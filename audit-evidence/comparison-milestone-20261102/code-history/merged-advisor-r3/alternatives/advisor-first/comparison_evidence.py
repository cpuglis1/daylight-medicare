"""Server-owned evidence boundary for the additive comparison workstream.

There is deliberately no consumer release/promotion loader here. The local
research database and its validated identity bridges remain research evidence;
this module neither queries it nor turns a profile/client flag into authority.
Fictional providers used by tests must construct explicitly fictional snapshots.
No fictional catalog is shipped with the application.
"""
from dataclasses import dataclass
from collections.abc import Mapping
import copy
import hashlib
import json


EVIDENCE_VERSION = 'comparison-evidence-held-r1'
PURPOSES = ('published_display', 'personal_comparison', 'ranking',
            'recommendation', 'quote', 'enrollment')
ECONOMIC_KEYS = frozenset({'commission', 'commissions', 'commission_rate', 'commission_amount',
    'payout', 'payouts', 'referral_fee', 'referral_fees', 'sponsorship', 'sponsor',
    'commercial', 'commercial_metadata', 'compensation', 'conversion_target',
    'lifetime_value', 'carrier_appointment', 'appointment_status', 'partner_preference',
    'revenue', 'revenue_weight', 'fulfillment_priority'})
UNIT_KEYS = frozenset({'unit_id', 'kind', 'display_name', 'identity', 'identity_state',
    'period', 'role', 'source_refs', 'restrictions', 'evaluation_state', 'fictional', 'components'})
OBSERVATION_KEYS = frozenset({'unit_id', 'dimension_id', 'item_id', 'result', 'value',
    'condition_set', 'evidence_state', 'source_use_state', 'policy_state',
    'evidence_refs', 'rule_refs', 'required_report_refs'})
VALUE_KEYS = frozenset({'type', 'amount', 'value', 'currency', 'unit', 'period', 'cost_type',
    'scope_key', 'population_basis', 'network', 'channel', 'phase', 'included_components',
    'excluded_components', 'assumptions'})


class ComparisonEvidenceError(ValueError):
    """A fixed-code error; never include supplied source or customer values."""


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def reject_economic_fields(value, depth=0):
    """Reject commercial feature keys, without searching personal prose values."""
    if depth > 40:
        raise ComparisonEvidenceError('COMPARISON_INPUT_TOO_DEEP')
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key.casefold().replace('-', '_') in ECONOMIC_KEYS:
                raise ComparisonEvidenceError('ECONOMIC_CONTEXT_FORBIDDEN')
            reject_economic_fields(child, depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in value:
            reject_economic_fields(child, depth + 1)


@dataclass(frozen=True)
class EvidenceSnapshot:
    """A snapshot supplied by a server dependency, never deserialized from HTTP.

    Real source authority is unimplemented and always held. ``fictional_fixture``
    allows exercising structural comparisons, with fixture-only findings and all
    real consumer purposes still held. Its unit IDs must use the fixture namespace.
    """
    manifest_id: str = EVIDENCE_VERSION
    serving_build_id: str | None = None
    research_build_id: str | None = None
    source_kind: str = 'research_held'
    completeness: str = 'unknown'
    units: tuple = ()
    observations: tuple = ()
    accepted_release_id: None = None


class HeldEvidenceSource:
    """The production default: no DB connection and no consumer catalog."""

    def snapshot(self, scope):
        return EvidenceSnapshot()


def held_evidence():
    return HeldEvidenceSource()


def read_snapshot(source=None, scope=None):
    """Read and copy one trusted provider snapshot; reject JSON-shaped providers.

    Snapshot contents never establish real output authority. Even a provider
    carrying observed/reviewed rows has no promotion path in this revision.
    """
    source = held_evidence() if source is None else source
    if isinstance(source, Mapping) or not callable(getattr(source, 'snapshot', None)):
        raise ComparisonEvidenceError('SERVER_EVIDENCE_SOURCE_REQUIRED')
    snapshot = source.snapshot(copy.deepcopy(scope or {}))
    if type(snapshot) is not EvidenceSnapshot:
        raise ComparisonEvidenceError('UNSUPPORTED_EVIDENCE_SNAPSHOT')
    if (snapshot.source_kind not in {'research_held', 'fictional_fixture'}
            or snapshot.completeness not in {'complete', 'partial', 'unknown'}
            or snapshot.accepted_release_id is not None
            or not isinstance(snapshot.manifest_id, str)
            or not isinstance(snapshot.units, (tuple, list))
            or not isinstance(snapshot.observations, (tuple, list))
            or len(snapshot.units) > 100 or len(snapshot.observations) > 5000):
        raise ComparisonEvidenceError('UNSUPPORTED_EVIDENCE_SNAPSHOT')
    units = copy.deepcopy(list(snapshot.units))
    observations = copy.deepcopy(list(snapshot.observations))
    reject_economic_fields({'units': units, 'observations': observations})
    seen = set()
    for unit in units:
        if (not isinstance(unit, dict) or not isinstance(unit.get('unit_id'), str)
                or set(unit) - UNIT_KEYS):
            raise ComparisonEvidenceError('UNSUPPORTED_EVIDENCE_UNIT')
        if unit['unit_id'] in seen:
            raise ComparisonEvidenceError('DUPLICATE_EVIDENCE_UNIT')
        seen.add(unit['unit_id'])
        if snapshot.source_kind == 'fictional_fixture' and (
                not unit['unit_id'].startswith('fixture:') or unit.get('fictional') is not True):
            raise ComparisonEvidenceError('FICTIONAL_IDENTITY_REQUIRED')
    keys = set()
    for row in observations:
        if (not isinstance(row, dict) or row.get('unit_id') not in seen
                or not isinstance(row.get('dimension_id'), str) or set(row) - OBSERVATION_KEYS):
            raise ComparisonEvidenceError('UNSUPPORTED_EVIDENCE_OBSERVATION')
        if row.get('value') is not None and (
                not isinstance(row['value'], dict) or set(row['value']) - VALUE_KEYS):
            raise ComparisonEvidenceError('UNSUPPORTED_TYPED_EVIDENCE_VALUE')
        key = (row['unit_id'], row['dimension_id'], row.get('item_id'))
        if key in keys:
            raise ComparisonEvidenceError('DUPLICATE_EVIDENCE_OBSERVATION')
        keys.add(key)
    # Reject non-JSON values/non-finite numbers rather than allowing a provider
    # to share mutable records or poison deterministic result identities.
    content = {'manifest_id': snapshot.manifest_id, 'serving_build_id': snapshot.serving_build_id,
               'research_build_id': snapshot.research_build_id, 'source_kind': snapshot.source_kind,
               'completeness': snapshot.completeness, 'units': units, 'observations': observations}
    try:
        digest = canonical_sha256(content)
    except (TypeError, ValueError):
        raise ComparisonEvidenceError('NON_JSON_EVIDENCE') from None
    return EvidenceSnapshot(snapshot.manifest_id, snapshot.serving_build_id,
                            snapshot.research_build_id, snapshot.source_kind,
                            snapshot.completeness, tuple(units), tuple(observations)), digest


def purpose_authorities(snapshot):
    """No current real or fictional record grants a real consumer purpose."""
    return {purpose: {'state': 'held', 'authority_refs': [],
                     'reason_codes': ['EXACT_RELEASE_REQUIRED', 'POLICY_NOT_ACCEPTED'],
                     'accepted_release_id': None}
            for purpose in PURPOSES}
