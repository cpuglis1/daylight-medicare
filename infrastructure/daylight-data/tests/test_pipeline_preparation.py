"""Catalog preparation preserves complete input scope, numbers and quarantine."""
from copy import deepcopy
from decimal import Decimal
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from daylight_data.comparison_pipeline import preparation
from daylight_data.comparison_pipeline.adapters import normalize_task
from daylight_data.comparison_pipeline.common import canonical, digest, file_hash, safe_json
from daylight_data.comparison_pipeline.runner import read_records, validate_manifest

OFFERING = "2026:H1045:048:002"
OTHER = "2026:H0000:001:000"
FAMILIES = ("authorization", "referral", "network_and_setting", "deductible",
            "frequency_and_quantity", "covered_days", "shared_allowance",
            "qualification", "exclusion", "waiver_and_replacement")


def record(identifier="record-one", roots=None):
    roots = roots or ["original-one"]
    identity = dict(year=2026, contract="H1045", plan="048", segment="002",
                    geography="Published county", geographic_variant="Exact source publication")
    def observation(side):
        evidence = {"side": side, "source_sha256": ("a" if side == "cms" else "b") * 64,
                    "interpretation_review_id": "unaccepted-fixture-reading"}
        if side == "cms":
            evidence.update(member="official.json", pointer="/exact/field")
        else:
            evidence.update(pdf_page=2, passage_sha256="c" * 64,
                            location={"column": "in-network"}, headers=["Full header"],
                            footnotes=["Full qualification and exception"])
        return {"identity": deepcopy(identity),
            "service": {"category": "office", "subtype": "Exact qualified service"},
            "context": {"network": "in_network", "setting": "office", "population": "members",
                        "assistance_basis": "published general schedule"},
            "cost": {"kind": "copayment", "amount": "10.00", "range_basis": "source amount"},
            "unit": {"currency_or_percentage": "USD", "denominator": "one qualified visit", "period": "per visit"},
            "boundaries": {"day_bands": [], "quantity": "One encounter", "frequency": "Per encounter",
                           "reset": "No accumulating allowance asserted"},
            "conditions": {f: {"state": "asserted", "assertion": "Exact condition " + f,
                "obligation_ids": list(roots), "evidence_ids": ["proof"],
                "interpretation_review_id": "unaccepted-fixture-reading"} for f in FAMILIES},
            "exceptions": [{"if": "qualified source exception", "then": "retain distinct alternative"}],
            "variant": {"kind": "base", "identifier": "base", "enrollment_basis": "source membership",
                        "effective_period": "2026 plan year"},
            "shared_budgets": [], "evidence": [evidence]}
    return {"id": identifier, "inventory_root_ids": list(roots), "cms": observation("cms"),
            "carrier": observation("carrier"), "outcome": "exact_agreement",
            "interpretation_review_receipt": "unaccepted-fixture", "accepted_for_reference": False}


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repository = Path(self.temporary.name).resolve()
        self.output = self.repository / "prepared"

    def catalog(self, records, name="catalog.jsonl.gz", *, bundle=True, offering=OFFERING):
        path = self.repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith((".jsonl", ".jsonl.gz")):
            payload = b"\n".join(canonical(r) for r in records) + b"\n"
        else:
            payload = canonical(records)
        path.write_bytes(gzip.compress(payload, mtime=0) if name.endswith(".gz") else payload)
        return {"path": name, "sha256": file_hash(path), "offering_id": offering,
                "bundle_by_original_ids": bundle}

    def spec(self, records=None, **kwargs):
        return {"offerings": [OFFERING], "catalogs": [self.catalog(records or [record()], **kwargs)]}

    def prepare(self, spec, output=None):
        result = preparation.prepare_batch(self.repository, spec, output or self.output)
        manifest = safe_json((self.repository / result["manifest_path"]).read_bytes())
        provenance = safe_json((self.repository / result["provenance_path"]).read_bytes())
        records = [raw for entry in manifest["inputs"]
                   for raw in read_records(self.repository / entry["path"])]
        return result, manifest, provenance, records

    def assert_unpublished(self):
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.repository.glob(".comparison-prepare-*")))

    def test_bundle_preserves_two_full_components_order_and_exact_scope(self):
        first = record("one", ["B", "A"])
        second = record("two", ["A", "B"])
        second["carrier"]["conditions"]["qualification"]["assertion"] = "Additional distinct condition"
        second["carrier"]["evidence"][0]["footnotes"] += ["Parallel branch retained"]
        spec = self.spec([first, second]); before = deepcopy(spec)
        result, manifest, provenance, records = self.prepare(spec)
        validate_manifest(manifest)
        self.assertEqual(spec, before)
        self.assertEqual(result["catalog_record_count"], 2)
        self.assertEqual(result["prepared_task_count"], 1)
        self.assertEqual(records[0]["original_ids"], ["A", "B"])
        self.assertEqual(records[0]["components"], [first, second])
        self.assertEqual(normalize_task(records[0])["components"], [first, second])
        self.assertEqual([p["component_index"] for p in provenance["records"]], [0, 1])
        self.assertFalse(provenance["semantic_completeness_inferred"])
        self.assertFalse(result["accepted_for_reference"])
        self.assertFalse(result["consumer_usable"])
        self.assertEqual(file_hash(self.repository / result["manifest_path"]), result["manifest_sha256"])

    def test_only_identical_whole_original_sets_group_not_overlaps(self):
        _, _, _, values = self.prepare(self.spec([
            record("a", ["A"]), record("ab", ["A", "B"]), record("b", ["B"]), record("a2", ["A"])]))
        self.assertEqual([r["original_ids"] for r in values], [["A"], ["A", "B"], ["B"]])
        self.assertEqual([c["id"] for c in values[0]["components"]], ["a", "a2"])

    def test_bundle_id_stable_when_condition_changes_but_content_hash_changes(self):
        first = record("one")
        _, manifest, _, rows = self.prepare(self.spec([first]))
        first["carrier"]["conditions"]["qualification"]["assertion"] += " New material condition."
        _, changed, _, new = self.prepare(self.spec([first]), self.repository / "prepared-two")
        self.assertEqual(rows[0]["id"], new[0]["id"])
        self.assertNotEqual(digest(rows[0]), digest(new[0]))
        self.assertNotEqual(manifest["inputs"][0]["sha256"], changed["inputs"][0]["sha256"])

    def test_catalog_identity_not_content_or_selected_group_order(self):
        spec = self.spec([record()])
        _, _, _, a = self.prepare(spec)
        spec2 = {"offerings": [OFFERING], "catalogs": [self.catalog([record()], "other.json")]}
        _, _, _, b = self.prepare(spec2, self.repository / "second")
        self.assertNotEqual(a[0]["id"], b[0]["id"])

    def test_unbundled_records_and_all_supported_file_transports(self):
        for name in ("one.json", "one.json.gz", "one.jsonl", "one.jsonl.gz"):
            with self.subTest(name=name):
                _, _, _, rows = self.prepare(self.spec([record()], name=name, bundle=False),
                                              self.repository / name.replace(".", "-") )
                self.assertEqual(rows, [record()])
        spec = self.spec(name="single.json", bundle=False)
        (self.repository / "single.json").write_bytes(canonical(record()))
        spec["catalogs"][0]["sha256"] = file_hash(self.repository / "single.json")
        self.assertEqual(self.prepare(spec)[3], [record()])

    def test_schema_invalid_record_is_explicit_separate_quarantine_with_raw_contents(self):
        invalid = record("invalid")
        invalid["carrier"]["unknown_material_rule"] = {"whole_parent": "Retain every clause"}
        result, _, provenance, rows = self.prepare(self.spec([record(), invalid]))
        self.assertEqual(result["quarantine_pending_count"], 1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1], invalid)
        self.assertEqual(provenance["records"][1]["normalization"], "quarantine_pending")
        self.assertIn("strict_r9_schema_violation", provenance["records"][1]["normalization_error"])
        with self.assertRaises(ValueError):
            normalize_task(rows[1], offering_id=OFFERING)

    def test_mixed_registered_artifacts_pass_through_with_unknown_and_invalid_quarantine(self):
        def artifact(kind, identifier, **fields):
            return {"artifact_type": kind, "id": identifier, "offering_id": OFFERING,
                    "original_ids": ["original-one"], **fields}
        cell = artifact("carrier_price_cell", "cell", cell_text="$0 if qualified; other charges may apply.",
                        source_complete=True, condition_context={"full_parent": "Complete governing source"})
        native = artifact("native_literal", "native", payload={"literal": 6}, pointer="/literal")
        gap = artifact("source_gap", "gap", gap={"required_source": "Existing document gap", "status": "missing"})
        unknown = artifact("not_a_registered_family", "unknown", payload={"retain": "full original"})
        invalid = artifact("native_literal", "invalid-native", payload={"literal": 6}, pointer="/absent")
        raws = [record("first"), cell, native, gap, unknown, invalid, record("second")]
        result, _, provenance, rows = self.prepare(self.spec(raws))
        self.assertEqual(result["bundle_count"], 1)
        self.assertEqual(result["quarantine_pending_count"], 2)
        self.assertEqual(rows[0]["components"], [raws[0], raws[-1]])
        self.assertEqual(rows[1:], raws[1:-1])
        self.assertEqual([r["normalization"] for r in provenance["records"]], [
            "strict_r9_valid", "registered_artifact_valid", "registered_artifact_valid",
            "registered_artifact_valid", "quarantine_pending", "quarantine_pending", "strict_r9_valid"])
        self.assertEqual(normalize_task(rows[3], offering_id=OFFERING)["components"], [])

    def test_native_is_never_wrapped_into_an_empty_component_bundle(self):
        native = {"artifact_type": "native_literal", "id": "native", "offering_id": OFFERING,
                  "original_ids": ["original-one"], "inventory_root_ids": ["original-one"],
                  "payload": {"native_decimal": Decimal("0.12345678901234567890123456789")},
                  "pointer": "/native_decimal"}
        result, _, provenance, rows = self.prepare(self.spec([native]))
        self.assertEqual(result["bundle_count"], 0)
        self.assertEqual(result["quarantine_pending_count"], 0)
        self.assertEqual(rows, [native])
        self.assertEqual(provenance["records"][0]["component_index"], None)
        self.assertEqual(normalize_task(rows[0], offering_id=OFFERING)["components"], [])

    def test_duplicate_component_ids_not_hidden_inside_bundle_or_quarantine(self):
        for malformed in (False, True):
            a, b = record("same"), record("same")
            if malformed:
                b["carrier"]["bad"] = "Schema rejection does not exempt duplicate identity"
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, "Duplicate catalog comparison"):
                self.prepare(self.spec([a, b]))
            self.assert_unpublished()

    def test_duplicate_ids_across_catalogs_and_duplicate_original_scope_fail(self):
        spec = self.spec([record()])
        spec["catalogs"].append(self.catalog([record()], "second.json"))
        with self.assertRaisesRegex(ValueError, "Duplicate catalog comparison"):
            self.prepare(spec)
        value = record(); value["inventory_root_ids"].append(value["inventory_root_ids"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate original IDs"):
            self.prepare(self.spec([value]))
        self.assert_unpublished()

    def test_catalog_container_provenance_does_not_force_semantic_replays(self):
        spec = self.spec([record("a")])
        spec["catalogs"].append(self.catalog([record("b")], "second.json"))
        _, manifest, _, _ = self.prepare(spec)
        self.assertEqual(manifest["inputs"][0]["dependency_paths"], [])
        self.assertEqual(manifest["inputs"][1]["dependency_paths"], [])
        self.assertTrue(all(c["path"] in {s["path"] for s in manifest["sources"]} for c in spec["catalogs"]))

    def test_unavailable_or_changed_validator_authority_is_not_mass_quarantine(self):
        spec = self.spec()
        for code in ("strict_validator_unavailable", "sealed_authority_unavailable", "sealed_authority_changed"):
            with self.subTest(code=code), patch.object(preparation, "normalize_task", side_effect=ValueError(code + " at /: unavailable")):
                with self.assertRaisesRegex(ValueError, "Preparation authority unavailable"):
                    self.prepare(spec)
            self.assert_unpublished()

    def test_scope_mismatch_in_each_side_fails_even_for_schema_invalid_record(self):
        for side in ("cms", "carrier"):
            value = record()
            value[side]["identity"].update(contract="H0000", plan="001", segment="000")
            value["bad"] = "Must not use schema quarantine to hide foreign scope"
            with self.subTest(side=side), self.assertRaisesRegex(ValueError, "Offering scope mismatch"):
                self.prepare(self.spec([value]))
            self.assert_unpublished()

    def test_catalog_scope_and_envelope_scope_fail(self):
        spec = self.spec(); spec["catalogs"][0]["offering_id"] = OTHER
        with self.assertRaisesRegex(ValueError, "outside the preparation scope"):
            self.prepare(spec)
        value = record(); value["offering_id"] = OTHER
        with self.assertRaisesRegex(ValueError, "Offering scope mismatch"):
            self.prepare(self.spec([value]))
        self.assert_unpublished()

    def test_all_inputs_pinned_and_catalogs_retained_as_provenance(self):
        spec = self.spec()
        entries = {}
        for kind, payload in (("sources", {"source": "full bytes"}),
                              ("mapping_registries", {"mapping": {"review_decision": "held"}}),
                              ("source_reviews", {"review_id": "unapproved", "decision": "held"})):
            path = self.repository / f"{kind}.json"
            path.write_bytes(canonical(payload))
            entries[kind] = [{"path": path.name, "sha256": file_hash(path), "role": kind}]
        spec.update(entries, metadata={"parent_manifest": "exact previous source preparation"})
        _, manifest, provenance, _ = self.prepare(spec)
        for kind in ("mapping_registries", "source_reviews"):
            self.assertEqual(manifest[kind], spec[kind])
        catalog = spec["catalogs"][0]
        self.assertIn({"path": catalog["path"], "sha256": catalog["sha256"],
                       "role": "comparison_catalog_provenance"}, manifest["sources"])
        self.assertEqual(manifest["inputs"][0]["dependency_paths"], [])
        self.assertEqual(provenance["spec"], spec)
        self.assertEqual(len(provenance["input_byte_bindings"]), 4)

    def test_only_explicit_substantive_context_dependencies_pass_through(self):
        spec = self.spec()
        path = self.repository / "context.txt"
        path.write_bytes(b"Full substantive governing context")
        spec["sources"] = [{"path": path.name, "sha256": file_hash(path), "role": "source_context"}]
        spec["catalogs"][0]["dependency_paths"] = [path.name]
        _, manifest, _, _ = self.prepare(spec)
        self.assertEqual(manifest["inputs"][0]["dependency_paths"], [path.name])
        spec["catalogs"][0]["dependency_paths"] = ["unbound.txt"]
        with self.assertRaisesRegex(ValueError, "absent from the pinned"):
            self.prepare(spec, self.repository / "another")

    def test_sha_drift_of_catalog_source_registry_and_review_rejects(self):
        for kind in ("catalogs", "sources", "mapping_registries", "source_reviews"):
            spec = self.spec()
            if kind == "catalogs":
                entry = spec[kind][0]
            else:
                path = self.repository / (kind + ".json")
                path.write_bytes(b"{}")
                entry = {"path": path.name, "sha256": file_hash(path)}
                spec[kind] = [entry]
            (self.repository / entry["path"]).write_bytes(b"changed")
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "byte binding changed"):
                self.prepare(spec)
            self.assert_unpublished()

    def test_strict_json_duplicate_keys_and_nonfinite_constants_fail_before_publication(self):
        for payload in (b'{"id":"a","id":"b"}', b'{"amount":NaN}', b'{"amount":Infinity}'):
            spec = self.spec(name="malformed.json")
            path = self.repository / "malformed.json"
            path.write_bytes(payload); spec["catalogs"][0]["sha256"] = file_hash(path)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.prepare(spec)
            self.assert_unpublished()

    def test_exact_decimal_source_number_never_round_trips_through_float(self):
        value = record()
        value["carrier"]["cost"]["amount"] = Decimal("10.12345678901234567890123456789")
        spec = self.spec([value], bundle=False)
        result, manifest, provenance, _ = self.prepare(spec)
        path = self.repository / manifest["inputs"][0]["path"]
        with gzip.open(path, "rb") as stream:
            raw = safe_json(stream.read(), exact_decimals=True)
        self.assertEqual(raw["carrier"]["cost"]["amount"], value["carrier"]["cost"]["amount"])
        # Sealed-r9 numeric semantics cannot silently coerce this source number
        # to a string/rounded float. Retain its exact bytes for quarantine.
        self.assertEqual(result["quarantine_pending_count"], 1)
        self.assertIn("strict_decimal_not_roundtrippable", provenance["records"][0]["normalization_error"])
        self.assertEqual(provenance["records"][0]["record_sha256"], digest(value))

    def test_invalid_record_keeps_exact_decimal_for_later_quarantine_encoding(self):
        value = record()
        value["invalid_source_field"] = Decimal("0.12345678901234567890123456789")
        result, _, provenance, rows = self.prepare(self.spec([value]))
        self.assertEqual(result["quarantine_pending_count"], 1)
        self.assertEqual(rows, [value])
        self.assertEqual(provenance["records"][0]["record_sha256"], digest(value))

    def test_changed_source_during_staging_cleans_up_without_publishing(self):
        spec = self.spec()
        original = preparation._write_json
        def change_source(path, value):
            original(path, value)
            (self.repository / spec["catalogs"][0]["path"]).write_bytes(b"changed after parsing")
        with patch.object(preparation, "_write_json", side_effect=change_source), self.assertRaisesRegex(ValueError, "during preparation"):
            self.prepare(spec)
        self.assert_unpublished()

    def test_existing_and_racing_destinations_never_overwritten(self):
        spec = self.spec()
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.prepare(spec)
        self.output.rmdir()
        original = preparation._publish
        def race(staging, output):
            output.mkdir()
            original(staging, output)
        with patch.object(preparation, "_publish", side_effect=race), self.assertRaisesRegex(ValueError, "already exists"):
            self.prepare(spec)
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertFalse(list(self.repository.glob(".comparison-prepare-*")))

    def test_output_must_be_new_and_bounded_including_dangling_symlink(self):
        spec = self.spec()
        with self.assertRaisesRegex(ValueError, "under the repository"):
            self.prepare(spec, self.repository.parent / "outside-prepared")
        self.output.symlink_to(self.repository / "uncreated")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.prepare(spec)
        self.assertFalse((self.repository / "uncreated").exists())

    def test_replay_is_byte_stable_with_same_input_and_destination_identity(self):
        spec = self.spec([record("a"), record("b")])
        first = self.prepare(spec)[0]
        artifacts = {p.relative_to(self.output).as_posix(): p.read_bytes()
                     for p in self.output.rglob("*") if p.is_file()}
        import shutil
        shutil.rmtree(self.output)
        second = self.prepare(spec)[0]
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(artifacts, {p.relative_to(self.output).as_posix(): p.read_bytes()
                                    for p in self.output.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
