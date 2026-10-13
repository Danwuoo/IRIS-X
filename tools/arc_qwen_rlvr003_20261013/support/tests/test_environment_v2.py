"""CPU-only boundary tests. Mocked observations cannot admit production."""
from pathlib import Path
import copy,importlib.util,json,sys,tempfile,time,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]/'portfolio63-rl-batched-20261012'
sys.path.insert(0,str(ROOT))
from owned_runtime import environment_v2 as e


class EnvironmentTests(unittest.TestCase):
    def test_exact_header_abi(self):
        e._compare_header_and_versions('size_t CUDNNWINAPI cudnnGetVersion(void);',torch_version=91002,library_version=91002)
    def test_reject_version_mismatch(self):
        with self.assertRaisesRegex(ValueError,'differs'):
            e._compare_header_and_versions('size_t cudnnGetVersion(void);',torch_version=91001,library_version=91002)
    def test_reject_no_observation(self):
        for value in (None,True,0,-1,'91002'):
            with self.assertRaises(ValueError):e._compare_header_and_versions('size_t cudnnGetVersion(void);',torch_version=value,library_version=91002)
    def test_reject_wrong_header_abi(self):
        for text in ('int cudnnGetVersion(void);','size_t cudnnGetVersion(int x);','missing'):
            with self.assertRaises(ValueError):e._compare_header_and_versions(text,torch_version=91002,library_version=91002)
    def test_map_exact_root(self):
        raw='1000-2000 r-xp 0000 00:00 1 /x/site-packages/nvidia/cudnn/lib/libcudnn.so.9\n'
        self.assertEqual(e._mapped_cudnn(raw,'/x/site-packages/nvidia/cudnn/lib'),[Path('/x/site-packages/nvidia/cudnn/lib/libcudnn.so.9')])
    def test_reject_foreign_deleted_or_escaped_backend(self):
        for path in ('/bad/libcudnn.so.9','/x/libcudnn.so.9 (deleted)','/x/libcudnn\\040.so.9'):
            with self.assertRaises(ValueError):e._mapped_cudnn('1000-2000 r-xp 0000 00:00 1 '+path,'/x')
    def test_reject_duplicate_backend_root(self):
        with self.assertRaises(ValueError):e._mapped_cudnn('1-2 r-xp 0 0 1 /x/libcudnn.so.9\n2-3 r-xp 0 0 2 /other/libcudnn_ops.so.9','/x')
    def test_stream_limits_and_deadline(self):
        import io
        with self.assertRaises(ValueError):e._stream_hash(io.BytesIO(b'abc'),deadline=time.monotonic()+2,maximum=2)
        with self.assertRaises(ValueError):e._stream_hash(io.BytesIO(b''),deadline=time.monotonic()-1,maximum=2)
    def test_nonfinite_or_bool_deadline_rejected(self):
        for value in (True,False,float('inf'),float('-inf'),float('nan')):
            with self.assertRaises(ValueError):e._check_time(value)
    def test_file_link_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);(p/'a').write_bytes(b'abc');(p/'b').symlink_to(p/'a')
            with self.assertRaises(ValueError):e._regular(p/'b')
    def fields(self):
        expected=json.loads((Path(__file__).resolve().parents[1]/'environment-candidate/REVIEWED-ENVIRONMENT-CANDIDATE.json').read_text())
        expected['format']=e.FORMAT;expected['cudnn_policy']=copy.deepcopy(e.POLICY)
        actual={**expected['actual_environment'],'cudnn_version':91002}
        return expected,actual
    def test_exact_prior_plus_current_observation(self):
        expected,actual=self.fields()
        with patch.object(e,'observe_cudnn',return_value={'torch_cudnn_version':91002}):
            self.assertEqual(e.verify_environment(expected,actual,model_config=expected['model_config'],native_identity=expected['native_identity_projection'],deadline=time.monotonic()+2),{'torch_cudnn_version':91002})
    def test_reject_any_prior_field_drift(self):
        for key in ('python_version','torch_version','cuda_version','device_count','devices'):
            expected,actual=self.fields();actual[key]='changed'
            with patch.object(e,'observe_cudnn') as observation,self.assertRaisesRegex(ValueError,'v25'):
                e.verify_environment(expected,actual,model_config=expected['model_config'],native_identity=expected['native_identity_projection'],deadline=time.monotonic()+2)
            observation.assert_not_called()
    def test_no_inferred_prior_integer(self):
        expected,actual=self.fields();expected['actual_environment']['cudnn_version']=91002
        with self.assertRaises(ValueError):e.verify_environment(expected,actual,model_config=expected['model_config'],native_identity=expected['native_identity_projection'],deadline=time.monotonic()+2)
    def test_reject_observation_record_drift(self):
        expected,actual=self.fields()
        with patch.object(e,'observe_cudnn',return_value={'torch_cudnn_version':91001}),self.assertRaisesRegex(ValueError,'recorded'):
            e.verify_environment(expected,actual,model_config=expected['model_config'],native_identity=expected['native_identity_projection'],deadline=time.monotonic()+2)
    def test_reject_policy_substitution(self):
        expected,actual=self.fields();expected['cudnn_policy']['wheel_sha256']='0'*64
        with self.assertRaises(ValueError):e.verify_environment(expected,actual,model_config=expected['model_config'],native_identity=expected['native_identity_projection'],deadline=time.monotonic()+2)

if __name__=='__main__':unittest.main()
