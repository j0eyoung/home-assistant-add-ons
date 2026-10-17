"""Resort list. Seeded with the Colorado resorts below; editable by writing RESORTS_PATH (JSON list).

Ikon list verified 2026-10-16 against ikonpass.com/en/destinations: Winter Park, Steamboat, Copper,
Eldora, Arapahoe Basin (unlimited on the full pass), Aspen Snowmass (7 days on the full pass).
Keystone is Vail/Epic, not Ikon: the user has a separate Keystone pass ("keystone").
Elevations are in feet; drive_min is typical Denver-to-resort minutes in good traffic."""
import json
import os

RESORTS_PATH = os.getenv("RESORTS_PATH", "/config/ski_resorts.json")

DEFAULT_RESORTS = [
    {"id": "winter_park", "name": "Winter Park", "lat": 39.8868, "lon": -105.7625, "base_ft": 9000, "summit_ft": 12060,
     "pass": "ikon", "pass_days": None, "snotel": ["1186:CO:SNTL", "335:CO:SNTL"], "drive_min": 85, "i70": True},
    {"id": "steamboat", "name": "Steamboat", "lat": 40.4572, "lon": -106.8045, "base_ft": 6900, "summit_ft": 10568,
     "pass": "ikon", "pass_days": None, "snotel": ["825:CO:SNTL"], "drive_min": 200, "i70": True},
    {"id": "copper", "name": "Copper Mountain", "lat": 39.5017, "lon": -106.1510, "base_ft": 9712, "summit_ft": 12441,
     "pass": "ikon", "pass_days": None, "snotel": ["415:CO:SNTL", "485:CO:SNTL"], "drive_min": 80, "i70": True},
    {"id": "eldora", "name": "Eldora", "lat": 39.9372, "lon": -105.5827, "base_ft": 9200, "summit_ft": 10600,
     "pass": "ikon", "pass_days": None, "snotel": ["663:CO:SNTL"], "drive_min": 60, "i70": False},
    {"id": "abasin", "name": "Arapahoe Basin", "lat": 39.6426, "lon": -105.8719, "base_ft": 10780, "summit_ft": 13050,
     "pass": "ikon", "pass_days": None, "snotel": ["505:CO:SNTL"], "drive_min": 75, "i70": True},
    {"id": "aspen_snowmass", "name": "Aspen Snowmass", "lat": 39.2084, "lon": -106.9490, "base_ft": 8104, "summit_ft": 12510,
     "pass": "ikon", "pass_days": 7, "snotel": ["542:CO:SNTL"], "drive_min": 210, "i70": True},
    {"id": "keystone", "name": "Keystone", "lat": 39.6050, "lon": -105.9540, "base_ft": 9280, "summit_ft": 12408,
     "pass": "keystone", "pass_days": None, "snotel": ["602:CO:SNTL", "505:CO:SNTL"], "drive_min": 75, "i70": True},
]

_REQUIRED = {"id", "name", "lat", "lon", "base_ft", "summit_ft"}


def load():
    """User's edited list if present and valid, else the defaults."""
    try:
        with open(RESORTS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data and all(_REQUIRED <= set(r) for r in data):
            return data
    except (OSError, ValueError):
        pass
    return [dict(r) for r in DEFAULT_RESORTS]


def save(resorts):
    for r in resorts:
        missing = _REQUIRED - set(r)
        if missing:
            raise ValueError(f"resort {r.get('id', '?')} missing {sorted(missing)}")
    with open(RESORTS_PATH, "w", encoding="utf-8") as f:
        json.dump(resorts, f, indent=1)


def mid_ft(r):
    return (r["base_ft"] + r["summit_ft"]) / 2
