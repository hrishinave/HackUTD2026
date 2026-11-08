# C1 device tests

Date: 2026-11-08. Operator: Hrishi (C). Laptop: the demo MacBook, with the Meta glasses paired.

## Status

**T2 retry, T3, and T4 PASS (operator-reported); C1 incomplete.** Hrishi replied “works” to the explicit-MacBook microphone retry and its voice, tap, and routing checks, then “yes t3 works” to the transcription test. The first T2 failure is retained below. T1's exact counts and timing remain unconfirmed. Do not request `gate/C1-devices` yet.

## Preparation

1. In macOS System Settings → Sound, verify Input is **MacBook Microphone** and Output is **the glasses**. Do not use the glasses microphone. Stop and tell Hrishi if either setting needs changing.
2. Close Music, Spotify, and other tabs playing media. Wear the glasses.
3. Before `gate/E1-server`, run `python3 -m http.server 8000 --bind 127.0.0.1` from `server/`. Open **Google Chrome** at `http://localhost:8000/static/interviewer.html` in its own visible window.
4. Click **Start interview**. The status must say that the silent loop is playing. Open Chrome's Console with Command–Option–J. Use only synthetic role-play and obtain the reader's consent before recording/transcription.

## Results

| Test | Result | Notes |
|---|---|---|
| T1: taps | WORKING — details pending | Hrishi's response to the T1 instructions: “it works”. Need explicit confirmation of `play`, `next`, `repeat`, respectively, 10/10 each within 0.5 s before marking PASS. |
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

T2 passed on retry, and T3 and T4 passed according to Hrishi's reports; the original T2 failure is retained. T1's exact counts and latency remain pending. Do not treat the software checks as `gate/C1-devices` approval.
