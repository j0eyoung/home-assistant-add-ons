"""Background loop (every 15 minutes): powder alerts, powder-morning wake-up, gear upkeep reminders,
thermostat reset after leaving the mountain, and the sensor.ski_* states for dashboards and the Daily Briefing.
Each task is wrapped so one failing entity or feed never stops the others."""
import datetime as dt
import os
import threading
import time
import traceback

import accuracy
import advisor
import dailysnow
import db
import forecast
import ha
import ranking
import resortinfo
import resorts
import season
import settings
import util

INTERVAL = 900
ALERT_IN = float(os.getenv("POWDER_ALERT_INCHES", "6"))
_state = {"at_mountain": None}


def _push(title, message):
    s = settings.load()
    if s["phone_service"]:
        ha.notify(s["phone_service"], title, message)


def powder_alerts():
    for hit in ranking.powder_alerts(resorts.load(), threshold_in=ALERT_IN):
        if db.once(f"powder:{hit['resort']}:{hit['first_day']}"):
            _push("Powder alert", f"{hit['resort']}: {hit['snow_in']} in forecast from {hit['first_day']}.")


def powder_morning():
    """At wake_time on a day with >= threshold fresh snow at the top pick: lights, speaker, phone."""
    s = settings.load()
    now = util.now()
    if now.strftime("%H:%M") < s["wake_time"] or now.hour >= 11:
        return
    rows = [r for r in ranking.best_days(resorts.load()) if "error" not in r]
    if not rows or rows[0]["fresh_in"] < ALERT_IN or not db.once(f"morning:{now.date()}"):
        return
    top = rows[0]
    msg = (f"Powder morning. {top['resort']} has {top['fresh_in']} inches of fresh snow. "
           f"Leave by {top['leave']['leave_at']} to be on the lifts by {s['arrive_by']}.")
    waze = (top.get("traffic") or {}).get("waze")
    if waze:
        msg += f" Waze says {waze['minutes']} minutes right now."
    actions = [lambda: _push("Powder morning", msg), lambda: packing_list(top["id"], now.date().isoformat())]
    if s["powder_lights"]:
        actions.append(lambda: ha.turn_on(s["powder_lights"]))
    if s["tts_entity"] and s["speaker_entity"]:
        actions.append(lambda: ha.speak(s["tts_entity"], s["speaker_entity"], msg))
    for act in actions:  # one failing entity shouldn't skip the others
        try:
            act()
        except Exception:
            traceback.print_exc()


def upkeep_reminders():
    for eq, kinds in season.upkeep().items():
        for kind, u in kinds.items():
            if u["due"] and db.once(f"upkeep:{eq}:{kind}:{u['last']}:{u['every']}"):
                _push("Gear upkeep", f"Your {eq} is due a {kind} ({u['days_since']} days since the last one).")
                if kind == "wax":
                    ha.shopping_add(f"{'Snowboard' if eq == 'board' else 'Ski'} wax")


def thermostat():
    """When the phone leaves a resort (was within 3 miles, now isn't), put the thermostat back to normal."""
    s = settings.load()
    if not (s["tracker_entity"] and s["climate_entity"]):
        return
    attrs = (ha.get_state(s["tracker_entity"]) or {}).get("attributes", {})
    lat, lon = attrs.get("latitude"), attrs.get("longitude")
    if lat is None or lon is None:
        return
    here = any(util.miles(lat, lon, r["lat"], r["lon"]) < 3 for r in resorts.load())
    if _state["at_mountain"] and not here:
        ha.set_temperature(s["climate_entity"], s["normal_temp_f"])
        _push("Heading home", f"Thermostat set back to {s['normal_temp_f']}F.")
    _state["at_mountain"] = here


def sensors():
    rows = [r for r in ranking.best_days(resorts.load()) if "error" not in r]
    if rows:
        top = rows[0]
        ha.set_state("sensor.ski_best_today", top["resort"],
                     {"friendly_name": "Ski: best today", "score": top["score"], "fresh_in": top["fresh_in"],
                      "leave_at": top["leave"]["leave_at"], "icon": "mdi:ski"})
    p = season.pass_summary()
    ha.set_state("sensor.ski_days_this_season", p["total_days"],
                 {"friendly_name": "Ski days this season", "unit_of_measurement": "days", "icon": "mdi:snowflake"})


def drying_reminder(resort_name):
    """Called when a day is logged: dry boots and gloves."""
    if settings.load()["drying_reminder"] and ha.available():
        try:
            _push("Dry your gear", f"Back from {resort_name}: put the boots and gloves on the dryer.")
        except Exception:
            traceback.print_exc()


