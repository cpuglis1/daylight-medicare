"""Independently reconstruct and check the entire L09 reference from native evidence.

Uses openpyxl for source workbooks; never imports the XML-based builder or its
normalization/selection helpers. Same-publication QA is not independent evidence.
"""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import zipfile
import openpyxl

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l09-star-ratings-2026-10-28'
PIN='a72f4f4965239e12b3b264c843a71ea6bbd9c655547be5b1f95b3b0df4d1cde7'
CODE={'l09_acquire.py','l09_build.py','l09_validate.py','l09_reference.py'}
OUTPUTS={'source-manifest.json','documents.json','measure-definitions.json','observations.json','offerings.json',
    'contracts.json','source-members.json','source-tables.json','contract-source-rows.json','context-tables.json',
    'landscape-comparisons.json','inventory.sqlite3','coverage.json','scope.json','gaps.json','refresh-diff.json'}


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:raise ValueError(message)


def interpreted(raw,kind):
    """Independent exact interpretation of the inspected native messages/scale."""
    text=str(raw).strip()
    state={'Not Applicable':'not_applicable','Not enough data available':'not_enough_data',
        'Plan too new to be measured':'too_new','Plan too small to be measured':'too_small',
        'No data available':'no_data','Plan not required to report measure':'not_required',
        'Medicare shows only a Star Rating for this topic':'star_only'}.get(text)
    if state or text=='':return {'state':state or 'blank','value_decimal':None,'unit':None}
    percent=text.endswith('%')
    try:number=Decimal(text.removesuffix('%'))
    except InvalidOperation as e:raise ValueError('Unknown source message') from e
    require(number.is_finite(),'Nonfinite source value')
    if kind!='measure_data':require(not percent and number in [Decimal(i)/2 for i in range(2,11)],'Invalid star state/value')
    elif percent:require(0<=number<=100,'Invalid percent')
    return {'state':'published_numeric' if kind=='measure_data' else 'rated',
        'value_decimal':format(number.normalize(),'f'),
        'unit':'percent' if percent else 'source_measure_value' if kind=='measure_data' else 'stars'}


def raw_cell(value):
    return '' if value is None else str(value)


def csv_table(raw):
    try:text,encoding=raw.decode('utf-8-sig'),'utf-8-sig'
    except UnicodeDecodeError:text,encoding=raw.decode('cp1252'),'cp1252'
    return list(csv.reader(io.StringIO(text))),encoding


def check_companion(raw,cell,kind):
    require(cell.data_type!='f','Unexpected source formula')
    a=raw.strip();b=raw_cell(cell.value).strip()
    if kind=='measure_data' and a.endswith('%'):
        require('%' in cell.number_format,'Percentage fraction lacks explicit source unit format')
        require(Decimal(a[:-1])/100==Decimal(b),'CSV/XLSX percentage differs')
    else:
        require(interpreted(a,kind)==interpreted(b,kind),'Native representations differ')


