#!/usr/bin/env python3
"""Offline document applicability and comparison worklist for the L03 reference.
Keyword-located passages are candidates, never automatic corroboration.
"""
from __future__ import annotations
import collections,csv,gzip,html,io,json,pathlib,re,zipfile
from decimal import Decimal
from l03_reference_build import DATA,L02,PBP_SHA,sha,dump

CONCEPTS={
 'plan_premium':r'monthly.{0,15}(?:plan )?premium|plan premium',
 'part_b_reduction':r'part b.{0,20}(?:reduction|premium)|giveback',
 'medical_deductible':r'medical deductible|annual deductible|these plans? do(?:es)? not have a deductible',
 'medical_moop':r'out.of.pocket.{0,25}(?:maximum|responsibility|limit)|maximum.{0,25}out.of.pocket',
 'drug_structure':r'part d|prescription drug|pharmacy.{0,20}deductible',
 'inpatient':r'inpatient hospital|inpatient stay',
 'psychiatric_inpatient':r'psychiatric hospital|inpatient mental|mental health.{0,30}inpatient',
 'skilled_nursing':r'skilled nursing',
 'rehabilitation':r'cardiac rehabilitation|pulmonary rehabilitation|rehabilitation services',
 'emergency':r'emergency care|emergency services|emergency room',
 'urgent':r'urgently needed|urgent care',
 'home_health':r'home health',
 'primary_care':r'primary care|provider of choice',
 'specialist':r'specialist',
 'diagnostics':r'diagnostic|laboratory services|x.ray',
 'outpatient_hospital':r'outpatient hospital|ambulatory surg|observation services',
 'transportation':r'ambulance|transportation',
 'equipment':r'durable medical|prosthetic|orthotic|medical supplies',
 'dialysis':r'dialysis',
 'preventive':r'preventive|wellness visit',
 'part_b_drugs':r'part b.{0,20}drugs|chemotherapy',
 'dental':r'dental', 'vision':r'vision|eyewear', 'hearing':r'hearing',
 'supplemental':r'fitness|over.the.counter|meals|acupuncture|telehealth|health education|chiropractic',
 'conditional':r'chronically ill|ssbci|special supplemental|eligibility.{0,30}benefit',
 'authorization_referrals':r'prior authorization|referral',
 'travel':r'worldwide|travel|visitor',
 'exclusions':r'exclusions|services.{0,20}not cover|limitations',
 'revisions':r'errata|amendment|addendum|rider|correction',
}
BLUE={
 'H1035-019':('fbm2518','fbm2487','BLUE-CLASSIC-ROUTE'),
 'H1035-045':('fbm2523','fbm2496','BLUE-PREMIER-ROUTE'),
 'H5434-002':('fbm2526','fbm2501','BLUE-SELECT-ROUTE'),
 'H5434-042':('fbm2537','fbm2515','BLUE-PATRIOT-ROUTE'),
 'H5434-045':('fbm2527','fbm2502','BLUE-SELECT-ROUTE'),
}

def readpath(root,value):
    p=pathlib.Path(value);return p if p.is_absolute() else root/p

