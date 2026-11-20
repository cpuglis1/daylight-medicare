#!/usr/bin/env python3
"""Apply the runtime and backup access explicitly approved by the owner.

CloudShell only. No public ingress, DNS, model calls, credentials or new resources.
Stops on any discrepancy. Never rerun initialization over existing app state.
"""
import argparse
import json
from pathlib import Path
import boto3
import stage_hosted_launch as stage


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-runtime-and-backup-access',action='store_true',required=True)
    parser.parse_args()
    stage.main()
    session=boto3.Session(region_name='us-east-1')
    assert session.client('sts').get_caller_identity()['Account']==stage.ACCOUNT
    cf=session.client('cloudformation')
    prepared=json.loads((stage.EVIDENCE/'prepared-launch.json').read_text())
    candidate=json.loads((stage.ROOT/'hosted-access.json').read_text())
    change=cf.describe_change_set(StackName=stage.STACK,ChangeSetName=prepared['changeset'])
    assert change['Status']=='CREATE_COMPLETE' and change['ExecutionStatus']=='AVAILABLE'
    assert change['Changes']==prepared['changes']
    actual=cf.get_template(StackName=stage.STACK,ChangeSetName=prepared['changeset'])['TemplateBody']
    if isinstance(actual,str):actual=json.loads(actual)
    assert actual==candidate,'Preview template differs from reviewed permissions'
    cf.execute_change_set(StackName=stage.STACK,ChangeSetName=prepared['changeset'])
    print('Applying the approved existing-host backup policy...',flush=True)
    cf.get_waiter('stack_update_complete').wait(StackName=stage.STACK,WaiterConfig={'Delay':5,'MaxAttempts':120})
    actual=cf.get_template(StackName=stage.STACK)['TemplateBody']
    if isinstance(actual,str):actual=json.loads(actual)
    assert actual==candidate,'Applied template differs'
    release=prepared['release']
    installed=stage.remote(session.client('ssm'),[
        '/usr/bin/python3 /var/lib/daylight-state/install-hosted-runtime.py apply '+release+' --approved-runtime-access'],
        'Install approved private runtime and backup operations; AI paused')
    report={'release':release,'backup_access_applied':True,'installation':installed,
            'public_access_changed':False,'ai_paused':True,'provider_calls':0}
    (stage.EVIDENCE/'runtime-installed.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
