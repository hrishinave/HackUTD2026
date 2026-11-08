(() => {
  const views = {
    interview: { title: "Interview", endpoint: "/api/interviews/INT-01/state", mock: "/static/mock/state.json" },
    contracts: { title: "Contracts", endpoint: "/api/contracts", mock: "/static/mock/contracts.json" },
    drift: { title: "Drift", endpoint: "/api/drift", mock: "/static/mock/drift.json" },
    finding: { title: "Finding detail", endpoint: "/api/findings", mock: "/static/mock/findings.json" },
    settings: { title: "Client settings" }
  };
  const useMocks = new URLSearchParams(window.location.search).get("mock") === "1";
  const byId = (id) => document.getElementById(id);
  const title = byId("page-title");
  const status = byId("connection-status");
  const navigation = [...document.querySelectorAll("[data-route]")];
  const received = new Map();
  let generation = 0;
  let controller;
  let pollTimer;
  let focusedLineage = "";

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
    document.querySelectorAll(".lineage-target").forEach((node) => node.classList.remove("lineage-target"));
    if (route.name !== "interview" || !route.detail) return;
    const target = [...document.querySelectorAll("[data-question-id]")].find((node) => node.dataset.questionId === route.detail);
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
      article.append(details);
      list.append(article);
    }
    if (!data.contracts.length) list.append(element("p", "No contracts have been supplied yet.", "empty-copy"));
    byId("contracts-list").replaceChildren(list);

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
    const response = await fetch(useMocks ? config.mock : config.endpoint, { headers: { Accept: "application/json" }, signal, cache: "no-store" });
    if (!response.ok) throw new Error("Evidence unavailable");
    return response.json();
  }

  function showRoute() {
    const route = currentRoute();
    const config = views[route.name];
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
    if (!config.endpoint) { status.textContent = "Local client settings"; return; }
    const message = document.querySelector('[data-message="' + route.name + '"]');
    const skeletons = document.querySelector("#" + route.name + "-view .loading-grid");
    const content = byId(route.name + "-content");
    const requestController = new AbortController();
    controller = requestController;
    const firstLoad = !received.has(route.name);
    if (skeletons) skeletons.hidden = !firstLoad;
    if (firstLoad && message) message.textContent = "Loading evidence…";
    if (firstLoad) status.textContent = useMocks ? "Loading synthetic preview" : "Connecting to local server";
    const timeout = setTimeout(() => requestController.abort(), 6000);
    try {
      let data = await requestData(config, requestController.signal);
      if (route.name === "contracts") {
        const interview = await requestData(views.interview, requestController.signal).catch(() => null);
        data = { contracts: data, interview };
      }
      if (currentGeneration !== generation) return;
      const serialized = JSON.stringify(data);
      if (received.get(route.name) !== serialized) {
        if (route.name === "interview") renderInterview(data);
        if (route.name === "contracts") renderContracts(data);
        received.set(route.name, serialized);
      }
      if (skeletons) skeletons.hidden = true;
      if (content) content.hidden = false;
      status.textContent = useMocks ? "Showing synthetic preview data" : "Connected to local server";
      if (message) message.textContent = route.name === "interview" ? "Interview state refreshes every second." : route.name === "contracts" ? "Synthetic interview evidence and contract targets." : "Data received. Evidence views will appear here.";
      focusLineage(route);
    } catch {
      if (currentGeneration !== generation) return;
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
  window.addEventListener("pagehide", () => { ++generation; clearTimeout(pollTimer); controller?.abort(); });
  showRoute();
})();
