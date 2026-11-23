'use strict';
/* D161: the enrollment views draw only what the server supplies. Fictional
   person (turned 65 in November 2026, neither part). No network. */
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), test = require('node:test'), assert = require('node:assert/strict');
const WEB = path.join(__dirname, '../web-8894');
const source = fs.readFileSync(path.join(WEB, 'enrollment-view.js'), 'utf8');
const content = JSON.parse(fs.readFileSync(path.join(__dirname, '../enrollment-content.json'), 'utf8'));

function load() {
  class Node {
    constructor(tag) {this.tagName = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.text = ''; this.className = '';}
    set textContent(v) {this.text = String(v); this.children = [];}
    get textContent() {return this.text + this.children.map(x => typeof x === 'string' ? x : x.textContent).join('');}
    append(...nodes) {this.children.push(...nodes);}
    setAttribute(k, v) {this.attributes[k] = v;}
  }
  const document = {createElement: tag => new Node(tag)};
  const window = {document};
  vm.runInNewContext(source, {window, Map, String, Number, JSON, Error, Promise});
  const all = node => [node, ...node.children.filter(x => typeof x === 'object').flatMap(all)];
  return {E: window.DaylightEnrollment, all};
}

const LINE = {text: 'Part A: not yet · Part B: not yet. Next: sign up through Social Security by February 28, 2027 (from your birthday month).',
  status: 'Part A: not yet · Part B: not yet.', plan: null,
  parts: [{part: 'A', state: 'needed', text: 'not yet'}, {part: 'B', state: 'needed', text: 'not yet'}],
  next: {id: 'sign_up', text: 'sign up through Social Security by February 28, 2027 (from your birthday month)', by: '2027-02-28', basis: 'estimated'}};
const ROUTE = {kind: 'signup_route', route: 'sign_up_a_and_b', title: 'How to sign up for Part A and Part B',
  lines: [content.statements.signup_routes.text, content.statements.never_ids.text],
  rows: [{label: 'Online', value: 'ssa.gov/medicare/sign-up', url: 'https://www.ssa.gov/medicare/sign-up'},
    {label: 'By phone', value: '1-800-772-1213', note: 'Monday through Friday, 8 a.m. to 7 p.m. TTY 1-800-325-0778.'}],
  guides: ['online_ab', 'phone'], sources: [{label: 'Social Security: Sign up for Medicare', url: 'https://www.ssa.gov/medicare/sign-up'}]};
const step = (id, title, state, text, choices) => ({id, title, state, text, choices});
const CHOICES = [['chosen', 'Done'], ['keep_existing', 'Keep what I have'], ['not_needed', 'Not needed'], ['decide_later', 'Decide later']];
const VIEW = {line: LINE, route: ROUTE, record: {route: 'sign_up_a_and_b'},
  dates: [{label: 'Sign-up window', value: 'August 1, 2026 to February 28, 2027', basis: 'estimated', note: 'From your birthday month.'},
    {label: 'Part B start', value: 'December 1, 2026', basis: 'reported', note: 'You told me.'}],
  dashboard: {paths: {
    original: {title: 'Original Medicare', open: 'medigap', steps: [step('ab', 'Parts A and B', 'open', LINE.status),
      step('medigap', 'Your share of medical costs', 'not_needed', 'No Medigap policy', CHOICES), step('part_d', 'Prescriptions', 'unknown', 'Not decided', CHOICES)]},
    advantage: {title: 'Medicare Advantage', open: 'plan', steps: [step('ab', 'Parts A and B', 'open', LINE.status),
      step('plan', 'Choose a plan', 'unknown', 'Not decided', [['chosen', 'Done'], ['decide_later', 'Decide later']]),
      step('drugs', 'Check that plan’s drug coverage', 'unknown', 'Not checked', [['chosen', 'Done']])]}}}};

test('the status line is one line: both parts, then the next step, exactly as supplied', () => {
  const {E} = load(), line = E.statusLine(VIEW);
  assert.equal(line.textContent, LINE.text);
  assert.equal(line.attributes.role, 'status');
  assert.equal(E.statusLine({line: null}), null);                 // nothing reported yet: no line
  assert.equal(E.statusLine(null), null);
});

