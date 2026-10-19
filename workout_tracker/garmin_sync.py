"""Garmin Connect: sign in from the app (once), then sync resting heart rate, HRV, sleep and your latest activity
into garmin_metrics a few times a day so the coach can use them.

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
    except Exception as e:
        return False, _friendly(e)

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
    """Sync shortly after start, then every few hours while connected."""
    def loop():
        time.sleep(90)
        while True:
            if connected():
                try:
                    sync(datetime.date.fromisoformat(local_today()))
                except Exception:
                    pass
            time.sleep(SYNC_EVERY_HOURS * 3600)
    threading.Thread(target=loop, daemon=True).start()
