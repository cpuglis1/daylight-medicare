"""Build the isolated, source-scoped L13 2026 published reference."""
from contextlib import closing
from copy import deepcopy
import hashlib,json,re,sqlite3,xml.etree.ElementTree as ET
from pathlib import Path
from l13_catalog import RULES,QUANTITIES,CLOCKS,GUIDE_MAP,RECONCILIATIONS,GAPS
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/data/l13-enrollment-2026-10-28';ACQ=BASE/'acquisition-r1';BUILD=BASE/'build-r1'
def norm(t):return ' '.join(t.split())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')

def guide_units(sid,s):
    text=(ROOT/s['text_path']).read_text().replace('\f','\f\n');starts={}
    # Skip tables of contents by physical page. Last actual section heading wins.
    minimum=13 if sid=='cms-2026-enrollment' else 6
    for m in re.finditer(r'(?m)^[ \t]*(\d{2}(?:\.\d+)*)[ \t]+[–—-][ \t]+([^\n]+)',text):
        page=text[:m.start()].count('\f')+1
        if page>minimum:starts[m.group(1)]=(m.start(),m.group(2).strip(),page)
    order=sorted((pos,k,title,page) for k,(pos,title,page) in starts.items());rows=[]
    for n,(pos,key,title,page) in enumerate(order):
        parts=key.split('.');end=len(text)
        for nxt,k2,_,_ in order[n+1:]:
            if not k2.startswith(key+'.'):end=nxt;break
        rows.append(dict(id=sid+':GUIDE:'+key,source_id=sid,text=norm(text[pos:end]),
            locator={'section':key,'physical_pdf_page':page,'includes_descendant_sections':True},
            disposition='retained_source_context_not_independently_accepted'))
    return rows

def make_units(sources):
    units=[]
    for sid,s in sources.items():
        if s['status']!='retained':continue
        text=(ROOT/s['text_path']).read_text()
        units.append(dict(id=sid+':ALL',source_id=sid,text=norm(text),locator={'method':s['extraction_kind']},disposition='retained_source_context'))
        if s['extraction_kind']=='native_pdf_text':
            units += [dict(id=sid+':PAGE:'+str(i),source_id=sid,text=norm(t),locator={'physical_pdf_page':i},disposition='retained_source_context') for i,t in enumerate(text.split('\f')[:-1],1)]
            if sid in ['cms-2026-enrollment','cms-d-lep-2026']:units+=guide_units(sid,s)
        elif s['extraction_kind']=='ecfr_xml_sections':
            units += [dict(id=sid+':CFR:'+r['section'],source_id=sid,text=r['text'],locator={'section':r['section'],'snapshot_date':'2026-01-01' if sid=='ecfr-422-62-jan' else '2026-10-27'},disposition='retained_source_context') for r in load(ROOT/s['structured_text_path'])['sections']]
    return units

def root_groups(sources,sid,section,letter,expected,prefix):
    tree=ET.parse(ROOT/sources[sid]['path']);node=next(n for n in tree.iter('DIV8') if n.get('N')==section)
    paragraphs=[norm(' '.join(n.itertext())) for n in node.findall('P')]
    active=False;groups={};key=None;intro=None
    for t in paragraphs:
        if re.match(r'^\('+letter+r'\)',t):active=True;intro=t;continue
        if active and re.match(r'^\('+chr(ord(letter)+1)+r'\)',t):break
        if not active:continue
        m=re.match(r'^\((\d+)\)',t)
        if m:key=int(m[1]);groups[key]=[]
        if key is not None:groups[key].append(t)
    assert sorted(groups)==list(range(1,expected+1)),(sid,section,list(groups))
    return [dict(id=f'{prefix}:{letter}:{k}',source_id=sid,section=section,paragraph=f'({letter})({k})',
         parent_conditions=intro,source_native_conditions=' '.join(v),
         source_clause_ids=[sid+':CFR:'+section],
         prior_CMS_approval='explicitly_required' if 'requires CMS approval prior to use' in ' '.join(v) else 'not_explicitly_stated_in_this_root_check_full_context',
         timing_sentences=[x.strip() for x in re.split(r'(?<=[.;])\s+(?=[A-Z(])',' '.join(v)) if re.search(r'\b(month|day|year|begin|end|effective|once|election)',x,re.I)],
         temporal_status='historical_ended_2020_not_active_2026' if prefix=='MA' and k==9 else 'source_conditions_and_edition_apply_no_personal_eligibility_inferred',
         normalization='source_native_complete_root_including_nested_paragraphs',qualified_review=None,personal_determination_enabled=False)
       for k,v in groups.items()]

