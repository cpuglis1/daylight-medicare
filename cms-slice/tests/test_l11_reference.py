"""L11 mutation and boundary checks against the retained research package."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import l11_validate as validator

BUILD=Path(os.environ.get('L11_TEST_BUILD',str(validator.BASE/'build-r1')))


class L11ReferenceTests(unittest.TestCase):
    def test_source_storage_and_independent_synthetic_checks(self):
        result=validator.validate(BUILD)
        self.assertEqual(result['errors'],[])

    def mutated(self,filename,change):
        original=validator.load
        def replacement(path):
            value=original(path)
            if Path(path)==BUILD/filename:
                value=copy.deepcopy(value);change(value)
            return value
        with patch.object(validator,'load',side_effect=replacement):
            return validator.validate(BUILD)

    def test_altered_condition_is_caught(self):
        r=self.mutated('rules.json',lambda rows:rows[0]['conditions'][0].update(text='All applicants qualify'))
        self.assertTrue(any('altered source condition'in e for e in r['errors']))

    def test_whole_qualification_cannot_silently_disappear(self):
        def remove(rows):
            row=next(r for r in rows if r['id']=='R21')
            clause=row['source_clause_ids'].pop()
            row['conditions']=[c for c in row['conditions']if c['source_clause_id']!=clause]
        r=self.mutated('rules.json',remove)
        self.assertTrue(any('Required clause relationship'in e for e in r['errors']))

    def test_group_months_cannot_become_days(self):
        r=self.mutated('clocks.json',lambda rows:next(c for c in rows if c['id']=='C03').update(unit='days',amount=63))
        self.assertTrue(any('C03 clock basis' in e for e in r['errors']))

    def test_notice_and_coverage_end_anchors_cannot_swap(self):
        r=self.mutated('clocks.json',lambda rows:next(c for c in rows if c['id']=='C04').update(start='later_of_notice_or_claim_denial_and_coverage_end'))
        self.assertTrue(any('C04 clock basis'in e for e in r['errors']))
        self.assertTrue(any('D01 synthetic window'in e for e in r['errors']))

    def test_plan_n_cannot_enter_ordinary_event_choices(self):
        r=self.mutated('policy-choices.json',lambda x:x['ordinary_event_newly_eligible'].append('N'))
        self.assertTrue(any('Newly eligible choices'in e for e in r['errors']))

    def test_newly_eligible_or_cannot_become_and(self):
        def change(rows):
            p=next(x for x in rows if x['id']=='P01')
            p['expression']={'not':{'all':['turned_65_before_2020','qualified_part_a_before_2020']}}
        r=self.mutated('synthetic-predicate-patterns.json',change)
        self.assertTrue(any('T02 synthetic predicate'in e for e in r['errors']))

    def test_unknown_does_not_become_false(self):
        self.assertIsNone(validator.boolean_pattern({'all':['known','missing']},{'known':True}))
        self.assertIsNone(validator.boolean_pattern({'not':'missing'},{}))

    def test_personal_deadline_execution_stays_disabled(self):
        with self.assertRaisesRegex(ValueError,'Personal deadline'):
            validator.synthetic_window({'start':'policy_delivery_or_receipt','amount':30,'unit':'days'},{'receipt':'2026-01-31'})

    def test_issuer_working_days_are_not_calendar_days(self):
        self.assertEqual(validator.synthetic_window({'start':'issuer_receives_disenrollment_notice','amount':10,'unit':'working_days'},
                                                    {'event':'2026-10-01'},synthetic=True),(None,None))

    def test_shared_proof_and_window_conditions_cannot_disappear(self):
        r=self.mutated('rules.json',lambda rows:next(x for x in rows if x['id']=='R09').update(shared_requirement_rule_ids=[]))
        self.assertTrue(any('lost common GI'in e for e in r['errors']))

    def test_commercial_input_is_rejected(self):
        r=self.mutated('rules.json',lambda rows:rows[0].update(commission=100))
        self.assertTrue(any('Commercial input'in e for e in r['errors']))

    def test_2027_applicability_cannot_be_relabeled_2026(self):
        r=self.mutated('temporal-reconciliation.json',lambda x:x.update(applicability_statement='These regulations are applicable to coverage beginning January 1, 2026.'))
        self.assertTrue(any('Final-rule date comparison'in e for e in r['errors']))


if __name__=='__main__':unittest.main()
