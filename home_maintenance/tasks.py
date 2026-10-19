"""Recurring maintenance tasks: interval in days or months, last done, next due, done/snooze, history.

Beyond the plain interval:
  * seasonal tasks (`active_months`): a task whose next due date falls out of season sleeps until the season starts;
  * spreading (`shift_days`): a new or just-completed task is nudged a few days (at most 10% of its interval, 14 days)
    to the lightest week, so the year's jobs do not all land on one Saturday;
  * status: ok / soon (due within 7 days) / overdue."""
import calendar
import collections
import datetime

import db

# (name, interval value, unit, active months or None)
PRESETS = [
    ("HVAC filter", 3, "months", None),
    ("Smoke/CO detector batteries", 6, "months", None),
    ("Water heater flush", 12, "months", None),
    ("Fridge water filter", 6, "months", None),
    ("Dishwasher/washer clean", 1, "months", None),
    ("Gutters", 6, "months", "10,11"),     # after the leaves fall
]
UNITS = ("days", "months")
SNOOZE_DAYS = 3
SOON_DAYS = 7


def today():
    return datetime.date.today()


def add_interval(d, value, unit):
    if unit == "days":
        return d + datetime.timedelta(days=value)
    m = d.month - 1 + value
    y, m = d.year + m // 12, m % 12 + 1
    return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def parse_months(value):
    """'11, 10,10' -> '10,11'; empty -> None. Raises ValueError for anything but months 1-12."""
    if value in (None, ""):
        return None
    try:
        months = sorted({int(p) for p in str(value).replace(" ", "").split(",") if p})
    except ValueError:
        raise ValueError("Active months look like 10,11 (1 to 12).")
    if not months or months[0] < 1 or months[-1] > 12:
        raise ValueError("Active months look like 10,11 (1 to 12).")
    return None if len(months) == 12 else ",".join(map(str, months))


def in_season(d, active_months):
    return not active_months or d.month in {int(m) for m in active_months.split(",")}


