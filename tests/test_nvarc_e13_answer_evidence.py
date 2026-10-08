"""Real E13 inference admission/adapter/event replay on literal CPU sources."""
import copy
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from tools import nvarc_e13_answer_evidence as evidence
from tools import nvarc_e13_runtime as runtime
from tools import nvarc_e12_answer_evidence as historical
from tools import nvarc_native_multitask as native
from tools import nvarc_native_solve_runtime as source
from tools.nvarc_public_eval import PhaseTelemetry
from tests.nvarc_e13_cpu_fixture import fixture,LiteralEngine


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.plan=fixture(self.root)
        self.engine=LiteralEngine();self.addCleanup(self.temp.cleanup)
        self.challenges=json.loads((self.root/'challenges.json').read_bytes())
    def solve(self,arm='search120',rank=0,deadline=1000.):
        directory=self.root/'workers'/str(rank)/'arms'/arm;directory.mkdir(parents=True)
        with patch.object(evidence.time,'time',side_effect=self.engine.now),patch.object(native,'test_views',side_effect=self.engine.views):
            record=evidence.solve_task(self.engine,self.root,self.plan,rank,deadline,PhaseTelemetry(),
                observe_forwards=True,arm_id=arm,directory=directory)
        allocations=json.loads((directory/'test-allocations.json').read_bytes())
        rows=evidence.read_events(directory/'inference-events.jsonl',record['binding'])
        return directory,record,allocations,rows
    def test_twelve_tests_have_arm_specific_full_windows_and_unchanged_caps(self):
        counts={a:0 for a in runtime.ARMS};prefixes={a:[] for a in runtime.ARMS}
        for rank,key in enumerate(self.plan['task_order']):
            for arm in runtime.ARMS:
                directory,record,allocations,rows=self.solve(arm,rank)
                count=runtime.TASK_COUNTS[key];contract=runtime.arm_contract(arm)
                self.assertEqual(evidence.check_inference(rows,record['tests'],count,plan=self.plan,
                    arm_id=arm,admitted_allocations=allocations),record['accounting'])
                evidence.verify_forward_observation(directory/'inference-forward-diagnostics.json',record['binding'],rows,count)
                self.assertEqual(record['accounting']['generation']['completed'],4*count)
                self.assertFalse(record['output_qualified'])
                for index,a in allocations.items():
                    self.assertEqual(runtime.allocation_deadlines(a,record['binding'],int(index)),
                        (a['started_epoch']+contract['generation_seconds'],a['started_epoch']+contract['per_test_seconds']))
                prefixes[arm].extend(r['input_ids_digest'] for r in rows if r['event']=='forward_reserved')
                counts[arm]+=count
        self.assertEqual(counts,{'search120':6,'search240':6});self.assertEqual(prefixes['search120'],prefixes['search240'])
        self.assertEqual(set(self.engine.scores),{-math.log(.2)})
    def test_no_clipped_short_or_long_window(self):
        for arm,total in [('search120',150),('search240',270)]:
            _,record,allocations,rows=self.solve(arm,deadline=100+total-.001)
            self.assertEqual([t['status'] for t in record['tests']],['not_executed']*2)
            self.assertEqual(allocations,{});self.assertEqual(rows,[])
        self.assertEqual(self.engine.calls,[])
    def test_exact_arm_binding_and_budget_reject_before_native_call(self):
        bound=evidence.task_binding(self.plan,self.challenges,0,schedule='interleaved',arm_id='search240')
        allocation=runtime.paired_allocation(bound,0,100.,1000.)
        adapter=NS(generation_deadline=340.,verification_deadline=370.)
        args=(self.challenges,bound['task_id'],0,None,None,None,None,adapter)
        kwargs=dict(maximum_candidates=64,emit=lambda *_a,**_k:None,test_allocation=allocation,arm_id='search240')
        with patch.object(evidence,'native_solve_test',return_value='literal') as solve:
            self.assertEqual(evidence.solve_test(*args,**kwargs),'literal');self.assertIsNone(solve.call_args.kwargs['dfs_arm'])
        for changes in (dict(arm_id='search120'),dict(arm_id=None),dict(maximum_candidates=True),
                dict(verification_schedule='deferred'),dict(test_allocation=dict(allocation,generation_seconds=120))):
            with self.subTest(changes=changes),patch.object(evidence,'native_solve_test') as solve:
                with self.assertRaises(RuntimeError):evidence.solve_test(*args,**dict(kwargs,**changes))
                solve.assert_not_called()
        adapter.generation_deadline=339.
        with self.assertRaisesRegex(RuntimeError,'deadlines'):evidence.solve_test(*args,**kwargs)
    def test_rehashed_wrong_binding_and_allocation_are_rejected(self):
        _,record,allocations,rows=self.solve()
        for field,value in [('arm_id','search240'),('training_updates',64),('generation_seconds',240),('rank',False)]:
            invalid=copy.deepcopy(rows);invalid[0][field]=value
            with self.subTest(field=field),self.assertRaises(RuntimeError):
                evidence.check_inference(invalid,record['tests'],2,plan=self.plan,arm_id='search120',admitted_allocations=allocations)
        invalid=copy.deepcopy(allocations);invalid['0']['session_deadline_epoch']=200.
        with self.assertRaises(RuntimeError):
            evidence.check_inference(rows,record['tests'],2,plan=self.plan,arm_id='search120',admitted_allocations=invalid)
    def test_failure_retains_reservation_and_recoverable_prefix(self):
        self.engine.fail_after=4
        with self.assertRaisesRegex(RuntimeError,'literal model failure'):self.solve()
        directory=self.root/'workers/0/arms/search120'
        record=json.loads((directory/'answer-checkpoint.json').read_bytes())
        allocations=json.loads((directory/'test-allocations.json').read_bytes())
        with patch.object(evidence,'verify_source_provenance'):
            result=evidence.recover_completed_tests(self.root,self.plan,0,arm_id='search120',directory=directory,
                admitted_allocations=allocations)
        self.assertEqual(result['tests'][0],record['tests'][0]);self.assertEqual(result['tests'][1]['status'],'not_executed')
        self.assertFalse(result['training_and_reset_qualified']);self.assertFalse(result['output_qualified'])
    def test_frozen_e12_rejects_new_plan(self):
        with self.assertRaises(RuntimeError):historical.for_plan(self.plan)
        self.assertEqual(evidence.PER_TEST,historical.PER_TEST)


if __name__=='__main__':unittest.main()
