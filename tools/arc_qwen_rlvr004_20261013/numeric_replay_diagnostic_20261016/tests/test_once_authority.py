"""Offline once-RUN authority tests; fixtures never authorize provider execution.

Real scope checks, write-once claims, journals, receipt writer and bracket run
against bounded in-memory metadata. Reviewer/finalizer boundaries are explicit
test doubles. No authentication, network, SDK, model or provider is invoked.
"""
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import socket
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from tools.arc_qwen_rlvr004_20261013.numeric_replay_diagnostic_20261016 import assemble as a


def load(path):
    module = types.ModuleType('once_scope_' + path.stem)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec', dont_inherit=True,
                 optimize=sys.flags.optimize), vars(module))
    return module


def owner(stop):
    return {'format': 'irisx/numeric-diagnostic-owner-direction-v1', 'owner_id': 'danielwuu',
        'request_id': 'SYNTHETIC-CPU-ONLY', 'instruction': 'Synthetic offline scope fixture; never grants real provider execution.',
        'run_purpose': a.RUN_PURPOSE, 'training_only': True,
        'one_accepted_run_per_distinct_reviewed_candidate': True,
        'continuous_monitoring_authorized': not stop, 'result_retrieval_authorized': not stop,
        **({'stop_after_submit_readback': True, 'single_post_submit_readback_authorized': True} if stop else {}),
        'session_limit_seconds': 43200, 'original_public_task_count': 120, 'original_public_query_denominator': 167,
        **{k: False for k in ('rl_optimizer_commit_authorized', 'later_B_C_dev_holdout_PUBLIC_authorized',
            'gpu_quota_query_authorized', 'new_resource_or_paid_provisioning_authorized',
            'official_competition_submission_authorized', 'legal_agreement_acceptance_authorized',
            'credential_or_permission_changes_authorized_by_this_file', 'runtime_or_scientific_success_claim')}}


class ReadbackProvider:
    def __init__(self, transport, source, fail=False):
        self.t, self.source, self.fail = transport, source, fail
        self.calls = []

    def kernel(self):
        self.calls.append('kernel')
        if self.fail: raise OSError('synthetic read failure')
        t = self.t
        metadata = types.SimpleNamespace(id=138123872, ref=t.REF, is_private=True,
            current_version_number=t.ACTIVE_VERSION, title='IRIS-X Learning Agent 20261011',
            language='python', kernel_type='notebook', kernel_data_sources=[], enable_gpu=True,
            enable_tpu=False, enable_internet=False, model_data_sources=[t.MODEL],
            dataset_data_sources=['/'.join(s.split('/')[:2]) for s in t.PINS],
            competition_data_sources=['arc-prize-2026-arc-agi-3'], docker_image=t.DOCKER,
            machine_shape='NvidiaRtxPro6000')
        metadata.to_dict = lambda: {'synthetic_test_only': True, 'source': 'in-memory metadata'}
        return types.SimpleNamespace(metadata=metadata, blob=types.SimpleNamespace(source=self.source.decode()))

    def status(self):
        self.calls.append('status')
        return types.SimpleNamespace(status=types.SimpleNamespace(name='RUNNING'), failure_message='')


class OnceAuthorityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='numeric-once-CPU-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')))
        self.t = load(HERE.parent / 'publication_windows_bridge_20261015/rl_transport.py')
        self.w = load(HERE / 'publication/verify_active_wire.py')
        t, c = self.t, self.t._common
        c.CONFIG = types.SimpleNamespace(scratch_root=self.root, evidence_root=self.root)
        c.STATE = c.PUBLICATION_STATE = self.root
        c.STOP = self.root / 'gpu-stop.json'
        t.__dict__.update({k: v for k, v in vars(c).items() if not k.startswith('_')})
        t.ACTIVE_VERSION = 49
        t.PINS = [t.DREF + '/25', *t.NON_CODE_PINS]

    def manifest(self, stop):
        direction = owner(stop)
        raw = a.encoded(direction)
        (self.root / 'OWNER-DIRECTION.json').write_bytes(raw)
        return {'owner_session_stop_attestation': {'path': 'OWNER-DIRECTION.json', **a.desc(raw)},
                'local_reconstruction': a.owner_publication_scope(direction)}

    def test_legacy_continuous_and_explicit_once_scope_agree(self):
        for stop in (False, True):
            with self.subTest(stop=stop):
                m = self.manifest(stop)
                expected = a.owner_publication_scope(owner(stop))
                self.assertEqual(self.t.diagnostic_owner_scope(owner(stop)), expected)
                self.assertEqual(self.t.publication_scope(m), expected)
                self.assertEqual(self.w.publication_scope(m, self.root), expected)
                path = self.root / 'OWNER-DIRECTION.json'
                self.assertEqual(a.owner_inputs(path, a.sha(path.read_bytes()))[0], owner(stop))

    def test_missing_mixed_or_truthy_authority_fails(self):
        cases = [('stop_after_submit_readback', False), ('stop_after_submit_readback', 1),
                 ('single_post_submit_readback_authorized', False), ('single_post_submit_readback_authorized', 1),
                 ('continuous_monitoring_authorized', True), ('result_retrieval_authorized', True),
                 ('one_accepted_run_per_distinct_reviewed_candidate', 1)]
        for key, value in cases:
            bad = dict(owner(True), **{key: value})
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError): a.owner_publication_scope(bad)
                with self.assertRaises(ValueError): self.t.diagnostic_owner_scope(bad)
        for key in ('stop_after_submit_readback', 'single_post_submit_readback_authorized'):
            bad = owner(True); del bad[key]
            with self.assertRaises(ValueError): a.owner_publication_scope(bad)

    def test_manifest_cannot_expand_once_owner_authority(self):
        for key in ('stop_after_submit_readback', 'single_post_submit_readback_authorized',
                    'provider_monitoring_authorized', 'exact_output_retrieval_authorized'):
            m = self.manifest(True)
            m['local_reconstruction'][key] = not m['local_reconstruction'][key]
            with self.subTest(key=key), self.assertRaises(ValueError): self.w.publication_scope(m, self.root)
            with self.assertRaises(ValueError): self.t.publication_scope(m)

    def execution(self, stop, action):
        m = self.manifest(stop)
        path = self.root / 'publication-manifest.json'; path.write_bytes(a.encoded(m))
        args = types.SimpleNamespace(action=action, manifest=str(path), manifest_sha=a.sha(path.read_bytes()),
            review='synthetic', review_sha='a'*64, material_sha='b'*64)
        review = {'provider_execution_admitted': True, 'synthetic_test_only': False, 'allowed_actions': [action]}
        return m, args, review

    def test_old_review_actions_cannot_grant_once_monitor_collect_or_watch(self):
        for action in ('poll', 'collect', 'watch'):
            m, args, review = self.execution(True, action)
            with self.subTest(action=action), patch.object(self.t, 'review_gate', return_value=review), \
                 patch.object(self.t, 'Provider') as provider:
                with self.assertRaisesRegex(ValueError, 'forbids_monitoring_and_retrieval'):
                    self.t.execution_gate(args, monitor=True)
                provider.assert_not_called()
            m, args, review = self.execution(False, action)
            with patch.object(self.t, 'review_gate', return_value=review):
                self.assertEqual(self.t.execution_gate(args, monitor=True), review)

    def test_consumed_claim_receipt_or_journal_blocks_before_provider(self):
        for name, value in (('active-readback.claim.json', {}), ('notebook-rlvr004-receipt.json', {}),
                            ('notebook-rlvr004-journal.json', {'post_submit_readback_attempts': 1}),
                            ('notebook-rlvr004-journal.json', {'single_post_submit_readback': True})):
            path = self.root / name; path.write_bytes(a.encoded(value))
            for action in ('verify-run', 'readiness', 'verify-code', 'verify-code-files', 'verify-inactive'):
                m, args, review = self.execution(True, action)
                with self.subTest(name=name, action=action), patch.object(self.t, 'review_gate', return_value=review), \
                     patch.object(self.t, 'Provider') as provider:
                    with self.assertRaisesRegex(ValueError, 'already_consumed'): self.t.execution_gate(args)
                    provider.assert_not_called()
            path.unlink()

    def test_locked_preprovider_check_closes_consumption_race(self):
        m, args, review = self.execution(True, 'readiness')
        @contextmanager
        def consumed_between_admission_and_lock():
            (self.root / 'active-readback.claim.json').write_bytes(b'{}\n')
            yield
        parser = types.SimpleNamespace(parse_args=lambda: args)
        with patch.object(self.t, 'parser', return_value=parser), patch.object(self.t, 'load_contract', return_value=m), \
             patch.object(self.t, 'review_gate', return_value=review), patch.object(self.t, 'lock', consumed_between_admission_and_lock), \
             patch.object(self.t, 'failure', side_effect=lambda e, action: {'error': str(e)}), \
             patch.object(self.t, 'Provider') as provider, redirect_stdout(io.StringIO()):
            self.assertEqual(self.t.main(), 2)
            provider.assert_not_called()

    def readback_fixture(self, stop, fail=False):
        t = self.t
        m = self.manifest(stop)
        scope = m['local_reconstruction']
        raw = b'{"cells": [], "metadata": {}}\n'
        row = {'role': 'rlvr004', 'expected_version': t.ACTIVE_VERSION,
            'title': 'IRIS-X Learning Agent 20261011', 'language': 'python', 'kernel_type': 'notebook',
            'enable_gpu': True, 'competition_sources': ['arc-prize-2026-arc-agi-3']}
        m['notebooks'] = [row]
        args = types.SimpleNamespace(manifest=str(self.root / 'publication-manifest.json'), manifest_sha='c'*64)
        t.write_new(self.root / 'active-finalized.ipynb', raw)
        claim = t.write_new(self.root / 'notebook-rlvr004.claim.json', {'synthetic_test_only': True, **scope})
        final = {'manifest_sha256': args.manifest_sha, 'finalized_sha256': t.sha(raw), **t.clock(100)}
        final_row = t.write_new(self.root / 'finalization.json', final)
        j = {'expected_version': t.ACTIVE_VERSION, 'manifest_sha256': args.manifest_sha, 'save_calls': 1,
             'claim_sha256': claim['sha256'], 'source_sha256': t.sha(raw), 'finalization_sha256': final_row['sha256'],
             'stage': 'save_accepted', 'predecessor': {'version': 48}, 'git_publication_completed': True,
             'git_commit': 'd'*40, 'single_post_submit_readback': False, **t.clock(100), **scope}
        t.publication_journal('notebook-rlvr004', j)
        return m, args, ReadbackProvider(t, raw, fail)

    def test_one_real_bracket_writes_honest_receipt_then_rejects_repeat(self):
        m, args, provider = self.readback_fixture(True)
        with patch.object(self.t, 'check_finalization'):
            receipt = self.t.verify_notebook(provider, m, args, 'rlvr004')
            self.assertEqual(provider.calls, ['kernel', 'status', 'kernel'])
            self.assertTrue(receipt['single_post_submit_readback'])
            self.assertTrue(receipt['stop_after_submit_readback'])
            self.assertFalse(receipt['provider_monitoring_authorized'])
            self.assertFalse(receipt['exact_output_retrieval_authorized'])
            journal = self.t.obj(self.root / 'notebook-rlvr004-journal.json')
            self.assertTrue(journal['single_post_submit_readback'])
            self.assertEqual(journal['post_submit_readback_attempts'], 1)
            self.assertEqual(receipt['launch_journal_sha256'], self.t.file_sha(self.root / 'notebook-rlvr004-journal.json'))
            self.assertEqual(journal['deadline_epoch'], 43300)
            with self.assertRaisesRegex(ValueError, 'already_consumed'):
                self.t.verify_notebook(provider, m, args, 'rlvr004')
            self.assertEqual(provider.calls, ['kernel', 'status', 'kernel'])

    def test_failed_bracket_cannot_retry(self):
        m, args, provider = self.readback_fixture(True, fail=True)
        with patch.object(self.t, 'check_finalization'):
            with self.assertRaisesRegex(OSError, 'synthetic read failure'):
                self.t.verify_notebook(provider, m, args, 'rlvr004')
            self.assertEqual(provider.calls, ['kernel'])
            self.assertFalse((self.root / 'notebook-rlvr004-receipt.json').exists())
            journal = self.t.obj(self.root / 'notebook-rlvr004-journal.json')
            self.assertEqual(journal['post_submit_readback_attempts'], 1)
            self.assertFalse(journal['single_post_submit_readback'])
            with self.assertRaisesRegex(ValueError, 'already_consumed'):
                self.t.verify_notebook(provider, m, args, 'rlvr004')
            self.assertEqual(provider.calls, ['kernel'])

    def test_legacy_continuous_readback_remains_repeatable(self):
        m, args, provider = self.readback_fixture(False)
        with patch.object(self.t, 'check_finalization'):
            first = self.t.verify_notebook(provider, m, args, 'rlvr004')
            second = self.t.verify_notebook(provider, m, args, 'rlvr004')
        self.assertEqual(len(provider.calls), 6)
        self.assertFalse(first['single_post_submit_readback'])
        self.assertFalse(second['stop_after_submit_readback'])
        self.assertTrue(second['provider_monitoring_authorized'])
        self.assertTrue(second['exact_output_retrieval_authorized'])

    def test_full_independent_wire_binds_once_and_continuous_authority(self):
        fixture = load(HERE.parent / 'publication_portable_20261015/tests/test_portable_wire.py')
        source = fixture.FINALIZER_SOURCE.replace(
            b'/kaggle/working/irisx-qwen14b-rlvr-20261013-run008', a.RUN.encode()).replace(
            b'/kaggle/working/irisx-qwen14b-rlvr-20261013-source008', a.SOURCE.encode())
        original_put = fixture.put
        for stop in (False, True):
            scope = a.owner_publication_scope(owner(stop))
            def scoped_put(path, value):
                if path.name == 'publication-manifest.json':
                    direction = original_put(path.parent / 'OWNER-DIRECTION.json', owner(stop))
                    direction['path'] = 'OWNER-DIRECTION.json'
                    value.update(run_purpose=a.RUN_PURPOSE, local_reconstruction=dict(scope),
                                 owner_session_stop_attestation=direction)
                elif path.name in ('notebook-rlvr004.claim.json', 'notebook-rlvr004-journal.json'):
                    value.update(scope)
                return original_put(path, value)
            with self.subTest(stop=stop), patch.object(fixture, 'v', self.w), \
                 patch.object(fixture, 'VERIFIER', HERE / 'publication/verify_active_wire.py'), \
                 patch.object(fixture, 'FINALIZER_SOURCE', source), patch.object(fixture, 'put', scoped_put):
                f = fixture.Fixture(self.root / ('wire-stop' if stop else 'wire-continuous'))
                self.assertEqual(f.verify()['status'], 'PASS')
                for required in ('stop_after_submit_readback', 'provider_monitoring_authorized'):
                    saved = f.journal.pop(required)
                    original_put(f.state / 'notebook-rlvr004-journal.json', f.journal)
                    with self.assertRaisesRegex(ValueError, 'current owner publication scope'): f.verify()
                    f.journal[required] = saved
                    original_put(f.state / 'notebook-rlvr004-journal.json', f.journal)
                if stop:
                    # Rebind hashes honestly; the independent semantic check still rejects.
                    f.claim['single_post_submit_readback'] = True
                    f.save_claim()
                    with self.assertRaisesRegex(ValueError, 'unsent readback scope'): f.verify()
                    f.claim['single_post_submit_readback'] = False
                    f.save_claim()
                    f.journal['provider_monitoring_authorized'] = True
                    original_put(f.state / 'notebook-rlvr004-journal.json', f.journal)
                    with self.assertRaisesRegex(ValueError, 'current owner publication scope'): f.verify()

    def test_static_consumer_review_still_required(self):
        text = (HERE / 'publication/rl_transport.py').read_text()
        import ast
        tree = ast.parse(text)
        for name in ('publication_preflight', 'run_prerequisites'):
            fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            self.assertIn('monitor_gate(args)', ast.get_source_segment(text, fn))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        self.assertLess(ast.get_source_segment(text, main).index('execution_gate(a)'),
                        ast.get_source_segment(text, main).index('provider=Provider()'))


if __name__ == '__main__': unittest.main()
