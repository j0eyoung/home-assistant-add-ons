"""Static per-resort extras: share of green and blue terrain, OpenSkiMap link, webcam page.
A resort's own keys in ski_resorts.json (beginner_pct, openskimap_id, openskimap_names, webcams_url) override these.

beginner_pct is green + blue run length as a share of all downhill runs, from OpenSkiMap statistics
(api.openskimap.org, October 2026). Data (c) OpenSkiMap.org contributors and OpenStreetMap contributors, ODbL.
OpenSkiMap's ids change when it rebuilds (three of these had by November 2026), so ski_areas() finds each resort
by its openskimap_names and the stored id is only a fallback."""
import urllib.parse

import httpjson
import util

OSM_SEARCH = "https://api.openskimap.org/search?query="
OSM_FEATURE = "https://api.openskimap.org/features/"

DEFAULT_INFO = {
    "winter_park": {"beginner_pct": 63, "openskimap_id": "eac3283b22abc1d56081b11e2c4867209961f982",
                    "openskimap_names": ["Winter Park"],
                    "webcams_url": "https://www.winterparkresort.com/the-mountain/mountain-cams"},
    "steamboat": {"beginner_pct": 55, "openskimap_id": "5267096488ef4504f32f94de066e28cd88b7830e",
                  "openskimap_names": ["Steamboat"],
                  "webcams_url": "https://www.steamboat.com/the-mountain/mountain-cams"},
    "copper": {"beginner_pct": 59, "openskimap_id": "0bab3102857cf4c7243d3db844c283a24413fa28",
               "openskimap_names": ["Copper Mountain"],
               "webcams_url": "https://www.coppercolorado.com/the-mountain/webcams/"},
    "eldora": {"beginner_pct": 64, "openskimap_id": "a2909bf21b379e545b5be4f1dbe9b6c334e9e41c",
               "openskimap_names": ["Eldora"],
               "webcams_url": "https://www.eldora.com/the-mountain/current-conditions/webcams/"},
    "abasin": {"beginner_pct": 43, "openskimap_id": "1e281ff389476a82150ad7ef7be5f1ea48edd5e5",
               "openskimap_names": ["Arapahoe Basin"],
               "webcams_url": "https://www.arapahoebasin.com/mountain-cams/"},
    "aspen_snowmass": {"beginner_pct": 72, "openskimap_id": "03b56bd47b26c384d82474a2fb4b3fbc3a0c4a31",
                       "openskimap_names": ["Aspen Snowmass", "Aspen Mountain", "Aspen Highlands", "Buttermilk"],
                       "webcams_url": "https://www.aspensnowmass.com/four-mountains/mountain-cams"},
    # Vail's site blocks scripts, so this page couldn't be checked; it follows Vail's usual URL pattern
    "keystone": {"beginner_pct": 55, "openskimap_id": "7d855b81e131f7cb7bdbc7b55e47a18d3ccb5e67",
                 "openskimap_names": ["Keystone"],
                 "webcams_url": "https://www.keystoneresort.com/the-mountain/mountain-conditions/mountain-cams.aspx"},
}


# Live webcam snapshots (still images that the cam host refreshes every few minutes; checked October 2026).
# Eldora (YouTube streams), Keystone and Steamboat (sites block scripts) only have the webcam page link.
WEBCAM_IMAGES = {
    "winter_park": ["https://cams.winterparkresort.com/best-western-cam.jpg"],
    "copper": ["https://img.hdrelay.com/frames/fb469125-f1f3-459f-aeb4-98cb674e395f/default/last.jpg"],
    "abasin": ["https://dirigo-resorts-f4e2bde5azc2cne6.z02.azurefd.net/arapahoe/images/medium/webcams/abasincam1001m.jpg",
               "https://dirigo-resorts-f4e2bde5azc2cne6.z02.azurefd.net/arapahoe/images/medium/webcams/abasincam5.jpg"],
    "aspen_snowmass": ["https://backend.roundshot.com/cams/87/medium", "https://backend.roundshot.com/cams/89/medium"],
}

# Weekend parking reservations. Only A-Basin's 2026-27 rules were confirmed (parkabasin.com, October 2026);
# add others in ski_resorts.json as {"parking": {"url", "note", "from", "to"}} (from/to are ISO dates).
DEFAULT_PARKING = {
    "abasin": {"url": "https://www.parkabasin.com/parkingbasics", "from": "2027-01-02", "to": "2027-05-02",
               "note": "A-Basin needs a parking reservation on weekends ($20, free with 4+ in the car). "
                       "Weekend reservations open Mondays at 2pm."},
}


def info(r):
    base = DEFAULT_INFO.get(r["id"], {})
    out = {k: r.get(k, base.get(k)) for k in ("beginner_pct", "openskimap_id", "webcams_url")}
    out["parking"] = r.get("parking", DEFAULT_PARKING.get(r["id"]))
    out["webcam_images"] = r.get("webcam_images", WEBCAM_IMAGES.get(r["id"], []))
    return out


def parking_needed(r, date_iso):
    """The parking note if this resort needs a reservation on that date (weekends within its season), else None."""
    import datetime as dt
    p = info(r)["parking"]
    if not p:
        return None
    d = dt.date.fromisoformat(date_iso)
    if d.weekday() < 5 or (p.get("from") and date_iso < p["from"]) or (p.get("to") and date_iso > p["to"]):
        return None
    return p


def ski_areas(r):
    """The resort's ski areas on OpenSkiMap (GeoJSON features with their outline), found by name nearest the resort.
    OpenSkiMap's ids change when it rebuilds, so the stored openskimap_id is only the fallback. Aspen Snowmass
    has four areas, one per mountain."""
    names = r.get("openskimap_names") or DEFAULT_INFO.get(r["id"], {}).get("openskimap_names") or [r["name"]]
    out = []
    for name in names:
        try:
            feats = httpjson.get(OSM_SEARCH + urllib.parse.quote(name), ttl=7 * 86400, stale_max=30 * 86400)
        except Exception:
            continue
        areas = [f for f in feats if f.get("properties", {}).get("type") == "skiArea"
                 and (f.get("geometry") or {}).get("type") in ("Polygon", "MultiPolygon")]
        named = [f for f in areas if name.lower() in str(f["properties"].get("name") or "").lower()] or areas
        near = [(util.miles(r["lat"], r["lon"], *_centre(f)), f) for f in named]
        near = [x for x in near if x[0] <= 15]
        if near:
            best = min(near, key=lambda x: x[0])[1]
            if all(best["properties"]["id"] != f["properties"]["id"] for f in out):
                out.append(best)
    if not out and info(r)["openskimap_id"]:
        try:
            out.append(httpjson.get(f"{OSM_FEATURE}{info(r)['openskimap_id']}.geojson", ttl=7 * 86400))
        except Exception:
            pass
    return out


def _centre(f):
    g = f["geometry"]
    ring = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
    return sum(p[1] for p in ring) / len(ring), sum(p[0] for p in ring) / len(ring)


def openskimap_url(r):
    try:
        areas = ski_areas(r)
    except Exception:
        areas = []
    oid = areas[0]["properties"]["id"] if areas else info(r)["openskimap_id"]
    return f"https://openskimap.org/?obj={oid}" if oid else None


def beginner_pct(r):
    return info(r)["beginner_pct"]
