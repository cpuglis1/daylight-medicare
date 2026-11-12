"""Build the isolated, dated L14 research inventory from whole retained sources."""
from collections import Counter,defaultdict
import csv,gzip,hashlib,io,json,re,sqlite3,zipfile
from pathlib import Path
from l14_catalog import RULES,RECONCILIATIONS,GAPS
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l14-other-coverage-2026-10-29';ACQ=BASE/'acquisition-r1';BUILD=BASE/'build-r1'
L='cms-landscape-202609';A='cms-contract-area-202610';D='cms-ma-directory-october-2026'
SPECIAL={'MSA','1876 Cost','HCPP - 1833 Cost','National PACE','LI NET Sponsor'}
def norm(s):return ' '.join(s.split())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def zipped(s):
    z=zipfile.ZipFile(ROOT/s['path']);n=next(n for n in z.namelist() if n.lower().endswith('.csv'))
    data=z.read(n);rd=csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    return rd,dict(member=n,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),columns=rd.fieldnames),{n:z.read(n).decode('utf-8-sig') for n in z.namelist() if n.lower().endswith('.txt')}
def routing(sid,r):
    typ=r['Plan Type'];org=r['Organization Type']
    if sid==D:return 'retain_full_contract_directory'
    local=(r['State Territory Abbreviation']=='FL' and r['County Name'] in ['Collier','All Counties']) if sid==L else r['FIPS']=='12021'
    special=(typ in ['Cost','MSA']) if sid==L else org in SPECIAL
    return 'retain_alternate_national_cohort' if special else ('retain_collier_route_L02_L04' if local else 'accounted_outside_retained_cohort')
def normalized(sid,r):
    directory=sid==D;land=sid==L
    contract=r['Contract Number' if directory else 'Contract ID']
    return dict(contract_id=contract,plan_id=r['Plan ID'] if land else None,segment_id=r['Segment ID'] if land else None,
        organization_type=r['Organization Type'],plan_type=r['Plan Type'],
        state=r['State Territory Abbreviation'] if land else (None if directory else r['State']),
        county=r['County Name'] if land else (None if directory else r['County']),fips=r['FIPS'] if sid==A else None,
        partial_county=(r['Partial']=='*') if sid==A else None,employer_group_only=(r['EGHP']=='*') if sid==A else None,
        national_note=(not r['FIPS'] and 'entire US' in r['Notes']) if sid==A else None,
        contract_effective_date=r['Contract Effective Date'] if directory else None,
        personal_availability='not_determined',source_year=2026)
def units(sources):
    out=[]
    for sid,s in sources.items():
        if s['status']!='retained' or s.get('extraction_kind')=='tabular_archive':continue
        t=(ROOT/s['text_path']).read_text()
        out.append(dict(id=sid+':ALL',source_id=sid,locator={'method':s['extraction_kind']},text=norm(t)))
        if s['extraction_kind']=='native_pdf_text':
            out += [dict(id=f'{sid}:PAGE:{i}',source_id=sid,locator={'physical_pdf_page':i},text=norm(p)) for i,p in enumerate(t.split('\f')[:-1],1)]
        elif s['extraction_kind']=='ecfr_xml_sections':
            out += [dict(id=f'{sid}:CFR:{r["section"]}',source_id=sid,locator={'section':r['section']},text=r['text']) for r in load(ROOT/s['structured_text_path'])['sections']]
    return out
def state_observation(sid,s):
    t=(ROOT/s['text_path']).read_text();pages=t.split('\f')[:-1]
    occurrences=[i for i,p in enumerate(pages,1) if re.search(r'\bCollier\b',p)]
    assert occurrences==[5,13],(sid,occurrences)
    row=next(x for x in pages[4].splitlines() if re.search(r'Hope PACE\s+Collier\s+Operational',x))
    cells=re.split(r'\s{2,}',row.strip());assert cells[:4]==['Hope PACE','Collier','Operational','4/12/2012']
    county=next(x for x in pages[12].splitlines() if re.match(r'\s*Collier\s+Hope PACE',x))
    cc=re.split(r'\s{2,}',county.strip());assert cc[:3]==['Collier','Hope PACE','Operational']
    month='2026-07' if 'july' in sid else '2026-08'
    return dict(id='HOPE-'+month,source_id=sid,report_month=month,updated='2026-08-12' if 'july' in sid else '2026-09-03',
        contract_id='H5934',contract_identity_basis='CMS exact legal/marketing identity plus Hope three-county program; state report itself has no contract ID',
        county='Collier',organization='Hope PACE',status=cells[2],initial_AHCA_approval=cells[3],slots_requested=cells[4],
        slots_approved=int(cells[5]),slots_funded=int(cells[6]),enrollment_first_of_month=int(cells[7]),
        actuarial_dual_rate_dollars=cells[8],estimated_claims_dollars=cells[9:],
        county_current_month_enrollees=int(cc[3]),fiscal_year_unique_individuals=int(cc[4]),
        raw_operational_cells=cells,raw_county_cells=cc,physical_pdf_pages=occurrences,
        reported_open_slots=None,personal_premium=None,live_capacity=None,
        source_clause_ids=[f'{sid}:PAGE:2',f'{sid}:PAGE:3',f'{sid}:PAGE:5',f'{sid}:PAGE:13'],
        interpretation='Dated operational/capacity/claims observations. Rate is state capitation, not a beneficiary quote. No vacancy calculation.')
