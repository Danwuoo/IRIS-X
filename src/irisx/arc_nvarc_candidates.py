"""Task-level augmented candidate generation, inverse mapping and ranking."""

from __future__ import annotations

from collections import OrderedDict, defaultdict
import math
import time
from typing import Any, Callable, Mapping

from .arc_nvarc_data import grid, seeded_transform, transform_grid, transform_task
from .arc_nvarc_representation import GridTokenizer, END, PAD
from .errors import ValidationError


def default_views(task: Mapping[str, Any], seed: int, color_repeats: int = 2) -> list[dict[str, Any]]:
    """Eight D4 views times seeded colors, matching the source's 16-view shape."""
    views = []
    for transpose in (False, True):
        for rotation in range(4):
            for repeat in range(color_repeats):
                index = (int(transpose) * 4 + rotation) * color_repeats + repeat
                spec = seeded_transform(task, seed, index)
                spec["rotation"], spec["transpose"] = rotation, transpose
                views.append(spec)
    return views


def rank_candidates(candidates: list[Mapping[str, Any]], *, policy: str = "votes-minus-mean-nll") -> list[dict[str, Any]]:
    """Aggregate only complete, inverse-mapped grids; never examine truth."""
    if policy not in {"votes-minus-mean-nll", "nll-sum"}:
        raise ValidationError("unknown candidate ranking policy")
    groups: dict[tuple[tuple[int, ...], ...], list[Mapping[str, Any]]] = defaultdict(list)
    for item in candidates:
        if not item.get("complete"):
            continue
        value = grid(item["grid"])
        groups[tuple(tuple(row) for row in value)].append(item)
    results = []
    for key, items in groups.items():
        votes = len(items)
        mean_nll = sum(float(item["verification_nll"]) for item in items) / votes
        beam_nll_sum = sum(float(item["beam_nll"]) for item in items)
        if not all(math.isfinite(float(item["verification_nll"])) and math.isfinite(float(item["beam_nll"])) for item in items):
            raise ValidationError("non-finite candidate score")
        score = votes - mean_nll if policy == "votes-minus-mean-nll" else 3 * votes - beam_nll_sum - mean_nll
        results.append({"grid": [list(row) for row in key], "score": score,
                        "votes": votes, "mean_verification_nll": mean_nll,
                        "beam_nll_sum": beam_nll_sum,
                        "sources": sorted(str(item["source"]) for item in items)})
    return sorted(results, key=lambda item: (-item["score"], -item["votes"], item["grid"]))


class PrefixLogitCache:
    """Bounded immutable-prefix logits cache; never stores a mutable KV state."""

    def __init__(self, backend: Callable[[list[int]], list[float]], capacity: int) -> None:
        if capacity < 1:
            raise ValidationError("prefix logit cache capacity must be positive")
        self.backend = backend
        self.capacity = capacity
        self.values: OrderedDict[tuple[int, ...], tuple[float, ...]] = OrderedDict()
        self.hits = self.misses = 0

    def __call__(self, prefix: list[int]) -> list[float]:
        key = tuple(prefix)
        if key in self.values:
            self.hits += 1
            self.values.move_to_end(key)
            return list(self.values[key])
        self.misses += 1
        value = tuple(self.backend(prefix))
        self.values[key] = value
        if len(self.values) > self.capacity:
            self.values.popitem(last=False)
        return list(value)

    def clear(self) -> None:
        self.values.clear()


