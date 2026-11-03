'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {model,render,accept}=require('../web/identity-view.js');
const held=['published_display','personal_comparison','ranking','recommendation','quote','enrollment'];
const internal={capability:{state:'internal_research_available',audience:'internal_research'},held_purposes:held};

test('consumer and malformed authority never reveal source candidates or source selection counts',()=>{
  for(const capability of [{state:'held',audience:'consumer'}, {state:'internal_research_available',audience:'consumer'}]) {
    const view=model({capability,held_purposes:held,choice_token:'opaque',source:{year:2026},
      candidates:[{candidate_id:'one',label:'PRIVATE_SOURCE_NAME'}],preparation:{selected_count:9}});
    assert.equal(view.candidates.length,0);assert.equal(view.source,null);assert.equal(view.preparation,null);
    assert.ok(!JSON.stringify(view).includes('PRIVATE_SOURCE_NAME'));
  }
  assert.equal(model({...internal,held_purposes:['recommendation'],choice_token:'opaque',candidates:[{candidate_id:'one',label:'SOURCE'}]}).candidates.length,0);
});

test('current reported facts remain separate from source labels and scope',()=>{
  const view=model({...internal,items:[{item_id:'medicine-1',kind:'drug_product',state:'ready_for_identity_lookup',
    reported:{name:'Reported medicine',strength:'500mg',form:'Tablet'}}]});
  assert.equal(view.items[0].label,'Reported medicine');assert.match(view.items[0].reportedDetails,/500mg/);
  assert.equal(view.items[0].kind,'drug');assert.ok(view.items[0].searchable);
  assert.equal(model({...internal,items:[{item_id:'doctor-1',kind:'provider_site',reported:{practice:'Reported practice',city:'Reported city'}}]}).items[0].kind,'provider');
});

test('provider sites preserve structured name and distinct addresses without an automatic choice',()=>{
  const view=model({...internal,choice_token:'opaque',item_id:'doctor-1',candidates:[
    {candidate_id:'a',kind:'provider_site',label:[{given:['Maria'],family:'Lopez'}],site:{address:{line:['1 Public Street'],city:'Naples',state:'FL'}},selectable:true},
    {candidate_id:'b',kind:'provider_site',label:[{text:'Maria Lopez'}],site:{address:{line:['2 Public Street'],city:'Naples',state:'FL'}},selectable:true},
  ]});
  assert.equal(view.candidates.length,2);assert.equal(view.candidates[0].label,'Maria Lopez');
  assert.notEqual(view.candidates[0].details,view.candidates[1].details);
  assert.equal(view.choiceToken,'opaque');assert.equal(view.itemId,'doctor-1');
});

test('pack and unresolved source details cannot acquire an automatic selection action',()=>{
  const view=model({...internal,choice_token:'opaque',candidates:[{candidate_id:'pack',kind:'drug_product',
    label:'Retained source pack',selectable:false,details:{ingredient_strength_description:'Not supplied',dose_form:'Pack'}}]});
  assert.equal(view.candidates[0].selectable,false);assert.match(view.candidates[0].details,/Source form: Pack/);
});

test('entity discovery and site identity selection have distinct explicit actions',()=>{
  const view=model({...internal,choice_token:'opaque',candidates:[{candidate_id:'entity',kind:'provider_entity',label:'Source actor',
    selectable:false,site_lookup_available:true,selector:{entity_key:'source:key'}}]});
  assert.equal(view.candidates[0].siteLookup,true);assert.equal(view.candidates[0].selectable,false);
  assert.deepEqual(view.candidates[0].selector,{entity_key:'source:key'});
});

class Node {
  constructor(tag){this.tag=tag;this.children=[];this.text='';}
  append(...values){this.children.push(...values);}
  set textContent(value){this.text=String(value);}
}
const doc={createElement:tag=>new Node(tag)};
const all=node=>[node,...node.children.flatMap(all)];

