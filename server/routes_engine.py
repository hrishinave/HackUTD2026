"""Engine routes: client WebSocket, interviews, contracts, settings, pages (except /claim)."""
import asyncio
import base64
import glob
import hashlib
import json
import logging
import os
import time
from collections import deque

from fastapi import APIRouter, Body, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from server import kb, llm, tts
from server import settings as st
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
            session = InterviewSession.from_dict(d, brief=build_brief(d["interview_id"], d["interviewee"]), bank=load_bank())
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
                if self.session.due_for_call(self.now_ms()):
                    self._trigger()
                await asyncio.sleep(TICK_S)
        except asyncio.CancelledError:
            pass

    def _trigger(self) -> None:
        user_input, based_on = self.session.begin_call()
        if self.can_question():
            if self.q_task and not self.q_task.done():
                self.q_task.cancel()
            self._count_call()
            self.q_task = asyncio.create_task(self._questions(user_input, based_on))
        else:
            log.warning("%s question call capped (%s total)", self.session.interview_id, self.total_calls)
        if self.book_task is None or self.book_task.done():
            if self.can_book():
                self._count_call()
                self.book_task = asyncio.create_task(self._bookkeeping(user_input))
            else:
                self.skipped_book += 1

    async def _questions(self, user_input: str, based_on: int) -> None:
        try:
            items = await llm.complete_questions(self.session.brief, user_input)
        except asyncio.CancelledError:
            return
        except llm.LLMRefused:
            log.warning("%s question call refused; keeping queue", self.session.interview_id)
            items = []
        except Exception as e:  # timeout, API error, bad JSON: keep the old queue
            log.warning("%s question call failed (%s: %s); keeping queue", self.session.interview_id, type(e).__name__, e)
            items = []
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


@router.get("/api/contracts")
def get_contracts():
    # E4 merges live interview evidence into these.
    with open(CONTRACTS_PATH) as f:
        return json.load(f)["contracts"]


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
                    runner.session.add_utterance(str(msg.get("text", "")), t_ms)
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


@router.get("/interviewer")
def page_interviewer():
    return _page("interviewer")


@router.get("/board")
def page_board():
    return _page("board")


@router.get("/terms")
def page_terms():
    return _page("terms")


@router.get("/privacy")
def page_privacy():
    return _page("privacy")
