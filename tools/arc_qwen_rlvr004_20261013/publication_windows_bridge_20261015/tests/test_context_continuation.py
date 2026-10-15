"""Synthetic offline f5 history only; no native/provider/restart evidence."""
import contextlib
import copy
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
PREFIX = ROOT.relative_to(REPO).as_posix() + '/'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


a = load('test_context_adapter_module', ROOT / 'context_continuation.py')
f = load('test_context_historical_fixture', ROOT / 'tests/test_recovery_epoch.py')


class ContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f.EpochTests.setUpClass()
        cls.sources = {name: subprocess.check_output(['git', 'show',
            a.HISTORICAL_COMMIT + ':' + PREFIX + name], cwd=REPO) for name in a.SOURCE_NAMES}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='offline-context-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.historical_repository = Path(self.temp.name) / 'historical-repository'
        self.history = self.historical_repository.joinpath(*a.PACKAGE_SUFFIX[:-1])
        self.history.mkdir(parents=True)
        (self.historical_repository / '.git').mkdir()
        self.current_repository = Path(self.temp.name) / 'current-repository'
        self.deployment = self.current_repository.joinpath(*a.PACKAGE_SUFFIX[:-1])
        self.deployment.mkdir(parents=True)
        (self.current_repository / '.git').mkdir()
        for name, raw in self.sources.items():
            (self.deployment / name).write_bytes(raw)
        for name in ('context_continuation.py', 'context-source-pins.json'):
            (self.deployment / name).write_bytes((ROOT / name).read_bytes())
        self.enterContext(mock.patch.object(a, '__file__', str(self.deployment / 'context_continuation.py')))
        for name, raw in self.sources.items():
            (self.history / name).write_bytes(raw)
        self.enterContext(mock.patch.object(f, 'ROOT', self.history))
        self.enterContext(mock.patch.object(f.r, '__file__', str(self.history / 'recovery_epoch.py')))
        original_write = f.write
        def write(path, value):
            if path.name == 'original-local.json':
                value.update(repository_root=str(self.historical_repository), candidate_root='/synthetic/candidate',
                    scratch_root='/synthetic/scratch', evidence_root='/synthetic/evidence',
                    gpu_stop_path='/synthetic/stop')
                value['runtime'] = {'venv_prefix': '/synthetic/venv', 'executable': {
                    'path': '/synthetic/venv/bin/python', 'resolved_path': '/synthetic/python', 'sha256': '8' * 64},
                    'python_version': [3, 12, 1], 'sdk_root': '/synthetic/sdk', 'home': '/synthetic/home',
                    'requests_ca_bundle': None, 'interop_environment_sha256': {'WSL_INTEROP': '6' * 64}}
                value['windows_bridge']['native_acceptance'] = {'path': '/synthetic/native-proof', 'sha256': '9' * 64}
            return original_write(path, value)
        with mock.patch.object(f, 'write', side_effect=write):
            self.fixture = f.EpochTests(methodName='runTest')
            self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.r = f.r
        self.state = self.fixture.state
        with self.r.RecoveryOwner(self.fixture.c.mapping) as owner:
            _, self.boot, _, context, self.eligibility = self.fixture.finish(owner)
        self.pending = context['covered_pending_claims']
        self.now = self.fixture.now + 110
        self.current = copy.deepcopy(self.fixture.local)
        self.current['repository_root'] = str(self.current_repository)
        self.current_path = Path(self.temp.name) / 'actual-current.json'
        self.config = types.SimpleNamespace(state_root=self.state, document_sha256=None,
                                            repository_root=self.current_repository)
        self.current['runtime']['interop_environment_sha256']['WSL_INTEROP'] = '7' * 64
        self.bind_current()
        def forbidden(*args, **kwargs):
            raise AssertionError('adapter must not execute mutation/runtime/provider callbacks')
        self.callbacks = {'STATE': self.state,
            'configuration_descriptor': lambda: self.current_descriptor,
            'configured': forbidden, 'claim': forbidden, 'journal': forbidden,
            'load_runtime': forbidden, 'provider': forbidden, 'auth': forbidden,
            'recovery_boot_observation': lambda review, challenge: self.boot}

    def bind_current(self):
        self.current_descriptor = f.write(self.current_path, self.current)
        self.config.document_sha256 = self.current_descriptor['sha256']

    def validate(self, **kwargs):
        options = {'now_epoch': self.now}
        options.update(kwargs)
        return a.validate_context(self.callbacks, self.config, self.pending, **options)

    def test_changed_selector_covers_only_original_unknown_without_writes_or_callbacks(self):
        before = self.r._scan(self.state)
        writes = list(self.fixture.c.writes)
        with mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('no subprocess')):
            result = self.validate()
        self.assertEqual(result, {self.fixture.review_value['unknown_session']:
            self.pending[0]['claim']['sha256']})
        self.assertEqual(self.r._scan(self.state), before)
        self.assertEqual(self.fixture.c.writes, writes)
        self.assertEqual(self.config.document_sha256, self.current_descriptor['sha256'])
        self.assertEqual(self.current['runtime']['interop_environment_sha256']['WSL_INTEROP'], '7' * 64)

    def test_exact_original_selector_is_also_allowed(self):
        self.current = copy.deepcopy(self.fixture.local)
        self.current['repository_root'] = str(self.current_repository)
        self.bind_current()
        self.validate()

    def test_separate_checkout_root_is_bound_and_original_sources_stay_unchanged(self):
        self.assertNotEqual(self.current_repository, self.historical_repository)
        self.assertTrue((self.current_repository / '.git').is_dir())
        self.assertTrue((self.historical_repository / '.git').is_dir())
        rows = self.fixture.review_value['recovery_sources']
        before = {name: Path(row['path']).read_bytes() for name, row in rows.items()}
        self.validate()
        self.assertEqual(before, {name: Path(row['path']).read_bytes() for name, row in rows.items()})
        self.assertEqual(self.current['repository_root'], str(self.current_repository))
        self.assertEqual(self.fixture.local['repository_root'], str(self.historical_repository))

    def test_unchanged_repository_root_is_compatible_with_preserved_history(self):
        for name in ('context_continuation.py', 'context-source-pins.json'):
            (self.history / name).write_bytes((ROOT / name).read_bytes())
        self.current['repository_root'] = str(self.historical_repository)
        self.config.repository_root = self.historical_repository
        self.bind_current()
        with mock.patch.object(a, '__file__', str(self.history / 'context_continuation.py')):
            self.validate()

    def test_raw_repository_root_cannot_name_a_different_checkout(self):
        self.current['repository_root'] = str(self.historical_repository)
        self.bind_current()
        observer = mock.Mock(side_effect=AssertionError('not yet'))
        self.callbacks['recovery_boot_observation'] = observer
        with self.assertRaisesRegex(ValueError, 'actual_repository_binding'):
            self.validate()
        observer.assert_not_called()

    def test_loaded_object_repository_root_must_match_actual_document(self):
        self.config.repository_root = self.historical_repository
        observer = mock.Mock(side_effect=AssertionError('not yet'))
        self.callbacks['recovery_boot_observation'] = observer
        with self.assertRaisesRegex(ValueError, 'actual_repository_binding'):
            self.validate()
        observer.assert_not_called()

    def test_adapter_must_occupy_exact_repository_relative_location(self):
        observer = mock.Mock(side_effect=AssertionError('not yet'))
        self.callbacks['recovery_boot_observation'] = observer
        wrong = self.deployment / 'renamed_context_adapter.py'
        with mock.patch.object(a, '__file__', str(wrong)):
            with self.assertRaisesRegex(ValueError, 'adapter_repository_location'):
                self.validate()
        observer.assert_not_called()

    def test_symlink_checkout_alias_is_not_an_independent_root(self):
        alias = Path(self.temp.name) / 'linked-checkout'
        alias.symlink_to(self.current_repository, target_is_directory=True)
        self.current['repository_root'] = str(alias)
        self.config.repository_root = alias
        self.bind_current()
        observer = mock.Mock(side_effect=AssertionError('not yet'))
        self.callbacks['recovery_boot_observation'] = observer
        with mock.patch.object(a, '__file__', str(alias.joinpath(*a.PACKAGE_SUFFIX))):
            with self.assertRaisesRegex(ValueError, 'directory_type'):
                self.validate()
        observer.assert_not_called()

    def test_distinct_root_paths_cannot_alias_the_same_directory_inode(self):
        same = types.SimpleNamespace(st_dev=1, st_ino=2)
        with mock.patch.object(a, '_directory', side_effect=lambda _: contextlib.nullcontext(17)), \
                mock.patch.object(a.os, 'fstat', return_value=same):
            with self.assertRaisesRegex(ValueError, 'repository_inode_alias'):
                a._repository_context(self.current, self.fixture.local, self.config)

    def test_new_checkout_cannot_overlap_frozen_operational_roots(self):
        for field in ('candidate_root', 'scratch_root', 'state_root', 'evidence_root'):
            for path in (self.current_repository, self.current_repository / 'nested',
                         self.current_repository.parent):
                with self.subTest(field=field, path=str(path)):
                    original = copy.deepcopy(self.fixture.local)
                    original[field] = str(path)
                    with self.assertRaisesRegex(ValueError, 'repository_operational_overlap'):
                        a._repository_context(self.current, original, self.config)

    def test_new_checkout_cannot_contain_or_be_contained_by_old_checkout(self):
        original = copy.deepcopy(self.fixture.local)
        original['repository_root'] = str(self.current_repository.parent)
        with self.assertRaisesRegex(ValueError, 'repository_roots_overlap'):
            a._repository_context(self.current, original, self.config)

    def test_multiple_same_boot_contexts_each_require_actual_hash_binding(self):
        for selector in ('8' * 64, '9' * 64, '8' * 64):
            self.current['runtime']['interop_environment_sha256']['WSL_INTEROP'] = selector
            self.bind_current()
            self.validate()
            old = self.config.document_sha256
            self.config.document_sha256 = '0' * 64
            with self.assertRaisesRegex(ValueError, 'actual_configuration_binding'):
                self.validate()
            self.config.document_sha256 = old

    def test_descriptor_is_required_and_not_synthesized_from_config_fields(self):
        del self.callbacks['configuration_descriptor']
        with self.assertRaisesRegex(ValueError, 'actual_configuration_descriptor_required'):
            self.validate()

    def test_callback_descriptor_must_match_actual_config_hash(self):
        self.callbacks['configuration_descriptor'] = lambda: self.fixture.review_value['original_configuration']
        with self.assertRaisesRegex(ValueError, 'actual_configuration_binding'):
            self.validate()

    def test_every_other_configuration_field_is_immutable(self):
        cases = [
            ('username', 'somebody-else'), ('candidate_root', '/changed'),
            ('scratch_root', '/changed'), ('evidence_root', '/changed'), ('gpu_stop_path', '/changed'),
            ('publication_manifest_sha256', '0' * 64), ('extra_key', None),
            ('runtime.home', '/changed'), ('runtime.venv_prefix', '/changed'),
            ('runtime.sdk_root', '/changed'), ('runtime.requests_ca_bundle', {'path': '/changed', 'sha256': '0' * 64}),
            ('runtime.python_version', [3, 12, 2]), ('runtime.executable.sha256', '0' * 64),
            ('runtime.extra_key', False), ('versions.active', 42),
            ('versions.code', True), ('versions.code_predecessor', 20.0),
            ('remote_predecessor.provider_status', 'COMPLETE'),
            ('windows_bridge.configuration.sha256', '0' * 64),
            ('windows_bridge.configuration.wsl_path', '/changed'),
            ('windows_bridge.configuration.native_path', 'C:\\changed'),
            ('windows_bridge.native_acceptance.sha256', '0' * 64)]
        original = copy.deepcopy(self.current)
        for field, value in cases:
            with self.subTest(field=field):
                self.current = copy.deepcopy(original)
                node = self.current
                parts = field.split('.')
                for key in parts[:-1]:
                    node = node[key]
                node[parts[-1]] = value
                self.bind_current()
                with self.assertRaisesRegex(ValueError, 'changed_beyond_interop'):
                    self.validate()

    def test_selector_schema_is_exact(self):
        for value in ({}, {'WSL_INTEROP': None}, {'WSL_INTEROP': 'bad'},
                      {'WSL_INTEROP': '7' * 64, 'WSLENV': '8' * 64}):
            with self.subTest(value=value):
                self.current['runtime']['interop_environment_sha256'] = value
                self.bind_current()
                with self.assertRaisesRegex(ValueError, 'interop_selector_schema'):
                    self.validate()

    def test_missing_and_duplicate_eligibility_fail_closed(self):
        raw = Path(self.eligibility['path']).read_bytes()
        duplicate = self.state / ('recovery-epoch-' + 'a' * 64 + '-eligibility.claim.json')
        duplicate.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'successful_eligibility_required'):
            self.validate()
        duplicate.unlink()
        Path(self.eligibility['path']).unlink()
        with self.assertRaisesRegex(ValueError, 'successful_eligibility_required'):
            self.validate()

    def test_no_or_malformed_seal_is_rejected(self):
        path = next(self.state.glob('recovery-epoch-*-sealed.claim.json'))
        raw = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'seal_required'):
            self.validate()
        path.write_bytes(b'{"format":"bad"}\n')
        with self.assertRaisesRegex(ValueError, 'seal_schema'):
            self.validate()
        path.write_bytes(raw)
        self.validate()

    def test_historical_descriptor_source_mutation_is_rejected_before_compile(self):
        row = self.fixture.review_value['recovery_sources']['bridge_client.py']
        Path(row['path']).write_bytes(b'raise AssertionError("must not execute")\n')
        with mock.patch.object(a, 'compile', create=True, side_effect=AssertionError('must not compile')):
            with self.assertRaisesRegex(ValueError, 'descriptor_changed'):
                self.validate()

    def test_historical_sibling_closure_is_independent_of_descriptor_copies(self):
        review = copy.deepcopy(self.fixture.review_value)
        name = 'operator_common.py'
        sibling = Path(review['recovery_sources']['recovery_epoch.py']['path']).parent / name
        copy_path = Path(self.temp.name) / 'separate-preserved-source.py'
        review['recovery_sources'][name] = f.write(copy_path, sibling.read_bytes())
        a._sources(review, a._pins())
        sibling.write_bytes(b'raise AssertionError("must not execute")\n')
        with self.assertRaisesRegex(ValueError, 'source_not_pinned_f5'):
            a._sources(review, a._pins())

    def test_self_consistent_wrong_source_descriptor_is_not_authority(self):
        review = copy.deepcopy(self.fixture.review_value)
        path = Path(self.temp.name) / 'fake.py'
        review['recovery_sources']['protocol.py'] = f.write(path, b'# substituted protocol\n')
        with self.assertRaisesRegex(ValueError, 'source_not_pinned_f5'):
            a._sources(review, a._pins())

    def test_each_historical_helper_load_remains_pinned_after_bootstrap(self):
        original_type = types.ModuleType
        captured = []
        def module(name):
            result = original_type(name)
            captured.append(result)
            return result
        with mock.patch.object(a.types, 'ModuleType', side_effect=module):
            self.validate()
        historical = captured[0]
        malicious = f.write(Path(self.temp.name) / 'new-unreviewed-helper.py',
            b'raise AssertionError("unreviewed helper executed")\n')
        for role in ('boot', 'protocol'):
            with self.subTest(role=role):
                with self.assertRaisesRegex(ValueError, 'source_not_pinned_f5'):
                    historical._reviewed_module(malicious, role)
        with self.assertRaisesRegex(ValueError, 'helper_role'):
            historical._reviewed_module(malicious, 'runtime')

    def test_manifest_digest_and_git_bytes_are_exact(self):
        pins = a._pins()
        self.assertEqual(set(pins), a.SOURCE_NAMES)
        for name, raw in self.sources.items():
            self.assertEqual(pins[name], {'bytes': len(raw), 'sha256': a._digest(raw)})
        with mock.patch.object(a, 'SOURCE_PINS_SHA256', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'source_manifest_changed'):
                self.validate()

    def test_current_protected_source_changes_fail_before_observation(self):
        original_read = a._read
        self.callbacks['recovery_boot_observation'] = mock.Mock(side_effect=AssertionError('not yet'))
        for name in a.PROTECTED_CURRENT:
            with self.subTest(name=name):
                def read(path):
                    raw = original_read(path)
                    return raw + b'\n' if Path(path) == self.deployment / name else raw
                with mock.patch.object(a, '_read', side_effect=read):
                    with self.assertRaisesRegex(ValueError, 'source_not_pinned_f5'):
                        self.validate()
        self.callbacks['recovery_boot_observation'].assert_not_called()

    def test_uncovered_new_unknown_session_blocks(self):
        self.fixture._session('4' * 64, ['open'], self.current_descriptor,
            self.fixture.review_value['original_native_configuration'], unknown=True)
        with self.assertRaisesRegex(ValueError, 'later_session_unknown'):
            self.validate()

    def test_pending_claims_must_be_exact(self):
        for pending in ([], self.pending * 2, [{'claim': self.pending[0]['claim']} ]):
            with self.subTest(pending=pending):
                with self.assertRaisesRegex(ValueError, 'pending_claims_not_exactly_covered'):
                    a.validate_context(self.callbacks, self.config, pending,
                        current_boot_descriptor=self.boot, now_epoch=self.now)

    def test_new_refresh_unknown_blocks(self):
        name = 'native-auth-refresh-' + '4' * 24
        row = f.write(self.state / (name + '.claim.json'), {'stage': 'intent'})
        f.write(self.state / (name + '-journal.json'), {'stage': 'refresh_unknown', 'claim_sha256': row['sha256']})
        with self.assertRaisesRegex(ValueError, 'later_refresh_unknown'):
            self.validate()

    def test_new_recovery_epoch_blocks(self):
        f.write(self.state / ('recovery-epoch-' + '4' * 64 + '.claim.json'), {'stage': 'prepared'})
        with self.assertRaisesRegex(ValueError, 'outstanding_token'):
            self.validate()

    def test_original_unknown_bytes_remain_sealed(self):
        path = Path(self.pending[0]['journal']['path'])
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'sealed_bytes_changed'):
            self.validate()

    def test_same_boot_freshness_host_and_runtime_remain_required(self):
        good = self.r._document(self.boot)
        mutations = {'host_install_sha256': '0' * 64, 'last_boot_utc': f.utc(self.fixture.now + 51),
                     'runtime_sha256': {'python': '0' * 64, 'base_python': 'b' * 64}}
        for key, value in mutations.items():
            with self.subTest(key=key):
                bad = copy.deepcopy(good)
                bad[key] = value
                row = f.write(Path(self.temp.name) / 'wrong-boot.json', bad)
                with self.assertRaises(ValueError):
                    self.validate(current_boot_descriptor=row)
        with self.assertRaisesRegex(ValueError, 'boot_changed_or_stale'):
            self.validate(now_epoch=self.now + 2000)

    def test_completed_disposition_outlives_consumed_capability_without_replay(self):
        later = self.fixture.now + 2000
        row = f.write(Path(self.temp.name) / 'fresh-later-boot.json',
            self.fixture.boot(later, self.fixture.now + 50))
        before = self.r._scan(self.state)
        self.validate(current_boot_descriptor=row, now_epoch=later)
        self.assertEqual(self.r._scan(self.state), before)

    def test_observer_receives_actual_callback_and_cannot_change_configuration(self):
        old_hash = self.config.document_sha256
        def observer(review, challenge):
            self.assertEqual(challenge, self.fixture.challenge)
            self.assertEqual(self.config.document_sha256, old_hash)
            self.current_path.write_bytes(b'{}\n')
            return self.boot
        self.callbacks['recovery_boot_observation'] = observer
        with self.assertRaisesRegex(ValueError, 'descriptor_changed'):
            self.validate()

    def test_no_fresh_observer_and_no_explicit_descriptor_blocks(self):
        del self.callbacks['recovery_boot_observation']
        with self.assertRaisesRegex(ValueError, 'fresh_boot_observer_required'):
            self.validate()

    def test_symlink_hardlink_and_intermediate_symlink_are_rejected(self):
        path = Path(self.temp.name) / 'linked-current.json'
        for kind in ('symlink', 'hardlink', 'intermediate'):
            with self.subTest(kind=kind):
                if kind == 'symlink':
                    path.symlink_to(self.current_path)
                    row = {**self.current_descriptor, 'path': str(path)}
                elif kind == 'hardlink':
                    os.link(self.current_path, path)
                    row = {**self.current_descriptor, 'path': str(path)}
                else:
                    path.symlink_to(self.current_path.parent, target_is_directory=True)
                    row = {**self.current_descriptor, 'path': str(path / self.current_path.name)}
                self.callbacks['configuration_descriptor'] = lambda: row
                with self.assertRaises(ValueError):
                    self.validate()
                path.unlink()

    def test_strict_json_rejects_duplicate_nonfinite_and_depth(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}',
                    b'{"a":' + b'1' * 25 + b'}', b'{"a":' + b'[' * 34 + b'0' + b']' * 34 + b'}'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    a._json(raw)


if __name__ == '__main__':
    unittest.main()
