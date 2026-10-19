"""Add-on web server: the phone-first UI in static/ and the JSON API behind it, plus the
/workout endpoints Claude Terminal uses.

The UI is served through Home Assistant ingress under a per-install path prefix, so the
page only ever uses relative URLs (e.g. fetch("api/plan")).
"""
import datetime
import os
import random
import re
import sqlite3
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import coach
import garmin_sync
import ha
import history
import insights
import library
import media
import meditation
import mindbody
import ninjas_sync
import planedit
import planner
import progression
import readiness
import tts
from db import DB_PATH, get_last_log
import engine as engine_mod
from engine import WorkoutEngine
from exercises import CARDIO_IMAGES, GUIDES

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "0.10.2"

app = FastAPI(title="AI Workout Tracker")
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
engine = WorkoutEngine()

# --- Exercise library (kept in memory; refreshed so background API Ninjas additions show up) ----

_library = {"loaded_at": 0.0, "entries": [], "by_name": {}}
_library_lock = threading.Lock()


def get_library():
    with _library_lock:
        if time.time() - _library["loaded_at"] > 600:
            entries = library.get_library(DB_PATH)
            _library.update(loaded_at=time.time(), entries=entries, by_name={e["name"]: e for e in entries})
    return _library


def library_card(e, why=None):
    similar = (e["image_match"] or "").startswith("similar")
    dose, sets = library.dose_for(e)
    return {
        "name": e["name"], "dose": dose, "sets": sets, "why": why,
        "images": e["images"], "image_note": f"Picture shows a similar movement ({e['image_match'][9:]})." if similar else None,
        "steps": e["instructions"], "tips": e["tips"], "safe": e["safe"],
        "warning": None if e["safe"] else
        "Filtered out of your plans: " + "; ".join(library.FLAG_REASONS.get(f, f) for f in e["constraint_tags"]) + ".",
        "muscles": e["muscles"], "equipment": e["equipment"], "level": e["level"],
        "sources": [library.SOURCE_NAMES.get(s, s) for s in e["sources"]],
        "weighted": e["equipment"] not in WEIGHTLESS_EQUIPMENT and not is_hold(dose, e["name"]),
        "hold": is_hold(dose, e["name"]), "hold_secs": hold_secs(dose, e["name"]),
        "rest_secs": rest_secs(dose, is_hold(dose, e["name"])), "each_side": each_side(dose, e["name"], e.get("single_arm")),
    }


_EACH = re.compile(r"each (side|leg|arm)|per side", re.I)
_ONE_SIDED = re.compile(r"single|one[- ]?(arm|leg)|side|lunge|split|pigeon|figure[- ]?four|lizard|quad|hamstring|calf|"
                        r"hip flexor|piriformis|it band|clamshell|unilateral|alternating", re.I)


_CLEARLY_ONE_SIDED = re.compile(r"side plank|single[- ]leg|one[- ]leg|single[- ]arm|one[- ]arm|pigeon|figure[- ]?four", re.I)


def each_side(dose, name, single=False):
    """Done one side at a time (left, then right)? '...each side if one-sided' only counts for one-sided moves."""
    if not _EACH.search(dose or ""):
        return bool(_CLEARLY_ONE_SIDED.search(name or ""))
    return "if one-sided" not in (dose or "") or bool(single) or bool(_ONE_SIDED.search(name or ""))


_HOLD = re.compile(r"\bhold\b|\b\d+(?:-\d+)?\s*(?:s|sec|secs|seconds|min|mins)\b", re.I)


def is_hold(dose, name):
    """Timed holds (wall sits, planks, stretches): tracked as check marks, one per hold, not reps."""
    return bool(_HOLD.search(f"{dose or ''} {name}")) or any(w in name.lower() for w in ("plank", "wall sit"))


_SECS = re.compile(r"(\d+)(?:\s*-\s*\d+)?\s*(s|sec|secs|seconds|min|mins)\b", re.I)
_REST = re.compile(r"(\d+)\s*(?:s|sec|seconds)\s*rest", re.I)


def hold_secs(dose, name=""):
    """Starting length of one hold, from the dose text ("3 x 45 s" -> 45, "2 x 20-30 s hold" -> 20, "3 min" -> 180)."""
    m = _SECS.search(dose or "") or _SECS.search(name or "")
    if not m:
        return 30
    n = int(m.group(1))
    return n * 60 if m.group(2).lower().startswith("min") else n


def rest_secs(dose, hold=False):
    m = _REST.search(dose or "")
    return int(m.group(1)) if m else (45 if hold else 60)


# Equipment where you don't track pounds: bodyweight, bands (tension, not lbs), rings, sliders, and so on
WEIGHTLESS_EQUIPMENT = {"bodyweight", "bands", "stability ball", "foam roller", "pull-up bar", "suspension trainer",
                        "sliders", "rings", "cardio machine"}


PT_SECTIONS = ("warmup", "strength")


def pt_exercises():
    """Exercises Joe's PT gave him, added in Settings: [{name, dose, cues, days (0=Mon; empty = every day), section, sets}]."""
    return library.load_settings().get("pt_exercises") or []


def pt_for_day(d):
    return [p for p in pt_exercises() if not p.get("days") or d.weekday() in p["days"]]


def how_to(name, why=None):
    """Dose, pictures and steps for an exercise in today's plan."""
    pt = next((p for p in pt_exercises() if p["name"] == name), None)
    guide = {"dose": pt["dose"] or "As your PT showed you", "cues": pt.get("cues") or [], "sets": pt.get("sets") or 3} if pt \
        else GUIDES.get(name)
    if guide:
        return {"name": name, "dose": guide["dose"], "sets": guide.get("sets", 3), "why": why,
                "images": guide.get("images", []), "image_note": guide.get("image_note"),
                "steps": guide["cues"], "tips": [], "safe": True, "warning": None, "weighted": False,
                "hold": is_hold(guide["dose"], name), "hold_secs": hold_secs(guide["dose"], name),
                "rest_secs": rest_secs(guide["dose"], is_hold(guide["dose"], name)),
                "each_side": each_side(guide["dose"], name), "pt": bool(pt)}
    entry = get_library()["by_name"].get(name)
    if entry:
        return library_card(entry, why)
    return {"name": name, "dose": None, "sets": 3, "why": why, "images": [], "image_note": None,
            "steps": [], "tips": [], "safe": True, "warning": None}


SPORT_OPTIONS = [("skiing", "Skiing"), ("snowboarding", "Snowboarding"), ("triathlon", "Triathlon")]


def _season(today):
    """Snow-season phase for a snow sport you have ticked; None otherwise."""
    if not ({"skiing", "snowboarding"} & set(selected_sports())):
        return None
    return planner.season_info(today)


def selected_sports():
    chosen = library.load_settings().get("sports")
    return chosen if chosen is not None else ["skiing", "snowboarding", "triathlon"]


def current_log(date_iso=None):
    """The last logged workout's numbers, with this morning's check-in laid over them for today."""
    last = dict(get_last_log())
    if date_iso in (None, history.local_today()):
        ck = history.get_checkin(DB_PATH)
        if ck:
            last["kidney_flank_pain"], last["pelvic_floor_tightness"] = ck["kidney"], ck["pelvic_floor"]
    return last


# --- "Bothered me": an exercise sits out for a while, then comes back with a reminder to go lighter ----------------

