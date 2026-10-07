"""Caller-owned E10 admission across a real process boundary, without model IO.

The coordinator retains the map in memory and durably publishes it before
replying. The worker can request only its assigned next test. Hashes and host
clocks establish a replay boundary, not physical GPU or operating-system
attestation. The caller must retain the final receipt hash independently.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import select
import socket
import struct
import time

from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import (admit_test_allocation, allocation_deadlines,
    canonical, digest, failure_status, require, write)
from tools.nvarc_native_submission import reject_truth, task_binding

FORMAT = 'irisx/nvarc-caller-admissions-v1'
MAX_FRAME = 64 * 1024


def send_frame(channel, value, *, timeout=5):
    body = canonical(value)
    require(len(body) <= MAX_FRAME, 'bounded allocation frame required')
    channel.settimeout(timeout)
    channel.sendall(struct.pack('!I', len(body)) + body)


def receive_frame(channel, *, timeout=5):
    # One absolute timeout covers the header AND body, including a slow sender.
    end = time.monotonic() + timeout
    def exact(size):
        pieces = []
        while size:
            remaining = end-time.monotonic()
            require(remaining > 0, 'allocation transport deadline exhausted')
            channel.settimeout(remaining)
            body = channel.recv(size)
            require(body, 'allocation transport closed before complete frame')
            pieces.append(body); size -= len(body)
        return b''.join(pieces)
    size = struct.unpack('!I', exact(4))[0]
    require(0 < size <= MAX_FRAME, 'bounded allocation frame required')
    return parse_json(exact(size))


class CallerAdmissions:
    """One parent writer; every assignment has an independently fixed deadline."""
    def __init__(self, directory, plan, challenges, *, now=time.time):
        self.directory = Path(directory)
        self.plan, self.challenges, self.now = plan, challenges, now
        self.identity = {'run_id': plan['run_id'], 'plan_digest': digest(plan)}
        self.allocations, self.ledger, self.channels = {}, [], {}
        self.head = digest(self.identity)
        self.path = self.directory/'caller-admissions.json'
        self.ledger_path = self.directory/'caller-admission-ledger.jsonl'
        require(not self.path.exists() and not self.ledger_path.exists(),
                'fresh caller admission identity required')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.publish()

    def register(self, channel, task_id, common_deadline_epoch):
        import math
        require(task_id in self.challenges and task_id not in self.allocations and
                type(common_deadline_epoch) in (int, float) and math.isfinite(common_deadline_epoch),
                'one assigned caller channel with finite common deadline required')
        require(channel.fileno() not in self.channels, 'distinct caller channel required')
        self.channels[channel.fileno()] = {'channel': channel, 'task_id': task_id,
            'binding': task_binding(self.plan, self.challenges, task_id),
            'common_deadline_epoch': common_deadline_epoch, 'next_test': 0}
        self.allocations[task_id] = {}

    def admit(self, state, request):
        index = state['next_test']; binding = state['binding']
        require(isinstance(request, dict) and set(request) ==
            {'format', 'binding_digest', 'test_index'} and
            request['format'] == 'irisx/nvarc-test-request-v1' and
            request['binding_digest'] == digest(binding) and
            type(request['test_index']) is int and request['test_index'] == index and
            index < len(self.challenges[state['task_id']]['test']),
            'allocation request must be the assigned next actual test')
        started = self.now()
        allocation = admit_test_allocation(binding, index, started, state['common_deadline_epoch'])
        row = {'sequence': len(self.ledger), 'previous': self.head,
            'allocation': allocation, 'allocation_digest': digest(allocation)}
        row['digest'] = digest(row)
        # The receipt is durable before worker acknowledgement. If either write
        # fails, no usable response is sent and the run fails closed.
        with self.ledger_path.open('ab') as stream:
            stream.write(canonical(row)+b'\n'); stream.flush()
            import os
            os.fsync(stream.fileno())
        self.ledger.append(row); self.head = row['digest']
        self.allocations[state['task_id']][str(index)] = allocation
        state['next_test'] += 1
        self.publish()
        return {'format': 'irisx/nvarc-test-response-v1', 'allocation': allocation,
                'caller_receipt_head': self.head}

    def service(self, *, timeout=0):
        """Service ready channels; protocol errors are returned to the parent."""
        channels = [s['channel'] for s in self.channels.values()]
        if not channels: return []
        ready, _, _ = select.select(channels, [], [], timeout)
        failures = []
        for channel in ready:
            state = self.channels[channel.fileno()]
            try:
                response = self.admit(state, receive_frame(channel, timeout=1))
                send_frame(channel, response, timeout=1)
            except BaseException as error:
                if not (state['next_test'] == len(self.challenges[state['task_id']]['test']) and
                        isinstance(error, RuntimeError) and
                        str(error) == 'allocation transport closed before complete frame'):
                    failures.append((state['task_id'], error))
                self.unregister(channel)
        return failures

    def unregister(self, channel):
        self.channels.pop(channel.fileno(), None)
        channel.close()

    def publish(self):
        value = {'format': FORMAT, **self.identity, 'allocations': self.allocations,
            'ledger': self.ledger, 'ledger_head': self.head,
            'clock': 'coordinator time.time host epoch seconds',
            'gpu_timing_attestation': False}
        write(self.path, value)
        return hashlib.sha256(canonical(value)).hexdigest()

    def close(self):
        for state in list(self.channels.values()): self.unregister(state['channel'])
        # Rewrite from the parent-owned values after all producers have stopped;
        # never accept the worker's copy of this file as authoritative.
        return self.publish()


class AllocationClient:
    def __init__(self, fd, binding, *, timeout=5):
        self.channel = socket.socket(fileno=fd)
        self.binding, self.timeout, self.next_test = binding, timeout, 0

    def request(self, test_index):
        require(type(test_index) is int and test_index == self.next_test,
                'worker must request its next actual test')
        send_frame(self.channel, {'format': 'irisx/nvarc-test-request-v1',
            'binding_digest': digest(self.binding), 'test_index': test_index}, timeout=self.timeout)
        response = receive_frame(self.channel, timeout=self.timeout)
        require(isinstance(response, dict) and set(response) ==
            {'format', 'allocation', 'caller_receipt_head'} and
            response['format'] == 'irisx/nvarc-test-response-v1' and
            isinstance(response['caller_receipt_head'],str) and
            __import__('re').fullmatch('sha256:[0-9a-f]{64}',response['caller_receipt_head']),
            'closed caller allocation response required')
        allocation_deadlines(response['allocation'], self.binding, test_index)
        self.next_test += 1
        return response['allocation']

    def close(self): self.channel.close()


def run_admitted_tests(challenges, task_id, solve, checkpoint, adapter, client, schedule):
    """Both arms use identical caller-admitted 20/30 budgets for every test."""
    def admitted(index):
        allocation = client.request(index)
        adapter.generation_deadline, adapter.verification_deadline = allocation_deadlines(
            allocation, client.binding, index)
        return solve(index, allocation, schedule)
    tests = [{'test_index': index, 'status': 'not_executed', 'attempts': [], 'missing_attempts': 2}
             for index in range(len(challenges[task_id]['test']))]
    failure = None
    for index in range(len(tests)):
        try:
            tests[index] = admitted(index)
        except BaseException as error:
            tests[index] = {'test_index': index, 'status': failure_status(error),
                            'attempts': [], 'missing_attempts': 2}
            failure = {'error_type': type(error).__name__, 'error_message': str(error)[:1200]}
            checkpoint(tests); break
        checkpoint(tests)
    return tests, failure


def load_caller_receipt(path, expected_sha256, plan, challenges):
    """Explicit caller path + independent hash, never worker-file discovery."""
    import re
    path = Path(path)
    require(re.fullmatch('[0-9a-f]{64}', expected_sha256 or '') and
        not path.is_symlink() and path.is_file(), 'exact caller receipt hash/path required')
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == expected_sha256, 'caller admission receipt bytes differ')
    value = parse_json(body); reject_truth(value)
    require(set(value) == {'format', 'run_id', 'plan_digest', 'allocations', 'ledger',
        'ledger_head', 'clock', 'gpu_timing_attestation'} and value['format'] == FORMAT and
        value['run_id'] == plan['run_id'] and value['plan_digest'] == digest(plan) and
        value['clock'] == 'coordinator time.time host epoch seconds' and
        value['gpu_timing_attestation'] is False and isinstance(value['allocations'], dict) and
        isinstance(value['ledger'], list), 'closed matching caller admission receipt required')
    identity = {'run_id': plan['run_id'], 'plan_digest': digest(plan)}
    head = digest(identity); reconstructed = {key: {} for key in value['allocations']}
    require(set(reconstructed) <= set(challenges), 'foreign caller admission task')
    common = {}
    for index, row in enumerate(value['ledger']):
        require(isinstance(row, dict) and set(row) ==
            {'sequence', 'previous', 'allocation', 'allocation_digest', 'digest'} and
            type(row['sequence']) is int and row['sequence'] == index and row['previous'] == head and
            row['digest'] == digest({k: v for k, v in row.items() if k != 'digest'}),
            'caller admission chain differs')
        allocation = row['allocation']; key = allocation.get('binding', {}).get('task_id')
        require(key in reconstructed, 'unassigned caller allocation task')
        test_index = len(reconstructed[key])
        require(test_index < len(challenges[key]['test']) and
            row['allocation_digest'] == digest(allocation), 'caller actual-test allocation closure differs')
        allocation_deadlines(allocation, task_binding(plan, challenges, key), test_index)
        common.setdefault(key, allocation['session_deadline_epoch'])
        require(allocation['session_deadline_epoch'] == common[key], 'common caller deadline changed between tests')
        if test_index:
            require(allocation['started_epoch'] >= reconstructed[key][str(test_index-1)]['started_epoch'],
                    'caller test start moved backwards')
        reconstructed[key][str(test_index)] = allocation; head = row['digest']
    require(reconstructed == value['allocations'] and head == value['ledger_head'],
            'caller receipt allocation map/chain closure differs')
    return value['allocations']


def validate_caller_deadlines(evidence, allocations, plan, challenges):
    """Bind BOTH E10 arms to the caller, including killed/uncommitted prefixes.

    Deferred native replay additionally reconstructs its FIFO and eight-view
    evidence. This additive screen gate closes baseline deadline declarations;
    it does not reinterpret host timestamps as physical execution evidence.
    """
    for record in evidence:
        key = record['task_id']; binding = task_binding(plan, challenges, key)
        local = allocations.get(key, {})
        for event in record['events']:
            if event['event'] in {'test_started', 'generation_completed', 'verification_schedule'}:
                index = event['test_index']
                deadlines = allocation_deadlines(local.get(str(index)), binding, index)
                if event['event'] == 'generation_completed':
                    require(event['source_end_time'] == deadlines[0],
                            'generation source cutoff differs from caller admission')
                if event['event'] == 'verification_schedule':
                    require((event['generation_deadline'], event['verification_deadline']) == deadlines and
                        event['test_allocation_digest'] == digest(local[str(index)]),
                        'deferred declaration differs from caller admission')
            if event['event'] == 'test_terminal':
                result = event['result']; index = result['test_index']
                deadlines = allocation_deadlines(local.get(str(index)), binding, index)
                observed = result.get('telemetry', {}).get('cooperative_deadlines', {})
                require((observed.get('generation'), observed.get('verification')) == deadlines,
                        'both-arm terminal deadlines differ from caller admission')
