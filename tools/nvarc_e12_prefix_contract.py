"""INERT E12 prefix-stop contract and CPU-observable Trainer event controller.

No native/model imports, runner, provider path, or admission publisher exist here.
The callbacks consume observations; they are not an installed native adapter.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import hashlib
import json
import math

from tools.nvarc_native_ttt_schedule import SOURCES, FUNCTIONS, ulp_distance


FORMAT = 'irisx/stage4-e12-prefix-contract-v1'
TRACE_FORMAT = 'irisx/stage4-e12-prefix-trace-v1'
PROFILES = {'E12-TTT64-PREFIX': 64, 'E12-TTT128-CONTROL': 128}
HORIZON = 128
WARMUP = 13
ROW_FIELDS = {'input_ids_digest', 'labels_digest', 'input_tokens', 'supervised_tokens'}
RNG_FIELDS = {'python', 'numpy', 'torch_cpu', 'torch_cuda'}
RESET_FIELDS = {'model_inventory_digest', 'rng', 'optimizer_state_entries', 'gradient_tensor_count'}
SOURCE_FIELDS = {'challenge_digest', 'model_digest', 'dependency_digest', 'configuration_digest',
                 'inference_contract_digest', 'native_sampler_digest'}
CONTRACT_FIELDS = {'format', 'experiment', 'execution_type', 'agent_execution', 'publication',
                   'evidence_kind', 'horizon', 'warmup_steps', 'prepared_rows', 'sampler_order',
                   'learning_rates', 'schedule_source_sha256', 'schedule_function_sha256',
                   'schedule_reference_rates', 'schedule_receipt',
                   'reset', 'sources', 'optimizer_parameter_tensors', 'design',
                   'saved_training_time_reallocation'}
STEP_FIELDS = {'index', 'prepared_index', 'row', 'rng_before', 'rng_after', 'forward_complete',
               'backward_complete', 'optimizer_entered', 'optimizer_complete', 'loss',
               'learning_rates', 'parameter_steps_before', 'parameter_steps_after',
               'scheduler_rates_after', 'callback_complete', 'global_step_after'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(value):
    return 'sha256:' + hashlib.sha256(canonical(value)).hexdigest()


def is_digest(value):
    return (type(value) is str and len(value) == 71 and value.startswith('sha256:') and
            all(c in '0123456789abcdef' for c in value[7:]))


def integer(value, expected=None):
    return type(value) is int and (expected is None or value == expected)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def scalar_reference():
    """CPU mathematical reference, not proof of installed native source execution."""
    rates = []
    for i in range(HORIZON + 1):
        progress = float(i - WARMUP) / float(HORIZON - WARMUP)
        scale = (float(i) / float(WARMUP) if i < WARMUP else
                 max(0., .5 * (1. + math.cos(math.pi * 2. * .5 * progress))))
        rates.append(5e-5 * scale)
    return rates


def validate_rng(value):
    require(type(value) is dict and set(value) == RNG_FIELDS and
            all(is_digest(value[k]) for k in ('python', 'numpy', 'torch_cpu')) and
            type(value['torch_cuda']) is list and 1 <= len(value['torch_cuda']) <= 4 and
            all(is_digest(v) for v in value['torch_cuda']), 'all reset/dropout RNG streams required')


def validate_reset(value):
    require(type(value) is dict and set(value) == RESET_FIELDS and
            is_digest(value['model_inventory_digest']) and
            integer(value['optimizer_state_entries'], 0) and
            integer(value['gradient_tensor_count'], 0), 'fresh model/optimizer/gradient reset required')
    validate_rng(value['rng'])


def row_observation(input_ids, labels):
    require(type(input_ids) is list and type(labels) is list and
            1 <= len(input_ids) == len(labels) <= 8192 and
            all(integer(v) and v >= 0 for v in input_ids) and
            all(integer(v) and (v >= 0 or v == -100) for v in labels),
            'one unpadded exact source token/label row required')
    return dict(input_ids_digest=digest(input_ids), labels_digest=digest(labels),
                input_tokens=len(input_ids), supervised_tokens=sum(v >= 0 for v in labels[1:]))


def validate_row(row):
    require(type(row) is dict and set(row) == ROW_FIELDS and
            all(is_digest(row[k]) for k in ('input_ids_digest', 'labels_digest')) and
            integer(row['input_tokens']) and 1 <= row['input_tokens'] <= 8192 and
            integer(row['supervised_tokens']) and
            0 <= row['supervised_tokens'] < row['input_tokens'], 'closed truth-free source row required')


def validate_contract(contract):
    require(type(contract) is dict and set(contract) == CONTRACT_FIELDS,
            'closed E12 contract required')
    require(contract['format'] == FORMAT and contract['experiment'] == 'E12' and
            contract['execution_type'] == 'INERT' and contract['agent_execution'] is False and
            contract['publication'] is False and contract['evidence_kind'] in {'cpu-synthetic-only', 'native-observed'} and
            contract['design'] == 'separate-reset-runs' and
            contract['saved_training_time_reallocation'] is False,
            'inert separate-reset E12 contract required')
    require(integer(contract['horizon'], HORIZON) and integer(contract['warmup_steps'], WARMUP) and
            contract['schedule_source_sha256'] == SOURCES and
            contract['schedule_function_sha256'] == FUNCTIONS, 'original 128/13 schedule binding required')
    rates = contract['learning_rates']
    require(type(rates) is list and len(rates) == 129 and all(finite(v) and v >= 0 for v in rates),
            'complete original LR sequence required; no 64-step recomputation')
    if contract['evidence_kind'] == 'cpu-synthetic-only':
        require(rates == scalar_reference() and contract['schedule_reference_rates'] == rates and
                contract['schedule_receipt'] is None, 'exact synthetic schedule with no native receipt required')
    else:
        validate_native_schedule(contract)
    rows = contract['prepared_rows']
    require(type(rows) is list and len(rows) == HORIZON, 'all 128 prepared rows required')
    for row in rows:
        validate_row(row)
    order = contract['sampler_order']
    require(type(order) is list and len(order) == HORIZON and all(integer(i) for i in order) and
            sorted(order) == list(range(HORIZON)), 'full 128-row sampler permutation required')
    validate_reset(contract['reset'])
    require(type(contract['sources']) is dict and set(contract['sources']) == SOURCE_FIELDS and
            all(is_digest(v) for v in contract['sources'].values()), 'exact same-source/config bindings required')
    require(integer(contract['optimizer_parameter_tensors'], 506), 'all 506 original native tensors required')
    return contract


def build_contract(*, rows, sampler_order, reset, sources):
    contract = dict(format=FORMAT, experiment='E12', execution_type='INERT', agent_execution=False,
                    publication=False, evidence_kind='cpu-synthetic-only', horizon=HORIZON,
                    warmup_steps=WARMUP, prepared_rows=deepcopy(rows), sampler_order=list(sampler_order),
                    learning_rates=scalar_reference(), schedule_source_sha256=dict(SOURCES),
                    schedule_function_sha256=dict(FUNCTIONS), schedule_reference_rates=scalar_reference(),
                    schedule_receipt=None, reset=deepcopy(reset), sources=dict(sources),
                    optimizer_parameter_tensors=506, design='separate-reset-runs',
                    saved_training_time_reallocation=False)
    return validate_contract(contract)


def validate_native_schedule(contract):
    """Verify the unchanged native scalar replay receipt, not native model provenance."""
    rates, reference, receipt = (contract[k] for k in
                                 ('learning_rates', 'schedule_reference_rates', 'schedule_receipt'))
    fields = {'source_sha256', 'function_sha256', 'warmup_steps', 'epoch_steps', 'rates',
              'reference_rates_sha256', 'reference_ulp_distances', 'maximum_reference_ulp_distance',
              'platform', 'python', 'model_calls', 'optimizer_steps', 'policy'}
    require(type(reference) is list and len(reference) == 129 and
            all(finite(v) and v >= 0 for v in reference) and
            rates[0] == rates[-1] == 0 and rates[13] == 5e-5 and
            max(ulp_distance(a, b) for a, b in zip(reference, scalar_reference())) <= 4 and
            max(ulp_distance(a, b) for a, b in zip(rates, scalar_reference())) <= 4,
            'original full native schedule reference within four ULPs required')
    distances = [ulp_distance(a, b) for a, b in zip(rates, reference)]
    require(type(receipt) is dict and set(receipt) == fields and receipt['source_sha256'] == SOURCES and
            receipt['function_sha256'] == FUNCTIONS and type(receipt['rates']) is list and
            all(finite(v) for v in receipt['rates']) and receipt['rates'] == rates and
            integer(receipt['warmup_steps'], WARMUP) and integer(receipt['epoch_steps'], HORIZON) and
            integer(receipt['model_calls'], 0) and integer(receipt['optimizer_steps'], 0) and
            receipt['reference_rates_sha256'] == hashlib.sha256(
                json.dumps(reference, separators=(',', ':')).encode()).hexdigest() and
            receipt['reference_ulp_distances'] == distances and
            all(integer(v) for v in receipt['reference_ulp_distances']) and
            integer(receipt['maximum_reference_ulp_distance'], max(distances)) and max(distances) <= 4 and
            all(type(receipt[k]) is str and bool(receipt[k]) for k in ('platform', 'python')) and
            receipt['policy'] == 'optimizer rate must exactly equal same-platform pinned scalar replay; reference differs by at most four ULPs',
            'exact source-verified native scalar schedule receipt required')


def build_native_contract(*, rows, sampler_order, reset, sources, rates, reference_rates, schedule_receipt):
    """A declarative native-observation contract; this grants no execution admission.

    Call only with the existing native_schedule return and exact package reference.
    Runtime/model/source provenance must independently qualify in the native adapter.
    """
    contract = build_contract(rows=rows, sampler_order=sampler_order, reset=reset, sources=sources)
    contract.update(evidence_kind='native-observed', learning_rates=list(rates),
                    schedule_reference_rates=list(reference_rates), schedule_receipt=deepcopy(schedule_receipt))
    return validate_contract(contract)


def validate_trainer(args, state):
    require(integer(args.max_steps, -1) and finite(args.num_train_epochs) and args.num_train_epochs == 1 and
            integer(args.gradient_accumulation_steps, 1) and
            integer(args.per_device_train_batch_size, 1) and
            args.learning_rate == 5e-5 and args.warmup_ratio == .1 and
            integer(args.warmup_steps, 0) and args.lr_scheduler_type == 'cosine' and
            args.adam_beta1 == .9 and args.adam_beta2 == .999 and args.adam_epsilon == 1e-8 and
            args.weight_decay == 0 and args.max_grad_norm == 1 and
            integer(state.max_steps, HORIZON),
            'unchanged one-epoch Trainer with derived max_steps=128 required')


def guarded(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        require(not self.errors, 'controller already failed; no recovery into qualification')
        try:
            return method(self, *args, **kwargs)
        except Exception as error:
            self.errors.append({'operation': method.__name__, 'error': str(error)})
            raise
    return wrapped


class PrefixStopController:
    """Observe actual row/update calls; request stop only at post-update callback.

    A native adapter must call these methods from guarded actual operations. Passing
    invented values cannot establish native provenance. Every rejection is sticky.
    """
    def __init__(self, contract, profile):
        self.contract = deepcopy(validate_contract(contract))
        require(profile in PROFILES, 'distinct E12 64-prefix or 128-control profile required')
        self.profile, self.limit = profile, PROFILES[profile]
        self.steps, self.errors = [], []
        self.started = self.finished = False
        self.reset = self.final_reset = None
        self.trainer_end = None

    @guarded
    def start(self, args, state, reset):
        require(not self.started and integer(state.global_step, 0), 'fresh Trainer global_step zero required')
        validate_trainer(args, state)
        validate_reset(reset)
        require(reset == self.contract['reset'], 'exact model/optimizer/all-RNG reset binding required')
        self.reset, self.started = deepcopy(reset), True

    @guarded
    def begin_step(self, global_step, input_ids, labels, rng_before):
        i = len(self.steps)
        require(self.started and not self.finished and i < self.limit and integer(global_step, i) and
                (not self.steps or self.steps[-1]['callback_complete']),
                'one ordered step permitted; no entry beyond completed stop target')
        row = row_observation(input_ids, labels)
        index = self.contract['sampler_order'][i]
        require(row == self.contract['prepared_rows'][index], 'actual row differs from original full sampler prefix')
        validate_rng(rng_before)
        self.steps.append(dict(index=i, prepared_index=index, row=row, rng_before=deepcopy(rng_before),
                               rng_after=None, forward_complete=False, backward_complete=False,
                               optimizer_entered=False, optimizer_complete=False, loss=None,
                               learning_rates=None, parameter_steps_before=None, parameter_steps_after=None,
                               scheduler_rates_after=None, callback_complete=False, global_step_after=None))

    def current(self):
        require(self.steps and not self.steps[-1]['callback_complete'], 'active step required')
        return self.steps[-1]

    @guarded
    def forward_return(self, loss):
        row = self.current()
        require(not row['forward_complete'] and finite(loss), 'one returned finite forward required')
        row.update(forward_complete=True, loss=loss)

    @guarded
    def backward_return(self, rng_after):
        row = self.current()
        require(row['forward_complete'] and not row['backward_complete'], 'successful backward after forward required')
        validate_rng(rng_after)
        row.update(backward_complete=True, rng_after=deepcopy(rng_after))

    def check_steps(self, values, expected):
        require(type(values) is list and len(values) == self.contract['optimizer_parameter_tensors'] and
                all(integer(v, expected) for v in values), 'all Adam moment step counters must be known and exact')

    def check_rates(self, values, index):
        require(type(values) is list and len(values) > 0 and
                all(finite(v) and v == self.contract['learning_rates'][index] for v in values),
                'every actual optimizer group must use the original LR prefix')

    @guarded
    def optimizer_enter(self, learning_rates, parameter_steps):
        row = self.current()
        require(row['backward_complete'] and not row['optimizer_entered'], 'completed backward before optimizer required')
        self.check_steps(parameter_steps, row['index'])
        self.check_rates(learning_rates, row['index'])
        row.update(optimizer_entered=True, learning_rates=list(learning_rates),
                   parameter_steps_before=list(parameter_steps))

    @guarded
    def optimizer_return(self, parameter_steps):
        row = self.current()
        require(row['optimizer_entered'] and not row['optimizer_complete'], 'actual optimizer return required')
        self.check_steps(parameter_steps, row['index'] + 1)
        row.update(optimizer_complete=True, parameter_steps_after=list(parameter_steps))

    @guarded
    def scheduler_return(self, learning_rates):
        row = self.current()
        require(row['optimizer_complete'] and row['scheduler_rates_after'] is None,
                'one scheduler step after completed optimizer update required')
        self.check_rates(learning_rates, row['index'] + 1)
        row['scheduler_rates_after'] = list(learning_rates)

    @guarded
    def on_step_end(self, args, state, control, **kwargs):
        validate_trainer(args, state)
        row = self.current()
        count = row['index'] + 1
        require(row['optimizer_complete'] and row['scheduler_rates_after'] is not None and
                integer(state.global_step, count) and type(control.should_training_stop) is bool,
                'post-optimizer/scheduler exact Trainer global_step required')
        require(not control.should_training_stop or count == self.limit, 'external early stop invalidates comparison')
        row.update(callback_complete=True, global_step_after=state.global_step)
        if count == self.limit:
            control.should_training_stop = True
        return control

    @guarded
    def finish(self, args, state, control, final_reset):
        validate_trainer(args, state)
        validate_reset(final_reset)
        require(not self.finished and len(self.steps) == self.limit and
                self.steps[-1]['callback_complete'] and integer(state.global_step, self.limit) and
                finite(state.epoch) and state.epoch == self.limit / HORIZON and
                control.should_training_stop is True and final_reset == self.contract['reset'],
                'exact completed prefix and post-run model/optimizer/all-RNG restoration required')
        self.final_reset, self.finished = deepcopy(final_reset), True
        self.trainer_end = dict(global_step=state.global_step, max_steps=state.max_steps, epoch=state.epoch,
                                should_training_stop=control.should_training_stop)
        result = self.snapshot()
        validate_trace(self.contract, result)
        return result

    def fail(self, operation, error):
        """The adapter records thrown forward/backward/optimizer calls before cleanup."""
        self.errors.append({'operation': str(operation), 'error': str(error)})

    def snapshot(self):
        return deepcopy(dict(format=TRACE_FORMAT, contract_digest=digest(self.contract), profile=self.profile,
                             evidence_kind=self.contract['evidence_kind'], reset=self.reset, final_reset=self.final_reset,
                             steps=self.steps, errors=self.errors, complete=self.finished,
                             trainer_end=self.trainer_end, native_runtime_verified=False, promotion=False))


def validate_trace(contract, trace):
    """Direct ledger checks independent of the controller's mutable lifecycle."""
    validate_contract(contract)
    fields = {'format', 'contract_digest', 'profile', 'evidence_kind', 'reset', 'final_reset', 'steps',
              'errors', 'complete', 'trainer_end', 'native_runtime_verified', 'promotion'}
    require(type(trace) is dict and set(trace) == fields and trace['format'] == TRACE_FORMAT and
            trace['contract_digest'] == digest(contract) and trace['profile'] in PROFILES and
            trace['evidence_kind'] == contract['evidence_kind'] and trace['errors'] == [] and
            trace['complete'] is True and trace['native_runtime_verified'] is False and
            trace['promotion'] is False, 'complete inert CPU trace without errors required')
    require(trace['reset'] == trace['final_reset'] == contract['reset'], 'both independent resets must match')
    validate_reset(trace['reset'])
    validate_reset(trace['final_reset'])
    steps = trace['steps']
    require(type(steps) is list and len(steps) == PROFILES[trace['profile']], 'exact declared prefix length required')
    end = trace['trainer_end']
    require(type(end) is dict and set(end) == {'global_step', 'max_steps', 'epoch', 'should_training_stop'} and
            integer(end['global_step'], len(steps)) and integer(end['max_steps'], HORIZON) and
            finite(end['epoch']) and end['epoch'] == len(steps) / HORIZON and
            end['should_training_stop'] is True, 'exact terminal Trainer state required')
    for i, row in enumerate(steps):
        require(type(row) is dict and set(row) == STEP_FIELDS and integer(row['index'], i) and
                integer(row['prepared_index'], contract['sampler_order'][i]) and
                integer(row['global_step_after'], i + 1) and
                row['row'] == contract['prepared_rows'][contract['sampler_order'][i]] and
                all(row[k] is True for k in ('forward_complete', 'backward_complete', 'optimizer_entered',
                                             'optimizer_complete', 'callback_complete')) and finite(row['loss']),
                'ordered actual source row and fully completed update required')
        validate_row(row['row'])
        validate_rng(row['rng_before'])
        validate_rng(row['rng_after'])
        for key, value in (('parameter_steps_before', i), ('parameter_steps_after', i + 1)):
            require(type(row[key]) is list and len(row[key]) == contract['optimizer_parameter_tensors'] and
                    all(integer(v, value) for v in row[key]), 'unknown/skipped optimizer moment update')
        for key, index in (('learning_rates', i), ('scheduler_rates_after', i + 1)):
            require(type(row[key]) is list and row[key] and
                    all(finite(v) and v == contract['learning_rates'][index] for v in row[key]),
                    'actual original optimizer/scheduler LR required')
    return True


