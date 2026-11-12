"""Local, value-free provenance and permissioned context for natural conversation.

The pinned engine uses ``confirmed_by_user`` as a legacy wire constraint.  New
reports carry an honest local confirmation plus versioned provenance; projection
is a compatibility boundary, never evidence that the person confirmed a summary.
These helpers do not apply reports, authorize actions, save data or verify facts.
"""
import copy
import json
import math
import re
from timing_language import end_date_refinement

VERSION = 1
CONTEXT_VERSION = 'natural-context-v1'
PROFILE_CONTEXT_VERSIONS = frozenset({CONTEXT_VERSION, 'natural-context-v2'})
SAFE_FIELDS = frozenset({'intent.goal', 'knowledge.general', 'subject.role', 'coverage.current'})
# Existing guide omissions plus the two separately protected local circumstances.
SENSITIVE_GUIDE_FIELDS = frozenset({'coverage.requestedStartMonth', 'needs.medicationDetails',
    'intent.goalDetail', 'needs.priorityOther', 'subject.displayLabel', 'coverage.birth',
    'coverage.birth.firstDay', 'needs.medications', 'needs.pharmacies', 'needs.providers',
    'outcome.drafts', 'comparison.requestedNames', 'situation.retirement', 'situation.age65'})
CONFIRMATIONS = {'user_reported': 'reported_by_user', 'explicitly_confirmed': 'explicitly_confirmed'}
# plans_filter: a structured answer entered on the Plans page (D97). It is a
# user report like any structured answer; the conversation confirms it once.
METHODS = {'direct_report', 'structured', 'explicit_confirmation', 'plans_filter'}
SCOPES = {'current', 'intended', 'historical', 'unknown'}
SUBJECTS = {'beneficiary', 'learner', 'unclear'}
UNRESOLVED = {'unknown', 'deferred', 'not sure', 'check later', 'later', ''}
TASKS = {'', 'learn', 'browse', 'compare', 'review', 'timing', 'providers',
         'drug_coverage', 'drug_pricing', 'medigap', 'snp', 'costs'}
ENTITY = re.compile(r'(?:profile|(?:doctor|medicine)-(?:extra-)?[0-9]{1,3})\Z')
QUESTION = re.compile(r'(?:T(?:0[1-9]|10)|RC(?:0[1-9]|1[0-9]|2[0-8])|RC11\.C1|RC16\.C[12])\Z')
REF = re.compile(r'(?:guide\.[A-Za-z][A-Za-z0-9_.]{0,99}|readiness\.RC(?:0[1-9]|1[0-9]|2[0-8])(?:\.(?:profile|(?:doctor|medicine)-(?:extra-)?[0-9]{1,3})\.[A-Za-z][A-Za-z0-9]{0,29})?)\Z')
FIELD_NAMES = {
    'T01': {'choice', 'text'}, 'T02': {'choice'}, 'T03': {'zip', 'county'},
    'T04': {'choice', 'month'}, 'T05': {'choice'}, 'T06': {'choice', 'text'},
    'T07': {'choice', 'text'}, 'T08': {'choice'}, 'T09': {'choice'}, 'T10': {'choice', 'text'},
    'RC01': {'choice'}, 'RC02': {'choice', 'zip', 'county', 'homeStatus'},
    'RC03': {'choice', 'year'}, 'RC04': {'choice'}, 'RC05': {'choice', 'month'},
    'RC06': {'choice', 'ageBand'}, 'RC07': {'choice'}, 'RC08': {'choice', 'eventDate'},
    'RC09': {'choice'}, 'RC10': {'choice'}, 'RC11': {'choice', 'jobEnd', 'coverageEnd'},
    'RC12': {'choice', 'gap'}, 'RC13': {'choice'}, 'RC14': {'choice'},
    'RC15': {'choice', 'event'}, 'RC16': {'choice', 'start', 'priorMedigap'},
    'RC17': {'choice'}, 'RC18': {'choice'}, 'RC19': {'choice', 'qualification'},
    'RC20': {'choice', 'location'}, 'RC21': {'choice', 'practice', 'city'},
    'RC22': {'choice', 'name', 'strength', 'form', 'brand'},
    'RC23': {'choice', 'quantity', 'daysSupply', 'pharmacy', 'channel', 'supply'},
    'RC24': {'choice'}, 'RC25': {'choice', 'amount', 'includes'},
    'RC26': {'choice'}, 'RC27': {'choice'}, 'RC28': {'choice'},
}
# Clarification-only targets. They do not extend the original question inventory
# or make a life circumstance a required intake item.
SITUATION_TARGETS = {'S_AGE65': {'month', 'year'}, 'S_RETIREMENT': {'status', 'when'}}
_LOCATION = {'comparison.scope.zip', 'comparison.scope.county'}
_PRIORITIES = {'needs.costPreference', 'needs.priorities'}
_TIMING = {'coverage.requestedStart', 'coverage.requestedStartMonth',
           'situation.retirement', 'situation.age65'}
