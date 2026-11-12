/* Read question descriptors from the real Python service and click the actual
 * production renderer. No browser, HTTP request, or AI transport is present. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const registry = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = fs.readFileSync(path.join(__dirname, '..', 'web', 'advisor.js'), 'utf8');
const plain = value => JSON.parse(JSON.stringify(value));
const production = [
  source.match(/^  const el = .*$/m)[0],
  source.match(/^  const button = .*$/m)[0],
  source.slice(source.indexOf('  function draftFor('),source.indexOf('  function resizeComposer(')),
  source.slice(source.indexOf('  function selectionSlot('),source.indexOf('  function revealSend(')),
  source.slice(source.indexOf('  function renderForm('),source.indexOf('  function renderReview(')),
].join('\n');

class Node {
  constructor(tag) {this.tagName=tag.toUpperCase();this.children=[];this.attributes=new Map();this.value='';this._text='';this.parentElement=null;}
  set textContent(value) {this._text=String(value);this.children=[];}
  get textContent() {return this._text+this.children.map(child=>child.textContent).join('');}
  append(...children) {for (const child of children) {child.parentElement=this;this.children.push(child);}}
  prepend(child) {child.parentElement=this;this.children.unshift(child);}
  setAttribute(key,value) {this.attributes.set(key,String(value));}
  getAttribute(key) {return this.attributes.get(key) ?? null;}
  querySelector(selector) {const group=selector.match(/^\[data-coverage-group="([a-z]+)"\]$/);return group ? all(this).find(node=>node.getAttribute('data-coverage-group')===group[1]) : null;}
  focus() {this.focused=true;}
}
function all(node) {return [node,...node.children.flatMap(all)];}
function harness(question, seed) {
  const message=new Node('textarea'), calls=[], notices=[], drafts=new Map();let host;
  const context=vm.createContext({
    document:{createElement:tag=>new Node(tag)},baseline:registry.baseline,drafts,
    state:{guide:{fields:{}},record:{facts:{}},assessment:{task:'compare'}},
    $:id=>id==='message'?message:host,readable:String,
    note:text=>notices.push(text),revealSend(){},
    presentControl:control=>control,
    presentText(parent,text,presentation,tag,cls) {const node=new Node(tag);node.textContent=text;node.className=cls||'';parent.append(node);},
    async turn(...args) {calls.push(plain(args));return true;},
    renderCurrent(){paint();},
  });
  vm.runInContext(production,context,{filename:'advisor.js:production-button-matrix'});
  if (seed) drafts.set(question.signature,structuredClone(seed));
  function paint() {host=new Node('section');context.renderForm(host,question,{reveal:false,offset:0});return host;}
  paint();
  return {context,calls,notices,message,paint,
    get draft(){return context.draftFor(question);},
    get buttons(){return all(host).filter(node=>node.tagName==='BUTTON');},
    click(label,last=false){const found=this.buttons.filter(node=>node.textContent===label);const button=last?found.at(-1):found[0];assert.ok(button,'Button must exist: '+label);button.onclick();},
    submit(){return context.submitForm(question);},
  };
}

test('the inventory covers all 41 approved meanings including child aliases and conditional finite fields',()=>{
  assert.equal(registry.inventoryIds.length,41);
  assert.equal(new Set(registry.questions.map(question=>question.auditInventoryId)).size,41);
  for (const key of ['county','daysSupply','channel','priorMedigap','includes'])
    assert.ok(registry.questions.some(question=>question.fields.some(field=>field.key===key && field.type==='select')));
});

for (const question of registry.questions) {
  const name=question.auditInventoryId+':'+question.auditVariant;
  test(name+' every precise choice routes its exact meaning only after Send',async()=>{
    for (const [value,label] of question.choices.filter(([value])=>value!=='unknown')) {
      const h=harness(question);
      if (question.id==='T05') {
        const view=h.context.insuranceChoiceView(question,h.draft);
        const group=view.items.find(item=>item.group && item.values.includes(value));
        if (group) h.click(group.label);
      }
      const visibleLabel=h.context.insuranceChoiceLabel(question,value,label);
      h.click(visibleLabel);
      assert.equal(h.calls.length,0,'Selecting never sends or grants a model request.');
      assert.deepEqual(Array.from(h.draft.choice),[value]);
      h.click(visibleLabel);
      assert.equal(h.context.hasFormAnswer(question),false,'Pressing the same answer again deselects it.');
      h.click(visibleLabel);
      await h.submit();
      assert.equal(h.calls.length,1);
      assert.deepEqual(h.calls[0][0],{type:question.fields.length?'stage':'choice',id:question.id,entity:question.entity,fields:{choice:value}});
      assert.equal(h.calls[0][2],true,'Only deliberate Send permits composition.');
    }
  });
  test(name+' unknown/defer/clear do not invent an answer',async()=>{
    for (const [resolution,label] of [['unknown','I don’t know'],['defer','Check later']]) {
      const h=harness(question);h.click(label,true);
      assert.equal(h.calls.length,0);
      await h.submit();
      // The backend resolves the current entity; a browser cannot redirect the
      // disposition to a different doctor or medicine by inventing an entity.
      assert.deepEqual(h.calls[0][0],{type:resolution,id:question.id});
      assert.equal(h.calls[0][2],true);
      h.click('Clear selection');assert.equal(h.context.hasFormAnswer(question),false);
      const before=h.calls.length;await h.submit();assert.equal(h.calls.length,before);
    }
    const h=harness(question,{choice:[],fields:{daysSupply:'30'},coverageGroup:'medicare'});
    h.click('Check later',true);
    assert.deepEqual(plain(h.draft.fields),{},'A whole-question disposition clears old finite-field selections.');
    assert.equal(h.draft.coverageGroup ?? '','','An unrelated refinement must not remain expanded.');
    h.click('Clear selection');
    assert.equal(h.draft.coverageGroup ?? '','','Clear selection resets local refinement state.');
  });
  for (const field of question.fields.filter(field=>field.type==='select')) {
    test(name+' '+field.key+' finite fields preserve exact field/entity',async()=>{
      for (const [value,label] of field.options) {
        const h=harness(question);h.click(label);
        assert.equal(h.calls.length,0);
        if (!(value==='other' && field.key==='daysSupply')) {
          h.click(label);
          assert.equal(h.context.hasFormAnswer(question),false,'A selected field option can be deselected.');
          h.click(label);
        }
        await h.submit();
        // Non-report options may deliberately focus the one composer instead.
        // Such controls must not create an invalid finite report.
        if (value==='other' && field.key==='daysSupply') {
          assert.equal(h.calls.length,0,'Another amount is a typing affordance, not a numeric days-supply report.');
          assert.equal(h.draft.fields.daysSupply ?? '', '');
        } else {
          assert.equal(h.calls.length,1);
          assert.deepEqual(h.calls[0][0],{type:'stage',id:question.id,entity:question.entity,fields:{[field.key]:value}});
        }
      }
    });
  }
}

test('every multi-select exclusive choice clears incompatible values in either order',()=>{
  const questions=registry.questions.filter(question=>question.auditVariant==='default' && question.multi);
  for (const question of questions) {
    const ordinary=question.choices.filter(([value])=>!['none','no','local','unknown','declined'].includes(value));
    const exclusives=question.choices.filter(([value])=>['none','no','local','declined'].includes(value));
    for (const [exclusive,exclusiveLabel] of exclusives) for (const [value,label] of ordinary) {
      const h=harness(question,{choice:[value],fields:{}});
      h.click(h.context.insuranceChoiceLabel(question,exclusive,exclusiveLabel));
      assert.deepEqual(Array.from(h.draft.choice),[exclusive],question.id+' '+exclusive+' must stand alone.');
      const again=harness(question,{choice:[exclusive],fields:{}});
      if (question.id==='T05') {
        const group=again.context.insuranceChoiceView(question,again.draft).items.find(item=>item.group && item.values.includes(value));
        if (group) again.click(group.label);
      }
      again.click(h.context.insuranceChoiceLabel(question,value,label));
      assert.deepEqual(Array.from(again.draft.choice),[value],question.id+' selecting an ordinary answer clears '+exclusive+'.');
    }
  }
});

test('existing assistance-program reports seed the full selected collection',()=>{
  const question=registry.questions.find(question=>question.id==='RC18' && question.auditVariant==='default');
  const h=harness(question);
  h.context.state.record.facts.RC18={value:{choice:'extra_help',programs:['medicaid','extra_help']},stale:false};
  h.context.drafts.delete(question.signature);
  assert.deepEqual(Array.from(h.draft.choice).sort(),['extra_help','medicaid']);
  h.context.state.record.facts.RC18.value.choice='declined';
  h.context.drafts.delete(question.signature);
  assert.deepEqual(Array.from(h.draft.choice),['declined'],'A later refusal does not display historical positive reports as a current selection.');
});

test('priorities cap is service-owned and prevents a fourth finite selection without losing the first three',()=>{
  const question=registry.questions.find(question=>question.id==='T10' && question.auditVariant==='default');
  assert.equal(question.max,3,'The active descriptor retains the approved choose-up-to-three meaning.');
  const h=harness(question);
  for (const label of ['Doctors and hospitals','Prescriptions','Total cost','Predictable costs']) h.click(label);
  assert.deepEqual(Array.from(h.draft.choice),['doctors','drugs','total_cost']);
  assert.equal(h.calls.length,0);
  assert.ok(h.notices.length,'The person must be told why the fourth answer was not selected.');
  h.click('Prescriptions');h.click('Predictable costs');
  assert.deepEqual(Array.from(h.draft.choice),['doctors','total_cost','bills']);
});

test('typed drafts block every finite answer and disclosure without silently replacing their text',()=>{
  for (const question of registry.questions.filter(question=>question.auditVariant==='all_fields')) {
    const h=harness(question), text='I want to ask about this before answering.';
    h.message.value=text;
    for (const button of [...h.buttons].filter(button=>button.textContent!=='Clear selection')) button.onclick();
    assert.equal(h.message.value,text);
    assert.deepEqual(Array.from(h.draft.choice),[]);
    assert.deepEqual(plain(h.draft.fields),{});
    assert.equal(h.draft.resolution ?? '','');
    assert.equal(h.calls.length,0);
  }
});

test('every direct current-insurance button closes an unrelated expansion without discarding a precise report',()=>{
  const question=registry.questions.find(question=>question.id==='T05' && question.auditVariant==='default');
  for (const group of ['former','medicare']) for (const value of ['employer','military','medicaid','none']) {
    const h=harness(question,{choice:[],fields:{},coverageGroup:group});
    const label=question.choices.find(([id])=>id===value)[1];
    h.click(h.context.insuranceChoiceLabel(question,value,label));
    assert.equal(h.draft.coverageGroup ?? '','',group+' must close after '+value+'.');
    assert.deepEqual(Array.from(h.draft.choice),[value]);
    assert.equal(h.calls.length,0);
    const view=h.context.insuranceChoiceView(question,h.draft);
    assert.equal(view.details.length,0,'No unrelated subtype question remains beneath a precise answer.');
  }
});
