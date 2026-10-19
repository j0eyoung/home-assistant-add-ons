"""ha.py: the Home Assistant bridge, with ha._call and the websocket module faked (no network, no threads)."""
import io
import json
import sys
import types
import urllib.request

import pytest

import ha


def friend(id=7, name="Mike", tier_label="Good", days_since=45, never_logged=False, birthday_today=False):
    return {"id": id, "name": name, "tier_label": tier_label, "days_since": days_since,
            "never_logged": never_logged, "birthday_today": birthday_today}


class FakeCall:
    """Stands in for ha._call. Records every request; `routes` maps (METHOD, url) to a value or an exception."""
    def __init__(self, routes=None):
        self.routes = routes or {}
        self.requests = []

    def __call__(self, method, url, body=None, timeout=10):
        self.requests.append((method, url, body))
        out = self.routes.get((method, url))
        if isinstance(out, BaseException):
            raise out
        return out

    def posts(self):
        return [(url, body) for method, url, body in self.requests if method == "POST"]

    def gets(self):
        return [url for method, url, _ in self.requests if method == "GET"]


INFO_URL = f"{ha.SUPERVISOR}/addons/self/info"
SERVICES_URL = f"{ha.CORE}/services"


@pytest.fixture
def call(monkeypatch):
    fake = FakeCall({("GET", INFO_URL): {"data": {"slug": "abc123_friend_reminder"}}})
    monkeypatch.setattr(ha, "_call", fake)
    return fake


# ---------------------------------------------------------------- send_nudge

def test_send_nudge_posts_to_the_notify_service(call):
    ha.send_nudge("mobile_app_pixel", friend())
    (url, body), = call.posts()
    assert url == f"{ha.CORE}/services/notify/mobile_app_pixel"
    assert set(body) == {"title", "message", "data"}


def test_normal_title_and_message(call):
    ha.send_nudge("mobile_app_pixel", friend(name="Mike", tier_label="Close", days_since=45))
    _, body = call.posts()[0]
    assert body["title"] == "Reach out to Mike"
    assert body["message"] == "Close friend. 45 days since you talked."


def test_birthday_title(call):
    ha.send_nudge("p", friend(name="Sara", birthday_today=True))
    _, body = call.posts()[0]
    assert body["title"] == "\U0001F382 Sara's birthday is today"
    assert "Reach out" not in body["title"]


def test_message_uses_singular_day_and_handles_never_logged(call):
    ha.send_nudge("p", friend(days_since=1))
    assert call.posts()[0][1]["message"] == "Good friend. 1 day since you talked."
    call.requests.clear()
    ha.send_nudge("p", friend(never_logged=True, days_since=12, tier_label="Casual"))
    assert call.posts()[0][1]["message"] == "Casual friend. Not logged yet."


def test_opener_is_appended_to_the_message(call):
    ha.send_nudge("p", friend(), opener="How is the new job going?")
    msg = call.posts()[0][1]["message"]
    assert msg.endswith("\nTry: “How is the new job going?”")
    assert msg.startswith("Good friend. 45 days since you talked.")


def test_no_opener_means_no_try_line(call):
    ha.send_nudge("p", friend(), opener=None)
    assert "Try:" not in call.posts()[0][1]["message"]


def test_three_actions_carry_the_friend_id(call):
    ha.send_nudge("p", friend(id=42))
    actions = call.posts()[0][1]["data"]["actions"]
    assert actions == [
        {"action": "FRIEND_DONE_42", "title": "Done"},
        {"action": "FRIEND_SNOOZE_42", "title": "Snooze"},
        {"action": "FRIEND_SKIP_42", "title": "Skip"},
    ]


def test_every_action_the_notification_sends_is_one_the_listener_accepts(call):
    ha.send_nudge("p", friend(id=5))
    for a in call.posts()[0][1]["data"]["actions"]:
        assert ha.ACTION.match(a["action"])


