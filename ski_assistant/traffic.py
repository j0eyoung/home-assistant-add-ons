"""Live traffic, from two optional sources. Both fail quietly: without them, leave times use the I-70 estimate.

Waze: Home Assistant's Waze Travel Time integration. Each Waze sensor (state = minutes, attributes route, origin,
destination) is matched to a resort by name in the sensor's name, entity id or destination, or set by hand in
Settings (waze_sensors: {resort_id: entity_id}). Read through the Supervisor, so it sees every sensor.

COtrip: CDOT's live data (incidents, road conditions, planned closures, travel times), with a free API key from
manage-api.cotrip.org in the add-on Configuration tab. The response format is parsed defensively (GeoJSON
features or plain lists) because it couldn't be checked without a key; /api/traffic/debug shows the field names
the feed actually sends so the parser can be tightened."""
import datetime as dt
import os
import re

import ha
import httpjson
import settings
import util

COTRIP = "https://data.cotrip.org/api/v1/{}?apiKey={}"
FEEDS = {"incidents": "Incident", "roadConditions": "Road condition", "plannedEvents": "Planned closure"}
TTL = 300  # 5 minutes

# Roads that matter for each resort's drive (a resort's own "roads" list in ski_resorts.json overrides these)
DEFAULT_ROADS = {
    "winter_park": ["I-70", "US 40"],
    "steamboat": ["I-70", "CO 9", "US 40", "CO 131"],
    "copper": ["I-70"],
    "eldora": ["CO 119", "CO 72", "US 36"],
    "abasin": ["I-70", "US 6"],
    "aspen_snowmass": ["I-70", "CO 82"],
    "keystone": ["I-70", "US 6"],
}


def _road_key(s):
    """'I-70', 'I 70', 'Interstate 70' -> 'i70'; 'US-40' -> 'us40'; 'CO 9'/'SH 9' -> 'co9'."""
    s = (s or "").lower()
    s = re.sub(r"interstate\s*", "i", s)
    s = re.sub(r"\b(sh|state highway|hwy|highway)\s*", "co", s)
    return re.sub(r"[^a-z0-9]", "", s)


def roads_for(r):
    return r.get("roads") or DEFAULT_ROADS.get(r["id"], ["I-70"] if r.get("i70") else [])


# Waze sensors in Home Assistant
def _waze_states():
    if not ha.available():
        return []
    try:
        states = ha._call("GET", f"{ha.CORE}/states") or []
    except Exception:
        return []
    out = []
    for s in states:
        a = s.get("attributes") or {}
        if not s.get("entity_id", "").startswith("sensor."):
            continue
        if "waze" in (a.get("attribution") or "").lower() or {"route", "origin", "destination"} <= set(a):
            out.append(s)
    return out


def _match_words(r):
    words = {r["id"].replace("_", " "), r["name"].lower()}
    words |= {w for w in r["name"].lower().split() if len(w) > 3 and w not in ("mountain", "resort", "basin")}
    if r["id"] == "abasin":
        words |= {"a-basin", "abasin", "arapahoe"}
    return words


def waze_sensors():
    """[{entity_id, name, minutes, route, destination}] for every Waze sensor Home Assistant has."""
    return [{"entity_id": s["entity_id"], "name": (s.get("attributes") or {}).get("friendly_name", s["entity_id"]),
             "minutes": _float(s.get("state")), "route": (s.get("attributes") or {}).get("route"),
             "destination": (s.get("attributes") or {}).get("destination"), "updated": s.get("last_updated")}
            for s in _waze_states()]


def waze_for(r, sensors=None):
    """Live drive minutes to this resort from its Waze sensor, or None."""
    sensors = waze_sensors() if sensors is None else sensors
    chosen = (settings.load().get("waze_sensors") or {}).get(r["id"])
    if chosen:
        match = next((s for s in sensors if s["entity_id"] == chosen), None)
    else:
        words = _match_words(r)
        match = next((s for s in sensors
                      if any(w in f"{s['entity_id']} {s['name']} {s['destination'] or ''}".lower().replace("_", " ")
                             for w in words)), None)
    if not match or match["minutes"] is None:
        return None
    return {"minutes": round(match["minutes"]), "route": match["route"], "entity_id": match["entity_id"],
            "updated": match["updated"]}


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# COtrip
def cotrip_key():
    return os.getenv("COTRIP_API_KEY", "")


