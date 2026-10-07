"""Exact full-mounted-input Stage 4 private rehearsal; no provider/scoring IO.

Common preparation precedes resource admission. Every actual test stays in the
plan and export denominator. Host clocks do not attest physical GPU timing.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
from pathlib import Path
import resource
import re
import shutil
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.arc_kaggle_submission import load_json, parse_json, validate_submission
from tools.nvarc_native_multitask import canonical, digest, public_training_material, require, validate_challenges, write
from tools.nvarc_official_adapter import allocate, coverage_summary, receipt_for
from tools.nvarc_official_parent import publish_working_output, recover_working_output
from tools.nvarc_output_lifecycle import GenerationStore, atomic_bytes, cleanup_workers, diagnostic, outcomes, terminal_attempt
from tools.nvarc_public_eval_parent import stop_process
from tools.nvarc_source_verification import prepare_verified
from tools.nvarc_resource_observer import ResourceObserver, run_observed


def require_working_disk(root, minimum_bytes):
    free = shutil.disk_usage(root).free
    require(free >= minimum_bytes, 'declared working disk reserve unavailable at current boundary')
    return {'free_bytes': free, 'minimum_bytes': minimum_bytes, 'observed_monotonic': time.monotonic()}


def worker_cuda_observations(root, task_order):
    observed = {}
    for key in task_order:
        path = Path(root)/'tasks'/key/'native/result.json'
        if not path.is_file(): observed[key] = {'status': 'unavailable', 'observation': None}; continue
        try: value = parse_json(path.read_bytes()).get('cuda_memory_observation')
        except BaseException as error:
            observed[key] = {'status': 'unavailable', 'observation': None,
                'error_type': type(error).__name__, 'message': str(error)[:500]}
            continue
        observed[key] = {'status': 'unavailable' if value is None else 'retained worker observation', 'observation': value}
    return {'per_task_process': observed, 'concurrent_gpu_peak_bytes': None,
        'concurrent_gpu_peak_status': 'unavailable; per-process highwaters are not a simultaneous allocation peak',
        'gpu_calls_added': 0, 'device_synchronizations_added': 0}


def resource_admission(candidate, specs, started, *, now=time.monotonic):
    """Called after ALL common preparation and again before first dispatch."""
    observed = now()
    elapsed = observed-started
    require(math.isfinite(elapsed) and 0 <= elapsed <= candidate['initial_preparation_seconds'],
            'common preparation exceeds declared finite allowance')
    available = (candidate['maximum_notebook_wall_seconds']-elapsed-
                 candidate['packaging_reserve_seconds']-candidate['scheduler_reserve_seconds'])
    allocation = allocate(specs, available)
    allocation['observation'] = {'boundary': 'after common material/dependency preparation',
        'elapsed_seconds': elapsed, 'observed_monotonic': observed,
        'finalization_reserve_seconds': candidate['packaging_reserve_seconds'],
        'scheduler_reserve_seconds': candidate['scheduler_reserve_seconds'],
        'gpu_timing_attestation': False}
    return allocation


def full_input_plan(candidate, challenges, materials, started, *, now=time.monotonic):
    counts = validate_challenges(parse_json(canonical(challenges)))
    require(set(materials) == set(counts), 'every actual task material required')
    specs = {}
    for key, count in counts.items():
        rows = materials[key]['rows']
        require(len(rows) == 128, 'complete fixed 128-row native epoch required')
        tokens = sum(row['input_tokens'] for row in rows)
        training = math.ceil(100+tokens/800)
        specs[key] = {'test_count': count, 'training_forwards': 128, 'optimizer_steps': 128,
            'training_input_tokens': tokens, 'training_supervised_tokens': sum(r['supervised_tokens'] for r in rows),
            'maximum_sequence_tokens': max(r['input_tokens'] for r in rows),
            'expected_rows_digest': digest(rows), 'texts_digest': digest(materials[key]['texts']),
            'source_learning_rates': candidate['native_source_learning_rates'],
            'inference_forward_limits': {'control': 7, 'generation': 4096*count, 'verification': 128*count},
            'maximum_inference_input_tokens': 5*1024**2*count, 'maximum_candidate_sequences_per_test': 64,
            'per_test_limits': {'generation': 4096, 'verification': 128, 'input_tokens': 5*1024**2},
            'verification_schedule': candidate['verification_schedule'],
            'training_seconds': training, 'inference_seconds': 30*count, 'per_test_seconds': 30,
            'inference_reserve_seconds': 30*count, 'reset_reserve_seconds': 60, 'preparation_seconds': 120,
            'task_seconds': training+30*count, 'child_seconds': 120+training+30*count+60}
    plan = dict(candidate)
    plan.update(format='irisx/nvarc-native-multitask-v1', challenges_digest=digest(challenges),
        task_order=list(counts), task_specs=specs, allocation=resource_admission(candidate, specs, started, now=now),
        worker_attempts=[{'attempt_id': key, 'task_id': key, 'mode': 'solve'} for key in counts],
        runtime_input={'tasks': len(counts), 'tests': sum(counts.values()),
            'selection': 'all actual mounted test challenges; no preview/task-count binding', 'test_answers_opened': False},
        maximum_training_forwards=128*len(counts), maximum_optimizer_steps=128*len(counts),
        maximum_training_microsteps=128*len(counts), maximum_generations=4*sum(counts.values()),
        maximum_training_tokens=sum(s['training_input_tokens'] for s in specs.values()),
        maximum_supervised_tokens=sum(s['training_supervised_tokens'] for s in specs.values()),
        maximum_outer_forwards=135*len(counts)+4224*sum(counts.values()))
    return plan


def prepare_plan(candidate, challenges, material_prepare, dependency_prepare, started, *, now=time.monotonic):
    """Injectable fake-clock boundary: neither preparation callback can dispatch."""
    validate_challenges(challenges)  # reject test truth before any preparation
    prepared = dependency_prepare()
    materials = material_prepare()
    plan = full_input_plan(candidate, challenges, materials, started, now=now)
    return plan, materials, prepared


def run_full_input(root, plan, challenges, materials, model, dependency, hardware, started,
                   *, launch=subprocess.Popen, now=time.monotonic, epoch=time.time, pause=time.sleep):
    from tools.nvarc_allocation_transport import CallerAdmissions
    root = Path(root)
    # No earlier numeric remainder is trusted for actual dispatch. Freeze the
    # fresh observation in plan.json before caller binding or worker creation.
    disk = require_working_disk(root, plan['minimum_free_working_bytes'])
    plan['allocation'] = resource_admission(plan, plan['task_specs'], started, now=now)
    plan['allocation']['post_preparation_predispatch_disk'] = disk
    write(root/'plan.json', plan)
    write(root/'parent-verification.json', {'plan_digest': digest(plan), 'source_inventory_verified': True,
        'four_distinct_bf16_l4s': True, 'model_material_digest': plan['model_material_digest'],
        'post_preparation_allocation_digest': digest(plan['allocation'])})
    receipts = [receipt_for(key) for key in plan['task_order']]
    by_task = {row['task_id']: row for row in receipts}
    write(root/'worker-receipts.json', receipts)
    caller = CallerAdmissions(root, plan, challenges, now=epoch)
    queues = [list(queue) for queue in plan['allocation']['queues']]
    states, resources, acquired_channels = {}, [], []
    deadline = started+plan['maximum_notebook_wall_seconds']-plan['packaging_reserve_seconds']-plan['scheduler_reserve_seconds']
    epoch_end = epoch()+max(0, deadline-now())
    def save(): write(root/'worker-receipts.json', receipts)
    def finalize(rank, status, code, error=None):
        state = states[rank]; receipt = by_task[state['task']]
        receipt.update(status=status, returncode=code)
        if error is not None: receipt.update(error_type=type(error).__name__, error_message=str(error)[:1000])
        if state['channel'].fileno() in caller.channels: caller.unregister(state['channel'])
        for stream in state['streams'].values(): stream.close()
        del states[rank]; save()
    try:
        while states or any(queues):
            for rank, state in list(states.items()):
                code = state['process'].poll()
                if code is None and now() >= state['deadline']:
                    stop_process(state['process']); finalize(rank, 'timeout', state['process'].poll())
                elif code is not None: finalize(rank, 'complete' if code == 0 else 'worker_crash', code)
            for task, error in caller.service():
                rank = next((rank for rank, state in states.items() if state['task'] == task), None)
                if rank is not None:
                    stop_process(states[rank]['process']); finalize(rank, 'failed', states[rank]['process'].poll(), error)
            for rank, queue in enumerate(queues):
                if rank in states or not queue: continue
                remaining = deadline-now()
                require(sum(plan['task_specs'][key]['child_seconds'] for key in queue) <= remaining,
                        'remaining whole lane no longer fits measured dispatch clock')
                key = queue.pop(0); spec = plan['task_specs'][key]
                directory = root/'tasks'/key; directory.mkdir(parents=True, exist_ok=False)
                write(directory/'texts.json', materials[key]['texts']); write(directory/'expected-rows.json', materials[key]['rows'])
                parent_channel, worker_channel = socket.socketpair()
                acquired_channels.extend((parent_channel, worker_channel))
                resource_row = {'identity': key, 'process': None, 'streams': {}}
                resources.append(resource_row)  # acquired resources survive partial launch
                common = min(epoch_end, epoch()+spec['child_seconds']-spec['reset_reserve_seconds'])
                try:
                    caller.register(parent_channel, key, common)
                    streams = resource_row['streams']
                    streams['stdout'] = (directory/'stdout.log').open('w', encoding='utf-8')
                    streams['stderr'] = (directory/'stderr.log').open('w', encoding='utf-8')
                    by_task[key].update(status='interrupted_pending', launched=True, reserved_seconds=spec['child_seconds'])
                    save()  # durable reservation before process creation
                    environment = dict(os.environ, PYTHONPATH=str(root)+os.pathsep+str(dependency),
                        CUDA_VISIBLE_DEVICES=hardware[rank]['uuid'], PYTHONHASHSEED='0', HF_HUB_OFFLINE='1',
                        TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1', UNSLOTH_DISABLE_STATISTICS='1',
                        WANDB_DISABLED='true', TOKENIZERS_PARALLELISM='false', PYTHONIOENCODING='utf-8',
                        TRITON_PTXAS_PATH='/usr/local/cuda/bin/ptxas', TRITON_CACHE_DIR=str(directory/'triton-cache'),
                        OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', IRIS_NATIVE_CHILD_DEADLINE=str(common+60),
                        IRIS_NATIVE_PARENT_PID=str(os.getpid()), IRIS_ALLOCATION_FD=str(worker_channel.fileno()))
                    command = [sys.executable, str(root/'inspection.py'), '--plan', str(root/'plan.json'),
                        '--model', str(model), '--dependency', str(dependency), '--solver', str(root/'solver.py'),
                        '--texts', str(directory/'texts.json'), '--rows', str(directory/'expected-rows.json'),
                        '--output', str(directory/'native')]
                    require(spec['child_seconds']+sum(plan['task_specs'][pending]['child_seconds'] for pending in queue) <=
                            deadline-now(), 'whole remaining lane no longer fits immediately before launch')
                    process = launch(command, cwd=directory, env=environment, stdout=streams['stdout'],
                        stderr=streams['stderr'], start_new_session=True, pass_fds=(worker_channel.fileno(),))
                    resource_row['process'] = process
                    states[rank] = dict(task=key, process=process, channel=parent_channel,
                                        streams=streams, deadline=now()+spec['child_seconds'])
                finally: worker_channel.close()
            if states: pause(.05)
    finally:
        primary = sys.exception(); secondary = []
        def attempt(action, phase):
            try: return action()
            except BaseException as error:
                secondary.append((error, diagnostic(error, phase)))
                return None
        cleanup = attempt(lambda: cleanup_workers(resources, stop_process, primary=primary), 'worker-cleanup')
        stopped = bool(cleanup and cleanup['all_producers_stopped'])
        if not stopped:
            error = RuntimeError('caller receipt freeze requires confirmed producer stop')
            secondary.append((error, diagnostic(error, 'caller-receipt-freeze')))
        for state in states.values():
            code = attempt(state['process'].poll, 'final-worker-poll')
            by_task[state['task']].update(returncode=code)
        attempt(save, 'final-worker-receipts')
        if stopped:
            receipt_hash = attempt(caller.close, 'caller-receipt-freeze')
            if receipt_hash is not None:
                attempt(lambda: write(root/'caller-receipt-binding.json', {'run_id': plan['run_id'], 'plan_digest': digest(plan),
                    'caller_admissions_sha256': receipt_hash, 'gpu_timing_attestation': False}), 'caller-receipt-binding')
        # No channel is forgotten if register, log-open or Popen failed midway.
        for channel in acquired_channels: attempt(channel.close, 'allocation-channel-close')
        if secondary:
            if primary is not None:
                primary.add_note('Stage4 secondary finalization errors: '+str([item[1] for item in secondary]))
            else:
                secondary[0][0].add_note('Stage4 secondary finalization errors: '+str([item[1] for item in secondary]))
                raise secondary[0][0]
    return receipts, receipt_hash, cleanup


def strict_export_command(root, model, receipt_hash, actual_task_order):
    """No candidate-pool condition: every actual task requires independent gates."""
    require(isinstance(actual_task_order, list) and actual_task_order and
            len(set(actual_task_order)) == len(actual_task_order), 'full actual mandatory task list required')
    command = [sys.executable, str(root/'tools/nvarc_guarded_cpu.py'), '--owner-pid', str(os.getpid()),
        '--script', str(root/'tools/nvarc_native_export.py'), '--', '--root', str(root),
        '--tokenizer', str(model/'tokenizer.json'), '--caller-admissions', str(root/'caller-admissions.json'),
        '--caller-admissions-sha256', receipt_hash]
    for key in actual_task_order: command.append('--require-task-gates='+key)
    return command


def require_mandatory_gate_context(context, task_order, model_material_digest):
    """Check fresh export's unconditional gates before working-root publication."""
    checked = context.get('mandatory_task_gates')
    require(isinstance(checked, dict) and set(checked) == set(task_order),
            'independent full-task epoch/reset/host gates required even for empty pools')
    for proof in checked.values():
        require(isinstance(proof, dict) and set(proof) == {'training', 'reset_inventory_digest', 'host_telemetry_digest'},
                'closed independent mandatory task proof required')
        training = proof['training']
        require(set(training) == {'full_task_epoch_verified', 'model_material_digest', 'preparation_digest',
            'training_ledger_digest', 'trained_inventory_digest', 'reset_verified_by_this_gate'} and
            training['full_task_epoch_verified'] is True and training['model_material_digest'] == model_material_digest and
            training['reset_verified_by_this_gate'] is False and
            all(isinstance(value, str) and re.fullmatch('sha256:[0-9a-f]{64}', value) for value in
                [proof['reset_inventory_digest'], proof['host_telemetry_digest'], training['preparation_digest'],
                 training['training_ledger_digest'], training['trained_inventory_digest']]),
            'independent epoch/source/reset/host proof binding differs')
    return checked


