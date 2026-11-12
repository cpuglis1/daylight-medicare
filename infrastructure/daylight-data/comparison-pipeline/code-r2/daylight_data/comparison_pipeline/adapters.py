"""Deterministic, research-only comparison input adapters.

``normalize_task(record, offering_id=None)`` accepts a strict sealed r9 record,
including its existing ``id`` and ``inventory_root_ids``, or one explicit envelope:

* ``artifact_type='r9_component_bundle'``, ``id``, ``components=[r9_record, ...]``.
  Optional offering_id/original_ids must agree with every component. Components,
  their order, full conditions and provenance survive; this is not an equivalence
  or whole-parent closure decision.
* ``artifact_type='carrier_price_cell'``, ``id``, ``offering_id``, ``original_ids``,
  ``cell_text`` (the WHOLE cell, including qualifiers). Optional ``source_complete``
  is a literal bool; ``condition_context``, ``evidence`` and
  ``unsupported_qualifiers`` retain full source context. A declared complete cell
  still needs interpretation. Literal $/USD/% tokens are observations only.
* ``artifact_type='native_literal'``, ``id``, ``offering_id``, ``original_ids``,
  ``payload`` and ``pointer`` (RFC6901). Optional evidence/authority is retained.
  Authority is an unreviewed input, never an executable decoder or approval.

* ``artifact_type='source_gap'``, ``id``, ``offering_id``, ``original_ids``,
  ``gap={...}`` (a nonempty retained source-gap declaration) and optional evidence.
  This transports an existing missing-source obligation, creating no new gap.

Source artifacts yield components=[] plus unresolved holds, NOT invented r9
observations. Unsupported/invalid inputs raise ValueError for caller quarantine.
No network, inventory mutation, source acceptance, name/amount joins or learned
native enums occur here. Sealed schema/guard bytes are checked before loading.
Source-artifact decimals use exact JSON strings with explicit encoding receipts.
Strict r9 JSON numbers retain numeric type only after an exact decimal serialization
round-trip check; otherwise they are quarantined. Original
input fingerprints are type-sensitive (Decimal is distinct from a string). Task identity depends only on the explicit
source record ID and exact offering; input/code changes invalidate evaluation,
not the stable task ID.
"""
from __future__ import annotations

import builtins
from copy import deepcopy
from decimal import Decimal
from functools import lru_cache
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
from types import MappingProxyType, ModuleType
from typing import Any

from daylight_data.adapters.common import canonical_json, offering_parts, sha256_file
import daylight_data.adapters.common as _common

_FORMAT = 'daylight/comparison-task/1'
_REGISTRY_VERSION = 'comparison-adapters-r1'
_AUTHORITY_PINS = MappingProxyType({
    'schema': ('docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/comparison-record.schema.json',
               '37e66820165e819baf6113955c54e727615e440ad655ac8fbea1ef519740140d'),
    'guard': ('docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/code/l03_r9_comparison.py',
              '0bd222621e4ede985505b7a70ba9f11a8dcf738ea66065ea7cc0bfb925414994'),
    'contract': ('docs/data/l03-ma-benefits-2026-10-25/inventory-r8/code/l03_comparison_contract.py',
                 'a5440048e43f53447f46fd51c17a91422d34c8fd415b5ebf06c66a1e78108d47'),
})
_COMMON_SHA = 'e95c9134b3fc3bf8d1902262cfb3564cd926e3c3dea1a668f00f4740f5ea771a'
_UNKNOWN = {'unknown', 'unresolved', 'missing'}
_PRICE = re.compile(
    r'(?<![\w$.,+-])(?P<sign>[+-]?)(?P<currency>\$|USD[ \t]+)'
    r'(?P<money>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?![\w,]|\.\d)'
    r'|(?<![\w.,])(?P<percent>[+-]?\d+(?:\.\d+)?)%(?![\w%])'
)


def _fail(code: str, path: str, message: str) -> None:
    raise ValueError(f'{code} at {path or "/"}: {message}')


def _pointer_part(value: str) -> str:
    return value.replace('~', '~0').replace('/', '~1')


