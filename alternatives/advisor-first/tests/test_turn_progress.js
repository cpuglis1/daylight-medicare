const assert = require('node:assert/strict');
const {test} = require('node:test');
const {view,start} = require('../web-8894/turn-progress.js');
test('copy changes only after actual receipts; slow thresholds are not invented stages',()=>{
  assert.equal(view(null,35000,false).text,'Sending your message…');
  assert.equal(view(null,35000,true).text,'Waiting for an update…');
  assert.equal(view({state:'working',stage:'doctors'},8000,true).more,'');
  assert.match(view({state:'working',stage:'doctors'},18000,true).more,/No need/);
  assert.match(view({state:'working',stage:'doctors'},35000,true).more,/longer than usual/);
  assert.equal(view({state:'working',stage:'draft text'},35000,true).stage,'waiting');
  assert.equal(view({state:'complete'},35000,true).more,'');
});
function harness(read){
  let clock=0,id=0;const tasks=new Map(),seen=[];
  const control=start({read,render:v=>seen.push(v),now:()=>clock,
    schedule:(f,ms)=>{tasks.set(++id,{f,ms});return id;},cancel:i=>tasks.delete(i)});
  return {control,seen,tasks,async poll(ms=1000){clock+=ms;const job=[...tasks].find(([,t])=>t.ms!==4000);assert.ok(job);tasks.delete(job[0]);await job[1].f();}};
}
test('one in-flight read, stage announcements deduplicated, polls stop on receipt',async()=>{
  let reads=0;const h=harness(async()=>++reads<3?{state:'working',stage:'composing'}:{state:'complete'});
  await h.poll();await h.poll();assert.equal(h.seen.length,2);
  await h.poll();assert.equal(h.tasks.size,0);assert.equal(reads,3);
});
test('stop aborts poll and ignores stale result',async()=>{
  let resolve,signal;const h=harness(s=>{signal=s;return new Promise(r=>resolve=r);});
  const pending=h.poll();h.control.stop();assert.equal(signal.aborted,true);
  resolve({state:'working',stage:'doctors'});await pending;
  assert.equal(h.seen.length,1);assert.equal(h.tasks.size,0);
});
test('poll failure is passive and recovery owns status',async()=>{
  let fail=false;const h=harness(async()=>{if(fail)throw Error('offline');return {state:'working',stage:'doctors'};});
  await h.poll();fail=true;await h.poll(35000);
  assert.equal(h.seen.at(-1).stage,'waiting');assert.equal(h.seen.at(-1).more,'');
  h.control.reconnecting();assert.equal(h.seen.at(-1).stage,'reconnecting');assert.equal(h.tasks.size,0);
});
