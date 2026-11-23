'use strict';
// D147: evaluation-only sorting view. Fictional results; no network.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const read=name=>fs.readFileSync(path.join(__dirname,'../web-8894',name),'utf8');
function dom(){
  const ids=new Map();
  class Node {
    constructor(tag){this.tagName=tag;this.children=[];this.listeners={};this.dataset={};this.attributes={};this.value='';this.isConnected=true;this.text='';this.className='';
      const self=this;this.classList={add:c=>{self.className=(self.className+' '+c).trim();},contains:c=>self.className.split(' ').includes(c)};}
    set id(v){this._id=v;ids.set(v,this);}get id(){return this._id;}
    set textContent(v){this.text=String(v);this.children=[];}get textContent(){return this.text+this.children.map(x=>x.textContent??x).join('');}
    append(...nodes){for(const n of nodes){this.children.push(n);if(typeof n==='object')n.parentNode=this;}}
    insertBefore(node,before){const i=this.children.indexOf(before);this.children.splice(i,0,node);node.parentNode=this;}
    replaceChildren(...nodes){this.children=[];this.append(...nodes);}
    setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,v){this.listeners[k]=v;}focus(){}
  }
  const document={createElement:t=>new Node(t),createElementNS:(_ns,t)=>new Node(t),getElementById:id=>ids.get(id),body:new Node('body')};
  class Option extends Node {constructor(label,value){super('option');this.textContent=label;this.value=value;}}
  const all=n=>[n,...n.children.filter(x=>typeof x==='object').flatMap(all)];
  return {Node,document,Option,all};
}
const check=(id,state,kind,label=id)=>({id,label,state,note:'Fictional note for '+id,kind});
const RESULT={method:'daylight-tiered-v1-20261112',evaluation_only:true,
  preferences:[{id:'doctors',label:'Keep your doctors',priority:true},{id:'predictable',label:'Predictable costs',priority:false}],
  path:{state:'ready',groups:[{id:'priority',label:'Matches your priorities',ids:['original']},{id:'needs',label:'Meets your needs, not all your priorities',ids:['advantage']}],
    plans:{original:{group:'priority',rank:1,recommended:true,checks:[check('doctors','met','priority','Keep your doctors')]},
      advantage:{group:'needs',rank:1,recommended:false,checks:[check('doctors','unknown','priority','Keep your doctors')]}},
    recommended_ids:['original'],no_pick_reason:null,sort_note:'',notes:['Fictional underwriting note.']},
  advantage:{state:'unavailable',message:'Fictional: not available.',groups:[],plans:{},recommended_ids:[],notes:[]},
  medigap:{state:'ready',groups:[{id:'priority',label:'Matches your priorities',ids:['g1','g2']},{id:'needs',label:'Meets your needs, not all your priorities',ids:['n1']},{id:'excluded',label:'Doesn’t meet your needs, or you may not qualify',ids:['f1']}],
    plans:{g1:{group:'priority',rank:1,recommended:true,checks:[check('predictable','met','preference'),check('doctors','met','priority')]},
      g2:{group:'priority',rank:2,recommended:false,checks:[check('doctors','unknown','priority')]},
      n1:{group:'needs',rank:1,recommended:false,checks:[check('doctors','not_met','priority')]},
      f1:{group:'excluded',rank:1,recommended:false,checks:[check('eligibility','not_met','eligibility','Who can buy it')]}},
    recommended_ids:['g1'],no_pick_reason:null,sort_note:'Ordered by lowest listed monthly premium.',notes:[]},
  part_d:{state:'ready',groups:[{id:'priority',label:'Meets your needs',ids:['p1']}],plans:{p1:{group:'priority',rank:1,recommended:false,checks:[]}},
    recommended_ids:[],no_pick_reason:'No pick yet: fictional reason.',sort_note:'',notes:[]}};
