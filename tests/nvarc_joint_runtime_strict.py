"""Independent shared-state candidate oracle and real bundled TRM optimizer.

The candidate oracle is a fixture; the source optimizer comparison uses actual
tiny source models and is not a published-scale runtime/quality claim.
"""
import sys
from pathlib import Path
import tempfile
import unittest
import torch

from irisx.arc_nvarc_candidates import FixtureCandidateBackend, solve_task
from irisx.arc_nvarc_m3_trm import _source_classes, _model_config, _batch, _step, _initial_carry_on_device
from irisx.arc_nvarc_trm_runtime import build_runtime_bundle, runtime_classes, verify_runtime_bundle, construct_source_model
from irisx.arc_nvarc_upstream import SOURCE
from irisx.errors import ValidationError


class JointRuntimeStrictTests(unittest.TestCase):
    def test_joint_votes_and_unique_verification_share_active_task_state(self):
        task = {'task_id': 'oracle', 'train': [{'input': [[1]], 'output': [[2]]}], 'test': [{'input': [[1]]}]}
        events, scores = [], []

        class Oracle(FixtureCandidateBackend):
            active = False
            def begin_task(self, task):
                super().begin_task(task)
                self.active = True
                events.append('begin')
            def verify(self, task, test_index, answer):
                if not self.active:
                    raise AssertionError('verifier used reset state')
                scores.append(answer)
                return float(answer[0][0])
            def supplemental_candidates(self, task, test_index):
                if not self.active:
                    raise AssertionError('supplemental pool used reset state')
                return [{'grid': [[2]], 'source': 'shared'}, {'grid': [[3]], 'source': 'view1'},
                        {'grid': [[3]], 'source': 'view2'}]
            def end_task(self):
                events.append('reset')
                self.active = False
                super().end_task()

        backend = Oracle({'oracle:0': [[[2]]]})
        observed = []
        result = solve_task(task, backend, {'seed': 1, 'maximum_calls_per_task': 1,
            'beams_per_call': 1, 'maximum_new_tokens': 3}, call_observer=observed.append)[0]
        self.assertEqual([[[2]], [[3]]], scores)
        self.assertEqual(['begin', 'reset'], events)
        self.assertFalse(backend.active)
        self.assertEqual((1, 3, 2), (result['returned_sequences'], result['supplemental_sequences'],
                                    result['verification_calls_so_far']))
        self.assertEqual([2, 2], [item['votes'] for item in result['ranked']])
        self.assertEqual([[[2]], [[3]]], result['attempts'])
        self.assertEqual(1, len([event for event in observed if event.get('branch') == 'trm' and event['status'] == 'reserved']))

    def test_bundled_source_optimizer_matches_pinned_source_and_restores_imports(self):
        threads = torch.get_num_threads()
        torch.set_num_threads(1)
        try:
            root = SOURCE / 'NVARC/external/TinyRecursiveModels'
            original_classes = _source_classes(root)
            old_module = sys.modules['models.layers']
            config = _model_config({'num_puzzle_identifiers': 1})

            def model_and_step(classes):
                core, loss, sparse, adam = classes
                torch.manual_seed(91)
                model = construct_source_model(classes, config, 'cpu')
                optimizers = [sparse(model.model.puzzle_emb.buffers(), world_size=1, lr=.01, weight_decay=.1),
                              adam(model.parameters(), lr=.0001, weight_decay=0., betas=(.9, .95))]
                observation = _step(model, _batch([[1, 2]], [[2, 1]], identifier=0), optimizers)
                return model.state_dict(), observation

            control, control_loss = model_and_step(original_classes)
            # A CPU dtype transfer reproduces CopyBackward on the exact source
            # sparse buffer without requiring CUDA in this regression.
            core, loss, sparse, _ = original_classes
            moved = loss(core(config), loss_type='stablemax_cross_entropy').to(dtype=torch.float64)
            self.assertTrue(any(value.requires_grad and not value.is_leaf for value in moved.buffers()))
            with self.assertRaisesRegex(ValueError, 'non-leaf'):
                sparse(moved.model.puzzle_emb.buffers(), world_size=1)
            cpu_model = construct_source_model(original_classes, config, 'cpu')
            batch = _batch([[1, 2]], [[2, 1]], identifier=0)
            with torch.device('meta'):
                broken = cpu_model.initial_carry(batch)
                corrected = _initial_carry_on_device(cpu_model, batch)
            self.assertEqual('meta', broken.inner_carry.z_H.device.type)
            self.assertTrue(all(value.device.type == 'cpu' for value in
                [corrected.inner_carry.z_H, corrected.inner_carry.z_L, corrected.steps, corrected.halted,
                 *corrected.current_data.values()]))
            with tempfile.TemporaryDirectory() as directory:
                bundle = Path(directory) / 'bundle'
                binding = build_runtime_bundle(root, bundle)
                with runtime_classes(bundle, binding['bundle_digest']) as classes:
                    actual, actual_loss = model_and_step(classes)
                    self.assertEqual((bundle / 'models/layers.py').resolve(), Path(sys.modules['models.layers'].__file__).resolve())
                self.assertIs(old_module, sys.modules['models.layers'])
                self.assertEqual(control_loss, actual_loss)
                self.assertEqual(set(control), set(actual))
                self.assertTrue(all(torch.equal(value, actual[name]) for name, value in control.items()))
                with (bundle / 'models/layers.py').open('ab') as stream:
                    stream.write(b'\n# modified source\n')
                with self.assertRaisesRegex(ValidationError, 'inventory'):
                    verify_runtime_bundle(bundle, binding['bundle_digest'])
        finally:
            torch.set_num_threads(threads)


if __name__ == '__main__':
    unittest.main()