def _items(data):
    """GeoJSON features (their properties) or a plain list of dicts."""
    if isinstance(data, dict):
        for k in ("features", "items", "data", "results"):
            if isinstance(data.get(k), list):
                data = data[k]
                break
    if not isinstance(data, list):
        return []
    return [(x.get("properties") if isinstance(x, dict) and isinstance(x.get("properties"), dict) else x)
            for x in data if isinstance(x, dict)]


def _first(p, *keys):
    for k in keys:
        v = p.get(k)
        if isinstance(v, (str, int, float)) and str(v).strip():
            return str(v).strip()
    return None


def _feed(name):
    return _items(httpjson.get(COTRIP.format(name, cotrip_key()), ttl=TTL, timeout=20))


# I-70 only matters between Denver and Vail Pass for these drives (Aurora, Glenwood Springs and the like don't)
ROAD_MILES = {"i70": (170, 265)}
SOON_HOURS = 24


def _road_id(s):
    """'I-70E' / 'Interstate 70' -> 'i70'; 'US-6E' -> 'us6'; 'CO-57S' / 'SH 9' -> 'co57' / 'co9'."""
    s = (s or "").lower().replace("interstate", "i").replace("state highway", "co")
    m = re.search(r"\b(i|us|co|sh)[\s-]*(\d+)", s)
    return f"{'co' if m.group(1) in ('co', 'sh') else m.group(1)}{m.group(2)}" if m else None


def _clock(t):
    """7:00AM -> '7am', 6:30PM -> '6:30pm', 12:00AM -> '12am'."""
    return f"{t.hour % 12 or 12}{'' if t.minute == 0 else f':{t.minute:02d}'}{'am' if t.hour < 12 else 'pm'}"


def _parse_when(part, now, after=None):
    """'October 20, 2026 at 7:00AM MDT' / 'Tuesday at 6:30AM MDT' / 'Tuesday, at about 7:00PM MDT' -> aware datetime."""
    tm = re.search(r"(\d{1,2}):(\d{2})\s*([AP]M)", part, re.I)
    if not tm:
        return None
    hour, minute = int(tm.group(1)) % 12, int(tm.group(2))
    if tm.group(3).upper() == "PM":
        hour += 12
    dm = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", part)
    day = None
    if dm:
        try:
            day = dt.datetime.strptime(f"{dm.group(1)} {dm.group(2)} {dm.group(3)}", "%B %d %Y").date()
        except ValueError:
            return None
    else:
        wd = next((i for i, n in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])
                   if n in part.lower()), None)
        if wd is None:
            return None
        base = (after or now).date()
        day = base + dt.timedelta(days=(wd - base.weekday()) % 7)
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=util.TZ)


def _when_text(start, end, now):
    def day(d):
        delta = (d.date() - now.date()).days
        return "today" if delta == 0 else "tomorrow" if delta == 1 else d.strftime("%a %b ") + str(d.day)
    if start.date() == end.date():
        return f"{day(start)} {_clock(start)}-{_clock(end)}"
    return f"{day(start)} {_clock(start)} to {day(end)} {_clock(end)}"


def _summarize(kind, road, direction, text, now):
    """One short, structured line from a CDOT notice. Returns None if the notice is for the wrong stretch."""
    rid = _road_id(road) or _road_id(text)
    miles = [float(x) for x in re.findall(r"Mile Point (\d+(?:\.\d+)?)", text)]
    if rid in ROAD_MILES and miles and not (min(miles) <= ROAD_MILES[rid][1] and max(miles) >= ROAD_MILES[rid][0]):
        return None
    start = end = None
    sm = re.search(r"Starting (.+?) until (.+?)\.(?:\s|$)", text)
    if sm:
        start = _parse_when(sm.group(1), now)
        end = _parse_when(sm.group(2), now, after=start) if start else None
    where = what = ""
    lm = re.match(r"\s*Between (.+?) from Mile Point", text)
    if lm:
        where = re.sub(r"\s*\([^)]*\)", "", lm.group(1))
        where = re.sub(r"(Exit \d+): ", r"\1 ", where).replace(" and ", " to ", 1)
        rest = re.split(r"Mile Point [\d.]+\.\s*", text.split(" from Mile Point", 1)[1], maxsplit=1)
        body = rest[1] if len(rest) > 1 else ""
        body = re.split(r"\bStarting\b|Full schedule", body)[0].strip()
        what = " ".join(re.split(r"(?<=\.)\s+", body)[:2]).rstrip(".")
    else:
        what = re.split(r"\bStarting\b|Full schedule", text)[0].strip().rstrip(".")
    what = re.sub(r"\s+due to\s+", " (", what) + (")" if " due to " in what else "") if what else what
    if start and end:
        status = "now" if start <= now <= end else "soon" if 0 <= (start - now).total_seconds() <= SOON_HOURS * 3600 else \
            ("gone" if end < now else "later")
        when = _when_text(start, end, now)
    else:
        status, when = "now", "now"
    if status == "gone":
        return None
    return {"kind": kind, "road": re.sub(r"(\d)[EWNS]\b", r"\1", (road or "").strip()),  # 'I-70W' -> 'I-70'
            "direction": (direction or "").strip(), "where": where,
            "what": what[:110], "when": when, "status": status}


