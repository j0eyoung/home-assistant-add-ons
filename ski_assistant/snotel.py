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
