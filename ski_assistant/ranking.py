"""Best-day ranking. Score 0-100 per resort per date from fresh snow, wind, temperature, crowds, drive.

Weights are plain constants so they are easy to tune. On a "skis" day the score is 85% the normal score plus
15% for how much of the mountain is green and blue (the learning-to-ski bias)."""
import datetime as dt
import os

import drive
import gear
import livestatus
import resortinfo
import settings
import snotel
import traffic
import transit
import util
import weather

# Max points per factor (sum 100)
W_SNOW, W_WIND, W_TEMP, W_CROWD, W_DRIVE = 40, 20, 15, 15, 10
SKI_BIAS = 15  # share of the score given to beginner terrain on a skis day
POWDER_IN = float(os.getenv("POWDER_ALERT_INCHES", "6"))


def _snow_pts(inches):  # 12in+ is a full powder day
    return W_SNOW * min(inches, 12.0) / 12.0


def _wind_pts(gust):  # lifts hold around 40-50 mph gusts
    return W_WIND * max(0.0, min(1.0, (50 - gust) / 35))


def _temp_pts(tmax, tmin):  # happiest around 15-30F; penalise bitter cold and slush
    mid = (tmax + tmin) / 2
    if 15 <= mid <= 30:
        return W_TEMP
    gap = 15 - mid if mid < 15 else mid - 30
    return W_TEMP * max(0.0, 1 - gap / 20)


def _crowd_pts(date):  # Mon-Thu quiet, Fri medium, Sat/Sun and ski holidays busiest
    if drive.holiday(date):
        return 0.0
    return {4: 0.6, 5: 0.0, 6: 0.15}.get(date.weekday(), 1.0) * W_CROWD


def _drive_pts(drive_min):  # 60 min or less is free, 4h+ gets nothing
    return W_DRIVE * max(0.0, min(1.0, (240 - drive_min) / 180))


def score_day(r, day, new_snow_in, drive_min):
    date = dt.date.fromisoformat(day["date"])
    parts = {"snow": _snow_pts(new_snow_in), "wind": _wind_pts(day["gust_mph"]),
             "temp": _temp_pts(day["tmax_f"], day["tmin_f"]), "crowd": _crowd_pts(date),
             "drive": _drive_pts(drive_min)}
    return round(sum(parts.values()), 1), {k: round(v, 1) for k, v in parts.items()}


def best_days(resorts, date=None, skis=False, include_paid=True, departure=None):
    """Ranked list for `date` (ISO string, default today in Denver). Fresh snow = overnight snow before `date`
    plus the snow that falls during the day."""
    date = date or util.today().isoformat()
    st = settings.load()
    dep = settings.departure(departure)
    live_today = date == util.today().isoformat()
    sensors = traffic.waze_sensors() if live_today else []
    rows = []
    for r in resorts:
        if not include_paid and r.get("pass") == "paid":
            continue
        try:
            days = weather.forecast(r)
        except Exception as e:
            rows.append({"resort": r["name"], "error": f"forecast failed: {e}"})
            continue
        idx = next((i for i, d in enumerate(days) if d["date"] == date), None)
        if idx is None:
            rows.append({"resort": r["name"], "error": f"no forecast for {date}"})
            continue
        day = days[idx]
        # Fresh = overnight snow (the previous day's 6am-6am total) plus what falls while you ride (6am-6pm);
        # that evening's snow belongs to tomorrow
        prev = days[idx - 1]["snow_in"] if idx > 0 else 0.0
        fresh = round(prev + day["snow_day_in"], 1)
        leave = drive.plan(r, dep, date, st["arrive_by"], st["buffer_min"], powder=fresh >= POWDER_IN)
        score, parts = score_day(r, day, fresh, leave["drive_min"])
        pct = resortinfo.beginner_pct(r)
        if skis:
            score = round(score * (100 - SKI_BIAS) / 100 + SKI_BIAS * (pct if pct is not None else 50) / 100, 1)
        rows.append({"resort": r["name"], "id": r["id"], "pass": r.get("pass"), "score": score, "parts": parts,
                     "fresh_in": fresh, "tmax_f": day["tmax_f"], "tmin_f": day["tmin_f"],
                     "wind_mph": day["wind_mph"], "gust_mph": day["gust_mph"], "leave": leave,
                     "beginner_pct": pct, "gear": gear.call(day, fresh, skis), "transit": transit.for_resort(r),
                     "snowpack": snotel.resort_snowpack(r), "live": livestatus.live_status(r),
                     "traffic": traffic.for_resort(r, sensors) if live_today else None})
    rows.sort(key=lambda x: -x.get("score", -1))
    return rows


def powder_alerts(resorts, threshold_in=6.0, window_days=2):
    """Resorts with >= threshold forecast snow over the next `window_days` days (today included)."""
    today = util.today().isoformat()
    hits = []
    for r in resorts:
        try:
            days = [d for d in weather.forecast(r, past_days=0) if d["date"] >= today][:window_days]
        except Exception:
            continue
        total = round(sum(d["snow_in"] for d in days), 1)
        if total >= threshold_in:
            hits.append({"resort": r["name"], "snow_in": total, "first_day": days[0]["date"]})
    return sorted(hits, key=lambda h: -h["snow_in"])
