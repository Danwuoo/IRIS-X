"""Real process-closure and sealed evaluation tests over synthetic 120/167 only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from tools.arc_learning_agent_20261011 import evaluation, process_guard
from tools.arc_learning_agent_20261011.budget import atomic_json, digest
from tools.arc_public_research_20261010.public_data import load_solver_tasks
from tools.arc_public_research_20261010.tests.test_public_data import make_assets


@unittest.skipUnless(sys.platform == 'linux', 'Linux owned-process closure required')
class EvaluationBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.assets = make_assets(self.root)
        self.source = evaluation.source_identity()
        self.guards = []
        self.addCleanup(self.stop_guards)
        guard = self.spawn('pass', 'closed-owner')
        limit = time.monotonic() + 10
        while guard.poll() is None and time.monotonic() < limit:
            time.sleep(0.01)
        self.assertIsNotNone(guard.poll(), 'synthetic owner did not exit')
        self.proof = guard.closed_proof()
        self.assertTrue(process_guard.verify_closed_proof(self.proof))
        self.result_path = self.root / 'owner-result.json'
        self.result = {'run_id': 'synthetic-boundary-run', 'status': 'partial',
            'model_stopped': True, 'pending_work': {},
            'solver_manifest_sha256': self.assets['solver_manifest_sha256'],
            'source_identity_sha256': digest(self.source), 'request_sha256': digest({'synthetic_request': True}),
            'prediction_origin': 'synthetic_cpu', 'production_model': False,
            'training_steps': 0, 'physical_usage': {}, 'elapsed_seconds': 0.0, 'results': {}}
        self.bindings = {'run_id': self.result['run_id'], 'prediction_origin': 'synthetic_cpu'}
        self.closure = {'format': 'irisx/learning-owner-closure-v1',
            'worker_identity': copy.deepcopy(guard.identity), 'returncode': 0, 'graceful': True,
            'source_identity_sha256': digest(self.source), 'result_sha256': None,
            'request_sha256': self.result['request_sha256'], 'session_members': [],
            'parent_identity': evaluation.process_identity(os.getpid()),
            'process_tree_proof': copy.deepcopy(self.proof)}
        self.write_result(self.result)

    def spawn(self, code, name):
        guard = process_guard.OwnedProcessGuard.spawn(
            [sys.executable, '-I', '-B', '-c', code], evidence_dir=self.root / name,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.guards.append(guard)
        return guard

    def stop_guards(self):
        for guard in self.guards:
            if guard.poll() is None or guard._remaining():
                guard.stop(timeout=5)

    def write_result(self, result):
        atomic_json(self.result_path, result)
        self.closure['result_sha256'] = hashlib.sha256(self.result_path.read_bytes()).hexdigest()

    def seal(self, name='predictions', *, closure=None, bindings=None):
        return evaluation.seal_predictions(self.root / name,
            solver_root=self.assets['solver_root'],
            solver_manifest_sha256=self.assets['solver_manifest_sha256'],
            evaluator_manifest_sha256=self.assets['evaluator_manifest_sha256'],
            result_path=self.result_path, closure=self.closure if closure is None else closure,
            bindings=self.bindings if bindings is None else bindings)

    def verify(self, seal, name='predictions'):
        return evaluation.verify_seal(self.root / name, seal['sha256'], self.assets['solver_root'])

    def test_real_graceful_owner_can_seal_and_identity_cannot_be_reused(self):
        seal = self.seal()
        document, solver, pools = self.verify(seal)
        self.assertEqual((document['tasks'], document['tests']), (120, 167))
        self.assertEqual(set(pools), set(evaluation.POLICIES))
        self.assertEqual(len(solver['challenges']), 120)
        self.assertFalse(document['generation_may_resume'])
        with self.assertRaisesRegex(ValueError, 'identity consumed'):
            self.seal()

    def test_live_owned_incarnation_blocks_closure_before_seal(self):
        closure = copy.deepcopy(self.closure)
        live = evaluation.process_identity(os.getpid())
        closure['process_tree_proof']['owned_identities'].append(live)
        with self.assertRaisesRegex(ValueError, 'still present'):
            self.seal(closure=closure)
        self.assertFalse((self.root / 'predictions').exists())

    def test_actual_forced_owner_closure_cannot_score(self):
        guard = self.spawn('import time; time.sleep(30)', 'forced-owner')
        marker = self.root / 'forced-owner' / 'worker-launch.json'
        limit = time.monotonic() + 5
        while not marker.exists() and guard.poll() is None and time.monotonic() < limit:
            time.sleep(0.01)
        self.assertTrue(marker.exists(), 'synthetic worker never launched')
        proof = guard.stop(timeout=5)
        self.assertTrue(proof['closed'], proof)
        self.assertTrue(proof['forced'])
        closure = copy.deepcopy(self.closure)
        closure.update(worker_identity=guard.identity, process_tree_proof=proof,
                       returncode=guard.child.returncode, graceful=False)
        with self.assertRaisesRegex(ValueError, 'owned worker failed'):
            self.seal(closure=closure)
        self.assertFalse((self.root / 'predictions').exists())

    def test_unknown_closure_or_foreign_owner_incarnation_fails_closed(self):
        for field, value in (('ownership_complete', False), ('closed', False),
                             ('errors', ['synthetic unresolved ownership'])):
            with self.subTest(field=field):
                closure = copy.deepcopy(self.closure)
                closure['process_tree_proof'][field] = value
                with self.assertRaisesRegex(ValueError, 'complete owned-process closure'):
                    self.seal(closure=closure)
        closure = copy.deepcopy(self.closure)
        closure['worker_identity']['birth'] += 1
        with self.assertRaisesRegex(ValueError, 'process-tree root binding'):
            self.seal(closure=closure)
        self.assertFalse((self.root / 'predictions').exists())

    def test_terminal_stop_unknown_work_and_result_bindings_are_required(self):
        changes = (
            ('status', 'running', 'terminal result'),
            ('model_stopped', False, 'terminal result'),
            ('pending_work', {'unresolved-call': {'gas': 200000}}, 'unknown work'),
            ('pending_work', None, 'unknown work'),
            ('source_identity_sha256', '0' * 64, 'source/request binding'),
            ('request_sha256', '0' * 64, 'source/request binding'),
            ('run_id', 'foreign-run', 'prediction run binding'),
            ('solver_manifest_sha256', '0' * 64, 'foreign solver result'),
            ('prediction_origin', 'trained_model_research', 'prediction origin'),
            ('production_model', True, 'production attribution'),
        )
        for field, value, message in changes:
            with self.subTest(field=field, value=value):
                result = copy.deepcopy(self.result)
                result[field] = value
                self.write_result(result)
                with self.assertRaisesRegex(ValueError, message):
                    self.seal()
                self.assertFalse((self.root / 'predictions').exists())
        self.write_result(self.result)
        self.verify(self.seal())

    def test_sealed_bytes_extra_files_and_seal_itself_are_tamper_evident(self):
        seal = self.seal()
        root = self.root / 'predictions'
        for name in ('global_grid.json', 'task_ttt.json', 'full_agent.json',
                     'owner-closure.json', 'solver-result.json', 'prediction-seal.json'):
            with self.subTest(name=name):
                path = root / name
                before = path.read_bytes()
                try:
                    path.write_bytes(before + b' ')
                    with self.assertRaises(ValueError):
                        self.verify(seal)
                finally:
                    path.write_bytes(before)
        extra = root / 'unsealed.json'
        extra.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.verify(seal)
        extra.unlink()
        self.verify(seal)

    def test_tamper_blocks_evaluator_launch_and_any_evaluator_file_read(self):
        seal = self.seal()
        (self.root / 'predictions' / 'full_agent.json').write_text('{}')
        with mock.patch.object(evaluation, 'read_regular', wraps=evaluation.read_regular) as reads, \
                mock.patch.object(evaluation.subprocess, 'Popen') as launch:
            with self.assertRaises(ValueError):
                evaluation.evaluate_sealed(self.root / 'predictions', seal['sha256'],
                    solver_root=self.assets['solver_root'], evaluator_root=self.assets['evaluator_root'],
                    output_root=self.root / 'evaluation', deadline=time.monotonic() + 30)
        launch.assert_not_called()
        evaluator = Path(self.assets['evaluator_root'])
        self.assertTrue(all(not Path(call.args[0]).is_relative_to(evaluator) for call in reads.call_args_list))
        self.assertFalse((self.root / 'evaluation').exists())

    def test_seal_policy_denominators_and_no_resume_cannot_be_rewritten(self):
        seal = self.seal()
        path = self.root / 'predictions' / 'prediction-seal.json'
        original = json.loads(path.read_bytes())
        for changes in ({'tests': 1}, {'tasks': 1}, {'generation_may_resume': True},
                        {'policies': ['full_agent']}):
            with self.subTest(changes=changes):
                atomic_json(path, {**original, **changes})
                changed_sha = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.assertRaises(ValueError):
                    evaluation.verify_seal(path.parent, changed_sha, self.assets['solver_root'])
        atomic_json(path, original)
        self.verify(seal)

    def test_missing_tasks_queries_and_policies_keep_full_scoring_denominator(self):
        # Only one of 167 synthetic queries gets a candidate. No real public
        # label file is opened; the fresh CPU evaluator uses make_assets data.
        result = copy.deepcopy(self.result)
        result['results'] = {'00000000': {'policies': {
            'full_agent': [{'candidates': [[[2]]]}, {'candidates': []}]}}}
        self.write_result(result)
        seal = self.seal()
        _, solver, pools = self.verify(seal)
        for policy, pool in pools.items():
            self.assertEqual(len(pool['records']), 120)
            self.assertEqual(sum(len(row['tests']) for row in pool['records']), 167)
            missing = next(row for row in pool['records'] if row['task_id'] == '00000001')
            self.assertTrue(all(q['status'] == 'not_executed' and q['ranked_grids'] == [] for q in missing['tests']))
        summary = evaluation.evaluate_sealed(self.root / 'predictions', seal['sha256'],
            solver_root=self.assets['solver_root'], evaluator_root=self.assets['evaluator_root'],
            output_root=self.root / 'evaluation', deadline=time.monotonic() + 30)
        if summary['status'] != 'SCORED':
            self.fail(str(summary) + '\n' + (self.root / 'evaluation' / 'stderr.txt').read_text())
        self.assertEqual((summary['tasks'], summary['tests']), (120, 167))
        self.assertEqual(summary['prediction_origin'], 'synthetic_cpu')
        self.assertIsNone(summary['official_score'])
        self.assertFalse(summary['training_used'])
        for policy, observed in summary['policies'].items():
            expected = 1 if policy == 'full_agent' else 0
            self.assertEqual((observed['tasks'], observed['tests']), (120, 167))
            self.assertEqual(observed['metrics']['pass_at_2']['numerator'], expected)
            self.assertEqual(observed['metrics']['pass_at_2']['denominator'], 167)
            self.assertEqual(observed['metrics']['empty_pool']['numerator'], 167 - expected)
            self.assertEqual(observed['metrics']['task_average_pass_at_2']['denominator'], 120)
            self.assertEqual(observed['metrics']['tasks_all_tests_pass_at_2']['numerator'], 0)

    def test_foreign_task_wrong_query_count_and_more_than_two_candidates_rejected(self):
        challenges = load_solver_tasks(self.assets['solver_root'], self.assets['solver_manifest_sha256'])['challenges']
        malformed = [
            {'foreign-task': {'policies': {}}},
            {'00000000': {'policies': {'full_agent': [{'candidates': []}]}}},
            {'00000000': {'policies': {'full_agent': [
                {'candidates': [[[1]], [[2]], [[3]]]}, {'candidates': []}]}}},
        ]
        for result in malformed:
            with self.subTest(result=result), self.assertRaises(ValueError):
                evaluation.make_pools(challenges, result, run_id='synthetic-malformed', elapsed_seconds=0)


if __name__ == '__main__':
    unittest.main()
