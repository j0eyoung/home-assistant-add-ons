"""Open-Meteo forecast per resort, at mid-mountain elevation. Imperial units."""
import httpjson
from resorts import mid_ft

URL = "https://api.open-meteo.com/v1/forecast"
FT_TO_M = 0.3048


def forecast(r, days=7, past_days=3):
    """Daily list of dicts: date, snow_in, tmax_f, tmin_f, wind_mph, gust_mph (past_days included)."""
    q = (f"?latitude={r['lat']}&longitude={r['lon']}&elevation={round(mid_ft(r) * FT_TO_M)}"
         "&daily=snowfall_sum,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,wind_gusts_10m_max"
         "&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch"
         f"&timezone=America%2FDenver&forecast_days={days}&past_days={past_days}")
    d = httpjson.get(URL + q)["daily"]
    out = []
    for i, day in enumerate(d["time"]):
        out.append({"date": day, "snow_in": d["snowfall_sum"][i] or 0.0, "tmax_f": d["temperature_2m_max"][i],
                    "tmin_f": d["temperature_2m_min"][i], "wind_mph": d["wind_speed_10m_max"][i] or 0.0,
                    "gust_mph": d["wind_gusts_10m_max"][i] or 0.0})
    return out
