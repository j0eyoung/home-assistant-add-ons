"""Garmin Connect import: every resort ski or snowboard activity you record becomes a season-log day.

This is the Workout Tracker's Garmin connector (same garminconnect version, same sign-in flow). If the Workout
Tracker's Garmin token is in the shared Home Assistant config folder (/config/garmin_tokens.json, where its
setup script put it), this add-on reuses it and needs no sign-in. Otherwise sign in once from the Season log tab:
your Garmin password is only used for the sign-in and never saved; Garmin's login token is saved in this add-on's
own /data/garmin_tokens.json. (Add-ons can't read each other's /data, so only the shared copy can be reused.)

Each activity is matched to the nearest resort (within 5 miles of where it started). A Snowboard activity logs
as board, a Ski activity as skis; Garmin's older combined "Ski/Board" type logs as board (you mostly ride) and
can be changed in the log. Two activities on the same day at the same resort merge into one day."""
import datetime as dt
import os
import threading
import time
import traceback

import db
import resorts
import season
import util

TOKEN_PATH = os.getenv("GARMIN_TOKEN_PATH", "/data/garmin_tokens.json")              # this add-on's own login
SHARED_TOKEN_PATH = os.getenv("GARMIN_SHARED_TOKEN_PATH", "/config/garmin_tokens.json")  # the Workout Tracker's
SYNC_EVERY_HOURS = 3
LOOKBACK_DAYS = 45
M_TO_FT = 3.28084

BOARD_TYPES = {"resort_snowboarding", "snowboarding"}
SKI_TYPES = {"resort_skiing", "skiing"}
EITHER_TYPES = {"resort_skiing_snowboarding_ws", "resort_skiing_snowboarding"}

_pending = {"garmin": None}  # a sign-in waiting for its MFA code
_lock = threading.Lock()
_last = {"at": None, "added": 0, "error": None}


def _garmin(**kw):
    from garminconnect import Garmin
    return Garmin(**kw)


def token_path():
    """This add-on's own login if there is one, else the Workout Tracker's shared one, else None."""
    for p in (TOKEN_PATH, SHARED_TOKEN_PATH):
        if p and os.path.exists(p):
            return p
    return None


def connected():
    return token_path() is not None


def status():
    p = token_path()
    return {"connected": p is not None, "source": None if not p else "own" if p == TOKEN_PATH else "workout tracker",
            "needs_mfa": _pending["garmin"] is not None, "last_sync": _last}


def _friendly(e):
    name = type(e).__name__
    if name == "GarminConnectTooManyRequestsError":
        return "Garmin says too many attempts. Wait a few minutes and try again."
    if name == "GarminConnectAuthenticationError":
        return "Garmin didn't accept that email and password."
    return f"Couldn't reach Garmin ({name}). Try again in a few minutes."


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
    """Removes this add-on's own login (the Workout Tracker's shared token is left alone)."""
    _pending["garmin"] = None
    try:
        os.remove(TOKEN_PATH)
    except OSError:
        pass


def equipment(type_key):
    if type_key in SKI_TYPES:
        return "ski"
    if type_key in BOARD_TYPES or type_key in EITHER_TYPES:
        return "board"
    return None


def nearest_resort(lat, lon, max_miles=5):
    if lat is None or lon is None:
        return None
    best = min(resorts.load(), key=lambda r: util.miles(lat, lon, r["lat"], r["lon"]))
    return best if util.miles(lat, lon, best["lat"], best["lon"]) <= max_miles else None


def _note(a):
    bits = ["Garmin"]
    if a.get("distance"):
        bits.append(f"{a['distance'] / 1609.34:.1f} mi")
    if a.get("duration"):
        bits.append(f"{a['duration'] / 3600:.1f} h")
    if a.get("maxSpeed"):
        bits.append(f"top speed {a['maxSpeed'] * 2.23694:.0f} mph")
    return ", ".join(bits)


