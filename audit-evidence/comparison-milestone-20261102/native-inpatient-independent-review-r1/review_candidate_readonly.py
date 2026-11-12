"""Independent source/lineage replay; never call the producer authoring code."""
from pathlib import Path
import collections
import gzip
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=ROOT/'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
CAND=BASE/'native-inpatient-control-reconciliation-r1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fp(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
checks=0
def check(x,label):
    global checks
    assert x,label
    checks+=1
def resolve(x,pointer):
    for part in pointer.strip('/').split('/'):
        part=part.replace('~1','/').replace('~0','~')
        x=x[int(part)] if isinstance(x,list) else x[part]
    return x
for m in read(HERE/'EXPECTED_FREEZE_R1.json')['members']:
    check(sha(HERE/m['path'])==m['sha256'],'Expected source seal changed')
check(sha(CAND/'FREEZE_R1.json')=='921904149c53c4841a7e6c4910db7836fabe4349401f33cfa4a2b7aabc8b4992','Exact candidate freeze')
for m in read(CAND/'FREEZE_R1.json')['members']:
    check(sha(CAND/m['path'])==m['sha256'] and (CAND/m['path']).stat().st_size==m['bytes'],'Frozen candidate member')
for m in read(CAND/'INPUT_BINDINGS.json')['files']:
    check(sha(ROOT/m['path'])==m['sha256'] and (ROOT/m['path']).stat().st_size==m['bytes'],'Exact source input: '+m['path'])
expected=read(HERE/'SOURCE_CONTROL_CENSUS_EXPECTED.json')
expected_records={x['pointer']:x for x in expected['controls']+expected['descriptors']}
native_path=ROOT/'docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/generated-r2/CMS-native-member.json'
native=read(native_path)
original_path=native_path.parent/'offering-canonical.jsonl.gz'
originals={x['id']:x for x in map(json.loads,gzip.decompress(original_path.read_bytes()).decode().splitlines())}
rows=read(CAND/'CONTROL_COMPARISONS.json')['records']
check(len(rows)==208 and len({r['pointer'] for r in rows})==208,'Exact unique source leaf count')
check({r['pointer'] for r in rows}==set(expected_records),'All and only original leaves')
prior={x['pointer']:x for x in read(HERE/'PRIOR_EXACT_AUTHORITY_EXPECTED.json')['records']}
decisions={}
for r in rows:
    p=r['pointer'];raw=resolve(native,p)
    check(r['raw']==raw and type(r['raw']) is type(raw),'Exact raw/type: '+p)
    check(r['raw_JSON_type']==type(raw).__name__ and r['raw_sha256_canonical_JSON']==fp(raw),'Typed raw hash: '+p)
    parent=resolve(native,r['immediate_parent_pointer'])
    whole=resolve(native,r['whole_object_pointer'])
    check(fp(parent)==r['immediate_parent_sha256'] and fp(whole)==r['whole_object_sha256'],'Exact whole/parent: '+p)
    check(r['categoryCode']==whole['categoryCode'] and r['categoryTypeId']==whole['categoryTypeId'],'Category/type local: '+p)
    check(r['accepted_for_reference'] is False and r['complete_meaning_agreement'] is False and r['new_native_global_label'] is None,'No source promotion: '+p)
    check(bool(r['next_action'].strip()) and bool(r['source_specific_meaning'].strip()),'Concrete meaning and next action: '+p)
    for b in r['original_ID_bindings']:
        check(fp(originals[b['id']])==b['canonical_record_sha256'],'Exact original payload: '+p)
        check(originals[b['id']]['kind']==b['kind'] and originals[b['id']]['states']==b['states'],'Original kind/state: '+p)
    if p not in prior:
        want='source_identity_descriptor' if p in {x['pointer'] for x in expected['descriptors']} else 'blank_retained_no_negative_inference'
        check(r['decision']==want,'Blank/descriptor not decoded: '+p)
    else:
        old=prior[p]
        check(any(v['verdict']==old['format_evidence_verdict'] for v in r['previous_format_decision_refs']),'Prior exact authority: '+p)
        if old['format_evidence_verdict']=='exact_named_control_retained_label_unresolved':
            check(r['decision']=='selector_hold','Selector remains held: '+p)
        elif old['format_evidence_verdict']=='literal_retained_without_new_enum_inference':
            check(r['decision'] in ['literal_cardinality_only','literal_operand_only'],'Literal remains bounded: '+p)
        else:
            check(r['decision'].startswith('scoped_'),'Scoped source-format projection: '+p)
    decisions[p]={'control_id':r['control_id'],'raw':raw,'decision':r['decision'],'expected_source_class':prior.get(p,{}).get('format_evidence_verdict','blank_or_descriptor'),'original_bindings':len(r['original_ID_bindings']),'review':'supported within source-format/context bounds; no full benefit equivalence'}

