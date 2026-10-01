"""Digest-bound published TRM runtime for a bounded joint GPU integration check.

The original model/loss/optimizers execute from unchanged, pinned source files.
One demo update and eight D4 inference views are explicit reduced workloads,
not the original pretraining or 2,000-epoch test adaptation recipe.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time

from .arc_nvarc_data import visible_task, transform_grid
from .arc_nvarc_m3_trm import _batch, _step, _initial_carry_on_device
from .arc_nvarc_trm import _decode_trm_tensor, TRM_REVISION
from .arc_nvarc_trm_checkpoint import load_published_state, published_model_config
from .canonical import canonical_bytes, digest_value
from .errors import ValidationError

SOURCE_HASHES = {
    'models/common.py': '6aaff2b0cee33073739586e4b416b030d338ab4b9ffb5261b2db14414dc3112b',
    'models/layers.py': '7dc53639944332244bbc3268909f00f11388c6bc1df70747d0589c20c2088d89',
    'models/sparse_embedding.py': '54aec93a6f4a296b6081314a62522ca9e8e3e4ba4e83c168bf64b22befd4949f',
    'models/losses.py': '7aa324db1556f0e715f71a6e14b01b25b44fb12fbe862352cb4651b52bb75e72',
    'models/recursive_reasoning/trm.py': '05d37524062ac6b7d958dbd7a173f3f7c99eaaa0b60cf78c57638a82ad185b46',
    'LICENSE': 'a17df02e2c90fbbb4b2fc0f0262ae429ef9c628c45ee434499fd9aeb987735a4',
}


def verify_runtime_bundle(root: Path, expected: str):
    paths = list(root.rglob('*'))
    if root.is_symlink() or not root.is_dir() or any(path.is_symlink() for path in paths):
        raise ValidationError('TRM runtime bundle path differs')
    actual = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in paths if path.is_file()}
    if actual != SOURCE_HASHES or digest_value(actual) != expected:
        raise ValidationError('TRM runtime pinned source inventory differs')
    return {'revision': TRM_REVISION, 'files': actual, 'bundle_digest': expected}


def build_runtime_bundle(source: Path, output: Path):
    if output.exists():
        raise ValidationError('new TRM runtime source identity required')
    for name, expected in SOURCE_HASHES.items():
        path = source / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValidationError('TRM source differs before packaging: ' + name)
    for name in SOURCE_HASHES:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source / name).read_bytes())
    return verify_runtime_bundle(output, digest_value(SOURCE_HASHES))


@contextmanager
def runtime_classes(root: Path, expected: str):
    verify_runtime_bundle(root, expected)
    previous_path = list(sys.path)
    previous_bytecode = sys.dont_write_bytecode
    previous_modules = {name: value for name, value in sys.modules.copy().items()
                        if name == 'models' or name.startswith('models.')}
    for name in previous_modules:
        del sys.modules[name]
    sys.path.insert(0, str(root))
    sys.dont_write_bytecode = True
    try:
        from adam_atan2_pytorch import AdamAtan2
        core = importlib.import_module('models.recursive_reasoning.trm')
        losses = importlib.import_module('models.losses')
        sparse = importlib.import_module('models.sparse_embedding')
        yield core.TinyRecursiveReasoningModel_ACTV1, losses.ACTLossHead, sparse.CastedSparseEmbeddingSignSGD_Distributed, AdamAtan2
    finally:
        for name in list(sys.modules):
            if name == 'models' or name.startswith('models.'):
                del sys.modules[name]
        sys.modules.update(previous_modules)
        sys.path[:] = previous_path
        sys.dont_write_bytecode = previous_bytecode


def construct_source_model(classes, config, device):
    """Construct sparse gradient buffers on their final device as leaf tensors.

    Moving an existing requires-grad buffer with Module.to creates a CopyBackward
    buffer that the source sparse optimizer rejects. Parameters and buffers are
    instead created directly on the selected device, as in upstream training.
    """
    import torch
    core, loss_cls, _, _ = classes
    with torch.device(device):
        model = loss_cls(core(config), loss_type='stablemax_cross_entropy')
    if any(value.requires_grad and not value.is_leaf for value in model.buffers()):
        raise ValidationError('TRM optimizer gradient buffer is not a leaf')
    if any(value.device != torch.device(device) for value in (*model.parameters(), *model.buffers())):
        raise ValidationError('TRM constructed model device differs')
    return model


def run_published_trm(plan: dict, task: dict, checkpoint: Path, bundle: Path, output: Path,
                      *, device='cuda:1'):
    import torch
    settings = plan['joint_trm']
    task = visible_task(task['task_id'], task)
    if (output.exists() or settings['maximum_optimizer_steps'] != 1 or
            settings['maximum_views'] != 8 or settings['maximum_act_forwards'] != 80 or
            settings['model_config'] != published_model_config(device_dtype='bfloat16') or
            digest_value([task]) != plan['visible_digest'] or len(task['test']) != 1):
        raise ValidationError('published joint TRM plan/task differs')
    if device not in ('cuda:1', 'cpu'):
        raise ValidationError('published joint TRM device differs')
    if device == 'cuda:1' and not torch.cuda.is_bf16_supported():
        raise ValidationError('published TRM requires BF16 GPU')
    output.mkdir(parents=True)
    started = time.monotonic()
    ledger = {'optimizer_steps_reserved': 0, 'optimizer_steps_completed': 0,
              'inference_views_reserved': 0, 'inference_views_completed': 0,
              'act_forwards_reserved': 0, 'phase': 'strict-checkpoint-load'}

    def emit(event, **details):
        with (output / 'events.jsonl').open('ab') as stream:
            stream.write(canonical_bytes({'event': event, 'ledger': ledger.copy(),
                'elapsed_seconds': time.monotonic() - started, **details}, newline=True))
            stream.flush()

    try:
        torch.manual_seed(44)
        with runtime_classes(bundle, settings['source_bundle_digest']) as classes:
            core, loss_cls, sparse_cls, adam_cls = classes
            model = construct_source_model(classes, settings['model_config'], device)
            loaded = load_published_state(model, checkpoint, settings['checkpoint_sha256'],
                compiler_prefix='' if settings.get('kernel_source') else '_orig_mod.')
            initial = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
            if device != 'cpu':
                torch.cuda.reset_peak_memory_stats(device)
            ledger.update(phase='public-demo-ttt', optimizer_steps_reserved=1)
            emit('optimizer-reserved')
            demo = task['train'][0]
            batch = {name: value.to(device) for name, value in _batch(demo['input'], demo['output'], identifier=0).items()}
            sparse = sparse_cls(model.model.puzzle_emb.buffers(), world_size=1, lr=.01, weight_decay=.1)
            adam = adam_cls(model.parameters(), lr=.0001, weight_decay=0., betas=(.9, .95))
            loss, gradients = _step(model, batch, [sparse, adam])
            ledger['optimizer_steps_completed'] = 1
            changed = [name for name, value in model.state_dict().items()
                       if not torch.equal(value.detach().cpu(), initial[name])]
            if not changed:
                raise ValidationError('joint TRM update did not change parameters')
            emit('optimizer-complete', loss=loss, gradient_parameters=gradients, changed_tensors=len(changed))
            del sparse, adam
            ledger['phase'] = 'eight-dihedral-views'
            model.eval()
            predictions, candidates = [], []
            with torch.inference_mode():
                for transpose in (False, True):
                    for rotation in range(4):
                        view = {'rotation': rotation, 'transpose': transpose, 'colors': list(range(10))}
                        input_grid = transform_grid(task['test'][0]['input'], view)
                        batch = {name: value.to(device) for name, value in _batch(input_grid, None, identifier=0).items()}
                        ledger['inference_views_reserved'] += 1
                        emit('view-reserved', view=view)
                        carry = _initial_carry_on_device(model.model, batch)
                        calls = 0
                        while calls < 10:
                            ledger['act_forwards_reserved'] += 1
                            calls += 1
                            carry, values = model.model(carry=carry, batch=batch)
                            if not bool(torch.isfinite(values['logits']).all()):
                                raise ValidationError('joint TRM inference logits nonfinite')
                            if bool(carry.halted.all()):
                                break
                        if not bool(carry.halted.all()):
                            raise ValidationError('joint TRM ACT horizon did not terminate')
                        raw_prediction = values['logits'].argmax(-1)[0].tolist()
                        try:
                            decoded = _decode_trm_tensor(raw_prediction)
                            candidate = transform_grid(decoded, view, inverse=True)
                        except ValidationError:
                            candidate = None
                        record = {'view': view, 'act_forwards': calls, 'raw_prediction': raw_prediction,
                                  'candidate': candidate, 'status': 'candidate' if candidate is not None else 'missing-candidate'}
                        predictions.append(record)
                        if candidate is not None:
                            candidates.append({'grid': candidate, 'source': 'trm:view' + str(len(predictions)-1),
                                               'branch': 'published-trm-model'})
                        ledger['inference_views_completed'] += 1
                        emit('view-complete', view=view, candidate_status=record['status'], act_forwards=calls)
            model.load_state_dict(initial, strict=True)
            if any(not torch.equal(value.detach().cpu(), initial[name]) for name, value in model.state_dict().items()):
                raise ValidationError('joint TRM published task reset differs')
            ledger['phase'] = 'complete'
            result = {'format': 'irisx/nvarc-published-trm-joint-result-v1', 'plan_digest': digest_value(plan),
                'visible_digest': plan['visible_digest'], 'checkpoint_load': loaded, 'model_config': settings['model_config'],
                'ledger': ledger, 'ttt_loss': loss, 'changed_tensors': changed, 'gradient_parameters': gradients,
                'predictions': predictions, 'candidates': candidates, 'adapter_reset_exact': True,
                'peak_cuda_allocated_bytes': 0 if device == 'cpu' else torch.cuda.max_memory_allocated(device),
                'peak_cuda_reserved_bytes': 0 if device == 'cpu' else torch.cuda.max_memory_reserved(device),
                'contains_evaluator_truth': False, 'correctness_scored': False, 'original_scale_ttt_verified': False,
                'original_notebook_v18_verified': False, 'wall_seconds': time.monotonic() - started}
            (output / 'result.json').write_bytes(canonical_bytes(result, newline=True))
            emit('complete')
            return result
    except BaseException as error:
        (output / 'failure.json').write_bytes(canonical_bytes({'plan_digest': digest_value(plan), 'ledger': ledger,
            'error_type': type(error).__name__, 'error_message': str(error)[:1200]}, newline=True))
        raise


def verify_joint_trm_result(plan, result):
    """Independently decode every raw model view; reject fixture/answer envelopes."""
    import math
    settings = plan['joint_trm']
    loaded, ledger = result['checkpoint_load'], result['ledger']
    if settings.get('kernel_source') and loaded.get('explicit_compiler_prefix')!='':
        raise ValidationError('trained TRM export prefix binding differs')
    if (result['format'] != 'irisx/nvarc-published-trm-joint-result-v1' or
            result['plan_digest'] != digest_value(plan) or result['visible_digest'] != plan['visible_digest'] or
            result['model_config'] != settings['model_config'] or
            loaded['checkpoint_sha256'] != settings['checkpoint_sha256'] or loaded['state_tensor_count'] != 15 or
            loaded['source_puzzle_embedding_shape'] != [1041208, 512] or loaded['target_puzzle_embedding_shape'] != [1, 512] or
            not loaded['source_mean_reset_applied'] or loaded['dropped_state_keys'] != 0 or
            not loaded['loaded_tensors_exact_after_explicit_dtype_cast'] or
            ledger['phase'] != 'complete' or ledger['optimizer_steps_reserved'] != 1 or ledger['optimizer_steps_completed'] != 1 or
            ledger['inference_views_reserved'] != 8 or ledger['inference_views_completed'] != 8 or
            not result['adapter_reset_exact'] or not result['changed_tensors'] or result['gradient_parameters'] <= 0 or
            not math.isfinite(result['ttt_loss']) or result['contains_evaluator_truth'] or result['correctness_scored'] or
            result['original_scale_ttt_verified'] or result['original_notebook_v18_verified']):
        raise ValidationError('joint published TRM result binding/workload differs')
    expected_views = [{'rotation': rotation, 'transpose': transpose, 'colors': list(range(10))}
                      for transpose in (False, True) for rotation in range(4)]
    if [item['view'] for item in result['predictions']] != expected_views:
        raise ValidationError('joint TRM eight model views differ')
    candidates = []
    for index, item in enumerate(result['predictions']):
        if not 1 <= item['act_forwards'] <= 10:
            raise ValidationError('joint TRM ACT budget differs')
        try:
            candidate = transform_grid(_decode_trm_tensor(item['raw_prediction']), item['view'], inverse=True)
        except ValidationError:
            candidate = None
        if candidate != item['candidate'] or item['status'] != ('candidate' if candidate is not None else 'missing-candidate'):
            raise ValidationError('joint TRM raw prediction/inverse map differs')
        if candidate is not None:
            candidates.append({'grid': candidate, 'source': 'trm:view' + str(index), 'branch': 'published-trm-model'})
    if (candidates != result['candidates'] or len(candidates) > 8 or
            ledger['act_forwards_reserved'] != sum(item['act_forwards'] for item in result['predictions'])):
        raise ValidationError('joint TRM candidate/forward ledger differs')
    return {'raw_candidates': len(candidates), 'act_forwards': ledger['act_forwards_reserved'],
            'optimizer_steps': 1, 'eight_views_verified': True, 'correctness_scored': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('plan', 'visible', 'checkpoint', 'bundle', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_bytes())
    raw = json.loads(args.visible.read_bytes())
    if any(set(test) != {'input'} for task in raw.values() for test in task['test']):
        raise ValidationError('joint TRM visible test answers forbidden')
    task = visible_task('00576224', raw['00576224'])
    run_published_trm(plan, task, args.checkpoint, args.bundle, args.output)
