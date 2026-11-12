"""Typed catalog metrics and consequential checks from the confirmed chat profile.

No scraping, fuzzy identity joins, browser-authored evidence or model decisions.
Reports establish requirements, never external coverage verification.
"""
import copy
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from comparison_evidence import canonical_sha256, reject_economic_fields
from plans_authority import permits
from plans_catalog import ROOT, SHA256

VERSION = 'plans-adapters-20261105-r2'
METRICS = ('monthly_plan_premium', 'in_network_medical_limit')
CHECKS = ('coverage_path', 'eligibility', 'service_area', 'restrictions',
          'drug_arrangement', 'providers', 'medicines', 'travel', 'assistance', 'baseline',
          'stated_priorities', 'budget')
FINDINGS_PATH = ROOT / 'cms-slice/data-sources/plans-verification-findings.json'
METRIC_FIELDS = dict(zip(METRICS, ('plan_premium', 'medical_maximums')))


def decimal_amount(value, unit):
    if (not isinstance(value, dict) or value.get('type') != 'decimal'
            or not isinstance(value.get('amount'), str) or value.get('currency') != 'USD'
            or value.get('unit') != unit):
        return None
    try:
        amount = Decimal(value['amount'])
        return amount if amount.is_finite() and amount >= 0 else None
    except InvalidOperation:
        return None


def metric_payload(identifier, key, metric):
    return {'catalog_sha256': SHA256, 'offering_id': identifier,
            'metric': key, 'finding': metric}


def catalog_metrics(typed, plans):
    rows = {row['offering_id']: row for row in typed['plans']}
    result = {}
    for plan in plans:
        source = rows[plan['id']]
        premium = source['scenarios']['premium_12_months']
        maximum = source['published']['medical_maximums']
        result[plan['id']] = {}
        for key, data, unit, refs, conditions in (
            (METRICS[0], premium.get('monthly_rate'), 'month', premium.get('source_refs', []),
             premium.get('conditions', {})),
            (METRICS[1], (maximum.get('value') or {}).get('in_network'), 'plan_year',
             maximum.get('source_refs', []), maximum.get('conditions', {}))):
            cell = plan['fields'][METRIC_FIELDS[key]]
            amount = decimal_amount(data, unit)
            valid = (cell['state'] in {'published', 'reference'} and amount is not None and bool(refs))
            # Re-resolve every locator, including the exact offering ID.
            resolved = {}
            for ref in refs:
                node = typed['source_bindings']
                for part in ref.split('/'):
                    node = node[part]
                resolved[ref] = canonical_sha256(node)
            result[plan['id']][key] = {
                'state': 'available' if valid else 'held',
                'amount': str(amount) if valid else None, 'currency': 'USD', 'unit': unit,
                'basis': key, 'source_field': METRIC_FIELDS[key],
                'evidence_refs': list(refs), 'source_bindings': resolved,
                'conditions': copy.deepcopy(conditions) if valid else {},
                'reason_codes': [] if valid else list(cell['reason_codes']) or ['TYPED_METRIC_UNAVAILABLE']}
    return result


class VerificationFindings:
    """Reload server-owned exact, expiring findings; identity lookups never qualify.

    Each finding needs separate personal_check authority. A finding may be
    imported from a verified tool/reviewer without hand-authoring profile cases
    or repeating the catalog's metrics. No HTTP write or profile persistence.
    """
    def __init__(self, path=FINDINGS_PATH, now=None):
        self.path = Path(path)
        self.now = now or (lambda: datetime.now(timezone.utc))

    def read(self, input_digest, authority):
        try:
            data = json.loads(self.path.read_bytes())
            reject_economic_fields(data)
            if data['schema'] != 'plans-verification-findings/1' or not isinstance(data['findings'], list):
                raise ValueError('FINDINGS_SCHEMA_INVALID')
            accepted, duplicates, seen = {}, set(), set()
            for row in data['findings']:
                if row.get('input_digest') != input_digest:
                    continue
                identifier, key, fact = row['offering_id'], row['check'], row['finding']
                pair = (identifier, key)
                if pair in seen:
                    duplicates.add(pair)
                seen.add(pair)
                checked = datetime.fromisoformat(fact['checked_at'])
                expires = datetime.fromisoformat(fact['expires_at'])
                valid = (key in CHECKS and fact['state'] in {'meets', 'known_conflict'}
                    and fact.get('verification_kind') == 'personal_plan_check'
                    and fact['scope'] == {'year': 2026, 'county_fips': '12021'}
                    and isinstance(fact['evidence_refs'], list) and bool(fact['evidence_refs'])
                    and checked.tzinfo is not None and expires.tzinfo is not None
                    and checked <= self.now() < expires
                    and permits(authority, 'personal_check', row))
                if valid:
                    accepted[pair] = copy.deepcopy(fact)
            return {pair: fact for pair, fact in accepted.items() if pair not in duplicates}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return {}


