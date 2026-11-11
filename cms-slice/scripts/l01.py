"""National L01 deterministic component evaluator and separate fail-closed gate.

Research is a Python/CLI operation only. HTTP never accepts a research flag.
No financial inputs are saved, logged, or sent to an AI by this module.
"""
import argparse
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re

from l01_acquire import PACKAGE, ROOT
from l01_build import digest

REGISTRY = ROOT / 'cms-slice/data-sources/l01-acceptance.json'
SCHEMA = 'l01-result/1'
RUNTIME_FILES = ('l01.py','l01_build.py','l01_acquire.py','l01_http.py','l01_validate.py','l01_runtime.py','l01_maintenance.py')
LOADED_RUNTIME_SHA256 = {name:hashlib.sha256((ROOT/'cms-slice/scripts'/name).read_bytes()).hexdigest() for name in RUNTIME_FILES}
STATES = {'value', 'unknown', 'unavailable', 'conflicting', 'expired', 'not_applicable', 'no_fixed_annual_cap'}
STATES_US = set('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC'.split())


class L01Error(ValueError):
    pass


class L01Held(L01Error):
    def __init__(self, message, state='unavailable'):
        super().__init__(message)
        self.state = state


def load(path):
    return json.loads(Path(path).read_text())


def utc(value):
    d = datetime.fromisoformat(value)
    if d.tzinfo is None:
        raise L01Held('Review timestamps require a timezone')
    return d.astimezone(timezone.utc)


def integer(value, name, minimum=0, maximum=10**16):
    if type(value) is not int or not minimum <= value <= maximum:
        raise L01Error('Invalid ' + name)
    return value


def value_cell(state, value_cents=None, **metadata):
    """Lossless typed monetary state; zero cannot stand for missing evidence."""
    if state not in STATES or (state != 'value' and value_cents is not None):
        raise L01Error('Invalid value-state envelope')
    if state == 'value':
        integer(value_cents, 'value cents')
    return {'state': state, 'value_cents': value_cents, **metadata}


def verify(package=PACKAGE, now=None):
    """Verify raw, extraction, inventory and code bindings before every operation."""
    package = Path(package)
    m = load(package / 'manifest.json')
    if (m['schema'] != 'l01-manifest/1' or type(m['year']) is not int or not 2000 <= m['year'] <= 2200
            or type(m['revision']) is not int or m['revision'] < 1
            or m['package_id'] != f'L01-US-{m["year"]}-r{m["revision"]}'):
        raise L01Held('Unsupported package identity')
    required = {'facts.json', 'bands.json', 'rules.json', 'inventory.json', 'requirements.json', 'sources.json', 'conflicts.json', 'observations.json', 'dependencies.json'}
    if not required <= {Path(f).name for f in m['files_sha256']}:
        raise L01Held('Required package file missing')
    if not set(RUNTIME_FILES) <= {Path(f).name for f in m['files_sha256']}:
        raise L01Held('Required runtime binding missing')
    for relative, sha in m['files_sha256'].items():
        recorded = Path(m['package_path'])
        rel = Path(relative)
        if rel.is_relative_to(recorded):
            path = (package / rel.relative_to(recorded)).resolve()
            safe = path.is_relative_to(package.resolve())
        else:
            path = (ROOT / relative).resolve()
            safe = path.is_relative_to(ROOT)
        if not safe or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise L01Held('Changed artifact or runtime binding')
        if rel.parent == Path('cms-slice/scripts') and rel.name in LOADED_RUNTIME_SHA256 and LOADED_RUNTIME_SHA256[rel.name] != sha:
            raise L01Held('Loaded runtime differs from package; restart required')
    # The loaded payloads must be the ones just verified, including relocated copies.
    for name in required:
        if str(Path(m['package_path']) / name) not in m['files_sha256']:
            raise L01Held('Consumed payload has no exact binding')
    for fact in load(package / 'facts.json') + load(package / 'bands.json'):
        if fact['version'] != f'{m["year"]}-r{m["revision"]}' or not fact['effective_from'].startswith(str(m['year'])):
            raise L01Held('Payload year/version does not match package')
    for source in load(package / 'sources.json'):
        if source.get('content_year_verified') is not None and source['content_year_verified'] != m['year']:
            raise L01Held('Raw evidence content year differs from selected package')
    # Freshness is not inferred from successful parsing or from runtime startup.
    if now is not None and now >= utc(m['source_review_after_utc']):
        raise L01Held('Source review expired; historical package preserved', 'expired')
    return m


