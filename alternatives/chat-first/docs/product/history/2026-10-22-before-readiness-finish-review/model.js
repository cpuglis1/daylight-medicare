/* Synthetic interaction model only. No eligibility, source-admission or ranking policy. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ReadinessDemo=api;})(typeof globalThis!=='undefined'?globalThis:this,()=>{
 const scenarios={ordinary:{label:'Job-coverage transition',queue:['RC09','RC11','RC12']},complete:{label:'All relevant facts already confirmed',queue:[]},unknown:{label:'Missing baseline facts / defer',queue:['RC02','RC03','RC04']},conflict:{label:'Conflicting current coverage',queue:['RC28']},needs:{label:'Doctor and prescription details',queue:['RC21','RC22','RC23']},source:{label:'Sources unavailable / stale',queue:[]}};
 function create(ids=[],deps={},limit=6){return {queue:[...new Set(ids)],deps,index:0,limit,seen:[],answers:{},drafts:{},mode:'entry',edited:false};}
 function show(s){while(s.index<s.queue.length){const id=s.queue[s.index];if((s.deps[id]||[]).some(d=>s.answers[d]&&['explicit_unknown','deferred','blocked_dependency'].includes(s.answers[d].state))){s.answers[id]={state:'blocked_dependency'};s.index++;continue;}if(!s.seen.includes(id)){if(s.seen.length>=s.limit){s.mode='summary';return;}s.seen.push(id);}s.mode='question';return;}s.mode='summary';}
 function start(s){s.index=0;show(s);return s;}
 function answer(s,value,state='resolved_report'){if(s.mode!=='question')throw Error('No current detail.');const id=s.queue[s.index];s.answers[id]={value,state};s.index++;show(s);return s;}
 function back(s){if(s.mode!=='question')throw Error('Back requires a detail.');if(s.index===0){s.mode='entry';return s;}s.index--;s.mode='question';return s;}
 function finish(s){s.mode='summary';return s;}
 function pending(s){return s.queue.filter(id=>!s.answers[id]||s.answers[id].state!=='resolved_report');}
 function current(s){return s.queue[s.index];}
 return {scenarios,create,start,answer,back,finish,pending,current};
});
