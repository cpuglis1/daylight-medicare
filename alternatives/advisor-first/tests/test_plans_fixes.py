"""D189: plan checks that state their true cause, and the chat on the Plans pages (:8895).

Real controller and engine, scripted model outputs, fictional reports, no
network. Built from visit 130911a983 (November 18, 2026). These check code
behavior; they do not grade a live model's language.
"""
import copy
import json
import pathlib
import types
import unittest
from unittest.mock import patch

import test_pending_questions as pending
import conversation_planner as planner
import journey_completion
import plans_fixes
import recommendation_engine as engine
import recommendation_http
from guest_profiles import ProfileError
from plans_service import PlansService
from test_recommendation_engine import MA, PDP, GAP, inputs

FIXTURE = json.loads((pathlib.Path(__file__).parent / 'fixtures/plans_checks_20261118.json').read_text())
EXPECTED = FIXTURE['expected']
ASK = 'Can you compare the two plans I have selected? Anything I should note?'
FACTS = dict(reply='Here is how the selected plans differ on the listed terms.', question_target=None, question='')


def visit_inputs(**changes):
    base = dict(doctors='list', medicines='yes', priorities=['total_cost', 'drugs'], cost_preference='lower_monthly',
                travel=['local'], current_coverage=['retiree'], status='incomplete', age=None, gender=None,
                tobacco=None, reported_age=None)
    base.update(changes)
    return inputs(**base)


def matrix(membership=None, state='unknown'):
    return {plan['id']: [{'name': plan['name'], 'state': state, 'membership': membership, 'evidence_dates': []}] for plan in MA}


def evaluate(inp, *, networks=None, original=(), medicines=None, medigap_result=None, causes=True, reported=()):
    result = engine.evaluate(inp, ma_plans=copy.deepcopy(MA), medigap_result=medigap_result,
                             part_d_result=copy.deepcopy(PDP), medicines=medicines, networks=networks, doctors=original)
    return (plans_fixes.annotate(result, inp, networks=networks, original=original, medicines=medicines, reported=reported)
            if causes else result)


def checks_of(result):
    for tab in ('path', 'advantage', 'medigap', 'part_d'):
        for plan_id, plan in (result[tab].get('plans') or {}).items():
            for check in plan['checks']:
                yield tab, plan_id, check