test('the sign-up route card shows the sentences, the routes and a button for each guide', () => {
  const {E, all} = load(), host = {children: [], append(...n) {this.children.push(...n);}}, opened = [];
  assert.equal(E.card(ROUTE, host, {guide: (id, route) => opened.push([id, route])}), true);
  const nodes = host.children.flatMap(all), text = nodes.map(n => n.text).join(' ');
  assert.match(text, /through Social Security: online, by phone at 1-800-772-1213/);
  assert.match(text, /never needs your Social Security number/);
  const link = nodes.find(n => n.tagName === 'a');
  assert.equal(link.href, 'https://www.ssa.gov/medicare/sign-up'); assert.equal(link.rel, 'noopener noreferrer');
  const buttons = nodes.filter(n => n.tagName === 'button');
  assert.deepEqual(buttons.map(b => b.textContent), ['Open the online sign-up guide', 'Open the phone guide']);
  buttons[1].onclick(); assert.deepEqual(opened, [['phone', 'sign_up_a_and_b']]);
  assert.equal(E.card({kind: 'enrollment_timing'}, host), false);    // other cards are not touched
  assert.equal(nodes.filter(n => n.tagName === 'input' || n.tagName === 'textarea').length, 0);   // nothing is asked for
});

test('a chosen finish gets its own summary, with the accepted notes', () => {
  const {E, all} = load(), host = {children: [], append(...n) {this.children.push(...n);}};
  E.card({kind: 'finish_summary', title: 'Your plan: Parts A and B only', rows: [{label: 'Part A', value: 'Not yet'}, {label: 'Prescriptions', value: 'No Part D plan'}],
    lines: [content.statements.no_limit.text], change: 'You can change this any time. Just tell me.'}, host);
  const text = host.children.flatMap(all).map(n => n.text).join(' ');
  assert.match(text, /No Part D plan/); assert.match(text, /Worth knowing/); assert.match(text, /no annual out-of-pocket limit/);
});

test('the way into the plans is one button on a card, and what a person already has is listed as facts', () => {
  // 15-profile run, November 13, 2026: no button into the plans appeared in twelve conversations.
  const {E, all} = load(), opened = [];
  const host = {children: [], append(...n) {this.children.push(...n);}};
  assert.equal(E.card({kind: 'plans_ready', title: 'Your Medigap prices are ready.', button: {label: 'See your Medigap prices', view: 'supplement'}}, host, {open: view => opened.push(view)}), true);
  const press = host.children.flatMap(all).find(n => n.tagName === 'button');
  assert.equal(press.text, 'See your Medigap prices'); press.onclick(); assert.deepEqual(opened, ['supplement']);
  const have = {children: [], append(...n) {this.children.push(...n);}};
  assert.equal(E.card({kind: 'coverage_now', title: 'What you have now', rows: [{label: 'Part A', value: 'active since 2020 (you told me)'}, {label: 'Your share of medical costs', value: 'You have Plan G.'}]}, have), true);
  const text = have.children.flatMap(all).map(n => n.text).join(' ');
  assert.match(text, /active since 2020 \(you told me\)/); assert.match(text, /You have Plan G\./);
  assert.equal(have.children.flatMap(all).filter(n => n.tagName === 'button').length, 0);   // a fact, never a decision
});

test('the other choices put the person’s own sentence in the composer; nothing is sent', () => {
  const {E, all} = load(), staged = [];
  const row = E.choices([{label: 'Parts A and B only', say: 'I want Parts A and B only.'}, {label: 'Wait for now', say: 'I’ll wait for now.'}], t => staged.push(t));
  const buttons = all(row).filter(n => n.tagName === 'button');
  assert.deepEqual(buttons.map(b => b.textContent), ['Parts A and B only', 'Wait for now']);
  buttons[0].onclick(); assert.deepEqual(staged, ['I want Parts A and B only.']);
});

