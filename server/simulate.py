"""Seeded usage simulator for the fictional Medicare billing office.

Generates 12 weeks of legacy-system usage and 8 weeks of post-launch usage of the
modernized claim app, with the C-01 drift and the C-02 holiday decoy planted.
All data is synthetic. Events follow the catalog envelope in
contracts/medicare_contracts.json and never carry free text.

Owner: AK (role D). Interface frozen in plan section 10.4.

    python -m server.simulate --seed 7            # writes data/*.jsonl and kb/log_facts.json
    python -m server.simulate --scenario data/scenario.json
"""
import argparse
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Post-launch values per week (index 0 = week 1). Planted numbers: they appear in the pitch.
DEFAULT_SCENARIO = {
    "weeks_legacy": 12,
    "weeks_post": 8,
    "clerks": 8,
    "denial_specialists": 5,
    "c01_fill": [0.90, 0.95, 0.95, 0.80, 0.62, 0.55, 0.52, 0.50],
    "c01_notes": [0.03, 0.03, 0.05, 0.14, 0.26, 0.29, 0.30, 0.31],
    "c02_median": [290, 280, 270, 265, 400, 262, 260, 258],
    "auth_tab_view_rate": [0.85, 0.80, 0.70, 0.45, 0.30, 0.25, 0.22, 0.20],
}

# Legacy baselines, matching each contract's baseline.values.
LEGACY = {
    "pa_in_notes_rate": 0.71,           # C-01: no PA field in the old app, number typed in notes
    "median_submit_seconds": 260,       # C-02
    "multi_reopen_rate": 0.06,          # C-03
    "recheck_within_48h_rate": 0.83,    # C-04
    "denial_exports_per_person_week": 6.2,  # C-05
}
# Post-launch values that hold steady (C-03, C-04, C-05 should stay healthy).
POST = {
    "multi_reopen_rate": 0.06,
    "recheck_within_48h_rate": 0.92,
    "denial_exports_per_person_week": 0.5,
    "see_fax_rate": 0.05,
}

CLAIMS_PER_CLERK_WEEK = 60
PA_SHARE = 0.35
ONE_REOPEN_RATE = 0.10
COVERAGE_CHANGES_PER_CLERK_WEEK = 5
DENIAL_VIEWS_PER_SPECIALIST_WEEK = 12
DURATION_SPREAD = 0.25                  # log-normal sigma around the weekly median
LAUNCH = datetime(2026, 9, 7, tzinfo=timezone.utc)  # Monday; week 1 starts here
PA_CODES = ["70553", "72148", "74177"]  # imaging procedures that need prior auth
OTHER_CODES = ["99213", "99214", "20610", "93000"]


def _h(text: str, n: int = 10) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:n]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _week_start(week: int) -> datetime:
    return LAUNCH + timedelta(days=7 * (week - 1 if week > 0 else week))


def _event(name, ts, role, actor, session, claim, props, week):
    return {"event": name, "ts": _iso(ts), "role": role, "actor_hash": actor,
            "session_id": session, "claim_id_hash": claim, "props": props, "week": week}


def _count(rng: random.Random, rate: float) -> int:
    """Integer count whose average is `rate`."""
    whole = int(rate)
    return whole + (1 if rng.random() < rate - whole else 0)


def _week_values(scenario: dict, week: int) -> dict:
    if week < 0:
        return {"post": False, "fill": 0.0, "notes": LEGACY["pa_in_notes_rate"], "see_fax": 1.0,
                "median": LEGACY["median_submit_seconds"], "tab": 0.0, "dead": 0.0,
                "multi": LEGACY["multi_reopen_rate"], "recheck": LEGACY["recheck_within_48h_rate"],
                "exports": LEGACY["denial_exports_per_person_week"]}
    i = week - 1
    notes = scenario["c01_notes"][i]
    return {"post": True, "fill": scenario["c01_fill"][i], "notes": notes, "see_fax": POST["see_fax_rate"],
            "median": scenario["c02_median"][i], "tab": scenario["auth_tab_view_rate"][i],
            "dead": 0.05 + 0.6 * notes,  # dead clicks on the Authorization tab rise with the notes workaround
            "multi": POST["multi_reopen_rate"], "recheck": POST["recheck_within_48h_rate"],
            "exports": POST["denial_exports_per_person_week"]}


