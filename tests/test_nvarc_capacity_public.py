"""Synthetic all167-query CPU mechanism tests, not PUBLIC accuracy evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

_MISSING = [name for name in ('torch', 'transformers', 'peft', 'tokenizers', 'safetensors')
            if importlib.util.find_spec(name) is None]
if not _MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine
    from tools.arc2_goal_sprint_20261017.data import inference_views, view_inputs
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline
    from tools.nvarc_capacity_20261018.model import from_dense, TREATMENTS
    from tools.nvarc_capacity_20261018 import public as p
    from tools.nvarc_posttrain_20261017.codec import encode_example
    from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
    from tools.nvarc_posttrain_20261017.score import validate_pool_inventory
    from tools.nvarc_posttrain_20261017.stability import verify_prediction


CFG = {'context_tokens': 64, 'generation_tokens': 2, 'evaluation_seed': 20261018,
       'views': 2, 'ttt_steps': 0}
SOURCE, PROTOCOL, REPORT = 'a' * 64, 'b' * 64, 'c' * 64


def solver():
    return {f'fixture-{index:03}': {'train': [{'input': [[1]], 'output': [[2]]}],
            'test': [{'input': [[3]]} for _ in range(2 if index < 47 else 1)]}
            for index in range(120)}


def frozen():
    return {'comparison_complete': True, 'comparison_report_sha256': REPORT,
        'protocol_sha256': PROTOCOL, 'source_identity': SOURCE, 'selected_treatment': 'initial_anchor',
        'selection_frozen_before_public': True, 'public_config': copy.deepcopy(CFG)}


def engine(treatment='baseline'):
    dense = tiny_engine(dtype=torch.bfloat16, probability_policy=FP32_BACKBONE_POLICY)
    return from_dense(dense, treatment, fixture_layers=(0, 1))


@unittest.skipIf(bool(_MISSING), 'Optional tiny capacity dependencies missing: ' + ', '.join(_MISSING))
class PublicCapacityCPU(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.pins = {}
        for treatment in TREATMENTS:
            e = engine(treatment)
            saved = e.save_checkpoint(cls.root / 'checkpoints' / treatment, origin={
                'phase': 'pre_public', 'public_ttt_applied': False, 'public_labels_used': False,
                'treatment': treatment, 'source_identity': SOURCE, 'protocol_sha256': PROTOCOL})
            cls.pins[treatment] = {key: saved[key] for key in ('root', 'manifest_sha256', 'state_sha256')}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fresh(self, treatment='baseline'):
        e = engine(treatment)
        pin = self.pins[treatment]
        e.load_checkpoint({key: pin[key] for key in ('root', 'manifest_sha256')})
        return e

    def run_arm(self, e=None, *, treatment='baseline', public=None, selection=None, pin=None, config=None, deadline=None):
        output = Path(tempfile.mkdtemp(dir=self.root)) / 'public'
        report = p.run_public_diagnostic(e or self.fresh(treatment), solver_payload=solver() if public is None else public,
            frozen_selection=frozen() if selection is None else selection,
            checkpoint_pin=self.pins[treatment] if pin is None else pin,
            output_dir=output, treatment=treatment, deadline=time.time() + 120 if deadline is None else deadline,
            config=CFG if config is None else config)
        checked = p.verify_public_artifacts(output, solver_payload=solver() if public is None else public,
            frozen_selection=frozen() if selection is None else selection,
            checkpoint_pin=self.pins[treatment] if pin is None else pin, treatment=treatment)
        self.assertTrue(checked['verified'])
        from tools.arc_offline_evaluation import validate_pools
        validate_pools(solver() if public is None else public, json.loads((output / 'pools.json').read_bytes()))
        self.assertEqual(checked['completed_views'], report['completed_views'])
        return report, output

    def test_actual_three_arm_generation_all167_same_recipe_and_raw_reconstruction(self):
        protocol_hashes = set()
        for treatment in TREATMENTS:
            with self.subTest(treatment=treatment):
                e = self.fresh(treatment)
                selection = frozen(); unchanged = copy.deepcopy(selection)
                report, output = self.run_arm(e, treatment=treatment, selection=selection)
                self.assertTrue(report['complete'], report)
                self.assertEqual(selection, unchanged)
                self.assertEqual(report['completed_views'], 334)
                self.assertEqual(report['attempted_views'], 334)
                self.assertEqual(report['completed_queries'], 167)
                self.assertEqual(report['failed_views'], 0)
                self.assertGreater(report['physical']['forward_calls'], 0)
                self.assertEqual(report['physical']['generation_forward_attempts'], report['physical']['forward_calls'])
                self.assertEqual(report['physical']['optimizer_steps'], 0)
                self.assertTrue(report['checkpoint_state_unchanged'])
                self.assertFalse(report['prediction_sealed'])
                self.assertFalse(report['public_scoring_performed'])
                self.assertFalse(report['clean_generalization_claimed'])
                protocol_hashes.add(report['protocol_sha256'])
                pools = json.loads((output / 'pools.json').read_bytes())
                validate_pool_inventory(pools)
                full = json.loads((output / 'full-candidate-pools.json').read_bytes())
                self.assertEqual(len(full['records']), 167)
                public = solver()
                for row in full['records']:
                    key, index = row['task_id'], row['test_index']
                    verification = verify_prediction(row, public[key], public[key]['test'][index]['input'], CFG,
                                                     task_id=key, views=2)
                    self.assertEqual(verification['completed_views'], 2)
                journal = [json.loads(line) for line in (output / 'view-attempts.jsonl').read_bytes().splitlines()]
                self.assertEqual([a['view'] for a in journal], [0] * 167 + [1] * 167)
                first, second = journal[:167], journal[167:]
                self.assertEqual([(a['task_id'], a['test_index']) for a in first],
                                 [(a['task_id'], a['test_index']) for a in second])
                self.assertEqual([(a['task_id'], a['test_index']) for a in first],
                                 [(key, i) for key in sorted(public) for i in range(len(public[key]['test']))])
                for name, artifact in report['private_artifacts'].items():
                    path = output / artifact['path']
                    self.assertEqual(name, artifact['path'])
                    self.assertEqual(len(path.read_bytes()), artifact['bytes'])
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact['sha256'])
        self.assertEqual(len(protocol_hashes), 1)

    def test_expired_deadline_still_writes_all167_unknown_queries(self):
        report, output = self.run_arm(deadline=time.time() - 1)
        self.assertFalse(report['complete']); self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['attempted_views'], 0)
        self.assertEqual(report['completed_views'], 0)
        pools = json.loads((output / 'pools.json').read_bytes()); validate_pool_inventory(pools)
        self.assertTrue(all(t['status'] == 'not_executed' and not t['ranked_grids']
                            for row in pools['records'] for t in row['tests']))
        self.assertTrue(all(value == 0 for value in report['physical'].values()))

    def test_partial_deadline_after_first_pass_keeps_all167_and_no_retries(self):
        e = self.fresh()
        actual = e.generate
        calls = 0
        def interrupt(prompt_ids, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 170:
                kwargs['deadline'] = time.time() - 1
            return actual(prompt_ids, **kwargs)
        with patch.object(e, 'generate', side_effect=interrupt):
            report, output = self.run_arm(e)
        self.assertEqual(calls, 170)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['completed_views'], 169)
        self.assertEqual(report['failed_views'], 1)
        self.assertEqual(report['completed_queries'], 2)
        pools = json.loads((output / 'pools.json').read_bytes()); validate_pool_inventory(pools)
        full = json.loads((output / 'full-candidate-pools.json').read_bytes())
        self.assertTrue(all(len(row['views']) >= 1 for row in full['records']))
        failure = full['records'][2]['attempts'][-1]
        self.assertEqual(failure['status'], 'deadline')
        self.assertEqual(failure['interrupted_trace']['status'], 'failed')
        self.assertEqual(failure['physical']['generation_forward_attempts'], 0)
        self.assertEqual(sum(a['physical']['sampled_tokens'] for row in full['records'] for a in row['attempts']),
                         report['physical']['sampled_tokens'])

    def test_interrupted_decode_keeps_raw_partial_tokens_and_physical_charge(self):
        e = self.fresh()
        calls = 0
        def limit(_deadline):
            nonlocal calls
            calls += 1
            if calls == 4:  # First token committed; second decode not submitted.
                raise PhaseDeadline('synthetic mid-view hard deadline')
        with patch('tools.nvarc_posttrain_20261017.engine.check_deadline', side_effect=limit):
            report, output = self.run_arm(e)
        self.assertFalse(report['complete'])
        self.assertEqual(report['completed_views'], 0)
        self.assertEqual(report['attempted_views'], 1)
        self.assertEqual(report['physical']['generation_forward_attempts'], 1)
        self.assertEqual(report['physical']['sampled_tokens'], 1)
        full = json.loads((output / 'full-candidate-pools.json').read_bytes())
        attempt = full['records'][0]['attempts'][0]
        self.assertEqual(len(attempt['interrupted_trace']['completion_ids'][0]), 1)
        self.assertEqual(attempt['physical']['sampled_tokens'], 1)
        self.assertEqual(full['records'][0]['ranked_grids'], [])

    def test_failed_forward_is_charged_once_without_rescue(self):
        e = self.fresh()
        with patch.object(e.model, 'forward', side_effect=RuntimeError('synthetic kernel failure')):
            report, output = self.run_arm(e)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['attempted_views'], 1)
        self.assertEqual(report['failed_views'], 1)
        self.assertEqual(report['physical']['generation_forward_attempts'], 1)
        self.assertEqual(report['physical']['forward_calls'], 0)
        self.assertGreater(report['physical']['generation_input_tokens'], 0)
        validate_pool_inventory(json.loads((output / 'pools.json').read_bytes()))

    def test_reject_answers_drop_tasks_queries_and_extra_fields_before_generation(self):
        mutations = [lambda v: v['fixture-000']['test'][0].update(output=[[4]]),
                     lambda v: v.pop('fixture-000'),
                     lambda v: v['fixture-000']['test'].pop(),
                     lambda v: v['fixture-000'].update(score=1),
                     lambda v: v['fixture-000']['train'][0].update(target=[[4]]),
                     lambda v: v['fixture-000']['test'][0].update(input=[[True]])]
        for mutate in mutations:
            bad = solver(); mutate(bad)
            e = self.fresh()
            with self.assertRaises(ValueError):
                self.run_arm(e, public=bad)
            self.assertEqual(e.forward_calls, 0)

    def test_reject_unfrozen_changed_recipe_and_checkpoint_contract(self):
        for key, value in [('comparison_complete', False), ('selection_frozen_before_public', False),
                           ('comparison_report_sha256', 'unknown'), ('selected_treatment', 'public_best'),
                           ('public_config', {**CFG, 'views': 8})]:
            e = self.fresh(); selection = frozen(); selection[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_arm(e, selection=selection)
            self.assertEqual(e.forward_calls, 0)
        for key in ('manifest_sha256', 'state_sha256'):
            e = self.fresh(); pin = {**self.pins['baseline'], key: 'd' * 64}
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.run_arm(e, pin=pin)
        e = self.fresh(); e._checkpoint_loaded = False
        with self.assertRaises(ValueError): self.run_arm(e)
        with self.assertRaises(ValueError): p.validate_config(CFG, fixture=False)
        with self.assertRaises(ValueError): self.run_arm(config={**CFG, 'ttt_steps': 1})

    def test_cpu_artifact_import_does_not_load_torch(self):
        code = ('import sys; from tools.nvarc_capacity_20261018.public import '
                'verify_public_artifacts,write_unexecuted_public; assert "torch" not in sys.modules')
        subprocess.run([sys.executable, '-c', code], check=True)

    def test_unexecuted_later_arm_preserves_complete_inventory_without_model_claim(self):
        output = Path(tempfile.mkdtemp(dir=self.root)) / 'unexecuted'
        report = p.write_unexecuted_public(solver_payload=solver(), frozen_selection=frozen(),
            checkpoint_pin=self.pins['moe4_top2'], output_dir=output, treatment='moe4_top2',
            deadline=time.time() - 1, config=CFG)
        self.assertEqual(report['status'], 'not_executed')
        self.assertFalse(report['model_loaded'])
        self.assertIsNone(report['checkpoint_state_unchanged'])
        checked = p.verify_public_artifacts(output, solver_payload=solver(), frozen_selection=frozen(),
            checkpoint_pin=self.pins['moe4_top2'], treatment='moe4_top2')
        self.assertEqual(checked['queries'], 167)
        self.assertEqual(checked['completed_views'], 0)
        self.assertFalse(checked['complete'])

    def test_independent_reconstruction_rejects_rehashed_ranked_grid_tampering(self):
        report, output = self.run_arm(deadline=time.time() - 1)
        pools_path = output / 'pools.json'
        pools = json.loads(pools_path.read_bytes())
        pools['records'][0]['tests'][0]['ranked_grids'] = [[[9]]]
        p.atomic_json(pools_path, pools)
        report['private_artifacts']['pools.json'] = p._artifact(pools_path, output)
        p.atomic_json(output / 'report.json', report)
        with self.assertRaisesRegex(ValueError, 'pool projection'):
            p.verify_public_artifacts(output, solver_payload=solver(), frozen_selection=frozen(),
                checkpoint_pin=self.pins['baseline'], treatment='baseline')

    def test_late_final_report_cannot_claim_complete(self):
        output = Path(tempfile.mkdtemp(dir=self.root)) / 'late'
        e = self.fresh(); deadline = time.time() + 120
        actual_time, actual_write = time.time, p.atomic_json
        late = False
        def now():
            return deadline + 1 if late else actual_time()
        def persist(path, value):
            nonlocal late
            actual_write(path, value)
            if Path(path).name == 'report.json' and value.get('complete'):
                late = True
        with patch.object(p, 'atomic_json', side_effect=persist), patch.object(p.time, 'time', side_effect=now):
            report = p.run_public_diagnostic(e, solver_payload=solver(), frozen_selection=frozen(),
                checkpoint_pin=self.pins['baseline'], output_dir=output, treatment='baseline',
                deadline=deadline, config=CFG)
        self.assertFalse(report['complete'])
        self.assertEqual(report['completed_views'], 334)
        self.assertEqual(report['status'], 'partial')
        self.assertIn('final report persistence', report['error']['message'])
        checked = p.verify_public_artifacts(output, solver_payload=solver(), frozen_selection=frozen(),
            checkpoint_pin=self.pins['baseline'], treatment='baseline')
        self.assertFalse(checked['complete'])

    def test_stable_ranking_reconstructs_original_view_order_not_arrival(self):
        task = solver()['fixture-000']; query = task['test'][0]['input']
        views = inference_views(2, seed=CFG['evaluation_seed'], task_id='fixture-000', demo_count=1)
        receipts = []
        for index, spec in enumerate(views):
            demos, transformed = view_inputs(task, query, spec)
            encoded = encode_example(demos, transformed, context=64, generation=2)
            receipts.append({'view': index, 'valid': True, 'tokens': 2, 'stop': 'completed',
                'demos_dropped': encoded['demos_dropped'], 'token_evidence': {
                    'prompt_ids': encoded['prompt_ids'], 'completion_ids': [1, 15],
                    'completion_log_probs': [-1., -1.], 'view_spec': spec}})
        result = {'views': list(reversed(receipts))}
        p._rank(result)
        self.assertEqual([row['view'] for row in result['views']], [0, 1])
        self.assertEqual(result['ranked_grids'], [[[1]], [[5]]])
        verify_prediction(result, task, query, CFG, task_id='fixture-000', views=2)
        corrupted = copy.deepcopy(result)
        corrupted['views'][0]['token_evidence']['prompt_ids'][-1] = 0
        with self.assertRaises(ValueError):
            verify_prediction(corrupted, task, query, CFG, task_id='fixture-000', views=2)


if __name__ == '__main__':
    unittest.main()
