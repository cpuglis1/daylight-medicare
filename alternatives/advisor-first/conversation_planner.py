"""D166: discussion-led planning for the unified demo only.

The interpreter proposes meaning; this module validates it and selects the
conversation's next useful move. It neither ranks plans nor admits evidence.
Planning memory is bounded, visit-only and never part of a saved profile.
"""
from collections import OrderedDict
import copy
import hashlib
import json
import re
import threading
import time

from adaptive_flow import metadata
from advisor_memory import HISTORY_TTL, VISIT_LIMIT
import enrollment_flow
import medigap_profile
import part_d_profile
import journey_completion

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
INTERPRETATION = '''
On this surface, discussion proposes the conversational meaning of this message.
Keep intent, facts, understanding, preferences, exploration and decisions distinct.
purpose is what the person wants help doing, not the product they mentioned.
focus is a topic, never a choice. reason_quote is an explicitly stated reason for
seeking help now; do not re-ask that reason when supplied. question_quote is the exact question/concern to
answer first (including requests without a question mark). quote supports purpose.
investigate lists only explicitly requested plan/price/doctor/drug investigations;
request_quote supports them. Explaining Medigap or comparing coverage structures
is not requesting Medigap prices. Prices on both paths are a legitimate inquiry
without a path preference. An unexplained 'show plans' has no inferred category.
decision has stance none/leaning/chosen/undecided and path. Only explicit current
first-person intentions of the beneficiary or helper support a decision. Asking
what a choice means, hypothetical/conditional choices, a named product, a priority,
or viewing a path cannot support it. Quote the full decisive clause. 'I want to
understand Medigap' is understand, not a decision. 'I want Original Medicare' does
not choose Medigap. Choosing a path never says an application was submitted.
If uncertain, leave decision none and uncertainty true. Familiarity stays in
learner_observations; preferences stay in validated reports. An answer to a CP_
question is a discussion response, not a new insurance fact unless independently
stated. Do not put any CP_ identifier in report updates.
'''
COMPOSITION = '''
discussion_plan is the authoritative conversation plan on this surface. It
replaces find mode, pricing-first intake and any fixed teaching sequence.
Answer the latest question first, with supported evidence and necessary
conditions. Then connect that answer to the person's situation or tradeoff and
ask the selected follow-up. Do not acknowledge merely filling fields. Use the
length the answer needs; there is no fixed sentence count. No quizzes or lesson
menu. A direct prices request does not require a completed education interview.
An explanation, a card viewed, an investigation and a reported preference are
not a choice. Only decisions explicitly reported by the person are choices.
Exploration is reversible and can cover both paths. General education needs no
ZIP, age, pricing sex or tobacco answer. Do not ask a price input unless the
discussion plan includes that investigation. Facts already reported and deferred
questions stay respected; confusion permits explanation again, never mastery
credit. Any uncertainty about a personal finding remains explicit.
For a requested investigation, explain its supplied unsupported/held limit and
useful alternatives. Do not keep collecting details that cannot enable it.
Use a ready tab only when relevant to the current discussion; its availability
is not an instruction to move the person to pricing.
software_cards names only cards actually attached to this turn. Describe their
purpose if useful; do not duplicate their numbers or dates. Do not announce a
price list just because it exists. Comparisons and recommendations still come
only from deterministic, authorized results; you cannot invent a preference,
recommendation, check or result. A pending check cannot hijack another question.
When finish_requested is present, answer any final question and close without
another intake question. Software supplies the recorded work, decision, open
checks and next action; do not claim an unresolved comparison is complete.
'''


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
        'decision': make({'stance': {'type': 'string', 'enum': ['none', 'leaning', 'chosen', 'undecided']},
                          'path': {'type': 'string', 'enum': list(PATHS)},
                          'quote': {'type': 'string', 'maxLength': 600}}),
    })


