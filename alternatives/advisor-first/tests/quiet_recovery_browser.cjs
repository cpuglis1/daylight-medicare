/* D175: same app and handlers, disposable profile, fictional declared responses. */
const fs=require('fs'), path=require('path'), assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {url:base,manifest}=JSON.parse(fs.readFileSync('/private/tmp/daylight-quiet-runtime.json'));
const output=path.resolve(__dirname,'../../../audit-evidence/quiet-recovery-20261114/browser');
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});const results=[];
 try{for(const viewport of [{width:1440,height:1000},{width:820,height:1180},{width:390,height:844}]){
  const ctx=await browser.newContext({viewport,reducedMotion:'reduce',serviceWorkers:'block'});
  const page=await ctx.newPage();page.setDefaultTimeout(10000);
  const errors=[],events=[];let state,count=0;
  await ctx.route('**/*',async route=>{
   if(new URL(route.request().url()).origin!==base)throw Error('Outbound browser request forbidden');
   if(route.request().url().endsWith('/api/conversation/turn')){
    const response=await route.fetch();state=await response.json();count++;
    events.push({request:JSON.parse(route.request().postData()),response:state});
    await route.fulfill({response,json:state});return;
   }
   return route.continue();
  });
  page.on('pageerror',e=>errors.push(e.message));
  async function send(){const r=page.waitForResponse(r=>r.url().endsWith('/api/conversation/turn'));await page.locator('#send').click();assert.equal((await r).status(),200);await page.locator('#pending-turn').waitFor({state:'hidden'});}
  async function say(text){await page.locator('#message').fill(text);await send();}
  async function capture(label){
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
   await page.locator('#current').scrollIntoViewIfNeeded();
   await page.screenshot({path:path.join(output,viewport.width+'-'+label+'.png')});
  }
  const result={viewport,manifest:manifest.id,errors};
  try{
   await page.goto(base);await page.locator('#start').click();
   await say('Start the fictional comparison.');assert.equal(state.assessment.nextQuestion.id,'T09');
   assert.equal(await page.locator('#current [aria-pressed="true"]').count(),0);
   await page.locator('#current').getByRole('button',{name:'More predictable costs',exact:true}).click();
   const before=count;await page.waitForTimeout(100);assert.equal(count,before);await send();
   assert.equal(state.generated.validation_recovery.component,'question');
   assert.equal(state.metrics.llmCalls,1);assert.equal(state.generated.answer_state,'continued');
   assert.ok(!state.notice);assert.notEqual(state.assessment.nextQuestion.id,'T09');
   const visible=await page.locator('body').innerText();
   assert.ok(!visible.includes('couldn’t finish'));assert.ok(!visible.includes('Your coverage is through a current job.'));
   assert.ok(!visible.includes('federal program'));await capture('quiet-continuation');
   await say('Continue with the fictional doctor check.');
   assert.equal(state.reply,'Your current coverage is still unknown.');
   assert.equal(state.assessment.nextQuestion.id,'T06');assert.ok(!state.generated.validation_recovery);
   await capture('uncertainty');
   await say('What will this cost in the fictional example?');
   assert.equal(state.generated.validation_recovery.component,'reply_blocks');
   assert.equal(state.generated.answer_state,'partial');assert.equal(state.metrics.llmCalls,2);
   assert.ok(state.notice.includes('unresolved'));assert.ok(!state.reply.includes('99999'));
   assert.ok(!(await page.locator('body').innerText()).includes('99999'));
   await capture('partial-answer');assert.deepEqual(errors,[]);
   result.status='passed';result.checks=['no preselection','deliberate Send','one-call bound answer','quiet approved question','unsupported claim hidden','unknown coverage accepted','partial answer disclosed','invalid block hidden','no overflow'];
  }catch(e){result.status='failed';result.failure=e.stack;process.exitCode=1;}
  fs.writeFileSync(path.join(output,viewport.width+'-events.json'),JSON.stringify(events,null,2));
  fs.writeFileSync(path.join(output,viewport.width+'-visible.txt'),await page.locator('body').innerText());
  await page.screenshot({path:path.join(output,viewport.width+'-final.png')});results.push(result);await ctx.close();
 }}finally{await browser.close();fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));}
 console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
