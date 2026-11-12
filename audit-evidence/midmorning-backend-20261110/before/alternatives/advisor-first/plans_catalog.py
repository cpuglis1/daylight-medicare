"""Exact r13 retained catalog. Acquisition, publication and fit stay separate."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'docs/product/recommendation-scope-2026-11-04-r13/display-candidate.json'
SHA256 = 'ba625a2968a53a46dc72dddf52a4e74064b56b0b14e55c9e8768d2b580fa3609'


class PlansCatalog:
    def __init__(self, path=PATH):
        self.path = Path(path)

    def read(self):
        raw = self.path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != SHA256:
            raise ValueError('CATALOG_INTEGRITY_MISMATCH')
        value = json.loads(raw)
        for source in value['inputs'].values():
            parent = (self.path.parent / source['path']).resolve()
            if hashlib.sha256(parent.read_bytes()).hexdigest() != source['sha256']:
                raise ValueError('CATALOG_PARENT_INTEGRITY_MISMATCH')
        ids = [p['display_candidate']['offering_id'] for p in value['plans']]
        if len(ids) != 72 or ids != sorted(set(ids)):
            raise ValueError('CATALOG_IDENTITY_MISMATCH')
        return copy.deepcopy(value)

    def typed(self):
        """Read source-native decimal values, never reverse-parse display prose."""
        catalog = self.read()
        source = catalog['inputs']['scenario_catalog']
        raw = (self.path.parent / source['path']).resolve().read_bytes()
        if hashlib.sha256(raw).hexdigest() != source['sha256']:
            raise ValueError('CATALOG_PARENT_INTEGRITY_MISMATCH')
        value = json.loads(raw)
        ids = [p['offering_id'] for p in value['plans']]
        if ids != [p['display_candidate']['offering_id'] for p in catalog['plans']]:
            raise ValueError('TYPED_CATALOG_IDENTITY_MISMATCH')
        return value
