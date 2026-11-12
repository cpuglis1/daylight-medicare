"""Read-only L13 source/field/parity validation. --write records a pre-seal receipt."""
import argparse
from contextlib import closing
from copy import deepcopy
import hashlib,json,re,sqlite3,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from l12_sources import PublicHTML
from l13_cases import run_cases
from l13_catalog import RULES,QUANTITIES,RECONCILIATIONS,GAPS,CLOCKS
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/data/l13-enrollment-2026-10-28';BUILD=BASE/'build-r1'
def norm(t):return ' '.join(t.split())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def need(ok,msg):
    if not ok:raise ValueError(msg)
def dataset():
    with closing(sqlite3.connect('file:'+str(BUILD/'l13-reference.sqlite')+'?mode=ro',uri=True)) as db:
        return {name:load(BUILD/name) for name, in db.execute('SELECT name FROM datasets')}

def check_clock_models(data):
    u={r['id']:r['text'] for r in data['source-clause-ledger.json']};c={r['id']:r for r in data['clocks.json']}
    # Independently stated source assertions and modeled values. These do not execute eligibility.
    specs={
    'K01':({'start_month_offset':-3,'end_month_offset':3,'inclusive_months':7},'cfr-407-20261027:CFR:407.14',[r'7-month',r'begins 3 months before',r'ends 3 months after']),
    'K02':({'early_months':'first_3','early_start':'eligibility_month','later_months':'last_4','later_start':'next_month'},'cfr-407-20261027:CFR:407.25',[r'first 3 months.*?first month of eligibility',r'last 4 months.*?month following']),
    'K03':({'start':'01-01','end_inclusive':'03-31','coverage':'next_month'},'cms-ab-enrollment:ALL',[r'January 1 through March 31']),
    'K04':({'end':'last_day_8th_consecutive_wholly_uncovered_month','covered_or_first_uncovered_start_options':'enrollment_month_through_plus_3','later_start':'next_month'},'cfr-406-20261027:CFR:406.24',[r'last day of the eighth consecutive month',r'first full month',r'three following months']),
    'K05':({'start':'first_day_cessation_month','duration_months_including_start':6,'coverage':'next_month'},'cfr-407-20261027:CFR:407.21',[r'6-month period beginning on the first day of the month that includes',r'month following']),
    'K06':({'start':'earlier_declared_or_incident_start','end':'applicable_end_plus_6_months','coverage':'next_month'},'cfr-407-20261027:CFR:407.23',[r'earlier of the date',r'ends 6 months after',r'end date of any extensions']),
    'K07':({'start':'SSA_notification_day','end':'six_months_later','coverage':'next_month'},'cfr-407-20261027:CFR:407.23',[r'day the individual notifies SSA',r'ends 6 months later']),
    'K08':({'start':'actual_release_day','end':'last_day_12th_month_after_release','retroactive_max_months':6},'cfr-407-20261027:CFR:407.23',[r'last day of the 12th month after the month',r'retroactive period of up to 6 months',r'halfway houses']),
    'K09':({'start':'notice','end':'termination_plus_6_months','coverage':'next_month_or_elected_retroactive'},'cfr-407-20261027:CFR:407.23',[r'notified of termination.*?ends 6 months after',r'pays the monthly premiums']),
    'K10':({'start':None,'end':None,'agency_duration_min_months':6},'cfr-407-20261027:CFR:407.23',[r'case by case basis.*?no less than 6 months']),
    'K11':({'start':'first_AB_month_minus_3','end':'later_of_end_AB_plus_2_months_or_B_IEP_end'},'cfr-422-B-20261027:CFR:422.62',[r'begins 3 months before',r'ends on the later of',r'last day of the second month after',r'Part B initial enrollment period']),
    'K12':({'start':'10-15','end_inclusive':'12-07','coverage':'01-01_following_year'},'cfr-423-B-20261027:CFR:423.38',[r'following calendar year is October 15 through December 7']),
    'K13':({'start':'01-01','end_inclusive':'03-31','max_elections':1,'coverage':'next_month'},['cms-2026-enrollment:GUIDE:30.4','cfr-422-B-20261027:CFR:422.62'],[r'January 1.*?March 31',r'make an election once']),
    'K14':({'start':'qualifying_institutional_status','end':'last_day_2nd_month_after_leaving'},'cfr-422-B-20261027:CFR:422.62',[r'last day of the second month after.*?ceases to reside']),
    'K15':({'frequency':'one_per_month','coverage':'next_month'},'cms-2026-enrollment:GUIDE:30.6.7',[r'once per month',r'first of the following month',r'at-risk beneficiary']),
    'K16':({'end':'end_of_2_full_calendar_months_after_applicable_event_end'},'cms-2026-enrollment:GUIDE:30.6.25',[r'ends two full calendar months following',r'Did not make an election.*?due to the disaster']),
    'K17':({'duration_calendar_days':60,'anchor':'LEP_notice_date'},'cms-d-lep-2026:GUIDE:70.1',[r'60 calendar days from the date of the LEP letter',r'pays the penalty while their reconsideration is under review'])}
    need(set(c)==set(specs),'Clock denominator changed')
    for key,(fields,sid,patterns) in specs.items():
        need(c[key]['modeled_fields']==fields,'Changed clock fields '+key)
        text=' '.join(u[k] for k in sid) if isinstance(sid,list) else u[sid]
        for p in patterns:need(re.search(p,text,re.I) is not None,'Source clock assertion '+key+' '+p)
        need(c[key]['personal_determination_enabled'] is False,'Clock released '+key)
    return len(specs)

