const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../apps/chat/app.js'), 'utf8');
function load(response = {headers:{get:()=> 'text/html'}}) {
  const stub = () => ({hidden:false,inert:false,value:'',dataset:{},style:{},children:[],classList:{add(){},remove(){}},addEventListener(){},focus(){},setAttribute(){},append(...items){this.children.push(...items);},insertBefore(item,before){const n=this.children.indexOf(before);this.children.splice(n<0?this.children.length:n,0,item);},replaceChildren(...items){this.children=items;}});
  const nodes = new Map();
  const document = {createElement:stub,getElementById(id){if(!nodes.has(id))nodes.set(id,stub());return nodes.get(id);},querySelector(){return stub();},body:{classList:{add(){},remove(){},toggle(){}}},addEventListener(){}};
  const context = vm.createContext({document,window:{scrollTo(){}},requestAnimationFrame(){},crypto:require('node:crypto').webcrypto,
    fetch:async()=>response,AbortSignal,setTimeout,clearTimeout,Intl,Date,console,matchMedia:()=>({matches:false})});
  vm.runInContext(source,context);
  return {context, run:code=>vm.runInContext(code,context), json:code=>JSON.parse(vm.runInContext(`JSON.stringify(${code})`,context))};
}
const fixed = 'new Date(2026,9,20)';
function dates(i){const c=load();return c.json(`computeDates(${JSON.stringify(i)},${fixed})`);}
test('birthday alone never generates a Medigap window',()=>{
  for(const medicare of ['only_a','no','unsure','yes_ab']) assert.equal(dates({medicare,birthMonth:1,birthYear:2027,birthdayFirst:'no'}).medigapStart,null);
});
test('Medigap uses the later of age 65 and the actual Part B month',()=>{
  const i={medicare:'yes_ab',birthMonth:1,birthYear:2025,birthdayFirst:'no',partBStart:'2026-10'};
  assert.deepEqual(dates(i).medigapStart,{year:2026,month:10});
  assert.deepEqual(dates(i).medigapEnd,{year:2027,month:3});
  assert.deepEqual(dates({...i,birthYear:2027,partBStart:'2024-02'}).medigapStart,{year:2027,month:1});
});
test('only A is not turned into an existing A/B foundation',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),medicare:'only_a'};`);
  assert.match(c.json('buildMap()')[0].sentence,/Part B has not been added/);
});
test('first-of-month birthday shifts the seven-month initial window',()=>{
  const d=dates({birthMonth:1,birthYear:2027,birthdayFirst:'yes'});
  assert.deepEqual(d.iepStart,{year:2026,month:9});assert.deepEqual(d.iepEnd,{year:2027,month:3});
});
test('unknown first-day status does not imply an exact date',()=>assert.equal(dates({birthMonth:1,birthYear:2027,birthdayFirst:'unsure'}).known,false));
test('past and future windows are distinguished from the current window',()=>{
  assert.equal(dates({birthMonth:1,birthYear:2025,birthdayFirst:'no'}).period,'past');
  assert.equal(dates({birthMonth:1,birthYear:2027,birthdayFirst:'no'}).period,'current');
  assert.equal(dates({birthMonth:12,birthYear:2028,birthdayFirst:'no'}).period,'upcoming');
});
test('old beneficiaries are not constrained to the former 2025-2028 range',()=>assert.equal(dates({birthMonth:6,birthYear:2005,birthdayFirst:'no'}).iepStart.year,2005));
test('job coverage does not produce a guessed initial or Medigap deadline',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),medicare:'only_a',job:'yes',birthMonth:1,birthYear:2025,birthdayFirst:'no',employmentEnd:'2026-11',coverageEnd:'2026-12'};`);
  const items=c.json('dateItems()');assert.equal(items.length,3);assert.match(items[2][1],/Confirm/);assert.doesNotMatch(JSON.stringify(items),/January 2025|Medigap window/);
});
test('Medigap dates are not introduced before their explanation',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),medicare:'yes_ab',leaning:'original',partBStart:'2026-10',birthMonth:1,birthYear:2025,birthdayFirst:'no'};`);
  assert.equal(c.json('dateItems()').some(r=>r[0].includes('Medigap')),false);
  c.run('state.journey.visited.add(5)');assert.equal(c.json('dateItems()').some(r=>r[0].includes('Medigap')),true);
});
test('unanswered, unknown and no-prescription states remain distinct',()=>{
  const c=load();
  for(const [drugs,expected] of [[undefined,'not answered'],['unsure','unknown'],['no','no regular']]){
    c.run(`state.intake={...freshIntake(),drugs:${JSON.stringify(drugs)||'undefined'}}`);
    assert.match(c.json('buildMap()').find(r=>r.title==='Comparison needs').sentence,new RegExp(expected));
  }
});
test('unknown county is a needs-attention state, not completed or outside',()=>{
  const c=load();c.run(`state.journey.reached=7;state.journey.stop=6;state.intake={...freshIntake(),recipient:'self',goal:'learn',zip:'34102',county:'unsure'};`);
  assert.equal(c.run('journeyStatus(0)'),'blocked');assert.equal(c.run('state.intake.county'),'unsure');
});
test('skipping to the final page never checks off unvisited questions',()=>{
  const c=load();c.run(`state.journey.reached=7;state.journey.stop=7;state.journey.visited=new Set([0,1,2,7]);`);
  for(const n of [3,4,5,6])assert.equal(c.run(`journeyStatus(${n})`),'skipped');
});
test('failed records remain blocked even on the final map',()=>{
  const c=load();c.run(`state.journey.reached=7;state.journey.stop=7;state.plansError='unavailable';`);
  assert.equal(c.run('journeyStatus(6)'),'blocked');assert.match(c.json('buildMap()').at(-1).sentence,/No plan comparison was completed/);
});
test('doctor and medicine notes are retained in the actionable checklist',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),doctor:'Dr Example',medicines:'Example medicine 5 mg',drugs:'yes',priorities:['keep_doctors']};`);
  const notes=c.json('checklistItems()').join(' ');assert.match(notes,/Dr Example/);assert.match(notes,/Example medicine 5 mg/);
});
test('unscored priorities and prescription use never silently become a financial sort',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),drugs:'yes',priorities:['keep_doctors','travel'],extras:['dental']};`);
  assert.deepEqual(c.json('intakeToPriorities().priorities'),[]);
  assert.deepEqual(c.json('intakeToPriorities().unscored'),['keep_doctors','travel','dental','medicines']);
});
test('published financial criteria retain an explicitly chosen order',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),priorities:['low_premium','predictable'],priorityOrder:['predictable','low_premium']};`);
  assert.deepEqual(c.json('intakeToPriorities().priorities'),['medical_limit','monthly_premium']);
});
test('HTML responses never leak JSON parsing or server HTML into the UI',async()=>{
  const c=load();await assert.rejects(c.run(`requestJSON('/api/catalog')`),error=> /isn't connected/.test(error.message)&& !/Unexpected token|DOCTYPE/.test(error.message));
});
test('pending validation stays closed and communicates the actual blocker',async()=>{
  const c=load({headers:{get:()=> 'application/json'},ok:false,status:503,json:async()=>({validation_status:'pending',error:'internal'})});
  await assert.rejects(c.run(`requestJSON('/api/catalog')`),error=>error.pending&&/awaiting validation/.test(error.message));
});
test('malformed JSON gets a recovery message',async()=>{
  const c=load({headers:{get:()=> 'application/json'},ok:true,json:async()=>{throw new SyntaxError('raw internal');}});
  await assert.rejects(c.run(`requestJSON('/api/catalog')`),error=>/usable response/.test(error.message)&&!error.message.includes('raw internal'));
});
test('new applicants receive an A/B enrollment action rather than only a plan-shopping task',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),medicare:'no',social:'no',job:'no'};`);
  assert.match(c.json('checklistItems()').join(' '),/apply for Parts A and B/);
});
test('automatic enrollment remains a notice/effective-date check',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),medicare:'no',social:'yes'};`);
  assert.match(c.json('checklistItems()').join(' '),/automatic-enrollment notice/);
});
test('adding B is distinct from both-parts enrollment',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),medicare:'only_a',job:'no'};`);
  assert.match(c.json('checklistItems()').join(' '),/adding Part B/);
});
test('uncertain Social Security benefits keep Medicare timing unresolved',()=>{
  const c=load();c.run(`state.journey.reached=7;state.journey.stop=7;state.intake={...freshIntake(),medicare:'no',social:'unsure',timingReviewed:true};`);
  assert.equal(c.run('journeyStatus(1)'),'blocked');
});
test('a network failure gets a useful recovery message',async()=>{
  const c=load();c.context.fetch=async()=>{throw new TypeError('Failed to fetch');};
  await assert.rejects(c.run(`requestJSON('/api/catalog')`),error=>/couldn't be reached/.test(error.message)&& !/Failed to fetch/.test(error.message));
});
test('invalid month formats never become effective dates',()=>{
  for(const value of ['2026-13','2026-00','not a date','2026-1','1899-05'])assert.equal(load().run(`parseMonth(${JSON.stringify(value)})`),null);
});
test('changing Medicare status resets the dependent route, while keeping personal notes',()=>{
  const c=load();c.run(`renderStop=()=>{};invalidatePlans=()=>{};state.intake={...freshIntake(),medicare:'yes_ab',partBStart:'2026-04',currentCoverage:'advantage',coverageReviewed:true,doctor:'Dr Example'};state.screen.coverage='review';pick('medicare','only_a',true);`);
  assert.equal(c.run('state.screen.coverage'),'context');assert.equal(c.run('state.intake.partBStart'),undefined);assert.equal(c.run('state.intake.currentCoverage'),undefined);assert.equal(c.run('state.intake.coverageReviewed'),false);assert.equal(c.run('state.intake.doctor'),'Dr Example');
});
test('changing the work answer removes stale transition dates and goal',()=>{
  const c=load();c.run(`renderStop=()=>{};invalidatePlans=()=>{};state.intake={...freshIntake(),job:'yes',jobGoal:'plan',employmentEnd:'2026-11',coverageEnd:'2026-12',employerSize:'20plus'};pick('job','no');`);
  for(const key of ['jobGoal','employmentEnd','coverageEnd','employerSize'])assert.equal(c.run(`state.intake.${key}`),undefined);
});
test('an already-enrolled worker is not told to apply for Part B again',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),medicare:'yes_ab',goal:'job',job:'yes',currentCoverage:'employer',employmentEnd:'2026-11',coverageEnd:'2026-12'};`);
  assert.equal(c.json('dateItems()').some(item=>item[0]==='Part B enrollment'),false);
  assert.equal(c.json('dateItems()').some(item=>item[0]==='Replacement coverage'),true);
  assert.doesNotMatch(c.json('checklistItems()').join(' '),/CMS-40B/);
  assert.match(c.json('buildMap()').find(s=>s.title==='Work-coverage transition').sentence,/Parts A and B are already in place/);
});
test('a birth year is converted to age-65 timing without user arithmetic',()=>{
  const d=dates({dobMonth:1,dobYear:1962,birthdayFirst:'no'});
  assert.deepEqual(d.turn65,{month:1,year:2027});
  assert.deepEqual(d.iepStart,{month:10,year:2026});
  assert.deepEqual(d.iepEnd,{month:4,year:2027});
});
test('first-day timing is preserved when entering an actual birth date',()=>{
  const d=dates({dobMonth:1,dobYear:1962,birthdayFirst:'yes'});
  assert.deepEqual(d.iepStart,{month:9,year:2026});
  assert.deepEqual(d.iepEnd,{month:3,year:2027});
});
test('birth date still cannot substitute for a confirmed Part B month',()=>{
  const i={dobMonth:1,dobYear:1962,birthdayFirst:'no',medicare:'yes_ab'};
  assert.equal(dates(i).medigapStart,null);
  assert.deepEqual(dates({...i,partBStart:'2026-10'}).medigapStart,{month:1,year:2027});
});
test('an explicitly unknown birth date does not generate exact deadlines',()=>{
  assert.equal(dates({dobMonth:1,dobYear:1962,birthdayFirst:'no',birthSkipped:true}).known,false);
});
test('a fresh guide does not choose personal answers or a coverage route',()=>{
  const i=load().json('freshIntake()');
  for(const key of ['recipient','goal','medicare','job','drugs','leaning','birthdayFirst']) assert.equal(i[key],undefined);
  assert.deepEqual(i.priorities,[]); assert.deepEqual(i.extras,[]);
});
test('unknown birth timing remains an open check in journey progress',()=>{
  const c=load(); c.run(`state.journey.reached=7;state.journey.stop=7;state.intake={...freshIntake(),coverageReviewed:true,birthSkipped:true};`);
  assert.equal(c.run('journeyStatus(2)'),'blocked');
  c.run(`state.intake.birthSkipped=false;state.intake.birthdayFirst='unsure'`);
  assert.equal(c.run('journeyStatus(2)'),'blocked');
});
test('basic typed questions identify the right coverage part explicitly',()=>{
  const c=load();
  assert.match(c.json(`findGuideTopic('What is Part B?')`).answer,/^Part B is medical insurance/);
  assert.match(c.json(`findGuideTopic('What does Part A cover?')`).answer,/^Part A is hospital insurance/);
  assert.equal(c.json(`findGuideTopic('What is Part D?')`).visual,'drugs');
});
test('guide lookup does not turn personal decisions into generic matching answers',()=>{
  const c=load();
  for(const question of ['Should I choose Medicare Advantage?','Does my doctor accept this plan?','Do I need Part B?','What will my medicines cost?']) {
    assert.equal(c.json(`findGuideTopic(${JSON.stringify(question)})`),null);
  }
});
test('a typed guide explanation works offline without sending notes or changing the journey',async()=>{
  const c=load();let requests=0;c.context.fetch=async()=>{requests++;throw new Error('should not send a guide question');};
  c.run(`state.intake={...freshIntake(),recipient:'someone',doctor:'TEST ONLY office'};state.journey.stop=3;`);
  const before=c.json('state.intake');await c.run(`askTyped('What is Part B?')`);
  assert.equal(requests,0);assert.equal(c.run('state.journey.stop'),3);assert.deepEqual(c.json('state.intake'),before);
  assert.equal(c.run('state.busy'),false);assert.match(c.json('state.history').at(-1).content,/^Part B is medical insurance/);
});
test('guide follow-up context remains bounded to recent explicit chat exchanges',()=>{
  const c=load();for(let n=0;n<7;n++)c.run(`rememberChat('Question ${n}','Answer ${n}')`);
  const history=c.json('state.history');assert.equal(history.length,8);assert.equal(history[0].content,'Question 3');
});
test('each stage has source-linked lesson topics with a relevant picture',()=>{
  const c=load();for(let n=0;n<8;n++){
    const lesson=c.json(`lessonFor(${n})`);assert.ok(lesson.visual);assert.match(lesson.source,/^https:\/\//);
    for(const id of lesson.topics)assert.ok(c.run(`Boolean(GUIDE_TOPICS[${JSON.stringify(id)}])`));
  }
});
test('focused help protects the guide on phone and desktop, then releases it on return',()=>{
  const c=load();c.run(`el('ask-panel').hidden=false`);c.context.matchMedia=()=>({matches:true});c.run('syncAskLayout()');
  assert.equal(c.run(`el('main').inert`),true);assert.equal(c.run(`el('journey-map').inert`),true);
  c.context.matchMedia=()=>({matches:false});c.run('syncAskLayout()');assert.equal(c.run(`el('main').inert`),true);
  c.run('closeAsk(false)'); assert.equal(c.run(`el('main').inert`),false);assert.equal(c.run(`el('journey-map').inert`),false);
});
test('Daylight privacy answers use app provenance and do not cite Medicare for app behavior',()=>{
  const c=load(); const topic=c.json(`findGuideTopic('What happens to my answers?')`);
  assert.equal(topic.source,null);assert.equal(topic.sourceLabel,'Daylight · about your answers');
  assert.match(topic.answer,/existing guide explanation are answered in this tab/);
  assert.match(topic.answer,/Submitted chat may be logged/);
});
test('reported A/B does not mark an unknown coverage arrangement as an entered fact',()=>{
  const c=load();for(const currentCoverage of [undefined,'unsure']) {
    c.run(`state.intake={...freshIntake(),medicare:'yes_ab',currentCoverage:${JSON.stringify(currentCoverage)}}`);
    assert.equal(c.json('buildMap()')[0].status,'A/B reported; arrangement unknown');
    assert.match(c.json('buildMap()')[0].sentence,/arrangement is still to confirm/);
  }
  c.run(`state.intake.currentCoverage='supplement'`); assert.match(c.json('buildMap()')[0].sentence,/Original Medicare \+ Medigap/);
  c.run(`state.intake.currentCoverage='unsure'`); assert.match(c.json('checklistItems()').join(' '),/identify how coverage is arranged/);
});
test('the focused answer keeps the literal submitted question before its reply and preserves the draft',async()=>{
  const c=load();c.run(`el('ask-input').value='Unsent test draft'`);await c.run(`askTyped('Explain Part B')`);
  assert.equal(c.run(`el('ask-thread').children[0].dataset.question`),'Explain Part B');
  assert.equal(c.run(`el('ask-thread').children[0].children[0].textContent`),'Explain Part B');
  assert.match(c.run(`el('ask-thread').children[0].children[1].children[1].textContent`),/^Part B is medical insurance/);
  assert.equal(c.run(`el('ask-input').value`),'Unsent test draft');
});
test('help at a new concept offers current questions and keeps earlier answers accessible',()=>{
  const c=load();c.run(`answerGuideTopic('basics');closeAsk(false);state.journey.stop=3;openAsk()`);
  assert.equal(c.run(`el('ask-thread').hidden`),true);assert.equal(c.run(`el('ask-intro').hidden`),false);
  const labels=c.json(`el('ask-canned').children.map(n=>n.textContent)`);
  assert.ok(labels.includes('What does Part D do?'));assert.ok(labels.includes('Read earlier questions (1)'));
  c.run(`answerGuideTopic('drugbasics')`);assert.equal(c.run(`el('ask-thread').hidden`),false);
  assert.equal(c.run(`el('ask-thread').children.length`),2);assert.equal(c.json('state.history').length,4);
});
test('live chat sends only explicit conversation and keeps the reply with the submitted question',async()=>{
  const c=load();await c.run('checkConnection()');const calls=[];
  c.context.fetch=async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({text:'TEST reply',question:'TEST follow-up'})};};
  c.run(`checkConnection=async()=>{state.live=true;};state.intake={...freshIntake(),doctor:'PRIVATE TEST NOTE',medicines:'PRIVATE TEST LIST'};rememberChat('Earlier explicit question','Earlier explicit answer')`);
  await c.run(`askTyped('Explain a topic beyond the guide')`);
  assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/live-chat');
  assert.deepEqual(Object.keys(calls[0].body).sort(),['conversation_id','history','message']);
  assert.doesNotMatch(JSON.stringify(calls[0].body),/PRIVATE TEST/);
  assert.equal(c.run(`el('ask-thread').children[0].children[1].children[1].textContent`),'TEST reply\n\nTEST follow-up');
  assert.equal(c.run('state.busy'),false);
});
test('starting over clears the chat and restores a fresh guide',()=>{
  const c=load();c.run(`state.chatTurns=4;state.chatWelcomed=true;rememberChat('Test question','Test answer');startOver()`);
  assert.equal(c.run('state.chatTurns'),0);assert.equal(c.run('state.chatWelcomed'),false);assert.deepEqual(c.json('state.history'),[]);
  assert.equal(c.run('state.journey.stop'),0);assert.equal(c.run('state.intake.recipient'),undefined);
});
test('a guided start asks the goal first and keeps the beginner picture to Medicare itself',()=>{
  const c=load();const lesson=c.json('lessonFor(0)');
  assert.equal(lesson.id,'basics');assert.deepEqual(lesson.concepts,['medicare']);assert.deepEqual(lesson.topics,['basics']);
  assert.match(c.json(`findGuideTopic('What is Medicare?')`).answer,/federal government/);
  c.run('renderStop=()=>{};beginJourney()');assert.equal(c.run('state.screen.start'),'goal');
});
test('coverage concepts arrive in the order their questions require them',()=>{
  const c=load();
  const expected=[[1,['medicare','parts']],[3,['medicare','parts','drugs']],[4,['medicare','parts','drugs','extras']],[5,['medicare','parts','drugs','extras','costs']]];
  for(const [n,concepts] of expected)assert.deepEqual(c.json(`lessonFor(${n}).concepts`),concepts);
  c.run(`state.screen.priorities='routesIntro'`);assert.equal(c.run(`lessonFor(5).concepts.includes('routes')`),true);assert.equal(c.run(`lessonFor(5).concepts.includes('medigap')`),false);
  c.run(`state.screen.priorities='medigapIntro'`);assert.equal(c.run(`lessonFor(5).concepts.includes('medigap')`),true);
});
test('going back preserves learned concepts without selecting personal answers',()=>{
  const c=load();c.run(`teachLesson(lessonFor(3));teachLesson(lessonFor(0))`);
  assert.deepEqual(c.json('[...state.learned]'),['medicare','parts','drugs']);
  assert.deepEqual(c.json('state.intake'),c.json('freshIntake()'));assert.equal(c.run('answeredStop(3)'),false);
});
test('route teaching does not force every person through a supplement lesson',()=>{
  const c=load();assert.equal(c.run('nextRouteLesson()'),'routesIntro');
  c.run(`state.learned.add('routes')`);assert.equal(c.run('nextRouteLesson()'),'route');
  c.run(`state.learned.add('medigap')`);assert.equal(c.run('nextRouteLesson()'),'route');
  assert.equal(c.run('state.intake.leaning'),undefined);
});
test('experienced comparison skips the beginner lesson and keeps earlier answers unknown',()=>{
  const c=load();c.run('renderStop=()=>{};beginJourney(true)');
  assert.equal(c.run('state.screen.start'),'compareKind');assert.equal(c.run('state.intake.goal'),'compare');assert.equal(c.run('state.guideOpen'),false);
  assert.equal(c.run('lessonFor(0).concepts.includes("medigap")'),true);
  assert.equal(c.run('answeredStop(1)'),false);assert.equal(c.run('state.intake.medicare'),undefined);
});
test('reset removes learned complexity as well as the personal and conversation state',()=>{
  const c=load();c.run(`teachLesson(lessonFor(7));startOver()`);
  assert.deepEqual(c.json('[...state.learned]'),['medicare']);assert.equal(c.run('nextRouteLesson()'),'routesIntro');
});
test('an already-taught route returns Back to the actual preceding priority question',()=>{
  const c=load();c.run(`renderStop=()=>{};state.learned=new Set(['medicare','parts','routes','medigap']);openOptions('top')`);
  assert.equal(c.run('state.screen.priorities'),'route');assert.equal(c.run('state.screen.routeBack'),'top');
});
test('a newly introduced route remembers the actual preceding teaching page',()=>{
  const c=load();c.run(`renderStop=()=>{};openOptions('priorities')`);
  assert.equal(c.run('state.screen.priorities'),'routesIntro');
  c.run(`completeRouteLesson('medigapIntro')`);
  assert.equal(c.run('state.screen.priorities'),'route');assert.equal(c.run('state.screen.routeBack'),'medigapIntro');
});

