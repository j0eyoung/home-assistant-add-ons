"""Builds the briefing: one entry per section, each failing on its own ("Unavailable", never a blank screen)
and publishing itself as sensor.daily_briefing_<key>. Kept in memory only."""
import datetime
import threading
import time

import addons
import config
import ha
import sections_ha

Off = addons.Off        # raised by a builder for "nothing to show right now" (off season, not set up)

SECTIONS = [
    ("today", "Today", "mdi:calendar-today", sections_ha.today_section),
    ("workout", "Workout", "mdi:dumbbell", addons.workout),
    ("meals", "Meals", "mdi:silverware-fork-knife", addons.meals),
    ("due", "Due today", "mdi:wrench-clock", addons.due),
    ("ski", "Ski", "mdi:ski", addons.ski),
    ("money", "Money", "mdi:cash", addons.money),
    ("shopping", "Shopping", "mdi:cart", sections_ha.shopping_section),
]

_latest = {"data": None}
_lock = threading.Lock()


def build_one(key, title, icon, fn):
    try:
        r = dict(fn())
        r["status"] = "ok"
    except Off as e:
        r = {"headline": str(e) or "Off", "lines": [str(e) or "Off"], "status": "off"}
    except Exception as e:
        print(f"Daily briefing: {key} unavailable: {type(e).__name__}: {e}", flush=True)
        r = {"headline": "Unavailable", "lines": ["Unavailable"], "status": "unavailable"}
    r.update(key=key, title=title, icon=icon)
    return r


def build():
    """All sections, now. {"updated": iso, "date": "Monday, October 19", "sections": [...]}"""
    out = [build_one(*s) for s in SECTIONS]
    n = sections_ha.now()
    return {"updated": n.isoformat(timespec="seconds"), "date": f"{n.strftime('%A')}, {n.strftime('%B')} {n.day}",
            "sections": out}


def markdown(section):
    """The text a dashboard markdown card shows: one paragraph per line."""
    return "\n\n".join(l for l in section["lines"] if l)


def notification_text(data):
    """The short phone summary: one line per section that has something to say, the day's events spelled out."""
    parts = []
    for s in data["sections"]:
        if s["status"] != "ok":
            continue
        if s["key"] == "today":
            parts.append("\n".join(l for l in s["lines"] if l))
        else:
            parts.append(f"{s['title']}: {s['headline']}")
    return "\n".join(parts)


def publish(data):
    """Writes the sensors (only the ones whose value changed). Returns how many were written."""
    written = 0
    for s in data["sections"]:
        attrs = {"friendly_name": f"Daily briefing {s['title'].lower()}", "icon": s["icon"], "status": s["status"],
                 "lines": s["lines"], "markdown": markdown(s)}
        for extra in ("events", "count"):
            if extra in s:
                attrs[extra] = s[extra]
        written += ha.publish(f"sensor.daily_briefing_{s['key']}", s["headline"], attrs)
    ok = sum(1 for s in data["sections"] if s["status"] == "ok")
    written += ha.publish("sensor.daily_briefing_summary", data["date"],
                          {"friendly_name": "Daily briefing", "icon": "mdi:television-ambient-light",
                           "sections_ok": ok, "sections_total": len(data["sections"]),
                           "markdown": "\n\n".join(f"**{s['title']}:** {s['headline']}" for s in data["sections"]
                                                   if s["status"] != "off")})
    return written


def latest():
    with _lock:
        return _latest["data"]


def refresh():
    data = build()
    with _lock:
        _latest["data"] = data
    return data


# ---------------------------------------------------------------- background loop
_sent = {"on": None}


def _morning_due(n):
    o = config.options()
    if not o["morning_notification"] or _sent["on"] == n.date():
        return False
    h, m = (int(x) for x in o["morning_time"].split(":"))
    return (n.hour, n.minute) >= (h, m)


def _tick(first):
    data = refresh()
    if ha.available():
        try:
            publish(data)
        except Exception as e:
            print(f"Daily briefing: could not publish the sensors: {e}", flush=True)
    n = sections_ha.now()
    if first and (n.hour, n.minute) >= tuple(int(x) for x in config.options()["morning_time"].split(":")):
        _sent["on"] = n.date()      # started after the morning time (an update or a restart): do not send it late
        return
    if ha.available() and _morning_due(n):
        svc = ha.notify_service()
        if not svc:
            return                  # no phone found yet: asked again on the next round
        _sent["on"] = n.date()      # claimed first, so a failing send is not repeated every minute
        try:
            ha.send_summary(svc, f"Good morning · {data['date']}", notification_text(data))
        except Exception as e:
            print(f"Daily briefing: morning summary failed: {e}", flush=True)


def start():
    def loop():
        first = True
        while True:
            try:
                _tick(first)
            except Exception as e:
                print(f"Daily briefing: refresh failed: {e}", flush=True)
            first = False
            time.sleep(config.options()["refresh_seconds"])
    threading.Thread(target=loop, daemon=True, name="briefing").start()
