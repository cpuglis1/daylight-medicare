"""Resolve declared local dependency references without fetching or changing evidence.

This is a byte/source dependency audit, not source-use or consumer acceptance.
Every traversed edge retains its original spelling and expected hash. ZIP member
names are retained as member lineage rather than mistaken for whole-file hashes.
"""
from __future__ import annotations

from collections import defaultdict, deque
import gzip
import hashlib
import json
import mimetypes
from pathlib import Path
import re
from typing import Any, Iterable

from .common import canonical_json, digest_json, digest_json_streamed, load_json, sha256_file

CATALOG_PATH = "docs/data/integration-review-2026-10-29/review-catalog.json"
COMPOSITION_PATH = "infrastructure/daylight-data/config/source-composition.2026.json"
HASH = re.compile(r"^[0-9a-f]{64}$")
PATH_KEYS = {"path", "raw", "file", "local_path", "raw_path", "extracted_path",
             "manifest", "parent_manifest", "source_manifest_path", "package", "parent_package",
             "directory", "build", "database", "hospital_database", "original_medicare_database",
             "reference_package", "validation", "report", "receipt", "acceptance_receipt",
             "identity_source", "source", "source_file", "input", "output", "code", "selection",
             "price_selection", "cost_selection", "previous_selection"}
PRIVATE_NAMES = {".env", ".git", ".aws", ".ssh", ".codex", "credentials", "credentials.json", "secrets", "secrets.json", "id_rsa", "id_ed25519"}
PRIVATE_PART = re.compile(r"(?:guest|profile|budget|transcript|session).*(?:\.sqlite3?|\.db|\.jsonl)$", re.I)
CONTROL_WORDS = ("manifest", "freeze", "selection", "CURRENT_", "access-hold", "source-stop", "sources")


def _exclusion(path: Path, root: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return 'excluded_outside_approved_root'
    if any(relative.parts[index:index + 2] == ('cms-slice', 'var') for index in range(len(relative.parts) - 1)):
        return 'excluded_private_material'
    if any(part in PRIVATE_NAMES or part.startswith('.env') for part in relative.parts) or PRIVATE_PART.search(relative.name):
        return 'excluded_private_material'
    return None


def _forbidden(path: Path, root: Path) -> bool:
    return _exclusion(path, root) is not None


def _pathlike(value: str, key: str = "") -> bool:
    # A path in a quotation/description is not a declared source dependency.
    # Only semantically named locator fields and exact hash maps are followed.
    declared_key = key in PATH_KEYS or key.endswith(('_path', '_file', '_manifest', '_database', '_selection'))
    if not declared_key or value.startswith(("http:", "https:", "s3:", "data:", "#")) or "\n" in value or len(value) > 600:
        return False
    if Path(value).name in PRIVATE_NAMES or Path(value).name.startswith('.env'):
        return True
    if value.startswith(("docs/", "cms-slice/", "plans/", "/Users/", "/private/", "/tmp/", "/var/")):
        return True
    return bool(re.search(r"(?:\.(?:jsonl?|csv|tsv|sqlite3?|txt|pdf|py|zip|html|md|gz|xlsx?|xml|yaml|toml)$|/[0-9a-f]{64}$)", value))


def _control_files(directory: Path) -> Iterable[Path]:
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix == '.json'
                  and any(word.lower() in path.name.lower() for word in CONTROL_WORDS))


def _mime(path: Path) -> str:
    guessed = mimetypes.guess_type(path.name)[0]
    if guessed:
        return guessed
    with path.open('rb') as handle:
        head = handle.read(256).lstrip()
    for prefix, mime in [(b'%PDF-', 'application/pdf'), (b'PK\x03\x04', 'application/zip'),
                         (b'SQLite format 3\x00', 'application/vnd.sqlite3'), (b'\x1f\x8b', 'application/gzip')]:
        if head.startswith(prefix):
            return mime
    if head.startswith((b'{', b'[')):
        return 'application/json'
    if head.lower().startswith((b'<!doctype html', b'<html')):
        return 'text/html'
    return 'application/octet-stream'


