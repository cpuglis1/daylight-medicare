import importlib.util
import os
from pathlib import Path
import unittest

PACKAGE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fictional_compact',PACKAGE/'tests/test_compact_database_r2.py')
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
spec=importlib.util.spec_from_file_location('compact_range',PACKAGE/'tools/compact_range.py')
ranges=importlib.util.module_from_spec(spec);spec.loader.exec_module(ranges)


@unittest.skipUnless(os.environ.get('DAYLIGHT_COMPACT_TESTS') == '1', 'Explicit local fictional PostgreSQL fixture run required')
class PackedRangeTests(unittest.TestCase):
    def test_complete_partial_blocks_match_source_and_point_view_and_other_ranges_reject(self):
        fixture=support.CompactBlockPostgresTests
        fixture.setUpClass()
        try:
            support.c.load_chunk(fixture.source,fixture.target,fixture.source_set,3,20)
            for first,last in ((1,2),(3,20)):
                params=('b'*64,'fixture',first,last)
                self.assertEqual(ranges.raw_hash(fixture.target,params),support.c.binary_hash(fixture.source,support.c.RAW_QUERY,params))
                self.assertEqual(ranges.raw_hash(fixture.target,params),support.c.binary_hash(fixture.target,support.c.RAW_QUERY,params))
            with self.assertRaisesRegex(ValueError,'checkpoint'):
                ranges.raw_hash(fixture.target,('b'*64,'fixture',2,3))
        finally:fixture.tearDownClass()


if __name__=='__main__':unittest.main()
