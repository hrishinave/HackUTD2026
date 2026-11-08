"""Client settings (drift opt-in, off by default) with an append-only audit log.

Paths are module-level and read inside each function (never as default
arguments) so tests can patch them after import.
"""
import json
import os
from datetime import datetime, timedelta, timezone

from server import contracts as ct

SETTINGS_PATH = "data/client_settings.json"
AUDIT_PATH = "data/audit.jsonl"
LIVE_EVENTS_PATH = "data/live_events.jsonl"

DEFAULTS = {
    "drift_enabled": False,
    "contracts_watched": ["C-01", "C-02", "C-03", "C-04", "C-05"],
    "notes_matching": False,
    "send_to_sf": False,
    "retention_days": 30,
    "admin": "Practice manager",
}


def _copy_defaults() -> dict:
    return json.loads(json.dumps(DEFAULTS))


def _client_path(base: str, company_id: str | None) -> str:
    if not company_id:
        return base
    safe = "".join(ch for ch in company_id if ch.isalnum() or ch in "-_ ").strip().replace(" ", "_") or "default"
    return os.path.join(os.path.dirname(base), "clients", safe, os.path.basename(base))


def load_settings(company_id: str | None = None) -> dict:
    s = _copy_defaults()
    path = _client_path(SETTINGS_PATH, company_id)
    if os.path.isfile(path):
        with open(path) as f:
            stored = json.load(f)
        s.update({k: v for k, v in stored.items() if k in DEFAULTS})
    return s


def _validate(changes: dict) -> None:
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise ValueError(f"unknown setting: {key}")
        default = DEFAULTS[key]
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be true or false")
        elif key == "retention_days":
            if isinstance(value, bool) or value not in (30, 90):
                raise ValueError("retention_days must be 30 or 90")
        elif key == "contracts_watched":
            known = {c["id"] for c in ct.load_all_contracts()}
            if not isinstance(value, list) or any(not isinstance(c, str) or c not in known for c in value):
                raise ValueError("contracts_watched must be a list of known contract IDs")
        elif isinstance(default, str):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key} must be a non-empty string")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_settings(changes: dict, actor: str, company_id: str | None = None) -> dict:
    """Validate and save partial settings, append an audit entry, handle purge.

    Raises ValueError on bad keys or values (nothing is written then).
    """
    changes = dict(changes)
    purge = bool(changes.pop("purge", False))
    _validate(changes)

    s = load_settings(company_id)
    s.update(changes)
    path = _client_path(SETTINGS_PATH, company_id)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(s, f, indent=2, sort_keys=True)

    purged = False
    live_path = _client_path(LIVE_EVENTS_PATH, company_id)
    if purge and not s["drift_enabled"] and os.path.exists(live_path):
        os.remove(live_path)
        purged = True

    entry = {"ts": _now(), "actor": actor, "changes": changes}
    if purged:
        entry["purged_live_events"] = True
    audit_path = _client_path(AUDIT_PATH, company_id)
    os.makedirs(os.path.dirname(audit_path) or ".", exist_ok=True)
    with open(audit_path, "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return s


def recent_audit(n: int = 20, company_id: str | None = None) -> list[dict]:
    path = _client_path(AUDIT_PATH, company_id)
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    return [json.loads(l) for l in lines[-n:]]


def _parse_ts(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def prune_old_events() -> None:
    """Delete live events older than retention_days (events with no readable ts are kept)."""
    if not os.path.isfile(LIVE_EVENTS_PATH):
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=load_settings()["retention_days"])
    kept = []
    with open(LIVE_EVENTS_PATH) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                ts = _parse_ts(json.loads(line).get("ts"))
            except json.JSONDecodeError:
                continue
            if ts is None or ts >= cutoff:
                kept.append(line.rstrip("\n"))
    with open(LIVE_EVENTS_PATH, "w") as f:
        f.write("".join(l + "\n" for l in kept))
