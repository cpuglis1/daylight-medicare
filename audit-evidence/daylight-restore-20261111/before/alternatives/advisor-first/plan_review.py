"""Reported-input checkpoint and visit-only handoff, never plan suitability.

The existing normalized profile owns meaning, provenance and unknowns. This
policy asks whether a useful initial comparison can be framed, not whether all
41 questions were asked or any personal coverage finding has been verified.
"""
import copy
import re
import secrets
import time

from comparison_profile import build_comparison_profile, _digest
from guest_profiles import ProfileError

VERSION = 'plan-review-20261104-r1'
TTL = 600
OPEN_STATES = {'unknown', 'deferred', 'declined'}
# D108 (November 8, 2026): the pilot tool uses 2026 Collier plan data only, so
# an unanswered coverage year defaults to 2026 for the review checkpoint. A
# year the person reports still wins; two different reported years still hold.
DEFAULT_YEAR = 2026
BAD_STATES = {'stale', 'conflicting', 'tentative', 'superseded'}


def input_digest(guide, record):
    """Bind all reports/dispositions, excluding navigation and learning progress."""
    conversation = record.get('conversation', {})
    return _digest({'fields': guide['fields'], 'facts': record['facts'],
        'dispositions': record.get('dispositions', {}),
        'entityDispositions': record.get('entityDispositions', {}),
        'provenance': record.get('natural', {}).get('provenance', {}),
        'conversation': {key: conversation.get(key) for key in
            ('baselineDispositions', 'skippedDetails', 'details', 'itemRevisions', 'itemInvalidations')}})


def readiness(guide, record, *, pending=None):
    goal_report = guide['fields'].get('intent.goal', {})
    if (goal_report.get('value') not in {'compare', 'review'}
            or goal_report.get('status') != 'reported'
            or record.get('conversation', {}).get('task') not in {'compare', 'review'}):
        # Learning and timing conversations have no comparison intake checklist.
        return {'version': VERSION, 'active': False, 'canReview': False,
                'criteria': [], 'missing': [], 'scope': {'year': None, 'zip': None, 'county': None},
                'holds': [], 'personalRecommendationAllowed': False}
    profile = build_comparison_profile(guide, record)
    facts = profile['facts']

    def field(path):
        return next(f for f in facts if f['ref']['path'] == path)

    def g(key):
        return field('guide.fields.' + key)

    def r(key, name='choice'):
        return field('readiness.facts.' + key + '.value.' + name)

    def known(fact, *, personal=True):
        return fact['usable_as_report'] and (not personal or fact['usable_for_bound_subject']
            or fact['capture_method'] == 'location_reference')

    criteria = []
    def add(key, label, identifier, reports, *, complete=None, allow_open=True, fields=None):
        states = [f['report_state'] for f in reports]
        answered = all(known(f, personal=key not in {'goal', 'priorities', 'costs'}) for f in reports)
        addressed = bool(complete if complete is not None else answered)
        if allow_open and any(s in OPEN_STATES for s in states):
            addressed = True
        if any(s in BAD_STATES for s in states):
            addressed = False
        state = 'reported' if addressed and answered else next((s for s in states if s in OPEN_STATES),
            'needs_clarification' if any(s in BAD_STATES for s in states) else 'missing')
        criteria.append({'id': key, 'label': label, 'question_id': identifier,
            'fields': fields, 'addressed': addressed, 'state': state,
            'report_refs': [copy.deepcopy(f['ref']) for f in reports]})

    goal, role = g('intent.goal'), g('subject.role')
    # The controller uses "compare" as an internal default even for an open
    # educational conversation. That routing default is not the person's goal.
    active = (known(goal, personal=False) and goal['value'] in {'compare', 'review'}
              and profile['extensions']['task'] in {'compare', 'review'})
    add('goal', 'What you want to compare', 'T01', [goal], complete=active, allow_open=False)
    add('person', 'Who the coverage is for', 'RC01', [role, r('RC01')],
        complete=known(role) and role['value'] in {'self', 'someone'}, allow_open=False)
    zip_fact, county = g('comparison.scope.zip'), g('comparison.scope.county')
    location_ok = known(zip_fact) and known(county) and isinstance(county['value'], dict)
    add('location', 'Home ZIP and county', 'T03' if not known(zip_fact) else 'RC02',
        [zip_fact, county], complete=location_ok, allow_open=False,
        fields=None if not known(zip_fact) else ['county'])
    year_fact, start = r('RC03', 'year'), g('coverage.requestedStartMonth')
    years = {int(match[0]) for f in [year_fact, start] if known(f)
             if (match := re.findall(r'\b(?:19|20)\d{2}\b', str(f['value']))) and len(match) == 1}
    defaulted = not years and DEFAULT_YEAR is not None
    year = next(iter(years)) if len(years) == 1 else (DEFAULT_YEAR if defaulted else None)
    year_reports = [f for f in [year_fact, start] if f['report_state'] != 'unanswered'] or [year_fact]
    add('year', 'Coverage year', 'RC03', year_reports, complete=year is not None,
        allow_open=False, fields=['year'])
    if defaulted:
        criteria[-1].update(state='defaulted', label='Coverage year (2026 pilot data)')
    if len(years) > 1:
        criteria[-1].update(state='needs_clarification', addressed=False)
    add('coverage', 'Current health insurance', 'T05', [g('coverage.current')])
    add('enrollment', 'Current Medicare enrollment', 'RC04', [r('RC04')])
    for key, label, identifier, status_key, list_key, none_value in [
        ('doctors', 'Doctors and hospitals to keep', 'T06', 'needs.providersStatus', 'needs.providers', 'none'),
        ('medicines', 'Prescriptions to include', 'T07', 'needs.medicinesStatus', 'needs.medications', 'no')]:
        status, names = g(status_key), g(list_key)
        complete = known(status) and (status['value'] == none_value or known(names) and bool(names['value']))
        # Selecting "add" without any retained names is not a completed list.
        add(key, label, identifier, [status] if status['value'] == none_value else [status, names], complete=complete)
    add('travel', 'Routine care away from home', 'T08', [g('needs.travel')])
    add('costs', 'Monthly payments and care costs', 'T09', [g('needs.costPreference')])
    add('priorities', 'What matters most', 'T10', [g('needs.priorities')])
    missing = [c for c in criteria if not c['addressed']]
    holds = [{'code': 'REPORT_LEFT_OPEN', 'label': c['label'], 'state': c['state']}
             for c in criteria if c['state'] in OPEN_STATES]
    holds += [{'code': issue['code'], 'label': 'A reported detail needs clarification', 'state': 'held'}
              for issue in profile['integrity_issues']]
    if pending:
        holds.append({'code': 'PENDING_CLARIFICATION', 'label': 'A reported detail needs clarification', 'state': 'held'})
    # These are actual capability boundaries, not claims that checks ran.
    holds.extend({'code': code, 'label': label, 'state': 'not_verified'} for code, label in [
        ('ELIGIBILITY_NOT_VERIFIED', 'Eligibility and enrollment timing'),
        ('SOURCE_PURPOSE_REVIEW_REQUIRED', 'Published plan information for this coverage year')])
    if g('needs.providersStatus')['value'] != 'none':
        holds.append({'code': 'DOCTOR_CHECKS_OPEN', 'label': 'Exact doctor offices and plan participation', 'state': 'not_verified'})
    if g('needs.medicinesStatus')['value'] != 'no':
        holds.append({'code': 'MEDICINE_CHECKS_OPEN', 'label': 'Exact medicines, pharmacy, coverage and costs', 'state': 'not_verified'})
    scope = {'year': year, 'zip': zip_fact['value'] if known(zip_fact) else None,
             'county': copy.deepcopy(county['value']) if known(county) else None}
    return {'version': VERSION, 'active': bool(active), 'canReview': bool(active and not missing and not pending),
            'criteria': criteria, 'missing': missing, 'scope': scope, 'holds': holds,
            'personalRecommendationAllowed': False}


