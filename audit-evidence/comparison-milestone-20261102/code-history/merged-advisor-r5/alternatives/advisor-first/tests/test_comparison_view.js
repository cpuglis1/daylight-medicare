'use strict';
const assert=require('node:assert/strict');
const test=require('node:test');
const {model,render,acceptReview}=require('../web/comparison-view.js');

test('held plan values, research units and trace never enter the preparation model',()=>{
  const out=model({units:[{display_name:'DO_NOT_RENDER',value:'$999'}],findings:[{value:'SECRET_HELD_VALUE'}],decision_record:{private:'PRIVATE_TRACE'},dimensions:[{dimension_id:'costs',label:'Costs'}],case_preparation:{baseline_reports:[]},preference_context:{priority_topics:['doctors']}});
  const text=JSON.stringify(out);assert.ok(!text.includes('DO_NOT_RENDER'));assert.ok(!text.includes('SECRET_HELD_VALUE'));assert.ok(!text.includes('PRIVATE_TRACE'));assert.deepEqual(out.priorities,['Doctors and hospitals']);assert.equal(out.dimensions[0].state,'Still needs evidence and review');
});
test('stale view suppresses baseline, priorities and connected markers',()=>{
  const out=model({status:'stale_binding',case_preparation:{baseline_reports:[{label:'Old',value:'OLD_VALUE'}]},preference_context:{priority_topics:['doctors']},research:{state:'connected_research_only'}});
  assert.equal(out.baseline.length,0);assert.equal(out.priorities.length,0);assert.equal(out.research,null);assert.match(out.notice,/fresh check/);
});
test('reported absence differs from missing or unaccepted source evidence',()=>{
  const base={case_preparation:{},dimensions:[{dimension_id:'drug_coverage',label:'Medicines'}]};
  assert.equal(model({...base,findings:[{dimension_id:'drug_coverage',result:'not_applicable',reason_codes:['REPORTED_REQUIREMENT_ABSENT']}]}).dimensions[0].state,'You reported no items for this check');
  assert.equal(model({...base,findings:[{dimension_id:'drug_coverage',result:'unresolved',reason_codes:['SOURCE_MISSING']}]}).dimensions[0].state,'Still needs evidence and review');
});
test('rendering source-like markup creates literal text and a working Return control',()=>{
  class Node{constructor(tag){this.tag=tag;this.children=[];}append(...values){this.children.push(...values);}set textContent(value){this.text=value;}}
  const doc={createElement:tag=>new Node(tag)},host=new Node('main');let returned=false;
  const section=render(host,{case_preparation:{baseline_reports:[{label:'Current coverage',value:'<img src=x onerror=bad()>employer'}]},dimensions:[]},{document:doc,onReturn:()=>{returned=true;}});
  const nodes=node=>[node,...node.children.flatMap(nodes)];
  assert.ok(nodes(section).some(node=>String(node.text).includes('<img')));assert.ok(!nodes(section).some(node=>node.tag==='img'));
  nodes(section).find(node=>node.tag==='button').onclick();assert.equal(returned,true);
});
test('review replaces only derived data, preserving current privacy, presentation and pause',()=>{
  const state={continuation:'fixture:current',guide:{preferences:{saveGuide:false,saveSensitive:false},flow:{guideOpen:false}},record:{current:'fixture'},assessment:{nextQuestion:null,intakePaused:true},comparison:{old:true}};
  const guide=state.guide,record=state.record,assessment=state.assessment;
  acceptReview(state,{continuation:'fixture:current',comparison:{fresh:true},guide:{preferences:{saveGuide:true,saveSensitive:true}},assessment:{intakePaused:false}});
  assert.equal(state.guide,guide);assert.equal(state.record,record);assert.equal(state.assessment,assessment);
  assert.equal(state.guide.preferences.saveSensitive,false);assert.equal(state.guide.flow.guideOpen,false);assert.equal(state.assessment.intakePaused,true);
  assert.deepEqual(state.comparison,{fresh:true});
  assert.throws(()=>acceptReview(state,{continuation:'fixture:older',comparison:{stale:true}}));assert.deepEqual(state.comparison,{fresh:true});
});