_PROVIDERS = {'needs.providersStatus', 'needs.providers', 'needs.travel'}
_MEDICINES = {'needs.medicinesStatus', 'needs.medications'}
GUIDE_ALLOWLIST = {
    'timing': _TIMING,
    'providers': _LOCATION | _PROVIDERS,
    'drug_coverage': _LOCATION | _MEDICINES,
    'drug_pricing': _LOCATION | _MEDICINES | {'needs.pharmacies'},
    'medigap': _LOCATION | _TIMING,
    'compare': _LOCATION | _PRIORITIES | _PROVIDERS | _MEDICINES,
    'review': _LOCATION | _PRIORITIES | _PROVIDERS | _MEDICINES,
    'snp': _LOCATION,
    'costs': _LOCATION | _PRIORITIES,
}
READINESS_ALLOWLIST = {
    'timing': {'RC01', 'RC03', 'RC04', 'RC05', 'RC06', 'RC07', 'RC08', 'RC09',
               'RC10', 'RC11', 'RC12', 'RC13', 'RC14', 'RC26', 'RC27'},
    'providers': {'RC01', 'RC02', 'RC03', 'RC20', 'RC21'},
    'drug_coverage': {'RC01', 'RC03', 'RC07', 'RC12', 'RC22', 'RC24'},
    'drug_pricing': {'RC01', 'RC02', 'RC03', 'RC18', 'RC22', 'RC23', 'RC24'},
    'medigap': {'RC01', 'RC02', 'RC03', 'RC04', 'RC05', 'RC06', 'RC07', 'RC08',
                'RC11', 'RC15', 'RC16', 'RC17'},
    'compare': {'RC01', 'RC02', 'RC03', 'RC04', 'RC07', 'RC20', 'RC21', 'RC22'},
    'review': {'RC01', 'RC02', 'RC03', 'RC04', 'RC07', 'RC20', 'RC21', 'RC22'},
    'snp': {'RC01', 'RC02', 'RC03', 'RC04', 'RC18', 'RC19'},
    'costs': {'RC01', 'RC02', 'RC03', 'RC18', 'RC25'},
}
CANNOT_INFER = [
    'Reported facts are not verified coverage, eligibility, prices or permission.',
    'Retirement does not establish retiree insurance or an insurance end date.',
    'Birthday, desired start, job end, insurance end and actual enrollment are distinct.',
    'A soonest-possible desired start is a preference, not an exact start month or actual enrollment.',
    'Unknown, deferred, none, tentative and stale are distinct; do not invent missing precision.',
    'A helper report does not become a beneficiary fact; a name does not verify an entity or coverage.',
]
AGENDA_TOPICS = frozenset({'doctors','drugs','total_cost','bills','travel','flexibility',
    'timing','learning','coverage_paths','current_coverage','other'})
PRIORITY_TOPICS = frozenset({'doctors','drugs','total_cost','bills','travel','other'})
MOVE_KINDS = frozenset({'ask','answer','teach','clarify','revise','invite'})
MOVE_REASONS = frozenset({'missing_dependency','user_question','contextual_teaching',
    'clarify_conflict','priority_change','open_learning'})
TASK_TOPICS = {
    'timing':{'timing','current_coverage','learning'},
    'providers':{'doctors','travel','flexibility'},
    'drug_coverage':{'drugs','total_cost','bills'},
    'drug_pricing':{'drugs','total_cost','bills'},
    'medigap':{'total_cost','bills','flexibility','coverage_paths','timing'},
    'learn':{'learning','coverage_paths'}, 'costs':{'total_cost','bills'},
    'compare':set(AGENDA_TOPICS), 'review':set(AGENDA_TOPICS),
    'browse':{'coverage_paths'}, 'snp':{'coverage_paths','current_coverage'}, '':set(),
}


def ensure_agenda(record):
    state = ensure_state(record)
    if 'agenda' not in state:
        state['agenda'] = {'version':1,'concerns':[],'priorityReasons':[],'lastMove':None}
    validate_state(record)
    return state['agenda']


def _validate_agenda(agenda):
    if (not isinstance(agenda,dict) or set(agenda)!={'version','concerns','priorityReasons','lastMove'}
            or type(agenda['version']) is not int or agenda['version']!=1
            or not isinstance(agenda['concerns'],list) or len(agenda['concerns'])>8
            or not isinstance(agenda['priorityReasons'],list) or len(agenda['priorityReasons'])>4):
        raise ValueError('Unsupported decision agenda.')
    for item in agenda['concerns']:
        if (not isinstance(item,dict) or set(item)!={'topic','subject','scope','status','revision'}
                or not all(isinstance(item[key],str) for key in ('topic','subject','scope','status'))
                or item['topic'] not in AGENDA_TOPICS or item['subject'] not in {'beneficiary','learner'}
                or item['scope'] not in {'current','intended'} or item['status'] not in {'open','addressed','deferred'}
                or type(item['revision']) is not int or item['revision']<0):
            raise ValueError('Unsupported explicit concern.')
    for item in agenda['priorityReasons']:
        if (not isinstance(item,dict) or set(item)!={'topic','reason','subject','scope','priorityRevision','revision'}
                or not all(isinstance(item[key],str) for key in ('topic','subject','scope'))
                or item['topic'] not in PRIORITY_TOPICS or item['subject']!='beneficiary' or item['scope']!='current'
                or not isinstance(item['reason'],str) or not 1<=len(item['reason'])<=160 or not _safe_value(item['reason'])
                or type(item['priorityRevision']) is not int or item['priorityRevision']<0
                or type(item['revision']) is not int or item['revision']<0):
            raise ValueError('Unsupported explicit priority reason.')
    move=agenda['lastMove']
    if move is not None and (not isinstance(move,dict) or set(move)!={'kind','topic','reason'}
            or not all(isinstance(move[key],str) for key in ('kind','topic','reason'))
            or move['kind'] not in MOVE_KINDS or move['topic'] not in AGENDA_TOPICS|{''}
            or move['reason'] not in MOVE_REASONS):
        raise ValueError('Unsupported advisor move.')


def sync_agenda(guide,record):
    """Old reasons never outlive their explicit current priority revision."""
    state=ensure_state(record)
    if 'agenda' not in state:return
    envelope=guide.get('fields',{}).get('needs.priorities',{})
    values=envelope.get('value',[])
    usable=(envelope.get('status')=='reported' and isinstance(values,list)
            and 'T10' not in record.get('conversation',{}).get('baselineDispositions',{})
            and envelope.get('confirmation') in {'reported_by_user','explicitly_confirmed','confirmed_by_user'})
    state['agenda']['priorityReasons']=[item for item in state['agenda']['priorityReasons']
        if usable and item['topic'] in values and item['priorityRevision']==envelope.get('revision')]


