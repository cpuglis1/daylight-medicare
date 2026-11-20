"""Prove unexpected disks are rejected before formatting or filesystem writes."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import restore_private_display as restore


class VolumeGuards(unittest.TestCase):
    def test_rejects_wrong_or_populated_disk_before_format(self):
        base = {'path': '/dev/test-never-real', 'serial': restore.VOLUME_SERIAL,
                'size': 30 * 1024**3, 'fstype': None, 'mountpoints': [None]}
        cases = [({'serial': 'different'}, []), ({'size': 20 * 1024**3}, []),
                 ({'children': [{}]}, []), ({'fstype': 'ext4'}, []),
                 ({'mountpoints': ['/existing']}, []), ({}, [{'type': 'gpt'}])]
        for changes, signatures in cases:
            def run(*args, **kwargs):
                if args[0] == 'lsblk':
                    return json.dumps({'blockdevices': [dict(base, **changes)]}).encode()
                if args[0] == 'wipefs':
                    return json.dumps({'signatures': signatures}).encode()
                raise AssertionError('Unexpected command before rejection: ' + args[0])
            with self.subTest(changes=changes, signatures=signatures), \
                    patch.object(restore.os, 'geteuid', return_value=0), \
                    patch.object(restore.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1, pw_gid=1)), \
                    patch.object(restore, 'run', side_effect=run), \
                    patch.object(restore.Path, 'mkdir') as mkdir:
                with self.assertRaises(ValueError):
                    restore.main()
                mkdir.assert_not_called()


if __name__ == '__main__':
    unittest.main()
