"""Home Assistant bridge through the Supervisor: phone notifications with Done / Snooze buttons, a WebSocket
listener that hears the button taps (event `mobile_app_notification_action`), sensor states and the shopping list.

Add-ons get SUPERVISOR_TOKEN with homeassistant_api: true, so there is nothing to set up but the phone."""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

import config

CORE = "http://supervisor/core/api"
SUPERVISOR = "http://supervisor"
WS_URL = "ws://supervisor/core/websocket"

ACTION = re.compile(r"^MAINT_(DONE|SNOOZE)_(\d+)$")


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


def _lookup_phones():
    for domain in _call("GET", f"{CORE}/services") or []:
        if domain.get("domain") == "notify":
            return sorted(n for n in domain.get("services", {}) if n.startswith("mobile_app_"))
    return []


def phones():
    """Companion-app notify services, e.g. ["mobile_app_pixel_9"] ([] when Home Assistant does not answer)."""
    try:
        return _lookup_phones()
    except Exception:
        return []


_phone = {"value": None, "found": [], "at": 0.0}


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
            _phone.update(value=found[0] if len(found) == 1 else "", found=found, at=time.time())
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


def _notify(service, payload):
    try:
        _call("POST", f"{CORE}/services/notify/{service}", payload)
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            raise RuntimeError(f"Home Assistant has no notify.{service}. Check notify_service in the add-on's "
                               "Configuration tab (it looks like mobile_app_pixel_9).") from e
        raise


def tag(task_id):
    return f"home-maintenance-{task_id}"


def send_due(service, task):
    """One notification per due task, with Done / Snooze buttons."""
    d = task["days_until"]
    msg = "Due today." if d == 0 else f"Overdue by {-d} day{'s' if d != -1 else ''}."
    tid = task["id"]
    data = {"tag": tag(tid), "group": "home-maintenance", "channel": "Home maintenance",
            "actions": [{"action": f"MAINT_DONE_{tid}", "title": "Done"},
                        {"action": f"MAINT_SNOOZE_{tid}", "title": "Snooze"}]}
    url = panel_url()
    if url:
        data.update(clickAction=url, url=url)   # Android uses clickAction, iPhone uses url
    _notify(service, {"title": task["name"], "message": msg, "data": data})


def send_message(service, title, message, tag_name):
    """A plain notification (toner alerts, warranty reminders)."""
    data = {"tag": tag_name, "group": "home-maintenance", "channel": "Home maintenance"}
    url = panel_url()
    if url:
        data.update(clickAction=url, url=url)
    _notify(service, {"title": title, "message": message, "data": data})


def clear(service, task_id):
    """Removes the task's notification from the phone once a button was handled."""
    _call("POST", f"{CORE}/services/notify/{service}", {"message": "clear_notification", "data": {"tag": tag(task_id)}})


def get_state(entity_id):
    """The entity's state object ({"state": "42", "attributes": {...}}); None when Home Assistant has no such entity."""
    try:
        return _call("GET", f"{CORE}/states/{entity_id}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def sensors():
    """Every sensor entity, for the toner picker: [{"entity_id", "name", "state"}]."""
    out = []
    for s in _call("GET", f"{CORE}/states") or []:
        if s["entity_id"].startswith("sensor."):
            out.append({"entity_id": s["entity_id"], "state": s.get("state"),
                        "name": (s.get("attributes") or {}).get("friendly_name") or s["entity_id"]})
    return sorted(out, key=lambda s: s["entity_id"])


def set_state(entity_id, state, attributes):
    """Creates or updates a plain state entity (not kept by Home Assistant across a restart)."""
    _call("POST", f"{CORE}/states/{entity_id}", {"state": state, "attributes": attributes})


def remove_state(entity_id):
    try:
        _call("DELETE", f"{CORE}/states/{entity_id}")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise


def fire_event(event_type, data):
    _call("POST", f"{CORE}/events/{event_type}", data)


def add_todo(text):
    _call("POST", f"{CORE}/services/todo/add_item", {"entity_id": config.options()["todo_entity"], "item": text})


def listen(on_action):
    """Background thread: calls on_action(kind, task_id) for each Done / Snooze tap. Reconnects forever."""
    def loop():
        import websocket   # websocket-client
        delay = 5
        while True:
            ws = None
            try:
                ws = websocket.create_connection(WS_URL, timeout=30)
                if json.loads(ws.recv()).get("type") != "auth_required":
                    raise RuntimeError("unexpected greeting")
                ws.send(json.dumps({"type": "auth", "access_token": _token()}))
                if json.loads(ws.recv()).get("type") != "auth_ok":
                    raise RuntimeError("Home Assistant refused the add-on's token")
                ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "mobile_app_notification_action"}))
                ws.settimeout(300)
                delay, msg_id = 5, 1
                while True:
                    try:
                        msg = json.loads(ws.recv())
                    except websocket.WebSocketTimeoutException:
                        msg_id += 1                      # quiet for 5 minutes: check the line is still alive
                        ws.send(json.dumps({"id": msg_id, "type": "ping"}))
                        continue
                    if msg.get("type") != "event":
                        continue
                    m = ACTION.match(str((msg.get("event") or {}).get("data", {}).get("action") or ""))
                    if m:
                        try:
                            on_action(m.group(1).lower(), int(m.group(2)))
                        except Exception as e:
                            print(f"Notification button failed: {e}", flush=True)
            except Exception as e:
                print(f"Home Assistant event listener: {e}; retrying in {delay}s", flush=True)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
            time.sleep(delay)
            delay = min(delay * 2, 120)

    if available():
        threading.Thread(target=loop, daemon=True, name="ha-events").start()
