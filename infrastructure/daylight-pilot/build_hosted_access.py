#!/usr/bin/env python3
"""Prepare the existing host's bounded backup namespace; no AWS calls."""
import copy
import json
from pathlib import Path

ROOT=Path(__file__).parent


def policy():
    return {'PolicyName':'HostedHistoryBackups','PolicyDocument':{
        'Version':'2012-10-17','Statement':[
            {'Sid':'PrivateHistoryObjects','Effect':'Allow',
             'Action':['s3:GetObject','s3:PutObject'],
             'Resource':{'Fn::Sub':'${BackupBucket.Arn}/hosted-backups/*'}},
            {'Sid':'ListDeletionJournalOnly','Effect':'Allow','Action':'s3:ListBucket',
             'Resource':{'Fn::GetAtt':['BackupBucket','Arn']},
             'Condition':{'StringLike':{'s3:prefix':'hosted-backups/deletions/*'}}},
            {'Sid':'EncryptPrivateHistory','Effect':'Allow',
             'Action':['kms:GenerateDataKey','kms:Decrypt'],
             'Resource':{'Fn::GetAtt':['DataKey','Arn']},
             'Condition':{'StringEquals':{
                 'kms:ViaService':{'Fn::Sub':'s3.${AWS::Region}.amazonaws.com'},
                 'kms:EncryptionContext:aws:s3:arn':{'Fn::GetAtt':['BackupBucket','Arn']}}}}
        ]}}


def template():
    original=json.loads((ROOT/'runtime-access.json').read_text())
    target=copy.deepcopy(original)
    target['Resources']['HostRole']['Properties']['Policies'].append(policy())
    # No changes to network, billing, disks, existing policies or bucket lifecycle.
    before=copy.deepcopy(target)
    before['Resources']['HostRole']['Properties']['Policies'].pop()
    assert before==original
    return target


if __name__=='__main__':
    (ROOT/'hosted-access.json').write_text(json.dumps(template(),indent=2)+'\n')
    print('hosted-access.json')
