"""Visit-only cross-plan research using the existing exact-input estimator.

No recommendation release, source acceptance or exact-store quote is implied.
Every read rechecks source authority and every estimate remains receipt-bound.
"""
from copy import deepcopy
from daylight_data.serving.part_d_math import EstimateHold


def compare(service, report, revision, plans, *, costs):
    service._scope()
    rows = {}
    for identifier, plan in plans.items():
        row = {'name': plan['name'], 'pharmacy': {'state': 'unknown'},
               'state': 'missing_inputs', 'hold': 'Refill and estimate details are still needed.'}
        if report.get('pharmacy') and report['pharmacy'].get('channel'):
            try:
                refs = []
                outlet, _ = service.pharmacy(refs, identifier, report['pharmacy'])
                row['pharmacy'] = {'state': outlet['status'], 'sources': refs}
            except EstimateHold as error:
                row['pharmacy']['hold'] = str(error)
        if costs:
            exact = {**deepcopy(report), 'offering_id': identifier}
            result = service.estimate(exact, revision)
            row.update({key: result[key] for key in ('state', 'hold', 'start', 'end',
                'drug_spending_cents', 'plan_premium_cents', 'plan_premium_plus_drugs_cents') if key in result})
            if result['state'] == 'offline_average_candidate': row.pop('hold', None)
            if result['state'] == 'offline_average_candidate' and not service.check_receipt(exact, revision, result['receipt']):
                row = {'name': plan['name'], 'pharmacy': {'state': 'unknown'},
                       'state': 'held', 'hold': 'result_changed'}
        rows[identifier] = row
    service._scope()
    return {'kind': 'drug_comparison', 'key': 'drug', 'name': 'Your pharmacy and drug costs',
            'plans': rows, 'participant_release': False,
            'details': ['Pharmacy listings and drug coverage are separate checks. Missing pharmacy evidence stays unresolved.',
                        'Estimates use published retail averages for the selected refill dates, not your store’s exact prices. '
                        'Medical costs are not included. Plans without an estimate cannot be called more expensive.']}
