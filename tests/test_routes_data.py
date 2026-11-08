"""Route tests for server/routes_data.py (owner: AK, role D). Never touch the real data/ folder."""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import drift as dr
from server import routes_data as rd
from server import settings as st
from server import simulate as sim

FIXTURE_STATE = Path(__file__).parent / "fixtures" / "state_sample.json"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "SETTINGS_PATH", str(tmp_path / "s.json"))
    monkeypatch.setattr(st, "AUDIT_PATH", str(tmp_path / "a.jsonl"))
    monkeypatch.setattr(st, "LIVE_EVENTS_PATH", str(tmp_path / "live.jsonl"))
    monkeypatch.setattr(sim, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(sim, "LOG_FACTS_PATH", tmp_path / "log_facts.json")
    monkeypatch.setattr(dr, "POST_EVENTS_PATH", tmp_path / "data" / "post_events.jsonl")
    monkeypatch.setattr(rd, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(rd, "_stub", {"next": 123})
    monkeypatch.setenv("ADMIN_TOKEN", "a")
    sim.write_outputs(7, sim.DEFAULT_SCENARIO)
    from server.app import app
    return TestClient(app)


def _on(**extra):
    st.save_settings({"drift_enabled": True, "notes_matching": True, **extra}, actor="test")


# /api/simulate

def test_simulate_needs_admin_token(api):
    assert api.post("/api/simulate", json={"seed": 7}).status_code == 401
    assert api.post("/api/simulate", headers={"X-Admin-Token": "wrong"}, json={"seed": 7}).status_code == 401


def test_simulate_writes_data(api, tmp_path):
    r = api.post("/api/simulate", headers={"X-Admin-Token": "a"}, json={"seed": 7})
    assert r.status_code == 200 and r.json()["post_events"] > 0
    assert (tmp_path / "data" / "post_events.jsonl").exists() and (tmp_path / "log_facts.json").exists()


# /api/drift and /api/findings

def test_drift_off_by_default(api):
    assert api.get("/api/drift").json() == {"enabled": False}
    assert api.get("/api/findings").json() == []


def test_drift_on_reports_statuses(api):
    _on()
    body = api.get("/api/drift").json()
    status = {c["contract_id"]: c["status"] for c in body["contracts"]}
    assert body["enabled"] is True
    assert status == {"C-01": "broken", "C-02": "holding", "C-03": "holding", "C-04": "holding", "C-05": "holding"}
    c02 = next(c for c in body["contracts"] if c["contract_id"] == "C-02")
    assert [w["state"] for w in c02["weekly"] if w["week"] == 5] == ["breach"]


def test_drift_respects_watched(api):
    _on(contracts_watched=["C-02"])
    assert [c["contract_id"] for c in api.get("/api/drift").json()["contracts"]] == ["C-02"]


def test_findings_route(api):
    _on()
    fs = api.get("/api/findings").json()
    assert [f["id"] for f in fs] == ["F-01"] and fs[0]["status"] == "broken" and fs[0]["type"] == "app_gap"


# Software Factory payload and stub

def test_sf_payload_403_when_sending_off(api):
    _on()
    assert api.get("/api/findings/F-01/sf-payload").status_code == 403


def test_sf_payload_and_stub_round_trip(api):
    _on(send_to_sf=True)
    p = api.get("/api/findings/F-01/sf-payload")
    assert p.status_code == 200 and set(p.json()) == {"end_user_email", "content"}
    first = api.post("/stub/v2/reporting-api/feedback", json=p.json())
    second = api.post("/stub/v2/reporting-api/feedback", json=p.json())
    assert first.json() == {"feedback_number": 123} and second.json() == {"feedback_number": 124}


def test_sf_payload_404_for_unknown_finding(api):
    _on(send_to_sf=True)
    assert api.get("/api/findings/F-99/sf-payload").status_code == 404


def test_stub_rejects_bad_payload(api):
    r = api.post("/stub/v2/reporting-api/feedback", json={"end_user_email": "a@b.c", "content": "x", "title": "no"})
    assert r.status_code == 422 and r.json()["detail"]["details"]
    assert api.post("/stub/v2/reporting-api/feedback", content=b"not json",
                    headers={"content-type": "application/json"}).status_code == 422


# /api/eval

def test_eval_with_no_interviews(api):
    body = api.get("/api/eval").json()
    assert body["interviews"] == 0 and body["rules_found"] == [] and body["rules_total"] == 7


def test_eval_scores_saved_interviews(api, tmp_path):
    (tmp_path / "state").mkdir()
    shutil.copy(FIXTURE_STATE, tmp_path / "state" / "INT-01.json")
    body = api.get("/api/eval").json()
    assert body["interviews"] == 1
    assert body["rules_found"] == ["PA-SCAN", "RETRO-ELIG", "TF-365"]
    assert body["hidden_found"] == 1 and body["hidden_total"] == 4      # RETRO-ELIG is the hidden one found
    assert body["contradictions_matched"] == ["X-1"] and body["contradictions_total"] == 2


def test_eval_reads_wrapped_state_files(api, tmp_path):
    (tmp_path / "state").mkdir()
    wrapped = {"state": json.loads(FIXTURE_STATE.read_text()), "counters": {"calls": 3}}
    (tmp_path / "state" / "INT-01.json").write_text(json.dumps(wrapped))
    assert api.get("/api/eval").json()["rules_found"] == ["PA-SCAN", "RETRO-ELIG", "TF-365"]
