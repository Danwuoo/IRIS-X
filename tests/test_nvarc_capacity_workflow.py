"""Real tiny CPU capacity training/generation/checkpoint and local closure tests.

These tests do not load official weights, run CUDA or establish capacity gains.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

MISSING = [name for name in ('torch', 'transformers', 'peft', 'pydantic', 'tokenizers', 'safetensors')
           if importlib.util.find_spec(name) is None]
if not MISSING:
    import torch
    from tests.test_nvarc_posttrain_engine import tiny_engine
    from tests.test_nvarc_matched_workflow import corpus
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, state_digest
    from tools.nvarc_capacity_20261018 import workflow as flow, controller, worker
    from tools.nvarc_capacity_20261018.model import from_dense, official_accounting


def make_engine(treatment):
    return from_dense(tiny_engine(dtype=torch.bfloat16, probability_policy='fp32-backbone-math-v1',
                                  adapter_seed=731, sample_seed=20261018),
                      treatment, fixture_layers=(0, 1))


@unittest.skipIf(bool(MISSING), 'Optional compact dependencies missing: ' + ','.join(MISSING))
class CapacityWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.temp = tempfile.TemporaryDirectory(); args = corpus(Path(cls.temp.name))
        cls.prepared = flow.prepare_panels(*args[:4], **args[4]); cls.public = copy.deepcopy(args[2])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def config(self):
        return {**flow.DEFAULT_CONFIG, 'updates': 4, 'context_tokens': 96, 'generation_tokens': 2}

    def run_flow(self, root, factory=make_engine, config=None, source_identity='a' * 64, **kwargs):
        return flow.run_workflow(factory, copy.deepcopy(self.prepared), deadline=time.time() + 180,
            output=root, source_identity=source_identity, config=self.config() if config is None else config, **kwargs)

    def test_fixed64_schedule_and_exclusions_precede_model(self):
        schedule = flow.training_schedule(self.prepared)
        again = flow.training_schedule(copy.deepcopy(self.prepared))
        self.assertEqual(schedule, again); self.assertEqual(len(schedule), 64)
        counts = {p: sum(row['parent_id'] == p for row in schedule) for p in self.prepared['training']}
        self.assertEqual(set(counts.values()), {4})
        protocol = self.prepared['protocol']
        self.assertFalse(set(protocol['development_parent_ids']) &
                         set(protocol['excluded_previous_panel'] + protocol['excluded_stability_panel']))
        self.assertEqual(len(protocol['excluded_previous_panel']), 24)
        self.assertEqual(len(protocol['excluded_stability_panel']), 32)
        broken = copy.deepcopy(self.prepared)
        broken['development'][next(iter(broken['development']))]['train'][0]['output'] = [[9]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'no-output'
            with self.assertRaises(ValueError):
                flow.run_workflow(lambda _: self.fail('model called before panel admission'), broken,
                    deadline=time.time() + 60, output=path, source_identity='a' * 64, config=self.config())
            self.assertFalse(path.exists())

    def test_exact_pure_official_trainable_counts(self):
        for treatment in flow.TREATMENTS:
            contract = controller.official_trainable_contract(treatment)
            counts = official_accounting(treatment)
            self.assertEqual(contract['parameter_count'], counts['trainable_parameters'])
            self.assertEqual(controller.expected_accounting(controller.shared._official_model_contract(), treatment,
                rank=64, selected_layers=controller.LAYERS), counts)
            self.assertEqual(contract['tensor_count'], len(contract['tensors']))
        self.assertGreater(controller.official_trainable_contract('moe4_top2')['parameter_count'],
                           controller.official_trainable_contract('baseline')['parameter_count'])

    def test_selection_never_uses_nll_or_partial_panel(self):
        def rows(scores):
            return {t: {'complete': True, 'evaluation': {'complete': True, 'pass2': score}}
                    for t, score in zip(flow.TREATMENTS, scores)}
        anchor = {'complete': True, 'pass2': 5}
        self.assertEqual(flow.select_treatment(rows([4, 5, 4]), anchor, complete=True), 'initial_anchor')
        self.assertEqual(flow.select_treatment(rows([6, 8, 7]), anchor, complete=True), 'depth32')
        self.assertEqual(flow.select_treatment(rows([8, 8, 7]), anchor, complete=True), 'initial_anchor')
        self.assertEqual(flow.select_treatment(rows([8, 7, 7]), anchor, complete=True), 'baseline')
        self.assertEqual(flow.select_treatment(rows([6, 8, 7]), anchor, complete=False), 'initial_anchor')

    def test_real_three_treatment_sft_raw_generation_exports_reload_and_cpu_audit(self):
        seen, contracts = {}, {}
        def factory(treatment):
            engine = make_engine(treatment); original = engine.sft_step; seen[treatment] = []
            contracts[treatment] = copy.deepcopy(engine.trainable_inventory)
            def step(example, optimizer, **kwargs):
                seen[treatment].append(copy.deepcopy(example))
                return original(example, optimizer, **kwargs)
            engine.sft_step = step
            return engine
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); root = base / 'worker/comparison'
            snapshot = controller.source_snapshot(Path(__file__).resolve().parents[1])
            source = controller.source_identity(snapshot)
            controller.write_new(base / 'source-manifest.json', snapshot)
            report = self.run_flow(root, factory, config={**self.config(), 'updates': 64}, source_identity=source)
            self.assertTrue(report['complete']); self.assertEqual(report['status'], 'complete')
            self.assertTrue(report['anchor']['complete']); self.assertEqual(report['anchor']['completed_parents'], 16)
            self.assertFalse(report['public_answers_used']); self.assertFalse(report['public_scoring_performed'])
            self.assertFalse(report['equal_compute_claimed']); self.assertFalse(report['capacity_gain_claimed'])
            self.assertEqual(seen['baseline'], seen['depth32']); self.assertEqual(seen['baseline'], seen['moe4_top2'])
            for treatment, cell in report['treatments'].items():
                self.assertTrue(cell['complete']); self.assertEqual(cell['training']['accepted_updates'], 64)
                self.assertEqual(cell['training']['physical']['optimizer_steps'], 64)
                self.assertEqual(cell['evaluation']['completed_parents'], 16)
                self.assertEqual(cell['evaluation']['physical']['optimizer_attempts'], 0)
                self.assertFalse(cell['approximate_flops']['measured'])
                self.assertFalse(cell['peak_memory']['gpu_measured'])
                self.assertGreater(cell['physical']['model_forward_attempts'], 4)
                self.assertGreater(cell['wall_seconds'], 0)
                saved = cell['checkpoint']; fresh = make_engine(treatment)
                fresh.load_checkpoint({k: saved[k] for k in ('root', 'manifest_sha256')})
                self.assertEqual(state_digest(adapter_state(fresh.model)), saved['state_sha256'])
                self.assertNotEqual(cell['initial_trainable_state_sha256'], saved['state_sha256'])
                for row in cell['evaluation']['records']:
                    prediction = json.loads((root / row['prediction_artifact']['path']).read_bytes())
                    self.assertEqual(len(prediction['views']), 2)
                    self.assertIn('completion_ids', prediction['views'][0]['token_evidence'])
            checked = controller.validate_comparison(root, expected_source=source, fixture_trainables=contracts)
            self.assertTrue(checked['complete']); self.assertTrue(checked['raw_development_predictions_verified'])
            original_bytes = (root / 'report.json').read_bytes()
            for mutate in ('gradient', 'parameters', 'flops'):
                corrupted = copy.deepcopy(report)
                cell = corrupted['treatments']['baseline']
                if mutate == 'gradient':
                    cell['training']['records'][0]['gradient_norm'] = -1.0
                elif mutate == 'parameters':
                    cell['parameter_accounting']['resident_parameters'] += 1
                else:
                    cell['approximate_flops']['training_dense_equivalent_proxy'] += 1
                (root / 'report.json').write_bytes(flow.canonical(corrupted))
                with self.assertRaises(ValueError):
                    controller.validate_comparison(root, expected_source=source, fixture_trainables=contracts)
                (root / 'report.json').write_bytes(original_bytes)
            self.assertEqual(checked['selected_treatment'], report['selected_treatment'])
            self.assertEqual(json.loads((root / 'report.json').read_bytes()), report)
            self.assertLess(sum(p.stat().st_size for p in root.rglob('*') if p.is_file()), 1024**3)
            public_config = {k: self.config()[k] for k in ('context_tokens', 'generation_tokens', 'evaluation_seed', 'views', 'ttt_steps')}
            public = worker.run_public_bundle(make_engine, copy.deepcopy(self.public), report,
                output=base / 'worker', deadline=time.time() + 180, config=public_config)
            self.assertTrue(public['complete'])
            self.assertEqual(public['frozen_selection']['selected_treatment'], report['selected_treatment'])
            public_check = controller.validate_public_bundle(base / 'worker', comparison=checked, solver_payload=self.public)
            self.assertTrue(public_check['complete'])
            self.assertEqual(sum(v['completed_views'] for v in public_check['treatments'].values()), 1002)
            # Real local owned closure followed by new immutable seals. This is
            # a synthetic closure/schema exercise, never official GPU evidence.
            closure = controller.run_owned([sys.executable, '-c', 'pass'], source_root=Path(__file__).resolve().parents[1],
                output=base / 'closure-fixture', deadline=time.time() + 30)
            started = time.time()
            seals = controller.seal_public_predictions(base, verification=public_check, closure=closure,
                expected_source=source, started_epoch=started, session_deadline_epoch=started + 43200)
            self.assertEqual(set(seals), set(flow.TREATMENTS))
            self.assertTrue(all(row['complete'] for row in seals.values()))
            for seal in seals.values():
                body = json.loads((base / seal['path']).read_bytes())
                self.assertFalse(body['provider_terminal_verified'])
                self.assertFalse(body['public_scoring_performed'])
                self.assertFalse(body['legacy_scorer_compatibility_claimed'])
            with self.assertRaises(FileExistsError):
                controller.seal_public_predictions(base, verification=public_check, closure=closure,
                    expected_source=source, started_epoch=started, session_deadline_epoch=started + 43200)
            # Mutating raw output after export must not survive source/artifact closure.
            first = report['treatments']['baseline']['evaluation']['records'][0]['prediction_artifact']['path']
            (root / first).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'artifact bytes or SHA'):
                controller.validate_comparison(root, expected_source=source, fixture_trainables=contracts)

    def test_deadline_before_first_update_keeps_all_unknown_denominators(self):
        called = []
        def factory(treatment):
            called.append(treatment); engine = make_engine(treatment)
            def stop(*args, **kwargs):
                raise PhaseDeadline('fixture deadline before commit')
            engine.sft_step = stop
            return engine
        with tempfile.TemporaryDirectory() as directory:
            report = self.run_flow(Path(directory) / 'result', factory)
            self.assertFalse(report['complete']); self.assertEqual(report['status'], 'partial')
            self.assertEqual(report['selected_treatment'], 'initial_anchor')
            self.assertEqual(called, ['baseline'])
            self.assertEqual(report['treatments']['baseline']['training']['attempted_updates'], 1)
            self.assertEqual(report['treatments']['baseline']['training']['accepted_updates'], 0)
            for cell in report['treatments'].values():
                self.assertEqual(cell['evaluation']['full_requested_denominator'], 16)
                self.assertEqual(len(cell['evaluation']['records']), 16)
                self.assertIsNone(cell['evaluation']['pass2'])
                self.assertIsNone(cell['checkpoint'])

    def test_numerical_failure_never_constructs_an_optimizer(self):
        from tools.nvarc_capacity_20261018 import model
        original = model.probability_admission
        def denied(*args, **kwargs):
            receipt = original(*args, **kwargs)
            receipt['passed'] = False
            receipt['error'] = {'type': 'SyntheticGateFailure', 'message': 'test injection, not observed model error'}
            return receipt
        with tempfile.TemporaryDirectory() as directory, patch.object(model, 'probability_admission', side_effect=denied), \
                patch.object(flow, 'make_optimizer', side_effect=AssertionError('optimizer must not be created')):
            root = Path(directory) / 'result'
            with self.assertRaisesRegex(ValueError, 'numerical admission failed'):
                self.run_flow(root)
            report = json.loads((root / 'report.json').read_bytes())
            self.assertFalse(report['complete']); self.assertEqual(report['status'], 'failed')
            self.assertEqual(report['selected_treatment'], 'initial_anchor')
            self.assertEqual(report['treatments']['baseline']['training']['attempted_updates'], 0)
            self.assertEqual(report['treatments']['baseline']['physical']['optimizer_attempts'], 0)
            self.assertFalse(report['treatments']['baseline']['probability_admission']['passed'])

    def test_public_deadline_initializes_all_three_full_denominators_without_loading(self):
        contracts = {}
        def factory(treatment):
            engine = make_engine(treatment); contracts[treatment] = copy.deepcopy(engine.trainable_inventory)
            return engine
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); report = self.run_flow(output / 'comparison', factory,
                config={**self.config(), 'updates': 1})
            checked = controller.validate_comparison(output / 'comparison', expected_source='a' * 64,
                                                      fixture_trainables=contracts)
            cfg = {k: self.config()[k] for k in ('context_tokens', 'generation_tokens', 'evaluation_seed', 'views', 'ttt_steps')}
            result = worker.run_public_bundle(lambda _: self.fail('expired PUBLIC must not load model'), self.public,
                report, output=output, deadline=time.time() - 1, config=cfg)
            self.assertFalse(result['complete'])
            self.assertEqual(result['frozen_selection']['selected_treatment'], report['selected_treatment'])
            verified = controller.validate_public_bundle(output, comparison=checked, solver_payload=self.public)
            self.assertFalse(verified['complete'])
            for treatment, arm in result['treatments'].items():
                self.assertEqual(arm['queries'], 167); self.assertEqual(arm['completed_views'], 0)
                self.assertIsNone(arm['checkpoint_state_unchanged'])
                pools = json.loads((output / 'public' / treatment / 'pools.json').read_bytes())
                self.assertEqual(len(pools['records']), 120)
                self.assertEqual(sum(len(row['tests']) for row in pools['records']), 167)
                self.assertFalse(result['loading'][treatment]['attempted'])

    def test_exact_official_source_verification_precedes_any_model_load(self):
        from tools.nvarc_capacity_20261018 import model
        from tools.nvarc_posttrain_20261017 import materials
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'source.json').write_text('{}'); now = time.time()
            args = ['--model-root', str(root), '--training-root', str(root), '--training-manifest', str(root),
                '--public-challenges', str(root), '--output', str(root / 'output'), '--source-root', str(root),
                '--source-manifest', str(root / 'source.json'), '--source-sha256', 'a' * 64,
                '--started-epoch', str(now), '--session-deadline-epoch', str(now + 43200),
                '--deadline-epoch', str(now + 120), '--comparison-deadline-epoch', str(now + 90), '--execute-official']
            with patch.object(worker, 'verify_source', return_value=True), \
                 patch('torch.cuda.is_available', return_value=True), patch('torch.cuda.device_count', return_value=1), \
                 patch('torch.cuda.mem_get_info', return_value=(40 * 1024**3, 48 * 1024**3)), \
                 patch.object(materials, 'verify_model', side_effect=ValueError('official model digest mismatch')), \
                 patch.object(model, 'load_engine') as load:
                with self.assertRaisesRegex(ValueError, 'official model digest mismatch'):
                    worker.main(args)
                load.assert_not_called()

    def test_source_snapshot_rejects_mutation_and_new_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'src').mkdir(); (root / 'tools/nvarc_posttrain_20261017').mkdir(parents=True)
            source = root / 'src/example.py'; source.write_text('x = 1\n')
            (root / 'tools/nvarc_posttrain_20261017/model-pins.json').write_text('{}')
            snapshot = controller.source_snapshot(root); identity = controller.source_identity(snapshot)
            self.assertTrue(controller.verify_source(root, snapshot, identity))
            source.write_text('x = 2\n')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                controller.verify_source(root, snapshot, identity)

    @unittest.skipUnless(sys.platform == 'linux' and hasattr(__import__('os'), 'pidfd_open'), 'Linux pidfds required')
    def test_actual_owned_process_closure_and_cpu_only_import(self):
        code = 'import sys; import tools.nvarc_capacity_20261018.controller; assert "torch" not in sys.modules; print("owned CPU closure")'
        with tempfile.TemporaryDirectory() as directory:
            result = controller.run_owned([sys.executable, '-B', '-c', code], source_root=Path(__file__).resolve().parents[1],
                output=Path(directory), deadline=time.time() + 30)
            self.assertTrue(result['closed']); self.assertTrue(result['normal_exit'])
            self.assertTrue(result['proof']['ownership_complete'])
            self.assertIn('owned CPU closure', (Path(directory) / 'worker.log').read_text())

    def test_worker_refuses_implicit_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            args = []
            for name in ('model-root', 'training-root', 'training-manifest', 'public-challenges', 'output', 'source-root', 'source-manifest'):
                args.extend(['--' + name, directory])
            args.extend(['--started-epoch', str(time.time()), '--session-deadline-epoch', str(time.time() + 43200),
                         '--source-sha256', 'a' * 64, '--deadline-epoch', str(time.time() + 120),
                         '--comparison-deadline-epoch', str(time.time() + 90)])
            with self.assertRaisesRegex(ValueError, 'explicit --execute-official'):
                worker.main(args)
