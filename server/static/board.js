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
  const charts = [];
  let lastDrift;
  let feedbackPayload;
  let drawerGeneration = 0;
  const settingsResource = { endpoint: "/api/settings", mock: "/static/mock/settings.json" };
  function stateChip(state) {
    const chip = element("span", (state || "not measured").replaceAll("_", " "), "status-chip state-" + (state || "not_measured"));
    chip.dataset.state = state || "not_measured";
    return chip;
  }

  function metricValue(value, unit) {
    if (!Number.isFinite(value)) return "Not measured";
    return unit === "share" ? percent(value) : Number(value.toFixed(2)).toLocaleString() + (unit === "seconds" ? " s" : " / week");
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
        { label: expectation.description || expectation.metric_id, data: weeks.map((week) => week.values?.[expectation.metric_id] ?? null), borderColor: "#0F6E6E", backgroundColor: "#0F6E6E", borderWidth: 2, pointRadius: 3 }
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
    if (finding.lineage) lineage.append(quote({ ...finding.lineage, question_origin: "ai" }));
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
    const firstLoad = !received.has(route.name + ":" + route.detail);
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
      if (route.name === "drift") data = { drift: data, findings: await requestData(views.finding, requestController.signal) };
      if (route.name === "finding") data = { findings: data, settings: await requestData(settingsResource, requestController.signal) };
      if (currentGeneration !== generation) return;
      const serialized = JSON.stringify(data);
      const cacheKey = route.name + ":" + route.detail;
      if (received.get(cacheKey) !== serialized) {
        if (route.name === "interview") renderInterview(data);
        if (route.name === "contracts") renderContracts(data);
        if (route.name === "drift") renderDrift(data);
        if (route.name === "finding") renderFinding(data, route.detail);
        received.set(cacheKey, serialized);
      }
      if (skeletons) skeletons.hidden = true;
      if (content) content.hidden = false;
      status.textContent = useMocks ? "Showing synthetic preview data" : "Connected to local server";
      if (message) message.textContent = route.name === "interview" ? "Interview state refreshes every second." : route.name === "contracts" ? "Synthetic interview evidence and contract targets." : "Synthetic demonstration · client monitoring permissions apply.";
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
    if (!feedbackPayload) return;
    const version = drawerGeneration;
    const payload = feedbackPayload;
    byId("sf-file").disabled = true;
    byId("sf-result").textContent = "Filing simulated feedback…";
    try {
      const response = await fetch(useMocks ? "/static/mock/sf-reply.json" : "/stub/v2/reporting-api/feedback", useMocks ? { signal: AbortSignal.timeout(6000) } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal: AbortSignal.timeout(6000) });
      if (!response.ok) throw new Error("Feedback unavailable");
      const reply = await response.json();
      if (!Number.isInteger(reply.feedback_number)) throw new Error("Invalid feedback response");
      if (version !== drawerGeneration) return;
      byId("sf-feedback-id").textContent = "FB-" + reply.feedback_number;
      byId("sf-result").textContent = "FB-" + reply.feedback_number + " filed · Simulated, no live connection";
      feedbackPayload = null;
    } catch {
      if (version !== drawerGeneration) return;
      byId("sf-result").textContent = "Feedback was not confirmed. Check the local stub before retrying.";
      byId("sf-file").disabled = false;
    }
  });
  window.addEventListener("pagehide", () => { ++generation; clearTimeout(pollTimer); controller?.abort(); charts.splice(0).forEach((chart) => chart.destroy()); });
  showRoute();
})();
