"""One-way sealed-prediction public-development evaluation in a fresh CPU process.

This authenticates trusted dataflow and current Linux process closure. It is not
same-UID filesystem isolation. No generation/model package is imported here.
The historical scorer and its 120/167 metric implementation remain unchanged.
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time

if __package__ in (None, ''):
    _root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(_root), str(_root / 'src')]

from tools.arc_kaggle_submission import parse_json, require
from tools.arc_public_research_20261010.public_data import (
    canonical, sha256, hash_value, hash_string, safe_path, read_regular, write_new, inventory,
    verify_inventory, load_solver_tasks, validate_manifest, separated, POLICIES, EXPOSURE,
    PROVENANCE_SHA256, LICENSE_SHA256, verify_upstream_inventory, git_object_sha)

ROOT = Path(__file__).resolve().parents[2]
SEAL_FORMAT = 'irisx/public120-prediction-seal-v1'
REPORT_FORMAT = 'irisx/public120-sealed-evaluation-v1'
SCORER_PINS = {
    'tools/arc_offline_evaluation.py': '3df3fd40c0a4db82dc6ad5c568102e45ad10efad8529412eae0623bd9f4ba016',
    'tools/arc_kaggle_submission.py': 'cdd570c99614d5eb326f9f07d86b36f80e4f5e53ec197370b5a0e03f262366bf',
    'src/irisx/arc_agi2.py': '0af942df40b76f208546a88864e84ddf521168bdb8f1fa4ce24232c36f3034a1',
    'tools/nvarc_native_multitask.py': '274cc5391ee45ee098cba4f002e31425d5bed88993c2b9319b0320c17a08fbdb',
    'tools/nvarc_native_solve_runtime.py': '56380d7c5fbb9219acfc846af275d6a334ed9460b6b6448e6feacf78be77b1c1',
    'src/irisx/__init__.py': '3ca8d59be8dae69d75bd92b279cdab54a5c411162d78544578f924264905702e',
    'src/irisx/artifacts.py': '28a7a48cbabd0f8556a1f976aebeaec3cc0824a380ab8bb4c12ba5cdfc762c95',
    'src/irisx/canonical.py': 'd2bacf5548440c865a64cb7cdfbbefcb995ec47e4e53ddfa4457964a83740a6a',
    'src/irisx/contracts.py': 'afb58a3fefe0c5482616d4cd219779c5bc9dacb30be44ea153ab85496b9af6b1',
    'src/irisx/errors.py': '45c10f3c10c958cb3cca97a26a3a0f79925ed5818ce591327d9ef1a851a6ffa4',
    'src/irisx/engine.py': 'bd08a6d9740d7696c6663410a450323c0c00cc5320bce184339ea4a98717d283',
    'src/irisx/bindings.py': 'cc0bb9698ab8803c3c951cd88d7c233661dd2a38c6f1066f7d86ac8be98f7601',
    'tools/__init__.py': 'f5ed985f7ed9e31ea3be113e86b11a7b44313f467c2e468a034ff789c7b85c76',
    'src/irisx/admission.py': '0520aa0b966ea7b2bd7f88330f6c3e0e407e428cf144458a1fda89317c38bb63',
}
LOCAL_SOURCE = ('tools/arc_public_research_20261010/public_data.py',
    'tools/arc_public_research_20261010/query_executor.py',
    'tools/arc_public_research_20261010/public_evaluator.py',
    'tools/arc_consolidated_20261010/__init__.py',
    'tools/arc_consolidated_20261010/arc_object_ir.py',
    'tools/arc_consolidated_20261010/assets.py', 'tools/arc_consolidated_20261010/verifier.py',
    'tools/arc_consolidated_20261010/legacy/arc_bounded_v2.py',
    'tools/arc_consolidated_20261010/legacy/arc_typed_ir.py')


def source_identity():
    """Scorer import closure plus the trusted selection/query bridge, all CPU-only."""
    paths = set(SCORER_PINS) | set(LOCAL_SOURCE)
    optional = ROOT / 'tools/arc_public_research_20261010/__init__.py'
    if optional.exists():
        paths.add(optional.relative_to(ROOT).as_posix())
    result = {name: sha256(read_regular(ROOT / name)) for name in sorted(paths)}
    require(all(result[k] == v for k, v in SCORER_PINS.items()), 'historical scorer source changed')
    return result


def _source_check(identity):
    required = source_identity()
    require(type(identity) is dict and set(required) <= set(identity) and len(identity) <= 1024,
            'complete scorer/selection source identity required')
    for name, value in identity.items():
        require(type(name) is str and not PurePosixPath(name).is_absolute() and '\\' not in name and
                all(part not in ('', '.', '..') for part in name.split('/')), 'unsafe source identity')
        read_regular(ROOT / name, hash_string(value))
    require(all(identity[k] == v for k, v in required.items()), 'source differs from sealed prediction source')


def _process(pid):
    require(type(pid) is int and pid > 0, 'valid process identifier required')
    try:
        body = (Path('/proc') / str(pid) / 'stat').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    parts = body[body.rfind(')') + 2:].split()
    return {'pid': pid, 'state': parts[0], 'ppid': int(parts[1]), 'group': int(parts[2]),
            'session': int(parts[3]), 'birth': int(parts[19])}


def _bound_document(ref):
    require(type(ref) is dict and set(ref) == {'path', 'sha256'}, 'bound owner evidence required')
    return parse_json(read_regular(ref['path'], ref['sha256']))


def verify_owner_proof(proof, bindings):
    """Require actual bound start/closure evidence, then inspect /proc afresh."""
    require(type(proof) is dict and proof.get('pending_reservations') == 0 and
            type(proof.get('pending_reservations')) is int, 'pending owner reservations block scoring')
    if proof.get('mode') == 'model-disabled':
        require(set(proof) == {'mode', 'model_disabled', 'physical_calls', 'pending_reservations'} and
                proof['model_disabled'] is True and type(proof['physical_calls']) is int and
                proof['physical_calls'] == 0 and bindings['prediction_origin'] in ('model_disabled', 'research_cpu', 'synthetic_cpu'),
                'disabled model cannot claim model/GPU execution')
        return
    require(set(proof) == {'mode', 'closure', 'request', 'start', 'pending_reservations', 'physical_calls'} and
            proof['mode'] == 'remote-owner' and type(proof['physical_calls']) is int and 0 <= proof['physical_calls'] <= 240,
            'owner proof schema differs')
    request_path, start_path = safe_path(proof['request']['path']), safe_path(proof['start']['path'])
    require(request_path.name == 'request.json' and start_path.name == 'worker-start.json' and
            request_path.parent == start_path.parent and request_path.parent.name.startswith('model-owner-'),
            'foreign owner evidence path roles')
    request, start, closed = _bound_document(proof['request']), _bound_document(proof['start']), proof['closure']
    require(request_path.parent.name == 'model-owner-' + request['nonce'], 'foreign owner evidence directory')
    required_model = {'tools/arc_public_research_20261010/remote_model_owner.py',
                      'tools/arc_public_research_20261010/model_provider.py',
                      'tools/arc_public_research_20261010/finite_trie.py'}
    require(required_model <= set(request['source_identity']), 'model process source closure incomplete')
    require(request.get('evidence_mode') == start.get('evidence_mode') and
            request['evidence_mode'] in ('production', 'synthetic-test-only') and
            (request['evidence_mode'] != 'synthetic-test-only' or bindings['prediction_origin'] == 'synthetic_cpu'),
            'synthetic process cannot establish production model execution')
    require(request['nonce'] == start['nonce'] and request['parent_pid'] == start['parent_pid'] and
            request['environment_plan_sha256'] == start['environment_plan_sha256'] == bindings['environment_plan_sha256'] and
            request['bootstrap']['actual_environment_lock_sha256'] == start['actual_environment_lock_sha256'] ==
            bindings['actual_environment_lock_sha256'], 'foreign owner start/environment evidence')
    require(request['source_identity'] and all(bindings['source_identity'].get(k) == v for k, v in request['source_identity'].items()) and
            start['source_identity_sha256'] == hash_value(request['source_identity']), 'foreign model source evidence')
    require(start['admission_sha256'] == request['bootstrap']['admission_sha256'], 'foreign owner admission')
    require(request['parent_pid'] in (os.getpid(), os.getppid()), 'owner evidence belongs to another coordinator')
    actual_parent = _process(request['parent_pid'])
    require(actual_parent is not None and actual_parent['birth'] == request['parent_identity']['birth'], 'owner parent incarnation differs')
    require(all(closed.get(k) is True for k in ('model_owner_stopped', 'model_released', 'owned_descendants_stopped')) and
            closed.get('owned_descendants') == [] and closed.get('environment_plan_sha256') == bindings['environment_plan_sha256'] and
            closed.get('actual_environment_lock_sha256') == bindings['actual_environment_lock_sha256'], 'owner closure differs')
    evidence = closed.get('process_evidence', {})
    require(evidence.get('process_stopped') is True and evidence.get('forced') is False and
            type(evidence.get('returncode')) is int and evidence['returncode'] == 0 and
            evidence.get('owned_descendants') == [] and evidence.get('owned_io_threads_stopped') is True and
            evidence.get('scope') == 'linux-owned-process-tree' and evidence.get('worker_pid') == start['worker_pid'],
            'crashed, forced, or unclosed owner blocks scoring')
    ack = closed.get('child_acknowledgement')
    require(type(ack) is dict and ack.get('model_owner_stopped') is True, 'graceful model close acknowledgement required')
    identities = evidence.get('observed_process_identities')
    require(type(identities) is list and identities and any(
            r.get('pid') == start['worker_identity']['pid'] and r.get('birth') == start['worker_identity']['birth']
            for r in identities), 'owner process birth records required')
    require(start['worker_identity']['pid'] == start['worker_pid'] and
            start['worker_identity']['session'] == start['worker_pid'], 'worker session identity differs')
    seen = set()
    for identity in identities:
        pid, birth = identity.get('pid'), identity.get('birth')
        require(type(pid) is int and type(birth) is int and (pid, birth) not in seen, 'invalid process birth record')
        seen.add((pid, birth))
        actual = _process(pid)
        require(actual is None or actual['birth'] != birth, 'owned process remains present')
    # Unknown descendants still in the worker's session cannot evade the list.
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            actual = _process(int(entry.name))
            require(actual is None or actual['session'] != start['worker_pid'], 'owned session remains present')


def _bindings(value):
    require(type(value) is dict and set(value) == {'run_id', 'source_identity', 'environment_plan_sha256',
            'actual_environment_lock_sha256', 'prediction_origin', 'model_sha256'}, 'prediction bindings schema differs')
    require(value['prediction_origin'] in ('research_gpu', 'research_cpu', 'model_disabled', 'synthetic_cpu'), 'explicit research origin required')
    for field in ('environment_plan_sha256', 'actual_environment_lock_sha256', 'model_sha256'):
        hash_string(value[field])
    _source_check(value['source_identity'])


def _pools(root, solver, bindings):
    from tools.arc_public_research_20261010.query_executor import build_policy_pool
    values = {}
    for policy in POLICIES:
        pool = parse_json(read_regular(root / ('pools-' + policy + '.json')))
        proof = parse_json(read_regular(root / ('prediction-proof-' + policy + '.json')))
        require(type(proof) is dict and set(proof) == {'selections', 'query_receipts'}, 'prediction proof schema differs')
        selection_path = safe_path(proof['selections']['path'])
        require(selection_path.parent == root and selection_path.name == 'selection-' + policy + '.json',
                'selection must be retained inside prediction seal')
        rebuilt = build_policy_pool(solver['challenges'], proof['selections'], proof['query_receipts'],
            run_id=bindings['run_id'], policy=policy, parent_wall_seconds=pool['parent_wall_seconds'])
        require(pool == rebuilt, 'pools differ from sealed demo-only selection/query receipts')
        values[policy] = pool
    return values


def seal_predictions(prediction_root, *, solver_root, solver_manifest_sha256,
                     evaluator_manifest_sha256, owner_proof, bindings):
    root, solver_root = separated(prediction_root, solver_root)
    require(not (root / 'prediction-seal.json').exists(), 'prediction seal already consumed')
    _bindings(bindings); hash_string(evaluator_manifest_sha256)
    solver = load_solver_tasks(solver_root, solver_manifest_sha256)
    verify_owner_proof(owner_proof, bindings)
    _pools(root, solver, bindings)
    seal = {'format': SEAL_FORMAT, 'phase': 'predictions-sealed-generation-closed',
            'bindings': bindings, 'solver_manifest_sha256': solver_manifest_sha256,
            'evaluator_manifest_sha256': evaluator_manifest_sha256, 'identity': solver['identity'],
            'owner_proof': owner_proof, 'files': inventory(root), 'sealed_at_ns': time.time_ns()}
    path = root / 'prediction-seal.json'
    written = write_new(path, seal)
    _verify_seal(root, written['sha256'], solver_root)
    return {'seal_sha256': written['sha256'], 'seal_path': str(path)}


def _verify_seal(root, seal_sha256, solver_root):
    root, solver_root = separated(root, solver_root)
    seal = parse_json(read_regular(root / 'prediction-seal.json', seal_sha256))
    require(type(seal) is dict and set(seal) == {'format', 'phase', 'bindings', 'solver_manifest_sha256',
            'evaluator_manifest_sha256', 'identity', 'owner_proof', 'files', 'sealed_at_ns'} and
            seal['format'] == SEAL_FORMAT and seal['phase'] == 'predictions-sealed-generation-closed' and
            type(seal['sealed_at_ns']) is int and seal['sealed_at_ns'] > 0, 'closed prediction seal required')
    _bindings(seal['bindings'])
    verify_inventory(root, seal['files'], exclude=('prediction-seal.json',))
    solver = load_solver_tasks(solver_root, seal['solver_manifest_sha256'])
    require(solver['identity'] == seal['identity'], 'sealed data/count bindings differ')
    if solver['manifest']['evidence_mode'] == 'synthetic-test-only':
        require(seal['bindings']['prediction_origin'] == 'synthetic_cpu', 'synthetic asset cannot claim GPU execution')
    else:
        require(seal['bindings']['prediction_origin'] != 'synthetic_cpu', 'synthetic run cannot score public assets')
    verify_owner_proof(seal['owner_proof'], seal['bindings'])
    return seal, solver, _pools(root, solver, seal['bindings'])


def _policy_prediction_origins(seal, evidence_mode):
    """Policy provenance follows sealed execution evidence, never object presence."""
    if evidence_mode == 'synthetic-test-only':
        return {policy: 'synthetic_cpu' for policy in POLICIES}
    proof = seal['owner_proof']
    model_ran = proof['mode'] == 'remote-owner' and proof['physical_calls'] > 0
    return {'raw': 'research_gpu' if model_ran else 'not_executed',
            'strict': 'research_gpu' if model_ran else 'not_executed',
            'uniform': 'research_cpu', 'shape': 'research_cpu'}


def _evaluate_worker(request):
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    root, solver_root, evaluator_root, output_root = separated(request['prediction_root'], request['solver_root'],
                                                             request['evaluator_root'], request['output_root'])
    seal, solver, pools = _verify_seal(root, request['seal_sha256'], solver_root)
    # First evaluator-side file open occurs only after complete seal/closure checks.
    manifest = validate_manifest(parse_json(read_regular(evaluator_root / 'manifest.json',
                                seal['evaluator_manifest_sha256'])), role='evaluator')
    require(manifest['identity'] == solver['identity'] and manifest['source'] == solver['manifest']['source'] and
            manifest['evidence_mode'] == solver['manifest']['evidence_mode'], 'solver/evaluator source bindings differ')
    verify_inventory(evaluator_root, manifest['files'], exclude=('manifest.json',))
    upstream = parse_json(read_regular(evaluator_root / 'upstream-inventory.json',
                                     manifest['source']['evaluation_inventory_sha256']))
    if manifest['evidence_mode'] == 'public-development':
        official_files = verify_upstream_inventory(upstream)
        for name, expected in official_files.items():
            require(git_object_sha('blob', read_regular(evaluator_root / 'upstream' / name)) == expected,
                    'official Git task blob differs')
    require(set(manifest['files']) == {'LICENSE', 'NOTICE', 'provenance.json', 'upstream-inventory.json'} |
            {'upstream/data/evaluation/' + k + '.json' for k in solver['challenges']}, 'evaluator file role inventory differs')
    from tools.arc_offline_evaluation import load_pinned_reference, evaluate
    challenges, solutions, reference = load_pinned_reference(evaluator_root / 'upstream', evaluator_root / 'provenance.json')
    require(challenges == solver['challenges'], 'full source demonstration/query projection differs')
    require(reference['provenance_sha256'] == manifest['source']['provenance_sha256'], 'reference provenance differs')
    reports = {policy: evaluate(challenges, solutions, pool) for policy, pool in pools.items()}
    del solutions
    _verify_seal(root, request['seal_sha256'], solver_root)
    verify_inventory(evaluator_root, manifest['files'], exclude=('manifest.json',))
    require(not any(name == 'torch' or name == 'transformers' or name.endswith('model_provider') for name in sys.modules),
            'model import forbidden in evaluator')
    labels = {'format': REPORT_FORMAT, 'status': 'SCORED', 'measurement': 'research-public-development',
              'profile': 'PUBLIC120', 'competition_gpu_equivalent': False, 'competition_gpu_output': False,
              'official_score': None, 'training_used': False, 'adapter_used': False, 'gpu_hardware_verified': False,
              'prediction_origin': seal['bindings']['prediction_origin'], 'evidence_mode': manifest['evidence_mode'],
              'policy_prediction_origins': _policy_prediction_origins(seal, manifest['evidence_mode']),
              'exposure': EXPOSURE, 'complete_official_pinned_set': manifest['complete_official_pinned_set'],
              'source_commit': manifest['source']['commit'], 'prediction_seal_sha256': request['seal_sha256'],
              'tasks': 120, 'queries': 167, 'scorer_sha256': SCORER_PINS['tools/arc_offline_evaluation.py'],
              'isolation': 'trusted fixed-code dataflow and stopped processes; no same-UID filesystem secrecy',
              'generation_may_resume': False}
    summary = {**labels, 'policies': {policy: result['development_metrics'] for policy, result in reports.items()}}
    write_new(output_root / 'evaluator-detail.json', {**labels, 'reports': reports})
    write_new(output_root / 'public-summary.json', summary)
    return summary


def evaluate_sealed(prediction_root, seal_sha256, *, solver_root, evaluator_root, output_root):
    """Never returns per-query correctness to the coordinator. One-shot CPU entry."""
    root, solver_root, evaluator_root, output_root = separated(prediction_root, solver_root, evaluator_root, output_root)
    require(not output_root.exists(), 'evaluator output identity consumed; no retry/resume')
    # Do not inspect evaluator files in the generation/coordinator process.
    _verify_seal(root, seal_sha256, solver_root)
    output_root.mkdir(parents=True)
    request = {'prediction_root': str(root), 'seal_sha256': seal_sha256, 'solver_root': str(solver_root),
               'evaluator_root': str(evaluator_root), 'output_root': str(output_root)}
    write_new(output_root / 'evaluation-request.json', request)
    began = time.monotonic()
    with (output_root / 'worker-stdout.txt').open('xb') as out, (output_root / 'worker-stderr.txt').open('xb') as err:
        child = subprocess.Popen([sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve()), '--worker',
                                  str(output_root / 'evaluation-request.json')], stdout=out, stderr=err,
            cwd=output_root, start_new_session=True, close_fds=True,
            env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'})
        try:
            child.wait(timeout=45)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(child.pid, signal.SIGKILL); child.wait()
        except BaseException:
            import signal
            os.killpg(child.pid, signal.SIGKILL); child.wait(); raise
    receipt = {'cpu_subprocess_returncode': child.returncode, 'cpu_subprocess_stopped': True,
               'wall_seconds': time.monotonic() - began, 'prediction_seal_sha256': seal_sha256}
    if child.returncode != 0:
        result = {'format': REPORT_FORMAT, 'status': 'SCORING_BLOCKED', 'official_score': None,
                  'reason': 'CPU evaluator rejected evidence or failed; no score reported', **receipt}
        write_new(output_root / 'scoring-blocked.json', result)
        return result
    _verify_seal(root, seal_sha256, solver_root)
    summary = parse_json(read_regular(output_root / 'public-summary.json'))
    require(summary['prediction_seal_sha256'] == seal_sha256 and summary['status'] == 'SCORED', 'foreign evaluation result')
    write_new(output_root / 'subprocess-receipt.json', receipt)
    return {**summary, 'subprocess': receipt}


if __name__ == '__main__':
    require(len(sys.argv) == 3 and sys.argv[1] == '--worker', 'private evaluator worker entry only')
    try:
        _evaluate_worker(parse_json(read_regular(sys.argv[2])))
    except Exception:
        # Never let an exception interpolate evaluator data into notebook logs.
        sys.stderr.write('sealed CPU evaluation rejected; no score released\n')
        raise SystemExit(2)