PAUSE_DAYS = 14
BACK_NOTE_DAYS = 14


def paused(date_iso=None):
    """{name: {"since", "until"}} for exercises sitting out on this date."""
    d = date_iso or history.local_today()
    return {n: p for n, p in (library.load_settings().get("paused") or {}).items() if p["until"] >= d}


def recently_back(date_iso=None):
    """Exercises whose pause ended in the last two weeks: {name: since}."""
    d = datetime.date.fromisoformat(date_iso or history.local_today())
    out = {}
    for n, p in (library.load_settings().get("paused") or {}).items():
        until = datetime.date.fromisoformat(p["until"])
        if until < d <= until + datetime.timedelta(days=BACK_NOTE_DAYS):
            out[n] = p["since"]
    return out


def _drop_paused(ops):
    """Removes 'add' changes for paused exercises: (kept ops, reasons)."""
    resting = paused()
    lower = {n.lower(): (n, p) for n, p in resting.items()}
    st = readiness.status()
    kept, why = [], []
    for op in ops:
        hit = lower.get(str(op.get("name") or "").strip().lower()) if op.get("op") == "add" else None
        machine = op.get("type") if op.get("op") in ("cardio", "extra_cardio", "day") else None
        if hit:
            why.append(f"{hit[0]} is paused until {datetime.date.fromisoformat(hit[1]['until']):%b %d} because it bothered you.")
        elif machine in st and not st[machine]["ok"]:
            why.append(f"The {st[machine]['name']} isn't unlocked yet: {st[machine]['why']}")
        else:
            kept.append(op)
    return kept, why


def garmin_today(date_iso=None):
    """Garmin-driven lighter day for today, if the switch is on in Settings (it is off by default)."""
    today = history.local_today()
    if (date_iso or today) != today or not library.load_settings().get("garmin_adjust"):
        return {"level": None, "reasons": []}
    return garmin_sync.recovery_signal(today)


def _generate(date_iso):
    """The engine's workout for a date, following that day's place in the weekly plan."""
    goals = selected_sports()
    d = datetime.date.fromisoformat(date_iso)
    day = planner.day_plan(d, goals)
    resting = paused(date_iso)
    entries = [e for e in get_library()["entries"] if e["name"] not in resting]
    gsig = garmin_today(date_iso)
    focus = "recovery" if gsig["level"] == "recovery" and day["focus"] in ("strength", "cardio") else day["focus"]
    w = engine.generate_next_workout(
        current_log(date_iso), today=d, library=entries, equipment=library.selected_equipment(),
        goals=goals, focus=focus, cardio_type=day["cardio_type"], theme=day["theme"],
        season_phase=day.get("season_phase"))
    if gsig["level"] == "lighter" and w.get("cardio_type") != "recovery":
        # Garmin says go lighter: one fewer extra and about a quarter less cardio
        if w.get("accessories"):
            last = w["accessories"].pop()
            if last["name"] in w["strength"]:
                w["strength"].remove(last["name"])
        if w.get("cardio_minutes"):
            w = planedit.apply(w, [{"op": "cardio", "type": w["cardio_type"],
                                    "minutes": max(10, int(w["cardio_minutes"] * 0.75 / 5) * 5),
                                    "why": "lighter day from your Garmin data"}])
    # Your PT's exercises for this weekday: daily ones join the non-negotiables, the rest go with strength
    for p in pt_for_day(d):
        if p.get("section") == "strength":
            if p["name"] not in w["strength"]:
                w["strength"] = w["strength"] + [p["name"]]
        elif p["name"] not in w["warmup"]:
            w["warmup"] = w["warmup"] + [p["name"]]
    if resting:   # the fixed exercises (wall sits and so on) sit out too
        w["strength"] = [n for n in w["strength"] if n not in resting]
        w["accessories"] = [a for a in w.get("accessories", []) if a["name"] not in resting]
    if day["phase"] == "Easy week" and day["focus"] == "strength" and w.get("accessories"):
        last = w["accessories"].pop()          # easy week: one fewer extra
        if last["name"] in w["strength"]:
            w["strength"].remove(last["name"])
    if day.get("cardio_minutes") and w.get("cardio_type") != "recovery":
        # minutes the coach put in the week: never more than 10 above what progression allows
        minutes = min(int(day["cardio_minutes"]), (w.get("cardio_minutes") or 0) + 10)
        w = planedit.apply(w, [{"op": "cardio", "type": w["cardio_type"], "minutes": minutes, "why": "weekly plan"}])
    return w


def todays_workout():
    today = history.local_today()
    return planedit.apply(_generate(today), planedit.overrides_for(today))


# --- Draft rows: the page uses {exercise, set, weight, reps, done}; 0.2.x drafts used table headers ---

def _page_row(r):
    if "exercise" in r:
        return r
    return {"exercise": r.get("Exercise"), "set": r.get("Set"), "weight": r.get("Weight (lbs)"),
            "reps": r.get("Reps"), "done": bool(r.get("Done"))}


def _history_row(r):
    return {"Exercise": r.get("exercise"), "Set": r.get("set"), "Weight (lbs)": r.get("weight"),
            "Reps": r.get("reps"), "Done": bool(r.get("done"))}


# --- Pages and API ---------------------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"), headers={"Cache-Control": "no-cache"})


def with_progress(card, last, phase):
    """Adds last time's sets and a suggested weight and reps to an exercise card."""
    back = recently_back()
    if card["name"] in back:
        card["bothered"] = (f"This bothered you on {datetime.date.fromisoformat(back[card['name']]):%b %d} and sat out for a while. "
                            "Go lighter today, and tap 'Bothered me' again if it still does.")
    date, sets = history.last_session(DB_PATH, card["name"])
    suggest = progression.suggest_hold if card.get("hold") else progression.suggest
    card["progress"] = suggest(date, sets, phase, last.get("rpe"), last.get("kidney_flank_pain"),
                               last.get("pelvic_floor_tightness"))
    if card["progress"]:
        card["progress"]["sets"] = sets                   # last time's sets, for "Same as last time"
    if card.get("hold") and card["progress"]:
        card["hold_secs"] = card["progress"]["secs"]      # today's target, a little longer than last time
    return card


def _cooldown_for(w, last, today):
    """Today's cool-down cards and the day type they follow (used by the plan and the guided cool-down)."""
    kidney, pf = last.get("kidney_flank_pain"), last.get("pelvic_floor_tightness")
    day_focus = planner.day_plan(datetime.date.fromisoformat(today), selected_sports())["focus"]
    if w.get("cardio_type") == "recovery":
        day_focus = "recovery"                     # a high kidney score turns any day into recovery
    cards = mindbody.cooldown(kidney, pf, focus=day_focus, day=today, equipment=library.selected_equipment())
    return day_focus, cards