def apply_agenda_reports(guide,record,message,proposal,accepted_updates=()):
    """Resolve bounded explicit decision context; never infer a preference.

    Topic enums are discourse hints. Reason text is a sensitive user report tied
    to a current T10 revision, not a new coverage/policy fact or action authority.
    Invalid agenda proposals do not discard independent profile reports.
    """
    sync_agenda(guide,record)
    if not isinstance(proposal,dict) or set(proposal)!={'concerns','priorityReason'}:return
    agenda=ensure_agenda(record)
    before=copy.deepcopy(agenda)
    def supported(quote):
        return (isinstance(quote,str) and 1<=len(quote)<=360 and quote.casefold() in message.casefold()
            and not re.search(r'\b(?:if|suppose|hypothetically|for example|used to)\b',quote,re.I))
    concerns=proposal.get('concerns')
    if isinstance(concerns,list) and len(concerns)<=2:
        for item in concerns:
            if (not isinstance(item,dict) or set(item)!={'topic','subject','scope','status','quote'}
                    or not all(isinstance(item[key],str) for key in ('topic','subject','scope','status'))
                    or item['topic'] not in AGENDA_TOPICS or item['subject'] not in {'beneficiary','learner'}
                    or item['scope'] not in {'current','intended'} or item['status'] not in {'open','addressed','deferred'}
                    or not supported(item['quote'])):continue
            quote=item['quote']
            if item['status']=='open' and (not re.search(r'\b(?:worr(?:y|ied)|concern|care about|matters?|important|priorit(?:y|ies)|prefer|want to keep|need to keep|want to understand|need to understand)\b',quote,re.I)
                    or re.search(r"\b(?:not worried|no longer|don['’]?t care|do not care)\b",quote,re.I)):continue
            if (item['subject']=='beneficiary' and guide.get('fields',{}).get('subject.role',{}).get('value')=='someone'
                    and re.search(r"\bI(?:['’]m| am| worry| care| want| prefer)\b",quote,re.I)
                    and not re.search(r'\b(?:mother|father|mom|dad|parent|spouse|wife|husband)\b',quote,re.I)):continue
            key=(item['topic'],item['subject'],item['scope'])
            old=next((x for x in agenda['concerns'] if (x['topic'],x['subject'],x['scope'])==key),None)
            if item['status']!='open' and not old:continue
            agenda['concerns']=[x for x in agenda['concerns'] if (x['topic'],x['subject'],x['scope'])!=key]
            agenda['concerns'].append({k:item[k] for k in ('topic','subject','scope','status')}|{'revision':record['stateVersion']+1})
            agenda['concerns']=agenda['concerns'][-8:]
    reason=proposal.get('priorityReason')
    envelope=guide.get('fields',{}).get('needs.priorities',{})
    updates=[item for item in accepted_updates if item.get('id')=='T10' and item.get('subject')=='beneficiary'
             and item.get('scope')=='current' and not item.get('uncertain')]
    if (isinstance(reason,dict) and set(reason)=={'topic','reason','quote','subject','scope'}
            and all(isinstance(reason[key],str) for key in ('topic','subject','scope'))
            and reason['topic'] in PRIORITY_TOPICS and reason['subject']=='beneficiary' and reason['scope']=='current'
            and isinstance(reason['reason'],str) and 1<=len(reason['reason'])<=160
            and supported(reason['quote']) and reason['reason'].casefold() in reason['quote'].casefold()
            and not re.search(r'\b(?:I think|maybe|might|probably|not sure|I guess)\b',reason['quote'],re.I)
            and _safe_value(reason['reason']) and updates and envelope.get('status')=='reported'
            and reason['topic'] in envelope.get('value',[])):
        agenda['priorityReasons']=[x for x in agenda['priorityReasons'] if x['topic']!=reason['topic']]
        agenda['priorityReasons'].append({'topic':reason['topic'],'reason':reason['reason'],
            'subject':'beneficiary','scope':'current','priorityRevision':envelope['revision'],
            'revision':record['stateVersion']+1})
        agenda['priorityReasons']=agenda['priorityReasons'][-4:]
    if agenda!=before:record['stateVersion']+=1
    validate_state(record)


def agenda_context(guide,record,task,current=None):
    """Relevant v2 discourse context only; the caller owns permission."""
    state=record.get('natural',{})
    if 'agenda' not in state:return None
    agenda=copy.deepcopy(state['agenda'])
    topics=set(TASK_TOPICS.get(task,set()))
    if (current or {}).get('id') in {'T09','T10'}:topics|=set(PRIORITY_TOPICS)
    topics|={'T06':{'doctors'},'RC21':{'doctors'},'T07':{'drugs'},'RC22':{'drugs'},
        'RC23':{'drugs','total_cost'},'T08':{'travel'},'RC20':{'travel'}}.get((current or {}).get('id'),set())
    agenda['concerns']=[item for item in agenda['concerns'] if item['topic'] in topics]
    envelope=guide.get('fields',{}).get('needs.priorities',{})
    agenda['priorityReasons']=[item for item in agenda['priorityReasons'] if item['topic'] in topics
        and envelope.get('status')=='reported' and item['topic'] in envelope.get('value',[])
        and 'T10' not in record.get('conversation',{}).get('baselineDispositions',{})
        and item['priorityRevision']==envelope.get('revision')]
    return agenda


def record_advisor_move(record,move):
    agenda=ensure_agenda(record)
    value={'kind':move.get('kind','ask'),'topic':move.get('topic',''),
           'reason':move.get('reason','missing_dependency')}
    if agenda['lastMove']!=value:
        agenda['lastMove']=value
    validate_state(record)


def initial_state():
    return {'version': VERSION, 'provenance': {}, 'dialogue': {
        'orientation': '', 'lastTarget': None, 'explainedTopics': [],
        'deferredTargets': [], 'clarifications': []}}


def ensure_state(record):
    """Initialize only the additive local record; old envelopes stay untouched."""
    if 'natural' not in record:
        record['natural'] = initial_state()
    validate_state(record)
    return record['natural']


def _valid_target(target):
    return (isinstance(target, dict) and set(target) == {'id', 'entity', 'fields'}
            and isinstance(target['id'], str) and (bool(QUESTION.fullmatch(target['id'])) or target['id'] in SITUATION_TARGETS)
            and isinstance(target['entity'], str) and bool(ENTITY.fullmatch(target['entity']))
            and isinstance(target['fields'], list) and len(target['fields']) <= 12
            and all(isinstance(x, str) and x in (SITUATION_TARGETS.get(target['id']) or FIELD_NAMES[target['id'].split('.')[0]]) for x in target['fields'])
            and len(set(target['fields'])) == len(target['fields']))


