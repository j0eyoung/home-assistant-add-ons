"""Briefing sections that come straight from Home Assistant: Today (date, weather, sun, calendar) and Shopping.

Every builder returns {"headline": str, "lines": [str, ...]} and may raise; sections.py turns a failure into
"Unavailable" so one broken source never blanks the screen."""
import datetime
import zoneinfo

import config
import ha

_tz = {"value": None, "at": 0.0}
SKIP_CALENDARS = ("holiday", "birthday")      # noisy for a "today" screen; add them under Calendars to include them


def tzinfo():
    """The Home Assistant time zone (cached for an hour), else the container's."""
    import time
    if _tz["value"] is None or time.time() - _tz["at"] > 3600:
        try:
            name = (ha._call("GET", f"{ha.CORE}/config") or {}).get("time_zone")
            _tz.update(value=zoneinfo.ZoneInfo(name) if name else None, at=time.time())
        except Exception:
            _tz["at"] = time.time()
    return _tz["value"] or datetime.datetime.now().astimezone().tzinfo


def now():
    return datetime.datetime.now(tzinfo())


def clock(dt):
    """9:30 AM (no leading zero, no platform-specific strftime flags)."""
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


_CONDITIONS = {
    "clear-night": "Clear", "cloudy": "Cloudy", "exceptional": "Exceptional", "fog": "Foggy", "hail": "Hail",
    "lightning": "Thunderstorms", "lightning-rainy": "Thunderstorms and rain", "partlycloudy": "Partly cloudy",
    "pouring": "Pouring rain", "rainy": "Rain", "snowy": "Snow", "snowy-rainy": "Sleet", "sunny": "Sunny",
    "windy": "Windy", "windy-variant": "Windy and cloudy",
}


def _weather_entity():
    wanted = config.options()["weather_entity"]
    if wanted:
        return wanted
    found = ha.entities("weather")
    return next((e for e in found if e == "weather.home"), found[0] if found else "")


def weather_line(today):
    ent = _weather_entity()
    st = ha.state(ent) if ent else None
    if not st or st.get("state") in ("unavailable", "unknown"):
        return None
    a = st.get("attributes") or {}
    unit = a.get("temperature_unit") or "°"
    cond = _CONDITIONS.get(st["state"], str(st["state"]).replace("-", " ").capitalize())
    bits = [cond]
    if a.get("temperature") is not None:
        bits.append(f"{round(float(a['temperature']))}{unit}")
    try:
        fc = ha.service_response("weather", "get_forecasts", {"entity_id": ent, "type": "daily"})
        day = ((fc.get(ent) or {}).get("forecast") or [None])[0]
        if day and day.get("temperature") is not None:
            hi, lo = round(float(day["temperature"])), day.get("templow")
            bits.append(f"high {hi}{unit}" + (f", low {round(float(lo))}{unit}" if lo is not None else ""))
        if day and day.get("precipitation_probability") not in (None, 0):
            bits.append(f"{day['precipitation_probability']}% chance of rain")
    except Exception:
        pass            # the current conditions are still worth showing
    return ", ".join(bits)


def sun_line():
    st = ha.state("sun.sun")
    if not st:
        return None
    a = st.get("attributes") or {}
    tz = tzinfo()
    out = []
    for label, key in (("Sunrise", "next_rising"), ("Sunset", "next_setting")):
        try:
            out.append(f"{label} {clock(datetime.datetime.fromisoformat(a[key]).astimezone(tz))}")
        except (KeyError, ValueError, TypeError):
            pass
    return " · ".join(out) or None


def _calendar_ids():
    chosen = config.options()["calendars"]
    if chosen:
        return chosen
    return [c for c in ha.entities("calendar") if not any(w in c for w in SKIP_CALENDARS)]


def calendar_lines(today):
    """Today's events across the chosen calendars: all-day first, then by start time. Returns (lines, errors)."""
    tz = tzinfo()
    start = datetime.datetime.combine(today, datetime.time.min, tz)
    end = start + datetime.timedelta(days=1)
    events, errors = [], 0
    for cal in _calendar_ids():
        try:
            for e in ha.calendar_events(cal, start, end):
                events.append(e)
        except Exception:
            errors += 1
    rows, seen = [], set()
    for e in events:
        s = e.get("start") or {}
        title = str(e.get("summary") or "(no title)")
        if "date" in s and "dateTime" not in s:
            if not (datetime.date.fromisoformat(s["date"]) <= today < datetime.date.fromisoformat((e.get("end") or {}).get("date", "9999-12-31"))):
                continue
            key, label, order = (title, "all day"), "All day", datetime.datetime.combine(today, datetime.time.min, tz)
        else:
            try:
                dt = datetime.datetime.fromisoformat(s["dateTime"]).astimezone(tz)
            except (KeyError, ValueError):
                continue
            if dt.date() != today:
                continue
            key, label, order = (title, dt), clock(dt), dt
        if key in seen:                       # the same event on two calendars
            continue
        seen.add(key)
        rows.append((order, label != "All day", title if label == "All day" else f"{label}  {title}"))
    rows.sort(key=lambda r: (r[1], r[0]))
    return [r[2] for r in rows], errors


def today_section():
    n = now()
    today = n.date()
    lines = [f"{n.strftime('%A')}, {n.strftime('%B')} {today.day}"]
    notes = []
    for fn in (lambda: weather_line(today), sun_line):
        try:
            text = fn()
        except Exception:
            text = None
        if text:
            lines.append(text)
    events, errors = calendar_lines(today)
    if events:
        lines.append("")
        lines += events
    elif errors:
        notes.append("calendar unavailable")
    else:
        lines += ["", "Nothing on the calendar"]
    return {"headline": f"{n.strftime('%a')} {n.strftime('%b')} {today.day}", "lines": lines + notes,
            "events": len(events)}


def shopping_section():
    ent = config.options()["shopping_list"]
    items = [str(i.get("summary")) for i in
             (ha.service_response("todo", "get_items", {"entity_id": ent, "status": "needs_action"}).get(ent) or {}).get("items", [])
             if i.get("summary")]
    if not items:
        return {"headline": "Nothing to buy", "lines": ["Shopping list is empty"], "count": 0}
    top = items[:8]
    more = f"+ {len(items) - len(top)} more" if len(items) > len(top) else ""
    return {"headline": f"{len(items)} item{'s' if len(items) != 1 else ''}", "lines": top + ([more] if more else []),
            "count": len(items)}
