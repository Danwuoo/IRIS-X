"""Separate strict operational adapter for the reviewed forward compact format.

The historical 97-source validator remains byte-for-byte untouched. This adapter
requires an independently approved exact new source digest, verifies full raw
owner/task detail bytes and deterministic projection, then retains all historical
launch, ledger, training, adapter, deadline, export and score-label checks.
The full validate_outputs wrapper requires a FUTURE, separately reviewed active-run
contract with a run001 role and actual COMPLETE outputs. The current inactive
repair release cannot satisfy that wrapper; no role/config rewrite is performed.
This is not archived-v4 recovery and never changes historical provider status.
"""
from __future__ import annotations

from tools.arc_learning_agent_20261011.deployment.validate_learning_outputs import *
from tools.arc_learning_agent_20261011.result_projection import verify_owner_projection
from tools.arc_public_research_20261010.public_data import load_solver_tasks


def verify_compact_projection(e, result, source, source_sha, solver_root, approved_source_identity_sha256):
    need(hash_ok(approved_source_identity_sha256) and digest(source) == source_sha ==
         approved_source_identity_sha256, 'approved_forward_source_digest')
    need(set(('tools/arc_learning_agent_20261011/result_projection.py',
              'tools/arc_learning_agent_20261011/archived_recovery.py')) <= set(source),
         'forward_projection_source_required')
    need(all(source.get(k) == v for k, v in SCORER_PINS.items()), 'historical_scorer_pins')
    need(len(canonical(result)) <= 16 * MIB, 'compact_owner_cap')
    raw = e.raw('worker/owner-evidence.json')
    need(len(raw) <= 64 * MIB, 'full_owner_recovery_cap')
    request = e.json('worker/request.json')
    need(request['source_identity'] == source and result['source_identity_sha256'] == source_sha,
         'compact_request_source_binding')
    solver = load_solver_tasks(solver_root, result['solver_manifest_sha256'])
    details = {}
    for key in result['results']:
        need(re.fullmatch('[0-9a-f]{8}', key) is not None, 'safe_task_detail_identity')
        details[key] = e.raw('worker/tasks/' + key + '/result.json')
    verify_owner_projection(result, full_raw=raw, request=request,
                            challenges=solver['challenges'], task_details=details)


