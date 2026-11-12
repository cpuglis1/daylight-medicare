"""Assemble bounded, versioned receipts without changing application inputs."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
SNAP = OUT/'snapshot'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, value):
    path = OUT/name
    if path.exists():
        raise RuntimeError('Preserve existing receipt: ' + name)
    path.write_text(json.dumps(value, indent=2) + '\n')

def main():
    if (OUT/'FREEZE_R1.json').exists():
        raise RuntimeError('Evidence already frozen.')
    capture = json.loads((OUT/'CAPTURE.json').read_text())
    layout = json.loads((OUT/'LAYOUT_COMPLETION_R1.json').read_text())
    runtime = json.loads((OUT/'EXTERNAL_RUNTIME_INPUTS.json').read_text())
    inputs = json.loads((SNAP/'INPUT_HASHES.json').read_text())
    guards = {mode: json.loads((OUT/(mode+'-execution-guard.json')).read_text())
              for mode in ['suite','reference','journey']}
    journey = json.loads((OUT/'actual-identity-http-journey.json').read_text())
    final_inputs, drift, bad = [], [], []
    for row in capture['files']:
        name = row['path']; path = SNAP/name
        if sha(path) != row['sha256'] or inputs[name] != row['sha256']:
            bad.append(name)
        if row['external_path'] and sha(Path(row['external_path'])) != row['sha256']:
            bad.append('external:' + name)
        original = REPO/name
        if sha(original) != row['sha256']:
            drift.append({'path':name,'captured_sha256':row['sha256'],'later_original_sha256':sha(original)})
        final_inputs.append({**row, 'final_storage': 'enumerated_external_symlink' if path.is_symlink() else 'real_copy',
                             'final_mode': oct(path.lstat().st_mode & 0o777)})
    if bad:
        raise RuntimeError('Input bytes changed: ' + repr(bad))
    for path, digest in runtime['third_party_files_sha256'].items():
        if sha(Path(path)) != digest:
            raise RuntimeError('Runtime dependency drift: ' + path)
    assert journey['passed'] and len(journey['checks']) == 29 and len(journey['requests']) == 33
    assert all(not g['snapshot_and_external_hash_mismatches'] for g in guards.values())
    assert guards['journey']['runtime_dependency_hash_mismatches'] == []
    witnesses = guards['journey']['postgres_connection_read_only_witnesses']
    assert len(witnesses) == 9 and all(w['default_transaction_read_only']=='on' for w in witnesses)
    runtime_paths = set(runtime['third_party_files_sha256'])
    external_modules = {k:v for k,v in guards['journey']['loaded_workspace_modules'].items()
                        if not v.startswith(str(SNAP)+'/')}
    assert all(p in runtime_paths for p in external_modules.values())
    suite_log = (OUT/'advisor-full-suite.log').read_text()
    reference_log = (OUT/'published-reference-targeted.log').read_text()
    def ids(log):
        return [f'{owner}.{method}' for method, owner in re.findall(r'^(test_\S+) \(([^)]+)\) \.\.\.', log, re.M)]
    first_ids, second_ids = ids(suite_log), ids(reference_log)
    assert len(first_ids)==766 and len(set(first_ids))==766
    assert len(second_ids)==9 and len(set(second_ids))==9
    assert not set(first_ids).intersection(second_ids)
    assert 'Ran 766 tests in 132.015s' in suite_log and 'FAILED (errors=1)' in suite_log
    assert 'Ran 9 tests in 3.509s' in reference_log and reference_log.rstrip().endswith('OK')
    assert 'ERROR: setUpClass (test_published_reference.PublishedReferenceTests)' in suite_log
    assert not re.search(r'^FAIL:', suite_log, re.M)
    write('EXACT_TEST_UNION_R1.json', {'schema':'daylight.exact-isolated-test-union.v1',
        'broad_attempt':{'tests_run':766,'individual_test_failures':0,'class_setup_errors':1,
            'seconds':132.015,'receipt':'advisor-full-suite.log','test_ids':first_ids},
        'targeted_previously_unexecuted_class':{'tests_run':9,'passed':True,'seconds':3.509,
            'receipt':'published-reference-targeted.log','test_ids':second_ids},
        'unique_executed_test_ids':775,'intersection':[], 'broad_runs':1,
        'application_and_dependency_byte_changes_between_runs':0,
        'fixture_layout_changes_only':'LAYOUT_COMPLETION_R1.json',
        'assertion':'Coherent same-input union; not a claim that one broad invocation returned OK.'})
    write('FINAL_INPUTS_R1.json', {'schema':'daylight.isolated-final-inputs.v1',
        'input_paths':len(final_inputs),'captured_content_hashes_unchanged':True,
        'regular_copied_files':sum(r['final_storage']=='real_copy' for r in final_inputs),
        'individual_external_links':sum(r['final_storage']=='enumerated_external_symlink' for r in final_inputs),
        'final_copied_bytes':sum(r['bytes'] for r in final_inputs if r['final_storage']=='real_copy'),
        'external_identity_controls_also_copied':sum(bool(r['also_external_identity_control']) for r in final_inputs),
        'files':final_inputs})
    write('ORIGINAL_WORKSPACE_AFTER_R1.json', {'observed_utc':datetime.now(timezone.utc).isoformat(),
        'original_files_changed_since_capture':drift,
        'meaning':'Informational only. Certification binds copied source plus unchanged enumerated dependencies, not current workspace or runtime.'})
    blocked = {}
    for mode,g in guards.items():
        counts=Counter(r.get('path',r.get('address','')) for r in g['workspace_access_violations'])
        blocked[mode]=[{'path':p,'attempts':n,'file_now_exists':Path(p).is_file()} for p,n in counts.items()]
    # The broad guard captured unsuccessful linecache-style diagnostic probes
    # against bare pseudo-filenames. A later guard ignores non-files before
    # enforcing the same data whitelist. Nothing was read from those paths.
    assert all(not x['file_now_exists'] for x in blocked['suite'])
    assert all(x['path'].endswith('.dist-info/METADATA') for x in blocked['journey'])
    write('GUARD_INTERPRETATION_R1.json', {'schema':'daylight.isolated-guard-interpretation.v1',
        'raw_guard_receipts_preserved':True,'blocked_attempts':blocked,
        'suite_nonexistent_pseudo_filename_probes':len(guards['suite']['workspace_access_violations']),
        'journey_optional_package_metadata_reads_denied':len(guards['journey']['workspace_access_violations']),
        'all_application_shared_replay_and_serving_modules_from_snapshot':True,
        'journey_non_snapshot_modules_are_only_hashed_psycopg_runtime':True,
        'raw_journey_all_workspace_modules_flag':guards['journey']['all_workspace_modules_loaded_from_snapshot'],
        'raw_flag_explanation':'False includes the explicitly declared installed PostgreSQL driver. Every such module is in EXTERNAL_RUNTIME_INPUTS.json; no mutable app/shared/serving module was imported.',
        'postgres_default_read_only_connections_witnessed':len(witnesses),
        'source_code_transaction_guards':'Copied serving/repository.py also sets each research transaction READ ONLY and SET LOCAL ROLE daylight_research_reader.',
        'sql_monitoring_limit':'The harness witnesses connection defaults; it is not a server-wide audit or an independent audit of concurrent database activity.',
        'resource_warnings_in_initial_log':len(re.findall('ResourceWarning:',suite_log)),
        'warning_limit':'Existing tests emitted unclosed temporary SQLite ResourceWarnings. No application fix or broad rerun was made.'})
    receipt = {'schema':'daylight.isolated-advisor-compatibility-result.v1',
        'observed_utc':datetime.now(timezone.utc).isoformat(),'status':'bounded_same_source_union_passed',
        'capture':'CAPTURE.json','capture_sha256':sha(OUT/'CAPTURE.json'),
        'snapshot_input_manifest_sha256':sha(SNAP/'INPUT_HASHES.json'),
        'application_logic_edits':0,'source_bytes_changed_between_executions':0,
        'initial_source_copies':269,'final_source_and_small_data_copies':280,
        'original_external_data_dependencies':488,'final_individual_external_data_links':476,
        'external_driver_runtime_files':193,'all_input_hashes_stable':True,
        'broad_suite_runs':1,'broad_test_count':766,'initial_class_setup_errors':1,
        'targeted_previously_unexecuted_tests':9,'unique_same_source_union_tests':775,
        'actual_source_journey':{'checks':29,'http_requests':33,'passed':True,'scripted_model_stages':6,
            'postgres_connections_with_read_only_default_witnessed':9},
        'initial_layout_failure_preserved':True,'no_claim_single_broad_invocation_passed':True,
        'real_guest_profile_access':False,'runtime_access_or_restart':False,
        'paid_ai_or_live_model_calls':0,'external_messages':0,'cloud_actions':0,
        'databases_copied':0,'pdfs_copied':0,'new_source_acceptance':False,'consumer_release':False,
        'requirements_scope':['D73: exact technical capability and limits','D86: privacy, separate saving and deterministic conversation compatibility','D87: explicit internal identity/comparison preparation with held consumer purposes'],
        'limits':['Applies to the immutable copied source and enumerated stable dependencies only, not mutable workspace or running :8893.',
            'Synthetic transport and fictional guest stores exercise mechanics; this does not establish live-model quality, comprehension, clinical/source acceptance, full whole-offering closure or a personal recommendation release.',
            'One initial class-setup containment error was corrected only by byte-identical data layout and nine targeted tests. Logs and both harness forms remain.',
            'External source data, PostgreSQL and installed system/driver runtime remain required; this packet is not a self-contained database/PDF archive.',
            'No rendered UI or responsive walkthrough was conducted; nested Node renderer checks executed through the existing Python suite.']}
    write('RESULT_R1.json',receipt)
    readme = '''# Isolated advisor compatibility — bounded coherent snapshot

The copied source supports a **775-test same-input union and a 29-check actual-source HTTP journey**. The one broad invocation executed 766 tests with no individual test failures and one class-setup error. The unchanged accepted-reference verifier rejected a small linked r4 file on its package-containment check. Eleven byte-identical small data files were copied into place; the previously unexecuted reference class then passed nine tests. The broad suite was not rerun. See [exact union](EXACT_TEST_UNION_R1.json) and [layout correction](LAYOUT_COMPLETION_R1.json).

The capture compared every original before copying, every copied byte, and every original after capture; application population was stable. There are 280 final real copies and 476 individual links to explicitly hashed immutable data. The 488 original external data obligations include the copied source-purpose policy and eleven subsequently copied r4 files. All content hashes remained unchanged across every run. The snapshot contains no database or PDF copies. The 193 installed PostgreSQL-driver runtime files are separately enumerated and hashed. See [capture](CAPTURE.json), [final inputs](FINAL_INPUTS_R1.json), [runtime inputs](EXTERNAL_RUNTIME_INPUTS.json) and [result](RESULT_R1.json).

The HTTP journey uses the real profile adapter and retained PostgreSQL sources with fictional reports, an ephemeral localhost server, a temporary fictional SQLite store, and the original locally scripted Responses transport. Its original neutral education fields and all 29 assertions are unchanged. The separate driver adjusts only the snapshot root, preloads copied infrastructure modules, and supplies the real repository for immutable controls and its checked Unix socket. Nine PostgreSQL connections each witnessed `default_transaction_read_only=on`; copied source also enforces read-only transactions and its research-reader role. No existing runtime was inspected, restarted or changed. No real guest/profile, paid model, cloud action, external message, new acceptance or consumer release was used.

The original broad log, original captured driver, adapted driver, guard variants and exact diffs are retained. Twenty blocked broad-run probes referred only to nonexistent diagnostic pseudo-filenames. Two optional installed-package metadata reads were blocked during the passing journey. The raw journey “all workspace modules” flag is false because it includes the separately hashed PostgreSQL driver; all application, shared engine, replay and infrastructure serving modules came from the copy. Existing tests emitted temporary-SQLite ResourceWarnings. [Guard interpretation](GUARD_INTERPRETATION_R1.json) retains these limits.

This verifies deterministic compatibility for this copied source and its enumerated dependencies. It does not certify the mutable workspace, active :8893 process, rendered usability, live-model quality, consumer comprehension, clinical/source meaning, whole-offering completion or a recommendation release. D73, D86 and D87 privacy, independence and separate source/consumer gates remain held. No app code was edited.
'''
    (OUT/'README.md').write_text(readme)
    members=[]
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            members.append({'path':str(path.relative_to(OUT)), 'sha256':sha(path), 'bytes':path.stat().st_size,
                'storage':'external_symlink' if path.is_symlink() else 'regular_file',
                **({'target':str(path.resolve())} if path.is_symlink() else {})})
    freeze={'schema':'daylight.isolated-compatibility-freeze.v1','observed_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Immutable captured advisor compatibility evidence, explicit external dependencies, failed attempt and bounded same-input union.',
        'files':members,'member_count':len(members),'result_sha256':sha(OUT/'RESULT_R1.json'),
        'new_acceptance':False,'consumer_release':False,'runtime_certification':False}
    write('FREEZE_R1.json',freeze)
    # Harden regular evidence without following external links or changing originals.
    for path in OUT.rglob('*'):
        if path.is_file() and not path.is_symlink():
            path.chmod(0o444)
    print(json.dumps({'freeze_sha256':sha(OUT/'FREEZE_R1.json'),'members':len(members),
                      'result_sha256':sha(OUT/'RESULT_R1.json'),'tests_union':775,'journey_checks':29,
                      'original_later_drift_files':len(drift)},indent=2))

if __name__=='__main__':
    main()
