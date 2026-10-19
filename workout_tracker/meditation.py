"""Guided meditation practices from The Holistic Care's free Stillness Library (no key needed).
The page plays the MP3s straight from their server; nothing is stored here."""
import json
import threading
import time
import urllib.request

API = "https://api.theholisticcare.com/v1/practices"
CREDIT = "Practices: The Holistic Care Stillness Library (theholisticcare.com), free to listen."
# Skipped: aimed at kids and students
SKIP = {"children", "students"}
LABELS = {"mindfulness": "Mindfulness", "breathwork": "Breathwork", "yoga-nidra": "Yoga nidra", "sleep": "Sleep",
          "nondual-awareness": "Open awareness"}

_cache = {"at": 0.0, "items": []}
_lock = threading.Lock()


def _fetch():
    items, offset = [], 0
    while offset < 400:
        req = urllib.request.Request(f"{API}?limit=100&offset={offset}", headers={"User-Agent": "ai-workout-tracker"})
        with urllib.request.urlopen(req, timeout=20) as r:
            page = json.load(r)
        data = page.get("data") or []
        items += data
        offset += len(data)
        if not data or offset >= (page.get("pagination") or {}).get("total", 0):
            break
    return items


def practices():
    """Cached for a day. Returns (list, error)."""
    with _lock:
        if _cache["items"] and time.time() - _cache["at"] < 86400:
            return _cache["items"], None
        try:
            raw = _fetch()
        except Exception as e:  # offline, API down: show what we had before
            return _cache["items"], None if _cache["items"] else f"Couldn't reach the meditation library ({e})."
        _cache["items"] = [
            {"id": p["id"], "title": p["title"].split(":")[0].strip(), "category": p.get("category"),
             "label": LABELS.get(p.get("category"), (p.get("category") or "").title()),
             "minutes": p.get("read_time_minutes"), "excerpt": p.get("excerpt"), "audio_url": p.get("audio_url"),
             "url": p.get("canonical_url")}
            for p in raw if p.get("audio_url") and p.get("category") not in SKIP
        ]
        _cache["at"] = time.time()
        return _cache["items"], None
