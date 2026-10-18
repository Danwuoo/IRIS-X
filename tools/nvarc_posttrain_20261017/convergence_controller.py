"""Owned official-2B convergence screen and independently verified private closure.

This CPU consumer never loads a model, imports torch, performs PUBLIC inference,
opens evaluator answers or selects a PUBLIC ensemble. A successful callable is
not evidence: complete source-bound artifacts and fresh owned-tree closure are
required. Tiny-fixture contracts exist only in the private artifact validator;
production dispatch/closure always fix the official baseline contract.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import time

from src.irisx.arc_nvarc_data import known_variant_group
from tools.arc2_goal_sprint_20261017.data import (
    canonical, digest, inference_views, transform, valid_grid, view_inputs,
)
from tools.arc2_goal_sprint_20261017.launch import (
    TRAINING_MANIFEST_SHA256, check_dataset_separation, require, sha, write_new,
)
from . import matched_controller as shared
from .codec import encode_example, parse_completion
from .concurrency import run_wave
from .controller import model_bound, progress
from .precision_contract import (FP32_HEAD_POLICY, FP32_BACKBONE_POLICY, stable_probe_admission,
    output_head_contract, full_precision_execution_contract)
from .probability_trace import validate_rows, validate_trace

WORKFLOW = WORKLOAD = 'compact-convergence-screen-v1'
JOB_ID = '2b-S'
ARMS = (*shared.ARMS, 'finite_hybrid')
TREATMENTS = ('no_ttt', 'ttt')
SCHEDULES = {'anchor': [], 'known_target_ce': ['known_target_ce'] * 4,
    'exact_positive_ce': ['exact_positive_ce'] * 4,
    'exact_centered_ddis': ['exact_centered_ddis'] * 4,
    'finite_hybrid': ['known_target_ce', 'exact_positive_ce', 'exact_centered_ddis', 'known_target_ce']}
DEFAULT_CONFIG = {'collection': {'seed': 0, 'max_groups': 8, 'target_mixed_groups': 2,
    'microbatch': 2, 'context_tokens': 8192, 'generation_tokens': 931, 'learning_rate': 2e-5},
    'training_seconds': 2400, 'window_seconds': 180, 'max_model_forward_attempts': 65536}
DEFAULT_EVALUATION = {'views': 2, 'ttt_steps': 32, 'ttt_lr': 5e-5, 'evaluation_seed': 20261018}
LOSS_CONTRACT = {
    'known_target_ce': 'mean complete-group mean target-token NLL; every complete prompt weight1/G',
    'exact_positive_ce': 'mean positive-trajectory mean completion-token NLL; unique-target compression weight positive_count/total_positives',
    'exact_centered_ddis': 'actual AF3/DDIS; advantage exact_reward-group_mean; divisor mixed_groups*8*completion_length; clip .2/.2; no std, referenceKL, entropy mask, OPSM or DAPO token-mean',
    'finite_hybrid': 'predeclared targetCE,positiveCE,DDIS,targetCE; one persistent fresh optimizer within arm',
}
COUNTERS = ('forward_calls', 'sampled_tokens', 'optimizer_steps', 'optimizer_attempts',
    'generation_forward_attempts', 'generation_input_tokens', 'generation_row_token_slots',
    'generation_finished_row_token_slots', 'generation_padding_tokens', 'model_forward_attempts', 'model_input_tokens')
PROJECTION_COUNTERS = ('diagnostic_head_projection_attempts', 'diagnostic_head_projection_successes')
MAX_ACTIVE_SECONDS = 7200
OUTER_CLOSURE_SECONDS, STOP_SECONDS, FINALIZATION_SECONDS = 180, 15, 30
LOAD_SECONDS, EVALUATION_RESERVE_SECONDS = 600, 3600
GIB = 1024 ** 3
# A conservative unmeasured envelope for FP32 math attention, not a quota gate.
# A full 8192-token 2-row/16-head FP32 attention matrix alone is8GiB.
MIN_FP32_FREE_BYTES = 40 * GIB
_json, _artifact, _regular = shared._json, shared._artifact, shared._regular
_sha256, _finite = shared._sha256, shared._finite


def _h(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _bounds(cfg):
    collection = cfg['collection']
    return {'collection_windows': 13, 'group_attempts': 13 * collection['max_groups'],
        'training_trajectory_slots': 13 * collection['max_groups'] * 8,
        'preflight_trajectory_slots': 13 * collection['microbatch'],
        'maximum_extra_diagnostic_head_projections': 13 * (4 * collection['generation_tokens'] + 6 * collection['microbatch']),
        'training_optimizer_attempts': 16, 'model_forward_attempts': cfg['max_model_forward_attempts'],
        'completion_tokens_per_trajectory': collection['generation_tokens'], 'context_tokens': collection['context_tokens'],
        'training_wall_seconds': cfg['training_seconds'], 'window_wall_seconds': cfg['window_seconds'],
        'count_includes_failed_and_no_signal': True, 'model_forwards_are_not_FLOPs': True}


@dataclass(frozen=True)
class _Contracts:
    """Explicit internal fixture seam; never accepted by production entrypoints."""
    training_manifest_sha256: str
    model: dict
    trainables: dict
    tokenizer: dict
    config: dict
    evaluation: dict
    probability_tolerance: float


def _official_contracts():
    return _Contracts(TRAINING_MANIFEST_SHA256, shared._official_model_contract(),
        {**shared._official_trainable_contract(), 'frozen_dtype': 'torch.float32',
         'probability_policy': FP32_BACKBONE_POLICY},
        shared._official_tokenizer_admission(), DEFAULT_CONFIG, DEFAULT_EVALUATION, .05)



def _topology(topology):
    shared._topology(topology)
    require(topology['free_bytes'] >= MIN_FP32_FREE_BYTES
        and topology['total_bytes'] * 4 // 5 >= MIN_FP32_FREE_BYTES,
        'unmeasured FP32/math recipe requires40GiB free within the80percent allocator envelope')


def phase_plan(config, now):
    """Finite 7200-second screen within the unchanged 43200-second session."""
    start, end = config.get('started_epoch'), config.get('deadline_epoch')
    require(_finite(start) and _finite(end) and _finite(now) and 0 < start <= now < end
        and end == start + 43200, 'finite original 43200-second session required')
    active_end = min(end, now + MAX_ACTIVE_SECONDS)
    wave_end = active_end - OUTER_CLOSURE_SECONDS
    worker_end = wave_end - STOP_SECONDS - FINALIZATION_SECONDS
    training_end = min(now + LOAD_SECONDS + 2400, worker_end - EVALUATION_RESERVE_SECONDS)
    require(training_end - now > LOAD_SECONDS + 600,
        'insufficient original-session time for finite training, paired evaluation and closure')
    return {'original_started_epoch': start, 'original_deadline_epoch': end, 'admitted_epoch': now,
        'active_deadline_epoch': active_end, 'maximum_active_seconds': MAX_ACTIVE_SECONDS,
        'wave_deadline_epoch': wave_end, 'worker_deadline_epoch': worker_end,
        'screen_deadline_epoch': training_end, 'evaluation_deadline_epoch': worker_end,
        'heldout_reserve_seconds': EVALUATION_RESERVE_SECONDS, 'load_timeout_seconds': LOAD_SECONDS,
        'outer_closure_reserve_seconds': OUTER_CLOSURE_SECONDS,
        'worker_finalization_reserve_seconds': FINALIZATION_SECONDS, 'owned_stop_reserve_seconds': STOP_SECONDS,
        'quota_hours_queried': False, 'measured_full_workload_feasibility_claimed': False}


def _counters(row):
    require(type(row) is dict and set(COUNTERS) <= set(row) <= set(COUNTERS) | set(PROJECTION_COUNTERS)
        and all(type(v) is int and v >= 0 for v in row.values()), 'complete nonnegative physical counters required')
    require(row['optimizer_steps'] <= row['optimizer_attempts'], 'accepted updates exceed attempts')
    return row


def _task(task):
    require(type(task) is dict and set(task) == {'train'} and type(task['train']) is list
        and 2 <= len(task['train']) <= 32, 'bounded train-only demonstration task required')
    for pair in task['train']:
        require(type(pair) is dict and set(pair) == {'input', 'output'}
            and all(valid_grid(v) for v in pair.values()), 'complete demonstration grids required')


def _panels(root, artifacts, protocol, contracts, training_root, training_manifest_path):
    names = ('source-binding.json', 'panel-admission.json', 'training-panel.json',
             'development-panel.json', 'source-panel-protocol.json')
    require(set(names) <= set(artifacts), 'retained source and train-only panels required')
    binding, admission, training, development, source_protocol = [_json(root / name) for name in names]
    require(_h(binding) == protocol.get('source_binding_sha256')
        and _h(admission) == protocol.get('training_admission_sha256')
        and _h(source_protocol) == protocol.get('source_panel_protocol_sha256'), 'source/panel content pin differs')
    require(binding['source'].get('training_manifest_sha256') == contracts.training_manifest_sha256,
            'independent immutable training-manifest pin differs')
    for key, field in (('source', 'source_sha256'), ('split', 'split_sha256'), ('family_lineage', 'family_lineage_sha256')):
        require(admission.get(field) == source_protocol.get(field) == _h(binding[key]), 'source/split/family SHA differs')
    split, family = binding['split'], binding['family_lineage']
    if training_manifest_path is not None:
        manifest_path = _regular(training_manifest_path, limit=shared.MAX_METADATA)
        require(sha(manifest_path) == contracts.training_manifest_sha256, 'original immutable training manifest bytes differ')
        manifest = _json(manifest_path)
        require(manifest['upstream']['fixed_splits'] == split['fixed_splits']
            and all(manifest['files'].get(name) == row for name, row in binding['source']['files'].items()),
            'source-binding differs from independent immutable manifest inventory')
    partitions = split['partition_ids']; groups = family['groups']
    require(set(binding['source']['files']) == {'data/training/'+p+'.json' for p in partitions['train']+partitions['dev']},
            'complete original training source inventory required')
    require(set(partitions) == set(groups) == {'train', 'dev', 'public'}
        and all(type(partitions[k]) is list and len(partitions[k]) == n and len(set(partitions[k])) == n
            and set(groups[k]) == set(partitions[k]) for k, n in (('train', 800), ('dev', 200), ('public', 120))),
        'original 800/200/120 source partitions required')
    require(set(partitions['train']).isdisjoint(partitions['dev'])
        and set(partitions['train'] + partitions['dev']).isdisjoint(partitions['public'])
        and all(set(groups[a].values()).isdisjoint(groups[b].values())
            for a, b in (('train', 'dev'), ('train', 'public'), ('dev', 'public')))
        and set(split['fixed_splits']) == {'train', 'dev'}
        and all(sorted(split['fixed_splits'][k]) == partitions[k] for k in ('train', 'dev'))
        and split.get('known_variant_partition_sha256') == _h(groups)
        and split.get('public_use') == 'input/demonstration exclusion only', 'split/known-variant isolation differs')
    receipt = split['receipt']
    require(receipt.get('training_test_fields_used') is False
        and receipt.get('training_manifest_sha256') == contracts.training_manifest_sha256
        and receipt.get('train_ids_digest') == digest(partitions['train'])
        and receipt.get('dev_ids_digest') == digest(partitions['dev']), 'original train-only split receipt differs')
    ids = protocol.get('development_parent_ids')
    require(type(ids) is list and len(ids) == len(set(ids)) == 16
        and all(type(p) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}', p) for p in ids)
        and type(training) is dict and len(training) == 16
        and all(type(p) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}', p) for p in training)
        and type(development) is dict
        and set(development) == set(ids) and set(training).isdisjoint(ids)
        and set(training) <= set(partitions['train']) and set(ids) <= set(partitions['dev']),
        'fixed disjoint sixteen-parent train/dev panels required')
    require(set(protocol.get('development_task_sha256', {})) == set(protocol.get('development_target_digests', {})) == set(ids)
        and len({groups['train'][p] for p in training}) == len({groups['dev'][p] for p in ids}) == 16,
        'exact heldout digest keys and distinct selected families required')
    parents = admission['parents']; entries = {r['parent_id']: r for r in parents}
    require(len(entries) == len(parents) == 16 and set(entries) == set(training)
        and source_protocol.get('training_parent_ids') == [r['parent_id'] for r in parents]
        and source_protocol.get('development_parent_ids') == ids
        and source_protocol.get('admission_sha256') == _h(admission)
        and source_protocol.get('held_demo_index') == 0 and source_protocol.get('views') == 2
        and source_protocol.get('probability_policy') == contracts.trainables['probability_policy'],
        'bound source-panel protocol differs')
    excluded = admission['excluded']
    require(set(excluded['parent_ids']) == set(partitions['dev'] + partitions['public'])
        and set(excluded['variant_groups']) == set(groups['dev'].values()) | set(groups['public'].values())
        and set(excluded['family_ids']) == {'known-variant:' + v for v in excluded['variant_groups']},
        'complete training exclusion denominators required')
    require(set(ids).isdisjoint(source_protocol['excluded_previous_panel'] + source_protocol['excluded_stability_panel'])
        and len(source_protocol['excluded_previous_panel']) == 24 and len(source_protocol['excluded_stability_panel']) == 32,
        'earlier selection/stability parent overlap forbidden')
    for kind, panel in (('train', training), ('dev', development)):
        for parent, task in panel.items():
            _task(task)
            group = known_variant_group({'train': task['train'], 'test': []})
            require(groups[kind][parent] == group, 'recomputed source family differs')
            if kind == 'train':
                require(entries[parent] == {'parent_id': parent, 'task_sha256': _h(task), 'variant_group': group,
                    'family_id': 'known-variant:' + group, 'held_index': 0}, 'training admission task differs')
            else:
                require(protocol['development_task_sha256'][parent] == source_protocol['development_task_sha256'][parent] == _h(task)
                    and protocol['development_target_digests'][parent] == source_protocol['development_target_digest'][parent]
                        == digest(task['train'][0]['output'])
                    and group == source_protocol['development_variant_groups'][parent]
                    and group not in source_protocol['excluded_development_variant_groups']
                    and all(pair['input'] != task['train'][0]['input'] for pair in task['train'][1:]),
                    'held-demo target/prompt or excluded family differs')
            if training_root is not None:
                path = _regular(Path(training_root) / (parent + '.json'), limit=shared.MAX_METADATA)
                expected = binding['source']['files']['data/training/' + parent + '.json']
                require(path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256']
                    and _json(path)['train'] == task['train'], 'retained panel differs from pinned original training bytes')
    return training, development, admission


def _prediction(raw, task, parent, cfg):
    """Rebuild prompt, EOS parsing, inverse transforms, votes and NLL ranking."""
    require(type(raw) is dict and raw.get('ranking') == 'votes-descending-mean-own-view-nll-tie-v1'
        and type(raw.get('views')) is list and len(raw['views']) <= 2 and type(raw.get('complete')) is bool,
        'bounded fixed raw prediction required')
    demos, query = {'train': task['train'][1:]}, task['train'][0]['input']
    specs = inference_views(2, seed=cfg['evaluation_seed'], task_id=parent, demo_count=len(demos['train']))
    candidates = []
    for index, row in enumerate(raw['views']):
        require(type(row.get('view')) is int and row['view'] == index, 'ordered unique prediction views required')
        evidence = row['token_evidence']; pairs, transformed = view_inputs(demos, query, specs[index])
        encoded = encode_example(pairs, transformed, context=cfg['context_tokens'], generation=cfg['generation_tokens'])
        ids, logps = evidence.get('completion_ids'), evidence.get('completion_log_probs')
        require(evidence.get('view_spec') == specs[index] and evidence.get('prompt_ids') == encoded['prompt_ids']
            and row.get('demos_dropped') == encoded['demos_dropped'] and type(ids) is list
            and 1 <= len(ids) <= cfg['generation_tokens'] and all(type(t) is int and 0 <= t < 16 for t in ids)
            and row.get('tokens') == len(ids) and type(logps) is list and len(logps) == len(ids)
            and all(_finite(v) and v <= 1e-6 for v in logps) and 15 not in ids[:-1]
            and row.get('stop') in {'completed', 'length'} and (row['stop'] == 'completed') == (ids[-1] == 15)
            and (row['stop'] != 'length' or len(ids) == cfg['generation_tokens']),
            'original fixed prompt/completion probabilities differ')
        grid = parse_completion(ids)
        require(type(row.get('valid')) is bool and row['valid'] == (grid is not None), 'raw completion parser differs')
        if grid is None:
            continue
        original = transform(grid, **specs[index]['transform'], inverse=True)
        found = next((i for i, candidate in enumerate(candidates) if candidate['grid'] == original), None)
        if found is None:
            found = len(candidates); candidates.append({'grid': original, 'votes': 0, 'nll_sum': 0., 'views': []})
        candidate = candidates[found]
        candidate['votes'] += 1; candidate['nll_sum'] += -sum(logps) / len(ids); candidate['views'].append(index)
        require(row.get('candidate') == found, 'inverse-view candidate identity differs')
    order = sorted(range(len(candidates)), key=lambda i: (-candidates[i]['votes'], candidates[i]['nll_sum'] / candidates[i]['votes'], i))
    require(raw.get('candidates') == candidates and raw.get('ranked_candidate_indices') == order
        and raw.get('ranked_grids') == [candidates[i]['grid'] for i in order[:2]]
        and raw['complete'] == (len(raw['views']) == 2), 'independently reconstructed prediction ranking differs')
    return {'verified': True, 'completed_views': len(raw['views']), 'candidate_count': len(candidates), 'result_sha256': _h(raw)}


def _probe(gate, lineage, cfg, tolerance, *, prompt, deadline, contracts, model_identity):
    require(type(gate) is dict and type(gate.get('passed')) is bool
        and gate.get('tolerance') == tolerance and gate.get('used_for_loss') is False
        and gate.get('full_pool_gate_still_required') is True and gate.get('gpu_backward_validated') is False
        and gate.get('policy_before_sha256') == lineage['policy_sha256']
        and _sha256(gate.get('policy_after_sha256')), 'unchanged full-policy numerical gate required')
    raw = gate['probe']; rows = raw.get('rows', []); trace = raw.get('trace', {})
    require(raw.get('training_authorized') is False, 'diagnostic samples never authorize loss')
    require(raw.get('seed') == cfg['seed'] and raw.get('requested_count') == cfg['microbatch']
        and raw.get('max_new_tokens') == cfg['generation_tokens'] and raw.get('deadline') == deadline,
        'probe seed/count/generation/original deadline differs')
    context = raw.get('context')
    if context is not None:
        require(context.get('probability_policy') == contracts.trainables['probability_policy'] and context.get('base_identity') == model_identity
            and context.get('model_contract') == contracts.model
            and context.get('base_dtype') == contracts.trainables['frozen_dtype']
            and context.get('output_head_contract') == output_head_contract(contracts.trainables['probability_policy']),
            'probe original model/precision policy context differs')
        if contracts.trainables['probability_policy'] == FP32_BACKBONE_POLICY:
            expected = full_precision_execution_contract()
            require(context.get('execution_policy') == expected, 'active FP32/math context differs')
            require(all(item.get('execution_policy') == expected for item in raw.get('logit_evidence', [])),
                    'actual forward computation escaped FP32/math policy')
    else:
        require(raw.get('status') != 'completed', 'completed probe lacks original model context')
    if trace.get('status') == 'completed':
        require(trace.get('prompts') == [prompt]*cfg['microbatch'], 'probe prompt differs from seeded first admitted training parent')
        validate_trace(trace, expected_trace_sha256=trace.get('sha256')); validate_rows(rows, trace)
        require(trace['sample'] is True and trace['batch_size'] == cfg['microbatch']
            and trace['max_new_tokens'] == cfg['generation_tokens'], 'fixed seeded probe trajectory denominator differs')
    else:
        require(raw.get('status') != 'completed' and not rows, 'partial probe cannot claim completed trajectories')
    cached = raw.get('cached_replay') or {}; cached_steps = cached.get('steps', [])
    require(type(cached_steps) is list and len(cached_steps) <= len(trace.get('steps', [])), 'bounded cached probe required')
    cached_gaps, full_gaps = [], []
    for index, row in enumerate(cached_steps):
        original = trace['steps'][index]
        require(all(row.get(k) == original.get(k) for k in ('step', 'selected_ids', 'retained'))
            and row.get('behavior_log_probs') == original.get('selected_log_probs'), 'cached original sampled denominator differs')
        a, b = row['behavior_log_probs'], row.get('cached_log_probs')
        require(type(b) is list and len(b) == cfg['microbatch'] and all(_finite(v) for v in a + b), 'finite cached vectors required')
        cached_gaps.extend(abs(x-y) for x, y in zip(a, b))
    full = raw.get('full_replay', [])
    require(type(full) is list and len(full) <= len(rows) <= cfg['microbatch'], 'bounded full probe required')
    for index, row in enumerate(full):
        original = rows[index]; a = original['behavior_log_probs'][original['prompt_length']:]; b = row.get('full_log_probs')
        require(row.get('row_index') == index and row.get('completion_ids') == original['completion_ids']
            and row.get('behavior_log_probs') == a and type(b) is list and len(b) == len(a)
            and all(_finite(v) for v in a + b), 'full probe original denominator differs')
        full_gaps.extend(abs(x-y) for x, y in zip(a, b))
    gaps = [max(cached_gaps) if cached_gaps else None, max(full_gaps) if full_gaps else None]
    require(raw.get('cached_max_abs_logp_gap') == gaps[0] and raw.get('full_max_abs_logp_gap') == gaps[1],
            'probe summary differs from original probability vectors')
    extra, extra_passed, admission_error = None, False, None
    try:
        extra, extra_passed = stable_probe_admission(raw, tolerance=tolerance, count=cfg['microbatch'])
    except (ValueError, TypeError, KeyError) as error:
        admission_error = {'type': type(error).__name__, 'message': str(error)[:1024]}
    require(gate.get('additional_stable_admission') == extra and gate.get('additional_admission_error') == admission_error,
            'stable probe admission differs from full16 raw evidence')
    passed = (raw.get('status') == 'completed' and gate['policy_after_sha256'] == lineage['policy_sha256']
        and len(rows) == len(full) == cfg['microbatch'] and cached.get('status') == 'completed'
        and 0 < len(cached_steps) == len(trace.get('steps', []))
        and raw.get('full_metrics', {}).get('tokens') == sum(len(r['completion_ids']) for r in rows)
        and all(_finite(g) and 0 <= g <= tolerance for g in gaps) and extra_passed)
    require(gate['passed'] == passed, 'numerical admission claim differs')
    return passed


def _window(window, training, admission, cfg, contracts, model_identity):
    capture = window['capture']; lineage = capture['lineage']; cc = capture['config']
    require(set(lineage) == {'policy_sha256', 'anchor_sha256', 'model_identity_sha256', 'admission_sha256'}
        and all(_sha256(v) for v in lineage.values()) and lineage['admission_sha256'] == _h(admission)
        and capture.get('seal_sha256') == _h({k: v for k, v in capture.items() if k != 'seal_sha256'})
        and all(cc.get(k) == v for k, v in cfg.items() if k != 'seed'), 'sealed exact current-policy capture required')
    require(window.get('behavior_probabilities_replaced') is False and window.get('partial_groups_used_for_loss') is False,
            'original sampled denominator and complete-group-only loss required')
    groups = capture['groups']; require(type(groups) is list and len(groups) <= cfg['max_groups'], 'bounded collection groups required')
    first = random.Random(cc['seed']).choice(sorted(training)); task = training[first]
    prompt = encode_example(task['train'][1:], task['train'][0]['input'], context=cc['context_tokens'], generation=cc['generation_tokens'])['prompt_ids']
    gate = window.get('preflight')
    passed = (_probe(gate, lineage, cc, contracts.probability_tolerance, prompt=prompt, deadline=window['deadline_epoch'],
        contracts=contracts, model_identity=model_identity) if gate is not None else False)
    require(passed or not groups, 'failed numerical preflight cannot admit collection')
    entries = {r['parent_id']: r for r in admission['parents']}
    rng = random.Random(cc['seed']); ids = sorted(entries)
    empty = dict(complete=0, trajectories=0, positive=0, all_wrong=0, all_correct=0, mixed=0)
    parents = {p: Counter(empty) for p in ids}; families = {r['family_id']: Counter(empty) for r in entries.values()}
    def weight(stats):
        p = (stats['positive'] + 1) / (stats['trajectories'] + 2)
        return .05 + 4 * p * (1-p) + 1 / math.sqrt(stats['complete'] + 1)
    all_rows, requested, mixed = [], 0, 0
    for index, group in enumerate(groups):
        expected = rng.choice(ids) if index % 2 == 0 else rng.choices(ids, weights=[weight(parents[p]) * weight(families[entries[p]['family_id']]) for p in ids], k=1)[0]
        require(group.get('group_id') == f'g{index}' and group.get('parent_id') == expected
            and group.get('allocation') == ('uniform-parent' if index % 2 == 0 else 'smoothed-family-parent-mixed')
            and mixed < cfg['target_mixed_groups'], 'seeded curriculum or stop point differs')
        task, entry = training[expected], entries[expected]; target = task['train'][0]['output']
        example = encode_example(task['train'][1:], task['train'][0]['input'], context=cc['context_tokens'], generation=cc['generation_tokens'])
        require(group.get('prompt_ids') == example['prompt_ids'] and group.get('training_target') == target
            and group.get('demos_dropped') == example['demos_dropped'], 'captured original training prompt/target differs')
        rows, batches = group['rows'], group['batches']; asked = returned = accepted = 0
        require(type(rows) is list and len(rows) <= 8 and type(batches) is list and len(batches) <= 8, 'bounded raw group required')
        for position, batch in enumerate(batches):
            require(all(type(batch.get(k)) is int for k in ('requested', 'returned', 'accepted'))
                and batch['requested'] == min(cc['microbatch'], 8-asked)
                and 0 <= batch['accepted'] <= batch['returned'] <= batch['requested']
                and batch['status'] in {'complete', 'deadline', 'failed'}
                and (batch['status'] != 'complete' or batch['requested'] == batch['returned'] == batch['accepted'])
                and (batch['status'] == 'complete' or position == len(batches)-1), 'original physical batch accounting differs')
            asked += batch['requested']; returned += batch['returned']; accepted += batch['accepted']
        require(asked <= 8 and accepted == len(rows), 'group retained/requested denominator differs')
        requested += asked
        for position, row in enumerate(rows):
            tokens, n, completion, logps = row['input_ids'], row['prompt_length'], row['completion_ids'], row['behavior_log_probs']
            require(type(n) is int and n == len(example['prompt_ids']) and type(completion) is list
                and 1 <= len(completion) <= cc['generation_tokens'] and len(tokens) <= cc['context_tokens']
                and tokens == example['prompt_ids'] + completion and all(type(v) is int and 0 <= v < 16 for v in tokens)
                and row['completion_tokens'] == len(completion) and 15 not in completion[:-1]
                and row['stop'] in {'length', 'completed'} and (row['stop'] == 'completed') == (completion[-1] == 15)
                and (row['stop'] != 'length' or len(completion) == cc['generation_tokens'])
                and type(logps) is list and len(logps) == len(tokens) and all(_finite(v) and v <= 1e-6 for v in logps)
                and logps[:n] == [0.] * n and all(row.get(k) == v for k, v in lineage.items())
                and all(row.get(k) == entry[k] for k in ('parent_id', 'task_sha256', 'variant_group', 'family_id'))
                and row.get('group_id') == group['group_id'] and row.get('sample_id') == f'g{index}:s{position}'
                and row.get('training_target') == target and row.get('reward') == float(parse_completion(completion) == target),
                'original sampled trajectory, exact reward or policy lineage differs')
            all_rows.append(row)
        if group['status'] == 'complete':
            require(len(rows) == asked == returned == 8 and all(b['status'] == 'complete' for b in batches), 'complete eight-row group required')
            positives = sum(r['reward'] for r in rows)
            category = 'all_wrong' if positives == 0 else 'all_correct' if positives == 8 else 'mixed'
            require(group['category'] == category, 'original exact category differs')
            for stats in (parents[expected], families[entry['family_id']]):
                stats.update(complete=1, trajectories=8, positive=positives, **{category: 1})
            mixed += category == 'mixed'
        else:
            require(group['status'] in {'deadline', 'failed'} and group['category'] is None
                and index == len(groups)-1, 'only terminal partial group allowed')
    collection = window['collection']
    expected = {'groups_attempted': len(groups), 'categories': dict(Counter(g['category'] or 'partial' for g in groups)),
        'trajectories_requested': requested, 'trajectories_retained': len(all_rows),
        'distinct_mixed_parents': len({g['parent_id'] for g in groups if g['category'] == 'mixed'}),
        'parent_stats': {p: {**dict(s), 'empirical_exact': s['positive']/s['trajectories'] if s['trajectories'] else None,
            'smoothed_exact': (s['positive']+1)/(s['trajectories']+2)} for p, s in parents.items()},
        'family_stats': {p: dict(s) for p, s in families.items()},
        'uniform_only_control_run': False, 'adaptive_efficiency_established': False}
    require(collection == expected, 'retained full-pool physical/statistical aggregate differs')
    verification = window['verification']; replay = verification.get('rows', [])
    require(type(replay) is list and len(replay) <= len(all_rows), 'full-pool raw replay vectors required')
    gaps, verified = [], 0
    for index, row in enumerate(replay):
        original = all_rows[index]; values = row.get('replay_log_probs')
        require(row.get('sample_id') == original['sample_id'] and row.get('group_id') == original['group_id']
            and row.get('input_ids_sha256') == _h(original['input_ids']) and row.get('prompt_length') == original['prompt_length']
            and type(values) is list and len(values) == len(original['behavior_log_probs'])
            and all(_finite(v) for v in values), 'full-pool replay must bind original sampled trajectory')
        gap = max(abs(a-b) for a, b in zip(values, original['behavior_log_probs'])); gaps.append(gap)
        if gap <= contracts.probability_tolerance:
            verified += 1
        else:
            require(index == len(replay)-1, 'replay continued after failed original-denominator gate')
    require(verification.get('observed_rows') == len(replay) and verification.get('verified_rows') == verified
        and verification.get('max_logp_gap') == (max(gaps) if gaps else None), 'full-pool raw probability gap summary differs')
    physical = _counters(window['physical'])
    require(physical['optimizer_attempts'] == physical['optimizer_steps'] == 0, 'frozen collection attempted an update')
    raw_probe = (gate or {}).get('probe', {})
    require(all(physical.get(key) == raw_probe.get(field, 0) for key, field in zip(PROJECTION_COUNTERS,
        ('extra_projection_attempts', 'extra_projection_successes'))), 'raw diagnostic projection charges differ')
    complete = window['status'] == 'complete'
    if complete:
        require(passed and bool(groups) and all(g['status'] == 'complete' for g in groups)
            and len(replay) == verified == len(all_rows) and verification.get('failed_row') is None
            and ((capture['status'] == 'target_reached' and mixed == cfg['target_mixed_groups'])
              or (capture['status'] == 'budget_exhausted' and len(groups) == cfg['max_groups'] and mixed < cfg['target_mixed_groups'])),
            'complete window requires actual full original pool admission')
    return complete


def _training(report, root, artifacts, training, admission, contracts, model_identity):
    result = report.get('training')
    if result is None:
        require(not report['complete'], 'missing training cannot complete screen')
        return False, {}
    cfg = contracts.config
    require(result.get('format') == 'irisx/compact-convergence-training-v1' and result.get('config') == cfg
        and result.get('bounds') == _bounds(cfg) and result.get('schedules') == SCHEDULES
        and result.get('loss_contract') == LOSS_CONTRACT and set(result.get('arms', {})) == set(ARMS)
        and result.get('anchor_state_sha256') == report['anchor_state_sha256']
        and result.get('anchor_policy_sha256') == report['anchor_policy_sha256']
        and all(result.get(k) is False for k in ('equal_compute_claimed', 'efficacy_claimed', 'public_or_dev_feedback_used', 'optimizer_resume_claimed')),
        'fixed five-arm finite training contract differs')
    windows, by_id = result.get('windows'), {}
    require(type(windows) is list and len(windows) <= 13, 'at most thirteen retained behavior windows required')
    expected_order = ['shared-anchor'] + [f'{a}-slot{i}' for a in ARMS[1:] for i in (1, 2, 3)]
    for index, compact in enumerate(windows):
        name = 'windows/' + expected_order[index] + '.json'
        require(compact.get('window_id') == expected_order[index] and compact.get('artifact') == artifacts.get(name),
                'ordered unique behavior-window artifacts required')
        window = _json(_artifact(root, name, compact['artifact']), limit=32*1024**2)
        expected = {k: v for k, v in window.items() if k not in ('capture', 'preflight', 'verification')}
        verification = window['verification']
        expected['verification'] = {k: v for k, v in verification.items() if k not in ('rows', 'failed_row')}
        expected['verification']['failed_row'] = (None if not verification.get('failed_row') else
            {k: v for k, v in verification['failed_row'].items() if k != 'replay_log_probs'})
        expected.update(capture_sha256=window['capture']['seal_sha256'], policy_sha256=window['capture']['lineage']['policy_sha256'],
                        preflight_passed=(window.get('preflight') or {}).get('passed'), artifact=artifacts[name])
        require(compact == expected, 'window summary differs from complete raw evidence')
        require(_finite(window.get('deadline_epoch')) and window['deadline_epoch'] <= result['deadline_epoch']
            <= report['training_deadline_epoch'], 'window expanded original training deadline')
        expected_seed = cfg['collection']['seed'] + (0 if index == 0 else int(expected_order[index][-1]))
        require(window['capture']['config'].get('seed') == expected_seed % (2**63), 'window sampling seed differs')
        _window(window, training, admission, cfg['collection'], contracts, model_identity); by_id[window['window_id']] = window
    require(len({w['capture']['lineage']['model_identity_sha256'] for w in by_id.values()}) <= 1,
            'behavior windows changed model admission identity')
    states = result.get('state_sha256')
    require(type(states) is dict and set(states) <= set(ARMS) and states.get('anchor') == report['anchor_state_sha256']
        and all(_sha256(v) for v in states.values()), 'exact completed trainable states required')
    attempts = steps = 0
    for arm in ARMS:
        record = result['arms'][arm]; slots = record.get('slots')
        require(type(slots) is list and len(slots) <= len(SCHEDULES[arm]), 'finite predeclared optimizer slots required')
        current = report['anchor_state_sha256']
        if arm == 'anchor':
            require(not slots and record.get('optimizer_attempts', 0) == 0, 'anchor cannot be trained')
        elif record['status'] != 'not_executed':
            require(record.get('before_state_sha256') == current and record.get('optimizer_initial_state_entries') == 0
                and record.get('optimizer_scope') == 'fresh-per-arm-persistent-within-four-slots', 'fresh same-anchor optimizer required')
        for index, slot in enumerate(slots):
            key = 'shared-anchor' if index == 0 else f'{arm}-slot{index}'
            require(key in by_id, 'optimizer slot lacks current-policy window')
            window = by_id[key]; capture = window['capture']
            require(slot.get('slot') == index and slot.get('objective') == SCHEDULES[arm][index]
                and slot.get('window_id') == key and slot.get('pool_sha256') == capture['seal_sha256']
                and slot.get('before_state_sha256') == current == capture['lineage']['anchor_sha256']
                and window['status'] == 'complete' and window['preflight']['passed'] is True,
                'slot uses stale, foreign or unverified original pool')
            if index == 0:
                require(capture['lineage']['policy_sha256'] == report['anchor_policy_sha256'], 'first-slot pool differs from same anchor')
            physical = _counters(slot['physical']); attempts += physical['optimizer_attempts']; steps += physical['optimizer_steps']
            require(physical['optimizer_attempts'] <= 1, 'slot exceeded one optimizer attempt')
            if slot['status'] == 'complete':
                groups = [g for g in capture['groups'] if g['status'] == 'complete']
                objective = slot['objective']
                counts = ([1 for g in groups] if objective == 'known_target_ce' else
                          [sum(r['reward'] for r in g['rows']) for g in groups] if objective == 'exact_positive_ce' else
                          [int(g['category'] == 'mixed') for g in groups])
                total = sum(counts)
                weights = [{'group_id': g['group_id'], 'parent_id': g['parent_id'], 'weight': count/total}
                           for g, count in zip(groups, counts) if count] if total else []
                require(slot.get('prompt_weights') == weights, 'objective loss weights differ from complete original groups')
                if objective == 'exact_centered_ddis':
                    require(slot.get('replayed') == 8*len(weights), 'DDIS replay denominator differs from complete mixed groups')
                else:
                    require(slot.get('backward_trajectories') == len(weights), 'CE backward denominator differs')
                require(type(slot.get('updated')) is bool and _sha256(slot.get('after_state_sha256'))
                    and slot['updated'] == (slot['after_state_sha256'] != current)
                    and physical['optimizer_steps'] == int(slot['updated']), 'real optimizer commit differs from state delta')
                current = slot['after_state_sha256']
        if record['status'] == 'complete':
            require(len(slots) == len(SCHEDULES[arm]) and all(s['status'] == 'complete' for s in slots)
                and record.get('state_sha256') == states.get(arm) == current, 'complete arm lacks every finite slot/state')
    physical = _counters(result['physical'])
    require(all(physical.get(k) == sum(w['physical'].get(k, 0) for w in by_id.values()) for k in PROJECTION_COUNTERS),
            'training extra head projection charges differ')
    if 'shared-anchor' in by_id and by_id['shared-anchor']['status'] == 'complete':
        require(result.get('shared_anchor_collection_physical') == by_id['shared-anchor']['physical'],
                'shared first-window collection charge differs')
    require(physical['optimizer_attempts'] == attempts <= 16 and physical['optimizer_steps'] == steps
        and physical['model_forward_attempts'] <= cfg['max_model_forward_attempts'], 'training physical bound differs')
    complete = (len(windows) == 13 and all(w['status'] == 'complete' for w in by_id.values())
        and all(r['status'] == 'complete' for r in result['arms'].values()) and set(states) == set(ARMS)
        and result.get('anchor_restored') is True and result.get('engine_poisoned') is False
        and result.get('returned_after_deadline') is False)
    require((result.get('status') == 'complete') == complete, 'training completion exceeds verified work')
    return complete, states


def _export(root, arm, export, source_identity, model_identity, protocol_sha, contracts):
    checkpoint = export.get('checkpoint', {}); directory = root / 'checkpoints' / arm
    require(type(checkpoint) is dict and Path(checkpoint.get('root', '')).absolute() == directory.absolute()
        and _sha256(checkpoint.get('manifest_sha256')) and _sha256(checkpoint.get('state_sha256')),
        'source-bound exact arm export path required')
    require({p.name for p in directory.iterdir()} == {'manifest.json', 'trainable_state.safetensors'}, 'exact checkpoint inventory required')
    path = _regular(directory / 'manifest.json', limit=8*1024**2); manifest = _json(path)
    require(path.read_bytes() == canonical(manifest)+b'\n' and sha(path) == checkpoint['manifest_sha256'], 'canonical checkpoint manifest differs')
    required = {'format', 'base_identity', 'model_contract', 'trainable_contract', 'tokenizer_admission', 'origin',
        'trainable_tensors', 'state_sha256', 'file', 'optimizer_resumed', 'rng_resumed', 'fresh_optimizer_required'}
    require(set(manifest) == required and manifest['format'] == 'irisx/nvarc-compact-trainable-v1'
        and manifest['base_identity'] == model_identity and manifest['model_contract'] == contracts.model
        and manifest['trainable_contract'] == contracts.trainables and manifest['tokenizer_admission'] == contracts.tokenizer
        and manifest['state_sha256'] == checkpoint['state_sha256']
        and manifest['optimizer_resumed'] is False and manifest['rng_resumed'] is False and manifest['fresh_optimizer_required'] is True,
        'exact stable baseline model/trainable/tokenizer contract required')
    origin = manifest['origin']
    require(origin.get('phase') == 'pre_public' and origin.get('public_labels_used') is False
        and origin.get('public_ttt_applied') is False and origin.get('workflow') == WORKFLOW
        and origin.get('source_identity') == source_identity and origin.get('job_id') == JOB_ID
        and origin.get('arm') == arm and origin.get('protocol_sha256') == protocol_sha
        and origin.get('selected') is False and origin.get('multi_update_screen') is True,
        'pre-PUBLIC source/job/protocol-bound arm checkpoint required')
    tensor = _regular(directory / 'trainable_state.safetensors')
    require(manifest['file'] == {'name': tensor.name, 'bytes': tensor.stat().st_size, 'sha256': sha(tensor)}, 'checkpoint tensor file differs')
    shared._verify_tensor_file(tensor, manifest, expected_tensors=contracts.trainables['tensors'],
                              expected_trainable_contract=contracts.trainables)
    return checkpoint['state_sha256']


def _evaluation(report, root, artifacts, protocol, development, states):
    evaluation, exports = report.get('evaluation'), report['exports']; ids = protocol['development_parent_ids']
    require(type(evaluation) is dict and set(evaluation) == set(ARMS), 'all five paired evaluation arms required')
    cfg = {**protocol['evaluation'], **{k: protocol['training_config']['collection'][k] for k in ('context_tokens', 'generation_tokens')}}
    complete, scores, ttt_attempts, ttt_steps = [], {}, 0, 0
    for arm in ARMS:
        cells = evaluation[arm]
        require(type(cells) is dict and set(cells) == set(TREATMENTS), 'both paired treatments must retain denominators')
        for treatment in TREATMENTS:
            cell = cells[treatment]; rows = cell.get('records')
            require(type(rows) is list and [r.get('parent_id') for r in rows] == ids
                and cell.get('full_requested_denominator') == 16 and type(cell.get('complete')) is bool,
                'complete fixed evaluation parent denominator required')
            for row in rows:
                require(type(row.get('complete')) is bool and row.get('target_digest') == protocol['development_target_digests'][row['parent_id']],
                        'predeclared held-target identity differs')
                artifact = row.get('prediction_artifact')
                if artifact is not None:
                    name = f'predictions/{arm}/{treatment}/{row["parent_id"]}.json'
                    require(artifact == artifacts.get(name) and artifact.get('path') == name
                        and exports[arm]['status'] == 'complete', 'prediction needs its exact exported arm')
                    raw = _json(_artifact(root, name, artifact), limit=4*1024**2)
                    verification = _prediction(raw, development[row['parent_id']], row['parent_id'], cfg)
                    require(row.get('verification') == verification and (not row['complete'] or raw['complete']), 'generated verification differs')
                    ranked = raw['ranked_grids']; target = row['target_digest']
                    require(type(row.get('pass1')) is int and type(row.get('pass2')) is int
                        and row['pass1'] == int(bool(ranked) and digest(ranked[0]) == target)
                        and row['pass2'] == int(any(digest(g) == target for g in ranked)), 'exact scores differ from original ranked predictions')
                else:
                    require(not row['complete'] and row.get('pass1') is None and row.get('pass2') is None,
                            'missing generated score must remain unknown, not measured zero')
                if row.get('status') != 'not_executed':
                    counters = _counters(row['physical'])
                    require(row.get('reset_state_sha256') == states.get(arm)
                        and (row.get('starting_state_sha256') == states.get(arm)
                             or (row.get('starting_state_sha256') is None and artifact is None and not row['complete']
                                 and all(counters[k] == 0 for k in COUNTERS))),
                        'evaluation/reset differs from exported pre-TTT state')
                    if treatment == 'no_ttt':
                        require(counters['optimizer_attempts'] == counters['optimizer_steps'] == 0
                            and (artifact is None or row.get('ending_state_sha256') == states.get(arm)), 'noTTT generation changed checkpoint')
                    else:
                        ttt_attempts += counters['optimizer_attempts']; ttt_steps += counters['optimizer_steps']
                        adaptation = row.get('adaptation')
                        if adaptation is not None:
                            require(adaptation.get('data') == 'demonstrations-only' and adaptation.get('optimizer_resumed') is False
                                and adaptation.get('held_target_used_for_gradient') is False
                                and adaptation.get('requested_steps') == cfg['ttt_steps']
                                and type(adaptation.get('attempts')) is int
                                and counters['optimizer_attempts'] <= adaptation['attempts'] <= cfg['ttt_steps']
                                and adaptation.get('steps') == counters['optimizer_steps']
                                and adaptation.get('all_requested_complete') == (adaptation['steps'] == cfg['ttt_steps']),
                                'paired fresh demo-only TTT physical contract differs')
                        if row['complete']:
                            reset = row.get('functional_reset', {}); a, b = reset.get('nll_before'), reset.get('nll_restored')
                            require(adaptation is not None and adaptation['all_requested_complete'] is True
                                and _finite(a) and _finite(b) and reset.get('tolerance') == 1e-6 + 1e-5 * max(abs(a), abs(b))
                                and abs(a-b) <= reset['tolerance'] and reset.get('verified') is True
                                and reset.get('held_probe_used_for_gradient') is False, 'complete TTT pair lacks independent functional reset')
            count = sum(r['complete'] for r in rows)
            require(cell.get('completed_parents') == count and cell['complete'] == (count == 16), 'evaluation completion differs')
            for metric in ('pass1', 'pass2'):
                observed = sum(r[metric] or 0 for r in rows)
                require(cell.get('observed_'+metric) == observed
                    and cell.get(metric) == (observed if count == 16 else None), 'partial full-panel scores must stay unknown')
            complete.append(cell['complete'])
        scores[arm] = cells['no_ttt']['pass2']
        paired = report.get('paired_ttt', {}).get(arm)
        if paired is not None:
            left, right = (cells[t]['records'] for t in TREATMENTS)
            require(all(r['complete'] for r in left+right) and paired == {'complete': True, 'denominator': 16,
                'wins': sum(a['pass2'] == 0 and b['pass2'] == 1 for a, b in zip(left, right)),
                'losses': sum(a['pass2'] == 1 and b['pass2'] == 0 for a, b in zip(left, right)),
                'ties': sum(a['pass2'] == b['pass2'] for a, b in zip(left, right)), 'ttt_used_for_weight_selection': False},
                'paired TTT aggregate differs from complete records')
        elif all(c['complete'] for c in cells.values()):
            require(not report['complete'], 'completed arm requires paired aggregate')
    require(ttt_attempts <= 5*16*cfg['ttt_steps'], 'paired TTT attempts exceeded finite denominator')
    physical = _counters(report['physical']); train_physical = (report.get('training') or {}).get('physical', {})
    require(all(physical.get(k) == train_physical.get(k, 0) for k in PROJECTION_COUNTERS),
            'workflow diagnostic projections differ from retained training work')
    require(physical['optimizer_attempts'] == train_physical.get('optimizer_attempts', 0) + ttt_attempts
        and physical['optimizer_steps'] == train_physical.get('optimizer_steps', 0) + ttt_steps, 'whole-workflow optimizer conservation differs')
    return all(complete), scores


def _validate_report(report, root, *, source_identity, model_identity, contracts, phase_deadlines=None, training_root=None, training_manifest_path=None):
    """Internal offline validator; production callers never pass custom contracts."""
    root = Path(root)
    require(type(report) is dict and report.get('format') == 'irisx/compact-convergence-workflow-v1'
        and report.get('source_identity') == source_identity and report.get('job_id') == JOB_ID
        and report.get('full_requested_denominator') == 16 and type(report.get('complete')) is bool
        and report.get('status') in {'complete', 'partial', 'failed'}
        and all(report.get(k) is False for k in ('public_predictions_performed', 'public_answers_used', 'public_scoring_performed',
            'equal_compute_claimed', 'efficacy_claimed', 'capacity_gain_claimed'))
        and _sha256(report.get('anchor_state_sha256')) and _sha256(report.get('anchor_policy_sha256')),
        'source-bound no-PUBLIC baseline convergence report required')
    if phase_deadlines is not None:
        require(report.get('training_deadline_epoch') == phase_deadlines['screen_deadline_epoch']
            and report.get('deadline_epoch') == phase_deadlines['worker_deadline_epoch'], 'original phase deadline binding differs')
    require(_finite(report.get('training_deadline_epoch')) and _finite(report.get('deadline_epoch'))
        and report['training_deadline_epoch'] < report['deadline_epoch'], 'finite ordered original phase deadlines required')
    artifacts = report.get('private_artifacts')
    require(type(artifacts) is dict and 'protocol.json' in artifacts and len(artifacts) <= 13 + 5*16*2 + 6,
            'bounded complete private artifact inventory required')
    for name, artifact in artifacts.items():
        require(name != 'report.json' and artifact.get('path') == name, 'no circular or aliased artifact pin')
        _artifact(root, name, artifact)
    protocol = _json(root/'protocol.json')
    require(_h(protocol) == report.get('protocol_sha256') and protocol.get('version') == WORKFLOW
        and protocol.get('source_identity') == source_identity and protocol.get('arms') == list(ARMS)
        and protocol.get('schedules') == SCHEDULES and protocol.get('training_config') == contracts.config
        and protocol.get('training_bounds') == _bounds(contracts.config) and protocol.get('loss_contract') == LOSS_CONTRACT
        and protocol.get('evaluation') == contracts.evaluation and protocol.get('paired_treatments') == list(TREATMENTS)
        and protocol.get('full_requested_denominator') == 16 and protocol.get('requested_view_generations') == 320
        and protocol.get('maximum_ttt_optimizer_attempts') == 80*contracts.evaluation['ttt_steps']
        and protocol.get('probability_policy') == contracts.trainables['probability_policy'] and protocol.get('capacity_treatment') is None
        and all(protocol.get(k) is False for k in ('public_feedback_used', 'initial_weight_cleanliness_claimed', 'efficacy_claimed', 'equal_compute_claimed')),
        'exact stable baseline-only finite protocol required')
    training, development, admission = _panels(root, artifacts, protocol, contracts, training_root, training_manifest_path)
    trained, states = _training(report, root, artifacts, training, admission, contracts, model_identity)
    exports = report.get('exports')
    require(type(exports) is dict and set(exports) == set(ARMS), 'all declared exports must remain explicit')
    for arm, export in exports.items():
        if export.get('status') == 'complete':
            state = _export(root, arm, export, source_identity, model_identity, report['protocol_sha256'], contracts)
            require(states.get(arm) == state, 'exported checkpoint differs from completed training state')
        else:
            require(export == {'status': 'not_executed'}, 'unknown export cannot advertise a checkpoint')
    evaluated, scores = _evaluation(report, root, artifacts, protocol, development, states)
    expected_artifacts = {'protocol.json', 'source-binding.json', 'panel-admission.json', 'training-panel.json',
        'development-panel.json', 'source-panel-protocol.json'}
    expected_artifacts.update(w['artifact']['path'] for w in (report.get('training') or {}).get('windows', []))
    expected_artifacts.update(r['prediction_artifact']['path'] for a in report['evaluation'].values()
        for c in a.values() for r in c['records'] if r.get('prediction_artifact') is not None)
    require(set(artifacts) == expected_artifacts, 'private artifact inventory differs from actual declared windows/predictions')
    inventory = shared._inventory(root)
    if report['complete']:
        expected_files = expected_artifacts | {'report.json'} | {f'checkpoints/{a}/{name}' for a in ARMS
            for name in ('manifest.json', 'trainable_state.safetensors')}
        require(set(inventory) == expected_files, 'complete report contains unbound or unexpected artifact files')
    complete = (trained and evaluated and all(e['status'] == 'complete' for e in exports.values())
        and report.get('anchor_restored') is True and report.get('engine_poisoned') is False
        and report.get('returned_after_deadline') is False)
    require(report['complete'] == complete and (report['status'] == 'complete') == complete, 'completion exceeds independently verified work')
    selected = 'anchor'
    if complete:
        best = max(scores.values()); winners = [a for a in ARMS if scores[a] == best]
        if len(winners) == 1 and best > scores['anchor']:
            selected = winners[0]
    require(report.get('selected_arm') == selected and report.get('candidate_selected') is (selected != 'anchor')
        and report.get('selection_label', 'retain-anchor') == ('provisional-small-panel-candidate' if selected != 'anchor' else 'retain-anchor'),
        'only complete unique strict noTTT generated-exact improvement may select a candidate')
    return complete


def validate_result(result, worker_root, *, source_identity, device_identity, phase_deadlines=None, training_root=None, training_manifest_path=None):
    require(type(result) is dict and result.get('mode') == 'convergence' and result.get('job_id') == JOB_ID
        and result.get('source_identity') == source_identity and result.get('workload_identity') == WORKLOAD
        and result.get('device_identity') == device_identity and model_bound(result.get('model_identity'), '2b')
        and type(result.get('completed')) is bool, 'bound official baseline2B convergence worker required')
    require(training_root is not None and training_manifest_path is not None,
            'independent original training source and manifest paths required')
    receipt = result.get('convergence_report', {})
    require(receipt.get('path') == 'convergence/report.json', 'exact persisted convergence report required')
    path = _artifact(worker_root, receipt['path'], receipt); report = _json(path, limit=4*1024**2)
    require(result.get('convergence') == report, 'worker result differs from persisted convergence report')
    complete = _validate_report(report, Path(worker_root)/'convergence', source_identity=source_identity,
        model_identity=result['model_identity'], contracts=_official_contracts(), phase_deadlines=phase_deadlines,
        training_root=training_root, training_manifest_path=training_manifest_path)
    require(result['completed'] == complete, 'worker envelope completion differs')
    return complete


def _closed_worker(row, worker_root, config, plan, device_identity):
    normal = shared._normal_closure(row)
    root = Path(worker_root)
    require(_json(root/'ownership/closure.json') == row['closure'], 'persisted owned-worker closure differs')
    launch = _json(root/'ownership/launch.json')
    require(launch.get('scope') == 'dedicated-subreaper-tree'
        and launch.get('worker_argv') == [config['python'], '-B', '-m', 'tools.nvarc_posttrain_20261017.worker', '--config', str(root/'config.json')],
        'owned closure belongs to a different worker invocation')
    job = _json(root/'config.json')
    require(all(job.get(k) == value for k, value in {'job_id': JOB_ID, 'variant': '2b', 'arm': 'S', 'mode': 'convergence',
        'workload_identity': WORKLOAD, 'source_identity': config['source_identity'], 'device_identity': device_identity,
        'model_root': config['model_roots']['2b'], 'seed': 7321, 'adapter_seed': 731, 'parameters': {},
        'training_root': config['training_root'], 'training_manifest_path': config['training_manifest_path'],
        'public_path': config['public_path'], 'cpu_threads': 1,
        'allocator_fraction': .8, 'training_deadline_epoch': plan['screen_deadline_epoch'],
        'deadline_epoch': plan['worker_deadline_epoch'], 'outer_deadline_epoch': plan['wave_deadline_epoch'],
        'original_started_epoch': config['started_epoch'], 'original_deadline_epoch': config['deadline_epoch']}.items()),
        'closed worker source/device/job/original deadline configuration differs')
    require(launch.get('supervisor_identity') == row['closure']['root_identity'], 'launch/closure process identity differs')
    return normal


def run(config):
    require(config.get('workflow') == WORKFLOW and config.get('parameters', {}) == {}
        and type(config.get('model_roots')) is dict and set(config['model_roots']) == {'2b'}
        and not any(k in config for k in ('capacity', 'checkpoint', 'checkpoints', 'resume')),
        'fixed fresh official baseline2B-only convergence recipe required')
    require(_sha256(config.get('source_identity')), 'pinned convergence source SHA required')
    phase_plan(config, time.time()); source, output = Path(config['source_root']), Path(config['output_root'])
    require(not any(p.is_symlink() for p in (output, *output.parents)), 'regular new diagnostic output required')
    check_dataset_separation(config['input_root'], config['allowed_input_roots'])
    output.mkdir(parents=True, exist_ok=False)
    require(shutil.disk_usage(output).free >= 4*GIB, 'five checkpoint exports and private evidence need4GiB free')
    write_new(output/'isolation.json', {'mechanism': 'dataset-separated-provider-execution', 'evaluator_dataset_absent': True,
        'os_sandbox_claimed': False, 'public_inference_performed': False,
        'public_projection_use': 'training split exclusion only', 'public_answers_used': False})
    env = {**os.environ, **config['runtime_env'], 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    observed = subprocess.run([config['python'], '-B', '-m', 'tools.nvarc_posttrain_20261017.worker', '--topology'],
        cwd=source, env=env, check=True, capture_output=True, text=True, timeout=120)
    topology = shared._decode(observed.stdout.splitlines()[-1]); _topology(topology)
    write_new(output/'topology.json', topology)
    plan = phase_plan(config, time.time()); write_new(output/'phase-plan.json', plan)
    job = {'job_id': JOB_ID, 'variant': '2b', 'arm': 'S', 'mode': 'convergence',
        'source_identity': config['source_identity'], 'workload_identity': WORKLOAD,
        'device_identity': topology['device_identity'], 'model_root': config['model_roots']['2b'],
        'seed': 7321, 'adapter_seed': 731, 'cpu_threads': 1, 'parameters': {}, 'allocator_fraction': .8,
        'training_deadline_epoch': plan['screen_deadline_epoch'],
        'original_started_epoch': config['started_epoch'], 'original_deadline_epoch': config['deadline_epoch'],
        **{key: config[key] for key in ('training_root', 'training_manifest_path', 'public_path')}}
    progress('convergence_screen_start', arms=list(ARMS), variant='2b', parents=16, views=2, ttt_steps=[0, 32])
    wave = run_wave([job], python=config['python'], source_root=str(source), output_root=str(output/'convergence-2b'),
        deadline_epoch=plan['wave_deadline_epoch'], common_env=env, load_timeout_seconds=LOAD_SECONDS,
        stop_timeout_seconds=STOP_SECONDS, finalization_reserve_seconds=FINALIZATION_SECONDS)
    require(type(wave.get('jobs')) is list and len(wave['jobs']) == 1 and wave['jobs'][0].get('job_id') == JOB_ID,
            'exactly one owned official2B worker required')
    row = wave['jobs'][0]; root = output/'convergence-2b'/JOB_ID
    normal = _closed_worker(row, root, config, plan, topology['device_identity']) if row.get('closure') is not None else False
    validated = False
    if row.get('result') is not None:
        require(row.get('closure_verified') is True and row.get('closure') is not None
            and _json(root/'result.json') == row['result'], 'closed persisted worker required before result consumption')
        validated = validate_result(row['result'], root, source_identity=config['source_identity'],
            device_identity=topology['device_identity'], phase_deadlines=plan, training_root=config['training_root'], training_manifest_path=config['training_manifest_path'])
    complete = normal and validated and row.get('status') == 'completed' and wave.get('completed') is True
    write_new(output/'convergence-2b-wave.json', wave)
    summary = {'format': 'irisx/nvarc-convergence-controller-v1', 'run_id': config['run_id'],
        'source_identity': config['source_identity'], 'workflow': WORKFLOW, 'workload_identity': WORKLOAD,
        'completed': complete, 'requested_models': ['2b'], 'requested_parents_per_arm': 16, 'arms': list(ARMS),
        'matched_views': 2, 'paired_ttt_steps': [0, 32], 'workers': wave['jobs'], 'phase_plan': plan,
        'public_inference_performed': False, 'public_scoring_performed': False, 'public_score': None, 'official_score': None,
        'clean_generalization_claimed': False, 'architecture_expansion_tested': False,
        'automatic_following_run': False, 'training_or_ensemble_selected_for_public': False}
    write_new(output/'run-summary.json', summary)
    progress('convergence_screen_closed', completed=complete, wall_seconds=wave.get('wall_seconds'))
    return summary


def close_diagnostic(config, control, proof):
    """Bind every bounded private artifact after both owned process trees close."""
    from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
    from .score import closure_structure
    closure_structure(proof); verify_closed_proof(proof)
    control, output = Path(control), Path(config['output_root'])
    require(config.get('workflow') == WORKFLOW and config.get('parameters', {}) == {}
        and set(config.get('model_roots', {})) == {'2b'} and _sha256(config.get('source_identity'))
        and not any(k in config for k in ('capacity', 'checkpoint', 'checkpoints', 'resume')),
        'closed fixed official baseline2B controller configuration required')
    require(_json(control/'controller-config.json') == config
        and _json(control/'owned-tree/closure.json') == proof, 'persisted controller configuration/closure differs')
    launch = _json(control/'owned-tree/launch.json')
    require(launch.get('scope') == 'dedicated-subreaper-tree'
        and launch.get('supervisor_identity') == proof['root_identity']
        and launch.get('worker_argv') == [config['python'], '-I', '-B',
            str(Path(config['source_root'])/'tools/nvarc_posttrain_20261017/bootstrap.py'),
            '--controller', str(control/'controller-config.json')], 'owner closure belongs to a different controller invocation')
    require(not control.absolute().is_relative_to(output.absolute()) and _json(control/'owner-closure.json') == proof,
            'external persisted owner closure required')
    files = shared._inventory(output); complete = False; plan = None
    if 'run-summary.json' in files:
        summary = _json(output/'run-summary.json')
        require(summary.get('format') == 'irisx/nvarc-convergence-controller-v1'
            and summary.get('source_identity') == config['source_identity'] and summary.get('run_id') == config['run_id']
            and summary.get('workflow') == summary.get('workload_identity') == WORKFLOW
            and summary.get('requested_models') == ['2b'] and summary.get('arms') == list(ARMS)
            and summary.get('requested_parents_per_arm') == 16 and summary.get('matched_views') == 2
            and summary.get('paired_ttt_steps') == [0, 32] and type(summary.get('completed')) is bool
            and all(summary.get(k) is False for k in ('public_inference_performed', 'public_scoring_performed',
                'clean_generalization_claimed', 'architecture_expansion_tested', 'automatic_following_run', 'training_or_ensemble_selected_for_public'))
            and summary.get('public_score') is None and summary.get('official_score') is None,
            'closed finite baseline-only screen summary differs')
        plan = _json(output/'phase-plan.json')
        require(plan == phase_plan(config, plan.get('admitted_epoch')) == summary.get('phase_plan'), 'closed original/active phase plan differs')
        wave = _json(output/'convergence-2b-wave.json'); topology = _json(output/'topology.json'); _topology(topology)
        require(summary.get('workers') == wave.get('jobs') and type(wave.get('jobs')) is list
            and len(wave['jobs']) == 1 and wave['jobs'][0].get('job_id') == JOB_ID, 'closed worker inventory differs')
        row = wave['jobs'][0]; root = output/'convergence-2b'/JOB_ID
        normal = _closed_worker(row, root, config, plan, topology['device_identity']) if row.get('closure') is not None else False
        validated = False
        if row.get('result') is not None:
            require(row.get('closure_verified') is True and row.get('closure') is not None
                and _json(root/'result.json') == row['result'], 'closed worker result differs')
            validated = validate_result(row['result'], root, source_identity=config['source_identity'],
                device_identity=topology['device_identity'], phase_deadlines=plan, training_root=config['training_root'], training_manifest_path=config['training_manifest_path'])
        eligible = normal and validated and row.get('status') == 'completed' and wave.get('completed') is True
        require(summary['completed'] == eligible, 'summary completion exceeds closed worker evidence')
        complete = eligible and proof['worker_returncode'] == proof['returncode'] == 0 and proof['forced'] is False
        require(shared._inventory(output) == files, 'private artifacts changed during final verification')
    finalized = time.time(); active_end = plan['active_deadline_epoch'] if plan is not None else config['deadline_epoch']
    within = (_finite(config.get('started_epoch')) and _finite(config.get('deadline_epoch'))
        and config['deadline_epoch'] == config['started_epoch'] + 43200
        and config['started_epoch'] <= finalized < min(config['deadline_epoch'], active_end))
    terminal = {'format': 'irisx/nvarc-closed-convergence-v1', 'run_id': config['run_id'],
        'finalization_epoch': finalized, 'finalization_within_original_session': within,
        'status': 'CLOSED_DIAGNOSTIC', 'completed': complete and within, 'source_manifest_sha256': config['source_identity'],
        'workflow': WORKFLOW, 'files': files, 'closure_sha256': sha(control/'owner-closure.json'),
        'generation_may_resume': False, 'public_score': None, 'official_score': None,
        'public_inference_performed': False, 'public_scoring_performed': False,
        'provider_terminal_verified': False, 'clean_generalization_claimed': False,
        'new_model_or_ensemble_selected_for_public': False}
    write_new(control/'terminal.json', terminal)
    after = time.time()
    if within and after >= min(config['deadline_epoch'], active_end):
        terminal.update(completed=False, finalization_epoch=after, finalization_within_original_session=False,
                        late_during_terminal_persistence=True)
        staged = control/'terminal.json.tmp'
        with staged.open('xb') as stream:
            stream.write(canonical(terminal)+b'\n'); stream.flush(); os.fsync(stream.fileno())
        staged.replace(control/'terminal.json')
    return terminal
