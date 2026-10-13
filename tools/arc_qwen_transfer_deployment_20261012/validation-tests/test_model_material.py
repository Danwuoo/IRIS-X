"""Explicit synthetic metadata unit fixtures; no model/GPU execution is claimed."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'validation'))
import validate_transfer_outputs as v

class MaterialMetadata(unittest.TestCase):
    synthetic=True
    @classmethod
    def setUpClass(cls):
        cls.source=v.SourceSnapshot(ROOT/'worktree',v.source_identity(ROOT/'worktree'))
        c=v.strict_json(cls.source.read('materials/qwen14b/material-contract.json'));h=v.strict_json(cls.source.read('materials/qwen14b/hardware-contract.json'));e=v.strict_json(cls.source.read('materials/qwen14b/environment-lock.json'))
        cls.identity={'format':'irisx/qwen14b-native-interface-v1','model_key':'qwen3-14b','profile_id':v.PROFILE_ID,'material_addendum_sha256':v.ADDENDUM_SHA256,'base_precision':'bfloat16','full_vocabulary_rows':151936,'context_limit':4096,'prompt_cap':3072,'output_cap':1024,'random_test_weights':False,'pretrained_weights_loaded':True,'production_admitted':False,'execution_mode':'native-qwen3-pretrained-c4096-transfer','model_id':'Qwen/Qwen3-14B','revision':v.REVISION,'verified_tensor_count':443,'verified_tensor_elements':14768307200,'all_eight_weight_sha256_verified':True,'separate_weights_and_hf_overlay':True,'provider_snapshot_identical_to_hf':False,'verified_weight_shards':{n:{'bytes':r['size_bytes'],'sha256':r['sha256']} for n,r in c['provider_files'].items() if r['role']=='base-weight'},'verified_overlay_files':{n:{'bytes':r['size_bytes'],'sha256':r['sha256']} for n,r in c['overlay_files'].items()},'provider_weight_index_sha256':c['provider_files']['model.safetensors.index.json']['sha256'],'overlay_template_sha256':c['template_sha256'],'overlay_vocabulary_sha256':c['vocabulary_sha256'],'model_manifest_sha256':v.BASE_CONTRACT_SHA256,'material_contract_sha256':v.BASE_CONTRACT_SHA256,'predecessor_material_contract_sha256':v.BASE_CONTRACT_SHA256,'hardware_profile':h['hardware'],'environment':{'environment_lock_sha256':c['environment']['sha256'],'actual_versions':e['versions'],'python':e['python'],'complete_transitive_lock_verified':True,'wheel_root_separate':True,'distribution_origins':{n:'/kaggle/working/SYNTHETIC_METADATA_FIXTURE/site-packages' for n in e['versions']}}}
        cls.hardware={**h['hardware'],'visible_device_count':1,'bf16_supported':True,'torch_cuda':h['torch_cuda'],'driver_version':h['driver_version'],'cache_atol':0.01,'cache_rtol':0.01,'fp8_admitted':False,'four_l4_tp_admitted':False,'successor_free_bytes_before_load':70000000000,'load_peak_allocated_bytes':30000000000,'estimate':{'base_weights_bytes':29536614400,'kv_bytes':671088640,'recurrent_bytes':0,'convolution_bytes':0,'adapter_parameter_elements':32112640,'adapter_training_bytes':513802240,'full_logits_loss_bytes':7467958272,'activation_allowance_bytes':13421772800,'allocator_workspace_reserve_bytes':8589934592,'estimated_required_bytes':60201170944,'measured':False,'memory_fit_guaranteed':False}}
    @classmethod
    def tearDownClass(cls):cls.source.close()
    def reject(self,edit_identity=lambda x:None,edit_hardware=lambda x:None):
        identity=deepcopy(self.identity);hardware=deepcopy(self.hardware);edit_identity(identity);edit_hardware(hardware)
        with self.assertRaises(v.ValidationError):v.validate_model_identity(identity,False,source=self.source,hardware=hardware)
    def test_exact_metadata_structure_only(self):v.validate_model_identity(self.identity,False,source=self.source,hardware=self.hardware)
    def test_changed_eighth_shard(self):self.reject(lambda x:x['verified_weight_shards']['model-00008-of-00008.safetensors'].update(sha256='0'*64))
    def test_wrong_shard_name_same_count(self):self.reject(lambda x:x['verified_weight_shards'].__setitem__('fake.safetensors',x['verified_weight_shards'].pop('model-00008-of-00008.safetensors')))
    def test_wrong_shard_bytes(self):self.reject(lambda x:x['verified_weight_shards']['model-00001-of-00008.safetensors'].update(bytes=1))
    def test_wrong_overlay(self):self.reject(lambda x:x['verified_overlay_files']['tokenizer.json'].update(sha256='0'*64))
    def test_wrong_actual_environment(self):self.reject(lambda x:x['environment']['actual_versions'].update(torch='0.0'))
    def test_wrong_actual_gpu(self):self.reject(edit_hardware=lambda x:x.update(name='Wrong GPU'))
    def test_wrong_driver(self):self.reject(edit_hardware=lambda x:x.update(driver_version='0'))
    def test_insufficient_memory(self):self.reject(edit_hardware=lambda x:x.update(successor_free_bytes_before_load=60201170944))
    def test_wrong_sequence_estimate(self):self.reject(edit_hardware=lambda x:x['estimate'].update(kv_bytes=335544320))

if __name__=='__main__':unittest.main()
