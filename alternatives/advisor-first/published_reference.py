"""Exact L03 r4 reference reads for the internal developer workspace.

Every call executes the original, unmodified lookup with ``research=False`` in
a fresh isolated interpreter. Nothing here releases a consumer candidate set,
personal result, AI context, or the rest of the research database.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time


VERSION = 'advisor-exact-published-reference-20261101-r1'
PACKAGE_ID = 'L03-PUBLISHED-COLLIER-2026-bounded-r4'
HELD_PURPOSES = ('published_display', 'personal_comparison', 'ranking',
                 'recommendation', 'quote', 'enrollment')
_MAX_OUTPUT_BYTES = 4 * 1024 * 1024


class PublishedReferenceError(RuntimeError):
    """Fixed-code failure; never expose worker exceptions or source values."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class PublishedReferenceRequestError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


# -I/-S/-B isolate this original engine from the advisor's pinned sibling
# modules, PYTHONPATH, user site packages and bytecode writes. The only path
# added by this worker is the explicitly selected repository's original scripts.
_WORKER = r'''
import hashlib, json, pathlib, sys

module = None
try:
    repository = pathlib.Path(sys.argv[1]).resolve()
    scripts = repository / 'cms-slice/scripts'
    sys.path.insert(0, str(scripts))
    import l03_scoped_reference as module
    if pathlib.Path(module.__file__).resolve() != scripts / 'l03_scoped_reference.py':
        raise ValueError('Unexpected original module')
    root, registry = pathlib.Path(module.ROOT), pathlib.Path(module.REGISTRY)
    files = {'original_lookup': pathlib.Path(module.__file__),
             'manifest': root / 'manifest.json', 'review_registry': registry,
             **{name: root / name for name in (
                 'entries.json', 'held-claims.json', 'offering-status.json',
                 'scope.json', 'dispositions.json')}}
    before = {name: path.read_bytes() for name, path in files.items()}
    request = json.loads(sys.stdin.read())
    reference = module.lookup(request, research=False)
    # Original lookup owns all acceptance, ancestor, code, allowlist and
    # revocation verification. This guard only binds the returned read to a
    # stable set of the exact files it consumed; it grants no new authority.
    if any(path.read_bytes() != before[name] for name, path in files.items()):
        print(json.dumps({'ok': False, 'error_code': 'REFERENCE_CHANGED_DURING_REPLAY'}))
        sys.exit(0)
    if (reference.get('package_id') != 'L03-PUBLISHED-COLLIER-2026-bounded-r4'
            or reference.get('mode') != 'accepted_bounded_published_reference'
            or reference.get('accepted_for_reference') is not True
            or (reference.get('offering') or {}).get('offering_id') != request['offering_id']
            or any(hold.get('value') is not None or hold.get('state') != 'unknown_held'
                   for hold in reference.get('holds', []))):
        raise ValueError('Original reference boundary mismatch')
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in before.items()}
    print(json.dumps({'ok': True, 'reference': reference,
        'accepted_dispositions': json.loads(before['dispositions.json']),
        'review_receipt': json.loads(before['review_registry']),
        'binding': {'package_id': reference['package_id'],
                    'original_module_sha256': hashes['original_lookup'],
                    'manifest_sha256': hashes['manifest'],
                    'review_registry_sha256': hashes['review_registry'],
                    'reference_files_sha256': hashes,
                    'replay': 'original_lookup_research_false_every_request'}},
        ensure_ascii=False, allow_nan=False))
except Exception as error:
    invalid = module is not None and isinstance(error, module.ReferenceError)
    code = 'EXACT_REFERENCE_REQUEST_REJECTED' if invalid else 'REFERENCE_AUTHORITY_HELD'
    print(json.dumps({'ok': False, 'error_code': code}))
'''


