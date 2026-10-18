"""CPU-only coordinator for a paired compact-model TTT stability diagnostic.

Uses the existing owned-worker lifecycle and admitted offline model materials.
No provider calls, PUBLIC inference, architecture expansion or score selection.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time

from tools.arc2_goal_sprint_20261017.launch import check_dataset_separation, require, sha, write_new
from .concurrency import run_wave
from .controller import model_bound, progress

WORKFLOW = 'paired-ttt-stability-v1'
WORKLOAD = 'compact-paired-ttt-stability-v1'


def run(config):
    require(config.get('workflow') == WORKFLOW, 'explicit diagnostic workflow required')
    require(config['deadline_epoch'] == config['started_epoch'] + 43200
            and 0 < config['started_epoch'] <= time.time() < config['deadline_epoch'], 'original session deadline required')
    require(config.get('parameters', {}) == {}, 'diagnostic v1 settings are fixed, not arbitrary posttraining overrides')
    source, output = Path(config['source_root']), Path(config['output_root'])
    output.mkdir(parents=True, exist_ok=False)
    check_dataset_separation(config['input_root'], config['allowed_input_roots'])
    write_new(output / 'isolation.json', {'mechanism': 'dataset-separated-provider-execution',
        'evaluator_dataset_absent': True, 'os_sandbox_claimed': False, 'public_inference_performed': False,
        'public_projection_use': 'training split exclusion only', 'public_answers_used': False})
    env = {**os.environ, **config['runtime_env'], 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    probe = subprocess.run([config['python'], '-B', '-m', 'tools.nvarc_posttrain_20261017.worker', '--topology'],
        cwd=source, env=env, check=True, capture_output=True, text=True, timeout=120)
    topology = json.loads(probe.stdout.splitlines()[-1]);write_new(output / 'topology.json', topology)
    # Previous actual single-worker 4B reservation was about25GB. This fixed
    # diagnostic admits only a device with a32GiB free envelope; it never pools
    # memory across devices or silently changes precision/optimizer/TTT.
    require(topology.get('device_count') == 1 and topology.get('free_bytes', 0) >= 32 * 1024**3,
            'paired original-recipe diagnostic requires one device with32GiB free; redesign separately otherwise')
    progress('actual_topology', **topology)
    waves = []
    for number, variant in enumerate(('2b', '4b')):
        now = time.time()
        end = now + max(0., config['deadline_epoch'] - 120 - now) / (2 - number)
        job = {'job_id': variant + '-S', 'variant': variant, 'arm': 'S', 'mode': 'stability',
            'source_identity': config['source_identity'], 'workload_identity': WORKLOAD,
            'device_identity': topology['device_identity'], 'model_root': config['model_roots'][variant],
            'seed': 7321 + number, 'adapter_seed': 731 if variant == '2b' else 739, 'cpu_threads': 1,
            'parameters': {}, 'allocator_fraction': .8,
            **{key: config[key] for key in ('training_root', 'training_manifest_path', 'public_path')}}
        progress('stability_variant_start', variant=variant, requested_parents=32,
                 treatments=['no_ttt', 'ttt32'], views=2, deadline_epoch=end)
        wave = run_wave([job], python=config['python'], source_root=str(source),
            output_root=str(output / ('stability-' + variant)), deadline_epoch=end, common_env=env,
            load_timeout_seconds=600, stop_timeout_seconds=15)
        if any(not row['closure_verified'] and row['status'] not in {'deadline_before_launch', 'ownership_blocked'}
               for row in wave['jobs']):
            raise RuntimeError('unverified worker closure; no later dispatch')
        for row in wave['jobs']:
            result = row.get('result')
            if result is not None:
                require(result.get('mode') == 'stability' and result.get('job_id') == job['job_id']
                        and all(result.get(key) == job[key] for key in ('source_identity', 'workload_identity', 'device_identity'))
                        and model_bound(result.get('model_identity'), variant),
                        'exact official model and diagnostic result required')
        waves.append(wave)
        write_new(output / ('stability-' + variant + '-wave.json'), wave)
        progress('stability_variant_closed', variant=variant, completed=wave['completed'], wall_seconds=wave['wall_seconds'])
    rows = [row for wave in waves for row in wave['jobs']]
    complete = len(rows) == 2 and all(row['status'] == 'completed' and row['closure_verified']
        and (row.get('result') or {}).get('stability', {}).get('complete') is True for row in rows)
    protocols = {(row.get('result') or {}).get('stability', {}).get('protocol_sha256') for row in rows}
    require(not complete or len(protocols) == 1 and None not in protocols, 'paired model panel/protocol differs')
    summary = {'format': 'irisx/nvarc-stability-controller-v1', 'run_id': config['run_id'],
        'source_identity': config['source_identity'], 'workflow': WORKFLOW, 'completed': complete,
        'requested_models': ['2b', '4b'], 'requested_parents_per_model': 32,
        'treatments': ['no_ttt', 'ttt32'], 'matched_views': 2, 'workers': rows,
        'public_inference_performed': False, 'public_score': None, 'official_score': None,
        'clean_generalization_claimed': False, 'architecture_expansion_tested': False,
        'automatic_following_run': False, 'training_or_ensemble_selected': False}
    write_new(output / 'run-summary.json', summary)
    return summary


def close_diagnostic(config, control, proof):
    """Bind existing private diagnostic artifacts only after owned-tree closure."""
    from tools.nvarc_posttrain_20261017.score import closure_structure
    closure_structure(proof)
    require(type(proof.get('forced')) is bool, 'explicit normal-versus-forced closure required')
    output = Path(config['output_root']); files = {}; total = 0
    if output.is_dir():
        for path in sorted(output.rglob('*')):
            if path.is_symlink():
                raise ValueError('diagnostic output symlink forbidden')
            if not path.is_file() or path.suffix not in {'.json', '.jsonl'}:
                continue
            size = path.stat().st_size; total += size
            require(size <= 64 * 1024**2 and total <= 256 * 1024**2, 'bounded diagnostic evidence required')
            files[path.relative_to(output).as_posix()] = {'bytes': size, 'sha256': sha(path)}
    summary_path = output / 'run-summary.json'
    summary = json.loads(summary_path.read_bytes()) if summary_path.is_file() else {}
    if summary:
        require(summary.get('source_identity') == config['source_identity']
                and summary.get('run_id') == config['run_id'] and summary.get('workflow') == WORKFLOW,
                'closed diagnostic summary identity differs')
    terminal = {'format': 'irisx/nvarc-closed-stability-v1', 'run_id': config['run_id'],
        'status': 'CLOSED_DIAGNOSTIC', 'completed': summary.get('completed') is True
            and proof['worker_returncode'] == 0 and proof['returncode'] == 0 and not proof['forced'],
        'source_manifest_sha256': config['source_identity'], 'workflow': WORKFLOW, 'files': files,
        'closure_sha256': sha(Path(control) / 'owner-closure.json'), 'generation_may_resume': False,
        'public_score': None, 'official_score': None, 'provider_terminal_verified': False,
        'clean_generalization_claimed': False, 'new_model_or_ensemble_selected': False}
    write_new(Path(control) / 'terminal.json', terminal)
    return terminal