def _clerk_week(rng, seed, week, i, actor, v, out):
    role = "billing_clerk"
    ws = _week_start(week)
    for n in range(CLAIMS_PER_CLERK_WEEK):
        day = n % 5
        opened = ws + timedelta(days=day, hours=8, seconds=rng.randrange(0, 8 * 3600))
        claim = _h(f"{seed}-claim-{week}-{i}-{n}", 12)
        session = _h(f"{seed}-session-{actor}-{week}-{day}", 12)
        pa = rng.random() < PA_SHARE
        code = rng.choice(PA_CODES if pa else OTHER_CODES)
        r = rng.random()
        reopens = 2 if r < v["multi"] else (1 if r < v["multi"] + ONE_REOPEN_RATE else 0)
        duration = v["median"] * math.exp(rng.gauss(0, DURATION_SPREAD))
        submitted = opened + timedelta(seconds=round(duration))

        out.append(_event("claim_opened", opened, role, actor, session, claim,
                          {"claim_type": "professional", "requires_prior_auth": pa, "procedure_code": code}, week))
        filled = False
        if pa and v["post"]:
            filled = rng.random() < v["fill"]
            viewed = filled or rng.random() < v["tab"]   # filling the field needs the tab
            if viewed:
                out.append(_event("claim_tab_viewed", opened + timedelta(seconds=20), role, actor, session, claim,
                                  {"tab": "authorization"}, week))
            if rng.random() < v["dead"]:
                out.append(_event("ui_click", opened + timedelta(seconds=15), role, actor, session, claim,
                                  {"element_id": "authorization_tab", "changed_state": False}, week))
        tags = []
        if pa:
            if rng.random() < v["notes"]:
                tags.append("auth_number")
            elif rng.random() < v["see_fax"]:
                tags.append("see_fax")
        for k in range(reopens):
            t = opened + timedelta(seconds=round(duration * (k + 1) / (reopens + 1)))
            out.append(_event("claim_reopened", t, role, actor, session, claim, {}, week))
        out.append(_event("claim_submitted", submitted, role, actor, session, claim,
                          {"requires_prior_auth": pa, "prior_auth_number_filled": filled, "notes_patterns": tags,
                           "first_pass_clean": reopens == 0, "procedure_code": code}, week))

    for k in range(COVERAGE_CHANGES_PER_CLERK_WEEK):
        t = ws + timedelta(days=k % 5, hours=9, seconds=rng.randrange(0, 7 * 3600))
        claim = _h(f"{seed}-coverage-{week}-{i}-{k}", 12)
        session = _h(f"{seed}-session-{actor}-{week}-{k % 5}", 12)
        out.append(_event("coverage_changed", t, role, actor, session, claim, {"after_date_of_service": True}, week))
        if rng.random() < v["recheck"]:
            delay = timedelta(hours=rng.uniform(1, 40))
        elif rng.random() < 0.5:
            delay = timedelta(hours=rng.uniform(60, 120))   # checked, but too late
        else:
            continue                                         # never re-checked
        out.append(_event("eligibility_checked", t + delay, role, actor, session, claim, {}, week))


def _specialist_week(rng, seed, week, i, actor, v, out):
    role = "denial_specialist"
    ws = _week_start(week)
    for k in range(DENIAL_VIEWS_PER_SPECIALIST_WEEK):
        day = k % 5
        t = ws + timedelta(days=day, hours=8, seconds=rng.randrange(0, 8 * 3600))
        out.append(_event("ui_click", t, role, actor, _h(f"{seed}-session-{actor}-{week}-{day}", 12), None,
                          {"element_id": "denials_list", "changed_state": True}, week))
    for k in range(_count(rng, v["exports"])):
        day = k % 5
        t = ws + timedelta(days=day, hours=16, seconds=rng.randrange(0, 3600))
        out.append(_event("export_csv", t, role, actor, _h(f"{seed}-session-{actor}-{week}-{day}", 12), None,
                          {"source_view": "denials"}, week))


def _sort_key(e):
    return (e["ts"], e["event"], e["actor_hash"], e["claim_id_hash"] or "")