class Acceptance:
    """Real reviewer receipts are supplied externally; this class never creates them."""
    def __init__(self, package=PACKAGE, registry=REGISTRY, now=None):
        self.package, self.registry = Path(package), Path(registry)
        self.now = now or (lambda: datetime.now(timezone.utc))

    def review(self, record, deadline):
        if record.get('review_after_utc') and self.now() >= utc(record['review_after_utc']):
            raise L01Held('Independent review expired', 'expired')
        if (record['decision'] != 'accepted' or record.get('revoked') is not False
                or not record['reviewer']['name'].strip()
                or record['reviewer']['role'] not in {'medicare_subject_matter_reviewer', 'ssa_rules_reviewer'}
                or record['reviewer']['independent_of_sales'] is not True
                or not record['receipt'].strip()
                or not utc(record['reviewed_at_utc']) <= self.now() < utc(record['review_after_utc']) <= deadline):
            raise L01Held('Independent scoped acceptance pending, expired or revoked')

    def require(self, capability, claim_ids=None):
        try:
            m = verify(self.package, self.now())
            r = load(self.registry)  # Reload: expiry and revocation take effect immediately.
            if (r['schema'] != 'l01-acceptance/1' or r['package_id'] != m['package_id']
                    or r['manifest_sha256'] != hashlib.sha256((self.package / 'manifest.json').read_bytes()).hexdigest()):
                raise L01Held('Acceptance does not bind this exact L01 package')
            deadline = utc(m['source_review_after_utc'])
            self.review(r['package_review'], deadline)
            deadline = min(deadline, utc(r['package_review']['review_after_utc']))
            requirements = load(self.package / 'requirements.json')
            binding = requirements['capabilities'][capability]
            sources = {s['id']: s for s in load(self.package / 'sources.json')}
            if any(sources[id]['status'] != 'acquired' for id in binding['sources']):
                raise L01Held('Required capability source missing')
            accepted = r['capabilities'][capability]
            self.review(accepted, deadline)
            if accepted['binding_sha256'] != digest(binding) or accepted['output_schema'] != SCHEMA:
                raise L01Held('Capability output binding changed')
            facts = {f['id']: f for f in load(self.package / 'facts.json') + load(self.package / 'bands.json')}
            rules = {f['id']: f for f in load(self.package / 'rules.json')}
            ids = binding['facts'] + binding.get('band_ids', []) if claim_ids is None else claim_ids
            if not set(ids) <= set(binding['facts'] + binding.get('band_ids', [])):
                raise L01Held('Output claim outside accepted capability')
            for id, record in [(id, facts[id]) for id in ids] + [(id, rules[id]) for id in binding['rules']]:
                receipt = r['claims'][id]
                self.review(receipt, min(deadline, utc(accepted['review_after_utc'])))
                if receipt['claim_sha256'] != digest(record) or receipt['conditions_reviewed'] is not True:
                    raise L01Held('Claim or conditions not accepted')
                for conflict in record.get('conflict_ids', []):
                    c = next(c for c in load(self.package / 'conflicts.json') if c['id'] == conflict)
                    resolution = r['conflicts'][conflict]
                    self.review(resolution, deadline)
                    if resolution['conflict_sha256'] != digest(c) or not resolution['canonical_disposition'].strip():
                        raise L01Held('Conflict has no exact reviewed disposition')
            return m
        except L01Held:
            raise
        except (OSError, KeyError, ValueError, TypeError, AttributeError, StopIteration) as e:
            raise L01Held('L01 consumer output held: exact independent acceptance required') from e

    def status(self):
        try:
            verify(self.package,self.now())
            integrity='passed'
        except L01Held as error:
            integrity=error.state
        except (OSError,KeyError,ValueError,TypeError,AttributeError):
            integrity='unavailable'
        capabilities = {}
        for c in load(self.package / 'requirements.json')['capabilities']:
            try:
                self.require(c)
                capabilities[c] = 'accepted_current'
            except L01Held:
                capabilities[c] = 'held'
        m = load(self.package / 'manifest.json')
        return {'package_id': m['package_id'], 'year': m['year'], 'capabilities': capabilities,
                'manifest_sha256':hashlib.sha256((self.package/'manifest.json').read_bytes()).hexdigest(),
                'loaded_runtime_sha256':LOADED_RUNTIME_SHA256,'runtime_integrity':integrity,
                'consumer_ready': any(s == 'accepted_current' for s in capabilities.values()),
                'personal_total_available': False, 'recommendations_available': False,
                'broader_L01_status': 'partial', 'financial_input_storage': False}


