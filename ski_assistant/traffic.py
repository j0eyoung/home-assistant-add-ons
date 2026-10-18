"""Live traffic, from two optional sources. Both fail quietly: without them, leave times use the I-70 estimate.

Waze: Home Assistant's Waze Travel Time integration. Each Waze sensor (state = minutes, attributes route, origin,
destination) is matched to a resort by name in the sensor's name, entity id or destination, or set by hand in
Settings (waze_sensors: {resort_id: entity_id}). Read through the Supervisor, so it sees every sensor.

COtrip: CDOT's live data (incidents, road conditions, planned closures, travel times), with a free API key from
manage-api.cotrip.org in the add-on Configuration tab. The response format is parsed defensively (GeoJSON
features or plain lists) because it couldn't be checked without a key; /api/traffic/debug shows the field names
the feed actually sends so the parser can be tightened."""
import os
import re

import ha
import httpjson
import settings

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


def alerts(roads=None):
    """Current incidents, road conditions and planned closures on the given roads (all roads if None).
    {"configured", "alerts": [{kind, road, text, direction, start}], "error"}"""
    if not cotrip_key():
        return {"configured": False, "alerts": [], "error": None}
    want = {_road_key(x) for x in roads} if roads else None
    out, errors = [], []
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
            blob = _road_key(f"{road or ''} {text}")
            if want and not any(w in blob for w in want):
                continue
            out.append({"kind": kind, "road": road, "text": text[:300],
                        "direction": _first(p, "direction", "travelDirection"),
                        "start": _first(p, "startTime", "start", "reportedTime", "lastUpdated")})
    return {"configured": True, "alerts": out[:40], "error": "; ".join(errors) or None}


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
