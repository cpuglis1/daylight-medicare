/* Real Chromium + real handlers. Fictional local transport. Every action is
   flushed to disk; only the disposable origin is allowed to receive requests. */
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '../../..');
const runtime = JSON.parse(fs.readFileSync('/private/tmp/daylight-behavioral-runtime.json'));
const base = runtime.url;
const output = path.resolve(process.argv[2] || path.join(root,'audit-evidence/behavioral-fixes-20261114/browser'));
const only = process.argv[3];
const driverHash=crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex');
const profiles = JSON.parse(fs.readFileSync(path.join(root,'docs/evaluations/behavioral-journeys-2026-11-14/profiles.json'))).profiles;
const S = text => ['say',text], P = target => ['plans',target], C = label => ['click',label];
const details = ['detail'], back = ['back'], drawer = ['drawer'], hide = ['hide'], auto = ['answer_checks'];
const cases = {
 BJ01:[P('paths'),drawer,S('Is a supplement the same thing as Advantage?'),hide,back,
  S('I checked: I turn 65 in December 2026, not November.'),S('So I choose either Advantage or Original Medicare, and Medigap is optional with Original?'),
  S('I have neither Part A nor Part B. I live in 34103. I am not receiving Social Security. I have a marketplace policy and no job coverage.'),
  S('I am not picking a policy today. Tell me the next steps to get A and B started.'),P('ab'),['guide'],back],
 BJ02:[S('I understand the basics. Can we go straight to the prices?'),
  S('I am 68, male, and do not use tobacco. I have Parts A and B, my Plan G and a separate drug plan.'),P('supplement'),details,['close_detail'],drawer,
  S('Does seeing this price mean I can definitely switch?'),hide,back,
  S('I checked my home ZIP: it is 34102, not 34103.'),P('supplement'),back,
  S('I am just researching. Keep my current Plan G for now; please summarize what I must confirm before switching.')],
 BJ03:[S('Lowest total cost using my pharmacy. I live in 34103. I have Parts A and B, my Plan G and a separate drug plan.'),
  S('I take metformin 500 mg tablets, 30 tablets every 30 days. Harbor Pharmacy at 1 Test Lane, retail. I have no help with drug costs.'),auto,
  S('The lowest premium is always cheapest, right?'),P('part-d'),details,['close_detail'],drawer,S('What did you count in these costs?'),hide,back,
  S('Actually use Grove Pharmacy at 2 Test Lane, not Harbor.'),auto,P('part-d'),back,
  S('You checked the drug list, so is this an exact price at my store?'),S('Keep my Plan G. For the drug plan, summarize the comparison and anything I still need to check.')],
 BJ04:[S('It is a Medicare Advantage HMO, with drug coverage. I am 71 in 34104. Both A and B have been active since 2020.'),
  S('I take insulin glargine and apixaban 5 mg tablets. Put the Advantage plans in order by what my drugs cost.'),P('advantage'),
  C('Original Medicare'),['medical_costs'],drawer,S('Would switching to Original Medicare let me use any doctor? I am only exploring, not choosing it.'),hide,C('Medicare Advantage'),back,
  S('Back to comparing my HMO drug costs. I do not know the insulin quantity or refill schedule. Leave that open. If the pharmacy is preferred, are all medicines cheap?'),
  S('What do I need from the box to finish this comparison? Please summarize what is still open.')],
 BJ05:[S('I have a marketplace policy until Parts A and B start December 2026. I live in 34103.'),
  S('My doctors are Dr. Nera Vale at Fictional Harbor Clinic; Dr. Tomas Reed at Fictional Heart Group.'),
  S('Why does the office matter if it is the same doctor?'),S('Please check both doctors.'),auto,
  S('I see Tomas Reed at 10 Test Lane in Naples, not the Fort Myers office. Keeping both doctors matters more than price.'),auto,
  P('paths'),C('Medicare Advantage'),['ma_list'],details,['close_detail'],C('Original Medicare'),back,
  S('Original Medicare and an Advantage network use the same doctor check?'),S('Give me a side-by-side doctor summary. I am not choosing yet.')],
 BJ06:[S('Mom has A and B, Plan G and a separate drug plan. She takes levothyroxine 50 mcg tablets, 30 tablets every 30 days. Harbor Pharmacy at 1 Test Lane delivers them.'),auto,
  P('part-d'),details,['close_detail'],drawer,S('By the way I live in Virginia and I am 43, ZIP 22201. Can you help me too?'),
  S('Let us stay with Mom for now.'),S('If I click a plan, am I enrolling her?'),hide,back,
  S('She does not know whether she gets assistance. Leave that open.'),S('Summarize this for Mom to review here. Do not send it anywhere or sign her up.')],
 BJ07:[S('I have my current employer group insurance, with 240 employees. I turn 65 in December 2026. Neither A nor B, no Social Security and no HSA. I live in 34103.'),
  P('paths'),C('Medicare Advantage'),['ma_list'],details,['close_detail'],back,
  S('That is a lecture. Give me one plan name.'),S('When I retire I will have all year to sign up, right?'),
  S('I will keep my work coverage for now. What do I confirm before deciding about Part B?')],
 BJ08:[S('I am 66 in 34102. I have Part A only, no Part B. Please open the Part B sign-up guide.'),P('ab'),['guide'],drawer,
  S('Can I just use this guide next February?'),hide,back,
  S('To be clear, I stopped working August 31, 2026. This is COBRA, which ends February 28, 2027.'),P('ab'),['guide'],back,
  S('So the COBRA end date is what starts my Part B deadline?'),S('Give me the next action for Part B and what dates I need to confirm.')],
 BJ09:[P('paths'),C('Original Medicare'),['medical_costs'],drawer,
  S('Why are you asking for my sex and tobacco use? I have not asked for a quote.'),S('Skip personal details. I do not want to answer that.'),hide,C('Original Medicare'),back,
  S('Original Medicare means I must buy a supplement?'),S('That is enough for today. I am undecided. Please give me a short recap.')],
 BJ10:[S('I am 69. I have a Medicare Advantage PPO. I have Parts A and B. My doctor is Dr. Nera Vale at 1 Test Lane. I take no medicines.'),auto,
  ['draft','Does that include my specialist?'],P('advantage'),details,['close_detail'],back,['assert_draft','Does that include my specialist?'],['clear_draft'],
  P('advantage'),drawer,S('What did you check about my doctor?'),hide,back,['refresh'],P('advantage'),back,
  S('I am not switching today. Summarize what we checked.')],
 BJ11:[S('I live in 34102. I have Parts A and B, my Plan G and a separate drug plan. I take metformin 500 mg tablets. Compare my medicines for 2027.'),
  S('Show me what you do have, but label the year.'),P('part-d'),['sample_or_block'],drawer,
  S('It covers it here. Can I assume the 2027 version does too?'),hide,back,
  S('Then do not pick a plan. What exactly needs updating before we finish?')],
 BJ12:[S('I am 65 in 34103. I have Parts A and B and no other coverage. I take no medicines.'),P('advantage'),details,['ask_detail'],
  S('What happens when I spend four months out of state?'),S('Actually flexibility matters more to me than the lowest premium.'),hide,C('Original Medicare'),['medical_costs'],C('Medicare Advantage'),['ma_list'],['same_detail'],['close_detail'],back,
  S('You showed me a supplement, so that is what I have selected?'),S('I am going to wait before choosing additional coverage. What do I still need to check?')]
};

