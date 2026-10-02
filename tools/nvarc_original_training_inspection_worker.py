"""Finite native adapter/Trainer inspection; every model operation is blocked.

This worker has no transport entry point. A separately verified parent must
provide exact source/material bindings and the completed native GPU prerequisite.
"""
from __future__ import annotations

import argparse
from array import array
import ast
from contextlib import contextmanager
import hashlib
import importlib.metadata
import inspect as python_inspect
import json
from pathlib import Path
import sys
import time
from types import ModuleType
from typing import Any, Union


FORMAT = 'irisx/nvarc-original-training-inspection-v1'
PARAMETERS = 528564224


def digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def require(value, message):
    if not value:
        raise RuntimeError(message)


@contextmanager
def zero_work_guard(torch, record):
    """Deny calls before execution, including compiled module call dispatch."""
    targets = [(torch.nn.Module, name, 'module-forward') for name in
        ('__call__', '_wrapped_call_impl', '_call_impl')]
    targets += [(torch.autograd, 'backward', 'backward'),
        (torch.autograd, 'grad', 'backward'), (torch.Tensor, 'backward', 'backward'),
        (torch.optim.Optimizer, '__init__', 'optimizer-construction'),
        (torch.optim.Adam, 'step', 'optimizer-step'),
        (torch.optim.AdamW, 'step', 'optimizer-step')]
    originals = [(owner, name, getattr(owner, name)) for owner, name, _ in targets]

    def denied(operation):
        def reject(*args, **kwargs):
            record({'operation': operation, 'blocked_before_execution': True})
            raise RuntimeError('zero-work inspection forbids ' + operation)
        return reject

    try:
        installed = []
        for owner, name, operation in targets:
            replacement = denied(operation)
            setattr(owner, name, replacement)
            installed.append((owner, name, replacement))

        def verify_installed():
            require(all(getattr(owner, name) is replacement for owner, name, replacement in installed),
                'zero-work guard changed during native import or construction')

        yield verify_installed
    finally:
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)


def original_definitions(source, namespace, class_hashes):
    """Execute only the two reviewed original classes and literal role constants."""
    tree = ast.parse(source)
    wanted = {'UnslothFixedTrainer', 'QwenDataCollatorForCompletionOnlyLM'}
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in wanted]
    require(len(classes) == 2 and {node.name for node in classes} == wanted,
        'both original native class definitions required')
    actual = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        for node in classes}
    require(actual == class_hashes, 'exact reviewed original class ASTs required')
    names = {'USER_TOKEN_ID': 11, 'ASSISTANT_TOKEN_ID': 12, 'PAD_ID': 13, 'EOS_ID': 15}
    constants = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            key = node.targets[0].id
            if key in names:
                require(ast.literal_eval(node.value) == names[key], 'original role constant differs')
                constants.append(node)
    require(len(constants) == 4, 'all four original role constants required')
    exec(compile(ast.Module(body=constants + classes, type_ignores=[]),
        'verified-original::native-classes', 'exec'), namespace)
    return tree


def source_snapshot(tree, raw):
    worker = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'worker')
    clones = [node for node in worker.body if isinstance(node, ast.Assign) and
        isinstance(node.value, ast.DictComp) and len(node.targets) == 1 and
        isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'default_weights']
    expected = ast.parse('default_weights = {k: v.clone().detach() for k, v in default_weights.items()}').body[0]
    require(len(clones) == 1 and ast.dump(clones[0], include_attributes=False) ==
        ast.dump(expected, include_attributes=False), 'complete original detached snapshot required')
    namespace = {'default_weights': raw}
    exec(compile(ast.Module(body=clones, type_ignores=[]), 'verified-original::snapshot', 'exec'), namespace)
    return namespace['default_weights']


def prepared_evidence(trainer, collator, expected_rows, binary=None):
    require(len(trainer.train_dataset) == len(expected_rows) == 128,
        'all complete source views must survive native preprocessing')
    # Mirror the actual HF Dataset dataloader's unused-column removal. Passing
    # its text/reply columns directly to tokenizer.pad is not the source flow.
    dataset = trainer._remove_unused_columns(trainer.train_dataset, description='native-inspection')
    evidence = []
    for index, (native, expected) in enumerate(zip(dataset, expected_rows)):
        ids = native['input_ids']
        batch = collator([native])
        require(batch['input_ids'].shape[0] == 1 and batch['labels'].shape == batch['input_ids'].shape,
            'source single-view native collator shape differs')
        actual_ids = batch['input_ids'][0].tolist()
        labels = batch['labels'][0].tolist()
        input_digest, label_digest = digest(ids), digest(labels)
        evidence.append({'row': index, 'input_tokens': len(ids),
            'supervised_tokens': sum(x >= 0 for x in labels[1:]),
            'input_ids_digest': input_digest, 'labels_digest': label_digest,
            'collator_preserved_input_ids': actual_ids == ids,
            'source_input_ids_equal': input_digest == expected['input_ids_digest'],
            'source_labels_equal': label_digest == expected['labels_digest']})
        if binary is not None:
            require(len(ids) == len(labels) and all(type(value) is int and 0 <= value < 16 for value in ids) and
                all(type(value) is int and (value == -100 or 0 <= value < 16) for value in labels),
                'bounded original sixteen-symbol tokens and completion labels required')
            values = array('h', ids + labels)
            if sys.byteorder != 'little': values.byteswap()
            offset = binary.tell(); body = values.tobytes(); binary.write(body)
            evidence[-1].update(retained_byte_offset=offset, retained_token_bytes=len(body))
    return evidence


