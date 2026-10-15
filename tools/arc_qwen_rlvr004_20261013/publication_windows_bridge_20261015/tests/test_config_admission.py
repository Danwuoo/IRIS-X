"""Offline structural admission tests, never native Windows acceptance.

Windows files and probe receipts exist only in an explicit in-memory filesystem.
The /run/WSL socket is mocked metadata, not an exercised interop connection. The
synthetic interpreter is never executed, no SDK is imported, and no credentials,
network, provider, training, or genuine native acceptance receipt are accessed.
Run this same suite normally and with -O; security gates must survive both.
"""
import ast
import builtins
import copy
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[2]
CASES = frozenset(('metadata', 'mutex', 'job_tree', 'deadline', 'pipe_eof',
                   'supervisor_kill', 'parent_death', 'source_unchanged',
                   'framed_operation_deadline', 'framed_official_rpc_deadline'))
VERSIONS = {'code_predecessor': 20, 'code': 21, 'inactive_predecessor': 39,
            'inactive': 40, 'active': 41}
INTEROP = '/run/WSL/777_SYNTHETIC_interop'
NATIVE_SOURCES = frozenset(('win_runtime.py', 'win_supervisor.py', 'protocol.py',
                           'native_config.py', 'native_auth.py', 'sdk_worker.py', 'sdk-lock.json'))
PROBE_SOURCES = frozenset(('win_runtime.py', 'win_supervisor.py', 'protocol.py', 'native_probe.py'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(document):
    return (json.dumps(document, sort_keys=True) + '\n').encode()


def load_source(name, path):
    """Compile source directly, preserving the test interpreter's optimization."""
    module = ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    try:
        exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                     optimize=sys.flags.optimize), vars(module))
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


CONFIG = load_source('windows_admission_test_config', ROOT / 'config.py')
LAUNCH = load_source('windows_admission_test_launch', ROOT / 'launch.py')