def test_tag_group_and_channel(call):
    ha.send_nudge("p", friend(id=42))
    data = call.posts()[0][1]["data"]
    assert data["tag"] == "friend-reminder-42" == ha.tag(42)
    assert data["group"] == "friend-reminder"
    assert data["channel"] == "Friend reminders"


def test_tag_is_per_friend(call):
    assert ha.tag(1) != ha.tag(2)


def test_click_action_and_url_point_at_the_add_on_panel(call):
    ha.send_nudge("p", friend())
    data = call.posts()[0][1]["data"]
    assert data["clickAction"] == data["url"] == "/hassio/ingress/abc123_friend_reminder"


def test_no_click_action_when_the_panel_url_is_unknown(monkeypatch):
    fake = FakeCall({("GET", INFO_URL): RuntimeError("supervisor unreachable")})
    monkeypatch.setattr(ha, "_call", fake)
    ha.send_nudge("p", friend())
    data = fake.posts()[0][1]["data"]
    assert "clickAction" not in data and "url" not in data
    assert len(data["actions"]) == 3                          # the buttons still work


def test_no_click_action_when_the_slug_is_missing(monkeypatch):
    fake = FakeCall({("GET", INFO_URL): {"data": {}}})
    monkeypatch.setattr(ha, "_call", fake)
    ha.send_nudge("p", friend())
    assert "clickAction" not in fake.posts()[0][1]["data"]


def test_panel_url_is_looked_up_once(call):
    assert ha.panel_url() == "/hassio/ingress/abc123_friend_reminder"
    assert ha.panel_url() == "/hassio/ingress/abc123_friend_reminder"
    ha.send_nudge("p", friend())
    assert call.gets() == [INFO_URL]


def test_panel_url_retries_after_a_failed_lookup(monkeypatch):
    answers = iter([RuntimeError("supervisor not ready"), {"data": {"slug": "abc123_friend_reminder"}}])

    def flaky(method, url, body=None, timeout=10):
        out = next(answers)
        if isinstance(out, BaseException):
            raise out
        return out
    monkeypatch.setattr(ha, "_call", flaky)
    assert ha.panel_url() is None
    assert ha.panel_url() == "/hassio/ingress/abc123_friend_reminder"


def test_send_nudge_propagates_a_failed_post(monkeypatch):
    fake = FakeCall({("GET", INFO_URL): {"data": {"slug": "s"}},
                     ("POST", f"{ha.CORE}/services/notify/p"): OSError("HA is down")})
    monkeypatch.setattr(ha, "_call", fake)
    with pytest.raises(OSError):
        ha.send_nudge("p", friend())


def test_clear_removes_the_friends_notification_by_tag(call):
    ha.clear("mobile_app_pixel", 42)
    (url, body), = call.posts()
    assert url == f"{ha.CORE}/services/notify/mobile_app_pixel"
    assert body == {"message": "clear_notification", "data": {"tag": "friend-reminder-42"}}


# ---------------------------------------------------------------- notify_service / phones

def services_reply(*notify_services, extra_domains=True):
    domains = [{"domain": "light", "services": {"turn_on": {}}}] if extra_domains else []
    domains.append({"domain": "notify", "services": {s: {} for s in notify_services}})
    return domains


def test_notify_service_strips_the_notify_prefix(set_options, in_home_assistant):
    set_options(notify_service="notify.mobile_app_pixel_9")
    assert ha.notify_service() == "mobile_app_pixel_9"


def test_notify_service_accepts_a_name_without_the_prefix(set_options, in_home_assistant):
    set_options(notify_service="  mobile_app_pixel_9  ")
    assert ha.notify_service() == "mobile_app_pixel_9"


def test_configured_service_is_used_without_asking_home_assistant(set_options, in_home_assistant, monkeypatch):
    set_options(notify_service="notify.mobile_app_pixel_9")
    fake = FakeCall()
    monkeypatch.setattr(ha, "_call", fake)
    ha.notify_service()
    assert fake.requests == []


