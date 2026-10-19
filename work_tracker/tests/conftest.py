"""Shared setup for the Work Tracker tests.

Run from the add-on folder:   python -m pytest tests -q -p no:cacheprovider

Nothing touches Home Assistant, the network or the real database: DB_PATH / OPTIONS_PATH are set before the
backend is imported, every test gets a fresh SQLite file, and urlopen is blocked. Scratch goes to
~/.claude/scratchpad/work-tracker-tests, never the Temp folder."""
import datetime
import json
import os
import pathlib
import shutil
import sys

sys.dont_write_bytecode = True

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = pathlib.Path(os.environ.get("WT_TEST_TMP")
                    or pathlib.Path.home() / ".claude" / "scratchpad" / "work-tracker-tests")
RUN = BASE / f"run-{os.getpid()}"
RUN.mkdir(parents=True, exist_ok=True)

os.environ["DB_PATH"] = str(RUN / "import-time.db")
os.environ["OPTIONS_PATH"] = str(RUN / "no-such-options.json")
os.environ.pop("SUPERVISOR_TOKEN", None)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import nudger   # noqa: E402

_real_start = nudger.start
nudger.start = lambda: None         # api.py would otherwise spawn the nudge loop and the HA listener
import api      # noqa: E402

nudger.start = _real_start

import config   # noqa: E402
import db       # noqa: E402
import ha       # noqa: E402
import hours    # noqa: E402

from starlette.testclient import TestClient  # noqa: E402


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = str(RUN / "pytest")


def pytest_sessionfinish(session, exitstatus):
    if getattr(db, "_keeper", None) is not None:
        try:
            db._keeper.close()
        except Exception:
            pass
    shutil.rmtree(RUN, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "wt.db"))
    db.init_db()
    monkeypatch.setattr(config, "OPTIONS_PATH", str(tmp_path / "no-such-options.json"))
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)

    def no_network(*a, **k):
        raise AssertionError("a test tried to open a real network connection")
    monkeypatch.setattr("urllib.request.urlopen", no_network)
    monkeypatch.setitem(ha._phone, "value", None)
    monkeypatch.setitem(ha._phone, "at", 0.0)
    monkeypatch.setitem(ha._panel, "url", None)
    monkeypatch.setitem(nudger._state, "retry_at", 0.0)
    monkeypatch.setitem(nudger._state, "later_until", 0.0)
    monkeypatch.setitem(nudger._state, "stop_on", None)
    monkeypatch.setitem(nudger._state, "summary_week", None)


@pytest.fixture
def clock(monkeypatch):
    """clock("2026-10-19 16:00") fixes hours.now(); returns a setter."""
    cur = {}

    def _set(s):
        cur["t"] = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")
    monkeypatch.setattr(hours, "now", lambda: cur["t"])
    return _set


@pytest.fixture
def set_options(monkeypatch, tmp_path):
    path = tmp_path / "options.json"

    def _set(**opts):
        path.write_text(json.dumps(opts), encoding="utf-8")
        monkeypatch.setattr(config, "OPTIONS_PATH", str(path))
    return _set


@pytest.fixture
def sent(monkeypatch):
    """Captures ha.send / ha.clear calls; a phone is 'found'."""
    log = {"send": [], "clear": []}
    monkeypatch.setattr(ha, "notify_service", lambda: "mobile_app_test")
    monkeypatch.setattr(ha, "send", lambda svc, title, msg, tag, actions=None: log["send"].append(
        {"title": title, "msg": msg, "tag": tag, "actions": [a for a, _ in actions or []]}))
    monkeypatch.setattr(ha, "clear", lambda svc, tag: log["clear"].append(tag))
    return log


@pytest.fixture
def client():
    return TestClient(api.app)
