"""Bounded, no-update real-Qwen probability-path diagnostic.

One genuine full-vocabulary sampled microbatch is traced. Forced cached replay
then reproduces its exact shapes, masks, positions and post-EOS filler; singleton
full train-mode replay uses the existing completion_logps path. Neither replay
replaces behavior probabilities. Cached provenance alone is NOT train-policy
parity, and this diagnostic never grants permission to train. Caller admission,
full-policy identity/restoration, and the independent full-pool gate still apply.

No model/data loader, optimizer, evaluator, provider or persistence is here.
Expected failures return partial evidence and charged attempted work. Interrupts
propagate with probability_probe_result attached, never as successful results.
"""
from __future__ import annotations

from collections import Counter
import copy
import importlib.metadata
import math
import time

import torch

from tools.arc2_goal_sprint_20261017.model import PhaseDeadline, check_deadline
from .engine import CompactEngine
from .probability_trace import (EOS_ID, MAX_CONTEXT, MAX_GENERATION, PAD_ID, MAX_BATCH,
                               _sha, validate_trace, validate_rows as _validate_rows)
from .precision import active_head, validate_policy
from .precision_contract import FP32_HEAD_POLICY

FORMAT = "irisx/nvarc-probability-probe-v1"
_COUNTERS = ("forward_calls", "sampled_tokens", "optimizer_steps", "optimizer_attempts",
             "generation_forward_attempts", "generation_input_tokens", "generation_row_token_slots",
             "generation_finished_row_token_slots", "generation_padding_tokens")


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _error(error):
    return {"type": type(error).__name__, "message": str(error)[:1024]}


def _work():
    return {"forward_attempts": 0, "forward_successes": 0, "input_tokens": 0,
            "row_token_slots": 0, "finished_row_token_slots": 0, "padding_tokens": 0,
            "selected_tokens": 0, "wall_seconds": 0.0}


class _HeadEvidence:
    """Observe actual 16-way logits and two same-hidden projection controls.

    These extra tiny GEMMs are diagnostic work, never behavior substitutions.
    No hidden vectors or graph are retained; model/backbone is not rerun here.
    """
    def __init__(self, engine, result):
        self.engine, self.result, self.calls = engine, result, 0
        self.handle = active_head(engine.model).register_forward_hook(self._capture)

    def _capture(self, module, args, output):
        _need(self.calls < 2 * MAX_GENERATION + 3 * MAX_BATCH, "bounded head diagnostic calls required")
        inputs = args[0]
        _need(output.ndim == 3 and output.shape[-1] == 16
              and output.numel() <= MAX_BATCH * MAX_GENERATION * 16,
              "bounded selected full16 logits required")
        enabled = torch.is_grad_enabled()
        item = {'call': self.calls, 'stage': self.result['stage'],
            'input_shape': list(inputs.shape), 'input_dtype': str(inputs.dtype),
            'actual_dtype': str(output.dtype), 'grad_enabled': enabled,
            'head_training': bool(module.training), 'actual_requires_grad': bool(output.requires_grad),
            'actual_logits': output.detach().float().cpu().tolist(),
            'fp32_same_hidden_logits': None, 'legacy_same_hidden_logits': None,
            'extra_projection_calls': 0, 'projection_attempts': 0,
            'projection_successes': 0, 'error': None}
        self.result['logit_evidence'].append(item)
        self.calls += 1
        try:
            _need(bool(torch.isfinite(output).all()), 'finite actual diagnostic logits required')
            for label in ('fp32_same_hidden_logits', 'legacy_same_hidden_logits'):
                item['projection_attempts'] += 1
                self.result['extra_projection_attempts'] += 1
                context = torch.autocast(inputs.device.type, enabled=False) if label.startswith('fp32') else self.engine.autocast()
                with torch.no_grad(), context:
                    value = torch.nn.functional.linear(inputs.detach().float() if label.startswith('fp32') else inputs.detach(),
                                                       module.weight.detach(), None)
                item['projection_successes'] += 1
                item['extra_projection_calls'] += 1
                self.result['extra_projection_successes'] += 1
                item[label] = value.float().cpu().tolist()
                _need(bool(torch.isfinite(value).all()), 'finite diagnostic projection logits required')
        except BaseException as error:
            item['error'] = _error(error)
            raise

    def close(self):
        self.handle.remove()


