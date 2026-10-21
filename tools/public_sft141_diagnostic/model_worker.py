"""Independent public Transformers diagnostic worker, with no evaluator access.

Only the CLI creates a real CUDA backend. ``run`` accepts a fake backend for
CPU contract tests; those tests are not evidence about the 2B model or a GPU.
The controller must enforce its original, whole-session wall-clock deadline.
This process has an additional cooperative deadline and never resumes a run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import tempfile
import time
from typing import Any, Callable

from . import contract

SCHEMA = "iris-public-sft141-worker-v1"
MAX_BUDGET_SECONDS = 7200.0
CONTEXT_CAP = 8192
VIEWS = tuple(range(8))
PROJECTION_SAFETY_FACTOR = 1.25


class BudgetExceeded(RuntimeError):
    """The original worker budget or its reserved closure window was reached."""


class AdmissionFailure(RuntimeError):
    """The fixed protocol cannot run on the actual backend."""


class Deadline:
    def __init__(self, seconds: float, clock: Callable[[], float] = time.monotonic):
        if not math.isfinite(seconds) or not 0 < seconds <= MAX_BUDGET_SECONDS:
            raise ValueError("budget must be finite, positive, and at most 7200 seconds")
        self.clock = clock
        self.start = clock()
        self.seconds = float(seconds)
        self.end = self.start + seconds
        # Reserve time for immutable serialization and controller scoring/closure.
        self.reserve = min(120.0, max(15.0, seconds * 0.02))
        self.work_end = self.end - self.reserve

    def remaining(self) -> float:
        return max(0.0, self.end - self.clock())

    def work_remaining(self) -> float:
        return max(0.0, self.work_end - self.clock())

    def check(self) -> None:
        if self.clock() >= self.work_end:
            raise BudgetExceeded("work deadline reached; closure reserve is not reusable")

    def expired(self) -> bool:
        return self.clock() >= self.work_end

    def receipt(self) -> dict[str, Any]:
        return {"budget_seconds": self.seconds, "elapsed_seconds": self.clock() - self.start,
                "remaining_seconds": self.remaining(), "closure_reserve_seconds": self.reserve,
                "work_remaining_seconds": self.work_remaining(), "resume_supported": False}


class Artifacts:
    """Atomically publish complete JSON bytes without ever replacing a receipt.

    Hard-link publication is atomic and exclusive on the intended NTFS/Linux
    filesystems. An unsupported filesystem fails closed rather than weakening
    this guarantee. A controller may read completed receipts after termination.
    """
    def __init__(self, output: Path | str):
        self.root = Path(output)
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / "receipts").mkdir()

    def write(self, relative: str, value: Any) -> None:
        destination = self.root / relative
        if destination.parent not in (self.root, self.root / "receipts"):
            raise ValueError("receipt must be an immediate child of output or receipts")
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8") + b"\n"
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, destination)  # Fails if a receipt already exists.
        finally:
            os.unlink(temporary)


def _digest(tokens: list[int]) -> str:
    return hashlib.sha256(json.dumps(tokens, separators=(",", ":")).encode()).hexdigest()


def _key(grid: list[list[int]]) -> str:
    return json.dumps(grid, separators=(",", ":"))


def validate_plan(plan: Any) -> None:
    """Reject label-bearing test records instead of silently ignoring labels."""
    if not isinstance(plan, dict) or plan.get("schema") != "iris-public-sft141-plan-v1":
        raise ValueError("unsupported gold-free plan schema")
    if set(plan) - {"schema", "parents", "provenance", "protocol"}:
        raise ValueError("unexpected plan fields")
    parents = plan.get("parents")
    if not isinstance(parents, list) or len(parents) != 12:
        raise ValueError("fixed diagnostic requires exactly 12 parents")
    seen = set()
    forbidden = {"answers", "gold", "solutions", "labels", "test_output", "outputs"}

    def metadata_is_clean(value: Any) -> None:
        if isinstance(value, dict):
            if forbidden.intersection(value) or "output" in value:
                raise ValueError("label-bearing metadata is not an inference input")
            for item in value.values():
                metadata_is_clean(item)
        elif isinstance(value, list):
            for item in value:
                metadata_is_clean(item)

    metadata_is_clean(plan.get("provenance", {}))
    metadata_is_clean(plan.get("protocol", {}))
    for parent in parents:
        if not isinstance(parent, dict) or set(parent) - {"task_id", "train", "test", "selection"}:
            raise ValueError("unexpected parent fields")
        task_id = parent.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in seen:
            raise ValueError("task IDs must be unique nonempty strings")
        seen.add(task_id)
        metadata_is_clean(parent.get("selection", {}))
        train, tests = parent.get("train"), parent.get("test")
        if not isinstance(train, list) or not train or not isinstance(tests, list) or not tests:
            raise ValueError("each parent requires all supports and at least one query")
        for example in train:
            if not isinstance(example, dict) or set(example) != {"input", "output"}:
                raise ValueError("support record must contain input and output only")
            contract.validate_grid(example["input"])
            contract.validate_grid(example["output"])
        for index, query in enumerate(tests):
            if not isinstance(query, dict) or set(query) != {"input", "test_index", "query_id"}:
                raise ValueError("test records must be gold-free input/index/ID only")
            if type(query["test_index"]) is not int or query["test_index"] != index:
                raise ValueError("test indices must preserve original contiguous order")
            if query["query_id"] != f"{task_id}:{index}":
                raise ValueError("query ID does not match parent and original index")
            contract.validate_grid(query["input"])


def full_answer_nll(logits: Any, prompt_length: int, answer: list[int]) -> float:
    """Sum FP32 token NLL, including EOS, at causal indices p-1+j.

    ``logits`` is [1, sequence, vocab]. No prompt tokens, padding, or length
    normalization enter the score. This helper is intentionally CPU-testable.
    """
    import torch
    if prompt_length < 1 or not answer or answer[-1] != contract.EOS_ID:
        raise ValueError("a nonempty full answer ending in EOS is required")
    if any(type(token) is not int or not 0 <= token < 16 for token in answer):
        raise ValueError("answer contains non-native token")
    if logits.ndim != 3 or logits.shape[0] != 1 or logits.shape[2] != 16:
        raise ValueError("logits must be batch-one native-vocabulary logits")
    start = prompt_length - 1
    end = start + len(answer)
    if logits.shape[1] < end:
        raise ValueError("missing logits for full answer including EOS")
    target = torch.tensor(answer, dtype=torch.long, device=logits.device)
    log_probs = torch.log_softmax(logits[0, start:end, :].float(), dim=-1)
    nll = -log_probs.gather(-1, target[:, None]).sum()
    value = float(nll.item())
    if not math.isfinite(value):
        raise ValueError("nonfinite full-answer NLL")
    return value


def load_public_tokenizer(model_dir: str):
    """Load the verified public tokenizer.json without auto-class conversion.

    Some Transformers AutoTokenizer versions reconstruct this custom WordLevel
    file as BPE and silently drop role tokens. Loading the exact tokenizer file
    avoids that conversion; the vocabulary, backend, decoding, and complete
    prompt encoding are still independently checked before any model load.
    """
    from transformers import PreTrainedTokenizerFast
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_file=str(Path(model_dir) / "tokenizer.json"),
        eos_token="<|im_end|>", pad_token="<|endoftext|>", bos_token="<|endoftext|>")
    if type(tokenizer.backend_tokenizer.model).__name__ != "WordLevel":
        raise AdmissionFailure("verified public tokenizer backend must remain WordLevel")
    return tokenizer


class TransformersBackend:
    """Public AutoModel only: BF16 CUDA, SDPA, no remote code or fallback."""
    def __init__(self, model_dir: str, plan: dict[str, Any], deadline: Deadline,
                 artifacts: Artifacts | None = None):
        import torch
        import transformers
        from transformers import AutoConfig, AutoModelForCausalLM, GenerationConfig
        self.torch = torch
        self.deadline = deadline
        deadline.check()
        if artifacts is not None:
            artifacts.write("environment.json", {"torch_version": torch.__version__,
                "transformers_version": transformers.__version__, "python_version": platform.python_version(),
                "cuda_runtime_version": torch.version.cuda, "cuda_available": torch.cuda.is_available(),
                "visible_gpu_count": torch.cuda.device_count()})
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise AdmissionFailure("exactly one visible CUDA GPU is required")
        if not torch.cuda.is_bf16_supported():
            raise AdmissionFailure("actual CUDA device does not support BF16")
        self.device = torch.device("cuda:0")
        self.tokenizer = load_public_tokenizer(model_dir)
        config = AutoConfig.from_pretrained(
            model_dir, local_files_only=True, trust_remote_code=False)
        if (Path(model_dir) / "adapter_config.json").exists() or getattr(config, "quantization_config", None):
            raise AdmissionFailure("adapters and quantization are not part of this public baseline")
        if config.vocab_size != 16:
            raise AdmissionFailure("public model vocab_size must be exactly 16")
        self._verify_tokenizer(plan)
        context = getattr(config, "max_position_embeddings", None)
        if type(context) is not int or context < 1:
            raise AdmissionFailure("model does not declare a finite positive context limit")
        self.max_context = min(CONTEXT_CAP, context)
        deadline.check()
        load_start = deadline.clock()
        if artifacts is not None:
            free, total = torch.cuda.mem_get_info(self.device)
            artifacts.write("load_preflight.json", {"model_config": config.to_dict(),
                "gpu_name": torch.cuda.get_device_name(0),
                "compute_capability": list(torch.cuda.get_device_capability(0)),
                "bf16_supported": True, "gpu_free_bytes": free, "gpu_total_bytes": total,
                "dtype": "bfloat16", "attention_implementation": "sdpa",
                "model_declared_context": context, "effective_context_cap": self.max_context,
                "tokenizer_contract_verified": True,
                "tokenizer_class": type(self.tokenizer).__name__,
                "tokenizer_backend_model": type(self.tokenizer.backend_tokenizer.model).__name__,
                "tokenizer_loader": "exact-local-tokenizer.json-PreTrainedTokenizerFast",
                "budget": deadline.receipt()})
        self.model = AutoModelForCausalLM.from_pretrained(
            model_dir, local_files_only=True, trust_remote_code=False,
            use_safetensors=True, torch_dtype=torch.bfloat16,
            attn_implementation="sdpa")
        self.model.to(device=self.device, dtype=torch.bfloat16)
        self.model.eval()
        if getattr(self.model, "is_quantized", False) or getattr(self.model, "peft_config", None):
            raise AdmissionFailure("loaded model unexpectedly contains quantization or PEFT adapters")
        torch.cuda.synchronize(self.device)
        deadline.check()
        if any(parameter.device != self.device for parameter in self.model.parameters()):
            raise AdmissionFailure("all model parameters must be on the single CUDA GPU")
        if any(parameter.is_floating_point() and parameter.dtype != torch.bfloat16
               for parameter in self.model.parameters()):
            raise AdmissionFailure("floating model parameters are not uniformly BF16")
        if getattr(self.model.config, "_attn_implementation", None) != "sdpa":
            raise AdmissionFailure("loaded model did not retain requested SDPA attention")
        # A NEW config avoids inherited penalties, sampling filters, or constraints.
        self.generation_config = GenerationConfig(
            max_new_tokens=contract.MAX_NEW_TOKENS, do_sample=False, num_beams=1,
            num_beam_groups=1, num_return_sequences=1, use_cache=True,
            eos_token_id=contract.EOS_ID, pad_token_id=contract.PAD_ID,
            bos_token_id=None, forced_bos_token_id=None, forced_eos_token_id=None,
            repetition_penalty=1.0, encoder_repetition_penalty=1.0,
            no_repeat_ngram_size=0, encoder_no_repeat_ngram_size=0,
            length_penalty=1.0, diversity_penalty=0.0, min_length=0,
            min_new_tokens=0, early_stopping=False, bad_words_ids=None,
            force_words_ids=None, suppress_tokens=None, begin_suppress_tokens=None,
            constraints=None, sequence_bias=None, penalty_alpha=None,
            renormalize_logits=False, remove_invalid_values=False,
            return_dict_in_generate=False, output_scores=False,
            output_attentions=False, output_hidden_states=False)
        properties = torch.cuda.get_device_properties(0)
        rotary = sorted({type(module).__name__ for module in self.model.modules()
                         if "rotary" in type(module).__name__.lower()})
        free, total = torch.cuda.mem_get_info(self.device)
        self.metadata = {
            "backend": "public-transformers", "torch_version": torch.__version__,
            "transformers_version": transformers.__version__, "python_version": platform.python_version(),
            "cuda_runtime_version": torch.version.cuda, "gpu_name": properties.name,
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "visible_gpu_count": torch.cuda.device_count(), "bf16_supported": True,
            "gpu_total_bytes": total, "gpu_free_bytes_after_load": free,
            "gpu_properties_total_bytes": properties.total_memory,
            "model_class": type(self.model).__name__, "model_config": config.to_dict(),
            "dtype": "bfloat16", "attention_implementation": "sdpa",
            "model_declared_context": context, "declared_initial_context_cap": CONTEXT_CAP,
            "effective_context_cap": self.max_context, "rotary_classes": rotary,
            "rope_scaling": getattr(config, "rope_scaling", None),
            "position_compatibility": "unresolved; standard Transformers position handling only; "
                "no claim of author-specific multi-axis RoPE equivalence",
            "load_seconds": deadline.clock() - load_start,
            "generation_config": self.generation_config.to_dict(),
            "tokenizer_contract_verified": True,
            "tokenizer_class": type(self.tokenizer).__name__,
            "tokenizer_backend_model": type(self.tokenizer.backend_tokenizer.model).__name__,
            "tokenizer_loader": "exact-local-tokenizer.json-PreTrainedTokenizerFast",
            "tokenizer_file_sha256": hashlib.sha256((Path(model_dir) / "tokenizer.json").read_bytes()).hexdigest(),
            "supports_dropped": 0,
            "quantization": None, "offload": False, "ttt": False, "peft": False,
            "compiled": False, "remote_code": False, "local_files_only": True,
        }

    def _verify_tokenizer(self, plan: dict[str, Any]) -> None:
        # Public tokenizer.json uses ByteLevel's U+010A glyph for LF in its
        # vocabulary, while rendered prompts and decoded text use literal LF.
        expected = {("Ċ" if token == "\n" else token): index
                    for index, token in enumerate(contract.TOKEN_STRINGS)}
        if self.tokenizer.get_vocab() != expected:
            raise AdmissionFailure("actual tokenizer vocabulary differs from 16-token contract")
        if self.tokenizer.eos_token_id != contract.EOS_ID or self.tokenizer.pad_token_id != contract.PAD_ID:
            raise AdmissionFailure("actual tokenizer EOS/PAD IDs differ from contract")
        for index, spelling in enumerate(contract.TOKEN_STRINGS):
            decoded = self.tokenizer.decode([index], skip_special_tokens=False,
                                            clean_up_tokenization_spaces=False)
            if decoded != spelling:
                raise AdmissionFailure("actual tokenizer decode differs from rendered native contract")
        for parent in plan["parents"]:
            for query in parent["test"]:
                for view in VIEWS:
                    text = contract.prompt_text(parent["train"], query["input"], view)
                    actual = self.tokenizer.encode(text, add_special_tokens=False)
                    if actual != contract.prompt_ids(parent["train"], query["input"], view):
                        raise AdmissionFailure("actual tokenizer prompt differs from contract")

    def _begin(self, deadline: Deadline) -> float:
        deadline.check()
        self.torch.cuda.synchronize(self.device)
        self.torch.cuda.reset_peak_memory_stats(self.device)
        return deadline.clock()

    def memory_snapshot(self) -> dict[str, Any]:
        free, total = self.torch.cuda.mem_get_info(self.device)
        return {"allocated_bytes": self.torch.cuda.memory_allocated(self.device),
                "reserved_bytes": self.torch.cuda.memory_reserved(self.device),
                "peak_allocated_bytes": self.torch.cuda.max_memory_allocated(self.device),
                "peak_reserved_bytes": self.torch.cuda.max_memory_reserved(self.device),
                "free_bytes": free, "total_bytes": total}

    def _finish(self, started: float, deadline: Deadline) -> dict[str, Any]:
        self.torch.cuda.synchronize(self.device)
        return {"seconds": deadline.clock() - started, "memory": self.memory_snapshot()}

    def generate(self, prompt: list[int], max_new_tokens: int, deadline: Deadline) -> dict[str, Any]:
        from transformers import StoppingCriteria, StoppingCriteriaList
        if max_new_tokens != contract.MAX_NEW_TOKENS:
            raise ValueError("generation ceiling is fixed at 931, never a tiny warm-up")
        if len(prompt) + max_new_tokens > self.max_context:
            raise AdmissionFailure("full support prompt plus 931-token allowance exceeds context")
        started = self._begin(deadline)
        torch = self.torch

        class StopAtDeadline(StoppingCriteria):
            def __call__(self, input_ids: Any, scores: Any, **kwargs: Any) -> bool:
                return deadline.expired()

        ids = torch.tensor([prompt], dtype=torch.long, device=self.device)
        with torch.inference_mode():
            sequences = self.model.generate(
                input_ids=ids, attention_mask=torch.ones_like(ids),
                generation_config=self.generation_config,
                stopping_criteria=StoppingCriteriaList([StopAtDeadline()]))
        returned = sequences[0].tolist()
        if returned[:len(prompt)] != prompt:
            raise AdmissionFailure("generate did not preserve the full prompt")
        answer = returned[len(prompt):]
        receipt = self._finish(started, deadline)
        receipt.update({"token_ids": answer, "generated_tokens": len(answer),
                        "termination": "eos" if answer and answer[-1] == contract.EOS_ID
                        else "deadline" if deadline.expired() else "max_tokens"})
        return receipt

    def score(self, prompt: list[int], answer: list[int], deadline: Deadline) -> dict[str, Any]:
        if len(prompt) + len(answer) > self.max_context:
            raise AdmissionFailure("full-answer scoring exceeds context; no truncation permitted")
        if not answer or answer[-1] != contract.EOS_ID:
            raise ValueError("full-answer scoring requires EOS")
        started = self._begin(deadline)
        # The final answer token is the target of the final supplied position.
        combined = prompt + answer[:-1]
        torch = self.torch
        ids = torch.tensor([combined], dtype=torch.long, device=self.device)
        with torch.inference_mode():
            logits = self.model(input_ids=ids, attention_mask=torch.ones_like(ids),
                                use_cache=False).logits
            nll = full_answer_nll(logits, len(prompt), answer)
        receipt = self._finish(started, deadline)
        receipt.update({"nll": nll, "answer_tokens": len(answer),
                        "input_tokens": len(combined), "batch_size": 1, "use_cache": False})
        return receipt


def _queries(plan: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for parent in plan["parents"]:
        for query in parent["test"]:
            prompts = [contract.prompt_ids(parent["train"], query["input"], view) for view in VIEWS]
            result.append({"task_id": parent["task_id"], "test_index": query["test_index"],
                           "query_id": query["query_id"], "_prompts": prompts,
                           "prompt_tokens_by_view": [len(prompt) for prompt in prompts],
                           "views": [{"view": view, "status": "missing"} for view in VIEWS],
                           "candidates": [], "vote": [], "rescored": [],
                           "vote_complete": False, "rescoring_complete": False, "status": "pending"})
    return result


def _failure_memory(backend: Any) -> dict[str, Any] | None:
    try:
        snapshot = getattr(backend, "memory_snapshot", None)
        return snapshot() if snapshot else None
    except Exception as exc:
        return {"unavailable": f"{type(exc).__name__}: {exc}"}


def _generation_record(backend: Any, prompt: list[int], deadline: Deadline) -> dict[str, Any]:
    record = dict(backend.generate(prompt, contract.MAX_NEW_TOKENS, deadline))
    tokens = record.get("token_ids")
    if not isinstance(tokens, list) or any(type(token) is not int for token in tokens):
        raise AdmissionFailure("backend did not return raw integer token IDs")
    if len(tokens) > contract.MAX_NEW_TOKENS:
        raise AdmissionFailure("backend exceeded the fixed generation ceiling")
    if not math.isfinite(record.get("seconds", float("nan"))) or record["seconds"] < 0:
        raise AdmissionFailure("backend generation timing is invalid")
    record.update({"prompt_tokens": len(prompt), "prompt_sha256": _digest(prompt),
                   "max_new_tokens": contract.MAX_NEW_TOKENS,
                   "generated_tokens": len(tokens), "eos_seen": contract.EOS_ID in tokens,
                   "truncated": not (tokens and tokens[-1] == contract.EOS_ID),
                   "valid": False, "grid": None})
    try:
        record["grid"] = contract.parse_answer(tokens)
        record["valid"] = True
        record["parse_error"] = None
    except ValueError as exc:
        record["parse_error"] = str(exc)
    return record


def _score_record(backend: Any, prompt: list[int], answer: list[int], deadline: Deadline) -> dict[str, Any]:
    record = dict(backend.score(prompt, answer, deadline))
    if not math.isfinite(record.get("nll", float("nan"))) or record["nll"] < 0:
        raise AdmissionFailure("NLL must be finite and nonnegative")
    if not math.isfinite(record.get("seconds", float("nan"))) or record["seconds"] < 0:
        raise AdmissionFailure("backend scoring timing is invalid")
    record.update({"prompt_tokens": len(prompt), "answer_tokens": len(answer),
                   "input_tokens": len(prompt) + len(answer) - 1,
                   "prompt_sha256": _digest(prompt), "answer_sha256": _digest(answer),
                   "includes_eos": True, "normalization": "sum-not-token-mean"})
    return record


def _projection(queries: list[dict[str, Any]], generation: list[dict[str, Any]],
                scoring: list[dict[str, Any]], deadline: Deadline, stage: str) -> dict[str, Any]:
    """Separate observed-EOS calibration from the pessimistic 931-token envelope.

    Admission is based on measured completed-EOS costs, not a requirement that
    every view emit a 30x30 grid. The watchdog is still authoritative. The
    candidate count of incomplete queries is explicitly estimated at eight,
    since three single-view admissions cannot establish view agreement.
    """
    missing = [(query, view) for query in queries for view in VIEWS
               if query["views"][view]["status"] == "missing"]
    completed_eos = [row for row in generation if not row["truncated"]]
    observed_generation = completed_eos or generation
    if not observed_generation or not scoring:
        raise AdmissionFailure("projection requires measured generation and scoring receipts")

    def nearest(rows: list[dict[str, Any]], key: str, target: int) -> dict[str, Any]:
        return min(rows, key=lambda row: (abs(row[key] - target), -row["seconds"]))

    def estimate_score(target_tokens: int) -> float:
        row = nearest(scoring, "input_tokens", target_tokens)
        return row["seconds"] * max(1.0, target_tokens / max(1, row["input_tokens"])) ** 2

    def envelope_score(target_tokens: int) -> float:
        return max(row["seconds"] * max(1.0, target_tokens / max(1, row["input_tokens"])) ** 2
                   for row in scoring)

    generation_estimate = 0.0
    generation_envelope = 0.0
    generation_rate = max(row["seconds"] / max(1, row["generated_tokens"]) for row in generation)
    max_measured_prompt = max(row["prompt_tokens"] for row in generation)
    for query, view in missing:
        length = len(query["_prompts"][view])
        row = nearest(observed_generation, "prompt_tokens", length)
        generation_estimate += row["seconds"] * max(1.0, length / max(1, row["prompt_tokens"]))
        generation_envelope += generation_rate * contract.MAX_NEW_TOKENS * max(
            1.0, length / max_measured_prompt)
    scoring_estimate = 0.0
    scoring_envelope = 0.0
    score_calls = 0
    for query in queries:
        if query["vote_complete"]:
            for candidate in query["candidates"]:
                for view in VIEWS:
                    if candidate["view_nll"][view]["status"] == "complete":
                        continue
                    length = len(query["_prompts"][view])
                    target = length + len(contract.answer_ids(contract.transform(candidate["grid"], view))) - 1
                    score_calls += 1
                    scoring_estimate += estimate_score(target)
                    scoring_envelope += envelope_score(length + contract.MAX_NEW_TOKENS - 1)
        else:
            for view in VIEWS:
                length = len(query["_prompts"][view])
                observed = nearest(observed_generation, "prompt_tokens", length)
                target = length + observed["generated_tokens"] - 1
                score_calls += 8
                scoring_estimate += 8 * estimate_score(target)
                scoring_envelope += 8 * envelope_score(length + contract.MAX_NEW_TOKENS - 1)
    estimate = PROJECTION_SAFETY_FACTOR * (generation_estimate + scoring_estimate)
    envelope = PROJECTION_SAFETY_FACTOR * (generation_envelope + scoring_envelope)
    return {"stage": stage, "observed_elapsed_seconds": deadline.clock() - deadline.start,
            "remaining_generation_calls": len(missing), "remaining_score_calls_upper_bound": score_calls,
            "measured_generation_calls": len(generation), "measured_score_calls": len(scoring),
            "measured_generation_seconds": sum(row["seconds"] for row in generation),
            "measured_scoring_seconds": sum(row["seconds"] for row in scoring),
            "estimated_generation_seconds": generation_estimate,
            "estimated_scoring_seconds": scoring_estimate,
            "safety_factor": PROJECTION_SAFETY_FACTOR,
            "estimated_remaining_work_seconds": estimate,
            "worst_case_envelope_seconds": envelope,
            "worst_case_generation_seconds": generation_envelope,
            "worst_case_scoring_seconds": scoring_envelope,
            "work_remaining_seconds": deadline.work_remaining(),
            "closure_reserve_seconds": deadline.reserve,
            "fits": estimate <= deadline.work_remaining(),
            "generation_fits": PROJECTION_SAFETY_FACTOR * generation_estimate <= deadline.work_remaining(),
            "worst_case_fits": envelope <= deadline.work_remaining(),
            "admission_basis": "measured-completed-EOS-calibration-not-worst-case-envelope" if completed_eos
                               else "measured-capped-generation-no-valid-EOS-observed",
            "observed_eos_calibration_calls": len(completed_eos),
            "uncertainty": "three unique admission queries; future answer length, decode latency and "
                           "candidate diversity are unknown; fixed hard deadline may produce partial results",
            "method": "nearest observed full-prompt EOS generation and full-answer NLL costs; "
                      "linear prompt / quadratic scoring-length scale; up to eight distinct candidates; "
                      "separate 931-token worst-case envelope is reported, not required to fit"}


def _rank(query: dict[str, Any]) -> None:
    pool: dict[str, dict[str, Any]] = {}
    for row in query["views"]:
        if row.get("valid"):
            grid = row["canonical_grid"]
            key = _key(grid)
            candidate = pool.setdefault(key, {"canonical_key": key, "grid": grid, "count": 0,
                "view_nll": [{"view": view, "status": "missing"} for view in VIEWS],
                "mean_nll": None, "combined_score": None})
            candidate["count"] += 1
    query["candidates"] = sorted(pool.values(), key=lambda candidate: candidate["canonical_key"])
    query["vote"] = [candidate["grid"] for candidate in sorted(
        pool.values(), key=lambda candidate: (-candidate["count"], candidate["canonical_key"]))[:2]]
    query["vote_complete"] = all(row["status"] == "complete" for row in query["views"])
    query["status"] = "vote_complete" if query["vote_complete"] else "partial_views"


def _result(result: dict[str, Any], deadline: Deadline, artifacts: Artifacts) -> dict[str, Any]:
    for query in result["queries"]:
        query.pop("_prompts", None)
    views = [row for query in result["queries"] for row in query["views"]]
    result["counts"] = {"queries": len(result["queries"]), "expected_views": 8 * len(result["queries"]),
        "missing_views": sum(row["status"] == "missing" for row in views),
        "failed_views": sum(row["status"] == "failed" for row in views),
        "invalid_views": sum(row["status"] == "complete" and not row["valid"] for row in views),
        "truncated_views": sum(row.get("truncated", False) for row in views),
        "valid_views": sum(row.get("valid", False) for row in views),
        "vote_complete_queries": sum(query["vote_complete"] for query in result["queries"]),
        "rescoring_complete_queries": sum(query["rescoring_complete"] for query in result["queries"])}
    result["timings"] = {
        "admission_generation_seconds": sum(row.get("seconds", 0.0) for row in result["context_admission"]),
        "admission_scoring_seconds": sum(row.get("scoring_receipt", {}).get("seconds", 0.0)
                                         for row in result["context_admission"]),
        "panel_generation_seconds": sum(row.get("seconds", 0.0) for row in views),
        "panel_rescoring_seconds": sum(row.get("seconds", 0.0) for query in result["queries"]
                                       for candidate in query["candidates"] for row in candidate["view_nll"]),
    }
    result["budget"] = deadline.receipt()
    result["full_panel_complete"] = result["status"] == "complete" and all(
        query["vote_complete"] and query["rescoring_complete"] for query in result["queries"])
    result["capability_claim"] = False
    artifacts.write("result.json", result)
    return result


def run(plan: dict[str, Any], backend: Any, output: Path | str, budget_seconds: float,
        clock: Callable[[], float] = time.monotonic, *, deadline: Deadline | None = None,
        artifacts: Artifacts | None = None) -> dict[str, Any]:
    """Run the fixed diagnostic. Backend injection is for tests, not the CLI."""
    deadline = deadline or Deadline(budget_seconds, clock)
    artifacts = artifacts or Artifacts(output)
    validate_plan(plan)
    queries = _queries(plan)
    result: dict[str, Any] = {"schema": SCHEMA, "status": "running", "phase": "context_admission",
        "queries": queries, "backend": backend.metadata, "context_admission": [], "projections": [],
        "ranking_formula": "A=count; B=count-mean(sum full-answer NLL over 8 D4 conditions)",
        "errors": [], "declared_initial_context_cap": CONTEXT_CAP,
        "timings": {"admission_generation_seconds": 0.0, "admission_scoring_seconds": 0.0,
                    "panel_generation_seconds": 0.0, "panel_rescoring_seconds": 0.0}}
    artifacts.write("backend.json", backend.metadata)
    generation_costs: list[dict[str, Any]] = []
    score_costs: list[dict[str, Any]] = []
    try:
        limit = min(CONTEXT_CAP, backend.max_context)
        for query in queries:
            for view, prompt in enumerate(query["_prompts"]):
                if len(prompt) + contract.MAX_NEW_TOKENS > limit:
                    raise AdmissionFailure(f"{query['query_id']} view {view}: full prompt "
                                           f"{len(prompt)} + 931 exceeds context cap {limit}")
        ordered = sorted(enumerate(queries), key=lambda pair: (
            max(pair[1]["prompt_tokens_by_view"]), pair[1]["query_id"]))
        # Three unique real queries: short, median, longest, exact longest D4 view.
        selected = [ordered[0], ordered[len(ordered) // 2], ordered[-1]]
        for label, (query_index, query) in zip(("short", "median", "longest"), selected):
            deadline.check()
            view = max(VIEWS, key=lambda number: query["prompt_tokens_by_view"][number])
            prompt = query["_prompts"][view]
            row = {"length_class": label, "query_id": query["query_id"], "query_index": query_index,
                   "view": view, "prompt_tokens_by_view": query["prompt_tokens_by_view"]}
            operation_started = deadline.clock()
            try:
                row.update(_generation_record(backend, prompt, deadline))
            except Exception as exc:
                row.update({"status": "failed", "seconds": deadline.clock() - operation_started,
                            "token_ids": None, "memory": _failure_memory(backend),
                            "error": f"{type(exc).__name__}: {exc}"})
                artifacts.write(f"receipts/admission-{label}-generation.json", row)
                result["context_admission"].append(row)
                raise
            row["status"] = "complete"
            artifacts.write(f"receipts/admission-{label}-generation.json", row)
            result["context_admission"].append(row)
            generation_costs.append(row)
            result["timings"]["admission_generation_seconds"] += row["seconds"]
            if row["termination"] == "deadline":
                raise BudgetExceeded("admission generation reached work deadline; raw tokens retained")
            deadline.check()
            # A formatting failure is not an OOM/context failure. If no legal
            # full answer was emitted, use a plainly labeled, source-independent
            # maximum legal grid only to measure forward memory/time. It is not
            # a prediction, candidate, or capability observation.
            calibration_answer = row["token_ids"] if row["valid"] else contract.answer_ids([[0] * 30 for _ in range(30)])
            source = "full-generated-answer-cost-calibration" if row["valid"] else "synthetic-30x30-zero-grid-cost-only"
            score_started = deadline.clock()
            try:
                scored = _score_record(backend, prompt, calibration_answer, deadline)
                scored.update({"status": "complete", "query_id": query["query_id"], "view": view,
                               "source": source, "length_class": label})
            except Exception as exc:
                failed_score = {
                    "status": "failed", "query_id": query["query_id"], "view": view,
                    "source": source, "length_class": label, "memory": _failure_memory(backend),
                    "seconds": deadline.clock() - score_started,
                    "error": f"{type(exc).__name__}: {exc}"}
                row["scoring_receipt"] = failed_score
                artifacts.write(f"receipts/admission-{label}-scoring.json", failed_score)
                raise
            artifacts.write(f"receipts/admission-{label}-scoring.json", scored)
            row["scoring_receipt"] = scored
            score_costs.append(scored)
            result["timings"]["admission_scoring_seconds"] += scored["seconds"]
        estimate = _projection(queries, generation_costs, score_costs, deadline, "after_admission")
        result["projections"].append(estimate)
        artifacts.write("receipts/projection-0000.json", estimate)
        if not estimate["generation_fits"]:
            result["status"] = "budget_declined"
            result["errors"].append("measured completed-EOS calibration does not admit full generation within remaining budget and closure reserve")
            return _result(result, deadline, artifacts)
        result["planned_budget_mode"] = "paired" if estimate["fits"] else "vote-first-rescoring-conditional"
        result["phase"] = "panel_generation"
        for query_index, query in enumerate(queries):
            for view in VIEWS:
                deadline.check()
                row = {"query_id": query["query_id"], "view": view}
                operation_started = deadline.clock()
                try:
                    row.update(_generation_record(backend, query["_prompts"][view], deadline))
                    row["status"] = "complete"
                    row["canonical_grid"] = contract.inverse(row["grid"], view) if row["valid"] else None
                except Exception as exc:
                    row.update({"status": "failed", "valid": False, "token_ids": None,
                                "memory": _failure_memory(backend),
                                "seconds": deadline.clock() - operation_started, "error": f"{type(exc).__name__}: {exc}"})
                    query["views"][view] = row
                    artifacts.write(f"receipts/view-{query_index:04d}-{view}.json", row)
                    _rank(query)
                    raise
                query["views"][view] = row
                artifacts.write(f"receipts/view-{query_index:04d}-{view}.json", row)
                generation_costs.append(row)
                result["timings"]["panel_generation_seconds"] += row["seconds"]
                _rank(query)
                if row["termination"] == "deadline":
                    raise BudgetExceeded("generation stopped at work deadline; raw partial tokens retained")
                estimate = _projection(queries, generation_costs, score_costs, deadline, "panel_generation")
                result["projections"].append(estimate)
                artifacts.write(f"receipts/projection-{len(result['projections']) - 1:04d}.json", estimate)
                if not estimate["generation_fits"]:
                    raise BudgetExceeded("updated completed-EOS generation projection exceeds work budget")
        # Complete A on the common pool before B. If B fails, A is preserved.
        result["phase"] = "panel_rescoring"
        if not estimate["fits"]:
            raise BudgetExceeded("vote-only result retained: observed full-candidate rescoring projection does not fit")
        for query_index, query in enumerate(queries):
            for candidate_index, candidate in enumerate(query["candidates"]):
                for view in VIEWS:
                    deadline.check()
                    answer = contract.answer_ids(contract.transform(candidate["grid"], view))
                    row = {"query_id": query["query_id"], "candidate_index": candidate_index, "view": view}
                    operation_started = deadline.clock()
                    try:
                        row.update(_score_record(backend, query["_prompts"][view], answer, deadline))
                        row["status"] = "complete"
                    except Exception as exc:
                        row.update({"status": "failed", "seconds": deadline.clock() - operation_started,
                                    "memory": _failure_memory(backend),
                                    "error": f"{type(exc).__name__}: {exc}"})
                        candidate["view_nll"][view] = row
                        artifacts.write(f"receipts/nll-{query_index:04d}-{candidate_index}-{view}.json", row)
                        raise
                    candidate["view_nll"][view] = row
                    artifacts.write(f"receipts/nll-{query_index:04d}-{candidate_index}-{view}.json", row)
                    score_costs.append(row)
                    result["timings"]["panel_rescoring_seconds"] += row["seconds"]
                    estimate = _projection(queries, generation_costs, score_costs, deadline, "panel_rescoring")
                    result["projections"].append(estimate)
                    artifacts.write(f"receipts/projection-{len(result['projections']) - 1:04d}.json", estimate)
                    if not estimate["fits"]:
                        raise BudgetExceeded("updated rescoring projection exceeds work budget")
                candidate["mean_nll"] = sum(item["nll"] for item in candidate["view_nll"]) / 8.0
                candidate["combined_score"] = candidate["count"] - candidate["mean_nll"]
            # Empty pools remain empty, never an arbitrary fallback prediction.
            query["rescored"] = [candidate["grid"] for candidate in sorted(
                query["candidates"], key=lambda item: (-item["combined_score"], item["canonical_key"]))[:2]]
            query["rescoring_complete"] = True
            query["status"] = "complete"
        result["phase"] = "closure"
        result["status"] = "complete"
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        if result["phase"] == "context_admission":
            result["status"] = "context_admission_failed"
        elif isinstance(exc, BudgetExceeded):
            result["status"] = "partial_budget"
        else:
            result["status"] = "partial_failure"
    return _result(result, deadline, artifacts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--budget-seconds", required=True, type=float)
    args = parser.parse_args(argv)
    deadline = Deadline(args.budget_seconds)
    artifacts = Artifacts(args.output)
    # Files are public and verified by the controller before launch. No network
    # materialization, raw ARC directory, evaluator file, or gold flag is accepted.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        with Path(args.plan).open("r", encoding="utf-8") as stream:
            plan = json.load(stream)
        validate_plan(plan)
        artifacts.write("started.json", {"schema": SCHEMA, "budget": deadline.receipt(),
                                        "plan_sha256": hashlib.sha256(Path(args.plan).read_bytes()).hexdigest()})
        backend = TransformersBackend(args.model_dir, plan, deadline, artifacts)
    except Exception as exc:
        artifacts.write("result.json", {"schema": SCHEMA, "status": "load_failed",
            "phase": "load", "queries": [], "full_panel_complete": False,
            "capability_claim": False, "budget": deadline.receipt(),
            "errors": [f"{type(exc).__name__}: {exc}"]})
        return 2
    result = run(plan, backend, args.output, args.budget_seconds,
                 deadline=deadline, artifacts=artifacts)
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
