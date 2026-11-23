"""November 13 closing options from reported preferences and supplied evidence."""
from datetime import date

import medigap_profile
from conversation_checks import doctor_reports
from recommendation_engine import first_eligibility, medigap_letter_eligibility
import ux_pass

VERSION = 'closing-options-v1'


def _pick(letter, rates):
    listings = [rate for rate in rates if rate['variant'] == letter
                and type(rate.get('monthly_cents')) is int and rate['monthly_cents'] >= 0
                and rate.get('company') and rate.get('id') and rate.get('source_effective_date')]
    if not listings:
        return None
    first = min(listings, key=lambda rate: (
        rate['monthly_cents'], rate['company'].casefold(), rate['company'], rate['id']))
    return {'letter': letter, 'company': first['company'], 'rate_id': first['id'],
            'monthly_cents': first['monthly_cents'], 'rate_date': first['source_effective_date'],
            'company_count': len({rate['company'].strip().casefold() for rate in listings})}


def _medigap(profile, result, first_eligible):
    view = {'status': profile['status'], 'still_needed': profile['missing'],
            'first': None, 'alternative': None, 'excluded_count': 0}
    if profile['status'] != 'ready':
        return view
    expected = {key: profile['inputs'][source] for key, source in (
        ('zip', 'zipcode'), ('age', 'age'), ('gender', 'gender'), ('tobacco', 'tobacco'))}
    expected['requested_effective_date'] = profile['effective_date']
    if (not result or result.get('status') != 'matched_source_prices'
            or result.get('profile') != expected):
        return {**view, 'status': 'unsupported'}
    rates = result['plans']
    eligible = [rate for rate in rates if medigap_letter_eligibility(rate['variant'], first_eligible)[0] == 'met']
    first, alternative = _pick('G', eligible), _pick('N', eligible)
    return {**view, 'status': 'ready' if first and alternative else 'unsupported',
            'first': first, 'alternative': alternative, 'excluded_count': len(rates) - len(eligible)}


def _doctors(guide, record, checks):
    evidence = {row['key']: row['original_medicare'] for row in checks
                if row.get('kind') in ('doctor', 'doctor_matrix') and row.get('original_medicare')}
    doctors = []
    for key in doctor_reports(guide, record):
        result = evidence.get('doctor:' + key, {})
        doctors.append({'id': key, 'state': result.get('state', 'unknown'),
                        'record_date': result.get('record_date')})
    return doctors


def status(flow, guide, record, today=None, *, medigap_result=None, doctor_results=(), drug_results=None):
    """Return options and reason. Supply exact Plans prices and current-visit evidence.

    The pricing snapshot is fixed by the Plans profile, regardless of today.
    No eligibility, doctor or drug evidence is fetched by this function.
    """
    path = flow.value(guide, 'intent.coveragePath')
    start = flow.value(guide, 'intent.pathStart')
    priorities = list(flow.value(guide, 'needs.priorities') or ())
    preference = flow.value(guide, 'needs.costPreference')
    cost = preference if preference in ('predictable', 'lower_monthly') else None
    if cost is None and 'bills' in priorities and 'total_cost' not in priorities:
        cost = 'predictable'
    travel = flow.value(guide, 'needs.travel') or ()
    travel = next((value for value in (travel if isinstance(travel, (list, tuple)) else [travel])
                   if value in ('elsewhere_us', 'outside_us')), None)
    if path in ('original_only', 'keep_current', 'wait'):
        return {'version': VERSION, 'options': None, 'reason': 'no_rule_yet'}
    if getattr(flow, 'd166', False):
        from conversation_planner import DECISION_VERSION, VERSION as PLANNER_VERSION
        lean = {'state': 'chosen', 'path': path} if flow.value(guide, DECISION_VERSION) == PLANNER_VERSION else {'state': 'undecided', 'path': None}
    else:
        lean = ux_pass.coverage_path(chosen=path, cost_preference=cost, travel=travel,
                                     task=record.get('conversation', {}).get('task', ''))
    if not getattr(flow, 'd166', False) and lean['state'] != 'chosen' and start in (*ux_pass.PATHS, 'both'):
        lean = {'state': 'undecided', 'path': None} if start == 'both' else {
            'state': 'leaning', 'path': start}
    if lean['path'] != 'original_medigap' or cost != 'predictable':
        return {'version': VERSION, 'options': None, 'reason': 'no_rule_yet'}
    return {'version': VERSION, 'reason': None, 'options': {
        'basis': {'path': lean['path'], 'path_state': lean['state'],
                  'cost_preference': preference if preference in ('predictable', 'lower_monthly') else None,
                  'priorities': priorities},
        'medigap': _medigap(medigap_profile.for_flow(flow, guide, record), medigap_result, first_eligibility(guide, record)),
        'part_d': {'address': True, 'named': None,
                   'reason': 'dated_drug_lists' if drug_results else 'medicines_not_checked'},
        'doctors': _doctors(guide, record, doctor_results),
    }}


