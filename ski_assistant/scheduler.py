"""Background loop (every 15 minutes): powder alerts, powder-morning wake-up, gear upkeep reminders,
thermostat reset after leaving the mountain, and the sensor.ski_* states for dashboards and the Daily Briefing.
Each task is wrapped so one failing entity or feed never stops the others."""
import datetime as dt
import os
import threading
import time
import traceback

import advisor
import dailysnow
import db
import ha
import ranking
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
    actions = [lambda: _push("Powder morning", msg)]
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


def daily_snow():
    """Write the Daily Snow once a day, from 5:30am, so it's ready for the morning (one Claude call)."""
    now = util.now()
    # One attempt a day: if Claude fails or declines, it waits for tomorrow (or a manual refresh)
    if advisor.available() and now.strftime("%H:%M") >= "05:30" and db.once(f"dailysnow:{now.date()}"):
        dailysnow.get()


TASKS = [daily_snow, powder_alerts, powder_morning, upkeep_reminders, thermostat, sensors]


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
