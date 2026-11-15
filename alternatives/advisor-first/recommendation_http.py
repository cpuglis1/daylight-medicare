"""D147: evaluation-only tiered recommendation endpoint for the local demo (:8895).

Installed only by the unified local demo, which cannot run with the pilot gate,
so pilot participants never see it. Reads the same display data the Plans tabs
read; no model call, no profile write, nothing saved.
"""
from urllib.parse import urlsplit

from guest_profiles import ProfileError
import medigap_pilot
import part_d_pilot
from plans_adapters import catalog_metrics
import recommendation_engine as engine
from part_d_visit import current_head


def ma_plans(server):
    view, _ = server.plans.projection()
    metrics = catalog_metrics(server.plans.catalog.typed(), view['plans'])
    plans = []
    for plan in view['plans']:
        values = metrics[plan['id']]
        def amount(key):
            cell = values.get(key) or {}
            return cell.get('amount') if cell.get('state') == 'available' else None
        plans.append({'id': plan['id'], 'name': plan['name'], 'type': plan['type'],
                      'restrictions': list(plan.get('retained_restrictions') or []),
                      'drugs': (plan['fields'].get('part_d_deductible') or {}).get('state') != 'not_applicable',
                      'premium': amount('monthly_plan_premium'),
                      'in_network_limit': amount('in_network_medical_limit')})
    return plans


def evaluate(server, inputs, medigap_repository, part_d_repository, *, checks=(), expected_doctors=()):
    inp = engine.validate_inputs(inputs)
    gap = inp['medigap']
    medigap_result = None
    if gap.get('status') == 'ready':
        medigap_result = medigap_pilot.prices(medigap_repository, {
            'zipcode': gap['zipcode'], 'age': gap['age'], 'gender': gap['gender'],
            'tobacco': gap['tobacco'], 'effective_date': medigap_pilot.DATE})
    scope = inp['scope']
    part_d_result = None
    if inp.get('part_d_status') == 'ready':
        part_d_result = part_d_pilot.published_plans(part_d_repository, {
            'zipcode': scope['zipcode'], 'county_fips': scope['county_fips'], 'year': scope['year']},
            server.adaptive.reference['zips'])
    medicines, networks, original, drug_costs = {}, {}, (), None
    for result in checks:
        if result['kind'] == 'formulary':
            medicines = {key: plan['medicines'] for key, plan in result['plans'].items()}
        elif result['kind'] == 'drug_comparison':
            drug_costs = result['plans']
    selected = {row['key']: row for row in checks if row['kind'] == 'doctor_matrix'}
    if expected_doctors:
        rows = [selected.get('doctor:' + item, {}) for item in expected_doctors]
        original = [row.get('original_medicare', {}) for row in rows]
        identifiers = {plan for row in rows for plan in row.get('plans', {})}
        networks = {plan: [row.get('plans', {}).get(plan, {}) for row in rows] for plan in identifiers}
    return engine.evaluate(inp, ma_plans=ma_plans(server), medigap_result=medigap_result,
                           part_d_result=part_d_result, medicines=medicines, networks=networks,
                           doctors=original, drug_costs=drug_costs)


def install_recommendation(server, medigap_repository=None, part_d_repository=None):
    server.adaptive.eval_recommendations = True
    base = server.RequestHandlerClass

    class Handler(base):
        def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
            if self.path == '/api/status' and code == 200 and isinstance(value, dict):
                value = {**value, 'eval_recommendations': {'method': engine.METHOD, 'evaluation_only': True}}
            return super().respond(code, value, mime, cookie)

        def do_POST(self):
            url = urlsplit(self.path)
            if url.path != '/api/recommendation':
                return super().do_POST()
            try:
                if not self.safe():
                    raise ProfileError('Request origin rejected.', 403)
                self.csrf()
                if url.query:
                    raise ProfileError('Keep personal details out of URLs.', 422)
                body = self.body()
                if set(body) not in ({'inputs'}, {'inputs', 'continuation'}):
                    raise ProfileError('Use current recommendation inputs.', 422)
                flow = server.adaptive
                owner = server.profiles.digest(self.token())
                checks, doctors = (), ()
                inp = body['inputs']
                if 'continuation' in body:
                    with flow.lock:
                        response = current_head(flow, owner, body['continuation'])['response']
                        guide, record = response['guide'], response['record']
                        if response.get('recommendationInputs') != inp:
                            raise ProfileError('Refresh sorting from the current conversation.', 409)
                        controller = getattr(flow, 'conversation_checks', None)
                        if controller:
                            from conversation_checks import doctor_reports
                            checks = controller.reconcile(owner, guide, record)['results']
                            doctors = doctor_reports(guide, record)
                result = evaluate(server, inp, medigap_repository, part_d_repository,
                                  checks=checks, expected_doctors=doctors)
                if 'continuation' in body:
                    with flow.lock:
                        current_head(flow, owner, body['continuation'])
                return self.respond(200, result)
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except ValueError:
                return self.respond(422, {'error': 'Use current recommendation inputs.'})
            except Exception:
                return self.respond(503, {'error': 'Daylight’s sorting is temporarily unavailable. Try again.',
                                          'code': 'RECOMMENDATION_UNAVAILABLE'})

    server.RequestHandlerClass = Handler
    return server
