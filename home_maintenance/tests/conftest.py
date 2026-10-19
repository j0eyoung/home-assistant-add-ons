"""Shared setup for the Home Maintenance tests. Run from the add-on folder:  python -m pytest tests -q -p no:cacheprovider

No Home Assistant, network or real database: DB_PATH / OPTIONS_PATH are set before any backend import, each test
gets a fresh SQLite file, and the background loop is stubbed out. Scratch files go under ~/.claude/scratchpad."""
import json
import os
import pathlib
import shutil
import sys

sys.dont_write_bytecode = True

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN = pathlib.Path.home() / ".claude" / "scratchpad" / "home-maintenance-tests" / f"run-{os.getpid()}"
RUN.mkdir(parents=True, exist_ok=True)
os.environ["DB_PATH"] = str(RUN / "import-time.db")
os.environ["OPTIONS_PATH"] = str(RUN / "options.json")
os.environ.pop("SUPERVISOR_TOKEN", None)
sys.path.insert(0, str(ROOT))

import reminders  # noqa: E402

_real_start = reminders.start
reminders.start = lambda: None
import api  # noqa: E402

reminders.start = _real_start
import config, db, ha, tasks, toner  # noqa: E402,F401
from starlette.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(db, "_keeper", None)
    monkeypatch.setattr(config, "OPTIONS_PATH", str(tmp_path / "options.json"))
    db.init_db()
    reminders._state.update(sent_on=None, retry_at=0.0, toner_at=0.0)
    yield


@pytest.fixture
def options(tmp_path):
    def set_(**kw):
        (tmp_path / "options.json").write_text(json.dumps(kw))
    return set_


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def ha_log(monkeypatch):
    """Records what would be sent to Home Assistant."""
    log = {"notify": [], "todo": [], "states": {}, "cleared": []}
    monkeypatch.setattr(ha, "notify_service", lambda: "mobile_app_test")
    monkeypatch.setattr(ha, "send_message", lambda svc, title, msg, tag: log["notify"].append((title, msg)))
    monkeypatch.setattr(ha, "send_due", lambda svc, t: log["notify"].append((t["name"], t["days_until"])))
    monkeypatch.setattr(ha, "add_todo", lambda text: log["todo"].append(text))
    monkeypatch.setattr(ha, "clear", lambda svc, tid: log["cleared"].append(tid))
    monkeypatch.setattr(ha, "get_state", lambda eid: log["states"].get(eid))
    return log
