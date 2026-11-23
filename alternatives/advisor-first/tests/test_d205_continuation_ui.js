/* Actual rendering helpers, fictional response; no browser or network. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../web-8894/advisor.js'),'utf8');
class Node {
  constructor(tag,text='',className=''){this.tag=tag;this.text=text;this.className=className;this.children=[];}
  append(...items){this.children.push(...items);}
  get textContent(){return this.text+this.children.map(c=>c.textContent??c).join('');}
}
function controls(next){
  const offers=[{hidden:false},{hidden:false}],exchanges=offers.map(o=>({querySelectorAll:()=>[o]}));
  const state={conversationNext:next,planReadiness:{canReview:true},record:{conversation:{}},assessment:{journey:{}},conversationPlanner:{guidance:{mode:'work'}}};
  const ctx={state,review:null,prepared:null,q:()=>null,$:()=>({querySelectorAll:()=>exchanges})};
  vm.createContext(ctx);
  vm.runInContext(source.slice(source.indexOf('  function reviewCheckpointAvailable()'),source.indexOf('  function paintHistory()')),ctx);
  return {ctx,state,offers};
}
test('a delivered clarification renders once and suppresses competing review and offers',()=>{
  const question='Do you understand the steps to sign up, or would you like enrollment help?';
  const {ctx,offers}=controls({kind:'clarification',question});
  assert.equal(ctx.reviewCheckpointAvailable(),false);ctx.syncNextStepOffers();assert.ok(offers.every(o=>o.hidden));
  Object.assign(ctx,{el:(tag,text,cls)=>new Node(tag,text,cls),document:{createTextNode:t=>new Node('#text',t)}});
  vm.runInContext(source.slice(source.indexOf('  function inlineText('),source.indexOf('  function textDuration(')),ctx);
  const rendered=ctx.richReply('We can work through this together.\n\n'+question);
  assert.equal(rendered.children.filter(c=>c.className==='conversation-question').length,1);
  assert.equal(rendered.textContent.split(question).length-1,1);
  assert.equal(rendered.children.some(c=>c.tag==='button'),false);
});
test('server-selected review and check each own the current action',()=>{
  const {ctx,state,offers}=controls({kind:'action',action:'plan_review'});
  assert.equal(ctx.reviewCheckpointAvailable(),true);ctx.syncNextStepOffers();assert.ok(offers.every(o=>o.hidden));
  state.conversationNext={kind:'action',action:'check'};
  state.conversationCheck={question:{kind:'doctor'}};
  assert.equal(ctx.reviewCheckpointAvailable(),false);ctx.syncNextStepOffers();assert.ok(offers.every(o=>o.hidden));
});
test('only the latest selected work offer remains actionable',()=>{
  const {ctx,offers}=controls({kind:'action',action:'card',card:'next_step_offer'});
  assert.equal(ctx.reviewCheckpointAvailable(),false);ctx.syncNextStepOffers();
  assert.equal(offers[0].hidden,true);assert.equal(offers[1].hidden,false);
});
test('exhausted-question fallback opens the existing editable profile',()=>{
  let opened=0;const host=new Node('main');
  const start=source.indexOf("    } else if (state.conversationNext?.action === 'profile_review') {");
  const end=source.indexOf('    } else if (state.conversationPlanner',start);
  vm.runInNewContext(source.slice(start,end).replace(/^    } else if/, 'if')+'}',{
    state:{conversationNext:{kind:'action',action:'profile_review'}},host,
    reviewInformation:()=>opened++,button:(text,click)=>({text,click})});
  assert.equal(host.children.length,1);assert.equal(host.children[0].text,'Review your profile');
  host.children[0].click();assert.equal(opened,1);
});
