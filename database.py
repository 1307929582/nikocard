import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'unused',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id TEXT NOT NULL,
            pan TEXT,
            cvv TEXT,
            exp_month TEXT,
            exp_year TEXT,
            card_type TEXT,
            expire_time TIMESTAMP,
            activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (key_id) REFERENCES keys(key_id)
        );
    ''')
    conn.commit()
    conn.close()

def is_setup_complete():
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = 'admin_password'").fetchone()
    conn.close()
    return row is not None

def set_admin_password(password):
    conn = get_db()
    hashed = generate_password_hash(password)
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_password', ?)", (hashed,))
    conn.commit()
    conn.close()

def verify_password(password):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = 'admin_password'").fetchone()
    conn.close()
    if row:
        return check_password_hash(row['value'], password)
    return False

def import_keys(key_list):
    conn = get_db()
    added = 0
    for key_id in key_list:
        key_id = key_id.strip()
        if key_id:
            try:
                conn.execute("INSERT INTO keys (key_id) VALUES (?)", (key_id,))
                added += 1
            except sqlite3.IntegrityError:
                pass
    conn.commit()
    conn.close()
    return added

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM keys").fetchone()[0]
    unused = conn.execute("SELECT COUNT(*) FROM keys WHERE status = 'unused'").fetchone()[0]
    used = conn.execute("SELECT COUNT(*) FROM keys WHERE status = 'used'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM keys WHERE status = 'failed'").fetchone()[0]
    conn.close()
    return {'total': total, 'unused': unused, 'used': used, 'failed': failed}

def get_unused_key():
    conn = get_db()
    row = conn.execute("SELECT key_id FROM keys WHERE status = 'unused' LIMIT 1").fetchone()
    conn.close()
    return row['key_id'] if row else None

def mark_key_used(key_id):
    conn = get_db()
    conn.execute("UPDATE keys SET status = 'used', used_at = ? WHERE key_id = ?",
                 (datetime.utcnow(), key_id))
    conn.commit()
    conn.close()

def mark_key_failed(key_id):
    conn = get_db()
    conn.execute("UPDATE keys SET status = 'failed' WHERE key_id = ?", (key_id,))
    conn.commit()
    conn.close()

def save_card(key_id, card_data):
    conn = get_db()
    conn.execute('''
        INSERT INTO cards (key_id, pan, cvv, exp_month, exp_year, card_type, expire_time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        key_id,
        card_data.get('pan'),
        card_data.get('cvv'),
        card_data.get('exp_month'),
        card_data.get('exp_year'),
        card_data.get('card_type'),
        card_data.get('expire_time')
    ))
    conn.commit()
    conn.close()

def get_active_card():
    conn = get_db()
    row = conn.execute('''
        SELECT * FROM cards ORDER BY activated_at DESC LIMIT 1
    ''').fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_all_cards():
    conn = get_db()
    rows = conn.execute('SELECT * FROM cards ORDER BY activated_at DESC').fetchall()
    conn.close()
    return [dict(row) for row in rows]
