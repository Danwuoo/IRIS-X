"""Synthetic-only tests. Never start Windows, import Kaggle or read credentials."""
import ast
import hashlib
import importlib.util
import io
import json
import ntpath
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load('test_preauth_probe_module', ROOT / 'preauth_probe.py')
protocol = load('test_preauth_protocol_module', ROOT / 'protocol.py')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


VERSIONS = {'code_predecessor': 20, 'code': 21, 'inactive_predecessor': 39, 'inactive': 40, 'active': 41}
CLOSURE = {'format': 'irisx/windows-job-closure-v1', 'active_processes': 0,
           'kill_on_close': True, 'breakaway_permitted': False, 'atomic_job_assignment': True}


def prepared():
    return {'protocol': protocol, 'config_sha256': 'a' * 64,
        'document': {'versions': VERSIONS, 'runtime': {
            'executable': {'sha256': 'b' * 64}, 'base_executable': {'sha256': 'c' * 64},
            'pyvenv_cfg_sha256': 'd' * 64}},
        'executable': '/mnt/c/venv/Scripts/python.exe',
        'supervisor': 'C:\\reviewed\\win_supervisor.py',
        'native_config': 'C:\\reviewed\\native-config.json'}


class Writer(io.BytesIO):
    def close(self):
        if not self.closed:
            self.transmitted = self.getvalue()
        super().close()


class FakeTransport:
    def __init__(self, proto, nonce, argv, *, frame='ready', reason='caller_pipe_eof',
                 code=124, closure=None, receipt_nonce=None, raw_receipt=None, trailing=False):
        self.protocol, self.nonce, self.argv = proto, nonce, argv
        self.writer = Writer()
        self.reader = self
        self.buffer = None
        self.frame, self.reason, self.code = frame, reason, code
        self.closure = dict(CLOSURE) if closure is None else closure
        self.receipt_nonce = nonce if receipt_nonce is None else receipt_nonce
        self.raw_receipt, self.trailing = raw_receipt, trailing
        self.released = False
    def read(self, size):
        if self.buffer is None:
            sent = self.writer.getvalue()
            request = self.protocol.FramedIO(io.BytesIO(sent), io.BytesIO(), nonce=self.nonce).receive(kinds={'request'})
            self.request = request
            value = {'sdk_lock_sha256': probe.SOURCE_SHA256['sdk-lock.json'], 'sdk_source_count': 170,
                     'account': 'danielwuu', 'existing_official_store': True}
            frame = self.frame
            if frame == 'wrong_lock':
                frame, value['sdk_lock_sha256'] = 'ready', '0' * 64
            elif frame == 'refresh_request':
                value = {'refresh_id': '1' * 64, 'account': 'danielwuu', 'old_expiration_epoch': 0}
            elif frame == 'response':
                value = {'operation': 'open', 'result': {'authenticated': True}}
            elif frame == 'timeout':
                raise probe.ProbeError('preauth_timeout')
            out = io.BytesIO()
            self.protocol.FramedIO(io.BytesIO(), out, nonce=self.nonce).send(frame, value,
                sequence=request['sequence'], request_sha256=request['request_sha256'])
            self.buffer = io.BytesIO(out.getvalue())
        return self.buffer.read(size)
    def finish(self, timeout):
        if self.trailing:
            raise probe.ProbeError('preauth_unexpected_trailing_frame')
        value = {'format': 'irisx/windows-supervisor-result-v1', 'nonce': self.receipt_nonce,
                 'ok': self.code == 0, 'reason': self.reason, 'closure': self.closure}
        raw = self.raw_receipt if self.raw_receipt is not None else json.dumps(value).encode() + b'\n'
        return self.code, raw
    def release(self):
        self.released = True


