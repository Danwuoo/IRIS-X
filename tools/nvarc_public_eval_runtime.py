"""Persistent original-model public worker. Heavy imports occur only in worker startup."""
from __future__ import annotations
import argparse
import importlib.metadata
import inspect
import json
import math
import os
import signal
from pathlib import Path
import sys
import time
from contextlib import nullcontext
from types import ModuleType
from typing import Any, Union

from tools.nvarc_public_eval import task_binding, empty_tests, validate_record, install_owner_guard, PhaseTelemetry, MailboxReader
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import write, digest, require, public_training_material, solve_test, training_deadline
from tools.nvarc_native_solve_runtime import (SourceModel, InferenceLimitReached,
    load_sources, cache_controls, reset_control, discard_optimizer_state)


class LightModel(SourceModel):
    """Keep actual verifier NLLs/bindings, never the full generation-logit stream."""
    def __init__(self, *args, per_test_limits, **kwargs):
        super().__init__(*args, **kwargs)
        self.per_test_limits = per_test_limits; self.test_start_counts = None
        self.verification_rows = None; self.observed = {}
        self.verification_deadline = None
        self.telemetry = None

    def __call__(self, *, input_ids, **kwargs):
        phase = self.active
        if phase != 'control' and self.test_start_counts is not None:
            counts, tokens = self.test_start_counts
            if self.reserved[phase]-counts[phase] >= self.per_test_limits[phase]:
                raise InferenceLimitReached('forward_limit')
            if self.input_tokens-tokens+input_ids.numel() > self.per_test_limits['input_tokens']:
                raise InferenceLimitReached('input_token_limit')
        rows = self.verification_rows
        if phase == 'verification':
            require(rows is not None and len(rows) == 4, 'actual verifier rows required')
            padded = [r['query_ids']+r['answer_ids'] for r in rows]; width = max(map(len, padded))
            require(input_ids.tolist() == [r+[13]*(width-len(r)) for r in padded], 'actual verifier input differs')
        search_deadline = self.generation_deadline
        try:
            if phase == 'verification' and self.verification_deadline is not None:
                self.generation_deadline = self.verification_deadline
            value = super().__call__(input_ids=input_ids, **kwargs)
        finally:
            self.generation_deadline = search_deadline
        if phase == 'verification':
            detail = nullcontext() if self.telemetry is None else self.telemetry.detail('verifier_readback')
            with detail:
                logits = value.logits.float().cpu().log_softmax(-1); observed = []
                for n, row in enumerate(rows):
                    start = len(row['query_ids'])-1; answer = row['answer_ids']
                    score = -logits[n, start:start+len(answer)][self.torch.arange(len(answer)), answer].sum().item()
                    observed.append({'source_view': row['source_view'], 'query_digest': digest(row['query_ids']),
                        'answer_digest': digest(answer), 'score': score})
            self.observed[sum(self.reserved.values())] = observed
        return value


def solve_all_tests(plan, challenges, key, solve, checkpoint, record, *, now=time.time, deadline=math.inf):
    """A planned deadline on test zero must not skip another real test."""
    for index in range(len(record['tests'])):
        if now() >= deadline: break
        try:
            record['tests'][index] = solve(index, min(deadline, now()+plan['per_test_seconds']))
        except InferenceLimitReached as error:
            record['tests'][index].update(status='budget_stop', termination_reason=error.reason)
        checkpoint(record)
    return record


def restore_task_state(engine, trainer, budget, adapter, before):
    """Always clear optimizer state before restoring every saved tensor."""
    if trainer is not None: discard_optimizer_state(engine.model, trainer, budget)
    engine.restore()
    engine.inference()
    require(engine.inventory() == engine.baseline, 'complete saved tensor restoration differs')
    reset = reset_control(adapter, before)
    if trainer is not None:
        require(trainer.optimizer is trainer.lr_scheduler is None and
            not trainer.accelerator._optimizers and not trainer.accelerator._schedulers and
            all(p.grad is None for p in engine.model.parameters()), 'optimizer/gradient state survived cleanup')
    return reset


