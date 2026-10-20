"""Home Assistant bridge through the Supervisor: reads states, calendars, forecasts and to-do lists, publishes the
sensor.daily_briefing_* sensors and sends the morning phone summary.

Add-ons get SUPERVISOR_TOKEN with homeassistant_api: true, so there is nothing to set up but the phone."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import config

CORE = "http://supervisor/core/api"
SUPERVISOR = "http://supervisor"


def _token():
    return os.getenv("SUPERVISOR_TOKEN", "")


def available():
    return bool(_token())


def _call(method, url, body=None, timeout=10):
    if not _token():
        raise RuntimeError("Not running inside Home Assistant.")
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def state(entity_id):
    """The full state object of an entity, or None when it does not exist."""
    try:
        return _call("GET", f"{CORE}/states/{urllib.parse.quote(entity_id)}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def entities(domain):
    """Entity ids of one domain, e.g. entities("calendar") -> ["calendar.family", ...]."""
    return sorted(s["entity_id"] for s in _call("GET", f"{CORE}/states") or [] if s["entity_id"].startswith(domain + "."))


def calendar_events(entity_id, start, end):
    """Events of one calendar between two aware datetimes. Each has summary, start and end ({"date"} or {"dateTime"})."""
    q = urllib.parse.urlencode({"start": start.isoformat(), "end": end.isoformat()})
    return _call("GET", f"{CORE}/calendars/{urllib.parse.quote(entity_id)}?{q}") or []


def service_response(domain, service, data):
    """A service that returns data (weather.get_forecasts, todo.get_items): {entity_id: {...}}."""
    out = _call("POST", f"{CORE}/services/{domain}/{service}?return_response", data, timeout=15) or {}
    return out.get("service_response") or {}


# ---------------------------------------------------------------- sensors
_published = {}          # entity_id -> (json of what was last written, time written)
FORCE_AFTER = 900        # seconds: Home Assistant forgets API-made sensors when it restarts, so rewrite now and then


def publish(entity_id, st, attributes):
    """Writes a sensor, but only when its value changed (or every 15 minutes): the recorder logs every write.
    Returns True when a write was made."""
    st = str(st)[:255]
    sig = json.dumps([st, attributes], sort_keys=True, default=str)
    last = _published.get(entity_id)
    if last and last[0] == sig and time.time() - last[1] < FORCE_AFTER:
        return False
    _call("POST", f"{CORE}/states/{entity_id}", {"state": st, "attributes": attributes})
    _published[entity_id] = (sig, time.time())
    return True


# ---------------------------------------------------------------- phone
_phone = {"value": None, "at": 0.0}


def _lookup_phones():
    for domain in _call("GET", f"{CORE}/services") or []:
        if domain.get("domain") == "notify":
            return sorted(n for n in domain.get("services", {}) if n.startswith("mobile_app_"))
    return []


def notify_service():
    """The configured notify service ("notify." prefix optional), else the only phone with the companion app."""
    svc = str(config.options()["notify_service"] or "").strip()
    if svc.startswith("notify."):
        svc = svc[len("notify."):]
    if svc or not available():
        return svc
    # A found phone is kept for 10 minutes; "no phone yet" is asked again after 30 s (e.g. right after pairing)
    if time.time() - _phone["at"] > (600 if _phone["value"] else 30):
        try:
            found = _lookup_phones()
            _phone.update(value=found[0] if len(found) == 1 else "", at=time.time())
        except Exception:
            _phone["at"] = time.time()
    return _phone["value"] or ""


_panel = {"url": None}


def panel_url():
    """Where a tapped notification opens: this add-on's page in Home Assistant."""
    if _panel["url"] is None:
        try:
            slug = (_call("GET", f"{SUPERVISOR}/addons/self/info") or {}).get("data", {}).get("slug")
            if slug:
                _panel["url"] = f"/hassio/ingress/{slug}"
        except Exception:
            pass
    return _panel["url"]


def send_summary(service, title, message):
    data = {"tag": "daily-briefing", "group": "daily-briefing", "channel": "Daily briefing"}
    url = panel_url()
    if url:
        data.update(clickAction=url, url=url)   # Android uses clickAction, iPhone uses url
    try:
        _call("POST", f"{CORE}/services/notify/{service}", {"title": title, "message": message, "data": data})
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            raise RuntimeError(f"Home Assistant has no notify.{service}. Check notify_service in the add-on's "
                               "Configuration tab (it looks like mobile_app_pixel_9).") from e
        raise