function write(file,value){fs.writeFileSync(file,typeof value==='string'?value:JSON.stringify(value,null,2));}
const digest = data => crypto.createHash('sha256').update(data).digest('hex');
async function run(browser,id,variant='interrupted',size=null){
 const profile=profiles.find(p=>p.id===id), folder=path.join(output,id+'-'+variant+(size?'-'+size.width:''));fs.mkdirSync(folder,{recursive:true});
 const viewport=size || (id==='BJ08'?{width:820,height:1180}:id==='BJ09'?{width:390,height:844}:{width:1440,height:1000});
 const ctx=await browser.newContext({viewport,reducedMotion:'reduce',serviceWorkers:'block'}), page=await ctx.newPage();page.setDefaultTimeout(4000);
 let state=null, seq=0, http=0, errors=[], blocked=[], pending=[], firstDetail=null;
 await ctx.route('**/*',route=>{if(new URL(route.request().url()).origin===base) return route.continue();blocked.push(route.request().url());return route.abort();});
 page.on('pageerror',e=>{errors.push(e.message);fs.appendFileSync(path.join(folder,'errors.jsonl'),JSON.stringify({error:e.message})+'\n');});
 page.on('dialog',d=>d.accept());
 page.on('response',response=>{if(!response.url().includes('/api/'))return; const job=(async()=>{let body;try{body=await response.json()}catch{return}
   if(body.guide&&body.record)state=body;
   if(body.status==='resumed'&&body.response?.guide)state=body.response;
   write(path.join(folder,'http-'+String(++http).padStart(3,'0')+'.json'),{url:response.url(),status:response.status(),request:response.request().postData(),body});})();pending.push(job);});
 async function flush(){await Promise.allSettled(pending);pending=[];}
 async function capture(action,before,status='performed',error=null){
  await flush();const n=String(++seq).padStart(3,'0');const html=await page.content();write(path.join(folder,n+'.html'),html);
  let body=await page.locator('body').innerText(), layout=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,
   focus:document.activeElement?.id||document.activeElement?.textContent?.slice(0,100),composer:(()=>{let r=document.getElementById('message')?.getBoundingClientRect();return r?{x:r.x,y:r.y,width:r.width,height:r.height}:null})()}));
  const event={seq,at:new Date().toISOString(),action,status,error,before,after:state,visible:body,layout,dom:n+'.html',dom_sha256:digest(html)};
  if(action[0]!=='say' || seq===1){await page.screenshot({path:path.join(folder,n+'.png')});event.screenshot=n+'.png';}
  fs.appendFileSync(path.join(folder,'events.jsonl'),JSON.stringify(event)+'\n');write(path.join(folder,'checkpoint.json'),event);
  return event;
 }
 async function say(text){
  await page.locator('#message').fill(text);const response=page.waitForResponse(r=>r.url().endsWith('/api/conversation/turn'),{timeout:12000});
  await page.locator('#send').click();const r=await response;const value=await r.json();await flush();
  if(!r.ok())throw Error(value.error||r.status());
  await page.locator('#pending-turn').waitFor({state:'hidden',timeout:12000});
 }
 async function click(label){await page.getByRole('button',{name:label,exact:true}).filter({visible:true}).first().click();await flush();}
 async function doAction(a){
  const [kind,text]=a;
  if(kind==='say')return say(text);
  if(kind==='click')return click(text);
  if(kind==='plans'){
   await page.locator('#plans-tab').click();await page.locator('#plans-panel .plans-title').first().waitFor();await page.waitForLoadState('networkidle');await flush();
   if(state?.conversationPlanner?.plans_view!==text)throw Error('Requested '+text+' but routed to '+state?.conversationPlanner?.plans_view);
   return;
  }
  if(kind==='back')return click('Back to my conversation');
  if(kind==='drawer')return page.locator('#plans-fab').click();
  if(kind==='hide'){
   const buttons=page.getByRole('button',{name:/^(Close|Hide chat|Back to the guide)$/}).filter({visible:true});
   await buttons.first().click();return;
  }
  if(kind==='medical_costs')return page.getByRole('button',{name:/Your share of medical costs/}).click();
  if(kind==='ma_list'){
   const b=page.getByRole('button',{name:/Choose a plan/}).filter({visible:true});if(await b.count())await b.first().click();return;
  }
  if(kind==='detail'||kind==='same_detail'){
   const scope=kind==='same_detail'?page.locator('article[data-plan-id]').filter({has:page.locator('h3',{hasText:firstDetail})}):page;
   const b=scope.getByRole('button',{name:/^(See full details|Full details|Details)$/}).filter({visible:true});await b.first().click();
   const title=await page.locator('dialog[open] h2').innerText();
   if(kind==='same_detail'&&title!==firstDetail)throw Error('Returned to a different plan');
   if(!firstDetail)firstDetail=title;return;
  }
  if(kind==='ask_detail')return page.locator('dialog[open]').getByRole('button',{name:'Ask Daylight about this plan',exact:true}).click();
  if(kind==='close_detail')return page.locator('dialog[open]').getByRole('button',{name:/Close/}).first().click();
  if(kind==='guide'){
   const b=page.getByRole('button',{name:/sign.up guide|Apply online|Call Social Security|How to sign up|Prepare.*call|Open.*guide/i}).filter({visible:true});await b.first().click();return;
  }
  if(kind==='draft')return page.locator('#message').fill(text);
  if(kind==='clear_draft')return page.locator('#message').fill('');
  if(kind==='assert_draft'){if(await page.locator('#message').inputValue()!==text)throw Error('Draft lost');return;}
  if(kind==='refresh'){
   const fields=JSON.stringify(state?.guide?.fields);const restored=page.waitForResponse(r=>r.url().endsWith('/api/conversation/resume'));
   await page.reload();await restored;await page.locator('#message').waitFor();await flush();
   if(JSON.stringify(state?.guide?.fields)!==fields)throw Error('Reports changed on refresh');return;
  }
  if(kind==='sample_or_block'){
   if(state?.partDProfile?.status!=='unsupported')throw Error('Unsupported year was substituted');
   return;
  }
  if(kind==='answer_checks'){
   for(let i=0;i<14;i++){
    const q=state?.conversationCheck?.question;if(!q)return;
    if(id==='BJ06'&&['period','fills','prior_spending','channel'].includes(q.field)){
     const before=state;await say('I do not know that detail. Leave it open for Mom to check.');
     await capture(['unknown_check',q.field],before);return;
    }
    const map={period:'2026-12-01',fills:'2026-12-01',prior_spending:'confirmed_zero',outlet_zip:'34103',channel:'retail',assistance:id==='BJ06'?'unknown':'none',quantity:'30',days_supply:'30',unit:'tablet'};
    let choice=q.choices?.find(c=>c.value===map[q.field]);
    if(['doctor','office','formulary_product','pharmacy','rxcui'].includes(q.field))choice=q.choices?.find(c=>!c.value.startsWith('__'));
    if(q.field==='pharmacy' && id==='BJ03' && (await page.locator('body').innerText()).includes('Actually use Grove'))choice=q.choices?.find(c=>c.value.startsWith('Grove:'));
    if(!choice&&!map[q.field]){await capture(['unavailable_answer',q.field],state,'blocked','No disclosed answer for this field');return;}
    const before=state;
    if(choice){const index=q.choices.indexOf(choice);
     if(q.choices.length>8)await page.locator('#conversation-check-choice').selectOption(String(index));
     else await page.locator('#conversation-check-choices button.choice').nth(index).click();
     const response=page.waitForResponse(r=>r.url().endsWith('/api/conversation/turn'));await page.locator('#send').click();await response;await flush();
    }else await say(map[q.field]);
    await capture(['answer_check',q.field,choice?.label||map[q.field]],before);
   }
   throw Error('Local check action budget reached');
  }
 }
 const report={id,variant,viewport,driver_sha256:driverHash,language_quality:'not_tested',human_review:'unreviewed',events:0,failures:[],unexecuted:[]};
 try{
  await page.goto(base);await page.locator('#start').click();await flush();
  const status=await (await ctx.request.get(base+'/api/status')).json();write(path.join(folder,'runtime.json'),status);
  if(!status.offline_test_manifest||!status.local_demo.discussion_planner)throw Error('Offline runtime not bound');
  await capture(['start'],null);
  const actions=[S(profile.opening),...cases[id]];
  for(const a of actions){
   if(variant==='direct'&&!['say','answer_checks'].includes(a[0]))continue;
   const before=state,start=Date.now();
   try{await doAction(a);await capture(a,before);}
   catch(e){report.failures.push({action:a,error:e.message});await capture(a,before,'blocked',e.message);}
   console.log(id,variant,seq,a[0],Date.now()-start);
  }
  report.outcome=state?.conversationPlanner?.outcome||null;
  if(report.outcome && (state.assessment?.nextQuestion || /What would you like to understand next\?/.test(state.reply||'')))report.failures.push({completion:'Generic intake followed a finish'});
  report.status=report.failures.length?'failed':!report.outcome?'incomplete':report.outcome.goal_complete?'goal_complete':'safe_blocked';
  report.final_decision=state?.coveragePath;report.parts=state?.enrollment?.record?.parts;
  if(id==='BJ10'&&variant==='interrupted'){
   // Separate context/visit clone. Never expire the completed main visit.
   const clone=await browser.newContext();await clone.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
   const p=await clone.newPage();await p.goto(base);await p.locator('#start').click();await p.locator('#message').fill(profile.opening);
   const r=p.waitForResponse(r=>r.url().endsWith('/api/conversation/turn'));await p.locator('#send').click();const o=await (await r).json();
   const expired=await clone.request.post(base+'/__test__/expire',{headers:{Origin:base},data:{continuation:o.continuation}});write(path.join(folder,'expiry-control.json'),await expired.json());
   const resumed=p.waitForResponse(r=>r.url().endsWith('/api/conversation/resume'));
   await p.reload();const expiredState=await (await resumed).json();write(path.join(folder,'expiry-response.json'),expiredState);
   if(expiredState.status!=='expired')throw Error('Separate expiry clone did not expire');
   await p.locator('#resume-status').waitFor();await p.locator('#start').waitFor();write(path.join(folder,'expiry.html'),await p.content());write(path.join(folder,'expiry.txt'),await p.locator('body').innerText());await p.screenshot({path:path.join(folder,'expiry.png')});await clone.close();
  }
 }catch(e){report.status='failed';report.failures.push({fatal:e.message});}
 report.events=seq;report.errors=errors;report.blocked_outbound=blocked;write(path.join(folder,'report.json'),report);await ctx.close();return report;
}
(async()=>{
 fs.mkdirSync(output,{recursive:true});const browser=await chromium.launch({headless:true});const reports=[];
 try{for(const p of profiles.filter(p=>!only||only.split(',').includes(p.id)))reports.push(await run(browser,p.id));
  if(!only||process.env.DIRECT_PAIRS)for(const id of ['BJ01','BJ03','BJ05','BJ07','BJ08','BJ12'].filter(id=>!only||only.split(',').includes(id)))reports.push(await run(browser,id,'direct'));
 }finally{write(path.join(output,'reports.json'),reports);await browser.close();}
 console.log(JSON.stringify(reports.map(r=>({id:r.id,variant:r.variant,status:r.status,failures:r.failures.length})),null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
