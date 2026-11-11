"""Build a sealed-ready, source-linked L12 research reference; no user service."""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3

import l12_catalog as catalog

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l12-help-with-costs-2026-10-28'
ACQ=BASE/'acquisition-r1'
BUILD=BASE/'build-r1'


def load(p):return json.loads(Path(p).read_text())
def norm(s):return ' '.join(s.split())
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def money(s):return format(Decimal(s.replace('$','').replace(',','').replace('+','').strip()),'f')


def make_units(sources):
    units=[]
    def add(key,sid,text,locator,role='retained_source_context'):
        units.append({'id':key,'source_id':sid,'text':norm(text),'locator':locator,'disposition':role})
    for sid,s in sources.items():
        if s['status']!='retained':continue
        text=(ROOT/s['text_path']).read_text()
        if s['extraction_kind']=='native_pdf_text':
            add(sid+':ALL',sid,text,{'method':'native_full_pdf_context'})
            for n,p in enumerate(text.split('\f')[:-1],1):
                if sid=='dcf-a9-current':
                    # Retain corrupt native extraction separately; modeled page
                    # evidence uses OCR plus visual transcription, explicitly.
                    add(sid+f':NATIVE:{n}',sid,p,{'pdf_page':n,'method':'native_corrupt_font_mapping'})
                    p=(ROOT/s['ocr_path']).read_text()
                add(sid+f':PAGE:{n}',sid,p,{'pdf_page':n,'method':'OCR_plus_visual_review' if sid=='dcf-a9-current' else 'native_pdf'})
            if sid.startswith('dcf-') and sid.split('-')[-1].isdigit() and len(sid.split('-')[-1]) in (3,4):
                # The last real passage heading wins over its table-of-contents
                # occurrence. Parent/prefix relationships remain inspectable.
                headings=[]
                for m in re.finditer(r'(?m)^(\d{4}\.\d{4}(?:\.\d{2})?)\s+([^\n]+)',text):
                    if '...' not in m[2] and len(m[2].strip())>2:headings.append((m.start(),m[1],m[2]))
                fragments={}
                for i,(start,code,title) in enumerate(headings):
                    end=headings[i+1][0] if i+1<len(headings) else len(text)
                    fragments[code]=(start,text[start:end],title)
                for code,(start,body,title) in fragments.items():
                    add(sid+':SECTION:'+code,sid,body,{'passage':code,'title':norm(title),
                          'pdf_page_start':text[:start].count('\f')+1,'character_start':start,
                          'character_end':start+len(body)})
        elif s['extraction_kind']=='ecfr_xml_sections':
            for row in load(ROOT/s['structured_text_path'])['sections']:
                add(sid+':CFR:'+row['section'],sid,row['text'],{'section':row['section'],'edition':'2026-10-27'})
        elif s['extraction_kind']=='word_textutil':
            add(sid+':ALL',sid,text,{'method':'textutil_document'})
            hits=list(re.finditer(r'(?m)^(65A-1\.\d+)\s+([^\n]+)',text))
            last={m[1]:m.start() for m in hits}
            for i,m in enumerate(hits):
                if m.start()!=last[m[1]]:continue # TOC retained in ALL, not a duplicate operative rule
                end=hits[i+1].start() if i+1<len(hits) else len(text)
                add(sid+':RULE:'+m[1],sid,text[m.start():end],{'rule':m[1],'character_start':m.start(),'character_end':end})
        else:
            data=load(ROOT/s['structured_text_path'])
            add(sid+':ALL',sid,'\n'.join(data['lines']),{'method':'html_visible_lines'})
            for n,line in enumerate(data['lines'],1):add(sid+f':LINE:{n}',sid,line,{'derived_line':n})
            for table in data['tables']:
                for n,row in enumerate(table['rows'],1):
                    add(sid+f':T{table["table_one_based"]}:R{n}',sid,' | '.join(row),
                        {'table':table['table_one_based'],'row':n,'preceding_heading':table['preceding_heading'],'cells':row})
    if len({u['id'] for u in units})!=len(units):raise ValueError('Duplicate source unit')
    return units


