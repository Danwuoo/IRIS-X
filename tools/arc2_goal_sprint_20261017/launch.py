"""Explicit solver/evaluator separation, complete tree closure, and sealed scoring.

Dataset-separated execution mounts no evaluator on the solver provider. The
parent scores only after exact provider terminal/output verification. The
optional Landlock mode fails closed if unsupported, never silently downgrading
to a claimed sandbox. The subreaper guard closes setsid/double-fork descendants.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import runpy
import shutil
import sys
import time

SCORER_SHA256 = "3df3fd40c0a4db82dc6ad5c568102e45ad10efad8529412eae0623bd9f4ba016"
SOLVER_MANIFEST_SHA256 = "549019b4b5cb47176f3abd3fcd9ca516e91b7d6e581dfc414a5a6452ff7b1f7f"
EVALUATOR_MANIFEST_SHA256 = "c7e8ad35770a66a71a22cccbbd0455c1c3bcc1a505dfb2e4c29819eec6209e33"
TRAINING_MANIFEST_SHA256 = "a4b9da04d8690c57a3d0855553989fa055c5b9283ffc1784fe99413c8d1cb9d5"
SCORING_RESERVE_SECONDS = 300


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def write_new(path, value):
    path = Path(path)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def relay_solver_log(reader, *, max_bytes=64 * 1024):
    """Relay bounded already-written solver diagnostics, never prediction files.

    The complete private log remains authoritative. Notebook stdout is only an
    observation channel: a disconnected consumer must not terminate learning.
    Reading uses a separate descriptor so the child's append position is intact.
    """
    require(type(max_bytes) is int and 0 < max_bytes <= 1024 * 1024,
            "bounded positive log relay size required")
    raw = reader.read(max_bytes)
    if raw:
        descriptor, blocking = None, None
        try:
            descriptor = sys.stdout.fileno()
            blocking = os.get_blocking(descriptor)
            os.set_blocking(descriptor, False)
            # A slow or disconnected notebook observer must never stall the
            # process-owner deadline loop. Short writes are deliberately not
            # retried; the original complete private log remains on disk.
            os.write(descriptor, raw.decode("utf-8", errors="replace").encode("utf-8"))
        except (AttributeError, OSError, TypeError, ValueError):
            pass
        finally:
            if descriptor is not None and blocking is not None:
                try:
                    os.set_blocking(descriptor, blocking)
                except (AttributeError, OSError, TypeError, ValueError):
                    pass
    return len(raw)


def regular(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink material forbidden: " + str(path))
    require(path.is_file(), "regular file required: " + str(path))
    return path


def verify_inventory(root, manifest_sha256):
    root = Path(root).absolute()
    require(sha(regular(root / "manifest.json")) == manifest_sha256, "dataset manifest pin differs")
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, row in manifest["files"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "unsafe inventory path")
        path = regular(root / name)
        require(path.stat().st_size == row["bytes"] and sha(path) == row["sha256"], "dataset byte identity differs: " + name)
    actual = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), "dataset symlink forbidden")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(manifest["files"]) | {"manifest.json"}, "dataset contains unmanifested material")
    return manifest


class IsolationUnavailable(RuntimeError):
    pass


class _Ruleset(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def landlock_abi():
    if sys.platform != "linux" or platform.machine() not in {"x86_64", "aarch64"}:
        raise IsolationUnavailable("Linux x86_64/aarch64 Landlock is required")
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)
    if abi < 1:
        number = ctypes.get_errno()
        raise IsolationUnavailable("Landlock unavailable: " + os.strerror(number))
    return abi


def apply_landlock(read_paths, write_paths):
    """Irreversible inherited allowlist. Never grant a data mount's common parent.

    READ_FILE/READ_DIR and EXECUTE are mediated; write/create/remove/refer and
    truncate are also handled when the kernel supports them. Symlink aliases
    are checked against their resolved targets by the kernel. Existing FDs are
    closed by the launch guard; stdin is /dev/null and only output logs remain.
    """
    abi = landlock_abi()
    libc = ctypes.CDLL(None, use_errno=True)
    handled = (1 << (15 if abi >= 3 else 14 if abi >= 2 else 13)) - 1
    readonly = (1 << 0) | (1 << 2) | (1 << 3)
    attributes = _Ruleset(handled)
    ruleset = libc.syscall(444, ctypes.byref(attributes), ctypes.sizeof(attributes), 0)
    if ruleset < 0:
        raise IsolationUnavailable("Landlock create_ruleset: " + os.strerror(ctypes.get_errno()))
    try:
        for raw, permissions in [(p, readonly) for p in read_paths] + [(p, handled) for p in write_paths]:
            path = Path(raw)
            if not path.exists():
                raise IsolationUnavailable("allowlist path missing: " + str(path))
            access = permissions
            if not path.is_dir():
                access &= (1 << 0) | (1 << 1) | (1 << 2) | ((1 << 14) if abi >= 3 else 0)
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = _PathRule(access, fd)
                if libc.syscall(445, ruleset, 1, ctypes.byref(rule), 0) != 0:
                    raise IsolationUnavailable("Landlock add_rule: " + os.strerror(ctypes.get_errno()))
            finally:
                os.close(fd)
        if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS, current child only.
            raise IsolationUnavailable("cannot apply no_new_privs")
        if libc.syscall(446, ruleset, 0) != 0:
            raise IsolationUnavailable("Landlock restrict_self: " + os.strerror(ctypes.get_errno()))
    finally:
        os.close(ruleset)
    return abi


def assert_denied(paths):
    """Open and immediately close only; never read even if a broken guard admits it."""
    denied = []
    for raw in paths:
        try:
            fd = os.open(raw, os.O_RDONLY | os.O_CLOEXEC)
        except OSError as exc:
            require(exc.errno in {errno.EACCES, errno.EPERM}, "isolation probe not a permission denial: " + str(raw))
            denied.append(str(raw))
        else:
            os.close(fd)
            raise IsolationUnavailable("evaluator path is readable after isolation: " + str(raw))
    require(denied, "at least one actual evaluator path must be denied")
    return denied


def check_allowlist(read_paths, write_paths, forbidden_roots):
    """Reject any broad grant containing evaluator/root/parent-control material."""
    for raw in list(read_paths) + list(write_paths):
        allowed = Path(raw).resolve()
        require(allowed != Path("/"), "root filesystem grant forbidden")
        for forbidden in forbidden_roots:
            hidden = Path(forbidden).resolve()
            require(not hidden.is_relative_to(allowed) and not allowed.is_relative_to(hidden),
                    "allowlist intersects protected evaluator/control material")


def check_dataset_separation(input_root, allowed_input_roots):
    """Fail if the original PUBLIC/evaluator or any unexpected input is mounted.

    This is a verified mount/data contract, NOT an OS sandbox. A clean provider
    execution mounts only pinned source, train, solver projection, wheels,
    interpreter and model. Existing ARC3 metadata is retained but never read.
    """
    root = Path(input_root).absolute()
    old = (root / "iris-x-public120-data-20261010", root / "datasets/danielwuu/iris-x-public120-data-20261010")
    require(not any(p.exists() or p.is_symlink() for p in old), "original evaluator-bearing PUBLIC Dataset is mounted")
    allowed = {Path(p).absolute() for p in allowed_input_roots}
    require(all(p.is_relative_to(root) and p != root and p.is_dir() for p in allowed), "exact existing input leaf roots required")
    require(all(not p.is_symlink() for p in allowed), "symlink input mount forbidden")
    # Preserve the association, but do not descend into/read competition data.
    allowed.update((root / "arc-prize-2026-arc-agi-3", root / "competitions/arc-prize-2026-arc-agi-3"))
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            require(not path.is_symlink(), "input hierarchy symlink forbidden")
            if path in allowed:
                continue
            require(path.is_dir() and any(p.is_relative_to(path) for p in allowed),
                    "unexpected input mount/file in dataset-separated run: " + str(path))
            pending.append(path)
    for leaf in allowed_input_roots:
        require(not (Path(leaf) / "evaluator").exists(), "evaluator directory present in solver-only mounted source")
    return True


def isolated_worker(spec_path):
    spec = json.loads(regular(spec_path).read_bytes())
    source = Path(spec["source_root"])
    sys.path[:0] = [str(source), str(source / "src")]
    if spec.get("evaluation_mode") == "external-cpu":
        check_dataset_separation(spec["input_root"], spec["allowed_input_roots"])
        verify_inventory(Path(spec["public_path"]).parent, SOLVER_MANIFEST_SHA256)
        receipt = {"format": "irisx/goal-isolation-v1", "mechanism": "dataset-separated-provider-execution",
                   "filesystem_allowlist_enforced": False, "os_sandbox_claimed": False,
                   "original_public_dataset_mounted": False, "evaluator_dataset_absent": True,
                   "solver_manifest_sha256": SOLVER_MANIFEST_SHA256,
                   "allowed_input_roots": spec["allowed_input_roots"],
                   "scoring": "external CPU only after source-side closure and provider terminal verification"}
    else:
        check_allowlist(spec["read_paths"], spec["write_paths"], spec["forbidden_roots"])
        # All process-level access is established before any model/training import.
        abi = apply_landlock(spec["read_paths"], spec["write_paths"])
        denied = assert_denied(spec["denied_probes"])
        receipt = {"format": "irisx/goal-isolation-v1", "mechanism": "landlock-filesystem-allowlist", "landlock_abi": abi,
                   "filesystem_allowlist_enforced": True, "actual_original_evaluator_paths_denied": denied,
                   "inherited_by_descendants": True, "preexisting_application_fds": False}
    write_new(Path(spec["output_dir"]) / "isolation.json", receipt)
    sys.argv = ["tools.arc2_goal_sprint_20261017.run", "--config", spec["solver_config"]]
    runpy.run_module("tools.arc2_goal_sprint_20261017.run", run_name="__main__", alter_sys=True)


def runtime_allowlist(source, environment, model_roots, training, public, output):
    # No /kaggle/input, /kaggle/working, /tmp, home, or whole /proc grant.
    paths = [Path(source), Path(environment), Path(sys.base_prefix), Path(training), Path(public), *map(Path, model_roots)]
    paths += [Path(p) for p in ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/opt", "/etc", "/sys",
                               "/proc/self", "/proc/cpuinfo", "/proc/meminfo", "/proc/stat",
                               "/proc/version", "/proc/driver/nvidia") if Path(p).exists()]
    writes = [Path(output), Path("/dev")]
    return sorted({str(p.absolute()) for p in paths}), [str(p) for p in writes]


def candidate_audit(path, pools, *, require_complete=True):
    """Validate private ranking provenance without consulting any answer bytes.

    Only the already selected two grids in pools.json are scored. The larger
    pool is retained to audit how those two were chosen, never for post-score
    candidate selection or an expanded pass@k claim.
    """
    path = regular(path)
    require(path.stat().st_size <= 64 * 1024**2, "bounded candidate audit required")
    def nonfinite(value):
        raise ValueError("nonfinite candidate audit value: " + value)
    def finite_float(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite candidate audit number")
        return result
    require(type(require_complete) is bool, "Boolean audit completeness requirement needed")
    audit = json.loads(path.read_bytes(), parse_constant=nonfinite, parse_float=finite_float)
    require(isinstance(audit, dict) and audit.get("format") == "irisx/private-full-candidates-v1"
            and audit.get("run_id") == pools.get("run_id"), "candidate audit identity differs")
    records = audit.get("records")
    require(isinstance(records, list) and len(records) <= 167, "bounded candidate records required")
    expected = {}
    for task in pools.get("records", []):
        for test in task.get("tests", []):
            require(isinstance(task["task_id"], str) and type(test["test_index"]) is int
                    and test["test_index"] >= 0, "exact selected query identity required")
            key = (task["task_id"], test["test_index"])
            require(key not in expected, "duplicate selected query")
            expected[key] = test
    seen = set()
    for record in records:
        require(isinstance(record, dict), "candidate query record required")
        require(isinstance(record.get("task_id"), str) and type(record.get("test_index")) is int
                and record["test_index"] >= 0, "exact candidate query identity required")
        key = (record.get("task_id"), record.get("test_index"))
        require(key in expected and key not in seen, "candidate query coverage differs")
        seen.add(key)
        candidates, order = record.get("candidates"), record.get("ranked_candidate_indices")
        require(isinstance(candidates, list) and len(candidates) <= 16, "bounded candidate list required")
        require(isinstance(order, list) and all(type(i) is int for i in order)
                and sorted(order) == list(range(len(candidates))), "candidate rank must be a permutation")
        require(all(isinstance(row, dict) and "grid" in row for row in candidates), "candidate grid record required")
        for row in candidates:
            grid = row["grid"]
            require(isinstance(grid, list) and 1 <= len(grid) <= 30
                    and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
                    and all(isinstance(line, list) and len(line) == len(grid[0])
                            and all(type(cell) is int and 0 <= cell <= 9 for cell in line) for line in grid),
                    "exact bounded integer candidate grid required")
        require(record.get("input_digest") == expected[key].get("input_digest")
                and [candidates[i]["grid"] for i in order[:2]] == expected[key].get("ranked_grids"),
                "candidate top two differ from sealed predictions")
    require(not require_complete or seen == set(expected), "candidate audit is incomplete for selected queries")
    return {"sha256": sha(path), "bytes": path.stat().st_size, "queries": len(records),
            "expected_queries": len(expected), "missing_queries": len(set(expected) - seen),
            "complete_coverage": seen == set(expected), "complete_required": require_complete,
            "used_for_scoring": False, "scored_file": "pools.json", "scored_max_candidates": 2}


def seal_predictions(output, seal_root, closure, source_sha256):
    from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
    verify_closed_proof(closure)
    require(closure["closed"] and closure["ownership_complete"], "complete solver subtree closure required before seal")
    source = regular(Path(output) / "pools.json")
    seal_root = Path(seal_root)
    seal_root.mkdir(mode=0o700)
    target = seal_root / "pools.json"
    with source.open("rb") as stream, target.open("xb") as dest:
        shutil.copyfileobj(stream, dest)
        dest.flush()
        os.fsync(dest.fileno())
    require(sha(source) == sha(target), "prediction copy changed while sealing")
    os.chmod(target, 0o400)
    summary_path = Path(output) / "run-summary.json"
    solver_summary = {"present": False, "sha256": None, "solver_status": None}
    if summary_path.exists():
        regular(summary_path)
        require(summary_path.stat().st_size <= 16 * 1024**2, "bounded solver summary required")
        summary = json.loads(summary_path.read_bytes())
        require(summary.get("run_id") == json.loads(target.read_bytes()).get("run_id"), "solver summary run identity differs")
        copied = seal_root / "run-summary.json"
        with copied.open("xb") as stream:
            stream.write(summary_path.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        require(sha(summary_path) == sha(copied), "solver summary changed while sealing")
        os.chmod(copied, 0o400)
        solver_summary = {"present": True, "sha256": sha(copied), "solver_status": summary.get("solver_status")}
    full_pool_path = Path(output) / "full-candidate-pools.json"
    full_pool_receipt = None
    complete_solver = closure["worker_returncode"] == 0 and solver_summary["solver_status"] == "complete"
    policy = summary.get("continuation_policy", {}) if solver_summary["present"] else {}
    expanded = (policy.get("candidate_views", 2) != 2 or policy.get("candidate_ranker", "first") != "first"
                or policy.get("candidate_batch_size", 1) != 1)
    require(not (complete_solver and expanded) or full_pool_path.is_file(),
            "completed expanded inference requires private candidate audit")
    if full_pool_path.exists() or full_pool_path.is_symlink():
        full_pool_receipt = candidate_audit(full_pool_path, json.loads(target.read_bytes()), require_complete=complete_solver)
        copied = seal_root / "full-candidate-pools.json"
        with full_pool_path.open("rb") as stream, copied.open("xb") as dest:
            shutil.copyfileobj(stream, dest)
            dest.flush()
            os.fsync(dest.fileno())
        require(sha(copied) == full_pool_receipt["sha256"] == sha(full_pool_path),
                "candidate audit changed while sealing")
        os.chmod(copied, 0o400)
    seal = {"format": "irisx/goal-prediction-seal-v1", "pools_sha256": sha(target),
            "source_manifest_sha256": source_sha256, "solver_manifest_sha256": SOLVER_MANIFEST_SHA256,
            "evaluator_manifest_sha256": EVALUATOR_MANIFEST_SHA256,
            "scorer_sha256": SCORER_SHA256, "generation_may_resume": False,
            "closure": closure, "solver_summary": solver_summary, "tasks": 120, "queries": 167, "sealed_epoch": time.time(),
            "isolation": json.loads(regular(Path(output) / "isolation.json").read_bytes())
                         if (Path(output) / "isolation.json").is_file() else {"mechanism": "synthetic-test-fixture"}}
    if full_pool_receipt is not None:
        seal["private_candidate_audit"] = full_pool_receipt
    write_new(seal_root / "prediction-seal.json", seal)
    os.chmod(seal_root / "prediction-seal.json", 0o400)
    return seal


def verify_external_closure(seal_root, seal, evidence):
    """Validate the parent's pinned remote terminal evidence, not local /proc.

    The parent must first verify the exact numeric provider run is terminal,
    match its submitted source, and retrieve the exact seal/pools outputs. This
    function binds those observations; it does not impersonate a provider API
    attestation or claim foreign PID identities are live-verifiable locally.
    """
    require(set(evidence) == {"terminal_path", "terminal_sha256", "seal_sha256", "source_manifest_sha256"},
            "explicit external terminal and sealed-source pins required")
    terminal_path = regular(evidence["terminal_path"])
    require(sha(terminal_path) == evidence["terminal_sha256"], "parent terminal evidence changed")
    require(sha(Path(seal_root) / "prediction-seal.json") == evidence["seal_sha256"], "downloaded seal differs from provider-bound expected bytes")
    terminal = json.loads(terminal_path.read_bytes())
    require(terminal.get("format") == "irisx/goal-provider-terminal-v1" and terminal.get("notebook_id") == 138123872
            and type(terminal.get("version")) is int and terminal["version"] > 0
            and terminal.get("status") in {"COMPLETE", "ERROR", "CANCEL_ACKNOWLEDGED", "CANCELLED"},
            "exact terminal numeric provider notebook evidence required")
    require(terminal.get("source_verified") is True and terminal.get("outputs_verified") is True,
            "parent must verify submitted source and exact downloaded outputs")
    require(terminal.get("source_manifest_sha256") == seal["source_manifest_sha256"] == evidence["source_manifest_sha256"]
            and terminal.get("prediction_seal_sha256") == evidence["seal_sha256"]
            and terminal.get("pools_sha256") == seal["pools_sha256"], "provider/source/prediction binding differs")
    stamp = terminal.get("verified_terminal_epoch")
    require(type(stamp) in {int, float} and math.isfinite(stamp) and stamp >= seal["sealed_epoch"] and stamp <= time.time(),
            "terminal observation must follow source-side sealing")
    require(seal["isolation"].get("mechanism") == "dataset-separated-provider-execution"
            and seal["isolation"].get("evaluator_dataset_absent") is True
            and seal["isolation"].get("os_sandbox_claimed") is False, "honest dataset-separated boundary receipt required")
    proof = seal["closure"]
    require(proof.get("format") == "irisx/owned-process-closure-v1"
            and proof.get("scope") == "dedicated-subreaper-tree"
            and proof.get("closed") is True and proof.get("ownership_complete") is True
            and proof.get("remaining") == [] and proof.get("errors") == []
            and type(proof.get("returncode")) is int and type(proof.get("worker_returncode")) is int,
            "source-side complete owned subtree closure required")
    identities = proof.get("owned_identities")
    require(isinstance(identities, list) and len(identities) >= 2 and proof.get("root_identity") in identities,
            "source-side process identity inventory required")
    for identity in identities:
        require(set(identity) == {"pid", "birth", "session", "state"} and
                all(type(identity[k]) is int and identity[k] >= 0 for k in ("pid", "birth", "session")) and
                type(identity["state"]) is str, "source-side process identity malformed")
    require(len({(i["pid"], i["birth"]) for i in identities}) == len(identities), "duplicate source-side process identities")
    return terminal


def score_sealed(seal_root, evaluator_root, public_path, source_root, *, external_evidence=None):
    """First answer read follows live closure or pinned terminal/export verification."""
    from tools.arc_learning_agent_20261011.process_guard import verify_closed_proof
    seal_root = Path(seal_root)
    seal = json.loads(regular(seal_root / "prediction-seal.json").read_bytes())
    if external_evidence is None:
        verify_closed_proof(seal["closure"])
        closure_verification = "same-host-live-process-incarnations"
    else:
        external_terminal = verify_external_closure(seal_root, seal, external_evidence)
        closure_verification = "pinned-source-closure-plus-parent-verified-provider-terminal"
    require(seal["generation_may_resume"] is False, "generation must be permanently closed")
    require(seal["solver_manifest_sha256"] == SOLVER_MANIFEST_SHA256 and
            seal["evaluator_manifest_sha256"] == EVALUATOR_MANIFEST_SHA256 and
            seal["tasks"] == 120 and seal["queries"] == 167, "sealed data identity/denominator differs")
    require(sha(regular(Path(source_root) / "tools/arc_offline_evaluation.py")) == SCORER_SHA256 == seal["scorer_sha256"],
            "unchanged original scorer required")
    require(sha(regular(seal_root / "pools.json")) == seal["pools_sha256"], "sealed predictions changed")
    if "private_candidate_audit" in seal:
        require(candidate_audit(seal_root / "full-candidate-pools.json",
                                json.loads((seal_root / "pools.json").read_bytes()),
                                require_complete=seal["private_candidate_audit"]["complete_required"]) == seal["private_candidate_audit"],
                "sealed private candidate audit changed")
    solver_summary = seal.get("solver_summary", {})
    if solver_summary.get("present"):
        require(sha(regular(seal_root / "run-summary.json")) == solver_summary["sha256"], "sealed solver summary changed")
        run_summary = json.loads((seal_root / "run-summary.json").read_bytes())
        require(run_summary.get("solver_status") == solver_summary.get("solver_status"), "sealed solver status differs")
    evaluator_root = Path(evaluator_root)
    verify_inventory(evaluator_root, EVALUATOR_MANIFEST_SHA256)
    from tools.arc_offline_evaluation import load_pinned_reference, evaluate
    import tools.arc_offline_evaluation as scorer_module
    require(sha(regular(scorer_module.__file__)) == SCORER_SHA256, "imported scorer bytes differ")
    challenges, solutions, reference = load_pinned_reference(evaluator_root / "upstream", evaluator_root / "provenance.json")
    require(challenges == json.loads(regular(public_path).read_bytes()), "solver and evaluator challenge projection differ")
    pools = json.loads((seal_root / "pools.json").read_bytes())
    report = evaluate(challenges, solutions, pools)
    del solutions
    metrics = report["development_metrics"]
    require(metrics["tasks"] == 120 and metrics["tests"] == 167, "full 120/167 evaluation denominator required")
    pass2 = metrics["metrics"]["pass_at_2"]
    nonempty = sum(bool(test.get("ranked_grids")) for row in pools.get("records", []) for test in row.get("tests", []))
    operational = (seal["closure"]["worker_returncode"] == 0 and solver_summary.get("present") is True
                   and solver_summary.get("solver_status") == "complete"
                   and (external_evidence is None or external_terminal["status"] == "COMPLETE"))
    threshold_met = pass2["numerator"] >= 156 and pass2["denominator"] == 167
    summary = {"format": "irisx/goal-public-summary-v1", "run_id": pools["run_id"],
               "measurement": "public-development", "official_score": None, "hidden_score": None,
               "tasks": 120, "queries": 167, "pass_at_2": pass2,
               "goal": "micro pass@2 > 0.93 (at least 156/167)",
               "score_threshold_met": threshold_met, "goal_met": threshold_met and operational,
               "operational_success": operational, "valid_scored_predictions": True,
               "model_capability_result": operational and nonempty > 0,
               "public_nonempty_queries": nonempty, "solver_status": solver_summary.get("solver_status"),
               "solver_summary_sha256": solver_summary.get("sha256"),
               "scorer_sha256": SCORER_SHA256, "prediction_seal_sha256": sha(seal_root / "prediction-seal.json"),
               "reference": reference, "solver_returncode": seal["closure"]["worker_returncode"],
               "generation_may_resume": False, "closure_verification": closure_verification,
               "isolation": seal["isolation"],
               "provider_terminal_evidence_sha256": None if external_evidence is None else external_evidence["terminal_sha256"],
               "provider_terminal": None if external_evidence is None else
                    {key: external_terminal[key] for key in ("notebook_id", "version", "status", "verified_terminal_epoch")}}
    require(sha(seal_root / "pools.json") == seal["pools_sha256"], "sealed predictions changed during scoring")
    write_new(seal_root / "evaluation-detail.json", report)
    write_new(seal_root / "public-summary.json", summary)
    return summary


def launch(request):
    from tools.arc_learning_agent_20261011.process_guard import OwnedProcessGuard, verify_closed_proof
    source = Path(request["source_root"]).absolute()
    control = Path(request["control_root"]).absolute()
    output = Path(request["solver_config"]["output_dir"]).absolute()
    evaluator = Path(request["evaluator_root"]).absolute()
    control.mkdir(mode=0o700, parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    for name in ("tmp", "home", "cache"):
        (output / name).mkdir()
    config_path = output / "solver-config.json"
    write_new(config_path, request["solver_config"])
    public = Path(request["solver_config"]["public_path"])
    keys = sorted(json.loads(regular(public).read_bytes()))
    require(len(keys) == 120, "complete solver task inventory required")
    mode = request.get("evaluation_mode", "landlock-local")
    require(mode in {"landlock-local", "external-cpu"}, "unknown evaluation boundary")
    if mode == "external-cpu":
        check_dataset_separation(request["input_root"], request["allowed_input_roots"])
        spec = {"source_root": str(source), "evaluation_mode": mode,
                "input_root": request["input_root"], "allowed_input_roots": request["allowed_input_roots"],
                "public_path": str(public), "solver_config": str(config_path), "output_dir": str(output)}
    else:
        probes = [str(evaluator / "manifest.json"), str(evaluator / "upstream/data/evaluation" / (keys[0] + ".json"))]
        for probe in probes:
            regular(probe)  # Presence only, never answer bytes.
        reads, writes = runtime_allowlist(source, request["environment_root"], request["model_roots"],
                                         request["solver_config"]["training_root"], public.parent, output)
        # Its manifest can sit at the training dataset root rather than data/training.
        reads.append(str(regular(request["solver_config"]["training_manifest_path"])))
        spec = {"source_root": str(source), "read_paths": reads, "write_paths": writes,
                "forbidden_roots": [str(evaluator), str(control)], "denied_probes": probes,
                "solver_config": str(config_path), "output_dir": str(output), "evaluation_mode": mode}
        check_allowlist(reads, writes, spec["forbidden_roots"])
    spec_path = control / "isolation-spec.json"
    write_new(spec_path, spec)
    deadline = float(request["solver_config"]["session_deadline_epoch"]) - SCORING_RESERVE_SECONDS
    require(math.isfinite(deadline) and time.time() < deadline, "platform deadline scoring reserve already reached")
    env = {**request["runtime_env"], "HOME": str(output / "home"), "TMPDIR": str(output / "tmp"),
           "HF_HOME": str(output / "cache"), "TRITON_CACHE_DIR": str(output / "cache/triton"),
           "CUDA_CACHE_PATH": str(output / "cache/cuda"), "PYTHONDONTWRITEBYTECODE": "1"}
    guard = None
    try:
        with (control / "solver.log").open("xb") as log, \
                (control / "solver.log").open("rb") as relay, open(os.devnull, "rb") as null:
            guard = OwnedProcessGuard.spawn([request["python"], "-I", "-B", str(source / "tools/arc2_goal_sprint_20261017/launch.py"),
                                            "--isolated-worker", str(spec_path)], evidence_dir=control / "owned-tree",
                                           cwd=output, env=env, stdin=null, stdout=log, stderr=log)
            while guard.poll() is None and time.time() < deadline:
                relay_solver_log(relay)
                time.sleep(min(2.0, max(0.01, deadline - time.time())))
            closure = guard.stop(timeout=30) if guard.poll() is None else guard.closed_proof()
            verify_closed_proof(closure)
            write_new(control / "owner-closure.json", closure)
            # Bound console draining even if a faulty worker emitted excessive
            # diagnostics; retain the full original file for terminal retrieval.
            for _ in range(16):
                if relay_solver_log(relay) == 0:
                    break
    finally:
        if guard is not None and guard.poll() is None:
            guard.stop(timeout=30)
    require((output / "isolation.json").is_file(), "solver isolation admission failed; see solver.log")
    require((output / "pools.json").is_file(), "solver produced no sealable predictions; see solver.log")
    pools_identity = json.loads(regular(output / "pools.json").read_bytes())
    require(pools_identity.get("run_id") == request["solver_config"]["run_id"], "solver prediction run identity differs")
    seal_root = control / "sealed"
    seal_predictions(output, seal_root, closure, request["source_manifest_sha256"])
    if mode == "external-cpu":
        terminal = {"status": "SEALED_AWAITING_EXTERNAL_EVALUATOR", "run_id": request["solver_config"]["run_id"],
                    "prediction_seal_sha256": sha(seal_root / "prediction-seal.json"),
                    "pools_sha256": sha(seal_root / "pools.json"), "source_manifest_sha256": request["source_manifest_sha256"],
                    "isolation": "dataset-separated-provider-execution", "official_score": None,
                    "public_score": None, "provider_terminal_verified": False, "generation_may_resume": False}
        write_new(control / "terminal.json", terminal)
        return terminal
    summary = score_sealed(seal_root, evaluator, public, source)
    write_new(control / "terminal.json", {"status": "SCORED", "summary": summary})
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolated-worker")
    parser.add_argument("--request")
    parser.add_argument("--external-score", action="store_true")
    parser.add_argument("--seal-root")
    parser.add_argument("--evaluator-root")
    parser.add_argument("--public-path")
    parser.add_argument("--source-root")
    parser.add_argument("--terminal-record")
    parser.add_argument("--terminal-sha256")
    parser.add_argument("--seal-sha256")
    parser.add_argument("--source-manifest-sha256")
    args = parser.parse_args()
    if args.external_score:
        require(all((args.seal_root, args.evaluator_root, args.public_path, args.source_root, args.terminal_record,
                     args.terminal_sha256, args.seal_sha256, args.source_manifest_sha256)), "all external scoring paths/pins required")
        source = Path(args.source_root)
        sys.path[:0] = [str(source), str(source / "src")]
        result = score_sealed(args.seal_root, args.evaluator_root, args.public_path, source,
            external_evidence={"terminal_path": args.terminal_record, "terminal_sha256": args.terminal_sha256,
                               "seal_sha256": args.seal_sha256, "source_manifest_sha256": args.source_manifest_sha256})
        print(json.dumps(result, sort_keys=True), flush=True)
    elif args.isolated_worker:
        isolated_worker(args.isolated_worker)
    else:
        require(args.request, "launch request required")
        request = json.loads(regular(args.request).read_bytes())
        source = Path(request["source_root"])
        sys.path[:0] = [str(source), str(source / "src")]
        print(json.dumps(launch(request), sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