def verify_predictions(e, result, source, source_sha, synthetic, *, solver_root, approved_source_identity_sha256):
    verify_compact_projection(e, result, source, source_sha, solver_root, approved_source_identity_sha256)
    summary = e.json('summary.json')
    need(summary.get('status') == 'COMPLETE' and summary.get('solver_status') == 'complete' and summary.get('score_status') == 'SCORED', 'runtime_terminal_incomplete')
    need(summary.get('run_id') == e.run_id and summary.get('model_stopped') is True and summary.get('training_steps') == result['training_steps'] and summary['physical_usage'] == result['physical_usage'], 'summary_binding')
    seal_raw = e.raw('predictions/prediction-seal.json')
    seal_sha = sha(seal_raw); seal = parse(seal_raw)
    need(summary['prediction_seal']['sha256'] == seal_sha and seal['format'] == 'irisx/learning-prediction-seal-v1' and seal['generation_may_resume'] is False, 'prediction_seal')
    need(seal['source_identity'] == source and digest(source) == source_sha == approved_source_identity_sha256, 'exact_approved_source_identity')
    need(all(source.get(k) == v for k, v in SCORER_PINS.items()), 'historical_scorer_pins')
    need(seal['tasks'] == 120 and seal['tests'] == 167 and seal['policies'] == list(POLICIES), 'prediction_denominator')
    need(seal['bindings'] == {'prediction_origin': result['prediction_origin'], 'run_id': e.run_id}, 'prediction_origin_binding')
    expected_files = {p + '.json' for p in POLICIES} | {'owner-closure.json', 'solver-result.json'}
    need(set(seal['files']) == expected_files, 'prediction_seal_file_set')
    for name, row in seal['files'].items():
        need(e.inventory['files'].get('predictions/' + name) == row, 'prediction_member_binding')
    need(e.raw('predictions/solver-result.json') == e.raw('worker/result.json') and e.raw('predictions/owner-closure.json') == e.raw('owner-closure.json'), 'sealed_result_closure_copies')
    need(result['solver_manifest_sha256'] == seal['solver_manifest_sha256'], 'solver_manifest_binding')
    pools = {}
    for policy in POLICIES:
        pool = e.json('predictions/' + policy + '.json')
        need(pool['run_id'] == e.run_id and pool['method'] == 'learning-agent/' + policy, 'pool_run_policy')
        records = pool['records']; need(type(records) is list and len(records) == 120, 'pool_task_denominator')
        task_ids = [r['task_id'] for r in records]
        need(len(set(task_ids)) == 120 and all(re.fullmatch('[0-9a-f]{8}', t) for t in task_ids), 'pool_task_identity')
        need(sum(len(r['tests']) for r in records) == 167, 'pool_test_denominator')
        for row in records:
            need(type(row['task_digest']) is str and row['task_digest'].startswith('sha256:') and hash_ok(row['task_digest'][7:]) and row['tests'], 'pool_task_digest')
            need([t['test_index'] for t in row['tests']] == list(range(len(row['tests']))), 'pool_test_indexes')
            for test in row['tests']:
                need(type(test['input_digest']) is str and test['input_digest'].startswith('sha256:') and hash_ok(test['input_digest'][7:]) and type(test['ranked_grids']) is list and len(test['ranked_grids']) <= 2, 'prediction_shape')
                # Deliberately do not inspect grid values or evaluate correctness.
        pools[policy] = {r['task_id']: (r['task_digest'], [(t['test_index'], t['input_digest']) for t in r['tests']]) for r in records}
    need(all(v == pools[POLICIES[0]] for v in pools.values()), 'pool_shared_denominator')
    results = result['results']
    need(type(results) is dict and set(results) <= set(pools[POLICIES[0]]), 'attempted_task_identity')
    need(synthetic or set(results) == set(pools[POLICIES[0]]), 'all_120_task_attempts_required')
    need(results, 'no_task_attempts')
    for task_id, task in results.items():
        need(task['task_id'] == task_id and task.get('status') in ('complete', 'budget_stopped', 'error'), 'task_attempt_terminal')
        need(task['physical_usage'].get('unknown_usage_events') == 0, 'task_unknown_work')
        detail = e.json('worker/tasks/' + task_id + '/result.json')
        need({k: v for k, v in detail.items() if k != 'evidence'} == task, 'compact_task_result_binding')
        need(set(task['policies']) == set(POLICIES) and all(len(task['policies'][p]) == len(pools[p][task_id][1]) for p in POLICIES), 'task_test_attempt_denominator')
    process = e.json('evaluation/process-receipt.json')
    need(process.get('returncode') == 0 and type(process['returncode']) is int and process.get('owned_process_stopped') is True and process.get('prediction_seal_sha256') == seal_sha, 'scorer_process_closure')
    for name in ('evaluation/public-summary.json', 'evaluation/evaluator-detail.json'):
        labels = score_labels(e.raw(name))
        need(labels.get('status') == 'SCORED' and labels.get('format') == 'irisx/learning-public-evaluation-v1' and labels.get('tasks') == 120 and labels.get('tests') == 167, 'scorer_status_labels')
        need(labels.get('prediction_origin') == result['prediction_origin'] and labels.get('prediction_seal_sha256') == seal_sha and labels.get('scorer_sha256') == SCORER_PINS['tools/arc_offline_evaluation.py'] and labels.get('generation_may_resume') is False and labels.get('training_used') is True and labels.get('training_steps') == result['training_steps'], 'scorer_labels_binding')
    return summary, seal, seal_sha, len(results)


