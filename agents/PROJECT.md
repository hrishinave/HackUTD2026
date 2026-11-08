# Pact: shared project context (read this first)

This file is the same for all four people and their coding agents (Claude Code or Codex). Your role file (`CLAUDE.md` / `AGENTS.md` at the repo root, copied from `agents/roles/<ROLE>/`) tells you what *you* build. The full specification is `docs/superpowers/plans/2026-11-08-hackutd-8090-full-plan.md` ("the plan"). When this file and the plan disagree, the plan wins; tell the integrator so this file gets fixed.

## The event

- HackUTD 2026, 8090.AI track: "Build agents and tools that accelerate legacy system modernization. Make it easier to understand, improve, or replace."
- Team of 4, 7 build hours, 4 laptops, one GitHub repo: `https://github.com/hrishinave/HackUTD2026`.
- Judges are 8090 engineers. They told us code mapping, PR/security review agents and plain code translation are overdone. The real gaps are understanding users before a rewrite and verifying fit after it.

## What we are building, in one paragraph

An 8090 interviewer wears speaker-only Meta glasses, paired straight to a MacBook, and interviews staff at a legacy client: a fictional Medicare billing office. A Chrome page on the laptop transcribes the conversation. A local server asks Claude Haiku 5.5 what to ask next, using a knowledge base built from the client's legacy COBOL code, documents and logs. A tap on the glasses plays the next question in the interviewer's ear. The interview turns into evidence-backed requirements and **behaviour contracts**: checkable statements of what usage should look like if each requirement is met. After launch, and only if the client opts in, usage of the new system is checked against those contracts. When people drift away from a requirement, we produce a finding with its cost, its type and a link back to the interview quote that created it. We then hand it to 8090's Software Factory as one simulated Feedback item. Tagline: **Software Factory checks code against requirements. We check requirements against people.**

## Decisions that are final (do not reopen them)

| Topic | Decision |
|---|---|
| Hardware | Speaker-only Meta glasses paired to the MacBook (confirmed). No phone. macOS Sound: Input = MacBook Microphone, Output = glasses |
| Interviewer client | One Chrome page at `http://localhost:8000/interviewer`: Web Speech API, Media Session API (glasses taps), HTML audio |
| Taps | Single tap = play top question, double tap = next question, triple tap = repeat last |
| LLM | Claude Haiku 5.5 only (`claude-haiku-5-5`), thinking disabled and effort low for interviews; D5 offline drafting uses adaptive thinking and effort medium; structured JSON output, cached brief |
| Engine shape | Two parallel calls per trigger: a fast question call (mostly returns prepared question IDs) and a bookkeeping call (slot fills, contradictions); 1.0 s debounce |
| Voice | Prepared questions are pre-voiced with ElevenLabs; new questions are voiced live; the browser voice is the fallback |
| Server | Python 3.12 + FastAPI on `127.0.0.1:8000`, plain files for data, no database |
| Web | Plain HTML/CSS/JS, Chart.js, IBM Plex fonts, design rules in plan section 9 |
| Drift | Off by default; the client switches it on in Client settings; sensors only, never changes the client app |
| Software Factory | One simulated integration: `POST /v2/reporting-api/feedback`, shown with exact payload and a local stub |
| Demo client | Fictional Medicare billing office; all data synthetic and labelled as such |

## Glossary

| Term | Meaning |
|---|---|
| Behaviour contract | JSON object (schema `contracts/contract.schema.json`) saying what usage should look like if a requirement is met. Five examples in `contracts/medicare_contracts.json` (C-01 to C-05) |
| Slot | A fact an interview must collect for a contract, e.g. `C-01.current_practice` |
| Brief | The cached system prompt for every Haiku call, built by `build_brief()` from the knowledge base |
| PQ-NN | A prepared question in `kb/question_bank.json` |
| Q-N | One question instance in one interview (Q-1, Q-2, ...). Links a question to when it was played, its answer and the slot it filled |
| Lineage | The chain contract field ← quote ← answer to Q-N ← reason. Proves an AI question produced a contract |
| Yield | Share of played AI questions whose answer filled a slot or raised a contradiction |
| Drift | A contract measured outside its tolerance for 2 consecutive post-launch weeks |
| Finding | A drifting contract with type, cost, lineage and explanation (plan section 8.4) |
| Gate | A git tag `gate/<name>` on `main` that says a dependency is ready (see `agents/WORKFLOW.md`) |
| Integrator | Keshav (role W). The only one who pushes to `main` and creates gate tags |