class ProtocolProbeTests(unittest.TestCase):
    def exercise(self, **kwargs):
        created = []
        def factory(*args):
            value = FakeTransport(*args, **kwargs)
            created.append(value)
            return value
        result = probe.exercise(prepared(), timeout_seconds=30, transport_factory=factory)
        return result, created[0]
    def test_open_ready_eof_never_ack_and_real_closure_required(self):
        result, transport = self.exercise()
        self.assertTrue(result['ok'])
        self.assertTrue(result['native_process_closure_verified'])
        self.assertFalse(result['ready_ack_sent'])
        self.assertFalse(result['auth_started'])
        self.assertFalse(result['real_operator_contract_tested'])
        self.assertFalse(result['production_execution_admitted'])
        self.assertTrue(result['synthetic_contract_bindings'])
        self.assertTrue(result['synthetic_transport'])
        self.assertTrue(transport.writer.closed)
        self.assertTrue(transport.released)
        sent = io.BytesIO(transport.writer.transmitted)
        request = protocol.FramedIO(sent, io.BytesIO(), nonce=result['nonce']).receive(kinds={'request'})
        self.assertEqual(request['payload']['operation'], 'open')
        self.assertEqual(sent.read(), b'')
        self.assertEqual(request['payload']['arguments']['versions'], VERSIONS)
        self.assertEqual(transport.argv[:4], [prepared()['executable'], '-I', '-B', prepared()['supervisor']])
        self.assertNotIn('ready_ack', transport.writer.transmitted.decode('utf-8', errors='ignore'))
    def test_nonzero_worker_exit_race_is_accepted_only_with_job_zero(self):
        result, unused = self.exercise(reason='worker_exit')
        self.assertTrue(result['ok'])
        self.assertEqual(result['native_closure']['exit_code'], 124)
    def test_wrong_lock_fails_even_with_closure(self):
        result, transport = self.exercise(frame='wrong_lock')
        self.assertFalse(result['ok'])
        self.assertTrue(result['native_process_closure_verified'])
        self.assertTrue(transport.writer.closed)
    def test_refresh_or_authenticated_frame_is_never_acknowledged(self):
        for frame in ('refresh_request', 'response'):
            result, transport = self.exercise(frame=frame)
            self.assertFalse(result['ok'])
            self.assertFalse(result['ready_verified'])
            self.assertNotIn(b'ack', transport.writer.transmitted)
    def test_timeout_still_closes_input_and_checks_native_closure(self):
        result, transport = self.exercise(frame='timeout')
        self.assertFalse(result['ok'])
        self.assertTrue(transport.writer.closed)
        self.assertTrue(result['native_process_closure_verified'])
        self.assertEqual(result['reason'], 'preauth_timeout')
    def test_no_receipt_or_wrong_nonce_never_proves_closure(self):
        for options in ({'raw_receipt': b''}, {'receipt_nonce': '0' * 64}):
            result, unused = self.exercise(**options)
            self.assertFalse(result['ok'])
            self.assertFalse(result['native_process_closure_verified'])
    def test_only_expected_nonzero_closed_paths_accepted(self):
        for options in ({'code': 0}, {'code': 125}, {'reason': 'deadline'},
                        {'reason': 'output_pipe_or_protocol_error'}, {'closure': None, 'raw_receipt': b'SECRET\n'}):
            result, unused = self.exercise(**options)
            self.assertFalse(result['ok'])
            self.assertNotIn('SECRET', json.dumps(result))
    def test_nonzero_active_job_and_bool_zero_are_rejected(self):
        for value in (1, False):
            result, unused = self.exercise(closure={**CLOSURE, 'active_processes': value})
            self.assertFalse(result['ok'])
    def test_trailing_output_fails_closed(self):
        result, unused = self.exercise(trailing=True)
        self.assertFalse(result['ok'])
        self.assertFalse(result['native_process_closure_verified'])
    def test_arbitrary_receipt_error_not_exposed(self):
        result, unused = self.exercise(raw_receipt=b'password=SECRET https://signed.invalid?token=SECRET\n')
        self.assertFalse(result['ok'])
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('signed.invalid', json.dumps(result))
    def test_oversized_receipt_rejected(self):
        result, unused = self.exercise(raw_receipt=b'x' * 4096 + b'\n')
        self.assertFalse(result['ok'])
    def test_invalid_timeout_fails_before_transport(self):
        for value in (0, 121, float('inf'), True):
            with self.assertRaises(probe.ProbeError):
                probe.exercise(prepared(), timeout_seconds=value, transport_factory=lambda *args: self.fail('launched'))


class FileGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.local, self.native = self.root / 'local', self.root / 'native'
        self.local.mkdir()
        self.native.mkdir()
        sources = {}
        for name, value in probe.SOURCE_SHA256.items():
            raw = (ROOT / name).read_bytes()
            self.assertEqual(digest(raw), value)
            (self.local / name).write_bytes(raw)
            (self.native / name).write_bytes(raw)
            sources[name] = {'bytes': len(raw), 'sha256': value}
        self.exe, self.base, self.cfg = self.root / 'python.exe', self.root / 'base.exe', self.root / 'pyvenv.cfg'
        self.exe.write_bytes(b'public synthetic executable')
        self.base.write_bytes(b'public synthetic base executable')
        self.cfg.write_bytes(b'home = synthetic\n')
        self.config = self.root / 'native-config.json'
        self.document = {'format': 'irisx/run008-windows-sdk-runtime-v1', 'account': 'danielwuu',
            'identity': {'sid': 'S-1-5-21-1-2-3-1001', 'profile': 'C:\\Users\\owner'},
            'source_root': 'C:\\reviewed', 'sources': sources, 'versions': VERSIONS,
            'network_environment_sha256': {}, 'requests_ca_bundle': None,
            'runtime': {'executable': {'path': 'C:\\venv\\Scripts\\python.exe', 'sha256': digest(self.exe.read_bytes())},
                'base_executable': {'path': 'C:\\Python312\\python.exe', 'sha256': digest(self.base.read_bytes())},
                'pyvenv_cfg_sha256': digest(self.cfg.read_bytes()), 'venv_prefix': 'C:\\venv',
                'sdk_root': 'C:\\venv\\Lib\\site-packages', 'python_version': [3, 12, 12]}}
        self.write_config()
        mapping = {'C:\\reviewed': self.native, 'C:\\reviewed\\native-config.json': self.config,
            'C:\\venv\\Scripts\\python.exe': self.exe, 'C:\\Python312\\python.exe': self.base,
            'C:\\venv\\pyvenv.cfg': self.cfg}
        self.mapping = patch.object(probe, 'native_to_wsl', side_effect=lambda value: mapping[value])
        self.mapping.start()
    def write_config(self):
        self.config.write_bytes(json.dumps(self.document).encode())
        self.args = SimpleNamespace(native_python=str(self.exe), native_supervisor='C:\\reviewed\\win_supervisor.py',
            native_config='C:\\reviewed\\native-config.json', native_config_sha256=digest(self.config.read_bytes()))
    def tearDown(self):
        self.mapping.stop()
        self.temp.cleanup()
    def test_all_fixed_sources_and_native_runtime_checked_before_launch(self):
        with patch.object(probe, 'Pipes', side_effect=AssertionError('must not launch')):
            result = probe.prepare(self.args, source_root=self.local)
        self.assertEqual(set(result['document']['sources']), set(probe.SOURCE_SHA256))
        self.assertGreaterEqual(len(result['snapshots']), 18)
    def test_changed_native_source_is_not_admitted(self):
        (self.native / 'sdk_worker.py').write_bytes(b'print("unreviewed")')
        with self.assertRaises(probe.ProbeError):
            probe.prepare(self.args, source_root=self.local)
    def test_changed_local_source_is_not_admitted(self):
        (self.local / 'protocol.py').write_bytes(b'print("unreviewed")')
        with self.assertRaises(probe.ProbeError):
            probe.prepare(self.args, source_root=self.local)
    def test_self_declared_config_cannot_replace_hard_pinned_source(self):
        self.document['sources']['sdk_worker.py']['sha256'] = '0' * 64
        self.write_config()
        with self.assertRaises(probe.ProbeError):
            probe.prepare(self.args, source_root=self.local)
    def test_base_executable_and_pyvenv_bytes_required(self):
        for path in (self.base, self.cfg):
            old = path.read_bytes()
            path.write_bytes(b'changed')
            with self.assertRaises(probe.ProbeError):
                probe.prepare(self.args, source_root=self.local)
            path.write_bytes(old)


class StaticGuardTests(unittest.TestCase):
    def test_credentials_rejected_before_read(self):
        for name in ('credentials.json', 'kaggle.json', 'access_token', 'oauth.json'):
            with self.assertRaises(probe.ProbeError):
                probe.bounded_read(Path('/tmp') / name, 1024)
        with self.assertRaises(probe.ProbeError):
            probe.native_to_wsl('C:\\Users\\owner\\.kaggle\\other.json')
    def test_unsafe_windows_mapping_rejected(self):
        for value in ('\\\\server\\share\\a.py', 'C:\\reviewed\\..\\a.py',
                      'C:\\reviewed\\file.py:stream', 'C:/reviewed/a.py', 'C:\\reviewed\\bad.\\a.py'):
            with self.assertRaises(probe.ProbeError):
                probe.native_to_wsl(value)
    def test_no_ack_send_or_sdk_import_path_in_probe(self):
        tree = ast.parse((ROOT / 'preauth_probe.py').read_bytes())
        sends = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == 'send']
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0].args[0].value, 'request')
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any('kaggle' in ast.unparse(node) or 'requests' in ast.unparse(node) for node in imports))


if __name__ == '__main__':
    unittest.main()
