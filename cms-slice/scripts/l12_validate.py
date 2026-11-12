"""Independent raw-evidence, storage and reference-boundary checks for L12.

Synthetic helpers below test interpretations only. They are never a personal
eligibility API and are not imported by the application.
"""
from contextlib import closing
from datetime import date
from decimal import Decimal
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l12-help-with-costs-2026-10-28'
BUILD=BASE/'build-r1'

def load(p):return json.loads(Path(p).read_text())
def norm(s):return ' '.join(s.split())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dec(s):return Decimal(s.replace('$','').replace(',','').replace('+','').strip())
def check(ok,why):
    if not ok:raise ValueError(why)

def raw_html_rows(path):
    """Separate regex extraction, independent of the ingestion HTML parser."""
    result=[]
    for body in re.findall(r'<table\b[^>]*>(.*?)</table>',Path(path).read_text(errors='replace'),re.I|re.S):
        rows=[]
        for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',body,re.I|re.S):
            cells=[norm(unescape(re.sub(r'<[^>]+>','',x))) for x in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>',row,re.I|re.S)]
            if any(cells):rows.append(cells)
        result.append(rows)
    return result

def reference_deemed(status,confirmed,part_d_eligible):
    if confirmed is not True or part_d_eligible is not True:return None
    return status in {'SSI','full_benefit_Medicaid','QMB','SLMB','QI'}

def deemed_through(day):
    day=date.fromisoformat(day)
    return date(day.year+(day.month>=7),12,31).isoformat()

def resource_basis(base,burial_people):
    if burial_people is None:return None
    if burial_people not in (0,1,2):raise ValueError('Invalid burial-person count')
    return Decimal(base)+Decimal(1500)*burial_people

def synthetic_lis_boundary(countable_income,annual_fpl_150,countable_resources,base_limit):
    if any(x is None for x in [countable_income,annual_fpl_150,countable_resources,base_limit]):return None
    return Decimal(countable_income)<Decimal(annual_fpl_150) and Decimal(countable_resources)<=Decimal(base_limit)

def validate_data(data):
    """Reconcile modeled tables and conditions without using builder/catalog."""
    s=data['summary.json'];sources=data['sources.json'];units=data['source-clause-ledger.json']
    check(s['reference_year']==2026 and s['reference_date']=='2026-10-28','Reference year/date')
    check(s['research_only'] is True and s['full_l12_complete'] is False,'Scope must retain unresolved review/historical gaps')
    check(s['collection_and_reference_implementation_complete'] is True,'Execution status')
    for k in ['consumer_release_enabled','personal_applicability_enabled']:check(s[k] is False,'Consumer or personal gate changed')
    for k in ['qualified_R17_review','human_acceptance']:check(s[k] is None,'Invented acceptance')
    byid={u['id']:u for u in units};check(len(byid)==len(units),'Duplicate clause')
    for filename,obj in data.items():
        if not isinstance(obj,list):continue
        for row in obj:
            for sid in row.get('source_clause_ids',[]):check(sid in byid,'Dangling source '+sid)
    rules={r['id']:r for r in data['rules.json']}
    check(set(rules)=={f'R{i:02}' for i in range(1,35)},'Rule denominator changed')
    for r in rules.values():
        check(r['reference_year']==2026 and r['reference_date']=='2026-10-28','Rule temporal context')
        check(r['qualified_review'] is None and r['human_acceptance'] is None and r['consumer_release_enabled'] is False,'Rule review gates')
        check(r['source_conditions']==[{'source_clause_id':i,'text':byid[i]['text']} for i in r['source_clause_ids']],'Complete evidence/conditions changed '+r['id'])
    programs=data['programs.json']
    check(len(programs)==12 and len({p['id'] for p in programs})==12,'Program inventory')
    for p in programs:
        check(p['eligibility_result']=='not_determined' and p['personal_applicability_enabled'] is False,'Invented program eligibility')
        check(p['source_clause_ids']==sorted({i for r in p['rule_ids'] for i in rules[r]['source_clause_ids']}),'Lost program lineage')
    families=data['work-family-coverage.json'];check(len(families)==12,'Work-family inventory')
    for f in families:check(f['rule_ids']==[r['id'] for r in rules.values() if r['family']==f['id']],'Work-family accounting')
    # Check exact raw source values in A-9.1 by reading each printed row. This
    # parser uses dollar-token positions rather than the builder's row regex.
    text=(ROOT/sources['dcf-a91-reused']['text_path']).read_text()
    expected=[];period=None
    labels=['Individual','Couple/2']+[str(i) for i in range(3,11)]+['Additional']
    for line in text.splitlines():
        if 'Financial Standards Effective April 2026' in line:period='april'
        if 'Interim Effective January 2026' in line:period='interim_january'
        pieces=line.split()
        if period and pieces and pieces[0] in labels and '$' in line:
            expected.append((period,pieces[0],re.findall(r'\+?\$[0-9,]+',line),norm(line)))
    rows=data['florida-msp-lis-tables.json'];check(len(rows)==len(expected)==22,'A91 row completeness')
    for row,(period,label,tokens,quote) in zip(rows,expected):
        check(row['id']==f'A91-{period}-{label}' and row['period']==period and row['family_size_source']==label,'A91 identity')
        check(row['family_size']==(1 if label=='Individual' else 2 if label=='Couple/2' else int(label) if label.isdigit() else None),'Family-size normalization')
        check(row['source_money_tokens']==tokens and row['source_quote']==quote,'A91 exact source tokens')
        names=['QMB','SLMB','QI','MSP_resources','LIS','LIS_base_resources'] if label in labels[:2] else ['QMB','SLMB','QI','LIS']
        expectedfields=dict(zip(names,[str(dec(x)) for x in tokens]))
        for n,field in row['fields'].items():
            check(field['value']==expectedfields.get(n),'A91 value/blank '+row['id']+' '+n)
            check(field['unit']==('USD/resources' if 'resources' in n else 'USD/month'),'A91 units')
            check(field['source_status']==('blank' if n not in expectedfields else 'published'),'A91 published/blank state')
            basis='source_blank_not_zero' if n not in expectedfields else 'base_resources_before_burial_exclusion' if n=='LIS_base_resources' else 'countable_resources' if 'resources' in n else 'countable_income_standard'
            check(field['basis']==basis,'A91 countable/resource basis')
        check(set(row['fields'])=={'QMB','SLMB','QI','MSP_resources','LIS','LIS_base_resources'},'A91 field omission')
        check((row['effective_start'],row['effective_end_exclusive'])==(('2026-04-01','2027-01-01') if period=='april' else ('2026-01-01','2026-04-01')),'A91 dates')
        check(row['interpretation_status']==('current_published_standard' if period=='april' else 'dated_DCF_interim_2_8_percent_explanation_and_attached_table_reconciled'),'January explanation status')
    # Independent HTML table extraction verifies all selected FPL/MSP cells,
    # not only sampled individuals. Unselected history/geographies stay raw.
    tables=raw_html_rows(ROOT/sources['ssa-0603001020']['path'])
    fpl=data['federal-FPL-2026.json'];check(len(fpl)==11,'FPL all family rows')
    check(tables[0][1][1]=='$15,960.00','FPL 2026/geography selection')
    for row,raw in zip(fpl,tables[0][1:]):
        check(row['family_size_source']==raw[0] and row['source_cells']==raw,'FPL family/source')
        check(row['values']==dict(zip(['100','135','140','145','150'],[str(dec(x)) for x in raw[1:]])),'FPL all percentage cells')
        check(row['unit']=='USD/year_countable_income' and row['reference_year']==2026 and 'Florida' in row['geography'],'FPL unit/year/geography')
    tables=raw_html_rows(ROOT/sources['ssa-0600815023']['path']);msp=data['federal-MSP-2026.json'];check(len(msp)==8,'Federal MSP complete rows')
    for row in msp:
        t=tables[['QMB','SLMB','QI','QDWI'].index(row['program'])]
        raw=next(x for x in t if x[0].startswith('All States') or x[0]=='Resource Limits') if row['id'].endswith('income') else next(x for x in t if x[0]=='Resource Limits')
        check(row['source_cells']==raw and dec(row['individual'])==dec(raw[1]) and dec(row['couple'])==dec(raw[2]),'Federal MSP value')
        income=row['id'].endswith('income')
        check(row['unit']==('USD/month' if income else 'USD/resources'),'MSP units')
        check(row['basis']==('gross_summary_including_20_and_earned_disregards' if income and row['program']=='QDWI' else 'gross_summary_including_20_disregard' if income else 'federal_resource_floor'),'Federal gross basis')
    # A-9 has corrupt native glyph mapping. Require the pinned rendered image
    # and OCR, then check every manually modeled value against printed tokens.
    a9=data['florida-medicaid-standards.json'];check(len(a9)==44,'A9 numeric denominator')
    printed=(ROOT/sources['dcf-a9-current']['ocr_path']).read_text()
    check('FINANCIAL ELIGIBILTY STANDARDS July 2026' in printed,'A9 table edition')
    numbers={dec(x) for x in re.findall(r'\$\s*([\d,]+(?:\.\d+)?)',printed)}
    for r in a9:
        check(dec(r['value']) in numbers,'A9 missing printed number '+r['id'])
        check(r['source_clause_ids']==['dcf-a9-current:PAGE:1'] and r['personal_calculation_enabled'] is False,'A9 provenance/gate')
        check(r['reference_table_edition']=='July 2026','A9 edition')
    # Separately authored semantic anchors catch row swaps, unit/date changes
    # and law/table differences that a numeric-token check alone cannot catch.
    anchors=[('A909','asset_disregard','13000','USD/resources',None),('A910','asset_disregard','24000','USD/resources',None),
             ('A915','income_level_for_share_of_cost','180','USD/month',None),('A916','income_level_for_share_of_cost','241','USD/month',None),
             ('A921','asset_limit','5000','USD/resources',None),('A932','exclusion_monthly_maximum','2410','USD/month','2026-01-01'),
             ('A933','exclusion_annual_maximum','9730','USD/year','2026-01-01'),('A938','MMMNA','2705','USD/month','2026-07-01'),
             ('A940','excess_shelter_standard','812','USD/month','2026-07-01'),('A943','divisor','10645','USD/month_divisor','2025-04-01')]
    a9id={r['id']:r for r in a9}
    for i,field,value,unit,start in anchors:check(tuple(a9id[i][k] for k in ['field','value','unit','effective_start'])==(field,value,unit,start),'A9 semantic/date anchor '+i)
    # Full 44-cell transcription and its contextual fields must additionally
    # match the separate visual-review receipt made from the printed PDF.
    visual=load(BASE/'visual-review-r1.json')
    check(visual['source_sha256']==sources['dcf-a9-current']['sha256'] and visual['render_sha256']==digest(ROOT/sources['dcf-a9-current']['render_path']),'A9 visual source fingerprint')
    check(visual['transcribed_rows']==[{k:r[k] for k in ['id','program_context','field','value','unit','effective_start','basis']} for r in a9],'All A9 modeled field transcription')
    check(visual['reviewer_kind']=='AI visual inspection; not independent qualified review','Visual review honesty')
    historical=data['historical-January-medicaid-standards.json'];check(len(historical)==44,'All historical A9 observations')
    hist_page=(ROOT/sources['dcf-cola-2026-archive']['text_path']).read_text().split('\f')[10]
    histnums={dec(x) for x in re.findall(r'\$\s*([\d,]+(?:\.\d+)?)',hist_page)}
    for r in historical:
        check(dec(r['value']) in histnums and r['source_clause_ids']==['dcf-cola-2026-archive:PAGE:11'],'Historical A9 printed value/provenance')
        check(r['reference_table_edition']=='January 2026' and r['personal_calculation_enabled'] is False,'Historical A9 status')
    histvisual=load(BASE/'historical-visual-review-r1.json')
    check(histvisual['source_sha256']==sources['dcf-cola-2026-archive']['sha256'],'Historical visual fingerprint')
    check(histvisual['transcribed_rows']==[{k:r[k] for k in ['id','program_context','field','value','unit','effective_start','basis']} for r in historical],'Historical A9 full transcription')
    hc=data['January-cross-publication-comparisons.json'];check(len(hc)==11,'All January comparison rows')
    janpage=(ROOT/sources['dcf-cola-2026-archive']['text_path']).read_text().split('\f')[11].split('Financial Standards April 2025')[0]
    for r in hc:
        original=next(x for x in rows if x['id']==r['record_id'])
        line=next(x for x in janpage.splitlines() if x.split() and x.split()[0]==original['family_size_source'])
        printedtokens=re.findall(r'\+?\$[\d,]+',line)
        check(r['source_money_tokens']==printedtokens==original['source_money_tokens'] and r['printed_numeric_cells']==len(printedtokens),'January independent cross-publication comparison')
    check(sum(r['printed_numeric_cells'] for r in hc)==48,'All 48 printed January numeric cells')
    memotext=(ROOT/sources['dcf-cola-2026-archive']['text_path']).read_text()
    check('An interim increase of 2.8 percent' in memotext and 'staff must not take action to close an' in memotext,'Interim explanation/continuity safeguard')
    studenttables=raw_html_rows(ROOT/sources['ssa-0500820510']['path'])
    student=next(r for t in studenttables for r in t if r[0]=='2026')
    check([dec(x) for x in student[1:]]==[Decimal('2410'),Decimal('9730')],'SSA operative student exclusion')
    memo=(ROOT/sources['cms-lis-2026']['text_path']).read_text().split('\f')
    resources=data['LIS-resources-2026.json'];check(len(resources)==2,'LIS resource denominator')
    for r,base,burial,total in zip(resources,['16590','33100'],['1500','3000'],['18090','36100']):
        check((r['base_limit'],r['maximum_burial_exclusion'],r['display_with_full_burial_allowance'])==(base,burial,total),'LIS resource basis')
        check(all(dec(x) in {dec(n) for n in re.findall(r'\$([\d,]+)',memo[0])} for x in [base,total]),'LIS source base/display')
    cost=data['LIS-cost-sharing-2026.json'];check(len(cost)==5,'LIS categories')
    rawcost=re.findall(r'^.*?\$0\s+\$(\d+(?:\.\d+)?)\s+\$(\d+(?:\.\d+)?)\s*$',memo[3],re.M)
    check(len(rawcost)==5,'CMS printed cost rows')
    for r,(generic,brand) in zip(cost,rawcost):
        check(dec(r['generic_copayment_maximum'])==dec(generic) and dec(r['brand_copayment_maximum'])==dec(brand),'LIS all copays')
        check(r['deductible_maximum']=='0' and r['annual_out_of_pocket_threshold']=='2100' and r['covered_drug_cost_share_above_threshold']=='0','LIS deductible/OOP')
        check(r['effective_start']=='2026-01-01' and r['effective_end_exclusive']=='2027-01-01' and 'maxima' in r['cost_basis'],'LIS dates and maximum basis')
    check('$2,100 for 2026' in memo[3] and 'no cost-sharing' in memo[3],'CMS OOP footnote')
    comparisons=data['basis-reconciliations.json'];check(len(comparisons)==6,'Basis comparison denominator')
    for r in comparisons:
        state=next(x for x in rows if x['id']==r['state_record_id'])
        federal=next(x for x in msp if x['id']==r['federal_record_id'])
        program=federal['program'];who='individual' if state['family_size']==1 else 'couple'
        check(r['state_countable']==state['fields'][program]['value'] and r['federal_gross_summary']==federal[who],'Comparison source linkage')
        check(r['general_disregard']=='20' and dec(r['state_countable'])+20==dec(r['federal_gross_summary']) and r['status']=='matches_after_basis_adjustment','Gross/countable $20 reconciliation')
    automatic=data['automatic-routes.json'];check(len(automatic)==6,'Automatic route count')
    for r in automatic:
        check(r['deems_LIS']==reference_deemed(r['qualifying_status'],True,True),'QDWI/SSI automatic-route distinction')
        check(r['conditions']==['actual_confirmed_status','Medicare_Part_D_eligible'] and r['not_a_personal_determination'] is True,'Automatic-route conditions')
    routes={r['id']:r for r in data['application-referrals.json']}
    check(set(routes)=={'ROUTE-DCF','ROUTE-SSA','ROUTE-SHINE','ROUTE-COLLIER'},'Referral inventory')
    for key,sid in [('ROUTE-DCF','dcf-help-landing'),('ROUTE-SSA','ssa-0603010010'),('ROUTE-SHINE','shine-contact'),('ROUTE-COLLIER','shine-collier')]:
        check(routes[key]['information_url']==sources[sid]['url'] and routes[key]['action_performed']=='public_information_only','Referral source/action')
    landing=load(ROOT/sources['dcf-help-landing']['structured_text_path'])
    check(routes['ROUTE-DCF']['application_url'] in {a['url'].rstrip('/') for a in landing['links'] if a['url']},'DCF application link')
    digits=re.sub(r'\D','',byid['shine-contact:ALL']['text'])
    for field in ['phone','TTY']:check(re.sub(r'\D','',routes['ROUTE-SHINE'][field]) in digits,'SHINE contact field source')
    # Critical qualifications cannot be lost from normalized prose.
    for rid,needles in {'R01':['income and resources','actual Part D'], 'R02':['QDWI alone is excluded','actual qualifying status'],
        'R03':['June 30','July 1','following year'],'R09':['none/one/both','Do not deduct'],
        'R10':['below 150%','at or below'],'R11':['contradictory note','both'],
        'R12':['does not guarantee','enhanced'], 'R21':['not the HCBS','does not itself deem'],
        'R22':['$5,000/$6,000','$4,000/$6,000'], 'R24':['no Medicare','qualifying institutional, hospice or HCBS'],
        'R25':['not gross-income','share of cost'], 'R27':['May 21, 2026','asset disregard','HCBS-waiver','predates 2026','broader disability'],
        'R30':['precise Florida election is not verified','not into a previous calendar year'],
        'R34':['not full Medicare Part B','does not by itself establish Part D']}.items():
        for needle in needles:check(needle in rules[rid]['meaning'],'Lost consequential qualification '+rid+': '+needle)
    coverage=data['medicaid-coverage-accounting.json'];expected={k for k in byid if k.startswith('dcf-2000:SECTION:2040.')}
    check({r['source_clause_id'] for r in coverage}==expected and len(coverage)==len(expected),'Complete MSSI passage accounting')
    check({g['id'] for g in data['gaps.json']}=={'G01','G02','G03','G04'},'Explicit unresolved gaps')
    for g in data['gaps.json']:check(g['independent_review'] is None and g['consumer_release_enabled'] is False,'Invented gap closure')
    counts={'program_records':len(programs),'source_scoped_rule_records':len(rules),'A91_rows':len(rows),'A9_numeric_observations':len(a9),
            'federal_FPL_rows':len(fpl),'federal_MSP_rows':len(msp),'LIS_resource_rows':len(resources),'LIS_cost_sharing_rows':len(cost),
            'automatic_routes':len(automatic),'basis_reconciliations':len(comparisons),'source_units':len(units),'source_registry_entries':len(sources),
            'retained_sources':sum(x['status']=='retained' for x in sources.values()),'retained_PDF_pages':sum(x.get('pdf_pages',0) for x in sources.values()),
            'coverage_passages':len(coverage),'historical_A9_observations':len(historical),'January_cross_publication_comparisons':len(hc)}
    check(all(s[k]==n for k,n in counts.items()),'Summary counts match complete datasets')
    check(data['before-after.json']['after']==counts and data['before-after.json']['newly_accepted_fields']==0,'Exact before/after accounting')
    return {'modeled_tables':'all selected rows and numeric fields checked; A9 all fields match visual transcript',
            'rules':'34 evidence bundles/critical conditions checked; prose meanings remain AI comparisons pending R17',
            'scope_guards':'passed','basis_comparisons':6,'programs':12,'rules_count':34}

def validate(build=BUILD,write_result=True):
    build=Path(build)
    with closing(sqlite3.connect('file:'+str(build/'l12-reference.sqlite')+'?mode=ro',uri=True)) as db:
        data={name:load(build/name) for name, in db.execute('SELECT name FROM datasets')}
        for name,payload in db.execute('SELECT name,payload FROM datasets'):
            check(json.loads(payload)==data[name],'SQLite/JSON full dataset mismatch '+name)
        expected={(name,str(r.get('id',i))):r for name,obj in data.items() if isinstance(obj,list) for i,r in enumerate(obj)}
        actual={(name,key):json.loads(payload) for name,key,payload in db.execute('SELECT dataset,id,payload FROM records')}
        check(expected==actual,'SQLite/JSON complete record/field parity')
        check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity')
    sources=data['sources.json'];fresh={};raw_count=0
    for sid,s in sources.items():
        check(sid==s['id'],'Source identity')
        if 'path' in s:
            check(digest(ROOT/s['path'])==s['sha256'],'Raw source changed '+sid)
            check((ROOT/s['path']).stat().st_size==s['bytes'],'Source byte count '+sid)
        if s['status']!='retained':continue
        raw=ROOT/s['path'];kind=s['extraction_kind'];raw_count+=1
        if kind=='native_pdf_text':
            extracted=subprocess.run(['pdftotext','-layout',str(raw),'-'],check=True,capture_output=True).stdout.decode()
            check(extracted==(ROOT/s['text_path']).read_text(),'Fresh PDF extraction mismatch '+sid)
            check(extracted.count('\f')==s['pdf_pages'],'PDF page count '+sid)
            fresh[sid]=extracted
        elif kind=='word_textutil':
            extracted=subprocess.run(['textutil','-convert','txt','-stdout',str(raw)],check=True,capture_output=True).stdout.decode()
            check(extracted==(ROOT/s['text_path']).read_text(),'Fresh rule-document extraction')
            fresh[sid]=extracted
        elif kind=='ecfr_xml_sections':
            tree=ET.parse(raw);sections={n.get('N'):norm(' '.join(n.itertext())) for n in tree.iter('DIV8')}
            for row in load(ROOT/s['structured_text_path'])['sections']:check(row['text']==sections[row['section']],'Fresh CFR full section')
            fresh[sid]=sections
        else:
            # Raw table comparisons above use a different parser. All visible
            # text/links are also re-extracted with the source parser.
            from l12_sources import PublicHTML
            parser=PublicHTML();parser.feed(raw.read_text(errors='replace'));parsed=parser.result()
            check(parsed==load(ROOT/s['structured_text_path']),'Fresh HTML full extraction '+sid)
            fresh[sid]=parsed
    # Check exact passage spans/pages against freshly extracted raw sources.
    for u in data['source-clause-ledger.json']:
        sid=u['source_id'];loc=u['locator'];source=fresh[sid]
        if 'character_start' in loc:expected=norm(source[loc['character_start']:loc['character_end']])
        elif 'pdf_page' in loc:
            expected=norm((ROOT/sources[sid]['ocr_path']).read_text()) if loc['method']=='OCR_plus_visual_review' else norm(source.split('\f')[loc['pdf_page']-1])
        elif 'section' in loc:expected=source[loc['section']]
        elif 'table' in loc:expected=norm(' | '.join(source['tables'][loc['table']-1]['rows'][loc['row']-1]))
        elif 'derived_line' in loc:expected=source['lines'][loc['derived_line']-1]
        else:expected=norm('\n'.join(source['lines'])) if isinstance(source,dict) else norm(source)
        check(expected==u['text'],'Exact source passage mismatch '+u['id'])
    # Independent fresh OCR must agree with retained extraction; visual review
    # controls the printed half fractions and row/column interpretation.
    s=sources['dcf-a9-current']
    ocr=subprocess.run(['tesseract',str(ROOT/s['render_path']),'stdout','-l','eng','--psm','6'],check=True,capture_output=True).stdout.decode()
    check(ocr==(ROOT/s['ocr_path']).read_text(),'Fresh A9 OCR mismatch')
    result={'schema':'l12-validation/1','passed':True,'raw_sources_verified':raw_count,
            'source_units_verified':len(data['source-clause-ledger.json']),
            'sqlite_full_dataset_parity':True,'sqlite_full_record_field_parity':True,
            **validate_data(data),'independent_qualified_review':False,'acceptance':None}
    if write_result:
        check(not (build/'manifest.json').exists(),'Cannot mutate a sealed revision')
        (build/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--verify-only',action='store_true');args=parser.parse_args()
    print(json.dumps(validate(write_result=not args.verify_only),indent=2))
