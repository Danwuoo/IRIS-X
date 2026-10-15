"""CPU-only negative tests for the separate, status-only v43 observer.

No credentials, provider requests, Windows jobs, or publication are exercised.
"""
import ast
import copy
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / 'observe.py'
BRIDGE = HERE.parent / 'publication_windows_bridge_20261015'
SPEC = importlib.util.spec_from_file_location('readonly_observer_under_test', SOURCE)
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)
FAKE_SOURCE = 'CPU-only fake notebook source\n'
FAKE_SHA = hashlib.sha256(FAKE_SOURCE.encode()).hexdigest()
GOOD_URL = 'https://api.kaggle.com/v1/kernels.KernelsApiService/GetKernel'


def metadata(**changes):
    value = {'id': observer.KERNEL_ID, 'ref': observer.REFERENCE,
             'currentVersionNumber': 43, 'isPrivate': True, 'enableGpu': True,
             'enableTpu': False, 'enableInternet': False,
             'machineShape': 'NvidiaRtxPro6000', 'title': 'Synthetic CPU fixture'}
    value.update(changes)
    return value


def kernel(meta=None, source=FAKE_SOURCE):
    return {'metadata': copy.deepcopy(metadata() if meta is None else meta),
            'blob': {'source': source}}


def request(url=GOOD_URL, method='POST'):
    return SimpleNamespace(url=url, method=method)


def argv():
    return ['--helper-sha', 'a' * 64, '--bridge-root', '/cpu/bridge',
            '--config', '/cpu/config.json', '--config-sha', 'b' * 64,
            '--accepted-metadata', '/cpu/accepted.json',
            '--accepted-metadata-sha', 'c' * 64, '--output', '/cpu/output']


class FakeProvider:
    def __init__(self, before=None, after=None, status='RUNNING', failure=''):
        self.kernels = iter([kernel() if before is None else before,
                             kernel() if after is None else after])
        self.status_value = {'status': status, 'failureMessage': failure}
        self.calls = []

    def kernel(self):
        self.calls.append('kernel')
        return next(self.kernels)

    def status(self):
        self.calls.append('status')
        return self.status_value


