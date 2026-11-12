"""Retain complete Humana publications and source-located address observations.

Native address observations are not unique clinicians. No NPI, specialty, or
plan participation is supplied by a fuzzy name match or a missing search result.
"""
import gzip,json,re,subprocess,xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from l08_r3_common import BASE,ROOT,PARENT,write,digest,assert_open
import sqlite3

CITY=re.compile(r'^(?P<city>.+?),\s*(?P<state>[A-Z]{2})\s+(?P<postal>\d{5}(?:-\d{4})?)$')
PHONE=re.compile(r'^\(\d{3}\)\s*\d{3}-\d{4}')
PLAN=re.compile(r'\b([HR]\d{4})-(\d{3})-(\d{3})\b')
STREET_START=re.compile(r'^\d+[A-Za-z]?(?:\s+\S|[A-Za-z]{2,})')

def extract(r):
    sh=r['sha256'];src=ROOT/r['path'];txt=ROOT/r['text_path']
    pages=txt.read_text().split('\f');n=int(re.search(r'^Pages:\s+(\d+)',r['pdfinfo'],re.M)[1])
    assert len(pages)==n+1 and not pages[-1].strip()
    front='\f'.join(pages[:25]);scopepage=None;geography=None
    for i,page in enumerate(pages[:10],1):
        m=re.search(r'This directory is for providers in the following State\(s\) or counties:\s*\n(.*?)(?:\n\s*\n)',page,re.S)
        if m:
            geography=m[1].strip()
            if re.search(r'\bCollier\b',geography):scopepage=i
            break
    applicable=scopepage is not None
    inventory={**r,'pages':n,'collier_geography_explicit':applicable,'geography_page':scopepage,'geography_raw':geography,
               'partial_list_explicit':'This is a partial list' in pages[0],
               'publication_date_raw':re.search(r'\b10/\d{2}/2026\b',pages[0])[0],
               'benefit_year':2026,'exact_plan_mentions':[],
               'state':'applicable_Collier_partial_directory'if applicable else'other_region_retained_not_used_for_Collier'}
    if not applicable:return inventory
    for i,page in enumerate(pages[:25],1):
        for m in PLAN.finditer(page):
            pid='2026:'+':'.join(m.groups())
            inventory['exact_plan_mentions'].append({'offering_id':pid,'page':i,'span':list(m.span()),'raw':m[0]})
    xp=BASE/'xml'/(sh+'.xml');gz=BASE/'xml'/(sh+'.xml.gz')
    if not gz.exists():
        subprocess.run(['pdftohtml','-xml','-hidden','-i','-zoom','1',str(src),str(xp)],check=True,capture_output=True)
        with gzip.open(gz,'wb')as out:out.write(xp.read_bytes())
        xp.unlink()
    inventory['xml_path']=str(gz.relative_to(ROOT));inventory['xml_sha256']=digest(gz.read_bytes())
    return inventory

