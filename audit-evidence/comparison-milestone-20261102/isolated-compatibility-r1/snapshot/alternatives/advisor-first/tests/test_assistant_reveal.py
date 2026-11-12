"""Keep free frontend interaction checks in the ordinary Python test run."""
from pathlib import Path
import shutil
import subprocess
import unittest


class AssistantRevealTests(unittest.TestCase):
    def test_real_rendering_preserves_the_8891_reveal_contract(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for the assistant interaction checks.")
        script = Path(__file__).with_suffix(".js")
        result = subprocess.run(
            [node, "--test", str(script)],
            cwd=script.parent,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
