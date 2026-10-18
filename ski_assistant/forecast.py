"""Up-to-16-day mountain forecast per resort, at base, mid and summit, from two models (ECMWF IFS HRES and
GFS Seamless, which is HRRR over the US for the first days) via Open-Meteo. One request per resort per
model, cached 30 minutes in memory.

Snow comes from each elevation's own wet-bulb temperature, not the model's snowfall: Open-Meteo adjusts
temperature to the requested height but its snowfall/rain split belongs to the whole grid cell, so base and
summit would otherwise get the same split. Each hour's precipitation is split into snow and rain by the
wet bulb, and the snow's water becomes depth with a snow-to-liquid ratio (SLR) that rises as it gets colder.
(Approach after monkeysnow's ADR 0011; this is our own implementation.)

The "blend" is the mean of the models that have data for that hour; past days are the models' own early
hours (a modelled history, not observations: SNOTEL and the resort report are the observations)."""
import datetime as dt
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpjson
import util

URL = "https://api.open-meteo.com/v1/forecast"
MODELS = {"ecmwf_ifs": "ECMWF", "gfs_seamless": "GFS"}
BANDS = ("base", "mid", "summit")
PAST_DAYS, FORECAST_DAYS = 5, 16
FT_TO_M = 0.3048
MM_PER_IN = 25.4
HOURLY = ("temperature_2m,relative_humidity_2m,surface_pressure,precipitation,snowfall,wind_speed_10m,"
          "wind_gusts_10m,cloud_cover,freezing_level_height")


def band_ft(r):
    return {"base": r["base_ft"], "mid": round((r["base_ft"] + r["summit_ft"]) / 2), "summit": r["summit_ft"]}


# Physics helpers (metric inside, imperial out)
def _es(t_c):
    """Saturation vapour pressure over water, hPa (Bolton 1980)."""
    return 6.112 * math.exp(17.67 * t_c / (t_c + 243.5))


def wet_bulb_c(t_c, rh, p_hpa):
    """Psychrometric wet bulb at the hour's surface pressure, solved by bisection."""
    e = max(rh, 1) / 100 * _es(t_c)
    lo, hi = t_c - 40, t_c
    for _ in range(40):
        tw = (lo + hi) / 2
        gamma = 0.00066 * (1 + 0.00115 * tw) * p_hpa
        if _es(tw) - gamma * (t_c - tw) > e:
            hi = tw
        else:
            lo = tw
    return (lo + hi) / 2


def snow_fraction(tw_c):
    """All snow at a wet bulb of -0.5C or colder, all rain at +1.5C or warmer, linear between."""
    return max(0.0, min(1.0, (1.5 - tw_c) / 2.0))


def slr(tw_c):
    """Snow-to-liquid ratio: about 8:1 near freezing, 14:1 at -5C, 20:1 (Colorado champagne) at -10C."""
    return max(7.0, min(22.0, 8 - 1.2 * tw_c))


def quality(ratio, rain_share):
    if rain_share >= 0.5:
        return "rain"
    if rain_share >= 0.15:
        return "mixed"
    if ratio >= 15:
        return "light powder"
    if ratio >= 11:
        return "average"
    return "dense"


# Fetch and derive
def _fetch(r, model):
    els = band_ft(r)
    q = (f"?latitude={','.join([str(r['lat'])] * 3)}&longitude={','.join([str(r['lon'])] * 3)}"
         f"&elevation={','.join(str(round(els[b] * FT_TO_M)) for b in BANDS)}"
         f"&hourly={HOURLY}&models={model}&past_days={PAST_DAYS}&forecast_days={FORECAST_DAYS}"
         "&wind_speed_unit=mph&timezone=America%2FDenver")
    data = httpjson.get(URL + q, ttl=1800, timeout=30)
    return data if isinstance(data, list) else [data]


