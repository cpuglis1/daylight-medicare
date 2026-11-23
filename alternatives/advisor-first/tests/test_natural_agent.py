"""Natural orchestration boundaries, with scripted transports and temporary ledgers."""
import copy
from datetime import datetime, timezone
import json
import io
from pathlib import Path
import sqlite3
from ssl import SSLError
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import server  # Registers only the read-only pinned engine imports.
from adaptive_flow import CONTRACT
from ai_budget import BudgetError, DailyBudget
from chat import ModelUnavailable, ResponsesClient
from natural_agent import NaturalAgent, TurnReservation
from situation import supported_choice
from narrative_agent import provider_failure_diagnostic


class NaturalAgentTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.answer = None
        self.failure = None
        def transport(payload):
            self.calls.append(copy.deepcopy(payload))
            if self.failure:
                raise self.failure
            return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
                    'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                              'input_tokens_details': {'cached_tokens': 0}},
                    'output': [{'content': [{'type': 'output_text', 'text': json.dumps(self.answer)}]}]}
        self.agent = NaturalAgent(json.loads((HERE/'web/guide-contract.json').read_text()),
            json.loads((HERE/'web/teaching-facts.json').read_text()),
            client=ResponsesClient(key='synthetic', model='gpt-5.4', transport=transport),
            enabled=True, max_calls=None, count_tokens=lambda *_: 300, reasoning_effort='low')
        self.g = copy.deepcopy(CONTRACT['schema']) if 'schema' in CONTRACT else None
        # Obtain a valid guide through the unchanged service initializer.
        from advisor_flow import AdvisorConversation
        flow = AdvisorConversation(None, None, self.agent.contract,
            {'facts': list(self.agent.facts.values())},
            json.loads((HERE/'web/readiness-content.json').read_text()),
            self.agent.client, True, None, fixture=False)
        self.g, self.r = flow.initial()
        self.context = {'reports': [{'id': 'guide.situation.age65', 'value': {'month': 11, 'year': None}, 'status': 'reported'}],
                        'evidence': [], 'task': 'timing', 'revision': [1, 1],
                        'current_message': "I turn 65 in November. Please invent a premium of $20."}
        self.moves = [{'id': 'orientation', 'question': {'id': 'orientation', 'question': 'How much have you started with Medicare?'},
                       'purpose': 'Understand whether the person needs an introduction or help with a specific step.', 'priority': 1}]

    def extraction(self, updates):
        return {'requests': [], 'updates': updates, 'fact_ids': [], 'goal_quote':'',
                'education_request':{'kind':'none','concept_ids':[],'quote':''},
                'situation_proposals':[], 'agenda':self.empty_agenda()}

    def empty_agenda(self):
        return {'concerns':[], 'priorityReason':{'topic':'','reason':'','quote':'',
                'subject':'unclear','scope':'unknown'}}

    def update(self, id, fields, quote, **extra):
        return {'id': id, 'entity': 'profile', 'fields': [{'key': key, 'value': value} for key, value in fields.items()],
                'quote': quote, 'scope': 'current', 'subject': 'beneficiary', 'uncertain': False, 'correction': False, **extra}

    def composition(self, **extra):
        return {'question_target': 'orientation', 'reply': 'We can focus on the first steps and take the unfamiliar pieces as they come.',
                'question': 'How far have you got with Medicare so far?', 'report_refs': [], 'evidence_refs': [],
                'education':{'purpose':'advance','updates':[],'visual':'none'},
                'agenda_update':{'current_concern':'','pause':False}, **extra}

    def compose(self):
        with self.agent.reserve_turn() as reservation:
            return self.agent.compose('owner', self.context, self.moves, str(uuid.uuid4()), reservation)

    def test_empty_candidates_allow_a_useful_educational_followup(self):
        self.moves = []
        self.answer = self.composition(question_target=None, reply='We can pause here.',
                                       question='Which part would you like to unpack?')
        self.assertEqual(self.compose()['question'], self.answer['question'])
        spec = self.calls[-1]['text']['format']['schema']['properties']
        self.assertEqual(spec['question_target']['enum'], [None])
        self.assertNotIn('enum', spec['question'])

    def ledger(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name)
        path.chmod(0o700)
        rates = json.loads((HERE.parents[1]/'alternatives/chat-first/cms-slice/config/ai-pricing.json').read_text())
        rates['verified_at'] = '2026-10-30T00:00:00Z'
        rates['valid_until'] = '2026-11-04T00:00:00Z'
        pricing = path/'pricing.json'
        pricing.write_text(json.dumps(rates))
        return DailyBudget(path/'usage.sqlite3', pricing_path=pricing,
                           clock=lambda: datetime(2026, 10, 30, 16, tzinfo=timezone.utc).timestamp())

    def test_generated_bridge_question_use_existing_slots_and_safe_payload(self):
        self.answer = self.composition()
        out = self.compose()
        self.assertEqual(out['question'], self.answer['question'])
        sent = self.calls[0]
        self.assertEqual(sent['max_output_tokens'], 900)
        self.assertEqual(sent['tools'], [])
        self.assertFalse(sent['store'])
        self.assertEqual(sent['reasoning'], {'effort': 'none'})
        self.assertIn('resolved_context', json.loads(sent['input'][0]['content']))

    def test_composer_receives_question_candidates_without_response_mode_choices(self):
        self.moves=[{'id':'answer','question':None},
                    {'id':'concern:T05','question':{'id':'T05','question':'What health insurance do you have now?'},
                     'purpose':'Current insurance determines the relevant timing checks.','priority':0}]
        self.answer=self.composition(question_target='T05',reply='We can work through the timing together.',
                                     question='What health insurance do you have now?')
        out=self.compose()
        sent=json.loads(self.calls[-1]['input'][0]['content'])
        self.assertNotIn('eligible_moves',sent)
        self.assertEqual([item['id'] for item in sent['question_candidates']],['T05'])
        self.assertEqual(out['reply'],self.answer['reply'])
        self.assertEqual(out['question'],self.answer['question'])
        self.assertNotIn('move_id',out)
        self.assertEqual(sent['resolved_context']['current_message'],self.context['current_message'])

    def test_reviewed_answer_can_continue_with_relevant_approved_question(self):
        self.moves=[{'id':'T05','question':{'id':'T05','question':'What health insurance do you have now?'}}]
        self.context['evidence']=[copy.deepcopy(self.agent.facts['dates'])]
        self.answer=self.composition(question_target='T05',
            reply='Medicare enrollment timing depends on the coverage you have now.',
            question='What health insurance do you have now?',evidence_refs=['dates'])
        out=self.compose()
        self.assertTrue(out['reply'])
        self.assertEqual(out['question_target'],'T05')
        self.assertTrue(out['question'])

    def test_required_clarification_blocks_other_intake_but_allows_side_education(self):
        self.moves=[{'id':'clarify:T05','required':True,'question':{'id':'clarify:T05','canonical_id':'T05',
                     'question':'What health insurance do you have now?'}},
                    {'id':'T04','question':{'id':'T04','question':'When would you like Medicare coverage to start?'}}]
        self.answer=self.composition(question_target='T04',reply='',question='When would you like coverage to start?')
        with self.assertRaisesRegex(ModelUnavailable,'required clarification'):
            self.compose()
        self.answer=self.composition(question_target=None,reply='We can stay with that question first.',
                                     question='Which part is unclear?')
        self.assertEqual(self.compose()['question_target'],None)
        self.answer=self.composition(question_target='clarify:T05',reply='',question='When is your birthday?')
        self.assertEqual(self.compose()['question'],'What health insurance do you have now?')

    def test_missing_targeted_question_recovers_canonical_question(self):
        self.answer=self.composition(question='')
        self.assertEqual(self.compose()['question'],self.moves[0]['question']['question'])

    def test_null_target_with_one_exact_canonical_question_recovers_its_id(self):
        self.moves=[{'id':'T03','question':{'id':'T03','question':'What ZIP code do you live in?'}}]
        self.answer=self.composition(question_target=None,reply='We can look at the options in your area.',
                                     question='  what   ZIP code do you live in?  ')
        out=self.compose()
        self.assertEqual(out['question_target'],'T03')
        self.assertEqual(out['question'],'what   ZIP code do you live in?')

    def test_null_educational_question_is_not_assigned_a_personal_target(self):
        self.moves=[{'id':'T03','question':{'id':'T03','question':'What ZIP code do you live in?'}}]
        self.answer=self.composition(question_target=None,reply='We can take that one part at a time.',
                                     question='Which part would you like explained?')
        out=self.compose()
        self.assertIsNone(out['question_target'])
        self.assertEqual(out['question'],self.answer['question'])

    def test_ambiguous_exact_question_match_does_not_guess_a_target(self):
        self.moves=[{'id':identifier,'question':{'id':identifier,'question':'Which detail should we clarify?'}}
                    for identifier in ('T03','T05')]
        self.answer=self.composition(question_target=None,reply='',question='Which detail should we clarify?')
        self.assertIsNone(self.compose()['question_target'])

    def test_required_clarification_is_checked_after_exact_target_recovery(self):
        self.moves=[{'id':'T05','required':True,'question':{'id':'T05','question':'What health insurance do you have now?'}},
                    {'id':'T03','question':{'id':'T03','question':'What ZIP code do you live in?'}}]
        self.answer=self.composition(question_target=None,reply='',question='What ZIP code do you live in?')
        with self.assertRaisesRegex(ModelUnavailable,'required clarification'):
            self.compose()

    def test_explanation_length_is_not_a_ninety_word_conversation_mode(self):
        self.moves=[]
        reply=' '.join(['We can take time to work through your questions together.']*10)
        self.assertGreater(len(reply.split()),90)
        self.answer=self.composition(question_target=None,reply=reply,question='')
        self.assertEqual(self.compose()['reply'],reply)

    def test_composition_reasoning_is_configurable_without_changing_budget_or_call_count(self):
        self.agent.composition_reasoning_effort='low'
        self.answer=self.composition()
        self.compose()
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.calls[0]['reasoning'],{'effort':'low'})
        self.assertEqual(self.calls[0]['max_output_tokens'],900)

    def circumstance(self,source_quote,**extra):
        return {'kind':'age65','subject':'beneficiary','scope':'intended','quote':source_quote,
                'uncertain':False,'correction':False,'month':11,'year':None,'status':'','when':'',**extra}

    def test_semantic_birthday_proposals_accept_both_reported_opening_phrasings(self):
        for message in ['I am turning 65 years old in november and want to enroll in medicare soon',
                        'Im turning 65 in november and am looking to understand my options']:
            with self.subTest(message=message):
                proposal=self.circumstance(message)
                self.answer={**self.extraction([]),'situation_proposals':[proposal]}
                with self.agent.reserve_turn() as reservation:
                    out=self.agent.extract('owner',message,self.g,{},str(uuid.uuid4()),reservation)
                self.assertEqual(out['situation_proposals'],[proposal])
                self.assertIsNone(out['situation_proposals'][0]['year'])
                self.assertNotIn('task',out)

    def test_circumstance_validation_rejects_invented_year_month_and_hypothetical(self):
        message='I am turning 65 years old in November.'
        proposals=[self.circumstance(message,year=2027),self.circumstance(message,month=12),
                   self.circumstance(message,quote='My birthday is in November.')]
        self.answer={**self.extraction([]),'situation_proposals':proposals}
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,{},str(uuid.uuid4()),reservation)
        self.assertEqual(out['situation_proposals'],[])
        self.assertEqual(len(out['rejected_situation_proposals']),3)
        hypothetical='If I am turning 65 in November, what happens?'
        self.assertFalse(self.agent._valid_situation_proposal(self.circumstance(hypothetical),hypothetical))

    def test_circumstance_validation_preserves_supported_retirement_without_coverage_inference(self):
        message="I've been retired for a few years."
        proposal=self.circumstance(message,kind='retirement',scope='current',month=None,
                                   status='retired',when='for a few years')
        self.answer={**self.extraction([]),'situation_proposals':[proposal]}
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,{},str(uuid.uuid4()),reservation)
        self.assertEqual(out['situation_proposals'],[proposal])
        self.assertEqual(out['updates'],[])

    def test_independent_hypothetical_question_does_not_erase_clear_birthday_report(self):
        quote='I turn 65 in November.'
        message=quote+' If I choose a private plan, what should I check?'
        proposal=self.circumstance(quote)
        self.assertTrue(self.agent._valid_situation_proposal(proposal,message))
        hypothetical='If I turn 65 in November, what happens?'
        self.assertFalse(self.agent._valid_situation_proposal(
            self.circumstance('I turn 65 in November'),hypothetical))

    def test_helper_and_beneficiary_situation_guard_uses_current_subject_role(self):
        first_person=self.circumstance('I turn 65 in November.')
        self.assertFalse(self.agent._valid_situation_proposal(first_person,first_person['quote'],role='someone'))
        self.assertTrue(self.agent._valid_situation_proposal(first_person,first_person['quote'],role='self'))
        relative=self.circumstance('My mother turns 65 in November.')
        self.assertFalse(self.agent._valid_situation_proposal(relative,relative['quote'],role='self'))
        self.assertTrue(self.agent._valid_situation_proposal(relative,relative['quote'],role='someone'))

    def test_same_message_helper_subject_report_prevents_capturing_helpers_birthday(self):
        message='This is for my mother. I turn 65 in November.'
        self.answer={**self.extraction([self.update('RC01',{'choice':'someone'},'This is for my mother.')]),
                     'situation_proposals':[self.circumstance('I turn 65 in November.')]}
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,{},str(uuid.uuid4()),reservation)
        self.assertEqual([item['id'] for item in out['updates']],['RC01'])
        self.assertEqual(out['situation_proposals'],[])

    def test_explicit_goal_contract_uses_the_same_bound_as_visit_memory(self):
        self.answer=self.extraction([])
        with self.agent.reserve_turn() as reservation:
            self.agent.extract('owner','I want help understanding my options.',self.g,{},str(uuid.uuid4()),reservation)
        spec=self.calls[-1]['text']['format']['schema']['properties']
        self.assertEqual(spec['goal_quote']['maxLength'],200)

    def test_one_bad_report_does_not_discard_clear_fact(self):
        text = 'My insurance is through my current job. I turn 65 in November.'
        self.answer = self.extraction([self.update('T05', {'choice': 'employer'}, text),
                                      self.update('RC09', {'choice': 'retiree'}, text)])
        with self.agent.reserve_turn() as reservation:
            out = self.agent.extract('owner', text, self.g, {}, str(uuid.uuid4()), reservation)
        self.assertEqual([item['id'] for item in out['updates']], ['T05'])
        self.assertEqual([item['id'] for item in out['rejected_updates']], ['RC09'])
        self.assertEqual(len(self.calls), 1)

    def test_extraction_entity_schema_only_exposes_real_profile_and_item_identities(self):
        self.answer=self.extraction([])
        context={'activeQuestion':{'id':'RC22','entity':'medicine-2','fields':[]},
                 'reports':[{'id':'readiness.RC21.doctor-1.practice','value':'Example clinic'}],
                 'known':[{'id':'readiness.RC22.medicine-extra-3.name','status':'reported'}]}
        with self.agent.reserve_turn() as reservation:
            self.agent.extract('owner','I need help with these details.',self.g,context,str(uuid.uuid4()),reservation)
        entities=self.calls[-1]['text']['format']['schema']['properties']['updates']['items']['properties']['entity']['enum']
        self.assertEqual(set(entities),{'profile','new','doctor-1','medicine-2','medicine-extra-3'})
        self.assertNotIn('timing',entities)
        self.assertNotIn('coverage',entities)

    def test_wrong_nonitem_entity_is_rejected_individually_and_never_normalized(self):
        message="My health insurance is through my wife's current job."
        self.answer=self.extraction([
            self.update('T05',{'choice':'employer'},message),
            self.update('RC09',{'choice':'spouse_job'},message,entity='timing')])
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,{},str(uuid.uuid4()),reservation)
        self.assertEqual([item['id'] for item in out['updates']],['T05'])
        self.assertEqual([item['id'] for item in out['rejected_updates']],['RC09'])
        self.answer=self.extraction([self.update('RC09',{'choice':'spouse_job'},message)])
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,{},str(uuid.uuid4()),reservation)
        self.assertEqual([(item['id'],item['entity']) for item in out['updates']],[('RC09','profile')])

    def test_birthday_correction_cannot_emit_generic_rc28_bookkeeping(self):
        message='Actually, I turn 65 in December, not November.'
        birthday=self.circumstance(message,month=12,correction=True)
        self.answer={**self.extraction([self.update('RC28',{'choice':'different'},message,scope='unknown')]),
                     'situation_proposals':[birthday]}
        context={'activeQuestion':{'id':'T05','entity':'profile','fields':[]}}
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,context,str(uuid.uuid4()),reservation)
        allowed=self.calls[-1]['text']['format']['schema']['properties']['updates']['items']['properties']['id']['enum']
        self.assertNotIn('RC28',allowed)
        self.assertEqual(out['updates'],[])
        self.assertEqual([item['id'] for item in out['rejected_updates']],['RC28'])
        self.assertEqual(out['situation_proposals'],[birthday])
        table=json.loads(self.calls[-1]['input'][0]['content'])['confirmed_context']['question_table']
        self.assertEqual(len(table['rows']),41)
        self.assertIn('RC28',[row[0] for row in table['rows']])

    def test_active_rc28_keeps_its_reviewed_coverage_period_meaning(self):
        message='They apply at different times.'
        self.answer=self.extraction([self.update('RC28',{'choice':'different'},message)])
        context={'activeQuestion':{'id':'RC28','entity':'profile','fields':[]}}
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,context,str(uuid.uuid4()),reservation)
        allowed=self.calls[-1]['text']['format']['schema']['properties']['updates']['items']['properties']['id']['enum']
        self.assertIn('RC28',allowed)
        self.assertEqual([(item['id'],item['fields']) for item in out['updates']],
                         [('RC28',[{'key':'choice','value':'different'}])])

    def test_item_entities_must_be_supplied_and_match_the_question_kind(self):
        self.agent.local.turn_context={
            'reports':[{'id':'readiness.RC21.doctor-1.practice'},
                       {'id':'readiness.RC22.medicine-2.name'}]}
        try:
            self.assertEqual(self.agent._allowed_entities('RC09'),['profile'])
            self.assertEqual(self.agent._allowed_entities('RC21'),['profile','new','doctor-1'])
            self.assertEqual(self.agent._allowed_entities('RC23'),['profile','new','medicine-2'])
        finally:
            self.agent.local.turn_context={}

    def test_pcp_identity_and_location_extract_as_independent_baseline_and_item_reports(self):
        message='My PCP is ashley tunkle in naples'
        baseline=self.update('T06',{'choice':'list','text':'ashley tunkle'},message)
        detail=self.update('RC21',{'choice':'details','practice':'ashley tunkle','city':'naples'},message,entity='new')
        context={'activeQuestion':{'id':'T06','entity':'profile','fields':[]},'reports':[],'known':[]}
        for updates in ([baseline,detail],[detail,baseline]):
            with self.subTest(order=[item['id'] for item in updates]):
                self.answer=self.extraction(updates)
                with self.agent.reserve_turn() as reservation:
                    out=self.agent.extract('owner',message,self.g,context,str(uuid.uuid4()),reservation)
                self.assertEqual({item['id'] for item in out['updates']},{'T06','RC21'})
                self.assertEqual(out['rejected_updates'],[])
                reported=next(item for item in out['updates'] if item['id']=='RC21')
                self.assertEqual(reported['entity'],'new')
                self.assertEqual({field['key']:field['value'] for field in reported['fields']},
                                 {'choice':'details','practice':'ashley tunkle','city':'naples'})

    def test_fabricated_date_is_rejected_individually(self):
        text = 'My job ends in March 2027. My insurance is through my current job.'
        self.answer = self.extraction([self.update('RC11', {'jobEnd': 'April 2027'}, text),
                                      self.update('T05', {'choice': 'employer'}, text)])
        with self.agent.reserve_turn() as reservation:
            out = self.agent.extract('owner', text, self.g, {}, str(uuid.uuid4()), reservation)
        self.assertEqual([item['id'] for item in out['updates']], ['T05'])

    def test_helper_fact_rejected_without_losing_beneficiary_fact(self):
        text = 'This is for my mother. I have insurance through my current job.'
        self.answer = self.extraction([self.update('RC01', {'choice': 'someone'}, text),
                                      self.update('T05', {'choice': 'employer'}, text, subject='learner')])
        with self.agent.reserve_turn() as reservation:
            out = self.agent.extract('owner', text, self.g, {}, str(uuid.uuid4()), reservation)
        self.assertEqual([item['id'] for item in out['updates']], ['RC01'])

    def test_unavailable_reference_is_rejected(self):
        self.answer = self.composition(report_refs=['rejected.retiree'])
        with self.assertRaises(ModelUnavailable): self.compose()

    def test_off_target_question_is_replaced_before_its_discarded_claims_are_checked(self):
        self.moves=[{'id':'T04','question':{'id':'T04',
            'question':'When would you like Medicare coverage to start?'}}]
        self.answer=self.composition(question_target='T04',reply='',question='When is your birthday?')
        self.assertEqual(self.compose()['question'],self.moves[0]['question']['question'])

    def test_recovering_a_question_keeps_personal_reply_grounding_required(self):
        self.moves=[{'id':'T04','question':{'id':'T04',
            'question':'When would you like Medicare coverage to start?'}}]
        self.answer=self.composition(question_target='T04',reply='You are turning 65 in November.',
            question='When is your birthday?')
        with self.assertRaisesRegex(ModelUnavailable,'resolved report reference'):
            self.compose()

    def test_sourced_generic_birthday_month_teaching_needs_no_personal_report_reference(self):
        self.moves=[{'id':'teach:dates','question':{'id':'T04',
            'question':'When would you like Medicare coverage to start?'}}]
        self.context['evidence']=[copy.deepcopy(self.agent.facts['dates'])]
        self.answer={'question_target':'T04',
            'reply':'The month you want Medicare to begin matters because your birthday month and when coverage actually starts are not always the same.',
            'question':'When would you like Medicare coverage to start?',
            'report_refs':[],'evidence_refs':['dates'],
            'education':{'purpose':'advance','updates':[],'visual':'none'},
            'agenda_update':{'current_concern':'timing','pause':False}}
        self.assertEqual(self.compose()['reply'],self.answer['reply'])

    def test_answer_keeps_grounded_teaching_and_open_educational_followup(self):
        self.moves=[{'id':'answer','question':None},
                    {'id':'T04','question':{'id':'T04','question':'When would you like Medicare coverage to start?'}}]
        self.context['evidence']=[copy.deepcopy(self.agent.facts['routesintro'])]
        self.answer=self.composition(question_target=None,
            reply='There are two main routes: Original Medicare, where Parts A and B come through the federal program, and Medicare Advantage, a private plan that provides Parts A and B. A practical difference for seeing doctors is that the rules for how you get care can differ between those two routes.',
            question='Would it help if I explain how seeing doctors usually works under each route?',
            evidence_refs=['routesintro'])
        out=self.compose()
        self.assertEqual(out['reply'],self.answer['reply'])
        self.assertEqual(out['question'],self.answer['question'])
        self.assertEqual(out['evidence_refs'],['routesintro'])

    def test_open_followup_does_not_allow_unsupported_personal_reply(self):
        self.moves=[{'id':'answer','question':None}]
        self.answer=self.composition(question_target=None,reply='Your premium will be $20.',
            question='Would you like another explanation?')
        with self.assertRaises(ModelUnavailable):self.compose()

    def test_nonempty_open_followup_is_a_valid_dialogue_turn(self):
        self.moves=[]
        self.answer=self.composition(question_target=None,reply='',question='What would help clarify that?')
        self.assertEqual(self.compose()['question'],self.answer['question'])

    def test_empty_answer_and_question_are_rejected(self):
        self.moves=[]
        self.answer=self.composition(question_target=None,reply='',question='')
        with self.assertRaises(ModelUnavailable):self.compose()

    def test_known_keep_doctor_priority_asks_for_identity_without_repeating_whether(self):
        self.moves=[{'id':'concern:T06','question':{'id':'T06',
            'question':'Which doctors or hospitals would you like to keep?'}}]
        self.answer=self.composition(question_target='T06',reply='',
            question='Are there doctors or hospitals you want to keep?')
        self.assertEqual(self.compose()['question'],'Which doctors or hospitals would you like to keep?')

    def test_actual_birthday_date_and_timing_assertions_still_need_personal_reference(self):
        for reply in ['Your birthday is in November.',
                      'With your November birthday coming up, we can focus on timing.',
                      'Your birthday is coming up.']:
            with self.subTest(reply=reply):
                self.answer=self.composition(reply=reply)
                with self.assertRaisesRegex(ModelUnavailable,'resolved report reference'):
                    self.compose()

    def test_unsupported_named_insurer_is_rejected(self):
        self.answer = self.composition(reply='Your Blue Cross insurance gives us a useful starting point.', report_refs=['guide.situation.age65'])
        with self.assertRaises(ModelUnavailable): self.compose()

    def test_conversational_capitalization_is_not_a_named_entity(self):
        self.answer = self.composition(reply='Your Medicare questions can guide where we start.')
        self.assertEqual(self.compose()['reply'], self.answer['reply'])

    def test_full_question_semantics_and_orientation_context_reach_extractor(self):
        self.answer = self.extraction([])
        context = {'activeQuestion': {'id': 'orientation', 'fields': [], 'entity': 'profile'}, 'dialogue': {'orientation': 'new'}}
        with self.agent.reserve_turn() as reservation:
            self.agent.extract('owner', 'I am just getting started.', self.g, context, str(uuid.uuid4()), reservation)
        sent = json.loads(self.calls[0]['input'][0]['content'])['confirmed_context']
        self.assertEqual(len(sent['question_table']['rows']), 41)
        self.assertNotIn('definitions', sent)
        self.assertNotIn('question_catalog', sent)
        self.assertEqual(sent['activeQuestion']['id'], 'orientation')

    def test_compact_table_preserves_every_public_question_contract_value(self):
        self.agent.local.turn_context = {'definitions': copy.deepcopy(self.agent.definitions), 'questionCatalog': copy.deepcopy(self.agent.catalog)}
        try:
            sent = self.agent.context(self.g)
        finally:
            self.agent.local.turn_context = {}
        table = sent['question_table']
        self.assertEqual(table['columns'], ['id', 'question', 'options', 'fields', 'purpose', 'dependency', 'requiredWhen', 'cannotInfer'])
        self.assertEqual(len(table['rows']), 41)
        expanded = {row[0]: dict(zip(table['columns'], row)) for row in table['rows']}
        definitions = {item['id']: item for item in self.agent.definitions}
        meanings = {item['id']: item for item in self.agent.catalog}
        self.assertEqual(set(expanded), set(definitions))
        for identifier, definition in definitions.items():
            for key in ['question', 'options', 'fields']:
                self.assertEqual(expanded[identifier][key], definition[key])
            for key in ['purpose', 'dependency', 'requiredWhen', 'cannotInfer']:
                self.assertEqual(expanded[identifier][key], meanings[identifier][key])
        original = json.dumps({'definitions': self.agent.definitions, 'question_catalog': self.agent.catalog})
        compact = json.dumps(table)
        self.assertLess(len(compact), len(original) * .85)
        self.assertNotIn('definitions', sent)
        self.assertNotIn('questionCatalog', sent)

    def test_conversational_punctuation_is_not_a_response_mode_restriction(self):
        self.answer = self.composition(reply='What matters most? We can work through it together.')
        self.assertEqual(self.compose()['reply'],self.answer['reply'])

    def test_current_message_cannot_authorize_amount_or_personal_finding(self):
        self.answer = self.composition(reply='Your premium is $20.')
        with self.assertRaises(ModelUnavailable): self.compose()

    def test_curly_apostrophe_personal_claims_do_not_bypass_guard(self):
        self.answer = self.composition(reply='You’re eligible to enroll now.', report_refs=['guide.situation.age65'])
        with self.assertRaises(ModelUnavailable): self.compose()

    def test_unsupported_insurance_definition_needs_evidence(self):
        self.answer = self.composition(reply='Medicare is private insurance for everyone.')
        with self.assertRaises(ModelUnavailable): self.compose()

    def test_drug_coverage_teaching_needs_evidence_even_with_softened_phrasing(self):
        claims = [
            'Medicare drug coverage is usually handled through a Part D plan or some Medicare Advantage plans.',
            'Drug coverage usually comes through a Part D plan.',
            'Part D plans generally cover prescription drugs.',
            'Medicare Advantage plans may include drug coverage.',
            'Prescription coverage can be part of your Medicare options.',
            'Prescription coverage can be part of what you compare. Part D plans cover every prescription.',
        ]
        for reply in claims:
            with self.subTest(reply=reply):
                self.answer = self.composition(reply=reply)
                with self.assertRaisesRegex(ModelUnavailable, 'reviewed evidence'):
                    self.compose()

    def test_drug_coverage_interest_can_have_a_plain_bridge_without_unsolicited_teaching(self):
        for reply in ['I can help compare options with drug coverage in mind.',
                      'We can include prescription coverage as a priority.',
                      'Prescription coverage can be part of what you compare later.']:
            with self.subTest(reply=reply):
                self.answer = self.composition(reply=reply)
                self.assertEqual(self.compose()['reply'], reply)

    def test_extraction_wire_has_proposals_and_no_routing_or_consumer_prose(self):
        self.answer = self.extraction([])
        with self.agent.reserve_turn() as reservation:
            out = self.agent.extract('owner','I want help understanding my options.',self.g,{},str(uuid.uuid4()),reservation)
        properties=self.calls[-1]['text']['format']['schema']['properties']
        # discourse_note: bounded rolling discourse brief (November 8, 2026).
        self.assertEqual(set(properties),{'updates','requests','fact_ids','agenda','situation_proposals','goal_quote','education_request','discourse_note'})
        for forbidden in ['mode','task','task_quote','reflection','confirmation','move_id','reason_id','practical_request']:
            self.assertNotIn(forbidden,properties)
            self.assertNotIn(forbidden,out)

    def test_explicit_goal_quote_is_separate_from_familiarity(self):
        message='I want to enroll in Medicare and I know very little about it.'
        self.answer={**self.extraction([self.update('T02',{'choice':'new'},'I know very little about it.')]),
                     'goal_quote':'I want to enroll in Medicare'}
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,{},str(uuid.uuid4()),reservation)
        self.assertEqual(out['goal_quote'],'I want to enroll in Medicare')
        self.assertEqual([item['id'] for item in out['updates']],['T02'])

    def test_unsupported_goal_quote_is_quarantined_without_losing_report(self):
        message='My insurance is through my current job.'
        self.answer={**self.extraction([self.update('T05',{'choice':'employer'},message)]),
                     'goal_quote':'I want enrollment help'}
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,{},str(uuid.uuid4()),reservation)
        self.assertEqual(out['goal_quote'],'')
        self.assertEqual(out['rejected_commands'],['goal'])
        self.assertEqual([item['id'] for item in out['updates']],['T05'])

    def test_invalid_check_commands_do_not_discard_clear_spouse_insurance(self):
        message="My health insurance is through my wife's current job."
        updates=[self.update('T05',{'choice':'employer'},message),
                 self.update('RC09',{'choice':'spouse_job'},message)]
        self.answer={**self.extraction(updates),
            'requests':[{'id':'payer_order','quote':'Please check who pays first.'},
                        {'id':'unknown_external_action','quote':message}]}
        context={'task':'timing','activeQuestion':{'id':'T05','question':'What health insurance do you have now?'}}
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,context,str(uuid.uuid4()),reservation)
        self.assertEqual(out['requests'],[])
        self.assertEqual([item['id'] for item in out['updates']],['T05','RC09'])
        self.assertEqual(out['rejected_commands'],['request','request'])

    def test_valid_check_survives_an_invalid_check(self):
        message='Please check payer order. My insurance is through my current job.'
        quote='My insurance is through my current job.'
        self.answer={**self.extraction([self.update('T05',{'choice':'employer'},quote)]),
            'requests':[{'id':'payer_order','quote':'Please check payer order.'},
                        {'id':'timing','quote':'A paraphrased request.'}]}
        with self.agent.reserve_turn() as reservation:
            out=self.agent.extract('owner',message,self.g,{},str(uuid.uuid4()),reservation)
        self.assertEqual(out['requests'],[{'id':'payer_order','quote':'Please check payer order.'}])
        self.assertEqual([item['id'] for item in out['updates']],['T05'])

    def test_malformed_envelope_and_unavailable_evidence_stay_fail_closed(self):
        message='My insurance is through my current job.'
        base=self.extraction([self.update('T05',{'choice':'employer'},message)])
        cases=[({key:value for key,value in base.items() if key!='goal_quote'},'invalid_structure'),
               ({**base,'mode':'report'},'invalid_structure'),
               ({**base,'requests':{}},'unsupported_action'),
               ({**base,'requests':[{'id':'timing','quote':7}]},'unsupported_action'),
               ({**base,'fact_ids':['unavailable_source']},'source_reference')]
        for answer,expected in cases:
            with self.subTest(expected=expected):
                self.answer=answer
                with self.assertLogs('natural_agent',level='WARNING') as captured:
                    with self.agent.reserve_turn() as reservation:
                        with self.assertRaises(ModelUnavailable):
                            self.agent.extract('private-owner',message,self.g,{},str(uuid.uuid4()),reservation)
                self.assertEqual(captured.output,['WARNING:natural_agent:Daylight extraction unavailable code='+expected])
                self.assertNotIn(message,' '.join(captured.output))
                self.assertNotIn('private-owner',' '.join(captured.output))

    def test_unsupported_date_is_rejected(self):
        self.answer = self.composition(reply='Your birthday is in December.', report_refs=['guide.situation.age65'])
        with self.assertRaises(ModelUnavailable): self.compose()

    def test_superseded_change_receipt_allows_legitimate_birthday_correction_contrast(self):
        self.context['reports'][0]['value']={'month':12,'year':None}
        self.context['resolved_changes']=[{'report_id':'guide.situation.age65',
            'previous_value':{'month':11,'year':None},'current_value':{'month':12,'year':None},
            'status':'superseded'}]
        self.answer=self.composition(reply='December, rather than November.',
                                     report_refs=['guide.situation.age65'])
        out=self.compose()
        self.assertEqual(out['reply'],self.answer['reply'])
        sent=json.loads(self.calls[-1]['input'][0]['content'])['resolved_context']
        self.assertEqual(len(sent['reports']),1)
        self.assertEqual(sent['reports'][0]['value'],{'month':12,'year':None})

    def test_raw_current_message_cannot_create_a_change_receipt_or_ground_an_amount(self):
        self.context['reports'][0]['value']={'month':12,'year':None}
        self.context['current_message']='Actually December, not November. My premium is $20.'
        self.context['resolved_changes']=[{'report_id':'guide.situation.age65',
            'previous_value':{'month':11,'year':None},'current_value':{'month':12,'year':None},
            'status':'superseded'}]
        self.answer=self.composition(reply='Your premium is $20.')
        with self.assertRaises(ModelUnavailable):self.compose()

    def test_modal_may_is_not_an_unsupported_month(self):
        for reply in ['That may help us focus on the next step.',
                      'Your choices may affect what we look at next.',
                      'The order may depend on your priorities.',
                      'You may not need every detail at once.',
                      'That may also help us focus.',
                      'This may still need a closer look.']:
            with self.subTest(reply=reply):
                self.answer = self.composition(reply=reply)
                self.assertEqual(self.compose()['reply'], self.answer['reply'])

    def test_polite_may_question_is_not_an_unsupported_month(self):
        for subject in ['I', 'we']:
            with self.subTest(subject=subject):
                self.answer = self.composition(question=f'May {subject} ask how far you have got with Medicare so far?')
                self.assertEqual(self.compose()['question'], self.answer['question'])

    def test_actual_may_dates_remain_grounded_case_insensitively(self):
        self.context['reports'][0]['value']['year'] = 2027
        for phrase in ['May 2027', 'may 2027', 'in May', 'in may',
                       'start in May', 'start in may', 'May', 'may',
                       'birthday May', 'birthday may', 'in May be ready',
                       'in may be ready', 'your May start date',
                       'your may start date', 'a May start', 'a may start']:
            with self.subTest(phrase=phrase):
                self.answer = self.composition(reply=f'We can use {phrase} as the next step.')
                with self.assertRaisesRegex(ModelUnavailable, 'date or amount'):
                    self.compose()

    def test_resolved_may_month_can_still_be_used_as_a_date(self):
        self.context['reports'] = [{'id': 'guide.situation.age65', 'value': {'month': 5, 'year': None}, 'status': 'reported'}]
        self.answer = self.composition(reply='With your May birthday coming up, we can focus on the next step.', report_refs=['guide.situation.age65'])
        self.assertEqual(self.compose()['reply'], self.answer['reply'])

    def test_resolved_numeric_birthday_month_can_use_display_name(self):
        self.answer = self.composition(reply='With your November birthday coming up, we can start with the steps that matter to you.', report_refs=['guide.situation.age65'])
        self.assertEqual(self.compose()['reply'], self.answer['reply'])
        self.assertIsNone(self.agent.local.last_composition_error)

    def test_normalized_resolved_date_can_use_month_name(self):
        self.context['reports'] = [{'id': 'readiness.RC11.profile.coverageEnd', 'value': '2027-04', 'status': 'reported'}]
        self.answer = self.composition(reply='With coverage ending in April, we can keep that date separate from when the job ends.', report_refs=['readiness.RC11.profile.coverageEnd'])
        self.assertEqual(self.compose()['reply'], self.answer['reply'])

    def test_unaccepted_message_month_cannot_ground_generated_date(self):
        self.context['reports'] = []
        self.context['current_message'] = 'I think my birthday might be in November.'
        self.answer = self.composition(reply='We can start with your November birthday.')
        with self.assertRaises(ModelUnavailable):self.compose()
        self.assertEqual(self.agent.local.last_composition_error, 'ungrounded_literal')

    def test_unknown_or_conflicting_dates_do_not_get_display_aliases(self):
        for status in ['unknown', 'tentative', 'conflicting', 'stale']:
            self.context['reports'] = [{'id': 'guide.situation.age65', 'value': {'month': 11, 'year': None}, 'status': status}]
            self.answer = self.composition(reply='We can start with your November birthday.', report_refs=['guide.situation.age65'])
            with self.assertRaises(ModelUnavailable):self.compose()

    def test_public_medicare_part_grammar_is_not_a_new_named_entity(self):
        self.moves = [{'id': 'RC04', 'question': {'id': 'RC04', 'question': 'Which Medicare parts do you have now?'}, 'purpose': 'Actual A/B status'}]
        self.answer = self.composition(question_target='RC04', question='Have you already enrolled in Medicare Part A or Part B?')
        self.assertEqual(self.compose()['question'], self.answer['question'])

    def test_question_meaning_failure_recovers_canonical_wording(self):
        self.moves = [{'id': 'T04', 'question': {'id': 'T04', 'question': 'When would you like Medicare coverage to start?'}, 'purpose': 'Desired start'}]
        self.answer = self.composition(question_target='T04', question='When did Part B start?')
        out = self.compose()
        self.assertEqual(out['question'], self.moves[0]['question']['question'])

    def test_actual_parts_question_cannot_become_generic_sign_up_progress(self):
        self.moves = [{'id': 'RC04', 'question': {'id': 'RC04', 'question': 'Which Medicare parts do you have now?'}, 'purpose': 'Actual A/B enrollment'}]
        self.answer = self.composition(question_target='RC04', question='Have you signed up for Medicare yet?')
        self.assertEqual(self.compose()['question'], self.moves[0]['question']['question'])
        self.answer = self.composition(question_target='RC04', question='Have you enrolled in Part A or Part B yet?')
        self.assertEqual(self.compose()['question'], self.answer['question'])

    def test_spouse_short_reply_inherits_only_explicit_whose_job_question(self):
        active = {'id': 'RC09', 'question': 'Whose job is this health insurance through?'}
        self.assertTrue(supported_choice('RC09', 'spouse_job', 'Through my wife.', active))
        self.assertTrue(supported_choice('T05', 'employer', 'Through my wife.', active))
        broad = {'id': 'T05', 'question': 'What health insurance do you have now?'}
        self.assertFalse(supported_choice('RC09', 'spouse_job', 'Through my wife.', broad))
        self.assertFalse(supported_choice('T05', 'employer', 'Through my wife.', broad))
        self.assertFalse(supported_choice('RC09', 'spouse_job', 'Through my wife. She is retired.', active))

    def test_contextual_spouse_answer_passes_extractor_not_broad_insurance_question(self):
        text = 'Through my wife.'
        updates = [self.update('RC09', {'choice': 'spouse_job'}, text)]
        for current, expected in [({'id': 'RC09', 'question': 'Whose job is this health insurance through?', 'fields': [], 'entity': 'profile'}, ['RC09']),
                                  ({'id': 'T05', 'question': 'What health insurance do you have now?', 'fields': [], 'entity': 'profile'}, [])]:
            self.answer = self.extraction(updates)
            with self.agent.reserve_turn() as reservation:
                out = self.agent.extract('owner', text, self.g, {'activeQuestion': current}, str(uuid.uuid4()), reservation)
            self.assertEqual([item['id'] for item in out['updates']], expected)
            sent = json.loads(self.calls[-1]['input'][0]['content'])['confirmed_context']['activeQuestion']
            self.assertEqual(sent['question'], current['question'])

    def test_application_progress_does_not_become_knowledge_or_actual_enrollment(self):
        message = "I'm just getting started. I haven't applied for Medicare yet. My health insurance is through my wife's current job."
        self.answer = self.extraction([
            self.update('T02', {'choice': 'new'}, "I'm just getting started.", subject='learner'),
            self.update('RC04', {'choice': 'neither'}, "I haven't applied for Medicare yet."),
            self.update('T05', {'choice': 'employer'}, "My health insurance is through my wife's current job."),
            self.update('RC09', {'choice': 'spouse_job'}, "My health insurance is through my wife's current job.")])
        with self.agent.reserve_turn() as reservation:
            out = self.agent.extract('owner', message, self.g, {'activeQuestion': {'id': 'orientation', 'fields': []}}, str(uuid.uuid4()), reservation)
        self.assertEqual([item['id'] for item in out['updates']], ['T05', 'RC09'])
        self.assertEqual({item['id'] for item in out['rejected_updates']}, {'T02', 'RC04'})

    def test_actual_ab_choices_require_their_specific_meaning(self):
        self.assertFalse(supported_choice('RC04', 'neither', "I haven't applied for Medicare yet."))
        self.assertFalse(supported_choice('RC04', 'pending', "I haven't applied for Medicare yet."))
        self.assertFalse(supported_choice('RC04', 'both', 'I have applied for Parts A and B.'))
        self.assertTrue(supported_choice('RC04', 'pending', 'I applied for Parts A and B and am waiting.'))
        self.assertTrue(supported_choice('RC04', 'both', 'I have Parts A and B.'))
        self.assertTrue(supported_choice('RC04', 'neither', 'I do not have Medicare.'))
        self.assertTrue(supported_choice('RC04', 'a_only', 'I only have Part A.'))
        self.assertFalse(supported_choice('RC04', 'neither', 'I am just getting started.'))

    def test_process_is_not_familiarity_but_explicit_knowledge_is(self):
        self.assertFalse(supported_choice('T02', 'new', "I'm just getting started."))
        self.assertTrue(supported_choice('T02', 'new', 'I do not understand Medicare.'))
        self.assertTrue(supported_choice('T02', 'new', 'New.', {'id': 'T02'}))

    def test_composer_cannot_repeat_uncommitted_insurance_or_application(self):
        self.answer = self.composition(reply="Since you are covered through your wife's current job, we can focus on that coverage.")
        with self.assertRaises(ModelUnavailable): self.compose()
        self.assertIn(self.agent.local.last_composition_error, {'missing_report_reference', 'missing_coverage_reference'})
        self.answer = self.composition(reply="Since you haven't applied yet, we can work through what comes next.")
        with self.assertRaises(ModelUnavailable): self.compose()
        self.assertEqual(self.agent.local.last_composition_error, 'missing_progress_reference')

    def test_spouse_worker_statement_needs_relationship_not_just_broad_insurance(self):
        self.context['reports'] = [{'id': 'guide.coverage.current', 'value': ['employer'], 'status': 'reported'}]
        self.answer = self.composition(reply="Your insurance through your wife's current job gives us a starting point.", report_refs=['guide.coverage.current'])
        with self.assertRaises(ModelUnavailable): self.compose()
        self.assertEqual(self.agent.local.last_composition_error, 'missing_worker_reference')
        self.context['reports'].append({'id': 'readiness.RC09.profile.choice', 'value': 'spouse_job', 'status': 'reported'})
        self.answer['report_refs'].append('readiness.RC09.profile.choice')
        self.assertEqual(self.compose()['reply'], self.answer['reply'])

    def test_atomic_reservation_and_unused_composition_release(self):
        budget = self.ledger()
        self.agent.budget = budget
        self.answer = self.extraction([])
        with self.agent.reserve_turn() as reservation:
            self.assertEqual(len(reservation.stages), 2)
            self.agent.extract('owner', 'I am retired.', self.g, {}, str(uuid.uuid4()), reservation)
        with budget.db() as db:
            rows = db.execute('SELECT status,charged,input_bound,output_bound FROM ai_charges ORDER BY status').fetchall()
        self.assertEqual([row[0] for row in rows], ['cancelled', 'settled'])
        self.assertEqual(rows[0][1], 0)
        self.assertEqual(rows[1][1], 300*2500 + 70*15000)
        self.assertEqual([row[2:] for row in rows], [(0, 900), (300, 900)])

    def test_both_stages_settle_without_extra_reservations(self):
        budget = self.ledger()
        self.agent.budget = budget
        with self.agent.reserve_turn() as reservation:
            self.answer = self.extraction([])
            self.agent.extract('owner', 'I am retired.', self.g, {}, str(uuid.uuid4()), reservation)
            self.answer = self.composition()
            self.agent.compose('owner', self.context, self.moves, str(uuid.uuid4()), reservation)
        with budget.db() as db:
            rows = db.execute('SELECT status,charged FROM ai_charges').fetchall()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row == ('settled', 300*2500 + 70*15000) for row in rows))
        self.assertEqual(len(self.calls), 2)

    def test_insufficient_group_allowance_starts_no_stage(self):
        budget = self.ledger()
        budget.seed([('historic', '2026-10-30', 392000, 0, 0)])
        self.agent.budget = budget
        with self.assertRaises(BudgetError): self.agent.reserve_turn()
        self.assertEqual(self.calls, [])
        with budget.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_charges').fetchone()[0], 1)

    def test_unissued_preflight_failure_releases_both_stages(self):
        budget = self.ledger()
        self.agent.budget = budget
        self.agent.count_tokens = lambda *_: 1_000_000
        self.answer = self.extraction([])
        with self.assertRaises(BudgetError):
            with self.agent.reserve_turn() as reservation:
                self.agent.extract('owner', 'I am retired.', self.g, {}, str(uuid.uuid4()), reservation)
        with budget.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ai_charges WHERE status='cancelled' AND charged=0").fetchone()[0], 2)
        self.assertEqual(self.calls, [])

    def test_transport_failure_stays_uncertain_no_retry(self):
        budget = self.ledger()
        self.agent.budget = budget
        self.failure = TimeoutError('fictional transport interruption')
        with self.assertRaises(ModelUnavailable):
            with self.agent.reserve_turn() as reservation:
                self.agent.extract('owner', 'I am retired.', self.g, {}, str(uuid.uuid4()), reservation)
        with budget.db() as db:
            self.assertEqual(sorted(row[0] for row in db.execute('SELECT status FROM ai_charges')), ['cancelled', 'uncertain'])
        self.assertEqual(len(self.calls), 1)

    def test_tls_extraction_failure_is_safe_and_keeps_issued_charge_uncertain(self):
        budget = self.ledger()
        self.agent.budget = budget
        before = copy.deepcopy(self.g)
        self.failure = SSLError('private TLS failure canary')
        with self.assertLogs('natural_agent', level='WARNING') as logs:
            with self.assertRaises(ModelUnavailable) as caught:
                with self.agent.reserve_turn() as reservation:
                    self.agent.extract('owner', 'I am retired.', self.g, {},
                                       str(uuid.uuid4()), reservation)
        self.assertEqual(self.agent.local.last_extraction_error, 'transport_or_format')
        self.assertNotIn('private TLS failure canary', str(caught.exception))
        self.assertNotIn('private TLS failure canary', '\n'.join(logs.output))
        self.assertEqual(self.g, before)
        with budget.db() as db:
            self.assertEqual(sorted(row[0] for row in db.execute('SELECT status FROM ai_charges')),
                             ['cancelled', 'uncertain'])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.agent.cache, {})

    def test_extraction_http_rejection_is_distinct_from_a_disconnected_reply(self):
        self.agent.budget = self.ledger()
        self.failure = HTTPError('https://example.test/', 400, 'private error', None,
            io.BytesIO(b'{"error":{"type":"invalid_request_error","message":"PRIVATE-BODY"}}'))
        self.addCleanup(self.failure.close)
        with self.assertLogs('natural_agent', level='WARNING') as logs:
            with self.assertRaisesRegex(ModelUnavailable, 'provider declined'):
                with self.agent.reserve_turn() as reservation:
                    self.agent.extract('owner', 'A fictional report.', self.g, {},
                                       str(uuid.uuid4()), reservation)
        recorded = '\n'.join(logs.output)
        self.assertIn('"http_status": 400', recorded)
        self.assertIn('"provider_code": "invalid_request_error"', recorded)
        self.assertNotIn('PRIVATE-BODY', recorded)
        self.assertEqual(len(self.calls), 1)

    def test_tls_composition_failure_preserves_settled_extraction_without_retry(self):
        budget = self.ledger()
        self.agent.budget = budget
        context_before = copy.deepcopy(self.context)
        with self.agent.reserve_turn() as reservation:
            self.answer = self.extraction([])
            self.agent.extract('owner', 'I am retired.', self.g, {}, str(uuid.uuid4()), reservation)
            self.failure = SSLError('private TLS failure canary')
            with self.assertRaises(ModelUnavailable) as caught:
                self.agent.compose('owner', self.context, self.moves, str(uuid.uuid4()), reservation)
        self.assertEqual(self.agent.local.last_composition_error, 'transport_or_format')
        self.assertNotIn('private TLS failure canary', str(caught.exception))
        self.assertEqual(self.context, context_before)
        with budget.db() as db:
            self.assertEqual(sorted(row[0] for row in db.execute('SELECT status FROM ai_charges')),
                             ['settled', 'uncertain'])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.agent.usage), 1)
        self.assertTrue(all(not key[1].startswith('compose:') for key in self.agent.cache))

    def test_connection_reset_is_normalized_at_both_stage_boundaries(self):
        for stage in ('extract', 'compose'):
            with self.subTest(stage=stage):
                self.failure = ConnectionResetError('fictional network reset')
                before = len(self.calls)
                with self.assertRaises(ModelUnavailable):
                    with self.agent.reserve_turn() as reservation:
                        if stage == 'extract':
                            self.agent.extract('owner', 'I am retired.', self.g, {},
                                               str(uuid.uuid4()), reservation)
                        else:
                            self.agent.compose('owner', self.context, self.moves,
                                               str(uuid.uuid4()), reservation)
                self.assertEqual(len(self.calls), before + 1)
                code = getattr(self.agent.local, 'last_extraction_error' if stage == 'extract'
                               else 'last_composition_error')
                self.assertEqual(code, 'transport_or_format')

    @staticmethod
    def streamed_answer(answer):
        events = [{'type':'response.output_text.delta','delta':json.dumps(answer)},
            {'type':'response.completed','response':{
                'status':'completed','model':'gpt-5.4','service_tier':'default',
                'usage':{'input_tokens':300,'output_tokens':70,'total_tokens':370,
                         'input_tokens_details':{'cached_tokens':0}}}}]
        return io.BytesIO(b''.join(b'data: '+json.dumps(event).encode()+b'\n' for event in events))

    def test_both_stages_send_counted_history_packing_bytes_without_mutating_memory(self):
        history = [{'user':f'User turn {index}', 'assistant':f'Assistant turn {index}'}
                   for index in range(6)]
        for stage in ('extract','compose'):
            with self.subTest(stage=stage):
                self.agent.budget = self.ledger()
                self.agent.client.transport = None
                context = {**copy.deepcopy(self.context), 'recent_exchanges':copy.deepcopy(history)}
                before = copy.deepcopy(context)
                counted = []
                def counter(_, payload):
                    counted.append(copy.deepcopy(payload))
                    content = json.loads(payload['input'][0]['content'])
                    current = content['confirmed_context' if stage == 'extract' else 'resolved_context']
                    return 16000 + 600*len(current['recent_exchanges'])
                self.agent.count_tokens = counter
                answer = self.extraction([]) if stage == 'extract' else self.composition()
                requests = []
                def open_stream(request, **_):
                    requests.append(request)
                    return self.streamed_answer(answer)
                target = 'narrative_agent.urlopen' if stage == 'extract' else 'natural_agent.urlopen'
                before_calls = self.agent.calls
                with patch(target, open_stream):
                    with self.agent.reserve_turn() as reservation:
                        if stage == 'extract':
                            self.agent.extract('owner','I am retired.',self.g,context,
                                               str(uuid.uuid4()),reservation)
                        else:
                            self.agent.compose('owner',context,self.moves,
                                               str(uuid.uuid4()),reservation)
                self.assertEqual(len(requests),1,'Packing counts never regenerate a model response.')
                self.assertEqual(self.agent.calls,before_calls+1)
                self.assertEqual(len(counted),1)
                key = 'confirmed_context' if stage == 'extract' else 'resolved_context'
                actual = json.loads(json.loads(requests[0].data)['input'][0]['content'])
                expected = json.loads(counted[0]['input'][0]['content'])
                self.assertEqual(actual,expected,'The real HTTP bytes must match the packed token count.')
                self.assertEqual(context,before,'Packing must never trim server visit memory.')
                self.assertEqual([len(json.loads(item['input'][0]['content'])[key]['recent_exchanges'])
                                  for item in counted],[6])

    def test_history_is_retained_above_the_former_input_ceiling(self):
        history = [{'user':str(index),'assistant':str(index)} for index in range(6)]
        content = {'resolved_context':{'recent_exchanges':history,'reports':[{'id':'keep'}],
                    'education_context':{'learning':{'focus':['coverage_paths']}}},
                   'question_candidates':[{'id':'T05'}]}
        payload = {'input':[{'role':'user','content':json.dumps(content)}]}
        counts = []
        def counter(_, item):
            state = json.loads(item['input'][0]['content'])
            counts.append(len(state['resolved_context']['recent_exchanges']))
            return 16000 + 300*counts[-1]
        self.agent.count_tokens = counter
        count = self.agent.count_request_tokens(self.agent.client,payload)
        self.assertEqual(count,17800)
        self.assertEqual(counts,[6])
        actual = json.loads(payload['input'][0]['content'])
        self.assertEqual(actual['resolved_context']['recent_exchanges'],history)
        self.assertEqual(actual['resolved_context']['reports'],content['resolved_context']['reports'])
        self.assertEqual(actual['resolved_context']['education_context'],
                         content['resolved_context']['education_context'])
        self.assertEqual(actual['question_candidates'],content['question_candidates'])

    def test_whole_chat_over_the_byte_bound_drops_only_the_oldest_exchanges(self):
        """D155: an extraction request past max_input_bytes keeps the newest exchanges and reports the drop."""
        history = [{'user': 'u%02d ' % index + 'x' * 1000, 'assistant': 'a' * 1000} for index in range(40)]
        content = {'confirmed_context': {'recent_exchanges': history, 'reports': [{'id': 'keep'}]}}
        payload = {'input': [{'role': 'user', 'content': json.dumps(content)}]}
        self.agent.max_input_bytes = 30_000
        self.agent.count_tokens = lambda _, value: 1000
        self.agent.count_request_tokens(self.agent.client, payload)
        self.assertLessEqual(len(json.dumps(payload).encode()), 30_000)
        kept = json.loads(payload['input'][0]['content'])['confirmed_context']['recent_exchanges']
        self.assertGreater(len(kept), 5)
        self.assertEqual(kept[-1], history[-1])
        self.assertEqual(kept, history[-len(kept):])
        self.assertEqual(self.agent.local.request_sizes['history_exchanges_dropped'], 40 - len(kept))

    def test_input_that_already_fits_keeps_every_exchange_with_one_count(self):
        content = {'resolved_context':{'recent_exchanges':[{'user':'old','assistant':'old'},
                                                         {'user':'new','assistant':'new'}]}}
        payload = {'input':[{'role':'user','content':json.dumps(content)}]}
        before = copy.deepcopy(payload)
        counts = []
        self.agent.count_tokens = lambda _, value: counts.append(copy.deepcopy(value)) or 7999
        self.assertEqual(self.agent.count_request_tokens(self.agent.client,payload),7999)
        self.assertEqual(json.loads(payload['input'][0]['content']),
                         json.loads(before['input'][0]['content']))
        self.assertEqual(payload['input'][0]['content'],
                         json.dumps(content,ensure_ascii=False,separators=(',',':')))
        self.assertEqual(len(counts),1)

    def test_lossless_json_compaction_precedes_counting(self):
        context = {'current_message':'My name has spaces. Please keep them.',
            'recent_exchanges':[{'user':'A complete sentence.', 'assistant':'Another complete sentence.'}],
            'reports':[{'id':'keep','value':{'month':11,'year':None}}],
            'education_context':{'learning':{'focus':['coverage_paths']}}}
        content = {'resolved_context':context,'question_candidates':[{'id':'T05'}]}
        payload = {'input':[{'role':'user','content':json.dumps(content,indent=2)}]}
        before = copy.deepcopy(content)
        counted = []
        def counter(_, item):
            text = item['input'][0]['content']
            counted.append(text)
            return 7999 if text == json.dumps(content,ensure_ascii=False,separators=(',',':')) else 9001
        self.agent.count_tokens = counter
        self.assertEqual(self.agent.count_request_tokens(self.agent.client,payload),7999)
        self.assertEqual(len(counted),1)
        self.assertEqual(json.loads(payload['input'][0]['content']),before)
        self.assertEqual(content,before)

    def test_input_exceeding_daily_budget_stays_unissued_without_removing_history(self):
        budget = self.ledger()
        self.agent.budget = budget
        context = {'recent_exchanges':[{'user':str(index),'assistant':str(index)} for index in range(6)]}
        before = copy.deepcopy(context)
        counts = []
        self.agent.count_tokens = lambda _, value: counts.append(copy.deepcopy(value)) or 1_000_000
        self.answer = self.extraction([])
        with self.assertRaises(BudgetError):
            with self.agent.reserve_turn() as reservation:
                self.agent.extract('owner','I am retired.',self.g,context,str(uuid.uuid4()),reservation)
        self.assertEqual(len(counts),1)
        self.assertEqual(context,before)
        self.assertEqual(self.calls,[])
        self.assertEqual(self.agent.calls,0)
        with budget.db() as db:
            self.assertEqual(sorted(row[0] for row in db.execute('SELECT status FROM ai_charges')),
                             ['cancelled','cancelled'])

    def test_composition_cache_binds_resolved_revision(self):
        self.answer = self.composition()
        request_id = str(uuid.uuid4())
        with self.agent.reserve_turn() as reservation:
            first = self.agent.compose('owner', self.context, self.moves, request_id, reservation)
            second = self.agent.compose('owner', self.context, self.moves, request_id, reservation)
            self.assertEqual(first, second)
        self.assertEqual(len(self.calls), 1)

    def test_provider_incomplete_diagnostic_is_value_free(self):
        response = {'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'},
                    'usage': {'input_tokens': 6000, 'output_tokens': 900, 'total_tokens': 6900,
                              'output_tokens_details': {'reasoning_tokens': 0, 'private': 'private canary'}},
                    'output': [{'content': [{'type': 'output_text', 'text': 'Private generated canary'}]}],
                    'error': {'message': 'Private provider canary'}}
        self.agent.client.transport = lambda _: response
        with self.assertRaises(ModelUnavailable):self.compose()
        diagnostic = self.agent.local.provider_failure
        self.assertEqual(diagnostic['event'], 'response.incomplete')
        self.assertEqual(diagnostic['incomplete_reason'], 'max_output_tokens')
        self.assertEqual(diagnostic['usage']['output_tokens'], 900)
        self.assertNotIn('canary', json.dumps(diagnostic).lower())
        self.assertEqual(set(diagnostic), {'event', 'incomplete_reason', 'provider_code', 'usage'})

    def test_streamed_provider_failure_retains_no_output_text(self):
        self.agent.client.transport = None
        event = {'type': 'response.failed', 'response': {'status': 'failed', 'output': ['Private generated canary'],
                 'error': {'message': 'Private provider canary'}, 'usage': {'input_tokens': 400, 'output_tokens': 12, 'total_tokens': 412}}}
        stream = io.BytesIO(('data: '+json.dumps(event)+'\n').encode())
        with patch('natural_agent.urlopen', return_value=stream):
            with self.assertRaises(ModelUnavailable):self.agent._complete({}, b'{}')
        self.assertEqual(self.agent.local.provider_failure['event'], 'response.failed')
        self.assertEqual(self.agent.local.provider_failure['usage']['output_tokens'], 12)
        self.assertNotIn('canary', json.dumps(self.agent.local.provider_failure).lower())

    def test_provider_reason_and_usage_are_strictly_filtered(self):
        result = provider_failure_diagnostic({'type': 'error', 'response': {
            'incomplete_details': {'reason': 'Private error with arbitrary prose'},
            'usage': {'input_tokens': -1, 'output_tokens': True, 'total_tokens': 'private',
                      'input_tokens_details': {'cached_tokens': 20, 'other': 'private'}}}})
        self.assertEqual(result, {'event': 'error', 'incomplete_reason': 'unknown', 'provider_code': 'unknown', 'usage': {'input_tokens_details': {'cached_tokens': 20}}})

    def test_nested_provider_code_is_bounded_without_error_message(self):
        result = provider_failure_diagnostic({'type': 'error', 'error': {'code': 'credit_balance_exhausted',
                    'type': 'insufficient_quota', 'message': 'Private provider error canary'}})
        self.assertEqual(result['provider_code'], 'credit_balance_exhausted')
        self.assertNotIn('canary', json.dumps(result))
        invalid = provider_failure_diagnostic({'type': 'error', 'error': {'code': 'Private provider canary'}})
        self.assertEqual(invalid['provider_code'], 'unknown')

    def test_quota_failure_is_readable_for_extraction_and_retains_hold(self):
        budget = self.ledger()
        self.agent.budget = budget
        self.agent.client.transport = lambda _: {'status': 'failed', 'error': {'code': 'credit_balance_exhausted', 'message': 'Private canary'}}
        with self.assertRaisesRegex(ModelUnavailable, 'AI provider has no credits remaining'):
            with self.agent.reserve_turn() as reservation:
                self.agent.extract('owner', 'I am retired.', self.g, {}, str(uuid.uuid4()), reservation)
        self.assertEqual(self.agent.local.provider_failure['provider_code'], 'credit_balance_exhausted')
        with budget.db() as db:
            rows = db.execute('SELECT status,charged FROM ai_charges').fetchall()
        self.assertEqual(sorted(row[0] for row in rows), ['cancelled', 'uncertain'])
        self.assertEqual(sum(row[1] for row in rows), 300*2500 + 900*15000)

    def test_streamed_quota_failure_preserves_accepted_details_message(self):
        self.agent.client.transport = None
        event = {'type': 'error', 'error': {'code': 'credit_balance_exhausted', 'type': 'insufficient_quota', 'message': 'Private canary'}}
        stream = io.BytesIO(('data: '+json.dumps(event)+'\n').encode())
        with patch('natural_agent.urlopen', return_value=stream):
            with self.assertRaisesRegex(ModelUnavailable, 'accepted details are preserved') as error:
                self.agent._complete({}, b'{}')
        self.assertIn('AI provider has no credits remaining', str(error.exception))
        self.assertNotIn('canary', str(error.exception))