test('three decisions per path; each shows its answer; a step button only navigates', () => {
  const {E, all} = load(), went = [];
  const nav = E.steps(VIEW, {tab: 'original', step: 'medigap', onStep: id => went.push(id)});
  const buttons = all(nav).filter(n => n.tagName === 'button');
  assert.equal(buttons.length, 3);
  assert.match(buttons[0].textContent, /1Parts A and BPart A: not yet · Part B: not yet\./);
  assert.match(buttons[1].textContent, /2Your share of medical costsNo Medigap policy/);
  assert.equal(buttons[1].attributes['aria-current'], 'step'); assert.equal(buttons[1].dataset.state, 'not_needed');
  buttons[2].onclick(); assert.deepEqual(went, ['part_d']);
  const ma = E.steps(VIEW, {tab: 'advantage', step: 'plan', local: {plan: {state: 'chosen', text: 'Fictional Plan One'}}, onStep() {}});
  assert.match(all(ma).filter(n => n.tagName === 'button')[1].textContent, /Fictional Plan One/);
  const picked = [], row = E.decisions(VIEW.dashboard.paths.original.steps[1], 'not_needed', v => picked.push(v));
  const choices = all(row).filter(n => n.tagName === 'button');
  assert.deepEqual(choices.map(b => b.textContent), ['Done', 'Keep what I have', 'Not needed', 'Decide later']);
  assert.equal(choices[2].attributes['aria-pressed'], 'true'); assert.equal(choices[0].attributes['aria-pressed'], 'false');
  choices[3].onclick(); assert.deepEqual(picked, ['decide_later']);
});

test('the Parts A and B step shows the dates with their basis and the route', () => {
  const {E, all} = load(), panel = E.partsPanel(VIEW, {guide() {}, stage() {}}), nodes = all(panel);
  const tags = nodes.filter(n => n.className === 'enroll-basis').map(n => [n.textContent, n.dataset.basis]);
  assert.deepEqual(tags, [['Estimate', 'estimated'], ['You told me', 'reported']]);      // never shown as confirmed
  assert.match(panel.textContent, /How to sign up for Part A and Part B/);
  assert.match(panel.textContent, /Tell Daylight what happened/);
});

test('before anything is known the Parts A and B step still says how to sign up and offers all three guides', () => {
  const opened = [], staged = [];
  const SIGNUP = {...ROUTE, route: 'general', guides: ['online_ab', 'add_part_b', 'phone']};
  const {E, all} = load(), panel = E.partsPanel({line: null, route: null, signup: SIGNUP, dates: []}, {guide: id => opened.push(id), stage: say => staged.push(say)});
  const nodes = all(panel), buttons = nodes.filter(n => n.tagName === 'button');
  assert.ok(nodes.some(n => n.tagName === 'h3' && n.text === 'How to sign up for Part A and Part B'));
  assert.ok(nodes.some(n => n.text === content.statements.signup_routes.text));
  for (const label of Object.values(E.GUIDE_LABELS)) assert.ok(buttons.some(b => b.text === label), label);
  buttons.filter(b => Object.values(E.GUIDE_LABELS).includes(b.text)).forEach(b => b.onclick());
  assert.deepEqual(opened, ['online_ab', 'add_part_b', 'phone']);
  buttons.find(b => b.text === 'I applied').onclick();
  assert.deepEqual(staged, ['I applied on ']);          // the person's own sentence goes to the composer; nothing is sent
  assert.ok(!nodes.some(n => n.className === 'enroll-lead'));   // no status is asserted
});

test('the sign-up card asks where the person is with Social Security; a tap sends their answer and nothing else', async () => {
  const sent = [], opened = [];
  const CALL = {stage: 'ask', question: 'Where are you with Social Security?', choices: [
    {label: 'I plan to call', action: {contact: 'planned'}, guide: 'phone'}, {label: 'I already called', action: {contact: 'called'}},
    {label: 'Not what I need right now', action: {contact: 'not_now'}}]};
  const {E, all} = load(), host = E.callBranch({call: CALL, record: {route: 'confirm_with_social_security'}},
    {decide: async fields => {sent.push(fields); return true;}, guide: (id, route) => opened.push([id, route])});
  const nodes = all(host), buttons = nodes.filter(n => n.tagName === 'button');
  assert.ok(nodes.some(n => n.text === CALL.question));
  assert.deepEqual(buttons.map(b => b.text), CALL.choices.map(c => c.label));
  await buttons[0].onclick();
  assert.deepEqual(sent, [{contact: 'planned'}]);
  assert.deepEqual(opened, [['phone', 'confirm_with_social_security']]);       // "I plan to call" opens the phone guide
  await buttons[2].onclick();
  assert.deepEqual(sent[1], {contact: 'not_now'});
  assert.equal(E.callBranch({call: {stage: 'not_now'}}, {decide() {}}), null);   // folded: nothing more is asked
  assert.equal(E.callBranch({call: CALL}, {}), null);                           // without a way to record it, no question
});

