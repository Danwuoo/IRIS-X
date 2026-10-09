"""CPU receipt regression tests; never enable a real calibration worker."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
import zipfile

from tools import arc_next_models as models
from tools import arc_next_offline_runtime as runtime
from tools import arc_next_training as training


class LoadingInfoTests(unittest.TestCase):
    def test_transformers_set_fields_roundtrip_and_stable_order(self):
        original = {'missing_keys': {'z', 'a'}, 'unexpected_keys': frozenset({'c', 'b'}),
                    'mismatched_keys': {('x', (2, 3), (4, 5))}, 'error_msgs': []}
        receipt = models._loading_info_receipt(original)
        parsed = json.loads(models.canonical(receipt))
        self.assertEqual(parsed['missing_keys'], ['a', 'z'])
        self.assertEqual(parsed['unexpected_keys'], ['b', 'c'])
        self.assertEqual(parsed['mismatched_keys'], [['x', [2, 3], [4, 5]]])
        self.assertIsInstance(original['missing_keys'], set)
        self.assertEqual(models.canonical(receipt), models.canonical(models._loading_info_receipt(original)))

    def test_empty_sets_and_legacy_lists_preserve_json_meaning(self):
        empty = {'missing_keys': set(), 'unexpected_keys': set(), 'mismatched_keys': set(), 'error_msgs': []}
        legacy = {key: [] for key in empty}
        self.assertEqual(models.canonical(models._loading_info_receipt(empty)), models.canonical(legacy))
        self.assertEqual(models._loading_info_receipt(legacy), legacy)

    def test_general_canonical_json_still_rejects_sets(self):
        with self.assertRaisesRegex(TypeError, 'Object of type set'):
            models.canonical({'arbitrary': set()})
        with self.assertRaisesRegex(TypeError, 'Object of type set'):
            models.canonical(models._loading_info_receipt({'unknown_field': set()}))

    def _load_fixture(self, loading, key='granite-4.2-8b'):
        spec = models.get_spec(key)
        tokenizer = NS(chat_template='fixture', get_chat_template=lambda: 'fixture',
                       get_vocab=lambda: {'x': 0, 'y': spec.vocab_size - 2})
        moves = []
        model = type(spec.architecture, (), {
            'get_input_embeddings': lambda self: NS(weight=NS(shape=(spec.vocab_size, 4))),
            'get_output_embeddings': lambda self: NS(weight=NS(shape=(spec.vocab_size, 4))),
            'parameters': lambda self: [NS(numel=lambda: 12, dtype='BF16')],
            'state_dict': lambda self: {'weight': NS(shape=(3, 4))},
            'to': lambda self, device: moves.append(device),
        })()
        identity = {'model_id': spec.repository + '@' + spec.revision,
                    'template_sha256': hashlib.sha256(b'fixture').hexdigest(),
                    'tokenizer_max_id': spec.vocab_size - 2,
                    'tensor_inventory': {'weight': {'shape': [3, 4], 'elements': 12}},
                    'vocabulary_mapping_sha256': models.digest(tokenizer.get_vocab()),
                    'tokenizer_special_ids': {}}
        transformer = NS(AutoTokenizer=NS(from_pretrained=lambda *args, **kwargs: tokenizer))
        setattr(transformer, spec.loader_class, NS(from_pretrained=lambda *args, **kwargs: (model, loading)))
        with tempfile.TemporaryDirectory() as temp, \
             patch.dict('sys.modules', {'torch': NS(bfloat16='BF16', float32='F32'), 'transformers': transformer}), \
             patch.object(models, 'validate_material', return_value=identity), \
             patch.object(models, 'validate_environment', return_value={}):
            session = models.load_candidate(temp, key, environment_lock_path='fixture',
                                            device='cpu', allow_experimental_qwen=True)
            models.write_json(Path(temp) / 'model-manifest.json', session.identity)
            parsed = json.loads((Path(temp) / 'model-manifest.json').read_text())
        self.assertEqual(moves, ['cpu'])
        return parsed

    def test_loader_model_manifest_accepts_clean_actual_hf_schema(self):
        parsed = self._load_fixture({'missing_keys': set(), 'unexpected_keys': set(),
                                     'mismatched_keys': set(), 'error_msgs': []})
        self.assertEqual(parsed['loading_info'], {key: [] for key in parsed['loading_info']})

    def test_nonempty_loader_errors_still_fail_before_device_move(self):
        for field, value in [('missing_keys', {'weight'}), ('unexpected_keys', {'other'}),
                             ('mismatched_keys', {('weight', (2,), (3,))}), ('error_msgs', ['failed'])]:
            loading = {'missing_keys': set(), 'unexpected_keys': set(), 'mismatched_keys': set(), 'error_msgs': []}
            loading[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(models.ContractError, 'unexplained model loading'):
                self._load_fixture(loading)

    def test_qwen_allowed_unused_mtp_keys_are_retained_sorted(self):
        parsed = self._load_fixture({'missing_keys': set(), 'unexpected_keys': {'mtp.z', 'mtp.a'},
                                     'mismatched_keys': set(), 'error_msgs': []}, key='qwen3.5-9b')
        self.assertEqual(parsed['loading_info']['unexpected_keys'], ['mtp.a', 'mtp.z'])


def config(root, *, interpreter=False):
    value = {'runtime_root': str(root/'inputs/runtime'), 'model_root': str(root/'inputs/model'),
             'wheels_root': str(root/'inputs/wheels'), 'environment_dir': str(root/'environment'),
             'output_root': str(root/'outputs'), 'run_tag': 'cpu-diagnostic-001', 'training_profile': 'pilot128',
             'enable_training_pilot': True, 'max_wall_seconds': 900, 'adapter_path': None,
             'pins': {key: {'reference': reference, 'manifest_sha256': '0'*64, 'private': True}
                      for key, reference in [('runtime', 'danielwuu/iris-arc-next-runtime/6'),
                                             ('model', 'danielwuu/iris-arc-granite42-8b-offline/2'),
                                             ('wheels', 'danielwuu/iris-arc-next-cu128-cp312-wheels/1')]}}
    if interpreter:
        value.update(interpreter_root=str(root/'inputs/interpreter'), interpreter_dir=str(root/'interpreter'))
        value['pins']['interpreter'] = {'reference': 'danielwuu/iris-arc-next-cpython312-offline/2',
                                      'manifest_sha256': '0'*64, 'private': True}
    (root/'environment').mkdir()
    return value


def completed():
    return {'status': 'completed-calibration', 'training': {'completed_profile': True,
            'budget': {'actual_optimizer_updates': 128}}, 'cleanup': {
            'worker_alive_after_cleanup': False, 'group_still_observable_after_kill': False}}


class WorkflowDiagnosticTests(unittest.TestCase):
    def _native(self, root, receipt):
        settings = config(root)
        def phase(name, *_args, **_kwargs):
            if name == 'CHECK_CPU_IMPORTS':
                return {'status': 'cpu-import-tokenizer-safetensor-verified',
                        'python_network_guard_verified': True, 'missing_local_model_failed_closed': True}
            if name == 'RUN_CALIBRATION':
                return receipt
            return {}
        with patch.object(runtime, 'inspect_runtime', return_value={}), \
             patch.object(runtime, '_runtime_environment', return_value={'environment_lock': 'fixture'}), \
             patch.object(runtime, 'launch_phase', side_effect=phase):
            return runtime._launch_training_native(settings, enabled=True)

    def test_exact_128_and_cleanup_success_still_completes(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self._native(Path(temp), completed())
        self.assertEqual(result['status'], 'completed-training-and-export')
        self.assertFalse(result['architecture_pilot_started'])

    def test_completion_and_cleanup_gate_fail_closed(self):
        cases = []
        for value in [127, True, 128.0, None]:
            item = completed(); item['training']['budget']['actual_optimizer_updates'] = value
            cases.append(item)
        for name, value in [('worker_alive_after_cleanup', True), ('worker_alive_after_cleanup', None),
                            ('group_still_observable_after_kill', True), ('group_still_observable_after_kill', None)]:
            item = completed(); item['cleanup'][name] = value; cases.append(item)
        item = completed(); item['training']['completed_profile'] = False; cases.append(item)
        item = completed(); item['status'] = 'failed'; cases.append(item)
        for item in cases:
            with self.subTest(receipt=item), tempfile.TemporaryDirectory() as temp, \
                 self.assertRaisesRegex(RuntimeError, '128 optimizer updates'):
                self._native(Path(temp), item)

    def test_child_error_and_traceback_are_retained_and_visible(self):
        failed = {'status': 'failed', 'cleanup': completed()['cleanup'], 'error': {
            'type': 'TypeError', 'message': 'Object of type set is not JSON serializable',
            'traceback': 'Traceback: original child frame'}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, 'child TypeError: Object of type set is not JSON serializable'):
                self._native(root, failed)
            result = json.loads((root/'outputs/cpu-diagnostic-001-workflow/result.json').read_text())
            self.assertEqual(result['failed_stage'], 'RUN_CALIBRATION')
            self.assertEqual(result['stages']['RUN_CALIBRATION']['error'], failed['error'])
            self.assertIn('Traceback', result['error']['traceback'])
            with zipfile.ZipFile(root/'outputs/cpu-diagnostic-001-workflow-diagnostics.zip') as archive:
                self.assertEqual(json.loads(archive.read('run_calibration-result.json'))['error'], failed['error'])

    def test_worker_captures_original_traceback_without_gpu_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = training.CalibrationConfig(output_dir=str(root))
            with patch.object(training, '_isolate_worker_process_group'), \
                 patch.object(training, 'load_training_material', side_effect=TypeError('injected child failure')):
                training._worker_entry(asdict(settings))
            result = json.loads((root/'result.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['error']['type'], 'TypeError')
            self.assertIn('TypeError: injected child failure', result['error']['traceback'])
            event = json.loads((root/'events.jsonl').read_text())
            self.assertEqual(event['error'], result['error'])

    def test_exported_evidence_keeps_worker_traceback_and_requires_cleanup(self):
        from tools.arc_next_report import export_report
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'run'; root.mkdir()
            failed = {'status': 'failed', 'error': {'type': 'TypeError', 'message': 'set failure',
                      'traceback': 'Traceback: original child frame'}, 'cleanup': completed()['cleanup']}
            models.write_json(root/'preflight.json', {})
            models.write_json(root/'result.json', failed)
            models.write_json(root/'watchdog-result.json', failed)
            result = export_report(root)
            with zipfile.ZipFile(result['archive']) as archive:
                self.assertEqual(json.loads(archive.read('result.json'))['error'], failed['error'])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/'run'; root.mkdir()
            models.write_json(root/'preflight.json', {})
            models.write_json(root/'watchdog-result.json', {'cleanup': {'worker_alive_after_cleanup': True}})
            with self.assertRaisesRegex(ValueError, 'stop is not confirmed'):
                export_report(root)

    def test_native_cancellation_retains_traceback_and_propagates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); settings = config(root)
            with patch.object(runtime, 'inspect_runtime', side_effect=KeyboardInterrupt('owner stop')), \
                 self.assertRaisesRegex(KeyboardInterrupt, 'owner stop'):
                runtime._launch_training_native(settings, enabled=True)
            result = json.loads((root/'outputs/cpu-diagnostic-001-workflow/result.json').read_text())
            self.assertEqual(result['status'], 'cancelled')
            self.assertIn('KeyboardInterrupt: owner stop', result['error']['traceback'])

    def test_dispatch_surfaces_verified_workflow_error_and_still_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); settings = config(root, interpreter=True)
            def dispatch(*_args, **_kwargs):
                path = root/'outputs/cpu-diagnostic-001-workflow'; path.mkdir()
                models.write_json(path/'result.json', {
                    'format': 'irisx/arc-next-training-workflow-result-v1', 'run_tag': settings['run_tag'],
                    'status': 'failed', 'error': {'type': 'RuntimeError', 'message': 'child TypeError: set failure',
                                                'traceback': 'original child traceback'}})
                return 1
            from tools import arc_next_offline_interpreter as interpreter
            with patch.object(runtime, 'inspect_runtime', return_value={'checks': {
                    'system': True, 'machine': True, 'glibc_minimum': True}}), \
                 patch.object(runtime, 'verify_runtime'), \
                 patch.object(interpreter, 'prepare_interpreter', return_value={'python_executable': '/fake/python', 'manifest_sha256': '0'*64}), \
                 patch.object(runtime, '_dispatch_process', side_effect=dispatch), \
                 self.assertRaisesRegex(RuntimeError, 'child TypeError: set failure'):
                runtime.launch_training(settings, enabled=True)
            result = json.loads((root/'outputs/cpu-diagnostic-001-dispatch/result.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['returncode'], 1)
            self.assertEqual(result['workflow_error']['traceback'], 'original child traceback')

    def test_malformed_workflow_receipt_cannot_mask_dispatch_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); settings = config(root, interpreter=True)
            def dispatch(*_args, **_kwargs):
                path = root/'outputs/cpu-diagnostic-001-workflow'; path.mkdir()
                (path/'result.json').write_text('not valid JSON')
                return 7
            from tools import arc_next_offline_interpreter as interpreter
            with patch.object(runtime, 'inspect_runtime', return_value={'checks': {
                    'system': True, 'machine': True, 'glibc_minimum': True}}), \
                 patch.object(runtime, 'verify_runtime'), \
                 patch.object(interpreter, 'prepare_interpreter', return_value={'python_executable': '/fake/python', 'manifest_sha256': '0'*64}), \
                 patch.object(runtime, '_dispatch_process', side_effect=dispatch), \
                 self.assertRaisesRegex(RuntimeError, 'Pinned CPython workflow failed'):
                runtime.launch_training(settings, enabled=True)
            result = json.loads((root/'outputs/cpu-diagnostic-001-dispatch/result.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['returncode'], 7)


if __name__ == '__main__':
    unittest.main()
