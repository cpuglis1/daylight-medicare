"""Reread source bytes and independently check every additive L14 modeled field."""
import csv,hashlib,io,json,re,sqlite3,subprocess,xml.etree.ElementTree as ET,zipfile
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from l12_sources import PublicHTML
from l14_r2_catalog import CLAIMS,GAPS

ROOT=Path(__file__).resolve().parents[2];PARENT=ROOT/'docs/data/l14-other-coverage-2026-10-29'
BASE=PARENT/'gap-resolution-r2';BUILD=BASE/'build-r2';VAL=BASE/'validation-r2'
PARENT_SHA='15d6e1d711cd590f280e7f92bd47c9d9b619481c6cd02570f3a83495c3fddedd'
def load(p):return json.loads(p.read_text())
def norm(t):return ' '.join(t.split())
def sha(b):return hashlib.sha256(b).hexdigest()
def fp(p):return dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
def need(ok,message):
    if not ok:raise ValueError(message)
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')

def guard_reference(r):
    need(r['benefit_year']==2026 and r['county_fips']=='12021','Wrong benefit period/geography')
    need(r['human_acceptance'] is None and r['qualified_R19_review'] is None,'Invented external review')
    need(not any(r[k] for k in ['full_l14_complete','consumer_release_enabled','personal_applicability_enabled']),'Unresolved reference released')
    need(r['data_gap_ids']==['G02','G03','G04'] and r['national_expansion_gap_ids']==['G06'] and r['review_gap_ids']==['G07'],'Gap silently waived')

def guard_state(s):
    need(s['county_fips']=='12021' and s['contract_id']=='H5934' and s['source_period']=='2026-09','Wrong state observation identity')
    need(all(s[k] is None for k in ['reported_open_slots','personal_premium','live_capacity']),'Historical count/rate became a personal claim')

def guard_msa(r):
    need(r['contract_id']=='H6130' and r['CMS_segment_id_source']=='0','Inexact MSA identity')
    need(all(r[k] is None for k in ['unified_plan_deductible','unified_plan_deposit','personal_quote']),'Conflicting MSA cost released')
    need(not r['deposit_is_guaranteed'] and not r['numeric_agreement_is_design_acceptance'],'Conditional deposit/design inferred')

def guard_profile(p):
    expected={'90091':'exact_case_not_determined','H4556':'4000_includes_Part_D_4100_has_no_drug_benefit',
              'H6142':'2025_UHS_brochure_allows_standalone_PDP','H6334':'sponsor_warns_retiree_benefit_termination'}
    need(p['id'] in expected and p['PDP_interaction']==expected[p['id']],'HCPP-specific PDP restriction lost')
    need(not p['unrestricted_public_enrollment'] and all(p[k] is None for k in ['Collier_provider_confirmed','personal_eligibility','acceptance']),'National note became personal access')

def guard_claim(r):
    need(r['qualified_review'] is None and r['acceptance'] is None and not r['personal_determination_enabled'],'Source observation inherited acceptance')
    if r['id'].startswith('UHS-'):need('2025' in r['source_edition'],'Wrong-year UHS evidence promoted')
    if r['id']=='HOTEL-MEMBERSHIP-AND-LOCAL-SERVICES':need('2014' in r['source_edition'],'Old SPD promoted')

def guard_audit(r):
    need(r['total_pages']==1 and r['count']==len(r['complete_results']),'Incomplete rule-search population')
    need(r['date_start']=='2025-01-01' and r['date_end']=='2026-10-29','Rule-search time window changed')
    need(r['final_ids']==[v['document_number'] for v in r['complete_results'] if v['type']=='Rule'],'Proposed rule promoted')

def guard_summary(r):
    need(not any(r[k] for k in ['area_only_ids_resolved','zero_pilots_proven','Collier_availability_proven_by_summary']),'Aggregate summary overclaim')
    need(r['PACE_contracts']==r['directory_PACE_contracts']==208 and r['area_PACE_contracts']==243,'National discrepancy lost')