def pbp_inventory(s):
    z=zipfile.ZipFile(ROOT/s['path']);members=[]
    for name in ['pbp_Section_A.txt','PlanArea.txt']:
        content=z.read(name);rd=csv.reader(io.StringIO(content.decode('cp1252')),delimiter='\t');headers=next(rd);rows=[];count=0;contract_rows=0
        for num,values in enumerate(rd,1):
            count=num
            if values[0]!='H6130':continue
            contract_rows+=1
            if name=='PlanArea.txt' and values[-2:]!=['Collier','FL']:continue
            assert len(values)==len(headers)
            # Repeated headers remain separate column positions, never DictReader overwrites.
            rows.append(dict(source_row=num,values=values,contract_id=values[0],plan_id=values[1],segment_id_source=values[2],
                plan_name=values[19] if name=='pbp_Section_A.txt' else None,group_flag=values[27] if name=='pbp_Section_A.txt' else values[14],
                county_code_SSA=values[10] if name=='PlanArea.txt' else None,pending_flag=values[11] if name=='PlanArea.txt' else None,
                partial_flag=values[12] if name=='PlanArea.txt' else None,source_year=values[13] if name=='PlanArea.txt' else '2026',
                personal_eligibility=None,consumer_plan_acceptance=None))
        members.append(dict(member=name,member_sha256=hashlib.sha256(content).hexdigest(),bytes=len(content),headers=headers,
            national_rows=count,H6130_national_rows=contract_rows,retained_rows=rows))
    assert all(len(m['retained_rows'])==18 for m in members)
    return dict(source_id='cms-pbp-2026-reused',snapshot='2026 benefits archive; last modified 2025-10-28, not October 2026 availability',members=members,
        preserved_original_cells=sum(len(r['values']) for m in members for r in m['retained_rows']),
        interpretation='18 exact CMS group plan/segment identities plus 18 Collier area rows retained. Not a public individual offering or verified current carrier design/benefit join.')