@app.get("/api/plan")
def plan():
    today = history.local_today()
    w = todays_workout()
    why = {a["name"]: a["why"] for a in w.get("accessories", [])}
    draft = history.load_draft(DB_PATH, today) or {}
    last = current_log(today)
    kidney, pf = last.get("kidney_flank_pain"), last.get("pelvic_floor_tightness")
    phase = planner.phase(datetime.date.fromisoformat(today))
    equipment = library.selected_equipment()
    day_focus, cool_cards = _cooldown_for(w, last, today)
    warmup_cards = [how_to(n) for n in w["warmup"]]
    # Vibration board primer on strength days (fine at any symptom level, short and lowest setting)
    if day_focus == "strength":
        warmup_cards += mindbody.tool_cards(equipment, "warmup")
    for c in warmup_cards:   # timed openers (2 min breathing, vibration board) get a timer on their card
        if "hold" not in c:
            c["hold"], c["hold_secs"] = is_hold(c.get("dose"), c["name"]), hold_secs(c.get("dose"), c["name"])
    season = _season(datetime.date.fromisoformat(today))
    if season and season["phase"] in ("Taper", "Opening day"):
        phase = "Easy week"          # opening week: hold loads, one set fewer
    gsig = garmin_today(today)
    if gsig["level"]:
        phase = "Easy week"          # Garmin says go lighter: hold loads, one set fewer
    return {
        "garmin": gsig,
        "season": season,
        # a ski readiness check every two weeks until opening day
        "at_pt": _pt_here["inside"],
        "bio": {k: v for k, v in insights.bio_status(DB_PATH, datetime.date.fromisoformat(today)).items()
                if k in ("due", "last", "next", "enabled")},
        "ski_due": bool(season and season.get("days", 0) > 0 and insights.ski_status(DB_PATH, datetime.date.fromisoformat(today))["due"]),
        "phase": phase,
        "coach_changes": len(planedit.overrides_for(today)),
        "checkin": history.get_checkin(DB_PATH, today),
        "snow_today": history.snow_days(DB_PATH, 5).get(today),
        "snow_sport": bool({"skiing", "snowboarding"} & set(selected_sports())),
        "last_scores": {"kidney": last.get("kidney_flank_pain"), "pelvic_floor": last.get("pelvic_floor_tightness")},
        "cooldown": {"note": mindbody.cooldown_note(kidney, pf, day_focus, cool_cards), "cards": cool_cards,
                     "title": {"cardio": "Qigong cool-down", "recovery": "Recovery wind-down", "rest": "Recovery wind-down"}.get(day_focus, "Cool-down")},
        "date": today,
        "warmup": warmup_cards,
        "strength": [with_progress(how_to(n, why.get(n)), last, phase) for n in w["strength"]],
        "cardio": {"text": w["cardio"], "minutes": w.get("cardio_minutes"), "note": w.get("cardio_note"),
                   "type": w.get("cardio_type"), "images": CARDIO_IMAGES.get(w.get("cardio_type"), [])},
        "extra_cardio": w.get("extra_cardio"),
        "session2": planedit.session2_names(today),
        "done": _done_today(today),
        "draft": {"tracker": [_page_row(r) for r in draft.get("tracker", [])], "checks": draft.get("checks", {})},
    }


class Draft(BaseModel):
    date: str
    tracker: list[dict] = []
    checks: dict[str, bool] = {}


@app.put("/api/draft")
def save_draft(d: Draft):
    if d.date != history.local_today():
        raise HTTPException(409, "A new day has started; reload the plan.")
    history.save_draft(DB_PATH, d.tracker, d.checks, d.date)
    return {"ok": True}


class Completion(BaseModel):
    rpe: int
    pelvic_floor: int
    kidney: int
    notes: str = ""
    tracker: list[dict] = []
    checks: dict[str, bool] = {}   # daily non-negotiables ticked today
    session: int = 1          # 2 = the second session of the day, logged on its own


def _records(log_id, names):
    """Personal records set by a just-saved workout, kept in its History entry."""
    holds = {n for n in names if how_to(n).get("hold")}
    prs = insights.personal_records(DB_PATH, log_id, holds)
    if prs:
        history.update_workout(DB_PATH, log_id, prs=prs)
    return prs


@app.post("/api/complete")
def complete(c: Completion):
    today = history.local_today()
    w = todays_workout()
    names2 = set(planedit.session2_names(today))
    if str(c.session) in _done_today(today):
        raise HTTPException(409, "Already logged today.")
    if c.session == 2:
        w2 = {"session": 2, "strength": [n for n in w["strength"] if n in names2], "extra_cardio": w.get("extra_cardio"),
              "cardio_type": (w.get("extra_cardio") or {}).get("type"), "cardio_minutes": (w.get("extra_cardio") or {}).get("minutes"),
              "cardio": (f"{w['extra_cardio']['minutes']} min easy {w['extra_cardio']['type']}: {w['extra_cardio']['text']}"
                         if w.get("extra_cardio") else "")}
        rows = [r for r in c.tracker if _page_row(r).get("exercise") in names2]
        log_id = history.complete_workout(DB_PATH, c.rpe, c.pelvic_floor, c.kidney, c.notes, w2,
                                          [_history_row(_page_row(r)) for r in rows])
        prs = _records(log_id, {_page_row(r).get("exercise") for r in rows})
        _ha_refresh_soon()
        return {"ok": True, "log_id": log_id, "prs": prs}
    # First session: log everything except the second session, and keep the second session's sets in the draft
    first = dict(w, strength=[n for n in w["strength"] if n not in names2])
    first.pop("extra_cardio", None)
    first["accessories"] = [a for a in first.get("accessories", []) if a["name"] not in names2]
    checks = c.checks or (history.load_draft(DB_PATH, today) or {}).get("checks") or {}
    first["warmup_done"] = [n for n in w.get("warmup", []) if checks.get(n)]
    first["day_type"] = insights.day_type(first, today, selected_sports())
    mine = [r for r in c.tracker if _page_row(r).get("exercise") not in names2]
    kept = [r for r in c.tracker if _page_row(r).get("exercise") in names2]
    log_id = history.complete_workout(DB_PATH, c.rpe, c.pelvic_floor, c.kidney, c.notes, first,
                                      [_history_row(_page_row(r)) for r in mine])
    if kept:
        history.save_draft(DB_PATH, kept, {}, today)
    prs = _records(log_id, {_page_row(r).get("exercise") for r in mine})
    _ha_refresh_soon()
    return {"ok": True, "log_id": log_id, "prs": prs}


@app.get("/api/history")
def workout_history(limit: int = 60):
    return {"workouts": history.get_history(DB_PATH, limit), "exercises": history.logged_exercises(DB_PATH)}


@app.get("/api/progress")
def progress(exercise: str):
    return {"exercise": exercise, "days": history.exercise_progress(DB_PATH, exercise)}


@app.get("/api/trends")
def symptom_trends(days: int = 30):
    """Kidney and pelvic floor scores by day with workout effort, and the patterns in them."""
    return insights.trends(DB_PATH, max(7, min(days, 120)), datetime.date.fromisoformat(history.local_today()),
                           selected_sports())


@app.get("/api/biofeedback")
def biofeedback():
    """Manometric biofeedback sessions with the pelvic PT, and whether the next one is due to be logged."""
    return insights.bio_status(DB_PATH, datetime.date.fromisoformat(history.local_today()))


class BioSession(BaseModel):
    date: str
    values: dict[str, float | None] = {}
    notes: str = ""


@app.post("/api/biofeedback")
def save_biofeedback(b: BioSession):
    try:
        d = datetime.date.fromisoformat(b.date)
    except ValueError:
        raise HTTPException(400, "The date must look like 2026-10-19.")
    if d > datetime.date.fromisoformat(history.local_today()):
        raise HTTPException(400, "That date is in the future.")
    if not insights.save_bio(DB_PATH, d.isoformat(), b.values, b.notes, insights.bio_settings()["unit"]):
        raise HTTPException(400, "Enter at least one reading or a note.")
    return biofeedback()


