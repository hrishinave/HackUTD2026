from server.feedback import build_payload, validate_payload

F = {"id": "F-01", "contract_id": "C-01", "status": "broken", "first_breach_week": 4, "type": "app_gap",
     "cost_usd_per_week": 15120, "explanation": "x", "requirement_statement": "Prior-auth number in its own field",
     "lineage": {"quote": "q", "interview_id": "INT-01", "timestamp": "14:32", "question_id": "Q-12"}}


def test_payload_matches_documented_shape():
    p = build_payload(F)
    assert set(p) == {"end_user_email", "content"} and validate_payload(p) == []
    assert "Simulated" in p["content"] and "Q-12" in p["content"]


def test_stub_rejects_extra_fields_and_blank_content():
    assert validate_payload({"end_user_email": "a@b.c", "content": "x", "title": "no"}) != []
    assert validate_payload({"end_user_email": "a@b.c", "content": "   "}) != []


def test_content_under_limit():
    assert len(build_payload(F)["content"]) <= 20000


# Extra checks beyond the plan's tests

def test_payload_from_real_finding_is_valid():
    from server.drift import findings
    from server.simulate import generate, DEFAULT_SCENARIO
    from server.contracts import load_catalog
    cat = load_catalog("contracts/medicare_contracts.json")
    _, post = generate(7, DEFAULT_SCENARIO)
    f = findings(cat["contracts"], post, {"drift_enabled": True, "contracts_watched": ["C-01"], "notes_matching": True})[0]
    p = build_payload(f)
    assert validate_payload(p) == []
    assert p["end_user_email"] == "usage-drift@pact.invalid"
    assert p["content"].rstrip().endswith("Simulated data.")
    assert "R-01" in p["content"] and "week 4" in p["content"]


def test_attachments_need_all_fields():
    ok = {"end_user_email": "a@b.c", "content": "x",
          "attachments": [{"file_name": "chart.png", "file_key": "k1", "file_size": 1200, "mime_type": "image/png"}]}
    assert validate_payload(ok) == []
    bad = {**ok, "attachments": [{"file_name": "chart.png"}]}
    assert validate_payload(bad) != []


def test_missing_email_rejected():
    assert validate_payload({"content": "x"}) != []
