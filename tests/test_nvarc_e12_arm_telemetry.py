"""CPU regressions for the observed E12 second-arm telemetry collision.

Use the real E12 admission wrapper, native solve_test and PhaseTelemetry.
Literal empty source views avoid model/vendor imports or numerical claims.
"""
import copy
import contextlib
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from tools import nvarc_e12_answer_evidence as evidence
from tools import nvarc_e12_runtime as runtime
from tools import nvarc_native_multitask as native
from tools.nvarc_public_eval import PhaseTelemetry


CHALLENGES={'synthetic':{'train':[{'input':[[1]],'output':[[1]]}],
    'test':[{'input':[[1]]},{'input':[[2]]}]}}


def solve_literal(collector,arm_id,index,*,fail=False):
    bound=dict(run_id=runtime.RUN_ID,task_id='synthetic',
        task_digest=native.digest(CHALLENGES['synthetic']),challenges_digest=native.digest(CHALLENGES),
        **runtime.arm_contract(arm_id))
    allocation=runtime.paired_allocation(bound,index,0.,1000.)
    counts={'generation':0,'verification':0}
    adapter=NS(telemetry=collector,generation_deadline=120.,verification_deadline=150.,
        reserved=dict(counts),completed=dict(counts),input_by_phase=dict(counts),
        completed_input_by_phase=dict(counts))
    # Only the source view boundary is replaced. The actual lifecycle,
    # accounting, terminal event and E12 deadline admission all execute.
    with patch.object(native,'test_views',return_value=('synthetic',None,NS(keys=[]),None,[]),
            side_effect=RuntimeError('literal source failure') if fail else None):
        return evidence.solve_test(CHALLENGES,'synthetic',index,None,None,NS(score_kgmon=lambda _:[]),
            None,adapter,maximum_candidates=64,emit=lambda *_a,**_k:None,
            test_allocation=allocation,arm_id=arm_id)


