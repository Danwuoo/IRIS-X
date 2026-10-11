"""One shared physical-call meter across policy views and training phases."""
from __future__ import annotations

import time
import math
from tools.arc_learning_agent_20261011.budget import atomic_json

from tools.arc_learning_agent_20261011.budget import BudgetExceeded


def _call_window(deadline):
    if type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError('finite call deadline required')
    now = time.monotonic()
    hard = min(deadline, now + 120)
    if hard <= now:
        raise BudgetExceeded('no time for new model work')
    return hard - min(5.0, (hard - now) * 0.1), hard


class MeteredModel:
    def __init__(self, native, ledger):
        self.native = native; self.ledger = ledger; self._counter = 0

    @property
    def model(self): return self.native.model
    @model.setter
    def model(self, value): self.native.model = value
    @property
    def tokenizer(self): return self.native.tokenizer
    @property
    def adapter_state_sha256(self): return self.native.adapter_state_sha256
    @adapter_state_sha256.setter
    def adapter_state_sha256(self, value): self.native.adapter_state_sha256 = value
    def __getattr__(self, key): return getattr(self.native, key)

    def _identity(self, prefix):
        self._counter += 1
        return prefix + '-' + str(self._counter)

    def generate(self, messages, *, kind, seed, max_new_tokens, deadline):
        if type(max_new_tokens) is not int or not 1 <= max_new_tokens <= 2048:
            raise ValueError('bounded generation required')
        deadline, hard_deadline = _call_window(deadline)
        event = self._identity('generation')
        self.ledger.reserve(event, {'generation_calls': 1, 'input_tokens': 6144,
                                    'output_tokens': max_new_tokens})
        atomic_json(self.ledger.path.parent / 'active-call.json', {'event_id': event, 'status': 'active', 'deadline_monotonic': hard_deadline, 'work_deadline_monotonic': deadline})
        try:
            result = self.native.generate(messages, kind=kind, seed=seed,
                                          max_new_tokens=max_new_tokens, deadline=deadline)
            dispatched = result.get('dispatched', result.get('model_forward_started'))
            if type(dispatched) is not bool: raise ValueError('dispatch receipt required')
            actual = {'generation_calls': int(dispatched),
                      'input_tokens': result['input_tokens'] if dispatched else 0,
                      'output_tokens': result['output_tokens'] if dispatched else 0}
            self.ledger.complete(event, actual, status='complete' if result['valid'] else
                                 ('failed' if dispatched else 'excluded'))
        except BaseException as exc:
            if event in self.ledger.pending: self.ledger.unknown(event, type(exc).__name__)
            raise
        atomic_json(self.ledger.path.parent / 'active-call.json', {'event_id': event, 'status': 'closed', 'deadline_monotonic': hard_deadline, 'work_deadline_monotonic': deadline})
        return {**result, 'physical_event_id': event}

    def score_completion(self, messages, completion, *, deadline):
        deadline, hard_deadline = _call_window(deadline)
        event = self._identity('likelihood')
        self.ledger.reserve(event, {'scoring_forwards': 1, 'input_tokens': 8192})
        atomic_json(self.ledger.path.parent / 'active-call.json', {'event_id': event, 'status': 'active', 'deadline_monotonic': hard_deadline, 'work_deadline_monotonic': deadline})
        try:
            result = self.native.score_completion(messages, completion, deadline=deadline)
            dispatched = result.get('dispatched', result.get('model_forward_started'))
            if type(dispatched) is not bool: raise ValueError('dispatch receipt required')
            actual = {'scoring_forwards': int(dispatched),
                      'input_tokens': result['input_tokens'] if dispatched else 0}
            self.ledger.complete(event, actual, status='complete' if result['valid'] else
                                 ('failed' if dispatched else 'excluded'))
        except BaseException as exc:
            if event in self.ledger.pending: self.ledger.unknown(event, type(exc).__name__)
            raise
        atomic_json(self.ledger.path.parent / 'active-call.json', {'event_id': event, 'status': 'closed', 'deadline_monotonic': hard_deadline, 'work_deadline_monotonic': deadline})
        return {**result, 'physical_event_id': event}

    def close(self): return self.native.close()


class TrainingStageFailed(RuntimeError):
    """Known attempted training work ended without a valid optimizer boundary."""


class MeteredTrainer:
    def __init__(self, trainer, ledger, *, max_sequence_tokens=8192):
        self.trainer = trainer; self.ledger = ledger; self._counter = 0
        self.max_sequence_tokens = max_sequence_tokens
        self.completed_optimizer_steps = 0
        self.training_receipts = []

    def __getattr__(self, key): return getattr(self.trainer, key)

    def _run(self, operation, *args, max_steps, **kwargs):
        if type(max_steps) is not int or max_steps < 0:
            raise ValueError('bounded integer optimizer steps required')
        remaining_steps = self.ledger.caps['training_steps'] - self.ledger.used['training_steps']
        remaining_tokens = self.ledger.caps['input_tokens'] - self.ledger.used['input_tokens']
        admitted_steps = min(max_steps, remaining_steps, remaining_tokens // self.max_sequence_tokens)
        if admitted_steps <= 0:
            return {'status': 'not_admitted', 'optimizer_steps': 0, 'steps': 0,
                    'input_tokens': 0, 'supervised_tokens': 0, 'elapsed_seconds': 0,
                    'reason': 'physical training budget exhausted'}
        self._counter += 1; event = 'training-' + str(self._counter)
        self.ledger.reserve(event, {'training_steps': admitted_steps,
                                    'input_tokens': admitted_steps * self.max_sequence_tokens})
        try:
            result = getattr(self.trainer, operation)(*args, max_steps=admitted_steps, **kwargs)
            self.completed_optimizer_steps += result.get('optimizer_steps', result.get('steps', 0))
            self.training_receipts.append(result)
            failed = result.get('status') in ('failed', 'error', 'failed_update') or result.get('usage_known') is False
            actual = {'training_steps': result.get('attempted_microbatches', result.get('optimizer_steps', result.get('steps'))),
                      'input_tokens': result['input_tokens']}
            self.ledger.complete(event, actual, status='failed' if failed else 'complete')
            if failed:
                error = TrainingStageFailed('failed optimizer boundary; dependent inference forbidden')
                error.receipt = result
                raise error
        except BaseException as exc:
            if event in self.ledger.pending: self.ledger.unknown(event, type(exc).__name__)
            raise
        return {**result, 'physical_event_id': event, 'requested_steps': max_steps,
                'admitted_steps': admitted_steps}

    def train(self, records, *, max_steps, **kwargs):
        return self._run('train', records, max_steps=max_steps, **kwargs)

    def adapt_task(self, task_id, demos, *, max_steps, **kwargs):
        return self._run('adapt_task', task_id, demos, max_steps=max_steps, **kwargs)
