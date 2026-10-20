"""Workout history: completed workouts with every set as its own row, plus an auto-saved draft of
today's workout so ticks and set entries survive closing the page.

Dates use the Home Assistant time zone (Supervisor passes it to the add-on as TZ), so an evening
workout is logged on the right day.
"""
import datetime
import json
import os
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS workout_sets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_id INTEGER,          -- daily_logs.id of the completed workout
        date TEXT,
        exercise TEXT,
        set_number INTEGER,
        weight_lbs REAL,
        reps INTEGER,
        done INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS workout_drafts (
        date TEXT PRIMARY KEY,   -- local date of the workout in progress
        data JSON,               -- {"tracker": [rows], "checks": {item: bool}}
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS daily_checkins (
        date TEXT PRIMARY KEY,   -- local date
        kidney INTEGER,          -- how the left flank feels this morning, 1-10
        pelvic_floor INTEGER,    -- pelvic floor tightness, 1-10
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS ski_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,               -- local date of the test
        test TEXT,               -- insights.SKI_TESTS id
        value REAL               -- seconds or count
    )""",
    """CREATE TABLE IF NOT EXISTS biofeedback (
        date TEXT PRIMARY KEY,   -- day of the session with the pelvic PT
        data JSON,               -- {measure id: value} (insights.BIOFEEDBACK)
        unit TEXT,               -- mmHg, cmH2O or uV for the pressure readings
        notes TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS pt_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
        source TEXT,             -- me | ai (suggested by the coach)
        created TEXT,
        asked_on TEXT,           -- set when ticked off at the PT visit
        answer TEXT              -- what the PT said
    )""",
    """CREATE TABLE IF NOT EXISTS water_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        ts TEXT,
        oz REAL
    )""",
    """CREATE TABLE IF NOT EXISTS body_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        ts TEXT,                 -- local time of the reading
        kind TEXT,               -- weight (v1 = lb) | bp (v1 = systolic, v2 = diastolic, v3 = pulse)
        v1 REAL, v2 REAL, v3 REAL,
        source TEXT,             -- manual | ha (a Home Assistant sensor, e.g. Withings)
        UNIQUE (kind, ts, source)
    )""",
    """CREATE TABLE IF NOT EXISTS coach_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT,               -- user | assistant
        content TEXT,
        extra TEXT,              -- JSON: error, changes, rejected, applied, dismissed
        created TEXT
    )""",
]


def daily_scores(db_path, days=30, today=None):
    """{date: {"kidney", "pelvic_floor"}} for each recent day: the morning check-in if there was one, otherwise the
    scores logged with that day's last workout."""
    today = today or local_now().date()
    since = (today - datetime.timedelta(days=days)).isoformat()
    conn = sqlite3.connect(db_path)
    out = {}
    for d, k, p in conn.execute("SELECT date, kidney_flank_pain, pelvic_floor_tightness FROM daily_logs WHERE date >= ? "
                                "ORDER BY id", (since,)):
        if k is not None and p is not None:
            out[d] = {"kidney": k, "pelvic_floor": p}
    try:
        for d, k, p in conn.execute("SELECT date, kidney, pelvic_floor FROM daily_checkins WHERE date >= ?", (since,)):
            out[d] = {"kidney": k, "pelvic_floor": p}
    except sqlite3.OperationalError:
        pass
    conn.close()
    return out


def snow_days(db_path, limit=60):
    """{date: sport} for logged ski and snowboard days."""
    return {w["date"]: (w["workout"] or {}).get("sport", "snow") for w in get_history(db_path, limit)
            if (w.get("workout") or {}).get("type") == "snow"}


def save_checkin(db_path, kidney, pelvic_floor, date=None):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT OR REPLACE INTO daily_checkins (date, kidney, pelvic_floor, updated_at) VALUES (?, ?, ?, ?)",
                 (date or local_today(), max(1, min(10, int(kidney))), max(1, min(10, int(pelvic_floor))),
                  local_now().isoformat()))
    conn.commit()
    conn.close()


