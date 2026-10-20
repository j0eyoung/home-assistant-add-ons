"""Shared setup for the Daily Briefing tests.

Run from C:\\AntiGravity\\HA Addons\\daily_briefing:   python -m pytest tests -q -p no:cacheprovider

Nothing here touches Home Assistant, the other add-ons or the network:
  * OPTIONS_PATH is set BEFORE any backend module is imported (config.py reads it at call time, but api.py starts
    the background loop at import, so sections.start is stubbed while api is imported).
  * Every test starts with no options file, no SUPERVISOR_TOKEN, and urllib's urlopen blocked.
  * `fake_ha` stands in for Home Assistant (ha._call) and `fake_addons` for the other add-ons (addons._get).
Scratch files go to ~/.claude/scratchpad/daily-briefing-tests (override with BRIEFING_TEST_TMP), never the Temp folder.
"""
import datetime
import json
import os
import pathlib
import shutil
import sys
import urllib.error
import zoneinfo

sys.dont_write_bytecode = True      # keep __pycache__ out of the add-on folder

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = pathlib.Path(os.environ.get("BRIEFING_TEST_TMP")
                    or pathlib.Path.home() / ".claude" / "scratchpad" / "daily-briefing-tests")
RUN = BASE / f"run-{os.getpid()}"
RUN.mkdir(parents=True, exist_ok=True)

os.environ["OPTIONS_PATH"] = str(RUN / "no-such-options.json")
os.environ.pop("SUPERVISOR_TOKEN", None)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sections  # noqa: E402

_real_start = sections.start
sections.start = lambda: None       # api.py would otherwise spawn the refresh loop
import api      # noqa: E402

sections.start = _real_start

import addons       # noqa: E402
import config       # noqa: E402
import ha           # noqa: E402
import sections_ha  # noqa: E402

from starlette.testclient import TestClient  # noqa: E402

TZ = zoneinfo.ZoneInfo("America/Denver")
MONDAY_8AM = datetime.datetime(2026, 10, 19, 8, 0, tzinfo=TZ)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = str(RUN / "pytest")


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(RUN, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OPTIONS_PATH", str(tmp_path / "no-such-options.json"))
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)

    def no_network(*a, **k):
        raise AssertionError("a test tried to open a real network connection")
    monkeypatch.setattr("urllib.request.urlopen", no_network)
    monkeypatch.setattr(sections_ha, "tzinfo", lambda: TZ)
    monkeypatch.setattr(sections_ha, "now", lambda: MONDAY_8AM)
    monkeypatch.setattr(ha, "_published", {})
    monkeypatch.setitem(ha._phone, "value", None)
    monkeypatch.setitem(ha._phone, "at", 0.0)
    monkeypatch.setitem(ha._panel, "url", None)
    monkeypatch.setitem(sections._sent, "on", None)
    monkeypatch.setitem(sections._latest, "data", None)


@pytest.fixture
def set_options(monkeypatch, tmp_path):
    """set_options(morning_time="06:30", calendars=["calendar.family"], ...) writes an options.json config.options() reads."""
    path = tmp_path / "options.json"

    def _set(**opts):
        path.write_text(json.dumps(opts), encoding="utf-8")
        monkeypatch.setattr(config, "OPTIONS_PATH", str(path))
    return _set


class FakeHA:
    """Home Assistant as the add-on sees it through the Supervisor."""

    def __init__(self):
        self.states = {}            # entity_id -> {"state": ..., "attributes": {...}}
        self.calendars = {}         # entity_id -> [events] (or an Exception to raise)
        self.responses = {}         # (domain, service) -> {entity_id: {...}} for ?return_response services
        self.phones = []
        self.writes = []            # (entity_id, state, attributes) published by the add-on
        self.notifications = []     # (service, body)
        self.time_zone = "America/Denver"

    def __call__(self, method, url, body=None, timeout=10):
        path = url[len(ha.CORE):] if url.startswith(ha.CORE) else url
        if method == "GET" and path == "/config":
            return {"time_zone": self.time_zone}
        if method == "GET" and path == "/states":
            return [{"entity_id": k, **v} for k, v in self.states.items()]
        if method == "GET" and path.startswith("/states/"):
            ent = path[len("/states/"):]
            if ent not in self.states:
                raise urllib.error.HTTPError(url, 404, "not found", {}, None)
            return {"entity_id": ent, **self.states[ent]}
        if method == "POST" and path.startswith("/states/"):
            self.writes.append((path[len("/states/"):], body["state"], body["attributes"]))
            return {}
        if method == "GET" and path.startswith("/calendars/"):
            ev = self.calendars[path[len("/calendars/"):].split("?")[0]]
            if isinstance(ev, Exception):
                raise ev
            return ev
        if method == "POST" and "?return_response" in path:
            domain, service = path[len("/services/"):].split("?")[0].split("/")
            return {"service_response": self.responses.get((domain, service), {})}
        if method == "GET" and path == "/services":
            return [{"domain": "notify", "services": {p: {} for p in self.phones}}]
        if method == "POST" and path.startswith("/services/notify/"):
            self.notifications.append((path[len("/services/notify/"):], body))
            return []
        if method == "GET" and url.endswith("/addons/self/info"):
            return {"data": {"slug": "c0a16a5a_daily_briefing"}}
        raise AssertionError(f"unexpected Home Assistant call: {method} {url}")


@pytest.fixture
def fake_ha(monkeypatch):
    fake = FakeHA()
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-token")
    monkeypatch.setattr(ha, "_call", fake)
    return fake


@pytest.fixture
def fake_addons(monkeypatch):
    """fake_addons.data[("meals", "/meals/today?date=2026-10-19")] = {...}; an Exception value is raised.
    fake_addons.calls records (name, path, token)."""
    class Fake:
        data = {}
        calls = []

        def __call__(self, name, path, token=""):
            self.calls.append((name, path, token))
            v = self.data[(name, path)]
            if isinstance(v, Exception):
                raise v
            return v
    fake = Fake()
    fake.data, fake.calls = {}, []
    monkeypatch.setattr(addons, "_get", fake)
    return fake


@pytest.fixture
def client():
    return TestClient(api.app)
