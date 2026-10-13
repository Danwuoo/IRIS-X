"""Offline truth-free checks against retained explicit synthetic original-scorer output."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'validation'))
import validate_transfer_outputs as v

class PublicArchive:
    synthetic=True
    def __init__(self,root):
        self.root=Path(root);self.members={p.relative_to(root).as_posix():{} for p in root.rglob('*') if p.is_file()};self.overrides={}
    def read(self,name):
        if 'target-escrow' in name or '/data/evaluation/' in name:raise AssertionError('gold read attempted')
        if name in self.overrides:return self.overrides[name]
        return v.local_file(self.root/v.safe_name(name),64*1024**2).read_bytes()
    def json(self,name):return v.strict_json(self.read(name),name)
    def change(self,name,fn):
        value=self.json(name);fn(value);self.overrides[name]=v.canonical(value);return value

class PublicContent(unittest.TestCase):
    synthetic=True
    @classmethod
    def setUpClass(cls):
        cls.root=ROOT/'validation-tests/public-fixture'
        if not cls.root.exists():raise unittest.SkipTest('retained original-scorer synthetic fixture absent')
        cls.source=v.SourceSnapshot(cls.root/'source-closure.zip',v.json_file(cls.root/'source-identity.json'))
    @classmethod
    def tearDownClass(cls):cls.source.close()
    def setUp(self):
        self.archive=PublicArchive(self.root/'run/owner');self.request=self.archive.json('request.json');self.terminal=v.json_file(self.root/'synthetic-terminal-adapter.json')
    def validate(self):return v.validate_public(self.archive,self.request,self.terminal,self.source,synthetic=True)
    def test_complete_synthetic167_original_scorer(self):
        out=self.validate();self.assertEqual(out['micro_pass_at_2_count'],167);self.assertFalse(out['goal_met']);self.assertFalse(out['eligible_complete_production_public_measurement'])
    def test_summary_only_metric_change(self):
        def edit(x):x['development_metrics']['metrics']['pass_at_2'].update(numerator=151,value=151/167)
        self.terminal['public_evaluation']=self.archive.change('public-evaluation/public-summary.json',edit)
        with self.assertRaisesRegex(v.ValidationError,'projection'):self.validate()
    def test_detail_row_change(self):
        self.archive.change('public-evaluation/evaluator-detail.json',lambda x:x['report']['rows'][0].update(pass2=False))
        with self.assertRaises(v.ValidationError):self.validate()
    def test_detail_metric_and_summary_both_rehashed(self):
        def edit(x):x['development_metrics']['metrics']['pass_at_2'].update(numerator=151,value=151/167)
        self.terminal['public_evaluation']=self.archive.change('public-evaluation/public-summary.json',edit)
        def edit_detail(x):edit(x);edit(x['report'])
        self.archive.change('public-evaluation/evaluator-detail.json',edit_detail)
        with self.assertRaisesRegex(v.ValidationError,'aggregate'):self.validate()
    def test_process_closure_missing(self):
        self.archive.change('public-evaluation/process-receipt.json',lambda x:x.update(owned_process_stopped=False))
        with self.assertRaisesRegex(v.ValidationError,'close cleanly'):self.validate()
    def test_process_timeout(self):
        self.archive.change('public-evaluation/process-receipt.json',lambda x:x.update(timed_out=True))
        with self.assertRaises(v.ValidationError):self.validate()
    def test_cpu_request_seal_mismatch(self):
        self.archive.change('public-evaluation/request.json',lambda x:x.update(seal_sha256='0'*64))
        with self.assertRaises(v.ValidationError):self.validate()
    def test_goal_claim_denied_for_synthetic(self):
        self.terminal['public_evaluation']=self.archive.change('public-evaluation/public-summary.json',lambda x:x.update(goal_met=True))
        self.archive.change('public-evaluation/evaluator-detail.json',lambda x:x.update(goal_met=True))
        with self.assertRaises(v.ValidationError):self.validate()
    def test_scorer_source_pin_changed(self):
        source=deepcopy(self.source.mapping);self.source.mapping['tools/arc_offline_evaluation.py']='0'*64
        try:
            with self.assertRaises(v.ValidationError):self.validate()
        finally:self.source.mapping=source
    def test_public_query_denominator_shrink(self):
        self.archive.change('public-evaluation/evaluator-detail.json',lambda x:x['report']['rows'].pop())
        with self.assertRaisesRegex(v.ValidationError,'denominator'):self.validate()
    def test_public_row_duplicate(self):
        self.archive.change('public-evaluation/evaluator-detail.json',lambda x:x['report']['rows'].__setitem__(1,deepcopy(x['report']['rows'][0])))
        with self.assertRaisesRegex(v.ValidationError,'identity'):self.validate()
    def test_public_physical_receipt_changed(self):
        self.archive.change('generations/00000000-0-0.json',lambda x:x.update(forward_input_tokens=1))
        with self.assertRaises(v.ValidationError):self.validate()
    def test_public_truthfree_pool_change(self):
        self.archive.change('public-prediction-seal/pool.json',lambda x:x['records'][0]['tests'][0].update(ranked_grids=[[[9]]]))
        with self.assertRaises(v.ValidationError):self.validate()
    def test_public_row_boolean_not_integer(self):
        self.archive.change('public-evaluation/evaluator-detail.json',lambda x:x['report']['rows'][0].update(pass2=1))
        with self.assertRaises(v.ValidationError):self.validate()

if __name__=='__main__':unittest.main()
