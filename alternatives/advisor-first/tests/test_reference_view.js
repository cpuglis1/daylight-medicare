'use strict';
const assert=require('node:assert/strict');
const test=require('node:test');
const {render}=require('../web/reference-view.js');

const offering='2026:H0000:001:000';
const heldPurposes=['published_display','personal_comparison','ranking','recommendation','quote','enrollment'];
// Fictional renderer transport only; no fixture establishes actual acceptance.
function fixture() {
  const entry={id:'fixture:amount',offering_id:offering,field:'Fictional hospital day-band amount',kind:'published_source_value',value:'0',unit:'USD/day',basis:'Fictional INN, days 1–5 only',qualifications:['Fictional network qualification','Fictional exception remains attached'],scope_warning:'Not a personal charge',carrier_evidence:[{document_sha256:'f'.repeat(64),pdf_page:7,text:'Fictional evidence quote'}],CMS_source:{member:'fixture.json',pointer:'/fixture/band/amount'},technical_context:{activation:'fixture:parent',empty:null,zero:0,flag:false},unexpected_original_field:{retained:['complete','verbatim']}};
  return {purpose:'reference_lookup',audience:'internal_research_workspace',
    reference:{package_id:'L03-PUBLISHED-COLLIER-2026-bounded-r4',mode:'accepted_bounded_published_reference',accepted_for_reference:true,offering:{offering_id:offering,carrier_document_state:'matched_for_research',accepted:false,consumer_usable:false},entries:[entry],related_reference_entries:[],holds:[{issue_id:'fixture:held',offering_id:offering,value:null,state:'unknown_held',remaining_gap_id:'fixture:gap',carrier_evidence_ids:['fixture:quote']}],scope:{whole_L03_complete:false,all_market_complete:false,personal_total:false}},
    accepted_dispositions:[{id:'fixture:disposition',wording_for_review:'Fictional conservative disposition'}],review_receipt:{receipt:'Fictional renderer test receipt'},binding:{manifest_sha256:'fixture:manifest'},authority:{reference_lookup:{state:'accepted_exact_subset'},...Object.fromEntries(heldPurposes.map(purpose=>[purpose,{state:'held'}]))},limitations:['Internal fictional reference renderer test only']};
}
class Node {
  constructor(tag,doc){this.tag=tag;this.ownerDocument=doc;this.children=[];this._text='';}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this._text='';this.children=[...nodes];}
  set textContent(value){this._text=String(value);this.children=[];}
  get textContent(){return this._text+this.children.map(node=>typeof node==='string'?node:node.textContent).join('');}
  set innerHTML(value){throw Error('Unsafe HTML sink used: '+value);}
}
function host(){const doc={createElement:tag=>new Node(tag,doc)};return new Node('section',doc);}
const nodes=node=>[node,...node.children.flatMap(child=>typeof child==='string'?[]:nodes(child))];
const rawObjects=node=>nodes(node).filter(child=>child.tag==='pre').map(child=>JSON.parse(child.textContent));

test('all entry fields, exact units, conditions, qualifications and evidence remain inspectable',()=>{
  const payload=fixture(),original=structuredClone(payload),target=host();render(target,payload,offering);
  assert.ok(target.textContent.includes('Published source value: 0 USD/day'));
  assert.ok(target.textContent.includes('Fictional INN, days 1–5 only'));
  for(const qualification of payload.reference.entries[0].qualifications)assert.ok(target.textContent.includes(qualification));
  assert.deepEqual(rawObjects(target).find(value=>value.id==='fixture:amount'),original.reference.entries[0]);
  assert.deepEqual(payload,original);
  assert.ok(target.textContent.includes('Full L03 and personal comparisons remain incomplete'));
});
test('single amount keeps related endpoints and native schedule ordering',()=>{
  const payload=fixture(),target=host();
  payload.reference.related_reference_entries=[
    {id:'fixture:begin',field:'Fictional first day',kind:'published_source_value',value:'1',unit:'day',qualifications:['Fictional paired endpoint'],native_condition:{same_schedule:'fixture:amount'}},
    {id:'fixture:end',field:'Fictional last day',kind:'published_source_value',value:'5',unit:'day',qualifications:['Fictional paired endpoint'],native_condition:{same_schedule:'fixture:amount'}}];
  render(target,payload,offering);
  const entries=rawObjects(target).filter(value=>value.id?.startsWith('fixture:'));
  assert.deepEqual(entries,[payload.reference.entries[0],...payload.reference.related_reference_entries]);
  assert.ok(target.textContent.includes('Related reference schedules and context'));
});
test('restricted zero-entry offering retains historical status without implying noncoverage',()=>{
  const payload=fixture(),target=host();payload.reference.entries=[];
  payload.reference.offering.carrier_document_state='restricted';
  render(target,payload,offering);
  assert.ok(target.textContent.includes('neither noncoverage nor current document availability'));
  const status=rawObjects(target).find(value=>value.offering);
  assert.deepEqual(status,{offering:payload.reference.offering,scope:payload.reference.scope});
  assert.equal(status.offering.accepted,false);assert.equal(status.offering.consumer_usable,false);
});
test('masked holds, exact receipt and dispositions survive without disputed scalar values',()=>{
  const payload=fixture(),target=host();render(target,payload,offering);
  const raw=rawObjects(target);
  assert.deepEqual(raw.find(Array.isArray),payload.reference.holds);
  assert.ok(target.textContent.includes('unknown_held'));
  assert.ok(raw.some(value=>Array.isArray(value)&&value[0]?.id==='fixture:disposition'));
  assert.deepEqual(raw.find(value=>value.review_receipt).review_receipt,payload.review_receipt);
  assert.ok(heldPurposes.every(purpose=>raw.find(value=>value.authority).authority[purpose].state==='held'));
});
test('mismatched scope or broader permission cannot replace a prior exact view',()=>{
  const changes=[p=>p.purpose='published_display',p=>p.audience='consumer',
    p=>p.reference.package_id='different-package',p=>p.reference.mode='research_pending_review',
    p=>p.reference.accepted_for_reference=false,p=>p.reference.offering.offering_id='2026:H0000:999:000',
    ...heldPurposes.map(purpose=>p=>p.authority[purpose].state='accepted')];
  for(const change of changes){const payload=fixture(),target=host();target.textContent='prior exact view';change(payload);
    assert.throws(()=>render(target,payload,offering));assert.equal(target.textContent,'prior exact view');}
});
test('unmasked disputed values fail closed before replacing an exact view',()=>{
  for(const change of [{value:'DO_NOT_RENDER_DISPUTED_AMOUNT'},{state:'accepted'}]){
    const payload=fixture(),target=host();target.textContent='prior exact view';
    Object.assign(payload.reference.holds[0],change);
    assert.throws(()=>render(target,payload,offering));
    assert.equal(target.textContent,'prior exact view');
  }
});
test('source-like markup is literal text in summaries, qualifications and raw evidence',()=>{
  const payload=fixture(),target=host(),markup='<img src=x onerror="throw 1"><script>BAD()</script>';
  payload.reference.entries[0].field=markup;payload.reference.entries[0].qualifications=[markup];
  payload.reference.entries[0].carrier_evidence[0].text=markup;
  payload.reference.holds[0].carrier_evidence_ids=[markup];
  render(target,payload,offering);
  assert.ok(target.textContent.includes(markup));
  assert.ok(!nodes(target).some(node=>['img','script','iframe'].includes(node.tag)));
  assert.equal(rawObjects(target).find(value=>value.id==='fixture:amount').carrier_evidence[0].text,markup);
});