def _additional_full(engine, rows, *, mode, deadline):
    """Actual eval/no-grad or train/grad-enabled forward, never backward/update."""
    result = {'mode': mode, 'status': 'running', 'error': None, 'rows': [],
              'metrics': _metrics([], []), 'work': _work(), 'backward_validated': False}
    start = time.monotonic(); expected_all, values_all = [], []
    try:
        for index, row in enumerate(rows):
            check_deadline(deadline)
            result['work']['forward_attempts'] += 1
            result['work']['input_tokens'] += len(row['input_ids'])
            before = engine.forward_calls
            try:
                if mode == 'train_grad':
                    with torch.enable_grad():
                        values = engine.completion_logps(row['input_ids'], row['prompt_length'])
                        _need(values.requires_grad, 'actual differentiable train forward required')
                        values = values[row['prompt_length']:].detach().float().cpu().tolist()
                else:
                    engine.model.eval()
                    tokens = torch.tensor([row['input_ids']], device=engine.device)
                    positions = torch.arange(row['prompt_length']-1, len(row['input_ids'])-1, device=engine.device)
                    with torch.no_grad(), engine.autocast():
                        output = engine.model(input_ids=tokens, attention_mask=torch.ones_like(tokens),
                                              use_cache=False, logits_to_keep=positions)
                    engine.forward_calls += 1
                    logits = output.logits[0].float()
                    targets = tokens[0, row['prompt_length']:]
                    values = (logits.gather(-1, targets[:, None]).squeeze(-1)
                              - torch.logsumexp(logits, -1)).cpu().tolist()
                    output = logits = tokens = positions = None
            finally:
                result['work']['forward_successes'] += engine.forward_calls - before
            expected = row['behavior_log_probs'][row['prompt_length']:]
            metrics = _metrics(expected, values)
            result['rows'].append({'row_index': index, 'completion_ids': row['completion_ids'][:],
                'behavior_log_probs': expected[:], 'full_log_probs': values, 'metrics': metrics})
            expected_all.extend(expected); values_all.extend(values)
            result['metrics'] = _metrics(expected_all, values_all)
            result['work']['row_token_slots'] += len(values)
            result['work']['selected_tokens'] += len(values)
            _need(result['metrics']['ratios_finite'] is True, 'finite additional replay ratios required')
            check_deadline(deadline)
        result['status'] = 'completed'
    except BaseException as error:
        result['status'] = 'deadline' if isinstance(error, PhaseDeadline) else 'failed'
        result['error'] = _error(error)
        if not isinstance(error, Exception):
            error.additional_probability_result = result
            raise
    finally:
        result['work']['wall_seconds'] = time.monotonic()-start
    return result