def validate_state(record):
    """Reject text/value-bearing metadata and unknown schema keys, fail closed."""
    if 'natural' not in record:
        return None
    state = record['natural']
    if not isinstance(state, dict) or set(state) not in ({'version', 'provenance', 'dialogue'}, {'version', 'provenance', 'dialogue','agenda'}) or type(state['version']) is not int or state['version'] != VERSION:
        raise ValueError('Unsupported natural conversation metadata.')
    provenance = state['provenance']
    if not isinstance(provenance, dict) or len(provenance) > 1024:
        raise ValueError('Unsupported report provenance.')
    for ref, item in provenance.items():
        if not isinstance(ref, str) or not REF.fullmatch(ref) or not isinstance(item, dict) or set(item) != {'method', 'status', 'subject', 'scope', 'revision', 'supersedesRevision'}:
            raise ValueError('Unsupported report provenance.')
        if any(not isinstance(item[key], str) for key in ('method', 'status', 'subject', 'scope')) or item['method'] not in METHODS or item['status'] not in CONFIRMATIONS or item['subject'] not in SUBJECTS or item['scope'] not in SCOPES:
            raise ValueError('Unsupported report provenance meaning.')
        if type(item['revision']) is not int or item['revision'] < 0 or item['supersedesRevision'] is not None and (type(item['supersedesRevision']) is not int or not 0 <= item['supersedesRevision'] <= item['revision']):
            raise ValueError('Unsupported report provenance revision.')
        if (item['method'] == 'explicit_confirmation') != (item['status'] == 'explicitly_confirmed'):
            raise ValueError('Report status does not match its capture method.')
    dialogue = state['dialogue']
    if not isinstance(dialogue, dict) or set(dialogue) != {'orientation', 'lastTarget', 'explainedTopics', 'deferredTargets', 'clarifications'}:
        raise ValueError('Unsupported natural dialogue state.')
    if not isinstance(dialogue['orientation'], str) or dialogue['orientation'] not in {'', 'progress', 'familiarity', 'answered', 'deferred'} or dialogue['lastTarget'] is not None and not _valid_target(dialogue['lastTarget']):
        raise ValueError('Unsupported natural dialogue target.')
    if not isinstance(dialogue['explainedTopics'], list) or len(dialogue['explainedTopics']) > 50 or any(not isinstance(x, str) or not re.fullmatch(r'[a-z_]{1,40}', x) for x in dialogue['explainedTopics']):
        raise ValueError('Unsupported explained topic metadata.')
    for key in ('deferredTargets', 'clarifications'):
        if not isinstance(dialogue[key], list) or len(dialogue[key]) > 100 or any(not _valid_target(x) for x in dialogue[key]):
            raise ValueError('Unsupported natural clarification metadata.')
    if 'agenda' in state:_validate_agenda(state['agenda'])
    if len(json.dumps(state).encode()) > 196608:
        raise ValueError('Natural conversation metadata is too large.')
    return state


def _envelopes(guide, record):
    for name, envelope in guide.get('fields', {}).items():
        yield 'guide.' + name, envelope
    for question, envelope in record.get('facts', {}).items():
        yield 'readiness.' + question, envelope


def legacy_projection(guide, record):
    """Copy into strict inherited schemas; never mutate or upgrade old records.

    Callers must retain/restore the additive metadata around inherited validation
    and persist it through their local adapter.  Dropping it durably would erase
    the distinction between a direct report and an explicit confirmation.
    """
    validate_state(record)
    g, r = copy.deepcopy(guide), copy.deepcopy(record)
    state = r.pop('natural', None)
    provenance = (state or {}).get('provenance', {})
    for ref, envelope in _envelopes(g, r):
        confirmation = envelope.get('confirmation')
        if confirmation in CONFIRMATIONS.values():
            item = provenance.get(ref)
            if not item or item['revision'] != envelope.get('revision') or CONFIRMATIONS[item['status']] != confirmation:
                raise ValueError('A new report needs matching local provenance.')
            envelope['confirmation'] = 'confirmed_by_user'
        elif confirmation != 'confirmed_by_user':
            raise ValueError('Unsupported report confirmation.')
    return g, r


def restore_state(guide, record, natural):
    """Restore local confirmations after inherited validation/projection."""
    g, r = copy.deepcopy(guide), copy.deepcopy(record)
    if natural is None:
        return g, r
    r['natural'] = copy.deepcopy(natural)
    validate_state(r)
    for ref, envelope in _envelopes(g, r):
        item = natural['provenance'].get(ref)
        if item and item['revision'] == envelope.get('revision'):
            envelope['confirmation'] = CONFIRMATIONS[item['status']]
    return g, r


def prune_for_storage(guide, record):
    """Copy existing save omissions and prune dangling value-free provenance.

    This does not authorize saving or change preferences.  Keep provenance for
    every surviving local confirmation so a permitted saved report can resume
    through the strict-schema adapter.  No value is reconstructed from metadata.
    """
    validate_state(record)
    g, r = copy.deepcopy(guide), copy.deepcopy(record)
    sensitive = g.get('preferences', {}).get('saveSensitive') is True
    if not sensitive:
        for field in SENSITIVE_GUIDE_FIELDS:
            g.get('fields', {}).pop(field, None)
        if 'conversation' in r:
            r['conversation']['details'] = {}
        for identifier in r.get('facts', {}):
            if r.get('dispositions', {}).get(identifier, {}).get('state') == 'resolved_report':
                r['dispositions'][identifier] = {'state': 'not_saved', 'automaticReopen': False}
        r['facts'] = {}
        for check in r.get('completeness', {}).get('checks', {}).values():
            if check.get('state') in {'resolved_report', 'confirmed_reported'}:
                check['state'] = 'not_saved'
        r['history'] = [{k: v for k, v in entry.items() if k != 'previous'}
                        for entry in r.get('history', [])]
    for envelope in g.get('fields', {}).values():
        envelope.pop('rawText', None)
    if 'natural' in r:
        if not sensitive and 'agenda' in r['natural']:
            r['natural']['agenda']['priorityReasons']=[]
        sync_agenda(g,r)
        present = set()
        for ref, envelope in _envelopes(g, r):
            present.add(ref)
            if ref.startswith('readiness.'):
                for field, value in envelope.get('value', {}).items():
                    if field == 'items':
                        for entity in value:
                            present.update(ref + '.' + entity['entity'] + '.' + key
                                           for key in entity if key != 'entity')
                    elif field != 'entity':
                        present.add(ref + '.profile.' + field)
        r['natural']['provenance'] = {ref: item for ref, item in r['natural']['provenance'].items()
                                      if ref in present}
        validate_state(r)
    return g, r