class SyntheticFixture:
    """Only test data: its receipt is never materialized or used by a worker."""

    def __init__(self, testcase):
        temporary = tempfile.TemporaryDirectory(prefix='windows-config-test-',
                                                 dir=REPOSITORY / '.irisx')
        testcase.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / 'synthetic-home'
        self.home.mkdir()
        prefix = self.root / 'synthetic-posix-venv'
        (prefix / 'bin').mkdir(parents=True)
        sdk = prefix / 'lib/python3.12/site-packages'
        sdk.mkdir(parents=True)
        executable = prefix / 'bin/python'
        executable.write_bytes(b'SYNTHETIC INTERPRETER DATA; NEVER EXECUTE\n')
        executable.chmod(0o700)
        (prefix / 'pyvenv.cfg').write_text('home = /synthetic-not-executed\n')
        self.runtime = {'venv_prefix': str(prefix),
            'executable': {'path': str(executable), 'resolved_path': str(executable),
                           'sha256': sha(executable.read_bytes())},
            'python_version': [3, 12, 14], 'sdk_root': str(sdk),
            'home': str(self.home), 'requests_ca_bundle': None,
            'interop_environment_sha256': {'WSL_INTEROP': sha(INTEROP.encode())}}
        self.source_bytes = {name: (ROOT / name).read_bytes()
                             for name in NATIVE_SOURCES | PROBE_SOURCES}
        windows_executable = b'SYNTHETIC WINDOWS EXECUTABLE; NEVER EXECUTE\n'
        self.bridge = {
            'executable': {'native_path': r'C:\SyntheticBridge\venv\Scripts\python.exe',
                'wsl_path': '/mnt/c/SyntheticBridge/venv/Scripts/python.exe',
                'sha256': sha(windows_executable)},
            'supervisor': {'native_path': r'C:\SyntheticBridge\source\win_supervisor.py',
                'wsl_path': '/mnt/c/SyntheticBridge/source/win_supervisor.py',
                'sha256': sha(self.source_bytes['win_supervisor.py'])},
            'configuration': {'native_path': r'C:\SyntheticBridge\configuration.json',
                'wsl_path': '/mnt/c/SyntheticBridge/configuration.json', 'sha256': ''},
            'native_acceptance': {'path': str(self.root / 'MEMORY-ONLY-synthetic-probe.json'),
                                  'sha256': ''}}
        self.native = {'format': 'irisx/run008-windows-sdk-runtime-v1',
            'account': 'danielwuu', 'versions': dict(VERSIONS),
            'source_root': r'C:\SyntheticBridge\source',
            'runtime': {'executable': {'path': self.bridge['executable']['native_path'],
                                       'sha256': sha(windows_executable)},
                        'base_executable': {'path': r'C:\SyntheticPython312\python.exe',
                                            'sha256': sha(b'SYNTHETIC BASE INTERPRETER')},
                        'pyvenv_cfg_sha256': sha(b'SYNTHETIC WINDOWS PYVENV CONFIG'),
                        'python_version': [3, 12, 14]},
            'sources': {name: {'bytes': len(raw), 'sha256': sha(raw)}
                        for name, raw in self.source_bytes.items() if name != 'native_probe.py'}}
        # These booleans only exercise structural parsing. No test asserts that
        # they are genuine native observations or grants execution from them.
        self.proof = {'format': 'irisx/windows-native-probe-v1', 'ok': True,
            'native_windows': True, 'network_used': False, 'real_auth_accessed': False,
            'checks': {name: {'ok': True} for name in CASES},
            'source_sha256': {name: sha(self.source_bytes[name]) for name in PROBE_SOURCES},
            'python_version': '3.12.14', 'python_executable_sha256': sha(windows_executable),
            'python_base_executable_sha256': self.native['runtime']['base_executable']['sha256'],
            'pyvenv_cfg_sha256': self.native['runtime']['pyvenv_cfg_sha256']}
        self.files = {self.bridge['executable']['wsl_path']: windows_executable,
                      self.bridge['supervisor']['wsl_path']: self.source_bytes['win_supervisor.py']}
        self.sync_native()
        self.sync_proof()
        repository = self.root / 'repository'
        (repository / '.git').mkdir(parents=True)
        candidate = self.root / 'candidate'
        candidate.mkdir()
        scratch = self.root / 'scratch'
        self.manifest_path = candidate / 'manifest.json'
        self.manifest = {'datasets': [{'reference': CONFIG.DREF, 'id': 12504696,
            'expected_predecessor_version': 20, 'expected_version': 21}],
            'notebooks': [{'role': role, 'existing_notebook_id': 138123872,
                'existing_notebook_reference': CONFIG.REF,
                'expected_predecessor_version': before, 'expected_version': after,
                'dataset_sources': [CONFIG.DREF + '/21'], 'predecessor_source_sha256': 'a' * 64}
                for role, before, after in [('inactive', 39, 40), ('rlvr004', 40, 41)]]}
        self.manifest_path.write_bytes(encoded(self.manifest))
        self.manifest_sha = sha(encoded(self.manifest))
        self.document = {'format': CONFIG.FORMAT, 'repository_root': str(repository),
            'candidate_root': str(candidate), 'scratch_root': str(scratch),
            'state_root': str(scratch / 'state'), 'evidence_root': str(scratch / 'evidence'),
            'gpu_stop_path': str(scratch / 'STOP'), 'runtime': self.runtime,
            'windows_bridge': self.bridge, 'username': 'danielwuu',
            'publication_manifest_sha256': self.manifest_sha, 'versions': dict(VERSIONS),
            'remote_predecessor': {'code_version': 20, 'notebook_version': 39,
                'notebook_source_sha256': 'a' * 64, 'snapshot_sha256': 'b' * 64,
                'provider_status': 'ERROR'}}
        self.config_path = self.root / 'local-config.json'
        self.rewrite()
        self.reads = []
        self.allowed_local_reads = ({self.config_path, self.manifest_path, executable}
                                    | {ROOT / name for name in self.source_bytes})
        self.real_bounded_read = CONFIG.bounded_read
        self.socket_mode = stat.S_IFSOCK | 0o600
        stack = ExitStack()
        testcase.addCleanup(stack.close)
        stack.enter_context(patch.dict(os.environ, {'HOME': str(self.home),
                                                   'WSL_INTEROP': INTEROP}, clear=True))
        stack.enter_context(patch.object(CONFIG.pwd, 'getpwuid',
            return_value=SimpleNamespace(pw_dir=str(self.home))))
        stack.enter_context(patch.object(CONFIG, 'bounded_read', side_effect=self.read))
        original_stat, original_lstat = Path.stat, Path.lstat

        def fake_stat(path, *args, **kwargs):
            value = str(path)
            self.guard_path(value)
            if value == INTEROP:
                return SimpleNamespace(st_mode=self.socket_mode)
            if value == '/run/WSL':
                return SimpleNamespace(st_mode=stat.S_IFDIR | 0o700)
            if value.startswith('/run/WSL/'):
                raise FileNotFoundError(2, 'unmapped synthetic WSL metadata', value)
            return original_stat(path, *args, **kwargs)

        def fake_lstat(path, *args, **kwargs):
            if str(path) == '/run/WSL' or str(path).startswith('/run/WSL/'):
                return fake_stat(path, *args, **kwargs)
            self.guard_path(str(path))
            return original_lstat(path, *args, **kwargs)

        stack.enter_context(patch.object(Path, 'stat', fake_stat))
        stack.enter_context(patch.object(Path, 'lstat', fake_lstat))
        original_open = os.open

        def guarded_open(path, *args, **kwargs):
            self.guard_path(str(path))
            return original_open(path, *args, **kwargs)

        stack.enter_context(patch.object(os, 'open', side_effect=guarded_open))
        for owner in (builtins, io):
            original_file_open = owner.open

            def guarded_file_open(path, *args, _original=original_file_open, **kwargs):
                if not isinstance(path, int):
                    self.guard_path(str(path))
                return _original(path, *args, **kwargs)

            stack.enter_context(patch.object(owner, 'open', side_effect=guarded_file_open))
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.split('.')[0] in ('kaggle', 'kagglesdk'):
                raise AssertionError('SDK import is outside offline config admission')
            return original_import(name, *args, **kwargs)

        stack.enter_context(patch.object(builtins, '__import__', side_effect=guarded_import))
        for target, name in ((subprocess, 'Popen'), (socket, 'socket'),
                             (socket, 'create_connection'), (os, 'execve')):
            stack.enter_context(patch.object(target, name,
                side_effect=AssertionError('process/network execution is outside this fixture')))

    @staticmethod
    def guard_path(value):
        lower = value.lower().replace('\\', '/')
        if lower.startswith('/mnt/'):
            raise AssertionError('Windows file access must use the explicit in-memory map')
        if '.kaggle' in lower.split('/') or any(word in lower for word in
                ('credentials.json', 'kaggle.json', 'access_token', '/.config/kaggle')):
            raise AssertionError('credential path must not even be inspected')

    def read(self, path, cap):
        self.reads.append((str(path), cap))
        if str(path) in self.files:
            raw = self.files[str(path)]
            CONFIG.need(len(raw) <= cap, 'local_bounded_regular_file')
            return raw
        if str(path).startswith('/mnt/'):
            raise FileNotFoundError('unmapped synthetic Windows file')
        if Path(path) not in self.allowed_local_reads:
            raise AssertionError('unplanned local read: ' + str(path))
        return self.real_bounded_read(path, cap)

    def sync_native(self):
        raw = encoded(self.native)
        self.files[self.bridge['configuration']['wsl_path']] = raw
        self.bridge['configuration']['sha256'] = sha(raw)

    def sync_proof(self):
        raw = encoded(self.proof)
        self.files[self.bridge['native_acceptance']['path']] = raw
        self.bridge['native_acceptance']['sha256'] = sha(raw)

    def rewrite(self):
        raw = encoded(self.document)
        self.config_path.write_bytes(raw)
        self.config_sha = sha(raw)

    def load(self):
        self.rewrite()
        return CONFIG.load(self.config_path, self.config_sha,
                           self.manifest_path, self.manifest_sha)

    def bridge_load(self):
        return CONFIG.load_windows_bridge(self.bridge, VERSIONS)

    def runtime_process(self, runtime):
        stack = ExitStack()
        stack.enter_context(patch.multiple(CONFIG.sys,
            prefix=str(runtime.venv_prefix), base_prefix='/synthetic-base',
            executable=str(runtime.executable), version_info=(*runtime.python_version, 'final', 0),
            flags=SimpleNamespace(isolated=1, dont_write_bytecode=1,
                                  ignore_environment=1, optimize=sys.flags.optimize)))
        stack.enter_context(patch.object(CONFIG.sysconfig, 'get_path',
                                         return_value=str(runtime.sdk_root)))
        stack.enter_context(patch.dict(os.environ, {'HOME': str(self.home),
            'WSL_INTEROP': INTEROP, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0'}, clear=True))
        return stack


class ConfigAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f = SyntheticFixture(self)

    def test_full_static_load_uses_only_exact_mapped_files_and_bounded_reads(self):
        result = self.f.load()
        self.assertEqual(result.windows_bridge, self.f.bridge)
        self.assertEqual(dict(result.versions), VERSIONS)
        with self.assertRaises(TypeError):
            result.versions['active'] = 999
        mapped = [(path, cap) for path, cap in self.f.reads if path.startswith('/mnt/')]
        expected = [(self.f.bridge[key]['wsl_path'], 128 * 1024**2)
                    for key in ('executable', 'supervisor', 'configuration')]
        expected.append((self.f.bridge['configuration']['wsl_path'], 4 * 1024**2))
        self.assertEqual(mapped, expected)
        self.assertIn((str(ROOT / 'native_probe.py'), 1024**2), self.f.reads)
        self.assertFalse(Path(self.f.bridge['native_acceptance']['path']).exists())
        self.assertEqual(set(self.f.proof['checks']), CASES)

    def test_closed_bridge_and_file_binding_schemas(self):
        for field in ('alternate_source', 'credentials'):
            with self.subTest(field=field):
                document = copy.deepcopy(self.f.bridge)
                document[field] = {}
                with self.assertRaisesRegex(ValueError, 'windows_bridge_schema'):
                    CONFIG.load_windows_bridge(document, VERSIONS)
        for key in ('executable', 'supervisor', 'configuration'):
            for field in ('sha256', 'wsl_path', 'native_path'):
                with self.subTest(key=key, field=field):
                    document = copy.deepcopy(self.f.bridge)
                    del document[key][field]
                    with self.assertRaisesRegex(ValueError, 'windows_bridge_file_binding'):
                        CONFIG.load_windows_bridge(document, VERSIONS)

    def test_exact_drive_mapping_rejects_alias_case_and_alternate_root_before_read(self):
        for value in ('/mnt/d/SyntheticBridge/venv/Scripts/python.exe',
                      '/mnt/c/syntheticbridge/venv/Scripts/python.exe',
                      '/tmp/python.exe', '/mnt/c/SyntheticBridge/venv/Scripts/../python.exe'):
            with self.subTest(value=value):
                document = copy.deepcopy(self.f.bridge)
                document['executable']['wsl_path'] = value
                self.f.reads.clear()
                with self.assertRaisesRegex(ValueError, 'windows_bridge_exact_drive_mapping'):
                    CONFIG.load_windows_bridge(document, VERSIONS)
                self.assertEqual(self.f.reads, [])

    def test_native_path_rejects_unc_relative_ads_dot_slash_and_control(self):
        values = (r'\\host\share\python.exe', r'C:python.exe', r'C:\dir\..\python.exe',
                  r'C:\dir\python.exe:stream', r'C:\dir\python.exe.', r'C:\dir\python.exe ',
                  'C:/dir/python.exe', 'C:\\dir\x00python.exe', 'C:\\dir\npython.exe')
        for value in values:
            with self.subTest(value=value):
                document = copy.deepcopy(self.f.bridge)
                document['executable']['native_path'] = value
                with self.assertRaisesRegex(ValueError, 'windows_bridge_native_path'):
                    CONFIG.load_windows_bridge(document, VERSIONS)

    def test_every_mapped_file_hash_is_verified(self):
        for key in ('executable', 'supervisor', 'configuration'):
            with self.subTest(key=key):
                path = self.f.bridge[key]['wsl_path']
                old = self.f.files[path]
                self.f.files[path] = old + b'CHANGED'
                try:
                    with self.assertRaisesRegex(ValueError, 'windows_bridge_file_bytes'):
                        self.f.bridge_load()
                finally:
                    self.f.files[path] = old

    def test_missing_mapped_file_has_no_alternate_path_fallback(self):
        path = self.f.bridge['executable']['wsl_path']
        del self.f.files[path]
        with self.assertRaisesRegex(FileNotFoundError, 'unmapped synthetic Windows file'):
            self.f.bridge_load()
        self.assertEqual(self.f.reads, [(path, 128 * 1024**2)])

    def test_native_configuration_identity_and_versions_match_exactly(self):
        for key, value in (('format', 'wrong'), ('account', 'other'),
                           ('versions', {**VERSIONS, 'active': 42})):
            with self.subTest(key=key):
                old = self.f.native[key]
                self.f.native[key] = value
                self.f.sync_native()
                with self.assertRaisesRegex(ValueError, 'windows_bridge_native_configuration'):
                    self.f.bridge_load()
                self.f.native[key] = old
        self.f.sync_native()

    def test_native_executable_path_and_hash_are_independently_bound(self):
        for key, value in (('path', r'C:\Other\python.exe'), ('sha256', '0' * 64)):
            with self.subTest(key=key):
                old = self.f.native['runtime']['executable'][key]
                self.f.native['runtime']['executable'][key] = value
                self.f.sync_native()
                with self.assertRaisesRegex(ValueError, 'windows_bridge_native_executable_binding'):
                    self.f.bridge_load()
                self.f.native['runtime']['executable'][key] = old
        self.f.sync_native()

    def test_native_source_set_is_exactly_the_seven_reviewed_siblings(self):
        original = copy.deepcopy(self.f.native['sources'])
        for sources in ({key: row for key, row in original.items() if key != 'sdk-lock.json'},
                        {**original, 'alternate.py': {'bytes': 1, 'sha256': 'a' * 64}}):
            with self.subTest(sources=sorted(sources)):
                self.f.native['sources'] = sources
                self.f.sync_native()
                with self.assertRaisesRegex(ValueError, 'windows_native_source_closure'):
                    self.f.bridge_load()

    def test_every_native_source_descriptor_requires_exact_fields_and_types(self):
        for name in sorted(NATIVE_SOURCES):
            original = dict(self.f.native['sources'][name])
            invalid = ({'sha256': original['sha256']}, {**original, 'alternate': 'ignored.py'},
                       {**original, 'bytes': True}, {**original, 'bytes': '1'},
                       {**original, 'sha256': 'bad'})
            for row in invalid:
                with self.subTest(name=name, row=row):
                    self.f.native['sources'][name] = row
                    self.f.sync_native()
                    with self.assertRaisesRegex(ValueError, 'windows_native_source_descriptor'):
                        self.f.bridge_load()
            self.f.native['sources'][name] = original
        self.f.sync_native()

    def test_every_native_source_size_hash_and_actual_sibling_bytes_are_bound(self):
        for name in sorted(NATIVE_SOURCES):
            original = dict(self.f.native['sources'][name])
            for key, value in (('bytes', original['bytes'] + 1), ('sha256', '0' * 64)):
                with self.subTest(name=name, key=key):
                    self.f.native['sources'][name] = {**original, key: value}
                    self.f.sync_native()
                    with self.assertRaisesRegex(ValueError, 'windows_native_source_not_reviewed_sibling'):
                        self.f.bridge_load()
            self.f.native['sources'][name] = original
            self.f.sync_native()
            # Substitute bytes only in the explicitly mocked reader; never
            # change another worker's real source or a Windows file.
            self.f.files[str(ROOT / name)] = self.f.source_bytes[name] + b'\n# synthetic change\n'
            with self.subTest(name=name, key='actual_sibling_bytes'):
                with self.assertRaisesRegex(ValueError, 'windows_native_source_not_reviewed_sibling'):
                    self.f.bridge_load()
            del self.f.files[str(ROOT / name)]

    def test_mutually_matching_receipt_and_native_descriptor_cannot_replace_reviewed_source(self):
        self.f.native['sources']['protocol.py']['sha256'] = '0' * 64
        self.f.proof['source_sha256']['protocol.py'] = '0' * 64
        self.f.sync_native()
        self.f.sync_proof()
        with self.assertRaisesRegex(ValueError, 'windows_native_source_not_reviewed_sibling'):
            self.f.bridge_load()

    def test_supervisor_parent_name_and_source_hash_are_bound(self):
        self.f.native['source_root'] = r'C:\AlternateSource'
        self.f.sync_native()
        with self.assertRaisesRegex(ValueError, 'windows_bridge_supervisor_binding'):
            self.f.bridge_load()
        self.f.native['source_root'] = r'C:\SyntheticBridge\source'
        self.f.native['sources']['win_supervisor.py']['sha256'] = '0' * 64
        self.f.sync_native()
        with self.assertRaisesRegex(ValueError, 'windows_native_source_not_reviewed_sibling'):
            self.f.bridge_load()

    def test_acceptance_receipt_exact_hash_and_closed_binding(self):
        for receipt in ({'path': '/other'}, {'path': '/other', 'sha256': 'bad'},
                        {**self.f.bridge['native_acceptance'], 'fallback': '/other'}):
            with self.subTest(receipt=receipt):
                document = copy.deepcopy(self.f.bridge)
                document['native_acceptance'] = receipt
                with self.assertRaisesRegex(ValueError, 'windows_native_acceptance_binding'):
                    CONFIG.load_windows_bridge(document, VERSIONS)
        self.f.files[self.f.bridge['native_acceptance']['path']] += b' '
        with self.assertRaisesRegex(ValueError, 'local_document_hash'):
            self.f.bridge_load()

    def test_receipt_json_remains_strict_under_mocked_filesystem(self):
        for raw, error in ((b'{"ok":true,"ok":true}', 'duplicate_json_key'),
                           (b'{"x":NaN}', 'nonfinite_json'), (b'[]', 'document_object')):
            with self.subTest(raw=raw):
                receipt = self.f.bridge['native_acceptance']
                self.f.files[receipt['path']] = raw
                receipt['sha256'] = sha(raw)
                with self.assertRaisesRegex(ValueError, error):
                    self.f.bridge_load()

    def test_receipt_native_offline_auth_flags_must_be_exact_booleans(self):
        for key, values in (('ok', (False, 1, None)), ('native_windows', (False, 1, None)),
                            ('network_used', (True, 0, None)),
                            ('real_auth_accessed', (True, 0, None))):
            for value in values:
                with self.subTest(key=key, value=value):
                    old = self.f.proof[key]
                    self.f.proof[key] = value
                    self.f.sync_proof()
                    with self.assertRaisesRegex(ValueError, 'windows_native_probe_incomplete'):
                        self.f.bridge_load()
                    self.f.proof[key] = old
        self.f.sync_proof()

    def test_old_eight_case_receipt_rejected_even_if_all_checks_pass(self):
        for name in ('framed_operation_deadline', 'framed_official_rpc_deadline'):
            del self.f.proof['checks'][name]
        self.assertEqual(len(self.f.proof['checks']), 8)
        self.f.sync_proof()
        with self.assertRaisesRegex(ValueError, 'windows_native_probe_cases'):
            self.f.bridge_load()

    def test_each_required_case_missing_failed_nonboolean_or_extra_rejected(self):
        original = copy.deepcopy(self.f.proof['checks'])
        for name in sorted(CASES):
            for row in (None, {'ok': False}, {'ok': 1}, {}):
                with self.subTest(name=name, row=row):
                    self.f.proof['checks'] = copy.deepcopy(original)
                    if row is None:
                        del self.f.proof['checks'][name]
                    else:
                        self.f.proof['checks'][name] = row
                    self.f.sync_proof()
                    with self.assertRaisesRegex(ValueError, 'windows_native_probe_cases'):
                        self.f.bridge_load()
        self.f.proof['checks'] = {**original, 'unreviewed_case': {'ok': True}}
        self.f.sync_proof()
        with self.assertRaisesRegex(ValueError, 'windows_native_probe_cases'):
            self.f.bridge_load()

    def test_receipt_source_set_is_closed(self):
        original = dict(self.f.proof['source_sha256'])
        for sources in ({k: v for k, v in original.items() if k != 'protocol.py'},
                        {**original, 'alternate.py': 'a' * 64}):
            self.f.proof['source_sha256'] = sources
            self.f.sync_proof()
            with self.assertRaisesRegex(ValueError, 'windows_native_probe_source_schema'):
                self.f.bridge_load()

    def test_each_receipt_source_hash_is_bound(self):
        for name in PROBE_SOURCES:
            with self.subTest(name=name):
                old = self.f.proof['source_sha256'][name]
                self.f.proof['source_sha256'][name] = '0' * 64
                self.f.sync_proof()
                error = ('windows_native_probe_source_bytes' if name == 'native_probe.py'
                         else 'windows_native_probe_stale_source')
                with self.assertRaisesRegex(ValueError, error):
                    self.f.bridge_load()
                self.f.proof['source_sha256'][name] = old
        self.f.sync_proof()

    def test_receipt_runtime_version_executable_base_and_venv_changed_missing_null(self):
        fields = ('python_version', 'python_executable_sha256',
                  'python_base_executable_sha256', 'pyvenv_cfg_sha256')
        for field in fields:
            for change in ('changed', 'missing', 'null'):
                with self.subTest(field=field, change=change):
                    old = self.f.proof[field]
                    if change == 'missing':
                        del self.f.proof[field]
                    else:
                        self.f.proof[field] = None if change == 'null' else (
                            '3.12.99' if field == 'python_version' else '0' * 64)
                    self.f.sync_proof()
                    with self.assertRaisesRegex(ValueError, 'windows_native_probe_runtime'):
                        self.f.bridge_load()
                    self.f.proof[field] = old
        self.f.sync_proof()

    def test_global_interpreter_receipt_without_bound_venv_config_is_not_admitted(self):
        self.f.proof['pyvenv_cfg_sha256'] = None
        self.f.sync_proof()
        with self.assertRaisesRegex(ValueError, 'windows_native_probe_runtime'):
            self.f.bridge_load()

    def test_mutually_null_base_and_venv_hashes_cannot_satisfy_runtime_binding(self):
        original_native = copy.deepcopy(self.f.native['runtime'])
        original_proof = copy.deepcopy(self.f.proof)
        for selected in (('base',), ('venv',), ('base', 'venv')):
            with self.subTest(selected=selected):
                self.f.native['runtime'] = copy.deepcopy(original_native)
                self.f.proof = copy.deepcopy(original_proof)
                if 'base' in selected:
                    self.f.native['runtime']['base_executable']['sha256'] = None
                    self.f.proof['python_base_executable_sha256'] = None
                if 'venv' in selected:
                    self.f.native['runtime']['pyvenv_cfg_sha256'] = None
                    self.f.proof['pyvenv_cfg_sha256'] = None
                self.f.sync_native()
                self.f.sync_proof()
                with self.assertRaisesRegex(ValueError, 'windows_native_probe_runtime_schema'):
                    self.f.bridge_load()

    def test_mutually_matching_malformed_python_versions_cannot_satisfy_runtime_binding(self):
        versions = (([3, 12, True], '3.12.True'), (['3', 12, 14], '3.12.14'),
                    ([3, 13, 0], '3.13.0'), ([3, 12, -1], '3.12.-1'),
                    ([3, 12, 100], '3.12.100'), ([3, 12], '3.12'),
                    ('3.12.14', '3...1.2...1.4'), (None, None))
        for native, receipt in versions:
            with self.subTest(native=native, receipt=receipt):
                self.f.native['runtime']['python_version'] = native
                self.f.proof['python_version'] = receipt
                self.f.sync_native()
                self.f.sync_proof()
                with self.assertRaisesRegex(ValueError, 'windows_native_probe_runtime_schema'):
                    self.f.bridge_load()

    def test_local_manifest_versions_and_remote_predecessor_are_checked_before_bridge(self):
        for key, value, error in (('active', 42, 'local_successor_versions'),
                                   ('code', True, 'local_version_integer')):
            with self.subTest(key=key):
                old = self.f.document['versions'][key]
                self.f.document['versions'][key] = value
                self.f.reads.clear()
                with self.assertRaisesRegex(ValueError, error):
                    self.f.load()
                self.assertFalse(any(path.startswith('/mnt/') for path, cap in self.f.reads))
                self.f.document['versions'][key] = old
        self.f.document['remote_predecessor']['notebook_version'] = 38
        with self.assertRaisesRegex(ValueError, 'local_remote_predecessor_versions'):
            self.f.load()

    def test_credential_guard_never_inspects_auth_paths_or_claims_oauth(self):
        before = {name for name in sys.modules if name.split('.')[0] in ('kaggle', 'kagglesdk')}
        result = self.f.load()
        with self.f.runtime_process(result.runtime):
            proof = CONFIG.credential_guard(result)
        self.assertIs(proof['credential_contents_inspected'], False)
        self.assertIs(proof['native_oauth_verified'], False)
        self.assertEqual(proof['format'], 'irisx/windows-bridge-wsl-boundary-v1')
        self.assertEqual(before, {name for name in sys.modules
                                  if name.split('.')[0] in ('kaggle', 'kagglesdk')})
        self.assertFalse(any('kaggle' in path.lower() for path, cap in self.f.reads))


class InteropAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f = SyntheticFixture(self)

    def test_pinned_interop_socket_is_only_cross_os_environment_inherited(self):
        runtime = CONFIG.load_runtime(self.f.runtime)
        inherited = {'HOME': str(self.f.home), 'WSL_INTEROP': INTEROP,
            'PATH': '/synthetic-bin', 'HTTPS_PROXY': 'http://synthetic-proxy',
            'SSL_CERT_FILE': '/synthetic-cert', 'KAGGLE_API_TOKEN': 'SYNTHETIC-NOT-A-TOKEN',
            'PYTHONPATH': '/unreviewed', 'PYTHONHOME': '/unreviewed', 'LD_PRELOAD': '/unreviewed',
            'WSL_DISTRO_NAME': 'unreviewed', 'UNRELATED': 'not inherited'}
        original = dict(inherited)
        result = CONFIG.child_environment(runtime, inherited)
        self.assertEqual(result, {'HOME': str(self.f.home), 'WSL_INTEROP': INTEROP,
            'PATH': '/synthetic-bin', 'HTTPS_PROXY': 'http://synthetic-proxy',
            'SSL_CERT_FILE': '/synthetic-cert', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0'})
        self.assertEqual(inherited, original)
        self.assertNotIn('WSLENV', result)

    def test_interop_pins_require_exact_single_key_and_sha256(self):
        for pins in ({}, {'WSL_INTEROP': 'bad'}, {'WSL_INTEROP': 'a' * 64, 'WSLENV': 'b' * 64},
                     {'WSLENV': 'a' * 64}, None):
            with self.subTest(pins=pins):
                self.f.runtime['interop_environment_sha256'] = pins
                with self.assertRaisesRegex(ValueError, 'reviewed_wsl_interop_required'):
                    CONFIG.load_runtime(self.f.runtime)

    def test_changed_or_missing_interop_fails_before_environment_is_returned(self):
        runtime = CONFIG.load_runtime(self.f.runtime)
        for value in (None, INTEROP + '-changed', '', 123):
            with self.subTest(value=value):
                environment = {'HOME': str(self.f.home)}
                if value is not None:
                    environment['WSL_INTEROP'] = value
                with self.assertRaisesRegex(ValueError, 'wsl_interop_environment_changed'):
                    CONFIG.child_environment(runtime, environment)

    def test_interop_must_be_socket_under_run_wsl_with_exact_suffix(self):
        for mode in (stat.S_IFREG | 0o600, stat.S_IFDIR | 0o700):
            with self.subTest(mode=mode):
                self.f.socket_mode = mode
                with self.assertRaisesRegex(ValueError, 'wsl_interop_socket_required'):
                    CONFIG.load_runtime(self.f.runtime)
        self.f.socket_mode = stat.S_IFSOCK | 0o600
        for value in ('/run/OTHER/777_interop', '/run/WSL/777_socket'):
            with self.subTest(value=value), patch.dict(os.environ, {'WSL_INTEROP': value}):
                self.f.runtime['interop_environment_sha256'] = {'WSL_INTEROP': sha(value.encode())}
                with self.assertRaisesRegex(ValueError, 'wsl_interop_socket_required'):
                    CONFIG.load_runtime(self.f.runtime)

    def test_unreviewed_wslenv_mapping_cannot_be_forwarded(self):
        runtime = CONFIG.load_runtime(self.f.runtime)
        for value in ('KAGGLE_API_TOKEN/u', 'HOME/p', 'PYTHONPATH/p', 'PATH/l'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'unreviewed_cross_os_environment_mapping'):
                    CONFIG.child_environment(runtime, {'HOME': str(self.f.home),
                        'WSL_INTEROP': INTEROP, 'WSLENV': value})
        environment = CONFIG.child_environment(runtime, {'HOME': str(self.f.home),
                                                         'WSL_INTEROP': INTEROP, 'WSLENV': ''})
        self.assertNotIn('WSLENV', environment)


class LauncherAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f = SyntheticFixture(self)

    def arguments(self, mode='publish'):
        self.f.rewrite()
        return [mode, 'validate', '--local-config', str(self.f.config_path),
            '--local-config-sha', self.f.config_sha, '--manifest', str(self.f.manifest_path),
            '--manifest-sha', self.f.manifest_sha]

    def test_source_pins_match_checked_in_source_without_test_override(self):
        self.assertEqual(LAUNCH.CONFIG_SOURCE_SHA256, sha((ROOT / 'config.py').read_bytes()))
        self.assertEqual(set(LAUNCH.ENTRY_SHA256), {'rl_transport.py', 'rl_collect.py', 'recovery_entry.py'})
        for name, digest in LAUNCH.ENTRY_SHA256.items():
            self.assertEqual(digest, sha((ROOT / name).read_bytes()), name)
        self.assertEqual(LAUNCH.config_module().FORMAT, CONFIG.FORMAT)

    def test_exact_binding_flags_allow_separate_and_equals_forms(self):
        for arguments in (['validate', '--local-config', '/exact', '--local-config-sha', 'a' * 64],
                          ['validate', '--local-config=/exact', '--local-config-sha=' + 'a' * 64]):
            result = LAUNCH.binding_arguments(arguments)
            self.assertEqual((result.local_config, result.local_config_sha), ('/exact', 'a' * 64))

    def test_duplicate_missing_abbreviated_and_separator_bindings_rejected(self):
        good = ['validate', '--local-config', '/exact', '--local-config-sha', 'a' * 64]
        bad = (good + ['--local-config=/other'], good + ['--local-config-sha', 'b' * 64],
               good + ['--local-c=/other'], good + ['--local-config-s', 'b' * 64],
               good + ['--'], ['validate'], ['validate', '--local-config', '/exact'])
        for arguments in bad:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                LAUNCH.binding_arguments(arguments)

    def test_binding_argument_count_type_length_and_nul_are_bounded(self):
        good = ['validate', '--local-config', '/exact', '--local-config-sha', 'a' * 64]
        for arguments in (good + ['x'] * 124, good + [None], good + ['x' * 8193],
                          good + ['invalid\x00argument']):
            with self.subTest(length=len(arguments)):
                with self.assertRaisesRegex(ValueError, 'bounded_operator_arguments_required'):
                    LAUNCH.binding_arguments(arguments)

    def test_exact_bound_interpreter_entry_and_forwarded_argv_for_both_modes(self):
        for mode, name in (('publish', 'rl_transport.py'), ('collect', 'rl_collect.py'), ('recover', 'recovery_entry.py')):
            with self.subTest(mode=mode), patch.dict(os.environ, {
                    'PYTHONPATH': '/alternate-source', 'KAGGLE_API_TOKEN': 'SYNTHETIC-NOT-A-TOKEN'}):
                arguments = self.arguments(mode)
                original = list(arguments)
                with patch.object(LAUNCH, 'pinned_source', wraps=LAUNCH.pinned_source) as checked:
                    executable, argv, environment = LAUNCH.plan(arguments)
                self.assertEqual(executable, self.f.runtime['executable']['path'])
                self.assertEqual(argv, [executable, '-I', '-B', str(ROOT / name), *arguments[1:]])
                self.assertEqual(arguments, original)
                self.assertEqual(checked.call_args_list[-1].args,
                                 (ROOT / name, LAUNCH.ENTRY_SHA256[name]))
                self.assertEqual(environment, {'HOME': str(self.f.home), 'WSL_INTEROP': INTEROP,
                    'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONHASHSEED': '0'})

    def test_main_execve_uses_exact_plan_no_shell_or_alternate_source(self):
        arguments = self.arguments()
        expected = LAUNCH.plan(arguments)
        with patch.object(sys, 'argv', [str(ROOT / 'launch.py'), *arguments]), \
                patch.object(LAUNCH.os, 'execve') as execve:
            LAUNCH.main()
        execve.assert_called_once_with(*expected)

    def test_config_source_pin_rejects_alternate_sibling_before_evaluation(self):
        alternate = self.f.root / 'config.py'
        marker = self.f.root / 'must-not-be-created'
        alternate.write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
        with patch.object(LAUNCH, '__file__', str(self.f.root / 'launch.py')):
            with self.assertRaisesRegex(ValueError, 'operator_source_bytes'):
                LAUNCH.config_module()
        self.assertFalse(marker.exists())

    def test_entry_source_pin_failure_prevents_exec(self):
        for mode, name in (('publish', 'rl_transport.py'), ('collect', 'rl_collect.py'), ('recover', 'recovery_entry.py')):
            with self.subTest(mode=mode), patch.dict(LAUNCH.ENTRY_SHA256, {name: '0' * 64}):
                with self.assertRaisesRegex(ValueError, 'operator_source_bytes'):
                    LAUNCH.plan(self.arguments(mode))

    def test_launch_rejects_wrong_config_hash_and_unbound_modes_before_exec(self):
        arguments = self.arguments()
        arguments[5] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'local_document_hash'):
            LAUNCH.plan(arguments)
        for arguments in ([], ['publish'], ['other', 'validate'], ['publish', '--source=/other']):
            with self.subTest(arguments=arguments), self.assertRaisesRegex(ValueError, 'usage:'):
                LAUNCH.plan(arguments)

    def test_source_reader_rejects_symlinks_special_files_relative_and_wrong_hash(self):
        source = self.f.root / 'source.py'
        source.write_bytes(b'value = 1\n')
        alias = self.f.root / 'alias.py'
        alias.symlink_to(source)
        fifo = self.f.root / 'source-fifo'
        os.mkfifo(fifo)
        for path, digest, error in ((alias, sha(source.read_bytes()), 'linked_operator_source'),
                                    (fifo, 'a' * 64, 'bounded_operator_source_required'),
                                    (Path('relative.py'), 'a' * 64, 'linked_operator_source'),
                                    (source, '0' * 64, 'operator_source_bytes')):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, error):
                LAUNCH.pinned_source(path, digest)

    def test_production_gates_do_not_depend_on_assert_or_sdk_imports(self):
        for name in ('config.py', 'launch.py'):
            tree = ast.parse((ROOT / name).read_bytes())
            self.assertFalse(any(isinstance(node, ast.Assert) for node in ast.walk(tree)), name)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module or '')
            self.assertFalse(any(name.split('.')[0] in ('kaggle', 'kagglesdk') for name in imports))


if __name__ == '__main__':
    unittest.main(verbosity=2)
