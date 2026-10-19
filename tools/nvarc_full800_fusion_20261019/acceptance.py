"""Predeclared merge/adoption gates, not authorization to launch or spend.

Input receipts require independently retained hashes. Hashes establish byte
identity, not truth or provider attestation. A local fixture cannot satisfy the
official-model evidence gate. Reused development scores are never hidden scores.
"""
from __future__ import annotations
import hashlib
import json
import math
import random

MATRIX_SCOPE = 'padded_linear_attention_rope_forward_backward_reentrant_rematerialization'
MATRIX_EXCLUSIONS = ['pointwise', 'embedding_scatter', 'routing_topk_dispatch_combine',
                     'loss', 'optimizer']


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def make_protocol(*, corpus_sha256, exposure_sha256, inference_contract_sha256,
                  training_parent_ids, development_pool_parent_ids, development_parent_ids, seeds,
                  architectures=('baseline', 'depth32', 'width8192', 'moe4_top2'),
                  created_at, minimum_mean_gain_parents=2,
                  competition_ref='arc-prize-2026-arc-agi-2', official_score_field='publicScore'):
    """Freeze BEFORE observing outcomes. This does not create a clean holdout.

    Three seeds are prospective acceptance evidence, not permission for three
    runs. Runtime and concurrency authorization is independent of this gate.
    """
    for value in (corpus_sha256, exposure_sha256, inference_contract_sha256):
        require(_pin(value), 'independent corpus/exposure/inference contract pins required')
    train, dev_pool, dev, seeds, arch = map(list, (training_parent_ids, development_pool_parent_ids,
                                                  development_parent_ids, seeds, architectures))
    require(all(type(x) is str and x for rows in (train, dev_pool, dev) for x in rows),
            'explicit original parent identities required')
    require(len(dev_pool) == len(set(dev_pool)) == 200 and not set(train) & set(dev_pool)
            and set(dev) <= set(dev_pool), 'fixed200 development roster and declared96 subset required')
    require(len(train) == len(set(train)) == 800 and len(dev) == len(set(dev)) == 96
            and not set(train) & set(dev), 'original disjoint800 train/fixed96 development required')
    require(len(seeds) >= 3 and len(seeds) == len(set(seeds))
            and all(type(s) is int and 0 <= s < 2**63 for s in seeds), 'at least three fixed distinct seeds required')
    require(arch and len(arch) == len(set(arch)) and arch[0] == 'baseline'
            and set(arch) <= {'baseline', 'depth32', 'width8192', 'moe4_top2'},
            'fixed supported architecture inventory required')
    require(type(created_at) in (int, float) and math.isfinite(created_at) and created_at > 0,
            'finite preregistration time required')
    require(type(minimum_mean_gain_parents) is int and minimum_mean_gain_parents >= 2,
            'single-parent improvement is not sufficient adoption evidence')
    require(competition_ref == 'arc-prize-2026-arc-agi-2'
            and official_score_field in ('publicScore', 'privateScore'),
            'the intended official ARC2 competition and predeclared score population are required')
    result = dict(format='irisx/full800-three-line-acceptance-v2',
        corpus_sha256=corpus_sha256, exposure_sha256=exposure_sha256,
        inference_contract_sha256=inference_contract_sha256,
        training_parent_ids=train, development_pool_parent_ids=dev_pool,
        development_parent_ids=dev, seeds=seeds, architectures=arch,
        created_at=created_at, minimum_mean_gain_parents=minimum_mean_gain_parents,
        bootstrap_replicates=10000, bootstrap_seed=20261019,
        bootstrap_unit='parent, jointly across seeds and paired arms',
        familywise_error=.05, hypotheses=2*len(arch)-1,
        architecture_selection='largest eligible absolute candidate mean; declared architecture order breaks ties',
        expansion_gate='must also improve the same paired dense-fusion seed models; equal800/update tokens, not equalFLOPs',
        development_reused=True, inherited_model_exposure='unresolved',
        scientific_scope='development adoption only; not hidden generalization',
        max_compute_ratio=1.05, full_training_updates=100, parents_per_update=8,
        training_compute_scope=MATRIX_SCOPE, training_compute_exclusions=MATRIX_EXCLUSIONS,
        compute_claim='matched padded matrix training work, not equal total method FLOPs or wall time',
        replay_control='source-reconstructed transformed gold CE0.5 vs sampled positive CE0.25 + AF3 DDIS0.25',
        shared_collection_policy='charged once experimentally; full incremental fusion-method cost disclosed',
        development_views=192, generation_tokens=931, automatic_new_runs_authorized=0,
        official_threshold=90.0, official_score_unit='0_to_100',
        competition_ref=competition_ref, official_score_field=official_score_field,
        formal_rule='all preregistered seed models strictly exceed90; no leaderboard-driven selection',
        formal_same_population_correlation_acknowledged=True,
        gcp_resource_creation_authorized=False, new_agent_harness_authorized=False)
    result['protocol_sha256'] = digest(result)
    return result


