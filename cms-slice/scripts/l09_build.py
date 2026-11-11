"""Build the pinned published 2026 contract-quality research reference."""
import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import posixpath
import re
import shutil
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l09-star-ratings-2026-10-28'
MA = ROOT / 'docs/data/l02-ma-availability-2026-10-25/build-r5/12021/offerings.json'
PDP = ROOT / 'docs/data/l04-pdp-availability-2026-10-25/build-r4/records.json'
LAND = ROOT / 'docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw/75f2797b510449fc0d376bbbbeb3c129f6091a697555281559ca28e6e4b8d882'
ARCHIVE_SHA = 'a72f4f4965239e12b3b264c843a71ea6bbd9c655547be5b1f95b3b0df4d1cde7'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
MESSAGES = {
    'Not Applicable': 'not_applicable', 'Not enough data available': 'not_enough_data',
    'Plan too new to be measured': 'too_new', 'Plan too small to be measured': 'too_small',
    'No data available': 'no_data', 'Plan not required to report measure': 'not_required',
    'Medicare shows only a Star Rating for this topic': 'star_only',
}
SUMMARY = [('part_c_summary', '2026 Part C Summary'), ('part_d_summary', '2026 Part D Summary'), ('overall', '2026 Overall')]
LAND_FIELDS = ['Part C Summary Star Rating', 'Part D Summary Star Rating', 'Overall Star Rating']
CODE = ['l09_acquire.py', 'l09_build.py', 'l09_validate.py', 'l09_reference.py']


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def column(index):
    result = ''
    while index:
        index, digit = divmod(index-1, 26)
        result = chr(65+digit)+result
    return result


