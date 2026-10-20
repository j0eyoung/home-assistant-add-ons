import json
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "work_tracker.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client TEXT NOT NULL,                -- client code, upper case (KISS, TORR)
    case_no TEXT NOT NULL DEFAULT '',    -- support case number, '' = none
    note TEXT NOT NULL DEFAULT '',
    start TEXT NOT NULL,                 -- local time, YYYY-MM-DD HH:MM:SS
    end TEXT,                            -- NULL = the timer is still running (survives restarts)
    billable INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS entries_start ON entries(start);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    client TEXT NOT NULL DEFAULT '',
    case_no TEXT NOT NULL DEFAULT '',
    due TEXT,                            -- YYYY-MM-DD; NULL = no deadline, never reminded
    snoozed_until TEXT,                  -- no reminder before this date
    notified_on TEXT,                    -- last day a reminder was sent
    done_at TEXT,                        -- NULL = open
    created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cases (
    case_no TEXT PRIMARY KEY,
    status TEXT NOT NULL,                -- short text pushed from the laptop
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
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


def get_setting(key, default=None):
    r = rows("SELECT value FROM settings WHERE key=?", (key,))
    return json.loads(r[0]["value"]) if r else default


def set_setting(key, value):
    run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value)))


if __name__ == "__main__":
    init_db()
    print("Database ready.")