def _json_copy(value: Any, path: str = '', decimals: list | None = None,
               active: set | None = None, *, strict_numbers: bool = False) -> Any:
    """Reject unsupported transport; never silently change a strict numeric proof."""
    if decimals is None:
        decimals = []
    if active is None:
        active = set()
    kind = type(value)
    if kind is Decimal:
        if not value.is_finite():
            _fail('nonfinite_number', path, 'Decimal must be finite')
        if strict_numbers:
            number = float(value)
            if not math.isfinite(number) or Decimal(str(number)) != value:
                _fail('strict_decimal_not_roundtrippable', path,
                      'cannot retain the original JSON numeric type/value under the sealed comparator; no string coercion')
            decimals.append({'path': path or '/', 'encoding': 'exact_json_number',
                             'source_decimal': str(value),
                             'serialized_number': json.dumps(number, allow_nan=False)})
            return number
        decimals.append({'path': path or '/', 'encoding': 'exact_decimal_string', 'value': str(value)})
        return str(value)
    if kind is float:
        if not math.isfinite(value):
            _fail('nonfinite_number', path, 'float must be finite')
        return value
    if value is None or kind in (str, bool, int):
        return value
    if kind not in (dict, list):
        _fail('unsupported_value_type', path, f'{kind.__name__} is not a JSON source value')
    if len(active) > 128:
        _fail('source_nesting_limit', path, 'source nesting exceeds supported JSON transport depth')
    if id(value) in active:
        _fail('cyclic_input', path, 'source must be an acyclic JSON value')
    active.add(id(value))
    try:
        if kind is list:
            return [_json_copy(v, f'{path}/{i}', decimals, active, strict_numbers=strict_numbers) for i, v in enumerate(value)]
        result = {}
        for k, v in value.items():
            if type(k) is not str:
                _fail('non_string_key', path, 'object keys must be strings')
            result[k] = _json_copy(v, path + '/' + _pointer_part(k), decimals, active, strict_numbers=strict_numbers)
        return result
    finally:
        active.remove(id(value))


def _typed_tree(value: Any) -> Any:
    """Unambiguous JSON tree for hashing; no Decimal/string or bool/int collision."""
    kind = type(value)
    if kind is dict:
        return ['object', [[k, _typed_tree(value[k])] for k in sorted(value)]]
    if kind is list:
        return ['array', [_typed_tree(v) for v in value]]
    if kind is Decimal:
        return ['decimal', str(value)]
    if kind is float:
        return ['float', value.hex()]
    if value is None:
        return ['null']
    return [{str: 'string', bool: 'boolean', int: 'integer'}[kind], value]


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(_typed_tree(value)).encode()).hexdigest()


def _repo_root() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / _AUTHORITY_PINS['schema'][0]).is_file():
            return p
    _fail('sealed_authority_unavailable', '/', 'local sealed r9 schema and parser files are required')


def _read_pinned(path: Path, expected: str) -> bytes:
    try:
        contents = path.read_bytes()
    except OSError as exc:
        _fail('sealed_authority_unavailable', str(path), str(exc))
    if hashlib.sha256(contents).hexdigest() != expected:
        _fail('sealed_authority_changed', str(path), 'does not match pinned authority digest')
    return contents


def adapter_dependencies() -> dict:
    """Expose exact static code/schema pins for the runner's evaluation cache."""
    root = _repo_root()
    for path, digest in _AUTHORITY_PINS.values():
        _read_pinned(root / path, digest)
    _read_pinned(Path(_common.__file__), _COMMON_SHA)
    return {
        **{name: {'path': path, 'sha256': digest} for name, (path, digest) in _AUTHORITY_PINS.items()},
        'normalization_helpers': {
            'path': 'infrastructure/daylight-data/src/daylight_data/adapters/common.py', 'sha256': _COMMON_SHA},
        'implementation': {
            'path': 'infrastructure/daylight-data/src/daylight_data/comparison_pipeline/adapters.py',
            'sha256': sha256_file(Path(__file__))},
    }


def adapter_version() -> str:
    try:
        validator_version = importlib.metadata.version('jsonschema')
    except importlib.metadata.PackageNotFoundError:
        validator_version = 'unavailable'
    value = {'registry': _REGISTRY_VERSION, 'dependencies': adapter_dependencies(),
             'jsonschema_version': validator_version}
    return _REGISTRY_VERSION + ':' + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _authority():
    root = _repo_root()
    # Recheck even after cache warmup: source authority drift fails closed.
    adapter_dependencies()
    return _compiled_authority(str(root))


