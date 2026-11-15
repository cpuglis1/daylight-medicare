"""D166: discussion-led planning for the unified demo only.

The interpreter proposes meaning and the composer selects a useful supported
question; this module validates their contracts. It neither ranks plans nor admits evidence.
Planning memory is bounded, visit-only and never part of a saved profile.
"""
from collections import OrderedDict
import copy
import hashlib
import json
import re
import threading
import time

from adaptive_flow import AdaptiveConversation, metadata
from advisor_memory import HISTORY_TTL, VISIT_LIMIT
import enrollment_flow
import medigap_profile
import part_d_profile
import journey_completion
import conversation_tasks

VERSION = 'discussion-planner-v1'
DECISION_VERSION = 'intent.decisionVersion'
COMPONENT_VERSION = 'intent.componentDecisionVersion'
PURPOSES = ('none', 'understand', 'review', 'problem', 'compare', 'investigate')
FOCI = ('', 'coverage_paths', 'original', 'medigap', 'advantage', 'part_d', 'enrollment',
        'doctors', 'medicines', 'costs', 'flexibility')
INVESTIGATIONS = ('medigap', 'advantage', 'part_d', 'doctors', 'medicines')
PATHS = ('', 'original', 'original_medigap', 'medicare_advantage', 'original_only', 'keep_current', 'wait')
DISCUSSION_QUESTIONS = {
    'CP_PURPOSE': ('What would you like help working through today?', ''),
    'CP_REASON': ('What prompted you to look at your coverage now?',
                  'That helps connect the options to what you want to change or understand.'),
    'CP_REACTION': ('What feels most important or still unclear as you weigh those options?', ''),
    'CP_UNDERSTANDING': ('Which part would help to make clearer?', ''),
    'CP_INVESTIGATE': ('Which would you like to investigate: Original Medicare options, Medicare Advantage, or both?', ''),
    'CP_NEXT': ('What would help you make your next decision?', ''),
    'CP_RETRY': ('Would you like to rephrase that question or leave it open for now?', ''),
    'CP_PARTS': ('Your reports about Parts A and B conflict. Which parts are in effect now?', ''),
    'CP_COVERAGE': ('You reported an Advantage or Medigap policy and a Medicare part that is not in effect. Which coverage is current?', ''),
}
INTERPRETATION = """
Priorities: (1) natural conversation flow, (2) collect consequential required
information using the existing profile, (3) educate in context. Interpret the
whole message and recent conversation, including indirect references, answers,
corrections and changes of mind. Extract EVERY relevant report independently of
the current question or task. A conversational detour must not discard reports.

Keep purpose, focus, facts, understanding, preferences and decisions distinct.
Purpose describes the help sought; focus is a topic, never a coverage choice.
Quote the person's actual words supporting each interpretation. question_quote
is the concern to answer first, including requests without a question mark.
reason_quote captures why they came; do not ask again when already supplied.

Use guidance to propose the next conversational stance from context:
- discuss: answer/explain/explore, with no personal intake this turn;
- suggest: propose one useful supported task and explain its value, without
  assuming the person agreed to it;
- work: advance a task they requested, accepted or are already answering;
- detour: answer a side question while retaining the active task;
- pause: respect their wish to stop questions or personal intake;
- finish: produce a requested summary using recorded work and remaining limits.
Task identifiers and conditional check meanings come from discussion_capabilities.
They describe capabilities, not required words or a script. Interpret acceptance,
refusal and continuation from the conversation. A blank task on work resumes the
active task; accepting an offered task uses that task. A task change must be
supported by the message. Select only relevant checks; do not request all fields.
Guidance.quote grounds the stance in this message; uncertain intent stays discuss.
A suggestion can arise from their stated goal and circumstances; do not claim it
is a request. Finish is a conversational outcome, never a policy choice.

investigate identifies the plan/price/doctor/drug work actually requested, not
products mentioned while learning. request_quote supports it in context. Product
research can cover both paths without a preference. Decisions have stance and
path; only explicit current beneficiary/helper intentions support a choice.
Curiosity, hypothetical choices, current coverage, a priority or a viewed path
cannot establish one. A path choice does not choose every component or say an
application was submitted. Leave uncertain decisions unset. Keep familiarity in
learner_observations, reports in updates, and CP_ identifiers out of updates.
"""
COMPOSITION = """
Priorities, in order: natural conversation flow; obtaining consequential required
information; contextual education. Respond to what the person just said and lead
toward their goal. Answering, explaining and asking can coexist in one turn.
Do not force an intake sequence or repeat generic reflection prompts.

Use discussion_plan, the profile's known/unknown/deferred reports, the existing
education/learner records and actual capability states together. The AI chooses
which supplied question is most useful now; their order is not a curriculum.
When asking a personal detail, select its approved question_target so the existing
controls are shown. Explain why it matters and help with unfamiliar terms. Reuse
all known reports, including facts supplied while answering a different question.
Never call a recorded fact missing or infer an unknown value.

For suggest, write a natural, specific offer of useful supported work connected
to the person's goal. Do not begin its intake until accepted or requested. For
work, use a consequential question from the supplied candidates, or explain the
available result/hold when no useful input remains. A direct request does not
need permission again. For discuss/detour, answer first and keep the practical
return point available; do not force a questionnaire into the explanation.
For pause/finish, do not append another intake or reflection question.

Teach only what helps this exchange or decision. The education ledger records
what was already explained: do not repeat introductions as a checklist. Revisit
when requested or clarification is needed; delivery never proves understanding.
General education needs no pricing inputs. Process suggestions are permitted;
insurance recommendations and personal findings require authorized evidence.

Cards are only those in software_cards. Use the relevant ready results without
inventing prices, identities, calculations, checks or fulfillment. Missing and
held evidence stays explicit. Neither browsing, explanation nor investigation
chooses a path. Finish summaries distinguish work performed, actual decisions,
open checks and next actions. No unsupported completion or personal fit claim.
"""


