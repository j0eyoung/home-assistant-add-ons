"""Daily mid-mountain forecast used by the ranking, powder alerts and gear call (a thin view over forecast.py).
A day's snow_in runs 6am that day to 6am the next, so the day before's total is what's fresh that morning."""
import forecast as fc


def forecast(r, days=None, past_days=None):
    """Daily list of dicts: date, snow_in, tmax_f, tmin_f, wind_mph, gust_mph, quality, rain_in
    (the past 5 days are included; callers filter by date)."""
    return [{k: d[k] for k in ("date", "snow_in", "snow_day_in", "tmax_f", "tmin_f", "wind_mph", "gust_mph", "quality", "rain_in")}
            for d in fc.daily(r)]
