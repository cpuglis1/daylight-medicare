"""D146 adapter from the trusted conversation head to the offline estimator."""

from collections import OrderedDict
from copy import deepcopy
from datetime import date
import re
from secrets import token_urlsafe
from time import time

from comparison_profile import build_comparison_profile
from guest_profiles import ProfileError
from natural_flow import list_items
from part_d_profile import profile as published_profile

OFFERING = re.compile(r'2026:[HRS]\d{4}:\d{3}:\d{3}\Z')
CONTINUATION = re.compile(r'[a-f0-9]{32}\.[a-f0-9]{64}\Z')
MAX_VISITS = 128
UNKNOWN = 'unknown'


def checked(condition, message='Use the current prescription question.', status=422):
    if not condition:
        raise ProfileError(message, status)


def current_head(flow, owner, continuation):
    """Only the journal's current, authenticated, unexpired snapshot is usable."""
    chain = flow.current_chain.get(owner)
    if (owner in flow.natural_active or flow.revoked_owners.get(owner, 0) > time()
            or not chain or flow.state_heads.get((owner, chain)) != continuation):
        raise ProfileError('Your conversation changed. Reopen the prescription check from the latest visit.', 409)
    for (entry_owner, _), entry in reversed(flow.turn_journal.items()):
        if entry_owner == owner and entry['expires'] > time() and entry['response']['continuation'] == continuation:
            return entry
    raise ProfileError('This visit expired. Reopen the prescription check from your conversation.', 409)


def reported_fields(guide, record):
    """Reuse D79 subject, scope and confirmed RC22/23/18 reports."""
    scope = published_profile(guide, record)
    fields = guide['fields']
    subject = fields.get('subject.role', {})
    medications = fields.get('needs.medications', {})
    normalized = build_comparison_profile(guide, record)
    values, references, conflicting = {}, {}, False
    for fact in normalized['facts']:
        identifier = fact.get('question_id')
        if identifier not in {'RC22', 'RC23', 'RC18'}:
            continue
        ref = fact['ref']
        if fact['report_state'] == 'conflicting':
            conflicting = True
        if not fact['usable_for_bound_subject'] or fact['temporal_scope'] != 'current':
            continue
        key = (identifier, ref['item_id'])
        field = ref['path'].rsplit('.', 1)[-1]
        values.setdefault(key, {})[field] = fact['value']
        references.setdefault(key, {})[field] = ref['report_revision']
    names = list_items(scope['medicines'])
    exact = {key[1]: value for key, value in values.items() if key[0] == 'RC22' and key[1] and value.get('name')}
    items = {}
    if scope['medicine_status'] != 'no' and (names or exact):
        # The shared flow assigns medicine-1, medicine-2, ... to the original
        # T07 list. Extra RC22 rows retain their own stable entity ID.
        items = {f'medicine-{index}': {'name': name} for index, name in enumerate(names, 1)}
        for key, value in exact.items():
            items[key] = {**items.get(key, {}), **value}
    meds = {}
    for item, identity in items.items():
        fill = values.get(('RC23', item), {})
        quantity = str(fill.get('quantity', '')).strip()
        amount = re.fullmatch(r'([1-9][0-9]{0,3})(?:\s+(tablets?|capsules?|mL))?', quantity, re.I)
        supply = re.fullmatch(r'(30|90)(?:[ -]days?)?', str(fill.get('daysSupply', '')).strip(), re.I)
        inputs = {}
        if amount:
            inputs['quantity'] = int(amount[1])
            if amount[2]:
                inputs['unit'] = 'mL' if amount[2].lower() == 'ml' else amount[2].lower().rstrip('s')
        if supply:
            inputs['days_supply'] = int(supply[1])
        meds[item] = {'identity': identity, 'inputs': inputs,
                      'unsupported_fill': bool((quantity and not amount)
                          or (fill.get('daysSupply') and not supply)),
                      'stamp': [identity, references.get(('RC22', item))],
                      'fill_stamp': [fill.get('quantity'), fill.get('daysSupply')],
                      'pharmacy': fill.get('pharmacy'),
                      'channel': fill.get('channel') or ('mail' if fill.get('choice') == 'mail' else None)}
    help_report = values.get(('RC18', None), {})
    programs = help_report.get('programs[]') or help_report.get('choice')
    assistance = ('none' if programs == 'none' or programs == ['none']
                  else UNKNOWN if programs in ('declined', 'unknown', 'deferred')
                  else 'reported_help' if programs else None)
    help_stamp = [record['facts'].get('RC18'), record.get('dispositions', {}).get('RC18')]
    visit_stamp = [subject, scope['inputs'], scope['year_defaulted']]
    outlet_stamp = [(key, value['pharmacy'], value['channel'])
                    for key, value in meds.items() if value['pharmacy'] or value['channel']]
    return scope, meds, assistance, [visit_stamp, outlet_stamp, help_stamp, conflicting,
                                     medications.get('revision')]


