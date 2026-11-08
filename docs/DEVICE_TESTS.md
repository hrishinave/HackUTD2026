# C1 device tests

Date: 2026-11-08. Operator: Hrishi (C). Laptop: the demo MacBook, with the Meta glasses paired.

## Status

**T1–T4 PASS (operator-reported); C1 device testing complete.** Hrishi clarified “no i meant it all passed with .5 secs” after the T1 acceptance question, correcting the earlier selection of “Some taps failed or were slower”. The corrected report is that all three gestures passed 10/10 within 0.5 s. T2 passed on retry after selecting the built-in microphone explicitly; T3 and T4 also passed according to Hrishi's reports. The first T2 failure is retained below.

**Gate handoff:** device outcome is PASS for the integrator's `gate/C1-devices` tag message. Final `git merge origin/main` reported already up to date; `pytest -q` still collected no tests (exit 5). This is not a green suite, so publish for review without claiming the workflow's full-suite check passed. Only Keshav (W) may merge to main and create the gate tag.

## Preparation

1. In macOS System Settings → Sound, verify Input is **MacBook Microphone** and Output is **the glasses**. Do not use the glasses microphone. Stop and tell Hrishi if either setting needs changing.
2. Close Music, Spotify, and other tabs playing media. Wear the glasses.
3. Before `gate/E1-server`, run `python3 -m http.server 8000 --bind 127.0.0.1` from `server/`. Open **Google Chrome** at `http://localhost:8000/static/interviewer.html` in its own visible window.
   After E1, use `http://localhost:8000/interviewer`. **Do not open the HTML file directly from Finder or a repo file link:** a `file://` page cannot load the root-relative `/static/interviewer.js` or use the server API correctly.
4. Click **Start interview**. The status must say that the silent loop is playing. Open Chrome's Console with Command–Option–J. Use only synthetic role-play and obtain the reader's consent before recording/transcription.

## Results

| Test | Result | Notes |
|---|---|---|
| T1: taps | PASS — operator-reported | Hrishi clarified “no i meant it all passed with .5 secs” in response to the explicit question about single/double/triple taps each passing 10/10 within 0.5 s. This supersedes the mistakenly selected failure option. No independently measured latency trace. |
| T2: voice with microphone in use | PASS on retry — operator-reported | First default-device probe selected the glasses (FAIL). After restoring routing, Hrishi replied “works” to the explicit-device retry and checks for MacBook input, clear voice through glasses, and functioning taps with capture active. Exact microphone label was not supplied. |
| T3: transcription at 0.7 m | PASS — operator-reported | Hrishi reported “yes t3 works” in response to the ten-line test at 0.7 m, requiring “prior auth”, “notes”, “denial”, and “coverage” to be recognized correctly. No raw transcript or per-line count was supplied; result is the operator's report. |
| T4: call-mode guard | PASS — operator-reported | Hrishi replied “works” to the retry instructions, which included checking that Input remained MacBook Microphone and Output remained glasses during active capture. No screenshot or independent agent observation. |

### T1: taps

With Start clicked and the glasses worn, perform 10 single taps, then 10 double taps, then 10 triple taps. Leave enough time between trials to distinguish each gesture. The page shows the last received action, and the Console logs `tap play`, `tap next`, or `tap repeat`. `pause` media events also map to `play`.

Report correct/total counts separately for all three gestures, any wrong or missed actions, and whether each event appeared within 0.5 s of the gesture. Page timestamps show receipt time, not physical tap latency; the operator must observe latency. Button and spacebar checks are separate fallback checks, not evidence that glasses taps work.

If T1 fails, stop and tell Hrishi. The plan permits one retry after closing other media apps/tabs and clicking Start again. If that also fails, record **FAIL: T1**, inform Hrishi immediately, and use spacebar / Ask next (and auto mode once implemented).

### T2 and T4: microphone, voice, and route

**First attempt failed:** requesting `deviceId: { exact: 'default' }` selected the glasses microphone. Do not use the default-device probe again. Hrishi reports restoring Input = MacBook Microphone and Output = glasses. Do not change system audio settings without Hrishi's approval.