@app.delete("/api/biofeedback/{date}")
def delete_biofeedback(date: str):
    insights.delete_bio(DB_PATH, date)
    return biofeedback()


class Snooze(BaseModel):
    days: int = 3


@app.post("/api/biofeedback/snooze")
def snooze_biofeedback(s: Snooze):
    until = datetime.date.fromisoformat(history.local_today()) + datetime.timedelta(days=max(1, min(s.days, 14)))
    library.save_settings({"biofeedback": {**(library.load_settings().get("biofeedback") or {}), "snooze_until": until.isoformat()}})
    return biofeedback()


@app.get("/api/report/pt")
def pt_visit_report(days: int = 30):
    """Everything to show the PT at a visit, for the last 14 to 90 days."""
    today = datetime.date.fromisoformat(history.local_today())
    warmups = engine_mod.DAILY_WARMUP +[p["name"] for p in pt_exercises() if p.get("section") != "strength"]
    return insights.pt_report(DB_PATH, max(7, min(days, 90)), today, selected_sports(), list(dict.fromkeys(warmups)),
                              lambda n: bool(how_to(n).get("hold")))


@app.get("/api/skitests")
def ski_tests():
    return insights.ski_status(DB_PATH, datetime.date.fromisoformat(history.local_today()))


class SkiResults(BaseModel):
    values: dict[str, float | None]


@app.post("/api/skitests")
def save_ski_tests(r: SkiResults):
    n = insights.save_ski_results(DB_PATH, r.values, history.local_today())
    if not n:
        raise HTTPException(400, "Enter at least one result.")
    return ski_tests()


@app.get("/api/install")
def install_info():
    """The add-on's own address on the home network, for adding it to the phone's home screen."""
    return ha.direct_address()


@app.get("/sw.js")
def service_worker():
    # Served from the root so it can cover the whole app when it's opened at its own address
    return FileResponse(os.path.join(HERE, "static", "sw.js"), media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})


@app.get("/api/library")
def search_library(q: str = "", focus: str = "", muscle: str = "", equipment: str = "",
                   pictures: bool = True, filtered: bool = False, offset: int = 0, limit: int = 25):
    entries = get_library()["entries"]
    words = q.lower().split()
    results = [
        e for e in entries
        if (filtered or e["safe"]) and (not pictures or e["images"])
        and all(w in e["name"].lower() for w in words)
        and (not focus or focus in e["goal_tags"])
        and (not muscle or muscle in e["muscles"])
        and (not equipment or e["equipment"] == equipment)
    ]
    return {
        "total": len(results), "all": len(entries), "safe": sum(e["safe"] for e in entries),
        "results": [library_card(e) for e in results[offset:offset + limit]],
        "muscles": sorted({m for e in entries for m in e["muscles"]}),
        "equipment": sorted({e["equipment"] for e in entries}),
    }


@app.get("/api/status")
def status():
    return {"version": VERSION, "claude_token": coach.has_token(), "ninjas": ninjas_sync.status(),
            "credits": library.CREDITS}


class CoachMessage(BaseModel):
    message: str
    recent: list[dict] = []


@app.post("/api/coach")
def ask_coach(m: CoachMessage):
    plan = todays_workout()
    lib = get_library()
    today = datetime.date.fromisoformat(history.local_today())
    ck = history.get_checkin(DB_PATH)
    ck_line = (f"TODAY'S MORNING CHECK-IN (Joe's own scores, 1-10): left kidney/flank {ck['kidney']}, pelvic floor tightness "
               f"{ck['pelvic_floor']}. Use these for today.") if ck else "No morning check-in yet today."
    resting = paused()
    pause_line = ("PAUSED EXERCISES (they bothered Joe; do not suggest them until the date): " +
                  "; ".join(f"{n} until {p['until']}" for n, p in resting.items())) if resting else ""
    st = readiness.status()
    pause_line += ("\nCARDIO MACHINES (cardio type 'bike' = Peloton, 'row' = water rower; only suggest unlocked ones): " +
                   "; ".join(f"{v['name']}: {'unlocked, ' + str(v['minutes']) + ' min max' if v['ok'] else 'locked. ' + v['why']}"
                             for v in st.values()))
    entries = [e for e in lib["entries"] if e["name"] not in resting]
    context = "\n\n".join(x for x in [planedit.INSTRUCTIONS, ck_line, pause_line,
                                      planedit.context(plan, entries, library.selected_equipment(), selected_sports()),
                                      planedit.week_context(today, selected_sports())] if x)
    info = _season(today)
    season_text = (f"{info['opening']} ({info['days']} days away)" if info["days"] > 0 else f"{info['opening']} (it has opened)") + \
        f". Phase: {info['phase']}: {info['text']}" if info else ""
    reply, error = coach.ask(m.message, m.recent, plan_context=context, season=season_text, sports=selected_sports())
    reply, data = planedit.extract(reply)
    ops, pause_rejects = _drop_paused((data or {}).get("changes") or [])
    changes, rejected = planedit.validate({"changes": [c for c in ops if c.get("op") != "day"]}, plan, lib["by_name"],
                                          library.selected_equipment())
    rejected = pause_rejects + rejected
    days, days_bad = planedit.validate_days([c for c in ops if c.get("op") == "day"], today, selected_sports())
    return {"reply": reply, "error": error, "rejected": rejected + days_bad,
            "changes": [dict(c, label=planedit.label(c)) for c in changes + days]}


class PlanChanges(BaseModel):
    changes: list[dict]


@app.post("/api/plan/changes")
def apply_changes(p: PlanChanges):
    """Joe approved the coach's changes. Checked again here, so only valid ones are ever saved."""
    lib = get_library()
    today = history.local_today()
    plan = planedit.apply(_generate(today), planedit.overrides_for(today))
    ops, pause_rejects = _drop_paused(p.changes)
    day_ops = [c for c in ops if c.get("op") == "day"]
    allowed, rejected = planedit.validate({"changes": [c for c in ops if c.get("op") != "day"]}, plan,
                                          lib["by_name"], library.selected_equipment())
    rejected = pause_rejects + rejected
    days_ok, days_bad = planedit.validate_days(day_ops, datetime.date.fromisoformat(today), selected_sports())
    if allowed:
        planedit.save(today, allowed)
    if days_ok:
        planner.save_changes(days_ok)
    return {"ok": True, "applied": len(allowed) + len(days_ok), "rejected": rejected + days_bad}