class PrescriptionVisit:
    """Fills and exact choices are scoped to one active guest visit, in RAM."""

    def __init__(self, flow, service):
        self.flow = flow
        self.service = service
        self.visits = OrderedDict()
        self.revision = 0

    def sync(self, owner, entry, plan):
        guide, record = entry['response']['guide'], entry['response']['record']
        scope, meds, assistance, stamps = reported_fields(guide, record)
        visit_stamp, outlet_stamp, help_stamp, conflicting, list_revision = stamps
        head = entry['response']['continuation']
        chain = head.split('.')[0]
        for key in list(self.visits):
            cached = self.visits[key]
            if (cached['expires'] <= time() or key in self.flow.revoked_owners
                    or self.flow.current_chain.get(key) != cached['chain']):
                self.visits.pop(key)
        prior = self.visits.get(owner)
        if prior is None or prior['chain'] != chain or prior['subject'] != visit_stamp[0]:
            prior = {'chain': chain, 'subject': visit_stamp[0], 'scope': None, 'outlet_stamp': None,
                     'help_stamp': None, 'list_revision': None, 'head': None, 'plan': None,
                     'meds': {}, 'details': {}, 'revision': 0}
        if (head, plan) != (prior['head'], prior['plan']):
            self.revision += 1
            prior['revision'] = self.revision
            prior.pop('receipt', None)
        if prior['scope'] != visit_stamp:
            prior['details'].pop('period', None)
            prior['details'].pop('prior_spending', None)
        if prior['outlet_stamp'] != outlet_stamp or prior['scope'] != visit_stamp:
            for key in ('outlet_zip', 'pharmacy', 'pharmacy_label', 'channel'):
                prior['details'].pop(key, None)
        if prior['help_stamp'] != help_stamp:
            prior['details'].pop('assistance', None)
        # A different T07 list revision can remove and reintroduce an item
        # between reads. Require its exact selection again.
        if prior['list_revision'] != list_revision:
            prior['meds'].clear()
        prior['meds'] = {key: data for key, data in prior['meds'].items()
                         if key in meds and data['stamp'] == meds[key]['stamp']}
        for key, data in prior['meds'].items():
            if data['fill_stamp'] != meds[key]['fill_stamp']:
                data['fill_stamp'] = meds[key]['fill_stamp']
                data['answers'] = {field: value for field, value in data['answers'].items()
                                   if field == 'rxcui'}
        prior.update(head=head, plan=plan, scope=visit_stamp, outlet_stamp=outlet_stamp,
                     help_stamp=help_stamp, list_revision=list_revision, expires=entry['expires'])
        self.visits[owner] = prior
        self.visits.move_to_end(owner)
        if len(self.visits) > MAX_VISITS:
            self.visits.popitem(last=False)
        if scope['status'] != 'ready':
            issue = 'scope_unsupported' if scope['status'] == 'unsupported' else 'scope_missing'
        elif self.flow.pending_for(owner) or conflicting:
            issue = 'profile_needs_confirmation'
        elif not meds:
            issue = 'no_reported_medicines'
        elif len(meds) > 12:
            issue = 'list_size_unsupported'
        elif any(m['unsupported_fill'] for m in meds.values()):
            issue = 'reported_fill_unsupported'
        elif (len({m['pharmacy'].casefold() for m in meds.values() if m['pharmacy']}) > 1
              or len({m['channel'] for m in meds.values() if m['channel']}) > 1):
            issue = 'multiple_outlets_unsupported'
        else:
            issue = None
        return prior, meds, assistance, issue

    def report(self, state, meds, assistance):
        details = state['details']
        outlet_zip = details.get('outlet_zip')
        if not outlet_zip:
            reported_zips = {match.group(1) for m in meds.values() if m['pharmacy']
                             and (match := re.search(r'\b(?:FL|Florida)\s+(\d{5})(?:-\d{4})?\s*$',
                                                    m['pharmacy'], re.I))}
            outlet_zip = next(iter(reported_zips)) if len(reported_zips) == 1 else None
        channel = next((m['channel'] for m in meds.values() if m['channel']), None)
        outlet = details.get('pharmacy')
        return {
            'offering_id': state['plan'], 'period': details.get('period'),
            'assistance': assistance or details.get('assistance'),
            'prior_spending': details.get('prior_spending'),
            'outlet_zip': outlet_zip,
            'pharmacy': {**outlet, 'channel': channel or details.get('channel')} if outlet else None,
            'medicines': [{**m['inputs'], **state['meds'].get(item, {}).get('answers', {})}
                          for item, m in meds.items()],
        }

    def question(self, meds, report):
        """The ordered missing-only flow. Source lookups are read-only."""
        for item, med in zip(meds, report['medicines'], strict=True):
            label = meds[item]['identity']['name']
            for field in ('rxcui', 'quantity', 'unit', 'days_supply', 'fills'):
                if not med.get(field):
                    return {'field': field, 'item': item, 'label': label}
        if not report['outlet_zip']:
            return {'field': 'outlet_zip'}
        if not report['pharmacy']:
            return {'field': 'pharmacy', 'zip': report['outlet_zip'],
                    'reported': next((m['pharmacy'] for m in meds.values() if m['pharmacy']), None)}
        if not report['pharmacy'].get('channel'):
            return {'field': 'channel'}
        for field in ('period', 'assistance', 'prior_spending'):
            if not report[field]:
                return {'field': field}
        return None

    def choices(self, state, meds, question):
        if question['field'] == 'rxcui':
            identity = meds[question['item']]['identity']
            name = identity['name'].strip()
            strength = identity.get('strength', '').strip()
            query = name if not strength or strength.casefold() in name.casefold() else f'{name} {strength}'
            candidates = self.service.products([], name=query)
            form = identity.get('form', '').casefold().split()
            return [{'value': row['rxcui'], 'label': row['name']} for row in candidates
                    if row['type'] in ('SCD', 'SBD') and row['route'] and row['strength_description']
                    and all(word in row['form'].casefold() for word in form)]
        if question['field'] == 'pharmacy':
            return [{'value': outlet['address_id'] + ':' + outlet['npi'],
                     'label': ', '.join(filter(None, [
                         next(iter(outlet['aliases']), outlet['name']) or f"NPI {outlet['npi']}",
                         *outlet['address'].values()])),
                     'outlet': {key: outlet[key] for key in ('address_id', 'npi', 'zip')}}
                    for outlet in self.service.outlets([], zip=question['zip'])]
        return []

    def answer(self, state, meds, question, value):
        field = question['field']
        details = state['details']
        if field in ('rxcui', 'pharmacy'):
            matches = [row for row in self.choices(state, meds, question) if row['value'] == value]
            checked(len(matches) == 1, 'Choose one exact result from the list.')
            if field == 'pharmacy':
                details[field] = matches[0]['outlet']
                details['pharmacy_label'] = matches[0]['label']
                return
        elif field in ('quantity', 'days_supply'):
            checked(type(value) is int and (1 <= value <= 10000 if field == 'quantity' else value in (30, 90)),
                    'Enter a whole fill quantity or choose a supported days supply.')
        elif field == 'fills':
            checked(isinstance(value, list) and 1 <= len(value) <= 13 and all(
                isinstance(row, dict) and set(row) == {'date', 'order'}
                and isinstance(row['date'], str) and re.fullmatch(r'2026-\d\d-\d\d', row['date'])
                and type(row['order']) is int and 1 <= row['order'] <= 12 for row in value),
                'Enter each planned 2026 fill date and its order for that day.')
            for row in value:
                date.fromisoformat(row['date'])
        elif field == 'period':
            checked(isinstance(value, str) and re.fullmatch(r'2026-\d\d-01', value),
                    'Use the first day of a month in 2026.')
            start = date.fromisoformat(value)
            value = {'start': value, 'confirmed': True,
                     'kind': 'full_year' if start.month == 1 else 'remaining_year'}
        elif field == 'outlet_zip':
            checked(isinstance(value, str) and re.fullmatch(r'[0-9]{5}', value), 'Enter the pharmacy’s five-digit ZIP.')
        else:
            allowed = {'unit': ('tablet', 'capsule', 'mL', 'other'),
                       'channel': ('retail', 'mail'), 'assistance': ('none', 'reported_help', UNKNOWN),
                       'prior_spending': ('confirmed_zero', 'nonzero', UNKNOWN)}
            checked(value in allowed[field], 'Choose a listed answer.')
        if 'item' in question:
            item = question['item']
            entry = state['meds'].setdefault(item, {'stamp': meds[item]['stamp'],
                                                   'fill_stamp': meds[item]['fill_stamp'], 'answers': {}})
            entry['answers'][field] = value
            if field == 'rxcui':
                entry['label'] = matches[0]['label']
        else:
            details[field] = value

    def dispatch(self, owner, body):
        from daylight_data.serving.binding import ResearchServingError
        from daylight_data.serving.part_d_math import EstimateHold

        action = body.get('action')
        head, plan = body.get('continuation'), body.get('offering_id')
        expected = {'read': set(), 'answer': {'revision', 'value'}, 'edit': {'revision', 'field', 'item'},
                    'estimate': {'revision'}, 'validate': {'revision', 'receipt'}}
        checked(isinstance(action, str) and action in expected and set(body) == expected[action] |
                {'action', 'continuation', 'offering_id'}, 'Use the current prescription check.')
        checked(isinstance(head, str) and CONTINUATION.fullmatch(head) and isinstance(plan, str)
                and OFFERING.fullmatch(plan), 'Open a 2026 plan from the current conversation.')
        with self.flow.lock:
            entry = current_head(self.flow, owner, head)
            live, meds, assistance, issue = self.sync(owner, entry, plan)
            revision = live['revision']
            checked(action == 'read' or type(body['revision']) is int and body['revision'] == revision,
                    'These prescription details changed. Review them again.', 409)
            if action == 'estimate':
                live.pop('receipt', None)
            state = deepcopy(live)
        if issue:
            return {'state': 'held', 'hold': issue, 'revision': revision, 'participant_release': False}

        report = self.report(state, meds, assistance)
        question = self.question(meds, report)
        status = {'state': 'ready', 'revision': revision}
        result_receipt = None
        changed = action in ('answer', 'edit')
        try:
            self.service._scope()
            if action == 'validate':
                receipt = state.get('receipt')
                valid = (receipt and body['receipt'] == receipt['id']
                         and self.service.check_receipt(report, revision, receipt['engine']))
                status = {'state': 'current' if valid else 'held', 'hold': None if valid else 'result_changed'}
            elif action == 'estimate':
                checked(question is None, 'Finish the missing prescription details first.', 409)
                outcome = self.service.estimate(report, revision)
                status = {key: value for key, value in outcome.items() if key in {
                    'state', 'hold', 'period_kind', 'start', 'end', 'plan_premium_cents',
                    'drug_spending_cents', 'plan_premium_plus_drugs_cents'}}
                if outcome['state'] == 'offline_average_candidate':
                    result_receipt = {'id': token_urlsafe(24), 'engine': outcome['receipt']}
                    status.update(receipt=result_receipt['id'], expires_at=
                        self.service.foundation.manifest['policy']['technical_read_until_utc'])
            else:
                if action == 'answer':
                    checked(question is not None, 'Review the completed details before making changes.', 409)
                    self.answer(state, meds, question, body['value'])
                elif action == 'edit':
                    field, item = body['field'], body['item']
                    checked(isinstance(field, str) and (item is None or isinstance(item, str)),
                            'Choose a reported detail to edit.')
                    if item is None:
                        checked(field in {'outlet_zip', 'pharmacy', 'channel', 'period', 'assistance', 'prior_spending'})
                        state['details'].pop(field, None)
                        if field == 'outlet_zip':
                            state['details'].pop('pharmacy', None)
                        if field in ('outlet_zip', 'pharmacy'):
                            state['details'].pop('pharmacy_label', None)
                    else:
                        checked(item in state['meds'] and field in state['meds'][item]['answers'])
                        answers = state['meds'][item]['answers']
                        if field == 'rxcui':
                            answers.clear()
                        else:
                            answers.pop(field)
                report = self.report(state, meds, assistance)
                question = self.question(meds, report)
                if question:
                    status.update(state='missing', question={**question, 'choices': [
                        {key: row[key] for key in ('value', 'label')}
                        for row in self.choices(state, meds, question)]})
                status['editable'] = [
                    {'item': item, 'field': field, 'medicine': meds[item]['identity']['name']}
                    for item, detail in state['meds'].items() for field in detail['answers']]
                status['editable'].extend({'item': None, 'field': field} for field in state['details']
                                          if field != 'pharmacy_label')
                if question is None:
                    status['summary'] = {
                        'period': report['period']['start'],
                        'pharmacy': state['details']['pharmacy_label'],
                        'channel': report['pharmacy']['channel'],
                        'assistance': report['assistance'],
                        'prior_spending': report['prior_spending'],
                        'medicines': [
                            {'name': state['meds'][item]['label'], 'quantity': med['quantity'],
                             'unit': med['unit'], 'days_supply': med['days_supply'],
                             'fill_count': len(med['fills'])}
                            for item, med in zip(meds, report['medicines'], strict=True)],
                    }
            self.service._scope()
        except (ResearchServingError, EstimateHold) as error:
            with self.flow.lock:
                if self.visits.get(owner) is live and live['revision'] == revision:
                    live.pop('receipt', None)
            return {'state': 'held', 'hold': str(error), 'revision': revision,
                    'participant_release': False}

        with self.flow.lock:
            current_head(self.flow, owner, head)
            latest = self.visits.get(owner)
            checked(latest is live and latest['revision'] == revision and latest['plan'] == plan,
                    'These prescription details changed. Review them again.', 409)
            if action == 'validate' and latest.get('receipt') != state.get('receipt'):
                status = {'state': 'held', 'hold': 'result_changed'}
            if changed:
                self.revision += 1
                state['revision'] = self.revision
                state.pop('receipt', None)
                self.visits[owner] = state
                revision = state['revision']
            if result_receipt:
                latest['receipt'] = result_receipt
        return {**status, 'revision': revision, 'participant_release': False}
