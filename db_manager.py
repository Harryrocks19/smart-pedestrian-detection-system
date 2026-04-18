"""
db_manager.py — Smart Pedestrian System Database Manager
Supports PostgreSQL (primary) + SQLite (fallback)

PostgreSQL setup:
  pip install psycopg2-binary
  Set DB_TYPE = "postgresql" and fill PG_PASSWORD below

SQLite setup:
  Nothing needed — works automatically as fallback
"""
import os
import sqlite3
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
DB_TYPE     = "postgresql"   # "postgresql" or "sqlite"

# PostgreSQL credentials — fill your password
PG_HOST     = "localhost"
PG_PORT     = 5432
PG_USER     = "postgres"
PG_PASSWORD = "root"   # ← replace with your actual password
PG_DBNAME   = "pedestrian_db"

# SQLite fallback
SQLITE_FILE = "logs/smart_pedestrian.db"

# ── Internal: get connection ──────────────────────────────────────────────────
def _get_pg():
    import psycopg2
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        user=PG_USER, password=PG_PASSWORD,
        dbname=PG_DBNAME
    )

def _get_sqlite():
    os.makedirs("logs", exist_ok=True)
    return sqlite3.connect(SQLITE_FILE, check_same_thread=False)

def get_conn():
    if DB_TYPE == "postgresql":
        return _get_pg()
    return _get_sqlite()

# ── Placeholder symbol (%s for PG, ? for SQLite) ─────────────────────────────
def ph():
    return "%s" if DB_TYPE == "postgresql" else "?"

# ── Init tables ───────────────────────────────────────────────────────────────
def init_db():
    os.makedirs("logs", exist_ok=True)
    try:
        conn = get_conn()
        c    = conn.cursor()

        if DB_TYPE == "postgresql":
            c.execute("""
                CREATE TABLE IF NOT EXISTS detection_log (
                    id         SERIAL PRIMARY KEY,
                    timestamp  TIMESTAMP,
                    people     INTEGER,
                    violations INTEGER,
                    vehicles   INTEGER,
                    risk       INTEGER,
                    alert      TEXT
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS alert_log (
                    id        SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP,
                    type      TEXT,
                    people    INTEGER,
                    vehicles  INTEGER,
                    risk      INTEGER
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS signal_log (
                    id        SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP,
                    signal    TEXT,
                    people    INTEGER,
                    vehicles  INTEGER,
                    risk      INTEGER
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS anomaly_log (
                    id        SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP,
                    z_score   REAL,
                    people    INTEGER
                )""")
            c.execute("""
                CREATE TABLE IF NOT EXISTS queue_log (
                    id          SERIAL PRIMARY KEY,
                    timestamp   TIMESTAMP,
                    queue_count INTEGER
                )""")
        else:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS detection_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT, people INTEGER, violations INTEGER,
                    vehicles INTEGER, risk INTEGER, alert TEXT);
                CREATE TABLE IF NOT EXISTS alert_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT, type TEXT, people INTEGER,
                    vehicles INTEGER, risk INTEGER);
                CREATE TABLE IF NOT EXISTS signal_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT, signal TEXT, people INTEGER,
                    vehicles INTEGER, risk INTEGER);
                CREATE TABLE IF NOT EXISTS anomaly_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT, z_score REAL, people INTEGER);
                CREATE TABLE IF NOT EXISTS queue_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT, queue_count INTEGER);
            """)

        conn.commit()
        conn.close()
        print(f"Database initialized: {DB_TYPE.upper()} — {PG_DBNAME if DB_TYPE == 'postgresql' else SQLITE_FILE}")
    except Exception as e:
        print(f"DB init error: {e}")
        if DB_TYPE == "postgresql":
            print("Falling back to SQLite...")
            import db_manager as _self
            _self.DB_TYPE = "sqlite"
            init_db()

# ── Log functions ─────────────────────────────────────────────────────────────
def _execute(sql, params):
    try:
        conn = get_conn()
        conn.cursor().execute(sql, params)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB write error: {e}")

def log_detection(people, violations, vehicles, risk, alert):
    p = ph()
    _execute(
        f"INSERT INTO detection_log (timestamp,people,violations,vehicles,risk,alert) VALUES ({p},{p},{p},{p},{p},{p})",
        (datetime.now(), people, violations, vehicles, risk, alert)
    )

def log_alert(alert_type, people, vehicles, risk):
    p = ph()
    _execute(
        f"INSERT INTO alert_log (timestamp,type,people,vehicles,risk) VALUES ({p},{p},{p},{p},{p})",
        (datetime.now(), alert_type, people, vehicles, risk)
    )

def log_signal(signal, people, vehicles, risk):
    p = ph()
    _execute(
        f"INSERT INTO signal_log (timestamp,signal,people,vehicles,risk) VALUES ({p},{p},{p},{p},{p})",
        (datetime.now(), signal, people, vehicles, risk)
    )

def log_anomaly(z_score, people):
    p = ph()
    _execute(
        f"INSERT INTO anomaly_log (timestamp,z_score,people) VALUES ({p},{p},{p})",
        (datetime.now(), z_score, people)
    )

def log_queue(queue_count):
    p = ph()
    _execute(
        f"INSERT INTO queue_log (timestamp,queue_count) VALUES ({p},{p})",
        (datetime.now(), queue_count)
    )

# ── Query function ────────────────────────────────────────────────────────────
def query(sql, params=()):
    try:
        conn = get_conn()
        c    = conn.cursor()
        c.execute(sql, params)
        cols = [d[0] for d in c.description]
        rows = [dict(zip(cols, row)) for row in c.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"DB query error: {e}")
        return []

# ── Dashboard helper: load table as pandas DataFrame ─────────────────────────
def load_table(table, limit=500):
    try:
        import pandas as pd
        conn = get_conn()
        if DB_TYPE == "postgresql":
            import psycopg2
            df = pd.read_sql(f"SELECT * FROM {table} ORDER BY id DESC LIMIT {limit}", conn)
        else:
            df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC LIMIT {limit}", conn)
        conn.close()
        return df if len(df) > 0 else None
    except Exception as e:
        print(f"DB load error ({table}): {e}")
        return None

if __name__ == "__main__":
    init_db()
    print("Testing insert...")
    log_detection(3, 1, 2, 0, "NO")
    log_alert("CROWD", 5, 1, 0)
    rows = query("SELECT * FROM detection_log ORDER BY id DESC LIMIT 3")
    print(f"Detection rows: {rows}")
    print("All OK!")