@app.get("/api/week")
def get_week(offset: int = 0):
    """The week (Monday to Sunday). offset 0 = this week, 1 = next week."""
    today = datetime.date.fromisoformat(history.local_today())
    start = planner.monday(today) + datetime.timedelta(days=7 * max(-1, min(offset, 2)))
    goals = selected_sports()
    done = {w["date"] for w in history.get_history(DB_PATH, 60) if (w.get("workout") or {}).get("session") != 2}
    days = planner.week(start, today, goals, done)
    snow = history.snow_days(DB_PATH, 60)
    for day in days:
        if day["date"] in snow:
            day["label"] = "Snow day: " + snow[day["date"]]
    rp = planner.replan_map(goals) if offset == 0 else {}
    replan = None
    if rp:
        names = {"core": "core activation", "legs": "legs", "back": "back and posture", "hips": "hips and balance", "full": "full body"}
        replan = {"missed": [names[t] for t in rp["missed"]], "dropped": [names[t] for t in rp["dropped"]]}
    for day in days:
        if day["status"] in ("today", "upcoming") and day["focus"] in ("strength", "cardio"):
            w = _generate(day["date"])
            day["strength"] = [n for n in w["strength"]] if day["focus"] == "strength" else []
            day["cardio_text"] = f"{w['cardio_minutes']} min {w['cardio_type']}" if day["focus"] != "rest" else None
    season = library.load_settings().get("season_start") or ""
    weeks_left = None
    if season:
        try:
            weeks_left = max(0, (datetime.date.fromisoformat(season) - today).days // 7)
        except ValueError:
            pass
    return {"start": start.isoformat(), "offset": offset, "days": days, "sports": goals, "phase": planner.phase(start),
            "season": _season(today), "replan": replan, "machines": readiness.status(today),
            "season_start": season, "weeks_to_season": weeks_left}


@app.post("/api/week/reset")
def reset_week():
    planner.clear_week(planner.monday(datetime.date.fromisoformat(history.local_today())))
    return {"ok": True}


class SecondSession(BaseModel):
    kind: str                # strength | core | mobility | cardio
    minutes: int = 20


@app.post("/api/plan/session2")
def add_second_session(s: SecondSession):
    """A second workout on request: built from the same safe library, checked like the coach's changes."""
    lib = get_library()
    equipment = library.selected_equipment()
    today = datetime.date.fromisoformat(history.local_today())
    plan = planedit.apply(_generate(today.isoformat()), planedit.overrides_for(today.isoformat()))
    last = current_log(today.isoformat())
    pf = last.get("pelvic_floor_tightness") or 1
    recovery = plan.get("cardio_type") == "recovery"
    if s.kind not in ("strength", "core", "mobility", "cardio"):
        raise HTTPException(400, "Choose strength, core, mobility or cardio.")
    if recovery and s.kind == "strength":
        return {"ok": False, "message": "Today is a recovery day, so a second strength session isn't added. Core, mobility or an easy walk work."}

    changes = []
    if s.kind == "cardio":
        ctype = "swim" if ("triathlon" in selected_sports() and pf >= 7) else ("walk" if recovery or pf >= 7 else "bike")
        changes.append({"op": "extra_cardio", "type": ctype, "minutes": max(5, min(s.minutes, 30)), "why": "easy, later in the day"})
    else:
        if s.kind == "strength":
            used = planner.day_plan(today, selected_sports()).get("theme")
            theme = next(t for t in ("legs", "back", "hips", "core") if t != used)
            slots = engine_mod.theme_slots(theme, selected_sports())[:4]
            label = {"legs": "legs", "back": "back and posture", "hips": "hips and balance", "core": "core"}[theme]
        elif s.kind == "core":
            slots = engine_mod.THEME_SLOTS["core"]
            label = "core"
        else:
            slots = [("mobility", "Hip and spine mobility"), ("mobility", "Rib and pelvic mobility")]
            label = "mobility"
        resting = paused()
        picks = engine_mod.pick_accessories([e for e in lib["entries"] if e["name"] not in resting],
                                            set(equipment) | {"bodyweight"}, today, recovery,
                                            set(plan["strength"]), selected_sports(), slots=slots, seed="session2")
        changes = [{"op": "add", "name": p["name"], "why": f"second session, {label}"} for p in picks]
    allowed, rejected = planedit.validate({"changes": changes}, plan, lib["by_name"], equipment)
    if allowed:
        planedit.save(today.isoformat(), allowed)
    return {"ok": bool(allowed), "added": len(allowed), "rejected": rejected,
            "message": None if allowed else "Nothing safe could be added with your equipment."}


_GUIDE_GOALS = {"Wall Sits (45s)": "legs", "Banded Lateral Walks": "legs", "Wall Tibialis Raises": "legs",
                "Supine Heel Slides": "core", "Wall-Push Deadbugs": "core"}


class SwapRequest(BaseModel):
    name: str


@app.post("/api/plan/swap")
def swap_exercise(s: SwapRequest):
    """A different safe exercise for the same muscle group, for today only."""
    lib = get_library()
    today = history.local_today()
    plan = planedit.apply(_generate(today), planedit.overrides_for(today))
    if s.name not in plan["strength"]:
        raise HTTPException(404, "That exercise isn't in today's plan.")
    entry = lib["by_name"].get(s.name)
    goals = [g for g in (entry["goal_tags"] if entry else []) if g in ("legs", "core", "upper back", "mobility", "balance")]
    goal = goals[0] if goals else _GUIDE_GOALS.get(s.name, "core")
    equipment = set(library.selected_equipment()) | {"bodyweight"}
    resting = paused()
    pool = [e for e in lib["entries"] if e["safe"] and goal in e["goal_tags"] and e["equipment"] in equipment
            and e["name"] not in plan["strength"] and e["name"] not in resting and e["name"] != s.name]
    if goal == "core":
        pool = [e for e in pool if e["level"] == "beginner"] or pool   # stay gentle with the deep core
    pool = [e for e in pool if e["images"] and e["instructions"]] or pool
    if not pool:
        return {"ok": False, "message": "No other safe exercise for that muscle group with your equipment."}
    pick = random.choice(pool)
    changes = [{"op": "remove", "name": s.name, "why": f"swapped for {pick['name']}"},
               {"op": "add", "name": pick["name"], "why": f"swapped in for {s.name}"}]
    allowed, rejected = planedit.validate({"changes": changes}, plan, lib["by_name"], library.selected_equipment())
    if len(allowed) < 2:
        return {"ok": False, "message": rejected[0] if rejected else "Couldn't swap that one."}
    planedit.save(today, allowed)
    return {"ok": True, "name": pick["name"]}


class PauseRequest(BaseModel):
    name: str
    days: int = PAUSE_DAYS


@app.post("/api/exercise/pause")
def pause_exercise(p: PauseRequest):
    """'Bothered me': the exercise sits out for a while (not forever), then returns with a go-lighter note."""
    today = datetime.date.fromisoformat(history.local_today())
    days = max(1, min(p.days, 60))
    all_p = library.load_settings().get("paused") or {}
    all_p[p.name.strip()[:120]] = {"since": today.isoformat(), "until": (today + datetime.timedelta(days=days - 1)).isoformat()}
    library.save_settings({"paused": all_p})
    return {"ok": True, "until": all_p[p.name.strip()[:120]]["until"]}


@app.post("/api/exercise/unpause")
def unpause_exercise(p: PauseRequest):
    all_p = library.load_settings().get("paused") or {}
    all_p.pop(p.name, None)
    library.save_settings({"paused": all_p})
    return {"ok": True}


class CheckIn(BaseModel):
    kidney: int
    pelvic_floor: int


@app.post("/api/checkin")
def save_checkin(c: CheckIn):
    """This morning's flank and pelvic floor scores. Today's plan is built from these instead of last session's."""
    history.save_checkin(DB_PATH, c.kidney, c.pelvic_floor)
    _ha_refresh_soon()
    return {"ok": True, "checkin": history.get_checkin(DB_PATH)}


@app.post("/api/plan/reset")
def reset_changes():
    planedit.clear(history.local_today())
    return {"ok": True}


def _done_today(today):
    """Today's logged sessions ("1" and/or "2") with a short summary for the Today page."""
    done = {}
    for w in history.get_history(DB_PATH, 10):
        if w["date"] != today:
            continue
        key = "2" if (w.get("workout") or {}).get("session") == 2 else "1"
        if key in done:
            continue
        sets = [s for s in w["sets"] if s.get("done")]
        done[key] = {"rpe": w.get("rpe"), "sets": len(sets), "exercises": len({s["exercise"] for s in sets}),
                     "minutes": (w.get("workout") or {}).get("cardio_minutes"),
                     "prs": (w.get("workout") or {}).get("prs", [])}
    return done


def _logged_dates():
    """Dates with a logged first session (a second session on its own doesn't count as that day's workout)."""
    return {w["date"] for w in history.get_history(DB_PATH, 30) if (w.get("workout") or {}).get("session") != 2}


planner.set_context(lambda: datetime.date.fromisoformat(history.local_today()), _logged_dates,
                    lambda: set(history.snow_days(DB_PATH, 30)), readiness.status)


class MachineOverride(BaseModel):
    machine: str      # bike | row
    value: str        # auto | cleared | not_yet


@app.post("/api/machines")
def set_machine_override(m: MachineOverride):
    if m.machine not in readiness.MACHINES or m.value not in readiness.OVERRIDES:
        raise HTTPException(400, "Unknown machine or setting.")
    ov = library.load_settings().get("machine_override") or {}
    ov[m.machine] = m.value
    library.save_settings({"machine_override": ov})
    planner._ctx["mcache"] = (0.0, None)
    return readiness.status()


@app.get("/api/machines")
def get_machines():
    return readiness.status()


class SnowDay(BaseModel):
    sport: str                 # skiing | snowboarding
    hours: float = 3
    rpe: int = 6
    kidney: int = 1
    pelvic_floor: int = 1
    notes: str = ""


@app.post("/api/snowday")
def log_snow_day(s: SnowDay):
    """A day on the slopes counts as that day's workout (legs and cardio); tomorrow's legs get a break."""
    if s.sport not in ("skiing", "snowboarding"):
        raise HTTPException(400, "Choose skiing or snowboarding.")
    today = history.local_today()
    hours = max(0.5, min(float(s.hours), 12))
    workout = {"type": "snow", "sport": s.sport, "hours": hours, "strength": [],
               "cardio": f"{hours:g} h {s.sport}", "cardio_type": "snow", "cardio_minutes": int(hours * 60)}
    draft = history.load_draft(DB_PATH, today)       # keep anything already typed in today's gym workout
    log_id = history.complete_workout(DB_PATH, s.rpe, s.pelvic_floor, s.kidney, s.notes, workout, [])
    if draft:
        history.save_draft(DB_PATH, draft.get("tracker", []), draft.get("checks", {}), today)
    _ha_refresh_soon()
    return {"ok": True, "log_id": log_id}


@app.on_event("startup")
def _start_garmin_sync():
    garmin_sync.start_background(history.local_today)


# --- Home Assistant: sensors and the morning reminder --------------------------------------------------------------

def streak():
    """Days in a row with a logged workout. Planned rest days don't break it; today counts once it's logged."""
    logged = {w["date"] for w in history.get_history(DB_PATH, 400)}
    d = datetime.date.fromisoformat(history.local_today())
    if d.isoformat() not in logged:
        d -= datetime.timedelta(days=1)
    n = 0
    for _ in range(365):
        if d.isoformat() in logged:
            n += 1
        elif planner.day_plan(d, selected_sports())["focus"] != "rest":
            break
        d -= datetime.timedelta(days=1)
    return n


def ha_refresh():
    """Pushes today's workout and the streak to Home Assistant (sensor.workout_today, sensor.workout_streak)."""
    if not ha.available():
        return
    today = history.local_today()
    w = todays_workout()
    day = planner.day_plan(datetime.date.fromisoformat(today), selected_sports())
    done = today in _logged_dates()
    if done:
        state = "Done"
    elif w.get("cardio_type") == "recovery" or day["focus"] in ("rest", "recovery"):
        state = "Rest day" if day["focus"] == "rest" else "Recovery day"
    elif day["focus"] == "cardio":
        state = f"Cardio: {w.get('cardio_minutes')} min {w.get('cardio_type')}"
    else:
        state = f"Strength: {day.get('theme_label') or 'strength'}"
    ha.set_state("sensor.workout_today", state, {
        "friendly_name": "Today's workout", "icon": "mdi:dumbbell", "done": done,
        "checked_in": bool(history.get_checkin(DB_PATH)), "exercises": w.get("strength", []), "cardio": w.get("cardio", "")})
    n = streak()
    ha.set_state("sensor.workout_streak", n, {"friendly_name": "Workout streak", "icon": "mdi:fire",
                                              "unit_of_measurement": "days"})


def _ha_refresh_soon():
    threading.Thread(target=lambda: _quietly(ha_refresh), daemon=True).start()


def _quietly(fn):
    try:
        fn()
    except Exception as e:
        print(f"Home Assistant update failed: {e}", flush=True)


def _maybe_remind():
    r = library.load_settings().get("reminder") or {}
    if not (r.get("enabled") and r.get("service") and ha.available()):
        return
    now = history.local_now()
    today = now.date().isoformat()
    if r.get("sent") == today or now.strftime("%H:%M") < r.get("time", "07:30"):
        return
    if history.get_checkin(DB_PATH) or today in _logged_dates():
        return
    ha.notify(r["service"], "How do you feel today?",
              "Tap to check in your kidney and pelvic floor scores. Today's plan adapts to them.")
    library.save_settings({"reminder": {**r, "sent": today}})


# --- At the PT office: when your phone enters the PT zone, a reminder to ask about new exercises ---------------------

_pt_here = {"inside": False}


def _pt_message():
    names = [p["name"] for p in pt_exercises()]
    msg = "Ask your PT if there are any new exercises, or changes to the ones you do. Add them in Settings › From your PT."
    if names:
        msg += " You're doing now: " + ", ".join(names[:6]) + ("…" if len(names) > 6 else "") + "."
    if insights.bio_settings()["enabled"]:
        msg += " Biofeedback today? Log the readings after."
    return msg


def _maybe_pt_visit():
    """Checked every minute: the first time today the phone is at the PT office, send the reminder."""
    v = library.load_settings().get("pt_visit") or {}
    if not (v.get("enabled") and v.get("lat") is not None and v.get("person") and ha.available()):
        _pt_here["inside"] = False
        return
    loc = ha.person_location(v["person"])
    # within the radius, allowing for GPS accuracy (capped so a vague fix across town doesn't count)
    _pt_here["inside"] = bool(loc) and ha.distance_m(loc[0], loc[1], v["lat"], v["lon"]) <= \
        int(v.get("radius") or 150) + min(loc[2], 100)
    today = history.local_today()
    service = v.get("service") or (library.load_settings().get("reminder") or {}).get("service")
    if _pt_here["inside"] and v.get("notified") != today and service:
        ha.notify(service, "At PT? Ask about new exercises 🏥", _pt_message())
        library.save_settings({"pt_visit": {**v, "notified": today}})


@app.on_event("startup")
def _start_ha_loop():
    def loop():
        time.sleep(30)
        tick = 0
        while True:
            _quietly(_maybe_pt_visit)          # every minute, so the PT reminder comes soon after you arrive
            if tick % 5 == 0:
                _quietly(ha_refresh)
                _quietly(_maybe_remind)
            tick += 1
            time.sleep(60)
    threading.Thread(target=loop, daemon=True).start()


@app.get("/api/ha")
def ha_info():
    r = library.load_settings().get("reminder") or {}
    v = library.load_settings().get("pt_visit") or {}
    up = ha.available()
    return {"available": up, "services": ha.notify_services() if up else [],
            "reminder": {"enabled": bool(r.get("enabled")), "time": r.get("time", "07:30"), "service": r.get("service", "")},
            "persons": ha.persons() if up else [],
            "pt_visit": {"enabled": bool(v.get("enabled")), "address": v.get("address", ""), "label": v.get("label", ""),
                         "lat": v.get("lat"), "lon": v.get("lon"), "radius": int(v.get("radius") or 150),
                         "person": v.get("person", ""), "service": v.get("service") or r.get("service", ""),
                         "inside": _pt_here["inside"]}}


class PTVisit(BaseModel):
    enabled: bool
    address: str = ""
    label: str = ""
    lat: float | None = None
    lon: float | None = None
    radius: int = 150
    person: str = ""
    service: str = ""


@app.post("/api/ha/ptvisit")
def save_pt_visit(p: PTVisit):
    if p.enabled and (p.lat is None or p.lon is None):
        raise HTTPException(400, "Find the PT office address first.")
    if p.enabled and not p.person:
        raise HTTPException(400, "Pick whose phone to follow.")
    old = library.load_settings().get("pt_visit") or {}
    library.save_settings({"pt_visit": {**old, "enabled": p.enabled, "address": p.address.strip()[:200],
                                        "label": p.label.strip()[:300], "lat": p.lat, "lon": p.lon,
                                        "radius": max(50, min(p.radius, 1000)), "person": p.person,
                                        "service": p.service.strip()}})
    threading.Thread(target=lambda: _quietly(_maybe_pt_visit), daemon=True).start()
    return ha_info()


class Address(BaseModel):
    address: str


@app.post("/api/ha/ptvisit/find")
def find_pt_office(a: Address):
    """Looks the PT office address up on OpenStreetMap."""
    if len(a.address.strip()) < 5:
        raise HTTPException(400, "Type the full address.")
    try:
        return {"matches": ha.geocode(a.address.strip()[:200])}
    except Exception as e:
        return {"matches": [], "error": f"Couldn't look it up ({type(e).__name__})."}


class Who(BaseModel):
    person: str


@app.post("/api/ha/ptvisit/here")
def pt_office_here(w: Who):
    """Uses the phone's current location as the PT office (tap it while you're there)."""
    loc = ha.person_location(w.person)
    if not loc:
        raise HTTPException(400, "Home Assistant doesn't have a location for that phone yet.")
    return {"lat": round(loc[0], 6), "lon": round(loc[1], 6), "accuracy": loc[2]}


@app.post("/api/ha/ptvisit/test")
def test_pt_visit():
    v = library.load_settings().get("pt_visit") or {}
    service = v.get("service") or (library.load_settings().get("reminder") or {}).get("service")
    if not service:
        raise HTTPException(400, "Pick your phone first.")
    try:
        ha.notify(service, "At PT? Ask about new exercises 🏥", _pt_message())
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


class Reminder(BaseModel):
    enabled: bool
    time: str = "07:30"
    service: str = ""


@app.post("/api/ha/reminder")
def save_reminder(r: Reminder):
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", r.time):
        raise HTTPException(400, "Use a time like 07:30.")
    old = library.load_settings().get("reminder") or {}
    library.save_settings({"reminder": {**old, "enabled": r.enabled, "time": r.time, "service": r.service.strip()}})
    return ha_info()


@app.post("/api/ha/test")
def ha_test():
    r = library.load_settings().get("reminder") or {}
    if not r.get("service"):
        raise HTTPException(400, "Pick your phone first.")
    try:
        ha.notify(r["service"], "Workout reminder test", "This is how your morning check-in reminder will look.")
        _quietly(ha_refresh)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"}


@app.get("/api/garmin")
def garmin_state():
    return garmin_sync.status()


class GarminLogin(BaseModel):
    email: str
    password: str


@app.post("/api/garmin/connect")
def garmin_connect(g: GarminLogin):
    result = garmin_sync.connect(g.email, g.password)
    if result["ok"] and not result["needs_mfa"]:
        garmin_sync.sync(datetime.date.fromisoformat(history.local_today()))
    return {**result, **garmin_sync.status()}


class GarminCode(BaseModel):
    code: str


@app.post("/api/garmin/mfa")
def garmin_mfa(c: GarminCode):
    result = garmin_sync.submit_mfa(c.code)
    if result["ok"]:
        garmin_sync.sync(datetime.date.fromisoformat(history.local_today()))
    return {**result, **garmin_sync.status()}


@app.post("/api/garmin/sync")
def garmin_sync_now():
    ok, message = garmin_sync.sync(datetime.date.fromisoformat(history.local_today()))
    return {"ok": ok, "message": message, **garmin_sync.status()}


@app.post("/api/garmin/disconnect")
def garmin_disconnect():
    garmin_sync.disconnect()
    return garmin_sync.status()


@app.post("/api/media/test")
def media_test():
    return media.test()


@app.get("/api/media/yoga/{name}")
def yoga_picture(name: str):
    """A yoga picture from the private B2 bucket (cached on first use)."""
    try:
        path = media.get(name)
    except FileNotFoundError:
        raise HTTPException(404, "No such picture")
    except Exception as e:
        raise HTTPException(502, f"Couldn't load the picture: {e}")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=2592000"})


@app.get("/api/mindbody")
def mind_body():
    return mindbody.cards()


@app.get("/api/meditation")
def meditation_library():
    items, error = meditation.practices()
    return {"practices": items, "error": error, "credit": meditation.CREDIT,
            "categories": [{"id": c, "label": meditation.LABELS.get(c, c.title())}
                           for c in sorted({p["category"] for p in items})]}


class ScriptRequest(BaseModel):
    minutes: int = 5
    focus: str = ""


@app.post("/api/meditation/script")
def meditation_script(r: ScriptRequest):
    script, error = coach.meditation_script(max(2, min(r.minutes, 15)), r.focus)
    return {"script": script, "error": error}


@app.get("/api/voices")
def voices():
    return {"voices": tts.catalog(), "selected": library.load_settings().get("voice", tts.DEFAULT_VOICE)}


class TTSRequest(BaseModel):
    voice: str = tts.DEFAULT_VOICE
    text: str = ""
    preview: bool = False


@app.post("/api/tts")
def make_audio(r: TTSRequest):
    text = tts.PREVIEW_TEXT if r.preview else r.text.strip()[:12000]
    if not text:
        raise HTTPException(400, "Nothing to read")
    return tts.public(tts.start(r.voice, text))


class QigongSession(BaseModel):
    voice: str = tts.DEFAULT_VOICE
    seconds: int = 45      # quiet time per move


@app.post("/api/qigong/session")
def qigong_session(q: QigongSession):
    """A guided Baduanjin session spoken by your chosen voice, as one audio file with a timeline of the moves."""
    segments, cards = mindbody.qigong_session(max(20, min(q.seconds, 120)))
    job = tts.start_session(q.voice, segments)
    steps = [{"name": "Getting ready", "image": None}] + \
        [{"name": c["name"], "image": (c["images"] or [None])[0], "note": c.get("image_note")} for c in cards] + \
        [{"name": "Breathing to finish", "image": None}]
    return {**tts.public(job), "steps": steps}


class GuidedRequest(BaseModel):
    voice: str = tts.DEFAULT_VOICE
    seconds: int = 45


@app.post("/api/cooldown/guided")
def guided_cooldown(g: GuidedRequest):
    """Today's cool-down, exactly as shown on the Today tab, read aloud with time for each pose or move."""
    today = history.local_today()
    w = todays_workout()
    _, cards = _cooldown_for(w, current_log(today), today)
    segments, steps = mindbody.guided_segments(cards, max(20, min(g.seconds, 120)))
    job = tts.start_session(g.voice, segments)
    return {**tts.public(job), "steps": steps}


@app.get("/api/tts/{key}/timeline")
def audio_timeline(key: str):
    t = tts.timeline(key)
    if t is None:
        raise HTTPException(404, "No timeline")
    return {"timeline": t}


@app.get("/api/tts/{key}")
def audio_status(key: str):
    job = tts.status(key)
    if not job:
        raise HTTPException(404, "Unknown audio")
    return tts.public(job)


@app.get("/api/tts/{key}/audio")
def audio_file(key: str):
    job = tts.status(key)
    if not job or job["status"] != "ready":
        raise HTTPException(404, "Audio isn't ready")
    return FileResponse(job["path"], media_type="audio/wav", headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/settings")
def get_settings():
    return {"equipment": library.selected_equipment(), "equipment_options": library.EQUIPMENT_OPTIONS,
            "media_base_url": library.load_settings().get("media_base_url", ""), "media_private": media.configured(),
            "sports": selected_sports(), "sport_options": [{"id": i, "label": l} for i, l in SPORT_OPTIONS],
            "season_start": library.load_settings().get("season_start", ""),
            "paused": [{"name": n, "since": p["since"], "until": p["until"]} for n, p in sorted(paused().items())],
            "machines": readiness.status() if "triathlon" not in selected_sports() else None,
            "gear_notes": library.load_settings().get("gear_notes", library.DEFAULT_GEAR_NOTES),
            "garmin_adjust": bool(library.load_settings().get("garmin_adjust", False)),
            "pt_exercises": pt_exercises(),
            "biofeedback": insights.bio_settings(), "bio_units": insights.BIO_UNITS}


def _clean_pt(items):
    """Checks the PT exercise list from Settings: unique names, short text, real weekdays."""
    out, seen = [], set()
    for p in items[:20]:
        name = str(p.get("name") or "").strip()[:80]
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        cues = [str(c).strip()[:300] for c in (p.get("cues") or []) if str(c).strip()][:12]
        days = sorted({int(x) for x in (p.get("days") or []) if str(x).isdigit() and 0 <= int(x) <= 6})
        dose = str(p.get("dose") or "").strip()[:80]
        m = re.match(r"\s*(\d+)\s*[x×]", dose)     # "2 x 12 each side": the dose says how many sets
        try:
            sets = int(m.group(1)) if m else int(p.get("sets") or 3)
        except (TypeError, ValueError):
            sets = 3
        out.append({"name": name, "dose": dose, "cues": cues,
                    "days": [] if len(days) == 7 else days,
                    "section": p.get("section") if p.get("section") in PT_SECTIONS else "warmup",
                    "sets": max(1, min(sets, 10))})
    return out


class Settings(BaseModel):
    garmin_adjust: bool | None = None
    equipment: list[str] | None = None
    gear_notes: str | None = None
    media_base_url: str | None = None
    voice: str | None = None
    sports: list[str] | None = None
    season_start: str | None = None
    pt_exercises: list[dict] | None = None
    biofeedback: dict | None = None      # {"enabled", "unit", "every_days"}


@app.put("/api/settings")
def put_settings(s: Settings):
    patch = {}
    if s.biofeedback is not None:
        old = library.load_settings().get("biofeedback") or {}
        b = s.biofeedback
        try:
            every = max(7, min(int(b.get("every_days", old.get("every_days", 14))), 60))
        except (TypeError, ValueError):
            every = 14
        patch["biofeedback"] = {**old, "enabled": bool(b.get("enabled", old.get("enabled"))), "every_days": every,
                                "unit": b.get("unit") if b.get("unit") in insights.BIO_UNITS else old.get("unit", "mmHg")}
    if s.pt_exercises is not None:
        patch["pt_exercises"] = _clean_pt(s.pt_exercises)
    if s.equipment is not None:
        # "bodyweight" is always available; unknown names are dropped
        patch["equipment"] = sorted({e for e in s.equipment if e in library.EQUIPMENT_OPTIONS} | {"bodyweight"})
    if s.gear_notes is not None:
        patch["gear_notes"] = s.gear_notes.strip()[:2000]
    if s.garmin_adjust is not None:
        patch["garmin_adjust"] = s.garmin_adjust
    if s.sports is not None:
        patch["sports"] = [x for x, _ in SPORT_OPTIONS if x in s.sports]
    if s.season_start is not None:
        try:
            patch["season_start"] = datetime.date.fromisoformat(s.season_start).isoformat() if s.season_start else ""
        except ValueError:
            raise HTTPException(400, "The season date must look like 2026-12-01")
    if s.voice is not None and s.voice in tts.VOICES:
        patch["voice"] = s.voice
    if s.media_base_url is not None:
        url = s.media_base_url.strip().rstrip("/")
        if url and not url.startswith("https://"):
            raise HTTPException(400, "The media address must start with https://")
        patch["media_base_url"] = url
    if patch:
        library.save_settings(patch)
    return get_settings()


@app.get("/api/claude")
def claude_state():
    return coach.login_state()


@app.post("/api/claude/login")
def claude_login():
    return coach.start_login()


class LoginCode(BaseModel):
    code: str


@app.post("/api/claude/code")
def claude_code(c: LoginCode):
    return coach.send_code(c.code)


@app.post("/api/claude/cancel")
def claude_cancel():
    return coach.cancel_login()


@app.post("/api/claude/logout")
def claude_logout():
    coach.logout()
    return coach.login_state()


@app.post("/api/report")
def make_report():
    _, error = coach.report()
    return {"ok": error is None, "error": error, "path": "/config/workout_tracker/progress_report.html"}


# --- Claude Terminal endpoints (unchanged from 0.1.x) ----------------------------------------------

class SymptomLog(BaseModel):
    rpe: int
    pelvic_floor_tightness: int
    kidney_flank_pain: int
    notes: str = ""


@app.get("/workout/today")
def get_todays_workout():
    """Claude Terminal can call this to see what Joe is supposed to do today."""
    return todays_workout()


@app.post("/workout/log")
def log_symptoms(log: SymptomLog):
    """Claude Terminal can call this to log Joe's symptoms and force the engine to adapt."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO daily_logs (date, completed, rpe, pelvic_floor_tightness, kidney_flank_pain, notes, executed_workout)
        VALUES (?, 1, ?, ?, ?, ?, ?)
    """, (history.local_today(), log.rpe, log.pelvic_floor_tightness, log.kidney_flank_pain, log.notes, "{}"))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Symptoms logged. Tomorrow's workout has been auto-regulated."}
