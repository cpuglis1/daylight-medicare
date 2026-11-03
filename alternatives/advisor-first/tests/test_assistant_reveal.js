/* Free behavioral checks of the actual :8893 presentation functions.
 * This intentionally does not start the app, a server, or a model request.
 */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const web = path.join(__dirname, '..', 'web');
const source = fs.readFileSync(path.join(web, 'advisor.js'), 'utf8');
const start = source.indexOf('  function paragraph(');
const end = source.indexOf('  function phaseTrack(', start);
assert.ok(start > 0 && end > start, 'Load the production paragraph/history functions, not a test copy.');
const renderingSource = source.slice(start, end);
const elementSource = source.match(/^  const el = .*$/m)?.[0];
const openingQuestionSource = source.match(/^  const OPENING_QUESTION = .*$/m)?.[0];
const revealSetSource = source.match(/^  const revealedReplies = new WeakSet\(\);$/m)?.[0];
const questionSetSource = source.match(/^  const revealedQuestions = new WeakSet\(\);$/m)?.[0];
const buttonSource = source.match(/^  const button = .*$/m)?.[0];
const formSource = source.slice(source.indexOf('  function renderForm('),source.indexOf('  async function submitForm('));
const referenceSource = source.slice(source.indexOf('  function drawReference('),source.indexOf('  function draftFor('));
const currentSource = source.slice(source.indexOf('  function renderCurrent('),source.indexOf('  function renderPrepared('));
const failureSource = source.slice(source.indexOf('  function generationUnavailable('),source.indexOf('  function visibleQuestion('));
const appendHistorySource = source.slice(source.indexOf('  function appendTurnHistory('),source.indexOf('  async function turn('));
const focusSource = source.slice(source.indexOf('  function conversationFocus('),source.indexOf('  function drawReference('));
assert.ok(elementSource && revealSetSource && questionSetSource && buttonSource, 'Use the production helpers and once-only reveal state.');