def check_data(data):
    s=data['summary.json'];sources=data['sources.json'];units=data['source-clause-ledger.json'];u={r['id']:r for r in units}
    need(len(units)==len(u),'Duplicate source unit')
    need(s['reference_year']==2026 and s['legal_snapshot']=='2026-10-27','Reference dates')
    need(s['full_l13_complete'] is False and s['qualified_R18_review'] is None and s['exact_reference_acceptance'] is None,'Unreviewed completion/acceptance')
    need(s['consumer_eligibility_deadlines_penalty_api_enabled'] is False and not s['recommendations_enabled'] and not s['UI_or_deployment_changes'],'Product scope expanded')
    expected_counts={'retained_sources':48,'reused_sources':8,'new_sources':40,'physical_PDF_pages':395,'rule_families':37,'MA_regulatory_SEP_roots':27,'D_regulatory_SEP_roots':36,'AB_exceptional_roots':10,'CMS_guidance_SEP_sections':36,'typed_quantity_observations':24,'clock_definitions':17,'source_reconciliations':11}
    for k,v in expected_counts.items():need(s[k]==v,'Denominator '+k)
    need(len(sources)==48,'Source denominator')
    need(s['source_units']==len(units),'Source unit accounting')
    for name,rows in data.items():
        if not isinstance(rows,list):continue
        if all(isinstance(r,dict) and 'id' in r for r in rows):need(len({r['id'] for r in rows})==len(rows),'Duplicate id '+name)
        for r in rows:
            for k in r.get('source_clause_ids',[]):need(k in u,'Dangling citation '+str(k))
            for e in r.get('source_conditions',[]):need(e['text']==u[e['source_clause_id']]['text'],'Truncated or changed source conditions '+r['id'])
    need(len(data['rules.json'])==37 and len(data['clocks.json'])==17,'Family/clock inventory')
    authored={r['id']:r for r in RULES}
    for r in data['rules.json']:
        for k,v in authored[r['id']].items():need(r[k]==v,'Authored field parity '+r['id']+' '+k)
        need(bool(r['meaning']) and len(r['required_case_evidence'])>0 and len(r['source_conditions'])==len(r['source_clause_ids']),'Incomplete rule fields '+r['id'])
        need(r['acceptance'] is None and r['qualified_R18_review'] is None and not r['personal_determination_enabled'],'Rule released '+r['id'])
    # Roots checked independently from fresh XML, complete direct paragraphs including all nested conditions.
    allroots=data['regulatory-SEP-inventory.json']
    for sid,sec,letter,count,prefix in [('cfr-422-B-20261027','422.62','b',27,'MA'),('cfr-423-B-20261027','423.38','c',36,'D')]:
        section=next(n for n in ET.parse(ROOT/sources[sid]['path']).iter('DIV8') if n.get('N')==sec)
        ps=[norm(' '.join(n.itertext())) for n in section.findall('P')]
        begin=next(i for i,t in enumerate(ps) if t.startswith('('+letter+') '))
        end=next((i for i in range(begin+1,len(ps)) if ps[i].startswith('('+chr(ord(letter)+1)+') ')),len(ps));body=ps[begin+1:end]
        starts=[(i,int(m[1])) for i,t in enumerate(body) if (m:=re.match(r'^\((\d+)\)',t))]
        need([n for _,n in starts]==list(range(1,count+1)),'Missing source SEP roots')
        got={r['id']:r for r in allroots if r['source_id']==sid};need(len(got)==count,'SEP inventory denominator')
        for j,(a,n) in enumerate(starts):
            stop=starts[j+1][0] if j+1<len(starts) else len(body);r=got[f'{prefix}:{letter}:{n}'];text=' '.join(body[a:stop])
            need(r['source_native_conditions']==text and r['parent_conditions']==ps[begin],'Missing root/nested/parent condition '+r['id'])
            flag='explicitly_required' if 'requires CMS approval prior to use' in text else 'not_explicitly_stated_in_this_root_check_full_context'
            need(r['prior_CMS_approval']==flag,'Approval requirement lost '+r['id'])
            expected=[x.strip() for x in re.split(r'(?<=[.;])\s+(?=[A-Z(])',text) if re.search(r'\b(month|day|year|begin|end|effective|once|election)',x,re.I)]
            need(r['timing_sentences']==expected,'Timing extraction '+r['id'])
            need(r['personal_determination_enabled'] is False and r['qualified_review'] is None,'SEP released')
    need(next(r for r in allroots if r['id']=='MA:b:9')['temporal_status']=='historical_ended_2020_not_active_2026','Expired route revived')
    for sid,sec,prefix in [('cfr-406-20261027','406.27','premium-A'),('cfr-407-20261027','407.23','B')]:
        ps=[norm(' '.join(n.itertext())) for n in next(n for n in ET.parse(ROOT/sources[sid]['path']).iter('DIV8') if n.get('N')==sec).findall('P')]
        starts=[(i,t[1]) for i,t in enumerate(ps) if re.match(r'^\([a-f]\)',t)]
        need([k for _,k in starts]==list('abcdef'),'AB exceptional source groups')
        for j,(a,k) in enumerate(starts[1:],1):
            end=starts[j+1][0] if j+1<len(starts) else len(ps)
            r=next(r for r in data['AB-exceptional-SEP-inventory.json'] if r['id']==prefix+':'+k)
            need(r['source_native_conditions']==' '.join(ps[a:end]) and r['parent_conditions']==ps[starts[0][0]],'AB exception conditions')
    cs=data['CMS-SEP-comparisons.json'];need(len(cs)==36,'Guidance SEP inventory')
    need({r['section'] for r in cs}=={'30.6.'+str(i) for i in range(1,37)},'Guidance section omitted')
    mapped=set()
    for r in cs:
        need(r['guide_conditions']==u[r['guide_source_clause_id']]['text'],'Guidance conditions changed')
        need(r['source_native_citations']==re.findall(r'\b(?:406|407|411|422|423)\.\d+(?:\([A-Za-z0-9]+\))*',r['guide_conditions']),'Source-native citation field')
        need(bool(r['citation_warning'])==(r['section']=='30.6.36'),'Stale catch-all citation warning lost')
        for b in r['regulatory_relationships']:
            if 'regulatory_root_id' in b:
                mapped.add(b['regulatory_root_id']);root=next(x for x in allroots if x['id']==b['regulatory_root_id'])
                need(b['complete_root_conditions']==root['source_native_conditions'],'Crosswalk truncation')
            else:need(b['complete_section_conditions']==u[b['source_clause_ids'][0]]['text'],'Context truncation')
    # b22 is in 30.1 (additional IEP), c26 in 30.4 (MA OEP), b9 explicitly historical.
    extra=data['additional-regulatory-context.json']
    need({r['id'] for r in allroots}-mapped=={r['regulatory_root_id'] for r in extra}=={'MA:b:9','MA:b:22','D:c:26'},'Unaccounted regulatory route')
    for r in extra:need(r['source_native_conditions']==next(x for x in allroots if x['id']==r['regulatory_root_id'])['source_native_conditions'],'Additional context conditions')
    need('422.62(b)(22)' in u['cms-2026-enrollment:GUIDE:30.1']['text'],'Additional IEP coordinating source omitted')
    qs=data['quantities.json'];need(len(qs)==24,'Quantity denominator')
    for r in qs:
        authored_q=next(q for q in QUANTITIES if q[0]==r['id'])
        need([r['title'],r['value'],r['unit'],r['source_clause_ids'][0],r['source_pattern']]==list(authored_q[1:]),'Quantity modeled field parity '+r['id'])
        text=u[r['source_clause_ids'][0]]['text'];m=re.search(r['source_pattern'],text,re.I)
        need(m is not None and r['source_quote']==text[max(0,m.start()-130):min(len(text),m.end()+180)],'Quantity source '+r['id'])
    # Independent typed values catch a changed numeric field even when its source quote is left intact.
    expected_values=[7,3,3,4,8,3,6,12,6,12,6,2,1,1,10,10,63,'38.99',1,'0.10',60,20,100,30]
    need([r['value'] for r in qs]==expected_values,'Typed value changed')
    check_clock_models(data)
    for r in data['clocks.json']:
        authored_clock=next(x for x in CLOCKS if x[0]==r['id'])
        need([r['rule_id'],r['clock'],r['modeled_fields'],r['required_conditions']]==list(authored_clock[1:]),'Clock conditions/units fields changed')
        need(r['source_clause_ids']==authored[r['rule_id']]['source_clause_ids'],'Clock source binding changed')
    rc={r['id']:r for r in data['reconciliations.json']};need(len(rc)==11,'Reconciliation denominator')
    for i,title,rule,status,meaning,ids in RECONCILIATIONS:
        need([rc[i][k] for k in ['title','rule_id','status','disposition','source_clause_ids']]==[title,rule,status,meaning,ids],'Reconciliation field parity '+i)
    need(data['gaps.json']==GAPS,'Gap/closure conditions changed')
    need(rc['RC06']['status']=='exact_personal_date_held' and s['known_published_exact_date_hold']==['RC06'],'Contract window hold removed')
    need('38.99' in next(r for r in data['rules.json'] if r['id']=='PD02')['meaning'],'Penalty basis omitted')
    need(next(r for r in data['gaps.json'] if r['id']=='G01')['consumer_exact_date_enabled'] is False,'Held gap released')
    a={r['id']:r for r in data['annual-windows.json']}
    need([a['AEP-for-2026'][k] for k in ['election_start','election_end_inclusive','coverage_start']]==['2025-10-15','2025-12-07','2026-01-01'],'2026 AEP year wrong')
    need([a['AEP-fall-2026-for-2027'][k] for k in ['election_start','election_end_inclusive','coverage_start']]==['2026-10-15','2026-12-07','2027-01-01'],'Fall2026 coverage year wrong')
    need(not a['AEP-fall-2026-for-2027']['plan_inventory_in_this_reference'] and not a['AEP-fall-2026-for-2027']['annual_penalty_base_available_in_this_reference'],'2027 data inferred')
    l01=next(r for r in data['layer-boundaries.json'] if r['id']=='L01');costbase=ROOT/'docs/data/l01-national-2026/published-reference-r1'
    need(l01['exact_annual_cost_records']==[r for r in load(costbase/'costs.json') if r['id'] in ['a_premium_full','a_premium_reduced','b_premium']],'L01 annual base record field parity')
    need(l01['published_reference_manifest_sha256']==digest(costbase/'manifest.json')=='16578a342c13755e0cfd29417af4228bba691ee36fd55e81c3b346d6db9ddfc1','L01 manifest identity')
    need(l01['L13_acceptance_inherited'] is False,'L01 acceptance inherited into L13')
    for path,fp in l01['pinned_reference_inputs'].items():need((ROOT/path).stat().st_size==fp['bytes'] and digest(ROOT/path)==fp['sha256'],'L01 pinned input changed')
    return {'all_modeled_records_structurally_checked':sum(len(x) for x in data.values() if isinstance(x,list)), 'complete_regulatory_SEP_roots':63,'complete_AB_exceptional_roots':10,'CMS_SEP_crosswalks':36,'typed_values_checked':24,'clock_models_checked':17}

