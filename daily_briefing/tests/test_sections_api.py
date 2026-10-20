"""sections.py (orchestration, sensors, morning summary) and api.py (page, JSON, ingress check)."""
import datetime
import re
import urllib.error

import pytest

import addons
import ha
import sections
import sections_ha
from conftest import TZ


def stub_sections(monkeypatch, **results):
    """Replace the builders: key -> dict to return, an exception to raise, or missing -> a trivial ok section."""
    def make(key):
        def fn():
            v = results.get(key, {"headline": f"{key} ok", "lines": [f"{key} ok"]})
            if isinstance(v, Exception):
                raise v
            return v
        return fn
    monkeypatch.setattr(sections, "SECTIONS", [(k, t, i, make(k)) for k, t, i, _ in sections.SECTIONS])


# ---------------------------------------------------------------- build
def test_a_failing_section_is_unavailable_and_the_rest_still_show(monkeypatch):
    stub_sections(monkeypatch, workout=urllib.error.URLError("down"))
    data = sections.build()
    by = {s["key"]: s for s in data["sections"]}
    assert by["workout"]["status"] == "unavailable" and by["workout"]["lines"] == ["Unavailable"]
    assert by["meals"]["status"] == "ok" and len(data["sections"]) == 7
    assert data["date"] == "Monday, October 19"


def test_off_sections_say_why(monkeypatch):
    stub_sections(monkeypatch, ski=addons.Off("Off season"))
    ski = next(s for s in sections.build()["sections"] if s["key"] == "ski")
    assert ski["status"] == "off" and ski["headline"] == "Off season"


def test_section_keys_match_the_dashboard():
    keys = {k for k, *_ in sections.SECTIONS}
    text = open(f"{api_dir()}/dashboard.yaml", encoding="utf-8").read()
    assert set(re.findall(r"sensor\.daily_briefing_(\w+)", text)) == keys


def api_dir():
    import api
    return api.HERE


def test_notification_text_skips_unavailable_and_off(monkeypatch):
    stub_sections(monkeypatch, today={"headline": "Mon", "lines": ["Monday, October 19", "Sunny, 70°F", "", "9:00 AM  Standup"]},
                  workout=RuntimeError("x"), ski=addons.Off("Off season"), meals={"headline": "Dinner: Tacos", "lines": []})
    text = sections.notification_text(sections.build())
    assert text.startswith("Monday, October 19\nSunny, 70°F\n9:00 AM  Standup")
    assert "Meals: Dinner: Tacos" in text and "Workout" not in text and "Ski" not in text


# ---------------------------------------------------------------- sensors
def test_publish_writes_one_sensor_per_section_plus_summary(fake_ha, monkeypatch):
    stub_sections(monkeypatch, shopping={"headline": "2 items", "lines": ["milk", "eggs"], "count": 2})
    data = sections.build()
    assert sections.publish(data) == 8
    names = [w[0] for w in fake_ha.writes]
    assert names[-1] == "sensor.daily_briefing_summary" and "sensor.daily_briefing_shopping" in names
    shop = next(w for w in fake_ha.writes if w[0] == "sensor.daily_briefing_shopping")
    assert shop[1] == "2 items" and shop[2]["lines"] == ["milk", "eggs"] and shop[2]["markdown"] == "milk\n\neggs" and shop[2]["count"] == 2
    assert sections.publish(data) == 0                       # nothing changed: nothing written


def test_publish_rewrites_only_what_changed(fake_ha, monkeypatch):
    stub_sections(monkeypatch)
    sections.publish(sections.build())
    fake_ha.writes.clear()
    stub_sections(monkeypatch, meals={"headline": "Dinner: Pasta", "lines": ["Dinner: Pasta"]})
    assert sections.publish(sections.build()) == 2           # meals + the summary that quotes it
    assert {w[0] for w in fake_ha.writes} == {"sensor.daily_briefing_meals", "sensor.daily_briefing_summary"}


# ---------------------------------------------------------------- the loop
def at(hour, minute=0):
    return datetime.datetime(2026, 10, 19, hour, minute, tzinfo=TZ)


