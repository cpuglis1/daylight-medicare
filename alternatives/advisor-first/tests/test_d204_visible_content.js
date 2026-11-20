/* Real view modules and continuation helpers; fictional data, no browser/network. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const root=path.join(__dirname,'../web-8894');
class Node {
 constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.text='';this.className='';this.classList={add(){},remove(){},toggle(){}};}
 set textContent(t){this.text=String(t);this.children=[];}
 get textContent(){return this.text+this.children.map(c=>typeof c==='string'?c:c.textContent).join(' ');}
 append(...v){this.children.push(...v);}
 prepend(...v){this.children.unshift(...v);}
 setAttribute(k,v){this.attributes[k]=v;}
 addEventListener(k,v){this[k]=v;}
}
const all=n=>[n,...n.children.filter(c=>typeof c==='object').flatMap(all)];
function load(){const document={createElement:t=>new Node(t),getElementById:()=>null},window={};
 const ctx={window,document,Intl,Map,Set,Option:function(t,v){const n=new Node('option');n.textContent=t;n.value=v;return n;}};
 for(const name of ['guided-close.js','conversation-checks.js'])vm.runInNewContext(fs.readFileSync(path.join(root,name),'utf8'),ctx);
 return ctx;
}
const result={kind:'doctor_matrix',key:'doctor:fiction',name:'Dr. Fiction',office_parts:{},date:'2026-11-19',details:['Selected office retained.'],plans:{p:{name:'Fictional Plan',state:'unknown'}}};
test('retained checks remain visible and doctor selectors remain selects',()=>{
 const {window}=load(),host=new Node('main');
 window.DaylightConversationChecks.render(host,{results:[result],compactResults:[result.key],question:{kind:'doctor',token:'fiction',question:'Choose your doctor',choices:Array.from({length:9},(_,i)=>({value:String(i),label:'Doctor '+i}))}}, {visit:'fiction.1',changed(){},defer(){},edit(){},editCheck(){}});
 assert.equal(all(host).filter(n=>n.tagName==='details').length,0);
 assert.match(host.textContent,/Dr. Fiction/);assert.match(host.textContent,/Fictional Plan/);
 const select=all(host).find(n=>n.tagName==='select');assert.ok(select);assert.equal(select.children.length,10);
});
test('summary facts and open checks are visible, with one continuation',()=>{
 const {window}=load();let clicks=0;
 const host=window.DaylightGuidedClose.summary({title:'Your next step',ready:true,rows:[{label:'Priority',value:'Predictable costs'}],findings:['Doctor check retained'],open:['Coverage needs checking'],steps:[{text:'Review your information'}]}, {review:()=>clicks++});
 assert.equal(all(host).filter(n=>n.tagName==='details').length,0);
 assert.match(host.textContent,/Predictable costs/);assert.match(host.textContent,/Coverage needs checking/);
 const buttons=all(host).filter(n=>n.tagName==='button');assert.equal(buttons.length,1);buttons[0].click();assert.equal(clicks,1);
});
test('current review checkpoint hides old and competing task offers',()=>{
 const source=fs.readFileSync(path.join(root,'advisor.js'),'utf8');
 const code=source.slice(source.indexOf('  function reviewCheckpointAvailable()'),source.indexOf('  function paintHistory()'));
 const offers=[{hidden:false},{hidden:false}],exchanges=offers.map(offer=>({querySelectorAll:()=>[offer]}));
 const state={planReadiness:{canReview:true},record:{conversation:{}},assessment:{journey:{}},conversationPlanner:{guidance:{mode:'work'}}};
 const ctx={state,review:null,prepared:null,q:()=>null,$:()=>({querySelectorAll:()=>exchanges})};vm.createContext(ctx);vm.runInContext(code,ctx);
 assert.equal(ctx.reviewCheckpointAvailable(),true);ctx.syncNextStepOffers();assert.ok(offers.every(o=>o.hidden));
 state.planReadiness.canReview=false;ctx.syncNextStepOffers();assert.equal(offers[0].hidden,true);assert.equal(offers[1].hidden,false);
 ctx.q=()=>({id:'T06'});ctx.syncNextStepOffers();assert.ok(offers.every(o=>o.hidden));
});
test('Sources still render as a disclosure',()=>{
 const source=fs.readFileSync(path.join(root,'advisor.js'),'utf8');
 const code=source.slice(source.indexOf('  function citationBlock('),source.indexOf('  function turnVisual('));
 const ctx={URL,Map,el:(tag,text,cls)=>{const n=new Node(tag);if(text)n.textContent=text;n.className=cls;return n;}};vm.createContext(ctx);vm.runInContext(code,ctx);
 const out=ctx.citationBlock([{url:'https://www.medicare.gov/',label:'Medicare'}]);assert.equal(out.tagName,'details');assert.equal(out.children[0].textContent,'Sources');
});
test('review and ready handoff each render exactly one working action',async()=>{
 const source=fs.readFileSync(path.join(root,'advisor.js'),'utf8');
 const start=source.indexOf('    if (!(window.DaylightGuidedClose && state.comparisonClose?.show) && reviewCheckpointAvailable())');
 const code=source.slice(start,source.indexOf('    if (config?.comparisonPreview',start));
 for(const ready of [false,true]) {
  const host=new Node('main'),calls=[];host.append(new Node('section'));
  const ctx={window:{},state:{plansHandoff:ready?{token:'fictional-reviewed-token'}:null},host,reviewCheckpointAvailable:()=>true,
   button:(label,click)=>{const n=new Node('button');n.textContent=label;n.click=click;return n;},
   turn:async action=>{calls.push(action);return true;},openPlansWorkspace:async()=>calls.push({opened:true})};
  vm.runInNewContext(code,ctx);assert.equal(host.children.filter(n=>n.tagName==='button').length,1);
  assert.equal(host.children[0].tagName,'button','Continue precedes expanded check results');
  assert.equal(host.children[0].textContent,ready?'See plans':'Review your info');await host.children[0].click();
  assert.equal(calls[0].type,ready?'get_plan_handoff':'review_plans');
  if(ready){assert.equal(calls[0].token,'fictional-reviewed-token');assert.equal(calls[1].opened,true);}
 }
});
