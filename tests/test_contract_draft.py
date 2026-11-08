import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import contract_draft as cd
from server import contracts as ct
from server import settings as st
from server.contracts import validate_contract
from server.simulate import generate, DEFAULT_SCENARIO

STATE = json.loads(Path("tests/fixtures/state_draft.json").read_text())
LEGACY, POST = generate(7, DEFAULT_SCENARIO)
NULL_PARAMS = {k: None for k in ["event", "flag", "tag", "start_event", "end_event", "task_start", "task_end",
                                 "loop_event", "max_loops", "trigger_event", "followup_event", "within_hours", "where_source_view"]}


def spec(**kw):
    s = {"requirement": "Weekly claim numbers reach the practice manager without clerks exporting spreadsheets.",
         "feature": "Reporting", "role": "billing_clerk", "template": "rate_per_person_week",
         "params": {**NULL_PARAMS, "event": "export_csv", "where_source_view": "claims"},
         "population": {"description": "Billing clerks' working weeks", "filter_key": None, "filter_value": None},
         "stated_value": 1.0, "target": None, "metric_id": "claims_export_rate",
         "metric_description": "Claims-list exports to CSV per clerk per week",
         "quotes": ["Every Friday I export the claims list to Excel for the practice manager"],
         "rule_ids": [], "criticality": "medium", "rationale": "Weekly manual export is a workaround."}
    s.update(kw)
    return s


LOOP = {"requirement": "Stuck claims are chased with the payer and tracked.", "feature": "Claim follow-up",
        "role": "billing_clerk", "quotes": ["If a claim sits pending more than 30 days I phone the payer"],
        "why_unmeasurable": "No event records payer calls.", "suggested_event_name": "payer_call_logged",
        "suggested_event_props": ["claim_id_hash", "days_pending"]}


def stub(drafts=(), loops=()):
    async def call(system, user):
        return {"drafts": list(drafts), "open_loops": list(loops)}
    return call


def run(drafts=(), loops=()):
    return asyncio.run(cd.draft_contracts("INT-09", state=STATE, call=stub(drafts, loops), legacy_events=LEGACY, persist=False))


def tmp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "DRAFTS_DIR", tmp_path / "drafts")
    monkeypatch.setattr(ct, "APPROVED_PATH", tmp_path / "approved.json")
    monkeypatch.setattr(st, "AUDIT_PATH", str(tmp_path / "audit.jsonl"))


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    # every test gets empty draft and approved storage, so local data/ never changes results
    tmp_storage(tmp_path, monkeypatch)


def test_valid_spec_becomes_schema_valid_contract():
    item = run([spec()])["items"][0]
    c = item["contract"]
    assert item["kind"] == "contract" and item["status"] == "draft" and validate_contract(c) == []
    e = c["expectations"][0]
    assert c["signal"] == "absence" and e["comparator"] == "<=" and e["target"] == 0.5 and e["tolerance"] == 0.5
    assert e["params"] == {"event": "export_csv", "where": {"source_view": "claims"}}
    assert c["events_required"] == ["export_csv"] and c["window"]["min_tasks"] == 5


def test_baseline_from_legacy_logs_corroborates_what_was_said():
    item = run([spec()])["items"][0]
    assert 0.8 <= item["baseline_value"] <= 1.2
    assert item["contract"]["confidence"]["did"] is True and item["contradiction"] is None


def test_said_and_logs_disagree_becomes_contradiction():
    item = run([spec(stated_value=5.0)])["items"][0]
    assert item["contradiction"]["kind"] == "person_vs_logs"
    assert item["contract"]["confidence"]["did"] is False and item["contract"]["confidence"]["level"] == "low"


def test_fabricated_quote_rejected():
    out = run([spec(quotes=["I never export anything"])])
    assert out["items"] == [] and "quote not found in transcript" in out["rejected"][0]["reasons"]


def test_unknown_event_rejected():
    out = run([spec(params={**NULL_PARAMS, "event": "report_viewed"})])
    assert "unknown event report_viewed" in out["rejected"][0]["reasons"]


def test_missing_template_param_rejected():
    out = run([spec(template="median_duration", params={**NULL_PARAMS, "start_event": "claim_opened"})])
    assert "missing param end_event" in out["rejected"][0]["reasons"]


def test_duplicate_of_existing_contract_rejected():
    dup = spec(template="median_duration", stated_value=240,
               params={**NULL_PARAMS, "start_event": "claim_opened", "end_event": "claim_submitted"})
    assert "duplicates C-02" in run([dup])["rejected"][0]["reasons"]


def test_unprompted_quote_has_no_question():
    ev = run([spec()])["items"][0]["contract"]["evidence"][0]
    assert ev["question_id"] is None and ev["question_origin"] == "unprompted" and ev["timestamp"] == "01:10"


def test_open_loop_lineage_and_instrumentation_suggestion():
    item = run(loops=[LOOP])["items"][0]
    ol = item["open_loop"]
    assert item["kind"] == "open_loop" and ol["suggested_event"]["name"] == "payer_call_logged"
    assert ol["evidence"][0]["question_id"] == "Q-4" and ol["evidence"][0]["question_origin"] == "interviewer"


