"""SQLite season log: ride days, lessons, gear service, and sent-notification keys."""
import os
import sqlite3
import threading
from contextlib import closing

DB_PATH = os.getenv("DB_PATH", "/config/ski.db")
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS days (id INTEGER PRIMARY KEY, date TEXT NOT NULL, resort_id TEXT NOT NULL,
  equipment TEXT NOT NULL CHECK (equipment IN ('board','ski')), vertical_ft INTEGER, notes TEXT DEFAULT '',
  garmin_ids TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY, date TEXT NOT NULL, resort_id TEXT DEFAULT '',
  skills TEXT DEFAULT '', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS service (id INTEGER PRIMARY KEY, date TEXT NOT NULL,
  equipment TEXT NOT NULL CHECK (equipment IN ('board','ski')), kind TEXT NOT NULL CHECK (kind IN ('wax','tune')));
CREATE TABLE IF NOT EXISTS sent (key TEXT PRIMARY KEY, at TEXT);
CREATE TABLE IF NOT EXISTS daily_snow (date TEXT PRIMARY KEY, text TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS forecast_check (date TEXT NOT NULL, resort_id TEXT NOT NULL, model TEXT NOT NULL,
  forecast_in REAL, observed_in REAL, PRIMARY KEY (date, resort_id, model));
CREATE TABLE IF NOT EXISTS plans (date TEXT NOT NULL, resort_id TEXT NOT NULL, created TEXT, PRIMARY KEY (date, resort_id));
"""


def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, closing(_conn()) as c:
        c.executescript(SCHEMA)
        # Columns added after the first release
        have = {r[1] for r in c.execute("PRAGMA table_info(days)")}
        for col in ("garmin_ids TEXT DEFAULT ''", "top_speed_mph REAL", "distance_mi REAL", "hours REAL"):
            if col.split()[0] not in have:
                c.execute(f"ALTER TABLE days ADD COLUMN {col}")
        c.commit()


def q(sql, args=()):
    with _lock, closing(_conn()) as c:
        return [dict(r) for r in c.execute(sql, args)]


def x(sql, args=()):
    with _lock, closing(_conn()) as c:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid


def once(key):
    """True the first time a key is seen (and records it); False afterwards. Avoids repeat alerts."""
    with _lock, closing(_conn()) as c:
        cur = c.execute("INSERT OR IGNORE INTO sent(key, at) VALUES (?, datetime('now'))", (key,))
        c.commit()
        return cur.rowcount == 1
