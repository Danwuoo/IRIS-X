"""Independent production-path CPU tests. No model, weights, provider or network."""
import copy
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(os.environ.get('REVIEW_RUNTIME_ROOT',str(Path(__file__).resolve().parents[1]/'worktree'))).resolve()
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools.arc_qwen_transfer_20261012 import backend, call_policy as cp, science_profiles as sp
from tools.arc_learning_agent_20261011.budget import WorkLedger, BudgetExceeded

class Clock:
    def __init__(self, t=1000.):self.t=t
    def __call__(self):return self.t

class Native:
    output_cap=1024;prompt_cap=3072
    def __init__(self, clock, *, return_at=1001., fail=None, valid=True, dispatched=True):
        self.clock=clock;self.return_at=return_at;self.fail=fail;self.valid=valid;self.dispatched=dispatched;self.calls=[]
    def generate(self, messages, **kwargs):
        self.calls.append(kwargs);self.clock.t=self.return_at
        if self.fail:raise self.fail
        return dict(valid=self.valid,dispatched=self.dispatched,forward_input_tokens=12 if self.dispatched else 0,
            output_tokens=2 if self.dispatched else 0,forward_calls=2 if self.dispatched else 0,
            finish_reason='eos' if self.valid else 'length' if self.dispatched else 'context_excluded',
            fatal_error=False,elapsed_seconds=1.0)

class Windows(unittest.TestCase):
    def test_hard_and_work_caps(self):
        r=cp.generation_window(5000,now=1000)
        self.assertEqual((r['deadline_monotonic'],r['work_deadline_monotonic']),(1180,1175))
    def test_short_branch_inside_global_clips(self):
        for rem in (.01,2,40,60,180,10000):
            r=cp.generation_window(1000+rem,now=1000)
            self.assertEqual(r['deadline_monotonic'],1000+min(rem,180))
            self.assertAlmostEqual(r['work_deadline_monotonic'],1000+min(rem,180)-min(5,min(rem,180)*.1))
    def test_invalid_clocks_reject_before_dispatch(self):
        for end in (1000,999,-1,float('nan'),float('inf'),True,'2000'):
            with self.subTest(end=end),self.assertRaises((ValueError,BudgetExceeded)):
                cp.generation_window(end,now=1000)
        for now in (-1,float('nan'),float('inf'),True):
            with self.subTest(now=now),self.assertRaises(ValueError):cp.generation_window(2000,now=now)
    def test_marker_exact_replay(self):
        r={**cp.generation_window(5000,now=1000),'status':'active','event_id':'qwen14b-generation-1'}
        cp.check_active_call(r,now=1001,owner_deadline=5000)
        for key,value in [('deadline_monotonic',1180.01),('work_deadline_monotonic',1175.01),
                          ('call_policy_sha256','0'*64),('started_monotonic',1002),('branch_deadline_monotonic',5001)]:
            with self.subTest(key=key),self.assertRaises(ValueError):cp.check_active_call({**r,key:value},now=1001,owner_deadline=5000)
    def test_marker_hard_deadline_strict(self):
        r={**cp.generation_window(5000,now=1000),'status':'active','event_id':'qwen14b-generation-1'}
        cp.check_active_call(r,now=1179.9999,owner_deadline=5000)
        for now in (1180,1180.01):
            with self.assertRaises(TimeoutError):cp.check_active_call(r,now=now,owner_deadline=5000)
    def test_generation_marker_cannot_spoof_operation_or_event(self):
        r={**cp.generation_window(5000,now=1000),'status':'active','event_id':'qwen14b-generation-1'}
        for event in ('unknown','qwen14b-generation-0','qwen14b-generation-1x','ladder-128'):
            with self.subTest(event=event),self.assertRaises(ValueError):cp.check_active_call({**r,'event_id':event},now=1001,owner_deadline=5000)
        for field,value in [('call_kind','score'),('event_id',''),('status','finished')]:
            with self.subTest(field=field),self.assertRaises(ValueError):cp.check_active_call({**r,field:value},now=1001,owner_deadline=5000)
    def test_legacy_marker_namespaces_and_clocks_preserved(self):
        for event,work in [('qwen14b-c4096-likelihood-1',1115),('ladder-128-base-numeric-prefill',2000),('ladder-4096',2000)]:
            r={'status':'active','event_id':event,'deadline_monotonic':1120,'work_deadline_monotonic':work}
            cp.check_active_call(r,now=1001,owner_deadline=5000)
            with self.assertRaises(ValueError):cp.check_active_call({**r,'deadline_monotonic':1300},now=1001,owner_deadline=5000)
    def test_owner_deadline_cannot_expand(self):
        r={**cp.generation_window(5000,now=1000),'status':'active','event_id':'qwen14b-generation-1'}
        with self.assertRaises(ValueError):cp.check_active_call(r,now=1001,owner_deadline=1100)
    def test_historical_non_generation_window_unchanged(self):
        from tools.arc_learning_agent_20261011.metering import _call_window
        with patch('time.monotonic',return_value=1000):self.assertEqual(_call_window(5000),(1115,1120))