test('start dates are typed by the person and sent as their own report', async () => {
  const sent = [];
  const CALL = {stage: 'called', question: 'What happened on the call?', choices: [
    {label: 'I applied', action: {report: 'applied'}}, {label: 'They gave me start dates', dates: true}]};
  const {E, all} = load(), host = E.callBranch({call: CALL}, {decide: async fields => {sent.push(fields); return true;}});
  const nodes = all(host), form = nodes.find(n => n.className === 'enroll-dates'), inputs = nodes.filter(n => n.tagName === 'input');
  assert.equal(form.hidden, true);
  await nodes.find(n => n.text === 'They gave me start dates').onclick();
  assert.equal(form.hidden, false);
  assert.deepEqual(sent, []);                                                    // opening the form records nothing
  inputs[1].value = '2026-12-01';
  nodes.find(n => n.tagName === 'button' && n.text === 'Done').onclick();
  assert.equal(JSON.stringify(sent), JSON.stringify([{starts: {B: '2026-12-01'}}]));
});

test('both paths are drawn side by side, then one question; the tapped start shows as pressed', async () => {
  const sent = [];
  const TRADE = {kind: 'trade_off', because: 'You said predictable costs matter more.', top: content.statements.no_limit.text,
    columns: [{id: 'original_medigap', title: 'Original Medicare with Medigap', lines: ['a', 'b'], amounts: [{label: 'Medigap', source: 'medigap'}]},
      {id: 'medicare_advantage', title: 'Medicare Advantage', lines: ['c', 'd'], amounts: [{label: 'Plan premium', source: 'ma_premium'}]}],
    note: 'You asked about Medicare Advantage first, so it stays open.',
    question: 'Both paths are on the card. Start with Medigap prices, and keep Medicare Advantage open to compare?',
    choices: [{label: 'Start with Medigap', action: {start_with: 'original_medigap'}}, {label: 'Start with Medicare Advantage', action: {start_with: 'medicare_advantage'}},
      {label: 'Show me both', action: {start_with: 'both'}}]};
  const {E, all} = load();
  class Box {constructor() {this.children = [];} append(...n) {this.children.push(...n);}}
  const box = new Box();
  assert.equal(E.card(TRADE, box, {decide: async fields => {sent.push(fields); return true;}, view: {start: 'medicare_advantage'}}), true);
  const nodes = box.children.flatMap(all), buttons = nodes.filter(n => n.tagName === 'button');
  assert.deepEqual(nodes.filter(n => n.tagName === 'h4').map(n => n.text), ['Original Medicare with Medigap', 'Medicare Advantage']);
  assert.ok(nodes.some(n => n.text === TRADE.note) && nodes.some(n => n.text === TRADE.question));
  assert.deepEqual(buttons.map(b => [b.text, b.attributes['aria-pressed']]),
    [['Start with Medigap', 'false'], ['Start with Medicare Advantage', 'true'], ['Show me both', 'false']]);
  await buttons[2].onclick();
  assert.deepEqual(sent, [{start_with: 'both'}]);
  assert.equal(E.card({kind: 'trade_off', text: 'old card'}, new Box(), {}), false);   // the earlier one-line card is left to the page
});

test('the phone guide opens with the person’s own lines for the call, and the Parts A and B step asks once', () => {
  const NOTES = {title: 'For your call', say: ['“I turned 65 in October 2026.”'], ask: ['“Do I need my employer to fill in form CMS-L564?”'],
    know: [content.statements.current_work.text], sources: []};
  const {E, all} = load(), page = E.guide(content, 'phone', {route: 'confirm_with_social_security', notes: NOTES}), nodes = all(page);
  assert.ok(nodes.some(n => n.tagName === 'h2' && n.text === 'For your call'));
  assert.deepEqual(nodes.filter(n => n.tagName === 'h3').map(n => n.text).slice(0, 3), ['Say', 'Ask', 'Good to know before you call']);
  assert.ok(nodes.some(n => n.text === NOTES.say[0]) && nodes.some(n => n.text === NOTES.ask[0]));
  assert.ok(!all(E.guide(content, 'online_ab', {notes: NOTES})).some(n => n.text === 'For your call'));   // only on the phone guide
  assert.ok(!all(E.guide(content, 'phone', {})).some(n => n.text === 'For your call'));                   // nothing reported, nothing shown
  const CALL = {stage: 'ask', question: 'Where are you with Social Security?', choices: [{label: 'I already called', action: {contact: 'called'}}]};
  const panel = all(E.partsPanel({...VIEW, call: CALL}, {guide() {}, stage() {}, decide: async () => true}));
  assert.equal(panel.filter(n => n.text === CALL.question).length, 1);
  assert.ok(!panel.some(n => n.text === 'Tell Daylight what happened'));
});

