(() => {
  const views = {
    interview: { title: "Interview", endpoint: "/api/interviews/INT-01/state", mock: "/static/mock/state.json" },
    contracts: { title: "Contracts", endpoint: "/api/contracts", mock: "/static/mock/contracts.json" },
    drift: { title: "Drift", endpoint: "/api/drift", mock: "/static/mock/drift.json" },
    finding: { title: "Finding detail", endpoint: "/api/findings", mock: "/static/mock/findings.json" },
    settings: { title: "Client settings" }
  };
  const useMocks = new URLSearchParams(window.location.search).get("mock") === "1";
  let selectedInterview = "";
  let selectedPerson = "billing_clerk_2";
  let selectedCompany = "medicare_billing_demo";
  let selectedCompanyName = "";
  let recognition;
  const byId = (id) => document.getElementById(id);
  const title = byId("page-title");
  const status = byId("connection-status");
  const navigation = [...document.querySelectorAll("[data-route]")];
  const received = new Map();
  const linkedEvidence = new Map();
  let generation = 0;
  let controller;
  let pollTimer;
  let focusedLineage = "";
  const charts = [];
  let lastDrift;
  let feedbackPayload;
  let drawerGeneration = 0;
  const settingsResource = { endpoint: "/api/settings", mock: "/static/mock/settings.json" };
  const draftsResource = { endpoint: "/api/drafts", mock: "/static/mock/drafts.json" };
  const lifecycleResource = { endpoint: "/api/lifecycle", mock: "/static/mock/lifecycle.json" };
  const STAGES = ["drafted", "approved", "baselined", "outcome", "renegotiated"];
  let feedbackFinding;
  const mockFiled = new Map();
  const requirementCache = new Map();
  const ADMIN_TOKEN_KEY = "pact.admin_token";

  // Company-scoped Pact routes get ?company_id= for the company selected on the board.
  const SCOPED_PATH = /^\/api\/(settings|drift|findings|lifecycle|filed|contracts|drafts)(\/|\?|$)/;
  const DEMO_COMPANY = "medicare_billing_demo";
  function scopedPath(path) {
    if (useMocks || !SCOPED_PATH.test(path)) return path;
    return path + (path.includes("?") ? "&" : "?") + "company_id=" + encodeURIComponent(selectedCompany);
  }

  // Live route first; while a teammate's route is not merged yet (FastAPI's bare "Not Found"), use the preview file.
  async function liveOrPreview(endpoint, mock, init = {}) {
    if (useMocks) return { response: await fetch(mock, { signal: init.signal, cache: "no-store" }), preview: true };
    const response = await fetch(scopedPath(endpoint), { cache: "no-store", ...init });
    if (response.status === 404 || response.status === 405) {
      const body = await response.clone().json().catch(() => null);
      if (body?.detail === "Not Found" || body?.detail === "Method Not Allowed") return { response: await fetch(mock, { signal: init.signal, cache: "no-store" }), preview: true };
    }
    return { response, preview: false };
  }

  async function readLifecycle(signal) {
    try {
      const { response, preview } = await liveOrPreview(lifecycleResource.endpoint, lifecycleResource.mock, { signal, headers: { Accept: "application/json" } });
      if (!response.ok) return null;
      return { stages: await response.json(), preview };
    } catch { return null; }
  }

  function stageStrip(entry) {
    const strip = element("ol", null, "stage-strip");
    strip.setAttribute("aria-label", "Contract lifecycle");
    const reached = entry?.stages || {};
    const outcome = reached.broken ? "broken" : reached.kept ? "kept" : "kept or broken";
    for (const name of STAGES) {
      const label = name === "outcome" ? outcome : name;
      const isReached = name === "outcome" ? Boolean(reached.broken || reached.kept) : reached[name] === true;
      const isCurrent = entry && (name === "outcome" ? ["kept", "broken"].includes(entry.stage) : entry.stage === name);
      const item = element("li", label, "stage");
      item.dataset.reached = String(isReached);
      if (name === "outcome" && reached.broken) item.dataset.broken = "true";
      if (isCurrent) { item.setAttribute("aria-current", "step"); item.append(element("span", "current", "stage-current")); }
      strip.append(item);
    }
    if (entry?.detail?.watching === "off") strip.append(element("li", "usage watching off", "stage-note"));
    return strip;
  }

  async function loadRequirement(contract, panel) {
    const pre = panel.querySelector("pre");
    const note = panel.querySelector(".requirement-note");
    if (requirementCache.has(contract.id)) { pre.textContent = requirementCache.get(contract.id); return; }
    pre.textContent = "Loading requirement document…";
    try {
      const { response, preview } = await liveOrPreview("/api/contracts/" + encodeURIComponent(contract.id) + "/sf-requirement", "/static/mock/sf-requirement.md", { signal: AbortSignal.timeout(6000) });
      if (!response.ok) throw new Error("unavailable");
      const text = await response.text();
      requirementCache.set(contract.id, text);
      pre.textContent = text;
      if (preview) note.textContent = "Preview sample (C-01). The live export appears once the requirement route is merged.";
      panel.querySelectorAll("button").forEach((button) => { button.disabled = false; });
    } catch { pre.textContent = "Requirement document unavailable. Try again in a moment."; }
  }

  function requirementView(contract) {
    const details = element("details", null, "requirement-view");
    details.append(element("summary", "Requirement view"));
    const panel = element("div", null, "requirement-panel");
    panel.append(element("p", "Software Factory Feature Requirements document. Add it to your project.", "muted-copy"));
    const actions = element("div", null, "draft-actions");
    const download = element("button", "Download (.md)", "primary-button"); download.type = "button"; download.disabled = true;
    const copy = element("button", "Copy", "secondary-button"); copy.type = "button"; copy.disabled = true;
    const status = element("span", "", "question-meta"); status.setAttribute("role", "status");
    actions.append(download, copy, status);
    panel.append(actions, element("p", "", "requirement-note question-meta"), element("pre", "", "payload requirement-doc"));
    download.addEventListener("click", () => {
      const text = requirementCache.get(contract.id); if (!text) return;
      const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
      const link = element("a"); link.href = url; link.download = (contract.requirement?.id || "requirement") + "-" + contract.id + ".md";
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    copy.addEventListener("click", async () => {
      const text = requirementCache.get(contract.id); if (!text) return;
      try { await navigator.clipboard.writeText(text); status.textContent = "Copied"; }
      catch { status.textContent = "Copy is blocked here. Use Download instead."; }
    });
    details.addEventListener("toggle", () => { if (details.open) loadRequirement(contract, panel); });
    details.append(panel);
    return details;
  }
  const droppedByInterview = new Map();
  let draftRecords = [];
  let mockDraftBundle;
  let mockApprovedContracts = [];
  let draftBusy = false;
  let decisionBusy = false;
  const dialogResolvers = new Map();

  function interviewConfig() {
    return { title: "Interview", endpoint: "/api/interviews/" + encodeURIComponent(selectedInterview) + "/state", mock: "/static/mock/state.json" };
  }

  // Saved and running interviews from GET /api/interviews, newest first.
  let interviewItems = [];
  const interviewNumber = (id) => Number(/^INT-(\d+)$/.exec(id || "")?.[1] || 0);
  const interviewCompany = (item) => item?.company_id || DEMO_COMPANY;
  const interviewIdentity = (item) => item.person_name || item.label || item.interviewee || "Interview";

  function companyLabel() {
    const item = interviewItems.find((entry) => interviewCompany(entry) === selectedCompany && entry.company_name);
    return selectedCompanyName || item?.company_name || (selectedCompany === DEMO_COMPANY ? "Medicare Billing Office" : selectedCompany.replaceAll("_", " "));
  }

  function companyInterviews() {
    return useMocks ? interviewItems : interviewItems.filter((item) => interviewCompany(item) === selectedCompany);
  }

  // The Contracts tab's "Saved interview" select: every interview for the selected company, newest first.
  function populateDraftInterviews(preferId) {
    const select = byId("draft-interview");
    const previous = preferId || select.value;
    const items = companyInterviews();
    byId("draft-company").textContent = "Company: " + companyLabel();
    if (!items.length) {
      const option = element("option", "No interviews for " + companyLabel() + " yet"); option.value = "";
      select.replaceChildren(option);
    } else {
      select.replaceChildren(...items.map((item) => {
        const option = element("option", [item.interview_id, interviewIdentity(item), item.position].filter(Boolean).join(" · "));
        option.value = item.interview_id; return option;
      }));
      const fallback = items.find((item) => item.interview_id === selectedInterview)?.interview_id || items[0].interview_id;
      select.value = items.some((item) => item.interview_id === previous) ? previous : fallback;
    }
    renderDrafts();
  }

  // The company changed (start dialog, picking a past interview): rescope the Contracts tab.
  function companyChanged() {
    received.delete("contracts:"); received.delete("drift:");
    draftRecords = [];
    populateDraftInterviews();
    if (currentRoute().name === "contracts") showRoute();
  }

  async function loadInterviewList() {
    const picker = byId("interview-picker");
    if (!picker) return;
    try {
      const response = await fetch(useMocks ? "/static/mock/interviews.json" : "/api/interviews", { cache: "no-store" });
      if (!response.ok) throw new Error("Interview list unavailable");
      const interviews = await response.json();
      interviewItems = (Array.isArray(interviews) ? interviews : []).filter((item) => item?.interview_id).sort((a, b) => interviewNumber(b.interview_id) - interviewNumber(a.interview_id));
      picker.replaceChildren();
      populateDraftInterviews();
      if (!interviewItems.length) {
        picker.append(element("option", "No past interviews yet"));
        picker.disabled = true; byId("interview-transcript").disabled = true;
        return;
      }
      picker.disabled = false;
      for (const interview of interviewItems) {
        const option = element("option", [interview.interview_id, interview.company_name, interviewIdentity(interview), interview.position].filter(Boolean).join(" · "));
        option.value = interview.interview_id;
        picker.append(option);
      }
      if (!interviewItems.some((item) => item.interview_id === selectedInterview)) {
        selectedInterview = (interviewItems.find((item) => interviewCompany(item) === selectedCompany) || interviewItems[0]).interview_id;
      }
      picker.value = selectedInterview;
      byId("interview-transcript").disabled = false;
      if (currentRoute().name === "interview") showRoute();
    } catch {
      picker.replaceChildren(element("option", "Could not load past interviews"));
      byId("draft-interview").replaceChildren(element("option", "Could not load interviews"));
    }
  }

  async function loadInterviewOptions() {
    const companyPicker = byId("company-picker");
    if (!companyPicker) return;
    try {
      const response = await fetch(useMocks ? "/static/mock/interview-options.json" : "/api/interview-options", { cache: "no-store" });
      if (!response.ok) throw new Error("Interview options unavailable");
      const data = await response.json();
      const options = byId("company-options");
      options.replaceChildren(...(data.companies || []).map((company) => {
        const option = element("option"); option.value = company.name; option.dataset.companyId = company.id; return option;
      }));
      const existing = (data.companies || []).find((company) => company.id === selectedCompany);
      companyPicker.value = selectedCompanyName || existing?.name || "";
      selectedCompanyName = companyPicker.value;
      companyPicker.addEventListener("input", () => {
        selectedCompanyName = companyPicker.value.trim();
        const match = (data.companies || []).find((company) => company.name.toLowerCase() === selectedCompanyName.toLowerCase());
        const next = match?.id || selectedCompanyName.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "new_client";
        if (next !== selectedCompany) { selectedCompany = next; companyChanged(); }
      });
    } catch {
      companyPicker.placeholder = "Enter a new company name";
      byId("person-name").placeholder = "Enter person's name";
    }
  }

  // ---- Live interview: speech in, question queue out, glasses media keys ----
  // Times sent to the server are milliseconds since the interview began (live.T0), never wall clock.
  const live = {
    active: false, starting: false, id: "", T0: Date.now(), ws: null, outbox: [], reconnectTimer: null,
    queue: { based_on_t_ms: 0, questions: [] }, queueReady: false, lastFinalT: 0, lastPlayed: null,
    clips: Object.create(null), playing: false, tapPending: false, serial: 0, tailTimer: null,
    lastTapToAudioMs: null, recognitionActive: false, recognitionTimer: null, recognitionRetryMs: 0,
    ending: false, onRecognitionEnd: null, sentCount: 0, ignoredWhilePlaying: 0, heardTimer: null,
    playingWatchdog: null, utterance: null
  };
  const liveNow = () => Date.now() - live.T0;
  const player = new Audio();
  let nextIdPromise = null;
  const setLive = (id, text) => { const node = byId(id); if (node) node.textContent = text; };
  const clipWaiters = new Map(); // question_id -> resolvers waiting for its pushed ElevenLabs clip

  // The server pushes each question's audio ~0.3-1 s after the queue. Resolve as soon as it arrives, or after maxMs.
  function waitForClip(questionId, maxMs) {
    if (live.clips[questionId]) return Promise.resolve(true);
    return new Promise((resolve) => {
      const finish = (arrived) => {
        clearTimeout(timer);
        const list = clipWaiters.get(questionId) || [];
        const remaining = list.filter((item) => item !== finish);
        if (remaining.length) clipWaiters.set(questionId, remaining); else clipWaiters.delete(questionId);
        resolve(arrived);
      };
      const timer = setTimeout(() => finish(false), maxMs);
      clipWaiters.set(questionId, [...(clipWaiters.get(questionId) || []), finish]);
    });
  }

  async function fetchNextInterviewId() {
    if (!useMocks) {
      try {
        const response = await fetch("/api/interviews/next-id", { cache: "no-store" });
        if (response.ok) {
          const data = await response.json();
          if (/^INT-\d{2,}$/.test(data?.interview_id || "")) return data.interview_id;
        }
      } catch { /* Fall back to the interview list below. */ }
    }
    const response = await fetch(useMocks ? "/static/mock/interviews.json" : "/api/interviews", { cache: "no-store" });
    if (!response.ok) throw new Error("Could not choose an interview ID. Check the local server and try again.");
    let max = 0;
    for (const item of await response.json()) {
      const match = /^INT-(\d+)$/.exec(item?.interview_id || "");
      if (match) max = Math.max(max, Number(match[1]));
    }
    if (live.id) max = Math.max(max, Number(/^INT-(\d+)$/.exec(live.id)?.[1] || 0));
    return "INT-" + String(max + 1).padStart(2, "0");
  }

  function prefetchNextId() { nextIdPromise = fetchNextInterviewId().catch(() => null); }

  function renderLive() {
    const rows = live.queue.questions.slice(0, 3).map((question, index) => {
      const row = element("li");
      row.append(element("span", (index === 0 ? "NEXT · " : index === 1 ? "SECOND · " : "THIRD · ") + (question.cue || "Detail:"), "queue-cue"));
      row.append(element("p", question.text || ""));
      row.append(element("span", [question.id, question.target].filter(Boolean).join(" · "), "question-meta id"));
      return row;
    });
    if (!rows.length) rows.push(element("li", live.active ? "Waiting for a question from the interview engine." : "No live interview.", "empty-copy"));
    byId("live-queue").replaceChildren(...rows);
    const ready = live.active && live.queueReady;
    byId("live-ask").disabled = !ready || !live.queue.questions.length;
    byId("live-skip").disabled = !ready || live.queue.questions.length < 2;
    byId("live-repeat").disabled = !live.active || !live.lastPlayed;
    byId("live-end").disabled = !live.active || live.ending;
    setLive("live-latency", live.lastTapToAudioMs === null ? "—" : live.lastTapToAudioMs + " ms");
    setLive("live-id", live.id || "");
  }

  function liveSend(message) {
    const text = JSON.stringify(message);
    if (live.ws && live.ws.readyState === WebSocket.OPEN) live.ws.send(text);
    else if (live.active) live.outbox.push(text);
  }

  function connectLive() {
    if (!live.active || !live.id) return;
    if (live.ws && (live.ws.readyState === WebSocket.CONNECTING || live.ws.readyState === WebSocket.OPEN)) return;
    clearTimeout(live.reconnectTimer);
    setLive("live-connection", "connecting…");
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(scheme + "//" + location.host + "/ws/client/" + encodeURIComponent(live.id));
    live.ws = socket;
    socket.onopen = () => {
      if (live.ws !== socket) return;
      socket.send(JSON.stringify({ type: "hello", device: "laptop-chrome", client: "consultancy-board", app_version: "0.2" }));
      while (live.outbox.length && socket.readyState === WebSocket.OPEN) socket.send(live.outbox.shift());
      setLive("live-connection", "connected");
    };
    socket.onmessage = (event) => {
      if (live.ws !== socket) return;
      try { onLiveMessage(JSON.parse(event.data)); } catch (error) { console.error("Server message could not be read:", error); }
    };
    socket.onclose = () => {
      if (live.ws !== socket || !live.active) return;
      setLive("live-connection", "disconnected; reconnecting in one second");
      clearTimeout(live.reconnectTimer);
      live.reconnectTimer = setTimeout(connectLive, 1000);
    };
    socket.onerror = () => { if (live.ws === socket) setLive("live-connection", "error; waiting to reconnect"); };
  }

  function onLiveMessage(message) {
    if (message.type === "queue") {
      live.queue = { based_on_t_ms: Number(message.based_on_t_ms) || 0, questions: (message.questions || []).slice(0, 3) };
      live.queueReady = true;
      renderLive();
    } else if (message.type === "audio" && message.question_id && message.mp3_b64) {
      live.clips[message.question_id] = "data:audio/mpeg;base64," + message.mp3_b64;
      for (const finish of clipWaiters.get(message.question_id) || []) finish(true);
    } else if (message.type === "ack") {
      if (message.of === "played") setLive("live-ack", "Server recorded " + (message.question_id || "the question") + " as played.");
    }
  }

  function getRecognition() {
    if (recognition !== undefined) return recognition;
    const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = Speech ? new Speech() : null;
    if (!recognition) return null;
    recognition.continuous = true; recognition.interimResults = false; recognition.lang = "en-US";
    recognition.onstart = () => { live.recognitionActive = true; setLive("live-recognition", "listening"); };
    recognition.onresult = (event) => {
      if (!live.active) return;
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        if (!event.results[index].isFinal) continue;
        const text = event.results[index][0].transcript.trim();
        if (!text) continue;
        if (live.playing) { // do not transcribe the question being played; say so instead of dropping it silently
          live.ignoredWhilePlaying += 1;
          setLive("live-recognition", "listening · ignored " + live.ignoredWhilePlaying + " sentence" + (live.ignoredWhilePlaying === 1 ? "" : "s") + " heard while a question played");
          continue;
        }
        live.lastFinalT = liveNow();
        liveSend({ type: "utterance", text, final: true, t_ms: live.lastFinalT });
        live.sentCount += 1;
        clearTimeout(live.heardTimer);
        setLive("live-recognition", "listening · " + live.sentCount + " sentence" + (live.sentCount === 1 ? "" : "s") + " sent");
        setLive("live-last-final", text);
      }
    };
    recognition.onend = () => {
      live.recognitionActive = false;
      if (live.onRecognitionEnd) { live.onRecognitionEnd(); return; } // End interview is flushing the last sentence
      if (!live.active || live.recognitionBlocked || live.ending) return;
      clearTimeout(live.recognitionTimer);
      live.recognitionTimer = setTimeout(() => { live.recognitionTimer = null; if (live.active) startRecognition(); }, live.recognitionRetryMs);
      live.recognitionRetryMs = 0;
    };
    recognition.onerror = (event) => {
      if (["not-allowed", "service-not-allowed"].includes(event.error)) {
        clearTimeout(live.recognitionTimer);
        setLive("live-recognition", "microphone permission denied; allow the microphone for this page in Chrome, then start the interview again");
        live.recognitionBlocked = true;
      } else if (event.error === "audio-capture") {
        // Often transient (a Bluetooth headset switching profiles when a question plays): keep retrying.
        live.recognitionRetryMs = 2000;
        setLive("live-recognition", "no microphone input; check Chrome's microphone selection · retrying in two seconds");
      } else if (event.error === "network") {
        live.recognitionRetryMs = 1000;
        setLive("live-recognition", "network error; retrying in one second");
      } else setLive("live-recognition", event.error + "; restarting");
      console.error("Recognition error:", event.error);
    };
    return recognition;
  }

  function startRecognition() {
    const rec = getRecognition();
    if (!rec) { setLive("live-recognition", "unavailable; open the board in Google Chrome"); return; }
    live.recognitionBlocked = false;
    if (live.recognitionActive) return;
    try { rec.start(); live.recognitionActive = true; setLive("live-recognition", "starting…"); }
    catch (error) { setLive("live-recognition", "could not start; check the microphone"); console.error("Recognition start failed:", error); }
  }

  function startMediaKeys() {
    const silence = byId("silence");
    silence.volume = 0.01;
    // Must run synchronously inside the click/submit gesture, or Chrome blocks audio and media keys never arrive.
    const playback = silence.play();
    if (!navigator.mediaSession || typeof MediaMetadata === "undefined") {
      setLive("live-glasses", "media keys unavailable in this browser; use Ask next or Space");
      return;
    }
    navigator.mediaSession.metadata = new MediaMetadata({ title: "Pact interview", artist: "Pact" });
    navigator.mediaSession.playbackState = "playing";
    navigator.mediaSession.setActionHandler("play", () => onTap("play"));
    navigator.mediaSession.setActionHandler("pause", () => onTap("play"));
    navigator.mediaSession.setActionHandler("nexttrack", () => onTap("next"));
    navigator.mediaSession.setActionHandler("previoustrack", () => onTap("repeat"));
    setLive("live-glasses", "starting silent loop…");
    playback.then(() => { if (live.active) setLive("live-glasses", "ready · tap the glasses to ask"); }).catch((error) => {
      navigator.mediaSession.playbackState = "none";
      setLive("live-glasses", "audio could not start; end and begin the interview again");
      console.error("Silent loop failed:", error);
    });
  }

  function speak(question, tapT) {
    const serial = ++live.serial;
    clearTimeout(live.tailTimer);
    player.onplaying = null; player.onended = null; player.onerror = null;
    player.pause();
    window.speechSynthesis?.cancel();
    live.playing = true;
    // Speech is ignored while a question plays, so never let a missing "ended" event leave it ignored for good.
    clearTimeout(live.playingWatchdog);
    live.playingWatchdog = setTimeout(() => {
      if (serial !== live.serial || !live.playing) return;
      live.playing = false;
      setLive("live-playback", "Question playback did not report its end; listening again.");
    }, 20000);
    let reported = false;
    let voiceAttempted = false;
    setLive("live-playback", "Starting question…");
    const started = () => {
      if (serial !== live.serial || reported) return;
      reported = true;
      live.lastTapToAudioMs = liveNow() - tapT;
      liveSend({ type: "metric", name: "tap_to_audio_ms", value: live.lastTapToAudioMs });
      // Lineage records playback when audio actually starts, not when it was attempted.
      liveSend({ type: "played", question_id: question.id, t_ms: liveNow() });
      live.lastPlayed = question;
      setLive("live-playback", "Playing: " + (question.cue || "") + " " + question.text);
      renderLive();
    };
    const done = () => {
      if (serial !== live.serial) return;
      clearTimeout(live.tailTimer);
      live.tailTimer = setTimeout(() => {
        if (serial !== live.serial) return;
        live.playing = false; clearTimeout(live.playingWatchdog);
        setLive("live-playback", reported ? "Ready for the next question." : "Question could not play. Check the browser audio output.");
      }, 300);
    };
    const browserVoice = () => {
      if (serial !== live.serial || voiceAttempted) return;
      voiceAttempted = true;
      if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === "undefined") { done(); return; }
      const utterance = new SpeechSynthesisUtterance((question.cue || "") + " " + question.text);
      live.utterance = utterance; // Chrome drops onend for garbage-collected utterances
      utterance.rate = 1.05; utterance.volume = 0.6;
      utterance.onstart = started; utterance.onend = done;
      utterance.onerror = (event) => { console.error("Question voice failed:", event.error); done(); };
      try { window.speechSynthesis.speak(utterance); } catch (error) { console.error("Question voice could not start:", error); done(); }
    };
    const source = live.clips[question.id] || question.audio_url;
    if (source) {
      player.src = source;
      player.onplaying = started; player.onended = done; player.onerror = browserVoice;
      try { player.play().catch(browserVoice); } catch { browserVoice(); }
    } else browserVoice();
    renderLive();
  }

  function waitForFresh(maxMs) {
    return new Promise((resolve) => {
      if (live.queue.based_on_t_ms >= live.lastFinalT) return resolve();
      const begun = Date.now();
      const timer = setInterval(() => {
        if (live.queue.based_on_t_ms >= live.lastFinalT || Date.now() - begun >= maxMs) { clearInterval(timer); resolve(); }
      }, 50);
    });
  }

  async function onTap(action) {
    if (!live.active || !live.queueReady || !["play", "next", "repeat"].includes(action)) return;
    const tapT = liveNow();
    setLive("live-last-tap", action + " · " + new Date().toLocaleTimeString());
    liveSend({ type: "tap", action, t_ms: tapT });
    if (live.tapPending) return;
    if (action === "repeat") {
      if (live.lastPlayed) speak(live.lastPlayed, tapT);
      else setLive("live-playback", "No question has played yet.");
      return;
    }
    live.tapPending = true;
    try {
      if (live.queue.based_on_t_ms < live.lastFinalT) setLive("live-playback", "Waiting up to one second for a fresh question…");
      await waitForFresh(1000);
      if (!live.active) return;
      const question = action === "next" ? live.queue.questions[1] : live.queue.questions[0];
      if (!question) {
        setLive("live-playback", action === "next" ? "No second question queued. A single tap asks the top question." : "Waiting for a question from the server.");
        return;
      }
      live.queue.questions = live.queue.questions.filter((item) => item.id !== question.id);
      renderLive();
      if (!live.clips[question.id] && !question.audio_url) {
        live.serial += 1; // stop a finishing earlier question from overwriting this status
        setLive("live-playback", "Waiting for voice…");
        await waitForClip(question.id, 1500);
        if (!live.active) return;
      }
      speak(question, tapT); // tap_to_audio_ms still measures from tapT, so it includes this wait
    } finally { live.tapPending = false; }
  }

  function stopLive(note) {
    live.active = false;
    for (const list of [...clipWaiters.values()]) for (const finish of list) finish(false);
    clearTimeout(live.reconnectTimer); clearTimeout(live.recognitionTimer); clearTimeout(live.tailTimer);
    clearTimeout(live.heardTimer); clearTimeout(live.playingWatchdog); live.utterance = null; live.onRecognitionEnd = null;
    try { recognition?.stop(); } catch { /* already stopped */ }
    live.recognitionActive = false;
    const socket = live.ws; live.ws = null;
    try { socket?.close(); } catch { /* already closed */ }
    live.outbox.length = 0;
    byId("silence").pause();
    live.serial += 1; live.playing = false;
    player.pause(); window.speechSynthesis?.cancel();
    if (navigator.mediaSession) {
      navigator.mediaSession.playbackState = "none";
      for (const action of ["play", "pause", "nexttrack", "previoustrack"]) { try { navigator.mediaSession.setActionHandler(action, null); } catch { /* unsupported */ } }
    }
    setLive("live-glasses", "off"); setLive("live-recognition", "stopped"); setLive("live-connection", "closed");
    setLive("live-playback", note || "Interview ended.");
    renderLive();
  }

  // Called synchronously from the "Begin interview" submit event: audio, media keys and recognition
  // start before the first await so Chrome treats them as part of the user gesture.
  function startNewInterview() {
    if (live.starting) return;
    const button = byId("start-interview-begin");
    const message = byId("start-interview-message");
    const personName = byId("person-name").value.trim();
    const personPosition = byId("person-position").value.trim();
    const companyName = byId("company-picker").value.trim();
    if (!companyName || !personName || !personPosition) { message.textContent = "Enter the company, person's name, and position before starting"; return; }
    selectedCompanyName = companyName;
    if (live.active) stopLive("Previous interview ended.");
    message.textContent = "Starting…";
    button.disabled = true;
    live.starting = true;
    live.active = true;
    live.T0 = Date.now();
    live.lastFinalT = 0; live.outbox.length = 0; live.queue = { based_on_t_ms: 0, questions: [] };
    live.queueReady = false; live.lastPlayed = null; live.clips = Object.create(null); live.lastTapToAudioMs = null; live.id = "";
    live.ending = false; live.sentCount = 0; live.ignoredWhilePlaying = 0;
    setDraftStatus("");
    clearTimeout(live.heardTimer);
    live.heardTimer = setTimeout(() => {
      if (live.active && !live.sentCount && !live.recognitionBlocked) setLive("live-recognition", "no speech heard in 20 seconds; check Chrome's microphone permission and input device");
    }, 20000);
    byId("live-panel").hidden = false;
    setLive("live-connection", "starting interview…"); setLive("live-ack", ""); setLive("live-last-final", "—"); setLive("live-last-tap", "—");
    setLive("live-playback", "Waiting for the first question.");
    startMediaKeys();
    startRecognition();
    renderLive();
    (async () => {
      try {
        const interviewId = (await (nextIdPromise || Promise.resolve(null))) || await fetchNextInterviewId();
        nextIdPromise = null;
        if (!live.active) return;
        live.id = interviewId; renderLive();
        const response = await fetch("/api/interviews/" + encodeURIComponent(interviewId) + "/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ interviewee: selectedPerson, company_id: selectedCompany, company_name: selectedCompanyName, person_name: personName, position: personPosition }) });
        if (!response.ok) throw new Error("Could not start the interview (HTTP " + response.status + ")");
        if (!live.active) return;
        connectLive();
        selectedInterview = interviewId;
        message.textContent = "";
        byId("start-interview-dialog").close();
        await loadInterviewList();
        byId("interview-picker").value = selectedInterview;
        if (currentRoute().name !== "interview" || currentRoute().detail) window.location.hash = "#interview"; else showRoute();
      } catch (error) {
        stopLive("Interview could not start.");
        byId("live-panel").hidden = true;
        message.textContent = error.message || "Could not start the interview";
      } finally { live.starting = false; button.disabled = false; }
    })();
  }

  // Stop recognition and wait for its last final result, so the closing sentence is not lost.
  function flushRecognition(maxMs) {
    clearTimeout(live.recognitionTimer);
    return new Promise((resolve) => {
      if (!recognition || !live.recognitionActive) { resolve(); return; }
      const finish = () => { clearTimeout(timer); live.onRecognitionEnd = null; resolve(); };
      const timer = setTimeout(finish, maxMs);
      live.onRecognitionEnd = finish;
      try { recognition.stop(); } catch { finish(); }
    });
  }

  // "End interview" button only: flush speech, close the interview, then draft contracts in the background.
  async function endInterview() {
    if (!live.active || live.ending || live.starting) return;
    const interviewId = live.id;
    live.ending = true; renderLive();
    setLive("live-playback", "Ending interview: saving the last sentence…");
    await flushRecognition(1500);
    const sent = live.sentCount;
    stopLive("Interview ended.");
    live.ending = false; renderLive();
    if (!interviewId) return;
    await loadInterviewList();
    autoDraft(interviewId, sent);
  }

  function setDraftStatus(text, state = "busy", interviewId = "") {
    for (const id of ["live-draft-status", "draft-auto-status"]) {
      const node = byId(id);
      if (!node) continue;
      node.hidden = !text; node.dataset.state = state;
      node.replaceChildren(text || "");
      if (interviewId) {
        const link = element("a", id === "live-draft-status" ? "Open Contracts" : "Show " + interviewId);
        link.href = "#contracts";
        link.addEventListener("click", () => { populateDraftInterviews(interviewId); });
        node.append(link);
      }
    }
  }

  // POST /api/drafts. Right after an interview ends the saved state can lag a moment, so 404/422 may be retried.
  async function postDrafts(interviewId, attempts = 1) {
    for (let attempt = 1; ; attempt += 1) {
      const response = await fetch(scopedPath("/api/drafts"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ interview_id: interviewId }), signal: AbortSignal.timeout(120000) });
      if (response.ok) return response.json();
      const body = await response.json().catch(() => ({}));
      const detail = typeof body?.detail === "string" ? body.detail : typeof body?.error === "string" ? body.error : "";
      if ((response.status === 404 || response.status === 422) && attempt < attempts) { await new Promise((resolve) => setTimeout(resolve, 1500)); continue; }
      if (response.status === 404) throw new Error(detail && detail !== "Not Found" ? detail : "No saved interview yet for " + interviewId);
      if (response.status === 422) throw new Error(/no transcript/i.test(detail) ? "No transcript yet for " + interviewId + ", so there is nothing to draft." : detail || "The server could not draft " + interviewId);
      if (response.status === 409) throw new Error("Already drafting " + interviewId + ", wait a few seconds");
      throw new Error(detail ? "Drafting failed: " + detail : "Drafting failed, try again; earlier drafts are unchanged");
    }
  }

  async function autoDraft(interviewId, sentCount) {
    if (useMocks) return;
    let lines = 0;
    try {
      const response = await fetch("/api/interviews/" + encodeURIComponent(interviewId) + "/state", { cache: "no-store", signal: AbortSignal.timeout(6000) });
      if (response.ok) lines = ((await response.json()).transcript || []).length;
    } catch { /* fall back to the count sent from this page */ }
    if (!lines && !sentCount) { setDraftStatus("No transcript was recorded for " + interviewId + ", so no contracts were drafted.", "error"); return; }
    if (draftBusy || decisionBusy) { setDraftStatus("Another drafting run is in progress. Draft " + interviewId + " from Contracts when it finishes.", "error"); return; }
    draftBusy = true; renderDrafts();
    setDraftStatus("Drafting contracts from " + interviewId + "…");
    try {
      const data = await postDrafts(interviewId, 3);
      droppedByInterview.set(interviewId, data.rejected || []);
      const ready = (data.items || []).filter((record) => record.status === "draft").length;
      setDraftStatus(ready ? ready + " draft" + (ready === 1 ? "" : "s") + " from " + interviewId + " ready for review in Contracts." : "Drafting " + interviewId + " finished with no new drafts.", "done", interviewId);
    } catch (error) {
      setDraftStatus(error.name === "TimeoutError" ? "Drafting " + interviewId + " is still unconfirmed. Check Contracts before starting another run." : error.message, "error");
    } finally {
      draftBusy = false;
      try { draftRecords = await readDrafts(AbortSignal.timeout(10000)); } catch { /* the list refreshes on the next visit */ }
      received.delete("contracts:");
      populateDraftInterviews(interviewId);
    }
  }

  // ---- Transcripts: GET /api/interviews/{id}/transcript (markdown), or built here from the interview state ----
  let transcriptText = "";
  let transcriptGeneration = 0;

  function transcriptFromState(state, interviewId) {
    const item = interviewItems.find((entry) => entry.interview_id === interviewId) || {};
    const out = ["# Interview transcript · " + interviewId, ""];
    const company = state.company_name || item.company_name;
    const person = state.person_name || item.person_name || state.label || item.label;
    const position = state.position || item.position;
    if (company) out.push("- Company: " + company);
    if (person) out.push("- Person: " + person);
    if (position) out.push("- Position: " + position);
    out.push("", "## Transcript", "");
    const events = (state.transcript || []).map((line) => ({ t: line.t_ms, kind: "said", text: line.text }));
    events.push(...(state.played || []).map((question) => ({ t: question.played_at, kind: "asked", id: question.id, text: question.text })));
    events.sort((a, b) => (a.t || 0) - (b.t || 0) || (a.kind === "asked" ? -1 : 1));
    for (const entry of events) {
      if (entry.kind === "asked") out.push("**[" + timeLabel(entry.t) + "] Interviewer (" + entry.id + "):** " + (entry.text || ""), "");
      else out.push("[" + timeLabel(entry.t) + "] " + (person || "Interviewee") + ": " + (entry.text || ""), "");
    }
    if (!events.length) out.push("_No speech or questions were recorded in this interview._", "");
    return out.join("\n");
  }

  async function fetchTranscript(interviewId) {
    if (!useMocks) {
      const response = await fetch("/api/interviews/" + encodeURIComponent(interviewId) + "/transcript", { cache: "no-store", signal: AbortSignal.timeout(6000) });
      if (response.ok) {
        if ((response.headers.get("content-type") || "").includes("json")) {
          const body = await response.json();
          return typeof body === "string" ? body : body.markdown || body.text || JSON.stringify(body, null, 2);
        }
        return response.text();
      }
      const body = await response.clone().json().catch(() => null);
      if (response.status !== 404 || body?.detail !== "Not Found") throw new Error(typeof body?.detail === "string" ? body.detail : "Transcript unavailable for " + interviewId);
    }
    // Route not merged yet (FastAPI's bare "Not Found"), or preview mode: build it from the interview state.
    const response = await fetch(useMocks ? "/static/mock/state.json" : "/api/interviews/" + encodeURIComponent(interviewId) + "/state", { cache: "no-store", signal: AbortSignal.timeout(6000) });
    if (!response.ok) throw new Error("Transcript unavailable for " + interviewId);
    return transcriptFromState(await response.json(), interviewId);
  }

  async function openTranscript(interviewId) {
    if (!interviewId) return;
    const version = ++transcriptGeneration;
    transcriptText = "";
    const item = interviewItems.find((entry) => entry.interview_id === interviewId);
    byId("transcript-title").textContent = "Transcript · " + interviewId;
    byId("transcript-meta").textContent = item ? [item.company_name, interviewIdentity(item), item.position].filter(Boolean).join(" · ") : "";
    byId("transcript-status").textContent = "";
    byId("transcript-download").disabled = true; byId("transcript-copy").disabled = true;
    byId("transcript-doc").textContent = "Loading transcript…";
    if (!byId("transcript-dialog").open) byId("transcript-dialog").showModal();
    try {
      const text = await fetchTranscript(interviewId);
      if (version !== transcriptGeneration) return;
      transcriptText = text;
      byId("transcript-doc").textContent = text;
      byId("transcript-download").disabled = false; byId("transcript-copy").disabled = false;
      byId("transcript-download").dataset.filename = interviewId + "-transcript.md";
    } catch (error) {
      if (version === transcriptGeneration) byId("transcript-doc").textContent = (error.name === "TimeoutError" ? "Transcript request timed out." : error.message) + " Try again in a moment.";
    }
  }

  function draftInterview(record) { return record.interview_id || /^DR-(INT-\d{2,})-\d+$/.exec(record.draft_id || "")?.[1] || "Unknown interview"; }

  function expectationText(expectation) {
    const { template, target, tolerance, description, unit, params = {} } = expectation;
    const lower = expectation.comparator === ">=";
    const direction = lower ? "at least " : "at most ";
    let wording = description + ": " + direction + metricValue(target, unit);
    if (template === "followup_within") wording += " within " + params.within_hours + " h";
    const breach = lower ? target - tolerance : target + tolerance;
    return wording + " · breach " + (lower ? "below " : "above ") + metricValue(breach, unit);
  }

  function confidenceChips(confidence) {
    const row = element("div", null, "confidence-row");
    for (const type of ["said", "did", "code"]) {
      const chip = element("span", type + ": " + (confidence?.[type] ? "confirmed" : "not confirmed"), "confidence-chip");
      chip.dataset.confirmed = String(confidence?.[type] === true); row.append(chip);
    }
    return row;
  }

  function openLoopBody(loop) {
    const body = element("div");
    body.append(element("h4", loop.requirement?.statement || "Open loop"));
    for (const evidence of loop.evidence || []) body.append(quote(evidence));
    body.append(element("p", "Not measurable yet: " + loop.why_unmeasurable, "muted-copy"));
    body.append(element("p", "To measure it, instrument " + loop.suggested_event?.name + " (" + (loop.suggested_event?.props || []).join(", ") + ").", "question-meta id"));
    if (loop.suggested_human_check) body.append(element("p", loop.suggested_human_check, "muted-copy"));
    return body;
  }

  function renderDrafts() {
    const interview = byId("draft-interview").value;
    const list = document.createDocumentFragment();
    const records = draftRecords.filter((record) => draftInterview(record) === interview && record.status === "draft");
    for (const record of records) {
      const card = element("section", null, "draft-card"); card.dataset.draftId = record.draft_id;
      card.append(element("p", "Draft from " + interview + " · " + record.draft_id, "draft-label"));
      if (record.kind === "contract" && record.contract) {
        const contract = record.contract;
        card.append(element("h4", contract.requirement?.statement));
        for (const expectation of contract.expectations || []) card.append(element("p", expectationText(expectation), "muted-copy"));
        for (const evidence of contract.evidence || []) card.append(quote(evidence));
        card.append(confidenceChips(contract.confidence));
        if (record.contradiction) card.append(element("p", [record.contradiction.statement_a, record.contradiction.statement_b].join(" · "), "draft-contradiction"));
        else card.append(element("p", "Interviewee said " + (record.stated_value ?? "not specified") + " · legacy logs show " + (record.baseline_value ?? "not measured"), "muted-copy"));
      } else if (record.open_loop) card.append(openLoopBody(record.open_loop));
      const checks = element("ul", null, "draft-checks");
      for (const check of record.checks || []) checks.append(element("li", check));
      card.append(checks);
      if (record.rationale) card.append(element("p", record.rationale, "muted-copy"));
      const transcriptLink = element("button", "View transcript", "text-link-button"); transcriptLink.type = "button";
      transcriptLink.addEventListener("click", () => openTranscript(draftInterview(record)));
      card.append(transcriptLink);
      const actions = element("div", null, "draft-actions");
      for (const action of ["approve", "reject"]) {
        const button = element("button", action === "approve" ? "Approve" : "Reject", action === "approve" ? "primary-button" : "secondary-button");
        button.type = "button"; button.disabled = decisionBusy || draftBusy;
        button.addEventListener("click", () => decideDraft(record, action)); actions.append(button);
      }
      card.append(actions); list.append(card);
    }
    if (!interview) list.append(element("p", "No interviews for " + companyLabel() + " yet. Start one on the Interview tab; its drafts appear here when it ends.", "empty-copy"));
    else if (!records.length) list.append(element("p", "No pending drafts for " + interview + ". Draft a saved interview to find new measurable requirements and open loops.", "empty-copy"));
    byId("draft-list").replaceChildren(list);
    const dropped = droppedByInterview.get(interview) || [];
    byId("draft-dropped").querySelector("summary").textContent = "Dropped by checks (" + dropped.length + ")";
    const droppedList = document.createDocumentFragment();
    for (const item of dropped) droppedList.append(element("li", item.requirement + " · " + (item.reasons || []).join("; ")));
    if (!dropped.length) droppedList.append(element("li", "No dropped results from a drafting run in this browser session.", "muted-copy"));
    byId("draft-dropped-list").replaceChildren(droppedList);
    byId("draft-run").disabled = draftBusy || decisionBusy || !interview;
    byId("draft-transcript").disabled = !interview;
    byId("draft-interview").disabled = draftBusy || decisionBusy || !interview;
    byId("draft-loading").hidden = !draftBusy;
    const loops = document.createDocumentFragment();
    for (const record of draftRecords.filter((item) => item.kind === "open_loop" && item.status === "approved")) {
      const panel = element("article", null, "panel evidence-panel open-loops");
      panel.append(element("p", (record.final_ids?.requirement_id || "Open loop") + " · drafted from " + draftInterview(record) + ", approved", "draft-label"), openLoopBody(record.open_loop)); loops.append(panel);
    }
    byId("approved-open-loops").replaceChildren(loops);
  }

  async function readDrafts(signal) {
    if (useMocks && mockDraftBundle) return structuredClone(mockDraftBundle.items);
    const data = await requestData(draftsResource, signal);
    if (useMocks) {
      mockDraftBundle = structuredClone(data);
      droppedByInterview.set(data.interview_id, data.rejected || []);
    }
    return Array.isArray(data) ? data : data.items;
  }

  function promptDialog(id) {
    return new Promise((resolve) => {
      dialogResolvers.set(id, resolve);
      byId(id).showModal();
    });
  }

  async function adminToken() {
    let token;
    try { token = sessionStorage.getItem(ADMIN_TOKEN_KEY); } catch { /* Storage may be blocked. */ }
    if (token) return token;
    byId("draft-token").value = "";
    token = await promptDialog("draft-token-dialog");
    if (token) { try { sessionStorage.setItem(ADMIN_TOKEN_KEY, token); } catch { /* The current action can still use the token. */ } }
    return token;
  }

  async function refreshDecisions() {
    const [records, contracts, interview, lifecycle] = await Promise.all([readDrafts(AbortSignal.timeout(10000)), requestData(views.contracts, AbortSignal.timeout(10000)), requestData(interviewConfig(), AbortSignal.timeout(6000)).catch(() => null), readLifecycle(AbortSignal.timeout(6000))]);
    draftRecords = records;
    renderContracts({ contracts, interview, lifecycle });
    renderDrafts();
    received.delete("contracts:"); received.delete("drift:"); lastDrift = null;
  }

  async function decideDraft(record, action) {
    if (decisionBusy || draftBusy) return;
    decisionBusy = true; renderDrafts();
    try {
      const token = useMocks ? "preview" : await adminToken();
      if (!token) return;
      let reason = null;
      if (action === "reject") {
        byId("draft-reject-reason").value = "";
        reason = await promptDialog("draft-reject-dialog");
        if (reason === null) return;
      }
      if (useMocks) {
        const item = mockDraftBundle.items.find((draft) => draft.draft_id === record.draft_id);
        item.status = action === "approve" ? "approved" : "rejected";
        item.reject_reason = reason;
        if (action === "approve") {
          item.final_ids = { contract_id: item.kind === "contract" ? "C-06" : null, requirement_id: item.kind === "contract" ? "R-07" : "R-08" };
          if (item.kind === "contract") {
            const contract = structuredClone(item.contract); contract.id = "C-06"; contract.requirement.id = "R-07"; mockApprovedContracts.push(contract);
          }
        }
      } else {
        const response = await fetch(scopedPath("/api/drafts/" + encodeURIComponent(record.draft_id) + "/" + action), { method: "POST", headers: { "Content-Type": "application/json", "X-Admin-Token": token }, body: JSON.stringify(action === "reject" ? { reason } : {}), signal: AbortSignal.timeout(15000) });
        if (response.status === 401) {
          try { sessionStorage.removeItem(ADMIN_TOKEN_KEY); } catch { /* Storage may be blocked. */ }
          throw new Error("Admin token was not accepted. Try the decision again with the client's current token.");
        }
        if (response.status === 409) { await refreshDecisions(); throw new Error("This draft has already been decided. The list has been refreshed."); }
        if (!response.ok) throw new Error("Decision was not confirmed. Refresh the drafts before trying again.");
      }
      await refreshDecisions();
      byId("draft-message").textContent = action === "approve" ? "Approved. Contracts and open loops have been refreshed." : "Rejected. Earlier approved contracts are unchanged.";
    } catch (error) { byId("draft-message").textContent = error.message || "Could not refresh the decision. Reload before retrying."; }
    finally { decisionBusy = false; renderDrafts(); }
  }

  async function runDrafts() {
    if (draftBusy || decisionBusy) return;
    const interview = byId("draft-interview").value;
    if (!interview) return;
    draftBusy = true; renderDrafts();
    byId("draft-message").textContent = "Drafting from saved interview evidence. Usually 10–30 seconds.";
    try {
      let data;
      if (useMocks) {
        if (!mockDraftBundle) await readDrafts(AbortSignal.timeout(6000));
        if (interview !== mockDraftBundle.interview_id) throw new Error("No saved interview yet for " + interview);
        data = structuredClone(mockDraftBundle);
      } else {
        data = await postDrafts(interview);
      }
      droppedByInterview.set(interview, data.rejected || []);
      draftRecords = await readDrafts(AbortSignal.timeout(10000));
      byId("draft-message").textContent = "Drafting complete. Review the evidence and checks before approving.";
    } catch (error) { byId("draft-message").textContent = error.name === "TimeoutError" ? "Drafting is still unconfirmed. Refresh before starting another run; earlier drafts are unchanged." : error.message; }
    finally { draftBusy = false; renderDrafts(); }
  }

  function stateChip(state) {
    const chip = element("span", (state || "not measured").replaceAll("_", " "), "status-chip state-" + (state || "not_measured"));
    chip.dataset.state = state || "not_measured";
    return chip;
  }

  function metricValue(value, unit) {
    if (!Number.isFinite(value)) return "Not measured";
    return unit === "share" ? percent(value) : Number(value.toFixed(2)).toLocaleString() + (unit === "seconds" ? " s" : " per person / week");
  }

  function monitoringOff() {
    const panel = element("article", null, "panel evidence-panel monitoring-off");
    panel.append(element("h3", "Drift monitoring is off for this client"));
    const link = element("a", "Open Client settings", "text-link");
    link.href = "#settings";
    panel.append(link);
    return panel;
  }

  function renderDrift(data) {
    lastDrift = data;
    charts.splice(0).forEach((chart) => chart.destroy());
    const root = byId("drift-content");
    root.replaceChildren();
    if (!data.drift.enabled) { root.append(monitoringOff()); return; }
    const contracts = data.drift.contracts || [];
    const summary = element("article", null, "panel evidence-panel drift-summary");
    summary.append(element("h3", "Contract status"), element("p", "Weeks 1–2 are learning weeks. Drift requires consecutive breaches after learning.", "muted-copy"));
    const list = element("ul", null, "status-list");
    for (const contract of contracts) {
      const row = element("li");
      const finding = data.findings.find((item) => item.contract_id === contract.contract_id);
      const label = element(finding ? "a" : "span", contract.contract_id + " · " + (contract.requirement?.statement || "Behaviour contract"));
      if (finding) label.href = "#finding/" + encodeURIComponent(finding.id);
      row.append(label, stateChip(contract.status));
      list.append(row);
    }
    if (!contracts.length) list.append(element("li", "No watched contracts. Choose contracts in Client settings.", "empty-copy"));
    summary.append(list);
    root.append(summary);
    for (const contract of contracts) {
      const expectation = contract.expectations?.[0];
      const weeks = contract.weekly || [];
      const panel = element("article", null, "panel evidence-panel chart-panel");
      const heading = element("header", null, "panel-heading");
      heading.append(element("h3", contract.contract_id + " · " + (expectation?.description || expectation?.metric_id || "Usage")), stateChip(contract.status));
      panel.append(heading);
      if (!expectation || !weeks.length) {
        panel.append(element("p", "No weekly measurements available yet.", "empty-copy"));
        root.append(panel); continue;
      }
      panel.append(element("p", "Target " + expectation.comparator + " " + metricValue(expectation.target, expectation.unit) + " · tolerance ± " + metricValue(expectation.tolerance, expectation.unit), "muted-copy"));
      const wrap = element("div", null, "chart-wrap");
      const canvas = element("canvas");
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", contract.contract_id + " weekly usage, target and tolerance. Exact values in the table below.");
      wrap.append(canvas); panel.append(wrap);
      const notesMetric = contract.expectations.find((item) => item.metric_id === "pa_in_notes_rate");
      if (contract.contract_id === "C-02") panel.append(element("p", "Week 5: single-week spike, not drift", "chart-note"));
      const tableDetails = element("details", null, "weekly-values");
      tableDetails.append(element("summary", "Weekly measurements"));
      const table = element("table");
      const header = element("tr");
      ["Week", "Measured", ...(notesMetric ? ["Auth in notes"] : []), "State"].forEach((value) => header.append(element("th", value)));
      const thead = element("thead"); thead.append(header); table.append(thead);
      const tbody = element("tbody");
      for (const week of weeks) {
        const row = element("tr");
        [week.week, metricValue(week.values?.[expectation.metric_id], expectation.unit), ...(notesMetric ? [metricValue(week.values?.[notesMetric.metric_id], "share")] : []), week.state?.replaceAll("_", " ")].forEach((value) => row.append(element("td", value)));
        tbody.append(row);
      }
      table.append(tbody); tableDetails.append(table); panel.append(tableDetails); root.append(panel);
      if (!window.Chart) {
        wrap.replaceChildren(element("p", "Chart library unavailable. Weekly measurements remain available below.", "empty-copy"));
        continue;
      }
      const band = weeks.map(() => expectation.target + expectation.tolerance);
      const lower = weeks.map(() => Math.max(0, expectation.target - expectation.tolerance));
      const datasets = [
        { label: "Tolerance upper", data: band, borderWidth: 0, pointRadius: 0, backgroundColor: "rgba(15,110,110,0.10)" },
        { label: "Tolerance band", data: lower, borderWidth: 0, pointRadius: 0, fill: { target: 0 }, backgroundColor: "rgba(15,110,110,0.10)" },
        { label: "Target", data: weeks.map(() => expectation.target), borderColor: "#5B636A", borderDash: [5, 4], borderWidth: 1, pointRadius: 0 },
        { label: expectation.description || expectation.metric_id, data: weeks.map((week) => week.values?.[expectation.metric_id] ?? null), borderColor: "#0F6E6E", backgroundColor: "#0F6E6E", pointBackgroundColor: weeks.map((week) => contract.contract_id === "C-02" && week.week === 5 ? "#B7791F" : "#0F6E6E"), borderWidth: 2, pointRadius: 3 }
      ];
      if (notesMetric) datasets.push({ label: "Auth number in notes", yAxisID: "notes", data: weeks.map((week) => week.values?.[notesMetric.metric_id] ?? null), borderColor: "#B7791F", borderWidth: 2, pointRadius: 3 });
      const learning = { id: "learningWeeks", beforeDraw(chart) {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea) return;
        const count = weeks.filter((week) => week.week <= (contract.learning_period_weeks ?? 2)).length;
        if (!count) return;
        const right = count >= weeks.length ? chartArea.right : (scales.x.getPixelForValue(count - 1) + scales.x.getPixelForValue(count)) / 2;
        ctx.save(); ctx.fillStyle = "rgba(91,99,106,0.10)"; ctx.fillRect(chartArea.left, chartArea.top, right - chartArea.left, chartArea.bottom - chartArea.top); ctx.restore();
      } };
      charts.push(new Chart(canvas, { type: "line", data: { labels: weeks.map((week) => "Week " + week.week), datasets }, plugins: [learning], options: {
        animation: false, responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: "index" },
        plugins: { legend: { labels: { filter: (item) => item.datasetIndex >= 2, boxWidth: 14 } }, tooltip: { filter: (item) => item.datasetIndex >= 2 } },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ...(expectation.unit === "share" ? { max: 1, ticks: { callback: (value) => percent(value) } } : {}) }, ...(notesMetric ? { notes: { position: "right", min: 0, max: 1, grid: { drawOnChartArea: false }, ticks: { callback: (value) => percent(value) }, title: { display: true, text: "Auth in notes" } } } : {}) }
      } }));
    }
  }

  function renderFinding(data, id) {
    const root = byId("finding-content");
    root.replaceChildren();
    if (!data.settings.drift_enabled) { root.append(monitoringOff()); return; }
    const finding = data.findings.find((item) => item.id === (id || "F-01"));
    if (!finding) { root.append(element("p", "This finding is not available. Return to Drift for current findings.", "empty-copy")); return; }
    const layout = element("div", null, "finding-layout");
    const detail = element("article", null, "panel evidence-panel");
    const heading = element("header", null, "panel-heading");
    heading.append(element("h3", finding.id + " · " + finding.contract_id, "id"), stateChip(finding.status));
    detail.append(heading, element("h4", finding.requirement_statement || "Prior authorization is recorded in its own field.", "contract-title"));
    detail.append(element("p", finding.explanation, "finding-explanation"));
    detail.append(element("p", "Type: " + (finding.type || "unclassified").replaceAll("_", " "), "eyebrow"), element("p", finding.type_reason, "muted-copy"));
    detail.append(element("p", "First breach: week " + finding.first_breach_week + " · severity " + finding.severity, "question-meta"));
    const signals = element("ul", null, "expectation-list");
    for (const signal of finding.related_signals || []) signals.append(element("li", signal.detector + ": " + percent(signal.from) + " → " + percent(signal.to)));
    detail.append(signals);
    const cost = element("aside", null, "panel evidence-panel");
    cost.append(element("p", "ESTIMATED WEEKLY IMPACT", "eyebrow"), element("p", Number.isFinite(finding.cost_usd_per_week) ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(finding.cost_usd_per_week) : "Not estimated", "finding-cost"), element("p", "Demo value · synthetic costs, not a financial forecast.", "muted-copy"));
    const button = element("button", "Preview Software Factory feedback", "primary-button"); button.type = "button";
    button.addEventListener("click", () => openFeedback(finding, data.settings)); cost.append(button);
    layout.append(detail, cost); root.append(layout);
    const lineage = element("article", null, "panel evidence-panel lineage-chain");
    lineage.append(element("h3", "Back to the interview"), element("p", [finding.contract_id, finding.lineage?.requirement_id, "Interview quote", finding.lineage?.question_id].filter(Boolean).join(" ← "), "id"));
    if (finding.lineage) lineage.append(quote({ question_origin: "ai", ...finding.lineage }));
    root.append(lineage);
  }

  function selectFeedbackTab(name) {
    document.querySelectorAll("[data-sf-tab]").forEach((tab) => {
      const selected = tab.dataset.sfTab === name;
      tab.setAttribute("aria-selected", String(selected)); tab.tabIndex = selected ? 0 : -1;
      byId("sf-" + tab.dataset.sfTab + "-panel").hidden = !selected;
    });
  }

  async function openFeedback(finding, settings) {
    const version = ++drawerGeneration;
    feedbackPayload = null;
    feedbackFinding = finding;
    byId("sf-file").disabled = true;
    byId("sf-feedback-id").textContent = "FEEDBACK PREVIEW";
    byId("sf-preview-title").textContent = finding.contract_id + " · Usage drift";
    byId("sf-preview-content").textContent = finding.explanation;
    byId("sf-result").textContent = "";
    byId("sf-payload").textContent = "";
    byId("sf-permission").textContent = settings.send_to_sf ? "This sends only to the local simulated feedback stub." : "Sending is off for this client. Enable Software Factory feedback in Client settings.";
    selectFeedbackTab("landing");
    byId("sf-drawer").showModal();
    if (!settings.send_to_sf) return;
    byId("sf-payload-loading").hidden = false;
    try {
      const payload = await requestData({ endpoint: "/api/findings/" + encodeURIComponent(finding.id) + "/sf-payload", mock: "/static/mock/sf-payload.json" }, AbortSignal.timeout(6000));
      if (version !== drawerGeneration) return;
      feedbackPayload = payload;
      byId("sf-payload").textContent = JSON.stringify(payload, null, 2);
      byId("sf-file").disabled = false;
    } catch { if (version === drawerGeneration) byId("sf-result").textContent = "Could not load feedback. Check client permission and try again."; }
    finally { if (version === drawerGeneration) byId("sf-payload-loading").hidden = true; }
  }

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = String(text);
    if (className) node.className = className;
    return node;
  }

  function timeLabel(value) {
    if (!Number.isFinite(value)) return "—";
    const seconds = Math.max(0, Math.floor(value / 1000));
    return String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
  }

  function percent(value) {
    return Number.isFinite(value) ? Math.round(value * 100) + "%" : "—";
  }

  function badge(id, origin, interview = "INT-01") {
    const link = id && interview === "INT-01";
    const node = element(link ? "a" : "span", id || "Unprompted", "question-badge");
    node.dataset.origin = origin || "unprompted";
    node.title = origin === "ai" ? "Answer to an AI-selected question" : origin === "interviewer" ? "Answer to an interviewer question" : "Unprompted evidence";
    if (link) node.href = "#interview/" + encodeURIComponent(id);
    return node;
  }

  function quote(evidence, includeBadge = true) {
    const figure = element("figure", null, "evidence-quote");
    figure.append(element("blockquote", evidence.quote || evidence.value || "No quote supplied."));
    const caption = element("figcaption");
    const details = [evidence.speaker, evidence.interview_id, evidence.timestamp].filter(Boolean);
    if (details.length) caption.append(element("span", details.join(" · ")));
    if (includeBadge) caption.append(badge(evidence.question_id, evidence.question_origin, evidence.interview_id || "INT-01"));
    if (evidence.question_id && (evidence.interview_id || "INT-01") === "INT-01") linkedEvidence.set(evidence.question_id, evidence);
    figure.append(caption);
    return figure;
  }

  function currentRoute() {
    const [name, detail] = (window.location.hash.slice(1) || "interview").split("/");
    const route = Object.hasOwn(views, name) ? name : "interview";
    let id = detail || "";
    try { id = decodeURIComponent(id); } catch { id = ""; }
    return { name: route, detail: id };
  }

  function focusLineage(route) {
    byId("recorded-lineage")?.remove();
    document.querySelectorAll(".lineage-target").forEach((node) => node.classList.remove("lineage-target"));
    if (route.name !== "interview" || !route.detail) return;
    let target = [...document.querySelectorAll("#interview-content [data-question-id]")].find((node) => node.dataset.questionId === route.detail);
    if (!target && linkedEvidence.has(route.detail)) {
      target = element("article", null, "panel evidence-panel"); target.id = "recorded-lineage";
      target.dataset.questionId = route.detail;
      target.append(element("h3", "Recorded interview evidence"), element("p", "This quote is attached to the contract. Its question is not in the current interview stream.", "muted-copy"), quote(linkedEvidence.get(route.detail), false));
      byId("interview-content").prepend(target);
    }
    if (target) {
      target.classList.add("lineage-target");
      const key = generation + ":" + route.detail;
      if (focusedLineage !== key) target.scrollIntoView({ block: "center" });
      focusedLineage = key;
    }
  }

  function renderInterview(state) {
    if (!state || !Array.isArray(state.transcript) || !Array.isArray(state.queue) || !Array.isArray(state.played)) {
      throw new Error("Interview data is unavailable");
    }
    const fills = state.slot_fills || {};
    const slots = Array.isArray(state.slots) ? state.slots : Object.keys(fills);
    const aiFields = Object.values(fills).filter((fill) => fill.question_origin === "ai").length;
    byId("coverage-stat").textContent = percent(state.coverage);
    byId("yield-stat").textContent = percent(state.yield);
    byId("ai-fields-stat").textContent = aiFields + " of " + slots.length;
    byId("interview-label").textContent = (state.interview_id || "INT-01") + " · " + (state.label || "Interview");

    const transcript = byId("transcript-lines");
    const followLatest = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 40;
    const previousScroll = transcript.scrollTop;
    const events = state.transcript.map((line) => ({ ...line, kind: "utterance" }));
    events.push(...state.played.map((question) => ({ ...question, kind: "played", t_ms: question.played_at })));
    events.sort((a, b) => (a.t_ms || 0) - (b.t_ms || 0) || (a.kind === "played" ? -1 : 1));
    const lines = document.createDocumentFragment();
    let answering = null;
    for (const entry of events) {
      const row = element("li");
      if (entry.kind === "played") {
        answering = entry.id;
        row.append(element("time", timeLabel(entry.t_ms)));
        row.append(element("p", "[" + entry.id + " played] " + (entry.text || ""), "played-marker"));
      } else {
        if (answering) row.dataset.questionId = answering;
        row.append(element("time", timeLabel(entry.t_ms)));
        row.append(element("p", entry.text || ""));
      }
      lines.append(row);
    }
    if (!events.length) lines.append(element("li", "Waiting for the first spoken sentence.", "empty-copy"));
    transcript.replaceChildren(lines);
    transcript.scrollTop = followLatest ? transcript.scrollHeight : previousScroll;
    if (followLatest) requestAnimationFrame(() => { transcript.scrollTop = transcript.scrollHeight; });

    const queue = document.createDocumentFragment();
    for (const question of state.queue.slice(0, 3)) {
      const row = element("li");
      row.append(element("span", question.cue || "Detail:", "queue-cue"));
      row.append(element("p", question.text || ""));
      row.append(element("span", [question.id, question.bank_id, question.target].filter(Boolean).join(" · "), "question-meta id"));
      row.append(element("span", question.reason || "No reason supplied.", "question-meta"));
      queue.append(row);
    }
    if (!state.queue.length) queue.append(element("li", "Waiting for questions from the interview engine.", "empty-copy"));
    byId("question-queue").replaceChildren(queue);

    const contracts = new Map();
    for (const slotId of slots) {
      const [contractId] = slotId.split(".");
      if (!contracts.has(contractId)) contracts.set(contractId, []);
      contracts.get(contractId).push(slotId);
    }
    const grid = document.createDocumentFragment();
    for (const [contractId, slotIds] of contracts) {
      const group = element("section", null, "slot-contract");
      group.append(element("h4", contractId));
      for (const slotId of slotIds) {
        const fill = fills[slotId];
        const row = element("div", null, "slot-row");
        const label = element("div", null, "slot-label");
        label.append(element("code", slotId.slice(contractId.length + 1)));
        if (fill) {
          label.append(badge(fill.question_id, fill.question_origin));
          if (fill.question_id) row.dataset.questionId = fill.question_id;
        } else label.append(element("span", "Open", "eyebrow"));
        row.append(label);
        if (fill) {
          row.append(quote({ ...fill, speaker: state.label, interview_id: state.interview_id || "INT-01", timestamp: timeLabel(fill.t_ms) }, false));
          const question = state.played.find((played) => played.id === fill.question_id);
          if (question?.reason) row.append(element("p", "Asked because: " + question.reason, "muted-copy"));
        }
        group.append(row);
      }
      grid.append(group);
    }
    if (!slots.length) grid.append(element("p", "No contract slots have been supplied yet.", "empty-copy"));
    byId("slot-grid").replaceChildren(grid);
    byId("slot-summary").textContent = Object.keys(fills).length + " / " + slots.length + " FILLED";
  }

  function renderContracts(data) {
    if (!Array.isArray(data.contracts)) throw new Error("Contract data is unavailable");
    const list = document.createDocumentFragment();
    for (const contract of data.contracts) {
      const article = element("article", null, "panel evidence-panel");
      const heading = element("header", null, "panel-heading");
      heading.append(element("h3", contract.id, "id"));
      heading.append(element("span", contract.requirement?.id || "", "id"));
      article.append(heading, element("h4", contract.requirement?.statement || "Requirement", "contract-title"));
      if (data.lifecycle) article.append(stageStrip(data.lifecycle.stages?.[contract.id]));
      const source = draftRecords.find((record) => record.status === "approved" && record.final_ids?.contract_id === contract.id);
      if (source) article.append(element("p", contract.id + " · drafted from " + draftInterview(source) + ", approved", "draft-label"));
      article.append(element("p", [contract.requirement?.feature, contract.role?.replaceAll("_", " "), contract.signal].filter(Boolean).join(" · "), "contract-meta"));
      article.append(element("p", contract.population?.description || "", "muted-copy"));
      const expectations = element("ul", null, "expectation-list");
      for (const expectation of contract.expectations || []) {
        const row = element("li");
        row.append(element("p", expectation.description || expectation.metric_id));
        row.append(element("code", expectation.metric_id + " · " + expectation.comparator + " " + expectation.target + " ± " + expectation.tolerance + " " + expectation.unit));
        expectations.append(row);
      }
      article.append(expectations);
      const confidence = element("div", null, "confidence-row");
      confidence.setAttribute("aria-label", "Evidence confidence");
      for (const type of ["said", "did", "code"]) {
        const confirmed = contract.confidence?.[type] === true;
        const chip = element("span", type[0].toUpperCase() + type.slice(1) + ": " + (confirmed ? "confirmed" : "not confirmed"), "confidence-chip");
        chip.dataset.confirmed = String(confirmed);
        confidence.append(chip);
      }
      article.append(confidence);
      if (contract.confidence?.note) article.append(element("p", contract.confidence.note, "muted-copy"));
      for (const evidence of contract.evidence || []) article.append(quote(evidence));
      if (!contract.evidence?.length) article.append(element("p", "No interview evidence has been attached yet.", "empty-copy"));
      for (const reference of contract.code_refs || []) article.append(element("p", reference.file + " · " + reference.rule_id, "question-meta id"));
      const details = element("details", null, "contract-shape");
      details.append(element("summary", "Contract shape"));
      details.append(element("pre", JSON.stringify({ signal: contract.signal, population: contract.population, expectations: contract.expectations, window: contract.window }, null, 2), "payload"));
      article.append(details, requirementView(contract));
      list.append(article);
    }
    if (!data.contracts.length) {
      const empty = element("article", null, "panel evidence-panel");
      empty.append(element("h3", "No approved contracts yet"), element("p", "No approved contracts for " + companyLabel() + " yet. Finish an interview and approve its drafts.", "empty-copy"));
      list.append(empty);
    }
    byId("contracts-list").replaceChildren(list);
    byId("demo-open-loops").hidden = !useMocks && selectedCompany !== DEMO_COMPANY;

    const contradictions = document.createDocumentFragment();
    if (!data.interview) contradictions.append(element("p", "Interview contradictions are unavailable until the interview state can be loaded.", "empty-copy"));
    else if (!data.interview.contradictions?.length) contradictions.append(element("p", "No contradictions have been recorded in this interview.", "empty-copy"));
    else for (const item of data.interview.contradictions) {
      const article = element("article", null, "contradiction-item");
      article.append(element("p", [item.kind?.replaceAll("_", " "), item.rule_id].filter(Boolean).join(" · "), "question-meta id"));
      article.append(element("blockquote", item.statement_a || ""), element("blockquote", item.statement_b || ""));
      article.append(element("p", item.resolution_status || "Open · needs human review", "muted-copy"));
      contradictions.append(article);
    }
    byId("contradictions-list").replaceChildren(contradictions);
  }

  async function requestData(config, signal) {
    const rawPath = useMocks ? config.mock : config.endpoint;
    const response = await fetch(scopedPath(rawPath), { headers: { Accept: "application/json" }, signal, cache: "no-store" });
    if (!response.ok) throw new Error("Evidence unavailable");
    const data = await response.json();
    if (useMocks && config === views.contracts) return [...data, ...structuredClone(mockApprovedContracts)];
    if (useMocks && config === views.drift) {
      for (const contract of mockApprovedContracts) {
        const metric = contract.expectations[0].metric_id;
        data.contracts.push({ contract_id: contract.id, requirement: contract.requirement, expectations: contract.expectations, status: "holding", learning_period_weeks: 2, weekly: Array.from({ length: 8 }, (_, i) => ({ week: i + 1, values: { [metric]: 0.25 }, state: i < 2 ? "learning" : "ok", people: 8 })) });
      }
    }
    return data;
  }

  function showRoute() {
    const route = currentRoute();
    // The Interview tab shows the interview chosen in "Past interviews" (views.interview is only its preview fallback).
    const config = route.name === "interview" ? interviewConfig() : views[route.name];
    const currentGeneration = ++generation;
    clearTimeout(pollTimer);
    controller?.abort();
    title.textContent = config.title;
    document.querySelectorAll(".view-panel").forEach((section) => { section.hidden = section.id !== route.name + "-view"; });
    navigation.forEach((link) => {
      if (link.dataset.route === route.name || (route.name === "finding" && link.dataset.route === "drift")) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    focusLineage(route);
    loadView(route, config, currentGeneration);
  }

  async function loadView(route, config, currentGeneration) {
    if (route.name === "interview" && !selectedInterview) {
      const message = document.querySelector('[data-message="interview"]');
      const skeletons = document.querySelector("#interview-view .loading-grid");
      if (skeletons) skeletons.hidden = true;
      byId("interview-content").hidden = true;
      status.textContent = "Ready for a new interview";
      if (message) message.textContent = "Choose a previous interview or enter a person's name and position to start one.";
      return;
    }
    if (!config.endpoint) { status.textContent = "Local client settings"; return; }
    const message = document.querySelector('[data-message="' + route.name + '"]');
    const skeletons = document.querySelector("#" + route.name + "-view .loading-grid");
    const content = byId(route.name + "-content");
    const requestController = new AbortController();
    controller = requestController;
    const firstLoad = !received.has(route.name + ":" + route.detail);
    if (skeletons) skeletons.hidden = !firstLoad;
    if (firstLoad && message) message.textContent = "Loading evidence…";
    if (firstLoad) status.textContent = useMocks ? "Loading synthetic preview" : "Connecting to local server";
    const timeout = setTimeout(() => requestController.abort(), 6000);
    try {
      let data = await requestData(config, requestController.signal);
      if (route.name === "contracts") {
        try { draftRecords = await readDrafts(requestController.signal); }
        catch { byId("draft-message").textContent = "Draft records unavailable. Earlier contract evidence is still shown."; }
        const interview = await requestData(interviewConfig(), requestController.signal).catch(() => null);
        const lifecycle = await readLifecycle(requestController.signal);
        data = { contracts: data, interview, drafts: draftRecords, lifecycle };
      }
      if (route.name === "drift") data = { drift: data, findings: await requestData(views.finding, requestController.signal) };
      if (route.name === "finding") data = { findings: data, settings: await requestData(settingsResource, requestController.signal) };
      if (currentGeneration !== generation) return;
      const serialized = JSON.stringify(data);
      const cacheKey = route.name + ":" + route.detail;
      if (received.get(cacheKey) !== serialized) {
        if (route.name === "interview") renderInterview(data);
        if (route.name === "contracts") { renderContracts(data); renderDrafts(); }
        if (route.name === "drift") renderDrift(data);
        if (route.name === "finding") renderFinding(data, route.detail);
        received.set(cacheKey, serialized);
      }
      if (skeletons) skeletons.hidden = true;
      if (content) content.hidden = false;
      status.textContent = useMocks ? "Showing synthetic preview data" : "Connected to local server";
      if (message) message.textContent = route.name === "interview" ? "Interview state refreshes every second." : route.name === "contracts" ? "Interview evidence and contract targets." : "Client monitoring permissions apply.";
      focusLineage(route);
    } catch {
      if (currentGeneration !== generation) return;
      if (route.name === "interview" && route.detail && linkedEvidence.has(route.detail)) {
        if (skeletons) skeletons.hidden = true;
        if (content) content.hidden = false;
        status.textContent = "Showing recorded lineage evidence";
        if (message) message.textContent = "The current interview stream is unavailable. This quote is preserved with the contract.";
        focusLineage(route);
        return;
      }
      status.textContent = useMocks ? "Synthetic preview unavailable" : "Local server unavailable";
      if (message) message.textContent = firstLoad ? "Waiting for evidence. Loading placeholders remain visible." : "Connection unavailable. Showing the last received evidence.";
    } finally {
      clearTimeout(timeout);
      if (route.name === "interview" && currentGeneration === generation) {
        pollTimer = setTimeout(() => loadView(currentRoute(), config, currentGeneration), 1000);
      }
    }
  }

  window.addEventListener("hashchange", showRoute);
  byId("start-interview")?.addEventListener("click", () => { prefetchNextId(); byId("start-interview-message").textContent = ""; byId("start-interview-dialog").showModal(); });
  byId("start-interview-cancel")?.addEventListener("click", () => byId("start-interview-dialog").close());
  // No await before startNewInterview: it starts audio and recognition inside this gesture.
  byId("start-interview-form")?.addEventListener("submit", (event) => { event.preventDefault(); startNewInterview(); });
  byId("live-ask").addEventListener("click", () => onTap("play"));
  byId("live-skip").addEventListener("click", () => onTap("next"));
  byId("live-repeat").addEventListener("click", () => onTap("repeat"));
  byId("live-end").addEventListener("click", endInterview);
  document.addEventListener("keydown", (event) => {
    if (event.code !== "Space" || event.repeat || !live.active) return;
    const target = event.target;
    if (document.querySelector("dialog[open]")) return;
    if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT|BUTTON|A|SUMMARY)$/.test(target.tagName))) return;
    event.preventDefault();
    onTap("play");
  });
  renderLive();
  byId("interview-picker")?.addEventListener("change", (event) => {
    selectedInterview = event.target.value;
    const item = interviewItems.find((entry) => entry.interview_id === selectedInterview);
    if (item && !useMocks && interviewCompany(item) !== selectedCompany) {
      selectedCompany = interviewCompany(item); selectedCompanyName = item.company_name || "";
      companyChanged();
    }
    populateDraftInterviews(selectedInterview);
    showRoute();
  });
  byId("interview-transcript").addEventListener("click", () => openTranscript(selectedInterview));
  byId("draft-interview").addEventListener("change", () => { byId("draft-message").textContent = ""; renderDrafts(); });
  byId("draft-run").addEventListener("click", runDrafts);
  byId("draft-transcript").addEventListener("click", () => openTranscript(byId("draft-interview").value));
  byId("transcript-close").addEventListener("click", () => byId("transcript-dialog").close());
  byId("transcript-dialog").addEventListener("close", () => { ++transcriptGeneration; });
  byId("transcript-download").addEventListener("click", () => {
    if (!transcriptText) return;
    const url = URL.createObjectURL(new Blob([transcriptText], { type: "text/markdown;charset=utf-8" }));
    const link = element("a"); link.href = url; link.download = byId("transcript-download").dataset.filename || "transcript.md";
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  byId("transcript-copy").addEventListener("click", async () => {
    if (!transcriptText) return;
    try { await navigator.clipboard.writeText(transcriptText); byId("transcript-status").textContent = "Copied"; }
    catch { byId("transcript-status").textContent = "Copy is blocked here. Use Download instead."; }
  });
  function finishDialog(id, value) {
    const resolve = dialogResolvers.get(id);
    dialogResolvers.delete(id);
    byId(id).close();
    resolve?.(value);
  }
  for (const name of ["token", "reject"]) {
    const id = "draft-" + name + "-dialog";
    byId("draft-" + name + "-cancel").addEventListener("click", () => finishDialog(id, null));
    byId(id).addEventListener("close", () => {
      const resolve = dialogResolvers.get(id); dialogResolvers.delete(id); resolve?.(null);
    });
    byId("draft-" + name + "-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const value = byId(name === "token" ? "draft-token" : "draft-reject-reason").value.trim();
      if (name === "token" && !value) return;
      finishDialog(id, value);
    });
  }
  byId("chart-library").addEventListener("load", () => { if (lastDrift) renderDrift(lastDrift); });
  byId("sf-close").addEventListener("click", () => byId("sf-drawer").close());
  byId("sf-drawer").addEventListener("close", () => { ++drawerGeneration; feedbackPayload = null; byId("sf-payload-loading").hidden = true; });
  const feedbackTabs = [...document.querySelectorAll("[data-sf-tab]")];
  feedbackTabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectFeedbackTab(tab.dataset.sfTab));
    tab.addEventListener("keydown", (event) => {
      let next;
      if (event.key === "ArrowRight") next = (index + 1) % feedbackTabs.length;
      if (event.key === "ArrowLeft") next = (index + feedbackTabs.length - 1) % feedbackTabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = feedbackTabs.length - 1;
      if (next != null) { event.preventDefault(); selectFeedbackTab(feedbackTabs[next].dataset.sfTab); feedbackTabs[next].focus(); }
    });
  });
  byId("sf-file").addEventListener("click", async () => {
    if (!feedbackPayload || !feedbackFinding) return;
    const version = drawerGeneration;
    const findingId = feedbackFinding.id;
    byId("sf-file").disabled = true;
    byId("sf-result").textContent = "Filing simulated feedback…";
    try {
      const { response, preview } = await liveOrPreview("/api/findings/" + encodeURIComponent(findingId) + "/file", "/static/mock/sf-file.json", { method: "POST", signal: AbortSignal.timeout(6000) });
      if (!response.ok) throw new Error("Feedback unavailable");
      const reply = await response.json();
      if (!Number.isInteger(reply.feedback_number)) throw new Error("Invalid feedback response");
      if (preview) {
        // Preview: emulate the file-once route so a second click shows the original number.
        reply.already_filed = mockFiled.has(findingId);
        if (reply.already_filed) reply.feedback_number = mockFiled.get(findingId); else mockFiled.set(findingId, reply.feedback_number);
      }
      if (version !== drawerGeneration) return;
      byId("sf-feedback-id").textContent = "FB-" + reply.feedback_number;
      byId("sf-result").textContent = reply.already_filed ? "Already filed as FB-" + reply.feedback_number : "FB-" + reply.feedback_number + " filed · Simulated, no live connection";
      byId("sf-file").disabled = false;
      received.delete("contracts:");
    } catch {
      if (version !== drawerGeneration) return;
      byId("sf-result").textContent = "Feedback was not confirmed. Check the local stub before retrying.";
      byId("sf-file").disabled = false;
    }
  });
  loadInterviewList();
  loadInterviewOptions();
  window.addEventListener("pagehide", () => { ++generation; clearTimeout(pollTimer); controller?.abort(); charts.splice(0).forEach((chart) => chart.destroy()); });
  showRoute();
})();
