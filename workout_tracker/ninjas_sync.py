"""API Ninjas exercise harvester that works within the free tier.

The free tier only offers /v1/exercises: at most 5 results per call, no paging, 100 calls/hour and
3,000 calls/month. To still collect the catalogue it "snowballs": every word (and word pair) in the
names found so far becomes a name search, rarest words first, because a search with 4 or fewer
results is complete. Searches that come back full (5 results) are narrowed by muscle, then
difficulty, type and equipment. Offline tests found ~80% of a 1,400-exercise catalogue in 2,500
calls. Progress is saved after every call, so the harvest resumes across restarts and months.

The API key comes from the add-on Configuration tab (/data/options.json) and never leaves the Green.
"""
import collections
import datetime
import heapq
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.api-ninjas.com/v1/exercises"
CACHE_DIR = os.getenv("LIBRARY_CACHE_DIR", "/config/workout_tracker/sources")
STATE_FILE = os.path.join(CACHE_DIR, "api-ninjas.json")
OPTIONS_FILE = "/data/options.json"

PAGE_SIZE = 5            # free tier returns at most 5 results per call
HOURLY_LIMIT = 90        # free tier allows 100/hour; keep headroom for other uses of the key
DEFAULT_MONTHLY_BUDGET = 2500   # free tier allows 3,000/month
REBUILD_EVERY = 25       # rebuild the exercise library after this many calls

# "shoulders" is missing from the API docs' list; if the API rejects it, that one search is skipped
MUSCLES = ["abdominals", "abductors", "adductors", "biceps", "calves", "chest", "forearms", "glutes",
           "hamstrings", "lats", "lower_back", "middle_back", "neck", "quadriceps", "shoulders", "traps", "triceps"]
DIFFICULTIES = ["beginner", "intermediate", "expert"]
TYPES = ["strength", "stretching", "cardio", "plyometrics", "powerlifting", "olympic_weightlifting", "strongman"]
# Partial matches: "machine" matches every machine, "band" every band, "bar" barbells and pull-up bars
EQUIPMENT_TERMS = ["machine", "bench", "barbell", "dumbbell", "kettlebell", "cable", "band", "ball", "bar",
                   "plate", "box", "roller", "ring", "rope", "weight", "sled", "slider", "suspension", "landmine"]
SEED_WORDS = ["press", "curl", "row", "squat", "lunge", "raise", "extension", "fly", "pull", "push",
              "deadlift", "bridge", "stretch", "hold", "plank", "crunch", "twist", "walk", "carry", "kick",
              "thrust", "shrug", "dip", "swing", "jump", "march", "slide", "reach", "circle", "roll", "pose",
              "bend", "lift", "rotation"]
_STOPWORDS = {"with", "and", "the", "to", "on", "of"}

# Lower runs first: seeds, then word searches (rarest first), then word pairs, then narrowing
_WORD, _PAIR, _NARROW = 1.0, 1.5, 2.0


def _query_key(query):
    return json.dumps(query, sort_keys=True)


def _words(name):
    return re.findall(r"[a-z0-9]+", name.lower())


def _narrower(query):
    """Narrower searches for a query that came back full."""
    if "muscle" not in query:
        return [dict(query, muscle=m) for m in MUSCLES]
    if "difficulty" not in query:
        return [dict(query, difficulty=d) for d in DIFFICULTIES]
    if "type" not in query:
        return [dict(query, type=t) for t in TYPES]
    if "equipments" not in query:
        return [dict(query, equipments=e) for e in EQUIPMENT_TERMS]
    return []


