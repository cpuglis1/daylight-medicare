/* Production utility handlers with a fake transport: no browser or AI calls. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'..','web','advisor.js'),'utf8');
const helpers = source.slice(source.indexOf('  async function save('),source.indexOf('  function reviewInformation('));
const privacy = source.slice(source.indexOf('  function privacy('),source.indexOf("  $('composer').onsubmit"));
const plain = value => JSON.parse(JSON.stringify(value));

function harness() {
  const calls=[],dialogs=[],notices=[],nodes=new Map();
  class Node {
    constructor(tag,text) {this.tag=tag;this.textContent=text;this.children=[];this.checked=false;this.value='';this.hidden=false;}
    append(...children) {this.children.push(...children);}
    close() {this.closed=true;}
    showModal() {this.open=true;}
  }
  const node=id=>{if(!nodes.has(id))nodes.set(id,new Node(id));return nodes.get(id);};
  node('message').value='Unsent current draft';
  const ctx=vm.createContext({
    state:{guide:{preferences:{saveGuide:true,saveSensitive:true},fields:{canary:'current report'}},record:{facts:{}},continuation:'old-owner-binding',identity:{old:true},comparison:{old:true}},
    session:{csrf:'old-csrf',hasSaved:true},savedVersion:3,readinessVersion:2,
    pendingSave:{guide:{preferences:{saveGuide:true,saveSensitive:true},fields:{old:'earlier sensitive snapshot'}},record:{facts:{}},expectedVersion:3,expectedReadinessVersion:2,operationId:'earlier-operation'},
    review:{token:'old-review'},prepared:{id:'old-preparation'},failedRequest:{requestId:'old-failed'},lastRequest:{requestId:'old-last'},
    saveText:'Not saved',busy:false,history:[{reply:'Retained conversation'}],drafts:new Map([['T04',{choice:['soonest']}]]),
    selectedGoal:'compare',showGuide:true,active:true,metrics:{turns:2,llmCalls:0},
    clone:structuredClone,crypto:{randomUUID:()=> 'new-operation-id'},$ :node,
    setBusy(value){ctx.busy=value;},render(){},renderCurrent(){},note(text){notices.push(text);},
    document:{createTextNode:text=>new Node('text',text)},
    el:(tag,text)=>new Node(tag,text),
    button:(text,handler)=>{const b=new Node('button',text);b.onclick=handler;return b;},
    dialog:title=>{const d=new Node('dialog',title);dialogs.push(d);return d;},
    api:async(path,body,method)=>{
      calls.push({path,body:body && structuredClone(body),method:method || (body ? 'POST' : 'GET')});
      return h.transport(path,body,method);
    },
  });
  const h={ctx,calls,dialogs,notices,node,transport(path,body) {
    if(path==='/api/guest/profile')return {version:4,guide:{fields:{stored:true}}};
    if(path==='/api/guest/readiness')return {version:3,record:{facts:{}}};
    if(path==='/api/guest/session')return {csrf:'new-csrf',version:0,hasSaved:false};
    if(path==='/api/conversation/save')return {version:5,readinessVersion:4,omittedSensitive:!body.guide.preferences.saveSensitive};
    if(path==='/api/conversation/turn')return {guide:structuredClone(body.guide),record:structuredClone(body.record),continuation:'new-owner-binding',assessment:{}};
    throw Error('Unexpected request '+path);
  }};
  vm.runInContext(helpers+'\n'+privacy,ctx,{filename:'advisor.js:actual-utility-handlers'});
  h.find=(tag,text,within=dialogs.at(-1))=> {
    const found=[];const visit=n=>{if(n.tag===tag && (text===undefined || n.textContent===text))found.push(n);for(const child of n.children || [])visit(child);};visit(within);return text===undefined ? found : found[0];
  };
  return h;
}

test('pending-save reconciliation reads versions without resending the earlier snapshot',async()=>{
  const h=harness(),before=plain(h.ctx.state);
  await h.ctx.reconcilePendingSave();
  assert.deepEqual(h.calls.map(c=>[c.path,c.method]),[['/api/guest/profile','GET'],['/api/guest/readiness','GET']]);
  assert.equal(h.ctx.pendingSave,null);assert.equal(h.ctx.savedVersion,4);assert.equal(h.ctx.readinessVersion,3);
  assert.deepEqual(plain(h.ctx.state),before);assert.equal(h.node('message').value,'Unsent current draft');
});

test('read-only reconciliation failure retains uncertainty and does not claim a save',async()=>{
  const h=harness(),pending=h.ctx.pendingSave;
  h.transport=async()=>{throw Error('offline');};
  await assert.rejects(h.ctx.reconcilePendingSave(),/offline/);
  assert.equal(h.ctx.pendingSave,pending);assert.equal(h.ctx.savedVersion,3);
  assert.ok(h.calls.every(call=>call.method==='GET'));
});

test('completeSave cannot resend an old payload after sensitive permission withdrawal',async()=>{
  const h=harness();h.ctx.state.guide.preferences.saveSensitive=false;
  await assert.rejects(h.ctx.completeSave(),/Privacy choices changed/);
  assert.equal(h.calls.length,0);
});

test('completeSave cannot write when saving is now paused',async()=>{
  const h=harness();h.ctx.state.guide.preferences.saveGuide=false;
  await assert.rejects(h.ctx.completeSave(),/Privacy choices changed/);
  assert.equal(h.calls.length,0);
});

test('Apply privacy choices reconciles uncertainty then saves current reduced permission',async()=>{
  const h=harness();h.ctx.privacy();
  const [save,sensitive]=h.find('input');save.checked=true;sensitive.checked=false;
  await h.find('button','Apply privacy choices').onclick();
  const writes=h.calls.filter(call=>call.method==='POST');
  assert.equal(writes.length,1);assert.equal(writes[0].path,'/api/conversation/save');
  assert.equal(writes[0].body.guide.preferences.saveSensitive,false);
  assert.equal(writes[0].body.expectedVersion,4);assert.equal(writes[0].body.expectedReadinessVersion,3);
  assert.equal(writes[0].body.operationId,'new-operation-id');
  assert.equal(writes[0].body.guide.fields.canary,'current report');
  assert.equal(writes[0].body.guide.fields.old,undefined);
});

test('pausing saving with a pending operation performs no new write',async()=>{
  const h=harness();h.ctx.privacy();
  const [save,sensitive]=h.find('input');save.checked=false;sensitive.checked=false;
  await h.find('button','Apply privacy choices').onclick();
  assert.equal(h.calls.length,2);assert.ok(h.calls.every(call=>call.method==='GET'));
  assert.equal(h.ctx.pendingSave,null);assert.match(h.ctx.saveText,/Saving paused/);
});

test('Check the pending save is read-only even with newly unchecked privacy controls',async()=>{
  const h=harness();h.ctx.privacy();for(const input of h.find('input'))input.checked=false;
  await h.find('button','Check the pending save').onclick();
  assert.ok(h.calls.every(call=>call.method==='GET'));assert.equal(h.ctx.pendingSave,null);
  assert.match(h.notices.at(-1),/without resending/);
});

test('deletion binds retained reports to the new owner without reusing any prior token',async()=>{
  const h=harness(),draft=h.node('message').value,history=h.ctx.history,drafts=h.ctx.drafts;
  const defaultTransport=h.transport;let deleted=false;
  h.transport=(path,body,method)=>method==='DELETE' ? (deleted=true,{deleted:true})
    : deleted && path==='/api/guest/profile' ? {version:0,guide:null}
    : deleted && path==='/api/guest/readiness' ? {version:0,record:null} : defaultTransport(path,body,method);
  assert.equal(await h.ctx.deleteSavedInformation(),true);
  assert.deepEqual(h.calls.map(c=>[c.path,c.method]),[['/api/guest/profile','DELETE'],['/api/guest/session','GET'],['/api/guest/profile','GET'],['/api/guest/readiness','GET'],['/api/conversation/turn','POST']]);
  const refresh=h.calls.at(-1).body;
  assert.deepEqual(plain(refresh.action),{type:'refresh'});assert.equal(refresh.continuation,undefined);assert.equal(refresh.aiConsent,undefined);
  assert.equal(h.ctx.state.continuation,'new-owner-binding');assert.equal(h.ctx.state.guide.fields.canary,'current report');
  assert.equal(h.ctx.pendingSave,null);assert.equal(h.ctx.review,null);assert.equal(h.ctx.prepared,null);
  assert.equal(h.ctx.lastRequest,null);assert.equal(h.ctx.failedRequest,null);assert.equal(h.ctx.state.identity,undefined);
  assert.equal(h.ctx.session.hasSaved,false);assert.equal(h.ctx.savedVersion,0);assert.equal(h.ctx.readinessVersion,0);
  assert.equal(h.node('message').value,draft);assert.equal(h.ctx.history,history);assert.equal(h.ctx.drafts,drafts);
});

test('failed reconnect after deletion keeps draft and a retry marker, never old authority',async()=>{
  const h=harness(),defaultTransport=h.transport;
  h.transport=(path,body,method)=>method==='DELETE' ? {deleted:true}
    : path==='/api/guest/profile' ? {version:0,guide:null}
    : path==='/api/guest/readiness' ? {version:0,record:null}
    : path==='/api/conversation/turn' ? Promise.reject(Error('reconnect unavailable')) : defaultTransport(path,body,method);
  await assert.rejects(h.ctx.deleteSavedInformation(),/reconnect unavailable/);
  assert.equal(h.ctx.state.sessionRebindRequired,true);assert.equal(h.ctx.state.continuation,undefined);
  assert.equal(h.ctx.session.hasSaved,false);assert.equal(h.ctx.review,null);assert.equal(h.ctx.pendingSave,null);
  assert.equal(h.node('message').value,'Unsent current draft');assert.equal(h.ctx.busy,false);
  h.transport=defaultTransport;await h.ctx.refreshVisitAuthority();
  assert.equal(h.ctx.state.sessionRebindRequired,undefined);assert.equal(h.ctx.state.continuation,'new-owner-binding');
});

test('a rejected delete preserves active reports, permissions, authorization and pending save',async()=>{
  const h=harness(),before=h.ctx.state,pending=h.ctx.pendingSave,review=h.ctx.review;
  h.transport=()=>Promise.reject(Object.assign(Error('Saved guide changed'),{code:409}));
  await assert.rejects(h.ctx.deleteSavedInformation(),/Saved guide changed/);
  assert.equal(h.ctx.state,before);assert.equal(h.ctx.state.continuation,'old-owner-binding');
  assert.equal(h.ctx.pendingSave,pending);assert.equal(h.ctx.review,review);assert.equal(h.ctx.session.hasSaved,true);
  assert.equal(h.calls.length,1);assert.equal(h.ctx.busy,false);
});

test('a lost deletion response remains uncertain and only reads/rebinds on recovery',async()=>{
  const h=harness(),defaultTransport=h.transport;
  h.transport=()=>Promise.reject(Error('response lost'));
  await assert.rejects(h.ctx.deleteSavedInformation(),/response lost/);
  assert.equal(h.ctx.state.deletionUncertain,true);assert.equal(h.ctx.state.sessionRebindRequired,true);
  assert.equal(h.ctx.state.continuation,undefined);assert.equal(h.ctx.pendingSave,null);
  assert.equal(h.ctx.state.guide.preferences.saveGuide,false);assert.match(h.ctx.saveText,/needs checking/);
  assert.equal(h.node('message').value,'Unsent current draft');
  h.transport=(path,body,method)=>path==='/api/guest/profile' ? {version:0,guide:null}
    : path==='/api/guest/readiness' ? {version:0,record:null} : defaultTransport(path,body,method);
  await h.ctx.refreshVisitAuthority();
  assert.equal(h.calls.filter(call=>call.method==='DELETE').length,1,'Recovery never retries deletion.');
  assert.equal(h.calls.filter(call=>call.method==='POST').length,1,'Only a free refresh is posted.');
  assert.equal(h.calls.at(-1).body.action.type,'refresh');assert.equal(h.calls.at(-1).body.aiConsent,undefined);
  assert.equal(h.ctx.state.deletionUncertain,undefined);assert.equal(h.ctx.session.hasSaved,false);
  assert.match(h.ctx.saveText,/No saved copy found/);
});

test('deletion retains a paused screen locally without copying pause into backend reports or authority',async()=>{
  const h=harness(),defaultTransport=h.transport;
  h.ctx.state.assessment={nextQuestion:null,intakePaused:true,conversationOpen:true,narrative:{opener:false}};
  h.transport=(path,body,method)=>method==='DELETE' ? {deleted:true}
    : path==='/api/guest/profile' ? {version:0,guide:null}
    : path==='/api/guest/readiness' ? {version:0,record:null}
    : path==='/api/conversation/turn' ? {guide:structuredClone(body.guide),record:structuredClone(body.record),continuation:'fresh',assessment:{nextQuestion:{id:'T04'},narrative:{opener:false}}}
    : defaultTransport(path,body,method);
  await h.ctx.deleteSavedInformation();
  assert.equal(h.ctx.state.assessment.nextQuestion,null);assert.equal(h.ctx.state.assessment.intakePaused,true);
  const posted=h.calls.find(call=>call.path==='/api/conversation/turn').body;
  assert.equal(posted.assessment,undefined);assert.equal(posted.continuation,undefined);
  assert.equal(posted.record.paused,undefined);assert.equal(posted.aiConsent,undefined);
  assert.equal(h.ctx.state.continuation,'fresh');
});

test('resuming a stored profile drops earlier failed-save and action bindings while preserving unsent text',async()=>{
  const h=harness();h.ctx.resume();
  h.transport=(path,body)=>path==='/api/guest/profile' ? {version:4,guide:{preferences:{saveGuide:true,saveSensitive:false},fields:{stored:true},flow:{}}}
    : path==='/api/guest/readiness' ? {version:3,record:{facts:{}}}
    : {guide:structuredClone(body.guide),record:structuredClone(body.record),continuation:'resumed-binding',assessment:{}};
  await h.find('button','Resume saved reports').onclick();
  assert.equal(h.ctx.state.continuation,'resumed-binding');assert.equal(h.ctx.pendingSave,null);
  assert.equal(h.ctx.lastRequest,null);assert.equal(h.ctx.failedRequest,null);assert.equal(h.ctx.review,null);
  assert.equal(h.node('message').value,'Unsent current draft');assert.equal(h.ctx.drafts.size,0);
});
