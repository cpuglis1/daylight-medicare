"""Inventory trust, exact encoding, cache corruption and transactional replay."""
from concurrent.futures import ThreadPoolExecutor
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from daylight_data.comparison_pipeline import inventory


def canonical(value, *, ascii=False):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=ascii, allow_nan=False).encode("utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repository = Path(self.temporary.name) / "repository"
        self.packet = self.repository / inventory._PACKET
        self.packet.mkdir(parents=True)
        self.database = Path(self.temporary.name) / "cache" / "inventory.sqlite3"
        self.rows = [
            {"id": "CANONICAL-001", "offering_id": "2026:H0001:001:000", "kind": "claim",
             "observation_ids": ["OBS-1", "OBS-2"], "detail": {"quote": "café — 腎"},
             "accepted_for_reference": False},
            {"id": "CANONICAL-002", "offering_id": "2026:H0001:002:000", "kind": "condition",
             "observation_ids": ["OBS-3"], "detail": {"required": "AND", "limit": None},
             "accepted_for_reference": False},
            {"id": "CANONICAL-003", "offering_id": "2026:H0001:001:000", "kind": "condition",
             "observation_ids": [], "detail": {"missing": True}, "accepted_for_reference": False},
            {"id": "CANONICAL-004", "offering_id": "2026:H0001:002:000", "kind": "claim",
             "observation_ids": ["OBS-4"], "detail": {}, "accepted_for_reference": False},
        ]
        self.expected_digest = hashlib.sha256(canonical(self.rows, ascii=True)).hexdigest()
        self.binding = {
            "algorithm": "SHA256 of all canonical records sorted by ID, compact sorted-key JSON array",
            "required_record_count": 4, "inventory_digest": self.expected_digest,
            "new_acceptance_inherited": False,
        }
        self.scope = [
            {"offering_id": "2026:H0001:001:000", "required": {"claim": 1, "condition": 1}},
            {"offering_id": "2026:H0001:002:000", "required": {"claim": 1, "condition": 1}},
        ]
        self.denominator = {"package_id": "fixture-r9", "required_claims": 2,
                            "required_conditions": 2, "required_total": 4, "offerings": 2}
        self._write_master(self.rows)
        self._write_controls()
        self.trusted = {**self.denominator, "inventory_digest": self.expected_digest,
                        "freeze_sha256": digest(self.packet / "freeze.json")}
        self.pinning = patch.dict(inventory._TRUSTED_RELEASE, self.trusted, clear=True)
        self.pinning.start()
        self.addCleanup(self.pinning.stop)

    def _write_master(self, rows):
        with gzip.open(self.packet / "master-inventory.jsonl.gz", "wb") as handle:
            for row in rows:
                handle.write(canonical(row) + b"\n")

    def _write_controls(self):
        for name, value in [("inventory-binding.json", self.binding),
                            ("denominator.json", self.denominator),
                            ("offering-inventory.json", self.scope)]:
            (self.packet / name).write_bytes(canonical(value))
        with (self.packet / "per-offering.csv").open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["offering_id", "required_claims", "required_conditions", "required_total"])
            for row in self.scope:
                values = row["required"]
                writer.writerow([row["offering_id"], values["claim"], values["condition"],
                                 sum(values.values())])
        self._reseal()

    def _reseal(self):
        freeze = {**self.denominator, "schema": "l03-semantic-inventory-freeze/1",
                  "inventory_digest": self.binding["inventory_digest"],
                  "semantic_claim_denominator_frozen": True,
                  "new_evidence_accepted": False, "fully_verified_L03": False,
                  "files_sha256": {name: digest(self.packet / name) for name in inventory._MEMBERS}}
        (self.packet / "freeze.json").write_bytes(canonical(freeze))

    def _trust_updated_fixture_bytes(self):
        # Only fixtures inject a release anchor; the production API has no
        # option to replace the sealed r9 scope or trust caller-supplied hashes.
        self._reseal()
        inventory._TRUSTED_RELEASE["freeze_sha256"] = digest(self.packet / "freeze.json")

    def build(self):
        return inventory.ensure_inventory(self.repository, self.database)

    def test_cold_and_warm_are_deterministic_and_do_not_decode_master_twice(self):
        cold = self.build()
        self.assertEqual(cold["mode"], "index_build")
        self.assertEqual((cold["record_count"], cold["offering_count"]), (4, 2))
        self.assertEqual(cold["inventory_digest"], self.expected_digest)
        before = digest(self.database)
        with patch.object(inventory, "_stream_originals", side_effect=AssertionError("master decoded")):
            with patch.object(inventory, "_file_hash", wraps=inventory._file_hash) as hashed:
                warm = self.build()
        self.assertEqual(warm["mode"], "cache_hit")
        self.assertTrue(warm["cache_hit"])
        self.assertFalse(warm["index_build"])
        self.assertEqual(warm["metadata_digest"], cold["metadata_digest"])
        self.assertIn((self.packet / "master-inventory.jsonl.gz").resolve(),
                      [c.args[0].resolve() for c in hashed.call_args_list])
        self.assertEqual(digest(self.database), before)
        self.assertEqual(warm["timings"]["index_build_seconds"], 0)
        self.assertFalse(warm["accepted_for_reference"])

    def test_original_hashes_use_utf8_and_query_keeps_exact_ids_kinds_observations(self):
        self.build()
        rows = inventory.originals_for_offering(self.database, "2026:H0001:001:000")
        self.assertEqual([r["id"] for r in rows], ["CANONICAL-001", "CANONICAL-003"])
        self.assertEqual(set(rows[0]), {"id", "offering_id", "kind", "original_sha256", "observation_ids"})
        self.assertEqual(rows[0]["original_sha256"], hashlib.sha256(canonical(self.rows[0])).hexdigest())
        self.assertNotEqual(rows[0]["original_sha256"], hashlib.sha256(canonical(self.rows[0], ascii=True)).hexdigest())
        self.assertEqual(rows[0]["observation_ids"], ["OBS-1", "OBS-2"])
        self.assertEqual(rows[1]["kind"], "condition")
        self.assertEqual(rows[1]["observation_ids"], [])

    def test_cache_contains_no_full_original_source_payloads(self):
        self.rows[0]["detail"]["quote"] = "SOURCE-PAYLOAD-" * 10000
        self.expected_digest = hashlib.sha256(canonical(self.rows, ascii=True)).hexdigest()
        self.binding["inventory_digest"] = self.expected_digest
        inventory._TRUSTED_RELEASE["inventory_digest"] = self.expected_digest
        self._write_master(self.rows)
        self._write_controls()
        self._trust_updated_fixture_bytes()
        self.build()
        with sqlite3.connect(self.database) as connection:
            columns = [r[1] for r in connection.execute("PRAGMA table_info(inventory_originals)")]
        self.assertEqual(columns, ["id", "offering_id", "kind", "original_sha256", "observation_ids_json"])
        self.assertLess(self.database.stat().st_size, 100000)
        self.assertNotIn(b"SOURCE-PAYLOAD-", self.database.read_bytes())

    def test_source_tamper_fails_even_on_warm_cache_and_preserves_cache(self):
        self.build()
        before = digest(self.database)
        with (self.packet / "master-inventory.jsonl.gz").open("ab") as handle:
            handle.write(b"changed")
        with self.assertRaisesRegex(inventory.InventorySourceError, "MEMBER_HASH"):
            self.build()
        self.assertEqual(digest(self.database), before)

    def test_coherent_freeze_edit_is_not_implicitly_a_new_trusted_release(self):
        self.build()
        self.binding["inventory_digest"] = "a" * 64
        self._write_controls()
        with self.assertRaisesRegex(inventory.InventorySourceError, "FREEZE_MISMATCH"):
            self.build()

    def test_digest_is_verified_even_when_compressed_member_hash_is_resealed(self):
        changed = copy.deepcopy(self.rows)
        changed[0]["detail"]["quote"] = "not the sealed meaning"
        self._write_master(changed)
        self._trust_updated_fixture_bytes()
        with self.assertRaisesRegex(inventory.InventorySourceError, "ASCII_DIGEST"):
            self.build()
        self.assertFalse(self.database.exists())

    def test_source_change_during_cold_build_never_publishes_an_index(self):
        original_stream = inventory._stream_originals

        def changing_stream(path):
            yield from original_stream(path)
            with (self.packet / "inventory-binding.json").open("ab") as handle:
                handle.write(b" ")

        with patch.object(inventory, "_stream_originals", changing_stream):
            with self.assertRaises(inventory.InventorySourceError):
                self.build()
        self.assertFalse(self.database.exists())
        self.assertEqual(list(self.database.parent.glob(".*.build-*")), [])

    def test_duplicate_and_out_of_order_originals_are_rejected(self):
        for rows in ([self.rows[1], self.rows[0]], [self.rows[0], self.rows[0]]):
            with self.subTest(rows=[r["id"] for r in rows]):
                self._write_master(rows)
                self._trust_updated_fixture_bytes()
                with self.assertRaisesRegex(inventory.InventorySourceError, "RECORD_SCOPE"):
                    self.build()
                self.assertFalse(self.database.exists())

    def test_per_offering_scope_checked_independently_of_global_count_and_digest(self):
        changed = copy.deepcopy(self.rows)
        changed[0]["offering_id"] = "2026:H0001:002:000"
        self.binding["inventory_digest"] = hashlib.sha256(canonical(changed, ascii=True)).hexdigest()
        inventory._TRUSTED_RELEASE["inventory_digest"] = self.binding["inventory_digest"]
        self._write_master(changed)
        self._write_controls()
        self._trust_updated_fixture_bytes()
        with self.assertRaisesRegex(inventory.InventorySourceError, "OFFERING_COUNTS"):
            self.build()

    def test_csv_scope_change_cannot_reuse_warm_cache(self):
        self.build()
        before = digest(self.database)
        path = self.packet / "per-offering.csv"
        path.write_text(path.read_text().replace(",1,1,2", ",2,0,2", 1))
        self._trust_updated_fixture_bytes()
        with self.assertRaisesRegex(inventory.InventorySourceError, "OFFERING_CSV"):
            self.build()
        self.assertEqual(digest(self.database), before)

    def test_same_count_cache_tamper_fails_global_and_offering_replay(self):
        self.build()
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE inventory_originals SET original_sha256=? WHERE id=?",
                               ("f" * 64, "CANONICAL-001"))
        before = digest(self.database)
        with self.assertRaises(inventory.InventoryCacheError):
            self.build()
        with self.assertRaises(inventory.InventoryCacheError):
            inventory.originals_for_offering(self.database, "2026:H0001:001:000")
        self.assertEqual(digest(self.database), before)

    def test_deleted_rows_and_incomplete_build_state_are_detected(self):
        for mutation in ("delete", "incomplete"):
            with self.subTest(mutation=mutation):
                self.database.unlink(missing_ok=True)
                self.build()
                with sqlite3.connect(self.database) as connection:
                    if mutation == "delete":
                        connection.execute("DELETE FROM inventory_originals WHERE id='CANONICAL-003'")
                    else:
                        metadata = json.loads(connection.execute("SELECT payload FROM inventory_metadata").fetchone()[0])
                        metadata["state"] = "building"
                        connection.execute("UPDATE inventory_metadata SET payload=?", (json.dumps(metadata),))
                with self.assertRaises(inventory.InventoryCacheError):
                    self.build()

    def test_cache_binding_tamper_is_not_mistaken_for_an_algorithm_upgrade(self):
        for field, value in (("source_fingerprint", "f" * 64),
                             ("accepted_for_reference", True),
                             ("metadata_digest", "invalid")):
            with self.subTest(field=field):
                self.database.unlink(missing_ok=True)
                self.build()
                with sqlite3.connect(self.database) as connection:
                    metadata = json.loads(connection.execute("SELECT payload FROM inventory_metadata").fetchone()[0])
                    metadata[field] = value
                    connection.execute("UPDATE inventory_metadata SET payload=?", (json.dumps(metadata),))
                before = digest(self.database)
                with self.assertRaises(inventory.InventoryCacheError):
                    self.build()
                self.assertEqual(digest(self.database), before)

    def test_missing_offering_metadata_is_cache_corruption_not_an_empty_scope(self):
        self.build()
        with sqlite3.connect(self.database) as connection:
            connection.execute("DELETE FROM inventory_offerings WHERE offering_id=?", ("2026:H0001:001:000",))
        with self.assertRaises(inventory.InventoryCacheError):
            inventory.originals_for_offering(self.database, "2026:H0001:001:000")

    def test_unknown_offering_fails_and_query_does_not_create_database(self):
        with self.assertRaises(inventory.InventoryCacheError):
            inventory.originals_for_offering(self.database, "missing")
        self.assertFalse(self.database.exists())
        self.build()
        with self.assertRaises(inventory.InventoryScopeError):
            inventory.originals_for_offering(self.database, "2027:H0001:001:000")
        with self.assertRaises(inventory.InventoryScopeError):
            inventory.originals_for_offering(self.database, "' OR 1=1 --")

    def test_unrelated_or_corrupt_database_is_not_overwritten(self):
        self.database.parent.mkdir(parents=True)
        self.database.write_bytes(b"not a SQLite database")
        before = self.database.read_bytes()
        with self.assertRaises(inventory.InventoryCacheError):
            self.build()
        self.assertEqual(self.database.read_bytes(), before)

    def test_algorithm_change_rebuilds_and_failed_rebuild_preserves_prior_cache(self):
        self.build()
        before = digest(self.database)
        with patch.object(inventory, "_ALGORITHM", "fixture-next-algorithm"):
            def broken_stream(_):
                yield self.rows[0]
                raise inventory.InventorySourceError("INJECTED_BUILD_INTERRUPTION")
            with patch.object(inventory, "_stream_originals", broken_stream):
                with self.assertRaisesRegex(inventory.InventorySourceError, "INTERRUPTION"):
                    self.build()
            self.assertEqual(digest(self.database), before)
            self.assertEqual(list(self.database.parent.glob(".*.build-*")), [])
            self.assertEqual(self.build()["mode"], "index_build")
            self.assertEqual(self.build()["mode"], "cache_hit")

    def test_concurrent_builders_publish_one_verified_cache(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            receipts = list(executor.map(lambda _: self.build(), range(2)))
        self.assertEqual(sorted(r["mode"] for r in receipts), ["cache_hit", "index_build"])
        self.assertEqual(receipts[0]["metadata_digest"], receipts[1]["metadata_digest"])

    def test_source_and_cache_symlinks_fail_closed(self):
        member = self.packet / "inventory-binding.json"
        outside = Path(self.temporary.name) / "binding.json"
        member.rename(outside)
        member.symlink_to(outside)
        with self.assertRaises(inventory.InventorySourceError):
            self.build()
        member.unlink()
        outside.rename(member)
        self.build()
        link = self.database.with_name("link.sqlite3")
        link.symlink_to(self.database)
        with self.assertRaises(inventory.InventoryCacheError):
            inventory.ensure_inventory(self.repository, link)


if __name__ == "__main__":
    unittest.main()
