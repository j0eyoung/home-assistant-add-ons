"""Optional live lift/terrain status. Unofficial public feeds that resort sites use themselves, so every
call fails quietly (returns None) and the ranking works without it.

Feed types, set per resort in its "live" entry:
  powdr      {"type": "powdr", "url": ".../lifts"}           lifts and trails by name (Copper, Eldora)
  mtnpowder  {"type": "mtnpowder", "name": "..."}            lifts and trails by name, snow, terrain
                                                             (Winter Park, Arapahoe Basin, Steamboat)
  aspen      {"type": "aspen", "mountains": ["Snowmass"...]} Aspen Skiing Co's own feeds, all four mountains
  onthesnow  {"type": "onthesnow", "path": "colorado/x"}     lift and run counts only, no names (Keystone: Vail's
                                                             own status page is behind a bot wall)

Besides the counts, "lifts" and "trails" list every lift and trail with a status (open, hold, scheduled, closed),
trails with a level (green, blue, black, double, park). They're None when the feed doesn't name them.
summary() drops the two lists for places that only need the counts."""
import html
import re
from concurrent.futures import ThreadPoolExecutor

import httpjson
import util

MTNPOWDER = "https://mtnpowder.com/feed"
ASPEN = "https://www.aspensnowmass.com/AspenSnowmass/{feed}/Feed?mountain={m}"
ONTHESNOW = "https://www.onthesnow.com/{path}/skireport"
TTL = 900  # 15 minutes

DEFAULT_LIVE = {
    "copper": {"type": "powdr", "url": "https://api.coppercolorado.com/api/v1/dor/drupal/lifts"},
    "eldora": {"type": "powdr", "url": "https://api.eldora.com/api/v1/dor/drupal/lifts"},
    "winter_park": {"type": "mtnpowder", "name": "Winter Park"},
    "abasin": {"type": "mtnpowder", "name": "Arapahoe Basin"},
    "steamboat": {"type": "mtnpowder", "name": "Steamboat"},
    # The resort sits at Snowmass, so Snowmass comes first and gives the snow numbers
    "aspen_snowmass": {"type": "aspen", "mountains": ["Snowmass", "AspenMountain", "AspenHighlands", "Buttermilk"]},
    "keystone": {"type": "onthesnow", "path": "colorado/keystone"},
}
ASPEN_NAMES = {"Snowmass": "Snowmass", "AspenMountain": "Aspen Mountain", "AspenHighlands": "Aspen Highlands",
               "Buttermilk": "Buttermilk"}


def _status(v):
    """A feed's lift or trail status as open, hold, scheduled or closed."""
    s = str(v or "").strip().lower()
    if s.startswith("open") or s in ("1", "true"):
        return "open"
    if "hold" in s:
        return "hold"
    if "sched" in s or "expect" in s or "anticipat" in s:
        return "scheduled"
    return "closed"


def level(v):
    """A difficulty as green, blue, black, double or park (None when unknown). Feeds and OpenStreetMap use many
    words: easiest/beginner/novice, more_difficult/intermediate, most_difficult/advanced/very difficult, expert/extreme."""
    s = str(v or "").strip().lower().replace("_", " ").replace("-", " ")
    if not s or s in ("n/a", "na", "none"):
        return None
    if "park" in s:
        return "park"
    if any(w in s for w in ("easi", "easy", "beginn", "novice", "green")):
        return "green"
    if "more difficult" in s or "intermediate" in s or "blue" in s:
        return "blue"
    if any(w in s for w in ("expert", "extreme", "double", "freeride")):
        return "double"
    if any(w in s for w in ("advanced", "difficult", "black")):
        return "black"
    return None


def _item(name, status, lvl=None, area=None, groomed=None):
    out = {"name": " ".join(str(name).split()), "status": status, "area": area}
    if lvl is not None or groomed is not None:
        out |= {"level": lvl, "groomed": groomed}
    return out


def _count(items):
    return sum(1 for x in items if x["status"] == "open")


