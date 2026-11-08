"""Software Factory Feedback payload, built from a drift finding, and the validator our local stub uses.

Mirrors 8090's documented Feedback Integration API: POST /v2/reporting-api/feedback with
`end_user_email` and `content` (required) and optional `attachments`; extra fields are
rejected. Simulated: we have no live connection or key.

Owner: AK (role D). Interface frozen in plan section 10.4.
"""

SERVICE_EMAIL = "usage-drift@fitcheck.invalid"   # a drift finding is observed, not filed by a clerk
MAX_CONTENT = 20000
MAX_ATTACHMENTS = 5
ALLOWED_KEYS = {"end_user_email", "content", "attachments"}
ATTACHMENT_KEYS = {"file_name", "file_key", "file_size", "mime_type"}
TYPE_LABEL = {"app_gap": "app gap", "stale_requirement": "stale requirement", "know_how_gap": "know-how gap"}
ROLE_LABEL = {"billing_clerk": "billing clerks", "medical_coder": "medical coders",
              "denial_specialist": "denial specialists", "practice_manager": "practice managers"}


def build_payload(finding: dict) -> dict:
    """Feedback item for one finding, in the documented shape. Content always ends with 'Simulated data.'"""
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
    content = "\n".join(lines)
    if len(content) > MAX_CONTENT:
        tail = "\nSimulated data."
        content = content[: MAX_CONTENT - len(tail)] + tail
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
