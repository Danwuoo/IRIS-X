"""CPU regressions for the observed E13 second-arm telemetry collision.

Use the real E13 admission wrapper, native solve_test and PhaseTelemetry.
Literal empty source views avoid model/vendor imports or numerical claims.
"""
from tests.platform_requirements import requires_linux
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

from tools import nvarc_e13_answer_evidence as evidence
from tools import nvarc_native_multitask as native
from tools.nvarc_public_eval import PhaseTelemetry


CHALLENGES={'synthetic':{'train':[{'input':[[1]],'output':[[1]]}],
    'test':[{'input':[[1]]},{'input':[[2]]}]}}


def _load_linux_runtime():
    global runtime
    from tools import nvarc_e13_runtime as runtime

def solve_literal(collector,arm_id,index,*,fail=False):
    bound=dict(run_id=runtime.RUN_ID,task_id='synthetic',
        task_digest=native.digest(CHALLENGES['synthetic']),challenges_digest=native.digest(CHALLENGES),
        **runtime.arm_contract(arm_id))
    allocation=runtime.paired_allocation(bound,index,0.,1000.)
    counts={'generation':0,'verification':0}
    adapter=NS(telemetry=collector,generation_deadline=float(allocation['generation_seconds']),verification_deadline=float(allocation['total_seconds']),
        reserved=dict(counts),completed=dict(counts),input_by_phase=dict(counts),
        completed_input_by_phase=dict(counts))
    # Only the source view boundary is replaced. The actual lifecycle,
    # accounting, terminal event and E13 deadline admission all execute.
    with patch.object(native,'test_views',return_value=('synthetic',None,NS(keys=[]),None,[]),
            side_effect=RuntimeError('literal source failure') if fail else None):
        return evidence.solve_test(CHALLENGES,'synthetic',index,None,None,NS(score_kgmon=lambda _:[]),
            None,adapter,maximum_candidates=64,emit=lambda *_a,**_k:None,
            test_allocation=allocation,arm_id=arm_id)


@requires_linux('Real native runtime imports POSIX resource accounting and Linux owned-process controls')
class ArmTelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _load_linux_runtime()

    def run_pair(self,order):
        snapshots={};answers={};collectors=[]
        for arm_id in order:
            with runtime.arm_inference_telemetry(snapshots,arm_id) as collector:
                collectors.append(collector)
                answers[arm_id]={'tests':[solve_literal(collector,arm_id,i) for i in range(2)]}
        return snapshots,answers,collectors

    def test_frozen_v10_shared_collector_reproduces_observed_exception(self):
        collector=PhaseTelemetry()
        first=solve_literal(collector,'search120',0)
        self.assertEqual(first['telemetry']['termination_reason'],'all_source_batches_completed')
        with self.assertRaisesRegex(RuntimeError,'one telemetry lifecycle per test required'):
            solve_literal(collector,'search240',0)
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
            with runtime.arm_inference_telemetry(snapshots,'search120') as collector:
                solve_literal(collector,'search120',0)
                solve_literal(collector,'search120',0)
        self.assertEqual(set(snapshots['search120']['tests']),{'0'})
        with self.assertRaisesRegex(RuntimeError,'one inference telemetry collector per E13 arm'):
            with runtime.arm_inference_telemetry(snapshots,'search120'):
                self.fail('same arm collector must not restart')

    def test_source_failure_retains_arm_snapshot_and_propagates_error(self):
        snapshots={}
        with self.assertRaisesRegex(RuntimeError,'literal source failure'):
            with runtime.arm_inference_telemetry(snapshots,'search240') as collector:
                solve_literal(collector,'search240',0,fail=True)
        self.assertEqual(snapshots['search240']['tests']['0']['termination_reason'],'exception:RuntimeError')
        self.assertEqual(snapshots['search240']['events'],[
            {'event':'phase_exception','phase':'parse_dedup','type':'RuntimeError'}])

    def test_completed_first_arm_snapshot_is_detached_from_later_mutation(self):
        snapshots={}
        with runtime.arm_inference_telemetry(snapshots,'search120') as first:
            solve_literal(first,'search120',0)
        saved=native.canonical(snapshots['search120'])
        with runtime.arm_inference_telemetry(snapshots,'search240') as second:
            solve_literal(second,'search240',0)
        self.assertEqual(native.canonical(snapshots['search120']),saved)
        first.tests['0']['counters']['processed']=99
        self.assertEqual(native.canonical(snapshots['search120']),saved)
        result=runtime.inference_telemetry_result(snapshots)
        snapshots['search120']['tests']['0']['counters']['processed']=42
        self.assertEqual(native.canonical(result['arms']['search120']),saved)

    def test_exported_checkpoint_telemetry_must_match_each_arm_exactly(self):
        snapshots,answers,_=self.run_pair(runtime.ARMS)
        value=runtime.inference_telemetry_result(snapshots)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for arm_id,answer in answers.items():
                native.write(root/(arm_id+'.json'),answer)
            exported={a:json.loads((root/(a+'.json')).read_bytes()) for a in runtime.ARMS}
            runtime.verify_inference_telemetry(value,exported)
            exported['search240']['tests'][0]['telemetry']['counters']['processed']=1
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
                        adapter=NS(telemetry=collector,generation_deadline=float(allocation['generation_seconds']),verification_deadline=float(allocation['total_seconds']),
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
                self.assertEqual(value['arms']['search120']['events'],[
                    {'event':'phase_exception','phase':'generation','type':'InferenceLimitReached'}])
                bad=copy.deepcopy(value);bad['arms']['search120']['events'][0]['type']='RuntimeError'
                with self.assertRaisesRegex(RuntimeError,'cooperative inference guard'):
                    runtime.verify_inference_telemetry(bad,answers)
                bad=copy.deepcopy(value);bad['arms']['search120']['events']*=2
                with self.assertRaisesRegex(RuntimeError,'cooperative inference guard'):
                    runtime.verify_inference_telemetry(bad,answers)

    def test_unknown_fields_or_impossible_phase_partition_are_rejected(self):
        snapshots,answers,_=self.run_pair(runtime.ARMS)
        value=runtime.inference_telemetry_result(snapshots)
        def added(value):value['arms']['search120']['inference_arms']={}
        def overlap(value):value['arms']['search120']['exclusive_host_seconds']['parse_dedup']=1e30
        def training(value):
            value['arms']['search120']['inclusive_host_seconds']['training']=0.
            value['arms']['search120']['exclusive_host_seconds']['training']=0.
        def missing(value):del value['arms']['search240']
        for mutate in (added,overlap,training,missing):
            with self.subTest(mutation=mutate.__name__):
                invalid=copy.deepcopy(value);mutate(invalid)
                with self.assertRaises(RuntimeError):runtime.verify_inference_telemetry(invalid,answers)


if __name__=='__main__':unittest.main()
