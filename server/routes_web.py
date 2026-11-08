"""Claim demo and opt-in, catalog-only usage events (no claim contents)."""
import hashlib
import html
import json
import os
import re
import secrets
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from server import settings

router = APIRouter()
ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / "contracts/medicare_contracts.json").read_text(encoding="utf-8"))["event_catalog"]
ROLES = {"billing_clerk", "medical_coder", "denial_specialist", "practice_manager"}
ENVELOPE = set(CATALOG["envelope"]) | {"week"}
_file_lock = Lock()


@router.get("/api/interview-options")
def interview_options():
    """Return companies and their interviewable people for the board start flow."""
    people_path = ROOT / "kb" / "people.json"
    people = json.loads(people_path.read_text(encoding="utf-8")) if people_path.exists() else {}
    company = {"id": "medicare_billing_demo", "name": "Medicare Billing Office", "people": []}
    for person_id, person in sorted(people.items()):
        company["people"].append({
            "id": person_id,
            "label": person.get("label", person_id),
            "role": person.get("role", ""),
            "interview_id": person.get("interview_id", ""),
        })
    return {"companies": [company]}


@router.get("/api/interviews")
def interviews():
    """List saved and currently running interviews for the board selector."""
    state_dir = ROOT / "data" / "state"
    saved = {}
    if state_dir.is_dir():
        for path in state_dir.glob("INT-*.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                state = raw.get("state", raw)
                saved[path.stem] = {
                    "interview_id": path.stem,
                    "label": state.get("label") or state.get("interviewee") or path.stem,
                    "person_name": state.get("person_name", state.get("label", "")),
                    "position": state.get("position", ""),
                    "company_name": state.get("company_name", ""),
                    "interviewee": state.get("interviewee", ""),
                    "started": True,
                    "updated_at": path.stat().st_mtime,
                }
            except (OSError, ValueError, TypeError):
                continue
    try:
        from server import routes_engine
        for interview_id, runner in routes_engine.sessions.items():
            state = runner.session.state()
            saved[interview_id] = {
                "interview_id": interview_id,
                "label": state.get("label") or state.get("interviewee") or interview_id,
                "person_name": state.get("person_name", state.get("label", "")),
                "position": state.get("position", ""),
                "company_name": state.get("company_name", ""),
                "interviewee": state.get("interviewee", ""),
                "started": True,
                "updated_at": None,
            }
    except Exception:
        pass
    return sorted(saved.values(), key=lambda item: item["interview_id"])


@router.get("/claim", response_class=HTMLResponse)
def claim():
    token = os.environ.get("CLIENT_WRITE_TOKEN")
    if not token:
        raise HTTPException(503, "Client write token is not configured")
    template = (ROOT / "server/static/claim.html").read_text(encoding="utf-8")
    return HTMLResponse(template.replace("{{CLIENT_TOKEN}}", html.escape(token, quote=True)),
                        headers={"Cache-Control": "no-store"})


def _validate_event(body):
    def invalid():
        raise HTTPException(422, "Expected a catalog event with flags and short IDs only")

    if not isinstance(body, dict) or set(body) - ENVELOPE:
        invalid()
    event = body.get("event")
    if not isinstance(event, str) or event not in CATALOG["events"]:
        invalid()
    if not isinstance(body.get("role"), str) or body["role"] not in ROLES:
        invalid()
    session = body.get("session_id")
    if not isinstance(session, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", session):
        invalid()
    claim_id = body.get("claim_id_hash")
    if claim_id is not None and (not isinstance(claim_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", claim_id)):
        invalid()
    props = body.get("props")
    allowed = CATALOG["events"][event]
    if not isinstance(props, dict) or set(props) - set(allowed):
        invalid()
    for name, value in props.items():
        kind = allowed[name]
        if name in {"notes", "text"}:
            invalid()
        if name == "notes_patterns":
            if not isinstance(value, list) or any(not isinstance(tag, str) or tag not in CATALOG["notes_pattern_tags"] for tag in value):
                invalid()
        elif kind.startswith("bool"):
            if not isinstance(value, bool):
                invalid()
        elif not isinstance(value, str) or len(value) > 40:
            invalid()
        elif " | " in kind and value not in kind.split(" | "):
            invalid()
    return {"event": event, "role": body["role"], "session_id": session,
            "claim_id_hash": claim_id, "props": dict(props)}


@router.post("/api/events")
async def post_event(request: Request, x_client_token: str | None = Header(default=None)):
    expected = os.environ.get("CLIENT_WRITE_TOKEN")
    if not expected or not x_client_token or not secrets.compare_digest(x_client_token, expected):
        raise HTTPException(401, "Client token required")
    current = settings.load_settings()
    if not current["drift_enabled"]:
        raise HTTPException(403, "Usage monitoring is off")
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, "Expected a JSON event") from None
    event = _validate_event(body)
    if not current["notes_matching"]:
        event["props"].pop("notes_patterns", None)
    event.update(week=8, ts=datetime.now(timezone.utc).isoformat(),
                 actor_hash=hashlib.sha1(event["session_id"].encode()).hexdigest()[:10])
    path = Path(settings.LIVE_EVENTS_PATH)
    with _file_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
    return {"ok": True}


@router.get("/api/events/recent")
def recent_events():
    path = Path(settings.LIVE_EVENTS_PATH)
    with _file_lock:
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as stream:
            return [json.loads(line) for line in deque((line for line in stream if line.strip()), maxlen=50)]
