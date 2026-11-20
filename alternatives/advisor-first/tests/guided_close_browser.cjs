/* D180 fictional journey through real HTTP, controller, review and Plans UI. */
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const runtime=JSON.parse(fs.readFileSync('/private/tmp/daylight-guided-close-runtime.json'));
const base=runtime.url,output=path.resolve(__dirname,'../../../audit-evidence/guided-plan-close-20261115/browser');
fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'runtime.json'),JSON.stringify(runtime,null,2));
(async()=>{
 const browser=await chromium.launch({headless:true}),results=[];
 try{for(const viewport of [{width:1440,height:1000},{width:820,height:1180},{width:390,height:844}]){
  const ctx=await browser.newContext({viewport,reducedMotion:'reduce',serviceWorkers:'block'}),page=await ctx.newPage();
  page.setDefaultTimeout(15000);const errors=[],turns=[];let state;
  page.on('pageerror',e=>errors.push(e.message));
  await ctx.route('**/*',async route=>{
   const url=new URL(route.request().url());assert.equal(url.origin,base,'Outbound request forbidden');
   if(url.pathname==='/api/conversation/turn'){
    const payload=JSON.parse(route.request().postData()),response=await route.fetch();state=await response.json();
    turns.push({payload,response:state});return route.fulfill({response,json:state});
   }return route.continue();
  });
  const result={viewport,errors,manifest:runtime.manifest.id};
  async function settle(count){for(let i=0;i<300 && turns.length<=count;i++)await new Promise(r=>setTimeout(r,100));
    await page.waitForFunction(()=>!document.body.classList.contains('turn-pending'));
    assert.ok(turns.length>count);assert.ok(!state.error,JSON.stringify(state));}
  async function send(text){const count=turns.length;await page.locator('#message').fill(text);await page.locator('#send').click();await settle(count);
    assert.equal(state.metrics.llmCalls,2);}
  async function selectCheck(){
    const q=state.conversationCheck?.question;assert.ok(q,'Expected exact identity question');
    const count=turns.length;
    if(await page.locator('#conversation-check-choice').count())await page.locator('#conversation-check-choice').selectOption('0');
    else await page.locator('#conversation-check-choices button').first().click();
    await page.locator('#send').click();await settle(count);return q.field;
  }
  async function shot(name){await page.screenshot({path:path.join(output,viewport.width+'-'+name+'.png')});}
  async function layout(){return page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,
    barText:document.querySelector('#phases').innerText,barLabel:document.querySelector('.profile-progress')?.getAttribute('aria-valuetext'),
    guide:document.querySelector('.plans-conversation-guide')?.dataset.view}));}
  try{
   await page.goto(base);await page.locator('#start').click();
   await send('I want to compare coverage for myself. I live in 34102, have Parts A and B, and have Original Medicare.');
   assert.equal(state.profileProgress.total,11);assert.equal((await layout()).barText,'');
   await shot('progress');
   await send('Please include Dr. Nera Vale in Naples.');
   assert.equal(await selectCheck(),'doctor');
   assert.notEqual(state.conversationCheck?.question?.field,'office','Exact sole office must be reused');
   const doctor=state.conversationCheck.results.find(r=>r.kind==='doctor_matrix');assert.ok(doctor);
   await send('I take metformin.');
   const fields=[];
   for(let i=0;i<6 && state.conversationCheck?.question;i++) {
    const q=state.conversationCheck.question;
    if(q.kind==='doctor')throw Error('Doctor was asked again');
    if(q.choices?.length && !fields.includes(q.field))fields.push(await selectCheck());
    else {const count=turns.length;await page.getByRole('button',{name:'Check later',exact:true}).first().click();await settle(count);}
   }
   assert.ok(fields.length,'Medicine identity selected');
   await send('I receive routine care locally.');
   await send('Keeping my doctors matters most.');
   assert.equal(state.assessment.nextQuestion?.id,'T09');
   const count=turns.length;
   await page.getByRole('button',{name:'More predictable costs',exact:true}).click();
   await page.locator('#send').click();await settle(count);
   assert.equal(state.metrics.llmCalls,1);assert.equal(state.profileProgress.addressed,11);
   assert.equal(state.comparisonClose.show,true);assert.equal(state.assessment.nextQuestion,null);
   assert.equal(state.coveragePath.state,'undecided');
   assert.ok(state.conversationCheck.compactResults.includes(doctor.key));
   assert.equal(await page.locator('#current .retained-check[open]').count(),0);
   assert.equal(await page.getByRole('button',{name:'Review my information and continue',exact:true}).count(),1);
   assert.equal(await page.locator('#review-plan-info').count(),0);
   await page.locator('#current .guided-close').scrollIntoViewIfNeeded();await shot('closing');
   assert.equal((await layout()).overflow,false);
   let n=turns.length;await page.getByRole('button',{name:'Review my information and continue',exact:true}).click();await settle(n);
   assert.equal(state.review.kind,'plan_profile');assert.ok(state.review.rows.length);
   assert.equal(state.metrics?.llmCalls || 0,0);
   n=turns.length;await page.locator('#send').click();await settle(n);
   await page.locator('#plans-panel h1').first().waitFor();
   assert.ok(state.plansHandoff);assert.equal(state.plansHandoff.personalRecommendationAllowed,false);
   assert.equal(state.metrics?.llmCalls || 0,0);
   await shot('plans');assert.equal((await layout()).overflow,false);
   // Actual UI navigation carries only the step code on a deliberate Send.
   await page.locator('#plans-panel .plan-kinds button').filter({hasText:'Original Medicare'}).click();
   await page.locator('#plans-fab').click();
   await page.locator('.plans-conversation-guide').waitFor();
   const navigation=await page.locator('.plans-conversation-guide').getAttribute('data-view');
   await shot('plans-chat');await send('What should I do on this page?');
   assert.equal(turns.at(-1).payload.plansContext.navigation,navigation);
   assert.equal(turns.at(-1).payload.plansContextPolicy,'plans-context-v1');
   assert.equal(state.coveragePath.state,'undecided');
   if(navigation==='supplement'){
    await page.getByRole('button',{name:'Continue to Part D',exact:true}).click();
    assert.equal(await page.locator('.plans-conversation-guide').getAttribute('data-view'),'part-d');
   }
   await page.locator('.plans-close-chat').click();
   await page.locator('#plans-panel .plan-kinds button').filter({hasText:'Medicare Advantage'}).click();
   await page.locator('#plans-fab').click();
   await page.locator('.plans-conversation-guide[data-view="advantage"]').waitFor();
   await send('What should I do on this page?');
   assert.equal(turns.at(-1).payload.plansContext.navigation,'advantage');
   assert.equal(state.coveragePath.state,'undecided');
   await page.getByRole('button',{name:'Continue to the drug check',exact:true}).click();
   await page.locator('.plans-conversation-guide[data-view="advantage-drugs"]').waitFor();
   await shot('advantage-guide');
   await page.locator('.plans-close-chat').click();
   await page.locator('#plans-panel').getByRole('button',{name:'Back to my conversation',exact:true}).click();
   assert.equal(await page.locator('.plans-conversation-guide').count(),0);
   await send('I need to pause for today.');
   assert.ok(state.cards.some(c=>c.kind==='guided_summary'));
   assert.equal(state.assessment.nextQuestion,null);await shot('pause');
   assert.deepEqual(errors,[]);result.passed=true;result.turns=turns.length;result.medicineFields=fields;
  }catch(error){result.passed=false;result.failure=String(error.stack);await shot('failure');throw error;}
  finally{results.push(result);fs.writeFileSync(path.join(output,viewport.width+'-turns.json'),JSON.stringify(turns,null,2));
   fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));await page.unrouteAll({behavior:'ignoreErrors'});await ctx.close();}
 }}finally{await browser.close();}
 console.log(JSON.stringify(results,null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
