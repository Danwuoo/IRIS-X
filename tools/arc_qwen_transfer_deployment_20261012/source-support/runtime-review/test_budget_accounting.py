"""Independent cost equations and admission checks, no model execution."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'worktree'))
from tools.arc_qwen_transfer_20261012 import science_profiles as s
from tools.arc_learning_agent_20261011.budget import WorkLedger

class PhysicalBudget(unittest.TestCase):
    def test_all_outer_folds_and_final_refits_are_counted(self):
        cases=[{'parent_id':str(i),'demos':[{}]*(2+i%4)} for i in range(48)]
        ids=[str(i) for i in range(16)];out=s.counts(cases,ids)
        D=sum(2+i%4 for i in range(16))
        self.assertEqual(out['training_updates'],16*(D+16))
        self.assertEqual(out['fold_generations'],3*D)
        self.assertEqual(out['fold_scores'],3*D)
        self.assertEqual(out['generation_calls'],3*D+6*16)
        self.assertEqual(out['full_demo_retrains'],16)
        self.assertEqual(out['outer_fold_retrains'],D)
        with self.assertRaises(ValueError):s.counts(cases,ids+['missing'])

    def test_long_single_call_is_rejected_even_when_total_fits(self):
        stats={'training_seconds_per_step':1.,'prefill_seconds_per_input':.001,
               'decode_seconds_per_call':.1,'full_seconds_per_input':.001}
        estimate=s.forecast(stats,updates=256,generations=224,reloads=3)
        self.assertLess(estimate['forecast_seconds']+600,43200)
        with tempfile.TemporaryDirectory() as td:
            ledger=WorkLedger(Path(td)/'work.jsonl')
            result=s.admission(estimate,ledger,time.monotonic()+43200)
            self.assertFalse(result['admitted'])
            self.assertFalse(result['per_call_admitted'])
            self.assertEqual(result['reason'],'native-per-call-deadline-exceeded')
            self.assertEqual(ledger.used['input_tokens'],0)

    def test_remaining_time_and_physical_reservation_slack_are_both_required(self):
        stats={'training_seconds_per_step':.1,'prefill_seconds_per_input':.0001,
               'decode_seconds_per_call':.001,'full_seconds_per_input':.0001}
        estimate=s.forecast(stats,updates=256,generations=224,reloads=3)
        with tempfile.TemporaryDirectory() as td:
            ledger=WorkLedger(Path(td)/'work.jsonl')
            self.assertTrue(s.admission(estimate,ledger,time.monotonic()+43200)['admitted'])
            self.assertFalse(s.admission(estimate,ledger,time.monotonic()+5)['admitted'])
            ledger.used['input_tokens']=ledger.caps['input_tokens']-estimate['input_tokens']
            self.assertFalse(s.admission(estimate,ledger,time.monotonic()+43200)['admitted'])

if __name__=='__main__':unittest.main(verbosity=2)