For the retry, select the actual built-in microphone by its device ID. Stop old test tracks first. Chrome already has microphone permission from the first test; if labels are missing or exactly one physical built-in microphone cannot be identified, this probe stops without opening any microphone. Report the error rather than falling back to the default.

```js
window.c1Mic?.getTracks().forEach(track => track.stop());
window.c1MacInputs = (await navigator.mediaDevices.enumerateDevices()).filter(device =>
  device.kind === 'audioinput' && !['default', 'communications'].includes(device.deviceId) &&
  /MacBook.*Microphone|Built[- ]in Microphone/i.test(device.label)
);
if (c1MacInputs.length !== 1) throw new Error('Cannot identify one MacBook microphone. Stop and report this.');
window.c1Mic = await navigator.mediaDevices.getUserMedia({
  audio: { deviceId: { exact: c1MacInputs[0].deviceId } }
});
console.log('T2 input:', c1Mic.getAudioTracks()[0].label);
```

Confirm the reported input is the MacBook microphone. If it names the glasses, stop the tracks immediately and report failure:

```js
c1Mic.getTracks().forEach(track => track.stop());
```

With the MacBook microphone stream still active:

```js
speechSynthesis.speak(new SpeechSynthesisUtterance('test'));
```

Check that the voice is heard in the glasses at full quality. Recheck single/double/triple taps while the mic remains active. During this test, open Sound settings and verify **Input = MacBook Microphone; Output = glasses** (T4). Do not change these settings silently. Record the heard audio quality, tap results, microphone label, and displayed routing. Then stop the mic:

```js
c1Mic.getTracks().forEach(track => track.stop());
```

### T3: transcription at distance

This is a temporary device probe, not C2's server-connected transcription. Before starting, verify Chrome's selected microphone at `chrome://settings/content/microphone` is the MacBook microphone too. The explicit `getUserMedia` selection in T2 does not itself configure speech recognition's input. If Chrome still selects the glasses, stop and tell Hrishi before any settings change. Keep the glasses as system output and return to the interviewer page.

With the consenting reader about 0.7 m from the laptop, run this in Chrome's Console:

```js
window.c1Recognition?.abort();
window.c1Finals = [];
window.c1Recognition = new webkitSpeechRecognition();
c1Recognition.continuous = true;
c1Recognition.interimResults = true;
c1Recognition.lang = 'en-US';
c1Recognition.onresult = event => {
  for (let i = event.resultIndex; i < event.results.length; i++) {
    if (event.results[i].isFinal) {
      c1Finals.push(event.results[i][0].transcript.trim());
      console.log('T3 final:', c1Finals.at(-1));
    }
  }
};
c1Recognition.onerror = event => console.error('T3 recognition error:', event.error);
c1Recognition.onend = () => console.log('T3 recognition ended; restart if the 10 lines are unfinished.');
c1Recognition.start();
```

Read these 10 lines, one at a time with a brief pause. They come from the supplied billing clerk 1, billing clerk 2, and denial specialist role-play scripts; all are fictional.

1. If it needs prior auth I put the number in the notes, or sometimes just see fax.
2. Pretty much every imaging claim for Medicare Advantage needs one.
3. Honestly we mostly just write see fax.
4. If coverage changes after the visit, it lands in my queue and I re-run eligibility.
5. There's a field for it? I've never used it. The system doesn't care what's in there.
6. A normal claim takes me maybe four minutes if nothing's weird.
7. If I have to open a claim twice, something went wrong.
8. The prior auth number always goes in the notes. That's where the system looks.
9. We keep a spreadsheet of every denial because the system loses track of them after a month.
10. I export the denials list a few times a week so the spreadsheet stays current.

Record how many source lines were captured and the actual recognition of “prior auth”, “notes”, “denial”, and “coverage”. Recognition can combine lines or split sentences across final results, so final-event count alone is not the number of lines captured. A recognition error or an incorrect required term is a failed test, not PASS. Stop afterward and review the captured text:

```js
c1Recognition.stop();
c1Finals.join('\n');
```

## Software checks

Before implementation:

- `client` created from `gate/G0-bootstrap` and updated with `origin/main` (`e5dbb1c`).
- C1's four files were absent, as expected before implementation.
- `pytest -q`: **no tests collected**, exit code 5. This is not a green test suite.
- Node, ffmpeg, and ffprobe are already installed; no dependencies installed.

