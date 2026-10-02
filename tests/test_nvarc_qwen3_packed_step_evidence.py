"""Rehashed full-gradient receipts cannot replace source, causal or shard gates."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE
from irisx.arc_nvarc_packing import pack_sequences
from irisx.arc_nvarc_qwen3_packed_step import SEGMENTED_FORMAT,BASE,PREFIX_SHA,schedule,call_schedule
from irisx.arc_nvarc_source_recipe import source_sft_lr
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools.verify_nvarc_qwen3_segmented import linear_names
from tools.verify_nvarc_qwen3_packed_step import verify


class FullGradientEvidenceTests(unittest.TestCase):
    def fixture(self,root,fault=None):
        rows=[{'input_ids':[14,15],'labels':[-100,15],'shuffle_position':i} for i in range(256)]
        placement=schedule(rows);run='nvarc-original-qwen3-packed-step-999'
        policy='per-sample unchanged GEMM through checkpoint backward'
        plan={'format':SEGMENTED_FORMAT,'run_id':run,'owner_decision':'Decision 0054','world_size':4,
            'source_recipe':RECIPE,'data_digest':digest_value(rows),'source_prefix_sha256':PREFIX_SHA,
            'model_material_digest':BASE,'maximum_optimizer_steps':1,'maximum_paid_usd':0,
            'maximum_generations':0,'maximum_teacher_calls':0,'retain_export':False,
            'maximum_physical_input_tokens':32768,'packing_capacity':256000,'packing_length_multiple':64,
            'maximum_notebook_wall_seconds':1500,'maximum_worker_wall_seconds':1260,'scheduled_input_tokens':512,
            'scheduled_supervised_tokens':256,'maximum_input_tokens':512,'maximum_outer_forwards':4,
            'physical_schedule':placement,'packed_linear_policy':policy,
            'cuda_differential_prerequisite':{'segmented_linear_observed':True}}
        package=root/'package';package.mkdir()
        atomic(package/'plan.json',plan);atomic(package/'samples.json',rows)
        atomic(package/'stage-summary.json',{'payload_sha256':{}})
        observations=[];values={'plan.json':plan,'payload-bindings.json':{},
            'hardware.json':{'torch':'2.10.0+cu128','inventory':[{'uuid':str(i),'name':'NVIDIA L4','bf16':True} for i in range(4)]},
            'material-verification.json':{'all_files_verified':True,'material_digest':BASE}}
        names=linear_names(36)
        for rank in range(4):
            p=placement['ranks'][rank];offsets=call_schedule(rows,rank)[0]['cu_seqlens']
            linear={'offsets':offsets,'module_names':names,'linear_calls_by_name':{n:1 for n in names},
                'maximum_invocations_per_module':2,'segment_gemm_calls':253*64,'weight_or_dtype_casts':0,
                'weights_modified':False,'weight_dtypes':{n:'torch.float32' for n in names}}
            r={'rank':rank,'world_size':4,'global_sequence_count':256,'packing_layout_digests':p['logical_digests'],
                'physical_packing_layout_digests':p['physical_digests'],'maximum_packed_input_tokens':32768,
                'real_forward_calls':1,'dummy_forward_calls':0,'collective_slots':1,'global_input_tokens':512,
                'global_supervised_tokens':256,'missing_owned_gradient_shards':[],'owned_parameter_shards':3,
                'accumulated_parameter_shards':3,'finite_nonzero_shards':3,'cpu_accumulation_bytes':12,
                'packing_execution':'torch-varlen-flash','fused_packing_verified':True,'global_token_mean_loss':1.0,
                'gradient_norm_before_clip':.5,'learning_rate':source_sft_lr(RECIPE,0),'synchronized_step_wall_seconds':5.0,
                'state_residency':{key:{'cpu/torch.float32':12} for key in ('parameter_bytes','gradient_bytes','optimizer_bytes')},
                'hardware':{'device_uuid':str(rank)},'checkpointed_layers':36,'packed_linear_policy':policy,
                'segmented_linear_policies':[linear],'segment_gemm_invocations_including_checkpoint':253*64}
            observations.append(r)
            values[f'worker/rank-{rank}-step.json']=r
            values[f'worker/rank-{rank}-forward-ledger.json']=[{**event,'completed':True} for event in call_schedule(rows,rank)]
            values[f'worker/rank-{rank}-reservation.json']={'run_id':run,'plan_digest':digest_value(plan),
                'optimizer_steps_reserved':1,'outer_forwards_reserved':1,'input_tokens_reserved':128,
                'dummy_input_tokens_reserved':0,'generation_calls':0,'teacher_calls':0,'maximum_paid_usd':0}
        worker={'run_id':run,'plan_digest':digest_value(plan),'outcome':'complete','model_material_digest':BASE,
            'optimizer_steps':1,'input_tokens':512,'supervised_tokens':256,'outer_forwards':4,'generation_calls':0,
            'teacher_calls':0,'checkpoint_exported':False,'optimizer_checkpoint_exported':False,'full_sft_completed':False,
            'historical_nemo_unsloth_parity':False,'contains_evaluator_truth':False,'rank_observations':observations,
            'weight_fingerprint_before':[1.0,2.0],'weight_fingerprint_after':[1.01,2.01],'step_wall_seconds':5.0,'timing_repetitions':1}
        if fault=='wrong-causal':values['worker/rank-0-forward-ledger.json'][0]['cu_seqlens']=[0,128]
        elif fault=='wrong-input':values['worker/rank-0-forward-ledger.json'][0]['input_ids_digest']='sha256:wrong'
        elif fault=='incomplete':values['worker/rank-0-forward-ledger.json'][0]['completed']=False
        elif fault=='bool-step':worker['optimizer_steps']=True
        elif fault=='bool-shard':observations[0]['owned_parameter_shards']=True
        elif fault=='wrong-lr':observations[0]['learning_rate']=.1
        elif fault=='missing-scope':observations[0]['segmented_linear_policies']=[]
        elif fault=='wrong-linear-offset':observations[0]['segmented_linear_policies'][0]['offsets']=[0,128]
        elif fault=='wrong-gemms':observations[0]['segmented_linear_policies'][0]['segment_gemm_calls']=1
        elif fault=='gradient-bytes':observations[0]['cpu_accumulation_bytes']=16
        elif fault=='false-sft':worker['full_sft_completed']=True
        values['worker/worker-result.json']=worker;values['terminal.json']={**worker,'wall_seconds':50.0}
        raw={name:canonical_bytes(value) for name,value in values.items()}
        index={'run_id':run,'plan_digest':digest_value(plan),'members':[{'path':name,'bytes':len(body),
            'sha256':hashlib.sha256(body).hexdigest()} for name,body in raw.items()]}
        archive=root/'result.zip'
        with zipfile.ZipFile(archive,'x') as stream:
            for name,body in raw.items():stream.writestr(name,body)
            stream.writestr('manifest.json',canonical_bytes(index))
        return archive,package

    def read_fixture(self,*args):
        # These are protocol fixtures, not approved source data or GPU runs.
        with patch('tools.stage_nvarc_qwen3_packed_step.preflight',return_value={'offline_package_verified':True}):return verify(*args)

    def test_complete_protocol_recounts_all_four_causal_and_gradient_scopes(self):
        with tempfile.TemporaryDirectory() as root:result=self.read_fixture(*self.fixture(Path(root)))
        self.assertTrue(result['actual_original_family_full_gradient_step_observed'])
        self.assertEqual(len(result['actual_rank_forward_prefixes']),4)
        self.assertFalse(result['full_sft_completed'])

    def test_rehashed_cost_causal_precision_shard_and_scope_faults_fail(self):
        for fault in ('wrong-causal','wrong-input','incomplete','bool-step','bool-shard','wrong-lr',
                'missing-scope','wrong-linear-offset','wrong-gemms','gradient-bytes','false-sft'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValidationError):self.read_fixture(*self.fixture(Path(root),fault))


if __name__=='__main__':unittest.main()
