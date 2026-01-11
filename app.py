from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import database as db
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

API_REDEEM = 'https://mercury.wxie.de/api/keys/redeem'
API_QUERY = 'https://mercury.wxie.de/api/keys/query'

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
    if success is False:
        return False

    status = _extract_status(payload)
    if status is not None:
        status_text = str(status).strip().lower()
        if status_text in ('unused', 'valid', 'available', 'active', 'ok', 'success'):
            return True
        if status_text in ('used', 'invalid', 'expired', 'disabled', 'redeemed', 'fail', 'failed'):
            return False

    msg = payload.get('message') or payload.get('msg') or ''
    if isinstance(msg, str) and msg:
        msg_lower = msg.lower()
        if any(term in msg_lower for term in ('invalid', 'expired', 'used', 'redeem', 'fail', 'error')):
            return False
        if any(term in msg_lower for term in ('valid', 'unused', 'available', 'ok', 'success')):
            return True

    if success is True:
        return True
    return None

def _check_key_validity(key_id):
    try:
        resp = requests.post(API_QUERY, json={'key_id': key_id},
                             headers={'Content-Type': 'application/json'}, timeout=20)
        result = resp.json()
    except Exception:
        return None
    return _interpret_query_result(result)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.before_request
def before_request():
    db.init_db()

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
    cards = db.get_all_cards()
    return render_template('dashboard.html', stats=stats, active_card=active_card, cards=cards)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/api/import', methods=['POST'])
@login_required
def import_keys():
    data = request.get_json() or {}
    keys_text = data.get('keys', '')
    raw_list = keys_text.strip().split('\n') if keys_text else []
    key_list = [key_id.strip() for key_id in raw_list if key_id.strip()]

    valid_keys = []
    invalid = 0
    unchecked = 0

    for key_id in key_list:
        verdict = _check_key_validity(key_id)
        if verdict is True:
            valid_keys.append(key_id)
        elif verdict is False:
            invalid += 1
        else:
            unchecked += 1

    added = db.import_keys(valid_keys)
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
    key_id = db.get_unused_key()
    if not key_id:
        return jsonify({'success': False, 'error': '没有可用的卡密'})
    try:
        resp = requests.post(API_REDEEM, json={'key_id': key_id}, headers={'Content-Type': 'application/json'}, timeout=30)
        raw_text = resp.text
        try:
            result = resp.json()
        except Exception:
            result = None

        if isinstance(result, dict) and result.get('success'):
            card = result.get('card', {})
            db.mark_key_used(key_id)
            db.save_card(key_id, card)
            return jsonify({
                'success': True,
                'card': {
                    'pan': card.get('pan'),
                    'cvv': card.get('cvv'),
                    'exp_month': card.get('exp_month'),
                    'exp_year': card.get('exp_year'),
                    'card_type': card.get('card_type'),
                    'expire_time': card.get('expire_time')
                },
                'expire_minutes': result.get('expire_minutes', 60),
                'stats': db.get_stats()
            })
        else:
            db.mark_key_failed(key_id)
            message = '激活失败'
            if isinstance(result, dict):
                message = result.get('message', message)
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
        db.mark_key_failed(key_id)
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
    return jsonify(db.get_all_cards())

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
