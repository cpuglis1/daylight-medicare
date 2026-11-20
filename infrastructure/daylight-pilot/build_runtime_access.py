#!/usr/bin/env python3
"""D194: prepare only the host's exact artifact/TLS read permissions, offline."""
import json
from pathlib import Path

from build_foundation import att, sub
from build_pro_migration import network

ARTIFACT_SHA256 = 'aaa19850dd02ccd61b25f633e170bc8f01d0321cbe26e5b1715874e2cfe3ec42'
ARTIFACT_KEY = 'deployment/rehearsal/' + ARTIFACT_SHA256 + '.tar.gz'
ORIGIN_CERTIFICATE = ('arn:aws:acm:us-east-1:020055445580:certificate/'
                      '7dc53f28-855c-46c1-8683-81b3f6661957')


def template():
    target = network('attach-address')
    target['Description'] = 'D194 closed host: read one deployment artifact and own origin certificate'
    target['Resources']['HostRole']['Properties']['Policies'].append({
        'PolicyName': 'ReadExactDeploymentAndOriginTLS',
        'PolicyDocument': {'Version': '2012-10-17', 'Statement': [
            {'Sid': 'ReadOneDeploymentArtifact', 'Effect': 'Allow',
             'Action': ['s3:GetObject'], 'Resource': sub('${BackupBucket.Arn}/' + ARTIFACT_KEY)},
            {'Sid': 'DecryptOwnDeploymentArtifact', 'Effect': 'Allow',
             'Action': ['kms:Decrypt'], 'Resource': att('DataKey', 'Arn'),
             'Condition': {'StringEquals': {
                 'kms:ViaService': sub('s3.${AWS::Region}.amazonaws.com'),
                 'kms:EncryptionContext:aws:s3:arn': att('BackupBucket', 'Arn')}}},
            {'Sid': 'ReadOwnOriginCertificate', 'Effect': 'Allow',
             'Action': ['acm:DescribeCertificate', 'acm:GetCertificate', 'acm:ExportCertificate'],
             'Resource': ORIGIN_CERTIFICATE}
        ]}})
    return target


def validate_changes(response):
    """Refuse extra resources, replacements, stale previews, or other role edits."""
    if response.get('Status') != 'CREATE_COMPLETE' or response.get('ExecutionStatus') != 'AVAILABLE':
        raise ValueError('Change set is not ready for review.')
    changes = response.get('Changes', [])
    if len(changes) != 1:
        raise ValueError('Expected only the existing host role.')
    r = changes[0].get('ResourceChange', {})
    if (r.get('LogicalResourceId'), r.get('Action'), r.get('Replacement'), r.get('ResourceType')) != (
            'HostRole', 'Modify', 'False', 'AWS::IAM::Role'):
        raise ValueError('Unexpected resource change or replacement.')
    if r.get('Scope') != ['Properties']:
        raise ValueError('Only role properties may change.')
    if any(d.get('Target', {}).get('Name') != 'Policies' for d in r.get('Details', [])):
        raise ValueError('Only the inline policies may change.')


if __name__ == '__main__':
    path = Path(__file__).with_name('runtime-access.json')
    path.write_text(json.dumps(template(), indent=2) + '\n')
    print(path.name)
