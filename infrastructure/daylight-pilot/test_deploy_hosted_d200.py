"""Offline checks for the D200 code-only deployment (no AWS, no host)."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import deploy_hosted_d200 as d

HERE = Path(__file__).resolve().parent
NEW = 'e' * 64


def unit(checks, OLD):
    return (f"[Unit]\nDescription=Daylight pilot\n[Service]\nUser=daylight-app\nWorkingDirectory={OLD}\n"
            "Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo\nEnvironment=DAYLIGHT_TOKEN_PREFLIGHT=local_bound\n"
            "Environment=DAYLIGHT_REVEAL_WPS=20\nEnvironment=DAYLIGHT_PRICING_REVIEW=/etc/daylight-pilot/pricing-review.json\n"
            f"MemoryMax={'2G' if checks else '900M'}\nEnvironment=DAYLIGHT_BLOCK_RELEASE=on\n"
            f"ExecStart=/opt/daylight-runtime/venv-3.14.7/bin/python {OLD}/alternatives/advisor-first/hosted_server.py "
            "--config /etc/daylight-pilot/runtime/pilot.json\n")


def config(checks, OLD):
    value = {'port': 19093, 'release': d.D199_RELEASE, 'binding': OLD + '/evidence/binding.json',
             'key_file': '/run/credentials/daylight-pilot.service/openai'}
    if checks:
        value.update(foundation_binding=OLD + '/evidence/foundation-binding.json',
                     foundation_root='/var/lib/daylight-state/foundation/2846f4415cf4',
                     foundation_dsn='x', controls_dsn='y')
    return json.dumps(value)


class D200DeployTests(unittest.TestCase):
    def setUp(self):
        self.d199 = d.load_d199(HERE)
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for name in ('units', 'config', 'state/operations', 'releases'):
            (self.root / name).mkdir(parents=True)
        for attr, sub in (('UNITS', 'units'), ('CONFIG', 'config'), ('STATE', 'state'), ('HOST_ROOT', '.')):
            patcher = patch.object(self.d199, attr, self.root / sub); patcher.start(); self.addCleanup(patcher.stop)

    def run_apply(self, environment, checks, release=d.D199_RELEASE):
        old = str(self.root / 'releases' / d.D199_RELEASE)
        (self.root / f'units/daylight-{environment}.service').write_text(unit(checks, old))
        raw = json.loads(config(checks, old)); raw['release'] = release
        (self.root / f'config/{environment}.json').write_text(json.dumps(raw))
        after = self.root / 'releases' / NEW
        with patch.object(d, 'read_plan', return_value={'release': NEW}), \
                patch.object(self.d199, 'stage', return_value=after), \
                patch.object(self.d199, 'switch') as switch:
            report = d.apply(self.root, 'unused', environment, self.d199)
        return report, switch

    def test_pilot_keeps_its_doctor_drug_checks_and_moves_only_the_release(self):
        report, switch = self.run_apply('pilot', checks=True)
        changes, environments, releases = switch.call_args.args
        self.assertEqual(environments, ['pilot']); self.assertEqual(releases, {'pilot': NEW})
        new_unit = changes[self.root / 'units/daylight-pilot.service'][1]
        new_config = json.loads(changes[self.root / 'config/pilot.json'][1])
        self.assertIn('MemoryMax=2G\n', new_unit); self.assertNotIn(d.D199_RELEASE, new_unit)
        self.assertEqual(new_config['foundation_root'], '/var/lib/daylight-state/foundation/2846f4415cf4')
        self.assertEqual(new_config['release'], NEW)
        self.assertTrue(report['checks_on_this_environment'])

    def test_test_stays_without_checks(self):
        _, switch = self.run_apply('test', checks=False)
        changes = switch.call_args.args[0]
        self.assertIn('MemoryMax=900M\n', changes[self.root / 'units/daylight-test.service'][1])
        self.assertNotIn('foundation_binding', json.loads(changes[self.root / 'config/test.json'][1]))

    def test_refuses_a_host_not_on_d199(self):
        with self.assertRaisesRegex(ValueError, 'not on the D199 release'):
            self.run_apply('test', checks=False, release='c' * 64)

    def test_changed_d199_tool_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'deploy_hosted_d199.py').write_text('# altered\n')
            with self.assertRaisesRegex(ValueError, 'differs from the deployed one'):
                d.load_d199(folder)


if __name__ == '__main__':
    unittest.main()
