#!/usr/bin/env python3
"""D199 CloudShell driver. Run from the folder where d199-transfer.zip was unzipped.

  python3 cloudshell_d199.py status            read-only: what each site runs now
  python3 cloudshell_d199.py upload            put the hash-checked files in the private bucket
  python3 cloudshell_d199.py apply test        switch test.daylightmedicare.com (checks on test)
  python3 cloudshell_d199.py apply pilot       switch daylightmedicare.com (checks move to main)
  python3 cloudshell_d199.py rollback test|pilot
  python3 cloudshell_d199.py renew-pricing 2026-11-26T15:00:00Z 2026-12-03T14:59:00Z

Workload account 020055445580, us-east-1. No credentials are printed or embedded.
"""
import hashlib
import base64
import json
from pathlib import Path
import sys
import time

import boto3

ACCOUNT = '020055445580'
INSTANCE = 'i-0f641362addf26b76'
BUCKET = 'daylight-pilot-foundation-backupbucket-zmzwmrv5ebp3'
KMS_KEY = 'arn:aws:kms:us-east-1:020055445580:key/532f547a-784f-4a61-876a-d692e3b675ac'
PYTHON = '/opt/daylight-runtime/venv-3.14.7/bin/python'
HOST_DIR = '/var/lib/daylight-state/operations/d199-files'
HERE = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def plan():
    path = HERE / 'd199-plan.json'
    value = json.loads(path.read_text())
    files = {value['bundle']: value['bundle_sha256'],
             'deploy_hosted_d199.py': value['tool_sha256'], 'd199-plan.json': sha(path)}
    for name, digest in files.items():
        if sha(HERE / name) != digest:
            raise SystemExit(f'{name} does not match the plan; stop.')
    return value, files


def prefix(value):
    return f"deployment/d199/{value['release'][:12]}/"


def verify_encryption(metadata):
    if (metadata.get('ServerSideEncryption') != 'aws:kms' or metadata.get('SSEKMSKeyId') != KMS_KEY
            or metadata.get('BucketKeyEnabled') is not True):
        raise SystemExit('Uploaded object encryption differs from the existing bucket requirements; stop.')


def upload_encrypted(s3, path, key, expected_sha):
    # S3Transfer.upload_file does not accept BucketKeyEnabled. These bounded
    # artifacts fit in a single streaming PutObject, which supports it directly.
    size = path.stat().st_size
    if size > 4 * 1024**3:
        raise SystemExit('Artifact exceeds the reviewed single-upload size; stop.')
    checksum = base64.b64encode(bytes.fromhex(expected_sha)).decode()
    with path.open('rb') as stream:
        s3.put_object(Bucket=BUCKET, Key=key, Body=stream, ContentLength=size,
                      ServerSideEncryption='aws:kms', SSEKMSKeyId=KMS_KEY,
                      BucketKeyEnabled=True, ExpectedBucketOwner=ACCOUNT, ChecksumSHA256=checksum)
    metadata = s3.head_object(Bucket=BUCKET, Key=key, ExpectedBucketOwner=ACCOUNT,
                              ChecksumMode='ENABLED')
    verify_encryption(metadata)
    if metadata.get('ContentLength') != size or metadata.get('ChecksumSHA256') != checksum:
        raise SystemExit('Uploaded object size or SHA256 verification failed; stop.')


def remote(ssm, commands, label, timeout=3600):
    sent = ssm.send_command(InstanceIds=[INSTANCE], DocumentName='AWS-RunShellScript', Comment=label,
                            Parameters={'commands': ['set -euo pipefail', *commands],
                                        'executionTimeout': [str(timeout)]})
    identifier = sent['Command']['CommandId']
    print(f'{label}: SSM command {identifier}', flush=True)
    while True:
        time.sleep(5)
        try:
            report = ssm.get_command_invocation(CommandId=identifier, InstanceId=INSTANCE)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if report['Status'] in {'Pending', 'InProgress', 'Delayed'}:
            print('.', end='', flush=True)
            continue
        print()
        print(report['StandardOutputContent'].strip())
        if report['Status'] != 'Success':
            print(report['StandardErrorContent'].strip()[-3000:])
            raise SystemExit(f"{label} ended with status {report['Status']}")
        return report['StandardOutputContent']


