"""Fictional contracts: structural comparisons do not establish real authority."""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
ENGINE = HERE.parent / 'chat-first' / 'cms-slice'
sys.path.insert(0, str(ENGINE / 'scripts'))
sys.path.insert(0, str(HERE))

from comparison_evidence import (ComparisonEvidenceError, EvidenceSnapshot, HeldEvidenceSource,
                                 canonical_sha256, read_snapshot)
from comparison_engine import (ComparisonError, QUESTION_IDS, build_comparison,
                               compare_dimension_values, evaluate_conditions)
from comparison_profile import build_comparison_profile
from natural_state import ensure_state

NOW = '2026-11-01T15:00:00+00:00'


def profile(task='compare'):
    guide = {'schemaVersion': 2, 'stateVersion': 0, 'fields': {}}
    record = json.loads((ENGINE / 'config/profile/customer-profile.template.json').read_text())['readiness']
    ensure_state(record)
    record['conversation'] = {'task': task, 'preparing': True}
    return build_comparison_profile(guide, record)


def rebind(case):
    for q in case['questions']:
        rows = [f for f in case['facts'] if f['ref']['path'] in q['canonical_paths']]
        q['fact_refs'] = [copy.deepcopy(f['ref']) for f in rows]
        q['report_states'] = sorted({f['report_state'] for f in rows})
    case['profile_binding'].pop('normalized_sha256', None)
    case['profile_binding']['normalized_sha256'] = canonical_sha256(case)
    return case


def fact(case, path, value, state='reported', item=None, revision=1, scope='current'):
    row = next(f for f in case['facts'] if f['ref']['path'] == path)
    row.update(value=value, report_state=state, usable_as_report=state in {'reported', 'explicit_none'},
               usable_for_bound_subject=state in {'reported', 'explicit_none'}, capture_subject='beneficiary',
               capture_method='direct_report', temporal_scope=scope)
    row['ref'].update(item_id=item, report_revision=revision, record_revision=revision, scope=scope)
    rebind(case)
    return row


def conditions(evaluation='true'):
    return {'completeness': 'complete', 'root': {'op': 'predicate', 'id': 'fixture:condition',
            'evaluation': evaluation, 'source_locator': 'fixture:document/page-1',
            'technical_context': 'Fictional test condition; no real policy.'},
            'missing_predicates': []}


def amount(value, **changes):
    return {'type': 'decimal', 'amount': value, 'currency': 'USD', 'unit': 'plan_premium',
            'period': 'month', 'cost_type': 'published_component',
            'scope_key': 'fixture:same-role-scope', 'population_basis': 'published',
            'network': None, 'channel': None, 'phase': None,
            'included_components': ['plan_premium'], 'excluded_components': ['care', 'drugs'],
            'assumptions': [], **changes}


class FictionalSource:
    """Test-local data only; this provider is never available through the app."""
    def __init__(self, *, reverse=False, source_kind='fictional_fixture'):
        self.units = [{'unit_id': 'fixture:a', 'kind': 'fictional_unit', 'fictional': True},
                      {'unit_id': 'fixture:b', 'kind': 'fictional_unit', 'fictional': True}]
        if reverse:
            self.units.reverse()
        self.rows = [{'unit_id': identifier, 'dimension_id': 'monthly_plan_premium',
                      'result': 'supports', 'value': amount(value),
                      'condition_set': conditions(), 'evidence_state': 'reviewed',
                      'policy_state': 'reviewed_for_exact_purpose', 'source_use_state': 'fixture_only',
                      'evidence_refs': ['fixture:observation'], 'rule_refs': ['fixture:comparator']}
                     for identifier, value in [('fixture:a', '0.10'), ('fixture:b', '0.30')]]
        self.source_kind = source_kind

    def snapshot(self, scope):
        return EvidenceSnapshot(manifest_id='fixture:manifest', source_kind=self.source_kind,
                                completeness='complete', units=tuple(self.units), observations=tuple(self.rows))


