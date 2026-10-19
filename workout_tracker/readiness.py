"""When the Peloton and the water rower come back into the plan.

Both are unlocked by your own scores (morning check-ins, or the scores logged with a workout), never by a calendar:

* Peloton (saddle pressure on the pelvic floor): your pelvic floor score averages 3 or lower over the last 7 days, with
  no day above 5 (at least 4 scored days). Starts at 12 easy minutes and adds 5 minutes a week, up to 45.
  It steps back if your most recent pelvic floor score is 5 or more.
* Rower (leg drive, bracing and the hinge load the flank and pelvic floor more): the Peloton has been unlocked for
  2 weeks and your kidney score has been 3 or lower on every scored day of the last 14 (at least 7 scored days).
  Starts at 8 easy minutes, low water level, and adds 5 minutes a week, up to 30. It steps back after a kidney score
  above 4.

A Settings switch per machine ("PT cleared it" / "Not yet") overrides the rules. These thresholds are a starting point
agreed with Joe, not medical advice; his PT has the final say."""
import datetime

import history
import library
from db import DB_PATH

MACHINES = {"bike": "Peloton", "row": "Water rower"}
OVERRIDES = ("auto", "cleared", "not_yet")


def _weeks_since(since, today):
    return max(0, (today - datetime.date.fromisoformat(since)).days // 7)


def status(today=None, scores=None):
    """{"bike": {...}, "row": {...}} with ok, minutes and a plain-English reason."""
    today = today or datetime.date.fromisoformat(history.local_today())
    scores = scores if scores is not None else history.daily_scores(DB_PATH, 30, today)
    settings = library.load_settings()
    saved = dict(settings.get("machines") or {})
    overrides = settings.get("machine_override") or {}
    changed = False

    def window(days):
        start = (today - datetime.timedelta(days=days - 1)).isoformat()
        return [scores[d] for d in sorted(scores) if start <= d <= today.isoformat()]

    latest = scores[max(scores)] if scores else None
    out = {}

    # --- Peloton ---
    week = window(7)
    pf = [s["pelvic_floor"] for s in week]
    if len(pf) < 4:
        ok, why = False, f"Needs a few more scored days ({len(pf)} of 4 this week). Do your morning check-ins."
    elif sum(pf) / len(pf) > 3 or max(pf) > 5:
        ok, why = False, (f"Unlocks when your pelvic floor averages 3 or lower over a week with no day above 5 "
                          f"(now {sum(pf) / len(pf):.1f}, highest {max(pf)}).")
    else:
        ok, why = True, "Your pelvic floor has stayed low this week."
    stepped_back = bool(ok and latest and latest["pelvic_floor"] >= 5)
    if stepped_back:
        ok, why = False, "Stepping back: your latest pelvic floor score was 5 or more. Walking for a few days."
    out["bike"] = _finish("bike", ok, why, stepped_back, overrides, saved, today, start=12, cap=45)

    # --- Rower ---
    bike_since = out["bike"]["since"]
    fortnight = window(14)
    kid = [s["kidney"] for s in fortnight]
    if not bike_since or _weeks_since(bike_since, today) < 2:
        left = 14 - ((today - datetime.date.fromisoformat(bike_since)).days if bike_since else 0)
        ok, why = False, (f"Unlocks after 2 good weeks on the Peloton ({left} days to go)." if bike_since
                          else "Unlocks after 2 good weeks on the Peloton.")
    elif len(kid) < 7:
        ok, why = False, f"Needs more scored days ({len(kid)} of 7 in the last 2 weeks)."
    elif max(kid) > 3:
        ok, why = False, f"Unlocks when your kidney score stays at 3 or lower for 2 weeks (highest lately: {max(kid)})."
    else:
        ok, why = True, "The Peloton has gone well and your kidney scores have stayed low."
    stepped_back = bool(ok and latest and latest["kidney"] > 4)
    if stepped_back:
        ok, why = False, "Stepping back: your latest kidney score was above 4."
    out["row"] = _finish("row", ok, why, stepped_back, overrides, saved, today, start=8, cap=30)

    for m in MACHINES:
        key = f"{m}_since"
        if out[m]["since"] != saved.get(key):
            saved[key] = out[m]["since"]
            changed = True
    if changed:
        library.save_settings({"machines": saved})
    return out


def _finish(machine, ok, why, stepped_back, overrides, saved, today, start, cap):
    override = overrides.get(machine, "auto")
    since = saved.get(f"{machine}_since")
    if override == "cleared":
        ok, why, stepped_back = True, "Your PT cleared it (set in Settings).", False
    elif override == "not_yet":
        ok, why, stepped_back = False, "Off for now (set in Settings).", False
    if ok and not since:
        since = today.isoformat()
    elif not ok and not stepped_back:
        since = None                       # lost it: the build-up starts again next time
    minutes = min(start + 5 * _weeks_since(since, today), cap) if since else start
    return {"name": MACHINES[machine], "ok": ok, "why": why, "stepped_back": stepped_back, "since": since,
            "minutes": minutes, "override": override}
