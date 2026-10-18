"""Local CPU-only owned-tree dispatch and source/artifact closure for capacity-v2.

No provider APIs, upload, model download, scorer or automatic experiment retry.
This controller does not import torch. Official architecture admission happens
inside the worker; this consumer independently checks exact trainable tensors,
raw dev generations, selection, source bytes and fresh process closure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time

from tools.arc2_goal_sprint_20261017.data import canonical, digest, loo_example
from tools.arc2_goal_sprint_20261017.launch import TRAINING_MANIFEST_SHA256, require, sha, write_new
from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard, verify_closed_proof
from tools.nvarc_posttrain_20261017 import matched_controller as shared
from tools.nvarc_posttrain_20261017.convergence_controller import _prediction
from tools.nvarc_posttrain_20261017.codec import encode_example
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
from tools.nvarc_posttrain_20261017.probability_trace import validate_rows, validate_trace

TREATMENTS = ('baseline', 'depth32', 'moe4_top2')
LAYERS = (6, 13, 20, 27)
MAX_SOURCE_BYTES = 64 * 1024**2
MAX_ARTIFACT_BYTES = 2 * 1024**3


def source_snapshot(root):
    root = Path(root).absolute()
    files = {}
    for directory in ('src', 'tools'):
        for path in sorted((root / directory).rglob('*.py')):
            shared._regular(path, limit=16 * 1024**2)
            files[path.relative_to(root).as_posix()] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    pin = root / 'tools/nvarc_posttrain_20261017/model-pins.json'
    shared._regular(pin); files[pin.relative_to(root).as_posix()] = {'bytes': pin.stat().st_size, 'sha256': sha(pin)}
    require(files and sum(row['bytes'] for row in files.values()) <= MAX_SOURCE_BYTES, 'bounded source closure required')
    return {'format': 'irisx/capacity-local-source-v1', 'files': files,
        'scope': 'all repository tools/src Python and exact official model pins; installed runtime is separately observed'}


def source_identity(snapshot):
    return hashlib.sha256(canonical(snapshot)).hexdigest()


def verify_source(root, snapshot, expected):
    require(shared._sha256(expected) and source_identity(snapshot) == expected,
            'pinned source snapshot identity differs')
    require(source_snapshot(root) == snapshot, 'source changed after immutable dispatch binding')
    return True


def official_trainable_contract(treatment):
    require(treatment in TREATMENTS, 'known capacity treatment required')
    contract = shared._official_trainable_contract(FP32_BACKBONE_POLICY)
    tensors = {}
    for name, row in contract['tensors'].items():
        found = re.match(r'^(base_model\.model\.model\.layers\.)(\d+)(\..+)$', name)
        if not found:
            tensors[name] = row; continue
        prefix, index, suffix = found.group(1), int(found.group(2)), found.group(3)
        if treatment == 'depth32':
            mapped = index + sum(layer < index for layer in LAYERS)
            tensors[prefix + str(mapped) + suffix] = row
            if index in LAYERS:
                tensors[prefix + str(mapped + 1) + suffix] = row
        elif treatment == 'moe4_top2' and index in LAYERS and suffix.startswith('.mlp.'):
            for expert in range(4):
                tensors[prefix + str(index) + '.mlp.experts.' + str(expert) + suffix[len('.mlp'):]] = row
        else:
            tensors[name] = row
    if treatment == 'moe4_top2':
        for layer in LAYERS:
            tensors[f'base_model.model.model.layers.{layer}.mlp.router.weight'] = {'shape': [4, 2048], 'dtype': 'torch.float32'}
    return {**contract, 'tensors': tensors, 'tensor_count': len(tensors),
        'parameter_count': sum(math.prod(row['shape']) for row in tensors.values()),
        'capacity_format': 'irisx/compact-capacity-fp32-v2', 'treatment': treatment,
        'router_parameters': 4 * 4 * 2048 if treatment == 'moe4_top2' else 0}




def expected_accounting(base, treatment, *, rank, selected_layers):
    """Independent pure geometry, not artifact-supplied parameter totals."""
    n, h, inter = (base[k] for k in ('num_hidden_layers', 'hidden_size', 'intermediate_size'))
    q, kv = base['num_attention_heads'] * base['head_dim'], base['num_key_value_heads'] * base['head_dim']
    attention = 2 * h * q + 2 * h * kv; ffn = 3 * h * inter; norms = 2 * h + 2 * base['head_dim']
    native = 33 * h + n * (attention + ffn + norms)
    attn_lora = rank * (2 * (h + q) + 2 * (h + kv)); ffn_lora = rank * 3 * (h + inter)
    blocks = len(selected_layers) if treatment == 'depth32' else 0
    moe = len(selected_layers) if treatment == 'moe4_top2' else 0
    extra = blocks * (attention + ffn + norms) + moe * 3 * ffn
    routers = moe * h * 4
    trainable = (n + blocks) * (attn_lora + ffn_lora) + moe * 3 * ffn_lora + 32 * h + routers
    total = native + extra + trainable
    active = total - 32 * h - moe * 2 * (ffn + ffn_lora)
    linear = (n + blocks) * (attention + ffn + attn_lora + ffn_lora) + 16 * h + moe * (ffn + ffn_lora + h * 4)
    return {'source_native_parameters': native, 'added_native_parameters': extra,
        'frozen_parameters': native + extra, 'trainable_parameters': trainable,
        'total_resident_parameters': total, 'potentially_active_parameters_per_token': active,
        'resident_parameter_bytes_fp32': total * 4, 'router_parameters': routers,
        'layers': n + blocks, 'selected_original_layers': list(selected_layers) if treatment != 'baseline' else [],
        'experts_per_selected_layer': 4 if moe else 1, 'experts_executed_per_token': 2 if moe else 1,
        'linear_forward_flops_per_token': 2 * linear,
        'flops_kind': 'analytic linear forward only; excludes quadratic attention/backward/recompute/optimizer',
        'equal_compute_claimed': False, 'actual_wall_seconds': None, 'actual_peak_memory_bytes': None}


def _numeric_summary(cell, treatment, schedule, *, fixture_trainables):
    records = cell['training']['records']
    for index, row in enumerate(records):
        example = schedule[index]['example']
        require(type(row['updated']) is bool and all(type(row[key]) in (int, float)
                and math.isfinite(row[key]) and row[key] >= 0 for key in ('loss', 'gradient_norm')),
                'finite nonnegative observed SFT loss/gradient required')
        require(row['tokens'] == len(example['prompt_ids']) + len(example['completion_ids'])
                and row['completion_tokens'] == len(example['completion_ids'])
                and row['supervised_tokens'] == sum(example['loss_mask'])
                and row['loss_mode'] == example['loss_mode'] == 'final'
                and row['demos_dropped'] == example['demos_dropped'], 'SFT observed token/loss-mask summary differs')
        require(type(row['router_gradient_norms']) is dict and all(value is None or
            (type(value) in (int, float) and math.isfinite(value) and value >= 0)
            for value in row['router_gradient_norms'].values()), 'finite observed router gradients required')
    if 'parameter_accounting' not in cell:
        require(not records, 'training records lack model parameter accounting'); return
    receipt = cell['model_contract']['capacity_v2']
    base = receipt['base_model_contract'] if fixture_trainables is not None else shared._official_model_contract()
    layers = receipt['selected_original_layers'] if fixture_trainables is not None else list(LAYERS)
    if treatment == 'baseline':
        layers = ()
    expected_trainable = official_trainable_contract(treatment) if fixture_trainables is None else fixture_trainables[treatment]
    expected = expected_accounting(base, treatment, rank=expected_trainable['rank'], selected_layers=layers)
    require(receipt['accounting'] == expected and expected['trainable_parameters'] == expected_trainable['parameter_count'],
            'independent architecture parameter accounting differs')
    actual = cell['parameter_accounting']
    require(actual == {'resident_parameters': expected['total_resident_parameters'],
        'trainable_parameters': expected['trainable_parameters'],
        'resident_parameter_bytes': expected['resident_parameter_bytes_fp32'],
        'active_parameters_per_token_proxy': expected['potentially_active_parameters_per_token'],
        'active_parameter_proxy_measured_flops': False, 'architecture_accounting': expected},
        'observed resident/trainable/active parameter accounting differs')
    for phase in ('training', 'evaluation'):
        if 'physical' not in cell[phase]: continue
        require(all(type(value) is int and value >= 0 for value in cell[phase]['physical'].values()),
                'nonnegative observed phase counters required')
        wall = cell[phase]['wall_seconds']
        require(type(wall) in (int, float) and math.isfinite(wall) and wall >= 0, 'finite nonnegative phase wall required')
    if 'approximate_flops' in cell:
        approx = cell['approximate_flops']; active = expected['potentially_active_parameters_per_token']
        require(approx['measured'] is False
            and approx['training_dense_equivalent_proxy'] == 6 * active * cell['training'].get('physical', {}).get('model_input_tokens', 0)
            and approx['inference_linear_proxy'] == 2 * active * cell['evaluation'].get('physical', {}).get('model_input_tokens', 0),
            'approximate FLOPs must reconstruct from actual token counters and remain unmeasured')
    if 'peak_memory' in cell:
        peak = cell['peak_memory']
        require(type(peak['gpu_measured']) is bool, 'explicit measured memory scope required')
        if peak['gpu_measured']:
            require(all(type(peak[key]) is int and peak[key] >= 0 for key in ('allocated_bytes', 'reserved_bytes'))
                    and peak['reserved_bytes'] >= peak['allocated_bytes'], 'consistent measured allocator peaks required')
        else:
            require(peak['allocated_bytes'] is None and peak['reserved_bytes'] is None, 'unmeasured GPU memory must remain unknown')


def _probability_gate(root, cell, artifacts, *, prompt, fixture):
    entry = cell.get('probability_admission')
    if entry is None:
        require(cell['training']['attempted_updates'] == 0, 'training without numerical admission forbidden')
        return False
    artifact = entry['artifact']
    require(artifacts.get(artifact['path']) == artifact, 'numerical admission artifact missing')
    raw = shared._json(shared._artifact(root, artifact['path'], artifact))
    tolerance = 1e-5 if fixture else .05
    require(raw.get('format') == 'irisx/capacity-sampled-full-admission-v1'
            and raw.get('probability_policy') == FP32_BACKBONE_POLICY
            and raw.get('tolerance') == entry['tolerance'] == tolerance
            and raw.get('optimizer_updates') == 0
            and raw['physical_counter_deltas']['optimizer_steps'] == 0
            and raw['physical_counter_deltas']['optimizer_attempts'] == 0,
            'fixed no-update probability gate required')
    passed = raw['error'] is None and len(raw['rows']) == 2
    if raw.get('passed'):
        validate_trace(raw['trace'], expected_trace_sha256=raw['trace']['sha256'])
        validate_rows(raw['rows'], raw['trace'])
        require(all(row['input_ids'][:row['prompt_length']] == prompt for row in raw['rows']),
                'probability gate did not use fixed first training prompt')
    for mode in ('eval_nograd', 'train_grad'):
        stage = raw['replays'].get(mode)
        if stage is None:
            passed = False; continue
        require(stage['mode'] == mode and stage['backward_validated'] is False, 'replay path contract differs')
        gaps = []
        require(len(stage['rows']) <= len(raw['rows']), 'replay row count exceeds actual samples')
        for index, replay in enumerate(stage['rows']):
            original = raw['rows'][index]; behavior = original['behavior_log_probs'][original['prompt_length']:]
            actual = replay['full_log_probs']
            require(replay['row_index'] == index and replay['completion_ids'] == original['completion_ids']
                    and replay['behavior_log_probs'] == behavior and len(actual) == len(behavior)
                    and all(type(v) in (int, float) and math.isfinite(v) for v in behavior + actual),
                    'original sampled probability denominator or replay differs')
            gaps.extend(abs(a - b) for a, b in zip(actual, behavior))
        measured = max(gaps) if gaps else None
        require(stage['metrics']['max_abs_logp_gap'] == measured and stage['metrics']['tokens'] == len(gaps),
                'replayed probability gap summary differs')
        passed = passed and stage['status'] == 'completed' and len(stage['rows']) == 2 and measured is not None and measured <= tolerance
    require(raw['passed'] == entry['passed'] == bool(passed), 'independently reconstructed probability gate differs')
    require(passed or cell['training']['attempted_updates'] == 0, 'failed numerical gate cannot admit an optimizer')
    return bool(passed)


def _official_model_manifest(manifest, treatment):
    base = shared._official_model_contract(); model = manifest['model_contract']; receipt = model.get('capacity_v2', {})
    layers = 32 if treatment == 'depth32' else 28
    require({k: v for k, v in model.items() if k != 'capacity_v2'} ==
            {**base, 'num_hidden_layers': layers, 'layer_types': ['full_attention'] * layers}
            and receipt.get('base_model_contract') == base and receipt.get('treatment') == treatment
            and receipt.get('probability_policy') == FP32_BACKBONE_POLICY
            and receipt.get('source_base_dtype') == 'torch.bfloat16' and receipt.get('resident_dtype') == 'torch.float32'
            and receipt.get('adapter_seed') == 731 and receipt.get('native_weights_trainable') is False,
            'independent official capacity architecture contract differs')
    require(shared.model_bound(manifest['base_identity'], '2b')
            and manifest['tokenizer_admission'] == shared._official_tokenizer_admission(),
            'official model/tokenizer binding differs')
    layout = []
    for index in range(28):
        layout.append({'index': len(layout), 'original_index': index, 'new': False})
        if treatment == 'depth32' and index in LAYERS:
            layout.append({'index': len(layout), 'original_index': index, 'new': True})
    require(receipt.get('layout') == layout and receipt.get('selected_original_layers') == ([] if treatment == 'baseline' else list(LAYERS)),
            'fixed capacity layer placement differs')


def _schedule(training, parents, cfg):
    rng = random.Random(cfg['seed']); result = []
    while len(result) < cfg['updates']:
        order = list(parents); rng.shuffle(order)
        for parent in order:
            demos, query, target = loo_example(training[parent], rng, augment=True)
            example = encode_example(demos, query, target, context=cfg['context_tokens'],
                                     generation=cfg['generation_tokens'], loss_mode='final')
            result.append({'step': len(result), 'parent_id': parent,
                'training_task_sha256': hashlib.sha256(canonical(training[parent])).hexdigest(),
                'example': example, 'example_sha256': hashlib.sha256(canonical(example)).hexdigest()})
            if len(result) == cfg['updates']: break
    return result


def validate_comparison(root, *, expected_source, training_root=None, training_manifest=None,
                        fixture_trainables=None):
    """Independent raw-token/dev counts and streamed checkpoint digest checks."""
    root = Path(root); report = shared._json(root / 'report.json', limit=4 * 1024**2)
    require(report['format'] == 'irisx/nvarc-capacity-comparison-v1' and report['source_identity'] == expected_source,
            'capacity report source/format differs')
    artifacts = report['private_artifacts']
    require(type(artifacts) is dict and len(artifacts) <= 1000, 'bounded exact artifact map required')
    for name, item in artifacts.items():
        require(item.get('path') == name, 'artifact index/path mismatch')
        shared._artifact(root, name, item)
    protocol = shared._json(root / 'protocol.json')
    require(hashlib.sha256(canonical(protocol)).hexdigest() == report['protocol_sha256']
            and protocol['source_identity'] == expected_source and protocol['treatments'] == list(TREATMENTS)
            and protocol['probability_policy'] == FP32_BACKBONE_POLICY,
            'capacity protocol identity differs')
    cfg = protocol['config']
    require(cfg['views'] == 2 and cfg['ttt_steps'] == 0 and 1 <= cfg['updates'] <= 64, 'fixed bounded comparison required')
    if fixture_trainables is None:
        require(cfg == {'updates': 64, 'learning_rate': 2e-5, 'seed': 20261018, 'adapter_seed': 731,
            'context_tokens': 8192, 'generation_tokens': 931, 'evaluation_seed': 20261018, 'views': 2,
            'ttt_steps': 0, 'training_wall_seconds': 900, 'evaluation_wall_seconds': 900}, 'official fixed config differs')
    training = shared._json(root / 'training-panel.json'); development = shared._json(root / 'development-panel.json')
    panel = shared._json(root / 'source-panel-protocol.json'); binding = shared._json(root / 'source-binding.json')
    require(len(training) == len(development) == 16 and set(training).isdisjoint(development)
            and set(development) == set(protocol['development_parent_ids'])
            and all(set(task) == {'train'} for task in (*training.values(), *development.values())),
            'fixed train-only independent sixteen-parent panels required')
    require(protocol['panel_pins']['protocol_sha256'] == hashlib.sha256(canonical(panel)).hexdigest()
            and protocol['panel_pins']['source_binding_sha256'] == hashlib.sha256(canonical(binding)).hexdigest(),
            'source panel binding differs')
    if training_root is not None:
        raw = shared._regular(training_manifest).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == TRAINING_MANIFEST_SHA256
                == binding['source']['training_manifest_sha256'], 'pinned original training source required')
        manifest = json.loads(raw)
        for name, record in binding['source']['files'].items():
            path = shared._regular(Path(training_root) / Path(name).name)
            require(all(manifest['files'][name].get(k) == v for k, v in record.items()) and path.stat().st_size == record['bytes'] and sha(path) == record['sha256'],
                    'original training bytes changed')
            parent = path.stem
            if parent in training or parent in development:
                require(json.loads(path.read_bytes())['train'] == (training | development)[parent]['train'],
                        'retained train/dev panel differs from admitted source')
    for parent, task in development.items():
        require(digest(task['train'][0]['output']) == protocol['development_target_digests'][parent]
                and hashlib.sha256(canonical(task)).hexdigest() == panel['development_task_sha256'][parent],
                'development target or task binding differs')
    schedule = shared._json(root / 'training-schedule.json')
    require(schedule == _schedule(training, panel['training_parent_ids'], cfg)
            and hashlib.sha256(canonical(schedule)).hexdigest() == protocol['training_schedule_sha256'],
            'independently reconstructed identical SFT schedule differs')
    def evaluation(cell, label):
        require(cell['full_requested_denominator'] == 16 and len(cell['records']) == 16
                and [r['parent_id'] for r in cell['records']] == protocol['development_parent_ids'],
                'every held-demo denominator and row required')
        first = second = completed = 0
        for row in cell['records']:
            require(row['target_digest'] == protocol['development_target_digests'][row['parent_id']], 'target pin differs')
            if row.get('prediction_artifact'):
                artifact = row['prediction_artifact']; require(artifacts.get(artifact['path']) == artifact, 'prediction artifact missing')
                raw = shared._json(shared._artifact(root, artifact['path'], artifact))
                _prediction(raw, development[row['parent_id']], row['parent_id'], cfg)
                target = development[row['parent_id']]['train'][0]['output']; ranked = raw['ranked_grids']
                p1, p2 = int(bool(ranked) and ranked[0] == target), int(target in ranked)
                require(row['pass1'] == p1 and row['pass2'] == p2 and row['complete'] == raw['complete'],
                        'generated-exact development score differs')
                first += p1; second += p2; completed += int(raw['complete'])
            else:
                require(not row['complete'] and row['pass1'] is None and row['pass2'] is None, 'unexecuted rows must remain unknown')
        require(cell['completed_parents'] == completed and cell['complete'] == (completed == 16)
                and cell['observed_pass1'] == first and cell['observed_pass2'] == second
                and cell['pass1'] == (first if completed == 16 else None)
                and cell['pass2'] == (second if completed == 16 else None), 'full-denominator score differs')
        return cell['complete']
    anchor_complete = evaluation(report['anchor'], 'initial_anchor')
    complete = anchor_complete
    for treatment in TREATMENTS:
        cell = report['treatments'][treatment]; completed = evaluation(cell['evaluation'], treatment)
        admitted = _probability_gate(root, cell, artifacts, prompt=schedule[0]['example']['prompt_ids'],
                                     fixture=fixture_trainables is not None)
        training_record = cell['training']; records = training_record['records']
        require(len(records) <= cfg['updates'] and all(
            {k: row[k] for k in ('step', 'parent_id', 'training_task_sha256', 'example_sha256')} ==
            {k: schedule[index][k] for k in ('step', 'parent_id', 'training_task_sha256', 'example_sha256')}
            for index, row in enumerate(records)), 'actual SFT examples/order differ')
        require(training_record['accepted_updates'] == sum(int(row['updated']) for row in records), 'accepted updates differ')
        _numeric_summary(cell, treatment, schedule, fixture_trainables=fixture_trainables)
        if training_record['completed']:
            require(len(records) == training_record['accepted_updates'] == training_record['attempted_updates'] == cfg['updates']
                    and training_record['physical']['optimizer_steps'] == cfg['updates'], 'complete identical optimizer budget required')
        pin = cell['checkpoint']
        if pin is not None:
            checkpoint_root = root / 'checkpoints' / treatment
            require(Path(pin['root']).absolute() == checkpoint_root.absolute(), 'checkpoint escaped treatment output')
            manifest_path = shared._regular(checkpoint_root / 'manifest.json')
            require(sha(manifest_path) == pin['manifest_sha256'], 'checkpoint manifest SHA differs')
            manifest = shared._json(manifest_path)
            require(manifest['state_sha256'] == pin['state_sha256'] and manifest['origin']['treatment'] == treatment
                    and manifest['origin']['source_identity'] == expected_source
                    and manifest['origin']['protocol_sha256'] == report['protocol_sha256']
                    and manifest['origin']['training_schedule_sha256'] == protocol['training_schedule_sha256']
                    and manifest['origin']['public_labels_used'] is False
                    and manifest['origin']['public_ttt_applied'] is False, 'immutable checkpoint origin differs')
            if fixture_trainables is None:
                _official_model_manifest(manifest, treatment)
            require(manifest['base_identity'] == cell['base_identity'] and manifest['model_contract'] == cell['model_contract']
                    and manifest['trainable_contract'] == cell['trainable_contract'], 'retained engine/checkpoint contracts differ')
            expected = official_trainable_contract(treatment) if fixture_trainables is None else fixture_trainables[treatment]
            require(manifest['trainable_contract'] == expected, 'independently fixed trainable contract differs')
            shared._verify_tensor_file(checkpoint_root / 'trainable_state.safetensors', manifest, FP32_BACKBONE_POLICY,
                expected_tensors=expected['tensors'], expected_trainable_contract=expected)
        actual_complete = admitted and completed and training_record['completed'] and pin is not None and not cell.get('engine_poisoned', True)
        require(not cell['complete'] or actual_complete, 'treatment claimed incomplete work as complete')
        complete = complete and cell['complete'] and actual_complete
    complete = complete and not report['returned_after_deadline'] and report['status'] == 'complete'
    require(report['complete'] == complete, 'comparison completion differs from retained evidence')
    selected = 'initial_anchor'
    if complete:
        scores = {t: report['treatments'][t]['evaluation']['pass2'] for t in TREATMENTS}
        best = max(scores.values()); winners = [t for t in TREATMENTS if scores[t] == best]
        if len(winners) == 1 and best > report['anchor']['pass2']: selected = winners[0]
    require(report['selected_treatment'] == selected and report['candidate_selected'] == (selected != 'initial_anchor'),
            'predeclared generated-exact selection differs')
    return {'complete': complete, 'selected_treatment': selected, 'raw_development_predictions_verified': True,
        'exact_trainable_tensors_verified': True, 'source_identity': expected_source,
        'comparison_report_sha256': sha(root / 'report.json')}



def validate_public_bundle(root, *, comparison, solver_payload):
    """Answer-free per-arm reconstruction only after external ownership closure."""
    from .public import verify_public_artifacts
    root = Path(root); bundle = shared._json(root / 'public-bundle.json')
    binding = shared._json(root / 'comparison/source-binding.json')
    require(binding['split']['receipt']['public_digest'] == digest(solver_payload),
            'PUBLIC input differs from comparison source binding')
    frozen = shared._json(root / 'frozen-selection.json')
    require(comparison['complete'] and frozen == bundle['frozen_selection']
            and frozen['comparison_report_sha256'] == comparison['comparison_report_sha256']
            and frozen['source_identity'] == comparison['source_identity']
            and frozen['selected_treatment'] == comparison['selected_treatment']
            and bundle['requested_treatments'] == list(TREATMENTS)
            and bundle['full_requested_queries_per_treatment'] == 167
            and bundle['public_scoring_performed'] is False, 'PUBLIC changed frozen development selection or denominator')
    report = shared._json(root / 'comparison/report.json'); verified = {}
    for treatment in TREATMENTS:
        checkpoint = report['treatments'][treatment]['checkpoint']
        pin = {k: checkpoint[k] for k in ('root', 'manifest_sha256', 'state_sha256')}
        arm_root = root / 'public' / treatment
        if not (arm_root / 'report.json').is_file():
            verified[treatment] = {'verified': False, 'complete': False, 'reason': 'worker interrupted before retained arm report',
                'tasks': 120, 'queries': 167, 'completed_views': None}
            continue
        require(bundle['treatments'].get(treatment) == shared._json(arm_root / 'report.json'),
                'PUBLIC bundle/arm report mismatch')
        verified[treatment] = verify_public_artifacts(arm_root, solver_payload=solver_payload,
            frozen_selection=frozen, checkpoint_pin=pin, treatment=treatment)
    complete = all(v['complete'] for v in verified.values())
    require(bundle['complete'] == complete, 'PUBLIC bundle completion differs from all three fixed recipes')
    return {'complete': complete, 'treatments': verified, 'selected_treatment': frozen['selected_treatment'],
        'comparison_report_sha256': frozen['comparison_report_sha256'], 'public_scoring_performed': False,
        'full_requested_tasks_per_treatment': 120, 'full_requested_queries_per_treatment': 167}



def seal_public_predictions(output, *, verification, closure, expected_source, started_epoch, session_deadline_epoch):
    """New local seal, not a provider receipt or legacy scorer authorization."""
    verify_closed_proof(closure['proof'])
    require(closure['closed'] is True, 'fresh closed worker ownership required before prediction seals')
    output = Path(output); frozen_path = output / 'worker/frozen-selection.json'
    frozen = shared._json(frozen_path)
    require(source_identity(shared._json(output / 'source-manifest.json')) == expected_source,
            'seal source manifest content identity differs')
    require(frozen['source_identity'] == expected_source and frozen['selected_treatment'] == verification['selected_treatment'],
            'seal source/frozen selection differs')
    seals = {}; directory = output / 'prediction-seals'; directory.mkdir(exist_ok=False)
    for treatment in TREATMENTS:
        checked = verification['treatments'][treatment]
        if not checked.get('verified'):
            continue
        root = output / 'worker/public' / treatment; report = shared._json(root / 'report.json')
        files = {}
        for path in sorted(root.iterdir()):
            shared._regular(path, limit=64 * 1024**2)
            files[path.relative_to(output).as_posix()] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
        require(sha(root / 'report.json') == checked['report_sha256'], 'PUBLIC changed after independent reconstruction')
        body = {'format': 'irisx/capacity-local-prediction-seal-v1', 'treatment': treatment, 'sealed_epoch': time.time(),
            'source_identity': expected_source, 'source_manifest_sha256': sha(output / 'source-manifest.json'),
            'original_started_epoch': started_epoch, 'original_session_deadline_epoch': session_deadline_epoch,
            'worker_closure_proof': closure['proof'],
            'worker_closure_sha256': hashlib.sha256(canonical(closure['proof'])).hexdigest(),
            'frozen_selection': frozen, 'frozen_selection_file_sha256': sha(frozen_path),
            'comparison_report_sha256': frozen['comparison_report_sha256'], 'checkpoint_pin': report['checkpoint_pin'],
            'verification': checked, 'files': files, 'complete': checked['complete'],
            'full_requested_tasks': 120, 'full_requested_queries': 167, 'requested_views_per_query': 2,
            'completed_views': checked['completed_views'], 'public_scoring_performed': False,
            'provider_terminal_verified': False, 'legacy_scorer_compatibility_claimed': False,
            'evaluator_boundary': 'Separate authorized answer-isolated evaluator may consume these exact pools only after '
                'verifying this new local seal and outer controller/source/runtime handoff; no evaluator is called here.'}
        body['seal_sha256'] = hashlib.sha256(canonical(body)).hexdigest()
        path = directory / (treatment + '.json'); write_new(path, body)
        seals[treatment] = {'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path),
            'seal_sha256': body['seal_sha256'], 'complete': checked['complete']}
    return seals


def run_owned(argv, *, source_root, output, deadline, env=None):
    """Generic narrow owned-tree runner; no workload substitution or retry."""
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    require(time.time() < deadline and math.isfinite(deadline), 'unconsumed owned worker deadline required')
    started = time.monotonic()
    with (output / 'worker.log').open('xb') as log:
        guard = OwnedProcessGuard.spawn(argv, evidence_dir=output / 'ownership', cwd=source_root,
            env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        try:
            while guard.poll() is None and time.time() < deadline:
                time.sleep(min(0.25, max(0.001, deadline - time.time())))
            proof = guard.stop(timeout=15) if guard.poll() is None else guard.closed_proof()
        except BaseException:
            guard.stop(timeout=15); raise
    verify_closed_proof(proof)
    return {'closed': True, 'proof': proof, 'wall_seconds': time.monotonic() - started,
        'normal_exit': proof['worker_returncode'] == 0 and proof['returncode'] == 0 and not proof['forced']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('model-root', 'training-root', 'training-manifest', 'public-challenges', 'output'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--started-epoch', type=float, required=True)
    parser.add_argument('--session-deadline-epoch', type=float, required=True)
    parser.add_argument('--deadline-epoch', type=float, required=True)
    parser.add_argument('--comparison-deadline-epoch', type=float)
    parser.add_argument('--public-diagnostics', action='store_true')
    parser.add_argument('--execute-official', action='store_true')
    args = parser.parse_args(argv)
    require(args.execute_official, 'explicit --execute-official required; imports never launch models')
    now = time.time()
    require(all(math.isfinite(v) for v in (args.started_epoch, args.session_deadline_epoch, args.deadline_epoch))
            and 0 < args.started_epoch <= now < args.deadline_epoch <= args.session_deadline_epoch
            and args.session_deadline_epoch == args.started_epoch + 43200,
            'original finite twelve-hour session identity and unconsumed bounded deadline required')
    source = Path(__file__).resolve().parents[2]; output = args.output.absolute()
    require(not output.exists(), 'new local output identity required')
    require(not any(p.is_symlink() for p in (output, *output.parents)), 'output symlink forbidden')
    worker_deadline = args.deadline_epoch - 60
    comparison_deadline = args.comparison_deadline_epoch or min(worker_deadline, now + 7200)
    require(now < comparison_deadline <= min(worker_deadline, now + 7200), 'comparison must fit original worker deadline and7200s bound')
    require(not args.public_diagnostics or worker_deadline - comparison_deadline >= 600,
            'optional PUBLIC needs a predeclared at-least600s separate reserve')
    output.mkdir(parents=True)
    snapshot = source_snapshot(source); identity = source_identity(snapshot)
    write_new(output / 'source-manifest.json', snapshot)
    command = [sys.executable, '-B', '-m', 'tools.nvarc_capacity_20261018.worker',
        '--model-root', str(args.model_root.absolute()), '--training-root', str(args.training_root.absolute()),
        '--training-manifest', str(args.training_manifest.absolute()), '--public-challenges', str(args.public_challenges.absolute()),
        '--output', str(output / 'worker'), '--source-root', str(source),
        '--source-manifest', str(output / 'source-manifest.json'), '--source-sha256', identity,
        '--started-epoch', str(args.started_epoch), '--session-deadline-epoch', str(args.session_deadline_epoch),
        '--deadline-epoch', str(worker_deadline), '--comparison-deadline-epoch', str(comparison_deadline), '--execute-official']
    if args.public_diagnostics: command.append('--public-diagnostics')
    env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
        'HF_HUB_DISABLE_TELEMETRY': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    closure = run_owned(command, source_root=source, output=output, deadline=args.deadline_epoch - 30, env=env)
    verify_source(source, snapshot, identity)
    validated = None
    if (output / 'worker/comparison/report.json').is_file():
        validated = validate_comparison(output / 'worker/comparison', expected_source=identity,
            training_root=args.training_root, training_manifest=args.training_manifest)
    public_verified = None
    if args.public_diagnostics and (output / 'worker/public-bundle.json').is_file():
        require(validated is not None and validated['complete'], 'PUBLIC requires verified complete development comparison')
        public_verified = validate_public_bundle(output / 'worker', comparison=validated,
            solver_payload=shared._json(args.public_challenges))
    inventory = {}; total = 0
    for path in sorted((output / 'worker').rglob('*')):
        if path.is_dir(): continue
        shared._regular(path, limit=MAX_ARTIFACT_BYTES); total += path.stat().st_size
        require(total <= MAX_ARTIFACT_BYTES, 'bounded2GiB output evidence exceeded')
        inventory[path.relative_to(output).as_posix()] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    verify_closed_proof(closure['proof'])
    verify_source(source, snapshot, identity)
    seals = {} if public_verified is None else seal_public_predictions(output,
        verification=public_verified, closure=closure, expected_source=identity,
        started_epoch=args.started_epoch, session_deadline_epoch=args.session_deadline_epoch)
    complete = (closure['normal_exit'] and bool(validated and validated['complete']) and time.time() < args.deadline_epoch
        and (not args.public_diagnostics or bool(public_verified and public_verified['complete'])))
    result = {'format': 'irisx/nvarc-capacity-local-closure-v1', 'complete': complete,
        'source_identity': identity, 'closure': closure, 'comparison_verification': validated,
        'comparison_complete': bool(validated and validated['complete']),
        'prediction_seals': seals, 'public_verification': public_verified, 'public_diagnostics_complete': None if public_verified is None else public_verified['complete'],
        'selected_treatment': validated['selected_treatment'] if validated and validated['complete'] else 'initial_anchor',
        'artifacts': inventory, 'total_artifact_bytes': total, 'public_diagnostics_requested': args.public_diagnostics,
        'public_scoring_performed': False, 'provider_execution_claimed': False,
        'runtime_boundary': 'Local owned worker and immutable artifacts only; no provider capsule or scorer dispatch.'}
    write_new(output / 'closed-result.json', result)
    print(json.dumps({k: result[k] for k in ('complete', 'selected_treatment', 'public_scoring_performed')}, sort_keys=True))
    return 0 if complete else 2


if __name__ == '__main__':
    raise SystemExit(main())
