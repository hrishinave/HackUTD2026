"""Engine routes: client WebSocket, interviews, contracts, settings, pages (except /claim)."""
import asyncio
import base64
import glob
import hashlib
import json
import logging
import copy
import os
import re
import time
from collections import deque

from fastapi import APIRouter, Body, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from server import kb, llm, tts
from server import contracts as ct
from server import settings as st
from server.contracts import validate_contract
from server.engine import InterviewSession
from server.kb import build_brief, load_bank

log = logging.getLogger("fitcheck.engine")

# uvicorn only configures its own loggers; give ours (fitcheck.engine, fitcheck.llm) a handler
# so warm-ups, cache numbers and played events show in the server log.
_root = logging.getLogger("fitcheck")
if not _root.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
    _root.addHandler(_h)
    _root.setLevel(logging.INFO)
    _root.propagate = False


def _startup_prune() -> None:
    try:
        st.prune_old_events()
    except Exception:  # never block startup on a bad events file
        log.exception("prune_old_events failed")


def _startup_load_sessions() -> None:
    for path in sorted(glob.glob(os.path.join(STATE_DIR, "*.json"))):
        try:
            with open(path) as f:
                d = json.load(f)
            if d["interview_id"] in sessions:  # startup hooks can fire twice; never replace a live session
                continue
            session =InterviewSession.from_dict(d, brief=build_brief(d["interview_id"], d["interviewee"]), bank=load_bank())
            runner = Runner(session)
            runner.total_calls = d.get("_calls_total", 0)
            sessions[session.interview_id] = runner
            log.info("restored %s (%d utterances, %d played)", session.interview_id, len(session.transcript), len(session.played))
        except Exception:
            log.exception("could not restore %s", path)


router = APIRouter(on_startup=[_startup_prune, _startup_load_sessions])


@router.get("/api/settings")
def get_settings():
    return {**st.load_settings(), "audit": st.recent_audit(20)}


@router.post("/api/settings")
def post_settings(body: dict = Body(...), x_admin_token: str | None = Header(default=None)):
    expected = os.environ.get("ADMIN_TOKEN")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="admin token required")
    try:
        return st.save_settings(body, actor=st.load_settings()["admin"])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

STATIC_DIR = "server/static"
CONTRACTS_PATH = "contracts/medicare_contracts.json"
STATE_DIR = "data/state"
LIVE_CLIPS_DIR = "data/clips/live"

CALLS_PER_MINUTE = 30
CALLS_PER_INTERVIEW = 800
BOOK_RESERVE_PER_MINUTE = 10    # bookkeeping stops this far below the per-minute cap
BOOK_RESERVE_TOTAL = 60         # ... and this far below the per-interview cap
TICK_S = 0.1
DEBOUNCE_MS = 1000


