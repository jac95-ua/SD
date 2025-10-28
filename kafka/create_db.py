"""Helper script to create the SQLite DB for central without starting Kafka.

Usage:
  python3 create_db.py --config kafka_config.local.yaml

This will create the DB file (path taken from config db_path or default
ev_charging.db) and create the required tables.
"""
import argparse
import sqlite3
import time
from pathlib import Path
import yaml


def load_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def init_db(db_path: str):
    p = Path(db_path)
    conn = sqlite3.connect(str(p))
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS cps (
            id TEXT PRIMARY KEY,
            location TEXT,
            price_kwh REAL,
            state TEXT,
            last_seen REAL
        )
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS drivers (
            id TEXT PRIMARY KEY,
            name TEXT
        )
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cp_id TEXT,
            driver_id TEXT,
            start_ts REAL,
            end_ts REAL,
            last_ts REAL,
            energy_kwh REAL DEFAULT 0.0,
            amount REAL DEFAULT 0.0,
            status TEXT
        )
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            ts REAL,
            kw REAL,
            amount REAL
        )
        '''
    )
    conn.commit()
    conn.close()
    print(f"DB inicializada en {p.resolve()}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='kafka_config.local.yaml')
    args = parser.parse_args()
    cfg = load_config(args.config)
    db_path = cfg.get('db_path', 'ev_charging.db')
    init_db(db_path)