def tensor_inventory(values, torch):
    result = []
    for name, tensor in sorted(values.items()):
        require(bool(torch.isfinite(tensor).all().item()), 'every saved adapter tensor must remain finite')
        result.append({'name': name, 'shape': list(tensor.shape), 'dtype': str(tensor.dtype),
            'elements': tensor.numel(), 'finite': True, 'sha256': hashlib.sha256(tensor.detach().contiguous()
                .view(torch.uint8).cpu().numpy().tobytes()).hexdigest()})
    return result


def run(plan, model_path, dependency, solver_path, texts, expected_rows, output):
    require(plan['format'] == FORMAT and plan['owner_decision'] == 'Decision 0054' and
        plan['approved'] is True and plan['original_unsloth_gpu_prerequisite_verified'] is True and
        all(type(plan[key]) is int and plan[key] == 0 for key in ('maximum_outer_forwards',
            'maximum_optimizer_steps', 'maximum_generations', 'maximum_teacher_calls', 'maximum_paid_usd')),
        'exact approved zero-work envelope and native prerequisite required')
    parent = json.loads((output.parent / 'parent-verification.json').read_bytes())
    require(parent['plan_digest'] == digest(plan) and parent['source_inventory_verified'] is True and
        parent['model_material_digest'] == plan['model_material_digest'] and
        parent['four_distinct_bf16_l4s'] is True, 'reviewed exact parent envelope required')
    started = time.monotonic()
    events = []

    def save(name, value):
        (output / name).write_text(json.dumps(value, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')

    def blocked(event):
        events.append(event)
        save('prohibited-attempts.json', events)

    sys.path.insert(0, str(dependency))
    versions = {name: importlib.metadata.version(name) for name in plan['versions']}
    require(versions == plan['versions'], 'exact sixteen original distributions required')
    import torch
    require(torch.__version__ == '2.8.0+cu128' and torch.version.cuda == '12.8' and
        Path(torch.__file__).resolve().is_relative_to(dependency.resolve()), 'original Torch CUDA import required')
    save('guard-state.json', {'installed_before_unsloth_import': True,
        'module_call_paths_blocked': ['__call__', '_wrapped_call_impl', '_call_impl'],
        'optimizer_construction_blocked': True, 'backward_and_step_blocked': True})
    with zero_work_guard(torch, blocked) as verify_guard:
        from unsloth import FastLanguageModel, UnslothTrainer, UnslothTrainingArguments
        from transformers import DataCollatorForLanguageModeling
        from peft import get_peft_model_state_dict, set_peft_model_state_dict
        from datasets import Dataset
        import numpy as np
        verify_guard()
        source = solver_path.read_text(encoding='utf-8')
        require(hashlib.sha256(source.encode()).hexdigest() == plan['solver_cell_sha256'],
            'exact trusted solver cell required')
        native_module = ModuleType('irisx_verified_original_solver')
        native_module.__file__ = str(solver_path)
        sys.modules[native_module.__name__] = native_module
        namespace = native_module.__dict__
        namespace.update({'UnslothTrainer': UnslothTrainer,
            'DataCollatorForLanguageModeling': DataCollatorForLanguageModeling,
            'np': np, 'torch': torch, 'Any': Any, 'Union': Union})
        tree = original_definitions(source, namespace, plan['original_class_ast_sha256'])
        model, tokenizer = FastLanguageModel.from_pretrained(model_name=str(model_path),
            full_finetuning=False, load_in_4bit=False, local_files_only=True,
            use_gradient_checkpointing=False, max_seq_length=8192)
        model = FastLanguageModel.get_peft_model(model, **plan['original_peft_parameters'])
        verify_guard()
        for parameter in model.parameters():
            if parameter.dtype == torch.float32:
                parameter.data = parameter.data.to(torch.bfloat16)
        trainable = [{'name': name, 'shape': list(p.shape), 'dtype': str(p.dtype), 'elements': p.numel()}
            for name, p in model.named_parameters() if p.requires_grad]
        save('adapter-topology.json', {'trainable': trainable,
            'trainable_parameters': sum(p['elements'] for p in trainable),
            'source_inferred_count_equal': sum(p['elements'] for p in trainable) == PARAMETERS})
        raw = get_peft_model_state_dict(model, adapter_name='default')
        defaults = source_snapshot(tree, raw)
        independent = all(defaults[k].data_ptr() != raw[k].data_ptr() and not defaults[k].requires_grad for k in defaults)
        require(independent, 'independent detached original baseline required')
        baseline = tensor_inventory(defaults, torch)
        save('baseline-inventory.json', baseline)
        key = next(k for k in sorted(raw) if 'lora_A' in k)
        before = float(defaults[key].flatten()[0])
        with torch.no_grad():
            raw[key].flatten()[0].add_(1)
        changed = float(raw[key].flatten()[0])
        require(changed != before and float(defaults[key].flatten()[0]) == before,
            'reversible scalar perturbation must leave detached baseline unchanged')
        set_peft_model_state_dict(model, defaults.copy(), adapter_name='default')
        restored = tensor_inventory(get_peft_model_state_dict(model, adapter_name='default'), torch)
        save('reset-inventory.json', restored)
        require(restored == baseline, 'every original saved tensor must reset to its baseline')
        save('reset-observation.json', {'key': key, 'before': before, 'perturbed': changed,
            'all_saved_tensors_restored': True, 'independent_detached_storage_observed': independent})
        del raw, defaults
        model = FastLanguageModel.for_training(model)
        collator = namespace['QwenDataCollatorForCompletionOnlyLM'](tokenizer=tokenizer, mlm=False)
        args = UnslothTrainingArguments(**plan['original_training_arguments'])
        before_lengths = {key: getattr(args, key, None) for key in ('max_length', 'max_seq_length')}
        trainer = namespace['UnslothFixedTrainer'](model=model, tokenizer=tokenizer,
            data_collator=collator, train_dataset=Dataset.from_list(texts),
            dataset_text_field='text', max_seq_length=8192, args=args)
        verify_guard()
        require(getattr(trainer, 'optimizer', None) is None, 'inspection must not create an optimizer')
        with (output / 'prepared-tokens.i16le').open('xb') as binary:
            rows = prepared_evidence(trainer, collator, expected_rows, binary)
        save('prepared-rows.json', rows)
        origins = []
        for index, cls in enumerate(type(trainer).__mro__):
            try:
                path = python_inspect.getsourcefile(cls)
            except TypeError:
                path = None
            row = {'class': cls.__name__, 'module': cls.__module__, 'source_path': path}
            if path is not None and Path(path).is_file():
                body = Path(path).read_bytes()
                require(len(body) <= 2 * 1024**2, 'bounded native Trainer class source required')
                name = 'trainer-source-' + str(index) + '.py'
                (output / name).write_bytes(body)
                row.update(retained_file=name, sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
            origins.append(row)
        current = [{'name': name, 'shape': list(p.shape), 'dtype': str(p.dtype), 'elements': p.numel()}
            for name, p in model.named_parameters() if p.requires_grad]
        result = {'format': FORMAT, 'versions': versions, 'trainable_before_trainer': trainable,
            'trainable_after_trainer': current, 'trainable_parameters': sum(p['elements'] for p in trainable),
            'declared_argument_lengths': before_lengths,
            'prepared_argument_lengths': {key: getattr(trainer.args, key, None) for key in ('max_length', 'max_seq_length')},
            'trainer_origins': origins, 'prepared_columns': trainer.train_dataset.column_names,
            'every_source_input_and_label_equal': all(row['collator_preserved_input_ids'] and
                row['source_input_ids_equal'] and row['source_labels_equal'] for row in rows),
            'prepared_rows_digest': digest(rows),
            'gradient_checkpoint_flags': [{'module': name, 'value': m.gradient_checkpointing}
                for name, m in model.named_modules() if hasattr(m, 'gradient_checkpointing')],
            'optimizer_created': False, 'prohibited_attempts': len(events), 'model_forwards': 0,
            'optimizer_steps': 0, 'generation_calls': 0, 'teacher_calls': 0,
            'cuda_peak_allocated_bytes': torch.cuda.max_memory_allocated(),
            'wall_seconds': time.monotonic() - started, 'full_long_ttt_completed': False,
            'correctness_scored': False, 'contains_evaluator_truth': False}
        save('native-inspection.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('plan', 'model', 'dependency', 'solver', 'texts', 'rows', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    run(json.loads(args.plan.read_bytes()), args.model, args.dependency, args.solver,
        json.loads(args.texts.read_bytes()), json.loads(args.rows.read_bytes()), args.output)
