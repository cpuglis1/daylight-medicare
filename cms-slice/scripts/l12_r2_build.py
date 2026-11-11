"""Build additive L12 r2; preserve the exact parent in JSON/SQLite lineage."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import sqlite3
from l12_build import load,write,norm,sha
from l12_r2_catalog import UPDATES,COMPARISONS,QUESTIONS

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l12-help-with-costs-2026-10-28'
PARENT=BASE/'build-r1';BUILD=BASE/'build-r2';ACQ=BASE/'acquisition-r2'
PARENT_HASH='93fb2cac9e490cb7a6670e1cec0cc192686be064fcba8a1be1e36580173189cd'

def parent_data():
    assert sha(PARENT/'manifest.json')==PARENT_HASH
    with closing(sqlite3.connect('file:'+str(PARENT/'l12-reference.sqlite')+'?mode=ro',uri=True)) as db:
        return {name:load(PARENT/name) for name, in db.execute('SELECT name FROM datasets')}

def new_units(sources):
    result=[]
    for sid,s in sources.items():
        if s['status']!='retained':continue
        text=(ROOT/s['text_path']).read_text()
        result.append({'id':sid+':ALL','source_id':sid,'text':norm(text),'locator':{'method':s['extraction_kind']},'disposition':'retained_source_context'})
        if s['extraction_kind']=='native_pdf_text':
            result += [{'id':sid+f':PAGE:{n}','source_id':sid,'text':norm(p),'locator':{'pdf_page':n,'method':'native_pdf'},'disposition':'retained_source_context'} for n,p in enumerate(text.split('\f')[:-1],1)]
        elif s['extraction_kind']=='ecfr_xml_sections':
            result += [{'id':sid+':CFR:'+r['section'],'source_id':sid,'text':r['text'],'locator':{'section':r['section'],'edition':'2026-10-27'},'disposition':'retained_source_context'} for r in load(ROOT/s['structured_text_path'])['sections']]
    return result

def table_comparisons(parent,sources):
    text=(ROOT/sources['dcf-poverty-2026-r2']['text_path']).read_text().split('\f')[6]
    chunks={'april':text.split('Financial Standards Effective April 2026')[1].split('Interim Effective January 2026')[0],
            'interim_january':text.split('Interim Effective January 2026')[1].split('2026 Medicare Premiums')[0]}
    records=[]
    for old in parent['florida-msp-lis-tables.json']:
        line=next(l for l in chunks[old['period']].splitlines() if l.split() and l.split()[0]==old['family_size_source'])
        tokens=re.findall(r'\+?\$[\d,]+',line)
        if tokens!=old['source_money_tokens']:raise ValueError('Changed A91 printed value '+old['id'])
        records.append({'id':'R2-'+old['id'],'parent_record_id':old['id'],'period':old['period'],
                        'source_money_tokens':tokens,'printed_numeric_cells':len(tokens),'status':'all_printed_numeric_cells_agree',
                        'source_clause_ids':old['source_clause_ids']+['dcf-poverty-2026-r2:PAGE:7'],'source_quote':norm(line)})
    return records

def build():
    if BUILD.exists():raise ValueError('Build exists; use a new candidate/revision')
    parent=parent_data();data=deepcopy(parent);extra=load(ACQ/'extraction-index.json')
    units=new_units(extra);data['sources.json'].update(extra);data['source-clause-ledger.json']+=units
    lookup={r['id']:r for r in data['source-clause-ledger.json']}
    changed=[]
    for r in data['rules.json']:
        if r['id'] not in UPDATES:continue
        previous=deepcopy(r);meaning,ids=UPDATES[r['id']];r['meaning']=meaning
        r['source_clause_ids']=list(dict.fromkeys(r['source_clause_ids']+ids))
        r['source_conditions']=[{'source_clause_id':i,'text':lookup[i]['text']} for i in r['source_clause_ids']]
        r['revision']=2;r['supersedes_meaning_in']='L12-PUBLISHED-FL-2026-research-r1'
        changed.append({'id':r['id'],'before':previous,'after':deepcopy(r),'new_acceptance':None})
    byrule={r['id']:r for r in data['rules.json']}
    for p in data['programs.json']:p['source_clause_ids']=sorted({i for rid in p['rule_ids'] for i in byrule[rid]['source_clause_ids']})
    for row in data['florida-msp-lis-tables.json']:row['source_clause_ids'].append('dcf-poverty-2026-r2:PAGE:7')
    for row in data['florida-medicaid-standards.json']:row['source_clause_ids'].append('dcf-spousal-2026-r2:PAGE:3')
    april=[]
    for old in parent['florida-medicaid-standards.json']:
        r=deepcopy(old);r['id']='APR-'+old['id'];r['reference_table_edition']='April 2026'
        r['source_clause_ids']=['dcf-poverty-2026-r2:PAGE:6'];r['transcription_method']='native_PDF_plus_full_page_visual_comparison'
        if old['id'] in ['A938','A940']:
            r['value']='2644' if old['id']=='A938' else '794';r['effective_start']='2025-07-01';r['effective_end_exclusive']='2026-07-01'
            r['basis']='previous spousal standard explicitly confirmed by May 11 notice for months before July 1, 2026'
        april.append(r)
    comparisons=[{'id':i,'title':t,'status':s,'affected_rule_ids':rids,'meaning':m,'source_clause_ids':ids,
                  'source_conditions':[{'source_clause_id':k,'text':lookup[k]['text']} for k in ids],
                  'actor':'AI source comparison; qualified R17 not asserted','qualified_review':None} for i,t,s,rids,m,ids in COMPARISONS]
    questions=[{'id':i,'title':t,'affected_records':ids,'question':q,'needed':n,'qualified_review':None,'consumer_release_enabled':False} for i,t,ids,q,n in QUESTIONS]
    transitions=[]
    for name,old,new in [('MMMNA','2644','2705'),('excess_shelter','794','812')]:
        for phase,value,start,end in [('previous',old,'2025-07-01','2026-07-01'),('updated',new,'2026-07-01','2027-01-01')]:
            transitions.append({'id':name+'-'+phase,'standard':name,'value':value,'unit':'USD/month',
                                'effective_start':start,'effective_end_exclusive':end,
                                'end_basis':'explicit prior period' if phase=='previous' else 'selected 2026 reference-year boundary, not actual expiration',
                                'source_clause_ids':['dcf-spousal-2026-r2:PAGE:1']})
    examples=[{'id':'FAM-'+str(i),'source_example':label,'eligible_applicants':eligible,'income_family_size':family,
               'resource_limit_basis':basis,'dependent_income_and_resources_counted':False,
               'conditions':['related_by_blood_marriage_or_adoption','living_in_same_household','at_least_one_half_support'],
               'source_clause_ids':['dcf-msp-filing-unit-r2:PAGE:2']} for i,label,eligible,family,basis in [
                   (1,'Individual supports co-resident sibling',1,2,'individual'),(2,'Parent supports co-resident child',1,2,'individual'),(3,'Couple supports co-resident grandchild',2,3,'couple')]]
    # Preserve originals rather than rewriting old gap history.
    data['parent-gaps.json']=deepcopy(parent['gaps.json'])
    data['gaps.json']=[{'id':'G01','status':'published_history_source_gap_closed','meaning':'Dated April transition/corrected attachment and July prior/new standards acquired. No separate student erratum or personal reprocessing date is claimed.','source_clause_ids':['dcf-poverty-2026-r2:PAGE:1','dcf-poverty-2026-r2:PAGE:6','dcf-spousal-2026-r2:PAGE:1'],'independent_review':None,'consumer_release_enabled':False}]+questions
    data.update({'rule-changes-r2.json':changed,'reconciliations-r2.json':comparisons,'review-questions-r2.json':questions,
                 'historical-April-medicaid-standards.json':april,'dated-A91-comparisons-r2.json':table_comparisons(parent,extra),
                 'spousal-transitions-r2.json':transitions,'MSP-family-examples-r2.json':examples,
                 'access-events-r2.json':[{'id':'AHCA-WEB-403','url':'https://ahca.myflorida.com/medicaid/medicaid-state-plan-attachments.html','observed_by':'web.open','http_status':403,'host_stop_respected':True,'retry_count':0,'retained_as_source_evidence':False,'consequence':'No direct retained state-plan election paragraph; discovery snippets do not close the election.'}]})
    for c in comparisons:
        for k in c['source_clause_ids']:
            if k not in lookup:raise ValueError('Missing source '+k)
    counts={**parent['before-after.json']['after'],'source_units':len(data['source-clause-ledger.json']),
            'source_registry_entries':len(data['sources.json']),'retained_sources':sum(s['status']=='retained' for s in data['sources.json'].values()),
            'retained_PDF_pages':sum(s.get('pdf_pages',0) for s in data['sources.json'].values()),
            'r2_reconciliations':len(comparisons),'r2_changed_rules':len(changed),'historical_April_observations':44,'r2_A91_comparisons':22,'remaining_review_questions':len(questions)}
    data['before-after.json']={'before':parent['summary.json'],'after':counts,'parent_data_preserved_verbatim_in_SQLite':True,
        'parent_rules':34,'current_rules':34,'changed_rule_ids':[r['id'] for r in changed],'removed_parent_records':0,
        'newly_accepted_fields':0,'counts_are_not_distinct_verified_facts':True}
    data['summary.json']={**parent['summary.json'],**counts,'schema':'l12-published-reference/2','reference_id':'L12-PUBLISHED-FL-2026-research-r2',
        'parent_manifest_sha256':PARENT_HASH,'full_l12_complete':False,'Florida_QMB_general_next_month_rule_confirmed':True,
        'Florida_QMB_state_month_election_confirmed':False,'historical_published_transition_gap_closed':True,
        'scope':'Published 2026 federal/Florida assistance reference with dated historical corrections and exact remaining questions; no personal adjudication.'}
    BUILD.mkdir();(BUILD/'code').mkdir()
    for name,obj in data.items():write(BUILD/name,obj)
    with closing(sqlite3.connect(BUILD/'l12-reference.sqlite')) as db:
        for prefix,payloads in [('',data),('parent_',parent)]:
            db.execute(f'CREATE TABLE {prefix}datasets (name TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            db.execute(f'CREATE TABLE {prefix}records (dataset TEXT,id TEXT,payload TEXT,PRIMARY KEY(dataset,id))')
            for name,obj in payloads.items():
                db.execute(f'INSERT INTO {prefix}datasets VALUES (?,?)',(name,json.dumps(obj,sort_keys=True)))
                if isinstance(obj,list):
                    for i,r in enumerate(obj):db.execute(f'INSERT INTO {prefix}records VALUES (?,?,?)',(name,str(r.get('id',i)),json.dumps(r,sort_keys=True)))
        db.commit()
    for p in ROOT.joinpath('cms-slice/scripts').glob('l12_r2_*.py'):shutil.copyfile(p,BUILD/'code'/p.name)
    shutil.copyfile(ROOT/'cms-slice/tests/test_l12_r2_reference.py',BUILD/'code/test_l12_r2_reference.py')
    print(json.dumps(data['summary.json'],indent=2))

if __name__=='__main__':build()