test('reported enrollment with unknown parts stays distinct from unknown enrollment',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),medicare:'yes_unknown_parts'};state.journey.reached=7;`);
  assert.equal(c.run('reviewMode()'),false);assert.equal(c.run('decidingPartB()'),false);
  assert.equal(c.run('unresolvedStop(1)'),true);
  assert.match(c.json('buildMap()')[0].sentence,/reported Medicare enrollment/);
  assert.match(c.json('checklistItems()').join(' '),/effective dates/);
  assert.equal(c.json('dateItems()').some(r=>/Initial enrollment window/.test(r[0])),false);
  c.run(`state.intake.medicare='unsure'`);assert.doesNotMatch(c.json('buildMap()')[0].sentence,/reported Medicare enrollment/);
});
test('another Medicare combination is not turned into Part A only or a new applicant',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),medicare:'different',medicareDetails:'Part B only'};`);
  assert.match(c.json('buildMap()')[0].sentence,/Part B only/);
  assert.doesNotMatch(c.json('checklistItems()').join(' '),/apply for Parts A and B/);
});
test('changing goal retains notes and candidates while invalidating the old comparison',()=>{
  const c=load();c.run(`renderStop=()=>{};state.intake={...freshIntake(),goal:'compare',medicines:'TEST LIST',doctor:'TEST OFFICE'};state.selected.set('test',{id:'test'});state.comparison={plans:[]};state.guidePreference=false;state.guideOpen=false;pick('goal','learn');`);
  assert.equal(c.run('state.intake.medicines'),'TEST LIST');assert.equal(c.run('state.selected.size'),1);
  assert.equal(c.run('state.comparison'),null);assert.equal(c.run('state.comparisonStale'),true);
  assert.equal(c.run('state.guideOpen'),false);
});
test('pure learning needs neither geography nor a compulsory shopping task',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),goal:'learn',recipient:'self'};state.personalReview=false;`);
  assert.equal(c.run('answeredStop(0)'),true);assert.deepEqual(c.json('routeStops()'),[0,7]);
  assert.equal(c.json('supportTasks()')[0].id,'learning');
  assert.doesNotMatch(c.json('checklistGroups()').map(g=>g.items.join(' ')).join(' '),/Complete the local plan search/);
});
test('work-coverage support offers a usable draft and does not instruct enrolled people to apply again',()=>{
  const c=load();c.run(`state.intake={...freshIntake(),goal:'job',job:'yes',medicare:'yes_ab',employmentEnd:'2026-11'};`);
  assert.equal(c.json('supportTasks()')[0].id,'benefits');
  assert.match(c.run(`preparationText('benefits')`),/exact last days/);
  assert.match(c.run(`preparationText('benefits')`),/2026-11/);
  assert.doesNotMatch(c.run(`preparationText('enrollment')`),/CMS-40B|Which enrollment period/);
  assert.match(c.run(`preparationText('benefits')`),/No one has been contacted/);
});
test('final Back follows a direct transition route rather than unvisited plans',()=>{
  const c=load();c.run(`renderStop=()=>{};state.journey.stop=2;state.screen.coverage='transition';advance(7);returnFromFinish();`);
  assert.equal(c.run('state.journey.stop'),2);assert.equal(c.run('state.screen.coverage'),'transition');
  assert.equal(c.run('state.journey.visited.has(6)'),false);
});
test('the complete HUD snapshot retains multi-county ZIPs instead of majority picking',()=>{
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../../apps/chat/zip-counties.json'),'utf8'));
  assert.deepEqual(data.zips['34102'],[['12021','Collier County','FL']]);
  assert.ok(data.zips['34134'].length>1);assert.ok(data.zips['34134'].some(r=>r[0]==='12021'));assert.ok(data.zips['34134'].some(r=>r[0]==='12071'));
  assert.equal(data.period,'September 2025');assert.match(data.source_url,/CMSgov/);
});
