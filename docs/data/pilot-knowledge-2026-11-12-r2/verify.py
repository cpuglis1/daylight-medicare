"""Offline source, preservation and retrieval checks; no live model calls.

Synthetic approval exists only in a temporary directory and is never activation.
"""
from datetime import date
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
sys.path.insert(0, str(REPO / 'alternatives/advisor-first'))
from pilot_knowledge import PilotKnowledge, approval_digest, ROOT as ACTIVE_ROOT, CONTROLS

DAY = date(2026, 11, 12)
CATALOG = json.loads((ROOT / 'catalog.json').read_text())
FACTS = {f['id']: f for f in CATALOG['facts']}
SOURCES = {s['id']: s for s in CATALOG['sources']}
NEW = set(json.loads((ROOT / 'addition-ids.json').read_text()))
HELD = {'pk_fl_under65', 'pk_fl_group', 'pk_fl_waiting'}
CASES = [
    ('What does Part A cover?', 'pk_part_a_benefits'),
    ('Do I need 40 quarters of work?', 'pk_part_a_premium'),
    ('What is the Part B premium in 2026?', 'pk_part_b_benefits_premium'),
    ('What is the Part C premium?', 'pk_part_c_premium'),
    ('Is Part D automatic?', 'pk_part_d_optional'),
    ('Does ALS mean a waiting period?', 'pk_disability_eligibility'),
    ('How does kidney failure affect Medicare?', 'pk_esrd_eligibility'),
    ('Does an observation stay count for skilled nursing?', 'pk_snf'),
    ('Will Medicare pay for custodial care?', 'pk_custodial'),
    ('When can I join my first drug plan?', 'pk_initial_plan_window'),
    ('Which enrollment periods are there?', 'pk_enrollment_windows'),
    ('How does the eight month window work?', 'pk_work_sep_start'),
    ('What if my birthday is the first of the month?', 'pk_first_day_birthday'),
    ('What happens when adding Part B later?', 'pk_new_part_b_plan_window'),
    ('What does loss of creditable coverage allow?', 'pk_plan_coverage_loss_window'),
    ('When does an MA open enrollment change start?', 'pk_ma_oep_effective'),
    ('When is the medigap enrollment window?', 'pk_medigap_window_scope'),
    ('How long does the Part A penalty last?', 'pk_penalty_a'),
    ('What if I was 23 months late?', 'pk_penalty_b'),
    ('Is the Part D penalty based on my premium?', 'pk_penalty_d'),
    ('What happens with 100 employees?', 'pk_payer_disability'),
    ('How does ESRD who pays first work?', 'pk_payer_esrd'),
    ('For COBRA who pays first?', 'pk_payer_retiree_cobra'),
    ('Who pays after a work injury?', 'pk_payer_injury'),
    ('How do drug tiers work?', 'pk_formulary_tiers'),
    ('Can I ask for a formulary exception?', 'pk_formulary_exception'),
    ('What is a tiering exception?', 'pk_tiering_exception'),
    ('Does Medigap drug coverage come with the policy?', 'pk_medigap_drug_exclusion'),
    ('What is the Part D cap in 2026?', 'pk_part_d_cap'),
    ('Who funds Medicaid?', 'pk_medicaid_governance'),
    ('What is the Social Security disability definition?', 'pk_ssa_disability_definition'),
]


class SocialInsuranceIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.control = json.loads((ROOT / 'review-controls.json').read_text())
        self.control['approved_facts'].update({i: {
            'digest': approval_digest(FACTS[i], SOURCES), 'accepted_on': '2026-11-12',
            'reviewer': 'SYNTHETIC OFFLINE TEST ONLY',
            'accepted_by': 'SYNTHETIC OFFLINE TEST ONLY'} for i in NEW})
        self.path = Path(self.temp.name) / 'synthetic-controls.json'
        self.save()
        self.index = PilotKnowledge(ROOT, self.path, surface='unified-8895')
        network = patch.object(socket, 'create_connection', side_effect=AssertionError('Network forbidden'))
        network.start(); self.addCleanup(network.stop)

    def save(self):
        self.path.write_text(json.dumps(self.control))

    def lookup(self, query, **kw):
        return self.index.select(query, today=DAY, **kw)

    def test_original_revision_and_runtime_approval_are_unchanged(self):
        evidence = REPO / 'audit-evidence/pilot-knowledge-social-insurance-20261112'
        before = json.loads((evidence / 'r1-before-sha256.json').read_text())
        previous = ROOT.with_name('pilot-knowledge-2026-11-12-r1')
        self.assertEqual(ACTIVE_ROOT, previous)
        self.assertEqual(before, {str(p.relative_to(previous)):hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in previous.rglob('*') if p.is_file()})
        hashes = json.loads((evidence / 'before-sha256.json').read_text())
        for name in ('alternatives/advisor-first/pilot_knowledge.py',
                     'alternatives/advisor-first/pilot-knowledge-review-8895.json'):
            self.assertEqual(hashlib.sha256((REPO/name).read_bytes()).hexdigest(), hashes[name])
        old = json.loads((previous / 'catalog.json').read_text())
        for fact in old['facts']:
            self.assertEqual(FACTS[fact['id']], fact)
        for source in old['sources']:
            self.assertEqual(SOURCES[source['id']], source)

    def test_pending_extension_cannot_enter_answers(self):
        pending = PilotKnowledge(ROOT, ROOT/'review-controls.json', surface='unified-8895')
        self.assertEqual(pending.status(today=DAY)['available_count'], 40)
        self.assertEqual(PilotKnowledge(surface='unified-8895').status(today=DAY)['available_count'], 40)
        for query, _ in CASES:
            self.assertTrue(NEW.isdisjoint(f['id'] for f in pending.select(query, today=DAY)))
        self.assertEqual(len(NEW), 31)

    def test_all_new_topics_are_retrievable_with_conditions_and_sources(self):
        self.assertEqual({i for _,i in CASES}, NEW)
        for query, expected in CASES:
            with self.subTest(query=query):
                results = self.lookup(query)
                self.assertIn(expected, [f['id'] for f in results])
                self.assertLessEqual(len(results), 3)
                f = next(f for f in results if f['id']==expected)
                self.assertEqual(f['conditions'], FACTS[expected]['conditions'])
                self.assertTrue(f['sources'])
                self.assertTrue(all(s['url'].startswith('https://') for s in f['sources']))

    def test_every_situation_has_retrievable_evidence_and_separate_start(self):
        situations = json.loads((ROOT/'enrollment-situations.json').read_text())['situations']
        self.assertEqual(len(situations), 16)
        for row in situations:
            with self.subTest(situation=row['id']):
                self.assertTrue(row['window'] and row['action'] and row['coverage_start'] and row['checks'])
                self.assertTrue(set(row['fact_ids']) <= FACTS.keys())
                self.assertTrue(set(row['fact_ids']) & {f['id'] for f in self.lookup(row['example_query'])})

    def test_all_retained_source_bytes_and_passages_are_exact(self):
        for s in SOURCES.values():
            if s['status'] != 'captured':
                continue
            for field, checksum in [('raw_path','sha256'), ('text_path','text_sha256')]:
                p = (ROOT/s[field]).resolve()
                self.assertTrue(p.is_relative_to(ROOT))
                self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), s[checksum])
        for f in FACTS.values():
            for p in f['support']:
                self.assertIn(p['source_id'], f['source_ids'])
                s = SOURCES[p['source_id']]
                self.assertEqual(s['status'], 'captured')
                q = (ROOT/s['text_path']).read_text()[p['start']:p['end']]
                self.assertEqual(q, p['quote'])
                self.assertEqual(hashlib.sha256(q.encode()).hexdigest(), p['sha256'])

    def test_stopped_source_and_florida_holds_stay_out(self):
        self.assertEqual(SOURCES['ssa-disability']['status'], 'stop_http')
        self.assertEqual(SOURCES['ssa-disability']['http_status'], 403)
        self.assertTrue(all('ssa-disability' not in f['source_ids'] for f in FACTS.values()))
        self.assertEqual({f['id'] for f in FACTS.values() if f['holds']}, HELD)
        # Even accidentally granting a receipt cannot remove a substantive hold.
        for i in HELD:
            self.control['approved_facts'][i] = {'digest':approval_digest(FACTS[i],SOURCES),
                'accepted_on':'2026-11-12','reviewer':'SYNTHETIC','accepted_by':'SYNTHETIC'}
        self.save()
        for i in HELD:
            for alias in FACTS[i]['aliases']:
                self.assertNotIn(i, [f['id'] for f in self.lookup('Florida '+alias, state='FL')])

    def test_year_expiry_and_wrong_surface_fail_closed(self):
        self.assertEqual(self.lookup('Part B premium in 2027'), [])
        self.assertEqual(self.lookup('Part D cap', year=2027), [])
        self.assertEqual(self.index.select('Part D cap', today=date(2027,1,1)), [])
        wrong = PilotKnowledge(ROOT, self.path, surface='advisor-8893')
        self.assertEqual(wrong.select('Part D cap', today=DAY), [])

    def test_specific_windows_and_payer_cases_do_not_replace_each_other(self):
        pairs = [
            ('What is the general enrollment period?', 'pk_gep', 'pk_ma_oep_effective'),
            ('MA open enrollment', 'pk_ma_oep_effective', 'pk_gep'),
            ('Part B special enrollment', 'pk_work_sep_start', 'pk_plan_coverage_loss_window'),
            ('Loss of creditable coverage', 'pk_plan_coverage_loss_window', 'pk_work_sep_start'),
            ('Disability who pays first with 100 employees?', 'pk_payer_disability', 'pk_payer_esrd'),
            ('ESRD who pays first?', 'pk_payer_esrd', 'pk_payer_disability'),
            ('Formulary exception', 'pk_formulary_exception', 'pk_tiering_exception'),
            ('Tiering exception', 'pk_tiering_exception', 'pk_formulary_exception'),
        ]
        for query, expected, unrelated in pairs:
            with self.subTest(query=query):
                found = {f['id'] for f in self.lookup(query)}
                self.assertIn(expected, found)
                self.assertNotIn(unrelated, found)

    def test_new_fact_withdrawal_also_invalidates_cached_receipt(self):
        f = next(f for f in self.lookup('Part D cap') if f['id']=='pk_part_d_cap')
        receipt = {f['id']:f['knowledge_digest']}
        self.assertTrue(self.index.current(receipt, today=DAY))
        self.control['blocked_sources'].append('partd-redesign'); self.save()
        self.assertNotIn(f['id'], [x['id'] for x in self.lookup('Part D cap')])
        self.assertFalse(self.index.current(receipt, today=DAY))


if __name__ == '__main__':
    unittest.main(verbosity=2)