class NativeEngine:
    def __init__(self, root, plan, model_path, dependency, rank):
        self.root, self.plan, self.rank, self.dependency = root, plan, rank, dependency
        sys.path.insert(0, str(dependency))
        require({k: importlib.metadata.version(k) for k in plan['versions']} == plan['versions'],
                'pinned native distributions differ')
        import torch
        require(torch.__version__ == '2.8.0+cu128' and torch.version.cuda == '12.8' and
            Path(torch.__file__).resolve().is_relative_to(dependency.resolve()) and
            torch.cuda.device_count() == 1 and torch.cuda.get_device_name(0) == 'NVIDIA L4',
            'exact single-L4 native runtime required')
        from hardware_helpers import normalize_gpu_uuid
        self.uuid = normalize_gpu_uuid(str(torch.cuda.get_device_properties(0).uuid))
        hardware = json.loads((root/'hardware.json').read_bytes())['inventory']
        require(self.uuid == hardware[rank]['uuid'], 'assigned actual L4 UUID differs')
        import numpy as np
        from inspection_helpers import (zero_work_guard, original_definitions, source_snapshot,
            tensor_inventory, prepared_evidence)
        self.torch, self.np = torch, np
        self.tensor_inventory, self.prepared_evidence = tensor_inventory, prepared_evidence
        blocked = []
        with zero_work_guard(torch, blocked.append) as guard:
            from unsloth import FastLanguageModel, UnslothTrainer, UnslothTrainingArguments
            from transformers import DataCollatorForLanguageModeling
            from peft import get_peft_model_state_dict, set_peft_model_state_dict
            from datasets import Dataset
            guard()
            namespace = ModuleType('irisx_verified_original_solver'); namespace.__file__ = str(root/'solver.py')
            sys.modules[namespace.__name__] = namespace
            namespace.__dict__.update(UnslothTrainer=UnslothTrainer, DataCollatorForLanguageModeling=DataCollatorForLanguageModeling,
                np=np, torch=torch, Any=Any, Union=Union)
            tree = original_definitions((root/'solver.py').read_text(encoding='utf-8'), namespace.__dict__, plan['original_class_ast_sha256'])
            model, tokenizer = FastLanguageModel.from_pretrained(model_name=str(model_path), full_finetuning=False,
                load_in_4bit=False, local_files_only=True, use_gradient_checkpointing=False, max_seq_length=8192)
            model = FastLanguageModel.get_peft_model(model, **plan['original_peft_parameters'])
            for parameter in model.parameters():
                if parameter.dtype == torch.float32: parameter.data = parameter.data.to(torch.bfloat16)
            guard()
            layout = {name: list(p.shape) for name, p in model.named_parameters() if p.requires_grad}
            require(layout == plan['source_inferred_trainable_layout'] and
                sum(p.numel() for p in model.parameters() if p.requires_grad) == 528564224 and
                all(p.dtype == torch.bfloat16 for p in model.parameters() if p.requires_grad), 'original native trainable layout required')
            raw = get_peft_model_state_dict(model, adapter_name='default')
            defaults = source_snapshot(tree, raw)
            require(all(defaults[k].data_ptr() != raw[k].data_ptr() and not defaults[k].requires_grad for k in defaults),
                    'independent detached source snapshot required')
            baseline = tensor_inventory(defaults, torch)
        require(not blocked, 'unexpected model work during preparation')
        self.model, self.tokenizer, self.defaults, self.baseline = model, tokenizer, defaults, baseline
        self.get_state, self.set_state, self.fast, self.args_type, self.dataset_type = (
            get_peft_model_state_dict, set_peft_model_state_dict, FastLanguageModel, UnslothTrainingArguments, Dataset)
        self.namespace = namespace
        self.loader, self.solver, self.decoder = load_sources(root, torch, np)
        self.inference()
        warm = self.adapter(lambda *_a, **_k: None)
        self.initial_control = cache_controls(warm)
        write(root/'workers'/str(rank)/'ready.json', {'rank': rank, 'uuid': self.uuid,
            'model_material_digest': plan['model_material_digest'], 'baseline_digest': digest(baseline),
            'torch': torch.__version__, 'initial_control_forwards': warm.completed})

    def inference(self): self.fast.for_inference(self.model)
    def inventory(self): return self.tensor_inventory(self.get_state(self.model, adapter_name='default'), self.torch)
    def restore(self): self.set_state(self.model, self.defaults.copy(), adapter_name='default')

    def adapter(self, emit, tests=1):
        return LightModel(self.model, self.torch, emit,
            forward_limits={'control': 7, 'generation': tests*4096, 'verification': tests*128},
            input_token_limit=tests*5242880, generation_deadline=0,
            per_test_limits={'generation': 4096, 'verification': 128, 'input_tokens': 5242880})

    def trainer(self, texts, rows, output):
        self.fast.for_training(self.model)
        collator = self.namespace.QwenDataCollatorForCompletionOnlyLM(tokenizer=self.tokenizer, mlm=False)
        args = self.args_type(**self.plan['original_training_arguments'])
        trainer = self.namespace.UnslothFixedTrainer(model=self.model, tokenizer=self.tokenizer, data_collator=collator,
            train_dataset=self.dataset_type.from_list(texts), dataset_text_field='text', max_seq_length=8192, args=args)
        require(trainer.optimizer is None and trainer.args.max_steps == -1 and
            trainer.args.max_length == trainer.args.max_seq_length == 8192 and not trainer.args.torch_compile and
            trainer.args.adam_beta1 == .9 and trainer.args.adam_beta2 == .999 and trainer.args.adam_epsilon == 1e-8,
            'unchanged original full-epoch Trainer arguments required')
        prepared = self.prepared_evidence(trainer, collator, rows)
        require(all(r['source_input_ids_equal'] and r['source_labels_equal'] and r['collator_preserved_input_ids'] for r in prepared),
                'all full native source rows/labels required')
        write(output/'prepared-rows.json', prepared)
        flags = [{'module': name, 'value': module.gradient_checkpointing} for name, module in self.model.named_modules()
                 if hasattr(module, 'gradient_checkpointing')]
        require(flags == self.plan['native_checkpoint_flags'], 'original native checkpoint flags required')
        origins = []
        for cls in type(trainer).__mro__:
            try: path = inspect.getsourcefile(cls)
            except TypeError: path = None
            if path is not None and Path(path).is_file():
                from tools.nvarc_public_eval import sha
                origins.append({'class': cls.__name__, 'module': cls.__module__, 'source_sha256': sha(path)})
        require(origins == self.plan['native_trainer_origins'], 'original native Trainer implementations differ')
        write(output/'preparation.json', {'checkpoint_flags': flags, 'trainer_origins': origins})
        return trainer


