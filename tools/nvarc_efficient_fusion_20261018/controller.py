"""Torch-free independent reconstruction, owned dispatch and immutable closure.

All genuine model work lives in the explicitly launched worker. This consumer
reconstructs exact rewards, curriculum allocation, objectives, probability gaps,
trainable checkpoint bytes, held-demo predictions and conservative selection.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from tools.arc2_goal_sprint_20261017.data import canonical, load_data
from tools.arc2_goal_sprint_20261017.launch import TRAINING_MANIFEST_SHA256, sha as file_sha, write_new
from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
from tools.nvarc_capacity_20261018.controller import run_owned
from tools.nvarc_posttrain_20261017 import matched_controller as shared
from tools.nvarc_posttrain_20261017.convergence_controller import _prediction, _probe
from tools.nvarc_posttrain_20261017.codec import encode_example, grid_tokens, parse_completion
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY, full_precision_execution_contract
from .contracts import (ARMS, DEFAULT_CONFIG, LOSS_CONTRACT, PROTOCOL, ROUTES, SELECTION_RULE,
                        CoverageChooser, category, physical_bounds, require, sha, validate_config)
from .panels import prepare_panels, validate_prepared

MAX_EVIDENCE_BYTES = 2 * 1024**3
COUNTERS = ('forward_calls', 'sampled_tokens', 'optimizer_steps', 'optimizer_attempts',
    'generation_forward_attempts', 'generation_input_tokens', 'generation_row_token_slots',
    'generation_finished_row_token_slots', 'generation_padding_tokens', 'model_forward_attempts', 'model_input_tokens')


def source_snapshot(root):
    root = Path(root).absolute(); files = {}
    for directory in ('src', 'tools'):
        for path in sorted((root/directory).rglob('*.py')):
            shared._regular(path, limit=16*1024**2)
            files[path.relative_to(root).as_posix()] = {'bytes': path.stat().st_size, 'sha256': file_sha(path)}
    path = root/'tools/nvarc_posttrain_20261017/model-pins.json'; shared._regular(path)
    files[path.relative_to(root).as_posix()] = {'bytes': path.stat().st_size, 'sha256': file_sha(path)}
    require(files and sum(v['bytes'] for v in files.values()) <= 64*1024**2, 'bounded complete source closure required')
    return {'format': 'irisx/efficient-fusion-source-v1', 'files': files}


def verify_source(root, snapshot, expected):
    require(shared._sha256(expected) and sha(snapshot) == expected and source_snapshot(root) == snapshot,
            'full immutable fusion source closure changed')


def collection_config(cfg, slot=0):
    return {'seed': (cfg['seed']+slot) % (2**63), 'max_groups': 1, 'target_mixed_groups': 1,
        **{k: cfg[k] for k in ('microbatch', 'context_tokens', 'generation_tokens', 'learning_rate')}}


def counters(value):
    require(type(value) is dict and set(value) == set(COUNTERS)
            and all(type(x) is int and x >= 0 for x in value.values()), 'complete nonnegative physical counters required')
    require(value['optimizer_steps'] <= value['optimizer_attempts'], 'optimizer steps exceed attempts')
    return value


def cost(value):
    require(type(value) is dict and set(value) == {'calls', 'tensor_bytes', 'wall_seconds'}
            and all(type(value[k]) is int and value[k] >= 0 for k in ('calls', 'tensor_bytes'))
            and shared._finite(value['wall_seconds']) and value['wall_seconds'] >= 0, 'finite full-policy checksum accounting required')


def sum_counters(records):
    values = [counters(r) for r in records]
    return {key: sum(r[key] for r in values) for key in COUNTERS}


def validate_replays(verify, rows, tolerance, *, complete):
    gaps = []; verified = 0; failed = None; nonfinite = False
    require(type(verify['rows']) is list and len(verify['rows']) <= len(rows), 'bounded replay observations required')
    for index, replay in enumerate(verify['rows']):
        row = rows[index]; values = replay['replay_log_probs']; classified = replay['nonfinite_values']
        require(replay['sample_id'] == row['sample_id'] and len(values) == len(row['input_ids'])
            and all(x is None or (shared._finite(x) and x <= 1e-6) for x in values), 'aligned original replay required')
        missing = [i for i, value in enumerate(values) if value is None]
        require(type(classified) is list and [v['index'] for v in classified] == missing
            and all(set(v) == {'index', 'value'} and v['value'] in ('nan', 'inf', '-inf') for v in classified),
            'nonfinite replay must retain exact index and classification')
        if missing:
            require(not complete and index == len(verify['rows'])-1 and replay['max_abs_logp_gap'] is None,
                    'nonfinite replay cannot be admitted or followed by further replay')
            gap = None; nonfinite = True
        else:
            gap = max(abs(a-b) for a, b in zip(values, row['behavior_log_probs'])); gaps.append(gap)
            require(replay['max_abs_logp_gap'] == gap, 'measured probability gap differs')
        if gap is not None and gap <= tolerance: verified += 1
        else:
            require(index == len(verify['rows'])-1, 'failed probability gate cannot continue replay')
            failed = replay
    require(verify['observed_rows'] == len(verify['rows']) and verify['verified_rows'] == verified
        and verify['max_logp_gap'] == (max(gaps) if gaps else None)
        and verify['nonfinite_replay_observed'] is nonfinite and verify['failed_row'] == failed,
        'probability summary differs from retained vectors')
    if complete: require(verified == 8 and failed is None, 'eight finite strict original-probability replays required')
    return verified


def _validate_group(raw, task, entry, cfg, allocation, admission_sha, expected_state, tolerance):
    slot = allocation['slot']; group = raw['group']; cc = collection_config(cfg, slot)
    require(raw['format'] == 'irisx/efficient-fusion-group-v1' and raw['slot'] == slot and raw['config'] == cc
            and raw['seal_sha256'] == sha({k: v for k, v in raw.items() if k != 'seal_sha256'})
            and raw['behavior_probabilities_replaced'] is False and raw['partial_groups_used_for_loss'] is False
            and raw['sealed_before_updates'] is True, 'fresh exact group seal/config differs')
    lineage = raw['lineage']
    require(set(lineage) == {'policy_sha256', 'anchor_sha256', 'model_identity_sha256', 'admission_sha256'}
            and all(shared._sha256(v) for v in lineage.values()) and lineage['anchor_sha256'] == expected_state
            and lineage['admission_sha256'] == admission_sha, 'fresh current fusion lineage differs')
    pairs, held = task['train'], entry['held_index']; target = pairs[held]['output']
    example = encode_example([p for i, p in enumerate(pairs) if i != held], pairs[held]['input'],
                             context=cc['context_tokens'], generation=cc['generation_tokens'])
    require(group['group_id'] == 'g'+str(slot) and group['parent_id'] == entry['parent_id']
            and group['allocation'] == allocation and group['prompt_ids'] == example['prompt_ids']
            and group['demos_dropped'] == example['demos_dropped'] and group['training_target'] == target,
            'training prompt/target/allocation differs from pinned source')
    rows, batches = group['rows'], group['batches']; require(type(rows) is list and len(rows) <= 8, 'bounded actual rows required')
    requested = accepted = returned = 0
    for i, batch in enumerate(batches):
        require(set(batch) == {'requested', 'returned', 'accepted', 'status'}
                and all(type(batch[k]) is int for k in ('requested', 'returned', 'accepted'))
                and batch['requested'] == min(cc['microbatch'], 8-requested)
                and 0 <= batch['accepted'] <= batch['returned'] <= batch['requested']
                and batch['status'] in ('complete', 'deadline', 'failed')
                and (batch['status'] == 'complete' or i == len(batches)-1), 'physical microbatch accounting differs')
        if batch['status'] == 'complete': require(batch['accepted'] == batch['returned'] == batch['requested'], 'partial successful microbatch')
        requested += batch['requested']; accepted += batch['accepted']; returned += batch['returned']
    require(accepted == len(rows) and requested <= 8, 'retained/physical row conservation differs')
    for index, row in enumerate(rows):
        n, ids, completion, logps = row['prompt_length'], row['input_ids'], row['completion_ids'], row['behavior_log_probs']
        require(type(n) is int and n == len(group['prompt_ids']) and type(ids) is list and len(ids) <= cc['context_tokens']
            and ids[:n] == group['prompt_ids'] and ids[n:] == completion and type(completion) is list
            and 1 <= len(completion) <= cc['generation_tokens'] and all(type(t) is int and 0 <= t < 16 for t in ids)
            and row['completion_tokens'] == len(completion) and 15 not in completion[:-1]
            and row['stop'] in ('completed', 'length') and (row['stop'] == 'completed') == (completion[-1] == 15)
            and (row['stop'] != 'length' or len(completion) == cc['generation_tokens'])
            and type(logps) is list and len(logps) == len(ids)
            and all(shared._finite(v) and v <= 1e-6 for v in logps) and all(v == 0 for v in logps[:n]),
            'original raw compact probability/token path differs')
        require(row['sample_id'] == group['group_id']+':s'+str(index) and row['group_id'] == group['group_id']
            and all(row[k] == entry[k] for k in ('parent_id', 'family_id', 'variant_group', 'task_sha256'))
            and all(row[k] == v for k, v in lineage.items()) and row['training_target'] == target
            and type(row['reward']) in (int, float) and row['reward'] == float(parse_completion(completion) == target),
            'exact reward or source/group/model lineage differs')
        if row['reward']: require(completion == grid_tokens(target)+[15], 'positive compact completion not unique target')
    verify = raw['verification']; verified = validate_replays(verify, rows, tolerance, complete=raw['status'] == 'complete')
    if raw['status'] == 'complete':
        require(group['status'] == 'complete' and len(rows) == requested == returned == 8
                and group['category'] == category([r['reward'] for r in rows]) and verified == 8
                and verify['failed_row'] is None and raw['full_policy_after_sha256'] == lineage['policy_sha256'],
                'complete frozen group requires all eight original verified trajectories')
    physical = counters(raw['physical'])
    retained_tokens = sum(r['completion_tokens'] for r in rows)
    require(physical['sampled_tokens'] >= retained_tokens and physical['generation_row_token_slots'] >= retained_tokens
        and physical['model_forward_attempts'] >= physical['generation_forward_attempts'] + len(verify['rows'])
        and physical['model_input_tokens'] >= physical['generation_input_tokens'] + sum(len(r['input_ids']) for r in rows[:len(verify['rows'])]),
        'physical collection contradicts retained generation/replay traces')
    if raw['status'] == 'complete':
        lengths = [r['completion_tokens'] for r in rows]
        steps = sum(max(lengths[i:i+cc['microbatch']]) for i in range(0, 8, cc['microbatch']))
        row_slots = sum(len(lengths[i:i+cc['microbatch']])*max(lengths[i:i+cc['microbatch']]) for i in range(0, 8, cc['microbatch']))
        require(physical['sampled_tokens'] == retained_tokens and physical['generation_forward_attempts'] == steps
            and physical['generation_row_token_slots'] == row_slots and physical['generation_finished_row_token_slots'] == row_slots-retained_tokens
            and physical['generation_input_tokens'] == 8*len(group['prompt_ids']) + row_slots-8
            and physical['model_forward_attempts'] == physical['forward_calls'] == steps+8,
            'complete collection physical trace conservation differs')
    counters(raw['physical']); cost(raw['hash_cost'])
    require(raw['physical']['optimizer_steps'] == raw['physical']['optimizer_attempts'] == 0,
            'group collection must not update optimizer')
    return rows


def _checkpoint(root, arm, export, report, protocol, contracts):
    require(export['status'] == 'complete', 'completed exact export required')
    spec = export['checkpoint']; directory = root/'checkpoints'/arm
    require(directory.is_dir() and not directory.is_symlink()
            and {p.name for p in directory.iterdir()} == {'manifest.json', 'trainable_state.safetensors'}, 'exact checkpoint file inventory required')
    manifest = shared._json(directory/'manifest.json'); path = directory/'trainable_state.safetensors'; shared._regular(path)
    require(file_sha(directory/'manifest.json') == spec['manifest_sha256']
            and manifest['state_sha256'] == spec['state_sha256'] == report['training']['state_sha256'][arm]
            and manifest['base_identity'] == report['base_identity'] and manifest['model_contract'] == contracts.model
            and manifest['trainable_contract'] == contracts.trainables and manifest['tokenizer_admission'] == contracts.tokenizer
            and manifest['file'] == {'name': path.name, 'bytes': path.stat().st_size, 'sha256': file_sha(path)},
            'checkpoint original model/tensor/manifest binding differs')
    expected = {'phase': 'pre_public', 'public_ttt_applied': False, 'public_labels_used': False,
        'workflow': PROTOCOL, 'arm': arm, 'source_identity': report['source_identity'],
        'protocol_sha256': report['protocol_sha256'], 'selected': False,
        'optimizer_slots': 0 if arm == 'anchor' else protocol['config']['updates']}
    require(manifest['origin'] == expected and manifest['optimizer_resumed'] is False
        and manifest['rng_resumed'] is False and manifest['fresh_optimizer_required'] is True, 'checkpoint origin/resume contract differs')
    shared._verify_tensor_file(path, manifest, FP32_BACKBONE_POLICY,
        expected_tensors=contracts.trainables['tensors'], expected_trainable_contract=contracts.trainables)
    return spec['state_sha256']


def validate_result(root, *, expected_source, expected_prepared, model_identity, fixture_contracts=None):
    """fixture_contracts is an internal test seam, never a CLI or artifact knob."""
    started = time.monotonic(); root = Path(root); validate_prepared(expected_prepared)
    report = shared._json(root/'report.json', limit=8*1024**2); protocol = shared._json(root/'protocol.json')
    prepared = shared._json(root/'prepared-panels.json'); require(prepared == expected_prepared, 'panel differs from independent raw-source reread')
    require(report['format'] == 'irisx/efficient-fusion-workflow-v1' and report['source_identity'] == expected_source
        and report['protocol_sha256'] == sha(protocol) and protocol['version'] == PROTOCOL
        and protocol['source_identity'] == expected_source and protocol['panel_pins'] == prepared['pins'], 'source/workflow/panel protocol differs')
    cfg = validate_config(protocol['config'])
    contracts = fixture_contracts or SimpleNamespace(model=shared._official_model_contract(),
        trainables=shared._official_trainable_contract(FP32_BACKBONE_POLICY), tokenizer=shared._official_tokenizer_admission(),
        probability_tolerance=.05)
    if fixture_contracts is None:
        require(cfg == DEFAULT_CONFIG and prepared['protocol']['train_count'] == 64
            and prepared['protocol']['dev_count'] == 96, 'official fixed fusion recipe required')
    require(report['engine_contract'] == contracts.model and report['trainable_contract'] == contracts.trainables
        and report['tokenizer_admission'] == contracts.tokenizer and report['base_identity'] == model_identity
        and report['probability_execution'] == full_precision_execution_contract(), 'exact admitted model/arithmetic contract differs')
    ids = prepared['protocol']['development_parent_ids']; denominator = len(ids)
    require(protocol['arms'] == list(ARMS) and protocol['loss_contract'] == LOSS_CONTRACT
        and protocol['bounds'] == physical_bounds(cfg) and protocol['selection_rule'] == SELECTION_RULE
        and protocol['development_parent_ids'] == ids and protocol['full_requested_denominator'] == denominator
        and protocol['development_target_digests'] == prepared['protocol']['development_target_digest']
        and protocol['requested_view_generations'] == len(ARMS)*denominator*2 and protocol['ttt_steps'] == 0,
        'fixed loss/evaluation/selection declaration differs')
    for key in ('public_inference_performed', 'public_answers_used', 'public_scoring_performed', 'ttt_performed',
                'equal_compute_claimed', 'efficacy_claimed', 'clean_generalization_claimed', 'owned_process_closure_verified'):
        require(report[key] is False, 'unsupported workflow claim')
    artifacts = report['private_artifacts']
    for name, receipt in artifacts.items(): shared._artifact(root, name, receipt)
    train = report['training']; require(train is not None and train['config'] == cfg and train['loss_contract'] == LOSS_CONTRACT
        and train['bounds'] == physical_bounds(cfg) and train['anchor_state_sha256'] == report['anchor_state_sha256']
        and train['anchor_policy_sha256'] == report['anchor_policy_sha256'], 'training protocol/anchor differs')
    chooser = CoverageChooser(prepared['protocol']['training_parent_ids'], cfg)
    entries = {row['parent_id']: row for row in prepared['admission']['parents']}
    first = chooser.order[0]; task = prepared['training'][first]; entry = entries[first]
    example = encode_example(task['train'][1:], task['train'][0]['input'], context=cfg['context_tokens'], generation=cfg['generation_tokens'])
    if train['preflight'] is not None:
        raw = shared._json(root/'probability-preflight.json', limit=32*1024**2)
        require(train['preflight']['sha256'] == sha(raw), 'preflight evidence binding differs')
        probe_physical = counters(train['preflight']['physical']); work = raw['probe']['work']
        require(probe_physical['model_forward_attempts'] == sum(v['forward_attempts'] for k, v in work.items() if k != 'total')
            and probe_physical['forward_calls'] == sum(v['forward_successes'] for k, v in work.items() if k != 'total')
            and probe_physical['model_input_tokens'] == sum(v['input_tokens'] for k, v in work.items() if k != 'total')
            and probe_physical['optimizer_steps'] == probe_physical['optimizer_attempts'] == 0,
            'preflight physical work differs from retained stage traces')
        require(raw['probe']['deadline'] <= train['deadline_epoch'] <= report['training_deadline_epoch'], 'preflight exceeded original training deadline')
        if raw.get('nonfinite_fields'):
            require(raw['passed'] is False and train['preflight']['passed'] is False and not train['groups']
                and train['status'] == 'failed', 'classified nonfinite preflight cannot authorize training')
            locations = set()
            for entry in raw['nonfinite_fields']:
                require(set(entry) == {'path', 'value'} and entry['value'] in ('nan', 'inf', '-inf')
                    and type(entry['path']) is list and entry['path'], 'classified nonfinite preflight location required')
                key = tuple(entry['path']); require(key not in locations, 'duplicate nonfinite preflight path'); locations.add(key)
                value = raw
                for part in entry['path']: value = value[part]
                require(value is None, 'classified preflight value must be null, never a finite substitute')
        else:
            require(_probe(raw, {'policy_sha256': train['anchor_policy_sha256']}, collection_config(cfg), contracts.probability_tolerance,
                prompt=example['prompt_ids'], deadline=raw['probe']['deadline'], contracts=contracts, model_identity=model_identity)
                == train['preflight']['passed'], 'initial preflight result differs')
    states = {arm: report['anchor_state_sha256'] for arm in ARMS}
    categories = []; shared_identity = None
    for index, summary in enumerate(train['groups']):
        parent, allocation = chooser.choose(); path = f'groups/{index:03}.json'
        require(path in artifacts, 'captured group lacks immutable artifact binding')
        raw = shared._json(root/path, limit=8*1024**2)
        rows = _validate_group(raw, prepared['training'][parent], entries[parent], cfg, allocation,
            prepared['pins']['admission_sha256'], states['routed_fusion'], contracts.probability_tolerance)
        require(summary['seal_sha256'] == raw['seal_sha256'] and summary['lineage'] == raw['lineage']
            and summary['physical'] == raw['physical'] and summary['hash_cost'] == raw['hash_cost']
            and summary['wall_seconds'] == raw['wall_seconds'] and summary['parent_id'] == parent
            and summary['category'] == raw['group']['category'] and summary['status'] == raw['status']
            and summary['rollouts_retained'] == len(rows)
            and summary['rollouts_requested'] == sum(b['requested'] for b in raw['group']['batches'])
            and summary['verification'] == {k: v for k, v in raw['verification'].items() if k not in ('rows', 'failed_row')},
            'group summary differs from full raw evidence')
        require(raw['deadline_epoch'] <= train['deadline_epoch'], 'group exceeds original training deadline')
        if shared_identity is None: shared_identity = raw['lineage']['model_identity_sha256']
        require(shared_identity == raw['lineage']['model_identity_sha256'], 'model identity changed between groups')
        if raw['status'] != 'complete':
            require(index == len(train['groups'])-1 and train['status'] != 'complete', 'partial group cannot precede further work'); break
        kind = chooser.observe(parent, [r['reward'] for r in rows]); categories.append(kind)
        for arm in ('routed_fusion', 'matched_target_ce'):
            slots = train['arms'][arm]['slots']
            if index >= len(slots):
                require(train['status'] != 'complete', 'complete recipe missing optimizer slot'); continue
            row = slots[index]; expected_objective = ROUTES[kind] if arm == 'routed_fusion' else 'known_target_ce'
            require(row['slot'] == index and row['parent_id'] == parent and row['objective'] == expected_objective
                and row['group_seal_sha256'] == raw['seal_sha256'] and row['prompt_sha256'] == sha(raw['group']['prompt_ids'])
                and row['before_state_sha256'] == states[arm], 'paired prompt/order/objective/state chain differs')
            counters(row['physical'])
            require(row['physical']['optimizer_attempts'] <= 1 and row['physical']['sampled_tokens'] == 0
                and all(row['physical'][k] == 0 for k in COUNTERS if k.startswith('generation_')),
                'optimizer slot cannot hide generation work or duplicate attempts')
            require(type(row['update_returned']) is bool, 'optimizer outcome distinct from scheduling status required')
            if expected_objective == 'exact_centered_ddis':
                name = f'gradients/{index:03}.json'
                require(name in artifacts and 'gradient_replay' in row, 'actual train-gradient gate evidence required')
                gradient = shared._json(root/name, limit=8*1024**2)
                require(gradient['format'] == 'irisx/efficient-fusion-gradient-replay-v1'
                    and gradient['slot'] == index and gradient['group_id'] == raw['group']['group_id']
                    and gradient['tolerance'] == contracts.probability_tolerance
                    and gradient['seal_sha256'] == sha({k: v for k, v in gradient.items() if k != 'seal_sha256'})
                    and row['gradient_replay'] == {k: v for k, v in gradient.items() if k not in ('rows', 'failed_row')},
                    'actual gradient replay seal/binding differs')
                validate_replays(gradient, rows, contracts.probability_tolerance, complete=row['update_returned'])
                if row['update_returned']:
                    require(gradient['status'] == 'complete' and gradient['commit_admitted'] is True
                        and shared._finite(row['max_replay_logp_gap'])
                        and row['max_replay_logp_gap'] <= contracts.probability_tolerance,
                        'actual AF3 gradient gate must precede commit')
            if row['update_returned']:
                require(type(row['updated']) is bool and shared._sha256(row['after_state_sha256'])
                    and row['updated'] == (row['before_state_sha256'] != row['after_state_sha256'])
                    and row['physical']['optimizer_steps'] == int(row['updated'])
                    and row['physical']['optimizer_attempts'] <= 1
                    and shared._finite(row['loss']) and shared._finite(row['gradient_norm']), 'actual finite optimizer commit differs')
                expected_graphs = 8 if expected_objective == 'exact_centered_ddis' else 1
                expected_tokens = (sum(len(r['input_ids']) for r in rows) if expected_graphs == 8
                    else len(raw['group']['prompt_ids']) + len(grid_tokens(raw['group']['training_target']))+1)
                require(row['physical']['model_forward_attempts'] == row['physical']['forward_calls'] == expected_graphs
                    and row['physical']['model_input_tokens'] == expected_tokens,
                    'optimizer replay graph/token accounting differs')
                if expected_objective == 'exact_centered_ddis':
                    require(row['mixed_groups'] == 1 and row['physical_trajectories'] == row['replayed'] == 8,
                            'mixed route must execute actual complete upstream AF3/DDIS')
                else:
                    require(row['backward_trajectories'] == 1, 'CE must use one unique complete target graph')
                require(row['exact_positive_duplicate_graphs_avoided'] == (7 if expected_objective == 'exact_positive_ce' else 0),
                        'exact-positive duplicate compression differs')
                states[arm] = row['after_state_sha256']
            else:
                require(row['physical']['optimizer_steps'] == 0, 'unreported committed optimizer step')
            if row['status'] != 'complete': require(train['status'] != 'complete', 'failed optimizer slot cannot complete recipe')
    require(train['curriculum'] == chooser.report(), 'curriculum coverage/stratum receipts differ')
    for arm in ARMS[1:]:
        require(len(train['arms'][arm]['slots']) <= len(train['groups']), 'optimizer slots exceed actual groups')
    if train['status'] == 'complete':
        require(len(train['groups']) == cfg['updates'] and train['curriculum']['parents_observed'] == len(prepared['training'])
            and train['anchor_restored'] is True and train['engine_poisoned'] is False and not train['returned_after_deadline']
            and train['preflight']['passed'] is True
            and all(train['arms'][a]['status'] == 'complete' and len(train['arms'][a]['slots']) == cfg['updates']
                    and all(s['status'] == 'complete' for s in train['arms'][a]['slots']) for a in ARMS[1:]),
            'complete multiupdate recipe requires all declared work and coverage')
    require(train['state_sha256'] == states, 'returned state chain differs from accepted optimizer work')
    counters(train['physical']); counters(report['physical']); cost(train['hash_cost_outside_groups']); cost(report['workflow_hash_cost'])
    phases = [g['physical'] for g in train['groups']] + [s['physical'] for a in ARMS[1:] for s in train['arms'][a]['slots']]
    if train['preflight'] is not None: phases.append(train['preflight']['physical'])
    require(train['physical'] == sum_counters(phases), 'training physical phase conservation differs')
    require(train['physical']['model_forward_attempts'] <= cfg['max_model_forward_attempts']
        and train['physical']['optimizer_attempts'] <= 2*cfg['updates'], 'actual bounded training work exceeded')
    require(train['physical']['optimizer_steps'] == sum(s['physical']['optimizer_steps'] for a in ARMS[1:] for s in train['arms'][a]['slots']),
            'physical optimizer totals differ')
    evaluations = report['evaluation']; require(set(evaluations) == set(ARMS), 'exact evaluation arm inventory required')
    exports_complete = True
    for arm in ARMS:
        if report['exports'][arm]['status'] == 'complete': _checkpoint(root, arm, report['exports'][arm], report, protocol, contracts)
        else: exports_complete = False
        cell = evaluations[arm]; rows = cell['records']; require([r['parent_id'] for r in rows] == ids
            and cell['full_requested_denominator'] == denominator, 'full fixed development denominator/order required')
        expected_eval = dict.fromkeys(COUNTERS, 0)
        for row in rows:
            parent = row['parent_id']; task = prepared['development'][parent]
            require(row['target_digest'] == prepared['protocol']['development_target_digest'][parent], 'fixed held target differs')
            if 'prediction_artifact' not in row:
                require(not row['complete'] and row['pass1'] is row['pass2'] is None, 'unexecuted development score invented'); continue
            artifact = row['prediction_artifact']; require(artifacts.get(artifact['path']) == artifact, 'prediction artifact binding differs')
            raw = shared._json(shared._artifact(root, artifact['path'], artifact)); _prediction(raw, task, parent, cfg)
            for view in raw['views']:
                n = view['tokens']; size = len(view['token_evidence']['prompt_ids'])+n-1
                for key in ('forward_calls','sampled_tokens','generation_forward_attempts','generation_row_token_slots','model_forward_attempts'):
                    expected_eval[key] += n
                for key in ('generation_input_tokens','model_input_tokens'): expected_eval[key] += size
            target = task['train'][0]['output']; ranked = raw['ranked_grids']
            require(row['complete'] == raw['complete'] and row['pass1'] == int(bool(ranked) and ranked[0] == target)
                and row['pass2'] == int(target in ranked) and row['state_sha256'] == states[arm], 'generated exact score/state differs')
        if 'physical' in cell:
            observed = counters(cell['physical'])
            require(observed['optimizer_steps'] == observed['optimizer_attempts'] == 0,
                    'no-TTT development must be optimizer-free')
            require(all(observed[k] >= expected_eval[k] for k in COUNTERS), 'evaluation work contradicts retained generations')
            if cell['complete']: require(observed == expected_eval, 'complete serial evaluation trace conservation differs')
        else: require(not any(expected_eval.values()), 'retained development work lacks physical receipt')
        done = sum(r['complete'] for r in rows)
        require(cell['completed_parents'] == done and cell['complete'] == (done == denominator), 'completion summary differs')
        for metric in ('pass1', 'pass2'):
            observed = sum(r[metric] or 0 for r in rows)
            require(cell['observed_'+metric] == observed and cell[metric] == (observed if done == denominator else None),
                    'full panel score differs from retained generations')
    require(report['physical'] == sum_counters([train['physical']] + [v['physical'] for v in evaluations.values() if 'physical' in v]),
            'workflow physical phase conservation differs')
    complete = (train['status'] == 'complete' and exports_complete and all(v['complete'] for v in evaluations.values())
        and report['anchor_restored'] and not report['engine_poisoned'] and not report['returned_after_deadline'] and report['status'] == 'complete')
    require(report['complete'] == complete, 'workflow completion exceeds retained evidence')
    scores = {a: evaluations[a]['pass2'] for a in ARMS}; selected = 'anchor'
    if complete:
        best = max(scores.values()); winners = [a for a, n in scores.items() if n == best]
        if len(winners) == 1 and best > scores['anchor']: selected = winners[0]
    require(report['selected_arm'] == selected and report['candidate_selected'] == (selected != 'anchor'), 'conservative generated-exact selection differs')
    return {'complete': complete, 'selected_arm': selected, 'full_requested_denominator': denominator,
        'pass2': scores, 'group_categories': {k: categories.count(k) for k in ROUTES},
        'training_parent_coverage': chooser.report()['parents_observed'], 'report_sha256': file_sha(root/'report.json'),
        'independent_verification_wall_seconds': time.monotonic()-started, 'public_scoring_performed': False,
        'fresh_model_reload_performed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('model-root', 'training-root', 'training-manifest', 'public-challenges', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    for key in ('started-epoch', 'session-deadline-epoch', 'deadline-epoch', 'training-deadline-epoch'):
        parser.add_argument('--'+key, type=float, required=True)
    parser.add_argument('--execute-official', action='store_true'); args = parser.parse_args(argv)
    now = time.time(); require(args.execute_official, 'explicit official execution flag required')
    require(all(math.isfinite(v) for v in (args.started_epoch, args.session_deadline_epoch, args.deadline_epoch, args.training_deadline_epoch))
        and 0 < args.started_epoch <= now < args.training_deadline_epoch < args.deadline_epoch <= args.session_deadline_epoch
        == args.started_epoch+43200 and args.deadline_epoch <= now+10800, 'original finite session and bounded active recipe required')
    source = Path(__file__).resolve().parents[2]; output = args.output.absolute()
    require(not output.exists() and not any(p.is_symlink() for p in (output, *output.parents)), 'new regular controller destination required')
    output.mkdir(parents=True); snapshot = source_snapshot(source); identity = sha(snapshot)
    write_new(output/'source-manifest.json', snapshot)
    command = [sys.executable, '-B', '-m', 'tools.nvarc_efficient_fusion_20261018.worker']
    for key in ('model_root', 'training_root', 'training_manifest', 'public_challenges', 'started_epoch',
                'session_deadline_epoch', 'training_deadline_epoch'):
        command.extend(['--'+key.replace('_', '-'), str(getattr(args, key))])
    command += ['--output', str(output/'worker'), '--source-root', str(source), '--source-manifest', str(output/'source-manifest.json'),
        '--source-sha256', identity, '--deadline-epoch', str(args.deadline_epoch-120), '--execute-official']
    env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
           'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    closure = run_owned(command, source_root=source, output=output, deadline=args.deadline_epoch-90, env=env)
    verify_source(source, snapshot, identity); verification = None; validation_error = None
    verification_start = time.monotonic()
    try:
        if (output/'worker/comparison/report.json').is_file():
            data = load_data(args.training_root, args.training_manifest, args.public_challenges,
                             expected_manifest_sha256=TRAINING_MANIFEST_SHA256)
            prepared = prepare_panels(*data, training_root=args.training_root, training_manifest_path=args.training_manifest)
            from tools.nvarc_posttrain_20261017.materials import verify_model
            model_identity = verify_model(args.model_root, '2b')
            verification = validate_result(output/'worker/comparison', expected_source=identity,
                                            expected_prepared=prepared, model_identity=model_identity)
    except Exception as error:
        validation_error = {'type': type(error).__name__, 'message': str(error)[:1024]}
    inventory = {}; total = 0
    for path in sorted((output/'worker').rglob('*')):
        if path.is_dir(): continue
        shared._regular(path, limit=MAX_EVIDENCE_BYTES); total += path.stat().st_size
        require(total <= MAX_EVIDENCE_BYTES, 'bounded2GiB full result evidence exceeded')
        inventory[path.relative_to(output).as_posix()] = {'bytes': path.stat().st_size, 'sha256': file_sha(path)}
    verify_source(source, snapshot, identity); verify_closed_proof(closure['proof'])
    complete = bool(closure['normal_exit'] and verification and verification['complete'] and time.time() < args.deadline_epoch)
    result = {'format': 'irisx/efficient-fusion-local-closure-v1', 'complete': complete,
        'source_identity': identity, 'closure': closure, 'verification': verification, 'validation_error': validation_error,
        'selected_arm': verification['selected_arm'] if complete else 'anchor',
        'artifacts': inventory, 'total_artifact_bytes': total, 'deadline_epoch': args.deadline_epoch,
        'finalization_epoch': time.time(), 'verification_and_sealing_wall_seconds': time.monotonic()-verification_start,
        'public_scoring_performed': False, 'provider_execution_claimed': False, 'generation_may_resume': False}
    write_new(output/'closed-result.json', result)
    if time.time() >= args.deadline_epoch and result['complete']:
        # Fail closed rather than leave an apparently completed late seal.
        from tools.arc2_goal_sprint_20261017.run import atomic_json
        result.update(complete=False, selected_arm='anchor', late_during_persistence=True, finalization_epoch=time.time())
        atomic_json(output/'closed-result.json', result)
    print(json.dumps({k: result[k] for k in ('complete', 'selected_arm', 'public_scoring_performed')}, sort_keys=True))
    return 0 if result['complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
