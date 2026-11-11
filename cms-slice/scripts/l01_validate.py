#!/usr/bin/env python3
"""Reproducible inventory, source comparison and independent-case verification.

This report is engineering evidence. It cannot create domain acceptance.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

from l01 import L01, Acceptance, L01Error, load, verify
from l01_acquire import PACKAGE, dump
from l01_build import SourceHTML, cents

AS_OF = datetime(2026, 10, 25, 18, tzinfo=timezone.utc)


def case_inventory(package=PACKAGE):
    expected = load(package / 'independent-expectations.json')
    cases = load(package / 'worked-cases.json')
    for filing, fixture in expected['income_boundaries'].items():
        for context, values in expected['monthly_cents'].items():
            for ti, threshold in enumerate(fixture['thresholds_dollars']):
                for delta, position in [(-1, 'below'), (0, 'at'), (1, 'above')]:
                    band = fixture[position][ti]
                    index = expected['married_separate_band_indices'][band] if filing == 'separate_together' else band
                    conflicting = filing == 'separate_together' and context != 'part_d' and band > 0
                    request = {'operation': 'irmaa', 'year': 2026, 'month': 10, 'state': 'FL', 'county_fips': '12021',
                               'coverage_context': context, 'covered_months': ['2026-10'], 'filing_status': 'married_separate' if filing == 'separate_together' else filing,
                               'lived_together': True, 'magi_cents': threshold * 100 + delta, 'tax_year': 2024,
                               'return_basis': 'normal_2024', 'changed_income': False, 'amended_return': False}
                    cases.append({'id': f'BOUNDARY-{context}-{filing}-{threshold}-{position}', 'request': request,
                                  'expected': {'state': 'conflicting' if conflicting else 'value', **({} if conflicting else {'sum_cents': values[index]})},
                                  'independent_work': 'Retained source table row, independently transcribed band-at/below/above fixture; precision $0.01; evaluator does not read expectation fixture'})
    return cases


def report(package=PACKAGE, write=True):
    package = Path(package)
    m = verify(package, AS_OF)
    service = L01(package, now=lambda: AS_OF)
    cases = case_inventory(package)
    outcomes = []
    for case in cases:
        try:
            result = service.research(case['request'])
        except (L01Error,KeyError,TypeError,OSError):
            outcomes.append({'id':case['id'],'expected':case['expected'],'actual':{'state':'unavailable','error':'Required research input/evidence field unavailable'},'passed':False})
            continue
        actual = {'state': result['state']}
        if 'sum_cents' in case['expected']:
            actual['sum_cents'] = sum(c['value_cents'] for c in result['components'] if c['state'] == 'value')
        if 'benefit_period_ended' in case['expected']:
            actual['benefit_period_ended'] = result.get('benefit_period_ended')
        outcomes.append({'id': case['id'], 'expected': case['expected'], 'actual': actual, 'passed': actual == case['expected']})
    # A separate source parser compares POMS 2026 rows against normalized B/D.
    sources = {s['id']: s for s in load(package / 'sources.json')}
    parser = SourceHTML()
    parser.feed((package / sources['SSA-POMS-TABLE']['extracted_artifact']).read_text())
    tables = [t for t in parser.tables if any('2024 (or 2023' in c for row in t['rows'] for c in row)]
    assert len(tables) == 3, 'POMS 2026 table denominator changed'
    bands = load(package / 'bands.json')
    comparisons = load(package / 'field-comparisons.json')
    poms_checks = []
    for filing, table in zip(['individual', 'joint', 'separate_together'], tables):
        rows = [row for row in table['rows'] if row and row[0].startswith(('More than', 'Greater than'))]
        expected_bands = [b for b in bands if b['coverage_context'] == 'full_b' and b['filing_status'] == filing and b['adjustment_cents'] > 0]
        assert len(rows) == len(expected_bands)
        d_bands = [b for b in bands if b['coverage_context'] == 'part_d' and b['filing_status'] == filing and b['adjustment_cents'] > 0]
        for row, b, d in zip(rows, expected_bands, d_bands):
            import re
            drug_amount = re.search(r'\$\s*([\d,.]+)', row[2]).group(1)
            poms_checks.append({'source_id': 'SSA-POMS-TABLE', 'locator': table['id'] + ' / ' + row[0],
                                'band_ids': [b['id'], d['id']], 'observed_full_b_total_cents': cents(row[1]),
                                'observed_d_adjustment_cents': cents(drug_amount),
                                'equal': b['published_total_cents'] == cents(row[1]) and d['adjustment_cents'] == cents(drug_amount)})
    corroborated = {c['band_id'] for c in comparisons if c['comparison'] == 'equal'}
    corroborated |= {id for c in poms_checks if c['equal'] for id in c['band_ids']}
    obligations = load(package / 'inventory.json')['obligations']
    required_sources = load(package / 'source-obligations.json')['obligations']
    observations = {o['id']:o for o in load(package/'observations.json')}
    records = {**{'fact:'+f['id']:f for f in load(package/'facts.json')},**{'band:'+b['id']:b for b in bands},**{'rule:'+r['id']:r for r in load(package/'rules.json')}}
    def backed(key):
        record=records.get(key)
        if not record:return False
        if key.startswith('rule:'):
            return bool(record.get('conditions') and record.get('source_sections')) and all(sources.get(s['source_id'],{}).get('status')=='acquired' for s in record['source_sections'])
        if key.startswith('fact:') and ('value' not in record or not record.get('period') or not record.get('conditions')):return False
        return bool(record.get('observation_ids')) and all(o in observations and sources.get(observations[o]['source_id'],{}).get('status')=='acquired' for o in record['observation_ids'])
    supported = [o['id'] for o in obligations if o['implementation_status']=='research_supported' and o.get('backing_records') and all(backed(k) for k in o['backing_records'])]
    remaining = [o['id'] for o in obligations if o['id'] not in supported]
    pending_bands = [b['id'] for b in bands if b['id'] not in corroborated]
    annual_maps = [x for x in load(package / 'source-index.json') if x['source_id'] == 'CMS-ANNUAL' and x['disposition'] == 'normalized']
    formal = load(package / 'formal-table-inventory.json')
    coverage = {
        'schema': 'l01-coverage/1', 'package_id': m['package_id'], 'inventory_version': load(package / 'inventory.json')['version'],
        'denominator_policy': 'Declared broad obligations never removed by failure, deferral or lack of evidence. URL discovery attempts reported separately from required documents. Research-supported is structural representation, not completeness of all policy conditions or acceptance.',
        'source_coverage': {'acquired': sum(sources.get(s['source_id'],{}).get('status') == 'acquired' for s in required_sources), 'required': len(required_sources),
                            'missing_ids': [s['id'] for s in required_sources if sources.get(s['source_id'],{}).get('status') != 'acquired'],
                            'all_acquisition_attempts': len(sources), 'superseded_attempts': sum(s['discovery_role'] == 'superseded_attempt' for s in sources.values()),
                            'alternative_representations': sum(s['discovery_role'] == 'alternative_representation' for s in sources.values())},
        'field_coverage': {'structurally_represented_obligations': len(supported), 'required_broad_obligations': len(obligations),
                           'mvp_represented': sum(o['id'] in supported and o['scope'] == 'mvp' for o in obligations),
                           'mvp_required': sum(o['scope'] == 'mvp' for o in obligations),
                           'remaining_obligation_ids': remaining, 'unsupported_or_dependency': len(remaining), 'waived': 0, 'deferred': 0,
                           'exact_locator_or_explicit_gap': len(obligations), 'unresolved_locator_ids': [o['id'] for o in obligations if o['locator_status'] == 'unresolved_locator_gap']},
        'annual_table_reconciliation': {'cms_data_rows_mapped': len(annual_maps), 'cms_expected_data_rows': 27,
                                        'expanded_bands': len(bands), 'required_bands': 45,
                                        'all_bands_have_source_observation': all(b['observation_ids'] for b in bands),
                                        'formal_tables_with_disposition': len(formal), 'formal_table_rows': sum(t['row_count'] for t in formal),
                                        'formal_table_footnotes': sum(len(t['notes']) for t in formal),
                                        'formal_comparisons_equal': sum(c['comparison'] == 'equal' for c in comparisons),
                                        'formal_comparisons_conflicting': sum(c['comparison'] == 'conflict' for c in comparisons)},
        'corroboration': {'bands_compared_equal_to_designated_crosscheck': len(corroborated), 'required_bands': len(bands),
                          'remaining_band_ids': pending_bands, 'poms_high_income_rows_compared': len(poms_checks),
                          'facts_numeric_value_compared':sum(c['comparison']=='equal_value' for c in load(package/'fact-comparisons.json')), 'required_facts':len(load(package/'facts.json')),
                          'facts_remaining_ids':[c['fact_id'] for c in load(package/'fact-comparisons.json') if c['comparison']!='equal_value'],
                          'note': 'Numeric equality does not accept conditions/periods. Agreement corroborates extraction; repeated FR conflicts remain open and cross-publication agreement is not independent human acceptance'},
        'rule_and_case_coverage': {'passed': sum(o['passed'] for o in outcomes), 'required_cases': len(cases),
                                 'income_boundary_cases': sum(c['id'].startswith('BOUNDARY') for c in cases),
                                 'implemented_rules': len(load(package / 'rules.json')), 'bounded_executable_rules_required':6, 'broader_obligations_total': len(obligations),
                                 'note': 'Boundary tests include correctly withheld conflicts; unsupported policy branches remain outside implemented coverage'},
        'conflict_closure': {'accepted_resolutions': 0, 'known_conflicts': len(load(package / 'conflicts.json')), 'proposed_only': ['L01-G03', 'L01-G04', 'L01-G09']},
        'human_acceptance': {'accepted_claims_and_rules': 0, 'required_normalized_claims_and_rules': len(load(package / 'facts.json')) + len(bands) + len(load(package / 'rules.json')), 'accepted_capabilities': 0, 'required_capabilities': len(load(package / 'requirements.json')['capabilities'])},
        'freshness': {'annual_sources_content_year_checked': sum(s.get('content_year_verified') == 2026 for s in sources.values()), 'raw_receipts_integrity_checked': sum(s['status'] == 'acquired' for s in sources.values()),
                      'source_review_after_utc': m['source_review_after_utc'], 'independent_review_current': 0, 'manual_temporal_status': 'Section revision headers retained; no global 2026 applicability approval'},
        'runtime_enabled_capabilities': 0, 'broader_layer_status': 'partial', 'recommendations_available': False,
    }
    validation = {'as_of_utc': AS_OF.isoformat(), 'manifest_integrity': 'passed', 'case_results': outcomes, 'poms_comparisons': poms_checks,
                  'source_to_dataset_and_dataset_to_source': 'CMS tables fully mapped; formal tables include operational exclusions; unresolved service locators explicitly listed',
                  'all_case_checks_passed': all(o['passed'] for o in outcomes) and all(c['equal'] for c in poms_checks)}
    if write:
        dump(package / 'coverage.json', coverage)
        dump(package / 'validation.json', validation)
        # Case inventory is a report, not mutable acceptance or a new data input.
        dump(package / 'qa/case-inventory.json', cases)
    return coverage, validation


if __name__ == '__main__':
    c, v = report()
    print(json.dumps({k: c[k] for k in ['source_coverage', 'rule_and_case_coverage', 'corroboration']}, indent=2))
    if not v['all_case_checks_passed']:
        raise SystemExit('L01 case or source-comparison failure')