class L01:
    def __init__(self, package=PACKAGE, gate=None, now=None):
        self.package = Path(package)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.gate = gate or Acceptance(package, now=self.now)

    def evaluate(self, request):
        """The sole consumer operation; schema and request cannot bypass acceptance."""
        result = self.research(request)
        capability = request['operation']
        if capability == 'personal_total':
            raise L01Held('Personal total costs require other accepted layers and personal facts')
        self.gate.require(capability, result['claim_ids'])
        if result['state'] == 'conflicting':
            # Resolution receipts accept a proposed canonical interpretation without
            # erasing the original disagreement. Re-evaluate only under that receipt.
            result = self.research(request, resolved_conflicts=set(load(self.gate.registry).get('conflicts', {})))
        result['mode'] = 'accepted_component'
        return result

    def research(self, request, *, resolved_conflicts=frozenset()):
        try:
            m = verify(self.package, self.now())
        except L01Held:
            raise
        except (OSError, KeyError, TypeError, ValueError, AttributeError) as error:
            raise L01Held('Package unavailable or malformed') from error
        year = m['year']
        if not isinstance(request, dict):
            raise L01Error('Use a typed request object')
        common = {'operation', 'year', 'month', 'state', 'county_fips'}
        fields = {
            'published_standard': set(),
            'published_cost_lookup': {'fact_ids','band_ids'},
            'premiums': {'covered_months', 'coverage_context', 'a_category'},
            'irmaa': {'covered_months', 'coverage_context', 'filing_status', 'magi_cents', 'magi_range_cents', 'tax_year', 'return_basis', 'lived_together', 'changed_income', 'amended_return', 'billed_amount_cents'},
            'hospital_stay': {'first_day', 'days', 'benefit_period_start', 'deductible_satisfied', 'reserve_remaining', 'use_reserve', 'coverage_confirmed', 'benefit_period_id', 'service_start_date'},
            'snf_stay': {'first_day', 'days', 'coverage_confirmed', 'benefit_period_id', 'service_start_date'},
            'ordinary_b': {'approved_charge_cents', 'deductible_remaining_cents', 'ordinary_rule_confirmed'},
            'benefit_reset': {'days_out', 'inpatient_definition_confirmed'},
            'personal_total': set(),
        }
        op = request.get('operation')
        if op not in fields or set(request) - (common | fields[op]):
            raise L01Error('Unknown operation or unreviewed input field')
        facts = {f['id']: f for f in load(self.package / 'facts.json')}
        bands = load(self.package / 'bands.json')
        rules = load(self.package / 'rules.json')
        result = {'schema': SCHEMA, 'package_id': m['package_id'], 'mode': 'research_unaccepted', 'state': 'value',
                  'year': request.get('year'), 'requested_month': request.get('month'), 'claim_ids': [], 'rule_versions': [],
                  'components': [], 'steps': [], 'assumptions': [], 'evidence': [], 'missing_inputs': [],
                  'external_dependencies': load(self.package / 'dependencies.json'), 'conflicts': [],
                  'unavailable_capabilities': ['personal_total', 'plan_recommendation'], 'reported_inputs_are_verified': False}

        def missing(*names):
            result['state'] = 'unknown'
            result['missing_inputs'].extend(names)
            return result

        if type(request.get('year')) is not int or request['year'] != m['year']:
            result.update(state='unavailable', reason='No year-correct package; no rollover substitution')
            return result
        if request.get('state') not in STATES_US:
            result.update(state='unavailable', reason='Jurisdiction not supported: US 50 states/DC only; territories and exceptional populations require reviewed applicability')
            return result
        month = request.get('month')
        if type(month) is not int or not 1 <= month <= 12:
            return missing('requested month (1–12)')
        if request.get('county_fips') is not None and not re.fullmatch(r'\d{5}', str(request['county_fips'])):
            raise L01Error('Invalid county FIPS')
        # County never changes a federal amount; exceptional populations remain outside scope.
        def use(ids, rule_ids=()):
            result['claim_ids'] = list(dict.fromkeys(result['claim_ids'] + list(ids)))
            result['rule_versions'] = [{'id': id, 'version': next(r['version'] for r in rules if r['id'] == id)} for id in rule_ids]
            selected = [facts[id] if id in facts else next(b for b in bands if b['id'] == id) for id in ids]
            obsids = {x for f in selected for x in f['observation_ids']}
            result['evidence'] = [o for o in load(self.package / 'observations.json') if o['id'] in obsids]
            result['rule_evidence'] = [{'rule_id': id, 'source_sections': next(r['source_sections'] for r in rules if r['id'] == id)} for id in rule_ids]
            result['conflicts'] = sorted({c for f in selected for c in f.get('conflict_ids', [])} - set(resolved_conflicts))
            if result['conflicts']:
                result['state'] = 'conflicting'
            return not result['conflicts']

        def component(id, amount, period, **kw):
            result['components'].append(value_cell('value', amount, id=id, currency='USD', period=period, **kw))

        def months():
            values = request.get('covered_months')
            if not isinstance(values, list) or not values:
                return None
            if len(values) != len(set(str(x) for x in values)) or len(values) > 12:
                raise L01Error('Covered months must be unique and at most twelve')
            for value in values:
                if not isinstance(value, str) or not re.fullmatch(str(year) + r'-(0[1-9]|1[0-2])', value):
                    raise L01Error('Covered month outside package year')
            if f'{year}-{month:02d}' not in values:
                raise L01Error('Requested month must be among covered months')
            return sorted(values)

        if op == 'personal_total':
            result.update(state='unavailable', reason='Supported federal components cannot establish personal total cost; dependencies remain unresolved')
            return result
        if op == 'published_standard':
            # Inspectable raw research facts, withheld entirely by the HTTP gate.
            selected = [f for f in facts.values() if f['coverage_context'] in {'part_a','full_b','immuno_b'}]
            use([f['id'] for f in selected])
            result['facts'] = selected
            return result
        if op == 'published_cost_lookup':
            ids = request.get('fact_ids',[])
            band_ids = request.get('band_ids',[])
            available_bands={b['id']:b for b in bands}
            for chosen,available in [(ids,facts),(band_ids,available_bands)]:
                if not isinstance(chosen,list) or len(chosen)>len(available) or any(not isinstance(id,str) or id not in available for id in chosen) or len(chosen)!=len(set(chosen)):
                    raise L01Error('Choose explicit known fact/band IDs')
            if not ids and not band_ids:raise L01Error('Choose a published fact or band; no personal income intake required')
            use(ids+band_ids)
            result['facts']=[facts[id] for id in ids]
            result['bands']=[available_bands[id] for id in band_ids]
            return result
        if op in {'premiums', 'irmaa'}:
            covered = months()
            if covered is None:
                return missing('explicit covered_months')
            context = request.get('coverage_context')
            if context not in {'full_b', 'immuno_b', 'part_d'}:
                return missing('coverage_context')
            if op == 'premiums':
                if context == 'part_d':
                    result.update(state='unavailable', reason='Part D plan premium belongs to plan layer; use IRMAA for federal adjustment')
                    return result
                id = 'b_premium' if context == 'full_b' else 'immuno_premium'
                ids = [id]
                a = request.get('a_category')
                if a is not None and a not in {'premium_free_reported', 'reduced_reported', 'full_reported'}:
                    return missing('explicit reported A premium category; entitlement not inferred')
                if a and context == 'immuno_b':
                    result.update(state='unavailable', reason='Immunosuppressive-only context is not full A/B coverage')
                    return result
                if a in {'reduced_reported', 'full_reported'}:
                    ids.append('a_premium_reduced' if a == 'reduced_reported' else 'a_premium_full')
                use(ids, ['premium_months'])
                for f in ids:
                    component(f, facts[f]['value'] * len(covered), 'explicit_covered_months', monthly_cents=facts[f]['value'], covered_months=covered)
                if a == 'premium_free_reported':
                    component('a_premium_reported', 0, 'explicit_covered_months', status_basis='user_report_not_entitlement_determination')
                result['steps'] = [{'operation': 'multiply', 'monthly_cents': facts[f]['value'], 'covered_month_count': len(covered), 'subtotal_cents': facts[f]['value'] * len(covered)} for f in ids]
                result['assumptions'] = ['Published base components only; IRMAA, protection, assistance, plan givebacks and penalties not included', 'A category, if supplied, is a reported scenario condition']
                return result
            required = ['filing_status', 'tax_year', 'return_basis']
            absent = [f for f in required if request.get(f) is None]
            if request.get('magi_cents') is None and request.get('magi_range_cents') is None:absent.append('magi_cents or a sufficient income range')
            if absent:
                return missing(*absent)
            if request.get('magi_cents') is not None and request.get('magi_range_cents') is not None:
                raise L01Error('Use one income representation')
            if request.get('magi_cents') is not None:
                income=integer(request['magi_cents'],'MAGI cents',minimum=-10**16)
                income_range={'lower_cents':income,'upper_cents':income,'lower_inclusive':True,'upper_inclusive':True}
            else:
                income_range=request['magi_range_cents']
                if not isinstance(income_range,dict) or set(income_range)!={'lower_cents','upper_cents','lower_inclusive','upper_inclusive'}:
                    raise L01Error('Use explicit income-range bounds and inclusivity')
                for key in ['lower_cents','upper_cents']:
                    if income_range[key] is not None:integer(income_range[key],key,minimum=-10**16)
                if any(type(income_range[k]) is not bool for k in ['lower_inclusive','upper_inclusive']):raise L01Error('Income-range inclusivity must be explicit')
                lo,hi=income_range['lower_cents'],income_range['upper_cents']
                if lo is not None and hi is not None and (lo>hi or (lo==hi and not (income_range['lower_inclusive'] and income_range['upper_inclusive']))):raise L01Error('Empty or reversed income range')
            basis = request['return_basis']
            tax = m['tax_return_basis']
            if not ((request['tax_year'] == tax['normal_year'] and basis == tax['normal_basis']) or (request['tax_year'] == tax['fallback_year'] and basis == tax['fallback_basis'])):
                return missing('year-correct confirmed tax-return basis or official determination')
            for flag in ['changed_income', 'amended_return']:
                if type(request.get(flag)) is not bool:
                    return missing(flag)
                if request[flag]:
                    result.update(state='unavailable', reason='New initial determination/appeal route; do not replace the tax basis automatically')
                    return result
            filing = request['filing_status']
            if filing == 'separate_together' and request.get('lived_together') is not True:
                return missing('consistent explicit lived_together condition')
            if filing == 'married_separate':
                if type(request.get('lived_together')) is not bool:
                    return missing('lived_together during tax year')
                if not request['lived_together']:
                    result.update(state='unavailable', reason='Lived apart all year requires SSA new-determination route; no operational assumption is a user fact')
                    return result
                filing = 'separate_together'
            if filing not in {'individual', 'joint', 'separate_together'}:
                return missing('supported filing_status')
            def contains(b):
                lo,hi=income_range['lower_cents'],income_range['upper_cents']
                lower=b['lower_cents'] is None or (lo is not None and (lo>b['lower_cents'] or (lo==b['lower_cents'] and (b['lower_inclusive'] or not income_range['lower_inclusive']))))
                upper=b['upper_cents'] is None or (hi is not None and (hi<b['upper_cents'] or (hi==b['upper_cents'] and (b['upper_inclusive'] or not income_range['upper_inclusive']))))
                return lower and upper
            candidates = [b for b in bands if b['filing_status'] == filing and b['coverage_context'] == context and contains(b)]
            if len(candidates) != 1:
                result.update(state='unknown', reason='Income range does not identify one band; a narrower published range is sufficient, exact income is optional')
                result['missing_inputs'].append('single-band income range')
                return result
            band = candidates[0]
            if not use([band['id']], ['irmaa', 'premium_months']):
                result['reason'] = 'Conflicting source evidence; proposed canonical band retained in research package but dependent amount withheld'
                return result
            monthly = band['adjustment_cents'] if context == 'part_d' else band['published_total_cents']
            component(context, monthly * len(covered), 'explicit_covered_months', monthly_cents=monthly, covered_months=covered,
                      federal_adjustment_cents=band['adjustment_cents'], base_cents=band['base_cents'])
            result['steps'] = [{'operation': 'select_explicit_income_band', 'band_id': band['id']}, {'operation': 'multiply_published_total_once' if context != 'part_d' else 'multiply_adjustment_once', 'monthly_cents': monthly, 'covered_month_count': len(covered)}]
            result['assumptions'] = ['Conditional published scenario; not an official SSA premium determination', 'Part D adjustment excludes plan premium; B total already includes B adjustment']
            if 'billed_amount_cents' in request:
                result['reported_billed_amount'] = {'state': 'reported', 'value_cents': integer(request['billed_amount_cents'], 'reported billed amount'), 'verified': False}
            return result
        if op == 'benefit_reset':
            if request.get('inpatient_definition_confirmed') is not True:
                return missing('rule-specific inpatient definition confirmed')
            days = integer(request.get('days_out'), 'days outside qualifying inpatient status', maximum=100000)
            use([], ['benefit_reset'])
            result['benefit_period_ended'] = days >= 60
            result['steps'] = [{'rule': '60 consecutive qualifying days', 'days_out': days}]
            result['assumptions'] = ['Conditional scenario; no eligibility determination; new diagnosis/January 1 is not a reset']
            return result
        if op in {'hospital_stay', 'snf_stay'}:
            if request.get('coverage_confirmed') is not True:
                return missing('covered qualifying inpatient/SNF services confirmed for scenario')
            absent = [x for x in ['first_day', 'days', 'benefit_period_id', 'service_start_date'] if request.get(x) is None]
            if absent:
                return missing(*absent)
            first = integer(request['first_day'], 'first cumulative covered day', 1, 100000)
            days = integer(request['days'], 'covered days', 1, 10000)
            try:
                service_start = date.fromisoformat(request['service_start_date'])
            except (ValueError, TypeError):
                raise L01Error('Invalid service start date') from None
            if service_start.year != year or service_start.month != month:
                raise L01Error('Service start must match requested month and package year')
            if (service_start + timedelta(days=days - 1)).year != year:
                result.update(state='unavailable', reason='Service interval crosses package year; split by actual service dates with each year-correct package')
                return result
            if not isinstance(request['benefit_period_id'], str) or not 1 <= len(request['benefit_period_id']) <= 80:
                raise L01Error('Explicit benefit period reference required')
            if op == 'snf_stay':
                use(['snf_21_100'], ['snf'])
                paid_days = sum(21 <= d <= 100 for d in range(first, first + days))
                uncovered = sum(d > 100 for d in range(first, first + days))
                component('snf_coinsurance', paid_days * facts['snf_21_100']['value'], 'covered_day', chargeable_days=paid_days)
            else:
                needed = ['benefit_period_start', 'deductible_satisfied', 'reserve_remaining', 'use_reserve']
                absent = [x for x in needed if request.get(x) is None]
                if absent:
                    return missing(*absent)
                try:
                    start = date.fromisoformat(request['benefit_period_start'])
                except (ValueError, TypeError):
                    raise L01Error('Invalid benefit period start') from None
                if start > service_start:
                    raise L01Error('Benefit period starts after service start')
                for flag in ['deductible_satisfied', 'use_reserve']:
                    if type(request[flag]) is not bool:
                        raise L01Error('Explicit boolean required: ' + flag)
                reserve = integer(request['reserve_remaining'], 'remaining lifetime reserve', 0, 60)
                if start.year != year and not request['deductible_satisfied']:
                    result.update(state='unavailable', reason='Unpaid deductible needs benefit-period starting-year package; no cross-year substitution')
                    return result
                ids = ['hospital_61_90', 'hospital_reserve'] + ([] if request['deductible_satisfied'] else ['a_deductible'])
                if not use(ids, ['hospital']):
                    return result
                ordinary = sum(61 <= d <= 90 for d in range(first, first + days))
                later = sum(d > 90 for d in range(first, first + days))
                used = min(later, reserve) if request['use_reserve'] else 0
                uncovered = later - used
                component('hospital_coinsurance', ordinary * facts['hospital_61_90']['value'] + used * facts['hospital_reserve']['value'], 'covered_day', ordinary_days=ordinary, reserve_days=used)
                if not request['deductible_satisfied']:
                    component('hospital_deductible', facts['a_deductible']['value'], 'benefit_period')
                result['reserve_remaining_after'] = reserve - used
            if uncovered:
                result['state'] = 'unknown'
                result['components'].append({'id': 'beyond_covered_days', 'state': 'unavailable', 'days': uncovered, 'value_cents': None, 'period': 'service', 'reason': 'Actual uncovered charges required'})
            result['steps'] = [{'operation': 'count_cumulative_days_in_explicit_benefit_period', 'first_day': first, 'day_count': days}]
            result['assumptions'] = ['Federal component scenario only; no supplemental/assistance/physician/actual uncovered charges included', 'Coverage and prior-use inputs are reported scenario conditions, not source verification']
            return result
        if op == 'ordinary_b':
            if request.get('ordinary_rule_confirmed') is not True:
                return missing('ordinary B rule applicability confirmed; exception service cannot use universal 20%')
            if request.get('approved_charge_cents') is None or request.get('deductible_remaining_cents') is None:
                return missing('Medicare-approved charge and remaining annual deductible')
            charge = integer(request['approved_charge_cents'], 'Medicare-approved charge')
            remaining = integer(request['deductible_remaining_cents'], 'remaining annual deductible', 0, facts['b_deductible']['value'])
            use(['b_deductible', 'b_coinsurance'], ['ordinary_b'])
            deductible = min(charge, remaining)
            rate = facts['b_coinsurance']['value']
            numerator = integer(rate['numerator'], 'rate numerator')
            denominator = integer(rate['denominator'], 'rate denominator', 1)
            if numerator > denominator or facts['b_coinsurance']['unit'] != 'fraction_of_Medicare_approved_amount':
                raise L01Held('Invalid charge-basis rate')
            coinsurance = int((Decimal(charge - deductible) * Decimal(numerator) / Decimal(denominator)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            component('ordinary_b_component', deductible + coinsurance, 'service', deductible_cents=deductible, coinsurance_cents=coinsurance)
            result['steps'] = [{'operation': 'apply_remaining_deductible', 'cents': deductible}, {'operation': 'apply_typed_coinsurance_to_remaining_approved_amount', 'rate': rate, 'cents': coinsurance, 'rounding': 'nearest cent, half up; research scenario'}]
            result['assumptions'] = ['Excludes excess charges, facility fees, other services, assistance and supplemental payments; not an exact personal bill']
            return result
        raise L01Error('Operation not implemented')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['status', 'research'])
    p.add_argument('--input', type=Path, help='Synthetic/local JSON request; no durable financial storage is created')
    p.add_argument('--as-of', help='Historical research replay clock only; never accepted by HTTP')
    a = p.parse_args()
    if a.as_of and a.action != 'research':
        p.error('--as-of is research replay only')
    now = (lambda: utc(a.as_of)) if a.as_of else None
    print(json.dumps(Acceptance().status() if a.action == 'status' else L01(now=now).research(load(a.input)), indent=2))
