from server.simulate import generate, DEFAULT_SCENARIO


def test_deterministic():
    assert generate(7, DEFAULT_SCENARIO) == generate(7, DEFAULT_SCENARIO)


def test_events_use_catalog_envelope_and_no_text():
    _, post = generate(7, DEFAULT_SCENARIO)
    for e in post[:200]:
        assert set(e) == {"event", "ts", "role", "actor_hash", "session_id", "claim_id_hash", "props", "week"}
        assert "notes" not in e["props"]


def test_c01_planted_drift_present():
    _, post = generate(7, DEFAULT_SCENARIO)
    wk = lambda w: [e for e in post if e["event"] == "claim_submitted" and e["props"]["requires_prior_auth"] and e["week"] == w]
    rate = lambda w: sum(e["props"]["prior_auth_number_filled"] for e in wk(w)) / len(wk(w))
    assert rate(2) > 0.9 and rate(8) < 0.6   # week 8 planted at 0.50: far enough from 0.6 that sampling noise can't fail it


def test_claims_exports_do_not_change_existing_c01_rates():
    _, post = generate(7, DEFAULT_SCENARIO)
    wk = lambda w: [e for e in post if e["event"] == "claim_submitted" and e["props"]["requires_prior_auth"] and e["week"] == w]
    rate = lambda w: sum(e["props"]["prior_auth_number_filled"] for e in wk(w)) / len(wk(w))
    assert rate(2) > 0.9 and rate(8) < 0.6


def test_role_sizes_meet_privacy_floor():
    _, post = generate(7, DEFAULT_SCENARIO)
    clerks = {e["actor_hash"] for e in post if e["role"] == "billing_clerk"}
    specialists = {e["actor_hash"] for e in post if e["role"] == "denial_specialist"}
    assert len(clerks) == 8 and len(specialists) == 5
