def test_cases_put_and_list(client):
    assert client.put("/api/cases/9832911", json={"status": "  Pending   customer "}).json() == \
        {"case_no": "9832911", "status": "Pending customer"}
    client.put("/api/cases/9832911", json={"status": "Closed"})
    assert [(c["case_no"], c["status"]) for c in client.get("/api/cases").json()] == [("9832911", "Closed")]
    assert client.get("/api/state").json()["cases"][0]["status"] == "Closed"


def test_cases_validation(client):
    assert client.put("/api/cases/9832911", json={"status": ""}).status_code == 400
    assert client.put("/api/cases/9832911", json={"status": "x" * 41}).status_code == 400
    assert client.put("/api/cases/bad%20no", json={"status": "ok"}).status_code == 400


def test_lan_port_needs_bearer_key(client, monkeypatch, set_options):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "t")
    assert client.get("/api/tasks").status_code == 403                       # no key configured: ingress only
    set_options(api_key="s3cret-key")
    assert client.get("/api/tasks").status_code == 403                       # no header
    assert client.get("/api/tasks", headers={"Authorization": "Bearer nope"}).status_code == 403
    assert client.get("/api/tasks", headers={"Authorization": "Bearer s3cret-key"}).status_code == 200
    assert client.get("/", headers={"Authorization": "Bearer s3cret-key"}).status_code == 403   # UI stays ingress-only
    assert client.get("/static/app.js", headers={"Authorization": "Bearer s3cret-key"}).status_code == 403