def _powdr(cfg):
    winter = ("winter", "all")
    lifts = [x for x in httpjson.get(cfg["url"], ttl=TTL) if x.get("season") in winter]
    lift_items = [_item(x.get("name"), _status(x.get("status")), area=(x.get("sector") or {}).get("name")) for x in lifts]
    trail_items = None
    try:
        trails = [x for x in httpjson.get(re.sub(r"/lifts/?$", "/trails", cfg["url"]), ttl=TTL)
                  if x.get("season") in winter and x.get("include", True)
                  and x.get("type") in ("alpine_trail", "terrain_park_trail")]
        trail_items = [_item(x.get("name"), _status(x.get("status")),
                             "park" if x.get("type") == "terrain_park_trail" else level(x.get("difficulty")),
                             (x.get("sector") or {}).get("name"), x.get("groom_status") == "groomed") for x in trails]
    except Exception:
        pass
    return {"lifts_open": _count(lift_items), "lifts_total": len(lift_items),
            "trails_open": _count(trail_items) if trail_items is not None else None,
            "trails_total": len(trail_items) if trail_items is not None else None,
            "terrain_open_pct": None, "as_of": None, "lifts": lift_items, "trails": trail_items}


def _mtnpowder(cfg):
    for r in httpjson.get(MTNPOWDER, ttl=TTL, timeout=40)["Resorts"]:
        if r["Name"] == cfg["name"]:
            s = r.get("SnowReport") or {}
            acres, total = _num(s.get("OpenTerrainAcres")), _num(s.get("TotalTerrainAcres"))
            # The resort's reported snow: use whichever area (mid-mountain, summit, base) has numbers
            areas = [s.get(k) or {} for k in ("MidMountainArea", "SummitArea", "BaseArea")]
            area = next((a for a in areas if _num(a.get("BaseIn")) is not None or _num(a.get("Last24HoursIn")) is not None), {})
            lifts, trails = [], []
            for a in r.get("MountainAreas") or []:
                where = a.get("Name")
                lifts += [_item(x.get("Name"), _status(x.get("StatusEnglish") or x.get("Status")), area=where)
                          for x in a.get("Lifts") or [] if x.get("Name")]
                trails += [_item(x.get("Name"), _status(x.get("StatusEnglish") or x.get("Status")),
                                 "park" if _yes(x.get("TerrainParkOnRun")) else level(x.get("Difficulty")), where,
                                 _yes(x.get("Grooming")))
                           for x in a.get("Trails") or []
                           if x.get("Name") and not _yes(x.get("Nordic"))
                           and "snowshoe" not in str(x.get("Difficulty")).lower()]
            return {"lifts_open": s.get("TotalOpenLifts"), "lifts_total": s.get("TotalLifts"),
                    "trails_open": s.get("TotalOpenTrails"), "trails_total": s.get("TotalTrails"),
                    "terrain_open_pct": round(100 * acres / total) if total and acres is not None else None,
                    "status": r.get("OperatingStatus"), "conditions": _text(s.get("BaseConditions")),
                    "base_in": _num(area.get("BaseIn")) or _num(s.get("SnowBaseRangeIn")),
                    "new_24h_in": _num(area.get("Last24HoursIn")), "new_48h_in": _num(area.get("Last48HoursIn")),
                    "new_72h_in": _num(area.get("Last72HoursIn")), "new_7d_in": _num(area.get("Last7DaysIn")),
                    "storm_in": _num(s.get("StormTotalIn")), "season_in": _num(s.get("SeasonTotalIn")),
                    "as_of": s.get("LastUpdate"), "lifts": lifts or None, "trails": trails or None}
    return None


def _yes(v):
    """MtnPowder's flags are "Yes" / "No" strings."""
    return v is True or str(v or "").strip().lower() in ("yes", "y", "true", "1")


def _aspen_one(m):
    """One Aspen Snowmass mountain: its snow report plus lift and trail names (each part may fail on its own)."""
    name = ASPEN_NAMES.get(m, m)
    rep = httpjson.get(ASPEN.format(feed="SnowReport", m=m), ttl=TTL)
    lifts = trails = None
    try:
        lifts = [_item(x.get("liftName"), _status(x.get("status")), area=name)
                 for x in httpjson.get(ASPEN.format(feed="LiftStatus", m=m), ttl=TTL).get("liftStatuses") or []]
    except Exception:
        pass
    try:
        trails = [_item(t.get("name"), "open" if t.get("isOpen") else "closed", level(t.get("difficulty")), name,
                        bool(t.get("isGroomed")))
                  for a in httpjson.get(ASPEN.format(feed="GroomingReport", m=m), ttl=TTL).get("areas") or []
                  for t in a.get("trails") or [] if t.get("name") and "uphill" not in str(a.get("name")).lower()]
    except Exception:
        pass
    return name, rep, lifts, trails


