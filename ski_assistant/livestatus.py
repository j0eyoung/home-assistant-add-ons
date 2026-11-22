"""Optional live lift/terrain status. Unofficial public feeds that resort sites use themselves, so every
call fails quietly (returns None) and the ranking works without it.

Feed types, set per resort in its "live" entry:
  powdr      {"type": "powdr", "url": ".../lifts"}   lifts only (Copper, Eldora)
  mtnpowder  {"type": "mtnpowder", "name": "..."}    lifts, trails and terrain (Winter Park, Arapahoe Basin)
Keystone (Vail) is behind a bot wall, so it has no entry."""
import httpjson
import util

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
            # The resort's reported snow: use whichever area (mid-mountain, summit, base) has numbers
            areas = [s.get(k) or {} for k in ("MidMountainArea", "SummitArea", "BaseArea")]
            area = next((a for a in areas if _num(a.get("BaseIn")) is not None or _num(a.get("Last24HoursIn")) is not None), {})
            return {"lifts_open": s.get("TotalOpenLifts"), "lifts_total": s.get("TotalLifts"),
                    "trails_open": s.get("TotalOpenTrails"), "trails_total": s.get("TotalTrails"),
                    "terrain_open_pct": round(100 * acres / total) if total else None,
                    "status": r.get("OperatingStatus"), "conditions": _text(s.get("BaseConditions")),
                    "base_in": _num(area.get("BaseIn")) or _num(s.get("SnowBaseRangeIn")),
                    "new_24h_in": _num(area.get("Last24HoursIn")), "new_48h_in": _num(area.get("Last48HoursIn")),
                    "new_72h_in": _num(area.get("Last72HoursIn")), "new_7d_in": _num(area.get("Last7DaysIn")),
                    "storm_in": _num(s.get("StormTotalIn")), "season_in": _num(s.get("SeasonTotalIn")),
                    "as_of": s.get("LastUpdate")}
    return None


def _text(v):
    return None if v in (None, "", "--") else v


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


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


_seen = {}  # resort id -> (date, "open" | "not_open"): the last daytime verdict


def season_state(r, live=None):
    """"open", "not_open" (not open for the season yet, or closed for it), or None when it can't be told.
    Lift counts only mean something while lifts would be running, so a verdict is taken between 10am and 3pm and
    remembered through the evening and the next day; a status that mentions the season or opening counts at any hour."""
    live = live if live is not None else live_status(r)
    if not live:
        return _remembered(r)
    status = (live.get("status") or "").strip().lower()
    if "season" in status or "opening" in status or "coming soon" in status:
        verdict = "not_open"   # "Opening Soon", "Closed for the Season"
    elif status.startswith("open"):
        verdict = "open"
    elif 10 <= util.now().hour < 15 and live.get("lifts_total"):
        verdict = "open" if (live.get("lifts_open") or 0) > 0 or (live.get("terrain_open_pct") or 0) > 0 else "not_open"
    else:
        return _remembered(r)
    _seen[r["id"]] = (util.today(), verdict)
    return verdict


def _remembered(r):
    hit = _seen.get(r["id"])
    return hit[1] if hit and (util.today() - hit[0]).days <= 1 else None
