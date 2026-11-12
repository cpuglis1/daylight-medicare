"""Build an additive L11 published-reference reconciliation; preserve sealed r1."""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess

import l11_r2_catalog as catalog
from l11_seal import verify as verify_parent

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l11-medigap-rights-2026-10-28'
ACQ = BASE / 'acquisition-r2'
PARENT = BASE / 'build-r1'
BUILD = BASE / 'build-r2'


def load(p): return json.loads(Path(p).read_text())
def norm(s): return ' '.join(s.split())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p, obj): Path(p).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def select(selector, units):
    if selector in units:
        # Include all actual descendants and continuation clauses of a root.
        prefix = '.' if selector.startswith(('FAC:', 'CFR')) else '-'
        return [k for k in units if k == selector or k.startswith(selector + prefix) or k.startswith(selector + '~')]
    matches = [k for k in units if k.startswith(selector + '.') or k.startswith(selector + '-')]
    if not matches: raise ValueError('Unresolved source selector ' + selector)
    return matches


def source_units():
    units = {u['id']: u for u in load(PARENT / 'source-clause-ledger.json')}
    sources = load(PARENT / 'sources.json')
    for sid, prefix, count in [('cms-2026-enrollment','ENROLL',145),
                               ('cms-2026-ma-exhibits','EXHIBIT',159),
                               ('fl-law-2016-194','LAW2016',28)]:
        receipt = ACQ / (sid + '.json'); r = load(receipt)
        if r['status'] != 'retained_pdf' or sha(ROOT / r['path']) != r['sha256']:
            raise ValueError('Changed source')
        text = subprocess.run(['pdftotext','-layout',str(ROOT / r['path']),'-'],
                              check=True, capture_output=True).stdout.decode()
        pages = text.split('\f')
        if pages[-1].strip() or len(pages)-1 != count: raise ValueError('PDF page accounting')
        output = ACQ / 'text' / (sid + '.txt')
        if output.read_text() != text: raise ValueError('Retained text differs from fresh extraction')
        sources[sid] = {**r, 'receipt_path':str(receipt.relative_to(ROOT)),
                        'text_path':str(output.relative_to(ROOT)), 'page_count':count}
        for i, page in enumerate(pages[:-1], 1):
            key = f'{prefix}:{i}'
            units[key] = {'id':key, 'source_id':sid, 'locator':{'pdf_page_one_based':i},
                          'text':norm(page), 'parent_anchor':None, 'rule_ids':[],
                          'disposition':'retained_context', 'reason':'Complete new-source page accounting; only linked pages support the reconciliation.'}
    # This is an official public web-tool extraction, not origin HTML. Preserve
    # exact source line numbers and the full unedited tool capture/provenance.
    capture = ACQ / 'web-statute-history.txt'
    section = capture.read_text().split('--------------------------------------------------------------------------------')[0]
    old = {}
    for line in section.splitlines():
        m = re.match(r'^L(\d+): (.*)$', line)
        if m and 177 <= int(m[1]) <= 225 and m[2].strip():
            old[int(m[1])] = norm(m[2])
    if not all(i in old for i in [177,179,194,196,224,225]):
        raise ValueError('Historical definition capture incomplete')
    sources['fl-creditable-2015-web'] = {
        'source_id':'fl-creditable-2015-web',
        'url':'https://www.flsenate.gov/Laws/Statutes/2015/627.6561',
        'status':'official_public_web_extraction_not_origin_html',
        'path':str(capture.relative_to(ROOT)), 'sha256':sha(capture),
        'scope':'Historical definition subsection (5) and neighboring old group-plan subsection (6)(a); not current authority.',
        'origin_tool_reference':'turn231view0', 'captured_on':'2026-10-28',
    }
    for i, text in old.items():
        key = f'FL2015:L{i}'
        units[key] = {'id':key,'source_id':'fl-creditable-2015-web',
                      'locator':{'original_web_line':i},'text':text,'parent_anchor':None,
                      'rule_ids':[],'disposition':'retained_context','reason':'Historical relocation comparison only.'}
    return units, sources


def guidance_section(number, units):
    if not number: return []
    # Source-wide search misses nothing but takes the LAST start, avoiding TOC
    # entries. Retain complete bounding pages, including split paragraphs.
    hits=[]
    pattern = re.compile(r'(?:^|\s)' + re.escape(number) + r'\s+[–-]\s+')
    for i in range(1,146):
        if pattern.search(units[f'ENROLL:{i}']['text']): hits.append(i)
    if not hits: raise ValueError('Guidance section missing ' + number)
    start=hits[-1]
    next_number='30.6.'+str(int(number.rsplit('.',1)[1])+1)
    end=start
    for i in range(start,146):
        t=units[f'ENROLL:{i}']['text']
        if (next_number+' –') in t or (number=='30.6.36' and '30.7 –' in t):
            end=i;break
    else:raise ValueError('Unbounded guidance section')
    return [f'ENROLL:{i}' for i in range(start,end+1)]


