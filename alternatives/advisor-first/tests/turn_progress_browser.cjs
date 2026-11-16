/* D178 actual HTTP/UI. Explicit fictional transport, blocked outbound network. */
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const runtime=JSON.parse(fs.readFileSync('/private/tmp/daylight-progress-runtime.json'));
const base=runtime.url,output=path.resolve(__dirname,'../../../audit-evidence/turn-progress-20261115/browser');
fs.mkdirSync(output,{recursive:true});fs.writeFileSync(path.join(output,'runtime.json'),JSON.stringify(runtime,null,2));
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const journeys=(process.env.DAYLIGHT_TEST_JOURNEYS||'conversation,doctors,medicines').split(',');
(async()=>{
 const browser=await chromium.launch({headless:true}),results=process.env.DAYLIGHT_TEST_JOURNEYS
  ?JSON.parse(fs.readFileSync(path.join(output,'results.json'))).filter(r=>!journeys.includes(r.journey)):[];
 try{for(const viewport of [{width:1440,height:1000},{width:820,height:1180},{width:390,height:844}]){
  for(const journey of journeys){
   const ctx=await browser.newContext({viewport,reducedMotion:journey==='doctors'?'no-preference':'reduce',serviceWorkers:'block'});
   const page=await ctx.newPage();page.setDefaultTimeout(12000);
   const errors=[],turns=[],polls=[],stem=viewport.width+'-'+journey;
   let state,requestId,pollFailure=false,loseReply=false,csrf;
   await ctx.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(url.origin!==base)throw Error('Outbound request forbidden');
    if(url.pathname==='/api/conversation/progress'){
     if(pollFailure)return route.abort('failed');
     const response=await route.fetch();const value=await response.json();polls.push(value);
     assert.ok(Object.keys(value).every(k=>['state','stage'].includes(k)),JSON.stringify(value));
     return route.fulfill({response,json:value});
    }
    if(url.pathname==='/api/conversation/turn'){
     const payload=JSON.parse(route.request().postData());requestId=payload.requestId;
     const response=await route.fetch();state=await response.json();turns.push({payload,response:state});
     if(loseReply){loseReply=false;return route.abort('failed');}
     return route.fulfill({response,json:state});
    }
    return route.continue();
   });
   page.on('pageerror',e=>errors.push(e.message));
   const headers=()=>({'Origin':base,'X-Daylight-CSRF':csrf});
   async function control(data){const r=await ctx.request.post(base+'/__test__/progress-gate',{headers:headers(),data});assert.equal(r.status(),200);return r.json();}
   async function held(stage){for(let i=0;i<120;i++){const s=await control({action:'read'});if(s.held===stage)return s;await wait(50);}throw Error('Backend did not enter '+stage);}
   async function visible(stage){await page.locator('.thinking[data-progress="'+stage+'"]').waitFor();}
   async function jump(ms){await page.clock.fastForward(ms);}
   async function screenshot(name){await page.screenshot({path:path.join(output,stem+'-'+name+'.png')});}
   async function layout(){return page.evaluate(()=>{
    const s=document.querySelector('.thinking[data-progress]'),w=s.querySelector('.thinking-words'),m=s.querySelector('.thinking-more');
    const pane=document.querySelector('#reading').getBoundingClientRect(),r=s.getBoundingClientRect();
    return {overflow:document.documentElement.scrollWidth>innerWidth+1,
     lineFont:getComputedStyle(w).fontSize,moreFont:getComputedStyle(m).fontSize,
     color:getComputedStyle(w).color,background:getComputedStyle(document.body).backgroundColor,
     animation:getComputedStyle(s.querySelector('.thinking-dot')).animationName,
     visible:r.top>=pane.top&&r.bottom<=pane.bottom,top:r.top,bottom:r.bottom,paneBottom:pane.bottom,
     status:document.querySelector('#status').textContent,text:s.innerText,hidden:s.getAttribute('aria-hidden'),
     statusRole:document.querySelector('#status').getAttribute('role')};
   });}
   const result={viewport,journey,errors,manifest:runtime.manifest.id};
   try{
    await page.clock.install();await page.goto(base);await page.locator('#start').click();
    csrf=(await (await ctx.request.get(base+'/api/guest/session')).json()).csrf;
    const source=journey==='conversation'?'working':journey;
    await control({action:'set',stages:[source,'composing'],bad:journey==='conversation'});
    const words=journey==='conversation'?'Help me organize enrollment before I retire.':journey==='doctors'
     ?'I live in 34102. Check my doctor, Dr. Nera Vale in Naples.':'I live in 34102 and take metformin. Check my medicine.';
    await page.locator('#message').fill(words);await page.locator('#send').click();
    await held(source);await visible(source);
    assert.equal(await page.locator('#message').inputValue(),'');
    assert.equal(await page.locator('#send').isDisabled(),true);
    assert.equal(await page.locator('#message').isEnabled(),true);
    await page.locator('#message').fill('A newer unsent thought.');
    await jump(6500);await visible(source);await screenshot('early');
    assert.equal(await page.locator('.thinking-more').isVisible(),false);
    await jump(11000);await page.getByText('Your message is here. No need to send it again.',{exact:true}).first().waitFor();
    await screenshot('18-seconds');
    await jump(17000);await page.locator('.thinking-more').filter({hasText:'longer than usual'}).waitFor();
    const geometry=await layout();result.geometry=geometry;
    assert.equal(geometry.overflow,false);assert.equal(geometry.visible,true,JSON.stringify(geometry));
    assert.equal(geometry.lineFont,'18px');assert.equal(geometry.moreFont,'18px');
    assert.equal(geometry.hidden,'true');assert.equal(geometry.statusRole,'status');
    assert.equal(geometry.status,geometry.text.replace(/\n+/g,' '));
    if(journey!=='doctors')assert.equal(geometry.animation,'none');
    else assert.notEqual(geometry.animation,'none');
    await screenshot('35-seconds');
    if(journey==='conversation'){
     // Authenticated endpoint reads remain responsive during a blocked model call.
     const r=await ctx.request.post(base+'/api/conversation/progress',{headers:headers(),data:{requestId}});
     assert.equal(r.status(),200);assert.equal((await r.json()).stage,'working');
     const forbidden=await ctx.request.post(base+'/api/conversation/progress',{headers:{Origin:base},data:{requestId}});
     assert.equal(forbidden.status(),403);
     const malformed=await ctx.request.post(base+'/api/conversation/progress',{headers:headers(),data:{requestId,report:'not allowed'}});
     assert.equal(malformed.status(),422);
     const other=await browser.newContext();const session=await(await other.request.get(base+'/api/guest/session')).json();
     const isolated=await other.request.post(base+'/api/conversation/progress',{headers:{Origin:base,'X-Daylight-CSRF':session.csrf},data:{requestId}});
     assert.deepEqual(await isolated.json(),{state:'unknown'});await other.close();
     pollFailure=true;await jump(1100);await visible('waiting');
     assert.equal(await page.locator('.thinking-more').isVisible(),false);await screenshot('poll-loss');
     pollFailure=false;await jump(1100);await visible('working');
    }
    await control({action:'release'});await held('composing');await jump(1100);await visible('composing');
    assert.ok(!(await page.locator('body').innerText()).includes('99999'));
    await screenshot('composing');
    await control({action:'release'});await page.locator('#pending-turn').waitFor({state:'hidden'});
    assert.equal(state.metrics.llmCalls,2);assert.equal(await page.locator('#message').inputValue(),'A newer unsent thought.');
    const settled=(await control({action:'read'}));result.operations=settled.events;
    assert.deepEqual(settled.calls,['working','composing']);
    assert.equal(settled.events[0].receipt.stage,source);assert.equal(settled.events[1].receipt.stage,'composing');
    const count=polls.length;await jump(5000);assert.equal(polls.length,count);
    const anchor=await page.evaluate(()=>{
     const r=document.querySelector('#reading').getBoundingClientRect();
     const a=document.querySelector('#history').lastElementChild.querySelector('.chat-daylight:last-child');
     return {offset:a.getBoundingClientRect().top-r.top,height:r.height,scroll:document.querySelector('#reading').scrollTop};
    });
    assert.ok(anchor.offset>=-1&&anchor.offset<anchor.height-40,'Reply beginning is outside the reading pane: '+JSON.stringify(anchor));result.replyStart=anchor;
    await screenshot('reply');
    if(journey==='conversation'){
     assert.equal(state.generated.validation_recovery.component,'reply_blocks');assert.equal(state.reply,'We can use the details you share to organize the next steps.');assert.ok(!state.reply.includes('99999'));assert.equal(state.notice,undefined);
     await page.locator('#message').fill('');
     await page.getByRole('button',{name:'Through a current job',exact:true}).click();
     await control({action:'set',stages:['composing']});loseReply=true;
     await page.locator('#send').click();await held('composing');await visible('composing');
     await control({action:'release'});await page.locator('#pending-turn').waitFor({state:'hidden'});
     assert.equal(state.metrics.llmCalls,1);assert.deepEqual((await control({action:'read'})).calls,['composing']);
     assert.equal(await page.locator('#send').innerText(),'Send');
     result.lostResponseRecovered=true;await screenshot('recovered');
    }
    assert.deepEqual(errors,[]);result.status='passed';
   }catch(e){result.status='failed';result.failure=e.stack;process.exitCode=1;await control({action:'set',stages:[]}).catch(()=>{});await control({action:'release'}).catch(()=>{});}
   await screenshot('final');fs.writeFileSync(path.join(output,stem+'-visible.txt'),await page.locator('body').innerText());
   fs.writeFileSync(path.join(output,stem+'-events.json'),JSON.stringify({turns,polls},null,2));
   results.push(result);fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));
   console.log(JSON.stringify(result));await ctx.close();
  }
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
