"""Owned, official-2B-only matched-control diagnostic and private closure.

The historical ``2b-S`` label is an ownership slot, not a scientific arm. All
four treatments live inside one fresh matched worker. This CPU coordinator
never imports torch, loads weights, probes a model, reads evaluator answers,
selects a PUBLIC ensemble, or changes devices/security/provider resources.
"""
from __future__ import annotations

import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
from .precision_contract import (LEGACY_POLICY, FP32_HEAD_POLICY, FP32_BACKBONE_POLICY,
                                 admit_policy, bind_trainable_contract)

from tools.arc2_goal_sprint_20261017.data import canonical, digest, valid_grid
from tools.arc2_goal_sprint_20261017.launch import TRAINING_MANIFEST_SHA256, check_dataset_separation, require, sha, write_new
from .concurrency import run_wave
from .controller import model_bound, progress

WORKFLOW = WORKLOAD = 'compact-matched-controls-v1'
PREFLIGHT = 'first-seeded-microbatch-cached-and-full-v1'
ARMS = ('anchor', 'known_target_ce', 'exact_positive_ce', 'exact_centered_ddis')
JOB_ID = '2b-S'
GIB = 1024 ** 3
MAX_METADATA = 64 * 1024 ** 2
MAX_CONTROLS = 512 * 1024 ** 2
MAX_FILE = 2 * GIB
MAX_TOTAL = 10 * GIB
MAX_FILES = 10000
OUTER_CLOSURE_SECONDS = 180
STOP_SECONDS = 15
FINALIZATION_SECONDS = 30
LOAD_SECONDS = 600
EVALUATION_RESERVE_SECONDS = 3600
# Completed original single-2B fixed-work receipt, not a matched-workload probe:
# Its measured peak is 11,276,386,304 bytes; ceil(1.2 * peak) + 2 GiB
# is 15,679,147,213 bytes. Round free-device admission UP to 20 GiB.
# The distinct 4B diagnostic's 32 GiB rule is not evidence for this 2B job.
HISTORICAL_2B_PEAK = 11276386304
HISTORICAL_2B_RESERVATION = (6 * HISTORICAL_2B_PEAK + 4) // 5 + 2 * GIB
MIN_FREE_BYTES = 20 * GIB


def _sha256(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _pairs(values):
    result = {}
    for key, value in values:
        require(key not in result, 'duplicate JSON field forbidden')
        result[key] = value
    return result


def _decode(raw):
    def invalid(value):
        raise ValueError('nonfinite JSON number forbidden: ' + value)
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=invalid)


def _regular(path, *, limit=MAX_FILE):
    path = Path(path)
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'private artifact symlink forbidden')
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit,
            'bounded regular private artifact required')
    return path


def _json(path, *, limit=MAX_METADATA):
    return _decode(_regular(path, limit=limit).read_bytes())


def _relative(root, name):
    require(type(name) is str and bool(name), 'explicit private artifact path required')
    path = Path(name)
    require(not path.is_absolute() and '..' not in path.parts and path.as_posix() == name
            and name not in {'.', ''}, 'safe relative private artifact path required')
    return _regular(Path(root) / path)


def _artifact(root, name, receipt):
    path = _relative(root, name)
    require(type(receipt) is dict and type(receipt.get('bytes')) is int
            and receipt['bytes'] == path.stat().st_size and _sha256(receipt.get('sha256'))
            and sha(path) == receipt['sha256'], 'private artifact bytes or SHA differs')
    return path


def phase_plan(config, now):
    """Reserve original-session phases, never a quota-hour admission policy."""
    start, end = config.get('started_epoch'), config.get('deadline_epoch')
    require(_finite(start) and _finite(end) and _finite(now)
            and 0 < start <= now < end and end == start + 43200,
            'finite original 43200-second session deadline required')
    wave_end = end - OUTER_CLOSURE_SECONDS
    worker_end = wave_end - STOP_SECONDS - FINALIZATION_SECONDS
    reserve = max(EVALUATION_RESERVE_SECONDS, (worker_end - now) / 2)
    screen_end = worker_end - reserve
    require(screen_end - now > LOAD_SECONDS + 600,
            'insufficient original-session time for load, collection/updates, heldout generation and closure')
    return {'original_started_epoch': start, 'original_deadline_epoch': end,
            'wave_deadline_epoch': wave_end, 'worker_deadline_epoch': worker_end,
            'screen_deadline_epoch': screen_end, 'evaluation_deadline_epoch': worker_end,
            'heldout_reserve_seconds': reserve, 'load_timeout_seconds': LOAD_SECONDS,
            'outer_closure_reserve_seconds': OUTER_CLOSURE_SECONDS,
            'worker_finalization_reserve_seconds': FINALIZATION_SECONDS,
            'owned_stop_reserve_seconds': STOP_SECONDS, 'quota_hours_queried': False,
            'measured_full_workload_feasibility_claimed': False}


def _topology(topology):
    require(type(topology) is dict and topology.get('measured') is True
            and type(topology.get('device_count')) is int and topology['device_count'] == 1
            and type(topology.get('device_identity')) is str and bool(topology['device_identity'].strip())
            and topology.get('hardware_partition_claimed') is False,
            'one measured, unpartitioned device required')
    total, free = topology.get('total_bytes'), topology.get('free_bytes')
    require(type(total) is int and type(free) is int and 0 <= free <= total
            and free >= MIN_FREE_BYTES and total * 4 // 5 >= HISTORICAL_2B_RESERVATION,
            'official 2B diagnostic requires one device with20GiB free and the measured2B allocator envelope')
    label = (topology['device_identity'] + ' ' + str(topology.get('name', ''))).upper()
    require('MIG-' not in label and 'MIG ' not in label, 'MIG memory is not the admitted whole-device recipe')


