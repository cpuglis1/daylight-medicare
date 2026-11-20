#!/usr/bin/env python3
"""Activate the invited fictional demo after OWNER-RUN secret entry.

Never prints credentials, calls OpenAI, initializes accounting, or changes AWS
resources. Requires the reviewed immutable release and existing egress guard.
"""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time

ROOT=Path('/opt/daylight-pilot')
STATE=Path('/var/lib/daylight-state')
CONFIG=Path('/etc/daylight-pilot/runtime')
UNITS=Path('/etc/systemd/system')
CREDENTIAL=Path('/etc/daylight-pilot/credentials/openai')
PROJECT='proj_XVkWvLOovz4I7JBUS0B0o9QE'
MODEL='gpt-6.1-sol'
SECRET='arn:aws:secretsmanager:us-east-1:020055445580:secret:daylight-pilot-foundation/openai-Dc7VCK'
PYTHON='/opt/daylight-runtime/venv-3.14.7/bin/python'
SERVICES=('daylight-pilot.service','daylight-test.service')


def run(*args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=60,
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','AWS_MAX_ATTEMPTS':'1'})
    if result.returncode:raise RuntimeError('Private activation command failed: '+Path(args[0]).name)
    return result.stdout.strip()


def validate_secret(value):
    expected={'schema','api_key','project','model','reasoning','data','monthly_limit_usd','hard_limit_owner_confirmed'}
    if (not isinstance(value,dict) or set(value)!=expected or type(value['schema']) is not int or
            value['schema']!=1 or value['project']!=PROJECT or value['model']!=MODEL or
            value['reasoning']!='low' or value['data']!='fictional' or
            type(value['monthly_limit_usd']) is not int or value['monthly_limit_usd']!=20 or
            value['hard_limit_owner_confirmed'] is not True or
            not isinstance(value['api_key'],str) or not re.fullmatch('sk-[A-Za-z0-9_-]{16,250}',value['api_key'])):
        raise ValueError('The owner-entered secret does not match the reviewed demo settings')
    return value['api_key']


def release_directory(release):
    if not re.fullmatch('[0-9a-f]{64}',release):raise ValueError('Use an exact release digest')
    directory=ROOT/'releases'/release
    if not (ROOT/'current').is_symlink() or (ROOT/'current').resolve()!=directory or directory.is_symlink():
        raise ValueError('Activate only the current immutable release')
    raw=(directory/'release-manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=release:raise ValueError('Manifest hash differs')
    manifest=json.loads(raw)
    if manifest.get('scope')!='fictional_invited_hosted_demo':raise ValueError('Wrong release scope')
    for name,digest in manifest['files_sha256'].items():
        path=directory/name
        if path.is_symlink() or not path.resolve().is_relative_to(directory) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Release file verification failed')
    routes=json.loads((directory/'alternatives/advisor-first/model-routes.json').read_text())['routes']
    demo=[r for r in routes if r['environment']=='hosted-demo']
    if (len(demo)!=1 or demo[0]['project']!=PROJECT or demo[0]['models']!=[MODEL] or
            demo[0]['data']!='fictional' or demo[0]['provider']!='openai' or
            demo[0]['endpoints']!={'responses':'https://api.openai.com/v1/responses',
            'input_tokens':'https://api.openai.com/v1/responses/input_tokens'}):
        raise ValueError('Dedicated demo route differs')
    health=[r for r in routes if r['environment']=='pilot']
    if len(health)!=1 or health[0]['project'] is not None or any(health[0]['endpoints'].values()):
        raise ValueError('The real-health pilot must remain blocked')
    return directory


def ledger_status():
    path=STATE/'budget/model-usage.sqlite3'
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=3) as db:
        total,missing,count=db.execute('''SELECT coalesce(sum(c.charged),0),
            count(*)-count(o.participant),count(*) FROM ai_charges c
            LEFT JOIN pilot_charge_owner o ON o.charge_id=c.id''').fetchone()
        if missing or total<0 or total>=20*1000000000 or db.execute("SELECT 1 FROM ai_meta WHERE key='blocked'").fetchone():
            raise ValueError('Shared accounting is blocked or exhausted')
        return {'accounted_nano_usd':total,'charges':count}


def access(environment):
    return sqlite3.connect((STATE/'cohorts'/environment/'access.sqlite3').as_uri()+'?mode=rw',uri=True,timeout=3)


def flag_states():
    states={}
    for environment in ('pilot','test'):
        with access(environment) as db:
            states[environment]=dict(db.execute('SELECT name,enabled FROM flags'))
        if states[environment]!={'guest_chat':0,'all_chat':0,'paid_features':0}:
            raise ValueError('This first activation requires paused messaging flags')
    return states


def set_flags(values):
    for environment,flags in values.items():
        with access(environment) as db:
            db.execute('BEGIN IMMEDIATE')
            for name,value in flags.items():
                if db.execute('UPDATE flags SET enabled=? WHERE name=?',(value,name)).rowcount!=1:
                    raise ValueError('Messaging flag is absent')


def unit_changes(directory):
    changes={}
    for environment in ('pilot','test'):
        name='daylight-'+environment+'.service'
        unit=UNITS/name;raw=unit.read_text()
        expected=f'ExecStart={PYTHON} {directory}/alternatives/advisor-first/hosted_server.py --config {CONFIG}/{environment}.json --paused'
        if (raw.count(expected)!=1 or raw.count('ExecStart=')!=1 or '[Service]\n' not in raw or
                'Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo\n' not in raw or
                'LoadCredential' in raw or 'SetCredential' in raw):
            raise ValueError('Unexpected paused service configuration')
        overrides=run('systemctl','show',name,'--property=DropInPaths','--value')
        if overrides!=str(UNITS/(name+'.d')/'10-daylight-egress.conf'):
            raise ValueError('Expected only the persistent egress override')
        config=json.loads((CONFIG/(environment+'.json')).read_text())
        if (config.get('release')!=directory.name or config.get('environment')!=environment or
                config.get('ledger')!=str(STATE/'budget/model-usage.sqlite3') or
                config.get('key_file')!=f'/run/credentials/{name}/openai'):
            raise ValueError('Unexpected persistent service binding')
        value=raw.replace(expected,expected.removesuffix(' --paused'))
        value=value.replace('[Service]\n','[Service]\nLoadCredential=openai:'+str(CREDENTIAL)+'\n',1)
        value=value.replace('(AI paused)','(invited fictional demo)')
        changes[unit]=(raw,value)
    return changes


def atomic_write(path,value):
    stat=path.stat();fd,temporary=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            os.fchmod(stream.fileno(),stat.st_mode&0o777);os.fchown(stream.fileno(),stat.st_uid,stat.st_gid)
            stream.write(value);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def http_ready():
    for port,host in ((19093,'daylightmedicare.com'),(19094,'test.daylightmedicare.com')):
        deadline=time.monotonic()+20
        while True:
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
            try:
                connection.request('GET','/pilot/join',headers={'Host':host,'Connection':'close'})
                response=connection.getresponse()
                if response.status==200:
                    response.read(65536)
                    break
            except (OSError,http.client.HTTPException):pass
            finally:connection.close()
            if time.monotonic()>=deadline:raise RuntimeError('Invitation page is unavailable')
            time.sleep(0.25)


def activate(release):
    directory=release_directory(release);before_ledger=ledger_status();old_flags=flag_states()
    changes=unit_changes(directory)
    if CREDENTIAL.exists() or CREDENTIAL.is_symlink():raise ValueError('A runtime credential already exists; use reviewed rotation')
    for service in (*SERVICES,'daylight-delete.service','daylight-egress.service'):
        if run('systemctl','is-active',service)!='active':raise ValueError('Required private services must be healthy')
    guard=json.loads(run('/usr/bin/python3',str(directory/'deployment/hosted_egress_guard.py'),'enforce'))
    if not guard.get('active'):raise ValueError('The one-time egress allowance is closed')
    http_ready()
    # The CLI's captured stdout exists only in this root process. It never goes
    # through a terminal, shell history, command arguments, logs or release files.
    retrieved=json.loads(run('/usr/bin/aws','--region','us-east-1','--no-cli-pager',
        '--cli-connect-timeout','5','--cli-read-timeout','20','secretsmanager','get-secret-value',
        '--secret-id',SECRET,'--version-stage','AWSCURRENT','--output','json'))
    if retrieved.get('ARN')!=SECRET:raise ValueError('Unexpected secret resource')
    body=json.loads(retrieved['SecretString']);key=validate_secret(body)
    version=retrieved['VersionId'];retrieved=None;body=None
    if CREDENTIAL.parent.is_symlink():raise ValueError('Use the root-only credential directory')
    CREDENTIAL.parent.mkdir(mode=0o700,exist_ok=True);CREDENTIAL.parent.chmod(0o700)
    fd=os.open(CREDENTIAL,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o400)
    with os.fdopen(fd,'w') as stream:stream.write(key);stream.flush();os.fsync(stream.fileno())
    key=None
    run('systemctl','stop',*SERVICES)
    try:
        for path,(old,new) in changes.items():
            if path.read_text()!=old:raise ValueError('Unit changed during activation')
            atomic_write(path,new)
        run('systemd-analyze','verify',*(str(path) for path in changes))
        run('systemctl','daemon-reload');run('systemctl','start',*SERVICES)
        run('systemctl','is-active',*SERVICES);http_ready()
        if ledger_status()!=before_ledger:raise ValueError('Accounting changed during provider-free activation')
        set_flags({name:{'guest_chat':1,'all_chat':1,'paid_features':0} for name in old_flags})
    except Exception:
        set_flags(old_flags);run('systemctl','stop',*SERVICES)
        for path,(old,_) in changes.items():atomic_write(path,old)
        run('systemctl','daemon-reload');run('systemctl','start',*SERVICES)
        # Retain the root-only credential for explicit retry/rotation review.
        raise
    result={'activated':True,'release':release,'project':PROJECT,'model':MODEL,'reasoning':'low',
        'secret_version':version,'shared_model_cap_usd':20,'visit_cap_usd':2,'provider_calls':0,
        'paid_features_enabled':False,'data_scope':'fictional','ledger':before_ledger}
    receipt=STATE/'operations'/('chat-activation-'+release+'.json')
    fd=os.open(receipt,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(result,stream);stream.flush();os.fsync(stream.fileno())
    return result


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('release');args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Root-only activation after owner credential entry')
    print(json.dumps(activate(args.release)))

if __name__=='__main__':main()