class ReadonlyCapabilityTests(unittest.TestCase):
    def test_writable_credential_guard_rejected_before_runtime_called(self):
        runtime = Mock()
        facade = observer.ReadonlyRuntime(runtime)
        with self.assertRaisesRegex(observer.ObserverError, 'existing_credential_requires_refresh'):
            with facade.credential_guard(allow_write=True):
                self.fail('Writable guard yielded')
        runtime.credential_guard.assert_not_called()
        self.assertIs(facade.refresh_denied_before_write_guard, True)

    def test_credential_guard_mode_requires_real_bool(self):
        for value in (1, 0, None, 'False'):
            with self.subTest(value=value):
                runtime = Mock()
                with self.assertRaisesRegex(observer.ObserverError, 'credential_guard_mode'):
                    with observer.ReadonlyRuntime(runtime).credential_guard(allow_write=value):
                        self.fail('Invalid guard mode yielded')
                runtime.credential_guard.assert_not_called()

    def test_readonly_credential_guard_preserves_original_context(self):
        calls = []
        marker = object()
        @contextmanager
        def guard(*, allow_write):
            calls.append(('enter', allow_write))
            try:
                yield marker
            finally:
                calls.append(('exit', allow_write))
        facade = observer.ReadonlyRuntime(SimpleNamespace(credential_guard=guard, untouched=17))
        with facade.credential_guard() as actual:
            self.assertIs(actual, marker)
        self.assertEqual(calls, [('enter', False), ('exit', False)])
        self.assertEqual(facade.untouched, 17)
        self.assertIs(facade.refresh_denied_before_write_guard, False)

    def test_refresh_intent_and_acceptance_always_refused(self):
        gate = observer.NoRefresh()
        self.assertIsNone(gate.check_ready())
        for method in (gate.intent, gate.accepted):
            with self.assertRaisesRegex(observer.ObserverError, 'refresh_forbidden'):
                method({'synthetic': True})

    def test_only_two_exact_rpc_paths_are_admitted(self):
        expected = frozenset('/v1/kernels.KernelsApiService/' + method
                            for method in ('GetKernel', 'GetKernelSessionStatus'))
        self.assertEqual(observer.RPC_PATHS, expected)
        for path in expected:
            for authority in ('api.kaggle.com', 'api.kaggle.com:443'):
                self.assertIsNone(observer.readonly_request(request('https://' + authority + path)))

    def test_mutation_refresh_download_and_url_variants_denied(self):
        paths = ('SaveKernel', 'CancelKernelSession', 'GetKernelSessionOutput',
                 'ListKernelSessionFiles', 'DownloadKernelOutput', 'RefreshToken')
        denied = ['https://api.kaggle.com/v1/kernels.KernelsApiService/' + name for name in paths]
        denied += ['http://api.kaggle.com' + next(iter(observer.RPC_PATHS)),
                   GOOD_URL.replace('api.kaggle.com', 'evil.example'),
                   GOOD_URL.replace('api.kaggle.com', 'api.kaggle.com.evil.example'),
                   GOOD_URL.replace('api.kaggle.com', 'api.kaggle.com:444'),
                   GOOD_URL.replace('api.kaggle.com', 'user:password@api.kaggle.com'),
                   GOOD_URL + '?download=1', GOOD_URL + '#fragment', GOOD_URL + '/',
                   GOOD_URL + ';different-operation',
                   GOOD_URL.replace('api.kaggle.com', '@api.kaggle.com'),
                   GOOD_URL.replace('/GetKernel', '/%47etKernel'),
                   GOOD_URL.replace('/GetKernel', '/../GetKernel'),
                   GOOD_URL.replace('/v1/', '//v1/'),
                   'https://api.kaggle.com/v1/oauth/token',
                   'https://storage.googleapis.com/synthetic-output.zip']
        for url in denied:
            with self.subTest(url=url), self.assertRaises(observer.ObserverError):
                observer.readonly_request(request(url))
        for method in ('GET', 'PUT', 'DELETE', 'PATCH', 'post'):
            with self.subTest(method=method), self.assertRaises(observer.ObserverError):
                observer.readonly_request(request(method=method))

    def bind(self):
        downstream = Mock(return_value='read-only-response')
        session = SimpleNamespace(send=Mock(side_effect=AssertionError('Unbound send')))
        client = SimpleNamespace(http_client=lambda: SimpleNamespace(_session=session))
        boundary = Mock()
        boundary.bind.side_effect = lambda unused_client, unused_auth: setattr(session, 'send', downstream)
        auth = object()
        observer.bind_readonly(boundary, client, auth, 100)
        boundary.bind.assert_called_once_with(client, auth)
        return session, downstream

    def test_binding_calls_existing_boundary_then_forwards_only_allowed_request(self):
        session, downstream = self.bind()
        req = request()
        with patch.object(observer.time, 'monotonic', return_value=99):
            self.assertEqual(session.send(req, timeout=3), 'read-only-response')
        downstream.assert_called_once_with(req, timeout=3)

    def test_expired_lease_rejects_before_validation_or_transport(self):
        for now in (100, 101):
            session, downstream = self.bind()
            with patch.object(observer.time, 'monotonic', return_value=now), \
                    patch.object(observer, 'readonly_request') as validator:
                with self.assertRaisesRegex(observer.ObserverError, 'observer_deadline'):
                    session.send(request())
            validator.assert_not_called()
            downstream.assert_not_called()

    def test_denied_request_never_reaches_bound_transport(self):
        session, downstream = self.bind()
        with patch.object(observer.time, 'monotonic', return_value=99):
            with self.assertRaisesRegex(observer.ObserverError, 'readonly_rpc_required'):
                session.send(request(GOOD_URL.replace('GetKernel', 'SaveKernel')))
        downstream.assert_not_called()


