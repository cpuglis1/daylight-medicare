const assert=require('node:assert/strict'),fs=require('fs');
const C=require('../apps/chat-alternative/chat-core.js'),P=require('../apps/chat-alternative/ten-state.js'),R=require('../apps/chat-alternative/readiness-core.js');
const content=JSON.parse(fs.readFileSync(__dirname+'/../apps/chat-alternative/readiness-content.json')),ref=JSON.parse(fs.readFileSync(__dirname+'/../apps/chat-alternative/zip-counties.json'));
const state=C.create();assert.equal(C.summary(state).reported,0);assert.equal(C.summary(state).checks.RC21.state,'not_applicable');assert.equal(C.next(state,content).id,'T01');
function text(message){const q=C.next(state,content),p=C.parse(state,message,q,ref,content);state.readiness.requests=[...new Set([...state.readiness.requests,...p.requests])];if(p.disposition){C.unknown(state,q,p.disposition);return;}return C.stage(state,p.baseline,p.reports,ref);}
// Turn 1 mixes exact suggested meaning and free text; later answers remove redundant prompts.
text('I want to find coverage. New to Medicare. My ZIP is 34102. Coverage starts January 2027.');assert.equal(C.next(state,content).id,'RC01');assert.equal(P.val(state.guide,'coverage.requestedStartMonth'),'2027-01');
text('For me. I have Original Medicare and Medigap.');assert.equal(C.next(state,content).id,'T06');assert.deepEqual(P.val(state.guide,'coverage.current'),['original','medigap']);
text('Doctors: Alice Example; Bob Example. Medicines: ExampleOne 5 mg tablet generic; ExampleTwo 10 mg capsule generic. Local only. More predictable costs. Priorities: doctors and prescriptions.');
assert.equal(R.entities(state.readiness,state.guide,'RC21').length,2);assert.equal(R.entities(state.readiness,state.guide,'RC22').length,2);assert.equal(C.next(state,content).id,'RC21');const before=C.summary(state);assert(before.reported>0&&before.percent<100);assert.equal(before.externalVerificationMissing.providers,'network_data_missing');
const beforeDoctor=C.summary(state).reported;C.stage(state,[],[{triggerId:'RC21',value:{choice:'details',entity:'doctor-1',practice:'Alice Example Clinic',city:'Naples FL'}}],ref);assert.equal(C.summary(state).reported,beforeDoctor+1);assert.match(C.next(state,content).question,/Bob Example/);assert(!C.next(state,content).question.includes('Alice Example'));
C.unknown(state,C.next(state,content),'deferred');assert.equal(C.next(state,content),null);assert(C.summary(state).deferred>0);
// Correcting a confirmed fact pauses for a conversational confirmation, then resumes without a reset.
let res=text('I want to review my coverage.');assert(res.pending);assert.equal(C.next(state,content).id,'confirm');assert.equal(P.val(state.guide,'intent.goal'),'compare');C.confirm(state,false,ref);assert.equal(P.val(state.guide,'intent.goal'),'compare');
state.edit='T08';res=C.stage(state,[{id:'T08',data:{value:['another_state','outside_us']}}],[],ref);assert(res.pending);C.confirm(state,true,ref);assert.deepEqual(P.val(state.guide,'needs.travel'),['another_state','outside_us']);assert.equal(C.next(state,content).id,'RC20');assert(C.summary(state).total>before.total);
C.stage(state,[],[{triggerId:'RC20',value:{choice:'us',location:'New York and Canada'}}],ref);assert.equal(C.next(state,content),null);
// True comparison request must never leak into the learning-only short route.
C.stage(state,[{id:'T01',data:{value:'learn'}}],[],ref);C.confirm(state,true,ref);state.readiness.requests.push('personal_pricing');C.sync(state);assert(R.pending(state.readiness,state.guide).includes('RC23'));
assert.throws(()=>C.next(state,null),/unavailable/);assert.throws(()=>C.stage(state,[{id:'T05',data:{value:['none','medigap']}}],[],ref));
const deferred=C.create();C.unknown(deferred,{...P.Q[0],baseline:true},'deferred');assert.equal(C.baselineStatus(deferred,P.Q[0]),'deferred');
const fresh=C.create();const doctors=C.parse(fresh,'Doctors: Dr. Smith; Dr. Jones',{...P.Q[5],baseline:true},ref,content);assert.equal(doctors.baseline[0].data.text,'Dr. Smith; Dr. Jones');assert.equal(C.parse(fresh,"I don't take any medications",{...P.Q[6],baseline:true},ref,content).baseline[0].data.value,'no');assert.equal(C.parse(fresh,'What does provider mean?',{...P.Q[5],baseline:true},ref,content).baseline.length,0);
// Save/resume projection, not transcript/draft storage. Used by the HTTP tests.
state.guide.preferences.saveGuide=true;state.guide.preferences.saveSensitive=true;state.guide.flow.node='R00';C.summary(state);
if(process.argv.includes('--fixture'))process.stdout.write(JSON.stringify({guide:state.guide,record:state.readiness}));else console.log('Conversation scenario passed: mixed three turns, later facts, multiple entities, conditional followup, correction, defer, progress and learning-scope guard.');
