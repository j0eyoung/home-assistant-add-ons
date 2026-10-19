import datetime
import json
import random

# Starting minutes for each cardio type, all at an easy pace (Zone 2)
CARDIO_BASE_MINUTES = {"recovery": 15, "swim": 20, "bike": 30, "run": 20, "walk": 20, "row": 10}
CARDIO_MAX_MINUTES = 45
# Add at most 5 minutes per week
PROGRESSION_DAYS = 7

CARDIO_TEXT = {
    "recovery": "Recovery: light walking or easy swimming (no running or biking)",
    "swim": "Swimming. Easy laps, or 10 x 50 m with 30 s rest. Symmetrical breathing, avoid aggressive torso rotation",
    "bike": "Cycling at low resistance and high cadence (85-95 rpm). Or swap for a backwards incline walk of the same length",
    "run": "Running in Zone 2, high cadence to minimize ground reaction force. If your heart rate drifts above Zone 2, alternate 2 min running / 1 min walking",
    "walk": "Treadmill incline walk",
    "row": "Water rower: easy, smooth strokes at a low water level. Push with the legs, keep the belly soft and breathe out on the drive; no sprints",
}

# Extra exercises drawn from the exercise library each day: (goal tag, why it is in the plan)
ACCESSORY_SLOTS = [
    ("legs", "Snowboard legs: edge control and quad endurance"),
    ("upper back", "Posture and swim pulling strength"),
    ("core", "Core control without crunching"),
    ("mobility", "Mobility"),
]
RECOVERY_SLOTS = [("mobility", "Recovery-day stretch"), ("mobility", "Recovery-day stretch")]
RECOVERY_MUSCLES = {"glutes", "hamstrings", "adductors", "abductors", "hip flexors", "quads", "lower back"}


SNOW_SPORTS = {"skiing", "snowboarding"}


def accessory_slots(goals):
    """Daily extras. Snow sports bias the legs slot and add a balance slot (edge, ankle and single-leg control)."""
    snow = SNOW_SPORTS & set(goals)
    if not snow:
        return [s for s in ACCESSORY_SLOTS if s[0] != "legs"] + [("legs", "Leg strength and endurance")]
    name = {"skiing"}.issuperset(snow) and "Ski" or ({"snowboarding"}.issuperset(snow) and "Snowboard" or "Ski and snowboard")
    slots = [("legs", f"{name} legs: quad endurance and control")] + [s for s in ACCESSORY_SLOTS if s[0] != "legs"]
    slots.insert(1, ("balance", f"{name} balance: single-leg, ankle and hip control"))
    return slots


# Muscle-group themes from the weekly plan: each strength day works a different group, and the groups rotate each week.
THEME_SLOTS = {
    # Core activation is where Joe's body struggles most, so every strength day has two core slots
    "legs": [("legs", "Quads and glutes"), ("legs", "Single-leg and hip strength"), ("core", "Core activation"),
             ("core", "Core stability")],
    "back": [("upper back", "Upper back and posture"), ("upper back", "Pulling strength"), ("core", "Core activation"),
             ("core", "Core stability"), ("mobility", "Chest and spine mobility")],
    "hips": [("balance", "Balance and ankle control"), ("legs", "Glutes and hips"), ("core", "Core activation"),
             ("core", "Core stability"), ("mobility", "Hip mobility")],
    "core": [("core", "Core activation"), ("core", "Deep core control"), ("core", "Core stability"),
             ("mobility", "Rib and pelvic mobility")],
    "full": [("legs", "Legs"), ("upper back", "Upper back"), ("core", "Core activation"), ("core", "Core stability")],
}
# Cardio days add one short piece of work for a group that isn't trained that day
CARDIO_THEME_SLOTS = {"core_add": [("core", "Core activation")], "mobility": [("mobility", "Hip and spine mobility")]}


def theme_slots(theme, goals, season_phase=None):
    slots = list(THEME_SLOTS[theme])
    if theme == "legs" and SNOW_SPORTS & set(goals):
        slots[0] = ("legs", "Snow legs: quad endurance and control")
        if season_phase in ("Ski prep", "Sharpen"):
            slots.insert(1, ("balance", "Edge and balance control for the slopes"))
    return slots


