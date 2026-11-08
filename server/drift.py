"""Drift detector: check post-launch usage against behaviour contracts.

Plan section 8: weekly windows per role, privacy floor, learning period, breach and
broken levels, drift after consecutive breached weeks, findings with type, cost and
lineage. Sensors only: nothing here changes the client app.

Owner: AK (role D). Interface frozen in plan section 10.4. This module never imports
server.settings; callers pass settings as a dict.
"""
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POST_EVENTS_PATH = REPO_ROOT / "data" / "post_events.jsonl"

LEVEL_RANK = {"ok": 0, "breach": 1, "broken": 2}
CRITICALITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}
ROLE_LABEL = {"billing_clerk": "billing clerks", "medical_coder": "medical coders",
              "denial_specialist": "denial specialists", "practice_manager": "practice managers"}


# ---------- loading ----------

def load_events(live_path: str | None = None) -> list[dict]:
    """Simulated post-launch events plus live claim-screen events (if a path is given and exists)."""
    events = []
    for path in [POST_EVENTS_PATH, Path(live_path) if live_path else None]:
        if path and Path(path).exists():
            with open(path) as f:
                events.extend(json.loads(line) for line in f if line.strip())
    return events


# ---------- helpers ----------

def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _matches(props: dict, flt: dict) -> bool:
    return all(props.get(k) == v for k, v in flt.items())


def _level(value: float, exp: dict) -> str:
    gap = (exp["target"] - value) if exp["comparator"] == ">=" else (value - exp["target"])
    tol = exp["tolerance"]
    if gap > 2 * tol:
        return "broken"
    if gap > tol:
        return "breach"
    return "ok"


def _claim_tasks(events: list[dict], start: str, end: str, flt: dict, loop: str | None = None) -> list[dict]:
    """Group a week's events by claim into tasks with start, end, merged props and loop count."""
    by_claim = defaultdict(lambda: {"start": None, "end": None, "props": {}, "loops": 0})
    for e in events:
        c = e.get("claim_id_hash")
        if not c:
            continue
        t = by_claim[c]
        if e["event"] == start:
            t["start"] = e["ts"]
            t["props"].update(e["props"])
        elif e["event"] == end:
            t["end"] = e["ts"]
            t["props"].update(e["props"])
        elif loop and e["event"] == loop:
            t["loops"] += 1
    return [t for t in by_claim.values() if t["start"] and t["end"] and _matches(t["props"], flt)]


def _measure(exp: dict, week_events: list[dict], all_role_events: list[dict], flt: dict, people: int,
             notes_matching: bool) -> dict:
    """Return value, tasks (for the floor) and misses (units at risk, for cost) for one expectation in one week."""
    t, p = exp["template"], exp["params"]
    if t in ("field_fill_rate", "detector_rate"):
        pop = [e for e in week_events if e["event"] == p["event"] and _matches(e["props"], flt)]
        if t == "detector_rate":
            if not notes_matching:
                return {"value": None, "tasks": len(pop), "misses": 0}
            hits = sum(1 for e in pop if p["tag"] in e["props"].get("notes_patterns", []))
            return {"value": hits / len(pop) if pop else None, "tasks": len(pop), "misses": hits}
        filled = sum(1 for e in pop if e["props"].get(p["flag"]))
        return {"value": filled / len(pop) if pop else None, "tasks": len(pop), "misses": len(pop) - filled}
    if t == "median_duration":
        tasks = _claim_tasks(week_events, p["start_event"], p["end_event"], flt)
        secs = [(_ts(x["end"]) - _ts(x["start"])).total_seconds() for x in tasks]
        if not secs:
            return {"value": None, "tasks": 0, "misses": 0}
        extra_minutes = sum(max(0.0, s - exp["target"]) for s in secs) / 60
        return {"value": statistics.median(secs), "tasks": len(secs), "misses": round(extra_minutes)}
    if t == "path_conformance":
        tasks = _claim_tasks(week_events, p["task_start"], p["task_end"], flt, loop=p["loop_event"])
        over = sum(1 for x in tasks if x["loops"] > p["max_loops"])
        return {"value": over / len(tasks) if tasks else None, "tasks": len(tasks),
                "misses": sum(max(0, x["loops"] - p["max_loops"]) for x in tasks)}
    if t == "followup_within":
        triggers = [e for e in week_events if e["event"] == p["trigger_event"] and _matches(e["props"], flt)]
        follow = defaultdict(list)
        for e in all_role_events:
            if e["event"] == p["followup_event"] and e.get("claim_id_hash"):
                follow[e["claim_id_hash"]].append(_ts(e["ts"]))
        limit = p["within_hours"] * 3600
        on_time = sum(1 for e in triggers
                      if any(0 <= (f - _ts(e["ts"])).total_seconds() <= limit for f in follow[e["claim_id_hash"]]))
        return {"value": on_time / len(triggers) if triggers else None, "tasks": len(triggers),
                "misses": len(triggers) - on_time}
    if t == "rate_per_person_week":
        n = sum(1 for e in week_events if e["event"] == p["event"] and _matches(e["props"], p.get("where", {})))
        value = n / people if people else None
        excess = max(0.0, n - exp["target"] * people)
        return {"value": value, "tasks": people, "misses": round(excess)}
    raise ValueError(f"unknown template {t}")


