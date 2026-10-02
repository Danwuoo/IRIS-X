"""Scalar portability and generated transport guards; no ML or approved data."""
import ast
import hashlib
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import nvarc_native_ttt_schedule as schedule
from tools.stage_nvarc_native_long_ttt import portable_worker,portable_budget,WORKER,BUDGET,FORMAT,PORTABLE_FORMAT


class NativeScheduleTests(unittest.TestCase):
    def fixture(self,root):
        warm='def get_warmup_steps(self,num_training_steps):\n    return self.warmup_steps if self.warmup_steps>0 else math.ceil(num_training_steps*self.warmup_ratio)\n'
        cosine='def _get_cosine_schedule_with_warmup_lr_lambda(current_step,*,num_warmup_steps,num_training_steps,num_cycles=.5):\n    if current_step<num_warmup_steps:return float(current_step)/float(max(1,num_warmup_steps))\n    progress=float(current_step-num_warmup_steps)/float(max(1,num_training_steps-num_warmup_steps))\n    return max(0.,.5*(1.+math.cos(math.pi*2.*num_cycles*progress)))\n'
        sources={'transformers/training_args.py':warm,'transformers/optimization.py':cosine+'\n'+cosine}
        for name,body in sources.items():
            path=root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(body.encode())
        hashes={name:hashlib.sha256(body.encode()).hexdigest() for name,body in sources.items()}
        funcs={'get_warmup_steps':hashlib.sha256(warm.rstrip().encode()).hexdigest(),
            '_get_cosine_schedule_with_warmup_lr_lambda':hashlib.sha256(cosine.rstrip().encode()).hexdigest()}
        args=SimpleNamespace(learning_rate=5e-5,warmup_ratio=.1,warmup_steps=0,num_train_epochs=1)
        return hashes,funcs,args

    def test_same_platform_oracle_preserves_exact_rates_and_bounds_reference_rounding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);hashes,funcs,args=self.fixture(root)
            with patch.dict(schedule.SOURCES,hashes,clear=True),patch.dict(schedule.FUNCTIONS,funcs,clear=True):
                warm,cosine=schedule.source_functions(root)
                reference=[5e-5*cosine(i,num_warmup_steps=13,num_training_steps=128,num_cycles=.5) for i in range(129)]
                reference[49]=math.nextafter(reference[49],math.inf)
                rates,evidence=schedule.native_schedule(root,args,reference)
                self.assertNotEqual(rates[49],reference[49]);self.assertEqual(evidence['maximum_reference_ulp_distance'],1)
                for _ in range(4):reference[49]=math.nextafter(reference[49],math.inf)
                with self.assertRaises(RuntimeError):schedule.native_schedule(root,args,reference)
                reference=rates[:];reference[0]=1e-300
                with self.assertRaises(RuntimeError):schedule.native_schedule(root,args,reference)
                with self.assertRaises(RuntimeError):schedule.ulp_distance(float('nan'),0.)

    def test_unbound_or_unsafe_vendor_scalar_code_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);hashes,funcs,args=self.fixture(root)
            with patch.dict(schedule.SOURCES,hashes,clear=True),patch.dict(schedule.FUNCTIONS,funcs,clear=True):
                path=root/'transformers/training_args.py';body=path.read_text().replace('return self.warmup_steps','import os\n    return self.warmup_steps')
                path.write_bytes(body.encode())
                with self.assertRaises(RuntimeError):schedule.source_functions(root)
                schedule.SOURCES['transformers/training_args.py']=hashlib.sha256(body.encode()).hexdigest()
                schedule.FUNCTIONS['get_warmup_steps']=hashlib.sha256(body.rstrip().encode()).hexdigest()
                with self.assertRaises(RuntimeError):schedule.source_functions(root)

    def test_new_render_preserves_legacy_bytes_and_records_actual_rate_on_rejection(self):
        worker=WORKER.read_bytes();budget=BUDGET.read_bytes()
        new_worker=portable_worker().decode();new_budget=portable_budget().decode()
        self.assertIn("FORMAT='"+PORTABLE_FORMAT+"'",new_worker)
        self.assertIn("FORMAT='"+FORMAT+"'",worker.decode())
        self.assertIn("save('native-schedule.json',schedule)",new_worker)
        self.assertIn("save('training-failure.json'",new_worker)
        self.assertIn("self.state['last_learning_rate_check']",new_budget)
        ast.parse(new_worker);ast.parse(new_budget)
        self.assertEqual(WORKER.read_bytes(),worker);self.assertEqual(BUDGET.read_bytes(),budget)


if __name__=='__main__':unittest.main()
