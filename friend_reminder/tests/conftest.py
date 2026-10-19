"""Shared setup for the Friend Reminder tests.

Run from C:\\AntiGravity\\FriendReminder:   python -m pytest tests -q -p no:cacheprovider

Nothing here touches Home Assistant, the network or the real database:
  * DB_PATH / OPTIONS_PATH are set BEFORE any backend module is imported (db.py and config.py read them at import).
  * Every test gets its own fresh SQLite file and a nonexistent options file.
  * SUPERVISOR_TOKEN and ANTHROPIC_API_KEY are removed, and urllib's urlopen is blocked.
  * api.py calls nudger.start() at import time; it is stubbed out so no loop or listener thread is ever spawned.
Scratch files go to ~/.claude/scratchpad/friend-reminder-tests (override with FRIEND_TEST_TMP), never the Temp folder.
"""
import datetime
import json
import os
import pathlib
import shutil
import sys
import time

sys.dont_write_bytecode = True      # keep __pycache__ out of the add-on folder

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = pathlib.Path(os.environ.get("FRIEND_TEST_TMP")
                    or pathlib.Path.home() / ".claude" / "scratchpad" / "friend-reminder-tests")
RUN = BASE / f"run-{os.getpid()}"   # one folder per run, so two overlapping runs never wipe each other's files
SESSION_DIR = RUN / "session"       # only used for the import-time database api.py creates
PYTEST_DIR = RUN / "pytest"         # pytest's own basetemp (tmp_path), wiped by pytest when the run starts

for old in BASE.glob("run-*"):      # leftovers of killed runs
    try:
        if time.time() - old.stat().st_mtime > 86400:
            shutil.rmtree(old, ignore_errors=True)
    except OSError:
        pass
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Environment first, backend imports after.
os.environ["DB_PATH"] = str(SESSION_DIR / "import-time.db")
os.environ["OPTIONS_PATH"] = str(SESSION_DIR / "no-such-options.json")
os.environ.pop("SUPERVISOR_TOKEN", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import nudger   # noqa: E402  (must come after the environment is set)

_real_start = nudger.start
nudger.start = lambda: None         # api.py would otherwise spawn the nudge loop and the HA listener
import api      # noqa: E402

nudger.start = _real_start          # restore, so a test can still exercise the real start() with threads faked

import config   # noqa: E402
import db       # noqa: E402
import friends  # noqa: E402
import ha       # noqa: E402

from starlette.testclient import TestClient  # noqa: E402


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # Keep pytest's tmp_path / tmp_path_factory out of the Windows Temp folder.
    if not config.option.basetemp:
        config.option.basetemp = str(PYTEST_DIR)


def pytest_sessionfinish(session, exitstatus):
    keeper = getattr(db, "_keeper", None)
    if keeper is not None:
        try:
            keeper.close()
        except Exception:
            pass
    shutil.rmtree(RUN, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    """A fresh database, no options file, not inside Home Assistant, no network, clean module caches."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "friends.db"))
    db.init_db()
    monkeypatch.setattr(config, "OPTIONS_PATH", str(tmp_path / "no-such-options.json"))
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def no_network(*a, **k):
        raise AssertionError("a test tried to open a real network connection")
    monkeypatch.setattr("urllib.request.urlopen", no_network)

    monkeypatch.setitem(ha._phone, "value", None)
    monkeypatch.setitem(ha._phone, "at", 0.0)
    monkeypatch.setitem(ha._phone, "found", [])
    monkeypatch.setitem(ha._panel, "url", None)
    monkeypatch.setitem(nudger._state, "sent_on", None)
    monkeypatch.setitem(nudger._state, "retry_at", 0.0)


@pytest.fixture
def today(monkeypatch):
    """The date friends.today() reports; fixed for the duration of the test."""
    d = datetime.date.today()
    monkeypatch.setattr(friends, "today", lambda: d)
    return d


@pytest.fixture
def set_options(monkeypatch, tmp_path):
    """set_options(nudge_time="08:30", nudges_per_day=2, ...) writes an options.json that config.options() reads."""
    path = tmp_path / "options.json"

    def _set(**opts):
        path.write_text(json.dumps(opts), encoding="utf-8")
        monkeypatch.setattr(config, "OPTIONS_PATH", str(path))
    return _set


@pytest.fixture
def make_friend():
    """make_friend(name, tier="good", **columns) inserts a row directly (any column, incl. added) and returns its id."""
    def _make(name="Alex", tier="good", added=None, **cols):
        row = {"name": name, "tier": tier, "added": added or datetime.date.today().isoformat(), **cols}
        keys = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        return db.run(f"INSERT INTO friends({keys}) VALUES({marks})", tuple(row.values()))
    return _make


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def client_from():
    """client_from("172.30.32.2") -> a TestClient whose requests arrive from that IP address."""
    def _make(host):
        async def app(scope, receive, send):
            if scope["type"] in ("http", "websocket"):
                scope = {**scope, "client": (host, 50000)}
            await api.app(scope, receive, send)
        return TestClient(app)
    return _make


@pytest.fixture
def in_home_assistant(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-token")