def _metrics(behavior, replay):
    result = {"tokens": 0, "max_abs_logp_gap": None, "mean_abs_logp_gap": None,
              "log_ratio_min": None, "log_ratio_max": None, "importance_ratio_min": None,
              "importance_ratio_max": None, "importance_ratio_mean": None,
              "ratio_below_0_8": None, "ratio_above_1_2": None,
              "ratios_finite": None, "ratio_error": None}
    if not behavior:
        return result
    _need(len(behavior) == len(replay), "probability vector lengths differ")
    gaps = [b - a for a, b in zip(behavior, replay)]
    _need(all(math.isfinite(v) for v in gaps), "finite probability gaps required")
    result.update(tokens=len(gaps), max_abs_logp_gap=max(map(abs, gaps)),
                  mean_abs_logp_gap=math.fsum(abs(v) / len(gaps) for v in gaps),
                  log_ratio_min=min(gaps), log_ratio_max=max(gaps))
    # Preserve measured gaps even when exponentiation is not representable.
    # A caller records this result, then fails the stage rather than emitting
    # JSON infinity or losing the raw selected-probability evidence.
    try:
        ratios = [math.exp(v) for v in gaps]
    except OverflowError:
        result.update(ratios_finite=False, ratio_error="importance ratio exponentiation overflow")
        return result
    result.update(importance_ratio_min=min(ratios), importance_ratio_max=max(ratios),
                  importance_ratio_mean=math.fsum(r / len(ratios) for r in ratios),
                  ratio_below_0_8=sum(r < 0.8 for r in ratios), ratio_above_1_2=sum(r > 1.2 for r in ratios),
                  ratios_finite=True)
    return result


def _modes(model):
    return [(module, module.training) for module in model.modules()]


def _restore_modes(modes):
    # Calling model.train(previous) would erase deliberately mixed child modes.
    for module, mode in modes:
        module.training = mode