def validate_pair(contract, short, control):
    validate_trace(contract, short)
    validate_trace(contract, control)
    require(short['profile'] == 'E12-TTT64-PREFIX' and control['profile'] == 'E12-TTT128-CONTROL',
            '64 versus 128 E12 profiles required')
    short_prefix, control_prefix = short['steps'], control['steps'][:64]
    if contract['evidence_kind'] == 'native-observed':
        # Separate CUDA runs need not produce bitwise-equal finite losses. This
        # compares the causal input/update contract, not numerical model output.
        short_structure = [{k: v for k, v in row.items() if k != 'loss'} for row in short_prefix]
        control_structure = [{k: v for k, v in row.items() if k != 'loss'} for row in control_prefix]
        require(short_structure == control_structure,
                'first 64 actual rows/LRs/backwards/optimizer counters/dropout RNG must match exactly')
    else:
        require(short_prefix == control_prefix,
                'first 64 synthetic rows/LRs/backwards/optimizer counters/losses/dropout RNG must match exactly')
    losses_equal = all(a['loss'] == b['loss'] for a, b in zip(short_prefix, control_prefix))
    max_difference = max(abs(a['loss'] - b['loss']) for a, b in zip(short_prefix, control_prefix))
    return dict(prefix_verified=True, completed_updates=[64, 128], schedule_horizon=128, warmup_steps=13,
                numerical_losses_equal=losses_equal,
                max_absolute_loss_difference=max_difference if math.isfinite(max_difference) else None,
                numerical_loss_difference_overflow=not math.isfinite(max_difference),
                native_runtime_verified=False, total_cost_reduction=None, quality_delta=None, promotion=False)


