"""Exact historical inputs without downgrading or editing the working tree."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

PACKAGE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reconcile',PACKAGE/'tools/prepare_dependency_verification.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
spec=importlib.util.spec_from_file_location('contracts',PACKAGE/'tests/test_full_db_queries.py')
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
v=support.verifier


class ReconciliationTests(unittest.TestCase):
    def test_recovered_exact_archive_member_and_reject_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();data=b'fictional-library==1.0\n';bundle=root/'archive.tar.gz'
            with tarfile.open(bundle,'w:gz') as archive:
                member=tarfile.TarInfo(r.LOCK);member.size=len(data);archive.addfile(member,io.BytesIO(data))
            fingerprint=hashlib.sha256(data).hexdigest()
            receipt={'bundle_path':bundle.name,'bytes':bundle.stat().st_size,'sha256':r.digest(bundle),
                'files':[{'path':r.LOCK,'bytes':len(data),'sha256':fingerprint}]}
            path=root/'receipt.json';path.write_text(json.dumps(receipt))
            self.assertEqual(r.recover_lock(root,path.name,fingerprint)[0],data)
            with bundle.open('ab') as out:out.write(b'corrupt')
            with self.assertRaisesRegex(ValueError,'archive differs'):r.recover_lock(root,path.name,fingerprint)

    def test_original_verifier_keeps_pin_guard_while_exact_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as directory,patch.multiple(v,RAW_ROWS=15,PROJECTION_ROWS=15,UNIT_COUNT=15):
            root=Path(directory).resolve();packet,summary=support.fixture_contract(root)
            old=b'fictional-library==1.0\n';current=old+b'fictional-validator==2.0\n'
            active=root/r.LOCK;active.parent.mkdir(parents=True,exist_ok=True);active.write_bytes(current)
            manifest=json.loads((packet/'BUILD_MANIFEST.json').read_text())
            manifest['executable_files'][r.LOCK]=hashlib.sha256(old).hexdigest()
            target=json.loads((packet/'TARGET.json').read_text());target['build_id']=v.digest(manifest)
            target['marker']='daylight-local-full/1:'+target['build_id']
            complete=json.loads((packet/'LOAD_COMPLETE.json').read_text());complete.update(build_id=target['build_id'],target=target)
            for name,value in [('BUILD_MANIFEST',manifest),('TARGET',target),('LOAD_COMPLETE',complete)]:
                support.write_json(packet/(name+'.json'),value)
            before={name:r.digest(packet/name) for name in ('BUILD_MANIFEST.json','TARGET.json','LOAD_COMPLETE.json')}
            with self.assertRaisesRegex(ValueError,'Frozen implementation'):v.load_contract(root,packet,summary)
            pins={**manifest['executable_files'],**manifest['selected_receipt_files']}
            for name,h in before.items():pins[str((packet/name).relative_to(root))]=h
            snapshot=root/'isolated-snapshot';r.materialize(root,snapshot,pins,old)
            result=v.load_contract(snapshot,snapshot/packet.relative_to(root),snapshot/summary.relative_to(root))
            self.assertEqual(len(result['units']),15)
            self.assertEqual(active.read_bytes(),current)
            self.assertEqual((snapshot/r.LOCK).read_bytes(),old)
            self.assertTrue(all(r.digest(packet/name)==h for name,h in before.items()))
            # Other sealed changes still fail: this is not a blanket drift waiver.
            (snapshot/v.BUILDER).chmod(0o644);(snapshot/v.BUILDER).write_text('changed fictional adapter')
            with self.assertRaisesRegex(ValueError,'Frozen implementation'):
                v.load_contract(snapshot,snapshot/packet.relative_to(root),snapshot/summary.relative_to(root))

    def test_duplicate_pin_and_path_escape_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicate'):r.pinned_versions(b'fictional_pkg==1\nfictional-pkg==1\n')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            with self.assertRaises(ValueError):r.regular(root,'../outside')

    def test_generated_execution_receipts_are_included_and_missing_ones_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();units=root/'packet/units';units.mkdir(parents=True)
            p=units/('a'*64+'.json');p.write_text('{"fictional":true}')
            self.assertEqual(r.execution_receipt_pins(root,Path('packet'),1),{str(p.relative_to(root)):r.digest(p)})
            with self.assertRaisesRegex(ValueError,'Exact completed'):r.execution_receipt_pins(root,Path('packet'),2)