def a91_tables(sources):
    text=(ROOT/sources['dcf-a91-reused']['text_path']).read_text()
    chunks=[('april','2026-04-01','2027-01-01',text.split('Financial Standards Effective April 2026',1)[1].split('Interim Effective January 2026',1)[0]),
            ('interim_january','2026-01-01','2026-04-01',text.split('Interim Effective January 2026',1)[1].split('2026 Medicare Premiums',1)[0])]
    rows=[]
    for period,start,end,chunk in chunks:
        for line in chunk.splitlines():
            m=re.match(r'\s*(Individual|Couple/2|[3-9]|10|Additional)\s+((?:[+]?[\$][\d,]+\s*)+)$',line)
            if not m:continue
            raw=re.findall(r'\+?\$[\d,]+',m[2]);values=[money(v) for v in raw];family=m[1]
            if family in ['Individual','Couple/2']:
                if len(values)!=6:raise ValueError('A-9.1 two-adult row shape')
                named=dict(zip(['QMB','SLMB','QI','MSP_resources','LIS','LIS_base_resources'],values))
            else:
                if len(values)!=4:raise ValueError('A-9.1 family row shape')
                named=dict(zip(['QMB','SLMB','QI','LIS'],values));named['MSP_resources']=None;named['LIS_base_resources']=None
            rows.append({'id':f'A91-{period}-{family}','dataset':'DCF_A9_1','family_size_source':family,
                        'family_size':1 if family=='Individual' else 2 if family=='Couple/2' else int(family) if family.isdigit() else None,
                        'row_type':'additional_person_increment' if family=='Additional' else 'published_standard',
                        'period':period,'effective_start':start,'effective_end_exclusive':end,
                        'period_basis':'source January/April header; end bounded by following selected period/year, not individual award expiry',
                        'interpretation_status':'current_published_standard' if period=='april' else 'dated_DCF_interim_2_8_percent_explanation_and_attached_table_reconciled',
                        'fields':{k:{'value':v,'unit':'USD/resources' if 'resources' in k else 'USD/month',
                                     'basis':'source_blank_not_zero' if v is None else 'base_resources_before_burial_exclusion' if k=='LIS_base_resources' else 'countable_income_standard' if 'resources' not in k else 'countable_resources',
                                     'source_status':'blank' if v is None else 'published'} for k,v in named.items()},
                        'source_clause_ids':['dcf-a91-reused:PAGE:1'],'source_quote':norm(line),'source_money_tokens':raw})
    if len(rows)!=22:raise ValueError('A-9.1 complete 2x11 row denominator')
    return rows


def ssa_tables(sources):
    result=[]
    sid='ssa-0603001020';data=load(ROOT/sources[sid]['structured_text_path'])
    table=data['tables'][0]
    if '2026' not in table['preceding_heading'] or table['rows'][1][1]!='$15,960.00':raise ValueError('Wrong year/geography FPL table')
    for rowno,row in enumerate(table['rows'][1:],2):
        result.append({'id':'SSA-FPL-'+row[0],'family_size_source':row[0], 'reference_year':2026,
                       'geography':'48_contiguous_states_and_DC_including_Florida', 'unit':'USD/year_countable_income',
                       'values':dict(zip(['100','135','140','145','150'],[money(x) for x in row[1:]])),
                       'usage':'FPL standards; 135/140/145 bands do not create current partial subsidy levels',
                       'effective_basis':'SSA published 2026 FPL; apply SSA applicable-year/filing/redetermination policy, not Florida April implementation date',
                       'source_clause_ids':[sid+f':T1:R{rowno}'],'source_cells':row})
    msp=[];sid='ssa-0600815023';data=load(ROOT/sources[sid]['structured_text_path'])
    for number,program in enumerate(['QMB','SLMB','QI','QDWI'],1):
        table=data['tables'][number-1]
        for i,row in enumerate(table['rows'],1):
            if row[0].startswith('All States') or row[0]=='Resource Limits':
                msp.append({'id':f'FED-{program}-'+('income' if row[0].startswith('All') else 'resources'),
                            'program':program,'reference_year':2026,
                            'basis':'gross_summary_including_20_and_earned_disregards' if program=='QDWI' and row[0].startswith('All') else 'gross_summary_including_20_disregard' if row[0].startswith('All') else 'federal_resource_floor',
                            'individual':money(row[1]),'couple':money(row[2]),
                            'unit':'USD/month' if row[0].startswith('All') else 'USD/resources',
                            'source_clause_ids':[sid+f':T{number}:R{i}'],'source_cells':row})
    return result,msp


