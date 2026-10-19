"""Exercise library: merges several exercise databases into the exercise_library table,
flags exercises that are unsafe for Joe (kidney adhesions, tight pelvic floor, weak core),
tags them by goal, and borrows pictures across sources by name.

Sources
- Free Exercise DB (public domain): data/free-exercise-db.json, photos on GitHub.
- RepDB free tier (in-app use with attribution, no redistribution): downloaded to /config at startup.
- Strength to Overcome functional fitness database (personal use): downloaded to /config at startup.
- Boostcamp workout programs (Kaggle): data/boostcamp-exercises.json, names with typical sets/reps.
"""
import ast
import csv
import io
import json
import os
import re
import sqlite3
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.getenv("LIBRARY_CACHE_DIR", "/config/workout_tracker/sources")
REFRESH_DAYS = 30
# Bump when the tagging or merge rules change so the table is rebuilt
LIBRARY_VERSION = "1"

FEDB_FILE = os.path.join(HERE, "data", "free-exercise-db.json")
FEDB_IMAGES = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5/exercises/"
REPDB_BASE = "https://raw.githubusercontent.com/RepDB/exercise-dataset/a360f87f9064de42a9c90228cfebae941a5016d5/"
STO_URL = "https://docs.google.com/spreadsheets/d/1zMYUkfVuTkHn08iiC5KoDcMnN8hps987pJr2_2iWnGo/export?format=csv"
BOOSTCAMP_FILE = os.path.join(HERE, "data", "boostcamp-exercises.json")

SOURCE_NAMES = {
    "repdb": "RepDB",
    "fedb": "Free Exercise DB",
    "ninjas": "API Ninjas",
    "sto": "Strength to Overcome",
    "boostcamp": "Boostcamp programs",
}
# Which source's name, instructions and pictures win when the same exercise appears twice
SOURCE_PRIORITY = ["repdb", "fedb", "ninjas", "sto", "boostcamp"]
CREDITS = ("Exercise data by RepDB (repdb.co) · Free Exercise DB (public domain) · API Ninjas (api-ninjas.com) · "
           "Strength to Overcome functional fitness database · Boostcamp programs (Kaggle)")

EQUIPMENT_CHOICES = [
    "bodyweight", "bands", "dumbbell", "kettlebell", "stability ball", "foam roller", "medicine ball",
    "bench", "pull-up bar", "cable", "machine", "barbell", "ez bar", "suspension trainer", "sliders",
    "rings", "clubbell", "macebell", "sandbag", "landmine", "plates", "cardio machine", "other",
]
# Joe's home gym: rack with adjustable bench, Centr 1 cable machine, pull-up bar, bands, dumbbells,
# EZ-curl bar, barbell, plates (25, 2 x 10, 2.5 lb), 15 lb kettlebell, foam roller, treadmill/Peloton/rower.
# Barbell lifts are still filtered out by the safety rules.
DEFAULT_EQUIPMENT = [
    "bodyweight", "bands", "dumbbell", "kettlebell", "foam roller", "bench", "pull-up bar", "cable",
    "ez bar", "barbell", "plates", "cardio machine", "vibration plate",
    "inversion table",
]

# --- Normalization -----------------------------------------------------------------------------

_EQUIPMENT_WORDS = [
    ("band", "bands"), ("dumbbell", "dumbbell"), ("kettlebell", "kettlebell"),
    ("stability ball", "stability ball"), ("exercise ball", "stability ball"), ("swiss ball", "stability ball"),
    ("foam roll", "foam roller"), ("medicine ball", "medicine ball"), ("slam ball", "medicine ball"),
    ("wall ball", "medicine ball"), ("pull up bar", "pull-up bar"), ("pull-up bar", "pull-up bar"),
    ("bench", "bench"), ("cable", "cable"), ("smith", "machine"), ("machine", "machine"),
    ("leg press", "machine"), ("leg curl", "machine"), ("leg extension", "machine"), ("hack squat", "machine"),
    ("e-z", "ez bar"), ("ez bar", "ez bar"), ("ez curl", "ez bar"), ("trap bar", "barbell"),
    ("barbell", "barbell"), ("suspension", "suspension trainer"), ("trx", "suspension trainer"),
    ("slider", "sliders"), ("ring", "rings"), ("clubbell", "clubbell"), ("macebell", "macebell"),
    ("sandbag", "sandbag"), ("landmine", "landmine"), ("plate", "plates"), ("treadmill", "cardio machine"),
    ("bike", "cardio machine"), ("elliptical", "cardio machine"), ("rower", "cardio machine"),
]


