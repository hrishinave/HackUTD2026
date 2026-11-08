let T0 = Date.now();
const now = () => Date.now() - T0;
let lastFinalT = 0;
let running = false;
let playing = false;
const INTERVIEW_ID = new URLSearchParams(location.search).get('id') || 'INT-01';
let ws;
const outbox = [];
let reconnectTimer;
let recognitionTimer;
let recognitionActive = false;
let recognitionRetryMs = 0;
let starting = false;
let sessionStarted = false;

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const rec = Recognition ? new Recognition() : null;

if (rec) {
  rec.continuous = true;
  rec.interimResults = true;
  rec.lang = 'en-US';
  rec.onstart = () => {
    recognitionActive = true;
    document.getElementById('recognition-status').textContent = 'Transcription: listening.';
  };
  rec.onresult = (event) => {
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      if (!result.isFinal || playing) continue;
      const text = result[0].transcript.trim();
      if (!text) continue;
      lastFinalT = now();
      send({ type: 'utterance', text, final: true, t_ms: lastFinalT });
      document.getElementById('last-final').textContent = text;
    }
  };
  rec.onend = () => {
    recognitionActive = false;
    if (!running) return;
    clearTimeout(recognitionTimer);
    recognitionTimer = setTimeout(() => {
      recognitionTimer = null;
      if (running) startRecognition();
    }, recognitionRetryMs);
    recognitionRetryMs = 0;
  };
  rec.onerror = (event) => {
    if (['not-allowed', 'service-not-allowed', 'audio-capture'].includes(event.error)) {
      running = false;
      clearTimeout(recognitionTimer);
      document.getElementById('recognition-status').textContent =
        'Transcription: microphone permission denied or input unavailable. Check Chrome’s MacBook microphone selection before reloading.';
    } else if (event.error === 'network') {
      recognitionRetryMs = 1000;
      document.getElementById('recognition-status').textContent = 'Transcription: network error; retrying in one second.';
    } else {
      document.getElementById('recognition-status').textContent = `Transcription: ${event.error}; waiting to restart.`;
    }
    console.error('Recognition error:', event.error);
  };
}

function startRecognition() {
  if (!rec) {
    document.getElementById('recognition-status').textContent = 'Transcription is unavailable. Open this page in Google Chrome.';
    return;
  }
  running = true;
  if (recognitionActive) return;
  try {
    rec.start();
    recognitionActive = true;
    document.getElementById('recognition-status').textContent = 'Transcription: starting…';
  } catch (error) {
    running = false;
    document.getElementById('recognition-status').textContent = 'Transcription could not start. Check the microphone and reload.';
    console.error('Recognition start failed:', error);
  }
}

let queue = { based_on_t_ms: 0, questions: [] };
let lastPlayed = null;
const clips = Object.create(null);
const player = new Audio();
let lastTapToAudioMs = null;
let playbackSerial = 0;
let playbackTailTimer;
let tapPending = false;

function render() {
  const rows = queue.questions.map((question) => {
    const row = document.createElement('li');
    const cue = document.createElement('strong');
    const text = document.createElement('p');
    const target = document.createElement('small');
    cue.textContent = question.cue;
    text.textContent = question.text;
    target.textContent = question.target;
    row.append(cue, text, target);
    return row;
  });
  document.getElementById('queue').replaceChildren(...rows);
  document.getElementById('queue-empty').hidden = rows.length > 0;
  document.getElementById('ask').disabled = !sessionStarted || rows.length === 0;
  document.getElementById('latency').textContent = lastTapToAudioMs === null
    ? 'Last tap to audio: —'
    : `Last tap to audio: ${lastTapToAudioMs} ms`;
}

let onServer = (msg) => {
  console.log('server', msg);
  if (msg.type === 'queue') {
    queue = { based_on_t_ms: msg.based_on_t_ms, questions: msg.questions.slice() };
    render();
  } else if (msg.type === 'audio') {
    clips[msg.question_id] = `data:audio/mpeg;base64,${msg.mp3_b64}`;
  }
};

