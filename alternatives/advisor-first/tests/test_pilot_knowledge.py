"""Offline evidence/release/correction checks. Receipts below are synthetic."""
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pilot_knowledge import ROOT, CONTROLS, PilotKnowledge, approval_digest
import test_natural_flow as support

DAY = date(2026, 11, 12)


def fixtures(root, controls):
    catalog = json.loads((root / 'catalog.json').read_text())
    sources = {s['id']: s for s in catalog['sources']}
    control = json.loads(CONTROLS.read_text())
    control['approved_facts'] = {f['id']: {
        'digest': approval_digest(f, sources), 'accepted_on': '2026-11-12',
        'reviewer': 'SYNTHETIC TEST ONLY', 'accepted_by': 'SYNTHETIC TEST ONLY'}
        for f in catalog['facts'] if not f['holds']}
    controls.write_text(json.dumps(control))
    return catalog, control


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'data'
        shutil.copytree(ROOT, self.root)
        self.controls = Path(self.temp.name) / 'review.json'
        self.catalog, self.control = fixtures(self.root, self.controls)
        self.index = PilotKnowledge(self.root, self.controls, surface='unified-8895')
        self.net = patch.object(socket, 'create_connection', side_effect=AssertionError('Network forbidden'))
        self.net.start(); self.addCleanup(self.net.stop)

    def select(self, message, **kw):
        return self.index.select(message, today=DAY, **kw)

    def write_controls(self):
        self.controls.write_text(json.dumps(self.control))

    def test_actual_catalog_has_exact_support_and_pending_stays_inactive(self):
        self.control['approved_facts'] = {}; self.write_controls()
        self.assertEqual(self.select('What is a formulary?'), [])
        self.assertEqual(len({f['id'] for f in self.catalog['facts']}), len(self.catalog['facts']))
        for f in self.catalog['facts']:
            self.assertTrue(f['text'] and f['conditions'] and f['support'])
            for p in f['support']:
                s = next(s for s in self.catalog['sources'] if s['id'] == p['source_id'])
                raw = (self.root / s['raw_path']).read_bytes()
                text = (self.root / s['text_path']).read_text()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), s['sha256'])
                self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), s['text_sha256'])
                self.assertEqual(text[p['start']:p['end']], p['quote'])

    def test_actual_owner_acceptance_is_exactly_71_and_scoped(self):
        control = json.loads(CONTROLS.read_text())
        expected = {f['id'] for f in self.catalog['facts'] if not f['holds']}
        self.assertEqual(set(control['approved_facts']), expected)
        self.assertEqual(len(expected), 71)
        self.assertEqual(control['allowed_surfaces'], ['unified-8895'])
        self.assertEqual(PilotKnowledge(surface='unified-8895').status(today=DAY)['available_count'], 71)
        for surface in (None, 'advisor-8893', 'unified-8897'):
            index = PilotKnowledge(surface=surface)
            self.assertEqual(index.select('formulary', today=DAY), [])
            self.assertEqual(index.status(today=DAY)['available_count'], 0)

    def test_disable_switch_withdraws_selection_and_cached_authority(self):
        f = self.select('formulary')[0]
        with patch.dict('os.environ', {'DAYLIGHT_DISABLE_PILOT_KNOWLEDGE':'1'}):
            self.assertEqual(self.select('formulary'), [])
            self.assertFalse(self.index.current({f['id']:f['knowledge_digest']}, today=DAY))
            self.assertFalse(self.index.status(today=DAY)['enabled'])

    def test_specific_question_keeps_conditions_and_official_citation(self):
        result = self.select('What is a formulary?')
        self.assertEqual([f['id'] for f in result], ['pk_formulary'])
        self.assertIn('exact drug', result[0]['conditions'][0])
        self.assertTrue(result[0]['sources'][0]['url'].startswith('https://www.medicare.gov/'))

    def test_florida_is_explicit_not_assumed_from_topic(self):
        self.assertEqual(self.select('What is SHINE?', state='NY'), [])
        self.assertEqual(self.select('What is SHINE in Florida?')[0]['id'], 'pk_shine')
        self.assertEqual(self.select('What is SHINE?', state='FL')[0]['id'], 'pk_shine')

    def test_other_year_and_expired_evidence_stay_out(self):
        self.assertTrue(self.select('formulary', year='2026'))
        self.assertEqual(self.select('formulary', year=2027), [])
        self.assertEqual(self.select('What is changing for 2027 formulary coverage?'), [])
        self.assertEqual(self.index.select('formulary', today=date(2027,1,1)), [])

    def test_no_match_never_invents_a_lookup(self):
        self.assertEqual(self.select('Can you book a restaurant?'), [])
        self.assertLessEqual(len(self.select('Medicare Advantage original medicare medigap premium drug coverage')), 3)

    def test_corrected_topic_does_not_reuse_prior_fact(self):
        first = self.select('What is SHINE in Florida?')
        second = self.select('Actually, what is a formulary?')
        self.assertEqual(first[0]['id'], 'pk_shine')
        self.assertEqual([f['id'] for f in second], ['pk_formulary'])

    def test_new_wording_invalidates_approval(self):
        next(f for f in self.catalog['facts'] if f['id']=='pk_formulary')['text'] = 'Every medicine is covered.'
        (self.root / 'catalog.json').write_text(json.dumps(self.catalog))
        self.assertEqual(self.select('formulary'), [])

    def test_source_change_blocks_use_and_replay(self):
        fact = self.select('formulary')[0]
        source = next(s for s in self.catalog['sources'] if s['id']=='drug-cover')
        (self.root / source['raw_path']).write_text('changed')
        self.assertEqual(self.select('formulary'), [])
        self.assertFalse(self.index.current({fact['id']:fact['knowledge_digest']}, today=DAY))

    def test_source_stop_and_acceptance_withdrawal_apply_without_restart(self):
        f = self.select('formulary')[0]
        self.control['blocked_sources'].append('drug-cover'); self.write_controls()
        self.assertEqual(self.select('formulary'), [])
        self.assertFalse(self.index.current({f['id']:f['knowledge_digest']}, today=DAY))
        self.control['blocked_sources'] = []; self.control['approved_facts'].pop('pk_formulary'); self.write_controls()
        self.assertEqual(self.select('formulary'), [])

    def test_legal_holds_cannot_be_removed_by_a_blanket_receipt(self):
        f = next(f for f in self.catalog['facts'] if f['id']=='pk_fl_group')
        self.control['approved_facts'][f['id']] = {'digest': approval_digest(f, {s['id']:s for s in self.catalog['sources']}),
            'accepted_on':'2026-11-12','reviewer':'SYNTHETIC','accepted_by':'SYNTHETIC'}
        self.write_controls()
        self.assertNotIn(f['id'], [x['id'] for x in self.select('Florida two months')])

    def test_malformed_or_missing_controls_fail_closed(self):
        self.controls.write_text('{')
        self.assertEqual(self.select('formulary'), [])
        self.controls.unlink()
        self.assertEqual(self.select('formulary'), [])


