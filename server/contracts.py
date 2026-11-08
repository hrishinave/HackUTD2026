"""Load the behaviour-contract catalog and validate contracts against the schema.

Owner: AK (role D). Interface frozen in plan section 10.4.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "contract.schema.json"

_validator = None


def _get_validator() -> Draft202012Validator:
    global _validator
    if _validator is None:
        with open(SCHEMA_PATH) as f:
            _validator = Draft202012Validator(json.load(f))
    return _validator


def load_catalog(path: str) -> dict:
    """Read a contracts catalog (event_catalog, contracts, open_loops). Relative paths resolve from the repo root."""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    with open(p) as f:
        return json.load(f)


def validate_contract(contract: dict) -> list[str]:
    """Return the schema error messages for one contract; [] when valid."""
    errors = sorted(_get_validator().iter_errors(contract), key=lambda e: list(e.path))
    return [f"{'/'.join(str(x) for x in e.path) or '(root)'}: {e.message}" for e in errors]