def get_checkin(db_path, date=None):
    """Today's morning check-in as {"kidney", "pelvic_floor"}, or None."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT kidney, pelvic_floor FROM daily_checkins WHERE date = ?",
                           (date or local_today(),)).fetchone()
    except sqlite3.OperationalError:   # table not created yet on an old database
        row = None
    conn.close()
    return {"kidney": row[0], "pelvic_floor": row[1]} if row else None


def local_now():
    try:
        tz = ZoneInfo(os.getenv("TZ") or "UTC")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return datetime.datetime.now(tz)


def local_today():
    return local_now().date().isoformat()


def ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    for statement in SCHEMA:
        conn.execute(statement)
    conn.commit()
    conn.close()


# --- Draft of today's workout ---------------------------------------------------------------------

def load_draft(db_path, date=None):
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT data FROM workout_drafts WHERE date = ?", (date or local_today(),)).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def save_draft(db_path, tracker_rows, checks, date=None):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO workout_drafts (date, data, updated_at) VALUES (?, ?, ?)",
        (date or local_today(), json.dumps({"tracker": tracker_rows, "checks": checks}), local_now().isoformat()))
    conn.commit()
    conn.close()


# --- Completed workouts ---------------------------------------------------------------------------

def _number(value, cast):
    try:
        return cast(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def complete_workout(db_path, rpe, pelvic_floor, kidney, notes, workout, tracker_rows, date=None):
    """Saves the workout and its sets, clears today's draft and returns the new daily_logs id."""
    date = date or local_today()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """INSERT INTO daily_logs (date, completed, rpe, pelvic_floor_tightness, kidney_flank_pain, notes, executed_workout)
           VALUES (?, 1, ?, ?, ?, ?, ?)""",
        (date, rpe, pelvic_floor, kidney, notes, json.dumps(workout)))
    log_id = c.lastrowid
    sets = []
    for row in tracker_rows:
        weight, reps, done = _number(row.get("Weight (lbs)"), float), _number(row.get("Reps"), int), bool(row.get("Done"))
        if done or weight or reps:   # skip untouched rows
            sets.append((log_id, date, str(row.get("Exercise") or "").strip(), _number(row.get("Set"), int), weight, reps, int(done)))
    c.executemany(
        "INSERT INTO workout_sets (log_id, date, exercise, set_number, weight_lbs, reps, done) VALUES (?, ?, ?, ?, ?, ?, ?)",
        sets)
    c.execute("DELETE FROM workout_drafts WHERE date = ?", (date,))
    conn.commit()
    conn.close()
    return log_id


def update_workout(db_path, log_id, **fields):
    """Adds fields to a saved workout's JSON (e.g. the personal records it set)."""
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT executed_workout FROM daily_logs WHERE id = ?", (log_id,)).fetchone()
    if row:
        try:
            data = json.loads(row[0] or "{}")
        except ValueError:
            data = {}
        data.update(fields)
        conn.execute("UPDATE daily_logs SET executed_workout = ? WHERE id = ?", (json.dumps(data), log_id))
        conn.commit()
    conn.close()


def get_history(db_path, limit=60):
    """Completed workouts, newest first, each with its sets."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    logs = [dict(r) for r in conn.execute(
        """SELECT id, date, rpe, pelvic_floor_tightness, kidney_flank_pain, notes, executed_workout
           FROM daily_logs ORDER BY date DESC, id DESC LIMIT ?""", (limit,))]
    sets = {}
    if logs:
        ids = [log["id"] for log in logs]
        for r in conn.execute(
                f"SELECT * FROM workout_sets WHERE log_id IN ({','.join('?' * len(ids))}) ORDER BY id", ids):
            sets.setdefault(r["log_id"], []).append(dict(r))
    conn.close()
    for log in logs:
        try:
            log["workout"] = json.loads(log.pop("executed_workout") or "{}")
        except ValueError:
            log["workout"] = {}
        log["sets"] = sets.get(log["id"], [])
    return logs


def exercise_progress(db_path, exercise):
    """Per workout day for one exercise: heaviest weight, total reps and sets done."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """SELECT date, MAX(weight_lbs), SUM(reps), SUM(done)
           FROM workout_sets WHERE exercise = ? GROUP BY date ORDER BY date""", (exercise,)).fetchall()
    conn.close()
    return [{"date": d, "top_weight_lbs": w or 0, "total_reps": r or 0, "sets_done": s or 0} for d, w, r, s in rows]


def last_session(db_path, exercise):
    """Sets done in the most recent session of an exercise: (date, [{weight, reps}]). (None, []) if never done."""
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT MAX(date) FROM workout_sets WHERE exercise = ? AND done = 1", (exercise,)).fetchone()
    if not row or not row[0]:
        conn.close()
        return None, []
    rows = conn.execute("SELECT weight_lbs, reps FROM workout_sets WHERE exercise = ? AND date = ? AND done = 1 "
                        "ORDER BY set_number", (exercise, row[0])).fetchall()
    conn.close()
    return row[0], [{"weight": w, "reps": r} for w, r in rows]


def logged_exercises(db_path):
    conn = sqlite3.connect(db_path)
    names = [r[0] for r in conn.execute(
        "SELECT exercise FROM workout_sets WHERE exercise != '' GROUP BY exercise ORDER BY COUNT(*) DESC")]
    conn.close()
    return names