@lru_cache(maxsize=1)
def _compiled_authority(root_text: str):
    try:
        import jsonschema
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012
    except ImportError as exc:
        _fail('strict_validator_unavailable', '/', f'jsonschema with Draft202012 support is required: {exc}')
    root = Path(root_text)
    schema = json.loads(_read_pinned(root / _AUTHORITY_PINS['schema'][0], _AUTHORITY_PINS['schema'][1]))
    registry = Registry().with_resource(schema['$id'], Resource(schema, DRAFT202012))
    validator = jsonschema.Draft202012Validator(schema, registry=registry)
    jsonschema.Draft202012Validator.check_schema(schema)
    contract = ModuleType('_daylight_pipeline_pinned_r8')
    contract.__file__ = str(root / _AUTHORITY_PINS['contract'][0])
    source = _read_pinned(Path(contract.__file__), _AUTHORITY_PINS['contract'][1])
    exec(compile(source, contract.__file__, 'exec'), contract.__dict__)
    guard = ModuleType('_daylight_pipeline_pinned_r9')
    guard.__file__ = str(root / _AUTHORITY_PINS['guard'][0])
    # Resolve ONLY the guard's fixed, hash-pinned dependency, without sys.path or
    # global sys.modules mutation. Input/configuration never chooses Python code.
    def pinned_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'l03_comparison_contract' and level == 0:
            return contract
        return builtins.__import__(name, globals, locals, fromlist, level)
    guard.__dict__['__builtins__'] = {**vars(builtins), '__import__': pinned_import}
    source = _read_pinned(Path(guard.__file__), _AUTHORITY_PINS['guard'][1])
    exec(compile(source, guard.__file__, 'exec'), guard.__dict__)
    return validator, guard.compare


def _hold(code: str, category: str, path: str, reason: str, dependencies: list | None = None) -> dict:
    return {'code': code, 'category': category, 'path': path or '/', 'reason': reason,
            'source_dependencies': deepcopy(dependencies or [])}


def _ids(value: Any, path: str) -> list[str]:
    if type(value) is not list or not value or any(type(x) is not str or not x.strip() for x in value):
        _fail('invalid_original_scope', path, 'expected a nonempty list of exact original IDs')
    if len(set(value)) != len(value):
        _fail('duplicate_original_scope', path, 'original IDs must not be duplicated in the envelope')
    return list(value)


def _offering(value: Any, path: str) -> str:
    try:
        offering_parts(value)  # Existing pinned helper: exact padded CY2026 IDs, no coercion.
    except (ValueError, TypeError):
        _fail('unsupported_offering', path, 'expected exact 2026:contract:plan:segment with padded identifiers')
    return value


def _declared_offering(raw: dict, requested: str | None) -> str | None:
    a = _offering(requested, '/offering_id (argument)') if requested is not None else None
    b = _offering(raw['offering_id'], '/offering_id') if 'offering_id' in raw else None
    if a and b and a != b:
        _fail('offering_scope_mismatch', '/offering_id', 'argument and envelope disagree')
    return a or b


def _source_dependencies(record: dict) -> list:
    return [deepcopy(e) for side in ('cms', 'carrier') if type(record.get(side)) is dict
            for e in record[side].get('evidence', [])]


def _unknown_holds(value: Any, path: str, dependencies: list):
    if type(value) is dict:
        if type(value.get('state')) is str and value['state'] in _UNKNOWN:
            yield _hold('unresolved_source_meaning', 'semantics', path,
                        str(value.get('reason') or value.get('assertion') or value['state']), dependencies)
        for k, v in value.items():
            yield from _unknown_holds(v, path + '/' + _pointer_part(k), dependencies)
    elif type(value) is list:
        for i, v in enumerate(value):
            yield from _unknown_holds(v, f'{path}/{i}', dependencies)


