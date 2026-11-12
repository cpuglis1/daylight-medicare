"""Visit-only exact drug-identity choices over an injected guarded repository.

This callable seam is not an HTTP route, model tool, saved profile authority or
coverage decision. Its caller must authenticate the owner and obtain an explicit
item-specific choice. Source options never choose themselves. No input report is
filled from a dictionary, and no clinical/name equivalence is inferred here.
"""
from dataclasses import asdict
import copy
import re
import secrets
import threading
import time

from comparison_evidence import canonical_sha256, reject_economic_fields
from comparison_methods import (IdentityBinding, RequiredInput,
                                assess_identity_binding, assess_required_inputs)


VERSION = 'visit-drug-identity-choice-20261101-r1'
NAMESPACE = 'retained_L05_RxCUI_dictionary'
HELD_PURPOSES = ('published_display', 'personal_comparison', 'ranking',
                 'recommendation', 'quote', 'enrollment')
PATH = 'readiness.facts.RC22.value.items[].'


class IdentityResolutionError(ValueError):
    """Fixed-code failure; no customer/source values in the error."""


def _hash(value):
    reject_economic_fields(value)
    return canonical_sha256(value)


def _inputs(profile, item_id, scope):
    if (not isinstance(profile, dict) or not isinstance(item_id, str) or not 1 <= len(item_id) <= 100
            or not isinstance(scope, dict) or type(scope.get('year')) is not int
            or scope['year'] != 2026 or scope != profile.get('requested_scope')):
        raise IdentityResolutionError('EXACT_CURRENT_ITEM_SCOPE_REQUIRED')
    assessment = assess_required_inputs(profile,
        [RequiredInput(PATH + leaf, item_id) for leaf in ('name', 'strength', 'form')],
        finding_id='drug-identity-confirmation')
    if assessment['input_state'] != 'sufficient_report':
        raise IdentityResolutionError('CURRENT_DRUG_REPORT_DETAILS_REQUIRED')
    refs = assessment['dependency_refs']
    facts = []
    for ref in refs:
        matches = [fact for fact in profile['facts'] if fact['ref'] == ref]
        if len(matches) != 1:
            raise IdentityResolutionError('DRUG_REPORT_BINDING_UNRESOLVED')
        fact = copy.deepcopy(matches[0])
        # Parent bookkeeping may advance while the exact item report is
        # unchanged. assess_identity_binding separately rejects parent rollback.
        fact['ref'].pop('record_revision', None)
        facts.append(fact)
    return {'refs': copy.deepcopy(refs), 'fingerprint': _hash(facts),
            'subject_id': profile['profile_binding']['subject_id']}


def _source_candidates(source):
    if (not isinstance(source, dict)
            or not isinstance(source.get('authority'), dict)
            or not isinstance(source.get('binding'), dict)
            or source.get('contract_id') != 'l05-exact-rxcui-research-r1'
            or source.get('operator_only') is not True
            or source.get('automatic_profile_binding') is not False
            or source.get('consumer_release') is not False
            or source.get('clinical_substitution') is not False
            or not isinstance(source.get('source_access_states'), list)
            or any(not isinstance(row, dict) or row.get('state') != 'permitted'
                   for row in source.get('source_access_states', []))
            or not isinstance(source.get('source_access_registration'), dict)
            or source['source_access_registration'].get('absence_is_permission') is not False
            or any(source.get('authority', {}).get(purpose, {}).get('state') != 'held'
                   for purpose in HELD_PURPOSES)
            or not isinstance(source.get('binding', {}).get('snapshot_id'), str)
            or not source['binding']['snapshot_id']
            or not isinstance(source.get('candidates'), list)
            or len(source['candidates']) > 20):
        raise IdentityResolutionError('EXACT_DICTIONARY_SOURCE_REQUIRED')
    _hash(source)
    candidates = {}
    for candidate in source['candidates']:
        if (not isinstance(candidate, dict) or candidate.get('namespace') != NAMESPACE
                or not isinstance(candidate.get('candidate_id'), str)
                or not candidate['candidate_id']
                or candidate['candidate_id'] in candidates
                or candidate.get('automatic_profile_binding') is not False
                or candidate.get('requires_identity_confirmation') is not True
                or candidate.get('coverage_inferred') is not False
                or candidate.get('output_authority') != 'held'
                or not isinstance(candidate.get('lineage'), dict)
                or not isinstance(candidate.get('identity'), dict)
                or not isinstance(candidate['identity'].get('rxcui'), str)
                or not re.fullmatch(r'[1-9][0-9]{0,9}', candidate['identity']['rxcui'])
                or not isinstance(candidate.get('states'), dict)
                or candidate['states'].get('source_use_state') != 'existing_source_policy_applies'
                or candidate.get('snapshot_source_use_state') != 'not_newly_reviewed'
                or not candidate.get('lineage', {}).get('raw_sha256')):
            raise IdentityResolutionError('EXACT_DICTIONARY_CANDIDATE_REQUIRED')
        candidates[candidate['candidate_id']] = copy.deepcopy(candidate)
    return candidates


