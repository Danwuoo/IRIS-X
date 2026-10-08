import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import publish_arc_next_quicksave as p
from tools import stage_arc_next_notebook as s
HAS_SDK=importlib.util.find_spec('kagglesdk') is not None
class QuickSaveTests(unittest.TestCase):
    def setUp(self):
        self.meta=dict(id=p.REF,title=p.SLUG,code_file='notebook.ipynb',language='python',kernel_type='notebook',
            is_private=True,enable_gpu=False,enable_internet=False,dataset_sources=[],competition_sources=[],kernel_sources=[],model_sources=[])
        self.nb=s.notebook({'source_digest':'a'*64,'source_commit':'b'*40},{'tools/__init__.py':b''})
        self.body=p.canonical(self.nb)
        self.binding=dict(package_manifest_sha256='a'*64,plan_sha256='b'*64,metadata_sha256='c'*64,
                          notebook_sha256=p.sha(self.body),source_digest=p.execution_source_digest(self.nb),offline_package_verified=True)
        self.patch=patch.object(p,'package_info',side_effect=lambda *_:({},copy.deepcopy(self.meta),self.body,self.binding));self.patch.start()
    def tearDown(self):self.patch.stop()
    def source(self):
        return {'metadata':dict(id=400000099,ref=p.REF,title=p.SLUG,currentVersionNumber=1,isPrivate=True,
          enableInternet=False,enableGpu=False,enableTpu=False,language='python',kernelType='notebook',machineShape='None'),
          'blob':{'source':self.body.decode()}}
    def test_request_scope(self):
        _,wire,_=p.request_fields('fake')
        self.assertEqual(wire['kernelExecutionType'],'QUICK_SAVE')
        self.assertFalse(wire['enableGpu']);self.assertFalse(wire['enableInternet']);self.assertTrue(wire['isPrivate'])
        self.assertNotIn('id',wire);self.assertNotIn('machineShape',wire);self.assertNotIn('sessionTimeoutSeconds',wire)
    def test_public_gpu_internet_or_mount_rejected(self):
        for key,value in [('is_private',False),('enable_gpu',True),('enable_internet',True),('competition_sources',['wrong'])]:
            original=self.meta[key];self.meta[key]=value
            with self.assertRaises(RuntimeError):p.request_fields('fake')
            self.meta[key]=original
    def test_exact_source_flags_and_content(self):
        result=p.verify_source_value(self.source(),'fake',400000099,self.binding['source_digest'])
        self.assertTrue(result['owner_start_default_false_verified']);self.assertFalse(result['provider_save_type_attested'])
        raw=self.source();raw['metadata']['enableGpu']=True
        with self.assertRaises(RuntimeError):p.verify_source_value(raw,'fake',400000099,self.binding['source_digest'])
        raw=self.source();nb=copy.deepcopy(self.nb);nb['cells'][1]['source']=[x.replace('RUN_CALIBRATION = False','RUN_CALIBRATION = True') for x in nb['cells'][1]['source']];raw['blob']['source']=p.canonical(nb).decode()
        with self.assertRaises(RuntimeError):p.verify_source_value(raw,'fake',400000099,p.execution_source_digest(nb))
    @unittest.skipUnless(HAS_SDK,'official SDK available in dedicated CLI environment')
    def test_genuine_sdk_wire_no_network(self):
        req,wire,_=p.request('fake');body=p.capture_prepared(req,wire)
        self.assertEqual(p.parse(body),wire)
    @unittest.skipUnless(HAS_SDK,'official SDK available in dedicated CLI environment')
    def test_prepare_binds_exact_body_and_no_duplicate_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with patch.object(p,'ROOT',root/'repo'):
                review=p.prepare('fake',root/'journal',newness_proof='complete-own-list')
                self.assertEqual(review['execution_type'],'QUICK_SAVE')
                self.assertEqual(p.read(root/'journal/ledger.json')['state'],'prepared-not-sent')
                p.write(p.claim_path(),{'reserved':True})
                with self.assertRaises(RuntimeError):p.prepare('fake',root/'another',newness_proof='complete-own-list')
if __name__=='__main__':unittest.main()