def validate_protocol(protocol, expected_sha256):
    require(_pin(expected_sha256) and protocol.get('protocol_sha256') == expected_sha256
            and digest({k:v for k,v in protocol.items() if k != 'protocol_sha256'}) == expected_sha256,
            'independently pinned predeclared acceptance protocol required')
    rebuilt = make_protocol(**{k:protocol[k] for k in ('corpus_sha256', 'exposure_sha256',
        'inference_contract_sha256', 'training_parent_ids', 'development_pool_parent_ids', 'development_parent_ids', 'seeds',
        'architectures', 'created_at', 'minimum_mean_gain_parents', 'competition_ref', 'official_score_field')})
    require(rebuilt == protocol, 'acceptance thresholds or fixed protocol changed')


def paired_parent_evidence(candidate, control, protocol):
    """Binary generated-exact pass@2 only. Never NLL, pooled views or missing=0.

    Bootstrap clusters by parent and averages paired seed differences within a
    parent. Seeds are not counted as additional independent task observations.
    """
    n, k = 96, len(protocol['seeds'])
    require(len(candidate) == len(control) == k, 'all preregistered paired seeds required')
    for rows in (candidate, control):
        require(all(type(row) is list and len(row) == n and all(type(x) is int and x in (0,1) for x in row)
                    for row in rows), 'complete binary generated-exact96 outcomes required; no null/partial')
    per_seed = [sum(a)-sum(b) for a,b in zip(candidate,control)]
    paired = [sum(candidate[s][p]-control[s][p] for s in range(k))/k for p in range(n)]
    rng = random.Random(protocol['bootstrap_seed'])
    samples = sorted(sum(paired[rng.randrange(n)] for _ in range(n))
                     for _ in range(protocol['bootstrap_replicates']))
    # Simultaneous lower bounds for the frozen architecture family; do not
    # pick the largest unadjusted interval after seeing four comparisons.
    lower = samples[int(protocol['familywise_error']/protocol['hypotheses'] * len(samples))]
    mean = sum(per_seed)/k
    return dict(mean_gain_parents=mean, seed_gain_parents=per_seed,
        paired_parent_simultaneous_lower_gain_parents=lower,
        familywise_error=protocol['familywise_error'], compared_hypotheses=protocol['hypotheses'],
        bootstrap_replicates=len(samples), independent_units=n,
        passed=mean >= protocol['minimum_mean_gain_parents'] and min(per_seed) >= 0 and lower > 0,
        clean_holdout_claimed=False, hidden_generalization_claimed=False)