def test_notify_service_auto_picks_the_only_phone(in_home_assistant, monkeypatch):
    fake = FakeCall({("GET", SERVICES_URL): services_reply("mobile_app_pixel_9", "notify", "persistent_notification")})
    monkeypatch.setattr(ha, "_call", fake)
    assert ha.notify_service() == "mobile_app_pixel_9"


def test_notify_service_is_empty_with_two_phones(in_home_assistant, monkeypatch):
    fake = FakeCall({("GET", SERVICES_URL): services_reply("mobile_app_pixel_9", "mobile_app_ipad")})
    monkeypatch.setattr(ha, "_call", fake)
    assert ha.notify_service() == ""


def test_notify_service_is_empty_with_no_phone(in_home_assistant, monkeypatch):
    fake = FakeCall({("GET", SERVICES_URL): services_reply("notify", "persistent_notification")})
    monkeypatch.setattr(ha, "_call", fake)
    assert ha.notify_service() == ""


def test_the_auto_picked_phone_is_cached(in_home_assistant, monkeypatch):
    fake = FakeCall({("GET", SERVICES_URL): services_reply("mobile_app_pixel_9")})
    monkeypatch.setattr(ha, "_call", fake)
    assert ha.notify_service() == "mobile_app_pixel_9"
    assert ha.notify_service() == "mobile_app_pixel_9"
    assert fake.gets() == [SERVICES_URL]


def test_the_phone_lookup_is_refreshed_after_ten_minutes(in_home_assistant, monkeypatch):
    fake = FakeCall({("GET", SERVICES_URL): services_reply("mobile_app_pixel_9")})
    monkeypatch.setattr(ha, "_call", fake)
    ha.notify_service()
    ha._phone["at"] -= 601
    ha.notify_service()
    assert len(fake.gets()) == 2


def test_notify_service_is_empty_outside_home_assistant():
    assert ha.available() is False
    assert ha.notify_service() == ""


def test_phones_lists_only_companion_apps_sorted(monkeypatch):
    fake = FakeCall({("GET", SERVICES_URL): services_reply("mobile_app_zeta", "notify", "mobile_app_alpha", "pushover")})
    monkeypatch.setattr(ha, "_call", fake)
    assert ha.phones() == ["mobile_app_alpha", "mobile_app_zeta"]


def test_phones_is_empty_when_home_assistant_is_unreachable(monkeypatch):
    monkeypatch.setattr(ha, "_call", FakeCall({("GET", SERVICES_URL): OSError("down")}))
    assert ha.phones() == []


def test_phones_is_empty_without_a_notify_domain(monkeypatch):
    monkeypatch.setattr(ha, "_call", FakeCall({("GET", SERVICES_URL): [{"domain": "light", "services": {}}]}))
    assert ha.phones() == []


# ---------------------------------------------------------------- _call and available

def test_available_follows_supervisor_token(monkeypatch):
    assert ha.available() is False
    monkeypatch.setenv("SUPERVISOR_TOKEN", "tok")
    assert ha.available() is True


def test_call_outside_home_assistant_raises_without_touching_the_network():
    with pytest.raises(RuntimeError, match="Not running inside Home Assistant"):
        ha._call("GET", f"{ha.CORE}/services")


def test_call_sends_the_bearer_token_and_a_json_body(in_home_assistant, monkeypatch):
    seen = {}

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen.update(req=req, timeout=timeout)
        return Reply(b'[{"ok": true}]')

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    out = ha._call("POST", "http://supervisor/core/api/services/notify/p", {"message": "hi"}, timeout=4)
    req = seen["req"]
    assert out == [{"ok": True}]
    assert req.get_method() == "POST" and req.full_url == "http://supervisor/core/api/services/notify/p"
    assert req.get_header("Authorization") == "Bearer test-token"
    assert req.get_header("Content-type") == "application/json"
    assert json.loads(req.data) == {"message": "hi"}
    assert seen["timeout"] == 4


