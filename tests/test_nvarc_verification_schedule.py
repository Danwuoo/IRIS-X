"""E10 bounded synthetic mechanisms. No ARC score or GPU performance inference."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from tests.test_nvarc_phase_telemetry import SolveFixture, Array
from tests.test_nvarc_native_solve import FakeTensor
from tests.test_nvarc_public_eval import fixture, record
from tools import nvarc_native_multitask as native
from tools import nvarc_native_solve_runtime as inference
from tools import nvarc_public_eval as public
from tools import nvarc_public_eval_runtime as runtime


class ScheduleFixture(SolveFixture):
    def __init__(self, *, batches=None, generation_seconds=1, verification_seconds=1,
                 generation_deadline=20, verification_deadline=30):
        super().__init__()
        self.outputs=batches if batches is not None else [
            [(2,[(.6,[2,15]),(.2,[1,15])]),(0,[(.1,[2,15]),(.3,[10,15])])],
            [(1,[(.2,[1,15]),(.4,[3,15])])],
            [(0,[(.1,[2,15])])],[(3,[(.3,[1,15])])]]
        self.generation_seconds=generation_seconds;self.verification_seconds=verification_seconds
        self.adapter.generation_deadline=generation_deadline
        self.adapter.verification_deadline=verification_deadline
        self.generated=0;self.verification_start_times=[];self.verification_grids=[]

    def generate(self, adapter, prefixes, max_tokens, floor, deadline):
        self.calls.append(('generation',max_tokens,floor,deadline))
        adapter(input_ids=FakeTensor(prefixes),use_cache=True)
        self.clock.advance(self.generation_seconds)
        result=copy.deepcopy(self.outputs[self.generated]);self.generated+=1
        return result

    def verify(self,queries,answers,tokenizer,adapter):
        self.verification_start_times.append(self.clock())
        self.verification_grids.append(answers[0])
        # Model-entry admission is cooperative, just as LightModel/EvidenceModel.
        search=adapter.generation_deadline
        try:
            adapter.generation_deadline=adapter.verification_deadline
            adapter(input_ids=FakeTensor([[10,1,15]]*4),use_cache=True)
        finally: adapter.generation_deadline=search
        self.clock.advance(self.verification_seconds)
        self.calls.append(('verification',answers[0]))
        return [float(answers[0])]*4

    def rank(self,votes):
        self.votes=copy.deepcopy(votes);groups={}
        for row in votes.values():
            key=native.grid_key(row['solution'].tolist())
            groups.setdefault(key,[]).append(row)
        # Independent frequency-minus-mean oracle, with stable first occurrence ties.
        ordered=sorted(groups.values(),key=lambda rows: len(rows)-sum(rows[0]['score_aug'])/8,reverse=True)
        return [rows[0]['solution'] for rows in ordered]

    def run(self,schedule='interleaved',*,telemetry=True,cap=64,module=native):
        if telemetry:self.adapter.telemetry=public.PhaseTelemetry(clock=self.clock)
        batches=[self.views.keys[i:i+4] for i in range(0,16,4)]
        def verification(_p,_b,solution,*_args):
            value=solution[0][0]
            rows=[{'input':'query','reply':str(value)} for _ in range(8)]
            bindings=[{'source_view':'a_0.v'+str(i),'query_ids':[10],'answer_ids':[value,15]} for i in range(8)]
            return rows,bindings
        args={} if module is not native else {'verification_schedule':schedule}
        with patch.object(module,'test_views',return_value=('a_0',SimpleNamespace(),self.views,self.formatter,batches)), \
             patch.object(module,'verifier_rows',side_effect=verification), \
             patch.object(inference.time,'time',self.clock):
            return module.solve_test({},'a',0,self.loader,self.solver,self.decoder,self.tokenizer,
                self.adapter,maximum_candidates=cap,emit=lambda e,**kw:self.events.append((e,kw)),**args)


class VerificationScheduleTests(unittest.TestCase):
    def retain(self,name,value):
        directory=os.environ.get('IRIS_E10_EVIDENCE_DIR')
        if directory:
            path=Path(directory);path.mkdir(parents=True,exist_ok=True)
            (path/name).write_bytes(native.canonical(value))
    def test_default_is_byte_semantic_baseline_with_same_calls_and_votes(self):
        old=ModuleType('e10_frozen_baseline')
        body=subprocess.run(['git','show','90ea1bcd40d9e8c88fb7e849e55257704e9b3c16:tools/nvarc_native_multitask.py'],
            capture_output=True,check=True).stdout
        exec(compile(body,'frozen-E00-E01-baseline','exec'),old.__dict__)
        prior,current=ScheduleFixture(),ScheduleFixture()
        self.assertEqual(prior.run(module=old),current.run())
        self.assertEqual(prior.calls,current.calls);self.assertEqual(prior.votes,current.votes)
        self.assertEqual(prior.events,current.events)

    def test_enough_time_scores_multiplicity_ranking_and_fifo_across_batches_views(self):
        a,b=ScheduleFixture(),ScheduleFixture()
        left,right=a.run(),b.run('deferred')
        self.assertEqual(left['ranked_grids'],right['ranked_grids'])
        self.assertEqual(a.votes,b.votes)
        self.retain('synthetic-parity.json',{'kind':'fake-model-fake-clock; no ARC/GPU claim',
            'interleaved':left,'deferred':right})
        self.assertEqual(right['ranked_grids'],[[[1]],[[2]],[[3]]])
        proof=right['verification_schedule'];self.assertEqual([r['first_sequence_index'] for r in proof['queue']],[0,1,5])
        self.assertEqual(b.verification_grids,['2','2','1','1','3','3'])
        c=right['telemetry']['counters']
        self.assertEqual((c['raw_returned'],c['processed'],c['invalid'],c['duplicate'],c['parsed_unique']),
                         (8,8,1,4,3))
        self.assertEqual((c['queued'],c['votes_ranked'],c['full_verified'],c['pending']),(3,7,3,0))
        self.assertEqual([s['source_view'] for s in right['telemetry']['sequences']],
            ['a_0.r2','a_0.r2','a_0.r0','a_0.r0','a_0.r5','a_0.r5','a_0.r8','a_0.r15'])
        self.assertEqual(len([e for e,_ in b.events if e=='candidate_ranked']),7)
        timing=b.adapter.telemetry.snapshot()
        self.assertAlmostEqual(sum(v or 0 for v in timing['exclusive_host_seconds'].values())+
            timing['unscoped_host_seconds'],timing['elapsed_host_seconds'])

    def test_no_telemetry_still_retains_fifo_partial_and_same_scores(self):
        a,b=ScheduleFixture(),ScheduleFixture()
        self.assertEqual({k:v for k,v in a.run('deferred').items() if k!='telemetry'},
                         b.run('deferred',telemetry=False))
        a,b=ScheduleFixture(generation_seconds=4,verification_seconds=4),ScheduleFixture(generation_seconds=4,verification_seconds=4)
        self.assertEqual(a.run('deferred')['verification_schedule'],b.run('deferred',telemetry=False)['verification_schedule'])

    def test_equal_source_scores_keep_first_occurrence_tie_not_beam_priority(self):
        f=ScheduleFixture(batches=[[(3,[(.8,[2,15]),(.1,[1,15]),(.9,[2,15])])],[],[],[]])
        r=f.run('deferred')
        self.assertEqual(r['ranked_grids'],[[[2]],[[1]]])
        self.assertEqual([q['first_sequence_index'] for q in r['verification_schedule']['queue']],[0,1])

    def test_generation_overrun_and_exact_30_verify_admission_boundary(self):
        for seconds,expected in ((21,[[[1]]]),(29.75,[])):
            f=ScheduleFixture(batches=[[(0,[(.1,[1,15])])],[],[],[]],generation_seconds=seconds)
            r=f.run('deferred')
            self.assertEqual(f.generated,1);self.assertEqual(r['ranked_grids'],expected)
            self.assertTrue(r['telemetry']['cooperative_deadlines']['generation_return_after_deadline'])
            if seconds==29.75:
                self.assertEqual(f.verification_start_times,[])
                self.assertEqual(r['verification_schedule']['verification_started_at'],30)
                self.assertEqual(r['verification_schedule']['queue'][0]['state'],'pending')

    def test_invalid_and_duplicate_count_in_64_cap_and_bounded_queue(self):
        for tokens,expected in (([10,15],(64,0,0)),([1,15],(0,1,64))):
            f=ScheduleFixture(batches=[[(0,[(.1,tokens)]*70)],[],[],[]])
            r=f.run('deferred');c=r['telemetry']['counters']
            self.assertEqual((c['invalid'],c['queued'],c['votes_ranked']),expected)
            self.assertEqual((c['raw_returned'],c['processed']),(70,64))
            self.assertEqual(r['verification_schedule']['generation_termination'],'candidate_limit')
        with self.assertRaisesRegex(RuntimeError,'bounded'):ScheduleFixture().run('deferred',cap=65)

    def test_early_generation_finish_immediately_verifies_without_waiting(self):
        f=ScheduleFixture();r=f.run('deferred')
        self.assertEqual(f.verification_start_times[0],6) # 4 batches + 8 parses * .25
        self.assertEqual(r['verification_schedule']['generation_finished_at'],6)
        self.assertLess(f.verification_start_times[0],20)

    def test_generation_entry_exact_20_boundary_and_no_phase_deadline_reset(self):
        f=ScheduleFixture(batches=[[(0,[(.1,[1,15])])],[],[],[]],generation_seconds=19.75)
        r=f.run('deferred');self.assertEqual(f.generated,1)
        self.assertEqual(f.verification_start_times,[20,21])
        self.assertEqual(r['verification_schedule']['generation_termination'],'inference_deadline')
        self.assertEqual((f.adapter.generation_deadline,f.adapter.verification_deadline),(20,30))

    def test_shared_30_deadline_partial_never_promoted_pending_duplicates_never_vote(self):
        f=ScheduleFixture(generation_seconds=4,verification_seconds=4)
        r=f.run('deferred');q=r['verification_schedule']['queue']
        self.assertEqual([row['state'] for row in q],['full','partial','pending'])
        self.assertEqual([row['completed_views'] for row in q],[8,4,0])
        self.assertEqual(r['ranked_grids'],[[[2]]])
        self.assertEqual(r['telemetry']['counters']['votes_ranked'],3)
        self.assertEqual(r['verification_schedule']['verification_termination'],'inference_deadline')
        self.assertEqual(f.verification_start_times,[18,22,26,30])
        self.assertEqual(f.adapter.completed['verification'],3)
        self.assertIsNone(f.adapter.verification_rows)

    def test_inflight_overrun_is_observed_not_preempted_or_new_admission(self):
        f=ScheduleFixture(generation_seconds=4,verification_seconds=11)
        r=f.run('deferred')
        self.assertEqual(f.adapter.completed['verification'],2)
        self.assertEqual(r['ranked_grids'],[[[2]]])
        self.assertEqual(r['verification_schedule']['verification_finished_at'],40)
        self.assertTrue(r['telemetry']['cooperative_deadlines']['verification_return_after_deadline'])
        self.assertFalse(r['telemetry']['cooperative_deadlines']['preemption'])
        self.assertEqual(r['verification_schedule']['queue'][1]['state'],'pending')

    def test_fake_mechanism_is_synthetic_source_view_gain_not_arc_quality(self):
        a,b=ScheduleFixture(generation_seconds=5,verification_seconds=3),ScheduleFixture(generation_seconds=5,verification_seconds=3)
        left,right=a.run(),b.run('deferred')
        self.assertGreater(right['completed_generation_batches'],left['completed_generation_batches'])
        self.assertFalse(right['correctness_scored'])
        self.assertIsNone(b.adapter.telemetry.snapshot()['gpu_kernel_seconds'])
        self.retain('synthetic-mechanism.json',{'kind':'synthetic non-performance illustration',
            'interleaved':left,'deferred':right})

    def test_later_test_independent_deadline_previous_checkpoint_survives_exception(self):
        plan,data=fixture();rec=record(plan,data,'a');f=ScheduleFixture();saved=[];calls=[]
        def solve(index,deadline):
            calls.append((index,deadline))
            if index:raise RuntimeError('later-test failure')
            r=f.run('deferred');return r
        with self.assertRaisesRegex(RuntimeError,'later-test'):
            runtime.solve_all_tests(plan,data,'a',solve,lambda r:saved.append(copy.deepcopy(r)),rec,
                now=f.clock,deadline=100)
        self.assertEqual(calls,[(0,30),(1,42)])
        self.assertTrue(saved[-1]['tests'][0]['ranked_grids'])
        self.assertEqual(len(saved[-1]['tests']),2)

    def test_truth_in_schedule_nested_is_rejected_and_legacy_identity_not_opted_in(self):
        plan,data=fixture();rec=record(plan,data,'a')
        rec['tests'][0]['verification_schedule']={'nested':{'answer_key':[[1]]}}
        with self.assertRaisesRegex(RuntimeError,'evaluator'):public.validate_record(plan,data,rec)
        plan['verification_schedule']='deferred'
        with self.assertRaisesRegex(RuntimeError,'historical'):public.validate_plan(plan,data,allow_fixture=True)

    def test_inert_screen_keeps_single_factor_full_tasks_and_pending_freeze(self):
        plan=json.loads((Path(__file__).resolve().parents[1]/'research/stage4-e10/inert-screen-plan.json').read_bytes())
        self.assertEqual(plan['owner_authorized_executions'],0)
        self.assertEqual(plan['screen']['task_runs_maximum'],24*2*2)
        self.assertEqual(plan['controls']['ttt_steps'],128)
        self.assertEqual(plan['controls']['processed_sequence_cap'],64)
        self.assertEqual(plan['controls']['dfs_sequence_probability_floor'],.2)
        self.assertEqual(plan['calibration_gate_before_E10']['additional_calibration_runs'],0)
        self.assertIsNone(plan['bindings']['partition_manifest'])
        self.assertIsNone(plan['screen']['screen_test_count'])
        self.assertEqual(plan['confirmation']['maximum_comparisons_across_stage4'],1)
        self.assertTrue(plan['confirmation']['requires_owner_authorization'])
        self.assertFalse(plan['local_validation_claims']['provider_permission'])


if __name__=='__main__':unittest.main()
