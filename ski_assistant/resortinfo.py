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


def info(r):
    base = DEFAULT_INFO.get(r["id"], {})
    return {k: r.get(k, base.get(k)) for k in ("beginner_pct", "openskimap_id", "webcams_url")}


def openskimap_url(r):
    oid = info(r)["openskimap_id"]
    return f"https://openskimap.org/?obj={oid}" if oid else None


def beginner_pct(r):
    return info(r)["beginner_pct"]
