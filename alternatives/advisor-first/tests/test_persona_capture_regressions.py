"""Controller defects exposed by the independently authored persona oracles."""
import copy
import unittest

import test_natural_flow as flow_harness
from comparison_profile import build_comparison_profile
from natural_flow import CONTEXT_POLICY, ProfileError
from natural_state import prune_for_storage


class PersonaCaptureRegressionTests(unittest.TestCase):
    def case(self):
        case = flow_harness.NaturalFlowTests()
        case.setUp()
        return case

    def test_explicit_named_item_resolves_an_ambiguous_edit_and_preserves_sibling(self):
        for identifier, fields in (('RC21', {'city': 'Miami'}),
                                   ('RC22', {'strength': '20 mg'}),
                                   ('RC23', {'daysSupply': '90'})):
            with self.subTest(identifier=identifier):
                case = self.case()
                before = case.seed_item_reports(identifier)
                text = 'Change that detail to ' + next(iter(fields.values())) + '.'
                case.message(text, [case.update(identifier, fields, text, correction=True)])
                self.assertEqual(case.flow.pending_for(case.owner)['update']['entity'], 'profile')
                self.assertTrue(case.r['facts'][identifier]['stale'])
                clarified = 'I mean the first item. Change its detail to ' + next(iter(fields.values())) + '.'
                case.message(clarified, [case.update(identifier, fields, clarified, entity=before[0]['entity'])])
                self.assertIsNone(case.flow.pending_for(case.owner))
                self.assertFalse(case.r['facts'][identifier]['stale'])
                items = case.flow.report(case.r, identifier)['items']
                self.assertEqual(items[1], before[1])
                self.assertEqual(len(items), 2)
                for key, value in fields.items():
                    self.assertEqual(items[0][key], value)

    def test_unrelated_or_unrecognized_item_does_not_resolve_ambiguous_fill(self):
        case = self.case()
        case.seed_item_reports('RC23')
        text = 'Change it to ninety days.'
        case.message(text, [case.update('RC23', {'daysSupply': '90'}, text, correction=True)])
        pending = copy.deepcopy(case.flow.pending_for(case.owner))
        for update in (case.update('RC23', {'pharmacy': 'Example Pharmacy'}, text, entity='medicine-1'),
                       case.update('RC23', {'daysSupply': '90'}, text, entity='medicine-99')):
            update['fields'] = {item['key']: item['value'] for item in update['fields']}
            self.assertEqual(case.flow.pending_resolution_update(pending, update, case.r), update)
        unrelated = 'The first fill uses Example Pharmacy.'
        case.message(unrelated, [case.update('RC23', {'pharmacy': 'Example Pharmacy'}, unrelated, entity='medicine-1')])
        self.assertEqual(case.flow.pending_for(case.owner)['update']['fields'], {'daysSupply': '90'})
        self.assertTrue(case.r['facts']['RC23']['stale'])

    def test_named_clarification_resolves_its_ambiguous_alias_and_retains_other_targets(self):
        for other_pending in (False, True):
            with self.subTest(other_pending=other_pending):
                case = self.case()
                before = case.seed_item_reports('RC23')
                text = 'Change it to ninety days.'
                case.message(text, [case.update('RC23', {'daysSupply': '90'}, text, correction=True)])
                tentative = 'I think the first fill should be sixty days, but I am not certain.'
                case.message(tentative, [case.update('RC23', {'daysSupply': '60'}, tentative, entity='medicine-1', uncertain=True)])
                if other_pending:
                    other = 'I think the second fill should be forty-five days.'
                    case.message(other, [case.update('RC23', {'daysSupply': '45'}, other, entity='medicine-2', uncertain=True)])
                certain = 'The first fill should be sixty days.'
                case.message(certain, [case.update('RC23', {'daysSupply': '60'}, certain, entity='medicine-1')])
                items = case.r['facts']['RC23']['value']['items']
                self.assertEqual(items[0]['daysSupply'], '60')
                self.assertEqual(items[1], before[1])
                self.assertEqual(bool(case.flow.pending_for(case.owner)), other_pending)
                self.assertEqual(case.r['facts']['RC23']['stale'], other_pending)
                if other_pending:
                    self.assertEqual(case.flow.pending_for(case.owner)['update']['entity'], 'medicine-2')
                    final = 'The second fill should be forty-five days.'
                    case.message(final, [case.update('RC23', {'daysSupply': '45'}, final, entity='medicine-2')])
                    self.assertIsNone(case.flow.pending_for(case.owner))
                    self.assertFalse(case.r['facts']['RC23']['stale'])

    def test_conflicting_beneficiary_holds_the_role_mirror_until_clarified(self):
        case = self.case()
        case.choice('RC01', choice='someone')
        text = 'This is for me.'
        case.message(text, [case.update('RC01', {'choice': 'self'}, text)])
        self.assertEqual(case.flow.pending_for(case.owner)['update']['id'], 'RC01')
        self.assertEqual(case.g['fields']['subject.role']['status'], 'stale')
        self.assertIsNone(case.flow.value(case.g, 'subject.role'))
        context = case.flow.context(case.g, case.r, CONTEXT_POLICY, case.flow.question('RC01'))
        self.assertFalse(any(item['id'] == 'guide.subject.role' and 'value' in item for item in context['reports']))
        comparison = build_comparison_profile(case.g, case.r)
        mirror = comparison['extensions']['subject_role_mirror']
        self.assertFalse(mirror['usable_as_report'])
        self.assertIsNone(comparison['profile_binding']['subject_role'])
        case.message(text, [case.update('RC01', {'choice': 'self'}, text)])
        self.assertIsNone(case.flow.pending_for(case.owner))
        self.assertEqual(case.flow.value(case.g, 'subject.role'), 'self')

    # Fix 2 (subject correction, Charlie 2026-11-21): a corrected "who is this
    # for" switches the subject and asks again about each earlier fact, instead
    # of refusing with "Open a separate visit".

    def age65(self, quote, month=3, year=2027):
        """Return an extraction carrying one turning-65 situation proposal."""
        return {'kind': 'age65', 'subject': 'beneficiary', 'scope': 'current', 'quote': quote,
                'uncertain': False, 'correction': False, 'month': month, 'year': year,
                'status': '', 'when': ''}

    def test_helper_first_person_wording_does_not_save_for_me(self):
        """'She turns 65 ... and I'll handle it' leaves who-it-is-for open instead of guessing 'self'."""
        case = self.case()
        case.choice('T01', choice='compare')
        text = "She turns 65 in March 2027 and I'll handle it."
        case.message(text, [], extraction=case.extraction([], situation_proposals=[self.age65(text)]))
        self.assertIsNone(case.flow.value(case.g, 'subject.role'))
        self.assertNotIn('RC01', case.r['facts'])

    def test_corrected_subject_switches_and_reconfirms_each_retained_fact(self):
        """A confirmed 'it is for my mom' switches to someone and holds T05 for re-confirmation."""
        case = self.case()
        case.choice('T01', choice='compare')
        case.choice('RC01', choice='self')
        case.choice('T05', choice='cobra')
        text = 'No, this is for my mom.'
        case.message(text, [case.update('RC01', {'choice': 'someone'}, text)])
        clarified = 'Yes, it is for my mom, not me.'
        case.message(clarified, [case.update('RC01', {'choice': 'someone'}, clarified, correction=True)])
        self.assertEqual(case.flow.value(case.g, 'subject.role'), 'someone')
        self.assertEqual(case.r['facts']['RC01']['value']['choice'], 'someone')
        self.assertFalse(case.r['facts']['RC01']['stale'])
        # The old answer is kept but not used until the person re-confirms it.
        self.assertIsNone(case.flow.value(case.g, 'coverage.current'))
        self.assertEqual(case.g['fields']['coverage.current']['value'], ['cobra'])
        self.assertEqual(case.flow.report(case.r, 'RC09'), {})
        pending = case.flow.pending_for(case.owner)
        self.assertEqual((pending['update']['id'], pending['update']['fields']), ('T05', {'choice': 'cobra'}))
        self.assertTrue(pending['update'].get('reconfirm'))
        move = case.flow.eligible(case.owner, case.g, case.r)[0]
        self.assertEqual(move['id'], 'T05')
        self.assertIn('who this visit is for', move['purpose'])
        case.message('Yes.', [])
        self.assertEqual(case.flow.value(case.g, 'coverage.current'), ['cobra'])
        self.assertEqual(case.flow.report(case.r, 'RC09')['choice'], 'cobra')
        self.assertIsNone(case.flow.pending_for(case.owner))

    def test_button_subject_change_switches_and_holds_readiness_facts(self):
        """Choosing 'self' after 'someone' no longer refuses; RC06 waits for re-confirmation."""
        case = self.case()
        case.choice('RC01', choice='someone')
        case.choice('RC06', choice='disability')
        case.choice('RC01', choice='self')
        self.assertEqual(case.flow.value(case.g, 'subject.role'), 'self')
        self.assertEqual(case.flow.report(case.r, 'RC06'), {})
        self.assertEqual(case.r['facts']['RC06']['value']['choice'], 'disability')
        pending = case.flow.pending_for(case.owner)
        self.assertEqual((pending['update']['id'], pending['update']['fields']), ('RC06', {'choice': 'disability'}))

    def test_subject_change_reconfirms_the_turning_65_report(self):
        """A held birthday is offered back as the exact proposed value and a 'yes' restores it."""
        case = self.case()
        case.choice('T01', choice='compare')
        case.choice('RC01', choice='self')
        text = 'I turn 65 in March 2027.'
        case.message(text, [], extraction=case.extraction([], situation_proposals=[self.age65(text)]))
        self.assertEqual(case.flow.value(case.g, 'situation.age65')['month'], 3)
        case.choice('RC01', choice='someone')
        self.assertIsNone(case.flow.value(case.g, 'situation.age65'))
        pending = case.flow.pending_for(case.owner)
        self.assertEqual(pending['update']['id'], 'S_AGE65')
        self.assertEqual(pending['update']['proposed']['month'], 3)
        case.message('Yes, that is right.', [])
        self.assertEqual(case.flow.value(case.g, 'situation.age65')['month'], 3)
        self.assertIsNone(case.flow.pending_for(case.owner))

    def test_reconfirmation_survives_a_dropped_in_memory_clarification(self):
        """Held targets live in the record, so a cleared pending question comes back next turn."""
        case = self.case()
        case.choice('RC01', choice='someone')
        case.choice('T05', choice='cobra')
        case.choice('RC01', choice='self')
        case.flow.clear_pending(case.owner)
        move = case.flow.eligible(case.owner, case.g, case.r)[0]
        self.assertEqual(move['id'], 'T05')
        self.assertTrue(move['required'])

    def test_research_only_still_cannot_take_over_a_persons_reports(self):
        """Switching from a person to research-only keeps the old refusal; no facts change."""
        case = self.case()
        case.choice('RC01', choice='someone')
        case.choice('RC06', choice='disability')
        before = copy.deepcopy((case.g, case.r))
        with self.assertRaisesRegex(ProfileError, 'separate visit'):
            case.flow.apply(case.g, case.r, {'id': 'RC01', 'fields': {'choice': 'research'}})
        self.assertEqual((case.g, case.r), before)

    def test_saved_role_mirror_switch_holds_reports_when_sensitive_facts_are_omitted(self):
        """A pruned saved visit (role mirror only) also switches and holds T05 instead of refusing."""
        case = self.case()
        case.choice('RC01', choice='someone')
        case.choice('T05', choice='cobra')
        guide, record = prune_for_storage(case.g, case.r)
        self.assertNotIn('RC01', record['facts'])
        case.flow.apply(guide, record, {'id': 'RC01', 'fields': {'choice': 'self'}})
        self.assertEqual(guide['fields']['subject.role']['value'], 'self')
        self.assertEqual(guide['fields']['coverage.current']['status'], 'stale')
        held = record['natural']['dialogue']['clarifications']
        self.assertIn({'id': 'T05', 'entity': 'profile', 'fields': []}, held)


if __name__ == '__main__':
    unittest.main()
