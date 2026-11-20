const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../pilot-web/join.js'), 'utf8');
const token = 'a'.repeat(32) + '.2000000000.' + 'b'.repeat(64);
const tick = () => new Promise(resolve => setImmediate(resolve));
function app({hash=false, active={}, access, redeem}={}) {
  const nodes = {};
  for (const id of ['[role="status"]','#continue-invitation','#save-history','#invitation-entry','#invitation-link']) {
    nodes[id] = {checked:false, disabled:false, hidden:false, events:{}, addEventListener(name,fn) { this.events[name]=fn; }};
  }
  const store = new Map([['daylight-visit-reference-v1','old-visit']]);
  const timers = new Map(); let timerId=0, nonce=0;
  const requests=[], navigations=[], replacements=[];
  const location={origin:'https://daylight.example',href:'https://daylight.example/'+(hash?'pilot/join#':'pilot/invite/')+token,assign:url=>navigations.push(url)};
  const context={URL,AbortController,location,history:{replaceState:(...args)=>replacements.push(args)},
    document:{querySelector:id=>nodes[id]},crypto:{randomUUID:()=>('c'.repeat(30)+(++nonce).toString().padStart(2,'0'))},
    sessionStorage:{getItem:key=>store.get(key)||null,setItem:(key,value)=>store.set(key,value),removeItem:key=>store.delete(key)},
    setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id),
    fetch:async (url,options)=>{
      if(url==='/pilot/access')return access ? access() : {ok:true,status:200,json:async()=>({active:false,savedHistory:false,ownerReentry:false,...active})};
      requests.push(JSON.parse(options.body));
      return redeem ? redeem(options,requests.length) : {ok:true,status:200,json:async()=>({joined:true,newVisit:true})};
    }};
  vm.runInNewContext(code,context);
  return {nodes,store,timers,requests,navigations,replacements};
}

test('legacy fragment remains intact and retry reuses nonce after lost response',async()=>{
  const page=app({hash:true,redeem:async (_options,count)=>{if(count===1)throw new Error('Disconnected');return {ok:true,status:200,json:async()=>({joined:true,newVisit:true})};}});
  await tick();assert.equal(page.replacements.length,0);
  await page.nodes['#continue-invitation'].events.click();
  assert.equal(page.nodes['#continue-invitation'].disabled,false);
  await page.nodes['#continue-invitation'].events.click();
  assert.equal(page.requests[0].requestId,page.requests[1].requestId);
  assert.deepEqual(page.navigations,['/']);assert.equal(page.store.has('daylight-visit-reference-v1'),false);
});

test('timeout includes a stalled JSON response body and releases Continue',async()=>{
  const page=app({redeem:async options=>({ok:true,status:200,json:()=>new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('timeout'),{name:'AbortError'}))))})});
  await tick();const click=page.nodes['#continue-invitation'].events.click();await tick();
  for(const fn of page.timers.values())fn();await click;
  assert.equal(page.nodes['#continue-invitation'].disabled,false);
  assert.match(page.nodes['[role="status"]'].textContent,/same visit/);
});

test('different parent invitation never inherits prior saved-chat consent',async()=>{
  const page=app({active:{active:true,savedHistory:true,invitationId:'d'.repeat(32)}});
  await tick();assert.equal(page.nodes['#save-history'].checked,false);assert.equal(page.nodes['#save-history'].disabled,false);
  await page.nodes['#continue-invitation'].events.click();assert.equal(page.requests[0].historyConsent,undefined);
});

test('same-parent continuation preserves existing visit recovery reference',async()=>{
  const page=app({active:{active:true,savedHistory:true,invitationId:'a'.repeat(32)},redeem:async()=>({ok:true,status:200,json:async()=>({joined:true,newVisit:false})})});
  await tick();assert.equal(page.nodes['#save-history'].checked,true);
  await page.nodes['#continue-invitation'].events.click();assert.equal(page.store.get('daylight-visit-reference-v1'),'old-visit');
});

test('initial session probe cannot change consent during an interrupted redemption',async()=>{
  let resolveAccess;
  const page=app({access:()=>new Promise(resolve=>{resolveAccess=resolve;}),
    redeem:async(_options,count)=>{if(count===1)throw new Error('Disconnected');return {ok:true,status:200,json:async()=>({joined:true,newVisit:false})};}});
  assert.equal(page.nodes['#continue-invitation'].disabled,true);
  await page.nodes['#continue-invitation'].events.click();assert.equal(page.requests.length,0);
  resolveAccess({ok:true,status:200,json:async()=>({active:true,savedHistory:true,invitationId:'a'.repeat(32)})});await tick();
  await page.nodes['#continue-invitation'].events.click();
  await page.nodes['#continue-invitation'].events.click();
  assert.equal(page.requests.length,2);assert.equal(page.requests[0].requestId,page.requests[1].requestId);
  assert.equal(page.requests[0].historyConsent,page.requests[1].historyConsent);assert.deepEqual(page.navigations,['/']);
});
