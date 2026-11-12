"""Read only the D129/D134 display subset. No fallback to the research DB."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from daylight_data.csg_medigap.store import Repository as CsgRepository, connect
from daylight_data.plan_types.common import code_binding, digest, file_sha, runtime_binding

CSG_BUILD = '7be76407ca94d33223ec0144bac16f2e220fba0205496bdf05577a42ab32831f'
PDP_BUILD = 'b6992365031d7e3bc3253651b21d924e9d160d7a2c6511e1cab96eb9d782c15c'
KINDS = {'pdp_offering': 10, 'pdp_county': 1, 'pdp_restriction': 10}


def implementation_binding():
    return {p.name: file_sha(p) for p in sorted(Path(__file__).parent.iterdir())
            if p.suffix in {'.py', '.sql'}}


class Snapshot:
    def __init__(self, factory, expected):
        self.factory, self.expected = factory, expected

    @contextmanager
    def read(self, scope):
        with self.factory() as c, c.transaction():
            c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            c.execute('SET LOCAL ROLE daylight_plan_research_reader')
            row = c.execute('SELECT snapshot_id,manifest FROM dl_pilot.snapshot').fetchone()
            if not row or row['snapshot_id'] != self.expected or digest(row['manifest']) != self.expected:
                raise RuntimeError('PILOT_SNAPSHOT_MISMATCH')
            m = row['manifest']
            if (m['schema'] != 'collier-display-subset/1' or m['implementation'] != implementation_binding()
                    or m['csg_build'] != CSG_BUILD or m['pdp_build'] != PDP_BUILD
                    or m['consumer_release'] != 'held'):
                raise RuntimeError('PILOT_BINDING_MISMATCH')
            if c.execute("SELECT 1 FROM dl_pilot.stop_event WHERE scope IN ('all',%s) LIMIT 1", (scope,)).fetchone():
                raise RuntimeError('SOURCE_STOP')
            yield c, m


class MedigapRepository:
    def __init__(self, snapshot, repository):
        self.snapshot, self.repository = snapshot, repository

    def query(self, **kwargs):
        with self.snapshot.read('medigap'):
            return self.repository.query(**kwargs)

    def status(self):
        with self.snapshot.read('medigap'):
            return self.repository.status()


class PdpRepository:
    """Exact three-query transport cache; never exposes a partial research build."""
    def __init__(self, snapshot, now=None):
        self.snapshot = snapshot
        self.now = now or (lambda: datetime.now(timezone.utc))

    def query(self, request):
        if (not isinstance(request, dict) or set(request) != {
                'reference_year', 'county_fips', 'intended_use', 'kind', 'page_size'}
                or type(request['reference_year']) is not int or request['reference_year'] != 2026
                or request['county_fips'] != '12021'
                or request['intended_use'] != 'developer_source_inspection'
                or request['kind'] not in KINDS or type(request['page_size']) is not int
                or request['page_size'] != 100):
            raise ValueError('UNSUPPORTED_PILOT_QUERY')
        with self.snapshot.read('pdp') as (c, m):
            source = m['pdp_source_manifest']
            if (digest({k: v for k, v in source.items() if k != 'build_id'}) != PDP_BUILD
                    or source['code'] != code_binding() or source['runtime'] != runtime_binding()):
                raise RuntimeError('RUNTIME_BINDING_MISMATCH')
            row = c.execute('SELECT payload FROM dl_pilot.pdp_response WHERE kind=%s',
                            (request['kind'],)).fetchone()
            if not row or digest(row['payload']) != m['pdp_response_sha256'][request['kind']]:
                raise RuntimeError('PILOT_PAYLOAD_MISMATCH')
            value = row['payload']
            if (value['build_id'] != PDP_BUILD or value['next_after'] is not None
                    or len(value['records']) != KINDS[request['kind']]):
                raise RuntimeError('PILOT_POPULATION_MISMATCH')
            # Never freeze freshness at export time. Keep the original earliest deadline.
            value['source_review_due'] = self.now() >= min(
                datetime.fromisoformat(v) for v in source['review_due'].values())
            return value


def repositories(binding_path, *, dsn=None):
    binding = json.loads(Path(binding_path).read_text())
    if binding.get('schema') != 'collier-display-binding/1':
        raise ValueError('INVALID_PILOT_BINDING')
    database = binding['database']
    if not database.startswith('daylight_pilot_'):
        raise ValueError('PILOT_DATABASE_REQUIRED')
    # Credentials are runtime configuration and never written into the binding.
    dsn = dsn or os.environ.get('DAYLIGHT_PILOT_DATABASE_URL')
    if not dsn:
        raise ValueError('DAYLIGHT_PILOT_DATABASE_URL_REQUIRED')
    factory = lambda: connect(dsn, database, readonly=True)
    snapshot = Snapshot(factory, binding['snapshot_id'])
    medigap = MedigapRepository(snapshot, CsgRepository(factory, CSG_BUILD))
    pdp = PdpRepository(snapshot)
    medigap.status()
    pdp.query({'reference_year': 2026, 'county_fips': '12021',
               'intended_use': 'developer_source_inspection', 'kind': 'pdp_county', 'page_size': 100})
    return medigap, pdp