function speak(question, tapT) {
  const serial = ++playbackSerial;
  clearTimeout(playbackTailTimer);
  // New taps may replace playback. Ignore callbacks from the replaced question.
  player.onplaying = null;
  player.onended = null;
  player.onerror = null;
  player.pause();
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  playing = true;
  let reported = false;
  let voiceAttempted = false;
  const status = document.getElementById('playback-status');
  status.textContent = 'Starting question…';

  const started = () => {
    if (serial !== playbackSerial || reported) return;
    reported = true;
    lastTapToAudioMs = now() - tapT;
    send({ type: 'metric', name: 'tap_to_audio_ms', value: lastTapToAudioMs });
    // Lineage should record playback when audio actually starts, not an attempt.
    send({ type: 'played', question_id: question.id, t_ms: now() });
    lastPlayed = question;
    status.textContent = `Playing: ${question.cue} ${question.text}`;
    render();
  };
  const done = () => {
    if (serial !== playbackSerial) return;
    clearTimeout(playbackTailTimer);
    playbackTailTimer = setTimeout(() => {
      if (serial !== playbackSerial) return;
      playing = false;
      status.textContent = reported ? 'Ready for the next question.' : 'Question could not play. Check the browser audio and report the error.';
    }, 300);
  };
  const browserVoice = () => {
    if (serial !== playbackSerial || voiceAttempted) return;
    voiceAttempted = true;
    if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === 'undefined') {
      done();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(`${question.cue} ${question.text}`);
    utterance.rate = 1.05;
    utterance.volume = 0.6;
    utterance.onstart = started;
    utterance.onend = done;
    utterance.onerror = (event) => {
      console.error('Question voice failed:', event.error);
      done();
    };
    try {
      window.speechSynthesis.speak(utterance);
    } catch (error) {
      console.error('Question voice could not start:', error);
      done();
    }
  };

  const source = clips[question.id] || question.audio_url;
  if (source) {
    player.src = source;
    player.onplaying = started;
    player.onended = done;
    player.onerror = browserVoice;
    try {
      player.play().catch(browserVoice);
    } catch (error) {
      browserVoice();
    }
  } else {
    browserVoice();
  }
  render();
}

function waitForFresh(maxMs) {
  return new Promise((resolve) => {
    if (queue.based_on_t_ms >= lastFinalT) return resolve();
    const started = Date.now();
    const timer = setInterval(() => {
      if (queue.based_on_t_ms >= lastFinalT || Date.now() - started >= maxMs) {
        clearInterval(timer);
        resolve();
      }
    }, 50);
  });
}

function connect() {
  if (ws && (ws.readyState === 0 || ws.readyState === 1)) return;
  clearTimeout(reconnectTimer);
  document.getElementById('connection-status').textContent = 'Connection: connecting…';
  const socket = new WebSocket(`ws://localhost:8000/ws/client/${encodeURIComponent(INTERVIEW_ID)}`);
  ws = socket;
  socket.onopen = () => {
    if (ws !== socket) return;
    socket.send(JSON.stringify({ type: 'hello', device: 'laptop-chrome', app_version: '0.1' }));
    while (outbox.length && socket.readyState === 1) socket.send(outbox.shift());
    document.getElementById('connection-status').textContent = 'Connection: connected.';
  };
  socket.onmessage = (event) => {
    if (ws !== socket) return;
    try {
      onServer(JSON.parse(event.data));
    } catch (error) {
      console.error('Server message could not be read:', error);
    }
  };
  socket.onclose = () => {
    if (ws !== socket) return;
    document.getElementById('connection-status').textContent = 'Connection: disconnected; retrying in one second.';
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 1000);
  };
  socket.onerror = () => {
    if (ws === socket) document.getElementById('connection-status').textContent = 'Connection: error; waiting to reconnect.';
  };
}

function send(obj) {
  const message = JSON.stringify(obj);
  if (ws && ws.readyState === 1) ws.send(message);
  else outbox.push(message);
}