# Replay every quoted SAS branch, ordinal-join context and target/MAX source line.
sasdir=BASE/'native-format-authority-research-r1/extracted-cms-code'
branches=read(CAND/'SCOPED_SAS_BRANCHES.json')['branches']
check(len(branches)==137 and len({b['evidence_id'] for b in branches})==137,'Exact branch IDs')
branchids={b['evidence_id'] for b in branches}
for b in branches:
    source=sasdir/Path(b['source_file']).name
    lines=source.read_text().splitlines()
    check(sha(source)==b['module_sha256'],'Original SAS module')
    text='\n'.join(lines[b['start_line']-1:b['end_line']]).strip()
    # The expression ends before its SQL list separator; physical line bounds
    # retain that comma. Permit only this explicit trailing separator difference.
    check(text.removesuffix(',')==b['literal_source'].strip(),'Exact guarded SAS source: '+b['evidence_id'])
    check(re.sub(r'\s+','',b['literal_guard']) in re.sub(r'\s+','',text),'Exact source guard')
    check(b['enum_meaning_assigned'] is False and b['global_mapping_authority'] is False,'No universal SAS mapping')
    context=b['complete_join_context'];src=ROOT/context['path']
    check(sha(src)==context['sha256'],'Join source hash')
    check('\n'.join(src.read_text().splitlines()[context['first_line']-1:context['last_line']])==context['source'],'Full ordinal join text')
    for occurrence in b['intermediate_target_all_literal_occurrences']+b['per_QID_MAX_source']:
        check(lines[occurrence['line']-1]==occurrence['source'],'Exact MAX/target source occurrence')
    for v in b['current_exact_native_inputs']:
        check(v['pointer'] in expected_records and resolve(native,v['pointer'])==v['raw'],'Local current branch input')
for r in rows:check(set(r['applicable_source_branch_ids'])<=branchids,'Control branch reference exists')

# Independently parse the original TSV and original XLSX cells, not producer code.
tables=ROOT/'docs/data/l03-ma-benefits-2026-10-25/acquisition-r1/tables'
rawlines=(tables/'pbp_b1a_inpat_hosp.txt').read_bytes().splitlines(keepends=True)
header=rawlines[0].decode('utf-8-sig').rstrip('\r\n').split('\t')
values=rawlines[5583].decode('utf-8-sig').rstrip('\r\n').split('\t')
flat=dict(zip(header,values,strict=True))
check((flat['pbp_a_hnumber'],flat['pbp_a_plan_identifier'],flat['segment_id'])==('H5652','002','0'),'Exact original flat identity')
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(tables/'PBP_Benefits_2026_dictionary.xlsx') as z:
    strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
    # itertext is exact here because this dictionary's shared strings are plain text.
    cells={}
    for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//s:row',ns):
        rc={}
        for c in row.findall('s:c',ns):
            col=re.match('[A-Z]+',c.attrib['r']).group()
            v=c.find('s:v',ns);value='' if v is None else (v.text or '')
            if c.attrib.get('t')=='s':value=strings[int(value)]
            elif c.attrib.get('t')=='inlineStr':value=''.join(c.itertext())
            rc[col]=value
        cells[int(row.attrib['r'])]=rc
