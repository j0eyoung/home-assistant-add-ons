"""How-to guides for each exercise: dose, form cues and optional demo pictures.

Pictures come from RepDB (repdb.co) illustrations and the public-domain Free Exercise DB.
Two pictures (start and finish) flip like a GIF; one picture shows as is.
"""

from library import FEDB_IMAGES, REPDB_BASE


def _frames(exercise_id):
    return [f"{FEDB_IMAGES}{exercise_id}/0.jpg", f"{FEDB_IMAGES}{exercise_id}/1.jpg"]


def _repdb(*names):
    return [f"{REPDB_BASE}images/flat/{n}.webp" for n in names]


# Keyed by the exact names engine.py prescribes
GUIDES = {
    "Gut-Motility Primer": {
        "dose": "2 min",
        "cues": [
            "Lie on your back with knees bent.",
            "Gently massage your belly in slow clockwise circles.",
            "Breathe deeply the whole time.",
        ],
    },
    "360-Degree Rib Breathing": {
        "dose": "2 min (about 10 slow breaths)",
        "cues": [
            "Lie on your back, knees bent, hands on the sides of your lower ribs.",
            "Breathe in through your nose and push your ribs outward and back into the floor, not just your belly up.",
            "Breathe out slowly and let the ribs settle. Keep it gentle: never force a stretch on the left side.",
        ],
    },
    "Core Canister Breathing (Leaky Can)": {
        "dose": "40 slow breaths (4 rounds of 10)",
        "cues": [
            "Lie on your back, knees bent, fingers just inside your hip bones (on the TA).",
            "Your core is a can: diaphragm is the lid, pelvic floor is the bottom, the TA (deep abs) is the walls.",
            "Breathe in through your nose: ribs widen, belly softens and the pelvic floor relaxes.",
            "Breathe out slowly through pursed lips and draw your lower belly in: you should feel the TA tighten and flatten under your fingers. That tension is the check that you're doing it right.",
            "No leaks: if your fingers feel a bulge or push-out, or you hold your breath, ease off and start the next breath. Let the pelvic floor follow lightly; never grip or clench.",
        ],
    },
    "TVA Adductor Hack": {
        "dose": "10 slow reps",
        "cues": [
            "Lie on your back, knees bent, yoga block or rolled towel between your knees.",
            "Put your fingers just inside your hip bones.",
            "Breathe in. As you breathe out, squeeze the block and 'zip up' your lower belly away from your fingers.",
            "You should feel the muscle tense and flatten under your fingers, not bulge. Don't tilt your pelvis or hold your breath.",
        ],
    },
    "Supine Heel Slides": {
        "dose": "2 x 10 each leg",
        "sets": 2,
        "cues": [
            "Lie on your back, knees bent, fingers on your lower belly (TVA).",
            "Zip up the TVA, then slowly slide one heel along the floor until the leg is straight.",
            "Slide it back and switch legs.",
            "Stop the slide where you lose the flat feeling under your fingers or your lower back starts to arch.",
        ],
    },
    "Wall-Push Deadbugs": {
        "dose": "2 x 8 each side",
        "sets": 2,
        "images": _repdb("dead-bug-start", "dead-bug-peak"),
        "image_note": "Picture shows a standard dead bug. For yours, press your hands flat into a wall behind your head.",
        "cues": [
            "Lie on your back with your head near a wall, arms overhead, palms pushing into the wall.",
            "Lift your knees to 90/90 (knees over hips, shins level).",
            "Keep pushing the wall and slowly lower one heel toward the floor, lower back flat.",
            "Bring it back and switch sides.",
        ],
    },
    "Wall Sits (45s)": {
        "dose": "3 x 45 s, 60 s rest",
        "sets": 3,
        "images": _repdb("wall-sit-main"),
        "cues": [
            "Back flat against the wall, feet about shoulder-width and a step out from the wall.",
            "Slide down until your knees are near 90 degrees (stay higher if needed). Knees over ankles.",
            "Keep breathing and keep the TVA zipped. Stand up if your left flank starts to pull.",
        ],
    },
    "Banded Lateral Walks": {
        "dose": "2 x 10 steps each way",
        "sets": 2,
        "images": _repdb("banded-lateral-walk-start", "banded-lateral-walk-peak"),
        "cues": [
            "Band just above your knees or around your ankles. Sit into a shallow half-squat.",
            "Step sideways, keeping tension on the band the whole time. Toes point forward.",
            "Keep your hips level and your chest tall; don't lean or twist.",
        ],
    },
    "Wall Tibialis Raises": {
        "dose": "2 x 15",
        "sets": 2,
        "cues": [
            "Lean your back against a wall with your heels about a foot out from it.",
            "Lift your toes up toward your shins as high as you can.",
            "Lower slowly. You should feel it in the front of your shins.",
        ],
    },
    "Supported Butterfly Pose (3 mins)": {
        "dose": "3 min",
        "sets": 1,
        "images": _repdb("butterfly-stretch-main"),
        "image_note": "Picture shows the seated version. For yours, lie back with pillows under your knees and back.",
        "cues": [
            "Lie back on pillows or a bolster, soles of the feet together, knees falling out to the sides.",
            "Support each knee with a pillow so nothing strains.",
            "Breathe slowly into your belly and ribs and let the pelvic floor relax.",
        ],
    },
    "Child's Pose (Focus on left rib expansion)": {
        "dose": "1-2 min",
        "sets": 1,
        "images": _repdb("childs-pose-main"),
        "cues": [
            "Kneel with knees wide and sit back toward your heels, arms reaching forward.",
            "Breathe into your back ribs, especially the left side.",
            "Let each breath out soften you a little further. No forcing.",
        ],
    },
}

# Demo photos for each cardio type in engine.py (swimming has none in the database)
CARDIO_IMAGES = {
    "recovery": _frames("Walking_Treadmill"),
    "walk": _frames("Walking_Treadmill"),
    "bike": _frames("Bicycling_Stationary"),
    "run": _frames("Running_Treadmill"),
}
