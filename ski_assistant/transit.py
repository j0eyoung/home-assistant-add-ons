"""Shuttle and transit options per resort. There is no live API for these, so this is static info with links:
check the link for the current schedule. Notes reflect what was published for 2025-26; 2026-27 dates were not
confirmed when this was written. A resort's own "transit" list (in ski_resorts.json) overrides the defaults."""

SUMMIT_STAGE = {"name": "Summit Stage (free county bus)",
                "url": "https://www.summitcountyco.gov/services/transit_summit_stage/bus_schedule/winter_bus_schedule.php",
                "note": "Winter schedule runs Nov 15, 2026 to Apr 17, 2027."}
SNOWSTANG_NOTE = "CDOT Snowstang coach from Denver, weekends and holiday Mondays last season (about $25 round trip)."

DEFAULT_TRANSIT = {
    "winter_park": [{"name": "Winter Park Express (Amtrak ski train)", "url": "https://www.amtrak.com/winter-park-express",
                     "note": "Denver Union Station to the base, Thursday to Monday in season last year. Dates for 2026-27 not confirmed."}],
    "copper": [dict(SUMMIT_STAGE, note="Copper/Frisco route. " + SUMMIT_STAGE["note"]),
               {"name": "Snowstang to Copper", "url": "https://ridebustang.com/routes/", "note": SNOWSTANG_NOTE}],
    "keystone": [SUMMIT_STAGE],
    "abasin": [{"name": "Snowstang to Arapahoe Basin", "url": "https://ridebustang.com/routes/arapahoe-basin/",
                "note": SNOWSTANG_NOTE},
               dict(SUMMIT_STAGE, note="Keystone park-and-ride to A-Basin in peak season. " + SUMMIT_STAGE["note"])],
    "eldora": [{"name": "RTD to Nederland, then the Eldora shuttle", "url": "https://www.rtd-denver.com/",
                "note": "Eldora is the one resort RTD serves (via Boulder to the Nederland park-and-ride). Check RTD for the current route."}],
}


def for_resort(r):
    return r.get("transit") or DEFAULT_TRANSIT.get(r["id"], [])
