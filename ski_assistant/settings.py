"""User settings in one small JSON file (rewritten only when the user saves)."""
import json
import os

PATH = os.getenv("SETTINGS_PATH", "/config/ski_settings.json")

DEFAULTS = {
    # Departure points for drive time. Home is a placeholder (downtown Denver): edit it in Settings.
    "departures": [{"name": "Home", "lat": 39.7392, "lon": -104.9903}],
    "default_departure": "Home",
    "arrive_by": "08:30",          # when you want to be at the lifts
    "buffer_min": 20,              # parking, boots, lift line
    "wax_every_days": {"board": 5, "ski": 5},
    "tune_every_days": {"board": 15, "ski": 15},
    # Home Assistant tie-ins; leave blank to skip
    "phone_service": "",           # e.g. mobile_app_pixel
    "tts_entity": "",              # e.g. tts.home_assistant_cloud
    "speaker_entity": "",          # media_player to announce on
    "powder_lights": [],           # light/switch entities to turn on for a powder morning
    "wake_time": "06:30",
    "tracker_entity": "",          # device_tracker for your phone
    "climate_entity": "",
    "normal_temp_f": 68,
    "drying_reminder": True,
    "waze_sensors": {},            # {resort_id: sensor.entity_id}; empty = match Waze sensors by name
}


def load():
    s = json.loads(json.dumps(DEFAULTS))
    try:
        with open(PATH, encoding="utf-8") as f:
            s.update(json.load(f))
    except (OSError, ValueError):
        pass
    return s


def save(patch):
    s = load()
    for k, v in patch.items():
        if k in DEFAULTS:
            s[k] = v
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)
    return s


def departure(name=None):
    s = load()
    name = name or s["default_departure"]
    deps = s["departures"]
    return next((d for d in deps if d["name"] == name), deps[0])