def ab_groups(sources,sid,sec,prefix):
    tree=ET.parse(ROOT/sources[sid]['path']);node=next(n for n in tree.iter('DIV8') if n.get('N')==sec)
    intro=None;group={};key=None
    for n in node.findall('P'):
        t=norm(' '.join(n.itertext()));m=re.match(r'^\(([a-f])\)',t)
        if m:
            key=m[1]
            if key=='a':intro=t
            else:group[key]=[]
        if key in group:group[key].append(t)
    assert list(group)==list('bcdef')
    return [dict(id=f'{prefix}:{k}',section=sec,paragraph=f'({k})',source_id=sid,parent_conditions=intro,
                 source_native_conditions=' '.join(v),source_clause_ids=[sid+':CFR:'+sec],personal_determination_enabled=False,qualified_review=None) for k,v in group.items()]

def build():
    if (BUILD/'manifest.json').exists():raise ValueError('Sealed build; new revision required')
    sources=load(ACQ/'extraction-index.json');units=make_units(sources);lookup={r['id']:r for r in units}
    rules=deepcopy(RULES)
    for r in rules:
        for k in r['source_clause_ids']:
            if k not in lookup:raise ValueError('Missing rule source '+r['id']+' '+k)
        r['source_conditions']=[{'source_clause_id':k,'text':lookup[k]['text']} for k in r['source_clause_ids']]
        r['AI_validation']={'modeled_fields':['title','meaning','required_case_evidence','applicability','source_clause_ids','source_conditions'],
            'method':'Read operative primary passages, compare numeric/date branches, retain complete source conditions; independent numeric/text and synthetic checks in validation packet',
            'qualified_or_external_review_claimed':False}
    seps=root_groups(sources,'cfr-422-B-20261027','422.62','b',27,'MA')+root_groups(sources,'cfr-423-B-20261027','423.38','c',36,'D')
    ab=ab_groups(sources,'cfr-406-20261027','406.27','premium-A')+ab_groups(sources,'cfr-407-20261027','407.23','B')
    sepby={r['id']:r for r in seps};comparisons=[]
    for n,refs in GUIDE_MAP.items():
        gid='cms-2026-enrollment:GUIDE:30.6.'+str(n);u=lookup[gid];bindings=[]
        for ref in refs:
            if ref in sepby:bindings.append({'regulatory_root_id':ref,'complete_root_conditions':sepby[ref]['source_native_conditions'],'source_clause_ids':sepby[ref]['source_clause_ids']})
            else:
                sid,sec=('cfr-422-B-20261027','422.62') if ref=='MA:c' else ('cfr-423-B-20261027','423.38')
                bindings.append({'regulatory_context_id':ref,'complete_section_conditions':lookup[sid+':CFR:'+sec]['text'],'source_clause_ids':[sid+':CFR:'+sec]})
        comparisons.append(dict(id='GUIDE-SEP-'+str(n).zfill(2),section='30.6.'+str(n),
             guide_conditions=u['text'],guide_source_clause_id=gid,regulatory_relationships=bindings,
             source_native_citations=re.findall(r'\b(?:406|407|411|422|423)\.\d+(?:\([A-Za-z0-9]+\))*',u['text']),
             interpretation='Related source routes, not one-to-one legal equivalence. All original nested conditions retained.',
             specific_reconciliation_ids=['RC06'] if n==10 else (['RC07'] if n in [7,8,35] else []),
             citation_warning='Guide catch-all MA citation (b)(26) is stale; actual current catch-all is (b)(27); (b)(26) is exceptional A/B enrollment.' if n==36 else None,
             field_validation='Exact retained guide text and full mapped regulatory roots; current citations reconciled; no automatic personal permission inferred',qualified_review=None))
    quantities=[]
    for i,t,value,unit,clause,pattern in QUANTITIES:
        text=lookup[clause]['text'];m=re.search(pattern,text,re.I)
        if not m:raise ValueError('No quantity support '+i+' '+pattern)
        quantities.append(dict(id=i,title=t,value=value,unit=unit,source_clause_ids=[clause],source_pattern=pattern,
             source_quote=text[max(0,m.start()-130):min(len(text),m.end()+180)],
             validation='typed_observation_compared_to_primary_source_and_exact_text_assertion',personal_determination_enabled=False))
    clocks=[dict(id=i,rule_id=rule,clock=clock,modeled_fields=fields,required_conditions=conditions,
            source_clause_ids=next(r['source_clause_ids'] for r in rules if r['id']==rule),
            personal_determination_enabled=False) for i,rule,clock,fields,conditions in CLOCKS]
    reconciliations=[dict(id=i,title=t,rule_id=rule,status=status,disposition=text,source_clause_ids=ids,
         source_conditions=[dict(source_clause_id=k,text=lookup[k]['text']) for k in ids],actor='AI research comparison',qualified_review=None) for i,t,rule,status,text,ids in RECONCILIATIONS]
    annual=[]
    for i,year in [('AEP-for-2026',2026),('AEP-fall-2026-for-2027',2027)]:
        annual.append(dict(id=i,election_start=f'{year-1}-10-15',election_end_inclusive=f'{year-1}-12-07',coverage_start=f'{year}-01-01',
             coverage_year=year,plan_inventory_in_this_reference=year==2026,
             annual_penalty_base_available_in_this_reference=year==2026,source_clause_ids=['cms-2026-enrollment:GUIDE:30.3']))
    annual += [dict(id='GEP-2026',election_start='2026-01-01',election_end_inclusive='2026-03-31',coverage_start='first_day_month_after_enrollment',source_clause_ids=['cfr-407-20261027:CFR:407.15','cfr-407-20261027:CFR:407.25']),
               dict(id='MA-OEP-2026',election_start='2026-01-01',election_end_inclusive='2026-03-31',coverage_start='next_month_if_eligible',source_clause_ids=['cms-2026-enrollment:GUIDE:30.4'],already_MA_required=True,max_elections=1)]
    boundary=[dict(id='L01',reuse='Existing accepted published federal annual premium amounts; no copied personal totals or new acceptance.',path='docs/data/l01-national-2026/published-reference-r1/README.md'),
              dict(id='L11',reuse='Medigap buying rights remain a separate exact-case gate. L13 SEP never grants a Medigap right by implication.',path='docs/data/l11-medigap-rights-2026-10-28/build-r2/manifest.json'),
              dict(id='L12',reuse='Actual LIS/buy-in/Medicaid status and periods required. L12 unresolved state choices and review are preserved, not decided by L13.',path='docs/data/l12-help-with-costs-2026-10-28/build-r2/manifest.json'),
              dict(id='UI',reuse='Existing readiness conversation is reported information; this research package changes no UI, profile, ranking or recommendation gate.',path='docs/product/READINESS_SOURCES.md')]
    l01=ROOT/'docs/data/l01-national-2026/published-reference-r1'
    boundary[0]['exact_annual_cost_records']=[r for r in load(l01/'costs.json') if r['id'] in ['a_premium_full','a_premium_reduced','b_premium']]
    assert len(boundary[0]['exact_annual_cost_records'])==3
    boundary[0]['published_reference_manifest_sha256']='16578a342c13755e0cfd29417af4228bba691ee36fd55e81c3b346d6db9ddfc1'
    assert sha(l01/'manifest.json')==boundary[0]['published_reference_manifest_sha256']
    boundary[0]['pinned_reference_inputs']={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in [l01/n for n in ['manifest.json','costs.json','observations.json','sources.json','RELEASE.json','review/owner-decision-2026-10-25.json']]}
    boundary[0]['L13_acceptance_inherited']=False
    extra_context=[dict(id=key,regulatory_root_id=key,source_native_conditions=sepby[key]['source_native_conditions'],
        source_clause_ids=ids,disposition=disposition) for key,ids,disposition in [
        ('MA:b:9',['cfr-422-B-20261027:CFR:422.62'],'Historical ESRD retroactive SEP ended December 31, 2020; retained, not active 2026'),
        ('MA:b:22',['cms-2026-enrollment:GUIDE:30.1'],'Additional Part D IEP coordinating MA SEP, covered outside 30.6 guidance headings'),
        ('D:c:26',['cms-2026-enrollment:GUIDE:30.4'],'MA OEP coordinating Part D SEP, covered outside 30.6 guidance headings')]]
    summary=dict(schema='l13-published-reference/1',reference_id='L13-PUBLISHED-COLLIER-2026-research-r1',
        scope='Published 2026 federal enrollment, penalty and coordination reference for Collier MVP; research-only synthetic arithmetic, no personal rule engine.',
        reference_year=2026,legal_snapshot='2026-10-27',retrieval_date='2026-10-28',
        retained_sources=len(sources),reused_sources=len(load(BASE/'reuse-inputs.json')),new_sources=len(sources)-len(load(BASE/'reuse-inputs.json')),
        physical_PDF_pages=sum(x.get('pdf_pages',0) for x in sources.values()),source_units=len(units),rule_families=len(rules),
        MA_regulatory_SEP_roots=27,D_regulatory_SEP_roots=36,AB_exceptional_roots=len(ab),CMS_guidance_SEP_sections=len(comparisons),
        typed_quantity_observations=len(quantities),clock_definitions=len(clocks),source_reconciliations=len(reconciliations),
        known_published_exact_date_hold=['RC06'],counts_are_not_distinct_verified_personal_rights=True,
        full_l13_complete=False,qualified_R18_review=None,exact_reference_acceptance=None,
        consumer_eligibility_deadlines_penalty_api_enabled=False,recommendations_enabled=False,UI_or_deployment_changes=False)
    data={'sources.json':sources,'source-clause-ledger.json':units,'rules.json':rules,'regulatory-SEP-inventory.json':seps,
          'AB-exceptional-SEP-inventory.json':ab,'CMS-SEP-comparisons.json':comparisons,'additional-regulatory-context.json':extra_context,'quantities.json':quantities,'clocks.json':clocks,
          'reconciliations.json':reconciliations,'annual-windows.json':annual,'layer-boundaries.json':boundary,'gaps.json':GAPS,'summary.json':summary,
          'before-after.json':dict(before=dict(normalized_L13_reference_packages=0,prior_sources_reused=summary['reused_sources']),after=summary,
              preserved_parent_manifests={'L11-r2':'30f3e52478b1e35003560eda8b58c65e14325fab8591a4fae38450c52ccdc1a0','L12-r1':'93fb2cac9e490cb7a6670e1cec0cc192686be064fcba8a1be1e36580173189cd','L12-r2':'566aa6ec0d76a5d9a6291350eeb7c60dc7e35c1d1355a65bf2da429be93375a5'},newly_accepted_fields=0)}
    BUILD.mkdir(exist_ok=True)
    (BUILD/'l13-reference.sqlite').unlink(missing_ok=True)  # Only this builder's unsealed candidate database.
    for name,obj in data.items():write(BUILD/name,obj)
    with closing(sqlite3.connect(BUILD/'l13-reference.sqlite')) as db:
        db.execute('CREATE TABLE datasets(name TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        db.execute('CREATE TABLE records(dataset TEXT,id TEXT,payload TEXT NOT NULL,PRIMARY KEY(dataset,id))')
        for name,obj in data.items():
            db.execute('INSERT INTO datasets VALUES (?,?)',(name,json.dumps(obj,sort_keys=True)))
            if isinstance(obj,list):
                for n,r in enumerate(obj):db.execute('INSERT INTO records VALUES (?,?,?)',(name,str(r.get('id',n)),json.dumps(r,sort_keys=True)))
        db.commit()
    print(json.dumps(summary,indent=2))
if __name__=='__main__':build()
