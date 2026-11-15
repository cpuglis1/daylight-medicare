"""D86 natural conversation over the retained, read-only dependency engine.

Reported facts resolve before prose is generated. Visit journals contain no raw
messages, saving stays optional, and actual preparation keeps its own authority.
"""
import copy
from contextvars import ContextVar
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import time

from advisor_flow import AdvisorConversation, fingerprint
from adaptive_flow import AdaptiveConversation, metadata, FIELD, Q, explicit_task, month
from chat import ModelUnavailable
from guest_profiles import ProfileError, for_storage
from profile_readiness import reject_sensitive
from identifier_guard import IDENTIFIER_MESSAGE, find_identifiers, submitted_strings
from log_guard import install as install_log_guard
from situation import FIELDS as SITUATION_FIELDS, MONTHS, birthday_first_day, observations
from advisor_models import MODELS
from advisor_memory import VisitMemory, CONTEXT_POLICY, HISTORY_LIMIT as VISIT_HISTORY_LIMIT, HISTORY_TTL as VISIT_HISTORY_TTL
from education import catalog_context, learning_context, concepts_for_lesson, plan_update
import learner_state
from decision_guidance import guidance
from applicable_rules import applicable_rules, required_target as select_required_target, floor_statement
from understanding import UnderstandingRegistry, UnderstandingError, attach_understanding
from task_work import (build_context as task_work_context, plan as plan_task_work,
                       attach_result as attach_task_work)
from natural_agent import NaturalAgent
from datetime import datetime, timezone

import cms_checklist
import medigap_profile
import conversation_planner
import recommendation_engine
import part_d_profile
import ux_flow
import enrollment_flow
# Local additions only: never mutate the imported 41-question engine catalogs.
Q = {**Q, **medigap_profile.CATALOG}
FIELD = {**FIELD, **medigap_profile.FIELDS}
from comparison_service import ComparisonService
from plan_review import PlanReviewService, readiness as plan_readiness, OPEN_STATES, input_digest as plans_input_digest
from plans_context import rehydrate as plans_rehydrate, context_evidence as plans_evidence, public_binding as plans_binding
from conversation_output import generated_conversation
from pilot_knowledge import PilotKnowledge, held_deadline_claim
from turn_contract import question_binding, working_assessment, outcome
from contextual_capture import classify_situation
from controller_diagnostics import unexpected_failure
from narrative_agent import provider_failure_message
from natural_state import (ensure_state, legacy_projection, restore_state, retirement_status_from_text,
                           record_capture, classify_update,
                           build_context, set_target, prune_for_storage, sync_agenda,
                           apply_agenda_reports, agenda_context, record_advisor_move)

PREVIOUS_CONTEXT_POLICY = 'natural-context-v2'
LEGACY_CONTEXT_POLICY = 'natural-context-v1'
# Active approved questions can need a narrower capability than the broad
# comparison goal. These use the existing timing allowlist, never all fields.
TIMING_CONTEXT_TARGETS = frozenset({'T04', 'T05', 'RC04', 'RC05', 'RC06', 'RC08',
    'RC09', 'RC10', 'RC11', 'RC12', 'RC13', 'RC26', 'RC27', 'S_AGE65', 'S_RETIREMENT'})
FAMILIARITY_CONTEXT_REFS = frozenset({'guide.situation.age65', 'guide.situation.retirement',
    'readiness.RC09.profile.choice'})
COMPOSITION_CODES = frozenset({'ungrounded_literal', 'ungrounded_entity', 'invalid_reference', 'false_unavailability',
    'missing_followup',
    'unsupported_finding', 'missing_evidence', 'missing_report_reference', 'missing_coverage_reference',
    'missing_worker_reference', 'missing_progress_reference', 'format_or_duplicate_question',
    'unavailable', 'transport_or_format', 'provider_failure', 'composition_unavailable',
    'input_token_verification', 'text_bound', 'invalid_structure', 'input_bound'})
LOGGER = logging.getLogger(__name__)
install_log_guard()  # HP-09: last-line identifier filter on Daylight loggers.
# Questions a Plans-page filter may answer (D97). All are free structured answers.
PLANS_FILTER_QUESTIONS = frozenset({'T01', 'RC01', 'T03', 'RC03', 'T05', 'RC04', 'T06', 'T07', 'T08', 'T09', 'T10'})
QUESTION_TOPICS = {'T02':'learning','T04':'timing','T05':'current_coverage','T06':'doctors',
    'T07':'drugs','T08':'travel','T09':'total_cost','T10':'other','RC09':'current_coverage',
    'RC11':'timing','S_AGE65':'timing','RC21':'doctors','RC22':'drugs','RC23':'drugs','RC25':'total_cost'}
TOPIC_FACTS = {'doctors':'checks','drugs':'drugbasics','total_cost':'costs','bills':'costs',
    'travel':'checks','flexibility':'switching','timing':'dates','learning':'basics',
    'coverage_paths':'routesintro','current_coverage':'basics','other':'checks'}
FACT_TOPICS = {'routesintro':'coverage_paths','options':'coverage_paths','checks':'doctors',
    'drugbasics':'drugs','drugs':'drugs','costs':'total_cost','medical_limit':'bills',
    'dates':'timing','switching':'flexibility','original':'coverage_paths','advantage':'coverage_paths'}


LESSON_EDITORIAL_SENTENCES = {
    'enrollment_intro': ' Do not turn this general explanation into a personal start date, deadline, eligibility decision or permission to delay Part B.',
    'cobra_timing': ' Use actual Medicare enrollment status and the applicable official enrollment rules to establish a personal next step; do not calculate a personal deadline or effective date from the COBRA end alone.',
}


# Owner sign-off November 13, 2026 (first line); the second follows its wording for a failure that was not slow.
TURN_TOO_LONG = 'That took too long, so I stopped. Your message is still here. Send again?'
TURN_FAILED = 'Something went wrong on our side, so I stopped. Your message is still here. Send again?'


def list_items(text, doctors=False):
    """Names in a medicine/doctor list as the person wrote them, de-duplicated.

    Medicines split on ; , newline and a standalone "and"; doctors only on ;
    and newline, because a doctor entry often carries a comma ("Dr. Maria
    Lopez, Naples") or "and" ("Naples Heart and Vascular"). Never rewrites a name.
    """
    if not isinstance(text, str):
        return []
    pattern = r'\s*(?:;|\n)\s*' if doctors else r'\s*(?:;|,|\n|\band\b(?=\s+[A-Za-z]))\s*'
    parts = re.split(pattern, text.strip())
    seen, items = set(), []
    for part in parts:
        part = part.strip(' .')
        key = part.casefold()
        if part and key not in seen and key not in {'unknown', 'deferred', 'not sure', 'check later', 'later', 'none', 'no'}:
            seen.add(key); items.append(part)
    return items


