"""Status lifecycle: fired → acknowledged | escalated | false_positive;
false_positive is terminal; 404 unknown ids."""


def _create(client):
    resp = client.post("/api/v1/alerts", json={
        "object_id": "obj1",
        "camera_id": "cam1",
        "timestamp": "2026-09-23T12:00:00",
        "reason": "roi_intrusion",
        "threat_score": 0.6,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["alert_id"]


def test_escalate(client):
    aid = _create(client)
    resp = client.post(f"/api/v1/alerts/{aid}/escalate")
    assert resp.status_code == 200
    assert resp.json()["status"] == "escalated"


def test_false_positive(client):
    aid = _create(client)
    resp = client.post(f"/api/v1/alerts/{aid}/false-positive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "false_positive"


def test_terminal_false_positive_rejects_acknowledge(client):
    aid = _create(client)
    client.post(f"/api/v1/alerts/{aid}/false-positive")
    resp = client.post(f"/api/v1/alerts/{aid}/acknowledge")
    assert resp.status_code == 400
    assert "terminal" in resp.json()["detail"]


def test_escalate_then_acknowledge_allowed(client):
    aid = _create(client)
    client.post(f"/api/v1/alerts/{aid}/escalate")
    resp = client.post(f"/api/v1/alerts/{aid}/acknowledge")
    assert resp.status_code == 200
    assert resp.json()["status"] == "acknowledged"


def test_unknown_id_404(client):
    assert client.post("/api/v1/alerts/nope-404/escalate").status_code == 404
    assert client.post("/api/v1/alerts/nope-404/false-positive").status_code == 404


def test_terminal_false_positive_rejects_escalate(client):
    aid = _create(client)
    client.post(f"/api/v1/alerts/{aid}/false-positive")
    resp = client.post(f"/api/v1/alerts/{aid}/escalate")
    assert resp.status_code == 400
    assert "terminal" in resp.json()["detail"]


def test_terminal_false_positive_rejects_false_positive(client):
    aid = _create(client)
    client.post(f"/api/v1/alerts/{aid}/false-positive")
    resp = client.post(f"/api/v1/alerts/{aid}/false-positive")
    assert resp.status_code == 400
    assert "terminal" in resp.json()["detail"]


def test_patch_status_on_terminal_returns_400_and_keeps_status(client):
    aid = _create(client)
    client.post(f"/api/v1/alerts/{aid}/false-positive")
    resp = client.patch(f"/api/v1/alerts/{aid}", json={"status": "acknowledged"})
    assert resp.status_code == 400
    assert "terminal" in resp.json()["detail"]
    assert client.get(f"/api/v1/alerts/{aid}").json()["status"] == "false_positive"


def test_enrichment_patch_does_not_resurrect_terminal(client):
    aid = _create(client)
    client.post(f"/api/v1/alerts/{aid}/false-positive")
    resp = client.patch(f"/api/v1/alerts/{aid}", json={"ai_explanation": "late enrichment"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "false_positive"
    assert body["ai_explanation"] == "late enrichment"


def test_patch_invalid_status_returns_400(client):
    aid = _create(client)
    resp = client.patch(f"/api/v1/alerts/{aid}", json={"status": "bogus"})
    assert resp.status_code == 400
    assert client.get(f"/api/v1/alerts/{aid}").json()["status"] == "fired"
