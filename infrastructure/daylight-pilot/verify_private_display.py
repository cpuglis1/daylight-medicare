#!/usr/bin/env python3
"""Read-only Linux restore verification; no conversations or provider calls."""
import hashlib
import json
import sys

from restore_private_display import DB, RELEASE, SOCKET, STATE, postgres, sql


def main():
    sys.path.insert(0, str(RELEASE / 'infrastructure/daylight-data/src'))
    from daylight_data.plan_types.common import code_binding, digest, runtime_binding
    from daylight_data.csg_medigap import store as csg
    manifest = json.loads((RELEASE / 'evidence/manifest.json').read_text())
    binding = json.loads((RELEASE / 'evidence/binding.json').read_text())
    assert digest(manifest) == binding['snapshot_id']
    assert sql('SELECT snapshot_id FROM dl_pilot.snapshot', DB) == binding['snapshot_id']
    assert json.loads(sql('SELECT manifest::text FROM dl_pilot.snapshot', DB)) == manifest
    source = manifest['pdp_source_manifest']
    assert source['runtime'] == runtime_binding() and source['code'] == code_binding()
    csg_manifest = json.loads(sql('SELECT manifest::text FROM dl_csg_medigap.build', DB))
    assert csg_manifest['runtime'] == csg.runtime_binding() and csg_manifest['code'] == csg.code_binding()
    keys = {'schema_revision': 'singleton', 'build': 'build_id',
            'source': 'build_id,source_sha256', 'rate': 'build_id,id',
            'benefit': 'build_id,source_sha256,variant', 'completion': 'build_id',
            'selection_event': 'event_id', 'stop_event': 'event_id'}
    hashes = {}
    for table, order in keys.items():
        query = f"SET timezone='UTC'; COPY (SELECT to_jsonb(t)::text FROM dl_csg_medigap.{table} t ORDER BY {order}) TO STDOUT"
        output = postgres('psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-h', str(SOCKET),
                          '-p', '55485', '-d', DB, '-c', query)
        hashes[table] = {'rows': int(sql(f'SELECT count(*) FROM dl_csg_medigap.{table}', DB)),
                         'sha256': hashlib.sha256(output).hexdigest()}
        assert hashes[table] == manifest['csg_tables'][table], table + ' parity mismatch'
    for kind, sha in manifest['pdp_response_sha256'].items():
        assert kind in {'pdp_offering', 'pdp_county', 'pdp_restriction'}
        payload = json.loads(sql(f"SELECT payload::text FROM dl_pilot.pdp_response WHERE kind='{kind}'", DB))
        assert digest(payload) == sha
    for role, schema in [('daylight_csg_reader', 'dl_csg_medigap'),
                         ('daylight_plan_research_reader', 'dl_pilot')]:
        assert sql(f"SELECT rolcanlogin OR rolsuper FROM pg_roles WHERE rolname='{role}'", DB) == 'f'
        assert sql(f"SELECT bool_and(has_table_privilege('{role}',c.oid,'SELECT') AND NOT has_table_privilege('{role}',c.oid,'INSERT,UPDATE,DELETE,TRUNCATE')) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='{schema}' AND c.relkind='r'", DB) == 't'
    assert sql('SHOW listen_addresses', DB) == ''
    assert sql('SHOW default_transaction_read_only', DB) == 'on'
    sys.path.insert(0, str(RELEASE / 'alternatives/advisor-first'))
    import server  # Pinned imports only: no socket, conversation or model call.
    receipt = {'full_csg_row_hashes_match': True, 'csg_tables': hashes,
               'pdp_payload_hashes_match': True, 'exact_code_runtime_bindings_match': True,
               'reader_privileges_verified': True, 'socket_only': True, 'read_only_default': True,
               'server_imports': True, 'snapshot_id': binding['snapshot_id'],
               'current_source_reconciliation': 'blocked by local socket access; still required',
               'app_role_http_checks': 'not run', 'app_activated': False}
    (STATE / 'restore-verification.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
