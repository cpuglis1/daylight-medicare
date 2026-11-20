#!/usr/bin/env python3
"""D208: remove accelerator conversation count cap and raise the shared ceiling to $50; preserve Ultrafast,
four resets and $5 original-session cap, with a $50 shared cumulative ceiling.
Owner remains standard/low, $2 per visit and $20 per link. Invite credentials,
histories and existing charged/reserved ledger rows are never replaced.
Reuses hash-pinned D199 staging/drain/readiness/rollback. No paid probes.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
D199_RELEASE = '99b3717656116a08a192148711bc8acb12d37f7664fc0e916bf3fa0a7ca41c22'
D207_RELEASE = '58daf665e2330687429a96ce7166190b94274d539536c3a0ed9e7972fcca246a'
D206_RELEASE = '01d005129ae9a9942b64cafa4ca404cf0c7420e88cadd19dfeeb7df1bbb2db75'
D200_RELEASE = '3698e69e98427b22e1933a16bb22becdec258a2978a98b3bc39f96d39611b46e'
D199_TOOL = '96099ba5c3b6aefd7411e54531afa5247b651a405c2ab435978af97155b53a09'
SCHEMA = 'daylight-d208-plan/v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_d199(folder):
    path = Path(folder) / 'deploy_hosted_d199.py'
    if path.is_symlink() or sha(path.read_bytes()) != D199_TOOL:
        raise ValueError('The D199 tool differs from the deployed one')
    spec = importlib.util.spec_from_file_location('deploy_hosted_d199', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    # Same staging code; the live base is now the D199 release.
    module.DEPLOYED = D199_RELEASE
    return module


def d199_manifest(directory):
    with zipfile.ZipFile(directory / 'd199-release/hosted-d199-99b371765611.zip') as archive:
        raw = archive.read('release-manifest.json')
    if sha(raw) != D199_RELEASE:
        raise ValueError('D199 bundle manifest is not the live release')
    return json.loads(raw)


def build(root, output_dir):
    directory = root / 'infrastructure/daylight-pilot'
    d199 = load_d199(directory)
    sys.path.insert(0, str(root / 'alternatives/advisor-first'))
    import server  # noqa: F401  (sets the pinned engine import path, as the D199 build does)
    live = d199_manifest(directory)
    files, _ = d199.selected(root)
    files['deployment/deploy_hosted_d200.py'] = directory / 'deploy_hosted_d200.py'
    files['deployment/deploy_hosted_d206.py'] = directory / 'deploy_hosted_d206.py'
    files['deployment/deploy_hosted_d207.py'] = directory / 'deploy_hosted_d207.py'
    files['deployment/deploy_hosted_d208.py'] = directory / 'deploy_hosted_d208.py'
    if any(path.is_symlink() for path in files.values()):
        raise ValueError('Release inputs must be regular files')
    contents = {name: path.read_bytes() for name, path in files.items()}
    manifest = {'scope': live['scope'], 'base_release': D199_RELEASE,
                'files_sha256': {name: sha(data) for name, data in contents.items()}}
    raw = d199.canonical(manifest); release = sha(raw)
    changed = {name: data for name, data in contents.items()
               if live['files_sha256'].get(name) != manifest['files_sha256'][name]}
    missing = sorted(set(live['files_sha256']) - set(manifest['files_sha256']))
    if missing:
        raise ValueError('Files would be dropped from the live release: ' + ', '.join(missing))
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / f'hosted-d208-{release[:12]}.zip'
    if not bundle.exists():
        with zipfile.ZipFile(bundle, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted({'release-manifest.json': raw, **changed}.items()):
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED; entry.external_attr = 0o100600 << 16
                archive.writestr(entry, data)
    with zipfile.ZipFile(bundle) as archive:
        if archive.read('release-manifest.json') != raw or set(archive.namelist()) != {'release-manifest.json', *changed}:
            raise ValueError('Existing bundle differs; never overwrite')
    plan = {'schema': SCHEMA, 'release': release, 'base_release': D199_RELEASE,
            'bundle': bundle.name, 'bundle_sha256': sha(bundle.read_bytes()),
            'changed_files': sorted(changed),
            'tool_sha256': sha((directory / 'deploy_hosted_d208.py').read_bytes()),
            'd199_tool_sha256': D199_TOOL}
    plan_path = output_dir / 'd208-plan.json'
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    transfer = output_dir / 'd208-transfer.zip'
    transfer.unlink(missing_ok=True)   # derived convenience archive; every member is hash-bound by the plan
    with zipfile.ZipFile(transfer, 'x', compression=zipfile.ZIP_STORED) as archive:
        for path in (bundle, plan_path, directory / 'deploy_hosted_d208.py',
                     directory / 'deploy_hosted_d199.py', directory / 'cloudshell_d208.py', directory / 'cloudshell_d199.py'):
            archive.write(path, path.name)
    return {'release': release, 'bundle': bundle.name, 'bundle_sha256': plan['bundle_sha256'],
            'plan_sha256': sha(plan_path.read_bytes()), 'changed_files': sorted(changed),
            'files': len(manifest['files_sha256']), 'transfer': str(transfer),
            'transfer_sha256': sha(transfer.read_bytes())}


def read_plan(folder, expected):
    raw = (folder / 'd208-plan.json').read_bytes()
    if sha(raw) != expected:
        raise ValueError('Plan hash differs')
    plan = json.loads(raw)
    if plan['schema'] != SCHEMA or plan['base_release'] != D199_RELEASE or plan['d199_tool_sha256'] != D199_TOOL:
        raise ValueError('Unexpected plan')
    if sha((folder / plan['bundle']).read_bytes()) != plan['bundle_sha256']:
        raise ValueError('Bundle hash differs')
    if sha(Path(__file__).read_bytes()) != plan['tool_sha256']:
        raise ValueError('This tool differs from the planned tool')
    return plan


def invitation_identity(d199, environment):
    import sqlite3
    root = d199.STATE / 'cohorts' / environment
    with sqlite3.connect((root / 'access.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        links = db.execute('SELECT id,expires,revoked,max_visits FROM shared_links ORDER BY id').fetchall()
    return sha((root / 'signing.key').read_bytes()), sha(json.dumps(links).encode())


def apply(folder, plan_sha, environment, d199):
    plan = read_plan(folder, plan_sha)
    after = d199.stage(folder, plan)
    unit, config = d199.UNITS / f'daylight-{environment}.service', d199.CONFIG / f'{environment}.json'
    old_unit, old_config = unit.read_text(), config.read_text()
    settings = json.loads(old_config)
    if settings['release'] not in (D207_RELEASE, after.name):
        raise ValueError(f'{environment} is not on the reviewed D207 release; nothing changed')
    checks = 'foundation_binding' in settings    # doctor/drug checks stay exactly where they are
    new_unit, current = d199.unit_text(old_unit, after, checks=checks)
    new_config = d199.config_text(old_config, after, checks,
                                  foundation_root=Path(settings['foundation_root']) if checks else None)
    value = json.loads(new_config)
    value['demo_policy'] = 'accelerator' if environment == 'pilot' else 'owner'
    new_config = json.dumps(value, indent=2) + '\n'
    changes = {unit: (old_unit, new_unit), config: (old_config, new_config)}
    backup = d199.STATE / 'operations' / f'd208-{environment}-{int(time.time())}'
    backup.mkdir(mode=0o700, parents=True)
    for path, (old, _) in changes.items():
        (backup / path.name).write_text(old)
    before_identity = invitation_identity(d199, environment)
    d199.switch(changes, [environment], {environment: after.name})
    if invitation_identity(d199, environment) != before_identity:
        raise RuntimeError('Invitation identity changed unexpectedly')
    if environment == 'pilot':
        link = d199.HOST_ROOT / 'current.d208'
        link.unlink(missing_ok=True); link.symlink_to(after); os.replace(link, d199.HOST_ROOT / 'current')
    report = {'environment': environment, 'release': after.name, 'previous': current.name, 'backup': str(backup),
              'checks_on_this_environment': checks, 'provider_calls': 0, 'invitations_changed': False, 'policy': value['demo_policy'],
              'shared_cap_usd': 50, 'conversation_count_limit': None if environment == 'pilot' else 'unchanged', 'visit_cap_usd': 5 if environment == 'pilot' else 2,
              'service_tier': 'ultrafast' if environment == 'pilot' else 'default'}
    (d199.STATE / 'operations' / f'd208-{environment}-{after.name[:12]}.json').write_text(json.dumps(report))
    return report


def rollback(environment, d199):
    backups = sorted((d199.STATE / 'operations').glob(f'd208-{environment}-*/'))
    if not backups:
        raise ValueError('No D208 backup for this environment')
    backup = backups[-1]
    changes = {}
    for saved in backup.iterdir():
        live = (d199.UNITS if saved.suffix == '.service' else d199.CONFIG) / saved.name
        changes[live] = (live.read_text(), saved.read_text())
    release = json.loads(changes[d199.CONFIG / f'{environment}.json'][1])['release']
    d199.switch(changes, [environment], {environment: release})
    if environment == 'pilot':
        link = d199.HOST_ROOT / 'current.d208'
        link.unlink(missing_ok=True); link.symlink_to(d199.HOST_ROOT / 'releases' / release)
        os.replace(link, d199.HOST_ROOT / 'current')
    return {'rolled_back': environment, 'restored_from': str(backup), 'release': release}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('build'); p.add_argument('--output', type=Path, required=True)
    p = commands.add_parser('apply'); p.add_argument('folder', type=Path); p.add_argument('plan_sha256')
    p.add_argument('--environment', choices=('test', 'pilot'), required=True)
    p = commands.add_parser('rollback'); p.add_argument('--environment', choices=('test', 'pilot'), required=True)
    args = parser.parse_args()
    if args.command == 'build':
        report = build(HERE.parents[1], args.output)
    else:
        if os.geteuid() != 0:
            raise ValueError('Root-only deployment')
        d199 = load_d199(HERE)
        (d199.STATE / 'operations').mkdir(mode=0o700, exist_ok=True)
        with (d199.STATE / 'operations/d199.lock').open('a') as lock:   # one deployment at a time, D199 or D208
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            report = (apply(args.folder, args.plan_sha256, args.environment, d199) if args.command == 'apply'
                      else rollback(args.environment, d199))
    print(json.dumps(report))


if __name__ == '__main__':
    sys.exit(main())
