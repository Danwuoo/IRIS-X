"""Synthetic provider/outer envelopes around unchanged actual tiny output bytes."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'validation')]
import validate_transfer_outputs as v
from fixture_helpers import make_synthetic_collector_fixture

class CollectorEnvelopes(unittest.TestCase):
    synthetic=True
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.args=make_synthetic_collector_fixture(Path(cls.temp.name)/'synthetic',synthetic=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_synthetic_full_positive(self):
        r=v.validate_outputs(**self.args);self.assertTrue(r['provider_envelope_verified']);self.assertTrue(r['synthetic']);self.assertFalse(r['operational_success']);self.assertFalse(r['goal_met']);self.assertEqual(r['status'],'TRANSFER_COMPLETE')
    def test_production_api_rejects_synthetic_envelope(self):
        with self.assertRaisesRegex(v.ValidationError,'synthetic envelope'):v.validate_outputs(**{**self.args,'allow_synthetic':False})
    def test_numeric_version_drift(self):
        r=deepcopy(self.args['retrieval_receipt']);r['after']['version']=22
        with self.assertRaises(v.ValidationError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_source_bracket_drift(self):
        r=deepcopy(self.args['retrieval_receipt']);r['after']['source_sha256']='1'*64
        with self.assertRaises(v.ValidationError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_output_archive_hash_tamper(self):
        r=deepcopy(self.args['retrieval_receipt']);next(x for x in r['files'] if x['provider_path'].endswith('evidence.zip'))['sha256']='1'*64
        with self.assertRaises(v.ValidationError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_missing_outer_closure(self):
        r=deepcopy(self.args['retrieval_receipt']);r['files']=[x for x in r['files'] if not x['provider_path'].endswith('launcher-closure.json')]
        with self.assertRaises(v.ValidationError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_checkpoint_omitted_presence(self):
        r=deepcopy(self.args['retrieval_receipt']);r['provider_files']=[x for x in r['provider_files'] if not x['path'].endswith('checkpoints.zip')]
        with self.assertRaises(v.ValidationError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_duplicate_download(self):
        r=deepcopy(self.args['retrieval_receipt']);r['files'].append(r['files'][0])
        with self.assertRaises(v.ValidationError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_provider_error_retains_measurements(self):
        r=deepcopy(self.args['retrieval_receipt']);r['before']['status']=r['after']['status']='ERROR';out=v.validate_outputs(**{**self.args,'retrieval_receipt':r})
        self.assertEqual(out['provider_status'],'ERROR');self.assertFalse(out['operational_success']);self.assertFalse(out['goal_met']);self.assertTrue(out['valid'])
    def test_provider_cancel_retains_measurements(self):
        r=deepcopy(self.args['retrieval_receipt']);r['before']['status']=r['after']['status']='CANCEL_ACKNOWLEDGED';out=v.validate_outputs(**{**self.args,'retrieval_receipt':r})
        self.assertEqual(out['provider_status'],'CANCEL_ACKNOWLEDGED');self.assertFalse(out['operational_success']);self.assertFalse(out['goal_met'])
    def test_running_provider_is_not_terminal(self):
        r=deepcopy(self.args['retrieval_receipt']);r['before']['status']=r['after']['status']='RUNNING'
        with self.assertRaises(v.ValidationError):v.validate_outputs(**{**self.args,'retrieval_receipt':r})
    def test_mutated_finalization_hash(self):
        f=v.json_file(self.args['finalization']);f['predispatch_epoch']+=1
        with self.assertRaises(v.ValidationError):v.validate_outputs(**{**self.args,'finalization':f})

if __name__=='__main__':unittest.main()
