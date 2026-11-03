"""Run the actual exact-reference renderer's behavioral checks in normal tests."""
from pathlib import Path
import shutil
import subprocess
import unittest


class ReferenceViewTests(unittest.TestCase):
    def test_reference_renderer(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        result = subprocess.run([node, '--test', str(Path(__file__).with_suffix('.js'))],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