class Wrapper(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).parent);self.root=Path(self.tmp.name);self.clock=Clock()
        self.ledger=WorkLedger(self.root/'physical-work.jsonl')
    def tearDown(self):self.tmp.cleanup()
    def invoke(self,native,*,deadline=5000,cap=1024):
        m=backend.TransferMeteredModel(native,self.ledger)
        with patch('time.monotonic',self.clock):
            return m.generate([],kind='grid',seed=1,max_new_tokens=cap,deadline=deadline)
    def test_nominal_expands_generation_only(self):
        native=Native(self.clock);r=self.invoke(native)
        self.assertEqual(native.calls[0]['deadline'],1175)
        self.assertEqual(r['call_window']['deadline_monotonic'],1180)
        self.assertEqual(self.ledger.used['generation_calls'],1)
        self.assertEqual(self.ledger.used['input_tokens'],12)
        self.assertEqual(self.ledger.used['output_tokens'],2)
        self.assertFalse(self.ledger.pending)
        marker=json.loads((self.root/'active-call.json').read_text())
        self.assertEqual(marker['status'],'closed');self.assertEqual(marker['event_id'],r['physical_event_id'])
    def test_soft_boundary_invalidates_even_valid_native(self):
        for t in (1175,1175.1):
            with self.subTest(t=t):
                self.clock.t=1000
                r=self.invoke(Native(self.clock,return_at=t))
                self.assertFalse(r['valid']);self.assertTrue(r['fatal_error']);self.assertEqual(r['finish_reason'],'deadline')
                # New wrappers do not legally reset IDs against the same ledger.
                break
    def test_just_before_soft_is_accepted(self):
        self.assertTrue(self.invoke(Native(self.clock,return_at=1174.9999))['valid'])
    def test_hard_boundary_on_evidence_io_is_fatal(self):
        original=backend.atomic_json
        def slow_close(path,body,**kw):
            original(path,body,**kw)
            if body.get('status')=='closed':self.clock.t=1180
        with patch.object(backend,'atomic_json',side_effect=slow_close):r=self.invoke(Native(self.clock))
        self.assertFalse(r['valid']);self.assertTrue(r['fatal_error'])
        self.assertEqual(self.ledger.used['input_tokens'],12)
    def test_failed_truncated_charges_not_refunded(self):
        r=self.invoke(Native(self.clock,valid=False))
        self.assertEqual(r['finish_reason'],'length')
        self.assertEqual(self.ledger.events[-1]['event'],'failed')
        self.assertEqual(self.ledger.used['generation_calls'],1)
        self.assertEqual(self.ledger.used['input_tokens'],12)
        self.assertEqual(self.ledger.used['output_tokens'],2)
    def test_known_nondispatch_reconciles_zero_without_generation(self):
        r=self.invoke(Native(self.clock,valid=False,dispatched=False))
        self.assertEqual(self.ledger.events[-1]['event'],'excluded')
        self.assertFalse(r['dispatched']);self.assertEqual(self.ledger.used['generation_calls'],0)
    def test_native_exception_unknown_and_closed_marker(self):
        with self.assertRaisesRegex(RuntimeError,'synthetic'):self.invoke(Native(self.clock,fail=RuntimeError('synthetic')))
        self.assertTrue(self.ledger.pending);self.assertEqual(self.ledger.events[-1]['event'],'unknown')
        self.assertEqual(self.ledger.used['generation_calls'],1)
        self.assertEqual(self.ledger.used['output_tokens'],1024)
        self.assertEqual(json.loads((self.root/'active-call.json').read_text())['status'],'closed')
        with self.assertRaises(BudgetExceeded):self.ledger.reserve('another',{'generation_calls':1})
    def test_expired_branch_never_reserves_or_calls(self):
        native=Native(self.clock)
        with self.assertRaises(BudgetExceeded):self.invoke(native,deadline=999)
        self.assertFalse(native.calls);self.assertEqual(len(self.ledger.events),1)
    def test_output_cap_never_expands(self):
        native=Native(self.clock)
        for cap in (0,-1,1025,True,3.5):
            with self.subTest(cap=cap),self.assertRaises(ValueError):self.invoke(native,cap=cap)
        self.assertFalse(native.calls);self.assertEqual(len(self.ledger.events),1)
    def test_active_marker_io_failure_records_unknown_and_cleanup(self):
        original=backend.atomic_json
        def fail_active(path,body,**kw):
            if body.get('status')=='active':raise OSError('synthetic marker write')
            return original(path,body,**kw)
        native=Native(self.clock)
        with patch.object(backend,'atomic_json',side_effect=fail_active),self.assertRaises(OSError):self.invoke(native)
        self.assertFalse(native.calls);self.assertTrue(self.ledger.pending)
        self.assertEqual(self.ledger.events[-1]['event'],'unknown')
        self.assertEqual(json.loads((self.root/'active-call.json').read_text())['status'],'closed')

