"""Briefing sections that come from the other add-ons. Each returns {"headline": str, "lines": [str, ...]} or raises
(Off for "nothing to show", anything else for "Unavailable"). Where an add-on already publishes a Home Assistant sensor
that is used; otherwise its HTTP API is read over Home Assistant's internal add-on network.

Hostnames are c0a16a5a-<slug with underscores turned into hyphens> (the hash comes from the library's URL).
Nothing here writes to another add-on and no secret is kept in the code."""
import datetime
import json
import urllib.request

import config
import ha
import sections_ha

PREFIX = "c0a16a5a-"
HOSTS = {   # name: (hostname, port)
    "meals": (PREFIX + "meal-planner", 8502),
    "friends": (PREFIX + "friend-reminder", 8503),
    "work": (PREFIX + "work-tracker", 8505),
    "ski": (PREFIX + "ski-assistant", 8099),
    "money": (PREFIX + "budget", 8099),
}
SKI_MONTHS = (11, 12, 1, 2, 3, 4)


class Off(Exception):
    """A section with nothing to show right now (not installed, not set up, off season)."""


def _get(name, path, token=""):
    host, port = HOSTS[name]
    req = urllib.request.Request(f"http://{host}:{port}{path}", headers={"Authorization": f"Bearer {token}"} if token else {})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())


def _sensor(entity_id):
    """A sensor's state object, or None when it is missing (add-on not installed or not published yet)."""
    st = ha.state(entity_id)
    return st if st and st.get("state") not in ("unavailable", "unknown") else None


def _num(v):
    f = float(v)
    return f"{f:g}"


def _hhmm(v):
    """08:15 or an ISO timestamp -> 8:15 AM; anything else is shown as it came."""
    try:
        return sections_ha.clock(datetime.datetime.fromisoformat(str(v)).astimezone(sections_ha.tzinfo()))
    except ValueError:
        pass
    try:
        h, m = str(v).split(":")[:2]
        return sections_ha.clock(datetime.datetime(2000, 1, 1, int(h), int(m)))
    except ValueError:
        return str(v)


# ---------------------------------------------------------------- workout (Workout Tracker sensors)
def workout():
    st = _sensor("sensor.workout_today")
    if st is None:
        raise Off("Workout Tracker not found")
    a = st.get("attributes") or {}
    lines = [str(st["state"])]
    lines += [str(x) for x in (a.get("exercises") or [])[:6]]
    if a.get("cardio") and str(a["cardio"]) not in lines:
        lines.append(str(a["cardio"]))
    headline = str(st["state"])
    streak = _sensor("sensor.workout_streak")
    if streak is not None:
        try:
            n = int(float(streak["state"]))
            lines.append(f"Streak: {n} day{'s' if n != 1 else ''}")
            headline += f" · {n}-day streak"
        except ValueError:
            pass
    return {"headline": headline, "lines": lines}


# ---------------------------------------------------------------- meals (Meal Planner /meals/*)
_SLOTS = ("breakfast", "lunch", "dinner")


def _meals_on(day):
    meals = _get("meals", f"/meals/today?date={day.isoformat()}").get("meals") or []
    return sorted(meals, key=lambda m: _SLOTS.index(m["slot"]) if m.get("slot") in _SLOTS else 9)


def meals():
    today = sections_ha.now().date()
    todays = _meals_on(today)
    lines = [f"{m['slot'].capitalize()}: {m['name']}" + (" (cooked)" if m.get("cooked") else "") for m in todays]
    try:
        tomorrow = today + datetime.timedelta(days=1)
        prep = [m["name"] for m in _meals_on(tomorrow)]
        if prep:
            lines.append("Prep for tomorrow: " + ", ".join(prep))
        soon = [i["name"] for i in _get("meals", "/meals/pantry").get("use_soon") or []
                if str(i.get("expires") or "9999") <= tomorrow.isoformat()]
        if soon:
            lines.append("Use up: " + ", ".join(soon[:5]))
    except Exception:
        pass            # today's meals are still worth showing
    dinner = next((m for m in todays if m.get("slot") == "dinner"), None)
    if not todays:
        return {"headline": "Nothing planned", "lines": ["No meals planned today"] + lines}
    return {"headline": f"Dinner: {dinner['name']}" if dinner else f"{len(todays)} meal{'s' if len(todays) != 1 else ''}",
            "lines": lines}


# ---------------------------------------------------------------- friends (Friend Reminder /api/state)
def friends():
    state = _get("friends", "/api/state")
    per_day = int((state.get("settings") or {}).get("nudges_per_day") or 1)
    picks = [f for f in state.get("friends") or [] if f.get("birthday_today") or (f.get("due") and not f.get("snoozed"))]
    picks = picks[:max(1, per_day)]
    if not picks:
        return {"headline": "No one due", "lines": ["No one to reach out to today"]}
    lines = []
    for f in picks:
        if f.get("birthday_today"):
            lines.append(f"{f['name']}: birthday today")
        elif f.get("never_logged"):
            lines.append(f"{f['name']}: not logged yet")
        else:
            d = f.get("days_since")
            lines.append(f"{f['name']}: {d} day{'s' if d != 1 else ''} since you talked")
    return {"headline": ", ".join(f["name"] for f in picks), "lines": lines}


