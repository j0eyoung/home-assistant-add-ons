"""Drive time and leave-by, built to beat I-70 traffic.

Base time comes from the public OSRM router (free-flow, no live traffic, cached a day). The same route says
whether you use I-70 and how long it takes to get onto it. On peak days (weekends and ski holidays) a traffic
curve is applied to the I-70 part based on when you reach it, and the leave time is the earlier of
"arrive by" and "be on I-70 before the rush". Powder days start the rush 30 minutes earlier and make it worse.
The curves are estimates of typical CDOT patterns, not live data."""
import datetime as dt

import httpjson

OSRM = "https://router.project-osrm.org/route/v1/driving/{},{};{},{}?overview=false&steps=true"

# Latest time to be on I-70 (westbound) on a peak day to stay ahead of the rush
ON_I70_BY = dt.time(6, 0)
POWDER_SHIFT = dt.timedelta(minutes=30)
# Traffic only applies to the congested stretch (C-470 to the Eisenhower Tunnel / Silverthorne, about 70 min);
# the rest of a long drive (e.g. on to Steamboat) runs at normal speed
CORRIDOR_MIN = 70

# (from, to, multiplier) for the I-70 part of the drive, by the time you get on I-70
WEST_PEAK = [((5, 30), (6, 0), 1.05), ((6, 0), (6, 30), 1.15), ((6, 30), (7, 0), 1.5), ((7, 0), (9, 0), 2.0),
             ((9, 0), (10, 30), 1.6), ((10, 30), (12, 0), 1.25)]
# Heading home, by the time you leave the resort. "last" = the last day of a weekend or holiday run.
EAST_LAST = [((11, 30), (12, 30), 1.3), ((12, 30), (18, 30), 2.0), ((18, 30), (19, 30), 1.3)]
EAST_MID = [((13, 30), (14, 30), 1.2), ((14, 30), (18, 0), 1.6), ((18, 0), (19, 0), 1.2)]


def _nth_weekday(year, month, weekday, n):
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def holiday(d):
    """Ski-traffic holidays: Thanksgiving Thu-Sun, Dec 20 - Jan 3, MLK Day, Presidents Day."""
    thanks = _nth_weekday(d.year, 11, 3, 4)
    if thanks <= d <= thanks + dt.timedelta(days=3):
        return True
    if (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 3):
        return True
    return d in (_nth_weekday(d.year, 1, 0, 3), _nth_weekday(d.year, 2, 0, 3))


def is_peak(d):
    return d.weekday() >= 5 or holiday(d)


def _curve(curve, t):
    hm = (t.hour, t.minute)
    return next((f for start, end, f in curve if start <= hm < end), 1.0)


def route(dep, r):
    """{"base_min", "to_i70_min"} from a departure point to a resort. to_i70_min is None when the route
    doesn't use I-70. Falls back to the resort's stored drive_min if routing fails."""
    try:
        data = httpjson.get(OSRM.format(dep["lon"], dep["lat"], r["lon"], r["lat"]), ttl=86400)
        steps = data["routes"][0]["legs"][0]["steps"]
        elapsed, to_i70 = 0.0, None
        for s in steps:
            if "I 70" in (s.get("ref") or "").split("; ") and not (s.get("ref") or "").startswith("I 70 BUS"):
                to_i70 = elapsed
                break
            elapsed += s["duration"]
        return {"base_min": round(data["routes"][0]["duration"] / 60),
                "to_i70_min": round(to_i70 / 60) if to_i70 is not None else None}
    except Exception:
        return {"base_min": r.get("drive_min", 120), "to_i70_min": 30 if r.get("i70") else None}


def _drive(rt, d, leave, powder):
    """Drive minutes when leaving at `leave` (datetime) on date `d`."""
    if rt["to_i70_min"] is None or not is_peak(d):
        return rt["base_min"]
    on_i70 = leave + dt.timedelta(minutes=rt["to_i70_min"])
    f = _curve(WEST_PEAK, on_i70 + (POWDER_SHIFT if powder else dt.timedelta()))
    if powder and f > 1:
        f = 1 + (f - 1) * 1.3
    return _with_factor(rt, f)


def _with_factor(rt, f):
    rest = rt["base_min"] - (rt["to_i70_min"] or 0)
    jam = min(rest, CORRIDOR_MIN)
    return round(rt["base_min"] + jam * (f - 1))


def plan(r, dep, date, arrive_by, buffer_min, powder=False):
    """When to leave `dep` for resort `r` on `date` (ISO), and when to head home."""
    d = dt.date.fromisoformat(date)
    rt = route(dep, r)
    ah, am = map(int, arrive_by.split(":"))
    target = dt.datetime.combine(d, dt.time(ah, am)) - dt.timedelta(minutes=buffer_min)

    # Latest departure that still gets you to the lot by the target time, with traffic for that departure
    leave = target - dt.timedelta(minutes=rt["base_min"])
    for _ in range(30):
        if leave + dt.timedelta(minutes=_drive(rt, d, leave, powder)) <= target:
            break
        leave -= dt.timedelta(minutes=10)
    reason = "arrive"

    uses_i70 = rt["to_i70_min"] is not None
    if uses_i70 and is_peak(d):
        cutoff = dt.datetime.combine(d, ON_I70_BY) - (POWDER_SHIFT if powder else dt.timedelta())
        beat = cutoff - dt.timedelta(minutes=rt["to_i70_min"])
        if beat < leave:
            leave, reason = beat, "traffic"
    drive = _drive(rt, d, leave, powder)
    out = {"leave_at": leave.strftime("%H:%M"), "arrive_at": (leave + dt.timedelta(minutes=drive)).strftime("%H:%M"),
           "drive_min": drive, "base_min": rt["base_min"], "uses_i70": uses_i70, "peak_day": is_peak(d),
           "powder": powder, "reason": reason}
    if reason == "traffic":
        out["on_i70_by"] = (leave + dt.timedelta(minutes=rt["to_i70_min"])).strftime("%H:%M")
        seven = dt.datetime.combine(d, dt.time(7, 0))  # what a typical "leave at 7" costs, for comparison
        out["if_later"] = {"leave_at": "07:00", "drive_min": _drive(rt, d, seven, powder)}
    if uses_i70 and is_peak(d):
        out["home"] = home_advice(rt, d)
    return out


def home_advice(rt, d):
    """Best windows to leave the resort, with the drive time at 3pm for comparison."""
    last = not is_peak(d + dt.timedelta(days=1))
    curve = EAST_LAST if last else EAST_MID
    before, after = curve[0][0], curve[-1][1]
    at3 = _with_factor(rt, _curve(curve, dt.time(15, 0)))
    return {"leave_before": dt.time(*before).strftime("%H:%M"), "or_after": dt.time(*after).strftime("%H:%M"),
            "drive_min_at_3pm": at3, "base_min": rt["base_min"]}