class ArmTelemetryTests(unittest.TestCase):
    def run_pair(self,order):
        snapshots={};answers={};collectors=[]
        for arm_id in order:
            with runtime.arm_inference_telemetry(snapshots,arm_id) as collector:
                collectors.append(collector)
                answers[arm_id]={'tests':[solve_literal(collector,arm_id,i) for i in range(2)]}
        return snapshots,answers,collectors

    def test_frozen_v10_shared_collector_reproduces_observed_exception(self):
        collector=PhaseTelemetry()
        first=solve_literal(collector,'ttt64',0)
        self.assertEqual(first['telemetry']['termination_reason'],'all_source_batches_completed')
        with self.assertRaisesRegex(RuntimeError,'one telemetry lifecycle per test required'):
            solve_literal(collector,'ttt128',0)
        self.assertEqual(set(collector.tests),{'0'})

    def test_each_arm_order_reuses_test_indexes_with_distinct_collectors(self):
        for order in (runtime.ARMS,tuple(reversed(runtime.ARMS))):
            with self.subTest(order=order):
                snapshots,answers,collectors=self.run_pair(order)
                self.assertIsNot(collectors[0],collectors[1])
                runtime.verify_inference_telemetry(runtime.inference_telemetry_result(snapshots),answers)
                for arm_id in runtime.ARMS:
                    self.assertEqual(set(snapshots[arm_id]['tests']),{'0','1'})
                    self.assertIsNone(snapshots[arm_id]['inclusive_host_seconds']['training'])
                    self.assertIsNotNone(snapshots[arm_id]['inclusive_host_seconds']['parse_dedup'])

    def test_same_arm_duplicate_test_still_fails_and_retains_snapshot(self):
        snapshots={}
        with self.assertRaisesRegex(RuntimeError,'one telemetry lifecycle per test required'):
            with runtime.arm_inference_telemetry(snapshots,'ttt64') as collector:
                solve_literal(collector,'ttt64',0)
                solve_literal(collector,'ttt64',0)
        self.assertEqual(set(snapshots['ttt64']['tests']),{'0'})
        with self.assertRaisesRegex(RuntimeError,'one inference telemetry collector per E12 arm'):
            with runtime.arm_inference_telemetry(snapshots,'ttt64'):
                self.fail('same arm collector must not restart')

    def test_source_failure_retains_arm_snapshot_and_propagates_error(self):
        snapshots={}
        with self.assertRaisesRegex(RuntimeError,'literal source failure'):
            with runtime.arm_inference_telemetry(snapshots,'ttt128') as collector:
                solve_literal(collector,'ttt128',0,fail=True)
        self.assertEqual(snapshots['ttt128']['tests']['0']['termination_reason'],'exception:RuntimeError')
        self.assertEqual(snapshots['ttt128']['events'],[
            {'event':'phase_exception','phase':'parse_dedup','type':'RuntimeError'}])

    def test_completed_first_arm_snapshot_is_detached_from_later_mutation(self):
        snapshots={}
        with runtime.arm_inference_telemetry(snapshots,'ttt64') as first:
            solve_literal(first,'ttt64',0)
        saved=native.canonical(snapshots['ttt64'])
        with runtime.arm_inference_telemetry(snapshots,'ttt128') as second:
            solve_literal(second,'ttt128',0)
        self.assertEqual(native.canonical(snapshots['ttt64']),saved)
        first.tests['0']['counters']['processed']=99
        self.assertEqual(native.canonical(snapshots['ttt64']),saved)
        result=runtime.inference_telemetry_result(snapshots)
        snapshots['ttt64']['tests']['0']['counters']['processed']=42
        self.assertEqual(native.canonical(result['arms']['ttt64']),saved)

    def test_exported_checkpoint_telemetry_must_match_each_arm_exactly(self):
        snapshots,answers,_=self.run_pair(runtime.ARMS)
        value=runtime.inference_telemetry_result(snapshots)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for arm_id,answer in answers.items():
                native.write(root/(arm_id+'.json'),answer)
            exported={a:json.loads((root/(a+'.json')).read_bytes()) for a in runtime.ARMS}
            runtime.verify_inference_telemetry(value,exported)
            exported['ttt128']['tests'][0]['telemetry']['counters']['processed']=1
            with self.assertRaisesRegex(RuntimeError,'independently replayed checkpoint'):
                runtime.verify_inference_telemetry(value,exported)

    def test_actual_native_caught_limits_remain_valid_arm_telemetry(self):
        for reason in ('forward_limit','input_token_limit','inference_deadline'):
            with self.subTest(reason=reason):
                snapshots={};answers={}
                for arm in runtime.ARMS:
                    with runtime.arm_inference_telemetry(snapshots,arm) as collector:
                        bound=dict(run_id=runtime.RUN_ID,task_id='synthetic',
                            task_digest=native.digest(CHALLENGES['synthetic']),
                            challenges_digest=native.digest(CHALLENGES),**runtime.arm_contract(arm))
                        allocation=runtime.paired_allocation(bound,0,0.,1000.)
                        counts={'generation':0,'verification':0}
                        adapter=NS(telemetry=collector,generation_deadline=120.,verification_deadline=150.,
                            reserved=dict(counts),completed=dict(counts),input_by_phase=dict(counts),
                            completed_input_by_phase=dict(counts),scope=lambda _:contextlib.nullcontext())
                        views=NS(keys=['view'],get=lambda *_:{'input':'x'})
                        def limited(*_):raise native.InferenceLimitReached(reason)
                        solver=NS(inference_turbo_dfs=limited,turbo_dfs=lambda:None)
                        with patch.object(native,'test_views',return_value=('synthetic',None,views,None,[['view']])), \
                             patch.object(native.time,'time',return_value=0.):
                            answer=evidence.solve_test(CHALLENGES,'synthetic',0,None,solver,
                                NS(score_kgmon=lambda _:[]),NS(encode=lambda _:[1]),adapter,
                                maximum_candidates=64,emit=lambda *_a,**_k:None,
                                test_allocation=allocation,arm_id=arm)
                        self.assertEqual(answer['termination_reason'],reason)
                        answers[arm]={'tests':[answer]}
                value=runtime.inference_telemetry_result(snapshots)
                runtime.verify_inference_telemetry(value,answers)
                self.assertEqual(value['arms']['ttt64']['events'],[
                    {'event':'phase_exception','phase':'generation','type':'InferenceLimitReached'}])
                bad=copy.deepcopy(value);bad['arms']['ttt64']['events'][0]['type']='RuntimeError'
                with self.assertRaisesRegex(RuntimeError,'cooperative inference guard'):
                    runtime.verify_inference_telemetry(bad,answers)
                bad=copy.deepcopy(value);bad['arms']['ttt64']['events']*=2
                with self.assertRaisesRegex(RuntimeError,'cooperative inference guard'):
                    runtime.verify_inference_telemetry(bad,answers)

    def test_unknown_fields_or_impossible_phase_partition_are_rejected(self):
        snapshots,answers,_=self.run_pair(runtime.ARMS)
        value=runtime.inference_telemetry_result(snapshots)
        def added(value):value['arms']['ttt64']['inference_arms']={}
        def overlap(value):value['arms']['ttt64']['exclusive_host_seconds']['parse_dedup']=1e30
        def training(value):
            value['arms']['ttt64']['inclusive_host_seconds']['training']=0.
            value['arms']['ttt64']['exclusive_host_seconds']['training']=0.
        def missing(value):del value['arms']['ttt128']
        for mutate in (added,overlap,training,missing):
            with self.subTest(mutation=mutate.__name__):
                invalid=copy.deepcopy(value);mutate(invalid)
                with self.assertRaises(RuntimeError):runtime.verify_inference_telemetry(invalid,answers)


