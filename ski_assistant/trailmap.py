"""Trail map data: a resort's runs and lifts from OpenStreetMap (the same data OpenSkiMap draws), each marked
open, hold, scheduled or closed from the resort's live report by matching names.

Where the lines come from, first found wins:
  1. trailmaps/<resort id>.json, shipped with the add-on. tools/make_trailmaps.py cuts them out of OpenSkiMap's
     download (runs and lifts tagged with the resort's ski areas). Public Overpass servers are often slow or down
     (November 2026: 502s and minute-long timeouts), so the built-in resorts never wait on them.
  2. A copy saved from Overpass in the cache folder (/data/trailmaps in the add-on), up to 30 days old.
  3. Overpass itself, for a resort added in ski_resorts.json: every run and lift in the bounding box of the
     resort's OpenSkiMap ski areas, kept when one of its points falls inside an area's outline.
Status is the live feed's (15 minutes). Names differ a little between OSM and the feeds ("Hi-Lonesome Express" /
"High Lonesome Express", "Coffee Pot (Lower)" / "Coffee Pot"), so matching drops filler words, ignores word order
and upper/lower, and finally accepts a close spelling. Map data (c) OpenStreetMap contributors, ODbL."""
import difflib
import json
import os
import re
import time
import urllib.parse

import httpjson
import livestatus
import resortinfo

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLED = os.path.join(HERE, "trailmaps")
CACHE = os.getenv("TRAILMAP_CACHE") or ("/data/trailmaps" if os.path.isdir("/data") else os.path.join(HERE, ".cache", "trailmaps"))
CACHE_DAYS = 30
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
LIFTS = "chair_lift|gondola|cable_car|mixed_lift|drag_lift|t-bar|j-bar|platter|rope_tow|magic_carpet"
_mem = {}  # resort id -> (loaded_at, geometry)

# Words that only say what kind of thing it is. Lifts drop more ("Hi-Lonesome Express" / "High Lonesome
# Express"); runs keep double and triple ("Double Zero" and "Triple Zero" are different runs).
FILLER_RUN = {"the", "run", "trail", "piste", "ski"}
FILLER_LIFT = FILLER_RUN | {"lift", "lifts", "chair", "chairlift", "express", "quad", "triple", "double", "six",
                            "pack", "sixpack", "high", "speed", "detachable"}
POSITION = {"upper", "lower", "middle", "mid", "top", "bottom"}
QUALIFIERS = POSITION | {"village", "i", "ii", "iii", "1", "2", "3"}
SAME = {"hi": "high", "endeavour": "endeavor", "mt": "mount", "st": "saint", "n": "and"}
RANK = {"open": 3, "hold": 2, "scheduled": 1, "closed": 0}


def geometry(r):
    """{"runs": [{name, level, lines}], "lifts": [{name, lines}], "source"}: lines are [[lat, lon], ...]."""
    hit = _mem.get(r["id"])
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    g = _read(os.path.join(BUNDLED, f"{r['id']}.json"))
    if not g:
        safe = re.sub(r"[^\w-]", "_", r["id"])
        path = os.path.join(CACHE, f"{safe}.json")
        cached = _read(path)
        if cached and time.time() - cached.get("saved", 0) < CACHE_DAYS * 86400:
            g = cached
        else:
            try:
                g = _from_overpass(r)
                _write(path, g)
            except Exception:
                if not cached:
                    raise
                g = cached  # an old copy beats no map
    _mem[r["id"]] = (time.time(), g)
    return g


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write(path, g):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(g, f, separators=(",", ":"))
    except OSError as e:
        print(f"[trailmap] couldn't save {path}: {e}", flush=True)


def _from_overpass(r):
    areas = resortinfo.ski_areas(r)
    if not areas:
        raise RuntimeError("OpenSkiMap has no ski area for this resort")
    runs, lifts = _osm([ring for f in areas for ring in _rings(f["geometry"])])
    return {"source": "OpenStreetMap (Overpass)", "saved": time.time(), "runs": runs, "lifts": lifts}


def for_resort(r):
    g = geometry(r)
    # Copies, so marking status never changes the cached lines
    runs = [dict(f) for f in g["runs"]]
    lifts = [dict(f) for f in g["lifts"]]
    if not runs and not lifts:
        raise RuntimeError("OpenStreetMap has no runs or lifts for this resort")
    live = livestatus.live_status(r) or {}
    has_status = bool(live.get("lifts") or live.get("trails"))
    run_idx, lift_idx = _Index(live.get("trails") or []), _Index(live.get("lifts") or [], lifts=True)
    used_runs, used_lifts = set(), set()
    for f in runs:
        hits = run_idx.find(f["name"])
        used_runs |= {id(x) for x in hits}
        f["status"] = _best(hits) if has_status else None
        f["level"] = next((x.get("level") for x in hits if x.get("level")), None) or f["level"]
        f["groomed"] = any(x.get("groomed") for x in hits)
    for f in lifts:
        hits = lift_idx.find(f["name"])
        used_lifts |= {id(x) for x in hits}
        f["status"] = _best(hits) if has_status else None
    lat = [p[0] for f in runs + lifts for line in f["lines"] for p in line]
    lon = [p[1] for f in runs + lifts for line in f["lines"] for p in line]
    named = lambda fs: sum(1 for f in fs if f["name"])
    return {"has_status": has_status, "as_of": live.get("as_of"), "source": g.get("source"),
            "bounds": [[min(lat), min(lon)], [max(lat), max(lon)]],
            "runs": [_out(f) for f in runs], "lifts": [_out(f) for f in lifts],
            "matched": {"runs": [sum(1 for f in runs if f["name"] and f["status"]), named(runs)],
                        "lifts": [sum(1 for f in lifts if f["name"] and f["status"]), named(lifts)]},
            # Open in the report but not found on the map, so the page can still name them
            "unmapped_open": sorted({x["name"] for x in (live.get("trails") or []) + (live.get("lifts") or [])
                                     if x["status"] == "open" and id(x) not in used_runs | used_lifts})}


