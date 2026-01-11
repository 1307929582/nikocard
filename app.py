from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import database as db
from functools import wraps
from datetime import datetime, timezone
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

API_REDEEM = 'https://mercury.wxie.de/api/keys/redeem'
API_QUERY = 'https://mercury.wxie.de/api/keys/query'
DEFAULT_ADDRESS = '41 Glenn Rd C23, East Hartford, CT 06118'

def _extract_status(payload):
    if not isinstance(payload, dict):
        return None
    for path in (
        ('status',),
        ('key', 'status'),
        ('data', 'status'),
        ('key_info', 'status'),
        ('result', 'status'),
    ):
        cur = payload
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and cur is not None:
            return cur
    return None

def _interpret_query_result(payload):
    if not isinstance(payload, dict):
        return None

    for flag in ('valid', 'is_valid', 'available'):
        if flag in payload:
            return bool(payload[flag])

    success = payload.get('success')

    status = _extract_status(payload)
    if status is not None:
        status_text = str(status).strip().lower()
        if status_text in ('unused', 'valid', 'available', 'active', 'ok', 'success'):
            return True
        if status_text in ('used', 'invalid', 'expired', 'disabled', 'redeemed', 'fail', 'failed'):
            return False
        if any(term in status_text for term in ('未使用', '有效')):
            return True
        if any(term in status_text for term in ('已使用', '无效', '过期', '禁用')):
            return False

    msg = payload.get('message') or payload.get('error') or payload.get('msg') or ''
    if isinstance(msg, str) and msg:
        msg_lower = msg.lower()
        if any(term in msg_lower for term in ('invalid', 'expired', 'used', 'redeem', 'fail', 'error')):
            return False
        if any(term in msg_lower for term in ('valid', 'unused', 'available', 'ok', 'success')):
            return True
        if any(term in msg for term in ('已使用', '无效', '过期', '禁用', '被使用')):
            return False
        if any(term in msg for term in ('有效', '未使用', '可用')):
            return True

    if success is True:
        return True
    return None

def _is_used_error(message):
    if not message:
        return False
    msg = str(message).lower()
    return any(term in msg for term in ('已被使用', '已使用', '被使用', 'used', 'redeemed'))

def _check_key_validity(key_id, query_url):
    try:
        resp = requests.post(query_url, json={'key_id': key_id},
                             headers={'Content-Type': 'application/json'}, timeout=20)
        result = resp.json()
    except Exception:
        return None
    return _interpret_query_result(result)

