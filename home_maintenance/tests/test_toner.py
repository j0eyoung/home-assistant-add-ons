import db
import toner


def st(v, name="HP Black Toner"):
    return {"state": v, "attributes": {"friendly_name": name}}


def test_low_toner_alerts_once_and_rearms(ha_log, options):
    options(toner_entities="sensor.hp_black_toner", toner_threshold=15, printer_model="HP M255")
    ha_log["states"]["sensor.hp_black_toner"] = st("40")
    assert toner.check()[0]["status"] == "ok"
    ha_log["states"]["sensor.hp_black_toner"] = st("12")
    assert toner.check()[0]["status"] == "low"
    toner.check()
    assert ha_log["todo"] == ["HP M255 Black toner cartridge"] and len(ha_log["notify"]) == 1
    ha_log["states"]["sensor.hp_black_toner"] = st("100")      # new cartridge
    toner.check()
    ha_log["states"]["sensor.hp_black_toner"] = st("10")
    toner.check()
    assert len(ha_log["todo"]) == 2


def test_unavailable_is_graceful_and_keeps_last_level(ha_log, options):
    options(toner_entities="sensor.a sensor.b")
    ha_log["states"]["sensor.a"] = st("55", "Cyan Toner")
    ha_log["states"]["sensor.b"] = st("unavailable")
    res = {r["entity_id"]: r for r in toner.check()}
    assert res["sensor.a"]["level"] == 55 and res["sensor.b"]["status"] == "unavailable"
    ha_log["states"]["sensor.a"] = st("unavailable")
    r = toner.check()[0]
    assert r["status"] == "unavailable" and r["level"] == 55 and not ha_log["todo"]


def test_missing_entity_and_ha_error(ha_log, options, monkeypatch):
    options(toner_entities="sensor.gone")
    assert toner.check()[0]["status"] == "unavailable"
    monkeypatch.setattr(toner.ha, "get_state", lambda e: 1 / 0)
    assert toner.check()[0]["status"] == "unavailable"


def test_failed_alert_retries(ha_log, options, monkeypatch):
    options(toner_entities="sensor.a")
    ha_log["states"]["sensor.a"] = st("5", "Black Toner")
    monkeypatch.setattr(toner.ha, "add_todo", lambda t: 1 / 0)
    monkeypatch.setattr(toner.ha, "notify_service", lambda: "")
    assert toner.check()[0]["alerted"] is False
    monkeypatch.setattr(toner.ha, "add_todo", lambda t: ha_log["todo"].append(t))
    assert toner.check()[0]["alerted"] is True and ha_log["todo"] == ["Black toner cartridge"]


def test_no_write_when_unchanged(ha_log, options):
    options(toner_entities="sensor.a")
    ha_log["states"]["sensor.a"] = st("50", "Black Toner")
    toner.check()
    first = db.rows("SELECT checked_at FROM toner")[0]["checked_at"]
    toner.check()
    assert db.rows("SELECT checked_at FROM toner")[0]["checked_at"] == first


def test_label_and_cartridge_naming(options):
    options(printer_model="HP M255")
    assert toner.label("sensor.x", st("1", "HP M255 Cyan Toner level")) == "HP M255 Cyan"
    assert toner.cartridge("sensor.x", st("1", "HP M255 Cyan Toner level")) == "HP M255 Cyan toner cartridge"
