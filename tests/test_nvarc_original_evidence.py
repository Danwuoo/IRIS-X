"""Rehashed hostile evidence and source grid-contract controls, offline."""
import hashlib
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.reconcile_nvarc_published_yield import inspect_pairs
from tools.verify_nvarc_qwen3_probe import verify,check_architecture
from tools.audit_nvarc_sdg_programs import inspect_program,carry_observation
from irisx.arc_nvarc_packing import pack_sequences,validate_pack
from irisx.arc_nvarc_qwen3_packing import execution_slices
from tools.stage_nvarc_qwen3_packed_step import prerequisite
from tools.verify_nvarc_qwen3_packed_step import verify as verify_packed_step
from irisx.arc_nvarc_qwen3_packed_step import FORMAT,BASE,PREFIX_SHA,schedule,StepCallBudget,call_schedule
from irisx.arc_nvarc_gpu_preflight_v2 import RECIPE


class OriginalEvidenceTests(unittest.TestCase):
    def test_actual_full_gradient_causal_or_extra_forward_is_blocked_before_entry(self):
        rows=[{'input_ids':[14,15],'labels':[-100,15],'shuffle_position':i} for i in range(256)]
        retained=[];budget=StepCallBudget(rows,0,lambda events:retained.append(copy.deepcopy(events)))
        class Tensor:
            def __init__(self,value):self.value=value
            def tolist(self):return self.value
        want=call_schedule(rows,0)[0]
        kwargs={'input_ids':Tensor([[14,15]*64]),'position_ids':Tensor([[0,1]*64]),
            'cu_seq_lens_q':Tensor(want['cu_seqlens']),'cu_seq_lens_k':Tensor(want['cu_seqlens']),
            'max_length_q':2,'max_length_k':2,'use_cache':False}
        with self.assertRaises(ValidationError):budget.before(None,(),{**kwargs,'position_ids':Tensor([list(range(128))])})
        self.assertEqual(retained,[])
        budget.before(None,(),kwargs);self.assertFalse(retained[-1][0]['completed'])
        budget.after(None,(),None);self.assertTrue(retained[-1][0]['completed'])
        with self.assertRaises(ValidationError):budget.before(None,(),kwargs)
        self.assertEqual(len(budget.events),1)

    def test_packed_step_reader_reconstructs_rehashed_rank_cost(self):
        rows=[{'input_ids':[14,15],'labels':[-100,15],'shuffle_position':i} for i in range(256)]
        placement=schedule(rows)
        plan={'format':FORMAT,'run_id':'nvarc-original-qwen3-packed-step-001','owner_decision':'Decision 0054',
            'world_size':4,'source_recipe':RECIPE,'data_digest':digest_value(rows),'source_prefix_sha256':PREFIX_SHA,
            'model_material_digest':BASE,'maximum_optimizer_steps':1,'maximum_paid_usd':0,
            'maximum_generations':0,'maximum_teacher_calls':0,'retain_export':False,
            'maximum_physical_input_tokens':32768,'packing_capacity':256000,'packing_length_multiple':64,
            'maximum_notebook_wall_seconds':4500,'maximum_worker_wall_seconds':4200,
            'scheduled_input_tokens':512,'scheduled_supervised_tokens':256,'maximum_input_tokens':512,
            'maximum_outer_forwards':4,'physical_schedule':placement}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);package=root/'package';package.mkdir()
            for name,value in (('plan.json',plan),('samples.json',rows),('stage-summary.json',{'payload_sha256':{'runtime':'abc'}})):
                (package/name).write_text(json.dumps(value),encoding='utf-8')
            reservation={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'optimizer_steps_reserved':1,
                'outer_forwards_reserved':1,'input_tokens_reserved':128,'dummy_input_tokens_reserved':0,
                'generation_calls':0,'teacher_calls':0,'maximum_paid_usd':0}
            values={'plan.json':plan,'payload-bindings.json':{'runtime':'abc'},
                'terminal.json':{'run_id':plan['run_id'],'outcome':'failed','contains_evaluator_truth':False,
                    'phase':'full-gradient-step','error_type':'RuntimeError','error_message':'fixture failure'},
                'worker/rank-0-reservation.json':reservation}
            def archive():
                raw={name:json.dumps(value).encode() for name,value in values.items()}
                manifest={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'members':[
                    {'path':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()} for name,content in raw.items()]}
                path=root/'result.zip'
                with zipfile.ZipFile(path,'w') as stream:
                    stream.writestr('manifest.json',json.dumps(manifest))
                    for name,content in raw.items():stream.writestr(name,content)
                return path
            def read_fixture():
                with patch('tools.stage_nvarc_qwen3_packed_step.preflight',return_value={'offline_package_verified':True}):
                    return verify_packed_step(archive(),package)
            proof=read_fixture()
            self.assertEqual(proof['reserved_training_ranks'],[0])
            self.assertEqual(proof['outcome'],'failed')
            self.assertNotIn('actual_original_family_full_gradient_step_observed',proof)
            reservation['input_tokens_reserved']=127
            with self.assertRaises(ValidationError):read_fixture()
            reservation['input_tokens_reserved']=128;reservation['optimizer_steps_reserved']=True
            with self.assertRaises(ValidationError):read_fixture()

    def test_full_gradient_stage_refuses_queued_numeric_prerequisite(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)/'nvarc-original-qwen3-probe-001'
            (folder/'execution-final').mkdir(parents=True)
            (folder/'execution-final/execution-ledger.json').write_text(json.dumps({
                'run_id':folder.name,'owner_decision':'Decision 0054','accepted':True,'push_reserved':1,
                'retrieval_reserved':0,'provider_version':1,'last_status':'QUEUED','terminal_observed':False}),encoding='utf-8')
            with self.assertRaises(ValidationError):prerequisite(folder)

    def test_full_gradient_stage_refuses_failed_retrieved_numeric_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)/'nvarc-original-qwen3-probe-001'
            (folder/'execution-final').mkdir(parents=True);(folder/'package-l4').mkdir()
            (folder/'execution-final/execution-ledger.json').write_text(json.dumps({
                'run_id':folder.name,'owner_decision':'Decision 0054','accepted':True,'push_reserved':1,
                'retrieval_reserved':1,'provider_version':1,'terminal_observed':True,'events':[{'outcome':'retrieved'}]}),encoding='utf-8')
            (folder/'package-l4/plan.json').write_text(json.dumps({'format':'irisx/nvarc-original-qwen3-probe-v1'}),encoding='utf-8')
            with patch('tools.stage_nvarc_qwen3_packed_step.verify',return_value={
                    'outcome':'failed','tiny_gradient_differential_observed':True}):
                with self.assertRaises(ValidationError):prerequisite(folder)

    def test_static_recovery_requires_exact_response_and_exposure(self):
        binding={'member':'outputs/data-00000.parquet','row':0,'completion_sha256':'abc',
            'code_sha256':'def','parent_ids':['public','protected'],'exposure_tags':['evaluation'],
            'filtered':False,'program_semantics_verified':False}
        observed={'state':'one-argument-contract','imports':['numpy'],'positional_parameters':['grid']}
        self.assertEqual(carry_observation({**binding,**observed},binding),observed)
        for key,value in (('completion_sha256','foreign'),('exposure_tags',[]),('row',1),('filtered',True)):
            with self.subTest(key=key),self.assertRaises(ValidationError):
                carry_observation({**binding,**observed,key:value},binding)
        with self.assertRaises(ValidationError):carry_observation({**binding,'state':'dynamic-success'},binding)

    def test_physical_slices_keep_whole_ordered_source_rows_and_lineage(self):
        rows=[{'input_ids':[14]+[n]*length+[15],'labels':[-100]+[n]*length+[15],
            'parents':['public-parent',str(n)],'exposure':['evaluation']} for n,length in ((1,15),(2,9),(3,7))]
        original=pack_sequences(rows,capacity=256)[0];before=copy.deepcopy(original)
        pieces=execution_slices(original,20)
        self.assertEqual(original,before)
        self.assertEqual([p['input_tokens'] for p in pieces],[17,20])
        self.assertEqual([i for p in pieces for i in p['execution_slice']['logical_segment_indices']],[0,1,2])
        self.assertEqual(sum(p['supervised_tokens'] for p in pieces),original['supervised_tokens'])
        for piece in pieces:
            validate_pack(piece)
            self.assertEqual(piece['execution_slice']['logical_pack_digest'],digest_value(original))
            for segment in piece['segments']:
                reference=original['segments'][segment['row_index']]
                self.assertEqual(segment['sequence_digest'],reference['sequence_digest'])
                self.assertEqual(segment['lineage'],reference['lineage'])
                for key in ('input_ids','labels','position_ids','attention_mask'):
                    self.assertEqual(piece[key][segment['start']:segment['end']],
                        original[key][reference['start']:reference['end']])
        for invalid in (16,True,0):
            with self.assertRaises(ValidationError):execution_slices(original,invalid)

    def test_legacy_and_modern_rotary_config_require_same_original_value(self):
        config={'model_type':'qwen3','vocab_size':16,'num_hidden_layers':36,'hidden_size':2560,
            'num_attention_heads':32,'num_key_value_heads':8,'head_dim':128,'intermediate_size':9728,
            'tie_word_embeddings':True,'attention_dropout':0}
        check_architecture({**config,'rope_theta':5000000})
        check_architecture({**config,'rope_parameters':{'rope_theta':5000000,'rope_type':'default'}})
        for params in ({'rope_theta':1000000,'rope_type':'default'},{'rope_theta':5000000,'rope_type':'dynamic'}):
            with self.assertRaises(ValidationError):check_architecture({**config,'rope_parameters':params})

    def test_static_source_entry_contract_never_executes_host_code(self):
        code="raise RuntimeError('must never run on host')\ndef generate_puzzle_output(grid):\n return grid"
        self.assertEqual(inspect_program(code,'generate_puzzle_output')['state'],'one-argument-contract')
        wrong='def generate_puzzle_output(grid,shape):\n return grid'
        self.assertEqual(inspect_program(wrong,'generate_puzzle_output')['state'],'one-argument-rejected')
        self.assertEqual(inspect_program('def broken(', 'generate_puzzle_output')['state'],'python-syntax-rejected')
        self.assertEqual(inspect_program('async def generate_puzzle_output(grid):\n return grid',
            'generate_puzzle_output')['state'],'async-entry')

    def test_source_pair_contract_rejects_boolean_ragged_and_short_data(self):
        pairs=[{'input':[[i%10,(i+1)%10]],'output':[[(i+2)%10,(i+3)%10]]} for i in range(12)]
        # Independent predicate accepts variety, making schema/color checks
        # independently observable instead of duplicating source validation.
        self.assertEqual(inspect_pairs(pairs,lambda grids:True)['issues'],[])
        for grid in ([[True,1]],[[1,2],[3]]):
            changed=[{**row,'input':grid} for row in pairs]
            self.assertIn('input-grid-contract',inspect_pairs(changed,lambda grids:True)['issues'])
        self.assertIn('below-source-minimum-twelve-pairs',inspect_pairs(pairs[:11],lambda grids:True)['issues'])
        self.assertEqual(inspect_pairs({'input':[[0]]},lambda grids:True)['issues'],['pair-schema'])

    def test_closed_failure_evidence_and_rehashed_cost_attack(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);package=root/'package';package.mkdir()
            plan={'run_id':'nvarc-original-qwen3-probe-001','maximum_outer_forwards':13,
                'maximum_input_tokens':344,'actual_model_input_tokens_per_pass':100}
            for name,value in [('plan.json',plan),('samples.json',[]),('stage-summary.json',{'payload_sha256':{'runtime':'abc'}})]:
                (package/name).write_text(json.dumps(value),encoding='utf-8')
            values={'plan.json':plan,'payload-bindings.json':{'runtime':'abc'},
                'terminal.json':{'run_id':plan['run_id'],'outcome':'failed','phase':'model-probe',
                    'error_type':'RuntimeError','error_message':'native backend unavailable','contains_evaluator_truth':False},
                'worker/worker-ledger.json':[{'stage':'tiny-independent-gradients','reserved_forwards':2,
                    'reserved_input_tokens':22,'cumulative_forwards':2,'cumulative_input_tokens':22}]}
            def write():
                raw={name:json.dumps(value).encode() for name,value in values.items()}
                manifest={'run_id':plan['run_id'],'plan_digest':digest_value(plan),'members':[
                    {'path':name,'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()} for name,value in raw.items()]}
                path=root/'result.zip'
                with zipfile.ZipFile(path,'w') as archive:
                    archive.writestr('manifest.json',json.dumps(manifest))
                    for name,value in raw.items():archive.writestr(name,value)
                return path
            proof=verify(write(),package)
            self.assertEqual(proof['reserved_outer_forwards'],2)
            self.assertEqual(proof['outcome'],'failed')
            # The attacker recomputes every ZIP digest, so rejection must come
            # from the independently reconstructed cost prefix.
            values['worker/worker-ledger.json'][0]['cumulative_forwards']=1
            with self.assertRaises(ValidationError):verify(write(),package)
            values['worker/worker-ledger.json'][0]['cumulative_forwards']=2
            values['payload-bindings.json']['runtime']='foreign'
            with self.assertRaises(ValidationError):verify(write(),package)


if __name__=='__main__':unittest.main()
