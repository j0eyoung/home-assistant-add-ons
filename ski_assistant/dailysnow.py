"""Daily Snow: a short Colorado forecast discussion, written by Claude once a day from the add-on's own data
(the 15-day blend per resort, the two models' totals, and the observed snow), through Claude Code on your
Claude subscription. Stored in SQLite so it runs once a day, not once per page view."""
import json
from concurrent.futures import ThreadPoolExecutor

import advisor
import db
import forecast
import livestatus
import resorts
import snotel
import util

SYSTEM = """You write a daily snow forecast discussion for Colorado skiers and riders, in the style of a
mountain forecaster's daily post. Use only the JSON data; never invent storms, totals or dates it doesn't show.
Inches are mid-mountain unless noted. Days 11-15 are low confidence; say so when you mention them, and say
when the two models disagree. Write plain text with these parts:
a one-line headline;
"Summary" (2-3 sentences);
"Next 5 days" (timing, totals by resort, snow quality, rain at the base if any);
"Days 6-15" (the pattern and confidence);
"Best bet" (one resort and day, for a snowboarder with an Ikon and a Keystone pass).
Keep it under 280 words. No markdown symbols."""


def _resort_data(r):
    s = forecast.summary(r)
    days = forecast.daily(r)
    today = util.today().isoformat()
    future = [d for d in days if d["date"] >= today][:15]
    models = {}
    for name in forecast.MODELS.values():
        vals = [d["models"].get(name) for d in future]
        models[name] = {"next5": round(sum(v or 0 for v in vals[:5]), 1),
                        "days6_10": round(sum(v or 0 for v in vals[5:10]), 1),
                        "days11_15": round(sum(v or 0 for v in vals[10:15]), 1),
                        "days_with_data": sum(v is not None for v in vals)}
    live = livestatus.live_status(r) or {}
    return {"resort": r["name"], "pass": r.get("pass"), "last5_in": s["last5_in"], "next5_in": s["next5_in"],
            "days6_10_in": s["days6_10_in"], "days11_15_in": s["days11_15_in"], "next5_base_and_summit": s["next5_by_band"],
            "daily": [{"date": d["date"], "snow_in": d["snow_in"], "quality": d["quality"],
                       "high_f": round(d["tmax_f"]), "gust_mph": round(d["gust_mph"])} for d in future],
            "models": models, "snotel": snotel.resort_snowpack(r),
            "reported": {k: live.get(k) for k in ("status", "base_in", "new_24h_in", "season_in", "lifts_open")}}


def get(refresh=False):
    """Today's Daily Snow, generating it if needed. {"date", "text", "created"} or {"error"}."""
    today = util.today().isoformat()
    if not refresh:
        row = db.q("SELECT date, text, created FROM daily_snow WHERE date = ?", (today,))
        if row:
            return row[0]
    if not advisor.available():
        return {"error": "Connect Claude in Settings to get the Daily Snow."}
    with ThreadPoolExecutor(max_workers=4) as pool:
        data = [x for x in pool.map(_safe, resorts.load()) if x]
    text, error = advisor.complete(SYSTEM, f"Today is {today}.\nData:\n{json.dumps(data)}", timeout=600)
    if not text:
        return {"error": error or "Claude returned nothing."}
    created = util.now().strftime("%Y-%m-%d %H:%M")
    db.x("INSERT OR REPLACE INTO daily_snow(date, text, created) VALUES (?,?,?)", (today, text, created))
    return {"date": today, "text": text, "created": created}


def _safe(r):
    try:
        return _resort_data(r)
    except Exception:
        return None
