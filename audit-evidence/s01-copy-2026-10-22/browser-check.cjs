const puppeteer=require('/tmp/jt/node_modules/puppeteer-core');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const BASE='http://127.0.0.1:8890';
const ROOT='/Users/cep4u/daylight';
const OUT='/Users/cep4u/Documents/Codex/2026-10-21/task/s01-copy-browser/final';fs.mkdirSync(OUT,{recursive:true});
const Q4='Part A helps cover inpatient hospital care. Part B helps cover doctors’ services and outpatient care.';
const Q7='You can add a separate Part D plan to Original Medicare; most Medicare Advantage plans include drug coverage.';
const PREMIUM='The Part B premium still applies; some plans help pay all or part of it.';
const originalFacts=JSON.parse(fs.readFileSync(path.join(ROOT,'cms-slice/apps/ten-question/teaching-facts.json')));
const advantage=originalFacts.facts.find(x=>x.id==='advantage');assert.ok(advantage.text.includes(PREMIUM));
const result={started_at_utc:new Date().toISOString(),base_url:BASE,requirements:['D19','D22','D23','D24','D66','D68'],checks:[],page_errors:[],blocked_non_get:[],unexpected_api:[],outbound_requests:[],api_interceptions:[],real_profile_requests:0,paid_ai_requests:0,
  limits:['Fresh isolated Chromium browser contexts; all /api requests intercepted before navigation. No real profiles, saved answers, source acceptance or paid AI used.',
    'Actual Part C map opens routesintro; standalone advantage fact is not mapped to that button. Separate fixture-only response aliases the current advantage fact to that existing map control for dialog-component rendering; no product mapping or file changes.']};
