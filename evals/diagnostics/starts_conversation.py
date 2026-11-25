"""Fictional visit starts for continuity and question timing diagnostics.

Setup records visitor-reported facts through native actions. Prior conversation
is represented as per-visit exchanges and supplies no source authority. Only
the fixture layer reads the pinned case hashes.
"""

from hashlib import sha256


# Hash each family's five source lines in variant order. Changes require review
# before a replacement row may reach the model under the same fixture.
FAMILY_HASHES = {
    'conversational_continuity-correction': '79d4e145eb3c439fb765df3889ea9b662f2841a351ceba2126cc09a3e2b46215',
    'conversational_continuity-office': '62bbceed5a8bd208e0b563d67215cf8452282627cc5fc07caddc3b2edabf3c32',
    'conversational_continuity-silent': 'bcf7005453f39fd6ac9937843070780d0ecadc3bc1baac9d721fcfaf40678da7',
    'conversational_continuity-uncertain': 'e0aa284831cd922d2fed67cc63bc34e66cf4a435b899311427e0511433a62ab9',
    'conversational_continuity-yes': '5ecad166f78a2dfa9bfc6776c5f3bb05768c9e45b07600c6a89281239961ad54',
    'question_timing-medigap': '2d948eb6dca9e191fc50f298a0fde7c538c0392bc25ec476adf55657ce9c8b8e',
    'question_timing-time': 'cdc2cb77dc9fb3ab4fc80393ad767c587d331a8e6773ec67e7c90cfcbd0d1592',
    'question_timing-handoff_consent': '05368ae5998b5ef8913d8b8107d220246a4fae7d9b809f6baf7c512ab2ec5ad4',
    'question_timing-format': '0177c9e5f882477fe48d91738f1b2f46093a352dfb5aaf1f008c692975aebfb9',
    'question_timing-relative': '1f71647827b3275d2bd9c0ff027c8c9ae4a56c48a1b438f53d546b29847c3f33',
}

# Context from the browser tab in variant 3 has not been shared with Daylight.
# The other prior preferences are deliberately worded as fictional visitor text.
PREFERENCES = {
    2: ('Please use plain language.', '', ''),
    4: ('I want to make the decision myself.', '', ''),
    5: ('Please take this one step at a time.', '', ''),
}


def _choice(identifier, *, entity=None, source=None, **fields):
    """Create a native structured answer with optional list item and provenance."""
    action = {'type': 'choice', 'id': identifier, 'fields': fields}
    if entity:
        action['entity'] = entity
    if source:
        action['source'] = source
    return action


def _task(task):
    """Create the native request to prepare for the named task."""
    return {'type': 'task', 'task': task, 'preparing': True}


def _fixture(family, journey, variant):
    """Return setup and verified facts independently of the calibration examples."""
    relation = ('someone' if journey == 'caregiver' else 'self')
    if family == 'question_timing-relative':
        relation = None
    setup = [] if relation is None else [_choice('RC01', choice=relation)]
    history = [PREFERENCES[variant]] if variant in PREFERENCES else []
    if relation == 'someone':
        history.insert(0, ('I am helping my dad with his Medicare visit. He is here with me.', '', ''))
    start = {'setup': setup, 'history': history, 'relationship': relation,
             'fields': {}, 'reports': {}}
    fields, reports = start['fields'], start['reports']

    if family == 'conversational_continuity-correction':
        setup.extend([_choice('T01', choice='compare'), _choice('T03', zip='34102'),
                      _choice('T03', zip='34103')])
        fields['comparison.scope.zip'] = '34103'
        start['postFields'] = {'comparison.scope.zip': '34103'}
        history.extend([('My home ZIP is 34102.', '', ''),
                        ('I need to correct that. My home ZIP is 34103.', 'I have 34103 now.', '')])
    elif family == 'conversational_continuity-office':
        setup.extend([_choice('T06', text='Dr. Finch'),
                      _choice('RC21', entity='doctor-1', practice='Downtown Clinic', city='Naples')])
        reports['RC21'] = {'choice': 'details', 'items': [
            {'entity': 'doctor-1', 'practice': 'Downtown Clinic', 'city': 'Naples', 'choice': 'details'}]}
        office = 'My dad goes to Downtown Clinic in Naples.' if relation == 'someone' else 'I go to Downtown Clinic in Naples.'
        history.append((office + ' Please use that office, not the Northside office.',
                        'I have the Downtown Clinic location.', ''))
    elif family == 'conversational_continuity-silent':
        setup.extend([_choice('T06', text='Dr. Finch'),
                      _choice('T06', text='Dr. Quinn; Dr. Lane', source='plans_filter')])
        start['plansAdditions'] = {'medicines': [], 'doctors': ['Dr. Quinn', 'Dr. Lane'],
                                  'removed': [], 'other': [], 'none': []}
        fields['needs.providers'] = 'Dr. Finch; Dr. Quinn; Dr. Lane'
        start['postFields'] = {'needs.providers': fields['needs.providers']}
    elif family == 'conversational_continuity-uncertain':
        setup.append(_choice('T01', choice='compare'))
        reports['RC23'] = None
        fields['needs.pharmacies'] = None
        who = 'My dad might use Pine Pharmacy' if relation == 'someone' else 'I might use Pine Pharmacy'
        history.append((who + ', but please leave that unconfirmed.', 'I will leave that open.', ''))
    elif family == 'conversational_continuity-yes':
        setup.extend([_choice('T07', text='Metformin'), _task('drug_pricing')])
        reports['RC23'] = None
        message = 'I think Brook Pharmacy is the pharmacy I want to use.'
        history.append((message, '', 'Should I use Brook Pharmacy?'))
        start['pending'] = {'id': 'RC23', 'entity': 'medicine-1', 'fields': {'pharmacy': 'Brook Pharmacy'},
                            'quote': message, 'subject': 'beneficiary', 'scope': 'current',
                            'uncertain': True, 'correction': False}
    elif family == 'question_timing-medigap':
        setup.extend([_choice('T03', zip='34101'),
                      _choice('MG_AGE', choice='68', source='plans_filter'),
                      _choice('MG_SEX', choice='Female', source='plans_filter'), _task('medigap')])
        fields.update({'comparison.scope.zip': '34101', 'medigap.ageOn20261110': 68,
                       'medigap.pricingSex': 'Female', 'medigap.tobaccoCategory': None})
        start['question'] = 'MG_TOBACCO'
        history.append(('Can you show me a Medigap price for my situation?', '', ''))
    elif family == 'question_timing-time':
        setup.extend([_task('timing'), _choice('RC10', choice='yes')])
        reports.update({'RC09': None, 'RC10': {'choice': 'yes'}})
        history.append(('My health coverage is through an employer with 35 people. I want to understand how it works with Medicare.',
                        '', ''))
    elif family == 'question_timing-handoff_consent':
        history.append(('I may want a person to go over this with me.', '', ''))
    elif family == 'question_timing-format':
        start['reviewedConcept'] = 'costs'
        history.append(('What does “premium” mean on this cost page?',
                        'The premium is a recurring charge for keeping a policy active.', ''))
    elif family == 'question_timing-relative':
        setup.append(_choice('T01', choice='compare'))
        start['question'] = 'RC01'
        fields['comparison.scope.zip'] = None
    else:
        raise ValueError('No executable setup was defined for the diagnostic family.')
    return start


