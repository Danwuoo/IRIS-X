"""Independent closed-archive reader for the bounded native trained solve."""
from __future__ import annotations
import argparse
import ast
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
from tools.nvarc_native_solve_runtime import require, grid_key, compare_vectors, SOURCE_HASHES



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
    require(type(solve['completed_generation_batches']) is int and
            0 <= solve['completed_generation_batches'] <= 4 and
            isinstance(coverage, list) and len(coverage) == solve['completed_generation_batches'] and
            type(solve['reserved_generation_batches']) is int and
            len(coverage) <= solve['reserved_generation_batches'] <= 4 and
            solve['attempted_source_views'] == 4*solve['reserved_generation_batches'] and
            solve['completed_source_views'] == 4*len(coverage) and
            solve['unfinished_source_views'] == 4*(solve['reserved_generation_batches']-len(coverage)),
            'source attempted/completed/unfinished-view denominators differ')
    for index, row in enumerate(coverage):
        ids = row['returned_row_ids']
        require(row['batch_index'] == index and row['attempted_views'] == 4 and
            isinstance(ids, list) and all(type(i) is int and 0 <= i < 4 for i in ids) and
            ids == sorted(set(ids)) and row['absent_rows'] == 4-len(ids) and
            type(row['explicit_empty_rows']) is int and 0 <= row['explicit_empty_rows'] <= len(ids) and
            row['rows_with_sequences'] == len(ids)-row['explicit_empty_rows'] and
            row['empty_rows'] == row['absent_rows']+row['explicit_empty_rows'], 'source sparse-row coverage differs')
    require(solve['source_views_without_sequences'] == sum(row['empty_rows'] for row in coverage)
            + solve['unfinished_source_views'],
            'source empty-row count differs')
    return coverage


def validate_inference_events(events, plan):
    reservations = [r for r in events if r['event'] == 'forward_reserved']
    completions = [r for r in events if r['event'] == 'forward_completed']
    by_id = {}
    completed_ids = set()
    for event in events:
        if event['event'] == 'forward_reserved':
            shape = event['batch_shape']
            require(type(event['call_id']) is int and event['call_id'] == len(by_id)+1 and
                    event['phase'] in plan['inference_forward_limits'] and
                    isinstance(shape, list) and len(shape) == 2 and
                    all(type(v) is int for v in shape) and shape[0] == 4 and 1 <= shape[1] <= 8192 and
                    type(event['physical_input_tokens']) is int and
                    event['physical_input_tokens'] == shape[0]*shape[1] and
                    type(event['cached']) is bool and
                    type(event['position_start']) is int and type(event['position_end']) is int and
                    0 <= event['position_start'] <= event['position_end'] < 8192 and
                    event['position_end']-event['position_start'] == shape[1]-1 and
                    (event['cached'] or event['position_start'] == 0),
                    'bounded actual inference reservation differs')
            by_id[event['call_id']] = event
        elif event['event'] == 'forward_completed':
            require(type(event['call_id']) is int and event['call_id'] in by_id and
                    event['call_id'] not in completed_ids and
                    event['phase'] == by_id[event['call_id']]['phase'] and
                    event['output_contract'] in {'tuple-logits-cache', 'model-output-logits-cache'},
                    'completion must follow one matching reservation')
            completed_ids.add(event['call_id'])
    counts = {p: sum(r['phase'] == p for r in reservations) for p in plan['inference_forward_limits']}
    done = {p: sum(r['phase'] == p for r in completions) for p in counts}
    tokens = {p: sum(r['physical_input_tokens'] for r in reservations if r['phase'] == p) for p in counts}
    require(all(counts[p] <= n for p,n in plan['inference_forward_limits'].items()) and
            tokens['control'] <= plan['maximum_control_input_tokens'] and
            sum(n for p,n in tokens.items() if p != 'control') <= plan['maximum_inference_input_tokens'],
            'actual inference count/token ceiling differs')
    return reservations, completions, counts, done, tokens


