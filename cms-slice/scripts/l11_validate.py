"""Independent L11 source-fidelity, field, storage and synthetic checks.

Passing this validator does not constitute a qualified interpretation review.
Synthetic date examples are unavailable for actual beneficiary use.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import html
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l11-medigap-rights-2026-10-28'


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    import hashlib
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def normalize(text):
    return ' '.join(text.replace('\xa0',' ').split())


def boolean_pattern(expr, facts):
    if isinstance(expr, str):
        value = facts.get(expr)
        if value is not None and type(value) is not bool:
            raise ValueError('Synthetic fact must be true/false/unknown')
        return value
    if set(expr) == {'not'}:
        value = boolean_pattern(expr['not'], facts)
        return None if value is None else not value
    if set(expr) == {'all'}:
        values = [boolean_pattern(x,facts) for x in expr['all']]
        return False if False in values else None if None in values else True
    if set(expr) == {'any'}:
        values = [boolean_pattern(x,facts) for x in expr['any']]
        return True if True in values else None if None in values else False
    raise ValueError('Unknown predicate operator')


def synthetic_window(clock, inputs, *, synthetic=False):
    if not synthetic:
        raise ValueError('Personal deadline execution is disabled')
    def d(key):
        return date.fromisoformat(inputs[key]) if inputs.get(key) else None
    start_key = clock['start']
    start = None; anchor = None
    if start_key == 'first_month_age65_and_part_b_first_day':
        start = d('first_qualifying_month')
        if start and start.day == 1:
            month = start.month - 1 + clock['amount']
            return start, date(start.year + month // 12, month % 12 + 1, 1)
        return None, None
    if start_key == 'applicable_notice_or_claim_denial_notice':
        start = anchor = d('notice')
    elif start_key == 'later_of_notice_or_claim_denial_and_coverage_end':
        a,b = d('notice'),d('coverage_end')
        start = anchor = max(a,b) if a and b else None
    elif start_key == 'termination_notice_received':
        start,anchor = d('notice'),d('coverage_end')
    elif start_key == 'earlier_of_applicable_notice_if_any_and_coverage_end':
        a,b = d('notice'),d('coverage_end')
        start = min(a,b) if a and b else b
        anchor = b
    elif start_key == 'disenrollment_minus_60_days':
        anchor = d('disenrollment')
        start = anchor - timedelta(days=clock['before_days']) if anchor else None
    elif start_key == 'effective_disenrollment':
        start = anchor = d('disenrollment')
    elif start_key == 'policy_delivery_or_receipt':
        start = anchor = d('receipt')
    elif start_key == 'medicaid_entitlement_or_loss_as_applicable':
        start = anchor = d('event')
    elif start_key == 'group_coverage_loss':
        start = anchor = d('loss')
    # Ambiguous month conventions, working days and notice scheduling remain
    # explicitly unavailable rather than assuming calendar-day arithmetic.
    if not start or not anchor or clock['unit'] != 'days':
        return None, None
    return start, anchor + timedelta(days=clock['amount'])


EXPECTED_CLOCKS = {
 'C01':('R01','months',6,'first_month_age65_and_part_b_first_day','start_plus_6_calendar_months_exclusive'),
 'C02':('R02','months',6,'first_qualifying_month_under_florida_statute','six_month_period_source_wording'),
 'C03':('R03','months',2,'following_group_policy_termination','two_month_period_source_wording'),
 'C04':('R22','days',63,'applicable_notice_or_claim_denial_notice','notice_plus_63_days'),
 'C05':('R23','days',63,'later_of_notice_or_claim_denial_and_coverage_end','start_plus_63_days'),
 'C06':('R24','days',63,'termination_notice_received','coverage_end_plus_63_days'),
 'C07':('R25','days',63,'earlier_of_applicable_notice_if_any_and_coverage_end','coverage_end_plus_63_days'),
 'C08':('R26','days',63,'disenrollment_minus_60_days','disenrollment_plus_63_days'),
 'C09':('R27','days',63,'effective_disenrollment','disenrollment_plus_63_days'),
 'C10':('R35','days',30,'policy_delivery_or_receipt','receipt_plus_30_days'),
 'C11':('R28','working_days',10,'issuer_receives_disenrollment_notice','ten_working_days_for_issuer_notice'),
 'C12':('R32','days',90,'medicaid_entitlement_or_loss_as_applicable','respective_event_plus_90_days_for_notice'),
 'C13':('R33','days',90,'group_coverage_loss','loss_plus_90_days_for_notice'),
 'C14':('R44','days',45,'planned_rate_change','at_least_45_days_advance_notice')
}


class OriginalText:
    def __init__(self, sources):
        self.sources = sources; self.cache = {}

    def expected(self, unit):
        sid = unit['source_id']; source = self.sources[sid]
        if sid not in self.cache:
            path = ROOT / source['path']
            if sid.startswith('usc-') or sid=='erisa-1999-definition':
                raw = path.read_text()
                paragraphs = [normalize(html.unescape(re.sub(r'<[^>]+>','',fragment)))
                              for fragment in re.findall(r'<p\b[^>]*>(.*?)</p>',raw,re.S|re.I)]
                self.cache[sid] = [p for p in paragraphs if p]
            elif sid == 'fl-rules-chapter':
                data = subprocess.check_output(['textutil','-convert','txt','-stdout',str(path)])
                self.cache[sid] = data.decode().splitlines()
            elif sid.startswith('fs-'):
                # Check against captured public extraction, not the builder's
                # joined lines file alone. Each original snapshot is hashed.
                rows = {}
                for capture in source['original_captures']:
                    p = ROOT / capture['path']
                    assert digest(p) == capture['sha256']
                    for block in p.read_text().split('--------------------------------------------------------------------------------'):
                        if source['requested_url'] + ')' not in block:
                            continue
                        for n,text in re.findall(r'^L(\d+): ?(.*)$',block,re.M):
                            clean = normalize(re.sub(r'【\d+†([^】]+)】',r'\1',text))
                            if int(n) in rows: assert rows[int(n)] == clean
                            rows[int(n)] = clean
                self.cache[sid] = rows
            elif source.get('content_type') == 'text/xml':
                self.cache[sid] = [normalize(''.join(p.itertext())) for p in ET.parse(path).findall('.//P')]
            else:
                run = subprocess.run(['pdftotext','-layout',str(path),'-'],capture_output=True,check=True)
                self.cache[sid] = run.stdout.decode().split('\f')
        rows = self.cache[sid]; locator = unit['locator']
        if 'paragraph_index_zero_based' in locator:
            return rows[locator['paragraph_index_zero_based']]
        if 'line_one_based' in locator:
            return normalize(rows[locator['line_one_based']-1])
        if 'web_line' in locator:
            return rows[locator['web_line']]
        if 'xml_p_zero_based' in locator:
            return rows[locator['xml_p_zero_based']]
        return normalize(rows[locator['pdf_page']-1])


def validate(dest):
    errors = []
    def check(ok, message):
        if not ok: errors.append(message)
    sources = load(dest/'sources.json'); rules = load(dest/'rules.json')
    ledger = load(dest/'source-clause-ledger.json'); units = {x['id']:x for x in ledger}
    clocks = {x['id']:x for x in load(dest/'clocks.json')}
    predicates = {x['id']:x for x in load(dest/'synthetic-predicate-patterns.json')}
    original = OriginalText(sources)
    contract = load(dest/'source-clause-contract.json')
    check(contract['source_unit_ids']==[u['id'] for u in ledger], 'Source inventory changed against revision contract')
    check(contract['required_rule_clause_ids']=={r['id']:r['source_clause_ids'] for r in rules}, 'Required clause relationship dropped/added against revision contract')
    check(contract['quantities_by_rule']=={r['id']:r['quantities'] for r in rules}, 'Structured quantity inventory differs from revision contract')
    source_checks = []
    for sid, source in sources.items():
        path = ROOT / source['path']
        check(path.is_file() and digest(path)==source['sha256'],sid+' source hash mismatch')
        check(path.stat().st_size==source['bytes'],sid+' source size mismatch')
        if source.get('wire_sha256') and source['wire_sha256'] != source['sha256']:
            wire = BASE/'acquisition-r1/raw'/source['wire_sha256']
            check(digest(wire)==source['wire_sha256'],sid+' wire hash mismatch')
        if 'text_path' in source:
            check(digest(ROOT/source['text_path'])==source['text_sha256'],sid+' text changed')
        source_checks.append({'source_id':sid,'content_status':source['content_status'],'hash_size_checked':True})
    unit_checks = []
    for unit in ledger:
        actual = original.expected(unit)
        check(actual==unit['text'],unit['id']+' original text differs')
        unit_checks.append({'source_clause_id':unit['id'],'original_text_matches':actual==unit['text']})
    condition_links = 0
    for rule in rules:
        check(rule['human_acceptance'] is None and rule['consumer_release_enabled'] is False,rule['id']+' release guard')
        check(set(rule['source_clause_ids'])=={c['source_clause_id'] for c in rule['conditions']},rule['id']+' dropped/extra condition')
        check(all(rid in {r['id'] for r in rules} for rid in rule['shared_requirement_rule_ids']),rule['id']+' shared requirement missing')
        if rule['id'] in {'R06','R07','R08','R09','R10','R11','R12','R13','R14','R15','R16','R17'}:
            check(rule['shared_requirement_rule_ids']==['R21'],rule['id']+' lost common GI evidence/window requirements')
        for condition in rule['conditions']:
            condition_links += 1
            check(condition['source_clause_id'] in units,rule['id']+' missing source clause')
            check(condition['text']==units[condition['source_clause_id']]['text'],rule['id']+' altered source condition')
        for q in rule['quantities']:
            witnesses = [units[u]['text'] for u in rule['source_clause_ids'] if q['witness'] in units[u]['text']]
            numbers = [int(n) for n in re.findall(r'\d+',q['witness'])]
            numbers += [n for word,n in {'six':6,'ten':10,'twelve':12,'thirty':30,'sixty-three':63,'ninety':90}.items()
                        if re.search(r'\b'+re.escape(word)+r'\b',q['witness'].lower())]
            check(bool(witnesses) and q['value'] in numbers,rule['id']+' quantity not independently reproduced')
            unit_words = {'months':['month'],'years':['year','age'],'days':['day'],'calendar_months':['calendar month'],'working_days':['working day']}
            check(q['unit'] in unit_words and any(w in q['witness'].lower() for w in unit_words[q['unit']]),rule['id']+' quantity unit mismatch')
    for cid,expected in EXPECTED_CLOCKS.items():
        c = clocks[cid]
        check(tuple(c[k] for k in ['rule','unit','amount','start','end'])==expected,cid+' clock basis/value differs')
        check(c['personal_calculation_enabled'] is False,cid+' enabled personal calculation')
    check(clocks['C08']['before_days']==60,'Voluntary application lead is not 60 days')
    choices = load(dest/'policy-choices.json')
    check(choices['ordinary_event_pre_2020']==['A','B','C','F','F_HIGH','K','L'],'Pre-2020 choices differ')
    check(choices['ordinary_event_newly_eligible']==['A','B','D','G','G_HIGH','K','L'],'Newly eligible choices differ')
    choice_source = ' '.join(units[u]['text'] for u in choices['source_clause_ids'])
    check('A, B, C, F (including F with a high deductible), K, or L' in choice_source,'State policy-choice source differs')
    check('“D” or “G”, respectively' in choice_source,'Federal transition source differs')
    check('High-Deductible G' in choice_source and 'High-Deductible F' in choice_source,'Explicit Florida high-deductible choice evidence missing')
    check(choices['personal_carrier_availability']=='not_determined','Unsupported carrier availability')
    temporal = load(dest/'temporal-reconciliation.json')
    fr = normalize((ROOT/sources['fr-2026-06600']['text_path']).read_text())
    check(temporal['effective_date_statement'] in fr and temporal['applicability_statement'] in fr,'Final-rule date comparison differs')
    check(temporal['published_federal_code_release']=='119-136' and temporal['latest_public_law_in_retained_OFR_index']==136,'Federal currency differs')
    check(temporal['incorporated_ERISA_definition_1999_matches_current'] is True and units['ERISA1999:1']['text']==units['ERISA:1']['text'],'Incorporated historical definition differs')
    check({x['paragraph'] for x in temporal['regulation_comparison']}=={'b.3','b.5','b.20','b.27'},'Regulation difference inventory changed')
    for row in temporal['regulation_comparison']:
        check(row['january_text']==units[row['january_source_clause_id']]['text'],'January regulation comparison altered')
        check(row['october_text']==units[row['october_source_clause_id']]['text'],'October regulation comparison altered')
    date_index = normalize(html.unescape(re.sub(r'<[^>]+>',' ',(ROOT/sources['fl-rules-index']['path']).read_text())))
    for rule,effective in temporal['official_rule_version_effective_dates'].items():
        d=date.fromisoformat(effective)
        observed=d.strftime('%m/%d/%Y').lstrip('0').replace('/0','/')
        pattern=re.escape(rule)+r'\b.{0,600}?'+re.escape(observed)
        check(bool(re.search(pattern,date_index)),rule+' effective date not independently located in index')
    crosswalk=load(dest/'sep-crosswalk.json')
    check(len(crosswalk)==27 and len({c['paragraph'] for c in crosswalk})==27,'Incomplete referenced special-election inventory')
    for c in crosswalk:
        check(bool(c['source_clause_ids']) and all(uid in units for uid in c['source_clause_ids']),'Special-election source lineage missing')
    for c in load(dest/'reconciliations.json'):
        check(bool(c['source_clause_ids']) and all(uid in units for uid in c['source_clause_ids']),'Comparison source lineage missing')
    fixtures = load(BASE/'synthetic-cases-r1.json'); case_results=[]
    for case in fixtures['cases']:
        actual = boolean_pattern(predicates[case['predicate']]['expression'],case['facts'])
        check(actual is case['expected'],case['id']+' synthetic predicate differs')
        case_results.append({'id':case['id'],'expected':case['expected'],'actual':actual,'passed':actual is case['expected']})
    for case in fixtures['date_cases']:
        start,end = synthetic_window(clocks[case['clock']],case['dates'],synthetic=True)
        actual = [start.isoformat() if start else None,end.isoformat() if end else None]
        expected = [case['expected_start'],case['expected_end']]
        check(actual==expected,case['id']+' synthetic window differs')
        case_results.append({'id':case['id'],'expected':expected,'actual':actual,'passed':actual==expected})
    db = sqlite3.connect('file:'+str(dest/'l11-reference.sqlite')+'?mode=ro',uri=True)
    for table,rows in [('rights',rules),('source_clauses',ledger),('clocks',list(clocks.values()))]:
        actual = {r[0]:json.loads(r[1]) for r in db.execute('SELECT id,data FROM '+table)}
        check(actual=={r['id']:r for r in rows},table+' full-field JSON/SQLite roundtrip differs')
    db.close()
    # Required modeled fields cannot acquire financial steering metadata.
    check(not re.search(r'"(?:commission|revenue|partner_preference|compensated_rank)"',json.dumps(rules)), 'Commercial input reached the reference')
    check({r['family'] for r in rules}=={f'RF{i:02}' for i in range(1,15)},'A planned work family disappeared')
    check(set(predicates)=={f'P{i:02}' for i in range(1,15)},'Predicate pattern missing')
    check(len(rules)==len({r['id'] for r in rules}), 'Duplicate rights record')
    check(len(ledger)==len(units), 'Duplicate source unit')
    for p in predicates.values():
        check(p['personal_execution_enabled'] is False and p['exhaustive_legal_predicate_model'] is False,'Misstated predicate scope')
        check(all(uid in units for uid in p['source_clause_ids']),'Predicate source lineage broken')
    return {'schema':'l11-validation/1','checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'status':'passed' if not errors else 'failed','errors':errors,'source_checks':source_checks,
            'source_clause_text_checks':unit_checks,'synthetic_case_results':case_results,
            'counts':{'sources':len(sources),'rules':len(rules),'source_units_independently_compared':len(ledger),
                      'condition_links_exactly_compared':condition_links,'quantities':sum(len(r['quantities']) for r in rules),
                      'clocks_compared':len(clocks),'synthetic_cases':len(case_results),'storage_rows_full_field_compared':len(rules)+len(ledger)+len(clocks),
                      'referenced_special_election_paragraphs':len(crosswalk),'official_rule_effective_dates_checked':len(temporal['official_rule_version_effective_dates'])},
            'limits':['Exact source fidelity, structured values, storage and authored synthetic cases checked; not an independent legal interpretation or exhaustive personal adjudication validation.',
                      'Condition links/source units are not counts of unique rights or verified semantic predicates.'],
            'full_l11_complete':False,'qualified_R16_review':None,'human_acceptance':None,'consumer_release_enabled':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('build',type=Path);p.add_argument('--write',action='store_true');a=p.parse_args()
    result=validate(a.build)
    if a.write:
        path=a.build/'validation.json'
        if path.exists():raise ValueError('Validation exists; preserve the revision')
        path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ['status','errors','counts']},indent=2))
    raise SystemExit(0 if result['status']=='passed' else 1)
