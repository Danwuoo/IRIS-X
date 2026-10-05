"""Owner-Editor public inference coordinator; no provider operations or solutions IO."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

from tools.nvarc_public_eval import ResultStore, validate_plan, write_archive, sha, install_owner_guard
from tools.nvarc_native_multitask import write, digest, require
from tools.arc_kaggle_submission import parse_json


def stop_process(process):
    if process.poll() is None:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=15)
        else:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        process.wait(timeout=15)


def prepare(root, plan, dependency):
    require(sys.version_info[:3] == (3, 11, 13), 'pinned Python 3.11.13 required')
    require(shutil.disk_usage(root).free >= 10*1024**3, 'ten GiB free working space required')
    inventory = parse_json((root/'source-inventory.json').read_bytes())
    for name, item in inventory.items():
        path = dependency/name
        require(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], 'dependency source differs: '+name)
    write(root/'source-verification.json', {'inventory_digest': digest(inventory), 'dependency_root': str(dependency)})
    sys.path.insert(0, str(dependency))
    import torch
    from hardware_helpers import collect_hardware_inventory
    require(torch.__version__ == '2.8.0+cu128' and torch.version.cuda == '12.8' and
        Path(torch.__file__).resolve().is_relative_to(dependency.resolve()), 'pinned Torch/CUDA source required')
    smi = subprocess.run(['nvidia-smi', '--query-gpu=index,name,memory.total,uuid', '--format=csv,noheader,nounits'],
        capture_output=True, text=True, timeout=30, check=True)
    hardware = collect_hardware_inventory(torch, smi.stdout, lambda value: write(root/'hardware-raw.json', value))
    require(len(hardware) == len({r['uuid'] for r in hardware}) == 4 and
        all(r['name'] == 'NVIDIA L4' and r['bf16'] for r in hardware), 'four distinct BF16 L4s required')
    write(root/'hardware.json', {'inventory': hardware, 'torch': torch.__version__, 'cuda': torch.version.cuda})
    mounts = [Path('/kaggle/input/models/sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1'),
              Path('/kaggle/input/qwen3_4b_grids15_sft139/transformers/bfloat16/1')]
    matches = [p for p in mounts if (p/'config.json').is_file()]
    require(len(matches) == 1, 'one exact published model mount required'); model = matches[0]
    for name, item in parse_json((root/'model-inventory.json').read_bytes()).items():
        path = model/name
        require(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], 'published model bytes differ: '+name)
    write(root/'model-verification.json', {'model_material_digest': plan['model_material_digest'],
        'all_ten_files_verified': True, 'competition_files_opened': 0})
    with (root/'dependency-setup.log').open('w', encoding='utf-8') as log:
        subprocess.run([sys.executable, '-m', 'pip', 'uninstall', '-y', 'tensorflow'],
            stdout=log, stderr=subprocess.STDOUT, timeout=60, check=True)
    return model, hardware


def run_workers(root, plan, challenges, model, dependency, hardware, store, started,
                *, launch=subprocess.Popen, worker_command=None, now=time.monotonic, pause=time.sleep):
    """Persistent file-mailbox workers; each task is dispatched once, no retries."""
    root = Path(root); states = {}; failures = []; finished = set(); sequence = 0
    seen = {}; setup_end = started+plan['startup_seconds']; last_progress = started
    end = started+plan['maximum_notebook_wall_seconds']-plan['export_reserve_seconds']
    epoch_end = time.time()+max(0, end-now())
    ttt = plan['profile'] == 'TTT128-30'
    queue = sorted(challenges, key=lambda k: (-((plan['task_materials'][k]['training_input_tokens']/800 if ttt else 0)
        +30*len(challenges[k]['test'])), k))
    root.joinpath('tasks').mkdir(exist_ok=True); root.joinpath('workers').mkdir(exist_ok=True)
    def event(kind, **details):
        row = {'event': kind, 'run_id': plan['run_id'], 'wall_seconds': now()-started, **details}
        with (root/'progress.jsonl').open('ab') as stream:
            stream.write(json.dumps(row, sort_keys=True).encode()+b'\n'); stream.flush(); os.fsync(stream.fileno())
        print(json.dumps(row), flush=True)
    def consume(key):
        path = root/'tasks'/key/'checkpoint.json'
        if path.is_file():
            signature = (path.stat().st_mtime_ns, path.stat().st_size)
            if seen.get(key) != signature:
                store.commit(parse_json(path.read_bytes())); seen[key] = signature
    def retire(rank, reason):
        state = states[rank]; stop_process(state['process'])
        if state['key'] is not None:
            consume(state['key']); finished.add(state['key'])
        state['retired'] = True; state['key'] = None
        failures.append({'rank': rank, 'reason': reason}); event('worker-retired', rank=rank, reason=reason)
    try:
        # Separate cwd/compiler caches prevent shared generated-code races.
        for rank in range(4):
            directory = root/'workers'/str(rank); directory.mkdir(exist_ok=False)
            stdout = (directory/'stdout.log').open('w', encoding='utf-8')
            stderr = (directory/'stderr.log').open('w', encoding='utf-8')
            environment = dict(os.environ, PYTHONPATH=str(root)+os.pathsep+str(dependency),
                CUDA_VISIBLE_DEVICES=hardware[rank]['uuid'], PYTHONHASHSEED='0', HF_HUB_OFFLINE='1',
                TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1', UNSLOTH_DISABLE_STATISTICS='1',
                WANDB_DISABLED='true', TOKENIZERS_PARALLELISM='false', PYTHONIOENCODING='utf-8',
                TRITON_PTXAS_PATH='/usr/local/cuda/bin/ptxas', TRITON_CACHE_DIR=str(directory/'triton-cache'),
                OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
            command = worker_command or [sys.executable, str(root/'tools/nvarc_public_eval_runtime.py')]
            command = [*command, '--root', str(root), '--model', str(model), '--dependency', str(dependency),
                       '--rank', str(rank), '--deadline', str(epoch_end), '--parent-pid', str(os.getpid())]
            states[rank] = {'process': None, 'key': None, 'ready': False, 'retired': False,
                            'sequence': 0, 'end': None, 'stdout': stdout, 'stderr': stderr}
            event('worker-start-reserved', rank=rank)
            states[rank]['process'] = launch(command, cwd=directory, env=environment,
                stdout=stdout, stderr=stderr, start_new_session=os.name != 'nt')
            write(directory/'process.json', {'run_id': plan['run_id'], 'parent_pid': os.getpid(),
                'worker_pid': states[rank]['process'].pid})
        dispatch_started = False
        while now() < end:
            for rank, state in states.items():
                if state['retired']: continue
                directory = root/'workers'/str(rank); ready = directory/'ready.json'
                if not state['ready'] and ready.is_file():
                    observed = parse_json(ready.read_bytes())
                    require(observed['rank'] == rank and observed['uuid'] == hardware[rank]['uuid'] and
                        observed['model_material_digest'] == plan['model_material_digest'], 'actual model-ready identity differs')
                    state['ready'] = True; event('model-ready', rank=rank, uuid=observed['uuid'])
                if state['key'] is not None:
                    consume(state['key'])
                    done = directory/'done.json'
                    if done.is_file():
                        result = parse_json(done.read_bytes())
                        if result['sequence'] == state['sequence']:
                            require(result['task_id'] == state['key'], 'worker completion task differs')
                            key = state['key']; consume(key); finished.add(key); state['key'] = None
                            event('task-finished', rank=rank, task_id=key, outcome=result['outcome'])
                            if result['retired']: retire(rank, 'task-error-or-reset-failure'); continue
                    if state['key'] is not None and now() >= state['end']:
                        retire(rank, 'task-watchdog-timeout'); continue
                code = state['process'].poll()
                if code is not None:
                    retire(rank, 'unexpected-worker-exit-'+str(code)); continue
            if not dispatch_started:
                if any(s['retired'] for s in states.values()):
                    raise RuntimeError('startup worker failure before complete four-model gate')
                if all(s['ready'] for s in states.values()): dispatch_started = True
                elif now() >= setup_end: raise RuntimeError('four-model startup exceeded 900-second budget')
            if dispatch_started:
                for rank, state in states.items():
                    if state['retired'] or state['key'] is not None or not queue: continue
                    if now()+120+(30 if not ttt else 150) >= end: continue
                    key = queue.pop(0); sequence += 1
                    state.update(key=key, sequence=sequence, end=min(end, now()+120+(1200 if ttt else 0)+30*len(challenges[key]['test'])))
                    event('task-dispatch-reserved', rank=rank, task_id=key, sequence=sequence)
                    write(root/'workers'/str(rank)/'job.json', {'sequence': sequence, 'task_id': key})
            if not queue and all(s['key'] is None for s in states.values()): break
            if all(s['retired'] for s in states.values()): break
            if dispatch_started and queue and all(s['key'] is None for s in states.values()) and now()+270 >= end: break
            if now()-last_progress >= 30:
                details = {'finished_tasks': len(finished), 'total_tasks': len(challenges),
                           'active_tasks': {str(r): s['key'] for r, s in states.items() if s['key'] is not None}}
                write(root/'progress.json', details); event('progress', **details); last_progress = now()
            pause(.2)
        for rank, state in states.items():
            if state['key'] is not None: consume(state['key'])
            if not state['retired']: write(root/'workers'/str(rank)/'job.json', {'stop': True})
        return {'finished_tasks': len(finished), 'dispatched_tasks': sequence, 'worker_failures': failures,
                'undispatched_tasks': len(queue), 'all_four_models_ready': all(s['ready'] for s in states.values())}
    finally:
        for state in states.values():
            if state['process'] is not None: stop_process(state['process'])
            state['stdout'].close(); state['stderr'].close()
        # Consume the last atomic checkpoint after all producers have stopped.
        for state in states.values():
            if state['key'] is not None: consume(state['key'])


def execute(root, plan, dependency, started):
    root = Path(root); phase = 'input'; store = None; summary = {}; errors = []
    try:
        require(os.environ.get('PYTHONHASHSEED') == '0' and sys.flags.hash_randomization == 0, 'parent startup hash seed zero required')
        require(sha(root/'challenges.json') == plan['challenges_sha256'], 'exact public input bytes differ')
        challenges = parse_json((root/'challenges.json').read_bytes()); validate_plan(plan, challenges)
        store = ResultStore(root, plan, challenges)
        phase = 'material-and-hardware'
        model, hardware = prepare(root, plan, dependency)
        phase = 'persistent-public-workers'
        summary = run_workers(root, plan, challenges, model, dependency, hardware, store, started)
    except BaseException as error:
        errors.append({'phase': phase, 'type': type(error).__name__, 'message': str(error)[:2400]})
    if store is not None: store.flush()
    coverage = parse_json((root/'coverage.json').read_bytes()) if (root/'coverage.json').is_file() else None
    failures = summary.get('worker_failures', [])
    failed = bool(errors or failures)
    partial = coverage is None or any(r['termination_reason'] != 'all_source_batches_completed' for r in coverage['rows'])
    terminal = {'format': plan['format'], 'run_id': plan['run_id'], 'plan_digest': digest(plan),
        'phase': phase, 'outcome': 'failed' if failed else 'partial' if partial else 'complete',
        'errors': errors, 'summary': summary, 'wall_seconds': time.monotonic()-started,
        'paid_usd': 0, 'correctness_scored': False, 'strict_portable_gpu_gate': False}
    write(root/'terminal.json', terminal)
    try:
        write_archive(root, root.parent/plan['download_archive'], plan)
    except BaseException as error:
        terminal['outcome'] = 'failed'; terminal['errors'].append({'phase': 'archive', 'type': type(error).__name__, 'message': str(error)[:2000]})
        write(root/'terminal.json', terminal)
    print(json.dumps(terminal), flush=True)
    return 1 if terminal['outcome'] == 'failed' else 0


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--dependency', type=Path, required=True); parser.add_argument('--started', type=float, required=True)
    parser.add_argument('--owner-pid', type=int, required=True)
    args = parser.parse_args(); plan = parse_json((args.root/'plan.json').read_bytes())
    def interrupted(*_args): raise KeyboardInterrupt('owner interrupted public evaluation')
    signal.signal(signal.SIGTERM, interrupted)
    install_owner_guard(args.owner_pid, signal.SIGTERM)
    return execute(args.root, plan, args.dependency, args.started)


if __name__ == '__main__': sys.exit(main())