def workbook(raw):
    """Direct XML extraction, independent of validator's openpyxl extraction."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', NS)]
        styles = ET.fromstring(z.read('xl/styles.xml'))
        formats = {0: 'General', 9: '0%', 10: '0.00%'}
        formats.update({int(x.get('numFmtId')): x.get('formatCode') for x in styles.findall('s:numFmts/s:numFmt', NS)})
        xfs = [int(x.get('numFmtId', '0')) for x in styles.findall('s:cellXfs/s:xf', NS)]
        rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS):
            target = rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows = {}
            for row in ET.fromstring(z.read(path)).findall('s:sheetData/s:row', NS):
                cells = {}
                for c in row.findall('s:c', NS):
                    if c.find('s:f', NS) is not None:
                        raise ValueError('Unexpected formula in rated source worksheet')
                    value = c.findtext('s:v', '', NS)
                    if c.get('t') == 's':
                        value = strings[int(value)]
                    elif c.get('t') == 'inlineStr':
                        value = ''.join(c.find('s:is', NS).itertext())
                    letters = re.sub(r'\d', '', c.get('r'))
                    number = 0
                    for letter in letters:
                        number = number*26+ord(letter)-64
                    numfmt = xfs[int(c.get('s', '0'))]
                    cells[number] = {'raw': value, 'format': formats.get(numfmt, 'builtin:'+str(numfmt))}
                if cells:
                    rows[int(row.get('r'))] = cells
            result[sheet.get('name')] = rows
        return result


def csv_rows(raw):
    try:
        text, encoding = raw.decode('utf-8-sig'), 'utf-8-sig'
    except UnicodeDecodeError:
        text, encoding = raw.decode('cp1252'), 'cp1252'
    return list(csv.reader(io.StringIO(text))), encoding


def scalar(raw, kind):
    token = raw.strip()
    if token in MESSAGES:
        return {'state': MESSAGES[token], 'value_decimal': None, 'unit': None}
    if not token:
        return {'state': 'blank', 'value_decimal': None, 'unit': None}
    percent = token.endswith('%')
    try:
        number = Decimal(token[:-1] if percent else token)
    except InvalidOperation as error:
        raise ValueError('Uninspected CMS source token: '+repr(raw)) from error
    if not number.is_finite():
        raise ValueError('Nonfinite source number')
    if kind != 'measure_data' and (percent or number < 1 or number > 5 or number*2 != (number*2).to_integral_value()):
        raise ValueError('Invalid published star scale')
    if kind == 'measure_data' and percent and not 0 <= number <= 100:
        raise ValueError('Invalid source percent')
    return {'state': 'published_numeric' if kind == 'measure_data' else 'rated',
            'value_decimal': format(number.normalize(), 'f'),
            'unit': 'percent' if percent else 'source_measure_value' if kind == 'measure_data' else 'stars'}


def pdf_pages(path):
    text = subprocess.check_output(['pdftotext', '-layout', '-enc', 'UTF-8', str(path), '-']).decode('utf-8')
    pages = text.split('\f')
    if pages[-1] == '':
        pages.pop()
    return pages


def definitions(pages):
    joined = '\f'.join(pages)
    starts, offset = [], 0
    for i, page in enumerate(pages, 1):
        if i > 10:
            for m in re.finditer(r'(?m)^[ \t]*Measure:\s*([CD]\d{2})\s*[-–—]\s*(.+)$', page):
                if '.....' not in m.group(2):
                    starts.append((m.group(1), offset+m.start(), offset+m.end(), i, m.group(2).strip()))
        offset += len(page)+1
    expected = ['C'+str(i).zfill(2) for i in range(1,34)]+['D'+str(i).zfill(2) for i in range(1,13)]
    if [s[0] for s in starts] != expected:
        raise ValueError('Measure-definition heading denominator changed')
    boundaries, at = [], 0
    for i, page in enumerate(pages, 1):
        boundaries.append((at, at+len(page), i))
        at += len(page)+1
    result = []
    end_last = re.search(r'(?m)(?:^|\f)[ \t]*Attachment A:', joined[starts[-1][2]:])
    if not end_last:
        raise ValueError('Technical-note attachment boundary not found')
    last = starts[-1][2]+end_last.start()
    for index, (code,start,heading_end,page,label) in enumerate(starts):
        end = starts[index+1][1] if index+1 < len(starts) else last
        segments = []
        for left,right,pno in boundaries:
            a,b = max(start,left),min(end,right)
            if a < b:
                text = joined[a:b]
                segments.append({'pdf_page': pno, 'start': a-left, 'end': b-left, 'text': text,
                                 'sha256': hashlib.sha256(text.encode()).hexdigest()})
        result.append({'code':code,'heading_first_line':label,'segments':segments,
                       'interpretation':'Complete published definition retained; no personal clinical or quality-fit inference'})
    return result


def build(acquisition, out):
    if out.exists():
        raise ValueError('Use a new immutable build revision')
    sources = read(acquisition/'source-manifest.json')
    if sources['schema'] != 'l09-acquisition/1' or sources['year'] != 2026 or (acquisition/'SEALED').read_text().strip() != sha(acquisition/'source-manifest.json'):
        raise ValueError('Acquisition contract/seal changed')
    for s in sources['sources'].values():
        path = (ROOT/s['path']).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != s['sha256'] or path.stat().st_size != s['bytes']:
            raise ValueError('Source evidence changed')
    if sources['sources']['ratings']['sha256'] != ARCHIVE_SHA:
        raise ValueError('Inspected 2026 ratings revision changed')
    planning = read(BASE/'planning-r1/reuse-audit.json')
    for p in [MA,PDP,LAND]:
        if sha(p) != planning['input_sha256'][str(p)]:
            raise ValueError('Pinned upstream population/source changed')
    ma,pdp = read(MA),read(PDP)
    offerings = [{'offering_id':r['id'],'contract':r['contract'],'name':r['name'],
        'product':'MA-PD' if r['drug']=='Yes' else 'MA-only',
        'rating_type':'overall' if r['drug']=='Yes' else 'part_c_summary',
        'identity_source':str(MA.relative_to(ROOT)),'identity_ordinal':i,
        'scope':'Collier FL 12021','source_status':r['inventory'], 'restriction_source_raw':r['restriction_raw']}
        for i,r in enumerate(ma,1)]
    offerings += [{'offering_id':r['offering_id'],'contract':r['fields']['contract_id']['raw'].strip(),
        'name':r['fields']['plan_name']['raw'].strip(), 'product':'PDP','rating_type':'part_d_summary',
        'identity_source':str(PDP.relative_to(ROOT)),'identity_ordinal':i,
        'scope':'Florida PDP region 11; serves Collier','source_status':'published_reference_unaccepted',
        'restriction_source_raw':None} for i,r in enumerate(pdp,1)]
    offerings.sort(key=lambda r:r['offering_id'])
    if len(offerings)!=82 or len({r['offering_id'] for r in offerings})!=82:
        raise ValueError('Changed 82-offering denominator')
    wanted = {r['contract'] for r in offerings}
    if len(wanted)!=24:
        raise ValueError('Changed 24-contract denominator')
    out.mkdir(parents=True)
    write(out/'source-manifest.json', sources)
    documents = []
    tech = None
    for source_id,s in sorted(sources['sources'].items()):
        if s['content_type'].split(';')[0] == 'application/pdf':
            pages = pdf_pages(ROOT/s['path'])
            documents.append({'source_id':source_id,'sha256':s['sha256'],'pages':[
                {'pdf_page':i,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()} for i,text in enumerate(pages,1)]})
            if source_id=='technical_notes':
                tech = definitions(pages)
    if tech is None:
        raise ValueError('No technical definitions')
    write(out/'documents.json',documents)
    write(out/'measure-definitions.json',tech)
    archive_source = sources['sources']['ratings']
    observations, table_meta, source_rows, contexts, members = [], {}, [], [], []
    with zipfile.ZipFile(ROOT/archive_source['path']) as z:
        sm = next(n for n in z.namelist() if 'Summary Ratings' in n and n.endswith('.xlsx'))
        mm = next(n for n in z.namelist() if 'Report_Card_Master_Table' in n and n.endswith('.xlsx'))
        primary = workbook(z.read(sm))['Summary_Rating']
        master = workbook(z.read(mm))
        primary_contracts = {cells[1]['raw'].strip():(row,cells) for row,cells in primary.items() if row>2 and cells.get(1,{}).get('raw','').strip()}
        if not wanted <= primary_contracts.keys() or primary[1][1]['raw']!='2026 Summary Star View: Medicare Report Card Master Table':
            raise ValueError('Wrong rating year or missing source contract')
        for j,(code,label) in enumerate(SUMMARY,9):
            if primary[2][j]['raw']!=label:
                raise ValueError('Summary field/type changed')
        for c in sorted(wanted):
            row,cells = primary_contracts[c]
            source_rows.append({'table':'summary','contract':c,'row':row,'member':sm,
                'native_cells':{column(i):v['raw'] for i,v in cells.items()}})
            for j,(code,label) in enumerate(SUMMARY,9):
                raw=cells[j]['raw']
                observations.append({'id':f'2026:{c}:summary:{code}','contract':c,'rating_year':2026,
                    'kind':'summary','code':code,'label':label,'domain':None,'measurement_period_raw':None,
                    'measurement_period_basis':'Summary aggregates multiple measure-specific periods',
                    'raw':raw,**scalar(raw,'summary'),'source_member':sm,'source_member_sha256':hashlib.sha256(z.read(sm)).hexdigest(),
                    'source_row':row,'source_column':column(j),'source_worksheet':'Summary_Rating',
                    'source_header_rows':[1,2],'source_revision_label':'July 22 2026',
                    'definition_code':None,'companion_member':mm,'companion_worksheet':'Summary_Rating'})
        table_meta['summary']={'member':sm,'header_rows':{str(i):{column(j):v['raw'] for j,v in primary[i].items()} for i in [1,2]},
            'national_contract_rows':len(primary_contracts),'target_contract_rows':len(wanted),
            'outside_scope_contract_rows':len(primary_contracts)-len(wanted),'fields_per_contract':3}
        for kind,label,sheet,start in [('measure_stars','Measure Stars','Measure_Stars',4),('measure_data','Measure Data','Measure_Data',4),('domain','Domain Stars','Domain_Stars',2)]:
            member = next(n for n in z.namelist() if label in n and n.endswith('.csv'))
            rows,encoding = csv_rows(z.read(member))
            if not rows[0][0].startswith('2026 '):
                raise ValueError('Wrong detail rating year')
            width = 50 if start==4 else 14
            if any(len(r)!=width for r in rows):
                raise ValueError('Unexpected native column denominator')
            source={r[0].strip():(i,r) for i,r in enumerate(rows[start:],start+1) if r[0].strip()}
            if len(source)!=len(rows)-start or not wanted<=source.keys():
                raise ValueError('Missing/duplicate contract in detail table')
            headers=rows[2] if start==4 else rows[1]
            table_meta[kind]={'member':member,'encoding':encoding,'header_rows':{str(i+1):r for i,r in enumerate(rows[:start])},
                'national_contract_rows':len(source),'target_contract_rows':len(wanted),
                'outside_scope_contract_rows':len(source)-len(wanted),'fields_per_contract':width-5}
            domain=None
            for j in range(5,width):
                if rows[1][j].strip():
                    domain=rows[1][j]
                code=headers[j].split(':',1)[0]
                if not re.fullmatch(r'[CD]\d{2}' if start==4 else r'[HD]D[1-5]',code):
                    raise ValueError('Unexpected measure/domain code')
                for c in sorted(wanted):
                    row,values=source[c]
                    observations.append({'id':f'2026:{c}:{kind}:{code}','contract':c,'rating_year':2026,
                        'kind':kind,'code':code,'label':headers[j],'domain':domain if start==4 else headers[j],
                        'measurement_period_raw':rows[3][j] if start==4 else None,
                        'measurement_period_basis':'Native measure header' if start==4 else 'Domain aggregates multiple measure-specific periods',
                        'raw':values[j],**scalar(values[j],kind),'source_member':member,
                        'source_member_sha256':hashlib.sha256(z.read(member)).hexdigest(),
                        'source_row':row,'source_column':column(j+1),'source_worksheet':None,
                        'source_header_rows':list(range(1,start+1)),'source_revision_label':'Oct 8 2025',
                        'definition_code':code if start==4 else None,'companion_member':mm,'companion_worksheet':sheet})
            for c in sorted(wanted):
                row,values=source[c]
                source_rows.append({'table':kind,'contract':c,'row':row,'member':member,'native_cells':values})
        core={sm,mm,*[v['member'] for k,v in table_meta.items() if k!='summary']}
        for n in z.namelist():
            data=z.read(n)
            if n in core:
                disposition='rated_source' if n!=mm else 'whole_master_comparison_and_context'
            elif n.endswith('.csv'):
                disposition='retained_context_table'
                rows,encoding=csv_rows(data)
                cut='Cut Points' in n
                contexts.append({'member':n,'encoding':encoding,'use':'published_context_only_no_derived_rating_or_icon',
                    'rows':[{'row':i,'raw':r,'disposition':'header' if i<=2 else 'national_cutpoint_context' if cut else 'in_scope_contract' if r[0].strip() in wanted else 'outside_scope_contract'} for i,r in enumerate(rows,1)]})
            else:
                disposition='retained_PQA_identity_methodology_context_no_drug_coverage_assertion'
            members.append({'member':n,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'disposition':disposition})
    observations.sort(key=lambda r:r['id'])
    if len(observations)!=2448 or len({r['id'] for r in observations})!=2448:
        raise ValueError('Changed rating observation denominator')
    by_id={r['id']:r for r in observations}
    for r in offerings:
        r['primary_observation_id']=f"2026:{r['contract']}:summary:{r['rating_type']}"
        if r['primary_observation_id'] not in by_id:
            raise ValueError('Missing primary rating join')
    comparisons=[]
    identities={r['offering_id'] for r in offerings}
    with zipfile.ZipFile(LAND) as z:
        member=next(n for n in z.namelist() if n.endswith('.csv'))
        for ordinal,row in enumerate(csv.DictReader(io.TextIOWrapper(z.open(member),encoding='utf-8-sig')),2):
            oid=':'.join([row['Contract Year'].strip(),row['Contract ID'].strip(),row['Plan ID'].strip().zfill(3),row['Segment ID'].strip().zfill(3)])
            if oid not in identities or row['State Territory Abbreviation'].strip()!='FL' or (not row['Contract ID'].startswith('S') and row['County Name'].strip()!='Collier'):
                continue
            for (code,_),field in zip(SUMMARY,LAND_FIELDS):
                obs=by_id[f"2026:{row['Contract ID']}:summary:{code}"]
                a,b=scalar(row[field],'summary'),{k:obs[k] for k in ['state','value_decimal','unit']}
                comparisons.append({'offering_id':oid,'field':field,'observation_id':obs['id'],'source_member':member,
                    'source_row':ordinal,'landscape_raw':row[field],'rating_raw':obs['raw'],'agrees':a==b})
    if len(comparisons)!=246 or not all(r['agrees'] for r in comparisons):
        raise ValueError('Landscape/ratings mismatch requires an explicit new revision disposition')
    contracts=[{'contract':c,'rating_year':2026,'offering_ids':[r['offering_id'] for r in offerings if r['contract']==c]} for c in sorted(wanted)]
    for name,value in [('observations.json',observations),('offerings.json',offerings),('contracts.json',contracts),
                       ('source-members.json',members),('source-tables.json',table_meta),('contract-source-rows.json',source_rows),
                       ('context-tables.json',contexts),('landscape-comparisons.json',comparisons)]:
        write(out/name,value)
    con=sqlite3.connect(out/'inventory.sqlite3')
    con.executescript('CREATE TABLE observations(id TEXT PRIMARY KEY,contract TEXT,kind TEXT,code TEXT,state TEXT,value_decimal TEXT,unit TEXT,payload TEXT); CREATE INDEX observation_contract ON observations(contract,kind,code); CREATE TABLE offerings(offering_id TEXT PRIMARY KEY,contract TEXT,rating_type TEXT,primary_observation_id TEXT,payload TEXT); CREATE INDEX offering_contract ON offerings(contract); CREATE TABLE contracts(contract TEXT PRIMARY KEY,payload TEXT); CREATE TABLE definitions(code TEXT PRIMARY KEY,payload TEXT); CREATE TABLE context(member TEXT PRIMARY KEY,payload TEXT);')
    con.executemany('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?)',[(r['id'],r['contract'],r['kind'],r['code'],r['state'],r['value_decimal'],r['unit'],canonical(r)) for r in observations])
    con.executemany('INSERT INTO offerings VALUES(?,?,?,?,?)',[(r['offering_id'],r['contract'],r['rating_type'],r['primary_observation_id'],canonical(r)) for r in offerings])
    con.executemany('INSERT INTO contracts VALUES(?,?)',[(r['contract'],canonical(r)) for r in contracts])
    con.executemany('INSERT INTO definitions VALUES(?,?)',[(r['code'],canonical(r)) for r in tech])
    con.executemany('INSERT INTO context VALUES(?,?)',[(r['member'],canonical(r)) for r in contexts])
    con.commit();con.close()
    coverage={'schema':'l09-coverage/1','year':2026,'offerings':82,'contracts':24,'required_observations':2448,
        'observations_by_kind':dict(Counter(r['kind'] for r in observations)),
        'states_by_kind':{k:dict(Counter(r['state'] for r in observations if r['kind']==k)) for k in sorted({r['kind'] for r in observations})},
        'offering_rating_types':dict(Counter(r['rating_type'] for r in offerings)),
        'measure_definitions':len(tech),'archive_members':len(members),'source_row_accounting':table_meta,
        'landscape_fields_compared':len(comparisons),'missing_contracts':[],'missing_offerings':[],
        'consumer_release_enabled':False,'personal_fit_implemented':False,'human_acceptance':None}
    write(out/'coverage.json',coverage)
    write(out/'scope.json',{'year':2026,'MA_county_fips':'12021','MA_state':'FL','PDP_region':'11','PDP_state':'FL',
        'scope':'Published contract quality for every exact pinned MA/PDP offering; no personal quality or fit determination',
        'summary_revision':'2026-07-22','detail_filename_date':'2025-10-08','archive_HTTP_last_modified':archive_source['last_modified'],
        'separate_display_measures':'Outside rated-measure scope; not missing stars', 'required_observation_ids':[r['id'] for r in observations]})
    write(out/'gaps.json',{'missing_published_source_rows':[],'unexplained_comparison_conflicts':[],
        'official_missing_states':'Preserved published evidence states, not acquisition failures or zero quality',
        'pending':[{'id':'R14','owner':'Independent scoped Medicare quality reviewer','action':'Review the exact summary/measure labels, periods, source-message mapping and limitations; accept or reject this exact revision','closure':'Genuine named dated exact-manifest review receipt'},
                   {'id':'G02','owner':'Source-use reviewer','action':'Confirm allowed consumer caching/redisplay including retained PQA context; no click acceptance was performed','closure':'Exact source/use/scope decision'},
                   {'id':'G06','owner':'Recommendation release owner','action':'Keep independent cross-layer recommendation gate held','closure':'Separate accepted capability and independence evidence'}],
        'limits':['Contract-level quality is not exact doctor/site participation or personal fit.',
                  'Retained contextual tables and PQA value sets do not establish drug coverage or permissions.',
                  'Publication dates, rating year, measurement periods and bonus-payment contexts are distinct.',
                  'Non-percent measure units and clinical definitions remain in full source-linked metric text; no derived costs, clinical rules or metric rescaling is implemented.']})
    prior=read(BASE/'planning-r1/scope-offerings.json')
    if {r['id'] for r in prior}!={r['offering_id'] for r in offerings}:
        raise ValueError('Planning/current population drift')
    write(out/'refresh-diff.json',{'baseline':'planning-r1 source inspection; not an accepted release','added_offerings':[],
        'removed_offerings':[],'summary_value_changes':[],'new_normalized_observations':2448,
        'future_refresh':'New immutable source/build and per-ID before/after diff required; never overwrite reviewed data'})
    (out/'code').mkdir()
    code_hashes={}
    for name in CODE:
        source=ROOT/'cms-slice/scripts'/name
        shutil.copy2(source,out/'code'/name)
        code_hashes[str(source.relative_to(ROOT))]=sha(source)
    inputs={str(p.relative_to(ROOT)):sha(p) for p in [MA,PDP,LAND,BASE/'planning-r1/assessment-manifest.json',acquisition/'source-manifest.json',acquisition/'SEALED']}
    files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    manifest={'schema':'l09-build/1','package_id':'L09-PUBLISHED-COLLIER-FL-2026-'+out.name,'year':2026,
        'files_sha256':files,'input_sha256':inputs,'code_sha256':code_hashes,
        'source_manifest_path':str((acquisition/'source-manifest.json').relative_to(ROOT)),
        'archive_sha256':ARCHIVE_SHA,'source_review_after_utc':sources['source_review_after_utc'],
        'required_observations':2448,'offerings':82,'contracts':24,'consumer_release_enabled':False,'human_acceptance':None}
    write(out/'manifest.json',manifest)
    (out/'SEALED').write_text(sha(out/'manifest.json')+'\n')
    print(json.dumps({'package':str(out),'observations':2448,'offerings':82,'contracts':24}))
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acquisition',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.acquisition.resolve(),a.out.resolve())
