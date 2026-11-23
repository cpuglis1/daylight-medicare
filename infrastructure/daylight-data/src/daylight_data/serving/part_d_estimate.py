"""Offline D146 identities, formulary, pharmacy and average-based estimates."""
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import hashlib
import hmac
import json
import secrets

from .binding import ResearchServingError
from .part_d_math import EstimateHold, Fill, METHOD, calculate, money
from .pilot_foundation import enforce_scope, file_hash

SCOPE = {'year': 2026, 'county_fips': '12021', 'purpose': 'offline_research'}
PARAMETERS = 'docs/data/part-d-national-2026/candidate-r1'
PARAMETER_MANIFEST = 'c231f95a50ceab5b0ecf2d24654b25a1a8d258b4414937a702c1230b6e71fb4a'
FORMULARY_FIELDS = ('TIER_LEVEL_VALUE', 'PRIOR_AUTHORIZATION_YN', 'STEP_THERAPY_YN',
                    'QUANTITY_LIMIT_YN', 'QUANTITY_LIMIT_AMOUNT', 'QUANTITY_LIMIT_DAYS',
                    'SELECTED_DRUG_YN')
# The CMS archive's release date, distinct from the date embedded in member names.
FORMULARY_RELEASE = '2026-09-16'
CHANNELS = {('retail', 'preferred'): 'PREF', ('retail', 'standard'): 'NONPREF',
            ('mail', 'preferred'): 'MAIL_PREF', ('mail', 'standard'): 'MAIL_NONPREF'}
UNITS = {'ORAL TABLET': 'tablet', 'EXTENDED RELEASE ORAL TABLET': 'tablet',
         'DELAYED RELEASE ORAL TABLET': 'tablet', 'ORAL CAPSULE': 'capsule',
         'EXTENDED RELEASE ORAL CAPSULE': 'capsule', 'DELAYED RELEASE ORAL CAPSULE': 'capsule'}
DISPENSING = {'3336C0003X': 'community/retail', '3336M0002X': 'mail order',
              '3336L0003X': 'long-term care', '3336S0011X': 'specialty',
              '3336H0001X': 'home infusion', '3336I0012X': 'institutional',
              '3336C0002X': 'clinic'}


def parse(data, field):
    return json.loads(data[field])


def decimal(value, maximum):
    if type(value) not in (int, str, Decimal) or len(str(value)) > 24:
        raise EstimateHold('invalid_numeric_value')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise EstimateHold('invalid_numeric_value') from None
    if not result.is_finite() or not 0 <= result <= maximum:
        raise EstimateHold('invalid_numeric_value')
    return result


def one(rows, hold):
    if len(rows) != 1:
        raise EstimateHold(hold)
    return rows[0]


def missing(report):
    """Ask only for absent reports. Confirmations are explicit identifiers."""
    questions = []
    fields = ('offering_id', 'pharmacy', 'period', 'assistance', 'prior_spending', 'medicines')
    for field in fields:
        if report.get(field) in (None, '', []):
            questions.append(field)
    for field, parts in (
        ('pharmacy', ('npi', 'zip', 'address_id', 'channel')),
        ('period', ('kind', 'start', 'confirmed')),
    ):
        item = report.get(field)
        if isinstance(item, dict):
            questions.extend(f'{field}.{part}' for part in parts if item.get(part) in (None, ''))
    for index, med in enumerate(report.get('medicines') or []):
        for field in ('rxcui', 'quantity', 'unit', 'days_supply', 'fills'):
            if med.get(field) in (None, '', []):
                questions.append(f'medicines.{index}.{field}')
        for fill_index, fill in enumerate(med.get('fills') or []):
            for field in ('date', 'order'):
                if fill.get(field) in (None, ''):
                    questions.append(f'medicines.{index}.fills.{fill_index}.{field}')
    return questions


