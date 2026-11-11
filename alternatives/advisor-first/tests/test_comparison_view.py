"""Run the actual preparation renderer's behavioral checks in the normal suite."""
from pathlib import Path
import shutil
import subprocess
import unittest


class ComparisonViewTests(unittest.TestCase):
    def test_preparation_renderer(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        result = subprocess.run([node, '--test', str(Path(__file__).with_suffix('.js'))],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