def _official_tensor_contract():
    """Exact FP32 rank64 trainables for the admitted 28-layer 2B model."""
    names = {'base_model.model.lm_head.modules_to_save.default.weight': [16, 2048],
             'base_model.model.model.embed_tokens.modules_to_save.default.weight': [16, 2048]}
    projections = {'self_attn.q_proj': (2048, 2048), 'self_attn.k_proj': (1024, 2048),
                   'self_attn.v_proj': (1024, 2048), 'self_attn.o_proj': (2048, 2048),
                   'mlp.gate_proj': (6144, 2048), 'mlp.up_proj': (6144, 2048),
                   'mlp.down_proj': (2048, 6144)}
    for layer in range(28):
        for projection, (out_dim, in_dim) in projections.items():
            prefix = f'base_model.model.model.layers.{layer}.{projection}'
            names[prefix + '.lora_A.default.weight'] = [64, in_dim]
            names[prefix + '.lora_B.default.weight'] = [out_dim, 64]
    return {name: {'shape': shape, 'dtype': 'torch.float32'} for name, shape in names.items()}


def _official_model_shape():
    return {'variant': '2b', 'model_type': 'qwen3', 'vocab_size': 16, 'num_hidden_layers': 28,
            'hidden_size': 2048, 'num_attention_heads': 16, 'num_key_value_heads': 8,
            'head_dim': 128, 'intermediate_size': 6144}



def _official_model_contract():
    """Pure equivalent of the engine's admitted official2B model contract."""
    return {**_official_model_shape(), 'tie_word_embeddings': False, 'attention_dropout': 0.,
        'attention_bias': False, 'hidden_act': 'silu', 'rms_norm_eps': 1e-6,
        'max_position_embeddings': 262144, 'layer_types': ['full_attention'] * 28,
        'bos_token_id': 13, 'eos_token_id': 15,
        'rope_parameters': {'rope_type': 'default', 'rope_theta': 5000000,
                            'mrope_interleaved': True, 'mrope_section': [24, 20, 20]}}


