"""Independently reread L14 source bytes; validate the finite published research scope."""
import argparse,csv,gzip,hashlib,io,json,re,sqlite3,subprocess,xml.etree.ElementTree as ET,zipfile
from collections import Counter,defaultdict
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from l12_sources import PublicHTML
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/data/l14-other-coverage-2026-10-29';BUILD=BASE/'build-r1';VAL=BASE/'validation-r1'
L='cms-landscape-202609';A='cms-contract-area-202610';D='cms-ma-directory-october-2026'
def load(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fp(p):return dict(bytes=p.stat().st_size,sha256=digest(p))
def norm(t):return ' '.join(t.split())
def need(ok,message):
    if not ok:raise ValueError(message)
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def descendants(x):
    if isinstance(x,dict):
        yield x
        for v in x.values():yield from descendants(v)
    elif isinstance(x,list):
        for v in x:yield from descendants(v)
def guard_reference(r):
    need(r['benefit_year']==2026 and r['county_fips']=='12021','Wrong year or geography')
    need(not r['personal_applicability_enabled'] and not r['consumer_release_enabled'] and not r['full_l14_complete'],'Unreviewed release')
    need(r['human_acceptance'] is None and r['qualified_R19_review'] is None,'Invented acceptance')
def guard_path(p):
    need(all(p[k] is None for k in ['personal_eligibility','current_opening','personal_quote','qualified_review','acceptance','individual_plan_segment']),'Unsupported path claim')
    if p['organization_type']=='HCPP - 1833 Cost':need(p['status']=='national_note_restricted_membership_local_access_unconfirmed','National note is not membership/access')
    if p['organization_type']=='MSA':need(p['employer_group_only'] and p['status']=='employer_group_only_contract_no_individual_plan_in_landscape','Lost MSA restriction')
def guard_state(r):
    need(all(r[k] is None for k in ['reported_open_slots','personal_premium','live_capacity']),'Capacity or rate became personal claim')
def compare_cells(got,want):need(got==want,'Source cell changed, omitted, or silently normalized')
def parents():
    pinned={
    'docs/data/l02-ma-availability-2026-10-25/build-r5/build-manifest.json':'73815d3f5358f74666f4f9e4673949735115dff82a62a52f6ed50f3686d3a0a9',
    'docs/data/l11-medigap-rights-2026-10-28/build-r2/manifest.json':'30f3e52478b1e35003560eda8b58c65e14325fab8591a4fae38450c52ccdc1a0',
    'docs/data/l12-help-with-costs-2026-10-28/build-r2/manifest.json':'566aa6ec0d76a5d9a6291350eeb7c60dc7e35c1d1355a65bf2da429be93375a5',
    'docs/data/l13-enrollment-2026-10-28/build-r1/manifest.json':'407d53ea070349b8dcba0fbbc10893932d96c32a71cbfa447d68ff470e08616c'}
    for p,sha in pinned.items():need(digest(ROOT/p)==sha,'Changed parent manifest '+p)
    # L13 seal already pins the exact shared evidence/helper bytes. Recheck every sealed file.
    p=ROOT/'docs/data/l13-enrollment-2026-10-28/build-r1/manifest.json'
    for path,expected in load(p)['files'].items():need(fp(ROOT/path)==expected,'Changed sealed parent input '+path)
    return dict(parent_manifest_hashes=pinned,L13_parent_pinned_files_checked=len(load(p)['files']))
def validate():
    data={p.stem:load(p) for p in BUILD.glob('*.json') if p.name!='manifest.json'}
    ref=data['reference'];guard_reference(ref);s=data['source-registry'];u={r['id']:r for r in data['evidence']};need(len(u)==len(data['evidence']),'Duplicate evidence ID')
    inputs=set();fresh={};pdf_pages=0
    for sid,r in s.items():
        inputs.add(ROOT/r['receipt_path'])
        if r.get('path'):inputs.add(ROOT/r['path']);need(fp(ROOT/r['path'])=={k:r[k] for k in ['bytes','sha256']},'Raw source hash '+sid)
        if r['status']!='retained':continue
        receipt=load(ROOT/r['receipt_path'])
        need(any(x.get('sha256')==r['sha256'] and (x.get('url')==r['url'] or x.get('requested_url')==r['url']) for x in descendants(receipt)),'No original receipt '+sid)
        raw=ROOT/r['path'];b=raw.read_bytes()
        if r.get('extraction_kind')=='tabular_archive':continue
        if b.startswith(b'%PDF'):
            command=['pdftotext']+([] if sid.startswith('govinfo-') else ['-layout'])+[str(raw),'-']
            t=subprocess.run(command,capture_output=True,check=True).stdout.decode();pdf_pages+=t.count('\f')
            need(r['pdf_pages']==t.count('\f'),'PDF page count '+sid)
        elif r['extraction_kind']=='ecfr_xml_sections':
            tree=ET.fromstring(b);sections=[{'section':n.get('N'),'text':norm(' '.join(n.itertext()))} for n in tree.iter('DIV8')]
            t='\n'.join(v['text'] for v in sections)+'\n';need(load(ROOT/r['structured_text_path'])=={'sections':sections},'XML truncation '+sid)
        else:
            parser=PublicHTML();parser.feed(b.decode(errors='replace'));v=parser.result();t='\n'.join(v['lines'])+'\n'
            need(load(ROOT/r['structured_text_path'])==v,'HTML structure changed '+sid)
        fresh[sid]=t;need((ROOT/r['text_path']).read_text()==t,'Text extraction mismatch '+sid)
        need(u[sid+':ALL']['text']==norm(t),'All-source evidence mismatch '+sid)
        if b.startswith(b'%PDF'):
            for i,p in enumerate(t.split('\f')[:-1],1):need(u[f'{sid}:PAGE:{i}']['text']==norm(p),'PDF page evidence changed')
    originals={};expected_ids=[];cell_count=0;scan=0;retained=0
    with gzip.open(BUILD/'national-routing.jsonl.gz','rt') as ledger:
        for sid in [L,A,D]:
            z=zipfile.ZipFile(ROOT/s[sid]['path']);member=next(n for n in z.namelist() if n.lower().endswith('.csv'));raw=z.read(member)
            reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')));orig={};types=Counter();routes=Counter();num=0;kept=0
            account=data['source-accounting'][sid]
            need(account['member']==member and account['sha256']==hashlib.sha256(raw).hexdigest() and account['columns']==reader.fieldnames,'Member schema/hash '+sid)
            for num,row in enumerate(reader,1):
                need(None not in row and all(v is not None for v in row.values()),'Malformed raw row')
                if sid==L:need(row['Contract Year']=='2026','Foreign benefit year')
                if sid==D:take=True;why='retain_full_contract_directory'
                else:
                    special=row['Plan Type'] in ['Cost','MSA'] if sid==L else row['Organization Type'] in ['MSA','1876 Cost','HCPP - 1833 Cost','National PACE','LI NET Sponsor']
                    local=(row['State Territory Abbreviation']=='FL' and row['County Name'] in ['Collier','All Counties']) if sid==L else row['FIPS']=='12021'
                    take=special or local;why='retain_alternate_national_cohort' if special else ('retain_collier_route_L02_L04' if local else 'accounted_outside_retained_cohort')
                cid=row['Contract Number' if sid==D else 'Contract ID'];types[row['Organization Type']+' / '+row['Plan Type']]+=1;routes[why]+=1
                led=json.loads(next(ledger));need(led==dict(source_id=sid,source_row=num,contract_id=cid,organization_type=row['Organization Type'],plan_type=row['Plan Type'],route=why,retained=take),'Missing/rerouted national row')
                if take:orig[num]=row;expected_ids.append(f'{sid}:{num}');kept+=1;cell_count+=len(row)
            need(account['national_rows']==num and account['retained_rows']==kept and account['all_types']==dict(types) and account['all_routes']==dict(routes),'Source accounting '+sid)
            originals[sid]=orig;scan+=num;retained+=kept
            # Independently compare every CSV-exported original cell and ordinal.
            with (BUILD/(sid+'-retained.csv')).open(newline='') as f:
                out=list(csv.DictReader(f))
            need(len(out)==len(orig),'CSV count')
            for r,(n,want) in zip(out,orig.items()):
                need(r.pop('source_id')==sid and r.pop('source_row')==str(n),'CSV identity');r.pop('route');compare_cells(r,want)
            for n in z.namelist():
                if n.lower().endswith('.txt'):need(u[sid+':README']['text']==norm(z.read(n).decode('utf-8-sig')),'Changed readme')
        need(next(ledger,None) is None,'Extra routing rows')
    need([r['id'] for r in data['records']]==expected_ids,'Selected row denominator/order')
    by={r['id']:r for r in data['records']}
    for r in data['records']:
        sid=r['source_id'];src=originals[sid][r['source_row']];compare_cells(r['raw'],src);n=r['normalized'];land=sid==L;di=sid==D
        want=dict(contract_id=src['Contract Number' if di else 'Contract ID'],plan_id=src['Plan ID'] if land else None,segment_id=src['Segment ID'] if land else None,
            organization_type=src['Organization Type'],plan_type=src['Plan Type'],state=src['State Territory Abbreviation'] if land else (None if di else src['State']),county=src['County Name'] if land else (None if di else src['County']),
            fips=src['FIPS'] if sid==A else None,partial_county=(src['Partial']=='*') if sid==A else None,employer_group_only=(src['EGHP']=='*') if sid==A else None,
            national_note=(not src['FIPS'] and 'entire US' in src['Notes']) if sid==A else None,contract_effective_date=src['Contract Effective Date'] if di else None,personal_availability='not_determined',source_year=2026)
        need(n==want,'Normalized field changed '+r['id'])
    need((scan,retained,cell_count)==(555704,6890,156979),'Finite inventory changed')
    need((ref['core_national_rows_scanned'],ref['retained_records'],ref['retained_original_cells'])==(scan,retained,cell_count),'Summary counts changed')
    aa=originals[A];dd=originals[D];ll=originals[L];local_l=[r for r in ll.values() if r['State Territory Abbreviation']=='FL' and r['County Name'] in ['Collier','All Counties']]
    local_a=[r for r in aa.values() if r['FIPS']=='12021'];neg=data['negative-search']
    need(len(local_l)==neg['landscape_collier_all_counties_rows']==82 and len(local_a)==neg['collier_contract_area_rows']==134,'Local denominator')
    need(neg['individual_Cost_source_rows']==neg['individual_MSA_source_rows']==neg['collier_1876_Cost_source_rows']==[],'False negative-search result')
    need(not any(r['Plan Type'] in ['Cost','MSA'] for r in local_l) and not any(r['Organization Type']=='1876 Cost' for r in local_a),'Negative search contradicted')
    need(neg['collier_MSA_source_rows']==[f'{A}:{n}' for n,r in aa.items() if r['FIPS']=='12021' and r['Organization Type']=='MSA'],'MSA excluded')
    expected={'90091','H4556','H5934','H6130','H6142','H6334','X0001'}
    need({r['id'] for r in data['paths']}==expected,'Alternate candidate denominator')
    for p in data['paths']:
        guard_path(p);dr=by[p['directory_source_record_id']]['raw'];areas=[by[k]['raw'] for k in p['service_area_source_record_ids']]
        need(dr['Contract Number']==p['id'] and all(r['Contract ID']==p['id'] for r in areas),'Inexact contract join')
        need((p['organization_name'],p['organization_type'],p['plan_type'],p['contract_effective_date'],p['directory_enrollment'])==(areas[0]['Organization Name'],areas[0]['Organization Type'],areas[0]['Plan Type'],dr['Contract Effective Date'],dr['Enrollment']),'Path source field changed')
    sa={r['Contract ID'] for r in aa.values() if r['Organization Type']=='National PACE'};di={r['Contract Number'] for r in dd.values() if r['Organization Type']=='National PACE'};an=data['source-anomalies']
    need(len(sa)==243 and len(di)==208 and an['pace_area_only']==sorted(sa-di) and an['pace_directory_only']==[],'PACE source mismatch lost')
    need(len(an['pace_national_note_records'])==243 and all(by[k]['normalized']['national_note'] for k in an['pace_national_note_records']),'PACE geography defect lost')
    need(len(an['Fenyx_FL_MSA_geography_records'])==68,'Legacy geography deduped silently')
    for r in data['state-observations']:
        guard_state(r);t=fresh[r['source_id']];ps=t.split('\f');need([i for i,p in enumerate(ps,1) if 'Collier' in p]==[5,13],'Unaccounted Collier state mention')
        op=next(x for x in ps[4].splitlines() if re.search(r'Hope PACE\s+Collier\s+Operational',x));co=next(x for x in ps[12].splitlines() if re.match(r'\s*Collier\s+Hope PACE',x))
        cells=re.split(r'\s{2,}',op.strip());cc=re.split(r'\s{2,}',co.strip());need(r['raw_operational_cells']==cells and r['raw_county_cells']==cc,'PDF cells shifted')
        values=[r[k] for k in ['slots_approved','slots_funded','enrollment_first_of_month','county_current_month_enrollees','fiscal_year_unique_individuals']]
        need(values==[int(cells[5]),int(cells[6]),int(cells[7]),int(cc[3]),int(cc[4])],'Typed state values changed')
        need(r['actuarial_dual_rate_dollars']==cells[8] and r['estimated_claims_dollars']==cells[9:] and r['initial_AHCA_approval']==cells[3] and r['slots_requested']==cells[4] and r['status']==cells[2],'Other state fields changed')
        need('All counties within the state are reflected' in t and len(re.findall(r'\bCollier\b',t))==2,'State census scope changed')
    from l14_catalog import RULES,RECONCILIATIONS,GAPS
    authored={r['id']:r for r in RULES};need(len(data['rules'])==len(authored)==21,'Rule inventory')
    for r in data['rules']:
        for key,value in authored[r['id']].items():need(r[key]==value,'Modeled rule field mismatch '+r['id']+' '+key)
        context=' '.join(u[k]['text'] for k in r['source_clause_ids'])
        for pattern in r['checks']:need(re.search(pattern,context,re.I) is not None,'Missing operative source condition '+r['id'])
    for rows in [data['rules'],data['reconciliations'],data['state-observations'],data['restricted-documents']]:
        for r in rows:
            for key in r['source_clause_ids']:need(key in u,'Dangling citation '+key)
            for clause in r.get('source_conditions',[]):need(clause['text']==u[clause['source_clause_id']]['text'],'Lost complete source context')
    need([{k:r[k] for k in a} for r,a in zip(data['reconciliations'],RECONCILIATIONS)]==RECONCILIATIONS and data['gaps']==GAPS,'Reconciliation/gap change')
    for r in data['restricted-documents']:
        sid=r['source_id'];p=fresh[sid].split('\f');title=norm(p[0]);m=re.search(r'H6130 Plans (.*?) An MSA',title)
        need(title.startswith('2026 Summary of Benefits') and m and r['publisher_identity_text']==m[1] and r['plan_ids']==re.findall(r'\b8\d{2}\b',m[1]),'Restricted source identity mismatch')
        need(r['physical_pdf_pages']==len(p)-1 and r['unified_plan_join'].startswith('held_') and r['personal_quote'] is None,'Unified conflicting MSA plan')
    # Reuse the held PBP before calling a group identity missing. Read physical columns
    # as arrays: both members have repeated header labels that must not be overwritten.
    pbp=data['pbp-reuse-inventory'];z=zipfile.ZipFile(ROOT/s['cms-pbp-2026-reused']['path']);pbp_cells=0
    for member in pbp['members']:
        name=member['member'];b=z.read(name);reader=csv.reader(io.StringIO(b.decode('cp1252')),delimiter='\t');headers=next(reader);expected=[];number=0;cohort=0
        for number,values in enumerate(reader,1):
            if values[0]!='H6130':continue
            cohort+=1
            if name=='PlanArea.txt' and not (values[15]=='Collier' and values[16]=='FL'):continue
            expected.append((number,values))
        need(headers==member['headers'] and number==member['national_rows'] and cohort==member['H6130_national_rows'] and hashlib.sha256(b).hexdigest()==member['member_sha256'],'PBP member/accounting mismatch')
        need(len(expected)==len(member['retained_rows'])==18,'PBP restricted identity denominator')
        for r,(n,values) in zip(member['retained_rows'],expected):
            compare_cells(r['values'],values);pbp_cells+=len(values)
            want=dict(source_row=n,values=values,contract_id=values[0],plan_id=values[1],segment_id_source=values[2],plan_name=values[19] if name=='pbp_Section_A.txt' else None,
                group_flag=values[27] if name=='pbp_Section_A.txt' else values[14],county_code_SSA=values[10] if name=='PlanArea.txt' else None,
                pending_flag=values[11] if name=='PlanArea.txt' else None,partial_flag=values[12] if name=='PlanArea.txt' else None,
                source_year=values[13] if name=='PlanArea.txt' else '2026',personal_eligibility=None,consumer_plan_acceptance=None)
            need(r==want and r['group_flag']=='1' and r['source_year']=='2026','PBP modeled identity/restriction changed')
        need({r['plan_id'] for r in member['retained_rows']}=={str(i) for i in range(801,819)},'PBP group IDs omitted')
    need(pbp_cells==pbp['preserved_original_cells']==ref['PBP_additional_original_cells']==1890,'PBP cell accounting')
    pbp_scanned=sum(m['national_rows'] for m in pbp['members'])
    need(ref['PBP_additional_national_rows_scanned']==pbp_scanned==2305248 and ref['national_rows_scanned']==scan+pbp_scanned==2860952,'Combined national scan accounting')
    need(u['cms-pbp-2026-reused:IDENTITY']['text']==json.dumps(pbp,sort_keys=True),'PBP identity context truncated')
    msa=next(r for r in data['paths'] if r['id']=='H6130')
    need(msa['CMS_group_plan_observations']==[dict(plan_id=r['plan_id'],segment_id_source=r['segment_id_source'],plan_name=r['plan_name'],source_member='pbp_Section_A.txt',source_row=r['source_row']) for r in pbp['members'][0]['retained_rows']],'PBP contract/plan identity attachment mismatch')
    docs=load(ROOT/s['fenyx-designs-current']['structured_text_path']);need(any('2026 Evidence of Coverage' in l['text'] and l['url']=='#' for l in docs['links']),'Broken EOC anchor basis changed')
    # Exact SQLite parity for every stored JSON key and row; read-only connection.
    with closing(sqlite3.connect('file:'+str(BUILD/'reference.sqlite')+'?mode=ro',uri=True)) as db:
        need(db.execute('PRAGMA integrity_check').fetchone()==('ok',),'SQLite integrity')
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")};need(tables==set(data),'SQLite dataset set changed')
        for name,rows in data.items():
            want=rows if isinstance(rows,dict) else {str(r.get('id',i)):r for i,r in enumerate(rows)}
            got={k:json.loads(v) for k,v in db.execute('SELECT id,payload FROM "'+name+'"')};need(got==want,'SQLite field parity '+name)
    checked=parents()
    inputs.update(p for p in BUILD.rglob('*') if p.is_file() and p.name!='manifest.json')
    inputs.update(p for p in BASE.joinpath('acquisition-r1').rglob('*') if p.is_file())
    inputs.update(p for p in ROOT.joinpath('cms-slice/scripts').glob('l14_*.py'))
    inputs.update([BASE/'reuse-inputs.json',ROOT/'cms-slice/scripts/l12_sources.py',ROOT/'cms-slice/tests/test_l14_reference.py'])
    return dict(passed=True,failures=[],validated_at_utc=datetime.now(timezone.utc).isoformat(),national_core_rows=scan,PBP_additional_national_rows=pbp_scanned,total_national_rows=scan+pbp_scanned,retained_rows=retained,original_cells_compared=cell_count,
        normalized_cells_compared=sum(len(r['normalized']) for r in data['records']),PBP_additional_original_cells_compared=pbp_cells,PBP_group_identities_and_Collier_rows_compared=36,retained_sources=49,physical_PDF_pages=pdf_pages,rule_families_compared=21,source_reconciliations=11,qualified_review=None,human_acceptance=None,
        checks=['Whole national routing and category accounting','All retained original and normalized fields','Exact contract and geography joins','Dated negative searches and source exclusions','Every Collier report occurrence and all modeled chart cells','Full source conditions and explicit conflicts','Every CSV/JSON/SQLite field','Parent seals'],
        semantic_review='AI read and compared modeled meanings/qualifications against operative primary passages; machine assertions verify identities, quantities and retained complete conditions. No independent specialist review claimed.',
        validated_inputs={str(p.relative_to(ROOT)):fp(p) for p in sorted(inputs)},**checked)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args()
    if a.write:need(not (BUILD/'manifest.json').exists(),'Sealed validation; read-only verify only')
    r=validate()
    if a.write:VAL.mkdir(exist_ok=True);write(VAL/'validation.json',r)
    print(json.dumps({k:v for k,v in r.items() if k not in ['validated_inputs','parent_manifest_hashes']},indent=2))
