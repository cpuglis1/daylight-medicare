const {chromium}=require('/Users/cep4u/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs');const assert=require('node:assert/strict');
const out=__dirname,origin='http://127.0.0.1:8897';
(async()=>{
 const browser=await chromium.launch({headless:true});const results=[];
 try {
 for(const [name,width,height] of [['desktop',1440,900],['tablet',820,1180],['phone',390,844]]){
  const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'});
  const page=await context.newPage();const errors=[],blocked=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){blocked.push(route.request().url());return route.abort();}return route.continue();});
  await page.goto(origin,{waitUntil:'networkidle'});await page.locator('#start:enabled').waitFor();
  const status=await page.evaluate(()=>fetch('/api/status').then(r=>r.json()));
  assert.equal(status.local_demo.fixture,true,'Never send test turns to a live model service');
  assert.equal(status.local_demo.upstream_proxy,false);
  await page.screenshot({path:`${out}/${name}-landing.png`,fullPage:true});
  await page.locator('#start').click();await page.locator('#workspace:visible').waitFor();
  await page.locator('#message').fill('Fictional unsent draft');await page.locator('#privacy').click();
  await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
  assert.equal(await page.locator('#message').inputValue(),'Fictional unsent draft');
  await page.screenshot({path:`${out}/${name}-conversation.png`});await page.locator('#message').fill('');
  const seeded=await page.evaluate(async()=>{
   const session=await fetch('/api/guest/session').then(r=>r.json());
   let state=await fetch('/api/conversation/initial').then(r=>r.json()),last;
   for(const [id,fields] of [['RC01',{choice:'self'}],['T03',{zip:'34102'}],['MG_AGE',{choice:'66'}],['MG_SEX',{choice:'Female'}],['MG_TOBACCO',{choice:'Non-Tobacco'}]]){
    last=crypto.randomUUID();const body={guide:state.guide,record:state.record,requestId:last,aiConsent:false,action:{type:'choice',id,fields,source:'plans_filter'},...(state.continuation?{continuation:state.continuation}:{})};
    const response=await fetch('/api/conversation/turn',{method:'POST',headers:{'Content-Type':'application/json','X-Daylight-CSRF':session.csrf},body:JSON.stringify(body)});
    state=await response.json();if(!response.ok)throw Error(`Fictional seed failed ${response.status}`);
   }
   window.DaylightVisitResume.write(last,state.guide.preferences);window.DaylightVisitResume.rememberPage('supplement');
   return {medigap:state.medigapProfile.status,partD:state.partDProfile.status};
  });
  assert.equal(seeded.medigap,'ready');assert.equal(seeded.partD,'ready');
  await page.reload({waitUntil:'networkidle'});await page.locator('[data-medigap-id]').first().waitFor();
  const mgCount=await page.locator('[data-medigap-id]').count();assert.ok(mgCount>0);
  await page.locator('[data-medigap-id]').first().scrollIntoViewIfNeeded();
  await page.screenshot({path:`${out}/${name}-medigap.png`});
  await page.getByRole('button',{name:'See full details',exact:true}).first().click();
  await page.getByRole('dialog').waitFor();await page.screenshot({path:`${out}/${name}-medigap-detail.png`});await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Part D drug plans',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.part-d-workspace .plan-card').length===10);
  await page.screenshot({path:`${out}/${name}-part-d.png`});
  await page.getByRole('button',{name:'Medicare Advantage',exact:true}).click();
  await page.locator('.plan-card').first().waitFor();await page.screenshot({path:`${out}/${name}-advantage.png`});
  const scrollWidth=await page.evaluate(()=>document.documentElement.scrollWidth);assert.ok(scrollWidth<=width,`${name} overflow`);
  assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
  results.push({name,width,height,scrollWidth,medigapRendered:mgCount,partDRendered:10,refreshRestoredProfileAndTab:true,draftPreserved:true,errors,blocked});
  await context.close();
 }
 }finally{await browser.close();}
 fs.writeFileSync(`${out}/browser-checks.json`,JSON.stringify(results,null,2)+'\n');console.log(JSON.stringify(results));
})().catch(error=>{console.error(error);process.exit(1)});