def _official_trainable_contract(probability_policy=LEGACY_POLICY):
    policy = admit_policy(probability_policy)
    tensors = _official_tensor_contract()
    # This describes resident frozen parameters, not the unchanged BF16 source
    # checkpoint. Head-only and legacy policies keep the backbone in BF16.
    frozen_dtype = 'torch.float32' if policy == FP32_BACKBONE_POLICY else 'torch.bfloat16'
    return bind_trainable_contract({'tensors': tensors, 'tensor_count': len(tensors),
        'parameter_count': sum(math.prod(row['shape']) for row in tensors.values()),
        'frozen_dtype': frozen_dtype, 'trainable_dtype': 'torch.float32',
        'rank': 64, 'alpha': 16, 'use_rslora': True,
        'target_modules': ['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],
        'modules_to_save': ['embed_tokens', 'lm_head']}, policy)


def _official_tokenizer_admission():
    # Same exact encode/decode probe contract as CompactEngine, without loading
    # transformers/torch in the coordinator or weakening the runtime admission.
    probes = {'0123456789\n': list(range(11)), 'user': [11], 'assistant': [12],
        '<|endoftext|>': [13], '<|im_start|>': [14], '<|im_end|>': [15],
        '<|im_start|>user\n12\n34<|im_end|>\n<|im_start|>assistant\n':
            [14, 11, 10, 1, 2, 10, 3, 4, 15, 10, 14, 12, 10],
        '56\n78<|im_end|>': [5, 6, 10, 7, 8, 15]}
    return {'vocab_size': 16, 'eos_token_id': 15, 'pad_token_id': 13,
            'probe_sha256': hashlib.sha256(canonical(probes) + b'\n').hexdigest()}


def _verify_tensor_file(path, manifest, probability_policy=LEGACY_POLICY, *,
                        expected_tensors=None, expected_trainable_contract=None):
    """Stream safe tensor bytes; no pickle, torch, base-model load or CUDA."""
    # Override is an internal verifier dependency for independently admitted
    # contracts/tests, never taken from the artifact or worker configuration.
    require((expected_tensors is None) == (expected_trainable_contract is None),
            'both independently admitted tensor and trainable contracts required')
    expected = _official_tensor_contract() if expected_tensors is None else expected_tensors
    expected_contract = (_official_trainable_contract(probability_policy)
                         if expected_trainable_contract is None else expected_trainable_contract)
    inventory = manifest.get('trainable_tensors')
    contract = manifest.get('trainable_contract', {})
    require(type(inventory) is dict and set(inventory) == set(expected)
            and contract == expected_contract,
            'exact official2B named trainables and rsLoRA contract required')
    state_hash = hashlib.sha256()
    with path.open('rb') as stream:
        length_bytes = stream.read(8)
        require(len(length_bytes) == 8, 'complete safetensors length required')
        length = int.from_bytes(length_bytes, 'little')
        require(2 <= length <= 8 * 1024**2, 'bounded safetensors header required')
        header = _decode(stream.read(length))
        require(type(header) is dict and set(header) - {'__metadata__'} == set(expected),
                'exact safetensors tensor inventory required')
        offset = 0
        for name in sorted(expected, key=lambda name: header[name].get('data_offsets', [MAX_FILE])[0]):
            tensor = header[name]
            shape = expected[name]['shape']
            size = math.prod(shape) * 4
            require(type(tensor) is dict and set(tensor) == {'dtype', 'shape', 'data_offsets'}
                    and tensor['dtype'] == 'F32' and tensor['shape'] == shape
                    and type(tensor['data_offsets']) is list
                    and all(type(n) is int for n in tensor['data_offsets'])
                    and tensor['data_offsets'] == [offset, offset + size],
                    'contiguous exact FP32 safetensors shape/offsets required')
            offset += size
        require(8 + length + offset == path.stat().st_size, 'safetensors trailing or missing data forbidden')
        for name in sorted(expected):
            shape, offset = expected[name]['shape'], header[name]['data_offsets'][0]
            require(type(inventory[name]) is dict and set(inventory[name]) == {'shape', 'dtype', 'sha256'}
                    and {k: inventory[name][k] for k in ('shape', 'dtype')} == expected[name],
                    'checkpoint tensor contract differs')
            state_hash.update(name.encode()); state_hash.update(str(tuple(shape)).encode())
            tensor_hash = hashlib.sha256()
            stream.seek(8 + length + offset)
            remaining = math.prod(shape) * 4
            while remaining:
                raw = stream.read(min(1024**2, remaining))
                require(bool(raw) and len(raw) % 4 == 0, 'complete aligned tensor bytes required')
                values = array.array('f'); values.frombytes(raw)
                if sys.byteorder != 'little':
                    values.byteswap()
                require(all(math.isfinite(value) for value in values), 'nonfinite checkpoint tensor forbidden')
                state_hash.update(raw); tensor_hash.update(raw); remaining -= len(raw)
            require(tensor_hash.hexdigest() == inventory[name]['sha256'], 'checkpoint tensor SHA differs')
    require(state_hash.hexdigest() == manifest.get('state_sha256'), 'checkpoint full state SHA differs')


def _verify_export(root, arm, export, source_identity, model_identity, probability_policy=LEGACY_POLICY):
    require(type(export) is dict and export.get('status') == 'complete', 'completed arm export required')
    checkpoint = export.get('checkpoint', {})
    expected_root = Path(root) / 'checkpoints' / arm
    require(type(checkpoint) is dict and type(checkpoint.get('root')) is str
            and Path(checkpoint['root']).absolute() == expected_root.absolute()
            and _sha256(checkpoint.get('manifest_sha256'))
            and _sha256(checkpoint.get('state_sha256'))
            and export.get('state_sha256') == checkpoint['state_sha256'],
            'export path and exact state binding required')
    manifest_path = _regular(expected_root / 'manifest.json', limit=8 * 1024**2)
    require({p.name for p in expected_root.iterdir()} == {'manifest.json', 'trainable_state.safetensors'},
            'exact checkpoint file inventory required')
    raw = manifest_path.read_bytes(); manifest = _decode(raw)
    require(raw == canonical(manifest) + b'\n' and sha(manifest_path) == checkpoint['manifest_sha256'],
            'canonical pinned checkpoint manifest required')
    required = {'format', 'base_identity', 'model_contract', 'trainable_contract', 'tokenizer_admission',
                'origin', 'trainable_tensors', 'state_sha256', 'file', 'optimizer_resumed', 'rng_resumed',
                'fresh_optimizer_required'}
    require(set(manifest) == required and manifest['format'] == 'irisx/nvarc-compact-trainable-v1'
            and manifest['base_identity'] == model_identity and model_bound(manifest['base_identity'], '2b')
            and manifest['state_sha256'] == checkpoint['state_sha256']
            and manifest['optimizer_resumed'] is False and manifest['rng_resumed'] is False
            and manifest['fresh_optimizer_required'] is True,
            'official model and fresh-optimizer export identity required')
    require(manifest['model_contract'] == _official_model_contract(), 'exact official2B model/rotary contract required')
    require(manifest['tokenizer_admission'] == _official_tokenizer_admission(),
            'exact compact tokenizer admission required')
    origin = manifest['origin']
    require(type(origin) is dict and origin.get('phase') == 'pre_public'
            and origin.get('public_labels_used') is False and origin.get('public_ttt_applied') is False
            and origin.get('source_identity') == source_identity and origin.get('job_id') == JOB_ID
            and origin.get('arm') == arm, 'source-bound no-PUBLIC arm export origin required')
    tensor_path = _regular(expected_root / 'trainable_state.safetensors')
    require(manifest['file'] == {'name': tensor_path.name, 'bytes': tensor_path.stat().st_size,
                                 'sha256': sha(tensor_path)}, 'checkpoint whole-file bytes or SHA differs')
    _verify_tensor_file(tensor_path, manifest, probability_policy)
    return manifest['state_sha256']


def _evaluation(evaluation, *, worker_root, artifacts, exports, parent_ids, target_digests):
    require(type(evaluation) is dict and type(evaluation.get('complete')) is bool
            and evaluation.get('full_requested_denominator') == 16
            and evaluation.get('requested_views') == 2
            and type(evaluation.get('arms')) is dict and set(evaluation['arms']) == set(ARMS),
            'fixed four-arm16-parent/two-view evaluation required')
    require(type(target_digests) is dict and set(target_digests) == set(parent_ids)
            and all(type(value) is str and re.fullmatch('sha256:[0-9a-f]{64}', value) for value in target_digests.values()),
            'pre-collection held-target digest mapping required')
    panels, complete, scores = [], [], {}
    for arm in ARMS:
        report = evaluation['arms'][arm]
        require(type(report) is dict and type(report.get('complete')) is bool
                and report.get('requested_parents') == 16
                and type(report.get('records')) is list and len(report['records']) <= 16,
                'full requested evaluation denominator required')
        records = report['records']; ids = []
        for row in records:
            require(type(row) is dict and type(row.get('parent_id')) is str and row['parent_id'] not in ids
                    and type(row.get('complete')) is bool and type(row.get('completed_views')) is int
                    and 0 <= row['completed_views'] <= 2
                    and row['complete'] == (row['completed_views'] == 2)
                    and type(row.get('valid')) is bool
                    and type(row.get('pass1')) is int and type(row.get('pass2')) is int
                    and 0 <= row['pass1'] <= row['pass2'] <= int(row['valid']),
                    'unique generated heldout record with explicit view completeness required')
            ids.append(row['parent_id'])
            require(row.get('target_digest') == target_digests[row['parent_id']],
                    'held-target digest differs from pre-collection protocol')
            if row['completed_views'] or row.get('prediction_artifact') is not None:
                artifact = row.get('prediction_artifact', {})
                name = f'predictions/{arm}/{row["parent_id"]}.json'
                require(artifact.get('path') == name and artifacts.get(name) == artifact,
                        'bound heldout raw prediction artifact required')
                raw = _json(_artifact(worker_root, name, artifact))
                verified = row.get('verification', {})
                require(verified.get('verified') is True and verified.get('completed_views') == row['completed_views']
                        and verified.get('result_sha256') == hashlib.sha256(canonical(raw)).hexdigest()
                        and raw.get('complete') == row['complete'] and type(raw.get('views')) is list
                        and len(raw['views']) == row['completed_views']
                        and row.get('state_sha256') == exports.get(arm, {}).get('state_sha256'),
                        'raw prediction verification or evaluated state differs')
                ranked, candidates, order = raw.get('ranked_grids'), raw.get('candidates'), raw.get('ranked_candidate_indices')
                require(type(ranked) is list and len(ranked) <= 2 and all(valid_grid(grid) for grid in ranked)
                        and type(candidates) is list and len(candidates) <= 2
                        and all(type(candidate) is dict and valid_grid(candidate.get('grid')) for candidate in candidates)
                        and type(order) is list
                        and all(type(index) is int and 0 <= index < len(candidates) for index in order)
                        and len(set(order)) == len(order)
                        and set(order) == set(range(len(candidates)))
                        and ranked == [candidates[index]['grid'] for index in order[:2]]
                        and type(verified.get('candidate_count')) is int and verified['candidate_count'] == len(candidates),
                        'bounded raw grids, rank and verified candidate count differ')
                target = target_digests[row['parent_id']]
                require(row['valid'] == bool(ranked)
                        and row['pass1'] == int(bool(ranked) and digest(ranked[0]) == target)
                        and row['pass2'] == int(any(digest(grid) == target for grid in ranked)),
                        'generated exact counts differ from retained grids and held-target digest')
            else:
                require(not row['valid'] and row['pass1'] == row['pass2'] == 0,
                        'unexecuted prediction cannot contribute exact accuracy')
        completed = sum(row['complete'] for row in records)
        require(type(report.get('complete_parents')) is int and report['complete_parents'] == completed
                and report['complete'] == (completed == 16)
                and all(type(report.get(key)) is int and report[key] == sum(int(row[key]) for row in records)
                        for key in ('pass1', 'pass2', 'valid')), 'evaluation aggregate differs from retained records')
        require(ids == parent_ids, 'every arm must retain the full fixed parent denominator')
        panels.append(ids); complete.append(report['complete']); scores[arm] = report['pass2']
    require(evaluation['complete'] == all(complete), 'evaluation complete flag differs')
    if all(complete):
        require(all(ids == panels[0] for ids in panels), 'matched generated heldout panels differ')
    return all(complete), scores


def _official_preflight_config():
    return {'tolerance': 0.05, 'microbatch': 2, 'seed': 0, 'generation_tokens': 931}


def _probability_preflight(matched, protocol, worker_root, artifacts):
    """Recompute the new early gate from retained numeric vectors, without ML.

    Historical v1 receipts had no preflight declaration. This compatibility
    path does not alter their original full-pool verification contract.
    """
    if 'probability_preflight' not in protocol:
        require('probability_preflight' not in matched, 'undeclared probability preflight')
        return True
    require(protocol['probability_preflight'] == PREFLIGHT, 'unknown probability preflight protocol')
    summary = matched.get('probability_preflight')
    if summary is None:
        require(matched['status'] != 'complete' and not matched['complete'] and matched.get('controls') is None,
                'missing preflight cannot admit collection or completion')
        return False
    name = 'matched-probability-preflight.json'
    require(name in artifacts, 'bound probability preflight artifact required')
    evidence = _json(Path(worker_root) / name)
    require(summary == {k: v for k, v in evidence.items() if k != 'probe'},
            'preflight summary differs from bound evidence')
    raw = evidence.get('probe', {})
    policy = admit_policy(protocol.get('probability_policy', LEGACY_POLICY))
    require(evidence.get('probability_policy', LEGACY_POLICY) == policy
            and (raw.get('context') or {}).get('probability_policy', LEGACY_POLICY) == policy,
            'preflight numerical policy differs from declared workflow')
    expected = _official_preflight_config()
    count, tolerance = expected['microbatch'], expected['tolerance']
    require(evidence.get('protocol') == PREFLIGHT and evidence.get('used_for_loss') is False
            and evidence.get('full_pool_verification_still_required') is True
            and all(evidence.get(k) == v for k, v in expected.items())
            and raw.get('training_authorized') is False,
            'official2B early diagnostic must preserve original frozen-policy admission')
    require(evidence.get('policy_before_sha256') == matched.get('anchor_policy_sha256')
            and _sha256(evidence.get('policy_before_sha256'))
            and _sha256(evidence.get('policy_after_sha256')), 'preflight full-policy binding differs')
    require(all(evidence.get('physical', {}).get(k) == 0 for k in ('optimizer_steps', 'optimizer_attempts')),
            'preflight must never update weights')
    def gap(pairs):
        differences = []
        for a, b in pairs:
            require(type(a) is list and type(b) is list and len(a) == len(b)
                    and all(_finite(v) for v in a + b), 'finite aligned preflight vectors required')
            differences.extend(abs(y - x) for x, y in zip(a, b))
        return max(differences) if differences else None
    trace = raw.get('trace', {})
    if trace.get('status') == 'completed':
        from .probability_trace import validate_trace, validate_rows
        validate_trace(trace, expected_trace_sha256=trace.get('sha256'))
        validate_rows(raw.get('rows'), trace)
        require(trace['sample'] is True and trace['batch_size'] == count
                and trace['max_new_tokens'] == expected['generation_tokens']
                and all(hashlib.sha256(canonical(prompt)).hexdigest() == evidence.get('prompt_ids_sha256')
                        for prompt in trace['prompts']), 'first sampled microbatch trace differs')
    else:
        require(raw.get('status') != 'completed' and not raw.get('rows'),
                'incomplete trace cannot provide admitted trajectories')
    cached = raw.get('cached_replay') or {}
    cached_steps = cached.get('steps', [])
    require(type(cached_steps) is list and len(cached_steps) <= len(trace.get('steps', [])),
            'cached replay exceeds captured trace')
    for index, row in enumerate(cached_steps):
        original = trace['steps'][index]
        require(row.get('step') == original.get('step')
                and row.get('retained') == original.get('retained')
                and row.get('selected_ids') == original.get('selected_ids')
                and row.get('behavior_log_probs') == original.get('selected_log_probs')
                and len(row.get('cached_log_probs', [])) == count,
                'cached replay must retain exact sampled selections and denominators')
    full = raw.get('full_replay', [])
    rows = raw.get('rows', [])
    require(type(full) is list and type(rows) is list and len(full) <= len(rows) <= count,
            'bounded early full replay required')
    for index, row in enumerate(full):
        original = rows[index]
        require(row.get('row_index') == index and row.get('completion_ids') == original.get('completion_ids')
                and len(row.get('full_log_probs', [])) == len(row.get('behavior_log_probs', [])) == len(original['completion_ids'])
                and row.get('behavior_log_probs') == original.get('behavior_log_probs', [])[original.get('prompt_length', 0):],
                'full replay must retain original sampled denominators')
    measured = {'cached_max_abs_logp_gap': gap([(r['behavior_log_probs'], r['cached_log_probs']) for r in cached_steps]),
                'full_max_abs_logp_gap': gap([(r['behavior_log_probs'], r['full_log_probs']) for r in full]),
                'full_path': raw.get('full_metrics')}
    additional_passed = True
    if policy == FP32_HEAD_POLICY:
        from .precision_contract import stable_probe_admission
        measured['additional_paths'], additional_passed = stable_probe_admission(raw, tolerance=tolerance, count=count)
    require(evidence.get('metrics') == measured and all(raw.get(k) == measured[k]
            for k in ('cached_max_abs_logp_gap', 'full_max_abs_logp_gap')),
            'preflight gap summary differs from measured raw vectors')
    passed = (additional_passed and raw.get('status') == 'completed' and cached.get('status') == 'completed'
        and len(full) == len(rows) == count and evidence['policy_before_sha256'] == evidence['policy_after_sha256']
        and 0 < len(cached_steps) == len(trace.get('steps', []))
        and raw.get('full_metrics', {}).get('tokens') == sum(len(r['completion_ids']) for r in rows)
        and evidence.get('engine_poisoned_after') is False
        and all(_finite(measured[k]) and 0 <= measured[k] <= tolerance
                for k in ('cached_max_abs_logp_gap', 'full_max_abs_logp_gap')))
    require(type(evidence.get('passed')) is bool and evidence['passed'] == passed
            and evidence.get('status') == raw.get('status'), 'preflight admission claim differs')
    require(passed or matched.get('controls') is None, 'failed preflight cannot admit collection')
    return passed


def validate_result(result, worker_root, *, source_identity, device_identity, phase_deadlines=None):
    """Validate persisted private evidence, not a callable's success flag."""
    require(type(result) is dict and result.get('mode') == 'matched' and result.get('job_id') == JOB_ID
            and result.get('source_identity') == source_identity and result.get('workload_identity') == WORKLOAD
            and result.get('device_identity') == device_identity and model_bound(result.get('model_identity'), '2b')
            and type(result.get('completed')) is bool, 'bound official2B matched worker result required')
    matched, receipt = result.get('matched'), result.get('matched_report', {})
    require(type(receipt) is dict and receipt.get('path') == 'matched-report.json', 'pinned matched report required')
    report_path = _artifact(worker_root, receipt['path'], receipt)
    require(_json(report_path) == matched and type(matched) is dict
            and matched.get('format') == 'irisx/nvarc-matched-workflow-v1'
            and type(matched.get('complete')) is bool and matched.get('status') in {'complete', 'partial', 'failed'}
            and matched.get('full_requested_denominator') == 16
            and matched.get('public_inference_performed') is False
            and matched.get('public_scoring_performed') is False
            and matched.get('public_answers_used') is False and matched.get('clean_generalization_claimed') is False
            and matched.get('source_identity') == source_identity and matched.get('job_id') == JOB_ID
            and matched.get('arms') == list(ARMS),
            'persisted no-PUBLIC matched report and fixed denominator required')
    if phase_deadlines is not None:
        require(matched.get('screen_deadline_epoch') == phase_deadlines['screen_deadline_epoch']
                and matched.get('evaluation_deadline_epoch') == phase_deadlines['worker_deadline_epoch'],
                'matched report original phase deadlines differ')
    artifacts = matched.get('private_artifacts')
    require(type(artifacts) is dict and {'matched-protocol.json', 'matched-admission.json',
            'matched-source-binding.json'} <= set(artifacts), 'complete private protocol/admission/source artifacts required')
    for name, artifact in artifacts.items():
        require(name != 'matched-report.json', 'report cannot contain a circular self hash')
        _artifact(worker_root, name, artifact)
    for filename, field in (('matched-protocol.json', 'protocol_sha256'), ('matched-admission.json', 'admission_sha256')):
        require(_sha256(matched.get(field))
                and hashlib.sha256(canonical(_json(Path(worker_root) / filename))).hexdigest() == matched[field],
                'matched protocol/admission content SHA differs')
    protocol = _json(Path(worker_root) / 'matched-protocol.json')
    admission = _json(Path(worker_root) / 'matched-admission.json')
    binding = _json(Path(worker_root) / 'matched-source-binding.json')
    require(type(binding) is dict and binding.get('source', {}).get('training_manifest_sha256') == TRAINING_MANIFEST_SHA256
            and all(protocol.get(field) == admission.get(field) == hashlib.sha256(canonical(binding.get(key))).hexdigest()
                    for key, field in (('source', 'source_sha256'), ('split', 'split_sha256'), ('family_lineage', 'family_lineage_sha256'))),
            'matched source/split/family binding differs')
    parent_ids = protocol.get('development_parent_ids')
    require(protocol.get('version') == WORKFLOW and protocol.get('arms') == list(ARMS)
            and protocol.get('admission_sha256') == matched['admission_sha256']
            and protocol.get('views') == 2 and protocol.get('ttt_steps') == 0 and protocol.get('held_demo_index') == 0
            and protocol.get('public_feedback_used') is False
            and type(parent_ids) is list and len(parent_ids) == 16 and len(set(parent_ids)) == 16
            and all(type(parent) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}', parent) for parent in parent_ids)
            and type(protocol.get('training_parent_ids')) is list and len(protocol['training_parent_ids']) == 16
            and set(protocol['training_parent_ids']).isdisjoint(parent_ids), 'fixed no-TTT heldout protocol required')
    exports = matched.get('exports')
    require(type(exports) is dict and not set(exports) - set(ARMS), 'only declared arm exports allowed')
    controls = matched.get('controls')
    preflight_passed = _probability_preflight(matched, protocol, worker_root, artifacts)
    if controls is None:
        partial_preflight = (matched['status'] == 'partial'
            and protocol.get('probability_preflight') == PREFLIGHT
            and (matched.get('probability_preflight') or {}).get('status') == 'deadline')
        require((matched['status'] == 'failed' or partial_preflight) and not matched['complete']
                and all(export.get('status') != 'complete' for export in exports.values()),
                'missing controls cannot provide completed work or exports')
        controls = {'status': 'failed', 'arms': {arm: {'status': 'not_run'} for arm in ARMS}}
    else:
        require(type(controls) is dict and type(controls.get('arms')) is dict
                and set(controls['arms']) == set(ARMS) and 'matched-controls.json' in artifacts,
                'all declared control arm receipts and full capture required')
        full = _json(Path(worker_root) / 'matched-controls.json', limit=MAX_CONTROLS)
        capture = full.get('capture', {})
        require(type(capture.get('groups')) is list and len(capture['groups']) <= 64
                and _sha256(capture.get('seal_sha256'))
                and capture['seal_sha256'] == hashlib.sha256(canonical({k: v for k, v in capture.items() if k != 'seal_sha256'})).hexdigest(),
                'full captured pool seal differs')
        expected = {**full, 'capture': {**{k: v for k, v in capture.items() if k != 'groups'},
                                       'group_count': len(capture['groups'])},
                    'collection': {**full['collection'], 'distinct_mixed_parents': len({g['parent_id'] for g in capture['groups']
                        if g['status'] == 'complete' and g['category'] == 'mixed'})}}
        require(controls == expected, 'compact controls differ from bound full capture')
    for arm, export in exports.items():
        if export.get('status') == 'complete':
            state = _verify_export(worker_root, arm, export, source_identity, result['model_identity'],
                                   protocol.get('probability_policy', LEGACY_POLICY))
            require(controls.get('state_sha256', {}).get(arm) == state
                    and (controls['arms'][arm].get('status') != 'complete'
                         or controls['arms'][arm].get('after_sha256') == state), 'control state differs from exported state')
    evaluated, scores = _evaluation(matched.get('evaluation'), worker_root=worker_root,
        artifacts=artifacts, exports=exports, parent_ids=parent_ids,
        target_digests=protocol.get('development_target_digest'))
    complete = (preflight_passed and controls.get('status') == 'complete' and all(controls['arms'][arm].get('status') == 'complete' for arm in ARMS)
                and set(exports) == set(ARMS) and all(v.get('status') == 'complete' for v in exports.values())
                and evaluated and matched.get('anchor_restored') is True and matched.get('engine_poisoned') is False
                and controls.get('anchor_restored') is True and controls.get('engine_poisoned') is False
                and matched.get('cleanup_errors') == [] and controls.get('cleanup_errors') == []
                and matched.get('returned_after_evaluation_deadline') is False)
    require(matched['complete'] == complete and (matched['status'] == 'complete') == complete
            and result['completed'] == complete, 'worker completion differs from actual controls/evaluation/exports')
    best = max(scores.values()); winners = [arm for arm in ARMS if scores[arm] == best]
    selected = winners[0] if complete and len(winners) == 1 and best > scores['anchor'] else 'anchor'
    require(matched.get('selected_arm') == selected and type(matched.get('candidate_selected')) is bool
            and matched['candidate_selected'] == (selected != 'anchor'),
            'only complete generated-exact strict improvement may select a candidate; ties retain anchor')
    require(matched.get('selection_label') == ('provisional16-parent-mechanism-candidate' if selected != 'anchor' else 'retain-anchor'),
            'selection label differs from verified provisional candidate status')
    return complete


def _normal_closure(row):
    from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
    from .score import closure_structure
    require(row.get('closure_verified') is True, 'unverified worker closure; no later dispatch')
    proof = row.get('closure')
    closure_structure(proof); verify_closed_proof(proof)
    return proof['returncode'] == 0 and proof['worker_returncode'] == 0 and proof['forced'] is False


def run(config):
    require(config.get('workflow') == WORKFLOW, 'explicit matched diagnostic workflow required')
    require(config.get('parameters', {}) == {} and type(config.get('model_roots')) is dict
            and set(config['model_roots']) == {'2b'} and not any(key in config for key in ('checkpoint', 'checkpoints', 'resume')),
            'fixed fresh official2B-only matched recipe required')
    require(_sha256(config.get('source_identity')), 'pinned matched source SHA required')
    phase_plan(config, time.time())
    source, output = Path(config['source_root']), Path(config['output_root'])
    require(not any(p.is_symlink() for p in (output, *output.parents)), 'regular diagnostic output directory required')
    check_dataset_separation(config['input_root'], config['allowed_input_roots'])
    output.mkdir(parents=True, exist_ok=False)
    require(shutil.disk_usage(output).free >= 3 * GIB,
            'matched diagnostic requires3GiB free for four states, staging and private evidence')
    write_new(output / 'isolation.json', {'mechanism': 'dataset-separated-provider-execution',
        'evaluator_dataset_absent': True, 'os_sandbox_claimed': False, 'public_inference_performed': False,
        'public_projection_use': 'training split exclusion only', 'public_answers_used': False})
    env = {**os.environ, **config['runtime_env'], 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    observed = subprocess.run([config['python'], '-B', '-m', 'tools.nvarc_posttrain_20261017.worker', '--topology'],
        cwd=source, env=env, check=True, capture_output=True, text=True, timeout=120)
    topology = _decode(observed.stdout.splitlines()[-1]); _topology(topology)
    write_new(output / 'topology.json', topology)
    plan = phase_plan(config, time.time()); write_new(output / 'phase-plan.json', plan)
    job = {'job_id': JOB_ID, 'variant': '2b', 'arm': 'S', 'mode': 'matched',
        'source_identity': config['source_identity'], 'workload_identity': WORKLOAD,
        'device_identity': topology['device_identity'], 'model_root': config['model_roots']['2b'],
        'seed': 7321, 'adapter_seed': 731, 'cpu_threads': 1, 'parameters': {}, 'allocator_fraction': .8,
        'training_deadline_epoch': plan['screen_deadline_epoch'],
        'original_started_epoch': plan['original_started_epoch'], 'original_deadline_epoch': plan['original_deadline_epoch'],
        **{key: config[key] for key in ('training_root', 'training_manifest_path', 'public_path')}}
    progress('matched_diagnostic_start', variant='2b', requested_parents=16, arms=list(ARMS), views=2,
             deadline_epoch=plan['worker_deadline_epoch'])
    wave = run_wave([job], python=config['python'], source_root=str(source), output_root=str(output / 'matched-2b'),
        deadline_epoch=plan['wave_deadline_epoch'], common_env=env, load_timeout_seconds=LOAD_SECONDS,
        stop_timeout_seconds=STOP_SECONDS, finalization_reserve_seconds=FINALIZATION_SECONDS)
    require(type(wave.get('jobs')) is list and len(wave['jobs']) == 1
            and wave['jobs'][0].get('job_id') == JOB_ID, 'exactly one official2B owned worker required')
    row = wave['jobs'][0]; normal = False
    if row.get('status') not in {'deadline_before_launch', 'ownership_blocked'} or row.get('closure') is not None:
        normal = _normal_closure(row)
    validated = False
    if row.get('result') is not None:
        require(row.get('closure_verified') is True and row.get('closure') is not None,
                'closed worker required before consuming private result')
        worker_root = output / 'matched-2b' / JOB_ID
        require(_json(worker_root / 'result.json') == row['result'], 'persisted worker result differs')
        validated = validate_result(row['result'], worker_root, source_identity=config['source_identity'],
                                    device_identity=topology['device_identity'], phase_deadlines=plan)
    complete = normal and row.get('status') == 'completed' and wave.get('completed') is True and validated
    write_new(output / 'matched-2b-wave.json', wave)
    summary = {'format': 'irisx/nvarc-matched-controller-v1', 'run_id': config['run_id'],
        'source_identity': config['source_identity'], 'workflow': WORKFLOW, 'workload_identity': WORKLOAD,
        'completed': complete, 'requested_models': ['2b'], 'requested_parents_per_arm': 16,
        'arms': list(ARMS), 'matched_views': 2, 'workers': wave['jobs'], 'phase_plan': plan,
        'public_inference_performed': False, 'public_scoring_performed': False, 'public_score': None,
        'official_score': None, 'clean_generalization_claimed': False, 'architecture_expansion_tested': False,
        'automatic_following_run': False, 'training_or_ensemble_selected_for_public': False}
    write_new(output / 'run-summary.json', summary)
    progress('matched_diagnostic_closed', completed=complete, wall_seconds=wave.get('wall_seconds'))
    return summary


def _inventory(output):
    files, total = {}, 0
    require(not any(p.is_symlink() for p in (output, *output.parents)), 'diagnostic output symlink forbidden')
    if not output.exists():
        return files
    require(output.is_dir(), 'diagnostic output directory required')
    for path in sorted(output.rglob('*')):
        require(not path.is_symlink(), 'diagnostic output symlink forbidden')
        if path.is_dir():
            continue
        path = _regular(path); size = path.stat().st_size; total += size
        require(total <= MAX_TOTAL and len(files) < MAX_FILES, 'bounded complete diagnostic evidence required')
        files[path.relative_to(output).as_posix()] = {'bytes': size, 'sha256': sha(path)}
    return files


def close_diagnostic(config, control, proof):
    """Bind ALL private files after fresh owner closure; never PUBLIC sealing."""
    from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
    from .score import closure_structure
    closure_structure(proof); verify_closed_proof(proof)
    control, output = Path(control), Path(config['output_root'])
    require(not control.absolute().is_relative_to(output.absolute()), 'control must be outside bound diagnostic files')
    require(_json(control / 'owner-closure.json') == proof, 'persisted owner closure differs')
    files = _inventory(output)
    summary = _json(output / 'run-summary.json') if 'run-summary.json' in files else None
    complete = False
    if summary is not None:
        require(type(summary) is dict and summary.get('format') == 'irisx/nvarc-matched-controller-v1'
                and summary.get('source_identity') == config['source_identity']
                and summary.get('run_id') == config['run_id'] and summary.get('workflow') == WORKFLOW
                and summary.get('workload_identity') == WORKLOAD and summary.get('requested_models') == ['2b']
                and summary.get('requested_parents_per_arm') == 16 and summary.get('arms') == list(ARMS)
                and summary.get('matched_views') == 2 and type(summary.get('completed')) is bool
                and summary.get('public_inference_performed') is False
                and summary.get('public_scoring_performed') is False and summary.get('public_score') is None
                and summary.get('official_score') is None and summary.get('clean_generalization_claimed') is False
                and summary.get('architecture_expansion_tested') is False
                and summary.get('automatic_following_run') is False
                and summary.get('training_or_ensemble_selected_for_public') is False,
                'closed matched summary identity or requested workload differs')
        plan = _json(output / 'phase-plan.json')
        require(summary.get('phase_plan') == plan
                and plan.get('original_started_epoch') == config['started_epoch']
                and plan.get('original_deadline_epoch') == config['deadline_epoch']
                and _finite(config['started_epoch']) and _finite(config['deadline_epoch'])
                and config['deadline_epoch'] == config['started_epoch'] + 43200
                and plan.get('wave_deadline_epoch') == config['deadline_epoch'] - OUTER_CLOSURE_SECONDS
                and plan.get('worker_deadline_epoch') == plan['wave_deadline_epoch'] - STOP_SECONDS - FINALIZATION_SECONDS
                and plan.get('evaluation_deadline_epoch') == plan['worker_deadline_epoch']
                and _finite(plan.get('screen_deadline_epoch'))
                and config['started_epoch'] < plan['screen_deadline_epoch'] <= plan['worker_deadline_epoch'] - EVALUATION_RESERVE_SECONDS,
                'closed original-session phase plan differs')
        wave = _json(output / 'matched-2b-wave.json')
        require(summary.get('workers') == wave.get('jobs') and len(wave['jobs']) == 1
                and wave['jobs'][0].get('job_id') == JOB_ID, 'closed summary worker inventory differs')
        row = wave['jobs'][0]
        normal = _normal_closure(row) if row.get('closure') is not None else False
        validated = False
        if row.get('result') is not None:
            require(row.get('closure_verified') is True and row.get('closure') is not None,
                    'closed worker required for diagnostic result')
            worker_root = output / 'matched-2b' / JOB_ID
            require(_json(worker_root / 'result.json') == row['result'], 'closed worker result differs')
            topology = _json(output / 'topology.json'); _topology(topology)
            validated = validate_result(row['result'], worker_root, source_identity=config['source_identity'],
                                        device_identity=topology['device_identity'], phase_deadlines=plan)
        eligible = normal and validated and row.get('status') == 'completed' and wave.get('completed') is True
        require(summary['completed'] == eligible, 'summary completion differs from validated closed worker')
        complete = eligible and proof['worker_returncode'] == 0 and proof['returncode'] == 0 and not proof['forced']
        require(_inventory(output) == files, 'private evidence changed during closure verification')
    finalized = time.time()
    within_session = (_finite(config.get('started_epoch')) and _finite(config.get('deadline_epoch'))
        and config['deadline_epoch'] == config['started_epoch'] + 43200
        and config['started_epoch'] <= finalized < config['deadline_epoch'])
    complete = complete and within_session
    terminal = {'format': 'irisx/nvarc-closed-matched-v1', 'run_id': config['run_id'],
        'finalization_epoch': finalized, 'finalization_within_original_session': within_session,
        'status': 'CLOSED_DIAGNOSTIC', 'completed': complete, 'source_manifest_sha256': config['source_identity'],
        'workflow': WORKFLOW, 'files': files, 'closure_sha256': sha(control / 'owner-closure.json'),
        'generation_may_resume': False, 'public_score': None, 'official_score': None,
        'public_inference_performed': False, 'public_scoring_performed': False,
        'provider_terminal_verified': False, 'clean_generalization_claimed': False,
        'new_model_or_ensemble_selected_for_public': False}
    write_new(control / 'terminal.json', terminal)
    # Correct a tiny final-write overrun without discarding the actual worker
    # evidence or pretending the original session clock can be reset.
    after_write = time.time()
    if within_session and after_write >= config['deadline_epoch']:
        terminal.update(completed=False, finalization_epoch=after_write,
                        finalization_within_original_session=False, late_during_terminal_persistence=True)
        raw = canonical(terminal) + b'\n'
        staged = control / 'terminal.json.tmp'
        with staged.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        staged.replace(control / 'terminal.json')
    return terminal
