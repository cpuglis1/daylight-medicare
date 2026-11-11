"""Additive L10 gap research using retained census and public OIR metadata.

Only ordinary filing/attachment metadata is read. No request, challenge,
comment, restricted document content or download endpoint is called.
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import http.cookiejar
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l10-medigap-2026-10-28'
WORK=BASE/'gap-resolution-r4'
ACQ=WORK/'acquisition'
LOCAL=threading.local()


def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def inventory():
    target=WORK/'case-index.json'
    if target.exists():return read(target)
    grouped={}
    for line in (BASE/'build-r2/filing-metadata.jsonl').open():
        x=json.loads(line);n=x['source_native'];key=(n['AppSrc'],n['FileLogNumber'],n['FilingId'])
        rec=grouped.setdefault(key,{'case':n['FileLogNumber'],'app_src':n['AppSrc'],'filing_id':n['FilingId'],
            'filed_date':n['FileDt'],'closed_date':n['CloseDt'],'filing_type':n['FilingType'],
            'final_action':n['FinalAction'],'restricted':n['IsRestricted'],'companies':set(),'naics':set(),
            'forms':set(),'market_names':set(),'source_row_ids':[]})
        rec['companies'].add(n['CoNm']);rec['naics'].add(str(n['NaicCoCd']))
        if n['FormNum']:rec['forms'].add(n['FormNum'])
        if n['MktNm']:rec['market_names'].add(n['MktNm'])
        rec['source_row_ids'].append(x['id'])
    cases=[]
    for key,rec in sorted(grouped.items(),key=lambda kv:str(kv[0])):
        for name in ['companies','naics','forms','market_names']:rec[name]=sorted(rec[name])
        rec['selected_for_metadata']=rec['final_action']=='APPROVED' and rec['filing_type'] in ['Rates','Both'] and rec['filed_date'][-4:] in ['2024','2025','2026']
        rec['selection_basis']='All retained approved rate/Both filings submitted 2024-2026, every company; earlier records stay indexed, not presumed expired'
        cases.append(rec)
    write(target,cases);return cases


class Session:
    def __init__(self):
        self.opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with self.opener.open('https://irfssearch.floir.gov/',timeout=45) as r:
            html=r.read(400000).decode()
        token=re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"',html)
        if not token:raise ValueError('Ordinary source session changed; stop')
        self.token=token[1]

    def post(self,sid,endpoint,fields):
        if endpoint not in ['/Search/GetFiling','/Search/GetDocuments']:raise ValueError('Metadata endpoints only')
        receipt=ACQ/(sid+'.json')
        if receipt.exists():
            r=read(receipt);assert r['inputs']==fields and r['endpoint']==endpoint
            raw=(ACQ/'raw'/r['sha256']).read_bytes();assert hashlib.sha256(raw).hexdigest()==r['sha256']
            return json.loads(raw)
        time.sleep(1)
        req=Request('https://irfssearch.floir.gov'+endpoint,data=urlencode({**fields,'__RequestVerificationToken':self.token}).encode(),
                    headers={'__RequestVerificationToken':self.token,'User-Agent':'DaylightPublicEvidenceResearch/1.0',
                             'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'})
        with self.opener.open(req,timeout=60) as response:
            raw=response.read(16000001)
            if response.code!=200 or len(raw)>16000000:raise ValueError('Source status/size stop')
            data=json.loads(raw)
            receipt_data={'source_id':sid,'endpoint':endpoint,'requested_url':req.full_url,'final_url':response.url,
                          'method':'POST','inputs':fields,'http_status':response.code,'bytes':len(raw),
                          'sha256':hashlib.sha256(raw).hexdigest(),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
                          'purpose':'Public metadata only; no request, challenge or restricted content','retries':0}
        (ACQ/'raw'/receipt_data['sha256']).write_bytes(raw);write(receipt,receipt_data);return data


def retained_detail(case):
    for d in read(BASE/'build-r2/filing-details.json'):
        if d['source_native']['FileLogNumber']==case:return d['source_native'],d['source_id']
    p=BASE/'filing-reconciliation-r3/metadata-r1'/(case+'-detail.json')
    if p.exists():return read(p),str(p.relative_to(ROOT))
    return None,None


def inspect_case(rec):
    if (WORK/'build-r1/SEALED').exists():raise ValueError('Sealed research revision; use a new revision')
    if rec['restricted']:return {'case':rec['case'],'state':'source_restricted_not_opened'}
    if not hasattr(LOCAL,'session'):LOCAL.session=Session()
    session=LOCAL.session;case=rec['case'];src=rec['app_src'];fid=rec['filing_id'] or ''
    detail,basis=retained_detail(case)
    if detail is None:
        detail=session.post(f'detail-{src}-{case}','/Search/GetFiling',{'fn':case,'id':fid,'src':src});basis='new_metadata_receipt'
    listing=session.post(f'attachments-{src}-{case}','/Search/GetDocuments',{'fn':case,'fid':fid,'src':src})
    if listing.get('IsRestricted'):
        result={'case':case,'state':'attachment_index_restricted_no_content_opened','detail':detail,'detail_basis':basis}
    else:
        docs=[{'title':d['DocumentTitle'],'type':d['DocumentType'],'status':d['DocumentStatus'],
               'date':d['DocumentDate'],'trade_secret':d['IsTradeSecret'],'stamped':d['IsStamped'],
               'sequence_id':d.get('SequenceId')} for d in listing.get('Documents',[])]
        result={'case':case,'state':'public_metadata_only','detail':detail,'detail_basis':basis,'documents':docs,
                'document_count':len(docs),'public_document_count':sum(not d['trade_secret'] for d in docs),
                'actual_rate_period':'not_established_by_metadata_or_title'}
    write(WORK/'filings'/(case+'.json'),result);return {'case':case,'state':result['state']}


def acquire(workers=3):
    if (WORK/'build-r1/SEALED').exists():raise ValueError('Sealed research revision; use a new revision')
    for p in [WORK/'filings',ACQ/'raw']:p.mkdir(parents=True,exist_ok=True)
    selected=[r for r in inventory() if r['selected_for_metadata']]
    results=[];failures=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(inspect_case,r):r for r in selected}
        for future in as_completed(futures):
            rec=futures[future]
            try:results.append(future.result())
            except Exception as e:
                failures.append({'case':rec['case'],'error':type(e).__name__,'reason':str(e),'state':'source_failure_no_retry'})
            if (len(results)+len(failures))%25==0:print(json.dumps({'inspected':len(results),'failures':len(failures),'selected':len(selected)}),flush=True)
    result={'selected_cases':len(selected),'inspected':sorted(results,key=lambda x:x['case']),
            'failures':failures,'complete_selected_metadata':len(results)==len(selected),'full_market_census_complete':False}
    write(WORK/'acquisition-status.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['inspected','failures']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inventory',action='store_true');a=p.parse_args()
    if a.inventory:
        rows=inventory();print(json.dumps({'indexed_cases':len(rows),'selected':sum(r['selected_for_metadata'] for r in rows)},indent=2))
    else:acquire()
