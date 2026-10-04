"""Independent closed-archive reader for the bounded native trained solve."""
from __future__ import annotations
import argparse
from array import array
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.canonical import digest_value
from irisx.arc_nvarc_combined import atomic, sha
from tools.stage_nvarc_native_solve import preflight, construct
from tools.nvarc_native_solve_runtime import require, grid_key, compare_vectors



def qualified_outcome(terminal, result, failure_evidence):
    """A failed child or later parent step can never become inconclusive/success."""
    require(terminal['outcome'] in {'complete', 'failed'} and
            result['outcome'] in {'complete', 'inconclusive', 'failed'} and
            isinstance(result.get('failures'), list), 'known terminal/pipeline outcome required')
    failures = result['failures']
    require(all(isinstance(row, dict) and set(row) == {'phase', 'error_type', 'error_message'} and
                row['phase'] in {'pipeline', 'optimizer_cleanup', 'adapter_restoration', 'post_reset_control'} and
                isinstance(row['error_type'], str) and row['error_type'] and
                isinstance(row['error_message'], str) for row in failures), 'known failure evidence required')
    if result['outcome'] == 'failed':
        require(terminal['outcome'] == 'failed' and failures and
                failure_evidence == {'failures': failures}, 'failed pipeline needs retained exact failure evidence')
    else:
        require(not failures and failure_evidence is None, 'nonfailure pipeline contradicts failure evidence')
    return 'failed' if terminal['outcome'] == 'failed' else result['outcome']


def validate_batch_coverage(solve):
    coverage = solve['generation_batch_coverage']
    require(isinstance(coverage, list) and len(coverage) == solve['completed_generation_batches'] and
            solve['attempted_source_views'] == 4*len(coverage), 'source attempted-view denominator differs')
    for index, row in enumerate(coverage):
        ids = row['returned_row_ids']
        require(row['batch_index'] == index and row['attempted_views'] == 4 and
            isinstance(ids, list) and all(type(i) is int and 0 <= i < 4 for i in ids) and
            ids == sorted(set(ids)) and row['absent_rows'] == 4-len(ids) and
            type(row['explicit_empty_rows']) is int and 0 <= row['explicit_empty_rows'] <= len(ids) and
            row['rows_with_sequences'] == len(ids)-row['explicit_empty_rows'] and
            row['empty_rows'] == row['absent_rows']+row['explicit_empty_rows'], 'source sparse-row coverage differs')
    require(solve['source_views_without_sequences'] == sum(row['empty_rows'] for row in coverage),
            'source empty-row count differs')
    return coverage