def run_one_task(engine, plan, challenges, key, output, solve_deadline, *, detailed_profiling=False):
    """One task; no optimizer/model reload reuse, retry or answer IO."""
    output.mkdir(exist_ok=False); started = time.monotonic(); trainer = budget = before = None
    telemetry = PhaseTelemetry(detailed=detailed_profiling)
    record = {'binding': task_binding(plan, challenges, key), 'baseline_verified': False,
        'training_complete': False, 'training_steps': 0, 'reset_verified': None,
        'training_accounting': 'pending-see-ledger' if plan['profile'] == 'TTT128-30' else 'no-TTT',
        'tests': empty_tests(len(challenges[key]['test'])), 'errors': [], 'timings': {}, 'outcome': 'active'}
    def checkpoint(value): write(output/'checkpoint.json', value)
    checkpoint(record)
    events = []; current = {}
    def emit(event, **details):
        # Reserve the full finite test allowance before calling its model. Do not
        # fsync hundreds of thousands of token-level forwards in the quick path.
        if event.startswith('forward_'): return
        if event == 'candidate_ranked':
            rows = sum((adapter.observed[c] for c in details['verification_call_ids']), [])
            require([r['score'] for r in rows] == details['score_aug'], 'actual eight-view NLLs differ from source scores')
            current[digest(details['candidate_grid'])] = {'scores': details['score_aug'], 'rows': rows}
        if event == 'test_started':
            record['tests'][details['test_index']]['termination_reason'] = 'interrupted_pending'
            checkpoint(record)
        if event in {'test_started', 'generation_reserved', 'generation_completed', 'test_terminal'}:
            details.pop('source_clock_reads', None)
            events.append({'event': event, **details})
    adapter = engine.adapter(emit, len(record['tests']))
    adapter.telemetry = telemetry
    fatal = False
    try:
        require(engine.inventory() == engine.baseline, 'baseline differs before task entry')
        write(output/'baseline-inventory.json', engine.baseline)
        engine.inference()
        with telemetry.scope('control'): before = cache_controls(adapter)
        require(before['baseline_prefill'] == engine.initial_control['baseline_prefill'], 'cross-task baseline control differs')
        record['baseline_verified'] = True
        if plan['profile'] == 'TTT128-30':
            with telemetry.scope('preparation'):
                material = public_training_material(engine.loader, engine.tokenizer, key, challenges[key])
            expected = plan['task_materials'][key]
            require(digest(material['rows']) == expected['rows_digest'] and digest(material['texts']) == expected['texts_digest'],
                    'public-demo-derived full epoch differs')
            trainer = engine.trainer(material['texts'], material['rows'], output)
            from nvarc_native_ttt_schedule import native_schedule
            from nvarc_native_ttt_budget import EpochBudget
            rates, schedule = native_schedule(engine.dependency, trainer.args, plan['native_source_learning_rates'])
            write(output/'native-schedule.json', schedule)
            def retain_training(value):
                with telemetry.detail('training_ledger_io'): write(output/'training-ledger.json', value)
            budget = EpochBudget(engine.torch, engine.model, trainer, material['rows'], rates,
                retain_training, expected_parameters=528564224,
                expected_dtype='torch.bfloat16')
            training_start = time.monotonic()
            deadline = min(time.time()+1200, solve_deadline-120-plan['per_test_seconds']*len(record['tests']))
            with telemetry.scope('training'):
                with training_deadline(budget, deadline): trainer.train(); moments = budget.complete()
                engine.torch.cuda.synchronize()
                require(trainer.state.global_step == 128 and trainer.state.epoch == 1, 'complete 128-step epoch required')
                trained = engine.inventory(); require(trained != engine.baseline, 'full TTT did not change tensors')
                write(output/'trained-inventory.json', trained)
            record.update(training_complete=True, training_steps=128)
            record['timings']['training_seconds'] = time.monotonic()-training_start
            discard_optimizer_state(engine.model, trainer, budget)
            import gc
            gc.collect(); engine.torch.cuda.empty_cache()
            require(trainer.accelerator.unwrap_model(engine.model, keep_fp32_wrapper=False) is engine.model,
                    'native task model identity differs')
        engine.inference()
        def solve(index, deadline):
            current.clear(); adapter.observed.clear()
            adapter.generation_deadline = max(time.time(), deadline-10)
            adapter.verification_deadline = deadline
            begin = time.monotonic()
            with engine.torch.inference_mode():
                test = solve_test(challenges, key, index, engine.loader, engine.solver, engine.decoder,
                    engine.tokenizer, adapter, maximum_candidates=64, emit=emit)
            test['candidate_evidence'] = dict(current)
            test['wall_seconds'] = time.monotonic()-begin
            test['forwards_completed'] = dict(adapter.completed)
            return test
        solve_all_tests(plan, challenges, key, solve, checkpoint, record, deadline=solve_deadline-120)
    except InferenceLimitReached as error:
        record['errors'].append({'phase': 'budget', 'type': type(error).__name__, 'reason': error.reason})
    except BaseException as error:
        fatal = True; record['errors'].append({'phase': 'task', 'type': type(error).__name__, 'message': str(error)[:2000]})
    finally:
        begin = time.monotonic()
        try:
            if before is None: raise RuntimeError('baseline control missing; retire worker')
            with telemetry.scope('reset'):
                reset = restore_task_state(engine, trainer, budget, adapter, before)
                write(output/'reset-inventory.json', engine.baseline); write(output/'post-reset-control.json', reset)
            record['reset_verified'] = True
        except BaseException as error:
            fatal = True; record['reset_verified'] = False
            record['errors'].append({'phase': 'reset', 'type': type(error).__name__, 'message': str(error)[:2000]})
        record['timings'].update(reset_seconds=time.monotonic()-begin, total_seconds=time.monotonic()-started)
        if budget is not None:
            record['training_steps'] = sum(r['completed'] for r in budget.state['optimizer_steps'])
            record['training_forwards_reserved'] = len(budget.state['forwards'])
            record['training_forwards_completed'] = sum(r['completed'] for r in budget.state['forwards'])
            record['training_accounting'] = 'observed-completed-and-reserved-counts'
        record['inference_forwards_reserved'] = dict(adapter.reserved)
        record['inference_forwards_completed'] = dict(adapter.completed)
        record['inference_input_tokens_by_phase'] = dict(adapter.input_by_phase)
        record['telemetry'] = telemetry.snapshot()
        if budget is not None:
            record['telemetry']['training_forwards'] = {
                'reserved': len(budget.state['forwards']),
                'completed': sum(r['completed'] for r in budget.state['forwards']),
                'reserved_input_tokens': sum(r['input_tokens'] for r in budget.state['forwards']),
                'completed_input_tokens': sum(r['input_tokens'] for r in budget.state['forwards'] if r['completed']),
                'reserved_supervised_tokens': sum(r['supervised_tokens'] for r in budget.state['forwards']),
                'completed_supervised_tokens': sum(r['supervised_tokens'] for r in budget.state['forwards'] if r['completed'])}
        record['outcome'] = 'failed' if fatal else 'partial' if record['errors'] or any(
            t['termination_reason'] != 'all_source_batches_completed' for t in record['tests']) else 'complete'
        validate_record(plan, challenges, record)
        checkpoint(record); write(output/'result.json', record)
        import gc
        gc.collect(); engine.torch.cuda.empty_cache()
    return record, fatal


