"""Offline synthetic binding tests; never access the account's OAuth store."""
import hashlib
import json
from pathlib import Path


def runtime_fixture(root):
    """Exact runtime JSON for static tests; no SDK or credential body is needed."""
    root = Path(root)
    prefix = root / 'native-venv'
    (prefix / 'bin').mkdir(parents=True, exist_ok=True)
    sdk_root = prefix / 'lib/python3.12/site-packages'
    sdk_root.mkdir(parents=True, exist_ok=True)
    executable = prefix / 'bin/python'
    executable.write_bytes(b'OFFLINE-SYNTHETIC-INTERPRETER-NOT-EXECUTABLE-CODE\n')
    executable.chmod(0o700)
    (prefix / 'pyvenv.cfg').write_text('home = /synthetic/not-launched\n')
    home = root / 'native-home'
    home.mkdir(exist_ok=True)
    return {'venv_prefix': str(prefix),
            'executable': {'path': str(executable), 'resolved_path': str(executable),
                           'sha256': hashlib.sha256(executable.read_bytes()).hexdigest()},
            'python_version': [3, 12, 14], 'sdk_root': str(sdk_root),
            'home': str(home), 'requests_ca_bundle': None}

import ast
import copy
import importlib.util
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import venv

SOURCE = Path(__file__).absolute().parents[1]
FROZEN = SOURCE.with_name('publication_run008')


def module_from_file(name, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = ''
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True), vars(module))
    return module


CONFIG = module_from_file('portable_binding_test_config', SOURCE / 'config.py')
LAUNCH = module_from_file('portable_binding_test_launch', SOURCE / 'launch.py')
AUTH = module_from_file('portable_binding_test_auth', SOURCE / 'native_auth.py')


