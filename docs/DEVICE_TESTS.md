# C1 device tests

Date: 2026-11-08. Operator: Hrishi (C). Laptop: the demo MacBook, with the Meta glasses paired.

## Status

**STOPPED — FAIL: T2 (wrong microphone).** Hrishi reported “its using glasses as mic” during the T2 input check. The agent instructed Hrishi to stop `c1Mic` tracks immediately; release has not yet been confirmed. No further device tests should run until the MacBook input is restored and explicitly verified. T1's exact counts and timing, T3, and T4 remain unconfirmed. Do not request `gate/C1-devices` yet.

## Preparation

1. In macOS System Settings → Sound, verify Input is **MacBook Microphone** and Output is **the glasses**. Do not use the glasses microphone. Stop and tell Hrishi if either setting needs changing.
2. Close Music, Spotify, and other tabs playing media. Wear the glasses.
3. Before `gate/E1-server`, run `python3 -m http.server 8000 --bind 127.0.0.1` from `server/`. Open **Google Chrome** at `http://localhost:8000/static/interviewer.html` in its own visible window.
4. Click **Start interview**. The status must say that the silent loop is playing. Open Chrome's Console with Command–Option–J. Use only synthetic role-play and obtain the reader's consent before recording/transcription.

## Results

| Test | Result | Notes |
|---|---|---|
| T1: taps | WORKING — details pending | Hrishi's response to the T1 instructions: “it works”. Need explicit confirmation of `play`, `next`, `repeat`, respectively, 10/10 each within 0.5 s before marking PASS. |
| T2: voice with microphone in use | FAIL — wrong microphone | Hrishi reported “its using glasses as mic” after the default-device capture probe. Instructed to stop tracks immediately; stop not yet confirmed. Voice quality and taps with the correct microphone remain untested. |
| T3: transcription at 0.7 m | PENDING | Need 10 role-play lines, with “prior auth”, “notes”, “denial”, and “coverage” transcribed correctly. |
| T4: call-mode guard | BLOCKED | T2 selected the glasses microphone. System Sound routing itself has not been visually verified; restore and verify MacBook input before retesting. |

### T1: taps

With Start clicked and the glasses worn, perform 10 single taps, then 10 double taps, then 10 triple taps. Leave enough time between trials to distinguish each gesture. The page shows the last received action, and the Console logs `tap play`, `tap next`, or `tap repeat`. `pause` media events also map to `play`.

Report correct/total counts separately for all three gestures, any wrong or missed actions, and whether each event appeared within 0.5 s of the gesture. Page timestamps show receipt time, not physical tap latency; the operator must observe latency. Button and spacebar checks are separate fallback checks, not evidence that glasses taps work.

If T1 fails, stop and tell Hrishi. The plan permits one retry after closing other media apps/tabs and clicking Start again. If that also fails, record **FAIL: T1**, inform Hrishi immediately, and use spacebar / Ask next (and auto mode once implemented).

### T2 and T4: microphone, voice, and route

**Do not rerun the default-device probe below:** it selected the glasses microphone on this laptop. It is retained as the record of the failed test. Before retrying, Hrishi must restore Input = MacBook Microphone and Output = glasses, and the next capture must select the actual MacBook device ID explicitly. Do not change system audio settings without Hrishi's approval.

```js
window.c1Mic = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: { exact: 'default' } } });
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

This is a temporary device probe, not C2's server-connected transcription. In Chrome's Console:

```js
window.c1Recognition = new webkitSpeechRecognition();
c1Recognition.continuous = true;
c1Recognition.interimResults = true;
c1Recognition.lang = 'en-US';
c1Recognition.onresult = event => {
  for (let i = event.resultIndex; i < event.results.length; i++) {
    if (event.results[i].isFinal) console.log('T3 final:', event.results[i][0].transcript);
  }
};
c1Recognition.onerror = event => console.error('T3 recognition error:', event.error);
c1Recognition.onend = () => console.log('T3 recognition ended; restart if the 10 lines are unfinished.');
c1Recognition.start();
```

A consenting person 0.7 m from the laptop reads 10 lines from `legacy/scripts/billing_clerk_2.md` or another supplied role-play script. Include the four target terms above. Record the lines used, number captured, and actual recognition of each target term. A recognition error or an incorrect required term is a failed test, not PASS. Stop afterward:

```js
c1Recognition.stop();
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

T2 failed its microphone check and testing is stopped. T1's exact counts and latency, T3, and T4 remain pending. Do not treat the software checks as `gate/C1-devices` approval.
