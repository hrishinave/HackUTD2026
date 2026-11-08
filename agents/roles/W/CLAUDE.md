# Role W: Web + integrator (evidence board, claim screen, events API, slides, merging and gates)

You are the coding agent for **role W** on team Fit Check (HackUTD 2026, 8090 track). Claude Code reads this as `CLAUDE.md` and Codex reads it as `AGENTS.md`; the text is the same. Your human is **Keshav** (role W), who is also the **integrator**: the only person who merges into `main` and creates `gate/*` tags. You help with integration, but **never push to `main` and never create or push a tag without your human saying yes in this session**.

**Team:** C = Hrishi (client, demo laptop), E = Prakrit (engine), D = AK (data), W = Keshav (web, integrator). Use names and roles in chat messages, e.g. `[blocked] AK (D) waiting on gate/E1-server (Prakrit, E)`.

## Read first, in this order

1. `agents/PROJECT.md`: what we're building, final decisions, glossary, file ownership, rules.
2. `agents/WORKFLOW.md`: branches, the gate table (with the check to run before each tag), the integration protocol. **You run this protocol.**
3. The plan, `docs/superpowers/plans/2026-11-08-hackutd-8090-full-plan.md`: Global Constraints; sections 3, 7, 8.0, 8.4, 9, 10, 11, 12, 13, 14, Part D; and your tasks **W1–W4**, which give the exact code and tests.

## Your job

You build everything the judges look at:

- the evidence board: Interview, Contracts, Drift and Finding views, plus the Software Factory drawer;
- the modernized claim screen and the events API that collects usage (only when the client has opted in);
- the Terms and Privacy pages;
- the mock data that lets you build before other gates open;
- the slides and demo script.

As integrator you clear gates, run the checkpoints, call the freeze and prepare the submission.

- **Branch:** `web`
- **You own (only edit these):** `server/routes_web.py` (after E1 creates it), `server/static/board.html`, `board.css`, `board.js`, `claim.html`, `claim.js`, `terms.html`, `privacy.html`, `server/static/mock/*.json`, `tests/test_events.py`, slides, `README.md`.
- **As integrator you also edit, on `main` only:** `.gitignore`, `.env.example`, `server/requirements.txt`, `contracts/`, `agents/`, the plan.
- **Never edit:** other owners' files (`server/static/interviewer.*`, `server/static/settings.js`, all other `server/*.py`, `kb/`, `legacy/`).

## Before 0:00: the bootstrap (integrator)

If `gate/G0-bootstrap` already exists on GitHub (`git ls-remote --tags origin`), skip this. Otherwise, with your human's yes:
```bash
git checkout main
git add .gitignore .env.example server/requirements.txt server/static/.gitkeep contracts docs agents
git commit -m "chore: bootstrap (plan, contracts, agent files)"
git push origin main
git tag -a gate/G0-bootstrap -m "G0 bootstrap" && git push origin gate/G0-bootstrap
```
Then:
- generate the two tokens with `python -c "import secrets; print(secrets.token_hex(16))"`, run twice;
- post them, with the Anthropic and ElevenLabs keys, in the team chat (never in the repo);
- post `[gate open] G0-bootstrap`.

## Your tasks, with gates

| Task | Time | Needs before starting | Allowed while waiting | When done, request |
|---|---|---|---|---|
| Task 0 kickoff, schema check, tag `gate/T0-schema` | 0:00–0:30 | `gate/G0-bootstrap` | none | (you tag `gate/T0-schema` yourself after the check) |
| W1 Board shell, tokens, Terms/Privacy | 0:30–1:30 | `gate/G0-bootstrap` | none | (no gate; merged with your next PR) |
| W2 Claim screen + events API | 1:30–2:30 | `claim.html` / `claim.js`: nothing. Events API in `routes_web.py` and its tests: **`gate/E1-server` (hard)**, because it needs `server/settings.py` and `routes_web.py` | Claim page HTML, CSS, JS, regexes | `gate/W2-events` |
| W3 Interview + Contracts views | 2:30–4:00 | Mocks first (`?mock=1`). Live Interview view: `gate/E3-engine` (soft). Live contract evidence: `gate/E4-lineage` (soft) | Everything against `server/static/mock/state.json` and `mock/contracts.json` | `gate/W3-views`, after retesting against the live engine |
| W4 Drift view, Finding detail, Software Factory drawer | 4:00–5:00 | Mocks first. Live drift: `gate/D3-drift` (soft). Stub button: `gate/D4-sf` (soft) | Everything against `mock/drift.json` and `mock/findings.json` | `gate/W4-views` |
| Slides and demo script | 5:00–6:00 | `gate/CP3` | none | none |
| Rehearsals, `gate/FREEZE`, `gate/RC`, submission | 5:30–7:00 | none | none | (you tag them) |

Check a gate:
```bash
git fetch origin --tags
git rev-parse -q --verify "refs/tags/gate/E1-server" >/dev/null && echo READY || echo NOT_READY
```
If it prints `NOT_READY`, stop the dependent step and keep building against mocks. If it prints `READY`, run `git merge origin/main`, then `pytest -q`, then switch from mocks to the live API.

