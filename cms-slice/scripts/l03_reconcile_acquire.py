"""Additive L03 r2 official publisher acquisition; never changes r1 evidence."""
import datetime, hashlib, json, pathlib, re, subprocess, urllib.request, urllib.error, urllib.parse
from html.parser import HTMLParser

ROOT=pathlib.Path(__file__).resolve().parents[2]/'docs/data/l03-ma-benefits-2026-10-25/reconciliation-r2'
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,t,a):
        if t=='a':
            d=dict(a)
            if d.get('href'):self.links.append(d['href'])

def acquire():
    ROOT.mkdir(exist_ok=True);raw=ROOT/'acquisition';raw.mkdir(exist_ok=True)
    mfpath=ROOT/'erickson-source-manifest.json'
    mf=json.loads(mfpath.read_text()) if mfpath.exists() else {'sources':[],'stops':{}}
    for number,slug in [('001','signature'),('002','liberty-no-rx'),('004','champion'),('006','freedom'),('008','liberty')]:
        page=f'https://www.ericksonadvantage.com/plans/{slug}-2026'
        urls=[(page,'discovery')]
        for url,kind in urls:
            old=next((x for x in mf['sources'] if x['url']==url),None)
            if old:r=old
            else:
                host=urllib.parse.urlparse(url).hostname
                if host in mf['stops']:continue
                r={'offering_id':f'2026:H5652:{number}:000','url':url,'kind':kind,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'accepted':False,'reuse_status':'research capture; consumer reuse not approved'}
                try:
                    with urllib.request.urlopen(url,timeout=45) as q:b=q.read();r.update(final_url=q.url,content_type=q.headers.get('Content-Type'))
                    sha=hashlib.sha256(b).hexdigest();f=raw/sha;f.write_bytes(b)
                    r.update(status='acquired',sha256=sha,path=str(f),bytes=len(b))
                    if kind!='discovery':
                        if not b.startswith(b'%PDF'):raise ValueError('Expected PDF')
                        subprocess.run(['pdftotext','-layout',str(f),str(f)+'.txt'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                        r['text_path']=str(f)+'.txt';r['text_sha256']=hashlib.sha256(pathlib.Path(r['text_path']).read_bytes()).hexdigest()
                except urllib.error.HTTPError as e:
                    r.update(status='unavailable',http_status=e.code,reason=str(e))
                    if e.code in [401,403,429]:mf['stops'][host]=f'HTTP {e.code}; no retry or alternate route'
                except Exception as e:r.update(status='unavailable',reason=str(e))
                mf['sources'].append(r);mfpath.write_text(json.dumps(mf,indent=2)+'\n')
                print(number,kind,r['status'],flush=True)
            if kind=='discovery' and r['status']=='acquired':
                p=Links();p.feed(pathlib.Path(r['path']).read_text())
                for u in dict.fromkeys(p.links):
                    if u.startswith('https://media.ericksonliving.com/ea/2026/Plans/'):
                        k='SB' if 'summary-en.pdf' in u else 'EOC' if 'eoc-en.pdf' in u else 'ANOC' if 'anoc-en.pdf' in u else None
                        if k:urls.append((u,k))
    return mf
if __name__=='__main__':acquire()
