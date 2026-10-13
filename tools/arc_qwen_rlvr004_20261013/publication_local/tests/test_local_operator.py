"""Offline local-path/auth-intent tests; fake SDK, no provider or credentials."""
import copy
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]


def load_source(name, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class LocalOperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repository = self.root / 'repo'
        self.repository.mkdir(); (self.repository / '.git').mkdir()
        self.candidate = self.repository / 'candidate'; self.candidate.mkdir()
        self.config = load_source('local_config_test_' + self._testMethodName, HERE / 'config.py')
        self.common = load_source('local_common_test_' + self._testMethodName, HERE / 'operator_common.py')
        self.manifest = {
            'datasets': [{'id': 12504696, 'reference': self.config.DREF, 'expected_predecessor_version': 16, 'expected_version': 17}],
            'notebooks': [
                {'role': 'inactive', 'existing_notebook_id': 138123872, 'existing_notebook_reference': self.config.REF,
                 'expected_predecessor_version': 31, 'expected_version': 32, 'predecessor_source_sha256': 'a' * 64,
                 'dataset_sources': [self.config.DREF + '/17']},
                {'role': 'rlvr004', 'existing_notebook_id': 138123872, 'existing_notebook_reference': self.config.REF,
                 'expected_predecessor_version': 32, 'expected_version': 33, 'dataset_sources': [self.config.DREF + '/17']}],
        }
        self.manifest_path = self.candidate / 'publication-manifest.json'
        self.manifest_raw = encode(self.manifest); self.manifest_path.write_bytes(self.manifest_raw)
        scratch = self.repository / '.irisx/local-operator-fixture'
        self.document = {
            'format': self.config.FORMAT, 'repository_root': str(self.repository), 'candidate_root': str(self.candidate),
            'scratch_root': str(scratch), 'state_root': str(scratch / 'state'), 'evidence_root': str(scratch / 'evidence'),
            'gpu_stop_path': str(scratch / 'SPRINT-GPU-STOP.json'), 'username': 'danielwuu',
            'credential': {'kind': 'windows-local', 'path': self.config.WSL_CREDENTIAL},
            'publication_manifest_sha256': digest(self.manifest_raw),
            'versions': {'code_predecessor': 16, 'code': 17, 'inactive_predecessor': 31, 'inactive': 32, 'active': 33},
            'remote_predecessor': {'code_version': 16, 'notebook_version': 31, 'notebook_source_sha256': 'a' * 64,
                                   'provider_status': 'ERROR', 'snapshot_sha256': 'b' * 64},
        }
        self.config_path = self.root / 'operator-config.json'

    def bind(self, document=None):
        raw = encode(self.document if document is None else document); self.config_path.write_bytes(raw)
        return self.common.configure(self.config_path, digest(raw), self.manifest_path, digest(self.manifest_raw))

    def test_exact_config_binds_ignored_state_without_home_changes(self):
        before = dict(os.environ)
        result = self.bind()
        self.assertEqual(dict(os.environ), before)
        self.assertEqual(self.common.STATE, result.state_root)
        self.assertEqual(self.common.STOP, result.gpu_stop_path)
        self.assertFalse(result.state_root.exists())
        with self.assertRaises(TypeError): result.versions['active'] = 999
        with self.assertRaisesRegex(ValueError, 'already_bound'): self.bind()

    def test_unconfigured_provider_and_claim_denied_without_state(self):
        with self.assertRaisesRegex(ValueError, 'configuration_required'): self.common.Provider()
        with self.assertRaisesRegex(ValueError, 'configuration_required'): self.common.claim('x', {})
        result = self.common.failure(self.common.GuardError('fixture'), 'validate')
        self.assertEqual(result['classification'], 'VERIFICATION_BLOCKED')
        self.assertFalse((self.repository / '.irisx').exists())

    def test_changed_config_source_rejected_before_auth_or_state(self):
        successor = self.root / 'changed-source'; successor.mkdir()
        (successor / 'operator_common.py').write_bytes((HERE / 'operator_common.py').read_bytes())
        (successor / 'config.py').write_bytes(b"raise RuntimeError('unreviewed config executed')\n")
        common = load_source('local_changed_source_fixture', successor / 'operator_common.py')
        raw = encode(self.document); self.config_path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'artifact_hash_or_size'):
            common.configure(self.config_path, digest(raw), self.manifest_path, digest(self.manifest_raw))
        self.assertIsNone(common.CONFIG); self.assertFalse((self.repository / '.irisx').exists())

    def test_manifest_hash_or_version_mismatch_denied(self):
        for mutation in ('hash', 'versions', 'noninteger'):
            common = load_source('local_denied_' + mutation, HERE / 'operator_common.py')
            document = copy.deepcopy(self.document)
            if mutation == 'hash': document['publication_manifest_sha256'] = 'c' * 64
            elif mutation == 'versions': document['versions']['active'] = 34
            else: document['versions']['code'] = True
            raw = encode(document); self.config_path.write_bytes(raw)
            with self.assertRaises(ValueError): common.configure(self.config_path, digest(raw), self.manifest_path, digest(self.manifest_raw))
            self.assertIsNone(common.CONFIG)

    def test_tracked_state_or_credential_payload_overlap_denied(self):
        for mutation in ('state', 'credential', 'scratch'):
            common = load_source('local_bad_path_' + mutation, HERE / 'operator_common.py')
            document = copy.deepcopy(self.document)
            if mutation == 'state': document['state_root'] = str(self.repository / 'tools/state')
            elif mutation == 'credential': document['credential']['path'] = str(self.candidate / 'credentials.json')
            else: document['scratch_root'] = str(self.repository / 'tools/scratch')
            raw = encode(document); self.config_path.write_bytes(raw)
            with self.assertRaises(ValueError): common.configure(self.config_path, digest(raw), self.manifest_path, digest(self.manifest_raw))

    def test_symlink_path_and_spoofed_home_denied(self):
        linked = self.root / 'linked'; linked.symlink_to(self.repository, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.config.secure_path(linked / 'candidate')
        raw = encode(self.document); self.config_path.write_bytes(raw)
        with mock.patch.dict(os.environ, {'HOME': str(self.root / 'spoofed')}):
            with self.assertRaisesRegex(ValueError, 'real_home'):
                self.config.load(self.config_path, digest(raw), self.manifest_path, digest(self.manifest_raw))

    def test_duplicate_json_and_nonfinite_denied(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            self.config_path.write_bytes(raw)
            with self.assertRaises(ValueError): self.config.read_json(self.config_path, digest(raw))

    def acl_result(self, **updates):
        sid = 'S-1-5-21-11-22-33-44'
        proof = {'format': 'irisx/local-windows-credential-acl-v1', 'credential_path': self.config.WINDOWS_CREDENTIAL,
                 'current_user_sid': sid, 'owner_sid': sid, 'allow_sids': [sid, 'S-1-5-18', 'S-1-5-32-544'],
                 'regular_file': True, 'reparse_path': False}
        proof.update(updates)
        return types.SimpleNamespace(returncode=0, stdout=encode(proof), stderr=b'')

    def test_acl_checks_live_current_sid_and_reparse_without_reading_secret(self):
        runner = mock.Mock(return_value=self.acl_result())
        with mock.patch.object(Path, 'is_file', return_value=True):
            proof = self.config.windows_acl_check(self.config.WSL_CREDENTIAL, runner=runner)
        self.assertEqual(proof['owner_sid'], proof['current_user_sid'])
        call = runner.call_args
        self.assertEqual(call.args[0][0], self.config.WSL_POWERSHELL)
        self.assertEqual(call.args[0][-2], '-EncodedCommand')
        self.assertNotIn('-Command', call.args[0])
        script = base64.b64decode(call.args[0][-1], validate=True).decode('utf-16le')
        self.assertIn('Get-Acl -LiteralPath', script)
        self.assertIn('ReparsePoint', script)
        self.assertIn("[System.IO.Path]::Combine($PSHOME, 'Modules\\Microsoft.PowerShell.Security\\Microsoft.PowerShell.Security.psd1')", script)
        self.assertIn("[System.IO.Path]::Combine($PSHOME, 'Modules\\Microsoft.PowerShell.Management\\Microsoft.PowerShell.Management.psd1')", script)
        self.assertIn('[Console]::OutputEncoding', script)
        self.assertNotIn('$env:HOME', script)
        self.assertNotIn('Get-Content', script)
        self.assertEqual(call.kwargs['timeout'], 30)

    def test_acl_extra_allow_wrong_owner_reparse_and_bad_command_denied(self):
        cases = [self.acl_result(allow_sids=['S-1-5-21-11-22-33-44', 'S-1-1-0']), self.acl_result(owner_sid='S-1-5-18'),
                 self.acl_result(reparse_path=True), types.SimpleNamespace(returncode=1, stdout=b'', stderr=b'no secret fixture')]
        with mock.patch.object(Path, 'is_file', return_value=True):
            for case in cases:
                with self.assertRaises(ValueError): self.config.windows_acl_check(self.config.WSL_CREDENTIAL, runner=mock.Mock(return_value=case))

    def test_posix_credentials_require_own_uid_and_mode0600(self):
        credential = self.root / 'synthetic-credentials.json'; credential.write_bytes(b'{}'); credential.chmod(0o600)
        config = types.SimpleNamespace(credential_path=credential, credential_kind='posix-local')
        self.assertEqual(self.config.credential_guard(config)['mode'], '0600')
        credential.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'owner_mode'): self.config.credential_guard(config)

    def fake_creds(self, expires=900, account='danielwuu', failed=False):
        clock = self.clock
        class Credentials:
            loads = []; saves = []; refreshes = 0
            _access_token = 'synthetic-not-a-real-token'
            _access_token_expiration = datetime.fromtimestamp(expires, timezone.utc)
            @classmethod
            def load(cls, *, client, file_path):
                cls.loads.append((client, file_path)); return cls()
            def get_username(self): return account
            def save(self, file_path=None): self.saves.append(file_path)
            def refresh_access_token(self):
                self.__class__.refreshes += 1
                if failed: raise RuntimeError('fixture refresh failed')
                self._access_token_expiration = datetime.fromtimestamp(clock[0] + 3600, timezone.utc)
                self.save()
            def get_access_token(self): return self._access_token
        return Credentials

    def auth_fixture(self, *, expires=900, account='danielwuu', failed=False):
        self.bind(); self.clock = [1000]
        credentials = self.fake_creds(expires=expires, account=account, failed=failed)
        sdk = types.ModuleType('kagglesdk'); sdk.KaggleCredentials = credentials
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict(sys.modules, {'kagglesdk': sdk}).start()
        mock.patch.object(self.common.time, 'time', side_effect=lambda: self.clock[0]).start()
        mock.patch.object(self.common, 'credential_guard', return_value={'fixture_acl': True}).start()
        return credentials

    def test_official_load_and_refresh_save_use_same_explicit_local_path(self):
        credentials = self.auth_fixture()
        token, expiry = self.common.existing_token('fixture-initial-client')
        self.assertEqual(expiry, 4600); self.assertTrue(token)
        expected_path = self.document['credential']['path']
        self.assertEqual(credentials.loads, [('fixture-initial-client', expected_path)])
        self.assertEqual(credentials.saves, [expected_path])
        self.assertEqual(credentials.refreshes, 1)
        for path in self.common.STATE.rglob('*.json'):
            self.assertNotIn(token.encode(), path.read_bytes())
        proof = self.common.obj(next(self.common.STATE.glob('local-auth-refresh-*-journal.json')))
        self.assertEqual(proof['stage'], 'refresh_accepted'); self.assertFalse(proof['new_grant_created'])

    def test_current_token_never_refreshes_or_writes_state(self):
        credentials = self.auth_fixture(expires=9000)
        self.common.existing_token('fixture-client')
        self.assertEqual(credentials.refreshes, 0); self.assertFalse(self.common.STATE.exists())

    def test_wrong_account_denied_before_refresh(self):
        credentials = self.auth_fixture(account='unapproved-fixture')
        with self.assertRaisesRegex(ValueError, 'account_missing'): self.common.existing_token('fixture-client')
        self.assertEqual(credentials.refreshes, 0)

    def test_unknown_refresh_blocks_second_refresh_and_requires_reconciliation(self):
        credentials = self.auth_fixture(failed=True)
        with self.assertRaises(self.common.AuthRefreshUncertain): self.common.existing_token('fixture-client')
        self.assertEqual(credentials.refreshes, 1)
        with self.assertRaisesRegex(ValueError, 'unknown_reconcile_only'): self.common.existing_token('fixture-client')
        self.assertEqual(credentials.refreshes, 1); self.assertEqual(len(credentials.loads), 1)

    def test_later_expiration_creates_distinct_refresh_intent(self):
        credentials = self.auth_fixture()
        self.common.existing_token('fixture-client')
        credentials._access_token_expiration = datetime.fromtimestamp(4600, timezone.utc)
        self.clock[0] = 4400
        self.common.existing_token('fixture-client')
        self.assertEqual(credentials.refreshes, 2)
        self.assertEqual(len(list(self.common.STATE.glob('local-auth-refresh-*.claim.json'))), 2)

    def test_one_publisher_claim_and_flock_are_exclusive(self):
        self.bind()
        self.common.claim('dataset-code-v17', {'fixture': True})
        with self.assertRaises(FileExistsError): self.common.claim('dataset-code-v17', {'fixture': True})
        with self.common.lock():
            with self.assertRaisesRegex(ValueError, 'already_running'):
                with self.common.lock(): pass

    def test_distinct_roles_and_attempt_states_share_one_publisher_lock(self):
        self.bind()
        successor = load_source('local_second_attempt_lock_fixture', HERE / 'operator_common.py')
        document = copy.deepcopy(self.document)
        document['state_root'] = str(Path(document['scratch_root']) / 'attempt-002/state')
        document['evidence_root'] = str(Path(document['scratch_root']) / 'attempt-002/evidence')
        raw = encode(document); self.config_path.write_bytes(raw)
        successor.configure(self.config_path, digest(raw), self.manifest_path, digest(self.manifest_raw))
        with self.common.lock('operator'):
            with self.assertRaisesRegex(ValueError, 'already_running:collector'):
                with self.common.lock('collector'): pass
            with self.assertRaisesRegex(ValueError, 'already_running:collector'):
                with successor.lock('collector'): pass
        with successor.lock('collector'): pass
        self.assertTrue((self.common.CONFIG.scratch_root / 'publisher.lock').is_file())
        self.assertFalse(self.common.STATE.exists()); self.assertFalse(successor.STATE.exists())

    def test_gpu_unavailable_failure_persists_stop_without_quota_api(self):
        self.bind()
        result = self.common.failure(RuntimeError('GPU is unavailable'), 'activate')
        self.assertTrue(result['sprint_stop']); self.assertTrue(self.common.STOP.is_file())
        with self.assertRaisesRegex(ValueError, 'gpu_stop_present'): self.common.no_gpu_stop()
        self.assertFalse(any('quota' in name.lower() for name in vars(self.common.Provider)))

    def test_provider_numeric_versions_required_and_send_reviewed_number(self):
        self.bind()
        modules = {}
        for parent in ('kagglesdk', 'kagglesdk.kernels', 'kagglesdk.kernels.types', 'kagglesdk.datasets', 'kagglesdk.datasets.types'):
            modules[parent] = types.ModuleType(parent)
        kernel_types = types.ModuleType('kagglesdk.kernels.types.kernels_api_service')
        dataset_types = types.ModuleType('kagglesdk.datasets.types.dataset_api_service')
        kernel_types.ApiDownloadKernelOutputRequest = type('OutputRequest', (), {})
        dataset_types.ApiDownloadDatasetRequest = type('DatasetRequest', (), {})
        modules[kernel_types.__name__] = kernel_types; modules[dataset_types.__name__] = dataset_types
        output = mock.Mock(); dataset = mock.Mock()
        provider = self.common.Provider.__new__(self.common.Provider); provider.ensure_read_auth = lambda: None
        provider.client = types.SimpleNamespace(kernels=types.SimpleNamespace(kernels_api_client=types.SimpleNamespace(download_kernel_output=output)),
                                              datasets=types.SimpleNamespace(dataset_api_client=types.SimpleNamespace(download_dataset=dataset)))
        with mock.patch.dict(sys.modules, modules):
            with self.assertRaises(TypeError): provider.output('fixture.json')
            with self.assertRaises(TypeError): provider.dataset_download()
            with self.assertRaises(ValueError): provider.output('fixture.json', version=34)
            with self.assertRaises(ValueError): provider.output('../fixture.json', version=31)
            with self.assertRaises(ValueError): provider.dataset_download(version=18)
            provider.output('fixture.json', version=31); provider.dataset_download('manifest.json', version=17)
        self.assertEqual(output.call_args.args[0].version_number, 31)
        self.assertEqual(dataset.call_args.args[0].dataset_version_number, 17)
        self.assertEqual(dataset.call_args.args[0].file_name, 'manifest.json')

    def test_read_client_renewal_preserves_resource_mutation_counters(self):
        self.bind()
        clients = []
        class Client:
            def __init__(self, api_token=None):
                self.token_present = api_token is not None; self.closed = False
                self.http = types.SimpleNamespace(_prepare_response=lambda kind, response: response)
                clients.append(self)
            def __enter__(self): return self
            def __exit__(self, *args): self.closed = True
            def http_client(self): return self.http
        sdk = types.ModuleType('kagglesdk'); sdk.KaggleClient = Client; sdk.KaggleCredentials = object
        redirect = types.ModuleType('kagglesdk.common.types.http_redirect'); redirect.HttpRedirect = type('HttpRedirect', (), {})
        provider = self.common.Provider.__new__(self.common.Provider)
        provider.client = Client(); old = provider.client; provider.access_expires_epoch = 1
        provider.mutation_counts = {'SaveKernel': 1, 'CreateDatasetVersionById': 1}
        bindings = []
        with mock.patch.dict(sys.modules, {'kagglesdk': sdk, redirect.__name__: redirect}), mock.patch.object(self.common, 'bound_sdk_client', side_effect=lambda client, counts: bindings.append(counts)), mock.patch.object(self.common, 'existing_token', return_value=('synthetic-token', 9999999999)), mock.patch.object(self.common, 'event'):
            provider.ensure_read_auth()
        self.assertTrue(old.closed); self.assertIs(bindings[-1], provider.mutation_counts)
        self.assertEqual(provider.mutation_counts, {'SaveKernel': 1, 'CreateDatasetVersionById': 1})


if __name__ == '__main__':
    unittest.main(verbosity=2)
