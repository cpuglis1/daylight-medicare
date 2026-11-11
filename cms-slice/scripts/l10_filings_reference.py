"""Integrity-checked research observations only; no personal rating interface."""
from datetime import date
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l10-medigap-2026-10-28'


class FilingIntegrityError(ValueError):
    pass


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify_hashes(root, expected):
    root = Path(root).resolve()
    for relative, wanted in expected.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file() or digest(path) != wanted:
            raise FilingIntegrityError('Missing or changed sealed file: ' + relative)


def observation_state(schedule, cell, on_date=None):
    """Source-state decision only. No age/sex/tobacco/customer inputs accepted."""
    reasons = []
    if schedule['status'] != 'APPROVED':
        reasons.append('superseded_or_unapproved_schedule')
    if cell['annual_premium_cents'] == 0:
        reasons.append('source_zero_meaning_unresolved')
    if not schedule['rate_effective_from'] or not schedule['rate_effective_through']:
        reasons.append('rate_effective_period_unresolved')
    if on_date is not None:
        if not isinstance(on_date, str):
            raise ValueError('Use an exact ISO date within 2026')
        selected = date.fromisoformat(on_date)
        if selected.isoformat() != on_date or selected.year != 2026:
            raise ValueError('Only exact 2026 research dates are supported')
        if schedule['rate_effective_from'] and schedule['rate_effective_through']:
            if not schedule['rate_effective_from'] <= on_date <= schedule['rate_effective_through']:
                reasons.append('outside_sourced_rate_period')
    return reasons


class FilingArchive:
    def __init__(self):
        pointer = read(BASE / 'CURRENT_FILINGS.json')
        self.path = (ROOT / pointer['package']).resolve()
        if not self.path.is_relative_to(ROOT) or pointer['human_acceptance'] is not None or pointer['consumer_release_enabled'] is not False:
            raise FilingIntegrityError('Invalid research selector')
        if digest(self.path / 'manifest.json') != pointer['manifest_sha256']:
            raise FilingIntegrityError('Selected filing manifest changed')
        if digest(self.path / 'SEALED') != pointer['seal_sha256']:
            raise FilingIntegrityError('Selected filing seal changed')
        self.manifest = read(self.path / 'manifest.json')
        if read(self.path / 'SEALED')['manifest_sha256'] != pointer['manifest_sha256']:
            raise FilingIntegrityError('Seal does not bind selected manifest')
        self.verify()
        audit = read(ROOT / self.manifest['independent_audit'])
        if not audit['passed'] or audit['human_acceptance'] is not None or audit['consumer_release_enabled'] is not False:
            raise FilingIntegrityError('Invalid research audit gate')
        self.schedules = {s['id']: s for s in read(self.path / 'schedules.json')}
        self.rates = {r['id']: r for r in read(self.path / 'rate-cells.json')}
        self.conditions = read(self.path / 'conditions.json')

    def verify(self):
        verify_hashes(ROOT, self.manifest['files'])
        if self.manifest['consumer_release_enabled'] is not False or self.manifest['human_acceptance'] is not None:
            raise FilingIntegrityError('This revision has no consumer-release or acceptance authority')

    def observation(self, rate_id, *, research=False, on_date=None):
        if research is not True:
            raise ValueError('Explicit research=True required')
        self.verify()
        if not isinstance(rate_id, str) or rate_id not in self.rates:
            raise ValueError('Unknown exact source observation ID')
        cell = self.rates[rate_id]
        schedule = self.schedules[cell['schedule_id']]
        holds = observation_state(schedule, cell, on_date)
        return {
            'rate_id': rate_id, 'schedule_id': schedule['id'], 'case': schedule['case'],
            'source_pdf_sha256': cell['source_pdf_sha256'], 'source_page': cell['source_page'],
            'scope': 'Published annual source grid observation; personal applicability and current sale unknown',
            'status': 'held_source_observation' if holds else 'research_source_grid_only', 'holds': holds,
            'annual_premium_cents': None if holds else cell['annual_premium_cents'], 'unit': 'USD/year',
            'company_raw': schedule['fields']['Issuing Carrier'], 'form_raw': schedule['fields']['Form Number'],
            'plan_raw': schedule['fields']['Plan'], 'region_raw': schedule['fields']['Region'],
            'age_raw': cell['age_raw'], 'sex_raw': cell['sex_raw'], 'class_raw': cell['class_raw'],
            'rate_effective_from': schedule['rate_effective_from'], 'rate_effective_through': schedule['rate_effective_through'],
            'policy_issue_range_is_rate_effective_period': False,
            'conditions': [f for f in self.conditions if f['case'] == schedule['case']],
            'payment_and_fee_fields_raw': {k: v for k, v in schedule['fields'].items() if k.startswith('Modal Factors/') or k in ['Policy Fee Assessed', 'Fee Amount', 'Other Description']},
            'personal_quote': False, 'current_sale': 'unknown', 'human_acceptance': None,
            'consumer_release_enabled': False, 'full_l10_complete': False,
        }
