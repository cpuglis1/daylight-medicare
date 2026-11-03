import subprocess
from pathlib import Path
import unittest


class IdentityViewTests(unittest.TestCase):
    def test_identity_renderer_authority_and_interaction_contract(self):
        script=Path(__file__).with_suffix('.js')
        result=subprocess.run(['node','--test',str(script)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