class CarrierAliasTests(unittest.TestCase):
    """R2: "UHC" on screen may be written "UnitedHealthcare"; other insurers stay ungrounded."""
    setUp = NaturalAgentTests.setUp
    extraction = NaturalAgentTests.extraction
    empty_agenda = NaturalAgentTests.empty_agenda
    update = NaturalAgentTests.update
    composition = NaturalAgentTests.composition
    compose = NaturalAgentTests.compose
    ledger = NaturalAgentTests.ledger

    def test_expanded_insurer_of_an_on_screen_plan_is_grounded(self):
        self.context['reports'] = []
        self.context['evidence'] = list(self.context.get('evidence', [])) + [
            {'id': 'plan:H0001-006', 'title': 'Plan', 'text': 'AARP Medicare Advantage from UHC FL-0006 (H0001-006) plan type: HMO-POS.',
             'summary': 'AARP Medicare Advantage from UHC FL-0006 (H0001-006) plan type: HMO-POS.'}]
        self.answer = self.composition(reply='These are UnitedHealthcare plans; the screen shows each one’s published terms.')
        self.assertEqual(self.compose()['reply'], self.answer['reply'])

    def test_an_insurer_not_on_screen_is_still_ungrounded(self):
        self.context['reports'] = []
        self.answer = self.composition(reply='Humana Gold Plus covers this differently.')
        with self.assertRaises(ModelUnavailable): self.compose()