def _strict_components(records: list, declared: str | None) -> tuple[list, str, list, list, list]:
    if type(records) is not list or not records:
        _fail('empty_component_bundle', '/components', 'all explicit components are required')
    validator, compare = _authority()
    components, roots, holds, checks, offerings = [], [], [], [], set()
    seen_ids = {}
    for i, record in enumerate(records):
        path = f'/components/{i}'
        if type(record) is not dict:
            _fail('invalid_component', path, 'expected a strict r9 record, not a wrapper or nested bundle')
        errors = sorted(validator.iter_errors(record), key=lambda e: str(list(e.absolute_path)))
        if errors:
            error = errors[0]
            location = path + ''.join('/' + _pointer_part(str(k)) for k in error.absolute_path)
            _fail('strict_r9_schema_violation', location, error.message)
        for side in ('cms', 'carrier'):
            obs = record[side]
            if obs is None:
                continue
            amount = obs.get('cost', {}).get('amount') if type(obs.get('cost')) is dict else None
            if type(amount) is float:
                _fail('inexact_monetary_type', path + '/' + side + '/cost/amount', 'use an exact Decimal, decimal string or integer')
            for n, band in enumerate((obs.get('boundaries') or {}).get('day_bands', [])):
                if type(band.get('amount')) is float:
                    _fail('inexact_monetary_type', f'{path}/{side}/boundaries/day_bands/{n}/amount', 'use an exact Decimal, decimal string or integer')
            identity = obs.get('identity')
            if type(identity) is dict and 'year' in identity:
                oid = f"{identity['year']}:{identity['contract']}:{identity['plan']}:{identity['segment']}"
                _offering(oid, path + '/' + side + '/identity')
                offerings.add(oid)
                if declared and declared != oid:
                    _fail('offering_scope_mismatch', path + '/' + side + '/identity', 'component is outside the requested offering')
            else:
                holds.append(_hold('component_identity_unresolved', 'scope', path + '/' + side + '/identity',
                                   'An envelope offering never fills missing source identity.', _source_dependencies(record)))
        if len(offerings) > 1:
            _fail('offering_scope_mismatch', path, 'all source identities in every component must refer to one exact offering')
        copied = _json_copy(record, strict_numbers=True)
        if list(validator.iter_errors(copied)):
            _fail('strict_r9_encoding_violation', path, 'Decimal transport encoding does not satisfy the exact sealed schema')
        digest = _fingerprint(record)
        if record['id'] in seen_ids:
            if seen_ids[record['id']] != digest:
                _fail('component_id_collision', path + '/id', 'same component ID has different complete content')
            holds.append(_hold('repeated_component', 'scope', path, 'Exact duplicate occurrence preserved; no deduplication or extra completion credit.'))
        seen_ids[record['id']] = digest
        components.append(copied)
        for identifier in record['inventory_root_ids']:
            if identifier not in roots:
                roots.append(identifier)
        deps = _source_dependencies(copied)
        holds.extend(_unknown_holds(copied, path, deps))
        try:
            actual = compare(copied['cms'], copied['carrier'])
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            _fail('sealed_guard_rejected_component', path, str(exc))
        checks.append({'component_id': copied['id'], 'input_record_fingerprint': digest,
                       'normalized_record_fingerprint': _fingerprint(copied), 'actual_r9_result': actual})
        if actual['outcome'] != record['outcome']:
            holds.append(_hold('stored_outcome_mismatch', 'semantics', path + '/outcome',
                               f"Stored {record['outcome']!r}; sealed guard returns {actual['outcome']!r}. Stored value retained.", deps))
        if actual['outcome'] not in ('exact_agreement', 'supported_carrier_statement', 'documented_inapplicability'):
            holds.append(_hold('comparison_not_complete', 'semantics', path,
                               f"Sealed r9 result: {actual['outcome']}; differences={actual.get('differences', [])!r}.", deps))
    resolved = declared or (next(iter(offerings)) if offerings else None)
    if resolved is None:
        _fail('offering_scope_unresolved', '/offering_id', 'no complete source identity or explicit research offering scope')
    return components, resolved, roots, holds, checks


def _direct(raw: dict, requested: str | None) -> dict:
    components, offering, roots, holds, checks = _strict_components([raw], _declared_offering({}, requested))
    return {'offering_id': offering, 'original_ids': roots, 'components': components,
            'holds': holds, 'comparison_checks': checks, 'source_artifacts': []}


def _bundle(raw: dict, requested: str | None) -> dict:
    _identifier(raw)
    components, offering, roots, holds, checks = _strict_components(raw.get('components'), _declared_offering(raw, requested))
    if 'original_ids' in raw:
        declared = _ids(raw['original_ids'], '/original_ids')
        if set(declared) != set(roots):
            _fail('original_scope_mismatch', '/original_ids', 'must exactly cover the union of every component inventory_root_ids')
        roots = declared
    return {'offering_id': offering, 'original_ids': roots, 'components': components,
            'holds': holds, 'comparison_checks': checks,
            'source_artifacts': [{'role': 'untrusted_bundle_envelope', 'raw_record': _json_copy(raw, strict_numbers=True)}]}


