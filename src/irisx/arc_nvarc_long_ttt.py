"""Reduced eight-view source TTT resource check on long public demonstrations."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import time

from .arc_nvarc_complete_ttt import complete_config
from .arc_nvarc_data import visible_task
from .arc_nvarc_representation import verify_model_material
from .arc_nvarc_source_bundle import verify_bundle
from .arc_nvarc_training import TaskLocalAdapter, load_compact_model, task_local_sequences
from .arc_nvarc_upstream import source_bundle
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError


def resource_config(*,cpu_optimizer_state=False):
    adaptation = complete_config()['adaptation']
    adaptation.update(augmentation_count=1, maximum_optimizer_steps=8, maximum_training_tokens=65536)
    if cpu_optimizer_state:adaptation['optimizer_state_device']='cpu'
    return {'adaptation': adaptation}


def check_plan(plan, config, tasks):
    if (plan.get('format') != 'irisx/nvarc-long-ttt-resource-v1' or
            re.fullmatch(r'nvarc-overnight-ttt-\d{3}', plan.get('run_id', '')) is None or
            plan.get('owner_decision') != 'Decision 0053' or plan.get('approved') is not True or
            config != resource_config(cpu_optimizer_state=plan.get('optimizer_state_device')=='cpu') or plan.get('config_digest') != digest_value(config) or
            plan.get('visible_digest') != digest_value(tasks) or len(tasks) != 1 or
            len(tasks[0]['test']) != 1 or 'output' in tasks[0]['test'][0] or
            plan.get('maximum_tasks') != 1 or plan.get('maximum_optimizer_steps') != 8 or
            plan.get('maximum_generations') != 0 or plan.get('maximum_verifications') != 0 or
            plan.get('maximum_outer_model_forwards') != 8 or plan.get('maximum_teacher_calls') != 0 or
            plan.get('maximum_paid_usd') != 0 or plan.get('backend') not in {'cuda-l4', 'cpu-fixture'}):
        raise ValidationError('long source resource plan differs')
    if plan['backend'] == 'cuda-l4' and not 6000 <= plan['source_epoch_max_sequence_length'] <= 8192:
        raise ValidationError('long source resource sequence length differs')


def run(plan_path, model_path, visible_path, config_path, bundle, output):
    import torch
    from peft import get_peft_model_state_dict
    plan = json.loads(plan_path.read_bytes())
    config = json.loads(config_path.read_bytes())
    raw = json.loads(visible_path.read_bytes())
    if any(set(test) != {'input'} for task in raw.values() for test in task['test']):
        raise ValidationError('long resource visible test answers forbidden')
    tasks = [visible_task(key, value) for key, value in sorted(raw.items())]
    check_plan(plan, config, tasks)
    material = verify_model_material(model_path, plan['material_digest'])
    if material['training_identity_digest'] != plan['training_identity_digest']:
        raise ValidationError('long source resource export identity differs')
    verify_bundle(bundle, plan['source_bundle_digest'])
    if output.exists():
        raise ValidationError('new long resource output required')
    output.mkdir(parents=True)
    started = time.monotonic()
    ledger = {'outer_model_forwards_reserved': 0, 'optimizer_steps_completed': 0,
              'generation_calls_completed': 0, 'verification_calls_completed': 0, 'phase': 'load'}
    def emit(event, **values):
        with (output / 'events.jsonl').open('ab') as stream:
            stream.write(canonical_bytes({'event': event, 'elapsed_seconds': time.monotonic()-started, **values}, newline=True))
            stream.flush()
    def observe_forward(module, args):
        if ledger['outer_model_forwards_reserved'] >= 8:
            raise ValidationError('long resource forward ceiling reached')
        ledger['outer_model_forwards_reserved'] += 1
    def observe_step(event):
        ledger['optimizer_steps_completed'] = event['completed_steps']
        emit('ttt-optimizer-returned', **event)
    adapter = hook = None
    try:
        with source_bundle(bundle, plan['source_bundle_digest']):
            rows = task_local_sequences(tasks[0], seed=42, augmentation_count=1, source_qwen=True,
                source_augmentation_seed=1, source_max_length=8192)
            if (len(rows) != 8 or sum(len(row['input_ids']) for row in rows) != plan['source_epoch_input_tokens'] or
                    max(len(row['input_ids']) for row in rows) != plan['source_epoch_max_sequence_length']):
                raise ValidationError('long source resource row/token binding differs')
            gpu = plan['backend'] == 'cuda-l4'
            model = load_compact_model(model_path, dtype='bfloat16' if gpu else 'float32')
            if gpu:
                model.to(torch.device('cuda', 0))
            hook = model.register_forward_pre_hook(observe_forward)
            adapter = TaskLocalAdapter(model, config['adaptation'], step_observer=observe_step)
            ledger['phase'] = 'reduced-eight-view-source-epoch'
            emit(ledger['phase'])
            adapter.adapt(tasks[0])
            observation = adapter.last_observation
            if observation['steps'] != 8 or not observation['complete_epoch'] or ledger['outer_model_forwards_reserved'] != 8:
                raise ValidationError('long source resource workload differs')
            changed = [name for name, value in get_peft_model_state_dict(adapter.model).items()
                       if not torch.equal(value.detach().cpu(), adapter.initial[name])]
            if not changed:
                raise ValidationError('long source adapter optimizer changed no state')
            adapter.reset(clear_observation=False)
            reset = all(torch.equal(value.detach().cpu(), adapter.initial[name])
                        for name, value in get_peft_model_state_dict(adapter.model).items())
            if not reset:
                raise ValidationError('long source adapter reset differs')
            ledger['phase'] = 'complete'
            result = {'format': 'irisx/nvarc-long-ttt-resource-result-v1', 'run_id': plan['run_id'],
                'plan_digest': digest_value(plan), 'material_digest': plan['material_digest'],
                'training_identity_digest': plan['training_identity_digest'], 'ttt': observation, 'ledger': ledger,
                'adapter_reset_exact': reset, 'changed_adapter_tensor_count': len(changed),
                'maximum_sequence_length_observed': max(len(row['input_ids']) for row in rows),
                'reduced_color_repeats': 1, 'original_128_view_epoch_verified': False,
                'contains_evaluator_truth': False, 'correctness_scored': False, 'full_scale_sft_verified': False,
                'original_qwen3_unsloth_parity': False, 'wall_seconds': time.monotonic()-started}
            (output / 'result.json').write_bytes(canonical_bytes(result, newline=True))
            emit('complete')
            return result
    except BaseException as error:
        failure = {'run_id': plan['run_id'], 'plan_digest': digest_value(plan), 'ledger': ledger,
            'error_type': type(error).__name__, 'error_message': str(error)[:1200],
            'ttt': None if adapter is None else adapter.last_observation, 'contains_evaluator_truth': False}
        (output / 'failure.json').write_bytes(canonical_bytes(failure, newline=True))
        raise
    finally:
        if hook is not None:
            hook.remove()
        if adapter is not None:
            adapter.reset(clear_observation=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('plan', 'model', 'visible', 'config', 'bundle', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.model, args.visible, args.config, args.bundle, args.output)
