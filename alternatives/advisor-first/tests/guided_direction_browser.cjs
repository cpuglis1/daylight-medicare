/* D172: actual app/handlers, local scripted model, disposable store. The one
 * labelled response decoration exercises large/late layout, not AI quality. */
const fs=require('fs'), path=require('path'), assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../../..');
const {url:base,manifest}=JSON.parse(fs.readFileSync('/private/tmp/daylight-guided-runtime.json'));
const output=path.resolve(process.argv[2] || path.join(root,'audit-evidence/guided-next-step-20261114/browser'));
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});const results=[];
 try{for(const viewport of [{width:1440,height:1000},{width:820,height:1180},{width:390,height:844}]){
  const ctx=await browser.newContext({viewport,reducedMotion:'reduce',serviceWorkers:'block'});
  const page=await ctx.newPage();page.setDefaultTimeout(10000);
  const errors=[],events=[];let state,count=0,decorate=false;
  await ctx.route('**/*',async route=>{
   if(new URL(route.request().url()).origin!==base)throw Error('Outbound browser request forbidden');
   if(route.request().url().endsWith('/api/conversation/turn')){
    const response=await route.fetch();const value=await response.json();count++;state=value;
    if(decorate){decorate=false;value.reply='Beginning of the fictional layout stress reply.\n\n| Item | Detail |\n| --- | --- |\n'+Array.from({length:28},(_,i)=>`| Fictional row ${i+1} | Layout verification only |`).join('\n');}
    events.push({request:JSON.parse(route.request().postData()),response:value});
    await route.fulfill({response,json:value});return;
   }
   return route.continue();
  });
  page.on('pageerror',e=>errors.push(e.message));
  async function send(){const r=page.waitForResponse(r=>r.url().endsWith('/api/conversation/turn'));await page.locator('#send').click();assert.equal((await r).status(),200);await page.locator('#pending-turn').waitFor({state:'hidden'});}
  async function say(text){await page.locator('#message').fill(text);await send();}
  async function pick(label){assert.equal(await page.locator('#current [aria-pressed="true"]').count(),0);await page.locator('#current').getByRole('button',{name:label,exact:true}).click();const n=count;await page.waitForTimeout(100);assert.equal(count,n,'Selection sent without deliberate Send');await send();}
  async function anchor(){return page.evaluate(()=>{const pane=document.querySelector('#reading'),reply=document.querySelector('#history .exchange:last-child .chat-daylight:last-child');return {offset:reply.getBoundingClientRect().top-pane.getBoundingClientRect().top,top:pane.scrollTop,overflow:document.documentElement.scrollWidth>innerWidth+1};});}
  const result={viewport,manifest:manifest.id,errors,checks:[]};
  try{
   await page.goto(base);await page.locator('#start').click();
   decorate=true;
   await say('I want to understand my coverage options. I am 68 and have my current employer group insurance. I am retiring next week.');
   assert.equal(state.generated.status,'complete',JSON.stringify(state.generated));
   assert.equal(state.assessment.nextQuestion.id,'CP_TIMING');
   const first=await anchor();assert.ok(Math.abs(first.offset-18)<3,JSON.stringify(first));
   await page.waitForTimeout(2800);const settled=await anchor();assert.ok(Math.abs(settled.offset-first.offset)<2,'Reply jumped after settling');
   await page.evaluate(()=>{const reply=document.querySelector('#history .exchange:last-child .chat-daylight:last-child');const visual=document.createElement('div');visual.style.height='500px';visual.textContent='Fictional late visualization layout';reply.append(visual);});
   await page.waitForTimeout(200);const grown=await anchor();assert.ok(Math.abs(grown.offset-first.offset)<2,'Late visual moved reply beginning');assert.equal(grown.overflow,false);
   await page.screenshot({path:path.join(output,viewport.width+'-reply-start.png')});
   // Deliberate reader movement must not be undone by a delayed auto-scroll.
   await page.locator('#reading').evaluate(p=>p.scrollTop+=130);const reader=await anchor();await page.waitForTimeout(600);assert.equal((await anchor()).top,reader.top);
   const n=count;await page.locator('#current').getByRole('button',{name:'Work through my Medicare timing',exact:true}).click();
   assert.equal(count,n);assert.equal(await page.locator('#message').inputValue(),'Work through my Medicare timing');await send();
   assert.equal(state.assessment.nextQuestion.id,'RC04');assert.equal(state.coveragePath.state,'undecided');
   assert.ok(!(state.cards||[]).some(c=>c.kind==='signup_route'));
   await page.locator('#current').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,viewport.width+'-parts-buttons.png')});
   await pick('Neither');assert.equal(state.assessment.nextQuestion.id,'RC09');
   await pick('My current job');assert.equal(state.assessment.nextQuestion.id,'RC11');
   await page.locator('#current').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,viewport.width+'-end-dates.png')});
   await pick('I don’t know');assert.notEqual(state.assessment.nextQuestion?.id,'RC11');
   await say('Settle on timing! Force a local failure.');
   assert.equal(state.generated.status,'unavailable');assert.notEqual(state.assessment.nextQuestion?.id,'CP_RETRY');
   assert.ok(!state.reply.includes('What would you like to understand next?'));
   assert.ok(state.assessment.nextQuestion?.choices.length);
   assert.deepEqual(errors,[]);result.checks=['reply beginning','no delayed jump','late visual','reader scroll retained','offer stages only','no preselection','parts buttons','employment buttons','end dates','unknown continues','failed generation keeps controls'];result.status='passed';
  }catch(e){result.status='failed';result.failure=e.stack;process.exitCode=1;}
  fs.writeFileSync(path.join(output,viewport.width+'-events.json'),JSON.stringify(events,null,2));
  fs.writeFileSync(path.join(output,viewport.width+'-visible.txt'),await page.locator('body').innerText());
  await page.screenshot({path:path.join(output,viewport.width+'-final.png')});
  results.push(result);await ctx.close();
 }}finally{await browser.close();fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));}
 console.log(JSON.stringify(results,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
