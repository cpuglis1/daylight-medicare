"""Owner/current-report identity preparation over frozen research dependencies.

All choices are RAM-only. Default consumer output is held. An explicitly injected
internal-research purpose may inspect source candidates under the existing exact
source-composition allowance; it grants no consumer, clinical or plan authority.
No profile backfill, persistence, model context or external acquisition occurs.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
import copy
import hashlib
import json
import re
import secrets
import threading
import time

from comparison_evidence import canonical_sha256
from comparison_methods import (IdentityBinding, RequiredInput, assess_identity_binding,
                                assess_required_inputs, _current_refs)
from identity_resolution import DrugIdentityChoices, IdentityResolutionError


VERSION = 'advisor-identity-journey-20261102-r1'
IDENTITY_SCOPE = {'year': 2026, 'category': 'identity_preparation'}
HELD_PURPOSES = ('published_display', 'personal_comparison', 'ranking', 'recommendation', 'quote', 'enrollment')
POLICY_PATH = 'infrastructure/daylight-data/config/source-composition.2026.json'
ALLOWANCES = {
    'L05': 'Drug name/strength/form identity confirmation candidates from the retained CMS/NLM dictionary, subject to trusted matching/explicit confirmation rather than fuzzy auto-binding.',
    'L08': 'Internal source-qualified provider/site candidate search with distinct exact-plan positive evidence, named-network evidence, family-only observation and unresolved state',
}
TOKEN = re.compile(r'[a-f0-9]{64}\Z')
ITEM = re.compile(r'(?:medicine|doctor)-(?:extra-)?[0-9]{1,3}\Z')


class IdentityJourneyError(ValueError):
    """Only fixed codes, never submitted/source/exception values."""


@dataclass(frozen=True)
class IdentityPurposeContract:
    repository_root: Path
    policy_sha256: str
    internal_research: bool = False

    @classmethod
    def load(cls, repository_root, *, internal_research=False):
        root = Path(repository_root).resolve()
        data = (root / POLICY_PATH).read_bytes()
        policy = json.loads(data)
        layers = {layer['layer_id']: layer for layer in policy['layers']}
        if (type(internal_research) is not bool or policy.get('reference_year') != 2026
                or policy.get('consumer_release_enabled') is not False
                or any(text not in layers[layer]['allowed_outputs'] for layer, text in ALLOWANCES.items())):
            raise IdentityJourneyError('IDENTITY_SOURCE_PURPOSE_UNAVAILABLE')
        return cls(root, hashlib.sha256(data).hexdigest(), internal_research)

    def current(self):
        try:
            return hashlib.sha256((self.repository_root / POLICY_PATH).read_bytes()).hexdigest() == self.policy_sha256
        except OSError:
            return False

    def public(self):
        valid = self.current()
        internal = self.internal_research and valid
        return {'state': 'internal_research_available' if internal else 'held',
            'audience': 'internal_research' if self.internal_research else 'consumer',
            'consumer_identity_preparation': 'held', 'consumer_release': False,
            'source_purpose': 'source_qualified_identity_candidate_inspection' if internal else None,
            'policy_ref': {'path': POLICY_PATH, 'sha256': self.policy_sha256},
            'reason_codes': ['CONSUMER_IDENTITY_SOURCE_PURPOSE_NOT_ACCEPTED']
                + ([] if valid else ['IDENTITY_SOURCE_PURPOSE_CHANGED']),
            'new_source_permission': False, 'new_ai_permission': False}


def _hash(value):
    return canonical_sha256(value)


def _positive(fact, subject):
    return (fact['ref']['subject_id'] == subject and fact['ref']['scope'] == 'current'
            and fact.get('capture_subject') == 'beneficiary'
            and fact.get('usable_for_bound_subject') is True and fact.get('usable_as_report') is True
            and fact.get('report_state') == 'reported'
            and isinstance(fact.get('value'), str) and bool(fact['value'].strip())
            and fact.get('capture_method') != 'location_reference')


def _item(profile, kind, item_id):
    assess_required_inputs(profile, [], finding_id='identity-journey-profile-validation')
    if (profile.get('requested_scope') != IDENTITY_SCOPE or not isinstance(item_id, str)
            or not ITEM.fullmatch(item_id) or kind not in {'drug_product', 'provider_site'}
            or not item_id.startswith('medicine-' if kind == 'drug_product' else 'doctor-')):
        raise IdentityJourneyError('EXACT_CURRENT_IDENTITY_ITEM_REQUIRED')
    question = 'RC22' if kind == 'drug_product' else 'RC21'
    prefix = 'readiness.facts.' + question + '.value.items[].'
    rows = [copy.deepcopy(f) for f in profile['facts']
            if f['ref']['path'].startswith(prefix) and f['ref']['item_id'] == item_id]
    if not rows:
        raise IdentityJourneyError('EXACT_CURRENT_IDENTITY_ITEM_REQUIRED')
    subject = profile['profile_binding']['subject_id']
    values = {f['ref']['path'][len(prefix):]: f['value'] for f in rows if _positive(f, subject)}
    leaf = 'name' if kind == 'drug_product' else 'practice'
    requirements = [RequiredInput(prefix + leaf, item_id)]
    assessment = assess_required_inputs(profile, requirements, finding_id='identity-discovery-item')
    refs = [copy.deepcopy(f['ref']) for f in rows if _positive(f, subject)]
    fingerprint_rows = copy.deepcopy(rows)
    for row in fingerprint_rows:
        row['ref'].pop('record_revision', None)
    return {'kind': kind, 'item_id': item_id, 'subject_id': subject,
        'subject_role': profile['profile_binding'].get('subject_role'),
        'profile_contract': profile.get('contract', {}).get('content_sha256'),
        'fingerprint': _hash(fingerprint_rows), 'values': values, 'refs': refs,
        'ready': assessment['input_state'] == 'sufficient_report',
        'input_state': assessment['input_state']}


def _source(value, contract):
    if (not isinstance(value, dict) or value.get('contract_id') != contract
            or value.get('operator_only') is not True or value.get('consumer_release') is not False
            or value.get('automatic_profile_binding') is not False
            or value.get('clinical_substitution', False) is not False
            or value.get('personal_recommendation_available', False) is not False
            or not isinstance(value.get('binding'), dict)
            or not isinstance(value['binding'].get('snapshot_id'), str)
            or value['binding'].get('accepted_release_id') is not None
            or not isinstance(value.get('source_access_states'), list)
            or any(not isinstance(row, dict) or row.get('state') != 'permitted'
                   for row in value['source_access_states'])
            or value.get('source_access_registration', {}).get('absence_is_permission') is not False
            or any(value.get('authority', {}).get(purpose, {}).get('state') != 'held'
                   for purpose in HELD_PURPOSES)):
        raise IdentityJourneyError('IDENTITY_SOURCE_HELD_STOPPED_OR_CHANGED')
    return value


def _drug_label(candidate, selectable):
    return {'candidate_id': candidate['candidate_id'], 'kind': 'drug_product',
        'label': candidate['identity']['drug_name'],
        'details': {key: copy.deepcopy(candidate['identity'].get(key)) for key in
                    ('rxcui', 'ingredient_strength_description', 'dose_form', 'concept_type')},
        'details_state': candidate['identity_detail_state'], 'identity_grain': candidate['identity_grain'],
        'selectable': selectable and candidate['identity_grain'] == 'drug_product_concept'
            and candidate['identity_detail_state'] == 'source_details_present',
        'reason_codes': copy.deepcopy(candidate.get('reason_codes', []))}


def _provider_ready(source, candidate):
    records = {row['record_ref']: row for key in ('entity_candidates', 'role_observations', 'location_observations')
               for row in source.get(key, [])}
    locators = {row['observation_id']: row for row in source.get('source_observation_locators', [])}
    sources = {row['source_native_fields']['id'] for row in source.get('sources', [])}
    if (candidate.get('actor_resolution_state') != 'explicit_source_actor_entity'
            or candidate.get('source_identity_conflict_refs')
            or candidate.get('output_authority') != 'held'
            or candidate.get('automatic_profile_binding') is not False):
        return False
    for ref in (candidate.get('entity_ref'), candidate.get('role_ref'), candidate.get('location_ref')):
        record = records.get(ref)
        if (record is None or record.get('output_authority') != 'held'
                or record.get('states', {}).get('source_use_state') != 'existing_source_policy_applies'
                or record.get('snapshot_source_use_state') != 'not_newly_reviewed'):
            return False
        locator = locators.get(record['source_native_fields'].get('observation_id'))
        if (not locator or locator.get('raw_parent_verified') is not True
                or locator.get('projected_locator_values_verified') is not True
                or ref not in locator.get('primary_record_refs', [])
                or not locator.get('pointer') or locator.get('source_id') not in sources):
            return False
    return True


def _provider_records_allowed(records):
    return all(isinstance(row, dict) and row.get('output_authority') == 'held'
        and row.get('states', {}).get('source_use_state') == 'existing_source_policy_applies'
        and row.get('snapshot_source_use_state') == 'not_newly_reviewed' for row in records)


def _search_basis(source):
    request = source.get('requested', {})
    return {key: copy.deepcopy(request.get(key, [])) for key in
            ('literal_tokens', 'leading_title_omitted_for_discovery_only')}


def _provider_label(source, candidate):
    return {'candidate_id': candidate['candidate_id'], 'kind': 'provider_site',
        'label': copy.deepcopy(candidate.get('source_name')),
        'site': copy.deepcopy(candidate.get('source_location')),
        'entity_type': candidate.get('entity_type'), 'relation_basis': candidate.get('relation_basis'),
        'actor_resolution_state': candidate.get('actor_resolution_state'),
        'details_state': candidate.get('identity_state'),
        'selectable': _provider_ready(source, candidate),
        'reason_codes': [] if _provider_ready(source, candidate) else ['SOURCE_ACTOR_SITE_OR_LINEAGE_UNRESOLVED']}


class IdentityJourney:
    def __init__(self, drug_discovery=None, drug_exact=None, provider_repository=None, *,
                 provider_discovery=None, purpose=None, clock=time.monotonic, ttl_seconds=600, max_offers=32):
        if (purpose is not None and type(purpose) is not IdentityPurposeContract
                or type(ttl_seconds) not in {int, float} or not 0 < ttl_seconds <= 1800
                or type(max_offers) is not int or not 1 <= max_offers <= 128):
            raise IdentityJourneyError('IDENTITY_JOURNEY_CONFIGURATION')
        self.discovery, self.provider, self.purpose = drug_discovery, provider_repository, purpose
        self.drug_exact, self.provider_discovery = drug_exact, provider_discovery
        self.clock, self.ttl_seconds, self.max_offers = clock, ttl_seconds, max_offers
        self._offers, self._selected, self._drug_services, self._epochs, self._lock = {}, {}, {}, {}, threading.RLock()

    def capability(self):
        return self.purpose.public() if self.purpose else {
            'state': 'held', 'audience': 'consumer', 'consumer_identity_preparation': 'held',
            'consumer_release': False, 'source_purpose': None,
            'reason_codes': ['CONSUMER_IDENTITY_SOURCE_PURPOSE_NOT_ACCEPTED'],
            'new_source_permission': False, 'new_ai_permission': False}

    def _owner(self, owner):
        if not isinstance(owner, str) or not 16 <= len(owner) <= 128:
            raise IdentityJourneyError('BOUND_IDENTITY_OWNER_REQUIRED')

    def _prune(self):
        now = self.clock()
        self._offers = {key: value for key, value in self._offers.items() if value['expires'] > now}
        self._selected = {key: value for key, value in self._selected.items() if value['expires'] > now}
        self._drug_services = {key: value for key, value in self._drug_services.items() if key in self._offers}
        self._epochs = {key: value for key, value in self._epochs.items() if value[1] > now}

    def _epoch(self, owner):
        with self._lock:
            self._prune()
            if owner not in self._epochs:
                if len(self._epochs) >= 128:
                    raise IdentityJourneyError('IDENTITY_JOURNEY_CAPACITY')
                self._epochs[owner] = (0, self.clock() + self.ttl_seconds)
            return self._epochs[owner][0]

    def _base(self, **values):
        return {'contract_id': VERSION, 'capability': self.capability(), 'candidates': [],
            'held_purposes': list(HELD_PURPOSES), 'personal_output_state': 'held',
            'consumer_release': False, 'profile_reports_changed': False,
            'ai_context_changed': False, 'saved': False, **values}

    def _enabled(self, kind):
        return (self.capability()['state'] == 'internal_research_available'
                and (self.discovery is not None and self.drug_exact is not None if kind == 'drug_product'
                     else self.provider is not None))

    def _same(self, profile, offer):
        current = _item(profile, offer['kind'], offer['item_id'])
        if (current['fingerprint'] != offer['inputs']['fingerprint']
                or current['subject_id'] != offer['inputs']['subject_id']
                or current['subject_role'] != offer['inputs']['subject_role']
                or current['profile_contract'] != offer['inputs']['profile_contract']
                or not _current_refs(profile, offer['inputs']['refs'], current['subject_id'],
                                     item_id=offer['item_id'])):
            raise IdentityJourneyError('IDENTITY_ITEM_REPORT_CHANGED')
        return current

    def _offer(self, owner, inputs, source, candidates, *, query, drug_token=None, drug_service=None,
               page=None, stage='site_or_product', expected_epoch=None):
        with self._lock:
            self._prune()
            if self._epochs.get(owner, (None,))[0] != expected_epoch:
                raise IdentityJourneyError('IDENTITY_REQUEST_REVOKED_OR_EXPIRED')
            if not self._enabled(inputs['kind']):
                raise IdentityJourneyError('IDENTITY_SOURCE_PURPOSE_CHANGED')
            ids = [row.get('candidate_id') for row in candidates]
            if (any(not isinstance(value, str) or not 1 <= len(value) <= 512 for value in ids)
                    or len(set(ids)) != len(ids)):
                raise IdentityJourneyError('IDENTITY_SOURCE_SHAPE_INVALID')
            selected_tokens = {value['offer_token'] for value in self._selected.values()}
            previous = [key for key, value in self._offers.items() if value['owner'] == owner
                        and value['item_id'] == inputs['item_id'] and value['kind'] == inputs['kind']
                        and key not in selected_tokens]
            for key in previous:
                self._offers.pop(key, None)
                self._drug_services.pop(key, None)
            if len(self._offers) >= self.max_offers or sum(v['owner'] == owner for v in self._offers.values()) >= 8:
                raise IdentityJourneyError('IDENTITY_JOURNEY_CAPACITY')
            token = secrets.token_hex(32)
            self._offers[token] = {'owner': owner, 'kind': inputs['kind'], 'item_id': inputs['item_id'],
                'inputs': copy.deepcopy(inputs), 'source': copy.deepcopy(source),
                'candidates': {row['candidate_id']: copy.deepcopy(row) for row in candidates},
                'query': copy.deepcopy(query), 'drug_token': drug_token,
                'expires': self.clock() + self.ttl_seconds, 'page': copy.deepcopy(page), 'stage': stage}
            if drug_service is not None:
                self._drug_services[token] = drug_service
            return token

    def drug_search(self, owner, profile, *, item_id, after_ordinal=0,
                    expected_snapshot_id=None, choice_token=None):
        self._owner(owner)
        inputs = _item(profile, 'drug_product', item_id)
        if not self._enabled('drug_product'):
            return self._base(state='held', item_id=item_id, kind='drug_product')
        if not inputs['ready']:
            return self._base(state='current_report_details_required', item_id=item_id, kind='drug_product')
        epoch = self._epoch(owner)
        if after_ordinal:
            previous = self._get(owner, choice_token)
            self._same(profile, previous)
            if (previous['kind'] != 'drug_product' or previous['item_id'] != item_id
                    or previous['page'].get('next_after_ordinal') != after_ordinal
                    or previous['source']['binding']['snapshot_id'] != expected_snapshot_id):
                raise IdentityJourneyError('EXACT_IDENTITY_CONTINUATION_REQUIRED')
        query = {'name_text': inputs['values']['name'],
                 'strength_text': None, 'form_text': None}
        try:
            source = _source(self.discovery.search(**query, limit=20, after_ordinal=after_ordinal,
                expected_snapshot_id=expected_snapshot_id), 'l05-literal-drug-candidates-research-r1')
            rows = source['candidates']
            if not isinstance(rows, list) or len(rows) > 20:
                raise IdentityJourneyError('IDENTITY_SOURCE_SHAPE_INVALID')
            if any(row.get('namespace') != 'retained_L05_RxCUI_dictionary'
                   or row.get('output_authority') != 'held'
                   or row.get('automatic_profile_binding') is not False
                   or row.get('requires_identity_confirmation') is not True
                   or row.get('coverage_inferred') is not False
                   or row.get('states', {}).get('source_use_state') != 'existing_source_policy_applies'
                   or row.get('snapshot_source_use_state') != 'not_newly_reviewed' for row in rows):
                raise IdentityJourneyError('IDENTITY_SOURCE_CANDIDATE_CHANGED')
            drug_token, drug_service, exact_rows = None, None, rows
            if rows and all(key in inputs['values'] for key in ('name', 'strength', 'form')):
                drug_service = DrugIdentityChoices(self.drug_exact, clock=self.clock,
                    ttl_seconds=self.ttl_seconds, max_offers=1, max_per_owner=1)
                exact = drug_service.offer(owner, profile, item_id=item_id,
                    rxcuis=list(dict.fromkeys(row['identity']['rxcui'] for row in rows)), scope=IDENTITY_SCOPE)
                if exact['source_binding']['snapshot_id'] != source['binding']['snapshot_id']:
                    raise IdentityJourneyError('IDENTITY_SOURCE_SNAPSHOT_CHANGED')
                by_id = {row['candidate_id']: row for row in rows}
                exact_rows = exact['candidates']
                if (set(by_id) != {row['candidate_id'] for row in exact_rows}
                        or any(row['identity'] != by_id[row['candidate_id']]['identity']
                               or row['lineage']['raw_sha256'] != by_id[row['candidate_id']]['lineage']['raw_sha256']
                               for row in exact_rows)):
                    raise IdentityJourneyError('IDENTITY_SOURCE_CANDIDATE_CHANGED')
                drug_token = exact['choice_token']
            self._same(profile, {'kind': 'drug_product', 'item_id': item_id, 'inputs': inputs})
            token = self._offer(owner, inputs, source, exact_rows, query=query,
                drug_token=drug_token, drug_service=drug_service, page=source['page'], expected_epoch=epoch)
        except Exception:
            self._invalidate(owner, 'drug_product', item_id)
            raise IdentityJourneyError('IDENTITY_SOURCE_UNAVAILABLE_OR_CHANGED') from None
        return self._base(state='candidates' if rows else 'not_observed_in_selected_dictionary',
            item_id=item_id, kind='drug_product', choice_token=token,
            candidates=[_drug_label(row, drug_token is not None) for row in exact_rows],
            page=copy.deepcopy(source['page']), partial=copy.deepcopy(source['partial']),
            source=self._source_label(source), explicit_choice_required=True,
            discovery_basis='literal_name_only', reported=copy.deepcopy(inputs['values']))

    def provider_search(self, owner, profile, *, item_id, selector=None, after_ordinal=0,
                        expected_snapshot_id=None, choice_token=None):
        self._owner(owner)
        inputs = _item(profile, 'provider_site', item_id)
        if not self._enabled('provider_site'):
            return self._base(state='held', item_id=item_id, kind='provider_site')
        if not inputs['ready']:
            return self._base(state='current_report_details_required', item_id=item_id, kind='provider_site')
        epoch = self._epoch(owner)
        if selector is None:
            if self.provider_discovery is None:
                return self._base(state='provider_discovery_not_connected', item_id=item_id, kind='provider_site')
            if after_ordinal:
                previous = self._get(owner, choice_token)
                self._same(profile, previous)
                if (previous['stage'] != 'provider_entity' or previous['item_id'] != item_id
                        or previous['page'].get('next_after_ordinal') != after_ordinal
                        or previous['source']['binding']['snapshot_id'] != expected_snapshot_id):
                    raise IdentityJourneyError('EXACT_IDENTITY_CONTINUATION_REQUIRED')
            try:
                source = _source(self.provider_discovery.search(inputs['values']['practice'], limit=20,
                    after_ordinal=after_ordinal, expected_snapshot_id=expected_snapshot_id, year=2026),
                    'l08-literal-provider-candidates-research-r1')
                rows = source['candidates']
                if not isinstance(rows, list) or len(rows) > 20:
                    raise IdentityJourneyError('IDENTITY_SOURCE_SHAPE_INVALID')
                if not _provider_records_allowed(rows + source.get('sources', [])):
                    raise IdentityJourneyError('IDENTITY_SOURCE_CANDIDATE_CHANGED')
                self._same(profile, {'kind': 'provider_site', 'item_id': item_id, 'inputs': inputs})
                token = self._offer(owner, inputs, source, rows,
                    query={'name_text': inputs['values']['practice']}, page=source['page'],
                    stage='provider_entity', expected_epoch=epoch)
            except Exception:
                self._invalidate(owner, 'provider_site', item_id)
                raise IdentityJourneyError('IDENTITY_SOURCE_UNAVAILABLE_OR_CHANGED') from None
            return self._base(state='provider_entities_require_site_lookup', item_id=item_id, kind='provider_site',
                choice_token=token, candidates=[{'candidate_id': row['candidate_id'], 'kind': 'provider_entity',
                    'label': copy.deepcopy(row['label']), 'selector': copy.deepcopy(row['selector']),
                    'selectable': False, 'site_lookup_available': True,
                    'details_state': 'city_and_site_unresolved'} for row in rows],
                page=copy.deepcopy(source['page']), partial=copy.deepcopy(source.get('partial')),
                source=self._source_label(source), reported=copy.deepcopy(inputs['values']),
                search_basis=_search_basis(source),
                explicit_entity_and_site_choices_required=True)
        if (not isinstance(selector, dict) or len(selector) != 1 or not set(selector) <= {'npi', 'entity_key'}):
            raise IdentityJourneyError('EXACT_PROVIDER_SELECTOR_REQUIRED')
        if 'npi' in selector and (not isinstance(selector['npi'], str)
                                 or not re.fullmatch(r'[0-9]{10}', selector['npi'])):
            raise IdentityJourneyError('EXACT_PROVIDER_SELECTOR_REQUIRED')
        expected_source = None
        if 'entity_key' in selector:
            previous = self._get(owner, choice_token)
            self._same(profile, previous)
            if (previous['stage'] != 'provider_entity' or previous['item_id'] != item_id
                    or not any(row.get('selector') == selector for row in previous['candidates'].values())):
                raise IdentityJourneyError('EXACT_DISCOVERED_PROVIDER_ENTITY_REQUIRED')
            expected_source = previous['source']['binding']['snapshot_id']
        try:
            source = _source(self.provider.lookup(**selector, year=2026,
                expected_snapshot_id=expected_source), 'l08-exact-provider-site-research-r2')
            rows = source['site_candidates']
            if not isinstance(rows, list) or len(rows) > 200:
                raise IdentityJourneyError('IDENTITY_SOURCE_SHAPE_INVALID')
            if not _provider_records_allowed([row for key in
                    ('entity_candidates', 'role_observations', 'location_observations', 'sources')
                    for row in source.get(key, [])]):
                raise IdentityJourneyError('IDENTITY_SOURCE_CANDIDATE_CHANGED')
            self._same(profile, {'kind': 'provider_site', 'item_id': item_id, 'inputs': inputs})
            token = self._offer(owner, inputs, source, rows, query=selector, expected_epoch=epoch)
        except Exception:
            self._invalidate(owner, 'provider_site', item_id)
            raise IdentityJourneyError('IDENTITY_SOURCE_UNAVAILABLE_OR_CHANGED') from None
        return self._base(state=source['identity_state'], item_id=item_id, kind='provider_site',
            choice_token=token, candidates=[_provider_label(source, row) for row in rows],
            page=copy.deepcopy(source['page']), partial=copy.deepcopy(source['partial']),
            source=self._source_label(source), explicit_choice_required=True)

    @staticmethod
    def _source_label(source):
        return {'snapshot_id': source['binding']['snapshot_id'], 'year': 2026,
            'currentness': 'dated_retained_source_not_reverified',
            'source_access_registration': copy.deepcopy(source['source_access_registration']),
            'consumer_release': False}

    def _get(self, owner, token):
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise IdentityJourneyError('IDENTITY_OFFER_EXPIRED_OR_FOREIGN')
        with self._lock:
            self._prune()
            offer = self._offers.get(token)
            if offer is None or offer['owner'] != owner:
                raise IdentityJourneyError('IDENTITY_OFFER_EXPIRED_OR_FOREIGN')
            return copy.deepcopy(offer)

    def confirm(self, owner, profile, *, choice_token, candidate_id, confirmed=False):
        self._owner(owner)
        if confirmed is not True:
            raise IdentityJourneyError('EXPLICIT_IDENTITY_CHOICE_REQUIRED')
        offer = self._get(owner, choice_token)
        self._same(profile, offer)
        if offer['stage'] != 'site_or_product':
            raise IdentityJourneyError('EXPLICIT_PROVIDER_SITE_CHOICE_REQUIRED')
        if not self._enabled(offer['kind']):
            self._invalidate(owner, offer['kind'], offer['item_id'])
            return self._base(state='held', item_id=offer['item_id'], kind=offer['kind'])
        if not isinstance(candidate_id, str) or candidate_id not in offer['candidates']:
            raise IdentityJourneyError('EXACT_OFFERED_IDENTITY_REQUIRED')
        candidate = offer['candidates'][candidate_id]
        try:
            if offer['kind'] == 'drug_product':
                if not offer['drug_token']:
                    raise IdentityJourneyError('CURRENT_DRUG_REPORT_DETAILS_REQUIRED')
                with self._lock:
                    drug_service = self._drug_services.get(choice_token)
                if drug_service is None:
                    raise IdentityJourneyError('IDENTITY_OFFER_EXPIRED_OR_FOREIGN')
                result = drug_service.confirm(owner, profile, choice_token=offer['drug_token'],
                    candidate_id=candidate_id, confirmed=True)
                binding = result['binding']
            else:
                if not _provider_ready(offer['source'], candidate):
                    raise IdentityJourneyError('SOURCE_ACTOR_SITE_OR_LINEAGE_UNRESOLVED')
                source = _source(self.provider.lookup(**offer['query'], year=2026,
                    expected_snapshot_id=offer['source']['binding']['snapshot_id']), 'l08-exact-provider-site-research-r2')
                if not _provider_records_allowed([row for key in
                        ('entity_candidates', 'role_observations', 'location_observations', 'sources')
                        for row in source.get(key, [])]):
                    raise IdentityJourneyError('IDENTITY_SOURCE_CANDIDATE_CHANGED')
                current = next((row for row in source['site_candidates'] if row['candidate_id'] == candidate_id), None)
                if (current is None or _hash(current) != _hash(candidate) or not _provider_ready(source, current)):
                    raise IdentityJourneyError('IDENTITY_SOURCE_CANDIDATE_CHANGED')
                binding = asdict(IdentityBinding('provider_site', candidate['namespace'], candidate_id,
                    offer['item_id'], copy.deepcopy(IDENTITY_SCOPE), tuple(offer['inputs']['refs']),
                    (source['binding']['snapshot_id'], candidate['entity_ref'], candidate['role_ref'], candidate['location_ref'])))
            self._same(profile, offer)
            if not self._enabled(offer['kind']):
                raise IdentityJourneyError('IDENTITY_SOURCE_PURPOSE_CHANGED')
            assessment = assess_identity_binding(profile, [IdentityBinding(**binding)],
                kind=offer['kind'], item_id=offer['item_id'], scope=IDENTITY_SCOPE)
            if assessment['identity_state'] != 'bound':
                raise IdentityJourneyError('IDENTITY_REPORT_BINDING_STALE')
            with self._lock:
                self._prune()
                if choice_token not in self._offers:
                    raise IdentityJourneyError('IDENTITY_OFFER_EXPIRED_OR_FOREIGN')
                self._selected[(owner, offer['kind'], offer['item_id'])] = {
                    'offer_token': choice_token, 'candidate_id': candidate_id,
                    'binding': copy.deepcopy(binding), 'source_snapshot_id': offer['source']['binding']['snapshot_id'],
                    'expires': self.clock() + self.ttl_seconds}
            return self._base(state='explicitly_selected_source_identity', item_id=offer['item_id'],
                kind=offer['kind'], selected_candidate_id=candidate_id,
                binding=binding, assessment=assessment, source=self._source_label(offer['source']),
                binding_purpose='explicit_source_identity_selection_only',
                reported_details_consistency='requires_separate_reconciliation',
                coverage_verified=False, clinical_equivalence_inferred=False)
        except Exception:
            self._invalidate(owner, offer['kind'], offer['item_id'])
            raise IdentityJourneyError('IDENTITY_SELECTION_STALE_UNRESOLVED_OR_SOURCE_CHANGED') from None

    def _invalidate(self, owner, kind, item_id):
        with self._lock:
            self._selected.pop((owner, kind, item_id), None)
            self._offers = {key: value for key, value in self._offers.items()
                if (value['owner'], value['kind'], value['item_id']) != (owner, kind, item_id)}
            self._drug_services = {key: value for key, value in self._drug_services.items() if key in self._offers}

    def view(self, owner, profile, *, item_id=None):
        self._owner(owner)
        if item_id is not None and (not isinstance(item_id, str) or not ITEM.fullmatch(item_id)):
            raise IdentityJourneyError('EXACT_CURRENT_IDENTITY_ITEM_REQUIRED')
        assess_required_inputs(profile, [], finding_id='identity-view')
        keys = sorted({('drug_product' if f['ref']['item_id'].startswith('medicine-') else 'provider_site',
                        f['ref']['item_id']) for f in profile['facts'] if isinstance(f['ref'].get('item_id'), str)
                       and ITEM.fullmatch(f['ref']['item_id'])})
        with self._lock:
            removed = [(kind, identifier) for owner_key, kind, identifier in self._selected
                       if owner_key == owner and (kind, identifier) not in keys]
            for kind, identifier in removed:
                self._invalidate(owner, kind, identifier)
        rows = []
        for kind, identifier in keys:
            inputs = _item(profile, kind, identifier)
            with self._lock:
                self._prune()
                selected = copy.deepcopy(self._selected.get((owner, kind, identifier)))
            state = 'ready_for_identity_lookup' if inputs['ready'] else 'current_report_details_required'
            if not self._enabled(kind):
                state = 'held'
                if selected:
                    self._invalidate(owner, kind, identifier)
            elif selected:
                try:
                    offer = self._get(owner, selected['offer_token'])
                    self._same(profile, offer)
                    state = 'selected_needs_source_recheck'
                    if item_id == identifier:
                        self.confirm(owner, profile, choice_token=selected['offer_token'],
                                     candidate_id=selected['candidate_id'], confirmed=True)
                        state = 'explicitly_selected_source_identity'
                except (ValueError, TypeError, KeyError):
                    self._invalidate(owner, kind, identifier)
                    state = 'stale_identity_needs_fresh_lookup'
            rows.append({'item_id': identifier, 'kind': kind, 'state': state,
                         'reported': copy.deepcopy(inputs['values'])})
        return self._base(state='identity_preparation', items=rows)

    def preparation(self, owner, profile):
        """Reported selections for preparation, never live source/coverage findings."""
        view = self.view(owner, profile)
        bindings = []
        if self.capability()['state'] == 'internal_research_available':
            with self._lock:
                for row in view['items']:
                    selected = self._selected.get((owner, row['kind'], row['item_id']))
                    if selected and row['state'] == 'selected_needs_source_recheck':
                        bindings.append({'item_id': row['item_id'], 'kind': row['kind'],
                            'binding': copy.deepcopy(selected['binding']),
                            'source_snapshot_id': selected['source_snapshot_id'],
                            'source_state': 'requires_live_recheck', 'personal_output_state': 'held'})
        return {'state': 'identity_selection_preparation_only', 'bindings': bindings,
                'selected_count': len(bindings), 'coverage_findings': [],
                'personal_output_state': 'held', 'saved': False, 'ai_context_changed': False}

    def forget_owner(self, owner, *, item_id=None):
        self._owner(owner)
        with self._lock:
            self._prune()
            if owner in self._epochs or len(self._epochs) < 128:
                epoch = self._epochs.get(owner, (0,))[0]
                self._epochs[owner] = (epoch + 1, self.clock() + self.ttl_seconds)
            self._offers = {key: value for key, value in self._offers.items()
                if value['owner'] != owner or item_id is not None and value['item_id'] != item_id}
            self._selected = {key: value for key, value in self._selected.items()
                if key[0] != owner or item_id is not None and key[2] != item_id}
            self._drug_services = {key: value for key, value in self._drug_services.items() if key in self._offers}
        return self._base(state='forgotten', items=[])


def local_identity_journey(*, repository_root=None, internal_research=False):
    """Explicit local server dependency, never constructed from request fields."""
    import getpass
    import sys
    root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    purpose = IdentityPurposeContract.load(root, internal_research=internal_research)
    if not internal_research:
        return IdentityJourney(purpose=purpose)
    package = root / 'infrastructure/daylight-data'
    sys.path.insert(0, str(package / 'src'))
    from daylight_data.serving.drug_candidates import candidate_repository_from_env
    from daylight_data.serving.identity import identity_repository_from_env
    from daylight_data.serving.provider_identity import provider_repository_from_env
    from daylight_data.serving.provider_candidates import provider_candidate_repository_from_env
    dsn = ('host=' + str(package / '.state/socket') +
           ' port=55485 dbname=daylight_research_2026_r2 user=' + getpass.getuser())
    return IdentityJourney(candidate_repository_from_env(repository_root=root, dsn=dsn),
        identity_repository_from_env(repository_root=root, dsn=dsn),
        provider_repository_from_env(repository_root=root, dsn=dsn),
        provider_discovery=provider_candidate_repository_from_env(repository_root=root, dsn=dsn), purpose=purpose)
