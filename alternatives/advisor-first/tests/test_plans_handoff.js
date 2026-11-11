'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../web/plans-handoff.js'),'utf8');
function fixture(){
  const events=[],window={dispatchEvent:event=>{events.push(event);return true;}};
  class CustomEvent {constructor(name,options){this.type=name;Object.assign(this,options);}}
  vm.runInNewContext(source,{window,CustomEvent,structuredClone,Date});
  const value={version:'plan-review-20261104-r1',destination:'plans',reportedInfoReviewed:true,
    token:'fictional-receipt',expiresAt:Date.now()/1000+600,profile:{facts:[{value:'fictional'}]}};
  return {api:window.DaylightPlansHandoff,value,events,window};
}
test('reviewed profile reaches registered workspace with no URL or storage',async()=>{
  const f=fixture();let received;
  const unregister=f.api.register(value=>{received=value;return true;});
  assert.equal(await f.api.open(f.value),true);assert.deepEqual(received,f.value);
  received.profile.facts[0].value='changed';assert.equal(f.value.profile.facts[0].value,'fictional');
  unregister();assert.equal(await f.api.open(f.value),false);
  assert.equal(f.events[0].type,'daylight:plans-requested');
});
test('expired or unreviewed handoff cannot open a workspace',async()=>{
  const f=fixture();f.api.register(()=>assert.fail('Must not open'));
  for(const invalid of [{...f.value,expiresAt:0},{...f.value,reportedInfoReviewed:false},{...f.value,version:'other'},null])
    assert.equal(await f.api.open(invalid),false);
});
