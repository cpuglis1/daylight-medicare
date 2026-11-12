import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advisor_tests_needed import needed


class AdvisorTestsNeededTests(unittest.TestCase):
    def test_docs_and_repo_config_only_skip_the_suite(self):
        self.assertFalse(needed(["README.md", "docs/project/CURRENT_STATE.md",
                                 "DAYLIGHT_REQUIREMENTS.md", ".github/dependabot.yml"]))

    def test_any_code_or_data_file_runs_the_suite(self):
        for path in ("alternatives/advisor-first/natural_flow.py", "infrastructure/daylight-data/requirements.lock",
                     "docs/product/plan-comparison-2026-11-01/question-decision-map.json",
                     "tools/run_advisor_checks.py", ".github/workflows/repository-checks.yml",
                     "tools/advisor_tests_needed.py"):
            with self.subTest(path=path):
                self.assertTrue(needed(["README.md", path]))

    def test_markdown_inside_code_roots_runs_the_suite(self):
        for path in ("alternatives/advisor-first/web/notes.md", "infrastructure/daylight-data/README.md",
                     "cms-slice/README.md", "tools/README.md"):
            with self.subTest(path=path):
                self.assertTrue(needed([path]))

    def test_unknown_or_empty_diff_runs_the_suite(self):
        self.assertTrue(needed([]))


if __name__ == "__main__":
    unittest.main()
