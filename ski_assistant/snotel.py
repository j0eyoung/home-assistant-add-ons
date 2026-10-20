"""SNOTEL snowpack from the NRCS AWDB REST API (SNWD snow depth in, WTEQ water equivalent in)."""
import datetime as dt
import httpjson

URL = "https://wcc.sc.egov.usda.gov/awdbRestApi/services/v1/data"


def snowpack(triplets, days=4):
    """Per station: current depth/SWE and 24h/72h depth change, for stations that answered."""
    end = dt.date.today()
    begin = end - dt.timedelta(days=days)
    q = (f"?stationTriplets={','.join(triplets)}&elements=SNWD,WTEQ&duration=DAILY"
         f"&beginDate={begin}&endDate={end}")
    out = {}
    for st in httpjson.get(URL + q, ttl=3600):
        res = {}
        for el in st.get("data", []):
            vals = [(v["date"], v.get("value")) for v in el["values"] if v.get("value") is not None]
            if vals:
                res[el["stationElement"]["elementCode"]] = vals
        depth, swe = res.get("SNWD"), res.get("WTEQ")
        if not depth:
            continue
        cur = depth[-1][1]
        out[st["stationTriplet"]] = {
            "depth_in": cur, "swe_in": swe[-1][1] if swe else None, "as_of": depth[-1][0],
            "new_24h_in": round(cur - depth[-2][1], 1) if len(depth) >= 2 else None,
            "new_72h_in": round(cur - depth[-4][1], 1) if len(depth) >= 4 else None}
    return out


def resort_snowpack(r):
    """Deepest-reporting nearby station for a resort, or None."""
    try:
        s = snowpack(r.get("snotel") or [])
    except Exception:
        return None
    return max(s.values(), key=lambda v: v["depth_in"]) if s else None


def daily_precip(triplets, days=35):
    """{date: inches} of daily precipitation from the first station in the list that reports it (PREC is the
    water-year running total, so each day is the difference from the day before)."""
    end = dt.date.today()
    begin = end - dt.timedelta(days=days)
    q = f"?stationTriplets={','.join(triplets)}&elements=PREC&duration=DAILY&beginDate={begin}&endDate={end}"
    by_station = {}
    for st in httpjson.get(URL + q, ttl=6 * 3600):
        for el in st.get("data", []):
            vals = [(v["date"][:10], v.get("value")) for v in el["values"] if v.get("value") is not None]
            if len(vals) >= 2:
                by_station[st["stationTriplet"]] = vals
    for trip in triplets:
        vals = by_station.get(trip)
        if vals:
            out = {}
            for (_, v0), (d1, v1) in zip(vals, vals[1:]):
                if v1 >= v0:  # PREC resets to zero on Oct 1; skip that day
                    out[d1] = round(v1 - v0, 2)
            return out
    return {}