def weekend_outlook():
    """Thursday evening: the best weekend day and resort, when to leave, and any parking reservation to book."""
    s = settings.load()
    now = util.now()
    if not s["weekend_outlook"] or now.weekday() != 3 or now.strftime("%H:%M") < s["outlook_time"]:
        return
    if not db.once(f"outlook:{now.date()}"):
        return
    best = []
    for days_ahead in (2, 3):  # Saturday, Sunday
        date = (now.date() + dt.timedelta(days=days_ahead)).isoformat()
        rows = [r for r in ranking.best_days(resorts.load(), date) if "error" not in r]
        if rows:
            best.append((date, rows[0]))
    if not best:
        return
    day, top = max(best, key=lambda x: x[1]["score"])
    by_id = {r["id"]: r for r in resorts.load()}
    name = dt.date.fromisoformat(day).strftime("%A")
    lines = [f"{name} at {top['resort']}: {top['fresh_in']} in fresh, high {round(top['tmax_f'])}F. "
             f"Leave {top['leave']['leave_at']}."]
    other = [b for b in best if b[0] != day]
    if other:
        od, o = other[0]
        lines.append(f"{dt.date.fromisoformat(od).strftime('%A')}: {o['resort']}, {o['fresh_in']} in.")
    park = resortinfo.parking_needed(by_id[top["id"]], day)
    if park:
        lines.append(park["note"])
    if s["phone_service"]:
        ha.notify(s["phone_service"], "Weekend ski outlook", " ".join(lines),
                  link=park["url"] if park else None, link_title="Book parking")


_trend = {}  # resort id -> [(time, next 5 days inches)], kept in memory only (no disk writes)


def storm_trends():
    """Storm trending up: the next-5-day total has jumped since earlier today and the two models agree."""
    if not settings.load()["storm_alerts"]:
        return
    now = time.time()
    for r in resorts.load():
        try:
            days = [d for d in forecast.daily(r) if d["date"] >= util.today().isoformat()][:5]
        except Exception:
            continue
        total = round(sum(d["snow_in"] for d in days), 1)
        history = [h for h in _trend.get(r["id"], []) if now - h[0] < 24 * 3600]
        history.append((now, total))
        _trend[r["id"]] = history
        earlier = [v for t, v in history if now - t >= 6 * 3600]
        if not earlier or total < 4 or total < ALERT_IN * 0.5:
            continue
        before = earlier[0]
        model_totals = [sum(d["models"].get(m) or 0 for d in days) for m in forecast.MODELS.values()]
        agree = min(model_totals) >= 0.6 * max(model_totals) if max(model_totals) > 0 else False
        if total - before >= 3 and agree and db.once(f"trend:{r['id']}:{util.today()}"):
            _push("Storm trending up", f"{r['name']}: next 5 days now {total} in (was {before} in earlier today). "
                                       "ECMWF and GFS agree.")


def model_accuracy():
    """Evening: save tomorrow's forecasts. Late morning: score the past ones against SNOTEL."""
    now = util.now()
    if now.hour >= 19 and db.once(f"acc_record:{now.date()}"):
        accuracy.record_tomorrow()
    if now.hour >= 11 and db.once(f"acc_score:{now.date()}"):
        accuracy.score_past()


def packing_list(resort_id, date_iso, skis=False):
    """Add the day's gear call (plus the basics) to the Home Assistant to-do list, once per day and resort."""
    s = settings.load()
    r = next((x for x in resorts.load() if x["id"] == resort_id), None)
    if not r or not db.once(f"packing:{date_iso}:{resort_id}"):
        return []
    row = next((x for x in ranking.best_days([r], date_iso, skis=skis) if "error" not in x), None)
    items = ["Pass", "Helmet and goggles", "Gloves", "Water and snacks"]
    if row:
        items = row["gear"]["wear"] + [n for n in row["gear"]["notes"]
                                       if not n.startswith(("Powder day", "Skis:", "Expect lift"))] + items
        if row["tmax_f"] < 20:
            items.append("Hand warmers")
    items.append("Skis, poles and ski boots" if skis else "Board and boots")
    added = []
    for item in dict.fromkeys(items):  # keep order, drop duplicates
        label = f"Ski {date_iso[5:]}: {item}"
        try:
            if s["packing_todo"]:
                ha.todo_add(s["packing_todo"], label)
            else:
                ha.shopping_add(label)
            added.append(item)
        except Exception:
            traceback.print_exc()
            break
    return added


def daily_snow():
    """Write the Daily Snow once a day, from 5:30am, so it's ready for the morning (one Claude call)."""
    now = util.now()
    # One attempt a day: if Claude fails or declines, it waits for tomorrow (or a manual refresh)
    if advisor.available() and now.strftime("%H:%M") >= "05:30" and db.once(f"dailysnow:{now.date()}"):
        dailysnow.get()


TASKS = [daily_snow, powder_alerts, powder_morning, storm_trends, weekend_outlook, model_accuracy,
         upkeep_reminders, thermostat, sensors]


def _loop():
    while True:
        for task in TASKS:
            try:
                task()
            except Exception:
                print(f"[scheduler] {task.__name__} failed at {dt.datetime.now():%H:%M}")
                traceback.print_exc()
        time.sleep(INTERVAL)


def start():
    if ha.available():  # only inside Home Assistant
        threading.Thread(target=_loop, daemon=True).start()
