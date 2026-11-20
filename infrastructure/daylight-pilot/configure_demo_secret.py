#!/usr/bin/env python3
"""OWNER-RUN CloudShell credential entry; no secret in chat, files or shell history.

First configure a dedicated OpenAI project: monthly $20, Enforce a hard limit,
GPT-6.1 Sol only, restricted Responses API key. This script makes NO OpenAI call.
"""
import getpass
import json
import re
import sys


def main():
    import boto3
    if not sys.stdin.isatty():raise ValueError('Use an interactive private terminal')
    session=boto3.Session(region_name='us-east-1')
    if session.client('sts').get_caller_identity()['Account']!='020055445580':
        raise ValueError('Wrong AWS account')
    client=session.client('secretsmanager')
    name='daylight-pilot-foundation/openai'
    if client.describe_secret(SecretId=name).get('VersionIdsToStages'):
        raise ValueError('A credential already exists; do not silently replace it')
    project=input('Dedicated OpenAI project ID (proj_...): ').strip()
    if not re.fullmatch('proj_[A-Za-z0-9]{8,64}',project):raise ValueError('Invalid project ID')
    answer=input('Confirm this project has a $20 monthly ENFORCED hard limit and a restricted demo key [yes]: ')
    if answer.strip().lower()!='yes':raise ValueError('Configure the provider limit first')
    key=getpass.getpass('Paste the restricted API key (hidden; press Enter): ').strip()
    if not re.fullmatch('sk-[A-Za-z0-9_-]{16,250}',key):raise ValueError('Invalid key format')
    body={'schema':1,'api_key':key,'project':project,'model':'gpt-6.1-sol',
          'reasoning':'low','data':'fictional','monthly_limit_usd':20,'hard_limit_owner_confirmed':True}
    client.put_secret_value(SecretId=name,SecretString=json.dumps(body))
    key=None;body=None
    print(json.dumps({'stored_in_aws':True,'project':project,'provider_calls':0}))

if __name__=='__main__':main()