# ---------- public interface ----------

def weekly_metrics(contract: dict, events: list[dict], settings: dict | None = None) -> list[dict]:
    """One row per post-launch week: {"week", "values", "tasks", "misses", "people", "levels", "state"}.

    State order (plan 8.3): suppressed (under min_tasks or min_people), then learning, then ok/breach/broken
    from the worst measured expectation. Suppressed weeks hide all values.
    """
    settings = settings or {}
    notes_matching = settings.get("notes_matching", True)
    win = contract["window"]
    role_events = [e for e in events if e["role"] == contract["role"] and e["week"] >= 1]
    by_week = defaultdict(list)
    for e in role_events:
        by_week[e["week"]].append(e)
    flt = contract["population"]["filter"]
    rows = []
    for week in sorted(by_week):
        wev = by_week[week]
        people = len({e["actor_hash"] for e in wev})
        values, tasks, misses, levels = {}, {}, {}, {}
        for exp in contract["expectations"]:
            m = _measure(exp, wev, role_events, flt, people, notes_matching)
            mid = exp["metric_id"]
            values[mid], tasks[mid], misses[mid] = m["value"], m["tasks"], m["misses"]
            if m["value"] is not None:
                levels[mid] = _level(m["value"], exp)
        measured_tasks = [tasks[m] for m in levels] or list(tasks.values()) or [0]
        if min(measured_tasks) < win["min_tasks"] or people < win["min_people"]:
            state = "suppressed"
            values = {k: None for k in values}
            levels = {}
        elif week <= win["learning_period_weeks"]:
            state = "learning"
        elif not levels:
            state = "not_measured"
        else:
            state = max(levels.values(), key=LEVEL_RANK.get)
        rows.append({"week": week, "values": values, "tasks": tasks, "misses": misses, "people": people,
                     "levels": levels, "state": state})
    return rows


def evaluate(contract: dict, weekly: list[dict]) -> dict:
    """Status from the weekly rows: drifting or broken after consecutive breached weeks, else holding."""
    need = contract["window"]["consecutive_breaches_for_drift"]
    judged = [w for w in weekly if w["state"] in LEVEL_RANK]
    if not judged:
        return {"status": "learning", "first_breach_week": None, "early_warning": False, "severity": 0.0,
                "recovered": False}
    runs, current = [], []
    for w in judged:
        if w["state"] in ("breach", "broken"):
            current.append(w)
        else:
            if current:
                runs.append(current)
            current = []
    if current:
        runs.append(current)
    qualifying = [r for r in runs if len(r) >= need]
    still_drifting = bool(qualifying) and qualifying[-1][-1] is judged[-1]
    first_breach = qualifying[0][0]["week"] if qualifying else None
    if still_drifting:
        status = "broken" if any(w["state"] == "broken" for w in qualifying[-1]) else "drifting"
    else:
        status = "holding"
    primary = contract["expectations"][0]
    latest = judged[-1]["values"].get(primary["metric_id"])
    severity = 0.0
    if latest is not None:
        gap = (primary["target"] - latest) if primary["comparator"] == ">=" else (latest - primary["target"])
        beyond = max(0.0, gap - primary["tolerance"]) / primary["tolerance"] if primary["tolerance"] else 0.0
        severity = round(beyond * CRITICALITY_WEIGHT[contract["criticality"]], 2)
    return {"status": status, "first_breach_week": first_breach,
            "early_warning": _early_warning(primary, judged) if status == "holding" else False,
            "severity": severity, "recovered": bool(qualifying) and not still_drifting}