def _out(f):
    out = {"n": f["name"], "l": f.get("level"), "s": f.get("status"), "c": f["lines"]}
    if f.get("groomed"):
        out["g"] = 1
    return out


def _best(items):
    return max((x["status"] for x in items), key=RANK.get) if items else None


# ---------- OpenStreetMap ----------
def _rings(g):
    if g["type"] == "Polygon":
        return [g["coordinates"][0]]
    if g["type"] == "MultiPolygon":
        return [p[0] for p in g["coordinates"]]
    return []


def _osm(rings):
    """Runs and lifts inside the ski area outlines: [{name, level, lines: [[[lat, lon], ...], ...]}]."""
    xs = [p[0] for ring in rings for p in ring]
    ys = [p[1] for ring in rings for p in ring]
    bb = f"{min(ys) - .005},{min(xs) - .005},{max(ys) + .005},{max(xs) + .005}"
    q = (f'[out:json][timeout:90];(way["piste:type"="downhill"]({bb});relation["piste:type"="downhill"]({bb});'
         f'way["aerialway"~"^({LIFTS})$"]({bb}););out tags geom;')
    body = urllib.parse.urlencode({"data": q}).encode()
    data, err = None, None
    for url in OVERPASS:
        try:
            data = httpjson.get(url, ttl=3600, timeout=90, body=body)
            break
        except Exception as e:
            err = e
    if data is None:
        raise RuntimeError(f"OpenStreetMap (Overpass) didn't answer: {err}")
    runs, lifts, member_ids = [], [], set()
    rels = [e for e in data.get("elements", []) if e["type"] == "relation"]
    for e in rels:
        member_ids |= {m["ref"] for m in e.get("members", []) if m.get("type") == "way"}
    for e in data.get("elements", []):
        t = e.get("tags") or {}
        if e["type"] == "way":
            lines = [_line(e.get("geometry"))]
        else:
            lines = [_line(m.get("geometry")) for m in e.get("members", []) if m.get("type") == "way"]
        lines = [x for x in lines if len(x) >= 2]
        if not lines or not any(_inside(p, rings) for line in lines for p in line):
            continue
        name = (t.get("name") or t.get("piste:name") or "").strip() or None
        if "aerialway" in t:
            lifts.append({"name": name, "level": None, "lines": lines})
        elif e["type"] == "way" and e["id"] in member_ids and not name:
            continue  # an unnamed piece of a run relation: the relation draws it
        else:
            runs.append({"name": name, "level": livestatus.level(t.get("piste:difficulty")), "lines": lines})
    return runs, lifts


def _line(geom):
    return [[round(p["lat"], 5), round(p["lon"], 5)] for p in geom or [] if p]


def _inside(p, rings):
    """Point [lat, lon] inside any outline (GeoJSON rings are [lon, lat])."""
    y, x = p
    for ring in rings:
        hit = False
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                hit = not hit
        if hit:
            return True
    return False


# ---------- Name matching ----------
def _tokens(name, filler=FILLER_RUN):
    s = str(name or "").lower().replace("&", " and ").replace("’", "'")
    s = re.sub(r"'", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return [SAME.get(w, w) for w in s.split() if SAME.get(w, w) not in filler]


class _Index:
    """Feed items looked up by an OSM name, loosest match last: same words, same words in another order, same words
    leaving out upper/lower/I/II (but never Upper for Lower), then a close spelling ("Noth Fork" / "North Fork";
    stricter for short names, so "David's Run" doesn't become "Davis")."""

    def __init__(self, items, lifts=False):
        self.filler = FILLER_LIFT if lifts else FILLER_RUN
        self.exact, self.sorted, self.core, self.joined = {}, {}, {}, {}
        for x in items:
            tok = _tokens(x["name"], self.filler)
            if not tok:
                continue
            self.exact.setdefault(" ".join(tok), []).append(x)
            self.joined.setdefault("".join(tok), []).append(x)  # "Rug Rat" / "Rugrat", "Tin Horn" / "Tinhorn"
            self.sorted.setdefault(" ".join(sorted(tok)), []).append(x)
            core = [w for w in tok if w not in QUALIFIERS]
            if core:
                self.core.setdefault(" ".join(sorted(core)), []).append(x)

    def find(self, name):
        tok = _tokens(name, self.filler)
        if not tok:
            return []
        key = " ".join(tok)
        hits = self.exact.get(key) or self.sorted.get(" ".join(sorted(tok))) or self.joined.get("".join(tok))
        if hits:
            return hits
        core = " ".join(sorted(w for w in tok if w not in QUALIFIERS))
        if core and core in self.core:
            mine = POSITION & set(tok)
            fits = [x for x in self.core[core]
                    if not mine or not (POSITION & set(_tokens(x["name"], self.filler))) or mine & set(_tokens(x["name"], self.filler))]
            if fits:
                return fits
        close = difflib.get_close_matches(key, list(self.exact), n=1, cutoff=0.93 if len(key) < 9 else 0.88)
        return self.exact[close[0]] if close else []