def _fields(update):
    fields = update.get('fields', {})
    if isinstance(fields, dict):
        return dict(fields)
    if isinstance(fields, list) and all(isinstance(x, dict) and set(x) == {'key', 'value'} and isinstance(x['key'], str) for x in fields):
        if len({x['key'] for x in fields}) != len(fields):
            raise ValueError('A report repeats a field.')
        return {x['key']: x['value'] for x in fields}
    raise ValueError('Unsupported report fields.')


def classify_update(update, message, existing=None):
    """Classify one proposal's scope/conflict, leaving actual apply to the service.

    Exact spans and these guards do not prove arbitrary natural-language entailment.
    Call after the extractor's schema/semantic safeguards; unsupported choices and
    dates must still pass the existing domain validators before any commit.
    ``existing`` is an envelope, a value dict, or the target entity's dict.
    """
    def decision(kind, reason):
        return {'decision': kind, 'reason': reason, 'update': copy.deepcopy(update)}
    if not isinstance(update, dict) or not isinstance(message, str):
        return {'decision': 'reject', 'reason': 'invalid_proposal', 'update': None}
    identifier = update.get('id', '')
    if not isinstance(identifier, str) or not QUESTION.fullmatch(identifier):
        return decision('reject', 'unsupported_question')
    identifier = identifier.split('.')[0]
    try:
        fields = _fields(update)
    except ValueError:
        return decision('reject', 'invalid_fields')
    if not fields or set(fields) - FIELD_NAMES[identifier] or any(not isinstance(x, str) or len(x) > 1800 for x in fields.values()):
        return decision('reject', 'invalid_fields')
    quote = update.get('quote', '')
    if not isinstance(quote, str) or not quote.strip() or quote.casefold() not in message.casefold():
        return decision('reject', 'missing_supporting_span')
    if re.search(r'\b(?:if|suppose|hypothetically|for example)\b', quote, re.I):
        return decision('reject', 'hypothetical')
    if update.get('subject') == 'learner' and identifier not in {'T01', 'T02'}:
        return decision('reject', 'wrong_person')
    if not isinstance(update.get('subject'), str) or not isinstance(update.get('scope'), str) or update.get('subject') not in SUBJECTS or update.get('scope') not in SCOPES or type(update.get('uncertain')) is not bool or type(update.get('correction')) is not bool:
        return decision('reject', 'missing_scope')
    if update['subject'] == 'unclear' or update['scope'] == 'unknown':
        return decision('clarify', 'unclear_scope')
    explicit_unknown = all(x.casefold().strip() in UNRESOLVED for x in fields.values())
    open_preference = identifier=='T04' and fields.get('choice') in {'soonest','after_coverage'} and update['scope']=='intended'
    if update['uncertain'] or not explicit_unknown and not open_preference and re.search(r'\b(?:I think|maybe|might|probably|not sure|I guess)\b', quote, re.I):
        return decision('clarify', 'tentative')
    if identifier == 'T05' and update['scope'] != 'current':
        return decision('reject', 'not_current_insurance')
    if identifier in {'RC04', 'RC07', 'RC09'} and update['scope'] != 'current':
        return decision('reject', 'not_current_enrollment' if identifier == 'RC04' else 'not_current_coverage')
    if identifier in {'RC05', 'RC16'} and update['scope'] == 'intended':
        return decision('reject', 'not_actual_enrollment')
    if identifier == 'T04' and fields.get('choice') in {'soonest','after_coverage'}:
        if update['scope'] != 'intended' or set(fields) != {'choice'}:
            return decision('reject', 'not_desired_start_preference')
    entity = update.get('entity', 'profile')
    if not isinstance(entity, str) or entity not in {'new', ''} and not ENTITY.fullmatch(entity):
        return decision('reject', 'unsupported_entity')
    if identifier not in {'RC21', 'RC22', 'RC23'} and entity not in {'profile', ''}:
        return decision('reject', 'wrong_entity_kind')
    if identifier == 'RC21' and entity.startswith('medicine-') or identifier in {'RC22', 'RC23'} and entity.startswith('doctor-'):
        return decision('reject', 'wrong_entity_kind')
    old = existing.get('value', existing) if isinstance(existing, dict) else (existing if existing is not None else {})
    if not isinstance(old, dict):
        old = {'choice': old}
    if 'items' in old and identifier in {'RC21', 'RC22', 'RC23'}:
        items = old['items']
        if entity in {'profile', '', 'new'}:
            if update['correction'] and items or identifier == 'RC23' and len(items) != 1:
                return decision('clarify', 'ambiguous_entity')
            old = {}
        else:
            matched = next((item for item in items if item.get('entity') == entity), None)
            if update['correction'] and matched is None:
                return decision('clarify', 'missing_correction_target')
            old = matched or {}
    def equivalent(key, left, right):
        if key == 'choice' and identifier in {'T05', 'T08', 'T10'}:
            tokens = lambda x: {str(v).strip().casefold() for v in (x if isinstance(x, list) else str(x).split(','))}
            return tokens(left) == tokens(right)
        return left == right or isinstance(left, str) and isinstance(right, str) and left.strip().casefold() == right.strip().casefold()
    changed = any(k in old and not equivalent(k, old[k], v) and str(old[k]).casefold() not in UNRESOLVED
                  for k, v in fields.items() if k != 'choice' or identifier not in {'RC21', 'RC22', 'RC23'})
    # A validated desired month supplies precision to a previously open-ended
    # preference. It does not contradict a personal coverage fact or establish
    # actual enrollment. Other changed dates retain the normal conflict guard.
    start_refinement = (identifier == 'T04' and old.get('choice') in {'soonest','after_coverage'}
        and (fields.get('choice') in {'soonest','after_coverage'} and set(fields)=={'choice'}
             or fields.get('choice') == 'month' and set(fields) == {'choice', 'month'}
             and fields['month'].strip().casefold() not in UNRESOLVED)
        and update['subject'] == 'beneficiary' and update['scope'] == 'intended')
    date_refinement = (identifier == 'RC11' and changed and all(
        key not in old or equivalent(key,old[key],value) or key in {'jobEnd','coverageEnd'} and end_date_refinement(old[key],value)
        for key,value in fields.items()))
    # Named assistance programs may coexist. The retained RC18 scalar is the
    # latest report, while its programs set is additive for typed reports.
    # Receiving another positive program is not a retraction of the first one.
    # None/declined and tentative, wrong-person or unsupported proposals retain
    # their normal conflict/scope guards.
    positive_programs = {'medicaid', 'extra_help', 'part_b_help', 'ssi'}
    program_addition = (identifier == 'RC18' and set(fields) == {'choice'}
        and update['subject'] == 'beneficiary' and update['scope'] == 'current'
        and isinstance(old.get('choice'), str) and bool(old['choice'])
        and set(old['choice'].split(',')) <= positive_programs
        and bool(fields['choice']) and set(fields['choice'].split(',')) <= positive_programs)
    # The retained provider-list operation appends a named provider to an
    # existing positive list. Naming that doctor after saying "cardiologist"
    # does not retract the earlier list or require a correction confirmation.
    provider_addition = (identifier == 'T06' and old.get('choice') == 'list'
        and fields.get('choice', 'list') == 'list' and set(fields) <= {'choice', 'text'}
        and bool(fields.get('text')) and fields['text'].strip().casefold() not in UNRESOLVED
        and update['subject'] == 'beneficiary' and update['scope'] in {'current', 'intended'})
    # A medicine named after an existing list ("I also take lisinopril") adds to
    # it, exactly like a doctor (Nov 9, 2026: Plans-tab chat would not add a
    # second medicine). A correction still replaces; "no prescriptions" is a
    # choice change and still needs confirmation.
    medicine_addition = (identifier == 'T07' and old.get('choice') in {'yes', 'list'}
        and fields.get('choice', 'yes') in {'yes', 'list'} and set(fields) <= {'choice', 'text'}
        and bool(fields.get('text')) and fields['text'].strip().casefold() not in UNRESOLVED
        and update['subject'] == 'beneficiary' and update['scope'] in {'current', 'intended'})
    provider_addition = provider_addition or medicine_addition
    if changed and not start_refinement and not date_refinement and not program_addition and not provider_addition and not update['correction'] and not (isinstance(existing, dict) and (existing.get('stale') or existing.get('status') in {'unknown', 'skipped', 'stale'})):
        return decision('clarify', 'conflicting_report')
    if start_refinement:
        return decision('accept', 'explicit_start_refinement')
    if program_addition:
        return decision('accept', 'explicit_program_addition')
    return decision('accept', 'explicit_partial' if any(x.casefold().strip() in UNRESOLVED for x in fields.values()) else 'explicit_report')


