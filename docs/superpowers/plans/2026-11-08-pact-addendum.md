# Pact Addendum: behaviour contracts into Software Factory (Requirements + Feedback triage)

> **For agentic workers:** this addendum extends `docs/superpowers/plans/2026-11-08-hackutd-8090-full-plan.md`. The same rules apply: tests first, own files only, gates through the integrator. Use superpowers:executing-plans or superpowers:subagent-driven-development task by task.

**Status:** Final, 2026-11-08. Verified against `main` at `ac3d37b` (gates open: G0, C1, C3, C4, D1, D2, D3, D4, D5-drafts, E1, E2, E3, E4, W2, W3, W4, W5-drafts-ui). The board already has the Software Factory drawer (W4) and the drafts UI (W5); this addendum modifies them, it does not rebuild them. No code was changed while writing it. Read-back confirmation and said-vs-did questions were considered and **dropped** from this build; they stay in Devpost's "What's next".

**Goal:** Make the behaviour contract Pact's single, visible output, and land it in two Software Factory places (the Feature Requirements doc and Feedback triage), with skills that let 8090's own agents write, triage and review contracts.

**What changes, in one paragraph:** A contract gets a visible lifecycle: drafted, approved by 8090, baselined, kept or broken, renegotiated. An approved contract can be exported as a Software Factory Feature Requirements document. A broken contract is filed once as a structured Feedback item that Software Factory's Triage agent can parse. Four skills teach 8090's existing agents how to use contracts. Separately, the product is renamed from Fit Check to Pact.

## Final requirements

1. The Feedback payload keeps its documented shape `{end_user_email, content}`, but `content` starts with a fixed, parseable header naming the contract, requirement, finding, status, type and cost.
2. Each finding is filed to the stub at most once; filing again returns the original number.
3. Any contract can be exported as a Markdown Feature Requirements document containing its evidence, confidence and a "Behaviour contract" section; a broken contract's export adds a proposed change labelled simulated.
4. Every contract shows its lifecycle stage on the board: drafted, approved, baselined, kept or broken, renegotiated.
5. The board's Software Factory drawer files a finding through the file-once route and shows the same FB number on a second click.
6. Four skills exist in `skills/`: contract writing, drift triage, persona review, interview. The triage skill describes the exact header from requirement 1.
7. One real persona-review run against the claim screen is recorded in `docs/evidence/persona-review.md`, unedited.
8. "Fit Check" no longer appears in product code, pages or docs (historical gate-log lines excepted); the service email is `usage-drift@pact.invalid`.
9. Every existing test still passes; nothing behind an open gate breaks.

## Why each piece exists

| Piece | Why |
|---|---|
| Fixed Feedback header + file once | The payload is free prose today, so Software Factory's Triage agent can't reliably tell a Pact item apart or link it to its requirement. Filing again currently creates a new number every time, which would flood triage with duplicates |
| Requirements export | The only integration that works today with no API key: Software Factory requirements are Markdown, and their Requirements agent reads documents you add to a project. It lands the interview half of Pact inside their product |
| Contract lifecycle | Turns two tools that look separate (interview, drift) into one object's story: "The interview writes the pact. Usage checks it's kept." |
| Skills (4) | Software Factory already ships Requirements Writing Rules and Triage Feedback skills. Ours teach those agents to use contracts, so the idea works inside Software Factory without our app |
| Persona review skill + one real run | Moves drift detection to before launch: an agent playing the real billing clerk, grounded in contracts and her own quotes, should flag the auth field hidden on a second tab (C-01) before any clerk sees it |
| Rename to Pact | The product name. Every user-facing title and the service email should match the pitch |

## What already exists and is reused (do not rebuild)

- **Contract drafting with approval** (`server/contract_draft.py`, gate D5-drafts): `draft_contracts`, `load_drafts`, `approve_draft`, `reject_draft`; `POST /api/drafts`, `GET /api/drafts`, `POST /api/drafts/{id}/approve|reject`. Approval assigns C-06/R-07... and adds to `data/contracts_approved.json`. This is the **drafted** and **approved** stage.
- **All contracts:** `server.contracts.load_all_contracts()` (catalog + approved drafts), `load_all_open_loops()`.
- **Drift:** `server.drift.findings(contracts, events, settings)`, `legacy_baseline(contract, legacy_events, settings)`, `load_events()`, `load_legacy_events()`; routes `GET /api/drift`, `GET /api/findings`.
- **Feedback:** `server.feedback.build_payload(finding)`, `validate_payload(body)`; `GET /api/findings/{id}/sf-payload` (403 when `send_to_sf` is off); stub `POST /stub/v2/reporting-api/feedback` with an in-memory counter `_stub["next"]` starting at 123.
- **Saved interview states:** `data/state/`, read by `routes_data._load_states()`.

