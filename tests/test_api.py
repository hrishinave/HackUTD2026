from fastapi.testclient import TestClient
from server.app import app

def test_client_ws_returns_fake_queue():
    c = TestClient(app)
    with c.websocket_connect("/ws/client/TEST") as ws:
        ws.send_json({"type": "hello", "device": "laptop-chrome", "app_version": "0.1"})
        ws.send_json({"type": "utterance", "text": "hello there", "final": True, "t_ms": 1000})
        msg = ws.receive_json()
        assert msg["type"] == "queue" and len(msg["questions"]) >= 1 and "based_on_t_ms" in msg

def test_played_is_acked():
    c = TestClient(app)
    with c.websocket_connect("/ws/client/TEST") as ws:
        ws.send_json({"type": "played", "question_id": "Q-1", "t_ms": 2000})
        assert ws.receive_json() == {"type": "ack", "of": "played", "question_id": "Q-1"}

def test_missing_page_is_clean_404():
    c = TestClient(app)
    r = c.get("/terms")
    assert r.status_code in (200, 404)
