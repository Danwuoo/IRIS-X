"""Torch-free identities for compact output-head numerical execution.

The policy changes computation, not pretrained tensor provenance. A new policy
requires fresh sampled behavior; old probabilities must never be relabeled.
"""

LEGACY_POLICY = "outer-autocast-compact-head-v1"
FP32_HEAD_POLICY = "fp32-compact-head-v1"


def admit_policy(value):
    if type(value) is not str or value not in (LEGACY_POLICY, FP32_HEAD_POLICY):
        raise ValueError("explicit admitted compact probability policy required")
    return value


def bind_trainable_contract(contract, policy):
    """Preserve exact historical schema for legacy checkpoints only."""
    admit_policy(policy)
    result = dict(contract)
    if policy != LEGACY_POLICY:
        result["probability_policy"] = policy
    return result


def stable_probe_admission(raw, *, tolerance, count):
    """Recompute extra numerical-path gates from original sampled vectors.

    Pure Python, shared by worker and independent artifact consumer. This never
    substitutes replay probabilities for behavior or grants optimizer admission.
    Partial/failed probes retain measured evidence but cannot pass.
    """
    import math
    def need(value, message):
        if not value:
            raise ValueError(message)
    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)
    rows = raw.get('rows', [])
    extras = raw.get('additional_replays', {})
    need(type(extras) is dict and set(extras) <= {'eval_nograd', 'train_grad'},
         'bounded declared additional probability paths required')
    summary, passed = {}, raw.get('status') == 'completed' and len(rows) == count
    for mode in ('eval_nograd', 'train_grad'):
        stage = extras.get(mode)
        if stage is None:
            summary[mode] = None
            passed = False
            continue
        need(stage.get('mode') == mode and stage.get('backward_validated') is False,
             'additional path must not claim backward validation')
        values = stage.get('rows', [])
        need(type(values) is list and len(values) <= len(rows), 'bounded additional rows required')
        gaps = []
        for index, value in enumerate(values):
            original = rows[index]
            behavior = original['behavior_log_probs'][original['prompt_length']:]
            replay = value.get('full_log_probs')
            need(value.get('row_index') == index and value.get('completion_ids') == original['completion_ids']
                 and value.get('behavior_log_probs') == behavior and type(replay) is list
                 and len(replay) == len(behavior) and all(finite(v) for v in behavior + replay),
                 'additional replay must retain exact original behavior denominator')
            gaps.extend(abs(a-b) for a,b in zip(behavior,replay))
        measured = {'tokens': len(gaps), 'max_abs_logp_gap': max(gaps) if gaps else None}
        need(all(stage.get('metrics', {}).get(k) == v for k,v in measured.items()),
             'additional probability summary differs from raw measurements')
        summary[mode] = measured
        passed = passed and stage.get('status') == 'completed' and len(values) == count \
            and finite(measured['max_abs_logp_gap']) and 0 <= measured['max_abs_logp_gap'] <= tolerance
    if raw.get('status') == 'completed':
        evidence = raw.get('logit_evidence')
        trace = raw.get('trace', {})
        cached = raw.get('cached_replay') or {}
        expected = [('generation', step['selected_ids'], step['selected_log_probs'])
                    for step in trace.get('steps', [])]
        expected += [('cached_replay', step['selected_ids'], step['cached_log_probs'])
                     for step in cached.get('steps', [])]
        for name, values in [('full_replay', raw.get('full_replay', [])),
                             ('full_eval_nograd', extras.get('eval_nograd', {}).get('rows', [])),
                             ('full_train_grad', extras.get('train_grad', {}).get('rows', []))]:
            expected += [(name, value['completion_ids'], value['full_log_probs']) for value in values]
        need(type(evidence) is list and len(evidence) == len(expected)
             and raw.get('extra_projection_calls') == raw.get('extra_projection_attempts')
             == raw.get('extra_projection_successes') == 2 * len(evidence),
             'complete charged full16 logit evidence required')
        for index, (item, (stage, ids, logps)) in enumerate(zip(evidence, expected)):
            gradient = stage == 'full_train_grad'
            need(item.get('call') == index and item.get('stage') == stage
                 and item.get('actual_dtype') == 'torch.float32'
                 and item.get('grad_enabled') is gradient
                 and item.get('actual_requires_grad') is gradient
                 and item.get('head_training') is (stage in ('full_replay', 'full_train_grad'))
                 and item.get('extra_projection_calls') == item.get('projection_attempts')
                 == item.get('projection_successes') == 2 and item.get('error') is None,
                 'actual head precision/mode/gradient evidence differs')
            actual = item.get('actual_logits')
            shape = (count, 1) if stage in ('generation', 'cached_replay') else (1, len(ids))
            for key in ('actual_logits', 'fp32_same_hidden_logits', 'legacy_same_hidden_logits'):
                matrix = item.get(key)
                need(type(matrix) is list and len(matrix) == shape[0]
                     and all(type(sequence) is list and len(sequence) == shape[1]
                             and all(type(vector) is list and len(vector) == 16 and all(finite(v) for v in vector)
                                     for vector in sequence) for sequence in matrix),
                     'finite bounded full16 logit evidence required')
            # Two FP32 linear dispatches can differ by final-bit rounding
            # (observed CPU maximum1.49e-8); this diagnostic control is not
            # the unchanged sampled-versus-replay 0.05 admission threshold.
            for sequence, reference in zip(actual, item['fp32_same_hidden_logits']):
                for vector, other in zip(sequence, reference):
                    need(all(abs(a-b) <= 1e-6 + 5e-7 * abs(b) for a,b in zip(vector,other)),
                         'FP32 head differs from same-hidden FP32 projection')
            vectors = [sequence[0] for sequence in actual] if shape[0] == count and stage in ('generation','cached_replay') else actual[0]
            need(len(vectors) == len(ids) == len(logps), 'logit/selection alignment differs')
            for vector, token, measured in zip(vectors, ids, logps):
                maximum = max(vector)
                rebuilt = vector[token] - maximum - math.log(math.fsum(math.exp(v-maximum) for v in vector))
                # Recompute in Python FP64; allow only FP32 logsumexp rounding,
                # not the scientific cached/full replay gate's 0.05 tolerance.
                rounding = 2e-5 + 2e-7 * max(abs(v) for v in vector)
                need(abs(rebuilt-measured) <= rounding, 'full16 logits do not bind actual selected probability')
    return summary, bool(passed)
