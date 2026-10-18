"""Train-derived adaptation diagnostic contracts, not official model evidence."""
import copy
import importlib.util
import math
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

MISSING = [name for name in ('torch', 'transformers', 'peft', 'pydantic') if importlib.util.find_spec(name) is None]
if not MISSING:
    import torch
    from tools.nvarc_posttrain_20261017 import stability as st
    from tools.nvarc_posttrain_20261017 import experiment as ex
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, state_digest


def task():
    return {'train': [{'input': [[1]], 'output': [[1]]}, {'input': [[2]], 'output': [[2]]},
                      {'input': [[3]], 'output': [[3]]}], 'test': [{'input': [[9]]}]}


def distinct_task(index):
    height, width = 1 + index // 20, 6 + index % 20
    return {'train': [{'input': [[c] * width for _ in range(height)],
                       'output': [[c] * width for _ in range(height)]} for c in (1, 2, 3)],
            'test': [{'input': [[9]]}]}


def config():
    return {'context_tokens': 8192, 'generation_tokens': 931, 'ttt_steps': 32, 'ttt_lr': 5e-5,
            'evaluation_seed': 20261017}


@unittest.skipIf(bool(MISSING), 'Optional compact dependencies missing: ' + ', '.join(MISSING))
class StabilityTests(unittest.TestCase):
    def engine(self, *, damage=False):
        class Fake:
            def __init__(self):
                self.model = torch.nn.Linear(1, 1, bias=False)
                with torch.no_grad(): self.model.weight.zero_()
                for key in st.COUNTERS: setattr(self, key, 0)
                self.examples = []
            def nll(self, example):
                self.forward_calls += 1
                return float(self.model.weight.detach().sum()) + 1.
            def sft_step(self, example, optimizer, deadline):
                self.examples.append(copy.deepcopy(example))
                with torch.no_grad(): self.model.weight.add_(.01)
                self.optimizer_steps += 1; self.optimizer_attempts += 1; self.forward_calls += 1
                return {'updated': True, 'gradient_norm': .5, 'loss': .1}
            def generate(self, prompt_ids, *, max_new_tokens, sample, deadline):
                start = max(i for i, value in enumerate(prompt_ids) if value == 11) + 2
                end = prompt_ids.index(15, start)
                grid = prompt_ids[start:end]
                if damage and float(self.model.weight.detach().sum()) > .01:
                    grid = [((value + 1) % 10 if value < 10 else value) for value in grid]
                completion = grid + [15]
                self.forward_calls += len(completion); self.sampled_tokens += len(completion)
                self.generation_forward_attempts += len(completion)
                self.generation_input_tokens += len(prompt_ids) + len(completion) - 1
                self.generation_row_token_slots += len(completion)
                return [{'input_ids': prompt_ids + completion, 'prompt_length': len(prompt_ids),
                    'completion_tokens': len(completion), 'stop': 'completed',
                    'behavior_log_probs': [0.] * len(prompt_ids) + [-.2] * len(completion)}]
        return Fake()

    def test_new_panel_is_deterministic_disjoint_and_ttt_eligible(self):
        dev = {f'parent{i:03}': distinct_task(i) for i in range(100)}
        first, excluded = st.select_panel(dev)
        second, _ = st.select_panel(dict(reversed(list(dev.items()))))
        self.assertEqual(first, second); self.assertEqual(len(first), 32)
        self.assertEqual(len(excluded), 24); self.assertFalse(set(first) & set(excluded))
        with self.assertRaises(ValueError): st.select_panel(dev, count=True)
        with self.assertRaises(ValueError): st.select_panel({'one': task()}, count=1, previous_count=1)

    def test_actual_callable_compares_same_views_and_restores_every_parent(self):
        engine = self.engine(damage=True); before = state_digest(adapter_state(engine.model))
        result = st.run_stability(engine, {'a': distinct_task(0), 'b': distinct_task(1)}, config(), deadline=math.inf,
                                  audit=Mock(), count=2, previous_count=0)
        self.assertTrue(result['complete']); self.assertTrue(result['causal_comparison_eligible'])
        self.assertEqual(result['summary']['no_ttt']['pass2'], 2)
        self.assertEqual(result['summary']['ttt32']['pass2'], 0)
        self.assertEqual(result['paired_change']['pass2'], {'wins': 0, 'losses': 2, 'ties': 0})
        self.assertEqual(result['physical_work']['optimizer_steps'], 64)
        self.assertEqual(state_digest(adapter_state(engine.model)), before)
        self.assertTrue(all(r['reset']['absolute_probe_nll_drift'] == 0 for r in result['records']))
        self.assertFalse(result['public_scoring_performed'])
        self.assertFalse(result['architecture_expansion_tested'])

    def test_known_variant_aliases_cannot_form_new_panel(self):
        dev = {f'alias{i:03}': task() for i in range(100)}
        with self.assertRaisesRegex(ValueError, 'known-variant groups'):
            st.select_panel(dev)
        with self.assertRaisesRegex(ValueError, 'known-variant groups'):
            st.select_panel(dev, count=2, previous_count=0)
        dev = {f'parent{i:03}': distinct_task(i) for i in range(100)}
        previous = ex.panel_ids(dev, 24)
        for index, key in enumerate(previous):
            dev[f'alias{index:03}'] = copy.deepcopy(dev[key])
        chosen, excluded = st.select_panel(dev)
        selected_groups = {st._variant_group(dev[key]) for key in chosen}
        excluded_groups = {st._variant_group(dev[key]) for key in excluded}
        self.assertEqual(len(selected_groups), 32)
        self.assertFalse(selected_groups & excluded_groups)

    def test_parameter_reset_without_functional_reset_denies_causal_claim(self):
        engine = self.engine(); original = engine.nll; calls = []
        def drift(example):
            value = original(example); calls.append(value)
            return value + (1. if len(calls) == 2 else 0.)
        engine.nll = drift
        result = st.run_stability(engine, {'a': task()}, config(), deadline=math.inf,
                                  audit=Mock(), count=1, previous_count=0)
        self.assertFalse(result['complete']); self.assertFalse(result['causal_comparison_eligible'])
        self.assertEqual(result['complete_parents'], 0)
        self.assertEqual(result['stop_reason'], 'functional_anchor_reset_drift')
        reset = result['records'][0]['reset']
        self.assertTrue(reset['parameter_state_verified'])
        self.assertFalse(reset['functional_probe_verified']); self.assertFalse(reset['verified'])
        self.assertEqual(reset['absolute_probe_nll_drift'], 1.)
        self.assertEqual(result['full_requested_denominator'], 1)

    def test_raw_token_verifier_detects_prompt_candidate_logprob_and_view_corruption(self):
        engine = self.engine(); cfg = {**config(), 'retain_token_evidence': True}
        predicted = ex.infer_query(engine, task(), [[5]], cfg, task_id='train', views=2, deadline=math.inf)
        self.assertTrue(st.verify_prediction(predicted, task(), [[5]], cfg, task_id='train', views=2)['verified'])
        def prompt(r): r['views'][0]['token_evidence']['prompt_ids'][0] = 0
        def candidate(r): r['ranked_grids'] = [[[9]]]
        def logprob(r): r['views'][0]['token_evidence']['completion_log_probs'][0] = float('nan')
        def repeated(r): r['views'][1]['view'] = r['views'][0]['view']
        for mutate in (prompt, candidate, logprob, repeated):
            with self.subTest(mutation=mutate.__name__):
                altered = copy.deepcopy(predicted); mutate(altered)
                with self.assertRaises(ValueError):
                    st.verify_prediction(altered, task(), [[5]], cfg, task_id='train', views=2)

    def test_deadline_preserves_incomplete_denominator_and_anchor(self):
        engine = self.engine(); before = state_digest(adapter_state(engine.model)); persist = Mock()
        with patch.object(st, 'adapt_task', side_effect=PhaseDeadline('bounded')):
            report = st.run_stability(engine, {'a': task()}, config(), deadline=math.inf,
                                      audit=Mock(), count=1, previous_count=0, persist=persist)
        self.assertFalse(report['complete']); self.assertFalse(report['causal_comparison_eligible'])
        self.assertEqual(report['full_requested_denominator'], 1)
        self.assertEqual(report['complete_parents'], 0)
        self.assertEqual(report['stop_reason'], 'original_phase_deadline')
        self.assertEqual(state_digest(adapter_state(engine.model)), before)
        persist.assert_called()

    def test_unknown_batch_factor_and_changed_learning_recipe_rejected(self):
        for change in ({'inference_batch_size': 2}, {'ttt_lr': 1e-4}, {'ttt_steps': 8}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                st.run_stability(self.engine(), {'a': task()}, {**config(), **change},
                                 deadline=math.inf, audit=Mock(), count=1, previous_count=0)

    def test_gradient_exception_restores_anchor_but_is_not_hidden(self):
        engine = self.engine(); before = state_digest(adapter_state(engine.model))
        def fail(*args, **kwargs):
            with torch.no_grad(): engine.model.weight.add_(2.)
            raise FloatingPointError('fatal numerical failure')
        with patch.object(st, 'adapt_task', side_effect=fail), self.assertRaises(FloatingPointError):
            st.run_stability(engine, {'a': task()}, config(), deadline=math.inf, audit=Mock(), count=1, previous_count=0)
        self.assertEqual(state_digest(adapter_state(engine.model)), before)

    def test_returned_engine_prompt_not_expected_prompt_is_retained_for_audit(self):
        engine = self.engine(); original = engine.generate
        def corrupt(*args, **kwargs):
            rows = original(*args, **kwargs); rows[0]['input_ids'][0] = 0; return rows
        engine.generate = corrupt
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            st.run_stability(engine, {'a': task()}, config(), deadline=math.inf, audit=Mock(), count=1, previous_count=0)

    def test_real_tiny_compact_engine_updates_and_resets_through_full_diagnostic(self):
        from tests.test_nvarc_posttrain_engine import tiny_engine
        engine = tiny_engine()
        torch.set_num_threads(1)
        before = state_digest(adapter_state(engine.model))
        result = st.run_stability(engine, {'a': task()}, {**config(), 'generation_tokens': 16},
                                  deadline=math.inf, audit=Mock(), count=1, previous_count=0)
        self.assertTrue(result['complete'])
        self.assertEqual(result['physical_work']['optimizer_steps'], 32)
        self.assertNotEqual(result['records'][0]['adapted_state_sha256'], before)
        self.assertEqual(state_digest(adapter_state(engine.model)), before)


if __name__ == '__main__': unittest.main()