def require_complete_rehearsal(coverage, receipts):
    """Separate deployment completion gate, including empty candidate pools."""
    require(all(row['launched'] and row['status'] == 'complete' and row['returncode'] == 0 for row in receipts) and
        coverage['tasks_launched'] == coverage['task_count'] and coverage['full_epochs'] == coverage['task_count'] and
        coverage['tests_started'] == coverage['test_count'] and coverage['all_resets_verified'] is True,
        'private full-input rehearsal incomplete; valid committed output does not establish completion')


def working_valid(store):
    if store is None: return False
    try: store.verify_projection(); return True
    except BaseException: return False


def finalize_resource_observations(observer, root, plan, gpu_observations, export_observation,
                                   disk_observations, started, primary, *, save=write):
    """All diagnostic finalizers run; secondary faults preserve the primary."""
    secondary = []
    def failed(error, phase):
        nonlocal primary
        detail = diagnostic(error, phase)
        if primary is None: primary = error
        else: secondary.append(detail)
    if gpu_observations is None and plan is not None:
        try: gpu_observations = worker_cuda_observations(root, plan['task_order'])
        except BaseException as error:
            failed(error, 'final-worker-resource-observation')
    measurements = {'format': 'irisx/stage4-resource-observations-v1', 'resource_qualification': False,
                    'resource_observation_status': 'unavailable'}
    if observer is not None:
        try:
            closed = observer.close()
            require(isinstance(closed, dict), 'structured resource observation receipt required')
            measurements = closed
        except BaseException as error: failed(error, 'resource-observer-close')
    measurements.update(fresh_cpu_export=export_observation, worker_cuda_memory_observations=gpu_observations,
        disk_admission_observations=disk_observations, notebook_wall_seconds=time.monotonic()-started,
        resource_finalization_secondary_errors=secondary)
    try: save(Path(root)/'resource-observations.json', measurements)
    except BaseException as error: failed(error, 'resource-receipt-write')
    if primary is not None and secondary:
        primary.add_note('secondary resource finalization diagnostics: '+str(secondary))
        primary.resource_observation_secondary_errors = secondary
    return measurements, primary


