/* D176 real UI/handlers, explicit fictional meanings, no outbound model traffic. */
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const runtime=JSON.parse(fs.readFileSync('/private/tmp/daylight-progress-runtime.json'));
const base=runtime.url, output=path.resolve(__dirname,'../../../audit-evidence/question-progress-20261115/browser');
fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'runtime.json'),JSON.stringify(runtime,null,2));
(async()=>{
 const browser=await chromium.launch({headless:true}),results=[];
 try{for(const viewport of [{width:1440,height:1000},{width:820,height:1180},{width:390,height:844}]){
  for(const journey of ['dates','parking']){
   const ctx=await browser.newContext({viewport,reducedMotion:'reduce',serviceWorkers:'block'});
   const page=await ctx.newPage();page.setDefaultTimeout(10000);
   const errors=[],events=[];let state;
   const stem=viewport.width+'-'+journey;
   await ctx.route('**/*',async route=>{
    if(new URL(route.request().url()).origin!==base)throw Error('Outbound request forbidden');
    if(route.request().url().endsWith('/api/conversation/turn')){
     const response=await route.fetch();state=await response.json();
     events.push({request:JSON.parse(route.request().postData()),response:state});
     fs.writeFileSync(path.join(output,stem+'-events.json'),JSON.stringify(events,null,2));
     return route.fulfill({response,json:state});
    }
    return route.continue();
   });
   page.on('pageerror',e=>errors.push(e.message));
   async function say(text){await page.locator('#message').fill(text);const r=page.waitForResponse(r=>r.url().endsWith('/api/conversation/turn'));await page.locator('#send').click();assert.equal((await r).status(),200);await page.locator('#pending-turn').waitFor({state:'hidden'});}
   const result={viewport,journey,errors,manifest:runtime.manifest.id};
   try{
    await page.goto(base);await page.locator('#start').click();
    if(journey==='dates'){
     await say('Help me coordinate the transition from my current job insurance.');
     assert.equal(state.assessment.nextQuestion.id,'RC11');
     await say('My job ends Apr 8, and coverage ends Apr. 30th.');
     assert.equal(state.record.facts.RC11.value.jobEnd,'april 8');
     assert.equal(state.record.facts.RC11.value.coverageEnd,'april 30');
     assert.ok(!JSON.stringify(state.record.facts.RC11.value).includes('2028'));
     assert.notEqual(state.assessment.nextQuestion?.id,'RC11');
     assert.equal(state.metrics.llmCalls,2);
     await say('Continue with the next detail.');assert.notEqual(state.assessment.nextQuestion?.id,'RC11');
     assert.equal(state.questionProgress.find(r=>r.question_id==='RC11').state,'reported');
    }else{
     await say('Help me compare costs.');assert.equal(state.assessment.nextQuestion.id,'T09');
     await say('That is difficult to answer.');assert.equal(state.assessment.nextQuestion.id,'T09');
     await say('I still need time to consider it.');assert.notEqual(state.assessment.nextQuestion?.id,'T09');
     assert.equal(state.questionProgress.find(r=>r.question_id==='T09').state,'parked');
     await page.locator('[data-question-progress] summary').click();
     assert.ok((await page.locator('[data-question-progress]').innerText()).includes('not yet recorded'));
     await page.locator('[data-question-progress]').scrollIntoViewIfNeeded();
     await page.screenshot({path:path.join(output,stem+'-parked.png')});
     await say('I prefer predictable bills.');
     assert.equal(state.guide.fields['needs.costPreference'].value,'predictable');
     assert.equal(state.questionProgress.find(r=>r.question_id==='T09').state,'reported');
     assert.notEqual(state.assessment.nextQuestion?.id,'T09');
     assert.equal(await page.locator('[data-question-progress]').count(),0);
    }
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    assert.deepEqual(errors,[]);result.status='passed';
   }catch(e){result.status='failed';result.failure=e.stack;process.exitCode=1;}
   await page.locator('#current').scrollIntoViewIfNeeded();
   await page.screenshot({path:path.join(output,stem+'-final.png')});
   fs.writeFileSync(path.join(output,stem+'-visible.txt'),await page.locator('body').innerText());
   results.push(result);await ctx.close();
  }
 }}finally{await browser.close();fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));}
 console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
