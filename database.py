import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'data.db')

def _ensure_column(conn, table, column, ddl):
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(default_provider=None):
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
        CREATE TABLE IF NOT EXISTS providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            redeem_url TEXT NOT NULL,
            query_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    _ensure_column(conn, 'keys', 'provider_id', 'provider_id INTEGER')

    if default_provider:
        name, redeem_url, query_url = default_provider
        existing = conn.execute("SELECT COUNT(*) FROM providers").fetchone()[0]
        if existing == 0:
            conn.execute(
                "INSERT INTO providers (name, redeem_url, query_url) VALUES (?, ?, ?)",
                (name, redeem_url, query_url)
            )
        default_row = conn.execute(
            "SELECT id FROM providers ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if default_row:
            conn.execute(
                "UPDATE keys SET provider_id = ? WHERE provider_id IS NULL",
                (default_row['id'],)
            )
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

def import_keys_for_provider(key_list, provider_id):
    conn = get_db()
    added = 0
    for key_id in key_list:
        key_id = key_id.strip()
        if key_id:
            try:
                conn.execute(
                    "INSERT INTO keys (key_id, provider_id) VALUES (?, ?)",
                    (key_id, provider_id)
                )
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

def get_unused_key(provider_id=None):
    conn = get_db()
    if provider_id is None:
        row = conn.execute("SELECT key_id FROM keys WHERE status = 'unused' LIMIT 1").fetchone()
    else:
        row = conn.execute(
            "SELECT key_id FROM keys WHERE status = 'unused' AND provider_id = ? LIMIT 1",
            (provider_id,)
        ).fetchone()
    conn.close()
    return row['key_id'] if row else None

def mark_key_used(key_id, provider_id=None):
    conn = get_db()
    if provider_id is None:
        conn.execute(
            "UPDATE keys SET status = 'used', used_at = ? WHERE key_id = ?",
            (datetime.utcnow(), key_id)
        )
    else:
        conn.execute(
            "UPDATE keys SET status = 'used', used_at = ? WHERE key_id = ? AND provider_id = ?",
            (datetime.utcnow(), key_id, provider_id)
        )
    conn.commit()
    conn.close()

def mark_key_failed(key_id, provider_id=None):
    conn = get_db()
    if provider_id is None:
        conn.execute("UPDATE keys SET status = 'failed' WHERE key_id = ?", (key_id,))
    else:
        conn.execute(
            "UPDATE keys SET status = 'failed' WHERE key_id = ? AND provider_id = ?",
            (key_id, provider_id)
        )
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

def get_providers():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, redeem_url, query_url FROM providers ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_provider_stats():
    conn = get_db()
    rows = conn.execute('''
        SELECT
            p.id,
            p.name,
            p.redeem_url,
            p.query_url,
            COALESCE(SUM(CASE WHEN k.status = 'unused' THEN 1 ELSE 0 END), 0) AS unused,
            COALESCE(SUM(CASE WHEN k.status = 'used' THEN 1 ELSE 0 END), 0) AS used,
            COALESCE(SUM(CASE WHEN k.status = 'failed' THEN 1 ELSE 0 END), 0) AS failed,
            COUNT(k.id) AS total
        FROM providers p
        LEFT JOIN keys k ON k.provider_id = p.id
        GROUP BY p.id
        ORDER BY p.id ASC
    ''').fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_provider(provider_id):
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, redeem_url, query_url FROM providers WHERE id = ?",
        (provider_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def add_provider(name, redeem_url, query_url=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO providers (name, redeem_url, query_url) VALUES (?, ?, ?)",
        (name, redeem_url, query_url)
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, name, redeem_url, query_url FROM providers WHERE name = ?",
        (name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def update_provider(provider_id, name, redeem_url, query_url=None):
    conn = get_db()
    conn.execute(
        "UPDATE providers SET name = ?, redeem_url = ?, query_url = ? WHERE id = ?",
        (name, redeem_url, query_url, provider_id)
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, name, redeem_url, query_url FROM providers WHERE id = ?",
        (provider_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def delete_provider(provider_id):
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM keys WHERE provider_id = ?",
        (provider_id,)
    ).fetchone()[0]
    if count > 0:
        conn.close()
        raise ValueError('该卡商下仍有卡密，无法删除')
    conn.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
    conn.commit()
    conn.close()