class WorkerTelemetryTests(unittest.TestCase):
    """Run the real worker orchestration around literal CPU training/inference.

    Only model/preparation boundaries are faked; the worker must pass distinct
    collectors into the real solver lifecycle and export each arm's evidence.
    """
    def run_worker(self,rank,*,fail_second=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'workers'/str(rank);output.mkdir(parents=True)
            (root/'materials').mkdir()
            material={'rows':[{'literal':i} for i in range(128)],'texts':['literal']*128}
            challenges={key:copy.deepcopy(CHALLENGES['synthetic']) for key in runtime.TASK_COUNTS}
            native.write(root/'challenges.json',challenges)
            plan=dict(screen_id=runtime.RUN_ID,task_order=list(runtime.TASK_COUNTS),
                model_material_digest=native.digest('literal-model'),arm_order=runtime.counterbalanced_order(runtime.TASK_COUNTS),
                task_specs={key:dict(expected_rows_digest=native.digest(material['rows']),
                    texts_digest=native.digest(material['texts'])) for key in runtime.TASK_COUNTS},
                native_source_learning_rates=[],reset_reserve_seconds=360,maximum_training_seconds=1200,
                maximum_worker_cuda_allocated_bytes=1,maximum_worker_host_rss_bytes=10**12)
            for key in runtime.TASK_COUNTS:native.write(root/'materials'/f'{key}.json',material)
            engines=[];trainers=[];answers={};collectors=[]
            class Engine:
                def __init__(self,*_args):
                    engines.append(self);self.changed=False;self.updates=0;self.rng=0
                    self.loader=self.tokenizer=None;self.dependency=root
                    self.model=NS(parameters=lambda:[],zero_grad=lambda **_k:None)
                    self.torch=NS(cuda=NS(empty_cache=lambda:None,max_memory_allocated=lambda:0))
                    self.baseline=self.inventory();self.initial_control={};self.adapter(None)
                    native.write(output/'ready.json',{})
                def inventory(self):return [{'literal':i,'changed':self.changed} for i in range(506)]
                def restore(self):self.changed=False
                def inference(self):pass
                def trainer(self,_texts,_rows,path):
                    limit=runtime.arm_contract(path.name)['training_updates']
                    def train():self.changed=True;self.updates+=limit
                    trainer=NS(train=train,optimizer=None,lr_scheduler=None,args=NS(),
                        accelerator=NS(_optimizers=[],_schedulers=[]))
                    trainers.append(trainer);return trainer
            class Budget:
                def __init__(self,engine,trainer,*args):
                    self.trainer=trainer;self.optimizer=None;self.output=Path(args[-3])
                def complete(self):return []
                def finish(self):
                    native.write(self.output/'prefix-contract.json',{})
                    native.write(self.output/'prefix-trace.json',{})
                    return {}
            def solve(_engine,_root,_plan,_rank,_deadline,collector,**kwargs):
                arm_id=kwargs['arm_id'];collectors.append(collector)
                answer={'tests':[solve_literal(collector,arm_id,i,
                    fail=fail_second and len(collectors)==2 and i==1) for i in range(2)]}
                native.write(kwargs['directory']/'answer-checkpoint.json',answer)
                answers[arm_id]=answer
                return answer
            with contextlib.ExitStack() as stack:
                patches={
                    'NativeEngine':Engine,'PrefixBudget':Budget,'profile_for_plan':lambda _:None,
                    'install_owner_guard':lambda *_a:None,'require_worker_receipt':lambda *_a:None,
                    'control_adapter':lambda *_a:NS(),'public_training_material':lambda *_a:material,
                    'native_schedule':lambda *_a:([],{}),'training_sources':lambda *_a:{},
                    'capture_rng':lambda e:e.rng,'restore_rng':lambda e,v:setattr(e,'rng',v),
                    'rng_observation':lambda v:{'literal':v},'model_metadata':lambda _m:{},
                    'verify_model_metadata':lambda *_a:None,'unchanged_model_layout':lambda *_a:None,
                    'training_deadline':lambda *_a:contextlib.nullcontext(),'reset_control':lambda *_a:{}}
                for name,value in patches.items():stack.enter_context(patch.object(runtime,name,value))
                stack.enter_context(patch.object(runtime.native_training,'preparation_guard',
                    side_effect=lambda *_a:contextlib.nullcontext(lambda:None)))
                stack.enter_context(patch.object(runtime.native_training,'wait_for_release',return_value=None))
                stack.enter_context(patch.object(runtime.native_training,'changed_tensors',return_value=506))
                stack.enter_context(patch.object(runtime.native_epoch,'inference_transition'))
                stack.enter_context(patch.object(runtime.prefix,'validate_pair'))
                stack.enter_context(patch.object(evidence,'solve_task',side_effect=solve))
                rc=runtime.worker(root,root,root,rank,time.time()+2500,os.getpid(),
                    runtime_api=NS(verify_runtime=lambda *_a,**_k:plan),
                    expected_plan_sha256=native.digest(plan).removeprefix('sha256:'))
            result=json.loads((output/'result.json').read_bytes())
            exported={a:json.loads((output/'arms'/a/'answer-checkpoint.json').read_bytes()) for a in answers}
            return rc,result,exported,engines,trainers,collectors

    def test_real_worker_reaches_second_arm_with_fresh_collector_in_both_orders(self):
        for rank in (1,2):
            with self.subTest(rank=rank):
                rc,result,answers,engines,trainers,collectors=self.run_worker(rank)
                self.assertEqual(rc,0,result['errors'])
                self.assertEqual(len(engines),1);self.assertEqual(len(trainers),2)
                self.assertEqual(engines[0].updates,192);self.assertFalse(engines[0].changed)
                self.assertIsNot(collectors[0],collectors[1])
                self.assertEqual(result['telemetry']['tests'],{})
                self.assertIsNone(result['telemetry']['inclusive_host_seconds']['parse_dedup'])
                self.assertIsNotNone(result['telemetry']['inclusive_host_seconds']['training'])
                runtime.verify_inference_telemetry(result['inference_telemetry'],answers)

    def test_worker_failure_exports_second_arm_snapshot_without_mutating_first(self):
        rc,result,answers,engines,trainers,collectors=self.run_worker(2,fail_second=True)
        self.assertEqual(rc,1);self.assertEqual(len(engines),1);self.assertFalse(engines[0].changed)
        self.assertEqual(result['arms']['ttt64']['status'],'complete')
        self.assertEqual(result['arms']['ttt128']['status'],'failed')
        self.assertTrue(result['arms']['ttt128']['baseline_restored'])
        saved=result['inference_telemetry']['arms']
        self.assertEqual(saved['ttt128']['tests']['1']['termination_reason'],'exception:RuntimeError')
        self.assertEqual(saved['ttt64']['tests'],{str(i):t['telemetry'] for i,t in enumerate(answers['ttt64']['tests'])})
        self.assertEqual(saved['ttt64']['events'],[])


if __name__=='__main__':unittest.main()
