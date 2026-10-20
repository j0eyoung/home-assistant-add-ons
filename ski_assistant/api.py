"""API + single-page UI. Served through Home Assistant ingress on port 8099."""
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import accuracy
import advisor
import claudecode
import dailysnow
import db
import drive
import forecast
import garmin
import ha
import livestatus
import ranking
import resortinfo
import resorts
import scheduler
import season
import settings
import snotel
import traffic
import transit
import util

app = FastAPI(title="Ski Assistant")
STATIC = os.path.join(os.path.dirname(__file__), "static")
ALERT_IN = float(os.getenv("POWDER_ALERT_INCHES", "6"))


@app.on_event("startup")
def _startup():
    db.init()
    scheduler.start()
    garmin.start_background(on_new_today=_garmin_new_today)


def _garmin_new_today(activities):
    """A ride recorded on Garmin today: the boot and glove drying reminder."""
    r = garmin.nearest_resort(activities[0].get("startLatitude"), activities[0].get("startLongitude"))
    scheduler.drying_reminder(r["name"] if r else "the mountain")


# Conditions and planning
@app.get("/api/resorts")
def get_resorts():
    return resorts.load()


@app.put("/api/resorts")
def put_resorts(items: List[dict]):
    try:
        resorts.save(items)
    except (ValueError, OSError) as e:
        raise HTTPException(400, str(e))
    return resorts.load()


@app.get("/api/best-days")
def best_days(date: Optional[str] = None, skis: bool = False, departure: Optional[str] = None):
    return ranking.best_days(resorts.load(), date, skis=skis, departure=departure)


@app.get("/api/alerts")
def alerts():
    return ranking.powder_alerts(resorts.load(), threshold_in=ALERT_IN)


@app.get("/api/snowpack")
def snowpack_all():
    return {r["id"]: snotel.resort_snowpack(r) for r in resorts.load()}


@app.get("/api/live")
def live():
    return {r["id"]: livestatus.live_status(r) for r in resorts.load()}


@app.get("/api/transit")
def transit_all():
    return {r["id"]: transit.for_resort(r) for r in resorts.load()}


class Ask(BaseModel):
    question: str
    date: Optional[str] = None
    skis: bool = False
    departure: Optional[str] = None


@app.post("/api/ask")
def ask(a: Ask):
    if not advisor.available():
        raise HTTPException(400, "Connect Claude in Settings first.")
    try:
        return advisor.ask(a.question.strip()[:500], a.date, a.skis, a.departure)
    except Exception as e:
        raise HTTPException(502, f"Claude request failed: {e}")


@app.get("/api/briefing", response_class=PlainTextResponse)
def briefing():
    """Short plain-text summary for the Daily Briefing add-on."""
    rows = [r for r in ranking.best_days(resorts.load()) if "error" not in r]
    lines = []
    if rows:
        t = rows[0]
        lines.append(f"Best ski pick today: {t['resort']} ({t['fresh_in']} in fresh, high {round(t['tmax_f'])}F, "
                     f"gusts {round(t['gust_mph'])} mph). Leave by {t['leave']['leave_at']}.")
    for a in alerts():
        lines.append(f"Powder alert: {a['resort']} {a['snow_in']} in from {a['first_day']}.")
    return "\n".join(lines) or "No ski data right now."


# OpenSnow-style forecast
def _report(r):
    return {"snotel": snotel.resort_snowpack(r), "reported": livestatus.live_status(r)}


def _row(r):
    try:
        return {"id": r["id"], "name": r["name"], "pass": r.get("pass"), "summary": forecast.summary(r), **_report(r)}
    except Exception as e:
        return {"id": r["id"], "name": r["name"], "pass": r.get("pass"), "error": str(e)}


@app.get("/api/forecast")
def forecast_all():
    """Every resort's snow summary (last 5 days, next 15) and observed snow, fetched in parallel."""
    rs = resorts.load()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_row, rs))
    for row, r in zip(rows, rs):
        row["lat"], row["lon"] = r["lat"], r["lon"]
    return rows


@app.get("/api/resort/{resort_id}")
def resort_detail(resort_id: str, band: str = "mid", departure: Optional[str] = None):
    r = next((x for x in resorts.load() if x["id"] == resort_id), None)
    if not r:
        raise HTTPException(404, "unknown resort")
    if band not in forecast.BANDS:
        raise HTTPException(400, "band must be base, mid or summit")
    try:
        days = forecast.daily(r, band)
        hours = forecast.next48(r, band)
    except Exception as e:
        raise HTTPException(502, f"forecast failed: {e}")
    st = settings.load()
    today = util.today().isoformat()
    return {"resort": {k: r[k] for k in ("id", "name", "base_ft", "summit_ft", "lat", "lon")} | {"pass": r.get("pass")},
            "band": band, "elevations": forecast.band_ft(r), "models": list(forecast.MODELS.values()),
            "daily": days, "next48": hours, **_report(r),
            "info": resortinfo.info(r) | {"openskimap_url": resortinfo.openskimap_url(r)},
            "transit": transit.for_resort(r), "traffic": traffic.for_resort(r), "accuracy": accuracy.scores(r["id"]),
            "leave_today": drive.plan(r, settings.departure(departure), today, st["arrive_by"], st["buffer_min"])}