## Global constraints (in addition to the main plan's)

- Task IDs and gates use the prefix **P** (C5, D5, W5 are already taken on `main`).
- Do not break anything behind an open gate. Every existing test must still pass.
- The Feedback payload **shape** stays exactly `{end_user_email, content}`. Only the text inside `content` changes.
- Nothing in this addendum sends anything to a real 8090 endpoint. Exports are downloads; filing goes to the local stub and is labelled "Simulated, no live connection".
- The interview engine (`server/engine.py`, `server/llm.py`, `server/kb.py`) is not changed by this addendum except for the rename.
- Priority if time runs short: P0, P1, P2, P3, P8, then P4, P5, P9.

## Interface changes (P0 adds these to plan section 10 before anyone builds)

**New routes (all in `server/routes_data.py`, owner D)**

| Method | Path | Result |
|---|---|---|
| POST | `/api/findings/{finding_id}/file` | Files the finding to the stub once. `{"feedback_number": n, "already_filed": bool, "payload": {...}}`; 403 when `send_to_sf` is off; 404 unknown finding |
| GET | `/api/filed` | `{finding_id: {"feedback_number", "contract_id", "filed_at"}}` |
| GET | `/api/contracts/{contract_id}/sf-requirement` | `text/markdown`: the Feature Requirements document for that contract; 404 unknown |
| GET | `/api/lifecycle` | `{id: {"stage": str, "stages": {name: bool}, "detail": {...}}}` |

**Feedback `content` header** (first lines of `content`, then the existing prose):
```
Pact-Contract: C-01
Requirement: R-01
Finding: F-01
Status: broken since week 4
Type: app_gap
Cost: $15,120/week at risk (demo value)
---
```

**Lifecycle stages, in order:** `drafted`, `approved`, `baselined`, `kept` or `broken`, `renegotiated`.

**New shared folders:** `skills/` and `docs/evidence/` (owner D). New modules `server/sf_export.py`, `server/lifecycle.py` (owner D).

## Gates

