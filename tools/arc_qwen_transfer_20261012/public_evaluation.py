"""One-way, source-bound PUBLIC120 scoring for the real-ARC transfer runtime.

This CPU-only bridge never generates answers or imports a model implementation.
It rebuilds the single frozen-SFT pool from retained native receipts and physical
work, then uses the unchanged historical scorer. The boundary is trusted fixed
code and stopped owned processes, not secrecy from arbitrary same-UID programs.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ''):
    sys.path[:0] = [str(ROOT), str(ROOT / 'src')]

from tools.arc_kaggle_submission import parse_json, require
from tools.arc_public_research_20261010.public_data import (
    read_regular, write_new, inventory, verify_inventory, load_solver_tasks,
    validate_manifest, verify_upstream_inventory, git_object_sha, separated,
    safe_path, hash_string, sha256, EXPOSURE)
from tools.arc_public_research_20261010.public_evaluator import SCORER_PINS
from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof, OwnedProcessGuard
from tools.arc_learning_agent_20261011.grid_codec import decode_grid, validate_grid, grid_messages
from tools.arc_qwen_probe_20261012.protocol import digest
from tools.arc_qwen_transfer_20261012.arc_adaptation import Transform
from tools.arc_offline_evaluation import POOL_FORMAT, validate_pools
from tools.nvarc_native_multitask import digest as scorer_digest

SOLVER_MANIFEST_SHA256 = '549019b4b5cb47176f3abd3fcd9ca516e91b7d6e581dfc414a5a6452ff7b1f7f'
EVALUATOR_MANIFEST_SHA256 = 'c7e8ad35770a66a71a22cccbbd0455c1c3bcc1a505dfb2e4c29819eec6209e33'
PUBLIC_MATERIAL_SHA256 = 'c55073f8e9f44682dd7d7f31ee7f04f39754a9922ec246073555026452f047e3'
SEAL_FORMAT = 'irisx/transfer-public-prediction-seal-v1'
REPORT_FORMAT = 'irisx/transfer-public-evaluation-v1'
ARTIFACT_FORMAT = 'irisx/transfer-public-predictions-v1'
METHOD = 'true-arc-transfer/frozen-selected-grid-model-identity-d4-top2'
MAX_EVIDENCE_BYTES = 96 * 1024**2


def source_identity():
    """The actual successor source closure, not the historical source pack."""
    result = {p.relative_to(ROOT).as_posix(): sha256(read_regular(p))
              for p in sorted(ROOT.rglob('*')) if p.is_file() and
              p.suffix in ('.py', '.json', '.jinja') and '__pycache__' not in p.parts}
    require(all(result.get(k) == v for k, v in SCORER_PINS.items()), 'historical scorer source changed')
    return result


def check_source(expected):
    require(type(expected) is dict and expected == source_identity(), 'sealed executable source differs')


def _json(path, expected=None):
    return parse_json(read_regular(path, expected))


def _exact(value, keys, name):
    require(type(value) is dict and set(value) == set(keys), name + ' schema differs')


def _relative(path, owner):
    path = Path(path)
    path = owner / path if not path.is_absolute() else path
    safe_path(path)
    require(path.is_relative_to(owner) and path != owner, 'evidence escapes original owner output')
    return path.relative_to(owner).as_posix()


def _no_evaluator_config(value):
    if type(value) is dict:
        for key, child in value.items():
            require(type(key) is str and not any(word in key.lower() for word in ('evaluator', 'answer', 'gold')),
                    'evaluator/answer configuration forbidden in model child')
            _no_evaluator_config(child)
    elif type(value) is list:
        for child in value: _no_evaluator_config(child)


def _ledger(raw):
    """Authenticate the complete physical-work chain and settled reservations."""
    rows = [parse_json(line) for line in raw.splitlines() if line]
    require(rows and len(rows) <= 100000, 'bounded nonempty physical ledger required')
    previous = '0' * 64; pending = {}; settled = {}; totals = {}
    for index, row in enumerate(rows):
        require(type(row) is dict and row.get('index') == index and row.get('previous') == previous,
                'physical ledger chain differs')
        require(row.get('sha256') == digest({k: v for k, v in row.items() if k != 'sha256'}),
                'physical ledger event digest differs')
        previous = row['sha256']; kind = row.get('event')
        if index == 0:
            require(kind == 'opened' and type(row.get('caps')) is dict, 'physical ledger opening required')
            totals = dict.fromkeys(row['caps'], 0)
            continue
        event = row.get('event_id')
        require(type(event) is str and event, 'physical event identity required')
        if kind == 'reserved':
            require(event not in pending and event not in settled and not pending, 'duplicate or unresolved physical work')
            amounts = row.get('amounts')
            require(type(amounts) is dict and amounts and set(amounts) <= set(totals) and
                    all(type(v) is int and v >= 0 for v in amounts.values()), 'physical reservation amounts differ')
            pending[event] = amounts
        elif kind in ('complete', 'failed', 'excluded'):
            amounts = row.get('amounts'); cap = pending.pop(event, None)
            require(cap is not None and type(amounts) is dict and set(amounts) == set(cap) and
                    all(type(v) is int and 0 <= v <= cap[k] for k, v in amounts.items()), 'unbound physical settlement')
            settled[event] = row
            for key, val in amounts.items(): totals[key] += val
        else:
            raise ValueError('unknown or unresolved physical work blocks scoring')
    require(not pending, 'pending physical work blocks scoring')
    require(all(totals[k] <= rows[0]['caps'][k] for k in totals), 'physical caps exceeded')
    return settled, totals


def _owner(proof, request, request_sha, read):
    verify_closed_proof(proof)
    require(proof['returncode'] == proof['worker_returncode'] == 0 and proof['forced'] is False,
            'failed or forced owner cannot score')
    launch = _json_bytes(read('owned-tree/launch.json'))
    child = _json_bytes(read('owned-tree/worker-launch.json'))
    persisted = _json_bytes(read('owned-tree/closure.json'))
    require(persisted == proof and launch.get('supervisor_identity') == proof['root_identity'] and
            child.get('supervisor_identity') == proof['root_identity'] and
            child.get('worker_identity') in proof['owned_identities'], 'foreign owner proof binding')
    argv = launch.get('worker_argv')
    require(type(argv) is list and len(argv) >= 3 and argv[-2:] == [str(Path(request['output_root']) / 'request.json'), request_sha],
            'owner request execution binding differs')
    fixture = request['config'].get('test_public_evaluation_fixture') is True
    require((fixture and '--fixture-owner' in argv) or
            argv[-3] == str(ROOT / 'tools/arc_qwen_transfer_20261012/child.py'),
            'wrong source worker entrypoint')
    parent = launch.get('coordinator_identity', {})
    from tools.arc_learning_agent_20261011.process_guard import _read_process
    current = _read_process(parent.get('pid'))
    require(current is not None and current['birth'] == parent.get('birth') and
            parent['pid'] in (os.getpid(), os.getppid()), 'foreign or expired coordinator incarnation')


def _json_bytes(raw):
    return parse_json(raw)


def _native_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _packing(compact, receipt, read, task, case_id, *, tiny):
    packing = parse_json(read(str(Path(compact['receipt_path']).with_suffix('.packing.json'))))
    require(packing.get('format') == 'irisx/whole-demonstration-packing-v1' and
            packing.get('task_id') == case_id and packing.get('query_targets_used') is False and
            packing.get('partial_grids_or_targets_truncated') is False and packing.get('withheld_demo_id') is None and
            packing.get('context_limit') == 4096 and packing.get('output_cap') == 1024,
            'bound whole-demonstration query packing required')
    if packing.get('admitted') is not True:
        require(packing.get('admitted') is False and compact['prediction'] is None and
                compact['dispatched'] is False and compact['physical_event_id'] is None and
                receipt.get('valid') is False and receipt.get('dispatched') is False and
                receipt.get('finish_reason') == 'context_excluded' and receipt.get('whole_example_excluded') is True,
                'unexecuted context exclusion receipt differs')
        return False
    selected = packing.get('selected_demo_ids')
    require(type(selected) is list and selected and all(type(v) is str and v.isdigit() for v in selected),
            'complete demonstration identities required')
    indices = [int(v) for v in selected]
    require(indices == sorted(set(indices)) and all(0 <= i < len(task['train']) for i in indices) and
            packing.get('omitted_demo_ids') == [str(i) for i in range(len(task['train'])) if i not in indices],
            'foreign or duplicated demonstration packing')
    transform = Transform(compact['transform_d4'])
    demos = [{k: [list(row) for row in transform.apply(task['train'][i][k])] for k in ('input', 'output')} for i in indices]
    query = [list(row) for row in transform.apply(task['query'])]
    messages = grid_messages(demos, query)
    # Exact expansion of the authenticated Qwen template's two plain-message
    # branch (no tools, history or thinking). No tokenizer/model import needed.
    expected = ''.join('<|im_start|>' + m['role'] + '\n' + m['content'] + '<|im_end|>\n' for m in messages)
    expected += '<|im_start|>assistant\n<think>\n\n</think>\n\n'
    prompt = packing.get('prompt')
    require(type(prompt) is str and prompt == expected and packing.get('prompt_sha256') == _native_digest(prompt) and
            receipt.get('rendered_prompt_sha256') == sha256(prompt.encode()) and
            type(packing.get('prompt_tokens')) is int and 0 < packing['prompt_tokens'] <= 3072 and
            receipt.get('input_tokens') == packing['prompt_tokens'], 'native prompt does not bind this transformed query/demos')
    return True


def _generation(compact, read, events, used_events, method, task, case_id, *, tiny):
    _exact(compact, ('transform_d4', 'inverse_applied', 'prediction', 'dispatched',
                    'physical_event_id', 'receipt_sha256', 'receipt_path'), 'generation binding')
    require(type(compact['transform_d4']) is int and compact['transform_d4'] in (0, 1) and
            compact['inverse_applied'] is True and type(compact['dispatched']) is bool,
            'fixed identity/D4 inverse required')
    raw = read(compact['receipt_path']); require(sha256(raw) == hash_string(compact['receipt_sha256']), 'native receipt hash differs')
    receipt = parse_json(raw); event = compact['physical_event_id']
    if not _packing(compact, receipt, read, task, case_id, tiny=tiny): return None, False
    require(type(receipt) is dict and event == receipt.get('physical_event_id') and
            event in events and event not in used_events, 'reused or unbound native physical event')
    used_events.add(event); amounts = events[event]['amounts']
    require(compact['dispatched'] is receipt.get('dispatched') and
            amounts == {'generation_calls': int(compact['dispatched']),
                        'input_tokens': receipt.get('forward_input_tokens'), 'output_tokens': receipt.get('output_tokens')},
            'native physical receipt amounts differ')
    require(receipt.get('tiny_cpu') is tiny, 'native generation origin differs')
    prediction = None
    if receipt.get('valid') is True:
        ids = receipt.get('output_token_ids'); eos = receipt.get('native_eos_ids')
        require(receipt.get('dispatched') is True and receipt.get('model_forward_started') is True and
                receipt.get('finish_reason') == 'eos' and events[event]['event'] == 'complete' and
                type(ids) is list and ids and all(type(v) is int and 0 <= v < 151936 for v in ids) and
                type(eos) is list and ids[-1] in eos and not any(v in eos for v in ids[:-1]) and
                receipt.get('output_tokens') == len(ids) and receipt.get('output_sha256') == hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest(),
                'complete native EOS receipt required')
        require(receipt.get('adapter_state_sha256') == method['adapter_sha256'], 'selected adapter generation binding differs')
        hash_string(receipt.get('adapter_fingerprint'))
        require(receipt.get('adapter_execution_mode') == ('base' if method['role'] == 'frozen_base' else 'trained'), 'native adapter execution mode differs')
        prediction = [list(row) for row in Transform(compact['transform_d4']).inverse().apply(decode_grid(receipt['text']))]
    if compact['prediction'] is not None: validate_grid(compact['prediction'])
    require(compact['prediction'] == prediction, 'selected prediction differs from native generated text/inverse')
    return prediction, receipt.get('dispatched') is True


def make_pool(challenges, artifact, *, read, events, run_id, elapsed_seconds, tiny):
    """Truth-free reconstruction. Omitted slots always retain the 167 denominator."""
    _exact(artifact, ('format', 'solver_manifest_sha256', 'method', 'predictions', 'case_receipts',
                     'case_count', 'test_answers_read', 'physical_pending', 'plan_sha256'), 'prediction artifact')
    require(artifact['format'] == ARTIFACT_FORMAT and artifact['test_answers_read'] is False and
            artifact['physical_pending'] == {}, 'closed truth-free predictions required')
    hash_string(artifact['plan_sha256']); method = artifact['method']
    _exact(method, ('candidate_id', 'role', 'checkpoint_manifest_sha256', 'adapter_sha256'), 'frozen method')
    require(method['candidate_id'] in ('base', 'sft64', 'sft256') or tiny and method['candidate_id'] in ('sft1', 'sft2'),
            'single frozen selected-model method required')
    require(method['role'] == ('frozen_base' if method['candidate_id'] == 'base' else 'global_sft'), 'selected model role differs')
    hash_string(method['checkpoint_manifest_sha256']); hash_string(method['adapter_sha256'])
    proposed = artifact['predictions']; cases = artifact['case_receipts']
    require(type(proposed) is dict and set(proposed) <= set(challenges) and type(cases) is list and
            type(artifact['case_count']) is int and artifact['case_count'] == len(cases) <= 167,
            'prediction/case denominator differs')
    for key, values in proposed.items():
        require(type(values) is list and len(values) == len(challenges[key]['test']), 'omitted or extra test prediction slot')
        for item in values:
            _exact(item, ('attempt_1', 'attempt_2'), 'top-two answer')
            for value in item.values():
                if value is not None: validate_grid(value)
    by_case = {}; used_events = set(); calls = 0
    for case in cases:
        _exact(case, ('parent_id', 'test_index', 'input_sha256', 'generations'), 'query receipt')
        key, index = case['parent_id'], case['test_index']; identity = (key, index)
        require(key in challenges and type(index) is int and 0 <= index < len(challenges[key]['test']) and
                identity not in by_case and case['input_sha256'] == digest(challenges[key]['test'][index]['input']),
                'foreign, shuffled or duplicate multi-test query binding')
        generations = case['generations']
        require(type(generations) is list and [g.get('transform_d4') for g in generations] in ([], [0], [0, 1]),
                'registered generation order differs')
        answers = []
        for compact in generations:
            answer, dispatched = _generation(compact, read, events, used_events, method,
                {'train': challenges[key]['train'], 'query': challenges[key]['test'][index]['input']},
                'public:' + key + ':' + str(index), tiny=tiny)
            calls += int(dispatched)
            if answer is not None and answer not in answers: answers.append(answer)
        expected = {'attempt_1': answers[0] if answers else None, 'attempt_2': answers[1] if len(answers) > 1 else None}
        require(key in proposed and proposed[key][index] == expected, 'top-two answers differ from ordered unique native predictions')
        by_case[identity] = {'answers': answers, 'complete': len(generations) == 2 and all(g['dispatched'] for g in generations)}
    records = []
    for key, task in sorted(challenges.items()):
        tests = []
        for index, query in enumerate(task['test']):
            row = by_case.get((key, index))
            if row is None:
                require(key not in proposed or proposed[key][index] == {'attempt_1': None, 'attempt_2': None}, 'answer lacks query execution receipt')
                continue
            tests.append({'test_index': index, 'input_digest': scorer_digest(query['input']), 'ranked_grids': row['answers'],
                          'status': 'complete' if row['complete'] else 'partial' if row['answers'] else 'not_executed'})
        records.append({'task_id': key, 'task_digest': scorer_digest(task), 'tests': tests, 'timings': {}})
    pool = {'format': POOL_FORMAT, 'run_id': run_id, 'method': METHOD, 'challenges_digest': scorer_digest(challenges),
            'records': records, 'parent_wall_seconds': elapsed_seconds}
    validate_pools(challenges, pool)
    return pool, {'observed_queries': len(by_case), 'generation_calls': calls,
                  'complete_coverage': len(by_case) == 167 and all(r['complete'] for r in by_case.values())}


def _bound_ref(ref, read):
    _exact(ref, ('path', 'sha256'), 'runtime evidence reference')
    raw = read(ref['path']); require(sha256(raw) == hash_string(ref['sha256']), 'runtime evidence bytes differ')
    return parse_json(raw)


def _runtime(result, artifact, read, *, tiny):
    evidence = result.get('runtime_evidence')
    require(type(evidence) is dict, 'runtime evidence required')
    if tiny:
        require(result.get('production_model') is not True, 'fixture cannot claim production model')
        return False
    _exact(evidence, ('model_admission', 'calibration', 'frozen_selection', 'checkpoint_manifest'), 'production runtime evidence')
    admission = _bound_ref(evidence['model_admission'], read)
    identity = admission.get('identity'); hardware = admission.get('hardware', {})
    require(type(identity) is dict and identity == {k: v for k, v in result.get('model_identity', {}).items() if k not in ('decoder_policy', 'decoder_policy_sha256')}, 'model admission/result identity differs')
    required = {'model_key': 'qwen3-14b', 'model_id': 'Qwen/Qwen3-14B',
                'revision': '40c069824f4251a91eefaf281ebe4c544efd3e18',
                'profile_id': 'qwen3-14b-native-bf16-r8-c4096-transfer-v1',
                'execution_mode': 'native-qwen3-pretrained-c4096-transfer',
                'pretrained_weights_loaded': True, 'random_test_weights': False,
                'full_vocabulary_rows': 151936, 'base_precision': 'bfloat16',
                'all_eight_weight_sha256_verified': True, 'verified_tensor_count': 443,
                'verified_tensor_elements': 14768307200, 'context_limit': 4096,
                'prompt_cap': 3072, 'output_cap': 1024}
    require(all(type(identity.get(k)) is type(v) and identity[k] == v for k, v in required.items()),
            'actual production native model evidence differs')
    require(result.get('production_model') is True and hardware.get('visible_device_count') == 1 and
            hardware.get('bf16_supported') is True and hardware.get('fp8_admitted') is False and
            hardware.get('four_l4_tp_admitted') is False, 'actual single-device BF16 runtime required')
    require(type(identity.get('environment')) is dict and identity['environment'], 'verified actual runtime environment required')
    calibration = _bound_ref(evidence['calibration'], read)
    require(calibration.get('status') == 'complete' and calibration.get('completed_lengths') == [128, 512, 2048, 4096] and
            calibration.get('full_context_measured') is True and calibration.get('cpu_fixture_only') is False and
            calibration.get('full_state_restoration_verified') is True, 'production4096 calibration evidence required')
    selection = _bound_ref(evidence['frozen_selection'], read)
    require(selection.get('method') == artifact['method'] and selection.get('query_targets_used') is False and
            selection.get('selected_before_public_queries') is True, 'pre-query demo/dev-only frozen selection required')
    main = _bound_ref(selection['main_selection'], read)
    require(main.get('selection_sha256') == selection.get('selection_sha256') and
            main.get('candidate_id') == artifact['method']['candidate_id'] and
            main.get('selection_uses_holdout_targets') is False and
            main.get('selection_sha256') == digest({k: v for k, v in main.items() if k != 'selection_sha256'}), 'frozen main selection differs')
    rankings = main.get('rankings')
    require(type(rankings) is list and len(rankings) == 3 and
            {r.get('candidate_id') for r in rankings} == {'base', 'sft64', 'sft256'} and
            all(type(r.get('update')) is int and r['update'] == {'base': 0, 'sft64': 64, 'sft256': 256}[r['candidate_id']] and
                r.get('denominator') == 16 and all(type(r.get(k)) is int and 0 <= r[k] <= 16 for k in ('exact', 'shape', 'valid')) for r in rankings) and
            rankings == sorted(rankings, key=lambda r: (-r['exact'], -r['shape'], -r['valid'], r['update'])) and
            rankings[0]['candidate_id'] == main['candidate_id'], 'preregistered dev16 base/SFT64/SFT256 ranking differs')
    require(main.get('checkpoint', {}).get('manifest_sha256') == artifact['method']['checkpoint_manifest_sha256'] and
            main['checkpoint'].get('adapter_sha256') == artifact['method']['adapter_sha256'], 'selected checkpoint reference differs')
    checkpoint = _bound_ref(evidence['checkpoint_manifest'], read)
    require(evidence['checkpoint_manifest']['sha256'] == artifact['method']['checkpoint_manifest_sha256'] and
            checkpoint.get('format') == 'irisx/qwen-branch-safe-checkpoint-v1' and
            checkpoint.get('adapter_sha256') == artifact['method']['adapter_sha256'], 'frozen selected checkpoint differs')
    binding = checkpoint.get('binding', {})
    from .checkpoint_policy import GLOBAL, validate_contract
    require(binding.get('branch_id') == 'global_grid', 'PUBLIC checkpoint must bind global_grid branch')
    schedule = validate_contract(binding.get('checkpoint_schedule'), binding['branch_id'], checkpoint.get('update'))
    require(schedule['schedule_id'] == GLOBAL and binding.get('config', {}).get('tiny_cpu') is False,
            'PUBLIC production checkpoint must use production transfer schedule')
    require(checkpoint.get('update') == {'base': 0, 'sft64': 64, 'sft256': 256}[artifact['method']['candidate_id']] and
            binding.get('config', {}).get('objective_cycle') == ['grid'] and
            binding.get('precision') == 'bf16-base-fp32-lora' and binding.get('rank') == 8 and binding.get('alpha') == 16,
            'frozen SFT recipe differs')
    require(type(binding.get('source')) is dict and binding['source'] and
            all(result['_source_identity'].get(k) == v for k, v in binding['source'].items()), 'checkpoint source differs')
    return True


def _verify_bundle(request_raw, result_raw, proof, read, solver_root, solver_sha, evaluator_sha):
    request = parse_json(request_raw); result = parse_json(result_raw)
    require(type(request) is dict and type(result) is dict and type(request.get('config')) is dict, 'bound child request/result required')
    check_source(request.get('source_identity'))
    fixture = request['config'].get('test_public_evaluation_fixture') is True
    require(not fixture or request['config'].get('tiny_cpu') is True, 'fixture seam must be explicitly tiny CPU')
    if not fixture:
        from tools.arc_qwen_transfer_20261012.protocol import validate_config
        require(request.get('format') == 'irisx/true-arc-transfer-request-v1', 'new runtime request identity required')
        validate_config(request['config'])
    _no_evaluator_config(request['config'])
    request_sha = sha256(request_raw)
    require(result.get('request_sha256') == request_sha and
            result.get('source_identity_sha256') == digest(request['source_identity']), 'foreign final result/source/request binding')
    require(result.get('status') in ('TRANSFER_COMPLETE', 'TRANSFER_PARTIAL') and result.get('model_stopped') is True and
            result.get('pending_work') == {} and result.get('physical_pending', {}) == {}, 'failed or unfinished model owner cannot score')
    _owner(proof, request, request_sha, read)
    config = request['config']
    require(config.get('public_solver_root') == str(solver_root) and
            config.get('public_solver_manifest_sha256') == solver_sha, 'solver config/request binding differs')
    tiny = config.get('tiny_cpu', False)
    require(type(tiny) is bool, 'exact fixture origin required')
    solver = load_solver_tasks(solver_root, solver_sha)
    mode = solver['manifest']['evidence_mode']
    require(tiny is (mode == 'synthetic-test-only'), 'synthetic and production asset origin mismatch')
    if not tiny:
        require(solver_sha == SOLVER_MANIFEST_SHA256 and evaluator_sha == EVALUATOR_MANIFEST_SHA256,
                'exact production PUBLIC120 manifest pins required')
        require(not any(k.startswith('test_') for k in config), 'fixture seam forbidden for production')
    branch = result.get('public_branch')
    require(type(branch) is dict and branch.get('status') in ('PUBLIC_PREDICTIONS_SEALED', 'PUBLIC_PARTIAL', 'complete', 'partial') and
            branch.get('solver_manifest_sha256') == solver_sha, 'closed public solve phase required')
    raw = read(branch['artifact_path']); require(sha256(raw) == hash_string(branch['artifact_sha256']), 'prediction artifact result binding differs')
    artifact = parse_json(raw)
    require(artifact.get('solver_manifest_sha256') == solver_sha and artifact.get('method') == branch.get('method'),
            'public solver/method binding differs')
    if not fixture:
        from tools.arc_qwen_transfer_20261012.protocol import PROTOCOL
        require(artifact.get('plan_sha256') == digest(PROTOCOL), 'source-bound public plan differs')
    events, totals = _ledger(read('physical-work.jsonl'))
    require(result.get('physical_usage') == totals, 'physical ledger/final result totals differ')
    run_id = result.get('run_id', 'transfer-' + request_sha[:24])
    pool, coverage = make_pool(solver['challenges'], artifact, read=read, events=events, run_id=run_id,
                              elapsed_seconds=result.get('elapsed_seconds'), tiny=tiny)
    require(branch.get('actual_generation_calls') == coverage['generation_calls'], 'public generation count differs')
    require(branch.get('cases') == coverage['observed_queries'], 'public observed query count differs')
    if not tiny:
        require(result.get('main_complete') is True and result.get('science_complete') is True and totals.get('training_steps', 0) >= 256,
                'primary real-grid256 SFT completion required before public measurement')
    admitted = _runtime({**result, '_source_identity': request['source_identity']}, artifact, read, tiny=tiny)
    complete = coverage['complete_coverage'] and branch['status'] in ('PUBLIC_PREDICTIONS_SEALED', 'complete') and result['status'] == 'TRANSFER_COMPLETE'
    return request, result, solver, pool, {**coverage, 'complete': complete, 'production_eligible': admitted and complete and result.get('operational_success') is True and result.get('error') is None,
                                         'evidence_mode': mode, 'method': artifact['method']}


def seal_predictions(prediction_root, *, solver_root, solver_manifest_sha256,
                     evaluator_manifest_sha256, request_path, result_path, owner_proof):
    """Seal only after the owned model tree has stopped. No evaluator reads."""
    root, solver_root = separated(prediction_root, solver_root)
    require(not root.exists(), 'prediction identity consumed')
    request_path, result_path = safe_path(request_path), safe_path(result_path)
    owner = request_path.parent
    require(request_path.name == 'request.json' and result_path.parent == owner and
            result_path.name == 'child-summary.json', 'owner request/result path roles differ')
    separated(owner, solver_root)
    require(root != owner and not owner.is_relative_to(root), 'prediction root cannot replace owner evidence')
    request_raw, result_raw = read_regular(request_path), read_regular(result_path)
    request = parse_json(request_raw)
    require(request.get('output_root') == str(owner), 'foreign owner output root')
    collected = {}; total = 0
    def read(path):
        nonlocal total
        relative = _relative(path, owner)
        if relative not in collected:
            raw = read_regular(owner / relative); total += len(raw)
            require(total <= MAX_EVIDENCE_BYTES and len(collected) < 2048, 'sealed evidence byte/file ceiling exceeded')
            collected[relative] = raw
        return collected[relative]
    _, _, solver, pool, execution = _verify_bundle(request_raw, result_raw, owner_proof, read,
                solver_root, hash_string(solver_manifest_sha256), hash_string(evaluator_manifest_sha256))
    root.mkdir(parents=True)
    write_new(root / 'request.json', request_raw, raw=True)
    write_new(root / 'solver-result.json', result_raw, raw=True)
    write_new(root / 'owner-proof.json', owner_proof)
    write_new(root / 'pool.json', pool)
    for name, raw in collected.items(): write_new(root / 'evidence' / name, raw, raw=True)
    seal = {'format': SEAL_FORMAT, 'phase': 'predictions-sealed-generation-closed',
            'request_sha256': sha256(request_raw), 'result_sha256': sha256(result_raw),
            'source_identity_sha256': digest(request['source_identity']),
            'solver_manifest_sha256': solver_manifest_sha256, 'evaluator_manifest_sha256': evaluator_manifest_sha256,
            'identity': solver['identity'], 'execution': execution, 'files': inventory(root),
            'generation_may_resume': False}
    written = write_new(root / 'prediction-seal.json', seal)
    verify_seal(root, written['sha256'], solver_root)
    return {'path': str(root / 'prediction-seal.json'), 'sha256': written['sha256']}


def verify_seal(prediction_root, seal_sha256, solver_root):
    root, solver_root = separated(prediction_root, solver_root)
    seal = _json(root / 'prediction-seal.json', seal_sha256)
    _exact(seal, ('format', 'phase', 'request_sha256', 'result_sha256', 'source_identity_sha256',
                  'solver_manifest_sha256', 'evaluator_manifest_sha256', 'identity', 'execution', 'files', 'generation_may_resume'), 'prediction seal')
    require(seal['format'] == SEAL_FORMAT and seal['phase'] == 'predictions-sealed-generation-closed' and
            seal['generation_may_resume'] is False, 'closed prediction seal required')
    verify_inventory(root, seal['files'], exclude=('prediction-seal.json',))
    request_raw = read_regular(root / 'request.json', seal['request_sha256'])
    result_raw = read_regular(root / 'solver-result.json', seal['result_sha256'])
    owner = safe_path(parse_json(request_raw)['output_root'])
    def read(path): return read_regular(root / 'evidence' / _relative(path, owner))
    request, result, solver, pool, execution = _verify_bundle(request_raw, result_raw, _json(root / 'owner-proof.json'), read,
                solver_root, seal['solver_manifest_sha256'], seal['evaluator_manifest_sha256'])
    require(seal['source_identity_sha256'] == digest(request['source_identity']) and seal['identity'] == solver['identity'] and
            seal['execution'] == execution and _json(root / 'pool.json') == pool, 'sealed source/execution/pool changed')
    return seal, solver, pool, result


def goal_met(eligible_complete_production, metrics):
    """The only terminal goal gate; provider status is never an input."""
    value = metrics['metrics']['pass_at_2']
    return (eligible_complete_production is True and metrics.get('tasks') == 120 and metrics.get('tests') == 167 and
            type(value.get('numerator')) is int and 151 <= value['numerator'] <= 167 and value.get('denominator') == 167)


def _worker(request):
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024**2, 16 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return _score_after_seal(request)


def _score_after_seal(request):
    """Testable CPU core; caller supplies no answers and cannot change scorer."""
    root, solver_root, evaluator_root, output = separated(request['prediction_root'], request['solver_root'],
                                                        request['evaluator_root'], request['output_root'])
    seal, solver, pool, result = verify_seal(root, request['seal_sha256'], solver_root)
    # FIRST EVALUATOR FILE OPEN. Every source/request/result/receipt/owner/pool
    # check above is truth-free and must succeed before crossing this boundary.
    manifest = validate_manifest(_json(evaluator_root / 'manifest.json', seal['evaluator_manifest_sha256']), role='evaluator')
    require(manifest['identity'] == solver['identity'] and manifest['source'] == solver['manifest']['source'] and
            manifest['evidence_mode'] == solver['manifest']['evidence_mode'], 'solver/evaluator source identity differs')
    verify_inventory(evaluator_root, manifest['files'], exclude=('manifest.json',))
    require(set(manifest['files']) == {'LICENSE', 'NOTICE', 'provenance.json', 'upstream-inventory.json'} |
            {'upstream/data/evaluation/' + key + '.json' for key in solver['challenges']}, 'evaluator file roles differ')
    upstream = _json(evaluator_root / 'upstream-inventory.json', manifest['source']['evaluation_inventory_sha256'])
    if manifest['evidence_mode'] == 'public-development':
        for name, expected in verify_upstream_inventory(upstream).items():
            require(git_object_sha('blob', read_regular(evaluator_root / 'upstream' / name)) == expected,
                    'pinned official Git task bytes differ')
    from tools.arc_offline_evaluation import load_pinned_reference, evaluate
    challenges, solutions, reference = load_pinned_reference(evaluator_root / 'upstream', evaluator_root / 'provenance.json')
    require(challenges == solver['challenges'] and reference['provenance_sha256'] == manifest['source']['provenance_sha256'],
            'full evaluator challenge projection/provenance differs')
    require(type(solutions) is dict and set(solutions) == set(challenges), 'exact answer task set required')
    for key, answers in solutions.items():
        require(type(answers) is list and len(answers) == len(challenges[key]['test']), 'exact answer query denominator required')
        for answer in answers: validate_grid(answer)
    report = evaluate(challenges, solutions, pool)
    del solutions
    verify_seal(root, request['seal_sha256'], solver_root)
    verify_inventory(evaluator_root, manifest['files'], exclude=('manifest.json',))
    require(not any(name.split('.')[0] in ('torch', 'transformers', 'peft', 'tensorflow') or
                    name.endswith(('native_model', 'qwen14b_model', 'model_provider')) for name in sys.modules),
            'model imports forbidden in CPU evaluator')
    metrics = report['development_metrics']
    require(metrics['tasks'] == 120 and metrics['tests'] == 167 and
            metrics['metrics']['pass_at_2']['denominator'] == 167, 'full PUBLIC120 scoring denominator required')
    eligible = seal['execution']['production_eligible'] and manifest['complete_official_pinned_set'] is True
    goal = goal_met(eligible, metrics)
    summary = {'format': REPORT_FORMAT, 'status': 'PUBLIC_EVALUATION_COMPLETE' if seal['execution']['complete'] else 'PUBLIC_EVALUATION_PARTIAL',
               'measurement': 'project-public-development', 'profile': 'PUBLIC120', 'tasks': 120, 'tests': 167,
               'method': METHOD, 'frozen_method': seal['execution']['method'], 'development_metrics': metrics,
               'primary_target': 'micro pass@2 >= 0.90; at least 151 of 167', 'goal_met': bool(goal),
               'eligible_complete_production_public_measurement': bool(eligible),
               'complete_prediction_coverage': seal['execution']['complete_coverage'],
               'observed_queries': seal['execution']['observed_queries'],
               'generation_calls': seal['execution']['generation_calls'],
               'prediction_origin': ('base_model_research' if seal['execution']['method']['role'] == 'frozen_base' else 'trained_model_research') if seal['execution']['evidence_mode'] == 'public-development' else 'synthetic_cpu',
               'evidence_mode': manifest['evidence_mode'], 'official_score': None,
               'competition_gpu_equivalent': False, 'competition_gpu_output': False,
               'four_l4_executed': False, 'fp8_executed': False, 'exposure': EXPOSURE,
               'complete_official_pinned_set': manifest['complete_official_pinned_set'],
               'source_commit': manifest['source']['commit'], 'source_identity_sha256': seal['source_identity_sha256'],
               'prediction_seal_sha256': request['seal_sha256'],
               'scorer_sha256': SCORER_PINS['tools/arc_offline_evaluation.py'],
               'physical_usage': result['physical_usage'],
               'generation_may_resume': False,
               'isolation': 'stopped owned processes and trusted fixed-code dataflow; no same-UID filesystem secrecy'}
    write_new(output / 'evaluator-detail.json', {**summary, 'report': report})
    write_new(output / 'public-summary.json', summary)
    return summary


def evaluate_sealed(prediction_root, seal_sha256, *, solver_root, evaluator_root, output_root, deadline):
    """One-shot bounded CPU subprocess. Never returns per-query correctness."""
    import signal
    require(type(deadline) in (int, float) and math.isfinite(deadline), 'finite scoring deadline required')
    root, solver, evaluator, output = separated(prediction_root, solver_root, evaluator_root, output_root)
    require(not output.exists(), 'evaluation identity consumed; no generation resumes')
    verify_seal(root, seal_sha256, solver)
    remaining = min(60.0, deadline - time.monotonic())
    if remaining <= 0:
        return {'status': 'SCORING_NOT_ADMITTED', 'goal_met': False, 'official_score': None}
    output.mkdir(parents=True)
    request = {'prediction_root': str(root), 'seal_sha256': seal_sha256, 'solver_root': str(solver),
               'evaluator_root': str(evaluator), 'output_root': str(output)}
    write_new(output / 'request.json', request)
    timed_out = False
    with (output / 'stdout.txt').open('xb') as out, (output / 'stderr.txt').open('xb') as err:
        child = subprocess.Popen([sys.executable, '-I', '-B', '-S', str(Path(__file__).resolve()),
                                  '--worker', str(output / 'request.json')], cwd=output, stdout=out, stderr=err,
                                 start_new_session=True, close_fds=True,
                                 env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'HF_HUB_OFFLINE': '1',
                                      'TRANSFORMERS_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1'})
        try:
            child.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            timed_out = True
            if child.poll() is None: os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
        except BaseException:
            if child.poll() is None: os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
            raise
    receipt = {'returncode': child.returncode, 'owned_process_stopped': child.poll() is not None,
               'timed_out': timed_out, 'prediction_seal_sha256': seal_sha256}
    write_new(output / 'process-receipt.json', receipt)
    if child.returncode != 0 or timed_out:
        return {'status': 'SCORING_BLOCKED', 'goal_met': False, 'official_score': None, **receipt}
    verify_seal(root, seal_sha256, solver)
    summary = _json(output / 'public-summary.json')
    require(summary.get('format') == REPORT_FORMAT and summary.get('prediction_seal_sha256') == seal_sha256,
            'foreign evaluator summary')
    return summary


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--fixture-owner':
        request = _json(safe_path(sys.argv[2]), sys.argv[3])
        require(request.get('config', {}).get('tiny_cpu') is True and
                request['config'].get('test_public_evaluation_fixture') is True,
                'explicit synthetic process fixture only')
    elif len(sys.argv) == 3 and sys.argv[1] == '--worker':
        try:
            _worker(_json(safe_path(sys.argv[2])))
        except Exception as exc:
            sys.stderr.write('isolated PUBLIC120 evaluator rejected evidence: ' + type(exc).__name__ + ': ' + str(exc)[:300] + '\n')
            raise SystemExit(2)
    else:
        raise SystemExit(2)
