"""Data-side routes: simulator, drift, findings, Software Factory payload and stub, eval.

Owner: AK (role D). Paths and shapes are frozen in plan section 10.2. Settings and tokens
are read on every request so tests can change them after import.
"""
import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from server import contract_draft as cd
from server import contracts as ct
from server import drift as dr
from server import settings as st
from server import simulate as sim
from server.contracts import load_catalog
from server.feedback import build_payload, validate_payload

router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = "contracts/medicare_contracts.json"
ANSWER_KEY_PATH = REPO_ROOT / "legacy" / "answer_key.json"
STATE_DIR = REPO_ROOT / "data" / "state"      # interview states saved by the engine (E4)
_stub = {"next": 123}                          # local Software Factory stub numbering

# How a recorded contradiction is matched to the answer key (plan 6, X-1 and X-2).
CONTRADICTION_MATCHERS = {
    "X-1": {"rule_id": "MOD-25", "keywords": ["modifier"]},
    "X-2": {"rule_id": None, "keywords": ["fax"]},
}


def _contracts() -> list[dict]:
    """Catalog contracts plus approved drafted contracts (D5), so drift, findings and payloads include them."""
    return ct.load_all_contracts()


def _settings(company_id: str | None = None) -> dict:
    """The saved watch list is authoritative, including an explicit empty list."""
    return st.load_settings(company_id)


def _events(company_id: str | None = None) -> list[dict]:
    return dr.load_events(st._client_path(st.LIVE_EVENTS_PATH, company_id))


def _require_admin(token: str | None) -> None:
    expected = os.environ.get("ADMIN_TOKEN")
    if not expected or token != expected:
        raise HTTPException(status_code=401, detail="admin token required")


# ---------- simulator ----------

@router.post("/api/simulate")
def simulate(body: dict | None = Body(default=None), x_admin_token: str | None = Header(default=None)):
    """Regenerate the synthetic data. Body: {"seed": 7}. Admin only."""
    _require_admin(x_admin_token)
    seed = int((body or {}).get("seed", 7))
    counts = sim.write_outputs(seed, sim.DEFAULT_SCENARIO)
    return {"ok": True, "seed": seed, **counts}


# ---------- drift ----------

@router.get("/api/drift")
def drift(company_id: str | None = None):
    """{"enabled": false} when drift monitoring is off; else weekly rows and status per watched contract."""
    s = _settings(company_id)
    if not s["drift_enabled"]:
        return {"enabled": False}
    events = _events(company_id)
    out = []
    for c in _contracts():
        if c["id"] not in s["contracts_watched"]:
            continue
        weekly = dr.weekly_metrics(c, events, s)
        ev = dr.evaluate(c, weekly)
        out.append({
            "contract_id": c["id"],
            "requirement": c["requirement"],
            "role": c["role"],
            "signal": c["signal"],
            "expectations": [{k: e[k] for k in ("metric_id", "description", "comparator", "target", "unit", "tolerance")}
                             for e in c["expectations"]],
            "learning_period_weeks": c["window"]["learning_period_weeks"],
            "status": ev["status"],
            "first_breach_week": ev["first_breach_week"],
            "early_warning": ev["early_warning"],
            "severity": ev["severity"],
            "recovered": ev["recovered"],
            "weekly": [{"week": w["week"], "values": w["values"], "state": w["state"], "people": w["people"]}
                       for w in weekly],
        })
    return {"enabled": True, "contracts": out}


@router.get("/api/findings")
def get_findings(company_id: str | None = None):
    """Findings for watched, drifting contracts. [] when drift monitoring is off."""
    return dr.findings(_contracts(), _events(company_id), _settings(company_id))


# ---------- Software Factory (simulated) ----------

@router.get("/api/findings/{finding_id}/sf-payload")
def sf_payload(finding_id: str, company_id: str | None = None):
    """The Feedback payload for one finding. 403 when the client has not allowed sending to Software Factory."""
    s = _settings(company_id)
    if not s["send_to_sf"]:
        raise HTTPException(status_code=403, detail="sending to Software Factory is turned off in Client settings")
    for f in dr.findings(_contracts(), _events(company_id), s):
        if f["id"] == finding_id:
            return build_payload(f)
    raise HTTPException(status_code=404, detail=f"unknown finding: {finding_id}")


@router.post("/stub/v2/reporting-api/feedback")
async def feedback_stub(request: Request):
    """Local stand-in for 8090's Feedback Integration API. Simulated, no live connection."""
    try:
        body = await request.json()
    except Exception:
        body = None
    errors = validate_payload(body) if body is not None else ["body must be valid JSON"]
    if errors:
        return JSONResponse(status_code=422, content={"detail": {
            "error_code": "unprocessable_entity", "message": "invalid feedback payload", "details": errors}})
    n = _stub["next"]
    _stub["next"] = n + 1
    return {"feedback_number": n}


