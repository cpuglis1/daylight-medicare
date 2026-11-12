"""D129 exact-profile source-price display. No profile storage or model context."""
import getpass
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from guest_profiles import ProfileError

BUILD = '7be76407ca94d33223ec0144bac16f2e220fba0205496bdf05577a42ab32831f'
DATE = '2026-11-10'
ZIPS = tuple(str(n) for n in range(34101, 34109))
KEYS = {'zipcode', 'age', 'gender', 'tobacco', 'effective_date'}
VARIANTS = ('A', 'B', 'C', 'D', 'F', 'HDF', 'G', 'HDG', 'K', 'L', 'M', 'N')
NOTICE = ('Prices match your ZIP, age, sex and tobacco inputs for November 10, 2026. '
          'These are listed premiums, not a guaranteed quote or a recommendation. '
          'Your eligibility and qualification for a rating class or discount still need checking.')


def local_repository():
    package = Path(__file__).resolve().parents[2] / 'infrastructure/daylight-data'
    sys.path.insert(0, str(package / 'src'))
    from daylight_data.csg_medigap.store import Repository, connect
    dsn = (f'host={package / ".state/socket"} port=55485 '
           f'dbname=daylight_research_2026_r2 user={getpass.getuser()}')
    return Repository(lambda: connect(dsn, 'daylight_research_2026_r2', readonly=True), BUILD)


def validate(body):
    if (set(body) != KEYS or not isinstance(body.get('zipcode'), str)
            or not re.fullmatch(r'\d{5}', body['zipcode'])
            or type(body.get('age')) is not int or not 0 <= body['age'] <= 120
            or body.get('gender') not in ('Female', 'Male')
            or body.get('tobacco') not in ('Non-Tobacco', 'Tobacco User')
            or not isinstance(body.get('effective_date'), str)):
        raise ProfileError('Enter an exact ZIP, age, sex and tobacco status for these prices.', 422)


def prices(repository, body):
    validate(body)
    base = {'display_authorization': 'D129', 'display_scope': 'profile_matched_source_prices',
            'source_build': BUILD, 'requested_effective_date': DATE,
            'personal_quote': False, 'eligibility': 'not_determined',
            'recommendation': 'not_provided', 'all_market_complete': False,
            'notice': NOTICE, 'plans': []}
    if not 65 <= body['age'] <= 74:
        return {**base, 'status': 'unsupported_pilot_age', 'message': (
            'Medigap pricing for ages 75+ is not supported in this pilot.' if body['age'] >= 75 else
            'Medigap pricing in this pilot supports ages 65–74; under-65 pricing is not supported.')}
    if body['zipcode'] not in ZIPS:
        return {**base, 'status': 'unsupported_pilot_zip',
                'message': 'Medigap pricing in this pilot covers ZIPs 34101–34108. Your ZIP is not supported yet.'}
    if body['effective_date'] != DATE:
        return {**base, 'status': 'unsupported_price_date',
                'message': 'These Medigap prices were requested for November 10, 2026. Prices for another date are not available yet.'}
    if repository is None:
        raise RuntimeError('MEDIGAP_SOURCE_UNAVAILABLE')
    source = repository.query(**body)
    if (source.get('build_id') != BUILD or source.get('personal_quote') is not False
            or source.get('status') != 'matched_source_observations'):
        raise RuntimeError('MEDIGAP_SOURCE_UNAVAILABLE')
    issues = {x['record_id'] for x in source.get('field_issues', [])}
    expected = {k: body[v] for k, v in (('zip', 'zipcode'), ('age', 'age'), ('gender', 'gender'),
                                      ('tobacco', 'tobacco'), ('requested_effective_date', 'effective_date'))}
    rows = source['records']
    if not rows or len(rows) > 1000:
        raise RuntimeError('MEDIGAP_SOURCE_UNAVAILABLE')
    plans = []
    for row in rows:
        if (any(row['scenario'].get(k) != v for k, v in expected.items())
                or row['variant'] not in VARIANTS or row['source_sha256'] != source['source_sha256']):
            raise RuntimeError('MEDIGAP_PROFILE_MISMATCH')
        plans.append({
            'id': row['id'], 'company': row['company_name_raw'], 'variant': row['variant'],
            'naic': row['naic'], 'rating_class': row['rating_class_raw'],
            'rating_type': row['rating_type_raw'], 'select_observed': row['select_observed'],
            **{k: row[k] for k in ('monthly_cents', 'annual_cents', 'monthly_with_discounts_cents',
                                   'annual_with_discounts_cents')},
            'household_discount': row['raw']['HH Discount'], 'policy_fee': row['raw']['Policy Fee'],
            'policy_fee_timing': row['policy_fee_timing'], 'discount_eligibility': row['discount_eligibility'],
            'source_effective_date': row['source_effective_date'], 'effective_end': row['effective_end'],
            'policy_form': row['policy_form'], 'policy_edition': row['policy_edition'],
            'source_sha256': row['source_sha256'], 'source_locator': row['source_locator'],
            'source_fields': row['raw'], 'rating_labels_need_review': row['id'] in issues,
        })
    return {**base, 'status': 'matched_source_prices', 'profile': expected,
            'plans': plans, 'source_review_holds': source['holds']}


def install_medigap(server, repository=None):
    """Same-origin POST only, with the existing guest/CSRF boundary and no AI calls."""
    base = server.RequestHandlerClass

    class Handler(base):
        def do_POST(self):
            url = urlsplit(self.path)
            if url.path != '/api/plans/medigap':
                return super().do_POST()
            try:
                if not self.safe():
                    raise ProfileError('Request origin rejected.', 403)
                self.csrf()
                if url.query:
                    raise ProfileError('Keep personal details out of URLs.', 422)
                body = self.body()
                value = prices(repository, body)
                return self.respond(200, value)
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except Exception:
                # No source rows, personal inputs, credentials or query text in errors/logs.
                return self.respond(503, {'error': 'Medigap prices are temporarily unavailable. Your entries are still here; try again.',
                                          'code': 'MEDIGAP_UNAVAILABLE'})

    server.RequestHandlerClass = Handler
    return server