class NaturalConversation(AdvisorConversation):
    @property
    def agent(self):
        return self._turn_agent.get() or self._agent

    @agent.setter
    def agent(self, value):
        self._agent = value

    def __init__(self, *args, **kwargs):
        self._turn_agent = ContextVar('daylight_turn_agent', default=None)
        super().__init__(*args, **kwargs)
        # This service owns its in-memory contract; pinned contract files and
        # their original question meanings remain unchanged.
        node = next(node for node in self.contract['nodes'] if node['id'] == 'R00')
        node['writes'] = list(dict.fromkeys([*node['writes'], *medigap_profile.FIELDS.values()]))
        self.agent = NaturalAgent.from_agent(self.agent)
        self.model_agents = {}
        self.progress_fact_ids = frozenset(self.facts)
        for fact in json.loads((Path(__file__).parent / "advisor-evidence.json").read_text())["facts"]:
            # The retained source also contains editorial instructions. Keep
            # those in the evidence record, separate from the public lesson.
            editorial = LESSON_EDITORIAL_SENTENCES.get(fact['id'])
            public = {**fact, 'text': fact['text'].replace(editorial, '')} if editorial else fact
            self.facts[fact['id']] = copy.deepcopy(public)
            self.agent.facts[fact['id']] = copy.deepcopy(public)
        # Owner direction (November 8, 2026): general Medicare rules the advisor
        # states before redirecting. Kept in their own file so the sealed
        # understanding registry lock is untouched; acceptance is recorded there.
        # Later sets (pilot-rules-r2.json, …) load only once the owner has set
        # their review_state to owner_accepted_<date>; a pending draft is inert.
        self.rule_facts = {}
        self.pilot_knowledge = PilotKnowledge()
        if not os.environ.get('DAYLIGHT_DISABLE_PILOT_RULES'):
            for rules_path in sorted(Path(__file__).parent.glob("pilot-rules*.json")):
                document = json.loads(rules_path.read_text())
                if not str(document.get('review_state', '')).startswith('owner_accepted'):
                    continue
                for fact in document["facts"]:
                    if fact.get('source') == '' and not fact.get('sources'):
                        # An owner statement without a source is only loaded
                        # once the owner has filled it in (no [OWNER] brackets).
                        if '[OWNER' in fact.get('text', ''):
                            continue
                    self.rule_facts[fact['id']] = copy.deepcopy(fact)
                    self.facts[fact['id']] = copy.deepcopy(fact)
                    self.agent.facts[fact['id']] = copy.deepcopy(fact)
        self.turn_journal = {}
        self.natural_active = set()
        self.clarifications = {}
        # Plans-page filter entries not yet acknowledged in the conversation,
        # per visit chain (Nov 9, 2026: taken as the person's report, never sent
        # as chat turns; the next chat reply acknowledges them once).
        self.plans_additions = {}
        # D138: when the fixed "Before you enroll" step was shown and
        # acknowledged, per visit chain. Visit-only, like the dialogue.
        self.before_enroll_times = {}
        # The last never-blank floor statement per visit chain, so a failed
        # turn never repeats the previous turn's fallback sentence (R5).
        self.last_floor = {}
        self.binding_key = secrets.token_bytes(32)
        self.state_heads = {}
        self.current_chain = {}
        self.revoked_owners = {}
        self.action_chains = {}
        # Dialogue is useful for continuity, but is never profile authority or
        # saved data. Browser-authored history is deliberately unsupported.
        self.memory = VisitMemory()
        self.visit_memory = self.memory._visits
        self.composition_diagnostics = []
        self.comparisons = ComparisonService()
        self.plan_reviews = PlanReviewService()
        self.plans_service = None
        self._plans_context = ContextVar('plans_context', default=None)
        self.understanding = UnderstandingRegistry()
        # D157: one additive profile field (the coverage path) and the
        # visit-only say-once ledger.
        ux_flow.register(self)

    def response(self, g, r, reply='', **extras):
        # Derived comparison data stays outside the two saved profile records.
        # Final turn attachment rebinds after provenance/composition bookkeeping.
        out = self.comparisons.attach(super().response(g, r, reply, **extras))
        out['planReadiness'] = plan_readiness(g, r)
        out['medigapProfile'] = medigap_profile.profile(g)
        out['partDProfile'] = part_d_profile.profile(g, r)
        if getattr(self, 'eval_recommendations', False):
            # D147: the reported details the evaluation-only sorting reads.
            out['recommendationInputs'] = recommendation_engine.inputs(g, r, out['medigapProfile'], out['partDProfile'])
        # D157: the recorded coverage path, what is left before a tab and the
        # personal Medigap window travel with every response.
        return ux_flow.status(self, out, g, r)

    def recent_exchanges(self, owner, task, policy):
        # v3 grants bounded visit continuity across topic changes. Older scoped
        # permission never silently expands to this new conversation context.
        return self.memory.recent(owner, self.current_chain.get(owner), policy)

    def remember_exchange(self, owner, message, out, policy, request_id):
        if self.fixture:
            return
        if self._plans_context.get():
            # Do not carry plan assertions into later turns after a release or
            # profile changes. Each Plans Send rehydrates its own fresh facts.
            # Preserve learning/task metadata under the existing visit policy.
            # The person's own words and Daylight's own question are not plan
            # assertions; dropping them made the Plans chat re-ask a question
            # already answered (S4, Nov 9, 2026). Only the reply is withheld.
            out = copy.deepcopy(out)
            out['reply'] = '(answered a question about the plans on screen)'
        question = out['assessment'].get('nextQuestion') or {}
        candidates = self.eligible(owner, out['guide'], out['record'])
        candidate_ids = [item['question']['id'] for item in candidates]
        target = question.get('id')
        if target and target not in candidate_ids:
            candidate_ids.append(target)
        working = out.pop('_advisor_memory', {})
        self.memory.remember(owner, self.current_chain.get(owner), policy,
            message, out.get('reply', ''), question.get('question', ''),
            question_target=target, candidate_ids=candidate_ids,
            agenda_update=working.get('agenda_update'), goal=working.get('goal'),
            education_record=working.get('education_record'),
            task_work_record=working.get('task_work_record'),
            learner_record=working.get('learner_record'), continuation=working.get('continuation'),
            discourse_note=working.get('discourse_note'), request_id=request_id)

    def pending_for(self, owner):
        return self.clarifications.get((owner,self.current_chain.get(owner)))

    def clear_pending(self, owner):
        self.clarifications.pop((owner,self.current_chain.get(owner)),None)

    def forget_owner(self, owner):
        """Revoke deleted guest authority and its visit-only working memory."""
        with self.lock:
            if owner in self.natural_active:
                raise ProfileError('A message is still processing. Try deleting after it finishes.', 409)
            self.revoked_owners[owner] = time.time() + VISIT_HISTORY_TTL
            self.memory.forget_owner(owner)
            self.ux.forget_owner(owner)
            if hasattr(self, 'discussion_visits'):
                self.discussion_visits.clear(owner)
            for store in (self.plans_additions, self.last_floor):
                for key in [key for key in store if key[0] == owner]:
                    store.pop(key, None)
            self.plan_reviews.forget_owner(owner)
            if self.plans_service:
                self.plans_service.forget_owner(owner)
            self.current_chain.pop(owner, None)
            for collection in (self.turn_journal, self.state_heads, self.clarifications):
                for key in [key for key in collection if key[0] == owner]:
                    collection.pop(key, None)
            for token in [token for token, binding in self.action_chains.items() if binding[0] == owner]:
                self.action_chains.pop(token, None)

    def record_reviewed_lesson(self, owner, chain, out, identifier, request_id):
        """Count a returned lesson only within an existing permitted v3 visit."""
        fact = next((fact for fact in out.get('facts', []) if fact.get('id') == identifier), None)
        concepts = concepts_for_lesson(identifier)
        if not fact or not fact.get('text') or not concepts:
            return
        prior = self.memory.education(owner, chain, CONTEXT_POLICY)
        updates = [{'concept_id': concept, 'depth': 'introduced',
                    'reason': 'requested_revisit' if concept in prior['concepts'] else 'new',
                    'evidence_refs': [identifier]} for concept in concepts]
        visuals = [visual for item in catalog_context()['concepts'] if item['concept_id'] in concepts
                   for visual in item['visuals']]
        planned = plan_update(prior, {'purpose': 'teach', 'updates': updates,
            'visual': visuals[0] if visuals else 'none'}, [identifier], requested_revisit=True,
            revisit_concepts=concepts, event_id=request_id)
        # No AI call, fake exchange or new permission is created. A shared
        # source maps to its primary lesson, not every concept it can support.
        if self.memory.commit_education(owner, chain, CONTEXT_POLICY, planned['record']):
            out['education'] = learning_context(planned['record'])
            out.setdefault('advisor', {})['visual'] = planned['visual']

    def initial(self):
        g, r = super().initial()
        ensure_state(r)
        return g, r

    def validate(self, guide, record):
        try:
            lg, lr = legacy_projection(guide, record)
            g, r = super().validate(lg, lr)
            medigap_profile.validate(g)
            return restore_state(g, r, record.get('natural'))
        except ValueError as error:
            if isinstance(error, ProfileError):raise
            raise ProfileError(str(error)) from None

    @staticmethod
    def binding_content(g, r):
        g = copy.deepcopy(g)
        g.pop('preferences', None)
        g.get('flow', {}).pop('guideOpen', None)
        return fingerprint(g, r)

    def bind(self, owner, g, r, chain):
        signature = hmac.new(self.binding_key, (owner + ':' + chain + ':' + self.binding_content(g, r)).encode(), hashlib.sha256).hexdigest()
        return chain + '.' + signature

    def current_presentation(self, owner, continuation):
        """Utility navigation retains the validated server turn, never UI input."""
        if not continuation:
            return None
        chain = continuation.split('.')[0]
        with self.lock:
            if (self.current_chain.get(owner) != chain
                    or self.state_heads.get((owner, chain)) != continuation):
                return None
            for (entry_owner, _), entry in reversed(list(self.turn_journal.items())):
                if (entry_owner == owner and entry['expires'] > time.time()
                        and entry['response'].get('continuation') == continuation):
                    return copy.deepcopy(entry['response']['assessment'])
        return None

    @staticmethod
    def retain_presentation(out, previous):
        if previous is None:
            return out
        assessment = out['assessment']
        for key in ('nextQuestion', 'intakePaused', 'conversationOpen'):
            if key in previous:
                assessment[key] = copy.deepcopy(previous[key])
            else:
                assessment.pop(key, None)
        for key in ('opener', 'focus'):
            if key in previous.get('narrative', {}):
                assessment['narrative'][key] = copy.deepcopy(previous['narrative'][key])
            else:
                assessment['narrative'].pop(key, None)
        return out

    def question(self, id, fields=None, entity='profile', text=None):
        if conversation_planner.enabled(self) and id in conversation_planner.DISCUSSION_QUESTIONS:
            return conversation_planner.question(id)
        if id in medigap_profile.FIELDS:
            return medigap_profile.question(id)
        if id in {'orientation','S_AGE65','S_RETIREMENT'}:
            wording={'orientation':'Where are you with Medicare so far?', 'S_AGE65':'What month and year do you turn 65?',
                     'S_RETIREMENT':'Are you retired, planning to retire, or still working?'}[id]
            return {'id':id, 'entity':'profile', 'question':text or wording,
                    'why':'', 'fields':[], 'choices':[], 'multi':False,
                    'signature':'natural-orientation-v1', 'conversational':True}
        return super().question(id, fields, entity, text)

    def assess(self, guide, record, edit=None):
        a = super().assess(guide, record, edit)
        dialogue = ensure_state(record)['dialogue']
        if (dialogue['orientation'] in {'progress', 'familiarity'}
                and self.value(guide, 'knowledge.general') is None
                and 'T02' not in metadata(record)['baselineDispositions']
                and not (edit or metadata(record).get('editing'))):
            a['nextQuestion'] = self.question('T02')
        target=dialogue.get('lastTarget')
        if (target and target['id'] == 'S_AGE65' and not self.value(guide, 'situation.age65')
                and 'S_AGE65' not in record['dispositions'] and not (edit or metadata(record).get('editing'))):
            a['nextQuestion'] = self.question('S_AGE65')
        if target and target['id'] in Q and self.target_relevant(guide,record,target['id']) and not (edit or metadata(record).get('editing')):
            identifier = target['id']
            missing = (self.value(guide, FIELD[identifier]) is None and identifier not in metadata(record)['baselineDispositions']) if identifier in FIELD else not self.report(record, identifier) and identifier not in record['dispositions']
            if identifier in medigap_profile.FIELDS:
                missing = any(item['id'] == identifier for item in medigap_profile.profile(guide)['questions'])
            if identifier not in FIELD and target.get('fields'):
                value=self.report(record,identifier)
                entity=target.get('entity','profile')
                item=value if entity=='profile' else next((item for item in value.get('items',[]) if item.get('entity')==entity),{})
                missing=any(not item.get(key) and not metadata(record)['skippedDetails'].get(identifier+'.'+entity+'.'+key)
                            for key in target['fields'])
            if identifier == 'RC01':
                missing=(self.value(guide,'subject.role') is None
                         and self.report(record,'RC01').get('choice')!='research'
                         and record['dispositions'].get('RC01',{}).get('state') not in {'explicit_unknown','deferred'})
            if missing:
                current=a.get('nextQuestion') or {}
                current_fields=[field['key'] for field in current.get('fields',[])]
                if (current.get('id')!=identifier or current.get('entity','profile')!=target.get('entity','profile')
                        or current_fields!=target.get('fields',[])):
                    a['nextQuestion'] = self.question(identifier, target.get('fields') or None, target.get('entity', 'profile'))
        if (a.get('nextQuestion') or {}).get('id')=='T06' and 'doctors' in (self.value(guide,'needs.priorities') or []):
            a['nextQuestion']=self.provider_detail_question()
        if self.ambiguous_current_coverage(guide):
            a['nextQuestion']=self.question('T05')
            a['state']='missing_information'
            a['ruleDecisions']['T05']['state']='conflicting'
            a['unresolvedReportedInputs'].append({'id':'T05','label':'Which Medicare coverage is current','state':'needs clarification'})
        a['narrative']['natural'] = True
        a['nextQuestion'] = self.contextual_question(guide,record,a.get('nextQuestion'))
        readiness = plan_readiness(guide, record)
        if (readiness['active'] and not self.ambiguous_current_coverage(guide)
                and not (edit or metadata(record).get('editing'))):
            candidates = self.plan_questions(guide, record, readiness)
            if readiness['canReview']:
                a['nextQuestion'] = None
            elif not a.get('nextQuestion'):
                a['nextQuestion'] = candidates[0]['question'] if candidates else None
        if not self.ambiguous_current_coverage(guide) and not (edit or metadata(record).get('editing')):
            pricing = self.medigap_questions(guide, record) or self.part_d_questions(guide, record)
            if pricing:
                a['nextQuestion'] = pricing[0]['question']
        return a

    @staticmethod
    def named_plan_task(text):
        """The Original Medicare product a person names, if any (D138)."""
        if not isinstance(text, str) or not text:
            return None
        if re.search(r'(?i)\bmedigap\b|\bmedicare supplements?\b|\bsupplement(?:al)? (?:plans?|insurance|polic(?:y|ies)|coverage)\b'
                     r'|\b(?:a|the) supplement\b|\b(?:high[- ]deductible )?plan [fgk-n]\b', text):
            return 'medigap'
        if re.search(r'(?i)\bpart d\b|\b(?:drug|prescription)(?: drug)? (?:plans?|coverage)\b|\bpdp\b', text):
            return 'drug_pricing'
        return None

    def part_d_questions(self, guide, record):
        # Reuse existing meanings for the drug-price task; no second intake.
        if conversation_planner.enabled(self) or metadata(record)['task'] != 'drug_pricing':
            return []
        view = part_d_profile.profile(guide, record)
        missing = [key for key in view['missing'] if key not in view['held']]
        if view['status'] == 'unsupported' or not missing:
            return []
        identifier = missing[0]
        if identifier == 'RC02' and not view['inputs']['zipcode']:
            return []  # A ZIP left open does not justify a county follow-up.
        fields = ['county'] if identifier == 'RC02' else ['year'] if identifier == 'RC03' else None
        question = self.question(identifier, fields)
        if identifier == 'T03':
            question['why'] = 'Your home ZIP and county identify which Part D plan information applies to your area.'
        elif identifier == 'RC02':
            question['question'] = 'Which county and state is that home ZIP in?'
            choices = self.reference['zips'].get(view['inputs']['zipcode'], [])
            if choices:
                question['fields'][0].update(type='select', options=[[x[0], x[1]+', '+x[2]] for x in choices])
        elif identifier == 'RC03':
            question['question'] = 'Which coverage year should we use for Part D plans?'
            question['why'] = 'Plans and their costs can change each year. Daylight has 2026 plans.'
        return [{'id': identifier, 'question': question, 'topic': 'drugs', 'priority': 0, 'required': False,
                 'purpose': 'Ask only this missing detail to locate dated Part D plan information. Reuse reported facts and explain why. Published premiums do not establish personal prescription costs.'}]

    def medigap_questions(self, guide, record):
        if conversation_planner.enabled(self) or metadata(record)['task'] != 'medigap':
            return []
        view = medigap_profile.profile(guide)
        if view['status'] == 'unsupported':
            return []
        missing = [key for key in view['missing'] if key not in view['held']]
        if not missing:
            return []
        identifier = missing[0]
        if identifier in {'RC01', 'T03'} and (identifier in record.get('dispositions', {})
                or identifier in metadata(record)['baselineDispositions']):
            return []
        return [{'id': identifier, 'question': self.contextual_question(guide, record, self.question(identifier)), 'topic': 'total_cost',
                 'priority': 0, 'required': False,
                 'purpose': 'Ask only this missing beneficiary detail for the dated Medigap price lookup. Explain why it is needed; unknown and check later keep prices unavailable.'}]

    def rows(self, g, r):
        rows = super().rows(g, r)
        for identifier, field in medigap_profile.FIELDS.items():
            item = g['fields'].get(field)
            if item:
                rows.append({'id': identifier, 'label': medigap_profile.LABELS[identifier],
                             'value': item['value'], 'status': item['status']})
        # D138: the current-insurance label says "(Parts A and B)". When the
        # person reported only one part, or none yet, the review must not
        # contradict that report two rows later.
        parts = (r.get('facts', {}).get('RC04', {}).get('value') or {}).get('choice')
        if parts in {'a_only', 'b_only', 'neither', 'pending'}:
            for row in rows:
                if row['id'] == 'T05' and isinstance(row['value'], str):
                    row['value'] = row['value'].replace('Original Medicare (Parts A and B)', 'Medicare')
        return rows

    def plan_questions(self, g, r, readiness):
        """Missing meanings, not a prescribed sequence or question counter."""
        candidates = []
        for criterion in readiness['missing']:
            if any(c['id'] == 'person' for c in readiness['missing']) and criterion['id'] != 'person':
                continue
            if criterion['state'] in OPEN_STATES:
                continue  # An explicit deferral is never an automatic repeat.
            identifier = criterion['question_id']
            question = self.question(identifier, criterion['fields'])
            if identifier == 'RC03':
                question['question'] = 'Which coverage year would you like to compare?'
            if identifier == 'RC02':
                question['question'] = 'Which county and state is that home ZIP in?'
                choices = self.reference['zips'].get(self.value(g, 'comparison.scope.zip'), [])
                if len(choices) > 1:
                    question['fields'][0].update(type='select', options=[[x[0], x[1]+', '+x[2]] for x in choices])
            candidates.append({'id': identifier, 'question': question, 'priority': 1,
                'required': criterion['state'] == 'needs_clarification',
                'topic': QUESTION_TOPICS.get(identifier, ''),
                'purpose': 'Needed to frame the requested plan comparison: '+criterion['label']+
                    '. Reuse existing answers. An explicit unknown stays open; it is not verification.'})
        if (candidates and not any(c['required'] for c in candidates)
                and self.value(g, 'subject.role') and self.value(g, 'knowledge.general') is None
                and 'T02' not in metadata(r)['baselineDispositions']):
            candidates.append({'id': 'T02', 'question': self.question('T02'), 'priority': 2,
                'required': False, 'topic': 'learning',
                'purpose': 'Optional: calibrate an explanation if the person’s understanding is unclear. Not a review requirement.'})
        return candidates

    def contextual_question(self,guide,record,question):
        if question and question['id'] in medigap_profile.FIELDS:
            return medigap_profile.question(question['id'], self.value(guide, 'subject.role'))
        if not question or question['id']!='RC11':
            return question
        kind=self.report(record,'RC09').get('choice')
        if kind not in {'cobra','retiree'}:
            return question
        question=copy.deepcopy(question)
        fields={item['key'] for item in question.get('fields',[])}
        name='COBRA' if kind=='cobra' else 'retiree coverage'
        question['coverageKind']=kind
        if fields=={'coverageEnd'}:
            question['question']='When does your '+name+' coverage end?' if kind=='cobra' else 'When does your retiree coverage end?'
        elif fields=={'jobEnd'}:
            question['question']='When did the job behind that coverage end?'
        elif fields=={'jobEnd','coverageEnd'}:
            question['question']='When did the job end, and when does your '+name+' coverage end?'
        question['why']='Keep the reported coverage end separate from any Medicare start date.'
        for item in question.get('fields',[]):
            item['label']=(name+' end date' if item['key']=='coverageEnd' else 'Previous job end date')
        return question

    def target_relevant(self,guide,record,identifier):
        """Do not resurrect an old question after its dependency was corrected.

        This only recognizes explicit contradictions. Unreported circumstances
        remain unknown; the normal dependency engine and pending-report queue
        continue to select any consequential clarification.
        """
        coverage=self.value(guide,'coverage.current')
        if identifier=='RC21' and self.value(guide,'needs.providersStatus')=='none':return False
        if identifier in {'RC22','RC23','RC24'} and self.value(guide,'needs.medicinesStatus')=='no':return False
        if coverage is not None:
            if identifier in {'RC09','RC10','RC11','RC13'} and not set(coverage)&{'employer','retiree','cobra'}:return False
            if identifier=='RC12' and not set(coverage)&{'employer','retiree','cobra','military'}:return False
            if identifier=='RC26' and 'military' not in coverage:return False
            if identifier=='RC16' and 'advantage' not in coverage:return False
        if identifier=='RC20':
            travel=self.value(guide,'needs.travel')
            if travel is not None and not set(travel)&{'elsewhere_us','another_state','outside_us'}:return False
        if identifier=='RC05' and self.report(record,'RC04').get('choice') in {'a_only','neither','pending'}:return False
        if identifier=='RC10' and self.report(record,'RC09').get('choice') in {'retiree','cobra'}:return False
        if identifier=='RC10' and self.report(record,'RC06').get('choice') in {'esrd','als','other'}:return False
        return True

    def provider_detail_question(self):
        # T06's approved free-text meaning is provider identity. An explicit
        # keep-doctor priority already answers whether there is someone to keep.
        question=self.question('T06')
        question['question']='Which doctors or hospitals would you like to keep?'
        return question

    @staticmethod
    def matches_pending(pending, update):
        if not pending:
            return False
        def keys(fields):
            return set(fields) if isinstance(fields, dict) else {field['key'] for field in fields}
        return any(target['id'] == update['id']
                   and target.get('entity', 'profile') == update.get('entity', 'profile')
                   and keys(target.get('fields', {})) <= keys(update.get('fields', {}))
                   for target in [pending['update'], *pending.get('remaining', [])])

    def aggregate_still_pending(self, pending, update, additional=()):
        return bool(pending and any(target['id'] == update['id']
                    and not any(self.matches_pending({'update':target}, resolved)
                                for resolved in (update, *additional))
                    for target in [pending['update'], *pending.get('remaining', [])]))

    @staticmethod
    def touches_pending(pending,update):
        return bool(pending and any(target['id']==update['id']
            and target.get('entity','profile')==update.get('entity','profile')
            and set(target.get('fields',{}))&set(update.get('fields',{}))
            for target in [pending['update'],*pending.get('remaining',[])]))

    @staticmethod
    def pending_resolution_update(pending, update, record):
        """Address an unresolved item only after the user names a retained item.

        A profile-scoped ambiguous edit has no selected medicine/provider yet.
        An explicit item report can clarify that target without changing the
        actual capture entity or choosing the first matching name. Unrelated
        fields and other pending targets remain unresolved.
        """
        identifier, entity = update['id'], update.get('entity', 'profile')
        if not pending or identifier not in {'RC21', 'RC22', 'RC23'} or entity in {'profile', '', 'new'}:
            return update
        item_source = 'RC22' if identifier == 'RC23' else identifier
        items = record['facts'].get(item_source, {}).get('value', {}).get('items', [])
        if not any(item.get('entity') == entity for item in items):
            return update
        targets = [pending['update'], *pending.get('remaining', [])]
        if any(target['id'] == identifier and target.get('entity', 'profile') == 'profile'
               and (set(target.get('fields', {})) - {'choice'}) & set(update.get('fields', {}))
               for target in targets):
            return {**update, 'entity': 'profile'}
        return update

    def resolve_pending(self, owner, update, guide, record):
        pending = self.pending_for(owner)
        if not pending:
            return
        remaining=[]
        for target in [pending['update'],*pending.get('remaining',[])]:
            if target['id']==update['id'] and target.get('entity','profile')==update.get('entity','profile'):
                fields={key:value for key,value in target.get('fields',{}).items() if key not in update.get('fields',{})}
                if fields:remaining.append({**target,'fields':fields})
            else:remaining.append(target)
        if not remaining:
            self.clear_pending(owner)
        else:
            pending.update(update=remaining[0], remaining=remaining[1:],
                           revision=[guide['stateVersion'], record['stateVersion']])

    def queue_pending(self, owner, updates, guide, record):
        pending = self.pending_for(owner)
        targets = ([pending['update'], *pending.get('remaining', [])] if pending else [])
        for update in updates:
            if update.get('entity') in ('new', ''):
                # A report about a list entry that does not exist yet is held as a question about the
                # list. Held as 'new' it became a question no target can name, the whole turn failed and
                # the medicine list was lost (profiles PP07 and PP14, November 13, 2026).
                update = {**update, 'entity': 'profile'}
            if not any(self.matches_pending({'update':target}, update)
                       and self.matches_pending({'update':update}, target) for target in targets):
                targets.append(copy.deepcopy(update))
        self.clarifications[(owner,self.current_chain[owner])] = {
            'update':targets[0], 'remaining':targets[1:],
            'revision':[guide['stateVersion'], record['stateVersion']], 'chain':self.current_chain[owner]}

    def retire_item_targets(self,owner,guide,record,update):
        omitted=({'RC21'} if update.get('id')=='T06' and update.get('fields',{}).get('choice')=='none'
                 else {'RC22','RC23','RC24'} if update.get('id')=='T07' and update.get('fields',{}).get('choice')=='no'
                 else set())
        pending=self.pending_for(owner)
        if omitted and pending:
            remaining=[item for item in [pending['update'],*pending.get('remaining',[])] if item['id'] not in omitted]
            self.clear_pending(owner)
            if remaining:self.queue_pending(owner,remaining,guide,record)

    def put(self, guide, key, value, source):
        previous = guide['fields'].get(key, {}).get('revision')
        super().put(guide, key, value, source)
        if key in {'situation.age65', 'coverage.birth', 'coverage.birth.firstDay'} and guide['fields'][key]['revision'] != previous:
            age = guide['fields'].get(medigap_profile.FIELDS['MG_AGE'])
            if age and age.get('status') == 'reported':
                # Preserve the old report as stale, rather than showing it as
                # current in chat/review while the price view uses a new birthday.
                age['status'] = 'stale'

    def apply(self, guide, record, update, source='user_choice'):
        if update.get('id') in medigap_profile.FIELDS:
            if self.value(guide, 'subject.role') not in {'self', 'someone'}:
                raise ProfileError('Tell Daylight who receives coverage before adding their pricing details.')
            if update.get('entity', 'profile') != 'profile':
                raise ProfileError('Use the current beneficiary’s pricing detail.')
            try:
                value = medigap_profile.parse(update['id'], update.get('fields'))
            except ValueError as error:
                raise ProfileError(str(error)) from None
            field = medigap_profile.FIELDS[update['id']]
            self.put(guide, field, value, source)
            if value in ('unknown', 'deferred'):
                guide['fields'][field]['status'] = 'unknown' if value == 'unknown' else 'skipped'
            return
        list_id = update.get('id', '').split('.')[0]
        quote = str(update.get('quote') or '')
        # "I also take atorvastatin" adds, even when the extractor marks it a
        # correction (live check, Nov 9, 2026: the list was replaced). Only the
        # person's own replacement words make it a replacement.
        additive = bool(re.search(r"(?i)\b(?:also|too|as well|another|in addition|plus|add(?:ed|ing)?)\b", quote)
                        and not re.search(r"(?i)\b(?:instead|actually|no longer|not taking|don['\u2019]?t take|stopped|quit|replac\w*|switch\w*|changed|rather|wrong|only take|correction)\b", quote))
        if list_id in {'T06', 'T07'} and isinstance(update.get('fields'), dict) and (not update.get('correction') or additive):
            text = update['fields'].get('text')
            status_path, list_path = (('needs.providersStatus', 'needs.providers') if list_id == 'T06'
                                      else ('needs.medicinesStatus', 'needs.medications'))
            if (isinstance(text, str) and text.strip() and text.strip().casefold() not in {'unknown', 'deferred', 'not sure', 'check later', 'later'}
                    and self.value(guide, status_path) in {'yes', 'list'} and self.value(guide, list_path)):
                # A list grows by union: "metformin" after "Eliquis" keeps both,
                # and a full restated list does not duplicate names.
                doctors = list_id == 'T06'
                merged = list_items(self.value(guide, list_path), doctors)
                merged += [item for item in list_items(text, doctors) if item.casefold() not in {m.casefold() for m in merged}]
                update = {**update, 'fields': {**update['fields'], 'text': '; '.join(merged)}, 'correction': True}
        # A stale aggregate is unavailable for guidance, but remains the complete
        # retained collection when applying a specifically addressed item edit.
        # The inherited report() intentionally hides stale facts, so expose this
        # collection only during its synchronous local mutation and restore its
        # hold afterward. Resolution of the exact pending target releases it.
        identifier = update['id'].split('.')[0]
        if identifier == 'RC01':
            # A pending conflict hides report()'s stale envelope. It must not
            # hide the beneficiary that owns the retained personal reports.
            # Readiness-only facts also need this guard; counting guide fields
            # alone misses them. Intent and familiarity can precede a person.
            prior = record['facts'].get('RC01', {}).get('value', {}).get('choice')
            if prior not in {'self', 'someone'}:
                prior = guide['fields'].get('subject.role', {}).get('value')
            personal_guide = set(guide['fields']) - {'intent.goal', 'intent.goalDetail', 'knowledge.general', 'subject.role'}
            personal_reports = set(record['facts']) - {'RC01'}
            personal_details = metadata(record).get('details', {})
            if prior in {'self', 'someone'} and update.get('fields', {}).get('choice') != prior and (personal_guide or personal_reports or personal_details):
                raise ProfileError('These reports belong to the person already identified. Open a separate visit for another person; the existing information is preserved.')
        retired=(identifier=='RC21' and self.value(guide,'needs.providersStatus')=='none'
                 or identifier=='RC22' and self.value(guide,'needs.medicinesStatus')=='no')
        if retired and identifier in record['facts']:
            previous=copy.deepcopy(record['facts'][identifier]['value'])
            record['history'].append({'triggerId':identifier,'revision':record['stateVersion'],'previous':previous})
            # A new list after an explicit No starts from only the newly supplied
            # items. The retired collection stays recoverable in history, not in
            # the fresh active name projection or as an unspoken identity match.
            update=copy.deepcopy(update)
            if update.get('entity') in {None,'','profile','new'}:
                prefix='doctor' if identifier=='RC21' else 'medicine'
                last=max([int(item['entity'].split('-')[-1]) for item in previous.get('items',[])]+[0])
                update['entity']=prefix+'-'+str(last+1)
            record['facts'][identifier]['value']={'choice':'details','items':[]}
            record['facts'][identifier]['stale']=False
        held = identifier in {'RC21', 'RC22', 'RC23'} and record['facts'].get(identifier, {}).get('stale')
        if held:
            record['facts'][identifier]['stale'] = False
        provider_text = (self.value(guide, 'needs.providers')
            if identifier == 'RC21' and not retired else None)
        previous_offices = copy.deepcopy(record['facts'].get('RC21', {}).get('value', {}).get('items', []))
        medicine_text = (self.value(guide, 'needs.medications')
            if identifier == 'RC22' and not retired else None)
        previous_medicines = copy.deepcopy(record['facts'].get('RC22', {}).get('value', {}).get('items', []))
        def names_item(name, item):
            return bool(name and re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', item, re.I))
        if medicine_text and update.get('entity') in (None, '', 'new', 'profile'):
            # A newly detailed medicine may already occupy a slot in T07.
            # Bind only an unambiguous named entry; do not attach its strength
            # to the first, still-unresolved medicine merely because RC22 is empty.
            name = update.get('fields', {}).get('name', '')
            matches = [i for i, item in enumerate(list_items(medicine_text), 1) if names_item(name, item)]
            if len(matches) == 1:
                entity = 'medicine-' + str(matches[0])
                occupied = next((item for item in previous_medicines if item.get('entity') == entity), None)
                if not occupied:
                    update = {**update, 'entity': entity}
        try:
            result = super().apply(guide, record, update, source)
            if isinstance(medicine_text, str) and medicine_text:
                items = list_items(medicine_text)
                if update.get('correction'):
                    old = next((item.get('name') for item in previous_medicines
                                if item.get('entity') == update.get('entity')), None)
                    new = update.get('fields', {}).get('name')
                    matches = [i for i, item in enumerate(items) if names_item(old, item)]
                    if new and len(matches) == 1 and old.casefold() != new.casefold():
                        items[matches[0]] = new
                projection = self.value(guide, 'needs.medications') or ''
                for name in list_items(projection):
                    if not any(names_item(name, item) for item in items):
                        items.append(name)
                retained = '; '.join(items)
                if retained != projection:
                    self.put(guide, 'needs.medications', retained, source)
            if isinstance(provider_text, str) and provider_text:
                # RC21 owns office detail. Its practice-only convenience
                # projection must not erase the independently reported T06
                # clinician/list text. Reconcile exact office corrections when
                # there is one unambiguous retained office; do not revive names
                # after an explicit No or guess a multi-office text binding.
                projection = self.value(guide, 'needs.providers') or ''
                if update.get('correction') and len(previous_offices) > 1:
                    return result
                if update.get('correction') and len(previous_offices) == 1:
                    for field in ('practice', 'city'):
                        old, new = previous_offices[0].get(field), update.get('fields', {}).get(field)
                        if isinstance(old, str) and old and isinstance(new, str) and new:
                            provider_text = provider_text.replace(old, new)
                for piece in projection.split('; '):
                    if piece and piece.casefold() not in provider_text.casefold():
                        provider_text += '; ' + piece
                if provider_text != projection:
                    self.put(guide, 'needs.providers', provider_text, source)
            return result
        finally:
            if held and identifier in record['facts']:
                record['facts'][identifier]['stale'] = True

    def capture(self, g, r, update, method='direct_report', resolve_aggregate=False):
        before_g, before_r = copy.deepcopy(g), copy.deepcopy(r)
        cg, cr = copy.deepcopy(g), copy.deepcopy(r)
        self.apply(cg, cr, update, 'confirmed_agent_interpretation')
        if resolve_aggregate and update['id'] in {'RC21', 'RC22', 'RC23'} and update['id'] in cr['facts']:
            cr['facts'][update['id']]['stale'] = False
        record_capture(cg, cr, before_g, before_r, update, method=method)
        self.validate(cg, cr)
        g.clear();g.update(cg);r.clear();r.update(cr)

    def teaching_candidates(self,g,r,current=None):
        task=metadata(r)['task'];identifier=(current or {}).get('id','')
        agenda=r.get('natural',{}).get('agenda',{})
        ids=[TOPIC_FACTS[item['topic']] for item in reversed(agenda.get('concerns',[])) if item['status']=='open']
        if 'cobra' in (self.value(g,'coverage.current') or []) and (task=='timing' or identifier in {'T04','RC11','S_AGE65'} or any(item['topic']=='timing' and item['status']=='open' for item in agenda.get('concerns',[]))):
            ids.insert(0,'cobra_timing')
        if identifier=='T05':ids+=['basics','dates','checks']
        elif identifier in {'T04','RC11'}:ids+=['dates','routesintro','checks']
        elif task in {'compare','review','providers'}:ids+=['routesintro','checks','costs']
        elif task in {'drug_coverage','drug_pricing'}:ids+=['drugbasics','costs','checks']
        else:ids+=['basics','parts','routesintro']
        return list(dict.fromkeys(id for id in ids if id in self.facts))[:3]

    def eligible(self, owner, g, r, **options):
        """D157: the dependency engine proposes; ux_flow.refine drops questions whose
        answer changes nothing the person sees and orders the rest toward their plans."""
        return ux_flow.refine(self, owner, g, r, self._eligible(owner, g, r, **options))

    def _eligible(self, owner, g, r, *, allow_orientation=False, answer_only=False, facts=(), priority_changed=False):
        """Consequential question candidates, never exclusive speech actions.

        The advisor may answer/teach with any candidate or stay with the current
        concern. The retained dependency engine still owns conditional meaning.
        """
        if self.ambiguous_current_coverage(g):
            question=self.question('T05')
            return [{'id':'T05','question':question,'topic':'current_coverage','priority':0,'required':True,
                     'purpose':'Clarify which Medicare coverage is current before using the ambiguous retained report. It may describe a transition; do not guess a route.'}]
        pending = self.pending_for(owner)
        if pending and pending['revision'] != [g['stateVersion'], r['stateVersion']]:
            self.clear_pending(owner); pending = None
        if pending:
            update = pending['update']
            fields = [key for key in update.get('fields', {}) if key != 'choice']
            question = self.contextual_question(g,r,self.question(update['id'], fields or None, update.get('entity', 'profile')))
            if question:
                question = copy.deepcopy(question)
                question['clarification'] = {'confirmable': self.pending_confirmation(owner, 'Yes, that\u2019s right.', []) is not None
                                             or self.pending_situation_confirmation(owner, 'Yes, that\u2019s right.', {}) is not None,
                                             'confirmLabel': 'Yes, that\u2019s right'}
            return [{'id': question['id'], 'question': question, 'topic': QUESTION_TOPICS.get(question['id'], ''),
                'purpose': 'Clarify this unresolved report before using it. Do not assert either candidate.',
                'priority': 0, 'required': True}]
        pricing = self.medigap_questions(g, r) or self.part_d_questions(g, r)
        if pricing:
            return pricing
        candidates = []
        current_medicare = set(self.value(g, 'coverage.current') or []) & {'original', 'advantage', 'medigap'}
        def add(question, priority=1, purpose=None):
            if not question or any(item['question']['id'] == question['id'] for item in candidates):
                return
            identifier = question['id']
            if (getattr(self,'conversation_checks',None) and not metadata(r).get('editing')
                    and identifier in self.conversation_checks.answered_locally(owner,g,r)):
                return
            if identifier == 'T04' and current_medicare and not metadata(r).get('editing'):
                return
            question = self.contextual_question(g,r,question)
            candidates.append({'id': identifier, 'question': question,
                'topic': QUESTION_TOPICS.get(identifier, ''), 'priority': priority, 'required': False,
                'purpose': purpose or question.get('why') or Q.get(identifier, {}).get('requiredness', '')})
        assessment = self.assess(g, r)
        if metadata(r).get('editing'):
            add(assessment.get('nextQuestion'), 0)
            return candidates
        role = self.value(g, 'subject.role')
        research_only = self.report(r, 'RC01').get('choice') == 'research'
        subject_deferred = r.get('dispositions', {}).get('RC01', {}).get('state') in {'explicit_unknown', 'deferred'}
        if not role and not research_only and not subject_deferred:
            add(self.question('RC01'), 0, 'Establish who receives coverage before personal coverage questions.')
        elif role:
            if (self.value(g,'coverage.current')==['cobra'] and self.value(g,'situation.age65')
                    and not self.report(r,'RC04') and 'RC04' not in r.get('dispositions',{})):
                add(self.question('RC04'),2,
                    'If timing needs clarification, establish actual Medicare enrollment before asking for a preferred start. COBRA does not establish A/B status; explain the distinction first.')
            # Preview real dependency branches without mutating the profile,
            # actual task, unknowns or deferred reports. A learning detour does
            # not park the advisor in an empty education-only scheduler.
            tasks = list(dict.fromkeys([metadata(r)['task'], 'compare', 'timing']))
            for task in tasks:
                if task in {'', 'learn', 'snp', 'browse'}:
                    continue
                shadow = copy.deepcopy(r)
                metadata(shadow).update(task=task, preparing=True, editing=None)
                for _ in range(4):
                    q = super().assess(g, shadow).get('nextQuestion')
                    if not q:
                        break
                    add(q, 1)
                    if q['id'] in FIELD:
                        metadata(shadow)['baselineDispositions'][q['id']] = 'deferred'
                    else:
                        shadow['dispositions'][q['id']] = {'state':'deferred'}
            coverage = self.value(g, 'coverage.current')
            if (not self.value(g, 'situation.age65') and 'S_AGE65' not in r.get('dispositions', {})
                    and (coverage == ['cobra'] or coverage == ['none'] and metadata(r)['task'] == 'timing')):
                add(self.question('S_AGE65'), 2,
                    'Ask for the 65th-birthday month, year and first-of-month exception together when the person needs age-based timing.')
            # These baseline meanings have no external lookup dependency.
            for identifier in ('T05', 'T04', 'T03', 'T06', 'T07', 'T08', 'T09', 'T10'):
                if self.value(g, FIELD[identifier]) is None and identifier not in metadata(r)['baselineDispositions']:
                    q = self.provider_detail_question() if identifier == 'T06' and 'doctors' in (self.value(g, 'needs.priorities') or []) else self.question(identifier)
                    add(q, 2)
        if candidates and self.value(g, 'knowledge.general') is None and 'T02' not in metadata(r)['baselineDispositions']:
            add(self.question('T02'), 2,
                'Optional familiarity question only if needed to calibrate explanations; do not make it a required intake step.')
        # Current insurance helps establish the timing rules before asking for
        # a preferred start, including when the birthday is not yet known.
        # Birthday does not establish desired start or enrollment.
        if metadata(r)['task'] == 'timing' or self.value(g, 'situation.age65'):
            for item in candidates:
                if item['id'] == 'T05': item['priority'] = 0
        readiness = plan_readiness(g, r)
        if readiness['active']:
            needed = self.plan_questions(g, r, readiness)
            if readiness['canReview']:
                return []
            # Preserve consequential timing/lookup/learning alternatives. The
            # minimum is a closing condition, not a replacement dialogue script.
            seen = {item['id'] for item in needed}
            return (needed + [item for item in candidates if item['id'] not in seen])[:12]
        # Eligibility is policy-neutral. The decision brief and its ranking are
        # applied only inside an explicitly permitted v3 composition below.
        return sorted(candidates, key=lambda item: item['priority'])[:12]

    def decision_candidates(self, owner, g, r, candidates, education_request=None):
        """Decision-sized guidance from existing state, not another intake gate."""
        brief = self.memory.brief(owner, self.current_chain.get(owner), CONTEXT_POLICY)
        dispositions = dict(metadata(r).get('baselineDispositions', {}))
        for identifier, item in r.get('dispositions', {}).items():
            state = item.get('state')
            if state in {'explicit_unknown', 'deferred'}:
                dispositions[identifier] = 'unknown' if state == 'explicit_unknown' else state
        for item in candidates:
            if item.get('required'):
                dispositions[item['question']['id']] = 'conflicting'
        return guidance(candidates, task=metadata(r)['task'],
            concerns=ensure_state(r).get('agenda', {}).get('concerns', []),
            age65=bool(self.value(g, 'situation.age65')), dispositions=dispositions,
            pending_question=brief.get('pending_question'), education_request=education_request)

    def context(self, g, r, policy=None, current=None):
        task = metadata(r)['task']
        active = None if current and current['id'] not in Q else current
        context = build_context(g, r, task, active_question=active,
                                consent_version=LEGACY_CONTEXT_POLICY if policy in {CONTEXT_POLICY, PREVIOUS_CONTEXT_POLICY} else policy)
        identifier = (current or {}).get('id', '').split('.')[0]
        if (policy == CONTEXT_POLICY and task != 'timing'
                and (identifier in TIMING_CONTEXT_TARGETS or identifier == 'T02')):
            capability = build_context(g, r, 'timing', active_question=active,
                                       consent_version=LEGACY_CONTEXT_POLICY)
            extra = capability['reports']
            if identifier != 'RC05' and task not in {'timing', 'medigap'}:
                # General orientation/current insurance needs circumstances,
                # not an unrelated saved precise Part-B effective date.
                extra = [item for item in extra if not item['id'].startswith('readiness.RC05.')]
            if identifier == 'T02':
                # A familiarity question can connect to the life circumstances
                # just reported; it does not need every prior enrollment date.
                extra = [item for item in extra if item['id'] in FAMILIARITY_CONTEXT_REFS]
            reports = {item['id']:item for item in context['reports']}
            reports.update({item['id']:item for item in extra})
            context['reports'] = list(reports.values())
            context['known'] = [item for item in context['known'] if item['id'] not in reports]
        if policy in {CONTEXT_POLICY, PREVIOUS_CONTEXT_POLICY}:
            capabilities={'T06':'providers','RC21':'providers','T07':'drug_coverage','RC22':'drug_coverage',
                'RC23':'drug_pricing','T09':'costs','T10':'costs',
                **{key:'medigap' for key in medigap_profile.FIELDS}}
            capability=capabilities.get(identifier)
            if capability and capability!=task:
                extra=build_context(g,r,capability,active_question=active,consent_version=LEGACY_CONTEXT_POLICY)
                reports={item['id']:item for item in context['reports']}
                reports.update({item['id']:item for item in extra['reports']})
                context['reports']=list(reports.values());context['known']=[x for x in context['known'] if x['id'] not in reports]
            agenda=agenda_context(g,r,task,current)
            if agenda:context['agenda']=agenda
            if (identifier=='T10' or task in {'compare','review'}) and 'other' in (self.value(g,'needs.priorities') or []):
                other=g['fields'].get('needs.priorityOther')
                if other and other.get('status')=='reported':
                    context['reports'].append({'id':'guide.needs.priorityOther','status':'reported',
                        'value':copy.deepcopy(other['value']),'provenance':{'method':'direct_report','revision':other['revision']}})
                    context['known']=[x for x in context['known'] if x['id']!='guide.needs.priorityOther']
        if policy == CONTEXT_POLICY and any(item['topic'] == 'timing' and item['status'] == 'open'
                for item in r.get('natural', {}).get('agenda', {}).get('concerns', [])):
            timing = build_context(g, r, 'timing', consent_version=LEGACY_CONTEXT_POLICY)
            prefixes = ('readiness.RC04.', 'readiness.RC06.', 'readiness.RC09.', 'readiness.RC11.')
            core = {'guide.situation.age65', 'guide.situation.retirement', 'guide.coverage.current',
                    'guide.coverage.requestedStart','guide.coverage.requestedStartMonth'}
            reports = {item['id']: item for item in context['reports']}
            reports.update({item['id']: item for item in timing['reports'] if item['id'] in core or item['id'].startswith(prefixes)})
            context['reports'] = list(reports.values())
            context['known'] = [item for item in context['known'] if item['id'] not in reports]
        if policy == CONTEXT_POLICY and set(self.value(g, 'coverage.current') or []) & {'employer', 'retiree', 'cobra'}:
            # Worker relationship qualifies the always-available current
            # insurance report; it is not an unrelated historical detail.
            timing = build_context(g, r, 'timing', consent_version=LEGACY_CONTEXT_POLICY)
            reports = {item['id']: item for item in context['reports']}
            reports.update({item['id']: item for item in timing['reports'] if item['id'].startswith('readiness.RC09.')})
            context['reports'] = list(reports.values())
            context['known'] = [item for item in context['known'] if item['id'] not in reports]
        if policy == CONTEXT_POLICY and (task == 'medigap' or identifier in medigap_profile.FIELDS):
            pricing = medigap_profile.profile(g)
            context['medigap_pricing_scope'] = {
                'effective_date': medigap_profile.DATE, 'ages': '65–74', 'zips': '34101–34108',
                'status': pricing['status'], 'message': pricing['message'], 'missing': pricing['missing'],
                'purpose': 'The Medigap tab automatically shows dated source prices when these reported details are complete. This is not eligibility or a guaranteed quote. Never invent rates.'}
        if policy == CONTEXT_POLICY:
            context['plans_pages'] = self.plans_pages(g, r)
            if getattr(self, 'conversation_checks', None):
                context['conversation_checks'] = self.conversation_checks.context()
        return context

    PLANS_PAGE_LABELS = {'RC01': 'who the coverage is for', 'T03': 'home ZIP code', 'RC02': 'county',
                         'RC03': 'coverage year', 'MG_AGE': 'age', 'MG_SEX': 'sex (Female or Male)',
                         'MG_TOBACCO': 'tobacco use'}

    def plans_pages(self, g, r):
        """D138: what the Plans page can show for this profile right now.

        Status only. No rate, plan name or count enters model context (D129);
        the tabs remain the place where listed amounts are read.
        """
        def page(view, tab, shows):
            return {'tab': tab, 'shows': shows, 'status': view['status'], 'message': view.get('message', ''),
                    'note': view.get('note', ''),
                    'still_needed': [self.PLANS_PAGE_LABELS.get(key, key) for key in view['missing']]}
        return {
            'medigap': page(medigap_profile.profile(g), 'Medicare Supplement (Medigap)',
                            'listed Medigap premiums for the reported ZIP, age, sex category and tobacco category; '
                            'the list covers ages 65–74 (age 64 is shown age-65 prices) in ZIPs 34101–34108, dated November 10, 2026'),
            'part_d': page(part_d_profile.profile(g, r), 'Part D drug plans',
                           'published 2026 stand-alone Part D plans for Collier County with premiums and deductibles'),
            'purpose': ('What the Plans page can show for this person right now. ready: that tab is showing the '
                        'listed information now; say so, name the tab, and never say prices or plan listings are '
                        'unavailable. missing: name the still_needed details that unlock it. unsupported: relay '
                        'message. Listed amounts and plan names are read on the tab; never state or invent them.')}

    def permitted_question(self, question, policy):
        if not question or policy in {CONTEXT_POLICY,PREVIOUS_CONTEXT_POLICY,LEGACY_CONTEXT_POLICY}:return copy.deepcopy(question)
        # Generated/derived question labels may echo an earlier private value.
        # Old consent covers only the public meaning, not that echoed value.
        return self.question(question['id'], [f['key'] for f in question.get('fields',[])] or None,
                             question.get('entity','profile'))

    @staticmethod
    def capture_values(g, r):
        """Compare committed meaning/status, excluding revision bookkeeping."""
        return ({key: (copy.deepcopy(item.get('value')), item.get('status')) for key, item in g['fields'].items()},
                {key: (copy.deepcopy(item.get('value')), item.get('stale', False)) for key, item in r['facts'].items()})

    @staticmethod
    def report_delta(before_g, before_r, g, r, updates=()):
        """New/reaffirmed validated reports must survive the next-question lens.

        Values come from resolved server records, not the extraction proposal.
        This is current-message context under v3, never expanded saved history.
        """
        def reports(guide, record):
            result = {}
            for capability in ('compare', 'timing', 'providers', 'drug_coverage', 'drug_pricing', 'medigap', 'costs', 'snp'):
                result.update({item['id']: item for item in build_context(guide, record, capability,
                    consent_version=LEGACY_CONTEXT_POLICY)['reports']})
            return result
        before, after = reports(before_g, before_r), reports(g, r)
        fresh = set()
        for update in updates:
            identifier = update['id']
            # A relational report needs its established subject/coverage
            # relationship, even after a different next question was chosen.
            if identifier in {'RC11', 'RC10', 'RC12', 'RC13'}:
                fresh.update(ref for ref in after if ref.startswith('readiness.RC09.') or ref == 'guide.coverage.current')
            if identifier == 'RC05':
                fresh.update(ref for ref in after if ref.startswith('readiness.RC04.'))
            if identifier == 'RC23':
                entity = update.get('entity', 'profile')
                fresh.update(ref for ref in after if ref.startswith('readiness.RC22.' + entity + '.'))
            if identifier in FIELD:
                fresh.add('guide.' + FIELD[identifier])
            elif identifier in {'S_AGE65', 'S_RETIREMENT'}:
                fresh.add('guide.' + SITUATION_FIELDS[identifier[2:].lower()])
            elif identifier.startswith('RC') and update.get('entity', 'profile') != 'new':
                entity = update.get('entity') or 'profile'
                fresh.update(ref for ref in after if ref.startswith('readiness.' + identifier + '.' + entity + '.'))
        return [item for ref, item in after.items()
                if (before.get(ref) != item or ref in fresh)
                and item.get('status') not in {'unknown', 'deferred', 'stale', 'tentative', 'conflicting'}]

    @staticmethod
    def resolved_changes(before_g, before_r, reports):
        changes = []
        for report in reports:
            identifier = report['id']
            if identifier.startswith('guide.'):
                previous = before_g.get('fields', {}).get(identifier[6:], {})
                if previous.get('status') not in {'reported', 'derived'}:
                    continue
                old = previous.get('value')
            else:
                parts = identifier.split('.')
                if len(parts) != 4:
                    continue
                _, question, entity, field = parts
                previous = before_r.get('facts', {}).get(question, {})
                if previous.get('stale'):
                    continue
                values = previous.get('value', {})
                item = values if entity == 'profile' else next((item for item in values.get('items', []) if item.get('entity') == entity), {})
                old = item.get(field)
            if old is not None and old != report['value']:
                changes.append({'report_id': identifier, 'previous_value': copy.deepcopy(old),
                    'current_value': copy.deepcopy(report['value']), 'status': 'superseded'})
        return changes[:12]

    def advisor_brief(self, owner, g, r, policy, candidates, goal=None, education_request=None):
        brief = self.memory.brief(owner, self.current_chain.get(owner), policy)
        if goal and len(goal) <= 200:
            brief['goal'] = goal
        eligible_ids = {item['question']['id'] for item in candidates}
        if brief.get('pending_question') not in eligible_ids:
            brief.pop('pending_question', None)
        brief['direction'] = 'Help this person understand their coverage options and reach an informed decision.'
        brief['reported_goal'] = self.value(g, 'intent.goal')
        brief['research_only'] = self.report(r, 'RC01').get('choice') == 'research'
        brief['explained_topics'] = ensure_state(r)['dialogue']['explainedTopics'][-8:]
        brief['familiarity'] = {'explicit_report': self.value(g, 'knowledge.general'),
            'calibration': 'Use topic-specific questions and dialogue tentatively; exposure is not comprehension.'}
        if policy == CONTEXT_POLICY:
            brief['decision'] = self.decision_candidates(owner, g, r, candidates, education_request)[1]
        return brief

    CONTINUATION_QUESTION = 'What would you like to understand next?'

    # Short typed answers that name a choice of the question on screen. The
    # model's interpretation keeps missing one-word replies that match a chip
    # ("Neither.", "Mine.", "Medicare. An HMO with drugs.") while the prose
    # claims they were noted (P01, P05, P07, Nov 8–9, 2026). This is exact
    # label/synonym matching of the first short segment, never inference.
    DIRECT_CHOICE_SYNONYMS = {
        'T02': {'new': 'new', 'new to medicare': 'new', 'brand new': 'new', 'a little': 'some', 'know a little': 'some',
                'some': 'some', 'a bit': 'some', 'comfortable': 'comfortable', 'comfortable with the basics': 'comfortable',
                'pretty comfortable': 'comfortable'},
        'T04': {'as soon as possible': 'soonest', 'soonest': 'soonest', 'asap': 'soonest', 'right away': 'soonest',
                'after my current coverage ends': 'after_coverage', 'after my coverage ends': 'after_coverage',
                'when my coverage ends': 'after_coverage', 'when my insurance ends': 'after_coverage',
                'already': 'already', 'i already have medicare': 'already', 'already have medicare': 'already',
                'i already have it': 'already'},
        'T05': {'medicare advantage': 'advantage', 'advantage': 'advantage', 'an hmo': 'advantage', 'hmo': 'advantage',
                'an hmo with drugs': 'advantage', 'a ppo': 'advantage', 'ppo': 'advantage', 'original medicare': 'original',
                'original': 'original', 'through a current job': 'employer', 'current job': 'employer', 'my job': 'employer',
                'work insurance': 'employer', 'job insurance': 'employer', 'employer insurance': 'employer',
                'regular employee insurance': 'employer', 'from a former job': 'retiree', 'retiree coverage': 'retiree',
                'retiree': 'retiree', 'cobra': 'cobra', 'medicaid': 'medicaid', 'no health insurance': 'none',
                'none': 'none', 'nothing': 'none', 'medigap': 'medigap', 'a supplement': 'medigap', 'supplement': 'medigap',
                'my supplement': 'medigap', 'plan g': 'medigap', 'plan n': 'medigap', 'plan f': 'medigap', 'medigap plan g': 'medigap',
                'medigap plan n': 'medigap', 'a separate prescription plan': 'drug', 'separate prescription plan': 'drug',
                'a separate drug plan': 'drug', 'separate drug plan': 'drug', 'a prescription plan': 'drug', 'prescription plan': 'drug',
                'a drug plan': 'drug', 'drug plan': 'drug', 'part d': 'drug', 'a part d plan': 'drug', 'part d plan': 'drug',
                'medicare advantage with drugs': 'advantage', 'an advantage plan': 'advantage',
                'va': 'military', 'tricare': 'military',
                # Part A alone is Original Medicare; the parts held are RC04.
                'regular medicare': 'original', 'parts a and b': 'original', 'part a and part b': 'original',
                'medicare parts a and b': 'original', 'part a only': 'original', 'medicare part a only': 'original',
                'i have medicare part a only': 'original', 'i have part a only': 'original', 'only part a': 'original',
                'part a': 'original', 'medicare part a': 'original', 'part a only (no part b yet)': 'original'},
        'T08': {'local': 'local', 'local only': 'local', 'near home': 'local', 'only near home': 'local', 'home only': 'local',
                'elsewhere in the u.s.': 'elsewhere_us', 'elsewhere in the us': 'elsewhere_us', 'other states': 'elsewhere_us',
                'outside the u.s.': 'outside_us', 'outside the us': 'outside_us', 'abroad': 'outside_us'},
        'T09': {'predictable': 'predictable', 'more predictable': 'predictable', 'more predictable costs': 'predictable',
                'predictable costs': 'predictable', 'predictable bills': 'predictable', 'lower monthly': 'lower_monthly',
                'lower monthly payments': 'lower_monthly', 'lower premium': 'lower_monthly', 'lower premiums': 'lower_monthly',
                'no preference': 'no_preference', 'no preference yet': 'no_preference'},
        'T10': {'doctors': 'doctors', 'my doctor': 'doctors', 'my doctors': 'doctors', 'keeping my doctor': 'doctors',
                'keeping my doctors': 'doctors', 'doctors and hospitals': 'doctors', 'prescriptions': 'drugs', 'drugs': 'drugs',
                'medicines': 'drugs', 'my prescriptions': 'drugs', 'total cost': 'total_cost', 'cost': 'total_cost',
                'costs': 'total_cost', 'predictable costs': 'bills', 'predictable': 'bills', 'predictable bills': 'bills',
                'travel': 'travel'},
        'RC04': {'neither': 'neither', 'none': 'neither', 'no medicare': 'neither', 'nothing yet': 'neither', 'not yet': 'neither',
                 'both': 'both', 'a and b': 'both', 'parts a and b': 'both', 'a & b': 'both', 'part a and part b': 'both',
                 'a only': 'a_only', 'part a only': 'a_only', 'just a': 'a_only', 'just part a': 'a_only',
                 'b only': 'b_only', 'part b only': 'b_only', 'applied': 'pending', 'waiting': 'pending', 'applied; waiting': 'pending',
                 'pending': 'pending'},
        'RC09': {'mine': 'my_job', 'me': 'my_job', 'my job': 'my_job', 'my current job': 'my_job', 'my work': 'my_job',
                 'my employer': 'my_job', 'my own job': 'my_job', 'my own': 'my_job', 'spouse': 'spouse_job',
                 "my husband's": 'spouse_job', "my wife's": 'spouse_job', "my spouse's": 'spouse_job', "my husband's job": 'spouse_job',
                 "my wife's job": 'spouse_job', "my spouse's job": 'spouse_job', "husband's job": 'spouse_job', "wife's job": 'spouse_job',
                 "spouse's current job": 'spouse_job', 'his job': 'spouse_job', 'her job': 'spouse_job', 'cobra': 'cobra',
                 'retiree': 'retiree', 'retiree coverage': 'retiree', 'former job': 'retiree', 'from a former job': 'retiree',
                 "my parent's job": 'family_job', "my mother's job": 'family_job', "my father's job": 'family_job'},
        'RC10': {'yes': 'yes', '20 or more': 'yes', 'more than 20': 'yes', 'over 20': 'yes', 'at least 20': 'yes',
                 'no': 'no', 'fewer than 20': 'no', 'under 20': 'no', 'less than 20': 'no', "i'm not sure": 'unknown',
                 'not sure': 'unknown'},
        'RC14': {'yes': 'yes', 'no': 'no', 'no hsa': 'no', 'yes, an hsa': 'yes'},
    }

    PART_STATUS_PHRASES = (
        ('a_only', re.compile(r"(?i)\b(?:part a only|only (?:have |has |got |on )?part a\b|just part a\b|part a(?:,| but| and)? (?:not|no|without|never) (?:part )?b\b|"
                               r"(?:never|haven['\u2019]t|have not|didn['\u2019]t|did not|not yet|still haven['\u2019]t) (?:signed up for|enrolled in|taken|gotten|added|started|picked up) part b\b|"
                               r"missed (?:signing up for |enrolling in |my window for )?part b\b|no part b\b|without part b\b|(?:skipped|declined|turned down|delayed|put off) part b\b)")),
        ('both', re.compile(r"(?i)\b(?:have|has|got|on|with|enrolled in|carry|hold) (?:medicare )?(?:both )?parts? a and (?:part )?b\b|\bboth parts? a and b\b")),
    )

    def part_status_report(self, message, updates, record):
        """The parts a person says they hold, read from their own explicit words.

        "Part A only" or "never signed up for Part B" is a statement about
        actual Medicare enrollment (RC04), not a conclusion. It applies only to
        the beneficiary's own sentence; a sentence about a spouse or parent is
        left to the extractor. Nothing here decides eligibility or dates.
        """
        if not isinstance(message, str) or any(u.get('id') == 'RC04' for u in updates):
            return None
        sentences = [part.strip() for part in re.split(r'(?<=[.!?])\s+|\n', message.strip()) if part.strip()]
        for sentence in sentences:
            if re.search(r"(?i)\b(?:my|his|her|their) (?:husband|wife|spouse|mother|father|mom|dad|parent|partner|sister|brother)\b", sentence):
                continue
            if re.search(r"(?i)\b(?:if|suppose|hypothetically|for example|I think|maybe|might|probably|not sure|I guess)\b|\?", sentence):
                continue
            for value, pattern in self.PART_STATUS_PHRASES:
                match = pattern.search(sentence)
                if match:
                    return {'id': 'RC04', 'entity': 'profile', 'fields': {'choice': value}, 'quote': match.group(0),
                            'scope': 'current', 'subject': 'beneficiary', 'uncertain': False, 'correction': False,
                            'direct_choice': True}
        return None

    def part_a_coverage_answer(self, message, current, updates, record):
        """'Just Part A' answers the coverage question once the parts are known.

        Part A alone is not a T05 answer value, so the model kept re-asking
        (S4, Nov 9, 2026: asked four times). When RC04 already records the
        parts held and the person says that is all they have, current coverage
        is Original Medicare. Any other coverage named in the message is left
        to the extractor.
        """
        if (not isinstance(current, dict) or current.get('id') != 'T05' or not isinstance(message, str)
                or len(message) > 160 or any(u.get('id') == 'T05' for u in updates)):
            return None
        parts = self.report(record, 'RC04').get('choice')
        if parts not in {'a_only', 'both'} and not any(u.get('id') == 'RC04' and u.get('fields', {}).get('choice') in {'a_only', 'both'} for u in updates):
            return None
        if re.search(r"(?i)\b(?:job|employer|work|retiree|cobra|va\b|tricare|military|medicaid|advantage|supplement|medigap|drug plan|part d|hmo|ppo)", message) or '?' in message:
            return None
        match = re.search(r"(?i)\b(?:(?:just|only)\s+(?:medicare\s+)?parts?\s+a(?:\s+and\s+b)?\b|parts?\s+a(?:\s+and\s+b)?\s+only\b|nothing else|no other (?:insurance|coverage)|that(?:'|\u2019)?s (?:all|it)\b|still just (?:that|those))", message)
        if not match:
            return None
        return {'id': 'T05', 'entity': 'profile', 'fields': {'choice': 'original'}, 'quote': match.group(0),
                'scope': 'current', 'subject': 'beneficiary', 'uncertain': False, 'correction': False, 'direct_choice': True}

    def direct_choices(self, message, current, updates):
        """Server-recognised choice answers for the question on screen (exact text only)."""
        if not isinstance(current, dict) or not isinstance(message, str):
            return []
        identifier = current.get('id')
        synonyms = self.DIRECT_CHOICE_SYNONYMS.get(identifier)
        if not synonyms or any(u.get('id') == identifier for u in updates):
            return []
        labels = {str(label).casefold(): value for value, label in (current.get('choices') or []) if isinstance(value, str)}
        valid = {value for value, _ in (current.get('choices') or [])} or set(synonyms.values())
        segments = [part.strip() for part in re.split(r'(?<=[.!?])\s+|\n', message.strip()) if part.strip()]
        if not segments:
            return []
        # Current coverage is often the second sentence after age/ZIP ("I'm 73,
        # in 34102. Original Medicare, Plan G, and a separate prescription plan.").
        candidates = [seg for seg in segments[:3] if len(seg) <= 90] if identifier == 'T05' else segments[:1]
        segment = candidates[0] if candidates else ''
        if not segment or (identifier != 'T05' and len(segment) > 60):
            return []
        parts = [segment]
        if identifier in {'T10', 'T05'}:
            parts = [part for seg in candidates for part in re.split(r'\s*(?:,|;|\band\b|\bthen\b|\bplus\b)\s*', seg) if part]
        found = []
        for part in parts:
            text = re.sub(r"^(?:it's|its|it is|that's|that is|the|just|only|probably|definitely)\s+", '', part.casefold().replace('’', "'")).strip(' .!?,;:')
            value = labels.get(text) or synonyms.get(text)
            if value is None and identifier == 'RC10':
                number = re.fullmatch(r'(?:about |around |roughly |maybe )?(\d{1,6})(?: people| employees| staff| workers)?', text)
                if number:
                    value = 'yes' if int(number.group(1)) >= 20 else 'no'
            if value in valid and value not in [item['fields']['choice'] for item in found]:
                scope = 'intended' if identifier == 'T04' and value in {'soonest', 'after_coverage'} else 'current'
                found.append({'id': identifier, 'entity': 'profile', 'fields': {'choice': value}, 'quote': part.strip(),
                              'scope': scope, 'subject': 'learner' if identifier in {'T01', 'T02'} else 'beneficiary',
                              'uncertain': False, 'correction': False, 'direct_choice': True})
        if identifier not in {'T10', 'T05'} and len(found) > 1:
            return []
        return found

    PLANS_LIST_FIELDS = {'medicines': ('needs.medicinesStatus', 'needs.medications'),
                         'doctors': ('needs.providersStatus', 'needs.providers')}

    def plans_lists(self, g):
        out = {}
        for kind, (status_path, list_path) in self.PLANS_LIST_FIELDS.items():
            out[kind] = list_items(self.value(g, list_path), kind == 'doctors') if self.value(g, status_path) in {'yes', 'list'} else []
        return out

    def note_plans_entry(self, owner, chain, before, g, action):
        """Accumulate a Plans-page entry for one later acknowledgement.

        Net changes only: removing and re-adding a name in two saves (the
        Remove control) is not reported as an addition.
        """
        after = self.plans_lists(g)
        entry = self.plans_additions.setdefault((owner, chain), {'medicines': [], 'doctors': [], 'removed': [], 'other': [], 'none': []})
        for kind in ('medicines', 'doctors'):
            old = {x.casefold(): x for x in before.get(kind, [])}
            new = {x.casefold(): x for x in after.get(kind, [])}
            for key, name in new.items():
                if key in old:
                    continue
                gone = [x for x in entry['removed'] if x.casefold() == key]
                if gone:
                    entry['removed'] = [x for x in entry['removed'] if x.casefold() != key]
                elif key not in {x.casefold() for x in entry[kind]}:
                    entry[kind].append(name)
            for key, name in old.items():
                if key in new:
                    continue
                if key in {x.casefold() for x in entry[kind]}:
                    entry[kind] = [x for x in entry[kind] if x.casefold() != key]
                elif key not in {x.casefold() for x in entry['removed']}:
                    entry['removed'].append(name)
        identifier = action.get('id')
        fields = action.get('fields') or {}
        if identifier in {'T06', 'T07'} and fields.get('choice') in {'none', 'no'} and not after['doctors' if identifier == 'T06' else 'medicines']:
            label = 'no doctors to check' if identifier == 'T06' else 'no prescriptions'
            if label not in entry['none']:
                entry['none'].append(label)
        elif identifier not in {'T06', 'T07'} and identifier in Q:
            choices = dict(Q[identifier].get('choices') or [])
            if identifier == 'T03' and fields.get('zip'):
                label = 'ZIP code ' + str(fields['zip'])
            else:
                values = [v for v in str(fields.get('choice', '')).split(',') if v]
                words = [str(choices.get(v, v)) for v in values]
                label = (Q[identifier].get('label') or Q[identifier].get('question') or identifier).rstrip('?')
                label = '%s: %s' % (label, ', '.join(words)) if words else ''
            if label:
                entry['other'] = [x for x in entry['other'] if x.split(':')[0] != label.split(':')[0]] + [label]
        if not any(entry.values()):
            self.plans_additions.pop((owner, chain), None)

    def plans_entry_context(self, owner, g):
        entry = self.plans_additions.get((owner, self.current_chain.get(owner)))
        if not entry or not any(entry.values()):
            return None
        lists = self.plans_lists(g)
        return {'medicines_added': list(entry['medicines']), 'doctors_added': list(entry['doctors']),
                'removed': list(entry['removed']), 'marked_none': list(entry['none']), 'other_changes': list(entry['other']),
                'current_medicines': lists['medicines'], 'current_doctors': lists['doctors'],
                'how_to_use': ('The person entered these on the Plans page. They are the person\'s own reports: take them as given and '
                               'do not ask whether they are right. In this reply, acknowledge them once by name in one short clause '
                               '("I see you added Eliquis and metformin on the Plans page"), then answer what the person asked. '
                               'If medicines or doctors were added and no other question is required, ask whether there are any others '
                               'to include as your question.')}

    @staticmethod
    def _join_names(names):
        names = list(names)
        return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]

    def plans_acknowledgement(self, entry, reply):
        """One deterministic sentence in the person's own entered words, used only
        when the composed reply did not already mention what they entered."""
        if not entry:
            return ''
        added = [*entry['medicines_added'], *entry['doctors_added']]
        text = (reply or '').casefold()
        if added and any(name.casefold() in text for name in added):
            return ''
        if not added and entry['removed'] and any(name.casefold() in text for name in entry['removed']):
            return ''
        if added:
            others = ('medicines or doctors' if entry['medicines_added'] and entry['doctors_added']
                      else 'medicines' if entry['medicines_added'] else 'doctors')
            return ('I see you added %s on the Plans page, and I’ve included %s. Tell me if there are any other %s to include.'
                    % (self._join_names(added), 'them' if len(added) > 1 else 'it', others))
        if entry['removed']:
            return 'I see you removed %s on the Plans page.' % self._join_names(entry['removed'])
        if entry['marked_none']:
            return 'I see you noted %s on the Plans page.' % self._join_names(entry['marked_none'])
        if entry['other_changes'] and not any(change.split(':')[-1].strip().casefold() in text for change in entry['other_changes']):
            return 'I see you updated your details on the Plans page (%s).' % '; '.join(entry['other_changes'])
        return ''

    def recovery_statement(self, rules, context, question, required_reason=None):
        """One reviewed general statement, never a personal finding or new prose.

        Only a rule the reports actually support may stand alone here: the rule
        the required question is confirming, then a met rule. A rule the reports
        show does not apply (``status`` 'not_met') is never the floor, because
        read on its own the general sentence sounds like reassurance (P08,
        November 9, 2026). Calendar rules are not a substitute for an answer.
        """
        key = (context.get('_owner'), self.current_chain.get(context.get('_owner'))) if context.get('_owner') else None
        previous = self.last_floor.get(key) if key else None
        def chosen(text):
            if key:
                self.last_floor[key] = text
            return text
        rule = floor_statement(rules, required_reason)
        if rule:
            text = rule.get('floor_text') or (self.facts.get(rule['fact_id']) or {}).get('summary')
            if text and text != previous:
                return chosen(text)
        excluded = {rule['fact_id'] for rule in rules if rule.get('status') == 'not_met'} | {'annual_enrollment'}
        if not context.get('_person_asked'):
            # General background is a fair floor for an intake turn, never a
            # stand-in answer to a question the person asked (S2, Nov 9, 2026).
            for item in context.get('evidence', []):
                if (isinstance(item, dict) and item.get('summary') and item.get('id') in self.facts
                        and item.get('id') not in excluded and item['summary'] != previous):
                    return chosen(item['summary'])
        if context.get('_person_asked'):
            return chosen('I don’t have a checked answer to that question here yet, so I won’t guess.')
        if question:
            return chosen('Let’s keep going with the next useful detail.')
        return chosen('Let’s keep going. You can ask me anything about your coverage.')

    @staticmethod
    def continuation_question(moves, previous_id=None):
        """Only actual clarification or an unresolved question already asked."""
        required = next((item for item in moves if item.get('required')), None)
        previous = next((item for item in moves if item['id'] == previous_id), None)
        selected = required or previous
        return copy.deepcopy(selected['question']) if selected else None

    def compose_response(self, owner, out, message, moves, policy, request_id, reservation, previous_dialogue=None,
                         submitted_answer=None, goal=None, priority_changed=False, accepted_reports=(), resolved_changes=(),
                         education_request=None, learner_observations=(), capture_outcomes=(), answer_context=None):
        if policy == CONTEXT_POLICY:
            # D157: intent and an explicit path choice are read from the person's
            # own words before the reply is composed; the order follows.
            ux_flow.note_message(self, owner, out['guide'], message, submitted_answer, out['record'])
            moves = ux_flow.refine(self, owner, out['guide'], out['record'], moves)
        learning = self.memory.education(owner, self.current_chain.get(owner), policy)
        retrieval_started = time.monotonic()
        # Only current explicit explanation requests can authorize a revisit.
        # Generic evidence made available below and an ordinary button answer
        # do not constitute such a request.
        requested_refs = [fact['id'] for fact in out.get('facts', []) if fact.get('id') in self.facts]
        education_request = education_request or {}
        known_concepts = {item['concept_id'] for item in catalog_context()['concepts']}
        request_quote = education_request.get('quote', '')
        revisit_concepts = [identifier for identifier in education_request.get('concept_ids', [])
                            if isinstance(identifier, str) and identifier in known_concepts]
        requested_revisit = bool(submitted_answer is None
            and education_request.get('kind') in {'explain', 'clarify', 'revisit'}
            and isinstance(request_quote, str) and request_quote.strip()
            and request_quote.casefold() in message.casefold() and revisit_concepts)
        if not requested_revisit: revisit_concepts = []
        checked_request = ({'kind': education_request['kind'], 'concept_ids': revisit_concepts}
                           if requested_revisit else None)
        stop_questions = bool(submitted_answer is None and re.search(
            r'(?i)(?:^|[.!?]\s+)(?:please\s+)?no more questions[.!]?\s*$', message))
        # A pause is the person's to call, in their own words. "Just say yes or
        # no" or "one word" is a request for brevity, not a stop; the model may
        # not end the turn without a question on that basis (P05, Nov 9, 2026).
        pause_allowed = bool(submitted_answer is None and re.search(
            r"(?i)\b(?:no more questions|stop (?:asking|the questions|here|for (?:now|today))|pause|that(?:'s| is) (?:all|enough|it) for (?:now|today)|"
            r"(?:i'm|i am|we're|we are) done|enough for (?:now|today)|let's stop|leave it (?:here|there)|talk (?:later|tomorrow)|"
            r"come back (?:later|tomorrow|another (?:day|time))|good(?:bye|night)|bye for now|don't ask (?:me )?(?:any ?more|another)|"
            r"no (?:more|further) questions)\b", message))
        if conversation_planner.enabled(self) and conversation_planner.state(self, owner).get('finish_requested'):
            pause_allowed = True
        observations = learner_state.observations(learner_observations, message) if policy == CONTEXT_POLICY else []
        learner = learner_state.merge(self.memory.learner(owner, self.current_chain.get(owner), policy), observations)
        open_concepts = [item['concept_id'] for item in learner['observations']
                         if item['signal'] in {'uncertain', 'misconception'}]
        # A failed generation has not chosen a new conversational direction.
        # Preserve an unresolved question already asked, or an actual required
        # clarification; never substitute the next optional profile field.
        pending_id = (previous_dialogue or {}).get('lastTarget') or {}
        pending_id = pending_id.get('id') if isinstance(pending_id, dict) else None
        rules, required_id, required_reason = [], None, None
        if policy == CONTEXT_POLICY:
            pending_id = self.memory.brief(
                owner, self.current_chain.get(owner), policy).get('pending_question') or pending_id
            moves, decision = self.decision_candidates(owner, out['guide'], out['record'], moves, checked_request)
            # Redirect, don't deflect (owner direction, November 8, 2026): select
            # the general rules the resolved reports make relevant, and the one
            # approved question the reply must ask. Reports only; no message text.
            brief = self.memory.brief(owner, self.current_chain.get(owner), policy)
            # The extractor's one-line summary of the person's concern (model-
            # derived, never raw text) lets cost pressure select the assistance
            # rules from the first turn (P13, Nov 9, 2026).
            concern = ' '.join(filter(None, [brief.get('current_concern', ''),
                                              str((out.get('_extraction_agenda') or {}).get('current_concern', ''))]))
            selected_rules = applicable_rules(
                lambda identifier: self.report(out['record'], identifier),
                lambda path: self.value(out['guide'], path),
                focus=decision.get('practical_focus', ''), concern=concern,
                trial_at_first_eligibility=(enrollment_flow.trial_at_first_eligibility(
                    self, out['guide'], out['record']) if enrollment_flow.enabled(self) else None),
                plans_view=bool(self._plans_context.get()))
            rules = []
            for rule in selected_rules:
                if rule['fact_id'] in self.facts:
                    rules.append(rule)
                elif (rule['fact_id'] == 'partb_sep_coverage_ended' and 'working_coverage_sep' in self.facts
                        and rule.get('status') != 'not_met' and not any(item['fact_id'] == 'working_coverage_sep' for item in selected_rules)):
                    # Until the reviewed 8-month-window statement is accepted
                    # (pilot-rules r2), the accepted job-coverage statement still
                    # carries the same window. Never leave the person with
                    # neither (R1, Nov 9, 2026).
                    rules.append({**rule, 'fact_id': 'working_coverage_sep'})
            dispositions = {identifier: item.get('state') for identifier, item in out['record'].get('dispositions', {}).items()}
            dispositions.update(metadata(out['record']).get('baselineDispositions', {}))
            required_id, required_reason = select_required_target(
                moves, moves, pending_id=pending_id, dispositions=dispositions, rules=rules)
        plans_entry = (self.plans_entry_context(owner, out['guide'])
                       if policy == CONTEXT_POLICY and submitted_answer is None else None)
        if plans_entry and (plans_entry['medicines_added'] or plans_entry['doctors_added']) and not self.pending_for(owner):
            identifier = 'T07' if plans_entry['medicines_added'] else 'T06'
            base = self.question(identifier)
            if base:
                names = plans_entry['current_medicines'] if identifier == 'T07' else plans_entry['current_doctors']
                ask = copy.deepcopy(base)
                ask['question'] = ('Besides %s, are there any other %s you’d like included?'
                                   % (self._join_names(names), 'prescriptions' if identifier == 'T07' else 'doctors or hospitals'))
                moves = [item for item in moves if item['id'] != identifier]
                moves.insert(0, {'id': identifier, 'question': ask, 'topic': QUESTION_TOPICS.get(identifier, ''),
                                 'purpose': 'Acknowledge the Plans-page entries and ask whether there are others to include.',
                                 'priority': 0, 'required': False})
        checks = getattr(self, 'conversation_checks', None)
        if (checks and not pause_allowed and not stop_questions and not self.pending_for(owner)
                and (not conversation_planner.enabled(self) or conversation_planner.checks_relevant(self, owner, out['guide']))):
            check_view = checks.reconcile(owner, out['guide'], out['record'])
            check_question = check_view.get('question')
            if check_question:
                identifier = ('RC21' if check_question['kind'] == 'doctor' else
                              'RC22' if check_question['field'] == 'rxcui' else 'RC23')
                question = self.question(identifier)
                # Exact candidate labels and source values stay in the local UI.
                question.update(question=check_question['question'], why=check_question['why'],
                                entity=check_question.get('item') or 'profile')
                moves = [{'id':identifier, 'question':question, 'topic':'doctors' if identifier=='RC21' else 'drugs',
                          'purpose':'Clarify the one missing detail for the local check already underway in this conversation.',
                          'priority':0, 'required':True}]
                required_id, required_reason = identifier, 'current_conversation_check'
        if policy == CONTEXT_POLICY:
            if conversation_planner.enabled(self):
                # The old guidance and check hooks may add candidates. Resolve
                # the discussion once more before assigning the final target.
                moves = conversation_planner.refine(self, owner, out['guide'], out['record'], moves)
            required_id, required_reason = ux_flow.target(self, owner, out['guide'], out['record'], moves,
                                                           required_id, required_reason)
        recovery_question = self.continuation_question(moves, pending_id)
        if recovery_question is None and required_id:
            recovery_question = copy.deepcopy(next(item['question'] for item in moves if item['id'] == required_id))
        context_question = recovery_question
        context = self.context(out['guide'], out['record'], policy, context_question)
        if checks and policy == CONTEXT_POLICY:
            state = checks.visits.get(owner,{})
            context['conversation_checks']['current'] = {
                'pending_detail': (state.get('question') or {}).get('field'),
                'displayed_results': [r['kind'] for r in state.get('results',[])],
                'deferred': bool(state.get('skipped'))}
        context['education_context'] = {
            'catalog': catalog_context(), 'learning': learning_context(learning),
            'requested_revisit': requested_revisit, 'revisit_concepts': revisit_concepts,
            'turn_kind': 'submitted_answer' if submitted_answer is not None else 'message',
            'current_clarification': revisit_concepts if checked_request
                and checked_request['kind'] == 'clarify' else [],
            # The person asked to learn this turn (a question or an explicit
            # explain/clarify request), or has said they want to learn for now.
            'user_requested': (bool(requested_refs) or education_request.get('kind') in {'explain', 'clarify', 'revisit'}
                               or any(item.get('signal') in {'uncertain', 'misconception'} for item in observations)),
            'learning_mode': (self.value(out['guide'], 'intent.goal') == 'learn'
                              or self.report(out['record'], 'RC01').get('choice') == 'research'
                              or bool((goal or '') and re.search(r'(?i)\b(?:just|only) (?:learn|understand|read)', goal or ''))),
        }
        # Relevant reported circumstances remain available when the conversation
        # changes topic. They use existing capability allowlists, never all facts.
        if policy == CONTEXT_POLICY:
            priority = self.context(out['guide'], out['record'], policy, self.question('T10'))
            context['agenda'] = priority.get('agenda', {})
            if priority_changed:
                reports = {item['id']: item for item in context['reports']}
                reports.update({item['id']: item for item in priority['reports'] if item['id'] in {'guide.needs.priorities', 'guide.needs.priorityOther', 'guide.needs.costPreference'}})
                context['reports'] = list(reports.values())
                context['known'] = [item for item in context['known'] if item['id'] not in reports]
            context['resolved_changes'] = copy.deepcopy(list(resolved_changes))
            context['advisor_brief'] = self.advisor_brief(owner, out['guide'], out['record'], policy,
                                                        moves, goal, checked_request)
            context['recent_exchanges'] = self.recent_exchanges(owner, metadata(out['record'])['task'], policy)
            reports = {item['id']: item for item in context['reports']}
            reports.update({item['id']: item for item in accepted_reports})
            context['reports'] = list(reports.values())
            context['known'] = [item for item in context['known'] if item['id'] not in reports]
        if previous_dialogue is not None:
            context['dialogue'] = copy.deepcopy(previous_dialogue)
        moves = [{**item, 'question': self.permitted_question(item.get('question'), policy)} for item in moves]
        context['current_message'] = message
        if policy == CONTEXT_POLICY:
            context['learner_context'] = learner_state.context(learner)
        # The advisor gets relevant reviewed material even when no explicit
        # educational request was classified by the extractor.
        evidence = {fact['id']: fact for fact in out.get('facts', [])}
        ids = [ref for item in catalog_context()['concepts'] if item['concept_id'] in revisit_concepts
               for ref in item['evidence_refs']]
        ids += [ref for item in catalog_context()['concepts'] if item['concept_id'] in open_concepts
                for ref in item['evidence_refs'][:1]]
        if policy == CONTEXT_POLICY:
            # A return to the coverage paths must be able to support the
            # person's still-open access concern. Conversation history is not
            # factual authority. Reattach existing public teaching, within the
            # same six supplemental-source bound, without expanding reports.
            decision = context.get('advisor_brief', {}).get('decision', {})
            if decision.get('practical_focus') in {'doctors', 'travel'}:
                ids += ['original', 'advantage', 'checks']
        ids += self.teaching_candidates(out['guide'], out['record'], context_question)
        ids += ['routesintro', 'basics', 'dates', 'enrollment_intro']
        if rules:
            # Rule statements come first so they survive the six-source bound.
            ids = [rule['fact_id'] for rule in rules] + ids
            if any(rule['rule_id'] == 'medigap_return_underwriting' for rule in rules):
                ids.insert(1, 'medical_limit')
            context['applicable_rules'] = [{**rule, 'statement': self.facts[rule['fact_id']]['summary']} for rule in rules]
        if required_id:
            candidate = next(item for item in moves if item['id'] == required_id)
            context['required_target'] = {'id': required_id, 'reason': required_reason,
                'question': candidate['question'].get('question') if isinstance(candidate.get('question'), dict) else candidate.get('question'),
                'rule': 'Your question must target this meaning unless the person asked to pause. You write the wording.'}
        for identifier in list(dict.fromkeys(ids))[:8]:
            if identifier in self.facts:
                evidence[identifier] = self.facts[identifier]
        # D158: local, exact-reviewed general education. This never creates a
        # report or an applicable rule, and leaves the pinned teaching intact.
        if not os.environ.get('DAYLIGHT_DISABLE_PILOT_KNOWLEDGE'):
            county = self.value(out['guide'], 'comparison.scope.county')
            state = county.get('state') if isinstance(county, dict) else None
            year_report = self.report(out['record'], 'RC03')
            year = year_report.get('year') or 2026
            for fact in self.pilot_knowledge.select(message, state=state, year=year):
                evidence[fact['id']] = fact
        if enrollment_flow.enabled(self):
            for fact in enrollment_flow.extra_evidence(message):
                evidence[fact['id']] = fact
        context['evidence'] = copy.deepcopy(list(evidence.values()))
        timings = getattr(self.agent.local, 'stage_timings', {})
        timings['evidence_retrieval'] = round((time.monotonic() - retrieval_started) * 1000)
        self.agent.local.stage_timings = timings
        knowledge_limits = self.pilot_knowledge.response_limits(message, context['evidence'])
        if knowledge_limits:
            context['knowledge_limits'] = knowledge_limits
            out['knowledgeLimits'] = copy.deepcopy(knowledge_limits)
        pending = self.pending_for(owner)
        context['uncertainties'] = [{'id': pending['update']['id'], 'status': 'needs_clarification'}] if pending else []
        if pending:
            identifier = pending['update']['id']
            prefixes = ['guide.' + FIELD[identifier]] if identifier in FIELD else ['readiness.' + identifier + '.']
            if identifier == 'T03' and set(pending['update'].get('fields', {})) == {'county'}:
                # A county qualification cannot invalidate an independently
                # supplied ZIP. FIELD[T03] maps the baseline ZIP, not county.
                prefixes = ['guide.comparison.scope.county']
            if identifier == 'T04': prefixes.append('guide.coverage.requestedStartMonth')
            if identifier in {'S_AGE65', 'S_RETIREMENT'}:
                prefixes = ['guide.' + SITUATION_FIELDS['age65' if identifier == 'S_AGE65' else 'retirement']]
            affected = [item for item in context['reports'] if any(item['id'].startswith(prefix) for prefix in prefixes)]
            context['reports'] = [item for item in context['reports'] if item not in affected]
            context['known'] += [{'id': item['id'], 'status': 'conflicting'} for item in affected]
        if submitted_answer is not None and policy == CONTEXT_POLICY:
            identifier = submitted_answer['question_id']
            prefix = 'guide.' + FIELD[identifier] if identifier in FIELD else 'readiness.' + identifier + '.'
            refs = [item['id'] for item in context['reports'] if item['id'] == prefix or item['id'].startswith(prefix if prefix.endswith('.') else prefix + '.')]
            context['submitted_answer'] = {**copy.deepcopy(submitted_answer), 'report_refs': refs}
        # This explicit standalone control must survive a failed generation.
        # It changes only asking behavior, never reports or factual authority.
        self.comparisons.attach(out)
        context['comparison_status'] = self.comparisons.context_status(out['comparison'])
        work_before = self.memory.task_work(owner, self.current_chain.get(owner), policy)
        context['task_work'] = task_work_context(context, work_before)
        if policy == CONTEXT_POLICY:
            context['working_assessment'] = working_assessment(context, capture_outcomes, answer_context)
            # Codes only (which report, accepted or not, and why), for the per-turn trace.
            out.setdefault('metrics', {})['capture'] = [
                {key: item.get(key) for key in ('target', 'status', 'reason') if item.get(key) is not None}
                for item in capture_outcomes if isinstance(item, dict)][:24]
            readiness = plan_readiness(out['guide'], out['record'], pending=self.pending_for(owner))
            # Status and meanings only; this adds no personal model values.
            context['plan_review'] = {'can_offer_review': readiness['canReview'],
                'missing': [{k: item[k] for k in ('question_id', 'label', 'state')} for item in readiness['missing']],
                'action': 'review_plans', 'review_is_not_verification': True}
        if plans_entry:
            context['plans_page_additions'] = plans_entry
        floor_keys = {'_owner': owner, '_person_asked': bool(submitted_answer is None and '?' in (message or ''))}
        context['require_followup'] = not stop_questions
        context['pause_allowed'] = pause_allowed or stop_questions
        plans_context = self._plans_context.get()
        if plans_context:
            plans_context = copy.deepcopy(plans_context)
            changed = bool(plans_context['input_digest'] and plans_input_digest(out['guide'], out['record']) != plans_context['input_digest'])
            plans_context['profile_changed'] = changed
            if changed:
                plans_context['recommendation'] = {'state': 'held', 'top_three': [],
                    'priority_order': [], 'reason_codes': ['CONFIRM_CURRENT_PROFILE']}
            context['plans_context'] = plans_context
            context['evidence'].extend(plans_evidence(plans_context))
        out['assessment']['conversationOpen'] = True
        out['assessment']['intakePaused'] = False
        if policy == CONTEXT_POLICY:
            ux_flow.brief(self, owner, out['guide'], out['record'], context, moves, message=message)
        try:
            composed = self.agent.compose(owner, context, moves, request_id, reservation)
            knowledge_receipts = {identifier: evidence[identifier]['knowledge_digest']
                for identifier in composed['evidence_refs']
                if identifier in evidence and evidence[identifier].get('knowledge_digest')}
            if not self.pilot_knowledge.current(knowledge_receipts):
                raise ModelUnavailable('The supporting source needs to be checked again.')
            if knowledge_receipts:
                out['knowledgeReceipts'] = knowledge_receipts
            if stop_questions:
                composed = copy.deepcopy(composed)
                composed.update(question_target=None, question='', education_followups=[])
                composed.setdefault('agenda_update', {})['pause'] = True
                composed['continuation'] = {'assessment': {'goal_progress': 'paused', 'next_move': 'finish'},
                    'delivered': 'answer_only', 'validation_changed_continuation': False}
            target = composed.get('question_target')
            selected = next((item for item in moves if item['question']['id'] == target), None) if target else None
            if target and not selected:
                raise ModelUnavailable('The next question could not be checked.')
            education_output = copy.deepcopy(composed['education'])
            education_output['visual'] = 'none'
            if not composed['reply'].strip():
                # A question, citation or proposed diagram alone is not a
                # delivered explanation. Open clarification may still survive.
                education_output['updates'] = [item for item in education_output['updates']
                    if item['depth'] == 'needs_clarification']
                education_output['visual'] = 'none'
            clarification = (revisit_concepts if requested_revisit
                and education_request.get('kind') == 'clarify' else [])
            clarification = list(dict.fromkeys([*clarification, *open_concepts]))
            planned = plan_update(learning, education_output, composed['evidence_refs'],
                requested_revisit=requested_revisit, revisit_concepts=revisit_concepts,
                clarification_concepts=clarification,
                event_id=request_id)
            # Delivery metadata can be rejected without erasing validated prose.
            # Record only accepted learning updates; response quality is evaluated
            # across conversations, not enforced by deleting a whole answer.
            out['reply'] = composed['reply']
            retained_only = (composed.get('validation_recovery') or {}).get('component') == 'question'
            if not out['reply'].strip() and retained_only and (selected or composed['question']):
                # Prose dropped by validation, question retained: show one
                # reviewed statement (never-blank floor, November 8, 2026). A
                # deliberate question-only reply is left as the model wrote it.
                out['reply'] = self.recovery_statement(rules, {**context, **floor_keys}, composed['question'], required_reason)
                out.setdefault('notice', 'I couldn’t finish that answer. Here is the part I’m sure of.')
            if plans_context:
                out['planEvidence'] = [f for f in plans_evidence(plans_context) if f['id'] in composed['evidence_refs']]
            if selected:
                q = copy.deepcopy(selected['question'])
                q.update(question=composed['question'], why='')
                out['assessment']['nextQuestion'] = q
            else:
                out['assessment']['nextQuestion'] = None
                if composed['question']:
                    out['reply'] = (out['reply'] + '\n\n' + composed['question']).strip()
            out['assessment']['narrative']['opener'] = False
            out['assessment']['intakePaused'] = bool(not selected and moves)
            out['assessment']['conversationOpen'] = bool(not selected and (
                composed['question'] or moves
                or self.report(out['record'], 'RC01').get('choice') == 'research'
                or metadata(out['record'])['task'] == 'learn'))
            ack = self.plans_acknowledgement(plans_entry, out['reply'])
            if ack:
                out['reply'] = (ack + '\n\n' + out['reply']).strip()
            elif (plans_entry and (plans_entry['medicines_added'] or plans_entry['doctors_added']) and target not in {'T06', 'T07'}
                    and not re.search(r'(?i)\bany (?:other|more)\b|\banything else\b|\bothers\b', out['reply'] + ' ' + composed['question'])):
                # The model acknowledged the entries but another question took
                # the turn: keep the owner's "any others?" as one plain sentence.
                kind = ('medicines or doctors' if plans_entry['medicines_added'] and plans_entry['doctors_added']
                        else 'medicines' if plans_entry['medicines_added'] else 'doctors')
                out['reply'] = (out['reply'] + '\n\nTell me if there are any other %s to include.' % kind).strip()
            if plans_entry:
                self.plans_additions.pop((owner, self.current_chain.get(owner)), None)
            out['generated'] = {'status': 'complete', 'move': target or 'answer'}
            out['metrics']['continuation'] = copy.deepcopy(composed.get('continuation'))
            if composed.get('validation_recovery'):
                out['generated']['validation_recovery'] = copy.deepcopy(composed['validation_recovery'])
            used = [identifier for identifier in composed['evidence_refs'] if identifier in evidence]
            taught = list(dict.fromkeys(ref for item in planned['accepted_updates']
                if item['depth'] != 'needs_clarification' for ref in item['evidence_refs']))
            sources = []
            for identifier in used:
                fact = evidence[identifier]
                for source in ([{'url': fact['source'], 'label': 'Medicare.gov: ' + fact['title']}] if fact.get('source') else fact.get('sources', [])):
                    if isinstance(source, dict) and source.get('url') and all(item['url'] != source['url'] for item in sources):
                        sources.append({'url': source['url'], 'label': source.get('label') or source.get('title') or fact['title']})
            kind = 'teach' if taught else 'ask' if selected else 'answer'
            out['advisor'] = {'kind': kind, 'topic': selected.get('topic', '') if selected else FACT_TOPICS.get(used[0], 'learning') if used else '',
                'reason': 'user_question' if requested_refs and used else 'contextual_teaching' if taught else 'missing_dependency',
                'teachingFactIds': taught, 'sources': sources, 'visual': planned['visual'],
                'educationFollowups': list(composed.get('education_followups', []))}
            work_record, work_result = plan_task_work(context, composed.get('task_work'),
                work_before, accepted_teaching=planned['accepted_updates'],
                paused=composed['agenda_update']['pause'])
            out['task_work'] = work_result
            record_advisor_move(out['record'], out['advisor'])
            if taught:
                m = metadata(out['record']); m['lastFactIds'] = taught
                for identifier in taught:
                    if identifier in self.progress_fact_ids and identifier not in m['journey']['learningSeen']: m['journey']['learningSeen'].append(identifier)
                    if identifier not in out['record']['natural']['dialogue']['explainedTopics']:
                        out['record']['natural']['dialogue']['explainedTopics'].append(identifier)
                out['record']['stateVersion'] += 1
            # Source references carry provenance; never render the entire fact
            # a second time beneath a generated educational explanation.
            out['facts'] = []
            working = {'agenda_update': composed.get('agenda_update', {}), 'education_record': planned['record'],
                       'task_work_record': work_record}
            if policy == CONTEXT_POLICY:
                working['learner_record'] = learner
            working['continuation'] = copy.deepcopy(composed.get('continuation'))
            if goal and len(goal) <= 200: working['goal'] = goal
            out['_advisor_memory'] = working
            out['education'] = learning_context(planned['record'])
        except (ModelUnavailable, ProfileError, ValueError) as error:
            out.pop('_advisor_memory', None)
            out.pop('education', None)
            # Never-blank floor (owner exception to D88, November 8, 2026): one
            # reviewed statement for the current rule or focus, plus the approved
            # question, instead of a status line and silence.
            out['reply'] = self.recovery_statement(rules, {**context, **floor_keys}, recovery_question, required_reason)
            ack = self.plans_acknowledgement(plans_entry, '')
            if ack:
                out['reply'] = (ack + '\n\n' + out['reply']).strip()
            if plans_entry:
                self.plans_additions.pop((owner, self.current_chain.get(owner)), None)
            if recovery_question is None and not stop_questions:
                # Every turn ends with a question (owner intent). With no
                # approved meaning left to ask, keep the conversation open with
                # the educational continuation instead of silence (P06/P08).
                out['reply'] = (out['reply'] + '\n\n' + self.CONTINUATION_QUESTION).strip()
            out['facts'] = []
            sources = []
            floor_rule = floor_statement(rules, required_reason)
            for rule in ([floor_rule] if floor_rule else []):
                fact = self.facts.get(rule['fact_id'], {})
                for source in ([{'url': fact['source'], 'label': 'Medicare.gov: ' + fact['title']}] if fact.get('source') else fact.get('sources', [])):
                    if isinstance(source, dict) and source.get('url'):
                        sources.append({'url': source['url'], 'label': source.get('label') or fact.get('title', '')}); break
            out['advisor'] = {'visual': 'none', 'teachingFactIds': [], 'sources': sources, 'kind': 'answer', 'topic': '', 'reason': 'recovery'}
            out['assessment']['nextQuestion'] = None if stop_questions else recovery_question
            out['assessment']['conversationOpen'] = True
            out['assessment']['intakePaused'] = stop_questions
            out['notice'] = 'I couldn’t finish that answer. Here is the part I’m sure of.'
            diagnostic = getattr(self.agent.local, 'provider_failure', None)
            if diagnostic and diagnostic.get('provider_code') in {'credit_balance_exhausted', 'insufficient_quota'}:
                out['notice'] = provider_failure_message(diagnostic, accepted=True)
            code = getattr(self.agent.local, 'last_composition_error', None) or ('provider_failure' if diagnostic else 'composition_unavailable')
            if code not in COMPOSITION_CODES: code = 'composition_unavailable'
            # Validation outcomes (names, dates, format, length) are diagnostics
            # in generated.code, not reader-facing notices: the reader sees the
            # one calm floor sentence (owner direction, Nov 8–9, 2026). Connection
            # and provider failures remain explicit because they change what the
            # person should do next.
            if code == 'input_token_verification':
                out['notice'] = 'The AI connection check did not finish. Your reported details are kept.'
            elif code == 'transport_or_format':
                failure = getattr(self.agent.local, 'last_transport_failure', {}) or {}
                if failure.get('http_status') == 429:
                    out['notice'] = 'The selected AI provider is limiting requests. Your reported details are kept.'
                elif failure.get('http_status'):
                    out['notice'] = 'The selected AI provider declined the request. Your reported details are kept.'
                elif failure.get('phase') == 'stream':
                    out['notice'] = 'The AI connection ended before the reply arrived. Your reported details are kept.'
            out['generated'] = {'status': 'unavailable', 'retryable': False, 'reason': str(error)[:220], 'code': code}
            transport = getattr(self.agent.local, 'last_transport_failure', None)
            if code == 'transport_or_format' and transport:
                out['generated']['transport'] = copy.deepcopy(transport)
            if diagnostic: out['generated']['providerFailure'] = copy.deepcopy(diagnostic)
            token_failure = getattr(self.agent.local,'last_token_failure',None)
            if code == 'input_token_verification' and token_failure:
                out['generated']['preflight'] = copy.deepcopy(token_failure)
            with self.lock:
                self.composition_diagnostics.append({'code': code, 'questionAvailable': bool(recovery_question), 'intakePaused': False})
                self.composition_diagnostics = self.composition_diagnostics[-50:]
            LOGGER.warning('Daylight composition unavailable code=%s question_available=%s', code, bool(recovery_question))
            out['metrics']['continuation'] = {'assessment': None, 'delivered': 'withheld',
                                              'validation_changed_continuation': True}
            out.setdefault('_advisor_memory', {})['continuation'] = copy.deepcopy(out['metrics']['continuation'])
        # Exact counting may fail before submission. Count paid stages actually
        # issued, including an uncertain stream, rather than attempted methods.
        stage = reservation.stage('compose') if reservation else None
        out['metrics']['llmCalls'] += stage.attempts if stage else 0
        out['metrics']['stageMs'] = copy.deepcopy(getattr(self.agent.local, 'stage_timings', {}))
        if policy == CONTEXT_POLICY:
            # D157: tidy the reply, attach code-built cards, record what was said.
            ux_flow.finish(self, owner, out, message, moves, rules=rules, required_reason=required_reason,
                           accepted_reports=accepted_reports, submitted_answer=submitted_answer)
        return out

    def message(self, owner, payload, g, r):
        action = payload['action']
        if set(action) != {'type', 'message'}:
            raise ProfileError('Use the current conversation message.')
        message = action.get('message', '')
        if not isinstance(message,str):raise ProfileError('Use a text message.')
        message=message.strip()
        if not 1 <= len(message) <= 1200:
            raise ProfileError('Use 1–1200 characters; longer lists can be added in several messages.')
        reject_sensitive(message)
        if find_identifiers(message):
            raise ProfileError(IDENTIFIER_MESSAGE)  # HP-07: never sent, saved or logged.
        if payload.get('aiConsent') is not True and not self.fixture:
            raise ProfileError('AI transfer needs your permission. The choices and reviewed explanations still work.', 428)
        if not self.fixture and (not self.agent.enabled or not self.agent.client.available):
            raise ModelUnavailable('Live AI is unavailable. Your message is preserved; the choices and reviewed explanations still work.')
        policy = payload.get('contextPolicy')
        current = self.assess(g, r)['nextQuestion']
        presentation = self.current_presentation(owner, payload.get('continuation'))
        if presentation is not None:
            current = copy.deepcopy(presentation.get('nextQuestion'))
        ns = ensure_state(r)
        if ns.get('agenda',{}).get('lastMove') and ns['dialogue']['lastTarget'] is None:
            current=None
        priorities_before=copy.deepcopy(g['fields'].get('needs.priorities'))
        previous_dialogue=copy.deepcopy(ns['dialogue'])
        # A question displayed in the previous response has the same underlying
        # target even though its generated wording is intentionally not stored.
        previous_orientation = ns['dialogue']['orientation'] == 'progress'
        if previous_orientation and presentation is None:
            current = self.question('T02')
            set_target(r, current, orientation='familiarity')
        pending = self.pending_for(owner)
        if pending and pending['revision'] == [g['stateVersion'], r['stateVersion']]:
            u = pending['update']
            if not current or (current['id'], current.get('entity', 'profile')) != (u['id'], u.get('entity', 'profile')):
                current = self.question(u['id'], [k for k in u['fields'] if k != 'choice'] or None, u.get('entity', 'profile'))
        answer_context = question_binding(self.permitted_question(current, policy), self.value(g, 'subject.role'),
            {'S_AGE65': ['month', 'year', 'first_day'], 'S_RETIREMENT': ['status', 'when']}.get((current or {}).get('id'), ()),
            subject='learner' if (current or {}).get('id') in {'T01', 'T02'} else 'beneficiary')
        short_birthday = (re.fullmatch(r'(' + '|'.join(MONTHS)
            + r')(?:\s+\d{1,2}(?:st|nd|rd|th)?,?)?(?:\s+((?:19|20)\d{2}))?'
            + r'(?:[,;]?\s+(?:and\s+)?(?:not )?(?:on )?the (?:first|1st)(?: day)?(?: of the month)?)?[.!]?',
            message, re.I) if current and current['id'] == 'S_AGE65' else None)
        # A whole, unambiguous reply to the active birthday question already
        # has a local parser and the same conflict checks as a model proposal.
        direct_birthday = bool(short_birthday and short_birthday[2] and self.value(g, 'subject.role') == 'self'
                               and policy == CONTEXT_POLICY)
        if self.fixture:
            # Synthetic mode remains explicitly labeled and makes no AI claim.
            result = self.fixture_result(message, current)
            result['updates'] = [u for u in result['updates'] if u['id'] not in {'T05','RC09'} or not observations(message)]
            reservation = None
        else:
            reservation = self.agent.reserve_turn(stages=('compose',) if direct_birthday else ('extract', 'compose'))
        before = [g['stateVersion'], r['stateVersion']]
        report_snapshot = (copy.deepcopy(g), copy.deepcopy(r))
        try:
            if not self.fixture and direct_birthday:
                self.agent.local.stage_timings = {}
                result = {'updates': [], 'requests': [], 'fact_ids': []}
            elif not self.fixture:
                context = self.context(g, r, policy, current)
                if conversation_planner.enabled(self) and policy == CONTEXT_POLICY:
                    context['discussion_enabled'] = True
                    context['discussion_instructions'] = conversation_planner.INTERPRETATION
                    prior = conversation_planner.state(self, owner)
                    context['discussion_context'] = {key: copy.deepcopy(prior[key])
                        for key in ('purpose', 'focus', 'exploring', 'investigate', 'decision')}
                if self._plans_context.get():
                    pc = self._plans_context.get()
                    context['plans_view'] = {k: copy.deepcopy(pc[k]) for k in
                        ('selected_id', 'focused_field', 'mode', 'visible_ids', 'compared_ids', 'attention_is_not_preference')}
                recent = self.recent_exchanges(owner, metadata(r)['task'], policy)
                safe_reports = {x['id'][6:]:x['value'] for x in context['reports'] if x['id'] in {'guide.intent.goal','guide.knowledge.general','guide.subject.role','guide.coverage.current'} and x['status'] in {'reported','derived'}}
                context.update(task=metadata(r)['task'], preparing=metadata(r)['preparing'],
                               lastFactIds=metadata(r)['lastFactIds'], activeQuestion=self.permitted_question(current,policy),
                               definitions=self.agent.definitions, safeReports=safe_reports, pending=False)
                context['teachingCandidates']=self.teaching_candidates(g,r,current)
                if policy == CONTEXT_POLICY:
                    context['answer_context'] = answer_context
                    context['advisor_brief'] = self.advisor_brief(owner, g, r, policy, self.eligible(owner, g, r))
                if policy == CONTEXT_POLICY:
                    context['recent_exchanges'] = recent
                    context['education_context'] = {'learning': learning_context(
                        self.memory.education(owner, self.current_chain.get(owner), policy))}
                    context['learner_context'] = learner_state.context(
                        self.memory.learner(owner, self.current_chain.get(owner), policy))
                    context['education_context']['catalog'] = catalog_context()
                extraction_guide, _ = legacy_projection(g, r)
                result = self.agent.extract(owner, message, extraction_guide, context, payload['requestId'], reservation)
            m = metadata(r)
            capture_outcomes = [outcome(item['id'], 'unsupported', item['reason'])
                for item in [*result.get('rejected_updates', []), *result.get('rejected_situation_proposals', [])]
                if item.get('id') in Q or item.get('id') in {'S_AGE65', 'S_RETIREMENT'}]
            # Interpretation proposes reports; it does not choose a hidden
            # conversation mode. The retained task is only a dependency lens.
            goal_quote = result.get('goal_quote', '')
            if not isinstance(goal_quote, str) or len(goal_quote) > 200 or goal_quote.casefold() not in message.casefold():
                goal_quote = ''
            # D138: naming the product is enough. The November 10 live runs
            # showed that requiring an exact product word plus a price word left
            # "what do the supplement plans cost?" and every Part D request
            # without a route to the tabs. Medigap is first when both are named;
            # its location questions also complete the Part D reference.
            wanted = self.named_plan_task(goal_quote)
            if not wanted and re.search(r"(?i)\?|\b(?:want|need|looking|show|see|cost|price|premium|how much|compare|find|get)", message) \
                    and not re.search(r'(?i)\badvantage\b|\bpart c\b|\bhmo\b|\bppo\b', message):
                wanted = self.named_plan_task(message)
            if wanted == 'drug_pricing' and m['task'] == 'medigap' and self.medigap_questions(g, r):
                wanted = None  # Finish the Medigap details first; they also locate the Part D plans.
            if wanted and not conversation_planner.enabled(self):
                m['task'], m['preparing'] = wanted, True
            m['checks'] = sorted(set(m['checks']) | {x['id'] for x in result.get('requests', []) if x['id']!='coverage_change' or re.search(r'(?i)\bjoin|drop|cancel|switch|replace',x['quote'])})
            pending_goal = self.pending_for(owner)
            if goal_quote and pending_goal and pending_goal['update']['id'] == 'T01':
                self.resolve_pending(owner, pending_goal['update'], g, r)
            updates = []
            for u in result.get('updates', []):
                u = copy.deepcopy(u)
                if isinstance(u['fields'], list):u['fields'] = {f['key']:f['value'] for f in u['fields']}
                if u['id'] == 'T01' and goal_quote and u.get('uncertain'):
                    # Mapping a clear goal to a coarse category is optional;
                    # uncertainty about the category must not restart intake.
                    continue
                for field in {'month','jobEnd','coverageEnd','eventDate','start'} & set(u['fields']):
                    if u['fields'][field] not in {'unknown','deferred','not sure','check later'}:
                        try:u['fields'][field]=month(u['fields'][field])
                        except ProfileError:pass
                updates.append(u)
            if policy == CONTEXT_POLICY:
                updates.extend(self.direct_choices(message, current, updates))
                if enrollment_flow.enabled(self):
                    negatives = enrollment_flow.explicit_parts(message, self.value(g, 'subject.role'))
                    if negatives:
                        states = tuple((negatives.get(p) or self.value(g, enrollment_flow.PART_FIELDS[p]) or {}).get('status') for p in ('A', 'B'))
                        explicit_choice = {('active', 'not_enrolled'): 'a_only', ('not_enrolled', 'active'): 'b_only',
                                           ('not_enrolled', 'not_enrolled'): 'neither'}.get(states)
                        updates = [u for u in updates if u.get('id') != 'RC04']
                        updates.append({'id': 'RC04', 'entity': 'profile', 'fields': {'choice': explicit_choice or 'unknown'},
                            'quote': message[:600], 'scope': 'current', 'subject': 'beneficiary',
                            'uncertain': False, 'correction': True, 'direct_choice': True})
                part_only = self.part_a_coverage_answer(message, current, updates, r)
                if part_only is not None:
                    updates.append(part_only)
                part_status = self.part_status_report(message, updates, r)
                if part_status is not None and (self.value(g, 'subject.role') == 'self' or any(u.get('id') == 'RC01' and u.get('fields', {}).get('choice') == 'self' for u in updates)):
                    updates.append(part_status)
                elif part_status is None and enrollment_flow.enabled(self):
                    # D161: "I applied" also answers which parts the person has, so it is not asked again.
                    reported_parts = enrollment_flow.parts_answer(self, g, r, message, updates)
                    if reported_parts is not None:
                        updates.append(reported_parts)
            # Dependencies first, independent of extraction order.
            updates.sort(key=lambda u:0 if u['id'] == 'RC01' else 1 if u['id'] in FIELD else 2)
            # Multiple positive priorities in one message are coequal answers
            # to the existing multi-select meaning, not sequential corrections.
            # Across-turn changes and explicit corrections retain their guards.
            priorities = [u for u in updates if u['id'] == 'T10']
            positive = set(dict(Q['T10']['choices'])) - {'unknown', 'none'}
            if (len(priorities) > 1
                    and all(set(u['fields']) == {'choice'} and not u.get('correction')
                            and not u.get('uncertain') and isinstance(u['fields']['choice'], str)
                            and set(u['fields']['choice'].split(',')) <= positive for u in priorities)
                    and len({(u.get('entity'), u.get('subject'), u.get('scope')) for u in priorities}) == 1):
                start = min(message.find(u['quote']) for u in priorities)
                end = max(message.find(u['quote']) + len(u['quote']) for u in priorities)
                if 0 <= start < end and end - start <= 600:
                    merged = copy.deepcopy(priorities[0])
                    merged['fields']['choice'] = ','.join(dict.fromkeys(
                        choice for u in priorities for choice in u['fields']['choice'].split(',')))
                    merged['quote'] = message[start:end]
                    updates = [u for u in updates if u['id'] != 'T10'] + [merged]
            ambiguous = [];accepted_updates=[]
            confirmation = self.pending_confirmation(owner, message, updates)
            if confirmation is not None:
                updates.append(confirmation)
            for update in updates:
                if (update['id'] == 'T03' and set(update['fields']) == {'county'}
                        and not re.fullmatch(r'\d{5}', str(self.value(g, 'comparison.scope.zip') or ''))):
                    # The existing location operation needs a ZIP before it can
                    # qualify a county. A request mentioning a county is neither
                    # a conflicting ZIP nor a failed clarification answer. Its
                    # words remain in the permitted visit; ask the normal ZIP
                    # candidate rather than creating an unresolvable hold.
                    capture_outcomes.append(outcome(update['id'], 'needs_clarification', 'missing_dependency'))
                    continue
                pending = self.pending_for(owner)
                resolution_update = self.pending_resolution_update(pending, update, r)
                resolves_pending = self.touches_pending(pending, update) or self.touches_pending(pending, resolution_update)
                if resolves_pending and not update.get('uncertain'):
                    update['correction'] = True
                old = g['fields'].get(FIELD[update['id']]) if update['id'] in FIELD else r['facts'].get(update['id'])
                if old and old.get('stale') and update['id'] in {'RC21', 'RC22', 'RC23'} and pending and not resolves_pending:
                    old = {**old, 'stale':False}
                if old and update['id'] in {'T04','T06','T07'}:
                    old=copy.deepcopy(old)
                    secondary={'T04':('month','coverage.requestedStartMonth'),'T06':('text','needs.providers'),'T07':('text','needs.medications')}[update['id']]
                    old['value']={'choice':old['value'],secondary[0]:self.value(g,secondary[1])}
                classification = classify_update(update, message, existing=old)
                if classification['decision'] == 'reject':
                    capture_outcomes.append(outcome(update['id'], 'unsupported', classification['reason'], update.get('entity', 'profile')))
                    continue
                if classification['decision'] == 'clarify':
                    if update['id'] == 'T01' and goal_quote:
                        continue
                    ambiguous.append(update)
                    capture_outcomes.append(outcome(update['id'], 'conflicting' if classification['reason'] == 'conflicting_report'
                        else 'needs_clarification', classification['reason'], update.get('entity', 'profile')))
                    continue
                try:
                    before_capture = self.capture_values(g, r)
                    self.capture(g, r, update, resolve_aggregate=resolves_pending and not self.aggregate_still_pending(pending, update, (resolution_update,)))
                    capture_outcomes.append(outcome(update['id'], 'already_known' if before_capture == self.capture_values(g, r)
                        else 'accepted', classification['reason'], update.get('entity', 'profile')))
                    accepted_updates.append(update)
                    self.retire_item_targets(owner,g,r,update)
                    if resolves_pending:
                        self.resolve_pending(owner, update, g, r)
                        if resolution_update is not update:
                            self.resolve_pending(owner, resolution_update, g, r)
                        pending = self.pending_for(owner)
                except ProfileError:
                    ambiguous.append(update)
                    capture_outcomes.append(outcome(update['id'], 'needs_clarification', 'capture_not_committed', update.get('entity', 'profile')))
            # The live model supplies semantic observations; the phrase
            # recognizer remains only for explicitly synthetic fixture mode.
            proposed_situation = observations(message, self.value(g, 'subject.role')) if self.fixture else {}
            situation_meta = {}
            conflicting_kinds = set()
            for proposal in result.get('situation_proposals', []):
                if proposal.get('subject') != 'beneficiary' or proposal.get('scope') == 'unknown':
                    capture_outcomes.append(outcome('S_' + proposal['kind'].upper(), 'unsupported', 'unresolved_subject_or_scope'))
                    continue
                kind = proposal['kind']
                value = ({'month': proposal['month'], 'year': proposal['year']} if kind == 'age65'
                         else {'status': proposal['status'], 'when': proposal['when']})
                if kind == 'age65':
                    first_day = proposal.get('first_day')
                    if first_day is None:
                        first_day = birthday_first_day(proposal['quote'], value['month'])
                    if first_day is not None:
                        value['first_day'] = first_day
                if kind in proposed_situation and proposed_situation[kind] != value:
                    conflicting_kinds.add(kind)
                proposed_situation[kind] = value
                situation_meta[kind] = proposal
            support = message
            if short_birthday:
                month_number = MONTHS.index(short_birthday[1].lower()) + 1
                value = {'month': month_number, 'year': int(short_birthday[2]) if short_birthday[2] else None}
                first_day = birthday_first_day(message, month_number)
                if first_day is not None:
                    value['first_day'] = first_day
                proposed_situation['age65'] = value
            elif (current and current['id'] == 'S_RETIREMENT' and 'retirement' not in proposed_situation
                    and retirement_status_from_text(message)):
                # A short answer to the retirement question in the person's own
                # words ("Yes, retired from civilian work and not working") states
                # one status; it needs no exact single-word match to count.
                proposed_situation['retirement'] = {'status': retirement_status_from_text(message), 'when': ''}
            situation_confirmation = self.pending_situation_confirmation(owner, message, proposed_situation)
            if situation_confirmation is not None:
                proposed_situation[situation_confirmation[0]] = situation_confirmation[1]
                support = message
            uncertain_kinds = {kind for kind, item in situation_meta.items() if item.get('uncertain')}
            situation={}
            for kind, value in proposed_situation.items():
                situation_id='S_'+kind.upper()
                old=g['fields'].get(SITUATION_FIELDS[kind])
                proposal = situation_meta.get(kind, {})
                scoped_support = proposal.get('quote') or support
                first_day = value.pop('first_day', None) if kind == 'age65' else None
                resolution=classify_situation(scoped_support,kind,value,existing=old, answer_context=answer_context)
                if resolution['reason'] == 'conflicting_report' and proposal.get('correction'):
                    resolution = classify_situation(scoped_support, kind, value, answer_context=answer_context)
                if kind in conflicting_kinds:
                    resolution = {'decision':'clarify','reason':'multiple_situation_reports','value':value}
                if kind in uncertain_kinds:
                    resolution = {'decision':'clarify','reason':'tentative','value':value}
                if resolution['decision']=='clarify' and resolution['reason']=='conflicting_report' and pending and pending['update']['id']==situation_id:
                    resolution=classify_situation(support,kind,value, answer_context=answer_context)
                if situation_confirmation is not None and kind == situation_confirmation[0] and resolution['decision'] != 'reject':
                    # The person confirmed the exact value Daylight asked about.
                    resolution = {'decision': 'accept', 'reason': 'explicit_confirmation', 'value': copy.deepcopy(value)}
                if resolution['decision']=='reject':
                    capture_outcomes.append(outcome(situation_id, 'unsupported', resolution['reason']))
                    continue
                if resolution['decision']=='clarify':
                    proposed_value = copy.deepcopy(resolution.get('value') or value)
                    if kind == 'age65' and first_day is not None:
                        proposed_value['first_day'] = first_day
                    ambiguous.append({'id':situation_id,'fields':{},'entity':'profile','proposed':proposed_value})
                    capture_outcomes.append(outcome(situation_id, 'conflicting' if resolution['reason'] == 'conflicting_report'
                        else 'needs_clarification', resolution['reason']))
                    continue
                value = resolution['value']
                if kind == 'age65':
                    prior = (old or {}).get('value') or {}
                    same_month = (value['month'], value['year']) == (prior.get('month'), prior.get('year'))
                    previous_flag = prior.get('first_day') if same_month else None
                    if (first_day is not None and previous_flag is not None and first_day != previous_flag
                            and (old or {}).get('status') == 'reported'
                            and not proposal.get('correction') and not (pending and pending['update']['id'] == situation_id)):
                        ambiguous.append({'id':situation_id,'fields':{},'entity':'profile'})
                        capture_outcomes.append(outcome(situation_id, 'conflicting', 'conflicting_report'))
                        continue
                    flag = previous_flag if first_day is None else first_day
                    if flag is not None:
                        value['first_day'] = flag
                situation[kind]=value
                before_g, before_r = copy.deepcopy(g), copy.deepcopy(r)
                self.put(g, SITUATION_FIELDS[kind], value, 'user_text')
                accepted_updates.append({'id': situation_id})
                capture_outcomes.append(outcome(situation_id,
                    'already_known' if old and old.get('status') == 'reported' and old.get('value') == value else 'accepted', resolution['reason']))
                record_capture(g, r, before_g, before_r, {'id':situation_id, 'fields':{}, 'entity':'profile'}, method='direct_report')
                if pending and pending['update']['id']==situation_id:
                    self.resolve_pending(owner, pending['update'], g, r)
                    pending = self.pending_for(owner)
            if situation and not self.value(g, 'subject.role') and re.search(r"(?i)\bI(?:'|’|m\b| am| have| turn)", message) and not re.search(r'(?i)\bmy (?:mother|father|mom|dad|parent|spouse|wife|husband)\b', message):
                self.capture(g, r, {'id':'RC01', 'fields':{'choice':'self'}, 'entity':'profile'})
            m = metadata(r)
            if not m['task']:
                m['task'], m['preparing'] = 'compare', True
                r['stateVersion'] += 1
            facts = [self.facts[fid] for fid in result.get('fact_ids', []) if fid in self.facts]
            if ambiguous:
                for update in ambiguous:
                    identifier=update['id']
                    field=FIELD.get(identifier) or (SITUATION_FIELDS['age65' if identifier=='S_AGE65' else 'retirement'] if identifier.startswith('S_') else None)
                    if field in g['fields']:g['fields'][field]['status']='stale'
                    if identifier=='RC01' and 'subject.role' in g['fields']:g['fields']['subject.role']['status']='stale'
                    if identifier=='T04' and 'coverage.requestedStartMonth' in g['fields']:g['fields']['coverage.requestedStartMonth']['status']='stale'
                    if identifier in r['facts']:r['facts'][identifier]['stale']=True
                r['stateVersion']+=1
                self.queue_pending(owner, ambiguous, g, r)
            elif self.pending_for(owner):
                self.pending_for(owner)['revision'] = [g['stateVersion'], r['stateVersion']]
            sync_agenda(g,r)
            if policy==CONTEXT_POLICY:apply_agenda_reports(g,r,message,result.get('agenda'),accepted_updates)
            if conversation_planner.enabled(self):
                conversation_planner.observe(self, owner, g, r, message, result, current)
            priority_changed=bool(priorities_before and any(x['id']=='T10' for x in accepted_updates)
                and priorities_before.get('value')!=g['fields'].get('needs.priorities',{}).get('value'))
            moves = self.eligible(owner, g, r, facts=facts, priority_changed=priority_changed)
            out = self.response(g, r, facts=facts, expectedStateVersion=before[0], expectedReadinessRevision=before[1],
                                metrics={'llmCalls':0 if self.fixture or direct_birthday else reservation.stage('extract').attempts, 'synthetic':self.fixture})
            # Commit reports before composition without pretending a new
            # conversational direction has been chosen. Unexpected failures
            # and exact receipt replay follow the same continuation boundary.
            prior_target = (previous_dialogue.get('lastTarget') or {}).get('id')
            out['assessment']['nextQuestion'] = self.continuation_question(moves, prior_target)
            out['assessment']['conversationOpen'] = True
            out['assessment']['intakePaused'] = False
            out['assessment']['narrative']['opener'] = False
            out['reply'] = ''
            set_target(out['record'], out['assessment'].get('nextQuestion'),
                       orientation='familiarity' if (out['assessment']['nextQuestion'] or {}).get('id')=='T02' else None)
            out['continuation'] = self.bind(owner, out['guide'], out['record'], self.current_chain[owner])
            self.comparisons.attach(out)
            with self.lock:
                key = (owner, payload['requestId'])
                self.turn_journal[key] = {'signature':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
                                         'response':copy.deepcopy(out), 'expires':time.time()+VISIT_HISTORY_TTL, 'stage':'resolved'}
                self.state_heads[(owner,self.current_chain[owner])] = out['continuation']
            if self.fixture:
                out['reply'] = 'Synthetic conversation: the supplied reports are captured.'
                if moves: out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question'])
                out['assessment']['narrative']['opener'] = False
            else:
                delta = self.report_delta(*report_snapshot, out['guide'], out['record'], accepted_updates)
                # The extractor's own one-line reading of this turn (discourse note
                # and priority reason) feeds rule selection as a concern signal —
                # model-derived summaries, never the raw message (Nov 9, 2026).
                reason = (result.get('agenda') or {}).get('priorityReason') or {}
                out['_extraction_agenda'] = {'current_concern': ' '.join(filter(None, [
                    str(result.get('discourse_note') or ''), str(reason.get('reason') or ''), str(reason.get('topic') or '')]))[:400]}
                out = self.compose_response(owner, out, message, moves, policy, payload['requestId'], reservation, previous_dialogue, goal=goal_quote or None, priority_changed=priority_changed,
                    accepted_reports=delta, resolved_changes=self.resolved_changes(*report_snapshot, delta),
                    education_request=result.get('education_request'),
                    learner_observations=result.get('learner_observations', ()),
                    capture_outcomes=capture_outcomes, answer_context=answer_context)
                out.pop('_extraction_agenda', None)
                if isinstance(result.get('discourse_note'), str) and result['discourse_note'].strip():
                    out.setdefault('_advisor_memory', {})['discourse_note'] = result['discourse_note'].strip()
            shown = [fact['id'] for fact in out.get('facts', []) if fact['id'] in self.progress_fact_ids]
            if shown:
                m=metadata(out['record']);m['lastFactIds']=shown
                for id in shown:
                    if id not in m['journey']['learningSeen']:m['journey']['learningSeen'].append(id)
                out['record']['stateVersion']+=1
            target = (out['assessment'].get('nextQuestion') or {}).get('id', '')
            # Value-free dialogue metadata; no generated prose is persisted.
            set_target(out['record'], out['assessment'].get('nextQuestion'),
                       orientation='familiarity' if target == 'T02' else None)
            if self.pending_for(owner):
                self.pending_for(owner)['revision']=[out['guide']['stateVersion'],out['record']['stateVersion']]
            self.validate(out['guide'], out['record'])
            if goal_quote and len(goal_quote) <= 200:
                out.setdefault('_advisor_memory', {})['goal'] = goal_quote
            self.remember_exchange(owner, message, out, policy, payload['requestId'])
            return out
        finally:
            if reservation:
                reservation.close()
                if 'out' in locals() and self.turn_trace_enabled():
                    out.setdefault('metrics', {})['settledUsage'] = reservation.trace_usage()

    AFFIRMATIVE = re.compile(
        r"(?i)^(?:yes|yep|yeah|yup|correct|right|exactly|that(?:'|\u2019)?s (?:right|correct|it|all|everything|the (?:complete |whole |full )?list)|"
        r"(?:no,?\s+)?(?:just|only) (?:those|that|these|the (?:two|three|one)|\w+ (?:two|three|one))\b.*|"
        r"(?:no,?\s+)?(?:nothing|no(?:thing)? else|none other|no others?)\b.*|those are all(?: of them)?|that is all|that is (?:right|correct)|"
        r"(?:yes,?\s+)?that(?:'|\u2019)?s (?:right|correct|all|it|everything|the (?:complete |whole |full )?list)\b.*|yes,? (?:that(?:'|\u2019)?s|those are|it is|that is) (?:right|correct|all|it|everything|the (?:complete |whole |full )?list|all of them)\b.*)[.!]*$")

    def affirmative_message(self, message):
        """A short reply that confirms what Daylight just asked, in the person's words."""
        text = (message or '').strip()
        if not text or len(text) > 90 or '?' in text:
            return False
        if re.search(r"(?i)\b(?:not|never|isn['\u2019]?t|aren['\u2019]?t|wasn['\u2019]?t|don['\u2019]?t|didn['\u2019]?t|wrong|instead|actually|but)\b", text) and not re.search(r"(?i)\b(?:nothing|no(?:thing)? else|none other|no others?|not (?:any )?others?)\b", text):
            return False
        if re.search(r"(?i)\b(?:I think|maybe|might|probably|not sure|I guess)\b", text):
            return False
        return bool(self.AFFIRMATIVE.fullmatch(text))

    def pending_confirmation(self, owner, message, updates):
        """Turn a bare affirmative into the pending profile report it confirms.

        "Just those two" after "is that the complete list?" confirms the exact
        value Daylight asked about. Nothing is invented: the fields are the
        ones the person already stated and the quote is this reply. Item
        clarifications that still lack a target and situation holds are
        resolved elsewhere.
        """
        pending = self.pending_for(owner)
        if not pending or not self.affirmative_message(message):
            return None
        target = pending['update']
        identifier = target.get('id', '')
        if identifier not in Q or not target.get('fields'):
            return None
        entity = target.get('entity', 'profile')
        if identifier in {'RC21', 'RC22', 'RC23'} and entity in {'profile', '', 'new'}:
            return None
        if any(self.touches_pending(pending, update) for update in updates):
            return None
        fields = {key: value for key, value in target['fields'].items() if isinstance(value, str)}
        if not fields or any(str(value).casefold().strip() in {'unknown', 'deferred', 'not sure', 'check later'} for value in fields.values()):
            return None
        subject = target.get('subject') if target.get('subject') in {'beneficiary'} else 'beneficiary'
        scope = target.get('scope') if target.get('scope') in {'current', 'intended'} else 'current'
        return {'id': identifier, 'fields': fields, 'entity': entity, 'quote': message.strip(),
                'subject': subject, 'scope': scope, 'uncertain': False, 'correction': True}

    def pending_situation_confirmation(self, owner, message, proposed_situation):
        """A bare affirmative confirms the exact life report Daylight asked about."""
        pending = self.pending_for(owner)
        if not pending or not self.affirmative_message(message):
            return None
        target = pending['update']
        kind = {'S_AGE65': 'age65', 'S_RETIREMENT': 'retirement'}.get(target.get('id'))
        if not kind or kind in proposed_situation or not isinstance(target.get('proposed'), dict):
            return None
        return kind, copy.deepcopy(target['proposed'])

    def turn_trace_enabled(self):
        return bool(getattr(self, 'turn_trace', None))

    def trace_turn(self, owner, chain, action, out, started, failure=None):
        """One line per turn on the local demo: codes, times and counts, never a person's words.

        Three causes in the 15-profile evaluation (November 13, 2026) could not be confirmed because
        the only record was the Terminal window. Off unless the demo server turns it on."""
        if not self.turn_trace_enabled():
            return
        try:
            metrics = (out or {}).get('metrics') or {}
            generated = (out or {}).get('generated') or {}
            question = ((out or {}).get('assessment') or {}).get('nextQuestion') or {}
            line = {'at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    'visit': hashlib.sha256((str(owner) + ':' + str(chain)).encode()).hexdigest()[:10],
                    'action': action.get('type'), 'ms': round((time.monotonic() - started) * 1000),
                    'stage_ms': metrics.get('stageMs'), 'calls': metrics.get('llmCalls'),
                    'settled_usage': metrics.get('settledUsage'),
                    'finish': ((out or {}).get('enrollment') or {}).get('record', {}).get('finish'),
                    'generated': generated.get('status'), 'code': generated.get('code'),
                    'recovery': (generated.get('validation_recovery') or {}).get('reason'),
                    'capture': metrics.get('capture'), 'ux': metrics.get('ux'),
                    'question': question.get('id'), 'local_check': bool(question.get('localCheck')),
                    'cards': [card.get('kind') for card in (out or {}).get('cards') or []],
                    'reply_chars': len((out or {}).get('reply') or ''), 'notice': bool((out or {}).get('notice'))}
            if failure:
                line['failure'] = {key: failure.get(key) for key in ('code', 'type', 'locations')}
            path = Path(self.turn_trace)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'a', encoding='utf-8') as handle:
                handle.write(json.dumps(line, sort_keys=True) + '\n')
        except Exception:
            LOGGER.warning('Daylight turn trace skipped')

    def park_passed_question(self, owner, chain, out):
        """One question never owns the conversation: shown once, shown once more, then parked.

        In fifteen live runs (November 13, 2026) 56 of 100 turns ended on the same doctor or
        medicine question. A parked question is no longer a candidate; a held confirmation
        behind it is dropped, so the next useful question can be asked."""
        try:
            question = out['assessment'].get('nextQuestion')
            if not question or question.get('localCheck'):
                return
            key = ux_flow.question_key(question)
            # Who the coverage is for and the ZIP code open everything else, so they are never parked.
            if key.split('|')[0] in ('RC01', 'T03') or self.ux.shown_question(owner, chain, key) <= 2:
                return
            self.ux.park(owner, chain, key)
            pending = self.pending_for(owner)
            if pending and ux_flow.question_key({'id': pending['update']['id'], 'entity': pending['update'].get('entity')}) == key:
                self.clear_pending(owner)
            choices = [item for item in self.eligible(owner, out['guide'], out['record'])
                       if ux_flow.question_key(item.get('question') or item) != key]
            out['assessment']['nextQuestion'] = copy.deepcopy(choices[0]['question']) if choices else None
            out.setdefault('metrics', {}).setdefault('ux', {})['question_parked'] = key
        except Exception:
            LOGGER.warning('Daylight question budget skipped', exc_info=True)

    def direct_disposition(self, owner, payload, g, r):
        """An exact unknown/defer needs neither transfer nor another model call."""
        if set(payload['action'])!={'type','message'} or not isinstance(payload['action'].get('message'),str):return None
        message=payload['action']['message'].strip()
        if re.fullmatch(r"(?i)(?:I don['’]t know|I do not know|not sure|unknown)[.!]?",message):kind='unknown'
        elif re.fullmatch(r'(?i)(?:check later|add later|defer|skip this|skip that)[.!]?',message):kind='defer'
        else:return None
        pending=self.pending_for(owner)
        presentation = self.current_presentation(owner, payload.get('continuation'))
        if not pending and presentation is not None and presentation.get('nextQuestion') is None:
            return None
        if (not pending and r.get('natural',{}).get('agenda',{}).get('lastMove')
                and r['natural']['dialogue']['lastTarget'] is None):return None
        orientation=ensure_state(r)['dialogue']['orientation']=='progress'
        target=pending['update'] if pending else None
        current=self.question(target['id'], [key for key in target['fields'] if key!='choice'] or None, target.get('entity','profile')) if pending else self.question('T02') if orientation else self.assess(g,r)['nextQuestion']
        if conversation_planner.enabled(self) and not pending and presentation is not None:
            current = presentation.get('nextQuestion')
        if not current:return None
        if current['id'] in Q and pending:
            state='unknown' if kind=='unknown' else 'deferred'
            fields={key:state for key in target['fields'] if key!='choice'} or {'choice':state}
            self.capture(g,r,{'id':target['id'],'entity':target.get('entity','profile'),'fields':fields},
                         resolve_aggregate=not self.aggregate_still_pending(pending,target))
            out=self.response(g,r,'That’s okay. We can work with what you know.')
        elif current['id'] in medigap_profile.FIELDS:
            self.capture(g, r, {'id': current['id'], 'fields': {'choice': 'unknown' if kind == 'unknown' else 'deferred'}})
            out = self.response(g, r, 'That’s okay. Matched prices will stay unavailable until you add that detail.')
        elif current['id'] in Q:
            legacy={k:v for k,v in payload.items() if k not in {'contextPolicy','continuation','model','aiProvider','plansContext','plansContextPolicy'}}
            legacy['action']={'type':kind,'id':current['id']}
            out=super().turn(owner,legacy)
        else:
            if current['id'].startswith('S_'):
                field=SITUATION_FIELDS['age65' if current['id']=='S_AGE65' else 'retirement']
                if field in g['fields']:g['fields'][field]['status']='unknown' if kind=='unknown' else 'skipped'
            set_target(r,orientation='deferred' if orientation else None)
            r['stateVersion']+=1
            out=self.response(g,r,'That’s okay. We can work with what you know.')
        if pending:self.resolve_pending(owner,target,out['guide'],out['record'])
        if self.pending_for(owner):
            self.pending_for(owner)['revision']=[out['guide']['stateVersion'],out['record']['stateVersion']]
            out['assessment']['nextQuestion']=self.eligible(owner,out['guide'],out['record'])[0]['question']
        if conversation_planner.enabled(self):
            conversation_planner.action_done(self, owner, out, {'type': kind, 'id': current['id']})
        set_target(out['record'],out['assessment'].get('nextQuestion'))
        return out

    def ai_paused(self):
        agent = self.agent
        budget = getattr(agent, 'budget', None)
        if budget is None:
            return False
        try:
            return not budget.summary(agent.client.model)['canRequest']
        except Exception:
            return True

    def direct_local_answer(self, owner, payload, g, r):
        """D138: while AI replies are paused, a bare ZIP or age that answers
        the question on screen is recorded without a model call, so a pause
        never strands the person short of the Plans tabs. With AI available the
        ordinary composed turn is unchanged."""
        action = payload['action']
        if set(action) != {'type', 'message'} or not isinstance(action.get('message'), str):
            return None
        message = action['message'].strip().rstrip('.')
        if not re.fullmatch(r'\d{1,5}', message) or self.fixture or self.pending_for(owner) or not self.ai_paused():
            return None
        current = self.assess(g, r)['nextQuestion']
        if not current:
            return None
        if current['id'] == 'T03' and re.fullmatch(r'\d{5}', message):
            legacy = {k: v for k, v in payload.items() if k not in {'contextPolicy', 'continuation', 'model', 'aiProvider', 'plansContext', 'plansContextPolicy'}}
            legacy['action'] = {'type': 'choice', 'id': 'T03', 'fields': {'zip': message}}
            out = super().turn(owner, legacy)
        elif current['id'] == 'MG_AGE' and re.fullmatch(r'\d{1,3}', message) and int(message) <= 120:
            self.capture(g, r, {'id': 'MG_AGE', 'entity': 'profile', 'fields': {'choice': message}})
            out = self.response(g, r)
        else:
            return None
        set_target(out['record'], out['assessment'].get('nextQuestion'))
        return out

    def compose_choice(self,owner,payload,out,before_g,before_r):
        """A deliberate finite answer uses resolution + one composition only."""
        if conversation_planner.enabled(self):
            conversation_planner.action_done(self, owner, out, payload['action'])
        if (self.fixture or payload.get('aiConsent') is not True
                or payload.get('contextPolicy')!=CONTEXT_POLICY):return out
        action=payload['action'];identifier=action.get('id','')
        question=self.question(identifier) if identifier in Q else None
        if action['type'] in {'unknown','defer'}:
            message='I don’t know.' if action['type']=='unknown' else 'I’ll check later.'
        else:
            fields=action.get('fields',{})
            choices=dict((question or {}).get('choices',[]))
            message='; '.join(choices.get(value,value) for value in str(fields.get('choice','')).split(',') if value)
            if not message:message='; '.join(str(value) for value in fields.values())
        message=message[:1200]
        sync_agenda(out['guide'],out['record'])
        old=before_g['fields'].get('needs.priorities',{})
        new=out['guide']['fields'].get('needs.priorities',{})
        changed=bool(identifier=='T10' and old and old.get('value')!=new.get('value'))
        moves=self.eligible(owner,out['guide'],out['record'],facts=out.get('facts',[]),priority_changed=changed)
        out['assessment']['nextQuestion']=copy.deepcopy(moves[0]['question']) if moves else None
        out['metrics']={'llmCalls':0,'synthetic':False}
        self.agent.local.stage_timings={}
        reservation=None
        try:
            reservation=self.agent.reserve_turn(stages=('compose',))
            submitted_answer={'question_id':identifier,'question':(question or {}).get('question',''),
                'kind':action['type'],'fields':copy.deepcopy(action.get('fields',{}))}
            delta = self.report_delta(before_g, before_r, out['guide'], out['record'], [action])
            out=self.compose_response(owner,out,message,moves,CONTEXT_POLICY,payload['requestId'],reservation,
                submitted_answer=submitted_answer, priority_changed=changed, accepted_reports=delta,
                resolved_changes=self.resolved_changes(before_g, before_r, delta),
                capture_outcomes=[outcome(identifier, 'already_known' if self.capture_values(before_g, before_r) == self.capture_values(out['guide'], out['record'])
                    else 'accepted', 'explicit_' + action['type'])],
                answer_context=question_binding(question, self.value(before_g, 'subject.role')))
        except (ModelUnavailable,ProfileError,ValueError) as error:
            out['reply']='';out['notice']=str(error)[:220]
            out['advisor']={'visual':'none','teachingFactIds':[],'sources':[]}
            out['generated']={'status':'unavailable','retryable':False,'code':'composition_unavailable'}
            out['assessment']['intakePaused']=bool(not moves and self.assess(out['guide'],out['record']).get('nextQuestion'))
            out['assessment']['conversationOpen']=metadata(out['record'])['task']=='learn'
        finally:
            if reservation:
                reservation.close()
                if self.turn_trace_enabled():
                    out.setdefault('metrics', {})['settledUsage'] = reservation.trace_usage()
        set_target(out['record'],out['assessment'].get('nextQuestion'))
        if self.pending_for(owner):
            self.pending_for(owner)['revision']=[out['guide']['stateVersion'],out['record']['stateVersion']]
        self.validate(out['guide'],out['record'])
        self.remember_exchange(owner,message,out,CONTEXT_POLICY,payload['requestId'])
        return out

    def replay_response(self, owner, response):
        """Recheck derived authority without another interpretation/composition."""
        cached = copy.deepcopy(response)
        held_deadline = held_deadline_claim(cached.get('reply', ''),
            {**self.pilot_knowledge.response_limits(), **cached.get('knowledgeLimits', {})})
        if held_deadline or not self.pilot_knowledge.current(cached.get('knowledgeReceipts', {})):
            # Keep the approved next question and entered reports. Withdraw the
            # stale prose, using the already-reviewed foundation as the floor.
            fact = self.facts['basics']
            cached['reply'] = fact['summary']
            cached['facts'] = []
            cached['advisor'] = {'reason': 'recovery', 'visual': 'none',
                'teachingFactIds': [], 'educationFollowups': [],
                'sources': [{'url': fact['source'], 'label': fact['title']}]}
            cached['generated'] = {'status': 'unavailable', 'retryable': False,
                                   'code': 'knowledge_claim_held' if held_deadline else 'knowledge_source_stale'}
            cached['notice'] = 'The source for the earlier answer needs rechecking.'
            cached.pop('knowledgeReceipts', None)
        continuation = cached.get('continuation')
        chain = continuation.split('.')[0] if continuation else None
        historical = bool(continuation and (
            self.current_chain.get(owner) != chain or
            self.state_heads.get((owner, chain)) != continuation))
        cached = generated_conversation(
            self.comparisons.attach(cached, historical=historical, replay=True))
        cached['planReadiness'] = plan_readiness(cached['guide'], cached['record'],
                                               pending=None if historical else self.pending_for(owner))
        if getattr(self, 'conversation_checks', None):
            if historical:
                cached.pop('conversationCheck', None)
                cached.pop('closingResearch', None)
            else:
                self.conversation_checks.attach(owner,cached,
                    show_question=not cached.get('review') and not metadata(cached['record']).get('editing')
                    and not cached.get('conversationCheck',{}).get('paused'))
                if hasattr(self, 'closing_price_read'):
                    import closing_options
                    closing_options.attach(self, cached)
        if cached.get('plansContext'):
            binding = cached['plansContext']
            try:
                projection, _ = self.plans_service.projection()
                stale = (historical or binding['profile_changed']
                         or projection['projection_digest'] != binding['projection_digest']
                         or self.plans_service.decision_evidence_digest(binding['input_digest'])
                            != binding.get('decision_evidence_digest'))
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                stale = True
            if stale:
                cached['reply'] = ''
                cached['facts'] = []
                cached['planEvidence'] = []
                cached['generated'] = {'status': 'unavailable', 'code': 'plans_context_stale', 'retryable': False}
                cached['notice'] = 'This reply used an earlier Plans view. Refresh and send again.'
        if historical:
            cached.pop('plansHandoff', None)
            if (cached.get('review') or {}).get('kind') == 'plan_profile':
                cached.pop('review', None)
            cached['planReadiness']['canReview'] = False
        else:
            try:
                if cached.get('plansHandoff'):
                    cached['plansHandoff'] = self.plan_reviews.resolve(cached['plansHandoff']['token'], owner, chain,
                        cached['guide'], cached['record'], cached['planReadiness'])
                if (cached.get('review') or {}).get('kind') == 'plan_profile':
                    self.plan_reviews._check(self.plan_reviews.reviews, cached['review']['token'], owner, chain,
                        cached['guide'], cached['record'])
            except ProfileError:
                cached.pop('plansHandoff', None)
                cached.pop('review', None)
        return attach_task_work(cached, historical=historical)

    def resolve_plans_handoff(self, owner, token):
        """Resolve a receipt against the current server head, never client facts."""
        with self.lock:
            if owner in self.natural_active or owner in self.revoked_owners:
                raise ProfileError('Resume the current visit before opening plans.', 409)
            chain = self.current_chain.get(owner)
            head = self.state_heads.get((owner, chain))
            current = next((entry['response'] for (entry_owner, _), entry in reversed(list(self.turn_journal.items()))
                if entry_owner == owner and entry['expires'] > time.time()
                and entry['response'].get('continuation') == head), None)
            if not current:
                raise ProfileError('Review your current information before opening plans.', 409)
            status = plan_readiness(current['guide'], current['record'], pending=self.pending_for(owner))
            return self.plan_reviews.resolve(token, owner, chain, current['guide'], current['record'], status)

    def recover(self, owner, payload):
        """Free, owner-bound recovery. Never executes the submitted action.

        A finished request is replayed only at the current head. Otherwise use
        the latest trusted snapshot in this chain, or reconnect validated local
        reports after process loss. A changed context needs a new deliberate
        Send; this endpoint cannot grant AI, saving or named-action permission.
        """
        allowed = {'guide','record','action','requestId','aiConsent','pendingId',
                   'contextPolicy','continuation','model','aiProvider','plansContext','plansContextPolicy'}
        if (not isinstance(payload, dict) or set(payload) - allowed
                or not {'guide', 'record', 'requestId'} <= set(payload)
                or not re.fullmatch(r'[A-Za-z0-9-]{10,80}', str(payload['requestId']))):
            raise ProfileError('Use the current message to reconnect.')
        g, r = self.validate(payload['guide'], payload['record'])
        signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        binding = payload.get('continuation')
        if binding is not None and (not isinstance(binding, str) or
                not re.fullmatch(r'[a-f0-9]{32}\.[a-f0-9]{64}', binding)):
            raise ProfileError('Use the current message to reconnect.')
        chain = binding.split('.')[0] if binding else None
        with self.lock:
            if self.revoked_owners.get(owner, 0) > time.time():
                raise ProfileError('This guest session was deleted. Start a fresh visit before continuing.', 401)
            # Even a completed older response must not race an active turn.
            if owner in self.natural_active:
                return {'status': 'working'}
            entry = self.turn_journal.get((owner, payload['requestId']))
            if entry and entry['expires'] > time.time():
                if entry['signature'] != signature:
                    raise ProfileError('This request key belongs to another turn.', 409)
                completed = entry['response']
                completed_binding = completed.get('continuation')
                chain = completed_binding.split('.')[0]
                if self.state_heads.get((owner, chain)) == completed_binding:
                    out = self.replay_response(owner, completed)
                    status = 'completed'
                else:
                    out = None
            else:
                out = None
            if out is None:
                reconnect_id = 'reconnect-' + signature[:48]
                reconnected = self.turn_journal.get((owner, reconnect_id))
                if reconnected and reconnected['expires'] > time.time():
                    chain = reconnected['response']['continuation'].split('.')[0]
                head = self.state_heads.get((owner, chain)) if chain else None
                latest = next((item['response'] for (item_owner, _), item
                    in reversed(list(self.turn_journal.items()))
                    if item_owner == owner and item['expires'] > time.time()
                    and head is not None and item['response'].get('continuation') == head), None)
                if latest is not None:
                    out = self.replay_response(owner, latest)
                    status = 'resumed'
                else:
                    # The existing free refresh creates new action authority.
                    # It cannot replay old tokens or restore lost visit memory.
                    out = self._turn(owner, {'guide': g, 'record': r,
                        'action': {'type': 'refresh'},
                        'requestId': reconnect_id})
                    status = 'reset'
            # Saving and guide visibility are local choices excluded from the
            # signed binding. An older cached response cannot re-enable either.
            out['guide']['preferences'] = copy.deepcopy(g['preferences'])
            if 'guideOpen' in g.get('flow', {}):
                out['guide']['flow']['guideOpen'] = g['flow']['guideOpen']
            if status != 'completed':
                out.pop('review', None)
                out.pop('preparation', None)
            return {'status': status, 'response': out}

    def turn(self, owner, payload):
        context_token = self._plans_context.set(None)
        try:
            if isinstance(payload, dict) and ({'plansContext', 'plansContextPolicy'} & payload.keys()):
                if (not self.plans_service or payload.get('aiConsent') is not True
                        or payload.get('contextPolicy') != CONTEXT_POLICY
                        or payload.get('plansContextPolicy') != 'plans-context-v1'
                        or not isinstance(payload.get('action'), dict)
                        or payload.get('action', {}).get('type') != 'message'):
                    raise ProfileError('Send deliberately to share the current Plans context.', 428)
                request = payload.get('plansContext')
                if not isinstance(request, dict):
                    raise ProfileError('Use the current Plans context.', 422)
                with self.lock:
                    handoff = (self.resolve_plans_handoff(owner, request.get('reviewToken'))
                               if request.get('reviewToken') is not None else None)
                    self._plans_context.set(plans_rehydrate(self.plans_service, owner, request, handoff))
            return self._selected_turn(owner, payload)
        finally:
            self._plans_context.reset(context_token)

    def _selected_turn(self, owner, payload):
        if not isinstance(payload, dict) or not ({'model', 'aiProvider'} & payload.keys()):
            return self._turn(owner, payload)
        model = payload.get('model')
        spec = MODELS.get(model) if isinstance(model, str) else None
        if (not spec or payload.get('aiProvider') != spec.provider
                or payload.get('aiConsent') is not True or payload.get('contextPolicy') != CONTEXT_POLICY):
            raise ProfileError('Choose a model and confirm its provider by sending from the conversation.', 428)
        agent = self.model_agents.get(model)
        if not agent or not agent.client.available or agent.client.model != model:
            raise ProfileError('That AI model is unavailable. Choose another model to send this message.', 503)
        selection = self._turn_agent.set(agent)
        try:
            return self._turn(owner, payload)
        finally:
            self._turn_agent.reset(selection)

    def _turn(self, owner, payload):
        allowed = {'guide','record','action','requestId','aiConsent','pendingId','contextPolicy','continuation','model','aiProvider','plansContext','plansContextPolicy'}
        if not isinstance(payload, dict) or set(payload) - allowed or not re.fullmatch(r'[A-Za-z0-9-]{10,80}', str(payload.get('requestId', ''))):
            raise ProfileError('Use a current conversation request.')
        key = (owner, payload['requestId'])
        turn_started = time.monotonic()
        signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.lock:
            self.revoked_owners = {key: expiry for key, expiry in self.revoked_owners.items() if expiry > time.time()}
            if owner in self.revoked_owners:
                raise ProfileError('This guest session was deleted. Start a fresh visit before continuing.', 401)
            self.turn_journal = {k:v for k,v in self.turn_journal.items() if v['expires'] > time.time()}
            if key in self.turn_journal:
                entry = self.turn_journal[key]
                if entry['signature'] != signature:raise ProfileError('This request key belongs to another turn.', 409)
                return self.replay_response(owner, entry['response'])
            if owner in self.natural_active:raise ProfileError('Your earlier message is still being processed. Your work is preserved.', 409)
            self.natural_active.add(owner)
        try:
            g, r = self.validate(payload['guide'], payload['record'])
            binding = payload.get('continuation')
            action = payload.get('action', {})
            if not isinstance(action, dict):raise ProfileError('Use a supported conversation action.')
            # HP-07: refuse any submitted answer or message that carries an SSN, MBI or card number.
            if any(find_identifiers(text) for text in submitted_strings(action)):
                raise ProfileError(IDENTIFIER_MESSAGE)
            # D97: a Plans-page filter submits the same structured answer as the
            # conversation, labelled so composition can confirm it once. Free
            # local action only: never an AI call, never another action type.
            plans_filter = 'source' in action
            if plans_filter:
                if (action.get('source') != 'plans_filter' or action.get('type') != 'choice'
                        or action.get('id') not in PLANS_FILTER_QUESTIONS | medigap_profile.FIELDS.keys() or payload.get('aiConsent') is True):
                    raise ProfileError('Use a supported Plans filter answer.')
                action = {k: v for k, v in action.items() if k != 'source'}
                fields = action.get('fields') if isinstance(action.get('fields'), dict) else {}
                if action.get('id') in {'T06', 'T07'} and isinstance(fields.get('text'), str) and fields['text'].strip():
                    # Each Plans-page Add extends the list (owner, Nov 9, 2026:
                    # a second medicine replaced the first). The Remove control
                    # first records "none", so its remaining list still replaces.
                    doctors = action['id'] == 'T06'
                    status_path, list_path = (('needs.providersStatus', 'needs.providers') if doctors
                                              else ('needs.medicinesStatus', 'needs.medications'))
                    if self.value(g, status_path) in {'yes', 'list'}:
                        merged = list_items(self.value(g, list_path), doctors)
                        merged += [item for item in list_items(fields['text'], doctors)
                                   if item.casefold() not in {m.casefold() for m in merged}]
                        action = {**action, 'fields': {**fields, 'text': '; '.join(merged)}}
                payload = {**payload, 'action': action}
            if binding:
                if not isinstance(binding,str) or not re.fullmatch(r'[a-f0-9]{32}\.[a-f0-9]{64}',binding):raise ProfileError('Use the current conversation state.',409)
                chain=binding.split('.')[0]
                if not hmac.compare_digest(binding,self.bind(owner,g,r,chain)) or self.state_heads.get((owner,chain)) != binding:
                    raise ProfileError('Your conversation changed. Keep this message and resume the latest state.',409)
            else:
                if r.get('natural',{}).get('provenance') and action.get('type') not in {'refresh','start'}:
                    raise ProfileError('Resume the current conversation before continuing. Your reports are preserved.',409)
                chain=secrets.token_hex(16)
            self.current_chain[owner]=chain
            checks = getattr(self, 'conversation_checks', None)
            if self._plans_context.get() and payload['plansContext']['reviewToken'] is not None:
                # Rebind inside the active-turn boundary. A valid receipt from
                # another same-owner visit cannot accompany this conversation.
                self.plan_reviews.resolve(payload['plansContext']['reviewToken'], owner, chain, g, r,
                    plan_readiness(g, r, pending=self.pending_for(owner)))
            if checks:
                checks.observe(owner, g, r, action,self._plans_context.get())
            presentation = self.current_presentation(owner, binding)
            if action.get('type') == 'start':
                self.memory.clear(owner, chain)
                if hasattr(self, 'discussion_visits'):
                    self.discussion_visits.clear(owner)
            if action.get('type') in {'run_preparation','accept_review','discard_review'} and self.action_chains.get(action.get('token')) != (owner,chain):
                raise ProfileError('This authorization belongs to an earlier conversation. Review the current action again.',409)
            if action.get('type') == 'check_back':
                if not checks or not binding or set(action) != {'type'}:
                    raise ProfileError('Use the current conversation check.',422)
                checks.back(owner,g,r)
                out = self.response(g,r)
                out['advisor'] = {'reason':'tool_result', 'sources':[], 'visual':'none'}
                out['metrics'] = {'llmCalls':0,'synthetic':self.fixture}
            elif action.get('type') == 'check_edit':
                if not checks or not binding or set(action) != {'type','key','field'}:
                    raise ProfileError('Use the current conversation check.',422)
                checks.edit(owner,g,r,action['key'],action['field'])
                out = self.response(g,r)
                out['advisor'] = {'reason':'tool_result', 'sources':[], 'visual':'none'}
                out['metrics'] = {'llmCalls':0,'synthetic':self.fixture}
            elif action.get('type') == 'check_answer':
                if not checks or not binding or set(action) != {'type','token','value'}:
                    raise ProfileError('Use the current conversation question.',422)
                checks.answer(owner,g,r,action['token'],action['value'])
                out = self.response(g,r)
                out['advisor'] = {'reason':'tool_result', 'sources':[], 'visual':'none'}
                out['metrics'] = {'llmCalls':0,'synthetic':self.fixture}
            elif (checks and action.get('type') == 'message' and binding
                  and (not conversation_planner.enabled(self) or conversation_planner.checks_relevant(self, owner, g))
                  and (not conversation_planner.enabled(self) or not conversation_planner.conservative_request(action.get('message', ''))['question_quote'])
                  and checks.text_answer(owner,g,r,action.get('message',''))):
                out = self.response(g,r,'Thanks, I have that.')
                out['advisor'] = {'reason':'tool_result', 'sources':[], 'visual':'none'}
                out['metrics'] = {'llmCalls':0,'synthetic':self.fixture}
            elif action.get('type') in {'review_plans', 'confirm_plan_review', 'get_plan_handoff', 'cancel_plan_review'}:
                kind = action['type']
                expected = {'type'} if kind == 'review_plans' else {'type', 'token'}
                if set(action) != expected:
                    raise ProfileError('Use the current plan review action.')
                status = plan_readiness(g, r, pending=self.pending_for(owner))
                out = self.response(g, r)
                self.retain_presentation(out, presentation)
                if kind == 'review_plans':
                    out['review'] = self.plan_reviews.begin(owner, chain, g, r, status, self.rows(g, r))
                elif kind == 'confirm_plan_review':
                    out['plansHandoff'] = self.plan_reviews.confirm(action['token'], owner, chain, g, r, status)
                elif kind == 'get_plan_handoff':
                    out['plansHandoff'] = self.plan_reviews.resolve(action['token'], owner, chain, g, r, status)
                else:
                    self.plan_reviews._check(self.plan_reviews.reviews, action['token'], owner, chain, g, r)
                    self.plan_reviews.reviews.pop(action['token'], None)
            elif action.get('id') in medigap_profile.FIELDS and action.get('type') in {'choice', 'stage', 'unknown', 'defer', 'edit'}:
                if set(action) - {'type', 'id', 'entity', 'fields'} or action.get('entity', 'profile') != 'profile':
                    raise ProfileError('Use the current Medigap question.')
                before_g, before_r = copy.deepcopy(g), copy.deepcopy(r)
                if action['type'] == 'edit':
                    out = self.response(g, r)
                    out['assessment']['nextQuestion'] = self.contextual_question(g, r, self.question(action['id']))
                else:
                    update = {'id': action['id'], 'entity': 'profile', 'fields':
                        {'choice': 'unknown' if action['type'] == 'unknown' else 'deferred'}
                        if action['type'] in {'unknown', 'defer'} else action.get('fields', {})}
                    self.capture(g, r, update, method='plans_filter' if plans_filter else 'structured')
                    self.resolve_pending(owner, update, g, r)
                    out = self.response(g, r)
                    out['reportedRows'] = self.rows(g, r)
                    if plans_filter:
                        self.retain_presentation(out, presentation)
                    else:
                        out = self.compose_choice(owner, payload, out, before_g, before_r)
                set_target(out['record'], out['assessment'].get('nextQuestion'))
            elif action.get('type') == 'message':
                out = (self.direct_disposition(owner,payload,g,r) or self.direct_local_answer(owner, payload, g, r)
                       or self.message(owner, payload, g, r))
            elif action.get('type') in {'before_enroll_open', 'before_enroll_ack'}:
                # D138: the fixed pre-enrollment step. All twelve CMS topics
                # with their reviewed statements, and the times it was shown
                # and acknowledged. No model call, no profile change.
                if set(action) != {'type'}:
                    raise ProfileError('Use the Before you enroll step.')
                now = datetime.now(timezone.utc).isoformat(timespec='seconds')
                education = (self.memory.education(owner, chain, CONTEXT_POLICY)
                             if payload.get('contextPolicy') == CONTEXT_POLICY else None)
                step = cms_checklist.before_enroll(self.facts, education)
                with self.lock:
                    times = self.before_enroll_times.setdefault((owner, chain), {})
                    if times.get('digest') != step['digest']:
                        times.clear(); times['digest'] = step['digest']
                    times.setdefault('shown_at', now)
                    if action['type'] == 'before_enroll_ack':
                        if not step['complete']:
                            raise ProfileError('The Before you enroll topics are not all available yet.', 409)
                        times['acknowledged_at'] = now
                    step.update(shown_at=times['shown_at'], acknowledged_at=times.get('acknowledged_at'))
                out = self.response(g, r)
                self.retain_presentation(out, presentation)
                out['beforeEnroll'] = step
            elif action.get('type') == 'enrollment_decision':
                # D161: a tapped dashboard decision (not needed, keep what I
                # have, decide later, done). No model call. A tab never comes here.
                try:
                    enrollment_flow.decide(self, g, action, r)
                except ValueError as error:
                    raise ProfileError(str(error)) from None
                out = self.response(g, r)
                self.retain_presentation(out, presentation)
                if conversation_planner.enabled(self):
                    conversation_planner.action_done(self, owner, out, action)
            elif action.get('type') == 'read_concept':
                # Older clients can still open sources without receiving a
                # prepared lesson or recording undelivered teaching.
                if set(action) != {'type', 'id'} or action.get('id') not in self.facts:
                    raise ProfileError('Choose a reviewed explanation.')
                out = self.response(g, r, facts=[copy.deepcopy(self.facts[action['id']])])
                self.retain_presentation(out, presentation)
            elif action.get('type') == 'explanation_preference':
                if (set(action) != {'type', 'value'} or not isinstance(action.get('value'), str)
                        or action.get('value') not in {'new', 'some', 'comfortable'}):
                    raise ProfileError('Choose a supported explanation preference.')
                update = {'id': 'T02', 'entity': 'profile', 'fields': {'choice': action['value']}}
                before_g, before_r = copy.deepcopy(g), copy.deepcopy(r)
                self.apply(g, r, update, 'user_choice')
                record_capture(g, r, before_g, before_r, update, method='structured')
                self.resolve_pending(owner, update, g, r)
                if self.pending_for(owner):
                    self.pending_for(owner)['revision'] = [g['stateVersion'], r['stateVersion']]
                out = self.response(g, r)
                previous_question = (presentation or {}).get('nextQuestion') or {}
                if previous_question.get('id') != 'T02':
                    self.retain_presentation(out, presentation)
                else:
                    set_target(out['record'], out['assessment'].get('nextQuestion'))
            elif action.get('type') in {'unknown','defer'} and self.pending_for(owner):
                # The visible button must resolve the same exact pending fields
                # and item as a typed unknown. The legacy disposition path does
                # not own this visit's clarification queue or aggregate hold.
                pending=self.pending_for(owner)
                target=pending['update']
                if (set(action)-{'type','id','entity'} or action.get('id')!=target['id']
                        or action.get('entity',target.get('entity','profile'))!=target.get('entity','profile')):
                    raise ProfileError('Use the current question when leaving a detail open.')
                words='I don’t know' if action['type']=='unknown' else 'check later'
                out=self.direct_disposition(owner,{**payload,'action':{'type':'message','message':words}},g,r)
                out=self.compose_choice(owner,payload,out,g,r)
            else:
                legacy = {k:v for k,v in payload.items() if k not in {'contextPolicy','continuation','model','aiProvider','plansContext','plansContextPolicy'}}
                if (action.get('type')=='task'
                        or action.get('type') in {'choice','stage'} and action.get('id')=='T01'
                        or action.get('type')=='next' and action.get('step') in {'explore','learn_next'}):
                    set_target(r,None)
                legacy['guide'], legacy['record'] = g, r
                plans_before = self.plans_lists(g) if plans_filter else None
                if action.get('type') == 'stage':
                    current = self.assess(g, r)['nextQuestion']
                    if not current or current['id'] != action.get('id') or current['entity'] != action.get('entity', 'profile'):
                        raise ProfileError('This form changed. Your entries are preserved.', 409)
                    legacy['action'] = {**action, 'type':'choice'}
                out = super().turn(owner, legacy)
                if (action.get('type') == 'task' or action.get('type') in {'choice','stage'}
                        and action.get('id') == 'T01'):
                    self.memory.clear_task_work(owner, chain)
                if (action.get('type') in {'refresh', 'read_concept', 'review_preparation', 'discard_review', 'run_preparation'}
                        or action.get('type') == 'next' and action.get('step') in {'samples', 'resume'}):
                    self.retain_presentation(out, presentation)
                    if self.pending_for(owner):
                        self.pending_for(owner)['revision'] = [out['guide']['stateVersion'], out['record']['stateVersion']]
                if out.get('review'):
                    self.action_chains[out['review']['token']] = (owner,chain)
                if action.get('type') in {'choice','stage'}:
                    self.retire_item_targets(owner,out['guide'],out['record'],action)
                    pending = self.pending_for(owner)
                    if self.touches_pending(pending, legacy['action']):
                        identifier = legacy['action']['id']
                        if identifier in {'RC21','RC22','RC23'} and identifier in out['record']['facts'] and not self.aggregate_still_pending(pending,legacy['action']):
                            out['record']['facts'][identifier]['stale'] = False
                        self.resolve_pending(owner,legacy['action'],out['guide'],out['record'])
                        out['assessment'] = self.assess(out['guide'], out['record'])
                    if self.pending_for(owner):
                        pending=self.pending_for(owner)
                        pending['revision'] = [out['guide']['stateVersion'], out['record']['stateVersion']]
                        out['assessment']['nextQuestion'] = self.eligible(owner, out['guide'], out['record'])[0]['question']
                    captured = copy.deepcopy(legacy['action'])
                    if captured['id'] == 'T04' and captured.get('fields', {}).get('choice') in {'month', 'soonest'}:
                        captured['scope'] = 'intended'
                    record_capture(out['guide'], out['record'], g, r, captured, method='plans_filter' if plans_filter else 'structured')
                    # Capture provenance is now current. Recompute the local
                    # checkpoint so the just-corrected field is not asked again.
                    if not self.pending_for(owner):
                        out['assessment'] = self.assess(out['guide'], out['record'])
                    out['reportedRows'] = self.rows(out['guide'], out['record'])
                    if plans_filter:
                        # Saved silently as the person's report; acknowledged
                        # once by the next chat reply (Nov 9, 2026).
                        self.note_plans_entry(owner, chain, plans_before, out['guide'], legacy['action'])
                if action.get('type')=='refresh' and presentation is None and ensure_state(out['record'])['dialogue']['orientation']=='progress':
                    out['assessment']['nextQuestion']=self.question('T02')
                    set_target(out['record'],out['assessment']['nextQuestion'],orientation='familiarity')
                    out['assessment']['narrative']['opener']=False
                elif action.get('type') in {'choice','stage','edit','resume','task','next'}:
                    set_target(out['record'],out['assessment'].get('nextQuestion'),orientation='answered' if ensure_state(out['record'])['dialogue']['orientation']=='progress' else None)
                sync_agenda(out['guide'],out['record'])
                if (not plans_filter and payload.get('aiConsent') is not True
                        and action.get('type') == 'choice' and action.get('id') == 'T01'
                        and self.assess(g, r)['narrative']['opener']):
                    choice = action['fields'].get('choice')
                    if choice in {'learn', 'compare', 'review'}:
                        out['openingChoice'] = choice
                        if choice == 'learn' and not out['assessment'].get('nextQuestion'):
                            if ux_flow.disabled():
                                question = self.question('T02')
                                out['assessment']['nextQuestion'] = question
                                set_target(out['record'], question, orientation='familiarity')
                            else:
                                # D157 (CV-01): no familiarity warm-up. The reviewed opening
                                # text teaches; the first real question follows it.
                                first = self.eligible(owner, out['guide'], out['record'])
                                if first:
                                    out['assessment']['nextQuestion'] = copy.deepcopy(first[0]['question'])
                                    set_target(out['record'], out['assessment']['nextQuestion'])
                if action.get('type') in {'choice','stage','unknown','defer'}:
                    out=self.compose_choice(owner,payload,out,g,r)
            self.comparisons.attach(out)
            if self._plans_context.get():
                ctx = self._plans_context.get()
                out['plansContext'] = plans_binding(ctx)
                out['plansContext']['profile_changed'] = bool(ctx['input_digest'] and plans_input_digest(out['guide'], out['record']) != ctx['input_digest'])
                try:
                    current_projection, _ = self.plans_service.projection()
                    evidence_changed = (current_projection['projection_digest'] != ctx['projection_digest']
                        or self.plans_service.decision_evidence_digest(ctx['input_digest'])
                           != ctx['decision_evidence_digest'])
                except (OSError, ValueError, KeyError, TypeError):
                    evidence_changed = True
                if evidence_changed:
                    out['reply'] = ''
                    out['planEvidence'] = []
                    out['generated'] = {'status': 'unavailable', 'code': 'plans_evidence_changed', 'retryable': False}
                    out['notice'] = 'Plan evidence changed during this reply. Refresh Plans and send again.'
            out['planReadiness'] = plan_readiness(out['guide'], out['record'], pending=self.pending_for(owner))
            out['medigapProfile'] = medigap_profile.profile(out['guide'])
            out['partDProfile'] = part_d_profile.profile(out['guide'], out['record'])
            if enrollment_flow.enabled(self):
                # D161: every response carries the enrollment view, whichever path
                # built it (a tapped answer, a model reply, a silent decision), so
                # the status line and the two-path dashboard never depend on the
                # kind of turn that came before.
                out['enrollment'] = enrollment_flow.view(self, out['guide'], out['record'])
            if getattr(self, 'eval_recommendations', False):
                out['recommendationInputs'] = recommendation_engine.inputs(
                    out['guide'], out['record'], out['medigapProfile'], out['partDProfile'])
            if payload.get('contextPolicy') == CONTEXT_POLICY:
                # D138: a deterministic account of the twelve CMS pre-enrollment
                # items, from delivered reviewed teaching only. Reading visit
                # memory under any other policy would clear it, so do not.
                out['cmsChecklist'] = cms_checklist.receipt(self.facts, self.memory.education(owner, chain, CONTEXT_POLICY))
            evidence_started = time.monotonic()
            if checks:
                pause = bool(out['assessment'].get('intakePaused') or re.fullmatch(
                    r'(?:please\s+)?(?:pause|stop|no more questions|goodbye)[.!]?', action.get('message','').strip(), re.I))
                continuing_check = action.get('type') in {'check_answer', 'check_back', 'check_edit'}
                checks.attach(owner,out,show_question=not pause and not out.get('review') and not out.get('preparation')
                              and (continuing_check or not conversation_planner.enabled(self)
                                   or conversation_planner.checks_relevant(self, owner, out['guide']))
                              and not metadata(out['record']).get('editing'),
                              count=action.get('type') == 'message')
                if pause:
                    out['conversationCheck']['question'] = None
            if hasattr(self, 'closing_price_read'):
                import closing_options
                closing_options.attach(self, out)
            if self.turn_trace_enabled() and (checks or hasattr(self, 'closing_price_read')):
                out.setdefault('metrics', {}).setdefault('stageMs', {})['local_evidence'] = round(
                    (time.monotonic() - evidence_started) * 1000)
            if action.get('type') == 'message' and enrollment_flow.enabled(self) and not ux_flow.disabled() and not conversation_planner.enabled(self):
                self.park_passed_question(owner, chain, out)
            if conversation_planner.enabled(self):
                if action.get('type') == 'task':
                    conversation_planner.action_done(self, owner, out, action)
                conversation_planner.attach(self, owner, out)
            if (action.get('type') == 'message' and not str(out.get('reply') or '').strip()
                    and not out.get('cards') and not out.get('notice') and not out.get('review')
                    and not out['assessment'].get('nextQuestion')
                    and not (out.get('conversationCheck') or {}).get('results')):
                # A typed message never meets silence (15-profile run, November 13, 2026). A reply that
                # is only the next question is still a reply; nothing at all is not.
                out['reply'] = 'Okay.'
            out['continuation'] = self.bind(owner, out['guide'], out['record'], chain)
            with self.lock:
                generated_conversation(out)
                preparation = out.get('preparation') or {}
                preparation_valid = (preparation.get('kind') == 'preparation'
                    and preparation.get('status') == 'prepared'
                    and preparation.get('inputDigest') == fingerprint(out['guide'], out['record']))
                # Free local controls do not grant AI permission or erase an
                # already permitted visit merely by omitting contextPolicy.
                attach_task_work(out, self.memory.task_work(owner, chain, CONTEXT_POLICY),
                    action=action.get('type'), preparation_valid=preparation_valid)
                if len(self.state_heads)>1024:self.state_heads.pop(next(iter(self.state_heads)))
                self.state_heads[(owner,chain)] = out['continuation']
                # D157: with a 24-hour visit, 128 turns across all visitors would evict a
                # morning visit by afternoon; 2048 holds a full pilot day.
                if len(self.turn_journal) >= 2048:self.turn_journal.pop(next(iter(self.turn_journal)))
                self.turn_journal[key] = {'signature':signature, 'response':copy.deepcopy(out), 'expires':time.time()+VISIT_HISTORY_TTL,
                    'starts_visit': not binding, 'silent': plans_filter or action['type'] in {'before_enroll_open', 'before_enroll_ack', 'enrollment_decision'}}
            self.trace_turn(owner, chain, action, out, turn_started)
            return out
        except (ProfileError, ModelUnavailable):
            raise
        except Exception as error:
            diagnostic = unexpected_failure(error)
            LOGGER.error('Daylight controller failure code=%s type=%s locations=%s',
                         diagnostic['code'], diagnostic['type'], diagnostic['locations'])
            sent = payload.get('action') if isinstance(payload.get('action'), dict) else {}
            self.trace_turn(owner, self.current_chain.get(owner) or '', sent, None, turn_started, failure=diagnostic)
            if sent.get('type') == 'message':
                # A typed message never ends in a bare server error. Nothing was saved, the
                # browser keeps the words in the box, and the person can send them again.
                raise ModelUnavailable(TURN_TOO_LONG if time.monotonic() - turn_started > 30 else TURN_FAILED) from error
            raise
        finally:
            with self.lock:self.natural_active.discard(owner)

    def save(self, token, csrf, payload):
        """Save both real report envelopes atomically, never a false confirmation."""
        if set(payload) != {'guide','record','expectedVersion','expectedReadinessVersion','operationId'}:
            raise ProfileError('Use the complete save request.')
        g, r = self.validate(payload['guide'], payload['record'])
        self.profiles.require(token, csrf)
        if not g['preferences'].get('saveGuide'):raise ProfileError('Choose saving before storing information.')
        expected, expected_r, op = payload['expectedVersion'], payload['expectedReadinessVersion'], payload['operationId']
        if type(expected) is not int or type(expected_r) is not int or not re.fullmatch(r'[A-Za-z0-9-]{10,80}', str(op)):
            raise ProfileError('Use current save versions and operation key.')
        g, r = prune_for_storage(g, r)
        signature = fingerprint(g, r);h = self.profiles.digest(token)
        with self.profiles.lock, self.profiles.db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT signature,version FROM requests WHERE token_hash=? AND op=?', (h,op)).fetchone()
            previous_r = db.execute('SELECT signature,version FROM readiness_requests WHERE token_hash=? AND op=?', (h,op)).fetchone()
            if previous or previous_r:
                if not previous or not previous_r or previous[0] != signature or previous_r[0] != signature:raise ProfileError('Save operation already used.',409)
                return {'saved':True,'version':previous[1],'readinessVersion':previous_r[1],'replayed':True}
            guest = db.execute('SELECT version,expires FROM guests WHERE token_hash=?', (h,)).fetchone()
            record = db.execute('SELECT version FROM readiness WHERE token_hash=?', (h,)).fetchone()
            if not guest or guest[1] <= self.profiles.clock():raise ProfileError('Guest session expired.',401)
            if guest[0] != expected or (record[0] if record else 0) != expected_r:raise ProfileError('Another tab changed the saved copy. Your current reports are preserved.',409)
            version, rv = expected+1, expected_r+1
            db.execute('UPDATE guests SET version=?,guide=? WHERE token_hash=?', (version,json.dumps(g),h))
            db.execute('INSERT INTO readiness VALUES(?,?,?) ON CONFLICT(token_hash) DO UPDATE SET version=excluded.version,record=excluded.record', (h,rv,json.dumps(r)))
            db.execute('INSERT INTO requests VALUES(?,?,?,?)', (h,op,version,signature))
            db.execute('INSERT INTO readiness_requests VALUES(?,?,?,?)', (h,op,signature,rv))
            db.execute('DELETE FROM requests WHERE token_hash=? AND version<?',(h,max(0,version-20)))
            db.execute('DELETE FROM readiness_requests WHERE token_hash=? AND version<?',(h,max(0,rv-20)))
        return {'saved':True,'version':version,'readinessVersion':rv,'omittedSensitive':not g['preferences'].get('saveSensitive',False)}
