"""Self-consistent CPU bundle and actual isolated authenticated-prefix tests."""
from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRATCH = REPO / '.irisx/code18-diagnostics/tests'
SCRATCH.mkdir(parents=True, exist_ok=True)
sys.dont_write_bytecode = True


def load(name, path):
    module = types.ModuleType(name); module.__file__ = str(path); module.__package__ = ''
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


builder = load('bundle_integration_builder', HERE / 'build_local_bundle.py')
guard = load('bundle_integration_guard', REPO / 'tools/arc_learning_agent_20261011/process_guard.py')


class BundleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.tmp.name)
        self.bundle = self.root / 'bundle'

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        return builder.build(self.bundle)

    def test_unchanged_complete_source_and_inert_bundle(self):
        result = self.build()
        archive = self.bundle / 'source-reference/source.zip'
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), builder.BASE_ARCHIVE_SHA256)
        self.assertEqual(result['source_members'], 259)
        self.assertFalse(result['production_admitted'])
        self.assertFalse(result['production_dispatch_authorized'])
        self.assertFalse(result['active_notebook_included'])
        self.assertFalse(result['material_review_included'])
        self.assertFalse(list(self.bundle.rglob('*.ipynb')))
        changed = {name for name in result['deployment'] if result['deployment'][name] != result['original_deployment'][name]}
        self.assertEqual(changed, {'launch_notebook.py', 'prepare_entry.py'})

    def test_pair_namespace_is_coherent(self):
        self.build()
        launch = (self.bundle / 'deployment/launch_notebook.py').read_text()
        prepare = (self.bundle / 'deployment/prepare_entry.py').read_text()
        notebook = (self.bundle / 'deployment/notebook_builder.py').read_text()
        for source in (launch, prepare):
            self.assertIn('irisx-qwen14b-rlvr-20261012-environment005', source)
            self.assertNotIn('irisx-qwen14b-rlvr-20261012-environment004', source)
        self.assertIn('irisx-qwen14b-rlvr-20261012-run005', notebook)
        self.assertIn('irisx-qwen14b-rlvr-20261012-source005', notebook)

    def test_existing_output_not_reused(self):
        self.bundle.mkdir(); sentinel = self.bundle / 'keep'; sentinel.write_bytes(b'original')
        with self.assertRaisesRegex(ValueError, 'fresh'):
            self.build()
        self.assertEqual(sentinel.read_bytes(), b'original')

    def test_outside_ignored_root_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ignored'):
            builder.build(REPO / 'not-an-output')
        self.assertFalse((REPO / 'not-an-output').exists())

    def test_linked_output_parent_rejected(self):
        real = self.root / 'real'; real.mkdir()
        link = self.root / 'link'; link.symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'linked'):
            builder.build(link / 'bundle')

    def test_bad_overlay_namespace_rejected(self):
        original = builder.module
        def changed_module(name, path):
            module = original(name, path)
            read = module.read
            def changed_read(path, *args, **kwargs):
                data = read(path, *args, **kwargs)
                if Path(path) == HERE / 'launch_notebook.py':
                    data = data.replace(b'irisx-qwen14b-rlvr-20261012-environment005', b'irisx-qwen14b-rlvr-20261012-environment004')
                return data
            module.read = changed_read
            return module
        with patch.object(builder, 'module', changed_module):
            with self.assertRaisesRegex(ValueError, 'namespace'):
                self.build()
        self.assertFalse(self.bundle.exists())

    def test_real_owned_child_authenticates_source_then_records_missing_material(self):
        self.build()
        deployment = self.bundle / 'deployment'
        launcher = self.root / 'synthetic-cpu-launcher'; launcher.mkdir()
        environment = self.root / 'synthetic-environment'
        # Test-only namespace relocation. No historical session or epoch is used.
        path = deployment / 'prepare_entry.py'
        raw = path.read_text()
        self.assertEqual(raw.count("Path('/kaggle/working/irisx-qwen14b-rlvr-20261012-run005-launcher')"), 1)
        self.assertEqual(raw.count("Path('/tmp/irisx-qwen14b-rlvr-20261012-environment005')"), 1)
        raw = raw.replace("Path('/kaggle/working/irisx-qwen14b-rlvr-20261012-run005-launcher')", 'Path(' + repr(str(launcher)) + ')')
        raw = raw.replace("Path('/tmp/irisx-qwen14b-rlvr-20261012-environment005')", 'Path(' + repr(str(environment)) + ')')
        path.write_text(raw)
        source = self.bundle / 'source-reference/producer-source'
        inputs = self.root / 'empty-synthetic-inputs'; inputs.mkdir()
        epoch = int(time.time())
        request = {'format': 'irisx/rlvr-parent-preparation-request-v1',
                   'ready': {'source_root': str(source), 'source_sha256': builder.BASE_SOURCE_SHA256},
                   'release': {'production_admitted': True, 'source_sha256': builder.BASE_SOURCE_SHA256,
                               'phase_policy_sha256': '3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda',
                               'environment_sha256': '0f7133bdb22d8cba124537622ab09a98e9450e1649df1b07d4e6661d48e33e28'},
                   'epoch': epoch, 'finalized': {'owner_request': {'original_epoch': epoch}},
                   'launcher_root': str(launcher), 'environment_root': str(environment), 'input_root': str(inputs)}
        request_path = launcher / 'synthetic-request.json'
        request_bytes = (json.dumps(request, sort_keys=True) + '\n').encode()
        request_path.write_bytes(request_bytes)
        request_sha = hashlib.sha256(request_bytes).hexdigest()
        # This runner changes no preparation logic; it checks absent tensor imports
        # after the genuine main() fails at missing target-free Dataset metadata.
        runner = self.root / 'synthetic-prefix-runner.py'
        runner.write_text('from pathlib import Path\nimport json,sys,types\np=Path(' + repr(str(path)) + ')\n'
            'm=types.ModuleType("synthetic_actual_prepare");m.__file__=str(p);m.__package__=""\n'
            'exec(compile(p.read_bytes(),str(p),"exec",dont_inherit=True),vars(m))\n'
            'sys.argv=[str(p),' + repr(str(request_path)) + ',' + repr(request_sha) + ']\n'
            'try:m.main()\nfinally:\n bad=[x for x in ("torch","transformers","peft") if x in sys.modules]\n'
            ' Path("fixture-import-check.json").write_text(json.dumps({"tensor_modules":bad,"synthetic_cpu_only":True}))\n'
            ' if bad:raise AssertionError("unexpected tensor import")\n')
        launch = load('actual_bundle_launcher', deployment / 'launch_notebook.py')
        with self.assertRaises(RuntimeError) as caught:
            launch.run_bounded([sys.executable, '-I', '-B', str(runner)], guard_module=guard,
                directory=launcher / 'preparation', deadline_epoch=time.time() + 45,
                env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'},
                scope='entire-owned-preparation-and-runtime',
                failure_context={'original_epoch': epoch, 'source_sha256': builder.BASE_SOURCE_SHA256,
                                 'request_sha256': request_sha})
        self.assertIn('dataset-resolution', caught.exception.__notes__[0])
        directory = launcher / 'preparation'
        failure = json.loads((directory / 'preparation-failure.json').read_bytes())
        self.assertEqual(failure['stage'], 'dataset-resolution')
        self.assertTrue(failure['source_authenticated'])
        self.assertEqual(failure['request_sha256'], request_sha)
        self.assertFalse(failure['operational_success'])
        self.assertEqual(json.loads((directory / 'fixture-import-check.json').read_bytes())['tensor_modules'], [])
        closure = json.loads((directory / 'closure.json').read_bytes())
        guard.verify_closed_proof(closure['proof'])
        self.assertEqual(closure['proof']['worker_returncode'], 1)
        self.assertFalse(closure['proof']['remaining'])
        self.assertFalse(environment.exists())
        self.assertFalse((launcher / 'installed-parent').exists())


if __name__ == '__main__':
    unittest.main()
