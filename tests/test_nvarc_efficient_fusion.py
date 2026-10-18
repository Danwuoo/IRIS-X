"""Actual tiny-model fusion integration, not official-weight GPU efficacy."""
from __future__ import annotations
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tools.nvarc_efficient_fusion_20261018 import contracts as c

MISSING = [n for n in ('torch', 'transformers', 'peft', 'tokenizers', 'safetensors', 'pydantic') if importlib.util.find_spec(n) is None]
if not MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine
    from tests.test_nvarc_matched_controls import scripted_groups
    from tests.test_nvarc_matched_workflow import corpus
    from tools.nvarc_efficient_fusion_20261018 import panels, training, workflow, controller
    from tools.nvarc_posttrain_20261017 import matched_controls as mc
    from tools.arc2_goal_sprint_20261017.model import adapter_state, state_digest


def config(**changes):
    return {**c.DEFAULT_CONFIG, 'updates': 3, 'microbatch': 8, 'context_tokens': 96,
            'generation_tokens': 2, 'learning_rate': 1e-3, **changes}


class CurriculumTests(unittest.TestCase):
    def test_fixed_bounds_no_loss_reproduction_claim(self):
        self.assertEqual(c.physical_bounds()['rollout_slots'], 768)
        self.assertEqual(c.physical_bounds()['optimizer_attempts_max'], 192)
        for cfg in (config(updates=True), config(ttt_steps=32), config(extra=True), config(max_parent_visits=4)):
            with self.assertRaises(ValueError): c.validate_config(cfg)

    def test_full_coverage_strata_floors_and_hard_parent_cap(self):
        chooser = c.CoverageChooser([f'p{i}' for i in range(64)])
        selected = []
        for slot in range(96):
            parent, allocation = chooser.choose(); selected.append(parent)
            if slot < 64: rewards = ([0]*8, [1, 0]*4, [1]*8)[slot%3]
            else: rewards = [1, 0]*4
            chooser.observe(parent, rewards)
        self.assertEqual(len(set(selected[:64])), 64)
        self.assertEqual(chooser.report()['stratum_floor_achieved'], dict.fromkeys(c.STRATA, 8))
        self.assertTrue(all(s['groups'] <= 3 for s in chooser.stats.values()))
        with self.assertRaises(ValueError): chooser.choose()

    def test_unavailable_strata_are_recorded_not_invented(self):
        chooser = c.CoverageChooser([f'p{i}' for i in range(64)])
        for _ in range(96):
            parent, _ = chooser.choose(); chooser.observe(parent, [1]*8)
        self.assertEqual(chooser.report()['unavailable_stratum_fallbacks'], 16)
        self.assertEqual(chooser.report()['stratum_floor_achieved'], {'all_correct': 8})
        self.assertEqual(chooser.report()['parents_observed'], 64)