def test_call_returns_none_for_an_empty_reply(in_home_assistant, monkeypatch):
    class Empty(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: Empty(b""))
    assert ha._call("GET", "http://supervisor/x") is None


# ---------------------------------------------------------------- the ACTION regex

@pytest.mark.parametrize("text,kind,fid", [
    ("FRIEND_DONE_7", "DONE", "7"),
    ("FRIEND_SNOOZE_123", "SNOOZE", "123"),
    ("FRIEND_SKIP_0", "SKIP", "0"),
])
def test_action_regex_accepts_valid_actions(text, kind, fid):
    m = ha.ACTION.match(text)
    assert m and m.group(1) == kind and m.group(2) == fid


@pytest.mark.parametrize("text", [
    "", "FRIEND_DONE_", "FRIEND_DONE", "FRIEND_DONE_abc", "FRIEND_DONE_-1", "FRIEND_DONE_1.5", "FRIEND_DONE_1 ",
    "FRIEND_DELETE_1", "FRIEND_done_1", "friend_done_1", "XFRIEND_DONE_1", "FRIEND_DONE_1_2", " FRIEND_DONE_1",
    "URI_1", "FRIEND_SNOOZE1",
])
def test_action_regex_rejects_everything_else(text):
    assert ha.ACTION.match(text) is None


# ---------------------------------------------------------------- listen()

class StopListening(BaseException):
    """Raised by the fake time.sleep to break out of listen()'s forever-loop."""


class FakeTimeout(Exception):
    """Stands in for websocket.WebSocketTimeoutException."""


class FakeWS:
    def __init__(self, script):
        self.script = list(script)
        self.sent = []
        self.closed = False
        self.timeouts = []

    def recv(self):
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item if isinstance(item, str) else json.dumps(item)

    def send(self, data):
        self.sent.append(json.loads(data))

    def settimeout(self, t):
        self.timeouts.append(t)

    def close(self):
        self.closed = True


AUTH_REQUIRED = {"type": "auth_required", "ha_version": "2026.10.0"}
AUTH_OK = {"type": "auth_ok"}
RESULT = {"id": 1, "type": "result", "success": True, "result": None}


def action_event(action, msg_id=1):
    return {"id": msg_id, "type": "event",
            "event": {"event_type": "mobile_app_notification_action", "data": {"action": action}}}


@pytest.fixture
def listen_env(monkeypatch, in_home_assistant):
    """Fake websocket module + synchronous Thread + a time.sleep that records and stops the loop."""
    env = types.SimpleNamespace(connections=[], urls=[], sleeps=[], stop_after=1, threads=[], scripts=[])

    def create_connection(url, timeout=None):
        env.urls.append((url, timeout))
        item = env.scripts.pop(0)
        if isinstance(item, BaseException):
            raise item
        ws = FakeWS(item)
        env.connections.append(ws)
        return ws

    fake_module = types.ModuleType("websocket")
    fake_module.create_connection = create_connection
    fake_module.WebSocketTimeoutException = FakeTimeout
    monkeypatch.setitem(sys.modules, "websocket", fake_module)

    def fake_sleep(seconds):
        env.sleeps.append(seconds)
        if len(env.sleeps) >= env.stop_after:
            raise StopListening

    monkeypatch.setattr(ha, "time", types.SimpleNamespace(sleep=fake_sleep, time=lambda: 0.0))

    class SyncThread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target, self.daemon, self.name = target, daemon, name
            env.threads.append(self)

        def start(self):
            self.target()

    monkeypatch.setattr(ha, "threading", types.SimpleNamespace(Thread=SyncThread))
    return env


def run_listen(env, on_action):
    with pytest.raises(StopListening):
        ha.listen(on_action)