def empty_proposal():
    return dict(purpose='none', focus='', quote='', reason_quote='', question_quote='', investigate=[],
                request_quote='', uncertain=False, decision=dict(stance='none', path='', quote=''))


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
    request = value['request_quote']
    inv = value['investigate']
    if (isinstance(inv, list) and len(inv) <= 5 and all(isinstance(k, str) and k in INVESTIGATIONS for k in inv)
            and supported(request, message) and not value['uncertain'] and not UNREAL.search(request)
            and not NEGATED.search(request) and INVESTIGATING.search(request)
            and not (LEARNING.search(request) and not re.search(r'\b(?:price|pricing|premium|quote|how much)\w*\b', request, re.I))):
        both = bool(re.search(r'\bboth (?:paths|options)\b', request, re.I))
        anaphora = bool(re.search(r'\b(?:those|these|that|it|them)\b', request, re.I))
        grounded = [k for k in inv if PRODUCTS[k].search(request) or anaphora and k == focus
                    or both and k in ('medigap', 'advantage', 'part_d')]
        out.update(investigate=list(dict.fromkeys(grounded)), request_quote=request)
    decision = value['decision']
    if (isinstance(decision, dict) and set(decision) == {'stance', 'path', 'quote'}
            and decision['stance'] in ('none', 'leaning', 'chosen', 'undecided') and decision['path'] in PATHS
            and supported(decision['quote'], message) and not value['uncertain']):
        text = decision['quote']
        if decision['stance'] == 'undecided' and re.search(r"not (?:sure|decided)|undecided|haven.t (?:chosen|decided)", text, re.I):
            out['decision'] = dict(stance='undecided', path='', quote=text)
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


def conservative_request(message):
    """Fallback for missing/malformed interpreter metadata; never a choice."""
    out = empty_proposal()
    text = message[:600]
    if '?' in message or LEARNING.search(message) or re.match(r'\s*(?:why|how|what|which|when|where|is|does|can|could|should|would|do)\b', message, re.I):
        out.update(question_quote=text, purpose='understand', quote=text)
    if re.search(r'\b(?:sign[ -]?up|part [ab].*prepar\w*|a and b.*start\w*|enroll.*part [ab])\b', message, re.I):
        out['focus'] = 'enrollment'
    elif re.search(r'\b(?:two .*paths|both (?:paths|options)|advantage.*medigap|medigap.*advantage|original.*advantage|advantage.*original)\b', message, re.I):
        out['focus'] = 'coverage_paths'
    elif re.search(r'\boriginal medicare\b', message, re.I) and not PRODUCTS['medigap'].search(message):
        out['focus'] = 'original'
    else:
        out['focus'] = next((k for k, p in PRODUCTS.items() if p.search(message)), '')
        if not out['focus'] and re.search(r'\b(?:options|paths)\b', message, re.I):
            out['focus'] = 'coverage_paths'
    drug_cost = bool(re.search(r'\b(?:cost\w*|cheap\w*|price\w*|pay|order)\b', message, re.I)
                    and re.search(r'\b(?:medicine\w*|drug\w*|prescription\w*|pharmacy)\b', message, re.I))
    if (not UNREAL.search(message) and not NEGATED.search(message)
            and (re.search(r'\b(?:prices?|pricing|premiums?|quotes?|how much)\b', message, re.I)
                 or drug_cost or re.search(r'\b(?:show|see|find|compare|review|look at)\b.{0,50}\b(?:plans?|options|advantage)\b', message, re.I))):
        inv = [k for k in ('medigap', 'advantage', 'part_d') if PRODUCTS[k].search(message)]
        # A held supplement is context for separate drug research, not a
        # request to price that supplement again.
        if drug_cost and 'part_d' in inv and re.search(r'\bkeep\w*\b.{0,20}\b(?:plan g|medigap|supplement)\b', message, re.I):
            inv = [k for k in inv if k != 'medigap']
        if re.search(r'\bboth (?:paths|options)\b', message, re.I):
            inv = ['medigap', 'advantage', 'part_d']
        out.update(purpose='investigate', quote=text, investigate=inv, request_quote=text)
        if drug_cost:
            out['investigate'] = list(dict.fromkeys(inv + ['medicines']))
    if (re.search(r'(?:^\s*(?:please )?|\b(?:can|could|would) you )(?:check|compare|research)\b.{0,35}\b(?:doctors?|medicines?)\b', message, re.I)
            and not UNREAL.search(message) and not NEGATED.search(message)):
        inv = [k for k in ('doctors', 'medicines') if PRODUCTS[k].search(message)]
        out.update(purpose='investigate', quote=text, investigate=inv, request_quote=text)
    clauses = re.split(r'(?<=[.!?])\s+|;', message)
    if len(clauses) > 1:
        # A negative factual report elsewhere must not cancel an explicit
        # investigation request (e.g. “Compare 2027. I don't want old plans”).
        requests = [conservative_request(clause) for clause in clauses if clause.strip()]
        explicit = [p for p in requests if p['purpose'] == 'investigate' and p['investigate']]
        if explicit:
            latest = explicit[-1]
            out.update(purpose='investigate', investigate=latest['investigate'],
                       request_quote=latest['request_quote'], quote=latest['quote'])
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
    return dict(id=identifier, entity='profile', question=words, why=why, fields=[], choices=[],
                multi=False, signature=VERSION + ':' + identifier, conversational=True)


