"""Explicit fictional provider envelopes, selected facts, and capacity checks."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import os
import struct
import sys
import tempfile
import unittest
import zipfile
VALIDATION=Path(__file__).resolve().parents[1]/'validation';ROOT=VALIDATION.parent
sys.path[:0]=[str(VALIDATION),str(VALIDATION.parent/'validation-tests')]
import validate_transfer_outputs as v
from successor_fixture_helpers import make_final_source_collector_fixture,release_path,source_for_release

class ExactReleasedEnvelope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected=os.environ.get('TRANSFER_VALIDATION_RELEASE')
        cls.release=release_path()
        if not (cls.release/'publication-manifest.json').is_file():raise unittest.SkipTest('512MiB successor release not yet assembled')
        try:cls.fixture_source=source_for_release(cls.release)
        except ValueError as exc:
            if str(exc)=='no exact immutable source fixture matches mapping':raise unittest.SkipTest('exact release present but matching immutable source fixture omitted') from exc
            raise
        cls.temp=tempfile.TemporaryDirectory(dir=VALIDATION.parent/'validation-tests')
        cls.args=make_final_source_collector_fixture(Path(cls.temp.name)/'explicit-fiction',synthetic=True,template_release=cls.release,source_root=cls.fixture_source)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_exact_manifest_and_source_fixture(self):
        r=v.validate_outputs(**self.args);self.assertTrue(r['valid']);self.assertTrue(r['synthetic']);self.assertEqual(r['source_archive_cap_bytes'],512*1024**2);self.assertEqual(r['status'],'TRANSFER_FAILED');self.assertFalse(r['goal_met']);self.assertEqual(r['separate_checkpoint_presence'],'UNKNOWN');self.assertFalse(r['whole_provider_inventory_verified']);self.assertEqual(r['manifest_sha256'],v.file_sha(self.release/'publication-manifest.json'))
    def test_exact_final_production_launch_source_approval_subcheck(self):
        m,msha=v.document(self.args['manifest']);f,_=v.document(self.args['finalization']);j,_=v.document(self.args['launch_journal']);l,_=v.document(self.args['launch_receipt'])
        if m.get('release_runtime_finalized') is not True:self.skipTest('preview has no production runtime approval')
        spec,constants=v.validate_launch(m,msha,f,j,l,self.args['finalized_notebook'],self.release.absolute(),allow_synthetic=False)
        self.assertEqual(spec['expected_version'],25);self.assertEqual(constants['EXECUTION_CUTOFF_SECONDS'],42000)
    def test_production_rejects_authored_fixture(self):
        with self.assertRaisesRegex(ValueError,'synthetic'):v.validate_outputs(**{**self.args,'allow_synthetic':False})
    def test_old_numeric_output21_rejected(self):
        r=deepcopy(self.args['retrieval_receipt']);r['numeric_output_version']=21
        with self.assertRaises(ValueError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_inactive24_cannot_be_active25(self):
        r=deepcopy(self.args['retrieval_receipt']);r['before']['version']=r['after']['version']=24
        with self.assertRaises(ValueError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_unrelated_latest26_rejected(self):
        r=deepcopy(self.args['retrieval_receipt']);r['after']['version']=26
        with self.assertRaises(ValueError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_whole_provider_inventory_claim_rejected(self):
        r=deepcopy(self.args['retrieval_receipt']);r['whole_provider_inventory_verified']=True
        with self.assertRaises(ValueError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_fake_checkpoint_absence_rejected(self):
        r=deepcopy(self.args['retrieval_receipt']);r['checkpoint_metadata_only']['presence']='ABSENT'
        with self.assertRaises(ValueError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_selected_header_fact_bad_numeric_version(self):
        r=deepcopy(self.args['retrieval_receipt']);r['provider_files'][0]['numeric_version']=21
        with self.assertRaises(ValueError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_outer_same_origin_clock_reset_rejected(self):
        f=v.json_file(self.args['finalization']);f['outer_deadline_epoch']+=1
        with self.assertRaises(ValueError):v.validate_outputs(**{**self.args,'finalization':f})
    def test_error_status_cannot_be_operational_success(self):
        r=deepcopy(self.args['retrieval_receipt']);r['before']['status']=r['after']['status']='ERROR';out=v.validate_outputs(**{**self.args,'retrieval_receipt':r});self.assertFalse(out['operational_success']);self.assertFalse(out['goal_met'])

class HeaderOnlyCheckpoint(unittest.TestCase):
    def setUp(self):
        self.prefix='synthetic/';self.name=self.prefix+'checkpoints.zip';self.t={'checkpoint_archive':{'bytes':1234,'sha256':'a'*64}}
        self.r={'checkpoint_downloaded':False,'provider_files':[{'path':self.name,'bytes':1234,'numeric_version':25,'size_source':'numeric_response_header_only'}],
            'checkpoint_metadata_only':{'path':self.name,'presence':'HTTP200_CONTENT_LENGTH_VERIFIED','bytes':1234,'http_status':200,'body_consumed_bytes':0,'archive_bytes_verified':False,'declared_sha256_unverified':'a'*64,'scope':'numeric output request; Content-Length and successful response only'}}
        self.d=SimpleNamespace(files={},listed={self.name:1234})
    def check(self,verified=False):return v.validate_checkpoint_observation(self.r,self.t,self.d,self.prefix,bytes_verified=verified)
    def test_header_same_size_is_not_bytes_verified(self):self.assertEqual(self.check(),'HTTP200_CONTENT_LENGTH_VERIFIED')
    def test_header_cannot_promote_archive_hash(self):
        with self.assertRaises(ValueError):self.check(True)
    def test_metadata_claimed_body_verification_rejected(self):
        self.r['checkpoint_metadata_only']['archive_bytes_verified']=True
        with self.assertRaises(ValueError):self.check()
    def test_partial_body_consumed_rejected(self):
        self.r['checkpoint_metadata_only']['body_consumed_bytes']=1
        with self.assertRaises(ValueError):self.check()
    def test_wrong_size_rejected(self):
        self.r['checkpoint_metadata_only']['bytes']=1235
        with self.assertRaises(ValueError):self.check()
    def test_wrong_declared_hash_rejected(self):
        self.r['checkpoint_metadata_only']['declared_sha256_unverified']='b'*64
        with self.assertRaises(ValueError):self.check()
    def test_wrong_version_rejected(self):
        self.r['provider_files'][0]['numeric_version']=22
        with self.assertRaises(ValueError):self.check()
    def test_unknown_cannot_substitute_declared_archive(self):
        self.r['checkpoint_metadata_only'].update(presence='UNKNOWN',bytes=None)
        with self.assertRaises(ValueError):self.check()

class ArchiveCapacity(unittest.TestCase):
    def test_real384mib_export_integrity(self):
        path=ROOT/'author-evidence/archive-capacity-receipt.json'
        if not path.exists():path=ROOT.parent/'portfolio63-transfer-repair-20261012/author-evidence/archive-capacity-receipt.json'
        if not path.exists():self.skipTest('unchanged retained archive-capacity fixture unavailable')
        receipt=v.json_file(path);row=receipt['checks']['384MiB_actual_export']['result'];path=Path(row['path'])
        if not path.exists():
            parts=path.parts;path=ROOT/Path(*parts[parts.index('author-evidence'):])
        if not path.exists():self.skipTest('retained384MiB expanded capacity archive not included in portable subset')
        archive=v.ClosedArchive(path)
        try:self.assertEqual(archive.sha256,row['sha256']);self.assertEqual(len(archive.members),769);self.assertGreater(sum(x.file_size for x in archive.members.values()),256*1024**2)
        finally:archive.close()
    def test_declared_expanded_total_over512_rejected_before_read(self):
        with tempfile.TemporaryDirectory(dir=VALIDATION.parent/'validation-tests') as temp:
            path=Path(temp)/'synthetic-over-cap.zip'
            with zipfile.ZipFile(path,'w') as z:
                for i in range(33):z.writestr('member%d'%i,b'')
            raw=bytearray(path.read_bytes());pos=0
            while True:
                pos=raw.find(b'PK\x01\x02',pos)
                if pos<0:break
                struct.pack_into('<I',raw,pos+24,16*1024**2);pos+=4
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'aggregate'):v.ClosedArchive(path)
    def test_container_size_over544_rejected(self):
        with tempfile.TemporaryDirectory(dir=VALIDATION.parent/'validation-tests') as temp:
            path=Path(temp)/'synthetic-sparse-over-cap.zip'
            with path.open('wb') as f:f.truncate(544*1024**2+1)
            with self.assertRaisesRegex(ValueError,'oversized'):v.ClosedArchive(path)

if __name__=='__main__':unittest.main()
