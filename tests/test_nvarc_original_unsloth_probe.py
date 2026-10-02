"""Independently recalculate numeric vectors and reject altered call budgets."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import stage_nvarc_original_unsloth_probe as probe
from irisx.arc_nvarc_combined import atomic
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError


class OriginalUnslothProbeTests(unittest.TestCase):
    def test_production_call_guard_reserves_before_call_and_blocks_extra_work(self):
        function=next(node for node in ast.parse(probe.WORKER).body if isinstance(node,ast.FunctionDef) and node.name=='bounded_call')
        class Tensor:
            def __init__(self,rows):self.rows=rows
            def detach(self):return self
            def cpu(self):return self
            def tolist(self):return self.rows
        model=type('Qwen3ForCausalLM',(),{})()
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary);executed=[]
            def actual_call(*args,**kwargs):
                ledger=json.loads((output/'reference-ledger.json').read_bytes())
                self.assertEqual(len(ledger),len(executed)+1)
                executed.append(ledger[-1]['stage']);return 'actual call'
            namespace={'active':None,'events':[],'ids':probe.IDS,'mode':'reference','output':output,
                'original_call':actual_call,'json':json}
            exec(compile(ast.Module(body=[function],type_ignores=[]),'trusted-production-cost-hook','exec'),namespace)
            hook=namespace['bounded_call']
            with self.assertRaises(RuntimeError):hook(model,input_ids=Tensor([probe.IDS]))
            self.assertEqual(executed,[])
            namespace['active']='prefill';hook(model,input_ids=Tensor([probe.IDS]))
            namespace['active']='cached-token'
            with self.assertRaises(RuntimeError):hook(model,input_ids=Tensor([[1]]))
            self.assertEqual(executed,['prefill'])
            hook(model,input_ids=Tensor([[0]]))
            with self.assertRaises(RuntimeError):hook(model,input_ids=Tensor([[0]]))
            self.assertEqual(executed,['prefill','cached-token'])
            self.assertEqual(sum(row['input_tokens_reserved'] for row in namespace['events']),13)

    def fixture(self, root, fault=None):
        package=root/'package';package.mkdir();run='nvarc-original-qwen3-unsloth-probe-999'
        plan={'run_id':run};atomic(package/'plan.json',plan);atomic(package/'stage-summary.json',{'payload_sha256':{}})
        content={'plan.json':plan,'payload-bindings.json':{},'terminal.json':{'run_id':run,'outcome':'complete',
            'contains_evaluator_truth':False,'wall_seconds':100.0,'optimizer_steps':0,'generations':0,'teacher_calls':0,'paid_usd':0},
            'hardware.json':{'inventory':[{'uuid':str(i),'name':'NVIDIA L4','bf16':True} for i in range(4)],
                'torch':'2.8.0+cu128','cuda':'12.8'},
            'model-verification.json':{'all_ten_files_verified':True,'model_material_digest':probe.MATERIAL},
            'dependency-verification.json':{'inventory':{}}}
        for mode in ('reference','unsloth'):
            content[mode+'-ledger.json']=[{'stage':stage,'input_ids':[ids],'outer_forwards_reserved':1,
                'input_tokens_reserved':len(ids)} for stage,ids in [('prefill',probe.IDS),('cached-token',[0])]]
            vectors=[[float(i) for i in range(16)], [float(i) for i in range(16)]]
            if mode=='unsloth':vectors[1][5]+=0.25
            content[mode+'-result.json']={'mode':mode,'versions':probe.PACKAGES,'python':'3.11.13',
                'torch':'2.8.0+cu128','cuda':'12.8','outer_forwards':2,'input_tokens':13,
                'untied_storage_observed':True,'parameter_dtypes':['torch.bfloat16'],
                'model_class':'Qwen3ForCausalLM','optimizer_steps':0,'generations':0,'teacher_calls':0,'vectors':vectors}
        if fault=='bool-cost':content['unsloth-ledger.json'][0]['outer_forwards_reserved']=True
        elif fault=='wrong-token':content['unsloth-ledger.json'][1]['input_ids']=[[1]]
        elif fault=='extra-call':content['reference-ledger.json'].append(dict(content['reference-ledger.json'][1]))
        elif fault=='trained':content['unsloth-result.json']['optimizer_steps']=1
        elif fault=='nonfinite':content['unsloth-result.json']['vectors'][0][0]=float('inf')
        elif fault=='bad-hardware':content['hardware.json']['inventory'][3]['uuid']='0'
        elif fault=='failure-prefix':
            content['terminal.json']['outcome']='failed'
            for name in ('reference-result.json','unsloth-result.json','unsloth-ledger.json'):
                content.pop(name)
            content['reference-ledger.json']=content['reference-ledger.json'][:1]
        raw={k:json.dumps(v,sort_keys=True,separators=(',',':')).encode() for k,v in content.items()}
        index={'run_id':run,'plan_digest':digest_value(plan),'members':[{'path':name,'bytes':len(body),
            'sha256':hashlib.sha256(body).hexdigest()} for name,body in raw.items()]}
        path=root/'result.zip'
        with zipfile.ZipFile(path,'x') as archive:
            for name,body in raw.items():archive.writestr(name,body)
            archive.writestr('manifest.json',canonical_bytes(index))
        return path,package,{'plan_digest':digest_value(plan)}

    def test_independent_numeric_recount_keeps_runtime_completion_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,package,checked=self.fixture(Path(temporary))
            with patch.object(probe,'preflight',return_value=checked),patch.object(probe,'binding',return_value={'inventory':{}}):
                result=probe.verify_archive(path,package)
            self.assertEqual((result['reserved_outer_forwards'],result['reserved_input_tokens']),(4,26))
            self.assertEqual(result['comparisons']['cached-token']['maximum_absolute_logit_difference'],0.25)
            self.assertTrue(result['comparisons']['prefill']['bitwise_equal'])
            self.assertFalse(result['historical_full_solver_parity'])
            self.assertFalse(result['correctness_scored'])

    def test_rehashed_cost_input_result_and_hardware_faults_are_rejected(self):
        for fault in ('bool-cost','wrong-token','extra-call','trained','nonfinite','bad-hardware'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temporary:
                path,package,checked=self.fixture(Path(temporary),fault)
                with patch.object(probe,'preflight',return_value=checked),patch.object(probe,'binding',return_value={'inventory':{}}),self.assertRaises(ValidationError):
                    probe.verify_archive(path,package)

    def test_failure_retains_only_actual_reserved_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            path,package,checked=self.fixture(Path(temporary),'failure-prefix')
            with patch.object(probe,'preflight',return_value=checked),patch.object(probe,'binding',return_value={'inventory':{}}):
                result=probe.verify_archive(path,package)
            self.assertEqual(result['outcome'],'failed')
            self.assertEqual((result['reserved_outer_forwards'],result['reserved_input_tokens']),(1,12))
            self.assertEqual(result['comparisons'],{})


if __name__=='__main__':unittest.main()