@lru_cache(maxsize=16)
def registry_file(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise EstimateHold('pharmacy_identity_source_changed')
    return json.loads(raw)


class PartDEstimate:
    def __init__(self, foundation):
        self.foundation = foundation
        self.binding = foundation.manifest['binding_id']
        self.receipt_key = secrets.token_bytes(32)

    def _scope(self, purpose='offline_research', year=2026, county_fips='12021'):
        scope = dict(year=year, county_fips=county_fips, purpose=purpose)
        enforce_scope(self.foundation.manifest, **scope, now=self.foundation.clock(),
                      served=getattr(self.foundation, "served", None))
        self.foundation._check_controls()

    def rows(self, dataset, refs, *, name=None, **filters):
        after = 0
        records = []
        while after is not None:
            result = self.foundation.read(dataset, **SCOPE, name=name, filters=filters,
                                          after=after, expected_binding=self.binding)
            records.extend(result['records'])
            after = result['next_after']
            if len(records) > 200:
                raise EstimateHold('narrow_search')
        refs.extend({'dataset': dataset, **record['locator']} for record in records)
        return [record['data'] for record in records]

    def products(self, refs, *, name=None, rxcui=None):
        filters = {} if rxcui is None else {'rxcui': rxcui}
        records = self.rows('drug_products', refs, name=name, **filters)
        products = []
        for row in records:
            identity = parse(row, 'payload')
            form = identity['dose_form']
            route = next((route for word, route in (
                ('INJECT', 'injection'), ('INHAL', 'inhalation'),
                ('OPHTHALMIC', 'ophthalmic'), ('NASAL', 'nasal'), ('OTIC', 'otic'),
                ('TRANSDERMAL', 'transdermal'), ('TOPICAL', 'topical'), ('RECTAL', 'rectal'),
                ('VAGINAL', 'vaginal'), ('SUBLINGUAL', 'sublingual'), ('ORAL', 'oral')
            ) if word in (form or '')), None)
            products.append({'rxcui': row['rxcui'], 'name': identity['name'],
                             'strength_description': identity['ingredient_strength_description'],
                             'form': form, 'route': route, 'type': identity['type'],
                             'identity_source': identity['source']})
        return products

    def _location(self, row):
        record = parse(row, 'record_json')
        location = one(record['candidate_locations'], 'pharmacy_outlet_unresolved')
        address = location.get('registry_address') or location.get('address')
        if not address or not location.get('address_id'):
            raise EstimateHold('pharmacy_outlet_unresolved')
        source = record['identity_source']
        path = (self.foundation.root / source.get('path', '')).resolve()
        org = {}
        if (source.get('sha256') and type(source.get('result_index')) is int
                and path.is_relative_to(self.foundation.root)):
            try:
                candidate = registry_file(path, source['sha256'])['results'][source['result_index']]
            except (OSError, KeyError, IndexError, ValueError) as error:
                if isinstance(error, EstimateHold):
                    raise
                raise EstimateHold('pharmacy_identity_source_unavailable') from None
            if str(candidate['number']) != row['npi']:
                raise EstimateHold('pharmacy_outlet_unresolved')
            org = candidate
        address = {key: address[key] for key in ('address_1', 'address_2', 'city', 'state', 'postal_code')}
        if address['postal_code'][:5] != row['network_zip']:
            raise EstimateHold('pharmacy_outlet_unresolved')
        taxonomies = [item['code'] for item in org.get('taxonomies', [])]
        return {'npi': row['npi'], 'zip': row['network_zip'], 'address_id': location['address_id'],
                'address': address, 'name': org.get('basic', {}).get('organization_name'),
                'aliases': [name['organization_name'] for name in org.get('other_names', [])
                            if name.get('organization_name')],
                'dispensing_types': [DISPENSING[code] for code in taxonomies if code in DISPENSING],
                'taxonomy_codes': taxonomies, 'identity_source': source}

    def outlets(self, refs, *, zip, npi=None, name=None):
        filters = {'network_zip': zip}
        if npi is not None:
            filters['npi'] = npi
        locations = []
        for row in self.rows('pharmacy_locations', refs, **filters):
            if row['identity_status'] in ('no_registry_identity', 'network_zip_unpublished'):
                continue
            try:
                location = self._location(row)
            except EstimateHold as error:
                if npi or str(error) != 'pharmacy_outlet_unresolved':
                    raise
                continue
            labels = ' '.join([location['name'] or '', *location['aliases'],
                               *location['address'].values()]).casefold()
            if name is None or all(word in labels for word in name.casefold().split()):
                locations.append(location)
        return locations

    def pharmacy(self, refs, plan, selection):
        if selection['channel'] not in ('retail', 'mail'):
            raise EstimateHold('unsupported_channel')
        found = self.outlets(refs, zip=selection['zip'], npi=selection['npi'])
        outlet = one([row for row in found if row['address_id'] == selection['address_id']],
                     'pharmacy_outlet_unresolved')
        net = one(self.rows('pharmacy_network', refs, offering_id=plan, pharmacy_npi=outlet['npi'],
                            PHARMACY_ZIPCODE=outlet['zip']), 'pharmacy_plan_outlet_unknown')
        channel = selection['channel']
        return ({**outlet, 'plan': plan, 'channel': channel, 'status': net[f'{channel}_status']}, net)

    def plan(self, refs, offering):
        return parse(one(self.rows('drug_plans', refs, offering_id=offering),
                         'plan_unknown'), 'payload')

    def formulary(self, refs, plan, rxcui):
        rows = self.rows('formulary_rows', refs, formulary_id=plan['formulary_id'],
                         rxcui=rxcui, table_name='basic')
        matched = []
        for row in rows:
            native = parse(row, 'raw_json')
            if (native['CONTRACT_YEAR'], native['FORMULARY_VERSION']) != ('2026', plan['formulary_version']):
                continue
            matched.append({'ndc': row['ndc'], 'ordinal': row['ordinal'],
                            'formulary_id': plan['formulary_id'], 'version': plan['formulary_version'],
                            **{field: native.get(field) for field in FORMULARY_FIELDS}})
        return matched

    def formulary_matrix(self, medicines):
        """Compare exact products under one bound offline snapshot."""
        if not 1 <= len(medicines) <= 12:
            raise EstimateHold('list_size_unsupported')
        codes = sorted({m['rxcui'] for m in medicines if m.get('rxcui')})
        with self.foundation.snapshot(**SCOPE) as conn:
            offered = conn.execute("""
                SELECT data->>'offering_id' AS id, (data->>'payload')::jsonb AS plan
                FROM dl_pilot_foundation.drug_plans ORDER BY ordinal
            """).fetchall()
            if (len(offered) != self.foundation.manifest['datasets']['drug_plans']['rows']
                    or len({row['id'] for row in offered}) != len(offered)):
                raise ResearchServingError('PILOT_DATABASE_FORMULARY_SCOPE_MISMATCH')
            found = conn.execute("""
                SELECT data FROM dl_pilot_foundation.formulary_rows
                WHERE data->>'rxcui' = ANY(%s) ORDER BY ordinal
            """, (codes,)).fetchall() if codes else []
        basic, supplemental = {}, set()
        for row in found:
            data = row['data']
            raw = parse(data, 'raw_json')
            if data['table_name'] == 'basic' and raw['CONTRACT_YEAR'] == '2026':
                key = data['formulary_id'], raw['FORMULARY_VERSION'], data['rxcui']
                basic.setdefault(key, set()).add(tuple(raw.get(field) for field in FORMULARY_FIELDS))
            elif data['table_name'] != 'basic':
                supplemental.add((raw.get('CONTRACT_ID'), raw.get('PLAN_ID'), data['rxcui']))

        plans = {}
        for row in offered:
            plan = row['plan']
            _, contract, pbp, _ = row['id'].split(':')
            checks = []
            for medicine in medicines:
                code = medicine.get('rxcui')
                matches = basic.get((plan['formulary_id'], plan['formulary_version'], code), set())
                status = ('needs_detail' if not code else 'unknown' if plan['suppressed']
                          else 'covered' if len(matches) == 1 else 'unknown' if matches
                          or (contract, pbp, code) in supplemental else 'not_listed')
                values = dict(zip(FORMULARY_FIELDS, next(iter(matches)))) if status == 'covered' else {}
                flag = {'Y': True, 'N': False, '1': True, '0': False}
                checks.append({**medicine, 'state': status, 'evidence_date': FORMULARY_RELEASE,
                               'tier': values.get('TIER_LEVEL_VALUE'),
                               'prior_authorization': flag.get(values.get('PRIOR_AUTHORIZATION_YN')),
                               'step_therapy': flag.get(values.get('STEP_THERAPY_YN')),
                               'quantity_limit': flag.get(values.get('QUANTITY_LIMIT_YN')),
                               'quantity_limit_amount': values.get('QUANTITY_LIMIT_AMOUNT'),
                               'quantity_limit_days': values.get('QUANTITY_LIMIT_DAYS')})
            plans[row['id']] = {'name': plan['name'], 'medicines': checks}
        return plans

    def _parameters(self):
        root = self.foundation.root / PARAMETERS
        if file_hash(root / 'manifest.json') != PARAMETER_MANIFEST:
            raise EstimateHold('federal_parameter_binding_changed')
        manifest = json.loads((root / 'manifest.json').read_text())
        path = root / 'costs.json'
        if file_hash(path) != manifest['files_sha256']['costs.json']:
            raise EstimateHold('federal_parameter_binding_changed')
        return {row['id']: row['value'] for row in json.loads(path.read_text())}

    def _inputs(self, report, refs, findings):
        if report['assistance'] != 'none':
            raise EstimateHold('assistance_unresolved_or_unsupported')
        if report['prior_spending'] != 'confirmed_zero':
            raise EstimateHold('prior_spending_unresolved_or_unsupported')
        period = report['period']
        start = date.fromisoformat(period['start'])
        kind = period['kind']
        if (period['confirmed'] is not True or start.year != 2026 or start.day != 1
                or (start.month == 1 and kind != 'full_year')
                or (start.month > 1 and kind != 'remaining_year')):
            raise EstimateHold('period_unresolved_or_unsupported')

        offering = report['offering_id']
        plan = self.plan(refs, offering)
        if plan['suppressed'] or plan['monthly_raw']['SNP'] != '0':
            raise EstimateHold('special_plan_rules_unresolved')
        outlet, network = self.pharmacy(refs, offering, report['pharmacy'])
        findings['pharmacy'] = outlet
        if outlet['status'] not in ('standard', 'preferred'):
            raise EstimateHold('channel_not_offered')
        if outlet['channel'] != 'retail' or network['IN_AREA_FLAG'] != '1':
            raise EstimateHold('only_in_area_retail_average_available')
        if ('community/retail' not in outlet['dispensing_types']
                or set(outlet['dispensing_types']) & {'long-term care', 'institutional', 'home infusion'}):
            raise EstimateHold('dispensing_setting_unresolved_or_unsupported')
        suffix = CHANNELS[(outlet['channel'], outlet['status'])]
        context = parse(one(self.rows('drug_benefit_context', refs, offering_id=offering),
                            'benefit_type_unresolved'), 'payload')
        setup = context['rx']['rxDetails']['rxSetup']
        benefit = setup['rxSetupDetails']['drugBenefitType']
        if benefit not in ('DS', 'AE', 'BA', 'EA'):
            raise EstimateHold('benefit_type_unsupported')
        schedules = self.rows('cost_schedules', refs, offering_id=offering, table_name='beneficiary')
        schedules = [parse(row, 'modeled_json') for row in schedules]
        parameters = self._parameters()
        standard = parameters['d_standard_deductible']
        deductible = money(decimal(plan['monthly_raw']['DEDUCTIBLE'], Decimal(standard) / 100))
        premium = money(decimal(plan['monthly_raw']['PREMIUM'], 10000))
        fills = self._fills(report['medicines'], refs, findings, plan, schedules, network, suffix,
                            start, benefit)
        result = calculate(fills, deductible=deductible, standard_deductible=standard,
                           threshold=parameters['d_oop_threshold'], benefit=benefit)
        return {**result, 'period_kind': kind, 'start': start.isoformat(), 'end': '2026-12-31',
                'price_basis': 'CMS Q3 2026 in-area retail average plus dated dispensing fee',
                'premium_months': 13 - start.month, 'monthly_plan_premium_cents': premium,
                'plan_premium_cents': premium * (13 - start.month),
                'plan_premium_plus_drugs_cents': premium * (13 - start.month) + result['drug_spending_cents'],
                'drug_deductible_cents': deductible, 'benefit_type': benefit}

    def _fills(self, medicines, refs, findings, plan, schedules, network, suffix, start, benefit):
        if not 1 <= len(medicines) <= 12:
            raise EstimateHold('unsupported_list_size')
        fills, order_keys, products = [], set(), set()
        findings['medicines'] = []
        for med in medicines:
            rxcui = med['rxcui']
            if rxcui in products:
                raise EstimateHold('duplicate_exact_product')
            products.add(rxcui)
            product = one(self.products(refs, rxcui=rxcui), 'medicine_identity_unresolved')
            rows = self.formulary(refs, plan, rxcui)
            findings['medicines'].append({'product': product, 'formulary': rows})
            if med.get('ndc'):
                rows = [row for row in rows if row['ndc'] == med['ndc']]
            row = one(rows, 'exact_formulary_product_unresolved')
            if 'INSULIN' in product['name']:
                raise EstimateHold('insulin_negotiated_price_or_unit_unresolved')
            if row['SELECTED_DRUG_YN'] != 'N':
                raise EstimateHold('selected_drug_rule_unresolved')
            if row['PRIOR_AUTHORIZATION_YN'] != 'N' or row['STEP_THERAPY_YN'] != 'N':
                raise EstimateHold('criteria_unresolved')
            if row['QUANTITY_LIMIT_YN'] != 'N':
                units = self.rows('quantity_units', refs, table='basic', rxcui=rxcui,
                                  source_row=str(row['ordinal']))
                findings['medicines'][-1]['quantity_unit_evidence'] = [
                    {'unit': item['unit'], 'state': item['state']}
                    for item in units if item['formulary_id'] == row['formulary_id']]
                raise EstimateHold('quantity_limit_rule_unresolved')
            unit = UNITS.get(product['form'])
            if (unit is None or unit != med['unit'] or product['type'] not in ('SCD', 'SBD')
                    or not product['strength_description']):
                raise EstimateHold('physical_price_unit_unresolved')
            quantity = decimal(med['quantity'], 10000)
            if not quantity or quantity != quantity.to_integral_value():
                raise EstimateHold('physical_quantity_unsupported')
            days = med['days_supply']
            if type(days) is not int or days not in (30, 90):
                raise EstimateHold('days_supply_unsupported')
            if not 1 <= len(med['fills']) <= 13:
                raise EstimateHold('unsupported_fill_count')
            price = one(self.rows('average_prices', refs, offering_id=plan['offering_id'],
                                  ndc=row['ndc'], days_supply=str(days)), 'published_average_unavailable')
            if price['disposition'] != 'published_average':
                raise EstimateHold('published_average_unavailable')
            fee_type = 'GENERIC' if product['type'] == 'SCD' else 'BRAND'
            fee = network.get(f'{fee_type}_DISPENSING_FEE_{days}')
            if fee in (None, '', '.'):
                raise EstimateHold('dispensing_fee_unresolved')
            if network.get('FLOOR_PRICE', '').strip() not in ('', '.', '0', '0.0', '0.0000'):
                raise EstimateHold('floor_price_rule_unresolved')
            amount = money(decimal(price['source_unit_cost'], 100000) * quantity + decimal(fee, 1000))
            matched = [s for s in schedules if s['DAYS_SUPPLY']['value'] == days
                       and (s['TIER']['value'] == int(row['TIER_LEVEL_VALUE'])
                            or benefit == 'DS' and s['TIER']['value'] is None)]
            schedule = one([s for s in matched if s['COVERAGE_LEVEL']['value'] == 1],
                           'cost_schedule_unresolved')
            kind = schedule[f'COST_TYPE_{suffix}']['value']
            if kind not in (1, 2):
                raise EstimateHold('supply_or_channel_not_offered')
            if schedule['TIER_SPECIALTY_YN']['value'] is not False:
                raise EstimateHold('specialty_tier_rule_unresolved')
            amount_share = decimal(schedule[f'COST_AMT_{suffix}']['value'], 1 if kind == 2 else 10000)
            minimum = money(decimal(schedule[f'COST_MIN_AMT_{suffix}']['value'], 10000))
            maximum = money(decimal(schedule[f'COST_MAX_AMT_{suffix}']['value'], 10000))
            if maximum and maximum < minimum:
                raise EstimateHold('cost_share_bounds_conflict')
            if kind == 1 and (minimum or maximum):
                raise EstimateHold('cost_share_bounds_unsupported')
            applies = schedule['DED_APPLIES_YN']['value']
            if type(applies) is not bool:
                raise EstimateHold('deductible_rule_unresolved')
            share_fields = [f'{field}_{suffix}' for field in (
                'COST_TYPE', 'COST_AMT', 'COST_MIN_AMT', 'COST_MAX_AMT')]
            for phase in matched:
                level = phase['COVERAGE_LEVEL']['value']
                if level == 0 and (applies or phase['DED_APPLIES_YN']['value'] is not False
                                   or any(phase[key]['value'] != schedule[key]['value']
                                          for key in share_fields)):
                    raise EstimateHold('pre_deductible_schedule_unresolved')
                if level == 3 and phase[share_fields[0]]['value'] in (1, 2) and any(
                        decimal(phase[key]['value'], 10000) for key in share_fields[1:]):
                    raise EstimateHold('catastrophic_schedule_conflict')
            previous = None
            for event in med['fills']:
                day = date.fromisoformat(event['date'])
                order = event['order']
                if (not start <= day <= date(2026, 12, 31) or type(order) is not int
                        or not 1 <= order <= 12 or (day, order) in order_keys
                        or previous is not None and (day - previous).days < days):
                    raise EstimateHold('fill_schedule_unresolved_or_unsupported')
                previous = day
                order_keys.add((day, order))
                fills.append(Fill(day, order, rxcui, amount, applies,
                                  money(amount_share) if kind == 1 else None,
                                  amount_share if kind == 2 else None, minimum, maximum))
        return fills

    def _revision(self, report, revision):
        payload = json.dumps([self.binding, PARAMETER_MANIFEST, METHOD, revision, report],
                             sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        return hmac.digest(self.receipt_key, payload, 'sha256').hex()

    def estimate(self, report, revision, *, purpose='offline_research', year=2026, county_fips='12021'):
        try:
            self._scope(purpose, year, county_fips)
            if type(revision) is not int or revision < 1:
                raise EstimateHold('report_revision_required')
            receipt = self._revision(report, revision)
            questions = missing(report)
            if questions:
                return {'state': 'missing_reports', 'missing': questions, 'revision': revision}
            refs, findings = [], {}
            try:
                estimate = self._inputs(report, refs, findings)
            except EstimateHold as error:
                estimate = {'hold': str(error)}
            self._scope(purpose, year, county_fips)
            # Deduplicate exact source locators without dropping any consulted evidence.
            source_keys = {json.dumps(ref, sort_keys=True): ref for ref in refs}
            return {'state': 'held' if 'hold' in estimate else 'offline_average_candidate',
                    **estimate, 'findings': findings, 'revision': revision, 'receipt': receipt,
                    'binding': self.binding, 'method': METHOD, 'parameter_manifest': PARAMETER_MANIFEST,
                    'sources': list(source_keys.values())}
        except (EstimateHold, ResearchServingError) as error:
            return {'state': 'held', 'hold': str(error)}
        except (AttributeError, IndexError, KeyError, TypeError, ValueError, OSError, InvalidOperation):
            return {'state': 'held', 'hold': 'input_or_bound_evidence_invalid'}

    def check_receipt(self, report, revision, receipt, *, purpose='offline_research',
                      year=2026, county_fips='12021'):
        """Call with the current authoritative report and revision, never a cached copy."""
        try:
            self._scope(purpose, year, county_fips)
            self._parameters()
            return isinstance(receipt, str) and hmac.compare_digest(
                receipt, self._revision(report, revision))
        except (ResearchServingError, ValueError, TypeError, OSError):
            return False
