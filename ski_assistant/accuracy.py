"""Which model has been right at each resort this season. Every evening the add-on saves each model's forecast
water for tomorrow; once SNOTEL has reported that day, it fills in what the resort's station measured. The blend
in forecast.py then leans toward the model with the smaller average miss (the PowderBench idea, on our own data).
Water is compared, not snow depth: SNOTEL depth settles and drifts, its precipitation gauge doesn't."""
import datetime as dt

import db
import forecast
import resorts
import snotel
import util

WINDOW_DAYS = 30
MIN_DAYS = 5      # equal weights until every model has this many scored wet days
DRY_FLOOR = 0.02  # days where forecast and observation are both under this teach nothing, so they're skipped


def record_tomorrow():
    """Save each model's forecast water for tomorrow, per resort (once each evening)."""
    tomorrow = (util.today() + dt.timedelta(days=1)).isoformat()
    for r in resorts.load():
        try:
            for model, water in forecast.day_water(r, tomorrow).items():
                db.x("INSERT OR IGNORE INTO forecast_check(date, resort_id, model, forecast_in) VALUES (?,?,?,?)",
                     (tomorrow, r["id"], model, water))
        except Exception:
            continue


def score_past():
    """Fill in what SNOTEL measured for saved forecasts of days that are over."""
    pending = db.q("SELECT DISTINCT resort_id FROM forecast_check WHERE observed_in IS NULL AND date < ?",
                   (util.today().isoformat(),))
    by_id = {r["id"]: r for r in resorts.load()}
    for row in pending:
        r = by_id.get(row["resort_id"])
        if not r or not r.get("snotel"):
            continue
        try:
            obs = snotel.daily_precip(r["snotel"])
        except Exception:
            continue
        for date, inches in obs.items():
            db.x("UPDATE forecast_check SET observed_in = ? WHERE resort_id = ? AND date = ? AND observed_in IS NULL",
                 (inches, r["id"], date))


def scores(resort_id):
    """{model_label: {"days", "mean_miss_in", "weight"}} over the last WINDOW_DAYS scored days."""
    since = (util.today() - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    rows = db.q("SELECT model, forecast_in, observed_in FROM forecast_check WHERE resort_id = ? AND date >= ? "
                "AND observed_in IS NOT NULL", (resort_id, since))
    per = {}
    for x in rows:
        if max(x["forecast_in"] or 0, x["observed_in"] or 0) < DRY_FLOOR:
            continue
        per.setdefault(x["model"], []).append(abs((x["forecast_in"] or 0) - x["observed_in"]))
    ready = len(per) == len(forecast.MODELS) and all(len(v) >= MIN_DAYS for v in per.values())
    raw = {m: 1 / (sum(v) / len(v) + 0.03) for m, v in per.items()} if ready else {}
    total = sum(raw.values())
    out = {}
    for m, label in forecast.MODELS.items():
        misses = per.get(m, [])
        out[label] = {"days": len(misses), "mean_miss_in": round(sum(misses) / len(misses), 2) if misses else None,
                      "weight": round(raw[m] / total, 2) if total else round(1 / len(forecast.MODELS), 2)}
    return out


def weights(resort_id):
    """{model_id: weight} for the blend (equal until every model has enough scored days)."""
    labels = {label: m for m, label in forecast.MODELS.items()}
    return {labels[k]: v["weight"] for k, v in scores(resort_id).items()}
