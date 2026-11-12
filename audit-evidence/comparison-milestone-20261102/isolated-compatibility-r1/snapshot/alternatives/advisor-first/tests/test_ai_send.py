"""Free checks that a deliberate Send needs no second AI confirmation."""
from pathlib import Path
import shutil
import subprocess
import unittest


class AISendTests(unittest.TestCase):
    def test_send_is_one_deliberate_request_without_a_confirmation_modal(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for the Send interaction checks.")
        script = Path(__file__).with_suffix(".js")
        result = subprocess.run(
            [node, "--test", str(script)], cwd=script.parent,
            capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