_RETIREMENT_NEGATED_WORK = re.compile(r"\b(?:not|no longer|never|stopped|quit|done|haven['\u2019]?t been|isn['\u2019]?t|am not|i['\u2019]m not|ain['\u2019]?t)\b[^.;,]{0,24}\bworking\b|\bnot\s+working\b", re.I)
_RETIREMENT_NOT_RETIRED = re.compile(r"\b(?:not|never|haven['\u2019]?t|isn['\u2019]?t|am not|i['\u2019]m not)\s+(?:yet\s+)?retired\b", re.I)
_RETIREMENT_RETIRING = re.compile(r"\bretiring\b|\b(?:plan(?:ning)?|going|about|hoping|expect(?:ing)?|intend(?:ing)?|want(?:ing)?|hope)\s+to\s+retire\b|\bwill\s+(?:be\s+)?retir(?:e|ing)\b|\bretire\s+(?:in|next|this|on|by|at|around|soon|early|later)\b", re.I)


def retirement_clause_status(clause):
    """Name the retirement status one clause states, or None when it states none.

    This reads only the person's own words for consistency checks; it never
    supplies a status the clause does not state.
    """
    if not isinstance(clause, str):
        return None
    if _RETIREMENT_NOT_RETIRED.search(clause):
        return 'working'
    if _RETIREMENT_NEGATED_WORK.search(clause):
        return 'retired'
    if _RETIREMENT_RETIRING.search(clause):
        return 'retiring'
    if re.search(r'\bworking\b', clause, re.I):
        return 'working'
    if re.search(r'\bretired\b', clause, re.I):
        return 'retired'
    return None


def retirement_status_from_text(text, limit=160):
    """One consistent retirement status stated across a short message, else None."""
    if not isinstance(text, str) or not text.strip() or len(text) > limit or '?' in text:
        return None
    if re.search(r"\b(?:if|suppose|hypothetically|for example|I think|maybe|might|probably|not sure|I guess)\b", text, re.I):
        return None
    clauses = [x.strip() for x in re.split(r'(?<=[.!?;])\s+|\n|,|\b(?:and|but)\b', text, flags=re.I) if x.strip()]
    statuses = {retirement_clause_status(clause) for clause in clauses} - {None}
    return statuses.pop() if len(statuses) == 1 else None