class Runner:
    """Timing, sockets and in-flight LLM calls for one InterviewSession."""

    def __init__(self, session: InterviewSession):
        self.session = session
        self.sockets: set[WebSocket] = set()
        self.loop_task: asyncio.Task | None = None
        self.q_task: asyncio.Task | None = None
        self.book_task: asyncio.Task | None = None
        self.call_times: deque[float] = deque()
        self.total_calls = 0
        self.skipped_book = 0
        self.q_based_on = -1
        self.audio: dict[str, str] = {}      # question_id -> mp3 base64, for questions without a bank clip
        self.voicing: set[str] = set()
        # interview clock: t_ms of the latest utterance and the monotonic time it arrived
        self.clock_t_ms = 0
        self.clock_mono = time.monotonic()

    def now_ms(self) -> int:
        return self.clock_t_ms + int((time.monotonic() - self.clock_mono) * 1000)

    def sync_clock(self, t_ms: int) -> None:
        if t_ms >= self.clock_t_ms:
            self.clock_t_ms, self.clock_mono = t_ms, time.monotonic()

    def _recent_calls(self) -> int:
        cutoff = time.monotonic() - 60
        while self.call_times and self.call_times[0] < cutoff:
            self.call_times.popleft()
        return len(self.call_times)

    def _count_call(self) -> None:
        self.call_times.append(time.monotonic())
        self.total_calls += 1

    def can_question(self) -> bool:
        # Question calls are never skipped for bookkeeping's sake; they stop only at the hard caps.
        return self._recent_calls() < CALLS_PER_MINUTE and self.total_calls < CALLS_PER_INTERVIEW

    def can_book(self) -> bool:
        return (self._recent_calls() < CALLS_PER_MINUTE - BOOK_RESERVE_PER_MINUTE
                and self.total_calls < CALLS_PER_INTERVIEW - BOOK_RESERVE_TOTAL)

    async def broadcast(self, msg: dict) -> None:
        for ws in list(self.sockets):
            try:
                await ws.send_json(msg)
            except Exception:
                self.sockets.discard(ws)

    async def send_queue(self) -> None:
        self.save()
        await self.broadcast(self.session.queue_message())
        for q in self.session.queue:
            if q.get("audio_url") is None and q["id"] not in self.audio and q["id"] not in self.voicing:
                self.voicing.add(q["id"])
                asyncio.create_task(self._voice(q))

    async def _voice(self, q: dict) -> None:
        """ElevenLabs render for a question with no bank clip; cached on disk by text so rehearsals don't re-spend."""
        try:
            text = f"{q['cue']} {q['text']}"
            path = os.path.join(LIVE_CLIPS_DIR, hashlib.sha1(text.encode()).hexdigest()[:16] + ".mp3")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    mp3 = f.read()
            else:
                mp3 = await asyncio.to_thread(tts.render, text)
                if mp3:
                    os.makedirs(LIVE_CLIPS_DIR, exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(mp3)
            if mp3:
                self.audio[q["id"]] = base64.b64encode(mp3).decode()
                await self.broadcast(self.audio_message(q["id"]))
        except Exception as e:  # the page falls back to the browser voice
            log.warning("%s voicing %s failed (%s)", self.session.interview_id, q.get("id"), e)
        finally:
            self.voicing.discard(q["id"])

    def audio_message(self, question_id: str) -> dict:
        return {"type": "audio", "question_id": question_id, "mp3_b64": self.audio[question_id]}

    def save(self) -> None:
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            path = os.path.join(STATE_DIR, f"{self.session.interview_id}.json")
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump({**self.session.to_dict(), "_calls_total": self.total_calls}, f)
            os.replace(tmp, path)
        except Exception:
            log.exception("%s could not save state", self.session.interview_id)

    def ensure_loop(self) -> None:
        if self.loop_task is None or self.loop_task.done():
            self.loop_task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        try:
            while self.sockets:
                now = self.now_ms()
                if self.session.due_for_call(now):
                    self._trigger()
                # wake exactly when the debounce expires instead of up to TICK_S late
                pending = self.session.last_utterance_t > self.session.last_called_t
                wait_ms = self.session.last_utterance_t + DEBOUNCE_MS - now if pending else TICK_S * 1000
                await asyncio.sleep(max(0.005, min(TICK_S, wait_ms / 1000)))
        except asyncio.CancelledError:
            pass

    def on_utterance(self) -> None:
        """Start the question call as soon as a final sentence arrives; _questions holds the result
        until the 1 s debounce has passed, so the call's latency overlaps the wait."""
        self.start_question_call()
        self.ensure_loop()

    def start_question_call(self) -> None:
        user_input, based_on = self.session.build_input()
        if not self.can_question():
            log.warning("%s question call capped (%s total)", self.session.interview_id, self.total_calls)
            return
        if self.q_task and not self.q_task.done():
            self.q_task.cancel()  # a newer sentence supersedes the call in flight
        self._count_call()
        self.q_based_on = based_on
        self.q_task = asyncio.create_task(self._questions(user_input, based_on))

    def _trigger(self) -> None:
        """Debounce expired: bookkeeping starts now; the question call started on the utterance."""
        user_input, based_on = self.session.begin_call()
        if self.q_based_on != based_on:  # no early call covered this sentence (e.g. it was capped)
            self.start_question_call()
        if self.book_task is None or self.book_task.done():
            if self.can_book():
                self._count_call()
                self.book_task = asyncio.create_task(self._bookkeeping(user_input))
            else:
                self.skipped_book += 1

    async def _questions(self, user_input: str, based_on: int) -> None:
        try:
            try:
                items = await llm.complete_questions(self.session.brief, user_input)
            except llm.LLMRefused:
                log.warning("%s question call refused; keeping queue", self.session.interview_id)
                items = []
            except asyncio.CancelledError:
                raise
            except Exception as e:  # timeout, API error, bad JSON: keep the old queue
                log.warning("%s question call failed (%s: %s); keeping queue", self.session.interview_id, type(e).__name__, e)
                items = []
            hold_ms = based_on + DEBOUNCE_MS - self.now_ms()
            if hold_ms > 0:  # never show a queue before 1 s of silence
                await asyncio.sleep(hold_ms / 1000)
        except asyncio.CancelledError:
            return
        if self.session.last_utterance_t > based_on:
            return  # a newer sentence arrived; its own call will deliver
        before = self.session.queue_message()
        self.session.apply_questions(items, self.now_ms(), based_on)
        after = self.session.queue_message()
        if items or after != before:
            await self.send_queue()
        else:
            self.save()

    async def _bookkeeping(self, user_input: str) -> None:
        try:
            result = await llm.complete_bookkeeping(self.session.brief, user_input)
        except asyncio.CancelledError:
            return
        except Exception as e:
            log.warning("%s bookkeeping failed (%s: %s)", self.session.interview_id, type(e).__name__, e)
            return
        self.session.apply_bookkeeping(result)
        self.save()

    async def refill_if_empty(self) -> None:
        if not self.session.queue:
            self.session.apply_questions([], self.now_ms(), self.session.based_on_t_ms)
            if self.session.queue:
                await self.send_queue()
                return
        self.save()

    def stop(self) -> None:
        for t in (self.loop_task, self.q_task, self.book_task):
            if t and not t.done():
                t.cancel()


# interview_id -> Runner (holds the InterviewSession)
sessions: dict[str, Runner] = {}


def _create_session(interview_id: str, interviewee: str) -> Runner:
    """Build the brief and session. KeyError if the interviewee is unknown."""
    brief = build_brief(interview_id, interviewee)
    plan = kb.load_people()[interviewee]["plan"]
    session = InterviewSession(interview_id, interviewee, brief=brief, bank=load_bank(), plan=plan)
    session.apply_questions([], 0, 0)  # never empty: first plan question is ready before any speech
    old = sessions.get(interview_id)
    runner = Runner(session)
    if old:
        old.stop()
        runner.sockets = old.sockets
    sessions[interview_id] = runner
    return runner


def _default_interviewee(interview_id: str) -> str:
    people = kb.load_people()
    for key in sorted(people):
        if people[key].get("interview_id") == interview_id:
            return key
    return "billing_clerk_2"


@router.post("/api/interviews/{interview_id}/start")
async def start_interview(interview_id: str, body: dict = Body(default={})):
    interviewee = body.get("interviewee") or _default_interviewee(interview_id)
    try:
        runner = _create_session(interview_id, interviewee)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown interviewee: {interviewee}")
    person_name = str(body.get("person_name", "")).strip()
    position = str(body.get("position", "")).strip()
    if person_name:
        runner.session.person_name = person_name
        runner.session.label = person_name
    if position:
        runner.session.position = position
    runner.session.company_id = str(body.get("company_id", "medicare_billing_demo"))
    warm = "ok"
    try:
        await llm.warm_up(runner.session.brief)
        runner.total_calls += 2
    except Exception as e:  # the interview still runs; the first real call just pays the cache write
        warm = f"failed: {type(e).__name__}"
        log.warning("%s warm-up failed: %s", interview_id, e)
    if runner.sockets:
        runner.ensure_loop()
    await runner.send_queue()
    log.info("%s started for %s (brief ~%d tokens, warm-up %s)", interview_id, interviewee, len(runner.session.brief) // 4, warm)
    return {"ok": True, "interview_id": interview_id, "interviewee": interviewee, "warm_up": warm}


@router.get("/api/interviews/{interview_id}/state")
def interview_state(interview_id: str):
    runner = sessions.get(interview_id)
    if not runner:
        raise HTTPException(status_code=404, detail="interview not started")
    return {**runner.session.state(),
            "calls": {"total": runner.total_calls, "last_minute": runner._recent_calls(),
                      "bookkeeping_skipped": runner.skipped_book}}


_INTERVIEW_ID = re.compile(r"^INT-\d{2}$")


@router.get("/api/contracts")
def get_contracts():
    """Catalog contracts with live interview evidence merged in.

    Live slot fills become evidence[] items (quote, speaker, interview, mm:ss, Q-N lineage). For an
    interview that has live evidence, it replaces that interview's catalog quotes; other quotes stay.
    Sessions whose ID isn't INT-NN (rehearsal/test runs) are left out so every contract stays schema-valid.
    """
    contracts = copy.deepcopy(ct.load_all_contracts())
    live_sessions = [r.session for iid, r in sorted(sessions.items()) if _INTERVIEW_ID.match(iid)]
    for contract in contracts:
        live = [e for s in live_sessions for e in s.evidence(contract["id"])]
        if not live:
            continue
        live_ids = {e["interview_id"] for e in live}
        kept = [e for e in contract.get("evidence", []) if e["interview_id"] not in live_ids]
        contract["evidence"] = kept + live
        contract["confidence"]["said"] = True
    for contract in contracts:
        errors = validate_contract(contract)
        if errors:
            log.warning("contract %s fails the schema after merge: %s", contract["id"], errors[:3])
    return contracts


@router.websocket("/ws/client/{interview_id}")
async def client_ws(ws: WebSocket, interview_id: str):
    await ws.accept()
    runner = sessions.get(interview_id)
    if runner is None:
        interviewee = _default_interviewee(interview_id)
        log.warning("%s socket opened before /start; starting for %s without warm-up", interview_id, interviewee)
        runner = _create_session(interview_id, interviewee)
    runner.sockets.add(ws)
    runner.ensure_loop()
    try:
        if runner.session.queue:
            await ws.send_json(runner.session.queue_message())
            for q in runner.session.queue:
                if q["id"] in runner.audio:
                    await ws.send_json(runner.audio_message(q["id"]))
        while True:
            msg = await ws.receive_json()
            runner = sessions.get(interview_id, runner)  # a /start may have replaced it
            runner.sockets.add(ws)
            runner.ensure_loop()
            kind = msg.get("type")
            if kind == "utterance":
                if msg.get("final", True):
                    t_ms = int(msg.get("t_ms", 0))
                    runner.sync_clock(t_ms)
                    text = str(msg.get("text", ""))
                    if text.strip():
                        runner.session.add_utterance(text, t_ms)
                        runner.on_utterance()
            elif kind == "played":
                qid = str(msg.get("question_id", ""))
                runner.session.mark_played(qid, int(msg.get("t_ms", runner.now_ms())))
                log.info("played %s %s", interview_id, qid)
                await ws.send_json({"type": "ack", "of": "played", "question_id": qid})
                await runner.refill_if_empty()
            elif kind == "metric":
                log.info("metric %s %s=%s", interview_id, msg.get("name"), msg.get("value"))
            elif kind in ("hello", "tap"):
                log.info("%s %s %s", interview_id, kind, {k: v for k, v in msg.items() if k != "type"})
    except WebSocketDisconnect:
        pass
    finally:
        r = sessions.get(interview_id)
        if r:
            r.sockets.discard(ws)
            if not r.sockets:
                r.stop()


def _page(name: str) -> FileResponse:
    path = os.path.join(STATIC_DIR, f"{name}.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"{name}.html not built yet")
    return FileResponse(path)


@router.get("/board")
def page_board():
    return _page("board")


@router.get("/terms")
def page_terms():
    return _page("terms")


@router.get("/privacy")
def page_privacy():
    return _page("privacy")
