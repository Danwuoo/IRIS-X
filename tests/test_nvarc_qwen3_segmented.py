"""Independent vectors and work accounting remain authoritative after rehashing."""
from array import array
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_qwen3_segmented_probe import FORMAT, schedule, SegmentedBudget
from irisx.arc_nvarc_qwen3_packing_diagnostic import TINY, ordered_rows
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools import verify_nvarc_qwen3_segmented as reader


class SegmentedEvidenceTests(unittest.TestCase):
    def rows(self):
        return [{'input_ids':[14,11,10,i,15,14,12,10,2,15],
            'labels':[-100]*8+[2,15],'parent_ids':['toy-'+str(i)]} for i in range(8)]

    def fixture(self, root, fault=None):
        rows=self.rows(); run='nvarc-original-qwen3-probe-999'
        plan={'format':FORMAT,'run_id':run,'maximum_input_tokens':284,
            'model_material_digest':'toy-material','maximum_segment_gemm_calls':4078}
        package=root/'package'; package.mkdir()
        atomic(package/'plan.json',plan); atomic(package/'samples.json',rows)
        atomic(package/'stage-summary.json',{'payload_sha256':{}})
        worker={'format':FORMAT,'run_id':run,'plan_digest':digest_value(plan),'outcome':'complete',
            'actual_outer_forwards':13,'actual_input_tokens':284,'actual_backwards':2,
            'tiny_gradients_passed':True,'tiny_logits_passed':True,'whole_model_fixed_numerical_gate_passed':True,
            'later_samples_bitwise_isolated':True,'native_varlen_gpu_differential_observed':True,
            'decoder_layers_executed':36,'weights_modified':False,'stored_and_compute_dtype':'bfloat16',
            'optimizer_steps':0,'generation_calls':0,'teacher_calls':0,'full_sft_completed':False,
            'historical_nemo_unsloth_parity':False,'correctness_scored':False,'contains_evaluator_truth':False}
        config={'model_type':'qwen3','vocab_size':16,'num_hidden_layers':36,'hidden_size':2560,
            'num_attention_heads':32,'num_key_value_heads':8,'head_dim':128,'intermediate_size':9728,
            'tie_word_embeddings':True,'attention_dropout':0,'rope_theta':5000000}
        _,ordered=ordered_rows(rows);offsets=[0]
        for row in ordered:offsets.append(offsets[-1]+len(row['input_ids']))
        _,tiny_ordered=ordered_rows(TINY);tiny_offsets=[0]
        for row in tiny_ordered:tiny_offsets.append(tiny_offsets[-1]+len(row['input_ids']))
        ledger=[];tokens=0
        for i,event in enumerate(schedule(rows)):
            tokens+=event['input_tokens'];ledger.append({**event,'completed':True,
                'cumulative_forwards':i+1,'cumulative_input_tokens':tokens})
        values={'plan.json':plan,'payload-bindings.json':{},'worker/worker-result.json':worker,
            'worker/loaded-config.json':config,'worker/worker-ledger.json':ledger,
            'worker/backward-ledger.json':[{'stage':s,'completed':True} for s in ('tiny-independent','tiny-packed')],
            'hardware.json':{'torch':'2.10.0+cu128','inventory':[{'uuid':str(i),'name':'NVIDIA L4','bf16':True} for i in range(4)]},
            'material-verification.json':{'all_files_verified':True,'material_digest':'toy-material'},
            'worker/sampled-states-policy.json':{'layers':['embed_tokens']+[f'layer-{i}' for i in range(36)]+['norm'],
                'local_positions':[[0,5,9]]*8,'offsets':offsets,'shape':[38,8,3,2560],'no_additional_forward':True}}
        for name,layers,bounds in [('tiny-linear-policy.json',2,tiny_offsets),('full-linear-policy.json',36,offsets),
                ('isolation-linear-policy.json',36,offsets)]:
            names=reader.linear_names(layers)
            values['worker/'+name]={'offsets':bounds,'module_names':names,'linear_calls_by_name':{n:1 for n in names},
                'segment_gemm_calls':len(names)*(len(bounds)-1),'weight_or_dtype_casts':0,'weights_modified':False,
                'maximum_invocations_per_module':1,'weight_dtypes':{n:'torch.bfloat16' for n in names}}
        gradients=[];shapes={name:[1,80,16] for name in ('independent-logits','packed-logits','isolation-logits')}
        shapes.update({name:[38,8,3,2560] for name in ('independent-states','packed-states')})
        shapes.update({name:[1,22,16] for name in ('tiny-reference-logits','tiny-packed-logits')})
        for i,(name,shape) in enumerate(reader.tiny_shapes().items()):
            a='tiny-reference-gradient-'+str(i);b='tiny-packed-gradient-'+str(i)
            gradients.append({'name':name,'shape':shape,'reference_vector':a,'packed_vector':b,'within_fixed_tolerance':True})
            shapes[a]=shapes[b]=shape
        values['worker/tiny-gradient-differential.json']={'gradients':gradients,'atol':.006,'rtol':.06,
            'original_scale':False,'all_gradients_passed':True,'all_logits_passed':True}
        metadata={};binary={}
        for name,shape in shapes.items():
            data=array('f',[0.0])*math.prod(shape)
            if fault in ('rehashed-numeric','honest-numerical-failure') and name=='packed-logits':data[0]=1.0
            if fault=='nonfinite' and name=='tiny-packed-gradient-0':data[0]=float('nan')
            if sys.byteorder!='little':data.byteswap()
            binary['worker/'+name+'.f32le']=data.tobytes()
            metadata[name]={'path':name+'.f32le','shape':shape,'dtype':'float32-le'}
        values['worker/vectors.json']=metadata
        if fault=='honest-numerical-failure':
            worker['whole_model_fixed_numerical_gate_passed']=False;worker['native_varlen_gpu_differential_observed']=False
        elif fault=='bool-cost':worker['optimizer_steps']=False
        elif fault=='false-sft':worker['full_sft_completed']=True
        elif fault=='extra-call':ledger.append(copy.deepcopy(ledger[-1]))
        elif fault=='partial-completion':ledger[-1]['completed']=False
        elif fault=='wrong-input':ledger[0]['input_ids_digest']=digest_value([9])
        elif fault=='duplicate-gpu':values['hardware.json']['inventory'][-1]['uuid']='0'
        elif fault=='wrong-gemm':values['worker/full-linear-policy.json']['segment_gemm_calls']-=1
        elif fault=='bool-linear-count':values['worker/full-linear-policy.json']['linear_calls_by_name'][reader.linear_names(36)[0]]=True
        elif fault=='wrong-shape':metadata['packed-states']['shape'][-1]=32
        elif fault=='missing-vector':binary.pop('worker/isolation-logits.f32le')
        values['terminal.json']={**worker,'wall_seconds':50.0}
        if fault=='failed-prefix':
            values['terminal.json'].update(outcome='failed',phase='model-probe',error_type='RuntimeError')
            values['worker/worker-ledger.json']=ledger[:2];values['worker/worker-ledger.json'][-1]['completed']=False
            values['worker/backward-ledger.json']=[]
        raw={name:canonical_bytes(value) for name,value in values.items()};raw.update(binary)
        index={'run_id':run,'plan_digest':digest_value(plan),'members':[{'path':name,'bytes':len(body),
            'sha256':hashlib.sha256(body).hexdigest()} for name,body in raw.items()]}
        path=root/'result.zip'
        with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,body in raw.items():archive.writestr(name,body)
            archive.writestr('manifest.json',canonical_bytes(index))
        return path,package,{'plan_digest':digest_value(plan)}

    def read_fixture(self,path,package,checked):
        with patch.object(reader,'preflight',return_value=checked):return reader.verify(path,package)

    def test_complete_all_vectors_qualify_only_bounded_backend(self):
        with tempfile.TemporaryDirectory() as root:result=self.read_fixture(*self.fixture(Path(root)))
        self.assertTrue(result['native_varlen_gpu_differential_observed'])
        self.assertEqual(result['internal_segment_gemm_calls'],4078)
        self.assertEqual(result['completed_outer_forwards'],13)
        self.assertFalse(result['full_sft_completed'])

    def test_honest_complete_numerical_failure_remains_unqualified(self):
        with tempfile.TemporaryDirectory() as root:result=self.read_fixture(*self.fixture(Path(root),'honest-numerical-failure'))
        self.assertFalse(result['native_varlen_gpu_differential_observed'])
        self.assertFalse(result['whole_model_fixed_numerical_gate_passed'])

    def test_rehashed_numerical_budget_scope_shape_and_hardware_faults_fail(self):
        for fault in ('rehashed-numeric','nonfinite','bool-cost','false-sft','extra-call','partial-completion',
                'wrong-input','duplicate-gpu','wrong-gemm','bool-linear-count','wrong-shape','missing-vector'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValidationError):self.read_fixture(*self.fixture(Path(root),fault))

    def test_failed_work_recounts_only_actual_completed_prefix(self):
        with tempfile.TemporaryDirectory() as root:result=self.read_fixture(*self.fixture(Path(root),'failed-prefix'))
        self.assertEqual((result['reserved_outer_forwards'],result['completed_outer_forwards']),(2,1))
        self.assertFalse(result['native_varlen_gpu_differential_observed'])


if __name__=='__main__':unittest.main()
