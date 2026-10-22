"""Deterministic bounded CPU experiments. Run as a module from repository root.

These small synthetic tensors and exogenous gradients are not Qwen weights,
forward/backward computation, a training recipe, or evidence of useful learning.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np

from . import reference as r

SEEDS = tuple(range(8))
STEPS = 256
GROUP_SIZE = 32
MAGNITUDES = (0.0, 2.0**-16, 2.0**-8, 0.25, 1.0, 16.0)
LEARNING_RATES = (1e-6, 1e-5, 3e-5)
HISTORIES = ("constant_direction", "alternating_cancellation", "sparse_1_in_32", "decay_only", "decaying_oscillation")
SNAPSHOTS = (1, 16, 64, 256)
PROBABILITY_WORDS = (0x3F800001, 0x3F804000, 0x3F808000, 0x3F80FFFF,
                     0xBF804000, 0xBF80FFFF, 0x00000001, 0x00008000,
                     0x80008000, 0x007FFFFF, 0x3FFFFFFF, 0x7F7EFFFF)
SAMPLES_PER_SEED = 4096
ALPHA_FAMILY = 1e-6


def synthetic_tensor():
    local = np.arange(GROUP_SIZE)
    mantissa = 1.0 + ((local * 37) % 128) / 128.0
    signs = np.where(local % 3 == 0, -1.0, 1.0)
    return np.concatenate([(scale * mantissa * signs).astype(np.float32) for scale in MAGNITUDES])


def direction(size):
    i = np.arange(size)
    return (np.where(i % 5 < 3, 1.0, -1.0) * (0.5 + (i % 7) / 7.0)).astype(np.float32)


def history_multiplier(name, step):
    if name == "constant_direction":
        return 1.0
    if name == "alternating_cancellation":
        return 1.0 if step % 2 == 0 else -1.0
    if name == "sparse_1_in_32":
        return 1.0 if step % 32 == 0 else 0.0
    if name == "decay_only":
        return 0.0
    if name == "decaying_oscillation":
        return (1.0 if step % 17 < 11 else -1.0) / (1.0 + step / 32.0)
    raise ValueError(name)


def summary(final, initial, target):
    final = np.atleast_2d(final).astype(np.float64)
    initial = initial.astype(np.float64)
    target = target.astype(np.float64)
    error = final - target
    displacement = target - initial
    norm2 = float(np.dot(displacement, displacement))
    return {
        "signed_mean_error": float(error.mean()),
        "individual_path_rmse": float(np.sqrt(np.mean(error**2))),
        "ensemble_mean_rmse": float(np.sqrt(np.mean(error.mean(axis=0)**2))),
        "max_absolute_error": float(np.max(np.abs(error))),
        "mean_displacement_projection_ratio": None if norm2 == 0 else float(np.mean((final - initial) @ displacement) / norm2),
        "reference_displacement_l2": float(np.sqrt(norm2)),
        "across_seed_variance_mean": float(np.mean(np.var(final, axis=0))),
    }


def group_summaries(final, initial, target):
    return [{"initial_magnitude_scale": scale,
             **summary(np.atleast_2d(final)[:, i*GROUP_SIZE:(i+1)*GROUP_SIZE],
                       initial[i*GROUP_SIZE:(i+1)*GROUP_SIZE], target[i*GROUP_SIZE:(i+1)*GROUP_SIZE])}
            for i, scale in enumerate(MAGNITUDES)]


class Diagnostics:
    def __init__(self, shape):
        self.changed = 0
        self.intended = 0
        self.total = 0
        self.ever_changed = np.zeros(shape, bool)
        self.write_error = np.zeros(shape, np.float64)
        self.add_error = np.zeros(shape, np.float64)

    def record(self, old, update, candidate, new):
        changed = new != old
        self.changed += int(np.count_nonzero(changed))
        self.intended += int(np.count_nonzero(candidate != old))
        self.total += old.size
        self.ever_changed |= changed
        self.write_error += new.astype(np.float64) - candidate.astype(np.float64)
        self.add_error += candidate.astype(np.float64) - (old.astype(np.float64) + update.astype(np.float64))

    def result(self):
        return {"changed_writes": self.changed, "fp32_candidate_nonzero_writes": self.intended,
                "total_writes": self.total,
                "update_survival_fraction_of_nonzero_fp32_candidates": None if not self.intended else self.changed/self.intended,
                "never_changed_coordinate_fraction": float(np.mean(~self.ever_changed)),
                "accumulated_write_error_rms": float(np.sqrt(np.mean(self.write_error**2))),
                "accumulated_fp32_addition_error_rms": float(np.sqrt(np.mean(self.add_error**2)))}


def random_cube(size):
    # Fixed bounded replay cache for this CPU experiment only, not production design.
    return np.stack([np.stack([r.indexed_bits(seed, "synthetic/weight", step,
                    np.arange(size, dtype=np.uint64)) for seed in SEEDS]) for step in range(STEPS)])


def writeback_case(initial, lr, name, random):
    near = r.nearest(initial)
    sr = np.repeat(near[None, :], len(SEEDS), axis=0)
    ref64 = initial.astype(np.float64).copy()
    ref32 = initial.copy()
    dnear, dsr = Diagnostics(near.shape), Diagnostics(sr.shape)
    curve = []
    for step in range(STEPS):
        if name == "decay_only":
            # Same predetermined decay update for every arm, computed from unrounded shadow.
            update = (-lr * 0.01 * ref64).astype(np.float32)
        else:
            update = (-np.float32(lr * history_multiplier(name, step)) * direction(initial.size)).astype(np.float32)
        oldn, olds = r.decode(near), r.decode(sr)
        cn, cs = np.add(oldn, update, dtype=np.float32), np.add(olds, update, dtype=np.float32)
        near, sr = r.nearest(cn), r.stochastic(cs, random[step])
        dnear.record(oldn, update, cn, r.decode(near))
        dsr.record(olds, update, cs, r.decode(sr))
        ref64 += update.astype(np.float64)
        ref32 = np.add(ref32, update, dtype=np.float32)
        if step + 1 in SNAPSHOTS:
            curve.append({"step": step+1, "nearest": summary(r.decode(near), initial, ref64),
                          "stochastic": summary(r.decode(sr), initial, ref64)})
    return {"kind": "identical-precomputed-fp32-update-writeback-only", "history": name, "lr_diagnostic_only": lr,
            "nearest": {**summary(r.decode(near), initial, ref64), **dnear.result(),
                        "groups": group_summaries(r.decode(near), initial, ref64)},
            "stochastic": {**summary(r.decode(sr), initial, ref64), **dsr.result(),
                           "groups": group_summaries(r.decode(sr), initial, ref64)},
            "fp32_shadow_vs_fp64": summary(ref32, initial, ref64), "trajectory": curve}


def moments(m, v, gradient):
    mnext = np.float32(0.9)*m + np.float32(0.1)*gradient
    vnext = np.float32(0.999)*v + np.float32(0.001)*(gradient*gradient)
    return mnext, vnext


def adam_delta(weights, m, v, step, lr):
    # Explicitly FP32 candidate math. Fixed synthetic replay, not selected training hyperparameters.
    mhat = m / np.float32(1.0 - 0.9**(step+1))
    vhat = v / np.float32(1.0 - 0.999**(step+1))
    scaled = mhat / (np.sqrt(vhat) + np.float32(1e-8))
    return -np.float32(lr) * (scaled + np.float32(0.01)*weights)


def adam_case(initial, lr, name, random):
    near = r.nearest(initial)
    sr = np.repeat(near[None, :], len(SEEDS), axis=0)
    mbits = np.zeros(initial.size, np.uint16)
    vbits = np.zeros(initial.size, np.uint16)
    mref, vref, wref = np.zeros_like(initial), np.zeros_like(initial), initial.copy()
    bf_moment_shadow = initial.copy()
    dnear, dsr = Diagnostics(near.shape), Diagnostics(sr.shape)
    moment_mse = np.zeros(2, np.float64)
    candidate_delta_mse = np.zeros(2, np.float64)
    curve = []
    for step in range(STEPS):
        gradient = (np.float32(1e-3 * history_multiplier(name, step)) * direction(initial.size)).astype(np.float32)
        mref, vref = moments(mref, vref, gradient)
        mc, vc = moments(r.decode(mbits), r.decode(vbits), gradient)
        mbits, vbits = r.nearest(mc), r.nearest(vc)
        m, v = r.decode(mbits), r.decode(vbits)
        moment_mse += [np.mean((m.astype(np.float64)-mref)**2), np.mean((v.astype(np.float64)-vref)**2)]
        ref_delta = adam_delta(wref, mref, vref, step, lr)
        oldn, olds = r.decode(near), r.decode(sr)
        dn, ds = adam_delta(oldn, m, v, step, lr), adam_delta(olds, m, v, step, lr)
        candidate_delta_mse += [np.mean((dn.astype(np.float64)-ref_delta)**2), np.mean((ds.astype(np.float64)-ref_delta)**2)]
        cn, cs = np.add(oldn, dn, dtype=np.float32), np.add(olds, ds, dtype=np.float32)
        near, sr = r.nearest(cn), r.stochastic(cs, random[step])
        dnear.record(oldn, dn, cn, r.decode(near))
        dsr.record(olds, ds, cs, r.decode(sr))
        wref = np.add(wref, ref_delta, dtype=np.float32)
        bf_moment_shadow = np.add(bf_moment_shadow, adam_delta(bf_moment_shadow, m, v, step, lr), dtype=np.float32)
        if step+1 in SNAPSHOTS:
            curve.append({"step": step+1, "nearest": summary(r.decode(near), initial, wref),
                          "stochastic": summary(r.decode(sr), initial, wref)})
    return {"kind": "exogenous-synthetic-gradient-adamw-replay", "history": name, "lr_diagnostic_only": lr,
            "moment_policy": "FP32-local-compute-then-RNE-BF16-mu-nu-before-update",
            "nearest": {**summary(r.decode(near), initial, wref), **dnear.result(),
                        "candidate_delta_rmse_vs_all_fp32": float(np.sqrt(candidate_delta_mse[0]/STEPS)),
                        "vs_same_bf16_moments_fp32_weight_shadow": summary(r.decode(near), initial, bf_moment_shadow),
                        "groups": group_summaries(r.decode(near), initial, wref)},
            "stochastic": {**summary(r.decode(sr), initial, wref), **dsr.result(),
                           "candidate_delta_rmse_vs_all_fp32": float(np.sqrt(candidate_delta_mse[1]/STEPS)),
                           "vs_same_bf16_moments_fp32_weight_shadow": summary(r.decode(sr), initial, bf_moment_shadow),
                           "groups": group_summaries(r.decode(sr), initial, wref)},
            "moment_rmse_over_steps": {"mu": float(np.sqrt(moment_mse[0]/STEPS)), "nu": float(np.sqrt(moment_mse[1]/STEPS))},
            "bf16_moment_fp32_weight_shadow_vs_all_fp32": summary(bf_moment_shadow, initial, wref),
            "trajectory": curve}


def probability_receipt():
    n = SAMPLES_PER_SEED * len(SEEDS)
    tolerance = float(np.sqrt(np.log(2*len(PROBABILITY_WORDS)/ALPHA_FAMILY)/(2*n)))
    random = np.concatenate([r.indexed_bits(seed, "probability-receipt", 0,
                  np.arange(SAMPLES_PER_SEED, dtype=np.uint64)) for seed in SEEDS])
    exhaustive_bits = np.arange(65536, dtype=np.uint16)
    rows = []
    for word in PROBABILITY_WORDS:
        x = np.array([word], np.uint32).view(np.float32)[0]
        toward, away = word >> 16, (word >> 16)+1
        endpoints = r.decode(np.array([toward, away], np.uint16)).astype(np.float64)
        lower, upper = float(min(endpoints)), float(max(endpoints))
        p = (float(x)-lower)/(upper-lower)
        outputs = r.decode(r.stochastic(np.full(n, x, np.float32), random)).astype(np.float64)
        observed = float(np.mean(outputs == upper))
        exhaustive = r.decode(r.stochastic(np.full(65536, x, np.float32), exhaustive_bits)).astype(np.float64)
        rows.append({"fp32_bits_hex": f"{word:08x}", "value": float(x), "lower": lower, "upper": upper,
                     "expected_numeric_upper_probability": p, "observed_numeric_upper_probability": observed,
                     "hoeffding_tolerance_familywise": tolerance, "within_tolerance": abs(observed-p) <= tolerance,
                     "sampled_mean_error_in_ulp": float(np.mean((outputs-float(x))/(upper-lower))),
                     "expected_variance_in_ulp_squared": p*(1-p),
                     "sampled_variance_in_ulp_squared": float(np.var((outputs-float(x))/(upper-lower))),
                     "rare_event_expected_count": min(p,1-p)*n,
                     "rare_event_power": "low: do not interpret sampled pass as rare-event validation" if min(p,1-p)*n < 20 else "at least 20 expected rare outcomes",
                     "exhaustive_uniform_bits_mean_exact": float(np.mean(exhaustive)) == float(x),
                     "exhaustive_numeric_upper_count": int(np.count_nonzero(exhaustive == upper)),
                     "expected_numeric_upper_count": int(round(p*65536))})
    return {"seeds": SEEDS, "samples_per_seed": SAMPLES_PER_SEED, "familywise_alpha": ALPHA_FAMILY,
            "bound": "Hoeffding union bound over 12 fixed cases, conditional on independent uniform PRNG draws; empirical hash check, not proof of PRNG independence",
            "all_within_predeclared_tolerance": all(row["within_tolerance"] for row in rows),
            "all_exhaustive_means_exact": all(row["exhaustive_uniform_bits_mean_exact"] for row in rows), "cases": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".irisx/cpt-prerequisites-20261021/numerics"))
    args = parser.parse_args()
    path = args.output/"numerical-receipt.json"
    if path.exists():
        parser.error("receipt already exists; choose a fresh --output directory to preserve evidence")
    started = time.monotonic()
    initial = synthetic_tensor()
    random = random_cube(initial.size)
    results = [writeback_case(initial, lr, name, random) for lr in LEARNING_RATES for name in HISTORIES]
    adam_results = [adam_case(initial, lr, name, random) for lr in LEARNING_RATES for name in HISTORIES]
    root = Path(__file__).resolve().parents[2]
    sources = [Path(__file__), Path(r.__file__), root/"tests/test_bf16_numeric_prerequisites_20261021.py"]
    receipt = {
        "schema": "iris-bf16-numerical-receipt-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "bounded CPU synthetic numerical prerequisite only, not Qwen/TPU/model training",
        "python": platform.python_version(), "numpy": np.__version__,
        "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
        "preregistered_in_source": {"seeds": SEEDS, "steps": STEPS, "learning_rates_diagnostic_only": LEARNING_RATES,
            "histories": HISTORIES, "snapshots": SNAPSHOTS, "parameters": initial.size, "initial_magnitudes": MAGNITUDES,
            "synthetic_initial_sha256": r.input_digest(initial), "rng_algorithm": r.ALGORITHM,
            "random_cache_sha256": hashlib.sha256(random.astype("<u2").tobytes()).hexdigest()},
        "storage_and_math": {"bf16_weight_and_moment_storage": "uint16 encodings, two bytes each per element",
            "persistent_fp32_master_in_bf16_arms": False, "candidate_and_adam_math": "bounded NumPy FP32",
            "references": "small FP64 unrounded writeback shadow and FP32 optimizer/weight shadows only for diagnostics",
            "cpu_random_cache_bytes": random.nbytes,
            "warning": "bounded CPU random cache is intentionally not a production memory design; no compiled/live TPU peak measured"},
        "probability": probability_receipt(), "writeback_experiments": results, "adam_replay_experiments": adam_results,
        "limitations": ["No real Qwen weights or real model-derived gradients; no forward/backward, loss, tokens or task accuracy.",
            "No native Pallas/XLA compile or TPU v5p run; SHA-256-U16 is not claimed bitwise equivalent to hardware stochastic conversion, Threefry or TPU PRNG.",
            "BF16 subnormals are preserved by this reference; actual backend flush/conversion semantics still need measurement.",
            "All BF16 weights and moments here are tiny CPU arrays; full-model memory, speed and fit are unverified.",
            "Unbiased final rounding does not make BF16 moments, nonlinear Adam or changing-gradient training unbiased.",
            "Finite magnitudes above BF16 maximum are rejected, not saturated or converted to infinity.",
            "Checkpoint tests cover a bounded rounding stream and BF16 buffer, not optimizer moments, distributed checkpoint or full model resume.",
            "Nonzero update survival is a diagnostic, not a learning acceptance threshold; single-path SR can have worse error/variance."],
        "elapsed_seconds": time.monotonic()-started,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"receipt": str(path), "cases": len(results)+len(adam_results),
                      "all_probability_tolerances_pass": receipt["probability"]["all_within_predeclared_tolerance"],
                      "all_exhaustive_means_exact": receipt["probability"]["all_exhaustive_means_exact"],
                      "elapsed_seconds": receipt["elapsed_seconds"]}))


if __name__ == "__main__":
    main()
