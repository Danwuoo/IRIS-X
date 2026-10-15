"""Synthetic offline f5 history only; no native/provider/restart evidence."""
import contextlib
import copy
import importlib.util
import json
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
p = load('test_context_publication_fixture', ROOT / 'tests/test_publication_state.py')


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
            repository_root=self.current_repository, scratch_root=Path(self.current['scratch_root']))
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

    def bind_publication(self):
        """A current-manifest view only; this fixture is not release admission."""
        (self.deployment / 'publication_state.py').write_bytes((ROOT / 'publication_state.py').read_bytes())
        self.current['candidate_root'] = str(Path(self.temp.name) / 'current-candidate')
        self.current['versions'] = p.versions()
        self.manifest_descriptor = f.write(Path(self.current['candidate_root']) / 'publication-manifest.json',
            p.manifest(configured_versions=self.current['versions']))
        self.current['publication_manifest_sha256'] = self.manifest_descriptor['sha256']
        self.bind_current()
        self.callbacks['publication_manifest_descriptor'] = lambda: self.manifest_descriptor

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

    def test_current_release_fields_do_not_have_to_equal_historical_configuration(self):
        # These fields are admitted by the unchanged current config/contract
        # gates. The recovery adapter only interprets the historical disposition.
        cases = [
            ('candidate_root', '/changed'), ('evidence_root', '/changed'), ('gpu_stop_path', '/changed'),
            ('publication_manifest_sha256', '0' * 64),
            ('runtime.venv_prefix', '/changed'),
            ('runtime.sdk_root', '/changed'), ('runtime.requests_ca_bundle', {'path': '/changed', 'sha256': '0' * 64}),
            ('runtime.python_version', [3, 12, 2]), ('runtime.executable.sha256', '0' * 64),
            ('versions', {'code_predecessor': 21, 'code': 22, 'inactive_predecessor': 41,
                          'inactive': 42, 'active': 43}),
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
                self.validate()

    def test_scratch_root_is_shared_with_history_and_actual_loaded_configuration(self):
        for document, loaded in (('/changed', '/changed'), ('/changed', '/synthetic/scratch'),
                                 ('/synthetic/scratch', '/changed')):
            with self.subTest(document=document, loaded=loaded):
                self.current['scratch_root'] = document
                self.config.scratch_root = Path(loaded)
                self.bind_current()
                observer = mock.Mock(side_effect=AssertionError('not yet'))
                self.callbacks['recovery_boot_observation'] = observer
                with self.assertRaisesRegex(ValueError, 'shared_scratch_root'):
                    self.validate()
                observer.assert_not_called()

    def test_state_root_is_bound_to_actual_configuration_and_history(self):
        self.current['state_root'] = '/changed'
        self.bind_current()
        with self.assertRaisesRegex(ValueError, 'actual_state_root'):
            self.validate()
        self.current['state_root'] = str(self.state)
        self.bind_current()
        self.config.state_root = Path('/changed')
        with self.assertRaisesRegex(ValueError, 'actual_configuration_binding'):
            self.validate()
        original = copy.deepcopy(self.fixture.local)
        original['state_root'] = '/changed'
        self.config.state_root = self.state
        with self.assertRaisesRegex(ValueError, 'shared_state_root'):
            a._shared_context(self.current, original, self.config)

    def test_candidate_successor_needs_no_material_lineage_callback_or_module(self):
        self.bind_publication()
        self.callbacks['material_lineage_descriptor'] = mock.Mock(side_effect=AssertionError('no lineage receipt'))
        self.assertFalse((self.deployment / 'material_lineage.py').exists())
        before = self.r._scan(self.state)
        result = self.validate()
        self.assertEqual(result, {self.fixture.review_value['unknown_session']:
            self.pending[0]['claim']['sha256']})
        self.callbacks['material_lineage_descriptor'].assert_not_called()
        self.assertEqual(self.r._scan(self.state), before)

    def test_current_publication_manifest_must_match_actual_configuration(self):
        self.bind_publication()
        self.current['publication_manifest_sha256'] = '0' * 64
        self.bind_current()
        with self.assertRaisesRegex(ValueError, 'actual_publication_manifest'):
            self.validate()

    def test_current_publication_view_keeps_every_new_unknown_blocking(self):
        self.bind_publication()
        self.fixture._session('4' * 64, ['open'], self.current_descriptor,
            self.fixture.review_value['original_native_configuration'], unknown=True)
        with self.assertRaisesRegex(ValueError, 'later_session_unknown'):
            self.validate()

    def test_current_publication_view_keeps_new_refresh_unknown_blocking(self):
        self.bind_publication()
        name = 'native-auth-refresh-' + '4' * 24
        row = f.write(self.state / (name + '.claim.json'), {'stage': 'intent'})
        f.write(self.state / (name + '-journal.json'), {'stage': 'refresh_unknown', 'claim_sha256': row['sha256']})
        with self.assertRaisesRegex(ValueError, 'later_refresh_unknown'):
            self.validate()

    def test_current_publication_view_keeps_pending_claims_exact(self):
        self.bind_publication()
        with self.assertRaisesRegex(ValueError, 'pending_claims_not_exactly_covered'):
            a.validate_context(self.callbacks, self.config, self.pending * 2, now_epoch=self.now)

    def test_current_publication_view_rejects_unrecognized_root_names(self):
        self.bind_publication()
        f.write(self.state / 'unreviewed-extra.json', {'inert': True})
        with self.assertRaisesRegex(ValueError, 'unexpected_root'):
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

    def test_current_source_successor_is_not_loaded_as_historical_validator(self):
        for name in a.SOURCE_NAMES:
            (self.deployment / name).write_bytes(b'raise AssertionError("current release is separately admitted")\n')
        self.validate()
        self.assertEqual({name: (self.history / name).read_bytes() for name in a.SOURCE_NAMES}, self.sources)

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

    def test_observer_cannot_change_loaded_scratch_namespace(self):
        def observer(review, challenge):
            self.config.scratch_root = Path('/changed')
            return self.boot
        self.callbacks['recovery_boot_observation'] = observer
        with self.assertRaisesRegex(ValueError, 'shared_scratch_root'):
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


class PreworkerContextTests(unittest.TestCase):
    """Actual adapter + frozen f5 validator, with isolated synthetic bytes only."""
    setUpClass = classmethod(ContextTests.setUpClass.__func__)
    bind_current = ContextTests.bind_current
    validate = ContextTests.validate

    def setUp(self):
        self.pre = load('context_preworker_fixture', ROOT / 'tests/test_preworker_disposition.py')
        pins = json.loads((ROOT / 'context-source-pins.json').read_bytes())['sources']
        original_after = f.EpochTests.after
        def full_normal_template(fixture, preparation):
            after, restart, binding_row = original_after(fixture, preparation)
            # A real f5 reconciliation had a fully shaped normal f5 native
            # template, distinct from the original failed 01ca configuration.
            # Build that template before reservation/sealing, never rewrite it.
            fixture.native = self.pre.synthetic_native_configuration(pins, fixture.versions)
            native = f.write(fixture.root / 'normal-f5.json', fixture.native)
            fixture.local = copy.deepcopy(fixture.local)
            fixture.local['windows_bridge']['configuration'] = {
                'wsl_path': native['path'], 'native_path': r'C:\Synthetic\normal-f5.json',
                'sha256': native['sha256']}
            normal = f.write(fixture.root / 'normal-local-f5.json', fixture.local)
            binding = json.loads(Path(binding_row['path']).read_bytes())
            binding.update(native_configuration_template=native,
                           local_configuration_template=normal)
            self.native_template = native
            return after, restart, f.write(Path(binding_row['path']), binding)
        with mock.patch.object(f.EpochTests, 'after', full_normal_template):
            ContextTests.setUp(self)
        (self.deployment / 'preworker_disposition.py').write_bytes((ROOT / 'preworker_disposition.py').read_bytes())
        self.history_before = self.r._scan(self.state)
        self.lease_files = self.pre.synthetic_lease_files(self.native_template['sha256'],
            self.fixture.versions, configuration_sha256=self.current_descriptor['sha256'],
            publication_manifest_sha256=self.current['publication_manifest_sha256'],
            epoch=self.fixture.now + 111)
        for name, raw in self.lease_files.items():
            (self.state / name).write_bytes(raw)
        claim_name = next(name for name in self.lease_files if name.endswith('.claim.json'))
        journal_name = next(name for name in self.lease_files if name.endswith('-journal.json'))
        def descriptor(name):
            raw = self.lease_files[name]
            return {'path': str(self.state / name), 'bytes': len(raw), 'sha256': self.r.sha(raw)}
        self.pair = {'claim': descriptor(claim_name), 'journal': descriptor(journal_name)}
        self.pending = [*self.pending, copy.deepcopy(self.pair)]
        self.lease_session = claim_name.removesuffix('.claim.json')
        self.now = self.fixture.now + 112

    def test_existing_durable_diagnostics_cover_only_preworker_without_rewriting_unknown(self):
        before = self.r._scan(self.state)
        with mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('no process')):
            result = self.validate()
        self.assertEqual(set(result), {self.fixture.review_value['unknown_session'], self.lease_session})
        self.assertEqual(result[self.lease_session], self.pair['claim']['sha256'])
        self.assertEqual(self.r._scan(self.state), before)
        self.assertTrue(all(before[name] == raw for name, raw in self.history_before.items()))
        for name in (self.lease_session, self.fixture.review_value['unknown_session']):
            row = json.loads((self.state / (name + '-journal.json')).read_bytes())
            self.assertEqual(row['stage'], 'UNKNOWN')
            self.assertIs(row['native_process_closure_verified'], False)

    def test_exact_pending_pair_required_not_only_claim_hash(self):
        original = copy.deepcopy(self.pending)
        for change in ('missing', 'duplicate', 'wrong_journal', 'wrong_path'):
            with self.subTest(change=change):
                self.pending = copy.deepcopy(original)
                if change == 'missing':
                    self.pending.pop()
                elif change == 'duplicate':
                    self.pending.append(copy.deepcopy(self.pair))
                elif change == 'wrong_journal':
                    self.pending[-1]['journal']['sha256'] = '0' * 64
                else:
                    self.pending[-1]['claim']['path'] += '.alias'
                with self.assertRaisesRegex(ValueError, 'context_preworker_pending_pair'):
                    self.validate()

    def test_other_unknown_session_still_rejected(self):
        self.fixture._session('d' * 64, ['open'], self.current_descriptor,
                              self.native_template, unknown=True)
        with self.assertRaises(ValueError):
            self.validate()

    def test_missing_event_and_contradictory_rpc_fail_closed(self):
        name = next(name for name in self.lease_files if name.startswith('events/'))
        path = self.state / name
        raw = path.read_bytes()
        path.unlink()
        with self.assertRaises(ValueError):
            self.validate()
        path.write_bytes(raw)
        path = self.state / 'events' / ('999-native-auth-refresh-' + self.lease_session + '-1234abcd.json')
        f.write(path, {'nonce': self.lease_session.removeprefix('native-bridge-'),
                       'stage': 'refresh_intent'})
        with self.assertRaises(ValueError):
            self.validate()

    def test_event_mutation_during_boot_observation_is_rejected(self):
        path = self.state / next(name for name in self.lease_files if name.startswith('events/'))
        def observer(review, challenge):
            path.write_bytes(path.read_bytes() + b' ')
            return self.boot
        self.callbacks['recovery_boot_observation'] = observer
        with self.assertRaisesRegex(ValueError, 'context_preworker_evidence_changed'):
            self.validate()

    def test_helper_source_replacement_rejected_before_observer(self):
        path = self.deployment / 'preworker_disposition.py'
        path.write_bytes(path.read_bytes() + b'\n# changed\n')
        observer = mock.Mock(side_effect=AssertionError('not reached'))
        self.callbacks['recovery_boot_observation'] = observer
        with self.assertRaisesRegex(ValueError, 'context_current_helper_source_pin'):
            self.validate()
        observer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