def _merge(items):
    """The same closure on several days becomes one line with several times."""
    merged = {}
    for a in items:
        k = (a["kind"], a["road"], a["direction"], a["where"], a["what"])
        if k in merged:
            m = merged[k]
            m["whens"].append(a["when"])
            if ["now", "soon", "later"].index(a["status"]) < ["now", "soon", "later"].index(m["status"]):
                m["status"] = a["status"]
        else:
            merged[k] = dict(a, whens=[a["when"]])
    out = []
    for m in merged.values():
        whens = m.pop("whens")
        m["when"] = "; ".join(whens[:3]) + (f" (+{len(whens) - 3} more)" if len(whens) > 3 else "")
        out.append(m)
    return sorted(out, key=lambda x: ["now", "soon", "later"].index(x["status"]))


def alerts(roads=None):
    """Incidents, road conditions and planned closures on the given roads (all roads if None), one short line each,
    active now first, then starting within 24 hours, then later.
    {"configured", "alerts": [{kind, road, direction, where, what, when, status}], "error"}"""
    if not cotrip_key():
        return {"configured": False, "alerts": [], "error": None}
    want = {_road_id(x) for x in roads} - {None} if roads else None
    now = util.now()
    found, errors = [], []
    for feed, kind in FEEDS.items():
        try:
            items = _feed(feed)
        except Exception as e:
            errors.append(f"{feed}: {type(e).__name__}")
            continue
        for p in items:
            road = _first(p, "routeName", "roadName", "primaryRoute", "route", "road", "highway", "name")
            text = _first(p, "travelerInformationMessage", "headline", "description", "eventDescription", "message",
                          "title", "summary", "type")
            if not text:
                continue
            # Road conditions are only worth showing when they're not plain "dry"
            if feed == "roadConditions" and re.fullmatch(r"(dry|good|normal)\.?", text.lower()):
                continue
            # Match on the notice's own road, not on roads it merely mentions ("...Colorado Avenue and I-70")
            if want and _road_id(road) not in want:
                continue
            try:
                a = _summarize(kind, road, _first(p, "direction", "travelDirection"), text, now)
            except Exception:
                a = {"kind": kind, "road": road or "", "direction": "", "where": "", "what": text[:110],
                     "when": "now", "status": "now"}
            if a:
                found.append(a)
    return {"configured": True, "alerts": _merge(found)[:40], "error": "; ".join(errors) or None}


def travel_times():
    """COtrip's published travel times ('destinations'), e.g. Denver to Silverthorne on I-70."""
    if not cotrip_key():
        return []
    try:
        items = _feed("destinations")
    except Exception:
        return []
    out = []
    for p in items:
        name = _first(p, "name", "displayName", "description", "destinationName")
        now = _first(p, "travelTime", "currentTravelTime", "travelTimeMinutes", "minutes", "duration")
        usual = _first(p, "freeFlowTravelTime", "typicalTravelTime", "averageTravelTime", "historicalTravelTime")
        if name and now:
            out.append({"name": name, "minutes": _float(now), "usual_minutes": _float(usual)})
    return out


def debug():
    """Field names (not values) of the first item in each COtrip feed, to tune the parser to the real format."""
    if not cotrip_key():
        return {"configured": False}
    out = {"configured": True}
    for feed in list(FEEDS) + ["destinations"]:
        try:
            items = _feed(feed)
            out[feed] = {"count": len(items), "fields": sorted(items[0].keys()) if items else []}
        except Exception as e:
            out[feed] = {"error": type(e).__name__}
    return out


def for_resort(r, sensors=None):
    """Everything live for one resort's drive: Waze minutes now and COtrip alerts on its roads."""
    roads = roads_for(r)
    return {"waze": waze_for(r, sensors), "roads": roads, "cotrip": alerts(roads)}
