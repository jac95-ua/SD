import sqlite3
import threading

DB_LOCK = threading.Lock()

def init_db(path='ev_central.db'):
    with DB_LOCK:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute('''
        CREATE TABLE IF NOT EXISTS cps (
            id TEXT PRIMARY KEY,
            location TEXT,
            price REAL,
            state TEXT
        )
        ''')
        conn.commit()
        conn.close()

def save_cp(path, cp_id, location, price=0.0, state='Activado'):
    with DB_LOCK:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute('REPLACE INTO cps (id, location, price, state) VALUES (?, ?, ?, ?)',
                    (cp_id, location, price, state))
        conn.commit()
        conn.close()

def load_cps(path):
    with DB_LOCK:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute('SELECT id, location, price, state FROM cps')
        rows = cur.fetchall()
        conn.close()
        return {r[0]: {'id': r[0], 'location': r[1], 'price': r[2], 'state': r[3]} for r in rows}