def observe(flow, owner, g, r, message, result, current=None):
    s = state(flow, owner)
    s.pop('outcome', None)
    s['finish_requested'] = journey_completion.request(message)
    checks = getattr(flow, 'conversation_checks', None)
    if checks and re.search(r"\b(?:don['’]t know|do not know|not sure|don['’]t have|leave (?:it|that|this) open)\b", message, re.I):
        visit = checks.visits.get(owner) or {}
        pending = visit.get('question')
        if pending and pending.get('field') in ('quantity', 'days_supply', 'rxcui', 'formulary_product', 'fills', 'assistance', 'drug_details'):
            checks.answer(owner, g, r, pending['token'], '__later__', parked=True)
    p = validate_proposal(result.get('discussion'), message, s['focus'])
    fallback = conservative_request(message)
    if p['purpose'] == 'none':
        p = {**fallback, 'decision': p['decision'], 'reason_quote': p['reason_quote'],
             'question_quote': p['question_quote'] or fallback['question_quote']}
    if (p['purpose'] == 'investigate' and not p['investigate'] and s['focus'] in INVESTIGATIONS
            and re.search(r'\b(?:those|these|that|it|them)\b', p['request_quote'], re.I)):
        p['investigate'] = [s['focus']]
    if p['purpose'] == 'investigate' and not p['investigate'] and s.get('task_investigate'):
        p['investigate'] = list(s['task_investigate'])
    elif not p['question_quote']:
        p['question_quote'] = fallback['question_quote']
    research_reports = {u.get('id') for u in result.get('updates', [])} & {'RC21', 'RC22', 'RC23', 'T06', 'T07'}
    if research_reports and not p['question_quote'] and s.get('task_investigate'):
        p.update(purpose='investigate', investigate=list(s['task_investigate']))
    s['latest'] = p
    if re.search(r"\b(?:matters? (?:most|more)|priority|too (?:much|expensive)|lowest total|keep\w* my doctor)\b", message, re.I):
        s['reason_known'] = True
    if re.search(r"\b(?:education only|just want to understand|not ready to give personal|skip personal details|not asked for a quote)\b", message, re.I):
        s['education_only'] = True
    if p['purpose'] == 'investigate' and p['investigate']:
        s['education_only'] = False
    if p['purpose'] == 'investigate' and 'medicines' in p['investigate']:
        held = flow.value(g, 'coverage.current') or []
        if not set(p['investigate']) & {'advantage', 'part_d'}:
            if 'advantage' in held: p['investigate'].append('advantage')
            elif 'drug' in held or PRODUCTS['part_d'].search(message): p['investigate'].append('part_d')
    if p['reason_quote']:
        s['reason_known'] = True
    s['clarify_understanding'] = any(item.get('signal') in ('uncertain', 'misconception', 'unfamiliar')
        and supported(item.get('quote'), message) for item in result.get('learner_observations', []))
    if (current or {}).get('id') in DISCUSSION_QUESTIONS and not p['question_quote']:
        s['asked'][(current or {})['id']] = 2
        if current['id'] == 'CP_REASON':
            s['reason_known'] = True
    if re.search(r"\b(?:leave|skip|defer|later|don['’]t know|not sure)\b", message, re.I) and current and not p['question_quote']:
        if current['id'] not in s['deferred']:
            s['deferred'].append(current['id'])
            s['deferred'] = s['deferred'][-24:]
    if p['purpose'] != 'none':
        s['purpose'] = p['purpose']
    if p['focus']:
        s['focus'] = p['focus']
    if s['finish_requested'] == 'ab_preparation':
        s['focus'] = 'enrollment'
    if p['purpose'] == 'investigate':
        s['investigate'] = p['investigate']
        if p['investigate']:
            s['task_investigate'] = list(p['investigate'])
            products = [v for v in p['investigate'] if v in ('medigap', 'part_d', 'advantage')]
            if products: s['plans_products'] = products
        match = re.search(r'\b(?:standard )?plan ([a-dfgk-n])\b', p['request_quote'], re.I)
        if match and 'medigap' in p['investigate']:
            s['medigap_variant'] = ('HD' if re.search(r'high[ -]deductible', p['request_quote'], re.I) else '') + match.group(1).upper()
        s['exploring'] = list(dict.fromkeys(s['exploring'] + p['investigate']))[-5:]
    elif p['purpose'] in ('understand', 'review', 'problem', 'compare') and p['quote']:
        # A question interrupts an investigation. The old target is retained as
        # exploration, but technical intake does not resume until it is useful.
        s['exploring'] = list(dict.fromkeys(s['exploring'] + s['investigate']))[-5:]
        s['investigate'] = []
    d = p['decision']
    if s['finish_requested'] in ('keep_current', 'wait'):
        d = {'stance': 'chosen', 'path': s['finish_requested'], 'quote': message}
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
    # Task is an evidence/dependency lens. It is never the authority to ask a
    # price question; refine() checks the explicit investigation independently.
    focus_task = {'enrollment': 'timing', 'doctors': 'providers', 'medicines': 'drug_coverage',
                  'costs': 'costs', 'medigap': 'medigap', 'part_d': 'drug_pricing'}
    task = ('medigap' if 'medigap' in s['investigate'] else 'drug_pricing' if 'part_d' in s['investigate']
            else focus_task.get(s['focus'], 'review' if s['purpose'] == 'review' else 'compare'))
    # Education about a product must not invoke its legacy preparation mode.
    if not s['investigate'] and task in ('medigap', 'drug_pricing'):
        task = 'compare'
    metadata(r).update(task=task, preparing=bool(s['investigate']))


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
    if s.get('finish_requested'):
        return []
    reports = [flow.value(g, field) or {} for field in enrollment_flow.PART_FIELDS.values()]
    if any(report.get('status') == 'conflicting' for report in reports):
        return [candidate(flow, g, r, 'CP_PARTS')]
    if (set(flow.value(g, 'coverage.current') or []) & {'advantage', 'medigap'}
            and any(report.get('status') == 'not_enrolled' for report in reports)
            and not s['asked'].get('CP_COVERAGE')):
        return [candidate(flow, g, r, 'CP_COVERAGE')]
    if metadata(r).get('editing'):
        return candidates
    required = [c for c in candidates if c.get('required')]
    if required and not (s['latest']['question_quote'] and s['purpose'] == 'understand'):
        return required
    selected = []
    dispositions = {**metadata(r).get('baselineDispositions', {}), **r.get('dispositions', {})}
    def add(identifier, purpose=''):
        limit = 1 if identifier in DISCUSSION_QUESTIONS else 2
        if identifier in dispositions or identifier in s['deferred'] or s['asked'].get(identifier, 0) >= limit:
            return
        c = next((copy.deepcopy(x) for x in candidates if x['id'] == identifier), None)
        c = c or candidate(flow, g, r, identifier, purpose)
        if c and not any(x['id'] == identifier for x in selected):
            if purpose: c['purpose'] = purpose
            selected.append(c)
    purpose, focus = s['purpose'], s['focus']
    investigation = s['investigate'] if purpose == 'investigate' else []
    role = flow.value(g, 'subject.role')
    coverage = flow.value(g, 'coverage.current')
    if purpose == 'none' and not role:
        add('CP_PURPOSE')
    elif purpose == 'investigate':
        if not investigation:
            add('CP_INVESTIGATE')
        for product in investigation:
            if product == 'medigap':
                view = medigap_profile.profile(g)
                if view['status'] != 'unsupported':
                    for identifier in view['missing']:
                        if identifier not in view['held']:
                            add(identifier, 'This detail is needed for the Medigap prices the person requested; explain why.')
            elif product in ('advantage', 'part_d'):
                view = part_d_profile.profile(g, r)
                if view['status'] != 'unsupported':
                    for identifier in view['missing']:
                        if identifier not in view['held']:
                            add(identifier, 'Locate the dated plan list the person requested.')
            elif product in ('doctors', 'medicines'):
                identifier = 'T06' if product == 'doctors' else 'T07'
                if not flow.value(g, 'needs.providersStatus' if product == 'doctors' else 'needs.medicinesStatus'):
                    add(identifier)
                if not flow.value(g, 'comparison.scope.zip'): add('T03')
        if not selected: add('CP_REACTION')
    elif s['decision']['stance'] == 'chosen' and s['decision']['path'] in ('keep_current', 'wait') and not s['latest']['question_quote']:
        add('CP_NEXT', 'Respect the decision; leave further investigation optional.')
    elif focus == 'enrollment':
        for c in candidates:
            if c['id'] in ('RC01', 'RC04', 'S_AGE65', 'RC05', 'RC06', 'RC09', 'RC10', 'RC11', 'RC12', 'RC13', 'RC14'):
                add(c['id'])
        if not selected: add('CP_NEXT')
    elif purpose == 'understand' or s.get('clarify_understanding'):
        add('CP_UNDERSTANDING', 'Answer the concept question; invite clarification without requiring personal intake.')
        if not selected: add('CP_REACTION', 'Connect this explanation to what the person is weighing; avoid repeating the previous follow-up.')
    elif purpose == 'compare' and s['latest']['question_quote'] and not role:
        add('CP_REACTION', 'Explain the paths first; discover which tradeoff matters to this person.')
    else:
        # Understand the present situation before asking what to buy. A/B
        # enrollment alone does not answer which other coverage is held.
        if not role:
            add('RC01')
        elif not coverage:
            add('T05', 'Understand current coverage, including anything alongside A and B, before comparing changes.')
        elif not s['reason_known'] and purpose in ('review', 'problem', 'compare', 'understand'):
            add('CP_REASON')
        if not selected and not flow.value(g, 'needs.priorities'):
            add('T10', 'Explore what matters to this person, not which product they should choose.')
        if not selected:
            priorities = set(flow.value(g, 'needs.priorities') or [])
            for identifier, relevant, value in (
                ('T06', bool(priorities & {'doctors', 'flexibility'}), flow.value(g, 'needs.providersStatus')),
                ('T08', bool(priorities & {'travel', 'flexibility'}), flow.value(g, 'needs.travel')),
                ('T07', bool(priorities & {'drugs', 'medicines'}), flow.value(g, 'needs.medicinesStatus')),
                ('T09', bool(priorities & {'bills', 'total_cost'}), flow.value(g, 'needs.costPreference'))):
                if relevant and not value: add(identifier)
        if not selected: add('CP_REACTION')
    if not selected:
        # No endlessly repeated fixed question: allow a contextual educational
        # follow-up. The model cannot use a null target for personal intake.
        return []
    return selected[:8]


