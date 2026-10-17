"""Home Assistant calls through the Supervisor (SUPERVISOR_TOKEN is given to add-ons with homeassistant_api: true).
Every function raises on failure; callers in scheduler.py wrap them so one broken entity never stops the rest."""
import json
import os
import urllib.request

CORE = "http://supervisor/core/api"
SUPERVISOR = "http://supervisor"


def available():
    return bool(os.getenv("SUPERVISOR_TOKEN"))


def _call(method, url, body=None, timeout=10):
    req = urllib.request.Request(
        url, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {os.getenv('SUPERVISOR_TOKEN', '')}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def service(domain, name, data):
    return _call("POST", f"{CORE}/services/{domain}/{name}", data)


def get_state(entity_id):
    return _call("GET", f"{CORE}/states/{entity_id}")


def set_state(entity_id, state, attributes):
    return _call("POST", f"{CORE}/states/{entity_id}", {"state": str(state)[:255], "attributes": attributes})


def notify_services():
    """Phone notification services from the companion app, e.g. ["mobile_app_pixel"]."""
    try:
        for domain in _call("GET", f"{CORE}/services") or []:
            if domain.get("domain") == "notify":
                names = sorted(domain.get("services", {}))
                return [n for n in names if n.startswith("mobile_app")] + [n for n in names if not n.startswith("mobile_app")]
    except Exception:
        pass
    return []


_panel = {"url": None}


def panel_url():
    """Where a tapped notification opens: this add-on's page in Home Assistant."""
    if _panel["url"] is None:
        try:
            slug = (_call("GET", f"{SUPERVISOR}/addons/self/info") or {}).get("data", {}).get("slug")
            _panel["url"] = f"/hassio/ingress/{slug}" if slug else ""
        except Exception:
            _panel["url"] = ""
    return _panel["url"] or None


def notify(phone_service, title, message):
    data = {}
    url = panel_url()
    if url:
        data = {"clickAction": url, "url": url}  # Android uses clickAction, iPhone uses url
    return service("notify", phone_service, {"title": title, "message": message, "data": data})


def speak(tts_entity, speaker_entity, message):
    return service("tts", "speak", {"entity_id": tts_entity, "media_player_entity_id": speaker_entity, "message": message})


def turn_on(entities):
    for e in entities:
        service("homeassistant", "turn_on", {"entity_id": e})


def set_temperature(climate_entity, temp_f):
    return service("climate", "set_temperature", {"entity_id": climate_entity, "temperature": temp_f})


def shopping_add(item):
    return service("shopping_list", "add_item", {"name": item})
