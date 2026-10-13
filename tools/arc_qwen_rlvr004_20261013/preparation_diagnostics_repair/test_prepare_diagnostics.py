"""Synthetic, stdlib-only CPU diagnostics tests; no installer/model/provider work."""
from pathlib import Path
import ast
import contextlib
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
FROZEN = HERE.parent / 'support/deployment'


def load_overlay(destination):
    destination.mkdir()
    shutil.copyfile(FROZEN / 'source_loader.py', destination / 'source_loader.py')
    shutil.copyfile(HERE / 'launch_notebook.py', destination / 'launch_notebook.py')
    path = destination / 'prepare_entry.py'
    shutil.copyfile(HERE / 'prepare_entry.py', path)
    module = types.ModuleType('synthetic_preparation_overlay')
    module.__file__ = str(path)
    module.__package__ = ''
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True), vars(module))
    return module


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.saved_modules = {name: sys.modules.get(name) for name in ('source_loader', 'launch_notebook')}
        self.module = load_overlay(self.root / 'deployment')
        self.launcher = self.root / 'run005-launcher'
        self.stage = self.launcher / 'preparation'
        self.stage.mkdir(parents=True)
        self.environment = self.root / 'environment005'
        self.environment.mkdir()
        self.module.DIAGNOSTIC_LAUNCHER_ROOT = self.launcher
        self.module.DIAGNOSTIC_ENVIRONMENT_ROOT = self.environment
        self.request = {'launcher_root': str(self.launcher), 'environment_root': str(self.environment),
                        'ready': {'source_sha256': 'a' * 64}}
        self.previous_cwd = Path.cwd()
        os.chdir(self.stage)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        os.chdir(self.previous_cwd)
        for name, value in self.saved_modules.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
        self.temporary.cleanup()

    def diagnostic(self):
        return json.loads((self.stage / 'preparation-failure.json').read_bytes())

    def execute_failure(self, error=None, stage='offline-installation', **kwargs):
        if error is None:
            error = ValueError('PRIVATE_EXCEPTION_TEXT /private/evaluator credentials environment argv')
        def failing(request, diagnostics):
            diagnostics.mark(stage)
            diagnostics.source_authenticated = True
            raise error
        with patch.object(self.module, '_prepare', failing):
            with self.assertRaises(type(error)) as caught:
                self.module.prepare(self.request, request_sha256='b' * 64, **kwargs)
        self.assertIs(caught.exception, error)
        return error

    def test_safe_failure_keeps_original_and_closed_summary(self):
        self.execute_failure(stage='source-authentication')
        row = self.diagnostic()
        self.assertEqual(row['stage'], 'source-authentication')
        self.assertEqual(row['request_sha256'], 'b' * 64)
        self.assertEqual(row['source_sha256'], 'a' * 64)
        self.assertEqual(row['exception_type'], 'ValueError')
        self.assertTrue(row['diagnostic_only'])
        for key in ('closure_authority', 'model_or_GPU_execution_claim', 'scoring_authority', 'operational_success'):
            self.assertIs(row[key], False)
        raw = (self.stage / 'preparation-failure.json').read_bytes()
        self.assertLessEqual(len(raw), self.module.DIAGNOSTIC_BYTES)
        for secret in (b'PRIVATE_EXCEPTION_TEXT', b'evaluator', b'credentials', b'environment', b'argv'):
            self.assertNotIn(secret, raw)
        self.assertEqual(stat.S_IMODE((self.stage / 'preparation-failure.json').stat().st_mode), 0o600)

    def test_small_private_log_separate_from_summary(self):
        raw = b'PRIVATE_INSTALLER_DETAIL\n' * 4
        (self.environment / 'installation.log').write_bytes(raw)
        self.execute_failure()
        row = self.diagnostic()
        descriptor = row['installer_log']
        self.assertEqual(row['installer_log_status'], 'retained')
        self.assertEqual(descriptor['original_bytes'], len(raw))
        self.assertEqual(descriptor['bytes'], len(raw))
        self.assertFalse(descriptor['truncated'])
        self.assertEqual(descriptor['offsets'], [{'source_offset': 0, 'excerpt_offset': 0, 'bytes': len(raw)}])
        self.assertEqual((self.stage / descriptor['filename']).read_bytes(), raw)
        self.assertEqual(descriptor['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(descriptor['sha256_scope'], 'retained-excerpt-bytes-only')
        self.assertNotIn(b'PRIVATE_INSTALLER_DETAIL', (self.stage / 'preparation-failure.json').read_bytes())

    def test_oversize_log_has_exact_bounded_first_and_last_offsets(self):
        cap = self.module.INSTALLER_EXCERPT_BYTES
        raw = b'F' * (cap // 2) + b'not-retained' * cap + b'L' * (cap // 2)
        (self.environment / 'installation.log').write_bytes(raw)
        self.execute_failure()
        descriptor = self.diagnostic()['installer_log']
        self.assertEqual(descriptor['original_bytes'], len(raw))
        self.assertEqual(descriptor['bytes'], cap)
        self.assertTrue(descriptor['truncated'])
        self.assertEqual(descriptor['offsets'], [
            {'source_offset': 0, 'excerpt_offset': 0, 'bytes': cap // 2},
            {'source_offset': len(raw) - cap // 2, 'excerpt_offset': cap // 2, 'bytes': cap // 2}])
        self.assertEqual((self.stage / descriptor['filename']).read_bytes(), b'F' * (cap // 2) + b'L' * (cap // 2))
        self.assertNotIn('original_sha256', descriptor)

    def test_sparse_huge_log_does_not_expand_copy(self):
        log = self.environment / 'installation.log'
        with log.open('wb') as stream:
            stream.write(b'head')
            stream.seek(8 * 1024**3)
            stream.write(b'tail')
        self.execute_failure()
        descriptor = self.diagnostic()['installer_log']
        self.assertEqual(descriptor['original_bytes'], 8 * 1024**3 + 4)
        self.assertEqual(descriptor['bytes'], self.module.INSTALLER_EXCERPT_BYTES)
        self.assertTrue(descriptor['truncated'])

    def test_symlink_log_is_not_read(self):
        target = self.root / 'private-target'
        target.write_bytes(b'PRIVATE_TARGET')
        (self.environment / 'installation.log').symlink_to(target)
        with patch.object(self.module.os, 'pread', side_effect=AssertionError('must not read symlink')):
            self.execute_failure()
        self.assertIsNone(self.diagnostic()['installer_log'])
        self.assertFalse((self.stage / 'installation-log-excerpt.bin').exists())

    def test_hardlink_log_is_not_read(self):
        target = self.root / 'private-target'
        target.write_bytes(b'PRIVATE_TARGET')
        os.link(target, self.environment / 'installation.log')
        with patch.object(self.module.os, 'pread', side_effect=AssertionError('must not read hardlink')):
            self.execute_failure()
        self.assertIsNone(self.diagnostic()['installer_log'])

    def test_fifo_log_never_blocks_or_reads(self):
        os.mkfifo(self.environment / 'installation.log')
        with patch.object(self.module.os, 'pread', side_effect=AssertionError('must not read FIFO')):
            self.execute_failure()
        self.assertIsNone(self.diagnostic()['installer_log'])

    def test_symlink_environment_directory_is_not_followed(self):
        actual = self.root / 'actual-environment'
        self.environment.rename(actual)
        (actual / 'installation.log').write_bytes(b'PRIVATE_TARGET')
        self.environment.symlink_to(actual, target_is_directory=True)
        self.execute_failure()
        self.assertIsNone(self.diagnostic()['installer_log'])

    def test_mutated_log_is_not_blessed(self):
        log = self.environment / 'installation.log'
        log.write_bytes(b'initial-log')
        original = os.pread
        def mutate(fd, count, offset):
            raw = original(fd, count, offset)
            log.write_bytes(b'mutated-log')
            return raw
        with patch.object(self.module.os, 'pread', mutate):
            self.execute_failure()
        self.assertIsNone(self.diagnostic()['installer_log'])
        self.assertFalse((self.stage / 'installation-log-excerpt.bin').exists())

    def test_replaced_log_is_not_blessed(self):
        log = self.environment / 'installation.log'
        log.write_bytes(b'initial-log')
        original = os.pread
        def replace(fd, count, offset):
            raw = original(fd, count, offset)
            log.rename(self.environment / 'retained-original')
            log.write_bytes(b'changed-log')
            return raw
        with patch.object(self.module.os, 'pread', replace):
            self.execute_failure()
        self.assertIsNone(self.diagnostic()['installer_log'])

    def test_reused_diagnostics_never_overwrite_original(self):
        self.execute_failure(stage='source-authentication')
        before = {p.name: p.read_bytes() for p in self.stage.iterdir()}
        self.execute_failure(stage='installed-parent-runtime')
        after = {p.name: p.read_bytes() for p in self.stage.iterdir()}
        self.assertEqual(before, after)

    def test_existing_excerpt_is_not_reused_or_overwritten(self):
        stale = self.stage / 'installation-log-excerpt.bin'
        stale.write_bytes(b'stale')
        (self.environment / 'installation.log').write_bytes(b'fresh')
        self.execute_failure()
        self.assertEqual(stale.read_bytes(), b'stale')
        self.assertIsNone(self.diagnostic()['installer_log'])

    def test_existing_summary_symlink_is_not_followed(self):
        target = self.root / 'old-private-summary'
        target.write_bytes(b'unchanged')
        (self.stage / 'preparation-failure.json').symlink_to(target)
        self.execute_failure(stage='source-authentication')
        self.assertEqual(target.read_bytes(), b'unchanged')

    def test_wrong_cwd_does_not_write_or_read_log(self):
        os.chdir(self.root)
        (self.environment / 'installation.log').write_bytes(b'PRIVATE_TARGET')
        self.execute_failure()
        self.assertEqual(list(self.stage.iterdir()), [])

    def test_symlink_destination_directory_is_not_followed(self):
        actual = self.launcher / 'actual-stage'
        self.stage.rename(actual)
        self.stage.symlink_to(actual, target_is_directory=True)
        self.execute_failure()
        self.assertEqual(list(actual.iterdir()), [])

    def test_unmatched_request_environment_never_reads_log(self):
        self.request['environment_root'] = '/private/unapproved-environment'
        self.execute_failure()
        self.assertEqual(list(self.stage.iterdir()), [])

    def test_copy_or_summary_write_failure_preserves_same_exception(self):
        (self.environment / 'installation.log').write_bytes(b'installer')
        with patch.object(self.module, '_diagnostic_new_file', side_effect=OSError('synthetic disk full')):
            self.execute_failure()
        self.assertFalse((self.stage / 'preparation-failure.json').exists())

    def test_fsync_failure_preserves_original_exception(self):
        with patch.object(self.module.os, 'fsync', side_effect=OSError('synthetic fsync failure')):
            self.execute_failure(stage='source-authentication')

    def test_custom_exception_class_name_is_never_recorded(self):
        private_type = type('PRIVATE_EXCEPTION_NAME', (Exception,), {})
        self.execute_failure(private_type('private text'), stage='source-authentication')
        row = self.diagnostic()
        self.assertEqual(row['exception_type'], 'OtherException')
        self.assertNotIn('PRIVATE_EXCEPTION_NAME', json.dumps(row))

    def test_system_exit_and_keyboard_interrupt_are_preserved(self):
        for error in (SystemExit(19), KeyboardInterrupt()):
            with self.subTest(exception=type(error).__name__):
                for p in self.stage.iterdir():
                    p.unlink()
                self.execute_failure(error, stage='source-authentication')
                self.assertEqual(self.diagnostic()['exception_type'], type(error).__name__)

    def test_stage_markers_are_fixed_and_bounded(self):
        tracker = self.module._PreparationDiagnostics(self.request, 'b' * 64)
        try:
            tracker.mark('PRIVATE_STAGE_TEXT')
            for _ in range(1000):
                tracker.mark('source-authentication')
        finally:
            tracker.close()
        raw = (self.stage / 'preparation-stages.jsonl').read_bytes()
        self.assertLessEqual(len(raw), self.module.STAGE_JOURNAL_BYTES)
        self.assertNotIn(b'PRIVATE_STAGE_TEXT', raw)
        for line in raw.splitlines():
            self.assertEqual(set(json.loads(line)), {'stage', 'observed_epoch', 'observed_monotonic'})
            self.assertIn(json.loads(line)['stage'], self.module.PREPARATION_STAGES)

    def test_unverified_request_never_claims_request_or_source_digest(self):
        tracker = self.module._PreparationDiagnostics(self.request, 'invalid')
        try:
            tracker.fail(ValueError('not relevant'))
        finally:
            tracker.close()
        row = self.diagnostic()
        self.assertIsNone(row['source_sha256'])
        self.assertIsNone(row['request_sha256'])
        self.assertFalse(row['source_authenticated'])

    def test_success_has_complete_marker_but_no_failure_or_authority_receipt(self):
        def success(request, diagnostics):
            diagnostics.mark('complete')
            return {'synthetic': True}
        with patch.object(self.module, '_prepare', success):
            self.assertEqual(self.module.prepare(self.request), {'synthetic': True})
        self.assertFalse((self.stage / 'preparation-failure.json').exists())
        rows = [json.loads(x) for x in (self.stage / 'preparation-stages.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['stage'], 'complete')

    @contextlib.contextmanager
    def synthetic_preparation_path(self, *, install_error=None):
        """Run real preparation control flow with all material/native work mocked."""
        import time
        source = self.root / 'source/runtime'
        source.mkdir(parents=True)
        policy = source / 'design/MEASURED-POLICY.json'
        environment = source.parent / 'release/REVIEWED-ENVIRONMENT.json'
        environment.parent.mkdir()
        data = self.root / 'synthetic-data'
        training = self.root / 'synthetic-training'
        interpreter = self.root / 'synthetic-interpreter'
        interpreter.mkdir()
        raw_manifest = b'{"synthetic":true}\n'
        (interpreter / 'interpreter-manifest.json').write_bytes(raw_manifest)
        contract = source / 'baseline/materials/qwen14b/material-contract.json'
        model = {'enabled': True, 'model_key': 'synthetic-model', 'profile_id': 'synthetic-profile',
            'reviewed_deployment_id': 'synthetic-deployment', 'material_addendum_sha256': 'c' * 64,
            'context_limit': 4096, 'prompt_cap': 3072, 'output_cap': 1024, 'tensor_parallel_size': 1,
            'precision': 'bf16-base-fp32-lora', 'seed': 1917, 'model_path': str(self.root / 'synthetic-model'),
            'tokenizer_path': str(contract.parent / 'hf-overlay'), 'wheel_root_path': str(self.root / 'synthetic-wheels'),
            'contract_path': str(contract), 'environment_lock_path': str(contract.parent / 'environment-lock.json')}
        environment.write_bytes(self.module.encoded({'model_config': model}))
        owner = {'owner_id': 'synthetic-owner', 'request_id': 'synthetic-request'}
        raw_owner = self.module.encoded(owner)
        (self.launcher / 'original-request.json').write_bytes(raw_owner)
        descriptor = {'format': 'owned-rl-parent-scorer-material-v1', 'scope': 'production-rl-abc', 'role': 'rl-abc',
            'owner_id': owner['owner_id'], 'original_request_id': owner['request_id'],
            'original_request_sha256': self.module.digest(raw_owner), 'raw_source_sha256': 'a' * 64,
            'evaluator_root': str(data / 'evaluator'), 'evaluator_manifest_sha256': 'd' * 64, 'scorer_pins_sha256': 'e' * 64}
        epoch = int(time.time())
        self.request.update(format='irisx/rlvr-parent-preparation-request-v1', epoch=epoch,
            ready={'source_root': str(source), 'source_sha256': 'a' * 64, 'source_archive_path': str(source.parent / 'source.zip')},
            release={'production_admitted': True, 'dataset_references': []},
            finalized={'owner_request': {'original_epoch': epoch},
                       'operator': {'parent_scorer_sha256': self.module.digest(self.module.encoded(descriptor))}},
            input_root=str(self.root / 'synthetic-input'), output_root=str(self.root / 'synthetic-output'))
        roots = {'interpreter': str(interpreter), 'wheels': model['wheel_root_path']}
        installed = {'python_command': [sys.executable, '-I', '-B', 'synthetic-offline-launcher.py'],
                     'interpreter': {'manifest_sha256': self.module.digest(raw_manifest)}}
        calls = []
        def install(*args):
            calls.append('synthetic-install')
            if install_error is not None:
                raise install_error
            return installed
        def run(*args, **kwargs):
            calls.append(('synthetic-run-bounded', args, kwargs))
            return {'synthetic': True}
        leaves = {
            'owned_runtime.parent_scoring': {'worker_environment': lambda **kw: {'SYNTHETIC_ONLY': '1'}},
            'owned_runtime.storage': {'storage_plan': lambda: {'synthetic': True},
                                    'before_session': lambda *a, **kw: {'synthetic': True}},
            'owned_runtime.public_bridge': {'EVALUATOR_MANIFEST_SHA256': 'd' * 64, 'SCORER_PINS_SHA256': 'e' * 64},
            'tools.arc_qwen_transfer_20261012.model_profile': {'MODEL_KEY': 'synthetic-model', 'PROFILE_ID': 'synthetic-profile',
                'DEPLOYMENT_ID': 'synthetic-deployment', 'MATERIAL_ADDENDUM_SHA256': 'c' * 64},
            'tools.arc_qwen_transfer_deployment_20261012.bootstrap': {'resolve_datasets': lambda *a: roots,
                'discover_model': lambda *a, **kw: model['model_path'], 'nonmodel_input_roots': lambda *a: (),
                'prepare_environment': install}}
        modules = {}
        for name, values in leaves.items():
            parts = name.split('.')
            for count in range(1, len(parts)):
                package_name = '.'.join(parts[:count])
                if package_name not in modules:
                    package = types.ModuleType(package_name)
                    package.__path__ = []
                    modules[package_name] = package
            module = types.ModuleType(name)
            vars(module).update(values)
            modules[name] = module
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules, modules))
            stack.enter_context(patch.object(self.module, 'source_import_paths', lambda source: None))
            stack.enter_context(patch.object(self.module, 'authenticate_preinstall_source', lambda *args: (policy, environment)))
            stack.enter_context(patch.object(self.module, 'verify_target_free_materials', lambda *args: (data, training)))
            stack.enter_context(patch.object(self.module, 'load_file', lambda *args: object()))
            stack.enter_context(patch.object(self.module, 'run_bounded', run))
            yield calls, modules

    def test_actual_preparation_flow_all_markers_and_installed_transition_synthetic(self):
        before = {name for name in ('torch', 'transformers', 'peft') if name in sys.modules}
        with self.synthetic_preparation_path() as (calls, modules):
            self.module.prepare(self.request, request_sha256='b' * 64)
        rows = [json.loads(x) for x in (self.stage / 'preparation-stages.jsonl').read_text().splitlines()]
        self.assertEqual([row['stage'] for row in rows], list(self.module.PREPARATION_STAGES))
        self.assertFalse((self.stage / 'preparation-failure.json').exists())
        self.assertEqual(calls[0], 'synthetic-install')
        name, args, kwargs = calls[1]
        self.assertEqual(name, 'synthetic-run-bounded')
        self.assertEqual(args[0][1:3], ['-I', '-B'])
        self.assertEqual(args[0][3], 'synthetic-offline-launcher.py')
        self.assertEqual(Path(args[0][4]).name, 'parent_entry.py')
        self.assertEqual(kwargs['deadline_epoch'], self.request['epoch'] + 42180)
        self.assertEqual(kwargs['directory'], self.launcher / 'installed-parent')
        self.assertEqual(before, {name for name in ('torch', 'transformers', 'peft') if name in sys.modules})

    def test_actual_preparation_flow_install_failure_is_truthful_synthetic(self):
        error = RuntimeError('SYNTHETIC_INSTALL_PRIVATE_TEXT')
        (self.environment / 'installation.log').write_bytes(b'PRIVATE_INSTALLER_LOG')
        with self.synthetic_preparation_path(install_error=error) as (calls, modules):
            with self.assertRaises(RuntimeError) as caught:
                self.module.prepare(self.request, request_sha256='b' * 64)
        self.assertIs(caught.exception, error)
        self.assertEqual(calls, ['synthetic-install'])
        row = self.diagnostic()
        self.assertEqual(row['stage'], 'offline-installation')
        self.assertTrue(row['source_authenticated'])
        self.assertEqual(row['installer_log_status'], 'retained')
        self.assertFalse((self.launcher / 'installed-parent-request.json').exists())
        self.assertNotIn('SYNTHETIC_INSTALL_PRIVATE_TEXT', json.dumps(row))

    def test_builtin_subclasses_and_custom_exceptions_roundtrip_to_safe_reader(self):
        private_type = type('PRIVATE_EXCEPTION_CLASS', (ValueError,), {})
        for error in (NotImplementedError('private'), BrokenPipeError('private'),
                      UnicodeError('private'), RecursionError('private'), private_type('private'),
                      FileNotFoundError('private'), ValueError('private')):
            with self.subTest(exception=type(error).__name__):
                for path in self.stage.iterdir():
                    path.unlink()
                self.execute_failure(error, stage='source-authentication')
                reader = sys.modules['launch_notebook']
                self.assertIs(self.module.PREPARATION_EXCEPTIONS, reader.PREPARATION_EXCEPTIONS)
                projection = reader.read_preparation_failure(self.stage,
                    {'request_sha256': 'b' * 64, 'source_sha256': 'a' * 64})
                self.assertIsNotNone(projection)
                expected = type(error).__name__ if type(error) in (FileNotFoundError, ValueError) else 'OtherException'
                self.assertEqual(self.diagnostic()['exception_type'], expected)
                self.assertEqual(projection['exception_type'], expected)
                self.assertEqual(projection['stage'], 'source-authentication')
                self.assertNotIn('private', json.dumps(projection).lower())

    def test_original_preparation_ast_is_preserved_except_diagnostic_statements(self):
        frozen = ast.parse((FROZEN / 'prepare_entry.py').read_text())
        overlay = ast.parse((HERE / 'prepare_entry.py').read_text())
        old = next(x for x in frozen.body if isinstance(x, ast.FunctionDef) and x.name == 'prepare')
        new = next(x for x in overlay.body if isinstance(x, ast.FunctionDef) and x.name == '_prepare')
        new.name = old.name
        new.args = old.args
        def diagnostic_statement(statement):
            return any(isinstance(node, ast.Name) and node.id == 'diagnostics' for node in ast.walk(statement))
        new.body = [x for x in new.body if not diagnostic_statement(x)]
        self.assertEqual(ast.dump(old, include_attributes=False), ast.dump(new, include_attributes=False))


if __name__ == '__main__':
    unittest.main()
