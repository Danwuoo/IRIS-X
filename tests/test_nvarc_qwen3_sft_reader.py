"""Artificial closed archives test isolation, never qualify a real SFT run."""
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
from tools.verify_nvarc_qwen3_source_sft import material_entries,read_archive,verify
from tools.verify_nvarc_qwen3_source_sft import expected_calls
from irisx.arc_nvarc_qwen3_packed_step import schedule


class OriginalSFTReaderTests(unittest.TestCase):
    def test_artificial_two_phase_complete_reader_rejects_rehashed_cost_and_restart_faults(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);package=root/'package';package.mkdir()
            rows=[{'input_ids':[14,11,10,1,15,14,12,10,2,15],
                'labels':[-100]*8+[2,15],'shuffle_position':i,'parent_id':'artificial-only'} for i in range(512)]
            placements=[schedule(rows[:256]),schedule(rows[256:])]
            plan={'run_id':'nvarc-original-qwen3-sft-901','data_kind':'original-source-prefix',
                'data_digest':digest_value(rows),'physical_schedules':placements}
            stream=digest_value({'kind':plan['data_kind'],'rows_digest':plan['data_digest']})
            identity=digest_value({'plan':plan,'source_stream_identity':stream})
            hardware=[{'uuid':f'artificial-uuid-{rank}','name':'NVIDIA L4','bf16':True} for rank in range(4)]
            objects={'plan.json':plan,'payload-bindings.json':{},'hardware.json':{'inventory':hardware},
                'checkpoint-inventory.json':[],'terminal.json':{'run_id':plan['run_id'],'outcome':'complete',
                    'contains_evaluator_truth':False,'generation_calls':0,'teacher_calls':0,'full_sft_completed':False,
                    'identity_digest':identity,'export_material_digest':'artificial-export'}}
            for index,placement in enumerate(placements):
                observations=[]
                for rank in range(4):
                    calls=expected_calls(rows[index*256:(index+1)*256],rank,placement['collective_slots_per_rank'])
                    stem=f'worker/rank-{rank}-'
                    objects[stem+f'call-reservation-{index:05d}.json']={'plan_digest':digest_value(plan),
                        'outer_forwards':1,'input_tokens':640,'source_input_tokens':640,
                        'completed':True,'real_forwards':1,'dummy_forwards':0}
                    objects[stem+f'forward-ledger-{index:05d}.json']=[{**call,'completed':True} for call in calls]
                    observations.append({'rank':rank,'step':index+1,'hardware':{'device_uuid':hardware[rank]['uuid']},
                        'checkpointed_layers':36,'packing_execution':'torch-varlen-flash','fused_packing_verified':True,
                        'missing_owned_gradient_shards':[],'finite_nonzero_shards':1,'owned_parameter_shards':1,
                        'accumulated_parameter_shards':1,'physical_packing_layout_digests':placement['ranks'][rank]['physical_digests'],
                        'real_forward_calls':1,'dummy_forward_calls':0,'global_sequence_count':256,
                        'global_input_tokens':2560,'global_supervised_tokens':512,'global_token_mean_loss':1.,
                        'gradient_norm_before_clip':1.,'source_lineage':[{k:v for k,v in row.items() if k not in {'input_ids','labels'}}
                            for row in rows[index*256+rank:(index+1)*256:4]],
                        'state_residency':{key:{'cpu/torch.float32':100} for key in ('parameter_bytes','gradient_bytes','optimizer_bytes')}})
                result={'identity_digest':identity,'plan_digest':digest_value(plan),'source_stream_identity':stream,
                    'step':index+1,'cursor':256*(index+1),'input_tokens':2560*(index+1),'supervised_tokens':512*(index+1),
                    'forwards':4*(index+1),'full_sft_completed':False,'model_family':'qwen3',
                    'optimizer_checkpoints_retained':True,'contains_evaluator_truth':False,'generation_calls':0,'teacher_calls':0,
                    'weight_fingerprint_before':[0.,0.],'weight_fingerprint_after':[float(index+1),float(index+1)],
                    'observations':[observations],'checkpoint':{'manifest_digest':'artificial-checkpoint'}}
                if index:result['restored_fingerprint']=[1.,1.]
                objects['worker/'+('pause-result.json' if not index else 'final-result.json')]=result
            objects['worker/export-chain.json']={'identity_digest':identity,'checkpoint_step':2,
                'checkpoint_manifest_digest':'artificial-checkpoint','reload_tensor_bytes_identical':True,
                'export_material_digest':'artificial-export'}
            (package/'plan.json').write_bytes(canonical_bytes(plan));(package/'samples.json').write_bytes(canonical_bytes(rows))
            (package/'stage-summary.json').write_bytes(canonical_bytes({'payload_sha256':{}}))
            def archive(name,values):
                raw={k:canonical_bytes(v) for k,v in values.items()};path=root/(name+'.zip')
                manifest={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'members':[
                    {'path':k,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in raw.items()]}
                with zipfile.ZipFile(path,'x') as stream:
                    stream.writestr('manifest.json',canonical_bytes(manifest))
                    for k,v in raw.items():stream.writestr(k,v)
                return path
            with patch('tools.stage_nvarc_qwen3_sft.preflight',return_value={'external_calls':0}):
                proof=verify(archive('good',objects),package)
                self.assertEqual(8,sum(r['completed_forwards'] for r in proof['actual_call_prefixes']))
                self.assertFalse(proof['retained_optimizer_bytes_verified'])
                for label,key,value in [('calls','real_forward_calls',2),('uuid','hardware',{'device_uuid':'wrong'}),
                        ('tokens','global_input_tokens',2561),('dtype','state_residency',{
                            key:{'cuda/torch.bfloat16':100} for key in ('parameter_bytes','gradient_bytes','optimizer_bytes')})]:
                    changed=copy.deepcopy(objects);changed['worker/final-result.json']['observations'][0][0][key]=value
                    with self.subTest(label=label),self.assertRaises(ValidationError):verify(archive(label,changed),package)
                changed=copy.deepcopy(objects);changed['worker/final-result.json']['restored_fingerprint']=[2.,2.]
                with self.assertRaises(ValidationError):verify(archive('restart',changed),package)

    def test_failure_archive_does_not_claim_work_and_rehashed_input_changes_are_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);package=root/'package';package.mkdir()
            plan={'run_id':'nvarc-original-qwen3-sft-901','data_kind':'original-source-prefix',
                'data_digest':digest_value([]),'physical_schedules':[]}
            hashes={'fixture':'source binding only'}
            (package/'plan.json').write_bytes(canonical_bytes(plan))
            (package/'samples.json').write_bytes(b'[]')
            (package/'stage-summary.json').write_bytes(canonical_bytes({'payload_sha256':hashes}))
            objects={'plan.json':plan,'payload-bindings.json':hashes,'checkpoint-inventory.json':[],
                'terminal.json':{'run_id':plan['run_id'],'outcome':'failed','phase':'retained-storage-gate',
                    'contains_evaluator_truth':False,'generation_calls':0,'teacher_calls':0,'full_sft_completed':False}}
            def archive(name,values):
                path=root/name;raw={k:canonical_bytes(v) for k,v in values.items()}
                manifest={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'members':[
                    {'path':k,'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in raw.items()]}
                with zipfile.ZipFile(path,'x') as stream:
                    stream.writestr('manifest.json',canonical_bytes(manifest))
                    for k,v in raw.items():stream.writestr(k,v)
                return path
            with patch('tools.stage_nvarc_qwen3_sft.preflight',return_value={'external_calls':0}):
                proof=verify(archive('good.zip',objects),package)
                self.assertEqual('failed',proof['outcome']);self.assertFalse(proof['full_sft_completed'])
                self.assertFalse(proof['retained_optimizer_bytes_verified'])
                for name,alter in [('plan',{'plan.json':{**plan,'data_digest':'changed'}}),
                        ('payload',{'payload-bindings.json':{'fixture':'changed'}}),
                        ('calls',{'worker/rank-9-call-reservation-00000.json':{}}),
                        ('ledger',{'worker/rank-9-forward-ledger-00000.json':[]}),
                        ('truth',{'terminal.json':{**objects['terminal.json'],'contains_evaluator_truth':True}}),
                        ('path',{'../escaped.json':{}})]:
                    with self.subTest(name=name),self.assertRaises(ValidationError):
                        verify(archive(name+'.zip',{**objects,**alter}),package)
                with zipfile.ZipFile(root/'good.zip','a') as stream:
                    stream.writestr('plan.json',canonical_bytes(plan))
                with self.assertRaises(ValidationError):read_archive(root/'good.zip',package)

    def test_latest_checkpoint_transfer_is_bounded_and_cannot_cross_a_transaction(self):
        transaction='checkpoint-step-0002-attempt-0001'
        items=[{'path':'checkpoints/latest.json','bytes':100,'sha256':'fixture'},
            {'path':f'checkpoints/{transaction}/manifest.json','bytes':100,'sha256':'fixture'},
            {'path':f'checkpoints/{transaction}/dcp/__0_0.distcp','bytes':11*1024**3,'sha256':'fixture'}]
        data={'checkpoint-inventory.json':canonical_bytes(items)}
        terminal={'outcome':'failed'}
        self.assertEqual(items,material_entries(data,terminal))
        for wrong in ([items[0],{**items[1],'path':'checkpoints/../../escape'}],items+[items[0]],
                [items[0],{**items[1],'bytes':17*1024**3}],items+[
                    {'path':'checkpoints/checkpoint-step-0001-attempt-0001/manifest.json','bytes':100}],items[1:]):
            with self.subTest(wrong=wrong),self.assertRaises(ValidationError):
                material_entries({'checkpoint-inventory.json':canonical_bytes(wrong)},terminal)


if __name__=='__main__':unittest.main()