def _early_warning(exp: dict, judged: list[dict]) -> bool:
    """Linear fit over the last 4 judged weeks projects a breach within 2 weeks."""
    pts = [(w["week"], w["values"].get(exp["metric_id"])) for w in judged[-4:]]
    pts = [(x, y) for x, y in pts if y is not None]
    if len(pts) < 3:
        return False
    mx = sum(x for x, _ in pts) / len(pts)
    my = sum(y for _, y in pts) / len(pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    slope = sum((x - mx) * (y - my) for x, y in pts) / den if den else 0.0
    projected = my + slope * (pts[-1][0] + 2 - mx)
    return _level(projected, exp) != "ok" and _level(pts[-1][1], exp) == "ok"


def _signal_series(events: list[dict], role: str) -> dict[str, dict[int, float]]:
    """Weekly discovery-detector rates for prior-auth claims (plan 8.2): dead clicks, tab views, auth numbers in notes."""
    pa_claims, dead, views, notes = defaultdict(set), defaultdict(set), defaultdict(set), defaultdict(int)
    for e in events:
        if e["role"] != role or e["week"] < 1:
            continue
        w, c = e["week"], e.get("claim_id_hash")
        if e["event"] == "claim_submitted" and e["props"].get("requires_prior_auth"):
            pa_claims[w].add(c)
            notes[w] += "auth_number" in e["props"].get("notes_patterns", [])
        elif e["event"] == "ui_click" and e["props"].get("element_id") == "authorization_tab" \
                and not e["props"].get("changed_state"):
            dead[w].add(c)
        elif e["event"] == "claim_tab_viewed" and e["props"].get("tab") == "authorization":
            views[w].add(c)
    out = {"dead_clicks:authorization_tab": {}, "tab_views:authorization": {}, "notes_pattern:auth_number": {}}
    for w, claims in pa_claims.items():
        n = len(claims)
        out["dead_clicks:authorization_tab"][w] = len(dead[w] & claims) / n
        out["tab_views:authorization"][w] = len(views[w] & claims) / n
        out["notes_pattern:auth_number"][w] = notes[w] / n
    return out


def _classify(contract: dict, signals: dict, first_week: int, last_week: int, notes_matching: bool):
    """Rules set the type (plan 8.4). Returns (type, reason, related_signals)."""
    related = []
    for name in contract.get("related_detectors", []):
        series = signals.get(name)
        if not series or first_week not in series or last_week not in series:
            continue
        if name.startswith("notes_pattern") and not notes_matching:
            continue
        related.append({"detector": name, "from": round(series[first_week], 2), "to": round(series[last_week], 2)})
    moved = {r["detector"]: r["to"] - r["from"] for r in related}
    dead_up = moved.get("dead_clicks:authorization_tab", 0) > 0.05
    views_down = moved.get("tab_views:authorization", 0) < -0.10
    workaround_up = moved.get("notes_pattern:auth_number", 0) > 0.05
    if dead_up or views_down:
        parts = []
        if dead_up:
            parts.append("dead clicks on the Authorization tab rose")
        if views_down:
            parts.append("views of the Authorization tab fell")
        reason = " and ".join(parts) + " as the contract metric dropped"
        return "app_gap", reason[0].upper() + reason[1:], related
    latest_views = signals.get("tab_views:authorization", {}).get(last_week)
    if latest_views is not None and latest_views < 0.2 and not workaround_up:
        return "know_how_gap", "The feature is barely visited and shows no frustration signals", related
    return "stale_requirement", "The metric fell with no frustration or workaround signals", related


def _explanation(contract: dict, exp: dict, first: float, last: float, ftype: str, related: list[dict]) -> str:
    who = ROLE_LABEL.get(contract["role"], contract["role"])
    pct = lambda v: f"{v:.0%}" if exp["unit"] == "share" else f"{v:.0f}"
    text = f"{exp['description']} moved from {pct(first)} to {pct(last)} for {who}."
    notes = next((r for r in related if r["detector"] == "notes_pattern:auth_number"), None)
    if ftype == "app_gap" and notes and notes["to"] > notes["from"]:
        text += (f" Over the same weeks the auth number typed into notes rose from {notes['from']:.0%} to "
                 f"{notes['to']:.0%}: clerks have gone back to the legacy workaround, and the Authorization tab "
                 f"is getting fewer views and more dead clicks.")
    elif ftype == "app_gap":
        text += " Frustration signals on the related screen rose at the same time, so the new screen is likely in the way."
    elif ftype == "know_how_gap":
        text += " The feature is barely used and nobody shows frustration, so people may not know it exists."
    else:
        text += " Nothing else moved with it, so the requirement itself may be out of date."
    return text


def findings(contracts: list[dict], events: list[dict], settings: dict | None = None) -> list[dict]:
    """Findings for watched contracts that are drifting or broken (plan 8.4). [] when drift monitoring is off."""
    settings = settings or {}
    if not settings.get("drift_enabled"):
        return []
    watched = set(settings.get("contracts_watched", [c["id"] for c in contracts]))
    notes_matching = settings.get("notes_matching", True)
    out, signals_by_role = [], {}
    for contract in contracts:
        if contract["id"] not in watched:
            continue
        weekly = weekly_metrics(contract, events, settings)
        ev = evaluate(contract, weekly)
        if ev["status"] not in ("drifting", "broken"):
            continue
        exp = contract["expectations"][0]
        mid = exp["metric_id"]
        judged = [w for w in weekly if w["state"] in LEVEL_RANK]
        visible = [w for w in weekly if w["values"].get(mid) is not None]
        last = judged[-1]
        # Baseline: the last healthy judged week before the drift started; else the first visible week.
        healthy = [w for w in judged if w["state"] == "ok" and w["week"] < (ev["first_breach_week"] or 10**6)]
        first = healthy[-1] if healthy else visible[0]
        role = contract["role"]
        if role not in signals_by_role:
            signals_by_role[role] = _signal_series(events, role)
        ftype, reason, related = _classify(contract, signals_by_role[role], first["week"], last["week"], notes_matching)
        ev0 = contract["evidence"][0]
        cost = contract.get("cost_model", {})
        out.append({
            "id": f"F-{len(out) + 1:02d}",
            "contract_id": contract["id"],
            "metric_id": mid,
            "status": ev["status"],
            "weekly": [{"week": w["week"], "value": w["values"].get(mid), "state": w["state"]} for w in weekly],
            "first_breach_week": ev["first_breach_week"],
            "early_warning": ev["early_warning"],
            "severity": ev["severity"],
            "cost_usd_per_week": round(last["misses"].get(mid, 0) * cost.get("unit_cost_usd", 0)),
            "cost_per": cost.get("per"),
            "cost_demo_value": cost.get("demo_value", True),
            "type": ftype,
            "type_reason": reason,
            "related_signals": related,
            "role": role,
            "people": last["people"],
            "requirement_statement": contract["requirement"]["statement"],
            "lineage": {"requirement_id": contract["requirement"]["id"], "quote": ev0["quote"],
                        "speaker": ev0["speaker"], "interview_id": ev0["interview_id"],
                        "timestamp": ev0["timestamp"], "question_id": ev0["question_id"],
                        "question_origin": ev0["question_origin"]},
            "explanation": _explanation(contract, exp, first["values"][mid], last["values"][mid], ftype, related),
        })
    return out
