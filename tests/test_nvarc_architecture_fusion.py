"""Real tiny-CPU architecture/fusion integration, not a model-quality result.

Only token selections are scripted to exercise all three reward routes. Actual
Qwen3/PEFT forwards, cached/full/gradient replay, AF3 loss, optimizer commits,
checkpoint bytes and fresh architecture reconstruction remain real. These
synthetic examples establish mechanism compatibility, not official-weight
feasibility, wall-matched value or held-out ARC training gains.
"""
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

MISSING = [name for name in ('torch', 'transformers', 'peft', 'tokenizers',
                            'safetensors', 'pydantic')
           if importlib.util.find_spec(name) is None]
if not MISSING:
    import torch
    from safetensors.torch import load_file
    from tests.test_nvarc_posttrain_engine import tiny_engine, example
    from tests.test_nvarc_matched_controls import scripted_groups
    from tests.test_nvarc_matched_workflow import corpus
    from tools.arc2_goal_sprint_20261017.model import adapter_state, state_digest
    from tools.nvarc_capacity_20261018 import model as capacity
    from tools.nvarc_width_20261018 import model as width
    from tools.nvarc_efficient_fusion_20261018 import architecture, contracts, controller, panels, training, workflow
    from tools.nvarc_posttrain_20261017 import convergence, experiment, matched_controls
    from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY


ARCHITECTURES = ('compact', 'baseline', 'depth32', 'moe4_top2', 'width8192')


def engine(kind):
    dense = tiny_engine(dtype=torch.bfloat16, probability_policy=FP32_BACKBONE_POLICY)
    if kind == 'compact':
        return dense
    if kind == 'width8192':
        return width.from_dense(dense, kind)
    return capacity.from_dense(dense, kind, fixture_layers=(0,))


def config():
    return {**contracts.DEFAULT_CONFIG, 'updates': 3, 'microbatch': 8,
            'context_tokens': 96, 'generation_tokens': 2, 'learning_rate': 1e-3}


def fixture_contracts(fresh):
    return SimpleNamespace(model=copy.deepcopy(fresh.contract),
                           trainables=copy.deepcopy(fresh.trainable_inventory),
                           tokenizer=copy.deepcopy(fresh.tokenizer_admission),
                           probability_tolerance=1e-5)


