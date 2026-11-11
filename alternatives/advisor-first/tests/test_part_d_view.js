'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../web-8894/part-d-plans.js'),'utf8');
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
  const mount=(value=current,visit=options.context)=>{current=value;options.profile=value;options.context=visit;host.replaceChildren();window.DaylightPartD.render(host,options);};
  mount();return {document,host,all,find,mount,calls,tick,ids,conversations,options};
}
const field=(value,basis,money=false)=>({value,basis,state:'published',value_encoding:money?'integer_cents':'literal'});
const rows=Array.from({length:4},(_,i)=>({id:String(i),name:'Fictional Drug Plan '+i,company:'Fictional Company',fields:{total_premium:field(i*100,'Total premium',true),annual_deductible:field(null,'Deductible',true),basic_premium:field(-2150,'Basic premium',true),supplemental_premium:field(2150+i*100,'Supplemental premium',true),has_tier_without_deductible:field('Yes','Tier exception'),drug_benefit_type:field('Basic','Benefit type')},restriction_summary:'Dated check; enrollment not confirmed.',source:{member:'fictional.csv',record_ordinal:i+1}}));
const response=body=>({status:'published_plans',profile:body,notice:'Published terms; personal costs unverified.',plans:rows});
function profile(changes={},held=[]) {
  const inputs={zipcode:'34101',county_fips:'12021',year:2026,...changes};
  const missing=inputs.zipcode?[]:['T03'];const unsupported=inputs.year!==2026;
  return {inputs,held,missing,status:unsupported?'unsupported':missing.length?'missing':'ready',message:unsupported?'Plans for another coverage year are not supported yet.':'',details:[{id:'T03',label:'Home ZIP code',value:inputs.zipcode},{id:'T07',label:'Medicines shared in chat',value:null}]};
}
test('ready shared profile automatically loads all published plans without demographic inputs',async()=>{
  const f=fixture(response);await f.tick();assert.equal(f.calls.length,1);assert.deepEqual(Object.keys(f.calls[0].body).sort(),['county_fips','year','zipcode']);
  assert.equal(f.all().filter(n=>n.dataset.partDId).length,4);assert.match(f.host.textContent,/\$0.00/);assert.match(f.host.textContent,/Not supplied/);
  f.mount();await f.tick();assert.equal(f.calls.length,1);assert.equal(f.all().filter(n=>n.tagName==='form').length,0);
});
test('missing scope invites chat without a duplicate form or price request',async()=>{
  const f=fixture(response,profile({zipcode:null}));assert.equal(f.calls.length,0);assert.equal(f.all().filter(n=>['form','input','select'].includes(n.tagName)).length,0);
  f.find(n=>n.tagName==='button'&&n.textContent==='Talk to Daylight').onclick();assert.deepEqual(f.conversations,[undefined]);
  f.mount(profile());await f.tick();assert.equal(f.calls.length,1);
});
test('chat corrections discard delayed old results and unsupported years clear prices',async()=>{
  const waiting=[];const f=fixture(body=>new Promise(resolve=>waiting.push(()=>resolve(response(body)))));
  f.mount(profile({year:2027}));waiting[0]();await f.tick();assert.equal(f.all().filter(n=>n.dataset.partDId).length,0);assert.equal(f.calls.length,1);
  assert.match(f.host.textContent,/another coverage year/);f.mount(profile({zipcode:'34108'}));waiting[1]();await f.tick();assert.match(f.host.textContent,/ZIP 34108/);
});
test('unknown answers remain open and corrections return to the specific chat question',async()=>{
  const f=fixture(response,profile({zipcode:null},['T03']));assert.match(f.host.textContent,/Details you left unknown/);
  f.find(n=>n.tagName==='button'&&n.textContent==='Edit Home ZIP code in conversation').onclick();assert.deepEqual(f.conversations,['T03']);assert.equal(f.calls.length,0);
});
test('source details preserve negative components and do not assign personal costs',async()=>{
  const f=fixture(response);await f.tick();const b=f.find(n=>n.tagName==='button'&&n.textContent==='See full details');b.onclick({currentTarget:b});
  assert.match(f.document.body.textContent,/-\$21.50/);assert.match(f.document.body.textContent,/not amounts assigned to you/);
});
test('three-plan comparison and removal retain all plans',async()=>{
  const f=fixture(response);await f.tick();for(let i=0;i<4;i++)f.find(n=>n.tagName==='button'&&n.textContent==='Add to compare').onclick();
  assert.match(f.host.textContent,/up to three/);f.find(n=>n.tagName==='button'&&n.textContent==='Compare selected (3)').onclick();assert.equal(f.all().filter(n=>n.tagName==='table').length,1);
  f.find(n=>n.tagName==='button'&&n.textContent==='Remove').onclick();assert.match(f.host.textContent,/Compare selected \(2\)/);
  f.find(n=>n.tagName==='button'&&n.textContent==='All listed plans').onclick();assert.equal(f.all().filter(n=>n.dataset.partDId).length,4);
});
test('failed reads keep profile and retry only deliberately',async()=>{
  let fail=true;const f=fixture(body=>{if(fail)throw Error('Unavailable');return response(body);});await f.tick();f.mount();await f.tick();assert.equal(f.calls.length,1);
  fail=false;f.find(n=>n.tagName==='button'&&n.textContent==='Try Part D plans again').onclick();await f.tick();assert.equal(f.calls.length,2);assert.equal(f.all().filter(n=>n.dataset.partDId).length,4);
});
