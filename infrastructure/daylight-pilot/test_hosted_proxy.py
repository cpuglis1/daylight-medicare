"""Offline rendering checks; actual nginx -t remains an installation check."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install_hosted_proxy as proxy


class ProxyTests(unittest.TestCase):
    def test_token_cannot_inject_configuration(self):
        for token in ('','x'*31,'x'*257,'x'*32+'"; include evil;',None,'x'*32+'\n'):
            with self.subTest(token=repr(token)),self.assertRaises(ValueError):proxy.render(token)

    def test_exact_private_upstreams_and_default_denial(self):
        config=proxy.render('a'*64)
        self.assertIn('daylightmedicare.com http://127.0.0.1:19093;',config)
        self.assertIn('test.daylightmedicare.com http://127.0.0.1:19094;',config)
        self.assertIn('if ($daylight_backend = "") { return 444; }',config)
        self.assertIn('if ($daylight_origin_ok = 0) { return 444; }',config)
        self.assertNotIn('listen 80',config)
        self.assertIn('proxy_set_header X-Daylight-Origin-Token "";',config)

    def test_no_cache_logs_or_replayed_provider_requests(self):
        config=proxy.render('safe-test-token_'*4)
        for directive in ('access_log off;','error_log /dev/null crit;',
                          'proxy_cache off;','proxy_next_upstream off;',
                          'add_header Cache-Control "no-store" always;',
                          'client_max_body_size 80000;',
                          'limit_conn daylight_connections 24;'):
            self.assertIn(directive,config)

    def test_wrong_candidate_never_reconfigures_service(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'candidate';path.write_bytes(b'candidate');path.chmod(0o600)
            with patch.object(proxy,'CANDIDATE',path),patch.object(proxy,'private_file',return_value=b'candidate'),patch.object(proxy,'run') as run:
                with self.assertRaises(ValueError):proxy.activate('0'*64)
                run.assert_not_called()


if __name__=='__main__':unittest.main()