def fresh_source_checks(data):
    sources=data['sources.json'];fresh={};pages=0;html=0;xml=0
    for sid,s in sources.items():
        raw=ROOT/s['path'];need(s['status']=='retained' and raw.stat().st_size==s['bytes'] and digest(raw)==s['sha256'],'Raw source '+sid)
        receipt=load(ROOT/s['receipt_path'])
        # Historical reuse can be nested in a resource packet. Match an actual receipt,
        # never treat the enclosing packet or its former freshness label as new evidence.
        def candidates(obj):
            if isinstance(obj,dict):
                yield obj
                for v in obj.values():yield from candidates(v)
            elif isinstance(obj,list):
                for v in obj:yield from candidates(v)
        need(any(r.get('sha256')==s['sha256'] and r.get('url',r.get('requested_url'))==s['url'] for r in candidates(receipt)),'Source receipt '+sid)
        body=raw.read_bytes()
        if body.startswith(b'%PDF'):
            text=subprocess.run(['pdftotext','-layout',str(raw),'-'],check=True,capture_output=True).stdout.decode();pages+=text.count('\f')
            need(text.count('\f')==s['pdf_pages'],'PDF page count '+sid)
        elif s['extraction_kind']=='ecfr_xml_sections':
            tree=ET.fromstring(body);sections=[{'section':n.get('N'),'text':norm(' '.join(n.itertext()))} for n in tree.iter('DIV8')]
            need({'sections':sections}==load(ROOT/s['structured_text_path']),'XML complete field parity '+sid)
            text='\n'.join(x['text'] for x in sections)+'\n';xml+=1
        else:
            p=PublicHTML();p.feed(body.decode(errors='replace'));parsed=p.result()
            need(parsed==load(ROOT/s['structured_text_path']),'HTML lines/tables/links parity '+sid)
            text='\n'.join(parsed['lines'])+'\n';html+=1
        need(text==(ROOT/s['text_path']).read_text(),'Fresh extraction parity '+sid);fresh[sid]=norm(text)
    for r in data['source-clause-ledger.json']:
        need(r['text'] in fresh[r['source_id']],'Unit is not exact source text '+r['id'])
    return dict(raw_sources_checked=len(sources),fresh_PDF_pages_checked=pages,HTML_sources_checked=html,XML_sources_checked=xml,exact_source_units_checked=len(data['source-clause-ledger.json']))

