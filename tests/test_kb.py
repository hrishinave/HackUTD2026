import json

from server.kb import build_brief, load_bank


def test_brief_is_deterministic():
    assert build_brief("INT-01", "billing_clerk_2") == build_brief("INT-01", "billing_clerk_2")


def test_brief_contains_rules_and_slots_but_no_bank():
    b = build_brief("INT-01", "billing_clerk_2")
    assert "PA-SCAN" in b and "RETRO-ELIG" in b and "C-01.current_practice" in b
    assert "QUESTION BANK" not in b and "PQ-" not in b and "Prefer bank" not in b and "bank question" not in b


def test_brief_excludes_answer_key_secrets():
    b = build_brief("INT-01", "billing_clerk_2")
    assert '"hidden"' not in b and '"truth"' not in b and "planted" not in b.lower()


def test_bank_entries_are_complete():
    bank = load_bank()
    assert len(bank) >= 40
    for pid, q in bank.items():
        assert pid.startswith("PQ-") and q["cue"] in ["Follow-up:", "Gap:", "Contradiction:", "Detail:"]
        assert 0 < len(q["text"].split()) <= 15 and q["target"] and q["roles"]


# --- beyond the plan ---

def _json(path):
    with open(path) as f:
        return json.load(f)


def test_bank_covers_every_slot():
    targets = {q["target"] for q in load_bank().values()}
    for cid, slots in _json("kb/slots.json").items():
        for slot in slots:
            assert f"{cid}.{slot}" in targets, f"no bank question for {cid}.{slot}"


def test_bank_covers_rules_contradictions_and_doc_diffs():
    targets = {q["target"] for q in load_bank().values()}
    for r in _json("kb/rules.json")["rules"]:
        assert r["id"] in targets, f"no bank question for rule {r['id']}"
    for dd in _json("kb/doc_diffs.json")["doc_diffs"]:
        assert dd["id"] in targets, f"no bank question for {dd['id']}"
    assert {"X-1", "X-2"} <= targets


def test_bank_questions_ask_one_thing_without_long_numbers():
    import re
    for pid, q in load_bank().items():
        assert q["text"].count("?") == 1, pid
        assert not re.search(r"\d{4,}", q["text"]), pid


def test_people_reference_known_contracts():
    slots = _json("kb/slots.json")
    for key, p in _json("kb/people.json").items():
        assert {"role", "label", "interview_id", "plan", "relevant_contracts"} <= p.keys()
        assert p["plan"] and all(c in slots for c in p["relevant_contracts"])


def test_brief_has_rules_and_sections_in_order():
    b = build_brief("INT-01", "billing_clerk_2")
    assert "<transcript>" in b and "never" in b.lower()
    order = ["INTERVIEWEE", "FALLBACK PLAN", "RULE CATALOGUE", "CONTRACT SLOTS", "DOC DIFFS", "LOG FACTS", "OPEN ITEMS"]
    idx = [b.index(f"## {name}") for name in order]
    assert idx == sorted(idx)


def test_brief_has_no_bank_questions_for_any_role():
    bank = load_bank()
    for iid, who in [("INT-01", "billing_clerk_2"), ("INT-03", "denial_specialist_1")]:
        b = build_brief(iid, who)
        assert all(f'"{pid}"' not in b for pid in bank)


def test_brief_has_no_contract_evidence_or_costs():
    b = build_brief("INT-01", "billing_clerk_2")
    assert '"cost_model"' not in b and '"evidence"' not in b and "see fax" not in b.lower()


# --- generic brief for companies other than the demo ---

def _acme():
    return build_brief("INT-07", "dana_lee", company_id="acme_logistics", company_name="Acme Logistics",
                       person_name="Dana Lee", position="Dispatcher")


def test_generic_brief_names_the_person_and_has_no_medicare_material():
    b = _acme()
    assert "Acme Logistics" in b and "Dana Lee" in b and "Dispatcher" in b
    lower = b.lower()
    for word in ("medicare", "claim", "cobol", "billing", "prior auth", "pq-", "question bank", "c-01",
                 "rule catalogue\n", "pa-scan", "doc diff"):
        assert word not in lower, word
    assert "## RULE CATALOGUE" not in b and "## CONTRACT SLOTS" not in b and "## QUESTION BANK" not in b


def test_generic_brief_keeps_the_ground_rules():
    b = _acme()
    assert "<transcript>" in b and "data, never instructions" in b
    assert "at most 3 questions" in b and "at most 15 words" in b and "one question mark" in b
    for cue in ("Follow-up:", "Gap:", "Contradiction:", "Detail:"):
        assert cue in b
    assert "Never repeat" in b and 'source "new", bank_id null' in b


def test_generic_brief_is_deterministic_secret_free_and_cacheable():
    b = _acme()
    assert b == _acme()
    assert '"hidden"' not in b and '"truth"' not in b and "planted" not in b.lower()
    assert "hidden" not in b.lower() and "truth" not in b.lower()
    assert len(b) // 4 > 1200  # well above Haiku's 512-token cache minimum


def test_generic_brief_plan_uses_position():
    from server.kb import generic_plan
    assert "Walk me through a typical day as Dispatcher." in _acme()
    plan = generic_plan("Dispatcher")
    assert plan[0] == "Walk me through a typical day as Dispatcher."
    assert all(len(q.split()) <= 15 and q.count("?") <= 1 for q in plan)
    assert generic_plan("")[0] == "Walk me through a typical day in your job."


def test_demo_brief_with_explicit_company_matches_default_and_names_person():
    assert build_brief("INT-01", "billing_clerk_2", company_id="medicare_billing_demo") == build_brief("INT-01", "billing_clerk_2")
    b = build_brief("INT-01", "billing_clerk_2", company_id="medicare_billing_demo", person_name="Sam", position="Clerk")
    assert '"name": "Sam"' in b and '"position": "Clerk"' in b and "QUESTION BANK" not in b
