"""Offline original-family policy rejects port identities and unsafe bounds."""
import copy
from pathlib import Path
import tempfile
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock,patch
from irisx.arc_nvarc_qwen3_sft import FORMAT,Policy,check_plan,encode_source_pair,file_inventory,verify_model
from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE
from irisx.canonical import digest_value
from irisx.errors import ValidationError


def fixture_plan():
    return {'format':FORMAT,'model_family':'qwen3','run_id':'nvarc-original-qwen3-sft-901','backend':'cpu',
        'data_kind':'synthetic-fixture','source_recipe':copy.deepcopy(RECIPE),'world_size':2,
        'model_inventory':{},'base_material_digest':digest_value({}),'global_batch_size':3,
        'maximum_optimizer_steps':3,'maximum_training_tokens':108,'maximum_input_tokens':114,
        'maximum_sequence_length':14,'maximum_physical_input_tokens':16,
        'packing_execution':'segmented-gemm-whole-sample-packing','packing_capacity':256000,
        'packing_length_multiple':64,'seed':24,'checkpoint_storage':'durable-retained','checkpoint_keep_last':2,
        'checkpoint_steps':[1,2,3],'maximum_outer_forwards':12,'maximum_worker_wall_seconds':180,
        'maximum_paid_usd':0,'maximum_generations':0,'maximum_teacher_calls':0}


class OriginalSFTPolicyTests(unittest.TestCase):
    def test_rank_zero_retention_error_is_broadcast_before_sibling_barrier(self):
        # A real corrupted retention inventory must not strand sibling ranks.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=root/'checkpoint-step-0001-attempt-0001';old.mkdir()
            (old/'manifest.json').write_text('{}')
            retained=old/'retained.bin';retained.write_bytes(b'prior checkpoint must survive')
            parent=ModuleType('torch');dist=ModuleType('torch.distributed');parent.distributed=dist
            calls=[]
            dist.broadcast_object_list=lambda value,src:calls.append(list(value))
            dist.barrier=Mock()
            with patch.dict(sys.modules,{'torch':parent,'torch.distributed':dist}),patch(
                    'irisx.arc_nvarc_fsdp_sft._save_checkpoint',return_value={'path':'checkpoint-step-0002-attempt-0001'}),patch(
                    'irisx.arc_nvarc_fsdp_sft.verify_checkpoint',side_effect=ValidationError('retained manifest invalid')):
                with self.assertRaisesRegex(ValidationError,'retained manifest invalid'):
                    Policy(root).save_checkpoint(None,None,None,root,{'step':2,'identity_digest':'fixture'},0,2,None)
            self.assertEqual('prior checkpoint must survive',retained.read_text())
            self.assertIn('retained manifest invalid',calls[-1][0])
            dist.barrier.assert_not_called()

    def test_family_recipe_durable_storage_and_finite_call_bounds_fail_closed(self):
        plan = fixture_plan();check_plan(plan,2)
        for key,value in [('format','irisx/nvarc-source-sft-v1'),('model_family','qwen3.5'),
                ('run_id','nvarc-overnight-sft-002'),('maximum_input_tokens',107),('maximum_outer_forwards',0),
                ('maximum_optimizer_steps',True),('maximum_worker_wall_seconds',0),
                ('checkpoint_storage','ephemeral-scratch'),('checkpoint_keep_last',0),
                ('checkpoint_steps',[2,3]),('packing_execution','isolated-segments'),('maximum_paid_usd',1)]:
            with self.subTest(key=key),self.assertRaises(ValidationError):
                changed = copy.deepcopy(plan);changed[key]=value;check_plan(changed,2)
        changed = copy.deepcopy(plan);changed['backend']='cuda-l4';changed['world_size']=4
        with self.assertRaises(ValidationError):check_plan(changed,4)

    def test_original_masks_keep_content_eos_and_reject_role_or_non_grid_text(self):
        pair=[{'role':'user','content':'12\n34'},{'role':'assistant','content':'56\n78'}]
        ids,labels=encode_source_pair(pair)
        self.assertEqual([5,6,10,7,8,15],[x for x in labels if x>=0])
        self.assertEqual(15,ids[-1])
        for wrong in ([pair[1],pair[0]],[pair[0],{'role':'assistant','content':'wrong'}]):
            with self.assertRaises(ValidationError):encode_source_pair(wrong)

    def test_exact_model_inventory_and_optional_bound_sidecar_without_ml_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'weight.safetensors').write_bytes(b'fixture bytes only')
            inventory=file_inventory(root)
            plan={'model_inventory':inventory,'base_material_digest':digest_value(inventory)}
            verify_model(root,plan)
            (root/'dataset-metadata.json').write_text('{}')
            with self.assertRaises(ValidationError):verify_model(root,plan)
            plan['model_sidecars']={'dataset-metadata.json':file_inventory(root)['dataset-metadata.json']}
            verify_model(root,plan)
            (root/'dataset-metadata.json').write_text('{"changed":true}')
            with self.assertRaises(ValidationError):verify_model(root,plan)


if __name__=='__main__':unittest.main()
