# Fit Check: parallel workflow, branches and gates

Four people work in parallel on four branches: Hrishi (C), Prakrit (E), AK (D) and Keshav (W). Dependencies between them are handled with **gates**. A gate is a git tag `gate/<name>` on `main`. Only the integrator (Keshav, W) creates gate tags, and only after merging the producing branch, running every test and doing the manual check listed below. An agent that needs a gate checks for the tag. If the tag isn't there, the agent stops and waits for its human.

## Branches

| Branch | Owner | Starts from |
|---|---|---|
| `main` | Keshav (W, integrator) only | Bootstrap commit, tag `gate/G0-bootstrap` |
| `client` | Hrishi (C) | `main` at `gate/G0-bootstrap` |
| `engine` | Prakrit (E) | `main` at `gate/G0-bootstrap` |
| `data` | AK (D) | `main` at `gate/G0-bootstrap` |
| `web` | Keshav (W) | `main` at `gate/G0-bootstrap` |

Nobody pushes to `main` except the integrator. Nobody force-pushes. Tags are never moved or deleted.

## Gate table

**Hard** means you may not start the dependent step until the gate exists. **Soft** means you may build against mocks or fakes first, but you must switch to the real thing, and retest, once the gate exists.

| Gate tag | Produced by | Expected | Unblocks | Type | Integrator's check before tagging |
|---|---|---|---|---|---|
| `gate/G0-bootstrap` | Integrator | Before 0:00 | Everyone cloning and branching | Hard | `agents/`, `contracts/`, plan, `.gitignore`, `.env.example`, `server/requirements.txt`, `server/static/.gitkeep` present on `main` |
| `gate/T0-schema` | Task 0 (all) | 0:30 | E3 using the schemas as written | Soft | One real Haiku call with each schema in plan 10.3 returned valid JSON; result written in the Gate log below (if type arrays were rejected, plan 10.3 updated to `anyOf` first) |
| `gate/E1-server` | E (E1) | 1:30 | C2 socket test; W2 events API (needs `server/settings.py` and `routes_web.py`); D2 `/api/simulate` route (needs `routes_data.py`); C4 settings panel (needs `/api/settings`) | Hard for those steps | `pytest -q` green; `uvicorn server.app:app --host 127.0.0.1 --port 8000` starts; `curl -s localhost:8000/api/settings` shows `"drift_enabled": false` |
| `gate/D1-legacy` | D (D1) | 1:30 | E2 rule catalogue, bank questions for rules, brief | Hard for E2 Steps 3–4 | `legacy/answer_key.json` has 7 rules, 2 contradictions, 2 doc diffs; `grep -c -E '"hidden"|"truth"' kb/rules.json kb/doc_diffs.json` prints 0 for both files |
| `gate/C1-devices` | C (C1) | 1:30 | Information for everyone (fallback decision) | Info | `docs/DEVICE_TESTS.md` has T1–T4 results; the tag message says `PASS` or `FAIL: <which>` |
| `gate/E2-kb` | E (E2) | 2:30 | E3 engine (loads `kb/people.json`, `kb/slots.json`, bank); E4 pre-voicing | Hard for E3, E4 | `pytest tests/test_kb.py -q` green; brief token estimate under 20k recorded in the PR |
| `gate/D2-sim` | D (D2) | 2:30 | E4 contract evidence merge (needs `server/contracts.py`); D3 | Hard for E4 Step 4 | `pytest tests/test_contracts.py tests/test_simulate.py -q` green; `python -m server.simulate --seed 7` writes `data/post_events.jsonl` |
| `gate/W2-events` | W (W2) | 2:30 | D3 reading live events (soft); demo judge clicks | Soft | `pytest tests/test_events.py -q` green; `/claim` loads and shows "Usage monitoring is off" with default settings |
| `gate/CP1` | Integrator | 2:30 | Checkpoint 1 | Checkpoint | Live: speak on `/interviewer` → fake queue arrives → glasses tap → voice in glasses → `played` in server log |
| `gate/E3-engine` | E (E3) | 4:00 | W3 Interview view on live data; C3 against the real engine | Soft (W3, C3 use mocks or the fake queue until then) | `pytest -q` green; live: a real Haiku question within 3 s of a spoken sentence; server log shows `cache_read_input_tokens > 0` on both call types |
| `gate/D3-drift` | D (D3) | 4:00 | W4 Drift view and Finding detail on live data; D4 | Soft for W4 (mocks until then) | `pytest tests/test_drift.py -q` green; with drift switched on, `curl -s localhost:8000/api/findings` returns F-01 with status `broken` |
| `gate/C3-client` | C (C3) | 4:00 | Checkpoint 2 | Hard for CP2 | Manual: single/double/triple tap behave as specified against the real engine; freshness gate waits ≤ 1 s |
| `gate/W3-views` | W (W3) | 4:00 | Checkpoint 2 | Hard for CP2 | Board Interview view updates live during a 1-minute test interview |
| `gate/CP2` | Integrator | 4:00 | Checkpoint 2 | Checkpoint | Real questions in the ear; drift findings visible on the board |
| `gate/E4-lineage` | E (E4) | 5:00 | Checkpoint 3 | Hard for CP3 | At least 40 clips in `data/clips/`; `/api/contracts` evidence validates (test green) |
| `gate/D4-sf` | D (D4) | 5:00 | W4 drawer button against the real stub | Soft for W4 | `pytest tests/test_feedback.py -q` green; `curl -s -X POST localhost:8000/stub/v2/reporting-api/feedback -H 'content-type: application/json' -d '{"end_user_email":"a@b.c","content":"x"}'` returns `{"feedback_number": 123}` |
| `gate/C4-settings` | C (C4) | 5:00 | Checkpoint 3 | Hard for CP3 | Toggling drift in `/board#settings` changes `curl localhost:8000/api/settings` and adds an audit entry |
| `gate/W4-views` | W (W4) | 5:00 | Checkpoint 3 | Hard for CP3 | Drift view shows C-01 broken and the C-02 "single-week spike" note; drawer shows FB-123 from the stub |
| `gate/D5-drafts` | D (D5) | About 2 h after D5 starts | W5 on live data; CP3 | Soft for W5, hard for CP3 | `pytest -q` green; plan D5 Step 7 live check: the INT-09 fixture produces at least one schema-valid contract (Friday claims export, `baseline_value` near 1.0, `confidence.did` true) and at least one open loop (payer calls), and C-01 is not drafted again; after approval, `/api/contracts` includes C-06 and `/api/drift` (drift on) lists it holding; saving an empty watched list excludes it and selecting C-06 again restores it |
| `gate/W5-drafts-ui` | W (W5) | After W4 | CP3 | Hard for CP3 | On the board, "Draft contracts" for INT-01 shows draft cards (quotes, Q badges, said-vs-did line), the open loop with its event to instrument, and the dropped list; Approve adds C-06 to the contracts list and the Drift view |
| `gate/CP3` | Integrator | 5:00 | Full integration | Checkpoint | Full demo script once start to finish, including drafting and approving a contract from the interview; `tap_to_audio_ms` < 500; sentence-to-queue < 3,000 ms; `pytest -q` green |
| `gate/FREEZE` | Integrator | 5:30 | Fixes only from here | Checkpoint | Announced in chat; after this only fix commits are merged |
| `gate/RC` | Integrator | 6:45 | Submission | Checkpoint | Second rehearsal recorded; README and Devpost text done |

