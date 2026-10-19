"""Phone nudges, checked once a minute:
  * stop time (Mon-Fri): "log off?" if a timer is still running or today's hours are below the daily target
    (on Friday also when the week is below the weekly target);
  * task reminders: from the task time on, once a day for every task that is due or overdue (Done / Snooze);
  * weekly summary: hours per client on the summary day."""
import datetime
import threading
import time

import config
import db
import ha
import hours
import tasks

WINDOW = datetime.timedelta(hours=3)   # a restart right at the nudge time does not skip the day
RETRY = 600                            # after a failed send, wait 10 minutes
LATER = 1800                           # the "Later" button on the stop nudge: ask again in 30 minutes

_state = {"retry_at": 0.0, "later_until": 0.0, "stop_on": None, "summary_week": None}
_lock = threading.Lock()


def _time(key, default):
    try:
        h, m = str(config.options()[key]).strip().split(":")[:2]
        return datetime.time(int(h), int(m))
    except Exception:
        return default


def in_window(now, t):
    start = datetime.datetime.combine(now.date(), t)
    return start <= now < start + WINDOW


def fmt_h(minutes):
    return f"{minutes / 60:.1f} h"


def _stop_message(now, opts):
    """(title, message, buttons) when a stop nudge is due, else None."""
    run = hours.running()
    today = now.date()
    day_min = hours.total_minutes(today, today, now)
    if run:
        what = run["client"] + (f" case {run['case_no']}" if run["case_no"] else "")
        since = run["start"][11:16]
        return ("Log off?", f"Timer running on {what} since {since}. Today: {fmt_h(day_min)}.",
                [("WT_STOP", "Stop timer"), ("WT_LATER", "Later")])
    target = opts["daily_target"]
    if target and day_min < target * 60:
        return ("Log off?", f"Logged {fmt_h(day_min)} of {target:g} h today.", [("WT_LATER", "Later")])
    wtarget = opts["weekly_target"]
    if wtarget and today.weekday() == 4:
        ws = hours.week_start(today)
        wk = hours.total_minutes(ws, ws + datetime.timedelta(days=6), now)
        if wk < wtarget * 60:
            return ("Log off?", f"Week so far: {fmt_h(wk)} of {wtarget:g} h.", [("WT_LATER", "Later")])
    return None


def check_stop(now, service, opts):
    if now.weekday() > 4:
        return False
    t = _time("stop_time", datetime.time(17, 30))
    today = now.date().isoformat()
    if _state["stop_on"] is None:
        _state["stop_on"] = db.get_setting("stop_nudged_on")
    if _state["stop_on"] == today or not in_window(now, t) or time.time() < _state["later_until"]:
        return False
    msg = _stop_message(now, opts)
    if msg is None:
        return False
    ha.send(service, msg[0], msg[1], "wt-stop", msg[2])
    _state["stop_on"] = today
    db.set_setting("stop_nudged_on", today)
    return True


def check_tasks(now, service):
    if now.time() < _time("task_time", datetime.time(9, 0)):
        return 0
    n = 0
    for t in tasks.due_now(now.date()):
        who = " ".join(x for x in (t["client"], t["case_no"]) if x)
        overdue = t["due"] < now.date().isoformat()
        msg = (f"{who}: " if who else "") + ("Overdue since " if overdue else "Due ") + t["due"]
        ha.send(service, t["title"], msg, f"wt-task-{t['id']}",
                [(f"WT_TASKDONE_{t['id']}", "Done"), (f"WT_TASKSNOOZE_{t['id']}", "Snooze")])
        tasks.mark_notified(t["id"], now.date())
        n += 1
    return n


def summary_text(now, opts):
    ws = hours.week_start(now.date())
    tot = hours.totals(now.date(), now)
    per = tot["week"]
    lines = [f"{c['client']}: {c['hours']:.2f} h" for c in per] or ["No hours logged."]
    total = sum(c["hours"] for c in per)
    head = f"Total {total:.2f} h" + (f" of {opts['weekly_target']:g} h" if opts["weekly_target"] else "")
    return f"Week of {ws.isoformat()}", head + "\n" + "\n".join(lines)


def check_summary(now, service, opts):
    if config.DAYS[now.weekday()] != opts["summary_day"] or not in_window(now, _time("summary_time", datetime.time(17, 0))):
        return False
    week = hours.week_start(now.date()).isoformat()
    if _state["summary_week"] is None:
        _state["summary_week"] = db.get_setting("summary_week")
    if _state["summary_week"] == week:
        return False
    title, msg = summary_text(now, opts)
    ha.send(service, "Weekly hours: " + title, msg, "wt-summary")
    _state["summary_week"] = week
    db.set_setting("summary_week", week)
    return True


def tick(now=None):
    """One pass over all three nudges. Returns what was sent, e.g. ["stop", "tasks:2", "summary"]."""
    now = now or datetime.datetime.now()
    with _lock:
        if time.time() < _state["retry_at"]:
            return []
        service = ha.notify_service()
        if not service:
            return []
        opts = config.options()
        sent = []
        try:
            if check_stop(now, service, opts):
                sent.append("stop")
            n = check_tasks(now, service)
            if n:
                sent.append(f"tasks:{n}")
            if check_summary(now, service, opts):
                sent.append("summary")
        except Exception as e:
            print(f"Nudge failed: {e}", flush=True)
            if not sent:
                _state["retry_at"] = time.time() + RETRY
        return sent


def on_button(kind, ident):
    """A button tapped on the phone."""
    service = ha.notify_service()
    tag = None
    if kind == "stop":
        e = hours.stop()
        print(f"Notification button: stop timer ({e['client'] if e else 'none running'})", flush=True)
        tag = "wt-stop"
    elif kind == "later":
        _state["later_until"] = time.time() + LATER
        tag = "wt-stop"
    elif kind == "taskdone" and ident is not None:
        tasks.done(ident)
        tag = f"wt-task-{ident}"
    elif kind == "tasksnooze" and ident is not None:
        tasks.snooze(ident)
        tag = f"wt-task-{ident}"
    if service and tag:
        try:
            ha.clear(service, tag)
        except Exception:
            pass


def test():
    """Sends one stop-style notification right now so the buttons can be tried. Not counted as today's nudge."""
    service = ha.notify_service()
    if not service:
        raise RuntimeError("No phone found. Set notify_service in the add-on's Configuration tab.")
    now = datetime.datetime.now()
    msg = _stop_message(now, config.options()) or ("Log off?", "Test nudge. Nothing is running.", [("WT_LATER", "Later")])
    ha.send(service, msg[0], msg[1], "wt-stop", msg[2])


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