function load(scripts=['recommendation-view.js']){
  const d=dom(),window={};
  const context={window,document:d.document,Option:d.Option,Intl,Number,Set,Map,Object,Array,Infinity,Error,String,JSON,console,Promise};
  for(const s of scripts)vm.runInNewContext(read(s),context);
  return {...d,window,R:window.DaylightRecommend};
}
const tick=()=>new Promise(r=>setImmediate(r));
const plain=v=>JSON.parse(JSON.stringify(v)); // values cross the vm realm
test('inputs are fetched once per change and cleared without inputs',async()=>{
  const {R}=load(),calls=[];let changes=0;
  R.configure(async(url,body)=>{calls.push([url,body]);return RESULT;});R.onChange(()=>changes++);
  assert.equal(R.active(),false);R.update(null);assert.equal(calls.length,0);
  R.update({version:'x',doctors:'list'});assert.equal(R.status().pending,true);await tick();
  R.update({version:'x',doctors:'list'});await tick();
  assert.deepEqual(plain(calls),[['/api/recommendation',{inputs:{version:'x',doctors:'list'}}]]);
  assert.equal(changes,1);assert.equal(R.tab('medigap').recommended_ids[0],'g1');assert.equal(R.tab('advantage'),null);
  R.update(null);assert.equal(R.active(),false);assert.equal(R.tab('medigap'),null);assert.equal(changes,2);
});
test('a stale answer never replaces newer inputs',async()=>{
  const {R}=load();let release;
  R.configure(async(url,body)=>body.inputs.n===1?new Promise(r=>{release=()=>r(RESULT);}):{...RESULT,medigap:{...RESULT.medigap,recommended_ids:['g2']}});
  R.update({n:1});R.update({n:2});await tick();release();await tick();
  assert.deepEqual(plain(R.tab('medigap').recommended_ids),['g2']);
});
test('cards get the top-match line and marked checks, needs and priorities first',async()=>{
  const {R,document,all}=load();R.configure(async()=>RESULT);R.update({v:1});await tick();
  const card=document.createElement('article'),actions=document.createElement('div');card.append(actions);
  R.decorate('medigap','g1',card,actions);
  assert.equal(card.children[0].className,'rec-fit');assert.ok(card.classList.contains('rec-recommended'));
  const text=card.textContent;assert.match(text,/Top match for what you told Daylight/);
  const items=all(card).filter(n=>/rec-check /.test(n.className));
  assert.deepEqual(items.map(n=>n.className),['rec-check rec-met','rec-check rec-met']);
  assert.match(items[0].textContent,/^✓Meets: doctorsYour priority/);   // the priority comes before other preferences
  const excluded=document.createElement('article');R.decorate('medigap','f1',excluded);
  assert.match(excluded.textContent,/✗Does not meet: Who can buy it/);
  const plain=document.createElement('article');R.decorate('part_d','p1',plain);assert.equal(plain.children.length,0);
});
test('groups keep backend order; rows it did not sort go last',async()=>{
  const {R}=load();R.configure(async()=>RESULT);R.update({v:1});await tick();
  const groups=R.arrange('medigap',[{id:'f1'},{id:'zz'},{id:'n1'},{id:'g2'},{id:'g1'}]);
  assert.deepEqual(plain(groups.map(g=>[g.id,g.rows.map(r=>r.id)])),[['priority',['g1','g2']],['needs',['n1']],['excluded',['f1']],['unsorted',['zz']]]);
  assert.equal(R.arrange('advantage',[{id:'a'}]),null);
});
test('summaries name the pick or why there is none, and explain the method',async()=>{
  const {R}=load();R.configure(async()=>RESULT);R.update({v:1});await tick();
  // D157 (CN-04): the page carries one quiet link; the explanation opens from it.
  assert.equal(R.summary('path',{}).textContent,'How Daylight sorted these');
  const path=R.explain('path',{original:'Original Medicare, with Medigap and a Part D drug plan'}).textContent;
  assert.doesNotMatch(path,/Evaluation mode|pilot/i);assert.match(path,/Top match: Original Medicare, with Medigap/);
  assert.match(path,/What you told Daylight: Keep your doctors \(your priority\), Predictable costs\./);
  assert.match(path,/Commissions and any payment to Daylight are not part of this sorting/);
  assert.match(R.explain('part_d').textContent,/No pick yet: fictional reason\./);
  assert.match(R.explain('advantage').textContent,/Fictional: not available\./);
});
test('Medigap tab defaults to the evaluation order, grouped, and keeps the other sorts',async()=>{
  const env=load(['recommendation-view.js','medigap-plans.js']),{R,window,document,all}=env;
  R.configure(async()=>RESULT);R.update({v:1});await tick();
  const rows=[['g1','G',15000],['g2','G',16000],['n1','N',11000],['f1','F',20000]].map(([id,variant,cents])=>({id,company:'Fictional '+id,variant,rating_class:'Standard',monthly_cents:cents,annual_cents:null,policy_fee:null,select_observed:false,source_fields:{},naic:'0'}));
  const profile={inputs:{zipcode:'34102',age:66,gender:'Female',tobacco:'Non-Tobacco'},held:[],details:[],missing:[],questions:[],status:'ready',message:''};
  const host=document.createElement('main');
  window.DaylightMedigap.render(host,{request:async()=>({status:'matched_source_prices',profile:{zip:'34102',age:66,gender:'Female',tobacco:'Non-Tobacco'},notice:'Fictional.',plans:rows}),profile,context:'v',conversation:()=>{}});
  await tick();await tick();
  const select=all(host).find(n=>n.tagName==='select'&&n.children.some(o=>o.value==='fit'));
  assert.equal(select.value,'fit');
  const list=document.getElementById('medigap-list');
  assert.deepEqual(list.children.map(n=>n.tagName),['section','section','section']);
  assert.deepEqual(all(list).filter(n=>n.dataset.medigapId).map(n=>n.dataset.medigapId),['g1','g2','n1','f1']);
  assert.match(list.children[0].textContent,/^Matches your priorities2 rates/);
  select.value='premium';select.onchange();
  assert.deepEqual(all(document.getElementById('medigap-list')).filter(n=>n.dataset.medigapId).map(n=>n.dataset.medigapId),['n1','g1','g2','f1']);
});