def make_numeric_tables(sources):
    a9=[{'id':i,'program_context':p,'field':f,'value':v,'unit':u,'effective_start':s,
         'effective_end_exclusive':None,'basis':basis,'reference_table_edition':'July 2026',
         'source_clause_ids':['dcf-a9-current:PAGE:1'],
         'transcription_method':'visual_source_transcription_plus_OCR_crosscheck',
         'personal_calculation_enabled':False} for i,p,f,v,u,s,basis in catalog.A9_ROWS]
    resources=[]
    for who,base,burial in [('individual','16590','1500'),('living_together_married_couple','33100','3000')]:
        resources.append({'id':'LIS-RES-'+who,'reference_year':2026,'household_basis':who,'base_limit':base,
                          'maximum_burial_exclusion':burial,'display_with_full_burial_allowance':str(int(base)+int(burial)),
                          'unit':'USD/resources','effective_start':'2026-01-01','effective_end_exclusive':'2027-01-01',
                          'conditions':'Burial treatment must be established; couple none/one/both cases differ. Do not deduct twice.',
                          'source_clause_ids':['cms-lis-2026:PAGE:1','cms-lis-2026:PAGE:3','ssa-0603030025:ALL','ssa-0603030020:ALL']})
    cost=[]
    categories=[('full_dual_institution_or_qualifying_HCBS','0','0'),('full_dual_income_le_100_FPL','1.60','4.90'),
                ('full_dual_between_100_150_FPL','5.10','12.65'),('MSP_QMB_SLMB_QI_or_SSI_non_full_dual','5.10','12.65'),
                ('applied_non_full_dual_meeting_LIS_conditions','5.10','12.65')]
    for i,(category,generic,brand) in enumerate(categories,1):
        cost.append({'id':f'LIS-COST-{i}','reference_year':2026,'category':category,'deductible_maximum':'0',
                     'generic_copayment_maximum':generic,'brand_copayment_maximum':brand,
                     'annual_out_of_pocket_threshold':'2100','covered_drug_cost_share_above_threshold':'0',
                     'unit':'USD','cost_basis':'published maxima for covered Part D drugs with exact category conditions; not store prices',
                     'effective_start':'2026-01-01','effective_end_exclusive':'2027-01-01',
                     'source_clause_ids':['cms-lis-2026:PAGE:4']})
    return a9,resources,cost


def historical_tables(sources,a9,a91):
    sid='dcf-cola-2026-archive';page=(ROOT/sources[sid]['text_path']).read_text().split('\f')[11]
    chunk=page.split('Interim Effective January 2026')[1].split('Financial Standards April 2025')[0]
    comparisons=[]
    for row in a91:
        if row['period']!='interim_january':continue
        line=next(x for x in chunk.splitlines() if x.split() and x.split()[0]==row['family_size_source'])
        tokens=re.findall(r'\+?\$[\d,]+',line)
        if tokens!=row['source_money_tokens']:raise ValueError('Dated/current January table mismatch')
        comparisons.append({'id':'HIST-'+row['family_size_source'],'record_id':row['id'],
                            'status':'all_printed_numeric_cells_agree','printed_numeric_cells':len(tokens),
                            'source_money_tokens':tokens,'source_clause_ids':['dcf-a91-reused:PAGE:1',sid+':PAGE:12'],
                            'source_quote':norm(line),'source_author':'Florida DCF','hosting_provenance':'original dated DCF memo retained from public Florida Health Justice archive; not a first-party download'})
    changes={'A911':'1182','A912':'1596','A919':'2683','A920':'3624','A926':'1342','A927':'269','A928':'538',
             'A932':'2416','A933':'9460','A938':'2644','A940':'794'}
    historical=[]
    for row in a9:
        r=dict(row);r['id']='JAN-'+row['id'];r['value']=changes.get(row['id'],row['value'])
        r['reference_table_edition']='January 2026';r['source_clause_ids']=[sid+':PAGE:11']
        r['effective_start']=row['effective_start'] if row['effective_start'] in (None,'2026-01-01','2025-04-01') else None
        r['basis']='source-native historical printed observation; edition is not proof of individual effective date'
        r['transcription_method']='native_PDF_table_plus_visual_comparison'
        r['interpretation_status']='historical_source_defect_use_SSA_current_DCF' if row['id'] in ('A932','A933') else 'historical_observation_not_personal_eligibility'
        historical.append(r)
    return historical,comparisons


