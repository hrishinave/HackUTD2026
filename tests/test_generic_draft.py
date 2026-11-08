"""Drafting for any company (not just the Medicare demo), per-company contracts and drafts, transcript export.

Never touches the real data/ folder: drafts, approved contracts, settings and states all live in tmp_path.
"""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from server import contract_draft as cd
from server import contracts as ct
from server import routes_engine as eng
from server import settings as st
from server.contracts import validate_contract
from server.engine import InterviewSession

NULL = {k: None for k in cd.ALL_PARAMS}
CO = "randstad_technology_solutions"

# Speech-recognition style transcript: short fragments, like the real INT-09.
STATE = {
    "interview_id": "INT-50", "company_id": CO, "company_name": "randstad technology solutions",
    "person_name": "Pat Doe", "label": "Pat Doe", "position": "Software Engineer", "interviewee": "pat_doe",
    "transcript": [
        {"t_ms": 6039, "text": "hello"},
        {"t_ms": 39394, "text": "so I recently worked on"},
        {"t_ms": 42825, "text": "fixing up the Cobalt Scripts"},
        {"t_ms": 45551, "text": "that are honestly pretty"},
        {"t_ms": 49476, "text": "old and slow"},
        {"t_ms": 76021, "text": "that usually takes about 20 minutes for that script to run and it's really slow "
                                "I would really hope that with new implementations we can get it down to 3 minutes"},
        {"t_ms": 98918, "text": "I would personally like to just switch the python because it's a more modern language"},
    ],
    "played": [{"id": "Q-13", "bank_id": None, "text": "How long does one of those scripts take to run?",
                "target": "volume", "reason": "", "origin": "ai", "played_at": 53887}],
    "questions": {"Q-13": {"cue": "Detail:", "text": "How long does one of those scripts take to run?"}},
    "contradictions": [], "slot_fills": {},
}


def spec(**kw):
    s = {"requirement": "The nightly COBOL batch script finishes in about 3 minutes.", "feature": "Batch jobs",
         "role": "whatever", "template": "median_duration",
         "params": {**NULL, "start_event": "script_run_started", "end_event": "script_run_finished"},
         "population": {"description": "Batch script runs", "filter_key": None, "filter_value": None},
         "stated_value": 1200, "target": 180, "metric_id": "script_run_seconds",
         "metric_description": "Median seconds per script run",
         "quotes": ["that usually takes about 20 minutes for that script to run"],
         "rule_ids": [], "criticality": "high", "rationale": "Stated duration and goal."}
    s.update(kw)
    return s


LOOP = {"requirement": "Engineers can write the batch logic in Python.", "feature": "Tooling", "role": "x",
        "quotes": ["I would personally like to just switch the python"], "why_unmeasurable": "A preference.",
        "suggested_event_name": "Script Language Changed", "suggested_event_props": ["language", "Old Language"]}


def stub(drafts=(), loops=(), seen=None):
    async def call(system, user):
        if seen is not None:
            seen.update(system=system, user=user)
        return {"drafts": list(drafts), "open_loops": list(loops)}
    return call