def clamp_season(d, active_months):
    """d itself when in season, else the first day of the next active month."""
    while not in_season(d, active_months):
        d = datetime.date(d.year + d.month // 12, d.month % 12 + 1, 1)
    return d


def _base(row):
    return datetime.date.fromisoformat(row["last_done"] or row["added"])


def assess(row, on=None):
    """Adds next_due, days_until (negative = overdue), status (ok / soon / overdue), due (due now and not snoozed)
    and in_season."""
    on = on or today()
    nxt = clamp_season(add_interval(_base(row), row["interval_value"], row["interval_unit"])
                       + datetime.timedelta(days=row.get("shift_days") or 0), row.get("active_months"))
    snoozed = row["snoozed_until"] and datetime.date.fromisoformat(row["snoozed_until"]) > on
    days = (nxt - on).days
    return {**row, "next_due": nxt.isoformat(), "days_until": days,
            "status": "overdue" if days < 0 else "soon" if days <= SOON_DAYS else "ok",
            "due": days <= 0 and not snoozed, "in_season": in_season(on, row.get("active_months"))}


def all_rows(on=None):
    return sorted((assess(r, on) for r in db.rows("SELECT * FROM tasks")), key=lambda t: (t["days_until"], t["name"]))


def due(on=None):
    return [t for t in all_rows(on) if t["due"]]


def get(task_id, on=None):
    r = db.rows("SELECT * FROM tasks WHERE id=?", (task_id,))
    return assess(r[0], on) if r else None


def spread(task_id, base, value, unit):
    """Shift (days) for the task's next due date: 0 to 10% of the interval (max 14) where the fewest other tasks
    fall in the same week. The smallest shift wins a tie, so a quiet calendar is left alone."""
    approx = value if unit == "days" else value * 30
    tol = min(14, approx // 10)
    if tol < 1:
        return 0
    weeks = collections.Counter(datetime.date.fromisoformat(t["next_due"]).isocalendar()[:2]
                                for t in all_rows() if t["id"] != task_id)
    nominal = add_interval(base, value, unit)
    return min(range(tol + 1), key=lambda s: (weeks[(nominal + datetime.timedelta(days=s)).isocalendar()[:2]], s))


def _check(value, unit):
    if unit not in UNITS or value < 1:
        raise ValueError("Interval must be 1 or more days or months.")


def add(name, value, unit="months", last_done=None, notes="", on=None, appliance_id=None, active_months=None):
    _check(value, unit)
    months = parse_months(active_months)
    on = on or today()
    tid = db.run("INSERT INTO tasks(name,interval_value,interval_unit,last_done,added,notes,appliance_id,active_months)"
                 " VALUES(?,?,?,?,?,?,?,?)",
                 (name.strip(), value, unit, last_done, on.isoformat(), notes, appliance_id, months))
    db.changed("UPDATE tasks SET shift_days=? WHERE id=?",
               (spread(tid, datetime.date.fromisoformat(last_done or on.isoformat()), value, unit), tid))
    return get(tid, on)


def update(task_id, **fields):
    allowed = {k: v for k, v in fields.items()
               if k in ("name", "interval_value", "interval_unit", "last_done", "notes", "appliance_id", "active_months")}
    _check(allowed.get("interval_value", 1), allowed.get("interval_unit", "days"))
    if "active_months" in allowed:
        allowed["active_months"] = parse_months(allowed["active_months"])
    if allowed:
        db.changed(f"UPDATE tasks SET {','.join(k + '=?' for k in allowed)} WHERE id=?", (*allowed.values(), task_id))
    return get(task_id)


def remove(task_id):
    return db.changed("DELETE FROM tasks WHERE id=?", (task_id,)) > 0


def done(task_id, note="", cost=None, on=None, parts=""):
    """Resets the clock to today (or `on`) and logs it. Returns None when there is no such task."""
    on = on or today()
    r = db.rows("SELECT * FROM tasks WHERE id=?", (task_id,))
    if not r:
        return None
    shift = spread(task_id, on, r[0]["interval_value"], r[0]["interval_unit"])
    db.run_many([("UPDATE tasks SET last_done=?, snoozed_until=NULL, shift_days=? WHERE id=?", (on.isoformat(), shift, task_id)),
                 ("INSERT INTO task_log(task_id,done_on,note,cost,parts) VALUES(?,?,?,?,?)",
                  (task_id, on.isoformat(), note or "", cost, parts or ""))])
    return get(task_id, on)


def snooze(task_id, days=SNOOZE_DAYS, on=None):
    on = on or today()
    n = db.changed("UPDATE tasks SET snoozed_until=? WHERE id=?",
                   ((on + datetime.timedelta(days=days)).isoformat(), task_id))
    return get(task_id, on) if n else None


def history(task_id):
    return db.rows("SELECT id, done_on, note, cost, parts FROM task_log WHERE task_id=? ORDER BY done_on DESC, id DESC", (task_id,))


def digest(on=None):
    """Overdue, due within 7 days, and how many tasks fall in each of the next 12 months."""
    on = on or today()
    rows = all_rows(on)
    horizon = collections.OrderedDict()
    for i in range(12):
        m = on.month - 1 + i
        horizon[f"{on.year + m // 12}-{m % 12 + 1:02d}"] = 0
    for t in rows:
        if t["days_until"] >= 0 and t["next_due"][:7] in horizon:
            horizon[t["next_due"][:7]] += 1
    return {"overdue": [t for t in rows if t["status"] == "overdue"],
            "this_week": [t for t in rows if t["status"] == "soon"], "horizon": horizon}


def seed_presets(on=None):
    """First start only: the presets are added once, so a task the user deletes stays deleted."""
    if db.get_setting("presets_seeded"):
        return 0
    for name, value, unit, months in PRESETS:
        add(name, value, unit, on=on, active_months=months)
    db.set_setting("presets_seeded", True)
    return len(PRESETS)
