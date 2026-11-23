"""Garmin Connect: sign in from the app (once), then sync resting heart rate, HRV, sleep and your latest activity
into garmin_metrics a few times a day so the coach can use them. Every hour it also copies the last ten days of
activities into garmin_activities, so Today can offer your ski days and cardio instead of you typing them in.

Your Garmin password is only used for the sign-in itself and is never saved. What is saved is the login token
(/data/garmin_tokens.json), which Garmin lets this add-on refresh on its own."""
import datetime
import json
import os
import sqlite3
import threading
import time

from db import DB_PATH

TOKEN_PATH = os.getenv("GARMIN_TOKEN_PATH", "/data/garmin_tokens.json")
SYNC_EVERY_HOURS = 6
ACTIVITY_EVERY_MINUTES = 60
ACTIVITY_DAYS = 10                # how far back each activity check looks
CHECK_AGAIN_SECS = 120            # "Check Garmin" more often than this just reuses the last check
_last_check = {"at": 0.0}

_pending = {"garmin": None}   # a sign-in waiting for its MFA code
_lock = threading.Lock()


def _garmin(**kw):
    from garminconnect import Garmin
    return Garmin(**kw)


def connected():
    return os.path.exists(TOKEN_PATH)


def last_sync():
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT date, resting_hr FROM garmin_metrics ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        return {"date": row[0], "resting_hr": row[1]} if row else None
    except sqlite3.Error:
        return None


def status():
    return {"connected": connected(), "needs_mfa": _pending["garmin"] is not None, "last": last_sync()}


def _friendly(e):
    name = type(e).__name__
    if name == "GarminConnectTooManyRequestsError":
        return "Garmin says too many attempts. Wait a few minutes and try again."
    if name == "GarminConnectAuthenticationError":
        return "Garmin didn't accept that email and password."
    return f"Couldn't sign in to Garmin ({name}). Try again in a few minutes."


def connect(email, password):
    """First step. Returns {"ok", "needs_mfa", "error"}. The password is not kept."""
    with _lock:
        try:
            g = _garmin(email=email.strip(), password=password, return_on_mfa=True)
            mfa, _state = g.login()
        except Exception as e:
            return {"ok": False, "needs_mfa": False, "error": _friendly(e)}
        if mfa:
            _pending["garmin"] = g
            return {"ok": True, "needs_mfa": True, "error": None}
        try:
            g.client.dump(TOKEN_PATH)
        except Exception as e:
            return {"ok": False, "needs_mfa": False, "error": f"Signed in, but couldn't save the login ({type(e).__name__})."}
        g.password = None
        return {"ok": True, "needs_mfa": False, "error": None}


def submit_mfa(code):
    """Second step, when Garmin sent a verification code."""
    with _lock:
        g = _pending["garmin"]
        if g is None:
            return {"ok": False, "error": "No sign-in is waiting for a code. Start again."}
        try:
            g.resume_login(None, "".join(code.split()))
            g.client.dump(TOKEN_PATH)
        except Exception as e:
            return {"ok": False, "error": "That code didn't work. Check it and try again."
                    if type(e).__name__ != "GarminConnectTooManyRequestsError" else _friendly(e)}
        g.password = None
        _pending["garmin"] = None
        return {"ok": True, "error": None}


