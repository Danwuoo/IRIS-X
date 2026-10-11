"""Prediction seals and one-way isolated historical PUBLIC120 scoring."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

if __package__ in (None, ''):
    ROOT = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(ROOT), str(ROOT / 'src')]

from tools.arc_learning_agent_20261011.budget import atomic_json, canonical, digest
from tools.arc_public_research_20261010.public_data import (
    load_solver_tasks, separated, read_regular, verify_inventory, validate_manifest,
    verify_upstream_inventory, git_object_sha, inventory)
from tools.arc_public_research_20261010.public_evaluator import SCORER_PINS
from tools.arc_offline_evaluation import validate_pools, POOL_FORMAT
from tools.nvarc_native_multitask import digest as old_digest

POLICIES = ('global_grid', 'task_ttt', 'full_agent')
ROOT = Path(__file__).resolve().parents[2]


def source_identity():
    from tools.arc_learning_agent_20261011.source_pack import collect_sources
    return {k: hashlib.sha256(v).hexdigest() for k, v in collect_sources().items()}


def check_source(expected):
    if expected != source_identity(): raise ValueError('sealed executable source differs')


def process_identity(pid):
    try:
        raw = (Path('/proc') / str(pid) / 'stat').read_text()
    except (FileNotFoundError, ProcessLookupError): return None
    fields = raw[raw.rfind(')') + 2:].split()
    return {'pid': pid, 'birth': int(fields[19]), 'session': int(fields[3]), 'state': fields[0]}


def session_members(sid):
    members = []
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            current = process_identity(int(path.name))
            if current and current['session'] == sid: members.append(current)
    return members


def verify_closed(closure, source, result_sha):
    required = {'format', 'worker_identity', 'returncode', 'graceful', 'source_identity_sha256',
                'result_sha256', 'session_members', 'request_sha256', 'parent_identity', 'process_tree_proof'}
    if set(closure) != required or closure['format'] != 'irisx/learning-owner-closure-v1':
        raise ValueError('owner closure schema differs')
    from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
    verify_closed_proof(closure['process_tree_proof'])
    if closure['process_tree_proof'].get('worker_returncode') != 0 or closure['process_tree_proof'].get('returncode') != 0 or closure['process_tree_proof'].get('forced') is not False:
        raise ValueError('owned worker failed')
    identity = closure['worker_identity']
    proof_identity = closure['process_tree_proof'].get('root_identity', {})
    if any(identity.get(k) != proof_identity.get(k) for k in ('pid', 'birth', 'session')):
        raise ValueError('foreign process-tree root binding')
    if set(identity) != {'pid', 'birth', 'session', 'state'} or identity['pid'] != identity['session']:
        raise ValueError('dedicated owner session required')
    current = process_identity(identity['pid'])
    if current and current['birth'] == identity['birth']: raise ValueError('owner still present')
    if session_members(identity['session']) or closure['session_members']:
        raise ValueError('owned descendants remain')
    if closure['returncode'] != 0 or closure['graceful'] is not True:
        raise ValueError('ungraceful owner cannot score')
    if closure['source_identity_sha256'] != digest(source) or closure['result_sha256'] != result_sha:
        raise ValueError('foreign owner/source/result binding')
    parent = process_identity(closure['parent_identity']['pid'])
    if parent is None or parent['birth'] != closure['parent_identity']['birth']:
        raise ValueError('coordinator incarnation changed')
    if parent['pid'] not in (os.getpid(), os.getppid()):
        raise ValueError('foreign coordinator')


def make_pools(challenges, results, *, run_id, elapsed_seconds):
    if not isinstance(results, dict) or not set(results) <= set(challenges):
        raise ValueError('foreign or duplicate task results')
    pools = {}
    for policy in POLICIES:
        records = []
        for task_id, task in sorted(challenges.items()):
            row = results.get(task_id)
            proposed = None if row is None else row.get('policies', {}).get(policy)
            if proposed is not None and (not isinstance(proposed, list) or len(proposed) != len(task['test'])):
                raise ValueError('multi-test result cardinality differs')
            tests = []
            for i, query in enumerate(task['test']):
                grids = [] if proposed is None else proposed[i]['candidates']
                if not isinstance(grids, list) or len(grids) > 2:
                    raise ValueError('top-two grid candidates required')
                tests.append({'test_index': i, 'input_digest': old_digest(query['input']),
                              'ranked_grids': grids, 'status': 'complete' if grids else 'not_executed'})
            records.append({'task_id': task_id, 'task_digest': old_digest(task), 'tests': tests, 'timings': {}})
        pool = {'format': POOL_FORMAT, 'run_id': run_id, 'method': 'learning-agent/' + policy,
                'challenges_digest': old_digest(challenges), 'records': records,
                'parent_wall_seconds': elapsed_seconds}
        validate_pools(challenges, pool); pools[policy] = pool
    return pools


def seal_predictions(prediction_root, *, solver_root, solver_manifest_sha256,
                     evaluator_manifest_sha256, result_path, closure, bindings):
    root, solver_root = separated(prediction_root, solver_root)
    if root.exists(): raise ValueError('prediction identity consumed')
    source = source_identity(); check_source(source)
    result_raw = read_regular(result_path)
    result_sha = hashlib.sha256(result_raw).hexdigest()
    verify_closed(closure, source, result_sha)
    result = json.loads(result_raw)
    if result.get('source_identity_sha256') != digest(source) or result.get('request_sha256') != closure['request_sha256']:
        raise ValueError('foreign result source/request binding')
    if result.get('run_id') != bindings.get('run_id'):
        raise ValueError('foreign prediction run binding')
    if result.get('status') not in ('complete', 'partial') or result.get('model_stopped') is not True:
        raise ValueError('solver terminal result required')
    if result.get('pending_work') or result.get('pending_work') is None:
        raise ValueError('unknown work blocks scoring')
    solver = load_solver_tasks(solver_root, solver_manifest_sha256)
    if result['solver_manifest_sha256'] != solver_manifest_sha256:
        raise ValueError('foreign solver result')
    if bindings.get('prediction_origin') not in ('trained_model_research', 'synthetic_cpu', 'model_disabled'):
        raise ValueError('explicit prediction origin required')
    if result.get('prediction_origin') != bindings['prediction_origin']:
        raise ValueError('prediction origin differs')
    if bindings['prediction_origin'] != 'trained_model_research' and result.get('production_model') is True:
        raise ValueError('production attribution differs')
    pools = make_pools(solver['challenges'], result['results'], run_id=result['run_id'],
                       elapsed_seconds=result['elapsed_seconds'])
    root.mkdir(parents=True)
    for policy, pool in pools.items(): atomic_json(root / (policy + '.json'), pool, exclusive=True)
    atomic_json(root / 'owner-closure.json', closure, exclusive=True)
    atomic_json(root / 'solver-result.json', result, exclusive=True)
    seal = {'format': 'irisx/learning-prediction-seal-v1', 'source_identity': source,
            'solver_manifest_sha256': solver_manifest_sha256,
            'evaluator_manifest_sha256': evaluator_manifest_sha256,
            'files': inventory(root), 'bindings': bindings, 'tasks': 120, 'tests': 167,
            'policies': list(POLICIES), 'generation_may_resume': False}
    atomic_json(root / 'prediction-seal.json', seal, exclusive=True)
    return {'path': str(root / 'prediction-seal.json'),
            'sha256': hashlib.sha256((root / 'prediction-seal.json').read_bytes()).hexdigest()}


def verify_seal(root, seal_sha, solver_root):
    root = Path(root)
    seal = json.loads(read_regular(root / 'prediction-seal.json', seal_sha))
    if seal['format'] != 'irisx/learning-prediction-seal-v1' or seal['generation_may_resume'] is not False:
        raise ValueError('prediction seal differs')
    if seal['policies'] != list(POLICIES) or (seal['tasks'], seal['tests']) != (120, 167):
        raise ValueError('policy/denominator differs')
    check_source(seal['source_identity'])
    verify_inventory(root, seal['files'], exclude=('prediction-seal.json',))
    closure = json.loads(read_regular(root / 'owner-closure.json'))
    verify_closed(closure, seal['source_identity'], seal['files']['solver-result.json']['sha256'])
    solver = load_solver_tasks(solver_root, seal['solver_manifest_sha256'])
    pools = {p: json.loads(read_regular(root / (p + '.json'))) for p in POLICIES}
    for pool in pools.values(): validate_pools(solver['challenges'], pool)
    return seal, solver, pools


def _worker(request):
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024**2, 32 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    root, solver_root, evaluator_root, output = separated(request['prediction_root'], request['solver_root'],
                                                        request['evaluator_root'], request['output_root'])
    seal, solver, pools = verify_seal(root, request['seal_sha256'], solver_root)
    # No evaluator-side file is opened before all above proof checks complete.
    manifest = validate_manifest(json.loads(read_regular(evaluator_root / 'manifest.json',
                                  seal['evaluator_manifest_sha256'])), role='evaluator')
    if manifest['identity'] != solver['identity'] or manifest['source'] != solver['manifest']['source']:
        raise ValueError('evaluator content differs from solver')
    verify_inventory(evaluator_root, manifest['files'], exclude=('manifest.json',))
    upstream = json.loads(read_regular(evaluator_root / 'upstream-inventory.json',
                                      manifest['source']['evaluation_inventory_sha256']))
    if manifest['evidence_mode'] == 'public-development':
        for name, expected in verify_upstream_inventory(upstream).items():
            if git_object_sha('blob', read_regular(evaluator_root / 'upstream' / name)) != expected:
                raise ValueError('official task blob differs')
    from tools.arc_offline_evaluation import load_pinned_reference, evaluate
    challenges, solutions, reference = load_pinned_reference(evaluator_root / 'upstream', evaluator_root / 'provenance.json')
    if challenges != solver['challenges']: raise ValueError('full challenge projection differs')
    reports = {name: evaluate(challenges, solutions, pool) for name, pool in pools.items()}
    del solutions
    verify_seal(root, request['seal_sha256'], solver_root)
    if any(k in sys.modules for k in ('torch', 'transformers', 'peft')):
        raise ValueError('neural modules forbidden in evaluator')
    result = json.loads(read_regular(root / 'solver-result.json'))
    labels = {'format': 'irisx/learning-public-evaluation-v1', 'status': 'SCORED',
              'measurement': 'project-public-development', 'official_score': None,
              'competition_gpu_equivalent': False, 'tasks': 120, 'tests': 167,
              'primary_target': 'micro pass@2 >= 0.50; at least 84 of 167',
              'secondary_metrics': ['task-macro pass@2', 'all-test task success'],
              'prediction_origin': seal['bindings']['prediction_origin'],
              'training_used': result['training_steps'] > 0,
              'training_steps': result['training_steps'], 'physical_usage': result['physical_usage'],
              'public_exposure': 'known public development; base pretraining exposure unknown',
              'prediction_seal_sha256': request['seal_sha256'],
              'scorer_sha256': SCORER_PINS['tools/arc_offline_evaluation.py'],
              'isolation': 'stopped owned processes and trusted code dataflow; not same-UID filesystem secrecy',
              'generation_may_resume': False}
    atomic_json(output / 'evaluator-detail.json', {**labels, 'reports': reports}, exclusive=True)
    summary = {**labels, 'policies': {p: r['development_metrics'] for p, r in reports.items()}}
    atomic_json(output / 'public-summary.json', summary, exclusive=True)


def evaluate_sealed(prediction_root, seal_sha256, *, solver_root, evaluator_root, output_root, deadline):
    root, solver, evaluator, output = separated(prediction_root, solver_root, evaluator_root, output_root)
    if output.exists(): raise ValueError('evaluation identity consumed; no generation resumes')
    verify_seal(root, seal_sha256, solver)
    remaining = min(60, deadline - time.monotonic())
    if remaining <= 0: return {'status': 'SCORING_NOT_ADMITTED', 'official_score': None}
    output.mkdir(parents=True)
    request = {'prediction_root': str(root), 'seal_sha256': seal_sha256,
               'solver_root': str(solver), 'evaluator_root': str(evaluator), 'output_root': str(output)}
    atomic_json(output / 'request.json', request, exclusive=True)
    with (output / 'stdout.txt').open('xb') as out, (output / 'stderr.txt').open('xb') as err:
        child = subprocess.Popen([sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve()),
                                  '--worker', str(output / 'request.json')], cwd=output, stdout=out, stderr=err,
            start_new_session=True, close_fds=True,
            env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'})
        try: child.wait(timeout=remaining)
        except BaseException:
            if child.poll() is None: os.killpg(child.pid, signal.SIGKILL)
            child.wait(); raise
    receipt = {'returncode': child.returncode, 'owned_process_stopped': child.poll() is not None,
               'prediction_seal_sha256': seal_sha256}
    atomic_json(output / 'process-receipt.json', receipt, exclusive=True)
    if child.returncode != 0: return {'status': 'SCORING_BLOCKED', **receipt}
    verify_seal(root, seal_sha256, solver)
    return json.loads(read_regular(output / 'public-summary.json'))


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--worker': raise SystemExit(2)
    try: _worker(json.loads(read_regular(sys.argv[2])))
    except Exception:
        sys.stderr.write('isolated evaluator rejected evidence; no score released\n')
        raise SystemExit(2)
