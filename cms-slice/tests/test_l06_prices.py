"""Corruption checks for the independent raw-source price comparator."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from l06_validate import compare_source_row


class SourcePriceCorruptionTests(unittest.TestCase):
    def setUp(self):
        # Synthetic identifiers and price; never presented as a real product.
        self.raw = b'H9999|001|000|12345678901|30|1.2345\r\n'
        self.row = (2, '2026:H9999:001:000', 'H9999', '001', '000',
                    '12345678901', 30, 12345, '1.2345', self.raw, 'published_average')

    def test_exact_native_row_is_accepted(self):
        compare_source_row(2, self.raw, self.row)

    def test_altered_modeled_amount_is_rejected_even_when_raw_copy_is_kept(self):
        row = list(self.row)
        row[7] = 12346
        with self.assertRaisesRegex(ValueError, 'Modeled price differs'):
            compare_source_row(2, self.raw, row)

    def test_deleted_source_row_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing from inventory'):
            compare_source_row(2, self.raw, None)

    def test_each_native_identity_cost_or_supply_change_is_rejected(self):
        for index, replacement in [(2, 'H9998'), (3, '002'), (4, '001'),
                                   (5, '12345678902'), (6, 90), (8, '1.2346')]:
            with self.subTest(column=index):
                row = list(self.row)
                row[index] = replacement
                with self.assertRaises(ValueError):
                    compare_source_row(2, self.raw, row)

    def test_relabeling_the_year_is_rejected(self):
        row = list(self.row)
        row[1] = '2027:H9999:001:000'
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            compare_source_row(2, self.raw, row)


if __name__ == '__main__':
    unittest.main()