def disconnect():
    _pending["garmin"] = None
    try:
        os.remove(TOKEN_PATH)
    except OSError:
        pass


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS garmin_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, resting_hr INTEGER, latest_activity_type TEXT,
        duration_secs INTEGER, avg_hr INTEGER, max_hr INTEGER, raw_data JSON)""")
    have = {r[1] for r in conn.execute("PRAGMA table_info(garmin_metrics)")}
    for col in ("hrv_avg INTEGER", "sleep_secs INTEGER", "body_battery INTEGER"):
        if col.split()[0] not in have:
            conn.execute(f"ALTER TABLE garmin_metrics ADD COLUMN {col}")


def _try(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


def sync(today=None):
    """Logs in with the saved token and stores today's numbers. Returns (ok, message)."""
    if not connected():
        return False, "Garmin isn't connected."
    today = (today or datetime.date.today()).isoformat()
    try:
        g = _garmin()
        g.login(TOKEN_PATH)
        stats = _try(g.get_stats, today) or {}
        rhr = stats.get("restingHeartRate") or stats.get("restingHeartRateInBeatsPerMinute") or 0
        hrv = (_try(g.get_hrv_data, today) or {}).get("hrvSummary", {}).get("lastNightAvg")
        sleep = ((_try(g.get_sleep_data, today) or {}).get("dailySleepDTO") or {}).get("sleepTimeSeconds")
        battery = stats.get("bodyBatteryMostRecentValue")
        activities = _try(g.get_activities, 0, 1) or []
        latest = activities[0] if activities else {}
        recent = _fetch_activities(g, today)
    except Exception as e:
        return False, _friendly(e)
    _last_check["at"] = time.time()
    store_activities(recent)

    conn = sqlite3.connect(DB_PATH)
    _ensure_table(conn)
    conn.execute("DELETE FROM garmin_metrics WHERE date = ?", (today,))   # one row per day, the newest values
    conn.execute(
        """INSERT INTO garmin_metrics (date, resting_hr, latest_activity_type, duration_secs, avg_hr, max_hr, raw_data,
                                       hrv_avg, sleep_secs, body_battery) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (today, rhr, (latest.get("activityType") or {}).get("typeKey", "unknown"), latest.get("duration", 0),
         latest.get("averageHR", 0), latest.get("maxHR", 0), json.dumps(latest), hrv, sleep, battery))
    conn.commit()
    conn.close()
    return True, "Garmin data synced."


# --- Activities: ski days and cardio your watch recorded ------------------------------------------------------------

KIND_LABELS = {"skiing": "Skiing", "snowboarding": "Snowboarding", "snow": "Skiing or snowboarding",
               "walk": "Walk", "run": "Run", "bike": "Ride", "row": "Row", "swim": "Swim"}
SNOW_KINDS = {"skiing", "snowboarding", "snow"}
CARDIO_KINDS = {"walk", "run", "bike", "row", "swim"}   # the app's own cardio types


def activity_kind(type_key):
    """Garmin's activity type -> a snow sport or one of the app's cardio types; None for anything else
    (strength, yoga and the like are logged in the app itself)."""
    t = (type_key or "").lower()
    if "resort_skiing_snowboarding" in t:
        return "snow"                       # Garmin's combined type: you say which when you log it
    if "snowboard" in t:
        return "snowboarding"
    if "ski" in t:
        return "skiing"
    if "run" in t:
        return "run"
    if "walk" in t or "hik" in t or "treadmill" in t:
        return "walk"
    if "cycl" in t or "bik" in t or "ride" in t or "spin" in t:
        return "bike"
    if "row" in t:
        return "row"
    if "swim" in t:
        return "swim"
    return None


def _ensure_activity_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS garmin_activities (
        activity_id TEXT PRIMARY KEY, date TEXT, start TEXT, type_key TEXT, kind TEXT, name TEXT, minutes INTEGER,
        distance_km REAL, avg_hr INTEGER, calories INTEGER, status TEXT DEFAULT 'new', log_id INTEGER)""")


def _fetch_activities(g, today_iso):
    start = (datetime.date.fromisoformat(today_iso) - datetime.timedelta(days=ACTIVITY_DAYS)).isoformat()
    acts = _try(g.get_activities_by_date, start, today_iso)
    if acts is None:   # older library: the latest few, filtered to the same days
        acts = [a for a in (_try(g.get_activities, 0, 30) or []) if str(a.get("startTimeLocal") or "")[:10] >= start]
    return acts or []


def store_activities(acts):
    """Adds new activities and refreshes known ones, keeping whether each was already logged or set aside."""
    rows = []
    for a in acts or []:
        start = str(a.get("startTimeLocal") or "")
        type_key = (a.get("activityType") or {}).get("typeKey") or ""
        kind = activity_kind(type_key)
        minutes = int(round((a.get("duration") or 0) / 60))
        if not a.get("activityId") or not kind or minutes < 1 or len(start) < 10:
            continue
        rows.append((str(a["activityId"]), start[:10], start, type_key, kind, (a.get("activityName") or "").strip()[:120],
                     minutes, round((a.get("distance") or 0) / 1000, 2) or None, int(a.get("averageHR") or 0) or None,
                     int(a.get("calories") or 0) or None))
    if not rows:
        return 0
    conn = sqlite3.connect(DB_PATH)
    _ensure_activity_table(conn)
    conn.executemany(
        """INSERT INTO garmin_activities (activity_id, date, start, type_key, kind, name, minutes, distance_km, avg_hr, calories)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(activity_id) DO UPDATE SET date = excluded.date, start = excluded.start, type_key = excluded.type_key,
             kind = excluded.kind, name = excluded.name, minutes = excluded.minutes, distance_km = excluded.distance_km,
             avg_hr = excluded.avg_hr, calories = excluded.calories""", rows)
    conn.commit()
    conn.close()
    return len(rows)


