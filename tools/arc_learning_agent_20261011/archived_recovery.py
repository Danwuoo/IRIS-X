"""Explicit, offline CPU recovery of immutable archived v4 predictions.

This is NOT the live owner protocol. Original result/closure/source/provider ERROR
are immutable, and recorded remote closure never purports to observe local PIDs.
No evaluator file is read by preparation or proof-only validation. The fresh
isolated scorer receives only already sealed predictions; generation cannot resume.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
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
import tools.arc_learning_agent_20261011.deployment.validate_learning_outputs as historical
from tools.arc_learning_agent_20261011.evaluation import make_pools, POLICIES, source_identity
from tools.arc_learning_agent_20261011.result_projection import project_owner_result
from tools.arc_public_research_20261010 import public_data as data
from tools.arc_public_research_20261010.public_evaluator import SCORER_PINS

ROOT = Path(__file__).resolve().parents[2]
MIB = 1024 ** 2
RAW_CAP, COMPACT_CAP = 64 * MIB, 16 * MIB
FORMAT = 'irisx/learning-archived-recovery-contract-v1'
SEAL_FORMAT = 'irisx/learning-archived-prediction-seal-v1'
DETAIL_SERIALIZER = 'frozen controller._json: sort_keys=True,separators=(comma,colon),allow_nan=False,ensure_ascii=True,newline'
V4 = {'reference': 'danielwuu/iris-x-learning-agent-20261011', 'kernel_id': 138123872,
      'version': 4, 'provider_status': 'ERROR', 'code_dataset_version': 2,
      'source_sha256': '5e048af557b5c8701665dbe95cbee635c925b1c80b62da25487cff64b920903b',
      'source_identity_sha256': 'ba7f3f558c3ff64ab8e9744fe095a78b811a482eea7d9af748787747d5d59f93',
      'raw_result_sha256': '9073b54f5eb6508cdd419e8d898a63b8c35cdf9fddc945b04845627e449ce0d9',
      'started_epoch': 1791697978, 'deadline_epoch': 1791741178}
INNER_FILES = ('owner-closure.json', 'owner-start.json', 'worker/request.json',
               'worker/result.json', 'worker/physical-work.jsonl', 'session-clock.json', 'admission.json')
GUARD_FILES = ('launch.json', 'worker-launch.json', 'supervisor-result.json', 'closure.json')
OUTER_FILES = ('request.json', 'launcher-closure.json', 'bootstrap.py', 'owned_process_guard.py')
NEURAL = ('torch', 'transformers', 'peft', 'tensorflow', 'jax')
need = historical.need


def clean_path(value):
    need(type(value) is str and Path(value).is_absolute() and '..' not in Path(value).parts,
         'absolute_path_required')
    path = Path(value)
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink_forbidden')
    return path


def descriptor(path, cap=COMPACT_CAP):
    path = clean_path(str(Path(path).absolute()))
    return {'path': str(path), **historical.regular_hash(path, cap)}


def bound_file(row, cap=COMPACT_CAP):
    need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'} and
         historical.integer(row['bytes'], 1) and historical.hash_ok(row['sha256']), 'file_descriptor')
    path = clean_path(row['path'])
    need(historical.regular_hash(path, cap) == {k: row[k] for k in ('bytes', 'sha256')}, 'input_bytes_hash')
    return path


def read_bound(row, cap=COMPACT_CAP):
    path = bound_file(row, cap)
    raw = historical.regular_bytes(path, cap)
    need(len(raw) == row['bytes'] and historical.sha(raw) == row['sha256'], 'input_changed')
    return raw


def parse(raw):
    value = historical.parse(raw)
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is float:
            need(math.isfinite(item), "nonfinite_json")
        elif type(item) is dict:
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)
    return value


def check_executable_sources(expected):
    need(type(expected) is dict and expected == source_identity(), 'recovery_source_changed')
    need(all(expected.get(k) == v for k, v in SCORER_PINS.items()), 'unchanged_scorer_required')


def failed_outer_proof(proof, fmt='irisx/owned-process-closure-v1'):
    """Strict recorded closure for this known outer packaging failure, not success.

    Do not replace fields and feed a fabricated successful proof to live/historical
    success validators. These original persisted values must all remain unchanged.
    """
    need(type(proof) is dict and proof.get('format') == fmt and
         proof.get('scope') == 'dedicated-subreaper-tree' and proof.get('closed') is True and
         proof.get('ownership_complete') is True, 'outer_recorded_closure_incomplete')
    need(proof.get('remaining') == [] and proof.get('errors') == [] and proof.get('forced') is False,
         'outer_forced_or_remaining')
    need(type(proof.get('returncode')) is int and proof['returncode'] == 1 and
         type(proof.get('worker_returncode')) is int and proof['worker_returncode'] == 1,
         'outer_expected_packaging_failure')
    root = historical.identity(proof['root_identity'])
    owned = [historical.identity(x) for x in proof['owned_identities']]
    reaped = [historical.identity(x) for x in proof['reaped_identities']]
    need(owned and len(owned) == len(set(owned)) and root in owned and
         len(reaped) == len(set(reaped)) and set(reaped) <= set(owned), 'outer_identity_binding')
    return root


def failed_outer_bundle(read_json, prefix, expected):
    proof = read_json(prefix + 'closure.json')
    need(proof == expected, 'outer_persisted_proof_binding')
    root = failed_outer_proof(proof)
    launch, worker = (read_json(prefix + n) for n in ('launch.json', 'worker-launch.json'))
    supervisor = read_json(prefix + 'supervisor-result.json')
    need(launch['format'] == 'irisx/owned-process-launch-v1' and
         launch['scope'] == 'dedicated-subreaper-tree' and
         historical.identity(launch['supervisor_identity']) == root, 'outer_launch_binding')
    need(worker['format'] == 'irisx/owned-worker-launch-v1' and worker['parent_death_signal'] == 9 and
         historical.identity(worker['supervisor_identity']) == root, 'outer_worker_binding')
    child = historical.identity(worker['worker_identity'])
    need(child in [historical.identity(x) for x in proof['owned_identities']], 'outer_worker_ownership')
    need(failed_outer_proof(supervisor, 'irisx/owned-supervisor-result-v1') == child and
         historical.identity(supervisor['supervisor_identity']) == root, 'outer_supervisor_binding')
    return launch, worker


class Evidence:
    def __init__(self, contract):
        self.contract = contract
        self.run_root = contract['output_root']
        historical.safe_name(self.run_root)
        need('/' not in self.run_root, 'output_root_name')
        expected = {self.run_root + '/' + x for x in INNER_FILES}
        expected.update(self.run_root + '/worker/process-guard/' + x for x in GUARD_FILES)
        expected.update(self.run_root + '-launcher/' + x for x in OUTER_FILES)
        expected.update(self.run_root + '-launcher/owned-tree/' + x for x in GUARD_FILES)
        need(type(contract['files']) is dict and set(contract['files']) == expected, 'historical_file_set')
        self.files = contract['files']
        for name, row in self.files.items():
            historical.safe_name(name)
            bound_file(row, RAW_CAP if name.endswith('/worker/result.json') else COMPACT_CAP)
        request = self.json('worker/request.json')
        self.run_id = request['run_id']

    def raw(self, name):
        return self.absolute_raw(self.run_root + '/' + name)

    def json(self, name):
        return parse(self.raw(name))

    def absolute_raw(self, name):
        need(name in self.files, 'historical_file_missing')
        return read_bound(self.files[name], RAW_CAP if name.endswith('/worker/result.json') else COMPACT_CAP)

    def absolute_json(self, name):
        return parse(self.absolute_raw(name))


def validate_receipts(contract):
    original, expected, seen = contract['original'], contract['files'], {}
    need(type(contract['retrieval_receipts']) is list and 0 < len(contract['retrieval_receipts']) <= 8,
         'retrieval_receipts_required')
    for binding in contract['retrieval_receipts']:
        receipt = parse(read_bound(binding))
        need(receipt.get('reference') == original['reference'] and
             receipt.get('kernel_id') == original['kernel_id'] and
             receipt.get('source_sha256') == original['source_sha256'], 'retrieval_source_identity')
        version = receipt.get('numeric_output_version', receipt.get('version'))
        need(type(version) is int and version == original['version'], 'retrieval_numeric_version')
        status = receipt.get('provider_status', receipt.get('after_status', receipt.get('status')))
        need(status == 'ERROR', 'original_provider_error_required')
        need(type(receipt.get('files')) is list, 'retrieval_file_rows')
        for row in receipt['files']:
            name = historical.safe_name(row['provider_path'])
            version = row.get('numeric_version', row.get('version'))
            need(type(version) is int and version == original['version'], 'file_numeric_version')
            binding = {k: row[k] for k in ('bytes', 'sha256')}
            need(name not in seen or seen[name] == binding, 'conflicting_retrieval_rows')
            seen[name] = binding
    for name, row in expected.items():
        need(seen.get(name) == {k: row[k] for k in ('bytes', 'sha256')}, 'unattested_archived_file')


def validate_contract(path, expected_sha256):
    raw = historical.regular_bytes(clean_path(str(Path(path).absolute())), COMPACT_CAP)
    need(historical.hash_ok(expected_sha256) and historical.sha(raw) == expected_sha256, 'contract_hash')
    c = parse(raw)
    fields = {'format', 'recovery_id', 'mode', 'original', 'source_root', 'source_identity',
              'recovery_source_identity', 'output_root', 'files', 'retrieval_receipts', 'notebook',
              'solver_root', 'evaluator_root', 'solver_manifest_sha256', 'evaluator_manifest_sha256'}
    need(type(c) is dict and set(c) == fields and c['format'] == FORMAT, 'contract_schema')
    need(c['mode'] in ('archived-v4', 'synthetic-test-only'), 'recovery_mode')
    historical.safe_name(c['recovery_id'])
    need('/' not in c['recovery_id'] and c['recovery_id'] != c['output_root'], 'fresh_recovery_identity')
    original = c['original']
    need(type(original) is dict and set(original) == set(V4), 'original_identity_schema')
    need(original['provider_status'] == 'ERROR' and type(original['version']) is int and
         historical.number(original['started_epoch']) and
         original['deadline_epoch'] == original['started_epoch'] + 43200, 'original_status_clock')
    if c['mode'] == 'archived-v4':
        need(original == V4 and len(c['source_identity']) == 97, 'exact_archived_v4_identity')
    else:
        need(original['reference'] == 'synthetic/test-only' and original['version'] == 4,
             'synthetic_identity_required')
    need(time.time() < original['deadline_epoch'], 'original_deadline_elapsed')
    source_root = clean_path(c['source_root'])
    source = c['source_identity']
    need(type(source) is dict and source and digest(source) == original['source_identity_sha256'],
         'original_source_identity')
    for name, expected in source.items():
        historical.safe_name(name)
        need(historical.hash_ok(expected) and
             historical.regular_hash(source_root / name, 4 * MIB)['sha256'] == expected,
             'original_source_bytes')
    need(all(source.get(k) == v for k, v in SCORER_PINS.items()), 'original_scorer_pins')
    check_executable_sources(c['recovery_source_identity'])
    for role in ('solver', 'evaluator'):
        clean_path(c[role + '_root'])
        need(historical.hash_ok(c[role + '_manifest_sha256']), 'public_manifest_pin')
    data.separated(c['solver_root'], c['evaluator_root'])
    validate_receipts(c)
    notebook = parse(read_bound(c['notebook']))
    need(c['notebook']['sha256'] == original['source_sha256'], 'original_notebook_hash')
    constants, suffix = historical.notebook_constants(historical.normalize_notebook(notebook))
    return c, Evidence(c), constants, suffix


def verify_history(c, e, constants, suffix, result):
    original = c['original']
    need(result['format'] == 'irisx/learning-owner-result-v1' and result['run_id'] == e.run_id and
         result['status'] == 'complete' and result['model_stopped'] is True and
         type(result['pending_work']) is dict and result['pending_work'] == {}, 'archived_owner_not_complete')
    need(result['source_identity_sha256'] == original['source_identity_sha256'], 'owner_original_source')
    need(e.files[e.run_root + '/worker/result.json']['sha256'] == original['raw_result_sha256'], 'original_raw_result')
    # Reuse original strict historical owner/ledger/training checks, with no /proc.
    request, owner = historical.verify_inner_owner(e, result, original['source_identity_sha256'])
    ledger, completed = historical.verify_ledger(e.raw('worker/physical-work.jsonl'), result['physical_usage'])
    historical.verify_training(result, completed, c['mode'] == 'synthetic-test-only')
    del completed
    clock = e.json('session-clock.json')
    need(set(clock) == {'format', 'session_id', 'origin', 'started_epoch', 'deadline_epoch', 'maximum_seconds'} and
         clock['format'] == 'irisx/learning-clock-v1' and clock['session_id'] == e.run_id and
         clock['origin'] == 'pre-dispatch' and clock['started_epoch'] == original['started_epoch'] and
         clock['deadline_epoch'] == original['deadline_epoch'] and clock['maximum_seconds'] == 43200,
         'original_session_clock')
    admission = e.json('admission.json')
    need(admission['run_id'] == e.run_id and admission['source_identity'] == c['source_identity'] and
         admission['enable_model'] is True and admission['clock'] == clock == request['clock'] and
         request['source_identity'] == c['source_identity'], 'admission_request_binding')
    for role in ('solver', 'evaluator'):
        need(admission[role + '_manifest_sha256'] == c[role + '_manifest_sha256'], 'admission_public_pin')
    need(request['solver_manifest_sha256'] == c['solver_manifest_sha256'], 'request_solver_pin')
    config = request['config']
    if c['mode'] == 'archived-v4':
        need(config.get('tiny_cpu', False) is False and config.get('validation_mode', False) is False and
             config.get('session_seconds') == 43200 and config.get('predispatch_clock') is True,
             'production_request_config')
    else:
        need(config.get('tiny_cpu') is True and config.get('validation_mode') is True and
             config.get('fixture_tasks') == 120, 'synthetic_full_denominator')
    need([row.get('stage') for row in result['stage_clock']] == list(historical.STAGE_CAPS), 'stage_order')
    for row in result['stage_clock']:
        need(row.get('maximum_seconds') == historical.STAGE_CAPS[row['stage']] and
             row.get('status') == 'complete' and row.get('within_cap') is True and
             historical.number(row.get('started_epoch')) and historical.number(row.get('elapsed_seconds')) and
             row['elapsed_seconds'] <= row['maximum_seconds'] and
             original['started_epoch'] <= row['started_epoch'] <= row['started_epoch'] + row['elapsed_seconds'] <= original['deadline_epoch'],
             'original_stage_deadline')
    need(len(result['results']) == 120 and all(row.get('status') == 'complete' and
         row['physical_usage'].get('unknown_usage_events') == 0 for row in result['results'].values()),
         'archived_task_work_incomplete')
    prefix = e.run_root + '-launcher/'
    outer = e.absolute_json(prefix + 'launcher-closure.json')
    need(outer.get('format') == 'irisx/learning-notebook-closure-v1' and outer.get('forced') is False and
         outer.get('reason') is None and outer.get('within_absolute_deadline') is True and
         outer.get('started_epoch') == original['started_epoch'] and
         outer.get('hard_deadline_epoch') == original['deadline_epoch'] and
         historical.number(outer.get('completed_epoch')) and
         original['started_epoch'] <= outer['completed_epoch'] <= original['deadline_epoch'], 'outer_deadline')
    launch, worker = failed_outer_bundle(e.absolute_json, prefix + 'owned-tree/', outer['process_tree_proof'])
    need(historical.identity(owner['parent_identity']) == historical.identity(worker['worker_identity']),
         'outer_inner_parent_binding')
    outer_raw = e.absolute_raw(prefix + 'request.json'); outer_request = parse(outer_raw)
    need(launch['worker_argv'][-1] == historical.sha(outer_raw), 'outer_request_launch_hash')
    expected_config = {k.lower(): constants[k] for k in ('MANUAL_START', 'ENABLE_MODEL', 'PROFILE',
        'OUTPUT_ROOT', 'SOURCE_PARENT', 'INPUT_ROOT', 'CODE_ROOT', 'DATA_ROOT', 'TRAINING_ROOT', 'MODEL_CONFIG', 'SEED')}
    expected_config.update(session_seconds=constants['SESSION_SECONDS'], predispatch_epoch=original['started_epoch'])
    need(outer_request['config'] == expected_config and outer_request['pins'] == constants['LEARNING_PINS'],
         'outer_original_source_config')
    need(constants['OUTPUT_ROOT'] == e.run_root and constants['PREDISPATCH_EPOCH'] == original['started_epoch'] and
         constants['SESSION_SECONDS'] == 43200 and constants['MANUAL_START'] is True and constants['ENABLE_MODEL'] is True,
         'original_notebook_activation')
    need(outer_request['started_epoch'] == original['started_epoch'] and
         outer_request['hard_deadline_epoch'] == original['deadline_epoch'], 'outer_original_clock')
    need(historical.sha(constants['LOADER_SOURCE'].encode()) == constants['LOADER_SHA256'] == outer_request['loader_sha256'],
         'outer_loader_bytes')
    need(e.absolute_raw(prefix + 'owned_process_guard.py') == constants['GUARD_SOURCE'].encode() and
         historical.sha(constants['GUARD_SOURCE'].encode()) == constants['GUARD_SHA256'] == outer_request['guard_sha256'],
         'outer_guard_bytes')
    need(type(suffix) is str and e.absolute_raw(prefix + 'bootstrap.py') == (constants['LOADER_SOURCE'] + suffix).encode() and
         historical.sha(e.absolute_raw(prefix + 'bootstrap.py')) == outer_request['driver_sha256'], 'outer_driver_bytes')
    historical.suffix_path(outer_request['launcher_root'], e.run_root + '-launcher')
    pins = constants['LEARNING_PINS']['data']['role_manifests']
    need(pins['solver'] == c['solver_manifest_sha256'] and pins['evaluator'] == c['evaluator_manifest_sha256'],
         'original_public_asset_pins')
    return request


def derived_details(result):
    """Frozen controller._json serializer; derived bytes are NOT provider downloads."""
    return {key: (json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
            for key, row in result['results'].items()}


def build_projection(c, e, constants, suffix):
    raw = e.raw('worker/result.json')
    result = parse(raw)
    request = verify_history(c, e, constants, suffix, result)
    solver = data.load_solver_tasks(c['solver_root'], c['solver_manifest_sha256'])
    need(solver['manifest']['evidence_mode'] == ('public-development' if c['mode'] == 'archived-v4' else 'synthetic-test-only'),
         'public_asset_evidence_mode')
    details = derived_details(result)
    # Do not retain two object-heavy copies of the full owner in the CPU child.
    del result
    gc.collect()
    projected = project_owner_result(raw, request=request, challenges=solver['challenges'], task_details=details)
    del raw, details
    gc.collect()
    pools = make_pools(solver['challenges'], projected['results'], run_id=projected['run_id'],
                       elapsed_seconds=projected['elapsed_seconds'])
    return projected, pools, solver


def output_separated(output, c, contract_path):
    output = clean_path(str(Path(output).absolute()))
    protected = [clean_path(c[k]) for k in ('source_root', 'solver_root', 'evaluator_root')]
    protected += [clean_path(row['path']) for row in c['files'].values()]
    protected += [clean_path(row['path']) for row in c['retrieval_receipts']]
    protected += [clean_path(c['notebook']['path']), clean_path(str(Path(contract_path).absolute()))]
    for path in protected:
        need(output != path and output not in path.parents and path not in output.parents,
             'recovery_output_overlaps_original')
    return output


def prepare_recovery(contract_path, contract_sha256, output_root):
    """Validate immutable inputs and seal exact policy pools. Never opens answers."""
    c, e, constants, suffix = validate_contract(contract_path, contract_sha256)
    output = output_separated(output_root, c, contract_path)
    need(not output.exists(), 'recovery_identity_consumed')
    projected, pools, _ = build_projection(c, e, constants, suffix)
    need(time.time() < c['original']['deadline_epoch'], 'original_deadline_elapsed')
    output.mkdir(parents=True)
    atomic_json(output / 'solver-result.json', projected, exclusive=True)
    for policy in POLICIES:
        atomic_json(output / (policy + '.json'), pools[policy], exclusive=True)
    seal = {'format': SEAL_FORMAT, 'recovery_id': c['recovery_id'], 'mode': c['mode'],
            'contract': descriptor(contract_path), 'original': c['original'],
            'source_identity_sha256': c['original']['source_identity_sha256'],
            'recovery_source_identity': c['recovery_source_identity'],
            'task_details_origin': 'deterministically reconstructed from exact original aggregate; not independently downloaded',
            'task_detail_serializer': DETAIL_SERIALIZER,
            'task_detail_serializer_source_sha256': c['source_identity']['tools/arc_learning_agent_20261011/controller.py'],
            'files': data.inventory(output), 'policies': list(POLICIES), 'tasks': 120, 'tests': 167,
            'generation_may_resume': False, 'new_gpu_execution': False,
            'original_provider_status': 'ERROR', 'created_epoch': time.time()}
    atomic_json(output / 'prediction-seal.json', seal, exclusive=True)
    seal_sha = descriptor(output / 'prediction-seal.json')['sha256']
    verify_recovery(output, seal_sha)
    return {'path': str(output / 'prediction-seal.json'), 'sha256': seal_sha,
            'status': 'ARCHIVED_PREDICTIONS_SEALED', 'original_provider_status': 'ERROR'}


def verify_recovery(root, seal_sha256):
    """Rehash originals, replay proof/ledger and reproduce projection/pools, truth-free."""
    root = clean_path(str(Path(root).absolute()))
    seal = parse(data.read_regular(root / 'prediction-seal.json', seal_sha256))
    need(type(seal) is dict and set(seal) == {'format', 'recovery_id', 'mode', 'contract', 'original',
         'source_identity_sha256', 'recovery_source_identity', 'task_details_origin', 'task_detail_serializer',
         'task_detail_serializer_source_sha256', 'files', 'policies', 'tasks', 'tests', 'generation_may_resume',
         'new_gpu_execution', 'original_provider_status', 'created_epoch'}, 'archived_seal_schema')
    need(seal.get('format') == SEAL_FORMAT and seal.get('generation_may_resume') is False and
         seal.get('new_gpu_execution') is False and seal.get('original_provider_status') == 'ERROR' and
         seal.get('policies') == list(POLICIES) and (seal.get('tasks'), seal.get('tests')) == (120, 167),
         'archived_seal_identity')
    expected_names = {'solver-result.json'} | {p + '.json' for p in POLICIES}
    need(set(seal['files']) == expected_names, 'archived_seal_files')
    data.verify_inventory(root, seal['files'], exclude=('prediction-seal.json',))
    c, e, constants, suffix = validate_contract(bound_file(seal['contract']), seal['contract']['sha256'])
    need(seal['recovery_id'] == c['recovery_id'] and seal['mode'] == c['mode'] and
         seal['original'] == c['original'] and seal['recovery_source_identity'] == c['recovery_source_identity'] and
         seal['source_identity_sha256'] == c['original']['source_identity_sha256'], 'archived_seal_contract_binding')
    need(historical.number(seal['created_epoch']) and c['original']['started_epoch'] <=
         seal['created_epoch'] < c['original']['deadline_epoch'], 'seal_original_deadline')
    need(seal['task_detail_serializer'] == DETAIL_SERIALIZER and seal['task_details_origin'] == 'deterministically reconstructed from exact original aggregate; not independently downloaded' and
         seal['task_detail_serializer_source_sha256'] == c['source_identity']['tools/arc_learning_agent_20261011/controller.py'],
         'derived_detail_provenance')
    projected, pools, solver = build_projection(c, e, constants, suffix)
    need(data.read_regular(root / 'solver-result.json') == canonical(projected), 'projection_bytes_changed')
    for policy in POLICIES:
        need(data.read_regular(root / (policy + '.json')) == canonical(pools[policy]), 'pool_order_or_bytes_changed')
    need(time.time() < c['original']['deadline_epoch'], 'original_deadline_elapsed')
    return seal, c, projected, pools, solver


def forbid_neural():
    need(not any(k == name or k.startswith(name + '.') for k in sys.modules for name in NEURAL),
         'neural_modules_forbidden')


def _isolated(request):
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (512 * MIB, 512 * MIB))
    resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * MIB, 32 * MIB))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    forbid_neural()
    import socket
    def no_network(event, args):
        if event == 'socket.__new__' and args[1] in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError('archived CPU scorer is offline')
        if event in ('socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.getnameinfo'):
            raise RuntimeError('archived CPU scorer DNS is offline')
    sys.addaudithook(no_network)
    # Refuse neural module imports even if a future transitive dependency attempts one.
    class NoNeural:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in NEURAL:
                raise ImportError('neural imports forbidden in archived scorer')
    sys.meta_path.insert(0, NoNeural())
    seal, c, projected, pools, solver = verify_recovery(request['seal_root'], request['seal_sha256'])
    output = output_separated(request['output_root'], c, seal['contract']['path'])
    data.separated(output, request['seal_root'])
    if request.get('proof_only') is True:
        atomic_json(output / 'proof-only.json', {'status': 'ARCHIVED_PROOF_VALIDATED',
                    'public_answers_opened': False, 'seal_sha256': request['seal_sha256'],
                    'maximum_resident_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}, exclusive=True)
        return
    need(request.get('proof_only') is False, 'explicit_scoring_mode_required')
    # First evaluator-side read occurs ONLY after complete input/projection/pool verification.
    evaluator = clean_path(c['evaluator_root'])
    manifest = data.validate_manifest(parse(data.read_regular(evaluator / 'manifest.json',
                                            c['evaluator_manifest_sha256'])), role='evaluator')
    need(manifest['identity'] == solver['identity'] and manifest['source'] == solver['manifest']['source'],
         'evaluator_solver_identity')
    data.verify_inventory(evaluator, manifest['files'], exclude=('manifest.json',))
    upstream = parse(data.read_regular(evaluator / 'upstream-inventory.json',
                                      manifest['source']['evaluation_inventory_sha256']))
    if manifest['evidence_mode'] == 'public-development':
        for name, expected in data.verify_upstream_inventory(upstream).items():
            need(data.git_object_sha('blob', data.read_regular(evaluator / 'upstream' / name)) == expected,
                 'official_public_blob')
    from tools.arc_offline_evaluation import load_pinned_reference, evaluate
    challenges, solutions, reference = load_pinned_reference(evaluator / 'upstream', evaluator / 'provenance.json')
    need(challenges == solver['challenges'], 'evaluator_challenge_projection')
    reports = {policy: evaluate(challenges, solutions, pools[policy]) for policy in POLICIES}
    del solutions, challenges, solver, pools
    labels = {'format': 'irisx/learning-archived-cpu-evaluation-v1', 'status': 'SCORED',
              'recovery_id': c['recovery_id'], 'mode': c['mode'], 'original_provider_status': 'ERROR',
              'measurement': 'archived-v4 CPU postprocessing recovery of existing trained-model predictions'
                  if c['mode'] == 'archived-v4' else 'synthetic-test-only archived recovery validation',
              'official_score': None, 'competition_gpu_equivalent': False,
              'tasks': 120, 'tests': 167, 'prediction_origin': projected['prediction_origin'],
              'training_used': projected['training_steps'] > 0, 'training_steps': projected['training_steps'],
              'physical_usage': projected['physical_usage'], 'new_gpu_execution': False,
              'generation_may_resume': False, 'prediction_seal_sha256': request['seal_sha256'],
              'original_raw_result_sha256': c['original']['raw_result_sha256'],
              'scorer_sha256': SCORER_PINS['tools/arc_offline_evaluation.py'],
              'original_deadline_epoch': c['original']['deadline_epoch']}
    del projected
    gc.collect()
    verify_recovery(request['seal_root'], request['seal_sha256'])
    forbid_neural()
    labels['maximum_resident_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    atomic_json(output / 'evaluator-detail.json', {**labels, 'reports': reports}, exclusive=True)
    atomic_json(output / 'public-summary.json', {**labels, 'policies': {
                p: reports[p]['development_metrics'] for p in POLICIES}}, exclusive=True)


def evaluate_recovery(seal_root, seal_sha256, output_root, *, proof_only=False):
    """Launch a new CPU-only child; proof_only never accesses evaluator assets."""
    need(type(proof_only) is bool, 'proof_only_boolean')
    seal, c, _, _, _ = verify_recovery(seal_root, seal_sha256)
    output = output_separated(output_root, c, seal['contract']['path'])
    data.separated(output, seal_root)
    need(not output.exists(), 'evaluation_identity_consumed')
    remaining = min(60.0, c['original']['deadline_epoch'] - time.time())
    need(remaining > 0, 'original_deadline_elapsed')
    output.mkdir(parents=True)
    request = {'seal_root': str(Path(seal_root).absolute()), 'seal_sha256': seal_sha256,
               'output_root': str(output), 'proof_only': proof_only}
    atomic_json(output / 'request.json', request, exclusive=True)
    with (output / 'stdout.txt').open('xb') as out, (output / 'stderr.txt').open('xb') as err:
        child = subprocess.Popen([sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve()),
                                  '--worker', str(output / 'request.json')], cwd=output,
             stdout=out, stderr=err, start_new_session=True, close_fds=True,
             env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'HF_HUB_OFFLINE': '1',
                  'TRANSFORMERS_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1'})
        try:
            child.wait(timeout=remaining)
        except BaseException:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            raise
    receipt = {'format': 'irisx/archived-cpu-process-receipt-v1', 'returncode': child.returncode,
               'owned_process_stopped': child.poll() is not None, 'proof_only': proof_only,
               'prediction_seal_sha256': seal_sha256, 'original_provider_status': 'ERROR',
               'cpu_only': True, 'limits': {'address_space_bytes': 512 * MIB, 'cpu_seconds': 45,
                                          'output_file_bytes': 32 * MIB}}
    atomic_json(output / 'process-receipt.json', receipt, exclusive=True)
    need(child.returncode == 0, 'isolated_archived_evaluator_failed')
    verify_recovery(seal_root, seal_sha256)
    name = 'proof-only.json' if proof_only else 'public-summary.json'
    return parse(data.read_regular(output / name))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--contract', required=True); prepare.add_argument('--contract-sha256', required=True)
    prepare.add_argument('--output', required=True)
    for command in ('verify', 'score'):
        item = sub.add_parser(command)
        item.add_argument('--seal-root', required=True); item.add_argument('--seal-sha256', required=True)
        item.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = prepare_recovery(args.contract, args.contract_sha256, args.output)
    else:
        result = evaluate_recovery(args.seal_root, args.seal_sha256, args.output, proof_only=args.command == 'verify')
    # The full scorer report is retained in its normal output files, not surfaced
    # accidentally in a repair/status log. No correctness interpretation here.
    print(json.dumps({k: result[k] for k in ('status', 'path', 'sha256', 'recovery_id',
          'original_provider_status', 'tasks', 'tests', 'public_answers_opened', 'maximum_resident_kib')
          if k in result}, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        try:
            _isolated(parse(data.read_regular(sys.argv[2])))
        except Exception as exc:
            sys.stderr.write('isolated archived evaluator rejected evidence: ' + type(exc).__name__ + '\n')
            raise SystemExit(2)
    else:
        main()