def parse_doc(inv):
    nodes=[];fonts={};pagecount=0
    with gzip.open(ROOT/inv['xml_path'],'rb')as stream:
        for _,page in ET.iterparse(stream,events=('end',)):
            if page.tag!='page':continue
            pagecount+=1;pg=int(page.attrib['number'])
            for f in page.findall('fontspec'):fonts[f.attrib['id']]=dict(f.attrib)
            for j,e in enumerate(page.findall('text')):
                t=''.join(e.itertext()).strip()
                if not t:continue
                nodes.append({'page':pg,'node':j,'text':t,'top':int(e.attrib['top']),
                              'left':int(e.attrib['left']),'width':int(e.attrib['width']),
                              'height':int(e.attrib['height']),'font':fonts[e.attrib['font']]})
            page.clear()
    assert pagecount==inv['pages']
    sh=inv['sha256'];native=BASE/'native'/(sh+'.jsonl.gz')
    with gzip.open(native,'wt')as out:
        for x in nodes:out.write(json.dumps(x,ensure_ascii=False)+'\n')
    inv['native_path']=str(native.relative_to(ROOT));inv['native_sha256']=digest(native.read_bytes());inv['native_nodes']=len(nodes)
    # Four publisher columns in reading order. Front matter, translation tables,
    # name index and source-only fragments are retained in full native/page data.
    # Only pages whose title is a clinical/provider section are modeled here.
    bypage={}
    for k,x in enumerate(nodes):x['native_index']=k;bypage.setdefault(x['page'],[]).append(x)
    stream=[];section=None;medical_pages=[];section_sources={};last_section_nodes=[]
    for pg,xs in bypage.items():
        heads=[x for x in xs if x['top']<70 and 'BoldItalic' in x['font']['family'] and int(x['font']['size'])>=17]
        if heads:
            section=' '.join(x['text']for x in heads)
            last_section_nodes=[x['native_index']for x in heads]
        if pg<35 or not section or re.search('Index|Índice|Directory|Directorio',section,re.I):continue
        medical_pages.append(pg);section_sources[pg]=last_section_nodes
        for col in range(4):
            xs2=sorted([x for x in xs if 72<=x['top']<755 and 30+136*col<=x['left']<166+136*col],key=lambda x:(x['top'],x['left'],x['node']))
            stream.extend((x,section,col)for x in xs2)
    outrows=[];county=None;lastbold=[];last_section=None;phoneless=0;citycount=0
    for k,(x,section,col)in enumerate(stream):
        t=x['text'];font=x['font']['family']
        if section!=last_section:lastbold=[];last_section=section
        if t.endswith(' COUNTY')and'Heavy'in font:county=x;lastbold=[]
        if 'Bold'in font and'Italic'not in font and not t.endswith('COUNTY'):
            prev=stream[k-1][0]if k else None
            if lastbold and prev is lastbold[-1]and prev['page']==x['page']and prev['left']==x['left']and 0<x['top']-prev['top']<=15:lastbold.append(x)
            else:lastbold=[x]
        m=CITY.match(t)
        if not m:continue
        citycount+=1
        preceding=[]
        for j in range(k-1,max(-1,k-5),-1):
            y,sec,c=stream[j]
            if y['page']!=x['page']or c!=col or 'Bold'in y['font']['family']or PHONE.match(y['text'])or CITY.match(y['text']):break
            preceding.insert(0,y)
            if STREET_START.match(y['text']):break
        address_nodes=preceding if preceding and STREET_START.match(preceding[0]['text'])else[]
        # Names are tracked in geometric reading order. Native PDF object order
        # is not a reliable ordering across columns or continued records.
        names=lastbold if lastbold and lastbold[-1]['page']>=x['page']-1 else[]
        nexts=[]
        for j in range(k+1,min(len(stream),k+12)):
            y,sec,c=stream[j]
            if sec!=section:break
            if (y['page']!=x['page']or c!=col)and not nexts and not PHONE.match(y['text']):break
            if 'Bold'in y['font']['family']and'Italic'not in y['font']['family']:break
            if CITY.match(y['text'])or STREET_START.match(y['text']):break
            nexts.append(y)
        phones=[y for y in nexts if PHONE.match(y['text'])]
        if not phones:phoneless+=1
        raw={'name_candidate_raw':' '.join(y['text']for y in names)or None,
             'street_raw':' '.join(y['text']for y in address_nodes)or None,
             'city_raw':m['city'],'state_raw':m['state'],'postal_raw':m['postal'],
             'phone_raw':phones[0]['text']if phones else None,
             'county_context_raw':county['text']if county else None,'section_raw':section,
             'conditions_raw':[y['text']for y in nexts if not PHONE.match(y['text'])]}
        loc={'name_candidate_raw':[y['native_index']for y in names],'street_raw':[y['native_index']for y in address_nodes],
             'city_state_postal':[x['native_index']],'phone_raw':[phones[0]['native_index']]if phones else[],
             'county_context_raw':[county['native_index']]if county else[],
             'conditions_raw':[y['native_index']for y in nexts if not PHONE.match(y['text'])],
             'section_raw':section_sources[x['page']]}
        outrows.append({'id':sh+':address:'+str(x['native_index']),'document_sha256':sh,'page':x['page'],'column':col,
                        'fields':raw,'locators':loc,'native_path':inv['native_path'],
                        'native_city_node':x['native_index'],'state':'published_address_observation; name association candidate; no unique clinician or personal guarantee',
                        'benefit_year':2026,'publication_date_raw':inv['publication_date_raw'],
                        'printed_county_is_collier':raw['county_context_raw']=='COLLIER COUNTY'})
    inv['address_observations']=len(outrows);inv['city_zip_anchors_accounted']=citycount;inv['no_nearby_phone']=phoneless
    inv['modeled_pages']=medical_pages
    return outrows

def main():
    assert_open();(BASE/'xml').mkdir(exist_ok=True);(BASE/'native').mkdir(exist_ok=True)
    source=json.loads((BASE/'new-pdf-inventory.json').read_text())
    invs=list(ThreadPoolExecutor(max_workers=2).map(extract,source))
    targets={r[0]for r in sqlite3.connect('file:'+str(PARENT/'followup-r2/providers.sqlite3')+'?mode=ro',uri=True).execute('select id from offerings')}
    bindings=[];stats=Counter()
    with gzip.open(BASE/'humana-address-observations.jsonl.gz','wt')as out:
        for inv in invs:
            if not inv['collier_geography_explicit']:continue
            mentions={x['offering_id']for x in inv['exact_plan_mentions']}
            inv['target_offerings']=sorted(mentions&targets)
            for pid in inv['target_offerings']:
                bindings.append({'offering_id':pid,'document_sha256':inv['sha256'],
                                 'state':'published_exact_plan_directory; explicitly_partial',
                                 'plan_mentions':[x for x in inv['exact_plan_mentions']if x['offering_id']==pid],
                                 'geography_page':inv['geography_page'],'publication_date_raw':inv['publication_date_raw']})
            for r in parse_doc(inv):
                out.write(json.dumps(r,ensure_ascii=False)+'\n');stats['address_observations']+=1
                if r['printed_county_is_collier']:stats['Collier_county_heading_observations']+=1
    write(BASE/'humana-document-inventory.json',invs);write(BASE/'humana-plan-document-bindings.json',bindings)
    write(BASE/'humana-extraction-summary.json',dict(stats,exact_target_plans_with_published_directory=len({x['offering_id']for x in bindings}),
       applicable_documents=sum(x['collier_geography_explicit']for x in invs),published_rosters_explicitly_partial=True))
    print(json.dumps(json.loads((BASE/'humana-extraction-summary.json').read_text())))

if __name__=='__main__':main()