def make_composition(root: Path) -> dict[str, Any]:
    """Resolve all selected layers and explicit bases/overlays from the dated catalog."""
    root = root.resolve()
    catalog = load_json(root / CATALOG_PATH)
    layers = []
    for layer in catalog['layers']:
        seeds: dict[str, dict[str, Any]] = {}
        for original in layer['current_artifacts']:
            path = root / original
            seeds[original] = {"path": original, "role": "catalog_selected_artifact_or_directory"}
            directory = path if path.is_dir() else path.parent
            for manifest in _control_files(directory):
                rel = manifest.relative_to(root).as_posix()
                seeds.setdefault(rel, {"path": rel, "role": "selected_component_control"})
        # Explicit overlay components preserve their independent acceptance boundaries.
        if layer['layer_id'] == 'L03':
            components = [('bounded-reference-r4', 'accepted_exact_535_entries_only'),
                          ('source-reconciliation-r7', 'unaccepted_additive_evidence'),
                          ('semantic-inventory-r9', 'unaccepted_required_obligations'),
                          ('inventory-r8', 'sealed_parent_of_r9')]
        elif layer['layer_id'] == 'L08':
            components = [('wellcare-r5', 'research_only'), ('original-medicare-r6', 'research_only'),
                          ('hospital-reference-r7', 'research_only')]
        elif layer['layer_id'] == 'L10':
            components = [('build-r2', 'research_only'), ('filing-reconciliation-r3/build-r1', 'research_only'),
                          ('gap-resolution-r4/build-r1', 'research_only'), ('targeted-filings-r5/build-r1', 'research_only')]
        elif layer['layer_id'] == 'L14':
            components = [('build-r1', 'research_only'), ('gap-resolution-r2/build-r2', 'research_only')]
        else:
            components = {
                'L01': [('published-reference-r1', 'exact_existing_receipt_gate_required')],
                'L02': [('build-r5', 'research_only')],
                'L04': [('build-r4', 'research_only'), ('restriction-check-r3', 'research_only')],
                'L05': [('build-r3', 'research_only'), ('condition-assessment-r1', 'research_only'), ('closeout-r1/build-r5', 'research_only')],
                'L06': [('build-r1', 'research_only'), ('build-cost-r1', 'research_only')],
                'L07': [('build-r1', 'research_only'), ('identity-build-r1', 'research_only'), ('location-build-r4', 'research_only'), ('closeout-r1', 'research_only')],
                'L09': [('build-r4', 'research_only')],
                'L11': [('build-r2', 'research_only')],
                'L12': [('build-r2', 'research_only')],
                'L13': [('build-r1', 'research_only')],
                'L15': [('build-r1', 'research_only')],
            }[layer['layer_id']]
        layer_directory = next(Path(*Path(item).parts[:3]) for item in layer['current_artifacts'] if item.startswith('docs/data/'))
        component_bindings = []
        for ordinal, (name, acceptance) in enumerate(components):
            directory = root / layer_directory / name
            choices = [directory / 'manifest.json', directory / 'build-manifest.json', directory / 'freeze.json']
            if layer['layer_id'] == 'L15':
                choices.append(root / layer_directory / 'manifest.json')
            control = next((path for path in choices if path.is_file()), None)
            component_bindings.append({'component': name, 'path': (layer_directory / name).as_posix(),
                                       'role': 'selected_base' if ordinal == 0 else 'selected_additive_component',
                                       'acceptance_boundary': acceptance,
                                       'control_path': control.relative_to(root).as_posix() if control else None,
                                       'control_sha256': sha256_file(control) if control else None})
        catalog_artifacts = {item['path']: item for item in catalog['artifacts']}
        for value in seeds.values():
            path = root / value['path']
            if path.is_file() and not _forbidden(path, root):
                value['sha256'] = sha256_file(path)
                value['bytes'] = path.stat().st_size
                prior = catalog_artifacts.get(value['path'])
                if prior and prior.get('sha256'):
                    value['catalog_sha256'] = prior['sha256']
                    value['catalog_sha256_matches'] = prior['sha256'] == value['sha256']
        layers.append({"layer_id": layer['layer_id'], "revision": layer['current_revision'],
                       "acceptance_status": layer['acceptance_status'], "scope": layer['scope'],
                       "allowed_outputs": layer['allowed_demo_use'], "held_outputs": layer['held_use'],
                       "components": component_bindings,
                       "seeds": sorted(seeds.values(), key=lambda item: item['path'])})
    binding = {"schema": "daylight-source-composition/1", "reference_year": 2026,
               "catalog_path": CATALOG_PATH, "catalog_sha256": sha256_file(root / CATALOG_PATH),
               "consumer_release_enabled": False, "personal_recommendations_enabled": False,
               "layers": layers}
    binding['composition_digest'] = digest_json(binding)
    return binding


