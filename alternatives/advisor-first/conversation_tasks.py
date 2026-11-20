"""D173: supported work and conditional questions, independent of user wording.

The model interprets intent and chooses a useful question. This adapter exposes
existing capabilities and dependencies; it does not interpret sentences, choose
insurance, accept sources, or perform external actions.
"""
import copy
from adaptive_flow import AdaptiveConversation, metadata, FIELD
from adaptive_agent import CHECKS
from plan_review import readiness

TASKS = {
    'compare': 'Compare coverage structures and tradeoffs using the person’s priorities.',
    'review': 'Review current coverage and what the person wants to change or retain.',
    'timing': 'Organize enrollment steps, actual coverage and distinct transition dates.',
    'providers': 'Check reported doctors and exact offices against available participation/network evidence.',
    'drug_coverage': 'Identify medicines and check available formulary evidence and restrictions.',
    'drug_pricing': 'Prepare medicine, refill and pharmacy inputs for supported drug-cost comparisons.',
    'medigap': 'Inspect available Medigap policies and published premiums; acceptance is separate.',
    'advantage': 'Inspect available Medicare Advantage plans within their supported location and year.',
    'costs': 'Clarify the person’s cost priorities, budget scope and available cost components.',
}
INVESTIGATIONS = {
    'compare': ('medigap','advantage','part_d','doctors','medicines'),
    'review': ('medigap','advantage','part_d','doctors','medicines'),
    'timing': (), 'providers': ('doctors',), 'drug_coverage': ('medicines',),
    'drug_pricing': ('part_d','medicines'), 'medigap': ('medigap',),
    'advantage': ('advantage','doctors','medicines'), 'costs': (),
}
DEFAULT_INVESTIGATIONS = {'providers':['doctors'], 'drug_coverage':['medicines'],
    'drug_pricing':['part_d','medicines'], 'medigap':['medigap'], 'advantage':['advantage']}
FOCI = {'compare':'coverage_paths','review':'coverage_paths','timing':'enrollment',
        'providers':'doctors','drug_coverage':'medicines','drug_pricing':'part_d',
        'medigap':'medigap','advantage':'advantage','costs':'costs'}
MODES = ('discuss', 'suggest', 'work', 'detour', 'pause', 'finish')
FINISHES = ('', 'summary', 'ab_preparation', 'keep_current', 'wait')
TOPICS = {'compare':'coverage_paths','review':'coverage_paths','timing':'timing',
          'providers':'doctors','drug_coverage':'drugs','drug_pricing':'drugs',
          'medigap':'coverage_paths','advantage':'coverage_paths','costs':'total_cost'}


def empty():
    return dict(mode='discuss', task='', checks=[], quote='', finish='')


def schema(make):
    return make(dict(mode={'type':'string','enum':list(MODES)},
        task={'type':'string','enum':['', *TASKS]},
        checks={'type':'array','maxItems':len(CHECKS),'items':{'type':'string','enum':list(CHECKS)}},
        quote={'type':'string','maxLength':600},
        finish={'type':'string','enum':list(FINISHES)}))


def validate(value, message):
    out = empty()
    if (not isinstance(value, dict) or set(value) != set(out)
            or value['mode'] not in MODES or value['task'] not in ('', *TASKS)
            or value['finish'] not in FINISHES or not isinstance(value['checks'], list)
            or len(value['checks']) > len(CHECKS) or any(c not in CHECKS for c in value['checks'])
            or not isinstance(value['quote'], str) or not 0 < len(value['quote'].strip()) <= 600
            or value['quote'].casefold() not in message.casefold()):
        return out
    return copy.deepcopy(value)


def candidates(flow, g, r, task, checks=()):
    """Walk one supported task on a shadow record; never invent reported facts."""
    if task not in TASKS: return []
    shadow = copy.deepcopy(r)
    meta = metadata(shadow)
    meta.update(task='compare' if task == 'advantage' else task, preparing=True, editing=None)
    meta['checks'] = list(dict.fromkeys(checks))
    found, seen = [], set()
    for _ in range(48):
        q = AdaptiveConversation.assess(flow, g, shadow).get('nextQuestion')
        if not q: break
        key = (q['id'], q.get('entity', 'profile'), tuple(f['key'] for f in q.get('fields', [])))
        if key in seen: break
        seen.add(key)
        if q['id'] != 'T04' and flow.target_relevant(g, r, q['id']):
            found.append(dict(id=q['id'], question=flow.contextual_question(g, r, q),
                topic=TOPICS[task], priority=1, required=False,
                purpose=q.get('why') or TASKS[task]))
        if q['id'].startswith('T'):
            meta['baselineDispositions'][q['id']] = 'deferred'
        else:
            shadow['dispositions'][q['id']] = {'state':'deferred'}
            for field in q.get('fields', []):
                meta['skippedDetails']['.'.join((q['id'],q.get('entity','profile'),field['key']))] = 'deferred'
    # Reuse the existing comparison checkpoint and approved preference fields;
    # these are information requirements, not conversational ordering rules.
    checkpoint = readiness(g, r)
    additions = [(item['question_id'], item.get('fields')) for item in checkpoint.get('criteria', [])
                 if not item['addressed'] and item['question_id'] != 'T01'] if task in ('compare','review') else []
    if task in ('compare','review','costs'):
        additions += [(identifier, None) for identifier in ('T09','T10') if flow.value(g, FIELD[identifier]) is None]
    if task == 'costs' and not flow.report(r, 'RC25'):
        additions.append(('RC25', ['amount','includes']))
    for identifier, fields in additions:
        if any(c['id'] == identifier for c in found): continue
        q = flow.contextual_question(g, r, flow.question(identifier, fields))
        if q: found.append(dict(id=identifier, question=q, topic=TOPICS[task], priority=1, required=False,
                               purpose=q.get('why') or TASKS[task]))
    return found


def context(flow, g, r):
    """Capability facts, not a scripted order or an intent recognizer."""
    pages = flow.plans_pages(g, r)
    result = []
    for task, description in TASKS.items():
        row = dict(id=task, purpose=description, investigations=list(INVESTIGATIONS[task]),
                   execution='reported-input preparation and existing checked services')
        product = {'medigap':'medigap','drug_pricing':'part_d','advantage':'advantage'}.get(task)
        if product and product in pages:
            row['availability'] = copy.deepcopy(pages[product])
        result.append(row)
    return {'tasks':result, 'conditional_checks':list(CHECKS),
            'limits':'Capabilities do not authorize transactions, personal recommendations or source acceptance. Missing/held evidence remains explicit.'}