After implementation:

- `node --check server/static/interviewer.js`: PASS.
- An isolated Node browser-API harness passed the four media mappings (`play`/`pause` → `play`, `nexttrack` → `next`, `previoustrack` → `repeat`), Start playback, Ask next, spacebar, focused-control and held-key guards, rejected-audio handling, and manual fallback when Media Session is unavailable. This used mocks, not physical media keys.
- ffprobe: MP3, mono, 44,100 Hz, exactly 10.000000 seconds. ffmpeg volume analysis: decoded silence at its -91 dB reporting floor.
- Local HTTP checks: the HTML, JavaScript, and MP3 all return HTTP 200 with their expected content types.
- Layout rendered and was visually inspected in the in-app browser. The preview was closed without starting media, so it cannot compete for glasses media keys.
- Automated launch of native Google Chrome timed out; subsequent app inventory still showed Chrome not running. Hrishi must open Chrome for device tests. This is not a glasses-test result.
- Before the skeleton commit, `git status` contained only the four C1 files; root `CLAUDE.md`, `AGENTS.md`, and `.env` were ignored and absent from status.
- Final C1 integration check: fetched origin and tags; `git merge origin/main` → already up to date at `e5dbb1c`; `pytest -q` → no tests collected, exit 5. No test suite is present on current main. This remains a handoff limitation, not a passing test result.
- Origin gate tags at handoff: `gate/G0-bootstrap`, `gate/D1-legacy`. `gate/E1-server` is absent, so C2's socket test and C3/C4's server-dependent work remain blocked on Prakrit (E).

All four device tests passed according to Hrishi's reports; the original T2 failure and its recovery are retained. Devices are ready for the C1 gate review, but the required green-suite condition cannot be established while pytest collects no tests. Do not create or claim the integrator's gate tag from this branch.

## C2: recognition and WebSocket integration

**Manual Chrome speech check: PASS (operator-reported).** Hrishi selected “All C2 checks pass” in response to the integrated Chrome test: the spoken sentence appears within about 2 seconds, connected/listening statuses are present, and a fresh queue arrives in the Console with MacBook input / glasses output. Automated checks below are recorded separately. The C1 T1–T4 results above remain historical results.

### Prerequisites and baseline

- Fetched origin; `gate/C1-devices`, `gate/E1-server`, and `gate/E2-kb` now exist alongside bootstrap and D1. Merged `origin/main` into `client` at `72902b0` before C2 implementation.
- The initial post-merge `pytest -q` failed during collection because the laptop's Python 3.12 environment lacked `anthropic`. The required host-access retry failed identically. Hrishi explicitly approved installing the declared dependencies in an isolated environment.
- Created `/private/tmp/fit-check-client-venv` with Python 3.12, reusing existing system packages. Installed the unchanged `server/requirements.txt` into that environment. No requirements or system audio settings were changed.
- Baseline `/private/tmp/fit-check-client-venv/bin/python -m pytest -q`: **36 passed**, with one third-party deprecation warning.
- Wrote a temporary client-check harness before implementation. It failed as expected because recognition was not configured in C1. No test file outside Role C's ownership was added to the repo.

### Automated results

- `node --check server/static/interviewer.js`: PASS.
- Temporary client harness: PASS for final-only sends, starting at `resultIndex`, trimming/ignoring blank results, timestamps relative to Start, suppression while `playing`, hello-before-buffered-message ordering, reconnect buffering, queue receipt, recognition restart, terminal microphone-permission handling, failed HTTP start cleanup/retry, and unsupported-recognition status.
- Full Python suite after C2 implementation: **36 passed**, one third-party deprecation warning.
- Final review sync: fetched origin again and merged `origin/main` at `842fcd3`, including W's events API and its tests. Full suite on the merged client branch: **58 passed**, one third-party deprecation warning. `gate/W2-events` now exists as well; `gate/E3-engine` is still absent at this check.
- Replaced only the verified temporary C1 file-server process with the FastAPI server, bound to `127.0.0.1:8000`, with `LLM_PROVIDER=fake`. No paid model calls or microphone capture in the automated test.
- Live integration using the actual client JavaScript, real HTTP/WebSocket transport, and synthetic recognition: **PASS**. `/interviewer` returned HTTP 200; `/start` succeeded; the server stored the synthetic final and sent a fresh fake queue in **1,073 ms** after the final event. Speech while `playing` was not stored. A real socket disconnect/reconnect delivered a buffered final exactly once.
- Updated page controls and status lines visually inspected in the in-app browser. That preview was closed without starting media or microphone capture.