@unittest.skipIf(bool(MISSING), 'Optional actual-ML dependencies absent: ' + ','.join(MISSING))
class ArchitectureFusionCPU(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.temp = tempfile.TemporaryDirectory()
        args = corpus(Path(cls.temp.name))
        cls.prepared = panels.prepare_panels(*args[:4], **args[4], train_count=3, dev_count=2)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def assert_exact_state(self, actual, expected):
        self.assertEqual(set(actual), set(expected))
        for name in expected:
            self.assertTrue(torch.equal(actual[name], expected[name]), name)

    def assert_architecture_trainables(self, kind, initial, trained):
        """Verify the expanded tensors, not merely the compact head, changed."""
        if kind == 'depth32':
            names = [n for n in trained if '.layers.1.' in n and '.lora_B.' in n]
        elif kind == 'moe4_top2':
            routers = [n for n in trained if '.router.weight' in n]
            self.assertTrue(routers)
            self.assertTrue(any(not torch.equal(trained[n], initial[n]) for n in routers))
            for index in range(4):
                self.assertTrue(any(f'.experts.{index}.' in n for n in trained))
            names = [n for n in trained if '.experts.' in n and '.lora_B.' in n]
        elif kind == 'width8192':
            names = [n for n in trained if '.mlp.up_proj.lora_B.' in n]
            self.assertTrue(names)
            for name in names:
                self.assertEqual(trained[name].shape[0], 85)
                self.assertGreater(trained[name][64:].abs().sum().item(), 0)
        else:
            names = [n for n in trained if '.lora_B.' in n]
        self.assertTrue(names)
        self.assertTrue(any(not torch.equal(trained[n], initial[n]) for n in names))

    def test_real_shared_workflow_all_routes_independent_audit_and_fresh_reload(self):
        for kind in ARCHITECTURES:
            with self.subTest(architecture=kind), tempfile.TemporaryDirectory() as directory:
                current = engine(kind)
                initial = adapter_state(current.model)
                policy = matched_controls.full_policy_sha256(current)
                frozen = {n: p.detach().clone() for n, p in current.model.named_parameters()
                          if not p.requires_grad}
                rng = current.generator.get_state().clone()
                root = Path(directory) / 'workflow'
                now = time.time()
                # One probe group, then all-wrong SFT, mixed AF3, all-correct CE.
                # The shared fixture checks real positive full16 probabilities.
                with patch('torch.multinomial', side_effect=scripted_groups(
                        [[1] * 8, [0] * 8, [1, 0] * 4, [1] * 8])):
                    report = workflow.run_workflow(current, self.prepared,
                        deadline=now + 180, training_deadline=now + 120, output=root,
                        source_identity='a' * 64, config=config())
                self.assertTrue(report['complete'])
                self.assertEqual(report['physical']['optimizer_steps'], 6)
                self.assertEqual(report['physical']['optimizer_attempts'], 6)
                self.assertEqual(matched_controls.full_policy_sha256(current), policy)
                self.assert_exact_state(adapter_state(current.model), initial)
                self.assert_exact_state({n: p for n, p in current.model.named_parameters()
                                         if not p.requires_grad}, frozen)
                self.assertTrue(torch.equal(current.generator.get_state(), rng))
                self.assertTrue(all(p.grad is None for p in current.parameters))

                fresh_anchor = engine(kind)
                audit = controller.validate_result(root, expected_source='a' * 64,
                    expected_prepared=self.prepared, model_identity=fresh_anchor.base_identity,
                    fixture_contracts=fixture_contracts(fresh_anchor))
                self.assertTrue(audit['complete'])
                self.assertEqual(audit['group_categories'],
                                 {'all_wrong': 1, 'mixed': 1, 'all_correct': 1})
                self.assertEqual(audit['training_parent_coverage'], 3)
                probe = json.loads((root / 'probability-preflight.json').read_bytes())
                self.assertTrue(probe['passed'])
                self.assertEqual(probe['policy_before_sha256'], policy)
                self.assertEqual(probe['policy_after_sha256'], policy)
                raw = probe['probe']
                self.assertEqual(raw['cached_replay']['status'], 'completed')
                self.assertEqual(len(raw['full_replay']), 8)
                self.assertLessEqual(raw['cached_max_abs_logp_gap'], 1e-5)
                self.assertLessEqual(raw['full_max_abs_logp_gap'], 1e-5)
                for mode in ('eval_nograd', 'train_grad'):
                    replay = raw['additional_replays'][mode]
                    self.assertEqual(replay['status'], 'completed')
                    self.assertLessEqual(replay['metrics']['max_abs_logp_gap'], 1e-5)
                self.assertTrue(any(row['grad_enabled'] and row['actual_requires_grad']
                                    for row in raw['logit_evidence']))
                self.assertEqual(raw['engine_counter_deltas']['optimizer_steps'], 0)
                self.assertFalse(raw['training_authorized'])

                routed = report['training']['arms']['routed_fusion']['slots']
                self.assertEqual([row['objective'] for row in routed],
                    ['known_target_ce', 'exact_centered_ddis', 'exact_positive_ce'])
                for arm in contracts.ARMS[1:]:
                    for slot in report['training']['arms'][arm]['slots']:
                        self.assertTrue(slot['updated'])
                        self.assertNotEqual(slot['before_state_sha256'], slot['after_state_sha256'])
                gradient = json.loads((root / 'gradients' / '001.json').read_bytes())
                self.assertTrue(gradient['commit_admitted'])
                self.assertEqual(gradient['verified_rows'], 8)
                self.assertLessEqual(gradient['max_logp_gap'], 1e-5)
                groups = [json.loads((root / 'groups' / f'{i:03}.json').read_bytes()) for i in range(3)]
                self.assertEqual(len({row['lineage']['policy_sha256'] for row in groups}), 3)
                self.assertTrue(all(row['verification']['verified_rows'] == 8 for row in groups))

                for arm in contracts.ARMS:
                    saved = report['exports'][arm]['checkpoint']
                    tensors = load_file(str(Path(saved['root']) / 'trainable_state.safetensors'))
                    fresh = engine(kind)
                    fresh.load_checkpoint({k: saved[k] for k in ('root', 'manifest_sha256')})
                    self.assert_exact_state(adapter_state(fresh.model), tensors)
                    self.assertEqual(state_digest(tensors), saved['state_sha256'])
                    self.assertEqual(set(tensors), set(fresh.trainable_inventory['tensors']))
                    architecture.admit_engine(fresh, require_fp32=True)
                    self.assert_exact_state({n: p for n, p in fresh.model.named_parameters()
                                             if not p.requires_grad}, frozen)
                    if arm == 'anchor':
                        self.assert_exact_state(tensors, initial)
                    else:
                        self.assert_architecture_trainables(kind, initial, tensors)
                    if arm == 'routed_fusion':
                        # Re-execute the learned reconstructed policy. An
                        # identity-preserving initial probe alone cannot show
                        # parity after experts/router/expanded adapters learn.
                        loaded_policy = matched_controls.full_policy_sha256(fresh)
                        with patch('torch.multinomial', side_effect=scripted_groups([[1] * 8])):
                            loaded_probe = convergence._preflight(fresh, example()['prompt_ids'],
                                training.collection_config(config()), deadline=time.time() + 60,
                                policy_sha=loaded_policy,
                                hash_cost={'calls': 0, 'tensor_bytes': 0, 'wall_seconds': 0.0})
                        self.assertTrue(loaded_probe['passed'])
                        self.assertEqual(loaded_probe['policy_after_sha256'], loaded_policy)
                        self.assertEqual(fresh.optimizer_attempts, 0)
                        self.assert_exact_state(adapter_state(fresh.model), tensors)
                    self.assertEqual(report['evaluation'][arm]['completed_parents'], 2)
                    self.assertEqual(report['evaluation'][arm]['full_requested_denominator'], 2)
                # A real, incompatible reconstruction cannot consume this file.
                saved = report['exports']['routed_fusion']['checkpoint']
                wrong = engine('width8192' if kind != 'width8192' else 'moe4_top2')
                before = adapter_state(wrong.model)
                with self.assertRaises(ValueError):
                    wrong.load_checkpoint({k: saved[k] for k in ('root', 'manifest_sha256')})
                self.assert_exact_state(adapter_state(wrong.model), before)
                self.assertFalse(report['ttt_performed'])
                self.assertFalse(report['efficacy_claimed'])
                self.assertFalse(report['public_answers_used'])

    def test_unreviewed_subclasses_and_mutated_architectures_fail_before_forward(self):
        for kind in ARCHITECTURES:
            with self.subTest(architecture=kind, change='unreviewed subclass'):
                current = engine(kind)
                current.__class__ = type('UnreviewedEngine', (type(current),), {})
                before = current.forward_calls
                with self.assertRaises(ValueError):
                    architecture.admit_engine(current, require_fp32=True)
                self.assertEqual(current.forward_calls, before)
                self.assertEqual(current.optimizer_attempts, 0)
            with self.subTest(architecture=kind, change='structure'):
                current = engine(kind)
                before = current.forward_calls
                if kind == 'moe4_top2':
                    current.model.get_base_model().model.layers[0].mlp.top_k = 1
                elif kind == 'width8192':
                    current.model.config.intermediate_size += 1
                elif kind in ('baseline', 'depth32'):
                    current.contract['capacity_v2']['treatment'] = 'width8192'
                else:
                    current.trainable_inventory['rank'] += 1
                with self.assertRaises(ValueError):
                    training.run_training(current, self.prepared,
                                          deadline=time.time() + 60, config=config())
                self.assertEqual(current.forward_calls, before)
                self.assertEqual(current.optimizer_attempts, 0)

    def test_historical_precision_cannot_enter_fusion(self):
        current = tiny_engine(dtype=torch.bfloat16)
        with self.assertRaises(ValueError):
            training.run_training(current, self.prepared,
                                  deadline=time.time() + 60, config=config())
        self.assertEqual(current.forward_calls, 0)
        self.assertEqual(current.optimizer_attempts, 0)

    def test_stale_real_behavior_group_rejected_before_second_update(self):
        for kind in ('depth32', 'moe4_top2', 'width8192'):
            with self.subTest(architecture=kind):
                current = engine(kind)
                policy = matched_controls.full_policy_sha256(current)
                original = training.collect_group
                collected = []
                def replay_old_group(*args, **kwargs):
                    if collected:
                        return copy.deepcopy(collected[0])
                    value = original(*args, **kwargs)
                    collected.append(copy.deepcopy(value))
                    return value
                with patch('torch.multinomial', side_effect=scripted_groups([[1] * 8, [0] * 8])), \
                        patch.object(training, 'collect_group', side_effect=replay_old_group):
                    with self.assertRaisesRegex(ValueError, 'current policy differs'):
                        training.run_training(current, self.prepared,
                                              deadline=time.time() + 120, config=config())
                self.assertEqual(len(collected), 1)
                self.assertEqual(collected[0]['verification']['verified_rows'], 8)
                self.assertEqual(current.optimizer_steps, 2)
                self.assertEqual(current.optimizer_attempts, 2)
                self.assertEqual(matched_controls.full_policy_sha256(current), policy)
                self.assertFalse(current._fatal_update)

    def test_real_demo_only_ttt_resets_each_parent_and_restores_function(self):
        # Separate from the deliberately no-TTT fusion selection workflow.
        task = {'train': [{'input': [[1]], 'output': [[2]]},
                          {'input': [[3]], 'output': [[4]]},
                          {'input': [[5]], 'output': [[6]]}]}
        tasks = {'synthetic-a': copy.deepcopy(task), 'synthetic-b': copy.deepcopy(task)}
        cfg = {'ttt_lr': 1e-3, 'context_tokens': 96, 'generation_tokens': 2,
               'dev_parents': 2, 'evaluation_seed': 17}
        for kind in ARCHITECTURES:
            with self.subTest(architecture=kind):
                current = engine(kind)
                initial = adapter_state(current.model)
                policy = matched_controls.full_policy_sha256(current)
                row = example()
                tokens = row['prompt_ids'] + row['completion_ids']
                with torch.no_grad():
                    original_logps = current.completion_logps(tokens, len(row['prompt_ids'])).clone()
                original_adapt = experiment.adapt_task
                entries, exits = [], []
                def observed_adapt(*args, **kwargs):
                    entries.append(state_digest(adapter_state(current.model)))
                    value = original_adapt(*args, **kwargs)
                    exits.append(state_digest(adapter_state(current.model)))
                    return value
                with patch.object(experiment, 'adapt_task', side_effect=observed_adapt):
                    report = experiment.evaluate_panel(current, tasks, cfg,
                        deadline=time.time() + 90, audit=lambda *args, **kwargs: None,
                        ttt_steps=2, views=2, ids=list(tasks))
                self.assertTrue(report['complete'])
                self.assertEqual(current.optimizer_steps, 4)
                self.assertEqual(entries, [state_digest(initial)] * 2)
                self.assertTrue(all(value != state_digest(initial) for value in exits))
                self.assertTrue(all(row['ttt']['data'] == 'demonstrations-only'
                                    for row in report['records']))
                self.assert_exact_state(adapter_state(current.model), initial)
                self.assertEqual(matched_controls.full_policy_sha256(current), policy)
                with torch.no_grad():
                    restored = current.completion_logps(tokens, len(row['prompt_ids']))
                torch.testing.assert_close(restored, original_logps, rtol=0, atol=0)


if __name__ == '__main__':
    unittest.main()
