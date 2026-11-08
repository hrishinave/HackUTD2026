import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import settings as st
from server.app import app


EVENT = {
    "event": "claim_opened", "role": "billing_clerk", "session_id": "s1",
    "props": {"claim_type": "professional", "requires_prior_auth": True, "procedure_code": "70553"},
}
HEADERS = {"X-Client-Token": "t"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "SETTINGS_PATH", str(tmp_path / "s.json"))
    monkeypatch.setattr(st, "AUDIT_PATH", str(tmp_path / "a.jsonl"))
    monkeypatch.setattr(st, "LIVE_EVENTS_PATH", str(tmp_path / "live.jsonl"))
    monkeypatch.setenv("CLIENT_WRITE_TOKEN", "t")
    return TestClient(app)


def test_events_rejected_when_drift_off(client):
    assert client.post("/api/events", headers=HEADERS, json=EVENT).status_code == 403
    assert not Path(st.LIVE_EVENTS_PATH).exists()


def test_events_need_token(client):
    st.save_settings({"drift_enabled": True}, actor="test")
    assert client.post("/api/events", json=EVENT).status_code == 401


def test_event_post_and_recent(client):
    st.save_settings({"drift_enabled": True}, actor="test")
    assert client.post("/api/events", headers=HEADERS, json=EVENT).status_code == 200
    bad = {**EVENT, "props": {**EVENT["props"], "notes": "PA 123456 see fax"}}
    assert client.post("/api/events", headers=HEADERS, json=bad).status_code == 422
    recent = client.get("/api/events/recent").json()
    assert len(recent) == 1 and recent[0]["event"] == "claim_opened" and recent[0]["week"] == 8
    assert recent[0]["actor_hash"] == hashlib.sha1(b"s1").hexdigest()[:10]
    assert recent[0]["session_id"] == "s1" and recent[0]["ts"]


def test_auth_and_consent_precede_body_parsing(client):
    for body in ("not json", "[]", "null"):
        assert client.post("/api/events", content=body).status_code == 401
        assert client.post("/api/events", headers=HEADERS, content=body).status_code == 403
    st.save_settings({"drift_enabled": True}, actor="test")
    assert client.post("/api/events", headers=HEADERS, content="not json").status_code == 422


@pytest.mark.parametrize("change", [
    {"event": "patient_notes"}, {"role": "patient"}, {"session_id": ""},
    {"session_id": "s" * 41}, {"patient_id": "DO-NOT-STORE"},
    {"props": {"text": "DO-NOT-STORE"}}, {"props": {"notes": "DO-NOT-STORE"}},
    {"props": {"procedure_code": "x" * 41}},
    {"props": {"procedure_code": {"text": "DO-NOT-STORE"}}},
    {"props": {"requires_prior_auth": "true"}}, {"props": []},
    {"event": "claim_tab_viewed", "props": {"tab": "patient-notes"}},
    {"event": "claim_submitted", "props": {"notes_patterns": ["DO-NOT-STORE"]}},
])
def test_invalid_event_never_written(client, change):
    st.save_settings({"drift_enabled": True}, actor="test")
    assert client.post("/api/events", headers=HEADERS, json={**EVENT, **change}).status_code == 422
    assert client.get("/api/events/recent").json() == []


def test_token_and_storage_path_are_read_per_request(client, monkeypatch, tmp_path):
    st.save_settings({"drift_enabled": True}, actor="test")
    monkeypatch.setenv("CLIENT_WRITE_TOKEN", "new")
    assert client.post("/api/events", headers=HEADERS, json=EVENT).status_code == 401
    monkeypatch.setattr(st, "LIVE_EVENTS_PATH", str(tmp_path / "changed.jsonl"))
    assert client.post("/api/events", headers={"X-Client-Token": "new"}, json=EVENT).status_code == 200
    assert len(client.get("/api/events/recent").json()) == 1


def test_recent_returns_last_fifty(client):
    Path(st.LIVE_EVENTS_PATH).write_text("".join(json.dumps({"n": n}) + "\n" for n in range(55)))
    assert [row["n"] for row in client.get("/api/events/recent").json()] == list(range(5, 55))


def test_notes_tags_follow_current_consent(client):
    st.save_settings({"drift_enabled": True}, actor="test")
    event = {**EVENT, "event": "claim_submitted", "props": {"notes_patterns": ["auth_number", "see_fax"]}}
    assert client.post("/api/events", headers=HEADERS, json=event).status_code == 200
    assert "notes_patterns" not in client.get("/api/events/recent").json()[-1]["props"]
    st.save_settings({"notes_matching": True}, actor="test")
    assert client.post("/api/events", headers=HEADERS, json=event).status_code == 200
    assert client.get("/api/events/recent").json()[-1]["props"]["notes_patterns"] == ["auth_number", "see_fax"]


def test_claim_injects_current_token_and_disables_caching(client, monkeypatch):
    monkeypatch.setenv("CLIENT_WRITE_TOKEN", 'test-token"<&')
    response = client.get("/claim")
    assert response.status_code == 200
    assert 'content="test-token&quot;&lt;&amp;"' in response.text
    assert "{{CLIENT_TOKEN}}" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_missing_token_configuration_fails_closed(client, monkeypatch):
    monkeypatch.delenv("CLIENT_WRITE_TOKEN")
    st.save_settings({"drift_enabled": True}, actor="test")
    assert client.post("/api/events", headers=HEADERS, json=EVENT).status_code == 401
    assert client.get("/claim").status_code == 503