def pick_accessories(library, equipment, today, recovery, exclude, goals=("snowboarding", "triathlon"), slots=None, seed=""):
    """Safe library exercises for today's open slots. Same picks all day, new picks tomorrow."""
    rng = random.Random(f"{today.isoformat()}{seed}")
    pool = [e for e in library if e["safe"] and e["equipment"] in equipment and e["name"] not in exclude]
    picks = []
    for goal, why in (RECOVERY_SLOTS if recovery else (slots if slots is not None else accessory_slots(goals))):
        taken = {p["name"] for p in picks}
        options = [e for e in pool if goal in e["goal_tags"] and e["name"] not in taken]
        if recovery:
            options = [e for e in options if RECOVERY_MUSCLES & set(e["muscles"])]
        if goal == "core":
            # Weak TVA: stay with beginner-level core work
            options = [e for e in options if e["level"] == "beginner"] or options
        # Prefer exercises with pictures and written steps
        options = ([e for e in options if e["images"] and e["instructions"]]
                   or [e for e in options if e["images"]] or options)
        if options:
            e = rng.choice(sorted(options, key=lambda x: x["name"]))
            picks.append({"name": e["name"], "why": why})
    return picks


DAILY_WARMUP = ["Gut-Motility Primer", "360-Degree Rib Breathing", "Core Canister Breathing (Leaky Can)",
                "TVA Adductor Hack"]


