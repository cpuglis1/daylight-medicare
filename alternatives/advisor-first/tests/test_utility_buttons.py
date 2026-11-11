"""Execute the actual utility handlers without browser or paid model calls."""
from pathlib import Path
import shutil
import subprocess
import unittest


class UtilityButtonsTests(unittest.TestCase):
    def test_production_utility_handlers_preserve_privacy_and_visit_authority(self):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        script = Path(__file__).with_suffix('.js')
        result = subprocess.run([node, '--test', str(script)], cwd=script.parent,
                                capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
