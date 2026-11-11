"""Independent source/storage and consequential boundary checks for L11 r2.

These checks establish fidelity and bounded source comparisons, not qualified
legal approval, a complete executable legal model or personal eligibility.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess

import l11_validate as baseline
from l11_seal import verify as verify_seal

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l11-medigap-rights-2026-10-28'
PARENT=BASE/'build-r1'
BUILD=BASE/'build-r2'
ACQ=BASE/'acquisition-r2'


def load(path):return json.loads(Path(path).read_text())
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def norm(text):return ' '.join(text.split())


def continuity_boundary(uncovered_days, *, synthetic=False, threshold=63):
    """An arithmetic example for the literal source boundary only."""
    if not synthetic:raise ValueError('Personal applicability is disabled')
    if uncovered_days is None:return None
    if type(uncovered_days) is not int or uncovered_days<0:raise ValueError('Invalid synthetic gap')
    return uncovered_days<=threshold


def verify_storage(build, datasets):
    errors=[];count=0
    expected={}
    for name,records in datasets.items():
        if isinstance(records,list):
            for i,row in enumerate(records):
                key=str(row.get('id',i)) if isinstance(row,dict) else str(i)
                expected[(name,key)]=row
    with closing(sqlite3.connect(f'file:{build / "l11-reference.sqlite"}?mode=ro',uri=True)) as db:
        actual={(ds,k):json.loads(payload) for ds,k,payload in db.execute('SELECT dataset,id,payload FROM records')}
    if actual.keys()!=expected.keys():errors.append('SQLite key coverage differs')
    for key,row in expected.items():
        if actual.get(key)!=row:errors.append('SQLite full-field mismatch '+str(key))
        count+=1
    return errors,count


def validate(build=BUILD):
    errors=[]
    def check(ok,why):
        if not ok:errors.append(why)
    parent=verify_seal(PARENT/'manifest.json')
    check(load(build/'parent-reference.json')['manifest_sha256']==parent['manifest_sha256'],'Parent manifest identity')
    # Re-run original independent raw-source and field validator on the sealed
    # parent; new findings do not quietly weaken any baseline check.
    prior=baseline.validate(PARENT)
    check(prior['status']=='passed','Parent full source validation')
    datasets={p.name:load(p) for p in build.glob('*.json') if p.name not in ['validation.json','tests-result.json','manifest.json']}
    rules=datasets['rules.json'];units=datasets['source-clause-ledger.json'];byid={u['id']:u for u in units}
    sources=datasets['sources.json'];sep=datasets['sep-crosswalk.json'];credit=datasets['creditable-category-comparisons.json']
    check(len(byid)==len(units),'Duplicate source-unit identity')
    parent_units=load(PARENT/'source-clause-ledger.json')
    for u in parent_units:
        check(byid.get(u['id'])==u,'Changed inherited source unit '+u['id'])
    parent_rules={r['id']:r for r in load(PARENT/'rules.json')}
    check(set(parent_rules)=={r['id'] for r in rules},'Changed base right-record inventory')
    for r in rules:
        for k,value in parent_rules[r['id']].items():
            if k!='hold_ids':check(r.get(k)==value,'Changed inherited right field '+r['id']+'.'+k)
        check(r.get('historical_r1_hold_ids')==parent_rules[r['id']]['hold_ids'],'Lost historical hold accounting')
    for name in ['clocks.json','policy-choices.json','quantity-comparisons.json',
                 'temporal-reconciliation.json','synthetic-predicate-patterns.json']:
        check(datasets[name]==load(PARENT/name),'Changed inherited '+name)
    page_counts={'cms-2026-enrollment':('ENROLL',145),'cms-2026-ma-exhibits':('EXHIBIT',159),
                 'fl-law-2016-194':('LAW2016',28)}
    new_ids=set();fresh_texts={}
    for sid,(prefix,pages) in page_counts.items():
        s=sources[sid];receipt=load(ROOT/s['receipt_path'])
        check(receipt['sha256']==s['sha256']==digest(ROOT/s['path']),'New source hash '+sid)
        check(receipt['bytes']==(ROOT/s['path']).stat().st_size,'Source byte count '+sid)
        check((ROOT/s['path']).read_bytes().startswith(b'%PDF'),'Expected public PDF '+sid)
        # Fresh extraction from bytes, not the derived text file or build output.
        fresh=subprocess.run(['pdftotext','-layout',str(ROOT/s['path']),'-'],check=True,capture_output=True).stdout.decode()
        check(fresh==(ROOT/s['text_path']).read_text(),'Retained new extraction '+sid)
        parts=fresh.split('\f');check(len(parts)-1==pages and not parts[-1].strip(),'Complete page accounting '+sid)
        for i,text in enumerate(parts[:-1],1):
            key=f'{prefix}:{i}';new_ids.add(key);fresh_texts[key]=norm(text)
            u=byid.get(key,{})
            check(u.get('text')==norm(text) and u.get('source_id')==sid and u.get('locator')=={'pdf_page_one_based':i},'Fresh PDF source/locator mismatch '+key)
    history_source=sources['fl-creditable-2015-web']
    check(digest(ROOT/history_source['path'])==history_source['sha256'],'Historical capture hash')
    old_section=(ROOT/history_source['path']).read_text().split('--------------------------------------------------------------------------------')[0]
    historical_lines={int(m[1]):norm(m[2]) for m in re.finditer(r'^L(\d+): (.+)$',old_section,re.M)
                      if 177<=int(m[1])<=225 and m[2].strip()}
    for line,text in historical_lines.items():
        key=f'FL2015:L{line}';new_ids.add(key)
        check(byid.get(key,{}).get('text')==text and byid.get(key,{}).get('locator')=={'original_web_line':line},'Historical clause fidelity '+key)
    check(set(byid)=={u['id'] for u in parent_units}|new_ids,'Exact before/after source denominator')
    # Full 27-paragraph census and exact source subtree relationships, with
    # independent expected classifications rather than a copied generated set.
    check({s['paragraph'] for s in sep}=={f'422.62(b)({i})' for i in range(1,28)} and len(sep)==27,'All 27 SEP paragraphs')
    listed={1,2,3,4,5,6,7,8,14,17,18,20,21,23,24,26,27}
    named={11,13,22,25,26}
    for row in sep:
        n=int(re.search(r'\((\d+)\)$',row['paragraph'])[1]);prefix=f'CFRJAN:b.{n}'
        expected={k for k in byid if k==prefix or k.startswith(prefix+'.')}
        check(expected<=set(row['source_clause_ids']),'Dropped SEP qualifier '+str(n))
        check(row['exhibit_24_listed']==(n in listed),'Incorrect Exhibit join '+str(n))
        check(bool(row['review_question_ids'])==(n in named),'Named SEP hold disappeared or broadened '+str(n))
        if n in listed-named:check(row['classification']=='CMS_expressly_listed_conditional_route','Listed conditional SEP classification '+str(n))
        if n not in listed|named:check(row['classification']=='historical_or_enrollment_scope_no_automatic_MA_exit_right','Enrollment/historical scope '+str(n))
        check(row['individual_determination'] is False and row['absence_from_exhibit_is_no_right_finding'] is False,'Personal/negative inference guard '+str(n))
        check(set(row['federal_MA_route_common_conditions'])=={'age_65_or_older','valid_first_sentence_1851_e_4_discontinuance','Original_Medicare_destination','timely_application_and_evidence','eligible_policy_offered'},'Common MA conditions '+str(n))
    exhibit=datasets['exhibit-24-crosswalk.json']
    check(len(exhibit)==18,'Exhibit 24 exact 18-row inventory')
    text=fresh_texts['EXHIBIT:123']+' '+fresh_texts['EXHIBIT:124']
    # Parse printed sections directly from the table boundaries; subsequent
    # narrative has no section references. This catches omissions/duplicates.
    table=text.split('List of Applicable MA SEPs (18):',1)[1].split('Other Medigap GI rights',1)[0]
    printed=re.findall(r'\(Section (30\.6\.\d+)\)',table)
    check(Counter(printed)==Counter(x['printed_section'] for x in exhibit),'Exhibit raw printed-section census')
    for row in exhibit:
        check(row['title_anchor'].lower() in table.lower(),'Exhibit event title '+row['id'])
        if row['section_number_differs']:
            check((row['printed_section'],row['operative_section']) in {('30.6.17','30.6.18'),('30.6.18','30.6.19')},'Unexpected section correction')
    check(sum(r['section_number_differs'] for r in exhibit)==2,'Both stale Exhibit section references retained')
    check('30.6.18 – SEP for individuals who were not adequately informed' in fresh_texts['ENROLL:41'],'Inadequate notice operative section')
    check('30.6.19 – SEP for individuals who disenroll from Part D' in fresh_texts['ENROLL:41'],'Other creditable coverage operative section')
    check('30.6.36 – SEP for other exceptional circumstances' in fresh_texts['ENROLL:49'] and '422.62(b)(26)' in fresh_texts['ENROLL:49'],'Catch-all guidance typo retained')
    check('other exceptional conditions' in byid['CFRJAN:b.27']['text'],'Catch-all regulation identity')
    current_expected={167,168,170,171,173,175,177,179,180,182,185,187,189,191,193,195,197,198,202,203,205,209,211,212}
    check(len(credit)==24 and {int(c['current_clause_id'].split('L')[1]) for c in credit}==current_expected,'Complete creditable category inventory')
    check(Counter(c['category'] for c in credit)==Counter({'included':10,'excepted':8,'separately_offered':3,'independent_noncoordinated':2,'separate_supplemental_policy':1}),'Category scope census')
    for row in credit:
        for prefix in ['current','historical']:
            for infix in ['', '_parent']:
                k=prefix+infix+'_clause_id';txt=prefix+infix+'_text'
                check(byid.get(row[k],{}).get('text')==row[txt],'Credit category/parent fidelity '+row['id']+':'+k)
        check(row['literal_text_identical']==(row['current_text']==row['historical_text']),'Historical text equality marker '+row['id'])
        check(row['automatic_personal_credit_enabled'] is False,'Personal credit guard')
    check('627.6562(3) 627.6561(5)' in fresh_texts['LAW2016:20'],'Session-law Medigap reference change')
    check('subject to the requirements of s. 627.6561(6)-(11)' in fresh_texts['LAW2016:20'],'Deleted group-credit condition retained')
    check('July 1, 2016' in fresh_texts['LAW2016:28'],'Session law effective date')
    threshold=int(re.search(r'\((\d+)\) days',byid['FAC:69O-156.003:5']['text'])[1])
    check('greater than' in byid['FAC:69O-156.003:5']['text'] and threshold==63,'Continuity source comparator')
    check([continuity_boundary(x,synthetic=True,threshold=threshold) for x in [0,62,63,64,None]]==[True,True,True,False,None],'Continuity arithmetic cases')
    check('no more than 63 days' in byid['GUIDE:13']['text'],'CMS Medigap continuity corroboration')
    check('63 or more days' in byid['GUIDE:32']['text'],'Distinct Part D penalty boundary corroboration')
    findings=datasets['reconciliations-r2.json']
    check(len(findings)==15 and len({f['id'] for f in findings})==15,'Reconciliation inventory')
    for row in findings+sep+exhibit:
        check(all(k in byid for k in row['source_clause_ids']),'Unresolved reconciliation source link '+row['id'])
    for row in findings:
        check(row['qualified_review'] is None and row['consumer_release_enabled'] is False,'Reconciliation review guard')
    questions=datasets['review-questions.json'];check({q['id'] for q in questions}=={f'Q{i:02}' for i in range(1,7)},'Named review coverage')
    check(all(q['reviewer'] is None and q['decision'] is None for q in questions),'No fabricated specialist review')
    after=datasets['before-after.json']['after']
    check(after['rights_records']==51 and after['clocks']==14 and after['source_units']==len(units),'Inventory accounting')
    check(after['generic_SEP_holds']==0 and after['named_SEP_interpretation_holds']==5,'SEP gap accounting')
    summary=datasets['summary.json']
    check(summary['reference_year']==2026 and summary['reference_date']=='2026-10-28','Reference period')
    check(summary['full_l11_complete'] is False and summary['consumer_release_enabled'] is False and summary['human_acceptance'] is None and summary['qualified_R16_review'] is None and summary['personal_applicability_enabled'] is False,'Reference release guard')
    storage_errors,stored=verify_storage(build,datasets);errors+=storage_errors
    return {'schema':'l11-r2-validation/1','checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'status':'passed' if not errors else 'failed','errors':errors,
            'parent_manifest_verified':parent['manifest_sha256'],
            'baseline_validation_passed':prior['status']=='passed',
            'PDF_pages_freshly_compared':332,'new_source_units':len(new_ids),
            'source_units':len(units),'SQLite_full_field_rows_compared':stored,
            'SEP_paragraphs_checked':27,'Exhibit_rows_checked':18,
            'creditable_categories_with_parent_scope_checked':24,
            'continuity_boundary_cases':5,'synthetic_only':True,
            'meaning_review':'AI source comparison; no independent qualified legal adjudication claimed.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);p.add_argument('--build',type=Path,default=BUILD);args=p.parse_args()
    result=validate(args.build)
    if args.output:
        if (args.output.parent/'manifest.json').exists():raise ValueError('Sealed revision: do not overwrite validation')
        args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status']=='passed' else 1)
