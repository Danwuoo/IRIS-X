"""Explicit callable probe factory; unchanged controller and full training flow.

Public worker admission is denied by require_public_worker_admission. This
module can exercise authored train/dev controls, never claim PUBLIC120 coverage.
"""
from __future__ import annotations
import time
from .qwen14b_profiles import MODEL_KEY, require
from .metering import MeteredModel, MeteredTrainer, _call_window
from .budget import atomic_json


def require_public_worker_admission(model_config):
    if model_config.get('model_key') == MODEL_KEY:
        raise ValueError('Qwen14B profile is probe-only: public solving/scoring denied until independent full-context/coverage admission')


class Qwen14BMeteredModel(MeteredModel):
    """Charge physical native forward tokens, including cached decode steps."""
    def generate(self, messages, *, kind, seed, max_new_tokens, deadline):
        require(type(max_new_tokens) is int and 0 < max_new_tokens <= self.native.output_cap,
                'Qwen14B bounded output cap required')
        deadline, hard = _call_window(deadline)
        event = self._identity('qwen14b-generation')
        # Native Qwen3 supports call-local KV caching. Without a usable cache,
        # conservatively reserve each complete-prefix forward; never undercharge.
        reserve = sum(self.native.prompt_cap + i for i in range(max_new_tokens))
        self.ledger.reserve(event, {'generation_calls': 1, 'input_tokens': reserve, 'output_tokens': max_new_tokens})
        atomic_json(self.ledger.path.parent / 'active-call.json', {'event_id': event, 'status': 'active',
                    'deadline_monotonic': hard, 'work_deadline_monotonic': deadline})
        try:
            result = self.native.generate(messages, kind=kind, seed=seed, max_new_tokens=max_new_tokens, deadline=deadline)
            dispatched = result.get('dispatched')
            require(type(dispatched) is bool, 'native dispatch receipt required')
            actual = {'generation_calls': int(dispatched), 'input_tokens': result['forward_input_tokens'],
                      'output_tokens': result['output_tokens'] if dispatched else 0}
            self.ledger.complete(event, actual, status='complete' if result['valid'] else 'failed' if dispatched else 'excluded')
        except BaseException as exc:
            if event in self.ledger.pending:
                self.ledger.unknown(event, type(exc).__name__)
            raise
        atomic_json(self.ledger.path.parent / 'active-call.json', {'event_id': event, 'status': 'closed',
                    'deadline_monotonic': hard, 'work_deadline_monotonic': deadline})
        return {**result, 'physical_event_id': event}


def create_backend(model_config, trainer_config=None, *, ledger=None):
    """Actual native tiny Qwen3 + real PEFT, on the existing public interfaces."""
    require(model_config.get('model_key') == MODEL_KEY, 'distinct explicit Qwen14B model key required')
    from .qwen14b_model import Qwen14BModel
    from .qwen14b_training import Qwen14BTrainer
    native = Qwen14BModel.from_config(model_config)
    try:
        model = Qwen14BMeteredModel(native, ledger) if ledger is not None else native
        trainer = Qwen14BTrainer(model, trainer_config)
        if ledger is not None:
            trainer = MeteredTrainer(trainer, ledger, max_sequence_tokens=native.context_limit)
        return model, trainer
    except BaseException:
        native.close()
        raise


def create_probe_backend(model_config, trainer_config=None, *, ledger=None):
    require(model_config.get('tiny_cpu') is True, 'explicit tiny CPU fixture required')
    return create_backend(model_config, trainer_config, ledger=ledger)
