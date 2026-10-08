"""Independent, zero-model, CPU-only E10 screen replay against caller pins.

The coordinator supplies the immutable outbound package and caller receipt
binding hashes from its retained record, not from worker checkpoints. A replay
PASS is transcript/source/resource consistency, never ARC quality or GPU clock
attestation. No runtime output is republished by this verifier.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_allocation_transport import load_caller_receipt
from tools.nvarc_native_multitask import digest, require
from tools.stage_nvarc_e10_screen import preflight, verify_runtime_tree, full_task_gate_ids


def verify(package, runtime, expected_package_manifest_sha256, expected_caller_bindings_sha256,
           *, replay_seconds=300, run=subprocess.run):
    package, runtime = Path(package), Path(runtime)
    preflight(package, expected_manifest_sha256=expected_package_manifest_sha256)
    screen, plans, challenges = verify_runtime_tree(runtime,current_resource=False)
    from tools.nvarc_runtime_archive import validate_members
    validate_members(runtime)
    require((runtime/'screen.json').read_bytes() == (package/'runtime/screen.json').read_bytes(),
            'retained screen differs from independently pinned outbound package')
    for name in screen['payload_sha256']:
        require((runtime/name).read_bytes() == (package/'runtime'/name).read_bytes(),
                'retained source/config/input differs from outbound: '+name)
    binding_path = runtime/'caller-receipt-bindings.json'
    require(not binding_path.is_symlink() and
        hashlib.sha256(binding_path.read_bytes()).hexdigest() == expected_caller_bindings_sha256,
        'independently retained caller receipt binding bytes differ')
    caller = parse_json(binding_path.read_bytes())
    require(set(caller) == {'screen_digest', 'receipt_sha256', 'gpu_timing_attestation'} and
        caller['screen_digest'] == digest(screen) and set(caller['receipt_sha256']) == set(plans) and
        caller['gpu_timing_attestation'] is False, 'closed matching caller receipt bindings required')
    require(type(replay_seconds) in (int, float) and 0 < replay_seconds <= 300,
            'bounded independent CPU replay required')
    replays = {}
    for key, plan in plans.items():
        receipt = runtime/key/'caller-admissions.json'
        load_caller_receipt(receipt, caller['receipt_sha256'][key], plan, challenges)
        environment = dict(os.environ, PYTHONHASHSEED='0', CUDA_VISIBLE_DEVICES='',
            PYTHONPATH=str(runtime/key), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1',
            OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
        command = [sys.executable, str(runtime/key/'tools/nvarc_native_export.py'), '--root', str(runtime/key),
            '--tokenizer', str(runtime/'verified-tokenizer.json'), '--caller-admissions', str(receipt),
            '--caller-admissions-sha256', caller['receipt_sha256'][key], '--validate-only', '--verify-committed']
        tasks=full_task_gate_ids(plan,challenges)
        for task in tasks:command.extend(['--require-task-gates',task])
        result = run(command, env=environment, cwd=runtime/key, capture_output=True, timeout=replay_seconds, check=True)
        context = parse_json(result.stdout)
        require(context['strict_replay_validated'] is True and context['output_published'] is False and
            context['committed_projection_verified'] is True and
            context['new_model_calls'] == 0 and context['cpu_only'] is True and
            context['caller_admission_receipt_sha256'] == caller['receipt_sha256'][key] and
            isinstance(context.get('mandatory_task_gates'),dict) and set(context['mandatory_task_gates'])==set(tasks),
            'fresh independent CPU replay result differs')
        replays[key] = context
    control=screen['calibration_subrun'];tasks=[job['task_id'] for job in screen['workload_order'] if job['job_id'] in screen['calibration_jobs']]
    command=[sys.executable,str(runtime/control/'tools/nvarc_native_export.py'),'--root',str(runtime/control),
        '--tokenizer',str(runtime/'verified-tokenizer.json'),'--caller-admissions',str(runtime/control/'caller-admissions.json'),
        '--caller-admissions-sha256',caller['receipt_sha256'][control],'--validate-only']
    for task in tasks:command.extend(['--require-task-gates',task])
    environment=dict(os.environ,PYTHONHASHSEED='0',CUDA_VISIBLE_DEVICES='',PYTHONPATH=str(runtime/control),
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1')
    result=run(command,env=environment,cwd=runtime/control,capture_output=True,timeout=replay_seconds,check=True)
    mandatory=parse_json(result.stdout)
    require(mandatory['strict_replay_validated'] is True and mandatory['output_published'] is False and
        set(mandatory['mandatory_task_gates'])==set(tasks),'external mandatory calibration replay differs')
    terminal = parse_json((runtime/'terminal.json').read_bytes())
    require(terminal['screen_digest'] == digest(screen) and terminal['screen_id'] == screen['screen_id'] and
        terminal['correctness_scored'] is terminal['promotion'] is terminal['official_submission'] is False,
        'matching unpromoted development terminal required')
    return {'screen_id': screen['screen_id'], 'screen_digest': digest(screen),
        'independent_replay_passed': True, 'task_count': screen['tasks'], 'actual_test_count': screen['tests'],
        'planned_task_runs': screen['task_runs'], 'planned_test_runs': screen['test_runs'],
        'runtime_outcome': terminal['outcome'], 'replays': replays,'mandatory_calibration':mandatory['mandatory_task_gates'],
        'new_model_calls': 0, 'correctness_scored': False,
        'gpu_timing_attestation': False, 'promotion': False, 'official_submission': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--expected-package-manifest-sha256', required=True)
    parser.add_argument('--expected-caller-bindings-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.package, args.runtime, args.expected_package_manifest_sha256,
                            args.expected_caller_bindings_sha256)))


if __name__ == '__main__': main()