def validate():
    need(not (BUILD/'manifest.json').exists(),'Sealed: use --verify via l14_r2_seal.py')
    parent=subprocess.run(['python3',str(ROOT/'cms-slice/scripts/l14_seal.py'),'--verify'],check=True,capture_output=True,text=True)
    parent_status=json.loads(parent.stdout);need(parent_status['manifest_sha256']==PARENT_SHA,'Parent hash')
    data={p.stem:load(p) for p in BUILD.glob('*.json')};ref=data['reference'];guard_reference(ref)
    new=load(BASE/'acquisition/extraction-index.json');reg=load(PARENT/'build-r1/source-registry.json')|new
    need(data['source-registry']==reg and data['new-source-registry']==new,'Registry changed')
    clauses={r['id']:r for r in load(PARENT/'build-r1/evidence.json')};expected_evidence=[];texts={};inputs=set();pdf_pages=0
    for sid,r in new.items():
        inputs.add(ROOT/r['receipt_path']);need(load(ROOT/r['receipt_path'])['status']==r['status'],'Receipt mismatch')
        if r['status']!='retained':
            need(r['id']=='cms-contract-summary-october-2026-page' and 'nodename' in r['reason'] and not r['access_stop'],'Unreported source-access block')
            continue
        raw=ROOT/r['path'];inputs.add(raw);need(fp(raw)=={k:r[k] for k in ['bytes','sha256']},'Raw source byte/hash mismatch '+sid)
        receipt=load(ROOT/r['receipt_path']);need(all(receipt[k]==r[k] for k in ['sha256','bytes','url','final_url','status']),'Source lineage changed')
        b=raw.read_bytes()
        if r.get('extraction_kind')=='tabular_archive':continue
        if b.startswith(b'%PDF'):
            t=subprocess.run(['pdftotext','-layout',str(raw),'-'],capture_output=True,check=True).stdout.decode()
            need(r['pdf_pages']==t.count('\f'),'PDF page accounting');pdf_pages+=t.count('\f')
        elif r['extraction_kind']=='public_json':
            v=json.loads(b);t=json.dumps(v,indent=2,sort_keys=True)+'\n';need(load(ROOT/r['structured_text_path'])==v,'JSON extraction loss')
        elif r['extraction_kind']=='federal_register_xml':
            tree=ET.fromstring(b);need(tree.tag=='RULE','Wrong FR document root')
            blocks=[dict(ordinal=i,title=n.get('TITLE'),part=n.get('PART'),text=norm(' '.join(n.itertext())),
                         section_numbers=[norm(' '.join(v.itertext())) for v in n.iter('SECTNO')]) for i,n in enumerate(tree.iter('REGTEXT'),1)]
            v=dict(root=tree.tag,regulatory_blocks=blocks,amendment_instructions=[norm(' '.join(n.itertext())) for n in tree.iter('AMDPAR')])
            need(load(ROOT/r['structured_text_path'])==v,'FR regulatory text omitted')
            t=norm(' '.join(tree.itertext()))+'\n'
        else:
            parser=PublicHTML();parser.feed(b.decode(errors='replace'));v=parser.result();t='\n'.join(v['lines'])+'\n'
            need(load(ROOT/r['structured_text_path'])==v,'HTML tables/links changed')
        texts[sid]=t;need((ROOT/r['text_path']).read_text()==t,'Source extraction mismatch '+sid);inputs.add(ROOT/r['text_path'])
        if r.get('structured_text_path'):inputs.add(ROOT/r['structured_text_path'])
        expected_evidence.append(dict(id=sid+':ALL',source_id=sid,locator='complete extracted source',text=norm(t)))
        if r.get('pdf_pages'):
            for i,p in enumerate(t.split('\f')[:-1],1):expected_evidence.append(dict(id=f'{sid}:PAGE:{i}',source_id=sid,locator={'physical_pdf_page':i},text=norm(p)))
    need(data['evidence']==expected_evidence,'Evidence inventory or complete passage changed')
    clauses.update({r['id']:r for r in expected_evidence})
    need(len(data['claims'])==len(CLAIMS)==14,'Claim denominator')
    for r,authored in zip(data['claims'],CLAIMS):
        guard_claim(r)
        need({k:r[k] for k in authored}==authored,'Modeled interpretation/condition changed '+r['id'])
        want=[dict(source_clause_id=k,text=clauses[k]['text']) for k in r['source_clause_ids']]
        need(r['source_conditions']==want,'Incomplete operative source context')
        for pattern in r['source_checks']:need(re.search(pattern,' '.join(v['text'] for v in want),re.I),'Missing claim source condition '+r['id'])
    # Independently locate every Collier mention, with a visually confirmed literal table fixture.
    s=data['state-observation'];guard_state(s);t=texts[s['source_id']];pages=t.split('\f')
    need([i for i,p in enumerate(pages,1) if re.search(r'\bCollier\b',p)]==[5,13],'New/unaccounted Collier row')
    op=next(x for x in pages[4].splitlines() if re.search(r'Hope PACE\s+Collier\s+Operational',x));co=next(x for x in pages[12].splitlines() if re.match(r'\s*Collier\s+Hope PACE',x))
    a=re.split(r'\s{2,}',op.strip());c=re.split(r'\s{2,}',co.strip())
    need(s['raw_operational_cells']==a==['Hope PACE','Collier','Operational','4/12/2012','N/A','120','120','95','$4,141.48','$376,874.68','$389,299.12','$393,440.60','$770,650.28'],'Operational table cell changed')
    need(s['raw_county_cells']==c==['Collier','Hope PACE','Operational','95','97'],'County table cell changed')
    want=dict(slots_approved=120,slots_funded=120,enrollment_first_of_month=95,actuarial_dual_rate_dollars=a[8],estimated_claims_source_cells=a[9:],county_current_month_enrollees=95,fiscal_year_unique_individuals=97,
              pending_additional_Collier_rows=[],report_updated='2026-10-01',posted_date='2026-10-27')
    need(all(s[k]==v for k,v in want.items()),'Typed state field changed')
    need('Updated 10/01/2026' in t and 'All counties within the state are reflected' in t,'Report update/census scope')
    need(re.search(r'2026 PACE Monthly Report September .*?October 27, 2026',norm(texts['ahca-report-index-approved']),re.I),'Index publication date absent')
    # Every returned public media field is preserved; date in upload path is not edition.
    for v in data['public-PDF-inventories']:
        sid=v['id'];raw=json.loads((ROOT/reg[sid]['path']).read_bytes());headers=reg[sid]['pagination_headers']
        need(v['total']==len(raw)==int(headers['X-WP-Total']) and v['total_pages']==int(headers['X-WP-TotalPages'])==1,'Incomplete media pagination')
        need(len(v['items'])==len(raw),'Missing media item')
        for r,item in zip(v['items'],raw):
            label=item['title']['rendered'];url=item['source_url'];filename=url.rsplit('/',1)[-1]
            years=sorted(set(re.findall(r'20(?:2[0-9])',label+' '+filename)));eoc=bool(re.search(r'evidence|eoc',label+' '+filename,re.I))
            expected=dict(media_id=item['id'],title=label,url=url,modified=item['modified'],edition_year_tokens=years,EOC_name_match=eoc,candidate_2026_EOC=eoc and '2026' in years,raw_item=item)
            need(r==expected,'Media field/benefit-year mismatch')
        need(v['candidate_2026_EOC_ids']==[],'Unexpected 2026 EOC candidate must be reconciled')
    # Independently scan all Section D rows and compare all 8,334 physical cells.
    pbp=data['pbp-section-d'];z=zipfile.ZipFile(ROOT/reg['cms-pbp-2026-reused']['path']);b=z.read('pbp_Section_D.txt');reader=csv.reader(io.StringIO(b.decode('cp1252')),delimiter='\t');headers=next(reader);rows=[];number=0
    need(pbp['headers']==headers and pbp['member_sha256']==sha(b) and pbp['field_ordinals_zero_based']=={'deductible':337,'annual_deposit':338},'PBP member schema or identity')
    for number,values in enumerate(reader,1):
        if values[0]=='H6130':rows.append(dict(source_row=number,values=values,contract_id=values[0],plan_id=values[1],segment_id_source=values[2],deductible_source=values[337],annual_deposit_source=values[338],personal_quote=None))
    need(pbp['retained_rows']==rows and len(rows)==18 and len(headers)==463 and number==pbp['national_rows']==7420,'PBP row denominator/original cell changed')
    need(pbp['original_cells']==8334 and {r['plan_id'] for r in rows}=={str(i) for i in range(801,819)},'Missing group plan')
    need(all(r['deductible_source']=='15000.00' for r in rows),'Deductible basis changed')
    # Independently reviewed physical page 2 fixtures. These are observations, not benefit acceptance.
    fixtures={
      'fenyx-2026-document-01':(['807','809','811'],[5000,7000,8800],[1200,2400,3600]),
      'fenyx-2026-document-02':(['803','807','809'],[4000,6000,7800],[1200,2400,3600]),
      'fenyx-2026-document-03':(['807','809'],[6000,7800],[2400,3600]),
      'fenyx-2026-document-04':(['811','815','816','818'],[5000,8400,12000,16000],[4800,8400,12000,24000]),
      'fenyx-2026-document-05':(['815','816','818'],[8400,12000,16000],[8400,12000,24000]),
      'fenyx-original-2026-5379':(['803','807','809'],[4000,6000,7800],[1200,2400,3600]),
      'fenyx-original-2026-5380':(['811','815','816','818'],[5000,8400,12000,16000],[4800,8400,12000,24000])}
    need(len(data['Fenyx-documents'])==7 and len(data['Fenyx-comparisons'])==22,'Summary document/column denominator')
    byid={r['plan_id']:r for r in rows};deposits=0
    for doc in data['Fenyx-documents']:
        sid=doc['id'];pp=(ROOT/reg[sid]['text_path']).read_text().split('\f')[:-1];ids,deds,deps=fixtures[sid]
        need(norm(pp[0]).startswith('2026 Summary of Benefits') and doc['printed_plan_ids']==ids and doc['page_count']==len(pp)==4,'Summary year/ID/page')
        need(doc['unified_design_join'] is None and doc['personal_quote'] is None,'Unverified summary unified')
        need(doc['cover_identity']==re.search(r'H6130 Plans (.*?) An MSA',norm(pp[0]))[1],'Cover identity changed')
        selected=[r for r in data['Fenyx-comparisons'] if r['source_id']==sid]
        need(len(selected)==len(ids),'Missing summary column')
        for r,pid,ded,dep in zip(selected,ids,deds,deps):
            guard_msa(r);cms=byid[pid]
            need(r['printed_plan_id']==pid and r['carrier_deductible_dollars']==ded and r['carrier_deposit_dollars']==dep,'Wrong column amount/ID')
            need(r['CMS_source_row']==cms['source_row'] and r['CMS_deductible_source']==cms['deductible_source'] and r['CMS_annual_deposit_source']==cms['annual_deposit_source'],'Wrong CMS cost join')
            need(r['deductible_numeric_agreement']==False and r['deposit_numeric_agreement']==(dep==int(float(cms['annual_deposit_source']))),'Numeric agreement mislabeled')
            need(r['all_source_conditions']==norm(pp[1]+' '+pp[2]),'Lost proration, DPC, group-payment or enrollment condition')
            for field,val in [('carrier_plan_premium_source',0),('carrier_deductible_source',ded),('carrier_deposit_source',dep)]:
                need(int(r[field].replace('$','').replace(',',''))==val,'Source amount representation changed')
            if sid.endswith('-01'):need(r['deposit_basis']=='initial_plus_up_to_conditional_DPC_extra' and 'proof of a paid DPC membership' in pp[1],'DPC deposit condition lost')
            deposits+=r['deposit_numeric_agreement']
    # Complete final-vs-proposed accounting, with exact XML/metadata retained for every final item.
    final=set();count=0
    for search in data['federal-register-searches']:
        guard_audit(search)
        v=json.loads((ROOT/reg[search['id']]['path']).read_bytes());count+=v['count']
        query=parse_qs(urlparse(reg[search['id']]['url']).query)
        need(query['conditions[cfr][title]']==['42'] and query['conditions[cfr][part]']==[search['part']] and query['conditions[publication_date][gte]']==['2025-01-01'] and query['conditions[publication_date][lte]']==['2026-10-29'],'Search request scope mismatch')
        need(v['count']==len(v['results'])==search['count'] and search['complete_results']==v['results'] and search['total_pages']==v['total_pages']==1,'Incomplete FR query')
        need(search['date_start']=='2025-01-01' and search['date_end']=='2026-10-29','FR audit time boundary')
        need(search['final_ids']==[r['document_number'] for r in v['results'] if r['type']=='Rule'] and search['proposed_ids']==[r['document_number'] for r in v['results'] if r['type']=='Proposed Rule'],'Proposed rule promoted')
        final.update(search['final_ids'])
    need(final=={'2025-06008','2025-08676','2025-09695','2026-06600','2026-11015'} and count==17,'Unaccounted final rule')
    for r in data['federal-register-amendments']:
        m=json.loads((ROOT/reg[r['metadata_source']]['path']).read_bytes());v=load(ROOT/reg[r['xml_source']]['structured_text_path'])
        need(r['id'] in final and all(r[k]==m[k] for k in ['publication_date','effective_on','action','dates']),'Amendment identity/date')
        need(r['regulatory_blocks']==v['regulatory_blocks'] and r['amendment_instructions']==v['amendment_instructions'],'Amendment scope truncated')
        sections=[s for block in r['regulatory_blocks'] for s in block['section_numbers']]
        need(not any(re.search(r'423\.250[48]',s) for s in sections),'Eligibility/duration amendment requires reconciliation')
    rule=next(r for r in data['federal-register-amendments'] if r['id']=='2026-06600');need(rule['effective_on']=='2026-06-01','LI NET amendment date')
    block=next(b for b in rule['regulatory_blocks'] if '§ 423.2536' in b['section_numbers']);need('423.128(d)(1)(i)(A)' in block['text'] and '(m)' in block['text'],'LI NET waiver unaccounted')
    need('460.98(b)(3)' in texts['fr-rule-xml-2026-11015'] and '460.112(a)' in texts['fr-rule-xml-2026-11015'],'Limited vacatur not retained')
    # Profile joins use existing exact IDs; sponsor terms are period-qualified and remain unaccepted.
    paths={r['id']:r for r in load(PARENT/'build-r1/paths.json')}
    for p in data['HCPP-profiles']:
        guard_profile(p);need(p['parent_directory_record']==paths[p['id']]['directory_source_record_id'],'Wrong sponsor contract')
        need(p['claim_ids']==[r['id'] for r in data['claims'] if r['contract_id']==p['id']],'Missing sponsor claim')
    summary=data['CMS-summary-observation'];archive=zipfile.ZipFile(ROOT/reg['cms-contract-summary-october-2026']['path'])
    guard_summary(summary)
    for v in load(BASE/'archive-members/index.json'):
        b=archive.read(v['member']);need((ROOT/v['path']).read_bytes()==b and sha(b)==v['sha256'] and len(b)==v['bytes'],'Archive member changed');inputs.add(ROOT/v['path'])
    ocr=(BASE/'archive-members/Monthly_Summary_Report_2026_10.ocr.txt').read_text()
    for key,pattern,want in [('PACE_contracts',r'PACE\s+(208)\b',208),('HCPP_contracts',r'\(HCPP\)\s+(5)\b',5),('MSA_contracts',r'MSA\s+(2)\b',2),('Cost_1876_contracts',r'1876 Cost\s+(6)\b',6)]:
        need(re.search(pattern,ocr) and summary[key]==want,'Summary count/visual fixture')
    need(summary['payment_as_of']=='2026-10-01' and summary['enrollments_accepted_through']=='2026-09-04' and not summary['area_only_ids_resolved'] and not summary['zero_pilots_proven'] and not summary['Collier_availability_proven_by_summary'],'Aggregate overclaim')
    need(data['gaps']==GAPS,'Gap status/closure changed')
    need(ref['new_retained_sources']==54 and ref['failed_local_transport_receipts']==1 and ref['new_PDF_pages']==pdf_pages==232 and ref['new_archive_PDF_pages']==1,'Source/page accounting')
    need(ref['new_PBP_original_cells']==8334 and ref['new_PBP_national_rows_scanned']==7420 and ref['Fenyx_summary_column_comparisons']==22,'New work accounting')
    # Complete JSON/SQLite parity for every modeled and retained field.
    db=BUILD/'reference.sqlite'
    with closing(sqlite3.connect(db)) as con:
        for name,rows in data.items():
            expected={str(k):v for k,v in rows.items()} if isinstance(rows,dict) else {str(r.get('id',i)):r for i,r in enumerate(rows)}
            got={k:json.loads(v) for k,v in con.execute('SELECT id,payload FROM "'+name+'"')}
            need(got==expected,'SQLite field parity '+name)
    for p in BASE.rglob('*'):
        if p.is_file() and 'build-r2' not in p.parts and 'validation-r2' not in p.parts:inputs.add(p)
    inputs.update(ROOT/'cms-slice/scripts'/n for n in ['l14_r2_acquire.py','l14_r2_sources.py','l14_r2_facts_search.py','l14_r2_catalog.py','l14_r2_build.py','l14_r2_validate.py'])
    report=dict(passed=True,failures=[],validated_at_utc=datetime.now(timezone.utc).isoformat(),parent_seal=parent_status,
                new_retained_sources=54,new_direct_PDF_pages=232,image_only_direct_PDF_pages=2,new_image_only_archive_PDF_pages=1,
                modeled_claims=14,complete_public_media_items=106,retained_PBP_rows=18,original_PBP_cells=8334,
                Fenyx_columns_compared=22,deductible_numeric_agreements=0,deposit_numeric_agreements=deposits,
                FR_query_results_accounted=17,unique_final_rule_documents=5,SQLite_JSON_tables_compared=len(data),
                qualified_R19_review=None,human_acceptance=None,full_l14_complete=False,
                limits='Mechanical source/provenance/field and condition-binding validation plus explicit visual table checks; not independent clinical/legal review or acceptance.',
                validated_inputs={str(p.relative_to(ROOT)):fp(p) for p in sorted(inputs)})
    VAL.mkdir(exist_ok=True);write(VAL/'validation.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='validated_inputs'},indent=2))
if __name__=='__main__':validate()