class WorkoutEngine:
    def __init__(self, db_path="workout_tracker.db"):
        self.db_path = db_path

    def generate_next_workout(self, last_log, today=None, library=None, equipment=None, goals=None,
                              focus=None, cardio_type=None, theme=None, season_phase=None):
        """
        Dynamically builds the next workout based on active goals
        (skiing, snowboarding, triathlon) and current medical symptoms.
        `focus` comes from the weekly plan: "rest" and "recovery" make a recovery day, "cardio" keeps the strength part
        to base core work. Symptoms always win: a kidney score above 5 forces a recovery day whatever the week says.
        `cardio_type` is the week's planned cardio, used only when it is safe for today's pelvic floor score.
        """
        active_goals = list(goals) if goals is not None else ["snowboarding", "triathlon"]
        self.goals = active_goals
        pf_tightness = last_log.get("pelvic_floor_tightness") or 1
        kidney_pain = last_log.get("kidney_flank_pain") or 1
        rpe = last_log.get("rpe") or 5
        last_workout = last_log.get("executed_workout") or {}
        today = today or datetime.date.today()

        workout_plan = {
            "warmup": list(DAILY_WARMUP),
            "strength": [],
            "cardio": ""
        }

        # --- MEDICAL AUTO-REGULATION ---
        if kidney_pain > 5 or focus in ("rest", "recovery"):
            # Flank is acting up (or the week says rest): recovery day, no twisting, lots of breathing
            workout_plan["strength"].append("Supported Butterfly Pose (3 mins)")
            workout_plan["strength"].append("Child's Pose (Focus on left rib expansion)")
            self._add_accessories(workout_plan, library, equipment, today, recovery=True)
            self._set_cardio(workout_plan, "recovery", rpe, kidney_pain, last_workout, today)
            return workout_plan

        # --- STRENGTH PROGRAMMING ---
        # Base core stability is always included
        workout_plan["strength"].extend(["Supine Heel Slides", "Wall-Push Deadbugs"])

        if focus == "cardio":
            # Cardio day: base core work plus one short piece for a group that isn't trained today
            self._add_accessories(workout_plan, library, equipment, today, recovery=False,
                                  slots=CARDIO_THEME_SLOTS.get(theme, []), seed=f"c{theme}")
        else:
            if ("snowboarding" in active_goals or "skiing" in active_goals) and theme in (None, "legs"):
                # Inject lateral edge control and quad endurance (Zero spinal load) on leg days
                workout_plan["strength"].extend(["Wall Sits (45s)", "Banded Lateral Walks", "Wall Tibialis Raises"])
            slots = theme_slots(theme, active_goals, season_phase) if theme in THEME_SLOTS else None
            self._add_accessories(workout_plan, library, equipment, today, recovery=False, slots=slots, seed=f"t{theme}")

        # --- CARDIO & TRIATHLON PROGRAMMING ---
        if "triathlon" in active_goals:
            # Decide between Swim, Bike, or Run based on Pelvic Floor
            if pf_tightness >= 7:
                # High impact (running) or seated pressure (biking) will flare the pelvic floor.
                # Force Swimming: Zero gravity, massive cardio, relieves pelvic pressure.
                auto_type = "swim"
            elif pf_tightness >= 4:
                # Moderate tightness: Biking is okay if saddle pressure is managed, or backwards walking.
                auto_type = "bike"
            else:
                # Pelvic floor is relaxed: Safe to train running impact
                auto_type = "run"
        else:
            auto_type = "walk"
        # The week's plan may ask for a different type, but only one that is safe at today's pelvic floor score
        safe_for_pf = {"swim": True, "walk": True, "bike": pf_tightness < 7, "run": pf_tightness < 4, "row": pf_tightness < 7}
        cardio_type = cardio_type if cardio_type in safe_for_pf and safe_for_pf[cardio_type] else auto_type
        self._set_cardio(workout_plan, cardio_type, rpe, kidney_pain, last_workout, today)

        return workout_plan

    def _add_accessories(self, workout_plan, library, equipment, today, recovery, slots=None, seed=""):
        if not library:
            return
        picks = pick_accessories(library, set(equipment or []), today, recovery, set(workout_plan["strength"]),
                                 getattr(self, "goals", ("snowboarding", "triathlon")), slots=slots, seed=seed)
        workout_plan["strength"].extend(p["name"] for p in picks)
        workout_plan["accessories"] = picks

    def _set_cardio(self, workout_plan, cardio_type, rpe, kidney_pain, last_workout, today):
        minutes, progressed_on, note = self._cardio_minutes(cardio_type, rpe, kidney_pain, last_workout, today)
        workout_plan["cardio"] = (
            f"{minutes} min: {self._cardio_label(cardio_type)}. "
            "Easy pace (you can talk in full sentences); the first 5 min are your warm-up."
        )
        workout_plan["cardio_type"] = cardio_type
        workout_plan["cardio_minutes"] = minutes
        workout_plan["cardio_progressed_on"] = progressed_on
        workout_plan["cardio_note"] = note

    def _cardio_label(self, cardio_type):
        """Cardio description; only called Triathlon Prep when triathlon is one of your sports."""
        text = CARDIO_TEXT[cardio_type]
        if "triathlon" in getattr(self, "goals", []) and cardio_type in ("swim", "bike", "run"):
            text = "Triathlon Prep: " + text
        return text

    def _cardio_minutes(self, cardio_type, rpe, kidney_pain, last_workout, today):
        """Returns (minutes, date the minutes last changed, why) based on the last logged session."""
        base = CARDIO_BASE_MINUTES[cardio_type]
        if cardio_type == "recovery":
            return base, None, "Recovery day: keep it short and easy."
        if last_workout.get("cardio_type") != cardio_type or not last_workout.get("cardio_minutes"):
            return base, today.isoformat(), "Starting length for this type of cardio."

        prev = last_workout["cardio_minutes"]
        progressed_on = last_workout.get("cardio_progressed_on") or today.isoformat()
        if rpe >= 8:
            minutes = max(10, round(prev * 0.75 / 5) * 5)
            return minutes, today.isoformat(), f"Cut back from {prev} min: your last effort was {rpe}/10."

        days_since_change = (today - datetime.date.fromisoformat(progressed_on)).days
        if rpe <= 6 and kidney_pain <= 3 and days_since_change >= PROGRESSION_DAYS and prev < CARDIO_MAX_MINUTES:
            minutes = min(prev + 5, CARDIO_MAX_MINUTES)
            return minutes, today.isoformat(), f"Up 5 min from {prev}: last session felt easy ({rpe}/10) and symptoms stayed low."
        return prev, progressed_on, f"Same as last time ({prev} min)."

# Example execution
if __name__ == "__main__":
    engine = WorkoutEngine()

    # Simulate user logging a tight pelvic floor after a hard week
    recent_log = {
        "pelvic_floor_tightness": 8,
        "kidney_flank_pain": 2
    }

    todays_workout = engine.generate_next_workout(recent_log)
    print("DYNAMIC WORKOUT GENERATED:")
    print(json.dumps(todays_workout, indent=2))
