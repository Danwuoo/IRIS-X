"""CPU regression of both ambient call sites and the installed-loader boundary."""
from contextlib import contextmanager
from pathlib import Path
import ast
import hashlib
import importlib
import importlib.metadata
import json
import os
import shutil
import sys
import tempfile
import time
import types
import unittest
import venv
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
REPO = TOOL.parents[1]
OLD = TOOL / 'preparation_diagnostics_repair'
SCRATCH = REPO / '.irisx/preparation-environment-repair/tmp'
SCRATCH.mkdir(parents=True, exist_ok=True)
sys.dont_write_bytecode = True


def load(name, path):
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


launch = load('preparation_environment_launch', HERE / 'launch_notebook.py')
historical = load('historical_preparation_tests', OLD / 'test_prepare_diagnostics.py')
elf = load('preparation_environment_elf', TOOL / 'loader_repair_run008/tests/elf_fixture.py')
guard = load('preparation_environment_guard', REPO / 'tools/arc_learning_agent_20261011/process_guard.py')
offline = load('preparation_environment_offline', REPO / 'tools/arc_next_offline_environment.py')
GUARD_ENVIRONMENT = {'PYTHONNOUSERSITE': '1', 'PIP_CONFIG_FILE': os.devnull,
    'PIP_NO_INDEX': '1', 'PIP_NO_CACHE_DIR': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'WANDB_MODE': 'offline'}


def load_overlay(destination):
    destination.mkdir()
    shutil.copyfile(TOOL / 'support/deployment/source_loader.py', destination / 'source_loader.py')
    for name in ('launch_notebook.py', 'prepare_entry.py'):
        shutil.copyfile(HERE / name, destination / name)
    return load('successor_preparation', destination / 'prepare_entry.py')


@contextmanager
def runtime(root, *, predecessor=False):
    """Import genuine loader modules with real unchanged dependencies; no model."""
    target = root / 'runtime'
    shutil.copytree(TOOL / 'source/owned_runtime', target / 'owned_runtime')
    shutil.copyfile(TOOL / 'loader_repair_run008/overlays/owned_runtime/environment_v2.py',
                    target / 'owned_runtime/environment_v2.py')
    parent = (TOOL / 'loader_repair_run008/overlays/owned_runtime/parent_scoring.py'
              if predecessor else HERE / 'parent_scoring.py')
    shutil.copyfile(parent, target / 'owned_runtime/parent_scoring.py')
    saved = {name: module for name, module in sys.modules.items()
             if name == 'owned_runtime' or name.startswith('owned_runtime.')}
    for name in saved:
        del sys.modules[name]
    sys.path.insert(0, str(target))
    try:
        yield target, importlib.import_module('owned_runtime.environment_v2'), importlib.import_module('owned_runtime.parent_scoring')
    finally:
        sys.path.remove(str(target))
        for name in list(sys.modules):
            if name == 'owned_runtime' or name.startswith('owned_runtime.'):
                del sys.modules[name]
        sys.modules.update(saved)


