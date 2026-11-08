(() => {
  const byId = (id) => document.getElementById(id);
  const form = byId("claim-form");
  const token = document.querySelector('meta[name="client-token"]').content;
  const sessionId = crypto.randomUUID();
  const claimId = crypto.randomUUID();
  let settings = { drift_enabled: false, notes_matching: false };
  let activeTab = "main";
  let submitted = false;
  let focusBeforePointer = null;

  function procedure() {
    const select = byId("procedure-code");
    return { procedure_code: select.value, requires_prior_auth: select.selectedOptions[0].dataset.requiresPriorAuth === "true" };
  }

  async function send(event, props) {
    if (!settings.drift_enabled) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch("/api/events", {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json", "X-Client-Token": token },
        body: JSON.stringify({ event, role: "billing_clerk", session_id: sessionId, claim_id_hash: claimId, props })
      });
      if (response.status === 403) {
        settings.drift_enabled = false;
        byId("monitoring-status").textContent = "Usage monitoring is off";
      } else if (!response.ok) {
        byId("monitoring-status").textContent = "Usage event could not be recorded. Claim entry remains available.";
      }
    } catch {
      byId("monitoring-status").textContent = "Usage monitoring connection unavailable. Claim entry remains available.";
    } finally {
      clearTimeout(timeout);
    }
  }

  function selectTab(name) {
    activeTab = name;
    for (const tab of ["main", "authorization"]) {
      byId(`${tab}-tab`).setAttribute("aria-selected", String(tab === name));
      byId(`${tab}-tab`).tabIndex = tab === name ? 0 : -1;
      byId(`${tab}-panel`).hidden = tab !== name;
    }
    send("claim_tab_viewed", { tab: name });
  }

  form.addEventListener("pointerdown", () => { focusBeforePointer = document.activeElement; });
  form.addEventListener("click", (event) => {
    const control = event.target.closest("button, input, select, textarea");
    if (!control || !control.id || control.disabled) return;
    let changed = control !== focusBeforePointer;
    if (control.id === "main-tab" || control.id === "authorization-tab") {
      const name = control.id === "main-tab" ? "main" : "authorization";
      changed = name !== activeTab;
      selectTab(name);
    } else if (control.id === "submit-claim") {
      changed = !submitted && form.checkValidity();
    }
    send("ui_click", { element_id: control.id.replaceAll("-", "_"), changed_state: changed });
  });

  form.addEventListener("keydown", (event) => {
    if (!["main-tab", "authorization-tab"].includes(event.target.id)) return;
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const name = event.key === "Home" ? "main" : event.key === "End" ? "authorization" : activeTab === "main" ? "authorization" : "main";
    byId(`${name}-tab`).focus();
    byId(`${name}-tab`).click();
  });

  // A required Main field may be hidden when Submit is clicked on Authorization.
  form.addEventListener("invalid", (event) => {
    if (byId("main-panel").contains(event.target) && activeTab !== "main") selectTab("main");
  }, true);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (submitted) return;
    submitted = true;
    const details = procedure();
    const authFilled = Boolean(byId("prior-auth-number").value.trim());
    const props = { ...details, prior_auth_number_filled: authFilled, first_pass_clean: !details.requires_prior_auth || authFilled };
    if (settings.notes_matching) {
      const notes = byId("claim-notes").value;
      props.notes_patterns = [];
      if (/\b(auth|pa)\s*#?\s*\d{4,}\b/i.test(notes)) props.notes_patterns.push("auth_number");
      if (/see fax/i.test(notes)) props.notes_patterns.push("see_fax");
    }
    send("claim_submitted", props);
    byId("submit-claim").disabled = true;
    byId("claim-result").textContent = "Demo claim submitted. No claim was sent to a payer.";
  });

  async function initialize() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch("/api/settings", { signal: controller.signal, cache: "no-store" });
      if (!response.ok) throw new Error("Settings unavailable");
      settings = await response.json();
      // Require an explicit boolean opt-in before sending anything.
      settings.drift_enabled = settings.drift_enabled === true;
      settings.notes_matching = settings.notes_matching === true;
      byId("monitoring-status").textContent = settings.drift_enabled ? "Usage monitoring is on · flags and tags only" : "Usage monitoring is off";
      if (settings.drift_enabled) {
        await send("claim_opened", { claim_type: "professional", ...procedure() });
      }
    } catch {
      settings = { drift_enabled: false, notes_matching: false };
      byId("monitoring-status").textContent = "Usage monitoring settings unavailable. No usage events will be sent.";
    } finally {
      clearTimeout(timeout);
      byId("monitoring-loading").hidden = true;
      byId("claim-controls").disabled = false;
    }
  }

  initialize();
})();