def norm_equipment(raw):
    e = (raw or "").strip().lower().replace("_", " ")
    if e in ("", "none", "body only", "bodyweight", "body weight", "no equipment"):
        return "bodyweight"
    for word, value in _EQUIPMENT_WORDS:
        if word in e:
            return value
    return "other"


_MUSCLE_WORDS = [
    ("transverse", "abs"), ("rectus abdominis", "abs"), ("abdominal", "abs"), ("core", "abs"),
    ("oblique", "obliques"), ("erector", "lower back"), ("lower back", "lower back"),
    ("quadratus lumborum", "lower back"), ("biceps femoris", "hamstrings"), ("rectus femoris", "quads"),
    ("glute", "glutes"), ("quad", "quads"), ("vastus", "quads"), ("hamstring", "hamstrings"),
    ("semiten", "hamstrings"), ("adduct", "adductors"), ("abduct", "abductors"), ("tensor", "abductors"),
    ("hip flexor", "hip flexors"), ("iliopsoas", "hip flexors"), ("psoas", "hip flexors"),
    ("gastroc", "calves"), ("soleus", "calves"), ("calf", "calves"), ("calves", "calves"),
    ("tibialis", "shins"), ("shin", "shins"), ("pector", "chest"), ("chest", "chest"), ("serratus", "chest"),
    ("deltoid", "shoulders"), ("shoulder", "shoulders"), ("rotator", "shoulders"), ("spinatus", "shoulders"),
    ("latissimus", "lats"), ("lats", "lats"), ("rhomboid", "upper back"), ("middle back", "upper back"),
    ("upper back", "upper back"), ("teres", "upper back"), ("trapez", "traps"), ("traps", "traps"),
    ("back", "upper back"), ("brachioradialis", "forearms"), ("forearm", "forearms"), ("wrist", "forearms"),
    ("biceps", "biceps"), ("brachialis", "biceps"), ("tricep", "triceps"), ("neck", "neck"), ("abs", "abs"),
]


def muscle_group(raw):
    m = (raw or "").strip().lower().replace("_", " ")
    for word, group in _MUSCLE_WORDS:
        if word in m:
            return group
    return None


def norm_level(raw):
    v = (raw or "").strip().lower()
    if v in ("beginner", "novice"):
        return "beginner"
    if v in ("intermediate", "advanced"):
        return v
    if v:
        return "expert"
    return None


_STOP = {"the", "a", "an", "with", "and", "on", "of", "to", "exercise", "bodyweight", "body", "weight",
         "only", "version", "variation", "standard", "basic"}
_SYNONYMS = {"db": "dumbbell", "dumbbells": "dumbbell", "kb": "kettlebell", "kettlebells": "kettlebell",
             "bb": "barbell", "calves": "calf", "bands": "band", "banded": "band"}


