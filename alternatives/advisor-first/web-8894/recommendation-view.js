/* D147: evaluation-only tiered sorting, shown only when the unified local demo
   (:8895) turns it on. The backend groups, ranks and checks every plan; this
   view renders those results and computes nothing itself. Pilot participants
   never receive recommendation inputs, so on :8894 it stays inert. */
(() => {
  'use strict';
  const MARK = {met: ['✓', 'Meets'], not_met: ['✗', 'Does not meet'], unknown: ['?', 'Not checked']};
  const KIND_ORDER = {eligibility: 0, need: 1, priority: 2, preference: 3};
  const listeners = new Set();
  let request = null, key = null, result = null, pending = false, error = '';
  const el = (tag, text, cls) => {const n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n;};

  function configure(fn) {request = fn;}
  function onChange(fn) {listeners.add(fn);}
  function notify() {for (const fn of listeners) {try {fn();} catch (e) {console.error('[Daylight sorting]', e);}}}
  // Inputs are the person's reported details, as the conversation returns them.
  function update(inputs) {
    if (!request || !inputs) {
      if (key !== null) {key = null; result = null; error = ''; pending = false; notify();}
      return;
    }
    const next = JSON.stringify(inputs);
    if (next === key) return;
    key = next; result = null; error = ''; void load(next, inputs);
  }
  async function load(current, inputs) {
    pending = true;
    try {
      const body = inputs.continuation ? {inputs:inputs.inputs,continuation:inputs.continuation} : {inputs};
      const value = await request('/api/recommendation', body);
      if (current === key) result = value;
    } catch (e) {
      if (current === key) error = e.message || 'Daylight’s sorting is temporarily unavailable.';
    } finally {
      if (current === key) {pending = false; notify();}
    }
  }
  const active = () => key !== null;
  const tab = kind => result?.[kind]?.state === 'ready' ? result[kind] : null;
  const plan = (kind, id) => tab(kind)?.plans?.[id] || null;

  function checks(kind, id) {
    const p = plan(kind, id);
    if (!p || !p.checks.length) return null;
    const list = el('ul', undefined, 'rec-checks');
    list.setAttribute('aria-label', 'How this fits what you told Daylight');
    for (const c of [...p.checks].sort((a, b) => KIND_ORDER[a.kind] - KIND_ORDER[b.kind])) {
      const [mark, word] = MARK[c.state] || MARK.unknown;
      const item = el('li', undefined, 'rec-check rec-' + c.state), sign = el('span', mark, 'rec-mark');
      sign.setAttribute('aria-hidden', 'true');
      const words = el('span', undefined, 'rec-words');
      words.append(el('span', word + ': ', 'sr-only'), el('strong', c.label));
      if (c.kind === 'priority') words.append(el('span', 'Your priority', 'rec-tag'));
      words.append(el('span', c.note, 'rec-note'));
      item.append(sign, words); list.append(item);
    }
    return list;
  }
  // Adds the top-match line and the checks to a plan card, before its actions.
  function decorate(kind, id, card, before = null, topWords = 'Top match for what you told Daylight') {
    const p = plan(kind, id);
    if (!p) return;
    const box = el('div', undefined, 'rec-fit');
    if (p.recommended) {card.classList.add('rec-recommended'); box.append(el('p', topWords, 'rec-badge'));}
    const list = checks(kind, id);
    if (list) box.append(list);
    if (!box.children.length) return;
    if (before && before.parentNode === card) card.insertBefore(box, before); else card.append(box);
  }
  // Rows in the backend's group order; rows the backend did not sort go last.
  function arrange(kind, rows, idOf = r => r.id) {
    const t = tab(kind);
    if (!t) return null;
    const left = new Map(rows.map(r => [idOf(r), r])), out = [];
    for (const g of t.groups) {
      const members = g.ids.filter(i => left.has(i)).map(i => left.get(i));
      for (const i of g.ids) left.delete(i);
      if (members.length) out.push({id: g.id, label: g.label, rows: members});
    }
    if (left.size) out.push({id: 'unsorted', label: 'Not sorted', rows: [...left.values()]});
    return out;
  }
  function method() {
    const d = el('details', undefined, 'rec-method');
    d.append(el('summary', 'How Daylight sorts these'));
    const steps = el('ol');
    for (const text of [
      'Who can join. A plan you may not qualify for, or with a joining rule you have not confirmed, is set aside and never suggested.',
      'What you need. A plan missing something you need, such as drug coverage, is set aside.',
      'Your priorities. A plan that misses something you said matters most moves to a second group.',
      'Then, inside each group, plans that meet more of your priorities come first, then more of your other preferences, and the cost order shown breaks ties.'])
      steps.append(el('li', text));
    d.append(steps,
      el('p', '✓ meets it. ✗ does not. ? means Daylight has not checked it yet; it never counts against a plan.'),
      el('p', 'Plans missing an amount stay in their group, listed after the others; they are not treated as worse and are not suggested.'),
      el('p', 'Commissions and any payment to Daylight are not part of this sorting.'),
      el('p', `Method ${result?.method || ''}.`, 'rec-fine'));
    d.open = true;
    return d;
  }
  // PG-04: only inputs that were actually checked are listed as used. The
  // backend marks each preference; this view never relabels a reason.
  function used(kind) {
    const prefs = result?.[kind]?.preferences || result?.preferences || [];
    if (!prefs.length) return ['You have not told Daylight what matters most yet, so plans are grouped by what you need and ordered by cost.'];
    const name = p => p.label + (p.priority ? ' (your priority)' : '');
    const checked = prefs.filter(p => p.checked !== false), open = prefs.filter(p => p.checked === false);
    const lines = [];
    if (checked.length) lines.push('What you told Daylight: ' + checked.map(name).join(', ') + '.');
    if (open.length) lines.push('Not checked: ' + open.map(name).join(', ') + '.');
    return lines;
  }
  // One summary block per page: what was suggested, or why nothing was.
  // CN-04: one small link at the bottom of the plan list opens the whole
  // explanation: the top match or why there is none, what was checked, the
  // order and the method. Group headers and each plan's checks stay on the plans.
  function summary(kind, names = {}, hideNote = null) {
    const box = details(kind, names, hideNote);
    if (!box) return null;
    const link = el('button', 'How Daylight sorted these', 'btn-quiet rec-link'); link.type = 'button';
    link.addEventListener('click', () => {
      const dialog = el('dialog', undefined, 'plan-sheet rec-dialog');
      const close = el('button', 'Close', 'btn-quiet sheet-close'); close.type = 'button';
      close.addEventListener('click', () => dialog.close());
      dialog.append(close, details(kind, names, hideNote) || box);
      dialog.addEventListener('close', () => {dialog.remove(); if (link.isConnected) link.focus();}, {once: true});
      document.body.append(dialog); dialog.showModal(); close.focus();
    });
    const wrap = el('p', undefined, 'rec-link-row'); wrap.append(link);
    return wrap;
  }
  function details(kind, names = {}, hideNote = null) {
    if (!active()) return null;
    const box = el('section', undefined, 'rec-summary'), head = el('div', undefined, 'rec-head');
    const title = el('h2', 'How Daylight sorted these'); title.id = 'rec-title-' + kind;
    box.setAttribute('aria-labelledby', title.id);
    head.append(title);
    box.append(head);
    if (pending) {box.append(el('p', 'Sorting for what you told Daylight…')); return box;}
    if (error) {box.append(el('p', error)); return box;}
    const t = result?.[kind];
    if (!t) return null;
    if (t.state !== 'ready') {box.append(el('p', t.message)); return box;}
    const top = t.recommended_ids.map(i => names[i] || null).filter(Boolean);
    if (t.recommended_ids.length) box.append(el('p', top.length ? 'Top match: ' + top.join('; ') + '.'
      : `${t.recommended_ids.length === 1 ? 'One top match is' : t.recommended_ids.length + ' top matches are'} marked below.`, 'rec-lead'));
    else if (t.no_pick_reason) box.append(el('p', t.no_pick_reason, 'rec-lead'));
    for (const line of used(kind)) box.append(el('p', line));
    if (t.sort_note) box.append(el('p', t.sort_note));
    for (const note of t.notes || []) if (!(typeof hideNote === 'function' && hideNote(note))) box.append(el('p', note, 'rec-fine'));
    box.append(method());
    return box;
  }
  window.DaylightRecommend = Object.freeze({configure, onChange, update, active, tab, plan, checks, decorate, arrange, summary, explain: details,
    status: () => ({active: active(), pending, error, ready: !!result})});
})();
