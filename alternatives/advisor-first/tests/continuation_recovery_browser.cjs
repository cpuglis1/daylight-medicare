/* D177 actual handlers/UI, fictional scripted language, outbound blocked. */
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const runtime=JSON.parse(fs.readFileSync('/private/tmp/daylight-continuation-runtime.json'));
const base=runtime.url,output=path.resolve(__dirname,'../../../audit-evidence/continuation-recovery-20261115/browser');
fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'runtime.json'),JSON.stringify(runtime,null,2));
(async()=>{
 const browser=await chromium.launch({headless:true}),results=[];
 try{for(const viewport of [{width:1440,height:1000},{width:820,height:1180},{width:390,height:844}]){
  for(const journey of ['recovery','worker']){
   const ctx=await browser.newContext({viewport,reducedMotion:'reduce',serviceWorkers:'block'});
   const page=await ctx.newPage();page.setDefaultTimeout(10000);
   const errors=[],events=[];let state;const stem=viewport.width+'-'+journey;
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
   async function send(){const r=page.waitForResponse(r=>r.url().endsWith('/api/conversation/turn'));await page.locator('#send').click();assert.equal((await r).status(),200);await page.locator('#pending-turn').waitFor({state:'hidden'});}
   async function say(text){await page.locator('#message').fill(text);await send();}
   const result={viewport,journey,errors,manifest:runtime.manifest.id};
   try{
    await page.goto(base);await page.locator('#start').click();
    await say(journey==='recovery'?'Help me organize enrollment before I retire.':'Help me prepare for the transition into Medicare.');
    assert.equal(state.generated.answer_state,'partial');assert.equal(state.notice,undefined);
    assert.equal(state.assessment.nextQuestion.id,'T05');assert.equal(state.metrics.llmCalls,2);
    assert.ok(!state.reply.includes('unresolved'));assert.ok(!state.reply.includes('99999'));
    await page.locator('#current').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,stem+'-partial.png')});
    await page.getByRole('button',{name:'Through a current job',exact:true}).click();await send();
    assert.equal(state.assessment.nextQuestion.id,'RC09');assert.equal(state.notice,undefined);
    assert.equal(state.metrics.llmCalls,1);assert.ok(!state.reply.includes('next detail'));
    if(journey==='recovery')assert.equal(state.reply,'Current work can affect your Medicare sign-up window.');
    else{assert.ok(state.reply.includes('whether'));assert.equal(state.generated.validation_recovery,undefined);}
    await page.locator('#current').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,stem+'-choice.png')});
    await say('Please connect this to the earlier enrollment request.');
    assert.equal(state.generated.validation_recovery,undefined);assert.equal(state.notice,undefined);
    assert.ok(state.reply.includes('employment source'));assert.equal(state.metrics.llmCalls,2);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    assert.deepEqual(errors,[]);result.status='passed';
   }catch(e){result.status='failed';result.failure=e.stack;process.exitCode=1;}
   await page.screenshot({path:path.join(output,stem+'-final.png')});
   fs.writeFileSync(path.join(output,stem+'-visible.txt'),await page.locator('body').innerText());
   results.push(result);await ctx.close();
  }
 }}finally{await browser.close();fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));}
 console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
