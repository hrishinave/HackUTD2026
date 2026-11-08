# Role C: Client (interviewer page, glasses, client settings panel)

You are the coding agent for **role C** on team Fit Check (HackUTD 2026, 8090 track). Claude Code reads this as `CLAUDE.md` and Codex reads it as `AGENTS.md`; the text is the same. Your human is **Hrishi** (role C). Their laptop is **the demo laptop**: the Meta glasses are paired to it, and the final integrated `main` runs on it during the demo.

**Team:** C = Hrishi (client, demo laptop), E = Prakrit (engine), D = AK (data), W = Keshav (web, integrator). Use names and roles in chat messages, e.g. `[blocked] AK (D) waiting on gate/E1-server (Prakrit, E)`.

## Read first, in this order

1. `agents/PROJECT.md`: what we're building, final decisions, glossary, file ownership, rules.
2. `agents/WORKFLOW.md`: branches, gates, how to wait for and request a gate.
3. The plan, `docs/superpowers/plans/2026-11-08-hackutd-8090-full-plan.md`: Global Constraints; sections 5.1, 5.4, 5.5, 8.0, 9, 10.1, 10.2, 11; and your tasks **C1–C4**, which give the exact code and tests.

## Your job

Build the Chrome page the interviewer uses during an interview (`http://localhost:8000/interviewer`). It does four things:

- transcribes the conversation with Chrome's speech recognition;
- sends each final sentence to the server over a WebSocket;
- receives the question queue;
- plays a question through the glasses when they tap.

You also run the glasses device tests that decide whether taps work, and you build the Client settings panel on the board.

- **Branch:** `client`
- **You own (only edit these):** `server/static/interviewer.html`, `server/static/interviewer.js`, `server/static/silence.mp3`, `server/static/settings.js`, `docs/DEVICE_TESTS.md`.
- **Never edit:** anything under `server/*.py`, `server/static/board.*`, `claim.*`, `terms.html`, `privacy.html`, `kb/`, `legacy/`, `contracts/`, `agents/`, the plan. If you need a change there, tell your human, who asks the owner.

## Setup on this laptop (once)

```bash
cp .env.example .env               # fill keys and tokens from the team chat
pip install -r server/requirements.txt
git checkout -b client             # if the branch doesn't exist yet
```
macOS System Settings › Sound: **Input = MacBook Microphone, Output = the glasses**. Quit Music, Spotify and any tab playing media. Never select the glasses as a microphone: that puts them in call mode and taps stop working.

## Your tasks, with gates

| Task | Time | Needs before starting | Allowed while waiting | When done, request |
|---|---|---|---|---|
| C1 Page skeleton + device tests | 0:30–1:30 | `gate/G0-bootstrap` | none | `gate/C1-devices` (tag message PASS or FAIL) |
| C2 Speech recognition + WebSocket | 1:30–2:30 | Recognition: nothing. Socket test: **`gate/E1-server` (hard)** | Recognition code, logging finals to the console | (no gate; included in CP1) |
| C3 Queue, taps, playback, freshness gate | 2:30–4:00 | `gate/E1-server` (its fake queue is enough to build and test) | none | `gate/C3-client`, only after `gate/E3-engine` exists and you've retested against the real engine |
| C4 Robustness + Client settings panel | 4:00–5:00 | `gate/E1-server` (for `/api/settings`) | none | `gate/C4-settings` |
| Fix list, then rehearsals as the demo operator | 5:00–6:45 | `gate/CP3`, then `gate/FREEZE` | none | none |

Check a gate:
```bash
git fetch origin --tags
git rev-parse -q --verify "refs/tags/gate/E1-server" >/dev/null && echo READY || echo NOT_READY
```
If it prints `NOT_READY`, stop and tell your human: `[blocked] C waiting on gate/E1-server (owner E)`. Then do only the allowed pre-work. If it prints `READY`, run `git merge origin/main`, then `pytest -q`, then continue.

## Task notes beyond the plan

