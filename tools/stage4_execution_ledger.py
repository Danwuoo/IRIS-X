"""Local Stage 4 execution admission and crash-conservative action journal.

This module performs no provider calls and never reads credentials. A caller must
reserve an action before making the corresponding external request, then retain
its non-secret receipt. A crash or uncertain provider response leaves the action
pending; it does not grant a second push. Hashes attest bytes, not trusted clocks
or physical GPU activity. Official competition submission is deliberately absent.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.arc_kaggle_submission import parse_json


PLAN = 'irisx/stage4-execution-plan-v1'
RESOURCE_PLAN = 'irisx/stage4-resource-execution-plan-v1'
STATE = 'irisx/stage4-execution-ledger-v1'
ACTIONS = {'push', 'status', 'retrieve'}
SHA = re.compile(r'[0-9a-f]{64}')


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def timestamp(value):
    require(type(value) is str, 'timestamp string required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timezone-qualified timestamp required')
    return result


def utc():
    return datetime.now(timezone.utc).isoformat()


def finite(value, *, positive=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0), 'finite resource bound required')
    return value


def validate_plan(plan):
    require(type(plan) is dict and set(plan) == {
        'format', 'run_id', 'purpose', 'created_at', 'source_commit',
        'package_sha256', 'provider', 'private', 'internet', 'maximum_paid_usd',
        'bounds', 'quota', 'materials'}, 'closed Stage 4 plan required')
    require(plan['format'] in (PLAN, RESOURCE_PLAN) and plan['provider'] == 'kaggle',
            'unsupported provider/plan')
    resource_only = plan['format'] == RESOURCE_PLAN
    require(not resource_only or plan['purpose'] == 'resource-check',
            'synthetic control plan is resource-check only')
    require(type(plan['run_id']) is str and re.fullmatch(r'stage4-[a-z0-9][a-z0-9-]{5,70}',
                                                       plan['run_id']), 'new Stage 4 run identity required')
    require(plan['purpose'] in {'development', 'resource-check', 'private-rehearsal'},
            'official submission is not an admitted action')
    timestamp(plan['created_at'])
    require(type(plan['source_commit']) is str and re.fullmatch('[0-9a-f]{40}',
            plan['source_commit']), 'exact source commit required')
    require(type(plan['package_sha256']) is str and SHA.fullmatch(plan['package_sha256']),
            'exact package byte hash required')
    require(plan['private'] is True and plan['internet'] is False
            and type(plan['maximum_paid_usd']) is int and plan['maximum_paid_usd'] == 0,
            'private offline USD 0 only')
    bounds = plan['bounds']
    bound_fields = {'session_wall_seconds',
        'quota_multiplier', 'reserved_quota_seconds', 'gpu_count', 'task_runs',
        'training_steps', 'generation_forwards', 'verification_forwards',
        'input_tokens', 'maximum_output_bytes', 'maximum_retrieval_attempts'}
    if resource_only:
        bound_fields |= {'synthetic_worker_runs', 'control_forwards'}
    require(type(bounds) is dict and set(bounds) == bound_fields,
        'closed finite workload bounds required')
    finite(bounds['session_wall_seconds'], positive=True)
    require(bounds['session_wall_seconds'] <= 12 * 3600, 'session exceeds published outer ceiling')
    finite(bounds['quota_multiplier'], positive=True)
    require(bounds['quota_multiplier'] >= 1, 'at least whole-session quota accounting required')
    finite(bounds['reserved_quota_seconds'], positive=True)
    require(bounds['reserved_quota_seconds'] >= bounds['session_wall_seconds'] * bounds['quota_multiplier'],
            'quota reservation does not cover whole session')
    for key in set(bounds) - {'session_wall_seconds', 'quota_multiplier', 'reserved_quota_seconds'}:
        require(type(bounds[key]) is int and bounds[key] >= 0, 'integer workload bounds required: ' + key)
    require(1 <= bounds['gpu_count'] <= 4
            and bounds['maximum_output_bytes'] > 0
            and 1 <= bounds['maximum_retrieval_attempts'] <= 3, 'invalid physical/workload bound')
    if resource_only:
        require(all(bounds[key] == 0 for key in ('task_runs', 'training_steps',
                    'generation_forwards', 'verification_forwards'))
                and bounds['synthetic_worker_runs'] == bounds['gpu_count']
                and bounds['control_forwards'] > 0 and bounds['input_tokens'] > 0,
                'resource-only controls cannot admit scientific tasks, training or generation')
    else:
        require(bounds['task_runs'] > 0, 'scientific workload requires positive task runs')
    quota = plan['quota']
    require(type(quota) is dict and set(quota) == {'snapshot_sha256', 'observed_at',
        'remaining_free_seconds', 'pay_to_scale_enabled'}, 'closed current quota evidence required')
    require(type(quota['snapshot_sha256']) is str and SHA.fullmatch(quota['snapshot_sha256']),
            'quota snapshot byte hash required')
    timestamp(quota['observed_at'])
    require(quota['pay_to_scale_enabled'] is False, 'paid scaling must be disabled')
    finite(quota['remaining_free_seconds'])
    require(quota['remaining_free_seconds'] >= bounds['reserved_quota_seconds'],
            'insufficient free quota for bounded session')
    materials = plan['materials']
    require(type(materials) is dict and set(materials) == {'model_ref', 'model_material_digest',
        'source_inventory_digest', 'challenge_digest', 'partition_manifest_sha256'},
        'closed material bindings required')
    require(type(materials['model_ref']) is str and re.fullmatch(
        r'[A-Za-z0-9_-][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*){0,4}',
        materials['model_ref']), 'structured noncredential model reference required')
    for key in ('model_material_digest', 'source_inventory_digest', 'challenge_digest'):
        require(type(materials[key]) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', materials[key]),
                'exact material digest required: ' + key)
    require(type(materials['partition_manifest_sha256']) is str
            and SHA.fullmatch(materials['partition_manifest_sha256']), 'partition binding required')
    return plan


def _sync(directory):
    if os.name != 'nt':
        fd = os.open(directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _exclusive(path, body):
    require(not path.is_symlink(), 'symlink journal path forbidden')
    with path.open('xb') as stream:
        require(stream.write(body) == len(body), 'short journal write')
        stream.flush()
        os.fsync(stream.fileno())


class Ledger:
    def __init__(self, root, *, campaign_root=None):
        self.root = Path(root).absolute()
        # All provider invocations in one campaign must use this one canonical
        # account-level directory. Sibling ledger roots share it by default.
        self.campaign_root = (Path(campaign_root).absolute() if campaign_root is not None
                              else self.root.parent/'.stage4-shared-admission')

    @contextmanager
    def _lock(self):
        require(not self.root.is_symlink(), 'symlink ledger root forbidden')
        lock = self.root / '.owner.lock'
        _exclusive(lock, canonical({'pid': os.getpid(), 'nonce': uuid.uuid4().hex}))
        try:
            yield
        finally:
            lock.unlink()  # A hard crash leaves ownership for explicit reconciliation.

    def initialize(self, plan, *, package, quota_snapshot, now=None):
        """Validate local byte bindings and fresh quota before creating an identity."""
        plan = validate_plan(plan)
        at = timestamp(now or utc())
        age = (at - timestamp(plan['quota']['observed_at'])).total_seconds()
        require(0 <= age <= 900, 'quota snapshot must be observed within 15 minutes')
        package = Path(package).absolute()
        require(not package.is_symlink(), 'regular package source required')
        package_body = package.read_bytes()
        quota_body = Path(quota_snapshot).read_bytes()
        require(sha(package_body) == plan['package_sha256'], 'package bytes differ')
        require(sha(quota_body) == plan['quota']['snapshot_sha256'],
                'quota snapshot bytes differ')
        require(timestamp(plan['created_at']) <= at, 'plan cannot be created after initialization')
        self.root.mkdir(parents=True, exist_ok=False)
        _exclusive(self.root / 'plan.json', canonical(plan))
        inputs = {'package_source': str(package), 'campaign_root': str(self.campaign_root)}
        _exclusive(self.root/'inputs.json', canonical(inputs))
        _exclusive(self.root/'outbound.bin', package_body)
        _exclusive(self.root/'quota-snapshot.json', quota_body)
        (self.root / 'events').mkdir()
        with self._lock():
            self._commit(None, {'kind': 'initialize', 'at': at.isoformat(),
                'plan_sha256': sha(canonical(plan)), 'inputs_sha256': sha(canonical(inputs))})
        return self.read()

    @contextmanager
    def _campaign_lock(self):
        require(not self.campaign_root.is_symlink(), 'regular canonical campaign directory required')
        self.campaign_root.mkdir(parents=True, exist_ok=True)
        path = self.campaign_root/'.owner.lock'
        _exclusive(path, canonical({'pid': os.getpid(), 'nonce': uuid.uuid4().hex}))
        try:
            yield
        finally:
            path.unlink()

    def _campaign_reserve(self, state, at):
        """Call with both ledger and campaign locks; consumed IDs never expire."""
        plan = state['plan']; key = self.campaign_root/(plan['run_id']+'.json')
        require(not key.exists() and not key.is_symlink(), 'run identity already consumed in this campaign')
        reserved = 0.0
        for path in sorted(self.campaign_root.glob('*.json')):
            require(not path.is_symlink(), 'regular campaign reservation required')
            record = parse_json(path.read_bytes())
            require(set(record) == {'run_id', 'ledger_root', 'plan_sha256', 'reserved_quota_seconds', 'at'},
                    'closed campaign reservation required')
            other = Ledger(record['ledger_root'], campaign_root=self.campaign_root).read()
            require(sha(canonical(other['plan'])) == record['plan_sha256']
                    and other['plan']['run_id'] == record['run_id']
                    and path.name == record['run_id']+'.json'
                    and record['reserved_quota_seconds'] == other['plan']['bounds']['reserved_quota_seconds'],
                    'campaign binding differs')
            timestamp(record['at'])
            rejected = any(e.get('kind') == 'receipt' and e.get('result') == 'rejected-without-version'
                           for e in other['events'])
            # Conservatively retain uncertain/uncommitted reservations. A fresh
            # provider snapshot plus observed terminal state releases occupancy;
            # previously consumed runtime remains charged by that snapshot.
            terminal_events = [e for e in other['events'] if e.get('kind') == 'receipt'
                               and e.get('result') in {'complete', 'error', 'cancelled'}]
            # Reusing a pre-run quota snapshot must not resurrect spent quota.
            # Only a newly observed provider snapshot strictly after termination
            # can account for prior consumption and release this reservation.
            accounted_terminal = bool(terminal_events) and timestamp(plan['quota']['observed_at']) > timestamp(
                terminal_events[-1]['at'])
            if not rejected and not accounted_terminal:
                reserved += finite(record['reserved_quota_seconds'])
        amount = plan['bounds']['reserved_quota_seconds']
        require(reserved + amount <= plan['quota']['remaining_free_seconds'],
                'shared campaign free quota already reserved')
        record = {'run_id': plan['run_id'], 'ledger_root': str(self.root),
                  'plan_sha256': sha(canonical(plan)), 'reserved_quota_seconds': amount, 'at': at}
        _exclusive(key, canonical(record))
        _sync(self.campaign_root)
        return sha(canonical(record))

    def _commit(self, previous, event):
        number = 0 if previous is None else previous['sequence'] + 1
        envelope = {'format': STATE, 'sequence': number,
                    'previous_sha256': None if previous is None else previous['sha256'], 'event': event}
        body = canonical(envelope)
        path = self.root / 'events' / f'{number:06d}.json'
        _exclusive(path, body)
        _sync(path.parent)
        marker = canonical({'sequence': number, 'sha256': sha(body)})
        temporary = self.root / ('state.' + uuid.uuid4().hex + '.tmp')
        _exclusive(temporary, marker)
        os.replace(temporary, self.root / 'state.json')
        _sync(self.root)

    def read(self):
        require(not self.root.is_symlink() and not (self.root/'events').is_symlink(), 'regular ledger required')
        require(not (self.root/'plan.json').is_symlink() and not (self.root/'state.json').is_symlink(),
                'regular journal files required')
        plan = validate_plan(parse_json((self.root/'plan.json').read_bytes()))
        require(not (self.root/'inputs.json').is_symlink(), 'regular input binding required')
        inputs_body = (self.root/'inputs.json').read_bytes()
        inputs = parse_json(inputs_body)
        require(type(inputs) is dict and set(inputs) == {'package_source', 'campaign_root'}
                and all(type(v) is str and Path(v).is_absolute() for v in inputs.values())
                and inputs['campaign_root'] == str(self.campaign_root), 'closed canonical input paths required')
        marker = parse_json((self.root/'state.json').read_bytes())
        require(set(marker) == {'sequence', 'sha256'} and type(marker['sequence']) is int
                and marker['sequence'] >= 0 and type(marker['sha256']) is str
                and SHA.fullmatch(marker['sha256']), 'invalid journal marker')
        events = []
        previous = None
        for index in range(marker['sequence'] + 1):
            path = self.root/'events'/f'{index:06d}.json'
            require(not path.is_symlink(), 'symlink event forbidden')
            body = path.read_bytes()
            envelope = parse_json(body)
            require(set(envelope) == {'format', 'sequence', 'previous_sha256', 'event'}
                    and envelope['format'] == STATE and type(envelope['sequence']) is int
                    and envelope['sequence'] == index and envelope['previous_sha256'] == previous,
                    'journal chain differs')
            require(canonical(envelope) == body, 'noncanonical journal event')
            previous = sha(body)
            events.append(envelope['event'])
        require(previous == marker['sha256'], 'journal marker hash differs')
        require(type(events[0]) is dict and set(events[0]) == {'kind', 'at', 'plan_sha256', 'inputs_sha256'}
                and events[0]['kind'] == 'initialize' and events[0]['plan_sha256'] == sha(canonical(plan))
                and events[0]['inputs_sha256'] == sha(inputs_body),
                'immutable plan binding differs')
        initial_at = timestamp(events[0]['at'])
        require(timestamp(plan['created_at']) <= initial_at
                and 0 <= (initial_at - timestamp(plan['quota']['observed_at'])).total_seconds() <= 900,
                'initializer time/initial quota differs')
        state = {'plan': plan, 'marker': marker, 'events': events, 'pending': {}, 'counts': {a: 0 for a in ACTIONS},
                 'accepted': None, 'terminal': None, 'retrieved': False, 'inputs': inputs}
        seen_requests = set()
        last_at = initial_at
        for event in events[1:]:
            require(type(event) is dict and 'kind' in event and 'at' in event, 'invalid journal event')
            at = timestamp(event['at'])
            require(at >= last_at, 'journal event time moved backwards')
            last_at = at
            if event['kind'] == 'reserve':
                require('action' in event, 'action field required')
                fields = {'kind', 'at', 'action', 'request_id'}
                if event['action'] == 'push': fields.add('campaign_sha256')
                require(set(event) == fields, 'closed reserve event required')
                action, request_id = event['action'], event['request_id']
                require(type(request_id) is str and re.fullmatch('[0-9a-f]{32}', request_id)
                        and request_id not in seen_requests, 'invalid action request identity')
                self._admit(state, action, event['at'])
                if action == 'push':
                    record_path = self.campaign_root/(plan['run_id']+'.json')
                    require(not record_path.is_symlink(), 'regular campaign reservation required')
                    record_body = record_path.read_bytes()
                    record = parse_json(record_body)
                    require(sha(record_body) == event['campaign_sha256']
                            and record['at'] == event['at'] and record['ledger_root'] == str(self.root)
                            and record['plan_sha256'] == sha(canonical(plan))
                            and record['run_id'] == plan['run_id']
                            and record['reserved_quota_seconds'] == plan['bounds']['reserved_quota_seconds'],
                            'campaign reservation differs from admitted event')
                seen_requests.add(request_id)
                state['pending'][request_id] = action
                state['counts'][action] += 1
            elif event['kind'] == 'receipt':
                require(set(event) == {'kind', 'at', 'request_id', 'result', 'receipt_sha256',
                                      'provider_identity'}, 'closed receipt event required')
                request_id = event['request_id']
                require(request_id in state['pending'], 'receipt has no reservation')
                self._validate_receipt(state['pending'][request_id], event['result'],
                                       event['receipt_sha256'], event['provider_identity'], state['accepted'])
                action = state['pending'].pop(request_id)
                if action == 'push' and event['result'] == 'accepted':
                    state['accepted'] = event['provider_identity']
                if action == 'status' and event['result'] in {'complete', 'error', 'cancelled'}:
                    state['terminal'] = event['result']
                if action == 'retrieve' and event['result'] == 'verified':
                    state['retrieved'] = True
            else:
                raise ValueError('unknown journal event')
        return state

    @staticmethod
    def _admit(state, action, at):
        require(action in ACTIONS, 'only private push/status/retrieve actions admitted')
        require(not state['pending'], 'pending action requires reconciliation; no automatic retry')
        if action == 'push':
            require(state['counts']['push'] == 0, 'one immutable push per run identity')
            age = (timestamp(at) - timestamp(state['plan']['quota']['observed_at'])).total_seconds()
            require(0 <= age <= 900, 'stale quota admission; acquire a new bound before push')
        else:
            require(state['accepted'] is not None, 'accepted exact provider version required')
            if action == 'status':
                require(state['terminal'] is None, 'terminal state is immutable; no further polling')
            if action == 'retrieve':
                require(state['terminal'] is not None and not state['retrieved'], 'terminal uncollected run required')
                require(state['counts']['retrieve'] < state['plan']['bounds']['maximum_retrieval_attempts'],
                        'bounded retrieval attempts exhausted')

    @staticmethod
    def _validate_receipt(action, result, receipt_sha256, provider_identity, accepted):
        require(type(receipt_sha256) is str and SHA.fullmatch(receipt_sha256), 'non-secret receipt byte hash required')
        allowed = {'push': {'accepted', 'rejected-without-version'},
                   'status': {'queued', 'running', 'complete', 'error', 'cancelled'},
                   'retrieve': {'verified', 'failed'}}
        require(result in allowed[action], 'unknown result remains pending for reconciliation')
        if action in {'status', 'retrieve'} or (action == 'push' and result == 'accepted'):
            require(type(provider_identity) is dict and set(provider_identity) == {'kernel_id', 'version'}
                    and type(provider_identity['kernel_id']) is str
                    and re.fullmatch(r'[a-z0-9_-]+/[a-z0-9_-]+', provider_identity['kernel_id'])
                    and type(provider_identity['version']) is int and provider_identity['version'] > 0,
                    'exact accepted private kernel/version required')
        if action in {'status', 'retrieve'}:
            require(provider_identity == accepted and accepted is not None,
                    'exact accepted kernel/version required on every observation')
        elif result != 'accepted':
            require(provider_identity is None, 'provider identity only set at accepted push')

    def reserve(self, action, *, now=None):
        require(action in ACTIONS, 'only private push/status/retrieve actions admitted')
        at = timestamp(now or utc()).isoformat()
        with self._lock():
            state = self.read()
            require(timestamp(at) >= timestamp(state['events'][-1]['at']), 'journal event time moved backwards')
            self._admit(state, action, at)
            next_event = self.root/'events'/f"{state['marker']['sequence']+1:06d}.json"
            if next_event.exists() or next_event.is_symlink():
                raise FileExistsError('uncommitted event requires explicit reconciliation')
            request_id = uuid.uuid4().hex
            event = {'kind': 'reserve', 'at': at, 'action': action, 'request_id': request_id}
            if action == 'push':
                original = Path(state['inputs']['package_source'])
                require(not original.is_symlink() and sha(original.read_bytes()) == state['plan']['package_sha256'],
                        'package source changed since admission')
                self._payload(state)
                with self._campaign_lock():
                    event['campaign_sha256'] = self._campaign_reserve(state, at)
                    self._commit(state['marker'], event)
            else:
                self._commit(state['marker'], event)
        return request_id

    def _payload(self, state):
        path = self.root/'outbound.bin'
        require(not path.is_symlink(), 'regular immutable outbound snapshot required')
        body = path.read_bytes()
        require(sha(body) == state['plan']['package_sha256'], 'immutable outbound snapshot differs')
        return body

    def payload_for_push(self, request_id):
        """Return admitted immutable bytes; transport must send these bytes.

        Never reopen the original mutable path after admission. The returned
        immutable bytes object closes that check/send race for the caller.
        """
        state = self.read()
        require(state['pending'].get(request_id) == 'push', 'pending exact push reservation required')
        return self._payload(state)

    def receipt(self, request_id, result, *, receipt_sha256, provider_identity=None, now=None):
        at = timestamp(now or utc()).isoformat()
        with self._lock():
            state = self.read()
            require(timestamp(at) >= timestamp(state['events'][-1]['at']), 'journal event time moved backwards')
            require(request_id in state['pending'], 'unknown or already completed request')
            action = state['pending'][request_id]
            self._validate_receipt(action, result, receipt_sha256, provider_identity, state['accepted'])
            self._commit(state['marker'], {'kind': 'receipt', 'at': at,
                         'request_id': request_id, 'result': result,
                         'receipt_sha256': receipt_sha256, 'provider_identity': provider_identity})
        return self.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect'])
    parser.add_argument('--ledger', type=Path, required=True)
    args = parser.parse_args()
    state = Ledger(args.ledger).read()
    print(json.dumps({key: state[key] for key in ('counts', 'pending', 'accepted', 'terminal', 'retrieved')}, indent=2))


if __name__ == '__main__':
    main()
