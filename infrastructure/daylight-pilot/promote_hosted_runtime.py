#!/usr/bin/env python3
"""Promote only a dedicated-project binding while both hosted apps are paused.

No schema, ledger, invite, egress, credential, proxy or AWS permissions change.
The new immutable release must differ only in hosted-demo's project identifier.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import subprocess
import tempfile

ROOT=Path('/opt/daylight-pilot')
STATE=Path('/var/lib/daylight-state')
CONFIG=Path('/etc/daylight-pilot/runtime')
UNITS=Path('/etc/systemd/system')
MODEL_ROUTE='alternatives/advisor-first/model-routes.json'
SERVICES=('daylight-pilot.service','daylight-test.service')


def run(*args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=45,
                          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    if result.returncode:raise RuntimeError('Paused promotion command failed: '+args[0])
    return result.stdout.strip()


def digest(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def inventory(release):
    if not digest(release):raise ValueError('Use an exact immutable release digest')
    directory=ROOT/'releases'/release
    if directory.is_symlink() or not directory.is_dir():raise ValueError('Use a staged release directory')
    raw=(directory/'release-manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=release:raise ValueError('Manifest digest differs')
    value=json.loads(raw)
    if (value.get('scope')!='fictional_invited_hosted_demo' or
            not isinstance(value.get('files_sha256'),dict)):
        raise ValueError('Unexpected release scope')
    for name,expected in value['files_sha256'].items():
        path=directory/name
        if (not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts or
                path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()) or
                not digest(expected) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected):
            raise ValueError('Release file verification failed')
    return directory,value['files_sha256']


def validate_delta(old,new,project):
    if not re.fullmatch('proj_[A-Za-z0-9]{8,64}',project):raise ValueError('Use the reviewed project ID')
    before,old_hashes=inventory(old);after,new_hashes=inventory(new)
    if old_hashes.keys()!=new_hashes.keys():raise ValueError('Release inventory changed')
    changed={name for name in old_hashes if old_hashes[name]!=new_hashes[name]}
    if changed!={MODEL_ROUTE}:raise ValueError('Only the dedicated model project may change')
    routes=json.loads((before/MODEL_ROUTE).read_text());expected=copy.deepcopy(routes)
    selected=[route for route in expected.get('routes',[]) if route.get('environment')=='hosted-demo']
    if (len(selected)!=1 or selected[0].get('data')!='fictional' or
            selected[0].get('provider')!='openai' or selected[0].get('project') is not None):
        raise ValueError('Unexpected existing fictional-demo route')
    selected[0]['project']=project
    if json.loads((after/MODEL_ROUTE).read_text())!=expected:
        raise ValueError('Model route changes exceed the project binding')
    return before,after


def no_visitors():
    for environment in ('pilot','test'):
        path=STATE/'cohorts'/environment/'access.sqlite3'
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=3) as db:
            if db.execute('SELECT count(*) FROM invites').fetchone()[0]:
                raise ValueError('This helper is limited to an unused paused deployment')
            if db.execute('SELECT count(*) FROM shared_links').fetchone()[0]:
                raise ValueError('An invitation link already exists')
            if db.execute('SELECT count(*) FROM flags WHERE enabled<>0').fetchone()[0]:
                raise ValueError('Messaging must remain paused')


def unit_changes(before,after,config_root=CONFIG,unit_root=UNITS):
    changes={}
    for environment in ('pilot','test'):
        name='daylight-'+environment+'.service'
        path=unit_root/name
        original=path.read_text()
        command=f'ExecStart=/opt/daylight-runtime/venv-3.14.7/bin/python {before}/alternatives/advisor-first/hosted_server.py --config {config_root}/{environment}.json --paused'
        if (original.count(command)!=1 or original.count('ExecStart=')!=1 or
                f'WorkingDirectory={before}\n' not in original or
                'Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo\n' not in original or
                'LoadCredential' in original or 'SetCredential' in original):
            raise ValueError('Service is not the expected paused installation')
        dropins=unit_root/(name+'.d')
        if dropins.exists():
            for dropin in dropins.glob('*.conf'):
                if (dropin.name!='10-daylight-egress.conf' or dropin.read_text()!=
                        '[Unit]\nRequires=daylight-egress.service\nAfter=daylight-egress.service\n'):
                    raise ValueError('Unexpected service override')
        credential=Path('/run/credentials')/name/'openai'
        if credential.exists() or credential.is_symlink():raise ValueError('Provider credential is already installed')
        config=config_root/(environment+'.json')
        settings=json.loads(config.read_text())
        if settings.get('release')!=before.name or settings.get('binding')!=str(before/'evidence/binding.json'):
            raise ValueError('Existing service binding differs')
        updated=copy.deepcopy(settings);updated['release']=after.name;updated['binding']=str(after/'evidence/binding.json')
        changes[path]=(original,original.replace(str(before),str(after)))
        changes[config]=(config.read_text(),json.dumps(updated,indent=2)+'\n')
    return changes


def atomic_write(path,value):
    stat=path.stat()
    fd,temporary=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            os.fchmod(stream.fileno(),stat.st_mode&0o777)
            os.fchown(stream.fileno(),stat.st_uid,stat.st_gid)
            stream.write(value);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def switch_pointer(target):
    temporary=ROOT/'current.promoting'
    if temporary.exists() or temporary.is_symlink():raise ValueError('An unfinished promotion needs review')
    temporary.symlink_to(target);os.replace(temporary,ROOT/'current')


def promote(release,project):
    current=ROOT/'current'
    if not current.is_symlink():raise ValueError('Expected an existing immutable release pointer')
    before,after=validate_delta(current.resolve().name,release,project)
    if current.resolve()!=before:raise ValueError('Unexpected current release location')
    no_visitors();changes=unit_changes(before,after)
    for service in SERVICES:
        if run('systemctl','is-active',service)!='active':raise ValueError('Existing paused apps must be healthy')
        # Inspect effective overrides, including /run overrides outside our directory.
        effective=run('systemctl','show',service,'--property=DropInPaths','--value')
        expected=str(UNITS/(service+'.d')/'10-daylight-egress.conf')
        if effective not in ('',expected):raise ValueError('Unexpected effective service override')
    user=pwd.getpwnam('daylight-app')
    for path in [after,*after.rglob('*')]:
        if path.is_symlink():raise ValueError('No symlinks in the staged release')
        os.chown(path,0,user.pw_gid);path.chmod(0o750 if path.is_dir() else 0o640)
    receipt=STATE/'operations'/('promotion-'+release+'.json')
    if receipt.exists():raise ValueError('A promotion receipt already exists')
    run('systemctl','stop',*SERVICES)
    try:
        no_visitors()
        for path,(old,new) in changes.items():
            if path.read_text()!=old:raise ValueError('Configuration changed during promotion')
            atomic_write(path,new)
        run('systemd-analyze','verify',*(str(UNITS/service) for service in SERVICES))
        switch_pointer(after)
        run('systemctl','daemon-reload');run('systemctl','start',*SERVICES)
        run('systemctl','is-active',*SERVICES)
    except Exception:
        # Code-only rollback; never touch data, accounting, credentials or quotas.
        run('systemctl','stop',*SERVICES)
        for path,(old,_) in changes.items():atomic_write(path,old)
        switch_pointer(before)
        run('systemctl','daemon-reload');run('systemctl','start',*SERVICES)
        raise
    report={'old_release':before.name,'new_release':after.name,'ai_paused':True,
            'state_ledger_schema_egress_unchanged':True,'project':project}
    fd=os.open(receipt,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(report,stream);stream.flush();os.fsync(stream.fileno())
    return report


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release');parser.add_argument('project')
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Owner-only promotion')
    print(json.dumps(promote(args.release,args.project)))

if __name__=='__main__':main()