def compare_costs(short, control):
    """Accept only complete separately metered session costs, including all overhead."""
    fields = {'meter_definition', 'allocation_gpu_count', 'session_seconds', 'complete_session_observed',
              'includes_startup_reset_inference_finalization', 'includes_instrumentation_checkpoint',
              'separate_reset_run'}
    for value in (short, control):
        require(type(value) is dict and set(value) == fields and
                type(value['meter_definition']) is str and bool(value['meter_definition']) and
                integer(value['allocation_gpu_count']) and value['allocation_gpu_count'] > 0 and
                finite(value['session_seconds']) and value['session_seconds'] > 0 and
                all(value[k] is True for k in ('complete_session_observed',
                    'includes_startup_reset_inference_finalization', 'includes_instrumentation_checkpoint',
                    'separate_reset_run')), 'complete independent end-to-end allocation meter required')
    require(short['meter_definition'] == control['meter_definition'] and
            short['allocation_gpu_count'] == control['allocation_gpu_count'], 'identical cost meter/allocation required')
    reduction = 1 - short['session_seconds'] / control['session_seconds']
    return dict(observed_allocated_gpu_seconds=[v['allocation_gpu_count'] * v['session_seconds']
                                               for v in (short, control)], reduction_fraction=reduction,
                cost_gate_passed=reduction >= .25, quality_gate_evaluated=False, promotion=False)