## Who does what

| Role | Person | Branch | Builds | Plan tasks |
|---|---|---|---|---|
| **C** Client | Hrishi (demo laptop, glasses paired here) | `client` | Interviewer page (speech, taps, playback, freshness gate), glasses device tests, Client settings panel | C1–C4 |
| **E** Engine | Prakrit | `engine` | Server skeleton and route files, settings module, knowledge base and question bank, Haiku adapter, interview engine, voice clips, lineage API | E1–E4 |
| **D** Data | AK | `data` | Legacy company in a box (COBOL, manual, answer key, scripts), contracts loader, simulator, drift detector, findings, Software Factory payload and stub, eval | D1–D4 |
| **W** Web + integrator | Keshav | `web` | Evidence board views, claim screen and events API, Terms/Privacy, slides; merges branches and tags gates | W1–W4 |

## Where things live

| Path | What | Owner |
|---|---|---|
| `contracts/` | Contract schema, five contracts, event catalog | Shared (integrator edits) |
| `docs/superpowers/plans/2026-11-08-hackutd-8090-full-plan.md` | The plan | Shared (integrator edits) |
| `agents/` | This file, WORKFLOW.md, README.md, role files | Shared (integrator edits) |
| `legacy/` | COBOL, manual, answer key, role-play scripts | D |
| `kb/rules.json`, `kb/doc_diffs.json`, `kb/log_facts.json` | Derived knowledge base files | D |
| `kb/slots.json`, `kb/people.json`, `kb/question_bank.json`, `kb/open_items.json` | Interview knowledge base | E |
| `server/app.py`, `server/routes_engine.py`, `server/settings.py`, `server/kb.py`, `server/llm.py`, `server/engine.py`, `server/tts.py` | Engine side | E |
| `server/routes_data.py`, `server/contracts.py`, `server/simulate.py`, `server/drift.py`, `server/feedback.py` | Data side | D |
| `server/routes_web.py`, `server/static/board.*`, `claim.*`, `terms.html`, `privacy.html`, `server/static/mock/` | Web side | W |
| `server/static/interviewer.*`, `server/static/silence.mp3`, `server/static/settings.js`, `docs/DEVICE_TESTS.md` | Client side | C |
| `tests/` | One test file per module; each owner owns the tests for their modules | per module |
| `data/` | Generated data, settings, clips, state (gitignored) | runtime |

## Rules every agent follows

1. Edit only files your role owns (table above). Need a change elsewhere? Ask the owner through your human.
2. Never push to `main`, never force-push, never move or delete a tag. Push only your own branch.
3. Never commit `.env`, `data/`, `CLAUDE.md` or `AGENTS.md` (they are gitignored; keep it that way).
4. Before starting a task with a dependency, check its gate (`agents/WORKFLOW.md`). If the gate is missing, stop and tell your human which gate and owner you are waiting on; do only the pre-work your role file allows.
5. Build against the interfaces in plan section 10 exactly: names, paths, message shapes, schemas. If you think one must change, stop and tell your human; the integrator changes it for everyone.
6. Tests first (the plan gives them), then code, then run the tests, then commit. Small commits with messages like `feat(engine): ...`.
7. No new dependencies without the integrator (they edit `server/requirements.txt`). The web side uses no build step and no npm packages.
8. API keys come from `.env` on the server only. Nothing secret goes into page code.
9. Before you ask for a gate: merge the latest `origin/main` into your branch, run `pytest -q` (all of it), push your branch.
10. At the end of every task, report to your human: what you built, test results, which gate to request, what's next.

## Quick commands

```bash
uvicorn server.app:app --host 127.0.0.1 --port 8000 --reload   # run the server
pytest -q                                                      # run all tests
git fetch origin --tags && git tag -l 'gate/*'                 # see which gates are open
git fetch origin && git merge origin/main                      # bring main into your branch
```
