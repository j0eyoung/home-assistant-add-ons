import json
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "home_maintenance.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    interval_value INTEGER NOT NULL,
    interval_unit TEXT NOT NULL DEFAULT 'months',   -- days / months
    last_done TEXT,                                  -- YYYY-MM-DD; NULL = never (counted from `added`)
    added TEXT NOT NULL,                             -- YYYY-MM-DD
    snoozed_until TEXT,                              -- no reminders before this date
    notes TEXT DEFAULT '',
    appliance_id INTEGER REFERENCES appliances(id) ON DELETE SET NULL,
    active_months TEXT,                              -- '10,11' = seasonal task; NULL = all year
    shift_days INTEGER NOT NULL DEFAULT 0            -- spreads the year's jobs apart (see tasks.spread)
);
CREATE TABLE IF NOT EXISTS appliances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT DEFAULT '', model TEXT DEFAULT '', serial TEXT DEFAULT '',
    purchase_date TEXT, warranty_end TEXT,
    store TEXT DEFAULT '', price REAL,
    lifespan_years REAL,
    notes TEXT DEFAULT '',
    warranty_notified TEXT                           -- the warranty_end already reminded about
);
CREATE TABLE IF NOT EXISTS shutoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL DEFAULT 'water',              -- water / gas / electric / other
    name TEXT NOT NULL,
    location TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS attachments (             -- receipts and photos; the bytes live in the S3 bucket
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_type TEXT NOT NULL,                        -- appliance / shutoff
    owner_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size INTEGER NOT NULL,
    s3_key TEXT NOT NULL,
    added TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    done_on TEXT NOT NULL,
    note TEXT DEFAULT '',
    cost REAL,
    parts TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS toner (
    entity_id TEXT PRIMARY KEY,
    name TEXT,
    level REAL,                  -- last good reading in percent; NULL = never read
    status TEXT NOT NULL,        -- ok / low / unavailable
    alerted INTEGER NOT NULL DEFAULT 0,
    checked_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

# Columns added after the first release: (table, column, definition) for databases created before them
MIGRATIONS = [("tasks", "appliance_id", "INTEGER REFERENCES appliances(id) ON DELETE SET NULL"),
              ("tasks", "active_months", "TEXT"),
              ("tasks", "shift_days", "INTEGER NOT NULL DEFAULT 0"),
              ("task_log", "parts", "TEXT DEFAULT ''")]

_keeper = None   # one connection held open so the WAL files are not created and deleted on every query


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    global _keeper
    conn = connect()
    conn.execute("PRAGMA journal_mode=WAL")      # persistent; fewer eMMC writes than a rollback journal
    conn.executescript(SCHEMA)
    for table, col, ddl in MIGRATIONS:
        if col not in [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    conn.commit()
    conn.close()
    if _keeper is None:
        _keeper = sqlite3.connect(DB_PATH, check_same_thread=False)
        _keeper.execute("SELECT count(*) FROM sqlite_master").fetchall()


def rows(sql, args=()):
    conn = connect()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def run(sql, args=()):
    conn = connect()
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def changed(sql, args=()):
    """An UPDATE/DELETE; returns how many rows it touched."""
    conn = connect()
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def run_many(statements):
    """Several writes in one transaction (one fsync instead of one per row)."""
    conn = connect()
    try:
        ids = [conn.execute(sql, args).lastrowid for sql, args in statements]
        conn.commit()
        return ids
    finally:
        conn.close()


def get_setting(key, default=None):
    r = rows("SELECT value FROM settings WHERE key=?", (key,))
    return json.loads(r[0]["value"]) if r else default


def set_setting(key, value):
    run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)))


if __name__ == "__main__":
    init_db()
    print("Database ready.")
