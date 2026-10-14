"""Bounded, stdlib-only offline preparation; never an execution/admission API.

Only the five pinned public source files and this package's source inventory are
read. Python sources are hashed as opaque bytes, never imported or executed.
No Git inspection, provider access, subprocess, epoch sampling, or file writes
are performed. The recorded baseline identifies the selected source bytes; it
is not an attestation of HEAD, the entire checkout, or an original private run.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

BASELINE_COMMIT = "cc14bd1a79aac1fe6135017c9e09d4834300675d"
PACKAGE_PATH = "tools/arc2_sft_rl_continuation_20261014"
PINS_PATH = PACKAGE_PATH + "/source-pins.json"
PINS_SHA256 = "220640c4f5a963d38153633040a0428ae2174e827b41f4dc466b119b1cf0c062"
SOURCE_PREFIX = "tools/arc_qwen_rlvr004_20261013/"
POLICY_PATH = SOURCE_PREFIX + "source/design/MEASURED-POLICY.json"
SOURCE_PATHS = (
    SOURCE_PREFIX + "publication_run008/rl_collect.py",
    SOURCE_PREFIX + "release/terminal-consumer/consumer/validate_owned_outputs.py",
    POLICY_PATH,
    SOURCE_PREFIX + "source/experiment_flow/controlled_batched.py",
    SOURCE_PREFIX + "source/rl_session/plan.py",
)
MAX_INVENTORY_BYTES = 16 * 1024
MAX_SOURCE_BYTES = 64 * 1024
MAX_TOTAL_SOURCE_BYTES = 128 * 1024


class PreparationError(ValueError):
    """The pinned public preparation inputs are missing, unsafe, or different."""


def _need(condition: bool, message: str) -> None:
    # Explicit checks intentionally remain effective under python -O.
    if not condition:
        raise PreparationError(message)


def _relative(name: str) -> tuple[str, ...]:
    _need(type(name) is str and 0 < len(name) <= 512, "invalid source path")
    parts = name.split("/")
    _need(
        not PurePosixPath(name).is_absolute()
        and len(parts) <= 24
        and all(part not in ("", ".", "..") for part in parts)
        and all(char.isascii() and (char.isalnum() or char in "/._-") for char in name),
        "source path must be clean project-relative POSIX text",
    )
    return tuple(parts)


def _identity(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


class _SourceRoot:
    """Descriptor-relative no-follow reads, including every root ancestor.

    Unsupported platforms fail closed. O_NONBLOCK avoids blocking on a FIFO
    before fstat rejects it. Each individual file is bounded and checked again
    after reading; no recursive tree traversal or evidence-directory read occurs.
    """

    def __init__(self, root: Path):
        _need(isinstance(root, Path), "repository_root must be a pathlib.Path")
        _need(".." not in root.parts, "repository root may not contain traversal")
        _need(
            hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
            and os.open in os.supports_dir_fd,
            "no-follow descriptor reads unavailable on this platform",
        )
        root = root.absolute()
        self.fd = -1
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            self.fd = os.open(root.anchor, flags)
            for part in root.parts[1:]:
                new_fd = os.open(part, flags, dir_fd=self.fd)
                os.close(self.fd)
                self.fd = new_fd
        except OSError as exc:
            self.close()
            raise PreparationError("repository root missing, linked, or not a directory") from exc

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def read(self, name: str, limit: int) -> bytes:
        parts = _relative(name)
        _need(type(limit) is int and 0 < limit <= MAX_SOURCE_BYTES, "invalid read limit")
        directory = os.dup(self.fd)
        descriptor = -1
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            for part in parts[:-1]:
                new_fd = os.open(part, directory_flags, dir_fd=directory)
                os.close(directory)
                directory = new_fd
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(parts[-1], flags, dir_fd=directory)
            before = os.fstat(descriptor)
            _need(stat.S_ISREG(before.st_mode), "non-regular source: " + name)
            _need(0 < before.st_size <= limit, "source byte limit: " + name)
            chunks = []
            remaining = limit + 1
            while remaining:
                chunk = os.read(descriptor, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            after = os.fstat(descriptor)
            current = os.stat(parts[-1], dir_fd=directory, follow_symlinks=False)
            _need(
                _identity(before) == _identity(after) == _identity(current)
                and len(raw) == before.st_size <= limit,
                "source changed during read: " + name,
            )
            return raw
        except OSError as exc:
            raise PreparationError("source missing, linked, or unreadable: " + name) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(directory)


def _strict_json(raw: bytes) -> dict:
    def pairs(rows: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in rows:
            _need(key not in result, "duplicate JSON field")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise PreparationError("non-finite JSON value")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PreparationError("invalid bounded JSON document") from exc
    _need(type(value) is dict, "JSON document must be an object")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _equal(actual: object, expected: object, label: str) -> None:
    _need(_canonical(actual) == _canonical(expected), "scientific policy differs: " + label)


def _validate_policy(policy: dict) -> None:
    """Explicit science checks supplement byte pins; repinning is not admission."""
    expected = {
        "format": "proposed-rlvr-single-session-policy-v2",
        "dispatch_authorized": False,
        "production_admitted": False,
        "hard_completion_guarantee": False,
        "clock_seconds": {"absolute": 43200, "inner": 42000, "outer": 42180, "provider": 42300},
        "anchor": {"label": "A", "updates": 256, "cosine_schedule_updates": 256,
                   "warmup_updates": 4, "min_lr_ratio": 0.1, "learning_rate": 0.0002,
                   "same_session_retrain": True, "historical_tensor_equivalence_claim": False,
                   "new_experiment_not_relabel_of_A64": True},
        "rl": {"batch_slots": 64, "max_batches": 4, "max_updates": 4,
               "learning_rate": 0.000001, "hard_phase_seconds": 7200,
               "planned_B_ceiling_seconds": 7080, "fixed_policy_within_batch": True,
               "temperature": 1.0, "top_p": 1.0, "resampling": False,
               "reward_dependent_replacement": False, "rollback_current_batch_only": True,
               "continue_next_disjoint_batch_after_zero_signal": True,
               "stop_on_incomplete_or_numeric_failure": True, "last_committed_B_preserved": True},
        "training_panel": {"attempts": 256, "parents": 32, "group_size": 8,
                           "fixed_batches_parent_positions": [[0, 8], [8, 16], [16, 24], [24, 32]],
                           "unchanged_previous_frozen_order": True},
        "control": {"label": "C", "restore": "A", "learning_rate": 0.0002,
                    "max_updates": 8192, "hard_phase_seconds": 7200, "padding": False,
                    "tolerance": "min(120,max(5,0.05*actual_B_seconds))",
                    "matched_quantity": "whole synchronized extra model-phase wall; setup, sampling, rewards, replay, hashing, Python, failed/rollback, save/reload and verification included"},
        "evaluation": {"TTT_updates": 0, "arms": ["A", "B", "C"], "dev_parents": 16,
                       "holdout_parents": 32, "greedy": True, "maximum_answers": 2,
                       "output_cap": 1024, "transforms": [0, 1], "paired_view_count": 288,
                       "selected_PUBLIC_queries": 167, "selected_PUBLIC_views": 334,
                       "public_arm_mixing": False,
                       "selection": "actual sealed dev predictions; exact count; fixed tie order A,B,C; freeze before any current-run held target access",
                       "primary_phase_order": ["common A", "B fixed-batch prefix", "C matched continuation",
                                               "A/B/C dev", "freeze selected arm", "selected-arm PUBLIC",
                                               "A/B/C held32", "model closure", "held scoring and original PUBLIC scorer"]},
    }
    for key, value in expected.items():
        if type(value) is dict and key != "clock_seconds":
            actual = policy.get(key)
            _need(type(actual) is dict, "missing scientific policy section: " + key)
            for field, required in value.items():
                _equal(actual.get(field), required, key + "." + field)
        else:
            _equal(policy.get(key), value, key)


def _artifact_checklist() -> list[dict]:
    """Names from pinned collectors/consumers, not claims that artifacts exist."""
    groups = [
        ("collector-output", ["RETRIEVAL-RECEIPT.json", "AUTHENTICATED-COLLECTION.json",
                              "TERMINAL-CONSUMER-RAW.json", "TERMINAL-VALIDATION.json",
                              "TERMINAL-CHECKPOINT.json"],
         "Retain exact numeric-version, source, selected-download, outside-in review and terminal report linkage."),
        ("collector-failure-output", ["TERMINAL-DIAGNOSTIC.json", "TERMINAL-BLOCKER.json"],
         "Retain applicable failure reports; absence of successful evidence cannot be converted to success."),
        ("owned-output", ["owner-request.json", "owner-clock.json", "artifact-inventory.json",
                          "outer-closure.json", "inner-closure.json", "owned-result.json",
                          "session-admission.json", "checkpoint-zip-descriptor.json"],
         "Use original authenticated ownership, clock and admission receipts; preserve consumed clocks and physical charges."),
        ("owned-experiment-output", ["experiment/result.json", "experiment/frozen-plan.json",
                                     "experiment/source-inventory.json", "experiment/physical-events.json",
                                     "experiment/A-checkpoint-proof.json", "experiment/B-checkpoint-proof.json",
                                     "experiment/C-checkpoint-proof.json"],
         "Verify original A/B/C persistence, whole-wall match, fixed dev selection, sealing and full PUBLIC denominator with existing validators."),
    ]
    return [{"root_role": role, "relative_names": names, "status": "not_inspected",
             "local_executor_requirement": requirement} for role, names, requirement in groups]


def prepare_plan(repository_root: Path) -> dict:
    """Return an inert deterministic aggregate, or raise PreparationError.

    This validates a small source-byte inventory, not a Git repository or runtime
    evidence. It does not synthesize private admission, sample a clock, assign a
    run identity, access credentials, launch training, or schedule another run.
    """
    source_root = _SourceRoot(repository_root)
    try:
        pins_raw = source_root.read(PINS_PATH, MAX_INVENTORY_BYTES)
        _need(hashlib.sha256(pins_raw).hexdigest() == PINS_SHA256, "source inventory byte pin differs")
        pins = _strict_json(pins_raw)
        _need(set(pins) == {"format", "baseline_commit", "scope", "authority", "dispatch_authorized", "files"},
              "source inventory schema differs")
        _need(pins["format"] == "irisx/arc2-offline-continuation-source-pins-v1"
              and pins["baseline_commit"] == BASELINE_COMMIT
              and pins["scope"] == "selected-public-source-bytes-only"
              and pins["authority"] == "reproducibility-only"
              and pins["dispatch_authorized"] is False, "source inventory scope differs")
        rows = pins["files"]
        _need(type(rows) is list and len(rows) == len(SOURCE_PATHS), "source inventory count differs")
        _need(all(type(row) is dict and set(row) == {"path", "bytes", "sha256", "role"} for row in rows),
              "source inventory member schema differs")
        _need([row["path"] for row in rows] == list(SOURCE_PATHS), "source inventory path set/order differs")
        total = 0
        policy_raw = None
        for row in rows:
            _relative(row["path"])
            size = row["bytes"]
            _need(type(size) is int and 0 < size <= MAX_SOURCE_BYTES, "source inventory byte limit")
            total += size
            _need(total <= MAX_TOTAL_SOURCE_BYTES, "aggregate source byte limit")
            raw = source_root.read(row["path"], size)
            _need(len(raw) == size and hashlib.sha256(raw).hexdigest() == row["sha256"],
                  "source byte pin differs: " + row["path"])
            if row["path"] == POLICY_PATH:
                policy_raw = raw
        _need(policy_raw is not None, "scientific policy missing")
        policy = _strict_json(policy_raw)
        _validate_policy(policy)
    finally:
        source_root.close()

    science = {key: policy[key] for key in (
        "identity", "anchor", "rl", "training_panel", "control", "evaluation",
        "clock_seconds", "reserves_seconds", "gates", "cost_model", "fallback")}
    science["evaluation"] = {
        **science["evaluation"], "public_tasks": 120,
        "public_denominator": {"tasks": 120, "queries": 167},
        "tie_break_order": ["A", "B", "C"],
        "holdout_is_pristine_project_confirmation": False,
        "seed": 1917, "decoder": "unchanged-native-grid-DFA",
        "packing": "frozen-native-whole-demo", "missing_or_invalid_answers": "wrong",
    }
    return {
        "format": "irisx/arc2-offline-continuation-plan-v1",
        "status": "OFFLINE_PREPARATION_ONLY",
        "baseline_commit": BASELINE_COMMIT,
        "dispatch_authorized": False,
        "production_admitted": False,
        "automatic_next_run": False,
        "model_execution_performed": False,
        "epoch_or_deadline_sampled": False,
        "original_private_admission_reconstructed": False,
        "source_identity": {
            "inventory_path": PINS_PATH, "inventory_sha256": PINS_SHA256,
            "scientific_policy_path": POLICY_PATH,
            "scientific_policy_sha256": hashlib.sha256(policy_raw).hexdigest(),
            "files": rows, "total_bytes": total,
            "selected_bytes_verified": True,
            "repository_head_verified": False, "complete_repository_verified": False,
            "authority": "reproducibility-only",
        },
        "scientific_plan": science,
        "local_executor_artifact_checklist": _artifact_checklist(),
        "limitations": [
            "Preparation supplies neither execution authority nor original private admission, release review, authentication, or environment bindings.",
            "Only the listed public source bytes are verified. Git HEAD, the complete checkout, private materials, runtime reports and provider state are not inspected.",
            "Pinned Python files are opaque source references; their runtime, model, collector and validator entry points are never imported or called.",
            "The controlled adapter is synthetic mechanics evidence only; no neural execution, scientific result, score or historical tensor equivalence is established.",
            "PUBLIC120 remains 120 tasks and 167 queries with the unchanged original sealed scorer; targets and evaluator bodies are never read here.",
            "held32 is reused experiment-held-out data, not pristine project confirmation. The comparison is of intervention packages, not an objective-only causal estimate.",
            "The 43200-second absolute bound includes queue, setup, model work, scoring and closure. No new epoch or deadline is sampled and no prior clock or charge is reset.",
            "A local executor must verify fresh authorized environment and release bindings using original independent evidence. Missing private admission is a blocker, never a template to fabricate.",
            "Artifact names are a checklist relative to their named local output roots, not existence or validation claims. Header-only checkpoint presence does not establish tensor verification or billing state.",
            "No completion or wall-match guarantee is supplied. Incomplete, unmatched, zero-signal, failed and unknown outcomes must retain their actual costs and limitations.",
        ],
    }