if __name__ == '__main__':
    unittest.main()


class RedirectContractNov9Tests(unittest.TestCase):
    """Owner intent, every turn ends with a question (live run P05–P09, Nov 9, 2026)."""
    setUp = NaturalAgentTests.setUp
    extraction = NaturalAgentTests.extraction
    empty_agenda = NaturalAgentTests.empty_agenda
    update = NaturalAgentTests.update
    composition = NaturalAgentTests.composition
    compose = NaturalAgentTests.compose
    ledger = NaturalAgentTests.ledger

    def test_brevity_demand_is_not_a_pause_and_the_open_question_is_restored(self):
        self.moves = [{'id': 'T06', 'question': {'id': 'T06', 'question': 'Are there doctors or hospitals you’d like to keep?',
                       'choices': [['none', 'No doctors to include']]}, 'purpose': 'x', 'priority': 1}]
        self.context['required_target'] = {'id': 'T06', 'reason': 'current_decision', 'question': 'Are there doctors or hospitals you’d like to keep?'}
        self.context['require_followup'] = True
        self.context['pause_allowed'] = False
        self.answer = self.composition(question_target=None, reply='No.', question='', agenda_update={'current_concern': 'COBRA bill', 'pause': True})
        out = self.compose()
        self.assertEqual(out['reply'], 'No.')
        self.assertEqual(out['question_target'], 'T06')
        self.assertEqual(out['question'], 'Are there doctors or hospitals you’d like to keep?')
        self.assertFalse(out['agenda_update']['pause'])

    def test_person_requested_pause_still_ends_without_a_question(self):
        self.context['require_followup'] = True
        self.context['pause_allowed'] = True
        self.answer = self.composition(question_target=None, reply='Of course. We can pick this up whenever you like.', question='',
                                       agenda_update={'current_concern': '', 'pause': True})
        out = self.compose()
        self.assertEqual(out['question'], '')
        self.assertTrue(out['agenda_update']['pause'])

    def test_missing_followup_keeps_the_answer_and_adds_the_continuation_question(self):
        self.moves = []
        self.context['require_followup'] = True
        self.context['pause_allowed'] = False
        self.answer = self.composition(question_target=None, reply='We can take the next piece at your pace.', question='')
        out = self.compose()
        self.assertEqual(out['reply'], self.answer['reply'])
        self.assertEqual(out['question'], 'What would you like to understand next?')
        self.assertIsNone(out['question_target'])
        self.assertEqual(out['validation_recovery']['reason'], 'missing_followup')

    def test_dependent_spouse_coverage_is_not_a_spouse_job_claim(self):
        self.context['reports'] = [{'id': 'guide.coverage.current', 'value': ['retiree'], 'status': 'reported'}]
        self.answer = self.composition(reply="Joining an outside drug plan could end the retiree package, including your husband's coverage.",
                                       report_refs=['guide.coverage.current'])
        self.assertEqual(self.compose()['reply'], self.answer['reply'])
        self.context['reports'] = [{'id': 'guide.coverage.current', 'value': ['employer'], 'status': 'reported'}]
        self.answer = self.composition(reply="Your insurance through your husband's job gives us a starting point.", report_refs=['guide.coverage.current'])
        with self.assertRaises(ModelUnavailable): self.compose()
        self.assertEqual(self.agent.local.last_composition_error, 'missing_worker_reference')

    def test_resolved_rule_months_ground_the_reply(self):
        self.context['applicable_rules'] = [{'rule_id': 'ma_trial_right', 'fact_id': 'ma_trial_right', 'status': 'not_met',
            'applies_because': ['RC16: first Advantage plan started March 2021; 12-month window ended March 2022'],
            'confirm_with': [], 'how_to_use': '', 'statement': 'x'}]
        self.context['reports'].append({'id': 'readiness.RC16.profile.choice', 'value': 'yes', 'status': 'reported'})
        self.answer = self.composition(reply='On the start you reported, March 2021, the 12-month trial right would have ended around March 2022.',
                                       report_refs=['readiness.RC16.profile.choice'])
        self.assertEqual(self.compose()['reply'], self.answer['reply'])