def bounded_dfs_search(query: list[int], next_log_probs: Callable[[list[int]], list[float]], *,
                       max_new_tokens: int, max_score: float, max_expansions: int,
                       max_sequences: int, deadline: float | None = None,
                       now: Callable[[], float] = time.monotonic) -> dict[str, Any]:
    """Source-order DFS with cumulative NLL pruning and isolated branch state.

    The pinned notebook sorts each node's non-EOS siblings by NLL, accepts EOS
    only below its score threshold, then explores siblings depth first. Full
    prefixes are recomputed here: no mutable Qwen hybrid cache crosses branches.
    This is bounded and deliberately slower than the notebook's batched cache.
    """
    if (not query or max_new_tokens < 1 or max_expansions < 1 or max_sequences < 1 or
            not math.isfinite(max_score) or max_score <= 0):
        raise ValidationError("invalid bounded DFS limits")
    results: list[dict[str, Any]] = []
    expansions = 0
    seen: set[tuple[int, ...]] = set()
    stack: list[tuple[tuple[int, ...], float]] = [((), 0.0)]
    token_limit_hit = False
    reason = "exhausted"
    while stack:
        if len(results) >= max_sequences:
            reason = "sequence_limit"
            break
        if deadline is not None and now() >= deadline:
            reason = "deadline"
            break
        if expansions >= max_expansions:
            reason = "expansion_limit"
            break
        suffix, score = stack.pop()
        probabilities = next_log_probs(query + list(suffix))
        expansions += 1
        if len(probabilities) <= END or any(not math.isfinite(float(p)) for p in probabilities):
            raise ValidationError("DFS backend returned invalid compact logits")
        options = []
        row_lengths = [0]
        for token in suffix:
            if token == 10:
                row_lengths.append(0)
            else:
                row_lengths[-1] += 1
        complete_grid_prefix = bool(suffix) and row_lengths[-1] > 0 and all(
            length == row_lengths[0] for length in row_lengths)
        for token in tuple(range(11)) + (END,):
            if token == 10 and (not suffix or row_lengths[-1] == 0 or
                                (len(row_lengths) > 1 and row_lengths[-1] != row_lengths[0])):
                continue
            if token != 10 and token != END and len(row_lengths) > 1 and row_lengths[-1] >= row_lengths[0]:
                continue
            if token == END and not complete_grid_prefix:
                continue
            nll = score - float(probabilities[token])
            if nll < max_score:
                if token == END:
                    candidate = suffix + (END,)
                    if candidate not in seen:
                        seen.add(candidate)
                        results.append({"tokens": list(candidate), "eos": True,
                                        "beam_nll": nll})
                elif len(suffix) + 1 < max_new_tokens:
                    options.append((nll, token))
                else:
                    token_limit_hit = True
        # Push in reverse so the next pop preserves the source's sorted DFS.
        for child_score, token in reversed(sorted(options, key=lambda item: (item[0], item[1]))):
            stack.append((suffix + (token,), child_score))
    else:
        if len(results) >= max_sequences:
            reason = "sequence_limit"
        elif token_limit_hit:
            reason = "token_limit"
        elif not results:
            reason = "no_valid_candidate"
    return {"sequences": results, "expansions": expansions,
            "completed_candidates": len(results), "stop_reason": reason,
            "max_new_tokens": max_new_tokens, "max_expansions": max_expansions,
            "max_sequences": max_sequences,
            "maximum_reachable_tokens": min(max_new_tokens, max_expansions)}


def bounded_dfs(query: list[int], next_log_probs: Callable[[list[int]], list[float]], *,
                max_new_tokens: int, max_score: float, max_expansions: int,
                max_sequences: int, deadline: float | None = None,
                now: Callable[[], float] = time.monotonic) -> tuple[list[dict[str, Any]], int]:
    """Compatibility wrapper for callers that need only sequences and cost."""
    result = bounded_dfs_search(query, next_log_probs, max_new_tokens=max_new_tokens,
                                max_score=max_score, max_expansions=max_expansions,
                                max_sequences=max_sequences, deadline=deadline, now=now)
    return result["sequences"], result["expansions"]


