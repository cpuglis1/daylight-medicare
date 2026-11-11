import pathlib,json,hashlib,datetime,urllib.request,urllib.error,urllib.parse,subprocess
"""Explicit-URL L03 research collector. Inherited source stops are binding; no retries or access bypasses."""
ROOT=pathlib.Path(__file__).resolve().parents[2]/'docs/data/l03-ma-benefits-2026-10-25';ROOT.mkdir(parents=True,exist_ok=True)
RAW=ROOT/'acquisition-r1';RAW.mkdir(exist_ok=True)
MF=ROOT/'source-manifest.json'
def digest(b):return hashlib.sha256(b).hexdigest()
def get(url,id,kind='discovery'):
 release=ROOT/'build-r1/RELEASE.json'
 if release.exists() and json.loads(release.read_text()).get('accepted'):raise ValueError('Accepted L03 revision is immutable; create a new revision')
 mf=json.loads(MF.read_text()) if MF.exists() else {'sources':[],'stops':{'uhc.com':'Inherited 403; no alternate routes','wellcare.com':'Inherited systematic/commercial collection restriction','medicare.gov':'Inherited 403/Plan Finder stop'}}
 if any(x['url']==url for x in mf['sources']):return next(x for x in mf['sources'] if x['url']==url)
 host=urllib.parse.urlparse(url).hostname
 if any(host==h or host.endswith('.'+h) for h in mf['stops']):raise ValueError('STOP '+host)
 r={'id':id,'url':url,'kind':kind,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'acceptance':'pending','allowed_use':'authorized research capture; consumer redisplay/reuse review pending'}
 class Redirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,msg,headers,newurl):
   nh=urllib.parse.urlparse(newurl).hostname
   if any(nh==h or nh.endswith('.'+h) for h in mf['stops']):raise ValueError('Redirect to stopped origin')
   return super().redirect_request(req,fp,code,msg,headers,newurl)
 try:
  op=urllib.request.build_opener(Redirect);resp=op.open(url,timeout=50);b=resp.read();sha=digest(b);path=RAW/sha
  if not path.exists():path.write_bytes(b)
  r.update(status='acquired',sha256=sha,bytes=len(b),path=str(path.relative_to(ROOT)),final_url=resp.url,content_type=resp.headers.get('Content-Type'),last_modified=resp.headers.get('Last-Modified'))
  if b.startswith(b'%PDF'):
   txt=RAW/(sha+'.txt');subprocess.run(['pdftotext','-layout',str(path),str(txt)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);r['text_path']=str(txt.relative_to(ROOT));r['text_sha256']=digest(txt.read_bytes())
 except urllib.error.HTTPError as e:
  r.update(status='unavailable',http_status=e.code,reason=str(e))
  if e.code in [401,403,429]:mf['stops'][host]=f'HTTP {e.code}; no retry or alternate route'
 except Exception as e:r.update(status='unavailable',reason=str(e))
 mf['sources'].append(r);MF.write_text(json.dumps(mf,indent=2)+'\n');print(id,r['status'],r.get('bytes'),flush=True);return r
if __name__=='__main__':
 import sys
 get(*sys.argv[1:])
