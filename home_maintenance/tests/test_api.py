def test_state_and_presets(client):
    import tasks
    tasks.seed_presets()
    s = client.get("/api/state").json()
    assert len(s["tasks"]) == 6 and s["toner"] == []
    assert all(p["added"] for p in client.get("/api/presets").json())


def test_task_crud_done_snooze(client):
    t = client.post("/api/tasks", json={"name": "Dryer vent", "interval_value": 1, "interval_unit": "days"}).json()
    assert client.post(f"/api/tasks/{t['id']}/snooze", json={"days": 2}).json()["snoozed_until"]
    d = client.post(f"/api/tasks/{t['id']}/done", json={"note": "cleaned", "cost": 0}).json()
    assert d["days_until"] == 1
    assert client.get(f"/api/tasks/{t['id']}/history").json()[0]["note"] == "cleaned"
    assert client.patch(f"/api/tasks/{t['id']}", json={"interval_value": 2}).json()["interval_value"] == 2
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 200
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 404


def test_validation(client):
    assert client.post("/api/tasks", json={"name": "x", "interval_value": 0}).status_code == 422
    assert client.post("/api/tasks", json={"name": "x", "interval_value": 1, "interval_unit": "weeks"}).status_code == 422
    assert client.post("/api/tasks", json={"name": "x", "interval_value": 1, "last_done": "nope"}).status_code == 422
    assert client.post("/api/tasks/999/done", json={}).status_code == 404


def test_toner_picker_saved_in_db(client, ha_log):
    r = client.put("/api/toner", json={"entities": ["sensor.hp_black"], "threshold": 20, "printer_model": "HP M255"})
    assert r.json()["threshold"] == 20 and r.json()["entities"][0]["status"] == "not checked yet"
    ha_log["states"]["sensor.hp_black"] = {"state": "unavailable", "attributes": {}}
    assert client.post("/api/toner/check").json()[0]["status"] == "unavailable"
    assert client.put("/api/toner", json={"entities": ["light.x"]}).status_code == 422



def test_new_endpoints(client, monkeypatch):
    import files
    a = client.post("/api/appliances", json={"name": "Dryer", "warranty_end": "2027-01-01", "lifespan_years": 10}).json()
    assert client.patch(f"/api/appliances/{a['id']}", json={"brand": "LG"}).json()["brand"] == "LG"
    assert client.post("/api/appliances", json={"name": "x", "warranty_end": "soon"}).status_code == 422
    t = client.post("/api/tasks", json={"name": "Lint", "interval_value": 3, "interval_unit": "months",
                                        "appliance_id": a["id"], "active_months": "1,2"}).json()
    assert t["appliance_id"] == a["id"] and t["active_months"] == "1,2"
    assert client.post("/api/tasks", json={"name": "x", "interval_value": 1, "active_months": "13"}).status_code == 422
    assert client.post(f"/api/tasks/{t['id']}/done", json={"parts": "vent kit"}).status_code == 200
    s = client.post("/api/shutoffs", json={"name": "Gas", "kind": "gas"}).json()
    assert client.post("/api/shutoffs", json={"name": "x", "kind": "steam"}).status_code == 422
    assert client.get("/api/digest").json()["horizon"]
    assert "BEGIN:VCALENDAR" in client.get("/api/calendar.ics").text
    st = client.get("/api/state").json()
    assert st["appliances"][0]["name"] == "Dryer" and st["shutoffs"][0]["id"] == s["id"] and st["storage_ready"] is False
    # no bucket: a clear 409, never a crash
    r = client.post(f"/api/appliances/{a['id']}/files?filename=r.jpg", content=b"jpg", headers={"content-type": "image/jpeg"})
    assert r.status_code == 409
    monkeypatch.setattr(files, "save", lambda *a_: {"id": 1, "filename": "r.jpg"})
    assert client.post(f"/api/shutoffs/{s['id']}/files?filename=r.jpg", content=b"jpg",
                       headers={"content-type": "image/jpeg"}).status_code == 200
    assert client.post("/api/appliances/999/files", content=b"x", headers={"content-type": "image/jpeg"}).status_code == 404
    assert client.get("/api/files/999").status_code == 404
    assert client.delete(f"/api/appliances/{a['id']}").status_code == 200


def test_unlink_task_from_appliance(client):
    a = client.post("/api/appliances", json={"name": "Dryer"}).json()
    t = client.post("/api/tasks", json={"name": "Lint", "interval_value": 3, "appliance_id": a["id"]}).json()
    assert client.patch(f"/api/tasks/{t['id']}", json={"appliance_id": 0, "active_months": ""}).json()["appliance_id"] is None


def test_index_serves_ui_with_version(client):
    r = client.get("/")
    assert r.status_code == 200 and "static/app.js?v=0." in r.text and "__V__" not in r.text
    assert client.get("/static/app.js").status_code == 200 and client.get("/static/icon.png").status_code == 200
