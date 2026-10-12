"""Policy fixtures plus an actual isolated CPU blocked-effectiveness session."""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch

from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_learning_agent_20261011.learning_cycle import train_with_canaries


def canary(loss=1.0, exact=0, complete=True):
    return {'complete': complete, 'rows': [{'sample_id': 'fixed',
        'scoring_receipt_complete': complete, 'score': {'nll_sum': loss * 2, 'token_count': 2}}],
        'dev': {'exact': exact}, 'learnability_controls': {'exact': 0},
        'shape_correct': exact, 'valid_grid': 1, 'mean_nll': loss,
        'exact': exact, 'denominator': 1, 'gate_pass': False}


class PolicyTrainer:
    config = {'stability_mode': True}
    def __init__(self):
        self.logical = 0; self.physical = 0; self.restored = None
    def snapshot(self, label): return {'label': label, 'value': self.logical}
    def snapshot_training_state(self, label): return {'label': label, 'value': self.logical}
    def restore_training_state(self, handle):
        self.logical = handle['value']; self.restored = handle
        return {'restored': True, 'logical': self.logical}
    def release_training_state(self, handle): return {'released': True}
    def release_snapshot(self, handle): return {'released': True}
    def train(self, records, *, max_steps, **kwargs):
        self.logical += max_steps; self.physical += max_steps
        return {'attempted_microbatches': max_steps, 'optimizer_steps': 1, 'status': 'complete'}


class CyclePolicyTests(unittest.TestCase):
    def test_training_checkpoint_is_hash_bound_but_not_duplicated_in_archive(self):
        from tools.arc_learning_agent_20261011.export import export_evidence
        class DiskTrainer(PolicyTrainer):
            def train(self, records, *, max_steps, checkpoint_dir, **kwargs):
                checkpoint_dir.mkdir(parents=True, exist_ok=True)
                (checkpoint_dir / 'state.pt').write_bytes(b'fixture-optimizer-state')
                return super().train(records, max_steps=max_steps, **kwargs)
        with tempfile.TemporaryDirectory() as tmp, patch(
                'tools.arc_learning_agent_20261011.learning_cycle.evaluate_panel',
                side_effect=[canary(), canary(.8, 1)]):
            root = Path(tmp)
            train_with_canaries(None, DiskTrainer(), [], {'panel_sha256': 'fixture'}, {},
                deadline=time.monotonic() + 10, output=root / 'worker/stable-learning',
                max_microbatches=2, chunk_microbatches=2)
            expected = 'worker/checkpoints/stable-global/state.pt'
            self.assertTrue((root / expected).is_file())
            self.assertFalse((root / 'worker/stable-learning/training-checkpoints').exists())
            receipt = export_evidence(root, run_id='checkpoint-namespace-regression',
                                      deadline=time.monotonic() + 10)
            self.assertEqual(receipt['separate_artifacts'][expected]['bytes'], 23)
            with zipfile.ZipFile(receipt['archive']['path']) as archive:
                self.assertNotIn(expected, archive.namelist())
                inventory = json.loads(archive.read('evidence-inventory.json'))
                self.assertEqual(inventory['separate_artifacts'], receipt['separate_artifacts'])
                self.assertIn('worker/stable-learning/stable-learning-report.json', archive.namelist())

    def run_cycle(self, trainer, reports, **kwargs):
        with tempfile.TemporaryDirectory() as tmp, patch(
                'tools.arc_learning_agent_20261011.learning_cycle.evaluate_panel', side_effect=reports):
            snapshots, result = train_with_canaries(None, trainer, [], {'panel_sha256': 'fixture'}, {},
                deadline=time.monotonic() + 10, output=Path(tmp) / 'cycle',
                max_microbatches=8, chunk_microbatches=2, **kwargs)
            retained = json.loads((Path(tmp) / 'cycle/stable-learning-report.json').read_bytes())
            self.assertEqual(retained, result)
            return snapshots, result

    def test_two_regressions_stop_restore_base_without_physical_refund(self):
        trainer = PolicyTrainer()
        snapshots, report = self.run_cycle(trainer, [canary(), canary(2), canary(3)])
        self.assertEqual((trainer.logical, trainer.physical), (0, 4))
        self.assertEqual(report['status'], 'canary_regression')
        self.assertEqual(report['attempted_microbatches'], 4)
        self.assertEqual(snapshots['early']['value'], 2)
        self.assertEqual(snapshots['final']['value'], 4)
        self.assertEqual(snapshots['best']['value'], 0)

    def test_restore_best_complete_boundary_not_final(self):
        trainer = PolicyTrainer()
        snapshots, report = self.run_cycle(trainer,
            [canary(), canary(.8, 1), canary(.9, 0), canary(1.2, 0)])
        self.assertEqual((trainer.logical, trainer.physical), (2, 6))
        self.assertEqual(snapshots['best']['value'], 2)
        self.assertEqual(snapshots['final']['value'], 6)
        self.assertEqual(report['optimizer_steps'], 3)

    def test_incomplete_initial_comparison_never_trains(self):
        trainer = PolicyTrainer()
        _, report = self.run_cycle(trainer, [canary(complete=False)])
        self.assertEqual(trainer.physical, 0)
        self.assertEqual(report['status'], 'base_canary_incomplete')
        self.assertEqual(set(report['checkpoint_aliases']), {'early', 'final'})

    def test_known_failed_chunk_stays_charged_and_is_preserved(self):
        from tools.arc_learning_agent_20261011.metering import TrainingStageFailed
        trainer = PolicyTrainer()
        def fail(*args, **kwargs):
            trainer.physical += 1
            error = TrainingStageFailed('synthetic failed finite boundary')
            error.receipt = {'attempted_microbatches': 1, 'optimizer_steps': 0, 'status': 'failed'}
            raise error
        trainer.train = fail
        _, report = self.run_cycle(trainer, [canary()])
        self.assertEqual(report['attempted_microbatches'], 1)
        self.assertEqual(trainer.physical, 1)
        self.assertEqual(len(report['failed_training_receipts']), 1)