def classify_situation(message, kind, value, existing=None):
    """Resolve one narrowly extracted life observation with clause-local scope.

    The recognizer supplies the supported value; this gate prevents that separate
    path from bypassing tentative/conflict rules.  It does not infer an observation
    from arbitrary prose or assert any coverage or eligibility consequence.
    """
    def result(decision, reason, resolved=None):
        return {'decision': decision, 'reason': reason,
                'value': copy.deepcopy(value if resolved is None else resolved)}
    if not isinstance(message, str) or not isinstance(kind, str) or kind not in {'retirement', 'age65'} or not isinstance(value, dict):
        return result('reject', 'unsupported_situation')
    if kind == 'retirement':
        valid = (set(value) == {'status', 'when'} and isinstance(value['status'], str)
                 and value['status'] in {'retired', 'retiring', 'working'}
                 and isinstance(value['when'], str) and len(value['when']) <= 80)
        relevant = re.compile(r'\bretir(?:ed|ing|ement)\b|\bworking\b', re.I)
    else:
        valid = (set(value) == {'month', 'year'} and type(value['month']) is int
                 and 1 <= value['month'] <= 12 and (value['year'] is None
                 or type(value['year']) is int and 1900 <= value['year'] <= 2099))
        relevant = re.compile(r'\b65\b|\bsixty.five\b|\bbirthday\b', re.I)
    if not valid:
        return result('reject', 'invalid_situation_value')
    # Keep punctuation on a clause so a question cannot become a statement. Split
    # coordinated observations to avoid one tentative field tainting another.
    clauses = [x.strip() for x in re.split(r'(?<=[.!?;])\s+|\n|,|\b(?:and|but)\b', message, flags=re.I) if x.strip()]
    selected = []
    epistemic_fragment = re.compile(r'^(?:I (?:think|guess|believe|thought)|maybe|probably|apparently|not sure|no|actually|correction)[.!?;]?$', re.I)
    for index, clause in enumerate(clauses):
        if relevant.search(clause):
            fragments = [clause]
            if index and epistemic_fragment.fullmatch(clauses[index - 1]):
                fragments.insert(0, clauses[index - 1])
            if index + 1 < len(clauses) and epistemic_fragment.fullmatch(clauses[index + 1]):
                fragments.append(clauses[index + 1])
            selected.append(' '.join(fragments))
    if not selected:
        return result('reject', 'missing_supporting_clause')
    if len(selected) > 1:
        # "Retired, and not working anywhere" states one status twice. Only
        # clauses that all agree with the proposed status merge; any mixed
        # or unreadable combination still asks for clarification.
        stated = {retirement_clause_status(fragment) for fragment in selected} if kind == 'retirement' else {None}
        if stated == {value['status']}:
            selected = [' '.join(selected)]
        else:
            return result('clarify', 'multiple_situation_clauses')
    clause = selected[0]
    if re.search(r'\b(?:if|suppose|hypothetically|for example)\b', clause, re.I):
        return result('reject', 'hypothetical')
    if '?' in clause:
        return result('clarify', 'question_not_report')
    if re.search(r"\b(?:I think|I (?:do not|don['’]t) think|I guess|I believe|I thought|maybe|may|might|could|probably|not sure|not certain|unsure|uncertain|apparently)\b", clause, re.I):
        return result('clarify', 'tentative')
    old = existing.get('value', existing) if isinstance(existing, dict) else None
    if not isinstance(old, dict) or isinstance(existing, dict) and existing.get('status') in {'unknown', 'skipped', 'stale'}:
        return result('accept', 'explicit_report')
    resolved = copy.deepcopy(value)
    if kind == 'age65' and value['year'] is None:
        resolved['year'] = old.get('year')
    if kind == 'retirement' and old.get('status') == value['status'] and not value['when']:
        resolved['when'] = old.get('when', '')
    changed = any(key in old and old[key] is not None and old[key] != val for key, val in resolved.items())
    correction = bool(re.search(r'\b(?:actually|correction|correct that|I meant|instead|rather|now|not retired)\b|^no\b', clause, re.I))
    if changed and not correction:
        return result('clarify', 'conflicting_report')
    return result('accept', 'explicit_correction' if changed else 'explicit_report', resolved)


def record_capture(guide, record, before_guide, before_record, update=None, method='direct_report'):
    """Mark changed committed envelopes and exact changed item/field references.

    Mutates only the supplied *new* guide/record.  No quote, value, timestamp,
    previous value or model prose enters this metadata.  The caller commits and
    invalidates dependencies transactionally; this function does neither.
    """
    if not isinstance(method, str) or method not in METHODS:
        raise ValueError('Unsupported capture method.')
    update = update or {}
    subject, scope = update.get('subject', 'beneficiary'), update.get('scope', 'current')
    if not isinstance(subject, str) or not isinstance(scope, str) or subject not in SUBJECTS or scope not in SCOPES or subject == 'unclear' or scope == 'unknown':
        raise ValueError('Resolve report scope before recording provenance.')
    state = ensure_state(record)
    status = 'explicitly_confirmed' if method == 'explicit_confirmation' else 'user_reported'
    old_envelopes = dict(_envelopes(before_guide, before_record))
    for ref, envelope in _envelopes(guide, record):
        previous = old_envelopes.get(ref)
        if previous == envelope or envelope.get('source') == 'location_reference' or envelope.get('status') == 'derived':
            continue
        # Invalidating an old fact does not constitute a fresh report.
        if previous and previous.get('revision') == envelope.get('revision'):
            continue
        item = {'method': method, 'status': status, 'subject': subject, 'scope': scope,
                'revision': envelope['revision'],
                'supersedesRevision': previous.get('revision') if previous else None}
        state['provenance'][ref] = copy.deepcopy(item)
        envelope['confirmation'] = CONFIRMATIONS[status]
        if ref.startswith('readiness.'):
            old_value = (previous or {}).get('value', {})
            new_value = envelope.get('value', {})
            for name, value in new_value.items():
                if name == 'items':
                    old_items = {x['entity']: x for x in old_value.get('items', [])}
                    for entity_value in value:
                        entity = entity_value['entity']
                        for field, field_value in entity_value.items():
                            if field != 'entity' and old_items.get(entity, {}).get(field) != field_value:
                                state['provenance'][ref + '.' + entity + '.' + field] = copy.deepcopy(item)
                elif name != 'entity' and old_value.get(name) != value:
                    state['provenance'][ref + '.profile.' + name] = copy.deepcopy(item)
    validate_state(record)
    return state


def set_target(record, question=None, *, orientation=None):
    state = ensure_state(record)
    if question is None:
        target = None
    else:
        fields = question.get('fields', [])
        target = {'id': question['id'], 'entity': question.get('entity', 'profile'),
                  'fields': [x.get('key') if isinstance(x, dict) else x for x in fields]}
        if not _valid_target(target):
            raise ValueError('Unsupported next target.')
    state['dialogue']['lastTarget'] = target
    if orientation is not None:
        state['dialogue']['orientation'] = orientation
    validate_state(record)
    return target