test('literal markup stays text and source selection occurs only after its named button',()=>{
  const host=new Node('main');let selected=0;let returned=0;
  const section=render(host,{...internal,choice_token:'opaque',candidates:[{candidate_id:'a',kind:'drug_product',label:'<script>source text</script>',selectable:true}]},
    {document:doc,onSelect:()=>selected++,onReturn:()=>returned++});
  assert.equal(selected,0);assert.ok(!all(section).some(node=>node.tag==='script'));
  assert.ok(all(section).some(node=>node.text.includes('<script>')));
  all(section).find(node=>node.text==='Select this source identity').onclick();assert.equal(selected,1);
  all(section).find(node=>node.text==='Return to comparison preparation').onclick();assert.equal(returned,1);
});

test('continuation and live recheck are explicit and source limits remain visible',()=>{
  const host=new Node('main');let more=0;let refresh='';
  const section=render(host,{...internal,items:[{item_id:'doctor-1',kind:'provider_site',state:'selected_needs_source_recheck',reported:{practice:'Own report'}}],
    page:{has_more:true,next_after_ordinal:20},source:{year:2026,site_continuation:'not_supported_within_selected_window'}},
    {document:doc,onMore:()=>more++,onRefresh:id=>refresh=id});
  assert.ok(all(section).some(node=>node.text.includes('partial source result')));
  assert.ok(all(section).some(node=>node.text.includes('site limit')));
  all(section).find(node=>node.text==='Show more possible matches').onclick();assert.equal(more,1);
  all(section).find(node=>node.text==='Recheck selected source identity').onclick();assert.equal(refresh,'doctor-1');
});

test('top-level source gaps and entity/role continuation never lose the partial warning',()=>{
  for(const value of [{partial:{is_partial:true}},{page:{entities_have_more:true}},{page:{roles_have_more:true}}]) {
    const section=render(new Node('main'),{...internal,...value},{document:doc});
    assert.ok(all(section).some(node=>node.text.includes('partial source result')));
  }
});

test('retained periods and source qualifications remain inspectable without currentness inference',()=>{
  const section=render(new Node('main'),{...internal,choice_token:'opaque',page:{site_continuation:'not_supported_within_selected_window'},
    source:{year:2026},source_contexts:[{record_ref:'actor',source_native_context:{provider_period:{end:'2025-12-31'},qualifiers:{note:'Retain this exact qualification'}}}],
    candidates:[{candidate_id:'site',kind:'provider_site',label:'Source practice',context_refs:['actor'],source_periods:{entity:{end:'2025-12-31'}},selectable:true}]},{document:doc});
  assert.ok(all(section).some(node=>node.text.includes('2025-12-31')));
  assert.ok(all(section).some(node=>node.text.includes('Retain this exact qualification')));
  assert.ok(all(section).some(node=>node.text.includes('site limit')));
});

test('derived response preserves current reports, privacy, pause and drafts',()=>{
  const guide={preferences:{saveSensitive:false}},record={current:true},assessment={intakePaused:true};
  const state={continuation:'current',guide,record,assessment,draft:'unsent',identity:{items:[{item_id:'medicine-1',kind:'drug_product',reported:{name:'Own report'}}]}};
  accept(state,{continuation:'current',identity:{...internal,state:'explicitly_selected_source_identity',item_id:'medicine-1'},
    guide:{preferences:{saveSensitive:true}},record:{wrong:true},assessment:{intakePaused:false}});
  assert.equal(state.guide,guide);assert.equal(state.record,record);assert.equal(state.assessment,assessment);assert.equal(state.draft,'unsent');
  assert.equal(state.identity.items[0].state,'selected_needs_source_recheck');
  const current=state.identity;assert.throws(()=>accept(state,{continuation:'old',identity:internal}));assert.equal(state.identity,current);
});

test('an explicit selection is never described as a search with no matches',()=>{
  const selected={...internal,state:'explicitly_selected_source_identity',source:{year:2026},candidates:[]};
  assert.equal(model(selected).noMatch,false);
  assert.equal(model({...selected,state:'not_observed_in_selected_dictionary'}).noMatch,true);
});
