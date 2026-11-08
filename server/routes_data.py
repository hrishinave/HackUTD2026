"""Data-side routes: simulator, drift, findings, Software Factory payload and stub, eval.

Owner: AK (role D). Paths and shapes are frozen in plan section 10.2. Settings and tokens
are read on every request so tests can change them after import.
"""
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, Body, Header, HTTPException, Request
from fastapi.responses import JSONResponse

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
    return load_catalog(CATALOG_PATH)["contracts"]


def _events() -> list[dict]:
    return dr.load_events(st.LIVE_EVENTS_PATH)


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
def drift():
    """{"enabled": false} when drift monitoring is off; else weekly rows and status per watched contract."""
    s = st.load_settings()
    if not s["drift_enabled"]:
        return {"enabled": False}
    events = _events()
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
def get_findings():
    """Findings for watched, drifting contracts. [] when drift monitoring is off."""
    return dr.findings(_contracts(), _events(), st.load_settings())


# ---------- Software Factory (simulated) ----------

@router.get("/api/findings/{finding_id}/sf-payload")
def sf_payload(finding_id: str):
    """The Feedback payload for one finding. 403 when the client has not allowed sending to Software Factory."""
    s = st.load_settings()
    if not s["send_to_sf"]:
        raise HTTPException(status_code=403, detail="sending to Software Factory is turned off in Client settings")
    for f in dr.findings(_contracts(), _events(), s):
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


# ---------- eval ----------

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
    }