## How work flows

```
owner: task done → tests green → merge origin/main → tests green → push branch → open PR "[gate X] ..."
integrator: merge into main locally → pytest -q → manual check → push main → tag gate/X → push tag → post in chat
waiting agent: git fetch --tags → tag exists? → merge origin/main into own branch → continue
```

### 1. Owner: asking for a gate

```bash
pytest -q                                   # your tests green
git fetch origin && git merge origin/main   # bring in everything already merged
pytest -q                                   # still green after the merge
git push -u origin <branch>
gh pr create --base main --head <branch> --title "[gate E1-server] Server skeleton, route files, settings, websocket" \
  --body "Tests: pytest -q -> N passed. Manual check: <what you ran and saw>. Gate requested: gate/E1-server"
```
Then post in the team chat: `[gate request] E1-server, PR #<n>, pytest N passed`.

If `gh` isn't set up, push the branch and post the same message with the branch name and commit hash (`git rev-parse --short HEAD`).

### 2. Integrator: clearing a gate

```bash
git checkout main && git pull
git merge --no-ff origin/<branch> -m "merge <branch>: gate <name>"
pytest -q                                   # must be green on the merged result
# run the manual check from the gate table
git push origin main
git tag -a gate/<name> -m "<name>: <one line, PASS/FAIL for info gates>"
git push origin gate/<name>
```
Then record it in the Gate log below (commit to `main`) and post `[gate open] <name>` in the chat.

