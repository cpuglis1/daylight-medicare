#!/usr/bin/env python3
"""Build/apply a narrow invitation-gate patch without altering hosted state.

Build runs locally. Apply runs as root on the existing host; no provider call,
new infrastructure, credential access, schema change, accounting reset or quota
reset. Existing paused/live service and credential configuration is preserved.
"""
import argparse
import base64
import copy
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import zipfile

BASE='1b088ac0558a36cf4c1a77d5ea33007a8b83b5fe4cf13374b7cb730b292fc7eb'
PREFIX='alternatives/advisor-first/'
ALLOWED={PREFIX+name for name in ('pilot_access.py','pilot-web/join.js','pilot-web/history.js',
    'pilot-web/history-join.html','pilot-web/join.html','pilot-web/join.css')}
ROOT=Path('/opt/daylight-pilot')
STATE=Path('/var/lib/daylight-state')
CONFIG=Path('/etc/daylight-pilot/runtime')
UNITS=Path('/etc/systemd/system')
SERVICES=('daylight-pilot.service','daylight-test.service')
PYTHON='/opt/daylight-runtime/venv-3.14.7/bin/python'


def sha(data):return hashlib.sha256(data).hexdigest()


def run(*args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=60,
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    if result.returncode:raise RuntimeError('Gate deployment command failed: '+Path(args[0]).name)
    return result.stdout.strip()


def manifest(raw,expected):
    if sha(raw)!=expected:raise ValueError('Base manifest hash differs')
    value=json.loads(raw)
    if value.get('scope')!='fictional_invited_hosted_demo' or not isinstance(value.get('files_sha256'),dict):
        raise ValueError('Unexpected release manifest')
    return value


def read_bundle(path,expected):
    raw=path.read_bytes()
    if len(raw)>1024*1024 or sha(raw)!=expected:raise ValueError('Patch bundle hash/size differs')
    value=json.loads(raw)
    if (set(value)!={'schema','base_release','reason','files'} or value['schema']!='daylight-gate-patch/v1'
            or value['base_release']!=BASE or not isinstance(value['reason'],str)
            or not 1<=len(value['reason'])<=240 or not isinstance(value['files'],dict)
            or not value['files'] or not set(value['files'])<=ALLOWED):
        raise ValueError('Patch is outside the reviewed gate-file scope')
    decoded={}
    for name,item in value['files'].items():
        if not isinstance(item,dict) or set(item)!={'before','after','base64'}:
            raise ValueError('Unexpected file patch fields')
        data=base64.b64decode(item['base64'],validate=True)
        if (len(data)>256*1024 or sha(data)!=item['after'] or item['before']==item['after']
                or not re.fullmatch('[0-9a-f]{64}',item['before'])):
            raise ValueError('Patch content hash/size differs')
        decoded[name]=data
    if sum(map(len,decoded.values()))>512*1024:raise ValueError('Patch is too large')
    return value,decoded


def build(workspace,base_archive,output,files,reason):
    if not files or len(set(files))!=len(files) or not set(files)<=ALLOWED:
        raise ValueError('Select only the reviewed gate files')
    with zipfile.ZipFile(base_archive) as archive:base=manifest(archive.read('release-manifest.json'),BASE)
    changes={}
    for name in files:
        path=workspace/name
        if path.is_symlink() or not path.resolve().is_relative_to(workspace.resolve()):raise ValueError('Invalid workspace file')
        data=path.read_bytes();before=base['files_sha256'][name];after=sha(data)
        if before!=after:changes[name]={'before':before,'after':after,'base64':base64.b64encode(data).decode()}
    value={'schema':'daylight-gate-patch/v1','base_release':BASE,'reason':reason,'files':changes}
    raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    with output.open('xb') as stream:stream.write(raw)
    read_bundle(output,sha(raw))
    return {'bundle':str(output),'sha256':sha(raw),'bytes':len(raw),'files':sorted(changes),'base_release':BASE}


def verify_tree(directory,release):
    if directory.is_symlink() or not directory.is_dir():raise ValueError('Immutable release directory required')
    value=manifest((directory/'release-manifest.json').read_bytes(),release)
    for name,digest in value['files_sha256'].items():
        path=directory/name
        if (Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink()
                or not path.resolve().is_relative_to(directory.resolve()) or sha(path.read_bytes())!=digest):
            raise ValueError('Installed release file differs')
    return value


def stage(bundle,decoded):
    before=ROOT/'releases'/BASE;base=verify_tree(before,BASE)
    new=copy.deepcopy(base);new['base_release']=BASE
    for name,item in bundle['files'].items():
        if base['files_sha256'].get(name)!=item['before']:raise ValueError('Patch baseline differs')
        new['files_sha256'][name]=item['after']
    raw=json.dumps(new,sort_keys=True,separators=(',',':')).encode();release=sha(raw)
    after=ROOT/'releases'/release
    if after.exists():verify_tree(after,release);return before,after
    with tempfile.TemporaryDirectory(prefix='.gate-patch-',dir=ROOT/'releases') as temporary:
        temporary=Path(temporary)
        for name in base['files_sha256']:
            target=temporary/name;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if name in decoded:target.write_bytes(decoded[name])
            else:shutil.copyfile(before/name,target)
            target.chmod(0o600)
        (temporary/'release-manifest.json').write_bytes(raw)
        (temporary/'release-manifest.json').chmod(0o600)
        verify_tree(temporary,release)
        temporary.rename(after)
    return before,after


def changes_for(before,after):
    result={};modes={}
    for environment in ('pilot','test'):
        name='daylight-'+environment+'.service';path=UNITS/name;old=path.read_text()
        base=f'ExecStart={PYTHON} {before}/alternatives/advisor-first/hosted_server.py --config {CONFIG}/{environment}.json'
        lines=[line for line in old.splitlines() if line.startswith('ExecStart=')]
        if (len(lines)!=1 or lines[0] not in (base,base+' --paused') or
                f'WorkingDirectory={before}\n' not in old or
                'Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo\n' not in old):
            raise ValueError('Unexpected active service configuration')
        modes[environment]='paused' if lines[0].endswith(' --paused') else 'live'
        overrides=run('systemctl','show',name,'--property=DropInPaths','--value')
        if overrides!=str(UNITS/(name+'.d')/'10-daylight-egress.conf'):
            raise ValueError('Unexpected effective service overrides')
        config=CONFIG/(environment+'.json');raw=config.read_text();value=json.loads(raw)
        if value.get('release')!=before.name or value.get('binding')!=str(before/'evidence/binding.json'):
            raise ValueError('Service binding does not match current release')
        updated=copy.deepcopy(value);updated['release']=after.name;updated['binding']=str(after/'evidence/binding.json')
        result[path]=(old,old.replace(str(before),str(after)))
        result[config]=(raw,json.dumps(updated,indent=2)+'\n')
    return result,modes


def atomic_write(path,value):
    stat=path.stat();fd,temporary=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            os.fchmod(stream.fileno(),stat.st_mode&0o777);os.fchown(stream.fileno(),stat.st_uid,stat.st_gid)
            stream.write(value);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def pointer(target):
    path=ROOT/'current.gate-patch'
    if path.exists() or path.is_symlink():raise ValueError('Unfinished pointer change requires review')
    path.symlink_to(target);os.replace(path,ROOT/'current')


def access(environment,readonly=False):
    return sqlite3.connect((STATE/'cohorts'/environment/'access.sqlite3').as_uri()+
        ('?mode=ro' if readonly else '?mode=rw'),uri=True,timeout=3)


def chat_flags(values=None):
    previous={}
    for environment in ('pilot','test'):
        with access(environment,readonly=values is None) as db:
            previous[environment]=dict(db.execute("SELECT name,enabled FROM flags WHERE name IN ('all_chat','guest_chat')"))
            if set(previous[environment])!={'all_chat','guest_chat'}:raise ValueError('Messaging flags are absent')
            if values is not None:
                for name,value in values[environment].items():db.execute('UPDATE flags SET enabled=? WHERE name=?',(value,name))
    return previous


def drained():
    with sqlite3.connect((STATE/'budget/model-usage.sqlite3').as_uri()+'?mode=ro',uri=True,timeout=3) as db:
        if db.execute("SELECT count(*) FROM ai_charges WHERE status='reserved'").fetchone()[0]:return False
    for environment in ('pilot','test'):
        value=run('runuser','-u','postgres','--','psql','-X','-qAt','-v','ON_ERROR_STOP=1',
            '-h',str(STATE/'pgsocket'),'-p','55485','-d','daylight_history_'+environment,
            '-c',"SELECT count(*) FROM hosted_history.turns WHERE status='accepted'")
        if value!='0':return False
    return True


def ready(release):
    for port,host in ((19093,'daylightmedicare.com'),(19094,'test.daylightmedicare.com')):
        deadline=time.monotonic()+25
        while True:
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
            try:
                connection.request('GET','/pilot/join',headers={'Host':host,'Connection':'close'})
                response=connection.getresponse()
                if response.status==200 and response.getheader('X-Daylight-Release')==release:
                    response.read(65536);break
            except (OSError,http.client.HTTPException):pass
            finally:connection.close()
            if time.monotonic()>=deadline:raise RuntimeError('Patched invitation page failed readiness')
            time.sleep(0.25)


def apply(bundle_path,expected):
    bundle,decoded=read_bundle(bundle_path,expected)
    if not (ROOT/'current').is_symlink() or (ROOT/'current').resolve()!=ROOT/'releases'/BASE:
        raise ValueError('Current release is not the exact reviewed baseline')
    before,after=stage(bundle,decoded);changes,modes=changes_for(before,after)
    user=pwd.getpwnam('daylight-app')
    for path in [after,*after.rglob('*')]:
        if path.is_symlink():raise ValueError('No release symlinks permitted')
        os.chown(path,0,user.pw_gid);path.chmod(0o750 if path.is_dir() else 0o640)
    old_flags=chat_flags();stopped=False
    # Let already-admitted work finish before pausing new messaging. The second
    # check below catches a request that raced with the admission switch.
    deadline=time.monotonic()+45
    while not drained():
        if time.monotonic()>=deadline:raise ValueError('An unfinished turn prevents safe restart; original services retained')
        time.sleep(0.5)
    try:
        chat_flags({name:{'all_chat':0,'guest_chat':0} for name in old_flags})
        deadline=time.monotonic()+45
        while not drained():
            if time.monotonic()>=deadline:raise ValueError('An unfinished turn prevents safe restart; original services retained')
            time.sleep(0.5)
        run('systemctl','stop',*SERVICES);stopped=True
        if not drained():raise ValueError('A turn entered while draining; leave original code for review')
        for path,(old,new) in changes.items():
            if path.read_text()!=old:raise ValueError('Configuration changed during preparation')
            atomic_write(path,new)
        run('systemd-analyze','verify',*(str(UNITS/name) for name in SERVICES))
        pointer(after);run('systemctl','daemon-reload');run('systemctl','start',*SERVICES)
        ready(after.name)
    except Exception:
        if stopped:
            run('systemctl','stop',*SERVICES)
            for path,(old,_) in changes.items():atomic_write(path,old)
            pointer(before);run('systemctl','daemon-reload');run('systemctl','start',*SERVICES)
            ready(before.name)
        chat_flags(old_flags)
        raise
    chat_flags(old_flags)
    report={'base_release':BASE,'release':after.name,'files':sorted(decoded),'modes_preserved':modes,
        'credential_configuration_preserved':True,'persistent_data_unchanged':True,'provider_calls':0}
    receipt=STATE/'operations'/('gate-patch-'+after.name+'.json')
    with receipt.open('x') as stream:json.dump(report,stream);stream.flush();os.fsync(stream.fileno())
    return report


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('build');p.add_argument('--workspace',type=Path,required=True);p.add_argument('--base-archive',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--reason',required=True);p.add_argument('files',nargs='+')
    p=commands.add_parser('apply');p.add_argument('bundle',type=Path);p.add_argument('sha256')
    args=parser.parse_args()
    if args.command=='build':report=build(args.workspace,args.base_archive,args.output,args.files,args.reason)
    else:
        if os.geteuid()!=0:raise ValueError('Root-only deployment')
        with (STATE/'operations/gate-patch.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);report=apply(args.bundle,args.sha256)
    print(json.dumps(report))

if __name__=='__main__':main()
