"""Synthetic contracts for local provenance, per-fact resolution and AI context."""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
ENGINE = HERE.parent / 'chat-first' / 'cms-slice'
sys.path.insert(0, str(ENGINE / 'scripts'))
sys.path.insert(0, str(HERE))
from guest_profiles import validate_guide
from readiness_profiles import validate as validate_readiness
from natural_state import (CONTEXT_VERSION, build_context, classify_situation, classify_update, ensure_state,
                           legacy_projection, prune_for_storage, record_capture, restore_state, set_target,
                           validate_state)


def envelope(value, revision=1, **extra):
    return {'value': value, 'status': 'reported', 'source': 'user_text',
            'confirmation': 'confirmed_by_user', 'revision': revision, **extra}


def proposal(identifier='RC11', fields=None, **extra):
    return {'id': identifier, 'entity': 'profile', 'fields': fields or {'jobEnd': '2027-03'},
            'quote': 'My job ends in March 2027', 'scope': 'current',
            'subject': 'beneficiary', 'uncertain': False, 'correction': False, **extra}


class NaturalStateTests(unittest.TestCase):
    def setUp(self):
        self.guide = {'schemaVersion': 2, 'stateVersion': 0, 'fields': {},
            'flow': {'node': 'A00', 'history': [], 'queue': [], 'lessonReturn': None,
                     'personalReview': False, 'guideOpen': True, 'origin': 'T01',
                     'invalidations': [], 'scroll': 0}, 'topics': {},
            'preferences': {'saveGuide': False, 'saveSensitive': False,
                            'noticeVersion': 'guest-notice-2026-10-21-v1'}}
        self.record = json.loads((ENGINE / 'config/profile/customer-profile.template.json').read_text())['readiness']
        self.contract = json.loads((HERE / 'web/guide-contract.json').read_text())

    def add_report(self, value='employer', method='direct_report'):
        before_g, before_r = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        self.guide['stateVersion'] += 1
        self.guide['fields']['coverage.current'] = envelope([value], self.guide['stateVersion'])
        record_capture(self.guide, self.record, before_g, before_r, method=method)

    def test_initialization_preserves_existing_confirmations_and_values(self):
        self.guide['fields']['coverage.current'] = envelope(['employer'])
        before = copy.deepcopy(self.guide)
        ensure_state(self.record)
        self.assertEqual(self.guide, before)
        self.assertEqual(self.record['natural']['provenance'], {})

    def test_direct_report_is_honest_and_projects_into_both_strict_schemas(self):
        self.add_report()
        self.assertEqual(self.guide['fields']['coverage.current']['confirmation'], 'reported_by_user')
        local_g, local_r = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        g, r = legacy_projection(self.guide, self.record)
        validate_guide(g, self.contract)
        validate_readiness(r)
        self.assertNotIn('natural', r)
        self.assertEqual(g['fields']['coverage.current']['confirmation'], 'confirmed_by_user')
        self.assertEqual((self.guide, self.record), (local_g, local_r))
        restored = restore_state(g, r, local_r['natural'])
        self.assertEqual(restored, (local_g, local_r))

    def test_explicit_confirmation_is_distinct_from_direct_or_structured_capture(self):
        self.add_report(method='explicit_confirmation')
        self.assertEqual(self.guide['fields']['coverage.current']['confirmation'], 'explicitly_confirmed')
        self.assertEqual(self.record['natural']['provenance']['guide.coverage.current']['status'], 'explicitly_confirmed')
        g, r = legacy_projection(self.guide, self.record)
        self.assertEqual(restore_state(g, r, self.record['natural'])[0], self.guide)

    def test_untracked_claim_of_new_confirmation_is_rejected(self):
        self.guide['fields']['coverage.current'] = envelope(['employer'], confirmation='reported_by_user')
        with self.assertRaises(ValueError):
            legacy_projection(self.guide, self.record)

    def test_provenance_revision_must_match_new_confirmation(self):
        self.add_report()
        self.guide['fields']['coverage.current']['revision'] += 1
        with self.assertRaises(ValueError):
            legacy_projection(self.guide, self.record)

    def test_correction_metadata_stores_no_span_or_old_or_new_values(self):
        self.add_report()
        old_g, old_r = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        self.guide['stateVersion'] = 2
        self.guide['fields']['coverage.current'] = envelope(['retiree'], 2)
        update = proposal('T05', {'choice': 'retiree'}, quote='Actually I have retiree insurance', correction=True)
        record_capture(self.guide, self.record, old_g, old_r, update)
        metadata = self.record['natural']['provenance']['guide.coverage.current']
        self.assertEqual(metadata['supersedesRevision'], 1)
        self.assertEqual(metadata['revision'], 2)
        durable = json.dumps(self.record['natural'])
        for secret in ('Actually', 'retiree', 'employer', 'quote', 'rawText'):
            self.assertNotIn(secret, durable)

    def test_exact_changed_medicine_field_provenance_preserves_other_item(self):
        self.record['facts']['RC22'] = {'value': {'choice': 'details', 'items': [
            {'entity': 'medicine-1', 'name': 'Example', 'strength': '5 mg'},
            {'entity': 'medicine-2', 'name': 'Example', 'strength': '10 mg'}]},
            'confirmation': 'confirmed_by_user', 'source': 'user_choice', 'revision': 1, 'stale': False}
        before_g, before_r = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        self.record['facts']['RC22']['revision'] = 2
        self.record['facts']['RC22']['value']['items'][1]['strength'] = '20 mg'
        record_capture(self.guide, self.record, before_g, before_r,
                       proposal('RC22', {'strength': '20 mg'}, entity='medicine-2', correction=True))
        refs = self.record['natural']['provenance']
        self.assertIn('readiness.RC22.medicine-2.strength', refs)
        self.assertNotIn('readiness.RC22.medicine-1.strength', refs)
        self.assertNotIn('readiness.RC22.medicine-2.name', refs)
        _, projected = legacy_projection(self.guide, self.record)
        validate_readiness(projected)

    def test_invalidation_alone_does_not_relabel_an_old_report(self):
        self.guide['fields']['coverage.current'] = envelope(['employer'])
        old_g, old_r = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        self.guide['fields']['coverage.current']['status'] = 'stale'
        record_capture(self.guide, self.record, old_g, old_r)
        self.assertEqual(self.record['natural']['provenance'], {})
        self.assertEqual(self.guide['fields']['coverage.current']['confirmation'], 'confirmed_by_user')

    def test_unknown_metadata_keys_and_text_are_rejected(self):
        state = ensure_state(self.record)
        state['dialogue']['rawTranscript'] = 'private conversation'
        with self.assertRaises(ValueError):
            validate_state(self.record)

    def test_invalid_target_fields_fail_closed(self):
        for identifier, fields in [('RC11', ['strength']), ('RC05.C1', ['month']), ('RC11', [{}])]:
            with self.subTest(identifier=identifier, fields=fields):
                with self.assertRaises(ValueError):
                    set_target(self.record, {'id': identifier, 'fields': fields})

    def test_target_retains_public_semantics_without_question_prose(self):
        set_target(self.record, {'id': 'RC11', 'entity': 'profile',
                                'question': 'private caller-provided prose',
                                'fields': [{'key': 'jobEnd'}, {'key': 'coverageEnd'}]}, orientation='progress')
        self.assertEqual(self.record['natural']['dialogue']['lastTarget'],
                         {'id': 'RC11', 'entity': 'profile', 'fields': ['jobEnd', 'coverageEnd']})
        self.assertNotIn('private', json.dumps(self.record['natural']))

    def test_situation_targets_only_extend_dialogue_clarification_metadata(self):
        for identifier, fields in [('S_AGE65', []), ('S_AGE65', ['month', 'year']),
                                   ('S_RETIREMENT', ['status', 'when'])]:
            target = set_target(self.record, {'id': identifier, 'fields': fields})
            self.assertEqual(target['id'], identifier)
            validate_state(self.record)
            update = proposal(identifier, {'choice': 'self'})
            self.assertEqual(classify_update(update, update['quote'])['decision'], 'reject')
        with self.assertRaises(ValueError):
            set_target(self.record, {'id': 'S_AGE65', 'fields': ['strength']})

    def test_clear_partial_and_unknown_are_accepted_independently(self):
        update = proposal(fields={'jobEnd': '2027-03', 'coverageEnd': 'unknown'})
        self.assertEqual(classify_update(update, update['quote'])['decision'], 'accept')
        unknown = proposal(fields={'jobEnd': 'unknown'}, quote="I don't know")
        self.assertEqual(classify_update(unknown, unknown['quote'])['decision'], 'accept')

    def test_uncertainty_and_conflict_do_not_become_usable_reports(self):
        for update, existing in [
            (proposal(uncertain=True), None),
            (proposal(quote='I think my job ends in March 2027'), None),
            (proposal(), {'jobEnd': '2027-04'}),
            (proposal(subject='unclear'), None),
        ]:
            with self.subTest(update=update):
                result = classify_update(update, update['quote'], existing)
                self.assertEqual(result['decision'], 'clarify')
        self.assertEqual(self.guide['fields'], {})
        self.assertEqual(self.record['facts'], {})

    def test_explicit_unambiguous_correction_may_replace_old_report(self):
        update = proposal(correction=True)
        self.assertEqual(classify_update(update, update['quote'], {'jobEnd': '2027-04'})['decision'], 'accept')

    def test_repeated_baseline_multiselect_is_not_a_conflict(self):
        update = proposal('T05', {'choice': 'employer'})
        self.assertEqual(classify_update(update, update['quote'], envelope(['employer']))['decision'], 'accept')
        update['fields']['choice'] = 'employer,medigap'
        self.assertEqual(classify_update(update, update['quote'], envelope(['medigap', 'employer']))['decision'], 'accept')
        update['fields']['choice'] = 'retiree'
        self.assertEqual(classify_update(update, update['quote'], envelope(['employer']))['decision'], 'clarify')

    def test_helper_hypothetical_future_actual_and_fabricated_span_are_rejected(self):
        cases = [proposal(subject='learner'), proposal(quote='Suppose my job ends in March 2027'),
                 proposal('RC05', {'month': '2027-03'}, scope='intended'),
                 proposal('T05', {'choice': 'employer'}, scope='historical')]
        for update in cases:
            with self.subTest(update=update):
                self.assertEqual(classify_update(update, update['quote'])['decision'], 'reject')
        self.assertEqual(classify_update(proposal(), 'A different message')['decision'], 'reject')

    def test_named_assistance_programs_coexist_without_an_implicit_correction(self):
        for existing in ('medicaid', 'extra_help', 'part_b_help', 'ssi', 'medicaid,extra_help'):
            for addition in ('medicaid', 'extra_help', 'part_b_help', 'ssi', 'part_b_help,ssi'):
                with self.subTest(existing=existing, addition=addition):
                    update = proposal('RC18', {'choice': addition}, quote='I receive these assistance benefits.')
                    result = classify_update(update, update['quote'], {'choice': existing, 'programs': existing.split(',')})
                    self.assertEqual(result['decision'], 'accept')
                    self.assertEqual(result['reason'], 'explicit_program_addition')

    def test_assistance_addition_does_not_bypass_conflict_or_scope_safeguards(self):
        for old, new in (('none', 'medicaid'), ('declined', 'extra_help'),
                         ('medicaid', 'none'), ('medicaid', 'declined'),
                         ('medicaid', 'invented_program')):
            update = proposal('RC18', {'choice': new}, quote='My assistance benefits changed.')
            self.assertEqual(classify_update(update, update['quote'], {'choice': old})['decision'], 'clarify')
        for overrides, decision in (({'uncertain': True}, 'clarify'),
                                    ({'subject': 'learner'}, 'reject'),
                                    ({'scope': 'unknown'}, 'clarify'),
                                    ({'scope': 'historical'}, 'clarify'),
                                    ({'quote': 'Suppose I receive Extra Help.'}, 'reject')):
            update = proposal('RC18', {'choice': 'extra_help'}, quote='I receive Extra Help.', **{k:v for k,v in overrides.items() if k != 'quote'})
            if 'quote' in overrides:
                update['quote'] = overrides['quote']
            self.assertEqual(classify_update(update, update['quote'], {'choice': 'medicaid'})['decision'], decision)

    def test_planned_or_past_enrollment_cannot_become_current_parts_or_delivery(self):
        for identifier in ('RC04', 'RC07', 'RC09'):
            for scope in ('intended', 'historical'):
                update = proposal(identifier, {'choice': 'both'}, scope=scope)
                self.assertEqual(classify_update(update, update['quote'])['decision'], 'reject')
        for identifier, fields in [('RC05', {'month': '2020-04'}), ('RC16', {'start': '2020-04'})]:
            update = proposal(identifier, fields, scope='historical')
            self.assertEqual(classify_update(update, update['quote'])['decision'], 'accept')

    def test_ambiguous_correction_never_picks_first_same_name_medicine(self):
        existing = {'items': [{'entity': 'medicine-1', 'name': 'Example'}, {'entity': 'medicine-2', 'name': 'Example'}]}
        update = proposal('RC22', {'strength': '5 mg'}, correction=True)
        self.assertEqual(classify_update(update, update['quote'], existing)['reason'], 'ambiguous_entity')
        update['entity'] = 'medicine-2'
        self.assertEqual(classify_update(update, update['quote'], existing)['decision'], 'accept')
        update['entity'] = 'medicine-3'
        self.assertEqual(classify_update(update, update['quote'], existing)['reason'], 'missing_correction_target')

    def test_provider_and_medicine_entity_kinds_cannot_cross(self):
        update = proposal('RC21', {'practice': 'Example practice'}, entity='medicine-1')
        self.assertEqual(classify_update(update, update['quote'])['decision'], 'reject')

    def context_fixture(self):
        self.guide['fields'] = {
            'coverage.current': envelope(['employer']), 'intent.goal': envelope('compare'),
            'knowledge.general': envelope('new'), 'subject.role': envelope('self'),
            'coverage.requestedStartMonth': envelope('2027-04'),
            'needs.medications': envelope('Example medicine'),
            'subject.displayLabel': envelope('Private display name'),
        }
        self.record['facts']['RC11'] = {'value': {'choice': 'dates', 'jobEnd': '2027-03', 'coverageEnd': '2027-04'},
            'source': 'user_choice', 'confirmation': 'confirmed_by_user', 'revision': 1, 'stale': False}
        self.record['facts']['RC22'] = {'value': {'choice': 'details', 'items': [
            {'entity': 'medicine-1', 'name': 'Example medicine', 'strength': '5 mg'}]},
            'source': 'user_choice', 'confirmation': 'confirmed_by_user', 'revision': 2, 'stale': False}

    def test_without_exact_permission_only_four_safe_prior_values_are_sent(self):
        self.context_fixture()
        for permission in (None, True, 'natural-context-v0'):
            context = build_context(self.guide, self.record, 'timing', consent_version=permission)
            self.assertEqual({x['id'] for x in context['reports']},
                {'guide.coverage.current', 'guide.intent.goal', 'guide.knowledge.general', 'guide.subject.role'})
            sent = json.dumps(context)
            for private in ('2027-04', '2027-03', 'Example medicine', '5 mg', 'Private display name'):
                self.assertNotIn(private, sent)
            self.assertTrue(all(set(x) == {'id', 'status'} for x in context['known']))

    def test_permission_alone_does_not_remove_task_relevance_filter(self):
        self.context_fixture()
        timing = build_context(self.guide, self.record, 'timing', consent_version=CONTEXT_VERSION)
        sent = json.dumps(timing)
        self.assertIn('2027-04', sent)
        self.assertNotIn('Example medicine', sent)
        self.assertNotIn('Private display name', sent)
        drugs = build_context(self.guide, self.record, 'drug_coverage', consent_version=CONTEXT_VERSION)
        self.assertIn('Example medicine', json.dumps(drugs))
        self.assertNotIn('2027-03', json.dumps(drugs))

    def test_stale_tentative_conflicting_and_id_values_are_presence_only(self):
        self.context_fixture()
        self.guide['fields']['coverage.requestedStartMonth']['status'] = 'stale'
        self.guide['fields']['needs.medications']['value'] = '123-45-6789'
        context = build_context(self.guide, self.record, 'timing', consent_version=CONTEXT_VERSION)
        self.assertNotIn('2027-04', json.dumps([x for x in context['reports'] if x['id'].startswith('guide.')]))
        self.assertNotIn('123-45-6789', json.dumps(context))
        self.guide['fields']['needs.medications']['value'] = '1EG4TE5MK73'
        drugs = build_context(self.guide, self.record, 'drug_coverage', consent_version=CONTEXT_VERSION)
        self.assertNotIn('1EG4TE5MK73', json.dumps(drugs))

    def test_learning_stays_minimal_and_raw_history_never_enters_context(self):
        self.context_fixture()
        self.record['history'] = [{'previous': {'jobEnd': 'secret-old-date'}}]
        context = build_context(self.guide, self.record, 'learn', consent_version=CONTEXT_VERSION)
        self.assertNotIn('secret-old-date', json.dumps(context))
        self.assertNotIn('Example medicine', json.dumps(context))
        self.assertEqual(len(context['reports']), 4)

    def test_context_has_exact_entity_refs_and_does_not_mutate_state(self):
        self.context_fixture()
        before = copy.deepcopy((self.guide, self.record))
        context = build_context(self.guide, self.record, 'drug_coverage',
            active_question={'id': 'RC22', 'entity': 'medicine-1', 'fields': [{'key': 'form'}]},
            consent_version=CONTEXT_VERSION)
        self.assertIn('readiness.RC22.medicine-1.strength', {x['id'] for x in context['reports']})
        self.assertEqual(context['activeQuestion'], {'id': 'RC22', 'entity': 'medicine-1', 'fields': ['form']})
        self.assertEqual((self.guide, self.record), before)

    def test_unknown_disposition_remains_presence_marker(self):
        self.record['dispositions']['RC05'] = {'state': 'explicit_unknown', 'automaticReopen': False}
        context = build_context(self.guide, self.record, 'timing', consent_version=CONTEXT_VERSION)
        self.assertEqual(context['reports'], [])
        self.assertIn({'id': 'readiness.RC05', 'status': 'explicit_unknown'}, context['known'])

    def test_unknown_and_deferred_fields_keep_distinct_status(self):
        self.context_fixture()
        self.record['facts']['RC11']['value'].update(jobEnd='unknown', coverageEnd='deferred')
        context = build_context(self.guide, self.record, 'timing', consent_version=CONTEXT_VERSION)
        statuses = {x['id']: x['status'] for x in context['reports']}
        self.assertEqual(statuses['readiness.RC11.profile.jobEnd'], 'unknown')
        self.assertEqual(statuses['readiness.RC11.profile.coverageEnd'], 'deferred')

    def test_unknown_or_skipped_guide_never_sends_retained_old_value(self):
        self.context_fixture()
        for status, expected in [('unknown', 'unknown'), ('skipped', 'deferred')]:
            self.guide['fields']['coverage.requestedStartMonth']['status'] = status
            self.guide['fields']['coverage.current']['status'] = status
            context = build_context(self.guide, self.record, 'timing', consent_version=CONTEXT_VERSION)
            fields = {x['id']: x for x in context['reports']}
            self.assertEqual(fields['guide.coverage.requestedStartMonth']['value'], expected)
            self.assertEqual(fields['guide.coverage.current']['value'], expected)
            self.assertNotIn('employer', json.dumps(fields['guide.coverage.current']))
            self.assertNotIn('2027-04', json.dumps(fields['guide.coverage.requestedStartMonth']))

    def test_situation_uncertainty_is_scoped_to_its_clause(self):
        message = "I think I'm retired, and I turn 65 in November"
        retirement = classify_situation(message, 'retirement', {'status': 'retired', 'when': ''})
        birthday = classify_situation(message, 'age65', {'month': 11, 'year': None})
        self.assertEqual(retirement['decision'], 'clarify')
        self.assertEqual(retirement['reason'], 'tentative')
        self.assertEqual(birthday['decision'], 'accept')
        message = "I'm retired and I think I turn 65 in November"
        self.assertEqual(classify_situation(message, 'retirement', {'status': 'retired', 'when': ''})['decision'], 'accept')
        self.assertEqual(classify_situation(message, 'age65', {'month': 11, 'year': None})['reason'], 'tentative')

    def test_situation_postposed_uncertainty_is_not_lost_at_comma(self):
        value = {'status': 'retired', 'when': ''}
        self.assertEqual(classify_situation("I'm retired, I think", 'retirement', value)['reason'], 'tentative')
        self.assertEqual(classify_situation("I think, I'm retired", 'retirement', value)['reason'], 'tentative')

    def test_negated_belief_cannot_become_positive_life_report(self):
        self.assertEqual(classify_situation("I don't think I'm retired", 'retirement',
            {'status': 'retired', 'when': ''})['reason'], 'tentative')
        self.assertEqual(classify_situation("I don’t think I turn 65 in November", 'age65',
            {'month': 11, 'year': None})['reason'], 'tentative')

    def test_situation_conflict_does_not_silently_overwrite_old_value(self):
        old = envelope({'month': 11, 'year': 2027})
        value = {'month': 12, 'year': None}
        self.assertEqual(classify_situation('I turn 65 in December', 'age65', value, old)['reason'], 'conflicting_report')
        result = classify_situation('Actually I turn 65 in December', 'age65', value, old)
        self.assertEqual(result['decision'], 'accept')
        self.assertEqual(result['reason'], 'explicit_correction')
        self.assertEqual(result['value'], {'month': 12, 'year': 2027})

    def test_situation_partial_reports_preserve_known_precision(self):
        old = envelope({'month': 11, 'year': 2027})
        result = classify_situation('I turn 65 in November', 'age65', {'month': 11, 'year': None}, old)
        self.assertEqual(result['decision'], 'accept')
        self.assertEqual(result['value']['year'], 2027)
        old = envelope({'status': 'retired', 'when': 'for three years'})
        result = classify_situation("I'm retired", 'retirement', {'status': 'retired', 'when': ''}, old)
        self.assertEqual(result['value']['when'], 'for three years')

    def test_situation_hypothetical_questions_and_unsupported_values_are_not_facts(self):
        value = {'status': 'retired', 'when': ''}
        self.assertEqual(classify_situation("Suppose I'm retired", 'retirement', value)['decision'], 'reject')
        self.assertEqual(classify_situation('Am I retired?', 'retirement', value)['decision'], 'clarify')
        self.assertEqual(classify_situation('My insurance is complicated', 'retirement', value)['decision'], 'reject')
        self.assertEqual(classify_situation('I turn 65 in November', 'age65', {'month': 20, 'year': None})['decision'], 'reject')

    def test_stale_fill_item_is_not_sent_after_medicine_identity_changes(self):
        self.context_fixture()
        self.record['facts']['RC23'] = {'value': {'choice': 'details', 'items': [
            {'entity': 'medicine-1', 'quantity': '30 tablets', 'pharmacy': 'Private pharmacy'}]},
            'source': 'user_choice', 'confirmation': 'confirmed_by_user', 'revision': 2, 'stale': False}
        self.record['conversation'] = {'itemRevisions': {'RC23.medicine-1': 2},
                                      'itemInvalidations': {'RC23.medicine-1': 3}}
        context = build_context(self.guide, self.record, 'drug_pricing', consent_version=CONTEXT_VERSION)
        self.assertNotIn('Private pharmacy', json.dumps(context))
        self.assertIn({'id': 'readiness.RC23.medicine-1.pharmacy', 'status': 'stale'}, context['known'])

    def test_storage_omissions_preserve_remaining_honest_report_provenance(self):
        self.add_report()
        before_g, before_r = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        self.guide['fields']['situation.age65'] = envelope({'month': 11, 'year': None}, 2)
        self.record['facts']['RC11'] = {'value': {'choice': 'dates', 'jobEnd': '2027-03'},
            'confirmation': 'confirmed_by_user', 'source': 'user_choice', 'revision': 1, 'stale': False}
        self.record['dispositions']['RC11'] = {'state': 'resolved_report', 'automaticReopen': False}
        self.record['history'] = [{'triggerId': 'RC11', 'previous': {'jobEnd': 'private-old-date'}}]
        record_capture(self.guide, self.record, before_g, before_r)
        source = copy.deepcopy((self.guide, self.record))
        g, r = prune_for_storage(self.guide, self.record)
        self.assertEqual((self.guide, self.record), source)
        self.assertNotIn('situation.age65', g['fields'])
        self.assertEqual(r['facts'], {})
        self.assertNotIn('previous', r['history'][0])
        self.assertEqual(r['dispositions']['RC11']['state'], 'not_saved')
        self.assertEqual(set(r['natural']['provenance']), {'guide.coverage.current'})
        projected_g, projected_r = legacy_projection(g, r)
        validate_guide(projected_g, self.contract)
        validate_readiness(projected_r)
        self.assertEqual(restore_state(projected_g, projected_r, r['natural']), (g, r))

    def test_sensitive_save_retains_exact_provenance_and_strips_raw_text(self):
        self.add_report()
        self.guide['preferences']['saveSensitive'] = True
        self.guide['fields']['coverage.current']['rawText'] = 'private literal user wording'
        g, r = prune_for_storage(self.guide, self.record)
        self.assertNotIn('rawText', g['fields']['coverage.current'])
        self.assertEqual(r['natural'], self.record['natural'])
        self.assertEqual(g['fields']['coverage.current']['confirmation'], 'reported_by_user')

    def test_pruning_deleted_item_retains_only_surviving_field_refs(self):
        self.test_exact_changed_medicine_field_provenance_preserves_other_item()
        self.guide['preferences']['saveSensitive'] = True
        self.record['facts']['RC22']['value']['items'].pop()
        _, r = prune_for_storage(self.guide, self.record)
        self.assertIn('readiness.RC22', r['natural']['provenance'])
        self.assertNotIn('readiness.RC22.medicine-2.strength', r['natural']['provenance'])


if __name__ == '__main__':
    unittest.main()
