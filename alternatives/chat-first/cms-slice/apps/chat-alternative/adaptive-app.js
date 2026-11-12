/* D79 October 28: one directed conversation and one deliberate Send action. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  };
  const button = (text, fn, primary = false) => {
    const node = el('button', text, primary ? 'primary-button' : 'secondary-button');
    node.type = 'button'; node.onclick = fn; return node;
  };
  const sourceLink = (text, url) => {
    const a = el('a', text);
    try { const u = new URL(url); if (u.protocol !== 'https:') return el('span', text); a.href = u.href; }
    catch { return el('span', text); }
    a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
  };
  let session, state, service, config, samples, content;
  let active = false, busy = false, consented = false, composing = false, version = 0, rv = 0, loaded = false;
  let messages = [], draft = '', selected = [], lastQuestion = '', pendingId = null, pendingUpdates = [], sendControl;
  let saveState = 'Visit only', saveError = '', saveQueue = Promise.resolve(), inflight = null, lastRequest = null, recognition = null;
  let renderedMessages = 0, renderedFirstId = null, serial = 0;
  const controlDrafts = new Map();
  const revealed = new Set();
  const metrics = { prompts: 0, atomicRequests: 0, userTurns: 0, assistantTurns: 0, llmCalls: 0, processingMs: 0, startedAt: null };
  const detailLabels = { choice: 'Your report', month: 'Part B start', jobEnd: 'Job end', coverageEnd: 'Insurance end', start: 'Advantage episode start', priorMedigap: 'Medigap left to join that Advantage plan', name: 'Medicine', strength: 'Strength', form: 'Form', practice: 'Doctor or practice', city: 'Office location', quantity: 'Quantity and units', daysSupply: 'Days supply', pharmacy: 'Pharmacy', channel: 'Fill channel', location: 'Routine-care location', gap: 'Drug-coverage gap', event: 'Coverage event or notice', eventDate: 'Event date', amount: 'Monthly amount or range', includes: 'What the amount includes', qualification: 'Reported program confirmation', year: 'Coverage year', homeStatus: 'Home context', ageBand: 'Reported age range' };
  function fieldTitle(key) {
    return ({ 'subject.role': 'Who this is for', 'coverage.requestedStartMonth': 'Intended coverage start', 'comparison.scope.county': 'County', 'needs.providers': 'Doctors and hospitals', 'needs.medications': 'Prescriptions', 'needs.medicationDetails': 'Prescription details', 'needs.pharmacies': 'Pharmacies', 'intent.goalDetail': 'What you want help with', 'needs.priorityOther': 'Other priorities' }[key]) || TenGuide.Q.find(q => q.field === key)?.question || key.replaceAll('.', ' ');
  }
  function readable(value) {
    if (Array.isArray(value)) return value.map(readable).join(', ');
    if (value && typeof value === 'object') return value.name ? [value.name, value.state].filter(Boolean).join(', ') : Object.entries(value).filter(([k]) => !['entity', 'choice'].includes(k)).map(([k, v]) => (detailLabels[k] || k) + ': ' + readable(v)).join(' · ');
    const labels = [['learn', 'Understand Medicare and my options'], ['self', 'Me'], ['someone', 'Someone I’m helping'], ['elsewhere_us', 'Elsewhere in the U.S.'], ...TenGuide.Q.flatMap(q => q.options || [])];
    return labels.find(([id]) => id === value)?.[1] || String(value);
  }
  async function api(path, body, signal) {
    const response = await fetch(path, { method: body ? 'POST' : 'GET', credentials: 'same-origin', signal,
      headers: { 'Content-Type': 'application/json', ...(session ? { 'X-Daylight-CSRF': session.csrf } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}) });
    const data = await response.json();
    if (!response.ok) { const e = Error(data.error || 'The request could not finish.'); e.code = response.status; throw e; }
    return data;
  }
  function say(role, text, facts = []) {
    if (!text && !facts.length) return;
    messages.push({ id: 'message-' + (++serial), role, text, facts });
    if (role === 'assistant') metrics.assistantTurns++;
  }
  function status(text) { if ($('chat-status')) $('chat-status').textContent = text; }
  function current() { return state?.assessment.nextQuestion; }
  function followup() { return state?.assessment.journey.nextStep; }
  function announce(text) { $('sr-live').textContent = text; }
  function updateBusy() {
    for (const n of $('stage').querySelectorAll('button,input,select,textarea')) if (!n.dataset.keepActive && n.id !== 'chat-input') n.disabled = busy;
    if (sendControl) sendControl.disabled = busy || (!draft.trim() && !selected.length);
    if ($('chat-cancel')) $('chat-cancel').hidden = !busy;
  }
  function utilities() {
    const host = $('guide-utilities');
    host.replaceChildren(button('Your guide & privacy', privacy));
    if (session?.hasSaved) host.append(button('Resume saved information', resume));
  }
  function openDialog(title) {
    const d = el('dialog', undefined, 'adaptive-dialog'), h = el('h2', title);
    h.id = 'adaptive-dialog-title-' + (++serial); d.setAttribute('aria-labelledby', h.id); d.append(h); document.body.append(d);
    d.addEventListener('close', () => d.remove(), { once: true }); return d;
  }
  function consent() {
    if (consented || config.mockAI) return Promise.resolve(true);
    return new Promise(resolve => {
      const d = openDialog('Send this message to AI?');
      d.append(el('p', 'Your submitted message, limited task and coverage context, and which details are already reported go to OpenAI. Previous provider, prescription, pharmacy and date values, and the raw conversation are not automatically attached. Saving is a separate choice. Do not enter ID numbers.'),
        button('Keep it here', () => { d.close(); resolve(false); }),
        button('Allow and send', () => { consented = true; d.close(); resolve(true); }, true));
      d.addEventListener('cancel', () => resolve(false), { once: true }); d.showModal();
    });
  }
  function paragraph(text, reveal) {
    const p = el('p');
    if (!reveal || matchMedia('(prefers-reduced-motion: reduce)').matches) { p.textContent = text; return p; }
    p.append(el('span', text, 'sr-only'));
    const visible = el('span', undefined, 'assistant-reveal'); visible.setAttribute('aria-hidden', 'true');
    const words = text.match(/\S+\s*|\s+/g) || [];
    words.forEach((word, i) => { const span = el('span', word, 'reveal-word'); span.style.setProperty('--word-delay', Math.min(i * 18, 650) + 'ms'); visible.append(span); });
    p.append(visible); return p;
  }
  function sources(host, facts) {
    const items = facts.flatMap(f => [...(f.source ? [{ url: f.source, label: new URL(f.source).hostname.replace('www.', '') }] : []), ...(f.sources || [])]);
    if (!items.length) return;
    const details = el('details', undefined, 'chat-sources'); details.append(el('summary', 'Sources'));
    const seen = new Set();
    for (const source of items) if (!seen.has(source.url)) { seen.add(source.url); details.append(sourceLink(source.label || source.title || 'Official source', source.url)); }
    host.append(details);
  }
  function historyRender() {
    const host = $('chat-thread'); if (!host) return;
    if (renderedFirstId !== messages[0]?.id || renderedMessages > messages.length) { host.replaceChildren(); renderedMessages = 0; }
    renderedFirstId = messages[0]?.id;
    for (const m of messages.slice(renderedMessages)) {
      const row = el('article', undefined, 'chat-message ' + (m.role === 'user' ? 'chat-user' : 'chat-daylight'));
      row.id = m.id; row.setAttribute('aria-label', m.role === 'user' ? 'You' : 'Daylight');
      const reveal = m.role === 'assistant' && !revealed.has(m.id);
      if (m.text) row.append(paragraph(m.text, reveal));
      for (const fact of m.facts || []) {
        row.append(el('h2', fact.title));
        const brief = state.guide.fields['knowledge.general']?.value === 'comfortable' && fact.summary;
        row.append(paragraph(brief ? fact.summary : fact.text, reveal));
        if (brief) { const more = el('details'); more.append(el('summary', 'More detail'), el('p', fact.text)); row.append(more); }
      }
      sources(row, m.facts || []); host.append(row); revealed.add(m.id);
    }
    renderedMessages = messages.length;
  }
  function dateHint(value, knownYear) {
    const names = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    const short = value.match(/^(0?[1-9]|1[0-2])[/.-]((?:19|20)?\d{2})$/) || value.match(/^(0[1-9]|1[0-2])(\d{2})$/);
    if (short) return names[Number(short[1]) - 1] + ' ' + (short[2].length === 2 ? '20' : '') + short[2];
    const iso=value.match(/^((?:19|20)\d{2})-(0[1-9]|1[0-2])(?:-(\d{2}))?$/);
    if(iso)return names[Number(iso[2])-1]+' '+(iso[3]?Number(iso[3])+', ':'')+iso[1];
    if (knownYear && names.some(n => n.toLowerCase() === value.toLowerCase())) return value + ' ' + knownYear;
    return '';
  }
  function toggle(value, multi) {
    const exclusive = ['__unknown','__defer','none','no','unknown','local','already','declined'];
    if (multi && !exclusive.includes(value)) { selected = selected.filter(v => !exclusive.includes(v)); selected = selected.includes(value) ? selected.filter(v => v !== value) : [...selected, value]; }
    else selected = selected.length === 1 && selected[0] === value ? [] : [value];
    for (const node of $('chat-suggestions').querySelectorAll('[data-choice]')) node.setAttribute('aria-pressed', String(selected.includes(node.dataset.choice)));
    renderSelection(); updateBusy();
  }
  function options() {
    if (pendingId) return [['__confirm','Use these details'], ['__reject','Keep my previous information']];
    if (state.assessment.journey.samplesVisible) return [];
    const q = current();
    const fieldChoices = q?.fields.length === 1 && q.fields[0].type === 'select' ? q.fields[0].options.filter(([v]) => !['other','unknown'].includes(v)).map(([v,l]) => ['__field:' + q.fields[0].key + ':' + v,l]) : [];
    return q ? [...q.choices.filter(([v])=>v!=='unknown'), ...fieldChoices, ['__unknown','I don’t know'], ['__defer','Check later']] : (followup()?.choices || []).map(c => [c.value, c.label]);
  }
  function renderSelection() {
    // A single persistent Send moves with the input being submitted.
    const home = $('chat-input-row'), host = $('chat-selection');
    if (home && sendControl) home.append(sendControl);
    if (host) {
      host.replaceChildren();
      if (selected.length) {
        if (!draft.trim()) host.append(sendControl);
        host.append(button('Clear selection', () => { selected = []; renderControls(); }));
      }
      host.hidden = !selected.length;
      if (selected.length && !draft.trim()) {
        const reading = $('chat-reading'), rect = sendControl.getBoundingClientRect(), bounds = reading.getBoundingClientRect();
        if (rect.bottom > bounds.bottom - 12) reading.scrollTop += rect.bottom - bounds.bottom + 12;
        else if (rect.top < bounds.top + 12) reading.scrollTop -= bounds.top + 12 - rect.top;
      }
    }
    const q = current(), samplesVisible = state.assessment.journey.samplesVisible;
    const label = samplesVisible ? 'Ask about these samples or your next steps' : q?.fields.length ? 'Type your answer or ask a question here' : 'Type an answer or ask a question';
    if ($('chat-entry-label')) $('chat-entry-label').textContent = label;
    const input = $('chat-input');
    if (input) {
      input.placeholder = samplesVisible ? 'Ask about a plan term or what to check next…' : q?.id === 'T03' ? 'For example, 34102' : q?.id === 'T06' ? 'Name the doctors or hospitals you want to keep…' : q?.id === 'T07' ? 'List your prescriptions, or choose none above…' : q?.fields.some(f => ['month','jobEnd','coverageEnd','start','year'].includes(f.key)) ? 'For example, December 2026 or 12/26…' : 'Type here, or choose an answer above…';
      input.inputMode = q?.id === 'T03' ? 'numeric' : 'text';
      const preview = $('chat-date-preview');
      const normalized = q?.fields.length === 1 && ['month','jobEnd','coverageEnd','start','year'].includes(q.fields[0].key) ? dateHint(draft.trim(), q.knownYear) : '';
      if (preview) preview.textContent = normalized ? 'Date entered: ' + normalized : '';
    }
  }
  function renderControls() {
    const host = $('chat-suggestions'); if (!host) return;
    if (sendControl) $('chat-input-row').append(sendControl);
    host.replaceChildren(); const q = current(), next = followup();
    if (state.assessment.journey.samplesVisible) {
      const heading = el('h2', 'Sample plan options'); host.append(heading, el('p', 'These five records show how plan options can be presented. They are unvalidated 2027 Collier County, Florida samples, not personal recommendations or a complete market.'));
      const wanted = state.guide.fields['coverage.requestedStartMonth']?.value || state.record.facts.RC03?.value.year;
      if (wanted) host.append(el('p', 'Your requested timing: ' + wanted + '. These sample records retain their own year and location.'));
      const details = el('details', undefined, 'profile-preview'); details.append(el('summary', 'Your information so far'), profileSummary()); host.append(details);
      appendPlans(host);
      host.append(el('p', 'You can review or change your information below, ask about a plan term, or return to your current question.'), button('Return to my conversation', () => turn({ type: 'next', step: 'resume' })));
      renderSelection(); updateBusy(); return;
    }
    if (pendingId) {
      host.append(el('h2', 'Have I understood these details correctly?'));
      for (const u of pendingUpdates) host.append(el('p', Object.entries(u.fields).map(([k, v]) => (detailLabels[k] || 'Reported detail') + ': ' + readable(v)).join(' · ')));
    } else if (q) {
      host.append(el('h2', q.question)); if (q.why) host.append(el('p', q.why, 'chat-why'));
    } else {
      const summary = state.assessment.journey.summary; if (summary) host.append(el('p', summary));
      if (state.assessment.unresolvedReportedInputs.length) {
        const details = el('details', undefined, 'open-details'); details.append(el('summary', 'Details still open'));
        const list = el('ul'); for (const item of state.assessment.unresolvedReportedInputs) list.append(el('li', item.label + ' — ' + (item.state === 'deferred' ? 'for later' : 'unknown')));
        details.append(list); host.append(details);
      }
      if (next) host.append(el('h2', next.question));
    }
    const row = el('div', undefined, 'chat-option-row'); row.setAttribute('role', 'group'); row.setAttribute('aria-label', pendingId ? 'Check the interpretation' : q?.question || next?.question || 'Next step');
    for (const [value, label] of options()) {
      const b = button(label, () => toggle(value, !!q?.multi)); b.dataset.choice = value;
      b.setAttribute('aria-pressed', String(selected.includes(value))); row.append(b);
    }
    host.append(row);
    const selection = el('div', undefined, 'chat-selection'); selection.id = 'chat-selection'; selection.hidden = true; host.append(selection);
    if (q && !pendingId) {
      if (q.fields.length) {
        const hint = q.fields.length === 1 ? 'Reply in the message box below.' : 'Use the message box below. You can include: ' + q.fields.map(f => f.label.toLowerCase()).join('; ') + '. Share what you know; the rest can stay unknown.';
        host.append(el('p', hint, 'chat-answer-hint'));
      }
      if (['T05','RC04','RC07'].includes(q.id)) {
        const help = el('div', undefined, 'adaptive-help-actions');
        help.append(button('What’s the difference?', () => turn({ type: 'help' })), button('How can I tell?', helpIdentify)); host.append(help);
      }
    }
    renderSelection(); updateBusy();
  }
  function profileSummary() {
    const list = el('dl', undefined, 'chat-profile-summary');
    const keys = ['intent.goal','subject.role','coverage.requestedStartMonth','coverage.current','comparison.scope.county','needs.providers','needs.medications'];
    for (const key of keys) { const f = state.guide.fields[key]; if (!f || ['unknown','skipped','stale'].includes(f.status)) continue; list.append(el('dt', fieldTitle(key)), el('dd', readable(f.value))); }
    if (!list.childElementCount) list.append(el('p', 'You can explore the samples without providing personal details.'));
    return list;
  }
  function appendPlans(host) {
    for (const p of samples.plans) {
      const row = el('section', undefined, 'chat-plan-record'); row.append(el('h3', p.name), el('p', p.id + ' · ' + p.year + ' · ' + p.plan_type), el('p', 'Premium not validated · provider fit unknown · drug fit unknown'));
      sources(row, [{ source: p.source.url }]); host.append(row);
    }
  }
  function helpIdentify() {
    const from = messages.length; say('user', 'How can I tell?'); metrics.userTurns++;
    say('assistant', 'You can check your coverage documents or ask the plan or benefits office how the coverage works. If you are still unsure, leave the answer unknown. Please keep Medicare and member ID numbers out of the chat.');
    render({ from, anchor: 'assistant' });
  }
  function progress() {
    const host = $('chat-progress'); host.replaceChildren(); const j = state.assessment.journey;
    const list = el('ol', undefined, 'adaptive-phases');
    j.labels.forEach((label, i) => { const li = el('li', label); if (i === j.phase) li.setAttribute('aria-current', 'step'); list.append(li); });
    const bar = el('progress'); bar.max = 4; bar.value = j.phase + 1; bar.setAttribute('aria-label', 'Conversation progress: ' + j.labels[j.phase]); bar.title = j.meaning;
    host.append(list, bar);
    if ($('review-information')) $('review-information').textContent = 'Review information' + (j.reportedGroups ? ' (' + j.reportedGroups + ')' : '');
    if ($('chat-save-state')) $('chat-save-state').textContent = saveError || saveState;
  }
  function buildShell() {
    if ($('chat-workspace')) return;
    $('stage').replaceChildren(); renderedMessages = 0; renderedFirstId = null;
    const workspace = el('div', undefined, 'chat-workspace'); workspace.id = 'chat-workspace';
    const p = el('nav', undefined, 'chat-progress'); p.id = 'chat-progress'; p.setAttribute('aria-label', 'Your progress');
    const reading = el('div', undefined, 'chat-reading'); reading.id = 'chat-reading';
    const thread = el('div'); thread.id = 'chat-thread'; thread.setAttribute('role', 'log'); thread.setAttribute('aria-label', 'Conversation'); thread.setAttribute('aria-live', 'polite');
    const suggestions = el('section', undefined, 'chat-suggestions adaptive-suggestions'); suggestions.id = 'chat-suggestions'; suggestions.setAttribute('aria-label', 'Current question'); reading.append(thread, suggestions);
    const form = el('form', undefined, 'chat-composer'); form.id = 'chat-form';
    const label = el('label', 'Type an answer or ask a question', 'chat-entry-label'); label.id = 'chat-entry-label'; label.htmlFor = 'chat-input';
    const row = el('div', undefined, 'chat-input-row'); row.id = 'chat-input-row'; const input = el('textarea'); input.id = 'chat-input'; input.rows = 2; input.maxLength = 1200; input.placeholder = 'Type here, or choose an answer above…';
    input.value = draft; input.oninput = () => { draft = input.value; renderSelection(); updateBusy(); };
    input.addEventListener('compositionstart', () => composing = true); input.addEventListener('compositionend', () => composing = false);
    input.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey && !composing && !e.isComposing) { e.preventDefault(); void submit(); } };
    sendControl = button('Send', submit, true); sendControl.id = 'chat-send'; row.append(input, sendControl);
    const preview = el('p', undefined, 'chat-date-preview'); preview.id = 'chat-date-preview'; input.setAttribute('aria-describedby', preview.id); form.append(label, row, preview);
    form.onsubmit = e => { e.preventDefault(); void submit(); };
    const secondary = el('div', undefined, 'chat-composer-tools'); secondary.append(button('Voice input', voice));
    const cancel = button('Cancel waiting', () => { inflight?.abort(); status('Stopped waiting. Your answer stays here. An AI request already sent may still use its reserved budget.'); });
    cancel.id = 'chat-cancel'; cancel.dataset.keepActive = 'true'; cancel.hidden = true;
    const save = el('span', undefined, 'chat-small'); save.id = 'chat-save-state'; secondary.append(cancel, save); form.append(secondary);
    const s = el('p', undefined, 'chat-status'); s.id = 'chat-status'; s.setAttribute('role', 'status'); form.append(s);
    const tools = el('nav', undefined, 'chat-tools'); tools.setAttribute('aria-label', 'Conversation controls');
    const reviewButton = button('Review information', review); reviewButton.id = 'review-information'; tools.append(button('Back', back), reviewButton, button('Browse sample plans', plans), button('Your information & privacy', privacy));
    if (config.mockAI) form.append(el('p', 'Synthetic fixture · AI replies are mocked.', 'chat-small'));
    workspace.append(p, reading, form, tools); $('stage').append(workspace);
  }
  function render({ from = null, anchor = 'user' } = {}) {
    active = true; document.body.classList.add('chat-mode'); $('landing').hidden = true; $('stage').hidden = false; $('journey-map').hidden = true;
    buildShell();
    if($('chat-input').value!==draft)$('chat-input').value=draft;
    historyRender(); renderControls(); progress(); utilities();
    if (from !== null) {
      const additions = messages.slice(from), target = additions.find(m => m.role === anchor) || additions[0];
      const reading = $('chat-reading'), node = target && $(target.id);
      if (node) { const rect = node.getBoundingClientRect(); const extra = anchor === 'user' ? Math.max(0, rect.height - reading.clientHeight * .42) : 0; reading.scrollTop += rect.top - reading.getBoundingClientRect().top - 18 + extra; }
      else $('chat-suggestions').scrollIntoView({ block: 'nearest' });
    }
  }
  async function begin() {
    if (!state || busy) return;
    if (!metrics.startedAt) metrics.startedAt = Date.now(); render();
    if (!messages.length) await turn({ type: 'start' });
    $('stage').focus({ preventScroll: true });
  }
  function choiceFields(q) {
    const fields = {}, values = selected.filter(v => !v.startsWith('__'));
    if (values.length) fields.choice = values.join(',');
    for (const value of selected.filter(v => v.startsWith('__field:'))) {
      const [, key, option] = value.split(':'); fields[key] = option;
    }
    return fields;
  }
  async function submit() {
    if (busy || composing) return;
    const q = current(), next = followup();
    const label = options().filter(([v]) => selected.includes(v)).map(([, l]) => l).join(', ');
    if (draft.trim()) {
      const pieces = [label];
      if (q) for (const [key, value] of Object.entries(choiceFields(q)).filter(([key]) => key !== 'choice')) pieces.push((q.fields.find(f => f.key === key)?.label || key) + ': ' + value);
      pieces.push(draft.trim()); const text = pieces.filter(Boolean).join('\n');
      if (text.length > 1200) { status('This combined answer is over 1,200 characters. Shorten it or send the details in separate messages. Everything you entered stays here.'); return; }
      await turn({ type: 'message', message: text }, draft.trim()); return;
    }
    if (!selected.length) { status('Choose an answer above or type below, then press Send.'); return; }
    if (pendingId) { await turn({ type: selected[0] === '__confirm' ? 'confirm' : 'reject' }); return; }
    if (q && !state.assessment.journey.samplesVisible) {
      if (selected[0] === '__unknown' || selected[0] === '__defer') {
        await turn({ type: selected[0] === '__unknown' ? 'unknown' : 'defer', id: q.id }); return;
      }
      const fields = choiceFields(q);
      if (q.choices.length && !fields.choice && !(['T06','T07'].includes(q.id) && fields.text) && !(q.id === 'T04' && fields.month)) { status('Choose an answer or type what you mean below.'); return; }
      await turn({ type: 'choice', id: q.id, entity: q.entity, fields }); return;
    }
    const picked = next?.choices.find(c => c.value === selected[0]); if (picked) await turn({ type: 'next', step: picked.value });
  }
  async function turn(action, draftSubmitted = null) {
    if (busy) return;
    const previousQuestion = current(), previousNext = followup(), before = state, from = messages.length;
    const controller = new AbortController(); inflight = controller;
    const snapshot = { guide: state.guide, record: state.record, action, aiConsent: consented || config.mockAI, pendingId };
    const signature = JSON.stringify(snapshot), requestId = lastRequest?.signature === signature ? lastRequest.id : crypto.randomUUID();
    lastRequest = { signature, id: requestId }; busy = true; updateBusy(); status(action.type === 'message' ? 'Daylight is reading your message…' : '');
    try {
      const result = await api('/api/conversation/turn', { ...snapshot, requestId }, controller.signal);
      if (state.guide.stateVersion !== result.expectedStateVersion || state.record.stateVersion !== result.expectedReadinessRevision) throw Error('Your information changed while this reply was prepared. Your answer is preserved.');
      const answering = ['message','choice','unknown','defer','next','confirm','reject'].includes(action.type);
      const answeredActive=answering&&(action.type!=='choice'||action.id===previousQuestion?.id);
      if (answering) {
        const prior = !answeredActive?null:pendingId ? 'Have I understood these details correctly?\n'+pendingUpdates.map(u=>Object.entries(u.fields).map(([k,v])=>(detailLabels[k]||'Reported detail')+': '+readable(v)).join(' · ')).join('\n') : previousQuestion && !before.assessment.journey.samplesVisible ? previousQuestion.question : previousNext?.question;
        if (prior && messages.at(-1)?.text !== prior) say('assistant', prior);
        let text = '';
        if (action.type === 'message') text = action.message;
        if (action.type === 'choice') text = [(previousQuestion?.choices || []).filter(([v]) => (action.fields.choice || '').split(',').includes(v)).map(([, l]) => l).join(', '), ...Object.entries(action.fields).filter(([k]) => k !== 'choice').map(([k, v]) => (previousQuestion?.fields.find(f => f.key === k)?.label || k) + ': ' + (v==='unknown'?'I don’t know':v==='deferred'?'Check later':['month','jobEnd','coverageEnd','start','year'].includes(k)?dateHint(v,previousQuestion?.knownYear)||v:v))].filter(Boolean).join(' · ');
        if(action.type==='choice'&&action.id==='T02'&&!answeredActive)text='Explanation preference: '+readable(action.fields.choice);
        if (action.type === 'next') text = previousNext?.choices.find(c => c.value === action.step)?.label || ({ samples: 'See sample plans', resume: 'Return to my conversation', explore: 'Explore my coverage options', learn_next: 'Keep learning', review: 'Review my information' }[action.step]);
        if (['unknown','defer','confirm','reject'].includes(action.type)) text = { unknown: 'I don’t know.', defer: 'Check later.', confirm: 'Use these details.', reject: 'Keep my previous information.' }[action.type];
        say('user', text); metrics.userTurns++;
        if (action.type === 'message' && draft.trim() === (draftSubmitted ?? action.message)) draft = '';
      } else if (action.type === 'help') { say('user', 'What’s the difference?'); metrics.userTurns++; }
      state = { guide: result.guide, record: result.record, assessment: result.assessment };
      pendingId = result.pendingId; pendingUpdates = result.pendingUpdates;
      metrics.llmCalls += result.metrics.llmCalls; metrics.processingMs += result.metrics.processingMs;
      say('assistant', result.reply, result.facts);
      if (answeredActive) { selected = []; if(previousQuestion)controlDrafts.delete(previousQuestion.signature); }
      else if(current()?.signature !== previousQuestion?.signature) {
        if(previousQuestion)controlDrafts.set(previousQuestion.signature,{selected:[...selected]});
        const saved=controlDrafts.get(current()?.signature);selected=saved?.selected||[];
      }
      const q = current(), prompt=q||followup();
      if (prompt && prompt.signature !== lastQuestion) { metrics.prompts++; metrics.atomicRequests += q?.atomicRequests||0; lastQuestion = prompt.signature; }
      busy = false; lastRequest = null; render({ from, anchor: action.type === 'help' || action.type === 'start' ? 'assistant' : 'user' });
      status(''); announce(q?.question || followup()?.question || 'The plan samples are here.');
      if (result.uiAction === 'review') review();
      if (state.guide.preferences.saveGuide) void persist();
    } catch (e) {
      busy = false;
      if (e.code === 428) { if (await consent()) return await turn(action, draftSubmitted); status('Your answer stays here. You can use the choices without AI.'); }
      else status((e.name === 'AbortError' ? 'Stopped waiting.' : e.message) + ' Your answer is preserved. No automatic retry.');
    } finally { busy = false; inflight = null; updateBusy(); }
  }
  function back() {
    if (busy) return;
    document.body.classList.remove('chat-mode'); $('landing').hidden = false; $('stage').hidden = true; active = false; utilities(); $('get-started').focus({ preventScroll: true });
  }
  function review(){const d=openDialog('Your reported information');d.append(el('p','These are reports you provided, not verified coverage. Editing preserves other answers and rechecks affected results.'));
    const depth=el('select'),depthLabel=el('label','Explanation preference');depth.id='review-depth';depthLabel.htmlFor=depth.id;depth.append(new Option('No preference selected',''),new Option('New to Medicare — more explanation','new'),new Option('Know a little','some'),new Option('Comfortable with the basics — keep it brief','comfortable'));depth.value=state.guide.fields['knowledge.general']?.value||'';depth.onchange=()=>{if(depth.value){d.close();void turn({type:'choice',id:'T02',fields:{choice:depth.value}});}};d.append(depthLabel,depth);
    const byField=Object.fromEntries(TenGuide.Q.map(q=>[q.field,q]));for(const [key,f]of Object.entries(state.guide.fields)){if(key==='comparison.scope.locationEvidence')continue;const q=byField[key];const row=el('section',undefined,'chat-review-row');row.append(el('h3',fieldTitle(key)),el('p',readable(f.value)),el('p',f.status==='derived'?'Derived from a published ZIP reference; residence is not verified':f.status==='stale'?'Needs review after a change':'Reported by you · not independently verified','chat-small'));if(q)row.append(button('Edit this answer',()=>{d.close();void turn({type:'edit',id:q.id});}));d.append(row);}
    for(const [id,f]of Object.entries(state.record.facts)){const definition=content.triggers.find(t=>t.id===id),row=el('section',undefined,'chat-review-row');row.append(el('h3',definition?.title||definition?.question||'Reported detail'));const items=f.value.items||[f.value];for(const item of items){const entries=Object.entries(item).filter(([k])=>!['entity','choice','programs'].includes(k));if(entries.length)for(const [k,v]of entries)row.append(el('p',(detailLabels[k]||k)+': '+readable(v)));else row.append(el('p',definition?.choices.find(([v])=>v===item.choice)?.[1]||'Reported detail'));}row.append(el('p',f.stale?'Needs review after a change':'Reported · not independently verified','chat-small'),button('Correct this detail',()=>{d.close();void turn({type:'edit',id});}));d.append(row);}
    const open=Object.entries(state.record.conversation?.baselineDispositions||{});for(const [id,disposition]of open)d.append(el('p',(TenGuide.Q.find(q=>q.id===id)?.question||'A detail')+': '+disposition+' · unresolved'));
    for(const [key,disposition]of Object.entries(state.record.conversation?.skippedDetails||{})){const field=key.split('.').at(-1);d.append(el('p',(detailLabels[field]||field)+': '+disposition+' · unresolved'));}
    d.append(button('Return to conversation',()=>d.close(),true));d.showModal();}
  function plans(){
    if(busy)return;
    const d=openDialog('Sample plan records');
    d.append(el('p','Five unvalidated 2027 Collier County, Florida records. These are samples, not personal recommendations, verified quotes or a complete market.'));
    appendPlans(d);d.append(button('Return to conversation',()=>d.close(),true));d.showModal();
  }
  async function persist(){saveQueue=saveQueue.then(async()=>{if(!state.guide.preferences.saveGuide)return;saveState='Saving…';if(active)progress();try{const receipt=await api('/api/conversation/save',{guide:state.guide,record:state.record,expectedVersion:version,expectedReadinessVersion:rv,operationId:crypto.randomUUID()});version=receipt.version;rv=receipt.readinessVersion;session.hasSaved=true;loaded=true;saveState=receipt.omittedSensitive?'Saved eligible reports · sensitive details stay in this tab':'Saved confirmed reports';saveError='';}catch(e){saveError=e.message;state.guide.preferences.saveGuide=false;saveState='Unsaved changes';}if(active)progress();utilities();});return saveQueue;}
  function privacy(){const d=openDialog('Your information & privacy');d.append(el('p',saveError||saveState),el('p','Saving is optional, for this browser, for '+(session.retentionDays||7)+' days from session creation. Anyone sharing this browser may reopen it. Raw chat, original messages, audio and unsent drafts are not saved. AI transfer is separate.'));const label=el('label'),check=el('input');check.type='checkbox';check.checked=state.guide.preferences.saveSensitive;label.append(check,document.createTextNode(' Also save confirmed optional wording, dates, provider, prescription, pharmacy and readiness details'));d.append(label,button('Save reported information',async()=>{if(session.hasSaved&&!loaded){d.append(el('p','Resume or review the existing saved copy before changing it.'));return;}state.guide.preferences.saveGuide=true;state.guide.preferences.saveSensitive=check.checked;d.close();await persist();}),button('Stop saving in this tab',()=>{state.guide.preferences.saveGuide=false;saveState='Visit only · existing saved copy retained';d.close();if(active)progress();}),button('Resume saved information',()=>{d.close();void resume();}),button('Review saved copy',async()=>{try{const g=await api('/api/guest/profile');const r=await api('/api/guest/readiness');const view=openDialog('Saved copy · current visit unchanged');for(const [key,f]of Object.entries(g.guide?.fields||{}))view.append(el('p',fieldTitle(key)+': '+readable(f.value)));view.append(el('p',Object.keys(r.record?.facts||{}).length+' saved readiness report groups.'),button('Close',()=>view.close()));view.showModal();}catch(e){d.append(el('p',e.message));}}),button('Delete this alternative’s saved information',()=>{const confirm=openDialog('Delete saved alternative information?');confirm.append(el('p','This permanently removes only this browser’s alternative guest profile and session. Original :8890 records and outside insurance records are unaffected.'),button('Cancel',()=>confirm.close()),button('Delete saved information',async()=>{try{await fetch('/api/guest/profile',{method:'DELETE',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Daylight-CSRF':session.csrf},body:JSON.stringify({expectedVersion:version,confirmed:true})}).then(async r=>{if(!r.ok)throw Error((await r.json()).error);});session=await api('/api/guest/session');version=0;rv=0;loaded=false;state.guide.preferences.saveGuide=false;saveState='Visit only';confirm.close();d.close();utilities();if(active)progress();}catch(e){confirm.append(el('p',e.message));}}));confirm.showModal();}));
    const diagnostics=el('details');diagnostics.append(el('summary','Conversation measurements'),el('p',metrics.prompts+' prompts · '+metrics.atomicRequests+' individual information requests · '+metrics.userTurns+' user turns · '+metrics.assistantTurns+' assistant messages · '+metrics.llmCalls+' AI calls. Elapsed this visit: '+Math.round((Date.now()-(metrics.startedAt||Date.now()))/1000)+' seconds, including pauses and waiting. Current visit only; this is not a measured consumer study.'));const more=el('details');more.append(el('summary','More about your information'),$('privacy-detail').content.cloneNode(true));d.append(more,diagnostics,button('Close',()=>d.close()));d.showModal();}
  async function resume(){if(busy)return;const d=openDialog('Resume saved information?');d.append(el('p','Open this only if you are comfortable showing the saved reports on this device. Raw conversation and drafts were not saved. Your current visit stays here until loading succeeds.'),button('Keep this visit',()=>d.close()),button('Resume saved reports',async()=>{try{const g=await api('/api/guest/profile'),r=await api('/api/guest/readiness');if(!g.guide)throw Error('No saved reports are available.');const snapshot={guide:g.guide,record:r.record||DaylightReadiness.create()};const result=await api('/api/conversation/turn',{...snapshot,action:{type:'refresh'},requestId:crypto.randomUUID()});state={guide:result.guide,record:result.record,assessment:result.assessment};version=g.version;rv=r.version;loaded=true;saveState=state.guide.preferences.saveGuide?'Saved eligible reports':'Visit only';messages=[];renderedMessages=0;renderedFirstId=null;draft='';selected=[];pendingId=null;say('assistant','Your saved reports are here. Chat and drafts were not saved; missing sensitive details remain unknown.');d.close();render();}catch(e){d.append(el('p',e.message+' Your current visit and saved copy are unchanged.'));}},true));d.showModal();}
  function voice(){const Voice=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Voice){status('Voice input is unavailable in this browser. Type your answer below.');$('chat-input').focus();return;}if(recognition){recognition.stop();recognition=null;return;}const d=openDialog('Use browser voice input?');d.append(el('p','Your browser’s speech service may process audio under its own permissions and privacy settings. Daylight receives the resulting text; it does not save audio. Review the text before sending it to Daylight or AI.'),button('Keep typing',()=>d.close()),button('Start voice input',()=>{d.close();recognition=new Voice();recognition.lang='en-US';recognition.onresult=e=>{draft=[draft,e.results[0][0].transcript].filter(Boolean).join(' ');$('chat-input').value=draft;updateBusy();};recognition.onerror=()=>status('Voice input could not finish. Type your answer instead.');recognition.onend=()=>recognition=null;recognition.start();}));d.showModal();}
  (async()=>{
    try {
      session=await api('/api/guest/session');version=session.version;
      [state,service,config,samples,content]=await Promise.all(['/api/conversation/initial','/api/status','/ten-config.json','/api/sample-plans','/readiness-content.json'].map(path=>api(path)));
      $('get-started').onclick=()=>begin();
      document.querySelector('.wordmark').onclick=e=>{e.preventDefault();if(active)back();};
      utilities();
    }catch(e){$('get-started').disabled=true;$('landing').append(el('p','The conversation could not load. Reload when connected. Existing saved information is unchanged.','flow-error'));}
  })();
})();
