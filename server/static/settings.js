(() => {
  const root = document.getElementById('settings-view');
  if (!root) return;
  const TOKEN_KEY = 'client_evidence.admin_token';
  const booleanKeys = ['drift_enabled', 'notes_matching', 'send_to_sf'];
  let baseline;
  let catalog = [];
  let busy = false;
  let dirty = false;
  let tokenValue = '';
  let controls = {};
  let selectedClient = 'medicare_billing_demo';
  let clients = [];

  const make = (tag, text, attributes = {}) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    Object.assign(element, attributes);
    return element;
  };
  const readToken = () => {
    try { return window.sessionStorage.getItem(TOKEN_KEY) || ''; }
    catch (error) { return tokenValue; }
  };
  const storeToken = (value) => {
    tokenValue = value;
    try {
      if (value) window.sessionStorage.setItem(TOKEN_KEY, value);
      else window.sessionStorage.removeItem(TOKEN_KEY);
    } catch (error) {
      // Saving settings still works when the browser blocks session storage.
    }
  };
  tokenValue = readToken();

  const style = make('style');
  style.textContent = `
    #settings-view { max-width:880px; line-height:1.5; }
    #settings-view h2 { margin:0 0 8px; font-size:24px; font-weight:500; }
    #settings-view h3 { margin:0 0 12px; font-size:18px; }
    #settings-view .settings-intro { color:var(--muted); margin:0 0 24px; }
    #settings-view fieldset { min-width:0; margin:0 0 20px; padding:20px; border:1px solid var(--line); border-radius:4px; background:var(--panel); }
    #settings-view legend { padding:0 6px; font-weight:600; }
    #settings-view .settings-check { display:flex; align-items:flex-start; gap:12px; margin:12px 0; }
    #settings-view .settings-check input { width:18px; height:18px; flex-shrink:0; margin:3px 0 0; accent-color:var(--accent); }
    #settings-view .settings-check strong { font-weight:500; }
    #settings-view .settings-help { display:block; color:var(--muted); font-size:13px; margin:4px 0 0; }
    #settings-view .settings-label { display:block; margin:8px 0; font-weight:500; }
    #settings-view input[type=password], #settings-view select { max-width:100%; padding:10px; border:1px solid var(--line); border-radius:4px; background:var(--bg); color:var(--ink); }
    #settings-view input[type=password] { display:block; width:420px; }
    #settings-view .settings-actions { display:flex; gap:12px; flex-wrap:wrap; margin:20px 0; }
    #settings-view button { min-height:44px; padding:10px 16px; border:1px solid var(--accent); border-radius:4px; color:var(--bg); background:var(--accent); cursor:pointer; }
    #settings-view button.secondary { color:var(--ink); background:transparent; border-color:var(--line); }
    #settings-view button.delete { color:var(--broken); background:transparent; border-color:var(--broken); }
    #settings-view button:disabled { cursor:default; opacity:.6; }
    #settings-view :is(button,input,select,a):focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
    #settings-view .settings-notice { padding:12px; border-left:3px solid var(--accent); margin:12px 0; }
    #settings-view [hidden] { display:none; }
    #settings-view .settings-audit { list-style:none; margin:12px 0; padding:0; }
    #settings-view .settings-audit li { padding:14px 0; border-bottom:1px solid var(--line); overflow-wrap:anywhere; }
    #settings-view .settings-audit p { margin:4px 0; font-size:13px; }
    #settings-view #client-settings-status { min-height:24px; overflow-wrap:anywhere; }
    #settings-view #client-settings-status[role=alert] { color:var(--broken); }
    #settings-view .settings-loading { height:160px; border-radius:4px; }
  `;
  const status = make('p', 'Loading client settings…', { id: 'client-settings-status', role: 'status' });
  status.setAttribute('aria-live', 'polite');
  const body = make('div', undefined, { id: 'client-settings-body' });
  const clientPicker = make('select', undefined, { id: 'settings-client-picker', 'aria-label': 'Client company' });
  root.replaceChildren(style, make('h2', 'Client settings'), make('label', 'Active client company', { htmlFor: 'settings-client-picker', className: 'settings-label' }), clientPicker,
    make('p', 'Choose what is measured for this client. Usage monitoring is off until the client enables it.', { className: 'settings-intro' }), status, body);

  function report(message, error = false) {
    status.setAttribute('role', error ? 'alert' : 'status');
    status.textContent = message;
  }

  function snapshot(value) {
    if (!value || !booleanKeys.every(key => typeof value[key] === 'boolean') ||
        !Array.isArray(value.contracts_watched) || !value.contracts_watched.every(id => typeof id === 'string') ||
        ![30, 90].includes(value.retention_days)) throw new Error('The server returned incomplete settings.');
    return { ...value, contracts_watched: value.contracts_watched.slice(), audit: Array.isArray(value.audit) ? value.audit.slice(-20) : [] };
  }

  async function getJSON(path) {
    const separator = path.includes('?') ? '&' : '?';
    const scopedPath = path === '/api/settings' ? path + separator + 'company_id=' + encodeURIComponent(selectedClient) : path;
    const response = await fetch(scopedPath, { cache: 'no-store' });
    if (!response.ok) throw new Error('Could not load the saved settings and contracts.');
    return response.json();
  }

  function setBusy(value) {
    busy = value;
    body.querySelectorAll('input, select, button').forEach(element => { element.disabled = value; });
  }

  function checkbox(id, title, help, checked, parent) {
    const input = make('input', undefined, { id, type: 'checkbox', checked });
    const words = make('span');
    words.append(make('strong', title));
    if (help) words.append(make('span', help, { className: 'settings-help' }));
    const label = make('label', undefined, { className: 'settings-check', htmlFor: id });
    label.append(input, words);
    parent.append(label);
    return input;
  }

  function render() {
    const form = make('form');
    controls = {};
    const monitoring = make('fieldset');
    monitoring.append(make('legend', 'Usage monitoring'));
    controls.drift_enabled = checkbox('settings-drift', 'Enable usage monitoring', 'Measure the selected behaviour contracts. No usage events are collected while this is off.', baseline.drift_enabled, monitoring);
    const notice = make('p', undefined, { className: 'settings-notice', hidden: !baseline.drift_enabled });
    const privacy = make('a', 'Privacy notice', { href: '/privacy' });
    notice.append(document.createTextNode('Tell staff what will be measured before enabling monitoring. '), privacy);
    monitoring.append(notice);
    controls.drift_enabled.onchange = () => { notice.hidden = !controls.drift_enabled.checked; };
    controls.notes_matching = checkbox('settings-notes', 'Match patterns in notes', 'Match locally in the claim screen; send pattern tags instead of note text.', baseline.notes_matching, monitoring);
    controls.send_to_sf = checkbox('settings-send', 'Allow Software Factory handoff', 'Enable the simulated feedback handoff. No live Software Factory connection.', baseline.send_to_sf, monitoring);

    const watched = make('fieldset');
    watched.append(make('legend', 'Contracts to watch'), make('p', 'Choose any contracts, or leave them all unselected.', { className: 'settings-help' }));
    controls.contracts = catalog.map((contract, index) => {
      const input = checkbox(`settings-contract-${index}`, contract.id,
        contract.requirement?.statement || 'Approved behaviour contract', baseline.contracts_watched.includes(contract.id), watched);
      input.value = contract.id;
      return input;
    });
    if (!catalog.length) watched.append(make('p', 'No contracts are available yet.'));

    const retention = make('fieldset');
    retention.append(make('legend', 'Retention'), make('label', 'Keep usage data for', { htmlFor: 'settings-retention', className: 'settings-label' }));
    controls.retention_days = make('select', undefined, { id: 'settings-retention' });
    for (const days of [30, 90]) controls.retention_days.append(make('option', `${days} days`, { value: String(days) }));
    controls.retention_days.value = String(baseline.retention_days);
    retention.append(controls.retention_days);

    const admin = make('fieldset');
    admin.append(make('legend', 'Save changes'), make('label', 'Admin token', { htmlFor: 'settings-admin-token', className: 'settings-label' }));
    controls.token = make('input', undefined, { type: 'password', id: 'settings-admin-token', value: tokenValue, autocomplete: 'off', spellcheck: false });
    controls.token.addEventListener('input', () => storeToken(controls.token.value.trim()));
    admin.append(controls.token, make('p', 'Kept for this tab’s session when browser storage is available. Also used by contract draft approvals.', { className: 'settings-help' }));
    const actions = make('div', undefined, { className: 'settings-actions' });
    const save = make('button', 'Save settings', { type: 'submit' });
    const reload = make('button', 'Reload saved settings', { type: 'button', className: 'secondary' });
    reload.onclick = load;
    actions.append(save, reload);
    admin.append(actions);
    const purge = make('button', 'Turn off and delete data', { type: 'button', className: 'delete' });
    purge.onclick = () => saveChanges(true);
    admin.append(purge, make('p', 'Turns monitoring off and deletes stored live usage events for this client.', { className: 'settings-help' }));
    form.append(monitoring, watched, retention, admin);
    form.onsubmit = (event) => { event.preventDefault(); saveChanges(false); };
    form.addEventListener('change', event => { if (event.target !== controls.token) dirty = true; });

    const audit = make('section');
    audit.append(make('h3', 'Recent changes'));
    const list = make('ol', undefined, { className: 'settings-audit' });
    const names = { drift_enabled: 'Usage monitoring', notes_matching: 'Notes pattern matching', send_to_sf: 'Software Factory handoff', contracts_watched: 'Watched contracts', retention_days: 'Retention days' };
    for (const entry of baseline.audit.slice().reverse()) {
      const item = make('li');
      const time = new Date(entry.ts);
      const when = Number.isNaN(time.getTime()) ? String(entry.ts || '') : time.toLocaleString();
      item.append(make('strong', `${entry.actor || 'Unknown actor'} · ${when}`));
      const changes = Object.entries(entry.changes || {}).map(([key, value]) => {
        const label = names[key] || key.replaceAll('_', ' ');
        const text = typeof value === 'boolean' ? (value ? 'On' : 'Off') : Array.isArray(value) ? (value.join(', ') || 'None') : String(value);
        return `${label}: ${text}`;
      });
      if (entry.purged_live_events) changes.push('Stored live usage events deleted');
      item.append(make('p', changes.join(' · ')));
      list.append(item);
    }
    audit.append(baseline.audit.length ? list : make('p', 'No changes recorded yet.', { className: 'settings-help' }));
    body.replaceChildren(form, audit);
    dirty = false;
  }

  function changedValues() {
    const changes = {};
    for (const key of booleanKeys) if (controls[key].checked !== baseline[key]) changes[key] = controls[key].checked;
    const days = Number(controls.retention_days.value);
    if (days !== baseline.retention_days) changes.retention_days = days;
    const selected = controls.contracts.filter(input => input.checked).map(input => input.value);
    if (JSON.stringify(selected.slice().sort()) !== JSON.stringify(baseline.contracts_watched.slice().sort())) changes.contracts_watched = selected;
    return changes;
  }

  async function saveChanges(purge) {
    if (busy || !baseline) return;
    const token = controls.token.value.trim();
    if (!token) {
      report('Enter the admin token to save changes.', true);
      controls.token.focus();
      return;
    }
    storeToken(token);
    const changes = purge ? { drift_enabled: false, purge: true } : changedValues();
    if (!Object.keys(changes).length) { report('No settings changes to save.'); return; }
    setBusy(true);
    report('Saving settings…');
    try {
      const response = await fetch('/api/settings?company_id=' + encodeURIComponent(selectedClient), { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Admin-Token': token }, body: JSON.stringify(changes) });
      if (!response.ok) throw new Error(response.status === 401 ? 'The admin token was not accepted. Correct it and try again.' : 'The server could not save these changes. Your edits are still here.');
      const saved = snapshot(await response.json());
      let auditAvailable = true;
      try { baseline = snapshot(await getJSON('/api/settings')); }
      catch (error) { baseline = { ...saved, audit: baseline.audit }; auditAvailable = false; }
      render();
      report((purge ? 'Monitoring is off and stored live usage events are cleared.' : 'Settings saved.') + (auditAvailable ? '' : ' The audit list could not refresh; reload saved settings to retry.'));
    } catch (error) {
      report(error.message || 'Could not reach the server. Your edits are still here.', true);
    } finally {
      setBusy(false);
    }
  }

  async function load() {
    if (busy) return;
    setBusy(true);
    report('Loading client settings…');
    if (!baseline) {
      const skeleton = make('div', undefined, { className: 'skeleton settings-loading' });
      skeleton.setAttribute('aria-hidden', 'true');
      body.replaceChildren(skeleton);
    }
    try {
      const [options, settings, contracts] = await Promise.all([fetch('/api/interview-options', { cache: 'no-store' }).then(r => r.json()), getJSON('/api/settings'), getJSON('/api/contracts')]);
      clients = options.companies || [];
      clientPicker.replaceChildren(...clients.map(client => make('option', client.name, { value: client.id })));
      clientPicker.value = selectedClient;
      if (!Array.isArray(contracts) || !contracts.every(c => c && typeof c.id === 'string')) throw new Error('Could not load the available contracts.');
      baseline = snapshot(settings);
      catalog = [...new Map(contracts.map(c => [c.id, c])).values()];
      tokenValue = readToken();
      render();
      report('Saved settings loaded.');
    } catch (error) {
      if (!baseline) {
        const retry = make('button', 'Retry loading settings', { type: 'button' });
        retry.onclick = load;
        body.replaceChildren(retry);
      }
      report(error.message || 'Could not reach the server. Retry loading settings.', true);
    } finally {
      setBusy(false);
    }
  }

  window.addEventListener('hashchange', () => {
    if (location.hash === '#settings' && !dirty && !busy) load();
  });
  clientPicker.addEventListener('change', () => { selectedClient = clientPicker.value; baseline = null; load(); });
  load();
})();
