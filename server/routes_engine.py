"""Engine routes: client WebSocket, interviews, contracts, settings, pages (except /claim)."""
import logging
import os

from fastapi import APIRouter, Body, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from server import settings as st

log = logging.getLogger("fitcheck.engine")


def _startup_prune() -> None:
    try:
        st.prune_old_events()
    except Exception:  # never block startup on a bad events file
        log.exception("prune_old_events failed")


router = APIRouter(on_startup=[_startup_prune])


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

# interview_id -> per-session state (fake for E1; InterviewSession from E3)
sessions: dict[str, dict] = {}


def _fake_queue(t_ms: int) -> dict:
    return {
        "type": "queue",
        "based_on_t_ms": t_ms,
        "questions": [
            {
                "id": "Q-1",
                "bank_id": None,
                "cue": "Detail:",
                "text": "Can you walk me through a normal claim?",
                "target": "C-02.current_practice",
                "audio_url": None,
            }
        ],
    }


@router.websocket("/ws/client/{interview_id}")
async def client_ws(ws: WebSocket, interview_id: str):
    await ws.accept()
    session = sessions.setdefault(interview_id, {"played": []})
    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            if kind == "utterance" and msg.get("final", True):
                await ws.send_json(_fake_queue(int(msg.get("t_ms", 0))))
            elif kind == "played":
                session["played"].append(msg.get("question_id"))
                log.info("played %s %s", interview_id, msg.get("question_id"))
                await ws.send_json({"type": "ack", "of": "played", "question_id": msg.get("question_id")})
            elif kind in ("hello", "tap", "metric"):
                log.info("%s %s %s", interview_id, kind, msg)
    except WebSocketDisconnect:
        pass


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