class Harvester:
    def __init__(self, state_file=STATE_FILE):
        self.state_file = state_file
        self.state = self._load()
        self.done = set(self.state["done"])
        self.word_counts = collections.Counter(
            w for n in self.state["exercises"] for w in set(_words(n)))

    def _load(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, encoding="utf-8") as f:
                return json.load(f)
        queue = [[0.0, i, {"name": w}] for i, w in enumerate(SEED_WORDS)]
        queue += [[0.0, len(queue) + i, {"muscle": m}] for i, m in enumerate(MUSCLES)]
        return {"version": 2, "exercises": {}, "queue": queue, "done": [], "seq": len(queue),
                "calls_by_month": {}, "hour_start": 0, "hour_calls": 0, "blocked_until": 0,
                "completed_at": None}

    def save(self):
        self.state["done"] = sorted(self.done)
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        tmp = self.state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f)
        os.replace(tmp, self.state_file)

    def _push(self, priority, query):
        if _query_key(query) not in self.done:
            self.state["seq"] += 1
            heapq.heappush(self.state["queue"], [priority, self.state["seq"], query])

    # --- Budget --------------------------------------------------------------------------------

    def _month(self, now):
        return datetime.datetime.fromtimestamp(now).strftime("%Y-%m")

    def wait_seconds(self, now, monthly_budget):
        """0 when a call may be made now, otherwise how long to wait."""
        s = self.state
        if now < s["blocked_until"]:
            return s["blocked_until"] - now
        if s["calls_by_month"].get(self._month(now), 0) >= monthly_budget:
            return 3600   # check again hourly; the count resets with the new month
        if now - s["hour_start"] >= 3600:
            s["hour_start"], s["hour_calls"] = now, 0
        if s["hour_calls"] >= HOURLY_LIMIT:
            return s["hour_start"] + 3600 - now
        return 0

    def _count_call(self, now):
        month = self._month(now)
        self.state["calls_by_month"][month] = self.state["calls_by_month"].get(month, 0) + 1
        self.state["hour_calls"] += 1

    # --- Crawl ---------------------------------------------------------------------------------

    def step(self, fetch, now=None):
        """Runs one search. Returns False when there is nothing left to search."""
        s = self.state
        if not s["queue"]:
            s["completed_at"] = s["completed_at"] or (now or time.time())
            return False
        heapq.heapify(s["queue"])
        item = heapq.heappop(s["queue"])
        query = item[2]
        key = _query_key(query)
        if key in self.done:
            return True
        now = now or time.time()
        try:
            results = fetch(query)
        except urllib.error.HTTPError as e:
            self._count_call(now)
            if e.code == 429:
                s["blocked_until"] = now + 3600
                heapq.heappush(s["queue"], item)
            else:
                print(f"API Ninjas: search {query} failed ({e.code}); skipping it", flush=True)
                self.done.add(key)
            return True
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"API Ninjas: search {query} failed ({e}); will retry", flush=True)
            s["blocked_until"] = now + 600
            heapq.heappush(s["queue"], item)
            return True

        self._count_call(now)
        self.done.add(key)
        new = []
        for r in results:
            name = (r.get("name") or "").strip()
            if name and name not in s["exercises"]:
                s["exercises"][name] = r
                new.append(name)
        for name in new:
            words = _words(name)
            for w in set(words):
                self.word_counts[w] += 1
            # Snowball: search each word of a new name, rarest first, then neighbouring word pairs
            for w in set(words):
                if len(w) > 2 and w not in _STOPWORDS:
                    self._push(_WORD + self.word_counts[w] * 0.01, {"name": w})
            for a, b in zip(words, words[1:]):
                self._push(_PAIR + self.word_counts[a] * 0.01, {"name": f"{a} {b}"})
        if len(results) >= PAGE_SIZE:
            for child in _narrower(query):
                self._push(_NARROW + len(query) - len(new) * 0.1, child)
        return True


def fetch_from_api(api_key):
    def fetch(query):
        url = API_URL + "?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(url, headers={"X-Api-Key": api_key, "User-Agent": "ai-workout-tracker"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    return fetch


def load_options():
    try:
        with open(OPTIONS_FILE, encoding="utf-8") as f:
            options = json.load(f)
    except (OSError, ValueError):
        options = {}
    key = "".join((options.get("api_ninjas_key") or "").split())
    budget = int(options.get("api_ninjas_monthly_budget") or DEFAULT_MONTHLY_BUDGET)
    return key, min(budget, 3000)


def run_forever(rebuild):
    """Background loop for the add-on: harvests within budget and rebuilds the library as it goes."""
    key, budget = load_options()
    if not key:
        print("API Ninjas: no API key set, so its exercises are skipped.", flush=True)
        return
    harvester = Harvester()
    fetch = fetch_from_api(key)
    since_rebuild = 0
    while True:
        wait = harvester.wait_seconds(time.time(), budget)
        if wait > 0:
            if since_rebuild:
                rebuild()
                since_rebuild = 0
            time.sleep(min(wait, 3600))
            continue
        if not harvester.step(fetch):
            harvester.save()
            if since_rebuild:
                rebuild()
            found = len(harvester.state["exercises"])
            print(f"API Ninjas: harvest complete, {found} exercises.", flush=True)
            return
        harvester.save()
        since_rebuild += 1
        if since_rebuild >= REBUILD_EVERY:
            rebuild()
            since_rebuild = 0
        time.sleep(2)   # be gentle with the API


def status(state_file=STATE_FILE):
    """Harvest progress for the app, or None before the first search."""
    if not os.path.exists(state_file):
        return None
    with open(state_file, encoding="utf-8") as f:
        state = json.load(f)
    month = datetime.datetime.now().strftime("%Y-%m")
    return {"exercises": len(state["exercises"]), "calls_this_month": state["calls_by_month"].get(month, 0),
            "complete": bool(state.get("completed_at"))}


def load_records(state_file=STATE_FILE):
    """Harvested exercises in the exercise library's common record shape."""
    import library
    if not os.path.exists(state_file):
        return []
    with open(state_file, encoding="utf-8") as f:
        exercises = json.load(f).get("exercises", {})
    out = []
    for e in exercises.values():
        equipment = e.get("equipments") or e.get("equipment") or []
        if isinstance(equipment, str):
            equipment = [equipment]
        steps = [s.strip() for s in re.split(r"(?<=[.!?])\s+", e.get("instructions") or "") if s.strip()]
        category = (e.get("type") or "strength").replace("_", " ")
        out.append(library._record(
            "ninjas", e["name"], category, library.norm_level(e.get("difficulty")),
            library.norm_equipment(equipment[0] if equipment else ""),
            [library.muscle_group(e.get("muscle"))],
            instructions=steps, tips=[e["safety_info"]] if e.get("safety_info") else [],
            images=(e.get("images") or [])[:2]))   # only paid keys return images
    return out


if __name__ == "__main__":
    import db
    if "--status" in sys.argv:
        state = Harvester().state
        print(json.dumps({"exercises": len(state["exercises"]), "queued": len(state["queue"]),
                          "calls_by_month": state["calls_by_month"], "completed_at": state["completed_at"]}))
    else:
        run_forever(lambda: __import__("library").build(db.DB_PATH))
