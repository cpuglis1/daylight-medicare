"""Read-only research bridge. Research identities never grant consumer authority.

This dependency is installed explicitly by the local operator. No customer values,
names, ZIPs, medicines or providers are sent to PostgreSQL: only the exact supported
catalog scope is queried. The ordinary conversation remains independent of it.
"""
from __future__ import annotations

import copy

from comparison_evidence import EvidenceSnapshot


RESEARCH_SCOPE = {'year': 2026, 'state': 'FL', 'county_fips': '12021',
                  'category': 'medicare_advantage'}
RESEARCH_BRIDGE_VERSION = 'advisor-postgres-research-20261101-r1'


def validate_research_scope(scope):
    if type(scope) is not dict or scope != RESEARCH_SCOPE:
        raise ValueError('UNSUPPORTED_RESEARCH_SCOPE')
    # bool is an int subclass, but is not an evidence year.
    if type(scope.get('year')) is not int:
        raise ValueError('UNSUPPORTED_RESEARCH_SCOPE')
    return copy.deepcopy(RESEARCH_SCOPE)


class RepositoryEvidenceSource:
    """A bounded server dependency, not a JSON/client-constructed authority."""

    def __init__(self, repository):
        self.repository = repository

    def snapshot(self, scope):
        validate_research_scope(scope)
        plans, after, binding = [], None, None
        for _ in range(5):
            page = self.repository.list_plans(
                scope, after_ordinal=after, limit=20,
                expected_snapshot_id=binding['snapshot_id'] if binding else None)
            if page.get('status') != 'research_only':
                raise RuntimeError('RESEARCH_BOUNDARY_MISMATCH')
            if binding is not None and binding != page['binding']:
                raise RuntimeError('RESEARCH_SNAPSHOT_CHANGED')
            binding = copy.deepcopy(page['binding'])
            if binding.get('accepted_release_id') is not None:
                raise RuntimeError('RESEARCH_BOUNDARY_MISMATCH')
            plans.extend(page['plans'])
            if not page['page']['has_more']:
                break
            next_after = page['page']['next_after_ordinal']
            if type(next_after) is not int or after is not None and next_after <= after:
                raise RuntimeError('RESEARCH_CURSOR_INVALID')
            after = next_after
        else:
            raise RuntimeError('RESEARCH_POPULATION_LIMIT')
        if len(plans) != page['total'] or len(plans) > 100:
            raise RuntimeError('RESEARCH_POPULATION_MISMATCH')
        units = []
        for plan in plans:
            units.append({
                'unit_id': plan['offering_id'], 'kind': 'cms_offering',
                'display_name': plan['display_name'],
                'identity': copy.deepcopy(plan['identity']),
                'identity_state': 'source_observed_research_only',
                'period': {'year': scope['year']}, 'role': 'medical_plan',
                'source_refs': [copy.deepcopy(plan['lineage'])],
                'restrictions': copy.deepcopy(plan.get('restrictions', [])),
                'evaluation_state': 'held', 'fictional': False,
            })
        return EvidenceSnapshot(
            manifest_id=binding['snapshot_id'],
            serving_build_id=RESEARCH_BRIDGE_VERSION,
            research_build_id=binding['build_id'], source_kind='research_held',
            completeness='partial', units=tuple(units))


def local_repository():
    """Explicit local-only operator entry point; never discover app secrets."""
    import getpass
    from pathlib import Path
    import sys

    root = Path(__file__).resolve().parents[2]
    package = root / 'infrastructure/daylight-data'
    sys.path.insert(0, str(package / 'src'))
    from daylight_data.serving import repository_from_env

    # The checked operating runbook uses this existing private Unix socket.
    # The repository independently verifies DB/OID/cluster/build before reads.
    dsn = ('host=' + str(package / '.state/socket') +
           ' port=55485 dbname=daylight_research_2026_r2 user=' + getpass.getuser())
    return repository_from_env(repository_root=root, dsn=dsn)
