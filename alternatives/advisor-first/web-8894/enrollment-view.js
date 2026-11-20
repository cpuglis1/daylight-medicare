/* D161: Parts A and B as the foundation (owner direction, November 12, 2026).
   View only. Every status, date and sentence drawn here is supplied by the
   server (enrollment_flow.view and /api/enrollment/content). This file infers
   nothing, stores nothing and never asks for a Social Security number,
   Medicare number or password. The step drawings are Daylight's own. */
(function (root) {
  'use strict';
  const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const doc = () => root.document;
  function el(tag, text, cls) {const n = doc().createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n;}
  function button(label, run, cls) {const b = el('button', label, cls || 'secondary-button'); b.type = 'button'; b.onclick = run; return b;}
  function link(label, url, cls) {const a = el('a', label, cls); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;}
  function longDate(iso) {const [y, m, d] = String(iso).split('-').map(Number); return MONTHS[m - 1] + ' ' + d + ', ' + y;}

  // Simple line drawings, one per step. Decorative: the words carry the meaning.
  const SVG = body => '<svg viewBox="0 0 72 56" width="72" height="56" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" focusable="false">' + body + '</svg>';
  const DRAWINGS = {
    browser: SVG('<rect x="6" y="8" width="60" height="40" rx="5"/><path d="M6 18h60"/><circle cx="13" cy="13" r="1.2"/><circle cx="19" cy="13" r="1.2"/><path d="M16 28h24M16 36h34"/>'),
    check: SVG('<rect x="16" y="8" width="40" height="42" rx="4"/><path d="M28 8v-3h16v3"/><path d="M26 30l7 7 13-14"/>'),
    lock: SVG('<rect x="18" y="24" width="36" height="26" rx="4"/><path d="M26 24v-7a10 10 0 0 1 20 0v7"/><path d="M36 34v6"/>'),
    person: SVG('<rect x="6" y="8" width="60" height="40" rx="5"/><circle cx="24" cy="24" r="6"/><path d="M13 42c2-7 20-7 22 0"/><path d="M44 22h14M44 30h14M44 38h9"/>'),
    choice: SVG('<rect x="8" y="10" width="14" height="14" rx="3"/><path d="M11 17l3 3 5-6"/><path d="M30 17h34"/><rect x="8" y="32" width="14" height="14" rx="3"/><path d="M30 39h26"/>'),
    parts: SVG('<rect x="6" y="12" width="26" height="32" rx="4"/><rect x="40" y="12" width="26" height="32" rx="4"/><path d="M14 36l5-16 5 16M16 31h6"/><path d="M48 20v16h6a4 4 0 0 0 0-8h-6h5a4 4 0 0 0 0-8z"/>'),
    calendar: SVG('<rect x="10" y="12" width="52" height="38" rx="4"/><path d="M10 22h52M22 8v8M50 8v8"/><path d="M20 31h6M33 31h6M46 31h6M20 41h6M33 41h6"/>'),
    send: SVG('<path d="M8 28l56-20-18 42-10-16z"/><path d="M36 34l28-26"/>'),
    receipt: SVG('<path d="M18 6h36v44l-6-4-6 4-6-4-6 4-6-4-6 4z"/><path d="M26 18h20M26 26h20M26 34h12"/>'),
    phone: SVG('<path d="M20 8h10l4 12-6 4c3 7 7 11 14 14l4-6 12 4v10c0 2-2 4-4 4C30 50 16 34 16 12c0-2 2-4 4-4z"/>'),
    pencil: SVG('<rect x="10" y="8" width="36" height="42" rx="4"/><path d="M18 20h20M18 28h20M18 36h10"/><path d="M48 40l14-18 4 3-14 18-6 3z"/>'),
    card: SVG('<rect x="6" y="12" width="60" height="34" rx="5"/><path d="M6 22h60"/><path d="M14 31h22M14 38h14"/><path d="M48 30v10M43 35h10"/>')
  };
  function drawing(name) {
    const span = el('span', undefined, 'enroll-drawing'); span.setAttribute('aria-hidden', 'true');
    span.innerHTML = DRAWINGS[name] || DRAWINGS.check; return span;
  }

  /* One compact line: Part A and Part B, then the next step. Used above the
     conversation and at the top of the plans pages. */
  function statusLine(view) {
    const line = view && view.line; if (!line) return null;
    const p = el('p', undefined, 'enroll-line'); p.setAttribute('role', 'status');
    line.parts.forEach((part, index) => {
      const item = el('span', undefined, 'enroll-part'); item.dataset.state = part.state;
      item.append(el('strong', 'Part ' + part.part + ': '), part.text + (index ? '.' : ''));
      p.append(item); if (!index) p.append(' · ');
    });
    const rest = line.text.slice(line.status.length).trim();
    if (rest) p.append(' ', el('span', rest, 'enroll-next'));
    return p;
  }

  function rows(host, list) {
    if (!(list || []).length) return;
    const dl = el('dl');
    for (const row of list) {
      const item = el('div', undefined, 'card-row'), value = el('dd');
      if (row.url) value.append(link(row.value, row.url)); else value.textContent = row.value;
      item.append(el('dt', row.label), value);
      if (row.basis) {const tag = el('span', row.basis === 'reported' ? 'You told me' : 'Estimate', 'enroll-basis'); tag.dataset.basis = row.basis; item.append(tag);}
      if (row.note) item.append(el('p', row.note, 'card-note'));
      dl.append(item);
    }
    host.append(dl);
  }
  const GUIDE_LABELS = {online_ab: 'Open the online sign-up guide', add_part_b: 'Open the Part B guide', phone: 'Open the phone guide'};

  /* Where the person is with Social Security: one question, tapped answers (approved design,
     November 13, 2026). Every word and every choice comes from the server's view; a tap sends
     the person's own answer and needs no model call. */
  function callBranch(view, actions) {
    const call = view && view.call; actions = actions || {};
    if (!call || !actions.decide || ['not_now', 'needs_info', 'dates'].includes(call.stage)) return null;
    const host = el('div', undefined, 'enroll-call'); host.dataset.stage = call.stage;
    if (call.line) host.append(el('p', call.line, 'card-text enroll-call-line'));
    if ((call.after || []).length) {const ul = el('ul', undefined, 'enroll-list'); for (const text of call.after) ul.append(el('li', text)); host.append(ul);}
    if (call.question) host.append(el('p', call.question, 'enroll-call-question'));
    const row = el('div', undefined, 'enroll-actions'), form = el('div', undefined, 'enroll-dates'); form.hidden = true;
    for (const choice of call.choices || []) {
      row.append(button(choice.label, async () => {
        if (choice.dates) {form.hidden = !form.hidden; return;}
        const saved = await actions.decide(choice.action);
        if (saved !== false && choice.guide && actions.guide) actions.guide(choice.guide, view.record && view.record.route);
      }));
    }
    if ((call.choices || []).length) host.append(row);
    if ((call.choices || []).some(choice => choice.dates)) {
      const inputs = {};
      for (const part of ['A', 'B']) {
        const label = el('label', 'Part ' + part + ' starts', 'enroll-date'), input = el('input'); input.type = 'date'; inputs[part] = input;
        label.append(input); form.append(label);
      }
      form.append(button('Done', () => {
        const starts = {}; for (const part of ['A', 'B']) if (inputs[part].value) starts[part] = inputs[part].value;
        if (Object.keys(starts).length) actions.decide({starts});
      }, 'primary-button'));
      host.append(form);
    }
    return host;
  }
  /* Cards already in the conversation keep up with what the person has since reported. */
  function live(root, view, actions) {
    if (!root || !root.querySelectorAll) return;
    for (const slot of root.querySelectorAll('.enroll-call-slot')) {
      const branch = callBranch(view, actions); slot.replaceChildren(...(branch ? [branch] : []));
      const box = slot.closest && slot.closest('.chat-card'); if (box) box.classList.toggle('enroll-folded', !!(view && view.call && view.call.stage === 'not_now'));
    }
    for (const b of root.querySelectorAll('.enroll-start')) b.setAttribute('aria-pressed', String(!!view && view.start === b.dataset.start));
  }

  /* Fills a chat card. Returns false for a card this file does not own. */
  function card(c, host, actions) {
    actions = actions || {};
    if (c.kind === 'discussion_paths') {
      const grid = el('div', undefined, 'chat-paths enroll-trade');
      for (const column of c.columns || []) {
        const box = el('article', undefined, 'chat-path');
        box.append(el('h4', column.title));
        for (const line of column.lines || []) box.append(el('p', line, 'card-text'));
        grid.append(box);
      }
      host.append(grid);
      if (actions.stage) {
        const row = el('div', undefined, 'enroll-actions');
        for (const action of c.actions || []) row.append(button(action.label, () => actions.stage(action.say)));
        host.append(row);
      }
      return true;
    }
    if (c.kind === 'next_step_offer') {
      // D183: an offer of work ends the turn as a button; it puts the person's
      // own words in the composer, and they press Send as with any answer.
      if (actions.stage) {
        const row = el('div', undefined, 'enroll-actions');
        for (const action of c.actions || []) row.append(button(action.label, () => actions.stage(action.say), 'secondary-button'));
        host.append(row);
      }
      return true;
    }
    if (c.kind === 'signup_route') {
      for (const text of c.lines || []) host.append(el('p', text, 'card-text'));
      rows(host, c.rows);
      if ((c.guides || []).length && actions.guide) {
        const row = el('div', undefined, 'enroll-actions');
        c.guides.forEach((id, index) => row.append(button(GUIDE_LABELS[id] || 'Open the guide', () => actions.guide(id, c.route), index ? 'secondary-button' : 'primary-button')));
        host.append(row);
      }
      if (actions.decide && c.route !== 'automatic') {
        const slot = el('div', undefined, 'enroll-call-slot'), branch = callBranch(actions.view, actions);
        if (branch) slot.append(branch); host.append(slot);
      }
      return true;
    }
    if (c.kind === 'trade_off' && (c.columns || []).length) {
      // Both paths side by side, from accepted sentences, then one question before narrowing.
      if (c.because) host.append(el('p', c.because, 'card-lean'));
      if (c.top) host.append(el('p', c.top, 'card-text'));
      const grid = el('div', undefined, 'chat-paths enroll-trade');
      for (const column of c.columns) {
        const box = el('article', undefined, 'chat-path'); box.dataset.path = column.id; box.append(el('h4', column.title));
        const ul = el('ul', undefined, 'enroll-list'); for (const text of column.lines || []) ul.append(el('li', text)); box.append(ul);
        const dl = el('dl');
        for (const amount of column.amounts || []) {
          const item = el('div', undefined, 'card-row'), value = el('dd', '', 'card-amount'); value.dataset.source = amount.source;
          value.textContent = 'On the tab'; item.append(el('dt', amount.label), value); dl.append(item);
        }
        box.append(dl); grid.append(box);
      }
      host.append(grid);
      if (c.note) host.append(el('p', c.note, 'card-note'));
      if (c.question && actions.decide) {
        host.append(el('p', c.question, 'enroll-call-question'));
        const row = el('div', undefined, 'enroll-actions');
        for (const choice of c.choices || []) {
          const b = button(choice.label, () => actions.decide(choice.action), 'secondary-button enroll-start');
          b.dataset.start = choice.action.start_with; b.setAttribute('aria-pressed', String(!!actions.view && actions.view.start === b.dataset.start));
          row.append(b);
        }
        host.append(row);
      }
      if (actions.amounts) actions.amounts(host);
      return true;
    }
    if (c.kind === 'plans_ready') {
      // The way into the plans, once, the moment a list is ready, whatever question is open (owner, November 13).
      if (c.button && actions.open) {
        const row = el('div', undefined, 'enroll-actions');
        row.append(button(c.button.label, () => actions.open(c.button.view), 'primary-button tab-ready'));
        host.append(row);
      }
      return true;
    }
    if (c.kind === 'coverage_now' || c.kind === 'trial_right') {
      // What the person already has: facts they reported, never a decision.
      rows(host, c.rows);
      return true;
    }
    if (c.kind === 'finish_summary') {
      rows(host, c.rows);
      if ((c.lines || []).length) {
        host.append(el('h4', 'Worth knowing'));
        for (const text of c.lines) host.append(el('p', text, 'card-text'));
      }
      if (c.change) host.append(el('p', c.change, 'card-note'));
      return true;
    }
    return false;
  }

  /* The two-path card's other choices. Each button puts the person's own
     sentence in the composer; they press Send, as with any other answer. */
  function choices(list, stage) {
    const host = el('div', undefined, 'enroll-choices');
    host.append(el('p', 'Or choose:', 'card-note'));
    const row = el('div', undefined, 'enroll-actions');
    for (const choice of list || []) row.append(button(choice.label, () => stage(choice.say)));
    host.append(row); return host;
  }

  /* The three decisions of the open path. Each button shows its answer, so
     the summary stays in view on every step. A step button is navigation. */
  function steps(view, options) {
    const path = view.dashboard.paths[options.tab];
    const nav = el('ol', undefined, 'enroll-steps'); nav.setAttribute('aria-label', path.title + ': three decisions');
    path.steps.forEach((step, index) => {
      const local = (options.local || {})[step.id] || {};
      const current = options.step === step.id;
      const li = el('li'), b = button('', () => options.onStep(step.id), 'enroll-step' + (current ? ' current' : ''));
      b.dataset.state = local.state || step.state;
      if (current) b.setAttribute('aria-current', 'step');
      b.append(el('span', String(index + 1), 'enroll-step-n'), el('span', step.title, 'enroll-step-title'),
        el('span', local.text || step.text, 'enroll-step-text'));
      li.append(b); nav.append(li);
    });
    return nav;
  }
  function board(view, options) {
    const host = el('div', undefined, 'enroll-board');
    const line = statusLine(view); if (line) host.append(line);
    host.append(steps(view, options)); return host;
  }

  /* How a step ends: done, keep what I have, not needed or decide later. */
  function decisions(step, current, run, lead) {
    const host = el('div', undefined, 'enroll-decide');
    host.append(el('span', lead || 'This step:', 'enroll-decide-lead'));
    for (const [value, label] of step.choices || []) {
      const b = button(label, () => run(value), 'enroll-decision');
      b.setAttribute('aria-pressed', String(current === value)); host.append(b);
    }
    return host;
  }

  /* Step 1 of either path: what is in place, the dates, how to sign up. */
  function partsPanel(view, actions) {
    actions = actions || {};
    const host = el('section', undefined, 'enroll-panel');
    const h = el('h1', 'Parts A and B', 'plans-title'); h.tabIndex = -1; host.append(h);
    if (view.line) host.append(el('p', view.line.text, 'enroll-lead'));
    if ((view.dates || []).length) {host.append(el('h2', 'Your dates')); rows(host, view.dates);}
    // The route for this person, or, before anything is known, how to sign up in general with every guide.
    const how = view.route || view.signup; actions = {...actions, view};
    if (how) {
      const box = el('section', undefined, 'chat-card'); box.dataset.kind = 'signup_route';
      box.append(el('h3', how.title)); card(how, box, actions);
      const links = sources(how.sources); if (links) box.append(links);
      host.append(box);
    }
    // The sign-up card above already carries the question; it stands alone only when there is no card.
    const branch = how && actions.decide && how.route !== 'automatic' ? null : callBranch(view, actions);
    if (branch) host.append(branch);
    else if (actions.stage && !actions.decide) {
      host.append(el('h2', 'Tell Daylight what happened'));
      host.append(el('p', 'Pick one, add any date you were given, and press Send.', 'card-note'));
      const row = el('div', undefined, 'enroll-actions');
      for (const [label, say] of [['I applied', 'I applied on '], ['I have my start dates', 'Part A starts  and Part B starts '],
        ['They asked for more information', 'Social Security asked for more information.']]) row.append(button(label, () => actions.stage(say)));
      host.append(row);
    }
    return host;
  }

  function sources(list) {
    const seen = new Map();
    for (const item of list || []) if (item && /^https:\/\//.test(item.url || '') && !seen.has(item.url)) seen.set(item.url, item.label || item.url);
    if (!seen.size) return null;
    const details = el('details', undefined, 'sources'); details.append(el('summary', 'Sources'));
    for (const [url, label] of seen) details.append(link(label, url));
    return details;
  }

  /* A sign-up guide: what to have ready, what is asked in order, what to say
     on the phone, what happens after. Shows when it was last checked and
     links to the official page. */
  function guide(content, id, options) {
    options = options || {};
    const g = (content.guides || []).find(item => item.id === id); if (!g) return null;
    const used = [];
    const text = item => {used.push(...(item.sources || [])); return (item.variants || {})[options.route] || item.text;};
    const host = el('article', undefined, 'enroll-guide'); host.dataset.guide = id;
    const h = el('h1', g.title, 'plans-title'); h.tabIndex = -1; host.append(h);
    const official = content.sources[g.official], meta = el('p', undefined, 'enroll-meta');
    meta.append('Last checked ' + longDate(content.last_checked) + ' · ', link('Official page: ' + official.label, official.url));
    host.append(meta);
    for (const item of g.lead || []) host.append(el('p', text(item), 'enroll-lead'));
    const notes = id === 'phone' ? options.notes : null;
    if (notes) {
      // "For your call": the person's own lines, built by the server from what they reported.
      const box = el('section', undefined, 'enroll-section enroll-notes'); box.append(el('h2', notes.title));
      for (const [label, lines, tag] of [['Say', notes.say, 'li'], ['Ask', notes.ask, 'li']]) {
        if (!(lines || []).length) continue;
        box.append(el('h3', label)); const ul = el('ul', undefined, 'enroll-list'); for (const line of lines) ul.append(el(tag, line)); box.append(ul);
      }
      if ((notes.know || []).length) {box.append(el('h3', 'Good to know before you call')); for (const line of notes.know) box.append(el('p', line, 'card-text'));}
      const links = sources(notes.sources); if (links) box.append(links);
      host.append(box);
    }
    const list = (title, items, tag) => {
      const section = el('section', undefined, 'enroll-section'); section.append(el('h2', title));
      const ul = el(tag || 'ul', undefined, 'enroll-list'); for (const item of items) ul.append(el('li', text(item)));
      section.append(ul); host.append(section);
    };
    list('What to have ready', g.ready || []);
    const steps = el('section', undefined, 'enroll-section'); steps.append(el('h2', g.steps_title || 'Steps'));
    const ol = el('ol', undefined, 'enroll-guide-steps');
    (g.steps || []).forEach((step, index) => {
      const li = el('li'), words = el('div', undefined, 'enroll-step-words');
      words.append(el('h3', (index + 1) + '. ' + step.title), el('p', text(step)));
      if (options.ask) words.append(button('Ask Daylight what this means', () => options.ask('On the “' + g.title + '” guide, what does step ' + (index + 1) + ' (“' + step.title + '”) mean? '), 'text-button'));
      li.append(drawing(step.drawing), words); ol.append(li);
    });
    steps.append(ol); host.append(steps);
    if ((g.write_down || []).length) list('What to write down', g.write_down);
    list('What happens after', (g.after || []).map(key => content.after[key]).filter(Boolean));
    host.append(el('p', content.statements.never_ids.text, 'enroll-safe'));
    const links = sources([official, ...used.map(key => content.sources[key])]); if (links) host.append(links);
    return host;
  }

  let cached = null;
  function load() {
    cached = cached || root.fetch('/api/enrollment/content', {credentials: 'same-origin'})
      .then(response => {if (!response.ok) throw new Error('unavailable'); return response.json();})
      .catch(error => {cached = null; throw error;});
    return cached;
  }

  const api = {statusLine, card, choices, steps, board, decisions, partsPanel, guide, sources, drawing, load, longDate, GUIDE_LABELS, callBranch, live};
  root.DaylightEnrollment = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