def _hours(loc, model):
    h = loc["hourly"]
    out = []
    for i, t in enumerate(h["time"]):
        temp, rh, p = h["temperature_2m"][i], h["relative_humidity_2m"][i], h["surface_pressure"][i]
        precip = h["precipitation"][i]
        if temp is None or precip is None:
            out.append(None)
            continue
        tw = wet_bulb_c(temp, rh if rh is not None else 90, p if p is not None else 700)
        frac = snow_fraction(tw)
        ratio = slr(tw)
        water_in = precip / MM_PER_IN
        fl = h.get("freezing_level_height", [None] * len(h["time"]))[i]
        out.append({"time": t, "temp_f": temp * 9 / 5 + 32, "wet_bulb_f": tw * 9 / 5 + 32,
                    "snow_in": water_in * frac * ratio, "rain_in": water_in * (1 - frac), "water_in": water_in,
                    "slr": ratio, "model_snow_in": (h["snowfall"][i] or 0) / 2.54,
                    "wind_mph": h["wind_speed_10m"][i] or 0, "gust_mph": h["wind_gusts_10m"][i] or 0,
                    "cloud": h["cloud_cover"][i], "freezing_ft": fl / FT_TO_M if fl is not None else None})
    return out


_derived = {}
_lock = threading.Lock()
TTL = 1800


def hourly(r):
    """{"times": [...], "models": {model: {band: [hour|None]}}, "blend": {band: [hour|None]}}.
    Cached per resort for as long as the raw forecast is, so the wet-bulb maths runs once per refresh."""
    key = (r["id"], r["lat"], r["lon"], r["base_ft"], r["summit_ft"])
    hit = _derived.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]

    def one(model):
        try:
            return model, _fetch(r, model)
        except Exception:
            return model, None

    with ThreadPoolExecutor(max_workers=len(MODELS)) as pool:
        fetched = [(m, locs) for m, locs in pool.map(one, MODELS) if locs]
    if not fetched:
        raise RuntimeError("no forecast model answered")
    times = fetched[0][1][0]["hourly"]["time"]
    per_model = {m: {b: _hours(loc, m) for b, loc in zip(BANDS, locs)} for m, locs in fetched}
    blend = {b: [_mean([per_model[m][b][i] for m in per_model]) for i in range(len(times))] for b in BANDS}
    out = {"times": times, "models": per_model, "blend": blend}
    with _lock:
        _derived[key] = (time.time(), out)
    return out


def _mean(hours):
    hs = [h for h in hours if h]
    if not hs:
        return None
    out = {"time": hs[0]["time"]}
    for k in hs[0]:
        if k == "time":
            continue
        vals = [h[k] for h in hs if h[k] is not None]
        out[k] = sum(vals) / len(vals) if vals else None
    return out


