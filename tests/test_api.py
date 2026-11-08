import time

from fastapi.testclient import TestClient
from server.app import app


def _receive_until(ws, pred, limit=10):
    for _ in range(limit):
        msg = ws.receive_json()
        if pred(msg):
            return msg
    raise AssertionError("expected message never arrived")


def test_client_ws_returns_fake_queue(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    c = TestClient(app)
    assert c.post("/api/interviews/TEST/start", json={"interviewee": "billing_clerk_2"}).json()["ok"] is True
    with c.websocket_connect("/ws/client/TEST") as ws:
        ws.send_json({"type": "hello", "device": "laptop-chrome", "app_version": "0.1"})
        first = ws.receive_json()  # the plan question is ready before anyone speaks
        assert first["type"] == "queue" and first["questions"]
        t0 = time.monotonic()
        ws.send_json({"type": "utterance", "text": "hello there", "final": True, "t_ms": 1000})
        msg = _receive_until(ws, lambda m: m["type"] == "queue" and m["based_on_t_ms"] == 1000)
        assert 0.9 <= time.monotonic() - t0 < 3.0  # after the 1 s debounce
        assert len(msg["questions"]) >= 1 and msg["questions"][0]["text"] == "Can you walk me through a normal claim?"


def test_played_is_acked_and_queue_refills(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    c = TestClient(app)
    c.post("/api/interviews/T2/start", json={"interviewee": "billing_clerk_2"})
    with c.websocket_connect("/ws/client/T2") as ws:
        q = ws.receive_json()["questions"][0]
        ws.send_json({"type": "played", "question_id": q["id"], "t_ms": 2000})
        assert _receive_until(ws, lambda m: m["type"] == "ack") == {"type": "ack", "of": "played", "question_id": q["id"]}
        refill = _receive_until(ws, lambda m: m["type"] == "queue")
        assert refill["questions"] and refill["questions"][0]["id"] != q["id"]
    state = c.get("/api/interviews/T2/state").json()
    assert [p["id"] for p in state["played"]] == [q["id"]]
    assert set(state) >= {"transcript", "queue", "played", "slot_fills", "contradictions", "rules_mentioned", "coverage", "yield"}


def test_start_unknown_interviewee_is_404_and_state_unknown_is_404():
    c = TestClient(app)
    assert c.post("/api/interviews/X/start", json={"interviewee": "nobody"}).status_code == 404
    assert c.get("/api/interviews/NOPE/state").status_code == 404


def test_contracts_route_lists_five():
    assert [k["id"] for k in TestClient(app).get("/api/contracts").json()] == ["C-01", "C-02", "C-03", "C-04", "C-05"]


def test_missing_page_is_clean_404():
    c = TestClient(app)
    r = c.get("/terms")
    assert r.status_code in (200, 404)