def _identifier(raw: dict) -> str:
    value = raw.get('id')
    if type(value) is not str or not value.strip():
        _fail('missing_artifact_id', '/id', 'a nonempty stable source ID is required')
    return value


def _artifact_base(raw: dict, requested: str | None) -> dict:
    _identifier(raw)
    offering = _declared_offering(raw, requested)
    if offering is None:
        _fail('offering_scope_unresolved', '/offering_id', 'source artifacts require an exact research offering scope')
    holds = []
    if not raw.get('evidence'):
        holds.append(_hold('source_evidence_missing', 'evidence', '/evidence', 'Source evidence/locators are not supplied; no source meaning is verified.'))
    return {'offering_id': offering, 'original_ids': _ids(raw.get('original_ids'), '/original_ids'),
            'components': [], 'comparison_checks': [], 'holds': holds, 'source_artifacts': []}


def _price_cell(raw: dict, requested: str | None) -> dict:
    result = _artifact_base(raw, requested)
    text = raw.get('cell_text')
    if type(text) is not str or not text.strip():
        _fail('missing_full_price_cell', '/cell_text', 'retain the entire source cell, including qualifiers')
    complete = raw.get('source_complete')
    if complete is not None and type(complete) is not bool:
        _fail('invalid_source_completeness', '/source_complete', 'use a literal boolean, not a string or numeric flag')
    if complete is not True:
        result['holds'].append(_hold('price_cell_partial_or_unstated', 'evidence', '/source_complete', 'A partial/unstated cell cannot establish complete price meaning.'))
    if 'condition_context' not in raw or raw['condition_context'] is None:
        result['holds'].append(_hold('condition_context_missing', 'evidence', '/condition_context', 'Full governing conditions, headers and footnotes remain required.'))
    literals = []
    for match in _PRICE.finditer(text):
        digits = match['percent'] if match['percent'] is not None else match['sign'] + match['money'].replace(',', '')
        amount = Decimal(digits)
        literals.append({'source_text': match.group(), 'start': match.start(), 'end': match.end(),
                         'amount_decimal': format(amount, 'f'),
                         'literal_unit': 'percent' if match['percent'] is not None else 'USD' if match['currency'].startswith('USD') else '$',
                         'meaning_state': 'unresolved', 'no_price_kind_period_or_qualification_inferred': True})
    result['source_artifacts'] = [{'role': 'carrier_complete_price_cell_source_artifact',
                                   'raw_record': _json_copy(raw), 'literal_price_tokens': literals}]
    result['holds'].append(_hold('whole_price_cell_interpretation_required', 'semantics', '/cell_text',
                               'Literal prices do not establish applicability, period, network, deductible, caps, history, replacement or after-cap liability.', raw.get('evidence') if type(raw.get('evidence')) is list else []))
    for i, qualifier in enumerate(raw.get('unsupported_qualifiers', []) if type(raw.get('unsupported_qualifiers')) is list else [raw['unsupported_qualifiers']] if 'unsupported_qualifiers' in raw else []):
        result['holds'].append(_hold('unsupported_price_qualifier', 'semantics', f'/unsupported_qualifiers/{i}',
                                   'Retained unresolved source qualifier: ' + canonical_json(qualifier)))
    return result


def _native(raw: dict, requested: str | None) -> dict:
    result = _artifact_base(raw, requested)
    if 'payload' not in raw:
        _fail('missing_native_payload', '/payload', 'literal source payload is required')
    pointer = raw.get('pointer')
    if type(pointer) is not str or (pointer and not pointer.startswith('/')):
        _fail('invalid_native_pointer', '/pointer', 'expected an RFC6901 pointer, including empty pointer for whole payload')
    value = raw['payload']
    for token in pointer.split('/')[1:] if pointer else []:
        if re.search(r'~(?![01])', token):
            _fail('invalid_native_pointer', '/pointer', 'invalid RFC6901 escape')
        token = token.replace('~1', '/').replace('~0', '~')
        if type(value) is dict and token in value:
            value = value[token]
        elif type(value) is list and re.fullmatch(r'0|[1-9]\d*', token) and int(token) < len(value):
            value = value[int(token)]
        else:
            _fail('native_pointer_not_found', '/pointer', 'pointer does not select a literal value; null is distinct from missing')
    result['source_artifacts'] = [{'role': 'native_literal_source_artifact', 'raw_record': _json_copy(raw),
                                   'literal_pointer': pointer, 'literal_value': _json_copy(value),
                                   'literal_value_type': type(value).__name__, 'meaning_state': 'unknown'}]
    result['holds'].append(_hold('native_authority_requires_review' if raw.get('authority') is not None else 'native_meaning_unresolved',
                               'semantics', '/authority', 'Literal extraction grants no native code, currency, enum, coverage or cross-format mapping. Supplied authority remains an unreviewed source input.'))
    return result