def build(root=DATA):
    out=root/'build-r1';mf=json.loads((root/'source-manifest.json').read_text());offerings=json.loads((out/'market-manifest.json').read_text())['observed_offerings']
    sources=mf['sources'];catalog=[];byhash={}
    for s in sources:
        if s.get('status')!='acquired' or not s.get('path'):continue
        path=readpath(root,s['path']);b=path.read_bytes()
        if sha(b)!=s['sha256']:raise ValueError('Source bytes changed '+s['id'])
        if not b.startswith(b'%PDF'):continue
        if s['sha256'] in byhash:byhash[s['sha256']]['aliases'].append(s['id']);continue
        text=readpath(root,s['text_path']).read_text();pages=text.split('\f')
        if not pages[-1].strip():pages.pop()
        first='\n'.join(pages[:3]);typ='SB' if ('Summary of Benefits' in first or 'Resumen de Beneficios' in first) and not ('Evidence of Coverage for' in first or 'Evidencia de cobertura para' in first) else 'EOC' if any(x in first.lower() for x in ['evidence of coverage','evidencia de cobertura']) else 'supplemental_detail'
        language='Spanish' if any(x in first.lower() for x in ['evidencia de cobertura','resumen de beneficios']) else 'English_or_unconfirmed'
        c={'id':s['id'],'aliases':[s['id']],'url':s.get('final_url',s['url']),'sha256':s['sha256'],'path':str(path),'text_path':str(readpath(root,s['text_path'])),
           'text_sha256':sha(readpath(root,s['text_path']).read_bytes()),'pdf_pages':len(pages),'document_kind':typ,'language':language,
           'year_2026_in_first_three_pages':'2026' in first,'plan_ids_in_first_three_pages':sorted(set(re.findall(r'[HR]\d{4}[ _-]\d{3}',first))),
           'source_acceptance':'pending','pages':pages,'first':first}
        byhash[c['sha256']]=c;catalog.append(c)
    def find(pred):return next((x for x in catalog if any(pred(a) for a in x['aliases']) and x['language']!='Spanish'),None)
    matrix=[]
    with zipfile.ZipFile(L02/'acquisition-r1/raw'/PBP_SHA) as z:
      for o in offerings:
        oid=o['id'];cp=o['contract']+'-'+o['plan'];matches={};basis=None;route=None
        if o['parent']=='Humana Inc.':
            code=o['contract']+o['plan']+o['segment'];matches={k:find(lambda a,k=k: a==oid+':'+k or (k=='SB' and a=='P26-N01:Humana:'+cp)) for k in ['SB','EOC']};basis='Exact year/contract/plan/segment in carrier asset URL, document title/ID checked against PBP.'
        elif cp in BLUE:
            sb,eoc,routeid=BLUE[cp];matches={'SB':find(lambda a:sb in a or (cp=='H1035-045' and a=='P26-N01:Guidewell:Premier')),'EOC':find(lambda a:eoc in a)}
            route=next(s for s in sources if s['id']==routeid);basis='Official carrier route links the 2026 county-specific EOC/SB; SB prints exact contract-plan and Collier. Segment checked against national PBP keys.'
        elif o['parent']=='Health Care Service Corporation':
            matches={k:find(lambda a,k=k:a=='HEALTHSPRING:'+cp+':'+k.lower()) for k in ['SB','EOC']};basis='Carrier plan-keyed 2026 PDF, exact contract-plan on cover; Collier on SB. Segment checked against national PBP keys.'
        elif o['parent']=='CVS Health Corporation':
            matches={k:find(lambda a,k=k:a=='AETNA:'+cp+':'+k+':VERIFIED-URL') for k in ['SB','EOC']};basis='Rendered 2026 exact-plan carrier page links these English SB/EOC; document ID and cover checked. Segment checked against national PBP keys.'
        elif o['parent']=='Elevance Health, Inc.':
            code=('FH26' if o['contract']=='H5427' else 'OP26')+o['plan'];result=next((s for s in sources if s['id']=='ELEVANCE:'+code+':RESULTS'),None)
            if result:
                text=readpath(root,result['path']).read_text();urls={}
                for u,label in re.findall(r'''<a[^>]+href=["']([^"']+)["'][^>]*>(.*?)</a>''',text,re.S):
                    label=re.sub('<[^>]+>',' ',label).strip()
                    if label in ['Summary of Benefits','Evidence of Coverage']:urls['SB' if label.startswith('Summary') else 'EOC']=html.unescape(u)
                matches={k:next((byhash.get(source.get('sha256')) for source in sources if source.get('url','').replace('/dlsecure/?','/dlsecure?')==u.replace('/dlsecure/?','/dlsecure?')),None) for k,u in urls.items()};route=result
            basis='Public carrier document search selected 2026/Collier/exact plan; multi-plan SB column must remain plan-specific; EOC is plan-keyed.'
        segments=sorted(n.split('-')[2] for n in z.namelist() if n.startswith(cp+'-') and n.endswith('-2026.json'))
        row={'offering_id':oid,'parent':o['parent'],'name':o['name'],'national_pbp_segments_for_contract_plan':segments,'document_matches':{},
             'rider_amendment_inventory':'not proven exhaustive; only observed documents/references retained','accepted':False}
        for kind in ['SB','EOC']:
            c=matches.get(kind)
            if c:
                printed=cp in c['first'] or cp.replace('-','_') in c['first'] or cp.replace('-','') in c['first']
                if o['parent']=='Elevance Health, Inc.':printed=printed or ('_'+o['plan'] in c['first']) or o['name'].split(' (')[0].lower() in c['first'].lower()
                # Blue EOC omits plan ID on cover; official county-specific link is additional evidence.
                explicit_segment=bool(re.search(o['contract']+r'[-_ ]?'+o['plan']+r'[-_ ]?'+o['segment']+r'(?:\D|$)',c['first']))
                segment_ok=segments==[o['segment']] or explicit_segment
                ok=c['year_2026_in_first_three_pages'] and segment_ok and (printed or o['parent']=='Guidewell Mutual Holding Corporation' and kind=='EOC')
                row['document_matches'][kind]={'status':'matched_for_research' if ok else 'applicability_review_required','document_id':c['id'],'sha256':c['sha256'],'url':c['url'],
                    'basis':basis,'year_on_cover':c['year_2026_in_first_three_pages'],'contract_plan_in_first_three_pages':printed,
                    'segment_basis':'explicit asset/document segment' if explicit_segment else 'only matching 2026 national PBP segment' if segment_ok else 'unresolved',
                    'route_id':route.get('id') if route else None,'county_check':'Collier in SB / official 2026 Collier document-search result' if ('Collier' in c['first'] or 'COLLIER' in c['first'] or o['parent']=='Elevance Health, Inc.') else 'check supporting SB/route; not a new availability acceptance'}
            else:
                why='Inherited UHC HTTP 403 stop' if 'UnitedHealth' in o['parent'] else 'Inherited Wellcare systematic/commercial collection restriction' if 'Centene' in o['parent'] else 'Exact document not located'
                row['document_matches'][kind]={'status':'restricted' if any(x in o['parent'] for x in ['UnitedHealth','Centene']) else 'missing','reason':why}
        matrix.append(row)
    # Page index preserves exact page context; phrase matches only locate potential evidence.
    passages=[]
    with gzip.open(out/'carrier-pages.jsonl.gz','wt',encoding='utf-8') as f:
        for c in catalog:
            for page,text in enumerate(c['pages'],1):f.write(json.dumps({'document_sha256':c['sha256'],'pdf_page':page,'text_sha256':sha(text.encode()),'text':text},ensure_ascii=False)+'\n')
    for row in matrix:
        for concept,pattern in CONCEPTS.items():
            evidence=[]
            for kind in ['SB','EOC']:
                doc=row['document_matches'][kind]
                if not doc.get('sha256'):continue
                c=byhash[doc['sha256']]
                found=[]
                for n,text in enumerate(c['pages'],1):
                    hits=list(re.finditer(pattern,text,re.I))
                    if hits:
                        found.append({'pdf_page':n,'page_text_sha256':sha(text.encode()),'hits':len(hits),
                                      'context':text[max(0,hits[0].start()-160):hits[0].end()+650]})
                evidence.append({'document_sha256':c['sha256'],'kind':kind,'matching_pages':len(found),'passages':found[:8]})
            passages.append({'offering_id':row['offering_id'],'concept':concept,'status':'candidate_passages_only' if any(x['matching_pages'] for x in evidence) else 'no_candidate_passage',
                             'evidence':evidence,'semantic_comparison':'not established by keyword matches','accepted':False})
    dump(out/'carrier-document-catalog.json',[{k:v for k,v in x.items() if k not in ['pages','first']} for x in catalog])
    dump(out/'plan-document-matrix.json',matrix)
    dump(out/'carrier-comparison-worklist.json',passages)
    stats={'observed_offerings':len(matrix),'minimum_SB_EOC_slots':2*len(matrix),'minimum_documents_note':'Not the exhaustive rider/amendment denominator.',
           'SB':dict(collections.Counter(x['document_matches']['SB']['status'] for x in matrix)),
           'EOC':dict(collections.Counter(x['document_matches']['EOC']['status'] for x in matrix)),
           'distinct_retained_pdfs':len(catalog),'retained_pdf_pages':sum(x['pdf_pages'] for x in catalog),'comparison_concepts':len(CONCEPTS),
           'concept_plan_worklist_rows':len(passages),'candidate_only_rows':sum(x['status']=='candidate_passages_only' for x in passages),'carrier_corroboration_from_keyword_search':0}
    dump(out/'document-coverage-summary.json',stats);print(json.dumps(stats,indent=2))

if __name__=='__main__':build()
