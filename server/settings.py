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


def load_settings() -> dict:
    s = _copy_defaults()
    if os.path.isfile(SETTINGS_PATH):
        with open(SETTINGS_PATH) as f:
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


def save_settings(changes: dict, actor: str) -> dict:
    """Validate and save partial settings, append an audit entry, handle purge.

    Raises ValueError on bad keys or values (nothing is written then).
    """
    changes = dict(changes)
    purge = bool(changes.pop("purge", False))
    _validate(changes)

    s = load_settings()
    s.update(changes)
    os.makedirs(os.path.dirname(SETTINGS_PATH) or ".", exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(s, f, indent=2, sort_keys=True)

    purged = False
    if purge and not s["drift_enabled"] and os.path.exists(LIVE_EVENTS_PATH):
        os.remove(LIVE_EVENTS_PATH)
        purged = True

    entry = {"ts": _now(), "actor": actor, "changes": changes}
    if purged:
        entry["purged_live_events"] = True
    os.makedirs(os.path.dirname(AUDIT_PATH) or ".", exist_ok=True)
    with open(AUDIT_PATH, "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return s


def recent_audit(n: int = 20) -> list[dict]:
    if not os.path.isfile(AUDIT_PATH):
        return []
    with open(AUDIT_PATH) as f:
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