def validate(package, output=None):
    package=Path(package).resolve()
    manifest=load(package/'manifest.json')
    require(manifest['schema']=='l09-build/1' and manifest['year']==2026,'Wrong reference contract/year')
    require(manifest['archive_sha256']==PIN and manifest['required_observations']==2448 and manifest['offerings']==82 and manifest['contracts']==24,'Changed frozen denominator')
    require(manifest['consumer_release_enabled'] is False and manifest['human_acceptance'] is None,'Invented acceptance/release')
    require((package/'SEALED').read_text().strip()==sha(package/'manifest.json'),'Build seal changed')
    expected_files=OUTPUTS|{'code/'+n for n in CODE}
    require(set(manifest['files_sha256'])==expected_files,'Dropped or added bound output')
    require(set(manifest['code_sha256'])=={'cms-slice/scripts/'+n for n in CODE},'Changed implementation binding')
    for rel,digest in manifest['files_sha256'].items():
        p=(package/rel).resolve();require(p.is_relative_to(package) and sha(p)==digest,'Output hash changed: '+rel)
    for group in ['input_sha256','code_sha256']:
        for rel,digest in manifest[group].items():
            p=(ROOT/rel).resolve();require(p.is_relative_to(ROOT) and sha(p)==digest,'Bound input/code changed: '+rel)
    sources=load(package/'source-manifest.json')
    require(sources==load(ROOT/manifest['source_manifest_path']),'Acquisition export differs')
    require(sources['schema']=='l09-acquisition/1' and sources['year']==2026,'Wrong acquisition year')
    expected_sources={'ratings','technical_notes','fact_sheet','cai_supplement','recalculated_cai_context','correction_context','performance_index'}
    require(set(sources['sources'])==expected_sources,'Missing source/context capture')
    for s in sources['sources'].values():
        p=(ROOT/s['path']).resolve();require(p.is_relative_to(ROOT) and sha(p)==s['sha256'] and p.stat().st_size==s['bytes'],'Changed retained native source')
    require(sources['sources']['ratings']['sha256']==PIN,'Wrong source revision')
    ma_path=ROOT/'docs/data/l02-ma-availability-2026-10-25/build-r5/12021/offerings.json'
    pdp_path=ROOT/'docs/data/l04-pdp-availability-2026-10-25/build-r4/records.json'
    ma,pdp=load(ma_path),load(pdp_path)
    expected_offerings=[]
    for i,r in enumerate(ma,1):
        require(r['year']=='2026','Wrong upstream MA year')
        expected_offerings.append({'offering_id':r['id'],'contract':r['contract'],'name':r['name'],
            'product':'MA-PD' if r['drug']=='Yes' else 'MA-only','rating_type':'overall' if r['drug']=='Yes' else 'part_c_summary',
            'identity_source':str(ma_path.relative_to(ROOT)),'identity_ordinal':i,'scope':'Collier FL 12021',
            'source_status':r['inventory'],'restriction_source_raw':r['restriction_raw']})
    for i,r in enumerate(pdp,1):
        require(r['offering_id'].startswith('2026:'),'Wrong upstream PDP year')
        expected_offerings.append({'offering_id':r['offering_id'],'contract':r['fields']['contract_id']['raw'].strip(),
            'name':r['fields']['plan_name']['raw'].strip(),'product':'PDP','rating_type':'part_d_summary',
            'identity_source':str(pdp_path.relative_to(ROOT)),'identity_ordinal':i,'scope':'Florida PDP region 11; serves Collier',
            'source_status':'published_reference_unaccepted','restriction_source_raw':None})
    for r in expected_offerings:r['primary_observation_id']='2026:'+r['contract']+':summary:'+r['rating_type']
    expected_offerings.sort(key=lambda r:r['offering_id'])
    offerings=load(package/'offerings.json')
    require(offerings==expected_offerings and len(offerings)==82,'Offering identity/type/restriction/join differs')
    contracts=sorted({r['contract'] for r in expected_offerings})
    require(len(contracts)==24,'Contract scope changed')
    require(load(package/'contracts.json')==[{'contract':c,'rating_year':2026,'offering_ids':[r['offering_id'] for r in offerings if r['contract']==c]} for c in contracts],'Contract census differs')
    expected_observations=[];metadata={};native_rows=[];contexts=[];members=[]
    with zipfile.ZipFile(ROOT/sources['sources']['ratings']['path']) as z:
        summary_member=next(n for n in z.namelist() if 'Summary Ratings' in n and n.endswith('.xlsx'))
        master_member=next(n for n in z.namelist() if 'Report_Card_Master_Table' in n and n.endswith('.xlsx'))
        standalone=openpyxl.load_workbook(io.BytesIO(z.read(summary_member)),read_only=True,data_only=False)
        master=openpyxl.load_workbook(io.BytesIO(z.read(master_member)),read_only=True,data_only=False)
        sheet=standalone['Summary_Rating'];sr=list(sheet.iter_rows())
        require(sr[0][0].value=='2026 Summary Star View: Medicare Report Card Master Table','Wrong summary title/year')
        srows={str(r[0].value).strip():(i,r) for i,r in enumerate(sr[2:],3) if r[0].value}
        require(len(srows)==len(sr)-2 and set(contracts)<=srows.keys(),'Missing/duplicate summary source row')
        primary_headers={str(i):{openpyxl.utils.get_column_letter(j):raw_cell(c.value) for j,c in enumerate(sr[i-1],1) if hasattr(c,'coordinate')} for i in [1,2]}
        metadata['summary']={'member':summary_member,'header_rows':primary_headers,'national_contract_rows':len(srows),
            'target_contract_rows':24,'outside_scope_contract_rows':len(srows)-24,'fields_per_contract':3}
        def record(c,kind,code,label,raw,row,col,member,worksheet,headers,revision,domain=None,period=None,definition=None,companion_sheet=None):
            return {'id':'2026:'+c+':'+kind+':'+code,'contract':c,'rating_year':2026,'kind':kind,'code':code,
                'label':label,'domain':domain,'measurement_period_raw':period,
                'measurement_period_basis':'Native measure header' if kind in ['measure_stars','measure_data'] else 'Summary aggregates multiple measure-specific periods' if kind=='summary' else 'Domain aggregates multiple measure-specific periods',
                'raw':raw,**interpreted(raw,kind),'source_member':member,'source_member_sha256':hashlib.sha256(z.read(member)).hexdigest(),
                'source_row':row,'source_column':openpyxl.utils.get_column_letter(col),'source_worksheet':worksheet,
                'source_header_rows':headers,'source_revision_label':revision,'definition_code':definition,
                'companion_member':master_member,'companion_worksheet':companion_sheet}
        msum={str(r[0].value).strip():r for r in list(master['Summary_Rating'].iter_rows())[2:] if r[0].value}
        summary_types=['part_c_summary','part_d_summary','overall'];summary_labels=['2026 Part C Summary','2026 Part D Summary','2026 Overall']
        require([sr[1][i].value for i in [8,9,10]]==summary_labels,'Summary rating types changed')
        for c in contracts:
            ordinal,cells=srows[c]
            native_rows.append({'table':'summary','contract':c,'row':ordinal,'member':summary_member,
                'native_cells':{openpyxl.utils.get_column_letter(i):raw_cell(cell.value) for i,cell in enumerate(cells,1) if hasattr(cell,'coordinate')}})
            for i,(code,label) in enumerate(zip(summary_types,summary_labels),9):
                value=raw_cell(cells[i-1].value);check_companion(value,msum[c][i-1],'summary')
                expected_observations.append(record(c,'summary',code,label,value,ordinal,i,summary_member,'Summary_Rating',[1,2],'July 22 2026',companion_sheet='Summary_Rating'))
        for kind,label,worksheet,skip in [('measure_stars','Measure Stars','Measure_Stars',4),('measure_data','Measure Data','Measure_Data',4),('domain','Domain Stars','Domain_Stars',2)]:
            member=next(n for n in z.namelist() if label in n and n.endswith('.csv'))
            rows,encoding=csv_table(z.read(member));width=50 if skip==4 else 14
            require(all(len(r)==width for r in rows) and rows[0][0].startswith('2026 '),'Native detail layout/year differs')
            data={r[0].strip():(i,r) for i,r in enumerate(rows[skip:],skip+1)}
            require(len(data)==len(rows)-skip and set(contracts)<=data.keys(),'Missing/duplicate detail contract')
            metadata[kind]={'member':member,'encoding':encoding,'header_rows':{str(i+1):r for i,r in enumerate(rows[:skip])},
                'national_contract_rows':len(data),'target_contract_rows':24,'outside_scope_contract_rows':len(data)-24,'fields_per_contract':width-5}
            other={str(r[0].value).strip():r for i,r in enumerate(master[worksheet].iter_rows(),1) if i>skip and r[0].value}
            headings=rows[2] if skip==4 else rows[1];group=None
            for col in range(5,width):
                if rows[1][col].strip():group=rows[1][col]
                code=headings[col].partition(':')[0]
                for c in contracts:
                    ordinal,values=data[c];check_companion(values[col],other[c][col],kind)
                    expected_observations.append(record(c,kind,code,headings[col],values[col],ordinal,col+1,member,None,list(range(1,skip+1)),
                        'Oct 8 2025',group if skip==4 else headings[col],rows[3][col] if skip==4 else None,code if skip==4 else None,worksheet))
            for c in contracts:
                ordinal,values=data[c];native_rows.append({'table':kind,'contract':c,'row':ordinal,'member':member,'native_cells':values})
        rated={summary_member,master_member,*[v['member'] for k,v in metadata.items() if k!='summary']}
        for name in z.namelist():
            raw=z.read(name)
            if name in rated:disposition='whole_master_comparison_and_context' if name==master_member else 'rated_source'
            elif name.endswith('.csv'):
                disposition='retained_context_table';rows,encoding=csv_table(raw)
                contexts.append({'member':name,'encoding':encoding,'use':'published_context_only_no_derived_rating_or_icon',
                    'rows':[{'row':i,'raw':r,'disposition':'header' if i<=2 else 'national_cutpoint_context' if 'Cut Points' in name else 'in_scope_contract' if r[0].strip() in contracts else 'outside_scope_contract'} for i,r in enumerate(rows,1)]})
            else:
                require(name.endswith('.xlsx') and 'PQA_Value_Sets_' in name,'Unaccounted archive member')
                disposition='retained_PQA_identity_methodology_context_no_drug_coverage_assertion'
            members.append({'member':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'disposition':disposition})
        standalone.close();master.close()
    expected_observations.sort(key=lambda r:r['id'])
    observations=load(package/'observations.json')
    require(len(expected_observations)==2448 and observations==expected_observations,'Source-derived observation/value/unit/period/state/locator differs')
    require(load(package/'source-tables.json')==metadata,'Source headers or whole-row accounting differs')
    require(load(package/'contract-source-rows.json')==native_rows,'Dropped source identity/context row')
    require(load(package/'context-tables.json')==contexts,'Context table/source disposition differs')
    require(load(package/'source-members.json')==members and len(members)==13,'Incomplete archive member census')
    documents=[];tech_pages=None;pdf_page_count=0
    for source_id,s in sorted(sources['sources'].items()):
        if s['content_type'].split(';')[0]!='application/pdf':continue
        pages=subprocess.check_output(['pdftotext','-layout','-enc','UTF-8',str(ROOT/s['path']),'-']).decode('utf-8').split('\f')
        if pages[-1]=='':pages.pop()
        pdf_page_count+=len(pages)
        documents.append({'source_id':source_id,'sha256':s['sha256'],'pages':[{'pdf_page':i,'text':t,'sha256':hashlib.sha256(t.encode()).hexdigest()} for i,t in enumerate(pages,1)]})
        if source_id=='technical_notes':tech_pages=pages
    require(load(package/'documents.json')==documents,'Truncated or changed full methodology/context pages')
    # Reconstruct each section by line boundaries, independently of builder regex.
    headings=[];page_starts=[];offset=0
    for i,page in enumerate(tech_pages,1):
        page_starts.append(offset);at=offset
        for line in page.splitlines(keepends=True):
            stripped=line.strip()
            if i>10 and stripped.startswith('Measure:') and '.....' not in stripped:
                after=stripped.partition(':')[2].strip();code=after[:3]
                if re.fullmatch('[CD][0-9]{2}',code):headings.append((code,at,after[3:].lstrip(' -–—'),i))
            at+=len(line)
        offset+=len(page)+1
    require([h[0] for h in headings]==['C'+str(i).zfill(2) for i in range(1,34)]+['D'+str(i).zfill(2) for i in range(1,13)],'Definition code census differs')
    joined='\f'.join(tech_pages);last_start=headings[-1][1]
    at=last_start;last_end=None
    for line in joined[last_start:].splitlines(keepends=True):
        if line.lstrip().startswith('Attachment A:'):
            last_end=at;break
        at+=len(line)
    require(last_end is not None,'Technical definition end missing')
    expected_definitions=[]
    for n,(code,start,label,pageno) in enumerate(headings):
        end=headings[n+1][1] if n+1<len(headings) else last_end
        segments=[]
        for i,(left,page) in enumerate(zip(page_starts,tech_pages),1):
            a,b=max(left,start),min(left+len(page),end)
            if a<b:
                text=joined[a:b];segments.append({'pdf_page':i,'start':a-left,'end':b-left,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()})
        expected_definitions.append({'code':code,'heading_first_line':label,'segments':segments,
            'interpretation':'Complete published definition retained; no personal clinical or quality-fit inference'})
    require(load(package/'measure-definitions.json')==expected_definitions,'Definition page/section/unit/qualification text differs')
    # Independently re-read exact upstream landscape identities and all summary fields.
    land=ROOT/'docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw/75f2797b510449fc0d376bbbbeb3c129f6091a697555281559ca28e6e4b8d882'
    byid={r['id']:r for r in expected_observations};ids={r['offering_id'] for r in offerings};comparisons=[]
    with zipfile.ZipFile(land) as z:
        member=next(n for n in z.namelist() if n.endswith('.csv'))
        for ordinal,row in enumerate(csv.DictReader(io.TextIOWrapper(z.open(member),encoding='utf-8-sig')),2):
            oid=':'.join([row['Contract Year'].strip(),row['Contract ID'].strip(),row['Plan ID'].strip().zfill(3),row['Segment ID'].strip().zfill(3)])
            if oid not in ids or row['State Territory Abbreviation'].strip()!='FL' or (not row['Contract ID'].startswith('S') and row['County Name'].strip()!='Collier'):continue
            for code,field in zip(['part_c_summary','part_d_summary','overall'],['Part C Summary Star Rating','Part D Summary Star Rating','Overall Star Rating']):
                observation=byid['2026:'+row['Contract ID']+':summary:'+code]
                agrees=interpreted(row[field],'summary')=={k:observation[k] for k in ['state','value_decimal','unit']}
                require(agrees,'Landscape basis/value conflict requires explicit hold')
                comparisons.append({'offering_id':oid,'field':field,'observation_id':observation['id'],'source_member':member,
                    'source_row':ordinal,'landscape_raw':row[field],'rating_raw':observation['raw'],'agrees':agrees})
    require(len(comparisons)==246 and load(package/'landscape-comparisons.json')==comparisons,'Landscape denominator/comparison differs')
    con=sqlite3.connect('file:'+str(package/'inventory.sqlite3')+'?mode=ro',uri=True)
    require({r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}=={'observations','offerings','contracts','definitions','context'},'Unexpected database tables')
    observed_db=con.execute('SELECT * FROM observations ORDER BY id').fetchall()
    require(len(observed_db)==2448,'Database observation count differs')
    for row,r in zip(observed_db,observations):
        require(row[:7]==tuple(r[k] for k in ['id','contract','kind','code','state','value_decimal','unit']) and json.loads(row[7])==r,'Indexed/payload observation differs')
    require([json.loads(r[0]) for r in con.execute('SELECT payload FROM offerings ORDER BY offering_id')]==offerings,'Database offering payload differs')
    for row,r in zip(con.execute('SELECT * FROM offerings ORDER BY offering_id'),offerings):
        require(row[:4]==tuple(r[k] for k in ['offering_id','contract','rating_type','primary_observation_id']),'Indexed offering join differs')
    for table,key,expected in [('contracts','contract',load(package/'contracts.json')),('definitions','code',expected_definitions),('context','member',contexts)]:
        require({r[0]:json.loads(r[1]) for r in con.execute('SELECT * FROM '+table)}=={r[key]:r for r in expected},'Database '+table+' differs')
    require(con.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Database integrity failed');con.close()
    coverage=load(package/'coverage.json')
    require(coverage=={'schema':'l09-coverage/1','year':2026,'offerings':82,'contracts':24,'required_observations':2448,
        'observations_by_kind':dict(Counter(r['kind'] for r in observations)),
        'states_by_kind':{k:dict(Counter(r['state'] for r in observations if r['kind']==k)) for k in sorted({r['kind'] for r in observations})},
        'offering_rating_types':dict(Counter(r['rating_type'] for r in offerings)),'measure_definitions':45,'archive_members':13,
        'source_row_accounting':metadata,'landscape_fields_compared':246,'missing_contracts':[],'missing_offerings':[],
        'consumer_release_enabled':False,'personal_fit_implemented':False,'human_acceptance':None},'Coverage/count/state ledger differs')
    scope=load(package/'scope.json')
    require(scope['year']==2026 and scope['MA_county_fips']=='12021' and scope['MA_state']=='FL' and scope['PDP_state']=='FL' and scope['PDP_region']=='11','Scope differs')
    require(scope['required_observation_ids']==[r['id'] for r in observations] and scope['summary_revision']=='2026-07-22' and scope['detail_filename_date']=='2025-10-08','Source period or frozen ID denominator differs')
    gaps=load(package/'gaps.json')
    require({r['id'] for r in gaps['pending']}=={'R14','G02','G06'} and not gaps['missing_published_source_rows'] and not gaps['unexplained_comparison_conflicts'],'Changed gap/review obligations')
    diff=load(package/'refresh-diff.json')
    require(not diff['added_offerings'] and not diff['removed_offerings'] and not diff['summary_value_changes'] and diff['new_normalized_observations']==2448,'Planning refresh diff differs')
    result={'schema':'l09-independent-validation/1','passed':True,'manifest_sha256':sha(package/'manifest.json'),
        'source_cells_checked':2448,'landscape_fields_checked':246,'offering_joins_checked':82,
        'measure_definitions_checked':45,'archive_members_accounted':13,'PDF_pages_checked':pdf_page_count,
        'context_native_rows_checked':sum(len(c['rows']) for c in contexts),'unexplained_modeled_value_mismatches':0,
        'consumer_release_enabled':False,'human_acceptance':None,
        'limits':'Whole modeled population/source-copy validation. CSV/XLSX agreement is same-publication QA; no independent clinical/quality interpretation or acceptance.'}
    if output is not None:
        output=Path(output);require(not output.exists(),'Refusing to overwrite validation receipt')
        output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();print(json.dumps(validate(a.package,a.out),indent=2))
