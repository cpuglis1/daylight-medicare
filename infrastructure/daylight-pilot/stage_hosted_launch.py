#!/usr/bin/env python3
"""CloudShell-only private stage and IAM preview. NEVER applies access or starts app."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import time
import zipfile
import boto3

ACCOUNT='020055445580'
INSTANCE='i-0f641362addf26b76'
STACK='daylight-pilot-foundation'
ROOT=Path(__file__).resolve().parent
EVIDENCE=ROOT/'evidence'


def remote(client,commands,label):
    result=client.send_command(InstanceIds=[INSTANCE],DocumentName='AWS-RunShellScript',
        Parameters={'commands':['set -e',*commands],'executionTimeout':['180']},Comment=label)
    identifier=result['Command']['CommandId']
    for _ in range(100):
        time.sleep(2)
        try:report=client.get_command_invocation(CommandId=identifier,InstanceId=INSTANCE)
        except client.exceptions.InvocationDoesNotExist:continue
        if report['Status'] in {'Pending','InProgress','Delayed'}:continue
        (EVIDENCE/(identifier+'.json')).write_text(json.dumps(report,default=str))
        if report['Status']!='Success':
            print(json.dumps({'failed_command':identifier,'status':report['Status'],
                              'output':report['StandardOutputContent'],'error':report['StandardErrorContent']}))
            raise RuntimeError('Private staging failed; no application activation attempted')
        return {'command':identifier,'output':report['StandardOutputContent'].strip()}
    raise RuntimeError('SSM staging has not completed; inspect before retrying')


def main():
    import os
    os.umask(0o077);EVIDENCE.mkdir(mode=0o700,exist_ok=True)
    session=boto3.Session(region_name='us-east-1')
    assert session.client('sts').get_caller_identity()['Account']==ACCOUNT
    report=json.loads((ROOT/'hosted-release-candidate.json').read_text())
    archive=ROOT/report['file'];raw=archive.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==report['sha256']
    ssm=session.client('ssm')
    destination='/var/lib/daylight-state/'+report['file']
    # Each SSM document stays below its command-size limit. All bytes are private
    # code, never credentials or participant content.
    commands=['umask 077',': > '+shlex.quote(destination)]
    for offset in range(0,len(raw),10000):
        part=base64.b64encode(raw[offset:offset+10000]).decode()
        commands.append('printf %s '+shlex.quote(part)+' | base64 -d >> '+shlex.quote(destination))
        remote(ssm,commands,'Stage reviewed private application bytes')
        commands=[]
    with zipfile.ZipFile(archive) as bundle:
        installer=bundle.read('deployment/install_hosted_runtime.py')
    installer_path='/var/lib/daylight-state/install-hosted-runtime.py'
    remote(ssm,['umask 077','printf %s '+shlex.quote(base64.b64encode(installer).decode())+
        ' | base64 -d > '+installer_path], 'Stage reviewed installer only')
    stage=remote(ssm,['/usr/bin/python3 '+installer_path+' stage '+destination+' '+report['sha256']],
                 'Verify and privately stage immutable hosted release')
    print(json.dumps({'staging':stage}))
    guard='/opt/daylight-pilot/releases/'+report['release']+'/deployment/hosted_egress_guard.py'
    kernel=remote(ssm,['unshare --net /usr/bin/python3 '+guard+' kernel-self-test'],
                  'Verify quota only in isolated network namespace')
    print(json.dumps({'kernel_check':kernel}))
    cf=session.client('cloudformation')
    current=cf.get_template(StackName=STACK,TemplateStage='Original')['TemplateBody']
    if isinstance(current,str):current=json.loads(current)
    original=json.loads((ROOT/'runtime-access.json').read_text())
    assert current==original,'Foundation changed; review before preparing new IAM scope'
    candidate=(ROOT/'hosted-access.json').read_text()
    name='hosted-backups-'+hashlib.sha256(candidate.encode()).hexdigest()[:12]
    try:change=cf.describe_change_set(StackName=STACK,ChangeSetName=name)
    except cf.exceptions.ClientError:
        cf.create_change_set(StackName=STACK,ChangeSetName=name,ChangeSetType='UPDATE',
            TemplateBody=candidate,Capabilities=['CAPABILITY_IAM'],
            Parameters=[{'ParameterKey':p['ParameterKey'],'UsePreviousValue':True}
                        for p in cf.describe_stacks(StackName=STACK)['Stacks'][0]['Parameters']],
            Description='Review only: existing host accesses bounded private hosted backup namespace')
        cf.get_waiter('change_set_create_complete').wait(StackName=STACK,ChangeSetName=name,
            WaiterConfig={'Delay':2,'MaxAttempts':90})
        change=cf.describe_change_set(StackName=STACK,ChangeSetName=name)
    assert change['Status']=='CREATE_COMPLETE' and change['ExecutionStatus']=='AVAILABLE'
    changes=change.get('Changes',[]);assert len(changes)==1
    r=changes[0]['ResourceChange']
    assert (r['LogicalResourceId'],r['Action'],r['Replacement'])==('HostRole','Modify','False')
    assert all(d.get('Target',{}).get('Name')=='Policies' for d in r.get('Details',[]))
    summary={'account':ACCOUNT,'release':report['release'],'staged':True,'kernel_check':kernel,
             'changeset':name,'changes':changes,'executed':False,'public_access_changed':False}
    (EVIDENCE/'prepared-launch.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary))

if __name__=='__main__':main()
