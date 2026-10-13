"""Offline exact transport/collector successor review and admission regressions."""
import ast
import base64
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import py_compile
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
ORIGINAL = HERE.parent / 'publication'
FROZEN = {
    'operator_common.py': 'b7642b808fd7e0ab4055958aac04fce15abd7953ef8c67f89e136e211bd8ad76',
    'rl_transport.py': '94822904a7032f55886f886c920000869432cb18222af04fb0f96006325b02a3',
    'rl_collect.py': '9a386e1697279067011bc5d832665396abc22c797991db479d3ad34f022f8446',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def load(name, path):
    module = types.ModuleType(name); module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


def functions(path):
    return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(path.read_bytes()).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


@unittest.skipUnless(os.name == 'posix', 'the publication operator requires local WSL/POSIX')
class LocalTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.repository = self.root / 'repo'; self.repository.mkdir()
        (self.repository / '.git').mkdir(); self.candidate = self.repository / 'candidate'; self.candidate.mkdir()
        self.transport = load('local_transport_fixture_' + self._testMethodName, HERE / 'rl_transport.py')
        self.manifest = {
            'datasets': [{'id': 12504696, 'reference': self.transport.DREF, 'expected_predecessor_version': 16, 'expected_version': 17}],
            'notebooks': [
                {'role': 'inactive', 'existing_notebook_id': 138123872, 'existing_notebook_reference': self.transport.REF,
                 'expected_predecessor_version': 31, 'expected_version': 32, 'predecessor_source_sha256': 'a' * 64,
                 'dataset_sources': [self.transport.DREF + '/17'], 'sha256': 'c' * 64},
                {'role': 'rlvr004', 'existing_notebook_id': 138123872, 'existing_notebook_reference': self.transport.REF,
                 'expected_predecessor_version': 32, 'expected_version': 33, 'dataset_sources': [self.transport.DREF + '/17'], 'sha256': 'd' * 64}],
        }
        self.manifest_path = self.candidate / 'publication-manifest.json'; self.manifest_path.write_bytes(encoded(self.manifest))
        scratch = self.repository / '.irisx/local-transport-fixture'
        self.config_document = {
            'format': 'irisx/rlvr-local-operator-config-v1', 'repository_root': str(self.repository), 'candidate_root': str(self.candidate),
            'scratch_root': str(scratch), 'state_root': str(scratch / 'state'), 'evidence_root': str(scratch / 'run-evidence'),
            'gpu_stop_path': str(scratch / 'STOP.json'), 'username': 'danielwuu',
            'credential': {'kind': 'windows-local', 'path': '/mnt/c/Users/wurre/.kaggle/credentials.json'},
            'publication_manifest_sha256': sha(self.manifest_path),
            'versions': {'code_predecessor': 16, 'code': 17, 'inactive_predecessor': 31, 'inactive': 32, 'active': 33},
            'remote_predecessor': {'code_version': 16, 'notebook_version': 31, 'notebook_source_sha256': 'a' * 64,
                                   'provider_status': 'ERROR', 'snapshot_sha256': 'b' * 64},
        }
        self.config_path = self.root / 'local-config.json'; self.config_path.write_bytes(encoded(self.config_document))
        self.material_path = self.root / 'material.json'
        self.material_path.write_bytes(encoded({'status': 'APPROVED', 'scope': {'publication_manifest': {'sha256': sha(self.manifest_path)}},
                                                'approved_notebooks': [{'role': row['role'], 'sha256': row['sha256']} for row in self.manifest['notebooks']]}))
        self.review_path = self.root / 'synthetic-review.json'
        self.review = {'status': 'PASS', 'publication_manifest_sha256': sha(self.manifest_path), 'material_approval_sha256': sha(self.material_path),
                       'local_config_sha256': sha(self.config_path), 'operator_files': {'rl_transport.py': sha(HERE / 'rl_transport.py'), 'operator_common.py': sha(HERE / 'operator_common.py')},
                       'provider_execution_admitted': False, 'synthetic_test_only': True, 'allowed_actions': []}
        self.review_path.write_bytes(encoded(self.review))

    def args(self, action='validate'):
        return types.SimpleNamespace(action=action, manifest=str(self.manifest_path), manifest_sha=sha(self.manifest_path),
                                     material=str(self.material_path), material_sha=sha(self.material_path), review=str(self.review_path), review_sha=sha(self.review_path),
                                     local_config=str(self.config_path), local_config_sha=sha(self.config_path), monitor_review=None, monitor_sha=None,
                                     mount=None, mount_sha=None, audit=None, audit_sha=None, consumer_root=None)

    def cli(self, args):
        result = ['fixture-operator', args.action]
        for name in ('manifest', 'manifest_sha', 'material', 'material_sha', 'review', 'review_sha', 'local_config', 'local_config_sha'):
            result.extend(['--' + name.replace('_', '-'), getattr(args, name)])
        return result

    def test_parser_requires_both_local_config_path_and_hash(self):
        full = self.cli(self.args())[1:]
        result = self.transport.parser().parse_args(full)
        self.assertEqual(result.local_config, str(self.config_path)); self.assertEqual(result.local_config_sha, sha(self.config_path))
        for option in ('--local-config', '--local-config-sha'):
            partial = list(full); index = partial.index(option); del partial[index:index + 2]
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                self.transport.parser().parse_args(partial)
            self.assertEqual(error.exception.code, 2)

    def test_no_config_fails_before_provider_or_authentication(self):
        argv = self.cli(self.args('readiness')); index = argv.index('--local-config'); del argv[index:index + 2]
        with mock.patch.object(sys, 'argv', argv), mock.patch.object(self.transport, 'Provider') as provider, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit): self.transport.main()
        provider.assert_not_called(); self.assertIsNone(self.transport.CONFIG)

    def test_invalid_config_rejected_before_source_contract_or_provider(self):
        self.config_path.write_bytes(encoded({'format': 'unapproved-fixture'})); args = self.args('readiness')
        with mock.patch.object(sys, 'argv', self.cli(args)), mock.patch.object(self.transport, 'Provider') as provider, mock.patch.object(self.transport, 'contract') as contract, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.transport.main(), 2)
        provider.assert_not_called(); contract.assert_not_called(); self.assertIsNone(self.transport.CONFIG)

    def test_changed_config_hash_rejected_before_authentication(self):
        args = self.args('readiness'); args.local_config_sha = '0' * 64
        with mock.patch.object(sys, 'argv', self.cli(args)), mock.patch.object(self.transport, 'Provider') as provider, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.transport.main(), 2)
        provider.assert_not_called(); self.assertIsNone(self.transport.CONFIG)

    def test_invalid_review_config_and_source_pins_rejected_before_provider(self):
        # The release-contract fixture supplies no provider authority. These
        # cases exercise actual config/material/review binding, without producer
        # evidence or any model/evaluator access.
        for field in ('local_config_sha256', 'operator_files'):
            transport = load('local_bad_review_' + field, HERE / 'rl_transport.py')
            review = copy.deepcopy(self.review)
            if field == 'local_config_sha256': review[field] = '0' * 64
            else: review[field]['rl_transport.py'] = '0' * 64
            self.review_path.write_bytes(encoded(review)); args = self.args('readiness')
            output = io.StringIO()
            with mock.patch.object(sys, 'argv', self.cli(args)), mock.patch.object(transport, 'contract', return_value=self.manifest), mock.patch.object(transport, 'Provider') as provider, contextlib.redirect_stdout(output):
                self.assertEqual(transport.main(), 2)
            provider.assert_not_called()
            expected = 'local_review_config_binding' if field == 'local_config_sha256' else 'operator_bytes_not_reviewed'
            self.assertIn(expected, output.getvalue())

    def test_configure_rebinds_transport_globals_to_explicit_roots(self):
        args = self.args(); self.transport.configure_local(args)
        self.assertIs(self.transport.CONFIG, self.transport._common.CONFIG)
        self.assertEqual(self.transport.BASE, self.repository); self.assertEqual(self.transport.WORK, self.candidate)
        self.assertEqual(self.transport.STATE, Path(self.config_document['state_root']))
        self.assertEqual(self.transport.STOP, Path(self.config_document['gpu_stop_path']))
        self.assertFalse(self.transport.STATE.exists())

    def test_collector_rebinds_globals_and_uses_config_evidence_root(self):
        collector = load('local_collector_roots_fixture', HERE / 'rl_collect.py')
        args = self.args()
        def configured_contract(_):
            collector.transport.configure_local(args); return self.manifest
        # Deliberately stop before launch receipt reads; inspect actual root
        # rebinding independently of the full authenticated launch fixture.
        class StopBeforeLaunch(Exception): pass
        with mock.patch.object(collector.transport, 'load_contract', side_effect=configured_contract), mock.patch.object(collector.transport, 'monitor_gate', side_effect=StopBeforeLaunch):
            with self.assertRaises(StopBeforeLaunch): collector.bindings(args)
        self.assertIs(collector.CONFIG, collector.transport.CONFIG)
        self.assertEqual(collector.STATE, Path(self.config_document['state_root']))
        self.assertEqual(collector.OUT, Path(self.config_document['evidence_root']))
        self.assertEqual(collector.DOWNLOADS, collector.OUT / 'downloads')
        self.assertFalse(collector.OUT.exists())

    def test_frozen_original_operator_bytes_unchanged(self):
        for name, digest in FROZEN.items(): self.assertEqual(sha(ORIGINAL / name), digest)

    def test_exact_source_dependency_pins_are_acyclic_and_current(self):
        collector = load('local_collector_pins_fixture', HERE / 'rl_collect.py')
        self.assertEqual(self.transport.COMMON_SOURCE_SHA256, sha(HERE / 'operator_common.py'))
        self.assertEqual(collector.COMMON_SOURCE_SHA256, sha(HERE / 'operator_common.py'))
        self.assertEqual(collector.TRANSPORT_SOURCE_SHA256, sha(HERE / 'rl_transport.py'))
        self.assertEqual(self.transport._common.CONFIG_SOURCE_SHA256, sha(HERE / 'config.py'))
        self.assertIsNone(collector.CONFIG); self.assertIsNone(collector.OUT)

    def test_transport_common_change_or_symlink_rejected_before_execution(self):
        successor = self.root / 'successor'; successor.mkdir()
        shutil.copyfile(HERE / 'rl_transport.py', successor / 'rl_transport.py')
        (successor / 'operator_common.py').write_bytes(b"raise RuntimeError('unreviewed dependency executed')\n")
        with self.assertRaisesRegex(ValueError, 'local_common_source_pin'): load('local_bad_common_fixture', successor / 'rl_transport.py')
        (successor / 'operator_common.py').unlink(); (successor / 'operator_common.py').symlink_to(HERE / 'operator_common.py')
        with self.assertRaisesRegex(ValueError, 'unsafe_local_common_source'): load('local_linked_common_fixture', successor / 'rl_transport.py')

    def test_collector_changed_upstream_transport_rejected_before_execution(self):
        successor = self.root / 'collector-successor'; successor.mkdir()
        for name in ('rl_collect.py', 'operator_common.py'): shutil.copyfile(HERE / name, successor / name)
        (successor / 'rl_transport.py').write_bytes(b"raise RuntimeError('unreviewed transport executed')\n")
        with self.assertRaisesRegex(ValueError, 'local_operator_source_pin'): load('local_bad_transport_fixture', successor / 'rl_collect.py')

    def test_valid_timestamp_poisoned_dependency_caches_are_not_read(self):
        successor = self.root / 'cache-successor'; successor.mkdir()
        for name in ('config.py', 'operator_common.py', 'rl_transport.py', 'rl_collect.py'):
            shutil.copyfile(HERE / name, successor / name)
        for name in ('operator_common.py', 'rl_transport.py'):
            path = successor / name; raw = path.read_bytes(); stamp = path.stat().st_mtime_ns
            evil = b"raise RuntimeError('POISONED DEPENDENCY CACHE')\n"
            path.write_bytes(evil + b'#' * (len(raw) - len(evil))); os.utime(path, ns=(stamp, stamp))
            py_compile.compile(str(path), doraise=True)
            path.write_bytes(raw); os.utime(path, ns=(stamp, stamp))
        collector = load('local_poisoned_cache_fixture', successor / 'rl_collect.py')
        self.assertIsNone(collector.CONFIG)
        self.assertEqual(collector.transport.COMMON_SOURCE_SHA256, sha(successor / 'operator_common.py'))

    def test_scientific_process_time_and_pin_functions_remain_exact(self):
        old = functions(ORIGINAL / 'rl_transport.py'); new = functions(HERE / 'rl_transport.py')
        changed_transport = {'review_gate', 'load_contract', 'verify_code', 'parser'}
        self.assertEqual(set(new) - set(old), {'configure_local'})
        for name in set(old) - changed_transport: self.assertEqual(new[name], old[name], name)
        old = functions(ORIGINAL / 'rl_collect.py'); new = functions(HERE / 'rl_collect.py')
        changed_collector = {'bindings', 'fetch_selected', 'checkpoint_observation'}
        self.assertEqual(set(old), set(new))
        for name in set(old) - changed_collector: self.assertEqual(new[name], old[name], name)
        old_tree = ast.parse((ORIGINAL / 'rl_transport.py').read_bytes())
        literals = {node.targets[0].id: ast.literal_eval(node.value) for node in old_tree.body if isinstance(node, ast.Assign)
                    and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {'FORMAT', 'OLD_SOURCE', 'DOCKER'}}
        for name, value in literals.items(): self.assertEqual(getattr(self.transport, name), value)
        self.assertEqual(self.transport.PINS[0], self.transport.DREF + '/17')
        self.assertEqual(self.transport.clock(100), {'dispatch_epoch': 100, 'predispatch_epoch': 100, 'deadline_epoch': 43300,
                                                   'global_deadline_epoch': 43300, 'execution_deadline_epoch': 42100,
                                                   'outer_deadline_epoch': 42280, 'provider_timeout_seconds': 42300})


if __name__ == '__main__':
    unittest.main(verbosity=2)
