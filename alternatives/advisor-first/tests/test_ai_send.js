/* Exercise the production request builder and turn with a fake transport.
 * No HTTP server, model call, or AI credits are used.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', process.env.DAYLIGHT_TEST_WEB || 'web', 'advisor.js'), 'utf8');
const start = source.indexOf('  function turnCandidate(');
const end = source.indexOf('  function concept(', start);
assert.ok(start > 0 && end > start, 'Load the actual production request builder and turn.');
const noticeHelpers = ['PAUSED', 'plain'].map(name => source.match(new RegExp('^  const '+name+' = .*$', 'm'))?.[0] || '').join('\n');
const openingSource = source.match(/^  const OPENING_CHOICES = Object\.freeze\(\{[\s\S]*?^  \}\);\n  const OPENING_REPLY_DELAY = .*$/m)?.[0] || '';
const production = source.match(/^  const OPENING_QUESTION = .*$/m)?.[0]+'\n'+openingSource+'\n'+noticeHelpers+'\n'+source.slice(start, end);
const visualSource = source.slice(source.indexOf('  function turnVisual('),source.indexOf('  function inlineGuide('));
const plain = value => JSON.parse(JSON.stringify(value));

function harness(failure) {
  const calls = [], notices = [], pending = [], recoveryCalls = [];
  let recoveryResult = null;
  let transportFailure = failure, renderFailure = null, nextRequest = 0;
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {
      value: id === 'message' ? 'I turn 65 in November.' : '', scrollTop: 0,
      lastElementChild: null, getBoundingClientRect: () => ({top: 0}),
      setAttribute() {}, focus() {},
    });
    return elements.get(id);
  };
  const initial = {guide: {preferences: {saveGuide: false}, answer: 'kept'},
    record: {report: 'kept'}, assessment: {nextQuestion: null}, continuation: 'signed-visit'};
  const response = structuredClone(initial);
  response.reply = 'We can work through the next steps together.';
  const context = vm.createContext({
    state: initial, config: {mockAI: false}, busy: false, review: null, prepared: null, visitResume: undefined,
    clone: structuredClone, crypto: {randomUUID: () => `unique-request-${++nextRequest}`},
    q: () => context.state.assessment.nextQuestion,
    $: element, failedRequest: null, lastRequest: null, frames: [], history: [],
    reviewMessage: '', preparedVersions: [], selectedGoal: '', parkedMessages: [],
    drafts:new Map(),selected:[],currentSignature:'',setTimeout:resolve=>resolve(),performance,
    closeDoctorCheck() {}, doctorComposer:null, service:{}, window:{DaylightConversationChecks:{clear() {}}},
    metrics: {turns: 0, llmCalls: 0},
    setBusy(value) { context.busy = value; }, note(value) { notices.push(value); },
    beginPending(words, usingAI) { pending.push({kind:'begin',words,usingAI}); },
    endPending() { pending.push({kind:'end'}); },
    resizeComposer() {}, updateScrollCue() {},
    render() {if (renderFailure) {const error = renderFailure;renderFailure = null;throw error;}}, renderCurrent() {},
    consent() { assert.fail('A deliberate Send must not open a second consent prompt.'); },
    dialog() { assert.fail('Sending a message must not create a dialog.'); },
    api: async (url, payload) => {
      if (url === '/api/conversation/recover') {
        recoveryCalls.push(structuredClone(payload));
        if (!recoveryResult) throw Error('Recovery connection unavailable.');
        return typeof recoveryResult === 'function' ? recoveryResult() : structuredClone(recoveryResult);
      }
      calls.push({url, payload: structuredClone(payload)});
      if (transportFailure) throw transportFailure;
      return structuredClone(response);
    },
  });
  vm.runInContext(visualSource+'\n'+production, context, {filename: 'advisor.js:production-send'});
  return {context, calls, notices, pending, element, initial,response,recoveryCalls,
    recoverWith(result) {recoveryResult=result;},
    failTransport(error) {transportFailure = error;},
    failRenderOnce(error) {renderFailure = error;},
    candidate: (action,deliberate) => context.turnCandidate(action,deliberate),
    turn: (action,words,deliberate,options) => context.turn(action,words,deliberate,options)};
}

test('plan-review actions preserve an unsent draft and do not authorize AI',async()=>{
  for (const type of ['review_plans','confirm_plan_review','get_plan_handoff']) {
    const h=harness();
    assert.equal(await h.turn({type,token:'review-token'}),false);
    assert.equal(h.calls.length,0);
    assert.equal(h.element('message').value,'I turn 65 in November.');
    h.element('message').value='';
    assert.equal(h.candidate({type,token:'review-token'}).aiConsent,false);
  }
});

test('only explicit confirmation opens the plans destination with its receipt',async()=>{
  const h=harness(),received=[];h.element('message').value='';
  h.response.plansHandoff={token:'reviewed-receipt',reportedInfoReviewed:true};
  h.context.DaylightPlansHandoff={open:async value=>{received.push(plain(value));return true;}};
  assert.equal(await h.turn({type:'confirm_plan_review',token:'review-token'},'See plans'),true);
  assert.deepEqual(received,[h.response.plansHandoff]);
  assert.equal(h.calls.length,1);
  assert.equal(h.calls[0].payload.aiConsent,false);
  assert.equal(await h.turn({type:'refresh'}),true);
  assert.equal(received.length,1,'Utility refresh cannot navigate into plans.');
});

test('a failed plans destination keeps the accepted state and lets the user retry',async()=>{
  const h=harness();h.element('message').value='';
  h.response.plansHandoff={token:'reviewed-receipt',reportedInfoReviewed:true};
  h.context.DaylightPlansHandoff={open:async()=>{throw Error('Fixture unavailable');}};
  assert.equal(await h.turn({type:'confirm_plan_review',token:'review-token'},'See plans'),true);
  assert.equal(h.context.state.plansHandoff.token,'reviewed-receipt');
  assert.match(h.notices.at(-1),/reviewed information is kept/);
});

test('a lost completed reply is recovered automatically without another model request',async()=>{
  const h=harness(Error('Connection lost'));
  h.recoverWith({status:'completed',response:h.response});
  const words=h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.calls.length,1);assert.equal(h.recoveryCalls.length,1);
  assert.deepEqual(h.recoveryCalls[0],h.calls[0].payload);
  assert.equal(h.context.history.length,1);assert.equal(h.element('message').value,'');
});

for (const status of ['reset','resumed']) test(`${status} session installs current state and preserves the unsent draft`,async()=>{
  const error=Object.assign(Error('Your conversation changed. Keep this message and resume the latest state.'),{code:409,recovery:'conversation_state'});
  const h=harness(error),words=h.element('message').value;
  h.context.history=[{reply:'Earlier conversation'}];h.context.review={token:'old-action'};
  const recovered=structuredClone(h.response);recovered.continuation='current-binding';
  h.recoverWith({status,response:recovered});
  assert.equal(await h.turn({type:'message',message:words},words),false);
  assert.equal(h.context.state.continuation,'current-binding');
  assert.equal(h.element('message').value,words);
  assert.equal(h.context.review,null);assert.equal(h.context.failedRequest,null);
  if (openingSource) assert.equal(h.context.history[0].reply,'Earlier conversation');
  assert.equal(h.calls.length,1,'Recovery never resubmits against a changed question.');
  assert.doesNotMatch(h.notices.at(-1),/Your conversation changed|resume the latest state/);
  assert.equal(h.context.busy,false);
  h.failTransport(null);h.response.continuation='after-reconnected-send';
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.calls[1].payload.continuation,'current-binding');
  assert.notEqual(h.calls[1].payload.requestId,h.calls[0].payload.requestId);
});

test('reconnection leaves a newer draft intact and parks the original',async()=>{
  const h=harness(Object.assign(Error('stale'),{code:409,recovery:'conversation_state'}));
  const words=h.element('message').value;
  h.recoverWith(()=>{h.element('message').value='A newer draft';return {status:'reset',response:h.response};});
  assert.equal(await h.turn({type:'message',message:words},words),false);
  assert.equal(h.element('message').value,'A newer draft');
  assert.deepEqual(plain(h.context.parkedMessages),[words]);
});

test('bounded working checks keep the original request key for the next Send',async()=>{
  const h=harness(Object.assign(Error('still working'),{code:409,recovery:'conversation_busy'}));
  h.recoverWith({status:'working'});
  const words=h.element('message').value,action={type:'message',message:words};
  assert.equal(await h.turn(action,words),false);
  assert.equal(h.recoveryCalls.length,20);assert.equal(h.calls.length,1);
  assert.equal(h.context.failedRequest.requestId,h.calls[0].payload.requestId);
  assert.match(h.notices.at(-1),/still working/);
  h.failTransport(null);
  assert.equal(await h.turn(action,words),true);
  assert.equal(h.calls[1].payload.requestId,h.calls[0].payload.requestId);
});

test('a still-processing request is automatically picked up when its receipt arrives',async()=>{
  const h=harness(Error('Connection lost'));let reads=0;
  h.recoverWith(()=>++reads < 4 ? {status:'working'} : {status:'completed',response:h.response});
  const words=h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.recoveryCalls.length,4);assert.equal(h.calls.length,1);
  assert.equal(h.context.history.length,1);assert.equal(h.context.busy,false);
});

test('non-session conflicts cannot invoke session recovery',async()=>{
  const h=harness(Object.assign(Error('A named action is no longer valid.'),{code:409}));
  const words=h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),false);
  assert.equal(h.recoveryCalls.length,0);assert.equal(h.calls.length,1);
});

test('expired guest authority reconnects freely with saving paused and draft retained',async()=>{
  const h=harness(Object.assign(Error('Guest expired'),{code:401}));
  let reconnects=0;
  h.context.refreshVisitAuthority=async()=>{reconnects++;const state=structuredClone(h.response);state.continuation='new-owner';state.guide.preferences={saveGuide:false,saveSensitive:false};h.context.state=state;};
  const words=h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),false);
  assert.equal(reconnects,1);assert.equal(h.context.state.continuation,'new-owner');
  assert.equal(h.context.state.guide.preferences.saveGuide,false);
  assert.equal(h.element('message').value,words);
  assert.match(h.notices.at(-1),/Saving is paused/);assert.equal(h.calls.length,1);
});

test('a recovered unavailable generation never becomes an assistant history message',async()=>{
  const h=harness(Object.assign(Error('stale'),{code:409,recovery:'conversation_state'}));
  h.response.generated={status:'unavailable'};h.response.reply='A generation failure notice.';
  h.recoverWith({status:'resumed',response:h.response});
  const words=h.element('message').value;
  await h.turn({type:'message',message:words},words);
  assert.equal(h.context.history.length,0);assert.equal(h.element('message').value,words);
});

test('Send carries current AI permission, relevant-context policy and the same visit state', () => {
  const h = harness();
  const payload = h.candidate({type: 'message', text: 'I turn 65 in November.'});
  assert.equal(payload.aiConsent, true);
  assert.equal(payload.contextPolicy, 'natural-context-v3');
  assert.equal(payload.continuation, 'signed-visit');
  assert.deepEqual(plain(payload.guide), plain(h.initial.guide));
  assert.deepEqual(plain(payload.record), plain(h.initial.record));
  payload.guide.answer = 'changed';
  assert.equal(h.initial.guide.answer, 'kept', 'Request snapshots must not mutate the current profile.');
  assert.equal(h.calls.length, 0, 'Building a payload must not contact AI.');
});

test('non-message navigation does not acquire expanded AI permission', () => {
  const h = harness();
  for (const type of ['start', 'resume', 'choice', 'edit', 'read_concept', 'review_preparation']) {
    const payload = h.candidate({type});
    assert.equal(payload.aiConsent, false, `${type} is not a deliberate message Send`);
    assert.equal(payload.contextPolicy, null);
  }
  assert.equal(h.calls.length, 0);
});

test('one deliberate Send makes one request and clears only its submitted draft', async () => {
  const h = harness();
  const words = h.element('message').value;
  assert.equal(await h.turn({type: 'message', text: words}, words), true);
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].url, '/api/conversation/turn');
  assert.equal(h.calls[0].payload.aiConsent, true);
  assert.equal(h.calls[0].payload.contextPolicy, 'natural-context-v3');
  assert.equal(h.element('message').value, '');
  assert.equal(h.context.busy, false);
});

test('an unexpected 428 preserves the draft without a modal or an automatic retry', async () => {
  const error = Object.assign(Error('AI permission could not be accepted.'), {code: 428});
  const h = harness(error);
  const words = h.element('message').value;
  assert.equal(await h.turn({type: 'message', text: words}, words), false);
  assert.equal(h.calls.length, 1);
  assert.equal(h.element('message').value, words);
  assert.equal(h.context.state, h.initial);
  assert.equal(h.context.busy, false);
  assert.match(h.notices.at(-1), /Your input is preserved/);
});

test('a successful answer retains the exact question before its user answer and leaves the next question current', async () => {
  const h = harness();
  const asked = 'How much have you learned about Medicare so far?';
  h.initial.assessment.nextQuestion = {id:'T02',signature:'T02.profile.choice',question:asked};
  h.response.assessment.nextQuestion = {id:'T04',signature:'T04.profile.month',question:'When would you like coverage to start?'};
  const words = 'I’ve done a little research.';
  h.element('message').value = words;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.context.history.length,1);
  assert.equal(h.context.history[0].askedQuestion,asked);
  assert.equal(h.context.history[0].user,words);
  assert.equal(h.context.history[0].reply,h.response.reply);
  assert.equal(h.context.history[0].requestId,h.calls[0].payload.requestId);
  assert.equal(h.context.state.assessment.nextQuestion.question,h.response.assessment.nextQuestion.question);
  h.context.render();h.context.renderCurrent();
  assert.equal(h.context.history.length,1,'An ordinary repaint cannot archive the current question.');
});

test('the opening invitation is preserved from the same copy used on screen, after the greeting', async () => {
  const h = harness();
  const greeting = {reply:'Hi, I’m Daylight.'};h.context.history.push(greeting);
  h.initial.assessment.narrative = {opener:true};
  h.response.assessment.narrative = {opener:false};
  h.response.assessment.nextQuestion = {id:'T02',question:'How familiar are you with Medicare?'};
  const words = h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.context.history.length,2);
  assert.equal(h.context.history[0],greeting);
  assert.equal(h.context.history[1].askedQuestion,vm.runInContext('OPENING_QUESTION',h.context));
});

test('a lost response keeps the unanswered question current, and exact replay archives it only once', async () => {
  const h = harness(Error('The connection was lost.'));
  const asked = 'When would you like Medicare coverage to start?';
  h.initial.assessment.nextQuestion = {id:'T04',signature:'T04.profile.month',question:asked};
  h.response.assessment.nextQuestion = {id:'T05',signature:'T05.profile.choice',question:'What health insurance do you have now?'};
  const words = 'ASAP';h.element('message').value = words;
  const action = {type:'message',message:words};
  assert.equal(await h.turn(action,words),false);
  assert.equal(h.calls.length,1,'A failed request does not automatically retry.');
  assert.equal(h.context.history.length,0);
  assert.equal(h.context.state.assessment.nextQuestion.question,asked);
  assert.equal(h.element('message').value,words);
  h.failTransport(null);
  assert.equal(await h.turn(action,words),true);
  assert.equal(h.calls.length,2);
  assert.equal(h.calls[0].payload.requestId,h.calls[1].payload.requestId);
  assert.equal(h.context.history.length,1);
  assert.equal(h.context.history[0].askedQuestion,asked);
  assert.equal(h.context.history[0].user,words);
});

test('an accepted turn with an unavailable provider response still preserves the question exactly once', async () => {
  const h = harness();
  const asked = 'When would you like Medicare coverage to start?';
  h.initial.assessment.nextQuestion = {id:'T04',signature:'T04.profile.month',question:asked};
  h.response.generated = {status:'unavailable',retryable:false};
  h.response.reply = 'Your details are here. I couldn’t finish the response just now, but we can continue.';
  h.response.assessment.nextQuestion = {id:'T05',signature:'T05.profile.choice',question:'What health insurance do you have now?'};
  const words = 'As soon as possible.';h.element('message').value = words;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.calls.length,1);
  assert.equal(h.context.history.length,1);
  assert.equal(h.context.history[0].askedQuestion,asked);
  assert.equal(h.context.history[0].reply,'','A generation failure is a replaceable status notice, not conversational prose.');
  assert.equal(h.notices.at(-1),h.response.reply);
  h.context.render();h.context.renderCurrent();
  assert.equal(h.context.history.length,1);
});

test('an exact replay after a local presentation error cannot duplicate question, answer or reply', async () => {
  const h = harness();
  const asked = 'How familiar are you with Medicare?';
  h.initial.assessment.nextQuestion = {id:'T02',signature:'T02.profile.choice',question:asked};
  h.response.assessment.nextQuestion = {id:'T04',signature:'T04.profile.month',question:'When would you like coverage to start?'};
  const words = h.element('message').value,action = {type:'message',message:words};
  h.failRenderOnce(Error('The local view could not finish.'));
  assert.equal(await h.turn(action,words),false);
  assert.equal(h.context.history.length,1);
  const accepted = h.context.history[0];
  assert.equal(await h.turn(action,words),true);
  assert.equal(h.calls[0].payload.requestId,h.calls[1].payload.requestId);
  assert.equal(h.context.history.length,1);
  assert.equal(h.context.history[0],accepted);
  assert.equal(accepted.askedQuestion,asked);
  assert.equal(accepted.user,words);
});

test('an explanation that keeps the same unanswered question current does not add a historical duplicate', async () => {
  const h = harness();
  const question = {id:'T04',signature:'T04.profile.month',question:'When would you like coverage to start?'};
  h.initial.assessment.nextQuestion = question;h.response.assessment.nextQuestion = structuredClone(question);
  assert.equal(await h.turn({type:'read_concept',id:'dates'}),true);
  assert.equal(h.context.history.length,1);
  assert.equal(h.context.history[0].askedQuestion,'');
  assert.equal(h.context.state.assessment.nextQuestion.question,question.question);
});

test('repeated unavailable generations replace one notice without repeating it as conversational replies', async () => {
  const h = harness();
  const notice = 'Your details are here. I couldn’t finish the response just now, but we can continue.';
  h.initial.assessment.narrative = {opener:true};
  h.response.generated = {status:'unavailable',retryable:false};h.response.notice = notice;h.response.reply = '';
  h.response.assessment.nextQuestion = {id:'T04',signature:'T04.profile.month',question:'When would you like Medicare coverage to start?'};
  const story = 'I turn 65 in November and want to enroll in medicare -- dont know too much and want to explore my options';
  h.element('message').value = story;
  assert.equal(await h.turn({type:'message',message:story},story),true);
  assert.equal(h.notices.at(-1),notice);
  h.element('message').value = 'As soon as possible.';
  h.response.assessment.nextQuestion = {id:'T05',signature:'T05.profile.choice',question:'What health insurance do you have now?'};
  assert.equal(await h.turn({type:'message',message:'As soon as possible.'},'As soon as possible.'),true);
  assert.equal(h.context.history.length,2);
  assert.ok(h.context.history.every(item => item.reply === ''));
  assert.ok(h.context.history.every(item => !item.askedQuestion.includes(notice)));
  assert.equal(h.notices.at(-1),notice,'The existing status receives the notice once per failed generation.');
  assert.equal(h.context.visibleQuestion(),h.response.assessment.nextQuestion.question);
});

test('a missing server question never resurrects the already answered previous question after a generation failure', async () => {
  const h = harness();
  h.initial.assessment.nextQuestion = {id:'T04',signature:'T04.profile.month',question:'When would you like Medicare coverage to start?'};
  h.response.assessment.nextQuestion = null;h.response.assessment.intakePaused = true;
  h.response.generated = {status:'unavailable',retryable:false};h.response.notice = 'The response could not finish.';h.response.reply = '';
  const words = 'As soon as possible.';h.element('message').value = words;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.context.state.assessment.nextQuestion,null);
  assert.equal(h.context.visibleQuestion(),'');
  assert.equal(h.notices.at(-1),h.response.notice);
  assert.equal(h.context.history[0].askedQuestion,h.initial.assessment.nextQuestion.question);
  assert.equal(h.context.history[0].reply,'');
});

test('an unavailable-generation notice cannot be preserved as though it were an actual question', async () => {
  const h = harness();
  const notice = 'The response could not finish.';
  h.initial.generated = {status:'unavailable'};h.initial.notice = notice;
  h.initial.assessment.nextQuestion = {id:'T04',signature:'T04.profile.month',question:notice};
  h.response.generated = {status:'complete',move:'T05'};
  h.response.assessment.nextQuestion = {id:'T05',signature:'T05.profile.choice',question:'What health insurance do you have now?'};
  assert.equal(h.context.visibleQuestion(),'');
  const words = h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.context.history[0].askedQuestion,'');
  assert.equal(h.context.history[0].reply,h.response.reply);
});

test('only a deliberate answer Send grants the same scoped permission for contextual composition', async () => {
  const h = harness();
  for (const type of ['choice','stage','unknown','defer']) {
    const action = {type,id:'T05',fields:{choice:'employer'}};
    assert.equal(h.candidate(action).aiConsent,false,'Selecting or programmatically changing an answer grants no new permission.');
    const payload = h.candidate(action,true);
    assert.equal(payload.aiConsent,true);
    assert.equal(payload.contextPolicy,'natural-context-v3');
    assert.deepEqual(plain(payload.action),action,'No grouping shortcut or new report schema reaches the server.');
  }
  for (const type of ['start','resume','edit','read_concept','review_preparation','run_preparation']) assert.equal(h.candidate({type},true).aiConsent,false);
  assert.equal(h.calls.length,0,'Permission construction does not call the model.');
  h.element('message').value = '';
  assert.equal(await h.turn({type:'choice',id:'T05',fields:{choice:'employer'}},'Through a current job',true),true);
  assert.equal(h.calls.length,1);
  assert.equal(h.calls[0].payload.aiConsent,true);
  assert.equal(h.calls[0].payload.contextPolicy,'natural-context-v3');
});

test('the actual answer submitter sends precise coverage only after refinement and deliberate Send', async () => {
  const submitSource = source.slice(source.indexOf('  async function submitForm('),source.indexOf('  function renderReview('));
  const labelSource = source.slice(source.indexOf('  function insuranceChoiceLabel('),source.indexOf('  function insuranceChoiceView('));
  const calls = [], notices = [], draft = {choice:[],fields:{},coverageGroup:'medicare'};
  const context = vm.createContext({$:() => ({value:''}),draftFor:() => draft,note:text => notices.push(text),readable:String,turn:async (...args) => {calls.push(args);return true;}});
  vm.runInContext(labelSource+'\n'+submitSource,context);
  const question = {id:'T05',entity:'profile',fields:[],choices:[['retiree','Retiree coverage'],['cobra','COBRA'],['advantage','Medicare Advantage (Part C)']]};
  await context.submitForm(question);
  assert.equal(calls.length,0,'A Medicare family disclosure is not a Medicare Advantage or Original Medicare report.');
  draft.choice = ['retiree','advantage'];
  await context.submitForm(question);
  assert.equal(calls.length,1);
  assert.deepEqual(plain(calls[0][0]),{type:'choice',id:'T05',entity:'profile',fields:{choice:'retiree,advantage'}});
  assert.equal(calls[0][1],'Retiree health plan · Medicare Advantage (Part C)');
  assert.equal(calls[0][2],true);
  assert.ok(!JSON.stringify(calls[0][0]).includes('coverageGroup'));
  for (const resolution of ['unknown','defer']) {
    draft.resolution = resolution;await context.submitForm(question);
    assert.deepEqual(plain(calls.at(-1)[0]),{type:resolution,id:'T05'});
    assert.equal(calls.at(-1)[2],true);
  }
});

test('the actual goal Send waits for deliberate submission and uses the local opening when supported', async () => {
  const submitSource = source.slice(source.indexOf('  async function submitCurrent('),source.indexOf('  function renderForm('));
  const calls = [];
  const context = vm.createContext({doctorComposer:null,composing:false,busy:false,review:null,selectedGoal:'compare',state:{assessment:{narrative:{opener:true}}},$:() => ({value:''}),syncSend() {},turn:async (...args) => {calls.push(args);return true;}});
  vm.runInContext(openingSource+'\n'+submitSource,context);
  assert.equal(calls.length,0);
  await context.submitCurrent();
  assert.deepEqual(plain(calls[0][0]),{type:'choice',id:'T01',fields:{choice:'compare'}});
  assert.equal(calls[0][2],!openingSource);
  if (openingSource) assert.deepEqual(plain(calls[0][3]),{opening:true});
  assert.equal(context.selectedGoal,'');
});

test('an inline check choice uses the existing Send and typed words remain a normal message', {skip: !source.includes('conversationCheck?.question')},async()=>{
  const calls=[],input={value:''};
  const context=vm.createContext({composing:false,busy:false,doctorComposer:null,service:{},
    state:{conversationCheck:{question:{token:'current-question'}}},$:()=>input,
    window:{DaylightConversationChecks:{answer:()=>({token:'current-question',value:'exact-office',label:'Confirmed office'})}},
    turn:async(...args)=>calls.push(args)});
  vm.runInContext(source.slice(source.indexOf('  async function submitCurrent('),source.indexOf('  function renderForm(')),context);
  assert.equal(calls.length,0);
  await context.submitCurrent();
  assert.deepEqual(plain(calls[0][0]),{type:'check_answer',token:'current-question',value:'exact-office'});
  input.value='Why does the office matter?';await context.submitCurrent();
  assert.deepEqual(plain(calls[1][0]),{type:'message',message:input.value});
});

test('the local opening shows pending briefly and sends no AI context', {skip: !openingSource}, async () => {
  const h = harness();
  let finishDelay;
  h.context.performance = {now: () => 10};
  h.context.setTimeout = (resolve, delay) => {
    assert.equal(delay,process.env.DAYLIGHT_TEST_WEB === 'web-8894' ? 1850 : 350);
    finishDelay = resolve;
  };
  h.initial.assessment.narrative = {opener:true};
  h.response.openingChoice = 'learn';h.response.reply = '';
  const turn = h.turn({type:'choice',id:'T01',fields:{choice:'learn'}},'Understand Medicare',false,{opening:true});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.calls[0].payload.aiConsent,false);
  assert.equal(h.calls[0].payload.contextPolicy,null);
  assert.deepEqual(h.pending,[{kind:'begin',words:'Understand Medicare',usingAI:true}]);
  assert.equal(typeof finishDelay,'function');
  finishDelay();
  assert.equal(await turn,true);
  assert.equal(h.context.history[0].reply,'We can start with the Medicare basics.');
});

test('selected teaching citations are retained without adding a duplicate lesson body', async () => {
  const h = harness();
  h.response.advisor = {kind:'teach',topic:'learning',sources:[{url:'https://www.medicare.gov/basics',label:'Medicare basics'}]};
  h.response.facts = [];
  const words = h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.deepEqual(plain(h.context.history[0].sources),h.response.advisor.sources);
  assert.equal(h.context.history[0].facts.length,0);
  assert.equal(h.context.history[0].reply,h.response.reply);
  h.response.generated = {status:'unavailable'};h.response.notice = 'The reply could not finish.';
  h.element('message').value = 'Please explain that.';
  assert.equal(await h.turn({type:'message',message:'Please explain that.'},'Please explain that.'),true);
  assert.equal(h.context.history.at(-1).sources.length,0,'Invalid generated teaching cannot attach its proposed citations as a valid answer.');
});

test('optional educational follow-ups stay with their accepted exchange and never survive failed generation', async () => {
  const h=harness();
  const prompts=['How do the two paths differ on doctor choice?','What would I pay with each path?'];
  h.response.advisor={educationFollowups:prompts};
  let words=h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.deepEqual(plain(h.context.history[0].educationFollowups),prompts);
  h.response.generated={status:'unavailable'};h.response.notice='The reply could not finish.';
  words='Could you explain more?';h.element('message').value=words;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.deepEqual(plain(h.context.history.at(-1).educationFollowups),[]);
  assert.deepEqual(plain(h.context.history[0].educationFollowups),prompts,'Later failures do not rewrite an earlier accepted answer.');
});

test('pending presentation is temporary while a Send is unresolved and preserves a newer typed draft', async () => {
  const h = harness();
  let finish;
  h.context.api = async (url,payload) => {
    h.calls.push({url,payload:structuredClone(payload)});
    return await new Promise(resolve => { finish = resolve; });
  };
  const submitted = h.element('message').value;
  const pending = h.turn({type:'message',message:submitted},submitted);
  assert.equal(h.context.busy,true);
  assert.equal(h.calls.length,1);
  assert.equal(h.context.history.length,0,'A pending bubble must not commit a transcript entry.');
  assert.deepEqual(h.pending,[{kind:'begin',words:submitted,usingAI:true}]);
  assert.equal(h.element('message').value,'','The submitted text leaves the composer before a response arrives.');
  h.element('message').value = 'A separate question I am still writing.';
  finish(structuredClone(h.response));
  assert.equal(await pending,true);
  assert.equal(h.context.history.length,1);
  assert.equal(h.context.history[0].user,submitted);
  assert.equal(h.element('message').value,'A separate question I am still writing.');
  assert.equal(h.pending.filter(event => event.kind === 'end').length,1);
  assert.equal(h.context.busy,false);
});

test('the composer clears before transport settles and restores the exact raw draft after a failed Send', async () => {
  const h = harness();
  let fail;
  h.context.api = async (url,payload) => {
    if (url === '/api/conversation/recover') throw Error('Recovery connection unavailable.');
    h.calls.push({url,payload:structuredClone(payload)});
    return await new Promise((resolve,reject) => {fail=reject;});
  };
  const raw='  I would like a little more detail.\n\n';
  const sent=raw.trim();h.element('message').value=raw;
  const pending=h.turn({type:'message',message:sent},sent);
  assert.equal(h.calls.length,1);
  assert.equal(h.element('message').value,'','Do not leave a submitted draft visible for the model wait.');
  assert.deepEqual(h.pending,[{kind:'begin',words:sent,usingAI:true}]);
  fail(Error('Connection interrupted.'));
  assert.equal(await pending,false);
  assert.equal(h.element('message').value,raw,'A retry keeps the user’s original spacing and line breaks.');
  assert.deepEqual(Array.from(h.context.parkedMessages),[]);
  assert.equal(h.context.history.length,0);
  assert.equal(h.calls.length,1,'A failed Send never automatically repeats the model request.');
});

test('a failed Send preserves a newer composer draft and makes the submitted draft recoverable separately', async () => {
  const h = harness();
  let fail;
  h.context.api = async url => {
    if (url === '/api/conversation/recover') throw Error('Recovery connection unavailable.');
    return await new Promise((resolve,reject) => {fail=reject;});
  };
  const raw='  What does Part B cover?\n';
  const sent=raw.trim();h.element('message').value=raw;
  const pending=h.turn({type:'message',message:sent},sent);
  assert.equal(h.element('message').value,'');
  const newer='Also, my husband is still working.';h.element('message').value=newer;
  fail(Error('Connection interrupted.'));
  assert.equal(await pending,false);
  assert.equal(h.element('message').value,newer,'A failed earlier request must not overwrite a new unsent message.');
  assert.deepEqual(Array.from(h.context.parkedMessages),[raw],'Restore draft can recover the failed submitted message.');
  assert.equal(h.context.history.length,0);
});

test('reading a concept leaves an unrelated typed draft in the composer during the request', async () => {
  const h = harness();
  let finish;
  h.context.api = async () => await new Promise(resolve => {finish=resolve;});
  const raw='A separate question I am still writing.';h.element('message').value=raw;
  const pending=h.turn({type:'read_concept',id:'partb'});
  assert.equal(h.element('message').value,raw,'Only a submitted typed message should be cleared.');
  finish(structuredClone(h.response));
  assert.equal(await pending,true);
  assert.equal(h.element('message').value,raw);
});

test('a successful response cannot clear a newly typed identical message', async () => {
  const h=harness();let finish;
  h.context.api=async () => await new Promise(resolve => {finish=resolve;});
  const words=h.element('message').value;
  const pending=h.turn({type:'message',message:words},words);
  assert.equal(h.element('message').value,'');
  h.element('message').value=words;
  finish(structuredClone(h.response));
  assert.equal(await pending,true);
  assert.equal(h.element('message').value,words,'Text entered during the wait is a new draft, even if it repeats the submitted text.');
});

test('a failed Send removes pending presentation once without committing history or retrying', async () => {
  const h = harness(Error('Connection interrupted.'));
  const words = h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),false);
  assert.equal(h.calls.length,1);
  assert.equal(h.context.history.length,0);
  assert.equal(h.element('message').value,words);
  assert.deepEqual(h.pending,[{kind:'begin',words,usingAI:true},{kind:'end'}]);
  assert.equal(h.context.busy,false);
});

test('a guide stays with its teaching exchange and cannot migrate onto a later timing question', async () => {
  const h = harness();
  h.response.advisor={teachingFactIds:['routesintro'],sources:[]};
  h.response.assessment.narrative={visual:{kind:'routes',title:'Two coverage paths'}};
  let words=h.element('message').value;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.context.history[0].visual.kind,'routes');
  const firstVisual=h.context.history[0].visual;
  h.response.advisor={teachingFactIds:[],sources:[]};
  h.response.assessment.nextQuestion={id:'RC11',question:'When does your COBRA coverage end?'};
  words='I have COBRA.';h.element('message').value=words;
  assert.equal(await h.turn({type:'message',message:words},words),true);
  assert.equal(h.context.history[1].visual,null,'Historical narrative.visual is not current-turn teaching.');
  assert.equal(h.context.history[0].visual,firstVisual);
  assert.equal(h.context.state.assessment.nextQuestion.question,'When does your COBRA coverage end?');
  assert.equal(h.calls.length,2);
});

test('Plans view context is captured once on message Send and never on navigation',()=>{
  const h=harness();let snapshots=0;
  h.context.DaylightPlans={snapshot(){snapshots++;return {version:'plans-context-v1',viewDigest:'current'};}};
  const request=h.context.turnCandidate({type:'message',message:'Explain this term.'});
  assert.equal(request.plansContextPolicy,'plans-context-v1');
  assert.equal(request.plansContext.viewDigest,'current');assert.equal(snapshots,1);
  const navigation=h.context.turnCandidate({type:'review_plans'});
  assert.equal(navigation.plansContext,undefined);assert.equal(snapshots,1);
});
