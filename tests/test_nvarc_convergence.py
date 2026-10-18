"""Real tiny Qwen CPU integration, never official-weight or GPU efficacy proof."""
from __future__ import annotations
import copy
import importlib.util
import time
import unittest
from unittest.mock import patch

MISSING = [n for n in ('torch','transformers','peft','pydantic','tokenizers','safetensors') if importlib.util.find_spec(n) is None]
if not MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine
    from tests.test_nvarc_matched_controls import fixture, config, scripted_groups
    from tools.nvarc_posttrain_20261017 import convergence as cv, matched_controls as mc
    from tools.arc2_goal_sprint_20261017.model import adapter_state, state_digest


def configuration(**changes):
    return {**cv.DEFAULT_CONFIG, 'collection': config(), **changes}


@unittest.skipIf(bool(MISSING), 'Optional compact dependencies absent: ' + ','.join(MISSING))
class ConvergenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def run_flow(self, engine=None, cfg=None):
        training, admission = fixture()
        return cv.run_training(engine or tiny_engine(), training, admission,
            expected_admission_sha256=mc._sha(admission), deadline=time.time()+120,
            config=cfg or configuration())

    def test_default_bounds_are_finite_and_not_reproduction(self):
        bounds = cv.physical_bounds()
        self.assertEqual(bounds['collection_windows'], 13)
        self.assertEqual(bounds['training_trajectory_slots'], 832)
        self.assertEqual(bounds['preflight_trajectory_slots'], 26)
        self.assertEqual(bounds['training_optimizer_attempts'], 16)
        self.assertEqual(cv.SCHEDULES['finite_hybrid'], ('known_target_ce','exact_positive_ce','exact_centered_ddis','known_target_ce'))
        self.assertIn('no std', cv.LOSS_CONTRACT['exact_centered_ddis'])
        for cfg in (configuration(window_seconds=181), configuration(max_model_forward_attempts=True),
                    configuration(training_seconds=float('inf')), configuration(extra='forbidden')):
            with self.assertRaises(ValueError): cv.validate_config(cfg)

    def test_real_multiupdate_af3_hybrid_same_anchor_and_fresh_current_policy(self):
        engine = tiny_engine(); before = mc.full_policy_sha256(engine)
        with patch('torch.multinomial', side_effect=scripted_groups([[1,0]*4]*26)):
            result = self.run_flow(engine)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(len(result['windows']), 13)
        self.assertEqual(result['physical']['optimizer_attempts'], 16)
        self.assertEqual(result['physical']['optimizer_steps'], 16)
        self.assertEqual(before, mc.full_policy_sha256(engine))
        self.assertTrue(result['anchor_restored']); self.assertFalse(result['engine_poisoned'])
        self.assertFalse(result['equal_compute_claimed']); self.assertFalse(result['efficacy_claimed'])
        pools = []
        for arm in cv.ARMS[1:]:
            row = result['arms'][arm]
            self.assertEqual(row['status'], 'complete'); self.assertEqual(len(row['slots']), 4)
            self.assertEqual(row['before_state_sha256'], result['anchor_state_sha256'])
            self.assertEqual(row['optimizer_initial_state_entries'], 0)
            self.assertGreater(row['optimizer_final_state_entries'], 0)
            self.assertTrue(all(s['updated'] for s in row['slots']))
            pools.append(row['slots'][0]['pool_sha256'])
            for slot in row['slots'][1:]:
                window = next(w for w in result['windows'] if w['window_id']==slot['window_id'])
                self.assertEqual(slot['before_state_sha256'], window['capture']['lineage']['anchor_sha256'])
                self.assertNotEqual(slot['before_state_sha256'], result['anchor_state_sha256'])
        self.assertEqual(len(set(pools)), 1)
        self.assertTrue(all(w['preflight']['passed'] for w in result['windows']))
        self.assertTrue(all(w['verification']['verified_rows']==8 for w in result['windows']))
        self.assertEqual(result['arms']['exact_centered_ddis']['physical']['optimizer_steps'],4)
        self.assertEqual(result['arms']['finite_hybrid']['slots'][2]['replayed'],8)

    def test_real_bf16_stable_head_multiupdate_requires_all_probability_paths(self):
        engine=tiny_engine(dtype=torch.bfloat16,probability_policy='fp32-compact-head-v1')
        with patch('torch.multinomial',side_effect=scripted_groups([[1,0]*4]*26)):
            result=self.run_flow(engine)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['physical']['optimizer_steps'],16)
        self.assertEqual(result['physical']['diagnostic_head_projection_attempts'],
            sum(w['preflight']['probe']['extra_projection_attempts'] for w in result['windows']))
        self.assertEqual(result['physical']['diagnostic_head_projection_successes'],
            result['physical']['diagnostic_head_projection_attempts'])
        self.assertGreater(result['physical']['diagnostic_head_projection_attempts'], 0)
        for window in result['windows']:
            gate=window['preflight']
            self.assertTrue(gate['passed']); self.assertFalse(gate['gpu_backward_validated'])
            self.assertEqual(set(gate['additional_stable_admission']),{'eval_nograd','train_grad'})
            self.assertLessEqual(gate['additional_stable_admission']['train_grad']['max_abs_logp_gap'],.05)
            self.assertTrue(gate['probe']['logit_evidence'])

    def test_stable_train_grad_path_mismatch_denies_before_any_collection_or_update(self):
        engine=tiny_engine(dtype=torch.bfloat16,probability_policy='fp32-compact-head-v1')
        original=engine.completion_logps
        def mismatch(ids,n):
            values=original(ids,n)
            if torch.is_grad_enabled():
                values=values.clone();values[n]+=.25
            return values
        with patch.object(engine,'completion_logps',side_effect=mismatch):
            with self.assertRaisesRegex(ValueError,'preflight failed') as caught:
                self.run_flow(engine)
        result=caught.exception.convergence_training_result
        gate=result['windows'][0]['preflight']
        self.assertFalse(gate['passed'])
        self.assertLessEqual(gate['probe']['full_max_abs_logp_gap'],.05)
        self.assertGreater(gate['probe']['additional_replays']['train_grad']['metrics']['max_abs_logp_gap'],.05)
        self.assertEqual(result['windows'][0]['capture']['groups'],[])
        self.assertEqual(result['physical']['diagnostic_head_projection_attempts'], gate['probe']['extra_projection_attempts'])
        self.assertEqual(result['physical']['diagnostic_head_projection_successes'], gate['probe']['extra_projection_successes'])
        self.assertGreater(result['physical']['diagnostic_head_projection_attempts'], 0)
        self.assertEqual(result['physical']['optimizer_attempts'],0)
        self.assertTrue(result['anchor_restored'])

    def test_failed_extra_projection_is_charged_separately_and_cannot_train(self):
        from tools.nvarc_posttrain_20261017.precision import active_head
        engine=tiny_engine(dtype=torch.bfloat16,probability_policy='fp32-compact-head-v1')
        pointer=active_head(engine.model).weight.data_ptr(); original=torch.nn.functional.linear; controls=[0]
        def linear(inputs, weight, bias=None):
            if weight.data_ptr()==pointer and not weight.requires_grad:
                controls[0]+=1
                if controls[0]==2: raise RuntimeError('injected diagnostic legacy GEMM failure')
            return original(inputs,weight,bias)
        with patch('torch.nn.functional.linear',side_effect=linear):
            with self.assertRaisesRegex(ValueError,'preflight failed') as caught:
                self.run_flow(engine)
        result=caught.exception.convergence_training_result
        window=result['windows'][0]
        self.assertEqual(result['physical']['diagnostic_head_projection_attempts'],2)
        self.assertEqual(result['physical']['diagnostic_head_projection_successes'],1)
        self.assertEqual(window['physical']['diagnostic_head_projection_attempts'],2)
        self.assertEqual(window['physical']['diagnostic_head_projection_successes'],1)
        self.assertEqual(result['physical']['optimizer_attempts'],0)
        self.assertEqual(window['capture']['groups'],[])
        self.assertIsNotNone(window['preflight']['probe']['logit_evidence'][0]['actual_logits'])
        self.assertTrue(result['anchor_restored'])

    def test_real_depth_compact_engine_uses_identical_convergence_gate_and_objectives(self):
        from tests.test_nvarc_capacity_factory import engine as depth_engine
        e=depth_engine(); before=mc.full_policy_sha256(e)
        with patch('torch.multinomial',side_effect=scripted_groups([[1,0]*4]*26)):
            result=self.run_flow(e)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['physical']['optimizer_steps'],16)
        self.assertTrue(all(w['preflight']['additional_stable_admission'] for w in result['windows']))
        self.assertEqual(before,mc.full_policy_sha256(e))
        self.assertTrue(result['anchor_restored'])

    def test_no_signal_slots_are_consumed_without_fabricated_ddis(self):
        with patch('torch.multinomial', side_effect=scripted_groups([[0]*8]*26)):
            result = self.run_flow()
        self.assertEqual(result['status'],'complete')
        self.assertEqual(len(result['windows']),13)
        self.assertEqual(result['physical']['optimizer_steps'],6)  # four target + two hybrid target
        self.assertTrue(all(not s['updated'] for s in result['arms']['exact_centered_ddis']['slots']))
        self.assertTrue(all(not s['updated'] for s in result['arms']['exact_positive_ce']['slots']))
        self.assertEqual(sum(w['collection']['groups_attempted'] for w in result['windows']),13)
        self.assertEqual(sum(w['collection']['trajectories_requested'] for w in result['windows']),104)

    def test_preflight_failure_stops_before_collection_preserves_measured_gap(self):
        engine=tiny_engine(); real=engine.completion_logps; before=mc.full_policy_sha256(engine)
        def changed(ids, n):
            values=real(ids,n).clone(); values[n]+=0.25; return values
        with patch.object(engine,'completion_logps',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'preflight failed') as caught:
                self.run_flow(engine)
        result=caught.exception.convergence_training_result
        self.assertEqual(result['physical']['optimizer_attempts'],0)
        self.assertEqual(len(result['windows']),1)
        window=result['windows'][0]
        self.assertEqual(window['capture']['groups'],[])
        self.assertAlmostEqual(window['preflight']['probe']['full_max_abs_logp_gap'],.25,places=5)
        self.assertFalse(window['preflight']['passed'])
        self.assertEqual(before,mc.full_policy_sha256(engine))

    def test_full_pool_failure_after_successful_probe_stops_updates(self):
        engine=tiny_engine(); real=engine.completion_logps; calls=0
        def changed(ids,n):
            nonlocal calls
            values=real(ids,n).clone(); calls+=1
            if calls>8: values[n]+=.25
            return values
        with patch.object(engine,'completion_logps',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'captured behavior') as caught:
                self.run_flow(engine)
        result=caught.exception.convergence_training_result
        window=result['windows'][0]
        self.assertTrue(window['preflight']['passed'])
        self.assertEqual(window['verification']['observed_rows'],1)
        self.assertEqual(window['verification']['verified_rows'],0)
        self.assertIsNotNone(window['verification']['failed_row']['replay_log_probs'])
        self.assertEqual(result['physical']['optimizer_attempts'],0)

    def test_physical_attempt_limit_charges_partial_but_does_not_train(self):
        result=self.run_flow(cfg=configuration(max_model_forward_attempts=1))
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['physical']['model_forward_attempts'],1)
        self.assertEqual(result['physical']['optimizer_attempts'],0)
        self.assertTrue(result['anchor_restored'])
        self.assertFalse(result['engine_poisoned'])

    def test_final_training_persistence_crossing_deadline_invalidates_completion(self):
        engine=tiny_engine(); training,admission=fixture(); now=time.time(); clock=[now]
        def persist(result):
            if result['status']=='complete' and result['anchor_restored']:
                clock[0]=now+121
        with patch.object(cv.time,'time',side_effect=lambda:clock[0]):
            result=cv.run_training(engine,training,admission,expected_admission_sha256=mc._sha(admission),
                deadline=now+120,config=configuration(),persist=persist)
        self.assertEqual(result['status'],'partial')
        self.assertTrue(result['returned_after_deadline'])
        self.assertEqual(result['stop_reason'],'deadline_during_training_persistence')
        self.assertTrue(result['anchor_restored'])

    def test_window_final_persistence_cannot_grant_late_update(self):
        engine=tiny_engine(); training,admission=fixture(); now=time.time(); clock=[now]
        def persist(result):
            if result['status']=='complete':clock[0]=now+121
        with patch.object(cv.time,'time',side_effect=lambda:clock[0]):
            with self.assertRaisesRegex(cv.PhaseDeadline,'finalization') as caught:
                cv.collect_window(engine,training,admission,expected_admission_sha256=mc._sha(admission),
                    config=config(),deadline=now+120,window_id='fixture',persist=persist)
        result=caught.exception.convergence_window_result
        self.assertEqual(result['status'],'deadline')
        self.assertEqual(result['physical']['optimizer_attempts'],0)

    def test_actual_unscripted_sampling_no_external_model_or_forged_reward(self):
        result=self.run_flow()
        self.assertEqual(result['status'],'complete')
        self.assertEqual(len(result['windows']),13)
        for w in result['windows']:
            self.assertEqual(w['capture']['lineage']['policy_sha256'],w['preflight']['policy_before_sha256'])
            self.assertFalse(w['behavior_probabilities_replaced'])
            for group in w['capture']['groups']:
                for row in group['rows']:
                    self.assertEqual(row['reward'],float(cv.parse_completion(row['completion_ids'])==group['training_target']))

if __name__=='__main__': unittest.main()