def evaluate(protocol, receipts, *, expected_protocol_sha256, expected_receipt_sha256):
    """Return blocked conditions instead of turning absent evidence into success.

    Receipts are normalized from separately audited runtime/evaluator/provider
    artifacts. The normalizer must retain their original identities and hashes.
    This function cannot independently authenticate a provider or private label.
    """
    validate_protocol(protocol, expected_protocol_sha256)
    require(_pin(expected_receipt_sha256) and digest(receipts) == expected_receipt_sha256,
            'independently retained evidence digest required')
    require(type(receipts) is dict and set(receipts) == {'engineering', 'paired_runs', 'formal_runs'},
            'exact three evidence categories required')
    missing = []; eng = receipts['engineering']
    required = ('actual_official_model', 'all800_training_complete', 'checkpoint_reload_exact',
        'optimizer_rng_resume_verified', 'strict_probability_gates_passed',
        'full192_evaluation_complete', 'owned_worker_closed_within_original_budget',
        'same_inference_contract', 'source_and_model_pins_verified')
    for arch in protocol['architectures']:
        e = eng.get(arch, {})
        if any(e.get(k) is not True for k in required): missing.append('engineering:'+arch+':incomplete_actual_model_evidence')
        if (e.get('corpus_sha256') != protocol['corpus_sha256'] or
            e.get('inference_contract_sha256') != protocol['inference_contract_sha256'] or
            e.get('committed_training_parent_ids') != protocol['training_parent_ids'] or
            e.get('development_parent_ids') != protocol['development_parent_ids'] or
            type(e.get('optimizer_updates')) is not int or e.get('optimizer_updates') != 100 or
            not _pin(e.get('original_runtime_receipt_sha256'))):
            missing.append('engineering:'+arch+':lineage_coverage_or_binding')
    engineering = not missing
    scientific = {}; runs = receipts['paired_runs']; bound_runs={}
    for arch in protocol['architectures']:
        by_seed = {r.get('seed'):r for r in runs if r.get('architecture') == arch}
        needed = [by_seed.get(s) for s in protocol['seeds']]
        reason = None
        if len(by_seed) != len([r for r in runs if r.get('architecture') == arch]): reason='duplicate_seed_evidence'
        elif set(by_seed) != set(protocol['seeds']) or any(r is None for r in needed): reason='preregistered_seed_results_missing_or_extra'
        else:
            seen_trajectories={'candidate':set(),'control':set()}
            for r in needed:
                executions=r.get('executions',{})
                valid_executions=True
                for role in ('candidate','control'):
                    execution=executions.get(role,{})
                    fields=('runtime_receipt_sha256','checkpoint_sha256','initial_trainable_state_sha256','source_sha256')
                    valid_executions=valid_executions and (
                        execution.get('seed')==r['seed'] and type(execution.get('seed')) is int and
                        type(execution.get('run_id')) is str and bool(execution['run_id']) and
                        all(_pin(execution.get(k)) for k in fields))
                    identity=(execution.get('run_id'),execution.get('runtime_receipt_sha256'),
                              execution.get('checkpoint_sha256'))
                    # Identical outcomes are allowed. Re-labeled identical
                    # executed trajectories are not independent seed evidence.
                    if any(identity[i]==old[i] for old in seen_trajectories[role] for i in range(3)):
                        valid_executions=False
                    seen_trajectories[role].add(identity)
                valid_executions=valid_executions and (
                    executions.get('candidate',{}).get('initial_trainable_state_sha256')==
                    executions.get('control',{}).get('initial_trainable_state_sha256'))
                if not valid_executions:reason='paired_independent_seed_execution_binding_unverified';break
                cost = r.get('cost', {})
                measured = (cost.get('matrix_accounting_complete') is True and
                    cost.get('same_update_and_padded_input_budget') is True and
                    cost.get('strong_sft_control') is True and
                    cost.get('method') == 'model_accounted_padded_training_matrix_flops' and
                    cost.get('scope') == protocol['training_compute_scope'] and
                    cost.get('excluded_operations') == protocol['training_compute_exclusions'] and
                    cost.get('equal_total_method_compute_claimed') is False and
                    cost.get('all_charged_matrix_work_returned') is True and
                    cost.get('shared_collection_charged_once') is True and
                    cost.get('full_collection_attributed_to_fusion_method') is True)
                numbers = [cost.get('candidate_training_matmul_flops'), cost.get('control_training_matmul_flops')]
                measured = measured and all(type(v) in (int,float) and math.isfinite(v) and v > 0 for v in numbers)
                if measured:
                    ratio = max(numbers)/min(numbers)
                    measured = ratio <= protocol['max_compute_ratio']
                tokens=[cost.get('candidate_charged_training_input_tokens'),cost.get('control_charged_training_input_tokens')]
                measured = measured and all(type(v) is int and v>0 for v in tokens)
                if measured: measured=max(tokens)/min(tokens)<=protocol['max_compute_ratio']
                measured = measured and cost.get('candidate_updates')==cost.get('control_updates')==100
                primary=[cost.get('candidate_known_target_input_tokens'),cost.get('control_known_target_input_tokens')]
                measured = measured and all(type(v) is int and v>=800 for v in primary) and primary[0]==primary[1]
                measured = measured and cost.get('fixed_replay_parent_ids')==protocol['training_parent_ids'][:16]
                # Different gold/sample target lengths remain visible; padded
                # matrix-work matching is not a claim of equal valid targets.
                measured = measured and all(type(cost.get(k)) is int and cost[k]>0 for k in
                    ('candidate_valid_target_tokens','control_valid_target_tokens','collection_physical_tokens'))
                if measured:
                    measured=all(tokens[i]>=primary[i] and
                        800<=cost[role+'_valid_target_tokens']<=tokens[i]
                        for i,role in enumerate(('candidate','control')))
                measured = measured and all(type(cost.get(k)) in (int,float) and
                    math.isfinite(cost[k]) and cost[k]>0 for k in
                    ('candidate_training_wall_seconds','control_training_wall_seconds','collection_wall_seconds'))
                if not measured: reason='compute_matched_strong_sft_control_unproven'; break
                if (r.get('development_parent_ids') != protocol['development_parent_ids'] or
                    r.get('training_parent_ids') != protocol['training_parent_ids'] or
                    r.get('corpus_sha256') != protocol['corpus_sha256'] or
                    r.get('inference_contract_sha256') != protocol['inference_contract_sha256'] or
                    not _pin(r.get('training_pool_sha256')) or
                    r.get('complete') is not True or r.get('protocol_sha256') != expected_protocol_sha256 or
                    r.get('preregistered_before_outcome') is not True or
                    not _pin(r.get('sealed_predictions_sha256'))):
                    reason='incomplete_or_unbound_paired_outcomes'; break
        if reason:
            scientific[arch] = dict(passed=False, reason=reason)
        else:
            scientific[arch] = paired_parent_evidence([r['candidate_pass2'] for r in needed],
                                                      [r['control_pass2'] for r in needed], protocol)
            scientific[arch]['absolute_candidate_mean_parents']=sum(sum(r['candidate_pass2']) for r in needed)/len(needed)
            bound_runs[arch]=needed
    expansions={}
    for arch in protocol['architectures'][1:]:
        if arch not in bound_runs or 'baseline' not in bound_runs:
            expansions[arch]=dict(passed=False,reason='same_seed_bound_dense_fusion_comparator_missing')
        else:
            expanded=bound_runs[arch];dense=bound_runs['baseline']
            # This contrast deliberately holds full800/100 updates and input
            # tokens fixed, NOT arithmetic work. Larger models cost more FLOPs.
            coverage_equal=all(e['cost'].get('candidate_known_target_input_tokens') ==
                               d['cost'].get('candidate_known_target_input_tokens') and
                               e['cost'].get('candidate_charged_training_input_tokens') ==
                               d['cost'].get('candidate_charged_training_input_tokens') and
                               e['training_pool_sha256']==d['training_pool_sha256'] and
                               type(e['cost'].get('candidate_known_target_input_tokens')) is int and
                               e['cost']['candidate_known_target_input_tokens']>0 and
                               e['cost'].get('fixed_replay_parent_ids')==d['cost'].get('fixed_replay_parent_ids')==
                               protocol['training_parent_ids'][:16] and
                               type(e['cost'].get('fixed_replay_parent_ids')) is list and
                               len(e['cost']['fixed_replay_parent_ids'])==16
                               for e,d in zip(expanded,dense))
            if not coverage_equal:
                expansions[arch]=dict(passed=False,reason='expansion_full800_replay_or_token_budget_differs')
            else:
                expansions[arch]=paired_parent_evidence([r['candidate_pass2'] for r in expanded],
                    [r['candidate_pass2'] for r in dense],protocol)
                expansions[arch].update(equal_flops_claimed=False,
                    matrix_accounting_scope=protocol['training_compute_scope'],
                    candidate_to_dense_training_matmul_flop_ratios=[e['cost']['candidate_training_matmul_flops']/
                        d['cost']['candidate_training_matmul_flops'] for e,d in zip(expanded,dense)])
    winners=[a for a in protocol['architectures'] if scientific[a]['passed']
             and (a=='baseline' or expansions[a]['passed'])]
    selected=max(winners,key=lambda a:scientific[a]['absolute_candidate_mean_parents']) if winners else None
    # Negative expansion arms are useful evidence, not a requirement to adopt
    # every architecture. Selection is familywise-controlled and frozen above.
    scientific_ok = engineering and selected is not None
    formal = receipts['formal_runs']; formal_reasons = []
    if len(formal) != len(protocol['seeds']) or {r.get('seed') for r in formal} != set(protocol['seeds']):
        formal_reasons.append('all_preregistered_formal_seed_results_missing')
    seen_models=set(); seen_submissions=set()
    score_contexts=set()
    selected_by_seed={r['seed']:r for r in bound_runs.get(selected,[])}
    for r in formal:
        score=r.get('score')
        if not (type(score) in (int,float) and math.isfinite(score) and 90 < score <= 100):
            formal_reasons.append('formal_score_not_strictly_above90')
        if (r.get('status') != 'COMPLETE' or r.get('score_field') != protocol['official_score_field'] or
            r.get('unit') != '0_to_100' or r.get('fixed_recipe_sha256') != expected_protocol_sha256 or
            r.get('preregistered_before_any_formal_feedback') is not True or
            r.get('leaderboard_selected') is not False or not _pin(r.get('provider_receipt_sha256')) or
            not _pin(r.get('model_checkpoint_sha256')) or
            type(r.get('submission_id')) is not int or r.get('submission_id',0)<=0 or
            r.get('competition_ref') != protocol['competition_ref'] or
            r.get('inference_contract_sha256') != protocol['inference_contract_sha256'] or
            r.get('model_checkpoint_sha256') != selected_by_seed.get(r.get('seed'),{}).get('executions',{}).get('candidate',{}).get('checkpoint_sha256') or
            r.get('architecture') != selected):
            formal_reasons.append('formal_provenance_or_no_feedback_contract_unverified')
        seen_models.add(r.get('model_checkpoint_sha256')); seen_submissions.add(r.get('submission_id'))
        score_contexts.add((r.get('competition_ref'),r.get('score_field'),r.get('unit')))
    if len(seen_models) != len(protocol['seeds']) or len(seen_submissions) != len(protocol['seeds']):
        formal_reasons.append('repeated_identical_model_or_submission_not_independent_seed_evidence')
    if len(score_contexts)!=1: formal_reasons.append('mixed_or_missing_official_score_populations')
    stable_formal = not formal_reasons
    return dict(format='irisx/full800-three-line-acceptance-result-v2',
        protocol_sha256=expected_protocol_sha256, evidence_sha256=expected_receipt_sha256,
        engineering_merge=engineering, engineering_missing=missing,
        scientific_adoption=scientific_ok, architecture_results=scientific,
        expansion_versus_dense_results=expansions,selected_architecture=selected,
        scientific_scope=protocol['scientific_scope'],
        compute_claim=protocol['compute_claim'],
        gcp_scaling_plan_ready=engineering and scientific_ok,
        gcp_resource_creation_authorized=False, stable_official_above90=stable_formal,
        formal_missing=sorted(set(formal_reasons)),
        new_methods_or_agent_harness_gate=engineering and scientific_ok and stable_formal,
        no_new_run_authorized_by_this_receipt=True,
        inherited_model_exposure='unresolved', development_reused=True)
