"""L03 r3 evidence helpers and explicit-URL permitted source capture.

Prior versions and source stops are preserved. No user/member data is sent.
"""
from __future__ import annotations
import datetime,hashlib,json,pathlib,re,subprocess,urllib.request,urllib.error,urllib.parse
from l03_reference_build import DATA,sha,dump

R1=DATA/'build-r1';R2=DATA/'reconciliation-r2';R3=DATA/'reconciliation-r3'
CATALOG={x['sha256']:x for x in json.loads((R1/'carrier-document-catalog.json').read_text())}
MATRIX={x['offering_id']:x for x in json.loads((R1/'plan-document-matrix.json').read_text())}
PAGES={}
def doc(oid,kind='EOC'):
    d=MATRIX[oid]['document_matches'][kind]
    if d['status']!='matched_for_research':raise ValueError('Restricted/unmatched offering')
    return CATALOG[d['sha256']]
def pages(oid,kind='EOC'):
    d=doc(oid,kind);h=d['sha256']
    if h not in PAGES:
        p=pathlib.Path(d['text_path']).read_text().split('\f')
        if not p[-1].strip():p.pop()
        PAGES[h]=p
    return PAGES[h]
def evidence(oid,kind,page,start=1,end=None):
    d=doc(oid,kind);p=pages(oid,kind)[page-1];ls=p.splitlines();end=len(ls) if end is None else end
    return {'document_sha256':d['sha256'],'url':d['url'],'kind':kind,'pdf_page':page,'page_text_sha256':sha(p.encode()),'line_start':start,'line_end':end,'text':'\n'.join(ls[start-1:end])}
def find(oid,pattern,kind='EOC',context=4,chapter=None):
    result=[]
    for n,p in enumerate(pages(oid,kind),1):
        if chapter is not None and not re.search(r'Chapter\s+'+str(chapter)+r'(?:\.|\s)',p[:800],re.I):continue
        ls=p.splitlines()
        for i,l in enumerate(ls):
            if re.search(pattern,l,re.I):result.append(evidence(oid,kind,n,max(1,i+1-context),min(len(ls),i+1+context)))
    return result

def acquire(url,id,kind='discovery'):
    R3.mkdir(exist_ok=True);raw=R3/'acquisition';raw.mkdir(exist_ok=True);mp=R3/'source-manifest.json'
    m=json.loads(mp.read_text()) if mp.exists() else {'sources':[],'stops':json.loads((DATA/'source-manifest.json').read_text())['stops']}
    old=next((x for x in m['sources'] if x['url']==url),None)
    if old:return old
    def stopped(url):
        host=urllib.parse.urlparse(url).hostname or ''
        return any(host==h or host.endswith('.'+h) for h in m['stops'])
    if stopped(url):raise ValueError('Inherited source stop: '+url)
    r={'id':id,'url':url,'kind':kind,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'accepted':False,'use':'published-source research; no personal applicability or consumer release'}
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if stopped(newurl):raise ValueError('Redirect to stopped source')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    try:
        with urllib.request.build_opener(Redirect).open(url,timeout=45) as q:b=q.read();r.update(final_url=q.url,content_type=q.headers.get('Content-Type'),last_modified=q.headers.get('Last-Modified'))
        h=sha(b);f=raw/h;f.write_bytes(b);r.update(status='acquired',sha256=h,path=str(f),bytes=len(b))
        if b.startswith(b'%PDF'):
            t=raw/(h+'.txt');subprocess.run(['pdftotext','-layout',str(f),str(t)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);r.update(text_path=str(t),text_sha256=sha(t.read_bytes()))
    except urllib.error.HTTPError as e:
        r.update(status='unavailable',http_status=e.code,reason=str(e))
        if e.code in [401,403,429]:m['stops'][urllib.parse.urlparse(url).hostname]=f'HTTP {e.code}; no retry/bypass'
    except Exception as e:r.update(status='unavailable',reason=str(e))
    m['sources'].append(r);dump(mp,m);print(id,r['status'],r.get('bytes'),flush=True);return r

if __name__=='__main__':
    import sys
    if sys.argv[1]=='acquire':acquire(*sys.argv[2:])
    elif sys.argv[1]=='find':
        for x in find(sys.argv[2],sys.argv[3],sys.argv[4] if len(sys.argv)>4 else 'EOC'):print(json.dumps(x,ensure_ascii=False))
