def test_timer_flow(client, clock):
    clock("2026-10-19 09:00")
    r = client.post("/api/timer/start", json={"client": "kiss", "case_no": "9832911", "note": "x"})
    assert r.status_code == 200 and r.json()["running"]["client"] == "KISS"
    clock("2026-10-19 10:00")
    s = client.get("/api/state").json()
    assert s["running"]["case_no"] == "9832911" and s["totals"]["day_minutes"] == 60
    assert client.post("/api/timer/stop").json()["stopped"]["end"].endswith("10:00:00")
    assert client.get("/api/state").json()["running"] is None


def test_bad_input_is_400(client, clock):
    clock("2026-10-19 09:00")
    assert client.post("/api/timer/start", json={"client": "bad code"}).status_code == 400
    assert client.post("/api/entries", json={"client": "KISS", "date": "nope", "minutes": 5}).status_code == 400
    assert client.get("/api/totals", params={"day": "x"}).status_code == 400
    assert client.post("/api/tasks", json={"title": " "}).status_code == 400


def test_entries_and_csv(client, clock):
    clock("2026-10-19 12:00")
    e = client.post("/api/entries", json={"client": "KISS", "case_no": "1", "date": "2026-10-19", "minutes": 50}).json()
    assert client.get("/api/entries").json()[0]["id"] == e["id"]
    assert client.patch(f"/api/entries/{e['id']}", json={"note": "n"}).json()["note"] == "n"
    csv = client.get("/api/export.csv")
    assert csv.headers["content-type"].startswith("text/csv") and "KISS,1,Y,50,0.75,n" in csv.text
    assert client.delete(f"/api/entries/{e['id']}").status_code == 200
    assert client.delete(f"/api/entries/{e['id']}").status_code == 404


def test_tasks(client, clock):
    clock("2026-10-19 12:00")
    t = client.post("/api/tasks", json={"title": "Follow up", "due": "2026-10-20", "client": "KISS"}).json()
    assert [x["id"] for x in client.get("/api/tasks").json()] == [t["id"]]
    assert client.post(f"/api/tasks/{t['id']}/snooze").status_code == 200
    assert client.patch(f"/api/tasks/{t['id']}", json={"due": None}).json()["due"] is None
    assert client.post(f"/api/tasks/{t['id']}/done").status_code == 200
    assert client.get("/api/tasks").json() == []
    assert len(client.get("/api/tasks", params={"done": True}).json()) == 1
    assert client.post("/api/tasks/999/done").status_code == 404


def test_only_ingress_allowed_inside_home_assistant(client, monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "t")
    assert client.get("/api/tasks").status_code == 403    # TestClient's host is not 172.30.32.2