def run(drafts=(), loops=(), state=None, iid="INT-50", persist=False, seen=None):
    return asyncio.run(cd.draft_contracts(iid, state=state or STATE, call=stub(drafts, loops, seen), persist=persist))


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "DRAFTS_DIR", tmp_path / "drafts")
    monkeypatch.setattr(cd, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(ct, "APPROVED_PATH", tmp_path / "approved.json")
    monkeypatch.setattr(st, "AUDIT_PATH", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(st, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(st, "LIVE_EVENTS_PATH", str(tmp_path / "live.jsonl"))
    monkeypatch.setattr(eng, "STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(eng, "sessions", {})
    (tmp_path / "state").mkdir()


def save_state(tmp_path, state):
    (tmp_path / "state" / f"{state['interview_id']}.json").write_text(json.dumps(state))


def client():
    from server.app import app
    return TestClient(app)


# ---------- generic drafting ----------

def test_generic_duration_becomes_interview_baselined_contract():
    out = run([spec()])
    assert out["mode"] == "generic" and out["company_id"] == CO and out["rejected"] == []
    item = out["items"][0]
    c = item["contract"]
    assert validate_contract(c) == []
    assert c["role"] == "software_engineer" and c["company_id"] == CO and item["company_id"] == CO
    e = c["expectations"][0]
    assert e["params"] == {"start_event": "script_run_started", "end_event": "script_run_finished"}
    assert (e["target"], e["tolerance"], e["unit"], e["comparator"]) == (180, 45, "seconds", "<=")
    assert c["baseline"]["source"] == "interview" and c["baseline"]["values"] == {"script_run_seconds": 1200}
    assert c["confidence"] | {"note": ""} == {"level": "medium", "said": True, "did": False, "code": False, "note": ""}
    assert c["code_refs"] == [] and c["events_required"] == ["script_run_started", "script_run_finished"]
    ev = c["evidence"][0]
    assert ev["question_id"] == "Q-13" and ev["question_origin"] == "ai" and ev["speaker"] == "Pat Doe"
    assert ev["timestamp"] == "01:16" and ev["interview_id"] == "INT-50"


def test_generic_without_a_number_is_low_confidence():
    c = run([spec(template="rate_per_person_week", stated_value=None, target=None,
                  params={**NULL, "event": "script_rerun_manually"})])["items"][0]["contract"]
    assert c["confidence"]["level"] == "low" and c["baseline"]["values"] == {}


def test_generic_open_loop_gets_role_company_and_snake_case_event():
    item = run(loops=[LOOP])["items"][0]
    ol = item["open_loop"]
    assert item["kind"] == "open_loop" and ol["role"] == "software_engineer" and ol["company_id"] == CO
    assert ol["suggested_event"] == {"name": "script_language_changed", "props": ["language", "old_language"]}


def test_generic_rejects_bad_names_and_fabricated_quotes():
    out = run([spec(params={**NULL, "start_event": "Script Started", "end_event": "script_run_finished"}),
               spec(quotes=["we never run scripts here"]),
               spec(params={**NULL, "start_event": "script_run_started"})])
    reasons = [r["reasons"][0] for r in out["rejected"]]
    assert out["items"] == []
    assert reasons == ["bad start_event name 'Script Started'", "quote not found in transcript", "missing param end_event"]


def test_quote_spanning_speech_fragments_is_verified():
    c = run([spec(quotes=["fixing up the Cobalt Scripts that are honestly pretty old and slow"])])["items"][0]["contract"]
    ev = c["evidence"][0]
    assert ev["timestamp"] == "00:42" and ev["quote"] == "fixing up the Cobalt Scripts that are honestly pretty old and slow"


def test_generic_prompt_has_no_medicare_text():
    seen = {}
    run([spec()], seen=seen)
    system = seen["system"].lower()
    for word in ("medicare", "medical", "billing", "claim", "clmedit", "prior auth"):
        assert word not in system, word
    assert "randstad technology solutions" in system and '"software_engineer"' in system
    assert "Pat Doe, Software Engineer" in seen["user"] and "Q-13 played at 00:53" in seen["user"]


def test_generic_schema_takes_free_roles_and_stays_under_union_limit():
    from tests.test_contract_draft import _count_unions
    assert _count_unions(cd.GENERIC_DRAFT_SCHEMA) <= cd.UNION_LIMIT
    assert cd.GENERIC_DRAFT_SCHEMA["properties"]["drafts"]["items"]["properties"]["role"] == {"type": "string"}
    assert cd.DRAFT_SCHEMA["properties"]["drafts"]["items"]["properties"]["role"] == {"enum": cd.ROLES}


def test_fake_provider_drafts_an_open_loop_for_a_generic_company(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    out = asyncio.run(cd.draft_contracts("INT-50", state=STATE, persist=False))
    assert [r["kind"] for r in out["items"]] == ["open_loop"] and out["rejected"] == []


def test_role_slug():
    assert cd.role_slug("Software Engineer II") == "software_engineer_ii"
    assert cd.role_slug("  ") == "staff" and cd.role_slug("3D artist") == "role_3d_artist"


# ---------- schema ----------

def test_schema_accepts_generic_contract_and_long_ids():
    c = copy.deepcopy(run([spec()])["items"][0]["contract"])
    c.update(id="C-123")
    c["requirement"]["id"] = "R-100"
    c["evidence"][0]["interview_id"] = "INT-100"
    assert validate_contract(c) == []
    assert validate_contract({**c, "role": "billing_clerk"}) == []
    assert validate_contract({**c, "role": "Software Engineer"}) != []
    assert validate_contract({**c, "id": "C-1"}) != []
    assert validate_contract({**c, "company_id": ""}) != []


# ---------- per-company contracts and drafts ----------

def _approve_generic(tmp_path, state=STATE):
    save_state(tmp_path, state)
    out = run([spec()], state=state, iid=state["interview_id"], persist=True)
    return cd.approve_draft(out["items"][0]["draft_id"], actor="test")


def test_approved_generic_contract_is_scoped_to_its_company(tmp_path):
    res = _approve_generic(tmp_path)
    assert res["contract_id"] == "C-06"
    c6 = next(c for c in ct._approved()["contracts"] if c["id"] == "C-06")
    assert c6["company_id"] == CO and validate_contract(c6) == []
    assert "C-06" in st.load_settings(CO)["contracts_watched"]
    assert "C-06" not in st.load_settings()["contracts_watched"]
    api = client()
    assert [c["id"] for c in api.get("/api/contracts").json()] == ["C-01", "C-02", "C-03", "C-04", "C-05"]
    assert [c["id"] for c in api.get("/api/contracts?company_id=medicare_billing_demo").json()][-1] == "C-05"
    assert [c["id"] for c in api.get(f"/api/contracts?company_id={CO}").json()] == ["C-06"]
    assert api.get("/api/contracts?company_id=nobody").json() == []
    assert [c["id"] for c in ct.load_company_contracts(CO)] == ["C-06"]


def test_duplicates_are_checked_within_the_company_only(tmp_path):
    _approve_generic(tmp_path)
    again = run([spec()])
    assert again["rejected"][0]["reasons"] == ["duplicates C-06"]
    other = {**STATE, "interview_id": "INT-51", "company_id": "acme", "company_name": "Acme"}
    assert len(run([spec()], state=other, iid="INT-51")["items"]) == 1


def test_approved_open_loop_carries_company(tmp_path):
    save_state(tmp_path, STATE)
    out = run(loops=[LOOP], persist=True)
    cd.approve_draft(out["items"][0]["draft_id"], actor="test")
    assert [o["company_id"] for o in ct.load_company_open_loops(CO)] == [CO]
    assert all(o.get("company_id") in (None, "medicare_billing_demo") for o in ct.load_company_open_loops(None))


def test_drafts_filter_by_company(tmp_path):
    save_state(tmp_path, STATE)
    run([spec()], persist=True)
    demo = json.loads(open("tests/fixtures/state_draft.json").read())
    asyncio.run(cd.draft_contracts("INT-09", state=demo, call=stub(loops=[{
        "requirement": "r", "feature": "f", "role": "billing_clerk",
        "quotes": ["If a claim sits pending more than 30 days I phone the payer"], "why_unmeasurable": "w",
        "suggested_event_name": "payer_call_logged", "suggested_event_props": []}]), legacy_events=[]))
    # an old-format record with no company_id falls back to its interview's saved state
    (tmp_path / "drafts" / "INT-52.json").write_text(json.dumps({"interview_id": "INT-52", "items": [
        {"draft_id": "DR-INT-52-1", "kind": "open_loop", "status": "draft"}]}))
    save_state(tmp_path, {**STATE, "interview_id": "INT-52"})
    api = client()
    assert len(api.get("/api/drafts").json()) == 3
    assert sorted(r["draft_id"] for r in api.get(f"/api/drafts?company_id={CO}").json()) == ["DR-INT-50-1", "DR-INT-52-1"]
    assert [r["draft_id"] for r in api.get("/api/drafts?company_id=medicare_billing_demo").json()] == ["DR-INT-09-1"]
    assert api.get("/api/drafts?company_id=acme").json() == []


def test_lifecycle_for_generic_company_shows_its_contract(tmp_path):
    _approve_generic(tmp_path)
    stages = client().get(f"/api/lifecycle?company_id={CO}").json()
    assert set(stages) == {"C-06"}


# ---------- POST /api/drafts ----------

def test_post_drafts_empty_transcript_is_422(tmp_path):
    save_state(tmp_path, {**STATE, "interview_id": "INT-60", "transcript": [{"t_ms": 1, "text": "  "}]})
    r = client().post("/api/drafts", json={"interview_id": "INT-60"})
    assert r.status_code == 422 and r.json()["detail"] == "no transcript yet"
    assert client().post("/api/drafts", json={"interview_id": "INT-61"}).status_code == 404


def test_post_drafts_uses_a_running_unsaved_session(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    s = InterviewSession("INT-70", "pat_doe", brief="", bank={}, plan=[], company_id=CO)
    s.company_name, s.person_name, s.position, s.label = "Randstad", "Pat Doe", "Software Engineer", "Pat Doe"
    s.add_utterance("the nightly export script takes about twenty minutes", 5000)
    monkeypatch.setattr(eng, "sessions", {"INT-70": SimpleNamespace(session=s)})
    r = client().post("/api/drafts", json={"interview_id": "INT-70"})
    assert r.status_code == 200
    body = r.json()
    assert body["company_id"] == CO and [i["kind"] for i in body["items"]] == ["open_loop"]
    assert body["items"][0]["open_loop"]["role"] == "software_engineer"


# ---------- transcript export ----------

def test_transcript_markdown_for_saved_interview(tmp_path):
    state = {**STATE, "interview_id": "INT-80",
             "contradictions": [{"kind": "person_vs_self", "statement_a": "about 20 minutes",
                                 "statement_b": "an hour", "rule_id": None}]}
    save_state(tmp_path, state)
    r = client().get("/api/interviews/INT-80/transcript")
    assert r.status_code == 200 and r.headers["content-type"] == "text/markdown; charset=utf-8"
    md = r.text
    assert md.startswith("# Interview INT-80: Pat Doe, Software Engineer at randstad technology solutions\n")
    lines = md.splitlines()
    i_q = lines.index("[00:53] Q-13 asked: Detail: How long does one of those scripts take to run?  ")
    assert lines[i_q - 1].startswith("[00:49] old and slow") and lines[i_q + 1].startswith("[01:16] that usually")
    assert "## Contradictions" in md and '- person_vs_self: "about 20 minutes" vs "an hour"' in md


def test_transcript_markdown_for_running_session_and_404(monkeypatch):
    s = InterviewSession("INT-81", "pat_doe", brief="", bank={}, plan=[], company_id=CO)
    s.company_name, s.person_name, s.position = "Randstad", "Pat Doe", "Engineer"
    s.add_utterance("first line", 1000)
    monkeypatch.setattr(eng, "sessions", {"INT-81": SimpleNamespace(session=s)})
    md = client().get("/api/interviews/INT-81/transcript").text
    assert "Randstad" in md and "[00:01] first line" in md and "## Contradictions" not in md
    assert client().get("/api/interviews/INT-99/transcript").status_code == 404