def finalize_terminal(root, run_id, store, qualified, primary, *, save=atomic_bytes):
    """A failed terminal write never upgrades a valid generation to exit success."""
    readback_started = time.monotonic()
    valid = working_valid(store)
    readback_elapsed = time.monotonic()-readback_started
    if not valid and primary is None:
        primary = RuntimeError('working generation projection failed final verification')
    terminal = {'run_id': run_id, 'official_score': None, 'paid_usd': 0,
        'observed_parent_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        'rss_observation_boundary': 'after working publication and final projection verification',
        'final_projection_verification_wall_seconds': readback_elapsed,
        **outcomes(valid, 'failure' if primary else 'success', qualified)}
    if primary is not None:
        terminal['primary_error'] = diagnostic(primary, 'stage4-private-rehearsal')
        if hasattr(primary, 'resource_observation_secondary_errors'):
            terminal['secondary_errors'] = primary.resource_observation_secondary_errors
    try:
        save(Path(root)/'terminal.json', canonical(terminal))
        save(Path(root).parent/'terminal.json', canonical(terminal))
    except BaseException as error:
        terminal['notebook_exit'] = 'failure'
        if primary is None: primary = error; terminal['primary_error'] = diagnostic(error, 'terminal-publication')
        else: terminal.setdefault('secondary_errors', []).append(diagnostic(error, 'terminal-publication'))
        terminal_attempt(terminal, lambda: save(Path(root)/'terminal.json', canonical(terminal)))
    return terminal, primary