def _daily(hours, times):
    """Daily rollup. A day's snow = 6am that day to 6am the next: "day" is 6am-6pm, "night" the 12 hours after,
    i.e. what you wake up to the next morning. Temps and wind are for the calendar day."""
    days = {}
    for i, t in enumerate(times):
        h = hours[i]
        if h is None:
            continue
        stamp = dt.datetime.fromisoformat(t)
        day = stamp.date()
        d = days.setdefault(day.isoformat(), {"date": day.isoformat(), "snow_day_in": 0.0, "snow_night_in": 0.0,
                                              "rain_in": 0.0, "water_in": 0.0, "model_snow_in": 0.0,
                                              "temps": [], "wind": 0.0, "gust": 0.0, "freeze": [], "slr_w": 0.0})
        d["temps"].append(h["temp_f"])
        d["wind"] = max(d["wind"], h["wind_mph"])
        d["gust"] = max(d["gust"], h["gust_mph"])
        if h["freezing_ft"] is not None:
            d["freeze"].append(h["freezing_ft"])
        # Snow periods: 06-18 belongs to the day; 18-06 to the night that starts that evening
        bucket_day = day if stamp.hour >= 6 else day - dt.timedelta(days=1)
        b = days.get(bucket_day.isoformat())
        if b is None:
            continue
        key = "snow_day_in" if 6 <= stamp.hour < 18 else "snow_night_in"
        b[key] += h["snow_in"]
        b["rain_in"] += h["rain_in"]
        b["water_in"] += h["water_in"]
        b["model_snow_in"] += h["model_snow_in"]
        b["slr_w"] += h["slr"] * h["water_in"]
    out = []
    for d in days.values():
        snow = d["snow_day_in"] + d["snow_night_in"]
        water = d["water_in"]
        ratio = d["slr_w"] / water if water else None
        rain_share = d["rain_in"] / water if water > 0.01 else 0.0
        out.append({"date": d["date"], "snow_in": round(snow, 1), "snow_day_in": round(d["snow_day_in"], 1),
                    "snow_night_in": round(d["snow_night_in"], 1), "rain_in": round(d["rain_in"], 2),
                    "water_in": round(water, 2), "model_snow_in": round(d["model_snow_in"], 1),
                    "slr": round(ratio, 1) if ratio else None,
                    "quality": quality(ratio or 10, rain_share) if water >= 0.05 else None,
                    "tmax_f": round(max(d["temps"]), 1), "tmin_f": round(min(d["temps"]), 1),
                    "wind_mph": round(d["wind"], 1), "gust_mph": round(d["gust"], 1),
                    "freezing_ft": round(min(d["freeze"]) / 100) * 100 if d["freeze"] else None,
                    "hours": len(d["temps"])})
    return sorted(out, key=lambda x: x["date"])


def daily(r, band="mid"):
    """Blended daily forecast for one band, plus each model's daily snow for the spread chart."""
    h = hourly(r)
    days = _daily(h["blend"][band], h["times"])
    models = {}
    for m, bands in h["models"].items():
        md = {d["date"]: d for d in _daily(bands[band], h["times"])}
        models[MODELS[m]] = {k: md[k]["snow_in"] if k in md and md[k]["hours"] >= 18 else None for k in md}
    for d in days:
        d["models"] = {name: vals.get(d["date"]) for name, vals in models.items()}
    return [d for d in days if d["hours"] >= 18]  # drop the partial last day


def summary(r):
    """Dashboard row: daily mid-mountain snow for the last 5 days and next 15, with period totals.
    Also the summit and base totals for the next 5 days (rain at the base shows up here)."""
    h = hourly(r)
    today = util.today().isoformat()
    mid = [d for d in _daily(h["blend"]["mid"], h["times"]) if d["hours"] >= 18]
    past = [d for d in mid if d["date"] < today][-5:]
    future = [d for d in mid if d["date"] >= today][:15]

    def total(days):
        return round(sum(d["snow_in"] for d in days), 1)

    def band_total(band):
        ds = [d for d in _daily(h["blend"][band], h["times"]) if today <= d["date"] and d["hours"] >= 18][:5]
        return {"snow_in": total(ds), "rain_in": round(sum(d["rain_in"] for d in ds), 2)}

    return {"past": [{"date": d["date"], "snow_in": d["snow_in"]} for d in past],
            "future": [{k: d[k] for k in ("date", "snow_in", "snow_day_in", "snow_night_in", "quality",
                                          "tmax_f", "tmin_f", "gust_mph", "rain_in")} for d in future],
            "last5_in": total(past), "next5_in": total(future[:5]), "days6_10_in": total(future[5:10]),
            "days11_15_in": total(future[10:15]),
            "next5_by_band": {b: band_total(b) for b in ("base", "summit")}}


def next48(r, band="mid"):
    """Hourly blend for the next 48 hours (snow, temp, wind) for the detail chart."""
    h = hourly(r)
    now = util.now().strftime("%Y-%m-%dT%H:00")
    rows = [x for x in h["blend"][band] if x and x["time"] >= now][:48]
    return [{"time": x["time"], "snow_in": round(x["snow_in"], 2), "rain_in": round(x["rain_in"], 2),
             "temp_f": round(x["temp_f"]), "gust_mph": round(x["gust_mph"])} for x in rows]
