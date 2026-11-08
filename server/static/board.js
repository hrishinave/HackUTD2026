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

  // Live route first; while a teammate's route is not merged yet (FastAPI's bare "Not Found"), use the preview file.
  async function liveOrPreview(endpoint, mock, init = {}) {
    if (useMocks) return { response: await fetch(mock, { signal: init.signal, cache: "no-store" }), preview: true };
    const response = await fetch(endpoint, { cache: "no-store", ...init });
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

  function draftInterview(record) { return /^DR-(INT-\d{2})-\d+$/.exec(record.draft_id || "")?.[1] || "Unknown interview"; }

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
      const actions = element("div", null, "draft-actions");
      for (const action of ["approve", "reject"]) {
        const button = element("button", action === "approve" ? "Approve" : "Reject", action === "approve" ? "primary-button" : "secondary-button");
        button.type = "button"; button.disabled = decisionBusy || draftBusy;
        button.addEventListener("click", () => decideDraft(record, action)); actions.append(button);
      }
      card.append(actions); list.append(card);
    }
    if (!records.length) list.append(element("p", "No pending drafts for " + interview + ". Draft a saved interview to find new measurable requirements and open loops.", "empty-copy"));
    byId("draft-list").replaceChildren(list);
    const dropped = droppedByInterview.get(interview) || [];
    byId("draft-dropped").querySelector("summary").textContent = "Dropped by checks (" + dropped.length + ")";
    const droppedList = document.createDocumentFragment();
    for (const item of dropped) droppedList.append(element("li", item.requirement + " · " + (item.reasons || []).join("; ")));
    if (!dropped.length) droppedList.append(element("li", "No dropped results from a drafting run in this browser session.", "muted-copy"));
    byId("draft-dropped-list").replaceChildren(droppedList);
    byId("draft-run").disabled = draftBusy || decisionBusy;
    byId("draft-interview").disabled = draftBusy || decisionBusy;
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
    try { token = sessionStorage.getItem("fitcheck.admin_token"); } catch { /* Storage may be blocked. */ }
    if (token) return token;
    byId("draft-token").value = "";
    token = await promptDialog("draft-token-dialog");
    if (token) { try { sessionStorage.setItem("fitcheck.admin_token", token); } catch { /* The current action can still use the token. */ } }
    return token;
  }

  async function refreshDecisions() {
    const [records, contracts, interview, lifecycle] = await Promise.all([readDrafts(AbortSignal.timeout(10000)), requestData(views.contracts, AbortSignal.timeout(10000)), requestData(views.interview, AbortSignal.timeout(6000)).catch(() => null), readLifecycle(AbortSignal.timeout(6000))]);
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
        const response = await fetch("/api/drafts/" + encodeURIComponent(record.draft_id) + "/" + action, { method: "POST", headers: { "Content-Type": "application/json", "X-Admin-Token": token }, body: JSON.stringify(action === "reject" ? { reason } : {}), signal: AbortSignal.timeout(15000) });
        if (response.status === 401) {
          try { sessionStorage.removeItem("fitcheck.admin_token"); } catch { /* Storage may be blocked. */ }
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
    draftBusy = true; renderDrafts();
    byId("draft-message").textContent = "Drafting from saved interview evidence. Usually 10–30 seconds.";
    try {
      let data;
      if (useMocks) {
        if (!mockDraftBundle) await readDrafts(AbortSignal.timeout(6000));
        if (interview !== mockDraftBundle.interview_id) throw new Error("No saved interview yet for " + interview);
        data = structuredClone(mockDraftBundle);
      } else {
        const response = await fetch("/api/drafts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ interview_id: interview }), signal: AbortSignal.timeout(120000) });
        if (response.status === 404) throw new Error("No saved interview yet for " + interview);
        if (response.status === 409) throw new Error("Already drafting, wait a few seconds");
        if (!response.ok) throw new Error("Drafting failed, try again; earlier drafts are unchanged");
        data = await response.json();
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
        try { draftRecords = await readDrafts(requestController.signal); }
        catch { byId("draft-message").textContent = "Draft records unavailable. Earlier contract evidence is still shown."; }
        const interview = await requestData(views.interview, requestController.signal).catch(() => null);
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
      if (message) message.textContent = route.name === "interview" ? "Interview state refreshes every second." : route.name === "contracts" ? "Synthetic interview evidence and contract targets." : "Synthetic demonstration · client monitoring permissions apply.";
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
  byId("draft-interview").value = useMocks ? "INT-01" : "INT-02";
  byId("draft-interview").addEventListener("change", () => { byId("draft-message").textContent = ""; renderDrafts(); });
  byId("draft-run").addEventListener("click", runDrafts);
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
  window.addEventListener("pagehide", () => { ++generation; clearTimeout(pollTimer); controller?.abort(); charts.splice(0).forEach((chart) => chart.destroy()); });
  showRoute();
})();
