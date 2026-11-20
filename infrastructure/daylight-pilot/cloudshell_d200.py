#!/usr/bin/env python3
"""D200 CloudShell driver. Run from the folder where d200-transfer.zip was unzipped.

  python3 cloudshell_d200.py status            read-only: what each site runs now
  python3 cloudshell_d200.py upload            put the four hash-checked files in the private bucket
  python3 cloudshell_d200.py grant             temporary read of exactly those four files by the host (24 h)
  python3 cloudshell_d200.py apply test        switch test.daylightmedicare.com
  python3 cloudshell_d200.py apply pilot       switch daylightmedicare.com
  python3 cloudshell_d200.py revoke            remove the temporary read permission
  python3 cloudshell_d200.py rollback test|pilot

Workload account 020055445580, us-east-1. No credentials are printed or embedded.
Doctor/drug checks, invitations, limits and the model are not changed.
"""
import datetime as dt
import json
from pathlib import Path
import sys

import cloudshell_d199 as d199   # same account, bucket, key, encryption and SSM helpers

HERE = Path(__file__).resolve().parent
HOST_DIR = '/var/lib/daylight-state/operations/d200-files'
HOST_ROLE = 'daylight-pilot-foundation-HostRole-1wbV5I89MZ97'
GRANT = 'D200TemporaryArtifactRead'


def plan():
    path = HERE / 'd200-plan.json'
    value = json.loads(path.read_text())
    files = {value['bundle']: value['bundle_sha256'], 'deploy_hosted_d200.py': value['tool_sha256'],
             'deploy_hosted_d199.py': value['d199_tool_sha256'], 'd200-plan.json': d199.sha(path)}
    for name, digest in files.items():
        if d199.sha(HERE / name) != digest:
            raise SystemExit(f'{name} does not match the plan; stop.')
    return value, files


def prefix(value):
    return f"deployment/d200/{value['release'][:12]}/"


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    session = d199.boto3.Session(region_name='us-east-1')
    if session.client('sts').get_caller_identity()['Account'] != d199.ACCOUNT:
        raise SystemExit('Switch to the Daylight workload account (020055445580) first.')
    ssm = session.client('ssm')
    command = sys.argv[1]
    if command == 'status':
        return d199.remote(ssm, [
            'readlink -f /opt/daylight-pilot/current',
            'for e in pilot test; do echo "$e: $(grep -o "releases/[0-9a-f]*" /etc/systemd/system/daylight-$e.service | head -1)'
            ' checks=$(grep -c foundation_binding /etc/daylight-pilot/runtime/$e.json || true)'
            ' $(systemctl is-active daylight-$e.service)"; done',
            'cat /etc/daylight-pilot/pricing-review.json 2>/dev/null || echo "no host pricing file"',
            'grep MemAvailable /proc/meminfo'], 'Daylight D200 read-only status', timeout=120)
    value, files = plan()
    iam = session.client('iam')
    if command == 'upload':
        s3 = session.client('s3')
        for name in files:
            d199.upload_encrypted(s3, HERE / name, prefix(value) + name, files[name])
            print('uploaded', name, flush=True)
    elif command == 'grant':
        until = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
        policy = {'Version': '2012-10-17', 'Statement': [{
            'Sid': 'ReadFourD200ReleaseFilesOnly', 'Effect': 'Allow', 'Action': 's3:GetObject',
            'Resource': [f'arn:aws:s3:::{d199.BUCKET}/{prefix(value)}{name}' for name in files],
            'Condition': {'DateLessThan': {'aws:CurrentTime': until}}}]}
        iam.put_role_policy(RoleName=HOST_ROLE, PolicyName=GRANT, PolicyDocument=json.dumps(policy))
        print(f'{GRANT} added for four files until {until}. Run "revoke" after both sites are checked.')
    elif command == 'revoke':
        try:
            iam.delete_role_policy(RoleName=HOST_ROLE, PolicyName=GRANT)
        except iam.exceptions.NoSuchEntityException:
            pass
        if GRANT in iam.list_role_policies(RoleName=HOST_ROLE)['PolicyNames']:
            raise SystemExit('The temporary read permission is still present; stop.')
        print(f'{GRANT} removed and its absence confirmed.')
    elif command in {'apply', 'rollback'}:
        if len(sys.argv) != 3 or sys.argv[2] not in {'test', 'pilot'}:
            raise SystemExit('Name the environment: test or pilot.')
        tool = f'{d199.PYTHON} -I {HOST_DIR}/deploy_hosted_d200.py'
        if command == 'apply':
            fetch = [f'install -d -m 700 {HOST_DIR}']
            for name, digest in files.items():
                fetch.append(f'aws s3api get-object --bucket {d199.BUCKET} --key {prefix(value)}{name} {HOST_DIR}/{name} >/dev/null')
                fetch.append(f'echo "{digest}  {HOST_DIR}/{name}" | sha256sum -c --quiet -')
            d199.remote(ssm, [*fetch, f"{tool} apply {HOST_DIR} {files['d200-plan.json']} --environment {sys.argv[2]}"],
                        f'Daylight D200 apply {sys.argv[2]}')
        else:
            d199.remote(ssm, [f'{tool} rollback --environment {sys.argv[2]}'], f'Daylight D200 rollback {sys.argv[2]}')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
