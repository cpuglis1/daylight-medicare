"""Offline exact-scope checks for the two reviewed public-launch updates."""
import copy
import json
import re
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import build_pro_migration
import public_launch as launch


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.foundation=json.loads((Path(__file__).parent/'hosted-access.json').read_text())
        self.edge=build_pro_migration.edge()

    def test_network_changes_only_ingress_and_preserves_backup_iam(self):
        result=launch.targets(self.foundation,self.edge,'pl-123abc')['network']
        self.assertEqual(result['Resources']['HostRole'],self.foundation['Resources']['HostRole'])
        result['Resources']['HostSecurityGroup']=copy.deepcopy(self.foundation['Resources']['HostSecurityGroup'])
        self.assertEqual(result,self.foundation)

    def test_edge_preserves_subscription_origin_token_tls_and_cache(self):
        result=launch.targets(self.foundation,self.edge,'pl-123abc')['edge']
        self.assertEqual(result['Resources']['ProSubscription'],self.edge['Resources']['ProSubscription'])
        before=self.edge['Resources']['Distribution']['Properties']['DistributionConfig']
        after=result['Resources']['Distribution']['Properties']['DistributionConfig']
        self.assertEqual(before['Origins'][0]['OriginCustomHeaders'],after['Origins'][0]['OriginCustomHeaders'])
        self.assertEqual(before['ViewerCertificate'],after['ViewerCertificate'])
        self.assertEqual(before['DefaultCacheBehavior'],after['DefaultCacheBehavior'])
        self.assertEqual(after['Origins'][0]['CustomOriginConfig']['OriginReadTimeout'],120)
        self.assertTrue(after['Enabled'])
        self.assertEqual(result['Resources']['ClosedWebAcl']['Properties']['DefaultAction'],{'Block':{}})

    def test_waf_no_paid_groups_or_content_observability(self):
        rules=launch.waf_rules()
        self.assertEqual(len(rules),3)
        for rule in rules:
            self.assertFalse(rule['VisibilityConfig']['SampledRequestsEnabled'])
            self.assertFalse(rule['VisibilityConfig']['CloudWatchMetricsEnabled'])
        self.assertNotIn('ManagedRuleGroupStatement',json.dumps(rules))
        self.assertEqual(rules[0]['Statement']['RateBasedStatement']['AggregateKeyType'],'CONSTANT')
        self.assertEqual(rules[1]['Statement']['RateBasedStatement']['AggregateKeyType'],'IP')

    def test_waf_description_uses_supported_characters(self):
        acl=launch.targets(self.foundation,self.edge,'pl-123abc')['edge']['Resources']['ClosedWebAcl']['Properties']
        # WAF's Description constraint rejects semicolons even though CFN's
        # template validation accepts the surrounding JSON document.
        pattern=r'^[a-zA-Z0-9=:#@/\-,.][a-zA-Z0-9+=:#@/\-,.\s]+[a-zA-Z0-9+=:#@/\-,.]{1,256}$'
        self.assertLessEqual(len(acl['Description']),256)
        self.assertRegex(acl['Description'],pattern)
        self.assertIsNone(re.fullmatch(pattern,
            'Invited Daylight demo; host/method allowlist and bounded coarse rates'))

    def test_rolled_back_stable_stack_can_be_reinspected(self):
        client=Mock()
        client.describe_stacks.return_value={'Stacks':[{'StackStatus':'UPDATE_ROLLBACK_COMPLETE'}]}
        self.assertEqual(launch.stack_info({'cloudformation':client},'test')['StackStatus'],'UPDATE_ROLLBACK_COMPLETE')
        client.describe_stacks.return_value={'Stacks':[{'StackStatus':'UPDATE_ROLLBACK_IN_PROGRESS'}]}
        with self.assertRaises(ValueError):launch.stack_info({'cloudformation':client},'test')

    def test_nonclosed_predecessor_and_invalid_prefix_refused(self):
        edge=copy.deepcopy(self.edge)
        edge['Resources']['Distribution']['Properties']['DistributionConfig']['Enabled']=True
        with self.assertRaises(ValueError):launch.targets(self.foundation,edge,'pl-123abc')
        for prefix in ('0.0.0.0/0','pl-abcd; open','pl-'):
            with self.subTest(prefix=prefix),self.assertRaises(ValueError):launch.targets(self.foundation,self.edge,prefix)

    def test_subscription_requires_actual_coverage(self):
        client=Mock()
        client.meta.service_model.operation_model.return_value=SimpleNamespace(input_shape=SimpleNamespace(members={'arn':object()}))
        value={'arn':launch.SUBSCRIPTION,'usageLevel':'DEFAULT','status':'ACTIVE','planTier':'PRO','planFamily':'CloudFront','resourceArns':[]}
        client.get_subscription.return_value={'subscription':value}
        with self.assertRaises(ValueError):launch.subscription_active({'pricing-plan-manager':client})
        value['resourceArns']=['arn:aws:cloudfront::'+launch.ACCOUNT+':distribution/'+launch.DISTRIBUTION,
                              'arn:aws:wafv2:'+launch.REGION+':'+launch.ACCOUNT+':global/webacl/'+launch.WAF_NAME+'/'+launch.WAF_ID]
        launch.subscription_active({'pricing-plan-manager':client})
        client.get_subscription.assert_called_with(arn=launch.SUBSCRIPTION)
        # The live API omits usageLevel for this DEFAULT Pro subscription.
        del value['usageLevel']
        launch.subscription_active({'pricing-plan-manager':client})
        value['usageLevel']='EXPANDED'
        with self.assertRaises(ValueError):launch.subscription_active({'pricing-plan-manager':client})
        del value['usageLevel']
        value['scheduledChange']={'changeType':'CANCELLATION'}
        with self.assertRaises(ValueError):launch.subscription_active({'pricing-plan-manager':client})

    def test_exact_dependency_only_subscription_row_allowed(self):
        expected={'ClosedWebAcl':'Modify','Distribution':'Modify'}
        rows=[{'LogicalResourceId':name,'Action':action,'Replacement':'False'} for name,action in expected.items()]
        dependency={'LogicalResourceId':'ProSubscription','Action':'Modify','Replacement':'False',
            'ResourceType':'AWS::PricingPlanManager::Subscription','PhysicalResourceId':launch.SUBSCRIPTION,
            'Scope':['Properties'],'Details':[{'Evaluation':'Dynamic','ChangeSource':'ResourceAttribute',
                'CausingEntity':'ClosedWebAcl.Arn','Target':{'Attribute':'Properties','Name':'ResourceArns','RequiresRecreation':'Never'}}]}
        launch.review_changes(rows+[dependency],expected,'edge')
        mutations=[('Replacement','Conditional'),('PhysicalResourceId','another'),('Action','Add'),('Scope',['Properties','Metadata'])]
        for key,value in mutations:
            bad=copy.deepcopy(dependency);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):launch.review_changes(rows+[bad],expected,'edge')
        for field,value in [('Evaluation','Static'),('ChangeSource','DirectModification'),('CausingEntity','Distribution.Arn')]:
            bad=copy.deepcopy(dependency);bad['Details'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):launch.review_changes(rows+[bad],expected,'edge')
        for field,value in [('Name','PlanTier'),('RequiresRecreation','Conditionally')]:
            bad=copy.deepcopy(dependency);bad['Details'][0]['Target'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):launch.review_changes(rows+[bad],expected,'edge')
        bad=copy.deepcopy(dependency);bad['Details'].append(copy.deepcopy(bad['Details'][0]))
        with self.assertRaises(ValueError):launch.review_changes(rows+[bad],expected,'edge')
        with self.assertRaises(ValueError):launch.review_changes(rows+[dependency],expected,'network')


if __name__=='__main__':unittest.main()
