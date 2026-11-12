"""D86 natural conversation over the retained, read-only dependency engine.

Reported facts resolve before prose is generated. Visit journals contain no raw
messages, saving stays optional, and actual preparation keeps its own authority.
"""
import copy
import hashlib
import hmac
import json
import logging
import re
import secrets
import time

from advisor_flow import AdvisorConversation, fingerprint
from adaptive_flow import AdaptiveConversation, metadata, FIELD, Q, explicit_task, month
from chat import ModelUnavailable
from guest_profiles import ProfileError, for_storage
from profile_readiness import reject_sensitive
from situation import FIELDS as SITUATION_FIELDS, observations
from natural_agent import NaturalAgent
from narrative_agent import provider_failure_message
from natural_state import (ensure_state, legacy_projection, restore_state,
                           record_capture, classify_update, classify_situation,
                           build_context, set_target, prune_for_storage, sync_agenda,
                           apply_agenda_reports, agenda_context, record_advisor_move)

CONTEXT_POLICY = 'natural-context-v2'
LEGACY_CONTEXT_POLICY = 'natural-context-v1'
VISIT_HISTORY_LIMIT = 3000
VISIT_HISTORY_TTL = 3600
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
        self.turn_journal = {}
        self.natural_active = set()
        self.clarifications = {}
        self.binding_key = secrets.token_bytes(32)
        self.state_heads = {}
        self.current_chain = {}
        self.action_chains = {}
        # Dialogue is useful for continuity, but is never profile authority or
        # saved data. Browser-authored history is deliberately unsupported.
        self.visit_memory = {}
        self.composition_diagnostics = []

    def recent_exchanges(self, owner, task, policy):
        with self.lock:
            self.visit_memory = {key:value for key,value in self.visit_memory.items()
                                 if value['expires'] > time.time()}
            key = (owner, self.current_chain.get(owner))
            if policy != CONTEXT_POLICY:
                self.visit_memory.pop(key, None)
                return []
            memory = self.visit_memory.get(key, {})
            return [copy.deepcopy(item['exchange']) for item in memory.get('exchanges', [])
                    if item['task'] == task]

    def remember_exchange(self, owner, message, out, policy):
        if policy != CONTEXT_POLICY or self.fixture:
            return
        key = (owner, self.current_chain[owner])
        exchange = {'user': message, 'assistant': out.get('reply', ''),
                    'question': (out['assessment'].get('nextQuestion') or {}).get('question', '')}
        task = metadata(out['record'])['task']
        with self.lock:
            memory = self.visit_memory.setdefault(key, {'exchanges': [], 'expires': 0})
            # Changing focus does not carry prior sensitive discourse into the
            # new task. Resolved profile context has its own relevance rules.
            exchanges = [item for item in memory['exchanges'] if item['task'] == task]
            exchanges.append({'task': task, 'exchange': exchange})
            exchanges = exchanges[-3:]
            while len(exchanges) > 1 and sum(len(text) for item in exchanges for text in item['exchange'].values()) > VISIT_HISTORY_LIMIT:
                exchanges.pop(0)
            memory.update(exchanges=exchanges, expires=time.time() + VISIT_HISTORY_TTL)
            if len(self.visit_memory) > 128:
                self.visit_memory.pop(next(iter(self.visit_memory)))

    def pending_for(self, owner):
        return self.clarifications.get((owner,self.current_chain.get(owner)))

    def clear_pending(self, owner):
        self.clarifications.pop((owner,self.current_chain.get(owner)),None)

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
        if (target and target['id'] in {'T06','T07','T09','T10'}
                and not (edit or metadata(record).get('editing'))
                and self.value(guide,FIELD[target['id']]) is None
                and target['id'] not in metadata(record)['baselineDispositions']
                and record.get('natural',{}).get('agenda',{}).get('lastMove',{})):
            a['nextQuestion']=self.question(target['id'])
        if (a.get('nextQuestion') or {}).get('id')=='T06' and 'doctors' in (self.value(guide,'needs.priorities') or []):
            a['nextQuestion']=self.provider_detail_question()
        a['narrative']['natural'] = True
        return a

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

    def aggregate_still_pending(self, pending, update):
        return bool(pending and any(target['id'] == update['id']
                    and not self.matches_pending({'update':target}, update)
                    for target in [pending['update'], *pending.get('remaining', [])]))

    def resolve_pending(self, owner, update, guide, record):
        pending = self.pending_for(owner)
        if not pending:
            return
        remaining = [target for target in [pending['update'], *pending.get('remaining', [])]
                     if not self.matches_pending({'update':target}, update)]
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

    def apply(self, guide, record, update, source='user_choice'):
        # A stale aggregate is unavailable for guidance, but remains the complete
        # retained collection when applying a specifically addressed item edit.
        # The inherited report() intentionally hides stale facts, so expose this
        # collection only during its synchronous local mutation and restore its
        # hold afterward. Resolution of the exact pending target releases it.
        identifier = update['id'].split('.')[0]
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
        a = self.assess(g, r)
        pending = self.pending_for(owner)
        if pending and pending['revision'] != [g['stateVersion'], r['stateVersion']]:
            self.clear_pending(owner)
            pending = None
        answers=[]
        if facts:
            answers=[{'id':'answer','question':None,'kind':'answer','topic':FACT_TOPICS.get(facts[0]['id'],'learning'),
                'reason':'user_question','teaching_ids':[fact['id'] for fact in facts],
                'purpose':'Answer the person’s actual question from this reviewed evidence. Pause intake when the answer deserves its own turn; do not force another field.','priority':0}]
        if answer_only and answers:return answers
        if pending:
            update = pending['update']
            fields = [x for x in update.get('fields', {}) if x != 'choice']
            q = self.question(update['id'], fields or None, update.get('entity', 'profile'))
            return [*answers,{'id':'clarify', 'question':q,'kind':'clarify','topic':QUESTION_TOPICS.get(q['id'],''),
                'reason':'clarify_conflict','purpose':'Clarify the specific unresolved report; do not assert either candidate.', 'priority':1 if answers else 0}]
        q = a['nextQuestion']
        moves = list(answers)
        if priority_changed:
            topic=next(iter(self.value(g,'needs.priorities') or []),'other')
            moves.append({'id':'revise','question':None,'kind':'revise','topic':topic,'reason':'priority_change',
                'purpose':'Respond to the explicit priority change and its stated reason. Explain what it changes about the checks or tradeoffs still to investigate, without pretending a comparison ran. A follow-up field is optional.','priority':0})
        if (allow_orientation and not metadata(r).get('editing')
                and self.value(g, 'knowledge.general') is None
                and 'T02' not in metadata(r)['baselineDispositions']):
            return [*moves,{'id':'T02', 'question':self.question('T02'),'kind':'ask','topic':'learning','reason':'missing_dependency',
                     'purpose':'Use the approved familiarity question to understand how much explanation is useful. Familiarity does not establish enrollment, research completion, or a coverage decision.', 'priority':0}]
        if q:
            moves.append({'id':q['id'], 'question':q,'kind':'ask','topic':QUESTION_TOPICS.get(q['id'],''),
                'reason':'missing_dependency','purpose':q.get('why') or Q[q['id']]['requiredness'], 'priority':2 if moves else 0})
        agenda=r.get('natural',{}).get('agenda',{})
        concerns=[item for item in agenda.get('concerns',[]) if item['status']=='open']
        if not facts:
            unseen=[id for id in self.teaching_candidates(g,r,q) if id not in metadata(r)['journey']['learningSeen']]
            novice=self.value(g,'knowledge.general')=='new'
            if unseen and (concerns or novice):
                id=unseen[0];topic=concerns[-1]['topic'] if concerns else QUESTION_TOPICS.get((q or {}).get('id'),'learning')
                moves.append({'id':'teach:'+id,'question':None if concerns else q,'kind':'teach','topic':topic,
                    'reason':'contextual_teaching','teaching_ids':[id],
                    'purpose':'Teach one concise reviewed concept that addresses the explicit concern or makes the current unfamiliar choice easier. Do not read back the profile or imply a preference was learned from teaching.','priority':0})
            for concern in [item for item in concerns if item['subject']=='beneficiary'][-1:]:
                target={'doctors':'T06','drugs':'T07','total_cost':'T09','bills':'T09'}.get(concern['topic'])
                if (target and self.value(g,'subject.role') and self.value(g,FIELD[target]) is None
                        and target not in metadata(r)['baselineDispositions'] and (not q or q['id']!=target)):
                    question=self.provider_detail_question() if target=='T06' and 'doctors' in (self.value(g,'needs.priorities') or []) else self.question(target)
                    purpose='Follow the explicit concern with this approved question only if it would help more than the queued dependency. Gathering this report does not release any policy or source gate.'
                    if target=='T06' and question['question'].startswith('Which '):
                        purpose+=' The person already wants to keep a doctor; ask which doctor or practice, rather than asking whether they want to keep one.'
                    moves.append({'id':'concern:'+target,'question':question,'kind':'ask','topic':concern['topic'],
                        'reason':'user_question','purpose':purpose,'priority':1})
        if not moves:
            purpose = ('Continue this open learning conversation. Answer an actual question only from reviewed evidence. '
                       'When no question or evidence was supplied, briefly invite the person to say what they want to understand; '
                       'do not invent a Medicare lesson or claim the journey is complete.'
                       if a['task']=='learn' else
                       'Answer the current question or invite the next concern; do not create another intake requirement.')
            moves.append({'id':'explain', 'question':None,'kind':'invite','topic':'learning' if a['task']=='learn' else '',
                'reason':'open_learning','purpose':purpose, 'priority':0})
        return moves

    def context(self, g, r, policy=None, current=None):
        task = metadata(r)['task']
        active = None if current and current['id'] not in Q else current
        context = build_context(g, r, task, active_question=active,
                                consent_version=LEGACY_CONTEXT_POLICY if policy == CONTEXT_POLICY else policy)
        identifier = (current or {}).get('id', '').split('.')[0]
        if (policy == CONTEXT_POLICY and task != 'timing'
                and (identifier in TIMING_CONTEXT_TARGETS or identifier == 'T02')):
            capability = build_context(g, r, 'timing', active_question=active,
                                       consent_version=LEGACY_CONTEXT_POLICY)
            extra = capability['reports']
            if identifier == 'T02':
                # A familiarity question can connect to the life circumstances
                # just reported; it does not need every prior enrollment date.
                extra = [item for item in extra if item['id'] in FAMILIARITY_CONTEXT_REFS]
            reports = {item['id']:item for item in context['reports']}
            reports.update({item['id']:item for item in extra})
            context['reports'] = list(reports.values())
            context['known'] = [item for item in context['known'] if item['id'] not in reports]
        if policy==CONTEXT_POLICY:
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
        return context

    def permitted_question(self, question, policy):
        if not question or policy in {CONTEXT_POLICY,LEGACY_CONTEXT_POLICY}:return copy.deepcopy(question)
        # Generated/derived question labels may echo an earlier private value.
        # Old consent covers only the public meaning, not that echoed value.
        return self.question(question['id'], [f['key'] for f in question.get('fields',[])] or None,
                             question.get('entity','profile'))

    def compose_response(self, owner, out, message, moves, policy, request_id, reservation, previous_dialogue=None,
                         submitted_answer=None):
        context_question=next((move['question'] for move in moves if move.get('question')),None)
        context = self.context(out['guide'], out['record'], policy, context_question)
        if policy==CONTEXT_POLICY and any(move.get('kind')=='revise' for move in moves):
            priority=self.context(out['guide'],out['record'],policy,self.question('T10'))
            reports={item['id']:item for item in context['reports']};reports.update({x['id']:x for x in priority['reports']})
            context['reports']=list(reports.values());context['known']=[x for x in context['known'] if x['id'] not in reports]
            context['agenda']=priority.get('agenda')
        # A pause/open learning conversation is a controller decision. It must
        # survive a failed composition, rather than looking like completion.
        out['assessment']['intakePaused'] = bool(not moves[0]['question'] and
            self.assess(out['guide'], out['record']).get('nextQuestion'))
        out['assessment']['conversationOpen'] = bool(not moves[0]['question'] and
            metadata(out['record'])['task']=='learn')
        if previous_dialogue is not None:context['dialogue']=copy.deepcopy(previous_dialogue)
        moves=[{**move,'question':self.permitted_question(move.get('question'),policy)} for move in moves]
        context['current_message'] = message  # This turn only; never saved in dialogue/journal.
        if policy == CONTEXT_POLICY:
            context['recent_exchanges'] = self.recent_exchanges(owner, metadata(out['record'])['task'], policy)
        evidence={fact['id']:fact for fact in out.get('facts', [])}
        for move in moves:
            for id in move.get('teaching_ids',[]):
                if id in self.facts:evidence[id]=self.facts[id]
        context['evidence'] = copy.deepcopy(list(evidence.values()))
        pending=self.pending_for(owner)
        context['uncertainties'] = [{'id':pending['update']['id'], 'status':'needs_clarification'}] if pending else []
        if pending:
            identifier = pending['update']['id']
            prefixes = ['guide.'+FIELD[identifier]] if identifier in FIELD else ['readiness.'+identifier+'.']
            if identifier=='T04':prefixes.append('guide.coverage.requestedStartMonth')
            if identifier in {'S_AGE65','S_RETIREMENT'}:prefixes=['guide.'+SITUATION_FIELDS['age65' if identifier=='S_AGE65' else 'retirement']]
            affected=[x for x in context['reports'] if any(x['id'].startswith(prefix) for prefix in prefixes)]
            context['reports']=[x for x in context['reports'] if x not in affected]
            context['known'] += [{'id':x['id'],'status':'conflicting'} for x in affected]
        if submitted_answer is not None and policy==CONTEXT_POLICY:
            identifier=submitted_answer['question_id']
            prefix='guide.'+FIELD[identifier] if identifier in FIELD else 'readiness.'+identifier+'.'
            refs=[item['id'] for item in context['reports']
                  if item['id']==prefix or item['id'].startswith(prefix if prefix.endswith('.') else prefix+'.')]
            context['submitted_answer']={**copy.deepcopy(submitted_answer),'report_refs':refs}
        try:
            composed = self.agent.compose(owner, context, moves, request_id, reservation)
            move = next((m for m in moves if m['id'] == composed['move_id']), None)
            if not move:
                raise ModelUnavailable('The next question could not be checked.')
            out['reply'] = composed['reply']
            if move['question']:
                q = copy.deepcopy(move['question'])
                q['question'] = composed['question']
                q['why'] = ''
                out['assessment']['nextQuestion'] = q
                out['assessment']['narrative']['opener'] = False
            else:
                out['assessment']['nextQuestion'] = None
                out['assessment']['narrative']['opener'] = False
            out['assessment']['intakePaused'] = bool(not move['question'] and
                self.assess(out['guide'], out['record']).get('nextQuestion'))
            out['generated'] = {'status':'complete', 'move':move['id']}
            kind=move.get('kind','ask' if move['question'] else 'answer')
            used=[id for id in composed['evidence_refs'] if id in evidence]
            sources=[]
            for id in used:
                fact=evidence[id]
                for source in ([{'url':fact['source'],'label':'Medicare.gov: '+fact['title']}] if fact.get('source') else fact.get('sources',[])):
                    if isinstance(source,dict) and source.get('url') and all(x['url']!=source['url'] for x in sources):
                        sources.append({'url':source['url'],'label':source.get('label') or source.get('title') or fact['title']})
            out['advisor']={'kind':kind,'topic':move.get('topic',''),'reason':move.get('reason','missing_dependency'),
                            'teachingFactIds':used,'sources':sources}
            record_advisor_move(out['record'],out['advisor'])
            if used:
                m=metadata(out['record'])
                m['lastFactIds']=used
                for id in used:
                    if id not in m['journey']['learningSeen']:m['journey']['learningSeen'].append(id)
                    if id not in out['record']['natural']['dialogue']['explainedTopics']:
                        out['record']['natural']['dialogue']['explainedTopics'].append(id)
                out['record']['stateVersion']+=1
                out['facts']=[]
            out['metrics']['llmCalls'] += 1
            out['metrics']['stageMs'] = copy.deepcopy(getattr(self.agent.local, 'stage_timings', {}))
            return out
        except (ModelUnavailable, ProfileError, ValueError) as error:
            # Resolution already succeeded. Return it, never replay extraction.
            # Invalid prose never replaces a valid next step or becomes a
            # repeated canned chat reply. Keep the post-capture approved target.
            out['reply'] = ''
            out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question'])
            out['notice'] = 'I couldn’t finish that reply. You can keep going.'
            diagnostic=getattr(self.agent.local,'provider_failure',None)
            if diagnostic and diagnostic.get('provider_code') in {'credit_balance_exhausted','insufficient_quota'}:
                out['notice']=provider_failure_message(diagnostic,accepted=True)
            code = getattr(self.agent.local,'last_composition_error',None) or ('provider_failure' if diagnostic else 'composition_unavailable')
            if code not in COMPOSITION_CODES:
                code = 'composition_unavailable'
            out['generated'] = {'status':'unavailable', 'retryable':False, 'reason':str(error)[:220], 'code':code}
            if getattr(self.agent.local,'provider_failure',None):out['generated']['providerFailure']=copy.deepcopy(self.agent.local.provider_failure)
            with self.lock:
                self.composition_diagnostics.append({'code':code,
                    'questionAvailable':bool(moves[0]['question']),
                    'intakePaused':out['assessment']['intakePaused']})
                self.composition_diagnostics = self.composition_diagnostics[-50:]
            LOGGER.warning('Daylight composition unavailable code=%s question_available=%s intake_paused=%s',
                           code, bool(moves[0]['question']), out['assessment']['intakePaused'])
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
                    context['recent_exchanges'] = recent
                extraction_guide, _ = legacy_projection(g, r)
                result = self.agent.extract(owner, message, extraction_guide, context, payload['requestId'], reservation)
            m = metadata(r)
            practical = result.get('practical_request', {}).get('task', '')
            selected = practical or explicit_task(message) or result.get('task', '')
            if selected and (not m['task'] or selected != 'learn' or re.search(r'(?i)instead|just learn|want to learn', message)):
                m['task'], m['preparing'] = selected, selected not in {'learn', 'browse'}
                r['stateVersion'] += 1
            m['checks'] = sorted(set(m['checks']) | {x['id'] for x in result.get('requests', []) if x['id']!='coverage_change' or re.search(r'(?i)\bjoin|drop|cancel|switch|replace',x['quote'])})
            updates = []
            for u in result.get('updates', []):
                u = copy.deepcopy(u)
                if isinstance(u['fields'], list):u['fields'] = {f['key']:f['value'] for f in u['fields']}
                if practical and u['id']=='T01' and u['fields'].get('choice')=='learn':
                    # Needing explanations does not change an explicit
                    # enrollment/comparison request into an education-only goal.
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
                resolves_pending = self.matches_pending(pending, update)
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
                    ambiguous.append(update)
                    continue
                try:
                    self.capture(g, r, update, resolve_aggregate=resolves_pending and not self.aggregate_still_pending(pending, update))
                    accepted_updates.append(update)
                    if resolves_pending:
                        self.resolve_pending(owner, update, g, r)
                        pending = self.pending_for(owner)
                except ProfileError:
                    ambiguous.append(update)
            proposed_situation = observations(message, self.value(g, 'subject.role'))
            support = message
            if current and current['id']=='S_AGE65':
                match=re.fullmatch(r'(?i)(January|February|March|April|May|June|July|August|September|October|November|December)(?:\s+((?:19|20)\d{2}))?[.!]?',message)
                if match:
                    names='january february march april may june july august september october november december'.split()
                    proposed_situation['age65']={'month':names.index(match[1].lower())+1,'year':int(match[2]) if match[2] else None}
                    support='I turn 65 in '+message
            elif current and current['id']=='S_RETIREMENT' and re.fullmatch(r'(?i)(?:retired|retiring|planning to retire|(?:still )?working)[.!]?',message):
                proposed_situation['retirement']={'status':'working' if 'working' in message.lower() else 'retiring' if 'retiring' in message.lower() or 'planning' in message.lower() else 'retired','when':''}
                support='I am '+message
            situation={}
            for kind, value in proposed_situation.items():
                situation_id='S_'+kind.upper()
                old=g['fields'].get(SITUATION_FIELDS[kind])
                resolution=classify_situation(support,kind,value,existing=old)
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
            if situation and not self.value(g, 'subject.role') and re.search(r"(?i)\bI(?:'|’| am| have| turn)", message) and not re.search(r'(?i)\bmy (?:mother|father|mom|dad|parent|spouse|wife|husband)\b', message):
                self.capture(g, r, {'id':'RC01', 'fields':{'choice':'self'}, 'entity':'profile'})
            m = metadata(r)
            if practical and m['task'] != practical:
                m['task'], m['preparing'] = practical, practical != 'browse'
                r['stateVersion'] += 1
            if not m['task'] and 'age65' in situation:
                m['task'], m['preparing'] = 'timing', True
                r['stateVersion'] += 1
            explicit_disposition=bool(re.search(r"(?i)\b(?:don['’]t know|do not know|not sure|unknown|check later|defer|skip (?:this|that))\b",message))
            if explicit_disposition and result.get('mode') in {'unknown','defer'} and current and current['id'] in Q and not updates:
                state = 'unknown' if result['mode'] == 'unknown' else 'deferred'
                fields = {f['key']:state for f in current['fields']} or {'choice':state}
                self.capture(g, r, {'id':current['id'], 'fields':fields, 'entity':current['entity']})
            facts = [self.facts[fid] for fid in result.get('fact_ids', []) if fid in self.facts]
            if facts:
                if not m['task']:m['task'] = 'learn'
                r['stateVersion'] += 1
            if ambiguous:
                for update in ambiguous:
                    identifier=update['id']
                    field=FIELD.get(identifier) or (SITUATION_FIELDS['age65' if identifier=='S_AGE65' else 'retirement'] if identifier.startswith('S_') else None)
                    if field in g['fields']:g['fields'][field]['status']='stale'
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
            orientation = bool('age65' in situation and ensure_state(r)['dialogue']['orientation'] == '')
            pause_intake=bool(facts and re.search(r'(?i)\bbefore\b|\bfirst\b|\bpause\b|\bhold off\b|\bnot ready\b',message))
            moves = self.eligible(owner, g, r, allow_orientation=orientation, answer_only=pause_intake,
                                  facts=facts,priority_changed=priority_changed)
            out = self.response(g, r, facts=facts, expectedStateVersion=before[0], expectedReadinessRevision=before[1],
                                metrics={'llmCalls':0 if self.fixture else 1, 'synthetic':self.fixture})
            # Commit the resolved receipt before composition, including the
            # generated-question-independent target and recoverable state.
            out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question'])
            out['assessment']['narrative']['opener'] = False
            out['reply'] = 'Your details are here. We can continue from this point.'
            set_target(out['record'], out['assessment'].get('nextQuestion'),
                       orientation='familiarity' if moves[0]['id']=='T02' else None)
            out['continuation'] = self.bind(owner, out['guide'], out['record'], self.current_chain[owner])
            with self.lock:
                key = (owner, payload['requestId'])
                self.turn_journal[key] = {'signature':hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
                                         'response':copy.deepcopy(out), 'expires':time.time()+3600, 'stage':'resolved'}
                self.state_heads[(owner,self.current_chain[owner])] = out['continuation']
            if self.fixture:
                out['reply'] = 'Synthetic conversation: the supplied reports are captured.'
                if moves[0]['question']:out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question'])
                out['assessment']['narrative']['opener'] = False
            else:
                out = self.compose_response(owner, out, message, moves, policy, payload['requestId'], reservation, previous_dialogue)
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
        out['assessment']['nextQuestion']=copy.deepcopy(moves[0]['question'])
        out['metrics']={'llmCalls':0,'synthetic':False}
        self.agent.local.stage_timings={}
        reservation=None
        try:
            reservation=self.agent.reserve_turn(stages=('compose',))
            submitted_answer={'question_id':identifier,'question':(question or {}).get('question',''),
                'kind':action['type'],'fields':copy.deepcopy(action.get('fields',{}))}
            out=self.compose_response(owner,out,message,moves,CONTEXT_POLICY,payload['requestId'],reservation,
                                      submitted_answer=submitted_answer)
        except (ModelUnavailable,ProfileError,ValueError) as error:
            out['reply']='';out['notice']=str(error)[:220]
            out['generated']={'status':'unavailable','retryable':False,'code':'composition_unavailable'}
            out['assessment']['intakePaused']=bool(not moves[0]['question'] and self.assess(out['guide'],out['record']).get('nextQuestion'))
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
            self.turn_journal = {k:v for k,v in self.turn_journal.items() if v['expires'] > time.time()}
            if key in self.turn_journal:
                entry = self.turn_journal[key]
                if entry['signature'] != signature:raise ProfileError('This request key belongs to another turn.', 409)
                return copy.deepcopy(entry['response'])
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
            if action.get('type') == 'start':
                self.visit_memory.pop((owner,chain), None)
            if action.get('type') in {'run_preparation','accept_review','discard_review'} and self.action_chains.get(action.get('token')) != (owner,chain):
                raise ProfileError('This authorization belongs to an earlier conversation. Review the current action again.',409)
            if action.get('type') == 'message':
                out = self.direct_disposition(owner,payload,g,r) or self.message(owner, payload, g, r)
            else:
                legacy = {k:v for k,v in payload.items() if k not in {'contextPolicy','continuation'}}
                legacy['guide'], legacy['record'] = g, r
                if action.get('type') == 'stage':
                    current = self.assess(g, r)['nextQuestion']
                    if not current or current['id'] != action.get('id') or current['entity'] != action.get('entity', 'profile'):
                        raise ProfileError('This form changed. Your entries are preserved.', 409)
                    legacy['action'] = {**action, 'type':'choice'}
                out = super().turn(owner, legacy)
                if out.get('review'):
                    self.action_chains[out['review']['token']] = (owner,chain)
                if action.get('type') in {'choice','stage'}:
                    pending = self.pending_for(owner)
                    if self.matches_pending(pending, legacy['action']):
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
            out['continuation'] = self.bind(owner, out['guide'], out['record'], chain)
            with self.lock:
                if len(self.state_heads)>1024:self.state_heads.pop(next(iter(self.state_heads)))
                self.state_heads[(owner,chain)] = out['continuation']
                if len(self.turn_journal) >= 128:self.turn_journal.pop(next(iter(self.turn_journal)))
                self.turn_journal[key] = {'signature':signature, 'response':copy.deepcopy(out), 'expires':time.time()+3600}
            return out
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