def target(flow, owner, g, r, moves, required_id, required_reason):
    selected = next((m for m in moves if m.get('required')), None) or next(iter(moves), None)
    return (selected['id'], 'discussion') if selected else (None, None)


def checks_relevant(flow, owner, g=None):
    s = state(flow, owner)
    if s.get('finish_requested') or s.get('outcome'):
        return False
    if s['purpose'] == 'understand':
        return False
    if (set(s['investigate']) & {'doctors', 'medicines'} or s['focus'] in ('doctors', 'medicines')):
        return True
    return bool(g and not s['latest']['question_quote'] and any(
        flow.value(g, field) for field in ('needs.providers', 'needs.medications')))


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
    if kind == 'enrollment_decision':
        if 'start_with' in action:
            focus = {'original_medigap': 'original', 'medicare_advantage': 'advantage', 'both': 'coverage_paths'}[action['start_with']]
            s.update(purpose='understand', focus=focus, investigate=[], latest=empty_proposal())
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
    elif 'advantage' in (flow.value(g, 'coverage.current') or []) and (
            re.search(r'\btrial right\b', s['latest']['question_quote'], re.I)):
        trial = enrollment_flow.trial_right(flow, g, r, enrollment_flow._today())
        if trial:
            cards.append(trial)
    pages = flow.plans_pages(g, r)
    if s['purpose'] == 'investigate':
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
        'finish_requested': s.get('finish_requested'),
        'answer_first': bool(s['latest']['question_quote']), 'question_to_answer': s['latest']['question_quote'],
        'investigations': list(s['investigate']), 'exploring': list(s['exploring']),
        'decision': path(flow, owner, g, r), 'next_question': moves[0]['id'] if moves else None,
        'deferred_questions': list(s['deferred']), 'software_cards': [c['kind'] for c in s['turn_cards']],
        'understanding_is_not_delivery': True}
    s['plan'] = plan
    context['discussion_plan'] = copy.deepcopy(plan)
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
    q = out['assessment'].get('nextQuestion')
    if q:
        s['asked'][q['id']] = s['asked'].get(q['id'], 0) + 1
    cards = copy.deepcopy(s.get('turn_cards', []))
    if (out.get('generated', {}).get('status') != 'complete'
            or out.get('generated', {}).get('validation_recovery', {}).get('component') == 'question'):
        # Never pretend a failed answer satisfied the outstanding question.
        s['plan']['answer_state'] = 'unresolved'
        if not out.get('reply'):
            out['reply'] = 'I don’t have a checked answer to that question here yet, so I won’t guess.'
        if 'couldn’t finish' in (out.get('notice') or ''): out.pop('notice', None)
        if s['latest']['question_quote'] and not out['assessment'].get('intakePaused'):
            out['assessment']['nextQuestion'] = question('CP_RETRY')
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
