"""D86 natural conversation over the retained, read-only dependency engine.

Reported facts resolve before prose is generated. Visit journals contain no raw
messages, saving stays optional, and actual preparation keeps its own authority.
"""
import copy
import hashlib
import hmac
import json
import logging
from pathlib import Path
import re
import secrets
import time

from advisor_flow import AdvisorConversation, fingerprint
from adaptive_flow import AdaptiveConversation, metadata, FIELD, Q, explicit_task, month
from chat import ModelUnavailable
from guest_profiles import ProfileError, for_storage
from profile_readiness import reject_sensitive
from situation import FIELDS as SITUATION_FIELDS, observations
from advisor_memory import VisitMemory, CONTEXT_POLICY, HISTORY_LIMIT as VISIT_HISTORY_LIMIT, HISTORY_TTL as VISIT_HISTORY_TTL
from education import catalog_context, learning_context, concepts_for_lesson, plan_update
from natural_agent import NaturalAgent
from comparison_service import ComparisonService
from controller_diagnostics import unexpected_failure
from narrative_agent import provider_failure_message
from natural_state import (ensure_state, legacy_projection, restore_state,
                           record_capture, classify_update, classify_situation,
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
COMPOSITION_CODES = frozenset({'ungrounded_literal', 'ungrounded_entity', 'invalid_reference',
    'unsupported_finding', 'missing_evidence', 'missing_report_reference', 'missing_coverage_reference',
    'missing_worker_reference', 'missing_progress_reference', 'format_or_duplicate_question',
    'unavailable', 'transport_or_format', 'provider_failure', 'composition_unavailable'})
LOGGER = logging.getLogger(__name__)
QUESTION_TOPICS = {'T02':'learning','T04':'timing','T05':'current_coverage','T06':'doctors',
    'T07':'drugs','T08':'travel','T09':'total_cost','T10':'other','RC09':'current_coverage',
    'RC11':'timing','RC21':'doctors','RC22':'drugs','RC23':'drugs','RC25':'total_cost'}
TOPIC_FACTS = {'doctors':'checks','drugs':'drugbasics','total_cost':'costs','bills':'costs',
    'travel':'checks','flexibility':'switching','timing':'dates','learning':'basics',
    'coverage_paths':'routesintro','current_coverage':'basics','other':'checks'}
FACT_TOPICS = {'routesintro':'coverage_paths','options':'coverage_paths','checks':'doctors',
    'drugbasics':'drugs','drugs':'drugs','costs':'total_cost','medical_limit':'bills',
    'dates':'timing','switching':'flexibility','original':'coverage_paths','advantage':'coverage_paths'}


class NaturalConversation(AdvisorConversation):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = NaturalAgent.from_agent(self.agent)
        self.progress_fact_ids = frozenset(self.facts)
        for fact in json.loads((Path(__file__).parent / "advisor-evidence.json").read_text())["facts"]:
            self.facts[fact["id"]] = copy.deepcopy(fact)
            self.agent.facts[fact["id"]] = copy.deepcopy(fact)
        self.turn_journal = {}
        self.natural_active = set()
        self.clarifications = {}
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

    def response(self, g, r, reply='', **extras):
        # Derived comparison data stays outside the two saved profile records.
        # Final turn attachment rebinds after provenance/composition bookkeeping.
        return self.comparisons.attach(super().response(g, r, reply, **extras))

    def recent_exchanges(self, owner, task, policy):
        # v3 grants bounded visit continuity across topic changes. Older scoped
        # permission never silently expands to this new conversation context.
        return self.memory.recent(owner, self.current_chain.get(owner), policy)

    def remember_exchange(self, owner, message, out, policy):
        if self.fixture:
            return
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
            education_record=working.get('education_record'))

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
        if id in {'orientation','S_AGE65','S_RETIREMENT'}:
            wording={'orientation':'Where are you with Medicare so far?', 'S_AGE65':'Which month will you turn 65?',
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
        if target and target['id'] in Q and self.target_relevant(guide,record,target['id']) and not (edit or metadata(record).get('editing')):
            identifier = target['id']
            missing = (self.value(guide, FIELD[identifier]) is None and identifier not in metadata(record)['baselineDispositions']) if identifier in FIELD else not self.report(record, identifier) and identifier not in record['dispositions']
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
        return a

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

    def apply(self, guide, record, update, source='user_choice'):
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
        try:
            return super().apply(guide, record, update, source)
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
        if identifier=='T05':ids+=['basics','dates','checks']
        elif identifier in {'T04','RC11'}:ids+=['dates','routesintro','checks']
        elif task in {'compare','review','providers'}:ids+=['routesintro','checks','costs']
        elif task in {'drug_coverage','drug_pricing'}:ids+=['drugbasics','costs','checks']
        else:ids+=['basics','parts','routesintro']
        return list(dict.fromkeys(id for id in ids if id in self.facts))[:3]

    def eligible(self, owner, g, r, *, allow_orientation=False, answer_only=False, facts=(), priority_changed=False):
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
            question = self.question(update['id'], fields or None, update.get('entity', 'profile'))
            return [{'id': question['id'], 'question': question, 'topic': QUESTION_TOPICS.get(question['id'], ''),
                'purpose': 'Clarify this unresolved report before using it. Do not assert either candidate.',
                'priority': 0, 'required': True}]
        candidates = []
        def add(question, priority=1, purpose=None):
            if not question or any(item['question']['id'] == question['id'] for item in candidates):
                return
            identifier = question['id']
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
            # These baseline meanings have no external lookup dependency.
            for identifier in ('T05', 'T04', 'T03', 'T06', 'T07', 'T08', 'T09', 'T10'):
                if self.value(g, FIELD[identifier]) is None and identifier not in metadata(r)['baselineDispositions']:
                    q = self.provider_detail_question() if identifier == 'T06' and 'doctors' in (self.value(g, 'needs.priorities') or []) else self.question(identifier)
                    add(q, 2)
        if candidates and self.value(g, 'knowledge.general') is None and 'T02' not in metadata(r)['baselineDispositions']:
            add(self.question('T02'), 2,
                'Optional familiarity question only if needed to calibrate explanations; do not make it a required intake step.')
        # Current insurance is a useful first dependency for an age-65 timing
        # concern. Birthday does not establish desired start or enrollment.
        if self.value(g, 'situation.age65'):
            for item in candidates:
                if item['id'] == 'T05': item['priority'] = 0
        return sorted(candidates, key=lambda item: item['priority'])[:12]

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
                'RC23':'drug_pricing','T09':'costs','T10':'costs'}
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
            core = {'guide.situation.age65', 'guide.situation.retirement', 'guide.coverage.current'}
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
        return context

    def permitted_question(self, question, policy):
        if not question or policy in {CONTEXT_POLICY,PREVIOUS_CONTEXT_POLICY,LEGACY_CONTEXT_POLICY}:return copy.deepcopy(question)
        # Generated/derived question labels may echo an earlier private value.
        # Old consent covers only the public meaning, not that echoed value.
        return self.question(question['id'], [f['key'] for f in question.get('fields',[])] or None,
                             question.get('entity','profile'))

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

    def advisor_brief(self, owner, g, r, policy, candidates, goal=None):
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
        return brief

    def compose_response(self, owner, out, message, moves, policy, request_id, reservation, previous_dialogue=None,
                         submitted_answer=None, goal=None, priority_changed=False, accepted_reports=(), resolved_changes=(),
                         education_request=None):
        context_question = next((item['question'] for item in moves if item.get('question')), None)
        context = self.context(out['guide'], out['record'], policy, context_question)
        learning = self.memory.education(owner, self.current_chain.get(owner), policy)
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
        context['education_context'] = {
            'catalog': catalog_context(), 'learning': learning_context(learning),
            'requested_revisit': requested_revisit, 'revisit_concepts': revisit_concepts,
            'turn_kind': 'submitted_answer' if submitted_answer is not None else 'message',
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
            context['advisor_brief'] = self.advisor_brief(owner, out['guide'], out['record'], policy, moves, goal)
            context['recent_exchanges'] = self.recent_exchanges(owner, metadata(out['record'])['task'], policy)
            reports = {item['id']: item for item in context['reports']}
            reports.update({item['id']: item for item in accepted_reports})
            context['reports'] = list(reports.values())
            context['known'] = [item for item in context['known'] if item['id'] not in reports]
        if previous_dialogue is not None:
            context['dialogue'] = copy.deepcopy(previous_dialogue)
        moves = [{**item, 'question': self.permitted_question(item.get('question'), policy)} for item in moves]
        context['current_message'] = message
        # The advisor gets relevant reviewed material even when no explicit
        # educational request was classified by the extractor.
        evidence = {fact['id']: fact for fact in out.get('facts', [])}
        ids = [ref for item in catalog_context()['concepts'] if item['concept_id'] in revisit_concepts
               for ref in item['evidence_refs']]
        ids += self.teaching_candidates(out['guide'], out['record'], context_question)
        ids += ['routesintro', 'basics', 'dates', 'enrollment_intro']
        for identifier in list(dict.fromkeys(ids))[:6]:
            if identifier in self.facts:
                evidence[identifier] = self.facts[identifier]
        context['evidence'] = copy.deepcopy(list(evidence.values()))
        pending = self.pending_for(owner)
        context['uncertainties'] = [{'id': pending['update']['id'], 'status': 'needs_clarification'}] if pending else []
        if pending:
            identifier = pending['update']['id']
            prefixes = ['guide.' + FIELD[identifier]] if identifier in FIELD else ['readiness.' + identifier + '.']
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
        self.comparisons.attach(out)
        context['comparison_status'] = self.comparisons.context_status(out['comparison'])
        recovery_question = copy.deepcopy(context_question)
        out['assessment']['conversationOpen'] = True
        out['assessment']['intakePaused'] = False
        try:
            composed = self.agent.compose(owner, context, moves, request_id, reservation)
            target = composed.get('question_target')
            selected = next((item for item in moves if item['question']['id'] == target), None) if target else None
            if target and not selected:
                raise ModelUnavailable('The next question could not be checked.')
            education_output = copy.deepcopy(composed['education'])
            if not composed['reply'].strip():
                # A question, citation or proposed diagram alone is not a
                # delivered explanation. Open clarification may still survive.
                education_output['updates'] = [item for item in education_output['updates']
                    if item['depth'] == 'needs_clarification']
                education_output['visual'] = 'none'
            planned = plan_update(learning, education_output, composed['evidence_refs'],
                requested_revisit=requested_revisit, revisit_concepts=revisit_concepts,
                event_id=request_id)
            repeated_finite_lesson = bool(submitted_answer is not None and selected
                and composed['education']['purpose'] in {'teach', 'recap'}
                and composed['education']['updates'] and not planned['accepted_updates']
                and not composed.get('education_metadata_dropped', False)
                and all(item['concept_id'] in learning['concepts']
                        and learning['concepts'][item['concept_id']]['depth'] != 'not_covered'
                        and item['reason'] in {'new', 'requested_revisit'}
                        for item in composed['education']['updates'])
                and set(planned['issues']) <= {'redundant_education_delivery', 'unrequested_education_revisit',
                                              'redundant_or_unrelated_education_visual'}
                and bool(set(planned['issues']) & {'redundant_education_delivery', 'unrequested_education_revisit'}))
            if repeated_finite_lesson:
                # The ordinary answer already resolved its field. Keep its
                # useful next question instead of replaying an obsolete lesson
                # or failing the turn. No replacement prose is invented.
                composed['reply'] = ''
                composed['evidence_refs'] = []
                composed['education_followups'] = []
            out['reply'] = composed['reply']
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
            out['assessment']['conversationOpen'] = bool(not selected and (moves or self.report(out['record'], 'RC01').get('choice') == 'research' or metadata(out['record'])['task'] == 'learn'))
            out['generated'] = {'status': 'complete', 'move': target or 'answer'}
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
            working = {'agenda_update': composed.get('agenda_update', {}), 'education_record': planned['record']}
            if goal and len(goal) <= 200: working['goal'] = goal
            out['_advisor_memory'] = working
            out['education'] = learning_context(planned['record'])
        except (ModelUnavailable, ProfileError, ValueError) as error:
            out.pop('_advisor_memory', None)
            out.pop('education', None)
            out['reply'] = ''
            out['facts'] = []
            out['advisor'] = {'visual': 'none', 'teachingFactIds': [], 'sources': []}
            out['assessment']['nextQuestion'] = recovery_question
            out['notice'] = 'I couldn’t finish that reply. You can keep going.'
            diagnostic = getattr(self.agent.local, 'provider_failure', None)
            if diagnostic and diagnostic.get('provider_code') in {'credit_balance_exhausted', 'insufficient_quota'}:
                out['notice'] = provider_failure_message(diagnostic, accepted=True)
            code = getattr(self.agent.local, 'last_composition_error', None) or ('provider_failure' if diagnostic else 'composition_unavailable')
            if code not in COMPOSITION_CODES: code = 'composition_unavailable'
            out['generated'] = {'status': 'unavailable', 'retryable': False, 'reason': str(error)[:220], 'code': code}
            if diagnostic: out['generated']['providerFailure'] = copy.deepcopy(diagnostic)
            with self.lock:
                self.composition_diagnostics.append({'code': code, 'questionAvailable': bool(recovery_question), 'intakePaused': False})
                self.composition_diagnostics = self.composition_diagnostics[-50:]
            LOGGER.warning('Daylight composition unavailable code=%s question_available=%s', code, bool(recovery_question))
        out['metrics']['llmCalls'] += 1
        out['metrics']['stageMs'] = copy.deepcopy(getattr(self.agent.local, 'stage_timings', {}))
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
        if payload.get('aiConsent') is not True and not self.fixture:
            raise ProfileError('AI transfer needs your permission. The choices and reviewed explanations still work.', 428)
        if not self.fixture and (not self.agent.enabled or not self.agent.client.available):
            raise ModelUnavailable('Live AI is unavailable. Your message is preserved; the choices and reviewed explanations still work.')
        policy = payload.get('contextPolicy')
        current = self.assess(g, r)['nextQuestion']
        ns = ensure_state(r)
        if ns.get('agenda',{}).get('lastMove') and ns['dialogue']['lastTarget'] is None:
            current=None
        priorities_before=copy.deepcopy(g['fields'].get('needs.priorities'))
        previous_dialogue=copy.deepcopy(ns['dialogue'])
        # A question displayed in the previous response has the same underlying
        # target even though its generated wording is intentionally not stored.
        previous_orientation = ns['dialogue']['orientation'] == 'progress'
        if previous_orientation:
            current = self.question('T02')
            set_target(r, current, orientation='familiarity')
        pending = self.pending_for(owner)
        if pending and pending['revision'] == [g['stateVersion'], r['stateVersion']]:
            u = pending['update']
            current = self.question(u['id'], [k for k in u['fields'] if k != 'choice'] or None, u.get('entity', 'profile'))
        if self.fixture:
            # Synthetic mode remains explicitly labeled and makes no AI claim.
            result = self.fixture_result(message, current)
            result['updates'] = [u for u in result['updates'] if u['id'] not in {'T05','RC09'} or not observations(message)]
            reservation = None
        else:
            reservation = self.agent.reserve_turn(stages=('extract', 'compose'))
        before = [g['stateVersion'], r['stateVersion']]
        report_snapshot = (copy.deepcopy(g), copy.deepcopy(r))
        try:
            if not self.fixture:
                context = self.context(g, r, policy, current)
                recent = self.recent_exchanges(owner, metadata(r)['task'], policy)
                safe_reports = {x['id'][6:]:x['value'] for x in context['reports'] if x['id'] in {'guide.intent.goal','guide.knowledge.general','guide.subject.role','guide.coverage.current'} and x['status'] in {'reported','derived'}}
                context.update(task=metadata(r)['task'], preparing=metadata(r)['preparing'],
                               lastFactIds=metadata(r)['lastFactIds'], activeQuestion=self.permitted_question(current,policy),
                               definitions=self.agent.definitions, safeReports=safe_reports, pending=False)
                context['teachingCandidates']=self.teaching_candidates(g,r,current)
                if policy == CONTEXT_POLICY:
                    context['advisor_brief'] = self.advisor_brief(owner, g, r, policy, self.eligible(owner, g, r))
                if policy == CONTEXT_POLICY:
                    context['recent_exchanges'] = recent
                    context['education_context'] = {'learning': learning_context(
                        self.memory.education(owner, self.current_chain.get(owner), policy))}
                extraction_guide, _ = legacy_projection(g, r)
                result = self.agent.extract(owner, message, extraction_guide, context, payload['requestId'], reservation)
            m = metadata(r)
            # Interpretation proposes reports; it does not choose a hidden
            # conversation mode. The retained task is only a dependency lens.
            goal_quote = result.get('goal_quote', '')
            if not isinstance(goal_quote, str) or len(goal_quote) > 200 or goal_quote.casefold() not in message.casefold():
                goal_quote = ''
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
            # Dependencies first, independent of extraction order.
            updates.sort(key=lambda u:0 if u['id'] == 'RC01' else 1 if u['id'] in FIELD else 2)
            ambiguous = [];accepted_updates=[]
            for update in updates:
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
                if classification['decision'] == 'reject':continue
                if classification['decision'] == 'clarify':
                    if update['id'] == 'T01' and goal_quote:
                        continue
                    ambiguous.append(update)
                    continue
                try:
                    self.capture(g, r, update, resolve_aggregate=resolves_pending and not self.aggregate_still_pending(pending, update, (resolution_update,)))
                    accepted_updates.append(update)
                    self.retire_item_targets(owner,g,r,update)
                    if resolves_pending:
                        self.resolve_pending(owner, update, g, r)
                        if resolution_update is not update:
                            self.resolve_pending(owner, resolution_update, g, r)
                        pending = self.pending_for(owner)
                except ProfileError:
                    ambiguous.append(update)
            # The live model supplies semantic observations; the phrase
            # recognizer remains only for explicitly synthetic fixture mode.
            proposed_situation = observations(message, self.value(g, 'subject.role')) if self.fixture else {}
            situation_meta = {}
            conflicting_kinds = set()
            for proposal in result.get('situation_proposals', []):
                if proposal.get('subject') != 'beneficiary' or proposal.get('scope') == 'unknown':
                    continue
                kind = proposal['kind']
                value = ({'month': proposal['month'], 'year': proposal['year']} if kind == 'age65'
                         else {'status': proposal['status'], 'when': proposal['when']})
                if kind in proposed_situation and proposed_situation[kind] != value:
                    conflicting_kinds.add(kind)
                proposed_situation[kind] = value
                situation_meta[kind] = proposal
            support = message
            if current and current['id'] == 'S_AGE65' and re.fullmatch(r'(?i)(January|February|March|April|May|June|July|August|September|October|November|December)(?:\s+((?:19|20)\d{2}))?[.!]?', message):
                match = re.fullmatch(r'(?i)([a-z]+)(?:\s+((?:19|20)\d{2}))?[.!]?', message)
                names = 'january february march april may june july august september october november december'.split()
                proposed_situation['age65'] = {'month': names.index(match[1].lower()) + 1, 'year': int(match[2]) if match[2] else None}
                support = 'I turn 65 in ' + message
            elif current and current['id'] == 'S_RETIREMENT' and re.fullmatch(r'(?i)(?:retired|retiring|planning to retire|(?:still )?working)[.!]?', message):
                proposed_situation['retirement'] = {'status': 'working' if 'working' in message.lower() else 'retiring' if 'retiring' in message.lower() or 'planning' in message.lower() else 'retired', 'when': ''}
                support = 'I am ' + message
            uncertain_kinds = {kind for kind, item in situation_meta.items() if item.get('uncertain')}
            situation={}
            for kind, value in proposed_situation.items():
                situation_id='S_'+kind.upper()
                old=g['fields'].get(SITUATION_FIELDS[kind])
                proposal = situation_meta.get(kind, {})
                scoped_support = proposal.get('quote') or support
                resolution=classify_situation(scoped_support,kind,value,existing=old)
                if resolution['reason'] == 'conflicting_report' and proposal.get('correction'):
                    resolution = classify_situation(scoped_support, kind, value)
                if kind in conflicting_kinds:
                    resolution = {'decision':'clarify','reason':'multiple_situation_reports','value':value}
                if kind in uncertain_kinds:
                    resolution = {'decision':'clarify','reason':'tentative','value':value}
                if resolution['decision']=='clarify' and resolution['reason']=='conflicting_report' and pending and pending['update']['id']==situation_id:
                    resolution=classify_situation(support,kind,value)
                if resolution['decision']=='reject':continue
                if resolution['decision']=='clarify':
                    ambiguous.append({'id':situation_id,'fields':{},'entity':'profile'})
                    continue
                value=resolution['value'];situation[kind]=value
                before_g, before_r = copy.deepcopy(g), copy.deepcopy(r)
                self.put(g, SITUATION_FIELDS[kind], value, 'user_text')
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
            priority_changed=bool(priorities_before and any(x['id']=='T10' for x in accepted_updates)
                and priorities_before.get('value')!=g['fields'].get('needs.priorities',{}).get('value'))
            moves = self.eligible(owner, g, r, facts=facts, priority_changed=priority_changed)
            out = self.response(g, r, facts=facts, expectedStateVersion=before[0], expectedReadinessRevision=before[1],
                                metrics={'llmCalls':0 if self.fixture else 1, 'synthetic':self.fixture})
            # Commit the resolved receipt before composition, including the
            # generated-question-independent target and recoverable state.
            out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question']) if moves else None
            out['assessment']['narrative']['opener'] = False
            out['reply'] = 'Your details are here. We can continue from this point.'
            set_target(out['record'], out['assessment'].get('nextQuestion'),
                       orientation='familiarity' if bool(moves and moves[0]['id']=='T02') else None)
            out['continuation'] = self.bind(owner, out['guide'], out['record'], self.current_chain[owner])
            self.comparisons.attach(out)
            with self.lock:
                key = (owner, payload['requestId'])
                self.turn_journal[key] = {'signature':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
                                         'response':copy.deepcopy(out), 'expires':time.time()+3600, 'stage':'resolved'}
                self.state_heads[(owner,self.current_chain[owner])] = out['continuation']
            if self.fixture:
                out['reply'] = 'Synthetic conversation: the supplied reports are captured.'
                if moves: out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question'])
                out['assessment']['narrative']['opener'] = False
            else:
                delta = self.report_delta(*report_snapshot, out['guide'], out['record'], accepted_updates)
                out = self.compose_response(owner, out, message, moves, policy, payload['requestId'], reservation, previous_dialogue, goal=goal_quote or None, priority_changed=priority_changed,
                    accepted_reports=delta, resolved_changes=self.resolved_changes(*report_snapshot, delta),
                    education_request=result.get('education_request'))
            if out.get('facts'):
                shown=[fact['id'] for fact in out['facts']]
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
            self.remember_exchange(owner, message, out, policy)
            return out
        finally:
            if reservation:reservation.close()

    def direct_disposition(self, owner, payload, g, r):
        """An exact unknown/defer needs neither transfer nor another model call."""
        if set(payload['action'])!={'type','message'} or not isinstance(payload['action'].get('message'),str):return None
        message=payload['action']['message'].strip()
        if re.fullmatch(r"(?i)(?:I don['’]t know|I do not know|not sure|unknown)[.!]?",message):kind='unknown'
        elif re.fullmatch(r'(?i)(?:check later|add later|defer|skip this|skip that)[.!]?',message):kind='defer'
        else:return None
        pending=self.pending_for(owner)
        if (not pending and r.get('natural',{}).get('agenda',{}).get('lastMove')
                and r['natural']['dialogue']['lastTarget'] is None):return None
        orientation=ensure_state(r)['dialogue']['orientation']=='progress'
        target=pending['update'] if pending else None
        current=self.question(target['id'], [key for key in target['fields'] if key!='choice'] or None, target.get('entity','profile')) if pending else self.question('T02') if orientation else self.assess(g,r)['nextQuestion']
        if not current:return None
        if current['id'] in Q and pending:
            state='unknown' if kind=='unknown' else 'deferred'
            fields={key:state for key in target['fields'] if key!='choice'} or {'choice':state}
            self.capture(g,r,{'id':target['id'],'entity':target.get('entity','profile'),'fields':fields},
                         resolve_aggregate=not self.aggregate_still_pending(pending,target))
            out=self.response(g,r,'That’s okay. We can work with what you know.')
        elif current['id'] in Q:
            legacy={k:v for k,v in payload.items() if k not in {'contextPolicy','continuation'}}
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
        set_target(out['record'],out['assessment'].get('nextQuestion'))
        return out

    def compose_choice(self,owner,payload,out,before_g,before_r):
        """A deliberate finite answer uses resolution + one composition only."""
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
                resolved_changes=self.resolved_changes(before_g, before_r, delta))
        except (ModelUnavailable,ProfileError,ValueError) as error:
            out['reply']='';out['notice']=str(error)[:220]
            out['advisor']={'visual':'none','teachingFactIds':[],'sources':[]}
            out['generated']={'status':'unavailable','retryable':False,'code':'composition_unavailable'}
            out['assessment']['intakePaused']=bool(not moves and self.assess(out['guide'],out['record']).get('nextQuestion'))
            out['assessment']['conversationOpen']=metadata(out['record'])['task']=='learn'
        finally:
            if reservation:reservation.close()
        set_target(out['record'],out['assessment'].get('nextQuestion'))
        if self.pending_for(owner):
            self.pending_for(owner)['revision']=[out['guide']['stateVersion'],out['record']['stateVersion']]
        self.validate(out['guide'],out['record'])
        self.remember_exchange(owner,message,out,CONTEXT_POLICY)
        return out

    def turn(self, owner, payload):
        allowed = {'guide','record','action','requestId','aiConsent','pendingId','contextPolicy','continuation'}
        if not isinstance(payload, dict) or set(payload) - allowed or not re.fullmatch(r'[A-Za-z0-9-]{10,80}', str(payload.get('requestId', ''))):
            raise ProfileError('Use a current conversation request.')
        key = (owner, payload['requestId'])
        signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with self.lock:
            self.revoked_owners = {key: expiry for key, expiry in self.revoked_owners.items() if expiry > time.time()}
            if owner in self.revoked_owners:
                raise ProfileError('This guest session was deleted. Start a fresh visit before continuing.', 401)
            self.turn_journal = {k:v for k,v in self.turn_journal.items() if v['expires'] > time.time()}
            if key in self.turn_journal:
                entry = self.turn_journal[key]
                if entry['signature'] != signature:raise ProfileError('This request key belongs to another turn.', 409)
                cached = copy.deepcopy(entry['response'])
                continuation = cached.get('continuation')
                cached_chain = continuation.split('.')[0] if continuation else None
                historical = bool(continuation and (
                    self.current_chain.get(owner) != cached_chain or
                    self.state_heads.get((owner, cached_chain)) != continuation))
                # Recheck derived authority without extracting/composing again.
                return self.comparisons.attach(cached, historical=historical, replay=True)
            if owner in self.natural_active:raise ProfileError('Your earlier message is still being processed. Your work is preserved.', 409)
            self.natural_active.add(owner)
        try:
            g, r = self.validate(payload['guide'], payload['record'])
            binding = payload.get('continuation')
            action = payload.get('action', {})
            if not isinstance(action, dict):raise ProfileError('Use a supported conversation action.')
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
            presentation = self.current_presentation(owner, binding)
            if action.get('type') == 'start':
                self.memory.clear(owner, chain)
            if action.get('type') in {'run_preparation','accept_review','discard_review'} and self.action_chains.get(action.get('token')) != (owner,chain):
                raise ProfileError('This authorization belongs to an earlier conversation. Review the current action again.',409)
            if action.get('type') == 'message':
                out = self.direct_disposition(owner,payload,g,r) or self.message(owner, payload, g, r)
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
                legacy = {k:v for k,v in payload.items() if k not in {'contextPolicy','continuation'}}
                if (action.get('type')=='task'
                        or action.get('type') in {'choice','stage'} and action.get('id')=='T01'
                        or action.get('type')=='next' and action.get('step') in {'explore','learn_next'}):
                    set_target(r,None)
                legacy['guide'], legacy['record'] = g, r
                if action.get('type') == 'stage':
                    current = self.assess(g, r)['nextQuestion']
                    if not current or current['id'] != action.get('id') or current['entity'] != action.get('entity', 'profile'):
                        raise ProfileError('This form changed. Your entries are preserved.', 409)
                    legacy['action'] = {**action, 'type':'choice'}
                out = super().turn(owner, legacy)
                if (action.get('type') in {'read_concept', 'review_preparation', 'discard_review', 'run_preparation'}
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
                    record_capture(out['guide'], out['record'], g, r, captured, method='structured')
                    out['reportedRows'] = self.rows(out['guide'], out['record'])
                if action.get('type')=='refresh' and ensure_state(out['record'])['dialogue']['orientation']=='progress':
                    out['assessment']['nextQuestion']=self.question('T02')
                    set_target(out['record'],out['assessment']['nextQuestion'],orientation='familiarity')
                    out['assessment']['narrative']['opener']=False
                elif action.get('type') in {'choice','stage','edit','resume','task','next'}:
                    set_target(out['record'],out['assessment'].get('nextQuestion'),orientation='answered' if ensure_state(out['record'])['dialogue']['orientation']=='progress' else None)
                sync_agenda(out['guide'],out['record'])
                if action.get('type') in {'choice','stage','unknown','defer'}:
                    out=self.compose_choice(owner,payload,out,g,r)
            self.comparisons.attach(out)
            out['continuation'] = self.bind(owner, out['guide'], out['record'], chain)
            with self.lock:
                if action.get('type') == 'read_concept':
                    self.record_reviewed_lesson(owner, chain, out, action['id'], payload['requestId'])
                if len(self.state_heads)>1024:self.state_heads.pop(next(iter(self.state_heads)))
                self.state_heads[(owner,chain)] = out['continuation']
                if len(self.turn_journal) >= 128:self.turn_journal.pop(next(iter(self.turn_journal)))
                self.turn_journal[key] = {'signature':signature, 'response':copy.deepcopy(out), 'expires':time.time()+3600}
            return out
        except (ProfileError, ModelUnavailable):
            raise
        except Exception as error:
            diagnostic = unexpected_failure(error)
            LOGGER.error('Daylight controller failure code=%s type=%s locations=%s',
                         diagnostic['code'], diagnostic['type'], diagnostic['locations'])
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
