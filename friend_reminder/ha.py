"""Home Assistant bridge through the Supervisor: phone notifications with Done / Snooze / Skip buttons,
and a WebSocket listener that hears the button taps (event `mobile_app_notification_action`).

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

ACTION = re.compile(r"^FRIEND_(DONE|SNOOZE|SKIP)_(\d+)$")


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
            _phone["at"] = time.time()          # Home Assistant not answering: keep the last phone found
    return _phone["value"] or ""


def phones_seen():
    """The phones found by the last notify_service() lookup (no extra call to Home Assistant)."""
    return list(_phone["found"])


_panel = {"url": None}


def panel_url():
    """Where a tapped notification opens: this add-on's page in Home Assistant."""
    if _panel["url"] is None:            # only a found slug is kept, so a Supervisor that was not ready is asked again
        try:
            slug = (_call("GET", f"{SUPERVISOR}/addons/self/info") or {}).get("data", {}).get("slug")
            if slug:
                _panel["url"] = f"/hassio/ingress/{slug}"
        except Exception:
            pass
    return _panel["url"]


def tag(friend_id):
    return f"friend-reminder-{friend_id}"


def send_nudge(service, friend, opener=None):
    """One notification per friend, with Done / Snooze / Skip buttons."""
    if friend["birthday_today"]:
        title = f"🎂 {friend['name']}'s birthday is today"
    else:
        title = f"Reach out to {friend['name']}"
    if friend["never_logged"]:
        msg = f"{friend['tier_label']} friend. Not logged yet."
    else:
        d = friend["days_since"]
        msg = f"{friend['tier_label']} friend. {d} day{'s' if d != 1 else ''} since you talked."
    if opener:
        msg += f"\nTry: “{opener}”"
    fid = friend["id"]
    actions = [{"action": f"FRIEND_DONE_{fid}", "title": "Done"}]
    if friend.get("due", True):                 # just a birthday: there is no round to snooze or skip
        actions += [{"action": f"FRIEND_SNOOZE_{fid}", "title": "Snooze"},
                    {"action": f"FRIEND_SKIP_{fid}", "title": "Skip"}]
    data = {"tag": tag(fid), "group": "friend-reminder", "channel": "Friend reminders", "actions": actions}
    url = panel_url()
    if url:
        data.update(clickAction=url, url=url)   # Android uses clickAction, iPhone uses url
    try:
        _call("POST", f"{CORE}/services/notify/{service}", {"title": title, "message": msg, "data": data})
    except urllib.error.HTTPError as e:
        if e.code in (400, 404):
            raise RuntimeError(f"Home Assistant has no notify.{service}. Check notify_service in the add-on's "
                               "Configuration tab (it looks like mobile_app_pixel_9).") from e
        raise


def clear(service, friend_id):
    """Removes the friend's notification from the phone once a button was handled."""
    _call("POST", f"{CORE}/services/notify/{service}", {"message": "clear_notification", "data": {"tag": tag(friend_id)}})


def listen(on_action):
    """Background thread: calls on_action(kind, friend_id) for each Done / Snooze / Skip tap. Reconnects forever."""
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