let browser;
async function begin(width,height,knowledge,alias){
 const context=await browser.createBrowserContext(),p=await context.newPage();await p.setViewport({width,height});
 p.on('pageerror',e=>result.page_errors.push(e.message));await p.setRequestInterception(true);
 p.on('request',async req=>{
  try{
   const u=new URL(req.url());
   if(u.origin!==BASE){result.outbound_requests.push(req.url());return req.abort();}
   if(req.method()!=='GET'){result.blocked_non_get.push({url:req.url(),method:req.method()});return req.abort();}
   if(u.pathname.startsWith('/api/')){
    result.api_interceptions.push(u.pathname);
    if(u.pathname==='/api/guest/session')return req.respond({status:200,contentType:'application/json',body:JSON.stringify({version:0,hasSaved:false,csrf:'synthetic-only-no-profile'})});
    if(u.pathname==='/api/status')return req.respond({status:200,contentType:'application/json',body:JSON.stringify({agent_available:false,consumer_ready:false,plan_validation_status:'pending'})});
    result.unexpected_api.push(u.pathname);return req.abort();
   }
   if(u.pathname==='/ten-config.json')return req.respond({status:200,contentType:'application/json',body:JSON.stringify({mockAI:true})});
   if(alias && u.pathname==='/teaching-facts.json'){
    const facts=JSON.parse(JSON.stringify(originalFacts));facts.facts=facts.facts.map(f=>f.id==='routesintro'?{...advantage,id:'routesintro'}:f);
    return req.respond({status:200,contentType:'application/json',body:JSON.stringify(facts)});
   }
   return req.continue();
  }catch(e){result.page_errors.push('interception:'+e.message);try{await req.abort();}catch(_){}}
 });
 await p.goto(BASE,{waitUntil:'networkidle0'});await p.waitForSelector('#get-started:not([disabled])');await p.click('#get-started');
 const next=async()=>{await p.click('#ten-continue');};
 await p.click('[data-value="learn"]');await next();
 await p.click('[data-value="'+knowledge+'"]');await next();
 await p.click('.ten-unknown');await next();
 return {context,p,next,width,height,knowledge,alias};
}
async function capture(p,name){await p.screenshot({path:path.join(OUT,name),fullPage:true});}
async function overflow(p){return p.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));}
async function reachSeven(x,saveQ4){
 const {p,next,width,height,knowledge}=x;
 assert.equal(await p.$eval('#stage h1',n=>n.textContent),'When do you need Medicare coverage to start?');
 const visible4=await p.$eval('.ten-teaching',n=>n.innerText);let expanded4=visible4;
 if(knowledge==='comfortable'){await p.click('.ten-explanation details summary');expanded4=await p.$eval('.ten-explanation details p',n=>n.innerText);}
 assert.ok(expanded4.startsWith(Q4));assert.ok(expanded4.endsWith('Your requested start is not verified eligibility or enrollment.'));
 const mapWasCollapsed=await p.$eval('.flow-picture-head button',n=>n.textContent==='Show map');
 if(mapWasCollapsed)await p.click('.flow-picture-head button');
 assert.deepEqual(await p.$$eval('.coverage-route-title',n=>n.map(x=>x.textContent)),['Original Medicare','Medicare Advantage']);
 const flow4=await overflow(p);assert.ok(flow4.document<=flow4.viewport+1);
 if(saveQ4)await capture(p,width+'-'+knowledge+'-q4.png');
 await p.click('[data-value="unknown"]');await next(); // T04
 await p.click('[data-value="unknown"]');await next(); // T05
 await p.click('[data-value="later"]');await next(); // T06
 assert.equal(await p.$eval('#stage h1',n=>n.textContent),'What prescriptions do you take?');
 const visible7=await p.$eval('.ten-teaching',n=>n.innerText);assert.ok(visible7.includes(Q7));
 let expanded7=visible7;
 if(knowledge==='comfortable'){assert.equal(visible7,Q7);await p.click('.ten-explanation details summary');expanded7=await p.$eval('.ten-explanation details p',n=>n.innerText);}
 assert.ok(expanded7.startsWith('Part D is prescription drug coverage.'));assert.ok(expanded7.endsWith('Exact plan rules still need checking.'));
 const flow7=await overflow(p);assert.ok(flow7.document<=flow7.viewport+1);
 if(saveQ4)await capture(p,width+'-'+knowledge+'-q7.png');
 return {width,height,familiarity:knowledge,q4_visible:visible4,q4_expanded:expanded4,q7_visible:visible7,q7_expanded:expanded7,map_initially_collapsed:mapWasCollapsed,overflow:[flow4,flow7]};
}
(async()=>{
 const served=await fetch(BASE+'/teaching-facts.json');assert.equal(served.status,200);const body=await served.text();
 assert.equal(JSON.parse(body).facts.find(x=>x.id==='advantage').text,advantage.text);
 result.active_static_facts_sha256=crypto.createHash('sha256').update(body).digest('hex');
 assert.equal(result.active_static_facts_sha256,crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT,'cms-slice/apps/ten-question/teaching-facts.json'))).digest('hex'));
 browser=await puppeteer.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--no-sandbox','--disable-background-networking']});
 for(const [width,height] of [[1440,1000],[820,1180],[390,844]]){
  for(const knowledge of ['new','comfortable']){
   const x=await begin(width,height,knowledge,false),record=await reachSeven(x,true);
   await x.p.evaluate(()=>[...document.querySelectorAll('.coverage-piece')].find(b=>b.textContent==='Part C · A + B benefits').click());
   await x.p.waitForSelector('dialog[open]');record.actual_map_popup=await x.p.$eval('dialog[open]',n=>n.innerText);
   assert.ok(record.actual_map_popup.startsWith('The two coverage routes'));assert.ok(!record.actual_map_popup.includes(PREMIUM));
   await capture(x.p,width+'-'+knowledge+'-actual-map-popup.png');result.checks.push(record);await x.context.close();
  }
  const x=await begin(width,height,'new',true);await reachSeven(x,false);
  await x.p.evaluate(()=>[...document.querySelectorAll('.coverage-piece')].find(b=>b.textContent==='Part C · A + B benefits').click());await x.p.waitForSelector('dialog[open]');
  const popup=await x.p.$eval('dialog[open]',n=>n.innerText);assert.ok(popup.startsWith('Medicare Advantage'));assert.ok(popup.includes(PREMIUM));
  assert.ok(popup.includes('Doctors, costs, and rules vary by plan.'));assert.ok(popup.includes("Check each plan's doctors, drug coverage, costs, and rules."));
  await capture(x.p,width+'-advantage-fact-component-fixture.png');result.checks.push({width,height,fixture_only:true,standalone_advantage_dialog:popup,product_mapping_changed:false});await x.context.close();
 }
 assert.deepEqual(result.page_errors,[]);assert.deepEqual(result.blocked_non_get,[]);assert.deepEqual(result.unexpected_api,[]);assert.deepEqual(result.outbound_requests,[]);
 result.finished_at_utc=new Date().toISOString();result.status='passed';fs.writeFileSync(path.join(OUT,'browser-checks.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify({status:result.status,actual_q4_q7_cases:6,standalone_advantage_component_cases:3,real_profile_requests:0,paid_ai_requests:0,page_errors:result.page_errors,output:OUT}));
 await browser.close();
})().catch(async e=>{result.status='failed';result.error=e.stack;fs.writeFileSync(path.join(OUT,'browser-checks.json'),JSON.stringify(result,null,2));if(browser)await browser.close();console.error(e);process.exitCode=1;});
