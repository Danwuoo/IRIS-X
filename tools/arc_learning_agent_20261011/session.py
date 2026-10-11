"""Default-inert one-session supervisor, stopped-owner seals, isolated scoring."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
import zipfile

from tools.arc_learning_agent_20261011.budget import SessionClock, atomic_json, canonical, digest
from tools.arc_learning_agent_20261011.evaluation import (
    process_identity, session_members, source_identity, seal_predictions, evaluate_sealed)
from tools.arc_public_research_20261010 import public_data
from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard

ROOT = Path(__file__).resolve().parents[2]


def _path_guard(output, inputs):
    output = Path(output).absolute()
    values = [output, ROOT, *(Path(p).absolute() for p in inputs)]
    for path in values:
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('symlink root forbidden')
    for path in values[1:]:
        if output == path or output.is_relative_to(path) or path.is_relative_to(output):
            raise ValueError('output/source/input overlap')
    if output.exists(): raise ValueError('fresh output root required; checkpoint reuse is explicit only')
    return output


def _kill_owned(child, identity):
    if identity is None: raise RuntimeError('cannot stop unknown process incarnation')
    current = process_identity(child.pid)
    if current and current['birth'] != identity['birth']:
        raise RuntimeError('worker PID was reused')
    if current or session_members(identity['session']):
        try: os.killpg(identity['session'], signal.SIGTERM)
        except ProcessLookupError: pass
    try: child.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try: os.killpg(identity['session'], signal.SIGKILL)
        except ProcessLookupError: pass
        child.wait(timeout=10)
    for member in session_members(identity['session']):
        # Children retain the dedicated session; only that owned session is signalled.
        try: os.kill(member['pid'], signal.SIGKILL)
        except ProcessLookupError: pass
    return session_members(identity['session'])


def _controls(root, deadline):
    from tools.arc_consolidated_20261010.controls import synthetic_controls
    from tools.arc_consolidated_20261010.arc_object_ir import compile_plan
    from tools.arc_consolidated_20261010.verifier import verify
    rows = []
    for i, control in enumerate(synthetic_controls()):
        remaining = min(3.0, deadline - time.monotonic())
        if remaining <= 0: raise TimeoutError('independent controls deadline')
        atomic_json(root / ('control-%03d-reserved.json' % i), {'gas': 200000, 'timeout': remaining}, exclusive=True)
        result = verify(compile_plan(control['plan']), control['task'], timeout=remaining)
        # Never forge a successful control from mocked or unexecuted results.
        passed = result.get('known') is True and result.get('dispatched') is True and \
                 result.get('owned_descendants_stopped') is True and result.get('status') == control['expected_status']
        rows.append({'control_id': control['control_id'], 'passed': passed, 'result': result})
    receipt = {'total': len(rows), 'expected': 128, 'passed': len(rows) == 128 and all(r['passed'] for r in rows),
               'rows': rows, 'gas': sum(r['result'].get('gas_charged', 0) for r in rows)}
    atomic_json(root / 'controls.json', receipt, exclusive=True)
    if not receipt['passed']: raise ValueError('independent controls failed')
    return receipt


def run_session(output_root, *, solver_root, evaluator_root, solver_manifest_sha256,
                evaluator_manifest_sha256, training_root, enable_model=False,
                bootstrap_config=None, config=None, started_epoch=None):
    """CPU preflight is explicit. Model work requires exact enable_model=True.

    Full model lifecycle is in one owned subprocess. The coordinator never opens
    public answer files, and evaluates only a gracefully stopped, sealed owner.
    """
    if type(enable_model) is not bool: raise ValueError('exact model Boolean required')
    if not sys.platform.startswith('linux'): raise ValueError('Linux isolation is required')
    config = {} if config is None else dict(config)
    allowed = {'session_seconds', 'seed', 'predispatch_clock', 'tiny_cpu', 'validation_mode',
               'python_executable', 'model', 'fixture_tasks', 'max_new_tokens', 'dev_tasks',
               'rollout_tasks', 'global_steps'}
    if set(config) - allowed: raise ValueError('unknown session configuration')
    for name, maximum in (('seed', 2**31-1), ('fixture_tasks', 120), ('max_new_tokens', 2048),
                          ('dev_tasks', 4), ('rollout_tasks', 32), ('global_steps', 4096)):
        if name in config and (type(config[name]) is not int or not 0 <= config[name] <= maximum):
            raise ValueError('invalid bounded configuration: ' + name)
    for name in ('tiny_cpu', 'validation_mode', 'predispatch_clock'):
        if name in config and type(config[name]) is not bool: raise ValueError('exact Boolean ' + name + ' required')
    if not config.get('tiny_cpu') and config.get('session_seconds', 43200) != 43200:
        raise ValueError('production stage envelope is frozen at maximum43200 seconds')
    if config.get('tiny_cpu') and config.get('validation_mode') is not True:
        raise ValueError('tiny CPU is explicit validation only')
    input_roots = [solver_root, evaluator_root, training_root]
    if bootstrap_config:
        input_roots.append(bootstrap_config.get('input_root', '/kaggle/input'))
        input_roots.extend(p for p in bootstrap_config.get('explicit_roots', {}).values() if p)
    root = _path_guard(output_root, input_roots); root.mkdir(parents=True)
    run_id = 'learning-' + uuid.uuid4().hex
    clock = SessionClock.create(root / 'session-clock.json', run_id,
        maximum_seconds=config.get('session_seconds', 43200), started_epoch=started_epoch,
        origin='pre-dispatch' if config.get('predispatch_clock') else 'first-active-cell')
    source = source_identity()
    admission = {'run_id': run_id, 'source_identity': source, 'enable_model': enable_model,
                 'solver_manifest_sha256': solver_manifest_sha256,
                 'evaluator_manifest_sha256': evaluator_manifest_sha256,
                 'clock': clock.record, 'config': config, 'status': 'preflight'}
    atomic_json(root / 'admission.json', admission, exclusive=True)
    solver = public_data.load_solver_tasks(solver_root, solver_manifest_sha256)
    if solver['manifest']['evidence_mode'] == 'public-development' and config.get('tiny_cpu'):
        raise ValueError('random tiny model cannot be attributed to public production run')
    preflight = root / 'preflight'; preflight.mkdir()
    if not config.get('tiny_cpu'):
        from tools.arc_learning_agent_20261011.data import load_official_training
        _, training_receipt = load_official_training(training_root,
            ROOT / 'research/arc-next-line/training-source-inventory.json',
            protected_ids=sorted(solver['challenges']))
        atomic_json(preflight / 'training-source.json', training_receipt, exclusive=True)
    controls = _controls(preflight, clock.deadline(reserve=3600, maximum=600))
    if not enable_model:
        receipt = {'status': 'PREFLIGHT_ONLY', 'run_id': run_id, 'model_calls': 0,
                   'training_steps': 0, 'controls_passed': controls['passed'], 'scoring_started': False,
                   'source_identity_sha256': digest(source), 'gpu_runtime_verified': False}
        atomic_json(root / 'summary.json', receipt, exclusive=True)
        return receipt
    prepared = None
    interpreter = sys.executable
    model_config = dict(config.get('model', {}))
    if model_config.get('adapter_path') is not None:
        raise ValueError('fresh clean base required; unbound historical adapter forbidden')
    if config.get('tiny_cpu'):
        model_config.update(tiny_cpu=True)
        interpreter = config.get('python_executable', sys.executable)
    else:
        from tools.arc_public_research_20261010.offline_bootstrap import plan_config, prepare_model_environment
        plan = plan_config(bootstrap_config, root / 'environment')
        gate = {'passed': True, 'profile': 'PUBLIC120', 'gate': 'public_research_contracts',
                'controls': {'total': 128, 'expected': 128}, 'tasks': 120, 'tests': 167,
                'solver_manifest_sha256': solver_manifest_sha256,
                'evaluator_manifest_sha256': evaluator_manifest_sha256}
        start = time.monotonic()
        prepared = prepare_model_environment(plan, enable_model=True, gate_receipt=gate,
            deadline_seconds=max(0.001, min(1800 - (time.time() - clock.record['started_epoch']), clock.remaining(reserve=3600))))
        atomic_json(root / 'bootstrap-receipt.json', prepared, exclusive=True)
        interpreter = prepared['python_command']
        if not isinstance(interpreter, list) or not interpreter:
            raise ValueError('verified interpreter command required')
        model_config.update(enabled=True, model_path=prepared['model_path'],
                            model_manifest_path=prepared['manifest_path'],
                            environment_lock_path=prepared['environment_lock_path'])
    worker_root = root / 'worker'; worker_root.mkdir()
    request = {'format': 'irisx/learning-owner-request-v1', 'run_id': run_id,
               'output_root': str(worker_root), 'source_identity': source,
               'solver_root': str(Path(solver_root).absolute()), 'solver_manifest_sha256': solver_manifest_sha256,
               'training_root': str(Path(training_root).absolute()), 'model_config': model_config,
               'config': config, 'clock': clock.record, 'parent_bootstrap_seconds': time.time() - clock.record['started_epoch'], 'controls': {'checks': 128, 'gas': controls['gas']}}
    atomic_json(worker_root / 'request.json', request, exclusive=True)
    request_sha = hashlib.sha256((worker_root / 'request.json').read_bytes()).hexdigest()
    worker_identity = None; child = None; forced = False
    with (worker_root / 'stdout.txt').open('xb') as out, (worker_root / 'stderr.txt').open('xb') as err:
        guard = OwnedProcessGuard.spawn([*(interpreter if isinstance(interpreter, list) else [interpreter]), '-I', '-B', str(Path(__file__).with_name('worker.py')),
                                  str(worker_root / 'request.json'), request_sha], evidence_dir=worker_root / 'process-guard', cwd=worker_root,
            stdout=out, stderr=err, start_new_session=True, close_fds=True,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'HF_HUB_OFFLINE': '1',
                 'TRANSFORMERS_OFFLINE': '1', **({'CUDA_VISIBLE_DEVICES': ''} if config.get('tiny_cpu') else {})})
        child = guard.child
        worker_identity = guard.identity
        atomic_json(root / 'owner-start.json', {'worker_identity': worker_identity,
                    'parent_identity': process_identity(os.getpid()), 'request_sha256': request_sha}, exclusive=True)
        try:
            while guard.poll() is None:
                if clock.remaining(reserve=3600) <= 0:
                    raise subprocess.TimeoutExpired('owner session', 0)
                marker = worker_root / 'active-stage.json'
                if marker.exists():
                    state = json.loads(public_data.read_regular(marker, limit=65536))
                    if state.get('session_id') != run_id:
                        raise ValueError('foreign stage watchdog marker')
                    if state.get('status') == 'active' and time.monotonic() > state['deadline_monotonic']:
                        raise subprocess.TimeoutExpired('owner stage ' + state['stage'], 0)
                call_marker = worker_root / 'active-call.json'
                if call_marker.exists():
                    call_state = json.loads(public_data.read_regular(call_marker, limit=65536))
                    if call_state.get('status') == 'active' and time.monotonic() > call_state['deadline_monotonic']:
                        raise subprocess.TimeoutExpired('owner neural call', 0)
                time.sleep(0.2)
        except subprocess.TimeoutExpired:
            forced = True; guard.stop(timeout=10)
        except BaseException:
            guard.stop(timeout=10); raise
    process_proof = guard.closed_proof()
    members = process_proof['remaining']
    if members or process_proof.get('ownership_complete') is not True:
        forced = True
        process_proof = guard.stop(timeout=10)
        members = process_proof['remaining']
    result_path = worker_root / 'result.json'
    closure = {'format': 'irisx/learning-owner-closure-v1', 'worker_identity': worker_identity,
               'returncode': child.returncode, 'graceful': child.returncode == 0 and not forced and process_proof.get('closed') is True and process_proof.get('worker_returncode') == 0 and process_proof.get('returncode') == 0 and process_proof.get('forced') is False,
               'process_tree_proof': process_proof,
               'source_identity_sha256': digest(source), 'request_sha256': request_sha,
               'result_sha256': hashlib.sha256(result_path.read_bytes()).hexdigest() if result_path.exists() else None,
               'session_members': members, 'parent_identity': process_identity(os.getpid())}
    atomic_json(root / 'owner-closure.json', closure, exclusive=True)
    if not closure['graceful'] or members or not result_path.exists():
        receipt = {'status': 'OWNER_FAILED', 'run_id': run_id, 'closure': closure,
                   'score': None, 'may_resume_generation_after_seal': False}
        atomic_json(root / 'summary.json', receipt, exclusive=True); return receipt
    result = json.loads(result_path.read_bytes())
    seal = seal_predictions(root / 'predictions', solver_root=solver_root,
        solver_manifest_sha256=solver_manifest_sha256, evaluator_manifest_sha256=evaluator_manifest_sha256,
        result_path=result_path, closure=closure,
        bindings={'prediction_origin': result['prediction_origin'], 'run_id': run_id})
    scored = evaluate_sealed(root / 'predictions', seal['sha256'], solver_root=solver_root,
        evaluator_root=evaluator_root, output_root=root / 'evaluation', deadline=clock.deadline(reserve=1800, maximum=60))
    summary = {'status': ('COMPLETE' if result['status'] == 'complete' else 'PARTIAL_SCORED') if scored.get('status') == 'SCORED' else 'SCORING_BLOCKED',
               'run_id': run_id, 'solver_status': result['status'], 'prediction_seal': seal,
               'score_status': scored.get('status'), 'physical_usage': result['physical_usage'],
               'training_steps': result['training_steps'], 'model_stopped': True,
               'clock': clock.record, 'remaining_seconds': clock.remaining(),
               'competition_gpu_equivalent': False}
    atomic_json(root / 'summary.json', summary, exclusive=True)
    from tools.arc_learning_agent_20261011.export import export_evidence
    exported = export_evidence(root, run_id=run_id, deadline=clock.deadline(maximum=900))
    return {**summary, 'export': exported}
