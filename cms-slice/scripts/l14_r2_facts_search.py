"""One bounded public FACTS contract search; no personal data or form enrollment."""
import hashlib,json
from datetime import datetime,timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor,Request,build_opener
from l14_r2_acquire import ACQ,BASE,ROOT,Redirects,write

class Form(HTMLParser):
    def __init__(self):super().__init__();self.hidden={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='input' and a.get('type')=='hidden':self.hidden[a['name']]=a.get('value','')

def search():
    if (BASE/'build-r2/manifest.json').exists():raise ValueError('Sealed')
    dest=ACQ/'receipts/fl-facts-hope-ahca-search.json'
    if dest.exists():raise ValueError('One search already recorded')
    url='https://facts.fldfs.com/Search/ContractSearch.aspx'
    opener=build_opener(Redirects(),HTTPCookieProcessor(CookieJar()))
    def retain(sid,response,method,query):
        with response:
            b=response.read(12000001)
            blocked=response.code in [401,403,429] or any(s in b.lower() for s in [b'challenge-platform',b'captcha-delivery'])
            sha=hashlib.sha256(b).hexdigest();path=ACQ/'raw'/sha;path.write_bytes(b)
            r=dict(id=sid,url=url,final_url=response.url,http_status=response.code,
                   retrieved_at_utc=datetime.now(timezone.utc).isoformat(),path=str(path.relative_to(ROOT)),
                   bytes=len(b),sha256=sha,content_type=response.headers.get('Content-Type'),
                   status='retained' if response.code==200 and not blocked and len(b)<=12000000 else 'failed',
                   access_stop=blocked,method=method,public_search_parameters=query,retry_count=0)
            write(ACQ/'receipts'/(sid+'.json'),r)
            if r['status']!='retained':raise ValueError('Search stopped')
            return b
    b=retain('fl-facts-search-session',opener.open(Request(url,headers={'User-Agent':'DaylightPublicEvidenceResearch/1.0'}),timeout=40),'GET',{})
    form=Form();form.feed(b.decode())
    params={'ctl00$PC$ddlAgency':'680000','ctl00$PC$txtVendorName':'HOPE',
            'ctl00$PC$txtConntractValueFrom':'','ctl00$PC$txtConntractValueTo':'',
            'ctl00$PC$txtBeginDate':'','ctl00$PC$txtEndDate':'','ctl00$PC$ddlCommodityGroup':'',
            'ctl00$PC$rblSrchOption':'','ctl00$PC$txtAgencyContractId':'',
            'ctl00$PC$txtGrantId':'','ctl00$PC$txtPOId':'','ctl00$PC$btnSearch':'Search'}
    request=Request(url,data=urlencode({**form.hidden,**params}).encode(),headers={'User-Agent':'DaylightPublicEvidenceResearch/1.0','Content-Type':'application/x-www-form-urlencoded'})
    retain('fl-facts-hope-ahca-search',opener.open(request,timeout=40),'POST',params)
    print('Public HOPE/AHCA search retained; no hidden session fields printed.')

if __name__=='__main__':search()
