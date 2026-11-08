"""Software Factory Feedback payload, built from a drift finding, and the validator our local stub uses.

Mirrors 8090's documented Feedback Integration API: POST /v2/reporting-api/feedback with
`end_user_email` and `content` (required) and optional `attachments`; extra fields are
rejected. Simulated: we have no live connection or key.

Content starts with a fixed Pact header (addendum P1) so Software Factory's Triage agent can parse it.
Each finding is filed to the stub at most once (file_finding, FILED_PATH).

Owner: AK (role D). Interface frozen in plan section 10.4 and the Pact addendum.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FILED_PATH = REPO_ROOT / "data" / "filed_feedback.json"   # read at call time; tests patch it
_stub = {"next": 123}                                      # one counter for the stub route and file_finding
HEADER_KEYS = ["Pact-Contract", "Requirement", "Finding", "Status", "Type", "Cost"]

SERVICE_EMAIL = "usage-drift@pact.invalid"   # a drift finding is observed, not filed by a clerk
MAX_CONTENT = 20000
MAX_ATTACHMENTS = 5
ALLOWED_KEYS = {"end_user_email", "content", "attachments"}
ATTACHMENT_KEYS = {"file_name", "file_key", "file_size", "mime_type"}
TYPE_LABEL = {"app_gap": "app gap", "stale_requirement": "stale requirement", "know_how_gap": "know-how gap"}
ROLE_LABEL = {"billing_clerk": "billing clerks", "medical_coder": "medical coders",
              "denial_specialist": "denial specialists", "practice_manager": "practice managers"}


def _requirement_id(finding: dict) -> str:
    rid = (finding.get("lineage") or {}).get("requirement_id") or finding.get("requirement_id")
    if rid:
        return rid
    try:
        from server.contracts import load_all_contracts
        for c in load_all_contracts():
            if c["id"] == finding.get("contract_id"):
                return c["requirement"]["id"]
    except Exception:
        pass
    return "unknown"


def _header(finding: dict) -> str:
    cost = finding.get("cost_usd_per_week")
    values = [
        finding.get("contract_id", "unknown"),
        _requirement_id(finding),
        finding.get("id", "unknown"),
        f"{finding.get('status', 'drifting')} since week {finding.get('first_breach_week')}",
        finding.get("type") or "unknown",
        f"${cost:,}/week at risk (demo value)" if cost is not None else "unknown",
    ]
    return "\n".join(f"{k}: {v}" for k, v in zip(HEADER_KEYS, values)) + "\n---\n"


def parse_header(content: str) -> dict:
    """Read the `Key: value` lines at the top of a Pact Feedback item, up to the `---` line."""
    out = {}
    for line in content.splitlines():
        if line.strip() == "---":
            break
        key, sep, value = line.partition(": ")
        if sep:
            out[key.strip()] = value.strip()
    return out


def build_payload(finding: dict) -> dict:
    """Feedback item for one finding, in the documented shape: Pact header, prose, ending 'Simulated data.'"""
    lin = finding.get("lineage", {})
    req = lin.get("requirement_id", finding.get("contract_id", ""))
    lines = [f"**Usage drift: {req} {finding.get('requirement_statement', '')}**".replace("  ", " "), ""]

    who = ROLE_LABEL.get(finding.get("role"), finding.get("role"))
    people = finding.get("people")
    scope = f" ({who}, {people} people)" if who and people else ""
    lines.append(f"Contract {finding['contract_id']} {finding.get('status', 'drifting')} since week "
                 f"{finding.get('first_breach_week')}{scope}.")
    if finding.get("explanation"):
        lines.append(finding["explanation"])

    related = finding.get("related_signals") or []
    if related:
        lines.append("Related signals: " + "; ".join(
            f"{r['detector']} {r['from']:.0%} to {r['to']:.0%}" for r in related) + ".")

    if finding.get("type"):
        label = TYPE_LABEL.get(finding["type"], finding["type"])
        reason = f" ({finding['type_reason']})" if finding.get("type_reason") else ""
        lines.append(f"Likely type: {label}{reason}.")

    if finding.get("cost_usd_per_week") is not None:
        lines.append(f"Estimated ${finding['cost_usd_per_week']:,}/week at risk (demo value).")

    if lin:
        who_said = f"{lin['speaker']}, " if lin.get("speaker") else ""
        asked = "answer to AI question" if lin.get("question_origin", "ai") == "ai" else "answer to question"
        q = f", {asked} {lin['question_id']}" if lin.get("question_id") else ""
        lines.append(f"Origin: {who_said}{lin.get('interview_id', '')} {lin.get('timestamp', '')}{q}.".replace(" .", "."))

    lines.append("Simulated data.")
    header = _header(finding)
    content = header + "\n".join(lines)
    if len(content) > MAX_CONTENT:
        tail = "\nSimulated data."
        content = content[: MAX_CONTENT - len(tail)] + tail   # header is at the front, so it survives
    return {"end_user_email": SERVICE_EMAIL, "content": content}


def validate_payload(body) -> list[str]:
    """Errors the documented endpoint would return; [] when valid."""
    if not isinstance(body, dict):
        return ["body must be a JSON object"]
    errors = [f"unexpected field '{k}'" for k in sorted(set(body) - ALLOWED_KEYS)]
    email = body.get("end_user_email")
    if not isinstance(email, str) or "@" not in email:
        errors.append("end_user_email is required and must be an email address")
    content = body.get("content")
    if not isinstance(content, str) or not content.strip():
        errors.append("content is required and must not be blank")
    elif len(content) > MAX_CONTENT:
        errors.append(f"content must be at most {MAX_CONTENT} characters")
    if "attachments" in body:
        atts = body["attachments"]
        if not isinstance(atts, list):
            errors.append("attachments must be a list")
        else:
            if len(atts) > MAX_ATTACHMENTS:
                errors.append(f"at most {MAX_ATTACHMENTS} attachments")
            for i, a in enumerate(atts):
                missing = ATTACHMENT_KEYS - set(a) if isinstance(a, dict) else ATTACHMENT_KEYS
                if missing:
                    errors.append(f"attachments[{i}] missing {sorted(missing)}")
                elif not isinstance(a["file_size"], int):
                    errors.append(f"attachments[{i}].file_size must be an integer")
    return errors


# ---------- stub numbering and file-once filing (addendum P1) ----------

def next_feedback_number(counter: dict | None = None) -> int:
    """Next number from the local Software Factory stub. Shared by the stub route and file_finding.

    routes_data passes its own `_stub` dict (read at call time) so both routes count from one place."""
    c = _stub if counter is None else counter
    n = c["next"]
    c["next"] = n + 1
    return n


def _filed_path(company_id: str | None = None) -> Path:
    """FILED_PATH for the default client; data/clients/<company>/filed_feedback.json for another company."""
    from server.settings import _client_path
    return Path(_client_path(str(FILED_PATH), company_id))


def load_filed(company_id: str | None = None) -> dict:
    """{finding_id: {"feedback_number", "contract_id", "filed_at"}}; {} when nothing is filed yet. Per company."""
    p = _filed_path(company_id)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def file_finding(finding: dict, counter: dict | None = None, company_id: str | None = None) -> dict:
    """File a finding to the stub once per company. Filing again returns the original number with already_filed True."""
    payload = build_payload(finding)
    filed = load_filed(company_id)
    if finding["id"] in filed:
        return {"feedback_number": filed[finding["id"]]["feedback_number"], "already_filed": True, "payload": payload}
    errors = validate_payload(payload)
    if errors:
        raise ValueError("; ".join(errors))
    n = next_feedback_number(counter)
    filed[finding["id"]] = {"feedback_number": n, "contract_id": finding["contract_id"],
                            "filed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    p = _filed_path(company_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(filed, indent=2))
    return {"feedback_number": n, "already_filed": False, "payload": payload}