class Causes(unittest.TestCase):
    def side(self, result, name):
        return {c['id']: c for c in result['path']['plans'][name]['checks']}

    def test_every_unknown_check_has_one_cause_and_no_state_changes(self):
        inp = visit_inputs()
        accepts = [{'state': 'accepts'}]
        before = evaluate(inp, networks=matrix(), original=accepts, causes=False)
        after = evaluate(inp, networks=matrix(), original=accepts)
        strip = lambda r: [(t, p, c['id'], c['state']) for t, p, c in checks_of(r)]
        self.assertEqual(strip(before), strip(after))                       # no new scoring
        for key in ('recommended_ids', 'groups'):
            for tab in ('path', 'advantage', 'part_d'):
                self.assertEqual(before[tab].get(key), after[tab].get(key), (tab, key))
        unknown = [(t, p, c) for t, p, c in checks_of(after) if c['state'] == 'unknown']
        self.assertTrue(unknown)
        for tab, plan, check in unknown:
            self.assertIn(check.get('cause'), plans_fixes.CAUSES, (tab, plan, check))
        for _, _, check in checks_of(after):
            if check['state'] != 'unknown':
                self.assertNotIn('cause', check)

    def test_no_needs_person_reason_for_a_detail_the_person_gave(self):
        inp = visit_inputs()
        result = evaluate(inp, networks=matrix(), original=[{'state': 'accepts'}],
                          medicines={p['id']: [{'state': 'unknown'}] for p in MA} | {p['id']: [{'state': 'unknown'}] for p in PDP['plans']})
        reported = {'T03', 'T05', 'T06', 'T07', 'T08', 'T09', 'T10', 'RC04', 'RC21', 'RC22'}   # the visit's reports
        # The same profile with no check result at all: the person is still not blamed.
        bare = evaluate(inp, reported=['RC21', 'RC22'])
        for outcome in (result, bare):
            for tab, plan, check in checks_of(outcome):
                if check.get('cause') == 'needs_person':
                    self.assertFalse(set(check['cause_fields']) & reported, (tab, plan, check))
                    self.assertTrue(check['cause_fields'], (tab, plan, check))
        doctor = next(c for c in bare['advantage']['plans']['hmo-cheap']['checks'] if c['id'] == 'doctors')
        self.assertEqual((doctor['cause'], doctor['note']), ('no_data', plans_fixes.REASONS['doctors_not_run']))

    def test_total_yearly_cost_is_not_calculated_everywhere(self):
        result = evaluate(visit_inputs(), networks=matrix(), original=[{'state': 'accepts'}])
        found = [c for _, _, c in checks_of(result) if c['id'] == 'total_cost']
        self.assertTrue(found)
        for check in found:
            self.assertEqual((check['state'], check['cause'], check['note']),
                             ('unknown', EXPECTED['total_cost']['cause'], EXPECTED['total_cost']['reason']))
            self.assertNotRegex(check['note'], r'(?i)medicine|care use|pharmacy')

    def test_monthly_cost_is_per_side(self):
        result = evaluate(visit_inputs(), networks=matrix(), original=[{'state': 'accepts'}])
        original, advantage = self.side(result, 'original')['lower_monthly'], self.side(result, 'advantage')['lower_monthly']
        want = EXPECTED['lower_monthly_original']
        self.assertEqual((original['cause'], original['cause_fields'], original['note']),
                         (want['cause'], want['fields'], want['reason']))
        self.assertTrue(advantage['note'].startswith(EXPECTED['lower_monthly_advantage']['reason_starts']), advantage)
        self.assertNotIn(EXPECTED['lower_monthly_advantage']['must_not_mention'], advantage['note'])
        self.assertEqual(advantage['state'], 'unknown')                      # shown, not scored
        # Medigap details in, prices found: the comparison is made as before.
        ready = evaluate(inputs(doctors='list', medicines='yes', cost_preference='lower_monthly'), medigap_result=copy.deepcopy(GAP))
        states = {s: self.side(ready, s)['lower_monthly']['state'] for s in ('original', 'advantage')}
        self.assertEqual(set(states.values()), {'met', 'not_met'})

    def test_doctor_reason_follows_whether_the_check_ran(self):
        ran = evaluate(visit_inputs(), networks=matrix(), original=[{'state': 'accepts'}])
        for plan in ran['advantage']['plans'].values():
            check = next(c for c in plan['checks'] if c['id'] == 'doctors')
            self.assertEqual((check['cause'], check['note']),
                             (EXPECTED['doctors_with_check']['cause'], EXPECTED['doctors_with_check']['reason']))
        self.assertEqual(self.side(ran, 'advantage')['doctors']['cause'], 'no_data')
        self.assertEqual(self.side(ran, 'original')['doctors']['state'], 'met')
        listed = evaluate(visit_inputs(), networks=matrix('listed_in_network', 'dated_listing'), original=[{'state': 'accepts'}])
        out = evaluate(visit_inputs(), networks=matrix('out_of_network', 'confirmed'), original=[{'state': 'accepts'}])
        self.assertEqual({next(c['state'] for c in p['checks'] if c['id'] == 'doctors') for p in listed['advantage']['plans'].values()}, {'met'})
        self.assertEqual({next(c['state'] for c in p['checks'] if c['id'] == 'doctors') for p in out['advantage']['plans'].values()}, {'not_met'})
        not_run = evaluate(visit_inputs())
        want = EXPECTED['doctors_without_check']
        for plan in not_run['advantage']['plans'].values():
            check = next(c for c in plan['checks'] if c['id'] == 'doctors')
            self.assertEqual((check['cause'], check['cause_fields'], check['note']), (want['cause'], want['fields'], want['reason']))
        self.assertEqual(self.side(not_run, 'original')['doctors']['note'], want['reason'])
        none_named = evaluate(visit_inputs(doctors=None, priorities=['doctors']))
        check = next(c for c in none_named['advantage']['plans']['hmo-cheap']['checks'] if c['id'] == 'doctors')
        self.assertEqual((check['cause'], check['cause_fields']), ('needs_person', ['T06']))

    def test_closing_summary_and_plans_pages_agree(self):
        flow = types.SimpleNamespace(plans_fixes=True, rows=lambda g, r: [
            {'id': 'T06', 'status': 'reported', 'value': 'Dr. Example'}, {'id': 'T07', 'status': 'reported', 'value': 'Examplol'}])
        label = lambda checks: {row['label']: row['value'] for row in journey_completion._learned(flow, {}, {}, None, checks)}
        ran = [{'kind': 'doctor_matrix', 'key': 'doctor:doctor-1'}, {'kind': 'formulary', 'key': 'formulary'}]
        self.assertEqual(label(ran), {'Checked': 'Dr. Example · Examplol'})
        self.assertEqual(label([]), {'To check': 'Dr. Example · Examplol'})
        self.assertEqual(label(ran[:1]), {'Checked': 'Dr. Example', 'To check': 'Examplol'})
        flow.plans_fixes = False
        self.assertEqual(label(ran), {'To check': 'Dr. Example · Examplol'})          # switch off: as before
        # Plans pages, same check results: checked means no_data, never "needs your details".
        plans = evaluate(visit_inputs(), networks=matrix(), original=[{'state': 'accepts'}])
        self.assertEqual({next(c['cause'] for c in p['checks'] if c['id'] == 'doctors') for p in plans['advantage']['plans'].values()}, {'no_data'})

    def test_handoff_annotates_only_with_the_switch_on(self):
        def run(on):
            server = types.SimpleNamespace(adaptive=types.SimpleNamespace(plans_fixes=on, reference={'zips': {}}))
            rows = {p['id']: {'name': p['name'], 'state': 'unknown', 'membership': None, 'evidence_dates': []} for p in MA}
            with patch('recommendation_http.ma_plans', return_value=copy.deepcopy(MA)), \
                    patch('recommendation_http.part_d_pilot.published_plans', return_value=copy.deepcopy(PDP)):
                return recommendation_http.evaluate(server, visit_inputs(), None, None,
                    checks=[{'kind': 'doctor_matrix', 'key': 'doctor:doctor-1', 'plans': rows, 'original_medicare': {'state': 'accepts'}}],
                    expected_doctors={'doctor-1': {'name': 'Example'}})
        on, off = run(True), run(False)
        self.assertEqual(on['causes'], plans_fixes.VERSION)
        self.assertNotIn('causes', off)
        self.assertFalse([c for _, _, c in checks_of(off) if 'cause' in c])
        self.assertEqual(next(c['note'] for c in off['advantage']['plans']['hmo-cheap']['checks'] if c['id'] == 'total_cost'),
                         'Needs your medicines and care use')
        self.assertEqual(next(c['cause'] for c in on['advantage']['plans']['hmo-cheap']['checks'] if c['id'] == 'doctors'), 'no_data')