def make_sep(units):
    rows=[]
    listed = {r[2]:r for r in catalog.EXHIBIT_ROWS if r[2] is not None}
    for n in range(1,28):
        selectors=[f'CFRJAN:b.{n}', 'MA:e-4', 'USC:s-3-B-ii', 'USC:s-3-A']
        ids=[k for s in selectors for k in select(s,units)]
        section=catalog.SEP_SECTIONS[n]
        ids += guidance_section(section, units)
        if n in listed: ids += ['EXHIBIT:123','EXHIBIT:124']
        if n in [11,13,22,25]:
            status='named_interpretation_review'; questions=['Q03']
        elif n==26:
            status='listed_but_entry_direction_mismatch'; questions=['Q04']
        elif n in listed:
            status='CMS_expressly_listed_conditional_route';questions=[]
        else:
            status='historical_or_enrollment_scope_no_automatic_MA_exit_right';questions=[]
        rows.append({'id':f'SEP{n:02}', 'paragraph':f'422.62(b)({n})',
                     'guidance_section':section,'exhibit_24_listed':n in listed,
                     'classification':status,'review_question_ids':questions,
                     'meaning':catalog.SEP_NOTES[n], 'source_clause_ids':sorted(set(ids)),
                     'individual_determination':False, 'absence_from_exhibit_is_no_right_finding':False,
                     'federal_MA_route_common_conditions':['age_65_or_older','valid_first_sentence_1851_e_4_discontinuance',
                         'Original_Medicare_destination','timely_application_and_evidence','eligible_policy_offered'],
                     'consumer_release_enabled':False})
    return rows


def make_credit(units):
    rows=[]
    for i,(group,title,current,old) in enumerate(catalog.CREDIT_LINES,1):
        a=f'FS:627.6562:L{current}';b=f'FL2015:L{old}'
        parent={'included':165,'excepted':184,'separately_offered':200,
                'independent_noncoordinated':207,'separate_supplemental_policy':212}[group]
        old_parent={'included':177,'excepted':196,'separately_offered':212,
                    'independent_noncoordinated':219,'separate_supplemental_policy':224}[group]
        rows.append({'id':f'CC{i:02}','title':title,'category':group,
                     'current_clause_id':a, 'current_text':units[a]['text'],
                     'current_parent_clause_id':f'FS:627.6562:L{parent}',
                     'current_parent_text':units[f'FS:627.6562:L{parent}']['text'],
                     'historical_clause_id':b, 'historical_text':units[b]['text'],
                     'historical_parent_clause_id':f'FL2015:L{old_parent}',
                     'historical_parent_text':units[f'FL2015:L{old_parent}']['text'],
                     'literal_text_identical':units[a]['text']==units[b]['text'],
                     'comparison':'Same named category retained; current wording and all parent qualifiers govern. No claim of identical legal wording.',
                     'automatic_personal_credit_enabled':False})
    return rows


