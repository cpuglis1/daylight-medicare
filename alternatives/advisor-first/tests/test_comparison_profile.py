"""Synthetic, store-free tests for the additive comparison profile view."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_profile import (ADAPTER_VERSION, CONTRACT_PATH, ComparisonProfileError,
                                build_comparison_profile, _digest)
from natural_state import ensure_state, legacy_projection, record_capture

TEMPLATE = json.loads((HERE.parent / 'chat-first/cms-slice/config/profile/customer-profile.template.json').read_text())


def envelope(value, revision=1, **extra):
    return {'value': value, 'status': 'reported', 'source': 'user_text',
            'confirmation': 'confirmed_by_user', 'revision': revision, **extra}


class ComparisonProfileTests(unittest.TestCase):
    def setUp(self):
        self.guide = copy.deepcopy(TEMPLATE['guide'])
        self.record = copy.deepcopy(TEMPLATE['readiness'])

    def build(self, **kwargs):
        return build_comparison_profile(self.guide, self.record, **kwargs)

    def fact(self, result, path, item=None):
        return next(f for f in result['facts'] if f['ref']['path'] == path and f['ref']['item_id'] == item)

    def guide_report(self, name, value, method='direct_report', **scope):
        old_g, old_r = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        self.guide['stateVersion'] += 1
        self.guide['fields'][name] = envelope(value, self.guide['stateVersion'])
        record_capture(self.guide, self.record, old_g, old_r, scope, method=method)

    def test_empty_profile_preserves_all_41_78_14_and_aliases(self):
        result = self.build()
        self.assertEqual(len(result['questions']), 41)
        self.assertEqual(len(result['contract']['baseline_paths']), 78)
        self.assertEqual(len(result['gap_reports']), 14)
        self.assertEqual(len(result['contract']['clarification_variants']), 11)
        self.assertTrue(all(f['report_state'] == 'unanswered' for f in result['facts']))
        self.assertFalse(any(f['externally_verified'] for f in result['facts']))
        by_id = {q['id']: q for q in result['questions']}
        for child, parent, field in [('RC11.C1', 'RC11', 'coverageEnd'),
                                     ('RC16.C1', 'RC16', 'start'), ('RC16.C2', 'RC16', 'priorMedigap')]:
            alias = by_id[child]
            self.assertEqual(alias['parent_alias_of'], parent)
            self.assertTrue(alias['alias_reused'])
            self.assertEqual(alias['fact_refs'], [x for x in by_id[parent]['fact_refs'] if x['path'].endswith('.' + field)])

    def test_direct_and_explicit_confirmation_survive_legacy_projection_honestly(self):
        self.guide_report('coverage.current', ['employer'])
        self.guide_report('needs.priorities', ['doctors'], method='explicit_confirmation')
        original = self.build()
        direct = self.fact(original, 'guide.fields.coverage.current')
        self.assertEqual((direct['capture_method'], direct['confirmation_state']), ('direct_report', 'reported_by_user'))
        self.assertEqual(direct['ref']['scope'], 'current')
        confirmed = self.fact(original, 'guide.fields.needs.priorities')
        self.assertEqual(confirmed['confirmation_state'], 'explicitly_confirmed')
        wire_g, wire_r = legacy_projection(self.guide, self.record)
        wire_r['natural'] = copy.deepcopy(self.record['natural'])
        wire = build_comparison_profile(wire_g, wire_r)
        self.assertEqual(wire['facts'], original['facts'])
        self.assertFalse(any(f['externally_verified'] for f in wire['facts']))

    def test_old_wire_confirmation_is_not_upgraded(self):
        self.guide['stateVersion'] = 1
        self.guide['fields']['coverage.current'] = envelope(['original'])
        fact = self.fact(self.build(), 'guide.fields.coverage.current')
        self.assertEqual(fact['confirmation_state'], 'legacy_unclassified')
        self.assertEqual(fact['capture_method'], 'legacy_unclassified')
        self.assertEqual(fact['temporal_scope'], 'unknown')
        self.assertEqual(fact['capture_subject'], 'unknown')
        self.assertEqual(fact['value'], ['original'])
        self.assertFalse(fact['usable_for_bound_subject'])

    def test_learner_report_is_retained_without_beneficiary_applicability(self):
        self.guide_report('coverage.current', ['original'], subject='learner')
        self.guide_report('knowledge.general', 'new', subject='learner')
        result = self.build(subject_id='synthetic-beneficiary')
        for path in ['guide.fields.coverage.current', 'guide.fields.knowledge.general']:
            fact = self.fact(result, path)
            self.assertEqual(fact['ref']['subject_id'], 'learner')
            self.assertEqual(fact['capture_subject'], 'learner')
            self.assertEqual(fact['report_state'], 'reported')
            self.assertTrue(fact['usable_as_report'])
            self.assertFalse(fact['usable_for_bound_subject'])
        self.assertEqual(result['profile_binding']['subject_id'], 'synthetic-beneficiary')

    def test_stale_role_mirror_is_not_an_active_subject_binding(self):
        self.guide_report('subject.role', 'self')
        self.guide['fields']['subject.role']['status'] = 'unknown'
        result = self.build()
        self.assertIsNone(result['profile_binding']['subject_role'])
        self.assertEqual(result['extensions']['subject_role_mirror']['value'], 'self')
        self.assertEqual(result['extensions']['subject_role_mirror']['report_state'], 'unknown')

    def test_untracked_or_mismatched_natural_confirmation_holds_only_affected_report(self):
        self.guide['stateVersion'] = 1
        self.guide['fields']['coverage.current'] = envelope(['original'], confirmation='reported_by_user')
        result = self.build()
        self.assertEqual(self.fact(result, 'guide.fields.coverage.current')['report_state'], 'conflicting')
        self.assertEqual(result['integrity_issues'][0]['code'], 'UNTRACKED_NATURAL_CONFIRMATION')
        ensure_state(self.record)['provenance']['guide.coverage.current'] = {
            'method': 'direct_report', 'status': 'user_reported', 'subject': 'beneficiary',
            'scope': 'current', 'revision': 2, 'supersedesRevision': None}
        result = self.build()
        self.assertFalse(self.fact(result, 'guide.fields.coverage.current')['usable_as_report'])
        self.assertIn('PROVENANCE_REVISION_MISMATCH', {x['code'] for x in result['integrity_issues']})

    def test_disagreeing_natural_confirmation_is_held(self):
        self.guide_report('coverage.current', ['original'])
        self.guide['fields']['coverage.current']['confirmation'] = 'explicitly_confirmed'
        result = self.build()
        self.assertEqual(self.fact(result, 'guide.fields.coverage.current')['report_state'], 'conflicting')
        self.assertIn('PROVENANCE_CONFIRMATION_MISMATCH', {x['code'] for x in result['integrity_issues']})

    def test_item_identity_field_revision_and_scoped_fill_invalidation(self):
        self.record['stateVersion'] = 6
        self.record['facts']['RC22'] = envelope({'choice': 'details', 'items': [
            {'entity': 'medicine-1', 'name': 'Synthetic same name', 'strength': '5 mg', 'form': 'tablet'},
            {'entity': 'medicine-2', 'name': 'Synthetic same name', 'strength': '10 mg', 'form': 'tablet'}]}, 6)
        self.record['facts']['RC23'] = envelope({'choice': 'details', 'items': [
            {'entity': 'medicine-1', 'quantity': '30 tablets', 'daysSupply': '30'},
            {'entity': 'medicine-2', 'quantity': '30 tablets', 'daysSupply': '30'}]}, 5)
        self.record['conversation'] = {'itemRevisions': {'RC23.medicine-1': 4, 'RC23.medicine-2': 5},
            'itemInvalidations': {'RC23.medicine-1': 6}, 'skippedDetails': {'RC22.medicine-1.brand': 'unknown'}}
        ensure_state(self.record)['provenance']['readiness.RC22.medicine-1.name'] = {
            'method': 'direct_report', 'status': 'user_reported', 'subject': 'beneficiary',
            'scope': 'current', 'revision': 2, 'supersedesRevision': 1}
        result = self.build()
        first = self.fact(result, 'readiness.facts.RC22.value.items[].name', 'medicine-1')
        second = self.fact(result, 'readiness.facts.RC22.value.items[].strength', 'medicine-2')
        self.assertEqual(first['ref']['report_revision'], 2)
        self.assertEqual(first['supersedes_ref']['report_revision'], 1)
        self.assertEqual(second['value'], '10 mg')
        self.assertEqual(self.fact(result, 'readiness.facts.RC22.value.items[].brand', 'medicine-1')['report_state'], 'unknown')
        self.assertEqual(self.fact(result, 'readiness.facts.RC23.value.items[].quantity', 'medicine-1')['report_state'], 'stale')
        self.assertEqual(self.fact(result, 'readiness.facts.RC23.value.items[].quantity', 'medicine-2')['report_state'], 'reported')
        self.assertTrue(first['usable_as_report'])

    def test_unknown_defer_partial_fields_explicit_none_and_zero_stay_distinct(self):
        self.record['stateVersion'] = 2
        self.record['dispositions'] = {'RC01': {'state': 'explicit_unknown'}, 'RC11': {'state': 'explicit_unknown'}}
        self.record['conversation'] = {'baselineDispositions': {'T03': 'deferred'},
            'skippedDetails': {'RC11.profile.coverageEnd': 'unknown'}}
        self.record['facts']['RC11'] = envelope({'choice': 'dates', 'jobEnd': '2026-12'}, 1)
        self.record['facts']['RC25'] = envelope({'choice': 'amount', 'amount': '0', 'includes': 'premiums'}, 2)
        self.guide['stateVersion'] = 1
        self.guide['fields']['needs.medicinesStatus'] = envelope('no')
        result = self.build()
        self.assertEqual(self.fact(result, 'readiness.facts.RC01.value.choice')['report_state'], 'unknown')
        self.assertEqual(self.fact(result, 'guide.fields.comparison.scope.zip')['report_state'], 'deferred')
        self.assertEqual(self.fact(result, 'readiness.facts.RC11.value.jobEnd')['report_state'], 'reported')
        self.assertEqual(self.fact(result, 'readiness.facts.RC11.value.coverageEnd')['report_state'], 'unknown')
        self.assertEqual(self.fact(result, 'guide.fields.needs.medicinesStatus')['report_state'], 'explicit_none')
        self.assertEqual(self.fact(result, 'readiness.facts.RC25.value.amount')['value'], '0')
        self.assertEqual(self.fact(result, 'readiness.facts.RC25.value.amount')['report_state'], 'reported')

    def test_advisor_circumstances_and_soonest_do_not_invent_dates_or_coverage(self):
        self.guide_report('situation.age65', {'month': 11, 'year': None})
        self.guide_report('situation.retirement', {'status': 'retired', 'when': ''})
        self.guide_report('coverage.requestedStart', 'soonest', scope='intended')
        result = self.build(requested_scope={'year': 2026, 'county_fips': '12021'})
        age = result['extensions']['situation']['age65']
        self.assertEqual(age['precision'], 'month_without_year')
        self.assertEqual(age['known_parts'], ['month'])
        self.assertEqual(age['missing_parts'], ['year'])
        self.assertEqual(self.fact(result, 'guide.fields.coverage.requestedStart')['precision'], 'preference_without_date')
        self.assertEqual(self.fact(result, 'guide.fields.coverage.current')['report_state'], 'unanswered')
        self.assertEqual(self.fact(result, 'readiness.facts.RC03.value.year')['report_state'], 'unanswered')
        self.assertEqual(len(result['contract']['baseline_paths']), 78)

    def test_priority_reasons_are_revision_bound_and_dialogue_never_becomes_fact(self):
        self.guide_report('needs.priorities', ['doctors'])
        natural = ensure_state(self.record)
        natural['dialogue']['explainedTopics'] = ['costs']
        natural['agenda'] = {'version': 1, 'concerns': [], 'lastMove': None, 'priorityReasons': [{
            'topic': 'doctors', 'reason': 'Synthetic explicit priority reason', 'subject': 'beneficiary',
            'scope': 'current', 'priorityRevision': 1, 'revision': 1}]}
        self.assertEqual(len(self.build()['extensions']['agenda']['priorityReasons']), 1)
        self.guide['stateVersion'] = 2
        self.guide['fields']['needs.priorities']['revision'] = 2
        result = self.build()
        self.assertEqual(result['extensions']['agenda']['priorityReasons'], [])
        self.assertIn('STALE_PRIORITY_REASON', {x['code'] for x in result['integrity_issues']})
        self.assertFalse(any('explainedTopics' in f['ref']['path'] for f in result['facts']))

    def test_gap_notes_retain_entity_and_revision_without_closing_gap(self):
        self.record['stateVersion'] = 3
        self.record['conversation'] = {'details': {'G05': [{'value': 'Synthetic unlisted office',
            'entity': 'doctor-1', 'revision': 3, 'source': 'user_choice', 'confirmation': 'confirmed_by_user'}]}}
        gap = next(x for x in self.build()['gap_reports'] if x['id'] == 'G05')
        self.assertFalse(gap['gap_closed'])
        self.assertEqual(gap['reports'][0]['ref']['item_id'], 'doctor-1')
        self.assertEqual(gap['reports'][0]['ref']['report_revision'], 3)
        self.assertFalse(gap['reports'][0]['externally_verified'])

    def test_inputs_are_unchanged_and_raw_history_text_is_not_exported(self):
        self.guide_report('coverage.current', ['original'])
        self.guide['fields']['coverage.current']['rawText'] = 'RAW_PRIVATE_CANARY'
        self.guide['fields']['chat.draft'] = envelope('DRAFT_PRIVATE_CANARY')
        self.record['history'] = [{'previous': 'HISTORY_PRIVATE_CANARY'}]
        before = copy.deepcopy((self.guide, self.record))
        first, second = self.build(), self.build()
        self.assertEqual((self.guide, self.record), before)
        self.assertEqual(first['profile_binding']['normalized_sha256'], second['profile_binding']['normalized_sha256'])
        serialized = json.dumps(first)
        for word in ['RAW_PRIVATE_CANARY', 'DRAFT_PRIVATE_CANARY', 'HISTORY_PRIVATE_CANARY']:
            self.assertNotIn(word, serialized)
        self.assertEqual(first['adapter_version'], ADAPTER_VERSION)

    def test_duplicate_items_future_revisions_and_scope_authority_cannot_silently_pass(self):
        self.record['stateVersion'] = 1
        self.record['facts']['RC22'] = envelope({'items': [{'entity': 'medicine-1'}, {'entity': 'medicine-1'}]})
        with self.assertRaises(ComparisonProfileError):
            self.build()
        self.record['facts'] = {}
        self.guide['fields']['coverage.current'] = envelope(['original'], revision=1)
        result = self.build()
        self.assertFalse(self.fact(result, 'guide.fields.coverage.current')['usable_as_report'])
        self.assertIn('REPORT_REVISION_AHEAD_OF_RECORD', {x['code'] for x in result['integrity_issues']})
        with self.assertRaises(ComparisonProfileError):
            self.build(requested_scope={'personal_recommendations_enabled': True})

    def test_contract_load_and_digest_failures_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing.json'
            with patch('comparison_profile.CONTRACT_PATH', path), self.assertRaises(ComparisonProfileError) as caught:
                self.build()
            self.assertEqual(caught.exception.code, 'PROFILE_CONTRACT_UNAVAILABLE')
            document = json.loads(CONTRACT_PATH.read_text())
            document['counts']['question_definitions'] = 42
            path.write_text(json.dumps(document))
            with patch('comparison_profile.CONTRACT_PATH', path), self.assertRaises(ComparisonProfileError) as caught:
                self.build()
            self.assertEqual(caught.exception.code, 'PROFILE_CONTRACT_DIGEST_MISMATCH')
            document['source_bindings']['adaptive']['path'] = '.env'
            document['content_sha256'] = _digest({k: v for k, v in document.items() if k != 'content_sha256'})
            path.write_text(json.dumps(document))
            with patch('comparison_profile.CONTRACT_PATH', path), self.assertRaises(ComparisonProfileError) as caught:
                self.build()
            self.assertEqual(caught.exception.code, 'PROFILE_CONTRACT_SOURCE_DRIFT')

    def test_malformed_selected_envelopes_and_dispositions_fail_with_fixed_codes(self):
        cases = [({'coverage.current': None}, {}, {}, 'PROFILE_ENVELOPE_INVALID'),
                 ({}, {'RC01': []}, {}, 'PROFILE_ENVELOPE_INVALID'),
                 ({}, {}, {'baselineDispositions': {'T01': []}}, 'PROFILE_DISPOSITION_INVALID')]
        for guide_fields, facts, conversation, code in cases:
            with self.subTest(code=code, selected=list(guide_fields or facts or conversation)):
                self.guide['fields'], self.record['facts'] = guide_fields, facts
                self.record['conversation'] = conversation
                with self.assertRaises(ComparisonProfileError) as caught:
                    self.build()
                self.assertEqual(caught.exception.code, code)
        self.guide['fields'], self.record['facts'], self.record['conversation'] = {}, {}, {}
        self.record['entityDispositions'] = {'RC21': None}
        with self.assertRaises(ComparisonProfileError) as caught:
            self.build()
        self.assertEqual(caught.exception.code, 'PROFILE_DISPOSITION_INVALID')


if __name__ == '__main__':
    unittest.main()