def _aspen(cfg):
    with ThreadPoolExecutor(max_workers=4) as pool:
        parts = list(pool.map(_try(_aspen_one), cfg["mountains"]))
    parts = [p for p in parts if p]
    if not parts:
        return None
    n = lambda rep, k, f: (rep.get(k) or {}).get(f) or 0
    first = parts[0][1]
    snow = lambda k: _num((first.get(k) or {}).get("inches"))
    statuses = [str(rep.get("status") or "") for _, rep, _, _ in parts]
    lifts = [x for p in parts for x in (p[2] or [])]
    trails = [x for p in parts for x in (p[3] or [])]
    acres, total = sum(n(r, "acres", "openCount") for _, r, _, _ in parts), sum(n(r, "acres", "totalCount") for _, r, _, _ in parts)
    return {"lifts_open": sum(n(r, "lifts", "openCount") for _, r, _, _ in parts),
            "lifts_total": sum(n(r, "lifts", "totalCount") for _, r, _, _ in parts),
            "trails_open": sum(n(r, "trails", "openCount") for _, r, _, _ in parts),
            "trails_total": sum(n(r, "trails", "totalCount") for _, r, _, _ in parts),
            "terrain_open_pct": round(100 * acres / total) if total else None,
            "status": next((s for s in statuses if s.lower().startswith("open")), statuses[0] or None),
            "conditions": _plain(first.get("today")),
            "base_in": snow("snowBase"), "new_24h_in": snow("snow24Hours"), "new_48h_in": snow("snow48Hours"),
            "new_72h_in": snow("snow72Hours"), "new_7d_in": snow("snow7Days"), "storm_in": None, "season_in": None,
            "as_of": first.get("lastUpdated"),
            "mountains": [{"name": name, "status": rep.get("status"),
                           "lifts_open": n(rep, "lifts", "openCount"), "lifts_total": n(rep, "lifts", "totalCount"),
                           "trails_open": n(rep, "trails", "openCount"), "trails_total": n(rep, "trails", "totalCount")}
                          for name, rep, _, _ in parts],
            "lifts": lifts or None, "trails": trails or None}


def _onthesnow(cfg):
    """OnTheSnow's report page: "Lifts Open 6 / 21" and "Runs Open - / 140" ("-" when the resort didn't say)."""
    page = httpjson.get(ONTHESNOW.format(path=cfg["path"]), ttl=TTL, text=True)

    def pair(label):
        i = page.find(f">{label}<")
        m = re.search(r"<span>\s*([\d-]+)\s*/\s*([\d-]+)\s*</span>", page[i:i + 600]) if i >= 0 else None
        return (_int(m.group(1)), _int(m.group(2))) if m else (None, None)

    lo, lt = pair("Lifts Open")
    to, tt = pair("Runs Open")
    if lt is None and tt is None:
        return None
    upd = re.search(r"Updated:\s*([A-Z][a-z]{2} \d{1,2})", page)
    return {"lifts_open": lo, "lifts_total": lt, "trails_open": to, "trails_total": tt, "terrain_open_pct": None,
            "as_of": upd.group(1) if upd else None, "source": "OnTheSnow", "lifts": None, "trails": None}


def _try(fn):
    def run(*a):
        try:
            return fn(*a)
        except Exception:
            return None
    return run


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _plain(v):
    """Feed HTML as one plain line (Aspen's "today" message)."""
    s = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", v or "")).split())
    return s or None


def summary(live):
    """A live status without the per-lift and per-trail lists, for lists of resorts and the advisor."""
    return {k: v for k, v in live.items() if k not in ("lifts", "trails")} if live else live


def _text(v):
    return None if v in (None, "", "--") else v


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


_TYPES = {"powdr": _powdr, "mtnpowder": _mtnpowder, "aspen": _aspen, "onthesnow": _onthesnow}


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
