"""Independent fixture containment, immutable calibration and original-clock checks."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_transfer_20261012 import protocol as p,science_profiles as s,decoder as d,runner as r
from tools.arc_learning_agent_20261011.budget import WorkLedger,atomic_json

class FixtureAndClock(unittest.TestCase):
    def test_tiny_defaults_match_execution_and_forecast(self):
        c=p.validate_config({'enabled':True,'tiny_cpu':True,'test_fixture_dataset':True,'started_epoch':time.time()})
        self.assertEqual(c['test_checkpoint_updates'],[1,2]);self.assertEqual(c['test_generation_cap'],4)
        self.assertNotIn('test_calibration_lengths',c)
        production={'enabled':True,'started_epoch':time.time(),'model':{},'training_root':'/tmp/train',
                    'public_exclusions_path':'/tmp/exclusions','public_exclusions_sha256':'a'*64}
        with self.assertRaises(ValueError):p.validate_config({**production,'test_calibration_lengths':[128,512]})
        with self.assertRaises(ValueError):p.validate_config({**production,'model':{'test_calibration_lengths':[128,512]}})

    def test_shortened_calibration_fails_before_any_native_work_in_production(self):
        for flag,lengths in [(False,[128,512]),(True,[128]),(True,[512]),(True,[128,512,4096])]:
            native=SimpleNamespace(tiny_cpu=flag,decoder_policy=None)
            with self.subTest(flag=flag,lengths=lengths),patch.dict(sys.modules,{'torch':SimpleNamespace()}):
                with self.assertRaisesRegex(ValueError,'explicit tinyCPU'):
                    d.run_calibration(native,None,None,'/does/not/create',time.monotonic()+60,fixture_lengths=lengths)

    def test_short_receipt_cannot_admit_production_or_relabel_actual_lengths(self):
        stats={'training_seconds_per_step':.01,'prefill_seconds_per_input':.00001,'decode_seconds_per_call':.001,'full_seconds_per_input':.00001}
        calibration={'completed_lengths':[128,512],'fixture_calibration_lengths':[128,512],
                     'cpu_fixture_only':True,'full_context_measured':False,'full_state_restoration_verified':True,
                     'behavioral_cache_admitted':True,'measurements':stats}
        original=deepcopy(calibration)
        with tempfile.TemporaryDirectory() as td:
            ledger=WorkLedger(Path(td)/'work.jsonl')
            with self.assertRaises(ValueError):s.decide(None,{'denominators':{}},calibration,ledger,time.monotonic()+3600,tiny=False)
            outcome=s.decide(None,{'denominators':{}},calibration,ledger,time.monotonic()+3600,tiny=True,backend_load_seconds=300)
            outcome['measurements']['training_seconds_per_step']=999
            self.assertEqual(calibration,original)
            self.assertEqual(outcome['updates'],2)
            self.assertGreaterEqual(outcome['forecast_seconds'],1.5*3*300)

    def test_execution_and_provider_clock_order_preserves_original_epoch(self):
        self.assertEqual((p.PROTOCOL['execution_cutoff_seconds'],p.PROTOCOL['provider_runtime_seconds'],p.PROTOCOL['maximum_session_seconds']),(42000,42300,43200))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';wall=100000.;mono=1000.;start=99000.
            proof={'closed':True,'returncode':0,'worker_returncode':0,'forced':False}
            guard=SimpleNamespace(poll=lambda:0,closed_proof=lambda:proof)
            def spawn(*args,**kwargs):
                atomic_json(root/'child-summary.json',{'status':'TRANSFER_NOT_ADMITTED','operational_success':False})
                return guard
            cfg={'enabled':True,'started_epoch':start,'model':{},'training_root':'/tmp/train',
                 'public_exclusions_path':'/tmp/exclusions','public_exclusions_sha256':'a'*64}
            with ExitStack() as stack:
                stack.enter_context(patch.object(r.time,'time',return_value=wall))
                stack.enter_context(patch.object(r.time,'monotonic',return_value=mono))
                stack.enter_context(patch.object(r,'source_identity',return_value={}))
                stack.enter_context(patch.object(r,'source_check'))
                stack.enter_context(patch.object(r,'verify_closed_proof'))
                stack.enter_context(patch.object(r.OwnedProcessGuard,'spawn',side_effect=spawn))
                stack.enter_context(patch.object(r,'checkpoint_inventory',return_value={'complete_store':False,'files':{},'bytes':0}))
                stack.enter_context(patch.object(r,'archive_closed',return_value={}))
                result=r.run_owned_transfer(cfg,root,python_command=['python','-I','-B','-S','/tmp/offline-run.py'])
            req=json.loads((root/'request.json').read_text())
            self.assertEqual(req['hard_deadline'],mono+(start+42000-wall))
            self.assertEqual(req['work_deadline'],req['hard_deadline']-600)
            self.assertEqual(result['predispatch_started_epoch'],start)
            self.assertEqual(result['effective_deadline_epoch'],start+42000)
            self.assertEqual(result['global_deadline_epoch'],start+43200)

if __name__=='__main__':unittest.main(verbosity=2)
