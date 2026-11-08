# Role D: Data (legacy company, simulator, drift detector, Software Factory stub, eval)

You are the coding agent for **role D** on team Fit Check (HackUTD 2026, 8090 track). Claude Code reads this as `CLAUDE.md` and Codex reads it as `AGENTS.md`; the text is the same. Your human is the D person. Your first deliverable unblocks E at 1:30, so ship the JSON files first.

## Read first, in this order

1. `agents/PROJECT.md`: what we're building, final decisions, glossary, file ownership, rules.
2. `agents/WORKFLOW.md`: branches, gates, how to wait for and request a gate.
3. The plan, `docs/superpowers/plans/2026-11-08-hackutd-8090-full-plan.md`: Global Constraints; sections 6, 7, 8 (all), 9 (the Software Factory drawer and payload), 10.2, 10.4, 11; and your tasks **D1–D4**, which give the exact code and tests.
4. `contracts/contract.schema.json`, `contracts/medicare_contracts.json`, `contracts/README.md`.

## Your job

You build the legacy "company in a box":

- the COBOL claims program with 7 planted rules, the partly wrong 2009 manual, the answer key and the role-play scripts;
- the contracts loader;
- the seeded simulator with the planted C-01 drift and the C-02 decoy;
- the drift detector and findings (opt-in aware);
- the Software Factory Feedback payload and local stub;
- the eval that scores the agent against the answer key.

- **Branch:** `data`
- **You own (only edit these):** `legacy/**`, `kb/rules.json`, `kb/doc_diffs.json`, `kb/log_facts.json`, `server/routes_data.py` (after E1 creates it), `server/contracts.py`, `server/simulate.py`, `server/drift.py`, `server/feedback.py`, `tests/test_contracts.py`, `tests/test_simulate.py`, `tests/test_drift.py`, `tests/test_feedback.py`, `tests/fixtures/state_sample.json`.
- **Never edit:** `server/app.py`, `server/routes_engine.py`, `server/routes_web.py`, `server/settings.py`, `server/static/*`, `kb/slots.json`, `kb/people.json`, `kb/question_bank.json`, `contracts/`, `agents/`, the plan.

## Setup on this laptop (once)

```bash
cp .env.example .env               # tokens from the team chat (ADMIN_TOKEN is used by /api/simulate)
pip install -r server/requirements.txt
git checkout -b data
```

## Your tasks, with gates

| Task | Time | Needs before starting | Allowed while waiting | When done, request |
|---|---|---|---|---|
| D1 Answer key, `kb/rules.json`, `kb/doc_diffs.json`, then COBOL, manual, scripts | 0:30–1:30 | `gate/G0-bootstrap` | none | `gate/D1-legacy` **as soon as the three JSON files are done** (E2 waits on them). Finish the COBOL, manual and scripts right after, in the same branch |
| D2 Contracts loader + simulator | 1:30–2:30 | Loader and simulator: nothing. `POST /api/simulate` route: **`gate/E1-server` (hard)**, because it needs `server/routes_data.py` | Loader, simulator, their tests, data generation | `gate/D2-sim` |
| D3 Drift detector + findings + `/api/drift`, `/api/findings` | 2:30–4:00 | Your own D2 work (same branch). `server.settings` from `gate/E1-server` (open by then). Live events from `gate/W2-events` (soft; works without them) | none | `gate/D3-drift` |
| D4 Software Factory payload + stub + eval | 4:00–5:00 | Your own D3 work. Eval over saved interviews: `gate/E4-lineage` (soft; until then use a hand-written `tests/fixtures/state_sample.json`) | Payload, stub, eval against the fixture | `gate/D4-sf` |
| Fix list, rehearsals | 5:00–6:45 | `gate/CP3`, then `gate/FREEZE` | none | none |

Check a gate:
```bash
git fetch origin --tags
git rev-parse -q --verify "refs/tags/gate/E1-server" >/dev/null && echo READY || echo NOT_READY
```
If it prints `NOT_READY`, stop and tell your human: `[blocked] D waiting on gate/E1-server (owner E)`. Then do only the allowed pre-work. If it prints `READY`, run `git merge origin/main`, then `pytest -q`, then continue.

## Task notes beyond the plan

