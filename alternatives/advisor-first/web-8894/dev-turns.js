/**
 * Dev turn panel for local testing of the advisor (D155 Q6b).
 *
 * Purpose: shows Charlie, one turn at a time, what happened behind each chat
 * turn: turn ID, facts saved, source lookups (tool calls with inputs and
 * outputs), model calls (model, tokens, latency, status), checks fired and
 * the next question, with "Show full prompt" and "Show raw output".
 *
 * Role: a self-contained script loaded by index.html. It does nothing unless
 * /ten-config.json says devTraces is true, which the backend sets only for a
 * local, non-pilot run that is saving turn traces (turn_trace.py). Data comes
 * from GET /api/dev/turns and /api/dev/turns/<turnId>, scoped to this visit's
 * cookie.
 *
 * Decisions: a separate file (not inline) to satisfy the page CSP
 * (script-src 'self'); text is inserted with textContent only, never as HTML,
 * because traces hold model output; the list refreshes every 3 seconds only
 * while the panel is open, so a closed panel costs nothing.
 */
(() => {
  'use strict';
  const POLL_MS = 3000;
  let open = false, timer = null, selected = null, known = '';

  /** Fetch JSON from the same origin with the visit cookie; throws on non-2xx. */
  async function getJson(path) {
    const response = await fetch(path, {credentials: 'same-origin', headers: {Accept: 'application/json'}});
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || response.statusText);
    return response.json();
  }

  /** Create an element with a class and optional text (never HTML). */
  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  /** Pretty-print a value for a <pre> block. */
  function pretty(value) {
    return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  }

  /** A titled section; returns its body element. */
  function section(parent, title, count) {
    const box = el('section', 'dt-section');
    box.append(el('h3', '', count === undefined ? title : `${title} (${count})`));
    const body = el('div', 'dt-body');
    box.append(body);
    parent.append(box);
    return body;
  }

  /** A collapsible block with a button-like summary and preformatted content. */
  function reveal(parent, label, value) {
    const details = el('details', 'dt-reveal');
    details.append(el('summary', '', label));
    details.append(el('pre', '', pretty(value)));
    parent.append(details);
  }

  /** Render one full turn record into the detail pane. */
  function renderTurn(pane, turn) {
    pane.replaceChildren();
    const head = el('div', 'dt-turn-head');
    head.append(el('code', 'dt-id', turn.turnId));
    const copy = el('button', 'dt-copy', 'Copy ID');
    copy.type = 'button';
    copy.addEventListener('click', () => navigator.clipboard?.writeText(turn.turnId));
    head.append(copy);
    pane.append(head);
    pane.append(el('p', 'dt-meta', `${turn.startedAt} · ${turn.status} · ${turn.latencyMs} ms · ${turn.action || ''}`));
    if (turn.message) pane.append(el('p', 'dt-message', `“${turn.message}”`));
    if (turn.error) pane.append(el('p', 'dt-error', turn.error));

    const facts = section(pane, 'Facts saved', (turn.factsSaved || []).length);
    if (!(turn.factsSaved || []).length) facts.append(el('p', 'dt-empty', 'None this turn.'));
    for (const row of turn.factsSaved || []) {
      facts.append(el('p', 'dt-row', `${row.field}: ${pretty(row.before)} → ${pretty(row.after)}`));
    }

    const tools = section(pane, 'Tool calls', (turn.toolCalls || []).length);
    for (const call of turn.toolCalls || []) {
      tools.append(el('p', 'dt-row dt-strong', `${call.tool} (${call.stage})`));
      reveal(tools, 'Input', call.input);
      reveal(tools, 'Output', call.output);
    }

    const models = section(pane, 'Model calls', (turn.modelCalls || []).length);
    for (const call of turn.modelCalls || []) {
      const tokens = call.tokens ? `${call.tokens.input_tokens ?? '?'} in / ${call.tokens.output_tokens ?? '?'} out` : 'no usage';
      models.append(el('p', 'dt-row dt-strong', `${call.kind} · ${call.model} · ${call.status} · ${call.latencyMs} ms · ${tokens}`));
      if (call.error) models.append(el('p', 'dt-error', call.error));
      if (call.request) reveal(models, 'Show full prompt', call.request);
      if (call.rawOutput !== undefined && call.rawOutput !== null) reveal(models, 'Show raw output', call.rawOutput);
    }

    const checks = section(pane, 'Checks fired', (turn.checks || []).length);
    if (!(turn.checks || []).length) checks.append(el('p', 'dt-empty', 'None this turn.'));
    for (const check of turn.checks || []) {
      checks.append(el('p', 'dt-row', `[${check.source}] ${check.message}`));
      if (check.detail) reveal(checks, 'Detail', check.detail);
    }

    const next = section(pane, 'Next question');
    next.append(el('pre', '', pretty(turn.nextQuestion ?? 'none')));
    if (turn.reply) reveal(next, 'Reply shown', turn.reply);
  }

  /** Load and show one turn by ID. */
  async function select(pane, list, turnId) {
    selected = turnId;
    for (const item of list.children) item.classList.toggle('dt-selected', item.dataset.turnId === turnId);
    try { renderTurn(pane, await getJson('/api/dev/turns/' + encodeURIComponent(turnId))); }
    catch (error) { pane.replaceChildren(el('p', 'dt-error', error.message)); }
  }

  /** Refresh the turn list; select the newest turn when a new one arrives. */
  async function refresh(list, pane) {
    let turns;
    try { turns = (await getJson('/api/dev/turns')).turns || []; }
    catch (error) { list.replaceChildren(el('li', 'dt-error', error.message)); return; }
    const signature = turns.map(turn => turn.turnId + turn.status).join();
    if (signature === known) return;
    const newest = turns.length ? turns[turns.length - 1].turnId : null;
    const arrived = newest && !known.includes(newest);
    known = signature;
    list.replaceChildren();
    turns.forEach((turn, index) => {
      const item = el('li', 'dt-item');
      item.dataset.turnId = turn.turnId;
      const button = el('button', '', `${index + 1}. ${turn.message || turn.action || 'turn'}`);
      button.type = 'button';
      button.addEventListener('click', () => select(pane, list, turn.turnId));
      item.append(button);
      list.append(item);
    });
    if (arrived || !selected) { if (newest) await select(pane, list, newest); }
    else for (const item of list.children) item.classList.toggle('dt-selected', item.dataset.turnId === selected);
  }

  /** Build the toggle and panel once dev traces are confirmed on. */
  function mount() {
    const toggle = el('button', 'dt-toggle', 'Turns');
    toggle.type = 'button';
    toggle.setAttribute('aria-expanded', 'false');
    const panel = el('aside', 'dt-panel');
    panel.setAttribute('aria-label', 'Turn traces (local testing)');
    panel.hidden = true;
    const header = el('div', 'dt-header');
    header.append(el('h2', '', 'Turn traces'), el('span', 'dt-note', 'Local testing only'));
    const close = el('button', 'dt-close', 'Close');
    close.type = 'button';
    header.append(close);
    const list = el('ol', 'dt-list');
    const pane = el('div', 'dt-pane');
    pane.append(el('p', 'dt-empty', 'Send a message to see its turn.'));
    panel.append(header, list, pane);
    document.body.append(toggle, panel);

    const setOpen = value => {
      open = value;
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      document.body.classList.toggle('dt-open', open);
      clearInterval(timer);
      if (open) { refresh(list, pane); timer = setInterval(() => refresh(list, pane), POLL_MS); }
    };
    toggle.addEventListener('click', () => setOpen(!open));
    close.addEventListener('click', () => setOpen(false));
  }

  getJson('/ten-config.json').then(config => { if (config && config.devTraces === true) mount(); }).catch(() => {});
})();