def attach(flow, out):
    """Build the current finish from the same prices and checks the visit sees."""
    out.pop('closingResearch', None)
    enrollment = out.get('enrollment') or {}
    line = enrollment.get('line') or {}
    finish = line.get('plan') or ('medicare_advantage' if
        flow.value(out['guide'], 'intent.coveragePath') == 'medicare_advantage' else None)
    if finish not in ('original_plus', 'medicare_advantage'):
        return
    guide, record = out['guide'], out['record']
    checks = (out.get('conversationCheck') or {}).get('results', [])
    drug_plans = next((r['plans'] for r in checks if r['kind'] == 'formulary'), {})
    doctors = _doctors(guide, record, checks)
    rows = []
    profile = out['medigapProfile']
    components = enrollment.get('record', {}).get('components', {})
    prices = None
    shopping_medigap = finish == 'original_plus' and components.get('medigap') == 'chosen'
    if shopping_medigap and profile['status'] == 'ready' and flow.closing_price_read:
        try:
            prices = flow.closing_price_read(profile['inputs'])
        except (OSError, RuntimeError, ValueError):
            pass
    options = status(flow, guide, record, medigap_result=prices, doctor_results=checks,
                     drug_results=drug_plans)['options']
    if shopping_medigap and options:
        for key, reason in (('first', 'predictable costs'), ('alternative', 'compare listed premiums and copays')):
            rate = options['medigap'][key]
            if rate:
                rows.append({'label': f"Medigap Plan {rate['letter']}",
                             'value': f"{rate['company']} · ${rate['monthly_cents'] / 100:,.2f}/month listed · "
                                      f"{rate['rate_date']} · {reason}"})
        if not rows:
            rows.append({'label': 'Medigap', 'value': 'Listed rates for your details still need checking.'})
    if doctors:
        matched = sum(doctor['state'] == 'accepts' for doctor in doctors)
        if finish == 'original_plus':
            rows.append({'label': 'Doctors', 'value': f'Medicare assignment is listed for {matched} of '
                         f'{len(doctors)} reported offices. Confirm assignment with the office.'})
        else:
            checked = [row['plans'] for row in checks if row['kind'] == 'doctor_matrix']
            listed = set.intersection(*({key for key, plan in plans.items()
                          if plan['membership'] in ('in_network', 'listed_in_network')} for plans in checked)
                          ) if len(checked) == len(doctors) else set()
            rows.append({'label': 'Doctors', 'value': f'{len(listed)} Medicare Advantage plans list all '
                         'selected offices in network. Confirm the office and plan before enrolling.'
                         if listed else 'Network fit for all reported doctors is still open.'})
    if components.get('part_d') != 'not_needed' and flow.value(guide, 'needs.medicinesStatus') != 'no':
        rows.append({'label': 'Medicines',
                     'value': ('Dated drug-list results are available above. Confirm restrictions and pharmacy costs.'
                               if drug_plans else 'Confirm your exact medicines to check the drug lists.')})
    next_line = line.get('next')
    next_step = next_line.get('text') if isinstance(next_line, dict) else next_line
    if rows:
        rows.append({'label': 'Next', 'value': next_step or 'Open your plans and review the remaining checks.'})
        out['closingResearch'] = {'title': 'What your research found', 'rows': rows}
