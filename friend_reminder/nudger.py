"""Daily nudges: at the set time, up to 1-2 phone notifications for the most overdue friends
(birthdays first), each with Done / Snooze / Skip buttons."""
import datetime
import threading
import time

import ai
import config
import db
import friends
import ha
import ranking

WINDOW = datetime.timedelta(hours=3)   # a restart or a busy minute right at the nudge time does not skip the day
RETRY = 600                            # after a failed send, wait 10 minutes before trying again

_state = {"sent_on": None, "retry_at": 0.0}
_lock = threading.Lock()


def nudge_time():
    try:
        h, m = str(config.options()["nudge_time"]).strip().split(":")[:2]
        return datetime.time(int(h), int(m))
    except Exception:
        return datetime.time(12, 0)


def window_start(now, t):
    """When the current nudge window opened: today's nudge time, or yesterday's while today's is not reached yet,
    so a late nudge time (say 23:30) keeps its full window past midnight."""
    start = datetime.datetime.combine(now.date(), t)
    return start if now >= start else start - datetime.timedelta(days=1)


def in_window(now, t):
    start = window_start(now, t)
    return start <= now < start + WINDOW


def _opener_for(f, reuse_from=None):
    """An opener for the notification when Claude is set up and there is something to go on. With reuse_from
    (a date), an opener already drafted that day is reused, so retries after a failed send do not pay again."""
    if not ai.available() or not (f.get("notes") or f["birthday_today"]):
        return None
    if reuse_from and f.get("opener") and str(f.get("opener_at") or "").startswith(reuse_from):
        return f["opener"]
    try:
        text = ai.opener(f)
        friends.save_opener(f["id"], text)
        return text
    except Exception as e:
        print(f"Opener for {f['name']} failed: {ai.describe_error(e)}", flush=True)
        return None


def tick(now=None):
    """Sends today's nudges once, inside the window after the nudge time. Returns the friends nudged."""
    now = now or datetime.datetime.now()
    today = now.date().isoformat()
    t = nudge_time()
    day = window_start(now, t).date().isoformat()     # the day this window belongs to (sent once per day)
    with _lock:
        if _state["sent_on"] is None:
            _state["sent_on"] = db.get_setting("nudged_on")
        if _state["sent_on"] == day or not in_window(now, t) or time.time() < _state["retry_at"]:
            return []
        service = ha.notify_service()
        if not service:
            return []
        picks = ranking.pick_nudges(friends.all_rows(), now.date(), config.options()["nudges_per_day"])
        sent = []
        try:
            for f in picks:
                ha.send_nudge(service, f, _opener_for(f, today))
                sent.append(f)
        except Exception as e:
            print(f"Nudge failed: {e}", flush=True)
            if not sent:
                _state["retry_at"] = time.time() + RETRY
                return []
        _state["sent_on"] = day
        db.set_setting("nudged_on", day)
        if sent:
            db.set_setting("last_nudge", {"date": today, "ids": [f["id"] for f in sent], "names": [f["name"] for f in sent]})
        return sent


def test(fid=None):
    """Sends one nudge right now (the top of the list, or a chosen friend) so the buttons can be tried.
    Does not count as today's nudge."""
    service = ha.notify_service()
    if not service:
        raise RuntimeError("No phone found. Set notify_service in the add-on's Configuration tab.")
    if fid is not None:
        f = friends.assessed(fid)
        if not f:
            raise LookupError("No such friend.")
    else:
        ranked = friends.ranked()
        if not ranked:
            raise LookupError("Add a friend first.")
        f = ranked[0]
    ha.send_nudge(service, f, _opener_for(f))
    return f


def on_button(kind, fid):
    """Done / Snooze / Skip tapped on the phone."""
    if friends.apply(kind, fid):
        print(f"Notification button: {kind} for friend {fid}", flush=True)
    service = ha.notify_service()
    if service:
        try:
            ha.clear(service, fid)
        except Exception:
            pass


def start():
    def loop():
        time.sleep(30)                 # let Home Assistant finish starting after a reboot
        while True:
            try:
                tick()
            except Exception as e:
                print(f"Nudge check failed: {e}", flush=True)
            time.sleep(60)

    threading.Thread(target=loop, daemon=True, name="nudger").start()
    ha.listen(on_button)
