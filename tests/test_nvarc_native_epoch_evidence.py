"""Artificial digest protocol only; preflight is mocked, no model/approved data used."""
from array import array
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from irisx.canonical import canonical_bytes,digest_value
from irisx.errors import ValidationError
from tools import verify_nvarc_native_long_ttt as reader


class NativeEpochEvidenceTests(unittest.TestCase):
    def fixture(self,root):
        package=root/'package';package.mkdir();original=root/'original/execution-final/retrieved';original.mkdir(parents=True)
        ids=[0]*7464;labels=[-100]*3744+[1]*3720
        expected={'input_tokens':7464,'supervised_tokens':3720,'input_ids_digest':digest_value(ids),'labels_digest':digest_value(labels)}
        rows=[dict(expected) for _ in range(128)];rates=[0.]+[5e-5]*127+[0.]
        topo=[{'name':f'parameter-{i}','shape':[528564224-505 if i==0 else 1],
            'elements':528564224-505 if i==0 else 1,'dtype':'torch.bfloat16'} for i in range(506)]
        baseline=[{**row,'finite':True,'sha256':'a'*64} for row in topo]
        with zipfile.ZipFile(original/'gpu-preflight-result.zip','w') as stream:stream.writestr('native/baseline-inventory.json',canonical_bytes(baseline))
        flags=[{'module':str(i),'value':True} for i in range(37)]
        plan={'run_id':'artificial-protocol','model_material_digest':'artificial','source_learning_rates':rates,
            'maximum_notebook_wall_seconds':10800,'maximum_child_wall_seconds':10500,
            'native_trainer_origins':[],'native_checkpoint_flags':flags,'native_adapter_topology':topo}
        (package/'plan.json').write_bytes(canonical_bytes(plan));binding=digest_value(plan)
        raw={key:key.encode() for key in ('worker','helper','budget','hardware','solver')}
        raw['expected_rows']=canonical_bytes(rows)
        prepared=[{**row,'retained_byte_offset':i*29856,'retained_token_bytes':29856} for i,row in enumerate(rows)]
        state={'forwards':[{**row,'completed':True,'loss':.7} for row in rows],
            'training_steps':[{'completed':True} for _ in rows],
            'optimizer_steps':[{'completed':True,'learning_rate':rates[i],'gradient_tensors':506,'gradient_norm_after_clip':.8} for i in range(128)],
            'optimizer_constructions':[{'completed':True}],'generation_calls':0,'teacher_calls':0}
        terminal={'run_id':plan['run_id'],'outcome':'complete','wall_seconds':1.,'contains_evaluator_truth':False,
            'generations':0,'teacher_calls':0,'paid_usd':0,'model_forwards':128,'optimizer_steps':128,
            'model_forwards_reserved':128,'optimizer_steps_reserved':128,'training_steps_reserved':128}
        gpus=[{'uuid':str(i),'name':'NVIDIA L4','bf16':True,'total_memory_bytes':100} for i in range(4)]
        trained=copy.deepcopy(baseline);trained[0]['sha256']='b'*64
        result={'run_id':plan['run_id'],'plan_digest':binding,'outcome':'complete','model_forwards':128,'optimizer_steps':128,
            'input_tokens':955392,'supervised_tokens':476160,'trainer_global_step':128,'trainer_epoch':1.,
            'generations':0,'teacher_calls':0,'paid_usd':0,'full_native_long_ttt_completed':True,'optimizer_discarded':True,
            'all_saved_tensors_restored':True,'checkpoint_exported':False,'correctness_scored':False,
            'contains_evaluator_truth':False,'training_wall_seconds':1.,'worker_wall_seconds':1.,
            'gradient_tensors_per_step':506,'cuda_peak_allocated_bytes':1,'cuda_peak_reserved_bytes':2}
        values={'plan.json':plan,'payload-bindings.json':{key:hashlib.sha256(value).hexdigest() for key,value in raw.items()},
            'terminal.json':terminal,'native/training-ledger.json':state,'hardware.json':{'torch':'2.8.0+cu128','cuda':'12.8','inventory':gpus},
            'native/hardware.json':{'device_uuid':'0'},'source-verification.json':{'inventory':{}},
            'model-verification.json':{'model_material_digest':'artificial','all_ten_files_verified':True},
            'native/preparation.json':{'max_length':8192,'max_seq_length':8192,'trainer_origins':[],
                'prepared_rows_digest':digest_value(prepared),'blocked_attempts':0,'checkpoint_flags':flags},
            'native/prepared-rows.json':prepared,'native/adapter-topology.json':topo,'native/baseline-inventory.json':baseline,
            'native/reset-inventory.json':baseline,'native/trained-inventory.json':trained,'native/training-result.json':result,
            'native/optimizer-state.json':[{'elements':row['elements'],'moment_bytes':row['elements']*4,
                'parameter_dtype':'torch.bfloat16','parameter_device':'cuda:0','step':128,'finite':True} for row in topo]}
        data={name:canonical_bytes(value) for name,value in values.items()}
        data.update({name:raw[key] for name,key in [('inspection.py','worker'),('inspection_helpers.py','helper'),
            ('nvarc_native_ttt_budget.py','budget'),('hardware_helpers.py','hardware'),('solver.py','solver'),('expected-rows.json','expected_rows')]})
        tokens=array('h',ids+labels)
        import sys
        if sys.byteorder!='little':tokens.byteswap()
        data['native/prepared-tokens.i16le']=tokens.tobytes()*128
        return package,root/'original',binding,raw,data

    def check(self,root,fixture,data):
        package,original,binding,raw,_=fixture;archive=root/'result.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as stream:
            members=[]
            for name,body in data.items():
                stream.writestr(name,body);members.append({'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
            stream.writestr('manifest.json',canonical_bytes({'run_id':'artificial-protocol','plan_digest':binding,'members':members}))
        with patch.object(reader,'preflight',return_value={'plan_digest':binding}),patch.object(reader,'raw_payloads',return_value=raw),\
            patch.object(reader,'native_inventory',return_value={}),patch.object(reader,'PREPARATION',original):
            return reader.verify(archive,package)

    def test_complete_protocol_and_rehashed_cost_mask_reset_moment_faults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture=self.fixture(root);data=fixture[-1]
            self.assertTrue(self.check(root,fixture,data)['full_native_long_ttt_completed'])
            changes=[('terminal.json','optimizer_steps',True),('native/training-result.json','input_tokens',1),
                ('native/training-result.json','full_native_long_ttt_completed',1),
                ('native/training-ledger.json','generation_calls',False)]
            for name,key,value in changes:
                altered=dict(data);obj=json.loads(altered[name]);obj[key]=value;altered[name]=canonical_bytes(obj)
                with self.subTest(name=name,key=key),self.assertRaises(ValidationError):self.check(root,fixture,altered)
            for name,index,key,value in [('native/optimizer-state.json',0,'step',True),
                ('native/reset-inventory.json',0,'sha256','c'*64),('native/prepared-rows.json',0,'retained_byte_offset',1)]:
                altered=dict(data);obj=json.loads(altered[name]);obj[index][key]=value;altered[name]=canonical_bytes(obj)
                with self.subTest(name=name,key=key),self.assertRaises(ValidationError):self.check(root,fixture,altered)

    def test_failed_prefix_retains_completed_and_reserved_work_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture=self.fixture(root);data=dict(fixture[-1]);state=json.loads(data['native/training-ledger.json'])
            state.update(forwards=state['forwards'][:1],training_steps=[{'completed':False}],optimizer_steps=[])
            state['forwards'][0].update(completed=False);state['forwards'][0].pop('loss')
            data['native/training-ledger.json']=canonical_bytes(state)
            terminal=json.loads(data['terminal.json']);terminal.update(outcome='failed',phase='worker',error_type='TimeoutError',error_message='fixture',
                model_forwards=0,optimizer_steps=0,model_forwards_reserved=1,optimizer_steps_reserved=0,training_steps_reserved=1)
            data['terminal.json']=canonical_bytes(terminal);result=self.check(root,fixture,data)
            self.assertEqual(result['model_forwards_reserved'],1);self.assertEqual(result['model_forwards'],0)
            self.assertFalse(result['full_native_long_ttt_completed'])


if __name__=='__main__':unittest.main()
