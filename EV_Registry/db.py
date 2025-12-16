import sqlite3
import threading
import uuid

# Usamos un lock para evitar problemas si hay muchas peticiones a la vez
DB_LOCK = threading.Lock()
DB_PATH = 'ev_registry.db'

def init_db():
    """Inicializa la tabla de registros si no existe."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('''
        CREATE TABLE IF NOT EXISTS registry (
            id TEXT PRIMARY KEY,
            location TEXT,
            token TEXT
        )
        ''')
        conn.commit()
        conn.close()

def register_cp(cp_id, location):
    """
    Registra un CP o actualiza sus datos.
    Genera un token de acceso seguro para él.
    """
    token = str(uuid.uuid4()) # Generamos una credencial única
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('REPLACE INTO registry (id, location, token) VALUES (?, ?, ?)',
                    (cp_id, location, token))
        conn.commit()
        conn.close()
    return token

def get_cp_token(cp_id):
    """Recupera el token de un CP para validarlo (si fuera necesario)."""
    with DB_LOCK:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT token FROM registry WHERE id = ?', (cp_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None