### Manual C2 acceptance procedure

1. Close the old C1 test tab so it cannot hold the microphone or media keys. Open Chrome at `http://localhost:8000/interviewer` (the FastAPI route).
2. Keep Chrome's input set to MacBook Microphone and system output to the glasses. Stop and report any routing change or microphone error; do not use the glasses input.
3. Choose Billing clerk 2 and click Start interview. Expect the silent loop, connected status, and listening status. Open the Console with Command–Option–J.
4. With consent and synthetic role-play only, say: “If it needs prior auth I put the number in the notes.” Expect the final sentence on the page within about 2 seconds and a new `server` / `queue` message reflecting that final in the Console. An initial queue before speech is not proof of this check.
5. Record the physical speech result here and in the C2 PR before calling C2 complete. C2 has no separate gate; its result feeds CP1. C3's completion gate additionally requires `gate/E3-engine` and a real-engine retest.

| C2 check | Result | Notes |
|---|---|---|
| Real spoken sentence → final utterance → fresh fake queue in Chrome | PASS — operator-reported | Hrishi selected “All C2 checks pass” for the procedure above. Includes the approximately 2-second final, connected/listening statuses, and fresh fake queue in Chrome. No independent timing trace or raw transcript was supplied. |

## C3: queue, taps, playback, and freshness

**C3 COMPLETE: fake-server and real-engine physical checks PASS (operator-reported).** After correcting the local-file URL issue below, the server confirmed spoken finals, fresh AI queues, and AI-origin played questions. Hrishi then confirmed “it works” in response to the final repeat/freshness check and requested no further C3 checks. Device acceptance is recorded from that confirmation; independent acoustic timing was not captured. Ready for Keshav's `gate/C3-client` review. Automated transport checks remain separate evidence.

During follow-up, Hrishi reported Start was unresponsive. Native Chrome inspection showed `file:///Users/hrishinave/Projects/HackUTD2026/server/static/interviewer.html`, rather than the running server URL. The agent navigated that tab to `http://localhost:8000/interviewer?id=C3-REAL-DEVICE`, clicked Start, and directly verified **Interview started**, **Connection: connected**, **Transcription: listening**, and an initial fallback-plan question. This fixed the Start issue without changing application code or audio settings. The subsequent real session stored at least six utterances, produced AI-origin queues, and recorded AI-origin playback of Q-5 (PQ-07) and Q-7 (PQ-31). Server logs showed browser-start metrics of 37 ms and 13 ms, respectively, and positive question/bookkeeping cache reads. These browser-start measurements do not measure sound arriving at the ear. Hrishi's final repeat/freshness confirmation completes the physical acceptance; the earlier zero-utterance observation remains historical troubleshooting evidence.

### Gates and baseline

- Verified `gate/E3-engine` exists on origin alongside `gate/E1-server`. Merged `origin/main` through `a030097` before implementation; baseline full Python suite: **67 passed**.
- Verified only that the locally supplied Anthropic key is present and `.env` is ignored; no key value was displayed or committed.
- A temporary C3 client harness was written and run before implementation. It failed as expected because C2 did not yet define `waitForFresh`.

### Implementation and automated checks

