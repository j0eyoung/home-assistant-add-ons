"""Build trailmaps/<resort id>.json (runs and lifts shipped with the add-on) from OpenSkiMap's download.

    python tools/make_trailmaps.py <folder>

<folder> holds runs.geojson and lifts.geojson from https://tiles.openskimap.org/geojson/ (about 800 MB and 115 MB);
they're downloaded there first if missing. Each line of those files is one feature, so the files are read a line
at a time and only lines naming one of the resorts' ski areas are parsed. Ski areas are found the way the add-on
finds them (resortinfo.ski_areas: OpenSkiMap search by name, nearest the resort). Rerun it now and then, since
OpenSkiMap rebuilds from OpenStreetMap every day. Data (c) OpenSkiMap.org and OpenStreetMap contributors, ODbL."""
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import livestatus  # noqa: E402
import resortinfo  # noqa: E402
import resorts  # noqa: E402

SOURCE = "https://tiles.openskimap.org/geojson/{}.geojson"
SKIP_LIFTS = {"zip_line", "station", "goods", "pylon"}
LIVE = {"operating", None}


def lines_of(g):
    """GeoJSON geometry as lines of [lat, lon] (area runs give their outline)."""
    t, c = g.get("type"), g.get("coordinates") or []
    parts = {"LineString": [c], "MultiLineString": c, "Polygon": c[:1], "MultiPolygon": [p[0] for p in c if p]}.get(t, [])
    return [[[round(p[1], 5), round(p[0], 5)] for p in part] for part in parts if len(part) >= 2]


def area_ids(props):
    return {a.get("properties", {}).get("id") for a in props.get("skiAreas") or []}


def main(folder):
    for name in ("runs", "lifts"):
        path = os.path.join(folder, f"{name}.geojson")
        if not os.path.exists(path):
            print(f"downloading {name}.geojson ...", flush=True)
            req = urllib.request.Request(SOURCE.format(name), headers={"User-Agent": "ski-assistant-ha-addon"})
            with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
    wanted = {}  # ski area id -> resort id
    for r in resorts.load():
        areas = resortinfo.ski_areas(r)
        print(f"{r['id']}: {', '.join(a['properties']['name'] or '?' for a in areas) or 'NO SKI AREA FOUND'}", flush=True)
        for a in areas:
            wanted[a["properties"]["id"]] = r["id"]
    out = {rid: {"source": "OpenSkiMap", "built": dt.date.today().isoformat(), "runs": [], "lifts": []}
           for rid in set(wanted.values())}
    for name in ("runs", "lifts"):
        with open(os.path.join(folder, f"{name}.geojson"), encoding="utf-8") as f:
            for line in f:
                if not any(i in line for i in wanted):
                    continue
                feat = json.loads(line.strip().rstrip(","))
                p = feat["properties"]
                rids = {wanted[i] for i in area_ids(p) if i in wanted}
                lines = lines_of(feat.get("geometry") or {})
                if not rids or not lines or p.get("status") not in LIVE:
                    continue
                label = (p.get("name") or "").strip() or None
                if name == "runs":
                    if "downhill" not in (p.get("uses") or []):
                        continue
                    item = {"name": label, "level": livestatus.level(p.get("difficulty")), "lines": lines}
                else:
                    if p.get("liftType") in SKIP_LIFTS:
                        continue
                    item = {"name": label, "lines": lines}
                for rid in rids:
                    out[rid][name].append(item)
    os.makedirs(os.path.join(ROOT, "trailmaps"), exist_ok=True)
    for rid, g in sorted(out.items()):
        path = os.path.join(ROOT, "trailmaps", f"{rid}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(g, f, separators=(",", ":"))
        print(f"{rid}: {len(g['runs'])} runs, {len(g['lifts'])} lifts, {os.path.getsize(path) // 1024} KB", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
