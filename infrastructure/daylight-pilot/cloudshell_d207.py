#!/usr/bin/env python3
"""Upload d207-transfer.zip to CloudShell and unzip in its own folder.

python3 cloudshell_d207.py status
python3 cloudshell_d207.py stage
python3 cloudshell_d207.py apply test
python3 cloudshell_d207.py apply pilot
python3 cloudshell_d207.py rollback test|pilot

Transfers reviewed code over existing SSM access; no IAM grant, S3 policy change,
new resource, credential export, provider request or invitation redemption.
"""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time
import boto3

HERE = Path(__file__).resolve().parent
INSTANCE = 'i-0f641362addf26b76'
HOST = '/var/lib/daylight-state/operations/d207-files'
PYTHON = '/opt/daylight-runtime/venv-3.14.7/bin/python'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def remote(client, commands, label):
    identifier = client.send_command(InstanceIds=[INSTANCE], DocumentName='AWS-RunShellScript',
        Comment='Daylight D207 ' + label,
        Parameters={'commands':['set -eu', *commands], 'executionTimeout':['600']})['Command']['CommandId']
    print('SSM', label, identifier, flush=True)
    while True:
        try:
            report = client.get_command_invocation(CommandId=identifier, InstanceId=INSTANCE)
        except client.exceptions.InvocationDoesNotExist:
            time.sleep(1); continue
        if report['Status'] in {'Pending','InProgress','Delayed'}:
            time.sleep(2); continue
        print(report['StandardOutputContent'].strip(), flush=True)
        if report['Status'] != 'Success':
            print(report['StandardErrorContent'][-2500:])
            raise SystemExit(report['Status'])
        return


def main():
    s = boto3.Session(region_name='us-east-1')
    if s.client('sts').get_caller_identity()['Account'] != '020055445580':
        raise SystemExit('Use the Daylight workload account.')
    c = s.client('ssm')
    command = sys.argv[1]
    if command == 'status':
        code = "import json; from pathlib import Path; " + \
            "print([{k:v for k,v in json.loads((Path('/etc/daylight-pilot/runtime')/(e+'.json')).read_text()).items() if k in ('release','environment','demo_policy')} for e in ('test','pilot')])"
        return remote(c,[PYTHON+' -c '+shlex.quote(code)],'read-only status')
    plan_path = HERE/'d207-plan.json'
    plan = json.loads(plan_path.read_text())
    files = {plan['bundle']:plan['bundle_sha256'], 'd207-plan.json':sha(plan_path.read_bytes()),
             'deploy_hosted_d207.py':plan['tool_sha256'], 'deploy_hosted_d199.py':plan['d199_tool_sha256']}
    for name,digest in files.items():
        if Path(name).name != name or sha((HERE/name).read_bytes()) != digest:
            raise SystemExit('Release file validation failed: '+name)
    if command == 'stage':
        remote(c,['install -d -m 700 '+HOST],'prepare artifact folder')
        for name,digest in files.items():
            raw = (HERE/name).read_bytes()
            target = HOST+'/'+name
            # Each independently hashed chunk is idempotently written at a fixed offset.
            # The full file is verified before it is eligible for application.
            for offset in range(0,len(raw),12000):
                chunk = raw[offset:offset+12000]
                code = ('import base64,pathlib; p=pathlib.Path('+repr(target+'.part')+'); '
                        +('p.write_bytes(b\'\'); ' if offset==0 else '')
                        +'f=p.open("r+b"); f.seek('+str(offset)+'); f.write(base64.b64decode('
                        +repr(base64.b64encode(chunk).decode())+')); f.close()')
                remote(c,[PYTHON+' -c '+shlex.quote(code)],'stage '+name+' '+str(offset))
            code = ('import pathlib,hashlib; p=pathlib.Path('+repr(target+'.part')+'); '
                    +'assert hashlib.sha256(p.read_bytes()).hexdigest()=='+repr(digest)+'; '
                    +'p.chmod(0o600); p.replace('+repr(target)+')')
            remote(c,[PYTHON+' -c '+shlex.quote(code)],'verify '+name)
    elif command == 'reset-accelerator':
        remote(c,[PYTHON+' -I '+HOST+'/deploy_hosted_d207.py reset-accelerator'],'reset accelerator allowances')
    elif command in {'apply','rollback'}:
        environment = sys.argv[2]
        if environment not in {'test','pilot'}: raise SystemExit('Name test or pilot.')
        args = ('apply '+HOST+' '+files['d207-plan.json'] if command=='apply' else 'rollback')
        remote(c,[PYTHON+' -I '+HOST+'/deploy_hosted_d207.py '+args+' --environment '+environment],command+' '+environment)
    else:
        raise SystemExit(__doc__)


if __name__=='__main__': main()
