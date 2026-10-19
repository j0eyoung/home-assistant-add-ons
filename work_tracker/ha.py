"""Home Assistant bridge through the Supervisor: phone notifications with action buttons, and a WebSocket
listener that hears the button taps (event `mobile_app_notification_action`).

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

# WT_STOP, WT_LATER, WT_TASKDONE_<id>, WT_TASKSNOOZE_<id>
ACTION = re.compile(r"^WT_(STOP|LATER|TASKDONE|TASKSNOOZE)(?:_(\d+))?$")


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


def send(service, title, message, tag, actions=None):
    """One notification. `actions` is a list of (action id, button title)."""
    data = {"tag": tag, "group": "work-tracker", "channel": "Work Tracker"}
    if actions:
        data["actions"] = [{"action": a, "title": t} for a, t in actions]
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


def clear(service, tag):
    _call("POST", f"{CORE}/services/notify/{service}", {"message": "clear_notification", "data": {"tag": tag}})


def listen(on_action):
    """Background thread: calls on_action(kind, id_or_None) for each button tap. Reconnects forever."""
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
                        msg_id += 1
                        ws.send(json.dumps({"id": msg_id, "type": "ping"}))
                        continue
                    if msg.get("type") != "event":
                        continue
                    m = ACTION.match(str((msg.get("event") or {}).get("data", {}).get("action") or ""))
                    if m:
                        try:
                            on_action(m.group(1).lower(), int(m.group(2)) if m.group(2) else None)
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