def solve_task(task: Mapping[str, Any], backend: Any, config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One adaptation per full task, then all test outputs share that state."""
    views = default_views(task, int(config["seed"]), int(config.get("color_repeats", 2)))
    maximum_calls = int(config["maximum_calls_per_task"])
    beams = int(config["beams_per_call"])
    max_tokens = int(config["maximum_new_tokens"])
    if maximum_calls < 1 or beams < 1 or max_tokens < 1:
        raise ValidationError("candidate call limits must be positive")
    results = []
    calls = 0
    verification_calls = 0
    try:
        backend.begin_task(task)
        for test_index in range(len(task["test"])):
            # Hold a share of the remaining invocation budget for each later
            # test; otherwise the first test can consume the whole task cap.
            remaining_tests = len(task["test"]) - test_index
            test_call_stop = calls + math.ceil((maximum_calls - calls) / remaining_tests)
            verified_grids: dict[tuple[tuple[int, ...], ...], float] = {}
            if hasattr(backend, "begin_test"):
                backend.begin_test(test_index)
            candidates = []
            returned_sequences = 0
            generation_observations = []
            for view_index, spec in enumerate(views):
                if calls >= test_call_stop:
                    break
                if hasattr(backend, "begin_view"):
                    backend.begin_view(spec, view_index)
                transformed = transform_task(task, spec)
                query = GridTokenizer().encode_query(transformed, test_index)
                calls += 1  # Reserve the invocation before backend failure.
                sequences = backend.generate(query, beams=beams, max_new_tokens=max_tokens)
                if hasattr(backend, "last_generation_observation"):
                    generation_observations.append({"view_index": view_index,
                                                    **backend.last_generation_observation})
                if len(sequences) > beams:
                    raise ValidationError("backend returned more sequences than bound")
                returned_sequences += len(sequences)
                for sequence_index, sequence in enumerate(sequences):
                    parsed = GridTokenizer().parse_completion(sequence["tokens"], stopped_on_eos=sequence["eos"])
                    if parsed is None:
                        continue
                    restored = transform_grid(parsed, spec, inverse=True)
                    canonical_grid = tuple(tuple(row) for row in restored)
                    if canonical_grid not in verified_grids:
                        verified_grids[canonical_grid] = float(backend.verify(task, test_index, restored))
                        verification_calls += 1
                    verification = verified_grids[canonical_grid]
                    candidates.append({"grid": restored, "complete": True,
                                       "source": f"qwen:view{view_index}:seq{sequence_index}",
                                       "beam_nll": float(sequence["beam_nll"]),
                                       "verification_nll": float(verification)})
            rank_started = time.monotonic()
            ranked = rank_candidates(candidates, policy=config.get("ranking", "votes-minus-mean-nll"))
            if hasattr(backend, "rank_seconds"):
                backend.rank_seconds += time.monotonic() - rank_started
            attempts = [item["grid"] for item in ranked[:2]]
            results.append({"task_id": task["task_id"], "test_index": test_index,
                            "attempts": attempts, "missing_attempts": 2 - len(attempts),
                            "ranked": ranked, "generation_calls_so_far": calls,
                            "verification_calls_so_far": verification_calls,
                            "returned_sequences": returned_sequences,
                            "generation_observations": generation_observations,
                            "status": "complete" if len(attempts) == 2 else "missing-candidate"})
    finally:
        backend.end_task()
    return results


class FixtureCandidateBackend:
    """Synthetic fixture predictions, deliberately marked non-model evidence."""

    kind = "fixture-predictions"

    def __init__(self, predictions: Mapping[str, list[list[list[int]]]]) -> None:
        self.predictions = predictions
        self.task_id = ""
        self.calls = 0
        self.test_index = 0
        self.view_spec: Mapping[str, Any] | None = None

    def begin_task(self, task: Mapping[str, Any]) -> None:
        self.task_id = task["task_id"]
        self.calls = 0

    def begin_test(self, test_index: int) -> None:
        self.test_index = test_index
        self.calls = 0

    def begin_view(self, spec: Mapping[str, Any], view_index: int) -> None:
        self.view_spec = spec

    def generate(self, query: list[int], *, beams: int, max_new_tokens: int) -> list[dict[str, Any]]:
        # The key selects predeclared fixture grids, never evaluator truth.
        current = self.calls
        self.calls += 1
        values = self.predictions.get(f"{self.task_id}:{self.test_index}", [])
        if not values:
            return []
        original = values[current % len(values)]
        rendered = transform_grid(original, self.view_spec) if self.view_spec is not None else original
        output = GridTokenizer().encode_grid(rendered) + [END]
        return [{"tokens": output, "eos": len(output) <= max_new_tokens,
                 "beam_nll": float(current + 1)}] if len(output) <= max_new_tokens else []

    def verify(self, task: Mapping[str, Any], test_index: int, answer: Any) -> float:
        return 0.0

    def end_task(self) -> None:
        self.task_id = ""


class QwenCandidateBackend:
    """Compact Qwen path with isolated-prefix DFS or named HF beam alternative."""

    kind = "qwen35-compact"

    def __init__(self, model: Any, *, task_adapter: Any = None,
                 decoding: str = "bounded-dfs", dfs_max_score: float = -math.log(0.2),
                 dfs_max_expansions: int = 256,
                 dfs_cache_mode: str = "full-prefix-recompute") -> None:
        if decoding not in {"bounded-dfs", "hf-beam"}:
            raise ValidationError("unknown Qwen decoding mode")
        if dfs_cache_mode not in {"full-prefix-recompute", "full-prefix-logit-cache"}:
            raise ValidationError("Qwen3.5 hybrid KV cache mode is unsupported")
        self.base_model = model
        self.model = model
        self.adapter = task_adapter
        self.decoding = decoding
        self.dfs_max_score = dfs_max_score
        self.dfs_max_expansions = dfs_max_expansions
        self.dfs_cache_mode = dfs_cache_mode
        self.prefix_cache: PrefixLogitCache | None = None
        self.last_generation_observation: dict[str, Any] = {}
        self.forward_calls = 0
        self.verification_calls = 0
        self.ttt_seconds = 0.0
        self.generate_seconds = 0.0
        self.rank_seconds = 0.0

    def begin_task(self, task: Mapping[str, Any]) -> None:
        self.ttt_seconds = self.generate_seconds = self.rank_seconds = 0.0
        self.forward_calls = self.verification_calls = 0
        self.last_generation_observation = {}
        self.prefix_cache = None
        if self.adapter is not None:
            started = time.monotonic()
            self.model = self.adapter.adapt(task)
            self.ttt_seconds = time.monotonic() - started

    def generate(self, query: list[int], *, beams: int, max_new_tokens: int) -> list[dict[str, Any]]:
        import torch

        device = next(self.model.parameters()).device
        started = time.monotonic()
        try:
            if self.decoding == "bounded-dfs":
                def next_probs(prefix: list[int]) -> list[float]:
                    ids = torch.tensor([prefix], dtype=torch.long, device=device)
                    with torch.inference_mode():
                        # Recompute per prefix. A mutable hybrid cache cannot
                        # be shared safely between sibling DFS branches.
                        logits = self.model(input_ids=ids, use_cache=False).logits[0, -1]
                        values = torch.log_softmax(logits.float(), dim=-1).cpu().tolist()
                    self.forward_calls += 1
                    return values
                callback = next_probs
                if self.dfs_cache_mode == "full-prefix-logit-cache":
                    if self.prefix_cache is None:
                        self.prefix_cache = PrefixLogitCache(next_probs, self.dfs_max_expansions)
                    callback = self.prefix_cache
                before_hits = self.prefix_cache.hits if self.prefix_cache is not None else 0
                search = bounded_dfs_search(query, callback, max_new_tokens=max_new_tokens,
                                            max_score=self.dfs_max_score,
                                            max_expansions=self.dfs_max_expansions,
                                            max_sequences=beams)
                self.last_generation_observation = {
                    key: value for key, value in search.items() if key != "sequences"}
                self.last_generation_observation["cache_mode"] = self.dfs_cache_mode
                self.last_generation_observation["cache_hits"] = (
                    self.prefix_cache.hits - before_hits if self.prefix_cache is not None else 0)
                return search["sequences"]
            ids = torch.tensor([query], dtype=torch.long, device=device)
            with torch.inference_mode():
                output = self.model.generate(input_ids=ids, max_new_tokens=max_new_tokens,
                                             num_beams=beams, num_return_sequences=beams,
                                             do_sample=False, return_dict_in_generate=True,
                                             output_scores=True, eos_token_id=END, pad_token_id=PAD)
            result = []
            for index, sequence in enumerate(output.sequences):
                suffix = sequence[len(query):].tolist()
                ended = END in suffix
                if ended:
                    suffix = suffix[:suffix.index(END) + 1]
                sequence_scores = getattr(output, "sequences_scores", None)
                beam_nll = -float(sequence_scores[index]) if sequence_scores is not None else 0.0
                result.append({"tokens": suffix, "eos": ended, "beam_nll": beam_nll})
            self.last_generation_observation = {
                "stop_reason": "hf-beam-return", "completed_candidates": sum(item["eos"] for item in result),
                "max_new_tokens": max_new_tokens, "max_sequences": beams,
                "internal_forward_calls": None, "cache_mode": "hf-managed"}
            return result
        finally:
            self.generate_seconds += time.monotonic() - started

    def verify(self, task: Mapping[str, Any], test_index: int, answer: Any) -> float:
        """Mean answer NLL under eight fixed, solver-visible views."""
        import torch

        tokenizer = GridTokenizer()
        started = time.monotonic()
        scores = []
        for spec in default_views(task, 17, color_repeats=1):
            transformed = transform_task(task, spec)
            query = tokenizer.encode_query(transformed, test_index)
            target = tokenizer.encode_grid(transform_grid(answer, spec)) + [END]
            tokens = query + target
            device = next(self.model.parameters()).device
            with torch.inference_mode():
                logits = self.model(input_ids=torch.tensor([tokens], dtype=torch.long, device=device),
                                    use_cache=False).logits[0]
                self.forward_calls += 1
                log_probs = torch.log_softmax(logits[len(query) - 1:-1].float(), dim=-1)
                nll = -log_probs.gather(1, torch.tensor(target, device=device).unsqueeze(1)).sum().item()
            scores.append(nll / len(target))
        self.verification_calls += 1
        self.rank_seconds += time.monotonic() - started
        return sum(scores) / len(scores)

    def end_task(self) -> None:
        try:
            if self.adapter is not None:
                self.adapter.reset(clear_observation=False)
        finally:
            if self.prefix_cache is not None:
                self.prefix_cache.clear()
            self.prefix_cache = None
            self.model = self.base_model