def prepare_checks(profile, plans, findings=None):
    """All 41 meanings remain in the profile; only consequential checks activate."""
    subject = profile['profile_binding']['subject_id']
    facts = profile['facts']
    findings = findings or {}

    def report(path):
        matches = [f for f in facts if f['ref']['path'] == path
                   and f['ref']['subject_id'] == subject and f['ref']['item_id'] is None]
        if len(matches) != 1:
            return None
        f = matches[0]
        return f if (f.get('usable_for_bound_subject') is True
            and f.get('usable_as_report') is True and f['report_state'] in {'reported', 'explicit_none'}
            and f['ref']['scope'] == 'current') else None

    def g(key): return report('guide.fields.' + key)
    def r(key): return report('readiness.facts.' + key + '.value.choice')
    def is_value(fact, value): return fact is not None and fact['value'] == value
    def receipt(state, code, reports=(), **extra):
        return {'state': state, 'reason_codes': [code],
                'report_refs': [copy.deepcopy(f['ref']) for f in reports if f],
                'externally_verified': False, **extra}

    provider, medicine, travel, assistance = (g('needs.providersStatus'), g('needs.medicinesStatus'),
                                             g('needs.travel'), r('RC18'))
    # A contradictory detail/entity must not be erased by an earlier "none".
    provider_items = any(f['value'] and f['report_state'] in {'reported', 'conflicting', 'stale'}
                         for f in facts if f['ref']['path'] == 'guide.fields.needs.providers'
                         or f['ref']['path'].startswith('readiness.facts.RC21.value.items[].'))
    medicine_items = any(f['value'] and f['report_state'] in {'reported', 'conflicting', 'stale'}
                         for f in facts if f['ref']['path'] == 'guide.fields.needs.medications'
                         or f['ref']['path'].startswith('readiness.facts.RC22.value.items[].'))
    result = {}
    for plan in plans:
        checks = {key: receipt('needs_check', code) for key, code in {
            'coverage_path': 'COVERAGE_PATH_DECISION_REQUIRED',
            'eligibility': 'ENROLLMENT_AND_ELIGIBILITY_NOT_VERIFIED',
            'service_area': 'ADDRESS_AVAILABILITY_NOT_VERIFIED',
            'restrictions': 'PUBLISHED_RESTRICTION_QUALIFICATION_REQUIRED',
            'drug_arrangement': 'DRUG_COVERAGE_ARRANGEMENT_NOT_VERIFIED',
            'providers': 'PROVIDER_SITE_PARTICIPATION_NOT_VERIFIED',
            'medicines': 'EXACT_PRODUCT_PHARMACY_AND_COST_NOT_VERIFIED',
            'travel': 'ROUTINE_AWAY_CARE_NOT_VERIFIED',
            'assistance': 'ASSISTANCE_COST_BASIS_NOT_VERIFIED',
            'baseline': 'KEEP_CURRENT_COVERAGE_COMPARISON_NOT_VERIFIED',
            'stated_priorities': 'REPORTED_PRIORITIES_NEED_SUPPORTED_DIMENSIONS',
            'budget': 'DECLARED_BUDGET_BASIS_NOT_VERIFIED'}.items()}
        priority = g('needs.priorities')
        if priority:
            checks['stated_priorities']['report_refs'] = [copy.deepcopy(priority['ref'])]
            checks['stated_priorities']['input_state'] = 'reported_not_verified'
            if isinstance(priority['value'], list) and set(priority['value']) & {'total_cost', 'bills', 'other'}:
                checks['stated_priorities']['reason_codes'] = ['PRIORITY_EXCEEDS_PREMIUM_AND_MEDICAL_LIMIT']
        budget_facts = [f for f in facts if f['ref']['path'].startswith('readiness.facts.RC25.value.')]
        if is_value(r('RC25'), 'none') or all(f['report_state'] == 'unanswered' for f in budget_facts):
            checks['budget'] = receipt('not_required', 'NO_DECLARED_FIXED_BUDGET', [r('RC25')])
        else:
            checks['budget']['report_refs'] = [copy.deepcopy(f['ref']) for f in budget_facts
                                               if f['report_state'] != 'unanswered']
        if not plan['retained_restrictions']:
            checks['restrictions'] = receipt('not_required', 'NO_PUBLISHED_SPECIAL_RESTRICTION',
                                             evidence_refs=[f"r13:{plan['id']}:restrictions"])
        if is_value(provider, 'none') and not provider_items:
            checks['providers'] = receipt('not_required', 'NO_REPORTED_PROVIDER_REQUIREMENT', [provider])
        if is_value(medicine, 'no') and not medicine_items:
            checks['medicines'] = receipt('not_required', 'NO_REPORTED_MEDICINES', [medicine])
        if is_value(travel, 'local') or is_value(travel, ['local']):
            checks['travel'] = receipt('not_required', 'NO_REPORTED_ROUTINE_AWAY_CARE', [travel])
        if is_value(assistance, 'none') and 'D-SNP' not in plan['type']:
            checks['assistance'] = receipt('not_required', 'NO_REPORTED_ASSISTANCE_ADJUSTMENT', [assistance])
        # A report of A+B, county, current coverage or an identity match is useful
        # preparation, but never proof of eligibility, network or future fit.
        for key, report_fact in [('eligibility', r('RC04')), ('service_area', g('comparison.scope.zip')),
                                  ('baseline', g('coverage.current'))]:
            if report_fact:
                checks[key]['report_refs'] = [copy.deepcopy(report_fact['ref'])]
                checks[key]['input_state'] = 'reported_not_verified'
        for key in CHECKS:
            verified = findings.get((plan['id'], key))
            if verified:
                checks[key] = {**copy.deepcopy(verified), 'externally_verified': True,
                               'reason_codes': ['EXACT_PERSONAL_CHECK_ACCEPTED']}
        result[plan['id']] = checks
    return result


def work_items(checks):
    """One actionable grouped dependency per check, retaining affected plans."""
    items = []
    for key in CHECKS:
        affected = [identifier for identifier, rows in checks.items() if rows[key]['state'] == 'needs_check']
        if not affected:
            continue
        items.append({'check': key, 'state': 'not_verified', 'offering_ids': affected,
                      'reason_codes': sorted({code for identifier in affected
                                             for code in checks[identifier][key]['reason_codes']})})
    return items