class FakeNode {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attributes = new Map();
    this.className = '';
    this.classList = {
      contains: name => this.className.split(/\s+/).includes(name),
      toggle: (name,force) => {
        const classes=new Set(this.className.split(/\s+/).filter(Boolean));
        const enabled=force === undefined ? !classes.has(name) : Boolean(force);
        if (enabled) classes.add(name);else classes.delete(name);
        this.className=[...classes].join(' ');return enabled;
      },
    };
    this._text = '';
    this.parentElement = null;
    this.value = '';
    this.style = {
      values: new Map(),
      setProperty(name, value) { this.values.set(name, value); },
      getPropertyValue(name) { return this.values.get(name) || ''; },
    };
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  append(...nodes) {
    for (const node of nodes) {
      assert.ok(node instanceof FakeNode, 'Rendering inserts text nodes through textContent.');
      node.parentElement = this;
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) { this.children = []; this._text = ''; this.append(...nodes); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  querySelector(selector) {
    const data = selector.match(/^\[data-coverage-group="([a-z]+)"\]$/);
    assert.ok(data,'The renderer only queries its authored coverage-group key.');
    return all(this,node => node.getAttribute('data-coverage-group') === data[1])[0] || null;
  }
  focus(options) {this.focused = true;this.focusOptions = options;}
  dispatchEvent(event) {
    const handler = this[`on${event.type}`];
    if (typeof handler === 'function') handler.call(this, {...event, target: this});
    return true;
  }
}

function all(root, predicate) {
  return [root, ...root.children.flatMap(child => all(child, predicate))].filter(predicate);
}
const byClass = (root, name) => all(root, node => node.className.split(/\s+/).includes(name));
const byTag = (root, name) => all(root, node => node.tagName === name.toUpperCase());
const accessibleText = node => node.getAttribute('aria-hidden') === 'true' ? '' :
  node._text + node.children.map(accessibleText).join('');
const visualText = node => node.className.split(/\s+/).includes('sr-only') ? '' :
  node._text + node.children.map(visualText).join('');

function harness(reduced = false) {
  const host = new FakeNode('div');
  const reference = new FakeNode('aside');
  const message = new FakeNode('textarea');
  let current = new FakeNode('section');
  const drafts = new Map();
  let reducedMotion = reduced;
  const queries = [];
  const notices = [];
  const context = vm.createContext({
    document: {createElement: tag => new FakeNode(tag)},
    $: id => { assert.ok(['history','reference','current','message'].includes(id)); return id === 'history' ? host : id === 'reference' ? reference : id === 'message' ? message : current; },
    matchMedia: query => { queries.push(query); return {matches: reducedMotion}; },
    URL,
    history: [],
    renderedHistory: 0,
    firstHistory: null,
    openingRevealed: false,
    draftFor: question => {if (!drafts.has(question)) drafts.set(question,{fields:{},choice:[]});return drafts.get(question);},
    renderCurrent() {context.renderCount++;},
    revealSend() {},
    selectionSlot() {},
    renderCount: 0,
    note(text) {notices.push(text);},
    review: null,
    prepared: null,
    showGuide: false,
    busy: false, inputs: 0,
    messageInput() {context.inputs++;},
    concept() {throw Error('Do not request another explanation while rendering.');},
    readable: value => String(value),
    state: {assessment:{narrative:{opener:false},journey:{samplesVisible:false}},guide:{flow:{}}},
    q: () => context.question,
  });
  // No fetch, timers, or provider transport are supplied. A reveal must remain
  // a local rendering effect on a complete, already accepted response.
  vm.runInContext(`${elementSource}\n${openingQuestionSource}\n${buttonSource}\n${revealSetSource}\n${questionSetSource}\n${renderingSource}\n${formSource}\n${referenceSource}\n${failureSource}\n${appendHistorySource}`, context,
    {filename: 'advisor.js:production-reveal-functions'});
  return {
    host, queries, notices,
    paint(items) { if (items !== undefined) context.history = items; context.paintHistory(); },
    append(requestId,askedQuestion,userWords,result) {return context.appendTurnHistory(requestId,askedQuestion,userWords,result);},
    paragraph(...args) { return context.paragraph(...args); },
    question(question,items) {
      if (items !== undefined) context.history = items;
      const questionHost = new FakeNode('section');
      current = questionHost;
      const presentation = context.questionPresentation(question);
      context.presentText(questionHost,question.question,presentation,'h1');
      context.renderForm(questionHost,question,presentation);
      return questionHost;
    },
    revealControl(control,reveal,offset) {return context.revealControl(control,reveal,offset);},
    presentation(question) {return context.questionPresentation(question);},
    control(text,presentation) {return context.presentControl(vm.runInContext('button',context)(text,() => {}),presentation);},
    draft(question) {return context.draftFor(question);},
    insuranceView(question) {return context.insuranceChoiceView(question,context.draftFor(question));},
    get renderCount() {return context.renderCount;},
    reference(visual,question = null,flags = {}) {
      Object.assign(context.state.assessment,{conversationOpen:false,intakePaused:false},flags);
      context.state.assessment.narrative.visual = visual;context.question = question;
      context.drawReference();return reference;
    },
    opening(items) {
      if (items !== undefined) context.history = items;
      const openingHost = new FakeNode('section');
      context.renderOpening(openingHost);
      return openingHost;
    },
    factBlock(facts, reveal) { return context.factBlock(facts, reveal); },
    turnVisual(result) {return context.turnVisual(result);},
    guide(visual,reveal = false,offset = 0) {return context.inlineGuide(visual,reveal,offset);},
    followups(prompts) {return context.educationFollowups(prompts);},
    message(text) {message.value = text;},
    get messageValue() {return message.value;},
    get messageFocused() {return message.focused;},
    get inputCount() {return context.inputs;},
    setBusy(value) {context.busy=value;},
    setReduced(value) { reducedMotion = value; },
    setFamiliarity(value,status = 'reported') {context.state.guide.fields = {'knowledge.general':{value,status}};},
  };
}

function currentHarness() {
  const nodes = new Map();
  const drafts = new Map(), calls = [];
  const node = id => {if (!nodes.has(id)) nodes.set(id,new FakeNode('div'));return nodes.get(id);};
  const context = vm.createContext({
    document:{createElement:tag => new FakeNode(tag)},
    $:node,
    matchMedia:() => ({matches:false}),
    history:[{reply:'Here is the answer to your question.'}],
    prepared:null,review:null,busy:false,openingRevealed:false,parkedMessages:[],selectedGoal:'',
    q:() => context.usableQuestion(context.state),
    draftFor:question => {const key = question.signature || question.id;if (!drafts.has(key)) drafts.set(key,{fields:{},choice:[]});return drafts.get(key);},
    selectionSlot() {},drawReference() {},setBusy() {},revealSend() {},concept() {},turn(...args) {calls.push(args);},reviewInformation() {},
    note(text) {node('status').textContent = text;},
  });
  vm.runInContext(`${elementSource}\n${openingQuestionSource}\n${buttonSource}\n${revealSetSource}\n${questionSetSource}\n${renderingSource}\n${formSource}\n${failureSource}\n${currentSource}`,context);
  return {
    node,calls,
    render(overrides = {},generated,reply = '',notice = '') {
      context.state = {assessment:{task:'timing',state:'missing_information',nextQuestion:null,narrative:{opener:false},journey:{samplesVisible:false},unresolvedReportedInputs:[],...overrides},guide:{fields:{}},record:{conversation:{editing:false}},generated,reply,notice};
      context.renderCurrent();return node('current');
    },
  };
}

test('the new greeting and subsequent assistant replies reveal, while user messages remain immediate', () => {
  const h = harness();
  const greeting = {reply: 'Hi, I’m Daylight. Let’s take this one step at a time.'};
  const response = {user: 'I turn 65 in November.', reply: 'We can work through the next steps together.'};
  h.paint([greeting, response]);
  assert.equal(h.host.children.length, 2);
  const answers = byClass(h.host, 'chat-daylight');
  assert.equal(answers.length, 2);
  assert.ok(answers.every(answer => byClass(answer, 'reveal-word').length > 1));
  const user = byClass(h.host, 'chat-user')[0];
  assert.equal(user.textContent, response.user);
  assert.equal(byClass(user, 'reveal-word').length, 0);
  assert.equal(byClass(user, 'sr-only').length, 0);
});

test('reviewed fact bodies reveal but their headings, Sources control and source links are immediate', () => {
  const h = harness();
  const facts = [{title: 'Part B', text: 'Part B helps cover medical care.',
    source: 'https://www.medicare.gov/coverage',
    sources: [{url: 'https://www.medicare.gov/basics', label: 'Medicare basics'}]}];
  h.paint([{reply: 'Here’s how that part works.', facts}]);
  const factHost = byClass(h.host, 'facts')[0];
  assert.equal(byClass(factHost, 'assistant-reveal').length, 1);
  assert.equal(visualText(byTag(factHost, 'p')[0]), facts[0].text);
  assert.equal(byTag(factHost, 'h2')[0].textContent, 'Part B');
  const answer = byClass(h.host,'chat-daylight')[0];
  const sources = byClass(answer, 'sources')[0];
  assert.equal(byClass(factHost,'sources').length,0,'Exchange citations belong after the complete answer.');
  assert.equal(byTag(sources, 'summary')[0].textContent, 'Sources');
  assert.equal(byTag(sources, 'a').length, 2);
  assert.equal(byClass(sources, 'reveal-word').length, 0);
  assert.equal(byClass(byTag(factHost, 'h2')[0], 'reveal-word').length, 0);
});

test('visual and accessible text each preserve every character, including spaces and HTML-like user content', () => {
  const h = harness();
  const text = '  Hello,  María.\nLet’s check <img src=x onerror=alert(1)> & your options.\t';
  const paragraph = h.paragraph(text, true);
  assert.equal(visualText(paragraph), text);
  assert.equal(accessibleText(paragraph), text);
  assert.equal(byClass(paragraph, 'sr-only').length, 1);
  const visual = byClass(paragraph, 'assistant-reveal')[0];
  assert.equal(visual.getAttribute('aria-hidden'), 'true');
  assert.equal(byTag(paragraph, 'img').length, 0, 'Model text must not become HTML.');
  assert.equal(byClass(paragraph, 'reveal-word').map(node => node.textContent).join(''), text);
});

test('the slower word timing stays bounded at 40ms per word and a 2000ms maximum relative delay', () => {
  const h = harness();
  const paragraph = h.paragraph(Array.from({length: 70}, (_, i) => `word${i}`).join(' '), true);
  const words = byClass(paragraph, 'reveal-word');
  assert.equal(words.length, 70);
  words.forEach((word, i) => assert.equal(word.style.getPropertyValue('--word-delay'), `${Math.min(i * 40, 2000)}ms`));
  assert.equal(words.at(-1).style.getPropertyValue('--word-delay'), '2000ms');
});

test('the reveal preserves the requested heading tag, class and sequential offset', () => {
  const h = harness();
  const heading = h.paragraph('A welcoming question for you.', true, 'h2', 'opening-title', 800);
  assert.equal(heading.tagName, 'H2');
  assert.equal(heading.className, 'opening-title');
  assert.equal(visualText(heading), 'A welcoming question for you.');
  assert.equal(accessibleText(heading), 'A welcoming question for you.');
  const words = byClass(heading, 'reveal-word');
  words.forEach((word, i) => assert.equal(word.style.getPropertyValue('--word-delay'), `${800 + i * 40}ms`));
});

test('the complete opening question, example and reassurance reveal in sequence after the greeting', () => {
  const h = harness();
  const greeting = {reply: 'Hi, I’m Daylight. Let’s take this one step at a time.'};
  const opening = h.opening([greeting]);
  const lines = [
    ['H2', '', 'What has you thinking about Medicare today?'],
    ['P', 'intro-example', 'For example: turning 65, leaving work, reviewing your coverage, or helping someone else.'],
    ['P', 'intro-help', 'A sentence or two is enough.'],
  ];
  assert.equal(opening.children.length, 3);
  let offset = Math.min(greeting.reply.match(/\S+/g).length * 40, 2000) + 120;
  lines.forEach(([tag, cls, text], index) => {
    const line = opening.children[index];
    assert.equal(line.tagName, tag);
    assert.equal(line.className, cls);
    assert.equal(visualText(line), text);
    assert.equal(accessibleText(line), text);
    const words = byClass(line, 'reveal-word');
    assert.equal(words.length, text.match(/\S+/g).length);
    words.forEach((word, i) => assert.equal(word.style.getPropertyValue('--word-delay'), `${offset + i * 40}ms`));
    offset += words.length * 40 + 100;
  });
});

test('repainting the opening never replays its question, examples or reassurance', () => {
  const h = harness();
  const first = h.opening([]);
  assert.ok(byClass(first, 'reveal-word').length > 0);
  const second = h.opening();
  assert.equal(byClass(second, 'reveal-word').length, 0);
  assert.equal(byClass(second, 'sr-only').length, 0);
  assert.equal(visualText(second), visualText(first));
  assert.equal(accessibleText(second), accessibleText(first));
});

test('reduced motion leaves the complete opening readable immediately and does not replay later', () => {
  const h = harness(true);
  const first = h.opening([]);
  assert.equal(first.children.length, 3);
  assert.equal(byClass(first, 'reveal-word').length, 0);
  h.setReduced(false);
  const second = h.opening();
  assert.equal(byClass(second, 'reveal-word').length, 0);
  assert.equal(visualText(second), visualText(first));
});

test('the actual loaded stylesheet retains the 120ms fade and disables animation for reduced motion', () => {
  const html = fs.readFileSync(path.join(web, 'index.html'), 'utf8');
  const css = fs.readFileSync(path.join(web, 'adaptive.css'), 'utf8');
  assert.match(html, /<link\b[^>]*href="\/adaptive\.css"[^>]*>/);
  assert.match(css, /body\.chat-mode \.reveal-word\{animation:assistant-word \.12s ease-out both!important;animation-delay:var\(--word-delay,0ms\)!important\}/);
  assert.match(css, /@keyframes assistant-word\{from\{opacity:0\}to\{opacity:1\}\}/);
  assert.match(css, /@media\(prefers-reduced-motion:reduce\)\{body\.chat-mode \.reveal-word\{animation:none!important\}\}/);
});

test('reduced motion renders complete plain text for greetings, replies and facts', () => {
  const h = harness(true);
  const greeting = {reply: 'Welcome to Daylight.'};
  const response = {user: 'Tell me about Part B.', reply: 'We can start there.',
    facts: [{title: 'Part B', text: 'This is the reviewed explanation.'}]};
  h.paint([greeting, response]);
  assert.equal(byClass(h.host, 'reveal-word').length, 0);
  assert.equal(byClass(h.host, 'sr-only').length, 0);
  assert.equal(byClass(h.host, 'assistant-reveal').length, 0);
  assert.equal(byClass(h.host, 'chat-daylight')[0].textContent, greeting.reply);
  assert.ok(h.host.textContent.includes(response.facts[0].text));
  assert.ok(h.queries.every(query => query === '(prefers-reduced-motion: reduce)'));
});

test('ordinary repaint preserves existing history nodes and never restarts an earlier reveal', () => {
  const h = harness();
  const greeting = {reply: 'Welcome to Daylight.'};
  h.paint([greeting]);
  const exchange = h.host.children[0];
  const firstWord = byClass(exchange, 'reveal-word')[0];
  h.paint();
  h.paint();
  assert.equal(h.host.children.length, 1);
  assert.equal(h.host.children[0], exchange);
  assert.equal(byClass(h.host.children[0], 'reveal-word')[0], firstWord);
});

test('completed words retire the animation class so leaving and returning to chat cannot replay them', () => {
  const h = harness();
  const reply = {reply: 'A greeting that should animate only once.'};
  h.paint([reply]);
  const exchange = h.host.children[0];
  const words = byClass(exchange, 'reveal-word');
  assert.ok(words.length > 1);
  for (const word of words) {
    assert.equal(typeof word.onanimationend, 'function');
    word.dispatchEvent({type: 'animationend', animationName: 'assistant-word'});
    assert.equal(word.className, '', 'A completed word must no longer match the body.chat-mode animation selector.');
    assert.equal(word.onanimationend, null);
    assert.equal(word.onanimationcancel, null);
  }
  // Back and Get started toggle body.chat-mode without recreating history.
  // Node identity alone did not prevent CSS from restarting the animation.
  h.paint();
  assert.equal(h.host.children[0], exchange);
  assert.equal(byClass(exchange, 'reveal-word').length, 0);
  assert.equal(visualText(exchange), reply.reply);
  assert.equal(accessibleText(exchange), reply.reply);
});

test('cancelled words also retire their animation class and remain readable on return', () => {
  const h = harness();
  const item = {reply: 'This reply is still arriving.',
    facts: [{title: 'A reviewed fact', text: 'Its full text remains available.'}]};
  h.paint([item]);
  const exchange = h.host.children[0];
  const visibleBefore = visualText(exchange);
  const accessibleBefore = accessibleText(exchange);
  const words = byClass(exchange, 'reveal-word');
  for (const word of words) {
    assert.equal(typeof word.onanimationcancel, 'function');
    word.dispatchEvent({type: 'animationcancel', animationName: 'assistant-word'});
    assert.equal(word.className, '');
    assert.equal(word.onanimationend, null);
    assert.equal(word.onanimationcancel, null);
  }
  h.paint();
  assert.equal(h.host.children[0], exchange);
  assert.equal(byClass(exchange, 'reveal-word').length, 0);
  assert.equal(visualText(exchange), visibleBefore);
  assert.equal(accessibleText(exchange), accessibleBefore);
});

test('appending a reply preserves previous node identity and reveals only the new answer', () => {
  const h = harness();
  const greeting = {reply: 'Welcome to Daylight.'};
  const items = [greeting];
  h.paint(items);
  const oldNode = h.host.children[0];
  items.push({user: 'I’m ready.', reply: 'Let’s work through your next step.'});
  h.paint();
  assert.equal(h.host.children[0], oldNode);
  assert.equal(h.host.children.length, 2);
  assert.ok(byClass(h.host.children[1], 'reveal-word').length > 0);
});

test('a history rebuild shows previously revealed objects immediately and reveals new objects once', () => {
  const h = harness();
  const first = {reply: 'An earlier answer.'};
  h.paint([first]);
  const replacement = {reply: 'A new greeting.'};
  h.paint([replacement, first]);
  assert.ok(byClass(h.host.children[0], 'reveal-word').length > 0);
  assert.equal(byClass(h.host.children[1], 'reveal-word').length, 0);
  assert.equal(h.host.children[1].textContent, first.reply);
  h.paint([]);
  assert.equal(h.host.children.length, 0);
  h.paint([first]);
  assert.equal(byClass(h.host, 'reveal-word').length, 0);
  assert.equal(h.host.textContent, first.reply);
});

test('a reply first displayed with reduced motion never animates when the preference later changes', () => {
  const h = harness(true);
  const first = {reply: 'Already read without motion.'};
  h.paint([first]);
  h.setReduced(false);
  h.paint([]);
  h.paint([first]);
  assert.equal(byClass(h.host, 'reveal-word').length, 0);
  const second = {reply: 'A new answer may reveal.'};
  h.paint([first, second]);
  assert.ok(byClass(h.host.children[1], 'reveal-word').length > 0);
});

test('a user-only exchange stays immediate and an empty reply does not create an assistant message', () => {
  const h = harness();
  h.paint([{user: 'A short report.', reply: '', facts: []}]);
  assert.equal(byClass(h.host, 'chat-user').length, 1);
  assert.equal(byClass(h.host, 'chat-daylight').length, 0);
  assert.equal(byClass(h.host, 'reveal-word').length, 0);
});

test('static explanations remain immediate and reveal does not weaken source URL filtering', () => {
  const h = harness();
  const facts = [{title: 'A source-backed explanation', text: 'Complete explanation.',
    sources: [{url: 'javascript:alert(1)', label: 'Unsafe'}, {url: 'http://example.com', label: 'Insecure'},
      {url: 'https://www.medicare.gov/basics', label: 'Official source'}]}];
  const staticFacts = h.factBlock(facts);
  assert.equal(byClass(staticFacts, 'reveal-word').length, 0);
  assert.equal(byTag(staticFacts, 'p')[0].textContent, facts[0].text);
  const links = byTag(staticFacts, 'a');
  assert.equal(links.length, 1);
  assert.equal(links[0].href, 'https://www.medicare.gov/basics');
  assert.equal(links[0].rel, 'noopener noreferrer');
});

test('a new current question and its answer buttons follow the reply, while choosing does not replay them', () => {
  const h = harness();
  const question = {id:'T02',question:'How much have you learned about Medicare so far?',choices:[['new','I’m starting from scratch'],['some','I’ve done some research']],fields:[],multi:false};
  const reply = 'We can start with the basics and take this at your pace.';
  const first = h.question(question,[{reply}]);
  const headingWords = byClass(byTag(first,'h1')[0],'reveal-word');
  assert.ok(headingWords.length > 1);
  const expectedOffset = Math.min((reply.match(/\S+/g).length - 1)*40,2000)+220;
  assert.equal(headingWords[0].style.getPropertyValue('--word-delay'),`${expectedOffset}ms`);
  const buttons = byTag(first,'button');
  assert.equal(buttons.length,4);
  assert.ok(buttons.every(button => button.className.includes('reveal-word')));
  assert.ok(Number.parseInt(buttons[0].style.getPropertyValue('--word-delay')) > Number.parseInt(headingWords.at(-1).style.getPropertyValue('--word-delay')));
  buttons.forEach((button,i) => assert.equal(Number.parseInt(button.style.getPropertyValue('--word-delay')),Number.parseInt(buttons[0].style.getPropertyValue('--word-delay'))+i*140));
  buttons[0].onclick();
  assert.equal(h.draft(question).choice[0],'new');
  assert.equal(h.renderCount,1,'Selection updates its state without sending an answer.');
  const second = h.question(question);
  assert.equal(byClass(second,'reveal-word').length,0);
  assert.equal(byTag(second,'button')[0].getAttribute('aria-pressed'),'true');
  const newTurnQuestion = {...question};
  assert.ok(byClass(h.question(newTurnQuestion,[{reply:'What would help next?'}]),'reveal-word').length > 0);
});

test('question text and finite answer buttons are immediately available with reduced motion', () => {
  const h = harness(true);
  const question = {id:'T02',question:'How familiar are you with Medicare?',choices:[['new','New to Medicare']],fields:[],multi:false};
  const first = h.question(question,[{reply:'We can start there.'}]);
  assert.equal(byClass(first,'reveal-word').length,0);
  assert.equal(accessibleText(byTag(first,'h1')[0]),question.question);
  assert.equal(accessibleText(byTag(first,'button')[0]),'New to Medicare');
  h.setReduced(false);
  assert.equal(byClass(h.question(question),'reveal-word').length,0);
});

test('control reveal preserves its accessible name, classes and keyboard visibility after completion or cancellation', () => {
  const h = harness();
  for (const event of ['animationend','animationcancel','focus']) {
    const control = new FakeNode('button');control.className = 'choice';control.textContent = 'I’ve done some research';
    h.revealControl(control,true,840);
    assert.equal(control.style.getPropertyValue('--word-delay'),'840ms');
    assert.equal(accessibleText(control),'I’ve done some research');
    assert.equal(byClass(control,'sr-only').length,0,'A native button supplies one complete name.');
    control.dispatchEvent({type:event});
    assert.equal(control.className,'choice');
    assert.equal(control.onanimationend,null);
    assert.equal(control.onanimationcancel,null);
    assert.equal(control.onfocus,null);
  }
});

test('opening shortcut buttons continue the opening sequence and do not animate on rerender', () => {
  const h = harness();
  const presentation = h.presentation({});
  presentation.offset = 2100;
  const first = h.control('Understand Medicare',presentation);
  const second = h.control('Find coverage',presentation);
  assert.equal(first.style.getPropertyValue('--word-delay'),'2100ms');
  assert.equal(second.style.getPropertyValue('--word-delay'),'2240ms');
  assert.equal(accessibleText(first),'Understand Medicare');
  const immediate = h.control('Understand Medicare',{reveal:false,offset:2100});
  assert.equal(byClass(immediate,'reveal-word').length,0);
  assert.match(source,/presentText\(\$\('shortcuts'\),'Need a starting point\?',openingPresentation/);
  assert.match(source,/row\.append\(presentControl\(b,openingPresentation\)\)/);
});

test('coverage timing uses one chat composer and genuine choices rather than another month input', () => {
  const h = harness();
  const question = {id:'T04',question:'When would you like Medicare coverage to start?',choices:[['already','I already have Medicare'],['asap','As soon as possible']],fields:[{key:'month',type:'text',label:'Month and year'}],multi:false};
  const rendered = h.question(question,[]);
  for (const tag of ['input','select','textarea']) assert.equal(byTag(rendered,tag).length,0);
  assert.deepEqual(byTag(rendered,'button').map(button => button.textContent),['I already have Medicare','As soon as possible','I don’t know','Check later']);
  byTag(rendered,'button')[1].onclick();
  assert.equal(h.draft(question).choice[0],'asap');
  assert.equal(h.renderCount,1);
});

test('finite field options remain explicit buttons and preserve each field independently', () => {
  const h = harness();
  const question = {id:'RC23',question:'What fill details do you know?',choices:[],fields:[{key:'quantity',type:'text',label:'Quantity'},{key:'daysSupply',type:'select',label:'Days supply',options:[['30','30 days'],['90','90 days']]},{key:'channel',type:'select',label:'How you fill it',options:[['retail','Retail pharmacy'],['mail','Mail order']]}],multi:false};
  const rendered = h.question(question,[]);
  assert.equal(byTag(rendered,'input').length+byTag(rendered,'select').length+byTag(rendered,'textarea').length,0);
  const buttons = byTag(rendered,'button');
  buttons.find(button => button.textContent === '30 days').onclick();
  buttons.find(button => button.textContent === 'Mail order').onclick();
  assert.equal(h.draft(question).fields.daysSupply,'30');
  assert.equal(h.draft(question).fields.channel,'mail');
  assert.equal(h.draft(question).fields.quantity,undefined);
});

test('historical diagrams stay absent beneath intake while current teaching has an inline guide', () => {
  const h = harness();
  const timing = {kind:'timeline',title:'Your Medicare timing',items:[['65th birthday','November'],['Current insurance','Not stated'],['Preferred start','Not stated']]};
  for (const visual of [timing,{kind:'basics',title:'A place to start'},{kind:'parts',title:'Original Medicare'},{kind:'routes',title:'Two coverage paths'}]) {
    const reference = h.reference(visual,{id:'RC11'});
    assert.equal(reference.hidden,true);
    assert.equal(reference.children.length,0,'Past learning cannot attach a graphic to an unrelated COBRA question.');
  }
  const visual = h.turnVisual({advisor:{teachingFactIds:['parts']}});
  const guide = h.guide(visual);
  assert.equal(byTag(guide,'button').length,2);
  assert.equal(byTag(guide,'details').length,0,'The teaching graphic is inline, not another disclosure.');
  assert.ok(guide.textContent.includes('Part B'));
});

test('a final current-turn timing picture includes only known reports and keeps unknown fields out', () => {
  const h = harness();
  const result = {advisor:{teachingFactIds:['dates']},assessment:{state:'external_validation_held',nextQuestion:null,
    conversationOpen:false,intakePaused:false,narrative:{visual:{kind:'timeline',title:'Your coverage timeline',
      items:[['Job ends','November 2026'],['Work insurance ends','Still open'],['Preferred start','December 2026']]}}}};
  const picture = h.guide(h.turnVisual(result));
  assert.equal(byTag(picture,'li').length,2);
  assert.ok(!picture.textContent.includes('Still open'));
  assert.ok(picture.textContent.includes('Dates and coverage still need checking.'));
  assert.equal(byTag(picture,'details').length,0);
});

test('intake footer controls stay hidden and profile review is offered with the final conversation summary', () => {
  const html = fs.readFileSync(path.join(web,'index.html'),'utf8');
  for (const id of ['back','review','prepare','samples']) {
    assert.match(html,new RegExp(`<button id="${id}"[^>]* hidden`));
  }
  assert.match(source,/for \(const id of \['back','review','prepare','samples'\]\) \$\(id\)\.hidden = true/);
  const renderCurrent = source.slice(source.indexOf('  function renderCurrent('),source.indexOf('  function composerHint('));
  assert.equal((renderCurrent.match(/Review your profile/g) || []).length,1);
  assert.ok(renderCurrent.indexOf('Review your profile') > renderCurrent.indexOf('Here’s where we are'));
  assert.doesNotMatch(html,/id="ai-notice"|aria-describedby="ai-notice"/);
  const privacySource = source.slice(source.indexOf('  function privacy('),source.indexOf("  $('composer').onsubmit"));
  assert.match(privacySource,/Send uses OpenAI\. When you choose Send, your message, recent conversation and relevant profile details go to OpenAI\./);
  assert.match(html,/id="privacy"[^>]*>Privacy &amp; saving</);
});

test('an educational intake pause leaves the generated answer and chat composer without a false final review', () => {
  const h = currentHarness();
  for (const assessment of [{intakePaused:true},{state:'education',task:'learn'},{state:'missing_information'},{state:'external_validation_held',conversationOpen:true}]) {
    const panel = h.render(assessment,{status:'complete',move:'explain'});
    assert.equal(panel.children.length,0);
    assert.equal(h.node('composer').hidden,false);
    for (const id of ['back','review','prepare','samples']) assert.equal(h.node(id).hidden,true);
  }
});

test('generated questions own their explanation, while a non-AI question retains its useful why', () => {
  const h = currentHarness();
  const question = {id:'T04',question:'When would you like coverage to start?',why:'Your desired start can differ from the end of current insurance.',choices:[['already','I already have Medicare']],fields:[{key:'month',type:'text'}]};
  const generated = h.render({nextQuestion:question},{status:'complete',move:'T04'});
  assert.ok(!visualText(generated).includes(question.why));
  const structured = h.render({nextQuestion:{...question}},{status:'unavailable'});
  assert.ok(visualText(structured).includes(question.why));
  assert.equal(byTag(structured,'input').length+byTag(structured,'textarea').length,0);
});

test('the real final summary reveals its text and optional actions once, including profile review', () => {
  const h = currentHarness();
  const summary = h.render({state:'external_validation_held',journey:{samplesVisible:false,summary:'Your reported information is ready for the next checks.'}});
  assert.ok(byClass(byTag(summary,'h1')[0],'reveal-word').length > 0);
  assert.ok(byTag(summary,'button').every(button => button.className.includes('reveal-word')));
  const labels = byTag(summary,'button').map(button => accessibleText(button));
  assert.ok(labels.includes('Review your profile'));
  assert.ok(labels.includes('Prepare my next steps'));
  assert.ok(labels.includes('Browse sample plans'));
});

test('old free-text reports and stale records cannot activate Send as an invisible selected answer', () => {
  const draftSource = source.slice(source.indexOf('  function draftFor('),source.indexOf('  function syncSend('));
  const context = vm.createContext({drafts:new Map(),baseline:[{id:'T04',field:'coverage.requestedStart'},{id:'T06',field:'needs.providersStatus'}],state:{assessment:{task:'timing'},guide:{fields:{'coverage.requestedStart':{status:'reported',value:'month'},'coverage.requestedStartMonth':{status:'stale',value:'2027-01'},'needs.providersStatus':{status:'reported',value:'list'},'needs.providers':{status:'stale',value:'Dr Example'}}},record:{facts:{RC23:{stale:true,value:{items:[{entity:'medicine-1',daysSupply:'30'}]}}}}}});
  vm.runInContext(draftSource,context);
  for (const question of [
    {id:'T04',signature:'T04.profile.month',entity:'profile',choices:[['already','I already have Medicare']],fields:[{key:'month',type:'text'}]},
    {id:'T06',signature:'T06.profile.text',entity:'profile',choices:[['none','No doctors to include']],fields:[{key:'text',type:'textarea'}]},
    {id:'RC23',signature:'RC23.medicine-1.daysSupply',entity:'medicine-1',choices:[],fields:[{key:'daysSupply',type:'select',options:[['30','30 days']]}]},
  ]) {
    const draft = context.draftFor(question);
    assert.equal(draft.choice.length,0);
    assert.equal(Object.keys(draft.fields).length,0);
    assert.equal(context.hasFormAnswer(question),false);
  }
  assert.equal(context.state.guide.fields['needs.providers'].value,'Dr Example','Stored profile data remains intact.');
});

test('an answered question remains plain assistant history before the user answer without replaying its text', () => {
  const h = harness();
  const greeting = {reply:'Hi, I’m Daylight.'};
  h.paint([greeting]);const oldNode = h.host.children[0];
  const item = {requestId:'turn-1',askedQuestion:'When would you like Medicare coverage to start?',user:'ASAP!',reply:'We can look at what needs checking next.'};
  h.paint([greeting,item]);
  assert.equal(h.host.children[0],oldNode,'Appending question history must preserve all existing nodes.');
  const exchange = h.host.children[1];
  assert.equal(exchange.children.length,3);
  const [asked,user,reply] = exchange.children;
  assert.equal(asked.getAttribute('aria-label'),'Daylight');
  assert.equal(asked.textContent,item.askedQuestion);
  assert.equal(accessibleText(asked),item.askedQuestion);
  assert.equal(byClass(asked,'reveal-word').length,0);
  assert.equal(byClass(asked,'sr-only').length,0);
  assert.equal(user.getAttribute('aria-label'),'You');
  assert.equal(user.textContent,item.user);
  assert.ok(byClass(reply,'reveal-word').length > 0,'Only the new assistant reply reveals.');
  h.paint();h.paint();
  assert.equal(h.host.children[1],exchange);
  assert.equal(byTag(exchange,'article').filter(article => accessibleText(article) === item.askedQuestion).length,1);
});

test('history rebuilds preserve answered questions exactly once as complete accessible plain text', () => {
  const h = harness();
  const item = {requestId:'turn-1',askedQuestion:'How familiar are you with Medicare?',user:'I know a little.',reply:'We can build from there.'};
  h.paint([item]);
  h.paint([]);h.paint([item]);
  assert.equal(h.host.children.length,1);
  assert.equal(byClass(h.host,'reveal-word').length,0);
  const articles = byTag(h.host,'article');
  assert.equal(articles.filter(article => accessibleText(article) === item.askedQuestion).length,1);
  assert.equal(visualText(articles[0]),item.askedQuestion);
  assert.equal(accessibleText(articles[1]),item.user);
  assert.equal(accessibleText(articles[2]),item.reply);
});

test('a generation failure keeps the server’s actual next question and choices available without adding its notice to the panel', () => {
  const h = currentHarness();
  const question = {id:'T04',question:'When would you like Medicare coverage to start?',choices:[['asap','As soon as possible'],['already','I already have Medicare']],fields:[{key:'month',type:'text'}]};
  const notice = 'Your details are here. I couldn’t finish the response just now, but we can continue.';
  const panel = h.render({nextQuestion:question},{status:'unavailable'},'',notice);
  assert.equal(visualText(byTag(panel,'h1')[0]),question.question);
  assert.ok(byTag(panel,'button').some(button => accessibleText(button) === 'As soon as possible'));
  assert.ok(!visualText(panel).includes(notice));
  assert.equal(byTag(panel,'textarea').length+byTag(panel,'input').length,0);
});

test('unavailable generation with no valid question cannot render a false completion or turn the notice into a heading', () => {
  const h = currentHarness();
  const notice = 'The response could not finish.';
  for (const question of [null,{id:'T04',question:notice,choices:[],fields:[]}]) {
    const panel = h.render({state:'external_validation_held',nextQuestion:question},{status:'unavailable'},'',notice);
    assert.equal(panel.children.length,0);
    assert.equal(h.node('composer').hidden,false);
    assert.ok(!panel.textContent.includes('Review your profile'));
  }
});

test('an open learning conversation cannot imply a final timing summary but can show current teaching', () => {
  const h = harness();
  const timing = {kind:'timeline',title:'Your coverage timeline',items:[['Job ends','November 2026'],['Preferred start','December 2026']]};
  const assessment = {narrative:{visual:timing},state:'external_validation_held',nextQuestion:null};
  assert.equal(h.reference(timing,null,{conversationOpen:true,state:'external_validation_held'}).hidden,true);
  assert.equal(h.turnVisual({advisor:{teachingFactIds:['dates']},assessment:{...assessment,conversationOpen:true}}),null);
  const guide = h.guide(h.turnVisual({advisor:{teachingFactIds:['parts']},assessment:{...assessment,conversationOpen:true}}));
  assert.ok(guide.textContent.includes('Part A'));
  assert.ok(guide.textContent.includes('Part B'));
  assert.equal(byTag(guide,'details').length,0);
});

test('service notices update one live status instead of being announced by competing regions', () => {
  const noteSource = source.match(/^  function note\(text\) \{.*\}$/m)?.[0];
  assert.ok(noteSource,'Exercise the production notice function.');
  const writes = [], nodes = new Map();
  const context = vm.createContext({$:id => {
    if (!nodes.has(id)) nodes.set(id,{set textContent(value) {writes.push({id,value});}});
    return nodes.get(id);
  }});
  vm.runInContext(noteSource,context);
  const notice = 'The response could not finish.';
  context.note(notice);
  assert.deepEqual(writes,[{id:'status',value:notice}],'One failure must cause one status announcement.');
  context.note('');
  assert.deepEqual(writes.at(-1),{id:'status',value:''});
  assert.equal(nodes.size,1);
  const html = fs.readFileSync(path.join(web,'index.html'),'utf8');
  assert.match(html,/<p id="status"[^>]*role="status"/);
  assert.doesNotMatch(html,/id="announcer"/);
  assert.match(html,/id="history"[^>]*role="log"[^>]*aria-live="polite"/,'The accessible conversation log remains in place.');
});

function currentInsuranceQuestion() {
  const baseline = JSON.parse(fs.readFileSync(path.join(web,'baseline-content.json'),'utf8')).find(question => question.id === 'T05');
  return {id:'T05',signature:'T05.profile.choice',question:'What health insurance do you have now?',choices:baseline.options,fields:[],multi:true,entity:'profile'};
}

test('a novice sees six ordinary-language insurance families without new preselected reports', () => {
  const h = harness(), question = currentInsuranceQuestion();
  h.setFamiliarity('new');
  const panel = h.question(question,[]), buttons = byTag(panel,'button');
  assert.deepEqual(buttons.map(accessibleText),['Through a current job','From a former job','Medicare','VA, TRICARE or military coverage','Medicaid','No health insurance','I don’t know','Check later']);
  assert.equal(h.draft(question).choice.length,0);
  assert.ok(buttons.every(button => button.getAttribute('aria-pressed') !== 'true'));
  for (const label of ['From a former job','Medicare']) {
    const group = buttons.find(button => accessibleText(button) === label);
    assert.equal(group.getAttribute('aria-expanded'),'false');
    assert.equal(group.getAttribute('aria-pressed'),null,'An answer family is disclosure, not a reported answer.');
  }
});

test('local insurance refinement preserves every approved distinction and sends no aggregate fact', () => {
  const h = harness(), question = currentInsuranceQuestion(), all = new Set();
  const panel = h.question(question,[]);
  for (const item of h.insuranceView(question).items) if (item.value) all.add(item.value);
  for (const label of ['From a former job','Medicare']) {
    byTag(panel,'button').find(button => accessibleText(button) === label).onclick();
    assert.equal(h.draft(question).choice.length,0,'Opening a group must not assert retiree, Medicare or another coverage fact.');
    const expanded = h.question(question), view = h.insuranceView(question);
    for (const [id] of view.details) all.add(id);
    assert.ok(byTag(expanded,'button').some(button => accessibleText(button) === 'I don’t know'));
    assert.ok(byTag(expanded,'button').some(button => accessibleText(button) === 'Check later'));
  }
  assert.deepEqual([...all].sort(),question.choices.filter(([id]) => id !== 'unknown').map(([id]) => id).sort());
  assert.equal(h.draft(question).choice.length,0);
  assert.equal(h.renderCount,2,'Local disclosures only rerender; the harness has no network transport.');
});

test('multiple precise insurance selections stay visible and correctable across local group changes', () => {
  const h = harness(), question = currentInsuranceQuestion();
  const choose = label => {const panel = h.question(question);byTag(panel,'button').find(button => accessibleText(button) === label).onclick();};
  choose('From a former job');choose('Retiree health plan');choose('Medicare');choose('Medicare Supplement / Medigap');
  const expanded = h.question(question);
  for (const label of ['Retiree health plan','Medicare Supplement / Medigap']) assert.equal(byTag(expanded,'button').find(button => accessibleText(button) === label).getAttribute('aria-pressed'),'true');
  assert.deepEqual(Array.from(h.draft(question).choice),['retiree','medigap']);
  choose('Medicare');
  const collapsed = h.question(question);
  for (const label of ['Retiree health plan','Medicare Supplement / Medigap']) assert.equal(byTag(collapsed,'button').find(button => accessibleText(button) === label).getAttribute('aria-pressed'),'true');
  choose('No health insurance');
  assert.deepEqual(Array.from(h.draft(question).choice),['none'],'An explicit none replaces mutually exclusive reports.');
});

test('selecting Medicaid closes an unrelated open Medicare refinement without asserting Medicare', () => {
  const h = harness(), question = currentInsuranceQuestion();
  const choose = label => byTag(h.question(question),'button').find(button => accessibleText(button) === label).onclick();
  choose('Medicare');
  assert.equal(h.insuranceView(question).details.length,4);
  choose('Medicaid');
  assert.deepEqual(Array.from(h.draft(question).choice),['medicaid']);
  assert.equal(h.draft(question).coverageGroup,'');
  assert.equal(h.insuranceView(question).details.length,0);
  assert.equal(byTag(h.question(question),'button').some(button => accessibleText(button) === 'Original Medicare (Parts A and B)'),false);
});

test('collapsing unrelated insurance details preserves explicitly selected Medicare plus Medicaid', () => {
  const h = harness(), question = currentInsuranceQuestion();
  const choose = label => byTag(h.question(question),'button').find(button => accessibleText(button) === label).onclick();
  choose('Medicare');choose('Original Medicare (Parts A and B)');choose('Medicaid');
  assert.deepEqual(Array.from(h.draft(question).choice),['original','medicaid']);
  assert.equal(h.insuranceView(question).details.length,0);
  const original = byTag(h.question(question),'button').find(button => accessibleText(button) === 'Original Medicare (Parts A and B)');
  assert.equal(original.getAttribute('aria-pressed'),'true');
});

test('unknown and defer close the open insurance refinement and clear finite draft data', () => {
  for (const label of ['I don’t know','Check later']) {
    const h = harness(), question = currentInsuranceQuestion();
    const choose = text => byTag(h.question(question),'button').find(button => accessibleText(button) === text).onclick();
    choose('Medicare');choose('Medicare Advantage (Part C)');
    h.draft(question).fields = {obsolete:'value'};
    choose(label);
    assert.equal(h.draft(question).coverageGroup,'');
    assert.equal(h.draft(question).choice.length,0);
    assert.equal(Object.keys(h.draft(question).fields).length,0);
    assert.equal(h.insuranceView(question).details.length,0);
  }
});

test('ambiguous current Medicare paths ask for clarification without changing a prior selection', () => {
  for (const pair of [['original','advantage'],['advantage','original'],['medigap','advantage'],['advantage','medigap']]) {
    const h = harness(), question = currentInsuranceQuestion();
    const choose = value => {
      if (h.draft(question).coverageGroup !== 'medicare') byTag(h.question(question),'button').find(button => accessibleText(button) === 'Medicare').onclick();
      const label = h.insuranceView(question).details.find(([id]) => id === value)[1];
      byTag(h.question(question),'button').find(button => accessibleText(button) === label).onclick();
    };
    choose(pair[0]);choose(pair[1]);
    assert.deepEqual(Array.from(h.draft(question).choice),[pair[0]]);
    assert.match(h.notices.at(-1),/Which Medicare coverage is current/);
    assert.equal(h.messageFocused,true);
  }
});

test('a longer spoken priority report can be reduced one button at a time without discarding the report', () => {
  const h = harness(), question = {id:'T10',signature:'T10.profile.choice',question:'What matters most?',max:3,multi:true,fields:[],choices:[['doctors','Doctors'],['drugs','Medicines'],['total_cost','Total cost'],['travel','Travel'],['other','Something else']]};
  h.draft(question).choice = ['doctors','drugs','total_cost','travel','other'];
  for (const label of ['Travel','Something else']) byTag(h.question(question),'button').find(button => accessibleText(button) === label).onclick();
  assert.deepEqual(Array.from(h.draft(question).choice),['doctors','drugs','total_cost']);
});

test('comfortable users can see the complete exact list, while unresolved familiarity keeps the simple view', () => {
  const h = harness(), question = currentInsuranceQuestion();
  h.setFamiliarity('comfortable');
  const complete = h.question(question), buttons = byTag(complete,'button');
  assert.equal(buttons.length,12);
  assert.ok(buttons.every(button => button.getAttribute('aria-expanded') === null));
  assert.ok(buttons.some(button => accessibleText(button) === 'Retiree health plan'));
  assert.ok(buttons.some(button => accessibleText(button) === 'COBRA'));
  assert.equal(h.draft(question).choice.length,0);
  for (const status of ['unknown','skipped','stale']) {
    h.setFamiliarity('comfortable',status);
    assert.equal(byTag(h.question(question),'button').length,8);
  }
});

test('typed draft blocks conflicting insurance selections until it is sent or cleared', () => {
  const h = currentHarness(), question = currentInsuranceQuestion(), draft = 'I also have a question about my wife’s coverage.';
  h.node('message').value = draft;
  const first = h.render({nextQuestion:question});
  assert.ok(byClass(first,'reveal-word').length > 0);
  byTag(first,'button').find(button => accessibleText(button) === 'Medicare').onclick();
  assert.equal(h.node('current'),first,'A blocked selection must not redraw or replay the question.');
  assert.equal(h.node('message').value,draft);
  assert.equal(h.node('message').focused,true);
  assert.match(h.node('status').textContent,/[Cc]lear.*choose/);
  assert.equal(first.querySelector('[data-coverage-group="medicare"]').getAttribute('aria-expanded'),'false');
  assert.equal(h.calls.length,0,'Neither typing nor blocked selection contacts AI.');
  h.node('message').value = '';
  byTag(first,'button').find(button => accessibleText(button) === 'Medicare').onclick();
  const refined = h.node('current');
  assert.equal(refined.querySelector('[data-coverage-group="medicare"]').focused,true);
  assert.equal(refined.querySelector('[data-coverage-group="medicare"]').focusOptions.preventScroll,true);
  assert.equal(byClass(refined,'reveal-word').length,0,'Clearing a draft permits local refinement without replaying words.');
  byTag(refined,'button').find(button => accessibleText(button) === 'Medicare Advantage (Part C)').onclick();
  assert.equal(h.calls.length,0);
});

test('new service-owned insurance distinctions cannot disappear from the grouped view', () => {
  const h = harness(), question = currentInsuranceQuestion();
  question.choices.push(['another_supported_type','Another supported coverage type']);
  const panel = h.question(question,[]);
  assert.ok(byTag(panel,'button').some(button => accessibleText(button) === 'Another supported coverage type'));
});

test('the compact topic track follows actual questions and teaching rather than accumulated intake completion', () => {
  const host = new FakeNode('nav');
  const context = vm.createContext({document:{createElement:tag => new FakeNode(tag)},$:() => host,prepared:null,review:null,history:[],q:() => context.state.assessment.nextQuestion});
  vm.runInContext(`${elementSource}\n${focusSource}`,context);
  const track = (question,advisor,facts = []) => {
    context.state = {assessment:{nextQuestion:question,task:'compare',narrative:{},journey:{phase:3,samplesVisible:false}},advisor};context.history = [{facts}];context.phaseTrack();
    return byTag(host,'li').find(node => node.getAttribute('aria-current') === 'true')?.textContent;
  };
  assert.equal(track({id:'T05'}),'Your situation');
  assert.equal(track({id:'T02'}),'Medicare basics');
  assert.equal(track({id:'T09'}),'Coverage options');
  assert.equal(track({id:'T04'}),'Your situation','Focus can return to circumstances without losing reports.');
  assert.equal(track(null,{topic:'learning'}),'Medicare basics');
  assert.equal(track(null,{topic:'coverage_paths'}),'Coverage options');
  assert.equal(track(null,null,[{id:'partb'}]),'Medicare basics');
  assert.equal(byTag(host,'li').length,4);
  assert.equal(byTag(host,'progress').length,1);
  assert.equal(byTag(host,'progress')[0].getAttribute('aria-hidden'),'true','The line is not announced as a percent complete.');
  assert.ok(!byTag(host,'li').some(node => node.getAttribute('aria-current') === 'step'));
  assert.match(host.getAttribute('aria-label'),/^Conversation focus:/);
});

test('generated teaching keeps one compact inspectable Sources disclosure without duplicating a lesson', () => {
  const h = harness(), url = 'https://www.medicare.gov/basics';
  const item = {reply:'Here is the relevant explanation.',facts:[],sources:[{url,label:'Medicare basics'},{url,label:'Duplicate reference'},{url:'javascript:alert(1)',label:'Unsafe'},{url:'http://example.com',label:'Insecure'}]};
  h.paint([item]);
  const answer = byClass(h.host,'chat-daylight')[0], sources = byClass(answer,'sources');
  assert.equal(byTag(answer,'p').length,1);
  assert.equal(byTag(answer,'h2').length,0);
  assert.equal(sources.length,1);
  assert.equal(byTag(sources[0],'summary')[0].textContent,'Sources');
  const links = byTag(sources[0],'a');
  assert.equal(links.length,1);
  assert.equal(links[0].href,url);
  assert.equal(links[0].textContent,'Medicare basics');
  assert.equal(links[0].rel,'noopener noreferrer');
  assert.equal(byClass(sources[0],'reveal-word').length,0);
  h.paint();
  assert.equal(byClass(h.host,'sources').length,1);
});

test('current-turn route teaching appears inline once while Sources remains a separate disclosure', () => {
  const h = harness();
  const visual=h.turnVisual({advisor:{teachingFactIds:['routesintro']}});
  const item={reply:'These are the two main coverage paths.',visual,
    sources:[{url:'https://www.medicare.gov/basics',label:'Medicare basics'}]};
  h.paint([item]);
  const answer=byClass(h.host,'chat-daylight')[0];
  const guides=byClass(answer,'inline-guide');
  assert.equal(guides.length,1);
  assert.ok(visualText(guides[0]).includes('Original Medicare'));
  assert.ok(visualText(guides[0]).includes('Medicare Advantage'));
  assert.equal(byTag(guides[0],'details').length,0);
  assert.equal(byTag(answer,'details').length,1,'Only Sources remains expandable.');
  assert.equal(byTag(answer,'summary')[0].textContent,'Sources');
  const firstGuide=guides[0];
  h.paint();
  assert.equal(byClass(h.host,'inline-guide')[0],firstGuide,'Repaint must not recreate or replay teaching.');
});

test('current visual intent selects the existing guide independently of citations', () => {
  const h=harness();
  for (const [intent,title,labels] of [
    ['routes','Two coverage paths',['Original Medicare','Medicare Advantage']],
    ['original','Original Medicare',['Original Medicare']],
    ['advantage','Medicare Advantage',['Medicare Advantage']],
    ['parts','Parts A and B',['Part A','Part B']],
    ['parta','Part A',['Part A']],
    ['partb','Part B',['Part B']],
  ]) {
    const visual=h.turnVisual({advisor:{visual:intent,teachingFactIds:[]},facts:[]});
    assert.equal(visual.title,title);
    const guide=h.guide(visual);
    assert.equal(guide.getAttribute('aria-label'),title);
    assert.deepEqual(byTag(guide,'button').map(accessibleText),labels);
    assert.equal(byTag(guide,'details').length,0);
  }
});

test('explicit none or invalid visual intent cannot fall back to a cited lesson or old timeline', () => {
  const h=harness();
  for (const visual of ['none',null,undefined,'unexpected','__proto__']) {
    assert.equal(h.turnVisual({advisor:{visual,teachingFactIds:['routesintro','parts','dates']},
      facts:[{id:'routesintro'}],assessment:{state:'external_validation_held',
        nextQuestion:null,narrative:{visual:{kind:'timeline',title:'Your timing',
          items:[['Birthday','November'],['Coverage','December']]}}}}),null);
  }
  assert.equal(h.turnVisual({advisor:{teachingFactIds:['routesintro']}}).title,'Two coverage paths',
    'Only older responses that lack the visual field retain the previous rendering contract.');
});

test('two successful turns retain the first guide without making a second guide from citations', () => {
  const h=harness(),url='https://www.medicare.gov/basics';
  const first={generated:{status:'complete'},reply:'These are the two main coverage paths.',facts:[],
    advisor:{visual:'routes',teachingFactIds:['routesintro'],sources:[{url,label:'Medicare basics'}]}};
  h.append('turn-one','What has you thinking about Medicare today?',
    'Turning 65 in November and looking to understand my Medicare options.',first);
  h.paint();
  const firstGuide=byClass(h.host,'inline-guide')[0];
  const second={generated:{status:'complete'},reply:'Your current insurance helps determine what comes next.',facts:[],
    advisor:{visual:'none',teachingFactIds:['routesintro'],sources:[{url,label:'Medicare basics'},{url,label:'Duplicate'}]}};
  h.append('turn-two','Is this for you, someone you help, or just general research?','Me',second);
  h.paint();
  assert.equal(byClass(h.host,'inline-guide').length,1);
  assert.equal(byClass(h.host,'inline-guide')[0],firstGuide,'A later citation cannot replace or replay the original guide.');
  const secondExchange=h.host.children[1],sources=byClass(secondExchange,'sources');
  assert.equal(sources.length,1,'The citation remains inspectable even without another guide.');
  assert.equal(byTag(sources[0],'summary')[0].textContent,'Sources');
  assert.equal(byTag(sources[0],'a').length,1);
  assert.equal(byTag(sources[0],'a')[0].href,url);
  const question={id:'T05',question:'What health insurance do you have now?',choices:[['none','No health insurance']],fields:[],multi:true};
  const current=h.question(question);
  assert.equal(byTag(current,'h1').length,1);
  assert.equal(accessibleText(byTag(current,'h1')[0]),question.question);
  assert.equal(accessibleText(secondExchange).includes(question.question),false,
    'The server-supplied follow-up stays in its existing dedicated question field.');
  h.append('turn-two','Is this for you, someone you help, or just general research?','Me',second);
  h.paint();
  assert.equal(h.host.children.length,2,'Request replay must not append a repeated exchange or graphic.');
});

test('a deliberate revisit may show the same guide again while failed generation never does', () => {
  const h=harness(),advisor={visual:'routes',teachingFactIds:['routesintro'],sources:[]};
  h.append('introduction','','My Medicare options',{generated:{status:'complete'},reply:'Here are the coverage paths.',advisor});
  h.paint();
  const original=byClass(h.host,'inline-guide')[0];
  h.append('requested-revisit','','Please explain the two paths again.',
    {generated:{status:'complete'},reply:'Let’s look at the two paths again.',advisor});
  h.paint();
  assert.equal(byClass(h.host,'inline-guide').length,2,'Frontend honors the validated revisit decision.');
  assert.equal(byClass(h.host,'inline-guide')[0],original);
  assert.equal(h.turnVisual({generated:{status:'unavailable'},advisor}),null);
});

test('fact and generated citations merge into one deduplicated Sources footer after the inline guide', () => {
  const h=harness(), first='https://www.medicare.gov/basics', second='https://www.medicare.gov/coverage', third='https://www.medicare.gov/plan-compare';
  const visual=h.turnVisual({advisor:{teachingFactIds:['routesintro']}});
  h.paint([{reply:'Here are the two coverage paths.',visual,
    facts:[{id:'routesintro',title:'Two coverage paths',text:'The paths arrange coverage differently.',source:first,
      sources:[{url:second,label:'Coverage details'},{url:first,label:'Repeated basics'}]}],
    sources:[{url:first,label:'Medicare basics'},{url:third,label:'Plan comparison'}]}]);
  const answer=byClass(h.host,'chat-daylight')[0], guide=byClass(answer,'inline-guide')[0];
  const sources=byClass(answer,'sources');
  assert.equal(sources.length,1);
  assert.equal(answer.children.at(-1),sources[0],'Sources follows both the explanation and graphic.');
  assert.ok(answer.children.indexOf(guide)<answer.children.indexOf(sources[0]));
  assert.equal(byClass(byClass(answer,'facts')[0],'sources').length,0);
  assert.equal(byTag(sources[0],'summary')[0].textContent,'Sources');
  assert.equal(byClass(sources[0],'reveal-word').length,0);
  assert.deepEqual(byTag(sources[0],'a').map(link=>link.href),[first,third,second]);
  assert.equal(byTag(sources[0],'a')[0].textContent,'Medicare basics');
});

test('failed or unrelated turns cannot select a route graphic from historical learning', () => {
  const h=harness();
  assert.equal(h.turnVisual({generated:{status:'unavailable'},advisor:{teachingFactIds:['routesintro']}}),null);
  assert.equal(h.turnVisual({advisor:{teachingFactIds:['enrollment_intro']},assessment:{
    nextQuestion:{id:'RC11'},narrative:{visual:{kind:'routes',title:'Two coverage paths'}},
    journey:{learningSeen:['routesintro']}}}),null);
  assert.equal(h.turnVisual({advisor:{teachingFactIds:[]},assessment:{narrative:{visual:{kind:'routes'}}}}),null);
});

test('typed text blocks finite answers, field choices and unknown without changing the draft', () => {
  const h=harness();
  const question={id:'RC23',question:'What fill details do you know?',choices:[['details','Add details']],
    fields:[{key:'daysSupply',type:'select',label:'Days supply',options:[['30','30 days']]}]};
  h.message('ASAP');
  const panel=h.question(question,[]);
  for (const label of ['Add details','30 days','I don’t know','Check later']) {
    byTag(panel,'button').find(button => accessibleText(button)===label).onclick();
  }
  assert.deepEqual(h.draft(question).choice,[]);
  assert.deepEqual(h.draft(question).fields,{});
  assert.equal(h.draft(question).resolution,undefined);
  assert.equal(h.renderCount,0);
  assert.equal(h.notices.length,4);
});

function pendingHarness() {
  const nodes=new Map(), history=[{reply:'Earlier conversation'}];
  const node=id => {if(!nodes.has(id)) nodes.set(id,new FakeNode('div'));return nodes.get(id);};
  node('status').className='chat-status';node('status').setAttribute('role','status');
  node('reading').scrollHeight=900;node('reading').scrollTop=100;
  const pendingSource=source.slice(source.indexOf('  function beginPending('),source.indexOf('  function rows('));
  const context=vm.createContext({document:{createElement:tag => new FakeNode(tag)},$:node,history});
  vm.runInContext(elementSource+'\n'+pendingSource,context);
  return {node,history,begin:(...args)=>context.beginPending(...args),end:()=>context.endPending()};
}

test('the real pending view shows the submitted message and three decorative dots without transcript writes', () => {
  const h=pendingHarness(), words='I have a question about my coverage.';
  h.begin(words,true);
  const pending=h.node('pending-turn');
  assert.equal(pending.hidden,false);
  const user=byClass(pending,'chat-user')[0], typing=byClass(pending,'typing-indicator')[0];
  assert.equal(user.textContent,words);
  assert.equal(user.getAttribute('aria-label'),'You');
  assert.equal(byClass(user,'reveal-word').length,0);
  assert.equal(byClass(typing,'typing-dot').length,3);
  assert.equal(typing.getAttribute('aria-hidden'),'true');
  assert.equal(byClass(pending,'sources').length,0);
  assert.equal(h.node('status').getAttribute('role'),'status');
  assert.equal(h.node('status').className,'chat-status sr-only');
  assert.deepEqual(h.history,[{reply:'Earlier conversation'}]);
  h.end();
  assert.equal(pending.hidden,true);
  assert.equal(pending.children.length,0);
  assert.equal(h.node('status').className,'chat-status');
  assert.equal(h.history.length,1);
});

test('manual navigation has no AI typing indicator and reduced motion disables its animation', () => {
  const h=pendingHarness();h.begin('',false);
  assert.equal(h.node('pending-turn').hidden,true);
  assert.equal(h.node('pending-turn').children.length,0);
  assert.equal(h.node('status').className,'chat-status');
  const css=fs.readFileSync(path.join(web,'advisor.css'),'utf8');
  assert.match(css,/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{\s*body\.chat-mode\s+\.typing-dot\s*\{[^}]*animation:\s*none\s*!important/);
});

test('the typing wave overrides the loaded universal animation reset, while reduced motion still wins', () => {
  const html=fs.readFileSync(path.join(web,'index.html'),'utf8');
  const sheets=[...html.matchAll(/<link\b[^>]*rel="stylesheet"[^>]*href="([^"]+)"[^>]*>/g)].map(match=>match[1]);
  assert.ok(sheets.indexOf('/styles.css')>=0);
  assert.ok(sheets.indexOf('/advisor.css')>sheets.indexOf('/styles.css'),'The scoped adapter must follow the retained shell styles.');
  const incumbent=sheets.slice(0,sheets.indexOf('/advisor.css')).map(file=>fs.readFileSync(path.join(web,file.replace(/^\//,'')),'utf8')).join('\n');
  assert.match(incumbent,/\*,\*::before,\*::after\s*\{[^}]*animation:\s*none\s*!important/,'The combined incumbent sheets contain an important reset that suppressed the old dots.');
  const css=fs.readFileSync(path.join(web,'advisor.css'),'utf8');
  assert.match(css,/body\.chat-mode\s+\.typing-dot\s*\{[^}]*animation:\s*daylight-typing\s+1\.1s\s+ease-in-out\s+infinite\s*!important/,'A normal declaration cannot override the important shell reset.');
  assert.match(css,/body\.chat-mode\s+\.typing-dot:nth-child\(2\)\s*\{[^}]*animation-delay:\s*\.14s\s*!important/);
  assert.match(css,/body\.chat-mode\s+\.typing-dot:nth-child\(3\)\s*\{[^}]*animation-delay:\s*\.28s\s*!important/);
  assert.match(css,/@keyframes\s+daylight-typing\s*\{[^}]*transform:\s*translateY\(0\)[^}]*\}[^}]*transform:\s*translateY\(-5px\)/,'Opacity alone is not the requested moving wave.');
  assert.match(css,/body\.chat-mode\s+\.typing-paused\s+\.typing-dot\s*\{[^}]*animation-play-state:\s*paused\s*!important/);
  const reducedRule=/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{\s*body\.chat-mode\s+\.typing-dot\s*\{[^}]*animation:\s*none\s*!important/;
  assert.match(css,reducedRule,'The reduced-motion rule must match the scoped important wave declaration.');
  assert.ok(css.search(reducedRule)>css.indexOf('animation:daylight-typing'),'Equal-specificity reduced motion wins by following the wave rule.');
});

function scrollCueHarness() {
  const nodes=new Map(),moves=[];
  const node=id => {if(!nodes.has(id)) nodes.set(id,new FakeNode('div'));return nodes.get(id);};
  const reading=node('reading'), pending=node('pending-turn'), current=node('current');
  const readingBounds={top:100,bottom:500}, pendingBounds={top:400,bottom:444}, currentBounds={top:700,bottom:850};
  reading.getBoundingClientRect=()=>readingBounds;
  pending.getBoundingClientRect=()=>pendingBounds;
  current.getBoundingClientRect=()=>currentBounds;
  reading.parentElement={getBoundingClientRect:()=>({top:50,bottom:700})};
  reading.scrollHeight=1400;reading.clientHeight=400;reading.scrollTop=100;
  reading.scrollTo=options=>{moves.push(options);reading.scrollTop=options.top;};
  const context=vm.createContext({$:node,document:{hidden:false},active:true,busy:false,question:{id:'T05'},q:()=>context.question,
    reduced:false,matchMedia:()=>({matches:context.reduced})});
  const functions=source.slice(source.indexOf('  function updateScrollCue('),source.indexOf('  function rows('));
  assert.ok(functions.startsWith('  function updateScrollCue('),'Exercise the production cue and jump helpers.');
  vm.runInContext(functions,context);
  return {context,node,moves,readingBounds,pendingBounds,currentBounds,update:()=>context.updateScrollCue(),jump:()=>context.jumpDown()};
}

test('a down arrow appears only when more conversation is below and labels the current question when it is offscreen', () => {
  const h=scrollCueHarness(),cue=h.node('chat-down');h.update();
  assert.equal(cue.hidden,false);
  assert.equal(cue.getAttribute('aria-label'),'Go to next question');
  assert.equal(cue.title,'Go to next question');
  assert.equal(cue.style.getPropertyValue('--chat-down-bottom'),'210px','The cue follows the space above the growing composer.');
  h.currentBounds.top=400;h.update();
  assert.equal(cue.getAttribute('aria-label'),'Go to latest message');
  h.node('reading').scrollTop=965;h.update();
  assert.equal(cue.hidden,true,'At the bottom, there should be no redundant arrow.');
  h.node('reading').scrollTop=100;h.context.busy=true;h.update();
  assert.equal(cue.hidden,true,'The pending typing view owns attention while Send is unresolved.');
  h.context.busy=false;h.context.active=false;h.update();assert.equal(cue.hidden,true);
});

test('the down arrow reaches and focuses the offscreen question, with an instant reduced-motion path to the latest message', () => {
  const h=scrollCueHarness();h.jump();
  assert.equal(h.moves.length,1);
  assert.equal(h.moves[0].top,682);
  assert.equal(h.moves[0].behavior,'smooth');
  assert.equal(h.node('current').getAttribute('tabindex'),'-1');
  assert.equal(h.node('current').focused,true);
  assert.equal(h.node('current').focusOptions.preventScroll,true);
  h.context.question=null;h.context.reduced=true;h.jump();
  assert.equal(h.moves[1].top,h.node('reading').scrollHeight);
  assert.equal(h.moves[1].behavior,'instant');
});

test('typing motion pauses in a hidden document or outside the visible reading pane', () => {
  const h=scrollCueHarness(),pending=h.node('pending-turn');h.update();
  assert.equal(pending.classList.contains('typing-paused'),false);
  h.context.document.hidden=true;h.update();assert.equal(pending.classList.contains('typing-paused'),true);
  h.context.document.hidden=false;h.pendingBounds.top=500;h.pendingBounds.bottom=544;
  h.update();assert.equal(pending.classList.contains('typing-paused'),true);
  h.pendingBounds.top=400;h.pendingBounds.bottom=444;
  h.update();assert.equal(pending.classList.contains('typing-paused'),false);
});

test('educational follow-ups form one optional collapsed disclosure with at most two unique safe text suggestions', () => {
  const h=harness();
  for (const value of [null,undefined,{},[],['',null,' '.repeat(2),'x'.repeat(121)]]) assert.equal(h.followups(value),null);
  const first='How do the two paths differ?';
  const second='What does <img src=x onerror=alert(1)> mean?';
  const menu=h.followups([first,`  ${first}  `,second,'A third suggested question?']);
  assert.equal(menu.tagName,'DETAILS');
  assert.notEqual(menu.open,true,'Suggestions must not compete with the next question by opening automatically.');
  assert.equal(byTag(menu,'summary')[0].textContent,'More about this');
  assert.deepEqual(byTag(menu,'button').map(accessibleText),[first,second]);
  assert.equal(byTag(menu,'img').length,0,'Model-suggested text never becomes HTML.');
  assert.equal(h.messageValue,'');assert.equal(h.inputCount,0);
});

test('selecting an educational follow-up fills an editable draft without sending or overwriting another draft', () => {
  const h=harness(),question='How do these paths differ on doctor choice?';
  const control=byTag(h.followups([question]),'button')[0];
  control.onclick();
  assert.equal(h.messageValue,question);assert.equal(h.messageFocused,true);assert.equal(h.inputCount,1);
  const raw='I was still writing this other question.';h.message(raw);control.onclick();
  assert.equal(h.messageValue,raw);assert.equal(h.inputCount,1);
  assert.match(h.notices.at(-1),/Your draft is still here/);
  h.message('');h.setBusy(true);control.onclick();
  assert.equal(h.messageValue,'');assert.equal(h.inputCount,1,'An unresolved Send cannot stage another suggestion.');
});

test('optional educational questions remain with their explanation before the unchanged Sources footer', () => {
  const h=harness(),question='How does doctor choice differ?';
  h.paint([{reply:'Here are the two main paths.',educationFollowups:[question],sources:[{url:'https://www.medicare.gov/basics',label:'Medicare basics'}]}]);
  const answer=byClass(h.host,'chat-daylight')[0],menu=byClass(answer,'education-followups')[0],sources=byClass(answer,'sources')[0];
  assert.ok(menu);assert.ok(sources);
  assert.equal(answer.children.at(-1),sources);
  assert.ok(answer.children.indexOf(menu)<answer.children.indexOf(sources));
  assert.equal(byTag(sources,'summary')[0].textContent,'Sources');
  const original=menu;h.paint();assert.equal(byClass(h.host,'education-followups')[0],original);
});

function composerHarness({minimum=80,viewport=800}={}) {
  const nodes=new Map(), calls=[], draft={choice:['already'],resolution:'unknown',fields:{month:'2027-01'},coverageGroup:'medicare'};
  const node=id => {if(!nodes.has(id)) nodes.set(id,new FakeNode(id==='message'?'textarea':'div'));return nodes.get(id);};
  const input=node('message'), reading=node('reading');
  input.scrollHeight=80;reading.scrollHeight=1000;reading.clientHeight=500;reading.scrollTop=100;
  const context=vm.createContext({$:node,window:{innerHeight:900,visualViewport:{height:viewport}},
    getComputedStyle:()=>({minHeight:String(minimum)}),q:()=>({id:'T04',signature:'T04.profile.choice'}),updateScrollCue(){},
    draftFor:()=>draft,selectedGoal:'compare',renderCount:0,sendSyncs:0,
    renderCurrent(){context.renderCount++;},syncSend(){context.sendSyncs++;},
    composing:false,busy:false,review:null,turn:async(...args)=>{calls.push(args);return true;}});
  const resizeSource=source.slice(source.indexOf('  function resizeComposer('),source.indexOf('  function syncSend('));
  const submitSource=source.slice(source.indexOf('  async function submitCurrent('),source.indexOf('  function renderForm('));
  vm.runInContext(resizeSource+'\n'+submitSource,context);
  return {node,draft,calls,context,resize:()=>context.resizeComposer(),input:()=>context.messageInput(),submit:()=>context.submitCurrent()};
}

test('typing ASAP clears only unsent answer selections and typed submission wins', async () => {
  const h=composerHarness();
  h.node('message').value='ASAP';h.input();
  assert.deepEqual(Array.from(h.draft.choice),[]);
  assert.equal(h.draft.resolution,'');
  assert.deepEqual(JSON.parse(JSON.stringify(h.draft.fields)),{});
  assert.equal(h.draft.coverageGroup,'');
  assert.equal(h.context.selectedGoal,'');
  assert.equal(h.context.renderCount,1);
  assert.equal(h.calls.length,0,'Typing does not transfer anything to AI.');
  await h.submit();
  assert.equal(h.calls.length,1);
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls[0][0])),{type:'message',message:'ASAP'});
  assert.equal(h.calls[0][1],'ASAP');
});

test('an empty draft preserves an intentional selection and typed submission still wins without an input event', async () => {
  const h=composerHarness();
  h.node('message').value='   ';h.input();
  assert.deepEqual(h.draft.choice,['already']);
  assert.equal(h.context.renderCount,0);
  h.node('message').value='I want help choosing the start date.';
  await h.submit();
  assert.equal(h.calls[0][0].type,'message');
  assert.equal(h.calls[0][0].message,'I want help choosing the start date.');
});

test('the composer grows, caps and shrinks while preserving a reader’s scroll position', () => {
  const h=composerHarness();
  h.node('message').scrollHeight=150;h.resize();
  assert.equal(h.node('message').style.height,'150px');
  assert.equal(h.node('message').style.overflowY,'hidden');
  h.node('message').scrollHeight=500;h.resize();
  assert.equal(h.node('message').style.height,'240px');
  assert.equal(h.node('message').style.overflowY,'auto');
  assert.equal(h.node('reading').scrollTop,100,'Writing must not drag someone away from earlier chat.');
  h.node('message').scrollHeight=55;h.resize();
  assert.equal(h.node('message').style.height,'80px');
  assert.equal(h.node('message').style.overflowY,'hidden');
});

test('the composer respects the mobile visual viewport, its minimum and the viewport fallback', () => {
  const h=composerHarness({minimum:76,viewport:400});h.node('message').scrollHeight=500;h.resize();
  assert.equal(h.node('message').style.height,'120px');
  h.context.window.visualViewport.height=200;h.resize();
  assert.equal(h.node('message').style.height,'76px');
  h.context.window.visualViewport=null;h.context.window.innerHeight=600;h.resize();
  assert.equal(h.node('message').style.height,'180px');
});
