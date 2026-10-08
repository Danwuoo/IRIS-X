"""Deterministic, independent-reviewable E12 fake Trainer fixture; no ML imports."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.nvarc_e12_prefix_contract import (SOURCE_FIELDS, PrefixStopController, build_contract,
    digest, row_observation, validate_pair)


def rng_observation(rng):
    """Four labeled mock streams; these are never represented as actual CUDA state."""
    state = rng.getstate()
    return dict(python=digest(['python', state]), numpy=digest(['numpy-mock', state]),
                torch_cpu=digest(['torch-cpu-mock', state]),
                torch_cuda=[digest(['torch-cuda-mock', state])])


def fixture_inputs():
    tokens = [{'input_ids': [1, i + 3, 2], 'labels': [-100, i + 3, 2]} for i in range(128)]
    order = list(range(128))
    random.Random(818).shuffle(order)
    reset = dict(model_inventory_digest=digest('synthetic baseline'), rng=rng_observation(random.Random(7)),
                 optimizer_state_entries=0, gradient_tensor_count=0)
    contract = build_contract(rows=[row_observation(**v) for v in tokens], sampler_order=order,
                              reset=reset, sources={k: digest(['synthetic-only', k]) for k in SOURCE_FIELDS})
    return contract, tokens


def trainer_args():
    return SimpleNamespace(max_steps=-1, num_train_epochs=1, gradient_accumulation_steps=1,
                           per_device_train_batch_size=1, learning_rate=5e-5, warmup_ratio=.1,
                           warmup_steps=0, lr_scheduler_type='cosine', adam_beta1=.9, adam_beta2=.999,
                           adam_epsilon=1e-8, weight_decay=0, max_grad_norm=1)


class FakeTrainer:
    """Separately initialized scalar weight, dropout RNG and 506 mock Adam counters.

    This intentionally implements the callback lifecycle itself. It neither imports
    transformers nor claims its callback ordering, gradient clipping, or native parity.
    """
    def __init__(self, contract, tokens, profile):
        self.contract, self.tokens = deepcopy(contract), deepcopy(tokens)
        self.args = trainer_args()
        self.state = SimpleNamespace(global_step=0, max_steps=128, epoch=0.)
        self.control = SimpleNamespace(should_training_stop=False)
        self.controller = PrefixStopController(contract, profile)
        self.rng = random.Random(7)
        self.parameter_steps = [0] * 506
        self.weight, self.moment = 1., 0.
        self.actual_forward_calls = self.actual_optimizer_calls = 0
        self.weight_after_zero_lr = None

    def run(self, *, rows=None, rates=None, fail_backward_at=None, skip_callback_stop=False):
        c = self.controller
        rates = self.contract['learning_rates'] if rates is None else rates
        order = self.contract['sampler_order'] if rows is None else rows
        try:
            c.start(self.args, self.state, self.contract['reset'])
            for i, index in enumerate(order):
                c.begin_step(self.state.global_step, **self.tokens[index], rng_before=rng_observation(self.rng))
                self.actual_forward_calls += 1
                dropout = self.rng.random()
                loss = self.weight * (self.tokens[index]['input_ids'][1] + dropout)
                c.forward_return(loss)
                if fail_backward_at == i:
                    raise RuntimeError('synthetic backward failed')
                self.moment = .9 * self.moment + .1 * loss
                c.backward_return(rng_observation(self.rng))
                c.optimizer_enter([rates[i]], self.parameter_steps)
                self.actual_optimizer_calls += 1
                self.weight -= rates[i] * self.moment
                self.parameter_steps = [v + 1 for v in self.parameter_steps]
                c.optimizer_return(self.parameter_steps)
                if i == 0:
                    self.weight_after_zero_lr = self.weight
                c.scheduler_return([rates[i + 1]])
                self.state.global_step += 1
                self.state.epoch = self.state.global_step / 128
                c.on_step_end(self.args, self.state, self.control)
                if self.control.should_training_stop and not skip_callback_stop:
                    break
            # Mock actual cleanup restores baseline, all RNG streams and empty state.
            self.weight, self.moment = 1., 0.
            self.parameter_steps = []
            self.rng = random.Random(7)
            restored = dict(model_inventory_digest=digest('synthetic baseline'),
                            rng=rng_observation(self.rng), optimizer_state_entries=len(self.parameter_steps),
                            gradient_tensor_count=0)
            return c.finish(self.args, self.state, self.control, restored)
        except Exception as error:
            c.fail('fake_trainer', error)
            raise


def paired_fixture():
    contract, tokens = fixture_inputs()
    short = FakeTrainer(contract, tokens, 'E12-TTT64-PREFIX').run()
    control = FakeTrainer(contract, tokens, 'E12-TTT128-CONTROL').run()
    return dict(contract=contract, short=short, control=control,
                validation=validate_pair(contract, short, control))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = paired_fixture()
    # Exclusive creation avoids replacing retained evidence.
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, sort_keys=True, separators=(',', ':'), allow_nan=False)
    print(json.dumps(result['validation'], sort_keys=True))


if __name__ == '__main__':
    main()
