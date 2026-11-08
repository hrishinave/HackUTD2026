import asyncio

from server.engine import InterviewSession
from server.llm import BookResult

BANK = {"PQ-07": {"cue": "Gap:", "text": "Where does the prior auth number go today?", "target": "C-01.current_practice", "roles": ["billing_clerk"]}}
def make(plan=None): return InterviewSession("INT-01", "billing_clerk_2", brief="BRIEF", bank=BANK, plan=plan)
def new(text, target, cue="Detail:"): return {"source": "new", "bank_id": None, "cue": cue, "text": text, "target": target, "reason": "r"}

def test_debounce_waits_1000ms_and_resets_after_call():
    s = make(); s.add_utterance("I put it in the notes", 10_000)
    assert not s.due_for_call(10_500) and s.due_for_call(11_100)
    s.begin_call()
    assert not s.due_for_call(20_000)

def test_ids_assigned_and_queue_capped_at_3():
    s = make()
    q = s.apply_questions([new(f"Question {i}?", "C-01.frequency") for i in range(5)], 12_000, 10_000)
    assert [x["id"] for x in q] == ["Q-1", "Q-2", "Q-3"]

def test_bank_pick_resolves_text_and_clip():
    s = make()
    q = s.apply_questions([{"source": "bank", "bank_id": "PQ-07", "cue": "Gap:", "text": "", "target": "C-01.current_practice", "reason": "r"}], 1, 0)
    assert q[0]["text"] == BANK["PQ-07"]["text"] and q[0]["audio_url"] == "/clips/PQ-07.mp3" and q[0]["bank_id"] == "PQ-07"

def test_critic_drops_filled_long_and_digit_questions():
    s = make()
    s.apply_bookkeeping(BookResult([{"contract_id": "C-01", "slot": "frequency", "value": "most", "quote": "most of them", "answered_question_id": None}], [], []))
    q = s.apply_questions([
        new("How often does that happen?", "C-01.frequency"),
        new(" ".join(["word"] * 20) + "?", "C-01.exceptions"),
        new("Is patient 48213 covered?", "C-04.trigger"),
        new("What about coverage changes?", "C-04.trigger", cue="Gap:")], 2, 0)
    assert [x["text"] for x in q] == ["What about coverage changes?"]

def test_lineage_records_answered_question_and_yield():
    s = make()
    q = s.apply_questions([new("Where does the auth number go?", "C-01.current_practice", cue="Gap:")], 1, 0)
    s.mark_played(q[0]["id"], 5)
    s.apply_bookkeeping(BookResult([{"contract_id": "C-01", "slot": "current_practice", "value": "notes", "quote": "in the notes", "answered_question_id": q[0]["id"]}], [], []))
    fill = s.state()["slot_fills"]["C-01.current_practice"]
    assert fill["question_id"] == "Q-1" and fill["question_origin"] == "ai"
    assert s.state()["yield"] == 1.0

def test_queue_never_empty_falls_back_to_plan():
    s = make(plan=["Walk me through a claim that needs prior auth."])
    q = s.apply_questions([], 1, 0)
    assert q and q[0]["cue"] == "Detail:" and q[0]["origin"] == "plan"

def test_build_input_has_transcript_markers_and_status():
    s = make(); s.add_utterance("I put it in the notes", 61_000)
    q = s.apply_questions([new("Why the notes?", "C-01.current_practice")], 62_000, 61_000)
    s.mark_played(q[0]["id"], 62_500)
    text, based_on = s.begin_call()
    assert "<transcript>" in text and "I put it in the notes" in text
    assert "[Q-1 played at 01:02]" in text and "C-01.current_practice: open" in text and based_on == 61_000

def test_queue_message_carries_freshness():
    s = make(); s.apply_questions([new("Why the notes?", "C-01.current_practice")], 5_000, 4_000)
    m = s.queue_message()
    assert m["type"] == "queue" and m["based_on_t_ms"] == 4_000 and m["questions"][0]["id"] == "Q-1"


# --- beyond the plan ---

def test_state_has_frozen_keys_and_coverage():
    s = make()
    s.apply_bookkeeping(BookResult([{"contract_id": "C-01", "slot": "frequency", "value": "most", "quote": "q", "answered_question_id": None}], [], ["PA-SCAN"]))
    st = s.state()
    assert set(st) >= {"transcript", "queue", "played", "slot_fills", "contradictions", "rules_mentioned", "coverage", "yield"}
    assert st["rules_mentioned"] == ["PA-SCAN"]
    assert st["slot_fills"]["C-01.frequency"]["question_origin"] == "unprompted"
    assert 0 < st["coverage"] < 1

def test_interviewer_origin_for_plan_answers_and_unknown_bank_dropped():
    s = make(plan=["Walk me through a claim that needs prior auth."])
    q = s.apply_questions([{"source": "bank", "bank_id": "PQ-99", "cue": "Gap:", "text": "", "target": "x", "reason": "r"}], 1, 0)
    assert q[0]["origin"] == "plan"
    s.mark_played(q[0]["id"], 2)
    s.apply_bookkeeping(BookResult([{"contract_id": "C-01", "slot": "population", "value": "v", "quote": "q", "answered_question_id": q[0]["id"]}], [], []))
    assert s.state()["slot_fills"]["C-01.population"]["question_origin"] == "interviewer"

def test_two_question_marks_and_replayed_text_dropped():
    s = make()
    q = s.apply_questions([new("Why the notes?", "C-01.current_practice")], 1, 0)
    s.mark_played(q[0]["id"], 2)
    q = s.apply_questions([new("Why the notes?", "C-01.exceptions"), new("Is it fast? Or slow?", "C-01.exceptions"), new("What changes it?", "C-01.exceptions")], 3, 0)
    assert [x["text"] for x in q] == ["What changes it?"]

def test_fake_provider(monkeypatch):
    from server import llm
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    qs = asyncio.run(llm.complete_questions("B", "<transcript>\n</transcript>"))
    book = asyncio.run(llm.complete_bookkeeping("B", "x"))
    assert qs and qs[0]["source"] == "new" and isinstance(book, BookResult)
    asyncio.run(llm.warm_up("B"))

def test_scripted_provider_returns_no_questions(monkeypatch):
    from server import llm
    monkeypatch.setenv("LLM_PROVIDER", "scripted")
    assert asyncio.run(llm.complete_questions("B", "x")) == []

def test_slot_given_with_contract_prefix_is_normalised():
    s = make()
    s.apply_bookkeeping(BookResult([{"contract_id": "C-01", "slot": "C-01.frequency", "value": "most", "quote": "q", "answered_question_id": None}], [], []))
    assert "C-01.frequency" in s.state()["slot_fills"] and s.state()["coverage"] > 0
    q = s.apply_questions([new("How often does that happen?", "C-01.frequency")], 1, 0)
    assert all(x["target"] != "C-01.frequency" for x in q)

def test_same_rule_contradiction_recorded_once():
    s = make()
    c1 = {"kind": "person_vs_code", "statement_a": "notes or fax", "statement_b": "code reads notes", "rule_id": "PA-SCAN"}
    c2 = {"kind": "person_vs_code", "statement_a": "I put it in the notes", "statement_b": "PA-SCAN reads notes", "rule_id": "PA-SCAN"}
    s.apply_bookkeeping(BookResult([], [c1], [])); s.apply_bookkeeping(BookResult([], [c2], []))
    assert len(s.state()["contradictions"]) == 1
