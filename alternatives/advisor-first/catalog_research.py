"""Read the sealed D91 catalog for local research."""

from hashlib import sha256
import json
from pathlib import Path

from comparison_research import validate_research_scope


CATALOG_PATH = (Path(__file__).resolve().parents[2] / 'docs/product'
                / 'recommendation-scope-2026-11-04-r5/catalog.json')
CATALOG_SHA256 = '2c0198a2b848a26e09440e3daf1355c0ec5e45b107ef7de63784cd48f1aa3756'
CRITICAL_BENEFITS_PATH = (CATALOG_PATH.parent.parent
                          / 'recommendation-scope-2026-11-04-r10/critical-benefits.json')
CRITICAL_BENEFITS_SHA256 = 'b677e66bd53d429d0e1aa7d1a563401d274f9fc95aee65c0a907a8e3b1cdd5a1'


def source_refs(value):
    if isinstance(value, dict):
        yield from value.get('source_refs', ())
        for child in value.values():
            yield from source_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from source_refs(child)


class CatalogResearch:
    def __init__(self, path=CATALOG_PATH, *, critical_benefits_path=None):
        self.path = Path(path)
        self.critical_benefits_path = critical_benefits_path

    def query(self, scope, *, offering_id=None, expected_catalog_sha256=None):
        scope = validate_research_scope(scope)
        if expected_catalog_sha256 not in (None, CATALOG_SHA256):
            raise ValueError('CATALOG_VERSION_MISMATCH')
        raw = self.path.read_bytes()
        if sha256(raw).hexdigest() != CATALOG_SHA256:
            raise RuntimeError('CATALOG_INTEGRITY_MISMATCH')
        catalog = json.loads(raw)
        plans = {plan['offering_id']: plan for plan in catalog['plans']}
        result = {
            'status': 'research_only', 'scope': scope,
            'candidate_id': catalog['candidate_id'], 'catalog_sha256': CATALOG_SHA256,
            'total': len(plans), 'purpose': catalog['purpose'],
        }
        if offering_id is None:
            result['plans'] = [{'offering_id': plan['offering_id'], 'name': plan['name'],
                                'coverage': plan['published']['coverage']['value']}
                               for plan in plans.values()]
            return result
        if not isinstance(offering_id, str) or offering_id not in plans:
            raise ValueError('UNKNOWN_CATALOG_OFFERING')
        plan = plans[offering_id]
        sources = {}
        for ref in sorted(set(source_refs(plan))):
            value = catalog['source_bindings']
            for key in ref.split('/'):
                value = value[key]
            sources[ref] = value
        detail = {**result, 'plan': plan, 'sources': sources,
                  'scenario_assumptions': catalog['scenario'], 'methods': catalog['methods']}
        if self.critical_benefits_path is not None:
            raw_benefits = self.critical_benefits_path.read_bytes()
            if sha256(raw_benefits).hexdigest() != CRITICAL_BENEFITS_SHA256:
                raise RuntimeError('CRITICAL_BENEFITS_INTEGRITY_MISMATCH')
            benefits = json.loads(raw_benefits)
            if benefits['inputs']['catalog']['sha256'] != CATALOG_SHA256 or benefits['purpose'] != catalog['purpose']:
                raise RuntimeError('CRITICAL_BENEFITS_SCOPE_MISMATCH')
            detail['critical_benefits_sha256'] = CRITICAL_BENEFITS_SHA256
            detail['critical_benefits'] = benefits['plans'][offering_id]
        return detail
