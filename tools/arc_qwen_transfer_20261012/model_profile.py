"""Explicit C4096 successor admission; historical C2048 material stays immutable.

This source-declared addendum is a review target, not independent review or GPU
fit evidence. A release must bind these exact bytes and its addendum digest.
The original composite loader is reused solely for unchanged material, runtime,
and load-coverage checks after the additional 4096 memory gate passes.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import math
import os
from pathlib import Path
import time
import weakref

from tools.arc_learning_agent_20261011.qwen14b_profiles import (
    MODEL_KEY, MODEL_ID, REVISION, VOCAB_SIZE, EOS_IDS, SMALL_FILES,
    HF_LICENSE_SHA256, authenticate_small_assets,
)
from tools.arc_learning_agent_20261011.qwen14b_contract import canonical
from tools.arc_qwen_probe_20261012.protocol import require, checked_json
from tools.arc_qwen_probe_20261012.admission import (
    CONTRACT_SHA256 as BASE_CONTRACT_SHA256, DEPLOYMENT_ID as BASE_DEPLOYMENT_ID,
)

PROFILE_ID = 'qwen3-14b-native-bf16-r8-c4096-transfer-v1'
DEPLOYMENT_ID = 'qwen3-14b-kaggle-v1-hf40c069-bf16-r8-c4096-transfer-20261012'
CONTEXT_LIMIT, PROMPT_CAP, OUTPUT_CAP = 4096, 3072, 1024
LENGTH_LADDER = (128, 512, 2048, 4096)


def profile():
    return {'profile_id': PROFILE_ID, 'model_key': MODEL_KEY, 'model_id': MODEL_ID,
            'revision': REVISION, 'context_limit': CONTEXT_LIMIT,
            'prompt_cap': PROMPT_CAP, 'output_cap': OUTPUT_CAP,
            'full_vocabulary_rows': VOCAB_SIZE, 'precision': 'bf16-base-fp32-lora',
            'lora_rank': 8, 'lora_alpha': 16, 'lora_dropout': 0.0,
            'batch_size': 1, 'tensor_parallel_size': 1,
            'attention_backend': 'sdpa', 'max_position_embeddings_unchanged': 40960,
            'pretrained_loading_default': False, 'production_admitted': False,
            'g4_fit_measured': False, 'four_l4_tp_admitted': False,
            'fp8_admitted': False, 'full_public167_coverage_admitted': False,
            'public_solving_admitted': False}


def memory_estimate(config, inventory, *, sequence_length=CONTEXT_LIMIT,
                    adapter_rank=8, batch_size=1):
    """Full-head loss bound at4096; analytic allowance, never measured fit."""
    exact = {'model_type': 'qwen3', 'num_hidden_layers': 40, 'hidden_size': 5120,
             'intermediate_size': 17408, 'vocab_size': VOCAB_SIZE,
             'num_attention_heads': 40, 'num_key_value_heads': 8, 'head_dim': 128}
    require(all(config.get(k) == v for k, v in exact.items()), 'exact Qwen14B topology required')
    require(type(sequence_length) is int and sequence_length == CONTEXT_LIMIT and
            type(adapter_rank) is int and adapter_rank == 8 and
            type(batch_size) is int and batch_size == 1, 'fixed4096/rank8/batch1 memory bound required')
    require(len(inventory) == 443 and all(e.get('dtype') == 'BF16' and
            type(e.get('elements')) is int and e['elements'] > 0 for e in inventory.values()),
            'complete443 BF16 tensor inventory required')
    elements = sum(e['elements'] for e in inventory.values())
    require(elements == 14768307200, 'exact Qwen14B parameter element count required')
    layers, h, inter, hd, heads, kv_heads = 40, 5120, 17408, 128, 40, 8
    adapter_elements = layers * adapter_rank * (
        3 * (h + inter) + 4 * h + 2 * heads * hd + 2 * kv_heads * hd)
    parts = {'base_weights_bytes': elements * 2,
             'kv_bytes': 2 * layers * kv_heads * hd * sequence_length * 2,
             'recurrent_bytes': 0, 'convolution_bytes': 0,
             'adapter_training_bytes': adapter_elements * 16,
             'full_logits_loss_bytes': batch_size * sequence_length * VOCAB_SIZE * 12,
             'activation_allowance_bytes': layers * sequence_length * h * 2 * 8,
             'allocator_workspace_reserve_bytes': 8 * 2**30}
    return {**parts, 'adapter_parameter_elements': adapter_elements,
            'estimated_required_bytes': sum(parts.values()), 'measured': False,
            'memory_fit_guaranteed': False,
            'scope': 'Analytic4096 allowance: BF16 base/KV; FP32 rank8 adapters, gradients and Adam; full151936-head logits/loss scratch; checkpointed activations.'}


# Exact, separately reviewable override. All other composite material clauses,
# byte inventories, HF assets, environment and hardware identity stay unchanged.
MATERIAL_ADDENDUM = {
    'format': 'irisx/qwen14b-c4096-material-addendum-v1',
    'status': 'prepared-for-independent-review-not-self-authorizing',
    'base_contract_sha256': BASE_CONTRACT_SHA256,
    'base_deployment_id': BASE_DEPLOYMENT_ID,
    'deployment_id': DEPLOYMENT_ID,
    'successor_profile': profile(),
    'overrides': {
        'profile_id': {'before': 'qwen3-14b-native-bf16-r8-c2048-probe-v1', 'after': PROFILE_ID},
        'probe_bounds.context_limit': {'before': 2048, 'after': CONTEXT_LIMIT},
        'probe_bounds.prompt_cap': {'before': 1792, 'after': PROMPT_CAP},
        'probe_bounds.output_cap': {'before': 256, 'after': OUTPUT_CAP},
        'hardware.memory_estimate.sequence_length': {'before': 2048, 'after': CONTEXT_LIMIT},
        'probe_bounds.maximum_probe_seconds': {'before': 10800, 'after': 43200},
        'hardware.cache_tolerance_scope': {
            'before': 'Predeclared bounded BF16 allclose ceilings; must actually pass on full vocabulary at the native probe sequence lengths both before and after optimizer update; no automatic widening.',
            'after': 'Fixed .01/.01 full151936-logit allclose remains recorded diagnostic. Cached admission requires finite complete heads, native cache/mask/position invariants, bitwise repeat-full reference, exact unconstrained argmax and grid-DFA greedy choices across multi-step base/updated/restored controls at every128/512/2048/4096 rung. Top8 logits/ranks and margins remain recorded; no numerical-tolerance widening. Choice mismatch denies cached mode; invalid, late, nonfinite, nondeterministic-reference or reset failure denies all science.'},
    },
    'base_hardware_descriptor_sha256': 'd377d42980938f6c87967e87bef5d9da9ba9467dc12fdb41c241dd49b4fe9362',
    'environment_lock_sha256': 'da56c7221914a54e87d344956ddb87d8df16a58a09dd21b1051b37598948bfd0',
    'tensor_inventory_sha256': '71be71b8cfe4957190aeb7d8774e0080c5a3dca194a94f3d3db2c3965d91575e',
    'hf_config_sha256': SMALL_FILES['config.json'],
    'loss_policy': 'completion-only causal loss; entire151936 vocabulary; no row or head truncation',
    'metering': {'training_sequence_reservation': CONTEXT_LIMIT,
                 'scoring_input_reservation': CONTEXT_LIMIT,
                 'generation_input_reservation': 'sum(3072+i for i in range(requested_output_tokens)); settle actual physical forward tokens',
                 'failed_or_unknown_work_remains_charged': True},
    'memory_estimate': {
        'base_weights_bytes': 29536614400, 'kv_bytes': 671088640,
        'recurrent_bytes': 0, 'convolution_bytes': 0,
        'adapter_parameter_elements': 32112640, 'adapter_training_bytes': 513802240,
        'full_logits_loss_bytes': 7467958272, 'activation_allowance_bytes': 13421772800,
        'allocator_workspace_reserve_bytes': 8589934592,
        'estimated_required_bytes': 60201170944, 'measured': False,
        'free_memory_reserve_bytes': 4294967296},
    'calibration': {'length_ladder': list(LENGTH_LADDER), 'updates_per_rung': 1,
                    'states': ['base', 'updated', 'restored'],
                    'full_head_rows': VOCAB_SIZE, 'atol': 0.01, 'rtol': 0.01,
                    'exact4096_required_before_science': True,
                    'finite_backward_and_optimizer_required': True,
                    'complete_training_state_restore_required': True,
                    'strict_allclose_is_separate_diagnostic': True,
                    'cache_requires_exact_behavioral_choices': True,
                    'invalid_late_nonfinite_or_reference_repeat_failure': 'fatal',
                    'behavioral_cache_mismatch': 'full-prefix-only-if-separately-budgeted',
                    'maximum_calibration_seconds': 1800},
    'all_other_material_clauses_unchanged': True,
    'session_clock_changes_authorized_by_this_addendum': True,
    'clock_policy': 'At most43200s including queue, setup, all loads/reloads, calibration, learning, inference, scoring and closure; no reset. Individual load and calibration phases remain bounded1800s. No execution authority is created.',
    'not_execution_authorization': True,
}
MATERIAL_ADDENDUM_SHA256 = hashlib.sha256(canonical(MATERIAL_ADDENDUM)).hexdigest()
_LOADED = weakref.WeakKeyDictionary()


def material_addendum():
    require(hashlib.sha256(canonical(MATERIAL_ADDENDUM)).hexdigest() == MATERIAL_ADDENDUM_SHA256,
            'source-bound successor material addendum mutated')
    return deepcopy(MATERIAL_ADDENDUM)


def validate_model_config(config):
    config = dict(config)
    require(config.get('model_key') == MODEL_KEY and config.get('profile_id') == PROFILE_ID,
            'exact distinct C4096 successor profile required')
    require(type(config.get('tiny_cpu', False)) is bool, 'explicit boolean tiny_cpu policy required')
    for name, expected in (('context_limit', CONTEXT_LIMIT), ('prompt_cap', PROMPT_CAP),
                           ('output_cap', OUTPUT_CAP), ('tensor_parallel_size', 1)):
        require(type(config.get(name, expected)) is int and config.get(name, expected) == expected,
                'fixed successor ' + name + ' differs')
        config[name] = expected
    require(config.get('precision', 'bf16-base-fp32-lora') == 'bf16-base-fp32-lora',
            'only BF16 base and FP32 rank8 LoRA admitted')
    require(config.get('material_addendum_sha256') == MATERIAL_ADDENDUM_SHA256,
            'exact successor material addendum digest required')
    material_addendum()
    return config


def _legacy_loading_config(config):
    """Material-only compatibility projection; never used for successor science."""
    return {**config, 'profile_id': 'qwen3-14b-native-bf16-r8-c2048-probe-v1',
            'reviewed_deployment_id': BASE_DEPLOYMENT_ID,
            'context_limit': 2048, 'prompt_cap': 1792, 'output_cap': 256}


def select_deployment(config):
    config = validate_model_config(config)
    require(config.get('enabled') is True and config.get('reviewed_deployment_id') == DEPLOYMENT_ID,
            'successor pretrained loading is default-disabled and exact-deployment only')
    from tools.arc_qwen_probe_20261012.admission import select_deployment as select_base
    select_base(_legacy_loading_config(config))
    c = checked_json(config['contract_path'], BASE_CONTRACT_SHA256)
    hardware = checked_json(Path(config['contract_path']).absolute().parent / c['hardware']['path'],
                            MATERIAL_ADDENDUM['base_hardware_descriptor_sha256'])
    require(hardware['cache_tolerance_scope'] == MATERIAL_ADDENDUM['overrides']['hardware.cache_tolerance_scope']['before'] and
            hardware['cache_atol'] == hardware['cache_rtol'] == 0.01,
            'cache-scope predecessor or unchanged numeric tolerances differ')
    for path, change in MATERIAL_ADDENDUM['overrides'].items():
        if path.startswith('hardware.'):
            continue  # source-pinned hardware predecessor checked above
        observed = c
        for part in path.split('.'):
            observed = observed[part]
        require(observed == change['before'], 'successor override predecessor differs: ' + path)
    require(c['hardware']['sha256'] == MATERIAL_ADDENDUM['base_hardware_descriptor_sha256'] and
            c['environment']['sha256'] == MATERIAL_ADDENDUM['environment_lock_sha256'] and
            c['expected_tensor_inventory']['sha256'] == MATERIAL_ADDENDUM['tensor_inventory_sha256'],
            'unchanged predecessor descriptors differ')
    return {'profile_id': PROFILE_ID, 'reviewed_deployment_id': DEPLOYMENT_ID,
            'material_addendum_sha256': MATERIAL_ADDENDUM_SHA256,
            'base_contract_sha256': BASE_CONTRACT_SHA256,
            'admission_phase': 'first-bounded-c4096-calibration',
            'production_admitted': False, 'context4096_measured': False}


def load_pretrained(config):
    config = validate_model_config(config)
    selected = select_deployment(config)
    deadline = config.get('_owned_probe_deadline')
    require(type(deadline) in (int, float) and math.isfinite(deadline) and
            0 < deadline - time.monotonic() <= 1800 and
            config.get('_owned_probe_supervisor_pid') == os.getppid() and
            config.get('_owned_probe_scope') == 'qwen14b-capability-only',
            'bounded owned1800s successor loader required')
    from tools.arc_qwen_probe_20261012 import admission as base
    c = checked_json(config['contract_path'], BASE_CONTRACT_SHA256)
    root = Path(config['contract_path']).absolute().parent
    # Validate runtime before the first native import, as the original loader does.
    base.validate_environment(config, c, deadline)
    cfg = checked_json(root / 'hf-overlay/config.json', SMALL_FILES['config.json'])
    inventory = base._descriptor(root, c, 'expected_tensor_inventory')['tensors']
    h = base._descriptor(root, c, 'hardware')
    estimate = memory_estimate(cfg, inventory)
    for key, expected in MATERIAL_ADDENDUM['memory_estimate'].items():
        if key != 'free_memory_reserve_bytes':
            require(estimate[key] == expected, 'successor memory calculus differs: ' + key)
    import torch
    require(torch.cuda.is_available() and torch.cuda.device_count() == 1 and torch.cuda.is_bf16_supported(),
            'exact single BF16 CUDA device required')
    prop = torch.cuda.get_device_properties(0)
    actual = {'name': prop.name, 'total_memory_bytes': prop.total_memory,
              'capability': list(torch.cuda.get_device_capability(0))}
    require(actual == h['hardware'], 'successor hardware identity differs')
    free, total = torch.cuda.mem_get_info(0)
    require(total == prop.total_memory and free >= estimate['estimated_required_bytes'] +
            MATERIAL_ADDENDUM['memory_estimate']['free_memory_reserve_bytes'],
            '4096 analytic estimate plus4GiB reserve unavailable before loading')
    # Original checks still verify all weights, overlay, exact environment,
    # driver, metadata, native loading coverage and BF16 placement unchanged.
    model, tokenizer, identity, hardware = base.load_composite(_legacy_loading_config(config))
    try:
        require(time.monotonic() < deadline, 'successor deadline expired during material loading')
        identity = {**identity, **selected, 'execution_mode': 'native-qwen3-pretrained-c4096-transfer',
                    'predecessor_material_contract_sha256': BASE_CONTRACT_SHA256,
                    'context_limit': CONTEXT_LIMIT, 'prompt_cap': PROMPT_CAP, 'output_cap': OUTPUT_CAP}
        hardware = {**hardware, 'predecessor_estimate': hardware['estimate'], 'estimate': estimate,
                    'successor_free_bytes_before_load': free, 'context4096_measured': False,
                    'g4_fit_measured': False, 'memory_fit_guaranteed': False}
        _LOADED[model] = {'tokenizer': tokenizer, 'config': config, 'identity': identity, 'hardware': hardware}
        return model, tokenizer
    except BaseException:
        del model
        torch.cuda.empty_cache()
        raise


def consume_load_evidence(model, tokenizer, config):
    evidence = _LOADED.pop(model, None)
    require(evidence is not None and evidence['tokenizer'] is tokenizer and
            evidence['config'] == validate_model_config(config),
            'native successor requires exact once-consumed verified loader evidence')
    return deepcopy(evidence['identity']), deepcopy(evidence['hardware'])
