"""Owned learning/solver process. No evaluator root or public answers are accepted."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time

if __package__ in (None, ''):
    ROOT = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(ROOT), str(ROOT / 'src')]

from tools.arc_learning_agent_20261011.budget import (
    SessionClock, WorkLedger, atomic_json, digest, BudgetExceeded, calibrated_steps)
from tools.arc_learning_agent_20261011.evaluation import check_source
from tools.arc_learning_agent_20261011.result_projection import write_owner_result
from tools.arc_public_research_20261010.public_data import load_solver_tasks, read_regular

ROOT = Path(__file__).resolve().parents[2]


def _snapshot_receipt(snapshot):
    return {k: v for k, v in snapshot.items() if k != 'snapshot_id'}


def _rank_ids(ids, seed):
    return sorted(ids, key=lambda k: (digest(['declared-task-order', seed, k]), k))


def _choose_global(tasks, manifest, model, trainer, snapshots, *, deadline, output, config):
    """Choose between completed global phases using only fixed training-dev targets."""
    from tools.arc_learning_agent_20261011.grid_codec import grid_messages, encode_grid
    ids = _rank_ids([k for k in tasks if manifest['tasks'][k]['split'] == 'dev' and
                    len(tasks[k]['train']) >= 3], config.get('seed', 0))[:config.get('dev_tasks', 4)]
    rows = []
    for name, snapshot in snapshots.items():
        trainer.restore(snapshot)
        for task_id in ids:
            if time.monotonic() >= deadline: break
            demos = tasks[task_id]['train']
            score = model.score_completion(grid_messages(demos[:-1], demos[-1]['input']),
                encode_grid(demos[-1]['output']), deadline=deadline)
            rows.append({'checkpoint': name, 'task_id': task_id, 'score': score})
    matched = [k for k in ids if all(any(r['checkpoint'] == n and r['task_id'] == k and
               r['score'].get('valid') for r in rows) for n in snapshots)]
    comparison_complete = bool(ids) and len(matched) == len(ids)
    means = {name: sum(next(r['score']['mean_nll'] for r in rows if r['checkpoint'] == name and
             r['task_id'] == k) for k in matched) / len(matched) for name in snapshots} if comparison_complete else {}
    selected = min(snapshots, key=lambda n: (means[n], list(snapshots).index(n))) if means else 'global_sft'
    reset = trainer.restore(snapshots[selected]); trainer.freeze_global()
    report = {'selected': selected, 'matched_dev_tasks': matched, 'predeclared_dev_tasks': ids,
              'mean_nll': means, 'rows': rows, 'public_answers_used': False, 'reset': reset,
              'comparison_complete': comparison_complete,
              'status': 'selected' if comparison_complete else 'inconclusive-default-global-sft'}
    atomic_json(output / 'global-checkpoint-selection.json', report, exclusive=True)
    return report


def _dev_select(tasks, manifest, model, trainer, *, deadline, output, config):
    """Held-out training-family task demos, never PUBLIC120 or adapted targets."""
    from tools.arc_learning_agent_20261011.grid_codec import grid_messages, encode_grid
    eligible = [k for k, t in tasks.items() if manifest['tasks'][k]['split'] == 'dev' and len(t['train']) >= 3]
    chosen = _rank_ids(eligible, config.get('seed', 0))[:config.get('dev_tasks', 4)]
    options = [0, 8, 16] if not config.get('tiny_cpu') else [0, 1]
    rows = []
    for task_id in chosen:
        task = tasks[task_id]
        visible, target = task['train'][:-1], task['train'][-1]
        for steps in options:
            if time.monotonic() >= deadline: break
            begun = False
            try:
                trainer.begin_task('dev:' + task_id); begun = True
                adaptation = None
                if steps:
                    adaptation = trainer.adapt_task('dev:' + task_id, visible, max_steps=steps, deadline=deadline)
                score = model.score_completion(grid_messages(visible, target['input']),
                    encode_grid(target['output']), deadline=deadline)
                rows.append({'task_id': task_id, 'steps': steps, 'score': score, 'adaptation': adaptation,
                             'held_out_demo_index': len(task['train']) - 1,
                             'target_used_for_adaptation': False})
            except BudgetExceeded:
                break
            finally:
                if begun and trainer._task_id is not None: trainer.end_task()
    # Compare only tasks with every predeclared option completed; no easier-subset reward.
    complete = [k for k in chosen if all(any(r['task_id'] == k and r['steps'] == n and r['score'].get('valid') and
                                           (n == 0 or (r['adaptation'] or {}).get('steps') == n)
                                           for r in rows) for n in options)]
    comparison_complete = bool(chosen) and len(complete) == len(chosen)
    means = {n: sum(next(r['score']['mean_nll'] for r in rows if r['task_id'] == k and r['steps'] == n)
                    for k in complete) / len(complete) for n in options} if comparison_complete else {}
    selected = min(options, key=lambda n: (means[n], n)) if means else 0
    receipt = {'status': 'selected' if means else 'inconclusive-default-zero', 'selected_ttt_steps': selected,
               'predeclared_options': options, 'predeclared_tasks': chosen, 'complete_matched_tasks': complete,
               'mean_nll': {str(k): v for k, v in means.items()}, 'rows': rows,
               'public_answers_used': False, 'comparison_complete': comparison_complete,
               'metric': 'same held-out training-demo completion NLL'}
    atomic_json(output / 'dev-selection.json', receipt, exclusive=True)
    return receipt


def _rollouts(tasks, manifest, model, ledger, *, deadline, output, config):
    from tools.arc_learning_agent_20261011.grid_codec import program_messages
    from tools.arc_learning_agent_20261011.program_tools import verify_program
    from tools.arc_learning_agent_20261011.data import verified_program_record
    selected = _rank_ids([k for k in tasks if manifest['tasks'][k]['split'] == 'train'],
                         config.get('seed', 0))[:config.get('rollout_tasks', 32)]
    records, rows = [], []
    for index, task_id in enumerate(selected):
        if time.monotonic() >= deadline: break
        all_demos = tasks[task_id]['train']
        if len(all_demos) < 2: continue
        task = {'train': all_demos[:-1], 'test': [{'input': all_demos[-1]['input']}]}
        failed = None
        for attempt in range(2):
            if time.monotonic() >= deadline: break
            try:
                text = model.generate(program_messages(task, feedback=None if failed is None else {
                    'source': failed['source'], 'program_sha256': failed['source_sha256'],
                    'demo_results': failed['receipt'].get('demos', []), 'errors': failed['errors'],
                    'partial_score': failed['partial_score']['exact_fraction']}), kind='program',
                    seed=index * 2 + attempt, max_new_tokens=config.get('max_new_tokens', 2048), deadline=deadline)
                row = {'task_id': task_id, 'attempt': attempt, 'generation': text}
                if not text.get('valid'):
                    rows.append(row); break
                event = 'rollout-verify-%04d-%d' % (index, attempt)
                ledger.reserve(event, {'cpu_checks': 1, 'gas': 200000})
                try:
                    proof = verify_program(text['text'], task['train'], output, event, deadline=deadline)
                    actual = proof['receipt']
                    known = actual.get('known') is True and actual.get('owned_descendants_stopped') is True
                    if known:
                        ledger.complete(event, {'cpu_checks': int(actual.get('dispatched', False)),
                                                'gas': actual.get('gas_charged', 0)})
                    else:
                        ledger.unknown(event, 'unverified program receipt'); raise RuntimeError('unknown verification')
                except BaseException:
                    if event in ledger.pending: ledger.unknown(event, 'program verification failed')
                    raise
                row['proof'] = proof; rows.append(row)
                if proof.get('all_demos_fit'):
                    heldout_event = event + '-heldout'
                    ledger.reserve(heldout_event, {'cpu_checks': 1, 'gas': 200000})
                    full_proof = verify_program(proof['source'], all_demos, output, heldout_event, deadline=deadline)
                    full_receipt = full_proof['receipt']
                    if full_receipt.get('known') is not True or full_receipt.get('owned_descendants_stopped') is not True:
                        ledger.unknown(heldout_event, 'heldout verification unknown')
                        raise RuntimeError('unknown heldout verification')
                    ledger.complete(heldout_event, {'cpu_checks': int(full_receipt.get('dispatched', False)),
                                                   'gas': full_receipt.get('gas_charged', 0)})
                    row['heldout_proof'] = full_proof
                    if full_proof.get('all_demos_fit'):
                        original_task = {'train': all_demos, 'test': task['test']}
                        record = verified_program_record(task_id, original_task, proof['source'], full_proof, manifest,
                            feedback=failed if failed is not None and any(d.get('status') == 'mismatch' for d in failed['receipt'].get('demos', [])) else None, generation_context={'visible_indices': list(range(len(all_demos)-1)),
                            'held_out_demo_index': len(all_demos)-1, 'visible_verification_proof': proof})
                        records.append(record)
                    break
                failed = proof
            except BudgetExceeded:
                break
    receipt = {'predeclared_tasks': selected, 'attempts': rows, 'verified_records': len(records),
               'public_answers_used': False, 'scope': 'train-parent execution-filtered self-trajectories'}
    atomic_json(output / 'rollout-receipt.json', receipt, exclusive=True)
    return records, receipt


def run(request):
    check_source(request['source_identity'])
    config = dict(request['config']); root = Path(request['output_root'])
    clock = SessionClock(request['clock'])
    clock.stage_marker = root / 'active-stage.json'
    started = time.monotonic()
    ledger = WorkLedger(root / 'physical-work.jsonl')
    ledger.reserve('preflight-controls', {'cpu_checks': request['controls']['checks'], 'gas': 200000 * request['controls']['checks']})
    ledger.complete('preflight-controls', {'cpu_checks': request['controls']['checks'], 'gas': request['controls']['gas']})
    solver = load_solver_tasks(request['solver_root'], request['solver_manifest_sha256'])
    protected = sorted(solver['challenges'])
    native = None; trainer = None; results = {}; stages = {}; status = 'complete'
    try:
        from tools.arc_learning_agent_20261011.data import (
            load_official_training, create_split_manifest, build_records, build_authored_curriculum,
            merge_manifests, validate_records)
        with clock.stage('data_admission') as deadline:
            if config.get('tiny_cpu'):
                fixture = json.loads(read_regular(request['training_root']))
                if set(fixture) != {'tasks', 'synthetic_test_only'} or fixture['synthetic_test_only'] is not True:
                    raise ValueError('explicit synthetic training fixture required')
                tasks = fixture['tasks']; training_source = {'synthetic_test_only': True}
            else:
                tasks, training_source = load_official_training(request['training_root'],
                    ROOT / 'research/arc-next-line/training-source-inventory.json', protected_ids=protected)
            manifest = create_split_manifest(tasks, protected_ids=protected,
                source_identity=training_source, seed=config.get('seed', 0),
                fixed_splits=training_source.get('fixed_splits'))
            records = build_records(tasks, manifest, protected_ids=protected,
                                    augmentations=1 if config.get('tiny_cpu') else 8, seed=config.get('seed', 0))
            if not config.get('tiny_cpu'):
                count = 8 * 8 * 2
                ledger.reserve('authored-controls', {'cpu_checks': count, 'gas': count * 200000})
                authored, authored_manifest, authored_report = build_authored_curriculum(
                    per_family=8, deadline=deadline, output_dir=root / 'authored-curriculum')
                raw_receipts = json.loads((root / 'authored-curriculum/receipts.json').read_bytes())
                actual_gas = sum(r[phase].get('gas_used', 0) for r in raw_receipts for phase in ('witness', 'mutation'))
                # The ceiling stays charged if the legacy receipt lacks a standard gas counter.
                ledger.complete('authored-controls', {'cpu_checks': count, 'gas': actual_gas if actual_gas else count * 200000})
                manifest = merge_manifests(manifest, authored_manifest, protected_ids=protected)
                records += authored
            admission = validate_records(records, manifest, protected)
            atomic_json(root / 'training-split.json', manifest, exclusive=True)
            atomic_json(root / 'training-admission.json', admission, exclusive=True)
            stages['data_admission'] = admission
        from tools.arc_learning_agent_20261011.native_model import NativeModel
        from tools.arc_learning_agent_20261011.training import Trainer
        from tools.arc_learning_agent_20261011.metering import MeteredModel, MeteredTrainer
        with clock.stage('bootstrap_and_load') as deadline:
            load_remaining = 1800 - request.get('parent_bootstrap_seconds', 0)
            if load_remaining <= 0: raise BudgetExceeded('combined bootstrap/load cap exhausted')
            load_hard = min(clock.events[-1]['hard_deadline_monotonic'], time.monotonic() + load_remaining)
            atomic_json(clock.stage_marker, {'stage': 'bootstrap_and_load', 'status': 'active',
                'session_id': clock.record['session_id'], 'deadline_monotonic': load_hard})
            native = NativeModel.from_config(request['model_config'])
            model = MeteredModel(native, ledger)
            train_config = {'split_manifest': manifest, 'protected_ids': protected,
                            'seed': config.get('seed', 0), 'lora_rank': 32, 'lora_alpha': 64,
                            'learning_rate': 1e-4, 'task_learning_rate': 5e-5,
                            'max_sequence_tokens': 8192, 'checkpoint_every': 128, 'checkpoint_keep': 2,
                            'objective_cycle': ['grid'] * 6 + ['program', 'repair']}
            if config.get('tiny_cpu'):
                train_config.update(tiny_cpu=True, lora_rank=2, lora_alpha=4,
                                    max_sequence_tokens=2048, gradient_checkpointing=False)
                import torch
                torch.set_num_threads(2)
            trainer_raw = Trainer(model, train_config)
            trainer = MeteredTrainer(trainer_raw, ledger, max_sequence_tokens=train_config['max_sequence_tokens'])
            stages['model_load'] = {'identity': native.identity, 'hardware': native.hardware,
                                    'initial_adapter': trainer.fingerprint()}
            initial = trainer.snapshot('pre-calibration')
        with clock.stage('calibrate') as deadline:
            sample = [r for r in records if r['split'] == 'train'][:64]
            calibration = trainer.train(sample, max_steps=1 if config.get('tiny_cpu') else 3, deadline=deadline)
            stages['calibration'] = calibration
            trainer.restore(initial)
            samples = [r['elapsed_seconds'] for r in calibration.get('updates', []) if r.get('elapsed_seconds', 0) > 0]
            if not samples: raise RuntimeError('no actual completed neural calibration update')
        with clock.stage('global_sft') as deadline:
            max_steps = 1 if config.get('tiny_cpu') else calibrated_steps(
                deadline - time.monotonic(), samples, maximum_steps=config.get('global_steps', 4096))
            stages['global_sft'] = trainer.train(records, max_steps=max_steps, deadline=deadline,
                                               checkpoint_dir=root / 'checkpoints/global-sft')
            if stages['global_sft'].get('steps', 0) <= 0: raise RuntimeError('global SFT made no update')
            global_sft = trainer.freeze_global()
            global_snapshots = {'global_sft': global_sft}
        with clock.stage('train_only_program_rollouts') as deadline:
            rollout_root = root / 'train-rollouts'; rollout_root.mkdir()
            if config.get('tiny_cpu'):
                trajectories = []; stages['rollouts'] = {'status': 'tiny-fixture-skipped', 'verified_records': 0}
            else:
                trajectories, stages['rollouts'] = _rollouts(tasks, manifest, model, ledger,
                    deadline=deadline, output=rollout_root, config=config)
        with clock.stage('verified_trajectory_sft') as deadline:
            if trajectories:
                trainer.restore(global_sft)
                # An independently verified repair/program target is never mined from public evaluation.
                stages['trajectory_sft'] = trainer.train(trajectories,
                    max_steps=calibrated_steps(deadline - time.monotonic(), samples, maximum_steps=512),
                    deadline=deadline, checkpoint_dir=root / 'checkpoints/trajectory-sft')
                global_snapshots['trajectory_sft'] = trainer.freeze_global()
            else:
                stages['trajectory_sft'] = {'status': 'skipped-no-verified-train-trajectories', 'steps': 0}
        with clock.stage('dev_and_freeze') as deadline:
            stages['global_selection'] = _choose_global(tasks, manifest, model, trainer, global_snapshots,
                deadline=deadline, output=root, config=config)
            stages['dev_selection'] = _dev_select(tasks, manifest, model, trainer,
                deadline=deadline, output=root, config=config)
            stages['global_export'] = trainer.export_adapter(root / 'trained-global-adapter')
            frozen_config = {'ttt_steps': stages['dev_selection']['selected_ttt_steps'],
                             'seed': config.get('seed', 0), 'max_new_tokens': config.get('max_new_tokens', 2048)}
            atomic_json(root / 'frozen-public-config.json', frozen_config, exclusive=True)
        from tools.arc_learning_agent_20261011.controller import solve_task
        with clock.stage('public_solve') as deadline:
            ids = _rank_ids(solver['challenges'], config.get('seed', 0))
            if config.get('tiny_cpu'): ids = ids[:config.get('fixture_tasks', 2)]
            solve_root = root / 'tasks'; solve_root.mkdir()
            for i, task_id in enumerate(ids):
                remaining = deadline - time.monotonic()
                if remaining <= 0: status = 'partial'; break
                # Time is fairly reserved across all remaining tasks, not exhausted by early search.
                task_deadline = min(deadline, time.monotonic() + remaining / (len(ids) - i))
                result = solve_task(task_id, solver['challenges'][task_id], model=model, trainer=trainer,
                    config=frozen_config, deadline=task_deadline, output_dir=solve_root / task_id,
                    work_ledger=ledger)
                results[task_id] = result
                atomic_json(root / 'progress.json', {'completed_tasks': len(results), 'scheduled_tasks': len(ids),
                    'physical_usage': ledger.summary(), 'remaining_seconds': clock.remaining()})
                if result['status'] == 'reset_failed' or ledger.pending:
                    raise RuntimeError('task lifecycle unknown; stop all new work')
    except BudgetExceeded as exc:
        status = 'partial'; stages['stop_reason'] = str(exc)
    finally:
        if trainer is not None and trainer._task_id is not None:
            trainer.end_task()
        if native is not None: native.close()
    check_source(request['source_identity'])
    result = {'format': 'irisx/learning-owner-result-v1', 'run_id': request['run_id'], 'status': status,
              'source_identity_sha256': digest(request['source_identity']), 'request_sha256': digest(request),
              'solver_manifest_sha256': request['solver_manifest_sha256'],
              'prediction_origin': ('model_disabled' if native is None else ('synthetic_cpu' if config.get('tiny_cpu') else 'trained_model_research')),
              'production_model': native is not None and not config.get('tiny_cpu', False), 'model_stopped': True,
              'results': results, 'stages': stages, 'stage_clock': clock.events,
              'training_steps': trainer.completed_optimizer_steps if trainer is not None else 0,
              'charged_training_microbatches': ledger.used['training_steps'], 'physical_usage': ledger.summary(),
              'pending_work': ledger.pending, 'elapsed_seconds': time.monotonic() - started}
    return write_owner_result(result, request=request, challenges=solver['challenges'])


if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit(2)
    raw = read_regular(sys.argv[1], sys.argv[2])
    try: run(json.loads(raw))
    except Exception as exc:
        # Source/task diagnostics are retained, never evaluator answers.
        sys.stderr.write(type(exc).__name__ + ': ' + str(exc)[:1000] + '\n')
        raise SystemExit(2)