If the tests or the check fail: don't push `main`. Run `git reset --hard origin/main` locally (this only discards the local merge), and tell the owner what failed.

If a merge conflicts, the owner resolves it on their branch (`git merge origin/main`, fix, test, push), not the integrator on `main`. Conflicts should be rare, because every file has one owner and `server/app.py` is only touched by E.

### 3. Waiting agent: checking a gate

```bash
git fetch origin --tags
git rev-parse -q --verify "refs/tags/gate/E1-server" >/dev/null && echo READY || echo NOT_READY
```
- `READY`: run `git merge origin/main` into your branch, run `pytest -q`, then continue.
- `NOT_READY`: stop. Tell your human: "Blocked on gate/E1-server (owner E). I can do <allowed pre-work> meanwhile." Do only that pre-work. Never invent the missing module, and never copy another owner's code into your branch.

## Interfaces are frozen

The names, paths, message shapes and schemas in plan section 10 are a contract between branches. Building against them is what lets four people work at once. A change goes through the integrator:
1. The person who needs it tells the integrator.
2. The integrator edits plan section 10 on `main`, tags nothing, and posts `[interface change] <what>` in the chat.
3. Every affected owner merges `origin/main`.

## Shared files (integrator edits only)

`.gitignore`, `.env.example`, `server/requirements.txt`, `contracts/`, `agents/`, `docs/superpowers/plans/`. Ask in the chat if you need a change.

## Secrets

The integrator generates `CLIENT_WRITE_TOKEN` and `ADMIN_TOKEN` once (`python -c "import secrets; print(secrets.token_hex(16))"`) and shares them, with the Anthropic and ElevenLabs keys, in the team chat. Not in the repo. Everyone puts them in their own `.env`.

## Chat message formats

| When | Message |
|---|---|
| Asking for a gate | `[gate request] <name>, PR #<n> (or branch@sha), pytest <N> passed` |
| Gate cleared | `[gate open] <name>` |
| Gate failed | `[gate failed] <name>: <what failed>` |
| Blocked | `[blocked] <role> waiting on gate/<name> (owner <role>)` |
| Interface change | `[interface change] <section 10.x>: <what changed>` |

## Gate log

The integrator appends one line per gate: time, tag, commit, check result.