test('each guide: ready list, what is asked in order with a drawing, after, last checked, official link', () => {
  const {E, all} = load();
  for (const id of ['online_ab', 'add_part_b', 'phone']) {
    const asked = [], page = E.guide(content, id, {route: 'sign_up_a_and_b', ask: t => asked.push(t)}), nodes = all(page), text = page.textContent;
    const spec = content.guides.find(g => g.id === id);
    assert.match(text, /Last checked November 12, 2026/, id);
    const official = nodes.find(n => n.tagName === 'a' && /^Official page:/.test(n.textContent));
    assert.equal(official.href, content.sources[spec.official].url, id);
    for (const heading of ['What to have ready', spec.steps_title, 'What happens after']) assert.ok(nodes.some(n => n.tagName === 'h2' && n.text === heading), id + ': ' + heading);
    const drawings = nodes.filter(n => n.className === 'enroll-drawing');
    assert.equal(drawings.length, spec.steps.length, id);
    for (const d of drawings) {assert.match(d.innerHTML, /^<svg /); assert.doesNotMatch(d.innerHTML, /<image|href=|ssa\.gov/);}   // our own drawings, no screenshots
    assert.match(text, /never needs your Social Security number/, id);
    nodes.find(n => n.tagName === 'button' && n.textContent === 'Ask Daylight what this means').onclick();
    assert.equal(asked.length, 1); assert.match(asked[0], /what does step 1/);
    assert.equal(nodes.filter(n => n.tagName === 'input' || n.tagName === 'textarea').length, 0, id);
  }
  const phone = load().E.guide(content, 'phone', {route: 'add_part_b'});
  assert.match(phone.textContent, /“I have Part A and I want to sign up for Part B\.”/);       // what to say follows the route
  assert.match(phone.textContent, /What to write down/);
  assert.match(phone.textContent, /1-800-772-1213/);
  assert.equal(load().E.guide(content, 'missing'), null);
});