def enabled(flow):
    return bool(getattr(flow, 'd166', False))


def enable(flow):
    node = next(node for node in flow.contract['nodes'] if node['id'] == 'R00')
    for field in (DECISION_VERSION, COMPONENT_VERSION):
        if field not in node['writes']:
            node['writes'].append(field)
    flow.d166 = True


def schema(make):
    return make({
        'purpose': {'type': 'string', 'enum': list(PURPOSES)},
        'focus': {'type': 'string', 'enum': list(FOCI)},
        'quote': {'type': 'string', 'maxLength': 600},
        'reason_quote': {'type': 'string', 'maxLength': 600},
        'question_quote': {'type': 'string', 'maxLength': 600},
        'investigate': {'type': 'array', 'maxItems': 5, 'items': {'type': 'string', 'enum': list(INVESTIGATIONS)}},
        'request_quote': {'type': 'string', 'maxLength': 600},
        'uncertain': {'type': 'boolean'},
        'guidance': conversation_tasks.schema(make),
        'decision': make({'stance': {'type': 'string', 'enum': ['none', 'leaning', 'chosen', 'undecided']},
                          'path': {'type': 'string', 'enum': list(PATHS)},
                          'quote': {'type': 'string', 'maxLength': 600}}),
    })


def empty_proposal():
    return dict(purpose='none', focus='', quote='', reason_quote='', question_quote='', investigate=[],
                request_quote='', uncertain=False, guidance=conversation_tasks.empty(), decision=dict(stance='none', path='', quote=''))


def supported(quote, message):
    return isinstance(quote, str) and 0 < len(quote.strip()) <= 600 and quote.casefold() in message.casefold()


# These are conservative action guards, not the semantic planner. An unfamiliar
# decision expression remains a discussion, rather than an unreviewed write.
UNREAL = re.compile(r"\b(?:if|suppose|hypothetically|for example|used to|might|maybe|wonder|considering)\b", re.I)
NEGATED = re.compile(r"\b(?:not|never|don['’]?t|do not|haven['’]?t|haven't|won['’]?t|without)\b", re.I)
LEARNING = re.compile(r'\b(?:understand|explain\w*|learn|mean|works?|difference|curious|explor\w*|tell me about)\b', re.I)
DECIDING = re.compile(r"\b(?:I(?:['’]m| am) (?:choosing|going with|keeping|waiting)|I (?:choose|pick|prefer|want|have decided)|"
                      r"I['’]ll (?:keep|wait|go with)|let['’]s (?:go with|choose)|we (?:choose|want))\b", re.I)


def explicit_components(message):
    """Validate component intentions separately from coverage ownership.

    Reuse the component vocabulary, but never its legacy have=keep shortcut.
    Questions, hypothetical decisions and attributed speech cannot write state.
    """
    found = {}
    for clause in re.split(r'(?<=[.!?])\s+|;', message.replace('’', "'")):
        if re.match(r'^\s*(?:please )?keep (?:my (?:current )?)?(?:plan [a-dfgk-n]|medigap|supplement)\b', clause, re.I):
            clause = 'I will ' + re.sub(r'^\s*please ', '', clause, flags=re.I).lstrip()
        if ('?' in clause or UNREAL.search(clause) or LEARNING.search(clause) or INVESTIGATING.search(clause)
                or re.search(r'\b(?:says?|said|should|could|would|whether)\b', clause, re.I)):
            continue
        if not re.search(r"\b(?:I|we)(?:'m|'re|'ll| am| are| will)?\s+(?:keep\w*|stay\w*|stick\w*|choose|chose|pick|picked|want|add|take|get|buy|decide|skip\w*|don'?t want|do not want|won'?t get)\b", clause, re.I):
            continue
        changes = enrollment_flow.choices_from_text(clause)['components']
        if re.search(r'\b(?:keep\w*|stay\w* with|stick\w* with)\b.{0,30}\bplan [a-dfgk-n]\b', clause, re.I):
            changes['medigap'] = 'keep_existing'
        # Choosing the Medigap category is not choosing an individual policy.
        if changes.get('medigap') == 'chosen' and not re.search(r'\bplan [a-dfgk-n]\b', clause, re.I):
            changes.pop('medigap')
        found.update(changes)
    return found