# ---------------------------------------------------------------- due today (Home Maintenance sensors, Work Tracker /api/state)
def _maintenance_part():
    st = _sensor("sensor.home_maintenance_due")
    if st is None:
        return None
    names = [str(n) for n in (st.get("attributes") or {}).get("due_tasks") or []]
    return [f"Home: {n}" for n in names]


def _work_part(today):
    key = config.options()["api_key"]
    if not key:
        return None
    out = []
    for t in _get("work", "/api/state", key).get("tasks") or []:
        due = str(t.get("due") or "")
        if not due or due > today.isoformat() or t.get("done_at"):
            continue
        if str(t.get("snoozed_until") or "")[:10] > today.isoformat():
            continue
        client = f" ({t['client']})" if t.get("client") else ""
        out.append(f"Work: {t.get('title') or 'Task'}{client}")
    return out


def due():
    today = sections_ha.now().date()
    lines, tried, failed = [], 0, 0
    for part in (_maintenance_part, lambda: _work_part(today)):
        try:
            got = part()
        except Exception:
            tried, failed = tried + 1, failed + 1
            continue
        if got is not None:
            tried += 1
            lines += got
    if tried and failed == tried:
        raise RuntimeError("no source answered")
    if not tried:
        raise Off("Not set up")
    if not lines:
        return {"headline": "Nothing due", "lines": ["Nothing due today"]}
    return {"headline": f"{len(lines)} due", "lines": lines[:8] + ([f"+ {len(lines) - 8} more"] if len(lines) > 8 else [])}


# ---------------------------------------------------------------- ski (Ski Assistant /api/best-days, /api/live)
def _lifts_open():
    live = _get("ski", "/api/live") or {}
    return {rid: v for rid, v in live.items() if isinstance(v, dict)}, any((v or {}).get("lifts_open") for v in live.values() if isinstance(v, dict))


def ski():
    month = sections_ha.now().month
    live, lifts = {}, False
    try:
        live, lifts = _lifts_open()
    except Exception:
        if month not in SKI_MONTHS:
            raise
    if month not in SKI_MONTHS and not lifts:
        raise Off("Off season")
    best = (_get("ski", "/api/best-days") or [None])[0]
    if not best:
        return {"headline": "No ski data", "lines": ["No ski data right now"]}
    bits = []
    if best.get("fresh_in") is not None:
        bits.append(f"{_num(best['fresh_in'])} in fresh")
    if best.get("tmax_f") is not None:
        bits.append(f"high {round(float(best['tmax_f']))}°F")
    if best.get("gust_mph") is not None:
        bits.append(f"gusts {round(float(best['gust_mph']))} mph")
    lines = [f"Best today: {best['resort']}" + (f" ({', '.join(bits)})" if bits else "")]
    leave = (best.get("leave") or {}).get("leave_at")
    if leave:
        lines.append(f"Leave by {_hhmm(leave)}")
    lv = live.get(best.get("id")) or {}
    if lv.get("lifts_total"):
        lines.append(f"Lifts open: {lv.get('lifts_open', 0)} of {lv['lifts_total']}")
    return {"headline": str(best["resort"]), "lines": lines}


# ---------------------------------------------------------------- money (Budget /api/summary)
def _usd(v):
    return f"${abs(float(v)):,.0f}"


def money():
    token = config.options()["api_token"]
    if not token:
        raise Off("Not set up")
    s = _get("money", "/api/summary", token)
    lines = []
    sts = s.get("safeToSpend")
    if sts and sts.get("left") is not None:
        left = float(sts["left"])
        lines.append(f"{_usd(left)} over the weekly allowance" if left < 0 else f"{_usd(left)} left to spend this week")
        if sts.get("daysLeft") is not None:
            lines.append(f"{sts['daysLeft']} days left in the week")
        headline = lines[0]
    elif s.get("budgeted") is not None:
        headline = f"{_usd(s.get('spent') or 0)} of {_usd(s['budgeted'])} spent"
    else:
        headline = "No budget data"
    if s.get("budgeted") is not None:
        lines.append(f"Spent {_usd(s.get('spent') or 0)} of {_usd(s['budgeted'])} this month")
    over = [o["category"] for o in s.get("overBudget") or [] if o.get("category")][:3]
    if over:
        lines.append("Over budget: " + ", ".join(over))
    return {"headline": headline, "lines": lines or [headline]}
