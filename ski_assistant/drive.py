"""Drive time and leave-by. Base time from the public OSRM router (no live traffic, cached a day); I-70 traffic
is a day-and-time heuristic. CDOT live traffic is not wired in yet."""
import datetime as dt
import httpjson

OSRM = "https://router.project-osrm.org/route/v1/driving/{},{};{},{}?overview=false"


def base_minutes(dep, r):
    """Typical drive minutes from a departure point, or the resort's stored drive_min if routing fails."""
    try:
        url = OSRM.format(dep["lon"], dep["lat"], r["lon"], r["lat"])
        return round(httpjson.get(url, ttl=86400)["routes"][0]["duration"] / 60)
    except Exception:
        return r.get("drive_min", 120)


def factor(r, weekday, hour, outbound=True):
    """I-70 traffic multiplier. weekday 0=Mon. Outbound = toward the mountain, else heading home."""
    if not r.get("i70"):
        return 1.0
    if outbound:
        if weekday in (5, 6):
            return 1.8 if 7 <= hour < 9 else 1.5 if 6 <= hour < 10 else 1.0
        if weekday == 4:
            return 1.5 if 15 <= hour < 19 else 1.0
    else:
        if weekday == 6:
            return 2.2 if 15 <= hour < 19 else 1.6 if 13 <= hour < 21 else 1.0
        if weekday == 5:
            return 1.4 if 15 <= hour < 18 else 1.0
    return 1.0


def plan(r, dep, date, arrive_by, buffer_min):
    """Leave time to be at the lifts by `arrive_by` ("HH:MM") on `date` (ISO), plus when to head home."""
    d = dt.date.fromisoformat(date)
    base = base_minutes(dep, r)
    ah, am = map(int, arrive_by.split(":"))
    arrive = dt.datetime.combine(d, dt.time(ah, am))
    f, depart = 1.0, arrive
    for _ in range(3):  # traffic depends on when you leave, which depends on traffic
        depart = arrive - dt.timedelta(minutes=base * f + buffer_min)
        f = factor(r, d.weekday(), depart.hour)
    out = {"leave_at": depart.strftime("%H:%M"), "base_min": base, "drive_min": round(base * f),
           "traffic_factor": f}
    if r.get("i70") and d.weekday() in (5, 6):
        out["home_advice"] = "Leave the mountain before 2:00pm or after 7:00pm to miss eastbound I-70 traffic."
    return out