def _source_gap(raw: dict, requested: str | None) -> dict:
    result = _artifact_base(raw, requested)
    if type(raw.get('gap')) is not dict or not raw['gap']:
        _fail('invalid_source_gap', '/gap', 'expected a nonempty existing source-gap declaration')
    result['source_artifacts'] = [{'role': 'required_source_gap_source_artifact',
                                   'raw_record': _json_copy(raw)}]
    result['holds'].append(_hold('required_source_missing', 'source', '/gap',
                               'Required source capability remains missing; the full declared gap is retained without interpreting a value or creating an inventory obligation.',
                               raw.get('evidence') if type(raw.get('evidence')) is list else []))
    return result


# Fixed per-source-family dispatch. No caller-selected module/function/config code.
ADAPTER_REGISTRY = MappingProxyType({
    'strict_r9': ('sealed-r9-record', _direct),
    'r9_component_bundle': ('sealed-r9-component-bundle', _bundle),
    'carrier_price_cell': ('carrier-complete-price-cell-source', _price_cell),
    'native_literal': ('native-literal-source', _native),
    'source_gap': ('required-source-gap', _source_gap),
})


def stable_task_id(offering_id: str, source_record_id: str) -> str:
    """Same identity for valid and quarantined occurrences of one source record.

    Content, interpretation, adapter and review fingerprints belong to evaluation
    identity. The caller can use this helper before schema validation while keeping
    the raw record and precise error in quarantine.
    """
    _offering(offering_id, '/offering_id')
    _identifier({'id': source_record_id})
    digest = hashlib.sha256(canonical_json([offering_id, source_record_id]).encode()).hexdigest()
    return 'comparison-task-' + digest


def normalize_task(raw_record: dict, *, offering_id: str | None = None) -> dict:
    """Return a source-preserving research task, or ValueError for quarantine."""
    if type(raw_record) is not dict:
        _fail('unsupported_record_type', '/', 'expected a JSON object')
    decimal_paths: list = []
    kind = raw_record.get('artifact_type', 'strict_r9')
    if type(kind) is not str or kind not in ADAPTER_REGISTRY:
        _fail('unsupported_adapter_family', '/artifact_type', 'supported families: ' + ', '.join(ADAPTER_REGISTRY))
    _json_copy(raw_record, decimals=decimal_paths, strict_numbers=kind in ('strict_r9', 'r9_component_bundle'))
    adapter_id, normalize = ADAPTER_REGISTRY[kind]
    result = normalize(raw_record, offering_id)
    result['holds'] += [
        _hold('independent_review_required', 'review', '/', 'Parsing and sealed mechanical comparison do not perform independent source/whole-condition review.'),
        _hold('reference_acceptance_held', 'review', '/', 'No new release/source-use acceptance is granted by an adapter.'),
    ]
    version = adapter_version()
    input_fp = _fingerprint(raw_record)
    source_record_id = _identifier(raw_record)
    # Task identity survives source/cell/component/code changes. Evaluation/cache
    # identity uses input_fingerprint + adapter_version and is deliberately separate.
    task_id = stable_task_id(result['offering_id'], source_record_id)
    return {'schema': _FORMAT, 'task_id': task_id, 'source_record_id': source_record_id,
            **result, 'adapter_id': adapter_id, 'adapter_version': version,
            'input_fingerprint': input_fp, 'adapter_dependencies': adapter_dependencies(),
            'decimal_encoding': decimal_paths, 'decimal_encoding_path_basis': 'raw_record RFC6901 pointers', 'research_only': True,
            'accepted_for_reference': False, 'consumer_usable': False}
