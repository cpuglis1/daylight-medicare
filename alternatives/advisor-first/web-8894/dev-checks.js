/**
 * Checks and instructions page for local testing (D155 Q8, Q2).
 *
 * Purpose: lets Charlie edit the conversation checks (each one an eval with its
 * own judge in tools/evaluation/sim_conversations.py) and the ordering guidance
 * paragraph the compose model reads, then save both with one button.
 *
 * Role: loaded by dev-checks.html. Reads GET /api/dev/checks and saves with
 * POST /api/dev/checks (cookie plus the X-Daylight-CSRF header from
 * GET /api/guest/session). Those routes exist only on a local run that saves
 * turn traces; anywhere else the page says it is unavailable.
 *
 * Decisions: a separate file for the page CSP (script-src 'self'); all text is
 * set with textContent or input values, never as HTML; gates are rendered as
 * read-only text with no inputs, and the server refuses gate edits anyway;
 * only changed fields are sent, so a save cannot touch what Charlie left alone.
 */
(() => {
  'use strict';
  const root = document.getElementById('dc-root');
  let csrf = '', loaded = null, defaultGuidance = '';

  /** Same-origin JSON request; POST sends the CSRF header. Throws with the server's error text. */
  async function api(path, body) {
    const init = {credentials: 'same-origin', headers: {Accept: 'application/json'}};
    if (body !== undefined) {
      init.method = 'POST';
      init.headers['Content-Type'] = 'application/json';
      init.headers['X-Daylight-CSRF'] = csrf;
      init.body = JSON.stringify(body);
    }
    const response = await fetch(path, init);
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(value.error || response.statusText);
    return value;
  }

  /** Create an element with a class and optional text (never HTML). */
  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  /** A labeled input; returns {wrap, input}. */
  function field(label, input) {
    const wrap = el('label', 'dc-field', label);
    wrap.append(input);
    return wrap;
  }

  /** Render one check card. Editable checks get inputs keyed by data attributes. */
  function renderCheck(check) {
    const card = el('section', 'dc-check');
    card.dataset.id = check.id;
    const head = el('div', 'dc-check-head');
    head.append(el('h3', '', check.title), el('code', '', check.id));
    if (check.decision) head.append(el('span', 'dc-badge', check.decision));
    head.append(el('span', 'dc-badge', check.gate ? 'Gate: read-only' : check.editable ? 'Editable' : 'Read-only'));
    card.append(head);
    if (!check.editable) {
      card.append(el('p', 'dc-readonly', check.question));
      card.append(el('p', 'dc-status', `Floor ${Math.round(check.floor * 100)}% · ${check.failOnAny ? 'one failure fails it' : 'judged on pass rate'}`));
      return card;
    }
    const title = el('input');
    title.type = 'text'; title.maxLength = 80; title.value = check.title; title.dataset.key = 'title';
    const question = el('textarea');
    question.maxLength = 1200; question.value = check.question; question.dataset.key = 'question';
    const floor = el('input');
    floor.type = 'number'; floor.min = '0'; floor.max = '100'; floor.step = '1';
    floor.value = String(Math.round(check.floor * 100)); floor.dataset.key = 'floor';
    const any = el('input');
    any.type = 'checkbox'; any.checked = !!check.failOnAny; any.dataset.key = 'failOnAny';
    const anyWrap = el('label', 'dc-inline');
    anyWrap.append(any, el('span', '', 'One failure fails the check'));
    card.append(field('Title', title), field('What the judge checks', question), field('Floor (minimum pass rate, %)', floor), anyWrap);
    return card;
  }

  /** Collect only the fields that differ from what was loaded. */
  function changedChecks() {
    const edits = [];
    for (const check of loaded.checks) {
      if (!check.editable) continue;
      const card = root.querySelector(`[data-id="${CSS.escape(check.id)}"]`);
      const edit = {id: check.id};
      for (const input of card.querySelectorAll('[data-key]')) {
        const key = input.dataset.key;
        let value = input.type === 'checkbox' ? input.checked : input.value;
        if (key === 'floor') value = Number(value) / 100;
        if (value !== check[key]) edit[key] = value;
      }
      if (Object.keys(edit).length > 1) edits.push(edit);
    }
    return edits;
  }

  /** Draw the whole page from a GET/POST payload. */
  function render(data) {
    loaded = data;
    defaultGuidance = data.instructions.default;
    root.replaceChildren(el('h1', '', 'Checks and instructions'));
    root.append(el('p', 'dc-status', 'Local testing only. Edits save to the repo config files and apply to the next turn and the next simulated run.'));

    root.append(el('h2', '', 'Ordering guidance'));
    root.append(el('p', 'dc-status', 'What the AI reads about which questions tend to come first. The hard rules (who the visit is for and ZIP before plans, privacy, sources) stay in code.'));
    const guidance = el('textarea');
    guidance.id = 'dc-guidance'; guidance.maxLength = 2000; guidance.value = data.instructions.orderingGuidance;
    guidance.setAttribute('aria-label', 'Ordering guidance');
    const reset = el('button', 'dc-secondary', 'Restore built-in text');
    reset.type = 'button';
    reset.addEventListener('click', () => { guidance.value = defaultGuidance; });
    root.append(guidance, reset);

    root.append(el('h2', '', `Checks (${data.checks.length})`));
    for (const check of data.checks) root.append(renderCheck(check));

    const bar = el('div', 'dc-actions');
    const save = el('button', 'dc-save', 'Save changes');
    save.type = 'button';
    const status = el('span', 'dc-status', '');
    status.setAttribute('role', 'status');
    bar.append(save, status);
    root.append(bar);
    save.addEventListener('click', async () => {
      const body = {};
      const edits = changedChecks();
      if (edits.length) body.checks = edits;
      if (guidance.value !== data.instructions.orderingGuidance) body.orderingGuidance = guidance.value;
      if (!Object.keys(body).length) { status.className = 'dc-status'; status.textContent = 'Nothing changed.'; return; }
      save.disabled = true;
      status.className = 'dc-status'; status.textContent = 'Saving…';
      try {
        render(await api('/api/dev/checks', body));
        const after = root.querySelector('.dc-actions [role=status]');
        after.textContent = 'Saved.';
      } catch (error) {
        save.disabled = false;
        status.className = 'dc-error'; status.textContent = error.message;
      }
    });
  }

  (async () => {
    try {
      const session = await api('/api/guest/session');
      csrf = session.csrf || '';
      render(await api('/api/dev/checks'));
    } catch (error) {
      root.replaceChildren(el('h1', '', 'Checks and instructions'),
        el('p', 'dc-error', `Unavailable: ${error.message}. This page works only on a local run that saves turn traces.`));
    }
  })();
})();