INVESTIGATING = re.compile(r'\b(?:prices?|pricing|premiums?|quotes?|how much|costs?|show|find|look at|see|compare|review|check|investigate)\b', re.I)
PRODUCTS = {
    'medigap': re.compile(r'\b(?:medigap|supplement|plan [a-n])\b', re.I),
    'advantage': re.compile(r'\b(?:advantage|part c|hmo|ppo)\b', re.I),
    'part_d': re.compile(r'\b(?:part d|drug plans?|prescription plans?)\b', re.I),
    'doctors': re.compile(r'\b(?:doctor|provider|hospital|specialist|network)\w*\b', re.I),
    'medicines': re.compile(r'\b(?:medicine|medication|prescription|drug|pharmacy)\w*\b', re.I),
}


def validate_proposal(value, message, focus=''):
    """Bound and ground hints; reject unsafe action/decision interpretations.

Quote matching proves provenance, not universal semantic entailment. The extra
action guards fail closed; a rejected hint never rejects independent reports.
"""
    out = empty_proposal()
    if not isinstance(value, dict) or set(value) != set(out):
        return out
    if value['purpose'] not in PURPOSES or value['focus'] not in FOCI or type(value['uncertain']) is not bool:
        return out
    if supported(value['quote'], message):
        out.update(purpose=value['purpose'], focus=value['focus'], quote=value['quote'], uncertain=value['uncertain'])
    if supported(value['question_quote'], message):
        out['question_quote'] = value['question_quote']
    if supported(value['reason_quote'], message):
        out['reason_quote'] = value['reason_quote']
    out['guidance'] = conversation_tasks.validate(value['guidance'], message)
    if value['uncertain']:
        out['guidance'] = conversation_tasks.empty()
    request, inv = value['request_quote'], value['investigate']
    if (isinstance(inv, list) and len(inv) <= 5
            and all(isinstance(k, str) and k in INVESTIGATIONS for k in inv)
            and supported(request, message) and not value['uncertain']):
        out.update(investigate=list(dict.fromkeys(inv)), request_quote=request)
    decision = value['decision']
    if (isinstance(decision, dict) and set(decision) == {'stance', 'path', 'quote'}
            and decision['stance'] in ('none', 'leaning', 'chosen', 'undecided') and decision['path'] in PATHS
            and supported(decision['quote'], message) and not value['uncertain']):
        text = decision['quote']
        if decision['stance'] == 'undecided' and re.search(r"not (?:sure|decided)|undecided|haven.t (?:chosen|decided)", text, re.I):
            out['decision'] = dict(stance='undecided', path='', quote=text)
        elif (decision['stance'] == 'chosen' and decision['path'] in ('keep_current', 'wait')
              and journey_completion.request(text) == decision['path']):
            # This validates a decision; it never routes conversational work.
            out['decision'] = copy.deepcopy(decision)
        elif (decision['path'] and '?' not in message and not UNREAL.search(message) and not NEGATED.search(message)
              and not LEARNING.search(message) and not re.search(r'\b(?:prices?|quotes?|pricing|premiums?|says?|said)\b', message, re.I)
              and (DECIDING.search(text) or decision['stance'] == 'leaning' and re.search(r"\bI(?:['’]m| am) leaning\b", text, re.I))):
            expected = {'original': r'\boriginal medicare\b', 'original_medigap': r'\bmedigap\b|\bsupplement\b',
                        'medicare_advantage': r'\badvantage\b', 'original_only': r'\b(?:parts? a and b|original medicare) only\b',
                        'keep_current': r'\bkeep(?:ing)?\b', 'wait': r'\bwait(?:ing)?\b'}[decision['path']]
            if re.search(expected, text, re.I):
                out['decision'] = copy.deepcopy(decision)
                if re.search(r'\b(?:prefer|leaning)\b', text, re.I):
                    out['decision']['stance'] = 'leaning'
    return out