| Time | Tag | Commit | Result |
|---|---|---|---|
| 2026-11-08, before 0:00 | gate/G0-bootstrap | d8963fb | Pushed with plan, contracts, agents/, .gitignore, .env.example, requirements (pushed from AK's laptop before roles were assigned) |
| 2026-11-08 04:44 CST | gate/D1-legacy | e5dbb1c | PR #1 merged; tag pushed. PASS: answer key has 7 rules, 2 contradictions, 2 doc diffs; hidden/truth matches 0 in both public KB files. pytest -q: no tests collected (no test suite in this revision). |
| 2026-11-08 05:07 CST | gate/C1-devices | e557afe | PR #2 merged. PASS: T1-T4 operator-reported by Hrishi; original T2 failure and successful retry documented. node --check and diff checks passed. pytest -q collected no tests; Keshav explicitly waived the empty-suite requirement for C1 in this session before authorizing merge, main push, and gate publication. |
| 2026-11-08 05:13 CST | gate/E1-server | 5ccc903 | PASS on local PR #3 merge: pytest -q 36 passed; uvicorn bound to 127.0.0.1:8000; GET /api/settings returned drift_enabled=false. |
| 2026-11-08 05:13 CST | gate/E2-kb | 5ccc903 | PASS on local PR #3 merge: all 11 KB tests passed within 36-test suite; 50 bank questions; brief token estimates 3238 / 3245 / 1546, all below 20000. E3 live check and tag remain pending separately. |
| 2026-11-08 05:26 CST | gate/W2-events | b53f65f | PR #5 local merge PASS: pytest -q 58 passed (22 W2 cases); JS syntax checks passed. Headless Chrome: /claim renders Usage monitoring is off and sends zero events; enabled submission stores flags/tags without raw patient, notes or authorization values; layouts fit at 1280px and 390px. |
| 2026-11-08 05:53 CST | gate/E3-engine | 88280f2 | PR #6 local merge PASS: 67 tests. Independent real-Haiku check of 23b31eb: sentence-to-queue 1837 ms (including API retry) and 1152 ms; questions cache_read 6108 and bookkeeping cache_read 6341. Both schemas accepted as written. Earlier 3027 ms failure remains superseded by the latency fix and passing rerun. E4 gate not opened. |
| 2026-11-08 06:02 CST | gate/W3-views | cd34688 | PR #9 local merge PASS: 67 tests; JS syntax; five mock contracts schema-valid. One-minute Chrome/live-Haiku interview: three synthetic answers, queues and played markers updated, two slots filled, one from an AI-selected question. Mock polling updates within 2 s; safe quote rendering; lineage links; 1280/390px layout checks passed. Fake bookkeeping has no fills, so attribution was tested using real Haiku. Live contract-evidence merge recheck remains pending E4-lineage. |
| 2026-11-08 06:16 CST | gate/D2-sim | 0500120 | PR #4 local merge PASS: 104 tests; CLI seed 7 generated 14866 legacy and 10992 post-launch events and post_events.jsonl in an isolated checkout. |
| 2026-11-08 06:16 CST | gate/D3-drift | 0500120 | PR #4 local merge PASS: 104 tests; real localhost HTTP findings returns F-01 broken from week 4; C-02 week-5 breach is isolated and holding; C-03/C-04/C-05 holding. Default drift-off routes return disabled/empty. |
| 2026-11-08 06:16 CST | gate/D4-sf | 0500120 | PR #4 local merge PASS: documented feedback request returns feedback_number 123; actual F-01 payload validates and round-trips as 124. Sending is tested against the local stub only. |
| 2026-11-08 06:16 CST | C2 integration (PR #7; no gate) | f1da170 | PASS: combined merge 104 tests; JS syntax; Chrome with mocked recognition and real HTTP/WebSocket verifies buffered finals, fresh fake queue, playback suppression, reconnect exactly once, and recognition restart. Physical speech PASS is Hrishi-reported. CP1 glasses/voice check remains pending. |
| 2026-11-08 06:45 CST | Plan integration (PR #8; no gate) | 917bcbd | Corrected W1 heading and four-union drafting schema; schema equals implementation; added approved-catalog/watch-control owner handoff and INT-02 rehearsal note. Adds D5/W5 and CP3 drafting requirements. |
| 2026-11-08 06:45 CST | gate/D5-drafts | 5ff47e1 | PR #10 local merge plus explicitly authorized D/E integration fixes PASS: 127 tests. Independent real-Haiku INT-09 run in 8.28 s: Friday contract schema-valid, baseline 1.0208, did=true; payer-call open loop; covered C-01 draft rejected. Approval assigns C-06/R-07, appears in catalog and holds in drift; explicit empty watch list and reselect respected; approval preserves monitoring-off defaults. Synthetic test storage removed. |
| 2026-11-08 06:53 CST | gate/C3-client | 5d301ea | PR #11 combined merge: 127 tests and JS syntax pass. Chrome with mocked speech/audio and real HTTP/WebSocket verifies top/second-current/repeat selection, pushed-clip preference, speech fallback and saved played order. Fresh queue releases wait at 201 ms; configured 1000 ms stale deadline observed 1007.6 ms including browser scheduling. Physical real-engine speech/glasses/repeat/freshness PASS is Hrishi-reported with server-state corroboration in DEVICE_TESTS.md. CP1 is not tagged by this review. |