def test_listen_dispatches_a_button_tap(listen_env):
    listen_env.scripts = [[AUTH_REQUIRED, AUTH_OK, RESULT, action_event("FRIEND_DONE_7"), ConnectionError("dropped")]]
    got = []
    run_listen(listen_env, lambda kind, fid: got.append((kind, fid)))
    assert got == [("done", 7)]
    ws = listen_env.connections[0]
    assert ws.sent[0] == {"type": "auth", "access_token": "test-token"}
    assert ws.sent[1] == {"id": 1, "type": "subscribe_events", "event_type": "mobile_app_notification_action"}
    assert listen_env.urls == [("ws://supervisor/core/websocket", 30)]
    assert 300 in ws.timeouts                                   # quiet-line timeout after the handshake
    assert ws.closed is True
    assert listen_env.sleeps == [5]                              # then it would reconnect after 5 s


def test_listen_dispatches_all_three_kinds_in_order(listen_env):
    listen_env.scripts = [[AUTH_REQUIRED, AUTH_OK, RESULT,
                           action_event("FRIEND_SNOOZE_3"), action_event("FRIEND_SKIP_4"), action_event("FRIEND_DONE_5"),
                           ConnectionError("dropped")]]
    got = []
    run_listen(listen_env, lambda kind, fid: got.append((kind, fid)))
    assert got == [("snooze", 3), ("skip", 4), ("done", 5)]


def test_listen_ignores_other_actions_and_other_messages(listen_env):
    listen_env.scripts = [[AUTH_REQUIRED, AUTH_OK, RESULT,
                           {"id": 9, "type": "pong"},
                           action_event("SOMETHING_ELSE"),
                           action_event("FRIEND_DELETE_1"),
                           action_event("FRIEND_DONE_abc"),
                           {"id": 1, "type": "event", "event": {"data": {}}},
                           {"id": 1, "type": "event", "event": None},
                           {"id": 1, "type": "event"},
                           {"id": 1, "type": "result", "event": {"data": {"action": "FRIEND_DONE_1"}}},   # not an event
                           action_event("FRIEND_SKIP_2"),
                           ConnectionError("dropped")]]
    got = []
    run_listen(listen_env, lambda kind, fid: got.append((kind, fid)))
    assert got == [("skip", 2)]


def test_listen_survives_a_failing_callback(listen_env, capsys):
    listen_env.scripts = [[AUTH_REQUIRED, AUTH_OK, RESULT, action_event("FRIEND_DONE_1"), action_event("FRIEND_SKIP_2"),
                           ConnectionError("dropped")]]
    got = []

    def on_action(kind, fid):
        if fid == 1:
            raise ValueError("boom")
        got.append((kind, fid))
    run_listen(listen_env, on_action)
    assert got == [("skip", 2)]
    assert "Notification button failed: boom" in capsys.readouterr().out


def test_listen_pings_when_the_line_is_quiet(listen_env):
    listen_env.scripts = [[AUTH_REQUIRED, AUTH_OK, RESULT, FakeTimeout(), FakeTimeout(),
                           action_event("FRIEND_DONE_8"), ConnectionError("dropped")]]
    got = []
    run_listen(listen_env, lambda kind, fid: got.append((kind, fid)))
    pings = [m for m in listen_env.connections[0].sent if m["type"] == "ping"]
    assert [p["id"] for p in pings] == [2, 3]                    # ids keep increasing
    assert got == [("done", 8)]


def test_listen_reports_a_refused_token_and_reconnects_later(listen_env, capsys):
    listen_env.scripts = [[AUTH_REQUIRED, {"type": "auth_invalid", "message": "Invalid access token"}]]
    got = []
    run_listen(listen_env, lambda kind, fid: got.append((kind, fid)))
    assert got == []
    assert "refused the add-on's token" in capsys.readouterr().out
    assert listen_env.connections[0].closed is True
    assert listen_env.sleeps == [5]