class OwnWordsGroundingTests(unittest.TestCase):
    """Echoing the amounts and names the person just typed is reporting, not invention (P11, Nov 9, 2026)."""
    setUp = NaturalAgentTests.setUp
    extraction = NaturalAgentTests.extraction
    empty_agenda = NaturalAgentTests.empty_agenda
    update = NaturalAgentTests.update
    composition = NaturalAgentTests.composition
    compose = NaturalAgentTests.compose
    ledger = NaturalAgentTests.ledger

    def test_amounts_and_names_from_the_current_message_are_grounded(self):
        self.context['reports'] = []
        self.context['current_message'] = 'Reedglass Pharmacy quoted $510 for 60 apixaban tablets and Dr. Tavin Rookmere prescribed it.'
        self.answer = self.composition(reply='A $510 quote for 60 tablets from Reedglass Pharmacy is the kind of cost a drug plan is meant to change; Dr. Tavin Rookmere’s prescription itself does not decide coverage.')
        self.assertEqual(self.compose()['reply'], self.answer['reply'])

    def test_bare_months_from_the_current_message_still_need_an_accepted_report(self):
        self.context['reports'] = []
        self.context['current_message'] = 'I think it was sometime in February, and I paid $510 last week.'
        self.answer = self.composition(reply='Since February you have paid $510 a month.')
        with self.assertRaises(ModelUnavailable): self.compose()
        self.assertEqual(self.agent.local.last_composition_error, 'ungrounded_literal')

    def test_specific_dates_the_person_typed_may_be_echoed(self):
        self.context['reports'] = []
        self.context['current_message'] = 'Plan N started February 1, 2021. I bought seven days on November 5, so I need more November 12.'
        self.answer = self.composition(reply='You said Plan N started February 1, 2021 and the next refill is needed November 12; a 7-day supply is what you bought.')
        self.assertEqual(self.compose()['reply'], self.answer['reply'])