class SourceBindingTests(unittest.TestCase):
    def test_pinned_bridge_sources_match_actual_repository_bytes(self):
        self.assertEqual(set(observer.PINS), {'win_runtime.py', 'native_config.py', 'win_supervisor.py',
            'sdk_worker.py', 'native_auth.py', 'protocol.py', 'sdk-lock.json'})
        for name, digest in observer.PINS.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((BRIDGE / name).read_bytes()).hexdigest(), digest)

    def test_fixed_accepted_input_hashes_cannot_be_rebound_by_cli(self):
        self.assertEqual(observer.CONFIG_SHA256,
            'ec32867044bd6de4f8cead0cc6d9f73a45419c1a091dbe3cdbdfadaf669fe0f9')
        self.assertEqual(observer.METADATA_SHA256,
            '0a22a9193407c049cbbceeb01f8ea9c5385d2a1855d0f97a6371adfa8a364106')
        with tempfile.TemporaryDirectory() as tmp:
            args, unused_win, unused_config, unused_runtime, fake_sys, unused_raw = self.bootstrap_fixture(tmp)
            args.accepted_metadata_sha = observer.METADATA_SHA256
            for field in ('config_sha', 'accepted_metadata_sha'):
                changed = copy.copy(args)
                setattr(changed, field, '0' * 64)
                with self.subTest(field=field), \
                        patch.object(observer, 'os', SimpleNamespace(name='nt')), \
                        patch.object(observer, 'sys', fake_sys), \
                        patch.object(observer, 'pinned_module') as module_loader:
                    with self.assertRaisesRegex(observer.ObserverError, 'fixed_accepted_input_hashes_required'):
                        observer.bootstrap(changed)
                    module_loader.assert_not_called()

    def test_accepted_metadata_requires_exact_v43_identity_and_settings(self):
        good = metadata()
        self.assertEqual(observer.accepted_metadata(observer.canonical(good)), good)
        with self.assertRaises(observer.ObserverError):
            observer.accepted_metadata(observer.canonical(kernel(good)))
        changes = [('id', 138123873), ('id', str(observer.KERNEL_ID)), ('ref', 'other/kernel'),
                   ('currentVersionNumber', 42), ('currentVersionNumber', 43.0),
                   ('isPrivate', False), ('isPrivate', 1), ('enableGpu', False),
                   ('enableTpu', True), ('enableInternet', True), ('machineShape', 'other')]
        for key, value in changes:
            with self.subTest(key=key, value=value), self.assertRaises(observer.ObserverError):
                observer.accepted_metadata(observer.canonical(metadata(**{key: value})))

    def test_duplicate_json_and_nonfinite_values_rejected(self):
        for raw in (b'{"id":1,"id":2}', b'{"value":NaN}', b'{"value":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(observer.ObserverError):
                observer.strict_json(raw)

    def test_read_pinned_rejects_changed_bytes_and_invalid_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.json'
            raw = b'{"synthetic":true}\n'
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            self.assertEqual(observer.read_pinned(path, digest), raw)
            for bad in ('0' * 64, 'A' * 64, '', None):
                with self.subTest(digest=bad), self.assertRaises(observer.ObserverError):
                    observer.read_pinned(path, bad)
            path.write_bytes(raw + b' ')
            with self.assertRaisesRegex(observer.ObserverError, 'source_hash_mismatch'):
                observer.read_pinned(path, digest)

    def bootstrap_fixture(self, directory):
        raw = observer.canonical(metadata(title='Externally bound metadata'))
        raw += b' ' * (923 - len(raw))
        accepted = Path(directory) / 'accepted.json'
        accepted.write_bytes(raw)
        args = SimpleNamespace(helper_sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            bridge_root=str(BRIDGE), config=str(Path(directory) / 'config.json'), config_sha=observer.CONFIG_SHA256,
            accepted_metadata=str(accepted), accepted_metadata_sha=hashlib.sha256(raw).hexdigest())
        runtime = SimpleNamespace(recovery=None, source_root=str(BRIDGE), versions={
            'code_predecessor': 21, 'code': 22, 'inactive_predecessor': 41, 'inactive': 42, 'active': 43})
        win = SimpleNamespace(read_source=Mock(side_effect=lambda path, cap: Path(path).read_bytes()))
        config = SimpleNamespace(load_runtime=Mock(return_value=runtime))
        fake_sys = SimpleNamespace(platform='win32', flags=SimpleNamespace(
            isolated=1, dont_write_bytecode=1, ignore_environment=1))
        return args, win, config, runtime, fake_sys, raw

    def test_bootstrap_metadata_is_bound_to_external_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, win, config, runtime, fake_sys, raw = self.bootstrap_fixture(tmp)
            with patch.object(observer, 'os', SimpleNamespace(name='nt')), \
                    patch.object(observer, 'sys', fake_sys), \
                    patch.object(observer, 'METADATA_SHA256', args.accepted_metadata_sha), \
                    patch.object(observer, 'pinned_module', side_effect=[win, config]):
                unused_root, unused_win, actual_runtime, expected = observer.bootstrap(args)
            self.assertIs(actual_runtime, runtime)
            self.assertEqual(expected, observer.accepted_metadata(raw))
            config.load_runtime.assert_called_once_with(args.config, args.config_sha)
            reads = [call for call in win.read_source.call_args_list
                     if call.args[0] == args.accepted_metadata]
            self.assertEqual(len(reads), 1)
            args.accepted_metadata_sha = '0' * 64
            with patch.object(observer, 'os', SimpleNamespace(name='nt')), \
                    patch.object(observer, 'sys', fake_sys), \
                    patch.object(observer, 'METADATA_SHA256', args.accepted_metadata_sha), \
                    patch.object(observer, 'pinned_module', side_effect=[win, config]):
                with self.assertRaises(observer.ObserverError):
                    observer.bootstrap(args)

    def test_bootstrap_never_parses_different_bytes_than_external_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, win, config, unused_runtime, fake_sys, raw = self.bootstrap_fixture(tmp)
            unbound = observer.canonical(metadata(title='Unbound first read'))
            unbound += b' ' * (923 - len(unbound))
            win.read_source.side_effect = [SOURCE.read_bytes(), unbound, raw]
            with patch.object(observer, 'os', SimpleNamespace(name='nt')), \
                    patch.object(observer, 'sys', fake_sys), \
                    patch.object(observer, 'METADATA_SHA256', args.accepted_metadata_sha), \
                    patch.object(observer, 'pinned_module', side_effect=[win, config]):
                with self.assertRaisesRegex(observer.ObserverError, 'accepted_metadata_hash'):
                    observer.bootstrap(args)
            self.assertEqual(win.read_source.call_count, 2)


class ObservationTests(unittest.TestCase):
    def observe(self, provider, times=None):
        if times is None:
            times = [observer.CLOCK['original_epoch'] + 1, observer.CLOCK['original_epoch'] + 2]
        with patch.object(observer, 'SOURCE_SHA256', FAKE_SHA):
            return observer.observe(provider, metadata(), wall=Mock(side_effect=times))

    def test_exact_kernel_status_kernel_bracket_and_no_false_closure(self):
        for status in sorted(observer.STATUS):
            with self.subTest(status=status):
                provider = FakeProvider(status=status)
                result = self.observe(provider)
                self.assertEqual(provider.calls, ['kernel', 'status', 'kernel'])
                self.assertIs(result['terminal'], status in observer.TERMINAL)
                self.assertIs(result['source_and_metadata_bracket_verified'], True)
                self.assertEqual(result['numeric_version'], 43)
                self.assertEqual(result['code_version'], 22)
                self.assertEqual(result['saved_source_sha256'], FAKE_SHA)
                self.assertEqual(result['metadata_sha256'], observer.sha(observer.canonical(metadata())))
                self.assertEqual(result['clock'], observer.CLOCK)
                for flag in ('remote_process_closure_verified', 'billing_verified',
                             'scientific_success_verified', 'old_native_session_closure_verified'):
                    self.assertIs(result[flag], False)

    def test_source_or_metadata_drift_at_either_end_is_rejected(self):
        for position in ('before', 'after'):
            for changed in (kernel(source=FAKE_SOURCE + 'changed'), kernel(metadata(title='changed'))):
                with self.subTest(position=position, changed=changed):
                    provider = FakeProvider(**{position: changed})
                    with self.assertRaises(observer.ObserverError):
                        self.observe(provider)
                    self.assertEqual(provider.calls, ['kernel'] if position == 'before'
                                     else ['kernel', 'status', 'kernel'])

    def test_status_schema_unknown_fields_and_unbounded_error_text_rejected(self):
        invalid = [{'status': 'SUCCESS', 'failureMessage': ''},
                   {'status': None, 'failureMessage': ''},
                   {'status': 'ERROR', 'failureMessage': 'arbitrary private provider detail'},
                   {'status': 'ERROR'},
                   {'status': 'ERROR', 'failureMessage': '', 'closure': True}]
        for value in invalid:
            with self.subTest(value=value):
                provider = FakeProvider()
                provider.status_value = value
                with self.assertRaises(observer.ObserverError):
                    self.observe(provider)
                self.assertEqual(provider.calls, ['kernel', 'status'])

    def test_original_clock_cannot_reset_or_expire(self):
        epoch, deadline = observer.CLOCK['original_epoch'], observer.CLOCK['global_deadline']
        for times in ([epoch - 1, epoch + 1], [epoch + 2, epoch + 1],
                      [epoch + 1, deadline], [epoch + 1, float('nan')]):
            with self.subTest(times=times), self.assertRaisesRegex(observer.ObserverError, 'original_clock_bound'):
                self.observe(FakeProvider(), times)


class OutputIsolationTests(unittest.TestCase):
    def test_fresh_output_is_created_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            native = base / 'native'
            native.mkdir()
            output = base / 'new-observation'
            self.assertEqual(observer.observation_output(output, native), output)
            self.assertTrue(output.is_dir())
            self.assertEqual(list(output.iterdir()), [])
            self.assertEqual(list(native.iterdir()), [])

    def test_state_names_and_state_ancestors_are_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ('STATE', 'state-run008', 'StateRecovery'):
                with self.subTest(name=name):
                    output = base / name
                    with self.assertRaisesRegex(observer.ObserverError, 'state_or_source_output_forbidden'):
                        observer.observation_output(output, base / 'native')
                    self.assertFalse(output.exists())
                    output.mkdir()
                    child = output / 'new-observation'
                    with self.assertRaisesRegex(observer.ObserverError, 'state_or_source_output_forbidden'):
                        observer.observation_output(child, base / 'native')
                    self.assertFalse(child.exists())

    def test_native_source_root_and_descendants_are_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            native = Path(tmp) / 'native'
            native.mkdir()
            for output in (native, native / 'new-observation'):
                with self.subTest(output=output), \
                        self.assertRaisesRegex(observer.ObserverError, 'state_or_source_output_forbidden'):
                    observer.observation_output(output, native)
            self.assertEqual(list(native.iterdir()), [])

    def test_existing_directory_is_not_reused_or_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'existing'
            output.mkdir()
            sentinel = output / 'sentinel.txt'
            sentinel.write_bytes(b'preserve this existing observation')
            with self.assertRaises(FileExistsError):
                observer.observation_output(output, Path(tmp) / 'native')
            self.assertEqual(sentinel.read_bytes(), b'preserve this existing observation')

    def test_symlink_ancestry_is_denied_before_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / 'target'
            target.mkdir()
            linked = base / 'linked'
            linked.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(observer.ObserverError, 'linked_path_forbidden'):
                observer.observation_output(linked / 'new-observation', base / 'native')
            self.assertEqual(list(target.iterdir()), [])


class EntrypointTests(unittest.TestCase):
    def test_argument_bindings_valid_and_duplicate_flags_rejected(self):
        parsed = observer.arguments(argv())
        self.assertFalse(parsed.worker)
        for extra in (['--helper-sha', 'd' * 64], ['--helper-sha=' + 'd' * 64]):
            with self.subTest(extra=extra), self.assertRaises(observer.ObserverError):
                observer.arguments(argv() + extra)

    def test_argument_shas_and_worker_binding_fail_closed(self):
        for option in ('--helper-sha', '--config-sha', '--accepted-metadata-sha'):
            args = argv()
            args[args.index(option) + 1] = 'A' * 64
            with self.subTest(option=option), self.assertRaises(observer.ObserverError):
                observer.arguments(args)
        for extras in (['--nonce', 'd' * 64], ['--worker'],
                       ['--worker', '--nonce', 'd' * 64, '--request-sha', 'e' * 64,
                        '--deadline-epoch', 'nan']):
            with self.subTest(extras=extras), self.assertRaises(observer.ObserverError):
                observer.arguments(argv() + extras)
        worker = observer.arguments(argv() + ['--worker', '--nonce', 'd' * 64,
            '--request-sha', 'e' * 64, '--deadline-epoch', str(observer.CLOCK['original_epoch'] + 10)])
        self.assertTrue(worker.worker)

    def test_import_is_inert_and_emits_nothing(self):
        code = compile(SOURCE.read_bytes(), str(SOURCE), 'exec')
        output = io.StringIO()
        with patch('socket.socket', side_effect=AssertionError('Network during import')), \
                patch('subprocess.Popen', side_effect=AssertionError('Process during import')), \
                patch('builtins.open', side_effect=AssertionError('File IO during import')), \
                patch('pathlib.Path.open', side_effect=AssertionError('File IO during import')), \
                patch('os._exit', side_effect=AssertionError('Exit during import')), \
                redirect_stdout(output), redirect_stderr(output):
            namespace = {'__name__': 'inert_observer_test', '__file__': str(SOURCE)}
            exec(code, namespace)
        self.assertEqual(output.getvalue(), '')

    def test_safety_gates_are_not_optimization_sensitive_asserts(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        self.assertFalse(any(isinstance(node, ast.Assert) for node in ast.walk(tree)))
        with self.assertRaises(observer.ObserverError):
            observer.need(False, 'always_enforced')


if __name__ == '__main__':
    unittest.main()