def _context(engine):
    versions = {}
    for name in ("torch", "transformers", "peft"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    cuda = engine.device.type == "cuda"
    return {"versions": versions, "device": str(engine.device), "base_dtype": str(engine.base_dtype),
            "parameter_dtypes": dict(Counter(str(p.dtype) for p in engine.model.parameters())),
            "model_class": type(engine.model.get_base_model()).__name__,
            "model_config": copy.deepcopy(engine.model.config.to_dict()),
            "model_contract": copy.deepcopy(engine.contract), "base_identity": copy.deepcopy(engine.base_identity),
            "probability_policy": engine.probability_policy,
            "output_head_contract": validate_policy(engine.model, engine.probability_policy),
            "attention_implementation": getattr(engine.model.config, "_attn_implementation", None),
            "gradient_checkpointing": bool(engine.model.is_gradient_checkpointing),
            "entry_model_training": bool(engine.model.training),
            "entry_module_training_counts": dict(Counter(str(m.training) for m in engine.model.modules())),
            "autocast": f"{engine.device.type}_bfloat16" if engine.base_dtype == torch.bfloat16 else "none",
            "cuda_version": torch.version.cuda,
            "paths": {"generation": {"mode": "eval", "grad_enabled": False, "cached": True},
                      "cached_replay": {"mode": "eval", "grad_enabled": False, "cached": True},
                      "full_replay": {"mode": "train", "grad_enabled": False, "cached": False}},
            "gpu_name": torch.cuda.get_device_name(engine.device) if cuda else None,
            "cudnn_version": torch.backends.cudnn.version() if cuda else None,
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "float32_matmul_precision": torch.get_float32_matmul_precision(),
            "cuda_matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
            "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
            "sdpa_backends": {"flash": torch.backends.cuda.flash_sdp_enabled(),
                              "memory_efficient": torch.backends.cuda.mem_efficient_sdp_enabled(),
                              "math": torch.backends.cuda.math_sdp_enabled()}}


def _admit_engine(engine):
    from transformers import Qwen3ForCausalLM
    _need(type(engine) is CompactEngine and type(engine.model.get_base_model()) is Qwen3ForCausalLM,
          "actual admitted CompactEngine with Qwen3ForCausalLM required")
    engine._checkpoint_admission()


@torch.no_grad()
def replay_trace(engine, trace, *, expected_trace_sha256, deadline):
    """Force all original selections, including discarded filler; never sample.

    Returns status='deadline' or 'failed' with charged partial results on failure.
    Interrupts propagate with probability_probe_result attached. Input traces
    are read-only and must have an independently retained seal.
    """
    result = {"status": "running", "error": None, "steps": [], "metrics": _metrics([], []), "work": _work()}
    started = time.monotonic()
    modes = _modes(engine.model)
    cache = output = tokens = attention = positions = None
    behavior, replay = [], []
    try:
        _admit_engine(engine)
        _need(type(deadline) in (int, float) and math.isfinite(deadline), "finite absolute deadline required")
        validate_trace(trace, expected_trace_sha256=expected_trace_sha256)
        check_deadline(deadline)
        engine.model.eval()
        prompts, lengths = trace["prompts"], trace["prompt_lengths"]
        count, width = trace["batch_size"], trace["padding_width"]
        tokens = torch.tensor([[PAD_ID] * (width - len(p)) + p for p in prompts], device=engine.device)
        attention = torch.tensor([[0] * (width - len(p)) + [1] * len(p) for p in prompts], device=engine.device)
        positions = (attention.cumsum(-1) - 1).clamp(min=0)
        for step, row in enumerate(trace["steps"]):
            check_deadline(deadline)
            work = result["work"]
            work["forward_attempts"] += 1
            work["input_tokens"] += tokens.numel()
            work["row_token_slots"] += count
            work["finished_row_token_slots"] += sum(not v for v in row["retained"])
            if step == 0:
                work["padding_tokens"] += count * width - sum(lengths)
            with engine.autocast():
                output = engine.model(input_ids=tokens, attention_mask=attention, position_ids=positions,
                                      past_key_values=cache, use_cache=True, logits_to_keep=1)
            engine.forward_calls += 1
            work["forward_successes"] += 1
            cache = output.past_key_values
            logits = output.logits[:, -1, :].float()
            _need(logits.shape == (count, 16) and bool(torch.isfinite(logits).all()), "finite cached full16 logits required")
            selected = torch.tensor(row["selected_ids"], device=engine.device)[:, None]
            logps = (logits.gather(1, selected).squeeze(1) - torch.logsumexp(logits, -1)).tolist()
            result["steps"].append({"step": step, "selected_ids": row["selected_ids"][:],
                "behavior_log_probs": row["selected_log_probs"][:], "cached_log_probs": logps,
                "retained": row["retained"][:]})
            work["selected_tokens"] += count
            behavior.extend(row["selected_log_probs"]); replay.extend(logps)
            result["metrics"] = _metrics(behavior, replay)
            if result["metrics"]["ratios_finite"] is False:
                raise FloatingPointError(result["metrics"]["ratio_error"])
            check_deadline(deadline)
            tokens = selected
            attention = torch.cat((attention, attention.new_ones((count, 1))), dim=1)
            positions = torch.tensor([[length + step] for length in lengths], device=engine.device)
        result["status"] = "completed"
    except BaseException as error:
        result["status"], result["error"] = ("deadline" if isinstance(error, PhaseDeadline) else "failed"), _error(error)
        if not isinstance(error, Exception):
            error.probability_probe_result = result
            raise
    finally:
        _restore_modes(modes)
        result["work"]["wall_seconds"] = time.monotonic() - started
        cache = output = tokens = attention = positions = None
    return result


@torch.no_grad()
def probe(engine, prompt_ids, *, count=2, max_new_tokens=MAX_GENERATION, deadline, seed=0):
    """Run one bounded sampled diagnostic without changing model, grads or RNG.

    count is 1..8 and max_new_tokens is 1..931. The caller owns the finite wall
    deadline and frozen-policy byte checks. The private generation RNG is left
    untouched by using a separate generator. No optimizer is created or called.
    All original module modes are restored, including mixed train/eval modes.
    """
    result = {"format": FORMAT, "status": "running", "stage": "admission", "error": None,
              "training_authorized": False, "seed": seed if type(seed) is int else None,
              "requested_count": count if type(count) is int else None,
              "max_new_tokens": max_new_tokens if type(max_new_tokens) is int else None,
              "deadline": deadline if type(deadline) in (int, float) and math.isfinite(deadline) else None,
              "context": None,
              "trace": {}, "rows": [], "cached_replay": None, "full_replay": [],
              "cached_max_abs_logp_gap": None, "full_max_abs_logp_gap": None,
              "additional_replays": {}, "logit_evidence": [], "extra_projection_calls": 0,
              "extra_projection_attempts": 0, "extra_projection_successes": 0,
              "full_metrics": _metrics([], []),
              "work": {"generation": _work(), "cached_replay": _work(), "full_replay": _work(),
                       "total": _work()}, "engine_counter_deltas": {key: 0 for key in _COUNTERS}}
    started = time.monotonic()
    modes = _modes(engine.model)
    before = {key: getattr(engine, key) for key in _COUNTERS}
    # No global RNG should be consumed by admitted dropout-zero forwards, but
    # fork_rng additionally guarantees process RNG restoration on failed paths.
    devices = [engine.device.index] if engine.device.type == "cuda" else []
    private_rng = engine.generator.get_state().clone()
    head_evidence = None
    behavior, full = [], []
    try:
        _admit_engine(engine)
        _need(type(count) is int and 1 <= count <= MAX_BATCH, "probe count must be in 1..8")
        _need(type(max_new_tokens) is int and 1 <= max_new_tokens <= MAX_GENERATION, "probe generation bound required")
        _need(type(seed) is int and 0 <= seed < 2**63, "bounded probe seed required")
        _need(type(deadline) in (int, float) and math.isfinite(deadline), "finite absolute deadline required")
        engine._tokens(prompt_ids)
        _need(len(prompt_ids) + max_new_tokens <= MAX_CONTEXT, "probe context reservation exceeds bound")
        check_deadline(deadline)
        result["context"] = _context(engine)
        # Optional only for the distinct repaired policy, leaving historical
        # legacy probe work and numerical execution unchanged.
        if engine.probability_policy == FP32_HEAD_POLICY:
            head_evidence = _HeadEvidence(engine, result)
        with torch.random.fork_rng(devices=devices):
            generator = torch.Generator(device=engine.device).manual_seed(seed)
            result["stage"] = "generation"
            stage_started = time.monotonic()
            try:
                result["rows"] = engine.generate(prompt_ids, count=count, max_new_tokens=max_new_tokens,
                    sample=True, deadline=deadline, generator=generator, trace=result["trace"])
            finally:
                work = result["work"]["generation"]
                work.update(forward_attempts=engine.generation_forward_attempts - before["generation_forward_attempts"],
                    forward_successes=engine.forward_calls - before["forward_calls"],
                    input_tokens=engine.generation_input_tokens - before["generation_input_tokens"],
                    row_token_slots=engine.generation_row_token_slots - before["generation_row_token_slots"],
                    finished_row_token_slots=engine.generation_finished_row_token_slots - before["generation_finished_row_token_slots"],
                    padding_tokens=engine.generation_padding_tokens - before["generation_padding_tokens"],
                    selected_tokens=count * len(result["trace"].get("steps", [])),
                    wall_seconds=time.monotonic() - stage_started)
            validate_trace(result["trace"], expected_trace_sha256=result["trace"]["sha256"])
            _validate_rows(result["rows"], result["trace"])
            result["stage"] = "cached_replay"
            try:
                cached = replay_trace(engine, result["trace"], expected_trace_sha256=result["trace"]["sha256"], deadline=deadline)
            except BaseException as error:
                cached = getattr(error, "probability_probe_result", None)
                if cached is not None:
                    result["cached_replay"] = cached
                    result["work"]["cached_replay"] = cached["work"]
                    result["cached_max_abs_logp_gap"] = cached["metrics"]["max_abs_logp_gap"]
                raise
            result["cached_replay"] = cached
            result["work"]["cached_replay"] = cached["work"]
            result["cached_max_abs_logp_gap"] = cached["metrics"]["max_abs_logp_gap"]
            if cached["status"] != "completed":
                result["error"] = cached["error"]
                if cached["status"] == "deadline":
                    raise PhaseDeadline("cached replay deadline; see cached_replay.error and partial trace")
                raise RuntimeError("cached replay failed; see cached_replay.error and partial trace")
            result["stage"] = "full_replay"
            stage_started = time.monotonic()
            try:
                for index, row in enumerate(result["rows"]):
                    check_deadline(deadline)
                    work = result["work"]["full_replay"]
                    work["forward_attempts"] += 1
                    work["input_tokens"] += len(row["input_ids"])
                    work["row_token_slots"] += row["completion_tokens"]
                    forward_before = engine.forward_calls
                    try:
                        values = engine.completion_logps(row["input_ids"], row["prompt_length"])
                    finally:
                        work["forward_successes"] += engine.forward_calls - forward_before
                    values = values[row["prompt_length"]:].tolist()
                    expected = row["behavior_log_probs"][row["prompt_length"]:]
                    detail = {"row_index": index, "completion_ids": row["completion_ids"][:],
                              "behavior_log_probs": expected, "full_log_probs": values, "metrics": None}
                    result["full_replay"].append(detail)
                    work["selected_tokens"] += len(values)
                    detail["metrics"] = _metrics(expected, values)
                    behavior.extend(expected); full.extend(values)
                    result["full_metrics"] = _metrics(behavior, full)
                    result["full_max_abs_logp_gap"] = result["full_metrics"]["max_abs_logp_gap"]
                    if result["full_metrics"]["ratios_finite"] is False:
                        raise FloatingPointError(result["full_metrics"]["ratio_error"])
                    check_deadline(deadline)
            finally:
                result["work"]["full_replay"]["wall_seconds"] = time.monotonic() - stage_started
            if engine.probability_policy == FP32_HEAD_POLICY:
                for mode in ('eval_nograd', 'train_grad'):
                    stage = 'full_' + mode
                    result['stage'] = stage
                    extra = None
                    try:
                        extra = _additional_full(engine, result['rows'], mode=mode, deadline=deadline)
                    except BaseException as error:
                        extra = getattr(error, 'additional_probability_result', None)
                        raise
                    finally:
                        if extra is not None:
                            result['additional_replays'][mode] = extra
                            result['work'][stage] = extra['work']
                    if extra['status'] == 'deadline':
                        raise PhaseDeadline('additional full replay deadline')
                    _need(extra['status'] == 'completed', 'additional full replay failed')
            result["stage"], result["status"] = "completed", "completed"
            if engine.probability_policy == FP32_HEAD_POLICY:
                from .precision_contract import stable_probe_admission
                # Schema/provenance failures also retain all diagnostic vectors.
                # A numerical gap alone is returned for the caller's strict gate.
                result['extra_projection_calls'] = sum(r['extra_projection_calls'] for r in result['logit_evidence'])
                stable_probe_admission(result, tolerance=0.05 if engine.base_dtype == torch.bfloat16 else 1e-5,
                                       count=count)
    except BaseException as error:
        result["status"] = "deadline" if isinstance(error, PhaseDeadline) else "failed"
        if result["error"] is None:
            result["error"] = _error(error)
        if not isinstance(error, Exception):
            error.probability_probe_result = result
            raise
    finally:
        if head_evidence is not None:
            head_evidence.close()
        result['extra_projection_calls'] = sum(r['extra_projection_calls'] for r in result['logit_evidence'])
        _restore_modes(modes)
        engine.generator.set_state(private_rng)
        result["engine_counter_deltas"] = {key: getattr(engine, key) - before[key] for key in _COUNTERS}
        for key in result["work"]["total"]:
            result["work"]["total"][key] = sum(result["work"][stage][key]
                for stage in result['work'] if stage != 'total')
        result["work"]["total"]["wall_seconds"] = time.monotonic() - started
    return result