def _safe_value(value, depth=0):
    if depth > 4:
        return False
    if value is None or type(value) in {bool, int}:
        return True
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, str):
        return len(value) <= 1800 and not re.search(r'\b\d{3}-\d{2}-\d{4}\b|\b[1-9][A-Z][A-Z0-9][0-9][A-Z][A-Z0-9][0-9][A-Z]{2}[0-9]{2}\b|\b(?:ssn|social security (?:number|no)|medicare (?:number|id)|password|api[_ -]?key)\s*[:=]|\x00', value, re.I)
    if isinstance(value, list):
        return len(value) <= 40 and all(_safe_value(x, depth + 1) for x in value)
    if isinstance(value, dict):
        return len(value) <= 12 and all(isinstance(k, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,35}', k) and _safe_value(v, depth + 1) for k, v in value.items())
    return False


def build_context(guide, record, task='', active_question=None, consent_version=None, question_catalog=None):
    """Build bounded context from allowlisted resolved state, never raw history.

    Without the exact scoped permission, earlier sensitive values are replaced by
    presence markers.  Even with permission, relevance is task-specific.  This is
    context construction, not a consent receipt: the controller owns authorization.
    """
    validate_state(record)
    if not isinstance(task, str) or task not in TASKS:
        raise ValueError('Unsupported context task.')
    state = record.get('natural', initial_state())
    provenance = state['provenance']
    # v2 adds only visit-scoped dialogue at the controller boundary. Both
    # reviewed versions authorize these existing task-relevant profile values;
    # this function never attaches any raw conversation text.
    permitted = consent_version in PROFILE_CONTEXT_VERSIONS if isinstance(consent_version,str) else False
    allowed_fields = SAFE_FIELDS | (GUIDE_ALLOWLIST.get(task, set()) if permitted else set())
    allowed_readiness = READINESS_ALLOWLIST.get(task, set()) if permitted else set()
    result = {'reports': [], 'known': [], 'task': task, 'dialogue': copy.deepcopy(state['dialogue']),
              'revision': [guide.get('stateVersion', 0), record.get('stateVersion', 0)],
              'activeQuestion': None, 'cannotInfer': list(CANNOT_INFER)}
    if active_question is not None:
        fields = active_question.get('fields', [])
        target = {'id': active_question['id'], 'entity': active_question.get('entity', 'profile'),
                  'fields': [x.get('key') if isinstance(x, dict) else x for x in fields]}
        if not _valid_target(target):
            raise ValueError('Unsupported active context target.')
        result['activeQuestion'] = target
    def add(ref, value, status, revision, allowed, inherited_confirmation=None):
        if not REF.fullmatch(ref):
            return
        provenance_item = copy.deepcopy(provenance.get(ref, {}))
        if not provenance_item:
            # Preserve the prior record's original meaning; do not relabel it a
            # new automatic report or claim external verification.
            provenance_item = {'method': 'legacy_record', 'confirmation': inherited_confirmation,
                               'revision': revision}
        if status == 'reported' and isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {'unknown', 'not sure'}:
                status = 'unknown'
            elif normalized in {'deferred', 'check later', 'later'}:
                status = 'deferred'
        marker = {'id': ref, 'status': status}
        # Legacy unknown/skipped edits retain the prior value internally. Never
        # transmit that old value as though it were still a resolved report.
        if status in {'unknown', 'skipped', 'deferred'}:
            status = 'deferred' if status in {'skipped', 'deferred'} else 'unknown'
            marker['status'] = status
            if allowed:
                result['reports'].append({**marker, 'value': status, 'provenance': provenance_item})
            else:
                result['known'].append(marker)
        # Tentative/conflicting/stale reports never become usable model facts.
        elif allowed and status not in {'stale', 'tentative', 'conflicting'} and _safe_value(value):
            result['reports'].append({**marker, 'value': copy.deepcopy(value), 'provenance': provenance_item})
        else:
            result['known'].append(marker)
    for name, envelope in guide.get('fields', {}).items():
        status=envelope.get('status','reported')
        value=envelope.get('value')
        if (name=='coverage.current' and isinstance(value,list) and status in {'reported','derived'}
                and 'advantage' in value and set(value)&{'original','medigap'}):
            # Retain old saved values without treating an ambiguous present
            # route as a usable fact. This is a context hold, not a migration.
            status='conflicting'
        add('guide.' + name, value, status,
            envelope.get('revision', 0), name in allowed_fields, envelope.get('confirmation'))
    for identifier, envelope in record.get('facts', {}).items():
        if identifier not in FIELD_NAMES or not identifier.startswith('RC'):
            continue
        value = envelope.get('value', {})
        status = 'stale' if envelope.get('stale') else 'reported'
        allowed = identifier in allowed_readiness
        for field, item in value.items():
            if field == 'items':
                for entity in item:
                    entity_id = entity.get('entity', '')
                    if not isinstance(entity_id, str) or not ENTITY.fullmatch(entity_id):
                        continue
                    for entity_field, entity_value in entity.items():
                        if entity_field in FIELD_NAMES[identifier] and entity_field != 'entity':
                            meta = record.get('conversation', {})
                            item_key = identifier + '.' + entity_id
                            item_status = 'stale' if meta.get('itemInvalidations', {}).get(item_key, -1) > meta.get('itemRevisions', {}).get(item_key, envelope.get('revision', 0)) else status
                            add('readiness.' + identifier + '.' + entity_id + '.' + entity_field,
                                entity_value, item_status, envelope.get('revision', 0), allowed, envelope.get('confirmation'))
            elif field in FIELD_NAMES[identifier] or field == 'programs' and identifier == 'RC18':
                add('readiness.' + identifier + '.profile.' + field, item, status,
                    envelope.get('revision', 0), allowed, envelope.get('confirmation'))
    # Dispositions carry only IDs/status; they are never inferred negative facts.
    for identifier, disposition in record.get('dispositions', {}).items():
        if identifier in FIELD_NAMES:
            ref = 'readiness.' + identifier
            if not any(x['id'].startswith(ref + '.') for x in result['reports'] + result['known']):
                result['known'].append({'id': ref, 'status': disposition.get('state', 'unresolved')})
    if question_catalog is not None:
        # Only public contracts, never caller-supplied profile values or prose.
        result['questionCatalog'] = [{key: copy.deepcopy(item[key]) for key in
            ('id', 'purpose', 'dependency', 'requiredWhen', 'cannotInfer') if key in item}
            for item in question_catalog if isinstance(item, dict) and isinstance(item.get('id'), str) and QUESTION.fullmatch(item['id'])]
    return result