- **D1, order matters.** Write `legacy/answer_key.json` first, exactly as in the plan. Then derive `kb/rules.json` and `kb/doc_diffs.json` without the `hidden` and `truth` fields, adding each rule's COBOL paragraph name as its code location. Push and request `gate/D1-legacy`. The integrator checks with `grep -c -E '"hidden"|"truth"'`, which must print 0.
    - The COBOL doesn't need to compile. Every rule paragraph needs a `*> RULE <ID>` comment so the agent and the eval can point at it.
    - Scripts: billing clerk 2 forgets RETRO-ELIG unless asked; only billing clerk 1 knows PAYER-TX017; X-1 belongs to billing clerk 1; X-2 sits between the two clerks.
- **D2, the simulator.** It must match the plan's numbers exactly:
    - `DEFAULT_SCENARIO`, about 60 claims per clerk per week, 35% of them needing prior auth;
    - about 5 `coverage_changed` events per clerk per week, all with `after_date_of_service: true`;
    - 6% of claims reopened at least twice;
    - at least 10 `ui_click` events per denial specialist per week on `denials_list`;
    - `week` from −12 to −1 for legacy and 1 to 8 after launch;
    - `actor_hash = sha1(f"{seed}-{role}-{i}")[:10]`.

  Every event has exactly the envelope keys in the plan test, and no free text anywhere. `python -m server.simulate --seed 7` writes `data/legacy_events.jsonl`, `data/post_events.jsonl` and `kb/log_facts.json`.
- **D3, the rules.** Follow plan section 8.3 and D3 Step 3 literally. The state order is suppressed, then learning, then ok, breach or broken; the worst expectation sets the week. People per week means distinct `actor_hash` of the role with any event that week.
    - `findings()` returns `[]` when drift is off, skips unwatched contracts, and marks `detector_rate` values `None` when `notes_matching` is off.
    - Read live events from `settings.LIVE_EVENTS_PATH` at call time.
    - The tests pin C-01 broken from week 4, the C-02 week-5 breach not counting as drift, C-03/C-04/C-05 holding, and the privacy floor.
- **D3, blind test.** You may write `data/scenario.json` (gitignored) with a different seed or drift for the blind check in the plan's test table. Don't tell the tester which contracts you planted until after the run.
- **D4.** The payload has only `end_user_email` (`usage-drift@fitcheck.invalid`) and `content`, ending with "Simulated data." The stub returns `{"feedback_number": n}` counting from 123, or 422 with the errors. The payload route returns 403 when `send_to_sf` is false.
- **Routes** go only in `server/routes_data.py`: `POST /api/simulate` (401 without `X-Admin-Token`), `GET /api/drift`, `GET /api/findings`, `GET /api/findings/{id}/sf-payload`, `POST /stub/v2/reporting-api/feedback`, `GET /api/eval`.

## Interfaces you produce (frozen; plan section 10)

- `server.contracts`: `load_catalog(path)`, `validate_contract(contract)`.
- `server.simulate`: `DEFAULT_SCENARIO`, `generate(seed, scenario)`.
- `server.drift`: `weekly_metrics(contract, events, settings)`, `evaluate(contract, weekly)`, `findings(contracts, events, settings)`. Finding objects shaped as plan 8.4.
- `server.feedback`: `build_payload(finding)`, `validate_payload(body)`.
- Files: `kb/rules.json`, `kb/doc_diffs.json`, `kb/log_facts.json`, `legacy/answer_key.json`.

## Interfaces you consume

- From E (gate E1-server): `server.settings.load_settings`, `LIVE_EVENTS_PATH`; `server/routes_data.py` (empty router).
- From E (gate E4-lineage, soft): `data/state/*.json` interview states for the eval.

## How you test

`pytest -q` with the tests the plan gives for D2–D4. Write each test first, see it fail, implement, see it pass. Noise matters: the planted values were chosen so seed 7 passes reliably. If a test fails only because of sampling noise, tell your human. Don't silently change the planted numbers; they appear in the pitch.

## Committing and asking for a gate

Commit small and often on `data` (`feat(data): ...`). When a task is done, follow `agents/WORKFLOW.md` section 1: merge `origin/main`, `pytest -q`, push, open a PR titled `[gate <name>] ...`, and post `[gate request] ...` in the chat. Never push to `main`, never force-push, never commit `.env`, `data/`, `CLAUDE.md` or `AGENTS.md`.

## Stop and ask your human when

- a hard gate is missing;
- a planted number would have to change;
- you'd need to edit a file you don't own or add a dependency;
- or an interface in section 10 seems wrong.

## Report at the end of every task

What you built, test results, which gate to request, what's blocked and on whom, and the next task.