class VisitPlans:
    """Same bounded visit boundary as conversation memory; no disk writes."""
    def __init__(self):
        self.visits = OrderedDict()
        self.lock = threading.RLock()

    def get(self, owner, chain):
        with self.lock:
            now = time.monotonic()
            for key in [k for k, v in self.visits.items() if v['expires'] <= now]:
                del self.visits[key]
            key = (owner, chain)
            if key not in self.visits:
                self.visits[key] = {'purpose': 'none', 'focus': '', 'investigate': [], 'exploring': [],
                    'decision': {'stance': 'undecided', 'path': ''}, 'latest': empty_proposal(),
                    'guidance': conversation_tasks.empty(), 'active_task': '', 'suggested_task': '', 'task_checks': [],
                    'asked': {}, 'deferred': [], 'reason_known': False, 'cards': {}, 'plan': {}, 'expires': now + HISTORY_TTL}
            self.visits.move_to_end(key)
            while len(self.visits) > VISIT_LIMIT:
                self.visits.popitem(last=False)
            self.visits[key]['expires'] = now + HISTORY_TTL
            return self.visits[key]

    def clear(self, owner, chain=None):
        with self.lock:
            for key in [k for k in self.visits if k[0] == owner and (chain is None or k[1] == chain)]:
                del self.visits[key]


def state(flow, owner):
    if not hasattr(flow, 'discussion_visits'):
        flow.discussion_visits = VisitPlans()
    return flow.discussion_visits.get(owner, flow.current_chain.get(owner))


def question(identifier):
    if identifier not in DISCUSSION_QUESTIONS:
        return None
    words, why = DISCUSSION_QUESTIONS[identifier]
    q = dict(id=identifier, entity='profile', question=words, why=why, fields=[], choices=[],
             multi=False, signature=VERSION + ':' + identifier, conversational=True)
    return q


def observe(flow, owner, g, r, message, result, current=None):
    s = state(flow, owner)
    s.pop('outcome', None)
    p = validate_proposal(result.get('discussion'), message, s['focus'])
    s['latest'] = p
    guide = p['guidance']
    # Invalid/missing interpretation cannot start a task or invent a response
    # meaning. Accepted reports still survive and the existing task is retained.
    if guide['quote']:
        s['guidance'] = copy.deepcopy(guide)
        mode = guide['mode']
        if mode == 'work':
            task = guide['task'] or s['active_task'] or s['suggested_task']
            if task:
                if task != s['active_task']:
                    s['task_checks'] = []
                    s['task_investigate'] = []
                    s['plans_products'] = []
                    s['focus'] = p['focus'] or conversation_tasks.FOCI[task]
                s['active_task'] = task
                s['task_checks'] = list(dict.fromkeys(s['task_checks'] + guide['checks']))
                s['suggested_task'] = ''
        elif mode == 'suggest':
            s['suggested_task'] = guide['task']
        s['education_only'] = mode in ('discuss', 'suggest', 'detour', 'pause')
    else:
        s['guidance'] = conversation_tasks.empty()
    s['finish_requested'] = (guide['finish'] or 'summary') if guide['mode'] == 'finish' else None
    # Finishing does not authorize a coverage decision.
    if s['finish_requested'] in ('keep_current', 'wait') and p['decision'].get('path') != s['finish_requested']:
        s['finish_requested'] = 'summary'
    if p['purpose'] != 'none': s['purpose'] = p['purpose']
    if p['focus']: s['focus'] = p['focus']
    if p['reason_quote']: s['reason_known'] = True
    if guide['mode'] == 'work' and s['active_task']:
        # The semantic task is separate from the conversational topic.
        allowed = conversation_tasks.INVESTIGATIONS[s['active_task']]
        s['investigate'] = [v for v in p['investigate'] if v in allowed]
        if not s['investigate']:
            s['investigate'] = [v for v in s.get('task_investigate', []) if v in allowed]
        if not s['investigate']:
            s['investigate'] = list(conversation_tasks.DEFAULT_INVESTIGATIONS.get(s['active_task'], []))
        s['task_investigate'] = list(s['investigate'])
        products = [v for v in s['investigate'] if v in ('medigap','advantage','part_d')]
        if products: s['plans_products'] = products
        s['exploring'] = list(dict.fromkeys(s['exploring'] + s['investigate']))[-5:]
        match = re.search(r'\b(?:standard )?plan ([a-dfgk-n])\b', p['request_quote'], re.I)
        if match and 'medigap' in s['investigate']:
            s['medigap_variant'] = ('HD' if re.search(r'high[ -]deductible', p['request_quote'], re.I) else '') + match.group(1).upper()
    else:
        s['investigate'] = []
    d = p['decision']
    if d['stance'] != 'none':
        s['decision'] = {k: d[k] for k in ('stance', 'path')}
        if d['stance'] in ('chosen', 'undecided') or d['stance'] == 'leaning' and flow.value(g, enrollment_flow.PATH_FIELD):
            enable(flow)
            flow.put(g, enrollment_flow.PATH_FIELD, d['path'] if d['stance'] == 'chosen' else 'undecided', 'user_text')
            flow.put(g, DECISION_VERSION, VERSION, 'user_text')
            if d['stance'] == 'chosen' and d['path'] == 'original_only':
                enrollment_flow._put_components(flow, g, {'medigap': 'not_needed', 'part_d': 'not_needed'}, 'user_text')
                flow.put(g, COMPONENT_VERSION, VERSION, 'user_text')
    components = explicit_components(message)
    if components:
        enrollment_flow._put_components(flow, g, components, 'user_text')
        flow.put(g, COMPONENT_VERSION, VERSION, 'user_text')
        # Adding Part D does not also buy Medigap; keeping a supplement does
        # not settle the drug-plan review or imply keeping all coverage.
        if flow.value(g, enrollment_flow.PATH_FIELD) == 'original_only' and any(
                value in ('chosen', 'keep_existing') for value in components.values()):
            flow.put(g, enrollment_flow.PATH_FIELD, 'original', 'user_text')
            flow.put(g, DECISION_VERSION, VERSION, 'user_text')
            s['decision'] = {'stance': 'chosen', 'path': 'original'}
    task = s['active_task'] if guide['mode'] == 'work' else ''
    report_task = 'compare' if task == 'advantage' else task
    if report_task in ('compare', 'review') and flow.value(g, 'intent.goal') != report_task:
        # This is a requested work goal, never an insurance choice. Use the
        # existing profile capture so review readiness and provenance agree.
        flow.capture(g, r, dict(id='T01', entity='profile', fields={'choice':report_task},
            quote=guide['quote'], scope='current', subject='learner'))
    metadata(r).update(task=report_task or 'learn', preparing=bool(task))