def verify(archive, package):
    checked = preflight(package)
    plan = json.loads((package / 'plan.json').read_bytes())
    admission = package / 'controller-admission.json'
    _, raw, _, _ = construct(plan['run_id'], admission if admission.is_file() else None)
    content = {}
    with zipfile.ZipFile(archive) as stream:
        names = stream.namelist()
        require(len(names) == len(set(names)) and
                sum(row.file_size for row in stream.infolist()) <= 16*1024**2,
                'closed bounded native solve archive required')
        manifest = json.loads(stream.read('manifest.json'))
        members = manifest['members']
        require(manifest['run_id'] == plan['run_id'] and manifest['plan_digest'] == checked['plan_digest'] and
                len(members) == len({r['path'] for r in members}) and
                set(names) == {r['path'] for r in members} | {'manifest.json'}, 'archive identity/closure differs')
        for row in members:
            path = PurePosixPath(row['path'])
            require(not path.is_absolute() and '..' not in path.parts and '\\' not in row['path'], 'unsafe result path')
            body = stream.read(row['path'])
            require(len(body) == row['bytes'] and hashlib.sha256(body).hexdigest() == row['sha256'], 'result member differs')
            content[row['path']] = body
    def read(name):
        return json.loads(content[name])
    require(read('plan.json') == plan and read('payload-bindings.json') ==
            {key: hashlib.sha256(body).hexdigest() for key, body in raw.items()}, 'returned input bindings differ')
    terminal = read('terminal.json')
    require(terminal['run_id'] == plan['run_id'] and terminal['outcome'] in {'complete', 'failed'} and
            terminal['contains_evaluator_truth'] is False and terminal['teacher_calls'] == terminal['paid_usd'] == 0 and
            0 <= terminal['wall_seconds'] <= plan['maximum_notebook_wall_seconds'], 'bounded terminal differs')
    proof = {'run_id': plan['run_id'], 'plan_digest': checked['plan_digest'], 'archive_sha256': sha(archive),
             'closed_members': len(content), 'process_outcome': terminal['outcome'],
             'trained_solve_gate': False, 'correctness_scored': False, 'full_numerical_parity_claim': False,
             'teacher_calls': 0, 'paid_usd': 0}
    if 'native/pipeline-result.json' not in content:
        require(terminal['outcome'] == 'failed', 'successful process must retain pipeline evidence')
        proof.update(outcome='failed-before-pipeline-result', failure_phase=terminal['phase'])
        return proof
    for name, key in [('inspection.py', 'worker'), ('inspection_helpers.py', 'helper'),
        ('solver.py', 'solver'), ('arc_loader.py', 'loader'), ('arc_decoder.py', 'decoder'),
        ('nvarc_native_solve_runtime.py', 'solve_runtime'), ('visible.json', 'visible'),
        ('nvarc_native_ttt_budget.py', 'budget'), ('nvarc_native_ttt_schedule.py', 'schedule')]:
        require(content[name] == raw[key], 'actual retained native source differs')
    hardware = read('hardware.json')
    devices = hardware['inventory']
    require(hardware['torch'] == '2.8.0+cu128' and hardware['cuda'] == '12.8' and
        len(devices) == len({row['uuid'] for row in devices}) == 4 and
        all(row['name'] == 'NVIDIA L4' and row['bf16'] is True for row in devices) and
        read('native/hardware.json')['device_uuid'] == devices[0]['uuid'] and
        read('model-verification.json')['all_ten_files_verified'] is True and
        read('model-verification.json')['model_material_digest'] == plan['model_material_digest'] and
        read('source-verification.json')['inventory'] == json.loads(raw['source_inventory']),
        'native model/source/four-L4 envelope differs')
    events = [json.loads(line) for line in content.get('native/solve-events.jsonl', b'').splitlines()]
    reservations = [r for r in events if r['event'] == 'forward_reserved']
    completions = [r for r in events if r['event'] == 'forward_completed']
    require([r['call_id'] for r in reservations] == list(range(1, len(reservations)+1)) and
            len({r['call_id'] for r in completions}) == len(completions) and
            {r['call_id'] for r in completions}.issubset({r['call_id'] for r in reservations}),
            'one reservation per actual native call required')
    by_id = {r['call_id']: r for r in reservations}
    require(all(row['phase'] == by_id[row['call_id']]['phase'] for row in completions), 'completed call phase differs')
    counts = {phase: sum(r['phase'] == phase for r in reservations) for phase in plan['inference_forward_limits']}
    done = {phase: sum(r['phase'] == phase for r in completions) for phase in counts}
    require(sum(counts.values()) == len(reservations) and all(counts[p] <= n
            for p, n in plan['inference_forward_limits'].items()), 'native phase counts exceed plan')
    input_by_phase = {phase: sum(r['physical_input_tokens'] for r in reservations if r['phase'] == phase)
                      for phase in counts}
    require(input_by_phase['control'] <= 168 and sum(n for p,n in input_by_phase.items() if p != 'control') <=
            plan['maximum_inference_input_tokens'], 'physical input-token budget differs')
    result = read('native/pipeline-result.json')
    require(result['run_id'] == plan['run_id'] and result['plan_digest'] == digest_value(plan) and
            result['inference_forwards_reserved'] == counts and result['inference_forwards_completed'] == done and
            result['inference_input_tokens_by_phase'] == input_by_phase and
            result['inference_physical_input_tokens'] == sum(input_by_phase.values()) and
            result['contains_evaluator_truth'] is False and result['correctness_scored'] is False and
            result['checkpoint_exported'] is False and result['teacher_calls'] == result['paid_usd'] == 0,
            'pipeline identity/cost/isolation differs')
    outcome = qualified_outcome(terminal, result,
        read('native/pipeline-failure.json') if 'native/pipeline-failure.json' in content else None)
    proof.update(outcome=outcome, pipeline_outcome=result['outcome'], failures=result['failures'],
                 inference_forwards_reserved=counts,
                 inference_forwards_completed=done, inference_physical_input_tokens=sum(input_by_phase.values()))
    ledger = read('native/training-ledger.json') if 'native/training-ledger.json' in content else {
        'forwards': [], 'optimizer_steps': [], 'training_steps': []}
    for key in ('forwards', 'optimizer_steps', 'training_steps'):
        require(len(ledger[key]) <= 128 and all(type(r['completed']) is bool for r in ledger[key]), 'bounded training prefix required')
    actual_training = sum(r['completed'] for r in ledger['forwards'])
    actual_steps = sum(r['completed'] for r in ledger['optimizer_steps'])
    require(result['training_forwards'] == actual_training and result['optimizer_steps'] == actual_steps and
            terminal['model_forwards'] == actual_training + len(completions) and
            terminal['model_forwards_reserved'] == len(ledger['forwards']) + len(reservations) and
            terminal['optimizer_steps'] == actual_steps, 'parent/training/inference cost mismatch')
    proof.update(training_forwards=actual_training, optimizer_steps=actual_steps)
    if result['training_complete']:
        expected = json.loads(raw['expected_rows'])
        preparation = read('native/preparation.json')
        prepared = read('native/prepared-rows.json')
        require(preparation['trainer_origins'] == plan['native_trainer_origins'] and
            preparation['checkpoint_flags'] == plan['native_checkpoint_flags'] and
            preparation['prepared_rows_digest'] == digest_value(prepared) and
            preparation['blocked_attempts'] == 0 and len(prepared) == len(expected) == 128,
            'exact native preparation evidence differs')
        tokens = content['native/prepared-tokens.i16le']; offset = 0
        for row, wanted in zip(prepared, expected):
            count = wanted['input_tokens']; size = count * 4
            require(row['retained_byte_offset'] == offset and row['retained_token_bytes'] == size and
                    offset + size <= len(tokens), 'native token slice differs')
            values = array('h'); values.frombytes(tokens[offset:offset+size]); offset += size
            if sys.byteorder != 'little': values.byteswap()
            ids, labels = list(values[:count]), list(values[count:])
            require(digest_value(ids) == wanted['input_ids_digest'] == row['input_ids_digest'] and
                digest_value(labels) == wanted['labels_digest'] == row['labels_digest'] and
                sum(v >= 0 for v in labels[1:]) == wanted['supervised_tokens'], 'native prepared token/label bytes differ')
        require(offset == len(tokens), 'extra prepared token bytes')
        require(all(len(ledger[key]) == 128 and all(r['completed'] for r in ledger[key])
                    for key in ('forwards', 'optimizer_steps', 'training_steps')) and
            Counter((r['input_ids_digest'],r['labels_digest']) for r in ledger['forwards']) ==
            Counter((r['input_ids_digest'],r['labels_digest']) for r in expected) and
            sum(r['input_tokens'] for r in ledger['forwards']) == 955392 and
            sum(r['supervised_tokens'] for r in ledger['forwards']) == 476160,
            'complete original source epoch recount differs')
        schedule = read('native/native-schedule.json')['rates']
        require(len(schedule) == 129 and all(row['learning_rate'] == schedule[i]
                    and row['gradient_tensors'] == 506 and math.isfinite(row['gradient_norm_after_clip'])
                    and 0 <= row['gradient_norm_after_clip'] <= 1.05
                    for i,row in enumerate(ledger['optimizer_steps'])), 'actual native optimizer recipe differs')
        before, trained = read('native/baseline-inventory.json'), read('native/trained-inventory.json')
        require(len(before) == len(trained) == 506 and [r['name'] for r in before] == [r['name'] for r in trained] and
                all(r['finite'] is True for r in before + trained), 'finite saved tensor topology differs')
        proof['changed_tensor_count'] = sum(a['sha256'] != b['sha256'] for a,b in zip(before, trained))
        require(proof['changed_tensor_count'] > 0, 'training did not change any saved tensor')
    if result['all_saved_tensors_restored']:
        require(read('native/baseline-inventory.json') == read('native/reset-inventory.json'), 'exact reset evidence differs')
        proof['exact_reset_verified'] = True
    if result['solve'] is not None:
        require(read('native/solve-result.json') == result['solve'], 'retained solve evidence differs')
        coverage = validate_batch_coverage(result['solve'])
        generation_events = [r for r in events if r['event'] == 'generation_completed']
        require([r['source_result_coverage'] for r in generation_events] == coverage,
                'source batch event coverage differs')
    if outcome == 'complete':
        require(plan['approved'] is True and terminal['outcome'] == 'complete' and
                result['training_complete'] is True and result['all_saved_tensors_restored'] is True and
                result['optimizer_discarded'] is True and result['post_reset_control_verified'] is True and
                counts == done and counts['control'] == 7 and input_by_phase['control'] == 168,
                'complete pipeline qualification differs')
        controls = [r for r in events if r['event'] == 'cache_control_result']
        require(len(controls) == 1, 'one complete same-run cache control required')
        control = controls[0]
        recomputed = {'deep': compare_vectors(control['deep_reference'], control['deep_cached']),
                      'sibling_after_deep': compare_vectors(control['sibling_reference'], control['sibling_cached'])}
        require(control['comparisons'] == recomputed and all(r['gate_passed'] for r in recomputed.values()) and
                read('native/post-reset-control.json')['prefill_bitwise_equal'] is True and
                read('native/post-reset-control.json')['prefill'] == control['baseline_prefill'],
                'cache/reset control evidence differs')
        solve = read('native/solve-result.json')
        require(result['solve'] == solve and solve['outcome'] == 'complete' and
                solve['completed_generation_batches'] == 4 and solve['attempted_source_views'] == 16 and
                solve['nonempty_ranking'] is True and solve['correctness_scored'] is False and
                solve['original_convenience_scorer_called'] is False and
                1 <= len(solve['ranked_grids']) == solve['unique_candidates'] <= 64 and
                len({grid_key(g) for g in solve['ranked_grids']}) == len(solve['ranked_grids']) and
                solve['attempts'] == solve['ranked_grids'][:2], 'nonempty source ranking/coverage differs')
        require(sum(r['event'] == 'generation_reserved' for r in events) ==
                sum(r['event'] == 'generation_completed' for r in events) == terminal['generations'] == 4,
                'all four generation batch calls must complete')
        proof.update(trained_solve_gate=True, unique_candidates=solve['unique_candidates'],
                     generation_batches=4, attempted_views=16, post_reset_control_verified=True)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'package', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'new independent native-solve proof required')
    proof = verify(args.archive, args.package)
    atomic(args.output, proof)
    print(json.dumps(proof))