- A `queue` message replaces the local queue; pushed base64 audio is indexed by question ID. Rendered cue, text, and target use text nodes.
- Single/play and pause media events select the top question; next selects the second question **currently queued**; repeat uses the last question whose audio started. Single and double tap trials must be read against the current visible list, since playing removes an item.
- Playback prefers pushed audio, then the bank clip URL, then browser voice. A missing or rejected clip also falls back to voice, with duplicate error callbacks guarded.
- `tap` messages include the relative timestamp. `played` and `tap_to_audio_ms` are sent when audio actually starts, so a failed playback attempt does not create false played lineage. The metric measures browser audio start, not independently observed Bluetooth sound at the ear.
- Capture suppression lasts through playback plus 300 ms. Replaced playback callbacks cannot release a newer playback's suppression guard.
- A stale tap waits for a fresh queue or a 1,000 ms deadline, with 50 ms polling. Concurrent freshness waits are suppressed; repeat does not wait for queue freshness.
- `node --check server/static/interviewer.js`: PASS. Temporary C3 harness: PASS for top/second/repeat selection, safe rendering, clip precedence, missing-clip fallback, played/metric messages, displayed latency, fresh-queue arrival, timeout behavior, and stale-playback callback isolation.
- Existing C2 temporary checks were updated only to supply C3's browser/DOM stubs; all C2 recognition, buffering, reconnect, permission, and HTTP setup checks still PASS.
- Full Python suite after C3 implementation: **67 passed**, one third-party deprecation warning.
- Final review sync: merged `origin/main` through `e15c1a9`, including the data gates and C2 integration. Full suite on the merged client branch: **104 passed**, one third-party deprecation warning, in 58.08 seconds. C2 and C3 temporary client harnesses and syntax checks also pass after the merge.
- The standard fake provider emits one question. For the plan's three-question test, a temporary fixture in `/private/tmp/fit-check-c3-fake-server.py` wraps only the fake question response in a separate server process. It serves the real FastAPI routes on `127.0.0.1:8000`. No Engine-owned repo source is edited or copied into the client branch.
- Actual C3 JavaScript against that three-question fake fixture: fresh queue in **1,015 ms**; second-current-question and repeat both acknowledged and stored by the real server. A stale queue waited **1,022 ms** wall time before playback (1,000 ms deadline plus event-loop scheduling).
- Actual C3 JavaScript against the real Haiku engine on an isolated `127.0.0.1:8001` server: fresh queue in **1,408 ms** after a synthetic final; top question and repeat both acknowledged and stored. Browser audio and recognition were mocked in both transport checks; no microphone was opened by those checks.

### Physical acceptance

Use MacBook Microphone input and glasses output, with other media apps/tabs closed. Stop and report any failed device check or routing change.

1. Fake fixture: open `http://localhost:8000/interviewer?id=C3-DEVICE` in Chrome, click Start, speak a synthetic sentence, and wait for three visible questions.
2. Single tap: top visible question is heard within 0.5 s. Wait for it to finish.
3. Double tap: second question in the **current** visible list plays. Triple tap repeats that same question. Check the server's `played` log and acknowledgement.
4. Speak again and tap as soon as the latest final appears, before the refreshed queue arrives. Playback should resume after at most about one second. This stale-queue delay is separate from the fresh-tap 0.5-second target.
5. After the fake-fixture check passes, switch the normal port-8000 server to `LLM_PROVIDER=anthropic` and repeat against real engine questions before requesting `gate/C3-client`. Do not switch the server while Hrishi is still testing the fake fixture.

| C3 check | Result | Notes |
|---|---|---|
| Fake-server three-question glasses mapping, latency, and freshness | PASS — operator-reported | Hrishi selected “All fake-server C3 glasses checks pass” for the procedure above. The real server state for C3-DEVICE contained 4 utterances and played IDs Q-2, Q-4, Q-4, Q-6, Q-7, including the repeated Q-4. No independent acoustic timing trace was supplied. |
| Real-engine glasses mapping, playback, and freshness retest | PASS — operator-reported, pipeline corroborated | After localhost Start recovery, saved state contained spoken finals, fresh AI queues, and AI-origin played Q-5/PQ-07 and Q-7/PQ-31. Server metrics were 37 ms / 13 ms to browser audio start. Hrishi confirmed “it works” after the final triple-tap repeat and stale-queue freshness instructions, and asked to stop further C3 checks. No independent acoustic trace; physical latency/repeat/freshness acceptance relies on the operator report. |

## C4: recovery, auto mode, and Client settings

**C4 COMPLETE — ready for `gate/C4-settings` review.** `gate/E1-server` was present before work began. C3 was accepted and tagged by the integrator; no additional C3 device checks were requested.

