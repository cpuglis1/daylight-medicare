"""D134: a view of existing reports for the dated Collier PDP reference.

No new profile fields, persistence or drug-cost inference. Medicines and pharmacy
reports stay in the existing permissioned conversation, never in source queries.
"""
import re
from comparison_profile import build_comparison_profile
from plan_review import BAD_STATES, OPEN_STATES


def profile(guide, record):
    normalized = build_comparison_profile(guide, record)
    facts = {item['ref']['path']: item for item in normalized['facts']}
    def fact(path):
        return facts[path]
    def known(item):
        return item['usable_as_report'] and (item['usable_for_bound_subject']
                or item['capture_method'] == 'location_reference')
    def value(path):
        item = fact(path)
        return item['value'] if known(item) else None
    role = value('guide.fields.subject.role')
    zipcode = value('guide.fields.comparison.scope.zip')
    county = value('guide.fields.comparison.scope.county')
    county_fips = county.get('fips') if isinstance(county, dict) else None
    year_facts = [fact('readiness.facts.RC03.value.year'), fact('guide.fields.coverage.requestedStartMonth')]
    years = {int(match[0]) for f in year_facts if known(f)
             if (match := re.findall(r'\b(?:19|20)\d{2}\b', str(f['value']))) and len(match) == 1}
    blocked_year = (any(f['report_state'] in BAD_STATES for f in year_facts)
                    or not years and year_facts[0]['report_state'] in OPEN_STATES)
    year = next(iter(years)) if len(years) == 1 and not blocked_year else (2026 if not years and not blocked_year else None)
    defaulted = year == 2026 and not years
    missing, held = [], []
    for identifier, present, paths in [
        ('RC01', role in {'self', 'someone'}, ['guide.fields.subject.role', 'readiness.facts.RC01.value.choice']),
        ('T03', bool(zipcode), ['guide.fields.comparison.scope.zip']),
        ('RC02', bool(county_fips), ['guide.fields.comparison.scope.county']),
        ('RC03', year is not None, ['readiness.facts.RC03.value.year', 'guide.fields.coverage.requestedStartMonth'])]:
        if not present:
            missing.append(identifier)
            if any(fact(path)['report_state'] in OPEN_STATES for path in paths):
                held.append(identifier)
    message = ''
    if year is not None and year != 2026:
        message = 'Daylight has 2026 Part D plans. Plans for another coverage year aren’t loaded yet; you can look at the 2026 plans by choosing 2026.'
    elif county_fips and county_fips != '12021':
        message = 'Daylight has Part D plans for Collier County, Florida so far.'
    status = 'unsupported' if message else 'missing' if missing else 'ready'
    medicine_status = value('guide.fields.needs.medicinesStatus')
    medicines = value('guide.fields.needs.medications')
    return {'status': status, 'message': message, 'missing': missing, 'held': held,
            'inputs': {'zipcode': zipcode, 'county_fips': county_fips, 'year': year},
            'year_defaulted': defaulted,
            'medicines': medicines, 'medicine_status': medicine_status,
            'personal_costs_available': False,
            'details': [
                {'id': 'T03', 'label': 'Home ZIP code', 'value': zipcode},
                {'id': 'RC02', 'label': 'County', 'value': county.get('name') if isinstance(county, dict) else None},
                {'id': 'RC03', 'label': 'Coverage year', 'value': year},
                {'id': 'T07', 'label': 'Medicines shared in chat', 'value': 'None reported' if medicine_status == 'no' else medicines}]}
