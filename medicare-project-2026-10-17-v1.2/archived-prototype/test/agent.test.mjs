import test from 'node:test';
import assert from 'node:assert/strict';
import {makeCase,comparison} from '../src/domain.mjs';
import {runAgent,validateAnswer,openAITransport,replayAgent} from '../src/agent.mjs';
const answer=(overrides={})=>({message:'A fictional comparison only.',evidence_ids:['E-PROFILE'],option_ids:[],recommendation_status:'educational',next_question:null,proposed_profile_updates:[],...overrides});
test('Wrapper sends strict server tools, stateless configuration and returns tool outputs with reasoning',async()=>{
 let round=0;const requests=[];
 const transport=async payload=>{requests.push(structuredClone(payload));round++;return round===1?{status:'completed',output:[{type:'reasoning',id:'reason-1',encrypted_content:'test-reasoning-token'},{type:'function_call',name:'get_case_context',arguments:'{}',call_id:'c1'}],usage:{input_tokens:10,output_tokens:2,total_tokens:12}}:{status:'completed',output:[{type:'message',content:[{type:'output_text',text:JSON.stringify(answer())}]}],usage:{input_tokens:20,output_tokens:5,total_tokens:25}};};
 const run=await runAgent({state:makeCase(),message:'Explain this case.',model:'test-model',transport});assert.equal(run.usage.total_tokens,37);assert.equal(requests[0].store,false);assert.equal(requests[0].parallel_tool_calls,false);assert.equal(requests[0].text.format.strict,true);assert(requests[1].input.some(x=>x.type==='reasoning'&&x.encrypted_content==='test-reasoning-token'));assert(requests[1].input.some(x=>x.type==='function_call_output'&&x.call_id==='c1'));assert.equal(run.mode,'openai');
});
test('Missing current-context tool read is rejected even when JSON is structurally correct',async()=>{await assert.rejects(()=>runAgent({state:makeCase(),message:'Hi',model:'test',transport:async()=>({status:'completed',output:[{type:'message',content:[{type:'output_text',text:JSON.stringify(answer({evidence_ids:[]}))}]}]})}),/profile was not inspected/);});
test('Invented evidence and stale-option readiness claims are blocked',()=>{const s=makeCase(),tools=new Set(['get_case_context','compare_options']);assert.throws(()=>validateAnswer(answer({evidence_ids:['FAKE']}),s,new Set(),tools),/uninspected/);assert.throws(()=>validateAnswer(answer({option_ids:['DEMO-MA-PPO'],recommendation_status:'ready_in_fixture'}),s,new Set(['E-PROFILE']),tools),/Readiness/);});
test('Incomplete API output cannot produce a partially actionable answer',async()=>{await assert.rejects(()=>runAgent({state:makeCase(),message:'Hi',model:'test',transport:async()=>({status:'incomplete',output:[]})}),/no partial recommendation/);});
test('Runaway tool loop terminates at a bounded round limit',async()=>{await assert.rejects(()=>runAgent({state:makeCase(),message:'Hi',model:'test',maxRounds:2,transport:async()=>({status:'completed',output:[{type:'function_call',name:'get_case_context',arguments:'{}',call_id:'c'}]})}),/bounded turn limit/);});
test('Unknown tool receives an error instead of executing arbitrary functionality',async()=>{
 let n=0;const transport=async payload=>{if(n++===0)return {status:'completed',output:[{type:'function_call',name:'submit_application',arguments:'{}',call_id:'bad'},{type:'function_call',name:'get_case_context',arguments:'{}',call_id:'good'}]};assert(payload.input.some(x=>x.call_id==='bad'&&x.output?.includes('Tool not allowed')));return {status:'completed',output:[{type:'message',content:[{type:'output_text',text:JSON.stringify(answer())}]}]};};
 const r=await runAgent({state:makeCase(),message:'Submit a plan',model:'test',transport});assert.equal(r.trace[0].status,'error');
});
test('Transport key remains an Authorization header and provider error bodies are withheld',async()=>{
 const secret='TEST-KEY-DO-NOT-EXPORT';let options;
 await assert.rejects(()=>openAITransport({model:'test'},{apiKey:secret,fetcher:async(url,o)=>{assert.equal(url,'https://api.openai.com/v1/responses');options=o;return {ok:false,status:429,headers:new Headers({'x-request-id':'test-request'})};}}),/OpenAI HTTP 429/);assert.equal(options.headers.Authorization,`Bearer ${secret}`);assert(!options.body.includes(secret));
});
test('Replay distinguishes annual review from an enrollment instruction',()=>{const r=replayAgent({state:makeCase(),message:'Do I need to re-enroll every year?'});assert.equal(r.answer.recommendation_status,'educational');assert.match(r.answer.message,/does not itself guarantee/);});
test('No comparison can create enrollment capability',()=>{for(const id of ['ready','doctor','underwriting','medication','no-market'])assert.equal(comparison(makeCase(id)).enrollment_available,false);});
