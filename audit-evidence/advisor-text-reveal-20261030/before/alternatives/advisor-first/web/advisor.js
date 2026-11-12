/* D86: one life-led conversation, precise forms and explicit operation review. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const button = (text, fn, cls = 'text-button') => { const b = el('button', text, cls); b.type = 'button'; b.onclick = fn; return b; };
  const clone = value => structuredClone(value);
  const labels = {choice:'Answer',month:'Month and year',jobEnd:'Job ends',coverageEnd:'Work insurance ends',start:'Advantage coverage started',priorMedigap:'Left Medigap for that Advantage plan',name:'Medicine',strength:'Strength',form:'Form',practice:'Doctor or practice',city:'Office location',quantity:'Quantity and units',daysSupply:'Days supply',pharmacy:'Pharmacy',channel:'Retail or mail order',location:'Routine care location',gap:'Drug coverage gap',event:'Coverage change',eventDate:'Date',includes:'What the amount includes',year:'Coverage year',entity:'Item'};
  let session, state, service, config, baseline, sampleData;
  let active = false, busy = false, aiConsent = false, composing = false, selectedGoal = '', review = null, prepared = null;
  let savedVersion = 0, readinessVersion = 0, pendingSave = null, saveText = 'Visit only', showGuide = true;
  let history = [], frames = [], selected = [], currentSignature = '', lastRequest = null, failedRequest = null;
  let renderedHistory = 0, firstHistory = null;
  let reviewMessage = '', preparedVersions = [];
  const parkedMessages = [];
  const drafts = new Map();
  const metrics = {turns:0,llmCalls:0,started:Date.now()};

  async function api(path, body, method) {
    const response = await fetch(path, {method:method || (body ? 'POST' : 'GET'),credentials:'same-origin',
      headers:{'Content-Type':'application/json',...(session ? {'X-Daylight-CSRF':session.csrf} : {})},
      ...(body ? {body:JSON.stringify(body)} : {})});
    const value = await response.json();
    if (!response.ok) { const error = Error(value.error || 'This request could not finish.'); error.code = response.status; throw error; }
    return value;
  }
  function readable(value) {
    if (value == null) return 'Still open';
    if (Array.isArray(value)) return value.map(readable).join('; ');
    if (typeof value === 'object') return Object.entries(value).filter(([k]) => k !== 'entity').map(([k,v]) => k === 'items' ? readable(v) : (labels[k] || k) + ': ' + readable(v)).join(' · ');
    if (typeof value === 'string' && /^\d{4}-(0[1-9]|1[0-2])(-\d{2})?$/.test(value)) {
      const [year,month,day] = value.split('-');
      return ['January','February','March','April','May','June','July','August','September','October','November','December'][Number(month)-1]+' '+(day ? Number(day)+', ' : '')+year;
    }
    return ({unknown:'I don’t know',deferred:'For later',self:'Me',someone:'Someone I’m helping',new:'More explanation',some:'Some explanation',comfortable:'Keep it brief'})[value] || String(value);
  }
  function note(text) { $('status').textContent = text; $('announcer').textContent = text; }
  function q() { return state?.assessment.nextQuestion; }
  function dialog(title) {
    const opener = document.activeElement, d = el('dialog', undefined, 'dialog'), h = el('h2',title);
    h.id = 'dialog-heading'; d.setAttribute('aria-labelledby',h.id); d.append(h); document.body.append(d);
    d.addEventListener('close',() => { d.remove(); if (opener?.isConnected) opener.focus(); },{once:true});
    return d;
  }
  function consent() {
    if (aiConsent || config.mockAI) return Promise.resolve(true);
    return new Promise(resolve => {
      const d = dialog('Use AI for this conversation?');
      d.append(el('p','Your messages and relevant details you share go to OpenAI so Daylight can follow the conversation. Depending on your question, this can include your birthday timing, coverage dates, doctors, medicines and pharmacy. Only relevant profile details are reused; your full conversation is not attached or saved as a transcript. Saving is a separate choice. Do not enter ID numbers.'),
        button('Use the choices instead',() => { d.close(); resolve(false); },'secondary'),
        button('Allow and send',() => { aiConsent = true; d.close(); resolve(true); },'primary'));
      d.addEventListener('cancel',() => resolve(false),{once:true}); d.showModal();
    });
  }
  function setBusy(value) {
    busy = value;
    for (const b of document.querySelectorAll('button')) b.disabled = value;
    for (const input of $('current').querySelectorAll('input,select,textarea')) input.disabled = value;
    $('message').disabled = false;
    syncSend();
  }
  function rows(host, values, edits = false) {
    for (const row of values) {
      const block = el('div',undefined,'review-row');
      block.append(el('h3',row.label),el('p',readable(row.value)));
      if (row.status === 'stale') block.append(el('p','Needs review after a change','small'));
      if (row.status === 'derived') block.append(el('p','From a published ZIP reference; residence is not verified.','small'));
      if (edits) block.append(button('Edit',async () => { document.querySelector('dialog')?.close(); if(row.id.startsWith('S_')){$('message').focus();note(row.id==='S_AGE65' ? 'Tell Daylight the corrected birthday detail, for example: I turn 65 in December 2027.' : 'Tell Daylight the corrected work status, for example: I’m still working.');return;} await turn({type:'edit',id:row.id}); }));
      host.append(block);
    }
  }
  function factBlock(facts) {
    const host = el('div',undefined,'facts');
    for (const fact of facts || []) {
      host.append(el('h2',fact.title),el('p',fact.text));
      const links = [...(fact.source ? [{url:fact.source,label:'Medicare.gov source'}] : []),...(fact.sources || [])];
      if (links.length) {
        const details = el('details',undefined,'sources'); details.append(el('summary','Sources'));
        for (const link of links) { try { const url = new URL(link.url); if (url.protocol !== 'https:') continue; const a = el('a',link.label || link.title || url.hostname); a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer'; details.append(a); } catch {} }
        host.append(details);
      }
    }
    return host;
  }
  function paintHistory() {
    const host = $('history');
    if (renderedHistory > history.length || firstHistory !== history[0]) {host.replaceChildren();renderedHistory = 0;}
    for (const item of history.slice(renderedHistory)) host.append(exchange(item));
    renderedHistory = history.length;firstHistory = history[0];
  }
  function exchange(item) {
    const block = el('div',undefined,'exchange');
    if (item.user) { const user = el('article',undefined,'chat-message chat-user'); user.setAttribute('aria-label','You'); user.append(el('p',item.user)); block.append(user); }
    if (item.reply || item.facts?.length) {
      const answer = el('article',undefined,'chat-message chat-daylight'); answer.setAttribute('aria-label','Daylight');
      if (item.reply) answer.append(el('p',item.reply));
      if (item.facts?.length) answer.append(factBlock(item.facts));
      block.append(answer);
    }
    return block;
  }
  function phaseTrack() {
    const host = $('phases'); host.replaceChildren();
    const journey = state.assessment.journey, list = el('ol',undefined,'adaptive-phases');
    journey.labels.forEach((name,i) => { const n = el('li',name); if (i === journey.phase) n.setAttribute('aria-current','step'); list.append(n); });
    const bar = el('progress'); bar.max = 4; bar.value = journey.phase + 1;
    bar.setAttribute('aria-label','Conversation progress: '+journey.labels[journey.phase]); bar.title = 'Conversation milestones, not verified eligibility.';
    host.append(list,bar);
  }
  function drawReference() {
    const host = $('reference'); host.replaceChildren();
    host.hidden = state.assessment.narrative.opener || state.assessment.journey.samplesVisible || !!prepared || !!review;
    const visual = state.assessment.narrative.visual;
    const details = el('details'), summary = el('summary',visual.title), content = el('div',undefined,'reference-content');
    details.open = showGuide; details.ontoggle = () => { showGuide = details.open; state.guide.flow.guideOpen = showGuide; }; details.append(summary,content); host.append(details);
    if (visual.kind === 'timeline') {
      const list = el('ol',undefined,'timeline'); for (const [label,value] of visual.items) { const row = el('li'); row.append(el('span',label),el('strong',readable(value))); list.append(row); } content.append(list,el('p','Your reports, with unknown dates left open.','diagram-caption'));
    } else if (visual.kind === 'parts') {
      const picture = el('div',undefined,'diagram diagram-parts');
      for (const [name,meaning,id] of [['Part A','Hospital insurance','parta'],['Part B','Medical insurance','partb']]) { const b = button('',() => concept(id),'diagram-box'); b.append(el('strong',name),el('small',meaning)); picture.append(b); } content.append(picture);
    } else if (visual.kind === 'routes') {
      for (const [title,copy,id] of [['Original Medicare','Parts A + B · optional separate Part D and Medigap','original'],['Medicare Advantage','Parts A + B through a private plan · most include drug coverage','advantage']]) { const route = el('div',undefined,'route'); route.append(el('h3',title),el('p',copy),button('Explain '+title,() => concept(id))); content.append(route); }
    } else {
      const b = button('',() => concept('basics'),'diagram-box'); b.append(el('strong','Medicare'),el('small','Federal health insurance')); content.append(b,button('Explain Medicare',() => concept('basics')));
    }
    if (visual.kind !== 'basics') content.append(button('Explain this',() => concept(visual.kind === 'timeline' ? 'dates' : visual.kind === 'parts' ? 'parts' : 'routesintro')));
  }
  function draftFor(question) {
    if (drafts.has(question.signature)) return drafts.get(question.signature);
    const fields = {};
    let choice = [];
    const base = baseline.find(x => x.id === question.id);
    if (base) {
      const f = state.guide.fields[base.field];
      if (f && !['unknown','skipped','stale'].includes(f.status)) choice = Array.isArray(f.value) ? [...f.value] : [f.value];
      if (question.id==='T01' && state.assessment.task==='timing') choice = []; // Internal timing focus is not a previously selected Find coverage answer.
      const fieldKey = ({T04:'coverage.requestedStartMonth',T06:'needs.providers',T07:'needs.medications',T03:'comparison.scope.zip'})[question.id];
      if (fieldKey && state.guide.fields[fieldKey]) fields[question.fields[0]?.key || 'text'] = state.guide.fields[fieldKey].value;
    } else {
      let value = state.record.facts[question.id]?.value || {};
      if (question.entity !== 'profile') value = value.items?.find(x => x.entity === question.entity) || {};
      for (const field of question.fields) if (value[field.key] != null) fields[field.key] = value[field.key];
      if (value.choice) choice = [value.choice];
    }
    const draft = {fields,choice}; drafts.set(question.signature,draft); return draft;
  }
  function hasFormAnswer(question) {
    if (!question) return false;
    const draft = draftFor(question);
    return !!draft.resolution || !!draft.choice.length || Object.values(draft.fields).some(value => String(value).trim());
  }
  function syncSend() {
    const send = $('send'), words = $('message').value.trim(), slot = $('selection');
    const selectedAnswer = state?.assessment.narrative.opener ? selectedGoal && selectedGoal !== 'unresolved' : hasFormAnswer(q());
    const contextual = !words && (review || selectedAnswer) && !prepared;
    const target = contextual && slot ? slot : $('composer-input');
    if (send.parentElement !== target) { if (target === slot) target.prepend(send); else target.append(send); }
    send.textContent = !words && review ? review.label : 'Send';
    send.disabled = busy || !!prepared || !(words || review || selectedAnswer);
    if (slot) slot.hidden = !contextual;
  }
  function selectionSlot(host,clear) {
    const slot = el('div',undefined,'chat-selection'); slot.id = 'selection';
    if (clear) slot.append(button('Clear selection',clear));
    host.append(slot);
  }
  function revealSend() {
    const reading = $('reading'), rect = $('send').getBoundingClientRect(), bounds = reading.getBoundingClientRect();
    if ($('send').closest('#reading') && rect.bottom > bounds.bottom - 12) reading.scrollTop += rect.bottom - bounds.bottom + 12;
  }
  async function submitCurrent() {
    if (composing || busy) return;
    const words = $('message').value.trim();
    if (words) { await turn({type:'message',message:words},words); return; }
    if (review) {
      const signature = q()?.signature;
      const ok = await turn({type:review.kind === 'preparation' ? 'run_preparation' : 'accept_review',token:review.token},review.label);
      if (ok && signature) drafts.delete(signature);
    } else if (state.assessment.narrative.opener && selectedGoal && selectedGoal !== 'unresolved') {
      const goal = selectedGoal;
      const label = {learn:'Understand Medicare',compare:'Find coverage',review:'Review my coverage'}[goal];
      if (await turn({type:'choice',id:'T01',fields:{choice:goal}},label)) {selectedGoal = '';syncSend();}
    } else if (q()) await submitForm(q());
  }
  function renderForm(host,question) {
    if (question.conversational) return;
    const draft = draftFor(question), form = el('form',undefined,'task-form'); form.id = 'detail-form';
    if (question.choices.length) {
      const choices = el('div',undefined,'choices'); choices.setAttribute('role','group'); choices.setAttribute('aria-label',question.question);
      for (const [value,label] of question.choices.filter(([v]) => v !== 'unknown')) {
        const b = button(label,() => { draft.resolution = ''; if (question.multi && !['none','no','local'].includes(value)) draft.choice = draft.choice.filter(x => !['none','no','local'].includes(x)).includes(value) ? draft.choice.filter(x => x !== value) : [...draft.choice.filter(x => !['none','no','local'].includes(x)),value]; else draft.choice = draft.choice.length === 1 && draft.choice[0] === value ? [] : [value]; renderCurrent(); revealSend(); },'choice');
        b.setAttribute('aria-pressed',String(draft.choice.includes(value))); choices.append(b);
      }
      form.append(choices);
    }
    const fieldGrid = el('div',undefined,'field-grid');
    for (const field of question.fields) {
      const group = el('div',undefined,'field-group'),label = el('label',field.label),id = 'detail-'+field.key;
      label.htmlFor = id;
      const input = el(field.type === 'select' ? 'select' : field.type === 'textarea' ? 'textarea' : 'input'); input.id = id; input.name = field.key;
      if (field.type === 'select') { input.append(new Option('Choose an answer','')); for (const [v,l] of field.options) input.append(new Option(l,v)); input.append(new Option('I don’t know','unknown'),new Option('Check later','deferred')); }
      else { if (input.tagName === 'INPUT') input.type = 'text'; input.autocomplete = 'off'; input.placeholder = ['month','jobEnd','coverageEnd','start'].includes(field.key) ? 'For example, March 2027' : field.key === 'zip' ? 'For example, 34102' : field.key === 'quantity' ? 'For example, 30 tablets' : 'Enter what you know'; }
      input.value = draft.fields[field.key] || ''; input.oninput = () => { draft.fields[field.key] = input.value; draft.resolution = ''; syncSend(); };
      group.append(label,input);
      if (field.type !== 'select' && question.fields.length > 1) { const tools = el('div',undefined,'field-tools'); tools.append(button('I don’t know',() => { draft.fields[field.key] = 'unknown'; input.value = 'unknown'; draft.resolution = ''; syncSend(); }),button('Check later',() => { draft.fields[field.key] = 'deferred'; input.value = 'deferred'; draft.resolution = ''; syncSend(); })); group.append(tools); }
      fieldGrid.append(group);
    }
    if (question.fields.length) form.append(fieldGrid);
    const actions = el('div',undefined,'choices');
    for (const [value,label] of [['unknown','I don’t know'],['defer','Check later']]) {
      const b = button(label,() => {draft.resolution = draft.resolution === value ? '' : value;draft.choice = [];renderCurrent();revealSend();},'choice');
      b.setAttribute('aria-pressed',String(draft.resolution === value)); actions.append(b);
    }
    form.append(actions); selectionSlot(form,() => {draft.choice = [];draft.resolution = '';draft.fields = {};renderCurrent();});
    form.onsubmit = e => { e.preventDefault(); void submitCurrent(); }; host.append(form);
  }
  async function submitForm(question) {
    if ($('message').value.trim()) {note('You have an unsent message. Send it first, or clear it before continuing with the form. Your entries are still here.');return;}
    const draft = draftFor(question),fields = Object.fromEntries(Object.entries(draft.fields).filter(([,v]) => String(v).trim()).map(([k,v]) => [k,String(v).trim()]));
    if (draft.resolution) { await turn({type:draft.resolution,id:question.id},draft.resolution === 'unknown' ? 'I don’t know' : 'Check later'); return; }
    if (draft.choice.length) fields.choice = draft.choice.join(',');
    if (question.id === 'T04' && fields.month && !fields.choice) fields.choice = 'month';
    if (question.id === 'T06' && fields.choice === 'none' || question.id === 'T07' && fields.choice === 'no') delete fields.text;
    else if (['T06','T07'].includes(question.id) && fields.text) delete fields.choice;
    if (!Object.keys(fields).length) { note('Add an answer, or choose I don’t know or Check later.'); return; }
    const choiceLabels = (question.choices || []).filter(([id]) => draft.choice.includes(id)).map(([,label]) => label);
    const detailWords = question.fields.filter(f => fields[f.key]).map(f => f.label+': '+readable(fields[f.key]));
    await turn({type:question.fields.length ? 'stage' : 'choice',id:question.id,entity:question.entity,fields},[...choiceLabels,...detailWords].join(' · '));
  }
  function renderReview(host) {
    host.append(el('h1',review.kind === 'preparation' ? 'Review your next steps' : 'Does this look right?'));
    host.append(el('p',review.kind === 'interpretation' ? 'These are reports from your message, not verified coverage.' : review.kind === 'preparation' ? 'This will prepare an editable checklist. It will not contact anyone or change your coverage.' : 'These are the details you entered, not verified coverage.'));
    const sheet = el('div',undefined,'review-sheet'); rows(sheet,review.rows); if (!review.rows.length) sheet.append(el('p','No personal details are needed to prepare a general starting checklist.')); host.append(sheet);
    selectionSlot(host);
    const actions = el('div',undefined,'task-actions'); actions.append(button(review.kind === 'preparation' ? 'Back to my conversation' : 'Make edits',() => turn({type:'discard_review',token:review.token})));
    host.append(actions);
  }
  function renderSamples(host) {
    host.append(el('h1','Sample plan options'),el('p','Explore how plan information is presented. These five unvalidated records are 2027 Collier County, Florida samples. They are not a complete market or personal recommendations.','sample-scope'));
    host.append(button('Return to my conversation',() => turn({type:'next',step:'resume'}),'secondary'));
    const timing = state.guide.fields['coverage.requestedStartMonth']?.value || state.record.facts.RC03?.value?.year;
    if (timing && !String(timing).startsWith('2027')) host.append(el('p','Your reported timing is '+timing+'. These samples retain their 2027 year.','notice'));
    for (const plan of sampleData.plans) {
      const row = el('article',undefined,'sample'); row.append(el('h3',plan.name),el('p',plan.id,'small'));
      const dl = el('dl');
      for (const [label,value] of [['Plan type',plan.plan_type],['Year',plan.year],['Location','Collier County, Florida'],['Monthly premium','Not validated'],['Doctor participation','Not checked'],['Prescription fit','Not checked'],['Personal total cost','Not calculated']]) dl.append(el('dt',label),el('dd',value));
      row.append(dl);
      if (plan.source?.url) {const link = el('a','Published source');link.href = plan.source.url;link.target = '_blank';link.rel = 'noopener noreferrer';row.append(link);}
      host.append(row);
    }
    host.append(button('Return to my conversation',() => turn({type:'next',step:'resume'}),'secondary'));
  }
  function renderCurrent() {
    const host = $('current');
    // Keep one persistent Send control while replacing the inline task.
    $('composer-input').append($('send')); host.replaceChildren();
    const opening = state.assessment.narrative.opener && !review && !prepared;
    $('composer').hidden = !!prepared;
    if (prepared) renderPrepared(host);
    else if (review) renderReview(host);
    else if (state.assessment.journey.samplesVisible) renderSamples(host);
    else if (opening) {
      host.append(el('h2','What has you thinking about Medicare today?'),el('p','For example: turning 65, leaving work, reviewing your coverage, or helping someone else.','intro-example'),el('p','A sentence or two is enough.','intro-help'));
    } else if (q() && state.assessment.narrative.focus !== 'prepare') {
      host.append(el('h1',q().question)); if (q().why) host.append(el('p',q().why,'why')); renderForm(host,q());
      if (state.record.conversation.editing) host.append(button('Return to my current task',() => turn({type:'resume'})));
    } else {
      host.append(el('h1',state.assessment.task === 'learn' ? 'What would you like to understand next?' : 'Here’s where we are'));
      if (state.assessment.journey.summary) host.append(el('p',state.assessment.journey.summary));
      const unresolved = state.assessment.unresolvedReportedInputs;
      if (unresolved.length) { const details = el('details'); details.append(el('summary','Details still open')); for (const item of unresolved) details.append(el('p',item.label+' — '+readable(item.state))); host.append(details); }
      const topics = el('div',undefined,'topic-actions');
      for (const [id,label] of [['basics','What Medicare is'],['parts','Parts A and B'],['routesintro','The two coverage paths'],['drugbasics','Prescription coverage'],['costs','How costs work']]) topics.append(button(label,() => concept(id)));
      host.append(topics,button('Prepare my next steps',() => turn({type:'review_preparation'}),'primary'));
    }
    $('message-label').textContent = 'Type an answer or ask a question';
    $('message').placeholder = opening ? 'Start wherever you like…' : 'You can answer here, too…';
    $('restore-draft').hidden = !parkedMessages.length;
    $('shortcuts').replaceChildren();
    if (opening) {
      $('shortcuts').append(el('p','Need a starting point?','small')); const row = el('div',undefined,'shortcut-row');
      for (const [id,label] of [['learn','Understand Medicare'],['compare','Find coverage'],['review','Review my coverage'],['unresolved','Something else']]) { const b = button(label,() => { selectedGoal = selectedGoal === id ? '' : id; renderCurrent(); revealSend(); if (id === 'unresolved') $('message').focus(); },'shortcut'); b.setAttribute('aria-pressed',String(selectedGoal === id)); row.append(b); }
      $('shortcuts').append(row);
      selectionSlot($('shortcuts'),() => {selectedGoal = '';renderCurrent();});
    } else if (!review && !prepared && state.assessment.narrative.suggestedCheck) $('shortcuts').append(button('Organize my work-to-Medicare transition',() => turn({type:'suggest_check',id:'timing'})));
    $('prepare').hidden = opening || !!review || !!prepared;
    drawReference(); setBusy(busy);
  }
  function renderPrepared(host) {
    const panel = el('section',undefined,'prepared');panel.append(el('h1','Your next steps, ready to use'),el('p','Edit this checklist, then copy or print it. Nothing has been sent.'));
    if (prepared.guideRevision !== state.guide.stateVersion || prepared.recordRevision !== state.record.stateVersion) panel.append(el('p','Your details have changed since this was prepared. Review the checklist before using it.','notice'));
    const label = el('label','Your editable checklist'); label.htmlFor = 'prepared-text'; const text = el('textarea');text.id = 'prepared-text';text.value = prepared.text;text.oninput = () => { prepared.text = text.value; };
    const print = el('pre',prepared.text,'print-output'); print.hidden = true;
    const actions = el('div',undefined,'task-actions');actions.append(button('Copy checklist',async () => { try { await navigator.clipboard.writeText(prepared.text); note('Checklist copied.'); } catch { text.focus();text.select();note('Select and copy the checklist text.'); } },'primary'),button('Print',() => { print.textContent = prepared.text;window.print(); },'secondary'),button('Return to my conversation',() => { prepared = null;renderCurrent(); }));
    panel.append(label,text,actions,el('p','Prepared from your reports. Personal coverage checks remain open.','small'),print);host.append(panel);
  }
  function render() { document.body.classList.toggle('chat-mode',active);phaseTrack();paintHistory();renderCurrent();$('save-status').textContent = saveText;$('resume').hidden = $('landing-resume').hidden = !session.hasSaved; }
  async function turn(action, userWords = '') {
    if (busy) return false;
    if (['accept_review','review_preparation','run_preparation'].includes(action.type) && $('message').value.trim()) {note('Send or clear your unsent message before confirming this step. Your draft is still here.');return false;}
    const before = state, previous = q(), fromReview = review;
    const candidate = {guide:clone(state.guide),record:clone(state.record),action,aiConsent:aiConsent || config.mockAI,contextPolicy:aiConsent || config.mockAI ? 'natural-context-v1' : null,...(state.continuation ? {continuation:state.continuation} : {})};
    // After a lost response, checking the same request retrieves its resolved
    // state rather than extracting/applying a second time.
    const prior = failedRequest && {...failedRequest};if(prior) delete prior.requestId;
    const payload = prior && JSON.stringify(prior) === JSON.stringify(candidate) ? failedRequest : {...candidate,requestId:crypto.randomUUID()};
    lastRequest = payload;setBusy(true);note(action.type === 'message' ? 'Daylight is working through your message…' : 'Working…');
    try {
      const result = await api('/api/conversation/turn',payload);
      failedRequest = null;
      state = result;review = result.review || null;prepared = result.preparation || null;
      if (review?.kind === 'interpretation' && userWords) reviewMessage = userWords;
      if (prepared) preparedVersions.push(prepared);
      if (previous && !previous.conversational && q()?.signature !== previous.signature && !['edit','resume'].includes(action.type)) frames.push(previous.id);
      const appended = !!(userWords || result.reply || result.facts?.length);
      if (appended) history.push({user:userWords,reply:result.reply || '',facts:result.facts || []});
      if (action.type === 'message') { selectedGoal = ''; if ($('message').value === userWords) $('message').value = ''; }
      if (action.type === 'discard_review' && fromReview?.kind === 'interpretation' && !$('message').value.trim()) $('message').value = reviewMessage;
      if (action.type === 'accept_review') reviewMessage = '';
      metrics.turns++;metrics.llmCalls += result.metrics?.llmCalls || 0;
      let saveWarning = '';
      if (state.guide.preferences.saveGuide && !review) {try {await save();} catch(error) {saveWarning = error.message+' Your current visit is still here.';}}
      note(saveWarning);render();
      if (fromReview && fromReview.kind!=='preparation' && !review && action.type === 'discard_review') note('Your draft is still here. Make edits and continue when ready.');
      const last = appended && $('history').lastElementChild;
      const target = last ? (action.type === 'read_concept' ? last.querySelector('.chat-daylight') : last.querySelector('.chat-user') || last.querySelector('.chat-daylight')) || last : $('current');
      const reading = $('reading');
      // Scroll the transcript only; the submitted answer stays in view above the reply.
      if (target) reading.scrollTop += target.getBoundingClientRect().top - reading.getBoundingClientRect().top - 18;
      target?.setAttribute('tabindex','-1');target?.focus({preventScroll:true});
      return true;
    } catch (error) {
      if (!error.code) failedRequest = payload;
      state = before;review = fromReview;
      if (action.type === 'message' && error.code === 428 && !aiConsent) {
        setBusy(false);
        if (await consent()) return await turn(action,userWords);
        parkedMessages.push($('message').value);$('message').value = '';renderCurrent();
        note('Your draft is set aside in this tab. Use the choices, or Restore draft when you want it back.');return false;
      }
      note(error.message+' Your input is preserved.');return false;
    }
    finally {setBusy(false);}
  }
  async function concept(id) { await turn({type:'read_concept',id}); }
  async function save() {
    if (pendingSave) throw Error('An earlier save needs checking. Open privacy to retry that exact save.');
    pendingSave = clone({guide:state.guide,record:state.record,expectedVersion:savedVersion,expectedReadinessVersion:readinessVersion,operationId:crypto.randomUUID()});
    await completeSave();
  }
  async function completeSave() {
    try { const result = await api('/api/conversation/save',pendingSave);savedVersion = result.version;readinessVersion = result.readinessVersion;session.hasSaved = true;saveText = result.omittedSensitive ? 'Saved · sensitive details omitted' : 'Saved in this browser';pendingSave = null; }
    catch (error) {saveText = 'Not saved — '+error.message;throw error;}
    finally {$('save-status').textContent = saveText;}
  }
  function reviewInformation() {
    const d = dialog('Your reported information');d.append(el('p','You can correct these reports. They do not establish verified coverage.'));
    rows(d,state.reportedRows || [],true);
    if (preparedVersions.length) {
      d.append(el('h3','Prepared checklists'));
      preparedVersions.forEach((version,i) => d.append(button('Open checklist '+(i+1),() => { prepared = version;review = null;d.close();renderCurrent(); })));
    }
    const preference = el('label','Explanation preference'),select = el('select');select.setAttribute('aria-label','Explanation preference');select.append(new Option('Choose if you like',''),new Option('New to Medicare — more explanation','new'),new Option('I know some basics','some'),new Option('Keep it brief','comfortable'));select.value = state.guide.fields['knowledge.general']?.value || '';select.onchange = async () => {if(select.value){d.close();await turn({type:'choice',id:'T02',fields:{choice:select.value}});}};preference.append(select);d.append(preference,button('Close',() => d.close(),'secondary'));d.showModal();
  }
  function privacy() {
    const d = dialog('Your information & privacy');
    d.append(el('p','Saving is optional, for this browser, for '+(session.retentionDays || 7)+' days from session creation. Anyone sharing this browser may reopen saved reports. Raw messages, conversation history and unsent drafts are not saved.'),el('p','After your permission, AI receives your messages and relevant profile details so it can follow the conversation. Saving and AI transfer are separate choices. Your full conversation is not attached.'));
    const saving = el('label'),saveBox = el('input');saveBox.type = 'checkbox';saveBox.checked = state.guide.preferences.saveGuide;saving.append(saveBox,document.createTextNode('Save my reported information in this browser'));
    const sensitive = el('label'),sensitiveBox = el('input');sensitiveBox.type = 'checkbox';sensitiveBox.checked = state.guide.preferences.saveSensitive;sensitive.append(sensitiveBox,document.createTextNode('Also save sensitive details, such as birthday timing, work status, doctors and prescriptions'));
    d.append(saving,sensitive,button('Apply privacy choices',async () => {state.guide.preferences.saveGuide = saveBox.checked;state.guide.preferences.saveSensitive = sensitiveBox.checked;try {if (saveBox.checked) await save();else saveText = session.hasSaved ? 'Saving paused · saved copy remains until deleted or expired' : 'Visit only';d.close();render();}catch(error){d.append(el('p',error.message));}},'primary'));
    if (pendingSave) d.append(button('Retry the pending save',async () => {try {await completeSave();d.close();render();note('The earlier save was checked. Apply privacy choices again to save newer changes.');}catch(error){d.append(el('p',error.message));}},'secondary'));
    if (session.hasSaved) d.append(button('Delete this variant’s saved information',() => {const confirm = dialog('Delete saved advisor information?');confirm.append(el('p','This permanently removes this browser’s saved advisor reports and session. Other Daylight variants are unaffected.'),button('Cancel',() => confirm.close(),'secondary'),button('Delete saved information',async () => {try {await api('/api/guest/profile',{expectedVersion:savedVersion,confirmed:true},'DELETE');session = await api('/api/guest/session');savedVersion = readinessVersion = 0;state.guide.preferences.saveGuide = false;state.guide.preferences.saveSensitive = false;saveText = 'Visit only';confirm.close();d.close();render();}catch(error){confirm.append(el('p',error.message));}},'primary'));confirm.showModal();}));
    const details = el('details');details.append(el('summary','Scope and service details'),el('p','Plan cards are five unvalidated 2027 Collier County samples. Recommendations, eligibility, prices, exact doctor/drug fit and enrollment remain independently held. The separate advisor service shares the existing $1/UTC-day AI cap. No automatic retries. Production vendor/retention review remains separate.'),el('p',metrics.turns+' turns · '+metrics.llmCalls+' AI calls in this visit. These are diagnostics, not a consumer study.'));d.append(details,button('Close',() => d.close(),'secondary'));d.showModal();
  }
  async function resume() {
    const d = dialog('Resume saved information?');d.append(el('p','Only open this if it is appropriate to show the saved reports on this device. Conversation and drafts were not saved.'),button('Keep this visit',() => d.close(),'secondary'),button('Resume saved reports',async () => {try {const g = await api('/api/guest/profile'),r = await api('/api/guest/readiness');if (!g.guide) throw Error('No saved reports were found.');const result = await api('/api/conversation/turn',{guide:g.guide,record:r.record || state.record,action:{type:'refresh'},requestId:crypto.randomUUID()});state = result;savedVersion = g.version;readinessVersion = r.version;history = [];review = prepared = null;drafts.clear();showGuide = state.guide.flow.guideOpen !== false;active = true;$('landing').hidden = true;$('workspace').hidden = false;d.close();saveText = 'Resumed · omitted sensitive details remain open';render();}catch(error){d.append(el('p',error.message+' Your current visit is preserved.'));}},'primary'));d.showModal();
  }
  $('composer').onsubmit = e => {e.preventDefault();void submitCurrent();};
  $('message').oninput = syncSend;
  $('restore-draft').onclick = () => {if($('message').value.trim()){note('Send or clear the current message before restoring your earlier draft.');return;}$('message').value = parkedMessages.pop() || '';renderCurrent();$('message').focus();note('Draft restored. It has not been sent.');};
  $('message').addEventListener('compositionstart',() => { composing = true; });$('message').addEventListener('compositionend',() => { composing = false; });
  $('message').addEventListener('keydown',e => {if(e.key === 'Enter' && !e.shiftKey && !e.isComposing && !composing){e.preventDefault();$('composer').requestSubmit();}});
  $('start').onclick = () => {active = true;$('landing').hidden = true;$('workspace').hidden = false;if(!history.length) history.push({reply:'Hi, I’m Daylight, your AI Medicare guide. I’ll help you understand your options, one step at a time.'});render();window.scrollTo({top:0,behavior:'instant'});$('workspace').focus({preventScroll:true});};
  $('back').onclick = async () => {if(review){await turn({type:'discard_review',token:review.token});return;}if(frames.length){await turn({type:'edit',id:frames.pop()});return;}$('workspace').hidden = true;$('landing').hidden = false;active = false;document.body.classList.remove('chat-mode');};
  $('review').onclick = reviewInformation;$('privacy').onclick = $('landing-privacy').onclick = privacy;$('resume').onclick = $('landing-resume').onclick = resume;
  $('prepare').onclick = () => turn({type:'review_preparation'});$('samples').onclick = () => turn({type:'next',step:'samples'});
  window.addEventListener('resize',() => {if(active) drawReference();});
  Promise.all([api('/api/guest/session'),api('/api/status'),api('/ten-config.json'),api('/baseline-content.json'),api('/api/sample-plans')]).then(async ([s,v,c,b,p]) => {session = s;service = v;config = c;baseline = b;sampleData = p;savedVersion = s.version;state = await api('/api/conversation/initial');state.reportedRows = [];showGuide = state.guide.flow.guideOpen !== false;$('start').disabled = false;$('privacy').disabled = $('landing-privacy').disabled = false;$('fixture').hidden = !config.mockAI;$('resume').hidden = $('landing-resume').hidden = !session.hasSaved;}).catch(error => {note(error.message);$('landing').append(el('p','Daylight could not load. Reload to try again. Existing saved information is unchanged.','notice'));});
})();