class PublishedReferenceAdapter:
    """Server-owned adapter; no registry, time or research-mode client override."""

    def __init__(self, repository_root=None, *, timeout_seconds=30):
        self.repository_root = (Path(repository_root).resolve() if repository_root is not None
                                else Path(__file__).resolve().parents[2])
        if (type(timeout_seconds) not in {int, float}
                or not 0 < timeout_seconds <= 60):
            raise ValueError('REFERENCE_ADAPTER_CONFIGURATION')
        self.timeout_seconds = timeout_seconds

    def lookup(self, offering_id, *, year=2026, entry_ids=None):
        if type(year) is not int or year != 2026:
            raise PublishedReferenceRequestError('EXACT_REFERENCE_YEAR_REQUIRED')
        if (not isinstance(offering_id, str)
                or not re.fullmatch(r'2026:[A-Z][0-9]{4}:[0-9]{3}:[0-9]{3}', offering_id)):
            raise PublishedReferenceRequestError('EXACT_REFERENCE_OFFERING_REQUIRED')
        request = {'year': year, 'offering_id': offering_id}
        if entry_ids is not None:
            if (type(entry_ids) is not list or not 1 <= len(entry_ids) <= 535
                    or any(type(item) is not str or not 1 <= len(item) <= 512 for item in entry_ids)
                    or len(set(entry_ids)) != len(entry_ids)):
                raise PublishedReferenceRequestError('EXACT_REFERENCE_ENTRY_IDS_REQUIRED')
            request['entry_ids'] = list(entry_ids)
        started = time.perf_counter()
        try:
            result = subprocess.run(
                [sys.executable, '-I', '-S', '-B', '-c', _WORKER, str(self.repository_root)],
                input=json.dumps(request, separators=(',', ':')), capture_output=True,
                text=True, encoding='utf-8', timeout=self.timeout_seconds, check=False,
                # Original replay is entirely local/stdlb. Do not forward the
                # live advisor's model credentials or application environment.
                env={}, cwd=self.repository_root,
            )
        except subprocess.TimeoutExpired:
            raise PublishedReferenceError('REFERENCE_LOOKUP_TIMEOUT') from None
        except (OSError, ValueError):
            raise PublishedReferenceError('REFERENCE_VERIFIER_UNAVAILABLE') from None
        if result.returncode != 0 or len(result.stdout.encode('utf-8')) > _MAX_OUTPUT_BYTES:
            raise PublishedReferenceError('REFERENCE_VERIFIER_UNAVAILABLE')
        try:
            replay = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise PublishedReferenceError('REFERENCE_VERIFIER_UNAVAILABLE') from None
        if not isinstance(replay, dict) or replay.get('ok') is not True:
            code = replay.get('error_code') if isinstance(replay, dict) else None
            if code == 'EXACT_REFERENCE_REQUEST_REJECTED':
                raise PublishedReferenceRequestError(code)
            if code not in {'REFERENCE_AUTHORITY_HELD', 'REFERENCE_CHANGED_DURING_REPLAY'}:
                code = 'REFERENCE_VERIFIER_UNAVAILABLE'
            raise PublishedReferenceError(code)
        binding = {**replay['binding'], 'adapter_version': VERSION,
                   'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        return {
            'contract_id': VERSION, 'purpose': 'reference_lookup',
            'audience': 'internal_research_workspace',
            'request': request, 'binding': binding,
            'reference': replay['reference'],
            'accepted_dispositions': replay['accepted_dispositions'],
            'review_receipt': replay['review_receipt'],
            'authority': {'reference_lookup': {'state': 'accepted_exact_subset',
                            'purpose': 'reference_lookup', 'package_id': PACKAGE_ID},
                          **{purpose: {'state': 'held', 'accepted_release_id': None}
                             for purpose in HELD_PURPOSES}},
            'limitations': [
                '535 exact entries and six conservative dispositions; full L03 remains partial.',
                '153 disputed claims remain held; all 25 restricted offerings remain visible.',
                'Historical candidate flags are preserved, not whole-offering acceptance.',
                'Related schedules, qualifications, units and evidence must remain attached.',
                'Internal reference inspection only; no consumer candidate set or AI context.',
                'Personal applicability, total cost, ranking and recommendations remain held.',
            ],
            'timings': {'elapsed_ms': round((time.perf_counter() - started) * 1000, 3)},
        }
