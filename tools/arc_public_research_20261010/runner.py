"""Bounded PUBLIC120 research coordinator. No answer bytes enter this process.

The callable is CPU-only by default; the CLI additionally requires --manual-start.
Partial runs never redispatch on resume. Tests have a separate synthetic-only
entry point; production has no provider, worker, command or candidate override.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import uuid
import zipfile

if __package__ in (None, ''):
    _root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(_root), str(_root / 'src')]

from tools.arc_consolidated_20261010 import assets, arc_object_ir as ir, evidence, verifier
from tools.arc_consolidated_20261010.controls import synthetic_controls
from tools.arc_consolidated_20261010.ledger import Ledger, BudgetExceeded, BindingMismatch, digest
from tools.arc_consolidated_20261010.path_guard import guard_paths, environment_path, normalized_path
from tools.arc_public_research_20261010 import public_data as data, public_evaluator as evaluator
from tools.arc_public_research_20261010 import query_executor as query, ranking, model_provider as mp
from tools.arc_kaggle_submission import parse_json, require

ROOT = Path(__file__).resolve().parents[2]
PROFILE = 'PUBLIC120'
FORMAT = 'irisx/public120-research-run-v1'
CONTROLS_SHA256 = '4c1b631ee7090d24caf7b4da976cd6f81c4c273e8b59070802a8cbbacb479608'
TASKS, TESTS, CONTROLS, RANK_CHECKS, MODEL_CALLS, QUERY_CHECKS = 120, 167, 128, 15360, 240, 1336
CPU_CHECKS, SESSION_SECONDS, CLEANUP_SECONDS, WORKERS = 17064, 7200, 120, 4
TRANSPORT_FIELDS = {'dispatched', 'gas_reserved', 'owned_descendants_stopped', 'gas_charged',
                    'wall_reserved_seconds', 'wall_seconds'}


def limits_for():
    return {'physical_calls': MODEL_CALLS, 'cpu_checks': CPU_CHECKS,
            'coverage_checks': CONTROLS + RANK_CHECKS, 'model_checks': MODEL_CALLS,
            'search_checks': QUERY_CHECKS, 'unknown_verifications': CPU_CHECKS,
            'unknown_model_calls': MODEL_CALLS, 'gas': CPU_CHECKS * verifier.MAX_STEPS,
            'prompt_tokens': MODEL_CALLS * 6144, 'output_tokens': MODEL_CALLS * 2048,
            'model_seconds': MODEL_CALLS * 120, 'verifier_seconds': CPU_CHECKS * 3,
            'load_seconds': SESSION_SECONDS, 'archive_seconds': CLEANUP_SECONDS,
            'wall_seconds': SESSION_SECONDS, 'unknown_calls': CPU_CHECKS + MODEL_CALLS + 16}


def source_identity():
    """Complete production source closure, including historical CPU scorer."""
    result = assets.executable_identity()
    result.update(evaluator.source_identity())
    for path in sorted(Path(__file__).parent.glob('*.py')):
        if path.name not in ('build_notebook.py', 'source_pack.py'):
            result[path.relative_to(ROOT).as_posix()] = data.sha256(data.read_regular(path))
    return dict(sorted(result.items()))



def _entry_provenance(value, full_source, solver_sha, evaluator_sha):
    """Authenticate the exact notebook transport declaration, or explicit CLI mode."""
    identity_sha = digest(full_source)
    if value is None:
        return {'format': 'irisx/public120-direct-source-admission-v1',
                'source_transport_mode': 'direct-source', 'source_identity_sha256': identity_sha,
                'solver_manifest_sha256': solver_sha, 'evaluator_manifest_sha256': evaluator_sha}
    required = {'format', 'code_reference', 'code_manifest_sha256', 'source_archive_sha256',
                'source_identity_sha256', 'source_transport_mode', 'source_archive_bytes_verified',
                'data_reference', 'data_material_manifest_sha256', 'solver_manifest_sha256',
                'evaluator_manifest_sha256'}
    require(type(value) is dict and set(value) == required, 'entry provenance exact schema required')
    require(value['format'] == 'irisx/public120-notebook-source-admission-v1' and
            value['code_reference'] == 'danielwuu/iris-x-public120-code-20261010/1' and
            value['data_reference'] == 'danielwuu/iris-x-public120-data-20261010/1',
            'entry provenance format or frozen Dataset references differ')
    for key in ('code_manifest_sha256', 'source_archive_sha256', 'source_identity_sha256',
                'data_material_manifest_sha256', 'solver_manifest_sha256', 'evaluator_manifest_sha256'):
        data.hash_string(value[key])
    mode = value['source_transport_mode']
    require(mode in ('verified-archive', 'verified-extracted-source-root',
                     'verified-extracted-source-directory') and
            type(value['source_archive_bytes_verified']) is bool and
            value['source_archive_bytes_verified'] is (mode == 'verified-archive'),
            'entry provenance transport/archive verification declaration differs')
    require(value['source_identity_sha256'] == identity_sha and
            value['solver_manifest_sha256'] == solver_sha and value['evaluator_manifest_sha256'] == evaluator_sha,
            'entry provenance source or data role binding differs')
    return dict(value)

def _cpu_environment():
    executable = Path(sys.executable).resolve()
    return {'format': 'irisx/public120-cpu-environment-v1', 'python_version': sys.version,
            'python_executable': str(executable),
            'python_executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
            'platform': platform.platform(), 'verifier_limits': verifier.known_limits(),
            'vm_pins': verifier.ASSET_PINS,
            'offline_environment': {k: os.environ.get(k) for k in
                ('PYTHONHASHSEED', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_DATASETS_OFFLINE')}}


def _stream_archive(root, *, stopped, summary, session_id, deadline_monotonic):
    """Same stopped-owner snapshot semantics, bounded to one 1 MiB copy buffer.

    Rank receipts are intentionally complete (hundreds of MiB in aggregate).
    Never keep their bytes in a list as the historical small-run archiver did.
    The ledger's subsequent archive completion is outside this journal prefix.
    """
    require(set(stopped) == {'model_owner_stopped', 'verifier_descendants_stopped'} and
            all(v is True for v in stopped.values()), 'global archive requires verified process closure')
    began = time.monotonic()
    archives = root / 'archives'; archives.mkdir(exist_ok=True)
    final = archives / ('evidence-' + session_id + '.zip')
    partial = final.with_suffix('.zip.partial')
    require(not final.exists() and not partial.exists(), 'archive identity already consumed')
    inventory = {}
    def deadline():
        require(time.monotonic() < deadline_monotonic, 'archive session deadline reached')
    with partial.open('xb') as output:
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
            for path in sorted(root.rglob('*')):
                deadline(); data.safe_path(path)
                if not path.is_file() or archives in path.parents or path.name.endswith(('.partial', '.lock')):
                    continue
                name = path.relative_to(root).as_posix()
                before = path.stat(); sha = hashlib.sha256(); count = 0
                with path.open('rb') as incoming, archive.open(name, 'w') as member:
                    while block := incoming.read(1024 * 1024):
                        deadline(); member.write(block); sha.update(block); count += len(block)
                after = path.stat()
                require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) and count == before.st_size,
                        'archive source changed while streaming')
                inventory[name] = {'sha256': sha.hexdigest(), 'bytes': count}
            seal = {'format': 'irisx/consolidated-global-seal-v1', 'session_id': session_id,
                'processes': stopped, 'files': inventory, 'summary': summary,
                'directory_fsync_supported': os.name == 'posix',
                'scope': 'immutable snapshot; archive completion accounting appended outside this snapshot',
                'billing': 'Program return does not stop VM billing'}
            archive.writestr('global-seal.json', data.canonical(seal) + b'\n')
        output.flush(); os.fsync(output.fileno())
    # Read every decompressed member back before publishing the archive name.
    with zipfile.ZipFile(partial) as archive:
        require(set(archive.namelist()) == set(inventory) | {'global-seal.json'}, 'archive member inventory differs')
        for name, expected in inventory.items():
            sha, count = hashlib.sha256(), 0
            with archive.open(name) as member:
                while block := member.read(1024 * 1024):
                    deadline(); sha.update(block); count += len(block)
            require(sha.hexdigest() == expected['sha256'] and count == expected['bytes'], 'archive readback differs')
        require(archive.read('global-seal.json') == data.canonical(seal) + b'\n', 'archive seal readback differs')
    sha = hashlib.sha256()
    with partial.open('rb') as incoming:
        while block := incoming.read(1024 * 1024):
            deadline(); sha.update(block)
    os.rename(partial, final); evidence.fsync_directory(archives)
    return {'archive': str(final), 'sha256': sha.hexdigest(), 'seconds': time.monotonic() - began,
            'files': len(inventory), 'directory_fsync_supported': os.name == 'posix',
            'streaming_buffer_bytes': 1024 * 1024}


def _error(exc):
    return {'type': type(exc).__name__, 'message': str(exc)[:1000]}


def _admit(ledger, seconds=3):
    if ledger.remaining_wall_seconds <= CLEANUP_SECONDS + seconds:
        raise BudgetExceeded('session admission stopped to preserve 120-second cleanup/scoring reserve')


def _compact(ledger):
    value = ledger.summary()
    value.pop('operations')
    return value


def _unknown(reason):
    return {'status': 'missing', 'reason': reason, 'known': False, 'all_demos_fit': False}


def _pending(ledger):
    return sum(op['status'] not in ('complete', 'fail') for op in ledger.summary()['operations'].values()
               if op['kind'] in ('model', 'cpu') or op.get('metadata', {}).get('owner_resource'))


def _scoring_admission(ledger):
    snapshot = ledger.summary()
    require(snapshot['reservation_overrun'] is False and snapshot['state'] != 'fail',
            'observed accounting overrun/failure prohibits prediction sealing and scoring')
    require(_pending(ledger) == 0, 'unresolved physical reservations prohibit scoring')
    require(ledger.remaining_wall_seconds > 50, 'insufficient reserved scoring time')


class FreshVerifier:
    """Ordered, controller-reserved physical calls, never a task/plan cache."""
    def __init__(self, ledger, verify_fn=None):
        self.ledger = ledger
        self.verify_fn = verify_fn or verifier.verify
        self.all_stopped = True
        self.workers_used = 0
        self.stop_reason = None

    def _prepare(self, job):
        _admit(self.ledger)
        require(self.all_stopped, 'unclosed CPU operation prohibits further dispatch')
        ident = 'cpu/' + job['call_id']
        require(self.ledger.operation(ident) is None, 'fresh physical check identity already consumed')
        source = ir.compile_plan(job['plan'])
        request = verifier._validate_request(source, job['task'], 3.0, verifier.MAX_STEPS)
        scope = job.get('scope', 'coverage')
        require(scope in ('coverage', 'model'), 'invalid demos verification scope')
        self.ledger.reserve('cpu', ident, {'cpu_checks': 1, scope + '_checks': 1,
            'gas': verifier.MAX_STEPS, 'unknown_verifications': 1, 'verifier_seconds': 3.0},
            metadata={'request_sha256': verifier._digest(request), 'scope': scope,
                      'fresh_physical': True, 'candidate_id': ir.digest(job['plan']),
                      'ranking_seal_sha256': job.get('ranking_seal_sha256')})
        return ident, source, request

    def _finish(self, work, value):
        ident, source, request = work
        require(type(value) is dict and TRANSPORT_FIELDS <= set(value), 'bounded verifier transport receipt required')
        if value.get('known') is True:
            verifier._validate_receipt({k: v for k, v in value.items() if k not in TRANSPORT_FIELDS}, request)
        self.all_stopped &= value.get('owned_descendants_stopped') is True
        self.ledger.record_response(ident, value)
        usage = {'verifier_seconds': value['wall_seconds']}
        if value.get('known') is True:
            usage.update(gas=value['gas_charged'], unknown_verifications=0)
        self.ledger.finish(ident, usage, outcome='complete' if value.get('known') else 'fail')
        return value

    def batch(self, jobs):
        """Retain every requested row, including undispatched and unknown checks."""
        jobs = list(jobs)
        rows = []
        with ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix='public120-cpu') as executor:
            for offset in range(0, len(jobs), WORKERS):
                window = []
                for job in jobs[offset:offset + WORKERS]:
                    if self.stop_reason:
                        window.append((job, None, None, _unknown(self.stop_reason)))
                        continue
                    try:
                        work = self._prepare(job)
                        future = executor.submit(self.verify_fn, work[1], job['task'],
                                                 timeout=3.0, max_steps=verifier.MAX_STEPS)
                        window.append((job, work, future, None))
                    except Exception as exc:
                        self.stop_reason = type(exc).__name__ + ': ' + str(exc)[:300]
                        window.append((job, None, None, _unknown(self.stop_reason)))
                self.workers_used = max(self.workers_used, sum(w[2] is not None for w in window))
                for job, work, future, missing in window:
                    value = missing
                    if future is not None:
                        try:
                            value = self._finish(work, future.result())
                        except BaseException as exc:
                            self.all_stopped = False
                            self.stop_reason = 'unresolved verifier reservation: ' + type(exc).__name__
                            value = {'status': 'unknown', 'known': False, 'all_demos_fit': False,
                                     'reason': self.stop_reason}
                    rows.append({'call_id': job['call_id'], 'candidate_id': ir.digest(job['plan']),
                                 'verification': value})
        return rows


def _base_pool():
    plans = ir.base_inventory()
    require(len(plans) == ranking.INVENTORY_COUNT and ir.digest(plans) == ranking.INVENTORY_SHA256,
            'frozen 5965-plan inventory changed')
    return [{'candidate_id': ir.digest(plan), 'plan': plan, 'origin': 'base',
             'source_sha256': data.sha256(ir.compile_plan(plan).encode())} for plan in plans]


def _controls(checked, root):
    controls = synthetic_controls()
    require(len(controls) == CONTROLS and digest(controls) == CONTROLS_SHA256,
            'independent 128-control definition changed')
    rows = checked.batch([{'call_id': 'control-%03d' % i, 'task': c['task'], 'plan': c['plan']}
                          for i, c in enumerate(controls)])
    for row, control in zip(rows, controls):
        row.update(control_id=control['control_id'], expected_status=control['expected_status'],
                   passed=row['verification'].get('known') is True and
                          row['verification'].get('dispatched') is True and
                          row['verification'].get('owned_descendants_stopped') is True and
                          row['verification']['status'] == control['expected_status'])
    report = {'total': CONTROLS, 'expected': CONTROLS, 'passed': all(r['passed'] for r in rows),
              'rows': rows, 'definition_sha256': CONTROLS_SHA256}
    data.write_new(root / 'controls.json', report)
    return report


def _seal_rankings(tasks, pool, root, ledger, rank_fn=None):
    rank_fn = rank_fn or ranking.rank_candidates
    orders, files = {}, {}
    candidate_ids = {row['candidate_id'] for row in pool}
    for policy, method in (('uniform', 'uniform'), ('shape', 'shape_palette_v1')):
        orders[policy] = {}
        for key, task in sorted(tasks.items()):
            _admit(ledger)
            record = rank_fn(task, pool, seed=0, method=method, budget=64)
            require(record['method'] == method and record['task_id'] == key and
                    record['budget'] == 64 and len(record['full_order']) == 5965 and
                    set(record['full_order']) == candidate_ids and
                    record['selected_candidate_ids'] == record['full_order'][:64] and
                    record['excluded_candidate_ids'] == [], 'frozen support/order contract differs')
            name = policy + '-' + key + '.json'
            files[name] = data.write_new(root / 'rankings' / name, record)
            orders[policy][key] = record['selected_candidate_ids']
    seal = {'format': 'irisx/public120-rankings-seal-v1', 'policy': ranking.policy_config(),
            'ranker_source_sha256': data.sha256(data.read_regular(Path(ranking.__file__).resolve())),
            'files': files, 'task_count': TASKS, 'physical_checks': 0,
            'sealed_at_ns': time.time_ns()}
    binding = data.write_new(root / 'rankings-seal.json', seal)
    # No ranking verifier has been invoked until the complete seal is durable.
    return orders, binding['sha256']


def _fresh_candidates(rows, pool_by_id, run_id, maximum):
    """First fitted distinct plans in original physical verification order."""
    result, seen = [], set()
    for row in rows:
        value = row['verification']
        cid = row['candidate_id']
        if (value.get('status') == 'fit' and value.get('known') is True and
                value.get('all_demos_fit') is True and value.get('dispatched') is True and
                value.get('owned_descendants_stopped') is True and cid not in seen):
            result.append({'candidate_id': cid, 'run_id': run_id, 'plan': pool_by_id[cid]['plan'],
                           'verification': value, 'fit_call_id': row['call_id'],
                           'fit_receipt_sha256': data.sha256(data.canonical(value) + b'\n')})
            seen.add(cid)
            if len(result) == maximum:
                break
    return result


def _bootstrap(plan, gate, ledger, root, owner_source):
    from tools.arc_public_research_20261010 import offline_bootstrap
    _admit(ledger)
    allowance = ledger.remaining_wall_seconds - CLEANUP_SECONDS - 5
    ledger.reserve('overhead', 'bootstrap', {'load_seconds': allowance},
                   metadata={'environment_plan_sha256': plan['plan_sha256'], 'owner_resource': True})
    began = time.monotonic()
    try:
        result = offline_bootstrap.prepare_model_environment(plan, enable_model=True,
            gate_receipt=gate, deadline_seconds=allowance)
        proof = result.get('child_stop_proof', {})
        require(result.get('status') == 'prepared' and set(proof) == {'material', 'install'} and all(
            p.get('owned_group_stopped') is True and p.get('leader_reaped') is True and
            p.get('live_group_members') == 0 for p in proof.values()), 'bootstrap child stop evidence missing')
        require(result['environment_plan_sha256'] == plan['plan_sha256'], 'bootstrap plan binding changed')
        ready = {k: result[k] for k in ('python_command', 'source_root', 'model_path', 'manifest_path',
                                      'environment_lock_path', 'actual_environment_lock_sha256')}
        admission = {'format': 'irisx/consolidated-runtime-admission-v2',
            'environment_plan_sha256': plan['plan_sha256'], 'source_identity_sha256': digest(owner_source),
            'prepared': ready, 'asset_receipts_sha256': digest(result['asset_receipts'])}
        path = root / 'runtime' / 'admission.json'
        bound = data.write_new(path, admission)
        ready = {**ready, 'admission_path': str(path), 'admission_sha256': bound['sha256']}
        receipt = {'bootstrap_stopped': True, 'child_stop_proof': proof,
                   'actual_environment_lock_sha256': result['actual_environment_lock_sha256'],
                   'asset_receipts': result['asset_receipts']}
    except BaseException as exc:
        receipt = {'bootstrap_stopped': getattr(exc, 'owned_descendants_stopped', False) is True,
                   'child_stop_proof': getattr(exc, 'child_stop_proof', {}), 'error': _error(exc)}
        ledger.record_response('bootstrap', receipt)
        ledger.finish('bootstrap', {'load_seconds': max(allowance, time.monotonic() - began)}, outcome='fail')
        raise
    ledger.record_response('bootstrap', receipt)
    ledger.finish('bootstrap', {'load_seconds': time.monotonic() - began})
    return ready


def _owner_proof(owner, closure, ledger, root):
    require(owner._request_path is not None, 'owner never established actual start evidence')
    refs = {}
    for name, path in (('request', owner._request_path), ('start', owner._request_path.parent / 'worker-start.json')):
        raw = data.read_regular(path)
        retained = root / 'runtime' / path.parent.name / path.name
        bound = ({'sha256': data.sha256(raw)} if retained == path else
                 data.write_new(retained, raw, raw=True))
        refs[name] = {'path': str(retained), 'sha256': bound['sha256']}
    return {'mode': 'remote-owner', 'closure': closure, **refs,
            'pending_reservations': _pending(ledger),
            'physical_calls': owner.accounting()['physical_calls_attempted']}


def _model_stage(tasks, requests, plan, gate, ledger, root, full_source, report):
    """No weight imports in parent; one child owner and no retry paths."""
    from tools.arc_public_research_20261010.remote_model_owner import RemoteModelOwner
    rows = {r.spec.call_id: {'call_id': r.spec.call_id, 'task_id': r.spec.task_id,
            'policy': r.spec.arm, 'status': 'excluded_session_budget'} for r in requests}
    report.update(rows=list(rows.values()), native_pair_admissions=[], status='partial',
                  owner_started=False, stop_confirmed=True, proof=None)
    owner, ownership_open, load_open = None, False, False
    inventory_hashes = {ir.digest(p) for p in ir.base_inventory()}
    # The owner only loads tools; the main source seal also binds src/irisx.
    owner_source = {k: v for k, v in full_source.items() if k.startswith('tools/')}
    try:
        ready = _bootstrap(plan, gate, ledger, root, owner_source)
        report['actual_environment_lock_sha256'] = ready['actual_environment_lock_sha256']
        _admit(ledger)
        owner = RemoteModelOwner(ready, environment_plan_sha256=plan['plan_sha256'],
            source_identity=owner_source, enabled=True,
            deadline_monotonic=time.monotonic() + ledger.remaining_wall_seconds - CLEANUP_SECONDS + 35)
        ledger.reserve('overhead', 'owner', {'physical_calls': 0}, metadata={'owner_resource': True})
        ownership_open = True
        allowance = min(1200, ledger.remaining_wall_seconds - CLEANUP_SECONDS - 5)
        ledger.reserve('overhead', 'load', {'load_seconds': allowance}, metadata={'owner_resource': True})
        load_open, began = True, time.monotonic()
        owner.set_initialization_deadline(began + allowance)
        report['native_preflight'] = owner.initialize_tokenizer()
        report['owner_started'] = True
        prepared = []
        for offset in range(0, len(requests), 2):
            _admit(ledger, 5)
            pair, admission = owner.prepare_group(list(requests[offset:offset + 2]))
            report['native_pair_admissions'].append(admission)
            if not pair:
                for request in requests[offset:offset + 2]:
                    rows[request.spec.call_id].update(status='excluded_token_budget', admission=admission)
            prepared.extend(pair)
        prompt_audit = {'profile': PROFILE, 'task_pairs': len(requests) // 2,
            'admitted_pairs': len(prepared) // 2, 'excluded_pairs': (len(requests) - len(prepared)) // 2,
            'maximum_physical_calls': len(prepared), 'model_loaded': False,
            'admissions': report['native_pair_admissions']}
        data.write_new(root / 'native-prompt-audit.json', prompt_audit)
        report['native_prompt_audit'] = {k: v for k, v in prompt_audit.items() if k != 'admissions'}
        print('PUBLIC120 native prompt admission: %d/%d pairs admitted; %d excluded; at most %d model calls.' %
              (len(prepared) // 2, len(requests) // 2, (len(requests) - len(prepared)) // 2, len(prepared)), flush=True)
        if prepared:
            owner.ensure_model_loaded()
        ledger.record_response('load', owner.accounting())
        ledger.finish('load', {'load_seconds': time.monotonic() - began})
        load_open = False
        for item in prepared:
            _admit(ledger, 5)
            request = item.request
            ident = 'model/' + request.spec.call_id
            allowance = min(120, ledger.remaining_wall_seconds - CLEANUP_SECONDS - 5)
            ledger.reserve('model', ident, {'prompt_tokens': item.prompt_tokens,
                'output_tokens': 2048, 'model_seconds': allowance, 'unknown_model_calls': 1},
                metadata=item.reservation())
            before = owner.model_seconds
            try:
                response = owner.dispatch(item, deadline_monotonic=time.monotonic() + allowance)
            except BaseException as exc:
                response = {'unknown_physical_call': True, 'error': _error(exc),
                            'request_sha256': item.sha256, 'cache_sha256': item.cache_sha256,
                            'model_seconds': max(allowance, owner.model_seconds - before)}
                ledger.record_response(ident, response)
                ledger.finish(ident, {'model_seconds': response['model_seconds']}, outcome='fail')
                rows[request.spec.call_id].update(status='unknown', response=response)
                raise
            ledger.record_response(ident, response)
            require(response['request_sha256'] == item.sha256 and response['cache_sha256'] == item.cache_sha256,
                    'model response request binding changed')
            ledger.finish(ident, {**{k: response[k] for k in ('prompt_tokens', 'output_tokens', 'model_seconds')},
                                  'unknown_model_calls': 0})
            classification = mp.classify_response(response['text'], inventory_hashes)
            complete = (not response.get('late') and not response.get('truncated') and
                        response.get('native_eos_complete') is True and response.get('finish_reason') == 'stop')
            rows[request.spec.call_id].update(status=classification['status'] if complete else 'incomplete_response',
                response=response, classification=classification,
                eligible=complete and classification['eligible'])
        report['status'] = 'complete'
    except BaseException as exc:
        report['error'] = _error(exc)
    finally:
        if owner is not None:
            report['owner_started'] = owner._request_path is not None
            report['stop_confirmed'] = False
            try:
                # Close first. Accounting failures must never bypass cleanup.
                closure = owner.close()
                report['closure'] = closure
                report['stop_confirmed'] = closure.get('owned_descendants_stopped') is True
                report['owner_accounting'] = owner.accounting()
            except BaseException as exc:
                report['closure_error'] = _error(exc)
            try:
                if load_open:
                    op = ledger.operation('load')
                    if 'response' not in op:
                        ledger.record_response('load', {'error': report.get('error'), 'accounting': owner.accounting()})
                    if op['status'] in ('reserved', 'responded'):
                        ledger.finish('load', {'load_seconds': time.monotonic() - began}, outcome='fail')
                if ownership_open and 'closure' in report:
                    ledger.record_response('owner', report['closure'])
                    ledger.finish('owner', outcome='complete' if report['stop_confirmed'] else 'fail')
                if 'closure' in report and report['owner_started']:
                    report['proof'] = _owner_proof(owner, report['closure'], ledger, root)
            except BaseException as exc:
                report['accounting_error'] = _error(exc)
        else:
            operation = ledger.operation('bootstrap')
            if operation:
                report['stop_confirmed'] = ('response' in operation and
                    ledger.get_response('bootstrap').get('bootstrap_stopped') is True)
        report['rows'] = list(rows.values())
        data.write_new(root / 'model.json', report)
    return report


def _query_policies(solver, selected, ledger, root, run_id, checked, query_fn=None):
    query_fn = query_fn or query.query_execute
    prediction_root = root / 'predictions'
    frozen, receipts, diagnostics = {}, {}, []
    # All policies are frozen before the first query, not just per task.
    for policy in data.POLICIES:
        frozen[policy] = query.freeze_selections(solver['challenges'], selected[policy],
            run_id=run_id, policy=policy, output_root=prediction_root)
        receipts[policy] = {}
    stopped = None
    for policy in data.POLICIES:
        for key, choices in frozen[policy]['selection']['selected'].items():
            receipts[policy][key] = []
            for index, value in enumerate(solver['query_inputs'][key]):
                for rank, choice in enumerate(choices):
                    call_id = 'query-%s-%s-%d-%d' % (policy, key, index, rank)
                    row = {'policy': policy, 'task_id': key, 'test_index': index,
                           'candidate_id': choice['candidate_id'], 'call_id': call_id}
                    if stopped:
                        diagnostics.append({**row, 'status': 'missing', 'reason': stopped})
                        continue
                    try:
                        _admit(ledger)
                        require(checked.all_stopped, 'CPU worker stop unconfirmed')
                        ledger.reserve('cpu', call_id, {'cpu_checks': 1, 'search_checks': 1,
                            'gas': verifier.MAX_STEPS, 'unknown_verifications': 1, 'verifier_seconds': 3.0},
                            metadata={**row, 'selection_sha256': frozen[policy]['selection_sha256'],
                                      'input_sha256': digest(value)})
                        receipt = query_fn(choice['plan'], [value], root / 'query-evidence', call_id,
                                           selection_sha256=frozen[policy]['selection_sha256'])
                        require(receipt['query_count'] == 1, 'one query input per CPU reservation required')
                        ledger.record_response(call_id, receipt)
                        result = receipt['results'][0]
                        checked.all_stopped &= receipt.get('owned_descendants_stopped') is True
                        usage = {'verifier_seconds': result['wall_seconds']}
                        if result['status'] in ('valid', 'invalid'):
                            usage.update(gas=result['gas_charged'], unknown_verifications=0)
                        ledger.finish(call_id, usage, outcome='complete' if result['status'] != 'missing' else 'fail')
                        receipts[policy][key].append({'candidate_id': choice['candidate_id'],
                                                     'test_index': index, 'receipt': receipt})
                        diagnostics.append({**row, 'status': result['status']})
                    except BaseException as exc:
                        stopped = type(exc).__name__ + ': ' + str(exc)[:300]
                        op = ledger.operation(call_id)
                        if op and op['status'] not in ('complete', 'fail'):
                            checked.all_stopped = False
                        diagnostics.append({**row, 'status': 'unknown' if op else 'missing', 'reason': stopped})
    for policy in data.POLICIES:
        pool = query.build_policy_pool(solver['challenges'], frozen[policy], receipts[policy],
            run_id=run_id, policy=policy, parent_wall_seconds=ledger.summary()['session_elapsed_seconds'])
        data.write_new(prediction_root / ('pools-' + policy + '.json'), pool)
        data.write_new(prediction_root / ('prediction-proof-' + policy + '.json'),
                       {'selections': frozen[policy], 'query_receipts': receipts[policy]})
    data.write_new(root / 'query-diagnostics.json', {'rows': diagnostics, 'task_denominator': TASKS,
        'test_denominator': TESTS, 'query_check_upper_bound': QUERY_CHECKS})
    return prediction_root


def run(output_root, solver_root, evaluator_root, solver_manifest_sha256, evaluator_manifest_sha256,
        enable_model=False, model_config=None, resume=False, session_seconds=SESSION_SECONDS, entry_wall_seconds=0.0, entry_provenance=None):
    """Explicit callable execution; model-disabled is a real CPU research mode."""
    return _run(output_root, solver_root, evaluator_root, solver_manifest_sha256,
                evaluator_manifest_sha256, enable_model=enable_model, model_config=model_config,
                resume=resume, session_seconds=session_seconds, entry_wall_seconds=entry_wall_seconds,
                entry_provenance=entry_provenance)


def _run_synthetic_for_tests(*args, verify_fn=None, rank_fn=None, query_fn=None, **kwargs):
    """Only synthetic 120/167 assets, always model-disabled, never real acceptance."""
    require(not kwargs.get('enable_model', False), 'synthetic hooks cannot enable a production owner')
    return _run(*args, **kwargs, _synthetic=True, _verify_fn=verify_fn, _rank_fn=rank_fn, _query_fn=query_fn)


def _run(output_root, solver_root, evaluator_root, solver_manifest_sha256, evaluator_manifest_sha256,
         *, enable_model=False, model_config=None, resume=False, session_seconds=SESSION_SECONDS, entry_wall_seconds=0.0, entry_provenance=None,
         _synthetic=False, _verify_fn=None, _rank_fn=None, _query_fn=None):
    started = time.monotonic()  # includes all source, inventory, ranking and bootstrap work
    require(type(enable_model) is bool and type(resume) is bool, 'Boolean model/resume switches required')
    require(type(session_seconds) in (int, float) and math.isfinite(session_seconds) and
            CLEANUP_SECONDS + 3 < session_seconds <= SESSION_SECONDS, 'session must be >123 and <=7200 seconds')
    require(type(entry_wall_seconds) in (int, float) and math.isfinite(entry_wall_seconds) and
            0 <= entry_wall_seconds < session_seconds, 'invalid entry bootstrap wall time')
    require(not (_synthetic and enable_model), 'synthetic coordinator cannot start a production model owner')
    require(_synthetic or all(v is None for v in (_verify_fn, _rank_fn, _query_fn)), 'production test hooks forbidden')
    require(enable_model or model_config is None, 'disabled model takes no model configuration')
    root, solver_root, evaluator_root = data.separated(*[normalized_path(p) for p in
                                                        (output_root, solver_root, evaluator_root)])
    data.hash_string(solver_manifest_sha256); data.hash_string(evaluator_manifest_sha256)
    guard_paths(model_config, {'source': ROOT, 'output': root, 'environment': environment_path(root)})
    data.separated(ROOT, root, environment_path(root), solver_root, evaluator_root)
    require(not root.exists() or resume, 'output identity exists; explicit resume required')
    require(not resume or (root / 'ledger' / 'journal.jsonl').is_file(), 'resume requires existing bound ledger')
    full_source, cpu_env = source_identity(), _cpu_environment()
    entry = _entry_provenance(entry_provenance, full_source, solver_manifest_sha256, evaluator_manifest_sha256)
    plan = None
    if enable_model:
        from tools.arc_public_research_20261010 import offline_bootstrap
        plan = offline_bootstrap.plan_config(model_config or {}, work_root=str(environment_path(root)))
    environment_sha = plan['plan_sha256'] if plan else digest(cpu_env)
    limits = limits_for()
    bindings = {'source': digest(full_source), 'task': digest({'solver': solver_manifest_sha256,
        'evaluator': evaluator_manifest_sha256}), 'model': mp.MODEL_MANIFEST_SHA256,
        'prompt': digest({'system': mp.SYSTEM_PROMPT, 'inventory': mp.INVENTORY_DESCRIPTION}),
        'sampling': digest(asdict(mp.Sampling())), 'budget': digest(limits),
        'mode': digest('synthetic-test-only' if _synthetic else 'public-development'),
        'environment': environment_sha, 'cpu_environment': digest(cpu_env), 'entry_provenance': digest(entry),
        'configuration': digest({'profile': PROFILE, 'enable_model': enable_model,
                                 'model_config': model_config, 'ranker': ranking.policy_config()})}
    root.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(root / 'ledger', bindings, limits)
    session_id = uuid.uuid4().hex
    report = {'format': FORMAT, 'profile': PROFILE, 'status': 'partial-inconclusive',
        'task_denominator': TASKS, 'test_denominator': TESTS, 'policies': list(data.POLICIES),
        'enable_model': enable_model, 'evidence_mode': 'synthetic-test-only' if _synthetic else 'public-development',
        'source_sha256': bindings['source'], 'training_used': False, 'adapter_used': False,
        'official_score': None, 'competition_gpu_equivalent': False, 'gpu_execution_validated': False,
        'workers_cap': WORKERS, 'session_seconds': session_seconds, 'entry_wall_seconds': entry_wall_seconds, 'cleanup_reserve_seconds': CLEANUP_SECONDS,
        'generation_may_resume': False, 'vm_billing_stopped': False,
        'scoring': {'status': 'SCORING_BLOCKED', 'official_score': None, 'reason': 'workflow incomplete'}}
    archive, solver, prediction_root = None, None, None
    owner_stopped, owner_proof = True, {'mode': 'model-disabled', 'model_disabled': True,
                                      'physical_calls': 0, 'pending_reservations': 0}
    actual_lock = digest(cpu_env)
    # Completed inspection may open a zero-second session; it cannot dispatch.
    with ledger.session(session_seconds=0 if resume else session_seconds,
                        prior_elapsed_seconds=0 if resume else entry_wall_seconds + time.monotonic() - started):
        if resume:
            prior = parse_json(data.read_regular(root / 'summary.json')) if (root / 'summary.json').is_file() else None
            require(ledger.summary()['state'] == 'complete' and prior is not None,
                    'partial resume is fail-closed; no retry, redispatch or continued generation is permitted')
            require((root / 'post-seal-closure.json').is_file(), 'completed resume requires post-seal closure')
            if (root / 'predictions' / 'prediction-seal.json').is_file():
                seal_raw = data.read_regular(root / 'predictions' / 'prediction-seal.json')
                evaluator._verify_seal(root / 'predictions', data.sha256(seal_raw), solver_root)
            return {'status': prior['status'], 'output_root': str(root), 'resumed_noop': True,
                    'report': prior, 'archive': parse_json(data.read_regular(root / 'post-seal-closure.json'))['archive']}
        data.write_new(root / 'run-binding.json', {'bindings': bindings, 'limits': limits,
            'source_identity': full_source, 'cpu_environment': cpu_env, 'run_id': session_id})
        data.write_new(root / 'entry-provenance.json', entry)
        checked = FreshVerifier(ledger, _verify_fn)
        ledger.reserve('overhead', 'archive', {'archive_seconds': CLEANUP_SECONDS}, metadata={'phase': 'final evidence'})
        try:
            require(verifier.capability()['available'], 'bounded Linux verifier unavailable')
            report['controls'] = _controls(checked, root)
            require(report['controls']['passed'], 'independent control gate failed')
            _admit(ledger)
            solver = data.load_solver_tasks(solver_root, solver_manifest_sha256)
            require((solver['manifest']['evidence_mode'] == 'synthetic-test-only') is _synthetic,
                    'synthetic assets require the separate synthetic-only coordinator')
            report['solver_identity'] = solver['identity']
            gate = {'profile': PROFILE, 'gate': 'public_research_contracts', 'passed': True,
                    'controls': {'total': CONTROLS, 'expected': CONTROLS},
                    'solver_manifest_sha256': solver_manifest_sha256,
                    'evaluator_manifest_sha256': evaluator_manifest_sha256,
                    'tasks': TASKS, 'tests': TESTS}
            data.write_new(root / 'admission.json', gate)
            pool = _base_pool()
            pool_by_id = {row['candidate_id']: row for row in pool}
            data.write_new(root / 'inventory.json', {'sha256': ranking.INVENTORY_SHA256, 'candidates': pool})
            orders, ranking_seal = _seal_rankings(solver['demos_tasks'], pool, root, ledger, _rank_fn)
            selected = {policy: {} for policy in data.POLICIES}
            report['ranking'] = {'sealed_sha256': ranking_seal, 'planned_checks': RANK_CHECKS,
                                 'completed_checks': 0, 'known_checks': 0}
            for policy in ('uniform', 'shape'):
                for key, ids in orders[policy].items():
                    jobs = [{'call_id': 'rank-%s-%s-%02d' % (policy, key, i),
                             'task': solver['demos_tasks'][key], 'plan': pool_by_id[cid]['plan'],
                             'ranking_seal_sha256': ranking_seal} for i, cid in enumerate(ids)]
                    rows = checked.batch(jobs)
                    data.write_new(root / 'verification' / ('%s-%s.json' % (policy, key)), {'rows': rows})
                    report['ranking']['completed_checks'] += sum(r['verification'].get('dispatched') is True for r in rows)
                    report['ranking']['known_checks'] += sum(r['verification'].get('known') is True for r in rows)
                    selected[policy][key] = _fresh_candidates(rows, pool_by_id, session_id, 2)
            report['model'] = {'status': 'model_disabled', 'planned_calls': MODEL_CALLS, 'physical_calls': 0,
                'rows': [{'task_id': key, 'policy': policy, 'status': 'model_disabled'}
                         for key in solver['demos_tasks'] for policy in ('raw', 'strict')]}
            if enable_model and checked.all_stopped:
                grammar = {'version': ir.IR_VERSION, 'contract': ir.plan_contract()}
                requests = mp.build_public_requests(list(solver['demos_tasks'].values()), grammar, environment_sha)
                report['model'] = {}
                owner_stopped = False
                _model_stage(solver['demos_tasks'], requests, plan, gate, ledger,
                             root, full_source, report['model'])
                owner_stopped = report['model']['stop_confirmed']
                actual_lock = report['model'].get('actual_environment_lock_sha256', actual_lock)
                owner_proof = report['model'].get('proof')
                if owner_proof is None and not report['model'].get('owner_started') and not any(
                    op['kind'] == 'model' for op in ledger.summary()['operations'].values()) and owner_stopped:
                    owner_proof = {'mode': 'model-disabled', 'model_disabled': True,
                                   'physical_calls': 0, 'pending_reservations': 0}
                if owner_stopped:
                    for row in report['model']['rows']:
                        if row.get('eligible'):
                            cid = row['classification']['plan_sha256']
                            job = {'call_id': 'model-fit-%s-%s' % (row['task_id'], row['policy']), 'scope': 'model',
                                   'task': solver['demos_tasks'][row['task_id']], 'plan': pool_by_id[cid]['plan']}
                            result = checked.batch([job])
                            selected[row['policy']][row['task_id']] = _fresh_candidates(result, pool_by_id, session_id, 1)
                            data.write_new(root / 'verification' / (job['call_id'] + '.json'), {'rows': result})
            # Model close comes before any selection or query, even on errors.
            if owner_stopped and checked.all_stopped:
                prediction_root = _query_policies(solver, selected, ledger, root, session_id, checked, _query_fn)
                _scoring_admission(ledger)
                require(owner_proof is not None, 'actual owner start/close proof unavailable')
                origin = 'synthetic_cpu' if _synthetic else ('research_gpu' if owner_proof['mode'] == 'remote-owner'
                    and owner_proof['physical_calls'] > 0 else 'research_cpu')
                prediction_bindings = {'run_id': session_id, 'source_identity': full_source,
                    'environment_plan_sha256': environment_sha, 'actual_environment_lock_sha256': actual_lock,
                    'prediction_origin': origin, 'model_sha256': mp.MODEL_MANIFEST_SHA256}
                require(source_identity() == full_source, 'source bytes changed during run')
                seal = evaluator.seal_predictions(prediction_root, solver_root=solver_root,
                    solver_manifest_sha256=solver_manifest_sha256, evaluator_manifest_sha256=evaluator_manifest_sha256,
                    owner_proof=owner_proof, bindings=prediction_bindings)
                report['prediction_seal'] = seal
                _scoring_admission(ledger)
                report['scoring'] = evaluator.evaluate_sealed(prediction_root, seal['seal_sha256'],
                    solver_root=solver_root, evaluator_root=evaluator_root, output_root=root / 'evaluation')
                if report['scoring']['status'] == 'SCORED':
                    report['status'] = 'complete' if report['ranking']['known_checks'] == RANK_CHECKS and \
                        report['ranking']['completed_checks'] == RANK_CHECKS and (
                        not enable_model or report['model']['status'] == 'complete') else 'partial-scored'
            else:
                report['scoring']['reason'] = 'owned process stop unconfirmed; scoring prohibited'
        except BaseException as exc:
            report['error'] = _error(exc)
            report['scoring'] = {'status': 'SCORING_BLOCKED', 'official_score': None,
                                 'reason': 'admission, source, resource, or closure contract not established',
                                 'error_type': type(exc).__name__}
        finally:
            report['workers_used'] = checked.workers_used
            report['processes'] = {'model_owner_stopped': owner_stopped,
                                   'verifier_descendants_stopped': checked.all_stopped}
            report['accounting'] = _compact(ledger)
            report['elapsed_seconds'] = entry_wall_seconds + time.monotonic() - started
            report['session_deadline_met'] = ledger.remaining_wall_seconds > 0
            data.write_new(root / 'summary.json', report)
            if owner_stopped and checked.all_stopped:
                try:
                    archive = _stream_archive(root, stopped=report['processes'], summary={
                        'format': FORMAT, 'status': report['status'], 'test_denominator': TESTS,
                        'task_denominator': TASKS, 'scoring_status': report['scoring']['status']},
                        session_id=session_id, deadline_monotonic=time.monotonic() + ledger.remaining_wall_seconds - 1)
                    ledger.finish('archive', {'archive_seconds': archive['seconds']})
                except BaseException as exc:
                    report['archive_error'] = _error(exc)
                    report['status'] = 'partial-archive-failed'
                    archive = None
            if ledger.remaining_wall_seconds <= 0:
                report['status'] = 'partial-session-deadline-exceeded'
            if ledger.summary()['reservation_overrun']:
                report['status'] = 'partial-accounting-overrun'
            final_state = 'complete' if report['status'] in ('complete', 'partial-scored') and archive and _pending(ledger) == 0 else 'partial'
            ledger.set_state(final_state, report['status'])
            data.write_new(root / 'post-seal-closure.json', {'format': 'irisx/public120-post-seal-closure-v1',
                'archive': archive, 'final_status': report['status'], 'accounting': _compact(ledger), 'processes': report['processes'],
                'generation_may_resume': False, 'elapsed_seconds': entry_wall_seconds + time.monotonic() - started,
                'session_deadline_met': ledger.remaining_wall_seconds > 0,
                'scope': 'Archive binds its journal prefix; this receipt records subsequent archive accounting.'})
    return {'status': report['status'], 'output_root': str(root), 'archive': archive,
            'session_id': session_id, 'report': report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manual-start', action='store_true')
    parser.add_argument('--enable-model', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--output-root')
    parser.add_argument('--solver-root')
    parser.add_argument('--evaluator-root')
    parser.add_argument('--solver-manifest-sha256')
    parser.add_argument('--evaluator-manifest-sha256')
    parser.add_argument('--model-config', help='JSON object: only pinned bootstrap input_root/explicit_roots')
    parser.add_argument('--session-seconds', type=float, default=SESSION_SECONDS)
    args = parser.parse_args(argv)
    if not args.manual_start:
        print(json.dumps({'status': 'manual-start-disabled', 'model_enabled': False}))
        return 0
    for key in ('output_root', 'solver_root', 'evaluator_root', 'solver_manifest_sha256', 'evaluator_manifest_sha256'):
        if not getattr(args, key):
            parser.error('--' + key.replace('_', '-') + ' is required with --manual-start')
    config = parse_json(data.read_regular(normalized_path(args.model_config))) if args.model_config else None
    if config is not None:
        require(type(config) is dict and set(config) <= {'input_root', 'explicit_roots'}, 'safe bootstrap config fields only')
    result = run(args.output_root, args.solver_root, args.evaluator_root, args.solver_manifest_sha256,
        args.evaluator_manifest_sha256, enable_model=args.enable_model, model_config=config,
        resume=args.resume, session_seconds=args.session_seconds)
    print(json.dumps({'status': result['status'], 'output_root': result['output_root'],
                      'scoring_status': result['report']['scoring']['status'], 'archive': result['archive']}))
    return 0 if result['report']['scoring']['status'] == 'SCORED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