def build_source_closure(root: Path | str, composition_path: Path | str | None = None, progress=None) -> dict[str, Any]:
    root = Path(root).resolve()
    composition = load_json(Path(composition_path)) if composition_path else make_composition(root)
    queue: deque[tuple[str, str, str, str | None, str, str]] = deque()
    queued: set[tuple[str, str, str, str | None, str]] = set()
    for layer in composition['layers']:
        for seed in layer['seeds']:
            queue.append((layer['layer_id'], '<composition>', seed['path'], seed.get('sha256'),
                          'selected_seed', seed['path']))
    artifacts: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    policies: dict[str, dict[str, Any]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    missing: dict[str, dict[str, Any]] = {}
    excluded: dict[str, dict[str, Any]] = {}
    inspected: set[tuple[str, str]] = set()
    hashes: dict[Path, str] = {}
    resolved_references = {}
    parsed_references: dict[str, list[tuple[str, str | None, str, str]]] = defaultdict(list)
    reference_markers = set()
    parsed_paths = set()
    alias_resolutions = {}

    def file_hash(path: Path) -> str:
        path = path.resolve()
        if path not in hashes:
            hashes[path] = sha256_file(path)
        return hashes[path]
    # Hash-only parent references are resolved through control manifests in approved layer packets.
    control_hash_index: dict[str, list[str]] = defaultdict(list)
    selected_layer_roots = set()
    for layer in composition['layers']:
        for seed in layer['seeds']:
            parts = Path(seed['path']).parts
            if len(parts) >= 3 and parts[:2] == ('docs', 'data'):
                selected_layer_roots.add(root.joinpath(*parts[:3]))
    for directory in sorted(selected_layer_roots):
        for path in sorted(directory.rglob('*.json')):
            if any(word.lower() in path.name.lower() for word in CONTROL_WORDS) and not _forbidden(path, root):
                control_hash_index[file_hash(path)].append(path.relative_to(root).as_posix())

    def add_missing(item: dict[str, Any]) -> None:
        missing[digest_json(item)] = item

    def resolve(original: str, source: str, expected: str | None, hint: str) -> Path:
        candidate = Path(original)
        if candidate.is_absolute():
            return candidate
        if original.startswith(('docs/', 'cms-slice/', 'plans/')):
            return root / candidate
        parent = root / source
        parent = parent if parent.is_dir() else parent.parent
        choices = [parent / candidate]
        if hint.startswith('code') or original.endswith('.py'):
            choices = [parent / 'code' / candidate, parent / candidate, root / 'cms-slice/scripts' / candidate]
        if original.startswith('raw/') and hint == 'raw_relative_path':
            choices.insert(0, parent / 'acquisition' / candidate)
        if original.startswith('data-sources/'):
            choices.append(root / 'cms-slice' / candidate)
        for ancestor in list(parent.parents)[:4]:
            if ancestor == root or root in ancestor.parents:
                choices.append(ancestor / candidate)
        existing = [path for path in choices if path.exists() and not _forbidden(path, root)]
        # Bare code filenames denote a sealed code copy when present.
        if expected:
            for path in existing:
                if path.is_file() and file_hash(path) == expected:
                    return path
        if not expected and len(candidate.parts) == 1 and not existing:
            # A bare PA/ST filename is a packet-local alias only when the same
            # manifest cryptographically binds this referring document and the
            # exact approved source_inputs path. No name-only evidence join.
            manifest = parent / 'manifest.json'
            referring = root / source
            if manifest.is_file() and not _forbidden(manifest, root) and referring.is_file():
                declared = load_json(manifest)
                if declared.get('files', {}).get(referring.name) == file_hash(referring):
                    inputs = declared.get('source_inputs', {})
                    matches = [(Path(name), digest) for name, digest in inputs.items()
                               if Path(name).name == candidate.name and isinstance(digest, str) and HASH.fullmatch(digest)]
                    if len(matches) == 1:
                        target, wanted = matches[0]
                        if not target.is_absolute():
                            target = root / target
                        if not _forbidden(target, root) and target.is_file() and file_hash(target) == wanted:
                            alias_resolutions[(source, original, hint)] = {
                                'alias_manifest_path': manifest.relative_to(root).as_posix(),
                                'alias_manifest_sha256': file_hash(manifest),
                                'alias_declared_source_input': matches[0][0].as_posix(),
                                'alias_expected_sha256': wanted,
                                'resolution_basis': 'exact_packet_manifest_source_input_alias'}
                            return target
        if expected and len(candidate.parts) == 1 and not existing:
            matches = [root / item['original_path'] for item in artifacts.values()
                       if Path(item['original_path']).name == candidate.name and item['sha256'] == expected]
            if matches:
                return sorted(matches)[0]
        return existing[0] if existing else choices[0]

    def enqueue(layer: str, source: str, original: str, expected: str | None, relation: str, location: str) -> None:
        marker = (layer, source, original, expected, relation)
        if marker not in queued:
            queued.add(marker)
            queue.append((layer, source, original, expected, relation, location))
        reference_marker = (source, original, expected, relation)
        if reference_marker not in reference_markers:
            reference_markers.add(reference_marker)
            parsed_references[source].append((original, expected, relation, location))

    def inspect(value: Any, layer: str, source: str, trail: tuple[str, ...] = ()) -> None:
        if isinstance(value, list):
            for ordinal, child in enumerate(value):
                inspect(child, layer, source, trail + (str(ordinal),))
            return
        if not isinstance(value, dict):
            return
        # Preserve clocks, publisher/edition, permission and member-range evidence exactly as declared.
        selected_meta = {key: item for key, item in value.items() if key in {
            'source_id', 'id', 'publisher', 'edition', 'version', 'reference_id', 'benefit_year', 'reference_year', 'year', 'source_period', 'name',
            'effective_from', 'effective_until', 'retrieved_at_utc', 'captured_at_utc', 'observed_at_utc',
            'source_review_after_utc', 'review_after_utc', 'requested_url', 'final_url', 'url',
            'content_type', 'last_modified', 'allowed_use', 'use', 'source_use', 'status',
            'http_status', 'acquisition_method', 'method', 'range', 'ranges', 'members', 'member',
            'member_sha256', 'archive_sha256', 'sha256', 'bytes'} and not isinstance(item, (dict, list))}
        if any(key in selected_meta for key in ('requested_url', 'final_url', 'url', 'allowed_use', 'member_sha256')) or ('members' in trail and 'name' in selected_meta):
            item = {'layer_id': layer, 'source_path': source, 'json_pointer': '/' + '/'.join(trail), 'declared': selected_meta}
            metadata.setdefault(digest_json([layer, source, selected_meta]), item)
        for key, child in value.items():
            location = '/' + '/'.join(trail + (str(key),))
            lower = key.lower()
            if any(token in lower for token in ('stop', 'hold', 'access_policy', 'allowed_use', 'source_use', 'permission')) or (isinstance(child, str) and 'STOP' in child):
                if not isinstance(child, (dict, list)):
                    policy = {'layer_id': layer, 'source_path': source, 'json_pointer': location,
                              'policy_key': key, 'declared_value': child}
                    policies.setdefault(digest_json([layer, source, key, child]), policy)
            # Hash maps preserve original relative/absolute spelling and original expected bytes.
            map_context = trail[-1].lower() if trail else ''
            hash_value = child if isinstance(child, str) and HASH.fullmatch(child) else (
                child.get('sha256') if isinstance(child, dict) else None)
            is_file_map = (map_context in {'files', 'files_sha256', 'code', 'code_sha256', 'evidence_sha256',
                                          'inputs', 'input_sha256', 'external_inputs', 'outputs',
                                          'transformation_dependencies', 'protected_files', 'source_inputs'} or
                           (map_context == 'metadata_receipts' and isinstance(child, dict) and 'sha256' in child) or
                           (isinstance(child, str) and HASH.fullmatch(child) and key.startswith(('docs/', 'cms-slice/', 'plans/', '/'))))
            if hash_value and HASH.fullmatch(str(hash_value)) and is_file_map and (
                    '/' in key or '.' in key or key.startswith('/')):
                enqueue(layer, source, key, hash_value, map_context or 'hash_map', location)
            if isinstance(child, str) and _pathlike(child, key) and key not in {'member', 'name', 'filename', 'source_member', 'companion_member'} and (key != 'file' or value.get('sha256') or child.startswith(('docs/', 'cms-slice/', 'plans/', '/Users/'))):
                expected = value.get(key + '_sha256')
                if key in {'path', 'raw_path', 'file', 'local_path', 'raw_relative_path'}:
                    expected = value.get('sha256', expected)
                if key in {'manifest', 'package', 'build'}:
                    expected = value.get('manifest_sha256', value.get('package_manifest_sha256', expected))
                enqueue(layer, source, child, expected if isinstance(expected, str) and HASH.fullmatch(expected) else None,
                        key, location)
            if isinstance(child, str) and HASH.fullmatch(child) and ('manifest_sha256' in key or key.endswith('freeze_sha256')):
                candidates = control_hash_index.get(child, [])
                if candidates:
                    # Retain every byte-identical declared control location, never modify a source pointer.
                    for candidate in candidates:
                        enqueue(layer, source, candidate, child, 'hash_bound_control:' + key, location)
                elif key.startswith('parent'):
                    add_missing({'layer_id': layer, 'source_path': source, 'original_reference': key,
                                 'expected_sha256': child, 'status': 'unresolved_hash_only_parent', 'json_pointer': location})
            inspect(child, layer, source, trail + (str(key),))

    processed_edges = 0
    while queue:
        layer, source, original, expected, relation, location = queue.popleft()
        processed_edges += 1
        if progress and processed_edges % 10000 == 0:
            progress({'processed': processed_edges, 'queued': len(queue), 'artifacts': len(artifacts), 'current': source})
        reference_key = (original, source, expected, relation)
        if reference_key not in resolved_references:
            resolved_references[reference_key] = resolve(original, source, expected, relation)
        path = resolved_references[reference_key]
        edge = {'layer_id': layer, 'from_path': source, 'original_reference': original,
                'expected_sha256': expected, 'relation': relation, 'json_pointer': location}
        exclusion = _exclusion(path, root)
        if exclusion:
            edge['status'] = exclusion
            excluded[digest_json(edge)] = edge
            edges[digest_json(edge)] = edge
            continue
        relative = path.resolve().relative_to(root).as_posix()
        edge['resolved_path'] = relative
        edge['resolution_basis'] = 'declared_locator_or_matching_sealed_code_copy'
        if expected and len(Path(original).parts) == 1 and Path(source).parent / original != Path(relative):
            edge['resolution_basis'] = 'exact_hash_and_basename_from_declared_artifact_or_sealed_code' 
        if not path.exists():
            edge['status'] = 'missing_dependency'
            add_missing(edge)
            edges[digest_json(edge)] = edge
            continue
        if path.is_dir():
            if expected:
                matched_controls = [child for child in _control_files(path) if file_hash(child) == expected]
                if not matched_controls:
                    add_missing(dict(edge, status='directory_pointer_hash_unresolved', resolved_path=relative))
                else:
                    edge['matched_control_path'] = matched_controls[0].relative_to(root).as_posix()
            edge['status'] = 'directory_control_expanded'
            edges[digest_json(edge)] = edge
            for child in _control_files(path):
                enqueue(layer, relative, child.relative_to(root).as_posix(), None, 'directory_control', '')
            continue
        if relative not in artifacts:
            actual = file_hash(path)
            artifacts[relative] = {'original_path': relative, 'absolute_original_path': str(path.resolve()),
                                   'bytes': path.stat().st_size, 'sha256': actual,
                                   'object_key': f'evidence/sha256/{actual[:2]}/{actual}',
                                   'mime': _mime(path), 'mime_basis': 'extension_or_magic_else_octet_stream',
                                   'layer_role': 'source_parser_code' if path.suffix == '.py' else ('original_source_bytes' if '/raw/' in relative else 'evidence_or_control'),
                                   'layer_ids': [], 'metadata_state': 'declared_metadata_preserved_separately_no_inferred_clock',
                                   'source_use_state': 'existing_policy_and_exact_review_required'}
        artifact = artifacts[relative]
        if layer not in artifact['layer_ids']:
            artifact['layer_ids'].append(layer)
        alias = alias_resolutions.get((source, original, relation))
        if alias:
            edge.update(alias)
            enqueue(layer, source, alias['alias_manifest_path'], alias['alias_manifest_sha256'], 'verified_alias_manifest', location)
        edge['actual_sha256'] = artifact['sha256']
        edge['status'] = 'hash_mismatch' if expected and expected != artifact['sha256'] else 'resolved'
        edges[digest_json(edge)] = edge
        if edge['status'] == 'hash_mismatch':
            add_missing(edge)
        marker = (layer, relative)
        if marker in inspected:
            continue
        inspected.add(marker)
        if relative in parsed_paths:
            for ref, wanted, kind, pointer in parsed_references[relative]:
                enqueue(layer, relative, ref, wanted, kind, pointer)
            continue
        parsed_paths.add(relative)
        if path.suffix.lower() == '.json':
            try:
                inspect(load_json(path), layer, relative)
            except (ValueError, UnicodeError) as error:
                add_missing({'layer_id': layer, 'source_path': relative, 'status': 'unparsed_structured_dependency',
                             'error_type': type(error).__name__})
        # JSONL records retain declared dependencies per row with bounded working memory.
        elif path.name.endswith(('.jsonl', '.jsonl.gz')):
            opener = gzip.open if path.name.endswith('.gz') else open
            try:
                with opener(path, 'rt', encoding='utf-8') as handle:
                    for ordinal, line in enumerate(handle, 1):
                        if line.strip() and any(token in line for token in (
                                'docs/', 'cms-slice/', 'plans/', '/Users/', '/private/', '/tmp/',
                                '"path"', '_path"', '"manifest"', '"files"', '"inputs"',
                                '"allowed_use"', '"source_use"', '"permissions"', 'STOP')):
                            inspect(json.loads(line), layer, relative, ('line', str(ordinal)))
            except (ValueError, UnicodeError, OSError) as error:
                add_missing({'layer_id': layer, 'source_path': relative, 'status': 'unparsed_structured_dependency',
                             'error_type': type(error).__name__})
    artifact_list = sorted(artifacts.values(), key=lambda item: item['original_path'])
    for item in artifact_list:
        item['layer_ids'].sort()
    unique = {item['sha256']: item['bytes'] for item in artifact_list}
    report = {'schema': 'daylight-source-closure/1', 'composition_digest': composition['composition_digest'],
              'reference_year': 2026, 'mode': 'read_only_declared_structured_dependency_closure',
              'consumer_release_enabled': False, 'personal_recommendations_enabled': False,
              'summary': {'layers': len(composition['layers']), 'logical_files': len(artifact_list),
                          'logical_bytes': sum(item['bytes'] for item in artifact_list),
                          'unique_objects': len(unique), 'unique_object_bytes': sum(unique.values()),
                          'dependency_edges': len(edges), 'unresolved_or_mismatched_edges': len(missing),
                          'policy_observations': len(policies), 'excluded_reference_edges': len(excluded)},
              'artifacts': artifact_list, 'dependencies': sorted(edges.values(), key=canonical_json),
              'missing_dependencies': sorted(missing.values(), key=canonical_json),
              'excluded_references': sorted(excluded.values(), key=canonical_json),
              'source_policy_observations': sorted(policies.values(), key=canonical_json),
              'declared_source_metadata': sorted(metadata.values(), key=canonical_json),
              'limitations': ['No upstream fetch or permission/source-use acceptance performed.',
                             'Declared ZIP members retain source hashes; member hashes are not whole-archive hashes.',
                             'Code bytes are archived; Python source is not executed or interpreted as a dependency manifest.',
                             'Directory links expand named JSON controls, never copy unrelated or private stores.',
                             'No source publication/effective/capture clock is invented when absent.',
                             'Unresolved paths/hashes remain blockers to claiming a complete archived closure.']}
    report['closure_digest'] = digest_json_streamed(report)
    return report


def write_closure_report(report: dict[str, Any], index_path: Path) -> dict[str, Any]:
    """Stream deterministic gzip plus a small index, never materialize serialized report."""
    archive_path = Path(str(index_path) + '.gz')
    uncompressed_hash = hashlib.sha256()
    uncompressed_bytes = 0
    encoder = json.JSONEncoder(indent=2, default=str)
    with archive_path.open('wb') as output:
        with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0, compresslevel=6) as archive:
            chunks, size = [], 0
            for part in encoder.iterencode(report):
                chunks.append(part)
                size += len(part)
                if size >= 262144:
                    content = ''.join(chunks).encode()
                    uncompressed_hash.update(content)
                    uncompressed_bytes += len(content)
                    archive.write(content)
                    chunks, size = [], 0
            content = (''.join(chunks) + '\n').encode()
            uncompressed_hash.update(content)
            uncompressed_bytes += len(content)
            archive.write(content)
    gaps = {'schema': 'daylight-source-closure-gaps/1', 'composition_digest': report['composition_digest'],
            'closure_digest': report['closure_digest'], 'missing_dependencies': report['missing_dependencies'],
            'excluded_references': report['excluded_references'], 'source_evidence_modified': False,
            'closure_complete': False if report['missing_dependencies'] else True}
    gaps_path = index_path.with_name('source-closure-gaps.json')
    gaps_path.write_text(json.dumps(gaps, indent=2) + '\n')
    index = {'schema': 'daylight-source-closure-index/1', 'reference_year': 2026,
             'composition_digest': report['composition_digest'], 'closure_digest': report['closure_digest'],
             'summary': report['summary'], 'closure_complete': gaps['closure_complete'],
             'full_report': {'path': archive_path.name, 'sha256': sha256_file(archive_path),
                             'bytes': archive_path.stat().st_size, 'gzip_mtime': 0,
                             'uncompressed_sha256': uncompressed_hash.hexdigest(),
                             'uncompressed_bytes': uncompressed_bytes},
             'gap_report': {'path': gaps_path.name, 'sha256': sha256_file(gaps_path)},
             'consumer_release_enabled': False, 'personal_recommendations_enabled': False,
             'limitations': report['limitations']}
    index_path.write_text(json.dumps(index, indent=2) + '\n')
    return index


