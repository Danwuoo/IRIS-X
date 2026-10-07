"""Bounded private E10 development coordinator. No provider or evaluator IO.

Fresh native task processes retain the existing full-epoch/reset/replay gates.
All arm/repeat jobs share one session cap. Admission receipts are parent-owned
and explicitly carried into a fresh CPU export. A failed calibration cannot
dispatch a comparative candidate. This is development, never official scoring.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import zipfile

from tools.arc_kaggle_submission import parse_json
from tools.nvarc_allocation_transport import CallerAdmissions
from tools.nvarc_native_multitask import canonical, digest, require, write
from tools.nvarc_output_lifecycle import cleanup_workers, diagnostic
from tools.nvarc_public_eval_parent import prepare, stop_process
from tools.nvarc_resource_attachment import verify_mount


def run_jobs(root, screen, plans, challenges, model, dependency, hardware, started,
             *, launch=subprocess.Popen, now=time.monotonic, epoch=time.time,
             pause=time.sleep, calibration_check=None):
    root = Path(root); states = {}; errors = []; finished = []
    admissions = {key: CallerAdmissions(root/key, plan, challenges, now=epoch)
                  for key, plan in plans.items()}
    receipts = {key: [{'task_id': task, 'attempt_id': task, 'status': 'not_executed',
                      'launched': False, 'returncode': None, 'reset_inferred': False}
                     for task in plan['task_order']] for key, plan in plans.items()}
    by_job = {(key, r['task_id']): r for key, rows in receipts.items() for r in rows}
    end = started+screen['maximum_notebook_wall_seconds']-screen['packaging_reserve_seconds']
    epoch_end = epoch()+max(0, end-now())
    queue = list(screen['workload_order']); calibration = set(screen['calibration_jobs'])
    completed_calibration = set(); calibrated = False
    ledger = root/'execution-ledger.jsonl'
    require(not ledger.exists(), 'fresh bounded execution ledger required')
    head = digest({'screen_digest': digest(screen)}); sequence = 0
    def event(kind, **details):
        nonlocal head, sequence
        row = {'sequence': sequence, 'previous': head, 'event': kind,
               'screen_digest': digest(screen), 'host_wall_seconds': now()-started, **details}
        row['digest'] = digest(row)
        with ledger.open('ab') as stream:
            stream.write(canonical(row)+b'\n'); stream.flush(); os.fsync(stream.fileno())
        head = row['digest']; sequence += 1
    def save_receipts(key): write(root/key/'worker-receipts.json', receipts[key])
    for key in plans: save_receipts(key)
    root.joinpath('workers').mkdir(exist_ok=False)
    def finalize(rank, status, code=None, error=None):
        state = states[rank]; key, task = state['job']['subrun'], state['job']['task_id']
        receipt = by_job[key, task]
        receipt.update(status=status, returncode=code)
        if error is not None:
            receipt.update(error_type=type(error).__name__, error_message=str(error)[:1000])
            errors.append({'subrun': key, 'task_id': task, **diagnostic(error, 'native-task')})
        if state['channel'].fileno() in admissions[key].channels:
            admissions[key].unregister(state['channel'])
        for name in ('stdout', 'stderr'):
            state[name].close()
        save_receipts(key); finished.append(state['job']['job_id'])
        event('task-terminal', job_id=state['job']['job_id'], status=status, returncode=code)
        if state['job']['job_id'] in calibration:
            require(status == 'complete', 'calibration native process failed; comparative dispatch refused')
            result = parse_json((root/key/'tasks'/task/'native/result.json').read_bytes())
            require(result['training_complete'] and result['all_saved_tensors_restored'] and
                result['post_reset_control_verified'] and result['optimizer_discarded'] and
                result.get('telemetry', {}).get('gpu_kernel_seconds', 'missing') is None,
                'calibration source/reset/host observation gate failed')
            # Strict CPU replay is a separate export gate after producer stop.
            # This runtime gate cannot stand in for native replay or quality.
            completed_calibration.add(state['job']['job_id'])
        del states[rank]
    try:
        while now() < end:
            for rank, state in list(states.items()):
                code = state['process'].poll()
                if code is not None:
                    finalize(rank, 'complete' if code == 0 else 'worker_crash', code); continue
                if now() >= state['deadline']:
                    stop_process(state['process']); finalize(rank, 'timeout', state['process'].poll()); continue
            for key, caller in admissions.items():
                for task, error in caller.service():
                    match = next((rank for rank, state in states.items()
                                  if state['job']['subrun'] == key and state['job']['task_id'] == task), None)
                    if match is not None:
                        stop_process(states[match]['process'])
                        finalize(match, 'failed', states[match]['process'].poll(), error)
            if not calibrated and completed_calibration == calibration:
                require(callable(calibration_check), 'independent calibration replay callback required')
                control = screen['calibration_subrun']
                calibration_check(control, admissions[control].publish())
                require(now()<end,'calibration replay exhausted work admission deadline')
                calibrated = True; event('calibration-observation-gate', passed=True,
                    gpu_timing_attestation=False, correctness_scored=False)
            for rank in range(screen['parallel_workers']):
                if rank in states: continue
                candidates = [job for job in queue if job['rank'] == rank and
                    (calibrated or job['job_id'] in calibration)]
                if not candidates: continue
                job = candidates[0]; key, task = job['subrun'], job['task_id']; plan = plans[key]
                spec = plan['task_specs'][task]; remaining = min(spec['child_seconds'], end-now())
                if remaining < spec['minimum_admission_seconds']: continue
                queue.remove(job); directory = root/'workers'/job['job_id']; directory.mkdir()
                output = root/key/'tasks'/task; output.mkdir(parents=True, exist_ok=False)
                material = parse_json((root/'materials'/(task+'.json')).read_bytes())
                require(digest(material) == parse_json((root/'task-material-index.json').read_bytes())[task],
                        'exact task-local material binding differs')
                write(output/'texts.json', material['texts']); write(output/'expected-rows.json', material['rows'])
                parent_channel, worker_channel = socket.socketpair()
                common_deadline = min(epoch_end, epoch()+remaining-spec['reset_reserve_seconds'])
                admissions[key].register(parent_channel, task, common_deadline)
                stdout = (directory/'stdout.log').open('w', encoding='utf-8')
                stderr = (directory/'stderr.log').open('w', encoding='utf-8')
                receipt = by_job[key, task]
                receipt.update(status='interrupted_pending', launched=True, reserved_seconds=remaining)
                save_receipts(key); event('task-launch-reserved', job_id=job['job_id'],
                    rank=rank, common_deadline_epoch=common_deadline, reserved_seconds=remaining)
                environment = dict(os.environ, PYTHONHASHSEED='0',
                    PYTHONPATH=str(root/key)+os.pathsep+str(dependency), CUDA_VISIBLE_DEVICES=hardware[rank]['uuid'],
                    HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1',
                    UNSLOTH_DISABLE_STATISTICS='1', WANDB_DISABLED='true', TOKENIZERS_PARALLELISM='false',
                    PYTHONIOENCODING='utf-8', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
                    TRITON_PTXAS_PATH='/usr/local/cuda/bin/ptxas', TRITON_CACHE_DIR=str(directory/'triton-cache'),
                    IRIS_NATIVE_CHILD_DEADLINE=str(common_deadline+spec['reset_reserve_seconds']),
                    IRIS_NATIVE_PARENT_PID=str(os.getpid()),
                    IRIS_ALLOCATION_FD=str(worker_channel.fileno()))
                command = [sys.executable, str(root/key/'inspection.py'), '--plan', str(root/key/'plan.json'),
                    '--model', str(model), '--dependency', str(dependency), '--solver', str(root/key/'solver.py'),
                    '--texts', str(output/'texts.json'), '--rows', str(output/'expected-rows.json'),
                    '--output', str(output/'native')]
                state = {'job': job, 'process': None, 'stdout': stdout, 'stderr': stderr,
                         'channel': parent_channel, 'deadline': now()+remaining}
                states[rank] = state
                try:
                    state['process'] = launch(command, cwd=directory, env=environment, stdout=stdout,
                        stderr=stderr, start_new_session=True, pass_fds=(worker_channel.fileno(),))
                finally: worker_channel.close()
            if not queue and not states: break
            if queue and not states and all(end-now() < plans[j['subrun']]['task_specs'][j['task_id']]['minimum_admission_seconds']
                                             for j in queue): break
            pause(.05)
    finally:
        cleanup = cleanup_workers([{'identity': state['job']['job_id'], 'process': state['process'],
            'streams': {name: state[name] for name in ('stdout', 'stderr')}} for state in states.values()],
            stop_process, primary=sys.exception())
        require(cleanup['all_producers_stopped'], 'caller receipt freeze requires confirmed producer stop')
        for state in states.values():
            key, task = state['job']['subrun'], state['job']['task_id']
            by_job[key, task].update(status='timeout' if now() >= end else 'interrupted_pending',
                                   returncode=state['process'].poll() if state['process'] else None)
        for key in plans: save_receipts(key)
        hashes = {key: caller.close() for key, caller in admissions.items()}
        write(root/'caller-receipt-bindings.json', {'screen_digest': digest(screen), 'receipt_sha256': hashes,
            'gpu_timing_attestation': False})
    return {'dispatched_tasks': sum(r['launched'] for rows in receipts.values() for r in rows),
        'finished_task_runs': len(finished), 'planned_task_runs': len(screen['workload_order']),
        'calibration_observation_gate': calibrated, 'errors': errors,
        'caller_receipt_sha256': hashes, 'cleanup': cleanup, 'execution_ledger_head': head}


def archive(root, destination, maximum_bytes):
    from tools.nvarc_runtime_archive import validate_members
    root = Path(root); interrupted=[];files = validate_members(root,interrupted=interrupted)
    index=canonical({'format':'irisx/unqualified-interrupted-artifacts-v1','artifacts':interrupted,
        'promotion':False,'candidate_qualification':False}) if interrupted else None
    require(sum(path.stat().st_size for path in files) + (len(index) if index and not (root/'interrupted-retention.json').exists() else 0) <= maximum_bytes,
            'bounded E10 evidence archive exceeded its declared byte cap')
    temporary = destination.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as output:
        for path in files: output.write(path, path.relative_to(root).as_posix())
        if index and not (root/'interrupted-retention.json').exists():output.writestr('interrupted-retention.json',index)
    temporary.replace(destination)


def execute(root, dependency, started):
    from tools.stage_nvarc_e10_screen import verify_runtime_tree,full_task_gate_ids
    root = Path(root); screen, plans, challenges = verify_runtime_tree(root)
    errors = []; summary = {}; phase = 'material-and-hardware'; stopped = True
    try:
        require(os.environ.get('PYTHONHASHSEED') == '0' and sys.flags.hash_randomization == 0,
                'fresh E10 parent startup hash seed zero required')
        require(shutil.disk_usage(root).free >= screen['minimum_free_working_bytes'],
                'bounded screen working-space reserve unavailable')
        write(root/'mount-policy.json',verify_mount(screen,'frozen public solver-visible development challenges only'))
        # Reuse the pinned original native material and four-L4 checks.
        model, hardware = prepare(root, next(iter(plans.values())), dependency)
        require(time.monotonic()-started <= screen['startup_seconds'],
                'initial pinned material/hardware setup exceeded declared startup budget')
        inventory = parse_json((root/'source-inventory.json').read_bytes())
        write(root/'source-verification.json', {'inventory': inventory, 'inventory_digest': digest(inventory)})
        for key, plan in plans.items():
            for name in ('hardware.json', 'model-verification.json', 'source-verification.json'):
                shutil.copyfile(root/name, root/key/name)
            write(root/key/'parent-verification.json', {'plan_digest': digest(plan),
                'source_inventory_verified': True, 'four_distinct_bf16_l4s': True,
                'model_material_digest': plan['model_material_digest']})
        phase = 'bounded-native-screen'
        def calibration_check(key, receipt_hash):
            cpu_export(root, key, screen, model, dependency, started, receipt_hash, validate_only=True,
                       mandatory_tasks=[job['task_id'] for job in screen['workload_order']
                           if job['job_id'] in screen['calibration_jobs']])
        summary = run_jobs(root, screen, plans, challenges, model, dependency, hardware, started,
                           calibration_check=calibration_check)
    except BaseException as error:
        errors.append(diagnostic(error, phase))
        stopped = getattr(error, 'cleanup_report', {}).get('all_producers_stopped', True)
    phase = 'independent-cpu-replay'
    exported = {}
    if stopped and (root/'caller-receipt-bindings.json').is_file():
        bindings = parse_json((root/'caller-receipt-bindings.json').read_bytes())
        require(bindings['screen_digest'] == digest(screen), 'caller screen identity differs')
        for key, plan in plans.items():
            try:
                cpu_export(root, key, screen, model, dependency, started, bindings['receipt_sha256'][key],
                    mandatory_tasks=full_task_gate_ids(plan,challenges))
                exported[key] = True
            except BaseException as error:
                exported[key] = False; errors.append({'subrun': key, **diagnostic(error, phase)})
    terminal = {'screen_id': screen['screen_id'], 'screen_digest': digest(screen), 'summary': summary,
        'outcome': 'failed' if errors else 'complete' if summary.get('finished_task_runs') == len(screen['workload_order'])
            and all(exported.values()) and len(exported) == len(plans) else 'partial',
        'errors': errors, 'strict_exports': exported, 'host_wall_seconds': time.monotonic()-started,
        'paid_usd': 0, 'correctness_scored': False, 'promotion': False, 'official_submission': False,
        'gpu_kernel_timing_attestation': False,
        'caller_receipt_bindings_sha256': hashlib.sha256((root/'caller-receipt-bindings.json').read_bytes()).hexdigest()
            if (root/'caller-receipt-bindings.json').is_file() else None,
        'allocated_gpu_hours_proxy': 4*(time.monotonic()-started)/3600,
        'allocation_observation': 'four GPUs required at material gate; provider provisioning and teardown timestamps unknown'}
    write(root/'terminal.json', terminal)
    if stopped:
        try: archive(root, root.parent/(screen['screen_id']+'.zip'), screen['maximum_archive_uncompressed_bytes'])
        except BaseException as error:
            terminal['outcome'] = 'failed'; terminal['errors'].append(diagnostic(error, 'archive'))
            write(root/'terminal.json', terminal)
    print(json.dumps(terminal), flush=True)
    return 0 if terminal['outcome'] == 'complete' else 1


def cpu_export(root, key, screen, model, dependency, started, receipt_hash, *, validate_only=False, mandatory_tasks=None):
    if not validate_only:
        from tools.stage_nvarc_e10_screen import full_task_gate_ids
        expected=full_task_gate_ids(parse_json((root/key/'plan.json').read_bytes()),
            parse_json((root/key/'challenges.json').read_bytes()))
        require(mandatory_tasks==expected,'final export requires all actual task gates in bound plan order')
    remaining = screen['maximum_notebook_wall_seconds']-(time.monotonic()-started)
    require(remaining > 0, 'whole-session CPU export deadline exhausted')
    environment = dict(os.environ, PYTHONHASHSEED='0', CUDA_VISIBLE_DEVICES='',
        PYTHONPATH=str(root/key)+os.pathsep+str(dependency), HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1', OMP_NUM_THREADS='2')
    command = [sys.executable, str(root/key/'tools/nvarc_native_export.py'), '--root', str(root/key),
        '--tokenizer', str(model/'tokenizer.json'), '--caller-admissions', str(root/key/'caller-admissions.json'),
        '--caller-admissions-sha256', receipt_hash]
    if validate_only: command.append('--validate-only')
    for task in mandatory_tasks or []:command.extend(['--require-task-gates',task])
    prefix = 'calibration-export' if validate_only else 'export'
    with (root/key/(prefix+'.stdout.log')).open('wb') as out, (root/key/(prefix+'.stderr.log')).open('wb') as err:
        subprocess.run(command, env=environment, cwd=root/key, stdout=out, stderr=err, check=True,
                       timeout=min(remaining, screen['maximum_export_process_seconds']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--dependency', type=Path, required=True)
    parser.add_argument('--started', type=float, required=True)
    parser.add_argument('--owner-pid', type=int, required=True)
    args = parser.parse_args()
    from tools.nvarc_public_eval import install_owner_guard
    install_owner_guard(args.owner_pid, signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt('E10 owner exited')))
    return execute(args.root, args.dependency, args.started)


if __name__ == '__main__': raise SystemExit(main())