def sync_activities(today=None, force=False):
    """Just the recent activities (one quick call). Returns (ok, message)."""
    if not connected():
        return False, "Garmin isn't connected."
    if not force and time.time() - _last_check["at"] < CHECK_AGAIN_SECS:
        return True, "Checked a moment ago."
    today = (today or datetime.date.today()).isoformat()
    try:
        g = _garmin()
        g.login(TOKEN_PATH)
        acts = _fetch_activities(g, today)
    except Exception as e:
        return False, _friendly(e)
    _last_check["at"] = time.time()
    n = store_activities(acts)
    return True, f"Checked Garmin: {n} recent activit{'y' if n == 1 else 'ies'}."


def activities(since_iso, statuses=("new",)):
    """Stored activities from a date on, oldest first."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        _ensure_activity_table(conn)
        marks = ",".join("?" * len(statuses))
        rows = [dict(r) for r in conn.execute(
            f"SELECT * FROM garmin_activities WHERE date >= ? AND status IN ({marks}) ORDER BY start",
            (since_iso, *statuses))]
        conn.close()
    except sqlite3.Error:
        return []
    for r in rows:
        r["label"] = KIND_LABELS.get(r["kind"], r["kind"])
    return rows


def get_activity(activity_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        _ensure_activity_table(conn)
        row = conn.execute("SELECT * FROM garmin_activities WHERE activity_id = ?", (str(activity_id),)).fetchone()
        conn.close()
    except sqlite3.Error:
        return None
    if not row:
        return None
    r = dict(row)
    r["label"] = KIND_LABELS.get(r["kind"], r["kind"])
    return r


def mark(activity_ids, status, log_id=None):
    """status: logged (it's in the app now) or ignored (you said it wasn't one)."""
    ids = [str(i) for i in activity_ids or []]
    if not ids:
        return
    conn = sqlite3.connect(DB_PATH)
    _ensure_activity_table(conn)
    conn.executemany("UPDATE garmin_activities SET status = ?, log_id = ? WHERE activity_id = ?",
                     [(status, log_id, i) for i in ids])
    conn.commit()
    conn.close()


def recovery_signal(today_iso):
    """Is today a day to go lighter, by Garmin? {"level": None|"lighter"|"recovery", "reasons": [...]}.

    Compared with your own recent numbers (14 days), not population norms. One sign of poor recovery makes the day
    lighter; two or more make it a recovery day. Needs today's synced numbers; with no data nothing changes."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM garmin_metrics WHERE date <= ? ORDER BY date DESC LIMIT 15", (today_iso,))]
        conn.close()
    except sqlite3.Error:
        return {"level": None, "reasons": []}
    if not rows or rows[0]["date"] != today_iso:
        return {"level": None, "reasons": []}
    today, past = rows[0], rows[1:]

    def median(key):
        vals = sorted(r[key] for r in past if r.get(key))
        return vals[len(vals) // 2] if len(vals) >= 5 else None

    reasons = []
    sleep = today.get("sleep_secs")
    if sleep and sleep < 6 * 3600:
        reasons.append(f"short sleep ({sleep / 3600:.1f} h)")
    battery = today.get("body_battery")
    if battery and battery < 30:
        reasons.append(f"low body battery ({battery})")
    hrv, hrv_usual = today.get("hrv_avg"), median("hrv_avg")
    if hrv and hrv_usual and hrv < 0.85 * hrv_usual:
        reasons.append(f"HRV {hrv} (your usual {hrv_usual})")
    rhr, rhr_usual = today.get("resting_hr"), median("resting_hr")
    if rhr and rhr_usual and rhr > rhr_usual + 5:
        reasons.append(f"resting heart rate {rhr} (your usual {rhr_usual})")
    level = "recovery" if len(reasons) >= 2 else "lighter" if reasons else None
    return {"level": level, "reasons": reasons}


def start_background(local_today):
    """Sync shortly after start, then everything every few hours and the recent activities every hour."""
    def loop():
        time.sleep(90)
        last_full = 0.0
        while True:
            if connected():
                try:
                    today = datetime.date.fromisoformat(local_today())
                    if time.time() - last_full >= SYNC_EVERY_HOURS * 3600:
                        sync(today)
                        last_full = time.time()
                    else:
                        sync_activities(today, force=True)
                except Exception:
                    pass
            time.sleep(ACTIVITY_EVERY_MINUTES * 60)
    threading.Thread(target=loop, daemon=True).start()