test('the doctor card writes dates and the office the way a person does, and says what its date is', () => {
  // Owner's test conversation, November 13, 2026: "Original Medicare · 2026-12-01", "record dated 2026-10-01",
  // "4225 EVANS AVE, FORT MYERS, FL, 339019311".
  class Node {
    constructor(tag) {this.tagName = tag; this.children = []; this.attributes = {}; this.text = ''; this.className = ''; this.classList = {toggle() {}, add() {}, remove() {}};}
    set textContent(v) {this.text = String(v);} get textContent() {return this.text;}
    append(...nodes) {this.children.push(...nodes);} setAttribute(k, v) {this.attributes[k] = v;} addEventListener() {}
  }
  const window = {}, document = {createElement: tag => new Node(tag), querySelectorAll: () => [], getElementById: () => null};
  vm.runInNewContext(fs.readFileSync(path.join(WEB, 'conversation-checks.js'), 'utf8'), {window, document, Intl, Set, Object, String, Number});
  const host = new Node('div');
  window.DaylightConversationChecks.render(host, {results: [{kind: 'doctor', key: 'doctor:1', name: 'STEPHEN E SMITH MD',
    office: '4225 EVANS AVE, FORT MYERS, FL, 339019311', plan: 'Original Medicare', date: '2026-12-01',
    details: ['Medicare lists this doctor as enrolled to bill Medicare (record dated 2026-10-01).']}]}, {});
  const all = node => [node, ...node.children.filter(x => typeof x === 'object').flatMap(all)], texts = all(host).map(n => n.text);
  assert.ok(texts.includes('4225 Evans Ave, Fort Myers, FL 33901-9311'), texts.join(' | '));
  assert.ok(texts.includes('Original Medicare · date checked: December 1, 2026'));
  assert.ok(texts.includes('Medicare lists this doctor as enrolled to bill Medicare (record dated October 1, 2026).'));
  assert.ok(texts.includes('STEPHEN E SMITH MD'));      // a name is left as Medicare publishes it
  assert.ok(!texts.some(text => /\d{4}-\d{2}-\d{2}/.test(text)));
  // Candidates arrive in parts with a flag for the place the person named: matches read normally, and a match
  // in another town says so. With no match in the named place the flag cannot tell us a place was named.
  const ask = new Node('div'), q = {kind: 'doctor', field: 'doctor', question: 'Which of these is Dr. Smith?', token: 't',
    choices: [{value: 'a', label: 'RAW A'}, {value: 'b', label: 'RAW B'}, {value: '__refine__', label: 'None of these: search by practice name'}],
    candidates: [{candidate_id: 'a', label: 'ANN SMITH MD', offices: [{line: '100 9TH ST N', city: 'NAPLES', state: 'FL', zip5: '34102', zip4: null, place_match: true}]},
      {candidate_id: 'b', label: 'STEPHEN E SMITH MD', offices: [{line: '4225 EVANS AVE', city: 'FORT MYERS', state: 'FL', zip5: '33901', zip4: '9311', place_match: false}]}]};
  window.DaylightConversationChecks.render(ask, {question: q, results: []}, {changed() {}, defer() {}, edit() {}, editCheck() {}, back() {}});
  const labels = all(ask).filter(n => n.tagName === 'button').map(n => n.text);
  assert.ok(labels.includes('ANN SMITH MD — 100 9th St N, Naples, FL 34102'), labels.join(' | '));
  assert.ok(labels.includes('STEPHEN E SMITH MD — 4225 Evans Ave, Fort Myers, FL 33901-9311 · different town'));
  assert.ok(labels.includes('None of these: search by practice name'));
});

test('the participant interface page does not load the enrollment files', () => {
  const index = fs.readFileSync(path.join(WEB, 'index.html'), 'utf8');
  assert.doesNotMatch(index, /enrollment/);
  // Wording awaiting sign-off is served by the :8895 process only, never from the shared web folder.
  assert.equal(fs.existsSync(path.join(WEB, 'enrollment-content.json')), false);
  for (const file of ['enrollment-view.js', 'advisor.js', 'plans-workspace.js'])
    assert.doesNotMatch(fs.readFileSync(path.join(WEB, file), 'utf8'), /at least 4 months before|Railroad Retirement Board|CMS-40B/, file);
});

test('discussion path actions only stage words and never record a decision or open prices', () => {
  const {E, all} = load(), staged = [], decisions = [], opened = [];
  const host = {children: [], append(...nodes) {this.children.push(...nodes);}};
  assert.equal(E.card({kind:'discussion_paths', columns:[
    {title:'Original Medicare',lines:['An explanation.']},
    {title:'Medicare Advantage',lines:['Another explanation.']}],
    actions:[{label:'Explore Original Medicare',say:'Help me understand Original Medicare.'}]},
    host,{stage:words=>staged.push(words),decide:value=>decisions.push(value),open:view=>opened.push(view)}),true);
  const controls=host.children.flatMap(all).filter(node=>node.tagName==='button');
  controls[0].onclick();
  assert.deepEqual(staged,['Help me understand Original Medicare.']);
  assert.deepEqual(decisions,[]);assert.deepEqual(opened,[]);
});

test('D183: an offer of work is a button that stages the person\'s own words', () => {
  const {E, all} = load();
  const host = {children: [], append(...n) {this.children.push(...n);}};
  const staged = [];
  const card = {kind: 'next_step_offer', title: '', actions: [{label: 'Check my doctors', say: 'Yes, let’s do that: check my doctors.'}]};
  assert.equal(E.card(card, host, {stage: words => staged.push(words)}), true);
  const buttons = host.children.flatMap(all).filter(n => n.tagName === 'button');
  assert.equal(buttons.length, 1);
  assert.equal(buttons[0].textContent, 'Check my doctors');
  buttons[0].onclick();
  assert.deepEqual(staged, ['Yes, let’s do that: check my doctors.']);
});