def execute(root, dependency, started):
    from tools.stage_nvarc_stage4_candidate import verify_runtime_tree
    from tools.nvarc_native_solve_runtime import load_sources
    from tools.nvarc_native_submission import read_task_evidence
    from tools.nvarc_native_export import native_bindings
    from tools.nvarc_allocation_transport import load_caller_receipt
    root = Path(root); candidate = verify_runtime_tree(root, require_approved=True)
    primary, published, qualified = None, None, False
    observer = None; export_observation = None; gpu_observations = None; plan = None
    disk_observations = {}
    try:
        observer = ResourceObserver(root.parent)
        observer.start()
        require(os.environ.get('PYTHONHASHSEED') == '0' and sys.flags.hash_randomization == 0,
                'fresh seed-zero parent interpreter required')
        disk_observations['before_common_preparation'] = require_working_disk(root, candidate['minimum_free_working_bytes'])
        challenge_path = Path('/kaggle/input/competitions/arc-prize-2026-arc-agi-2/arc-agi_test_challenges.json')
        challenges = parse_json(canonical(load_json(challenge_path))); validate_challenges(challenges)
        write(root/'challenges.json', challenges)
        write(root/'input-provenance.json', {'path': str(challenge_path),
            'sha256': hashlib.sha256(challenge_path.read_bytes()).hexdigest(),
            'opened_files': [challenge_path.name], 'test_answers_opened': False})
        def material_prepare():
            # Import only after the exact dependency mount has been verified and
            # prep/uninstall has completed. Current provider versions must pass.
            import numpy as np
            import tokenizers
            require(np.__version__ == candidate['versions']['numpy'] and
                    tokenizers.__version__ == candidate['versions']['tokenizers'],
                    'pinned CPU material preparation versions differ')
            tok = tokenizers.Tokenizer.from_file(str(root/'verified-tokenizer.json'))
            class Tokens:
                def encode(self, text): return tok.encode(text).ids
                def decode(self, values): return tok.decode(values, skip_special_tokens=False)
            loader, _, _ = load_sources(root, SimpleNamespace(no_grad=lambda: lambda f: f), np)
            return {key: public_training_material(loader, Tokens(), key, task) for key, task in challenges.items()}
        with observer.phase('common_preparation'):
            plan, materials, prepared = prepare_plan(candidate, challenges, material_prepare,
                lambda: prepare_verified(root, candidate, dependency), started)
        disk_observations['after_common_preparation'] = require_working_disk(root, candidate['minimum_free_working_bytes'])
        model, hardware = prepared
        with observer.phase('native_worker_dispatch_and_completion'):
            receipts, receipt_hash, cleanup = run_full_input(root, plan, challenges, materials, model, dependency, hardware, started)
        gpu_observations = worker_cuda_observations(root, plan['task_order'])
        disk_observations['before_fresh_cpu_export'] = require_working_disk(root, candidate['minimum_free_working_bytes'])
        remaining = candidate['maximum_notebook_wall_seconds']-(time.monotonic()-started)
        require(remaining > 0, 'finalization clock exhausted')
        environment = dict(os.environ, PYTHONHASHSEED='0', CUDA_VISIBLE_DEVICES='',
            PYTHONPATH=str(root)+os.pathsep+str(dependency), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
            HF_DATASETS_OFFLINE='1', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
        with observer.phase('fresh_strict_cpu_export'), (root/'export.stdout.log').open('w') as stdout, (root/'export.stderr.log').open('w') as stderr:
            export_observation = run_observed(strict_export_command(root, model, receipt_hash, plan['task_order']),
                cwd=root, env=environment, stdout=stdout, stderr=stderr,
                timeout=min(candidate['maximum_export_process_seconds'], remaining))
        require(export_observation['returncode'] == 0 and export_observation['confirmed_stopped'] and
                not export_observation['timed_out'], 'fresh strict exporter failed or exceeded bounded clock')
        with observer.phase('native_readback_and_projection_verification'):
            allocations = load_caller_receipt(root/'caller-admissions.json', receipt_hash, plan, challenges)
            evidence = read_task_evidence(root, plan, challenges, receipts)
            native = GenerationStore(root, 'native', native_bindings(root, plan, challenges, evidence, test_allocations=allocations))
            manifest, bodies = native.read(); native.verify_projection()
        require(manifest['outcomes']['evidence_qualified'] is True, 'strict native generation required')
        mandatory = require_mandatory_gate_context(parse_json(bodies['export-process.json']),
            plan['task_order'], plan['model_material_digest'])
        qualified = True
        summary = {'run_id': plan['run_id'], 'candidate_digest': digest(candidate), 'runtime_plan_digest': digest(plan),
            'output_counts': validate_submission(challenges, parse_json(bodies['submission.json'])),
            'coverage': coverage_summary(root, plan, receipts), 'strict_same_runtime_export_completed': True,
            'submission_sha256': hashlib.sha256(bodies['submission.json']).hexdigest(),
            'audit_sha256': hashlib.sha256(bodies['submission-audit.json']).hexdigest(),
            'caller_admissions_sha256': receipt_hash, 'mandatory_task_gates': mandatory, 'resource_admission': plan['allocation'], 'cleanup': cleanup,
            'observed_parent_peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            'rss_observation_boundary': 'before working generation publication; terminal includes later peak',
            'worker_cuda_memory_observations': gpu_observations, 'fresh_cpu_export_resources': export_observation,
            'resource_observations_before_working_publication': observer.report(),
            'correctness_scored': False, 'official_score': None, 'strict_portable_gpu_gate': False,
            'paid_usd': 0, 'teacher_calls': 0, 'promotion': False}
        # Set the expected store BEFORE publication to inspect post-commit faults.
        published = GenerationStore(root.parent, 'official', {**manifest['bindings'], 'native_manifest_digest': digest(manifest)})
        with observer.phase('working_generation_publication_and_projection'):
            publish_working_output(native, root.parent, challenges, summary)
        with observer.phase('working_projection_final_readback'):
            published.verify_projection()
        require_complete_rehearsal(summary['coverage'], receipts)
        require(time.monotonic()-started <= candidate['maximum_notebook_wall_seconds'],
                'working output finalization exceeded whole notebook clock')
    except BaseException as error: primary = error
    measurements, primary = finalize_resource_observations(observer, root, plan, gpu_observations,
        export_observation, disk_observations, started, primary)
    terminal, primary = finalize_terminal(root, candidate['run_id'], published, qualified, primary)
    if primary is not None:
        primary.add_note('Stage4 terminal diagnostics: '+str(terminal)); raise primary
    return terminal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True); parser.add_argument('--dependency', type=Path, required=True)
    parser.add_argument('--started', type=float, required=True); parser.add_argument('--owner-pid', type=int, required=True)
    args = parser.parse_args()
    from tools.nvarc_public_eval import install_owner_guard
    import signal
    install_owner_guard(args.owner_pid, signal.SIGKILL)
    print(canonical(execute(args.root, args.dependency, args.started)).decode(), flush=True)


if __name__ == '__main__': main()
