"""Vendor digest mismatch retains one consumed read and never retries."""
from email.message import Message
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.verify_nvarc_original_runtime_wheels import PACKAGES,verify
from irisx.errors import ValidationError


class ReleaseResponse(io.BytesIO):
    status=200
    def geturl(self):return 'https://pypi.org/pypi/accelerate/1.10.1/json'


class OriginalRuntimeMaterialTests(unittest.TestCase):
    def test_wrong_vendor_digest_retains_read_and_prevents_second_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            for package,version in PACKAGES.items():
                name=package.replace('-','_')+'-'+version+'-py3-none-any.whl'
                metadata=Message();metadata['Name']=package;metadata['Version']=version
                with zipfile.ZipFile(folder/name,'w') as archive:
                    archive.writestr(package.replace('-','_')+'-'+version+'.dist-info/METADATA',metadata.as_bytes())
            first=sorted(folder.glob('*.whl'))[0]
            release={'urls':[{'filename':first.name,'size':first.stat().st_size,
                'digests':{'sha256':'0'*64},'url':'https://files.pythonhosted.org/packages/fixture.whl'}]}
            with patch('tools.verify_nvarc_original_runtime_wheels.urlopen',
                    return_value=ReleaseResponse(json.dumps(release).encode())) as request:
                with self.assertRaises(ValidationError):verify(folder)
                self.assertEqual(request.call_count,1)
                frozen=(folder/'acquisition.json').read_bytes()
                ledger=json.loads(frozen)
                self.assertEqual(ledger['release_reads_reserved'],1)
                self.assertEqual(ledger['state'],'verification-failed-retained')
                with self.assertRaises(ValidationError):verify(folder)
                self.assertEqual(request.call_count,1)
                self.assertEqual(frozen,(folder/'acquisition.json').read_bytes())
                self.assertFalse((folder/'manifest.json').exists())


if __name__=='__main__':unittest.main()
