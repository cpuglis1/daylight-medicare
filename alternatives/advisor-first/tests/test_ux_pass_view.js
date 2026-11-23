'use strict';
/* D157: the Medigap page is plans first: one pricing line, the person's own
   window line, filters, then the list. Fictional rates; no network. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../web-8894/medigap-plans.js'),'utf8');
function fixture(plans, age=65, windowLine=null, port=''){
  const ids=new Map();let document;
  class Node {
    constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.dataset={};this.attributes={};this.value='';this.isConnected=true;this.text='';this.hidden=false;}
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
  const window={location:{port}};vm.runInNewContext(source,{window,document,Option,Intl,Number,Set,Map,Promise,JSON,Object,Array,Infinity,Error,String,Math});
  const host=new Node('main');document.body.append(host);const conversations=[];
  const details=[['MG_AGE','Age for Medigap pricing',age,'derived'],['MG_SEX','Sex used for Medigap pricing','Male','reported'],['MG_TOBACCO','Medigap tobacco category','Non-Tobacco','reported']]
    .map(([id,label,value,status])=>({id,label,value,status}));
  const profile={inputs:{zipcode:'34102',age,gender:'Male',tobacco:'Non-Tobacco'},held:[],details,missing:[],questions:[],status:'ready',message:'',note:''};
  window.DaylightMedigap.render(host,{context:'v',profile,window:windowLine,conversation:id=>conversations.push(id),
    request:async()=>({status:'matched_source_prices',profile:{zip:'34102',age,gender:'Male',tobacco:'Non-Tobacco'},notice:'Listed rates. Not a guaranteed quote.',plans})});
  const all=(node=host)=>[node,...node.children.filter(x=>typeof x==='object').flatMap(all)];
  const tick=()=>new Promise(resolve=>setImmediate(resolve));
  return {host,all,tick,document,conversations,window,profile};
}
const rate=(id,company,variant,cents)=>({id,company,variant,rating_class:'Standard',monthly_cents:cents,annual_cents:null,monthly_with_discounts_cents:null,annual_with_discounts_cents:null,policy_fee:null,household_discount:null,source_fields:{},rating_labels_need_review:false});
const PLANS=[rate('g1','HealthSpring National Health Insurance Company (f/k/a CNHIC)','G',15000),rate('n1','Fictional Mutual','N',11000),
  rate('f1','Fictional Mutual','F',21000),rate('c1','Fictional Life','C',20500),rate('h1','Fictional Life','HDF',6000)];
const LATER=PLANS.map(plan=>['C','F','HDF'].includes(plan.variant)
  ? {...plan,set_aside:{reason:'Only for people eligible for Medicare before January 1, 2020'}} : plan);
const WINDOW={state:'upcoming',text:'If your Part B starts December 1, 2026, your Medigap Open Enrollment Period runs December 2026 through May 2027. During it, an insurer can’t turn you down or charge more because of your health.'};

test('plans first: one pricing line, the person’s window line, then filters and the list',async()=>{
  const f=fixture(PLANS,65,WINDOW);await f.tick();await f.tick();
  const text=f.host.textContent;
  assert.match(text,/ZIP 34102 · Age 65 · Male · Non-tobacco · prices dated November 10, 2026/);        // CN-12, PG-01
  assert.equal((text.match(/November 10, 2026/g)||[]).length,1);                                       // PG-06: the date once
  assert.doesNotMatch(text,/Pilot coverage|reported age|Age reported|guaranteed quote|Talk to Daylight/); // PG-01, PG-06, PG-07, CN-10
  assert.equal((text.match(/Medigap Open Enrollment Period/g)||[]).length,1);                           // PG-03: his window, once
  assert.match(text,/runs December 2026 through May 2027/);
  assert.doesNotMatch(text,/Outside the 6-month/);                                                      // not shown to someone inside it
  assert.equal(f.all().filter(n=>n.tagName==='button'&&n.textContent==='Edit').length,1);              // a single Edit
  assert.doesNotMatch(text,/Plan letters at a glance/);                                                 // folded into the filter
  assert.equal(f.all().filter(n=>n.tagName==='button'&&n.textContent==='All listed rates').length,0);   // live run: alone it did nothing
  const letters=f.all().find(n=>n.tagName==='select'&&n.children.some(o=>/Plan G/.test(o.textContent)));
  assert.match(letters.children.find(o=>o.value==='G').textContent,/Plan G · 1 rate · \$150\.00/);
  assert.match(letters.children.find(o=>o.value==='F').textContent,/eligible before 2020 only/);
});
test('plans a newly eligible person cannot buy stay visible in a closed group with the reason',async()=>{
  const f=fixture(LATER,65,WINDOW);await f.tick();await f.tick();
  const list=f.document.getElementById('medigap-list');
  const cards=list.children.filter(n=>n.tagName==='article').map(n=>n.dataset.medigapId);
  assert.deepEqual(cards.sort(),['g1','n1']);                                                           // PG-02: main list
  const aside=list.children.find(n=>n.tagName==='details');
  assert.match(aside.textContent,/Plans C, F and high-deductible F \(3\)/);
  assert.match(aside.textContent,/Only for people who were eligible for Medicare before January 1, 2020\./);
  assert.deepEqual(f.all(aside).filter(n=>n.dataset.medigapId).map(n=>n.dataset.medigapId).sort(),['c1','f1','h1']);   // still visible (D64)
  assert.notEqual(aside.open,true);
  const older=fixture(PLANS,72,null);await older.tick();await older.tick();
  assert.equal(older.document.getElementById('medigap-list').children.filter(n=>n.tagName==='details').length,0);
  assert.match(older.host.textContent,/Outside the 6-month Medigap Open Enrollment Period/);            // PG-03: only outside it
  assert.equal((older.host.textContent.match(/Outside the 6-month/g)||[]).length,1);
});
test('cards show a plain company name and keep the legal name in the details',async()=>{
  const f=fixture(PLANS,65,WINDOW);await f.tick();await f.tick();
  const card=f.all().find(n=>n.dataset.medigapId==='g1');
  assert.match(card.textContent,/HealthSpring National Health Insurance Company · Plan G/);              // PG-05
  assert.doesNotMatch(card.textContent,/f\/k\/a/);
});
test('a plan letter is described where the letter is; the participant build waits for sign-off',async()=>{
  const f=fixture(PLANS,65,WINDOW,'8895');await f.tick();await f.tick();                                // CN-12
  const g=f.all().find(n=>n.dataset.medigapId==='g1'),n=f.all().find(x=>x.dataset.medigapId==='n1');
  assert.match(g.textContent,/Covers everything Medigap can cover except the yearly Part B deductible\./);
  assert.match(n.textContent,/up to \$20 for some office visits, up to \$50 for some emergency room visits/);
  const line=f.document.getElementById('medigap-letter-note');assert.equal(line.hidden,true);           // letters mixed: on the rate
  const letters=f.all().find(x=>x.tagName==='select'&&x.children.some(o=>/Plan G/.test(o.textContent)));
  letters.value='G';letters.onchange();
  assert.equal(line.hidden,false);
  assert.match(line.textContent,/^Plan G: Covers everything Medigap can cover except the yearly Part B deductible\.$/);
  const one=f.all(f.document.getElementById('medigap-list')).find(x=>x.dataset.medigapId==='g1');
  assert.equal((one.textContent.match(/Covers everything Medigap/g)||[]).length,0);                     // one letter chosen: said once, above
  assert.doesNotMatch(f.host.textContent,/Plan letters at a glance|What the letters mean/);             // no separate block
  const other=fixture(PLANS,65,WINDOW);await other.tick();await other.tick();
  assert.match(other.host.textContent,/Covers everything Medigap can cover/);                           // signed off November 12: both builds
  for(const v of ['A','B','C','D','F','HDF','G','HDG','K','L','M','N']){const s=f.window.DaylightMedigap.letterNote(v);
    assert.ok(s&&(s.match(/[.!?](\s|$)/g)||[]).length===1,v+' is one sentence');}
});
test('the two-path card reads a listed range that leaves out plans the person cannot buy',async()=>{
  const f=fixture(PLANS,65,WINDOW);await f.tick();                                                     // X-03
  const send=async (_,body)=>({plans:body.age===65 ? LATER : PLANS});
  assert.deepEqual({...await f.window.DaylightMedigap.range(send,f.profile)},{low:11000,high:15000,count:2});
  assert.deepEqual({...await f.window.DaylightMedigap.range(send,{...f.profile,inputs:{...f.profile.inputs,age:72}})},{low:6000,high:21000,count:5});
  assert.equal(await f.window.DaylightMedigap.range(send,{status:'missing'}),null);
});