def validate_outputs(download_root, *, manifest, finalization, launch_journal, launch_receipt,
                     retrieval_receipt, finalized_notebook, template_notebook=None,
                     saved_notebook=None, launch_binding=None, allow_synthetic=False,
                     solver_root, approved_source_identity_sha256):
    """Return compact counters/IDs/hashes. Raise ValidationError on any missing proof.

    Manifest must be its exact reviewed file, not an edited reconstruction. Other
    metadata may be paths or mappings (mappings are hashed using canonical JSON).
    All local/provider paths are explicit. allow_synthetic is solely for tests;
    its result always has operational_success=False, status=SYNTHETIC_VALIDATED.
    """
    need(type(allow_synthetic) is bool, 'synthetic_flag_boolean')
    m, manifest_sha = document(manifest)
    f, _ = document(finalization); j, _ = document(launch_journal)
    l, _ = document(launch_receipt); r, retrieval_sha = document(retrieval_receipt)
    try:
        need(m['format'] == 'irisx/learning-result-projection-repair-publication-contract-v1', 'publication_manifest_format')
        spec, constants, suffix = verify_launch(m, manifest_sha, f, j, l, finalized_notebook, template_notebook, saved_notebook)
        if r.get('launch_binding_sha256') is not None:
            need(launch_binding is not None, 'launch_binding_missing')
            binding, binding_sha = document(launch_binding)
            need(binding_sha == r['launch_binding_sha256'], 'launch_binding_hash')
            for key, expected in {'predispatch_epoch': f['predispatch_epoch'], 'deadline_epoch': f['deadline_epoch'], 'submitted_source_sha256': l['submitted_source_sha256'], 'saved_source_sha256': l['saved_source']['sha256']}.items():
                need(binding.get(key) == expected, 'launch_binding_fields')
        d = Downloads(download_root, r, l, spec, manifest_sha)
        e = Evidence(d, spec['output_root'], allow_synthetic)
        try:
            result = e.json('worker/result.json')
            need(result['format'] == 'irisx/learning-owner-result-v1' and result['run_id'] == e.run_id and result['status'] == 'complete' and result['model_stopped'] is True and result['pending_work'] == {}, 'solver_terminal_incomplete')
            source, source_sha = m['source_identity'], m['source_identity_sha256']
            need(result['source_identity_sha256'] == source_sha, 'result_source_binding')
            ledger, completed = verify_ledger(e.raw('worker/physical-work.jsonl'), result['physical_usage'])
            global_steps = verify_training(result, completed, allow_synthetic)
            summary, seal, seal_sha, attempted = verify_predictions(e, result, source, source_sha, allow_synthetic, solver_root=solver_root, approved_source_identity_sha256=approved_source_identity_sha256)
            if not allow_synthetic:
                verify_public_pins(seal, constants)
            inner_request, owner = verify_inner_owner(e, result, source_sha)
            admission = e.json('admission.json')
            need(admission['run_id'] == e.run_id and admission['source_identity'] == source and admission['enable_model'] is True and admission['solver_manifest_sha256'] == seal['solver_manifest_sha256'] and admission['evaluator_manifest_sha256'] == seal['evaluator_manifest_sha256'], 'admission_binding')
            need(inner_request['source_identity'] == source and inner_request['clock'] == summary['clock'] and admission['clock'] == summary['clock'], 'request_clock_source_binding')
            if allow_synthetic:
                need(inner_request['config'].get('tiny_cpu') is True and inner_request['config'].get('validation_mode') is True, 'synthetic_test_mode_required')
                need(attempted == inner_request['config'].get('fixture_tasks', 2), 'synthetic_attempt_count')
            else:
                need(inner_request['config'].get('tiny_cpu', False) is False and inner_request['config'].get('validation_mode', False) is False and inner_request['config'].get('session_seconds') == 43200 and inner_request['config'].get('predispatch_clock') is True, 'production_request_config')
            artifact_counts = verify_adapter(e, result, allow_synthetic)
            outer_sha = verify_outer(d, spec, constants, suffix, f, e, summary, owner)
            need([s.get('stage') for s in result['stage_clock']] == list(STAGE_CAPS), 'stage_clock_sequence')
            for stage in result['stage_clock']:
                need(stage.get('maximum_seconds') == STAGE_CAPS[stage['stage']] and stage.get('status') == 'complete' and stage.get('within_cap') is True and number(stage.get('started_epoch')) and number(stage.get('elapsed_seconds')) and stage['elapsed_seconds'] <= stage['maximum_seconds'] and f['predispatch_epoch'] <= stage['started_epoch'] <= stage['started_epoch'] + stage['elapsed_seconds'] <= f['deadline_epoch'], 'stage_deadline_or_incomplete')
            return {'format': 'irisx/learning-projection-operational-validation-v1',
                    'status': 'SYNTHETIC_VALIDATED' if allow_synthetic else 'COMPLETE',
                    'operational_success': not allow_synthetic, 'synthetic_test_only': allow_synthetic,
                    'reference': l['reference'], 'kernel_id': l['kernel_id'], 'version': l['version'],
                    'run_id': e.run_id, 'manifest_sha256': manifest_sha,
                    'submitted_source_sha256': l['submitted_source_sha256'],
                    'saved_source_sha256': l['saved_source']['sha256'],
                    'retrieval_receipt_sha256': retrieval_sha, 'source_identity_sha256': source_sha,
                    'archive_sha256': e.archive_sha, 'archive_members_hashed': e.member_count,
                    'archive_expanded_bytes': e.expanded_bytes, 'prediction_seal_sha256': seal_sha,
                    'launcher_closure_sha256': outer_sha, 'task_attempts': attempted,
                    'prediction_tasks': 120, 'prediction_tests': 167, 'global_sft_optimizer_steps': global_steps,
                    'training_optimizer_steps': result['training_steps'],
                    'physical_ledger_events': ledger['events'], 'physical_ledger_sha256': ledger['last_sha256'],
                    'physical_counts': ledger['charged'], **artifact_counts,
                    'historical_process_closure_verified': True, 'absolute_deadline_verified': True,
                    'provider_vm_or_billing_state_verified': False, 'scientific_metrics_read': False}
        finally:
            e.close()
    except (KeyError, TypeError, IndexError, SyntaxError, zipfile.BadZipFile, OSError) as exc:
        raise ValidationError('missing_or_invalid_operational_evidence') from exc
