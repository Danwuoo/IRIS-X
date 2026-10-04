"""Offline multi-test evidence acceptance. Tiny CPU and injected work are labeled."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import nvarc_native_multitask as runtime
from tools import nvarc_native_submission as bridge
from tools import stage_nvarc_native_multitask as stage
from tools.nvarc_native_solve_runtime import load_sources, InferenceLimitReached

try:
    import numpy as np
    import torch
    from tokenizers import Tokenizer
    ML=True
except ImportError:
    ML=False


@unittest.skipUnless(ML,'optional offline tiny ML/native source material')
class MultiTaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not stage.MODEL.exists():raise unittest.SkipTest('retained native materials unavailable')
        cls.original_plan,cls.raw,_,_=stage.construct('nvarc-original-qwen3-native-multitask-990')
        cls.temp=tempfile.TemporaryDirectory(prefix='iris-multitask-tests-')
        cls.directory=Path(cls.temp.name)
        for name,key in stage.FILES.items():
            path=cls.directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(cls.raw[key])
        cls.loader,cls.solver,cls.decoder=load_sources(cls.directory,torch,np)
        tok=Tokenizer.from_file(str(stage.MODEL/'model/tokenizer.json'))
        class Tokens:
            def encode(self,text):return tok.encode(text).ids
            def decode(self,ids):return tok.decode(ids,skip_special_tokens=False)
        cls.tokenizer=Tokens()
        cls.challenges={'a':{'train':[{'input':[[1]],'output':[[2]]},{'input':[[3]],'output':[[4]]}],
                             'test':[{'input':[[5]]},{'input':[[6,7]]}]},
                        'b':{'train':[{'input':[[1,2]],'output':[[2,1]]}], 'test':[{'input':[[8]]}]}}
        cls.plan=copy.deepcopy(cls.original_plan)
        cls.plan.update(task_order=['a','b'],challenges_digest=runtime.digest(cls.challenges),
                        task_specs={'a':cls.original_plan['task_specs'][stage.TASKS[0]],
                                    'b':cls.original_plan['task_specs'][stage.TASKS[1]]})
        cls.threads=torch.get_num_threads();torch.set_num_threads(1)
        # A real learned tiny torch model, with no attention/cache semantics.
        # Its generated tokens and verifier scores are real; GPU/Unsloth claims
        # and Qwen quality claims are never inferred from this transition model.
        class Tiny(torch.nn.Module):
            def __init__(self):
                super().__init__();self.embedding=torch.nn.Embedding(16,8);self.head=torch.nn.Linear(8,16)
            @property
            def device(self):return self.embedding.weight.device
            def forward(self,input_ids,**kw):
                return SimpleNamespace(logits=self.head(self.embedding(input_ids)),past_key_values=object())
        torch.manual_seed(909);cls.model=Tiny()
        optimizer=torch.optim.AdamW(cls.model.parameters(),lr=.06)
        ids=torch.tensor([[10,0]]);labels=torch.tensor([[0,15]])
        for _ in range(120):
            optimizer.zero_grad();loss=torch.nn.functional.cross_entropy(cls.model(ids).logits.flatten(0,1),labels.flatten())
            loss.backward();optimizer.step()
        cls.model.eval()
        cls.evidence,cls.results=cls.produce()

    @classmethod
    def tearDownClass(cls):
        torch.set_num_threads(cls.threads);cls.temp.cleanup()

    @classmethod
    def produce(cls,*,fail_test=None,injected=False,candidate_mode=None):
        output=[];results=[]
        for task_id in cls.challenges:
            directory=Path(tempfile.mkdtemp(dir=cls.directory));binding=bridge.task_binding(cls.plan,cls.challenges,task_id)
            events=runtime.Events(directory/'events.jsonl',binding)
            spec=cls.plan['task_specs'][task_id]
            adapter=runtime.EvidenceModel(cls.model,torch,events.emit,forward_limits=spec['inference_forward_limits'],
                input_token_limit=spec['maximum_inference_input_tokens'],generation_deadline=time.time()+60,
                per_test_limits=spec['per_test_limits'])
            checkpoint_value=None
            def checkpoint(tests):
                nonlocal checkpoint_value
                checkpoint_value={'binding':binding,'tests':copy.deepcopy(tests),
                    'event_count':events.sequence,'event_head':events.head}
            solver=cls.solver
            if injected:
                # Exercise inverse/dedup and real verifier NLLs, but explicitly
                # identify candidates as injected. No native model provenance.
                def fake(model,prefixes,*args):
                    ids=torch.tensor(prefixes)
                    model(input_ids=ids,use_cache=True)
                    return [(0,[(.2,[0,15]),(.3,[0,15])]),(1,[(.4,[1,15])])]
                solver=SimpleNamespace(inference_turbo_dfs=fake,calc_scores=cls.solver.calc_scores,
                                       turbo_dfs=cls.solver.turbo_dfs)
            def solve(i):
                if fail_test==(task_id,i):raise RuntimeError('injected downstream failure')
                active_solver=solver
                if candidate_mode is not None:
                    _,_,_,_,batches=runtime.test_views(cls.challenges,task_id,i,cls.loader,cls.tokenizer)
                    cursor=0
                    def scripted(model,prefixes,*args):
                        nonlocal cursor
                        model(input_ids=torch.tensor(prefixes),use_cache=True)
                        batch=batches[cursor];cursor+=1
                        if candidate_mode=='empty':return []
                        rows=[]
                        for n,key in enumerate(batch):
                            a=cls.loader.ArcDataset.forward_mod(np.array([[2]]),key)
                            tokens=cls.tokenizer.encode(cls.loader.QwenFormatter(cls.tokenizer).fmt_reply([a.tolist()]))
                            rows.append((n,[(.2,tokens)]))
                        return rows
                    active_solver=SimpleNamespace(inference_turbo_dfs=scripted,calc_scores=cls.solver.calc_scores,
                        turbo_dfs=cls.solver.turbo_dfs)
                return runtime.solve_test(cls.challenges,task_id,i,cls.loader,active_solver,cls.decoder,cls.tokenizer,adapter,
                    maximum_candidates=64,emit=events.emit)
            tests,failure=runtime.run_task_tests(cls.challenges,task_id,solve,checkpoint)
            logs=[json.loads(line) for line in (directory/'events.jsonl').read_bytes().splitlines()]
            output.append({'task_id':task_id,'binding':binding,'checkpoint':checkpoint_value,'events':logs,
                'receipt':{'task_id':task_id,'attempt_id':task_id,'status':'failed' if failure else 'complete',
                           'launched':True,'reset_inferred':False},'ledger_truncated':False,
                'provenance':'injected-fixture' if injected or candidate_mode is not None else 'tiny-cpu-model'})
            results.append(tests)
        return output,results

    def export(self,evidence=None,plan=None):
        return bridge.build_native_submission(self.challenges,plan or self.plan,evidence or self.evidence,
            self.directory,self.tokenizer,allow_fixture=True)

    @staticmethod
    def rechain(data):
        previous=runtime.digest(data['binding'])
        for i,row in enumerate(data['events']):
            row.update(sequence=i,previous=previous);row.pop('digest',None)
            row['digest']=runtime.digest(row);previous=row['digest']
        cp=data['checkpoint'];cp['event_head']=data['events'][cp['event_count']-1]['digest']

    def test_real_tiny_generation_nonempty_original_inverse_dedup_rank_export(self):
        submission,audit=self.export()
        self.assertEqual((audit['task_count'],audit['test_output_count']),(2,3))
        self.assertTrue(all(t['ranked_grids'] for task in self.results for t in task))
        self.assertTrue(all(len(t['ranked_grids'])==len({runtime.grid_key(g) for g in t['ranked_grids']}) for task in self.results for t in task))
        self.assertEqual(len(submission['a']),2)
        self.assertTrue(all(s in {'tiny_cpu_model','filler'} for r in audit['rows'] for s in r['attempt_sources']))
        self.assertFalse(audit['digest_is_execution_attestation'])

    def test_multi_test_source_ids_preserve_one_not_fake_zero(self):
        starts=[e for e in self.evidence[0]['events'] if e['event']=='test_started']
        self.assertEqual([e['base_key'] for e in starts],['a_0','a_1'])
        self.assertTrue(all(k.startswith('a_1.') for k in starts[1]['source_views']))

    def test_injected_candidates_have_distinct_provenance_and_cannot_enter_strict_route(self):
        evidence,_=self.produce(injected=True);_,audit=self.export(evidence)
        self.assertTrue(any('injected_fixture' in row['attempt_sources'] for row in audit['rows']))
        with self.assertRaisesRegex(RuntimeError,'provenance'):
            bridge.build_native_submission(self.challenges,self.plan,evidence,self.directory,self.tokenizer)

    def test_tiny_cpu_model_cannot_establish_native_gpu_provenance(self):
        with self.assertRaisesRegex(RuntimeError,'provenance'):
            bridge.build_native_submission(self.challenges,self.plan,self.evidence,self.directory,self.tokenizer)

    def test_caller_cannot_relabel_cpu_evidence_as_native_without_hardware_and_ttt(self):
        evidence=copy.deepcopy(self.evidence)
        for data in evidence:
            data['provenance']='native-model';data['receipt']['returncode']=0
        with self.assertRaisesRegex(RuntimeError,'native hardware/training'):
            bridge.build_native_submission(self.challenges,self.plan,evidence,self.directory,self.tokenizer)

    def test_one_candidate_native_complete_keeps_model_slot_distinct_from_duplicate_filler(self):
        evidence,results=self.produce(candidate_mode='single');submission,audit=self.export(evidence)
        self.assertTrue(all(t['native_complete'] and t['status']=='missing-candidate' for task in results for t in task))
        self.assertTrue(all(row['supplied_attempts']==1 and row['attempt_sources']==['injected_fixture','filler'] and
                            row['fill_policy']=='duplicate_first' for row in audit['rows']))
        self.assertTrue(all(t['attempt_1']==t['attempt_2'] for tests in submission.values() for t in tests))

    def test_empty_dfs_keeps_all_source_views_and_constant_filler(self):
        evidence,results=self.produce(candidate_mode='empty');_,audit=self.export(evidence)
        self.assertTrue(all(t['completed_generation_batches']==4 and not t['native_complete'] for task in results for t in task))
        self.assertEqual(audit['model_attempt_slots_missing'],6)
        self.assertTrue(all(r['fill_policy']=='constant_zero_1x1' for r in audit['rows']))

    def test_unknown_evaluator_fields_fail_closed_even_if_rehashed(self):
        evidence=copy.deepcopy(self.evidence);data=evidence[0];data['events'][0]['answer_key']=[[1]]
        self.rechain(data)
        with self.assertRaisesRegex(RuntimeError,'unknown/evaluator'):self.export(evidence)

    def test_partial_completion_then_failure_retains_all_tests_and_second_task(self):
        evidence,_=self.produce(fail_test=('a',1));submission,audit=self.export(evidence)
        self.assertEqual(len(submission['a']),2);self.assertEqual(audit['test_output_count'],3)
        self.assertGreater(audit['rows'][0]['supplied_attempts'],0)
        self.assertEqual(audit['rows'][1]['attempt_sources'],['filler','filler'])
        self.assertGreater(audit['rows'][2]['supplied_attempts'],0)
        self.assertEqual(audit['rows'][0]['input_task_status'],'failed')

    def test_killed_worker_can_keep_only_earlier_committed_test(self):
        evidence=copy.deepcopy(self.evidence);a=evidence[0]
        terminal=next(e for e in a['events'] if e['event']=='test_terminal')
        n=terminal['sequence']+1;a['events']=a['events'][:n]
        a['checkpoint']['tests'][1]={'test_index':1,'status':'not_executed','attempts':[],'missing_attempts':2}
        a['checkpoint'].update(event_count=n,event_head=a['events'][-1]['digest'])
        a['receipt']['status']='worker_crash'
        _,audit=self.export(evidence)
        self.assertGreater(audit['rows'][0]['supplied_attempts'],0)
        self.assertEqual(audit['rows'][1]['supplied_attempts'],0)
        self.assertFalse(a['receipt']['reset_inferred'])

    def test_undispatched_tasks_and_tests_remain_in_denominator(self):
        evidence=copy.deepcopy(self.evidence)
        for data in evidence:
            data.update(checkpoint=None,events=[])
            data['receipt'].update(launched=False,status='session_limit')
        _,audit=self.export(evidence)
        self.assertEqual(audit['test_output_count'],3);self.assertEqual(audit['model_attempt_slots_missing'],6)

    def test_producer_program_tamper_rejected(self):
        path=self.directory/'tools/nvarc_native_multitask.py';body=path.read_bytes()
        try:
            path.write_bytes(body+b'\n# altered producer\n')
            with self.assertRaisesRegex(RuntimeError,'program bytes'):self.export()
        finally:path.write_bytes(body)

    def test_chain_tamper_rejected(self):
        evidence=copy.deepcopy(self.evidence);evidence[0]['events'][0]['base_key']='b_0'
        with self.assertRaisesRegex(RuntimeError,'chain/binding'):self.export(evidence)

    def test_rehashed_ranking_inverse_and_verification_tamper_rejected(self):
        for change in ('grid','rank','verification','generation'):
            with self.subTest(change=change):
                evidence=copy.deepcopy(self.evidence);data=evidence[0]
                if change=='grid':
                    e=next(e for e in data['events'] if e['event']=='candidate_ranked');e['candidate_grid']=[[9,9]]
                elif change=='rank':
                    data['checkpoint']['tests'][0]['ranked_grids'].reverse()
                    data['checkpoint']['tests'][0]['attempts']=data['checkpoint']['tests'][0]['ranked_grids'][:2]
                    e=next(e for e in data['events'] if e['event']=='test_terminal');e['result']=copy.deepcopy(data['checkpoint']['tests'][0])
                elif change=='verification':
                    e=next(e for e in data['events'] if e['event']=='verification_observed');e['rows'][0]['score']+=1
                else:
                    e=next(e for e in data['events'] if e['event']=='generation_completed');e['source_result'][0][1][0][0]+=.05
                self.rechain(data)
                with self.assertRaises(RuntimeError):self.export(evidence)

    def test_stale_run_wrong_task_and_duplicate_task_test_rejected(self):
        for change in ('run','task','duplicate-task','duplicate-test'):
            with self.subTest(change=change):
                evidence=copy.deepcopy(self.evidence)
                if change=='run':evidence[0]['binding']['run_id']='different-run'
                elif change=='task':evidence[0]['checkpoint']['tests'][1]['base_key']='a_0'
                elif change=='duplicate-task':evidence[1]=copy.deepcopy(evidence[0])
                else:evidence[0]['checkpoint']['tests'][1]['test_index']=0
                with self.assertRaises(RuntimeError):self.export(evidence)

    def test_evaluator_metadata_rejected_recursively(self):
        for key in ('expected_output','exact_match','evaluator_truth','solutions','correctness_scored'):
            evidence=copy.deepcopy(self.evidence);evidence[0]['events'][0][key]=True
            with self.assertRaisesRegex(RuntimeError,'evaluator|evaluated'):self.export(evidence)

    def test_finite_forward_budget_stops_without_model_entry_and_keeps_denominator(self):
        events=[];adapter=runtime.EvidenceModel(self.model,torch,lambda e,**kw:events.append((e,kw)),
            forward_limits={'control':7,'generation':1,'verification':2},input_token_limit=10000,
            generation_deadline=time.time()+60)
        result=runtime.solve_test(self.challenges,'a',0,self.loader,self.solver,self.decoder,self.tokenizer,adapter,
            maximum_candidates=64,emit=lambda e,**kw:events.append((e,kw)))
        self.assertEqual(result['termination_reason'],'forward_limit')
        self.assertEqual(result['source_view_denominator'],16)
        self.assertEqual(result['unfinished_source_views'],4)
        self.assertEqual(result['undispatched_source_views'],12)
        self.assertEqual(adapter.reserved['generation'],1)

    def test_failure_classification_includes_timeout_oom_interrupt(self):
        for error,status in [(TimeoutError(),'timeout'),(RuntimeError('CUDA out of memory'),'oom'),
                             (KeyboardInterrupt(),'interrupted_pending'),(InferenceLimitReached('forward_limit'),'budget_stop')]:
            self.assertEqual(runtime.failure_status(error),status)

    def test_original_internal_dfs_deadline_is_retained_as_planned_stop(self):
        events=[];deadline=time.time()+60
        adapter=runtime.EvidenceModel(self.model,torch,lambda e,**kw:events.append((e,kw)),
            forward_limits={'control':7,'generation':32,'verification':16},input_token_limit=10000,generation_deadline=deadline)
        class ExpiredSourceClock:
            @staticmethod
            def time():return deadline+1
        namespace=self.solver.turbo_dfs.__globals__
        with patch.dict(namespace,{'time':ExpiredSourceClock}):
            result=runtime.solve_test(self.challenges,'a',0,self.loader,self.solver,self.decoder,self.tokenizer,adapter,
                maximum_candidates=64,emit=lambda e,**kw:events.append((e,kw)))
        self.assertEqual(result['termination_reason'],'source_dfs_deadline')
        self.assertTrue(result['coverage'][0]['source_dfs_deadline_observed'])
        self.assertFalse(result['native_complete']);self.assertFalse(result['search_exhaustiveness_claim'])

    def test_training_rows_are_derived_once_per_task_from_only_public_train(self):
        material=stage.training_material(self.challenges,self.directory,self.tokenizer)
        changed=copy.deepcopy(self.challenges);changed['a']['test'].append({'input':[[9]]})
        changed['a']['test'][0]['input']=[[9,9],[9,9]]
        other=stage.training_material(changed,self.directory,self.tokenizer)
        self.assertEqual(material['a'],other['a'])
        self.assertEqual(len(material['a']['rows']),128)
        self.assertNotEqual(material['a']['rows'],material['b']['rows'])

    def test_second_test_views_match_joint_original_augmentation_rng_stream(self):
        state=np.random.get_state()
        try:
            ds=self.loader.ArcDataset(queries={'a':self.challenges['a']},keys=['a']).split_multi_replies()
            ds=ds.augment(n=2,seed=2).cut_to_len(formatter=self.loader.QwenFormatter(self.tokenizer),name='input',max_len=8192-931)
        finally:np.random.set_state(state)
        _,_,views,_,_=runtime.test_views(self.challenges,'a',1,self.loader,self.tokenizer)
        expected=[k for k in ds.keys if k.split('.')[0]=='a_1']
        self.assertEqual(views.keys,expected)
        self.assertEqual(views.queries,{k:ds.queries[k] for k in expected})

    def test_inert_parent_writes_closed_terminal_zip_before_any_gpu_import(self):
        plan,raw,notebook,_=stage.construct('nvarc-original-qwen3-native-multitask-991')
        with tempfile.TemporaryDirectory() as temp:
            source=''.join(notebook['cells'][0]['source']).replace("Path('/kaggle/working')",'Path('+repr(temp)+')')
            with self.assertRaisesRegex(RuntimeError,'inert package'):
                exec(compile(source,'inert-native-parent','exec'),{'__name__':'inert_test'})
            self.assertTrue((Path(temp)/'結果.zip').is_file())
            terminal=json.loads((Path(temp)/plan['run_id']/'terminal.json').read_bytes())
            self.assertEqual(terminal['outcome'],'failed')
            self.assertEqual(terminal['model_forwards'],0)

    def test_admission_rejects_missing_or_unreconciled_resource_assertions(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'admission.json';path.write_text('{}')
            with self.assertRaises(RuntimeError):stage.admission_for(path,'nvarc-original-qwen3-native-multitask-991')
        self.assertIsNone(stage.admission_for(None,'inert'))

    def test_closed_offline_preflight_and_independent_inert_archive_verifier(self):
        from tools.verify_nvarc_native_multitask import verify
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);package=root/'package'
            checked=stage.stage(package,'nvarc-original-qwen3-native-multitask-992')
            self.assertFalse(checked['approved_for_runtime'])
            notebook=json.loads((package/'kernel/notebook.ipynb').read_bytes())
            source=''.join(notebook['cells'][0]['source']).replace("Path('/kaggle/working')",'Path('+repr(str(root))+')')
            with self.assertRaisesRegex(RuntimeError,'inert package'):exec(compile(source,'inert-archive','exec'),{})
            proof=verify(root/'結果.zip',package)
            self.assertFalse(proof['gpu_validation_gate']);self.assertEqual(proof['outcome'],'failed-before-dispatch')
            nested=package/'nested';nested.mkdir();(nested/'stage-summary.json').write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'closed exact'):stage.preflight(package)

    def test_partial_ledger_tail_does_not_upgrade_reset_or_discard_complete_test(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=copy.deepcopy(self.evidence[0]);directory=root/'tasks/a/native';directory.mkdir(parents=True)
            (directory/'checkpoint.json').write_bytes(runtime.canonical(data['checkpoint']))
            (directory/'events.jsonl').write_bytes(b''.join(runtime.canonical(e)+b'\n' for e in data['events'])+b'{"interrupted')
            receipt=data['receipt'];receipt['status']='worker_crash'
            recovered=bridge.read_task_evidence(root,self.plan,self.challenges,[receipt])
            self.assertTrue(recovered[0]['ledger_truncated'])
            self.assertEqual(recovered[0]['events'],data['events'])
            self.assertEqual(recovered[1]['receipt']['status'],'not_executed')
            self.assertFalse(recovered[0]['receipt']['reset_inferred'])


if __name__=='__main__':unittest.main()
