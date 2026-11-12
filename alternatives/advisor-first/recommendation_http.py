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


def evaluate(server, inputs, medigap_repository, part_d_repository):
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
    return engine.evaluate(inp, ma_plans=ma_plans(server), medigap_result=medigap_result,
                           part_d_result=part_d_result)


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
                if not isinstance(body, dict) or set(body) != {'inputs'}:
                    raise ProfileError('Use current recommendation inputs.', 422)
                return self.respond(200, evaluate(server, body['inputs'], medigap_repository, part_d_repository))
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except ValueError:
                return self.respond(422, {'error': 'Use current recommendation inputs.'})
            except Exception:
                return self.respond(503, {'error': 'Daylight’s sorting is temporarily unavailable. Try again.',
                                          'code': 'RECOMMENDATION_UNAVAILABLE'})

    server.RequestHandlerClass = Handler
    return server