## Integrator duties (all through `agents/WORKFLOW.md` section 2)

- **When a `[gate request]` arrives, clear it promptly.** Other laptops are waiting.
- **Order of work:**
    1. Merge the branch into local `main`.
    2. Run `pytest -q` on the merged result.
    3. Run that gate's check from the gate table.
    4. Only if both pass: show your human the result, and on their yes push `main`, create the annotated tag and push it.
    5. Add a line to the Gate log in `agents/WORKFLOW.md` and post `[gate open] <name>`.
- **If either fails:** run `git reset --hard origin/main` locally, which discards only the unpushed merge. Post `[gate failed] <name>: <reason>`. The owner fixes it on their branch.
- **Conflicts:** the owner resolves them on their branch by merging `origin/main`. Don't resolve other people's code on `main`.
- **Checkpoints:** tag `gate/CP1` at 2:30, `gate/CP2` at 4:00 and `gate/CP3` at 5:00, each after its live check. Then `gate/FREEZE` at 5:30 (fix commits only after that), and `gate/RC` at 6:45.
- **Interface changes:** the only way plan section 10 changes is through you: edit it on `main`, push, post `[interface change] ...`.
- **The demo laptop is C's.** For checkpoints and rehearsals, C pulls `main` there.

## Task notes beyond the plan

- **W1, design rules (plan section 9).**
    - **Colour:** background `#F6F4EF` (never pure white), panels `#FFFDF8`, ink `#1D2327`, muted text `#5B636A`, lines `#D9D4CA`. One accent, `#0F6E6E`, used only for our tool's own elements and the C-01 finding. Status colours: holding `#4E7D5B`, drifting `#B7791F`, broken `#A23B2A`.
    - **Type:** IBM Plex Sans and IBM Plex Mono.
    - **Shape:** 4 px corners, 1 px borders.
    - **Never:** shadows, gradients (except the skeleton shimmer), glass, orbs, emojis, Lucide icons, hover animations, three-card rows, bento grids.
    - **Always:** skeleton loaders while loading, and a footer with Terms and Privacy.
    - **Page structure:** `board.html` holds one `<section id="<name>-view">` per view, including an empty `settings-view`, plus `<script src="/static/settings.js" defer></script>`. C writes `settings.js`; don't create it.
- **W2.**
    - **Routes in `routes_web.py`:** `GET /claim` (fills the client token into the meta tag), `POST /api/events`, `GET /api/events/recent`.
    - **Event checks, in this order:** token (401), drift on (403), shape (422: catalog name, no `notes`/`text` prop, no string over 40 characters).
    - **Reading values:** read `os.environ` and `settings.LIVE_EVENTS_PATH` at request time.
    - **Browser:** notes regexes run in the browser and only tags are sent. With drift off, the claim page sends nothing and says so.
- **W3 and W4, mocks.** Write the mock JSON by hand from plan 10.2, 8.4 and `contracts/medicare_contracts.json`. The F-01 example in 8.4 is the finding mock. Keep the live and mock code paths identical apart from the URL.
- **W4, Chart.js.** Load it from cdnjs with an exact version and the SRI integrity hash shown on the cdnjs page. The drawer button is disabled with an explanation when `send_to_sf` is false, and always labelled "Simulated, no live connection".
- **Demo and pitch:** plan section 12 (script), section 13 (fallbacks), Part D (slides and Q&A). Record the second rehearsal as the backup video.

## Interfaces you depend on (frozen; plan section 10)

- `GET /api/interviews/{id}/state` keys: `transcript`, `queue`, `played`, `slot_fills`, `contradictions`, `rules_mentioned`, `coverage`, `yield`.
- `GET /api/contracts`, `GET /api/settings`, `GET /api/drift` (`{"enabled": false}` when off), `GET /api/findings`, `GET /api/findings/{id}/sf-payload`, `POST /stub/v2/reporting-api/feedback`, `GET /api/eval`.
- `server.settings`: `load_settings`, `save_settings`, `SETTINGS_PATH`, `AUDIT_PATH`, `LIVE_EVENTS_PATH`.

## How you test

- `pytest tests/test_events.py -q`, which the plan gives for W2.
- `node --check` on every `.js` file you own.
- Manual checks for each view against mocks, then against live data.
- As integrator: `pytest -q` on every merge.

## Committing

Commit small and often on `web` (`feat(web): ...`). Your own work goes through the same gate protocol as everyone else's: merge `origin/main`, test, push `web`, then merge it into `main` with the same checks. Never force-push. Never commit `.env`, `data/`, `CLAUDE.md` or `AGENTS.md`.

## Stop and ask your human when

- any push to `main` or any tag is about to happen (always);
- a gate check fails;
- two owners need the same file;
- an interface must change;
- or the schedule is slipping. Use the cut list in plan section 14.

## Report at the end of every task

What you built, test results, gates cleared and pending, who is blocked on whom, and the next task.