def _parse_expire_time(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        try:
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        except Exception:
            return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(text)
    except Exception:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None

def _is_expired(value):
    dt = _parse_expire_time(value)
    if not dt:
        return False
    if dt.tzinfo is None:
        return dt <= datetime.utcnow()
    return dt <= datetime.now(timezone.utc)

def _filter_expired(cards):
    return [card for card in cards if not _is_expired(card.get('expire_time'))]

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.before_request
def before_request():
    db.init_db(default_provider=('默认卡商', API_REDEEM, API_QUERY, DEFAULT_ADDRESS))

@app.route('/')
def index():
    if not db.is_setup_complete():
        return redirect(url_for('setup'))
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if db.is_setup_complete():
        return redirect(url_for('login'))
    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm')
        if password and password == confirm and len(password) >= 4:
            db.set_admin_password(password)
            return redirect(url_for('login'))
        return render_template('setup.html', error='密码不匹配或长度不足4位')
    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not db.is_setup_complete():
        return redirect(url_for('setup'))
    if request.method == 'POST':
        password = request.form.get('password')
        if db.verify_password(password):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    stats = db.get_stats()
    active_card = db.get_active_card()
    cards = _filter_expired(db.get_all_cards())
    providers = db.get_providers()
    return render_template('dashboard.html', stats=stats, active_card=active_card, cards=cards, providers=providers)

@app.route('/settings')
@login_required
def settings():
    providers = db.get_provider_stats()
    return render_template('settings.html', providers=providers)

@app.route('/api/providers', methods=['POST'])
@login_required
def create_provider():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    redeem_url = (data.get('redeem_url') or '').strip()
    query_url = (data.get('query_url') or '').strip()
    address = (data.get('address') or '').strip()

    if not name or not redeem_url:
        return jsonify({'success': False, 'error': '请输入卡商名称和激活接口'})

    try:
        provider = db.add_provider(name, redeem_url, query_url or None, address or None)
    except Exception as e:
        msg = str(e)
        if 'UNIQUE' in msg:
            return jsonify({'success': False, 'error': '卡商名称已存在'})
        return jsonify({'success': False, 'error': msg})

    return jsonify({'success': True, 'provider': provider})

@app.route('/api/providers/<int:provider_id>', methods=['PATCH'])
@login_required
def update_provider(provider_id):
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    redeem_url = (data.get('redeem_url') or '').strip()
    query_url = (data.get('query_url') or '').strip()
    address = (data.get('address') or '').strip()

    if not name or not redeem_url:
        return jsonify({'success': False, 'error': '请输入卡商名称和激活接口'})

    try:
        provider = db.update_provider(provider_id, name, redeem_url, query_url or None, address or None)
    except Exception as e:
        msg = str(e)
        if 'UNIQUE' in msg:
            return jsonify({'success': False, 'error': '卡商名称已存在'})
        return jsonify({'success': False, 'error': msg})

    if not provider:
        return jsonify({'success': False, 'error': '卡商不存在'})
    return jsonify({'success': True, 'provider': provider})

@app.route('/api/providers/<int:provider_id>', methods=['DELETE'])
@login_required
def delete_provider(provider_id):
    try:
        db.delete_provider(provider_id)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': True})

@app.route('/api/import', methods=['POST'])
@login_required
def import_keys():
    data = request.get_json() or {}
    keys_text = data.get('keys', '')
    provider_id = data.get('provider_id')
    if provider_id is None:
        return jsonify({'success': False, 'error': '请选择卡商'})
    try:
        provider_id = int(provider_id)
    except Exception:
        return jsonify({'success': False, 'error': '卡商参数错误'})

    provider = db.get_provider(provider_id)
    if not provider:
        return jsonify({'success': False, 'error': '卡商不存在'})

    raw_list = keys_text.strip().split('\n') if keys_text else []
    key_list = [key_id.strip() for key_id in raw_list if key_id.strip()]

    valid_keys = []
    unchecked_keys = []
    invalid = 0
    unchecked = 0

    for key_id in key_list:
        if provider.get('query_url'):
            verdict = _check_key_validity(key_id, provider['query_url'])
        else:
            verdict = None
        if verdict is True:
            valid_keys.append(key_id)
        elif verdict is False:
            invalid += 1
        else:
            unchecked += 1
            unchecked_keys.append(key_id)

    added = db.import_keys_for_provider(valid_keys + unchecked_keys, provider_id)
    stats = db.get_stats()
    return jsonify({
        'success': True,
        'added': added,
        'invalid': invalid,
        'unchecked': unchecked,
        'total': len(key_list),
        'stats': stats
    })

@app.route('/api/activate', methods=['POST'])
@login_required
def activate():
    data = request.get_json() or {}
    provider_id = data.get('provider_id')
    if provider_id is None:
        return jsonify({'success': False, 'error': '请选择卡商'})
    try:
        provider_id = int(provider_id)
    except Exception:
        return jsonify({'success': False, 'error': '卡商参数错误'})

    provider = db.get_provider(provider_id)
    if not provider:
        return jsonify({'success': False, 'error': '卡商不存在'})
    if not provider.get('redeem_url'):
        return jsonify({'success': False, 'error': '卡商未配置激活接口'})

    skipped = 0
    while True:
        key_id = db.get_unused_key(provider_id)
        if not key_id:
            return jsonify({'success': False, 'error': '没有可用的卡密', 'stats': db.get_stats()})
        try:
            resp = requests.post(
                provider['redeem_url'],
                json={'key_id': key_id},
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            raw_text = resp.text
            try:
                result = resp.json()
            except Exception:
                result = None

            if isinstance(result, dict) and result.get('success'):
                card = result.get('card', {})
                db.mark_key_used(key_id, provider_id)
                db.save_card(key_id, card)
                return jsonify({
                    'success': True,
                    'card': {
                        'pan': card.get('pan'),
                        'cvv': card.get('cvv'),
                        'exp_month': card.get('exp_month'),
                        'exp_year': card.get('exp_year'),
                        'card_type': card.get('card_type'),
                        'expire_time': card.get('expire_time'),
                        'address': provider.get('address')
                    },
                    'expire_minutes': result.get('expire_minutes', 60),
                    'stats': db.get_stats(),
                    'skipped_used': skipped
                })
            else:
                db.mark_key_failed(key_id, provider_id)
                message = '激活失败'
                if isinstance(result, dict):
                    message = result.get('message') or result.get('error') or result.get('msg') or message
                used_error = _is_used_error(message) or _is_used_error(raw_text)
                if used_error:
                    skipped += 1
                    continue
                return jsonify({
                    'success': False,
                    'error': message,
                    'stats': db.get_stats(),
                    'debug': {
                        'status_code': resp.status_code,
                        'response': result,
                        'raw': raw_text[:2000] if raw_text else None
                    }
                })
        except Exception as e:
            db.mark_key_failed(key_id, provider_id)
            return jsonify({
                'success': False,
                'error': str(e),
                'stats': db.get_stats(),
                'debug': {
                    'exception': str(e)
                }
            })

@app.route('/api/stats')
@login_required
def get_stats():
    return jsonify(db.get_stats())

@app.route('/api/cards')
@login_required
def get_cards():
    return jsonify(_filter_expired(db.get_all_cards()))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
