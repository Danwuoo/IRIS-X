"""Actual retained tiny execution and synthetic mutations of its envelopes."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'validation'))
import validate_transfer_outputs as v
from fixture_helpers import *

class RetainedContent(unittest.TestCase):
    synthetic=True
    @classmethod
    def setUpClass(cls):
        if not RETAINED_ROOT.exists():raise unittest.SkipTest('retained owned tiny execution not present')
    def rejected(self,mutate):
        with tempfile.TemporaryDirectory() as temp:
            path=derive_retained_fixture(Path(temp)/'fixture',synthetic=True,mutate=mutate)
            with self.assertRaises((v.ValidationError,ValueError)):validate_fixture(path)
    def test_retained_real_tiny_positive(self):
        result=validate_fixture(RETAINED_ROOT)
        self.assertTrue(result['valid']);self.assertTrue(result['synthetic']);self.assertFalse(result['science_complete']);self.assertFalse(result['operational_success']);self.assertFalse(result['goal_met']);self.assertFalse(result['costs']['full4096_measured'])
    def test_production_api_rejects_tiny(self):
        with self.assertRaisesRegex(v.ValidationError,'synthetic'):
            v.validate_content(RETAINED_ROOT,v.source_identity(RETAINED_SOURCE),source_root=RETAINED_SOURCE)
    def test_latest_source_cannot_relabel_old_run(self):
        with self.assertRaisesRegex(v.ValidationError,'exact source identity'):
            v.validate_content(RETAINED_ROOT,v.source_identity(ROOT/'worktree'),source_root=ROOT/'worktree',allow_synthetic=True)
    def test_helper_requires_synthetic(self):
        with self.assertRaises(ValueError):derive_retained_fixture('/unused',synthetic=False)
    def test_terminal_status_promotion(self):self.rejected(lambda m,t:t.update(status='TRANSFER_PARTIAL'))
    def test_physical_totals_tamper(self):self.rejected(lambda m,t:bind_child(m,t,lambda c:c['physical_usage'].update(input_tokens=1)))
    def test_model_old_profile(self):self.rejected(lambda m,t:bind_child(m,t,lambda c:c['model_identity'].update(profile_id='old2048')))
    def test_changed_source_sha(self):self.rejected(lambda m,t:edit_json(m,'request.json',lambda r:r['source_identity'].update({'tools/arc_qwen_transfer_20261012/runner.py':'0'*64})))
    def test_changed_model_revision(self):self.rejected(lambda m,t:bind_child(m,t,lambda c:c['model_identity'].update(reference_revision='0'*40)))
    def test_changed_panel_denominator(self):self.rejected(lambda m,t:edit_json(m,'dataset/solver-dataset.json',lambda d:d['denominators'].update(holdout=31)))
    def test_changed_panel_source(self):self.rejected(lambda m,t:edit_json(m,'dataset/frozen-plan.json',lambda d:d['holdout_ids'].__setitem__(0,d['dev_ids'][0])))
    def test_missing_native_receipt(self):self.rejected(lambda m,t:m.pop('experiment/dev/base/000-0.json'))
    def test_changed_native_receipt_charge(self):self.rejected(lambda m,t:edit_json(m,'experiment/dev/base/000-0.json',lambda r:r.update(forward_input_tokens=1)))
    def test_changed_checkpoint_full_state(self):self.rejected(lambda m,t:edit_json(m,'experiment/checkpoint-metadata/sft1/resume/state.json',lambda x:x['payload']['handle'].update(state_sha256='0'*64)))
    def test_changed_reload_state(self):self.rejected(lambda m,t:edit_json(m,'experiment/fresh-reload-1.json',lambda x:x['loaded'].update(state_sha256='0'*64)))
    def test_changed_training_counter(self):self.rejected(lambda m,t:edit_json(m,'experiment/train-1.json',lambda x:x.update(optimizer_steps=0)))
    def test_changed_calibration_measured_timing(self):self.rejected(lambda m,t:edit_json(m,'calibration/calibration.json',lambda x:x['measurements'].update(training_seconds_per_step=0.0)))
    def test_changed_forecast_ledger_head(self):self.rejected(lambda m,t:edit_json(m,'feasibility.json',lambda x:x.update(ledger_head_sha256='0'*64)))
    def test_changed_forecast_physical_prefix(self):self.rejected(lambda m,t:edit_json(m,'feasibility.json',lambda x:x['physical_usage_at_decision'].update(input_tokens=0)))
    def test_missing_source_guaranteed_phase_files(self):
        names=('active-stage.json','feasibility.json','model-admission.json','calibration/calibration.json','decoder-policy.json','full-diagnostics.json','training-receipts-at-exit.json','dataset/solver-dataset.json','dataset/frozen-plan.json','experiment/dev-prediction-seal.json','experiment/dev-predictions-sealed.json','experiment/holdout-prediction-seal.json','experiment/holdout-predictions-sealed.json','experiment/ttt-predictions-sealed.json','experiment/checkpoint-receipts.json','experiment/full-report.json','experiment/training-admission.json','experiment/frozen-selection.json','experiment/public-selection.json','experiment/main-complete.json','main-scoring.json')
        for name in names:
            with self.subTest(omitted=name):self.rejected(lambda m,t:m.pop(name))
    def test_missing_ttt_admission_forecast(self):self.rejected(lambda m,t:edit_json(m,'experiment/ttt-predictions-sealed.json',lambda x:x.pop('forecast')))
    def test_changed_forecast(self):self.rejected(lambda m,t:edit_json(m,'feasibility.json',lambda x:x.update(forecast_seconds=0.0)))
    def test_changed_scorer_denominator(self):self.rejected(lambda m,t:edit_json(m,'main-scoring.json',lambda x:x['scopes']['holdout']['base'].update(denominator=31)))
    def test_no_escrow_parse(self):
        old=v.ClosedArchive.json
        def guarded(instance,name):
            if 'target-escrow' in name:raise AssertionError('target escrow parsed')
            return old(instance,name)
        v.ClosedArchive.json=guarded
        try:self.assertTrue(validate_fixture(RETAINED_ROOT)['valid'])
        finally:v.ClosedArchive.json=old

class TargetedTTT(unittest.TestCase):
    synthetic=True
    def setUp(self):
        root=ROOT/'native-ttt-1791809444730656889'
        if not root.exists():self.skipTest('retained actual targeted tiny TTT absent')
        self.archive=TargetedTTTArchive(root);self.request={'output_root':str(root.absolute())}
    def test_actual_one_case_demo_only_replay(self):
        result=v.validate_ttt(self.archive,self.request,self.archive.dataset)
        self.assertEqual(result['complete_rows'],1);self.assertEqual(result['status'],'TTT_PARTIAL')
    def test_target_demo_leak_rejected(self):
        n='experiment/ttt/d93c6891/selector-inputs.json';x=self.archive.json(n);x['candidates'][1]['folds'][0]['adaptation_demo_ids'].append('0');self.archive.overrides[n]=v.canonical(x)
        with self.assertRaises(ValueError):v.validate_ttt(self.archive,self.request,self.archive.dataset)
    def test_selected_answer_tamper(self):
        for row in self.archive.phase['rows']:
            if row['complete']:row['answers']=[[[0]]]
        with self.assertRaises(ValueError):v.validate_ttt(self.archive,self.request,self.archive.dataset)
    def test_fake_full_ttt_denominator(self):
        self.archive.phase['status']='TTT_COMPLETE'
        with self.assertRaises(ValueError):v.validate_ttt(self.archive,self.request,self.archive.dataset)
    def test_reset_state_tamper(self):
        n='experiment/ttt/d93c6891/fold-0-reset.json';x=self.archive.json(n);x['adapter_sha256']='0'*64;self.archive.overrides[n]=v.canonical(x)
        with self.assertRaises(ValueError):v.validate_ttt(self.archive,self.request,self.archive.dataset)

if __name__=='__main__':unittest.main()
