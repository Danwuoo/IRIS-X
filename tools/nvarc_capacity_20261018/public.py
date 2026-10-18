"""Answer-free, post-selection PUBLIC developmental capacity diagnostics.

All three capacity arms use the same predeclared two-view/no-TTT recipe. Views
are scheduled round-robin over the entire 167-query inventory, never assigned
legacy per-task time slices. This module never opens evaluator material. Its
prediction artifacts are NOT a prediction seal, provider receipt or score.
The external controller must first prove owned-process closure and immutably
seal these artifacts; the unchanged protected scorer remains a separate step.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

from tools.arc2_goal_sprint_20261017.data import (
    canonical, digest, inference_views, transform, valid_grid, view_inputs,
)
from tools.arc2_goal_sprint_20261017.launch import require, regular, sha, write_new
from tools.nvarc_posttrain_20261017.codec import encode_example, parse_completion
from tools.nvarc_posttrain_20261017.precision_contract import FP32_BACKBONE_POLICY
from tools.nvarc_posttrain_20261017.score import validate_pool_inventory
from tools.nvarc_posttrain_20261017.probability_trace import validate_trace, validate_rows

TREATMENTS = ('baseline', 'depth32', 'moe4_top2')
COUNTERS = ('forward_calls', 'sampled_tokens', 'optimizer_steps', 'optimizer_attempts',
            'generation_forward_attempts', 'generation_input_tokens', 'generation_row_token_slots',
            'generation_finished_row_token_slots', 'generation_padding_tokens')

PROTOCOL = 'compact-capacity-public-two-view-round-robin-v1'
FORMAT = 'irisx/nvarc-capacity-public-diagnostic-v1'
RANKING = 'votes-descending-mean-own-view-nll-tie-v1'
TASKS, QUERIES, VIEWS = 120, 167, 2
DEFAULT_CONFIG = {'context_tokens': 8192, 'generation_tokens': 931,
                  'evaluation_seed': 20261018, 'views': 2, 'ttt_steps': 0}
FROZEN_KEYS = {'comparison_complete', 'comparison_report_sha256', 'protocol_sha256',
               'source_identity', 'selected_treatment', 'selection_frozen_before_public', 'public_config'}
MAX_ARTIFACT_BYTES = 64 * 1024**2


def atomic_json(path, value):
    # Same canonical/fsync/replace convention as the solver, without torch imports.
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('wb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)


def _is_sha(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None


def _sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate_solver_payload(public):
    """Reject answers/extra metadata, and retain every declared test query."""
    require(type(public) is dict and len(public) == TASKS, 'exact120-task solver inventory required')
    count = 0
    for task_id, task in public.items():
        require(type(task_id) is str and bool(re.fullmatch(r'[A-Za-z0-9_-]{1,128}', task_id)),
                'bounded explicit task ID required')
        require(type(task) is dict and set(task) == {'train', 'test'},
                'exact train/test solver fields required; evaluator metadata forbidden')
        require(type(task['train']) is list and bool(task['train'])
                and all(type(pair) is dict and set(pair) == {'input', 'output'}
                        and valid_grid(pair['input']) and valid_grid(pair['output']) for pair in task['train']),
                'strict demonstration input/output grids required')
        require(type(task['test']) is list and bool(task['test'])
                and all(type(query) is dict and set(query) == {'input'}
                        and valid_grid(query['input']) for query in task['test']),
                'PUBLIC test fields must be input-only; answers forbidden')
        count += len(task['test'])
    require(count == QUERIES, 'exact167-query solver inventory required')
    require(len(canonical(public)) <= MAX_ARTIFACT_BYTES, 'bounded answer-free solver payload required')
    return {'tasks': TASKS, 'queries': QUERIES, 'solver_payload_digest': digest(public)}


def validate_config(config=None, *, fixture=False):
    cfg = copy.deepcopy(DEFAULT_CONFIG if config is None else config)
    require(type(cfg) is dict and set(cfg) == set(DEFAULT_CONFIG), 'exact PUBLIC config schema required')
    require(type(cfg['views']) is int and cfg['views'] == VIEWS
            and type(cfg['ttt_steps']) is int and cfg['ttt_steps'] == 0,
            'predeclared two-view no-TTT PUBLIC recipe required')
    require(type(cfg['evaluation_seed']) is int and cfg['evaluation_seed'] == DEFAULT_CONFIG['evaluation_seed'],
            'shared fixed PUBLIC evaluation seed required')
    require(all(type(cfg[key]) is int and 1 <= cfg[key] <= DEFAULT_CONFIG[key]
                for key in ('context_tokens', 'generation_tokens')), 'bounded PUBLIC token dimensions required')
    require(fixture or cfg == DEFAULT_CONFIG, 'official PUBLIC inference dimensions are frozen')
    return cfg


def _frozen_selection(value, cfg):
    require(type(value) is dict and set(value) == FROZEN_KEYS, 'exact frozen development-selection identity required')
    require(value['comparison_complete'] is True and value['selection_frozen_before_public'] is True,
            'complete development selection must be frozen before PUBLIC')
    require(all(_is_sha(value[key]) for key in ('comparison_report_sha256', 'protocol_sha256', 'source_identity')),
            'frozen source/protocol/development report SHA256 identities required')
    require(value['selected_treatment'] in ('initial_anchor', *TREATMENTS)
            and value['public_config'] == cfg, 'frozen selection and predeclared PUBLIC recipe differ')
    return copy.deepcopy(value)


def _checkpoint_metadata(pin, frozen, treatment):
    require(type(pin) is dict and set(pin) == {'root', 'manifest_sha256', 'state_sha256'}
            and type(pin['root']) is str and all(_is_sha(pin[key]) for key in ('manifest_sha256', 'state_sha256')),
            'exact checkpoint root/manifest/state SHA256 contract required')
    root = Path(pin['root'])
    require(not root.is_symlink() and root.is_dir()
            and {p.name for p in root.iterdir()} == {'manifest.json', 'trainable_state.safetensors'},
            'exact regular checkpoint inventory required')
    manifest_path = regular(root / 'manifest.json')
    require(manifest_path.stat().st_size <= 8 * 1024**2 and sha(manifest_path) == pin['manifest_sha256'],
            'pinned checkpoint manifest differs')
    manifest = json.loads(manifest_path.read_bytes())
    require(manifest.get('format') == 'irisx/nvarc-compact-trainable-v1'
            and manifest.get('state_sha256') == pin['state_sha256']
            and manifest.get('model_contract', {}).get('capacity_v2', {}).get('treatment') == treatment
            and manifest.get('trainable_contract', {}).get('treatment') == treatment,
            'exact capacity checkpoint format/treatment/state pin required')
    tensor_path = regular(root / 'trainable_state.safetensors')
    require(tensor_path.stat().st_size <= 2 * 1024**3, 'bounded checkpoint tensor file required')
    require(manifest['file'] == {'name': tensor_path.name, 'bytes': tensor_path.stat().st_size,
                                'sha256': sha(tensor_path)}, 'checkpoint tensor bytes differ')
    origin = manifest['origin']
    require(origin.get('phase') == 'pre_public' and origin.get('public_ttt_applied') is False
            and origin.get('public_labels_used') is False and origin.get('treatment') == treatment
            and origin.get('source_identity') == frozen['source_identity']
            and origin.get('protocol_sha256') == frozen['protocol_sha256'],
            'checkpoint must originate from the exact frozen pre-PUBLIC comparison')
    return manifest


def _checkpoint(engine, pin, frozen, treatment):
    from tools.arc2_goal_sprint_20261017.model import adapter_state, state_digest
    manifest = _checkpoint_metadata(pin, frozen, treatment)
    require(engine._checkpoint_loaded is True and manifest['state_sha256'] == pin['state_sha256']
            and state_digest(adapter_state(engine.model)) == pin['state_sha256'],
            'fresh restored checkpoint/live trainables differ')
    require(manifest['base_identity'] == engine.base_identity and manifest['model_contract'] == engine.contract
            and manifest['trainable_contract'] == engine.trainable_inventory
            and manifest['tokenizer_admission'] == engine.tokenizer_admission,
            'checkpoint model/tokenizer/trainable reconstruction contract differs')
    return copy.deepcopy(pin)


def _physical(engine):
    values = {key: getattr(engine, key) for key in COUNTERS}
    require(all(type(v) is int and v >= 0 for v in values.values()), 'nonnegative physical engine counters required')
    return values


def _delta(after, before):
    result = {key: after[key] - before[key] for key in COUNTERS}
    require(all(v >= 0 for v in result.values()), 'physical counters may not reset during PUBLIC')
    return result


def _rank(record):
    """Stable original view-index order, independent of scheduling/arrival order."""
    candidates = []
    record['views'].sort(key=lambda view: view['view'])
    for view in record['views']:
        view.pop('candidate', None)
        evidence = view['token_evidence']
        grid = parse_completion(evidence['completion_ids'])
        view['valid'] = grid is not None
        if grid is None:
            continue
        original = transform(grid, **evidence['view_spec']['transform'], inverse=True)
        found = next((i for i, candidate in enumerate(candidates) if candidate['grid'] == original), None)
        if found is None:
            found = len(candidates)
            candidates.append({'grid': original, 'votes': 0, 'nll_sum': 0., 'views': []})
        candidate = candidates[found]
        candidate['votes'] += 1
        candidate['nll_sum'] += -sum(evidence['completion_log_probs']) / len(evidence['completion_ids'])
        candidate['views'].append(view['view'])
        view['candidate'] = found
    order = sorted(range(len(candidates)), key=lambda i: (-candidates[i]['votes'],
                   candidates[i]['nll_sum'] / candidates[i]['votes'], i))
    record.update(candidates=candidates, ranked_candidate_indices=order,
                  ranked_grids=[candidates[i]['grid'] for i in order[:2]], ranking=RANKING,
                  complete=len(record['views']) == VIEWS)


def _artifact(path, output):
    path = regular(path)
    require(path.stat().st_size <= MAX_ARTIFACT_BYTES, 'bounded PUBLIC evidence file required')
    return {'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)}


def _initialize_output(*, output_dir, public, cfg, frozen, pin, treatment, deadline, inventory):
    output = Path(output_dir).absolute()
    require(not any(p.is_symlink() for p in (output, *output.parents))
            and (not output.exists() or not any(output.iterdir())),
            'new empty PUBLIC artifact destination required')
    output.mkdir(parents=True, exist_ok=True)
    specs = {key: inference_views(VIEWS, seed=cfg['evaluation_seed'], task_id=key,
                                  demo_count=len(public[key]['train'])) for key in sorted(public)}
    protocol = {'version': PROTOCOL, 'config': cfg, **inventory, 'ranking': RANKING,
        'schedule': 'view-major then sorted task ID then original test index',
        'view_specs': specs, 'retry_policy': 'none; interrupted attempts remain charged',
        'full_requested_views': QUERIES * VIEWS, 'per_task_time_slices': False,
        'public_answers_used': False, 'selection_uses_public': False}
    protocol_sha = _sha(protocol)
    run_id = 'capacity-public-' + _sha([frozen, treatment, pin['manifest_sha256'], protocol_sha])[:24]
    write_new(output / 'protocol.json', protocol)
    write_new(output / 'frozen-selection.json', frozen)
    write_new(output / 'checkpoint-pin.json', pin)
    pools = {'format': 'irisx/arc-offline-pools-v1', 'run_id': run_id,
        'method': 'capacity PUBLIC developmental diagnostic; predeclared2views/noTTT',
        'challenges_digest': inventory['solver_payload_digest'], 'records': [], 'parent_wall_seconds': None}
    full = {'format': 'irisx/private-full-candidates-v1', 'run_id': run_id, 'records': []}
    jobs = []
    for key in sorted(public):
        task = public[key]
        pool = {'task_id': key, 'task_digest': digest(task), 'timings': {}, 'tests': []}
        pools['records'].append(pool)
        for index, query in enumerate(task['test']):
            projected = {'test_index': index, 'input_digest': digest(query['input']),
                         'ranked_grids': [], 'status': 'not_executed'}
            record = {'task_id': key, 'test_index': index, 'input_digest': projected['input_digest'],
                'views': [], 'attempts': [], 'candidates': [], 'ranked_candidate_indices': [],
                'ranked_grids': [], 'ranking': RANKING, 'complete': False}
            pool['tests'].append(projected); full['records'].append(record)
            jobs.append((key, index, query['input'], projected, record))
    validate_pool_inventory(pools)
    atomic_json(output / 'pools.json', pools)
    atomic_json(output / 'full-candidate-pools.json', full)
    report = {'format': FORMAT, 'run_id': run_id, 'treatment': treatment, 'status': 'running',
        'complete': False, 'tasks': TASKS, 'queries': QUERIES, 'views_per_query': VIEWS,
        'requested_views': QUERIES * VIEWS, 'completed_views': 0, 'attempted_views': 0,
        'failed_views': 0, 'unattempted_views': QUERIES * VIEWS, 'completed_queries': 0, 'nonempty_queries': 0,
        'source_identity': frozen['source_identity'], 'protocol_sha256': protocol_sha,
        'frozen_selection_sha256': _sha(frozen), 'selected_treatment': frozen['selected_treatment'],
        'comparison_report_sha256': frozen['comparison_report_sha256'], 'checkpoint_pin': pin,
        'deadline_epoch': deadline, 'ttt_steps': 0, 'ttt_committed_updates': 0,
        'public_answers_used': False, 'selection_changed': False, 'public_scoring_performed': False,
        'owned_process_closure_verified': False, 'prediction_sealed': False,
        'inherited_exposure_qualified': True, 'capacity_gain_claimed': False,
        'clean_generalization_claimed': False, 'hidden_or_official_claimed': False,
        'private_artifacts': {}, 'error': None, 'physical': {key: 0 for key in COUNTERS},
        'limits': ['PUBLIC is developmental and inherited-exposure-qualified, not clean/hidden/official evaluation.',
            'No PUBLIC result may change the frozen selection, training recipe or inference recipe.',
            'All120tasks/167queries remain in the denominator, including failures and missing predictions.',
            'Scoring requires separate owned-process closure, immutable prediction sealing and unchanged protected scorer.',
            'This worker does not manufacture a provider terminal receipt or evaluator-isolation attestation.']}
    atomic_json(output / 'report.json', report)
    return output, specs, pools, full, jobs, report


def run_public_diagnostic(engine, *, solver_payload, frozen_selection, checkpoint_pin,
                          output_dir, treatment, deadline, config=None):
    """Execute one fresh restored arm; never load answers, adapt, retry or select.

    `deadline` is the original absolute time.time epoch, shared across PUBLIC
    arms. Reduced generation/context bounds exist only for CPU tiny fixtures.
    A failed attempt retains its raw trace and ALL physical counters, stops this
    arm, and leaves unexecuted queries in the full denominator. Completed view
    receipts are fsynced to an append-only journal before the pool is updated.
    Normal deadline exit also persists the complete raw-candidate inventory.
    """
    from .model import CapacityEngine
    from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, adapter_state, check_deadline, state_digest
    require(isinstance(engine, CapacityEngine) and treatment in TREATMENTS and engine.treatment == treatment,
            'fresh named CapacityEngine required')
    engine._checkpoint_admission()
    require(engine.probability_policy == FP32_BACKBONE_POLICY, 'capacity PUBLIC requires admitted FP32 math')
    cfg = validate_config(config, fixture=engine.contract['variant'] == 'tiny' and engine.device.type == 'cpu')
    frozen = _frozen_selection(frozen_selection, cfg)
    inventory = validate_solver_payload(solver_payload)
    public = copy.deepcopy(solver_payload)
    pin = _checkpoint(engine, checkpoint_pin, frozen, treatment)
    require(type(deadline) in (int, float) and math.isfinite(deadline), 'finite original PUBLIC deadline required')
    before = _physical(engine)
    require(not any(before.values()), 'PUBLIC requires fresh checkpoint-restored engine counters')
    output, specs, pools, full, jobs, report = _initialize_output(output_dir=output_dir, public=public,
        cfg=cfg, frozen=frozen, pin=pin, treatment=treatment, deadline=deadline, inventory=inventory)
    started = time.monotonic()
    journal_path = output / 'view-attempts.jsonl'
    try:
        with journal_path.open('xb') as journal:
            for view_index in range(VIEWS):
                for key, index, query, projected, record in jobs:
                    check_deadline(deadline)
                    work_before = _physical(engine)
                    attempt = {'task_id': key, 'test_index': index, 'view': view_index,
                               'status': 'running', 'error': None}
                    trace, encoded = {}, None
                    report['attempted_views'] += 1
                    try:
                        demos, transformed = view_inputs(public[key], query, specs[key][view_index])
                        encoded = encode_example(demos, transformed, context=cfg['context_tokens'],
                                                 generation=cfg['generation_tokens'])
                        rows = engine.generate(encoded['prompt_ids'], max_new_tokens=cfg['generation_tokens'],
                                               sample=False, deadline=deadline, trace=trace)
                        validate_trace(trace, expected_trace_sha256=trace['sha256'])
                        validate_rows(rows, trace)
                        require(type(rows) is list and len(rows) == 1, 'exact one generated view trajectory required')
                        row = rows[0]
                        require(row['prompt_length'] == len(encoded['prompt_ids'])
                                and row['input_ids'][:row['prompt_length']] == encoded['prompt_ids'],
                                'actual generated prompt differs')
                        receipt = {'view': view_index, 'valid': False, 'tokens': row['completion_tokens'],
                            'stop': row['stop'], 'demos_dropped': encoded['demos_dropped'],
                            'token_evidence': {'prompt_ids': list(row['input_ids'][:row['prompt_length']]),
                                'completion_ids': list(row['input_ids'][row['prompt_length']:]),
                                'completion_log_probs': list(row['behavior_log_probs'][row['prompt_length']:]),
                                'view_spec': copy.deepcopy(specs[key][view_index])}}
                        # Reject malformed rows before any vote can be committed.
                        provisional = copy.deepcopy(record)
                        provisional['views'].append(receipt)
                        _rank(provisional)
                        _verify_prediction(provisional, public[key], query, cfg, task_id=key, views=VIEWS)
                        record.update(provisional)
                        attempt.update(status='complete', receipt=copy.deepcopy(record['views'][-1]))
                    except Exception as exc:
                        attempt.update(status='deadline' if isinstance(exc, PhaseDeadline) else 'failed',
                                       error={'type': type(exc).__name__, 'message': str(exc)[:1024]},
                                       interrupted_trace=trace)
                        if encoded is not None:
                            attempt['encoded_prompt_ids'] = encoded['prompt_ids']
                            attempt['view_spec'] = copy.deepcopy(specs[key][view_index])
                        raise
                    finally:
                        attempt['physical'] = _delta(_physical(engine), work_before)
                        record['attempts'].append(copy.deepcopy(attempt))
                        journal.write(canonical(attempt) + b'\n'); journal.flush(); os.fsync(journal.fileno())
                        projected.update(ranked_grids=copy.deepcopy(record['ranked_grids']),
                            status='complete' if record['complete'] else 'partial' if record['views']
                            else 'failed')
                        atomic_json(output / 'pools.json', pools)
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)[:1024]}
        report['status'] = 'partial' if isinstance(exc, PhaseDeadline) else 'failed'
    finally:
        try:
            engine.sync()
        except Exception as exc:
            report.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)[:1024]})
        report['physical'] = _delta(_physical(engine), before)
        all_attempts = [a for row in full['records'] for a in row['attempts']]
        if report['physical'] != {key: sum(a['physical'][key] for a in all_attempts) for key in COUNTERS}:
            report.update(status='failed', error={'type': 'IntegrityError',
                'message': 'PUBLIC physical work is not accounted exactly once'})
        report.update(completed_views=sum(len(row['views']) for row in full['records']),
            failed_views=sum(a['status'] != 'complete' for a in all_attempts),
            unattempted_views=QUERIES * VIEWS - len(all_attempts),
            completed_queries=sum(row['complete'] for row in full['records']),
            nonempty_queries=sum(bool(row['ranked_grids']) for row in full['records']),
            wall_seconds=time.monotonic() - started)
        unchanged = state_digest(adapter_state(engine.model)) == pin['state_sha256']
        report['checkpoint_state_unchanged'] = unchanged
        report['physical_no_updates_verified'] = not report['physical']['optimizer_steps'] and not report['physical']['optimizer_attempts']
        if not unchanged or not report['physical_no_updates_verified'] or frozen_selection != frozen:
            report['status'] = 'failed'
            report['error'] = {'type': 'IntegrityError', 'message': 'PUBLIC mutated frozen selection or checkpoint state'}
        else:
            try:
                engine._checkpoint_admission()
            except Exception as exc:
                report.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)[:1024]})
        pools['parent_wall_seconds'] = report['wall_seconds']
        validate_pool_inventory(pools)
        atomic_json(output / 'pools.json', pools)
        atomic_json(output / 'full-candidate-pools.json', full)
        for name in ('protocol.json', 'frozen-selection.json', 'checkpoint-pin.json',
                     'pools.json', 'full-candidate-pools.json', 'view-attempts.jsonl'):
            report['private_artifacts'][name] = _artifact(output / name, output)
        report['complete'] = (report['completed_views'] == QUERIES * VIEWS and report['error'] is None
                              and time.time() < deadline)
        if report['complete']:
            report['status'] = 'complete'
        elif report['status'] == 'running':
            report['status'] = 'partial'
            report['error'] = {'type': 'PhaseDeadline', 'message': 'PUBLIC persistence/verification exceeded original deadline'}
        atomic_json(output / 'report.json', report)
        # A late final report write cannot claim deadline-complete inference.
        if report['complete'] and time.time() >= deadline:
            report.update(complete=False, status='partial', error={
                'type': 'PhaseDeadline', 'message': 'PUBLIC final report persistence exceeded original deadline'})
            atomic_json(output / 'report.json', report)
    return report


def verify_public_artifacts(output, *, solver_payload, frozen_selection, checkpoint_pin, treatment,
                            checkpoint_root=None):
    """Independently reconstruct an arm without targets, model execution or edits.

    Hashes establish internal byte consistency, not process ownership, trusted
    provenance or a provider signature. Call only as part of the controller's
    independently bound closure/sealing workflow, before evaluator access.
    """
    inventory = validate_solver_payload(solver_payload)
    output = Path(output).absolute()
    require(not output.is_symlink() and output.is_dir(), 'regular PUBLIC artifact directory required')
    def read(name):
        path = regular(output / name)
        require(path.stat().st_size <= MAX_ARTIFACT_BYTES, 'bounded PUBLIC evidence file required')
        return json.loads(path.read_bytes())
    report, protocol = read('report.json'), read('protocol.json')
    cfg = validate_config(protocol['config'], fixture=True)
    frozen = _frozen_selection(frozen_selection, cfg)
    require(type(report.get('complete')) is bool and report.get('status') in {'complete', 'partial', 'failed', 'not_executed'}
            and treatment in TREATMENTS and report['format'] == FORMAT and report['treatment'] == treatment,
            'exact named PUBLIC diagnostic required')
    local_pin = checkpoint_pin if checkpoint_root is None else {**checkpoint_pin, 'root': str(checkpoint_root)}
    manifest = _checkpoint_metadata(local_pin, frozen, treatment)
    validate_config(cfg, fixture=manifest['model_contract']['variant'] == 'tiny')
    expected_artifacts = {'protocol.json', 'frozen-selection.json', 'checkpoint-pin.json',
                          'pools.json', 'full-candidate-pools.json', 'view-attempts.jsonl'}
    require(set(report['private_artifacts']) == expected_artifacts, 'complete PUBLIC artifact inventory required')
    for name, artifact in report['private_artifacts'].items():
        require(artifact == _artifact(output / name, output), 'PUBLIC artifact SHA/bytes/path differ')
    require(read('frozen-selection.json') == frozen and read('checkpoint-pin.json') == checkpoint_pin
            and report['checkpoint_pin'] == checkpoint_pin and report['frozen_selection_sha256'] == _sha(frozen)
            and report['source_identity'] == frozen['source_identity']
            and report['comparison_report_sha256'] == frozen['comparison_report_sha256']
            and report['selected_treatment'] == frozen['selected_treatment'], 'frozen selection/checkpoint identity differs')
    specs = {key: inference_views(VIEWS, seed=cfg['evaluation_seed'], task_id=key,
                                  demo_count=len(solver_payload[key]['train'])) for key in sorted(solver_payload)}
    expected_protocol = {'version': PROTOCOL, 'config': cfg, **inventory, 'ranking': RANKING,
        'schedule': 'view-major then sorted task ID then original test index', 'view_specs': specs,
        'retry_policy': 'none; interrupted attempts remain charged', 'full_requested_views': QUERIES * VIEWS,
        'per_task_time_slices': False, 'public_answers_used': False, 'selection_uses_public': False}
    require(protocol == expected_protocol and report['protocol_sha256'] == _sha(expected_protocol),
            'fixed shared PUBLIC recipe/view identity differs')
    run_id = 'capacity-public-' + _sha([frozen, treatment, checkpoint_pin['manifest_sha256'], _sha(protocol)])[:24]
    pools, full = read('pools.json'), read('full-candidate-pools.json')
    validate_pool_inventory(pools)
    require(pools['run_id'] == full['run_id'] == report['run_id'] == run_id
            and pools['challenges_digest'] == inventory['solver_payload_digest']
            and full['format'] == 'irisx/private-full-candidates-v1', 'PUBLIC run/solver identity differs')
    query_ids = [(key, index) for key in sorted(solver_payload)
                 for index in range(len(solver_payload[key]['test']))]
    require([(r['task_id'], r['test_index']) for r in full['records']] == query_ids
            and [r['task_id'] for r in pools['records']] == sorted(solver_payload),
            'full sorted120/167 query inventories required')
    projected = {(r['task_id'], t['test_index']): t for r in pools['records'] for t in r['tests']}
    for record in pools['records']:
        require(record['task_digest'] == digest(solver_payload[record['task_id']]), 'public task digest differs')
    attempts = {}
    for record in full['records']:
        key, index = record['task_id'], record['test_index']
        query = solver_payload[key]['test'][index]['input']
        require(record['input_digest'] == digest(query) == projected[key, index]['input_digest']
                and record['ranking'] == RANKING, 'input digest/ranking declaration differs')
        _verify_prediction(record, solver_payload[key], query, cfg, task_id=key, views=VIEWS)
        require([a['view'] for a in record['attempts']] == list(range(len(record['attempts'])))
                and len(record['attempts']) <= VIEWS, 'unique original view attempts, no rescue retries required')
        successes = []
        for attempt in record['attempts']:
            view = attempt['view']
            require(attempt['task_id'] == key and attempt['test_index'] == index
                    and attempt['status'] in {'complete', 'deadline', 'failed'}, 'attempt identity/status differs')
            work = attempt['physical']
            require(type(work) is dict and set(work) == set(COUNTERS)
                    and all(type(v) is int and v >= 0 for v in work.values())
                    and work['optimizer_steps'] == work['optimizer_attempts'] == 0,
                    'exact physical counters and zero optimizer work required')
            if attempt['status'] == 'complete':
                require(attempt['error'] is None, 'successful view cannot carry failure')
                receipt = attempt['receipt']; evidence = receipt['token_evidence']
                count = len(evidence['completion_ids']); prompt = len(evidence['prompt_ids'])
                expected_work = {name: 0 for name in COUNTERS}
                expected_work.update(forward_calls=count, sampled_tokens=count, generation_forward_attempts=count,
                                     generation_input_tokens=prompt + count - 1, generation_row_token_slots=count)
                require(work == expected_work and receipt['view'] == view,
                        'completed actual singleton generation physical work differs')
                successes.append(receipt)
            else:
                require(type(attempt['error']) is dict, 'failed attempt must preserve error')
                trace = attempt.get('interrupted_trace', {})
                if trace:
                    trace_body = {k: v for k, v in trace.items() if k != 'sha256'}
                    require(trace['sha256'] == hashlib.sha256(canonical(trace_body) + b'\n').hexdigest()
                            and trace['batch_size'] == 1 and trace['sample'] is False
                            and trace['max_new_tokens'] == cfg['generation_tokens'],
                            'interrupted raw trace identity differs')
                    demos, query_view = view_inputs(solver_payload[key], query, specs[key][view])
                    encoded = encode_example(demos, query_view, context=cfg['context_tokens'],
                                             generation=cfg['generation_tokens'])
                    require(trace['prompts'] == [encoded['prompt_ids']]
                            and attempt['encoded_prompt_ids'] == encoded['prompt_ids']
                            and attempt['view_spec'] == specs[key][view]
                            and all(trace['work'][name] == work[name] for name in trace['work']),
                            'failed raw prompt/counters differ')
                else:
                    require(not any(work.values()), 'failed submitted model work must retain its trace')
            attempts[key, index, view] = attempt
        require(successes == record['views'], 'successful raw view receipts differ from attempts')
        status = ('complete' if record['complete'] else 'partial' if record['views'] else
                  'failed' if record['attempts'] else 'not_executed')
        require(projected[key, index]['ranked_grids'] == record['ranked_grids']
                and projected[key, index]['status'] == status, 'scorer pool projection changed')
    journal = [json.loads(line) for line in regular(output / 'view-attempts.jsonl').read_bytes().splitlines()]
    schedule = [(key, index, view) for view in range(VIEWS) for key, index in query_ids]
    require([(a['task_id'], a['test_index'], a['view']) for a in journal] == schedule[:len(journal)]
            and len(journal) == len(attempts)
            and all(attempts[a['task_id'], a['test_index'], a['view']] == a for a in journal),
            'fixed round-robin durable attempt journal differs')
    require(all(a['status'] == 'complete' for a in journal[:-1]), 'work continued after a failed view')
    physical = {name: sum(a['physical'][name] for a in journal) for name in COUNTERS}
    completed_views = sum(len(r['views']) for r in full['records'])
    require(report['tasks'] == TASKS and report['queries'] == QUERIES and report['views_per_query'] == VIEWS
            and report['requested_views'] == QUERIES * VIEWS and report['physical'] == physical
            and report['attempted_views'] == len(journal) and report['completed_views'] == completed_views
            and report['failed_views'] == sum(a['status'] != 'complete' for a in journal)
            and report['unattempted_views'] == QUERIES * VIEWS - len(journal)
            and report['completed_queries'] == sum(r['complete'] for r in full['records'])
            and report['nonempty_queries'] == sum(bool(r['ranked_grids']) for r in full['records']),
            'full-denominator PUBLIC summary or charged work differs')
    require(report['ttt_steps'] == report['ttt_committed_updates'] == 0
            and report['selection_changed'] is False and report['public_answers_used'] is False
            and report['public_scoring_performed'] is False and report['prediction_sealed'] is False
            and report['inherited_exposure_qualified'] is True
            and report['capacity_gain_claimed'] is False and report['clean_generalization_claimed'] is False
            and report['hidden_or_official_claimed'] is False, 'honest answer-free developmental boundary required')
    if report['complete']:
        require(report['status'] == 'complete' and report['error'] is None and completed_views == QUERIES * VIEWS
                and report['checkpoint_state_unchanged'] is True and report['physical_no_updates_verified'] is True,
                'complete PUBLIC recipe/unchanged state required')
    return {'verified': True, 'tasks': TASKS, 'queries': QUERIES, 'completed_views': completed_views,
            'protocol_sha256': report['protocol_sha256'], 'report_sha256': sha(regular(output / 'report.json')),
            'complete': report['complete'], 'targets_opened': False, 'owned_process_closure_verified': False,
            'prediction_sealed': False}


def _verify_prediction(result, task, query, cfg, *, task_id, views):
    """Torch-free equivalent of existing stability.verify_prediction contract."""
    specs = inference_views(views, seed=cfg['evaluation_seed'], task_id=task_id, demo_count=len(task['train']))
    require(type(result['views']) is list and len(result['views']) <= views, 'bounded successful views required')
    for index, record in enumerate(result['views']):
        require(type(record['view']) is int and record['view'] == index, 'original contiguous view index required')
        evidence = record['token_evidence']
        demos, transformed = view_inputs(task, query, specs[index])
        encoded = encode_example(demos, transformed, context=cfg['context_tokens'], generation=cfg['generation_tokens'])
        ids, logps = evidence['completion_ids'], evidence['completion_log_probs']
        require(type(ids) is list and type(logps) is list and bool(ids)
                and evidence['view_spec'] == specs[index] and evidence['prompt_ids'] == encoded['prompt_ids']
                and record['demos_dropped'] == encoded['demos_dropped']
                and record['tokens'] == len(ids) and len(ids) == len(logps)
                and all(type(token) is int and 0 <= token < 16 for token in ids)
                and 15 not in ids[:-1] and record['stop'] in {'completed', 'length'}
                and (record['stop'] == 'completed') == (ids[-1] == 15)
                and (record['stop'] != 'length' or len(ids) == cfg['generation_tokens'])
                and len(ids) <= cfg['generation_tokens']
                and all(type(v) in (int, float) and math.isfinite(v) and v <= 1e-6 for v in logps),
                'retained raw completion/prompt/log probability identity differs')
        require(type(record['valid']) is bool and record['valid'] == (parse_completion(ids) is not None),
                'parser result differs from raw completion')
    rebuilt = copy.deepcopy(result)
    _rank(rebuilt)
    require(all(result[key] == rebuilt[key] for key in ('views', 'candidates', 'ranked_candidate_indices',
                                                      'ranked_grids', 'ranking', 'complete')),
            'fixed view/ranking reconstruction differs')
    return {'verified': True, 'completed_views': len(result['views']), 'result_sha256': _sha(result)}


def write_unexecuted_public(*, solver_payload, frozen_selection, checkpoint_pin, output_dir,
                            treatment, deadline, config=None, reason='global deadline before model load'):
    """Persist full missing-work denominators without loading any model.

    Zero work means this arm did not load/infer, not that its checkpoint was
    live-restored or tested. Checkpoint file and origin bindings are still checked.
    """
    require(treatment in TREATMENTS and type(reason) is str and 1 <= len(reason) <= 1024,
            'explicit unexecuted arm and bounded reason required')
    inventory = validate_solver_payload(solver_payload)
    public = copy.deepcopy(solver_payload)
    cfg = validate_config(config, fixture=True)
    frozen = _frozen_selection(frozen_selection, cfg)
    manifest = _checkpoint_metadata(checkpoint_pin, frozen, treatment)
    validate_config(cfg, fixture=manifest['model_contract']['variant'] == 'tiny')
    require(type(deadline) in (int, float) and math.isfinite(deadline), 'finite original deadline required')
    output, specs, pools, full, jobs, report = _initialize_output(output_dir=output_dir, public=public,
        cfg=cfg, frozen=frozen, pin=copy.deepcopy(checkpoint_pin), treatment=treatment, deadline=deadline,
        inventory=inventory)
    with (output / 'view-attempts.jsonl').open('xb') as stream:
        stream.flush(); os.fsync(stream.fileno())
    report.update(status='not_executed', error={'type': 'NotExecuted', 'message': reason}, wall_seconds=0.,
                  checkpoint_state_unchanged=None, physical_no_updates_verified=True, model_loaded=False)
    pools['parent_wall_seconds'] = 0.
    atomic_json(output / 'pools.json', pools)
    for name in ('protocol.json', 'frozen-selection.json', 'checkpoint-pin.json',
                 'pools.json', 'full-candidate-pools.json', 'view-attempts.jsonl'):
        report['private_artifacts'][name] = _artifact(output / name, output)
    atomic_json(output / 'report.json', report)
    return report