def build():
    if (BUILD/'manifest.json').exists():raise ValueError('Sealed; use new revision')
    BUILD.mkdir(exist_ok=True);sources=load(ACQ/'extraction-index.json');evidence=units(sources);ub={r['id']:r for r in evidence}
    records=[];accounting={};readmes={};allgroups={};retained_fields=0
    ledger=BUILD/'national-routing.jsonl.gz'
    with ledger.open('wb') as dest,gzip.GzipFile(fileobj=dest,mode='wb',mtime=0) as gz:
        for sid in [L,A,D]:
            reader,meta,txt=zipped(sources[sid]);types=Counter();routes=Counter();groups=defaultdict(list);total=0;kept=0
            for num,r in enumerate(reader,1):
                assert None not in r and all(v is not None for v in r.values())
                if sid==L:assert r['Contract Year']=='2026'
                total+=1;route=routing(sid,r);types[r['Organization Type']+' / '+r['Plan Type']]+=1;routes[route]+=1
                contract=r['Contract Number' if sid==D else 'Contract ID'];groups[contract].append((num,r))
                retain=route!='accounted_outside_retained_cohort'
                gz.write((json.dumps(dict(source_id=sid,source_row=num,contract_id=contract,organization_type=r['Organization Type'],plan_type=r['Plan Type'],route=route,retained=retain),sort_keys=True)+'\n').encode())
                if retain:
                    kept+=1;retained_fields+=len(r)
                    records.append(dict(id=f'{sid}:{num}',source_id=sid,source_row=num,route=route,raw=r,normalized=normalized(sid,r)))
            accounting[sid]={**meta,'national_rows':total,'retained_rows':kept,'all_types':dict(types),'all_routes':dict(routes),'raw_source_sha256':sources[sid]['sha256'],'source_period':sources[sid]['source_period']}
            allgroups[sid]=groups;readmes.update({sid+'/'+n:t for n,t in txt.items()})
    for key,t in readmes.items():
        evidence.append(dict(id=key.split('/')[0]+':README',source_id=key.split('/')[0],locator={'archive_member':key.split('/',1)[1]},text=norm(t)))
    ub={r['id']:r for r in evidence}
    local_l=[r for r in records if r['source_id']==L and r['raw']['State Territory Abbreviation']=='FL' and r['raw']['County Name'] in ['Collier','All Counties']]
    local_a=[r for r in records if r['source_id']==A and r['raw']['FIPS']=='12021']
    contract_records={r['raw']['Contract Number']:r for r in records if r['source_id']==D}
    candidates=[]
    for cid,items in allgroups[A].items():
        row=items[0][1];org=row['Organization Type']
        if org not in SPECIAL:continue
        selected=[(n,r) for n,r in items if r['FIPS']=='12021' or (not r['FIPS'] and 'entire US' in r['Notes'])]
        if not selected or (org=='National PACE' and cid!='H5934'):continue
        if cid=='H5934':status='dated_state_and_program_Collier_confirmation'
        elif org=='MSA':status='employer_group_only_contract_no_individual_plan_in_landscape'
        elif org=='HCPP - 1833 Cost':status='national_note_restricted_membership_local_access_unconfirmed'
        else:status='conditional_national_temporary_drug_program'
        dr=contract_records.get(cid);assert dr is not None
        candidates.append(dict(id=cid,contract_id=cid,organization_name=row['Organization Name'],organization_type=org,plan_type=row['Plan Type'],status=status,
            service_area_source_record_ids=[f'{A}:{n}' for n,r in selected],directory_source_record_id=dr['id'],
            employer_group_only=any(r['EGHP']=='*' for n,r in selected),national_note=any(not r['FIPS'] for n,r in selected),
            contract_effective_date=dr['raw']['Contract Effective Date'],directory_enrollment=dr['raw']['Enrollment'],
            enrollment_grain='contract-wide October snapshot; suppressed * is at most ten, never zero',
            individual_plan_segment=None,personal_eligibility=None,current_opening=None,personal_quote=None,qualified_review=None,acceptance=None))
    negative=dict(reference_year=2026,county_fips='12021',county='Collier',landscape_period='2026-09',contract_area_period='2026-10',
        landscape_collier_all_counties_rows=len(local_l),landscape_collier_type_counts=dict(Counter(r['raw']['Plan Type'] for r in local_l)),
        individual_MSA_source_rows=[r['id'] for r in local_l if r['raw']['Plan Type']=='MSA'],individual_Cost_source_rows=[r['id'] for r in local_l if r['raw']['Plan Type']=='Cost'],
        collier_contract_area_rows=len(local_a),collier_MSA_source_rows=[r['id'] for r in local_a if r['raw']['Organization Type']=='MSA'],
        collier_1876_Cost_source_rows=[r['id'] for r in local_a if r['raw']['Organization Type']=='1876 Cost'],
        contract_1876_Cost_ids=sorted(cid for cid,rows in allgroups[A].items() if rows[0][1]['Organization Type']=='1876 Cost'),
        limits=['September individual file excludes employer, Part B-only and PACE records','October contract areas exclude pilot contracts','No full-year, live availability or individual eligibility inference','HCPP, PACE and LI NET national-note rows are retained separately, not counted as individual landscape plans'])
    pace_a={cid for cid,v in allgroups[A].items() if v[0][1]['Organization Type']=='National PACE'}
    pace_d={cid for cid,v in allgroups[D].items() if v[0][1]['Organization Type']=='National PACE'}
    anomalies=dict(pace_contract_area_count=len(pace_a),pace_directory_count=len(pace_d),pace_area_only=sorted(pace_a-pace_d),pace_directory_only=sorted(pace_d-pace_a),
        pace_national_note_records=[r['id'] for r in records if r['source_id']==A and r['raw']['Organization Type']=='National PACE' and r['normalized']['national_note']],
        Fenyx_FL_MSA_geography_records=[r['id'] for r in records if r['source_id']==A and r['raw']['Contract ID']=='H6130' and r['raw']['State']=='FL'],
        interpretation='Unresolved national PACE directory differences and blanket national-note geography are not local availability evidence. Fenyx retains both legacy 12025 and current 12086 Miami-Dade codes; no Collier alias change.')
    observations=[state_observation(sid,sources[sid]) for sid in ['ahca-pace-july-2026','ahca-pace-august-2026']]
    pbp=pbp_inventory(sources['cms-pbp-2026-reused'])
    evidence.append(dict(id='cms-pbp-2026-reused:IDENTITY',source_id='cms-pbp-2026-reused',locator={'members':['pbp_Section_A.txt','PlanArea.txt'],'complete_retained_rows':True},text=json.dumps(pbp,sort_keys=True)))
    ub={r['id']:r for r in evidence}
    next(p for p in candidates if p['id']=='H6130')['CMS_group_plan_observations']=[dict(plan_id=r['plan_id'],segment_id_source=r['segment_id_source'],plan_name=r['plan_name'],source_member='pbp_Section_A.txt',source_row=r['source_row']) for r in pbp['members'][0]['retained_rows']]
    documents=[]
    for sid in sorted(k for k in sources if k.startswith('fenyx-2026-document-')):
        pages=(ROOT/sources[sid]['text_path']).read_text().split('\f')[:-1]
        header=norm(pages[0]);assert header.startswith('2026 Summary of Benefits')
        identity=re.search(r'H6130 Plans (.*?) An MSA',header)[1]
        documents.append(dict(id=sid,source_id=sid,benefit_year=2026,contract_id='H6130',publisher_identity_text=identity,
            plan_ids=re.findall(r'\b8\d{2}\b',identity),physical_pdf_pages=len(pages),
            source_clause_ids=[f'{sid}:PAGE:{i}' for i in range(1,len(pages)+1)],
            unified_plan_join='held_conflicting_design_ids_no_segment_or_group_mapping',personal_quote=None,
            benefit_amounts='Source-native pages retained; not normalized into a unified plan/consumer cost model'))
    rules=[]
    for r in RULES:
        rr=dict(r);rr['source_conditions']=[dict(source_clause_id=k,text=ub[k]['text']) for k in r['source_clause_ids']]
        for a in r['checks']:
            text=' '.join(ub[k]['text'] for k in r['source_clause_ids']);assert re.search(a,text,re.I),(r['id'],a)
        rules.append(rr)
    reconciliations=[]
    for r in RECONCILIATIONS:
        rr=dict(r);rr['source_conditions']=[dict(source_clause_id=k,text=ub[k]['text']) for k in r['source_clause_ids']];reconciliations.append(rr)
    payloads={'source-registry':sources,'source-accounting':accounting,'records':records,'evidence':evidence,'paths':sorted(candidates,key=lambda r:r['id']),
        'negative-search':negative,'source-anomalies':anomalies,'state-observations':observations,'restricted-documents':documents,'pbp-reuse-inventory':pbp,'rules':rules,'reconciliations':reconciliations,'gaps':GAPS}
    meta=dict(reference_id='L14-PUBLISHED-COLLIER-2026-research-r1',benefit_year=2026,county_fips='12021',source_snapshots=['2026-07','2026-08','2026-09','2026-10'],program_pages_retrieved='2026-10-29',
        retained_source_count=sum(s['status']=='retained' for s in sources.values()),
        national_rows_scanned=sum(v['national_rows'] for v in accounting.values())+sum(m['national_rows'] for m in pbp['members']),
        core_national_rows_scanned=sum(v['national_rows'] for v in accounting.values()),PBP_additional_national_rows_scanned=sum(m['national_rows'] for m in pbp['members']),
        retained_records=len(records),retained_original_cells=retained_fields,PBP_group_plan_identity_observations=18,PBP_Collier_area_observations=18,PBP_additional_original_cells=pbp['preserved_original_cells'],modeled_paths=len(candidates),modeled_rules=len(rules),
        qualified_R19_review=None,human_acceptance=None,personal_applicability_enabled=False,consumer_release_enabled=False,full_l14_complete=False,
        scoped_collection_and_reference_implementation_complete=True,geography='Published county-level reference; no address eligibility conclusion')
    payloads['reference']=meta
    for name,payload in payloads.items():write(BUILD/(name+'.json'),payload)
    for sid in [L,A,D]:
        subset=[r for r in records if r['source_id']==sid];cols=list(subset[0]['raw'])
        with (BUILD/(sid+'-retained.csv')).open('w',newline='') as f:
            wr=csv.DictWriter(f,fieldnames=['source_id','source_row','route']+cols);wr.writeheader()
            wr.writerows({**{k:r[k] for k in ['source_id','source_row','route']},**r['raw']} for r in subset)
    db=BUILD/'reference.sqlite';db.unlink(missing_ok=True)
    with sqlite3.connect(db) as con:
        for table,rows in payloads.items():
            con.execute('CREATE TABLE "'+table+'" (id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            pairs=rows.items() if isinstance(rows,dict) else ((r.get('id',str(i)),r) for i,r in enumerate(rows))
            con.executemany('INSERT INTO "'+table+'" VALUES (?,?)',[(str(k),json.dumps(v,sort_keys=True)) for k,v in pairs])
    print(json.dumps(meta,indent=2))
if __name__=='__main__':build()