def name_key(name):
    """Order-insensitive key so 'Dumbbell Bench Press' and 'Bench Press (Dumbbell)' match."""
    s = name.lower().replace("&", " and ").replace("-", " ")
    s = re.sub(r"\b(push|pull|sit|chin|step)ups?\b", r"\1 up", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    words = []
    for w in s.split():
        w = _SYNONYMS.get(w, w)
        if w in _STOP:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        words.append(w)
    return " ".join(sorted(words))


def _literal(v):
    """RepDB stores lists and dicts as Python-literal strings."""
    if isinstance(v, str) and v[:1] in "[{":
        try:
            return ast.literal_eval(v)
        except (ValueError, SyntaxError):
            return None
    return v


# --- Safety and goal tagging ---------------------------------------------------------------------

FLAG_REASONS = {
    "heavy_lifting": "heavy barbell or competition-style lifting",
    "high_impact": "jumping or high impact (pelvic floor)",
    "explosive": "explosive swings, throws or slams",
    "twisting": "twists the torso (pulls on the kidney adhesions)",
    "spine_loading": "weight loads the spine from above (kidney)",
    "core_pressure": "crunch, sit-up or plank-style pressure (pelvic floor, weak core)",
    "lower_back": "loads the lower back muscles the kidney is attached to",
    "inverted": "upside-down position",
    "one_sided_load": "weight on one side only (pulls on the kidney side)",
    "advanced": "advanced or expert level",
}

_FREE_WEIGHTS = {"dumbbell", "kettlebell", "barbell", "ez bar", "clubbell", "macebell", "sandbag", "landmine", "plates"}
_LOADED = _FREE_WEIGHTS | {"medicine ball", "machine", "cable"}
_HEAVY_CATEGORIES = {"powerlifting", "olympic weightlifting", "strongman"}
_AXIAL_LOAD_POSITIONS = {"overhead", "front rack", "back rack", "zercher", "shoulder", "order"}


def _rx(pattern):
    return re.compile(pattern, re.I)


_TWIST = _rx(r"twist|russian|wood ?chop|rotation|windmill|side bend|bicycle crunch|turkish|get[- ]?up|"
             r"corkscrew|\bmill\b|\bhalo\b|oblique crunch|cross[- ]body crunch|swivel")
_SPINE_LOADERS = _rx(r"squat|lunge|step[- ]?up|deadlift|good ?morning|shrug|clean|jerk|snatch|thruster|overhead|"
                     r"military|push press|shoulder press|z press|farmer|carry|march|walk|yoke|rack|zercher|calf raise")
_IMPACT = _rx(r"jump|\bhops?\b|bound|sprint|burpee|skip|plyo|depth|jacks?\b|tuck jump|\bslam|\bkip")
_EXPLOSIVE = _rx(r"swing|snatch|clean|throw|toss|\bslam|push press|jerk|ballistic")
_CORE_PRESSURE = _rx(r"sit[- ]?up|crunch|v[- ]?up|jack ?knife|leg raise|toes[- ]to[- ]bar|knees[- ]to[- ](chest|elbow)|"
                     r"hanging knee|ab wheel|roll[- ]?out|flutter|scissor|mountain climber|plank|hollow|\bl[- ]sit|"
                     r"dragon flag|windshield|spider|inchworm|walk[- ]?out|crawl")
_PLANK_OK = _rx(r"incline.*plank|plank.*incline|bear")
_LOWER_BACK = _rx(r"hyperextension|back extension|superman|reverse hyper|good ?morning")
_INVERTED = _rx(r"handstand|headstand|inver(sion|ted)|shoulder stand")
_SINGLE_ARM = _rx(r"single[- ]arm|one[- ]arm|suitcase|offset|uneven")


def safety_flags(rec):
    name, eq = rec["name"], rec["equipment"]
    flags = set()
    if rec["category"] in _HEAVY_CATEGORIES or eq == "barbell":
        flags.add("heavy_lifting")
    if rec["category"] == "plyometrics" or _IMPACT.search(name):
        flags.add("high_impact")
    if rec["category"] == "ballistics" or _EXPLOSIVE.search(name):
        flags.add("explosive")
    if _TWIST.search(name) or "rotational" in rec.get("patterns", []):
        flags.add("twisting")
    spine_loaded = _SPINE_LOADERS.search(name) or rec.get("load_position") in _AXIAL_LOAD_POSITIONS
    if eq in _FREE_WEIGHTS and spine_loaded and "no_axial_load" not in rec.get("tags", []):
        flags.add("spine_loading")
    if _CORE_PRESSURE.search(name) and not _PLANK_OK.search(name):
        flags.add("core_pressure")
    if _LOWER_BACK.search(name):
        flags.add("lower_back")
    if _INVERTED.search(name):
        flags.add("inverted")
    if eq in _LOADED and (_SINGLE_ARM.search(name) or rec.get("single_arm") or rec.get("load_position") == "suitcase"):
        flags.add("one_sided_load")
    if rec["level"] in ("advanced", "expert"):
        flags.add("advanced")
    return flags


_LEG_MUSCLES = {"quads", "glutes", "hamstrings", "adductors", "abductors", "calves", "shins", "hip flexors"}


def goal_tags(rec):
    muscles, goals = set(rec["muscles"]), set()
    if rec["category"] == "stretching":
        goals.add("mobility")
    if rec["category"] in ("strength", "balance"):
        if muscles & _LEG_MUSCLES:
            goals.add("legs")
        if muscles & {"upper back", "lats", "traps"}:
            goals.add("upper back")
        if muscles & {"abs", "obliques"}:
            goals.add("core")
    if rec["category"] == "balance":
        goals.add("balance")
    return goals


def dose_for(entry):
    """Conservative default dose for library exercises: (text, sets)."""
    name = entry["name"].lower()
    if entry["equipment"] == "foam roller":
        return "60 s per area, gentle pressure", 1
    if entry["category"] == "stretching":
        return "2 x 30 s (each side if one-sided)", 2
    if "hold" in name or "isometric" in name or "isometric hold" in entry.get("details", {}).get("patterns", []):
        return "2 x 20-30 s hold", 2
    return "2 x 10-12, light and slow. Stop if your left flank pulls.", 2


# --- Source loaders: each returns records with a common shape -------------------------------------

def _record(source, name, category, level, equipment, muscles, **extra):
    rec = {"source": source, "name": name.strip(), "category": category, "level": level,
           "equipment": equipment, "muscles": sorted({m for m in muscles if m}), "instructions": [],
           "tips": [], "images": [], "tags": [], "patterns": [], "load_position": None,
           "single_arm": False, "sets": None, "reps": None}
    rec.update(extra)
    return rec


def load_fedb():
    out = []
    for e in json.load(open(FEDB_FILE, encoding="utf-8")):
        muscles = [muscle_group(m) for m in e.get("primaryMuscles", []) + e.get("secondaryMuscles", [])]
        out.append(_record(
            "fedb", e["name"], e["category"], norm_level(e.get("level")), norm_equipment(e.get("equipment")),
            muscles, instructions=e.get("instructions") or [],
            images=[FEDB_IMAGES + p for p in e.get("images", [])[:2]]))
    return out


def load_repdb(path):
    raw = json.load(open(path, encoding="utf-8"))
    rows = raw.get("exercises") if isinstance(raw, dict) else raw
    if rows is None:
        rows = next(v for v in raw.values() if isinstance(v, list))
    category_map = {"olympic": "olympic weightlifting"}
    out = []
    for e in rows:
        muscles = [muscle_group(m) for m in (_literal(e.get("primary_muscles")) or []) + (_literal(e.get("secondary_muscles")) or [])]
        flat = ((_literal(e.get("images")) or {}).get("flat") or {})
        images = [REPDB_BASE + flat[k] for k in ("start", "peak", "main") if flat.get(k)][:2]
        out.append(_record(
            "repdb", e["name_en"], category_map.get(e.get("category"), e.get("category")),
            norm_level(e.get("difficulty")), norm_equipment(e.get("equipment")), muscles,
            instructions=_literal(e.get("instructions_en")) or [], tips=_literal(e.get("tips_en")) or [],
            images=images, tags=_literal(e.get("tags")) or [],
            single_arm=str(e.get("is_unilateral")) == "True" and norm_equipment(e.get("equipment")) in _LOADED))
    return out


_STO_CATEGORIES = {"plyometric": "plyometrics", "olympic weightlifting": "olympic weightlifting",
                   "powerlifting": "powerlifting", "mobility": "stretching", "balance": "balance",
                   "ballistics": "ballistics"}


def load_sto(path):
    rows = list(csv.reader(io.open(path, encoding="utf-8", errors="replace", newline="")))
    header_at = next(i for i, r in enumerate(rows) if r and "Exercise" in [c.strip() for c in r])
    header = [c.strip() for c in rows[header_at]]
    col = {h: i for i, h in enumerate(header) if h}

    def get(r, h):
        i = col.get(h)
        return r[i].strip() if i is not None and i < len(r) else ""

    out = []
    for r in rows[header_at + 1:]:
        name = get(r, "Exercise")
        if not name:
            continue
        muscles = [muscle_group(get(r, h)) for h in ("Target Muscle Group", "Prime Mover Muscle", "Secondary Muscle")]
        patterns = [get(r, f"Movement Pattern #{n}").lower() for n in (1, 2, 3)]
        out.append(_record(
            "sto", name, _STO_CATEGORIES.get(get(r, "Primary Exercise Classification").lower(), "strength"),
            norm_level(get(r, "Difficulty Level")), norm_equipment(get(r, "Primary Equipment")), muscles,
            patterns=[p for p in patterns if p and p != "unsorted*"],
            load_position=get(r, "Load Position (Ending)").lower() or None,
            single_arm=get(r, "Single or Double Arm") == "Single Arm",
            details={"posture": get(r, "Posture"), "body_region": get(r, "Body Region")}))
    return out


_BOOSTCAMP_MUSCLES = [
    (r"leg curl|romanian|rdl|hamstring|nordic", ["hamstrings", "glutes"]), (r"squat|lunge|leg press|step[- ]?up|leg extension", ["quads", "glutes"]),
    (r"hip thrust|glute|bridge|kickback", ["glutes"]), (r"adduct", ["adductors"]), (r"abduct", ["abductors"]),
    (r"calf", ["calves"]), (r"deadlift", ["hamstrings", "glutes", "lower back"]), (r"pulldown|pull[- ]?up|chin[- ]?up", ["lats"]),
    (r"\brow\b|rows\b|face pull|reverse fly|rear delt", ["upper back"]), (r"shrug", ["traps"]),
    (r"bench|chest|fly|push[- ]?up|dip", ["chest", "triceps"]), (r"lateral raise|shoulder|overhead press|military|front raise", ["shoulders"]),
    (r"curl", ["biceps"]), (r"tricep|pushdown|skull", ["triceps"]), (r"crunch|sit[- ]?up|plank|ab |abs|core|dead ?bug|pallof", ["abs"]),
    (r"oblique|side bend", ["obliques"]), (r"stretch|mobility", []),
]


def load_boostcamp():
    out = []
    for e in json.load(open(BOOSTCAMP_FILE, encoding="utf-8"))["exercises"]:
        # Names used in only one program are mostly custom one-offs or typos
        if e["programs"] < 2:
            continue
        name = e["name"]
        hint = re.search(r"\(([^)]+)\)", name)
        equipment = norm_equipment(hint.group(1)) if hint else norm_equipment(name)
        if equipment == "other" and not hint:
            equipment = "bodyweight" if re.search(r"(?i)push ?up|pull ?up|chin ?up|plank|crunch|stretch|hold|bridge", name) else "other"
        muscles = next((m for p, m in _BOOSTCAMP_MUSCLES if re.search(p, name, re.I)), [])
        if re.search(r"(?i)stretch|mobility", name):
            category = "stretching"
        elif re.search(r"(?i)\b\d+\s?(m|km|k|cal|min)\b|\brun\b|\berg\b|assault|bike|sprint", name):
            category = "cardio"
        else:
            category = "strength"
        out.append(_record("boostcamp", name, category, None, equipment, muscles, sets=e.get("sets"), reps=e.get("reps")))
    return out


# --- Merge, pictures and storage ------------------------------------------------------------------

_LEVELS = [None, "beginner", "intermediate", "advanced", "expert"]
_MOVEMENTS = {"press", "row", "squat", "lunge", "curl", "raise", "stretch", "bridge", "deadlift", "pulldown",
              "fly", "extension", "thrust", "kickback", "walk", "pose", "hold", "crunch", "plank", "dip", "shrug",
              "pull", "push", "carry", "swing", "step", "rotation", "twist", "slide", "march", "reach"}


def merge(records):
    groups = {}
    for rec in records:
        groups.setdefault(name_key(rec["name"]), []).append(rec)
    merged = []
    for key, recs in groups.items():
        recs.sort(key=lambda r: SOURCE_PRIORITY.index(r["source"]))
        primary = recs[0]
        pick = lambda field: next((r[field] for r in recs if r[field]), primary[field])
        entry = {
            "key": key, "name": primary["name"],
            "sources": sorted({r["source"] for r in recs}, key=SOURCE_PRIORITY.index),
            "category": primary["category"],
            "level": max((r["level"] for r in recs), key=_LEVELS.index),
            "equipment": next((r["equipment"] for r in recs if r["equipment"] != "other"), primary["equipment"]),
            "muscles": sorted({m for r in recs for m in r["muscles"]}),
            "instructions": pick("instructions"), "tips": pick("tips"), "images": pick("images"),
            "image_match": "exact" if pick("images") else None,
            "typical_sets": pick("sets"), "typical_reps": pick("reps"),
            "details": {"patterns": sorted({p for r in recs for p in r["patterns"]}),
                        "load_position": pick("load_position"),
                        **next((r["details"] for r in recs if r.get("details")), {})},
        }
        # Conservative: an exercise is flagged if any source's data flags it
        flags = set()
        for r in recs:
            flags |= safety_flags(r)
        entry["flags"] = sorted(flags)
        entry["goals"] = sorted(goal_tags(entry))
        merged.append(entry)
    _borrow_pictures(merged)
    return merged


def _borrow_pictures(entries):
    """Give exercises without pictures the pictures of the closest similar movement."""
    pictured = [e for e in entries if e["images"]]
    index = {}
    for i, e in enumerate(pictured):
        for w in set(e["key"].split()):
            index.setdefault(w, []).append(i)
    for e in entries:
        if e["images"]:
            continue
        words = set(e["key"].split())
        moves = words & _MOVEMENTS
        if not moves:
            continue
        candidates = set()
        for w in moves:
            candidates.update(index.get(w, []))
        best, best_score = None, 0.0
        for i in candidates:
            c = pictured[i]
            cwords = set(c["key"].split())
            if not moves <= cwords:
                continue
            score = len(words & cwords) / len(words | cwords) + (0.15 if c["equipment"] == e["equipment"] else 0)
            if score > best_score:
                best, best_score = c, score
        if best and best_score >= 0.5:
            e["images"] = best["images"]
            e["image_match"] = f"similar: {best['name']}"


def _cached_download(url, filename):
    """Local copy of a downloadable source, refreshed every REFRESH_DAYS. None if never downloaded."""
    path = os.path.join(CACHE_DIR, filename)
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < REFRESH_DAYS * 86400
    if not fresh:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": "ai-workout-tracker"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            with open(path + ".tmp", "wb") as f:
                f.write(data)
            os.replace(path + ".tmp", path)
        except Exception as e:
            print(f"Exercise library: could not download {filename}: {e}", flush=True)
    return path if os.path.exists(path) else None


def _source_files():
    files = {"fedb": FEDB_FILE, "boostcamp": BOOSTCAMP_FILE,
             "repdb": _cached_download(REPDB_BASE + "exercises.json", "repdb.json"),
             "sto": _cached_download(STO_URL, "strength-to-overcome.csv")}
    # API Ninjas is harvested in the background by ninjas_sync.py when a key is set
    import ninjas_sync
    if os.path.exists(ninjas_sync.STATE_FILE):
        files["ninjas"] = ninjas_sync.STATE_FILE
    return {k: v for k, v in files.items() if v}


def _signature(files):
    parts = [LIBRARY_VERSION] + [f"{k}:{os.path.getsize(p)}:{int(os.path.getmtime(p))}" for k, p in sorted(files.items())]
    return "|".join(parts)


SCHEMA = """
    CREATE TABLE IF NOT EXISTS exercise_library (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        key TEXT UNIQUE,
        sources JSON,
        category TEXT,
        level TEXT,
        equipment TEXT,
        primary_muscle TEXT,
        muscles JSON,
        goal_tags JSON,
        constraint_tags JSON,   -- safety flags; empty means safe for Joe
        safe INTEGER,
        impact_level TEXT,
        instructions JSON,
        tips JSON,
        images JSON,
        image_match TEXT,       -- 'exact', 'similar: <exercise>' or NULL
        typical_sets REAL,
        typical_reps REAL,
        details JSON
    )
"""


def _ensure_schema(conn):
    c = conn.cursor()
    cols = [r[1] for r in c.execute("PRAGMA table_info(exercise_library)")]
    if cols and "key" not in cols:
        # Table from 0.1.x: it was never filled, so replace it (keep it aside if someone added rows)
        if c.execute("SELECT count(*) FROM exercise_library").fetchone()[0]:
            c.execute("ALTER TABLE exercise_library RENAME TO exercise_library_old")
        else:
            c.execute("DROP TABLE exercise_library")
    c.execute(SCHEMA)
    c.execute("CREATE TABLE IF NOT EXISTS library_meta (key TEXT PRIMARY KEY, value TEXT)")


def build(db_path, force=False):
    """Rebuilds the exercise_library table when a source or the rules changed."""
    files = _source_files()
    signature = _signature(files)
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    c = conn.cursor()
    row = c.execute("SELECT value FROM library_meta WHERE key = 'signature'").fetchone()
    if row and row[0] == signature and not force:
        conn.close()
        return None

    import ninjas_sync
    loaders = {"fedb": load_fedb, "boostcamp": load_boostcamp, "repdb": load_repdb, "sto": load_sto,
               "ninjas": ninjas_sync.load_records}
    records, counts = [], {}
    for source, path in files.items():
        try:
            recs = loaders[source]() if source in ("fedb", "boostcamp") else loaders[source](path)
        except Exception as e:
            print(f"Exercise library: skipped {SOURCE_NAMES[source]}: {e}", flush=True)
            continue
        counts[source] = len(recs)
        records.extend(recs)
    entries = merge(records)

    c.execute("DELETE FROM exercise_library")
    c.executemany(
        """INSERT INTO exercise_library (name, key, sources, category, level, equipment, primary_muscle, muscles,
               goal_tags, constraint_tags, safe, impact_level, instructions, tips, images, image_match,
               typical_sets, typical_reps, details)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(e["name"], e["key"], json.dumps(e["sources"]), e["category"], e["level"], e["equipment"],
          e["muscles"][0] if e["muscles"] else None, json.dumps(e["muscles"]), json.dumps(e["goals"]),
          json.dumps(e["flags"]), 0 if e["flags"] else 1,
          "high" if "high_impact" in e["flags"] else "low", json.dumps(e["instructions"]), json.dumps(e["tips"]),
          json.dumps(e["images"]), e["image_match"], e["typical_sets"], e["typical_reps"], json.dumps(e["details"]))
         for e in entries])
    c.execute("INSERT OR REPLACE INTO library_meta (key, value) VALUES ('signature', ?)", (signature,))
    conn.commit()
    conn.close()
    safe = sum(1 for e in entries if not e["flags"])
    pictured = sum(1 for e in entries if e["images"])
    summary = {"sources": counts, "exercises": len(entries), "safe": safe, "with_pictures": pictured}
    print(f"Exercise library built: {summary}", flush=True)
    return summary


EQUIPMENT_OPTIONS = [
    "bodyweight", "bands", "dumbbell", "kettlebell", "stability ball", "foam roller", "massage ball", "medicine ball",
    "bench", "squat rack", "pull-up bar", "cable", "machine", "barbell", "ez bar", "suspension trainer", "sliders",
    "rings", "clubbell", "macebell", "sandbag", "landmine", "plates", "cardio machine", "treadmill", "bike",
    "rower", "vibration plate", "inversion table", "other",
]

# What the coach is told about the gym (editable in Settings). Weights matter: the coach can only
# prescribe loads you can actually build.
DEFAULT_GEAR_NOTES = (
    "Cardio: treadmill, Peloton bike, KingSmith water rower.\n"
    "Strength: squat rack, adjustable bench (flat/incline/decline), Centr 1 cable machine / functional trainer "
    "with Marsafit ergonomic grips, Rage pull-up bar.\n"
    "Free weights: dumbbells 5-35 lb; barbell with six 25 lb bumper plates, about ten 2.5 lb plates and a 10 lb "
    "bumper set; EZ-curl bar; 15 lb kettlebell; bands 30, 50 and 70 lb.\n"
    "Recovery: vibration board, inversion table, Rage recovery set (foam roller, massage ball). "
    "Joe's PT said the vibration board could help, and Joe says both it and the inversion table are fine at any "
    "symptom level and helpful when he is tight: use the vibration board for recovery on the lowest setting in short "
    "sessions, and the inversion table for gentle decompression at a shallow angle after training."
)

# App settings live in one JSON file next to the database so they survive updates and can grow
# (equipment now; sports and training goals later). The Settings tab is the only thing that writes it.
SETTINGS_PATH = os.getenv("SETTINGS_PATH", "/config/workout_tracker/settings.json")


def load_settings(path=None):
    try:
        with open(path or SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


_settings_lock = threading.Lock()


def save_settings(patch, path=None):
    # one writer at a time: background checks (reminders, PT office) also save, and a lost update would drop a setting
    path = path or SETTINGS_PATH
    with _settings_lock:
        settings = load_settings(path)
        settings.update(patch)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp, path)
    return settings


def selected_equipment(options_path="/data/options.json"):
    """Equipment chosen in the Settings tab, else the add-on Configuration tab, else the defaults."""
    chosen = load_settings().get("equipment")
    if chosen is None:
        try:
            chosen = json.load(open(options_path, encoding="utf-8")).get("equipment")
        except (OSError, ValueError):
            chosen = None
    return chosen or DEFAULT_EQUIPMENT


def get_library(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM exercise_library ORDER BY name").fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    out = []
    for r in rows:
        e = dict(r)
        for field in ("sources", "muscles", "goal_tags", "constraint_tags", "instructions", "tips", "images", "details"):
            e[field] = json.loads(e[field] or "null") or ([] if field != "details" else {})
        e["safe"] = bool(e["safe"])
        out.append(e)
    return out


if __name__ == "__main__":
    print(build(os.getenv("DB_PATH", "workout_tracker.db"), force=True))
