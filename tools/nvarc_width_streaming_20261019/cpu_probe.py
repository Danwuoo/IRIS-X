"""Offline, bounded official single-layer comparison; never the official 2B model.

Run reference and streamed modes in separate fresh processes, sequentially.
The unchanged widen_mlp is the reconstruction oracle, not an assumed formula.
All source files are pinned before a one-layer subset is selected. No tasks,
held-out answers, generation benchmark, GPU or network calls are used.
"""
from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import signal
import time

import torch
from torch import nn
from transformers import AutoConfig, Qwen3ForCausalLM
from peft import LoraConfig, get_peft_model
from safetensors.torch import save_file, load_file

from tools.nvarc_capacity_20261017.factory import _geometry, _digest
from tools.nvarc_posttrain_20261017.engine import PROJECTIONS, OFFICIAL_SHAPES
from tools.nvarc_posttrain_20261017.materials import verify_model, sha_file
from tools.nvarc_posttrain_20261017.precision import (
    install_policy, install_checkpoint_policy, full_precision_compute,
)
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
from tools.nvarc_width_20261018.expansion import widen_mlp, replica_indices
from .bridge import build_bounded_model, SafetensorSource, tensor_sha256, memory_plan


def need(value, message):
    if not value:
        raise ValueError(message)


def rss():
    rows = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    return {'rss_bytes': int(rows['VmRSS'].split()[0]) * 1024,
            'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}


def trim():
    gc.collect()
    import ctypes
    ctypes.CDLL(None).malloc_trim(0)


def parameter_hashes(model, *, trainable=None):
    return {name: tensor_sha256(value) for name, value in model.named_parameters()
            if trainable is None or value.requires_grad == trainable}


def probes(model):
    model.eval()
    ids = torch.tensor([[14, 11, 10, 1, 2, 15, 10, 14, 12, 10]])
    with torch.no_grad(), full_precision_compute('cpu'):
        outputs = model(ids, use_cache=True)
        logits = outputs.logits.detach().clone()
        cached = model(torch.tensor([[3]]), past_key_values=outputs.past_key_values, use_cache=True).logits.detach().clone()
    g = torch.Generator().manual_seed(9301)
    values = torch.randn((1, 3, model.config.hidden_size), generator=g).mul_(.1).requires_grad_()
    with full_precision_compute('cpu'):
        mlp_output = model.get_base_model().model.layers[0].mlp(values)
        gradient = torch.autograd.grad(mlp_output.square().mean(), values)[0]
    return {'full_logits': logits, 'cached_logits': cached,
            'mlp_output': mlp_output.detach(), 'mlp_input_gradient': gradient.detach()}


def reference_model(config, source, *, widened):
    """Original dense initialization/promotion plus unchanged widen_mlp oracle."""
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(123)
        raw = Qwen3ForCausalLM(copy.deepcopy(config)).bfloat16()
        with torch.no_grad():
            for name, p in raw.named_parameters():
                with source.tensor(name) as value:
                    p.copy_(value)
                del value
        torch.random.default_generator.manual_seed(731)
        model = get_peft_model(raw, LoraConfig(r=64, lora_alpha=16, lora_dropout=0.0,
            use_rslora=True, bias='none', task_type='CAUSAL_LM', target_modules=list(PROJECTIONS),
            modules_to_save=['embed_tokens', 'lm_head']))
        for p in model.parameters():
            if p.requires_grad:
                p.data = p.data.float()
        install_policy(model, FP32_BACKBONE_POLICY)
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        install_checkpoint_policy(model, FP32_BACKBONE_POLICY)
        model.enable_input_require_grads()
        if widened:
            widen_mlp(raw.model.layers[0].mlp, 8192, layer_index=0)
            model.config.intermediate_size = 8192
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('reference', 'streamed'), required=True)
    args = parser.parse_args()
    need(not args.output.exists(), 'distinct immutable output directory required')
    args.output.mkdir(parents=True)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('bounded 180-second CPU probe')))
    signal.alarm(180)
    started = time.monotonic()
    report = {'format': 'irisx/official-layer-streaming-bridge-evidence-v1', 'mode': args.mode,
        'success': False, 'device': 'cpu', 'source_scope': 'official layer 0 plus compact heads/final norm',
        'full_2b_constructed': False, 'width_engine_admitted': False,
        'official_full_model_result': False, 'capability_gain_established': False,
        'held_out_accuracy_measured': False, 'full_context_admitted': False,
        'optimizer_recipe_equivalence_claimed': False,
        'memory_comparison_scope': 'bounded reference harness only, not production from_pretrained',
        'reference_constructs_FP32_then_BF16': True,
        'reference_build_peak_includes_dense_function_and_input_gradient_probes': True,
        'exit137_cause_or_resolution_established': False,
        'cpu_threads': 1, 'watchdog_seconds': 180,
        'versions': {name: importlib.metadata.version(name) for name in ('torch','transformers','peft','safetensors')},
        'stages': []}
    repo = Path(__file__).resolve().parents[2]
    code_files = ('tools/nvarc_width_streaming_20261019/bridge.py',
                  'tools/nvarc_width_streaming_20261019/cpu_probe.py',
                  'tools/nvarc_width_20261018/expansion.py',
                  'tools/nvarc_posttrain_20261017/precision.py')
    report['code_sha256'] = {name: sha_file(repo / name) for name in code_files}
    def persist():
        report['wall_seconds'] = time.monotonic() - started
        report['final_memory'] = rss()
        (args.output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    def stage(name, **details):
        row = {'name': name, 'elapsed_seconds': time.monotonic() - started, 'memory': rss(), **details}
        report['stages'].append(row)
        persist()
        print(json.dumps(row), flush=True)
    try:
        report['verified_official_identity'] = verify_model(args.source, '2b')
        config = AutoConfig.from_pretrained(args.source, local_files_only=True, trust_remote_code=False)
        config.num_hidden_layers = 1
        config.layer_types = ['full_attention']
        config.use_cache = False
        config._attn_implementation = 'sdpa'
        geometry = {key: getattr(config, key) for key in OFFICIAL_SHAPES['2b']}
        names = {name: name for name in _geometry(geometry)}
        source = SafetensorSource(args.source / 'model.safetensors', names=names)
        report['selected_native_tensors'] = len(names)
        report['selected_source_parameters'] = sum(torch.Size(shape).numel() for shape, _ in source.manifest.values())
        report['full2b_analytic_memory_plan_not_execution'] = memory_plan(OFFICIAL_SHAPES['2b'], 8192)
        stage('source_verified_and_subset_selected')
        build_start = time.monotonic()
        if args.mode == 'reference':
            model = reference_model(config, source, widened=False)
            # Dense probes are intentionally performed before the unchanged
            # widening oracle, unlike the streamed builder's tensor-only path.
            dense_probe = probes(model)
            save_file(dense_probe, args.output / 'dense-probes.safetensors')
            expansion = widen_mlp(model.get_base_model().model.layers[0].mlp, 8192, layer_index=0)
            model.config.intermediate_size = 8192
            report['reference_expansion'] = expansion
        else:
            built = build_bounded_model(config, source, target_width=8192, rank=64, alpha=16, adapter_seed=731)
            model = built.model
            report['bridge_receipt'] = built.receipt
            del built
        report['build_seconds'] = time.monotonic() - build_start
        report['build_memory'] = rss()
        report['construction_peak_includes_dense_function_probe'] = args.mode == 'reference'
        stage('expanded_subset_built', parameter_count=sum(p.numel() for p in model.parameters()),
              trainable_count=sum(p.numel() for p in model.parameters() if p.requires_grad))
        report['initial_parameter_sha256'] = parameter_hashes(model)
        report['initial_buffer_sha256'] = {n: tensor_sha256(v) for n, v in model.named_buffers()}
        original_frozen = parameter_hashes(model, trainable=False)
        initial_probe = probes(model)
        save_file(initial_probe, args.output / 'initial-probes.safetensors')
        if args.mode == 'reference':
            report['dense_width_max_abs_gaps'] = {name: float((dense_probe[name] - value).abs().max())
                                                for name, value in initial_probe.items()}
            need(report['dense_width_max_abs_gaps']['full_logits'] <= 1e-4
                 and report['dense_width_max_abs_gaps']['cached_logits'] <= 1e-4
                 and report['dense_width_max_abs_gaps']['mlp_output'] <= 1e-4
                 and report['dense_width_max_abs_gaps']['mlp_input_gradient'] <= 1e-5,
                 'official subset dense-width preservation tolerance exceeded')
            del dense_probe
        stage('initial_exact_tensor_and_function_receipts_recorded')
        parameters = [p for p in model.parameters() if p.requires_grad]
        optimizer = torch.optim.AdamW(parameters, lr=2e-5, weight_decay=.01, foreach=False)
        ids = torch.tensor([[14, 11, 10, 1, 2, 15, 10, 14, 12, 10]])
        report['updates'] = []
        for step in range(2):
            model.train(); optimizer.zero_grad(set_to_none=True)
            recomputations = []
            hook = model.get_base_model().model.layers[0].mlp.register_forward_pre_hook(
                lambda *_: recomputations.append(True))
            with full_precision_compute('cpu'):
                logits = model(ids, use_cache=False).logits
                # Synthetic token labels exercise the real gradients; this is
                # neither ARC training data nor a capability/gain evaluation.
                loss = torch.nn.functional.cross_entropy(logits[:, :-1].reshape(-1, 16), ids[:, 1:].reshape(-1))
                loss.backward()
            hook.remove()
            need(len(recomputations) >= 2, 'actual backward checkpoint recomputation required')
            gradients = {n: p.grad for n, p in model.named_parameters() if p.requires_grad}
            need(all(value is not None and bool(torch.isfinite(value).all()) for value in gradients.values()),
                 'complete finite trainable gradients required')
            need(all(p.grad is None for p in model.parameters() if not p.requires_grad), 'native gradient detected')
            if step == 1:
                need(all(bool(value.count_nonzero()) for name, value in gradients.items() if '.lora_A.' in name),
                     'nonzero LoRA-A gradients after real zero-B update required')
            m = model.get_base_model().model.layers[0].mlp
            selected, _ = replica_indices(6144, 8192, 0)
            gate_b_grad = m.gate_proj.lora_B['default'].weight.grad
            differentiated = int(((gate_b_grad[selected] - gate_b_grad[6144:]).norm(dim=1) > 0).sum())
            need(differentiated == 2048, 'all added gate-B rows must have distinct paired gradients')
            row = {'step': step + 1, 'loss': float(loss.detach()), 'differentiated_gate_B_pairs': differentiated,
                   'mlp_forward_calls_including_recompute': len(recomputations),
                   'gradient_sha256': {name: tensor_sha256(value) for name, value in gradients.items()},
                   'gradient_nonzero': {name: bool(value.count_nonzero()) for name, value in gradients.items()}}
            optimizer.step(); optimizer.zero_grad(set_to_none=True)
            row['trainable_after_sha256'] = parameter_hashes(model, trainable=True)
            report['updates'].append(row)
            stage('finite_real_update_completed', step=step + 1, loss=row['loss'])
            del logits, loss, gradients, gate_b_grad, m, selected
        need(parameter_hashes(model, trainable=False) == original_frozen, 'frozen official native tensor changed')
        report['final_parameter_sha256'] = parameter_hashes(model)
        trainables = {n: p.detach().clone() for n, p in model.named_parameters() if p.requires_grad}
        checkpoint = args.output / 'trainables.safetensors'
        save_file(trainables, checkpoint)
        report['checkpoint'] = {'sha256': sha_file(checkpoint), 'bytes': checkpoint.stat().st_size,
            'tensor_count': len(trainables), 'not_a_WidthEngine_checkpoint': True}
        final_probe = probes(model)
        save_file(final_probe, args.output / 'final-probes.safetensors')
        expected_parameters = report['final_parameter_sha256']
        del model, optimizer, parameters, trainables, initial_probe
        trim()
        stage('first_model_released_before_reload')
        fresh = build_bounded_model(config, source, target_width=8192, rank=64, alpha=16, adapter_seed=731).model
        with torch.no_grad():
            loaded = load_file(checkpoint)
            expected_names = {n for n, p in fresh.named_parameters() if p.requires_grad}
            need(set(loaded) == expected_names, 'complete exact trainable checkpoint inventory required')
            for name, p in fresh.named_parameters():
                if p.requires_grad:
                    need(tuple(loaded[name].shape) == tuple(p.shape) and loaded[name].dtype == p.dtype,
                         'reload tensor metadata differs')
                    p.copy_(loaded[name])
        need(parameter_hashes(fresh) == expected_parameters, 'fresh reconstruction/reload tensor hashes differ')
        replay = probes(fresh)
        report['fresh_reload_probe_bitwise_equal'] = {name: torch.equal(value, replay[name]) for name, value in final_probe.items()}
        need(all(report['fresh_reload_probe_bitwise_equal'].values()), 'fresh reload function or input gradient differs')
        need(report['code_sha256'] == {name: sha_file(repo / name) for name in code_files},
             'source changed during bounded evidence run')
        report['success'] = True
        stage('fresh_reload_exact_hash_function_and_gradient_verified')
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
        persist()
        raise
    finally:
        persist()
        signal.alarm(0)


if __name__ == '__main__':
    main()
