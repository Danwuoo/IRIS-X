"""Default-inert, bounded FP8 microprobe. Never downloads/installs model material.

An explicitly enabled future run compares the installed NVIDIA Transformer
Engine Linear BF16 route against its supported per-tensor FP8 route. It does
not admit full-model/LoRA training, inference, FP8 KV, W8A16 or W4A16. Baseline,
calibration and FP8 timings have distinct labels. No BF16 fallback counts as FP8.

API references checked 2026-10-11 (installed versions are checked separately):
https://nvidia.github.io/TransformerEngine/support_matrix.html
https://nvidia.github.io/TransformerEngine/api/pytorch.html
https://nvidia.github.io/TransformerEngine/api/common.html
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import gc
import importlib.metadata
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any


@dataclass(frozen=True)
class ProbeConfig:
    enable_gpu_probe: bool = False
    scope: str = "linear_microprobe"
    recipe: str = "auto_per_tensor"
    rows: int = 32
    in_features: int = 64
    out_features: int = 64
    steps: int = 2
    calibration_steps: int = 2
    timeout_seconds: float = 60.0
    device: int = 0
    seed: int = 20261011
    max_relative_l2_error: float = 0.20
    max_relative_loss_error: float = 0.10

    def validate(self) -> None:
        if type(self.enable_gpu_probe) is not bool:
            raise ValueError("enable_gpu_probe must be a bool")
        for name in ("rows", "in_features", "out_features"):
            value = getattr(self, name)
            if type(value) is not int or not 16 <= value <= 512 or value % 16:
                raise ValueError(name + " must be a multiple of 16 in [16, 512]")
        for name in ("steps", "calibration_steps"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 4:
                raise ValueError(name + " must be in [1, 4]")
        if type(self.device) is not int or not 0 <= self.device <= 15:
            raise ValueError("device must be in [0, 15]")
        if type(self.seed) is not int or not 0 <= self.seed < 2**31:
            raise ValueError("seed must be a nonnegative 31-bit integer")
        for name, upper in (("timeout_seconds", 120), ("max_relative_l2_error", 1),
                            ("max_relative_loss_error", 1)):
            value = getattr(self, name)
            if type(value) not in (int, float) or not 0 < value <= upper or not math.isfinite(value):
                raise ValueError(name + " is out of bounds")


def dependency_versions() -> dict[str, str | None]:
    """Distribution metadata only: no torch/TE import and no CUDA access."""
    result = {}
    for package in ("torch", "transformer-engine", "transformer-engine-torch", "nvidia-cublas-cu12"):
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = None
    return result


def _result(config: ProbeConfig, status: str, reason: str, **extra: Any) -> dict[str, Any]:
    # fp8_executed attests a completed verified arm. On ERROR/OOM/TIMEOUT it
    # does not establish that zero FP8 kernels ran before interruption.
    return {"format": "irisx/precision-microprobe-v1", "status": status, "reason": reason,
            "config": asdict(config), "whole_model_admitted": False,
            "deployment_admitted": False, "fp8_executed": False,
            "fallback_used": False, "measurements": {}, **extra}


def _gate(config: ProbeConfig) -> dict[str, Any] | None:
    config.validate()
    if config.scope != "linear_microprobe":
        return _result(config, "REFUSED", "Whole-model/LoRA training routes are not validated by this microprobe")
    if config.recipe not in ("auto_per_tensor", "per_tensor_delayed", "per_tensor_current"):
        return _result(config, "UNSUPPORTED", "Only per-tensor FP8 is implemented; no MXFP8/block-scale substitution")
    if not config.enable_gpu_probe:
        return _result(config, "NOT_RUN", "GPU probe disabled; no CUDA import, discovery or execution")
    return None


def run_probe(config: ProbeConfig | None = None) -> dict[str, Any]:
    """Explicit opt-in only; kill the isolated process on the hard timeout."""
    config = config or ProbeConfig()
    gate = _gate(config)
    if gate is not None:
        return gate
    return _bounded_subprocess(config)


def _bounded_subprocess(config: ProbeConfig, command: list[str] | None = None) -> dict[str, Any]:
    """Accept no outcome without pidfd-bound closure of the entire owned tree.

    The work timeout is followed by at most five seconds of guarded shutdown;
    the guard also has a five-second bounded pre-execution launch handshake.
    A valid child receipt never substitutes for verified descendant closure.
    """
    from tools.arc_learning_agent_20261011 import process_guard as pg

    config.validate()
    try:
        pg._require_linux()
    except RuntimeError as error:
        return _result(config, "UNSUPPORTED", str(error),
                       cleanup={"owned_tree_closed": False, "process_started": False})
    command = command or [sys.executable, "-m", "tools.arc_learning_agent_20261011.precision_probe",
                          "--_child", json.dumps(asdict(config), allow_nan=False)]
    root = str(Path(__file__).resolve().parents[2])
    started = time.monotonic()
    deadline = started + config.timeout_seconds
    guard = None
    proof = None
    timed_out = False
    execution_error = None
    closure_error = None
    with tempfile.TemporaryDirectory(prefix="precision-probe-") as tmp:
        with open(Path(tmp) / "stdout", "wb") as stdout, open(Path(tmp) / "stderr", "wb") as stderr:
            try:
                guard = pg.OwnedProcessGuard.spawn(
                    command, evidence_dir=Path(tmp) / "owned-tree", cwd=root,
                    stdout=stdout, stderr=stderr)
                while guard.poll() is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        break
                    time.sleep(min(0.01, remaining))
            except Exception as error:
                execution_error = type(error).__name__ + ": " + str(error)[:600]
            finally:
                if guard is not None:
                    try:
                        try:
                            proof = guard.closed_proof()
                        except Exception:
                            # A snapshot/read failure must not skip teardown.
                            proof = None
                        if not proof or not proof.get("closed"):
                            proof = guard.stop(timeout=5)
                        pg.verify_closed_proof(proof)
                    except Exception as error:
                        closure_error = type(error).__name__ + ": " + str(error)[:600]
                else:
                    closure_error = "No independently verifiable launch/closure proof"
        elapsed = time.monotonic() - started
        cleanup = {
            "owned_tree_closed": closure_error is None,
            "process_reaped": bool(proof and proof.get("returncode") is not None),
            "closure_proof": proof,
            "cleanup_timeout_seconds": 5,
            "launch_handshake_timeout_seconds": 5,
        }

        def finish(result: dict[str, Any]) -> dict[str, Any]:
            result["elapsed_wall_seconds"] = elapsed
            result["cleanup"] = {**result.get("cleanup", {}), **cleanup}
            return result

        if closure_error is not None:
            return finish(_result(config, "LIFECYCLE_FAILURE", closure_error,
                                  execution_error=execution_error))
        if execution_error is not None:
            return finish(_result(config, "ERROR", execution_error))
        if timed_out:
            return finish(_result(config, "TIMEOUT", "Work deadline expired; complete owned tree stopped and reaped"))
        # Supervisor nonzero/forced closure includes a worker which exits zero
        # while leaving descendants behind. Preserve that operational failure.
        if proof["returncode"] != 0 or proof["worker_returncode"] != 0 or proof["forced"]:
            return finish(_result(config, "ERROR", "Probe exit required forced closure or returned nonzero",
                                  returncode=proof["returncode"],
                                  worker_returncode=proof["worker_returncode"]))
        output = Path(tmp) / "stdout"
        if output.stat().st_size > 1_048_576:
            return finish(_result(config, "ERROR", "Probe output exceeded the bounded receipt size"))
        lines = output.read_text(errors="replace").splitlines()
        receipts = [line[len("PRECISION_PROBE_RESULT="):] for line in lines
                    if line.startswith("PRECISION_PROBE_RESULT=")]
        try:
            if len(receipts) != 1:
                raise ValueError("missing or repeated receipt")
            def reject_constant(value):
                raise ValueError("nonfinite JSON constant: " + value)
            result = json.loads(receipts[0], parse_constant=reject_constant)
            _validate_child_receipt(result, config)
            return finish(result)
        except (ValueError, TypeError, AttributeError, RecursionError, OverflowError):
            return finish(_result(config, "ERROR", "Invalid bounded probe receipt"))


def _validate_child_receipt(result: Any, config: ProbeConfig) -> None:
    """Reject impossible precision/admission claims before accepting IPC data."""
    required = {"format", "status", "reason", "config", "whole_model_admitted",
                "deployment_admitted", "fp8_executed", "fallback_used", "measurements"}
    statuses = {"NOT_RUN", "UNSUPPORTED", "ERROR", "OOM", "NUMERICAL_FAILURE", "MEASURED_MICROPROBE_PASS"}
    if (not isinstance(result, dict) or not required <= set(result)
            or set(result) - required - {"runtime", "comparison", "cleanup"}
            or result["format"] != "irisx/precision-microprobe-v1"
            or result["status"] not in statuses or not isinstance(result["reason"], str)
            or result["whole_model_admitted"] is not False
            or result["deployment_admitted"] is not False
            or type(result["fp8_executed"]) is not bool
            or type(result["fallback_used"]) is not bool
            or not isinstance(result["measurements"], dict)):
        raise ValueError("invalid precision receipt schema/admission claims")
    if json.dumps(result["config"], sort_keys=True, allow_nan=False) != json.dumps(asdict(config), sort_keys=True, allow_nan=False):
        raise ValueError("receipt does not match requested configuration")
    # Includes metadata, not just the measured fields; JSON floats such as
    # 1e400 also parse to infinity even when parse_constant rejects NaN.
    def finite_tree(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite receipt value")
        if isinstance(value, dict):
            for child in value.values():
                finite_tree(child)
        elif isinstance(value, list):
            for child in value:
                finite_tree(child)
    finite_tree(result)

    def number(value, *, integer=False):
        if (type(value) not in ((int,) if integer else (int, float)) or value < 0
                or (type(value) is int and value > 2**63 - 1) or not math.isfinite(value)):
            raise ValueError("invalid finite nonnegative measurement")

    measurements = result["measurements"]
    if set(measurements) - {"bf16", "fp8"}:
        raise ValueError("unknown measurement arm")
    for precision, arm in measurements.items():
        fields = {"measurement_label", "fp8_executed", "fallback_used", "steps", "finite", "loss",
                  "elapsed_seconds", "calibration", "peak_allocated_bytes", "peak_reserved_bytes", "memory_scope"}
        if not isinstance(arm, dict) or set(arm) != fields:
            raise ValueError("incomplete forward/backward arm")
        fallback_arm = (precision == "fp8" and result["status"] == "UNSUPPORTED"
                        and result["fallback_used"] is True and result["fp8_executed"] is False
                        and arm["measurement_label"] == "BF16_FALLBACK")
        label = ("BF16_FALLBACK" if fallback_arm else
                 "TE_PER_TENSOR_FP8_FWD_BWD" if precision == "fp8" else "TE_BF16_FWD_BWD")
        if (arm["measurement_label"] != label or arm["fp8_executed"] is not (precision == "fp8" and not fallback_arm)
                or arm["fallback_used"] is not fallback_arm or type(arm["finite"]) is not bool
                or type(arm["steps"]) is not int or arm["steps"] != config.steps
                or not isinstance(arm["memory_scope"], str)):
            raise ValueError("arm precision or work-count mismatch; no fallback accepted")
        number(arm["elapsed_seconds"])
        number(arm["peak_allocated_bytes"], integer=True)
        number(arm["peak_reserved_bytes"], integer=True)
        if arm["peak_reserved_bytes"] < arm["peak_allocated_bytes"]:
            raise ValueError("inconsistent allocated/reserved peaks")
        if arm["loss"] is None:
            if arm["finite"]:
                raise ValueError("finite arm lacks finite loss")
        else:
            number(arm["loss"])
        calibration = arm["calibration"]
        if not isinstance(calibration, dict) or set(calibration) != {"measurement_label", "steps", "elapsed_seconds", "statistics_collected"}:
            raise ValueError("invalid calibration/warmup receipt")
        number(calibration["elapsed_seconds"])
        if precision == "bf16":
            expected_label, expected_steps, collected = "NOT_APPLICABLE_BF16_REFERENCE", 0, False
        else:
            selected = result.get("runtime", {}).get("recipe")
            if selected not in ("per_tensor_current", "per_tensor_delayed"):
                raise ValueError("missing measured per-tensor recipe")
            current = selected == "per_tensor_current"
            expected_label = ("BF16_WARMUP_CURRENT_SCALING_NO_PERSISTENT_CALIBRATION" if current else
                              "BF16_DELAYED_SCALING_CALIBRATION_NOT_FP8_EXECUTION")
            expected_steps, collected = config.calibration_steps, not current
        if (calibration["measurement_label"] != expected_label
                or type(calibration["steps"]) is not int or calibration["steps"] != expected_steps
                or calibration["statistics_collected"] is not collected):
            raise ValueError("calibration/warmup mislabeled")
    if result["fallback_used"]:
        fallback = measurements.get("fp8", {})
        if (result["status"] != "UNSUPPORTED" or result["fp8_executed"]
                or set(measurements) != {"bf16", "fp8"}
                or fallback.get("measurement_label") != "BF16_FALLBACK"
                or fallback.get("fallback_used") is not True
                or fallback.get("fp8_executed") is not False):
            raise ValueError("fallback is accepted only as an explicit unsupported diagnostic")
    if result["status"] == "NOT_RUN":
        if measurements or result["fp8_executed"] or result["fallback_used"]:
            raise ValueError("NOT_RUN cannot claim measured execution")
    measured = result["status"] in {"MEASURED_MICROPROBE_PASS", "NUMERICAL_FAILURE"}
    if measured:
        if (set(measurements) != {"bf16", "fp8"} or result["fp8_executed"] is not True
                or result["fallback_used"] is not False):
            raise ValueError("measured result requires actual matched BF16 and FP8 arms")
        runtime = result.get("runtime")
        if (not isinstance(runtime, dict) or runtime.get("available") is not True
                or runtime.get("cuda_observed") is not True
                or runtime.get("fp8_runtime_check", {}).get("supported") is not True
                or not isinstance(runtime.get("distributions"), dict)
                or not isinstance(runtime.get("torch"), str)):
            raise ValueError("measured result lacks checked runtime evidence")
        comparison = result.get("comparison")
        if not isinstance(comparison, dict) or set(comparison) != {"errors", "relative_loss_error"}:
            raise ValueError("missing matched comparison")
        errors = comparison["errors"]
        if not isinstance(errors, dict) or set(errors) != {"output", "weight_grad", "input_grad"}:
            raise ValueError("forward/backward comparisons are required")
        for item in errors.values():
            if not isinstance(item, dict) or set(item) != {"finite", "relative_l2", "max_abs"} or type(item["finite"]) is not bool:
                raise ValueError("invalid comparison fields")
            if item["finite"]:
                number(item["relative_l2"])
                number(item["max_abs"])
            elif item["relative_l2"] is not None or item["max_abs"] is not None:
                raise ValueError("nonfinite comparisons must be explicitly unknown")
        loss_error = comparison["relative_loss_error"]
        if loss_error is not None:
            number(loss_error)
        passed = (all(arm["finite"] for arm in measurements.values())
                  and all(item["finite"] and item["relative_l2"] <= config.max_relative_l2_error for item in errors.values())
                  and loss_error is not None and loss_error <= config.max_relative_loss_error)
        if passed != (result["status"] == "MEASURED_MICROPROBE_PASS"):
            raise ValueError("status conflicts with numerical thresholds")


class ProbeUnavailable(RuntimeError):
    """The installed backend cannot perform this precise requested operation."""


class _TorchTEBackend:
    def __init__(self, config: ProbeConfig):
        # This constructor is reachable only after _gate explicitly permits GPU.
        import torch
        self.torch = torch
        self.config = config
        self.te = None
        self.module = None
        self.live = []
        self.runtime = {"distributions": dependency_versions(), "torch": torch.__version__,
                        "torch_cuda": torch.version.cuda, "cuda_observed": False}

    def discover(self) -> dict[str, Any]:
        torch, config = self.torch, self.config
        if not torch.cuda.is_available():
            return {"available": False, "reason": "No CUDA device available", **self.runtime}
        if config.device >= torch.cuda.device_count():
            return {"available": False, "reason": "Requested device absent", **self.runtime}
        torch.cuda.set_device(config.device)
        properties = torch.cuda.get_device_properties(config.device)
        capability = torch.cuda.get_device_capability(config.device)
        self.runtime.update(cuda_observed=True, device_name=properties.name,
                            memory_bytes=properties.total_memory, sm=list(capability))
        if capability not in ((8, 9), (9, 0), (10, 0), (10, 3), (12, 0)):
            raise ProbeUnavailable("Target SM is outside this per-tensor probe's supported set")
        import transformer_engine.pytorch as te
        from transformer_engine.common import recipe
        self.te = te
        check = getattr(te, "is_fp8_available", None)
        if check is None:
            raise ProbeUnavailable("Installed TE lacks the documented FP8 runtime availability API")
        supported, reason = check(return_reason=True)
        self.runtime["fp8_runtime_check"] = {"supported": bool(supported), "reason": str(reason)}
        if not supported:
            raise ProbeUnavailable("Installed TE/runtime rejects per-tensor FP8: " + str(reason))
        selected = config.recipe
        if selected == "auto_per_tensor":
            selected = "per_tensor_current" if capability == (12, 0) else "per_tensor_delayed"
        cls = getattr(recipe, "Float8CurrentScaling" if selected == "per_tensor_current"
                      else "DelayedScaling", None)
        if cls is None:
            raise ProbeUnavailable("Installed TE lacks requested recipe: " + selected)
        self.recipe = cls(fp8_format=recipe.Format.HYBRID)
        self.runtime.update(recipe=selected, recipe_class=type(self.recipe).__name__,
                            forward_operand_format="e4m3", backward_operand_format="e5m2",
                            parameter_dtype="bf16", reduction_dtype="fp32",
                            optimizer="none; no parameter updates")
        if callable(getattr(te, "autocast", None)):
            self.context = lambda enabled, calibrating=False: te.autocast(
                enabled=enabled, calibrating=calibrating, recipe=self.recipe)
            self.runtime["autocast_api"] = "autocast"
        elif callable(getattr(te, "fp8_autocast", None)):
            self.context = lambda enabled, calibrating=False: te.fp8_autocast(
                enabled=enabled, calibrating=calibrating, fp8_recipe=self.recipe)
            self.runtime["autocast_api"] = "fp8_autocast"
        else:
            raise ProbeUnavailable("Installed TE lacks a supported autocast API")
        return {"available": True, **self.runtime}

    def measure(self, precision: str) -> dict[str, Any]:
        torch, te, c = self.torch, self.te, self.config
        torch.manual_seed(c.seed)
        device = "cuda:" + str(c.device)
        # Recreate one module per arm; identical deterministic CPU-generated
        # weights/data, never keep BF16 and FP8 models resident together.
        generator = torch.Generator(device="cpu").manual_seed(c.seed)
        weight = torch.randn(c.out_features, c.in_features, generator=generator) / math.sqrt(c.in_features)
        source = torch.randn(c.rows, c.in_features, generator=generator)
        target = torch.randn(c.rows, c.out_features, generator=generator)
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(c.device)
        self.module = te.Linear(c.in_features, c.out_features, bias=False,
                                params_dtype=torch.bfloat16, device=device)
        with torch.no_grad():
            self.module.weight.copy_(weight.to(device=device, dtype=torch.bfloat16))
        x = source.to(device=device, dtype=torch.bfloat16).requires_grad_(True)
        target = target.to(device=device, dtype=torch.float32)
        self.live = [x, target]
        fp8 = precision == "fp8"
        calibration = {"measurement_label": "NOT_APPLICABLE_BF16_REFERENCE",
                       "steps": 0, "elapsed_seconds": 0.0, "statistics_collected": False}
        if fp8:
            torch.cuda.synchronize(c.device)
            start = time.monotonic()
            for _ in range(c.calibration_steps):
                with torch.no_grad(), self.context(False, calibrating=True):
                    self.module(x)
            torch.cuda.synchronize(c.device)
            current = self.runtime["recipe"] == "per_tensor_current"
            calibration.update(
                measurement_label=("BF16_WARMUP_CURRENT_SCALING_NO_PERSISTENT_CALIBRATION" if current else
                                   "BF16_DELAYED_SCALING_CALIBRATION_NOT_FP8_EXECUTION"),
                statistics_collected=not current, steps=c.calibration_steps,
                elapsed_seconds=time.monotonic() - start)
        torch.cuda.synchronize(c.device)
        start = time.monotonic()
        all_finite = True
        for _ in range(c.steps):
            self.module.zero_grad(set_to_none=True)
            x.grad = None
            with self.context(fp8):
                output = self.module(x)
                loss = (output.float() - target).square().mean()
            loss.backward()
            tensors = (output, loss, self.module.weight.grad, x.grad)
            all_finite = all_finite and all(t is not None and bool(torch.isfinite(t).all().item())
                                           for t in tensors)
        torch.cuda.synchronize(c.device)
        elapsed = time.monotonic() - start
        # Snapshots move to CPU; comparison storage does not inflate GPU peaks.
        snapshots = {"output": output.detach().float().cpu().reshape(-1).tolist(),
                     "weight_grad": self.module.weight.grad.detach().float().cpu().reshape(-1).tolist(),
                     "input_grad": x.grad.detach().float().cpu().reshape(-1).tolist()}
        loss_value = float(loss.item())
        result = {"measurement_label": "TE_PER_TENSOR_FP8_FWD_BWD" if fp8 else "TE_BF16_FWD_BWD",
                  "fp8_executed": fp8, "fallback_used": False, "steps": c.steps,
                  "finite": all_finite, "loss": loss_value if math.isfinite(loss_value) else None,
                  "elapsed_seconds": elapsed, "calibration": calibration,
                  "peak_allocated_bytes": int(torch.cuda.max_memory_allocated(c.device)),
                  "peak_reserved_bytes": int(torch.cuda.max_memory_reserved(c.device)),
                  "memory_scope": "isolated arm incl. module, data, calibration and backward",
                  "snapshots": snapshots}
        return result

    def cleanup(self) -> None:
        if self.module is not None:
            self.module.zero_grad(set_to_none=True)
        self.module = None
        self.live = []
        gc.collect()
        if self.runtime.get("cuda_observed"):
            self.torch.cuda.empty_cache()


def _error_metrics(reference: list[float], actual: list[float]) -> dict[str, Any]:
    if not reference or len(reference) != len(actual):
        raise ValueError("comparison snapshot mismatch")
    if not all(math.isfinite(v) for v in reference + actual):
        return {"finite": False, "relative_l2": None, "max_abs": None}
    delta = [a - r for r, a in zip(reference, actual)]
    return {"finite": True, "relative_l2": math.sqrt(sum(d * d for d in delta)) /
            max(math.sqrt(sum(r * r for r in reference)), 1e-12),
            "max_abs": max(abs(d) for d in delta)}


def _execute_probe(config: ProbeConfig, backend_factory: Any = _TorchTEBackend) -> dict[str, Any]:
    """Child entry; backend injection is only for CPU contract/lifecycle tests."""
    gate = _gate(config)
    if gate is not None:
        return gate
    backend = None
    result = _result(config, "ERROR", "Probe did not complete")
    measurements: dict[str, Any] = {}
    cleanup_calls = 0
    try:
        backend = backend_factory(config)
        runtime = backend.discover()
        result["runtime"] = runtime
        if not runtime.get("available"):
            result.update(status="NOT_RUN", reason=runtime.get("reason", "CUDA unavailable"))
        else:
            arms = {}
            for precision in ("bf16", "fp8"):
                try:
                    arm = backend.measure(precision)
                    arms[precision] = arm.pop("snapshots")
                    measurements[precision] = arm
                finally:
                    backend.cleanup()
                    cleanup_calls += 1
            result["fallback_used"] = measurements["fp8"].get("fallback_used") is True
            if (measurements["fp8"].get("fp8_executed") is not True
                    or measurements["fp8"].get("fallback_used") is not False
                    or measurements["fp8"].get("measurement_label") != "TE_PER_TENSOR_FP8_FWD_BWD"):
                raise ProbeUnavailable("Backend did not attest actual FP8; BF16 fallback is not accepted")
            result["fp8_executed"] = True
            errors = {name: _error_metrics(arms["bf16"][name], arms["fp8"][name])
                      for name in ("output", "weight_grad", "input_grad")}
            baseline_loss, fp8_loss = measurements["bf16"]["loss"], measurements["fp8"]["loss"]
            loss_error = (abs(fp8_loss - baseline_loss) / max(abs(baseline_loss), 1e-12)
                          if baseline_loss is not None and fp8_loss is not None else None)
            passed = (all(a["finite"] for a in measurements.values())
                      and all(e["finite"] and e["relative_l2"] <= config.max_relative_l2_error
                              for e in errors.values())
                      and loss_error is not None and loss_error <= config.max_relative_loss_error)
            result.update(status="MEASURED_MICROPROBE_PASS" if passed else "NUMERICAL_FAILURE",
                          reason="Synthetic Linear only; no full-model, LoRA, optimizer or deployment admission",
                          comparison={"errors": errors, "relative_loss_error": loss_error})
    except (ImportError, ProbeUnavailable) as error:
        result.update(status="UNSUPPORTED", reason=str(error))
    except Exception as error:
        # CUDA OOM subclasses RuntimeError; avoid keeping its traceback alive in
        # the receipt. Finally releases references and empties the allocator.
        is_oom = "out of memory" in str(error).lower() or type(error).__name__ == "OutOfMemoryError"
        result.update(status="OOM" if is_oom else "ERROR", reason=type(error).__name__ + ": " + str(error)[:600])
    finally:
        if backend is not None:
            try:
                backend.cleanup()
                cleanup_calls += 1
                result["cleanup"] = {"allocator_cleanup_attempted": True, "cleanup_calls": cleanup_calls}
            except Exception as error:
                result["cleanup"] = {"allocator_cleanup_attempted": True, "error": type(error).__name__}
                result.update(status="ERROR", reason="Backend cleanup failed; isolated process must exit")
            if "runtime" not in result and hasattr(backend, "runtime"):
                result["runtime"] = backend.runtime
        result["measurements"] = measurements
    return result


def quantize_e4m3_reference(values: list[float], *, calibration_amax: float | None = None) -> dict[str, Any]:
    """Actual CPU scalar E4M3 quantize/dequantize reference, NOT GPU execution.

    Finite E4M3 range +/-448, subnormal spacing 2^-9; round-to-nearest/even,
    saturate at the calibrated bound. No training or kernel claim follows.
    Nonzero magnitudes/calibration bounds must be in [1e-30, 1e30]; extremes
    outside this reference domain fail explicitly, before division or norms.
    """
    if (not values or len(values) > 4096
            or not all(type(v) in (int, float) and (type(v) is int or math.isfinite(v)) for v in values)):
        raise ValueError("expected 1..4096 finite scalar values")
    if any(v != 0 and not 1e-30 <= abs(v) <= 1e30 for v in values):
        raise ValueError("CPU reference magnitude must be zero or within [1e-30, 1e30]")
    amax = max(abs(v) for v in values) if calibration_amax is None else calibration_amax
    if (type(amax) not in (int, float) or amax < 0
            or (amax != 0 and not 1e-30 <= amax <= 1e30) or not math.isfinite(amax)):
        raise ValueError("calibration_amax must be zero or finite within [1e-30, 1e30]")
    if amax == 0 and any(v != 0 for v in values):
        raise ValueError("zero calibration bound cannot encode nonzero values")
    scale = amax / 448 if amax else 1.0
    quantized = []
    for value in values:
        x = min(abs(value / scale), 448.0)
        spacing = 2.0 ** max(-9, math.floor(math.log2(x)) - 3) if x else 2.0**-9
        q = min(round(x / spacing) * spacing, 448.0)
        quantized.append(math.copysign(q * scale, value))
    return {"measurement_label": "CPU_E4M3_REFERENCE_NOT_GPU_OR_MODEL", "fp8_executed": False,
            "quantized_dequantized": quantized, "scale": scale, "calibration_amax": amax,
            "clipped_values": sum(abs(v) > amax for v in values),
            "error": _error_metrics(values, quantized)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-gpu-probe", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=60)
    parser.add_argument("--recipe", default="auto_per_tensor")
    parser.add_argument("--_child", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._child is not None:
        result = _execute_probe(ProbeConfig(**json.loads(args._child)))
        print("PRECISION_PROBE_RESULT=" + json.dumps(result, sort_keys=True, allow_nan=False))
    else:
        result = run_probe(ProbeConfig(enable_gpu_probe=args.enable_gpu_probe,
                                      timeout_seconds=args.timeout_seconds, recipe=args.recipe))
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