class ContextFitTests(unittest.TestCase):
    """A bounded composition context is compacted, never refused (P12/P16/P17, Nov 9, 2026)."""
    setUp = NaturalAgentTests.setUp
    extraction = NaturalAgentTests.extraction
    empty_agenda = NaturalAgentTests.empty_agenda
    update = NaturalAgentTests.update
    composition = NaturalAgentTests.composition
    compose = NaturalAgentTests.compose
    ledger = NaturalAgentTests.ledger

    def big_context(self):
        plans = [{'id': f'H1045-0{n}', 'name': f'Plan {n}', 'type': 'HMO-POS', 'identity_state': 'listed',
                  'fields': {f'f{i}': {'label': 'Label ' + 'x' * 40, 'state': 'reference', 'value': '$%d' % i,
                                       'conditions': ['condition ' + 'y' * 120] * 3, 'reason_codes': ['CODE'] * 2,
                                       'evidence_ref': f'ev:{n}:{i}'} for i in range(25)}} for n in range(3)]
        evidence = [{'id': f'ev:{n}:{i}', 'text': 'Plan value ' + 'z' * 200 + ' (published 2026 term; shown for review, not yet confirmed by Daylight)',
                     'kind': 'published_plan_field', 'review_state': 'reference', 'offering_id': f'H1045-0{n}'}
                    for n in range(3) for i in range(25)]
        evidence += [{'id': f'fact{i}', 'text': 'Reviewed statement ' + 'w' * 300, 'summary': 's'} for i in range(8)]
        return {'reports': [{'id': 'guide.coverage.current', 'value': ['advantage'], 'status': 'reported'}],
                'applicable_rules': [{'rule_id': 'ma_trial_right', 'statement': 'rule'}],
                'advisor_brief': {'discourse': ['note'] * 5},
                'recent_exchanges': [{'user': 'u' * 400, 'assistant': 'a' * 900, 'question': 'q'} for _ in range(8)],
                'education_context': {'catalog': {'concepts': [{'concept_id': 'c', 'description': 'd' * 500}] * 10}},
                'learner_context': {'observations': ['o' * 2000]},
                'plans_context': {'plans': plans, 'compared_ids': [p['id'] for p in plans], 'reference_notice': 'n' * 300},
                'evidence': evidence}

    def test_oversized_context_is_compacted_oldest_first_and_keeps_reports_rules_and_moves(self):
        context = self.big_context()
        before = len(json.dumps(context))
        steps = NaturalAgent._fit_context(context, self.moves, 40_000)
        # Measured the way _fit_context measures (compact UTF-8 JSON); with D155
        # history goes last, so compaction stops at the bound with little slack.
        after = len(json.dumps({'resolved_context': context, 'question_candidates': self.moves}, ensure_ascii=False, separators=(',', ':')).encode())
        self.assertLessEqual(after, 40_000)
        self.assertLess(after, before)
        # D155: history is compacted last, and only the oldest exchanges.
        self.assertNotIn('recent_exchanges:3', steps)
        self.assertTrue(all(not s.startswith('recent_exchanges') for s in steps[:-1]))
        self.assertEqual(context['reports'][0]['id'], 'guide.coverage.current')
        self.assertEqual(context['applicable_rules'][0]['rule_id'], 'ma_trial_right')
        self.assertEqual(context['advisor_brief']['discourse'], ['note'] * 5)
        # Every evidence id the model may cite is still in the context.
        self.assertTrue(all(item['id'] for item in context['evidence']))

    def test_fitting_context_is_untouched(self):
        context = {'reports': [], 'evidence': [], 'recent_exchanges': [{'user': 'hi', 'assistant': 'hello', 'question': ''}]}
        self.assertEqual(NaturalAgent._fit_context(context, self.moves, 40_000), [])
        self.assertEqual(len(context['recent_exchanges']), 1)

    def test_oversized_compose_request_is_sent_after_compaction(self):
        self.context.update(self.big_context())
        self.context['current_message'] = 'Compare the plans.'
        self.answer = self.composition()
        # The merged compose instructions carry both dev's and the D155 rules (~2 KB more).
        self.agent.max_input_bytes = 63_000
        out = self.compose()
        self.assertEqual(out['question'], self.answer['question'])
        self.assertTrue(self.agent.local.context_trim)
        self.assertLessEqual(len(json.dumps(self.calls[-1]).encode()), 63_000)
