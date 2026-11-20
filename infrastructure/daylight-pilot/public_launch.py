#!/usr/bin/env python3
"""D194 guarded public launch of existing resources; no DNS/key/resource creation.

preview is read-only AWS inspection. prepare creates unexecuted change sets.
execute requires the exact preview digest plus action-time public-access approval.
Run network first, verify completion, then edge. No automatic retries/next stage.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket

ACCOUNT='020055445580'
REGION='us-east-1'
FOUNDATION='daylight-pilot-foundation'
EDGE='daylight-pilot-edge'
DISTRIBUTION='EHF4UYWRJHWYV'
HOST='i-0f641362addf26b76'
SG='sg-0b9fdca69a1cb7c57'
ORIGIN_IP='54.83.20.244'
WAF_NAME='ClosedWebAcl-3A3FLDhTpsLv'
WAF_ID='ccdda758-09cf-4090-9a54-8c5b84d5e3a4'
SUBSCRIPTION='arn:aws:pricingplanmanager::020055445580:subscription:sub_3MIo6koerCsbtVl8ZeHChkzkKJB'
CACHE_POLICY='4135ea2d-6df8-44a3-9df3-4b5a84be39ad'
REQUEST_POLICY='216adef6-5c7f-47e4-b989-5492eafa07d3'


def require(value,message):
    if not value:raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with path.open('x') as stream:json.dump(value,stream,indent=2)
    path.chmod(0o600)


def clients():
    import boto3
    session=boto3.Session(region_name=REGION)
    require(session.client('sts').get_caller_identity()['Account']==ACCOUNT,'Wrong workload account')
    return {name:session.client(name) for name in ('cloudformation','cloudfront','ec2','wafv2','secretsmanager','pricing-plan-manager')}


def template(c,stack):
    value=c['cloudformation'].get_template(StackName=stack,TemplateStage='Original')['TemplateBody']
    return json.loads(value) if isinstance(value,str) else value


def stack_info(c,stack):
    value=c['cloudformation'].describe_stacks(StackName=stack)['Stacks'][0]
    require(value['StackStatus'] in {'CREATE_COMPLETE','UPDATE_COMPLETE','UPDATE_ROLLBACK_COMPLETE'},'Stack is not stable: '+stack)
    return value


def subscription_active(c):
    client=c['pricing-plan-manager']
    operation=client.meta.service_model.operation_model('GetSubscription')
    names=set(operation.input_shape.members)
    require(names=={'arn'},'Unexpected subscription API shape; inspect it read-only')
    value=client.get_subscription(arn=SUBSCRIPTION)['subscription']
    require(value.get('arn')==SUBSCRIPTION and value.get('usageLevel','DEFAULT')=='DEFAULT' and
            value.get('status')=='ACTIVE' and value.get('planTier')=='PRO' and
            value.get('planFamily')=='CloudFront' and not value.get('scheduledChange'),
            'Existing Pro subscription must be ACTIVE with no pending cancellation/tier change')
    required={'arn:aws:cloudfront::'+ACCOUNT+':distribution/'+DISTRIBUTION,
              'arn:aws:wafv2:'+REGION+':'+ACCOUNT+':global/webacl/'+WAF_NAME+'/'+WAF_ID}
    require(len(value.get('resourceArns',[]))==2 and required==set(value['resourceArns']),
            'Pro coverage must remain exactly the existing distribution and WAF')


def visibility(name):
    return {'SampledRequestsEnabled':False,'CloudWatchMetricsEnabled':False,'MetricName':name}


def byte_match(field,value,transform='NONE'):
    return {'ByteMatchStatement':{'SearchString':value,'FieldToMatch':field,
        'TextTransformations':[{'Priority':0,'Type':transform}],'PositionalConstraint':'EXACTLY'}}


def permitted_request():
    return {'AndStatement':{'Statements':[
        {'OrStatement':{'Statements':[byte_match({'SingleHeader':{'Name':'host'}},host,'LOWERCASE')
                                     for host in ('daylightmedicare.com','test.daylightmedicare.com')]}},
        {'OrStatement':{'Statements':[byte_match({'Method':{}},method) for method in ('GET','HEAD','POST')]}}
    ]}}


def waf_rules():
    # Ordinary WAF rules on the existing Pro-associated ACL. No paid bot groups,
    # challenges, CAPTCHA, sampled requests, logs or CloudWatch metrics are added.
    return [
        {'Name':'daylight-global-rate','Priority':0,'Action':{'Block':{}},
         'Statement':{'RateBasedStatement':{'Limit':2000,'AggregateKeyType':'CONSTANT',
             'EvaluationWindowSec':300,'ScopeDownStatement':permitted_request()}},
         'VisibilityConfig':visibility('daylight-global-rate')},
        {'Name':'daylight-ip-rate','Priority':1,'Action':{'Block':{}},
         'Statement':{'RateBasedStatement':{'Limit':600,'AggregateKeyType':'IP','EvaluationWindowSec':300}},
         'VisibilityConfig':visibility('daylight-ip-rate')},
        {'Name':'daylight-invited-app','Priority':2,'Action':{'Allow':{}},
         'Statement':permitted_request(),'VisibilityConfig':visibility('daylight-invited-app')}
    ]


def targets(foundation,edge,prefix):
    require(prefix.startswith('pl-') and len(prefix)>3 and all(c in '0123456789abcdef' for c in prefix[3:]),'Invalid prefix list')
    network=copy.deepcopy(foundation)
    props=network['Resources']['HostSecurityGroup']['Properties']
    require(not props.get('SecurityGroupIngress'),'Expected closed origin ingress')
    props['SecurityGroupIngress']=[{'IpProtocol':'tcp','FromPort':443,'ToPort':443,
        'SourcePrefixListId':prefix,'Description':'CloudFront only; exact distribution origin token is also required'}]
    restore=copy.deepcopy(network)
    restore['Resources']['HostSecurityGroup']=copy.deepcopy(foundation['Resources']['HostSecurityGroup'])
    require(restore==foundation,'Unexpected non-ingress modification')
    live=copy.deepcopy(edge)
    require(set(live['Resources'])=={'Distribution','ClosedWebAcl','ProSubscription'},'Unexpected edge resources')
    distribution=live['Resources']['Distribution']['Properties']['DistributionConfig']
    require(distribution['Enabled'] is False,'Distribution is already enabled')
    require(set(distribution['Aliases'])=={'daylightmedicare.com','test.daylightmedicare.com'},'Unexpected aliases')
    require(distribution['DefaultCacheBehavior']['CachePolicyId']==CACHE_POLICY and
            distribution['DefaultCacheBehavior']['OriginRequestPolicyId']==REQUEST_POLICY,'Unexpected cache policies')
    require(len(distribution['Origins'])==1 and distribution['Origins'][0]['DomainName']=='origin.daylightmedicare.com','Unexpected origin')
    distribution['Enabled']=True
    distribution['Comment']='Daylight invited fictional demo; saved history and cumulative model cap'
    distribution['Origins'][0]['CustomOriginConfig']['OriginReadTimeout']=120
    acl=live['Resources']['ClosedWebAcl']['Properties']
    require(acl['DefaultAction']=={'Block':{}} and not acl.get('Rules'),'Expected block-all ACL')
    acl['Rules']=waf_rules()
    acl['Description']='Invited Daylight demo, host/method allowlist and bounded coarse rates'
    require(live['Resources']['ProSubscription']==edge['Resources']['ProSubscription'],'Subscription must remain unchanged')
    return {'network':network,'edge':live}


def preview(c,directory,baseline):
    path=directory/'public-launch-plan.json'
    require(not path.exists(),'Preview exists; inspect it or use a new directory')
    foundation=template(c,FOUNDATION);edge=template(c,EDGE)
    require(foundation==json.loads(baseline.read_text()),'Current foundation differs from hosted-access baseline; preserve new grants')
    stacks={name:stack_info(c,name) for name in (FOUNDATION,EDGE)}
    subscription_active(c)
    sg=c['ec2'].describe_security_groups(GroupIds=[SG])['SecurityGroups'][0]
    require(not sg['IpPermissions'],'Origin ingress must still be closed')
    instance=c['ec2'].describe_instances(InstanceIds=[HOST])['Reservations'][0]['Instances'][0]
    require(instance.get('PublicIpAddress')==ORIGIN_IP and instance['State']['Name']=='running','Unexpected origin host/address')
    prefix=c['ec2'].describe_managed_prefix_lists(Filters=[{'Name':'prefix-list-name',
        'Values':['com.amazonaws.global.cloudfront.origin-facing']}])['PrefixLists']
    require(len(prefix)==1 and prefix[0]['OwnerId']=='AWS','Expected AWS-owned CloudFront prefix list')
    config=c['cloudfront'].get_distribution_config(Id=DISTRIBUTION)['DistributionConfig']
    require(config['Enabled'] is False,'CloudFront is already enabled')
    acl=c['wafv2'].get_web_acl(Name=WAF_NAME,Id=WAF_ID,Scope='CLOUDFRONT')['WebACL']
    require(acl['DefaultAction']=={'Block':{}} and not acl['Rules'],'WAF is no longer block-all')
    target=targets(foundation,edge,prefix[0]['PrefixListId'])
    for value in target.values():c['cloudformation'].validate_template(TemplateBody=json.dumps(value))
    after_config=copy.deepcopy(config)
    after_config['Enabled']=True
    after_config['Comment']=target['edge']['Resources']['Distribution']['Properties']['DistributionConfig']['Comment']
    after_config['Origins']['Items'][0]['CustomOriginConfig']['OriginReadTimeout']=120
    plan={'account':ACCOUNT,'region':REGION,'created_at':datetime.now(timezone.utc).isoformat(),
        'before':{'network':foundation,'edge':edge},'target':target,
        'stacks':{'network':FOUNDATION,'edge':EDGE},
        'stack_ids':{stage:stacks[name]['StackId'] for stage,name in [('network',FOUNDATION),('edge',EDGE)]},
        'parameters':{stage:[{'ParameterKey':p['ParameterKey'],'UsePreviousValue':True} for p in stacks[name].get('Parameters',[])]
                      for stage,name in [('network',FOUNDATION),('edge',EDGE)]},
        'prefix':prefix[0]['PrefixListId'],'distribution_before_sha256':digest(config),
        'distribution_after_sha256':digest(after_config),
        'expected_changes':{'network':{'HostSecurityGroup':'Modify'},'edge':{'ClosedWebAcl':'Modify','Distribution':'Modify'}},
        'dns':[
            {'type':'A','host':'origin','value':ORIGIN_IP},
            {'type':'ALIAS','host':'@','value':'d95tkkq6lwfvh.cloudfront.net','replaces':'existing root URL Redirect only'},
            {'type':'CNAME','host':'test','value':'d95tkkq6lwfvh.cloudfront.net'}],
        'preserve_dns':['all MX','all TXT including DKIM','all three ACM validation CNAMEs','all unrelated records'],
        'resource_additions':0,'subscription_changes':0,'invoice_hard_cap':False}
    save(path,plan)
    print(json.dumps({'plan_sha256':digest(plan),'plan_file':str(path),
        'expected_changes':plan['expected_changes'],'dns':plan['dns'],'aws_resource_mutations':0}))


def load(path,reviewed):
    plan=json.loads(path.read_text())
    require(plan['account']==ACCOUNT and plan['region']==REGION and digest(plan)==reviewed,'Wrong or changed reviewed preview')
    require(targets(plan['before']['network'],plan['before']['edge'],plan['prefix'])==plan['target'],'Unexpected target scope')
    return plan


def prepare(c,path,reviewed):
    plan=load(path,reviewed)
    require(not path.with_name('public-launch-changesets.json').exists(),'Change sets already prepared')
    receipt={}
    for stage in ('network','edge'):
        stack=plan['stacks'][stage]
        require(template(c,stack)==plan['before'][stage],'Template drift before preparation')
        require(stack_info(c,stack)['StackId']==plan['stack_ids'][stage],'Stack identity changed')
        result=c['cloudformation'].create_change_set(StackName=stack,
            ChangeSetName='public-'+stage+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
            ChangeSetType='UPDATE',TemplateBody=json.dumps(plan['target'][stage]),
            Capabilities=['CAPABILITY_IAM'],Parameters=plan['parameters'][stage],
            Description='D194 existing-resource invited demo launch; no new subscription or paid tier')
        receipt[stage]=result['Id']
    save(path.with_name('public-launch-changesets.json'),receipt)
    print(json.dumps({'prepared':receipt,'executed':False}))


def review_changes(rows,expected,stage):
    dependencies=[r for r in rows if r.get('LogicalResourceId')=='ProSubscription']
    if dependencies:
        require(stage=='edge' and len(dependencies)==1,'Unexpected subscription change')
        row=dependencies[0]
        require(row.get('Action')=='Modify' and row.get('Replacement')=='False' and
                row.get('ResourceType')=='AWS::PricingPlanManager::Subscription' and
                row.get('PhysicalResourceId')==SUBSCRIPTION and row.get('Scope')==['Properties'],
                'Subscription identity, replacement or scope changed')
        details=row.get('Details',[])
        require(len(details)==1,'Unexpected subscription change details')
        detail=details[0];target=detail.get('Target',{})
        require(detail.get('Evaluation')=='Dynamic' and detail.get('ChangeSource')=='ResourceAttribute' and
                detail.get('CausingEntity')=='ClosedWebAcl.Arn' and
                target.get('Attribute')=='Properties' and target.get('Name')=='ResourceArns' and
                target.get('RequiresRecreation')=='Never',
                'Only the unchanged WAF ARN dependency may affect the subscription preview')
    direct=[r for r in rows if r.get('LogicalResourceId')!='ProSubscription']
    require(len(direct)==len(expected) and
            {r['LogicalResourceId']:r['Action'] for r in direct}==expected,'Unexpected changes; refuse launch')
    require(all(r.get('Replacement') in (None,'False') for r in rows),'Resource replacement refused')


def inspect(c,path,reviewed,stage):
    plan=load(path,reviewed)
    changes=json.loads(path.with_name('public-launch-changesets.json').read_text())
    response=c['cloudformation'].describe_change_set(ChangeSetName=changes[stage])
    require(response['StackId']==plan['stack_ids'][stage],'Change set stack identity differs')
    require(response['Status']=='CREATE_COMPLETE' and response['ExecutionStatus']=='AVAILABLE','Change set is not available')
    rows=[r['ResourceChange'] for r in response.get('Changes',[])]
    review_changes(rows,plan['expected_changes'][stage],stage)
    body=c['cloudformation'].get_template(ChangeSetName=changes[stage],TemplateStage='Original')['TemplateBody']
    require((json.loads(body) if isinstance(body,str) else body)==plan['target'][stage],'Change-set template drift')
    if stage=='edge':
        require(plan['target']['edge']['Resources']['ProSubscription']==plan['before']['edge']['Resources']['ProSubscription'],
                'Subscription template must remain identical')
        require(plan['target']['edge']['Resources']['ProSubscription']['Properties'].get('UsageLevel')=='DEFAULT',
                'Reviewed CloudFormation usage level must remain DEFAULT')
        subscription_active(c)
    return plan,changes[stage],rows


def execute(c,path,reviewed,stage):
    plan,change,rows=inspect(c,path,reviewed,stage)
    require(template(c,plan['stacks'][stage])==plan['before'][stage],'Live template drift before execution')
    subscription_active(c)
    if stage=='network':
        require(not c['ec2'].describe_security_groups(GroupIds=[SG])['SecurityGroups'][0]['IpPermissions'],'Origin already open')
        require(digest(c['cloudfront'].get_distribution_config(Id=DISTRIBUTION)['DistributionConfig'])==plan['distribution_before_sha256'],'CloudFront drift')
    else:
        verify_network(c,plan)
        require({r[4][0] for r in socket.getaddrinfo('origin.daylightmedicare.com',443,socket.AF_INET)}=={ORIGIN_IP},'Origin DNS is not the reviewed host')
        secret=c['secretsmanager'].describe_secret(SecretId='daylight-pilot-foundation/openai')
        require(any('AWSCURRENT' in labels for labels in secret.get('VersionIdsToStages',{}).values()),'Dedicated provider key is not installed')
        require(digest(c['cloudfront'].get_distribution_config(Id=DISTRIBUTION)['DistributionConfig'])==plan['distribution_before_sha256'],'CloudFront drift')
    c['cloudformation'].execute_change_set(ChangeSetName=change)
    print(json.dumps({'stage_started':stage,'changes':[{k:r.get(k) for k in ('LogicalResourceId','Action','Replacement')} for r in rows],
                      'next':'Verify stack completion before another stage or DNS traffic change'}))


def verify_network(c,plan):
    require(stack_info(c,FOUNDATION)['StackId']==plan['stack_ids']['network'],'Foundation changed')
    require(template(c,FOUNDATION)==plan['target']['network'],'Foundation target not applied')
    rules=c['ec2'].describe_security_groups(GroupIds=[SG])['SecurityGroups'][0]['IpPermissions']
    require(len(rules)==1 and rules[0]['IpProtocol']=='tcp' and rules[0]['FromPort']==443 and rules[0]['ToPort']==443 and
        not rules[0].get('IpRanges') and not rules[0].get('Ipv6Ranges') and not rules[0].get('UserIdGroupPairs') and
        [p['PrefixListId'] for p in rules[0].get('PrefixListIds',[])]==[plan['prefix']],'Unexpected origin ingress')


def verify(c,path,reviewed,stage):
    plan=load(path,reviewed);verify_network(c,plan)
    if stage=='edge':
        require(template(c,EDGE)==plan['target']['edge'],'Edge target not applied')
        require(stack_info(c,EDGE)['StackId']==plan['stack_ids']['edge'],'Edge stack identity changed')
        distribution=c['cloudfront'].get_distribution(Id=DISTRIBUTION)['Distribution']
        require(distribution['Status']=='Deployed','CloudFront deployment is still in progress')
        require(digest(distribution['DistributionConfig'])==plan['distribution_after_sha256'],'CloudFront target differs')
        acl=c['wafv2'].get_web_acl(Name=WAF_NAME,Id=WAF_ID,Scope='CLOUDFRONT')['WebACL']
        normalized=json.loads(json.dumps(acl['Rules'],default=lambda value:value.decode() if isinstance(value,bytes) else value))
        require(acl['DefaultAction']=={'Block':{}} and normalized==waf_rules(),'WAF target differs')
        subscription_active(c)
    print(json.dumps({'stage':stage,'verified':True,'dns_and_browser_checks_still_required':True}))


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('preview','prepare','inspect','execute','verify'))
    parser.add_argument('--directory',type=Path,default=Path('public-launch-evidence'))
    parser.add_argument('--baseline',type=Path,default=Path('hosted-access.json'))
    parser.add_argument('--reviewed-sha256')
    parser.add_argument('--stage',choices=('network','edge'))
    parser.add_argument('--approved-public-exposure',action='store_true')
    args=parser.parse_args();c=clients();path=args.directory/'public-launch-plan.json'
    if args.action=='preview':preview(c,args.directory,args.baseline)
    elif args.action=='prepare':prepare(c,path,args.reviewed_sha256)
    else:
        require(args.stage,'Select one stage')
        if args.action=='inspect':
            _,_,rows=inspect(c,path,args.reviewed_sha256,args.stage)
            print(json.dumps([{k:r.get(k) for k in ('LogicalResourceId','Action','Replacement')} for r in rows]))
        elif args.action=='execute':
            require(args.approved_public_exposure,'Action-time public-exposure approval is required')
            execute(c,path,args.reviewed_sha256,args.stage)
        else:verify(c,path,args.reviewed_sha256,args.stage)


if __name__=='__main__':main()
