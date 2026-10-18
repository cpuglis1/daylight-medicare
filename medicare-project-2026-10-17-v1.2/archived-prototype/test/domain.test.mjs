import test from 'node:test';
import assert from 'node:assert/strict';
import {makeCase,comparison,updateProfile,executeTool} from '../src/domain.mjs';
import {validateCatalog} from '../tools/ingest.mjs';
test('Bundle includes separate PDP premium once and uses exact integer-cent totals',()=>{
 const g=comparison(makeCase()).options.find(o=>o.id==='DEMO-BUNDLE-G');
 assert.equal(g.monthly_premium_cents,21000);assert.equal(g.annual_premium_cents,252000);assert.equal(g.estimated_annual_total_cents,315600);assert.match(g.cost_scope,/excludes base Part B/);
});
test('Zero-premium plan is excluded when its doctor conflicts with a hard preference',()=>{
 const o=comparison(makeCase()).options.find(o=>o.id==='DEMO-MA-ZERO');assert.equal(o.excluded,true);assert.equal(o.ready_in_fixture,false);assert.equal(o.estimated_annual_total_cents,134000);
});
test('Stale provider listing cannot be readiness-approved',()=>{const o=comparison(makeCase()).options.find(o=>o.id==='DEMO-MA-PPO');assert.equal(o.provider_status,'stale');assert.equal(o.ready_in_fixture,false);assert.match(o.blockers.join(' '),/Verify/);});
for(const id of ['doctor','medication','underwriting'])test(`Missing material fact blocks all definitive options: ${id}`,()=>{const s=comparison(makeCase(id));assert.equal(s.readiness,'more_information_needed');assert.equal(s.options.some(o=>o.ready_in_fixture),false);});
test('Unknown market returns no loaded data without using another county',()=>{const s=comparison(makeCase('no-market'));assert.equal(s.readiness,'no_loaded_data');assert.equal(s.options.length,0);assert.equal(s.market.coverage_complete,false);});
test('Confirmed preference change creates a new comparison version and changes feasible set',()=>{
 const s=makeCase(),old=comparison(s);updateProfile(s,{keep_doctor:false,max_monthly_premium:0});const next=comparison(s);assert.notEqual(old.snapshot_id,next.snapshot_id);assert.equal(next.profile_version,2);assert.deepEqual(next.options.filter(o=>o.ready_in_fixture).map(o=>o.id),['DEMO-MA-ZERO']);
});
test('Profile validation rejects unknown authority and invalid numeric values atomically',()=>{const s=makeCase(),before=structuredClone(s);assert.throws(()=>updateProfile(s,{enrollment_authorized:true}));assert.throws(()=>updateProfile(s,{max_monthly_premium:NaN}));assert.deepEqual(s,before);});
test('Tools are read-only, reject arbitrary names and refuse out-of-market access',()=>{const s=makeCase(),before=structuredClone(s);executeTool('compare_options',{},s);assert.deepEqual(s,before);assert.throws(()=>executeTool('submit_application',{},s));assert.throws(()=>executeTool('get_option_details',{option_id:'REAL-PLAN'},s));assert.throws(()=>executeTool('compare_options',{user_id:'other-person'},s));});
const manifest={source_id:'test',source_release:'v1',benefit_year:2027,expected_records:1,rights:{ingest:true},synthetic:true};
const row={plan_version_id:'x',source_id:'test',source_release:'v1',source_record_id:'r1',benefit_year:2027,plan_type:'mapd',service_area_codes:['DEMO-001'],monthly_premium_cents:0};
test('Ingestion refuses duplicate identities, wrong years, missing rights and count loss',()=>{
 assert.equal(validateCatalog([row],manifest).passed,true);
 assert.equal(validateCatalog([row,row],{...manifest,expected_records:2}).passed,false);
 assert.equal(validateCatalog([{...row,benefit_year:2026}],manifest).passed,false);
 assert.equal(validateCatalog([] ,manifest).passed,false);
 assert.throws(()=>validateCatalog([row],{...manifest,rights:{ingest:false}}));
});
test('25,000 canonical synthetic records validate without conflating rate cells with unique products',()=>{
 const rows=Array.from({length:25000},(_,i)=>({...row,plan_version_id:`synthetic-${i}`,source_record_id:`row-${i}`}));const r=validateCatalog(rows,{...manifest,expected_records:25000});assert.equal(r.passed,true);assert.equal(r.unique_plan_versions,25000);assert.equal(r.synthetic,true);
});