@app.get("/api/traffic")
def traffic_now():
    """Waze sensors found in Home Assistant, which resort each matches, I-70 corridor alerts and COtrip travel times."""
    sensors = traffic.waze_sensors()
    roads = sorted({x for r in resorts.load() for x in traffic.roads_for(r)})
    return {"waze_sensors": sensors, "waze": {r["id"]: traffic.waze_for(r, sensors) for r in resorts.load()},
            "cotrip": traffic.alerts(roads), "travel_times": traffic.travel_times()}


@app.get("/api/traffic/debug")
def traffic_debug():
    return traffic.debug()


@app.get("/api/daily-snow")
def daily_snow(refresh: bool = False):
    try:
        return dailysnow.get(refresh=refresh)
    except Exception as e:
        raise HTTPException(502, f"Daily Snow failed: {e}")


# Season log
class Day(BaseModel):
    date: str
    resort_id: str
    equipment: str  # board | ski
    vertical_ft: Optional[int] = None
    notes: str = ""


class Going(BaseModel):
    date: str
    resort_id: str
    skis: bool = False


@app.post("/api/going")
def going(g: Going):
    """'I'm going': puts the day's packing list on the Home Assistant to-do list."""
    db.x("INSERT OR IGNORE INTO plans(date, resort_id, created) VALUES (?,?,?)",
         (g.date, g.resort_id, util.now().strftime("%Y-%m-%d %H:%M")))
    if not ha.available():
        return {"added": [], "note": "Saved. The packing list goes to Home Assistant when the add-on runs there."}
    added = scheduler.packing_list(g.resort_id, g.date, skis=g.skis)
    return {"added": added, "note": f"{len(added)} items added to your list." if added else "Already on your list."}


@app.get("/api/stats")
def stats():
    return season.stats()


@app.get("/api/days")
def days():
    return season.list_days()


@app.post("/api/days")
def add_day(d: Day):
    if d.equipment not in ("board", "ski"):
        raise HTTPException(400, "equipment must be board or ski")
    new_id = season.add_day(d.date, d.resort_id, d.equipment, d.vertical_ft, d.notes)
    name = next((r["name"] for r in resorts.load() if r["id"] == d.resort_id), d.resort_id)
    if d.date == util.today().isoformat():
        scheduler.drying_reminder(name)
    return {"id": new_id}


class DayEquipment(BaseModel):
    equipment: str


@app.patch("/api/days/{day_id}")
def set_day_equipment(day_id: int, e: DayEquipment):
    if e.equipment not in ("board", "ski"):
        raise HTTPException(400, "equipment must be board or ski")
    season.set_equipment(day_id, e.equipment)
    return {"ok": True}


@app.delete("/api/days/{day_id}")
def delete_day(day_id: int):
    season.delete_day(day_id)
    return {"ok": True}


# Garmin import
class GarminLogin(BaseModel):
    email: str
    password: str


class GarminCode(BaseModel):
    code: str


@app.get("/api/garmin")
def garmin_state():
    return garmin.status()


@app.post("/api/garmin/connect")
def garmin_connect(g: GarminLogin):
    result = garmin.connect(g.email, g.password)
    if result["ok"] and not result["needs_mfa"]:
        garmin.sync()
    return {**result, **garmin.status()}


@app.post("/api/garmin/mfa")
def garmin_mfa(c: GarminCode):
    result = garmin.submit_mfa(c.code)
    if result["ok"]:
        garmin.sync()
    return {**result, **garmin.status()}


@app.post("/api/garmin/sync")
def garmin_sync():
    added, error, _ = garmin.sync()
    return {"added": added, "error": error, **garmin.status()}


@app.post("/api/garmin/disconnect")
def garmin_disconnect():
    garmin.disconnect()
    return garmin.status()


# Gear upkeep
class Service(BaseModel):
    date: str
    equipment: str
    kind: str  # wax | tune


@app.get("/api/gear")
def gear_upkeep():
    return season.upkeep()


@app.post("/api/gear")
def add_service(s: Service):
    if s.equipment not in ("board", "ski") or s.kind not in ("wax", "tune"):
        raise HTTPException(400, "equipment must be board or ski, kind wax or tune")
    return {"id": season.add_service(s.date, s.equipment, s.kind)}


class Shopping(BaseModel):
    item: str


@app.post("/api/shopping")
def shopping(s: Shopping):
    try:
        ha.shopping_add(s.item.strip()[:100])
    except Exception as e:
        raise HTTPException(502, f"Home Assistant shopping list failed: {e}")
    return {"ok": True}


# Settings
@app.get("/api/map")
def map_config():
    """Basemap for the Radar tab. A CARTO key (add-on option) is used by the browser to load its tiles."""
    return {"carto_key": os.getenv("CARTO_API_KEY", "")}


@app.get("/api/settings")
def get_settings():
    return {"settings": settings.load(), "phones": ha.notify_services() if ha.available() else [],
            "in_home_assistant": ha.available()}


@app.put("/api/settings")
def put_settings(patch: dict):
    try:
        return settings.save(patch)
    except OSError as e:
        raise HTTPException(400, str(e))


# Claude Code sign-in (same flow as the Workout Tracker)
@app.get("/api/claude")
def claude_state():
    return claudecode.login_state()


@app.post("/api/claude/login")
def claude_login():
    return claudecode.start_login()


class LoginCode(BaseModel):
    code: str


@app.post("/api/claude/code")
def claude_code(c: LoginCode):
    return claudecode.send_code(c.code)


@app.post("/api/claude/cancel")
def claude_cancel():
    return claudecode.cancel_login()


@app.post("/api/claude/logout")
def claude_logout():
    claudecode.logout()
    return claudecode.login_state()


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC), name="static")
