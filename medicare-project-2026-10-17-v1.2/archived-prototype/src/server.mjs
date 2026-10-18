import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {randomBytes} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {CASES,makeCase,comparison,context,updateProfile,evidenceRegistry} from './domain.mjs';
import {BASE_PROMPT,runAgent,replayAgent} from './agent.mjs';
const staticFiles={'/':['index.html','text/html; charset=utf-8'],'/app.js':['app.js','text/javascript; charset=utf-8'],'/styles.css':['styles.css','text/css; charset=utf-8']};
export function createServer({liveEnabled=process.env.ENABLE_OPENAI==='1',model=process.env.OPENAI_MODEL,keyPresent=Boolean(process.env.OPENAI_API_KEY),agent=runAgent}={}){
 const sessions=new Map();
 const server=http.createServer(async(req,res)=>{
  res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');
  res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'self'; form-action 'self'");
  const json=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(data));};
  const host=req.headers.host||'';
  if(!/^(127\.0\.0\.1|localhost):\d+$/.test(host))return json(403,{error:'Only a loopback host is allowed'});
  if(req.headers.origin&&req.headers.origin!==`http://${host}`)return json(403,{error:'Cross-origin requests are not allowed'});
  const url=new URL(req.url,`http://${host}`);
  if(req.method==='GET'&&staticFiles[url.pathname]){
   const [file,type]=staticFiles[url.pathname];res.writeHead(200,{'Content-Type':type});res.end(await readFile(new URL(`../public/${file}`,import.meta.url)));return;
  }
  if(!url.pathname.startsWith('/api/'))return json(404,{error:'Not found'});
  for(const [id,s]of sessions)if(Date.now()-s.touched>3600000&&!s.busy)sessions.delete(id);
  let sid=(req.headers.cookie||'').split(';').map(x=>x.trim()).find(x=>x.startsWith('aphrodite='))?.slice(10);
  if(!sid||!sessions.has(sid)){
   if(sessions.size>=200)return json(503,{error:'Local session limit reached; restart the workbench'});
   sid=randomBytes(24).toString('hex');sessions.set(sid,{state:makeCase(),history:[],csrf:randomBytes(24).toString('hex'),touched:Date.now(),busy:false});
   res.setHeader('Set-Cookie',`aphrodite=${sid}; HttpOnly; SameSite=Strict; Path=/`);
  }
  const session=sessions.get(sid);session.touched=Date.now();
  if(req.method==='GET'&&url.pathname==='/api/state')return json(200,{...context(session.state),comparison:comparison(session.state),csrf:session.csrf,cases:CASES.map(({id,label})=>({id,label})),live_available:liveEnabled&&keyPresent&&Boolean(model),model:model||null,base_prompt:BASE_PROMPT});
  if(req.method==='GET'&&url.pathname==='/api/evidence'){
   const e=evidenceRegistry(session.state)[url.searchParams.get('id')];return json(e?200:404,e||{error:'Evidence not found'});
  }
  if(req.method!=='POST')return json(405,{error:'Method not allowed'});
  if(req.headers['x-csrf-token']!==session.csrf)return json(403,{error:'Missing or invalid local session token'});
  if(!/^application\/json\b/.test(req.headers['content-type']||''))return json(415,{error:'JSON content required'});
  if(session.busy)return json(409,{error:'A turn is running. Wait before changing this case.'});
  try{
   let raw='';for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>32768)return json(413,{error:'Request too large'});}
   const body=JSON.parse(raw||'{}');
   if(url.pathname==='/api/case'){session.state=makeCase(body.case_id);session.history=[];return json(200,{ok:true});}
   if(url.pathname==='/api/profile'){updateProfile(session.state,body.patch);session.history=[];return json(200,{ok:true});}
   if(url.pathname==='/api/chat'){
    if(typeof body.message!=='string'||!body.message.trim()||body.message.length>6000)throw new Error('Message must contain 1–6000 characters');
    if(typeof(body.operator_prompt??'')!=='string'||(body.operator_prompt||'').length>10000)throw new Error('Invalid operator prompt');
    if(!['replay','openai'].includes(body.mode))throw new Error('Unknown evaluation mode');
    if(body.mode==='openai'&&!(liveEnabled&&keyPresent&&model))return json(412,{error:'OpenAI mode requires ENABLE_OPENAI=1, OPENAI_API_KEY and OPENAI_MODEL on the server'});
    session.busy=true;
    try{
     const args={state:session.state,message:body.message,history:session.history,operatorPrompt:body.operator_prompt||'',model};
     const result=body.mode==='openai'?await agent(args):replayAgent(args);
     session.history.push({role:'user',content:body.message},{role:'assistant',content:JSON.stringify(result.answer)});
     session.history=session.history.slice(-12);
     return json(200,{...result,comparison:comparison(session.state)});
    }finally{session.busy=false;}
   }
   return json(404,{error:'Not found'});
  }catch(error){return json(400,{error:error.name==='AbortError'?'Request timed out; no recommendation was committed':error.message});}
 });
 return server;
}
if(process.argv[1]===fileURLToPath(import.meta.url)){
 const port=Number(process.env.PORT||8787);
 if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('PORT must be 1024–65535');
 createServer().listen(port,'127.0.0.1',()=>console.log(`Aphrodite synthetic evaluation workbench: http://127.0.0.1:${port}`));
}
