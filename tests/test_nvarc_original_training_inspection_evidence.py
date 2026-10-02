"""Closed native inspection vectors/reset evidence; entirely artificial fixtures."""
from array import array
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from irisx.arc_nvarc_combined import atomic
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools import stage_nvarc_original_training_inspection as probe


class NativeInspectionEvidenceTests(unittest.TestCase):
    def test_tiny_source_layout_has_projection_adapters_and_full_save_modules(self):
        config = {'hidden_size': 32, 'num_attention_heads': 4, 'num_key_value_heads': 2,
            'head_dim': 8, 'intermediate_size': 64, 'num_hidden_layers': 1, 'vocab_size': 16}
        layout = probe.trainable_layout(config, 2)
        self.assertEqual(len(layout), 16)
        self.assertEqual(sum(a * b for a, b in layout.values()), 2048)
        self.assertEqual(layout['base_model.model.model.layers.0.self_attn.k_proj.lora_B.default.weight'], [16, 2])
        self.assertEqual(layout['base_model.model.model.embed_tokens.modules_to_save.default.weight'], [16, 32])
        self.assertFalse(any('embed_tokens.lora_' in name for name in layout))

    def test_missing_native_prerequisite_prevents_any_package_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / 'package'
            with patch.object(probe, 'prerequisite', side_effect=ValidationError('native prerequisite incomplete')):
                with self.assertRaisesRegex(ValidationError, 'prerequisite incomplete'):
                    probe.stage(package, 'nvarc-original-qwen3-training-inspect-999')
            self.assertFalse(package.exists())

    def fixture(self, root, fault=None):
        run = 'nvarc-original-qwen3-training-inspect-999'
        plan = {'run_id': run, 'versions': {'torch': '2.8.0'}, 'source_input_tokens': 640,
            'source_supervised_tokens': 256, 'source_maximum_sequence_length': 5,
            'source_inferred_trainable_layout': {'toy': [2, 2]}}
        package = root / 'package'; package.mkdir(); atomic(package / 'plan.json', plan)
        ids = [14, 12, 10, 1, 15]; labels = [-100, -100, -100, 1, 15]
        expected = [{'row': i, 'input_tokens': 5, 'supervised_tokens': 2,
            'input_ids_digest': digest_value(ids), 'labels_digest': digest_value(labels)} for i in range(128)]
        rows = [{**row, 'source_input_ids_equal': True, 'source_labels_equal': True,
            'collator_preserved_input_ids': True, 'retained_byte_offset': i * 20, 'retained_token_bytes': 20}
            for i, row in enumerate(expected)]
        values = array('h', (ids + labels) * 128)
        if sys.byteorder != 'little': values.byteswap()
        raw = {'worker': b'trusted worker fixture', 'solver': b'trusted solver fixture',
            'expected_rows': canonical_bytes(expected), 'texts_gzip': probe.gzip.compress(b'[]', mtime=0)}
        weights = [{'name': 'toy', 'shape': [2, 2], 'elements': 4, 'dtype': 'torch.bfloat16',
            'finite': True, 'sha256': 'a' * 64}]
        trainable = [{k: v for k, v in weights[0].items() if k not in ('finite', 'sha256')}]
        observation = {'format': probe.FORMAT, 'versions': plan['versions'], 'optimizer_created': False,
            'model_forwards': 0, 'optimizer_steps': 0, 'generation_calls': 0, 'teacher_calls': 0,
            'prohibited_attempts': 0, 'contains_evaluator_truth': False, 'full_long_ttt_completed': False,
            'prepared_rows_digest': digest_value(rows), 'trainable_before_trainer': trainable,
            'trainable_after_trainer': trainable, 'trainable_parameters': 4,
            'every_source_input_and_label_equal': True, 'prepared_argument_lengths': {'max_length': 8192},
            'gradient_checkpoint_flags': [{'module': 'toy', 'value': True}], 'trainer_origins': []}
        content = {'plan.json': plan, 'payload-bindings.json': {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()},
            'terminal.json': {'run_id': run, 'outcome': 'complete', 'wall_seconds': 20.0,
                'contains_evaluator_truth': False, 'model_forwards': 0, 'optimizer_steps': 0,
                'generations': 0, 'teacher_calls': 0, 'paid_usd': 0},
            'hardware.json': {'inventory': [{'uuid': str(i), 'name': 'NVIDIA L4', 'bf16': True} for i in range(4)],
                'torch': '2.8.0+cu128', 'cuda': '12.8'}, 'source-verification.json': {'inventory': {}},
            'model-verification.json': {'all_ten_files_verified': True, 'model_material_digest': probe.MATERIAL},
            'native/native-inspection.json': observation, 'native/prepared-rows.json': rows,
            'native/adapter-topology.json': {'trainable': trainable}, 'native/baseline-inventory.json': weights,
            'native/reset-inventory.json': weights,
            'native/reset-observation.json': {'all_saved_tensors_restored': True, 'independent_detached_storage_observed': True},
            'native/guard-state.json': {'installed_before_unsloth_import': True,
                'module_call_paths_blocked': ['__call__', '_wrapped_call_impl', '_call_impl'],
                'optimizer_construction_blocked': True, 'backward_and_step_blocked': True}}
        binary = values.tobytes()
        if fault == 'vector-change': binary = b'\x02\x00' + binary[2:]
        elif fault == 'bool-cost': content['terminal.json']['model_forwards'] = False
        elif fault == 'mask-summary-lie': rows[0]['source_labels_equal'] = False
        elif fault == 'reset-change': content['native/reset-inventory.json'] = [{**weights[0], 'sha256': 'b' * 64}]
        elif fault == 'nonfinite-state': weights[0]['finite'] = False
        elif fault == 'duplicate-gpu': content['hardware.json']['inventory'][-1]['uuid'] = '0'
        elif fault == 'extra-vector-suffix': binary += b'\x00\x00'
        elif fault == 'effective-length': observation['prepared_argument_lengths']['max_length'] = 1024
        elif fault == 'changed-topology': plan['source_inferred_trainable_layout'] = {'other': [2, 2]}
        elif fault == 'dtype-policy':
            trainable[0]['dtype'] = 'torch.float32'
        observation['prepared_rows_digest'] = digest_value(rows)
        blobs = {name: canonical_bytes(value) for name, value in content.items()}
        blobs.update({'inspection.py': raw['worker'], 'solver.py': raw['solver'],
            'expected-rows.json': raw['expected_rows'], 'texts.json': b'[]', 'native/prepared-tokens.i16le': binary})
        # Mutations deliberately rehash the complete envelope. The independent
        # raw-vector/state checks, rather than the archive hash, must reject them.
        atomic(package / 'plan.json', plan)
        index = {'run_id': run, 'plan_digest': digest_value(plan), 'members': [{'path': name,
            'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} for name, body in blobs.items()]}
        path = root / 'result.zip'
        with zipfile.ZipFile(path, 'x') as archive:
            for name, body in blobs.items(): archive.writestr(name, body)
            archive.writestr('manifest.json', canonical_bytes(index))
        return path, package, raw, {'plan_digest': digest_value(plan)}

    def read_fixture(self, path, package, raw, checked):
        with patch.object(probe, 'preflight', return_value=checked), patch.object(probe, 'payloads_for', return_value=raw), \
                patch.object(probe, 'source_inventory', return_value={}), patch.object(probe, 'PARAMETERS', 4):
            return probe.verify(path, package)

    def test_complete_raw_vector_recount_and_full_saved_reset(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.read_fixture(*self.fixture(Path(temporary)))
        self.assertTrue(result['source_long_ttt_prerequisite_qualified'])
        self.assertTrue(result['every_source_input_and_label_equal'])
        self.assertFalse(result['full_long_ttt_completed'])
        self.assertFalse(result['correctness_scored'])

    def test_rehashed_raw_vector_mask_reset_cost_and_hardware_faults_are_rejected(self):
        for fault in ('vector-change', 'bool-cost', 'mask-summary-lie', 'reset-change', 'nonfinite-state',
                'duplicate-gpu', 'extra-vector-suffix'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaises(ValidationError):
                    self.read_fixture(*self.fixture(Path(temporary), fault))

    def test_observed_context_topology_or_dtype_difference_does_not_unlock_ttt(self):
        for fault in ('effective-length', 'changed-topology', 'dtype-policy'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                result = self.read_fixture(*self.fixture(Path(temporary), fault))
                self.assertEqual(result['outcome'], 'complete')
                self.assertFalse(result['source_long_ttt_prerequisite_qualified'])


if __name__ == '__main__': unittest.main()