def sqlite_checks(data):
    count=0
    with closing(sqlite3.connect('file:'+str(BUILD/'l13-reference.sqlite')+'?mode=ro',uri=True)) as db:
        need(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity')
        need(set(data)=={n for n, in db.execute('SELECT name FROM datasets')},'Dataset names')
        for name,obj in data.items():
            need(json.loads(db.execute('SELECT payload FROM datasets WHERE name=?',(name,)).fetchone()[0])==obj,'JSON/SQLite all fields '+name)
            expected={str(r.get('id',i)):r for i,r in enumerate(obj)} if isinstance(obj,list) else {}
            actual={k:json.loads(p) for k,p in db.execute('SELECT id,payload FROM records WHERE dataset=?',(name,))}
            need(actual==expected,'SQLite row field parity '+name);count+=len(actual)
    return dict(datasets_checked=len(data),SQLite_JSON_records_checked=count,SQLite_integrity='ok')

def parent_checks():
    targets=[('docs/data/l11-medigap-rights-2026-10-28/build-r2/manifest.json','30f3e52478b1e35003560eda8b58c65e14325fab8591a4fae38450c52ccdc1a0'),('docs/data/l12-help-with-costs-2026-10-28/build-r1/manifest.json','93fb2cac9e490cb7a6670e1cec0cc192686be064fcba8a1be1e36580173189cd'),('docs/data/l12-help-with-costs-2026-10-28/build-r2/manifest.json','566aa6ec0d76a5d9a6291350eeb7c60dc7e35c1d1355a65bf2da429be93375a5')]
    checked=set()
    for path,h in targets:
        need(digest(ROOT/path)==h,'Parent manifest changed '+path)
        manifest=load(ROOT/path)
        entries={str((ROOT/path).parent/p if path.startswith('docs/data/l11') else ROOT/p):r for p,r in manifest['files'].items()}
        if isinstance(manifest.get('external_inputs'),dict):entries.update({str(ROOT/p):r for p,r in manifest['external_inputs'].items()})
        for p,r in entries.items():
            if p in checked:continue
            need(Path(p).stat().st_size==r['bytes'] and digest(Path(p))==r['sha256'],'Sealed parent byte changed '+p);checked.add(p)
    return dict(parent_manifests_preserved=3,unique_parent_pinned_files_preserved=len(checked))

def sealed_checks():
    if not (BUILD/'manifest.json').exists():return dict(sealed=False)
    m=load(BUILD/'manifest.json')
    for p,r in m['files'].items():need((ROOT/p).stat().st_size==r['bytes'] and digest(ROOT/p)==r['sha256'],'Sealed L13 byte changed '+p)
    need(m['qualified_R18_review'] is None and m['human_acceptance'] is None and not m['consumer_release_enabled'] and not m['full_l13_complete'],'Sealed scope release changed')
    return dict(sealed=True,sealed_files_checked=len(m['files']))

def validate():
    data=dataset();r={**check_data(data),**fresh_source_checks(data),**sqlite_checks(data),**parent_checks()}
    cases=run_cases();need(all(c['passed'] for c in cases),'Synthetic date/penalty failure')
    inputs={BUILD/name for name in data}|{BUILD/'l13-reference.sqlite',BASE/'synthetic-cases.json',ROOT/'cms-slice/scripts/l12_sources.py',ROOT/'cms-slice/tests/test_l13_reference.py'}
    inputs.update(ROOT.joinpath('cms-slice/scripts').glob('l13_*.py'))
    inputs.update(ROOT/p for p in next(r for r in data['layer-boundaries.json'] if r['id']=='L01')['pinned_reference_inputs'])
    for source in data['sources.json'].values():
        inputs.update(ROOT/source[k] for k in ['path','text_path','receipt_path'])
        if source.get('structured_text_path'):inputs.add(ROOT/source['structured_text_path'])
    r.update(synthetic_cases=len(cases),synthetic_cases_passed=sum(c['passed'] for c in cases),qualified_R18_review=None,exact_acceptance=None,full_l13_complete=False,consumer_release_enabled=False,failures=[],passed=True,
             validated_inputs={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(inputs)})
    return r,cases
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args()
    if a.write:need(not (BUILD/'manifest.json').exists(),'Cannot write into sealed reference')
    result,cases=validate()
    if a.write:
        out=BASE/'validation-r1';out.mkdir(exist_ok=True)
        for name,obj in [('validation.json',result),('synthetic-results.json',cases)]: (out/name).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
    print(json.dumps({**{k:v for k,v in result.items() if k!='validated_inputs'},'validated_input_files':len(result['validated_inputs']),**sealed_checks()},indent=2))