def worker(root, model, dependency, rank, deadline, parent_pid, *, detailed_profiling=False):
    install_owner_guard(parent_pid, signal.SIGKILL)
    require(os.environ.get('PYTHONHASHSEED') == '0' and sys.flags.hash_randomization == 0,
            'worker startup hash seed zero required')
    plan = json.loads((root/'plan.json').read_bytes()); challenges = json.loads((root/'challenges.json').read_bytes())
    directory = root/'workers'/str(rank); last = 0; reader = MailboxReader()
    load_telemetry = PhaseTelemetry(detailed=detailed_profiling)
    with load_telemetry.scope('load'):
        engine = NativeEngine(root, plan, model, dependency, rank)
    write(directory/'load-telemetry.json', load_telemetry.snapshot())
    while time.time() < deadline:
        job = directory/'job.json'
        body = reader.read(job)
        if body is None: time.sleep(.1); continue
        value = parse_json(body)
        if value.get('stop'): return
        require(type(value['sequence']) is int and value['sequence'] > 0 and
            value['task_id'] in challenges, 'worker job identity differs')
        if value['sequence'] <= last: time.sleep(.1); continue
        last = value['sequence']; key = value['task_id']
        record, fatal = run_one_task(engine, plan, challenges, key, root/'tasks'/key, deadline,
                                    detailed_profiling=detailed_profiling)
        write(directory/'done.json', {'sequence': last, 'task_id': key, 'outcome': record['outcome'], 'retired': fatal})
        print(json.dumps({'task_id': key, 'outcome': record['outcome']}), flush=True)
        if fatal: return


def main():
    parser = argparse.ArgumentParser()
    for name in ('root', 'model', 'dependency'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--rank', type=int, required=True); parser.add_argument('--deadline', type=float, required=True)
    parser.add_argument('--parent-pid', type=int, required=True)
    parser.add_argument('--detailed-profiling', action='store_true')
    args = parser.parse_args()
    worker(args.root, args.model, args.dependency, args.rank, args.deadline, args.parent_pid,
           detailed_profiling=args.detailed_profiling)


if __name__ == '__main__': main()
