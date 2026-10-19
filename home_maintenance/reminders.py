"""Background loop: a daily phone reminder (with Done / Snooze buttons) for each task that is due, a toner check
every 30 minutes, and the handler for the button taps."""
import datetime
import threading
import time

import appliances
import config
import db
import ha
import publish
import tasks
import toner

RETRY = 600            # after a failed send, wait 10 minutes before trying again
TONER_EVERY = 1800

_state = {"sent_on": None, "retry_at": 0.0, "toner_at": 0.0}
_lock = threading.Lock()


def reminder_time():
    try:
        h, m = str(config.options()["reminder_time"]).strip().split(":")[:2]
        return datetime.time(int(h), int(m))
    except Exception:
        return datetime.time(9, 0)


def digest_message(d):
    parts = []
    if d["overdue"]:
        parts.append(f"Overdue ({len(d['overdue'])}): " + ", ".join(t["name"] for t in d["overdue"]))
    if d["this_week"]:
        parts.append(f"This week ({len(d['this_week'])}): " + ", ".join(t["name"] for t in d["this_week"]))
    busy = [f"{m[5:]}/{m[2:4]}: {n}" for m, n in list(d["horizon"].items())[1:4] if n]
    if busy:
        parts.append("Coming up (month/year): " + ", ".join(busy))
    return "\n".join(parts)


def weekly_digest(now):
    """Mondays after the reminder time: one summary of what is overdue, due this week and coming up.
    Skipped when there is nothing overdue or due this week."""
    week = "%d-W%02d" % now.isocalendar()[:2]
    if now.weekday() != 0 or now.time() < reminder_time() or db.get_setting("digest_week") == week:
        return False
    service = ha.notify_service()
    d = tasks.digest(now.date())
    if not service or not (d["overdue"] or d["this_week"]):
        return False
    ha.send_message(service, "Home maintenance this week", digest_message(d), "home-maintenance-digest")
    db.set_setting("digest_week", week)
    return True


def warranty_check(now):
    """Reminds once per warranty, in the 30 days before it ends. Returns the appliances reminded."""
    service = ha.notify_service()
    sent = []
    for a in appliances.warranty_reminders(now.date()) if service else []:
        days = a["warranty_days_left"]
        when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
        ha.send_message(service, f"Warranty ending: {a['name']}", f"The warranty ends {when} ({a['warranty_end']}).",
                        f"home-maintenance-warranty-{a['id']}")
        appliances.mark_reminded(a["id"], a["warranty_end"])
        sent.append(a)
    return sent


def _daily(now):
    today = now.date().isoformat()
    with _lock:
        if _state["sent_on"] is None:
            _state["sent_on"] = db.get_setting("reminded_on")
        if _state["sent_on"] == today or now.time() < reminder_time() or time.time() < _state["retry_at"]:
            return []
        service = ha.notify_service()
        if not service:
            return []
        sent = []
        try:
            for t in tasks.due(now.date()):
                ha.send_due(service, t)
                sent.append(t)
                try:
                    ha.fire_event("home_maintenance_task_due", {"task_id": t["id"], "name": t["name"],
                                                                 "days_until": t["days_until"], "next_due": t["next_due"]})
                except Exception:
                    pass
        except Exception as e:
            print(f"Reminder failed: {e}", flush=True)
            if not sent:
                _state["retry_at"] = time.time() + RETRY
                return []
        _state["sent_on"] = today
        db.set_setting("reminded_on", today)
        return sent


def tick(now=None):
    """Sends today's reminders once (any time after the reminder time), then the Monday digest and any warranty
    reminder. Returns the tasks reminded."""
    now = now or datetime.datetime.now()
    sent = _daily(now)
    for extra in (weekly_digest, warranty_check):
        try:
            extra(now)
        except Exception as e:
            print(f"{extra.__name__} failed: {e}", flush=True)
    return sent


def on_button(kind, task_id):
    """Done / Snooze tapped on the phone."""
    if (tasks.done(task_id) if kind == "done" else tasks.snooze(task_id)):
        print(f"Notification button: {kind} for task {task_id}", flush=True)
        publish.sync()
    service = ha.notify_service()
    if service:
        try:
            ha.clear(service, task_id)
        except Exception:
            pass


def start():
    def loop():
        time.sleep(30)                 # let Home Assistant finish starting after a reboot
        while True:
            try:
                tick()
            except Exception as e:
                print(f"Reminder check failed: {e}", flush=True)
            try:
                publish.sync(force=time.time() >= _state["toner_at"])
            except Exception as e:
                print(f"Publishing to Home Assistant failed: {e}", flush=True)
            if time.time() >= _state["toner_at"]:
                _state["toner_at"] = time.time() + TONER_EVERY
                try:
                    toner.check()
                except Exception as e:
                    print(f"Toner check failed: {e}", flush=True)
            time.sleep(60)

    threading.Thread(target=loop, daemon=True, name="reminders").start()
    ha.listen(on_button)