test('D214 card findings show explicit outcomes, conditional drug warnings and scoped cost amounts',async()=>{
  const {R,all}=load();
  const data=plain(RESULT);
  data.plan_card_checks={version:'collier-plan-card-checks-v1'};
  data.part_d.plans.p1.card_checks=[
    {id:'medicines',label:'Your medicines',state:'unknown',kind:'observation',indicator:'warning',outcome:'Needs checking',note:'Fictional medicine requires prior authorization. This is not an approval.'},
    {id:'drug_cost',label:'Premiums and drug spending',state:'met',kind:'observation',indicator:'supported',outcome:'Estimate available',note:'$22.34 for the selected December refills. Uses retail averages and excludes medical costs.'},
    {id:'total_cost',label:'Total yearly cost',state:'unknown',kind:'observation',indicator:'warning',outcome:'Not calculated',note:'A complete medical-plus-drug estimate is not available.'}
  ];
  R.configure(async()=>data);R.update({planCardChecks:true,inputs:{v:1},continuation:'fictional'});await tick();
  const list=R.checks('part_d','p1');
  const rows=all(list).filter(n=>n.dataset.checkId);
  assert.deepEqual(rows.map(n=>n.className),['rec-check rec-evidence rec-warning','rec-check rec-evidence rec-supported','rec-check rec-evidence rec-warning']);
  assert.deepEqual(rows.map(n=>n.dataset.finding),['unknown','met','unknown']);
  assert.match(list.textContent,/Your medicinesNeeds checking/);
  assert.match(list.textContent,/prior authorization/);
  assert.match(list.textContent,/Estimate available.*\$22\.34/);
  assert.match(list.textContent,/Total yearly costNot calculated/);
  assert.equal(all(list).filter(n=>n.tagName==='svg').length,3);
  assert.match(R.explain('part_d').textContent,/does not mean a plan is affordable or cheapest/);
});

test('D214 changed or withdrawn evidence clears old marks before the replacement arrives',async()=>{
  const {R}=load();let release,changed=0,calls=0;
  const first=plain(RESULT);first.part_d.plans.p1.card_checks=[{id:'medicines',label:'Your medicines',state:'met',kind:'observation',indicator:'supported',outcome:'Listed',note:'Fictional dated listing.'}];
  R.configure(async()=>++calls===1?first:new Promise(resolve=>{release=()=>resolve(RESULT);}));
  R.onChange(()=>changed++);
  R.update({planCardChecks:true,inputs:{n:1},continuation:'same',evidence:[{membership:'listed_in_network'}]});await tick();
  assert.ok(R.checks('part_d','p1'));
  R.update({planCardChecks:true,inputs:{n:1},continuation:'same',evidence:[]});
  assert.equal(R.checks('part_d','p1'),null);
  assert.equal(R.status().pending,true);
  assert.ok(changed>=3);release();await tick();
  assert.equal(R.status().pending,false);
});
