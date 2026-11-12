"""Build an additive, bounded L14 gap reconciliation; never modify the r1 seal."""
import csv,hashlib,io,json,re,sqlite3,zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
from l14_r2_catalog import CLAIMS,GAPS

ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'docs/data/l14-other-coverage-2026-10-29'
BASE=PARENT/'gap-resolution-r2';BUILD=BASE/'build-r2';VAL=BASE/'validation-r2'
PARENT_SHA='15d6e1d711cd590f280e7f92bd47c9d9b619481c6cd02570f3a83495c3fddedd'
def load(p):return json.loads(p.read_text())
def norm(t):return ' '.join(t.split())
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def source_text(reg,sid):return (ROOT/reg[sid]['text_path']).read_text()
def amt(t):
    v=Decimal(t.replace('$','').replace(',','').strip('()*'))
    assert v==v.to_integral_value()
    return int(v)

def build():
    if (BUILD/'manifest.json').exists():raise ValueError('Sealed; create a new revision')
    assert sha((PARENT/'build-r1/manifest.json').read_bytes())==PARENT_SHA
    BUILD.mkdir(exist_ok=True)
    parent=load(PARENT/'build-r1/source-registry.json');new=load(BASE/'acquisition/extraction-index.json')
    assert not set(parent)&set(new)
    reg=parent|new;evidence=[]
    for sid,r in new.items():
        if r['status']!='retained' or r.get('extraction_kind')=='tabular_archive':continue
        t=source_text(reg,sid)
        evidence.append(dict(id=sid+':ALL',source_id=sid,locator='complete extracted source',text=norm(t)))
        if r.get('pdf_pages'):
            for i,p in enumerate(t.split('\f')[:-1],1):
                evidence.append(dict(id=f'{sid}:PAGE:{i}',source_id=sid,locator={'physical_pdf_page':i},text=norm(p)))
    clauses={r['id']:r for r in load(PARENT/'build-r1/evidence.json')+evidence}
    claims=[]
    for r in CLAIMS:
        rr=dict(r);rr['source_conditions']=[dict(source_clause_id=k,text=clauses[k]['text']) for k in r['source_clause_ids']]
        text=' '.join(x['text'] for x in rr['source_conditions'])
        for pattern in r['source_checks']:assert re.search(pattern,text,re.I),(r['id'],pattern)
        claims.append(rr)
    sid='ahca-pace-september-2026-approved';pages=source_text(reg,sid).split('\f')
    assert [i for i,p in enumerate(pages,1) if 'Collier' in p]==[5,13]
    op=next(t for t in pages[4].splitlines() if re.search(r'Hope PACE\s+Collier\s+Operational',t))
    co=next(t for t in pages[12].splitlines() if re.match(r'\s*Collier\s+Hope PACE',t))
    a=re.split(r'\s{2,}',op.strip());c=re.split(r'\s{2,}',co.strip())
    state=dict(id='Collier-September-2026',source_id=sid,source_period='2026-09',report_updated='2026-10-01',
               posted_date='2026-10-27',index_source_id='ahca-report-index-approved',county_fips='12021',
               contract_id='H5934',raw_operational_cells=a,raw_county_cells=c,
               slots_approved=int(a[5]),slots_funded=int(a[6]),enrollment_first_of_month=int(a[7]),
               actuarial_dual_rate_dollars=a[8],estimated_claims_source_cells=a[9:],
               county_current_month_enrollees=int(c[3]),fiscal_year_unique_individuals=int(c[4]),
               pending_additional_Collier_rows=[],reported_open_slots=None,personal_premium=None,live_capacity=None,
               claim_accounting_disposition='Literal cumulative claims do not equal the three monthly cells; preserve without repair. Government claims, not personal cost.',
               source_clause_ids=[sid+':PAGE:5',sid+':PAGE:13'])
    media=[]
    for sid in ['fenyx-pdf-library-p1','hope-pdf-library-p1']:
        r=reg[sid];items=json.loads((ROOT/r['path']).read_bytes());h=r['pagination_headers']
        assert len(items)==int(h['X-WP-Total']) and h['X-WP-TotalPages']=='1'
        records=[]
        for v in items:
            label=v['title']['rendered'];url=v['source_url'];name=url.rsplit('/',1)[-1]
            eoc=bool(re.search(r'evidence|eoc',label+' '+name,re.I))
            # The upload path/year is not the benefit edition. Keep all title/filename years.
            years=sorted(set(re.findall(r'20(?:2[0-9])',label+' '+name)))
            records.append(dict(media_id=v['id'],title=label,url=url,modified=v['modified'],
                                edition_year_tokens=years,EOC_name_match=eoc,
                                candidate_2026_EOC=eoc and '2026' in years,raw_item=v))
        media.append(dict(id=sid,source_id=sid,total=len(records),total_pages=1,items=records,
                          candidate_2026_EOC_ids=[x['media_id'] for x in records if x['candidate_2026_EOC']],
                          scope='Complete returned public PDF media index, not all unpublished/private documents'))
    # Preserve the existing CMS physical column arrays, including duplicate labels.
    z=zipfile.ZipFile(ROOT/parent['cms-pbp-2026-reused']['path']);member='pbp_Section_D.txt';b=z.read(member)
    rows=csv.reader(io.StringIO(b.decode('cp1252')),delimiter='\t');headers=next(rows);kept=[];number=0
    di=headers.index('pbp_d_msa_ded_amt');ai=headers.index('pbp_d_msa_annual_amt')
    for number,v in enumerate(rows,1):
        if v[0]=='H6130':kept.append(dict(source_row=number,values=v,contract_id=v[0],plan_id=v[1],segment_id_source=v[2],
                                        deductible_source=v[di],annual_deposit_source=v[ai],personal_quote=None))
    assert len(kept)==18 and all(len(r['values'])==len(headers) for r in kept)
    pbp=dict(source_id='cms-pbp-2026-reused',member=member,member_sha256=sha(b),headers=headers,
             national_rows=number,retained_rows=kept,original_cells=sum(len(v['values']) for v in kept),
             field_ordinals_zero_based={'deductible':di,'annual_deposit':ai},
             interpretation='Source observations only. Employer/group design basis is unresolved; no unified personal cost model.')
    ids={r['plan_id']:r for r in kept};comparisons=[];documents=[]
    for sid in [f'fenyx-2026-document-{n:02}' for n in range(1,6)]+['fenyx-original-2026-5379','fenyx-original-2026-5380']:
        pages=source_text(reg,sid).split('\f')[:-1];cover=norm(pages[0]);identity=re.search(r'H6130 Plans (.*?) An MSA',cover)[1]
        planids=re.findall(r'\b8\d{2}\b',identity);amountlines=[]
        for line in pages[1].splitlines():
            money=re.findall(r'\(?\$\d[\d,]*\)?',line)
            if len(money)==len(planids):amountlines.append(money)
        assert len(amountlines)>=3 and all(amt(v)==0 for v in amountlines[0])
        conditional='Initial Deposit' in pages[1];se='Self Employed' in identity
        documents.append(dict(id=sid,contract_id='H6130',benefit_year=2026,cover_identity=identity,printed_plan_ids=planids,
                              page_count=len(pages),source_clause_ids=[f'{sid}:PAGE:{n}' for n in range(1,len(pages)+1)],
                              unified_design_join=None,personal_quote=None))
        for col,pid in enumerate(planids):
            raw=ids[pid];d=amt(amountlines[1][col]);dep=amt(amountlines[2][col]);cmsd=amt(raw['deductible_source']);cmsa=amt(raw['annual_deposit_source'])
            comparisons.append(dict(id=f'{sid}:{col+1}',source_id=sid,contract_id='H6130',printed_plan_id=pid,
                 printed_column_ordinal=col+1,carrier_plan_premium_source=amountlines[0][col],carrier_deductible_source=amountlines[1][col],
                 carrier_deposit_source=amountlines[2][col],carrier_deductible_dollars=d,carrier_deposit_dollars=dep,
                 deposit_basis='initial_plus_up_to_conditional_DPC_extra' if conditional else ('annual_plus_monthly_source_schedule' if se else 'full_year_deposit'),
                 all_source_conditions=norm(pages[1]+' '+pages[2]),deposit_is_guaranteed=False,
                 CMS_source_row=raw['source_row'],CMS_segment_id_source=raw['segment_id_source'],CMS_deductible_source=raw['deductible_source'],CMS_annual_deposit_source=raw['annual_deposit_source'],
                 deductible_numeric_agreement=d==cmsd,deposit_numeric_agreement=dep==cmsa,
                 numeric_agreement_is_design_acceptance=False,unified_plan_deductible=None,unified_plan_deposit=None,personal_quote=None,
                 disposition='Hold deductible/design-basis discrepancy; retain deposit basis/conditions even where numbers agree.',
                 source_clause_ids=[sid+':PAGE:1',sid+':PAGE:2',sid+':PAGE:3']))
    audits=[];final={}
    for part in ['417','423','460']:
        sid='fr-'+part+'-since-2025';r=reg[sid];v=json.loads((ROOT/r['path']).read_bytes())
        assert v['count']==len(v['results']) and v['total_pages']==1
        for result in v['results']:
            if result['type']=='Rule':final[result['document_number']]=result
        audits.append(dict(id=sid,part=part,date_start='2025-01-01',date_end='2026-10-29',count=v['count'],total_pages=v['total_pages'],
                           complete_results=v['results'],final_ids=[r['document_number'] for r in v['results'] if r['type']=='Rule'],
                           proposed_ids=[r['document_number'] for r in v['results'] if r['type']=='Proposed Rule']))
    amendments=[]
    for did in sorted(final):
        sid='fr-rule-xml-'+did;v=load(ROOT/reg[sid]['structured_text_path']);m=json.loads((ROOT/reg['fr-rule-metadata-'+did]['path']).read_bytes())
        amendments.append(dict(id=did,metadata_source='fr-rule-metadata-'+did,xml_source=sid,publication_date=m['publication_date'],
                               effective_on=m.get('effective_on'),action=m['action'],dates=m['dates'],
                               regulatory_blocks=v['regulatory_blocks'],amendment_instructions=v['amendment_instructions']))
    profiles=[];parentpaths=load(PARENT/'build-r1/paths.json')
    for cid in ['90091','H4556','H6142','H6334']:
        p=next(r for r in parentpaths if r['id']==cid)
        profiles.append(dict(id=cid,parent_directory_record=p['directory_source_record_id'],
             identity_basis='CMS legal/marketing organization, sponsor name and matching published contact/address/domain; not a public individual-plan offering',
             claim_ids=[r['id'] for r in claims if r['contract_id']==cid],
             PDP_interaction=('sponsor_warns_retiree_benefit_termination' if cid=='H6334' else '2025_UHS_brochure_allows_standalone_PDP' if cid=='H6142' else '4000_includes_Part_D_4100_has_no_drug_benefit' if cid=='H4556' else 'exact_case_not_determined'),
             unrestricted_public_enrollment=False,Collier_provider_confirmed=None,personal_eligibility=None,acceptance=None))
    summary=dict(source_id='cms-contract-summary-october-2026',member='Monthly_Summary_Report_2026_10/Monthly_Summary_Report_2026_10.pdf',
                 physical_pdf_page=1,evidence_kind='image-only PDF visually inspected; retained OCR is secondary locator',
                 PACE_contracts=208,HCPP_contracts=5,Cost_1876_contracts=6,MSA_contracts=2,
                 payment_as_of='2026-10-01',enrollments_accepted_through='2026-09-04',
                 directory_PACE_contracts=208,area_PACE_contracts=243,area_only_ids_resolved=False,
                 zero_pilots_proven=False,Collier_availability_proven_by_summary=False)
    reference=dict(reference_id='L14-PUBLISHED-COLLIER-2026-gap-r2',benefit_year=2026,county_fips='12021',
                   parent_manifest_sha256=PARENT_SHA,parent_reference='L14-PUBLISHED-COLLIER-2026-research-r1',
                   parent_paths=7,parent_rules=21,new_claims=len(claims),new_retained_sources=sum(r['status']=='retained' for r in new.values()),
                   failed_local_transport_receipts=sum(r['status']!='retained' for r in new.values()),new_PDF_pages=sum(r.get('pdf_pages',0) for r in new.values()),
                   new_archive_PDF_pages=1,new_PBP_original_cells=pbp['original_cells'],new_PBP_national_rows_scanned=number,
                   Fenyx_summary_documents=len(documents),Fenyx_summary_column_comparisons=len(comparisons),
                   human_acceptance=None,qualified_R19_review=None,full_l14_complete=False,consumer_release_enabled=False,personal_applicability_enabled=False,
                   data_gap_ids=['G02','G03','G04'],national_expansion_gap_ids=['G06'],casework_gap_ids=['G05'],review_gap_ids=['G07'])
    payloads={'reference':reference,'source-registry':reg,'new-source-registry':new,'evidence':evidence,
              'claims':claims,'state-observation':state,'public-PDF-inventories':media,'pbp-section-d':pbp,
              'Fenyx-documents':documents,'Fenyx-comparisons':comparisons,'federal-register-searches':audits,
              'federal-register-amendments':amendments,'HCPP-profiles':profiles,'CMS-summary-observation':summary,'gaps':GAPS}
    for name,v in payloads.items():write(BUILD/(name+'.json'),v)
    db=BUILD/'reference.sqlite';db.unlink(missing_ok=True)
    with sqlite3.connect(db) as con:
        for name,rows in payloads.items():
            con.execute('CREATE TABLE "'+name+'" (id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            pairs=rows.items() if isinstance(rows,dict) else ((r.get('id',str(i)),r) for i,r in enumerate(rows))
            con.executemany('INSERT INTO "'+name+'" VALUES (?,?)',[(str(k),json.dumps(v,sort_keys=True)) for k,v in pairs])
    print(json.dumps(reference,indent=2))
if __name__=='__main__':build()