def build_starts(rows):
    """Return available starts based on complete independently pinned families."""
    starts = {}
    for family, family_hash in FAMILY_HASHES.items():
        keys = [f'{family}-{variant}' for variant in range(1, 6)]
        if any(key not in rows for key in keys):
            continue
        hashes = [rows[key][1] for key in keys]
        if sha256(''.join(hashes).encode('ascii')).hexdigest() != family_hash:
            continue
        for variant, key in enumerate(keys, 1):
            case, line_hash = rows[key]
            if case['split'] != 'heldout':
                raise ValueError('Conversation diagnostic binding requires a held-out row.')
            starts[key] = {**_fixture(family, case['journey'], variant), 'lineHash': line_hash}
    return starts


def prepare_state(flow, owner, state, start):
    """Apply standalone validated setup operations and rebind before a live turn."""
    from run_live import turn
    from identifier_guard import find_identifiers
    from natural_state import classify_update

    if concept := start.get('reviewedConcept'):
        fact = flow.facts.get(concept, {})
        if 'A premium is the amount you pay each month for coverage.' not in fact.get('text', ''):
            raise ValueError('The advisor did not expose the reviewed premium definition.')
    if pending := start.get('pending'):
        message = pending['quote']
        if find_identifiers(message) or classify_update(pending, message)['decision'] != 'clarify':
            raise ValueError('The fictional pharmacy report did not validate as tentative.')
        flow.queue_pending(owner, [pending], state['guide'], state['record'])
        _, state = turn(flow, owner, state, {'type': 'refresh'})
        confirmation = flow.pending_confirmation(owner, 'Yes.', [])
        if not confirmation or any(confirmation[key] != pending[key] for key in ('id', 'entity', 'fields')):
            raise ValueError('The advisor did not expose the exact pending pharmacy confirmation.')
        first = flow.eligible(owner, state['guide'], state['record'])[0]['question']
        if (first['id'], first.get('entity')) != (pending['id'], pending['entity']):
            raise ValueError('The pending pharmacy question is not the next eligible target.')
    if 'plansAdditions' in start:
        chain = state['continuation'].split('.')[0]
        if flow.plans_additions.get((owner, chain)) != start['plansAdditions']:
            raise ValueError('The first Plans acknowledgement is not queued for this visit.')
    return state


def observe_state(flow, owner, out, start):
    """Record native post-turn state so behavior failures remain observable."""
    if pending := start.get('pending'):
        value = out['record']['facts'].get('RC23', {}).get('value', {})
        item = next((item for item in value.get('items', []) if item['entity'] == pending['entity']), {})
        remaining = flow.pending_for(owner)
        targets = [remaining['update'], *remaining.get('remaining', [])] if remaining else []
        pharmacy_pending = any(
            target.get('id') == pending['id'] and target.get('entity') == pending['entity']
            and target.get('fields', {}).get('pharmacy') == pending['fields']['pharmacy']
            for target in targets
        )
        return {
            'pharmacy': {'expected': pending['fields']['pharmacy'], 'actual': item.get('pharmacy')},
            'pendingRemains': {'expected': False, 'actual': pharmacy_pending},
        }
    if 'plansAdditions' in start:
        chain = out['continuation'].split('.')[0]
        return {'plansAcknowledgementQueued': {
            'expected': False, 'actual': (owner, chain) in flow.plans_additions,
        }}
    return {}
