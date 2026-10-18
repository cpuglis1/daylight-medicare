import test from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from '../src/server.mjs';
test('HTTP boundary isolates cases and blocks cross-origin, missing-CSRF and unavailable live calls',async()=>{
 const server=createServer({liveEnabled:false,keyPresent:false});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base=`http://127.0.0.1:${server.address().port}`;
 try{
  const a=await fetch(base+'/api/state');const cookie=a.headers.get('set-cookie').split(';')[0],state=await a.json();assert.equal(state.live_available,false);assert(!('api_key' in state));
  const headers={'Content-Type':'application/json',Cookie:cookie,'x-csrf-token':state.csrf};
  assert.equal((await fetch(base+'/api/profile',{method:'POST',headers:{'Content-Type':'application/json',Cookie:cookie},body:'{}'})).status,403);
  assert.equal((await fetch(base+'/api/profile',{method:'POST',headers:{...headers,Origin:'https://other.example'},body:'{}'})).status,403);
  assert.equal((await fetch(base+'/api/chat',{method:'POST',headers,body:JSON.stringify({mode:'openai',message:'Hi'})})).status,412);
  assert.equal((await fetch(base+'/api/case',{method:'POST',headers,body:JSON.stringify({case_id:'doctor'})})).status,200);
  const a2=await (await fetch(base+'/api/state',{headers:{Cookie:cookie}})).json();assert.equal(a2.case_id,'doctor');
  const b=await (await fetch(base+'/api/state')).json();assert.equal(b.case_id,'ready');
  const reply=await (await fetch(base+'/api/chat',{method:'POST',headers,body:JSON.stringify({mode:'replay',message:'Compare my options'})})).json();assert.equal(reply.answer.recommendation_status,'provisional');assert.equal(reply.profile_version,a2.profile_version);
  assert.equal((await fetch(base+'/src/agent.mjs')).status,404);
 }finally{await new Promise(resolve=>server.close(resolve));}
});