@unittest.skipUnless(os.environ.get('ARC_LEARNING_NEURAL_TESTS') == '1', 'explicit actual CPU neural test')
class BlockedStableSessionTests(unittest.TestCase):
    def test_real_model_blocked_before_public_generation_or_gold_scoring(self):
        from tools.arc_learning_agent_20261011.session import run_session
        from tools.arc_learning_agent_20261011.tests.test_data import fixture_tasks
        from tools.arc_public_research_20261010.tests.test_public_data import make_assets
        with tempfile.TemporaryDirectory(prefix='stable-real-session-') as tmp:
            root = Path(tmp); assets = make_assets(root)
            tasks = fixture_tasks()
            for task in tasks.values():
                task['train'].append(copy.deepcopy(task['train'][-1]))
            training = root / 'training.json'
            atomic_json(training, {'synthetic_test_only': True, 'tasks': tasks}, exclusive=True)
            config = {'tiny_cpu': True, 'validation_mode': True, 'learning_profile': 'stable_v2',
                'session_seconds': 7200, 'fixture_tasks': 2, 'max_new_tokens': 32, 'dev_tasks': 1,
                'model': {'tiny_cpu': True, 'output_cap': 32}}
            with patch('tools.arc_learning_agent_20261011.session.evaluate_sealed',
                       side_effect=AssertionError('public scorer must not run')):
                result = run_session(root / 'output', solver_root=assets['solver_root'],
                    evaluator_root=assets['evaluator_root'],
                    solver_manifest_sha256=assets['solver_manifest_sha256'],
                    evaluator_manifest_sha256=assets['evaluator_manifest_sha256'],
                    training_root=training, enable_model=True, config=config)
            if result['status'] != 'EFFECTIVENESS_BLOCKED':
                self.fail(str(result) + (root / 'output/worker/stderr.txt').read_text())
            self.assertEqual(result['score_status'], 'NOT_RUN')
            self.assertFalse((root / 'output/evaluation').exists())
            self.assertFalse((root / 'output/predictions').exists())
            owner = json.loads((root / 'output/worker/result.json').read_bytes())
            self.assertEqual(owner['results'], {})
            self.assertEqual(owner['pending_work'], {})
            self.assertTrue(owner['model_stopped'])
            self.assertGreater(owner['physical_usage']['charged']['generation_calls'], 0)
            self.assertTrue(owner['stages']['global_sft']['restored_best_complete_state']['restored'])
            self.assertTrue(Path(result['export']['archive']['path']).is_file())
            closure = json.loads((root / 'output/owner-closure.json').read_bytes())
            self.assertTrue(closure['graceful'])


if __name__ == '__main__': unittest.main()