def path(flow, owner, g, r):
    s = state(flow, owner)
    d = s['decision']
    recorded = flow.value(g, enrollment_flow.PATH_FIELD)
    if (flow.value(g, DECISION_VERSION) == VERSION
            or g.get('fields', {}).get(enrollment_flow.PATH_FIELD, {}).get('source') == 'user_choice') and recorded in PATHS:
        d = {'stance': 'chosen', 'path': recorded}
    if d['stance'] in ('chosen', 'leaning') and d['path']:
        return {'state': d['stance'], 'path': d['path'], 'because': ['You chose this path.'] if d['stance'] == 'chosen' else ['You said you are leaning this way.']}
    return {'state': 'undecided', 'path': None, 'because': []}


def decision_guide(flow, g):
    """Old text heuristics have no decision authority. Keep original reports
    intact; project unconfirmed legacy choices out of enrollment guidance."""
    if not enabled(flow):
        return g
    fields = g.get('fields', {})
    unconfirmed = [key for key in (enrollment_flow.PATH_FIELD, enrollment_flow.COMPONENT_FIELD)
                   if key in fields and fields[key].get('source') != 'user_choice'
                   and flow.value(g, COMPONENT_VERSION if key == enrollment_flow.COMPONENT_FIELD else DECISION_VERSION) != VERSION]
    return {**g, 'fields': {key: value for key, value in fields.items() if key not in unconfirmed}} if unconfirmed else g


def candidate(flow, g, r, identifier, purpose='', priority=1):
    q = question(identifier) or flow.contextual_question(g, r, flow.question(identifier))
    return dict(id=identifier, question=copy.deepcopy(q), topic='', priority=priority, required=False,
                purpose=purpose or q.get('why') or 'Continue this discussion.') if q else None


def refine(flow, owner, g, r, candidates):
    s = state(flow, owner)
    if s.get('finish_requested') or s['guidance']['mode'] == 'pause': return []
    if metadata(r).get('editing'): return candidates
    reports = [flow.value(g, field) or {} for field in enrollment_flow.PART_FIELDS.values()]
    if any(report.get('status') == 'conflicting' for report in reports):
        return [{**candidate(flow, g, r, 'CP_PARTS'), 'required':True}]
    if (set(flow.value(g, 'coverage.current') or []) & {'advantage','medigap'}
            and any(report.get('status') == 'not_enrolled' for report in reports)):
        return [{**candidate(flow, g, r, 'CP_COVERAGE'), 'required':True}]
    if s['guidance']['mode'] != 'work' or not s['active_task']:
        return []
    required = [c for c in candidates if c.get('required')]
    if required: return required
    selected = conversation_tasks.candidates(flow, g, r, s['active_task'], s['task_checks'])
    # Existing product profiles own their required inputs and supported scope.
    for product in s['investigate']:
        if product not in ('medigap','part_d','advantage'): continue
        view = medigap_profile.profile(g) if product == 'medigap' else part_d_profile.profile(g, r)
        if view['status'] == 'unsupported':
            selected = []
            continue
        for identifier in view['missing']:
            if identifier not in view['held'] and not any(c['id'] == identifier for c in selected):
                c = candidate(flow, g, r, identifier)
                if c: selected.append(c)
    dispositions = {**metadata(r).get('baselineDispositions', {}), **r.get('dispositions', {})}
    return [c for c in selected if c['id'] not in dispositions and c['id'] not in s['deferred']][:24]


