"""Exact L01 published-reference access, isolated from the pinned advisor engine.

The original verifier owns acceptance, expiry, revocation and qualifications.
No person, income, charges, rule application or total calculation is accepted.
"""
import json
from pathlib import Path
import subprocess
import sys

from understanding import UnderstandingError

_WORKER = r'''
import hashlib, json, pathlib, sys
try:
    repository = pathlib.Path(sys.argv[1]).resolve()
    scripts = repository / 'cms-slice/scripts'
    sys.path.insert(0, str(scripts))
    import l01_reference as reference
    if pathlib.Path(reference.__file__).resolve() != scripts / 'l01_reference.py':
        raise ValueError('Unexpected module')
    files = {'module': pathlib.Path(reference.__file__),
             'manifest': reference.PACKAGE / 'manifest.json', 'review': reference.REGISTRY,
             **{name: reference.PACKAGE / name for name in ('costs.json', 'bands.json',
                 'notes.json', 'observations.json', 'sources.json', 'conflicts.json')}}
    before = {name: path.read_bytes() for name, path in files.items()}
    result = reference.lookup(json.loads(sys.stdin.read()), research=False)
    reference.verify(reference.PACKAGE)
    reference.require_review(reference.PACKAGE, reference.REGISTRY)
    if (result['schema'] != 'l01-published-result/1' or result['year'] != 2026
            or result['mode'] != 'accepted_published_reference'
            or any(result[k] is not False for k in ('personal_applicability_determined',
                  'personal_total_available', 'recommendations_available'))
            or any(path.read_bytes() != before[name] for name, path in files.items())):
        raise ValueError('Reference boundary changed')
    print(json.dumps({'ok': True, 'reference': result,
        'binding': {name: hashlib.sha256(raw).hexdigest() for name, raw in before.items()}},
        ensure_ascii=False, allow_nan=False))
except Exception:
    print(json.dumps({'ok': False}))
'''


class PublishedCostReference:
    def __init__(self, repository=None):
        self.repository = Path(repository).resolve() if repository else Path(__file__).resolve().parents[2]

    def lookup(self, request):
        if (not isinstance(request, dict) or set(request) - {'year', 'ids'}
                or type(request.get('year')) is not int or request['year'] != 2026
                or 'ids' in request and (not isinstance(request['ids'], list)
                    or not 1 <= len(request['ids']) <= 78
                    or any(not isinstance(item, str) or not 1 <= len(item) <= 128 for item in request['ids'])
                    or len(set(request['ids'])) != len(request['ids']))):
            raise UnderstandingError('PUBLISHED_COST_REFERENCE_REQUEST_INVALID')
        try:
            worker = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', _WORKER, str(self.repository)],
                input=json.dumps(request), capture_output=True, text=True, encoding='utf-8',
                cwd=self.repository, env={}, timeout=30, check=False)
            if worker.returncode != 0 or len(worker.stdout.encode()) > 4 * 1024 * 1024:
                raise UnderstandingError('PUBLISHED_COST_REFERENCE_HELD')
            value = json.loads(worker.stdout)
            if value.get('ok') is not True:
                raise UnderstandingError('PUBLISHED_COST_REFERENCE_HELD')
            return {'purpose': 'published_reference_lookup',
                'personal_authority': 'held', 'reference': value['reference'], 'binding': value['binding']}
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise UnderstandingError('PUBLISHED_COST_REFERENCE_HELD') from None
