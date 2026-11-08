"""Load the behaviour-contract catalog and validate contracts against the schema.

Owner: AK (role D). Interface frozen in plan section 10.4.
"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "contracts" / "contract.schema.json"
CATALOG_PATH = "contracts/medicare_contracts.json"
APPROVED_PATH = REPO_ROOT / "data" / "contracts_approved.json"   # approved drafts (D5); read at call time

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


# ---------- approved drafts (Task D5) ----------

def _approved() -> dict:
    p = Path(APPROVED_PATH)
    if not p.exists():
        return {"contracts": [], "open_loops": []}
    d = json.loads(p.read_text())
    d.setdefault("contracts", [])
    d.setdefault("open_loops", [])
    return d


def load_all_contracts() -> list[dict]:
    """Catalog contracts (C-01..C-05) plus every approved drafted contract."""
    return load_catalog(CATALOG_PATH)["contracts"] + _approved()["contracts"]


def load_all_open_loops() -> list[dict]:
    """Catalog open loops plus every approved drafted open loop."""
    return load_catalog(CATALOG_PATH).get("open_loops", []) + _approved()["open_loops"]


def _num(identifier: str) -> int:
    return int(identifier.split("-")[1])


def next_ids() -> tuple[str, str]:
    """Next free contract and requirement IDs. Requirement IDs count open loops too (R-06 is the catalog open loop)."""
    contracts, loops = load_all_contracts(), load_all_open_loops()
    c = max([_num(x["id"]) for x in contracts] or [0]) + 1
    r = max([_num(x["requirement"]["id"]) for x in contracts + loops] or [0]) + 1
    return f"C-{c:02d}", f"R-{r:02d}"
