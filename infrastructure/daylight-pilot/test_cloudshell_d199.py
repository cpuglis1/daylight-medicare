"""Provider-free verification of required encryption on every deployment upload."""
import base64
import contextlib
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import cloudshell_d199 as driver


class UploadTests(unittest.TestCase):
    def test_all_uploads_require_exact_kms_key_and_bucket_key_then_verify(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            names=('code.zip','deploy_hosted_d199.py','d199-plan.json','data.tar.gz')
            hashes={}
            for name in names:
                data=('fictional '+name).encode();(root/name).write_bytes(data)
                hashes[name]=hashlib.sha256(data).hexdigest()
            value={'release':'a'*64,'data_archive':'data.tar.gz','data_archive_sha256':hashes['data.tar.gz']}
            files={name:hashes[name] for name in names[:-1]}
            metadata={};s3=Mock()
            def put(**kwargs):
                data=kwargs['Body'].read()
                self.assertEqual(kwargs['ServerSideEncryption'],'aws:kms')
                self.assertEqual(kwargs['SSEKMSKeyId'],driver.KMS_KEY)
                self.assertIs(kwargs['BucketKeyEnabled'],True)
                self.assertEqual(kwargs['ExpectedBucketOwner'],driver.ACCOUNT)
                self.assertEqual(kwargs['ChecksumSHA256'],base64.b64encode(hashlib.sha256(data).digest()).decode())
                metadata[kwargs['Key']]={name:kwargs[name] for name in
                    ('ServerSideEncryption','SSEKMSKeyId','BucketKeyEnabled','ContentLength','ChecksumSHA256')}
            s3.put_object.side_effect=put
            s3.head_object.side_effect=lambda **kwargs:metadata[kwargs['Key']]
            sts=Mock();sts.get_caller_identity.return_value={'Account':driver.ACCOUNT}
            session=Mock();session.client.side_effect=lambda name:{'sts':sts,'s3':s3,'ssm':Mock()}[name]
            with patch.object(driver,'HERE',root),patch.object(driver,'plan',return_value=(value,files)), \
                    patch.object(driver.boto3,'Session',return_value=session),patch.object(driver.sys,'argv',['driver','upload']), \
                    contextlib.redirect_stdout(io.StringIO()):
                driver.main()
            self.assertEqual(s3.put_object.call_count,4)
            self.assertEqual(s3.head_object.call_count,4)
            s3.upload_file.assert_not_called()
            for call in s3.head_object.call_args_list:
                self.assertEqual(call.kwargs['ExpectedBucketOwner'],driver.ACCOUNT)
                self.assertEqual(call.kwargs['ChecksumMode'],'ENABLED')

    def test_wrong_remote_encryption_key_or_bucket_key_is_refused(self):
        good={'ServerSideEncryption':'aws:kms','SSEKMSKeyId':driver.KMS_KEY,'BucketKeyEnabled':True}
        driver.verify_encryption(good)
        for field,value in [('ServerSideEncryption','AES256'),('SSEKMSKeyId','wrong-key'),('BucketKeyEnabled',False)]:
            with self.subTest(field=field),self.assertRaises(SystemExit):
                driver.verify_encryption({**good,field:value})

    def test_remote_checksum_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'artifact';path.write_bytes(b'fictional')
            s3=Mock();s3.head_object.return_value={'ServerSideEncryption':'aws:kms','SSEKMSKeyId':driver.KMS_KEY,
                'BucketKeyEnabled':True,'ContentLength':9,'ChecksumSHA256':'wrong'}
            with self.assertRaises(SystemExit):
                driver.upload_encrypted(s3,path,'reviewed/key',driver.sha(path))


if __name__=='__main__':unittest.main()