def test_listen_rejects_an_unexpected_greeting(listen_env, capsys):
    listen_env.scripts = [[{"type": "hello"}]]
    run_listen(listen_env, lambda kind, fid: None)
    assert "unexpected greeting" in capsys.readouterr().out
    assert listen_env.connections[0].sent == []                  # never sent the token


def test_listen_backs_off_when_the_connection_keeps_failing(listen_env):
    listen_env.stop_after = 9
    listen_env.scripts = [ConnectionRefusedError("nope")] * 9
    run_listen(listen_env, lambda kind, fid: None)
    assert listen_env.sleeps == [5, 10, 20, 40, 80, 120, 120, 120, 120]


def test_listen_resets_the_backoff_after_a_good_connection(listen_env):
    listen_env.stop_after = 4
    listen_env.scripts = [ConnectionRefusedError("a"), ConnectionRefusedError("b"),
                          [AUTH_REQUIRED, AUTH_OK, RESULT, ConnectionError("dropped")],
                          ConnectionRefusedError("c")]
    run_listen(listen_env, lambda kind, fid: None)
    assert listen_env.sleeps == [5, 10, 5, 10]                   # 5 again after the successful handshake


def test_listen_starts_a_daemon_thread_inside_home_assistant(listen_env):
    listen_env.scripts = [[AUTH_REQUIRED, AUTH_OK, ConnectionError("dropped")]]
    run_listen(listen_env, lambda kind, fid: None)
    t, = listen_env.threads
    assert t.daemon is True and t.name == "ha-events"


def test_listen_does_nothing_outside_home_assistant(monkeypatch):
    started = []

    class Boom:
        def __init__(self, *a, **k):
            started.append(1)
    monkeypatch.setattr(ha, "threading", types.SimpleNamespace(Thread=Boom))
    ha.listen(lambda kind, fid: None)                            # SUPERVISOR_TOKEN is unset
    assert started == []


# ---------------------------------------------------------------- review fixes

def test_birthday_without_a_due_round_offers_only_done(call):
    ha.send_nudge("p", {**friend(id=3, birthday_today=True), "due": False})
    assert [a["title"] for a in call.posts()[0][1]["data"]["actions"]] == ["Done"]


def test_due_birthday_keeps_all_three_buttons(call):
    ha.send_nudge("p", {**friend(id=3, birthday_today=True), "due": True})
    assert [a["title"] for a in call.posts()[0][1]["data"]["actions"]] == ["Done", "Snooze", "Skip"]


def test_unknown_notify_service_gets_a_clear_error(monkeypatch):
    import urllib.error

    def reject(method, url, body=None, timeout=10):
        if method == "POST":
            raise urllib.error.HTTPError(url, 400, "Bad Request", {}, None)
        return None
    monkeypatch.setattr(ha, "_call", reject)
    with pytest.raises(RuntimeError, match="no notify.mobile_app_typo"):
        ha.send_nudge("mobile_app_typo", friend())


def test_no_phone_yet_is_asked_again_after_30_seconds(in_home_assistant, monkeypatch):
    replies = iter([services_reply(), services_reply("mobile_app_pixel_9")])
    monkeypatch.setattr(ha, "_call", lambda method, url, body=None, timeout=10: next(replies))
    assert ha.notify_service() == ""
    ha._phone["at"] -= 31                         # the phone gets paired; half a minute later
    assert ha.notify_service() == "mobile_app_pixel_9"


def test_a_failed_refresh_keeps_the_last_phone(in_home_assistant, monkeypatch):
    replies = iter([services_reply("mobile_app_pixel_9"), OSError("core restarting")])

    def flaky(method, url, body=None, timeout=10):
        out = next(replies)
        if isinstance(out, BaseException):
            raise out
        return out
    monkeypatch.setattr(ha, "_call", flaky)
    assert ha.notify_service() == "mobile_app_pixel_9"
    ha._phone["at"] -= 601
    assert ha.notify_service() == "mobile_app_pixel_9"