def test_morning_summary_sent_once_after_the_time(fake_ha, monkeypatch):
    stub_sections(monkeypatch)
    fake_ha.phones = ["mobile_app_pixel_9"]
    monkeypatch.setattr(sections_ha, "now", lambda: at(6, 59))
    sections._tick(first=True)
    assert fake_ha.notifications == []
    monkeypatch.setattr(sections_ha, "now", lambda: at(7, 0))
    sections._tick(first=False)
    sections._tick(first=False)
    assert len(fake_ha.notifications) == 1
    svc, body = fake_ha.notifications[0]
    assert svc == "mobile_app_pixel_9" and body["title"] == "Good morning · Monday, October 19"


def test_started_after_the_morning_time_does_not_send_late(fake_ha, monkeypatch):
    stub_sections(monkeypatch)
    fake_ha.phones = ["mobile_app_pixel_9"]
    monkeypatch.setattr(sections_ha, "now", lambda: at(9, 30))
    sections._tick(first=True)
    sections._tick(first=False)
    assert fake_ha.notifications == []


def test_morning_summary_can_be_turned_off(fake_ha, monkeypatch, set_options):
    set_options(morning_notification=False)
    stub_sections(monkeypatch)
    fake_ha.phones = ["mobile_app_pixel_9"]
    monkeypatch.setattr(sections_ha, "now", lambda: at(6, 0))
    sections._tick(first=True)
    monkeypatch.setattr(sections_ha, "now", lambda: at(8, 0))
    sections._tick(first=False)
    assert fake_ha.notifications == []


def test_morning_summary_waits_for_a_phone(fake_ha, monkeypatch):
    stub_sections(monkeypatch)
    monkeypatch.setattr(sections_ha, "now", lambda: at(6, 0))
    sections._tick(first=True)
    monkeypatch.setattr(sections_ha, "now", lambda: at(7, 5))
    sections._tick(first=False)
    assert fake_ha.notifications == [] and sections._sent["on"] is None
    fake_ha.phones = ["mobile_app_pixel_9"]
    ha._phone["at"] = 0.0
    sections._tick(first=False)
    assert len(fake_ha.notifications) == 1


def test_failed_send_is_not_repeated_every_minute(fake_ha, monkeypatch):
    stub_sections(monkeypatch)
    fake_ha.phones = ["mobile_app_pixel_9"]
    monkeypatch.setattr(sections_ha, "now", lambda: at(6, 0))
    sections._tick(first=True)
    monkeypatch.setattr(sections_ha, "now", lambda: at(7, 1))
    calls = []

    def fail(*a, **k):
        calls.append(1)
        raise RuntimeError("phone offline")
    monkeypatch.setattr(ha, "send_summary", fail)
    sections._tick(first=False)
    sections._tick(first=False)
    assert len(calls) == 1


def test_tick_outside_home_assistant_does_not_publish(monkeypatch):
    stub_sections(monkeypatch)
    monkeypatch.setattr(ha, "_call", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no Home Assistant call expected")))
    sections._tick(first=True)
    assert sections.latest()["sections"]


# ---------------------------------------------------------------- web
def test_page_and_assets(client):
    r = client.get("/")
    assert r.status_code == 200 and "Daily Briefing" in r.text and "__V__" not in r.text and 'rel="icon"' in r.text
    assert client.get("/static/icon.png").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_briefing_json(client, monkeypatch):
    stub_sections(monkeypatch)
    d = client.get("/api/briefing").json()
    assert d["date"] == "Monday, October 19" and [s["key"] for s in d["sections"]][:2] == ["today", "workout"] and d["version"]


def test_dashboard_yaml_is_served_and_parses(client):
    yaml = pytest.importorskip("yaml")
    r = client.get("/api/dashboard.yaml")
    doc = yaml.safe_load(r.text)
    grid = doc["views"][0]["cards"][0]
    assert grid["type"] == "grid" and len(grid["cards"]) == 7


def test_only_ingress_may_call_inside_home_assistant(monkeypatch):
    from starlette.testclient import TestClient
    import api
    monkeypatch.setenv("SUPERVISOR_TOKEN", "t")

    def from_host(host):
        async def app(scope, receive, send):
            if scope["type"] == "http":
                scope = {**scope, "client": (host, 50000)}
            await api.app(scope, receive, send)
        return TestClient(app)
    assert from_host("172.30.32.2").get("/").status_code == 200
    r = from_host("172.30.33.4").get("/api/briefing")
    assert r.status_code == 403 and "Open Daily Briefing from Home Assistant" in r.json()["detail"]
