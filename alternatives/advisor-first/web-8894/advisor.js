/* D86: one life-led conversation, precise forms and explicit operation review. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const button = (text, fn, cls = 'text-button') => { const b = el('button', text, cls); b.type = 'button'; b.onclick = fn; return b; };
  const clone = value => structuredClone(value);
  const OPENING_QUESTION = 'What has you thinking about Medicare today?';
  const OPENING_CHOICES = Object.freeze({
    learn: {label:'Understand Medicare',reply:'We can start with the Medicare basics.'},
    compare: {label:'Find coverage',reply:'Let’s work through the coverage options for your situation.'},
    review: {label:'Review my coverage',reply:'Let’s start with the coverage you have today.'}
  });
  const OPENING_REPLY_DELAY = 350;
  const labels = {choice:'Answer',month:'Month and year',jobEnd:'Job ends',coverageEnd:'Work insurance ends',start:'Advantage coverage started',priorMedigap:'Left Medigap for that Advantage plan',name:'Medicine',strength:'Strength',form:'Form',practice:'Doctor or practice',city:'Office location',quantity:'Quantity and units',daysSupply:'Days supply',pharmacy:'Pharmacy',channel:'Retail or mail order',location:'Routine care location',gap:'Drug coverage gap',event:'Coverage change',eventDate:'Date',includes:'What the amount includes',year:'Coverage year',entity:'Item'};
  let session, state, service, config, baseline, sampleData;
  let active = false, conversationStarted = false, busy = false, composing = false, selectedGoal = '', review = null, prepared = null;
  let conversationScroll = 0;
  let savedVersion = 0, readinessVersion = 0, pendingSave = null, saveText = 'Visit only', showGuide = true;
  let history = [], frames = [], selected = [], currentSignature = '', lastRequest = null, failedRequest = null;
  let renderedHistory = 0, firstHistory = null;
  const revealedReplies = new WeakSet();
  const revealedQuestions = new WeakSet();
  let openingRevealed = false;
  let lastFocus = 0; // Progress track: keep the last positive focus across failed or questionless turns.
  let reviewMessage = '', preparedVersions = [];
  const parkedMessages = [];
  const drafts = new Map();
  const metrics = {turns:0,llmCalls:0,started:Date.now()};
  const visitResume = window.DaylightVisitResume;
  let pendingTimer = 0;
  let dialogCount = 0;
  let doctorComposer = null, doctorDraft = '';

  async function api(path, body, method) {
    const previewPath = location.pathname === '/d146/' &&
      (path.startsWith('/api/') || path === '/ten-config.json') ? '/d146' + path : path;
    const response = await fetch(previewPath, {method:method || (body ? 'POST' : 'GET'),credentials:'same-origin',
      headers:{'Content-Type':'application/json',...(session ? {'X-Daylight-CSRF':session.csrf} : {})},
      ...(body ? {body:JSON.stringify(body)} : {})});
    const value = await response.json();
    if (!response.ok) { const error = Error(value.error || 'This request could not finish.'); error.code = response.status;error.recovery = value.recovery; throw error; }
    return value;
  }
  function readable(value) {
    if (value == null) return 'Still open';
    if (Array.isArray(value)) return value.map(readable).join('; ');
    // D138: a routing answer ("details", "dates") is not a detail to read back.
    if (typeof value === 'object') return Object.entries(value).filter(([k,v]) => k !== 'entity' && !(k === 'choice' && Object.keys(value).length > 1 && ['details','dates','partial','amount'].includes(v))).map(([k,v]) => k === 'items' ? readable(v) : (labels[k] || k) + ': ' + readable(v)).join(' · ');
    if (typeof value === 'string' && /^(january|february|march|april|may|june|july|august|september|october|november|december)\b/.test(value)) return value[0].toUpperCase()+value.slice(1);
    if (typeof value === 'string' && /^\d{4}-(0[1-9]|1[0-2])(-\d{2})?$/.test(value)) {
      const [year,month,day] = value.split('-');
      return ['January','February','March','April','May','June','July','August','September','October','November','December'][Number(month)-1]+' '+(day ? Number(day)+', ' : '')+year;
    }
    return ({unknown:'I don’t know',deferred:'For later',self:'Me',someone:'Someone I’m helping',new:'More explanation',some:'Some explanation',comfortable:'Keep it brief'})[value] || String(value);
  }
  let cmsChecklist = null;
  // D138: budget and pricing-review messages are operator wording. A
  // participant sees one plain sentence; the operator detail stays on /api/status.
  const PAUSED = /AI pricing is unknown|review expired|Paid requests are paused|AI usage needs reconciliation|persistent AI budget|could not be verified/i;
  const plain = text => PAUSED.test(text || '') ? 'Daylight can’t write new replies right now. You can still answer with the buttons, and the Plans page still works. Your message is kept.' : text;
  function note(text) { $('status').textContent = plain(text); }
  function q() { return state && usableQuestion(state); }
  function dialog(title) {
    const opener = document.activeElement, d = el('dialog', undefined, 'dialog'), h = el('h2',title);
    h.id = 'dialog-heading-'+ ++dialogCount; d.setAttribute('aria-labelledby',h.id); d.append(h); document.body.append(d);
    d.addEventListener('close',() => { d.remove(); if (opener?.isConnected) opener.focus(); },{once:true});
    return d;
  }
  function setBusy(value) {
    busy = value;
    for (const b of document.querySelectorAll('button')) b.disabled = value;
    for (const input of $('current').querySelectorAll('input,select,textarea')) input.disabled = value;
    $('message').disabled = false;
    const modelSelect = $('ai-model');
    if (modelSelect && config?.models?.length) modelSelect.disabled = value;
    syncSend();
  }
  function beginPending(words, usingAI) {
    const host = $('pending-turn'); host.replaceChildren(); host.hidden = !usingAI;
    $('status').className = usingAI ? 'chat-status sr-only' : 'chat-status';
    if (!usingAI) return;
    if (words) {
      const user = el('article',undefined,'chat-message chat-user'); user.setAttribute('aria-label','You');
      user.append(el('p',words)); host.append(user);
    }
    // :8894 thinking state: the Daylight mark, three bouncing dots and words.
    // Screen readers get the status line instead; motion stops under reduced motion.
    const typing = el('div',undefined,'chat-message chat-daylight thinking');
    typing.setAttribute('aria-hidden','true');
    const dots = el('span',undefined,'thinking-dots');
    for (let i = 0; i < 3; i++) dots.append(el('span',undefined,'thinking-dot'));
    const line = el('p',undefined,'thinking-line'); line.append(dots,el('span','Daylight is thinking…','thinking-words'));
    typing.append(line);
    host.append(typing);
    clearTimeout(pendingTimer);
    pendingTimer = setTimeout(() => { if (typing.isConnected) typing.append(el('p','Longer answers can take up to half a minute. Your message is safe.','thinking-more')); },10000);
    document.body.classList.add('turn-pending');
    $('send').textContent = 'Sending…';
    $('status').className = 'chat-status sr-only';
    $('reading').scrollTop = $('reading').scrollHeight;
  }
  function endPending() {
    clearTimeout(pendingTimer); document.body.classList.remove('turn-pending'); $('send').textContent = 'Send';
    $('pending-turn').replaceChildren(); $('pending-turn').hidden = true;
    $('status').className = 'chat-status';
  }
  function updateScrollCue() {
    const reading = $('reading'), cue = $('chat-down'), pending = $('pending-turn');
    const bounds = reading.getBoundingClientRect(), pendingBounds = pending.getBoundingClientRect();
    pending.classList.toggle('typing-paused',document.hidden || pendingBounds.bottom <= bounds.top || pendingBounds.top >= bounds.bottom);
    // Hidden whenever the pane is at the bottom (within 40px, which covers the 8px tolerance and the bottom fade).
    cue.hidden = !active || busy || Math.ceil(reading.scrollTop) + reading.clientHeight >= reading.scrollHeight - 40;
    if (cue.hidden) return;
    const nextBelow = q() && $('current').getBoundingClientRect().top > bounds.bottom - 44;
    const label = nextBelow ? 'Go to next question' : 'Go to latest message';
    cue.setAttribute('aria-label',label);cue.title = label;
    const workspace = reading.parentElement.getBoundingClientRect();
    cue.style.setProperty('--chat-down-bottom',Math.max(0,workspace.bottom - bounds.bottom + 10)+'px');
  }
  // After a reply, a reader who was following the conversation should see the
  // next question and its answer buttons, not only the down arrow. Scroll just
  // enough for #current to fit, never past its top, and never when the reader
  // had scrolled up or has moved since this was scheduled.
  function showCurrentQuestion(reading, expectedTop = null) {
    const current = $('current');
    if (!current.childElementCount || (expectedTop !== null && Math.abs(reading.scrollTop - expectedTop) > 2)) return reading.scrollTop;
    const bounds = reading.getBoundingClientRect(), rect = current.getBoundingClientRect();
    const overflow = rect.bottom - (bounds.bottom - 32), room = rect.top - bounds.top - 18;
    if (overflow > 0 && room > 0) reading.scrollTop += Math.min(overflow,room);
    return reading.scrollTop;
  }
  function jumpDown() {
    const reading = $('reading'), bounds = reading.getBoundingClientRect();
    const questionBelow = q() && $('current').getBoundingClientRect().top > bounds.bottom - 44;
    const top = questionBelow ? reading.scrollTop + $('current').getBoundingClientRect().top - bounds.top - 18 : reading.scrollHeight;
    reading.scrollTo({top,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    if (questionBelow) {$('current').setAttribute('tabindex','-1');$('current').focus({preventScroll:true});}
    updateScrollCue();
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
  // Preserve :8891's bounded reveal after the server validates the full reply.
  // Assistive technology receives one complete message, never partial words.
  function paragraph(text, reveal, tag = 'p', cls = '', offset = 0) {
    const p = el(tag, undefined, cls);
    reveal = false; // :8894 — complete text on first paint; no staged word reveal for older readers.
    if (!reveal || matchMedia('(prefers-reduced-motion: reduce)').matches) { p.textContent = text; return p; }
    p.append(el('span', text, 'sr-only'));
    const visible = el('span', undefined, 'assistant-reveal'); visible.setAttribute('aria-hidden', 'true');
    const words = text.match(/\S+\s*|\s+/g) || [];
    words.forEach((word, i) => {
      const span = el('span', word, 'reveal-word');
      span.style.setProperty('--word-delay', offset + Math.min(i * 40, 2000) + 'ms');
      // Leaving chat or changing motion preference can cancel the animation.
      // Retire its class either way so returning cannot restart old words.
      span.onanimationend = span.onanimationcancel = () => { span.className = ''; span.onanimationend = span.onanimationcancel = null; };
      visible.append(span);
    });
    p.append(visible); return p;
  }
  // :8894 — model replies sometimes use simple Markdown (tables, bullet and
  // numbered lists, **bold**). Build real elements from text nodes only; no
  // HTML from the model is ever parsed. Plain prose renders exactly as before.
  function inlineText(node, text) {
    for (const part of String(text).split(/(\*\*[^*\n]+\*\*)/g)) {
      if (/^\*\*[^*\n]+\*\*$/.test(part)) node.append(el('strong', part.slice(2, -2)));
      else if (part) node.append(document.createTextNode(part));
    }
    return node;
  }
  function richReply(text) {
    const lines = String(text).replace(/\r/g, '').split('\n'), host = el('div', undefined, 'reply-body');
    const special = /^(\||[-*•]\s+|\d+[.)]\s+|#{1,6}\s+)/;
    const cells = line => line.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
    const separator = line => /^\|?[\s:|-]+\|?$/.test(line) && line.includes('-');
    let i = 0;
    while (i < lines.length) {
      const line = lines[i].trim();
      if (!line) {i++; continue;}
      if (line.startsWith('|')) {
        const rows = []; while (i < lines.length && lines[i].trim().startsWith('|')) rows.push(lines[i++].trim());
        while (rows.length && separator(rows[0])) rows.shift();
        const data = rows.filter(r => !separator(r)).map(cells), hasHead = (rows.length > 1 && separator(rows[1])) || (data.length > 1 && data[0][0] === '');
        if (!data.length) continue;
        const wrap = el('div', undefined, 'reply-table'), table = el('table');
        if (hasHead) {const tr = el('tr'); data.shift().forEach(c => {const th = inlineText(el('th'), c); th.scope = 'col'; tr.append(th);}); const thead = el('thead'); thead.append(tr); table.append(thead);}
        const tbody = el('tbody');
        for (const row of data) {const tr = el('tr'); row.forEach((c, n) => {const cell = inlineText(el(n ? 'td' : 'th'), c); if (!n) cell.scope = 'row'; tr.append(cell);}); tbody.append(tr);}
        table.append(tbody); wrap.append(table); host.append(wrap); continue;
      }
      const bullet = /^[-*•]\s+/, number = /^\d+[.)]\s+/;
      if (bullet.test(line) || number.test(line)) {
        const pattern = bullet.test(line) ? bullet : number, list = el(pattern === bullet ? 'ul' : 'ol');
        while (i < lines.length && pattern.test(lines[i].trim())) list.append(inlineText(el('li'), lines[i++].trim().replace(pattern, '')));
        host.append(list); continue;
      }
      if (/^#{1,6}\s+/.test(line)) {host.append(inlineText(el('p', undefined, 'reply-heading'), line.replace(/^#{1,6}\s+/, '').replace(/\*\*/g, ''))); i++; continue;}
      const buf = [line]; i++;
      while (i < lines.length && lines[i].trim() && !special.test(lines[i].trim())) buf.push(lines[i++].trim());
      host.append(inlineText(el('p'), buf.join('\n')));
    }
    return host;
  }
  function textDuration(text) { return Math.min(Math.max((text.match(/\S+/g) || []).length - 1,0) * 40,2000) + 120; }
  function revealControl(control, reveal, offset = 0) {
    reveal = false; // :8894 — controls are usable immediately.
    if (!reveal || matchMedia('(prefers-reduced-motion: reduce)').matches) return control;
    const originalClass = control.className;
    control.className += ' reveal-word';
    control.style.setProperty('--word-delay',offset+'ms');
    const finish = () => { control.className = originalClass; control.onanimationend = control.onanimationcancel = control.onfocus = null; };
    control.onanimationend = control.onanimationcancel = control.onfocus = finish;
    return control;
  }
  function questionPresentation(question) {
    const reveal = !revealedQuestions.has(question);
    revealedQuestions.add(question);
    const latest = history.at(-1);
    const lastText = [latest?.reply,...(latest?.facts || []).map(fact => fact.text)].filter(Boolean).join(' ');
    return {reveal,offset:reveal && lastText ? textDuration(lastText) + 100 : 0};
  }
  function presentText(host, text, presentation, tag = 'p', cls = '') {
    host.append(paragraph(text,presentation.reveal,tag,cls,presentation.offset));
    presentation.offset += textDuration(text) + 100;
  }
  function presentControl(control, presentation) {
    const result = revealControl(control,presentation.reveal,presentation.offset);
    presentation.offset += 140;
    return result;
  }
  function renderOpening(host) {
    const reveal = !openingRevealed;
    openingRevealed = true;
    const wordCount = text => (text.match(/\S+/g) || []).length;
    const greeting = history.length === 1 && history[0].reply;
    let offset = greeting ? Math.min(wordCount(greeting) * 40, 2000) + 120 : 0;
    for (const [tag,text,cls] of [
      ['h2',OPENING_QUESTION,''],
      ['p','You can start with something like “I’m retiring soon and don’t know where to begin.”','intro-example'],
      ['p','A sentence or two is enough.','intro-help']
    ]) {
      host.append(paragraph(text,reveal,tag,cls,offset));
      offset += wordCount(text) * 40 + 100;
    }
    return {reveal,offset};
  }
  function factBlock(facts, reveal = false, withSources = true) {
    const host = el('div',undefined,'facts');
    for (const fact of facts || []) {
      host.append(el('h2',fact.title),paragraph(fact.text,reveal));
      const links = [...(fact.source ? [{url:fact.source,label:'Medicare.gov source'}] : []),...(fact.sources || [])];
      const sources = withSources && citationBlock(links);if (sources) host.append(sources);
    }
    return host;
  }
  function citationBlock(links) {
    const unique = new Map();
    for (const link of Array.isArray(links) ? links : []) {
      try {const url = new URL(link.url);if (url.protocol === 'https:' && !unique.has(url.href)) unique.set(url.href,{url,label:link.label || link.title || url.hostname});} catch {}
    }
    if (!unique.size) return null;
    const details = el('details',undefined,'sources');details.append(el('summary','Sources'));
    for (const {url,label} of unique.values()) {const a = el('a',label);a.href = url.href;a.target = '_blank';a.rel = 'noopener noreferrer';details.append(a);}
    return details;
  }
  function turnVisual(result) {
    if (result.generated?.status === 'unavailable') return null;
    if (result.understanding) {
      return result.understanding.state === 'educational'
        ? {kind:'understanding',title:result.understanding.title,guide:result.understanding} : null;
    }
    // Current responses select a guide independently of their citations.
    // An explicit none must also suppress older fact/timeline inference.
    if (result.advisor && Object.prototype.hasOwnProperty.call(result.advisor,'visual')) {
      switch (result.advisor.visual) {
        case 'routes': return {kind:'routes',title:'Two coverage paths',concepts:['original','advantage']};
        case 'original': return {kind:'routes',title:'Original Medicare',concepts:['original']};
        case 'advantage': return {kind:'routes',title:'Medicare Advantage',concepts:['advantage']};
        case 'parts': return {kind:'parts',title:'Parts A and B',concepts:['parta','partb']};
        case 'parta': return {kind:'parts',title:'Part A',concepts:['parta']};
        case 'partb': return {kind:'parts',title:'Part B',concepts:['partb']};
        default: return null;
      }
    }
    // Retain rendering for older fixtures/responses without a visual contract.
    const ids = new Set([...(result.advisor?.teachingFactIds || []),...(result.facts || []).map(fact => fact.id)]);
    if (ids.has('routesintro') || ids.has('options')) return {kind:'routes',title:'Two coverage paths',concepts:['original','advantage']};
    if (ids.has('original') || ids.has('medigap')) return {kind:'routes',title:'Original Medicare',concepts:['original']};
    if (ids.has('advantage')) return {kind:'routes',title:'Medicare Advantage',concepts:['advantage']};
    if (ids.has('parts')) return {kind:'parts',title:'Parts A and B',concepts:['parta','partb']};
    if (ids.has('parta')) return {kind:'parts',title:'Part A',concepts:['parta']};
    if (ids.has('partb')) return {kind:'parts',title:'Part B',concepts:['partb']};
    const assessment = result.assessment, timeline = assessment?.narrative?.visual;
    if ((ids.has('dates') || ids.has('enrollment_intro')) && timeline?.kind === 'timeline'
        && !assessment.nextQuestion && !assessment.conversationOpen && !assessment.intakePaused
        && !['missing_information','education'].includes(assessment.state)) {
      const items = timeline.items.filter(([,value]) => value && !['Not stated','Still open'].includes(value));
      if (items.length >= 2) return {kind:'timeline',title:timeline.title,items};
    }
    return null;
  }
  function inlineGuide(visual, reveal = false, offset = 0, includeTitle = true) {
    if (!visual) return null;
    if (visual.kind === 'understanding') {
      return typeof DaylightUnderstanding === 'undefined' ? null :
        DaylightUnderstanding.render(visual.guide,{reviewDates:reviewDateInformation,explain:concept});
    }
    const host = el('section',undefined,'inline-guide'); host.setAttribute('aria-label',visual.title);
    if (includeTitle) host.append(paragraph(visual.title,reveal,'h3','guide-title',offset));
    if (visual.kind === 'timeline') {
      const list = el('ol',undefined,'timeline');
      for (const [label,value] of visual.items) {
        const row = el('li');row.append(el('span',label),paragraph(readable(value),reveal,'strong','',offset+140));list.append(row);
      }
      host.append(list,paragraph('Your reported timing. Dates and coverage still need checking.',reveal,'p','diagram-caption',offset+240));return host;
    }
    const content = el('div',undefined,'guide-concepts');
    const concepts = visual.kind === 'routes' ? [
      ['original','Original Medicare','Parts A + B · optional separate Part D and Medigap'],
      ['advantage','Medicare Advantage','Parts A + B through a private plan · most include drug coverage']
    ] : [['parta','Part A','Hospital insurance'],['partb','Part B','Medical insurance']];
    for (const [id,title,copy] of concepts.filter(([id]) => visual.concepts.includes(id))) {
      const item = el('div',undefined,'guide-concept');
      const label = button(title,() => concept(id),'text-button guide-concept-link'); label.setAttribute('aria-label','Explain '+title);
      item.append(revealControl(label,reveal,offset+140),paragraph(copy,reveal,'p','guide-description',offset+240));
      content.append(item);
    }
    host.append(content); return host;
  }
  function educationFollowups(prompts) {
    const questions = [...new Set((Array.isArray(prompts) ? prompts : []).filter(text => typeof text === 'string' && text.trim() && text.length <= 120).map(text => text.trim()))].slice(0,2);
    if (!questions.length) return null;
    const details = el('details',undefined,'education-followups');details.append(el('summary','More about this'));
    for (const question of questions) details.append(button(question,() => {
      if (busy) return;
      if ($('message').value.trim()) {note('Your draft is still here. Send or clear it before choosing a question.');$('message').focus();return;}
      $('message').value = question;messageInput();$('message').focus();
    }));
    return details;
  }
  function paintHistory() {
    const host = $('history');
    if (renderedHistory > history.length || firstHistory !== history[0]) {host.replaceChildren();renderedHistory = 0;}
    for (const item of history.slice(renderedHistory)) {
      host.append(exchange(item,!revealedReplies.has(item)));
      revealedReplies.add(item);
    }
    renderedHistory = history.length;firstHistory = history[0];
  }
  function exchange(item, reveal = false) {
    const block = el('div',undefined,'exchange');
    if (item.askedQuestion) {
      const question = el('article',undefined,'chat-message chat-daylight'); question.setAttribute('aria-label','Daylight');
      question.append(paragraph(item.askedQuestion,false)); block.append(question);
    }
    if (item.user) { const user = el('article',undefined,'chat-message chat-user'); user.setAttribute('aria-label','You'); user.append(el('p',item.user)); block.append(user); }
    if (item.reply || item.sources?.length || item.notice) {
      const answer = el('article',undefined,'chat-message chat-daylight'); answer.setAttribute('aria-label','Daylight');
      // A recovery turn leads with its one-line notice ("I couldn't finish that
      // answer…") so the statement that follows reads as the part that stands.
      if (item.notice && item.noticeFirst) answer.append(el('p',item.notice,'chat-small'));
      if (item.reply) answer.append(richReply(item.reply));
      // A server notice (for example a partial answer) stays with its reply in the
      // transcript; the live status line repeats it once for assistive technology.
      if (item.notice && !item.noticeFirst) answer.append(el('p',item.notice,'chat-small'));
      // Conversation prose comes from the model. Prepared lessons, timelines
      // and milestone narration stay out of the chat, including old receipts.
      const followups = educationFollowups(item.educationFollowups);if (followups) answer.append(followups);
      const links = [...(item.sources || []),...(item.visual?.guide?.sources || []),...(item.facts || []).flatMap(fact => [...(fact.source ? [{url:fact.source,label:'Medicare.gov source'}] : []),...(fact.sources || [])])];
      const sources = citationBlock(links);if (sources) answer.append(sources);
      block.append(answer);
    }
    return block;
  }
  function conversationFocus() {
    // Only a positive signal (explicit topic, current question, taught facts or
    // an explicit stage) moves the track. A failed or questionless turn keeps
    // the previous focus instead of jumping to the task fallback.
    if (prepared || review || state.assessment.narrative.focus === 'prepare') return lastFocus = 3;
    if (state.assessment.journey.samplesVisible) return lastFocus = 2;
    if (state.assessment.narrative.opener) return lastFocus = 0;
    const topic = state.advisor?.topic;
    if (topic === 'learning') return lastFocus = 1;
    if (['timing','current_coverage'].includes(topic)) return lastFocus = 0;
    if (['coverage_paths','doctors','drugs','total_cost','bills','travel','flexibility'].includes(topic)) return lastFocus = 2;
    const question = q();
    if (question) {
      if (question.id === 'T02') return lastFocus = 1;
      return lastFocus = ['T06','T07','T08','T09','T10','RC20','RC21','RC22','RC23','RC24','RC25'].includes(question.id) ? 2 : 0;
    }
    const taught = history.at(-1)?.facts || [];
    if (taught.length) return lastFocus = taught.some(fact => ['routesintro','options','original','advantage','medigap','drugbasics','costs'].includes(fact.id)) ? 2 : 1;
    return lastFocus;
  }
  function phaseTrack() {
    const host = $('phases'); host.replaceChildren();
    const focus = conversationFocus(), topics = ['Your situation','Medicare basics','Coverage options','Next steps'], list = el('ol',undefined,'adaptive-phases');
    host.setAttribute('aria-label','Conversation focus: '+topics[focus]);
    topics.forEach((name,i) => { const n = el('li',name); if (i === focus) n.setAttribute('aria-current','true'); list.append(n); });
    const bar = el('progress'); bar.max = 4; bar.value = focus + 1;
    bar.setAttribute('aria-hidden','true'); bar.title = 'Current conversation focus';
    host.append(list,bar);
  }
  function drawReference() {
    const host = $('reference'); host.replaceChildren();
    // Teaching belongs to its explanation in history, never to a later
    // unrelated intake question because a concept was seen earlier.
    host.hidden = true;
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
    } else {
      const fact = state.record.facts[question.id];
      let value = !fact?.stale && fact?.value || {};
      if (question.entity !== 'profile') value = value.items?.find(x => x.entity === question.entity) || {};
      for (const field of question.fields) if (field.type === 'select' && value[field.key] != null) fields[field.key] = value[field.key];
      if (question.id === 'RC18' && value.choice !== 'declined' && Array.isArray(value.programs) && value.programs.length) choice = [...value.programs];
      else if (value.choice) choice = [value.choice];
    }
    // A saved free-text report must not become an invisible selected answer.
    // Existing reports remain in the profile; new details come through chat.
    choice = choice.filter(value => question.choices.some(([id]) => id === value));
    const draft = {fields,choice}; drafts.set(question.signature,draft); return draft;
  }
  function hasFormAnswer(question) {
    if (!question) return false;
    const draft = draftFor(question);
    if (question.max && draft.choice.length > question.max) return false;
    return !!draft.resolution || !!draft.choice.length || Object.values(draft.fields).some(value => String(value).trim());
  }
  function resizeComposer() {
    const input = $('message'), reading = $('reading');
    const atEnd = reading.scrollHeight - reading.clientHeight - reading.scrollTop < 32;
    const minimum = parseFloat(getComputedStyle(input).minHeight) || 80;
    const viewport = window.visualViewport?.height || window.innerHeight;
    const maximum = Math.max(minimum,Math.min(240,Math.floor(viewport * .3)));
    input.style.height = 'auto';
    const height = Math.max(minimum,Math.min(input.scrollHeight,maximum));
    input.style.height = height+'px'; input.style.overflowY = input.scrollHeight > height ? 'auto' : 'hidden';
    if (atEnd) reading.scrollTop = reading.scrollHeight;
    updateScrollCue();
  }
  function messageInput() {
    if (doctorComposer) {
      window.DaylightDoctorCheck.setName($('message').value);
      resizeComposer();syncSend();
      return;
    }
    if ($('message').value.trim()) {
      const question = q(), draft = question && draftFor(question);
      if (selectedGoal || draft && (draft.choice.length || draft.resolution || Object.keys(draft.fields).length || draft.coverageGroup)) {
        selectedGoal = '';
        if (draft) {draft.choice = [];draft.resolution = '';draft.fields = {};draft.coverageGroup = '';}
        renderCurrent();
      }
    }
    resizeComposer(); syncSend();
  }
  function syncSend() {
    const send = $('send'), words = $('message').value.trim(), slot = $('selection');
    if (doctorComposer) {
      send.textContent = 'Continue';
      send.disabled = doctorComposer.busy || !doctorComposer.composer || !words;
      return;
    }
    const selectedAnswer = state?.assessment.narrative.opener ? selectedGoal && selectedGoal !== 'unresolved' : hasFormAnswer(q());
    const contextual = !words && (review || selectedAnswer) && !prepared;
    const target = contextual && slot ? slot : $('composer-input');
    if (send.parentElement !== target) { if (target === slot) target.prepend(send); else target.append(send); }
    send.textContent = busy && document.body.classList.contains('turn-pending') ? 'Sending…' : !words && review ? review.label : 'Send';
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
    if (doctorComposer) {
      if (doctorComposer.composer && words) await window.DaylightDoctorCheck.submitName();
      return;
    }
    if (words && service?.local_demo?.doctor_chat) {
      const named = words.match(/^(?:please\s+)?check\s+(Dr\.?\s+[^\r\n]{1,125})[.!]?$/i);
      if (/^(?:(?:can you|please)\s+)?check\s+(?:a|my)\s+doctor[.!?]?$/i.test(words) || named) {
        openDoctorCheck(named?.[1] || '', true);
        return;
      }
    }
    if (words) { await turn({type:'message',message:words},words); return; }
    if (review) {
      const signature = q()?.signature;
      const action = review.kind === 'plan_profile' ? 'confirm_plan_review' : review.kind === 'preparation' ? 'run_preparation' : 'accept_review';
      const ok = await turn({type:action,token:review.token},review.label);
      if (ok && signature) drafts.delete(signature);
    } else if (state.assessment.narrative.opener && selectedGoal && selectedGoal !== 'unresolved') {
      const goal = selectedGoal;
      const {label} = OPENING_CHOICES[goal];
      if (await turn({type:'choice',id:'T01',fields:{choice:goal}},label,false,{opening:true})) {selectedGoal = '';syncSend();}
    } else if (q()) await submitForm(q());
  }
  function renderForm(host,question,presentation) {
    if (question.conversational) return;
    const draft = draftFor(question), form = el('form',undefined,'task-form'); form.id = 'detail-form';
    if (question.choices.length) {
      const choices = el('div',undefined,'choices'); choices.setAttribute('role','group'); choices.setAttribute('aria-label',question.question);
      const view = insuranceChoiceView(question,draft);
      for (const item of view.items) {
        if (item.group) {
          const b = button(item.label,() => {if (!choiceMayChange()) return;draft.coverageGroup = draft.coverageGroup === item.group ? '' : item.group;draft.resolution = '';renderCurrent();$('current').querySelector('[data-coverage-group="'+item.group+'"]')?.focus({preventScroll:true});},'choice');
          b.setAttribute('data-coverage-group',item.group);b.setAttribute('aria-expanded',String(draft.coverageGroup === item.group));b.setAttribute('aria-controls','insurance-refinement');choices.append(presentControl(b,presentation));
        } else choices.append(answerChoice(question,draft,item.value,item.label,presentation));
      }
      form.append(choices);
      if (view.selected.length) {
        const selected = el('div',undefined,'choices');selected.setAttribute('role','group');selected.setAttribute('aria-label','Selected health insurance');
        for (const [value,label] of view.selected) selected.append(answerChoice(question,draft,value,label,presentation));
        form.append(selected);
      }
      const refinement = el('div');refinement.id = 'insurance-refinement';
      if (view.details.length) {
        presentText(refinement,view.detailLabel,presentation,'p','small');
        const details = el('div',undefined,'choices');details.setAttribute('role','group');details.setAttribute('aria-label',view.detailLabel);
        for (const [value,label] of view.details) details.append(answerChoice(question,draft,value,label,presentation));
        refinement.append(details);
      }
      if (question.id === 'T05') form.append(refinement);
    }
    // Free text belongs in the one chat composer. Only genuine finite options
    // become answer buttons, including any service-owned field options.
    for (const field of question.fields.filter(field => field.type === 'select')) {
      const group = el('div',undefined,'choices'); group.setAttribute('role','group'); group.setAttribute('aria-label',field.label);
      if (question.fields.length > 1) presentText(form,field.label,presentation,'p','small');
      for (const [value,label] of field.options) {
        const b = button(label,() => {
          if (!choiceMayChange()) return;
          if (question.id === 'RC23' && field.key === 'daysSupply' && value === 'other') {
            delete draft.fields[field.key];draft.resolution = '';renderCurrent();
            note('Type the number of days in the message box, for example: a 45-day supply.');$('message').focus({preventScroll:true});return;
          }
          draft.fields[field.key] = draft.fields[field.key] === value ? '' : value;draft.resolution = '';renderCurrent();revealSend();
        },'choice');
        b.setAttribute('aria-pressed',String(draft.fields[field.key] === value));group.append(presentControl(b,presentation));
      }
      form.append(group);
    }
    const actions = el('div',undefined,'choices');
    if (question.clarification?.confirmable) {
      const label = question.clarification.confirmLabel || 'Yes, that’s right';
      const b = button(label,() => {if (!choiceMayChange()) return;void turn({type:'message',message:label+'.'},label,true);},'choice');
      actions.append(presentControl(b,presentation));
    }
    for (const [value,label] of [['unknown','I don’t know'],['defer','Check later']]) {
      const b = button(label,() => {if (!choiceMayChange()) return;draft.resolution = draft.resolution === value ? '' : value;draft.choice = [];draft.fields = {};draft.coverageGroup = '';renderCurrent();revealSend();},'choice');
      b.setAttribute('aria-pressed',String(draft.resolution === value)); actions.append(presentControl(b,presentation));
    }
    form.append(actions); selectionSlot(form,() => {draft.choice = [];draft.resolution = '';draft.fields = {};draft.coverageGroup = '';renderCurrent();});
    form.onsubmit = e => { e.preventDefault(); void submitCurrent(); }; host.append(form);
  }
  function insuranceChoiceLabel(question,value,label) {
    if (question.id !== 'T05') return label;
    return {employer:'Through a current job',retiree:'Retiree health plan',cobra:'COBRA',original:'Original Medicare (Part A, or Parts A and B)',advantage:'Medicare Advantage (Part C)',medigap:'Medicare Supplement / Medigap',drug:'Separate Medicare drug plan',military:'VA, TRICARE or military coverage',medicaid:'Medicaid',none:'No health insurance'}[value] || label;
  }
  function choiceMayChange() {
    if (!$('message').value.trim()) return true;
    note('Your typed message is ready to send. Clear it to choose an answer instead.');
    $('message').focus({preventScroll:true}); return false;
  }
  function insuranceChoiceView(question,draft) {
    const all = question.choices.filter(([value]) => value !== 'unknown').map(([value,label]) => [value,insuranceChoiceLabel(question,value,label)]);
    const complete = {items:all.map(([value,label]) => ({value,label})),details:[],selected:[],detailLabel:''};
    const familiarity = state.guide.fields?.['knowledge.general'];
    if (question.id !== 'T05' || familiarity?.value === 'comfortable' && !['unknown','skipped','stale'].includes(familiarity.status)) return complete;
    const groups = [{group:'former',label:'From a former job',detailLabel:'Which kind of coverage from a former job?',values:['retiree','cobra']},{group:'medicare',label:'Medicare',detailLabel:'Which Medicare coverage is current?',values:['original','advantage','medigap','drug']}];
    const available = new Map(all), items = [];
    for (const value of ['employer','former','medicare','military','medicaid','none']) {
      const group = groups.find(item => item.group === value);
      if (group) {if (group.values.some(id => available.has(id))) items.push(group);}
      else if (available.has(value)) items.push({value,label:available.get(value)});
    }
    const grouped = groups.flatMap(group => group.values), direct = items.filter(item => !item.group).map(item => item.value);
    for (const [value,label] of all) if (!grouped.includes(value) && !direct.includes(value)) items.push({value,label});
    const expanded = groups.find(group => group.group === draft.coverageGroup);
    const details = all.filter(([value]) => expanded?.values.includes(value));
    if (expanded?.group === 'medicare' && question.id === 'T05') details.push(['a_only','Part A only (no Part B yet)']);
    const selected = all.filter(([value]) => grouped.includes(value) && !expanded?.values.includes(value) && draft.choice.includes(value));
    return {items,details,selected,detailLabel:expanded?.detailLabel || ''};
  }
  function answerChoice(question,draft,value,label,presentation) {
    const b = button(label,() => {
      if (!choiceMayChange()) return;
      if (question.id === 'T05' && value === 'a_only') {
        // Part A alone is a statement about the parts held (RC04), told in the
        // person's words; the server records it from this sentence.
        void turn({type:'message',message:'I have Medicare Part A only, not Part B yet.'},label,true);return;
      }
      const exclusive = ['none','no','local','unknown','declined'];
      let next;
      if (question.multi && !exclusive.includes(value)) {
        const current = draft.choice.filter(choice => !exclusive.includes(choice));
        next = current.includes(value) ? current.filter(choice => choice !== value) : [...current,value];
        const maximum = question.max;
        if (maximum && !current.includes(value) && next.length > maximum) {note('Choose up to '+maximum+' priorities. Clear one before adding another.');return;}
      } else next = draft.choice.length === 1 && draft.choice[0] === value ? [] : [value];
      if (question.id === 'T05' && next.includes('advantage') && next.some(choice => ['original','medigap'].includes(choice))) {
        note('Which Medicare coverage is current? If you’re changing plans or aren’t sure, tell Daylight in the message box.');$('message').focus({preventScroll:true});return;
      }
      draft.resolution = '';draft.choice = next;
      if (draft.coverageGroup && !insuranceChoiceView(question,draft).details.some(([id]) => id === value)) draft.coverageGroup = '';
      renderCurrent();revealSend();
    },'choice');
    b.setAttribute('aria-pressed',String(draft.choice.includes(value)));return presentControl(b,presentation);
  }
  async function submitForm(question) {
    if ($('message').value.trim()) {note('Your typed answer is ready to send.');return;}
    const draft = draftFor(question),fields = Object.fromEntries(Object.entries(draft.fields).filter(([,v]) => String(v).trim()).map(([k,v]) => [k,String(v).trim()]));
    if (draft.resolution) { await turn({type:draft.resolution,id:question.id},draft.resolution === 'unknown' ? 'I don’t know' : 'Check later',true); return; }
    if (question.max && draft.choice.length > question.max) {note('Choose up to '+question.max+' priorities, or describe them in your message.');return;}
    if (draft.choice.length) fields.choice = draft.choice.join(',');
    if (question.id === 'T04' && fields.month && !fields.choice) fields.choice = 'month';
    if (question.id === 'T06' && fields.choice === 'none' || question.id === 'T07' && fields.choice === 'no') delete fields.text;
    else if (['T06','T07'].includes(question.id) && fields.text) delete fields.choice;
    if (!Object.keys(fields).length) { note('Add an answer, or choose I don’t know or Check later.'); return; }
    const choiceLabels = (question.choices || []).filter(([id]) => draft.choice.includes(id)).map(([id,label]) => insuranceChoiceLabel(question,id,label));
    const detailWords = question.fields.filter(f => fields[f.key]).map(f => f.label+': '+readable(fields[f.key]));
    await turn({type:question.fields.length ? 'stage' : 'choice',id:question.id,entity:question.entity,fields},[...choiceLabels,...detailWords].join(' · '),true);
  }
  function renderReview(host) {
    if (review.kind === 'plan_profile') {
      host.append(el('h1','Review your info'),el('p','Does this reflect what you want to use to compare plans? You can edit a detail or tell Daylight what to change.'));
      const sheet = el('div',undefined,'review-sheet plan-profile-review');rows(sheet,review.rows,true);host.append(sheet);
      const checks = el('section',undefined,'plan-review-checks');checks.append(el('h2','Still to check'));
      const list = el('ul');
      for (const item of review.readiness.holds) list.append(el('li',item.label));
      checks.append(list,el('p','These are your reported details. Reviewing them keeps the open checks visible when you see plans.','small'));host.append(checks);
      // D138: the fixed pre-enrollment step, with the conversation count as supporting detail.
      const before = el('section',undefined,'plan-review-checks');
      before.append(el('h2','Before you enroll'),el('p','Medicare rules list twelve topics to go over before anyone enrolls in a plan.'+(cmsChecklist ? ` ${cmsChecklist.covered} of ${cmsChecklist.total} have come up in this conversation so far.` : ''),'small'),button('Read the twelve topics',beforeEnroll));
      host.append(before);
      selectionSlot(host);
      host.append(button('Keep talking',() => turn({type:'cancel_plan_review',token:review.token})));
      return;
    }
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
    const opening = state.assessment.narrative.opener && !review && !prepared && !state.comparisonViewOpen;
    const setup = $('chat-prescription-setup');
    if (setup) setup.hidden = !!doctorComposer || state.record.conversation?.task === 'drug_pricing'
      || state.partDProfile?.status === 'ready';
    let openingPresentation;
    $('composer').hidden = !!prepared;
    if (window.DaylightDoctorCheck?.render(host)) {
      $('shortcuts').replaceChildren();
      for (const id of ['back','review','prepare','samples']) $(id).hidden = true;
      $('reference').hidden = true;
      return;
    }
    if (window.DaylightPrescriptionPreview?.render(host)) {
      $('composer').hidden = true;
      if ($('chat-doctor-check')) $('chat-doctor-check').hidden = true;
      return;
    }
    if ($('chat-doctor-check')) $('chat-doctor-check').hidden = false;
    if (prepared) renderPrepared(host);
    else if (review) renderReview(host);
    else if (state.identityViewOpen && typeof DaylightIdentity !== 'undefined') {
      DaylightIdentity.render(host,state.identity,{
        onSearch:item => identityAction('/api/identity/'+(item.kind === 'drug' ? 'drug' : 'provider')+'/search',{itemId:item.id}),
        onSelect:(candidate,view) => candidate.siteLookup
          ? identityAction('/api/identity/provider/search',{itemId:view.itemId,selector:candidate.selector,choiceToken:view.choiceToken})
          : identityAction('/api/identity/confirm',{choiceToken:view.choiceToken,candidateId:candidate.id,confirmed:true}),
        onMore:view => identityAction('/api/identity/'+(state.identity.kind === 'drug_product' ? 'drug' : 'provider')+'/search',{
          itemId:view.itemId,afterOrdinal:view.page.next_after_ordinal,expectedSnapshotId:view.page.snapshot_id,choiceToken:view.choiceToken}),
        onRefresh:itemId => identityAction('/api/identity/view',{itemId}),
        onForget:async itemId => {if(await identityAction('/api/identity/forget',{itemId}))await identityAction('/api/identity/view');},
        onReturn:async () => {state.identityViewOpen=false;state.identity=null;renderCurrent();await reviewComparison();},
      });
    }
    else if (state.comparisonViewOpen && typeof DaylightComparison !== 'undefined') {
      DaylightComparison.render(host,state.comparison,{
        onReturn:() => {
          state.comparisonViewOpen=false;renderCurrent();
          const opener = state.comparison?.educational_preview && $('open-comparison-preview');
          if (opener) opener.focus(); else focusCurrentReview();
        },
        onScenario:openComparisonPreview,
      });
      if (!state.comparison?.educational_preview) {
        if(state.identity?.preparation?.selected_count > 0)host.append(el('p','Source identity selections are retained for this visit. Coverage and reported-detail consistency still need checking.','small'));
        host.append(button('Review medicine and doctor identities',() => identityAction('/api/identity/view')));
      }
    }
    else if (state.assessment.journey.samplesVisible) renderSamples(host);
    else if (opening) {
      openingPresentation = renderOpening(host);
    } else if (state.planReadiness?.canReview && !q() && state.generated?.status !== 'complete') {
      host.append(el('h1','Ready to review your info before we look at plans?'));
    } else if (q() && state.assessment.narrative.focus !== 'prepare') {
      const presentation = questionPresentation(q());
      presentText(host,q().question,presentation,'h1');
      if (q().why && (state.generated?.status !== 'complete' || q().id.startsWith('MG_')
          || state.record?.conversation?.task === 'drug_pricing' && ['RC01','T03','RC02','RC03'].includes(q().id))) presentText(host,q().why,presentation,'p','why');
      renderForm(host,q(),presentation);
      if (service?.local_demo?.doctor_chat && ['T06','RC21'].includes(q().id)) {
        host.append(button('Check a doctor’s office',() => openDoctorCheck()));
      }
      if (state.record.conversation.editing) host.append(button('Return to my current task',() => turn({type:'resume'})));
    } else if (!conversationPaused()) {
      const presentation = questionPresentation(state.assessment);
      presentText(host,'Here’s where we are',presentation,'h1');
      if (state.assessment.journey.summary) presentText(host,state.assessment.journey.summary,presentation);
      const unresolved = state.assessment.unresolvedReportedInputs;
      if (unresolved.length) { const details = el('details'); details.append(presentControl(el('summary','Details still open'),presentation)); for (const item of unresolved) details.append(el('p',item.label+' — '+readable(item.state))); host.append(details); }
      const topics = el('div',undefined,'topic-actions');
      for (const [id,label] of [['basics','What Medicare is'],['parts','Parts A and B'],['routesintro','The two coverage paths'],['drugbasics','Prescription coverage'],['costs','How costs work']]) topics.append(presentControl(button(label,() => concept(id,label)),presentation));
      host.append(topics,presentControl(button('Review your profile',reviewInformation),presentation),presentControl(button('Prepare my next steps',() => turn({type:'review_preparation'}),'primary'),presentation),presentControl(button('Browse sample plans',() => turn({type:'next',step:'samples'})),presentation));
      if (state.comparison) host.append(presentControl(button('Review comparison preparation',reviewComparison),presentation));
    }
    // D138: when the details a tab needs are complete, the conversation
    // offers the way to it. The listed amounts stay on the tab.
    if (!review && !prepared && !state.comparisonViewOpen && !state.identityViewOpen
        && typeof DaylightPlans !== 'undefined' && DaylightPlans.openView) {
      const task = state.record.conversation?.task;
      if (task === 'medigap' && state.medigapProfile?.status === 'ready')
        host.append(button('See your Medigap prices',() => DaylightPlans.openView('supplement')));
      if (['medigap','drug_pricing'].includes(task) && state.partDProfile?.status === 'ready')
        host.append(button('See your Part D drug plans',() => DaylightPlans.openView('part-d')));
      if (!opening && window.DaylightPrescriptionPreview && state.partDProfile?.status === 'ready')
        host.append(button('Check fictional drug costs',() => openPrescriptionPreview()));
    }
    if (state.planReadiness?.canReview && !review && !prepared && !state.comparisonViewOpen
        && !state.identityViewOpen && !state.record.conversation.editing && !state.assessment.journey.samplesVisible) {
      const action = button('Review your info',() => turn({type:'review_plans'}),'primary');
      action.id = 'review-plan-info';host.append(action);
      if (state.plansHandoff) host.append(button('See plans',async () => {
        if (await turn({type:'get_plan_handoff',token:state.plansHandoff.token})) await openPlansWorkspace();
      }));
    }
    if (config?.comparisonPreview && !review && !prepared && !state.comparisonViewOpen
        && !state.identityViewOpen && !state.assessment.journey.samplesVisible) {
      const preview = button('See 2026 plan comparison',() => openComparisonPreview(3));
      preview.id = 'open-comparison-preview';host.append(preview);
    }
    $('message-label').textContent = 'Type an answer or ask a question';
    $('message').placeholder = opening ? 'Start wherever you like…' : composerHint(q());
    $('restore-draft').hidden = !parkedMessages.length;
    $('shortcuts').replaceChildren();
    if (opening) {
      presentText($('shortcuts'),'Need a starting point?',openingPresentation,'p','small'); const row = el('div',undefined,'shortcut-row');
      const choices = [...Object.entries(OPENING_CHOICES), ['unresolved',{label:'Something else'}]];
      for (const [id,{label}] of choices) { const b = button(label,() => { if (!choiceMayChange()) return;selectedGoal = selectedGoal === id ? '' : id; renderCurrent(); revealSend(); if (id === 'unresolved') $('message').focus(); },'shortcut'); b.setAttribute('aria-pressed',String(selectedGoal === id)); row.append(presentControl(b,openingPresentation)); }
      $('shortcuts').append(row);
      selectionSlot($('shortcuts'),() => {selectedGoal = '';renderCurrent();});
    }
    // Corrections stay conversational; profile inspection and preparation are
    // offered with the final summary rather than on every intake turn.
    for (const id of ['back','review','prepare','samples']) $(id).hidden = true;
    drawReference(); setBusy(busy);
  }
  function conversationPaused() {
    if (generationUnavailable(state) && !q()) return true;
    if (state.assessment.narrative.focus === 'prepare') return false;
    return state.assessment.intakePaused || state.assessment.conversationOpen || !q() && ['missing_information','education'].includes(state.assessment.state);
  }
  function focusCurrentReview() {
    const reading=$('reading'),current=$('current');
    reading.scrollTop += current.getBoundingClientRect().top - reading.getBoundingClientRect().top - 18;
    current.setAttribute('tabindex','-1');current.focus({preventScroll:true});updateScrollCue();
  }
  function openDoctorCheck(name = '', consumed = false) {
    if (!active || busy || !service?.local_demo?.doctor_chat || !window.DaylightDoctorCheck || doctorComposer) return;
    doctorDraft = consumed ? '' : $('message').value;
    $('chat-doctor-check').hidden = true;
    if ($('chat-prescription-rehearsal')) $('chat-prescription-rehearsal').hidden = true;
    window.DaylightDoctorCheck.open({initialName:name, onExit:() => closeDoctorCheck(), onView:view => {
      doctorComposer = view;
      $('composer').hidden = !view.composer;
      $('message-label').textContent = 'Doctor’s name';
      $('message').placeholder = 'Type your doctor’s name…';
      $('message').value = view.composer ? view.name : '';
      $('message').disabled = view.busy;
      $('restore-draft').hidden = $('resume').hidden = true;
      syncSend();
      if (view.composer) resizeComposer();
      if (view.focus) {
        focusCurrentReview();
        if (view.composer) $('message').focus({preventScroll:true});
      }
    }});
    renderCurrent();
    showCurrentQuestion($('reading'));
    $('message').focus();
    if (name) void window.DaylightDoctorCheck.submitName();
  }
  function closeDoctorCheck(repaint = true) {
    if (!doctorComposer) return;
    window.DaylightDoctorCheck.close();
    doctorComposer = null;
    $('message').disabled = false;
    $('message').value = doctorDraft;
    doctorDraft = '';
    $('chat-doctor-check').hidden = false;
    if ($('chat-prescription-rehearsal')) $('chat-prescription-rehearsal').hidden = false;
    if (repaint) {
      render();
      $('message').focus();
    }
  }
  async function reviewComparison() {
    if (busy) return;
    if (state.sessionRebindRequired) {try {await refreshVisitAuthority();} catch(error) {note(error.message);return;}}
    setBusy(true);note('Preparing your comparison view…');
    try {
      const result=await api('/api/comparison/journey',{guide:state.guide,record:state.record,requestId:crypto.randomUUID(),...(state.continuation ? {continuation:state.continuation} : {})});
      DaylightComparison.acceptReview(state,result);
      if(result.identity) {DaylightIdentity.accept(state,result);state.identityViewOpen=false;}
      renderCurrent();focusCurrentReview();note('');
    } catch(error) {note(error.message);}
    finally {setBusy(false);}
  }
  async function openComparisonPreview(days) {
    if (busy || !config?.comparisonPreview) return;
    if (!state.continuation && !await turn({type:'start'})) return;
    if (state.sessionRebindRequired) {
      try {await refreshVisitAuthority();} catch(error) {note(error.message);return;}
    }
    const editing = state.comparisonViewOpen;
    setBusy(true);note('Updating the plan comparison…');
    try {
      const result = await api('/api/comparison/review',{
        guide:state.guide,record:state.record,continuation:state.continuation,
        requestId:crypto.randomUUID(),preview_days:days,
      });
      if (result.comparison?.educational_preview?.state !== 'local_fixture_only') {
        throw Error('The comparison preview is unavailable.');
      }
      DaylightComparison.acceptReview(state,result);
      renderCurrent();
      note(editing ? 'Hospital example updated to '+days+' covered days.' : '');
    } catch(error) {
      if (editing && (error.code === 409 || error.code === 422)) {
        state.comparisonViewOpen=false;renderCurrent();
      }
      note(error.message);
    } finally {
      setBusy(false);
      if (state.comparisonViewOpen && editing) $('comparison-stay-change')?.focus();
      else if (state.comparisonViewOpen) focusCurrentReview();
      else $('open-comparison-preview')?.focus();
    }
  }
  async function identityAction(path,extra={}) {
    if (!busy && state.sessionRebindRequired) {try {await refreshVisitAuthority();} catch(error) {note(error.message);return false;}}
    if(busy || !state.continuation)return false;
    const continuation=state.continuation;
    setBusy(true);note('Checking identity preparation…');
    try {
      const result=await api(path,{guide:state.guide,record:state.record,continuation,
        requestId:crypto.randomUUID(),...extra});
      if(state.continuation !== continuation)throw Error('Your conversation changed. Review its latest state.');
      DaylightIdentity.accept(state,result);renderCurrent();focusCurrentReview();note('');return true;
    } catch(error) {
      // Drop old source labels and opaque choices after any failed recheck.
      // Own reported details, drafts and current conversation remain intact.
      if(state.identity)state.identity={capability:{state:'held',audience:'consumer'},
        items:state.identity.items || [],candidates:[]};
      renderCurrent();focusCurrentReview();note(error.message);return false;
    } finally {setBusy(false);}
  }
  function composerHint(question) {
    if (!question) return 'Ask a question or tell me anything else…';
    if (question.id === 'T04') return 'A month and year, or as soon as possible…';
    if (question.id === 'T03' || question.id === 'RC02') return 'Type the home ZIP code…';
    if (question.id === 'RC11') return 'Tell me any job or insurance end dates you know…';
    if (['T06','RC21'].includes(question.id)) return 'Type the doctor or practice and location…';
    if (['T07','RC22','RC23'].includes(question.id)) return 'Tell me the prescription details you know…';
    return 'Type your answer or ask a question…';
  }
  function openPrescriptionPreview(plan) {
    if (!window.DaylightPrescriptionPreview || !state.continuation || busy) return false;
    window.DaylightPlans?.close('current');
    window.DaylightPrescriptionPreview.open(plan, api, () => state.continuation, () => {
      window.DaylightPrescriptionPreview.close();
      renderCurrent();
      $('message').focus();
    }, state.partDProfile?.inputs);
    renderCurrent();
    showCurrentQuestion($('reading'));
    return true;
  }
  function renderPrepared(host) {
    const panel = el('section',undefined,'prepared');panel.append(el('h1','Your next steps, ready to use'),el('p','Edit this checklist, then copy or print it. Nothing has been sent.'));
    if (prepared.guideRevision !== state.guide.stateVersion || prepared.recordRevision !== state.record.stateVersion) panel.append(el('p','Your details have changed since this was prepared. Review the checklist before using it.','notice'));
    const label = el('label','Your editable checklist'); label.htmlFor = 'prepared-text'; const text = el('textarea');text.id = 'prepared-text';text.value = prepared.text;text.oninput = () => { prepared.text = text.value; };
    const print = el('pre',prepared.text,'print-output'); print.hidden = true;
    const actions = el('div',undefined,'task-actions');actions.append(button('Copy checklist',async () => { try { await navigator.clipboard.writeText(prepared.text); note('Checklist copied.'); } catch { text.focus();text.select();note('Select and copy the checklist text.'); } },'primary'),button('Print',() => { print.textContent = prepared.text;window.print(); },'secondary'),button('Return to my conversation',() => { prepared = null;renderCurrent(); }));
    panel.append(label,text,actions,el('p','Prepared from your reports. Personal coverage checks remain open.','small'),print);host.append(panel);
  }
  function render() {
    document.body.classList.toggle('chat-mode',active);
    const visitAvailable = !!visitResume?.read();
    $('start').textContent = conversationStarted || visitAvailable ? 'Continue the conversation' : 'Get started';
    phaseTrack();paintHistory();renderCurrent();
    $('save-status').textContent = saveText;$('save-status').hidden = saveText === 'Visit only';
    $('resume').hidden = !session.hasSaved || visitAvailable;
    $('landing-resume').hidden = !session.hasSaved;
    $('landing-resume').textContent = visitAvailable ? 'Visit options' : 'Resume saved information';
    if(active && !$('composer').hidden) resizeComposer();
  }
  function showConversation(focus = true) {
    conversationStarted = active = true;
    $('landing').hidden = true;$('workspace').hidden = false;
    render();window.scrollTo({top:0,behavior:'instant'});
    if (focus) $('workspace').focus({preventScroll:true});
  }
  function showHome() {
    closeDoctorCheck(false);
    if (document.body.classList.contains('plans-page')) window.DaylightPlans?.close();
    conversationScroll = $('reading').scrollTop;
    active = false;$('workspace').hidden = true;$('landing').hidden = false;
    render();window.scrollTo({top:0,behavior:'instant'});$('start').focus({preventScroll:true});
  }
  function turnCandidate(action,deliberateAnswer = false) {
    const sendingToAI = action.type === 'message' || deliberateAnswer && ['choice','stage','unknown','defer'].includes(action.type);
    const model = sendingToAI && config.models?.find(item => item.available && item.id === $('ai-model')?.value);
    const plansContext = action.type === 'message' && typeof DaylightPlans !== 'undefined' ? DaylightPlans.snapshot() : null;
    return {guide:clone(state.guide),record:clone(state.record),action,
      aiConsent:sendingToAI,contextPolicy:sendingToAI ? 'natural-context-v3' : null,
      ...(plansContext ? {plansContext,plansContextPolicy:'plans-context-v1'} : {}),
      ...(model ? {model:model.id,aiProvider:model.provider} : {}),
      ...(state.continuation ? {continuation:state.continuation} : {})};
  }
  async function requestConversationTurn(payload) {
    visitResume?.write(payload.requestId, state.guide.preferences, true);
    try {
      const result = await api('/api/conversation/turn',payload);
      visitResume?.write(payload.requestId, result.guide.preferences);
      return result;
    }
    catch (error) {
      if (error.code && !['conversation_state','conversation_busy'].includes(error.recovery)) throw error;
      // These are free receipt/state reads, never retries of a paid action.
      note('Reconnecting to your conversation…');
      try {
        for (let attempt = 0; attempt < 20; attempt++) {
          const recovered = await api('/api/conversation/recover',payload);
          if (recovered.status === 'completed' && recovered.response?.continuation) {
            visitResume?.write(payload.requestId, recovered.response.guide.preferences);
            return recovered.response;
          }
          if (['resumed','reset'].includes(recovered.status) && recovered.response?.continuation) {
            if (recovered.requestId) visitResume?.write(recovered.requestId, recovered.response.guide.preferences);
            error.recoveredState = recovered.response;error.recoveredStatus = recovered.status;
            error.recoveredRequestId = recovered.requestId;
            error.message = recovered.status === 'reset'
              ? 'We’ve reconnected. Your details are still here. Send your message when you’re ready.'
              : 'You’re back at the latest reply. Review it, then send your message when you’re ready.';
            throw error;
          }
          if (recovered.status !== 'working') throw Error('Recovery did not return a current conversation.');
          if (attempt < 19) await new Promise(resolve => setTimeout(resolve,1500));
        }
        error.message = 'Daylight is still working on your message. Send again to check for its reply.';
        error.checkAgain = true;
      } catch (recoveryError) {
        if (error.recoveredState) throw error;
        if (recoveryError.code === 401) throw recoveryError;
        error.message = 'Daylight couldn’t reconnect just now. Your message is here; try Send again shortly.';
      }
      throw error;
    }
  }
  function generationUnavailable(view) { return view.generated?.status === 'unavailable'; }
  async function openPlansWorkspace() {
    const handoff = state.plansHandoff;
    if (!handoff) return;
    try {
      const opened = typeof DaylightPlansHandoff !== 'undefined' && await DaylightPlansHandoff.open(handoff);
      if (!opened) note('Your information is ready. The plans workspace is not connected yet; you can keep talking or review your info.');
    } catch {
      note('Your reviewed information is kept. The plans workspace could not open; try See plans again.');
    }
  }
  function generationNotice(view) { return generationUnavailable(view) ? plain(view.notice || view.reply || '') : ''; }
  function usableQuestion(view) {
    const question = view.assessment.nextQuestion, text = question?.question;
    if (typeof text !== 'string' || !text.trim()) return null;
    // An error notice belongs in status, never in an archived/current question.
    return generationUnavailable(view) && text.trim() === generationNotice(view).trim() ? null : question;
  }
  function visibleQuestion(view = state, reviewing = review, preparing = prepared) {
    if (reviewing || preparing || view.assessment.journey?.samplesVisible) return '';
    const narrative = view.assessment.narrative || {};
    if (narrative.opener) return OPENING_QUESTION;
    return narrative.focus === 'prepare' ? '' : usableQuestion(view)?.question || '';
  }
  function appendTurnHistory(requestId, askedQuestion, userWords, result, previous = null) {
    // A recovery turn (advisor.reason === 'recovery') carries one reviewed
    // statement that must stay visible even though generation was unavailable.
    const recovery = result.advisor?.reason === 'recovery';
    const opening = result.openingChoice ? OPENING_CHOICES[result.openingChoice] : null;
    const reply = opening?.reply || (generationUnavailable(result) && !recovery ? '' : result.reply || '');
    userWords ||= opening?.label || '';
    const sources = generationUnavailable(result) && !recovery ? [] : result.advisor?.sources || [];
    const notice = typeof result.notice === 'string' ? plain(result.notice.trim()) : '';
    const appended = !!(userWords || reply || result.facts?.length || sources.length || notice);
    if (appended && !history.some(item => item.requestId === requestId)) {
      const artifacts = typeof DaylightVisitArtifacts !== 'undefined' ? DaylightVisitArtifacts : null;
      history.push({requestId,askedQuestion,user:userWords,reply,notice,noticeFirst:recovery,facts:result.facts || [],sources,visual:turnVisual(result),educationFollowups:generationUnavailable(result) ? [] : result.advisor?.educationFollowups || [],
        reportedDates:artifacts?.timelineFor(previous,result) || [],
        comparisonMilestone:artifacts?.comparisonMilestone(previous,result) || false});
    }
    return appended;
  }
  async function turn(action, userWords = '', deliberateAnswer = false, options = {}) {
    // Plans-page saves are the person's own entries: saved quietly, never shown
    // as chat turns and never moving focus to the chat (Nov 9, 2026). The next
    // chat reply acknowledges them once.
    const silent = !!options.silent;
    if (busy) return false;
    closeDoctorCheck();
    if (state.sessionRebindRequired) {try {await refreshVisitAuthority();} catch(error) {note(error.message+' Your current visit and draft are preserved.');return false;}}
    if (['accept_review','review_preparation','run_preparation','review_plans','confirm_plan_review','get_plan_handoff'].includes(action.type) && $('message').value.trim()) {note('Send or clear your unsent message before confirming this step. Your draft is still here.');return false;}
    const before = state, previous = q(), fromReview = review, previousQuestion = visibleQuestion();
    const candidate = turnCandidate(action,deliberateAnswer);
    // After a lost response, checking the same request retrieves its resolved
    // state rather than extracting/applying a second time.
    const prior = failedRequest && {...failedRequest};if(prior) delete prior.requestId;
    const payload = prior && JSON.stringify(prior) === JSON.stringify(candidate) ? failedRequest : {...candidate,requestId:crypto.randomUUID()};
    const submittedDraft = action.type === 'message' && $('message').value.trim() === userWords.trim() ? $('message').value : '';
    const pane = $('reading'), following = pane.scrollHeight - pane.clientHeight - pane.scrollTop < 120;
    if (submittedDraft) {$('message').value = '';resizeComposer();}
    const showingPending = candidate.aiConsent || options.opening === true;
    const openingStarted = options.opening ? performance.now() : 0;
    lastRequest = payload;setBusy(true);beginPending(silent ? '' : userWords,showingPending);note(silent ? 'Saving…' : showingPending ? 'Daylight is preparing a reply.' : 'Working…');
    updateScrollCue();
    let pending = true;
    try {
      const result = await requestConversationTurn(payload);
      if (options.opening && !result.openingChoice && result.guide.fields?.['intent.goal']?.value === action.fields.choice) {
        result.openingChoice = action.fields.choice;
      }
      failedRequest = null;
      state = result;review = result.review || null;prepared = result.preparation || null;
      if (review?.kind === 'interpretation' && userWords) reviewMessage = userWords;
      if (prepared) preparedVersions.push(prepared);
      if (!silent && previous && !previous.conversational && q()?.signature !== previous.signature && !['edit','resume'].includes(action.type)) frames.push(previous.id);
      // Move a question into the transcript only when a successful turn has
      // answered or displaced it. Renders and failed sends leave it current.
      const askedQuestion = (userWords || previousQuestion !== visibleQuestion()) ? previousQuestion : '';
      const appended = silent ? false : appendTurnHistory(payload.requestId,askedQuestion,userWords,result,before);
      if (action.type === 'message') selectedGoal = '';
      if (action.type === 'discard_review' && fromReview?.kind === 'interpretation' && !$('message').value.trim()) $('message').value = reviewMessage;
      if (action.type === 'accept_review') reviewMessage = '';
      metrics.turns++;metrics.llmCalls += result.metrics?.llmCalls || 0;
      if (options.opening) {
        const remaining = OPENING_REPLY_DELAY - (performance.now() - openingStarted);
        if (remaining > 0) await new Promise(resolve => setTimeout(resolve,remaining));
      }
      endPending();pending = false;note(silent ? '' : generationNotice(result));render();
      const saving = state.guide.preferences.saveGuide && !review ? save().catch(error => {
        note([silent ? '' : generationNotice(result),error.message+' Your current visit is still here.'].filter(Boolean).join(' '));
      }) : null;
      if (result.cmsChecklist) cmsChecklist = result.cmsChecklist; // D138: keep the latest account for the review.
      if (typeof DaylightPlans !== 'undefined') DaylightPlans.afterTurn(result);
      if (silent) {await saving;return true;}
      if (fromReview && fromReview.kind!=='preparation' && !review && action.type === 'discard_review') note('Your draft is still here. Make edits and continue when ready.');
      const last = appended && $('history').lastElementChild;
      const latestReply = last && (last.querySelector('.chat-daylight:last-child') || last.querySelector('.chat-daylight'));
      const target = last ? (action.type === 'read_concept' ? latestReply : last.querySelector('.chat-user') || latestReply) || last : $('current');
      const reading = $('reading');
      // Scroll the transcript only; the submitted answer stays in view above the reply.
      if (target) reading.scrollTop += target.getBoundingClientRect().top - reading.getBoundingClientRect().top - 18;
      target?.setAttribute('tabindex','-1');target?.focus({preventScroll:true});
      if (following && q()) {
        const shown = showCurrentQuestion(reading);
        const settle = textDuration([history.at(-1)?.reply,...(history.at(-1)?.facts || []).map(fact => fact.text)].filter(Boolean).join(' ')) + 400;
        setTimeout(() => {showCurrentQuestion(reading,shown);updateScrollCue();},settle);
      }
      if (action.type === 'confirm_plan_review' && result.plansHandoff) await openPlansWorkspace();
      await saving;
      return true;
    } catch (error) {
      if (!error.code || error.checkAgain) failedRequest = payload;
      state = error.recoveredState || before;review = error.recoveredState ? null : fromReview;
      if (error.recoveredState) {
        prepared = null;failedRequest = lastRequest = null;selectedGoal = '';
        frames = [];drafts.clear();selected = [];currentSignature = '';
        if (error.recoveredStatus === 'resumed' && error.recoveredRequestId) {
          // Display the actual latest server reply without claiming this draft
          // was accepted or relabeling its original question/user message.
          appendTurnHistory(error.recoveredRequestId,'','',state);
        }
      }
      if (error.code === 401) {
        state.sessionRebindPresentation = clone(state.assessment);
        state.sessionRebindRequired = true;delete state.continuation;
        state.guide.preferences.saveGuide = state.guide.preferences.saveSensitive = false;
        pendingSave = null;review = prepared = null;failedRequest = lastRequest = null;
        saveText = 'Session changed · saving paused';
        try {await refreshVisitAuthority();error.message = 'We’ve reconnected. Saving is paused; your message is ready to send.';}
        catch (_) {error.message = 'Daylight couldn’t reconnect just now. Your message is here; try Send again shortly.';}
      }
      if (submittedDraft && !$('message').value.trim()) $('message').value = submittedDraft;
      else if (submittedDraft && $('message').value !== submittedDraft && !parkedMessages.includes(submittedDraft)) parkedMessages.push(submittedDraft);
      $('restore-draft').hidden = !parkedMessages.length;
      if (error.recoveredState || error.code === 401) render();
      note(error.message+(parkedMessages.includes(submittedDraft) ? ' Your earlier message is available in Restore draft. Your current input is preserved.' : ' Your input is preserved.'));return false;
    }
    finally {if (pending) endPending();setBusy(false);resizeComposer();}
  }
  function concept(id, label = id) {
    if (busy) return;
    if ($('message').value.trim()) {note('Your draft is still here. Send or clear it before choosing a question.');$('message').focus();return;}
    $('message').value = 'Can you explain '+label+'?';messageInput();$('message').focus();
  }
  async function save() {
    if (pendingSave) throw Error('An earlier save needs checking. Open privacy to check the saved copy.');
    pendingSave = clone({guide:state.guide,record:state.record,expectedVersion:savedVersion,expectedReadinessVersion:readinessVersion,operationId:crypto.randomUUID()});
    await completeSave();
  }
  async function completeSave() {
    if (!pendingSave) throw Error('There is no pending save to check.');
    if (!state.guide.preferences.saveGuide || pendingSave.guide.preferences.saveSensitive !== state.guide.preferences.saveSensitive) throw Error('Privacy choices changed. Apply them to check the saved copy before saving again.');
    try { const result = await api('/api/conversation/save',pendingSave);savedVersion = result.version;readinessVersion = result.readinessVersion;session.hasSaved = true;saveText = result.omittedSensitive ? 'Saved · sensitive details omitted' : 'Saved in this browser';pendingSave = null; }
    catch (error) {saveText = 'Not saved — '+error.message;throw error;}
    finally {$('save-status').textContent = saveText;$('save-status').hidden = saveText === 'Visit only';}
  }
  async function reconcilePendingSave() {
    // A lost response does not prove that a save failed. Inspect both saved
    // versions rather than replaying a payload with earlier privacy choices.
    const [saved,readiness] = await Promise.all([api('/api/guest/profile'),api('/api/guest/readiness')]);
    if (!Number.isInteger(saved.version) || !Number.isInteger(readiness.version)) throw Error('The saved copy could not be checked. Your current visit is preserved.');
    savedVersion = saved.version;readinessVersion = readiness.version;
    session.hasSaved = !!saved.guide;pendingSave = null;
    saveText = session.hasSaved ? 'Saved copy checked · current changes not saved' : 'Visit only';
  }
  async function refreshVisitAuthority() {
    const uncertainDelete = !!state.deletionUncertain, previousCSRF = session?.csrf;
    const presentation = state.sessionRebindPresentation;
    session = await api('/api/guest/session');
    if (uncertainDelete || session.csrf !== previousCSRF) {
      const [saved,readiness] = await Promise.all([api('/api/guest/profile'),api('/api/guest/readiness')]);
      if (!Number.isInteger(saved.version) || !Number.isInteger(readiness.version)) throw Error('The saved copy could not be checked. Your current visit is preserved.');
      savedVersion = saved.version;readinessVersion = readiness.version;session.hasSaved = !!saved.guide;
      if (uncertainDelete) saveText = session.hasSaved ? 'Saved copy remains · deletion not confirmed' : 'No saved copy found · saving paused';
    }
    const result = await api('/api/conversation/turn',{guide:clone(state.guide),record:clone(state.record),action:{type:'refresh'},requestId:crypto.randomUUID()});
    // Retain the current screen while the owner changes. This is presentation
    // only: no old dialogue, pause memory, tokens or authority is transferred.
    if (presentation?.intakePaused || presentation?.conversationOpen && !presentation.nextQuestion) {
      result.assessment.nextQuestion = null;result.assessment.intakePaused = !!presentation.intakePaused;
      result.assessment.conversationOpen = !!presentation.conversationOpen;
      if (result.assessment.narrative) result.assessment.narrative.opener = false;
    } else if (presentation?.nextQuestion?.signature && presentation.nextQuestion.signature === result.assessment.nextQuestion?.signature) {
      result.assessment.nextQuestion = clone(presentation.nextQuestion);
    }
    state = result;review = prepared = null;
    // A refreshed owner has no authority to reuse the prior owner's action,
    // identity or failed-request tokens. Composer/history/form drafts stay local.
    failedRequest = lastRequest = null;
  }
  async function deleteSavedInformation() {
    if (busy) return false;
    const presentation = clone(state.assessment);
    setBusy(true);
    visitResume?.clear();
    try {
      try {await api('/api/guest/profile',{expectedVersion:savedVersion,confirmed:true},'DELETE');}
      catch(error) {
        if (!error.code) {
          // A lost response is an unknown outcome, not a confirmed rejection.
          // Do not reuse the possibly revoked owner or retry the deletion.
          pendingSave = null;state.guide.preferences.saveGuide = state.guide.preferences.saveSensitive = false;
          delete state.continuation;delete state.identity;delete state.comparison;
          state.identityViewOpen = state.comparisonViewOpen = false;
          state.sessionRebindRequired = state.deletionUncertain = true;
          state.sessionRebindPresentation = presentation;
          review = prepared = null;failedRequest = lastRequest = null;
          saveText = 'Deletion needs checking · saving paused';
        }
        throw error;
      }
      savedVersion = readinessVersion = 0;pendingSave = null;
      session.hasSaved = false;
      state.guide.preferences.saveGuide = false;state.guide.preferences.saveSensitive = false;
      delete state.continuation;delete state.identity;delete state.comparison;
      state.identityViewOpen = state.comparisonViewOpen = false;state.sessionRebindRequired = true;
      state.sessionRebindPresentation = presentation;
      review = prepared = null;failedRequest = lastRequest = null;saveText = 'Visit only';
      await refreshVisitAuthority();
      return true;
    } finally {setBusy(false);render();}
  }
  function reviewDateInformation() {
    const d = dialog('Dates you’ve shared');
    d.append(el('p','These are your current reported dates. A preferred start is not a confirmed coverage date.'));
    const dates = typeof DaylightVisitArtifacts !== 'undefined' ? DaylightVisitArtifacts.reportedDates(state) : [];
    rows(d,dates,true);
    if (!dates.length) d.append(el('p','No current dates to display. You can tell Daylight any correction in the conversation.'));
    d.append(button('Return to my conversation',() => d.close(),'primary'));d.showModal();
  }
  function reviewInformation() {
    const d = dialog('Your reported information');d.append(el('p','These are your reports, not verified coverage. To change anything, close this and tell Daylight.'));
    rows(d,state.reportedRows || []);
    if (preparedVersions.length) {
      d.append(el('h3','Prepared checklists'));
      preparedVersions.forEach((version,i) => d.append(button('Open checklist '+(i+1),() => { prepared = version;review = null;d.close();renderCurrent(); })));
    }
    const preference = el('label','Explanation preference'),select = el('select');select.setAttribute('aria-label','Explanation preference');select.append(new Option('Choose if you like',''),new Option('New to Medicare — more explanation','new'),new Option('I know some basics','some'),new Option('Keep it brief','comfortable'));select.value = state.guide.fields['knowledge.general']?.value || '';select.onchange = async () => {if(select.value){d.close();await turn({type:'explanation_preference',value:select.value});}};preference.append(select);d.append(preference,button('Close',() => d.close(),'secondary'));d.showModal();
  }
  function privacy() {
    const d = dialog('Your information & privacy');
    d.append(el('p','When you send a question or answer for an AI reply, Daylight shares it, recent conversation and relevant profile details with '+(config?.models?.find(m => m.id === $('ai-model')?.value)?.provider || 'the AI provider')+'. On the Plans page, an AI message also shares the plans you are viewing. The first three starting options and browsing plans work without AI. Saving your profile is a separate choice.'),el('p','Refreshing this tab can reopen your conversation and reported details while this visit is available. Unsent drafts stay on this page. Optional profile saving keeps the reported details you choose for '+(session.retentionDays || 7)+' days from session creation. Anyone sharing this browser may reopen those reports. Conversation and drafts stay out of the saved profile.'));
    const saving = el('label'),saveBox = el('input');saveBox.type = 'checkbox';saveBox.checked = state.guide.preferences.saveGuide;saving.append(saveBox,document.createTextNode('Save my reported information in this browser'));
    const sensitive = el('label'),sensitiveBox = el('input');sensitiveBox.type = 'checkbox';sensitiveBox.checked = state.guide.preferences.saveSensitive;sensitive.append(sensitiveBox,document.createTextNode('Also save sensitive details, such as birthday timing, work status, doctors and prescriptions'));
    d.append(saving,sensitive,button('Apply privacy choices',async () => {state.guide.preferences.saveGuide = saveBox.checked;state.guide.preferences.saveSensitive = sensitiveBox.checked;visitResume?.preferences(state.guide.preferences);try {if (state.sessionRebindRequired) await refreshVisitAuthority();if (pendingSave) await reconcilePendingSave();if (saveBox.checked) await save();else saveText = session.hasSaved ? 'Saving paused · saved copy remains until deleted or expired' : 'Visit only';d.close();render();}catch(error){d.append(el('p',error.message));}},'primary'));
    if (pendingSave) d.append(button('Check the pending save',async () => {try {await reconcilePendingSave();d.close();render();note('The saved copy was checked without resending your earlier information. Apply privacy choices to save current changes.');}catch(error){d.append(el('p',error.message));}},'secondary'));
    if (session.hasSaved) d.append(button('Delete this variant’s saved information',() => {const confirm = dialog('Delete saved advisor information?');confirm.append(el('p','This permanently removes this browser’s saved advisor reports and session. Other app variants are unaffected.'),button('Cancel',() => confirm.close(),'secondary'),button('Delete saved information',async () => {try {if(await deleteSavedInformation()){confirm.close();d.close();}}catch(error){confirm.append(el('p',error.message+(state.deletionUncertain ? ' Deletion could not be confirmed. Saving is paused and your current visit is preserved; the next action will check the saved copy and reconnect.' : state.sessionRebindRequired ? ' Saved information was deleted. Your current visit is preserved; the next action will retry reconnecting.' : '')));}},'primary'));confirm.showModal();}));
    if (!state.guide.preferences.saveGuide) d.append(button('Start over',() => {
      const confirm = dialog('Start over?');
      confirm.append(el('p','This clears this conversation and the details you reported in this visit.'),
        button('Keep this conversation',() => confirm.close(),'secondary'),
        button('Start over',async () => {
          try {await startFreshVisit();confirm.close();d.close();}
          catch {confirm.append(el('p','A new conversation could not start. Try again.','notice'));}
        },'primary'));
      confirm.showModal();
    }));
    const details = el('details');details.append(el('summary','Scope and service details'),el('p','Plan cards are five unvalidated 2027 Collier County samples. Recommendations, eligibility, prices, exact doctor/drug fit and enrollment remain independently held. This advisor variant has a $5/UTC-day AI cap within the shared usage ledger. No automatic retries. Production vendor/retention review remains separate.'),el('p',metrics.turns+' turns · '+metrics.llmCalls+' AI calls in this visit. These are diagnostics, not a consumer study.'));d.append(details,button('Close',() => d.close(),'secondary'));d.showModal();
  }
  async function restoreVisit() {
    if (busy || !visitResume?.read()) return;
    setBusy(true);
    $('resume-status')?.remove();
    try {
      const restored = await visitResume.restore(api);
      if (!restored || restored.status !== 'resumed') {
        const text = restored?.status === 'working'
          ? 'Your reply is still being prepared. Choose Continue the conversation to check again.'
          : 'This visit is no longer available. You can start again or reopen any saved reports.';
        const notice = el('p',text,'notice');notice.id = 'resume-status';notice.setAttribute('role','status');$('landing').append(notice);
        return;
      }
      state = restored.response;review = state.review || null;prepared = state.preparation || null;
      cmsChecklist = state.cmsChecklist || null;
      failedRequest = lastRequest = pendingSave = null;
      selectedGoal = '';frames = [];drafts.clear();
      if (Array.isArray(restored.history)) {
        history = restored.history.map(item => {
          const opening = item.openingChoice ? OPENING_CHOICES[item.openingChoice] : null;
          return {...item,user:opening?.label || item.user,reply:opening?.reply || item.reply,notice:plain(item.notice || '')};
        });
      } else {
        history = [];
        appendTurnHistory(restored.requestId,'','',state);
      }
      reviewMessage = review?.kind === 'interpretation' ? history.find(item => item.requestId === restored.requestId)?.user || '' : '';
      showGuide = state.guide.flow.guideOpen !== false;
      saveText = state.guide.preferences.saveGuide ? 'Saving enabled for this browser' : 'Visit only';
      showConversation(false);
      $('reading').scrollTop = $('reading').scrollHeight;
      updateScrollCue();
      note('Your conversation is ready to continue.');
      if (session.hasSaved) {
        try {const saved = await api('/api/guest/readiness');readinessVersion = saved.version;}
        catch {note('Your conversation is open. The saved copy could not be checked.');}
      }
    } catch (error) {
      if (error.code === 401) visitResume.clear();
      const notice = el('p','Your visit could not reopen just now. Choose Continue the conversation to try again.','notice');notice.id = 'resume-status';notice.setAttribute('role','status');$('landing').append(notice);
    } finally {setBusy(false);render();}
  }
  async function startFreshVisit() {
    if (busy) return;
    setBusy(true);
    try {
      const fresh = await api('/api/conversation/initial');
      const requestId = crypto.randomUUID();
      const result = await api('/api/conversation/turn',{guide:fresh.guide,record:fresh.record,action:{type:'start'},requestId});
      visitResume?.clear();
      visitResume?.write(requestId,result.guide.preferences);
      state = result;history = [];frames = [];drafts.clear();parkedMessages.length = 0;
      review = prepared = pendingSave = failedRequest = lastRequest = cmsChecklist = null;
      reviewMessage = '';preparedVersions = [];selectedGoal = '';selected = [];currentSignature = '';
      lastFocus = 0;conversationScroll = 0;openingRevealed = false;saveText = 'Visit only';
      showGuide = state.guide.flow.guideOpen !== false;
      $('message').value = '';$('restore-draft').hidden = true;$('resume-status')?.remove();
      if (document.body.classList.contains('plans-page')) window.DaylightPlans?.close();
      showConversation();$('reading').scrollTop = 0;note('');
    } finally {setBusy(false);render();}
  }
  // D138: all twelve CMS pre-enrollment topics with their reviewed statements.
  // The server returns the wording and records when it was shown and acknowledged.
  async function beforeEnroll() {
    if (!await turn({type:'before_enroll_open'},'',false,{silent:true}) || !state.beforeEnroll) { note('The Before you enroll topics could not open. Try again.'); return; }
    const step = state.beforeEnroll, when = iso => new Date(iso).toLocaleString([], {dateStyle:'medium',timeStyle:'short'});
    const d = dialog('Before you enroll');
    d.append(el('p','Medicare rules list twelve topics to go over before anyone enrolls in a plan. Daylight does not enroll anyone yet. Read each one, and ask Daylight about anything that is unclear.'));
    step.items.forEach((item,index) => {
      const section = el('section',undefined,'before-enroll-topic');section.append(el('h3',`${index+1}. ${item.title}`));
      for (const row of item.statements) section.append(el('p',row.text));
      if (item.covered_in_conversation) section.append(el('p','This also came up in your conversation.','small'));
      d.append(section);
    });
    const status = el('p',step.acknowledged_at ? 'Recorded as read on '+when(step.acknowledged_at)+'.' : 'Shown on '+when(step.shown_at)+'.','small');status.setAttribute('role','status');
    d.append(status,button('I’ve read these',async () => { if (await turn({type:'before_enroll_ack'},'',false,{silent:true}) && state.beforeEnroll?.acknowledged_at) status.textContent = 'Recorded as read on '+when(state.beforeEnroll.acknowledged_at)+'.'; },'primary'),button('Close',() => d.close(),'secondary'));
    d.showModal();
  }
  async function resume() {
    if (visitResume?.read()) {
      const d = dialog('Resume this visit?');
      d.append(el('p','Your conversation and reported details may still be available in this tab. Open them only if it is appropriate on this device.'),
        button('Cancel',() => d.close(),'secondary'),
        button('Resume visit',async () => {d.close();await restoreVisit();},'primary'),
        button('Start a separate visit',async () => {
          try {
            await startFreshVisit();d.close();
          } catch {d.append(el('p','A separate visit could not start. Your current visit is still available.'));}
        },'secondary'));
      d.showModal();return;
    }
    const d = dialog('Resume saved information?');
    d.append(el('p','Only open this if it is appropriate to show the saved reports on this device. Conversation and drafts were not saved.'),
      button('Keep this visit',() => d.close(),'secondary'),
      button('Resume saved reports',async () => {
        if (busy) return;
        setBusy(true);
        try {
          const [g,r] = await Promise.all([api('/api/guest/profile'),api('/api/guest/readiness')]);
          if (!g.guide) throw Error('No saved reports were found.');
          const requestId = crypto.randomUUID();
          const result = await api('/api/conversation/turn',{guide:g.guide,record:r.record || state.record,action:{type:'refresh'},requestId});
          visitResume?.write(requestId,result.guide.preferences);
          state = result;savedVersion = g.version;readinessVersion = r.version;
          pendingSave = failedRequest = lastRequest = null;selectedGoal = '';history = [];review = prepared = null;drafts.clear();
          showGuide = state.guide.flow.guideOpen !== false;saveText = 'Resumed · omitted sensitive details remain open';
          d.close();showConversation();
        } catch(error) {d.append(el('p',error.message+' Your current visit is preserved.'));}
        finally {setBusy(false);render();}
      },'primary'));
    d.showModal();
  }
  $('composer').onsubmit = e => {e.preventDefault();void submitCurrent();};
  $('chat-down').onclick = jumpDown;
  $('reading').addEventListener('scroll',updateScrollCue,{passive:true});
  $('reading').addEventListener('toggle',() => {updateScrollCue();requestAnimationFrame(updateScrollCue);},true);
  document.addEventListener('visibilitychange',updateScrollCue);
  $('message').oninput = messageInput;
  $('restore-draft').onclick = () => {if($('message').value.trim()){note('Send or clear the current message before restoring your earlier draft.');return;}$('message').value = parkedMessages.pop() || '';renderCurrent();messageInput();$('message').focus();note('Draft restored. It has not been sent.');};
  $('message').addEventListener('compositionstart',() => { composing = true; });$('message').addEventListener('compositionend',() => { composing = false; });
  $('message').addEventListener('keydown',e => {if(e.key === 'Enter' && !e.shiftKey && !e.isComposing && !composing){e.preventDefault();$('composer').requestSubmit();}});
  $('start').onclick = () => {
    if (busy) return;
    if (!conversationStarted && visitResume?.read()) {void restoreVisit();return;}
    showConversation();$('reading').scrollTop = conversationScroll;updateScrollCue();
  };
  $('daylight-home').onclick = event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (state && !busy) showHome();
  };
  $('back').onclick = async () => {if(review){await turn({type:'discard_review',token:review.token});return;}if(frames.length){await turn({type:'edit',id:frames.pop()});return;}showHome();};
  $('review').onclick = reviewInformation;$('privacy').onclick = $('landing-privacy').onclick = privacy;$('resume').onclick = $('landing-resume').onclick = resume;
  $('prepare').onclick = () => turn({type:'review_preparation'});$('samples').onclick = () => turn({type:'next',step:'samples'});
  window.addEventListener('resize',() => {if(active) resizeComposer();});
  window.visualViewport?.addEventListener('resize',() => {if(active) resizeComposer();});
  window.addEventListener('beforeunload',event => {
    const question = q(), draft = question && drafts.get(question.signature);
    if (busy || active && state?.continuation && !visitResume?.read() || $('message').value.trim() || draft && (draft.choice?.length || draft.resolution || Object.keys(draft.fields || {}).length)) {
      event.preventDefault();event.returnValue = '';
    }
  });
  Promise.all([api('/api/guest/session'),api('/api/status'),api('/ten-config.json'),api('/baseline-content.json'),api('/api/sample-plans')]).then(async ([s,v,c,b,p]) => {session = s;service = v;config = c;const modelSelect = $('ai-model');
    if (modelSelect && c.models?.some(item => item.available)) {
      for (const model of c.models) {
        const option = el('option', model.label + (model.available ? '' : ' (unavailable)'));
        option.value = model.id;option.disabled = !model.available;modelSelect.append(option);
      }
      modelSelect.value = (c.models.find(item => item.id === c.defaultModel && item.available) || c.models.find(item => item.available)).id;
      const showProvider = () => {
        const model = c.models.find(item => item.id === modelSelect.value);
        $('model-transfer').textContent = 'Send shares relevant chat and profile details with ' + model.provider + '.';
      };
      modelSelect.addEventListener('change', showProvider);
      showProvider();$('model-control').hidden = false;
      $('model-control').classList.toggle('model-dev', new URLSearchParams(location.search).has('models'));
    }
    baseline = b;sampleData = p;savedVersion = s.version;state = await api('/api/conversation/initial');state.reportedRows = [];showGuide = state.guide.flow.guideOpen !== false;$('start').disabled = false;$('privacy').disabled = $('landing-privacy').disabled = false;$('fixture').hidden = !config.mockAI;$('resume').hidden = $('landing-resume').hidden = !session.hasSaved;
    if (service?.local_demo?.doctor_chat && window.DaylightDoctorCheck) {
      const check = button('Check a doctor', () => openDoctorCheck());
      check.id = 'chat-doctor-check';
      document.querySelector('.chat-tools').prepend(check);
    }
    if (service?.local_demo?.prescription_rehearsal) {
      const link = el('a', 'Try fictional drug costs', 'text-button');
      link.id = 'chat-prescription-rehearsal';
      link.href = '/d146/';
      link.target = '_blank';
      link.rel = 'noopener';
      link.setAttribute('aria-label', 'Try fictional drug costs in a separate tab');
      document.querySelector('.chat-tools').append(link);
    } else if (window.DaylightPrescriptionPreview) {
      const scope = 'Fictional visit. Use invented details only.';
      document.querySelector('.landing-sub').after(el('p', scope, 'chat-small'));
      $('fixture').textContent = scope;
      const setup = button('Set up a fictional drug cost check', () =>
        turn({type:'task',task:'drug_pricing',preparing:true},'',false,{silent:true}));
      setup.id = 'chat-prescription-setup';
      document.querySelector('.chat-tools').append(setup);
    }
    window.DaylightPlans?.init({request:api,activate:()=>{closeDoctorCheck(false);active=true;$('landing').hidden=true;$('workspace').hidden=false;render();},ask:text=>{
      const previous=$('message').value;
      if(previous.trim()&&previous!==text&&!parkedMessages.includes(previous)){
        parkedMessages.push(previous);$('restore-draft').hidden=false;
        note('Your earlier message is available in Restore draft. This plan question is ready to edit.');
      }
      $('message').value=text;messageInput();
    },
    // D97: Plans-page filters write the same free structured answers as the
    // conversation, labelled plans_filter; never an AI call.
    answer:(id,fields) => turn({type:'choice',id,fields,source:'plans_filter'},'',false,{silent:true}),
    // D131: route to the existing conversation without sending a message,
    // inventing an answer or consuming the person's unsent draft.
    medigapConversation:async id => {
      if (!await turn({type:'task',task:'medigap',preparing:true},'',false,{silent:true})) return false;
      selectedGoal = '';
      return id ? turn({type:'edit',id},'',false,{silent:true}) : true;
    },
    partDConversation:async id => {
      if (!await turn({type:'task',task:'drug_pricing',preparing:true},'',false,{silent:true})) return false;
      selectedGoal = '';
      return id ? turn({type:'edit',id},'',false,{silent:true}) : true;
    },
    prescriptionPreview: window.DaylightPrescriptionPreview ? openPrescriptionPreview : null,
    profile:() => ({fields:clone(state.guide.fields),facts:clone(state.record.facts || {}),provenance:clone(state.record.natural?.provenance || {}),
      readiness:clone(state.planReadiness || null),handoff:clone(state.plansHandoff || null),medigap:clone(state.medigapProfile || null),partD:clone(state.partDProfile || null),
      // D147: evaluation-only sorting inputs; present only when the local demo turns it on.
      recommendation:service?.eval_recommendations ? clone(state.recommendationInputs || null) : null,task:state.record.conversation?.task || '',visit:state.continuation?.split('.')[0] || '',busy}),
    review:() => turn({type:'review_plans'}),
    beforeEnroll,
    privacy});
    render();
    if (performance.getEntriesByType('navigation')[0]?.type === 'reload') await restoreVisit();
  }).catch(error => {note(error.message);$('landing').append(el('p','Daylight could not load. Reload to try again. Existing saved information is unchanged.','notice'));});
})();