def generate(seed: int, scenario: dict) -> tuple[list[dict], list[dict]]:
    """Return (legacy_events, post_events), each sorted by time. Same seed and scenario give identical output."""
    rng = random.Random(seed)
    clerks = [hashlib.sha1(f"{seed}-billing_clerk-{i}".encode()).hexdigest()[:10] for i in range(scenario["clerks"])]
    specialists = [hashlib.sha1(f"{seed}-denial_specialist-{i}".encode()).hexdigest()[:10]
                   for i in range(scenario["denial_specialists"])]
    weeks = list(range(-scenario["weeks_legacy"], 0)) + list(range(1, scenario["weeks_post"] + 1))
    legacy, post = [], []
    for week in weeks:
        v = _week_values(scenario, week)
        out = post if week > 0 else legacy
        for i, actor in enumerate(clerks):
            _clerk_week(rng, seed, week, i, actor, v, out)
        for i, actor in enumerate(specialists):
            _specialist_week(rng, seed, week, i, actor, v, out)
    legacy.sort(key=_sort_key)
    post.sort(key=_sort_key)
    return legacy, post


def legacy_facts(events: list[dict]) -> dict:
    """Baseline numbers from legacy logs, for kb/log_facts.json (the interview brief cites these)."""
    by_claim = defaultdict(dict)
    reopens = defaultdict(int)
    pa_claims = pa_in_notes = 0
    for e in events:
        c = e["claim_id_hash"]
        if e["event"] == "claim_opened":
            by_claim[c]["opened"] = e["ts"]
        elif e["event"] == "claim_reopened":
            reopens[c] += 1
        elif e["event"] == "claim_submitted":
            by_claim[c]["submitted"] = e["ts"]
            by_claim[c]["clean"] = e["props"]["first_pass_clean"]
            if e["props"]["requires_prior_auth"]:
                pa_claims += 1
                pa_in_notes += "auth_number" in e["props"]["notes_patterns"]
    secs = lambda a, b: (datetime.fromisoformat(b.replace("Z", "+00:00")) - datetime.fromisoformat(a.replace("Z", "+00:00"))).total_seconds()
    durations = [secs(v["opened"], v["submitted"]) for v in by_claim.values() if v.get("clean") and "opened" in v]
    submitted = [c for c, v in by_claim.items() if "submitted" in v]
    triggers = {e["claim_id_hash"]: e["ts"] for e in events if e["event"] == "coverage_changed"}
    checks = {e["claim_id_hash"]: e["ts"] for e in events if e["event"] == "eligibility_checked"}
    on_time = sum(1 for c, t in triggers.items() if c in checks and secs(t, checks[c]) <= 48 * 3600)
    exports = sum(1 for e in events if e["event"] == "export_csv")
    person_weeks = len({(e["actor_hash"], e["week"]) for e in events if e["role"] == "denial_specialist"})
    weeks = sorted({e["week"] for e in events})
    return {
        "source": f"synthetic legacy logs, weeks {weeks[0]} to {weeks[-1]}",
        "facts": {
            "pa_in_notes_rate": round(pa_in_notes / pa_claims, 3),
            "median_submit_seconds": round(statistics.median(durations)),
            "multi_reopen_rate": round(sum(1 for c in submitted if reopens[c] >= 2) / len(submitted), 3),
            "recheck_within_48h_rate": round(on_time / len(triggers), 3),
            "denial_exports_per_person_week": round(exports / person_weeks, 2),
        },
        "plain": [
            "In the legacy system the prior-auth number is typed into the notes on most prior-auth claims; the PA-NUM field is never used.",
            "A clean claim takes a clerk about four and a half minutes from opening to submitting.",
            "Most coverage changes after a visit are re-checked within two days.",
            "Denial specialists export the denials list several times a week.",
        ],
        "note": "Synthetic demo data.",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic legacy and post-launch usage.")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--scenario", help="JSON file overriding DEFAULT_SCENARIO keys (e.g. data/scenario.json)")
    args = ap.parse_args()
    scenario = dict(DEFAULT_SCENARIO)
    if args.scenario:
        with open(args.scenario) as f:
            scenario.update(json.load(f))
    legacy, post = generate(args.seed, scenario)
    data_dir = REPO_ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    for name, events in [("legacy_events.jsonl", legacy), ("post_events.jsonl", post)]:
        with open(data_dir / name, "w") as f:
            for e in events:
                f.write(json.dumps(e, sort_keys=True) + "\n")
    with open(REPO_ROOT / "kb" / "log_facts.json", "w") as f:
        json.dump(legacy_facts(legacy), f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"seed {args.seed}: {len(legacy)} legacy events, {len(post)} post-launch events; wrote data/*.jsonl and kb/log_facts.json")


if __name__ == "__main__":
    main()