def target(flow, owner, g, r, moves, required_id, required_reason):
    # Mandatory ambiguity is code-owned; otherwise the model selects a useful
    # approved meaning, not the first item in a fixed topic branch.
    required = next((m for m in moves if m.get('required')), None)
    return (required['id'], 'clarification') if required else (None, None)


def checks_relevant(flow, owner, g=None):
    s = state(flow, owner)
    return (not s.get('finish_requested') and not s.get('outcome')
        and s['guidance']['mode'] == 'work'
        and (bool(set(s['investigate']) & {'doctors','medicines','part_d','advantage'})
             or s['active_task'] in ('compare','review') and bool(g and any(
                 flow.value(g, field) for field in ('needs.providers','needs.medications')))))


def note_message(flow, owner, g, message, submitted_answer=None, r=None):
    if r is not None:
        # Keep actual application/coverage capture, excluding legacy inferred
        # decisions. Current coverage remains separate from keeping it.
        enrollment_flow.capture(flow, g, r, message)
        # A changed report withdraws summary evidence too. The research
        # controller will supply fresh results through its ordinary checks.
        s = state(flow, owner)
        if s.get('last_check_signature') != report_signature(g, r):
            s.pop('last_check_results', None)
    if submitted_answer:
        s = state(flow, owner)
        s['latest'] = empty_proposal()
        s['asked'].pop(submitted_answer.get('question_id'), None)


def action_done(flow, owner, out, action):
    """Free controls convey only what their labels actually authorize."""
    s = state(flow, owner)
    kind = action.get('type')
    if kind in ('choice', 'stage', 'unknown', 'defer') and s['active_task']:
        s['guidance'] = {**s['guidance'], 'mode':'work', 'task':s['active_task']}
        s['education_only'] = False
        s['investigate'] = list(s.get('task_investigate') or
                               conversation_tasks.DEFAULT_INVESTIGATIONS.get(s['active_task'], []))
    if kind == 'enrollment_decision':
        if 'start_with' in action:
            focus = {'original_medigap': 'original', 'medicare_advantage': 'advantage', 'both': 'coverage_paths'}[action['start_with']]
            s.update(purpose='understand', focus=focus, investigate=[], latest=empty_proposal())
            s['guidance'] = conversation_tasks.empty()
            s['exploring'] = list(dict.fromkeys(s['exploring'] + [focus]))[-5:]
        elif 'path' in action:
            s['decision'] = {'stance': 'undecided' if action['path'] == 'undecided' else 'chosen',
                             'path': '' if action['path'] == 'undecided' else action['path']}
    elif kind == 'task' or kind in ('choice', 'stage') and action.get('id') == 'T01':
        task = action.get('task') or action.get('fields', {}).get('choice')
        s['latest'] = empty_proposal()
        if task in ('medigap', 'drug_pricing'):
            product = 'medigap' if task == 'medigap' else 'part_d'
            s.update(purpose='investigate', focus=product, investigate=[product])
        else:
            s.update(purpose={'learn': 'understand', 'review': 'review', 'compare': 'compare'}.get(task, 'problem'),
                     focus={'timing': 'enrollment', 'providers': 'doctors', 'drug_coverage': 'medicines'}.get(task, 'coverage_paths'),
                     investigate=[])
        if task in conversation_tasks.TASKS:
            s.update(active_task=task, guidance={**conversation_tasks.empty(), 'mode':'work','task':task}, education_only=False)
            s['investigate'] = list(conversation_tasks.DEFAULT_INVESTIGATIONS.get(task, []))
            s['task_investigate'] = list(s['investigate'])
        else:
            s['guidance'] = conversation_tasks.empty()
    elif kind in ('unknown', 'defer'):
        identifier = action.get('id')
        if identifier and identifier not in s['deferred']: s['deferred'].append(identifier)
    if kind in ('choice', 'stage', 'unknown', 'defer', 'task', 'enrollment_decision') and not out.get('generated'):
        moves = flow.eligible(owner, out['guide'], out['record'])
        if not metadata(out['record']).get('editing') and action.get('source') != 'plans_filter':
            out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question']) if moves else None
            from natural_state import set_target
            set_target(out['record'], out['assessment']['nextQuestion'])


def educational_card(flow, s):
    if s['focus'] not in ('coverage_paths', 'costs', 'flexibility'):
        return None
    # Reuse the accepted statements without the old inferred lean, price
    # placeholders, completion counters or premature decision controls.
    return {'kind': 'discussion_paths', 'title': 'Two ways to get Medicare coverage',
        'columns': [
            {'title': 'Original Medicare', 'lines': [enrollment_flow.statement('original_what'),
                enrollment_flow.statement('trade_original_access'), enrollment_flow.statement('trade_medigap_helps')]},
            {'title': 'Medicare Advantage', 'lines': [enrollment_flow.statement('trade_ma_limit'),
                enrollment_flow.statement('trade_ma_network'), enrollment_flow.statement('trade_ma_drugs')]},
        ], 'sources': enrollment_flow._statement_sources('original_what', 'trade_original_access',
                    'trade_medigap_helps', 'trade_ma_limit', 'trade_ma_network', 'trade_ma_drugs'),
        'actions': [{'label': 'Explore Original Medicare', 'say': 'Help me understand Original Medicare and its options.'},
                    {'label': 'Explore Medicare Advantage', 'say': 'Help me understand Medicare Advantage.'}]}