class CostReplay(unittest.TestCase):
    def test_scoring_does_not_acquire_generation_window(self):
        stats={'training_seconds_per_step':1,'prefill_seconds_per_input':.001,'decode_seconds_per_call':.001,'full_seconds_per_input':.02}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
            ledger=WorkLedger(Path(root)/'ledger.jsonl')
            with patch('time.monotonic',return_value=1000):
                r=sp.admission(sp.forecast(stats,updates=0,generations=1,scores=1),ledger,5000)
        self.assertFalse(r['admitted']);self.assertTrue(r['generation_per_call_admitted']);self.assertFalse(r['score_per_call_admitted'])
        self.assertEqual(r['score_work_seconds_available'],115)
    def test_short_branch_no_generation_inflation(self):
        stats={'training_seconds_per_step':0,'prefill_seconds_per_input':.001,'decode_seconds_per_call':.04,'full_seconds_per_input':0}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
            ledger=WorkLedger(Path(root)/'ledger.jsonl')
            with patch('time.monotonic',return_value=1000):
                r=sp.admission(sp.forecast(stats,updates=0,generations=1),ledger,1040)
        self.assertFalse(r['admitted']);self.assertEqual(r['generation_work_seconds_available'],36)

    def test_exact_v21_statistics_now_fit_generation_and_whole_main(self):
        import zipfile
        archive=ROOT.parents[1]/'portfolio63-next-20261012/publication/run-evidence/downloads/irisx-qwen14b-transfer-20261012-run001/evidence.zip'
        with zipfile.ZipFile(archive) as z:
            name=next(n for n in z.namelist() if n.endswith('/feasibility.json') or n=='feasibility.json')
            old=json.loads(z.read(name))
        estimate=sp.forecast(old['measurements'],updates=256,generations=224,reloads=3)
        self.assertAlmostEqual(estimate['generation_seconds']*1.5,115.7146352476084)
        self.assertGreater(estimate['generation_seconds']*1.5,115)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as root:
            ledger=WorkLedger(Path(root)/'ledger.jsonl')
            with patch('time.monotonic',return_value=1000):r=sp.admission(estimate,ledger,1000+old['remaining_seconds'])
        self.assertTrue(r['admitted']);self.assertEqual(r['generation_work_seconds_available'],175)
        self.assertFalse(r['actual_timeout_observed'])

if __name__=='__main__':unittest.main(verbosity=2)
