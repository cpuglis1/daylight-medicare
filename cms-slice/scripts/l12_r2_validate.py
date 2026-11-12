"""Raw-evidence and full parent/current field validation for additive L12 r2."""
from contextlib import closing
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from l12_validate import check,dec,norm,load,digest
from l12_r2_build import BASE,ROOT,PARENT,BUILD,PARENT_HASH,parent_data

def qmb_month_options(requirements_met,decision):
    """Synthetic federal alternatives; intentionally does not choose Florida's."""
    if requirements_met is None or decision is None:return None
    a,b=map(date.fromisoformat,[requirements_met,decision])
    if a>b:raise ValueError('Requirements cannot be met after the decision in this example')
    def following(d):return date(d.year+(d.month==12),1 if d.month==12 else d.month+1,1).isoformat()
    return {'requirements_month_option':following(a),'decision_month_option':following(b),'Florida_selected_option':None}

def synthetic_supported_relative(related,resident,support_fraction):
    if related is None or resident is None or support_fraction is None:return None
    return bool(related and resident and Decimal(support_fraction)>=Decimal('.5'))

def validate_data(data,parent):
    s=data['summary.json'];check(s['reference_id']=='L12-PUBLISHED-FL-2026-research-r2' and s['parent_manifest_sha256']==PARENT_HASH,'Exact r2 identity/parent')
    for k in ['consumer_release_enabled','personal_applicability_enabled','full_l12_complete']:check(s[k] is False,'Release or full completion invented')
    for k in ['qualified_R17_review','human_acceptance']:check(s[k] is None,'Review/acceptance invented')
    check(s['Florida_QMB_general_next_month_rule_confirmed'] is True and s['Florida_QMB_state_month_election_confirmed'] is False,'QMB baseline/election must remain distinct')
    check(s['historical_published_transition_gap_closed'] is True,'Published historical gap status')
    units={u['id']:u for u in data['source-clause-ledger.json']};oldunits={u['id']:u for u in parent['source-clause-ledger.json']}
    check(len(units)==len(data['source-clause-ledger.json']) and all(units.get(k)==r for k,r in oldunits.items()),'All parent source units preserved exactly')
    oldrules={r['id']:r for r in parent['rules.json']};rules={r['id']:r for r in data['rules.json']}
    changes={r['id']:r for r in data['rule-changes-r2.json']};check(set(changes)=={'R06','R17','R19','R28','R30'},'Explicit changed-rule denominator')
    check(set(rules)==set(oldrules),'No parent rule omission or silent denominator change')
    for rid,r in rules.items():
        if rid in changes:
            check(changes[rid]['before']==oldrules[rid] and changes[rid]['after']==r,'Exact before/after rule evidence')
            check(set(r['source_clause_ids'])>=set(oldrules[rid]['source_clause_ids']),'Old contrary evidence removed')
        else:check(r==oldrules[rid],'Unlisted rule change '+rid)
        check(r['source_conditions']==[{'source_clause_id':i,'text':units[i]['text']} for i in r['source_clause_ids']],'Complete conditions '+rid)
        check(r['qualified_review'] is None and r['human_acceptance'] is None and r['consumer_release_enabled'] is False,'Rule review scope')
    # All unchanged parent datasets remain verbatim. Changed tables retain all
    # fields, with only declared additional provenance; original copies are also
    # compared in full in SQLite parent_datasets/parent_records below.
    changed={'sources.json','source-clause-ledger.json','rules.json','programs.json','florida-msp-lis-tables.json','florida-medicaid-standards.json','gaps.json','before-after.json','summary.json'}
    for name,obj in parent.items():
        if name not in changed:check(data[name]==obj,'Unexpected inherited dataset change '+name)
    for name,added in [('florida-msp-lis-tables.json','dcf-poverty-2026-r2:PAGE:7'),('florida-medicaid-standards.json','dcf-spousal-2026-r2:PAGE:3')]:
        check(len(data[name])==len(parent[name]),'Inherited table row omission')
        for new,old in zip(data[name],parent[name]):
            cleaned=deepcopy(new);cleaned['source_clause_ids'].remove(added)
            check(cleaned==old,'Unlisted parent table field change')
    check(len(data['programs.json'])==12,'Program denominator')
    for p,old in zip(data['programs.json'],parent['programs.json']):
        cleaned=deepcopy(p);cleaned['source_clause_ids']=old['source_clause_ids'];check(cleaned==old,'Program nonlineage field changed')
        check(p['source_clause_ids']==sorted({i for r in p['rule_ids'] for i in rules[r]['source_clause_ids']}),'Program exact rule lineage')
    for obj in data.values():
        if not isinstance(obj,list):continue
        for row in obj:
            for k in row.get('source_clause_ids',[]):check(k in units,'Dangling source '+k)
    sources=data['sources.json'];page=(ROOT/sources['dcf-poverty-2026-r2']['text_path']).read_text().split('\f')
    check(all(sources.get(k)==r for k,r in parent['sources.json'].items()),'Parent source registry fields preserved')
    table=page[6];parts={'april':table.split('Financial Standards Effective April 2026')[1].split('Interim Effective January 2026')[0],
                        'interim_january':table.split('Interim Effective January 2026')[1].split('2026 Medicare Premiums')[0]}
    a91=data['dated-A91-comparisons-r2.json'];check(len(a91)==22,'All dated A91 comparisons')
    for row in a91:
        old=next(x for x in parent['florida-msp-lis-tables.json'] if x['id']==row['parent_record_id'])
        line=next(x for x in parts[old['period']].splitlines() if x.split() and x.split()[0]==old['family_size_source'])
        nums=re.findall(r'\+?\$[\d,]+',line)
        check(row['source_money_tokens']==nums==old['source_money_tokens'] and row['printed_numeric_cells']==len(nums),'All dated A91 numeric cells')
        check(row['source_quote']==norm(line) and row['status']=='all_printed_numeric_cells_agree','A91 exact locator/status')
    check(sum(x['printed_numeric_cells'] for x in a91)==96,'96 numeric cells including increments')
    april=data['historical-April-medicaid-standards.json'];check(len(april)==44,'All April A9 observations')
    printed={dec(x) for x in re.findall(r'\$\s*([\d,]+(?:\.\d+)?)',page[5])}
    for r,old in zip(april,parent['florida-medicaid-standards.json']):
        check(r['id']=='APR-'+old['id'] and r['reference_table_edition']=='April 2026','April observation identity/edition')
        check(r['source_clause_ids']==['dcf-poverty-2026-r2:PAGE:6'] and dec(r['value']) in printed,'April printed evidence')
        for k in ['program_context','field','unit','personal_calculation_enabled']:check(r[k]==old[k],'April field qualification '+k)
        check(r['value']==({'A938':'2644','A940':'794'}.get(old['id'],old['value'])),'April vs July field mapping')
        if old['id'] in ['A938','A940']:check(r['effective_start']=='2025-07-01' and r['effective_end_exclusive']=='2026-07-01','Explicit previous period')
        else:check(r['effective_start']==old['effective_start'] and r['effective_end_exclusive']==old['effective_end_exclusive'] and r['basis']==old['basis'],'April preserved basis/date')
    check('February 24, 2026' in page[0] and 'April 1, 2026' in page[0] and 'April and' in page[0] and 'pending applications and open cases' in norm(page[0]),'Dated April instruction')
    check('$2,410 monthly, Maximum $9,730 per calendar year' in page[5],'Dated corrected student row')
    spousal=(ROOT/sources['dcf-spousal-2026-r2']['text_path']).read_text().split('\f')
    july_numbers={dec(x) for x in re.findall(r'\$\s*([\d,]+(?:\.\d+)?)',spousal[2])}
    for r in data['florida-medicaid-standards.json']:check(dec(r['value']) in july_numbers,'All current A9 observations in dated July attachment')
    check('May 11, 2026' in spousal[0] and 'July 1, 2026' in spousal[0] and 'supersedes all other prior transmittals' in spousal[0],'Dated July supersession')
    transitions=data['spousal-transitions-r2.json'];check(len(transitions)==4,'All previous/new spousal rows')
    for r in transitions:
        expected={'MMMNA-previous':'2644','MMMNA-updated':'2705','excess_shelter-previous':'794','excess_shelter-updated':'812'}
        check(r['value']==expected[r['id']] and r['unit']=='USD/month','Spousal printed values/units')
        old=r['id'].endswith('previous');check((r['effective_start'],r['effective_end_exclusive'])==(('2025-07-01','2026-07-01') if old else ('2026-07-01','2027-01-01')),'Spousal effective boundaries')
    check('$4,067' in spousal[0] and 'same through December 31, 2026' in spousal[0],'Maximum allowance distinct from minimum')
    examples=data['MSP-family-examples-r2.json'];check(len(examples)==3,'Three official family examples')
    for r,expected in zip(examples,[(1,2,'individual'),(1,2,'individual'),(2,3,'couple')]):
        check(tuple(r[k] for k in ['eligible_applicants','income_family_size','resource_limit_basis'])==expected,'Family size/resource basis')
        check(r['dependent_income_and_resources_counted'] is False and r['conditions']==['related_by_blood_marriage_or_adoption','living_in_same_household','at_least_one_half_support'],'Dependent conditions/resources')
    family=units['dcf-msp-filing-unit-r2:PAGE:2']['text']
    for phrase in ['at least one half','income and assets of the dependent SFU member(s) are not counted','individual limit','couple limit']:check(phrase in family,'Official family qualification '+phrase)
    for rid,phrases in {'R06':['long-term-care','not doubled'], 'R19':['LIS-aligned','not counted','resource ceilings','same-sex'],
                        'R28':['not a located standalone erratum','$2,644','$2,705'], 'R30':['No retained Florida instruction','retroactive processing','SLMB/QI']}.items():
        for phrase in phrases:check(phrase in rules[rid]['meaning'],'Lost reference qualification '+rid)
    comps=data['reconciliations-r2.json'];check({x['id'] for x in comps}=={f'C{i:02}' for i in range(1,11)},'Comparison accounting')
    for c in comps:check(c['source_conditions']==[{'source_clause_id':i,'text':units[i]['text']} for i in c['source_clause_ids']] and c['qualified_review'] is None,'Full comparison conditions/review')
    questions=data['review-questions-r2.json'];check({q['id'] for q in questions}=={'Q01','Q02','Q03','Q04','Q05'},'Exact remaining questions')
    for q in questions:check(q['qualified_review'] is None and q['consumer_release_enabled'] is False,'Question review gate')
    check(data['gaps.json'][0]['status']=='published_history_source_gap_closed' and data['parent-gaps.json']==parent['gaps.json'],'Historical closure with parent gap preserved')
    check(sources['dcf-cola-2026-later-r2']['sha256']==sources['dcf-cola-2026-archive']['sha256'],'Later archive COLA copy is byte-identical, not a correction')
    check(s['source_units']==len(units) and s['source_registry_entries']==len(sources) and s['retained_sources']==sum(x['status']=='retained' for x in sources.values()),'Summary source accounting')
    event=data['access-events-r2.json'][0];check(event['http_status']==403 and event['host_stop_respected'] is True and event['retry_count']==0 and event['retained_as_source_evidence'] is False,'Access stop honesty')
    return {'A91_comparison_rows':22,'A91_numeric_cells':96,'April_A9_observations':44,'source_comparisons':10,'changed_rule_ids':sorted(changes),'remaining_review_questions':5,'Florida_election_verified':False}

