"""Fictional visit starts for continuity and question timing diagnostics.

Setup records visitor-reported facts through native actions. Prior conversation
is represented as per-visit exchanges and supplies no source authority. Only
the fixture layer reads the pinned case hashes.
"""

from hashlib import sha256


# Hash each family's five source lines in variant order. Changes require review
# before a replacement row may reach the model under the same fixture.
FAMILY_HASHES = {
    'conversational_continuity-correction': '2dd51ae8427d62ef90e7f40977a3e38dfbd16a81ca215fac6680fc97cf1d73f2',
    'conversational_continuity-office': '1738e6edd4d4214c256ddc771e73e5755640c415938aeeeae323873b986b86e2',
    'conversational_continuity-parts': '29bbf95575c6471397619a7e83d6b87be45f61b0be264927a6ce95e595ea80d3',
    'conversational_continuity-silent': 'f53ad7bfd062eee636bf62b1dca5ea4165efcb3b6e0cf19eec81d8e05c46cb1f',
    'conversational_continuity-uncertain': 'ba0c06fe67a7fb057e425f866cad3fbebe2d4853b335e0df43afeceb10d3b81e',
    'conversational_continuity-yes': '79e2cb8b369ecc9edae4492eb78e248d14a05c2fe6e9c6c67afb1718e86b8cfa',
    'question_timing-format': 'c94a4883f8985909da161fd2f0003f00d81c9dc5229bfbac26d25cee5769efb1',
    'question_timing-handoff_consent': 'e7e4b95c819c6e5c90b23e07210857450ead634c6ba6a5e3abba1e8dff8371e7',
    'question_timing-medigap': 'adf228d2a039b09fbc409d5a5f4e0544954f61b8147d27b0635223d0d87f21a1',
    'question_timing-relative': '8176010c89a67f0daa6e01726699a27d92232dde8815926e94953528b98e7fe6',
    'question_timing-time': 'b1fc6e0c891c56449e4e39c895d08be8a51b149512a05d4fca746ecf12c1e9e5',
    'question_timing-year': 'c0d164517b88e3d4d8aef2fccdf3bf5c4af809bd1839326c7b2b2a090ad8ee09',
}

# The Aetna booklet has a known year. The Humana printout is a visitor
# report with an unknown year, so it must not become a catalog selection.
AETNA_BOOKLET = '2026:H5521:033:000'
HUMANA_PRINTOUT = 'HumanaChoice Florida H5216-072 (PPO)'


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


def _fixture(family, journey):
    """Return setup and verified facts independently of the calibration examples."""
    relation = ('someone' if journey == 'caregiver' else 'self')
    if family == 'question_timing-relative':
        relation = None
    setup = [] if relation is None else [_choice('RC01', choice=relation)]
    history = []
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
    elif family == 'conversational_continuity-parts':
        setup.extend([_task('timing'), _choice('RC04', choice='a_only')])
        reports['RC04'] = {'choice': 'a_only'}
        start['postReports'] = dict(reports)
        history.append(("The card only shows Part A. I'm retired and I no longer have insurance through work.",
                        'I have Part A only and no current job coverage.', ''))
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
        history.append(("The company behind my health insurance has 35 employees. I'm trying to figure out how this insurance affects when I sign up for Medicare.",
                        '', ''))
    elif family == 'question_timing-year':
        setup.extend([_choice('T01', choice='compare'), _choice('T03', zip='34103')])
        fields['comparison.scope.zip'] = '34103'
        start['datedBooklet'] = AETNA_BOOKLET
        history.append((f'I have the 2026 Aetna Medicare Signature (PPO) H5521-033 summary and '
                        f'a printout for {HUMANA_PRINTOUT} without the year showing.',
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
        for key in keys:
            case, line_hash = rows[key]
            if case['split'] != 'heldout':
                raise ValueError('Conversation diagnostic binding requires a held-out row.')
            starts[key] = {**_fixture(family, case['journey']), 'lineHash': line_hash}
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


def prepare_trial(service, owner, state, start):
    """Bind the dated comparison reference through normal Plans permission."""
    if not start.get('datedBooklet'):
        return {}
    from starts_facts import prepare_trial as bind_plan

    return bind_plan(service, owner, state, {'selected_plan': start['datedBooklet']})


def verify_observation(trace, start):
    """Require the exact dated browsing entry at composition for year cases."""
    if not start.get('datedBooklet'):
        return True
    from starts_facts import verify_observation as verify_plan

    return verify_plan(trace, {'selected_plan': start['datedBooklet'], 'requires_source_lookup': False})


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