class PlanReviewService:
    """Short-lived owner/chain/report-bound receipts. Nothing saved to a profile."""
    def __init__(self):
        self.reviews = {}
        self.handoffs = {}

    def forget_owner(self, owner):
        for entries in (self.reviews, self.handoffs):
            for token in [t for t, value in entries.items() if value['owner'] == owner]:
                entries.pop(token, None)

    def _prune(self):
        for entries in (self.reviews, self.handoffs):
            for token in [t for t, value in entries.items() if value['expires'] <= time.time()]:
                entries.pop(token, None)
            while len(entries) >= 128:
                entries.pop(next(iter(entries)))

    def begin(self, owner, chain, guide, record, status, rows):
        self._prune()
        if not status['canReview']:
            raise ProfileError('A few key details are still open. Continue the conversation before reviewing plans.', 409)
        token = secrets.token_urlsafe(24)
        self.reviews[token] = {'owner': owner, 'chain': chain, 'digest': input_digest(guide, record),
                               'expires': time.time() + TTL}
        rows = copy.deepcopy(rows)
        for criterion in status['criteria']:
            if not any(row['id'] == criterion['question_id'] for row in rows):
                rows.append({'id': criterion['question_id'], 'label': criterion['label'],
                             'value': criterion['state'], 'status': criterion['state']})
        for row in rows:
            if row['id'] == 'RC03':
                row.update(label='Coverage year', value=status['scope']['year'])
            elif row['id'] == 'RC04':
                row['label'] = 'Current Medicare enrollment'
        order = ['RC01', 'T01', 'T03', 'RC02', 'RC03', 'T04', 'T05', 'RC04',
                 'T06', 'RC21', 'T07', 'RC22', 'RC23', 'T08', 'RC20', 'T09', 'RC25', 'T10']
        rows.sort(key=lambda row: order.index(row['id']) if row['id'] in order else len(order))
        return {'kind': 'plan_profile', 'token': token, 'label': 'See plans',
                'rows': rows, 'readiness': copy.deepcopy(status)}

    def _check(self, entries, token, owner, chain, guide, record):
        self._prune()
        entry = entries.get(token) if isinstance(token, str) else None
        if (not entry or entry['owner'] != owner or entry['chain'] != chain
                or entry['digest'] != input_digest(guide, record)):
            raise ProfileError('Your information changed or this review expired. Review your current information to see plans.', 409)
        return entry

    def confirm(self, token, owner, chain, guide, record, status):
        entry = self._check(self.reviews, token, owner, chain, guide, record)
        if not status['canReview']:
            raise ProfileError('Review the remaining details before seeing plans.', 409)
        receipt = secrets.token_urlsafe(24)
        self.handoffs[receipt] = {**entry, 'expires': time.time() + TTL}
        self.reviews.pop(token)
        return self.resolve(receipt, owner, chain, guide, record, status)

    def resolve(self, token, owner, chain, guide, record, status):
        entry = self._check(self.handoffs, token, owner, chain, guide, record)
        if not status['canReview']:
            raise ProfileError('Review the current information before continuing to plans.', 409)
        return {'version': VERSION, 'token': token, 'expiresAt': entry['expires'],
                'destination': 'plans', 'reportedInfoReviewed': True,
                'inputDigest': entry['digest'], 'scope': copy.deepcopy(status['scope']),
                'profile': build_comparison_profile(guide, record),
                'holds': copy.deepcopy(status['holds']), 'personalRecommendationAllowed': False}
