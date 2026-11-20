"""Offline boundary checks for the exact D194 permission preview."""
import copy
import unittest

import build_runtime_access as build
from build_pro_migration import network


class RuntimeAccessTests(unittest.TestCase):
    def test_every_resource_except_existing_role_is_preserved(self):
        before, after = network('attach-address'), build.template()
        self.assertEqual(before['Parameters'], after['Parameters'])
        self.assertEqual(before['Outputs'], after['Outputs'])
        self.assertEqual(set(before['Resources']), set(after['Resources']))
        for name in before['Resources']:
            if name != 'HostRole':
                self.assertEqual(before['Resources'][name], after['Resources'][name], name)
        prior = before['Resources']['HostRole']['Properties']
        role = copy.deepcopy(after['Resources']['HostRole']['Properties'])
        self.assertEqual(role['Policies'][:-1], prior['Policies'])
        role['Policies'].pop()
        self.assertEqual(role, prior)

    def test_new_permissions_are_read_only_and_exactly_scoped(self):
        role = build.template()['Resources']['HostRole']['Properties']
        statements = role['Policies'][-1]['PolicyDocument']['Statement']
        actions = {a for s in statements for a in s['Action']}
        self.assertEqual(actions, {'s3:GetObject', 'kms:Decrypt', 'acm:DescribeCertificate',
                                   'acm:GetCertificate', 'acm:ExportCertificate'})
        self.assertEqual(statements[0]['Resource'],
                         {'Fn::Sub': '${BackupBucket.Arn}/' + build.ARTIFACT_KEY})
        self.assertEqual(statements[2]['Resource'], build.ORIGIN_CERTIFICATE)
        self.assertIn('kms:ViaService', statements[1]['Condition']['StringEquals'])
        self.assertIn('kms:EncryptionContext:aws:s3:arn', statements[1]['Condition']['StringEquals'])

    def test_change_review_rejects_ingress_extra_resources_and_replacement(self):
        good = {'Status': 'CREATE_COMPLETE', 'ExecutionStatus': 'AVAILABLE', 'Changes': [
            {'ResourceChange': {'LogicalResourceId': 'HostRole', 'Action': 'Modify',
                'Replacement': 'False', 'ResourceType': 'AWS::IAM::Role', 'Scope': ['Properties'],
                'Details': [{'Target': {'Name': 'Policies'}}]}}]}
        build.validate_changes(good)
        for field, value in [('LogicalResourceId', 'HostSecurityGroup'), ('Replacement', 'True'),
                             ('Replacement', 'Conditional'), ('Action', 'Add')]:
            bad = copy.deepcopy(good)
            bad['Changes'][0]['ResourceChange'][field] = value
            with self.assertRaises(ValueError):
                build.validate_changes(bad)
        bad = copy.deepcopy(good)
        bad['Changes'].append(copy.deepcopy(bad['Changes'][0]))
        with self.assertRaises(ValueError):
            build.validate_changes(bad)


if __name__ == '__main__':
    unittest.main()
