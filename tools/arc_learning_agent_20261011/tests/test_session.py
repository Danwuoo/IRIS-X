"""Actual tiny-neural lifecycle; synthetic120/167 only, never benchmark claims."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from tools.arc_public_research_20261010.tests.test_public_data import make_assets
from tools.arc_learning_agent_20261011.tests.test_data import fixture_tasks
from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_learning_agent_20261011.session import run_session, _path_guard


class SessionBoundaryTests(unittest.TestCase):
    def test_source_output_overlap_rejected_before_work(self):
        from tools.arc_learning_agent_20261011.session import ROOT
        with self.assertRaises(ValueError): _path_guard(ROOT / 'new-output', ['/not-accessed'])

    def test_input_output_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): _path_guard(Path(d) / 'input/output', [Path(d) / 'input'])


@unittest.skipUnless(os.environ.get('ARC_LEARNING_NEURAL_TESTS') == '1', 'explicit actual tiny-neural CPU validation')
class NeuralSessionTests(unittest.TestCase):
    def test_two_tasks_complete_owner_seal_score_archive(self):
        root_parent = Path(os.environ.get('ARC_LEARNING_TEST_OUTPUT', tempfile.gettempdir()))
        root_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='learning-session-', dir=root_parent) as tmp:
            root = Path(tmp); assets = make_assets(root)
            training = root / 'training-fixture.json'
            tasks = fixture_tasks()
            atomic_json(training, {'synthetic_test_only': True, 'tasks': tasks}, exclusive=True)
            output = root / 'output'
            result = run_session(output, solver_root=assets['solver_root'], evaluator_root=assets['evaluator_root'],
                solver_manifest_sha256=assets['solver_manifest_sha256'],
                evaluator_manifest_sha256=assets['evaluator_manifest_sha256'], training_root=training,
                enable_model=True, config={'tiny_cpu': True, 'validation_mode': True,
                    'session_seconds': 7200, 'fixture_tasks': 2, 'max_new_tokens': 32, 'dev_tasks': 0,
                    'model': {'tiny_cpu': True, 'output_cap': 32}})
            if result['status'] != 'COMPLETE':
                detail = (output / 'worker/stderr.txt').read_text() if (output / 'worker/stderr.txt').exists() else ''
                self.fail(str(result) + '\n' + detail)
            self.assertEqual(result['score_status'], 'SCORED')
            self.assertGreaterEqual(result['training_steps'], 2)
            owner = json.loads((output / 'worker/result.json').read_bytes())
            self.assertEqual(len(owner['results']), 2)
            self.assertFalse(owner['production_model'])
            self.assertEqual(owner['prediction_origin'], 'synthetic_cpu')
            self.assertEqual(owner['pending_work'], {})
            self.assertNotEqual(owner['stages']['global_sft']['adapter_before_sha256'],
                                owner['stages']['global_sft']['adapter_after_sha256'])
            scored = json.loads((output / 'evaluation/public-summary.json').read_bytes())
            self.assertEqual((scored['tasks'], scored['tests']), (120, 167))
            self.assertEqual(scored['prediction_origin'], 'synthetic_cpu')
            self.assertFalse(scored['competition_gpu_equivalent'])
            closure = json.loads((output / 'owner-closure.json').read_bytes())
            self.assertTrue(closure['graceful'])
            self.assertTrue(closure['process_tree_proof']['closed'])
            self.assertTrue(closure['process_tree_proof']['ownership_complete'])
            archive = Path(result['export']['archive']['path'])
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), result['export']['archive']['sha256'])
            # Preserve compact evidence only if an explicit receipt destination was configured.
            if os.environ.get('ARC_LEARNING_RECEIPT_DIR'):
                target = Path(os.environ['ARC_LEARNING_RECEIPT_DIR']); target.mkdir(parents=True, exist_ok=True)
                atomic_json(target / 'ACTUAL-TINY-SESSION.json', {'result': result,
                    'stages': owner['stages'], 'closure': closure, 'tasks_observed': len(owner['results']),
                    'synthetic_only': True, 'actual_neural_training': True}, exclusive=True)


if __name__ == '__main__': unittest.main()