class PlansChat(pending.PendingBase):
    fixes = True

    def setUp(self):
        pending.PendingBase.setUp(self)
        self.flow.plans_service = PlansService(self.flow)
        if self.fixes:
            plans_fixes.enable(self.flow)
        self.first()

    def view(self):
        return self.flow.plans_service.workspace(self.owner)

    def context(self, navigation='advantage', compared=(), **extra):
        view = self.view()
        inside = navigation == 'advantage'
        ids = [p['id'] for p in view['plans']]
        return {'version': 'plans-context-v1', 'reviewToken': None, 'viewDigest': view['view_digest'],
                'visibleIds': ids[:4] if inside else [], 'comparedIds': list(compared) if inside else [],
                'selectedId': None, 'field': None, 'mode': 'compare' if compared and inside else 'all',
                'navigation': navigation, **extra}

    def send(self, text, context, compose=None, **kw):
        self.extractions.append(self.read(text, targets=[], mode='discuss', task='', disposition='none', **kw))
        self.compositions.append(compose or FACTS)
        return self.take(self.payload({'type': 'message', 'message': text}, plansContextPolicy='plans-context-v1',
                                      plansContext=copy.deepcopy(context)))

    def choose(self):
        plan = self.view()['plans'][0]
        self.turn({'type': 'enrollment_decision', 'selected_plan': {'product': 'advantage', 'plan_id': plan['id'], 'name': plan['name']}})
        return plan

    def test_the_exact_failing_sequence_now_sends_and_compares(self):
        chosen = self.choose()
        ids = [p['id'] for p in self.view()['plans'][:2]]
        out = self.send(ASK, self.context(compared=ids))
        self.assertEqual(out['generated']['status'], 'complete', out.get('notice'))
        sent = self.composed_context()['plans_context']
        self.assertEqual(sent['compared_ids'], ids)
        both = {p['id']: p for p in sent['plans'] if p['id'] in ids}
        self.assertEqual(set(both), set(ids))
        for plan in both.values():
            self.assertTrue(plan['fields'] and plan['type'])                  # every server-projected field of both plans
        self.assertEqual(sent['chosen_plan'], {'product': 'advantage', 'plan_id': chosen['id'], 'name': chosen['name']})
        self.assertEqual(sent['selection_rule'], plans_fixes.COMPARE_RULE)
        self.assertNotIn('selection_request', sent)
        self.assertEqual(self.flow.value(self.g, 'intent.selectedPlan')['plan_id'], chosen['id'])   # restored after validation

    def test_ranking_from_the_model_is_not_shown(self):
        ids = [p['id'] for p in self.view()['plans'][:2]]
        ranked = 'You should choose the first plan.'
        out = self.send(ASK, self.context(compared=ids), compose=dict(reply=ranked, question_target=None, question=''))
        self.assertNotIn(ranked, out.get('reply') or '')

    def test_nothing_selected_is_stated_to_the_composer(self):
        self.send(ASK, self.context())
        sent = self.composed_context()['plans_context']
        self.assertEqual((sent['compared_ids'], sent['selected_id'], sent['chosen_plan']), ([], None, None))
        self.assertEqual(sent['selection_rule'], plans_fixes.NOTHING_SELECTED)

    def test_every_advisor_field_at_once_sends_from_every_plans_view(self):
        self.choose()
        for identifier, choice in (('MG_SEX', 'Female'), ('MG_TOBACCO', 'Non-Tobacco')):
            try:
                self.choice(identifier, choice=choice)
            except ProfileError:
                pass
        text = 'I was born in March 1961 and my Part B started in April 2026.'
        birth = {'kind': 'birth', 'subject': 'beneficiary', 'quote': 'born in March 1961', 'status': '', 'month': 3,
                 'year': 1961, 'product': '', 'name': '', 'carrier': '', 'letter': ''}
        self.say(text, targets=[], disposition='none', coverage_reports=[birth])
        held = set(self.g['fields'])
        for group in ('intent.selectedPlan', 'coverage.birth', 'situation.retirement', 'enrollment.partA', 'medigap.ageOn20261110'):
            self.assertIn(group, held, sorted(held))
        for navigation in ('paths', 'ab', 'guide', 'supplement', 'part-d', 'advantage', 'advantage-drugs'):
            out = self.send('What does this page show?', self.context(navigation))
            self.assertEqual(out['generated']['status'], 'complete', navigation)
        self.assertIn('intent.selectedPlan', self.g['fields'])
        # Derived from the field tables: nothing advisor-first writes reaches the strict check.
        strict, extras = plans_fixes.set_aside(self.flow, self.g)
        self.assertLessEqual(set(strict['fields']), plans_fixes.contract_fields(self.flow.contract))
        self.assertIn('intent.selectedPlan', extras)

    def test_a_truly_unknown_field_is_still_rejected_with_a_plain_sentence(self):
        import natural_flow
        guide = copy.deepcopy(self.g)
        guide['fields']['made.up'] = copy.deepcopy(guide['fields']['subject.role'])
        with self.assertRaises(ProfileError) as caught:
            self.flow.validate(guide, self.r)                              # stopped by the local provenance check
        self.assertEqual(str(caught.exception), natural_flow.SEND_FAILED)
        guide['fields']['made.up']['confirmation'] = 'confirmed_by_user'
        with self.assertRaises(ProfileError) as caught:
            self.flow.validate(guide, self.r)                              # stopped by the inherited strict validation
        self.assertEqual(str(caught.exception), natural_flow.SEND_FAILED)
        self.assertNotIn('profile field', str(caught.exception))
        strict, extras = plans_fixes.set_aside(self.flow, guide)
        self.assertIn('made.up', strict['fields'])
        self.assertNotIn('made.up', extras)

    def test_part_d_and_medigap_selections_travel_as_published_fields(self):
        rows = copy.deepcopy(PDP['plans'])
        for row, name in zip(rows, ('Alpha Rx', 'Beta Rx', 'Gamma Rx')):
            row['name'] = name
        gap = [dict(p, company='Fictional Mutual') for p in copy.deepcopy(GAP['plans'])]
        self.flow.plans_selection_read = lambda product, g, r: rows if product == 'part_d' else gap
        self.send(ASK, self.context('part-d', selection=['pdp-zero', 'pdp-low-ded']))
        sent = self.composed_context()
        plans = {p['id']: p for p in sent['plans_context']['plans']}
        self.assertEqual(plans['pdp-zero']['fields']['total_premium']['value'], '$0.00')
        self.assertEqual(plans['pdp-low-ded']['fields']['annual_deductible']['value'], '$0.00')
        self.assertEqual(plans['pdp-low-ded']['fields']['total_premium']['value'], '$98.00')
        self.assertEqual(sent['plans_context']['selection_rule'], plans_fixes.COMPARE_RULE)
        evidence = [e['text'] for e in sent['evidence'] if e.get('kind') == 'published_plan_field']
        self.assertTrue(any('Beta Rx' in t and '$98.00' in t for t in evidence), evidence[:4])
        self.send(ASK, self.context('supplement', selection=['G-15000', 'N-11000']))
        plans = {p['id']: p for p in self.composed_context()['plans_context']['plans']}
        self.assertEqual(plans['G-15000']['fields']['monthly_premium']['value'], '$150.00')
        self.assertIn('Medigap Plan N', plans['N-11000']['name'])
        with self.assertRaises(ProfileError):
            self.send(ASK, self.context('part-d', selection=['not-listed']))
        with self.assertRaises(ProfileError):
            self.send(ASK, self.context('paths', selection=['pdp-zero']))