def build():
    if BUILD.exists():raise ValueError('Build directory exists; use a new candidate/revision')
    BUILD.mkdir();(BUILD/'code').mkdir()
    sources=load(ACQ/'extraction-index.json');units=make_units(sources);byid={u['id']:u for u in units}
    sources['dcf-cola-2026-archive']['source_author']='Florida Department of Children and Families'
    sources['dcf-cola-2026-archive']['hosting_provenance']='Original dated DCF memorandum I-25-12-0013 hosted by Florida Health Justice public archive; not a first-party download.'
    rules=[]
    for rid,fam,title,meaning,selectors in catalog.RULES:
        ids=[]
        for sel in selectors:
            if sel not in byid:raise ValueError('Missing exact evidence selector '+sel)
            ids.append(sel)
        rules.append({'id':rid,'family':fam,'title':title,'meaning':meaning,'reference_year':2026,
                      'reference_date':'2026-10-28','jurisdiction':'federal_and_Florida_as_individually_sourced',
                      'source_clause_ids':ids,'source_conditions':[{'source_clause_id':k,'text':byid[k]['text']} for k in ids],
                      'comparison_actor':'AI source transcription/comparison; qualified R17 pending',
                      'qualified_review':None,'human_acceptance':None,'consumer_release_enabled':False})
    byrule={r['id']:r for r in rules};programs=[]
    for pid,name,benefit,rids in catalog.PROGRAMS:
        programs.append({'id':pid,'name':name,'assistance_summary':benefit,'reference_year':2026,
                         'rule_ids':rids,'source_clause_ids':sorted({s for rid in rids for s in byrule[rid]['source_clause_ids']}),
                         'eligibility_result':'not_determined','personal_applicability_enabled':False})
    a91=a91_tables(sources);fpl,msp=ssa_tables(sources);a9,resources,cost=make_numeric_tables(sources)
    historical,historical_comparisons=historical_tables(sources,a9,a91)
    checks=[]
    for program in ['QMB','SLMB','QI']:
        federal=next(r for r in msp if r['program']==program and 'income' in r['id'])
        for family,field in [('Individual','individual'),('Couple/2','couple')]:
            state=next(r for r in a91 if r['period']=='april' and r['family_size_source']==family)
            checks.append({'id':f'RC-{program}-{field}','comparison':'federal gross summary versus Florida countable standard',
                           'state_record_id':state['id'],'federal_record_id':federal['id'],
                           'state_countable':state['fields'][program]['value'],'general_disregard':'20',
                           'federal_gross_summary':federal[field], 'unit':'USD/month',
                           'status':'matches_after_basis_adjustment' if Decimal(state['fields'][program]['value'])+20==Decimal(federal[field]) else 'unresolved',
                           'source_clause_ids':state['source_clause_ids']+federal['source_clause_ids']+['dcf-2400:SECTION:2440.0322']})
    automatic=[]
    for program,qualifies in [('SSI',True),('full_benefit_Medicaid',True),('QMB',True),('SLMB',True),('QI',True),('QDWI_alone',False)]:
        automatic.append({'id':'DEEM-'+program,'qualifying_status':program,'deems_LIS':qualifies,
                          'conditions':['actual_confirmed_status','Medicare_Part_D_eligible'],
                          'source_clause_ids':['ssa-0603010005:ALL','ecfr-lis-cms-1027:CFR:423.773'],
                          'not_a_personal_determination':True})
    routes=[{'id':'ROUTE-DCF','purpose':'Medicaid/MSP information and official application route','information_url':sources['dcf-help-landing']['url'],
             'application_url':'https://myaccess.myflfamilies.com','action_performed':'public_information_only','source_clause_ids':['dcf-help-landing:ALL']},
            {'id':'ROUTE-SSA','purpose':'Extra Help application and agency process','information_url':sources['ssa-0603010010']['url'],
             'application_url':None,'action_performed':'public_information_only','source_clause_ids':['ssa-0603010010:ALL']},
            {'id':'ROUTE-SHINE','purpose':'Free neutral Florida Medicare counseling','information_url':sources['shine-contact']['url'],
             'phone':'1-800-963-5337','TTY':'1-800-955-8770','action_performed':'public_information_only','source_clause_ids':['shine-contact:ALL']},
            {'id':'ROUTE-COLLIER','purpose':'Current official Collier counseling locations and appointment/member restrictions',
             'information_url':sources['shine-collier']['url'],'action_performed':'public_information_only','source_clause_ids':['shine-collier:ALL']}]
    gaps=[{'id':i,'title':t,'kind':k,'meaning':m,'closure':c,'owner_action_now':'No download or outreach requested; a later named qualified/agency review must be explicit.',
           'independent_review':None,'consumer_release_enabled':False} for i,t,k,m,c in catalog.GAPS]
    # Preserve the complete MSSI coverage-passage census, including paths that
    # cannot simply be offered to a current Medicare beneficiary.
    coverage=[]
    linked={s for r in rules for s in r['source_clause_ids']}
    for u in units:
        if u['id'].startswith('dcf-2000:SECTION:2040.'):
            coverage.append({'id':u['id'],'title':u['locator']['title'],
                             'disposition':'explicitly_linked_reference' if u['id'] in linked else 'retained_context_or_separate_path_conditions_not_adjudicated',
                             'source_clause_id':u['id']})
    for u in units:
        if u['id'] in linked:u['disposition']='linked_modeled_evidence'
    counts={'program_records':len(programs),'source_scoped_rule_records':len(rules),
            'A91_rows':len(a91),'A9_numeric_observations':len(a9),'federal_FPL_rows':len(fpl),
            'federal_MSP_rows':len(msp),'LIS_resource_rows':len(resources),'LIS_cost_sharing_rows':len(cost),
            'automatic_routes':len(automatic),'basis_reconciliations':len(checks),'source_units':len(units),
            'source_registry_entries':len(sources),'retained_sources':sum(s['status']=='retained' for s in sources.values()),
            'retained_PDF_pages':sum(s.get('pdf_pages',0) for s in sources.values()),'coverage_passages':len(coverage),
            'historical_A9_observations':len(historical),'January_cross_publication_comparisons':len(historical_comparisons)}
    data={'sources.json':sources,'source-clause-ledger.json':units,'rules.json':rules,'programs.json':programs,
          'florida-msp-lis-tables.json':a91,'florida-medicaid-standards.json':a9,
          'federal-FPL-2026.json':fpl,'federal-MSP-2026.json':msp,'LIS-resources-2026.json':resources,
          'LIS-cost-sharing-2026.json':cost,'basis-reconciliations.json':checks,'automatic-routes.json':automatic,
          'application-referrals.json':routes,'gaps.json':gaps,'medicaid-coverage-accounting.json':coverage,
          'historical-January-medicaid-standards.json':historical,'January-cross-publication-comparisons.json':historical_comparisons,
          'work-family-coverage.json':[{'id':k,'title':v,'rule_ids':[r['id'] for r in rules if r['family']==k],
                                       'status':'source_reference_or_explicit_review_gap'} for k,v in catalog.FAMILIES.items()],
          'before-after.json':{'before':{'L12_normalized_records':0},'after':counts,'newly_accepted_fields':0,
                              'earlier_layers_modified':False,'counts_are_not_unique_verified_fact_counts':True},
          'summary.json':{'schema':'l12-published-reference/1','reference_id':'L12-PUBLISHED-FL-2026-research-r1',
                          'reference_year':2026,'reference_date':'2026-10-28',**counts,'research_only':True,
                          'full_l12_complete':False,'collection_and_reference_implementation_complete':True,
                          'qualified_R17_review':None,'human_acceptance':None,'consumer_release_enabled':False,
                          'personal_applicability_enabled':False,'scope':'Published 2026 federal/Florida assistance reference; current October standards plus explicit historical/source gaps, no agency adjudication.'}}
    for name,obj in data.items():write(BUILD/name,obj)
    with closing(sqlite3.connect(BUILD/'l12-reference.sqlite')) as db:
        db.execute('CREATE TABLE datasets (name TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        db.execute('CREATE TABLE records (dataset TEXT, id TEXT, payload TEXT, PRIMARY KEY(dataset,id))')
        for name,obj in data.items():
            db.execute('INSERT INTO datasets VALUES (?,?)',(name,json.dumps(obj,sort_keys=True)))
            if isinstance(obj,list):
                for i,row in enumerate(obj):db.execute('INSERT INTO records VALUES (?,?,?)',(name,str(row.get('id',i)),json.dumps(row,sort_keys=True)))
        db.commit()
    for name in ['l12_acquire.py','l12_sources.py','l12_catalog.py','l12_build.py','l12_validate.py','l12_seal.py']:
        shutil.copyfile(ROOT/'cms-slice/scripts'/name,BUILD/'code'/name)
    shutil.copyfile(ROOT/'cms-slice/tests/test_l12_reference.py',BUILD/'code/test_l12_reference.py')
    print(json.dumps(data['summary.json'],indent=2))


if __name__=='__main__':build()
