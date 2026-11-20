'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../web-8894/medigap-plans.js'),'utf8');
function fixture(request, initial=profile()){
  const ids=new Map();let document;
  class Node {
    constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.dataset={};this.attributes={};this.value='';this.isConnected=true;this.text='';}
    set id(v){this._id=v;ids.set(v,this);}get id(){return this._id;}
    set textContent(v){this.text=String(v);this.children=[];}get textContent(){return this.text+this.children.map(x=>x.textContent??x).join('');}
    append(...nodes){this.children.push(...nodes);for(const n of nodes)if(typeof n==='object')n.parent=this;}
    replaceChildren(...nodes){const remove=n=>{if(n.id)ids.delete(n.id);for(const c of n.children||[])remove(c);};for(const n of this.children)remove(n);this.children=[];this.append(...nodes);}
    setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,v){this.listeners[k]=v;}
    focus(){document.activeElement=this;}showModal(){this.open=true;}close(){this.open=false;this.listeners.close?.();}
    remove(){this.isConnected=false;this.parent.children=this.parent.children.filter(x=>x!==this);}
  }
  document={createElement:tag=>new Node(tag),getElementById:id=>ids.get(id),body:new Node('body')};
  class Option extends Node {constructor(label,value){super('option');this.textContent=label;this.value=value;}}
  const window={};vm.runInNewContext(source,{window,document,Option,Intl,Number,Set,Object,Array,Infinity,Error,String});
  const host=new Node('main');document.body.append(host);const calls=[];
  let current=initial;const conversations=[];
  const options={context:'fictional-visit',profile:current,request:async(url,body)=>{calls.push({url,body});return request(body);},
    conversation:id=>conversations.push(id)};
  const all=(node=host)=>[node,...node.children.filter(x=>typeof x==='object').flatMap(all)];
  const find=predicate=>all().find(predicate);
  const tick=()=>new Promise(resolve=>setImmediate(resolve));
  const mount=(value=current,visit=options.context)=>{current=value;options.profile=value;options.context=visit;host.replaceChildren();window.DaylightMedigap.render(host,options);};
  mount();return {document,host,all,find,mount,calls,tick,ids,conversations,options};
}
const rows=Array.from({length:4},(_,i)=>({id:String(i),company:'Fictional Company '+i,variant:'G',rating_class:i?'Household':'Standard',monthly_cents:12345+i,annual_cents:null,monthly_with_discounts_cents:11728,annual_with_discounts_cents:140000,policy_fee:'$20 fixed',household_discount:'5%',source_fields:{'AM Best Rating':'Stable'},rating_labels_need_review:true}));
const response=body=>({status:'matched_source_prices',profile:{zip:body.zipcode,age:body.age,gender:body.gender,tobacco:body.tobacco},notice:'Listed premiums; qualifications unknown.',plans:rows});
function profile(changes={},held=[]) {
  const inputs={zipcode:'34101',age:68,gender:'Female',tobacco:'Non-Tobacco',...changes};
  const keys={MG_AGE:'age',MG_SEX:'gender',MG_TOBACCO:'tobacco'};
  const details=Object.entries(keys).map(([id,key])=>({id,label:key,value:inputs[key],status:held.includes(id)?'unknown':'reported'}));
  const missing=Object.entries(keys).filter(([id,key])=>inputs[key]==null).map(([id])=>id);
  if(!inputs.zipcode)missing.unshift('T03');
  const unsupported=inputs.age>=75;
  return {inputs,held,details,missing,questions:[],status:unsupported?'unsupported':missing.length?'missing':'ready',message:unsupported?'Medigap pricing for ages 75+ is not supported in this pilot.':''};
}
test('chat answers automatically fetch exact prices; rerenders do not refetch',async()=>{
  const f=fixture(response);await f.tick();assert.equal(f.calls.length,1);assert.equal(f.calls[0].body.age,68);assert.equal(f.calls[0].body.effective_date,'2026-11-10');
  assert.equal(f.all().filter(n=>n.dataset.medigapId).length,4);assert.match(f.host.textContent,/\$123\.45/);assert.match(f.host.textContent,/Not supplied/);assert.match(f.host.textContent,/Standard/);assert.match(f.host.textContent,/Household/);
  assert.equal(f.all().filter(n=>n.tagName==='form').length,0);f.mount();await f.tick();assert.equal(f.calls.length,1);
});
test('missing profile invites conversation without a second intake or price request',async()=>{
  const f=fixture(response,profile({tobacco:null}));assert.equal(f.calls.length,0);
  assert.equal(f.all().filter(n=>['form','input','select'].includes(n.tagName)).length,0);
  // D157 (CN-10): never a generic panel; the button opens the exact missing question.
  assert.match(f.host.textContent,/1 detail left to see your Medigap prices/);assert.doesNotMatch(f.host.textContent,/Talk to Daylight|Pilot coverage/);
  f.find(n=>n.tagName==='button'&&n.textContent==='Continue in the conversation').onclick();
  assert.deepEqual(f.conversations,['MG_TOBACCO']);assert.equal(f.calls.length,0);
  f.mount(profile({tobacco:'Tobacco User'}));await f.tick();
  assert.equal(f.calls.length,1);assert.equal(f.calls[0].body.age,68);assert.equal(f.calls[0].body.tobacco,'Tobacco User');
  assert.equal(f.find(n=>n.textContent==='Talk to Daylight'),undefined);
});
test('delayed old prices are discarded after a chat correction',async()=>{
  const waits=[];const f=fixture(body=>new Promise(resolve=>waits.push(()=>resolve(response(body)))));
  f.mount(profile({age:69}));assert.equal(f.calls.length,2);waits[0]();await f.tick();assert.equal(f.all().filter(n=>n.dataset.medigapId).length,0);
  waits[1]();await f.tick();assert.match(f.host.textContent,/Age 69/);assert.equal(f.all().filter(n=>n.dataset.medigapId).length,4);
});
test('75+ removes rates without asking sex or tobacco; corrected age reloads automatically',async()=>{
  const f=fixture(response);await f.tick();f.mount(profile({age:75,gender:null,tobacco:null}));await f.tick();
  assert.match(f.host.textContent,/75\+ is not supported in this pilot/);assert.equal(f.calls.length,1);assert.equal(f.all().filter(n=>n.tagName==='form').length,0);assert.equal(f.all().filter(n=>n.dataset.medigapId).length,0);
  f.mount(profile({age:74}));await f.tick();assert.equal(f.calls.length,2);assert.equal(f.calls[1].body.age,74);
});
test('unknown stays open and deliberate editing routes to its chat question',async()=>{
  const f=fixture(response,profile({tobacco:null},['MG_TOBACCO']));await f.tick();
  assert.equal(f.calls.length,0);assert.equal(f.all().filter(n=>['form','input','select'].includes(n.tagName)).length,0);
  // D157 (CN-12): one pricing line with a single Edit that opens each detail.
  assert.equal(f.all().filter(n=>n.tagName==='button'&&n.textContent==='Edit').length,1);
  f.find(n=>n.tagName==='button'&&n.textContent==='Tobacco').onclick();
  assert.deepEqual(f.conversations,['MG_TOBACCO']);assert.equal(f.calls.length,0);
});
test('failed lookup keeps shared answers and retries only deliberately',async()=>{
  let fail=true;const f=fixture(body=>{if(fail)throw Error('Temporarily unavailable. Try again.');return response(body);});await f.tick();
  assert.match(f.host.textContent,/Temporarily unavailable/);f.mount();await f.tick();assert.equal(f.calls.length,1);
  fail=false;f.find(n=>n.textContent==='Try prices again'&&n.tagName==='button').onclick();await f.tick();assert.equal(f.calls.length,2);assert.equal(f.all().filter(n=>n.dataset.medigapId).length,4);
});
test('compare three source rates, remove and return to the full list',async()=>{
  const f=fixture(response);await f.tick();
  for(let i=0;i<4;i++)f.find(n=>n.tagName==='button'&&n.textContent==='Add to compare').onclick();
  assert.match(f.host.textContent,/up to three/);f.find(n=>n.tagName==='button'&&n.textContent==='Compare selected (3)').onclick();assert.equal(f.all().filter(n=>n.tagName==='table').length,1);assert.match(f.host.textContent,/\$1,400\.00/);
  f.find(n=>n.tagName==='button'&&n.textContent==='Remove').onclick();assert.match(f.host.textContent,/Compare selected \(2\)/);
  f.find(n=>n.tagName==='button'&&n.textContent==='All listed rates').onclick();assert.equal(f.all().filter(n=>n.dataset.medigapId).length,4);
});
