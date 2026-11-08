import json

from server.kb import build_brief, load_bank


def test_brief_is_deterministic():
    assert build_brief("INT-01", "billing_clerk_2") == build_brief("INT-01", "billing_clerk_2")


def test_brief_contains_rules_slots_and_bank():
    b = build_brief("INT-01", "billing_clerk_2")
    assert "PA-SCAN" in b and "RETRO-ELIG" in b and "C-01.current_practice" in b and "PQ-" in b


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
    order = ["INTERVIEWEE", "FALLBACK PLAN", "QUESTION BANK", "RULE CATALOGUE", "CONTRACT SLOTS", "DOC DIFFS", "LOG FACTS", "OPEN ITEMS"]
    idx = [b.index(f"## {name}") for name in order]
    assert idx == sorted(idx)


def test_brief_bank_is_filtered_by_role():
    b = build_brief("INT-03", "denial_specialist_1")
    bank = load_bank()
    clerk_only = [pid for pid, q in bank.items() if q["roles"] == ["billing_clerk"]]
    assert clerk_only and all(f'"{pid}"' not in b for pid in clerk_only)


def test_brief_has_no_contract_evidence_or_costs():
    b = build_brief("INT-01", "billing_clerk_2")
    assert '"cost_model"' not in b and '"evidence"' not in b and "see fax" not in b.lower()
