"""Explicit source fetch, leaf-process deadlines, and post-exit sealed scoring."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .model_pins import verify_model, sha256_file


def write_json(path, value):
    path = Path(path)
    raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b'\n'
    with path.open('xb') as stream:
        stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def offline_environment():
    env = os.environ.copy()
    env.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                'HF_DATASETS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false'})
    return env


def leaf(command, log_path, timeout):
    """Own a single non-spawning child. Bound setup/worker/scorer independently."""
    if timeout <= 0:
        raise TimeoutError('No time remains for this stage')
    with Path(log_path).open('xb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env=offline_environment(),
                                   cwd=str(Path(__file__).resolve().parents[2]))
        try:
            return process.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            process.kill()  # This leaf PID only, never any unrelated user process.
            process.wait(timeout=5)
            return process.returncode, True
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            raise


def preflight(materials, model, output):
    from .materials import verify_materials
    verification, _ = verify_materials(materials)
    pins = {name: sha256_file(Path(materials) / name)
            for name in ('plan.json', 'gold.json', 'material_manifest.json')}
    model_receipt = verify_model(model)
    sources = {p.name: sha256_file(p) for p in sorted(Path(__file__).parent.iterdir())
               if p.is_file() and p.suffix in {'.py', '.json'}}
    write_json(output, {'materials': verification, 'material_sha256': pins,
                       'model': model_receipt, 'source_sha256': sources})


def score_stage(materials, output, worker_returncode, timed_out):
    output = Path(output)
    admission = json.loads((output / 'admission.json').read_text())
    for name, digest in admission['material_sha256'].items():
        if sha256_file(Path(materials) / name) != digest:
            raise ValueError('Frozen materials changed during inference')
    result_path = output / 'worker' / 'result.json'
    if not result_path.exists():
        result_path.parent.mkdir(exist_ok=True)
        write_json(result_path, {'status': 'worker_deadline' if timed_out else 'worker_failed',
                   'queries': [], 'qualification': 'No aggregate result; individual raw receipts remain preserved, not silently counted as completed.'})
    seal = {'worker_exited': True, 'returncode': worker_returncode, 'timed_out': timed_out,
            'result_sha256': sha256_file(result_path),
            'receipts': {str(p.relative_to(output / 'worker')): sha256_file(p)
                         for p in sorted((output / 'worker' / 'receipts').glob('*.json'))}}
    write_json(output / 'prediction_seal.json', seal)
    # Gold is decoded only after the worker is gone and predictions are sealed.
    from .evaluate import score_sealed
    report = score_sealed(Path(materials) / 'plan.json', Path(materials) / 'gold.json',
                          result_path, output / 'prediction_seal.json')
    report.update(worker_returncode=worker_returncode, worker_timed_out=timed_out)
    if worker_returncode or timed_out:
        report['scientific_complete'] = False
    write_json(output / 'evaluation.json', report)
    return 0 if report['scientific_complete'] else 2


def run_diagnostic(materials, model, output, budget_seconds=7200):
    if not 60 <= budget_seconds <= 7200:
        raise ValueError('This diagnostic requires a whole-run budget of 60..7200 seconds')
    started = time.monotonic()
    deadline = started + budget_seconds
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    materials, model = Path(materials).resolve(), Path(model).resolve()
    write_json(output / 'intent.json', {'schema': 'iris-public-sft141-run-v1',
        'budget_seconds': budget_seconds, 'started_unix': time.time(),
        'same_session_resume': False, 'scientific_protocol': '12 parents, all task.test inputs, 8 D4 views, common-pool rankings'})
    entry = [sys.executable, '-m', 'tools.public_sft141_diagnostic']
    stage = 'preflight'
    try:
        rc, timeout = leaf(entry + ['_preflight', '--materials-dir', str(materials),
                          '--model-dir', str(model), '--output', str(output / 'admission.json')],
                          output / 'preflight.log', deadline - time.monotonic() - 45)
        if rc or timeout:
            raise RuntimeError('Preflight failed; see preflight.log. No model worker started.')
        stage = 'inference'
        remaining = deadline - time.monotonic() - 30
        command = [sys.executable, '-m', 'tools.public_sft141_diagnostic.model_worker',
                   '--plan', str(materials / 'plan.json'), '--model-dir', str(model),
                   '--output', str(output / 'worker'), '--budget-seconds', str(remaining)]
        rc, timeout = leaf(command, output / 'worker.log', remaining)
        stage = 'scoring'
        command = entry + ['_score', '--materials-dir', str(materials), '--output', str(output),
                            '--worker-returncode', str(rc)]
        if timeout:
            command.append('--timed-out')
        score_rc, score_timeout = leaf(command, output / 'scoring.log', deadline - time.monotonic() - 5)
        elapsed = time.monotonic() - started
        complete = score_rc == 0 and not score_timeout and elapsed <= budget_seconds
        write_json(output / 'closure.json', {'elapsed_seconds': elapsed, 'budget_seconds': budget_seconds,
                   'within_total_budget': elapsed <= budget_seconds, 'scientific_complete': complete,
                   'worker_returncode': rc, 'worker_timed_out': timeout,
                   'scorer_returncode': score_rc, 'scorer_timed_out': score_timeout})
        return 0 if complete else 2
    except Exception as exc:
        write_json(output / 'failure.json', {'stage': stage, 'type': type(exc).__name__,
                   'message': str(exc), 'elapsed_seconds': time.monotonic() - started})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    fetch = subs.add_parser('fetch', help='Explicitly download pinned official public ARC evaluation files')
    fetch.add_argument('--data-dir', required=True)
    prepare = subs.add_parser('prepare', help='Generate independent gold-separated materials locally')
    prepare.add_argument('--data-dir', required=True)
    prepare.add_argument('--materials-dir', required=True)
    verify = subs.add_parser('verify-model')
    verify.add_argument('--model-dir', required=True)
    for name in ('run', '_preflight'):
        run = subs.add_parser(name)
        run.add_argument('--materials-dir', required=True)
        run.add_argument('--model-dir', required=True)
        run.add_argument('--output', required=True)
        if name == 'run':
            run.add_argument('--budget-seconds', type=int, default=7200)
    score = subs.add_parser('_score')
    score.add_argument('--materials-dir', required=True)
    score.add_argument('--output', required=True)
    score.add_argument('--worker-returncode', type=int, required=True)
    score.add_argument('--timed-out', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'fetch':
        from .materials import fetch_public_data
        print(json.dumps(fetch_public_data(args.data_dir), indent=2))
    elif args.command == 'prepare':
        from .materials import prepare_materials
        print(json.dumps(prepare_materials(args.data_dir, args.materials_dir), indent=2))
    elif args.command == 'verify-model':
        print(json.dumps(verify_model(args.model_dir), indent=2))
    elif args.command == '_preflight':
        preflight(args.materials_dir, args.model_dir, args.output)
    elif args.command == '_score':
        return score_stage(args.materials_dir, args.output, args.worker_returncode, args.timed_out)
    else:
        return run_diagnostic(args.materials_dir, args.model_dir, args.output, args.budget_seconds)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
