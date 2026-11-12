"""D134 bounded local published PDP display; sealed research authority is retained."""
import getpass
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from guest_profiles import ProfileError

BUILD = 'b6992365031d7e3bc3253651b21d924e9d160d7a2c6511e1cab96eb9d782c15c'
NOTICE = ('Published 2026 plan premiums and deductibles from the September CMS snapshot. '
          'These are not your prescription costs or a recommendation. Drug coverage, pharmacy costs, '
          'subsidies, eligibility and current enrollment availability still need checking.')


def local_repository():
    package = Path(__file__).resolve().parents[2] / 'infrastructure/daylight-data'
    sys.path.insert(0, str(package / 'src'))
    from daylight_data.plan_types.store import Repository, connect
    dsn = (f'host={package / ".state/socket"} port=55485 '
           f'dbname=daylight_research_2026_r2 user={getpass.getuser()}')
    return Repository(lambda: connect(dsn, readonly=True), BUILD)


def published_plans(repository, body, zip_reference):
    if (not isinstance(body, dict) or set(body) != {'zipcode', 'county_fips', 'year'}
            or not isinstance(body.get('zipcode'), str) or not re.fullmatch(r'\d{5}', body['zipcode'])
            or not isinstance(body.get('county_fips'), str) or not re.fullmatch(r'\d{5}', body['county_fips'])
            or type(body.get('year')) is not int):
        raise ProfileError('Use the home ZIP, county and coverage year from your conversation.', 422)
    base = {'display_authorization': 'D134', 'display_scope': 'published_pdp_reference',
            'source_build': BUILD, 'personal_costs_available': False,
            'personal_recommendation_available': False, 'all_market_complete': False,
            'notice': NOTICE, 'plans': []}
    if body['year'] != 2026:
        return {**base, 'status': 'unsupported_year', 'message': 'This pilot has 2026 Part D plan information. Plans for another coverage year are not supported yet.'}
    if body['county_fips'] != '12021':
        return {**base, 'status': 'unsupported_county', 'message': 'Part D plan information in this pilot covers Collier County, Florida.'}
    if not any(row[0] == body['county_fips'] for row in zip_reference.get(body['zipcode'], [])):
        raise ProfileError('Confirm the home ZIP and county in the conversation before viewing Part D plans.', 422)
    if repository is None:
        raise RuntimeError('PART_D_SOURCE_UNAVAILABLE')
    collected = {}
    for kind in ('pdp_offering', 'pdp_county', 'pdp_restriction'):
        # Inspect the exact sealed source revision; D134 authorizes this separate
        # bounded display adapter. No fabricated receipt or source promotion.
        source = repository.query({'reference_year': 2026, 'county_fips': '12021',
            'intended_use': 'developer_source_inspection', 'kind': kind, 'page_size': 100})
        if (source.get('build_id') != BUILD or source.get('next_after')
                or source.get('source_review_due') is not False or source.get('personal_quote') is not False):
            raise RuntimeError('PART_D_SOURCE_BINDING')
        collected[kind] = source
    offerings = collected['pdp_offering']['records']
    counties = collected['pdp_county']['records']
    restrictions = {r['cms_offering_id']: r['payload'] for r in collected['pdp_restriction']['records']}
    if (len(offerings) != 10 or len({r['cms_offering_id'] for r in offerings}) != 10
            or len(restrictions) != 10 or len(counties) != 1
            or counties[0]['county_fips'] != '12021' or counties[0]['region'] != '11'):
        raise RuntimeError('PART_D_POPULATION_BINDING')
    plans = []
    for row in offerings:
        raw = row['payload']; fields = raw['fields']; identifier = row['cms_offering_id']
        if (row['holds'] or row['region'] != '11' or raw['offering_id'] != identifier
                or raw['region'] != '11' or raw['state'] != 'FL' or identifier not in restrictions
                or fields['year']['value'] != 2026 or fields['plan_type']['value'] != 'PDP'):
            raise RuntimeError('PART_D_SCOPE_BINDING')
        plans.append({'id': identifier, 'name': fields['plan_name']['value'],
            'company': fields['marketing_name']['value'], 'fields': fields,
            'source': raw['source'], 'restriction': restrictions[identifier],
            'restriction_summary': ('No applicable published restriction was found in the retained check through October 25, 2026. This is a dated notice check, not live enrollment confirmation.'
                if any(check.get('as_of') == '2026-10-25'
                    and check.get('result') == 'no_applicable_published_restriction_found'
                    and not check.get('applicable_restriction_notices')
                    and not check.get('unresolved_restriction_questions')
                    for check in restrictions[identifier].get('checks', []))
                else 'Published restriction evidence needs checking. Current enrollment availability is not confirmed.'),
            'source_sha256': row['artifact_sha256']})
    return {**base, 'status': 'published_plans', 'profile': body, 'plans': plans,
            'source_review_holds': collected['pdp_offering']['unresolved_checks'],
            'source_policy': collected['pdp_offering']['source_policy']}


def install_part_d(server, repository=None):
    base = server.RequestHandlerClass
    class Handler(base):
        def do_POST(self):
            url = urlsplit(self.path)
            if url.path != '/api/plans/part-d':
                return super().do_POST()
            try:
                if not self.safe():
                    raise ProfileError('Request origin rejected.', 403)
                self.csrf()
                if url.query:
                    raise ProfileError('Keep personal details out of URLs.', 422)
                return self.respond(200, published_plans(repository, self.body(), server.adaptive.reference['zips']))
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except Exception:
                return self.respond(503, {'error': 'Part D plan information is temporarily unavailable. Your details are still here; try again.', 'code': 'PART_D_UNAVAILABLE'})
    server.RequestHandlerClass = Handler
    return server
