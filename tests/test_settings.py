import json
from fastapi.testclient import TestClient
from server import settings as st
from server.app import app

def _paths(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "SETTINGS_PATH", str(tmp_path / "s.json"))
    monkeypatch.setattr(st, "AUDIT_PATH", str(tmp_path / "a.jsonl"))

def test_defaults_are_off(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    s = st.load_settings()
    assert s["drift_enabled"] is False and s["notes_matching"] is False and s["send_to_sf"] is False

def test_save_writes_audit(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    st.save_settings({"drift_enabled": True}, actor="Practice manager")
    line = json.loads(open(tmp_path / "a.jsonl").read().splitlines()[-1])
    assert line["actor"] == "Practice manager" and line["changes"] == {"drift_enabled": True}

def test_settings_change_requires_admin_token(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", "a")
    c = TestClient(app)
    assert c.post("/api/settings", json={"drift_enabled": True}).status_code == 401
    assert c.post("/api/settings", headers={"X-Admin-Token": "a"}, json={"drift_enabled": True}).json()["drift_enabled"] is True


def _live(tmp_path, monkeypatch):
    p = tmp_path / "live.jsonl"
    monkeypatch.setattr(st, "LIVE_EVENTS_PATH", str(p))
    return p

def test_get_settings_returns_settings_and_audit(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    st.save_settings({"notes_matching": True}, actor="Practice manager")
    body = TestClient(app).get("/api/settings").json()
    assert body["drift_enabled"] is False and body["notes_matching"] is True
    assert body["audit"][-1]["changes"] == {"notes_matching": True}

def test_invalid_settings_rejected(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", "a")
    c = TestClient(app)
    for bad in ({"retention_days": 60}, {"drift_enabled": "yes"}, {"nope": 1}, {"contracts_watched": ["C-99"]}):
        assert c.post("/api/settings", headers={"X-Admin-Token": "a"}, json=bad).status_code == 422
    assert st.load_settings() == st.DEFAULTS

def test_purge_deletes_live_events_only_when_drift_off(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    live = _live(tmp_path, monkeypatch)
    live.write_text('{"event": "claim_opened"}\n')
    saved = st.save_settings({"drift_enabled": True, "purge": True}, actor="x")
    assert "purge" not in saved and live.exists()
    st.save_settings({"drift_enabled": False, "purge": True}, actor="x")
    assert not live.exists()
    assert "purge" not in json.loads(open(tmp_path / "s.json").read())

def test_prune_old_events_keeps_recent(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    _paths(tmp_path, monkeypatch)
    live = _live(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    old = {"event": "claim_opened", "ts": (now - timedelta(days=45)).isoformat()}
    new = {"event": "claim_opened", "ts": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z")}
    live.write_text(json.dumps(old) + "\n" + json.dumps(new) + "\n")
    st.prune_old_events()
    assert [json.loads(l) for l in live.read_text().splitlines()] == [new]
