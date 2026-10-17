"""Optional live lift/terrain status. Unofficial public feeds that resort sites use themselves, so every
call fails quietly (returns None) and the ranking works without it.

Feed types, set per resort in its "live" entry:
  powdr      {"type": "powdr", "url": ".../lifts"}   lifts only (Copper, Eldora)
  mtnpowder  {"type": "mtnpowder", "name": "..."}    lifts, trails and terrain (Winter Park, Arapahoe Basin)
Keystone (Vail) is behind a bot wall, so it has no entry."""
import httpjson

MTNPOWDER = "https://mtnpowder.com/feed"
TTL = 900  # 15 minutes

DEFAULT_LIVE = {
    "copper": {"type": "powdr", "url": "https://api.coppercolorado.com/api/v1/dor/drupal/lifts"},
    "eldora": {"type": "powdr", "url": "https://api.eldora.com/api/v1/dor/drupal/lifts"},
    "winter_park": {"type": "mtnpowder", "name": "Winter Park"},
    "abasin": {"type": "mtnpowder", "name": "Arapahoe Basin"},
}


def _powdr(cfg):
    lifts = [x for x in httpjson.get(cfg["url"], ttl=TTL) if x.get("season") in ("winter", "all")]
    return {"lifts_open": sum(1 for x in lifts if x.get("status") == "open"), "lifts_total": len(lifts),
            "trails_open": None, "trails_total": None, "terrain_open_pct": None, "as_of": None}


def _mtnpowder(cfg):
    for r in httpjson.get(MTNPOWDER, ttl=TTL, timeout=40)["Resorts"]:
        if r["Name"] == cfg["name"]:
            s = r.get("SnowReport") or {}
            acres, total = _num(s.get("OpenTerrainAcres")), _num(s.get("TotalTerrainAcres"))
            return {"lifts_open": s.get("TotalOpenLifts"), "lifts_total": s.get("TotalLifts"),
                    "trails_open": s.get("TotalOpenTrails"), "trails_total": s.get("TotalTrails"),
                    "terrain_open_pct": round(100 * acres / total) if total else None,
                    "season_in": _num(s.get("SeasonTotalIn")), "as_of": s.get("LastUpdate")}
    return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def beginner_pct(r):
    """Percent of trails rated green or blue, when the resort's feed lists trails; else the resort's own
    `beginner_pct` if the user set one, else None."""
    cfg = r.get("live") or DEFAULT_LIVE.get(r["id"])
    if cfg and cfg["type"] == "mtnpowder":
        try:
            for res in httpjson.get(MTNPOWDER, ttl=TTL, timeout=40)["Resorts"]:
                if res["Name"] == cfg["name"]:
                    trails = [t for a in res.get("MountainAreas", []) for t in a.get("Trails", [])]
                    easy = sum(1 for t in trails if t.get("TrailIcon") in ("GreenCircle", "BlueSquare"))
                    if trails:
                        return round(100 * easy / len(trails))
        except Exception:
            pass
    return r.get("beginner_pct")


_TYPES = {"powdr": _powdr, "mtnpowder": _mtnpowder}


def live_status(r):
    """Live status dict for a resort, or None when there is no feed or it failed."""
    cfg = r.get("live") or DEFAULT_LIVE.get(r["id"])
    fn = _TYPES.get(cfg["type"]) if cfg else None
    if not fn:
        return None
    try:
        return fn(cfg)
    except Exception:
        return None