def fetch_commands(value, files):
    lines = [f'install -d -m 700 {HOST_DIR}']
    # The data archive is uploaded once through the S3 console (too large for CloudShell).
    for name, digest in {**files, value['data_archive']: value['data_archive_sha256']}.items():
        lines.append(f'aws s3api get-object --bucket {BUCKET} --key {prefix(value)}{name} {HOST_DIR}/{name} >/dev/null')
        lines.append(f'echo "{digest}  {HOST_DIR}/{name}" | sha256sum -c --quiet -')
    return lines


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    session = boto3.Session(region_name='us-east-1')
    if session.client('sts').get_caller_identity()['Account'] != ACCOUNT:
        raise SystemExit('Switch to the Daylight workload account (020055445580) first.')
    ssm = session.client('ssm')
    command = sys.argv[1]
    if command == 'status':
        remote(ssm, [
            'readlink -f /opt/daylight-pilot/current',
            'for e in pilot test; do echo "$e: $(grep -o "releases/[0-9a-f]*" /etc/systemd/system/daylight-$e.service | head -1)'
            ' checks=$(grep -c foundation_binding /etc/daylight-pilot/runtime/$e.json || true)'
            ' $(systemctl is-active daylight-$e.service)"; done',
            'grep -h -E "BLOCK_RELEASE|TOKEN_PREFLIGHT|PRICING_REVIEW" /etc/systemd/system/daylight-*.service || true',
            'cat /etc/daylight-pilot/pricing-review.json 2>/dev/null || echo "no host pricing file yet"',
            'grep MemAvailable /proc/meminfo; df -h /var/lib/daylight-state | tail -1',
        ], 'Daylight D199 read-only status', timeout=120)
        return
    value, files = plan()
    if command == 'upload':
        s3 = session.client('s3')
        if not (HERE / value['data_archive']).exists():
            try:
                metadata = s3.head_object(Bucket=BUCKET, Key=prefix(value) + value['data_archive'],
                                          ExpectedBucketOwner=ACCOUNT)
            except Exception:
                raise SystemExit(f"Put {value['data_archive']} next to this script (or upload it in the "
                                 f"S3 console to s3://{BUCKET}/{prefix(value)}) first.")
            verify_encryption(metadata)
        for name in files:
            upload_encrypted(s3, HERE / name, prefix(value) + name, files[name])
            print('uploaded', name, flush=True)
        if (HERE / value['data_archive']).exists():
            if sha(HERE / value['data_archive']) != value['data_archive_sha256']:
                raise SystemExit('The data archive does not match the plan; stop.')
            upload_encrypted(s3, HERE / value['data_archive'], prefix(value) + value['data_archive'],
                             value['data_archive_sha256'])
            print('uploaded', value['data_archive'], flush=True)
        return
    if command in {'apply', 'rollback'} and (len(sys.argv) != 3 or sys.argv[2] not in {'test', 'pilot'}):
        raise SystemExit('Name the environment: test or pilot.')
    tool = f'{PYTHON} -I {HOST_DIR}/deploy_hosted_d199.py'
    if command == 'apply':
        remote(ssm, [*fetch_commands(value, files),
                     f"{tool} apply {HOST_DIR} {files['d199-plan.json']} --environment {sys.argv[2]}"],
               f'Daylight D199 apply {sys.argv[2]}')
    elif command == 'rollback':
        remote(ssm, [f'{tool} rollback --environment {sys.argv[2]}'], f'Daylight D199 rollback {sys.argv[2]}')
    elif command == 'renew-pricing' and len(sys.argv) == 4:
        remote(ssm, [f'{tool} renew-pricing {sys.argv[2]} {sys.argv[3]}'], 'Daylight weekly price review')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
