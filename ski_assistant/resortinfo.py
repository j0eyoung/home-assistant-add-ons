"""Static per-resort extras: share of green and blue terrain, OpenSkiMap link, webcam page.
A resort's own keys in ski_resorts.json (beginner_pct, openskimap_id, webcams_url) override these.

beginner_pct is green + blue run length as a share of all downhill runs, from OpenSkiMap statistics
(api.openskimap.org, October 2026). Data (c) OpenSkiMap.org contributors and OpenStreetMap contributors, ODbL."""

DEFAULT_INFO = {
    "winter_park": {"beginner_pct": 63, "openskimap_id": "eac3283b22abc1d56081b11e2c4867209961f982",
                    "webcams_url": "https://www.winterparkresort.com/the-mountain/mountain-cams"},
    "steamboat": {"beginner_pct": 55, "openskimap_id": "1b452491f464540026e80e10ab6d7290b414c1f6",
                  "webcams_url": "https://www.steamboat.com/the-mountain/mountain-cams"},
    "copper": {"beginner_pct": 59, "openskimap_id": "0bab3102857cf4c7243d3db844c283a24413fa28",
               "webcams_url": "https://www.coppercolorado.com/the-mountain/webcams/"},
    "eldora": {"beginner_pct": 64, "openskimap_id": "1f25a1eacb8cc9814282d91ae00fd9af7a533d0e",
               "webcams_url": "https://www.eldora.com/the-mountain/current-conditions/webcams/"},
    "abasin": {"beginner_pct": 43, "openskimap_id": "1e281ff389476a82150ad7ef7be5f1ea48edd5e5",
               "webcams_url": "https://www.arapahoebasin.com/mountain-cams/"},
    "aspen_snowmass": {"beginner_pct": 72, "openskimap_id": "ab35349ba4e03d734a486561e99d5be0b772449f",
                       "webcams_url": "https://www.aspensnowmass.com/four-mountains/mountain-cams"},
    # Vail's site blocks scripts, so this page couldn't be checked; it follows Vail's usual URL pattern
    "keystone": {"beginner_pct": 55, "openskimap_id": "7d855b81e131f7cb7bdbc7b55e47a18d3ccb5e67",
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


def openskimap_url(r):
    oid = info(r)["openskimap_id"]
    return f"https://openskimap.org/?obj={oid}" if oid else None


def beginner_pct(r):
    return info(r)["beginner_pct"]