class ComparisonEngineTests(unittest.TestCase):
    def test_actual_adapter_empty_case_accounts_all_41_without_completion_claim(self):
        out = build_comparison(profile(), generated_at=NOW)
        rows = out['decision_record']['question_accounting']
        self.assertEqual([r['question_id'] for r in rows], list(QUESTION_IDS))
        self.assertEqual(len(rows), 41)
        self.assertTrue(all(not r['additional_alias_obligation'] for r in rows))
        self.assertIsNone(out['next_question'])
        self.assertFalse(out['personalized_recommendation_allowed'])
        self.assertEqual(out['universe']['evaluated_count'], 0)
        self.assertEqual([u['kind'] for u in out['units']], ['current_arrangement'])

    def test_default_has_no_release_and_all_independent_purposes_held(self):
        out = build_comparison(profile(), generated_at=NOW)
        self.assertEqual(len(out['authority']), 6)
        self.assertTrue(all(x['state'] == 'held' for x in out['authority'].values()))
        self.assertIsNone(out['binding']['accepted_release_id'])
        self.assertEqual(out['tradeoffs'], [])
        self.assertTrue(all(f['value'] is None and f['output_state'] == 'held' for f in out['findings']))
        self.assertTrue(all(not w['external_action_completed'] for w in out['work_items']))
        self.assertEqual({x['kind'] for x in out['outcomes']}, {'continue_checking', 'keep_current', 'defer_decision'})

    def test_case_release_flags_never_release_evidence_or_copy_fake_plans(self):
        case = profile()
        expected = build_comparison(case, generated_at=NOW)
        case.update(authority={'recommendation': {'state': 'permitted'}},
                    accepted_release_id='pretend', source_kind='fictional_fixture',
                    units=[{'unit_id': 'pretend-real-plan'}])
        self.assertEqual(build_comparison(case, generated_at=NOW), expected)

    def test_dictionary_provider_and_nonnull_release_are_rejected(self):
        with self.assertRaisesRegex(ComparisonEvidenceError, 'SERVER_EVIDENCE_SOURCE_REQUIRED'):
            build_comparison(profile(), {'authority': 'permitted'}, NOW)
        class Bad(HeldEvidenceSource):
            def snapshot(self, scope):
                return EvidenceSnapshot(accepted_release_id='forged')
        with self.assertRaisesRegex(ComparisonEvidenceError, 'UNSUPPORTED_EVIDENCE_SNAPSHOT'):
            build_comparison(profile(), Bad(), NOW)

    def test_research_records_cannot_become_consumer_units_even_if_reviewed(self):
        out = build_comparison(profile(), FictionalSource(source_kind='research_held'), NOW)
        self.assertFalse(out['fictional'])
        self.assertEqual(len(out['units']), 1)
        self.assertEqual(out['tradeoffs'], [])
        self.assertTrue(all(f['result'] == 'unresolved' for f in out['findings']))

    def test_fictional_comparisons_keep_source_order_and_never_grant_real_authority(self):
        out = build_comparison(profile(), FictionalSource(reverse=True), NOW)
        self.assertTrue(out['fictional'])
        self.assertEqual([u['unit_id'] for u in out['units'][1:]], ['fixture:b', 'fixture:a'])
        trade = next(t for t in out['tradeoffs'] if t['dimension_id'] == 'monthly_plan_premium')
        self.assertEqual(trade['relation'], 'left_higher')
        self.assertEqual(trade['difference'], '0.20')
        self.assertEqual(trade['overall_relation'], 'tradeoff_or_unresolved')
        self.assertIsNone(out['universe']['automatic_personal_order'])
        self.assertIsNone(out['binding']['accepted_release_id'])
        self.assertTrue(all(a['state'] == 'held' for a in out['authority'].values()))

    def test_integrity_hold_blocks_supports_and_fixture_values(self):
        case = profile()
        case['integrity_issues'] = [{'code': 'PROVENANCE_REVISION_MISMATCH', 'path': 'fixture:path', 'severity': 'hold'}]
        out = build_comparison(case, FictionalSource(), NOW)
        self.assertTrue(all(f['result'] == 'unresolved' and f['value'] is None for f in out['findings']))
        self.assertTrue(all(t['relation'] == 'unresolved' for t in out['tradeoffs']))

    def test_learner_and_unscoped_legacy_reports_never_satisfy_beneficiary_findings(self):
        for subject, usable in [('learner', True), ('learner', False), ('beneficiary', False)]:
            with self.subTest(subject=subject):
                case = profile()
                provider = fact(case, 'readiness.facts.RC21.value.items[].practice', 'fixture:learner-office', item='doctor-1')
                medicine = fact(case, 'readiness.facts.RC22.value.items[].strength', 'fixture:learner-strength', item='medicine-1')
                coverage = fact(case, 'guide.fields.coverage.current', ['fixture:learner-coverage'])
                for row in (provider, medicine, coverage):
                    row['ref']['subject_id'] = subject
                    row['usable_for_bound_subject'] = usable
                    row['capture_subject'] = 'learner' if subject == 'learner' else 'unknown'
                rebind(case)
                source = FictionalSource()
                source.rows.append({'unit_id': 'fixture:a', 'dimension_id': 'coverage_structure',
                    'result': 'supports', 'value': amount('0'), 'condition_set': conditions(),
                    'policy_state': 'reviewed_for_exact_purpose', 'evidence_state': 'reviewed',
                    'source_use_state': 'fixture_only', 'evidence_refs': ['fixture:evidence'],
                    'rule_refs': ['fixture:rule'], 'required_report_refs': [coverage['ref']]})
                out = build_comparison(case, source, NOW)
                self.assertEqual(out['units'][0]['identity_state'], 'unknown')
                relevant = [f for f in out['findings'] if f['dimension_id'] in {'coverage_structure', 'provider_access', 'drug_coverage'}]
                self.assertTrue(all(f['report_refs'] == [] and f['result'] != 'supports' for f in relevant))
                self.assertNotIn('fixture:learner-', json.dumps(out))

    def test_all14_gaps_remain_open_and_material_question_gaps_reach_work_items(self):
        case = profile('timing')
        out = build_comparison(case, generated_at=NOW)
        ledger = out['decision_record']['gap_accounting']
        self.assertEqual({g['gap_id'] for g in ledger}, {f'G{x:02d}' for x in range(1, 15)})
        self.assertTrue(all(not g['gap_closed'] for g in ledger))
        finding = next(f for f in out['findings'] if f['dimension_id'] == 'eligibility_transition')
        self.assertTrue({'RC10', 'RC13', 'RC14', 'RC27'}.issubset(finding['question_ids']))
        self.assertTrue({'G01', 'G02', 'G07', 'G10'}.issubset(finding['gap_ids']))
        work = next(w for w in out['work_items'] if w['dimension_id'] == 'eligibility_transition')
        self.assertEqual(work['gap_ids'], finding['gap_ids'])
        medigap = build_comparison(profile('medigap'), generated_at=NOW)
        finding = next(f for f in medigap['findings'] if f['dimension_id'] == 'eligibility_transition')
        self.assertTrue({'RC17', 'RC16.C1', 'RC16.C2'}.issubset(finding['question_ids']))
        self.assertNotIn('RC14', finding['question_ids'])

    def test_missing_required_fixture_input_does_not_produce_a_finding(self):
        case, source = profile(), FictionalSource()
        source.rows[0]['required_report_refs'] = [case['facts'][0]['ref']]
        out = build_comparison(case, source, NOW)
        f = next(f for f in out['findings'] if f['unit_id'] == 'fixture:a' and f['dimension_id'] == 'monthly_plan_premium')
        self.assertEqual(f['result'], 'unresolved')
        self.assertIn('INPUT_PRECISION_MISSING', f['reason_codes'])

    def test_exact_decimal_difference_and_incompatible_cost_scopes(self):
        self.assertEqual(compare_dimension_values(amount('0.10'), amount('0.30'))['difference'], '-0.20')
        for changed in [amount('0.30', period='year'), amount('0.30', scope_key='fixture:other'),
                        amount('0.30', included_components=['all_costs']), amount(None),
                        amount(float('nan')), amount('NaN')]:
            with self.subTest(changed=changed):
                self.assertEqual(compare_dimension_values(amount('0.10'), changed)['relation'], 'unresolved')
        self.assertEqual(compare_dimension_values(amount('0'), amount('0.00'))['relation'], 'equal')
        self.assertEqual(compare_dimension_values(amount('123456789012345678901234567890.10'),
            amount('123456789012345678901234567890.30'))['difference'], '-0.20')

    def test_priorities_are_explicit_unordered_emphasis_not_constraints_or_ranking(self):
        case = profile()
        p = fact(case, 'guide.fields.needs.priorities', ['travel', 'doctors'], revision=3)
        fact(case, 'guide.fields.needs.costPreference', 'predictable')
        fact(case, 'readiness.facts.RC25.value.amount', '100')
        case['extensions']['agenda']['priorityReasons'] = [
            {'topic': 'doctors', 'reason': 'Fictional stated continuity priority.', 'subject': 'beneficiary',
             'scope': 'current', 'priorityRevision': 3, 'revision': 1},
            {'topic': 'travel', 'reason': 'Fictional stale reason.', 'subject': 'beneficiary',
             'scope': 'current', 'priorityRevision': 2, 'revision': 1}]
        rebind(case)
        out = build_comparison(case, FictionalSource(reverse=True), NOW)
        context = out['preference_context']
        self.assertEqual(context['ordering'], 'unordered_set')
        self.assertEqual(context['priority_topics'], ['doctors', 'travel'])
        self.assertEqual([r['topic'] for r in context['current_priority_reasons']], ['doctors'])
        self.assertFalse(context['hard_constraints_evaluated'])
        self.assertIsNone(context['inferred_weights'])
        self.assertEqual(context['constraint_evaluation']['gap_ids'], ['G12'])
        self.assertEqual(next(d for d in out['dimensions'] if d['dimension_id'] == 'provider_access')['user_relevance'], 'explicit_preference_emphasis')
        self.assertEqual([u['unit_id'] for u in out['units'][1:]], ['fixture:b', 'fixture:a'])
        p['ref']['subject_id'] = 'learner'; p['usable_for_bound_subject'] = False
        rebind(case)
        self.assertEqual(build_comparison(case, generated_at=NOW)['preference_context']['priority_topics'], [])

    def test_incomplete_empty_conflicting_and_nested_conditions(self):
        self.assertEqual(evaluate_conditions({'completeness': 'complete', 'predicates': []}), 'unknown')
        c = conditions(); c['missing_predicates'] = ['fixture:missing']
        self.assertEqual(evaluate_conditions(c), 'unknown')
        c = conditions('conflicting')
        self.assertEqual(evaluate_conditions(c), 'conflicting')
        c = conditions(); c['root'] = {'op': 'and', 'children': [conditions()['root'],
            {'op': 'not', 'children': [conditions('false')['root']]}]}
        self.assertEqual(evaluate_conditions(c), 'true')

    def test_conditions_and_native_qualifications_survive_but_unknown_is_not_conflict(self):
        source = FictionalSource()
        source.rows[0]['condition_set']['missing_predicates'] = ['fixture:required-exception']
        out = build_comparison(profile(), source, NOW)
        f = next(f for f in out['findings'] if f['unit_id'] == 'fixture:a' and f['dimension_id'] == 'monthly_plan_premium')
        self.assertEqual(f['condition_set'], source.rows[0]['condition_set'])
        self.assertEqual(f['result'], 'unresolved')
        self.assertIsNone(f['value'])

    def test_unknown_and_explicit_none_have_different_requirement_semantics(self):
        case = profile('providers')
        fact(case, 'guide.fields.needs.providersStatus', 'none', 'explicit_none')
        out = build_comparison(case, generated_at=NOW)
        f = next(f for f in out['findings'] if f['dimension_id'] == 'provider_access')
        self.assertEqual(f['result'], 'not_applicable')
        self.assertEqual(f['condition_set']['scope'], 'reported_requirement_only_not_external_care_needs')
        fact(case, 'guide.fields.needs.providersStatus', 'unknown', 'unknown')
        f = next(f for f in build_comparison(case, generated_at=NOW)['findings'] if f['dimension_id'] == 'provider_access')
        self.assertEqual(f['result'], 'unresolved')

    def test_user_question_must_come_from_current_controller_and_match_task(self):
        case = profile('providers')
        q = {'id': 'RC21', 'entity': 'doctor-1', 'question': 'Which office should we check?',
             'fields': [{'key': 'practice'}]}
        out = build_comparison(case, generated_at=NOW, eligible_questions=[q])
        self.assertEqual(out['next_question']['question_id'], 'RC21')
        self.assertEqual(out['next_question']['item_id'], 'doctor-1')
        self.assertTrue(out['next_question']['answer_cannot_verify_external_evidence'])
        self.assertIsNone(build_comparison(case, generated_at=NOW)['next_question'])
        self.assertIsNone(build_comparison(case, generated_at=NOW, eligible_questions=[{'id': 'RC14'}])['next_question'])

    def test_known_unknown_or_deferred_target_is_not_asked_again(self):
        case = profile('medigap')
        path = 'readiness.facts.RC16.value.start'
        q = {'id': 'RC16.C1', 'fields': [{'key': 'start'}], 'question': 'Relevant episode start?'}
        for state, value in [('reported', '2025-05'), ('unknown', 'unknown'), ('deferred', 'later')]:
            fact(case, path, value, state)
            with self.subTest(state=state):
                out = build_comparison(case, generated_at=NOW, eligible_questions=[q])
                self.assertIsNone(out['next_question'])
                self.assertTrue(out['work_items'])
        self.assertEqual(next(r for r in out['decision_record']['question_accounting'] if r['question_id'] == 'RC16.C1')['additional_alias_obligation'], False)

    def test_question_fallback_is_stable_and_preserves_orientation(self):
        case = profile('compare')
        a, b = {'id': 'T06', 'question': 'Providers?'}, {'id': 'T07', 'question': 'Medicines?'}
        one = build_comparison(case, generated_at=NOW, eligible_questions=[b, a])
        two = build_comparison(case, generated_at=NOW, eligible_questions=[a, b])
        self.assertEqual(one, two)
        self.assertEqual(one['next_question']['question_id'], 'T06')
        self.assertEqual(build_comparison(profile('timing'), generated_at=NOW,
            eligible_questions=[{'id': 'T02', 'question': 'Familiarity?'}])['next_question']['question_id'], 'T02')

    def test_revisions_invalidate_result_binding_without_mutating_source(self):
        case = profile(); before = copy.deepcopy(case)
        a = build_comparison(case, generated_at=NOW)
        self.assertEqual(case, before)
        self.assertEqual(a, build_comparison(case, generated_at=NOW))
        fact(case, 'readiness.facts.RC22.value.items[].strength', '5 mg', item='medicine-1')
        b = build_comparison(case, generated_at=NOW)
        self.assertNotEqual(a['comparison_id'], b['comparison_id'])
        self.assertFalse(b['validity']['stale_action_replay_allowed'])
        self.assertNotIn('5 mg', json.dumps(b))

    def test_commercial_canaries_are_rejected_and_unknown_source_keys_not_projected(self):
        case = profile(); case['commission'] = 'fixture:canary'
        with self.assertRaisesRegex(ComparisonEvidenceError, 'ECONOMIC_CONTEXT_FORBIDDEN'):
            build_comparison(case, generated_at=NOW)
        source = FictionalSource(); source.units[0]['payout'] = 'fixture:canary'
        with self.assertRaisesRegex(ComparisonEvidenceError, 'ECONOMIC_CONTEXT_FORBIDDEN'):
            build_comparison(profile(), source, NOW)
        source = FictionalSource(); source.units[0]['unreviewed_proxy'] = 'fixture:canary'
        with self.assertRaisesRegex(ComparisonEvidenceError, 'UNSUPPORTED_EVIDENCE_UNIT'):
            build_comparison(profile(), source, NOW)
        source = FictionalSource(); source.rows[0]['value']['unreviewed_proxy'] = 'fixture:canary'
        with self.assertRaisesRegex(ComparisonEvidenceError, 'UNSUPPORTED_TYPED_EVIDENCE_VALUE'):
            build_comparison(profile(), source, NOW)

    def test_malformed_all41_and_wrong_alias_fail_closed(self):
        case = profile(); case['questions'][0] = copy.deepcopy(case['questions'][1])
        with self.assertRaisesRegex(ComparisonError, 'PROFILE_CONTRACT_MISMATCH'):
            build_comparison(case, generated_at=NOW)
        case = profile(); case['questions'][-1]['parent_alias_of'] = 'RC11'
        with self.assertRaisesRegex(ComparisonError, 'PROFILE_QUESTION_BINDING_MISMATCH'):
            build_comparison(case, generated_at=NOW)

    def test_snapshot_digest_and_response_change_on_source_revision(self):
        source = FictionalSource()
        one = build_comparison(profile(), source, NOW)
        source.rows[0]['value']['amount'] = '0.20'
        two = build_comparison(profile(), source, NOW)
        self.assertNotEqual(one['binding']['evidence_sha256'], two['binding']['evidence_sha256'])
        self.assertNotEqual(one['comparison_id'], two['comparison_id'])
        source.units[0]['fictional'] = False
        with self.assertRaisesRegex(ComparisonEvidenceError, 'FICTIONAL_IDENTITY_REQUIRED'):
            read_snapshot(source)


if __name__ == '__main__':
    unittest.main()