def prepare(flow, owner, g, r, moves, context):
    s = state(flow, owner)
    cards = []
    card = educational_card(flow, s)
    if card and (s['latest']['question_quote'] or s['purpose'] == 'compare'):
        fingerprint = hashlib.sha256(repr(card).encode()).hexdigest()
        if s['cards'].get(card['kind']) != fingerprint or context.get('education_context', {}).get('requested_revisit'):
            cards.append(card)
    if s['focus'] == 'enrollment':
        import ux_flow
        timing = ux_flow._timing_card(flow, owner, g, r, s['latest']['question_quote'])
        if timing: cards.append(timing)
        cards.extend(enrollment_flow.cards(flow, owner, flow.current_chain.get(owner), g, r,
                                           s['latest']['question_quote'], cards))
        if s['guidance']['mode'] == 'work' and moves:
            # Do not put fulfillment ahead of the pending information request.
            cards = [c for c in cards if c['kind'] != 'signup_route']
    elif 'advantage' in (flow.value(g, 'coverage.current') or []) and (
            re.search(r'\btrial right\b', s['latest']['question_quote'], re.I)):
        trial = enrollment_flow.trial_right(flow, g, r, enrollment_flow._today())
        if trial:
            cards.append(trial)
    pages = flow.plans_pages(g, r)
    if s['guidance']['mode'] == 'work':
        names = {'medigap': ('See Medigap prices', 'supplement'), 'advantage': ('See Medicare Advantage plans', 'advantage'),
                 'part_d': ('See Part D plans', 'part-d')}
        for name in s['investigate']:
            if name not in names: continue
            ready = part_d_profile.profile(g, r)['status'] == 'ready' if name == 'advantage' else pages[name]['status'] == 'ready'
            if ready:
                label, view = names[name]
                cards.append({'kind': 'plans_ready', 'title': label, 'tab': name, 'button': {'label': label, 'view': view}})
    record = enrollment_flow.journey(flow, g, r, enrollment_flow._today())
    if record.get('finish'):
        line = enrollment_flow.status_line(record, {part: flow.value(g, field) for part, field in enrollment_flow.PART_FIELDS.items()},
            flow.value(g, enrollment_flow.PATH_FIELD), flow.value(g, 'coverage.socialBenefits') == 'yes', flow.value(g, 'coverage.current') or [])
        summary = enrollment_flow.finish_card(record, line) if line else None
        if summary: cards = [summary]
    # One conceptual card per turn; multiple requested result links share a row
    # in the frontend. Never stack an unrelated route or coverage card.
    cards = [c for c in cards if s['cards'].get(c['kind']) != hashlib.sha256(repr(c).encode()).hexdigest()
             or context.get('education_context', {}).get('requested_revisit')]
    s['turn_cards'] = cards[:3] if all(c['kind'] == 'plans_ready' for c in cards) else cards[:1]
    plan = {'version': VERSION, 'purpose': s['purpose'], 'focus': s['focus'],
        'direction_version': 'semantic-guidance-v2',
        'guidance': {k:copy.deepcopy(v) for k,v in s['guidance'].items() if k != 'quote'},
        'active_task': s['active_task'], 'suggested_task': s['suggested_task'],
        'require_structured': s['guidance']['mode'] == 'work' and bool(moves),
        'finish_requested': s.get('finish_requested'),
        'answer_first': bool(s['latest']['question_quote']), 'question_to_answer': s['latest']['question_quote'],
        'investigations': list(s['investigate']), 'exploring': list(s['exploring']),
        'decision': path(flow, owner, g, r), 'next_question': None, 'available_questions': [m['id'] for m in moves],
        'deferred_questions': list(s['deferred']), 'software_cards': [c['kind'] for c in s['turn_cards']],
        'understanding_is_not_delivery': True}
    s['plan'] = plan
    context['discussion_plan'] = copy.deepcopy(plan)
    context['discussion_capabilities'] = conversation_tasks.context(flow, g, r)
    context['plans_pages']['purpose'] = (
        'Availability evidence only. Use the status and supplied limits for products '
        'in discussion_plan.investigations. Unrequested ready tabs do not trigger intake '
        'or a plan announcement. Listed prices and identities stay in deterministic views.')
    context['conversation_state'] = {'already_said': sorted(flow.ux.view(owner, flow.current_chain.get(owner))['points']),
        'rules': [COMPOSITION], 'software_cards': plan['software_cards']}
    context['enrollment'] = enrollment_flow.context(flow, g, r)
    if not checks_relevant(flow, owner, g) and 'conversation_checks' in context:
        context['conversation_checks'].pop('current', None)
    return context


