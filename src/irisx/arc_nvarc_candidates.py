"""Task-level augmented candidate generation, inverse mapping and ranking."""

from __future__ import annotations

from collections import defaultdict
import math
import time
from typing import Any, Mapping

from .arc_nvarc_data import grid, seeded_transform, transform_grid, transform_task
from .arc_nvarc_representation import GridTokenizer, END
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


def solve_task(task: Mapping[str, Any], backend: Any, config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One adaptation per full task, then all test outputs share that state."""
    views = default_views(task, int(config["seed"]), int(config.get("color_repeats", 2)))
    maximum_calls = int(config["maximum_calls_per_task"])
    beams = int(config["beams_per_call"])
    max_tokens = int(config["maximum_new_tokens"])
    if maximum_calls < 1 or beams < 1 or max_tokens < 1:
        raise ValidationError("candidate call limits must be positive")
    backend.begin_task(task)
    results = []
    calls = 0
    for test_index in range(len(task["test"])):
        if hasattr(backend, "begin_test"):
            backend.begin_test(test_index)
        candidates = []
        returned_sequences = 0
        for view_index, spec in enumerate(views):
            if calls >= maximum_calls:
                break
            if hasattr(backend, "begin_view"):
                backend.begin_view(spec, view_index)
            transformed = transform_task(task, spec)
            query = GridTokenizer().encode_query(transformed, test_index)
            sequences = backend.generate(query, beams=beams, max_new_tokens=max_tokens)
            calls += 1
            if len(sequences) > beams:
                raise ValidationError("backend returned more sequences than bound")
            returned_sequences += len(sequences)
            for sequence_index, sequence in enumerate(sequences):
                parsed = GridTokenizer().parse_completion(sequence["tokens"], stopped_on_eos=sequence["eos"])
                if parsed is None:
                    continue
                restored = transform_grid(parsed, spec, inverse=True)
                verification = backend.verify(task, test_index, restored)
                candidates.append({"grid": restored, "complete": True,
                                   "source": f"qwen:view{view_index}:seq{sequence_index}",
                                   "beam_nll": float(sequence["beam_nll"]),
                                   "verification_nll": float(verification)})
        ranked = rank_candidates(candidates, policy=config.get("ranking", "votes-minus-mean-nll"))
        attempts = [item["grid"] for item in ranked[:2]]
        results.append({"task_id": task["task_id"], "test_index": test_index,
                        "attempts": attempts, "missing_attempts": 2 - len(attempts),
                        "ranked": ranked, "generation_calls_so_far": calls,
                        "returned_sequences": returned_sequences,
                        "status": "complete" if len(attempts) == 2 else "missing-candidate"})
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
    """Real compact Qwen path. HF beam search replaces the source turbo DFS.

    The divergence is explicit in source-use; this still creates multiple
    likelihood-scored candidates and model-based verification across views.
    """

    kind = "qwen35-compact"

    def __init__(self, model: Any, *, task_adapter: Any = None) -> None:
        self.base_model = model
        self.model = model
        self.adapter = task_adapter
        self.ttt_seconds = 0.0
        self.generate_seconds = 0.0
        self.rank_seconds = 0.0

    def begin_task(self, task: Mapping[str, Any]) -> None:
        self.ttt_seconds = self.generate_seconds = self.rank_seconds = 0.0
        if self.adapter is not None:
            started = time.monotonic()
            self.model = self.adapter.adapt(task)
            self.ttt_seconds = time.monotonic() - started

    def generate(self, query: list[int], *, beams: int, max_new_tokens: int) -> list[dict[str, Any]]:
        import torch

        device = next(self.model.parameters()).device
        ids = torch.tensor([query], dtype=torch.long, device=device)
        started = time.monotonic()
        with torch.inference_mode():
            output = self.model.generate(input_ids=ids, max_new_tokens=max_new_tokens,
                                         num_beams=beams, num_return_sequences=beams,
                                         do_sample=False, return_dict_in_generate=True,
                                         output_scores=True, eos_token_id=END, pad_token_id=13)
        self.generate_seconds += time.monotonic() - started
        result = []
        for index, sequence in enumerate(output.sequences):
            suffix = sequence[len(query):].tolist()
            ended = END in suffix
            if ended:
                suffix = suffix[:suffix.index(END) + 1]
            beam_nll = -float(output.sequences_scores[index]) if hasattr(output, "sequences_scores") else 0.0
            result.append({"tokens": suffix, "eos": ended, "beam_nll": beam_nll})
        return result

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
                logits = self.model(input_ids=torch.tensor([tokens], dtype=torch.long, device=device)).logits[0]
                log_probs = torch.log_softmax(logits[len(query) - 1:-1].float(), dim=-1)
                nll = -log_probs.gather(1, torch.tensor(target, device=device).unsqueeze(1)).sum().item()
            scores.append(nll / len(target))
        self.rank_seconds += time.monotonic() - started
        return sum(scores) / len(scores)

    def end_task(self) -> None:
        self.model = self.base_model