class SwitchOff(PlansChat):
    fixes = False
    test_the_exact_failing_sequence_now_sends_and_compares = None
    test_ranking_from_the_model_is_not_shown = None
    test_nothing_selected_is_stated_to_the_composer = None
    test_every_advisor_field_at_once_sends_from_every_plans_view = None
    test_a_truly_unknown_field_is_still_rejected_with_a_plain_sentence = None
    test_part_d_and_medigap_selections_travel_as_published_fields = None

    def test_before_the_chosen_plan_field_is_rejected(self):
        """The root cause, reproduced: intent.selectedPlan, at guest_profiles.validate_guide."""
        self.assertFalse(plans_fixes.enabled(self.flow))
        self.assertEqual(sorted(plans_fixes.advisor_fields() - plans_fixes.contract_fields(self.flow.contract)),
                         ['intent.selectedPlan'])
        self.choose()
        with self.assertRaises(ProfileError) as caught:
            self.send(ASK, self.context())
        self.assertEqual(str(caught.exception), FIXTURE['before']['send_error']['text'])
        with self.assertRaises(ProfileError):
            self.send(ASK, self.context('part-d', selection=['pdp-zero']))      # the new key is not accepted when off

    def test_environment_switch(self):
        import os
        with patch.dict(os.environ, {'DAYLIGHT_PLANS_FIXES': '0'}):
            self.assertFalse(plans_fixes.switch_on())
        with patch.dict(os.environ, {'DAYLIGHT_PLANS_FIXES': '1'}):
            self.assertTrue(plans_fixes.switch_on())


if __name__ == '__main__':
    unittest.main()