def test_approve_assigns_next_ids_and_joins_catalog(tmp_path, monkeypatch):
    tmp_storage(tmp_path, monkeypatch)
    out = asyncio.run(cd.draft_contracts("INT-09", state=STATE, call=stub([spec()]), legacy_events=LEGACY))
    res = cd.approve_draft(out["items"][0]["draft_id"], actor="Keshav")
    assert res["contract_id"] == "C-06" and res["requirement_id"] == "R-07"
    assert "C-06" in [c["id"] for c in ct.load_all_contracts()]
    with pytest.raises(ValueError):
        cd.approve_draft(out["items"][0]["draft_id"], actor="Keshav")


def test_rerun_keeps_approved_and_skips_its_duplicate(tmp_path, monkeypatch):
    tmp_storage(tmp_path, monkeypatch)
    first = asyncio.run(cd.draft_contracts("INT-09", state=STATE, call=stub([spec()]), legacy_events=LEGACY))
    cd.approve_draft(first["items"][0]["draft_id"], actor="Keshav")
    second = asyncio.run(cd.draft_contracts("INT-09", state=STATE, call=stub([spec()]), legacy_events=LEGACY))
    assert "duplicates C-06" in second["rejected"][0]["reasons"]
    assert [r["status"] for r in cd.load_drafts("INT-09")] == ["approved"]


def test_approved_contract_holds_in_drift(tmp_path, monkeypatch):
    from server.drift import weekly_metrics, evaluate
    tmp_storage(tmp_path, monkeypatch)
    out = asyncio.run(cd.draft_contracts("INT-09", state=STATE, call=stub([spec()]), legacy_events=LEGACY))
    cd.approve_draft(out["items"][0]["draft_id"], actor="Keshav")
    c6 = [c for c in ct.load_all_contracts() if c["id"] == "C-06"][0]
    assert evaluate(c6, weekly_metrics(c6, POST, {"notes_matching": True}))["status"] == "holding"


def test_clerk_claims_exports_exist_and_are_the_only_clerk_exports():
    clerk_exports = [e for e in LEGACY + POST if e["role"] == "billing_clerk" and e["event"] == "export_csv"]
    assert clerk_exports and all(e["props"]["source_view"] == "claims" for e in clerk_exports)
    assert sum(1 for e in LEGACY if e["props"].get("source_view") == "claims") > sum(1 for e in POST if e["props"].get("source_view") == "claims")


def test_approved_contract_appears_in_drift_view(tmp_path, monkeypatch):
    # settings.py only accepts the five catalog IDs in contracts_watched; approved drafts must still be watched
    from server import drift as dr
    monkeypatch.setattr(st, "SETTINGS_PATH", str(tmp_path / "s.json"))
    monkeypatch.setattr(st, "LIVE_EVENTS_PATH", str(tmp_path / "live.jsonl"))
    post_path = tmp_path / "post.jsonl"
    post_path.write_text("".join(json.dumps(e) + "\n" for e in POST))
    monkeypatch.setattr(dr, "POST_EVENTS_PATH", post_path)
    out = asyncio.run(cd.draft_contracts("INT-09", state=STATE, call=stub([spec()]), legacy_events=LEGACY))
    cd.approve_draft(out["items"][0]["draft_id"], actor="Keshav")
    st.save_settings({"drift_enabled": True}, actor="test")
    rows = TestClient(__import__("server.app", fromlist=["app"]).app).get("/api/drift").json()["contracts"]
    assert ("C-06", "holding") in [(r["contract_id"], r["status"]) for r in rows]


def _count_unions(node) -> int:
    if isinstance(node, dict):
        own = 1 if isinstance(node.get("type"), list) or "anyOf" in node else 0
        return own + sum(_count_unions(v) for v in node.values())
    if isinstance(node, list):
        return sum(_count_unions(v) for v in node)
    return 0


def test_schema_stays_under_api_union_limit():
    # the API rejects structured-output schemas with more than 16 union-typed fields (found in the live check)
    assert _count_unions(cd.DRAFT_SCHEMA) <= cd.UNION_LIMIT


def test_unused_param_markers_mean_not_set():
    marked = {**{k: "" for k in NULL_PARAMS}, "max_loops": -1, "within_hours": 0, "event": "export_csv", "where_source_view": "claims"}
    item = run([spec(params=marked)])["items"][0]
    assert item["contract"]["expectations"][0]["params"] == {"event": "export_csv", "where": {"source_view": "claims"}}


def test_routes_need_admin_token_to_approve(tmp_path, monkeypatch):
    tmp_storage(tmp_path, monkeypatch)
    monkeypatch.setenv("ADMIN_TOKEN", "a")
    out = asyncio.run(cd.draft_contracts("INT-09", state=STATE, call=stub([spec()]), legacy_events=LEGACY))
    c = TestClient(__import__("server.app", fromlist=["app"]).app)
    did = out["items"][0]["draft_id"]
    assert c.post(f"/api/drafts/{did}/approve").status_code == 401
    assert c.post(f"/api/drafts/{did}/approve", headers={"X-Admin-Token": "a"}).json()["contract_id"] == "C-06"