def write_json(path, document):
    path.write_text(json.dumps(document, sort_keys=True) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_fixture(root):
    root = Path(root)
    runtime = runtime_fixture(root)
    repository = root / 'repository'
    (repository / '.git').mkdir(parents=True)
    candidate = root / 'candidate'; candidate.mkdir()
    scratch = root / 'scratch'
    manifest = {'datasets': [{'reference': CONFIG.DREF, 'id': 12504696,
                              'expected_predecessor_version': 20, 'expected_version': 21}],
                'notebooks': [
                    {'role': role, 'existing_notebook_id': 138123872,
                     'existing_notebook_reference': CONFIG.REF,
                     'expected_predecessor_version': before, 'expected_version': after,
                     'dataset_sources': [CONFIG.DREF + '/21'], 'predecessor_source_sha256': 'a' * 64}
                    for role, before, after in [('inactive', 39, 40), ('rlvr004', 40, 41)]]}
    manifest_path = candidate / 'manifest.json'
    manifest_sha = write_json(manifest_path, manifest)
    document = {'format': CONFIG.FORMAT, 'repository_root': str(repository),
                'candidate_root': str(candidate), 'scratch_root': str(scratch),
                'state_root': str(scratch / 'state-run008'), 'evidence_root': str(scratch / 'evidence-run008'),
                'gpu_stop_path': str(scratch / 'STOP'), 'runtime': runtime, 'username': 'danielwuu',
                'publication_manifest_sha256': manifest_sha,
                'versions': {'code_predecessor': 20, 'code': 21, 'inactive_predecessor': 39, 'inactive': 40, 'active': 41},
                'remote_predecessor': {'code_version': 20, 'notebook_version': 39,
                                       'notebook_source_sha256': 'a' * 64, 'snapshot_sha256': 'b' * 64,
                                       'provider_status': 'ERROR'}}
    config_path = root / 'local-config.json'
    config_sha = write_json(config_path, document)
    return document, config_path, config_sha, manifest_path, manifest_sha


class PortableBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='irisx-portable-binding-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.doc, self.config_path, self.config_sha, self.manifest_path, self.manifest_sha = config_fixture(self.root)
        self.home = Path(self.doc['runtime']['home'])
        self.environment = mock.patch.dict(os.environ, {'HOME': str(self.home)}, clear=True)
        self.environment.start(); self.addCleanup(self.environment.stop)
        self.account = mock.patch.object(CONFIG.pwd, 'getpwuid', return_value=types.SimpleNamespace(pw_dir=str(self.home)))
        self.account.start(); self.addCleanup(self.account.stop)

    def rewrite(self):
        self.config_sha = write_json(self.config_path, self.doc)

    def load(self):
        self.rewrite()
        return CONFIG.load(self.config_path, self.config_sha, self.manifest_path, self.manifest_sha)

    def runtime(self):
        return CONFIG.load_runtime(self.doc['runtime'])

    def runtime_process(self, runtime):
        stack = __import__('contextlib').ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.multiple(CONFIG.sys,
            prefix=str(runtime.venv_prefix), base_prefix='/synthetic-base', executable=str(runtime.executable),
            flags=types.SimpleNamespace(isolated=1, dont_write_bytecode=1, ignore_environment=1),
            version_info=(*runtime.python_version, 'final', 0)))
        stack.enter_context(mock.patch.object(CONFIG.sysconfig, 'get_path', return_value=str(runtime.sdk_root)))
        stack.enter_context(mock.patch.dict(os.environ, {'HOME': str(self.home),
            'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0'}, clear=True))
        return stack

    def store(self):
        store = self.home / '.kaggle'; store.mkdir(mode=0o700)
        path = store / 'credentials.json'
        path.write_bytes(b'SYNTHETIC TEST DATA, NEVER AUTHENTICATED\n'); path.chmod(0o600)
        return path

    def test_static_load_without_sdk_or_credentials_or_subprocess(self):
        with mock.patch.object(subprocess, 'run', side_effect=AssertionError('no subprocess')), \
             mock.patch.object(AUTH, 'verify_sdk', side_effect=AssertionError('no SDK')):
            result = self.load()
        self.assertEqual(result.runtime.home, self.home)
        self.assertFalse((self.home / '.kaggle').exists())
        self.assertFalse(any(name.split('.')[0] in ('kaggle', 'kagglesdk') for name in sys.modules))
        self.assertEqual(result.versions['active'], 41)
        with self.assertRaises(TypeError): result.versions['active'] = 42

    def test_closed_runtime_and_config_schemas(self):
        for field in ('extra', 'native_wrapper'):
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.doc); candidate[field] = {}
                with self.assertRaisesRegex(ValueError, 'local_config_schema'): CONFIG.config_schema(candidate)
        self.doc['runtime']['extra'] = True
        with self.assertRaisesRegex(ValueError, 'native_runtime_schema'): self.load()

    def test_no_bool_patch_or_versions(self):
        for version in ([3, 12, True], [3, 12], '3.12.14', [3, 11, 14], [3, 12, -1], [3, 12, 1000]):
            with self.subTest(version=version):
                original = self.doc['runtime']['python_version']; self.doc['runtime']['python_version'] = version
                with self.assertRaisesRegex(ValueError, 'native_python312_exact_patch_required'): self.runtime()
                self.doc['runtime']['python_version'] = original
        self.doc['versions']['code_predecessor'] = True
        with self.assertRaisesRegex(ValueError, 'local_version_integer'): self.load()

    def test_no_bool_remote_or_manifest_versions(self):
        self.doc['remote_predecessor']['code_version'] = True
        with self.assertRaisesRegex(ValueError, 'local_remote_predecessor_version_integer'): self.load()
        self.doc['remote_predecessor']['code_version'] = 20
        manifest = json.loads(self.manifest_path.read_text())
        manifest['datasets'][0]['expected_predecessor_version'] = True
        self.manifest_sha = write_json(self.manifest_path, manifest)
        self.doc['publication_manifest_sha256'] = self.manifest_sha
        with self.assertRaisesRegex(ValueError, 'local_manifest_version_integer'): self.load()

    def test_json_hash_duplicate_nonfinite_and_bounds(self):
        with self.assertRaisesRegex(ValueError, 'local_document_hash'): CONFIG.read_json(self.config_path, '0' * 64)
        for raw, error in ((b'{"a":1,"a":2}', 'duplicate_json_key'),
                           (b'{"a":NaN}', 'nonfinite_json'), (b'{"a":1e999}', 'nonfinite_json'),
                           (b'[]', 'document_object')):
            self.config_path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, error): CONFIG.read_json(self.config_path)
        with self.config_path.open('wb') as stream: stream.truncate(4 * 1024**2 + 1)
        with self.assertRaisesRegex(ValueError, 'bounded_regular'): CONFIG.read_json(self.config_path)

    def test_path_rejects_relative_noncanonical_and_symlink(self):
        for value in ('relative', '/tmp/../etc', '/tmp//duplicate', '/tmp/./dot', '//tmp/item', True, '/tmp/nul\x00'):
            with self.subTest(value=value), self.assertRaises(ValueError): CONFIG.secure_path(value)
        alias = self.root / 'alias'; alias.symlink_to(self.home, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): CONFIG.secure_path(alias / 'missing')

    def test_real_home_mismatch_does_not_get_rewritten(self):
        os.environ['HOME'] = str(self.root)
        with self.assertRaisesRegex(ValueError, 'real_account_home'): self.runtime()
        self.assertEqual(os.environ['HOME'], str(self.root))

    def test_runtime_real_home_mismatch(self):
        self.doc['runtime']['home'] = str(self.root)
        with self.assertRaisesRegex(ValueError, 'real_account_home'): self.runtime()

    def test_sdk_root_is_within_explicit_venv(self):
        self.doc['runtime']['sdk_root'] = str(self.root)
        with self.assertRaisesRegex(ValueError, 'native_sdk_root'): self.runtime()

    def test_executable_wrong_hash_and_target(self):
        self.doc['runtime']['executable']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'native_executable_bytes'): self.runtime()
        self.doc['runtime']['executable']['resolved_path'] = str(self.root)
        with self.assertRaisesRegex(ValueError, 'resolved_identity'): self.runtime()

    def test_executable_leaf_direct_link_accepted_chain_rejected(self):
        executable = Path(self.doc['runtime']['executable']['path'])
        target = self.root / 'reviewed-python'; executable.rename(target); executable.symlink_to(target)
        self.doc['runtime']['executable']['resolved_path'] = str(target)
        self.assertEqual(self.runtime().executable_resolved, target)
        alias = self.root / 'intermediate'; alias.symlink_to(target)
        executable.unlink(); executable.symlink_to(alias)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.runtime()

    def test_executable_parent_link_rejected(self):
        prefix = Path(self.doc['runtime']['venv_prefix'])
        (prefix / 'bin').rename(prefix / 'real-bin'); (prefix / 'bin').symlink_to(prefix / 'real-bin', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'parent_link|symlink'): self.runtime()

    def test_executable_missing_mode_or_oversize(self):
        executable = Path(self.doc['runtime']['executable']['path']); executable.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'regular_executable'): self.runtime()
        executable.chmod(0o700)
        with executable.open('wb') as stream: stream.truncate(128 * 1024**2 + 1)
        with self.assertRaisesRegex(ValueError, 'bounded_regular_file'): self.runtime()

    def test_ca_must_match_current_inherited_path_and_hash(self):
        ca = self.root / 'already-inherited-ca.pem'; ca.write_bytes(b'SYNTHETIC CA DATA\n')
        ca_hash = hashlib.sha256(ca.read_bytes()).hexdigest()
        os.environ['REQUESTS_CA_BUNDLE'] = str(ca)
        with self.assertRaisesRegex(ValueError, 'ca_inherited_mismatch'): self.runtime()
        self.doc['runtime']['requests_ca_bundle'] = {'path': str(ca), 'sha256': ca_hash}
        self.assertEqual(self.runtime().requests_ca_bundle.path, ca)
        ca.write_bytes(b'CHANGED\n')
        with self.assertRaisesRegex(ValueError, 'ca_bytes'): self.runtime()

    def test_config_cannot_select_new_ca(self):
        ca = self.root / 'new-ca.pem'; ca.write_bytes(b'SYNTHETIC')
        self.doc['runtime']['requests_ca_bundle'] = {'path': str(ca), 'sha256': hashlib.sha256(ca.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, 'ca_inherited_mismatch'): self.runtime()

    def test_alternate_tls_rejected_not_transmitted(self):
        for variable in CONFIG.FORBIDDEN_TLS_ENV:
            with self.subTest(variable=variable), mock.patch.dict(os.environ, {variable: ''}):
                with self.assertRaisesRegex(ValueError, 'alternate_tls_environment'): self.runtime()

    def test_environment_strips_secrets_and_import_injection(self):
        runtime = self.runtime()
        inherited = {'HOME': str(self.home), 'PATH': '/normal/path', 'HTTPS_PROXY': 'http://existing-proxy',
                     'SSL_CERT_FILE': '/existing/file', 'SSL_CERT_DIR': '/existing/dir',
                     'KAGGLE_API_TOKEN': 'SYNTHETIC', 'PYTHONPATH': '/unreviewed', 'LD_PRELOAD': '/unreviewed',
                     'UNRELATED': 'not inherited'}
        result = CONFIG.child_environment(runtime, inherited)
        self.assertEqual(set(result), {'HOME', 'PATH', 'HTTPS_PROXY', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
                                       'PYTHONDONTWRITEBYTECODE', 'PYTHONHASHSEED'})
        self.assertEqual(result['HOME'], str(self.home))
        self.assertNotIn('KAGGLE_CONFIG_DIR', result)

    def test_isolated_runtime_accepts_exact_process(self):
        runtime = self.runtime(); self.runtime_process(runtime)
        proof = CONFIG.runtime_guard(runtime)
        self.assertFalse(proof['credential_contents_inspected'])

    def test_runtime_rejects_isolation_prefix_executable_version_and_sdk(self):
        runtime = self.runtime(); self.runtime_process(runtime)
        mismatches = [('prefix', str(self.root), 'bound_venv'),
                      ('base_prefix', str(runtime.venv_prefix), 'bound_venv'),
                      ('executable', str(runtime.executable_resolved) + '-other', 'bound_executable'),
                      ('version_info', (3, 12, 99), 'version_mismatch'),
                      ('flags', types.SimpleNamespace(isolated=0, dont_write_bytecode=1, ignore_environment=1), 'isolated')]
        for key, value, error in mismatches:
            with self.subTest(key=key), mock.patch.object(CONFIG.sys, key, value):
                with self.assertRaisesRegex(ValueError, error): CONFIG.runtime_guard(runtime)
        with mock.patch.object(CONFIG.sysconfig, 'get_path', return_value=str(self.root)):
            with self.assertRaisesRegex(ValueError, 'sysconfig_sdk_root'): CONFIG.runtime_guard(runtime)

    def test_runtime_rejects_credential_or_unknown_environment_even_empty(self):
        runtime = self.runtime(); self.runtime_process(runtime)
        for variable in (*CONFIG.FORBIDDEN_AUTH_ENV, 'UNKNOWN', 'LD_PRELOAD'):
            with self.subTest(variable=variable), mock.patch.dict(os.environ, {variable: ''}):
                with self.assertRaisesRegex(ValueError, 'alternate_auth_or_import'): CONFIG.runtime_guard(runtime)

    def test_credential_guard_only_checks_metadata(self):
        config = self.load(); path = self.store(); self.runtime_process(config.runtime)
        original = os.open
        def guarded_open(name, *args, **kwargs):
            if Path(name) == path: raise AssertionError('credential content must not be opened')
            return original(name, *args, **kwargs)
        with mock.patch.object(os, 'open', side_effect=guarded_open):
            proof = CONFIG.credential_guard(config)
        self.assertTrue(proof['existing_official_store'])
        self.assertFalse(proof['credential_contents_inspected'])

    def test_credentials_require_private_mode_and_regular_single_link(self):
        config = self.load(); path = self.store(); self.runtime_process(config.runtime)
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'oauth_store_mode'): CONFIG.credential_guard(config)
        path.chmod(0o600); os.link(path, path.with_name('hardlink'))
        with self.assertRaisesRegex(ValueError, 'oauth_store_mode'): CONFIG.credential_guard(config)
        path.with_name('hardlink').unlink(); path.unlink(); path.symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'symlink'): CONFIG.credential_guard(config)

    def test_credentials_bounded_and_nonempty(self):
        config = self.load(); path = self.store(); self.runtime_process(config.runtime)
        for size in (0, 65537):
            with path.open('wb') as stream: stream.truncate(size)
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, 'oauth_store_mode'): CONFIG.credential_guard(config)

    def test_alternate_store_files_including_dangling_links_rejected(self):
        config = self.load(); self.store(); self.runtime_process(config.runtime)
        for name in ('kaggle.json', 'access_token', 'access_token.txt'):
            alternate = self.home / '.kaggle' / name
            alternate.symlink_to(self.root / 'missing')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'alternate_credential_store'): CONFIG.credential_guard(config)
            alternate.unlink()

    def test_launcher_protects_config_flags(self):
        good = ['validate', '--local-config', '/x', '--local-config-sha', 'a' * 64]
        self.assertEqual(LAUNCH.binding_arguments(good).local_config, '/x')
        for bad in (good + ['--local-config', '/y'], good + ['--local-config-s', 'b' * 64],
                    good + ['--'], ['validate'], good + ['--local-c=x']):
            with self.subTest(args=bad), self.assertRaises(ValueError): LAUNCH.binding_arguments(bad)

    def test_launcher_source_pin_checked_before_config_evaluation(self):
        with mock.patch.object(LAUNCH, 'CONFIG_SOURCE_SHA256', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'operator_source_bytes'): LAUNCH.config_module()

    def test_launcher_exact_exec_and_forwarding_with_clean_env(self):
        self.rewrite()
        arguments = ['publish', 'validate', '--local-config', str(self.config_path), '--local-config-sha', self.config_sha,
                     '--manifest', str(self.manifest_path), '--manifest-sha', self.manifest_sha]
        with mock.patch.object(LAUNCH, 'CONFIG_SOURCE_SHA256', hashlib.sha256((SOURCE / 'config.py').read_bytes()).hexdigest()), \
             mock.patch.dict(LAUNCH.ENTRY_SHA256, {'rl_transport.py': hashlib.sha256((SOURCE / 'rl_transport.py').read_bytes()).hexdigest()}), \
             mock.patch.dict(os.environ, {'PYTHONPATH': '/unreviewed', 'KAGGLE_API_TOKEN': 'SYNTHETIC'}):
            executable, argv, environment = LAUNCH.plan(arguments)
        self.assertEqual(executable, self.doc['runtime']['executable']['path'])
        self.assertEqual(argv, [executable, '-I', '-B', str(SOURCE / 'rl_transport.py'), *arguments[1:]])
        self.assertNotIn('PYTHONPATH', environment); self.assertNotIn('KAGGLE_API_TOKEN', environment)
        self.assertEqual(environment['HOME'], str(self.home))

    def test_fifo_inputs_fail_promptly_in_real_process(self):
        fifo = self.root / 'fifo'; os.mkfifo(fifo)
        code = "import runpy,sys; c=runpy.run_path(sys.argv[1]); c['read_json'](sys.argv[2])"
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(SOURCE / 'config.py'), str(fifo)],
                                text=True, capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0); self.assertIn('local_bounded_regular_file', result.stderr)
        with self.assertRaisesRegex(ValueError, 'bounded_operator_source'): LAUNCH.pinned_source(fifo, 'a' * 64)

    def test_official_session_ast_is_unchanged(self):
        def official(path):
            tree = ast.parse(path.read_text())
            return next(ast.dump(node, include_attributes=False) for node in tree.body
                        if isinstance(node, ast.ClassDef) and node.name == 'OfficialSession')
        self.assertEqual(official(SOURCE / 'native_auth.py'), official(FROZEN / 'native_auth.py'))
        self.assertEqual((SOURCE / 'sdk-lock.json').read_bytes(), (FROZEN / 'sdk-lock.json').read_bytes())


class SdkBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='irisx-sdk-binding-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sources = {}
        for name in ('kaggle', 'kagglesdk'):
            path = self.root / name / '__init__.py'; path.parent.mkdir()
            path.write_text("value = 'reviewed'\n")
            self.sources[path.relative_to(self.root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.lock = {'format': 'irisx/run008-native-sdk-source-lock-v1',
                     'distributions': {'kaggle': '2.2.4', 'kagglesdk': '0.1.37'}, 'sources': self.sources}
        self.common = {'configured': lambda: types.SimpleNamespace(runtime=types.SimpleNamespace(sdk_root=self.root)),
                       'secure_path': CONFIG.secure_path, 'need': CONFIG.need, 'verified': self.verified}
        patcher = mock.patch.object(__import__('sysconfig'), 'get_path', return_value=str(self.root))
        patcher.start(); self.addCleanup(patcher.stop)
        patcher = mock.patch.object(AUTH.importlib.metadata, 'distribution', side_effect=lambda name:
            types.SimpleNamespace(version=self.lock['distributions'][name], locate_file=lambda _: self.root))
        patcher.start(); self.addCleanup(patcher.stop)

    def verified(self, path, digest, cap):
        if path.name == 'sdk-lock.json':
            self.assertEqual(digest, AUTH.LOCK_SHA256)
            return json.dumps(self.lock).encode()
        raw = CONFIG.bounded_read(path, cap)
        CONFIG.need(hashlib.sha256(raw).hexdigest() == digest, 'artifact_hash_or_size')
        return raw

    def test_sdk_exact_version_root_and_full_source_closure(self):
        root, sources = AUTH.verify_sdk(self.common)
        self.assertEqual(root, self.root); self.assertEqual(sources, self.sources)

    def test_sdk_metadata_version_and_origin_must_match(self):
        for version, root, error in [('wrong', self.root, 'distribution_version'),
                                     ('2.2.4', self.root.parent, 'outside_bound_root')]:
            with self.subTest(error=error), mock.patch.object(AUTH.importlib.metadata, 'distribution',
                    return_value=types.SimpleNamespace(version=version, locate_file=lambda _: root)):
                with self.assertRaisesRegex(ValueError, error): AUTH.verify_sdk(self.common)

    def test_sdk_sysconfig_root_must_match(self):
        with mock.patch.object(__import__('sysconfig'), 'get_path', return_value=str(self.root.parent)):
            with self.assertRaisesRegex(ValueError, 'sysconfig_root'): AUTH.verify_sdk(self.common)

    def test_sdk_unpinned_extra_or_changed_source_rejected(self):
        extra = self.root / 'kaggle/extra.py'; extra.write_text('value = 1\n')
        with self.assertRaisesRegex(ValueError, 'source_closure'): AUTH.verify_sdk(self.common)
        extra.unlink(); (self.root / 'kaggle/__init__.py').write_text('value = 2\n')
        with self.assertRaisesRegex(ValueError, 'artifact_hash_or_size'): AUTH.verify_sdk(self.common)

    def test_sdk_missing_source_or_link_rejected(self):
        path = self.root / 'kaggle/__init__.py'; path.unlink()
        with self.assertRaisesRegex(ValueError, 'source_closure'): AUTH.verify_sdk(self.common)
        path.symlink_to(self.root / 'kagglesdk/__init__.py')
        with self.assertRaisesRegex(ValueError, 'symlink'): AUTH.verify_sdk(self.common)

    def test_sdk_preimport_rejected(self):
        with mock.patch.dict(sys.modules, {'kaggle.unreviewed': types.ModuleType('kaggle.unreviewed')}):
            with self.assertRaisesRegex(ValueError, 'must_not_be_preimported'): AUTH.verify_sdk(self.common)

    def test_source_only_loader_ignores_cached_bytecode(self):
        import py_compile
        source = self.root / 'kaggle/__init__.py'
        malicious = self.root / 'unreviewed.py'; malicious.write_text("value = 'UNREVIEWED CACHE'\n")
        cache = Path(importlib.util.cache_from_source(str(source)))
        cache.parent.mkdir()
        py_compile.compile(str(malicious), cfile=str(cache), doraise=True)
        finder = AUTH.ReviewedSdkFinder(self.root, self.sources, self.common)
        with mock.patch.object(sys, 'path', [str(self.root)]):
            spec = finder.find_spec('kaggle')
            namespace = {}; exec(spec.loader.get_code('kaggle'), namespace)
        self.assertEqual(namespace['value'], 'reviewed')

    def test_source_only_loader_rejects_outside_root_and_unpinned(self):
        other = self.root / 'outside'; (other / 'kaggle').mkdir(parents=True)
        (other / 'kaggle/__init__.py').write_text('value = 1\n')
        finder = AUTH.ReviewedSdkFinder(self.root / 'bound', self.sources, self.common)
        with mock.patch.object(sys, 'path', [str(other)]):
            with self.assertRaisesRegex(ValueError, 'outside_venv'): finder.find_spec('kaggle')
        finder = AUTH.ReviewedSdkFinder(self.root, {}, self.common)
        with mock.patch.object(sys, 'path', [str(self.root)]):
            with self.assertRaisesRegex(ValueError, 'unpinned_import'): finder.find_spec('kaggle')


class IsolatedProcessTests(unittest.TestCase):
    def test_actual_venv_isolated_runtime_and_help_without_store(self):
        if sys.version_info[:2] != (3, 12): self.skipTest('real POSIX Python 3.12 required')
        with tempfile.TemporaryDirectory(prefix='irisx-real-venv-') as temp:
            root = Path(temp); prefix = root / 'venv'
            venv.EnvBuilder(with_pip=False, symlinks=False).create(prefix)
            executable = prefix / 'bin/python'
            self.assertFalse(executable.is_symlink())
            home = pwd.getpwuid(os.getuid()).pw_dir
            runtime = {'venv_prefix': str(prefix), 'executable': {'path': str(executable), 'resolved_path': str(executable),
                         'sha256': hashlib.sha256(executable.read_bytes()).hexdigest()},
                       'python_version': list(sys.version_info[:3]), 'sdk_root': str(prefix / 'lib/python3.12/site-packages'),
                       'home': home, 'requests_ca_bundle': None}
            path = root / 'runtime.json'; write_json(path, runtime)
            code = "import runpy,json,sys; c=runpy.run_path(sys.argv[1]); r=c['load_runtime'](json.load(open(sys.argv[2]))); print(json.dumps(c['runtime_guard'](r)))"
            environment = {'HOME': home, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0'}
            for optimize in ([], ['-O']):
                result = subprocess.run([str(executable), '-I', '-B', *optimize, '-c', code, str(SOURCE / 'config.py'), str(path)],
                                        env=environment, text=True, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(json.loads(result.stdout)['credential_contents_inspected'])
            help_result = subprocess.run([str(executable), '-I', '-B', str(SOURCE / 'launch.py'), '--help'],
                                         env={}, text=True, capture_output=True, timeout=10)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn('--local-config', help_result.stdout)
            self.assertNotIn('LOCAL_CONTRACT_PASS', help_result.stdout)


if __name__ == '__main__':
    unittest.main()
