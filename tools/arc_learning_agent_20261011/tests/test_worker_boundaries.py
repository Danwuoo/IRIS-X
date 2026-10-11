"""Synthetic worker-boundary tests; scripted models and real bounded CPU VM only."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from tools.arc_learning_agent_20261011 import data, program_tools, worker
from tools.arc_learning_agent_20261011.budget import WorkLedger
from tools.arc_learning_agent_20261011.grid_codec import encode_grid, grid_messages, program_messages


WIDTH = "def transform(grid):\n    return [[len(grid[0])]]\n"
WRONG = "def transform(grid):\n    return [[0]]\n"
VISIBLE_ONLY = "def transform(grid):\n    n = len(grid[0])\n    if n > 3:\n        n = 3\n    return [[n]]\n"


class ScriptedPrograms:
    def __init__(self, sources):
        self.sources = iter(sources)
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append({'messages': copy.deepcopy(messages), **kwargs})
        return {'valid': True, 'text': next(self.sources)}


class ScriptedTrainer:
    def __init__(self, *, incomplete_task=None):
        self.current = 'global_sft'
        self.restores = []
        self.frozen = []
        self._task_id = None
        self.steps = 0
        self.adaptations = []
        self.ended = []
        self.incomplete_task = incomplete_task

    def restore(self, snapshot):
        self.current = snapshot['name']
        self.restores.append(self.current)
        return {'restored': self.current}

    def freeze_global(self):
        self.frozen.append(self.current)
        return {'name': self.current}

    def begin_task(self, task_id):
        if self._task_id is not None:
            raise AssertionError('task state carried over')
        self._task_id = task_id
        self.steps = 0

    def adapt_task(self, task_id, demos, *, max_steps, deadline):
        self.adaptations.append((task_id, copy.deepcopy(demos), max_steps))
        self.steps = max_steps
        return {'steps': 0 if task_id == self.incomplete_task else max_steps}

    def end_task(self):
        self.ended.append(self._task_id)
        self._task_id = None
        self.steps = 0


class ScriptedScores:
    def __init__(self, trainer, score):
        self.trainer = trainer
        self.score = score
        self.calls = []

    def score_completion(self, messages, completion, *, deadline):
        self.calls.append({'checkpoint': self.trainer.current,
                           'task_id': self.trainer._task_id, 'steps': self.trainer.steps,
                           'messages': copy.deepcopy(messages), 'completion': completion})
        value = self.score(self.trainer, completion)
        return ({'valid': False, 'error': 'synthetic incomplete forward'} if value is None else
                {'valid': True, 'mean_nll': value, 'nll_sum': value * 2, 'token_count': 2})


class ScratchTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)


@unittest.skipUnless(program_tools.legacy.capability()['available'], 'bounded Linux CPU VM required')
class RolloutBoundaryTests(ScratchTest):
    def setUp(self):
        super().setUp()
        self.tasks = {
            'train-parent': {'train': [
                {'input': [[1, 2]], 'output': [[2]]},
                {'input': [[3, 4, 5]], 'output': [[3]]},
                {'input': [[6, 6, 6, 6]], 'output': [[4]]}],
                'test': [{'input': [[9, 8, 7, 6, 5]]}]},
            'dev-parent': {'train': [
                {'input': [[1], [2]], 'output': [[1, 1], [2, 2]]},
                {'input': [[3]], 'output': [[3, 3]]}]} }
        # Admit demo-only sources; inject an unrelated query sentinel only at the
        # worker seam to prove it cannot enter generated training prompts.
        self.manifest = data.create_split_manifest(
            {key: {'train': task['train']} for key, task in self.tasks.items()},
            fixed_splits={'train': ['train-parent'], 'dev': ['dev-parent']})
        self.ledger = WorkLedger(self.root / 'work.jsonl')

    def rollout(self, model):
        return worker._rollouts(self.tasks, self.manifest, model, self.ledger,
            deadline=time.monotonic() + 30, output=self.root, config={'rollout_tasks': 8})

    def test_withheld_demo_query_projection_and_two_real_proofs_before_admission(self):
        model = ScriptedPrograms([WIDTH])
        demos = self.tasks['train-parent']['train']
        visible_task = {'train': demos[:-1], 'test': [{'input': demos[-1]['input']}]}
        events = []
        real_verify, real_compile = program_tools.verify_program, data.verified_program_record

        def verify(source, received_demos, *args, **kwargs):
            proof = real_verify(source, received_demos, *args, **kwargs)
            events.append(('verified', copy.deepcopy(received_demos), proof['all_demos_fit']))
            return proof

        def compile_record(task_id, original_task, source, proof, manifest, **kwargs):
            self.assertEqual(events, [('verified', demos[:-1], True), ('verified', demos, True)])
            self.assertEqual(original_task['train'], demos)
            self.assertEqual(proof['demos'], demos)
            self.assertEqual(kwargs['generation_context']['visible_verification_proof']['demos'], demos[:-1])
            events.append(('admitted', task_id))
            return real_compile(task_id, original_task, source, proof, manifest, **kwargs)

        with mock.patch.object(program_tools, 'verify_program', side_effect=verify), \
                mock.patch.object(data, 'verified_program_record', side_effect=compile_record):
            records, receipt = self.rollout(model)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0]['messages'], program_messages(visible_task))
        self.assertNotIn('98765', model.calls[0]['messages'][-1]['content'])
        self.assertNotIn('Output:\n4', model.calls[0]['messages'][-1]['content'])
        self.assertEqual(receipt['predeclared_tasks'], ['train-parent'])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['messages'], model.calls[0]['messages'])
        self.assertEqual(records[0]['provenance']['generalization_claim'], 'training-heldout-demo-not-prompted')
        data.validate_records(records, self.manifest, ())
        self.assertEqual(self.ledger.pending, {})
        self.assertEqual(self.ledger.used['cpu_checks'], 2)
        self.assertGreater(self.ledger.used['gas'], 0)
        self.assertEqual(json.loads((self.root / 'rollout-receipt.json').read_bytes()), receipt)

    def test_visible_fit_heldout_failure_never_admitted_or_used_for_repair(self):
        model = ScriptedPrograms([VISIBLE_ONLY])
        with mock.patch.object(data, 'verified_program_record') as admit:
            records, receipt = self.rollout(model)
        admit.assert_not_called()
        self.assertEqual(records, [])
        self.assertEqual(len(model.calls), 1)
        self.assertTrue(receipt['attempts'][0]['proof']['all_demos_fit'])
        self.assertFalse(receipt['attempts'][0]['heldout_proof']['all_demos_fit'])
        self.assertEqual(receipt['verified_records'], 0)
        self.assertEqual(self.ledger.used['cpu_checks'], 2)
        self.assertFalse(self.ledger.pending)

    def test_real_visible_failure_repair_keeps_heldout_out_of_feedback(self):
        model = ScriptedPrograms([WRONG, WIDTH])
        records, receipt = self.rollout(model)
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['kind'], 'repair')
        self.assertEqual(records[0]['messages'], model.calls[1]['messages'])
        self.assertEqual(len(records[0]['provenance']['failure_proof']['demos']), 2)
        self.assertEqual(len(receipt['attempts'][0]['proof']['receipt']['demos']), 2)
        self.assertNotIn('Output:\n4', model.calls[1]['messages'][-1]['content'])
        self.assertNotIn('98765', model.calls[1]['messages'][-1]['content'])
        self.assertEqual(self.ledger.used['cpu_checks'], 3)
        data.validate_records(records, self.manifest, ())

    def test_unknown_full_proof_blocks_admission_and_keeps_reservation(self):
        real_verify = program_tools.verify_program
        count = 0

        def unknown_full(*args, **kwargs):
            nonlocal count
            proof = real_verify(*args, **kwargs)
            count += 1
            if count == 2:
                proof = copy.deepcopy(proof)
                proof['receipt']['known'] = False
            return proof

        with mock.patch.object(program_tools, 'verify_program', side_effect=unknown_full), \
                mock.patch.object(data, 'verified_program_record') as admit:
            with self.assertRaisesRegex(RuntimeError, 'unknown heldout verification'):
                self.rollout(ScriptedPrograms([WIDTH]))
        admit.assert_not_called()
        self.assertEqual(list(self.ledger.pending), ['rollout-verify-0000-0-heldout'])
        self.assertEqual(self.ledger.events[-1]['event'], 'unknown')
        self.assertEqual(self.ledger.pending['rollout-verify-0000-0-heldout']['gas'], 200000)
        self.assertFalse((self.root / 'rollout-receipt.json').exists())


class SelectionBoundaryTests(ScratchTest):
    def setUp(self):
        super().setUp()
        def task(color):
            return {'train': [{'input': [[1]], 'output': [[1]]},
                              {'input': [[2]], 'output': [[2]]},
                              {'input': [[color, 0]], 'output': [[color]]}],
                    'test': [{'input': [[9, 8, 7, 6, 5]]}]}
        self.tasks = {'dev-a': task(3), 'dev-b': task(4), 'train-only': task(5),
                      'short-dev': {'train': task(6)['train'][:2]}}
        self.manifest = {'tasks': {key: {'split': 'train' if key == 'train-only' else 'dev'}
                                    for key in self.tasks}}
        self.snapshots = {name: {'name': name} for name in ('global_sft', 'trajectory_sft')}

    def choose(self, trainer, model, **config):
        return worker._choose_global(self.tasks, self.manifest, model, trainer, self.snapshots,
            deadline=time.monotonic() + 30, output=self.root, config={'dev_tasks': 8, **config})

    def dev_select(self, trainer, model):
        return worker._dev_select(self.tasks, self.manifest, model, trainer,
            deadline=time.monotonic() + 30, output=self.root, config={'tiny_cpu': True, 'dev_tasks': 8})

    def test_global_choice_uses_identical_predeclared_training_dev_targets(self):
        trainer = ScriptedTrainer()
        scores = {'global_sft': {'3': 4.0, '4': 8.0}, 'trajectory_sft': {'3': 1.0, '4': 3.0}}
        model = ScriptedScores(trainer, lambda t, c: scores[t.current][c])
        result = self.choose(trainer, model)
        self.assertEqual(result['selected'], 'trajectory_sft')
        self.assertEqual(result['mean_nll'], {'global_sft': 6.0, 'trajectory_sft': 2.0})
        self.assertEqual(set(result['predeclared_dev_tasks']), {'dev-a', 'dev-b'})
        self.assertEqual(result['matched_dev_tasks'], result['predeclared_dev_tasks'])
        self.assertTrue(result['comparison_complete'])
        self.assertFalse(result['public_answers_used'])
        self.assertEqual(trainer.restores, ['global_sft', 'trajectory_sft', 'trajectory_sft'])
        self.assertEqual(trainer.frozen, ['trajectory_sft'])
        for checkpoint in self.snapshots:
            calls = [c for c in model.calls if c['checkpoint'] == checkpoint]
            for call, task_id in zip(calls, result['predeclared_dev_tasks']):
                demos = self.tasks[task_id]['train']
                self.assertEqual(call['messages'], grid_messages(demos[:-1], demos[-1]['input']))
                self.assertEqual(call['completion'], encode_grid(demos[-1]['output']))

    def test_global_incomplete_task_cannot_select_on_easier_matched_subset(self):
        trainer = ScriptedTrainer()
        scores = {'global_sft': {'3': 9.0, '4': 1.0}, 'trajectory_sft': {'3': 0.1, '4': None}}
        result = self.choose(trainer, ScriptedScores(trainer, lambda t, c: scores[t.current][c]))
        self.assertEqual(result['matched_dev_tasks'], ['dev-a'])
        self.assertEqual(result['selected'], 'global_sft')
        self.assertEqual(result['mean_nll'], {})
        self.assertFalse(result['comparison_complete'])
        self.assertEqual(result['status'], 'inconclusive-default-global-sft')
        self.assertEqual(trainer.frozen, ['global_sft'])

    def test_global_equal_scores_prefer_sft_and_no_eligible_tasks_default(self):
        trainer = ScriptedTrainer()
        result = self.choose(trainer, ScriptedScores(trainer, lambda t, c: 1.0))
        self.assertEqual(result['selected'], 'global_sft')
        (self.root / 'global-checkpoint-selection.json').unlink()
        model = ScriptedScores(trainer, lambda t, c: self.fail('no dev scoring admitted'))
        result = self.choose(trainer, model, dev_tasks=0)
        self.assertEqual(result['selected'], 'global_sft')
        self.assertFalse(result['comparison_complete'])
        self.assertEqual(model.calls, [])

    def test_dev_selection_adapts_visible_demos_and_resets_each_option(self):
        trainer = ScriptedTrainer()
        model = ScriptedScores(trainer, lambda t, c: 4.0 if t.steps == 0 else 1.0)
        result = self.dev_select(trainer, model)
        self.assertEqual(result['selected_ttt_steps'], 1)
        self.assertTrue(result['comparison_complete'])
        self.assertEqual(len(trainer.ended), 4)
        self.assertIsNone(trainer._task_id)
        for task_id, demos, steps in trainer.adaptations:
            self.assertEqual(demos, self.tasks[task_id.removeprefix('dev:')]['train'][:-1])
            self.assertEqual(steps, 1)
        for call in model.calls:
            demos = self.tasks[call['task_id'].removeprefix('dev:')]['train']
            self.assertEqual(call['messages'], grid_messages(demos[:-1], demos[-1]['input']))
            self.assertEqual(call['completion'], encode_grid(demos[-1]['output']))

    def test_dev_invalid_option_cannot_promote_on_matched_subset(self):
        trainer = ScriptedTrainer()
        model = ScriptedScores(trainer, lambda t, c: None if t.steps and c == '4' else
                               (0.1 if t.steps else 9.0))
        result = self.dev_select(trainer, model)
        self.assertEqual(result['complete_matched_tasks'], ['dev-a'])
        self.assertEqual(result['selected_ttt_steps'], 0)
        self.assertEqual(result['mean_nll'], {})
        self.assertFalse(result['comparison_complete'])
        self.assertIsNone(trainer._task_id)

    def test_dev_incomplete_actual_updates_block_promotion_despite_valid_score(self):
        trainer = ScriptedTrainer(incomplete_task='dev:dev-b')
        model = ScriptedScores(trainer, lambda t, c: 0.1 if t.steps else 9.0)
        result = self.dev_select(trainer, model)
        self.assertTrue(all(row['score']['valid'] for row in result['rows']))
        self.assertEqual(result['selected_ttt_steps'], 0)
        self.assertEqual(result['mean_nll'], {})
        self.assertFalse(result['comparison_complete'])
        self.assertIsNone(trainer._task_id)


if __name__ == '__main__':
    unittest.main()
