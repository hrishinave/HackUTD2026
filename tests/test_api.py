import base64
import json
import time

import pytest
from fastapi.testclient import TestClient
from server import routes_engine, tts
from server.app import app


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    # never call ElevenLabs from tests; keep state and live clips out of data/
    monkeypatch.setattr(tts, "render", lambda text: b"MP3:" + text.encode())
    monkeypatch.setattr(routes_engine, "STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(routes_engine, "LIVE_CLIPS_DIR", str(tmp_path / "live"))


def _receive_until(ws, pred, limit=10):
    for _ in range(limit):
        msg = ws.receive_json()
        if pred(msg):
            return msg
    raise AssertionError("expected message never arrived")


def test_client_ws_returns_fake_queue(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    c = TestClient(app)
    assert c.post("/api/interviews/TEST/start", json={"interviewee": "billing_clerk_2"}).json()["ok"] is True
    with c.websocket_connect("/ws/client/TEST") as ws:
        ws.send_json({"type": "hello", "device": "laptop-chrome", "app_version": "0.1"})
        first = ws.receive_json()  # the plan question is ready before anyone speaks
        assert first["type"] == "queue" and first["questions"]
        t0 = time.monotonic()
        ws.send_json({"type": "utterance", "text": "hello there", "final": True, "t_ms": 1000})
        msg = _receive_until(ws, lambda m: m["type"] == "queue" and m["based_on_t_ms"] == 1000)
        assert 0.9 <= time.monotonic() - t0 < 3.0  # after the 1 s debounce
        assert len(msg["questions"]) >= 1 and msg["questions"][0]["text"] == "Can you walk me through a normal claim?"


def test_played_is_acked_and_queue_refills(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    c = TestClient(app)
    c.post("/api/interviews/T2/start", json={"interviewee": "billing_clerk_2"})
    with c.websocket_connect("/ws/client/T2") as ws:
        q = ws.receive_json()["questions"][0]
        ws.send_json({"type": "played", "question_id": q["id"], "t_ms": 2000})
        assert _receive_until(ws, lambda m: m["type"] == "ack") == {"type": "ack", "of": "played", "question_id": q["id"]}
        refill = _receive_until(ws, lambda m: m["type"] == "queue")
        assert refill["questions"] and refill["questions"][0]["id"] != q["id"]
    state = c.get("/api/interviews/T2/state").json()
    assert [p["id"] for p in state["played"]] == [q["id"]]
    assert set(state) >= {"transcript", "queue", "played", "slot_fills", "contradictions", "rules_mentioned", "coverage", "yield"}


def test_start_unknown_interviewee_is_404_and_state_unknown_is_404():
    c = TestClient(app)
    assert c.post("/api/interviews/X/start", json={"interviewee": "nobody"}).status_code == 404
    assert c.get("/api/interviews/NOPE/state").status_code == 404


def test_contracts_route_lists_five():
    assert [k["id"] for k in TestClient(app).get("/api/contracts").json()] == ["C-01", "C-02", "C-03", "C-04", "C-05"]


def test_missing_page_is_clean_404():
    c = TestClient(app)
    r = c.get("/terms")
    assert r.status_code in (200, 404)


def test_new_questions_get_audio_and_state_is_saved_and_restored(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    c = TestClient(app)
    c.post("/api/interviews/T3/start", json={"interviewee": "billing_clerk_2"})
    with c.websocket_connect("/ws/client/T3") as ws:
        q = _receive_until(ws, lambda m: m["type"] == "queue")["questions"][0]
        audio = _receive_until(ws, lambda m: m["type"] == "audio")
        assert audio["question_id"] == q["id"]
        assert base64.b64decode(audio["mp3_b64"]) == b"MP3:Detail: " + q["text"].encode()
        ws.send_json({"type": "utterance", "text": "I do imaging claims", "final": True, "t_ms": 3000})
        _receive_until(ws, lambda m: m["type"] == "queue" and m["based_on_t_ms"] == 3000)
        ws.send_json({"type": "played", "question_id": q["id"], "t_ms": 4000})
        _receive_until(ws, lambda m: m["type"] == "ack")
    saved = json.loads((tmp_path / "state" / "T3.json").read_text())
    assert saved["transcript"][0]["text"] == "I do imaging claims" and saved["played"][0]["id"] == q["id"]
    before = c.get("/api/interviews/T3/state").json()
    routes_engine.sessions.pop("T3")
    routes_engine._startup_load_sessions()
    after = c.get("/api/interviews/T3/state").json()
    assert after["transcript"] == before["transcript"] and after["played"] == before["played"]
    assert after["queue"] == before["queue"]


def test_question_call_overlaps_debounce_but_queue_waits_for_silence(monkeypatch):
    from server import llm
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    calls = []
    real = llm.complete_questions
    async def spy(brief, user_input):
        calls.append(time.monotonic())
        return await real(brief, user_input)
    monkeypatch.setattr(llm, "complete_questions", spy)
    c = TestClient(app)
    c.post("/api/interviews/T4/start", json={"interviewee": "billing_clerk_2"})
    with c.websocket_connect("/ws/client/T4") as ws:
        _receive_until(ws, lambda m: m["type"] == "queue")
        calls.clear()
        t0 = time.monotonic()
        ws.send_json({"type": "utterance", "text": "first thought", "final": True, "t_ms": 1000})
        ws.send_json({"type": "utterance", "text": "and more", "final": True, "t_ms": 1300})
        msg = _receive_until(ws, lambda m: m["type"] == "queue" and m["based_on_t_ms"] >= 1000)
        waited = time.monotonic() - t0
    assert calls and calls[0] - t0 < 0.5            # call starts right away, not after the debounce
    assert msg["based_on_t_ms"] == 1300             # the queue reflects the latest sentence only
    assert waited >= 0.9                            # and is still held until 1 s of silence


def test_contracts_merge_live_evidence_with_lineage_and_validate(monkeypatch):
    from server.contracts import validate_contract
    from server.llm import BookResult
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    c = TestClient(app)
    c.post("/api/interviews/INT-01/start", json={"interviewee": "billing_clerk_2"})
    c.post("/api/interviews/LIVE9/start", json={"interviewee": "billing_clerk_2"})  # not INT-NN: ignored
    for iid in ("INT-01", "LIVE9"):
        s = routes_engine.sessions[iid].session
        q = s.apply_questions([{"source": "new", "bank_id": None, "cue": "Gap:", "text": "Where does the prior auth number go today?",
                                "target": "C-01.current_practice", "reason": "r"}], 60_000, 0)
        qid = next(x["id"] for x in q if x["text"] == "Where does the prior auth number go today?")
        s.mark_played(qid, 60_000)
        s.add_utterance("I put the number in the notes, or sometimes just see fax.", 61_500)
        s.begin_call()
        s.apply_bookkeeping(BookResult([{"contract_id": "C-01", "slot": "current_practice", "value": "notes",
                                         "quote": "I put the number in the notes, or sometimes just see fax.",
                                         "answered_question_id": qid}], [], []))
    contracts = c.get("/api/contracts").json()
    assert [k["id"] for k in contracts] == ["C-01", "C-02", "C-03", "C-04", "C-05"]
    for k in contracts:
        assert validate_contract(k) == [], (k["id"], validate_contract(k))
    c01 = contracts[0]
    live = [e for e in c01["evidence"] if e["interview_id"] == "INT-01"]
    assert live == [{"quote": "I put the number in the notes, or sometimes just see fax.", "speaker": "Billing clerk 2",
                     "interview_id": "INT-01", "timestamp": "01:01", "question_id": qid, "question_origin": "ai"}]
    assert all(e["interview_id"] != "LIVE9" for e in c01["evidence"])
    assert c01["confidence"]["said"] is True
    # contracts without live evidence keep the catalog's
    assert contracts[4]["evidence"] and all(e["interview_id"] != "INT-01" for e in contracts[4]["evidence"])
    routes_engine.sessions.pop("INT-01"); routes_engine.sessions.pop("LIVE9")


# --- v3: Haiku-written questions for any company, interview IDs ---

def test_start_for_new_company_uses_generic_brief_and_opening_questions(monkeypatch):
    from server import llm
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    seen = []
    real = llm.complete_questions
    async def spy(brief, user_input):
        seen.append((brief, user_input))
        return await real(brief, user_input)
    monkeypatch.setattr(llm, "complete_questions", spy)
    c = TestClient(app)
    r = c.post("/api/interviews/INT-41/start", json={"interviewee": "billing_clerk_2", "company_id": "acme_logistics",
                                                     "company_name": "Acme Logistics", "person_name": "Dana Lee",
                                                     "position": "Dispatcher"})
    assert r.status_code == 200
    body = r.json()
    assert body["company_id"] == "acme_logistics" and body["interviewee"] == "dana_lee" and body["opening"] == "ok"
    s = routes_engine.sessions["INT-41"].session
    assert "Acme Logistics" in s.brief and "Medicare" not in s.brief and s.bank == {}
    assert s.slot_ids == [] and s.plan[0] == "Walk me through a typical day as Dispatcher."
    # the opening call ran on an empty transcript and its question is queued as an AI question
    assert any("Nothing has been said yet" in u for _, u in seen)
    assert s.queue and s.queue[0]["origin"] == "ai" and s.queue[0]["bank_id"] is None
    with c.websocket_connect("/ws/client/INT-41") as ws:
        assert ws.receive_json()["type"] == "queue"
        ws.send_json({"type": "utterance", "text": "I route the trucks every morning", "final": True, "t_ms": 5000})
        msg = _receive_until(ws, lambda m: m["type"] == "queue" and m["based_on_t_ms"] == 5000)
        assert msg["questions"]
    state = c.get("/api/interviews/INT-41/state").json()
    assert state["company_id"] == "acme_logistics" and state["company_name"] == "Acme Logistics"
    assert state["person_name"] == "Dana Lee" and state["position"] == "Dispatcher" and state["coverage"] == 0.0
    # restored after a restart with the same generic brief
    brief = s.brief
    routes_engine.sessions.pop("INT-41")
    routes_engine._startup_load_sessions()
    assert routes_engine.sessions["INT-41"].session.brief == brief
    # other companies' sessions never feed the demo contracts
    assert all(e["interview_id"] != "INT-41" for k in c.get("/api/contracts").json() for e in k["evidence"])
    routes_engine.sessions.pop("INT-41")


def test_start_new_company_with_unknown_person_is_not_404(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "scripted")  # no questions: the fallback plan opens
    c = TestClient(app)
    r = c.post("/api/interviews/INT-42/start", json={"company_id": "zeta", "company_name": "Zeta", "person_name": "Nobody Known",
                                                     "position": "Warehouse lead"})
    assert r.status_code == 200 and r.json()["opening"] == "plan"
    q = routes_engine.sessions["INT-42"].session.queue
    assert q[0]["origin"] == "plan" and q[0]["text"] == "Walk me through a typical day as Warehouse lead."
    routes_engine.sessions.pop("INT-42")


def test_opening_failure_falls_back_to_plan(monkeypatch):
    from server import llm
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    async def boom(brief, user_input):
        raise TimeoutError("slow")
    monkeypatch.setattr(llm, "complete_questions", boom)
    c = TestClient(app)
    r = c.post("/api/interviews/INT-43/start", json={"company_id": "zeta", "person_name": "A", "position": "Driver"})
    assert r.status_code == 200 and r.json()["opening"].startswith("failed")
    assert routes_engine.sessions["INT-43"].session.queue[0]["origin"] == "plan"
    routes_engine.sessions.pop("INT-43")


def test_next_interview_id(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    saved = dict(routes_engine.sessions)
    routes_engine.sessions.clear()
    try:
        c = TestClient(app)
        assert c.get("/api/interviews/next-id").json() == {"interview_id": "INT-01"}
        state = tmp_path / "state"; state.mkdir(exist_ok=True)
        (state / "INT-07.json").write_text("{}")
        (state / "LIVE9.json").write_text("{}")
        assert c.get("/api/interviews/next-id").json() == {"interview_id": "INT-08"}
        c.post("/api/interviews/INT-99/start", json={"company_id": "zeta", "person_name": "A", "position": "B"})
        assert c.get("/api/interviews/next-id").json() == {"interview_id": "INT-100"}
        c.post("/api/interviews/INT-100/start", json={"company_id": "zeta", "person_name": "A", "position": "B"})
        assert c.get("/api/interviews/next-id").json() == {"interview_id": "INT-101"}
    finally:
        routes_engine.sessions.clear()
        routes_engine.sessions.update(saved)


def test_contract_merge_accepts_three_digit_interview_ids():
    assert routes_engine._INTERVIEW_ID.match("INT-01") and routes_engine._INTERVIEW_ID.match("INT-123")
    assert not routes_engine._INTERVIEW_ID.match("INT-1") and not routes_engine._INTERVIEW_ID.match("LIVE9")


def test_interview_options_include_saved_companies(monkeypatch, tmp_path):
    from server import routes_web
    state = tmp_path / "web_state"; state.mkdir()
    monkeypatch.setattr(routes_web, "STATE_DIR", state)
    for iid, cid, name, person in [("INT-05", "acme_logistics", "Acme Logistics", "Dana Lee"),
                                   ("INT-06", "acme_logistics", "Acme Logistics", "Sam Ortiz"),
                                   ("INT-07", "medicare_billing_demo", "Medicare Billing Office", "Billing clerk 2"),
                                   ("INT-08", "zeta", "Zeta Co", "Dana Lee")]:
        (state / f"{iid}.json").write_text(json.dumps({"interview_id": iid, "company_id": cid, "company_name": name,
                                                        "person_name": person, "position": "Dispatcher", "interviewee": "x"}))
    saved = dict(routes_engine.sessions)
    routes_engine.sessions.clear()
    try:
        companies = TestClient(app).get("/api/interview-options").json()["companies"]
    finally:
        routes_engine.sessions.update(saved)
    assert [c["id"] for c in companies] == ["medicare_billing_demo", "acme_logistics", "zeta"]
    assert companies[1]["name"] == "Acme Logistics" and [p["label"] for p in companies[1]["people"]] == ["Dana Lee", "Sam Ortiz"]
    assert companies[0]["people"] and companies[2]["name"] == "Zeta Co"
