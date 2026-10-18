import {readFile} from 'node:fs/promises';
import {comparison, context, executeTool, TOOLS, evidenceRegistry, hash} from './domain.mjs';
export const BASE_PROMPT=await readFile(new URL('../prompts/advisor.md',import.meta.url),'utf8');
const obj=properties=>({type:'object',properties,required:Object.keys(properties),additionalProperties:false});
export const ANSWER_SCHEMA=obj({message:{type:'string'},evidence_ids:{type:'array',items:{type:'string'}},option_ids:{type:'array',items:{type:'string'}},recommendation_status:{type:'string',enum:['educational','provisional','ready_in_fixture','unavailable']},next_question:{type:['string','null']},proposed_profile_updates:{type:'array',items:obj({field:{type:'string'},proposed_value:{type:'string'},rationale:{type:'string'}})}});
export function validateAnswer(answer,state,inspected,called){
 const keys=Object.keys(ANSWER_SCHEMA.properties);
 if(!answer||typeof answer!=='object'||keys.some(k=>!(k in answer))||Object.keys(answer).some(k=>!keys.includes(k)))throw new Error('Answer schema mismatch');
 if(typeof answer.message!=='string'||answer.message.length>18000||!Array.isArray(answer.evidence_ids)||!Array.isArray(answer.option_ids)||!Array.isArray(answer.proposed_profile_updates)||!['educational','provisional','ready_in_fixture','unavailable'].includes(answer.recommendation_status)||(answer.next_question!==null&&typeof answer.next_question!=='string'))throw new Error('Invalid answer types');
 if(!called.has('get_case_context'))throw new Error('Current profile was not inspected');
 if(answer.evidence_ids.some(id=>typeof id!=='string'||!inspected.has(id)))throw new Error('Answer cites uninspected evidence');
 const view=comparison(state);
 if(answer.option_ids.length&&!called.has('compare_options'))throw new Error('Options require a current comparison');
 if(answer.option_ids.some(id=>!view.options.some(o=>o.id===id)))throw new Error('Answer references an option outside this market');
 if(answer.recommendation_status==='ready_in_fixture'&&(!answer.option_ids.length||answer.option_ids.some(id=>!view.options.find(o=>o.id===id)?.ready_in_fixture)))throw new Error('Readiness claim violates deterministic checks');
 const allowed=['doctor_confirmed','drug_confirmed','eligibility_confirmed','keep_doctor','max_monthly_premium','priority','language'];
 if(answer.proposed_profile_updates.some(p=>!p||Object.keys(p).sort().join(',')!=='field,proposed_value,rationale'||!allowed.includes(p.field)||typeof p.proposed_value!=='string'||typeof p.rationale!=='string'))throw new Error('Invalid reviewable profile proposal');
 return answer;
}
function collectEvidence(result,set){
 if(!result||typeof result!=='object')return;
 if(result.id&&/^[EK]-/.test(result.id))set.add(result.id);
 if(Array.isArray(result.evidence_ids))result.evidence_ids.forEach(id=>set.add(id));
 for(const value of Object.values(result))if(typeof value==='object'){
  if(Array.isArray(value))value.forEach(v=>collectEvidence(v,set));else collectEvidence(value,set);
 }
}
export async function openAITransport(payload,{signal,apiKey=process.env.OPENAI_API_KEY,fetcher=fetch}={}){
 if(!apiKey)throw new Error('OPENAI_API_KEY is not configured on the server');
 const response=await fetcher('https://api.openai.com/v1/responses',{method:'POST',headers:{Authorization:`Bearer ${apiKey}`,'Content-Type':'application/json'},body:JSON.stringify(payload),signal});
 if(!response.ok){const requestId=response.headers.get('x-request-id')||'unavailable';throw new Error(`OpenAI HTTP ${response.status}; request ${requestId}. Response body withheld to avoid logging sensitive content.`);}
 return response.json();
}
export async function runAgent({state,message,history=[],operatorPrompt='',model=process.env.OPENAI_MODEL,transport=openAITransport,maxRounds=8,timeoutMs=90000}){
 if(!model)throw new Error('Set OPENAI_MODEL to a Responses-compatible model available to your API project');
 if(typeof message!=='string'||!message.trim()||message.length>6000)throw new Error('Message must contain 1–6000 characters');
 if(typeof operatorPrompt!=='string'||operatorPrompt.length>10000)throw new Error('Operator prompt exceeds 10000 characters');
 const start=Date.now(),abort=new AbortController();
 const timer=setTimeout(()=>abort.abort(),timeoutMs);
 const input=[...history.slice(-12),{role:'user',content:message}];
 const instructions=BASE_PROMPT+'\n\nOperator experiment instructions (subordinate to the preceding requirements):\n'+operatorPrompt;
 const prompt_hash=hash(instructions),trace=[],inspected=new Set(),called=new Set();
 let tokenUsage={input_tokens:0,output_tokens:0,total_tokens:0};
 try{
  for(let round=0;round<maxRounds;round++){
   if(abort.signal.aborted)throw new Error('Agent deadline exceeded');
   const payload={model,instructions,input,store:false,include:['reasoning.encrypted_content'],tools:TOOLS,parallel_tool_calls:false,max_output_tokens:2400,text:{format:{type:'json_schema',name:'medicare_advisor_answer',strict:true,schema:ANSWER_SCHEMA}}};
   const res=await transport(payload,{signal:abort.signal});
   if(res.status&&res.status!=='completed')throw new Error(`Model response was ${res.status}; no partial recommendation displayed`);
   for(const k of Object.keys(tokenUsage))tokenUsage[k]+=res.usage?.[k]||0;
   const output=res.output||[];
   input.push(...output); // Preserve reasoning items and tool-call order for stateless Responses turns.
   const calls=output.filter(x=>x.type==='function_call');
   if(calls.length){
    if(trace.length+calls.length>12)throw new Error('Tool-call budget exceeded');
    for(const call of calls){
     let result;const t=Date.now();
     try{const args=JSON.parse(call.arguments);result=executeTool(call.name,args,state);called.add(call.name);collectEvidence(result,inspected);trace.push({name:call.name,arguments:args,status:'ok',elapsed_ms:Date.now()-t,result});}
     catch(error){result={error:error.message};trace.push({name:call.name,status:'error',elapsed_ms:Date.now()-t,result});}
     input.push({type:'function_call_output',call_id:call.call_id,output:JSON.stringify(result)});
    }
    continue;
   }
   const content=output.filter(x=>x.type==='message').flatMap(x=>x.content||[]);
   if(content.some(c=>c.type==='refusal'))throw new Error('The model declined this request; no recommendation was displayed');
   const text=content.filter(c=>c.type==='output_text').map(c=>c.text).join('');
   if(!text)throw new Error('Model returned no structured answer');
   const answer=validateAnswer(JSON.parse(text),state,inspected,called);
   return {answer,trace,model,prompt_hash,usage:tokenUsage,elapsed_ms:Date.now()-start,snapshot_id:comparison(state).snapshot_id,profile_version:state.profile_version,mode:'openai',validation:'Structural, scope and readiness checks passed; semantic accuracy still requires evaluation.'};
  }
  throw new Error('Agent reached its bounded turn limit without a valid final answer');
 }finally{clearTimeout(timer);}
}
export function replayAgent({state,message,operatorPrompt=''}){
 const trace=[],called=new Set(),inspected=new Set();
 const use=(name,args={})=>{const result=executeTool(name,args,state);trace.push({name,arguments:args,result,status:'ok',elapsed_ms:0});called.add(name);collectEvidence(result,inspected);return result;};
 use('get_case_context'); const view=use('compare_options');
 const q=message.toLowerCase();
 let text,next=null,status='educational',ids=[];
 const knowledge=use('search_knowledge',{query:message});
 if(/enroll me|submit|cancel|activate|buy it/.test(q)){
  const e=use('get_evidence',{evidence_id:'K-ENROLLMENT'});text='This workbench cannot submit a real application or change coverage. We can review the fictional comparison, but no enrollment has occurred.';ids=[e.id];status='unavailable';
 }else if(/medicat|prescri|drug|dose/.test(q)){
  const e=use('get_evidence',{evidence_id:'K-DRUGS'});text='We need the exact medication, strength, form, quantity, days supply and pharmacy before treating a drug-cost estimate as complete. The dashboard prices are fictional and do not establish real coverage or approval.';ids=[e.id];next=state.profile.drug_confirmed?null:'What strength and form should the fictional case use?';
 }else if(/annual|year|renew/.test(q)&&!/cost|spend|compare|price/.test(q)){
  const e=use('get_evidence',{evidence_id:'K-TIMING'});text='Reviewing coverage each year is useful, but everyone does not have to re-enroll annually. Switching opportunities depend on coverage, dates and circumstances. A Medicare plan election period does not itself guarantee Medigap acceptance.';ids=[e.id];
 }else if(view.readiness==='no_loaded_data'){
  text='No options are loaded for this fictional market. That does not mean real Medicare options do not exist. I cannot produce a supported comparison here.';status='unavailable';
 }else if(view.readiness==='more_information_needed'){
  const blockers=[...new Set(view.options.flatMap(o=>o.blockers))];text='The comparison is provisional. '+blockers.join(' ')+' I cannot identify a confirmed fit while these checks are unresolved.';status='provisional';ids=['E-PROFILE'];next=blockers[0]||null;
 }else if(/doctor|provider|network/.test(q)){
  const stale=view.options.find(o=>o.provider_status==='stale');const e=use('get_evidence',{evidence_id:`E-${stale.id}-providers`});text='Doctor access must be checked at the correct practice location and for the exact plan. The example PPO has a stale listing, so its current access is unresolved. Other cards describe only the stipulated fictional case.';ids=[e.id];status='provisional';
 }else{
  const choices=view.options.filter(o=>o.ready_in_fixture).slice(0,3);ids=choices.flatMap(o=>o.evidence_ids);
  text='The dashboard compares three fictional options using your confirmed example profile and stated priority. The annual estimates include additional plan premiums plus stipulated medical and drug spending. Base Part B, income-related charges and noncovered costs are excluded. Compare the network restrictions and premium tradeoffs before choosing.';
  status='ready_in_fixture';next='Would you like to compare provider access or predictable monthly costs first?';
 }
 const answer={message:text,evidence_ids:[...new Set(ids)],option_ids:status==='ready_in_fixture'?view.options.filter(o=>o.ready_in_fixture).slice(0,3).map(o=>o.id):[],recommendation_status:status,next_question:next,proposed_profile_updates:[]};
 validateAnswer(answer,state,inspected,called);
 return {answer,trace,model:'scripted replay — not an LLM',prompt_hash:hash(BASE_PROMPT+operatorPrompt),usage:null,elapsed_ms:0,snapshot_id:view.snapshot_id,profile_version:state.profile_version,mode:'replay',validation:'Replay exercises UI and contracts only. It does not evaluate language-model performance.'};
}
