import json
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "friend_reminder.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS friends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    tier TEXT NOT NULL DEFAULT 'good',   -- close / good / casual (see ranking.TIERS)
    interval_days INTEGER,               -- per-friend override; NULL = the tier's interval
    last_contact TEXT,                   -- YYYY-MM-DD; NULL = never logged (counted from `added`)
    birthday TEXT,                       -- MM-DD or YYYY-MM-DD
    notes TEXT DEFAULT '',
    snoozed_until TEXT,                  -- no nudges before this date (Snooze / Skip)
    opener TEXT,                         -- last conversation opener Claude drafted
    opener_at TEXT,
    added TEXT NOT NULL                  -- YYYY-MM-DD
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS ignored (     -- contacts set to "Don't remind" on an import, hidden on the next one
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    added TEXT NOT NULL
);
"""

_keeper = None   # one connection held open so the WAL files are not created and deleted on every query


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    global _keeper
    conn = connect()
    conn.execute("PRAGMA journal_mode=WAL")      # persistent; fewer eMMC writes than a rollback journal
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    if _keeper is None:
        _keeper = sqlite3.connect(DB_PATH, check_same_thread=False)
        _keeper.execute("SELECT count(*) FROM sqlite_master").fetchall()   # a connection opens the WAL only on its first read


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
