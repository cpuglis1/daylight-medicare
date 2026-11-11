"""Build a research-only L11 published-rights reference from retained evidence.

Source clauses are retained in full, including their hierarchy and qualifiers.
The reference has no personal eligibility, enrollment or UI integration.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import xml.etree.ElementTree as ET

from l11_catalog import CLOCKS, GAPS, NEW, PRE, PREDICATES, RULES
from l11_sources import ACQ, BASE, ROOT, norm, sha


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + '\n')


def load(path):
    return json.loads(Path(path).read_text())


def temporal_and_reconciliations(dest, sources, units):
    index = (ROOT / sources['fl-rules-index']['path']).read_text()
    dates = {}
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>',index,re.S):
        text = norm(html.unescape(re.sub(r'<[^>]+>',' ',row)))
        match = re.match(r'(69O-156\.\d+) .*?(\d{1,2}/\d{1,2}/\d{4})$',text)
        if match: dates[match[1]]=datetime.strptime(match[2],'%m/%d/%Y').date().isoformat()
    sources['fl-rules-chapter']['current_rule_version_effective_dates_from_official_index'] = dates
    archive = (ROOT / sources['public-law-index']['text_path']).read_text()
    currency = (ROOT / sources['usc-currency']['text_path']).read_text()
    latest = max(int(n) for n in re.findall(r'119-(\d+)',archive))
    if latest != 136 or '119-136' not in currency:
        raise ValueError('Published federal currency changed; review before building')
    final_rule = norm((ROOT / sources['fr-2026-06600']['text_path']).read_text())
    effective = 'These regulations are effective June 1, 2026.'
    applicable = 'These regulations are applicable to coverage beginning January 1, 2027.'
    if effective not in final_rule or applicable not in final_rule:
        raise ValueError('Final-rule date statements changed')
    jan = {u['id'].split(':',1)[1]:u for u in units if u['id'].startswith('CFRJAN:')}
    oct_ = {u['id'].split(':',1)[1]:u for u in units if u['id'].startswith('CFROCT:')}
    changes = [{'paragraph':k,'january_source_clause_id':u['id'],'october_source_clause_id':oct_[k]['id'],
                'january_text':u['text'],'october_text':oct_[k]['text']} for k,u in jan.items()
               if k in oct_ and u['text']!=oct_[k]['text']]
    expected = {'b.3','b.5','b.20','b.27'}
    if {c['paragraph'] for c in changes} != expected:
        raise ValueError('Unexpected dated regulation difference')
    temporal = {'schema':'l11-temporal-reconciliation/1','reference_date':'2026-10-28',
                'published_federal_code_release':'119-136','latest_public_law_in_retained_OFR_index':latest,
                'law_index_source_id':'public-law-index','current_code_source_id':'usc-medigap-current',
                'official_rule_version_effective_dates':dates,
                'regulation_comparison':changes,'final_rule_source_id':'fr-2026-06600',
                'effective_date_statement':effective,'applicability_statement':applicable,
                'coverage_2026_basis':'January 2026 paragraph text for provisions changed by the final rule whose stated applicability begins with 2027 coverage. Later text is retained for comparison, not silently applied to 2026.',
                'limit':'Specific post-2026 coverage or mixed transition cases require their own dated application review. Dates not established by the retained sources remain unspecified.'}
    historical = next(u['text'] for u in units if u['id']=='ERISA1999:1')
    current = next(u['text'] for u in units if u['id']=='ERISA:1')
    if historical != current:
        raise ValueError('Incorporated employee-welfare definition changed; reconcile versions')
    temporal['incorporated_ERISA_definition_1999_matches_current'] = True
    temporal['incorporated_ERISA_source_clause_ids'] = ['ERISA1999:1','ERISA:1']
    dump(dest/'temporal-reconciliation.json',temporal)
    assessed = {1:'express_termination_route',2:'express_move_route_with_exclusions',3:'express_breach_or_misrepresentation_route_with_CMS_process',
                6:'cost_plan_analogue_with_program_conditions',8:'express_prior_medigap_trial_route',9:'historical_ESRD_provision_ended_2020',
                23:'express_significant_network_route_with_CMS_determination',27:'exceptional_CMS_determination_route'}
    crosswalk=[]
    for n in range(1,28):
        clauses = resolve('CFRJAN:b.'+str(n),units)
        crosswalk.append({'paragraph':'422.62(b)('+str(n)+')','source_clause_ids':[u['id'] for u in clauses],
                          'classification':assessed.get(n,'exact_event_and_statutory_authority_review_required'),
                          'not_a_personal_GI_determination':True,'hold_id':None if n in assessed else 'G09'})
    dump(dest/'sep-crosswalk.json',crosswalk)
    topics = [
      ('RC01','Florida event plan choices','source_reconciled','Use state A/B/C/F/high-F/K/L and federal D/G substitution for newly eligible; retain broader trial exceptions and actual issuer availability.',['FAC:69O-156.0095:5','USC:s-3-C','USC:z','FAQ:4','CMSFAQ:7']),
      ('RC02','Employer clocks','source_reconciled_separate_rights','Federal notice-based and Florida later-of notice/end clocks remain separate; state two-month group-policy opportunity is a third right.',['USC:s-3-E-i','FAC:69O-156.0095:3.a','FS:627.6741:L155','GUIDE:19']),
      ('RC03','Two trial paths','source_reconciled','Former-policy/first-entry path differs from first-Part-A-at-65 any-policy path.',['USC:s-3-B-v','USC:s-3-B-vi','FAC:69O-156.0095:5']),
      ('RC04','Interrupted trials','source_reconciled','Keep involuntary termination, no intervening enrollment and two-year outer limit; no automatic reset.',['USC:s-3-F','FAC:69O-156.0095:4']),
      ('RC05','Preexisting conditions','source_reconciled','Initial enrollment may permit bounded exclusion with credit; protected GI prohibits preexisting exclusion. Replacement credit concerns similar benefits.',['USC:s-1','USC:s-2','USC:s-3-A','FAC:69O-156.019:']),
      ('RC06','Suspension limits','source_reconciled','Medicaid 24-month cap and notices are distinct from disability/employer protection; reinstatement premium and coverage terms retained.',['USC:q-5-A','USC:q-6','FAC:69O-156.0075:1.g']),
      ('RC07','SELECT conversion','source_reconciled_with_case_dependency','Same-issuer, offered comparable-or-lesser benefits and six-month in-force requirement differ from an all-carrier event purchase right.',['FAC:69O-156.030:13','USC:s-3-B-iii']),
      ('RC08','Return and issuer notices','source_reconciled','30 days from receipt for free look differs from 10 working days for issuer notice and 45 days advance rate notice.',['FS:627.674:L185','FAC:69O-156.0095:6','FAC:69O-156.014:1']),
      ('RC09','2020 eligibility cutoff','federal_definition_retained_state_summary_flagged','Prior qualifying Part A entitlement/deemed eligibility can exclude a beneficiary from newly-eligible status despite turning 65 after 2020.',['USC:z-2','FAC:69O-156.003:14']),
      ('RC10','Creditable definition','material_cross_reference_hold','Statute expressly imports current 627.6562(3); older FAC points to absent 627.6561(5). Retain literal definitions and no unsupported personal credit calculation.',['FS:627.6741:L162','FAC:69O-156.003:5','FAC:69O-156.003:6','FS:627.6562:L155-212']),
      ('RC11','Legacy Part D substitution','historical_scope_reconciled','Original initial Part D period is not a new annual 2026 right.',['USC:v-3','USC:v-6-D','FAC:69O-156.0095:2.g']),
      ('RC12','Other exceptional SEPs','case_classification_hold','All 27 numbered special-election paragraphs retained and inventoried. No blanket all-SEP or no-other-SEP Medigap conclusion.',['CFRJAN:b','MA:e-4','CMSFAQ:8'])]
    comparisons=[]
    for cid,topic,status,conclusion,selectors in topics:
        refs=list(dict.fromkeys(u['id'] for s in selectors for u in resolve(s,units)))
        comparisons.append({'id':cid,'topic':topic,'status':status,'conclusion':conclusion,'source_clause_ids':refs,
                            'comparison_actor':'AI source comparison; qualified independent R16 review pending'})
    dump(dest/'reconciliations.json',comparisons)


def units_from_sources():
    sources = load(ACQ / 'extraction-index.json')
    units = []
    for sid, prefix in [('usc-medigap-current', 'USC'), ('usc-ma-election-current', 'MA'),
                        ('usc-employee-benefit-definition','ERISA'),('usc-medicare-group-definition','MEX'),
                        ('usc-group-plan-tax-definition','TAX')]:
        rows = load(ROOT / sources[sid]['paragraphs_path'])
        parent = 'intro'; counts = Counter()
        for i, row in enumerate(rows):
            if row['html_id']:
                parent = row['html_id']
            key = prefix + ':' + parent
            counts[key] += 1
            if counts[key] > 1:
                key += '~' + str(counts[prefix + ':' + parent] - 1)
            units.append({'id': key, 'source_id': sid, 'locator': {'paragraph_index_zero_based': i, 'html_id': row['html_id']},
                          'text': row['text'], 'parent_anchor': prefix + ':' + parent})
    historical = load(ROOT/sources['erisa-1999-definition']['paragraphs_path'])
    found=[(i,r) for i,r in enumerate(historical) if r['text'].startswith('(1) The terms')]
    if len(found)!=1: raise ValueError('Historical definition location changed')
    i,r=found[0]
    units.append({'id':'ERISA1999:1','source_id':'erisa-1999-definition',
                  'locator':{'paragraph_index_zero_based':i,'html_id':r['html_id']},
                  'text':r['text'],'parent_anchor':'ERISA1999:1'})
    chapter = (ROOT / sources['fl-rules-chapter']['text_path']).read_text().splitlines()
    rule = None; levels = {}; counts = Counter()
    for number, text in enumerate(chapter, 1):
        if number > 45 and re.match(r'^69O-156\.\d+ ', text):
            rule = text.split()[0]; levels = {}; path = 'root'
        elif rule:
            rest = text.lstrip()
            tokens = re.match(r'^(\([^)]*\))+', rest)
            if tokens:
                for token in re.findall(r'\(([^)]*)\)', tokens[0]):
                    level = 1 if token.isdigit() else 5 if token.isupper() else 2
                    levels = {k: v for k, v in levels.items() if k < level}
                    levels[level] = token
                rest = rest[len(tokens[0]):]
            for pat, level in [(r'^(\d+)\.', 3), (r'^([a-z])\.', 4)]:
                match = re.match(pat, rest)
                if match:
                    levels = {k: v for k, v in levels.items() if k < level}
                    levels[level] = match[1]; rest = rest[match.end():]
            path = '.'.join(v for _, v in sorted(levels.items())) or 'root'
            if text.startswith('Rulemaking Authority'):
                path = 'history'
        else:
            continue  # The chapter index is retained separately.
        if not text.strip():
            continue
        key = 'FAC:' + rule + ':' + path
        counts[key] += 1
        if counts[key] > 1:
            key += '~' + str(counts['FAC:' + rule + ':' + path] - 1)
        units.append({'id': key, 'source_id': 'fl-rules-chapter', 'locator': {'rule': rule, 'line_one_based': number, 'clause_path': path},
                      'text': norm(text), 'parent_anchor': 'FAC:' + rule + ':' + path})
    for sid, source in list(sources.items()):
        if not sid.startswith('fs-'):
            continue
        lines = load(ROOT / source['path'])
        section = sid[3:]
        body = False
        for number, text in lines.items():
            if text.startswith(section + '\u2003') or text.startswith(section + ' '):
                body = True
            if body and text.strip():
                units.append({'id': f'FS:{section}:L{number}', 'source_id': sid,
                              'locator': {'web_line': int(number)}, 'text': norm(re.sub(r'【\d+†([^】]+)】', r'\1', text)),
                              'parent_anchor': 'FS:' + section})
            if body and text.startswith('History.') or body and text.startswith('History.—'):
                break
    held = load(BASE / 'reuse-audit.json')['held_sources']
    for hid, prefix in [('H01', 'GUIDE'), ('H02', 'FAQ'), ('H03', 'BLUE'), ('H04', 'BLUESELECT')]:
        source = next(s for s in held if s['id'] == hid)
        if sha(ROOT / source['path']) != source['sha256'] or sha(ROOT / source['text_path']) != source['text_sha256']:
            raise ValueError('Held source changed: ' + hid)
        sid = 'held-' + hid
        sources[sid] = {**source, 'source_id': sid, 'content_status': 'reused_held_bytes', 'capture_limit': source['limits']}
        pages = (ROOT / source['text_path']).read_text().split('\f')
        if len(pages) - (1 if not pages[-1].strip() else 0) != source['pages']:
            raise ValueError('Held PDF page count changed')
        for i, page in enumerate(pages, 1):
            if page.strip():
                units.append({'id': f'{prefix}:{i}', 'source_id': sid, 'locator': {'pdf_page': i},
                              'text': norm(page), 'parent_anchor': prefix})
    for sid, prefix in [('cms-naic-faq', 'CMSFAQ')]:
        pages = (ROOT / sources[sid]['text_path']).read_text().split('\f')
        for i, page in enumerate(pages, 1):
            if page.strip():
                units.append({'id': f'{prefix}:{i}', 'source_id': sid, 'locator': {'pdf_page': i}, 'text': norm(page), 'parent_anchor': prefix})
    for sid, prefix in [('ecfr-422-62-jan', 'CFRJAN'), ('ecfr-422-62-gzip', 'CFROCT')]:
        tree = ET.parse(ROOT / sources[sid]['path'])
        levels = []; counts = Counter()
        for i, p in enumerate(tree.findall('.//P')):
            text = norm(''.join(p.itertext()))
            tags = re.match(r'^(?:\([^)]*\))+', text)
            if tags:
                values = re.findall(r'\(([^)]*)\)', tags[0])
                for value in values:
                    level = 1 if value in ['a', 'b', 'c', 'd'] and not value.isupper() and not levels else None
                    # The source supplies top-level (a)..(d), numeric children and roman grandchildren.
                    if value in ['a','b','c','d'] and (len(values)>1 or len(text)>10 and text.startswith('('+value+') ')):
                        levels = [value]
                    elif value.isdigit():
                        levels = levels[:1] + [value]
                    elif value in ['i','ii','iii','iv','v','vi']:
                        levels = levels[:2] + [value]
                    else:
                        levels = levels[:3] + [value]
            key = prefix + ':' + '.'.join(levels)
            counts[key] += 1
            if counts[key] > 1:
                key += '~' + str(counts[prefix + ':' + '.'.join(levels)] - 1)
            units.append({'id': key, 'source_id': sid, 'locator': {'xml_p_zero_based': i}, 'text': text, 'parent_anchor': prefix + ':' + '.'.join(levels)})
    ids = [u['id'] for u in units]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate source unit identity')
    return sources, units


def resolve(selector, units):
    if selector.startswith('FS:') and re.search(r':L\d+-\d+$', selector):
        prefix, bounds = selector.rsplit(':L', 1)
        start, end = map(int, bounds.split('-'))
        return [u for u in units if u['id'].startswith(prefix + ':L') and start <= u['locator']['web_line'] <= end]
    if selector.startswith('FAC:') and selector.endswith(':'):
        matches = [u for u in units if u['id'].startswith(selector)]
    elif selector.startswith(('FAC:', 'CFRJAN:', 'CFROCT:')):
        matches = [u for u in units if u['id'] == selector or u['id'].startswith(selector + '.') or u['id'].startswith(selector + '~')]
    elif selector.startswith(('USC:', 'MA:', 'ERISA:', 'MEX:', 'TAX:')):
        matches = [u for u in units if u['id'] == selector or u['id'].startswith(selector + '-') or u['id'].startswith(selector + '~')]
    else:
        matches = [u for u in units if u['id'] == selector]
    if not matches:
        raise ValueError('Missing exact source selector: ' + selector)
    return matches


def build(dest):
    if dest.exists():
        raise ValueError('Build directory already exists; preserve it and use a new revision')
    dest.mkdir(parents=True)
    sources, units = units_from_sources()
    temporal_and_reconciliations(dest,sources,units)
    lookup = {u['id']:u for u in units}
    def with_source_parents(selected):
        expanded = dict(selected)
        for uid in list(selected):
            if uid.startswith(('USC:', 'MA:', 'ERISA:', 'MEX:', 'TAX:')):
                prefix,path = uid.split(':',1)
                path = path.split('~')[0]
                candidates = [prefix+':'+path.rsplit('-',i)[0] for i in range(1,path.count('-')+1)]
            elif uid.startswith(('FAC:', 'CFRJAN:', 'CFROCT:')):
                prefix,path = uid.rsplit(':',1)
                path = path.split('~')[0]
                candidates = [prefix+':'+path.rsplit('.',i)[0] for i in range(1,path.count('.')+1)]
                if uid.startswith('FAC:'): candidates.append(prefix+':root')
            else:
                candidates = []
            for parent in candidates:
                for key in [parent]+[u for u in lookup if u.startswith(parent+'~')]:
                    if key in lookup: expanded[key]=lookup[key]
        return expanded
    records = []; reverse = {u['id']: [] for u in units}
    field_checks = []
    for spec in RULES:
        selected = {u['id']: u for selector in spec['source_selectors'] for u in resolve(selector, units)}
        explicit = set(selected)
        selected = with_source_parents(selected)
        evidence = list(selected.values())
        conditions = [{'source_clause_id': u['id'], 'text': u['text'],
                       'role': 'selected_source_clause' if u['id'] in explicit else 'inherited_source_parent'} for u in evidence]
        text = ' '.join(u['text'] for u in evidence)
        for quantity in spec['quantities']:
            matches = [u['id'] for u in evidence if quantity['witness'] in u['text']]
            if not matches:
                raise ValueError(spec['id'] + ' quantity witness missing: ' + quantity['witness'])
            field_checks.append({'rule_id': spec['id'], **quantity, 'source_clause_ids': matches,
                                 'comparison': 'literal_source_witness_and_authored_quantity_review', 'result': 'source_witness_present'})
        record = {**spec, 'jurisdiction': 'US-FL' if any(u['source_id'].startswith(('fs-', 'fl-')) for u in evidence) else 'US',
                  'reference_year': 2026, 'reference_date': '2026-10-28',
                  'source_clause_ids': list(selected), 'conditions': conditions,
                  'review_status': 'AI_source_comparison_pending_qualified_R16', 'human_acceptance': None,
                  'consumer_release_enabled': False}
        gi_events = {'R06','R07','R08','R09','R10','R11','R12','R13','R14','R15','R16','R17'}
        record['shared_requirement_rule_ids'] = ['R21'] if spec['id'] in gi_events else []
        record['conditional_policy_choice_rule_id'] = 'R19' if spec['id'] in gi_events else None
        record['relationship_limit'] = 'Shared requirements apply with the selected event; policy-choice exceptions and clocks must follow that event, never all branches or the longest clock.'
        record['source_effective_context'] = 'Exact source editions, retained rule history and 2026 applicability are in sources.json and temporal-reconciliation.json; no unsourced effective day is inferred.'
        records.append(record)
        for uid in selected:
            reverse[uid].append(spec['id'])
    # Every retained source unit is accounted for. Source-unit accounting is not
    # an asserted semantic claim denominator or a substitute for qualified review.
    ledger = []
    for unit in units:
        linked = reverse[unit['id']]
        if linked:
            reason='Directly retained in normalized reference conditions, including inherited source parents'
        elif unit['source_id']=='ecfr-422-62-gzip':
            reason='Later regulation retained for dated comparison; 2027 coverage amendments are not silently used for 2026'
        elif unit['id'].startswith('FAC:'):
            reason='Retained chapter context: benefit standards/administration/marketing outside this published buying-rights claim set; rights clauses and source parents are linked separately'
        elif unit['id'].startswith(('GUIDE:','FAQ:','BLUE:','BLUESELECT:','CMSFAQ:')):
            reason='Retained full document page outside the modeled buying-rights passage set; benefits/costs/contact or other context is not promoted to an L11 claim'
        else:
            reason='Retained source context, headings, certification/enforcement/history or cross-layer provisions outside the modeled buying-rights claim set'
        ledger.append({**unit, 'rule_ids': linked, 'disposition': 'modeled_source_clause' if linked else 'retained_context', 'reason': reason})
    choices = {'ordinary_event_pre_2020': PRE, 'ordinary_event_newly_eligible': NEW,
               'first_part_a_at_65_trial': 'any_eligible_policy_offered_subject_to_MACRA',
               'former_policy_trial': 'same_policy_if_available_same_issuer_else_event_choices_with_legacy_Rx_qualification',
               'source_clause_ids': [u['id'] for s in ['FAC:69O-156.0095:5', 'USC:z', 'FAQ:4', 'FAQ:5'] for u in resolve(s, units)],
               'personal_carrier_availability': 'not_determined'}
    predicates = []
    for p in PREDICATES:
        refs = list(dict.fromkeys(u['id'] for selector in p['source_selectors'] for u in resolve(selector, units)))
        predicates.append({**p, 'source_clause_ids': refs, 'scope': 'illustrative_synthetic_validation_pattern',
                           'exhaustive_legal_predicate_model': False, 'personal_execution_enabled': False})
    dump(dest / 'sources.json', sources)
    dump(dest / 'rules.json', records)
    dump(dest / 'clocks.json', CLOCKS)
    dump(dest / 'policy-choices.json', choices)
    dump(dest / 'synthetic-predicate-patterns.json', predicates)
    dump(dest / 'source-clause-ledger.json', ledger)
    dump(dest / 'quantity-comparisons.json', field_checks)
    dump(dest / 'gaps.json', GAPS)
    statuses = {
        'G01':'personal_deadline_interpretation_held',
        'G02':'ordinary_rule_retained_nonstandard_case_conditional',
        'G03':'federal_definition_source_reconciled_qualified_confirmation_pending',
        'G04':'stale_cross_reference_retained_qualified_reconciliation_pending',
        'G05':'separate_routes_source_reconciled_specific_policy_dependency_retained',
        'G06':'historical_period_source_reconciled_no_new_2026_annual_right_claimed',
        'G07':'conditional_carrier_evidence_not_required_for_statutory_reference',
        'G08':'independent_qualified_review_and_acceptance_pending',
        'G09':'complete_source_inventory_partial_exceptional_case_classification'}
    dump(dest / 'issue-dispositions.json', {
        'items':[{'id':g['id'],'title':g['title'],'status':statuses[g['id']],'closure':g['closure']} for g in GAPS],
        'missing_core_bulk_source_files':[],
        'core_published_source_collection_status':'Named legal/guidance corpus retained through origin downloads or complete public web text; interpretation and exact review limits remain.',
        'genuine_remaining_required_review_topics':['G01','G04','G08','G09'],
        'conditional_nonstandard_or_carrier_cases':['G02','G05','G07'],
        'source_comparison_resolutions_requiring_no_new_bulk_collection':['G03','G06']})
    dump(dest / 'source-clause-contract.json', {
        'schema':'l11-source-clause-contract/1','status':'research_inventory_not_independently_accepted',
        'source_unit_ids':[u['id'] for u in ledger],
        'required_rule_clause_ids':{r['id']:r['source_clause_ids'] for r in records},
        'quantities_by_rule':{r['id']:r['quantities'] for r in records},
        'meaning_is_not_frozen_as_an_exhaustive_semantic_predicate_denominator':True})
    db = sqlite3.connect(dest / 'l11-reference.sqlite')
    db.executescript('CREATE TABLE rights(id TEXT PRIMARY KEY, family TEXT NOT NULL, jurisdiction TEXT NOT NULL, data TEXT NOT NULL); CREATE TABLE source_clauses(id TEXT PRIMARY KEY, source_id TEXT NOT NULL, data TEXT NOT NULL); CREATE TABLE clocks(id TEXT PRIMARY KEY, rule_id TEXT NOT NULL, data TEXT NOT NULL);')
    db.executemany('INSERT INTO rights VALUES(?,?,?,?)', [(r['id'],r['family'],r['jurisdiction'],json.dumps(r,sort_keys=True)) for r in records])
    db.executemany('INSERT INTO source_clauses VALUES(?,?,?)', [(u['id'],u['source_id'],json.dumps(u,sort_keys=True)) for u in ledger])
    db.executemany('INSERT INTO clocks VALUES(?,?,?)', [(c['id'],c['rule'],json.dumps(c,sort_keys=True)) for c in CLOCKS])
    db.commit(); db.close()
    code = dest / 'code'; code.mkdir()
    for filename in ['l11_acquire.py','l11_sources.py','l11_catalog.py','l11_build.py','l11_validate.py','l11_seal.py']:
        p = ROOT / 'cms-slice/scripts' / filename
        if p.exists(): shutil.copyfile(p, code / filename)
    shutil.copyfile(ROOT/'cms-slice/tests/test_l11_reference.py',code/'test_l11_reference.py')
    summary = {'schema':'l11-research-reference/1','built_at_utc':datetime.now(timezone.utc).isoformat(),
               'reference_year':2026,'reference_date':'2026-10-28','rights_records':len(records),
               'work_families':sorted({r['family'] for r in records}), 'clocks':len(CLOCKS),
               'retained_source_units':len(units),'modeled_source_units':sum(bool(x) for x in reverse.values()),
               'condition_links':sum(len(r['conditions']) for r in records), 'structured_quantities':len(field_checks),
               'unit_counts_are_not_unique_legal_claim_or_verified_fact_counts':True,
               'normalization_scope':'Published source-clause reference, not an exhaustive independently accepted executable legal predicate model',
               'research_only':True,'full_l11_complete':False,'human_acceptance':None,'consumer_release_enabled':False}
    dump(dest / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