questions=read(CAND/'EXACT_FLAT_INPATIENT_QUESTIONS.json')['fields']
check(len(questions)==300 and {x['field'] for x in questions}==set(flat),'All original flat fields')
for q in questions:
    check(q['raw']==flat[q['field']],'Exact flat value: '+q['field'])
    for d in q['original_dictionary_cells']:
        actual={c:cells[d['row']].get(c,'') for c in 'ABCDEFGHIJK'}
        check(d['cells']==actual,'Original XLSX cells: '+str(d['row']))
    check(q['locator']['raw_line_with_terminator_sha256']==hashlib.sha256(rawlines[5583]).hexdigest(),'Exact flat raw row hash')
    source_rows=[d['cells'] for d in q['original_dictionary_cells']]
    codebook={c['I']:c['J'] for c in source_rows if c['I'] and c['J']}
    check(q['codebook']==codebook,'Original codebook pairs: '+q['field'])
    check(q['flat_codebook_label']==codebook.get(q['raw']),'No cross-format flat label transfer')
holds=read(CAND/'HOLD_REGISTER.json')['held_records']
check(len(holds)==17,'Exact held questions')
for h in holds:
    check(h['pointer'] in expected_records and h['raw']==resolve(native,h['pointer']),'Held exact source path/raw')
    check(h['specific_question'] and h['next_action'] and not h['external_blocker_established'],'Unfinished internal action remains')
w=read(CAND/'WORKBOOK_SCOPE_REVIEW.json')
check(w['exact_34_followup_candidate_pointer_matches']==[],'No wrong-path follow-up reuse')
with zipfile.ZipFile(ROOT/w['workbook_path']) as z:
    strings=[''.join(t.text or '' for t in x.findall('.//s:t',ns)) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
    xml=z.read(w['primary_workbook_XML_replay']['workbook_member'])
    check(hashlib.sha256(xml).hexdigest()==w['primary_workbook_XML_replay']['member_sha256'],'Primary hidden workbook XML')
    actual_cells={}
    for row in ET.fromstring(xml).findall('.//s:row',ns):
        rc={}
        for c in row.findall('s:c',ns):
            col=re.match('[A-Z]+',c.attrib['r']).group();v=c.find('s:v',ns);f=c.find('s:f',ns)
            value=None if v is None else v.text
            if c.attrib.get('t')=='s':value=strings[int(value)]
            rc[col]={'value':value,'formula':None if f is None else f.text}
        actual_cells[int(row.attrib['r'])]=rc
    for row in w['exact_specs']:
        for col,c in row['cells'].items():
            check(actual_cells[row['row']][col]=={k:c[k] for k in ('value','formula')},'Exact workbook rule cell')
vba=w['FFS_capture_source'];vba_path=ROOT/vba['path']
check(sha(vba_path)==vba['sha256'],'Original VBA source')
check('\n'.join(vba_path.read_text().splitlines()[vba['first_line']-1:vba['last_line']])==vba['source'],'Complete VBA guard/first-property block')
for selection in w['conditional_actual_selection']:
    check(resolve(native,selection['selected_pointer'])==selection['raw'],'Exact conditional workbook operand')
    check(selection['categoryTypeId_guard_present'] is False,'No invented workbook type guard')
account=read(CAND/'ACCOUNTING.json')
check(not account['whole_offering_complete'] and account['new_acceptance']==0 and account['new_original_obligations']==0,'No new original/adoption/acceptance')
result={'schema':'daylight.native-inpatient.independent-replay.r1','checks_passed':checks,
    'control_decisions':decisions,'decision_counts':dict(collections.Counter(r['decision'] for r in rows)),
    'exact_flat_questions_replayed':len(questions),'exact_SAS_branches_replayed':len(branches),
    'candidate_sha256':sha(CAND/'FREEZE_R1.json'),'confirmed_findings':[],
    'scope':'Source-format and preservation replay, not full factual or carrier/native benefit equivalence.',
    'new_acceptance':False,'database_or_app_write':False}
print(json.dumps(result,ensure_ascii=False,indent=2))
