import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_advisor_checks import assign, module_of, parse_shard


class FakeSuite:
    def __init__(self, count):
        self.count = count

    def countTestCases(self):
        return self.count


class ShardTests(unittest.TestCase):
    loaded = {f"test_m{i:02d}": FakeSuite(n) for i, n in enumerate([90, 5, 40, 40, 1, 0, 300, 12, 7, 66, 3])}

    def test_every_module_lands_in_exactly_one_shard(self):
        for count in (1, 2, 3, 4, 7):
            with self.subTest(count=count):
                parts = [assign(self.loaded, (i, count)) for i in range(1, count + 1)]
                flat = [m for part in parts for m in part]
                self.assertEqual(sorted(flat), sorted(self.loaded))
                self.assertEqual(len(flat), len(set(flat)))

    def test_no_shard_runs_everything_and_assignment_is_stable(self):
        self.assertEqual(assign(self.loaded, None), list(self.loaded))
        self.assertEqual(assign(self.loaded, (2, 4)), assign(dict(reversed(self.loaded.items())), (2, 4)))

    def test_known_failure_ids_map_to_their_module(self):
        self.assertEqual(module_of("test_curriculum_flow.CurriculumFlowTests.test_x"), "test_curriculum_flow")
        self.assertEqual(module_of("setUpClass (test_persona_journeys.CurrentPersonaJourneys)"), "test_persona_journeys")

    def test_shard_argument(self):
        self.assertIsNone(parse_shard(None))
        self.assertEqual(parse_shard("3/4"), (3, 4))
        for bad in ("0/4", "5/4"):
            with self.assertRaises(ValueError):
                parse_shard(bad)


if __name__ == "__main__":
    unittest.main()