| Gate | Produced by | Unblocks | Type | Integrator's check |
|---|---|---|---|---|
| `gate/P0-addendum` | Keshav | Everyone's P tasks | Hard | This addendum committed at `docs/superpowers/plans/2026-11-08-pact-addendum.md`; plan section 10 has the interface changes; WORKFLOW gate table has the P gates; role files point to the addendum |
| `gate/P1-feedback-v2` | AK | P4 (triage skill), P8 drawer | Hard for P4; soft for P8 | `pytest -q` green; `POST /api/findings/F-01/file` twice returns the same number with `already_filed: true` the second time; content starts with the header |
| `gate/P2-req-export` | AK | P8 Requirement view | Hard for P8 view | `pytest -q` green; `curl localhost:8000/api/contracts/C-01/sf-requirement` returns Markdown with every contract field |
| `gate/P3-lifecycle` | AK | P8 lifecycle strip | Hard for P8 strip (mock until then) | `pytest -q` green; with drift on, `/api/lifecycle` shows C-01 at `broken`, and at `renegotiated` after filing F-01 |
| `gate/P4-skills` | AK | Pitch, Devpost | Info | Four `SKILL.md` files with valid front matter; triage skill header matches `build_payload` exactly; Keshav reviewed |
| `gate/P5-persona-run` | AK | Pitch, Devpost | Info | `docs/evidence/persona-review.md` contains a real agent run; the tag message says whether it flagged C-01 (never edit the result) |
| `gate/P8-contract-card` | Keshav | Demo | Hard for the demo | C-01's card shows every stage it has reached; Requirement view downloads Markdown; drawer files once and shows the same FB number on a second click |
| `gate/P9-rename` | Keshav (after each owner's rename lands) | Submission | Hard for submission | `grep -rli -E "fit check|fitcheck" server agents docs tests kb` lists only `agents/WORKFLOW.md` (gate log) |

---

## Task P0 (Keshav, integrator): land the addendum, 15–20 min

**Files:** create `docs/superpowers/plans/2026-11-08-pact-addendum.md` (this file); modify `docs/superpowers/plans/2026-11-08-hackutd-8090-full-plan.md` (section 10: the interface changes above; Owners: D also owns `skills/`, `docs/evidence/`, `server/sf_export.py`, `server/lifecycle.py`), `agents/WORKFLOW.md` (add the P gates), `agents/PROJECT.md` (ownership rows), each `agents/roles/*/CLAUDE.md` + `AGENTS.md` (one line under "Your tasks": "Addendum tasks: see `docs/superpowers/plans/2026-11-08-pact-addendum.md`, your P tasks").

- [ ] Step 1: Copy this file into the repo path above.
- [ ] Step 2: Apply the interface changes to plan section 10 exactly as written above.
- [ ] Step 3: Add the gate table rows to `agents/WORKFLOW.md`.
- [ ] Step 4: Update ownership in `agents/PROJECT.md`. In each `agents/roles/<ROLE>/CLAUDE.md`, insert that role's block from **Appendix A** as a new section directly after the existing "## Your tasks, with gates" section, add `server/sf_export.py`, `server/lifecycle.py`, `skills/**`, `docs/evidence/**`, `tests/test_sf_export.py`, `tests/test_lifecycle.py` to D's "You own" list, then copy each `CLAUDE.md` to `AGENTS.md`.
- [ ] Step 5: Commit `docs: pact addendum (requirements export, feedback triage, lifecycle, skills)`, push `main`, tag `gate/P0-addendum`, post `[interface change] Pact addendum` and `[gate open] P0-addendum`.

---

## Task P1 (AK, D): Feedback item v2, 30 min

**Why:** Triage can parse and link Pact items; no duplicate filings.

**Files:** modify `server/feedback.py`, `server/routes_data.py`, `tests/test_feedback.py`, `tests/test_routes_data.py`.

**Interfaces produced:** `build_payload(finding)` (header added); `parse_header(content) -> dict`; `FILED_PATH = REPO_ROOT / "data" / "filed_feedback.json"` (read at call time); `load_filed() -> dict`; `file_finding(finding) -> dict`; routes `POST /api/findings/{id}/file`, `GET /api/filed`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_feedback.py (additions)
from server.feedback import build_payload, validate_payload, parse_header

F = {"id": "F-01", "contract_id": "C-01", "status": "broken", "first_breach_week": 4, "type": "app_gap",
     "cost_usd_per_week": 15120, "explanation": "x", "requirement_statement": "Prior-auth number in its own field",
     "lineage": {"requirement_id": "R-01", "quote": "q", "interview_id": "INT-01", "timestamp": "14:32", "question_id": "Q-12"}}

def test_content_starts_with_parseable_header():
    p = build_payload(F)
    h = parse_header(p["content"])
    assert h == {"Pact-Contract": "C-01", "Requirement": "R-01", "Finding": "F-01",
                 "Status": "broken since week 4", "Type": "app_gap", "Cost": "$15,120/week at risk (demo value)"}
    assert p["content"].rstrip().endswith("Simulated data.") and validate_payload(p) == []

def test_service_email_is_pact():
    assert build_payload(F)["end_user_email"] == "usage-drift@pact.invalid"
```

```python
# tests/test_routes_data.py (additions). Uses the file's existing `api` fixture (patches settings, simulator,
# drift paths, STATE_DIR and resets rd._stub to 123) and its `_on(**extra)` helper. FILED_PATH is new, so patch it here.
from server import feedback as fb

def test_file_finding_once(api, tmp_path, monkeypatch):
    monkeypatch.setattr(fb, "FILED_PATH", tmp_path / "filed.json")
    _on(send_to_sf=True)
    first = api.post("/api/findings/F-01/file").json()
    second = api.post("/api/findings/F-01/file").json()
    assert first["already_filed"] is False and second["already_filed"] is True
    assert first["feedback_number"] == second["feedback_number"] == 123
    assert api.get("/api/filed").json()["F-01"]["contract_id"] == "C-01"

def test_file_finding_403_when_sending_off(api, tmp_path, monkeypatch):
    monkeypatch.setattr(fb, "FILED_PATH", tmp_path / "filed.json")
    _on()
    assert api.post("/api/findings/F-01/file").status_code == 403
```
The existing `test_sf_payload_and_stub_round_trip` (stub returns 123 then 124) must still pass: the stub route and `file_finding` share one counter helper, and the stub route itself does not deduplicate.

- [ ] **Step 2:** Run: FAIL.
- [ ] **Step 3: Implement.**
  - `SERVICE_EMAIL = "usage-drift@pact.invalid"`. Update the existing test that expects the old address.
  - `build_payload` prepends the header lines (exact keys and order above; `Requirement` from `lineage.requirement_id`, falling back to the contract's requirement ID; `Cost: unknown` when `cost_usd_per_week` is None), then `---`, then the existing prose unchanged. The 20,000-character truncation keeps both the header and the final "Simulated data."
  - `parse_header(content)` reads `Key: value` lines until `---`.
  - `file_finding(finding)`: if the finding ID is in `load_filed()`, return `{"feedback_number": existing, "already_filed": True, "payload": build_payload(finding)}`. Otherwise build and validate the payload, take the next stub number (move the counter logic into one helper used by both the stub route and this function), save `{finding_id: {"feedback_number", "contract_id", "filed_at"}}` to `FILED_PATH`, return `already_filed: False`.
  - Route `POST /api/findings/{id}/file`: 403 when `send_to_sf` is off (same message as `sf-payload`), 404 when unknown, else `file_finding`. Route `GET /api/filed` returns `load_filed()`.
- [ ] **Step 4:** `pytest -q`: PASS. Commit `feat(data): feedback v2 header, file once, pact service email`. Request `gate/P1-feedback-v2`.

## Task P2 (AK, D): Requirements export, 45 min

**Why:** The interview half lands in Software Factory today, as a Markdown requirement doc with the behaviour contract inside.

**Files:** create `server/sf_export.py`, `tests/test_sf_export.py`; modify `server/routes_data.py`.

**Interfaces produced:** `requirement_markdown(contract: dict, finding: dict | None = None) -> str`; route `GET /api/contracts/{contract_id}/sf-requirement` (`text/markdown; charset=utf-8`).

- [ ] **Step 1: Failing tests**

```python
from server.contracts import load_catalog
from server.sf_export import requirement_markdown

C01 = {c["id"]: c for c in load_catalog("contracts/medicare_contracts.json")["contracts"]}["C-01"]

def test_markdown_has_every_contract_field():
    md = requirement_markdown(C01)
    for must in ["# R-01:", C01["requirement"]["statement"], "## Evidence", "## Confidence", "## Behaviour contract",
                 "pa_field_fill_rate", "0.95", "0.05", "Success Metrics", "claim_submitted", "Pact", "Synthetic data"]:
        assert must in md, must
    assert "## Proposed change" not in md

def test_broken_contract_adds_simulated_proposed_change():
    md = requirement_markdown(C01, finding={"id": "F-01", "status": "broken", "first_breach_week": 4, "type": "app_gap",
                                            "explanation": "Clerks type the number in notes again."})
    assert "## Proposed change" in md and "tracked suggestion (simulated)" in md
```

- [ ] **Step 2:** Run: FAIL.
- [ ] **Step 3: Implement** `requirement_markdown` with these sections, in order:
  1. `# <requirement id>: <statement>` and a line `Feature: <feature> · Persona: <role label> · Source: Pact behaviour contract <contract id>`.
  2. `## Requirement`: the statement.
  3. `## Evidence`: one bullet per evidence item: `"<quote>" (<speaker>, <interview_id> <timestamp>, answer to AI question <question_id>)`; omit the question part when `question_id` is null.
  4. `## Confidence`: level, said / did / code as yes/no, the note.
  5. `## Behaviour contract`: the promise (statement), a Markdown table of expectations (metric_id, description, comparator, target, tolerance, unit), the baseline values and note, the events to instrument (`events_required`), the window rules (weekly, min tasks, min people, learning weeks, consecutive breaches), and the line "Monitored version of this requirement's entry in Product Overview › Success Metrics."
  6. `## Proposed change` only when a finding is passed: "Would be proposed as a tracked suggestion (simulated)." plus the finding's status, first breach week, type and explanation, and one suggested requirement edit: for `app_gap`, "The requirement must be completable in the main flow, without opening a secondary tab"; for `know_how_gap`, "The requirement must be discoverable without training"; for `stale_requirement`, "Review whether this requirement still applies".
  7. Footer: "Generated by Pact. Synthetic data. Maps onto your configured Feature Document Template."
  - Route: find the contract in `ct.load_all_contracts()`; if drift is on and a finding exists for it (from `dr.findings(...)`), pass it; return `Response(content=md, media_type="text/markdown; charset=utf-8")`; 404 for unknown IDs.
- [ ] **Step 4:** `pytest -q`: PASS. Commit `feat(data): software factory requirement export`. Request `gate/P2-req-export`.

## Task P3 (AK, D): Contract lifecycle, 30 min

**Why:** One object, one visible story, from interview to Software Factory.

**Files:** create `server/lifecycle.py`, `tests/test_lifecycle.py`; modify `server/routes_data.py`.

**Interfaces produced:** `contract_stages(contracts, drafts, findings, filed, settings, legacy_events, baseline_fn=None) -> dict` (`baseline_fn` defaults to `drift.legacy_baseline`; tests pass a stub); route `GET /api/lifecycle`.

- [ ] **Step 1: Failing tests** (build inputs by hand; no files)

```python
from server.lifecycle import contract_stages

C = {"id": "C-01", "requirement": {"id": "R-01"}, "expectations": [{"metric_id": "pa_field_fill_rate"}]}

def test_full_lifecycle():
    out = contract_stages(
        contracts=[C], drafts=[],
        findings=[{"id": "F-01", "contract_id": "C-01", "status": "broken"}],
        filed={"F-01": {"contract_id": "C-01", "feedback_number": 123}},
        settings={"drift_enabled": True}, legacy_events=[], baseline_fn=lambda c, ev, s: {"pa_field_fill_rate": 0.0})
    s = out["C-01"]
    assert s["stages"] == {"drafted": True, "approved": True, "baselined": True,
                           "kept": False, "broken": True, "renegotiated": True}
    assert s["stage"] == "renegotiated"

def test_drift_off_means_not_watched():
    out = contract_stages(contracts=[C], drafts=[], findings=[], filed={},
                          settings={"drift_enabled": False}, legacy_events=[], baseline_fn=lambda c, ev, s: {})
    assert out["C-01"]["stages"]["kept"] is False and out["C-01"]["stages"]["broken"] is False
    assert out["C-01"]["detail"]["watching"] == "off" and out["C-01"]["stage"] == "approved"

def test_pending_draft_is_only_drafted():
    out = contract_stages(contracts=[], drafts=[{"draft_id": "D-0001", "status": "draft"}], findings=[], filed={},
                          settings={"drift_enabled": True}, legacy_events=[], baseline_fn=lambda c, ev, s: {})
    assert out["D-0001"]["stage"] == "drafted" and out["D-0001"]["stages"]["approved"] is False
```

- [ ] **Step 2:** Run: FAIL.
- [ ] **Step 3: Implement.** For every contract in `contracts` (catalog plus approved drafts):
  - `drafted`: always true (catalog contracts were drafted by hand; approved drafts came from `draft_contracts`).
  - `approved`: true for every contract in `contracts` (pending drafts are not in this list).
  - `baselined`: `baseline_fn(contract, legacy_events, settings)` has at least one non-null value. Default `baseline_fn` is `drift.legacy_baseline`.
  - `kept` / `broken`: only when `settings["drift_enabled"]`: `broken` if a finding for the contract exists, else `kept`. When drift is off both are false and `detail.watching = "off"`.
  - `renegotiated`: a filed entry has `contract_id` equal to the contract's ID.
  - `stage` = the last true stage in the order above (`kept` and `broken` share a position).
  - Pending drafts from `drafts` (status `draft`) are included, keyed by `draft_id`, with only `drafted: true`.
  - Route `GET /api/lifecycle`: gather `ct.load_all_contracts()`, `load_drafts(status="draft")`, `dr.findings(...)` when drift is on, `load_filed()`, settings and `dr.load_legacy_events()`.
- [ ] **Step 4:** `pytest -q`: PASS. Commit `feat(data): contract lifecycle stages`. Request `gate/P3-lifecycle`.

## Task P4 (AK, D): Skills, 40 min

**Why:** 8090's own agents can write, triage and review contracts without our app.

**Files:** create, each with `SKILL.md` and `references/`:
- `skills/behaviour-contract-writing/` (extends Software Factory's Requirements Writing Rules)
- `skills/contract-drift-triage/` (extends Triage Feedback)
- `skills/contract-persona-review/` (pre-launch QA)
- `skills/contract-interview/` (extends the Requirements agent's interview mode)

- [ ] Step 1: For each skill, write front matter (`name`, one-line `description` saying when to use it), then numbered steps, rules, and an output format.
- [ ] Step 2: `references/`: copy `contracts/contract.schema.json`; write `examples.md` (C-01 to C-05 as contract sections, same layout as P2's "Behaviour contract" section); write `anti-patterns.md` (numbers invented in the interview, no tolerance, free-text events, findings without a contract ID or quote).
- [ ] Step 3: **Triage skill specifics:** recognise items whose `content` starts with `Pact-Contract:`; read the header exactly as P1 defines it; link the item to the Feature Requirement named in `Requirement:`; name the Theme after the broken promise (the requirement statement); by `Type:` choose a Work Order (`app_gap`, `know_how_gap`) or a requirement change (`stale_requirement`); set priority from `Cost:`; never create a second Theme for the same `Pact-Contract`.
- [ ] Step 4: **Persona review skill specifics:** `references/persona-billing-clerk.md` built only from `legacy/scripts/billing_clerk_2.md`, `kb/people.json` and contracts C-01, C-03, C-04 (goals, daily volume, habits, workarounds, her own quotes, where her patience runs out). Steps: read the Feature Requirements docs with their behaviour contracts; for each contract, walk the task as her through the UI code (and in a browser if available); report every place the build would break a contract or force the old workaround. Output table: contract ID, what she'd hit, her supporting quote, severity, suggested fix. Rules: no finding without a contract ID or quote; separate "breaks a contract" from "preference"; never change code.
- [ ] Step 5: **Interview skill specifics:** how to fill contract slots in an interview: prefer questions about rules in the legacy code that haven't come up; ask for quantities and compare them with legacy log facts; one question at a time, at most 15 words; record each answer against a contract slot with its quote.
- [ ] Step 6: Ask Keshav to review; commit `docs(skills): pact skills for requirements, triage, persona review, interview`. Request `gate/P4-skills`.

## Task P5 (AK, D): One real persona review run, 15 min

**Why:** Evidence for the pitch that contracts catch problems before launch.

**Files:** create `docs/evidence/persona-review.md`.

- [ ] Step 1: In a fresh Claude Code session in a checkout of `main` that includes P4, say: "Use the skill in `skills/contract-persona-review` to review `server/static/claim.html` and `server/static/claim.js` against contracts C-01, C-03 and C-04. Write your report as the table the skill specifies."
- [ ] Step 2: Paste the full output into `docs/evidence/persona-review.md` with the date, model and the exact prompt. **Do not edit the findings.** If it did not flag the C-01 second-tab problem, say so in the file and in the tag message.
- [ ] Step 3: Commit `docs(evidence): persona review run`. Request `gate/P5-persona-run`.

## Task P8 (Keshav, W): Contract card, Requirement view, drawer filing, 45–60 min

**Why:** The judges see one contract's whole story and both Software Factory landings.

**Files:** modify `server/static/board.html`, `server/static/board.js`, `server/static/board.css`; create `server/static/mock/lifecycle.json`, `server/static/mock/sf-file.json`, `server/static/mock/sf-requirement.md`.

**Builds on what's already merged:** `renderContracts(data)` in `board.js` (about line 520) draws the Contracts view; the drafts UI (`renderDrafts`, about line 65) stays as it is; the Software Factory drawer (`#sf-drawer`) loads the payload from `GET /api/findings/{id}/sf-payload` and its "File" button (`#sf-file`, click handler about line 701) currently POSTs that payload straight to `/stub/v2/reporting-api/feedback`, with `mock/sf-reply.json` in mock mode.

- [ ] Step 1: **Contract card** (extend `renderContracts`): one card per contract with a stage strip (drafted, approved, baselined, kept or broken, renegotiated) from `GET /api/lifecycle`, reached stages filled in the accent colour, the current stage labelled. Keep the existing quotes, said/did/code chips, target ± tolerance. Until `gate/P3-lifecycle`, read `mock/lifecycle.json` (C-01 at `renegotiated`, others at `kept`).
- [ ] Step 2: **Requirement view** on each card: fetch `GET /api/contracts/{id}/sf-requirement` (mock: `mock/sf-requirement.md`, a copy of the C-01 output once P2 lands, or a hand-written sample before), show it in a panel, with **Download (.md)** (filename `<requirement id>-<contract id>.md`) and **Copy** buttons (wrap the clipboard call in try/catch). Label: "Software Factory Feature Requirements document. Add it to your project."
- [ ] Step 3: **Drawer filing** (change the existing `#sf-file` click handler only): replace the POST to `/stub/v2/reporting-api/feedback` with `POST /api/findings/{id}/file` (no body) for the finding the drawer was opened for; in mock mode read `mock/sf-file.json` (`{"feedback_number": 123, "already_filed": false, "payload": {...}}`). Show `FB-<number> filed · Simulated, no live connection`, or `Already filed as FB-<number>` when `already_filed` is true. Keep the Payload tab loading from `sf-payload` (after P1 it includes the header). The existing disabled state when `send_to_sf` is off stays.
- [ ] Step 4: `node --check server/static/board.js`; manual check against the gate list. Commit `feat(web): contract card lifecycle, requirement export view, file-once drawer`. Request `gate/P8-contract-card`.

## Task P9 (everyone, Keshav last): Rename Fit Check to Pact, 15 min total

**Why:** One name everywhere.

Each owner renames in their own files only:
- **Prakrit:** `server/routes_engine.py`, `server/tts.py`, `server/llm.py`, `server/app.py`. Text only; no behaviour change.
- **AK:** `server/feedback.py` (service email, done in P1), `tests/test_feedback.py`.
- **Hrishi:** `server/static/interviewer.html`, `server/static/interviewer.js`. Text only.
- **Keshav:** `server/static/board.html`, `claim.html`, `terms.html`, `privacy.html`, `agents/` files, both plan files. Historical Gate log lines in `agents/WORKFLOW.md` stay as written.
- [ ] Each owner: `pytest -q` (and `node --check` for JS) still green; commit `chore: rename Fit Check to Pact (<role>)`; request merge with title `[P9-rename] <role>`.
- [ ] Keshav, after all four merges: `grep -rli -E "fit check|fitcheck" server agents docs tests kb` lists only `agents/WORKFLOW.md`. Tag `gate/P9-rename`.
- Known exception (2026-11-08): the internal browser storage keys `fitcheck.admin_token` and `fitcheck.queue.*`, and the docs that name them, keep the old name on purpose. See the P9 note under the Gate log in `agents/WORKFLOW.md`.

---

## Demo changes (plan section 12)

- Contracts view: C-01's card shows its stages; open its **Requirement view**, show the Markdown, click Download. Line: "This is a Software Factory requirement document you could add to a project today."
- Drift: C-01 **broken**; the drawer files it once (`FB-123`, then "Already filed"); the card moves to **renegotiated**. Line: "A pact lands in Software Factory twice: in the requirement when it's written, and in Feedback triage when it's broken."
- Slide: the four skills, and the persona review result from `docs/evidence/persona-review.md` (only what it actually found).

## Self-review

- Every final requirement has a task: 1–2 (P1), 3 (P2), 4 (P3, P8), 5 (P8), 6 (P4), 7 (P5), 8 (P9, P1), 9 (all tasks run `pytest -q`).
- Names are used consistently: `parse_header`, `file_finding`, `load_filed`, `FILED_PATH`, `requirement_markdown`, `contract_stages`; routes `/api/findings/{id}/file`, `/api/filed`, `/api/contracts/{id}/sf-requirement`, `/api/lifecycle`; header keys `Pact-Contract`, `Requirement`, `Finding`, `Status`, `Type`, `Cost`; stages `drafted`, `approved`, `baselined`, `kept`, `broken`, `renegotiated`.
- No existing interface is removed: `sf-payload` and the stub route stay; P8 only changes which route the drawer button calls.
- The interview engine is untouched apart from rename text, so the live interview demo carries no new risk.
- Assumption to check during build: `tests/test_routes_data.py` has a reusable drift-on client fixture (P1 adapts to whatever it has).

---

## Appendix A: role-file sections (P0 pastes these into each role file)

Each block goes into `agents/roles/<ROLE>/CLAUDE.md` directly after "## Your tasks, with gates", then `CLAUDE.md` is copied to `AGENTS.md`. They use the same table format, gate commands and stop rules as the original tasks.

### For `agents/roles/C/CLAUDE.md` (Hrishi)

```markdown
## Addendum tasks (Pact), with gates

Read `docs/superpowers/plans/2026-11-08-pact-addendum.md` first. Your only addendum task is the rename.

| Task | Needs before starting | Allowed while waiting | When done, request |
|---|---|---|---|
| P9 Rename "Fit Check" to "Pact" in `server/static/interviewer.html` and `server/static/interviewer.js` (text only, no behaviour change) | `gate/P0-addendum` | none | PR titled `[P9-rename] C`; chat `[gate request] P9-rename C` |

Run `node --check server/static/interviewer.js` and `pytest -q` before the PR. After P9, keep the demo laptop ready: after each new gate, pull `main` there, restart the server, and re-run the glasses tap test.
```

### For `agents/roles/E/CLAUDE.md` (Prakrit)

```markdown
## Addendum tasks (Pact), with gates

Read `docs/superpowers/plans/2026-11-08-pact-addendum.md` first. Your only addendum task is the rename. The interview engine must not change behaviour.

| Task | Needs before starting | Allowed while waiting | When done, request |
|---|---|---|---|
| P9 Rename "Fit Check" to "Pact" in `server/routes_engine.py`, `server/tts.py`, `server/llm.py`, `server/app.py` (text only, no behaviour change) | `gate/P0-addendum` | none | PR titled `[P9-rename] E`; chat `[gate request] P9-rename E` |

Run `pytest -q` before the PR. After P9, you're free for fix requests and rehearsals.
```

### For `agents/roles/D/CLAUDE.md` (AK)

```markdown
## Addendum tasks (Pact), with gates

Read `docs/superpowers/plans/2026-11-08-pact-addendum.md` first; it has the exact tests and code shapes. Do these in order.

| Task | Needs before starting | Allowed while waiting | When done, request |
|---|---|---|---|
| P1 Feedback v2: header, `parse_header`, file once (`file_finding`, `FILED_PATH`), `POST /api/findings/{id}/file`, `GET /api/filed`, service email `usage-drift@pact.invalid` (your P9 part) | `gate/P0-addendum` | none | `gate/P1-feedback-v2` |
| P2 Requirements export: `server/sf_export.py`, `GET /api/contracts/{id}/sf-requirement` | `gate/P0-addendum` | none | `gate/P2-req-export` |
| P3 Lifecycle: `server/lifecycle.py`, `GET /api/lifecycle` | Your own P1 (same branch) | none | `gate/P3-lifecycle` |
| P4 Four skills in `skills/` | Triage skill: your own P1 header is final (same branch) | Contract-writing, persona-review and interview skills | `gate/P4-skills` (ask Keshav to review) |
| P5 One real persona-review run into `docs/evidence/persona-review.md` | **`gate/P4-skills` (hard)**: run it from a fresh checkout of `main` that includes the skill | none | `gate/P5-persona-run` (tag message says whether C-01 was flagged) |

Keshav's P8 waits on your P2 and P3, so request those gates as soon as each is green. Never edit the persona run's findings.
```

### For `agents/roles/W/CLAUDE.md` (Keshav)

```markdown
## Addendum tasks (Pact), with gates

Read `docs/superpowers/plans/2026-11-08-pact-addendum.md` first. You land it (P0), build P8, and close the rename (P9).

| Task | Needs before starting | Allowed while waiting | When done, request |
|---|---|---|---|
| P0 Land the addendum on `main`: plan section 10 interface changes, P gates in `agents/WORKFLOW.md`, ownership in `agents/PROJECT.md`, Appendix A sections in every role file | none | none | You tag `gate/P0-addendum` (with your human's yes) |
| P8 Step 1 Contract card lifecycle strip (extend `renderContracts`) | Live data: **`gate/P3-lifecycle` (hard)** | Build against `mock/lifecycle.json` | (with Step 3) |
| P8 Step 2 Requirement view (Download / Copy) | Live data: **`gate/P2-req-export` (hard)** | Build against `mock/sf-requirement.md` | (with Step 3) |
| P8 Step 3 Drawer files through `POST /api/findings/{id}/file` | Live data: `gate/P1-feedback-v2` (soft) | Build against `mock/sf-file.json` | `gate/P8-contract-card` |
| P9 Rename in `board.html`, `claim.html`, `terms.html`, `privacy.html`, `agents/`, both plans; then the final grep | Your part: `gate/P0-addendum`. Final tag: all four `[P9-rename]` merges | Your own files | You tag `gate/P9-rename` |

Keep clearing gate requests with the WORKFLOW.md section 2 protocol. Never push `main` or a tag without your human's yes.
```