def finish(flow, owner, out, message, moves, **kwargs):
    s = state(flow, owner)
    if s['guidance']['mode'] == 'pause':
        out['assessment'].update(nextQuestion=None, intakePaused=True, conversationOpen=True)
    q = out['assessment'].get('nextQuestion')
    if q:
        s['asked'][q['id']] = s['asked'].get(q['id'], 0) + 1
    cards = copy.deepcopy(s.get('turn_cards', []))
    if out.get('generated', {}).get('status') != 'complete':
        # Never pretend a failed answer satisfied the outstanding question.
        s['plan']['answer_state'] = 'unresolved'
        if not out.get('reply'):
            out['reply'] = 'I don’t have a checked answer to that question here yet, so I won’t guess.'
        # A generation failure is ours, not a request for the person to reword
        # a clear goal. Keep the approved next question and any useful controls.
        if not out['assessment'].get('intakePaused') and moves:
            out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question'])
            suffix = '\n\nWhat would you like to understand next?'
            if out['reply'].endswith(suffix): out['reply'] = out['reply'][:-len(suffix)]
    else:
        s['plan']['answer_state'] = 'delivered' if s['latest']['question_quote'] else 'not_requested'
    for card in cards:
        s['cards'][card['kind']] = hashlib.sha256(repr(card).encode()).hexdigest()
    if cards: out['cards'] = cards
    if s.get('finish_requested'):
        s['outcome'], card = journey_completion.summary(flow, owner, out['guide'], out['record'], s, out)
        out['cards'] = [card]
        # A failed generation cannot replace the concrete software summary
        # with a generic rephrase/intake loop.
        if out.get('generated', {}).get('status') != 'complete':
            out['reply'] = 'Your visit summary keeps the work performed, open checks and next action together below.'
    flow.ux.record(owner, flow.current_chain.get(owner), out.get('reply', ''))
    attach(flow, owner, out)


def report_signature(g, r):
    from conversation_checks import reported_fields
    return hashlib.sha256(json.dumps(reported_fields(g, r), sort_keys=True).encode()).hexdigest()


def attach(flow, owner, out):
    s = state(flow, owner)
    out['conversationPlanner'] = {k: copy.deepcopy(v) for k, v in s['plan'].items() if k != 'question_to_answer'}
    out['conversationPlanner'].setdefault('version', VERSION)
    out['conversationPlanner'].update(purpose=s['purpose'], focus=s['focus'], investigations=list(s['investigate']))
    products = s.get('plans_products', [p for p in s.get('task_investigate', s['investigate']) if p in ('medigap', 'part_d', 'advantage')])
    out['conversationPlanner']['plans_view'] = ({'medigap': 'supplement', 'part_d': 'part-d', 'advantage': 'advantage'}[products[0]]
        if len(products) == 1 else 'paths')
    if s['focus'] == 'enrollment': out['conversationPlanner']['plans_view'] = 'ab'
    out['conversationPlanner']['medigap_variant'] = s.get('medigap_variant')
    out['conversationPlanner']['education_only'] = s.get('education_only', False)
    out['coveragePath'] = path(flow, owner, out['guide'], out['record'])
    out['conversationPlanner'].update(decision=copy.deepcopy(out['coveragePath']), exploring=list(s['exploring']),
        next_question=(out['assessment'].get('nextQuestion') or {}).get('id'))
    out['whatsLeft'] = None
    if 'conversationCheck' in out and not out['conversationCheck'].get('paused'):
        s['last_check_results'] = copy.deepcopy(out['conversationCheck'].get('results', []))
        s['last_check_signature'] = report_signature(out['guide'], out['record'])
    if s.get('outcome'):
        out['conversationPlanner']['outcome'] = copy.deepcopy(s['outcome'])
        out['assessment']['nextQuestion'] = None
        out['assessment']['intakePaused'] = True
        out['conversationPlanner']['next_question'] = None
        if out.get('enrollment'):
            out['enrollment']['record']['outcome'] = copy.deepcopy(s['outcome'])
    # Enrollment status remains factual. During exploration it must not tell a
    # person their next conversational step is choosing/buying a path.
    enrollment = out.get('enrollment')
    if isinstance(enrollment, dict) and isinstance(enrollment.get('line'), dict):
        line = enrollment['line']
        if out['coveragePath']['state'] != 'chosen' and line.get('next', {}).get('id', '').startswith('choose_'):
            line['next'] = {**line['next'], 'text': ''}
            line['text'] = line['status']
    return out