# ---------- contract drafting (Task D5) ----------

_draft_locks: dict[str, asyncio.Lock] = {}


@router.post("/api/drafts")
async def run_drafts(body: dict = Body(...)):
    """Draft contracts from one interview's saved state. Body: {"interview_id": "INT-01"}."""
    interview_id = str((body or {}).get("interview_id", ""))
    if not re.fullmatch(r"INT-\d{2}", interview_id):
        raise HTTPException(status_code=422, detail="interview_id must look like INT-01")
    if not (Path(cd.STATE_DIR) / f"{interview_id}.json").exists():
        raise HTTPException(status_code=404, detail=f"no saved interview state for {interview_id}")
    lock = _draft_locks.setdefault(interview_id, asyncio.Lock())
    if lock.locked():
        raise HTTPException(status_code=409, detail=f"already drafting {interview_id}")
    async with lock:
        try:
            return await cd.draft_contracts(interview_id)
        except Exception as exc:  # model call failed, refused or was cut off; saved drafts are unchanged
            return JSONResponse(status_code=502, content={"error": f"drafting failed: {type(exc).__name__}: {exc}"})


@router.get("/api/drafts")
def get_drafts(interview_id: str | None = None, status: str | None = None):
    return cd.load_drafts(interview_id, status)


def _decide(fn, draft_id: str, token: str | None, *args):
    _require_admin(token)
    try:
        return fn(draft_id, st.load_settings().get("admin", "admin"), *args)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown draft: {draft_id}")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/api/drafts/{draft_id}/approve")
def approve_draft(draft_id: str, x_admin_token: str | None = Header(default=None)):
    return _decide(cd.approve_draft, draft_id, x_admin_token)


@router.post("/api/drafts/{draft_id}/reject")
def reject_draft(draft_id: str, body: dict | None = Body(default=None), x_admin_token: str | None = Header(default=None)):
    return _decide(cd.reject_draft, draft_id, x_admin_token, (body or {}).get("reason"))


# ---------- eval ----------

def _draft_text(rec: dict) -> str:
    body = rec["contract"] if rec["kind"] == "contract" else rec["open_loop"]
    return (body["requirement"]["statement"] + " " + " ".join(e["quote"] for e in body["evidence"])).lower()


def _uncovered_scores(key: dict) -> dict:
    """D5: did drafting find the planted requirements no existing contract covers, and classify them right?"""
    planted = key.get("uncovered_requirements", [])
    drafts = cd.load_drafts()
    found, right = [], 0
    for u in planted:
        hits = [r for r in drafts if sum(k in _draft_text(r) for k in u["keywords"]) >= 2]
        if hits:
            found.append(u["id"])
            if any((r["kind"] == "contract") == u["measurable"] for r in hits):
                right += 1
    return {"uncovered_found": len(found), "uncovered_matched": found, "uncovered_total": len(planted),
            "uncovered_classified_right": right}


def _load_states() -> list[dict]:
    states = []
    d = Path(STATE_DIR)
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            try:
                raw = json.loads(p.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            states.append(raw.get("state", raw) if isinstance(raw, dict) else {})
    return states


def _matches(contradiction: dict, matcher: dict) -> bool:
    if matcher["rule_id"] and contradiction.get("rule_id") == matcher["rule_id"]:
        return True
    text = f"{contradiction.get('statement_a', '')} {contradiction.get('statement_b', '')}".lower()
    return any(k in text for k in matcher["keywords"])


@router.get("/api/eval")
def eval_scores():
    """Score saved interviews against the answer key: rules and contradictions the agent surfaced."""
    key = json.loads(Path(ANSWER_KEY_PATH).read_text())
    rule_ids = {r["id"] for r in key["rules"]}
    hidden = {r["id"] for r in key["rules"] if r["hidden"]}
    states = _load_states()
    found = sorted({r for s in states for r in s.get("rules_mentioned", []) if r in rule_ids})
    recorded = [c for s in states for c in s.get("contradictions", [])]
    matched = sorted(x["id"] for x in key["contradictions"]
                     if x["id"] in CONTRADICTION_MATCHERS
                     and any(_matches(c, CONTRADICTION_MATCHERS[x["id"]]) for c in recorded))
    return {
        "interviews": len(states),
        "rules_found": found,
        "rules_total": len(rule_ids),
        "hidden_found": len(set(found) & hidden),
        "hidden_total": len(hidden),
        "contradictions_found": len(matched),
        "contradictions_matched": matched,
        "contradictions_total": len(key["contradictions"]),
        **_uncovered_scores(key),
    }