def validate_solve_evidence(solve, events, raw):
    coverage = validate_batch_coverage(solve)
    generated = [r for r in events if r['event'] == 'generation_completed']
    reserved = [r for r in events if r['event'] == 'generation_reserved']
    require([r['batch_index'] for r in reserved] == list(range(len(reserved))) and
            all(r['view_count'] == 4 for r in reserved) and
            len(generated) <= len(reserved) <= 4 and
            solve['reserved_generation_batches'] == len(reserved) and
            [r['batch_index'] for r in generated] == list(range(len(generated))) and
            [r['source_result_coverage'] for r in generated] == coverage,
            'source generation reservation/coverage differs')
    require(solve['termination_reason'] in {'all_source_batches_completed', 'task_deadline',
            'inference_deadline', 'forward_limit', 'input_token_limit'} and
            solve['all_source_batches_completed'] is (len(generated) == 4) and
            solve['correctness_scored'] is False and solve['original_convenience_scorer_called'] is False,
            'source solve termination/isolation differs')
    parsed = [r for r in events if r['event'] == 'candidate_parsed']
    ranked = [r for r in events if r['event'] == 'candidate_ranked']
    require(type(solve['returned_sequences']) is int and
            type(solve['invalid_parsed_candidates']) is int and
            0 <= solve['invalid_parsed_candidates'] <= solve['returned_sequences'] <= 64 and
            solve['raw_candidates'] == len(parsed) == solve['returned_sequences']-solve['invalid_parsed_candidates'] and
            len(ranked) <= len(parsed), 'candidate parsing/verification accounting differs')
    grids = []
    if ranked:
        # Execute only the exact public formatter/inverse and four ranking definitions.
        # This reader has no solution loader, evaluator or model call.
        import numpy as np
        namespace = {'np': np, 'AutoTokenizer': object}
        for name, wanted in [('arc_loader.py', {'QwenFormatter', 'ArcDataset',
                'convert_grid_to_string', 'is_valid_solution', 'permute_mod'}),
                ('arc_decoder.py', {'hashable', 'score_sum', 'getter_kgmon', 'score_kgmon'})]:
            body = raw['loader' if name == 'arc_loader.py' else 'decoder']
            require(hashlib.sha256(body).hexdigest() == SOURCE_HASHES[name], 'exact reader source differs')
            nodes = [n for n in ast.parse(body).body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in wanted]
            require({n.name for n in nodes} == wanted, 'reader source definitions missing')
            exec(compile(ast.Module(body=nodes, type_ignores=[]), name, 'exec'), namespace)
        class Tokens:
            def decode(self, values):
                return ''.join('\n' if t == 10 else str(t) for t in values)
        formatter = namespace['QwenFormatter'](Tokens())
        candidates = {}
        scores_by_grid = {}
        for index, row in enumerate(ranked):
            require(row['source_view'] == parsed[index]['source_view'] and
                    row['candidate_grid'] == parsed[index]['candidate_grid'] and
                    row['beam_score'] == parsed[index]['beam_score'], 'ranked candidate differs from parsed prefix')
            tokens = row['source_tokens']
            require(isinstance(tokens, list) and 2 <= len(tokens) <= 931 and tokens[-1] == 15 and
                    all(type(t) is int and 0 <= t <= 10 for t in tokens[:-1]) and
                    type(row['beam_score']) in (int, float) and math.isfinite(row['beam_score']) and
                    0 <= row['beam_score'] < -math.log(.2) and
                    isinstance(row['source_view'], str) and row['source_view'].split('.')[0] == solve['task_id']+'_0' and
                    isinstance(row['score_aug'], list) and len(row['score_aug']) == 8 and
                    all(type(s) in (int,float) and math.isfinite(s) and s >= 0 for s in row['score_aug']),
                    'exact EOS/score/source-view candidate evidence required')
            array = formatter.convert_tokens_to_array(tokens)
            require(array is not None, 'retained source tokens must parse')
            solution = namespace['ArcDataset'].invert_mod(array, row['source_view'], inv_perm=True)
            require(solution.tolist() == row['candidate_grid'], 'retained source inverse differs')
            key = grid_key(row['candidate_grid'])
            require(parsed[index]['already_verified'] is (key in scores_by_grid) and
                    (key not in scores_by_grid or scores_by_grid[key] == row['score_aug']),
                    'duplicate votes must share one verified score vector')
            scores_by_grid[key] = row['score_aug']
            candidates[str(index)] = {**row, 'solution': solution}
        grids = [g.tolist() for g in namespace['score_kgmon'](candidates)]
    require(solve['ranked_grids'] == grids and solve['unique_candidates'] == len(grids) and
            solve['attempts'] == grids[:2] and solve['missing_attempts'] == max(0,2-len(grids)) and
            solve['nonempty_ranking'] is bool(grids) and
            solve['outcome'] == ('complete' if len(generated) == 4 and grids and
                solve['termination_reason'] == 'all_source_batches_completed' else 'inconclusive'),
            'independent inverse/deduplication/vote ranking differs')
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
    for key, limit in [('model_forwards', plan['maximum_outer_forwards']),
                       ('model_forwards_reserved', plan['maximum_outer_forwards']),
                       ('optimizer_steps', plan['maximum_optimizer_steps']),
                       ('optimizer_steps_reserved', plan['maximum_optimizer_steps']),
                       ('training_steps_reserved', plan['maximum_training_forwards']),
                       ('generations', plan['maximum_generations'])]:
        require(type(terminal[key]) is int and 0 <= terminal[key] <= limit,
                'bounded terminal work counter differs: ' + key)
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
    reservations, completions, counts, done, input_by_phase = validate_inference_events(events, plan)
    result = read('native/pipeline-result.json')
    require(result['run_id'] == plan['run_id'] and result['plan_digest'] == digest_value(plan) and
            result['inference_forwards_reserved'] == counts and result['inference_forwards_completed'] == done and
            result['inference_input_tokens_by_phase'] == input_by_phase and
            result['inference_physical_input_tokens'] == sum(input_by_phase.values()) and
            result['contains_evaluator_truth'] is False and result['correctness_scored'] is False and
            result['checkpoint_exported'] is False and result['teacher_calls'] == result['paid_usd'] == 0,
            'pipeline identity/cost/isolation differs')
    require(all(type(result[k]) is bool for k in ('training_complete', 'all_saved_tensors_restored',
            'post_reset_control_verified', 'optimizer_discarded')), 'explicit pipeline qualification flags required')
    outcome = qualified_outcome(terminal, result,
        read('native/pipeline-failure.json') if 'native/pipeline-failure.json' in content else None)
    proof.update(outcome=outcome, pipeline_outcome=result['outcome'], failures=result['failures'],
                 inference_forwards_reserved=counts,
                 inference_forwards_completed=done, inference_physical_input_tokens=sum(input_by_phase.values()))
    ledger = read('native/training-ledger.json') if 'native/training-ledger.json' in content else {
        'forwards': [], 'optimizer_steps': [], 'training_steps': []}
    for key in ('forwards', 'optimizer_steps', 'training_steps'):
        require(len(ledger[key]) <= 128 and all(type(r['completed']) is bool for r in ledger[key]), 'bounded training prefix required')
    require(all(type(r['input_tokens']) is int and 1 <= r['input_tokens'] <= 8192 and
                type(r['supervised_tokens']) is int and 0 <= r['supervised_tokens'] <= r['input_tokens']
                for r in ledger['forwards']) and
            result['training_input_tokens'] == sum(r['input_tokens'] for r in ledger['forwards']) <=
                plan['maximum_training_tokens'], 'physical reserved training tokens differ')
    actual_training = sum(r['completed'] for r in ledger['forwards'])
    actual_steps = sum(r['completed'] for r in ledger['optimizer_steps'])
    require(result['training_forwards'] == actual_training and result['optimizer_steps'] == actual_steps and
            terminal['model_forwards'] == actual_training + len(completions) and
            terminal['model_forwards_reserved'] == len(ledger['forwards']) + len(reservations) and
            terminal['optimizer_steps'] == actual_steps and
            terminal['optimizer_steps_reserved'] == len(ledger['optimizer_steps']) and
            terminal['training_steps_reserved'] == len(ledger['training_steps']), 'parent/training/inference cost mismatch')
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
        validate_solve_evidence(result['solve'], events, raw)
        require(result['solve']['reserved_generation_batches'] == terminal['generations'],
                'parent/solve generation reservations differ')
    if result['post_reset_control_verified']:
        require(result['all_saved_tensors_restored'] and counts['control'] == done['control'] == 7 and
                input_by_phase['control'] == 168, 'post-reset control must follow complete cache controls and reset')
        controls = [r for r in events if r['event'] == 'cache_control_result']
        require(len(controls) == 1, 'one complete same-run cache control required')
        control = controls[0]
        recomputed = {'deep': compare_vectors(control['deep_reference'], control['deep_cached']),
                      'sibling_after_deep': compare_vectors(control['sibling_reference'], control['sibling_cached'])}
        require(control['comparisons'] == recomputed and all(r['gate_passed'] for r in recomputed.values()) and
                read('native/post-reset-control.json')['prefill_bitwise_equal'] is True and
                read('native/post-reset-control.json')['prefill'] == control['baseline_prefill'],
                'cache/reset control evidence differs')
    if outcome == 'complete':
        require(plan['approved'] is True and terminal['outcome'] == 'complete' and
                result['training_complete'] is True and result['all_saved_tensors_restored'] is True and
                result['optimizer_discarded'] is True and result['post_reset_control_verified'] is True and
                counts == done and counts['control'] == 7 and input_by_phase['control'] == 168,
                'complete pipeline qualification differs')
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