def validate(write_result=True):
    from l12_validate import validate as validate_parent
    validate_parent(PARENT,write_result=False)
    m=load(PARENT/'manifest.json');check(digest(PARENT/'manifest.json')==PARENT_HASH,'Parent manifest fingerprint')
    for p,f in m['files'].items():check(digest(ROOT/p)==f['sha256'] and (ROOT/p).stat().st_size==f['bytes'],'Parent sealed dependency changed '+p)
    parent=parent_data()
    with closing(sqlite3.connect('file:'+str(BUILD/'l12-reference.sqlite')+'?mode=ro',uri=True)) as db:
        data={name:load(BUILD/name) for name, in db.execute('SELECT name FROM datasets')}
        totals={}
        for prefix,expected in [('',data),('parent_',parent)]:
            datasets={n:json.loads(p) for n,p in db.execute(f'SELECT name,payload FROM {prefix}datasets')};check(datasets==expected,'All SQLite dataset fields '+prefix)
            records={(n,i):json.loads(p) for n,i,p in db.execute(f'SELECT dataset,id,payload FROM {prefix}records')}
            wanted={(n,str(r.get('id',i))):r for n,obj in expected.items() if isinstance(obj,list) for i,r in enumerate(obj)}
            check(records==wanted,'All SQLite record fields '+prefix);totals[prefix+'records']=len(records)
        check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Database integrity')
    extra=load(BASE/'acquisition-r2/extraction-index.json');fresh={}
    for sid,s in extra.items():
        raw=ROOT/s['path'];check(digest(raw)==s['sha256'] and raw.stat().st_size==s['bytes'],'New raw source integrity')
        if s['status']!='retained':continue
        kind=s['extraction_kind']
        if kind=='native_pdf_text':text=subprocess.run(['pdftotext','-layout',str(raw),'-'],check=True,capture_output=True).stdout.decode();check(text.count('\f')==s['pdf_pages'],'Fresh PDF pages')
        elif kind=='ecfr_xml_sections':
            sections=[{'section':n.get('N'),'text':norm(' '.join(n.itertext()))} for n in ET.parse(raw).iter('DIV8')]
            check({'sections':sections}==load(ROOT/s['structured_text_path']),'Full fresh CFR sections');text='\n'.join(r['text'] for r in sections)+'\n'
        elif kind=='public_json':text=json.dumps(load(raw),indent=2,sort_keys=True)+'\n'
        else:
            from l12_sources import PublicHTML
            p=PublicHTML();p.feed(raw.read_text(errors='replace'));check(p.result()==load(ROOT/s['structured_text_path']),'Fresh HTML full content');text='\n'.join(p.result()['lines'])+'\n'
        check(text==(ROOT/s['text_path']).read_text(),'Exact fresh extraction '+sid);fresh[sid]=text
    for u in data['source-clause-ledger.json']:
        if u['source_id'] not in extra:continue
        sid=u['source_id'];loc=u['locator']
        if 'pdf_page' in loc:expected=norm(fresh[sid].split('\f')[loc['pdf_page']-1])
        elif 'section' in loc:expected=next(r['text'] for r in load(ROOT/extra[sid]['structured_text_path'])['sections'] if r['section']==loc['section'])
        else:expected=norm(fresh[sid])
        check(u['text']==expected,'Exact new evidence unit '+u['id'])
    result={'passed':True,'parent_manifest_unchanged':True,'all_parent_dependencies_verified':len(m['files']),
            'all_parent_and_current_SQLite_fields_match':True,**totals,'new_retained_sources':sum(s['status']=='retained' for s in extra.values()),
            'new_PDF_pages_freshly_checked':sum(s.get('pdf_pages',0) for s in extra.values()),**validate_data(data,parent),'qualified_R17_review':None,'human_acceptance':None}
    if write_result:
        check(not (BUILD/'manifest.json').exists(),'Sealed r2 cannot be mutated');(BUILD/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');a=p.parse_args();print(json.dumps(validate(not a.verify_only),indent=2))
