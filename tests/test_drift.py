from server.drift import weekly_metrics, evaluate, findings
from server.simulate import generate, DEFAULT_SCENARIO
from server.contracts import load_catalog

CAT = load_catalog("contracts/medicare_contracts.json")
C = {c["id"]: c for c in CAT["contracts"]}
_, POST = generate(7, DEFAULT_SCENARIO)
ON = {"drift_enabled": True, "contracts_watched": list(C), "notes_matching": True}


def test_c01_is_broken_from_week_4():
    r = evaluate(C["C-01"], weekly_metrics(C["C-01"], POST, ON))
    assert r["status"] == "broken" and r["first_breach_week"] == 4


def test_learning_weeks_never_breach():
    wk = weekly_metrics(C["C-01"], POST, ON)
    assert all(w["state"] == "learning" for w in wk if w["week"] <= 2)


def test_c02_decoy_single_bad_week_not_drift():
    wk = weekly_metrics(C["C-02"], POST, ON)
    assert [w["state"] for w in wk if w["week"] == 5] == ["breach"]
    assert evaluate(C["C-02"], wk)["status"] == "holding"


def test_holding_contracts_hold():
    for cid in ["C-03", "C-04", "C-05"]:
        assert evaluate(C[cid], weekly_metrics(C[cid], POST, ON))["status"] == "holding"


def test_privacy_floor_suppresses_small_groups():
    three = sorted({x["actor_hash"] for x in POST if x["role"] == "billing_clerk"})[:3]
    few = [e for e in POST if e["actor_hash"] in three]
    assert all(w["state"] == "suppressed" for w in weekly_metrics(C["C-01"], few, ON))


def test_notes_matching_off_skips_detector_expectation():
    wk = weekly_metrics(C["C-01"], POST, {**ON, "notes_matching": False})
    assert all(w["values"].get("pa_in_notes_rate") is None for w in wk)


def test_finding_has_type_cost_lineage():
    f = [x for x in findings(CAT["contracts"], POST, ON) if x["contract_id"] == "C-01"][0]
    assert f["type"] == "app_gap" and f["cost_usd_per_week"] > 0 and f["lineage"]["question_id"] == "Q-12"


def test_no_findings_when_drift_off():
    assert findings(CAT["contracts"], POST, {**ON, "drift_enabled": False}) == []


# Extra checks beyond the plan's tests

def test_only_c01_drifts_with_default_scenario():
    assert [f["contract_id"] for f in findings(CAT["contracts"], POST, ON)] == ["C-01"]


def test_unwatched_contracts_are_skipped():
    assert findings(CAT["contracts"], POST, {**ON, "contracts_watched": ["C-02"]}) == []


def test_suppressed_weeks_hide_values():
    three = sorted({x["actor_hash"] for x in POST if x["role"] == "billing_clerk"})[:3]
    few = [e for e in POST if e["actor_hash"] in three]
    assert all(v is None for w in weekly_metrics(C["C-01"], few, ON) for v in w["values"].values())


def test_finding_shape_for_feedback_payload():
    f = findings(CAT["contracts"], POST, ON)[0]
    for key in ["id", "contract_id", "metric_id", "status", "weekly", "first_breach_week", "early_warning", "severity",
                "cost_usd_per_week", "type", "type_reason", "related_signals", "lineage", "explanation", "requirement_statement"]:
        assert key in f
    assert f["id"] == "F-01" and f["status"] == "broken"