def main():
    import argparse
    import resource
    import sys
    import time
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path, required=True)
    parser.add_argument('--composition', type=Path)
    parser.add_argument('--write-composition', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--progress', action='store_true')
    args = parser.parse_args()
    if args.write_composition:
        args.write_composition.write_text(json.dumps(make_composition(args.repository_root), indent=2) + '\n')
    started = time.monotonic()
    report = build_source_closure(args.repository_root, args.composition,
                                  progress=(lambda item: print(canonical_json(item), flush=True)) if args.progress else None)
    index = write_closure_report(report, args.output)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak if sys.platform == 'darwin' else peak * 1024
    metrics = {'schema': 'daylight-source-closure-run-metrics/1', 'closure_digest': report['closure_digest'],
               'elapsed_seconds': round(time.monotonic() - started, 3), 'peak_rss_bytes': peak,
               'worker_memory_target_bytes': 512 * 1024 * 1024,
               'meets_worker_memory_target': peak <= 512 * 1024 * 1024,
               'meaning': 'Local audit process measurement; not deployment or ingestion throughput'}
    args.output.with_name('source-closure-run-metrics.json').write_text(json.dumps(metrics, indent=2) + '\n')
    print(canonical_json({'summary': index['summary'], 'closure_digest': report['closure_digest'], 'metrics': metrics}))


if __name__ == '__main__':
    main()
