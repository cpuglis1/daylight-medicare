/* Master v1 first-slice state. In-memory only; server persistence requires a later capability. */
(function (root, factory) { const api = factory(); if (typeof module === 'object' && module.exports) module.exports = api; else root.DaylightState = api; })(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const PHASES = ['Your goal','Your situation','Your options','Your next step'];
  const FIELDS = {'intent.goal':['learn','compare','review','job','unresolved'],'subject.role':['self','someone','other'],'knowledge.general':['new','some','comfortable','unknown'],'privacy.persistenceChoice':['visit_only'],'subject.displayLabel':null};
  const blank = field => ({field,value:null,status:'unanswered',confirmation:'not_required',rawText:'',source:null,evidenceRefs:[],saveScope:'visit_only',revision:0});
  function create() { return {schemaVersion:1,stateVersion:0,subjectId:'local-'+Math.random().toString(36).slice(2),fields:Object.fromEntries(Object.keys(FIELDS).map(k=>[k,blank(k)])),coverage:{enrollment:blank('coverage.enrollment')},topics:{},flow:{node:'A01',history:[],queue:[],lessonReturn:null,drafts:{},guideOpen:true,pending:null,visited:[],invalidations:[]},sync:{status:'unsaved',mode:'visit_only',acknowledgedStateVersion:null},events:[],operations:{}}; }
  const value = (s,k) => s.fields[k]?.value;
  const known = (s,k) => s.fields[k]?.confirmation==='confirmed_by_user' && s.fields[k]?.status!=='stale';
  function apply(s, command) {
    const {expectedStateVersion,idempotencyKey,patches,rawText='',nodeId=s.flow.node,kind='user_choice'}=command;
    if (!idempotencyKey) throw Error('A command key is required.');
    const signature=JSON.stringify({patches,rawText,nodeId,kind});
    if(s.operations[idempotencyKey]) {if(s.operations[idempotencyKey].signature!==signature)throw Error('Command key already used.');return s.operations[idempotencyKey].revision;}
    if(expectedStateVersion!==s.stateVersion)throw Error('Details changed. Review the interpretation again.');
    if(!Array.isArray(patches)||!patches.length)throw Error('Choose at least one detail to confirm.');
    for(const p of patches){const valid=p.field==='subject.displayLabel'?typeof p.value==='string'&&p.value.length<=80&&!/[<>]|\d{7,}/.test(p.value):FIELDS[p.field]?.includes(p.value);if(!valid||!['reported','unknown','skipped'].includes(p.status||'reported'))throw Error('Unsupported profile detail.');}
    const role=patches.find(p=>p.field==='subject.role');
    if(role&&known(s,'subject.role')&&value(s,'subject.role')!==role.value)throw Error('A different person needs a separate guide.');
    const revision=s.stateVersion+1, changes=[];
    for(const p of patches){const before=s.fields[p.field];s.fields[p.field]={...blank(p.field),value:p.value,status:p.status||'reported',confirmation:'confirmed_by_user',rawText,source:{kind,nodeId,actor:'guest',eventId:idempotencyKey},capturedAt:new Date().toISOString(),confirmedAt:new Date().toISOString(),revision};changes.push({field:p.field,before,after:s.fields[p.field]});if(before.value!==p.value&&p.field==='intent.goal')s.flow.invalidations.push('next_task','comparison_rationale','preparation_context');if(before.value!==p.value&&p.field==='knowledge.general')s.flow.invalidations.push('teaching_queue');}
    s.stateVersion=revision;s.events.push({revision,kind:'ApplyConfirmedPatch',changes});s.operations[idempotencyKey]={signature,revision};return revision;
  }
  function propose(s,raw,nodeId=s.flow.node) {
    const text=String(raw).trim();if(!text||text.length>1200)throw Error('Use 1–1200 characters.');
    const t=text.toLowerCase().replace(/[’]/g,"'"),patches=[],unresolved=[];
    const goals=[];if(/\b(compare|comparing|shop for)\b.*\b(plans?|coverage|options)\b/.test(t))goals.push('compare');if(/\b(review|change|replace|add to)\b.*\b(coverage|plan)\b/.test(t))goals.push('review');if(/\b(job|employer|work)\b.*\b(end|ending|ends|retir|leav|los)/.test(t))goals.push('job');if(/\b(learn about|understand)\b.*\bmedicare\b/.test(t))goals.push('learn');
    if(goals.length===1)patches.push({field:'intent.goal',value:goals[0]});else if(goals.length>1)unresolved.push('More than one possible goal: please choose the goal below.');
    const someone=/\b(my (mom|mum|mother|dad|father|parent|wife|husband|partner)|helping someone|for someone)\b/.test(t),self=/\b(for me|for myself|myself)\b/.test(t);
    if(someone!==self&&(someone||self))patches.push({field:'subject.role',value:someone?'someone':'self'});
    let knowledge=null;
    if(/\b(new to medicare|don't know (much|anything) about medicare|not familiar with medicare)\b/.test(t))knowledge='new';
    else if(/\b(know (a little|some basics)|know some medicare|know a bit)\b/.test(t))knowledge='some';
    else if(!/\b(not|don't feel) comfortable\b/.test(t)&&(/\b(comfortable with (medicare|the basics)|know the basics|understand the basics)\b/.test(t)||nodeId==='A04'&&/^i('?m| am) comfortable[.!]?$/.test(t)))knowledge='comfortable';
    if(knowledge)patches.push({field:'knowledge.general',value:knowledge});
    const requestedTopic=/\b(explain|what|help|understand)\b/.test(t)?/part b/.test(t)?'partb':/part a/.test(t)?'parta':/medicare/.test(t)?'basics':null:null;
    if(!patches.length)unresolved.push('I could not reliably turn this into a starting detail. Your original words are retained; you can choose a detail manually or ask a question.');
    return {rawText:text,nodeId,expectedStateVersion:s.stateVersion,patches,unresolved,requestedTopic};
  }
  function phase(node,origin='A01'){if(node==='X01')return phase(origin);return node.startsWith('A')?0:node.startsWith('L')?1:node.startsWith('O')?2:3;}
  function visit(s,id){s.flow.node=id;if(!s.flow.visited.includes(id))s.flow.visited.push(id);const concept={L00:'medicare',L02:'part_a',L03:'part_b',L04:'original',L05:'drugs'}[id];if(concept&&!s.topics[concept])s.topics[concept]={seenAt:new Date().toISOString(),selfReport:'unknown'};}
  function nextMissing(s){if(!known(s,'intent.goal'))return 'A01';if(!known(s,'subject.role'))return 'A02';if(!known(s,'knowledge.general'))return 'A03';if(!known(s,'privacy.persistenceChoice'))return 'A05';return startRoute(s);}
  function startRoute(s){const goal=value(s,'intent.goal'),depth=value(s,'knowledge.general');s.flow.queue=[];s.flow.lessonReturn=null;if(goal==='learn'||goal==='unresolved')return 'L00';if(depth!=='comfortable'){s.flow.queue=['L02','L03','L04'];s.flow.lessonReturn=goal==='compare'?'O00':'C00';return 'L00';}return goal==='compare'?'O00':'C00';}
  function afterLesson(s,id){const fallback={L00:'L01',L02:'L03',L03:'L04',L04:'L05',L05:'L01'}[id]||'L01';if(s.flow.queue.length){const at=s.flow.queue.indexOf(id);return s.flow.queue[at+1]||s.flow.lessonReturn||fallback;}return s.flow.lessonReturn||fallback;}
  function visibleConcepts(s,id=s.flow.node){const order=['medicare','part_a','part_b','original','drugs'],limit={L00:0,L02:1,L03:2,L04:3,L05:4}[id];if(id.startsWith('A')||id==='X01'&&s.flow.pending?.nodeId?.startsWith('A'))return [];return order.filter((c,i)=>s.topics[c]&&(limit===undefined||i<=limit));}
  return {PHASES,FIELDS,create,value,known,apply,propose,phase,visit,nextMissing,startRoute,afterLesson,visibleConcepts};
});