class EnvironmentPolicyTests(unittest.TestCase):
    def test_no_ambient_metadata_or_model_import_required(self):
        before = set(sys.modules)
        with patch.object(importlib.metadata, 'distribution', side_effect=AssertionError('ambient lookup forbidden')) as lookup:
            with patch.dict(os.environ, {}, clear=True):
                env = launch.preparation_environment()
        lookup.assert_not_called()
        self.assertNotIn('CUDA_VISIBLE_DEVICES', env)
        self.assertFalse({'torch', 'transformers', 'peft', 'owned_runtime.environment_v2'} & (set(sys.modules) - before))

    def test_closed_environment_retains_only_valid_production_device_controls(self):
        uuid = 'GPU-01234567-89ab-cdef-0123-456789abcdef'
        ambient = {'CUDA_VISIBLE_DEVICES': '0,' + uuid, 'CUDA_DEVICE_ORDER': 'PCI_BUS_ID',
                   'PATH': '/foreign/bin', 'LD_LIBRARY_PATH': '/foreign/lib', 'LD_PRELOAD': '/foreign.so',
                   'LD_AUDIT': '/foreign.so', 'PYTHONPATH': '/private/evaluator',
                   'PYTHONHOME': '/foreign', 'KAGGLE_TOKEN': 'SYNTHETIC', 'HOME': '/private'}
        with patch.dict(os.environ, ambient, clear=True):
            env = launch.preparation_environment()
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'], ambient['CUDA_VISIBLE_DEVICES'])
        self.assertEqual(env['CUDA_DEVICE_ORDER'], 'PCI_BUS_ID')
        self.assertFalse(set(env) & {'LD_PRELOAD', 'LD_AUDIT', 'PYTHONPATH', 'PYTHONHOME', 'KAGGLE_TOKEN', 'HOME'})
        self.assertNotIn('/foreign', json.dumps(env))
        self.assertNotIn('/private', json.dumps(env))

    def test_invalid_device_controls_fail_closed_even_before_install(self):
        for key, values in {'CUDA_VISIBLE_DEVICES': ['', 'all', '0,', '-1', 'GPU-short', '0' * 4097],
                            'CUDA_DEVICE_ORDER': ['', 'arbitrary']}.items():
            for value in values:
                with self.subTest(key=key, value=value[:30]), patch.dict(os.environ, {key: value}, clear=True):
                    with self.assertRaises(ValueError):
                        launch.preparation_environment()

    def test_parent_policy_matches_true_worker_except_owned_library_prefix(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory, runtime(Path(directory)) as (_, e, p):
            for ambient in ({}, {'CUDA_VISIBLE_DEVICES': '0,1', 'CUDA_DEVICE_ORDER': 'FASTEST_FIRST'}):
                with patch.dict(os.environ, ambient, clear=True), patch.object(p, '_worker_library_path',
                        return_value='/synthetic/owned/lib:' + ':'.join(p.TRUSTED_DRIVER_LIBRARY_DIRECTORIES)):
                    parent = launch.preparation_environment()
                    worker = p.worker_environment(fixture=False)
                self.assertEqual(parent['PATH'], ':'.join(p.TRUSTED_DRIVER_EXECUTABLE_DIRECTORIES))
                self.assertEqual(parent['LD_LIBRARY_PATH'], ':'.join(p.TRUSTED_DRIVER_LIBRARY_DIRECTORIES))
                self.assertEqual(worker, {**parent, **GUARD_ENVIRONMENT,
                    'LD_LIBRARY_PATH': '/synthetic/owned/lib:' + parent['LD_LIBRARY_PATH']})

    def test_worker_guard_values_are_fixed_and_fixture_environment_is_unchanged(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory, runtime(Path(directory)) as (_, e, p):
            old_path = TOOL / 'loader_repair_run008/overlays/owned_runtime/parent_scoring.py'
            old = types.ModuleType('owned_runtime.prior_parent_scoring')
            old.__file__, old.__package__ = str(old_path), 'owned_runtime'
            exec(compile(old_path.read_bytes(), str(old_path), 'exec', dont_inherit=True), vars(old))
            with patch.dict(os.environ, {key: 'untrusted' for key in GUARD_ENVIRONMENT}, clear=True), \
                 patch.object(p, '_worker_library_path', return_value='/synthetic/owned/lib'):
                worker = p.worker_environment(fixture=False)
                self.assertEqual({key: worker[key] for key in GUARD_ENVIRONMENT}, GUARD_ENVIRONMENT)
                self.assertEqual(p.worker_environment(fixture=True), old.worker_environment(fixture=True))

    def test_only_fixed_production_guard_values_change_runtime_source(self):
        old_path = TOOL / 'loader_repair_run008/overlays/owned_runtime/parent_scoring.py'
        old = ast.parse(old_path.read_text())
        new = ast.parse((HERE / 'parent_scoring.py').read_text())
        worker = next(node for node in new.body if isinstance(node, ast.FunctionDef) and node.name == 'worker_environment')
        added = [node for node in ast.walk(worker) if isinstance(node, ast.Expr)
                 and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                 and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 'result'
                 and node.value.func.attr == 'update']
        self.assertEqual(len(added), 1)
        self.assertEqual({keyword.arg for keyword in added[0].value.keywords}, set(GUARD_ENVIRONMENT))
        block = next(node for node in worker.body if isinstance(node, ast.If) and added[0] in node.body)
        self.assertEqual(ast.dump(block.test), "UnaryOp(op=Not(), operand=Name(id='fixture', ctx=Load()))")
        block.body.remove(added[0])
        self.assertEqual(ast.dump(old, include_attributes=False), ast.dump(new, include_attributes=False))

    def test_launcher_passes_wrong_ambient_distribution_without_lookup(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory, runtime(Path(directory)) as (_, e, p):
            root = Path(directory)
            output = root / 'output'
            source = root / 'source/runtime'
            source.mkdir(parents=True)
            sentinel = RuntimeError('synthetic stop after actual preparation dispatch')
            loader = types.SimpleNamespace(need=lambda ok, message: None if ok else (_ for _ in ()).throw(ValueError(message)),
                clean_path=lambda path: Path(path), digest=lambda raw: hashlib.sha256(raw).hexdigest(),
                source_import_paths=lambda path: None)
            builder = types.SimpleNamespace(OUTPUT=str(output), SOURCE=str(source.parent),
                build=lambda *a, **kw: {'synthetic': True}, encoded=lambda value: (json.dumps(value) + '\n').encode())
            def loaded(name, path):
                return loader if name == 'rlvr_checked_loader' else builder if name == 'rlvr_checked_builder' else guard
            wrong = types.SimpleNamespace(version='SYNTHETIC_WRONG_VERSION')
            with patch.object(e.importlib.metadata, 'distribution', return_value=wrong) as lookup:
                with self.assertRaisesRegex(ValueError, 'exact installed cuDNN distribution'):
                    p.worker_environment(fixture=False)
                lookup.reset_mock()
                with patch.object(launch, 'load_file', loaded), patch.object(launch, 'run_bounded', side_effect=sentinel) as bounded:
                    with self.assertRaises(RuntimeError) as caught:
                        launch.launch(ready={'source_root': str(source), 'source_sha256': 'a' * 64},
                            release={'production_admitted': True, 'release_role': 'rlvr004'},
                            finalized={'owner_request': {}, 'operator': {}}, loader_source='',
                            output_root=str(output), input_root=str(root / 'inputs'), epoch=int(time.time()))
                self.assertIs(caught.exception, sentinel)
                lookup.assert_not_called()
            argv = bounded.call_args.args[0]
            self.assertEqual(argv[:3], [sys.executable, '-I', '-B'])
            self.assertEqual(Path(argv[3]).name, 'prepare_entry.py')
            self.assertEqual(bounded.call_args.kwargs['env'], launch.preparation_environment())
            request = json.loads(Path(argv[4]).read_text())
            self.assertEqual(request['notebook_python_executable'], sys.executable)
            self.assertEqual(bounded.call_args.kwargs['deadline_epoch'], request['epoch'] + 42180)

    def test_only_intended_deployment_delta(self):
        old = (OLD / 'launch_notebook.py').read_text()
        new = (HERE / 'launch_notebook.py').read_text()
        helper = ast.get_source_segment(new, next(node for node in ast.parse(new).body
            if isinstance(node, ast.FunctionDef) and node.name == 'preparation_environment')) + '\n\n\n'
        new = new.replace(helper, '').replace('os, re, selectors', 'os, selectors')
        new = new.replace("        stage='parent-environment-policy';env=preparation_environment()",
            "        stage='parent-environment-import'\n        from owned_runtime.parent_scoring import worker_environment\n        stage='parent-environment-policy';env=worker_environment(fixture=False)")
        self.assertEqual(old, new)
        old = (OLD / 'prepare_entry.py').read_text()
        new = (HERE / 'prepare_entry.py').read_text()
        new = new.replace('PREPARATION_EXCEPTIONS,preparation_environment', 'PREPARATION_EXCEPTIONS')
        new = new.replace("    diagnostics.mark('preparation-imports')\n", "    diagnostics.mark('preparation-imports')\n    from owned_runtime.parent_scoring import worker_environment\n")
        new = new.replace('env=preparation_environment()', 'env=worker_environment(fixture=False)')
        self.assertEqual(old, new)

    def test_real_worker_loader_source_and_preimport_gates_remain_pinned(self):
        repair = TOOL / 'loader_repair_run008'
        manifest = json.loads((repair / 'OVERLAY-MANIFEST.json').read_text())
        for target, row in manifest['files'].items():
            raw = (repair / row['path']).read_bytes()
            self.assertEqual(len(raw), row['bytes'], target)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'], target)
        runner = (repair / 'overlays/owned_runtime/runner.py').read_text()
        self.assertLess(runner.index('verify_cudnn_installation(config'), runner.index('worker_env=worker_environment'))
        self.assertLess(runner.index('worker_env=worker_environment'), runner.index('launch=register_launch'))
        worker = (repair / 'overlays/owned_runtime/worker.py').read_text()
        self.assertLess(worker.index('verify_child_loader_environment(request'), worker.index('from owned_runtime.factory'))
        self.assertLess(worker.index('verify_child_loader_environment(request'), worker.index('    import torch'))
        self.assertNotIn('preparation_environment', runner + worker)


class PreparationFlowTests(historical.DiagnosticsTests):
    """Rerun all retained diagnostic regressions against the new two-file pair."""
    def setUp(self):
        with patch.object(historical, 'load_overlay', load_overlay):
            super().setUp()

    def test_original_preparation_ast_is_preserved_except_diagnostic_statements(self):
        original = ast.parse((TOOL / 'support/deployment/prepare_entry.py').read_text())
        text = (HERE / 'prepare_entry.py').read_text()
        text = text.replace("    diagnostics.mark('preparation-imports')\n", "    diagnostics.mark('preparation-imports')\n    from owned_runtime.parent_scoring import worker_environment\n")
        text = text.replace('env=preparation_environment()', 'env=worker_environment(fixture=False)')
        current = ast.parse(text)
        old = next(node for node in original.body if isinstance(node, ast.FunctionDef) and node.name == 'prepare')
        new = next(node for node in current.body if isinstance(node, ast.FunctionDef) and node.name == '_prepare')
        new.name, new.args = old.name, old.args
        new.body = [statement for statement in new.body if not any(
            isinstance(node, ast.Name) and node.id == 'diagnostics' for node in ast.walk(statement))]
        self.assertEqual(ast.dump(old, include_attributes=False), ast.dump(new, include_attributes=False))

    def test_preparation_passes_wrong_ambient_distribution_after_install(self):
        with self.synthetic_preparation_path() as (calls, modules):
            wrong = types.SimpleNamespace(version='SYNTHETIC_WRONG_VERSION')
            with patch.object(importlib.metadata, 'distribution', return_value=wrong) as lookup:
                modules['owned_runtime.parent_scoring'].worker_environment = lambda **kw: (_ for _ in ()).throw(AssertionError('ambient worker environment forbidden'))
                self.module.prepare(self.request, request_sha256='b' * 64)
            lookup.assert_not_called()
        self.assertEqual(calls[0], 'synthetic-install')
        self.assertEqual(calls[1][2]['env'], launch.preparation_environment())

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux gcc required for actual ELF proof')
    def test_real_installed_interpreter_valid_flow(self):
        self._installed_flow('valid')

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux gcc required for actual ELF proof')
    def test_real_installed_interpreter_wrong_distribution_rejected(self):
        self._installed_flow('wrong_distribution')

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux gcc required for actual ELF proof')
    def test_real_installed_interpreter_parent_byte_tamper_rejected(self):
        self._installed_flow('parent_tampered')

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux gcc required for actual ELF proof')
    def test_real_installed_interpreter_child_byte_tamper_rejected(self):
        self._installed_flow('child_tampered')

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux gcc required for actual ELF proof')
    def test_real_installed_interpreter_foreign_loaded_backend_rejected(self):
        self._installed_flow('foreign_backend')

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux gcc required for actual ELF proof')
    def test_exact_offline_guard_installed_interpreter_flow(self):
        expected = json.loads((TOOL / 'release/SOURCE-INVENTORY.json').read_text())['files']
        self.assertEqual(hashlib.sha256((REPO / 'tools/arc_next_offline_environment.py').read_bytes()).hexdigest(),
                         expected['baseline/tools/arc_next_offline_environment.py'])
        self._installed_flow('guard_environment')

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux gcc required for actual ELF proof')
    def test_exact_offline_guard_predecessor_reproduces_environment_mismatch(self):
        self._installed_flow('guard_predecessor')

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux gcc required for actual ELF proof')
    def test_exact_offline_guard_wrong_environment_value_rejected(self):
        self._installed_flow('guard_bad_value')

    @unittest.skipUnless(sys.platform == 'linux' and shutil.which('gcc'), 'Linux gcc required for actual ELF proof')
    def test_exact_offline_guard_extra_environment_key_rejected(self):
        self._installed_flow('guard_extra_key')

    def _installed_flow(self, case):
        # Real interpreter, dist-info, wheel and ELF; all source/material/
        # installer/model work outside the loader transition is mocked.
        with self.synthetic_preparation_path() as (calls, modules):
            fixture_root = self.root / 'elf-fixture'
            fixture_root.mkdir()
            with runtime(fixture_root, predecessor=case == 'guard_predecessor') as (source, e, p):
                config, data = elf.build(fixture_root, source)
                venv.EnvBuilder(with_pip=False, symlinks=True).create(data['prefix'])
                metadata = Path(data['site']) / 'nvidia_cudnn_cu12-9.10.2.21.dist-info'
                metadata.mkdir()
                version = '0.0.0' if case == 'wrong_distribution' else data['policy']['distribution_version']
                (metadata / 'METADATA').write_text('Metadata-Version: 2.1\nName: nvidia-cudnn-cu12\nVersion: ' + version + '\n')
                offline_launcher = None
                if case.startswith('guard_'):
                    (Path(data['site']) / 'sitecustomize.py').write_text(offline.NETWORK_GUARD)
                    (Path(data['prefix']) / offline.NETWORK_GUARD_HOOK_RELATIVE).write_text(offline._network_guard_hook(data['prefix']))
                    offline_launcher = Path(data['prefix']) / 'offline-run.py'
                    offline_launcher.write_text(offline._LAUNCHER)
                data.update(case=case, result_path=str(self.launcher / 'synthetic-parent-result.json'))
                config.write_text(json.dumps(data))
                if case == 'parent_tampered':
                    with (Path(data['lib']) / 'libcudnn_ops.so.9').open('ab') as stream:
                        stream.write(b'tampered before parent verification')
                original_install = modules['tools.arc_qwen_transfer_deployment_20261012.bootstrap'].prepare_environment
                def installed(*args):
                    value = original_install(*args)
                    command = [str(Path(data['prefix']) / 'bin/python'), '-I', '-B'] + (['-O'] if sys.flags.optimize else [])
                    if offline_launcher is not None:
                        command += ['-S', str(offline_launcher)]
                    value['python_command'] = command + [str(HERE / 'cpu_parent_worker.py'), str(config), 'parent']
                    return value
                wrong = types.SimpleNamespace(version='SYNTHETIC_WRONG_AMBIENT_VERSION')
                with patch.object(modules['tools.arc_qwen_transfer_deployment_20261012.bootstrap'], 'prepare_environment', installed), \
                     patch.object(self.module, 'load_file', return_value=guard), \
                     patch.object(self.module, 'run_bounded', launch.run_bounded), \
                     patch.dict(sys.modules, modules), \
                     patch.object(importlib.metadata, 'distribution', return_value=wrong) as lookup:
                    if case in ('valid', 'guard_environment'):
                        self.module.prepare(self.request, request_sha256='b' * 64)
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'owned parent preparation/runtime failed'):
                            self.module.prepare(self.request, request_sha256='b' * 64)
                        self.assertEqual(self.diagnostic()['stage'], 'installed-parent-runtime')
                lookup.assert_not_called()
                row = json.loads(Path(data['result_path']).read_text())
                self.assertTrue(row['synthetic_cpu_only'])
                self.assertTrue(row['isolated'])
                self.assertEqual(row['prefix'], data['prefix'])
                expected_environment = launch.preparation_environment()
                if case.startswith('guard_'):
                    expected_environment.update(GUARD_ENVIRONMENT)
                self.assertEqual(row['preparation_environment'], expected_environment)
                self.assertEqual(row['accepted'], case in ('valid', 'guard_environment'))
                if case in ('valid', 'guard_environment'):
                    self.assertEqual(row['distribution_version'], '9.10.2.21')
                    self.assertEqual(row['child']['api'], 91002)
                    self.assertEqual(row['child']['stage'], 'complete')
                    self.assertEqual(Path(row['deployment_target'][0]).name, 'parent_entry.py')
                    self.assertEqual(row['worker_environment']['LD_LIBRARY_PATH'], data['lib'] + ':' + data['system'])
                    self.assertEqual(len(row['child']['observation']['verified_libraries']), 3)
                elif case in ('parent_tampered', 'wrong_distribution'):
                    self.assertEqual(row['stage'], 'parent-installation-verification')
                    self.assertNotIn('child', row)
                elif case == 'child_tampered':
                    self.assertEqual(row['child']['stage'], 'child-startup')
                    self.assertFalse(row['child']['native_load_attempted'])
                elif case.startswith('guard_'):
                    self.assertEqual(row['child']['stage'], 'child-startup')
                    self.assertFalse(row['child']['native_load_attempted'])
                    self.assertEqual(row['child']['error']['message'], 'actual child environment differs from authenticated loader policy')
                else:
                    self.assertEqual(row['child']['stage'], 'mapping-admission')
                    self.assertEqual(row['child']['api'], 90800)
                    self.assertIn('exact pinned wheel', row['child']['error']['message'])


if __name__ == '__main__':
    unittest.main()
