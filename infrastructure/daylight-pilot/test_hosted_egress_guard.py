import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('guard',Path(__file__).with_name('hosted_egress_guard.py'))
guard=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(guard)


class EgressTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'allowance.json'
        patcher=patch.object(guard,'STATE',self.path);patcher.start();self.addCleanup(patcher.stop)
        self.table={'nftables':[{'table':{'family':'inet','name':guard.TABLE}},
            {'quota':{'name':'origin','bytes':guard.ORIGIN_BYTES,'used':1,'handle':5}}]}

    def state(self,phase='active'):
        state={'schema':1,'uid':998,'resolvers':['169.254.169.253'],
            'origin_bytes':guard.ORIGIN_BYTES,'app_bytes':guard.APP_BYTES,
            'phase':phase,'fingerprint':guard.fingerprint(self.table)}
        guard.durable_write(self.path,state)

    def test_rules_cover_both_families_metadata_protocols_and_loopback(self):
        value=guard.rules(998,['169.254.169.253','fd00:ec2::253'])
        self.assertIn('table inet daylight_egress',value)
        self.assertIn('ip6 daddr fd00:ec2::254 drop',value)
        self.assertLess(value.index('169.254.169.254 drop'),value.index('oifname "lo" return'))
        self.assertLess(value.index('oifname "lo" return'),value.index('quota name "origin"'))
        self.assertIn('udp sport 443 quota name "origin" drop',value)
        self.assertIn('meta skuid 998 quota name "provider" drop',value)
        self.assertTrue(value.rstrip().endswith('}\n}'))

    def test_no_shell_syntax_or_root_uid(self):
        for uid in (0,-1,'998; accept',True):
            with self.assertRaises(ValueError):guard.rules(uid,[])
        with self.assertRaises(ValueError):guard.rules(998,['1.2.3.4; accept'])

    def test_grant_is_durable_before_kernel_change(self):
        seen=[]
        def command(args,**kwargs):
            if args==[guard.NFT,'--file','-']:
                self.assertEqual(json.loads(self.path.read_text())['phase'],'fully_debited')
                seen.append('grant')
            return SimpleNamespace(returncode=3,stdout='')
        with patch.object(guard,'live_table',side_effect=[None,self.table]),patch.object(guard,'command',side_effect=command):
            result=guard.initialize(998,['169.254.169.253'])
        self.assertEqual(seen,['grant']);self.assertTrue(result['active'])
        self.assertEqual(json.loads(self.path.read_text())['phase'],'active')

    def test_no_automatic_regrant(self):
        self.state()
        with self.assertRaises(ValueError):guard.initialize(998,[])

    def test_live_restart_preserves_kernel_counters(self):
        self.state()
        changed=json.loads(json.dumps(self.table));changed['nftables'][1]['quota']['used']=2000
        with patch.object(guard,'live_table',return_value=changed),patch.object(guard,'command') as command:
            result=guard.enforce();command.assert_not_called()
        self.assertTrue(result['reused_counters'])

    def test_reboot_closes_instead_of_replenishing(self):
        self.state();seen=[]
        def command(args,**kwargs):
            if 'data' in kwargs:seen.append(kwargs['data'])
            return SimpleNamespace(returncode=0,stdout='')
        with patch.object(guard,'live_table',side_effect=[None,self.table]),patch.object(guard,'command',side_effect=command):
            result=guard.enforce()
        self.assertFalse(result['active'])
        self.assertTrue(all('tcp sport 443 drop' in x and 'quota name' not in x for x in seen))
        self.assertEqual(json.loads(self.path.read_text())['phase'],'closed')

    def test_rule_drift_refuses_startup(self):
        self.state();modified=json.loads(json.dumps(self.table));modified['nftables'][1]['quota']['bytes']*=2
        with patch.object(guard,'live_table',return_value=modified):
            with self.assertRaises(ValueError):guard.enforce()

    def test_missing_state_refuses_startup(self):
        with self.assertRaises(ValueError):guard.enforce()

    def test_crash_after_debit_never_regrants(self):
        self.state(phase='fully_debited')
        with patch.object(guard,'live_table',return_value=self.table):
            with self.assertRaises(ValueError):guard.enforce()

    def test_nft_read_failure_not_treated_as_empty_rules(self):
        self.state()
        with patch.object(guard,'command',side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError):guard.enforce()


if __name__=='__main__':unittest.main()
