"""Opt-in 16-symbol grid-chat query-only log-probability indexing; no model hooks.
Aligned labels are NOT pre-shifted. Manual scoring uses prediction_positions
with target_ids; never apply a second shift. No objective normalization chosen.
"""

def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _grid_body(body):
    need(body and all(type(v) is int and 0 <= v <= 10 for v in body), 'empty/non-grid/header-injected body')
    rows = [[]]
    for token in body:
        if token == 10:
            rows.append([])
        else:
            rows[-1].append(token)
    need(1 <= len(rows) <= 30 and all(1 <= len(row) <= 30 for row in rows), 'empty/oversized grid row')
    need(len({len(row) for row in rows}) == 1, 'ragged grid')


def query_response_view(input_ids, attention_mask, *, query_prompt_ids):
    """Strict alternating complete grid frames; final assistant is query response.

    query_prompt_ids must come from the trusted pre-generation prompt, not be
    recomputed from a generated completion. Exact prefix and body-start binding
    prevents a complete injected frame from moving the scored query boundary.
    Right padding must be token13 with attention0; token13 in real content is
    rejected. Need >=1 support pair followed by one query pair. Untrusted raw
    tokenizer acceptance is NOT sufficient validation.
    """
    need(type(input_ids) is list and type(attention_mask) is list and len(input_ids) == len(attention_mask) > 0,
         'aligned nonempty arrays')
    need(all(type(t) is int and 0 <= t < 16 for t in input_ids), 'integer vocabulary IDs')
    need(all(type(m) is int and m in (0, 1) for m in attention_mask), 'integer binary attention')
    n = sum(attention_mask)
    need(n > 0 and attention_mask == [1] * n + [0] * (len(input_ids)-n), 'nonempty right-padded attention')
    need(input_ids[n:] == [13] * (len(input_ids)-n), 'padding must be nonzero PAD13')
    need(type(query_prompt_ids) is list and 0 < len(query_prompt_ids) < n
         and all(type(t) is int and 0 <= t < 16 for t in query_prompt_ids)
         and input_ids[:len(query_prompt_ids)] == query_prompt_ids, 'trusted query prompt prefix binding')
    at = 0
    assistants = []
    pairs = 0
    while at < n:
        for role in (11, 12):
            need(at + 3 <= n and input_ids[at:at+3] == [14, role, 10], 'exact alternating role header')
            body_start = at + 3
            at = body_start
            while at < n and input_ids[at] != 15:
                at += 1
            need(at < n, 'missing closing EOS15')
            _grid_body(input_ids[body_start:at])
            if role == 12:
                assistants.append((body_start, at+1))
            at += 1
        pairs += 1
    need(at == n and pairs >= 2, 'one or more support pairs plus query pair')
    start, end = assistants[-1]
    need(start == len(query_prompt_ids), 'query body must start at trusted prompt boundary')
    need(end == n and input_ids[end-1] == 15, 'query completion closes real sequence')
    aligned_labels = [-100] * len(input_ids)
    aligned_labels[start:end] = input_ids[start:end]
    targets = list(input_ids[start:end])
    predictions = list(range(start-1, end-1))
    need(all(attention_mask[p+1] == 1 and input_ids[p+1] == y for p, y in zip(predictions, targets)),
         'once-shift alignment')
    return dict(true_length=n, padded_length=len(input_ids), support_pairs=pairs-1,
                query_body_start=start, query_end_exclusive=end,
                aligned_labels=aligned_labels, prediction_positions=predictions,
                target_ids=targets, response_token_count=end-start,
                support_assistant_target_count=sum(b-a for a,b in assistants[:-1]),
                all_assistant_target_count=sum(b-a for a,b in assistants))


def validate_logprob_alignment(input_ids, attention_mask, prediction_positions, target_ids, *, query_prompt_ids):
    """Reject caller-supplied zero/double shift, wrong targets or omitted EOS."""
    q = query_response_view(input_ids, attention_mask, query_prompt_ids=query_prompt_ids)
    need(type(prediction_positions) is list and all(type(x) is int for x in prediction_positions)
         and prediction_positions == q['prediction_positions'], 'prediction positions must be shifted exactly once')
    need(type(target_ids) is list and all(type(x) is int for x in target_ids)
         and target_ids == q['target_ids'], 'complete exact query targets including EOS')
    return q['response_token_count']


def score_response_logprobs(input_ids, attention_mask, prediction_positions, target_ids, selected_logprobs, *, query_prompt_ids):
    """Pure CPU accounting check, not a model/gradient/softmax implementation.

    Caller supplies already normalized log-probabilities at the exact validated
    positions. Return both sum and mean; DPO/RL normalization is not chosen here.
    """
    import math
    n = validate_logprob_alignment(input_ids, attention_mask, prediction_positions, target_ids, query_prompt_ids=query_prompt_ids)
    need(type(selected_logprobs) is list and len(selected_logprobs) == n
         and all(type(x) in (int, float) and math.isfinite(x) and x <= 0 for x in selected_logprobs),
         'one finite nonpositive conditional log-probability per query token')
    total = math.fsum(selected_logprobs)
    return {'sum': total, 'mean': total/n, 'tokens': n}
