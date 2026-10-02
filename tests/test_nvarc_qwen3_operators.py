"""Closed partial-layer vectors; rehashed false claims cannot qualify SFT."""
from array import array
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_qwen3_operator_probe import FORMAT,MODES,OPERATORS,OperatorBudget,schedule,parameter_layout
from irisx.arc_nvarc_qwen3_packing_diagnostic import ordered_rows
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools import verify_nvarc_qwen3_operators as reader


class FirstLayerOperatorEvidenceTests(unittest.TestCase):
    def rows(self):
        return [{'input_ids':[14,11,10,i,15,14,12,10,2,15],'labels':[-100]*8+[2,15],
            'parent_ids':['toy-'+str(i)],'exposure':['training2']} for i in range(8)]

    def test_changed_or_unreserved_actual_input_cannot_consume_operator_budget(self):
        rows=self.rows();allowed=schedule(rows);retained=[]
        plan={'maximum_outer_forwards':21,'maximum_input_tokens':560,'maximum_worker_wall_seconds':900}
        budget=OperatorBudget(rows,plan,lambda name,value:retained.append(copy.deepcopy(value)))
        model=type('Qwen3ForCausalLM',(),{})();calls=[]
        class Tensor:
            def __init__(self,ids):self.ids=ids
            def tolist(self):return [self.ids]
        def actual(*args,**kwargs):
            self.assertFalse(retained[-1][-1]['completed']);calls.append(1);return 'vector'
        def invoke(ids):return budget.guard_call(model,(),{'input_ids':Tensor(ids)},actual)
        with self.assertRaises(ValidationError):invoke(rows[0]['input_ids'])
        with self.assertRaises(ValidationError):budget.perform(MODES[0],lambda:invoke([1,2]))
        self.assertEqual(calls,[])
        self.assertEqual(budget.perform(MODES[0],lambda:invoke(rows[0]['input_ids'])),'vector')
        self.assertTrue(retained[-1][-1]['completed'])
        with self.assertRaises(ValidationError):budget.perform(MODES[2],lambda:invoke(rows[1]['input_ids']))
        self.assertEqual(len(calls),1)
        self.assertEqual(len(allowed),21)
        self.assertEqual(sum(row['input_tokens'] for row in allowed),560)

    def fixture(self,root,fault=None):
        rows=self.rows();run='nvarc-original-qwen3-probe-999';plan={'format':FORMAT,'run_id':run,
            'retained_decoder_layers':[0],'whole_model_numerical_qualification':False,
            'maximum_notebook_wall_seconds':1200,'maximum_input_tokens':560,'model_material_digest':'toy-material'}
        package=root/'package';package.mkdir();atomic(package/'plan.json',plan);atomic(package/'samples.json',rows)
        atomic(package/'stage-summary.json',{'payload_sha256':{}})
        config={'num_hidden_layers':36,'tie_word_embeddings':True,'hidden_size':2560,'head_dim':128,
            'vocab_size':16,'num_attention_heads':32,'num_key_value_heads':8,'intermediate_size':9728}
        ledger=[];tokens=0
        for i,event in enumerate(schedule(rows)):
            tokens+=event['input_tokens'];ledger.append({**event,'completed':True,
                'cumulative_forwards':i+1,'cumulative_input_tokens':tokens})
        _,ordered=ordered_rows(rows);offsets=[0]
        for row in ordered:offsets.append(offsets[-1]+len(row['input_ids']))
        values={'plan.json':plan,'payload-bindings.json':{},
            'terminal.json':{'run_id':run,'outcome':'complete','wall_seconds':50.0,'contains_evaluator_truth':False},
            'worker/worker-ledger.json':ledger,'hardware.json':{'torch':'2.10.0+cu128',
                'inventory':[{'uuid':str(i),'name':'NVIDIA L4','bf16':True} for i in range(4)]},
            'material-verification.json':{'all_files_verified':True,'material_digest':'toy-material'},
            'worker/worker-result.json':{'format':FORMAT,'run_id':run,'plan_digest':digest_value(plan),'outcome':'complete',
                'contains_evaluator_truth':False,'full_sft_completed':False,'correctness_scored':False,'partial_model':True,
                'decoder_layers_executed':1,'whole_model_numerical_gate_passed':False,'actual_outer_forwards':21,
                'actual_input_tokens':560,'optimizer_steps':0,'backwards':0,'generation_calls':0,'teacher_calls':0},
            'worker/original-loaded-config.json':config,'worker/retained-model-subset.json':{
                'original_decoder_layers':36,'retained_decoder_layers':[0],'whole_model':False,'weights_modified':False,
                'parameters':[{'name':name,'shape':shape,'dtype':'torch.bfloat16'} for name,shape in parameter_layout(config).items()]},
            'worker/capture-policy.json':{'operators':list(OPERATORS),'local_positions':[[0,5,9]]*8,'offsets':offsets,
                'whole_model_qualification':False,'additional_forwards_from_hooks':0}}
        settings={};metadata={};binary={};arrays={}
        for mode in MODES:
            fp32='fp32-linear' in mode
            settings[mode]={'bf16_reduced_precision_reduction':not ('no-reduced' in mode or fp32),
                'float32_matmul_precision':'highest' if fp32 else 'medium',
                'linear_compute':'float32 with output cast to input dtype' if fp32 else 'stored bfloat16',
                'rewritten_linear_modules':8 if fp32 else 0,'attention':'sdpa' if mode.startswith('independent') else
                    'irisx_qwen3_torch_varlen_native_gqa' if 'native-gqa' in mode else 'irisx_qwen3_torch_varlen'}
            for operator in (*OPERATORS,'logits'):
                name=mode+'-'+operator;shape=[1,80,16] if operator=='logits' else [8,3,1]
                data=array('f',[0.0]*(__import__('math').prod(shape)))
                if mode=='packed-repeat' and operator in ('q-projection','layer-0-output','logits'):data[0]=0.5
                if sys.byteorder!='little':data.byteswap()
                metadata[name]={'path':name+'.f32le','shape':shape,'dtype':'float32-le'}
                binary['worker/'+name+'.f32le']=data.tobytes();arrays[name]=data
        comparisons={mode:{operator:{'max_absolute_error':max(abs(a-b) for a,b in zip(arrays[mode+'-'+operator],
            arrays[('independent-fp32-linear' if 'fp32-linear' in mode else 'independent-flash-sdpa')+'-'+operator])),
            'bitwise_equal':arrays[mode+'-'+operator]==arrays[('independent-fp32-linear' if 'fp32-linear' in mode else 'independent-flash-sdpa')+'-'+operator]}
            for operator in (*OPERATORS,'logits')} for mode in MODES[2:]}
        values.update({'worker/compute-settings.json':settings,'worker/vectors.json':metadata,'worker/operator-comparisons.json':comparisons})
        if fault=='rehashed-vector':binary['worker/packed-repeat-q-projection.f32le']=array('f',[1.0]+[0.0]*23).tobytes()
        elif fault=='nonfinite-vector':binary['worker/packed-repeat-q-projection.f32le']=array('f',[float('inf')]+[0.0]*23).tobytes()
        elif fault=='missing-vector':binary.pop('worker/packed-repeat-q-projection.f32le')
        elif fault=='bool-cost':values['worker/worker-result.json']['backwards']=False
        elif fault=='partial-completion':ledger[-1]['completed']=False
        elif fault=='wrong-input':ledger[0]['input_ids_digest']=digest_value([1,2])
        elif fault=='full-model-claim':values['worker/worker-result.json']['whole_model_numerical_gate_passed']=True
        elif fault=='missing-parameter':values['worker/retained-model-subset.json']['parameters'].pop()
        elif fault=='wrong-dtype':values['worker/retained-model-subset.json']['parameters'][0]['dtype']='torch.float32'
        elif fault=='changed-precision':settings['packed-repeat-no-reduced']['bf16_reduced_precision_reduction']=True
        elif fault=='duplicate-gpu':values['hardware.json']['inventory'][-1]['uuid']='0'
        elif fault=='failed-prefix':
            values['terminal.json'].update(outcome='failed',phase='model-probe',error_type='RuntimeError')
            values['worker/worker-ledger.json']=ledger[:2];values['worker/worker-ledger.json'][-1]['completed']=False
        raw={name:canonical_bytes(value) for name,value in values.items()};raw.update(binary)
        index={'run_id':run,'plan_digest':digest_value(plan),'members':[{'path':name,'bytes':len(body),
            'sha256':hashlib.sha256(body).hexdigest()} for name,body in raw.items()]}
        path=root/'result.zip'
        with zipfile.ZipFile(path,'x') as stream:
            for name,body in raw.items():stream.writestr(name,body)
            stream.writestr('manifest.json',canonical_bytes(index))
        return path,package,{'plan_digest':digest_value(plan)}

    def read_fixture(self,path,package,checked):
        with patch.object(reader,'preflight',return_value=checked),patch.object(reader,'WIDTHS',{name:1 for name in OPERATORS}):
            return reader.verify(path,package)

    def test_complete_vectors_identify_first_operator_without_qualifying_whole_model(self):
        with tempfile.TemporaryDirectory() as temporary:result=self.read_fixture(*self.fixture(Path(temporary)))
        self.assertEqual(result['first_nonbitwise_operator']['packed-repeat'],'q-projection')
        self.assertIsNone(result['first_nonbitwise_operator']['packed-fp32-linear'])
        self.assertEqual(result['completed_outer_forwards'],21)
        self.assertFalse(result['whole_model_numerical_gate_passed'])
        self.assertFalse(result['full_sft_completed'])

    def test_rehashed_vector_cost_precision_subset_or_hardware_faults_are_rejected(self):
        for fault in ('rehashed-vector','nonfinite-vector','missing-vector','bool-cost','partial-completion',
                'wrong-input','full-model-claim','missing-parameter','wrong-dtype','changed-precision','duplicate-gpu'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temporary:
                with self.assertRaises(ValidationError):self.read_fixture(*self.fixture(Path(temporary),fault))

    def test_failure_recounts_only_completed_partial_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:result=self.read_fixture(*self.fixture(Path(temporary),'failed-prefix'))
        self.assertEqual((result['reserved_outer_forwards'],result['completed_outer_forwards']),(2,1))
        self.assertFalse(result['whole_model_numerical_gate_passed'])


if __name__=='__main__':unittest.main()
