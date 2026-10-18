import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {makeCase,updateProfile} from '../src/domain.mjs';
import {runAgent,replayAgent} from '../src/agent.mjs';
const live=process.argv.includes('--live');
const cases=JSON.parse(await readFile(new URL('./cases.json',import.meta.url),'utf8'));
if(live&&(process.env.ENABLE_OPENAI!=='1'||!process.env.OPENAI_API_KEY||!process.env.OPENAI_MODEL))throw new Error('Live eval requires ENABLE_OPENAI=1, OPENAI_API_KEY and OPENAI_MODEL. Uses synthetic cases and incurs API charges.');
const only=process.argv.find(x=>x.startsWith('--case='))?.slice(7);
if(only&&!cases.some(c=>c.id===only))throw new Error('Unknown evaluation case');
const report={mode:live?'openai':'scripted_replay',created_at:new Date().toISOString(),semantic_accuracy:'NOT GRADED: independent review required for each rubric',results:[]};
for(const c of cases.filter(c=>!only||c.id===only)){
 const state=makeCase(c.case_id);if(c.patch)updateProfile(state,c.patch);
 try{
  const run=live?await runAgent({state,message:c.message}):replayAgent({state,message:c.message});
  const checks={allowed_status:c.statuses.includes(run.answer.recommendation_status),context_read:run.trace.some(t=>t.name==='get_case_context'&&t.status==='ok'),comparison_read:!c.require_compare||run.trace.some(t=>t.name==='compare_options'&&t.status==='ok'),no_unsupported_selection:!c.forbid_option_selection||!run.answer.option_ids.length};
  const passed=Object.values(checks).every(Boolean);report.results.push({id:c.id,contract_checks_passed:passed,checks,semantic_review_required:true,review_rubric:c.review,run});console.log(`${passed?'PASS':'FAIL'} contract checks: ${c.id}; semantic review pending`);
 }catch(e){report.results.push({id:c.id,contract_checks_passed:false,error:e.message,semantic_review_required:true,review_rubric:c.review});console.log(`FAIL ${c.id}: ${e.message}`);}
}
const dir=new URL('../runs/',import.meta.url);await mkdir(dir,{recursive:true});const path=new URL(`eval-${live?'openai':'replay'}-${Date.now()}.json`,dir);await writeFile(path,JSON.stringify(report,null,2));
const passed=report.results.filter(x=>x.contract_checks_passed).length;console.log(`${passed}/${report.results.length} contract-check passes. This is not a semantic-quality or suitability score. Report: ${path.pathname}`);if(passed!==report.results.length)process.exitCode=1;