def build():
    parent_check=verify_parent(PARENT/'manifest.json')
    if BUILD.exists(): raise ValueError('Use a new build directory; never overwrite a revision')
    BUILD.mkdir();(BUILD/'code').mkdir()
    units,sources=source_units()
    findings=[]
    for rid,title,status,meaning,selectors,rule_ids in catalog.RECONCILIATIONS:
        ids=sorted(set(k for s in selectors for k in select(s,units)))
        findings.append({'id':rid,'title':title,'status':status,'meaning':meaning,
                         'source_clause_ids':ids, 'rule_ids':rule_ids,
                         'comparison_actor':'AI source comparison; independent qualified R16 pending',
                         'qualified_review':None,'consumer_release_enabled':False})
    sep=make_sep(units);credit=make_credit(units)
    questions=[{'id':i,'title':t,'historical_gap_ids':g,'rule_ids':r,
                'requested_decision':q,'why_review_remains':why,'reviewer':None,'decision':None}
               for i,t,g,r,q,why in catalog.REVIEW_QUESTIONS]
    rows=[]
    for printed,actual,n,title in catalog.EXHIBIT_ROWS:
        rows.append({'id':f'E{len(rows)+1:02}', 'printed_section':printed,'operative_section':actual,
                     'regulation_paragraph':f'422.62(b)({n})' if n else '1851(e)(4) second sentence / SEP65',
                     'title_anchor':title,'section_number_differs':printed!=actual,
                     'source_clause_ids':['EXHIBIT:123','EXHIBIT:124']+guidance_section(actual,units)})
    gaps=[]
    for g in load(PARENT/'gaps.json'):
        gid=g['id']
        status={'G01':'open_precise_interpretation','G02':'open_nonstandard_case_interpretation',
                'G03':'closed_source_reconciliation','G04':'closed_source_reconciliation',
                'G05':'source_reconciled_named_R16_confirmation','G06':'closed_source_reconciliation',
                'G07':'outside_required_statutory_reference_case_evidence_only',
                'G08':'independent_review_and_exact_acceptance_pending',
                'G09':'narrowed_to_five_named_paragraphs'}[gid]
        gaps.append({'id':gid,'previous_title':g['title'],'r1_preserved':True,'r2_disposition':status,
                     'review_question_ids':[q['id'] for q in questions if gid in q['historical_gap_ids']],
                     'new_bulk_data_required_for_statutory_reference':False})
    rules=load(PARENT/'rules.json')
    for r in rules:
        r['historical_r1_hold_ids']=r.pop('hold_ids')
        r['hold_ids']=[q['id'] for q in questions if r['id'] in q['rule_ids'] and q['id']!='Q06']
        r['r2_reconciliation_ids']=[f['id'] for f in findings if r['id'] in f['rule_ids']]
        r['r2_qualified_R16_pending']=True
    parent_ids={u['id'] for u in load(PARENT/'source-clause-ledger.json')}
    for row in findings+sep+rows:
        for key in row['source_clause_ids']:
            if key not in units:raise ValueError('Dangling source clause '+key)
            if key not in parent_ids:
                units[key]['disposition']='linked_reconciliation_evidence'
    linked={v for r in credit for k,v in r.items() if k.endswith('clause_id')}
    for key in linked:
        if key.startswith('FL2015:'):units[key]['disposition']='linked_reconciliation_evidence'
    objects={'rules.json':rules,'source-clause-ledger.json':list(units.values()),'sources.json':sources,
             'reconciliations-r2.json':findings,'sep-crosswalk.json':sep,
             'creditable-category-comparisons.json':credit,'exhibit-24-crosswalk.json':rows,
             'review-questions.json':questions,'issue-dispositions.json':gaps}
    for name in ['clocks.json','policy-choices.json','temporal-reconciliation.json',
                 'quantity-comparisons.json','synthetic-predicate-patterns.json']:
        objects[name]=load(PARENT/name)
    before={'rights_records':51,'clocks':14,'source_units':len(load(PARENT/'source-clause-ledger.json')),
            'SEP_paragraphs':27,'generic_SEP_holds':19}
    after={'rights_records':len(rules),'clocks':len(objects['clocks.json']),'source_units':len(units),
           'SEP_paragraphs':len(sep),'generic_SEP_holds':0,
           'named_SEP_interpretation_holds':sum(bool(s['review_question_ids']) for s in sep),
           'new_sources':4,'new_PDF_pages':332,'creditable_category_comparisons':len(credit),
           'reconciliation_findings':len(findings),'exhibit_rows':len(rows)}
    objects['before-after.json']={'before':before,'after':after,
          'added_source_unit_ids':sorted(set(units)-{u['id'] for u in load(PARENT/'source-clause-ledger.json')}),
          'removed_source_unit_ids':[], 'newly_accepted_fields':0,
          'base_meanings_and_source_conditions_preserved':True,
          'counts_are_not_counts_of_unique_rights_or_verified_facts':True}
    objects['parent-reference.json']={'path':str(PARENT.relative_to(ROOT)),
                 'manifest_sha256':parent_check['manifest_sha256'],
                 'source_scope':'Published 2026 federal/Florida Medigap rights for the Collier MVP',
                 'parent_acceptance_inherited':False}
    objects['summary.json']={'schema':'l11-research-reference/2','reference_year':2026,
             'reference_date':'2026-10-28','reference_id':'L11-PUBLISHED-FL-2026-research-r2',
             **after,'research_only':True,'full_l11_complete':False,
             'consumer_release_enabled':False,'human_acceptance':None,'qualified_R16_review':None,
             'personal_applicability_enabled':False,
             'normalization_scope':'Source-clause reference and additive issue reconciliation, not an accepted executable personal legal model.'}
    objects['review-coverage.json']={'requirements':['D64','D73'],
          'consumer_task':'More precise published buying-right reference; no UI or personal result introduced.',
          'independence':'No commercial fields, carrier incentives, ranking or revenue used.',
          'reported_vs_verified':'No beneficiary data; source comparisons and synthetic examples are distinct from personal applicability.',
          'permission_and_storage':'Only public sources retained; both variants and guest stores untouched.',
          'proof':'Source fidelity, exact storage parity and boundary tests; qualified review and acceptance still pending.'}
    for name,obj in objects.items():write(BUILD/name,obj)
    with closing(sqlite3.connect(BUILD/'l11-reference.sqlite')) as db:
        db.execute('CREATE TABLE records (dataset TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(dataset,id))')
        for dataset, records in objects.items():
            if isinstance(records,list):
                for i,row in enumerate(records):
                    key=str(row.get('id',i)) if isinstance(row,dict) else str(i)
                    db.execute('INSERT INTO records VALUES (?,?,?)',(dataset,key,json.dumps(row,sort_keys=True)))
        db.commit()
    for name in ['l11_r2_acquire.py','l11_r2_catalog.py','l11_r2_build.py','l11_r2_validate.py','l11_r2_seal.py']:
        shutil.copyfile(ROOT/'cms-slice/scripts'/name,BUILD/'code'/name)
    shutil.copyfile(ROOT/'cms-slice/tests/test_l11_r2_reference.py',BUILD/'code/test_l11_r2_reference.py')
    print(json.dumps(objects['summary.json'],indent=2))


if __name__=='__main__':build()