def import_activity(a):
    """Adds or merges one Garmin activity into the season log. Returns True if it changed the log."""
    type_key = (a.get("activityType") or {}).get("typeKey", "")
    eq = equipment(type_key)
    if not eq:
        return False
    gid = str(a.get("activityId"))
    if db.q("SELECT id FROM days WHERE ',' || garmin_ids || ',' LIKE ?", (f"%,{gid},%",)):
        return False  # already imported
    if db.q("SELECT key FROM sent WHERE key = ?", (f"garmin_skip:{gid}",)):
        return False  # you deleted this day
    date = (a.get("startTimeLocal") or "")[:10]
    if not date:
        return False
    r = nearest_resort(a.get("startLatitude"), a.get("startLongitude"))
    rid = r["id"] if r else "other"
    vert = round((a.get("elevationLoss") or 0) * M_TO_FT) or None
    speed = round(a["maxSpeed"] * 2.23694, 1) if a.get("maxSpeed") else None
    miles = round(a["distance"] / 1609.34, 1) if a.get("distance") else None
    hours = round(a["duration"] / 3600, 2) if a.get("duration") else None
    same = db.q("SELECT * FROM days WHERE date = ? AND resort_id = ? ORDER BY id LIMIT 1", (date, rid))
    if same:
        d = same[0]
        ids = ",".join(filter(None, [d.get("garmin_ids"), gid]))
        total = (d["vertical_ft"] or 0) + (vert or 0) or None
        notes = d["notes"] if d["notes"] else _note(a)
        db.x("UPDATE days SET garmin_ids = ?, vertical_ft = ?, notes = ?, top_speed_mph = MAX(COALESCE(top_speed_mph, 0), ?), "
             "distance_mi = COALESCE(distance_mi, 0) + ?, hours = COALESCE(hours, 0) + ? WHERE id = ?",
             (ids, total, notes, speed or 0, miles or 0, hours or 0, d["id"]))
    else:
        db.x("INSERT INTO days(date, resort_id, equipment, vertical_ft, notes, garmin_ids, top_speed_mph, distance_mi, hours) "
             "VALUES (?,?,?,?,?,?,?,?,?)", (date, rid, eq, vert, _note(a), gid, speed, miles, hours))
    return True


def sync():
    """Logs in with the saved token and imports recent ski/snowboard activities.
    Returns (added, error, today's newly added activities)."""
    if not connected():
        return 0, "Garmin isn't connected.", []
    start = (util.today() - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    # The first sync goes back to the start of last season, so season stats can compare the two
    if not db.q("SELECT key FROM sent WHERE key = 'garmin_backfill'"):
        last_season = dt.date.fromisoformat(season.season_start()) - dt.timedelta(days=365)
        start = last_season.isoformat()
    try:
        g = _garmin()
        g.login(token_path())
        acts = g.get_activities_by_date(start, util.today().isoformat()) or []
    except Exception as e:
        _last.update(at=util.now().strftime("%Y-%m-%d %H:%M"), added=0, error=_friendly(e))
        return 0, _friendly(e), []
    added = 0
    new_today = []
    for a in acts:
        if import_activity(a):
            added += 1
            if (a.get("startTimeLocal") or "")[:10] == util.today().isoformat():
                new_today.append(a)
    db.once("garmin_backfill")
    _last.update(at=util.now().strftime("%Y-%m-%d %H:%M"), added=added, error=None)
    return added, None, new_today


def start_background(on_new_today=None):
    """Sync shortly after start, then every few hours while connected."""
    def loop():
        time.sleep(60)
        while True:
            if connected():
                try:
                    _added, _error, new_today = sync()
                    if new_today and on_new_today:
                        on_new_today(new_today)
                except Exception:
                    traceback.print_exc()
            time.sleep(SYNC_EVERY_HOURS * 3600)
    threading.Thread(target=loop, daemon=True).start()