let onTap = async (action) => {
  if (!sessionStarted || !['play', 'next', 'repeat'].includes(action)) return;
  const tapT = now();
  console.log('tap', action);
  document.getElementById('tap-output').textContent =
    `Last action: ${action} · ${new Date().toLocaleTimeString()}`;
  send({ type: 'tap', action, t_ms: tapT });
  if (tapPending) return;
  if (action === 'repeat') {
    if (lastPlayed) speak(lastPlayed, tapT);
    else document.getElementById('playback-status').textContent = 'No question has played yet.';
    return;
  }
  tapPending = true;
  try {
    if (queue.based_on_t_ms < lastFinalT) {
      document.getElementById('playback-status').textContent = 'Waiting up to one second for a fresh question…';
    }
    await waitForFresh(1000);
    const question = action === 'next' ? queue.questions[1] : queue.questions[0];
    if (!question) {
      document.getElementById('playback-status').textContent = action === 'next'
        ? 'No second question queued. Single tap asks the top question.'
        : 'Waiting for a question from the server.';
      return;
    }
    queue.questions = queue.questions.filter(item => item.id !== question.id);
    speak(question, tapT);
  } finally {
    tapPending = false;
  }
};

function startMediaKeys() {
  const status = document.getElementById('status');
  if (!navigator.mediaSession || typeof MediaMetadata === 'undefined') {
    status.textContent = 'Media keys are unavailable. Use Google Chrome; Ask next and spacebar still log actions.';
    return;
  }

  const silence = document.getElementById('silence');
  silence.volume = 0.01;
  // Start playback inside the click handler so Chrome permits audio.
  const playback = silence.play();
  navigator.mediaSession.metadata = new MediaMetadata({ title: 'Fit Check interview' });
  navigator.mediaSession.playbackState = 'playing';
  navigator.mediaSession.setActionHandler('play', () => onTap('play'));
  navigator.mediaSession.setActionHandler('pause', () => onTap('play'));
  navigator.mediaSession.setActionHandler('nexttrack', () => onTap('next'));
  navigator.mediaSession.setActionHandler('previoustrack', () => onTap('repeat'));

  status.textContent = 'Starting the silent loop…';
  playback.then(() => {
    status.textContent = 'Silent loop playing. Glasses media controls ready.';
  }).catch((error) => {
    navigator.mediaSession.playbackState = 'none';
    status.textContent = 'Audio could not start. Click Start interview to retry and report the error.';
    console.error('Silent loop failed:', error);
  });
}

document.getElementById('start').onclick = async () => {
  if (starting || sessionStarted) return;
  starting = true;
  T0 = Date.now();
  lastFinalT = 0;
  outbox.length = 0;
  const start = document.getElementById('start');
  const interviewee = document.getElementById('interviewee');
  start.disabled = true;
  interviewee.disabled = true;
  try {
    // Keep audio and recognition inside the user gesture. Buffer finals until
    // /start completes, so resetting the server cannot discard early speech.
    startMediaKeys();
    startRecognition();
    document.getElementById('connection-status').textContent = 'Connection: starting interview…';
    const response = await fetch(`/api/interviews/${encodeURIComponent(INTERVIEW_ID)}/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interviewee: interviewee.value })
    });
    if (!response.ok) throw new Error(`Interview start returned HTTP ${response.status}`);
    connect();
    sessionStarted = true;
    render();
    start.textContent = 'Interview started';
  } catch (error) {
    sessionStarted = false;
    running = false;
    clearTimeout(recognitionTimer);
    if (rec) rec.stop();
    recognitionActive = false;
    outbox.length = 0;
    document.getElementById('silence').pause();
    if (navigator.mediaSession) navigator.mediaSession.playbackState = 'none';
    document.getElementById('status').textContent = 'Silent loop stopped.';
    document.getElementById('connection-status').textContent = 'Connection: interview could not start. Click Start interview to retry.';
    document.getElementById('recognition-status').textContent = 'Transcription: stopped after interview setup failed.';
    start.disabled = false;
    interviewee.disabled = false;
    console.error('Interview start failed:', error);
  } finally {
    starting = false;
  }
};
document.getElementById('ask').onclick = () => onTap('play');
document.addEventListener('keydown', (event) => {
  if (event.code !== 'Space' || event.repeat) return;
  // Let focused buttons keep their native keyboard activation.
  const target = event.target;
  if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT|BUTTON|A)$/.test(target.tagName))) return;
  event.preventDefault();
  onTap('play');
});
