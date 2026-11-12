"""Fictional D146 replay. Installed only by the isolated, model-free demo."""
import json
from pathlib import Path

from guest_profiles import ProfileError

ASSETS = Path(__file__).resolve().parent / 'part-d-preview'
ROUTE = '/drug-estimate-preview'
API = '/api/drug-estimate-preview'
FILES = {'': ('index.html', 'text/html'), '/screen.css': ('screen.css', 'text/css'),
         '/screen.js': ('screen.js', 'text/javascript')}


def install_estimate_preview(server, service, cases):
    from daylight_data.serving.binding import ResearchServingError
    from daylight_data.serving.part_d_local import fictional_report

    if server.server_port != 8897 or not server.adaptive.fixture or server.budget is not None:
        raise ValueError('Use the isolated model-free estimate preview.')
    base = server.RequestHandlerClass
    by_id = {case['id']: case for case in cases}

    class Handler(base):
        def do_GET(self):
            if self.path == API:
                if self.validate_request():
                    return self.respond(200, {'cases': cases, 'expires':
                        service.foundation.manifest['policy']['technical_read_until_utc']})
                return None
            path = self.path.removeprefix(ROUTE)
            if self.path.startswith(ROUTE) and path in FILES:
                if self.validate_request():
                    file, mime = FILES[path]
                    return self.respond(200, (ASSETS / file).read_bytes(), mime + '; charset=utf-8')
                return None
            return super().do_GET()

        def do_POST(self):
            if self.path != API:
                return super().do_POST()
            if not self.validate_request():
                return None
            try:
                body = self.body()
                case_id, revision, quantity_mode = (
                    body.get(key) for key in ('case', 'revision', 'quantity_mode'))
                if (set(body) != {'case', 'revision', 'quantity_mode'}
                        or not isinstance(case_id, str) or case_id not in by_id
                        or type(revision) is not int or not 1 <= revision <= 1000000
                        or quantity_mode not in ('as_listed', 'missing', '30', '60')
                        or case_id != 'D146-03' and quantity_mode != 'as_listed'):
                    raise ProfileError('Choose a fictional example from this preview.', 422)
                case = by_id[case_id]
                results = []
                for choice in case['choices']:
                    report = fictional_report(case, choice)
                    if quantity_mode != 'as_listed':
                        report['medicines'][0]['quantity'] = (
                            None if quantity_mode == 'missing' else int(quantity_mode))
                    outcome = service.estimate(report, revision)
                    visible = {key: value for key, value in outcome.items()
                               if key in {'state', 'hold', 'missing', 'period_kind', 'start', 'end',
                                          'plan_premium_cents', 'drug_spending_cents',
                                          'plan_premium_plus_drugs_cents'}}
                    outlet = outcome.get('findings', {}).get('pharmacy')
                    if outlet:
                        visible['pharmacy'] = {key: outlet[key] for key in ('channel', 'status')}
                    results.append({'label': choice['label'], **visible})
                try:
                    service._scope()
                except ResearchServingError as error:
                    results = [{'label': choice['label'], 'state': 'held', 'hold': str(error)}
                               for choice in case['choices']]
                return self.respond(200, {'revision': revision, 'results': results})
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})

    server.RequestHandlerClass = Handler
    return server


def attach(server, root):
    from daylight_data.serving.part_d_local import local_candidate

    path = root / 'audit-evidence/d146-drug-estimate-20261112/cases.json'
    return install_estimate_preview(server, local_candidate(root), json.loads(path.read_text()))
