from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
import database as db
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

API_REDEEM = 'https://mercury.wxie.de/api/keys/redeem'
API_QUERY = 'https://mercury.wxie.de/api/keys/query'

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

@app.route('/api/import', methods=['POST'])
@login_required
def import_keys():
    data = request.get_json()
    keys_text = data.get('keys', '')
    key_list = keys_text.strip().split('\n')
    added = db.import_keys(key_list)
    stats = db.get_stats()
    return jsonify({'success': True, 'added': added, 'stats': stats})

@app.route('/api/activate', methods=['POST'])
@login_required
def activate():
    key_id = db.get_unused_key()
    if not key_id:
        return jsonify({'success': False, 'error': '没有可用的卡密'})
    try:
        resp = requests.post(API_REDEEM, json={'key_id': key_id}, headers={'Content-Type': 'application/json'}, timeout=30)
        result = resp.json()
        if result.get('success'):
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
            return jsonify({'success': False, 'error': result.get('message', '激活失败'), 'stats': db.get_stats()})
    except Exception as e:
        db.mark_key_failed(key_id)
        return jsonify({'success': False, 'error': str(e), 'stats': db.get_stats()})

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