class DrugIdentityChoices:
    """Bounded process-memory choices; no persistence, AI, name search or UI.

    The repository is a server-injected guarded DrugIdentityRepository. Never
    accept a serialized client source response in place of that dependency.
    Owner is likewise server-bound, never taken from a body field.
    """

    def __init__(self, repository, *, clock=time.monotonic, ttl_seconds=600,
                 max_offers=32, max_per_owner=4):
        if (type(ttl_seconds) not in {int, float} or not 0 < ttl_seconds <= 1800
                or type(max_offers) is not int or not 1 <= max_offers <= 128
                or type(max_per_owner) is not int or not 1 <= max_per_owner <= 16):
            raise ValueError('IDENTITY_CHOICE_CONFIGURATION')
        self.repository, self.clock = repository, clock
        self.ttl_seconds, self.max_offers, self.max_per_owner = ttl_seconds, max_offers, max_per_owner
        self._offers, self._lock = {}, threading.RLock()

    def _owner(self, owner):
        if not isinstance(owner, str) or not 16 <= len(owner) <= 128:
            raise IdentityResolutionError('BOUND_OWNER_REQUIRED')

    def _prune(self):
        now = self.clock()
        self._offers = {key: value for key, value in self._offers.items()
                        if value['expires'] > now}

    def _read(self, rxcuis, *, expected_snapshot_id=None):
        try:
            value = self.repository.lookup_rxcuis(rxcuis, year=2026,
                expected_snapshot_id=expected_snapshot_id)
        except Exception:
            raise IdentityResolutionError('IDENTITY_SOURCE_UNAVAILABLE_OR_CHANGED') from None
        candidates = _source_candidates(value)
        if expected_snapshot_id is not None and value['binding']['snapshot_id'] != expected_snapshot_id:
            raise IdentityResolutionError('IDENTITY_SOURCE_UNAVAILABLE_OR_CHANGED')
        return value, candidates

    def offer(self, owner, profile, *, item_id, rxcuis, scope):
        self._owner(owner)
        inputs = _inputs(profile, item_id, scope)
        # The guarded repository validates the exact numeric-ID batch. No
        # customer name/strength/form or owner is sent to the dictionary query.
        source, candidates = self._read(rxcuis)
        with self._lock:
            self._prune()
            if len(self._offers) >= self.max_offers or sum(value['owner'] == owner
                    for value in self._offers.values()) >= self.max_per_owner:
                raise IdentityResolutionError('IDENTITY_CHOICE_CAPACITY')
            token = secrets.token_hex(32)
            self._offers[token] = {'owner': owner, 'item_id': item_id,
                'scope': copy.deepcopy(scope), 'inputs': inputs,
                'source_snapshot': source['binding']['snapshot_id'],
                'source_binding': copy.deepcopy(source['binding']),
                'source_registration': copy.deepcopy(source.get('source_access_registration')),
                'candidates': candidates, 'selected': None,
                'expires': self.clock() + self.ttl_seconds}
        return {'contract_id': VERSION, 'choice_token': token, 'item_id': item_id,
            'scope': copy.deepcopy(scope), 'candidates': list(candidates.values()),
            'matches': copy.deepcopy(source.get('matches', [])),
            'source_binding': copy.deepcopy(source['binding']),
            'source_access_registration': copy.deepcopy(source.get('source_access_registration')),
            'expires_in_seconds': self.ttl_seconds,
            'explicit_choice_required': True, 'profile_reports_changed': False,
            'source_release_changed': False, 'personal_output_state': 'held'}

    def _current(self, offer, profile):
        inputs = _inputs(profile, offer['item_id'], offer['scope'])
        if (inputs['subject_id'] != offer['inputs']['subject_id']
                or inputs['fingerprint'] != offer['inputs']['fingerprint']):
            raise IdentityResolutionError('IDENTITY_ITEM_REPORT_CHANGED')
        return inputs

    def _binding(self, offer, candidate):
        evidence = candidate['lineage']
        return IdentityBinding('drug_product', NAMESPACE, candidate['candidate_id'],
            offer['item_id'], copy.deepcopy(offer['scope']),
            tuple(copy.deepcopy(offer['inputs']['refs'])),
            (offer['source_snapshot'], evidence['raw_sha256'], candidate['candidate_id']))

    def confirm(self, owner, profile, *, choice_token, candidate_id, confirmed=False):
        self._owner(owner)
        if confirmed is not True:
            raise IdentityResolutionError('EXPLICIT_IDENTITY_CHOICE_REQUIRED')
        if (not isinstance(choice_token, str) or not re.fullmatch(r'[a-f0-9]{64}', choice_token)
                or not isinstance(candidate_id, str) or not 1 <= len(candidate_id) <= 512):
            raise IdentityResolutionError('EXACT_OFFERED_CANDIDATE_REQUIRED')
        with self._lock:
            self._prune()
            offer = self._offers.get(choice_token)
            if offer is None or offer['owner'] != owner:
                raise IdentityResolutionError('IDENTITY_CHOICE_EXPIRED_OR_FOREIGN')
            self._current(offer, profile)
            candidate = offer['candidates'].get(candidate_id)
            if candidate is None or offer['selected'] not in {None, candidate_id}:
                raise IdentityResolutionError('EXACT_OFFERED_CANDIDATE_REQUIRED')
            if (candidate.get('identity_grain') != 'drug_product_concept'
                    or candidate.get('identity_detail_state') != 'source_details_present'):
                raise IdentityResolutionError('SOURCE_PRODUCT_DETAILS_OR_GRAIN_UNRESOLVED')
            # Replay the guarded source immediately before selection. A STOP,
            # revision, disappearance or changed raw candidate invalidates it.
            _, current = self._read([candidate['identity']['rxcui']],
                expected_snapshot_id=offer['source_snapshot'])
            if candidate_id not in current or _hash(current[candidate_id]) != _hash(candidate):
                raise IdentityResolutionError('IDENTITY_SOURCE_CANDIDATE_CHANGED')
            if offer['expires'] <= self.clock():
                self._offers.pop(choice_token, None)
                raise IdentityResolutionError('IDENTITY_CHOICE_EXPIRED_OR_FOREIGN')
            self._current(offer, profile)
            binding = self._binding(offer, candidate)
            assessment = assess_identity_binding(profile, (binding,), kind='drug_product',
                item_id=offer['item_id'], scope=offer['scope'])
            if assessment['identity_state'] != 'bound':
                raise IdentityResolutionError('IDENTITY_REPORT_BINDING_STALE')
            offer['selected'] = candidate_id
            return {'contract_id': VERSION, 'choice_state': 'explicitly_selected_source_identity',
                'binding': asdict(binding), 'assessment': assessment,
                'source_binding': copy.deepcopy(offer['source_binding']),
                'source_access_registration': copy.deepcopy(offer['source_registration']),
                'profile_reports_changed': False, 'clinical_equivalence_inferred': False,
                'reported_details_consistency': 'requires_separate_reconciliation',
                'binding_purpose': 'explicit_source_identity_selection_only',
                'coverage_verified': False, 'current_terminology_status_verified': False,
                'source_release_changed': False, 'personal_output_state': 'held'}

    def forget_owner(self, owner):
        self._owner(owner)
        with self._lock:
            self._offers = {key: value for key, value in self._offers.items()
                            if value['owner'] != owner}
