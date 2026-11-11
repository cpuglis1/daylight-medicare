"""Sealed research access to the 17 retained filing packets; no personal rating."""
from datetime import date
from pathlib import Path

from l10_targeted_intake import ROOT, BASE, PACKET, OUT, read, sha


class TargetedReferenceHeld(ValueError):
    pass


def source_state(schedule, cell, on_date=None):
    holds = []
    if schedule['status'] != 'APPROVED':
        holds.append('unapproved_or_replaced_source')
    if cell['annual_premium_cents'] == 0:
        holds.append('source_zero_meaning_unresolved')
    if not schedule['rate_effective_from'] or not schedule['rate_effective_through']:
        holds.append('approved_rate_period_unresolved')
    if on_date is not None:
        if not isinstance(on_date, str):
            raise TargetedReferenceHeld('Exact ISO date required')
        chosen = date.fromisoformat(on_date)
        if chosen.isoformat() != on_date or chosen.year != 2026:
            raise TargetedReferenceHeld('Only exact 2026 research dates supported')
        if schedule['rate_effective_from'] and schedule['rate_effective_through'] and not schedule['rate_effective_from'] <= on_date <= schedule['rate_effective_through']:
            holds.append('outside_sourced_rate_period')
    return holds


class TargetedArchive:
    def __init__(self):
        pointer = read(BASE / 'CURRENT_TARGETED_FILINGS.json')
        self.path = (ROOT / pointer['package']).resolve()
        if not self.path.is_relative_to(ROOT) or sha(self.path / 'manifest.json') != pointer['manifest_sha256'] or sha(self.path / 'SEALED') != pointer['seal_sha256']:
            raise TargetedReferenceHeld('Changed selected research archive')
        self.manifest = read(self.path / 'manifest.json')
        self.verify()
        parent = BASE / 'filing-reconciliation-r3/build-r1'
        self.schedules = {s['id']: s for p in [parent, self.path] for s in read(p / 'schedules.json')}
        self.rates = {r['id']: r for p in [parent, self.path] for r in read(p / 'rate-cells.json')}
        if len(self.schedules) != 628 or len(self.rates) != 63196:
            raise TargetedReferenceHeld('Changed composite source accounting')

    def verify(self):
        m = self.manifest
        if m['human_acceptance'] is not None or m['consumer_release_enabled'] is not False or m['full_l10_complete'] is not False:
            raise TargetedReferenceHeld('Research revision cannot grant consumer acceptance')
        for rel, wanted in m['files'].items():
            path = (ROOT / rel).resolve()
            if not path.is_relative_to(ROOT) or sha(path) != wanted:
                raise TargetedReferenceHeld('Changed bound evidence: ' + rel)
        if not read(ROOT / m['independent_audit'])['passed']:
            raise TargetedReferenceHeld('Exact independent source audit required')

    def observation(self, request, *, research=False):
        if research is not True:
            raise TargetedReferenceHeld('Explicit research=True required; no personal rating release')
        if not isinstance(request, dict) or set(request) - {'rate_id', 'on_date'} or not isinstance(request.get('rate_id'), str):
            raise TargetedReferenceHeld('Only exact source ID and optional research date are supported')
        self.verify()
        cell = self.rates.get(request['rate_id'])
        if cell is None:
            raise TargetedReferenceHeld('Unknown exact source observation')
        schedule = self.schedules[cell['schedule_id']]
        holds = source_state(schedule, cell, request.get('on_date'))
        return {'rate_id': cell['id'], 'case': cell['case'], 'source_page': cell['source_page'],
                'source_pdf_sha256': cell['source_pdf_sha256'], 'schedule_id': schedule['id'],
                'status': 'held_source_observation' if holds else 'research_source_grid_only', 'holds': holds,
                'annual_premium_cents': None if holds else cell['annual_premium_cents'], 'unit': 'USD/year',
                'form_raw': schedule['fields']['Form Number'], 'region_raw': schedule['fields']['Region'],
                'rate_effective_from': schedule['rate_effective_from'], 'rate_effective_through': schedule['rate_effective_through'],
                'policy_issue_dates_are_not_rate_periods': True, 'current_sale': 'unknown', 'personal_quote': False,
                'human_acceptance': None, 'consumer_release_enabled': False, 'full_l10_complete': False}
