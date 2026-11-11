"""Pin query selection to completed immutable local-build controls, not 'latest'."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re

VERSION = 'collier-research-serving-r1'
PACKET = 'docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3'
SCOPE = {'year': 2026, 'state': 'FL', 'county_fips': '12021', 'category': 'medicare_advantage'}
SELECTION = {
    'collier': ('L02', 'collier_offerings', '/build-r5/12021/'),
    'national': ('L02', 'offerings', '/build-r5/'),
    'semantic': ('L03', 'semantic_unit', '/semantic-inventory-r9/'),
    'quality': ('L09', 'observations', '/build-r4/'),
    'quality_binding': ('L09', 'offerings', '/build-r4/'),
}


class ResearchServingError(ValueError):
    """Fixed-code failures must not contain source text, DSNs or personal data."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _json(root, path):
    if (path.is_symlink() or not path.resolve().is_relative_to(root)
            or not path.is_file() or path.stat().st_size > 8 * 1024**2):
        raise ResearchServingError('PINNED_CONTROL_UNAVAILABLE')
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ResearchServingError('PINNED_CONTROL_SYMLINK')
    data = path.read_bytes()
    try:
        return json.loads(data), hashlib.sha256(data).hexdigest()
    except (TypeError, ValueError):
        raise ResearchServingError('PINNED_CONTROL_INVALID') from None


@dataclass(frozen=True)
class ResearchBinding:
    build_id: str
    database: str
    manifest_sha256: str
    target: dict
    selections: dict
    unit_receipts: tuple
    control_hashes: dict
    adapter_sha256: str

    @property
    def binding_id(self):
        return digest({'version': VERSION, 'build_id': self.build_id,
                       'manifest_sha256': self.manifest_sha256,
                       'selections': self.selections, 'controls': self.control_hashes,
                       'adapter_sha256': self.adapter_sha256})


def load_local_binding(repository_root, packet=PACKET, *, selection=None):
    root = Path(repository_root).resolve()
    directory = root / packet
    manifest, manifest_hash = _json(root, directory / 'BUILD_MANIFEST.json')
    target, target_hash = _json(root, directory / 'TARGET.json')
    complete, complete_hash = _json(root, directory / 'LOAD_COMPLETE.json')
    build_id = digest(manifest)
    if (manifest.get('schema') != 'daylight-local-full-build/2'
            or target.get('build_id') != build_id or complete.get('build_id') != build_id
            or manifest.get('database') != target.get('database')
            or complete.get('target') != target
            or manifest.get('consumer_release_enabled') is not False
            or complete.get('consumer_release_enabled') is not False
            or manifest.get('new_acceptance') is not False or complete.get('new_acceptance') is not False
            or complete.get('source_rows') != 17767179 or complete.get('projection_rows') != 17823148
            or complete.get('unit_receipts') != 363):
        raise ResearchServingError('COMPLETED_BUILD_BINDING_MISMATCH')
    hashes = {'BUILD_MANIFEST.json': manifest_hash, 'TARGET.json': target_hash,
              'LOAD_COMPLETE.json': complete_hash}
    required = SELECTION if selection is None else selection
    selections, receipts = {}, []
    # These are the 363 declared execution receipts, not a scan of source trees.
    files = sorted((directory / 'units').glob('*.json'))
    if len(files) != 363:
        raise ResearchServingError('UNIT_RECEIPT_ACCOUNTING_MISMATCH')
    for path in files:
        receipt, receipt_hash = _json(root, path)
        binding = receipt.get('binding', {})
        matches = [key for key, (layer, table, part) in required.items()
                   if binding.get('layer_id') == layer and binding.get('source_table') == table
                   and part in binding.get('source_path', '')]
        if not matches:
            continue
        if (receipt.get('build_id') != build_id or receipt.get('database_verified') is not True
                or receipt.get('new_acceptance') is not False or path.stem != receipt.get('selected_slot')
                or not re.fullmatch('[a-f0-9]{64}', binding.get('derivation_id', ''))
                or manifest['selected_source_files'].get(binding.get('source_path')) != binding.get('source_sha256')):
            raise ResearchServingError('SELECTED_UNIT_RECEIPT_MISMATCH')
        native = {key: binding[key] for key in ('layer_id', 'source_path', 'source_table',
                                               'source_sha256', 'derivation_id', 'adapter_code_sha256')}
        for key in matches:
            if key in selections and selections[key] != native:
                raise ResearchServingError('AMBIGUOUS_SELECTED_DERIVATION')
            selections[key] = native
        receipts.append({'job_id': receipt['job_id'], 'source_rows': receipt['source_rows'],
                         'stream_sha256': receipt['stream_sha256'], 'selected_slot': receipt['selected_slot']})
        hashes['units/' + path.name] = receipt_hash
    if set(selections) != set(required):
        raise ResearchServingError('REQUIRED_DERIVATION_ABSENT')
    code_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(Path(__file__).parent.glob('*.py'))}
    return ResearchBinding(build_id, target['database'], manifest_hash, target, selections,
                           tuple(receipts), hashes, digest(code_hashes))