- **C1, before the server exists.** Serve the page with `cd server && python -m http.server 8000` and open `http://localhost:8000/static/interviewer.html`. Chrome allows the microphone and Media Session on `localhost`. Once `gate/E1-server` is open, use `uvicorn server.app:app --host 127.0.0.1 --port 8000` and `http://localhost:8000/interviewer`.
- **C1, `silence.mp3`.** Make it with `ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 10 -q:a 9 server/static/silence.mp3`. If ffmpeg is missing, ask your human before installing anything (`brew install ffmpeg`).
- **C1, device tests.** T1–T4 in the plan need the real glasses on this laptop. Write results in `docs/DEVICE_TESTS.md` as a table: test, result, notes. If T1 (taps) fails after closing other media apps and clicking Start again, write `FAIL: T1` and tell your human immediately. The team then uses the spacebar, the "Ask next" button and auto mode.
- **C2.** Reset `T0 = Date.now()` in the Start click handler. All `t_ms` values are milliseconds since Start. Send only final results, iterating from `e.resultIndex`. Drop finals while `playing` is true.
- **C3.** Message shapes are exactly plan section 10.1. A `queue` message replaces your local queue. The `audio` message carries `mp3_b64` for a question ID. Bank questions come with `audio_url` (`/clips/PQ-NN.mp3`).
    - **Freshness gate:** on a tap, if `queue.based_on_t_ms < lastFinalT`, wait up to 1,000 ms for a newer queue.
    - **Tap mapping:** `play` and `pause` → top question; `nexttrack` → second question; `previoustrack` → repeat last.
- **C4, `settings.js`.** It renders into `<section id="settings-view">`, which W puts in `board.html`. Settings API: `GET /api/settings`; `POST /api/settings` with header `X-Admin-Token` and a body of changed keys (`drift_enabled`, `contracts_watched`, `notes_matching`, `send_to_sf`, `retention_days`, optional `purge`). Wrap every `sessionStorage` and `localStorage` call in try/catch.
- **Design:** the interviewer page is used live, so keep it plain and large:
    - one Start button, a connection and recognition status line, the current queue (cue, text), a big "Ask next" button, an auto-mode toggle, and the last `tap_to_audio_ms`;
    - colours and fonts from plan section 9 (`#F6F4EF` background, `#1D2327` ink, `#0F6E6E` accent, IBM Plex Sans);
    - no shadows, gradients or emojis.

## Interfaces you depend on (do not change them)

- WebSocket `ws://localhost:8000/ws/client/{interview_id}`, messages in plan 10.1.
- `POST /api/interviews/{id}/start` with `{"interviewee": "billing_clerk_2"}`. Interviewees: `billing_clerk_1`, `billing_clerk_2`, `denial_specialist_1`.
- `GET /clips/{bank_id}.mp3`, `GET /api/settings`, `POST /api/settings`.
- Function names inside your page (plan C1–C3): `startMediaKeys`, `startRecognition`, `connect`, `send`, `onServer`, `onTap`, `speak`, `waitForFresh`, `render`.

## How you test

- `node --check server/static/interviewer.js` and `node --check server/static/settings.js`: no syntax errors.
- The manual tests in plan C1–C3. Write the results into the PR body.
- `pytest -q` must stay green after you merge `origin/main`, even though you don't own Python files.

## Committing and asking for a gate

Commit small and often on `client` (`feat(client): ...`). When a task is done, follow `agents/WORKFLOW.md` section 1: merge `origin/main`, `pytest -q`, push, open a PR titled `[gate <name>] ...`, and post `[gate request] ...` in the chat. Never push to `main`, never force-push, never commit `.env`, `data/`, `CLAUDE.md` or `AGENTS.md`.

## Stop and ask your human when

- a hard gate is missing;
- a device test fails;
- you'd need to edit a file you don't own;
- an interface in plan section 10 seems wrong;
- you want to install something;
- or anything would make the demo laptop's audio settings change.

## Report at the end of every task

What you built, the test and device results, which gate to request, what's blocked and on whom, and the next task.
