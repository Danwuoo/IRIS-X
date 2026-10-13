"""Authored metadata-only adversaries for PUBLIC production-checkpoint boundary.
No pretrained model, provider, real PUBLIC challenge or gold file is accessed.
Synthetic metadata below cannot establish real model admission.
"""
from copy import deepcopy
import hashlib,json,os
from pathlib import Path
import sys
import unittest
HERE=Path(__file__).resolve().parent
SOURCE=Path(os.environ.get('REVIEW_SOURCE',str(HERE.parent/'worktree'))).resolve()
sys.path[:0]=[str(SOURCE),str(SOURCE/'src')]
from tools.arc_qwen_transfer_20261012 import public_evaluation as pe, checkpoint_policy as policy
from tools.arc_qwen_transfer_20261012.protocol import digest


def fixture(mutate=lambda c:None):
    files={}
    def ref(name,value):
        raw=json.dumps(value,sort_keys=True).encode();files[name]=raw
        return {'path':name,'sha256':hashlib.sha256(raw).hexdigest()}
    identity={'model_key':'qwen3-14b','model_id':'Qwen/Qwen3-14B','revision':'40c069824f4251a91eefaf281ebe4c544efd3e18',
      'profile_id':'qwen3-14b-native-bf16-r8-c4096-transfer-v1','execution_mode':'native-qwen3-pretrained-c4096-transfer',
      'pretrained_weights_loaded':True,'random_test_weights':False,'full_vocabulary_rows':151936,'base_precision':'bfloat16',
      'all_eight_weight_sha256_verified':True,'verified_tensor_count':443,'verified_tensor_elements':14768307200,
      'context_limit':4096,'prompt_cap':3072,'output_cap':1024,'environment':{'explicit_metadata_test_only':True}}
    checkpoint={'format':'irisx/qwen-branch-safe-checkpoint-v1','adapter_sha256':'a'*64,'update':64,
      'binding':{'branch_id':'global_grid','config':{'objective_cycle':['grid'],'tiny_cpu':False},
      'precision':'bf16-base-fp32-lora','rank':8,'alpha':16,'source':{'authored-test.py':'b'*64},
      'checkpoint_schedule':policy.contract(policy.GLOBAL,'global_grid')}}
    mutate(checkpoint)
    cr=ref('checkpoint.json',checkpoint)
    method={'candidate_id':'sft64','role':'global_sft','checkpoint_manifest_sha256':cr['sha256'],'adapter_sha256':'a'*64}
    rows=[{'candidate_id':'sft64','update':64,'exact':2,'shape':2,'valid':2,'denominator':16},
          {'candidate_id':'base','update':0,'exact':0,'shape':0,'valid':0,'denominator':16},
          {'candidate_id':'sft256','update':256,'exact':0,'shape':0,'valid':0,'denominator':16}]
    main={'candidate_id':'sft64','selection_uses_holdout_targets':False,'rankings':rows,
      'checkpoint':{'manifest_sha256':cr['sha256'],'adapter_sha256':'a'*64}}
    main['selection_sha256']=digest(main)
    selection={'method':method,'query_targets_used':False,'selected_before_public_queries':True,
      'selection_sha256':main['selection_sha256'],'main_selection':ref('main.json',main)}
    evidence={'checkpoint_manifest':cr,'frozen_selection':ref('selection.json',selection),
      'model_admission':ref('admission.json',{'identity':identity,'hardware':{'visible_device_count':1,'bf16_supported':True,'fp8_admitted':False,'four_l4_tp_admitted':False}}),
      'calibration':ref('calibration.json',{'status':'complete','completed_lengths':[128,512,2048,4096],
      'full_context_measured':True,'cpu_fixture_only':False,'full_state_restoration_verified':True})}
    return {'runtime_evidence':evidence,'model_identity':identity,'production_model':True,'_source_identity':{'authored-test.py':'b'*64}}, {'method':method},files

class PublicBoundary(unittest.TestCase):
    def check(self,mutate=lambda c:None):
        result,artifact,files=fixture(mutate)
        return pe._runtime(result,artifact,files.__getitem__,tiny=False)
    def test_nominal_production_schedule_metadata(self):self.assertTrue(self.check())
    def test_omitted_schedule(self):
        with self.assertRaises(ValueError):self.check(lambda c:c['binding'].pop('checkpoint_schedule'))
    def test_fixture_schedule(self):
        with self.assertRaises(ValueError):self.check(lambda c:c['binding'].update(checkpoint_schedule=policy.contract(policy.FIXTURE,'global_grid')))
    def test_ttt_schedule(self):
        with self.assertRaises(ValueError):self.check(lambda c:c['binding'].update(checkpoint_schedule=policy.contract(policy.TTT,'representative_ttt')))
    def test_wrong_bound_branch(self):
        with self.assertRaises(ValueError):self.check(lambda c:c['binding'].update(branch_id='representative_ttt'))
    def test_nonproduction_config(self):
        for tiny in (True,None,0):
            with self.subTest(tiny=tiny),self.assertRaises(ValueError):self.check(lambda c:c['binding']['config'].update(tiny_cpu=tiny))
    def test_bad_update(self):
        for update in (None,True,16,65,257):
            with self.subTest(update=update),self.assertRaises(ValueError):self.check(lambda c:c.update(update=update))
    def test_self_consistent_wrong_source_contract(self):
        with self.assertRaises(ValueError):self.check(lambda c:c['binding']['checkpoint_schedule'].update(source_sha256={}))

if __name__=='__main__':unittest.main(verbosity=2)
