"""Contract lifecycle: drafted, approved, baselined, kept or broken, renegotiated.

One object's story from interview to Software Factory: "The interview writes the pact. Usage checks it's kept."
Pure function over inputs the route gathers, so tests build them by hand.

Owner: AK (role D). Interface: Pact addendum, task P3.
"""
from server import drift

ORDER = ["drafted", "approved", "baselined", "kept", "broken", "renegotiated"]   # kept and broken share a position


def _stage(stages: dict) -> str:
    current = "drafted"
    for name in ORDER:
        if stages.get(name):
            current = name
    return current


def contract_stages(contracts, drafts, findings, filed, settings, legacy_events, baseline_fn=None) -> dict:
    """{id: {"stage", "stages": {name: bool}, "detail": {...}}} for every contract and every pending draft."""
    baseline_fn = baseline_fn or drift.legacy_baseline
    watching = bool(settings.get("drift_enabled"))
    by_contract = {}
    for f in findings or []:
        by_contract.setdefault(f["contract_id"], f)
    filed_by_contract = {}
    for fid, entry in (filed or {}).items():
        filed_by_contract.setdefault(entry.get("contract_id"), {"finding_id": fid, **entry})

    out = {}
    for c in contracts:
        values = baseline_fn(c, legacy_events, settings) or {}
        finding = by_contract.get(c["id"])
        filing = filed_by_contract.get(c["id"])
        stages = {
            "drafted": True,
            "approved": True,
            "baselined": any(v is not None for v in values.values()),
            "kept": watching and finding is None,
            "broken": watching and finding is not None,
            "renegotiated": filing is not None,
        }
        detail = {
            "requirement_id": c.get("requirement", {}).get("id"),
            "watching": "on" if watching else "off",
            "baseline": values,
            "finding_id": finding["id"] if finding else None,
            "finding_status": finding.get("status") if finding else None,
            "feedback_number": filing.get("feedback_number") if filing else None,
        }
        out[c["id"]] = {"stage": _stage(stages), "stages": stages, "detail": detail}

    for d in drafts or []:
        if d.get("status") != "draft":
            continue
        stages = {name: name == "drafted" for name in ORDER}
        out[d["draft_id"]] = {"stage": "drafted", "stages": stages,
                              "detail": {"watching": "on" if watching else "off", "kind": d.get("kind")}}
    return out