### Baseline and scope

- Merged `origin/main` at `0189aa8`, refreshed the local Role C instruction copies, and read the updated C4/D5 handoff. Baseline Python suite: **127 passed**, one third-party deprecation warning.
- A temporary queue-recovery/auto-mode check was written before implementation and failed as expected because queues were not persisted. The board's settings section was also observed empty before `settings.js` existed.
- Changed only Role C's interviewer HTML/JS, new `settings.js`, and this log. No board files, backend source, shared instructions, plan, or dependency files were edited by Role C.
- Hrishi explicitly supplied and authorized the local environment update. Values were saved only in ignored, untracked `.env` with owner-only permissions. No credential values appear in this log or the committed files.

### Recovery and auto-mode checks

- Last queue is stored under `fitcheck.queue.<interview_id>` and restored on reload. Storage reads/writes and malformed cached data are caught. Restored questions are displayed, but playback waits for a current-session server queue, preventing old question IDs from being reported as newly played after Start resets the session.
- Auto mode starts off. After a final sentence it waits 2 seconds without new speech, then plays only a top `Contradiction:` question. New speech/interim results, manual taps, disabling auto mode, and terminal microphone errors cancel the pending trigger. A late contradiction queue can use the already elapsed silence deadline; each final triggers at most one automatic play.
- Connection, recognition, and last browser-start latency are displayed together near Start.
- Syntax checks and temporary C2/C3/C4 harnesses: **PASS**. C4 coverage includes restore/current-session gating, blocked localStorage, two-second timing, new-speech and toggle-off cancellation, no repeated firing, manual detail questions, and late contradiction arrival. No microphone or physical glasses test was needed for these automated C4 checks.

### Settings and audit checks

- `settings.js` renders into W's existing `#settings-view`, loads `/api/settings` and `/api/contracts`, and offers the three monitoring/handoff toggles, dynamic contract checkboxes, 30/90-day retention, admin token, Save, reload, and turn-off/purge controls.
- Admin token storage uses shared session key `fitcheck.admin_token`, with every access in try/catch. Saves use `X-Admin-Token` and only changed keys; purge sends exactly `drift_enabled: false, purge: true`. The latest 20 audit entries are shown. Enabling monitoring reveals a staff-notice reminder and Privacy link.
- Temporary settings harness: **PASS** for dynamic approved IDs, empty watch list, token key/header, changed-key payloads, retention, purge payload, 20-entry audit limit, safe text rendering, rejected-token edit preservation, blocked sessionStorage, initial load retry, and successful saves whose audit refresh fails.
- In-app browser against an isolated real FastAPI server and temporary data: **PASS**. Monitoring toggle saved and appeared in audit; reloading retained settings and the tab token; an empty watch list stayed empty; approved C-06 could be selected; retention saved as 90; a wrong token was rejected without losing edits or adding an audit entry. Independent backend inspection confirmed the exact partial-change audit records.
- Purge API was exercised only on a generated temporary live-event fixture: **PASS**, file removed and purge audit recorded. Demo live events were not purged.
- Final demo-server gate check at `http://localhost:8000/board#settings`: **PASS**. The UI enabled monitoring; an independent GET confirmed `drift_enabled: true` and the audit entry. The UI then restored monitoring to its original off value. A second GET confirmed all original settings were restored and audit records contained only the on/off changes. Token fields remained masked.
- Native Chrome automation was unavailable because the Mac was locked; the in-app browser remained available and completed the settings UI checks. No OS audio settings were changed.

### Final integration and handoff

- Merged `origin/main` through `f2899cd`, including the E4-lineage gate. Full merged-branch suite with fake LLM and empty vendor-key overrides: **129 passed**, one third-party deprecation warning, in 65.01 seconds. Vendor overrides applied only to the test process, not `.env` or the demo server.
- Demo server restarted on `127.0.0.1:8000` and loaded the authorized `.env`. Saved settings preview: `/private/tmp/fit-check-c4-settings.png` (not a repo file).
- Gate to request: **`gate/C4-settings`**. Only Keshav (W) merges to main and tags it. After C4, the remaining team milestones are integration, the CP3 fix list, and rehearsals as the demo operator.
