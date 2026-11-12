/* D49–D61: deterministic master policy. No model can mutate this state directly. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.GuidePolicy=api;})(typeof globalThis==='object'?globalThis:this,function(){
'use strict';
const PHASES=['Your goal','Your situation','Your options','Your next step'];
const TOPIC={L00:'basics',L02:'parta',L03:'partb',L04:'original',L05:'drugbasics',L06:'extras',L07:'costs',L08:'costs',L09:'medical_limit',L10:'routesintro',L11:'options',L12:'medigap',L13:'switching'};
const LABEL={L00:'Medicare',L02:'Part A',L03:'Part B',L04:'Original Medicare',L05:'Part D',L06:'Other benefits',L07:'Monthly premium',L08:'Costs when getting care',L09:'Medical spending limits',L10:'Medicare Advantage',L11:'Coverage routes',L12:'Medigap',L13:'Switching rights'};
const BASIC={A01:'intent.goal',A02:'subject.role',A02B:'subject.displayLabel',A03:'knowledge.general',A05:'privacy.persistenceChoice'};
const SENSITIVE=new Set(['subject.displayLabel','coverage.birth','coverage.birth.firstDay','needs.medications','needs.pharmacies','needs.providers','outcome.drafts','comparison.requestedNames']);
function make(contract){const nodes=Object.fromEntries(contract.nodes.map(n=>[n.id,n]));const fields=new Set(contract.nodes.flatMap(n=>n.writes).concat(['intent.goal','knowledge.general','privacy.persistenceChoice','subject.role','subject.displayLabel','intent.timingQuestion']));
const create=()=>({schemaVersion:2,stateVersion:0,fields:{},flow:{node:'A01',history:[],queue:[],lessonReturn:null,personalReview:false,guideOpen:true,origin:'A01',invalidations:[],scroll:0},topics:{},preferences:{saveGuide:false,saveSensitive:false,noticeVersion:'guest-notice-2026-10-21-v1'}});
const val=(s,k)=>s.fields[k]?.value;const known=(s,k)=>!!s.fields[k]&&s.fields[k].status!=='stale';
function record(s,k,v,status='reported',raw='',source='user_choice'){
 const enums={'intent.goal':['learn','compare','review','job','unresolved'],'knowledge.general':['new','some','comfortable','unknown'],'subject.role':['self','someone','other'],'coverage.enrollment':['ab','a','b_only','parts_unknown','no','unknown'],'intent.timingQuestion':['age65','supplement_window','part_b_start','unknown']};if(enums[k]&&!enums[k].includes(v))throw Error('Choose a supported answer or keep it unknown.');
 if(!fields.has(k)||!['reported','unknown','skipped','stale','derived'].includes(status))throw Error('Unsupported guide detail.');
 if(k==='subject.role'&&known(s,k)&&val(s,k)!==v&&Object.keys(s.fields).some(x=>x.startsWith('coverage.')||x.startsWith('needs.')))throw Error('A different person needs a separate guide. Start a new guide to keep the people separate.');
 if(status==='derived'&&!['comparison.scope.county','comparison.scope.locationEvidence'].includes(k))throw Error('Only the published location reference can derive location.');
 const before=val(s,k);s.stateVersion++;s.fields[k]={value:v,status,confirmation:'confirmed_by_user',rawText:String(raw).slice(0,1200),source,revision:s.stateVersion,confirmedAt:new Date().toISOString()};
 if(JSON.stringify(before)!==JSON.stringify(v)&&['intent.goal','subject.role','intent.compareKind','intent.comparisonMode','comparison.scope.zip','comparison.scope.county','comparison.scope.year','coverage.enrollment','coverage.current','needs.medications','needs.providers','needs.priorities','coverage.job.employmentEnd','coverage.job.coverageEnd'].includes(k)){s.flow.invalidations.push(k);for(const x of ['comparison.snapshot','comparison.viewedSnapshot','outcome.status'])if(s.fields[x])s.fields[x].status='stale';}
}
function atomic(s,patches,expected,raw='',source='confirmed_agent_interpretation'){if(expected!==s.stateVersion)throw Error('Your guide changed. Review the interpretation again.');const copy=JSON.parse(JSON.stringify(s));for(const p of patches)record(copy,p.field,p.value,p.status||'reported',raw,source);Object.assign(s,copy);}
function restoreFields(s,previous){const consent=s.fields['privacy.persistenceChoice'];s.fields=JSON.parse(JSON.stringify(previous));if(consent)s.fields['privacy.persistenceChoice']=consent;s.stateVersion++;for(const k of ['comparison.snapshot','comparison.viewedSnapshot','outcome.status'])if(s.fields[k])s.fields[k].status='stale';s.flow.invalidations.push('answer_undo');}
function canonical(id,s){const aliases={A04:'A03',A02B:'A02',O01:'O00',O04:'O03',O04B:'O03',O05:'O03',C04:'C03',J01:'J00',J04:'J03',L00:'L01',L02:'E01',L03:'E01',L04:'E01',L05:'E02',L06:'E04',L07:'E04',L08:'E04',L09:'E04',L10:'E03',L11:'E03',L12:'O11',L13:'O11'};return aliases[id]||id;}
function introduce(s,ids){for(const id of ids)s.topics[id]||={seenAt:new Date().toISOString(),selfReport:'unknown'};}
function visit(s,id,push=true,scroll=0){id=canonical(id,s);if(!nodes[id])throw Error('Unknown guide step.');if(push)s.flow.history.push(frame(s,scroll));if(s.flow.history.length>100)s.flow.history.shift();s.flow.node=id;s.flow.queue=[];s.flow.lessonReturn=null;
 if(id==='A03')introduce(s,['L00']);
 if(['C00','C03','O00','E01','E02','E03','O11'].includes(id))introduce(s,['L00','L02','L03','L04']);
 if(id==='N00'||id==='E02')introduce(s,['L05']);
 if(id==='E03')introduce(s,['L05','L10','L11','L12']);if(id==='O11')introduce(s,['L12']);}

function back(s){const f=s.flow.history.pop();if(!f)return null;s.flow.node=canonical(f.node,s);s.flow.queue=[];s.flow.lessonReturn=null;s.flow.personalReview=!!f.personalReview;return f;}
function lessons(s,ids,ret){s.flow.queue=[...ids];s.flow.lessonReturn=ret;return ids[0];}
function novice(s){return val(s,'knowledge.general')!=='comfortable';}
function partsNeeded(s){return novice(s)&&!s.topics.L04;}
function personal(s){s.flow.personalReview=true;if(!known(s,'subject.role'))return 'A02';return known(s,'coverage.enrollment')?resolve(s,'@after_enrollment'):'C00';}
function start(s){const g=val(s,'intent.goal');if(s.flow.personalReview)return personal(s);return g==='learn'||g==='unresolved'?'L01':g==='compare'?'O00':personal(s);}
function missing(s){if(!known(s,'intent.goal'))return 'A01';if(!known(s,'subject.role'))return 'A02';if(!known(s,'knowledge.general'))return 'A03';return start(s);}
function resolve(s,target){const g=val(s,'intent.goal'),goalLearn=g==='learn'&&!s.flow.personalReview,pr=val(s,'needs.priorities')||[];switch(target){
case '@after_knowledge':return !known(s,'subject.role')?'A02':start(s);
case '@start_route':return start(s);case '@personal_entry':return personal(s);
case '@after_parts':return goalLearn?'L05':'C00';case '@after_drug_lesson':return goalLearn?'L06':'N00';case '@after_extras_lesson':return goalLearn?'L07':'N03';case '@after_cost_lesson':return goalLearn?'L10':'O00';case '@after_routes_lesson':return goalLearn?'L01':'O00';case '@after_supplement_lesson':return 'O11';
case '@after_enrollment':return g==='job'?'J00':['ab','parts_unknown','b_only'].includes(val(s,'coverage.enrollment'))?'C03':'J00';
case '@after_current':return g==='job'?'J00':g==='review'?resolve(s,'@after_change'):'N00';case '@after_change':return val(s,'intent.change')==='keep'?'F00':['add','replace'].includes(val(s,'intent.change'))?'O00':'N00';
case '@after_job':return g==='job'?'J03':val(s,'intent.timingQuestion')==='age65'?'C05':'N00';case '@after_timing':return ['supplement_window','part_b_start'].includes(val(s,'intent.timingQuestion'))?'C07':'N00';case '@after_part_b':return val(s,'intent.compareKind')==='medigap'?'O11':'N00';
case '@after_transition':return val(s,'intent.jobTask')==='compare'?'N00':'F00';case '@after_medicines':return 'N03';case '@after_priorities':return pr.length>1?'N05':resolve(s,'@after_priority_order');case '@after_priority_order':return pr.some(x=>['doctors','travel'].includes(x))?'N06':'O00';case '@after_providers':return 'O00';
case '@after_lesson':{const at=s.flow.queue.indexOf(s.flow.node);if(at>=0)return s.flow.queue[at+1]||s.flow.lessonReturn||resolve(s,contract.lesson_defaults[s.flow.node]);return resolve(s,contract.lesson_defaults[s.flow.node]||'L01');}
case '@confirmed_return':case '@confirmed_dispatch':case '@unknown_return':return missing(s);case '@origin':return s.flow.origin||'A01';case '@safe_local':return s.flow.origin||'L00';case '@resume':return s.flow.node;case '@lesson_return':return s.flow.lessonReturn||'L01';default:if(nodes[target])return target;return 'F00';}}
function frame(s,scroll=0){return {node:s.flow.node,scroll,queue:[...s.flow.queue],lessonReturn:s.flow.lessonReturn,personalReview:s.flow.personalReview};}
function prepare(s,id){return canonical(id,s);}
function nextTask(s,id){const skipped=[];for(let count=0;count<30;count++){id=canonical(id,s);const n=nodes[id],field=fieldFor(id),entry=s.fields[field];if(!n||!entry||entry.status==='stale'||['O00','O03','L01','E01','E02','E03','E04'].includes(id))return {node:id,skipped};let next;
 if(id==='C03'){if(val(s,'intent.goal')==='review'&&!known(s,'intent.change'))return {node:id,skipped};next=resolve(s,'@after_current');}
 else if(id==='J00'){if(['active','ended'].includes(entry.value)&&!known(s,'intent.jobTask'))return {node:id,skipped};next=['active','ended'].includes(entry.value)?'J02':resolve(s,'@after_job');}
 else if(id==='J03'){if(!known(s,nodes.J04.writes[0]))return {node:id,skipped};next='J05';}
 else {if(!['single_choice','multi_choice','optional_dates','optional_choice','sensitive_list','free_text','location','scope'].includes(n.kind))return {node:id,skipped};let option=n.kind==='multi_choice'?n.options.find(o=>o.id==='continue'):n.options.find(o=>o.id===entry.value)||n.options.find(o=>o.id===(entry.status==='skipped'?'skip':entry.status==='unknown'?'unknown':n.kind==='optional_dates'?'date':['sensitive_list','free_text'].includes(n.kind)?'save':''));if(!option)return {node:id,skipped};next=resolve(s,option.next);}
 if(next===id)return {node:id,skipped};skipped.push(id);id=next;}return {node:id,skipped};}

function fieldFor(id){return BASIC[id]||nodes[id]?.writes?.[0];}
function answer(s,id,option,value,raw=''){const n=nodes[id];if(!n)throw Error('Unknown question.');const o=n.options.find(x=>x.id===option);if(!o)throw Error('Choose a listed answer.');
 if(option==='other'){s.flow.origin=id;return 'X01';}
 if(id==='A03'&&option==='text')return 'A04';
 if(id==='L01'&&option==='personal')return personal(s);
 if(id==='O01'&&option==='personal')return personal(s);
 if(id==='F00'&&option==='options')return 'O00';
 if(id==='O05'){record(s,'comparison.scope.year',option==='supported'?'2027':'unknown',option==='supported'?'reported':'unknown');return resolve(s,o.next);}
 if(id==='L01'||id.startsWith('E'))return resolve(s,o.next);
 if(TOPIC[id]){if(option==='know'){introduce(s,[id]);s.topics[id].selfReport='familiar';}return resolve(s,'@after_lesson');}
 if(['A01','A02','A02B','A03','A04','A05'].includes(id)){
  const field=fieldFor(id);let v=value===undefined?option:value;const status=['unknown','skip'].includes(option)?(option==='skip'?'skipped':'unknown'):'reported';if(id==='A03'&&option==='skip')v='unknown';if(id==='A02B'&&option==='skip')v='';if(id==='A04'&&option==='skip'){record(s,'knowledge.general','unknown','skipped');return resolve(s,'@after_knowledge');}if(field)record(s,field,v,status,raw);if(id==='A03')s.flow.guideOpen=v!=='comfortable';if(id==='A01'||id==='A02'||id==='A02B')return missing(s);return resolve(s,o.next);
 }
 if(n.kind==='single_choice'||n.kind==='multi_choice'||['optional_dates','optional_choice','sensitive_list','free_text','location','scope'].includes(n.kind)){
  const field=fieldFor(id);if(field&&!['continue','other'].includes(option)||field&&value!==undefined)record(s,field,value===undefined?option:value,(option==='unknown'||Array.isArray(value)&&value.includes('unknown'))?'unknown':option==='skip'?'skipped':'reported',raw);
 }
 return resolve(s,o.next);
}
function group(s,id,values){const copy=JSON.parse(JSON.stringify(s)),put=(k,v,status='reported',source='user_choice')=>record(copy,k,v,status,'',source);let next;
 if(id==='A02'){put('subject.role',values.role);if(values.role==='someone'&&values.label?.trim())put('subject.displayLabel',values.label.trim());next=missing(copy);}
 else if(id==='O00'){put('intent.compareKind',values.kind);if(values.kind==='difference'){next='E03';}else {if(!['browse','personal','unknown'].includes(values.mode))throw Error('Choose how you want to explore.');put('intent.comparisonMode',values.mode,values.mode==='unknown'?'unknown':'reported');next=values.kind==='named'?'O02':values.kind==='medigap'?'O11':values.mode==='personal'?personal(copy):'O03';}}
 else if(id==='C03'){put('coverage.current',values.coverage,values.coverage.includes('unknown')?'unknown':'reported');if(val(copy,'intent.goal')==='review'){if(!values.change)throw Error('Choose what you want to do with this coverage.');put('intent.change',values.change,values.change==='unknown'?'unknown':'reported');}next=resolve(copy,'@after_current');}
 else if(id==='J00'){put('coverage.job.status',values.status,values.status==='unknown'?'unknown':'reported');if(['active','ended'].includes(values.status)){if(!values.task)throw Error('Choose what would help with this coverage.');put('intent.jobTask',values.task,values.task==='unknown'?'unknown':'reported');next='J02';}else next=resolve(copy,'@after_job');}
 else if(id==='J03'){for(const node of ['J03','J04']){const v=values[node];if(!v)throw Error('Enter each date or mark it unknown/continuing.');if(!['unknown','ongoing'].includes(v)&&!/^\d{4}-(0[1-9]|1[0-2])$/.test(v))throw Error('Use a month and year or an explicit unknown.');put(nodes[node].writes[0],v,v==='unknown'?'unknown':'reported');}next='J05';}
 else if(id==='O03'){if(!['2027','unknown','other'].includes(values.year)&&!/^\d{4}$/.test(values.year))throw Error('Choose a coverage year.');put('comparison.scope.year',values.year,/^\d{4}$/.test(values.year)?'reported':'unknown');put('comparison.scope.zip',values.zip||'unknown',values.zip?'reported':'unknown');if(values.county){put('comparison.scope.county',values.county,values.derived?'derived':'reported',values.derived?'location_reference':'user_choice');put('comparison.scope.locationEvidence',values.evidence,values.derived?'derived':'reported',values.derived?'location_reference':'user_choice');}else {put('comparison.scope.county','unknown','unknown');put('comparison.scope.locationEvidence','unknown','unknown');}next=values.year!=='2027'?'X04':'O06';}
 else throw Error('Unknown grouped task.');Object.assign(s,copy);return next;}
function phase(s){const n=nodes[s.flow.node];return n?.phase==='preserve'?(nodes[s.flow.origin]?.phase||'P1'):n?.phase||'P1';}
function picture(s){if(['A01','A02'].includes(s.flow.node))return [];if(s.flow.node==='A03')return ['L00'];return ['L00','L02','L03','L04','L05','L10','L11','L12'].filter(id=>s.topics[id]);}
function eligible(s){const set=new Set([s.flow.node,'L01','F00']);for(const n of contract.nodes)if(n.id===missing(JSON.parse(JSON.stringify(s))))set.add(n.id);if(known(s,'intent.goal'))set.add('O00');if(val(s,'intent.goal')==='learn')for(const id of ['E01','E02','E03','E04'])set.add(id);if(val(s,'intent.goal')!=='learn'||s.flow.personalReview)set.add('C00');return [...set].slice(0,12);}
function hydrate(value){if(value?.schemaVersion!==2||!nodes[value.flow?.node]||!value.fields||typeof value.fields!=='object')throw Error('This saved guide needs a supported version. Start a private visit or keep it for review.');const s=JSON.parse(JSON.stringify(value));s.flow.node=canonical(s.flow.node,s);s.flow.history=s.flow.history||[];s.flow.queue=s.flow.queue||[];s.flow.invalidations=s.flow.invalidations||[];s.preferences=s.preferences||{saveGuide:false,saveSensitive:false};if(s.preferences.noticeVersion!=='guest-notice-2026-10-21-v1'){s.preferences.saveGuide=false;s.preferences.noticeVersion='guest-notice-2026-10-21-v1';if(s.fields['privacy.persistenceChoice'])s.fields['privacy.persistenceChoice'].status='stale';s.flow.node='A05';}return s;}
return {nodes,create,val,known,record,atomic,visit,back,lessons,missing,resolve,answer,fieldFor,phase,picture,eligible,hydrate,frame,prepare,restoreFields,nextTask,group,canonical,introduce};}
return {make,PHASES,TOPIC,LABEL,SENSITIVE};});