@unittest.skipIf(bool(MISSING), 'Optional actual-ML dependencies absent: '+','.join(MISSING))
class ActualFusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1); cls.temp = tempfile.TemporaryDirectory(); args = corpus(Path(cls.temp.name))
        cls.prepared = panels.prepare_panels(*args[:4], **args[4], train_count=3, dev_count=2)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def engine(self): return tiny_engine(dtype=torch.bfloat16, probability_policy='fp32-backbone-math-v1')

    def test_real_routes_all_groups_used_fresh_states_and_matched_control(self):
        engine = self.engine(); initial = mc.full_policy_sha256(engine); groups = []; probes = []
        with patch('torch.multinomial', side_effect=scripted_groups([[1]*8, [0]*8, [1,0]*4, [1]*8])):
            result = training.run_training(engine, self.prepared, deadline=time.time()+120, config=config(),
                persist_group=lambda value: groups.append(copy.deepcopy(value)) if value.get('seal_sha256') else None,
                persist_probe=probes.append)
        self.assertEqual(result['status'], 'complete'); self.assertEqual(result['physical']['optimizer_steps'], 6)
        self.assertEqual([s['objective'] for s in result['arms']['routed_fusion']['slots']],
                         ['known_target_ce', 'exact_centered_ddis', 'exact_positive_ce'])
        self.assertEqual(result['arms']['routed_fusion']['slots'][-1]['backward_trajectories'], 1)
        self.assertEqual(result['arms']['routed_fusion']['slots'][-1]['exact_positive_duplicate_graphs_avoided'], 7)
        self.assertEqual(result['curriculum']['parents_observed'], 3)
        self.assertEqual(len(probes), 1); self.assertTrue(probes[0]['passed'])
        self.assertEqual(mc.full_policy_sha256(engine), initial)
        self.assertEqual([s['prompt_sha256'] for s in result['arms']['routed_fusion']['slots']],
                         [s['prompt_sha256'] for s in result['arms']['matched_target_ce']['slots']])
        self.assertTrue(all(g['verification']['verified_rows'] == 8 for g in groups))
        self.assertFalse(result['equal_compute_claimed'])

    def test_nonfinite_replay_persists_safe_vectors_before_gate_failure(self):
        engine = self.engine(); entry = self.prepared['admission']['parents'][0]; parent = entry['parent_id']; saved = []
        original = engine.completion_logps
        def broken(ids, n):
            values = original(ids, n); values[n] = float('nan'); return values
        with patch.object(engine, 'completion_logps', side_effect=broken), \
                patch('torch.multinomial', side_effect=scripted_groups([[1]*8])):
            with self.assertRaisesRegex(ValueError, 'full-policy replay'):
                training.collect_group(engine, self.prepared['training'][parent], entry,
                    admission_sha=self.prepared['pins']['admission_sha256'], cfg=config(), slot=0, allocation={},
                    deadline=time.time()+60, persist=lambda value: saved.append(json.loads(json.dumps(value, allow_nan=False))))
        self.assertEqual(engine.optimizer_attempts, 0)
        self.assertTrue(saved[-1]['verification']['nonfinite_replay_observed'])
        self.assertIsNone(saved[-1]['verification']['max_logp_gap'])
        self.assertEqual(saved[-1]['verification']['failed_row']['nonfinite_values'][0]['value'], 'nan')

    def test_real_end_to_end_exports_independent_audit_and_fresh_reload(self):
        engine = self.engine(); original = mc.full_policy_sha256(engine)
        fixture = SimpleNamespace(model=engine.contract, trainables=engine.trainable_inventory,
                                  tokenizer=engine.tokenizer_admission, probability_tolerance=1e-5)
        with tempfile.TemporaryDirectory() as tmp, patch('torch.multinomial',
                side_effect=scripted_groups([[1]*8, [0]*8, [1,0]*4, [1]*8])):
            root = Path(tmp)/'workflow'; now = time.time()
            report = workflow.run_workflow(engine, self.prepared, deadline=now+180, training_deadline=now+120,
                                           output=root, source_identity='a'*64, config=config())
            self.assertTrue(report['complete']); self.assertEqual(report['physical']['optimizer_steps'], 6)
            audit = controller.validate_result(root, expected_source='a'*64, expected_prepared=self.prepared,
                                                model_identity=engine.base_identity, fixture_contracts=fixture)
            self.assertTrue(audit['complete']); self.assertEqual(audit['training_parent_coverage'], 3)
            self.assertEqual(audit['group_categories'], {'all_wrong': 1, 'mixed': 1, 'all_correct': 1})
            for arm in c.ARMS:
                saved = report['exports'][arm]['checkpoint']; fresh = self.engine()
                fresh.load_checkpoint({k: saved[k] for k in ('root', 'manifest_sha256')})
                self.assertEqual(state_digest(adapter_state(fresh.model)), saved['state_sha256'])
                self.assertEqual(report['evaluation'][arm]['full_requested_denominator'], 2)
                self.assertEqual(report['evaluation'][arm]['completed_parents'], 2)
            self.assertEqual(mc.full_policy_sha256(engine), original)
            self.assertFalse(report['ttt_performed']); self.assertFalse(report['public_answers_used'])
            original_report = (root/'report.json').read_bytes()
            changed = json.loads(original_report); changed['physical'] = dict.fromkeys(controller.COUNTERS, 0)
            (root/'report.json').write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'physical phase conservation'):
                self.audit(root, engine)
            (root/'report.json').write_bytes(original_report)
            changed = json.loads((root/'report.json').read_bytes()); changed['training']['curriculum']['parents_observed'] = 1
            (root/'report.json').write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'curriculum'):
                controller.validate_result(root, expected_source='a'*64, expected_prepared=self.prepared,
                    model_identity=engine.base_identity, fixture_contracts=fixture)

    def audit(self, root, engine, prepared=None):
        fixture = SimpleNamespace(model=engine.contract, trainables=engine.trainable_inventory,
                                  tokenizer=engine.tokenizer_admission, probability_tolerance=1e-5)
        return controller.validate_result(root, expected_source='a'*64, expected_prepared=prepared or self.prepared,
            model_identity=engine.base_identity, fixture_contracts=fixture)

    def test_actual_gradient_path_mismatch_is_preserved_and_prevents_commit(self):
        engine = self.engine(); active = [False]; original_probe = training.cv._preflight; original_logps = engine.completion_logps
        def probed(*args, **kwargs):
            result = original_probe(*args, **kwargs); active[0] = True; return result
        def shifted(ids, n):
            values = original_logps(ids, n)
            if active[0] and torch.is_grad_enabled(): values = values.clone(); values[n] += .25
            return values
        with tempfile.TemporaryDirectory() as tmp, patch.object(training.cv, '_preflight', side_effect=probed), \
                patch.object(engine, 'completion_logps', side_effect=shifted), \
                patch('torch.multinomial', side_effect=scripted_groups([[1]*8, [1,0]*4])):
            root = Path(tmp)/'failed'; now = time.time()
            with self.assertRaisesRegex(ValueError, 'train-gradient replay'):
                workflow.run_workflow(engine, self.prepared, output=root, source_identity='a'*64,
                    deadline=now+120, training_deadline=now+90, config=config())
            self.assertEqual(engine.optimizer_attempts, 0)
            raw = json.loads((root/'gradients/000.json').read_bytes())
            self.assertFalse(raw['commit_admitted']); self.assertGreater(raw['max_logp_gap'], .2)
            self.assertFalse(self.audit(root, engine)['complete'])

    def test_preflight_nonfinite_is_classified_persisted_and_auditable(self):
        engine = self.engine(); original = engine.completion_logps
        def broken(ids, n):
            values = original(ids, n); values[n] = float('nan'); return values
        with tempfile.TemporaryDirectory() as tmp, patch.object(engine, 'completion_logps', side_effect=broken), \
                patch('torch.multinomial', side_effect=scripted_groups([[1]*8])):
            root = Path(tmp)/'failed'; now = time.time()
            with self.assertRaisesRegex(ValueError, 'preflight required'):
                workflow.run_workflow(engine, self.prepared, output=root, source_identity='a'*64,
                    deadline=now+120, training_deadline=now+90, config=config())
            raw = json.loads((root/'probability-preflight.json').read_bytes())
            self.assertFalse(raw['passed']); self.assertTrue(raw['nonfinite_fields'])
            self.assertEqual(engine.optimizer_attempts, 0); self.assertFalse(self.audit(root, engine)['complete'])

    def test_postcommit_deadline_preserves_committed_state_and_charge(self):
        from tools.arc2_goal_sprint_20261017.model import PhaseDeadline
        engine = self.engine(); original = training.check_deadline
        def expire(deadline):
            if engine.optimizer_steps: raise PhaseDeadline('synthetic postcommit deadline')
            return original(deadline)
        with tempfile.TemporaryDirectory() as tmp, patch.object(training, 'check_deadline', side_effect=expire), \
                patch('torch.multinomial', side_effect=scripted_groups([[1]*8, [0]*8])):
            root = Path(tmp)/'partial'; now = time.time()
            report = workflow.run_workflow(engine, self.prepared, output=root, source_identity='a'*64,
                deadline=now+120, training_deadline=now+90, config=config())
            slot = report['training']['arms']['routed_fusion']['slots'][0]
            self.assertEqual(slot['status'], 'deadline'); self.assertTrue(slot['update_returned'])
            self.assertEqual(report['physical']['optimizer_steps'], 1); self.assertFalse(self.audit(root, engine)['complete'])

    def test_saturated_only_routes_are_identical_to_matched_target_ce(self):
        engine = self.engine()
        with patch('torch.multinomial', side_effect=scripted_groups([[1]*8, [0]*8, [1]*8, [0]*8])):
            result = training.run_training(engine, self.prepared, deadline=time.time()+120, config=config())
        left, right = [result['arms'][a]['slots'] for a in ('matched_target_ce', 'routed_fusion')]
        self.assertEqual([s['after_state_sha256'] for s in left], [s['after_state_sha256'] for s in right])
        self.assertEqual(state_digest(result['states']['matched_target_ce']), state_digest(result['states']['routed_fusion']))

    def test_full64_96_panel_and96_optimizer_slots_complete_on_real_tiny_model(self):
        # Complete production panel/update COUNTS on a tiny CPU model, not an
        # official-model feasibility or accuracy claim. No stochastic-result
        # interpretation of scripted synthetic draws is made.
        args_root = Path(self.temp.name)/'full-counts'; args_root.mkdir(exist_ok=True)
        args = corpus(args_root)
        prepared = panels.prepare_panels(*args[:4], **args[4])
        engine = self.engine(); cfg = config(updates=96)
        patterns = [[1]*8]+[([0]*8, [1,0]*4, [1]*8)[i%3] for i in range(96)]
        fixture = SimpleNamespace(model=engine.contract, trainables=engine.trainable_inventory,
                                  tokenizer=engine.tokenizer_admission, probability_tolerance=1e-5)
        with tempfile.TemporaryDirectory() as tmp, patch('torch.multinomial', side_effect=scripted_groups(patterns)):
            root = Path(tmp)/'full'; now = time.time()
            report = workflow.run_workflow(engine, prepared, output=root, source_identity='b'*64,
                deadline=now+300, training_deadline=now+180, config=cfg)
            self.assertTrue(report['complete']); self.assertEqual(report['physical']['optimizer_steps'], 192)
            self.assertEqual(report['training']['curriculum']['parents_observed'], 64)
            self.assertTrue(all(v['completed_parents'] == 96 for v in report['evaluation'].values()))
            audit = controller.validate_result(root, expected_source='b'*64, expected_prepared=prepared,
                model_identity=engine.base_identity, fixture_contracts=fixture)
            self.assertTrue(audit['complete']); self.assertEqual(audit['full_requested_denominator'], 96)

    def test_probability_mismatch_stops_before_any_optimizer(self):
        engine = self.engine(); observed = []
        original = training.collect_group
        def collect(*args, **kwargs):
            original_logps = engine.completion_logps
            def shifted(ids, n):
                values = original_logps(ids, n); values[n] -= .1; return values
            with patch.object(engine, 'completion_logps', side_effect=shifted): return original(*args, **kwargs)
        with patch('torch.multinomial', side_effect=scripted_groups([[1]*8, [1]*8])), \
                patch.object(training, 'collect_group', side_effect=collect):
            with self.assertRaisesRegex(ValueError, 'full-policy replay'):
                training.run_training(engine, self.prepared, deadline=time.time()+120, config=config(),
                    persist=lambda value: observed.append(value))
        self.assertEqual(engine.optimizer_attempts, 0); self.assertTrue(observed[-1]['anchor_restored'])
        self.assertEqual(observed[-1]['status'], 'failed')

    def test_partial_collection_no_loss_and_full_denominator(self):
        engine = self.engine(); original = engine.generate; calls = [0]
        def interrupted(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                from tools.arc2_goal_sprint_20261017.model import PhaseDeadline
                raise PhaseDeadline('synthetic deadline before first training group')
            return original(*args, **kwargs)
        with tempfile.TemporaryDirectory() as tmp, patch.object(engine, 'generate', side_effect=interrupted), \
                patch('torch.multinomial', side_effect=scripted_groups([[1]*8])):
            now = time.time(); report = workflow.run_workflow(engine, self.prepared, output=Path(tmp)/'partial',
                source_identity='a'*64, deadline=now+120, training_deadline=now+90, config=config())
            self.assertFalse(report['complete']); self.assertEqual(report['selected_arm'], 'anchor')
            self.assertEqual(report['physical']['optimizer_steps'], 0)
            for cell in report['evaluation'].values():
                self.assertEqual(cell['full_requested_denominator'], 2); self.assertIsNone(cell['pass2'])
                self.assertEqual(len(cell['records']), 2)