class ConversationTests(unittest.TestCase):
    payload = support.NaturalFlowTests.payload
    take = support.NaturalFlowTests.take
    turn = support.NaturalFlowTests.turn
    message = support.NaturalFlowTests.message
    stage_payloads = support.NaturalFlowTests.stage_payloads
    composed_context = support.NaturalFlowTests.composed_context
    update = staticmethod(support.NaturalFlowTests.update)
    extraction = staticmethod(support.NaturalFlowTests.extraction)

    def setUp(self):
        support.NaturalFlowTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.controls = Path(self.temp.name) / 'review.json'
        self.catalog, self.control = fixtures(ROOT, self.controls)
        self.flow.pilot_knowledge = PilotKnowledge(ROOT, self.controls, surface='unified-8895')
        self.net = patch.object(socket, 'create_connection', side_effect=AssertionError('Network forbidden'))
        self.net.start(); self.addCleanup(self.net.stop)

    def test_question_citation_correction_and_continuation_in_same_visit(self):
        out = self.message('What is SHINE in Florida?', compose={
            'reply':'Florida SHINE offers free, unbiased and confidential health-insurance counseling.',
            'evidence_refs':['pk_shine']})
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertTrue(any(s['url']=='https://www.floridashine.org/home.aspx' for s in out['advisor']['sources']))
        self.assertNotIn('Medicare.gov:', out['advisor']['sources'][0]['label'])
        self.assertTrue(out['assessment']['nextQuestion'])
        out2 = self.message('Actually, what is a formulary?', compose={
            'reply':'A formulary is a plan’s list of covered prescription drugs.', 'evidence_refs':['pk_formulary']})
        self.assertEqual(out2['generated']['status'], 'complete')
        self.assertEqual(set(out2['knowledgeReceipts']), {'pk_formulary'})
        self.assertTrue(out2['assessment']['nextQuestion'])
        self.assertNotIn('pk_shine', [f['id'] for f in self.composed_context()['evidence']])
        self.assertEqual(len(self.calls), 4, 'Only existing interpretation and composition per turn')

    def test_pending_catalog_and_unknown_scope_do_not_inject_claims(self):
        self.control['approved_facts'] = {}
        self.controls.write_text(json.dumps(self.control))
        out = self.message('What is a formulary?')
        self.assertFalse(any(f['id'].startswith('pk_') for f in self.composed_context()['evidence']))
        self.assertNotIn('knowledgeReceipts', out)
        self.assertTrue(out['assessment']['nextQuestion'])

    def test_resolved_location_reused_and_correction_invalidates_florida_scope(self):
        self.message('This is for me. I live in ZIP 34102.', updates=[
            self.update('RC01', {'choice':'self'}, 'This is for me.'),
            self.update('T03', {'zip':'34102'}, '34102')])
        self.message('What is SHINE?', compose={
            'reply':'Florida SHINE offers free health-insurance counseling.', 'evidence_refs':['pk_shine']})
        self.assertIn('pk_shine', [f['id'] for f in self.composed_context()['evidence']])
        self.message('Correction: I live in ZIP 10001.', updates=[
            self.update('T03', {'zip':'10001'}, '10001', correction=True)])
        self.message('What is SHINE?')
        self.assertNotIn('pk_shine', [f['id'] for f in self.composed_context()['evidence']])

    def test_stop_during_composition_rejects_new_reply(self):
        def compose(sent):
            self.control['blocked_sources'].append('drug-cover')
            self.controls.write_text(json.dumps(self.control))
            return {'reply':'A formulary is a plan’s list of covered prescription drugs.', 'evidence_refs':['pk_formulary']}
        out = self.message('What is a formulary?', compose=compose)
        self.assertNotIn('knowledgeReceipts', out)
        self.assertNotIn('A formulary is', out['reply'])
        self.assertTrue(out['assessment']['nextQuestion'])

    def test_replayed_reply_withdraws_stale_sources_and_preserves_reports(self):
        out = self.message('What is a formulary?', compose={
            'reply':'A formulary is a plan’s list of covered prescription drugs.', 'evidence_refs':['pk_formulary']})
        self.control['blocked_sources'].append('drug-cover')
        self.controls.write_text(json.dumps(self.control))
        replay = self.flow.replay_response(self.owner, out)
        self.assertEqual(replay['generated']['code'], 'knowledge_source_stale')
        self.assertEqual(replay['guide'], out['guide'])
        self.assertEqual(replay['assessment']['nextQuestion'], out['assessment']['nextQuestion'])
        self.assertNotIn('A formulary is', replay['reply'])
        self.assertNotIn('knowledgeReceipts', replay)
        self.assertFalse(any('what-drug-plans-cover' in s['url'] for s in replay['advisor']['sources']))


if __name__ == '__main__':
    unittest.main()
