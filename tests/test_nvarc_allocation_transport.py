"""Synthetic/process-only caller transport; no model, provider, labels or GPU."""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

from tools import nvarc_allocation_transport as transport
from tools.nvarc_native_multitask import canonical, digest, write
from tools.nvarc_native_submission import task_binding


def fixture():
    challenges = {'a': {'train': [{'input': [[1]], 'output': [[2]]}],
                        'test': [{'input': [[3]]}, {'input': [[4]]}]}}
    plan = {'run_id': 'stage4-e10-screen-synthetic-deferred-r1',
            'producer_sha256': 'synthetic-no-model', 'challenges_digest': digest(challenges)}
    return plan, challenges


class AllocationTransportTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'POSIX inherited socket process fixture')
    def test_real_process_multiple_tests_parent_clock_and_separate_receipt(self):
        plan, challenges = fixture(); binding = task_binding(plan, challenges, 'a')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); stamps = iter([10., 55.])
            caller = transport.CallerAdmissions(root, plan, challenges, now=lambda: next(stamps))
            parent, child = socket.socketpair(); caller.register(parent, 'a', 80.)
            code = '''import json,os,sys
from tools.nvarc_allocation_transport import AllocationClient
client=AllocationClient(int(sys.argv[1]),json.loads(sys.argv[2]))
values=[client.request(0),client.request(1)]
print(json.dumps(values),flush=True)
'''
            environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1])+os.pathsep+'src',
                               PYTHONHASHSEED='0', CUDA_VISIBLE_DEVICES='')
            process = subprocess.Popen([sys.executable, '-c', code, str(child.fileno()), json.dumps(binding)],
                pass_fds=(child.fileno(),), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
            child.close()
            try:
                end = time.monotonic()+10
                while process.poll() is None and time.monotonic() < end:
                    self.assertEqual(caller.service(timeout=.1), [])
                out, err = process.communicate(timeout=2)
                self.assertEqual(process.returncode, 0, err.decode())
                values = json.loads(out)
                self.assertEqual([v['started_epoch'] for v in values], [10., 55.])
                self.assertEqual([transport.allocation_deadlines(v, binding, index) for index, v in enumerate(values)],
                                 [(30., 40.), (70., 80.)])
                receipt_hash = caller.close()
                trusted = transport.load_caller_receipt(caller.path, receipt_hash, plan, challenges)
                self.assertEqual(trusted['a'], {str(i): v for i, v in enumerate(values)})
                self.assertNotIn('worker_report', json.loads(caller.path.read_bytes()))
            finally:
                if process.poll() is None: process.kill(); process.wait(timeout=2)
                caller.close()

    def test_assigned_next_actual_index_only_without_extra_clock_reads(self):
        plan, challenges = fixture(); binding = task_binding(plan, challenges, 'a'); sampled = []
        with tempfile.TemporaryDirectory() as tmp:
            caller = transport.CallerAdmissions(tmp, plan, challenges, now=lambda: sampled.append(10) or 10)
            parent, child = socket.socketpair(); caller.register(parent, 'a', 15)
            state = caller.channels[parent.fileno()]
            request = {'format': 'irisx/nvarc-test-request-v1', 'binding_digest': digest(binding), 'test_index': 0}
            for changed in ({**request, 'test_index': True}, {**request, 'test_index': 1},
                            {**request, 'binding_digest': 'foreign'}, {**request, 'extra': 1}):
                with self.assertRaisesRegex(RuntimeError, 'assigned next'): caller.admit(state, changed)
            self.assertEqual(sampled, [])
            response = caller.admit(state, request)
            self.assertEqual(transport.allocation_deadlines(response['allocation'], binding, 0), (10, 15))
            with self.assertRaisesRegex(RuntimeError, 'assigned next'): caller.admit(state, request)
            self.assertEqual(sampled, [10]); caller.close(); child.close()

    def test_after_common_deadline_cannot_create_new_allowance(self):
        plan, challenges = fixture(); binding = task_binding(plan, challenges, 'a')
        with tempfile.TemporaryDirectory() as tmp:
            caller = transport.CallerAdmissions(tmp, plan, challenges, now=lambda: 100)
            parent, child = socket.socketpair(); caller.register(parent, 'a', 100)
            with self.assertRaisesRegex(RuntimeError, 'caller-admitted'):
                caller.admit(caller.channels[parent.fileno()], {'format': 'irisx/nvarc-test-request-v1',
                    'binding_digest': digest(binding), 'test_index': 0})
            self.assertEqual(caller.ledger, []); caller.close(); child.close()

    def test_rehashed_receipt_does_not_replace_independently_retained_hash(self):
        plan, challenges = fixture(); binding = task_binding(plan, challenges, 'a')
        with tempfile.TemporaryDirectory() as tmp:
            caller = transport.CallerAdmissions(tmp, plan, challenges, now=lambda: 10)
            parent, child = socket.socketpair(); caller.register(parent, 'a', 100)
            caller.admit(caller.channels[parent.fileno()], {'format': 'irisx/nvarc-test-request-v1',
                'binding_digest': digest(binding), 'test_index': 0})
            original = caller.close(); value = json.loads(caller.path.read_bytes())
            allocation = value['ledger'][0]['allocation']; allocation['session_deadline_epoch'] += 30
            value['allocations']['a']['0'] = copy.deepcopy(allocation)
            row = value['ledger'][0]; row['allocation_digest'] = digest(allocation)
            row['digest'] = digest({k: v for k, v in row.items() if k != 'digest'}); value['ledger_head'] = row['digest']
            write(caller.path, value)
            with self.assertRaisesRegex(RuntimeError, 'bytes differ'):
                transport.load_caller_receipt(caller.path, original, plan, challenges)
            child.close()

    def test_receipt_closure_foreign_plan_truth_and_common_deadline_mutations(self):
        plan, challenges = fixture(); binding = task_binding(plan, challenges, 'a')
        with tempfile.TemporaryDirectory() as tmp:
            caller = transport.CallerAdmissions(tmp, plan, challenges, now=lambda: 10)
            parent, child = socket.socketpair(); caller.register(parent, 'a', 100)
            for index in (0, 1): caller.admit(caller.channels[parent.fileno()], {
                'format': 'irisx/nvarc-test-request-v1', 'binding_digest': digest(binding), 'test_index': index})
            caller.close(); original = json.loads(caller.path.read_bytes())
            for mode in ('truth', 'foreign', 'missing', 'deadline'):
                value = copy.deepcopy(original)
                if mode == 'truth': value['allocations']['a']['0']['solutions'] = [[[1]]]
                if mode == 'foreign': value['plan_digest'] = 'foreign'
                if mode == 'missing': value['allocations']['a'].pop('1')
                if mode == 'deadline':
                    value['ledger'][1]['allocation']['session_deadline_epoch'] = 101
                    row = value['ledger'][1]; row['allocation_digest'] = digest(row['allocation'])
                    row['digest'] = digest({k: v for k, v in row.items() if k != 'digest'}); value['ledger_head'] = row['digest']
                write(caller.path, value); expected = hashlib.sha256(caller.path.read_bytes()).hexdigest()
                with self.subTest(mode=mode), self.assertRaises((RuntimeError, ValueError)):
                    transport.load_caller_receipt(caller.path, expected, plan, challenges)
            child.close()

    def test_partial_first_test_does_not_skip_later_test_and_exception_preserves_commit(self):
        plan, challenges = fixture(); binding = task_binding(plan, challenges, 'a')
        class Client:
            def request(self, index): return transport.admit_test_allocation(binding, index, 31*index, 80)
        client = Client(); client.binding = binding; adapter = SimpleNamespace(); saved = []; calls = []
        def solve(index, allocation, schedule):
            calls.append((index, adapter.generation_deadline, adapter.verification_deadline, schedule))
            if index: raise RuntimeError('synthetic second-test exception')
            return {'test_index': index, 'attempts': [[[2]]], 'termination_reason': 'inference_deadline'}
        tests, failure = transport.run_admitted_tests(challenges, 'a', solve,
            lambda values: saved.append(copy.deepcopy(values)), adapter, client, 'deferred')
        self.assertEqual(calls, [(0, 20, 30, 'deferred'), (1, 51, 61, 'deferred')])
        self.assertEqual(tests[0]['attempts'], [[[2]]]); self.assertEqual(tests[1]['attempts'], [])
        self.assertEqual(saved[-1][0], saved[0][0]); self.assertIn('second-test', failure['error_message'])

    def test_bounded_frames_reject_oversized_partial_and_duplicate_json(self):
        parent, child = socket.socketpair()
        try:
            child.sendall(struct.pack('!I', transport.MAX_FRAME+1))
            with self.assertRaisesRegex(RuntimeError, 'bounded'): transport.receive_frame(parent, timeout=.1)
            body = b'{"x":1,"x":2}'; child.sendall(struct.pack('!I', len(body))+body)
            with self.assertRaisesRegex(ValueError, 'duplicate'): transport.receive_frame(parent, timeout=.1)
            child.sendall(struct.pack('!I', 4)+b'{')
            with self.assertRaises((TimeoutError, RuntimeError)): transport.receive_frame(parent, timeout=.02)
        finally: parent.close(); child.close()

    def test_both_arm_deadline_gate_rejects_coordinated_baseline_mutations_and_prefixes(self):
        plan, challenges = fixture(); binding = task_binding(plan, challenges, 'a')
        allocation = transport.admit_test_allocation(binding, 0, 10, 100)
        allocations = {'a': {'0': allocation}}
        evidence = [{'task_id': 'a', 'events': [
            {'event': 'test_started', 'test_index': 0},
            {'event': 'generation_completed', 'test_index': 0, 'source_end_time': 30},
            {'event': 'test_terminal', 'result': {'test_index': 0,
                'telemetry': {'cooperative_deadlines': {'generation': 30, 'verification': 40}}}}]}]
        transport.validate_caller_deadlines(evidence, allocations, plan, challenges)
        for mode in ('coordinated', 'missing', 'prefix', 'terminal'):
            changed = copy.deepcopy(evidence); trusted = allocations
            if mode in ('coordinated', 'prefix'): changed[0]['events'][1]['source_end_time'] += 30
            if mode in ('coordinated', 'terminal'):
                for key in ('generation', 'verification'):
                    changed[0]['events'][2]['result']['telemetry']['cooperative_deadlines'][key] += 30
            if mode == 'prefix': changed[0]['events'].pop()
            if mode == 'missing': trusted = {}
            with self.subTest(mode=mode), self.assertRaisesRegex(RuntimeError, 'caller'):
                transport.validate_caller_deadlines(changed, trusted, plan, challenges)


if __name__ == '__main__': unittest.main()
