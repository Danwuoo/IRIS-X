"""Post-gate, supervised preparation of the existing five offline Datasets.

Planning is pure. Real preparation is Linux-only and runs in owned children.
Runtime integrity hashes opaque bytes, including evaluator members, without
parsing their contents. Only aggregate integrity receipts leave that child.
No old scientific launch, training parser, model load or GPU call is used.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import select
import signal
import subprocess
import sys
import time
import uuid

FORMAT = "irisx/consolidated-offline-bootstrap-v1"
HELPER_PINS = {
    "arc_next_offline_bundle.py": "e8e9994de69449d0602907c87e48a3e7bc5c43ee19b9c211fb06e8845bac15bc",
    "arc_next_offline_interpreter.py": "575e503931e1780af0b703ee4caf6070a30e4f39a780169f2f5e7710f30103c9",
    "arc_next_offline_environment.py": "a678e3986e8c69acf003205cb86a66fc4efb652879ec4ab18d81f747cdc8f6b0",
    "arc_next_offline_runtime.py": "aabdd22379b0f156f0e3bc17cacbef3850d5d5cd72bf4f5359a26a07f8297eb8",
}
MODEL_HELPER_PINS = {
    "__init__.py": "f5ed985f7ed9e31ea3be113e86b11a7b44313f467c2e468a034ff789c7b85c76",
    "arc_next_models.py": "d8c3bda2ef5c557fa93756805c91ea26c5c0773d8f124914791eef13b2f0740b",
    "arc_next_index_repair.py": "05d2855e6029d873f0e74938e73d11ed7a21b72e0a630619b4415d3ebf3ac030",
}
PINS = {
    "runtime": {"reference": "danielwuu/iris-arc-next-runtime/8", "manifest_sha256": "c2e7913e8ae208deb26e06f37fcd76c79c1a87b6c49ffb3de7b2ee054fee7e67", "manifest": "bundle-manifest.json"},
    "model": {"reference": "danielwuu/iris-arc-granite42-8b-offline/2", "manifest_sha256": "cd845822cd2c0ca749dd3e6f580f51e68b91c0e5c5886fe239fc3c14f5bb0b99", "manifest": "irisx-model-material.json"},
    "wheels": {"reference": "danielwuu/iris-arc-next-cu128-cp312-wheels/1", "manifest_sha256": "2b082a3c36534b5602b8a9f738beec2c01b3d2df11b5438f1c352a84c118b052", "manifest": "wheel-lock.json"},
    "interpreter": {"reference": "danielwuu/iris-arc-next-cpython312-offline/2", "manifest_sha256": "20a52944f1ee2abf6f47a2e3beafce44951993439fede39335e660cea143495e", "manifest": "interpreter-manifest.json"},
    "adapter": {"reference": "danielwuu/iris-arc-granite42-run003-adapter-20261009/1", "manifest_sha256": "7215085857a3caacbe32302a9b6e77b4ad9524fee2a5a621c39dacb02ee2e9d0", "manifest": "adapter-manifest.json"},
}
SOURCE_LOCK_SHA256 = "8cf82737a0c6c92d0d26f3a7a268e59c55f4a4de213733777f71324930ece239"
ADAPTER_BINDING_SHA256 = "7b1cb8f8806b16ab00f05640e7d7603e596f5ed3d653b013e8ff5e859160d5cf"
MODEL_ID = "ibm-granite/granite-4.2-8b@f8de16cdcdbc6c779ca517604e050d82cc119e44"
MAX_JSON_BYTES = 1_048_576


class BootstrapError(ValueError):
    def __init__(self, message):
        super().__init__(message)
        self.bootstrap_wall_seconds = 0.0
        self.child_stop_proof = {}
        self.owned_descendants_stopped = True  # No child dispatched yet.


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _literal_path(value, *, absolute=False):
    value = os.fspath(value) if isinstance(value, os.PathLike) else value
    if (type(value) is not str or not value or len(value) > 4096
            or any(ord(c) < 32 for c in value)
            or ".." in value.replace("\\", "/").split("/")):
        raise BootstrapError("invalid explicit path")
    if absolute and (not value.startswith("/") or "\\" in value or ":" in value):
        raise BootstrapError("mount roots must be absolute Linux paths")
    return value


def plan_config(model_config, work_root):
    """Pure canonical planning; no stat, scan, imports, installation or mount read."""
    config = {} if model_config is None else model_config
    if type(config) is not dict or set(config) - {"input_root", "explicit_roots"}:
        raise BootstrapError("bootstrap configuration accepts only input_root and explicit_roots")
    overrides = config.get("explicit_roots", {})
    if type(overrides) is not dict or set(overrides) - set(PINS):
        raise BootstrapError("unknown Dataset role")
    normalized = {
        "format": FORMAT,
        "input_root": _literal_path(config.get("input_root", "/kaggle/input"), absolute=True),
        "explicit_roots": {role: None if overrides.get(role) is None else
                           _literal_path(overrides[role], absolute=True) for role in PINS},
        "work_root": _literal_path(work_root),
        "pins": json.loads(canonical(PINS)), "helper_pins": dict(HELPER_PINS),
    }
    return {"config": normalized, "plan_sha256": digest(normalized)}


def _validate_plan(plan):
    if type(plan) is not dict or set(plan) != {"config", "plan_sha256"}:
        raise BootstrapError("exact bootstrap plan envelope required")
    config = plan["config"]
    if type(config) is not dict or set(config) != {"format", "input_root", "explicit_roots", "work_root", "pins", "helper_pins"}:
        raise BootstrapError("exact normalized bootstrap config required")
    expected = plan_config({"input_root": config["input_root"],
                            "explicit_roots": config["explicit_roots"]}, config["work_root"])
    if plan != expected:
        raise BootstrapError("bootstrap plan binding changed")
    return config


def _safe(path, *, directory=False, exists=True):
    path = Path(path).absolute()
    if ".." in path.parts:
        raise BootstrapError("path traversal forbidden")
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise BootstrapError("symlink/junction path forbidden")
    if exists and not (path.is_dir() if directory else path.is_file()):
        raise BootstrapError("required local path missing")
    return path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BootstrapError("duplicate JSON key")
        result[key] = value
    return result


def _read_json(path):
    path = _safe(path)
    if path.stat().st_size > MAX_JSON_BYTES:
        raise BootstrapError("bootstrap JSON byte bound")
    return json.loads(path.read_bytes(), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(BootstrapError("nonfinite JSON")))


def _write_new(path, value):
    raw = canonical(value) + b"\n"
    if len(raw) > MAX_JSON_BYTES:
        raise BootstrapError("bootstrap JSON byte bound")
    path = _safe(path, exists=False)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return _sha(path)


def _load_verified(name, path, expected, *, package=False):
    """Import only exact trusted bytes, bypassing Python bytecode caches."""
    path = _safe(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise BootstrapError("trusted bootstrap helper hash differs: " + name)
    previous = sys.modules.get(name)
    if previous is not None:
        if Path(getattr(previous, "__file__", "")).absolute() != path:
            raise BootstrapError("conflicting trusted helper import: " + name)
        return previous
    spec = importlib.util.spec_from_file_location(name, path,
               submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    if "." in name:
        parent, child = name.rsplit(".", 1)
        setattr(sys.modules[parent], child, module)
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _helpers(*, models=False):
    root = Path(__file__).resolve().parent
    tools_root = root.parent
    _load_verified("tools", tools_root / "__init__.py", MODEL_HELPER_PINS["__init__.py"], package=True)
    result = {}
    for filename in ("arc_next_offline_bundle.py", "arc_next_offline_environment.py",
                     "arc_next_offline_interpreter.py", "arc_next_offline_runtime.py"):
        result[filename] = _load_verified("tools." + filename[:-3], root / "legacy" / filename,
                                         HELPER_PINS[filename])
    if models:
        for filename in ("arc_next_models.py", "arc_next_index_repair.py"):
            result[filename] = _load_verified("tools." + filename[:-3], tools_root / filename,
                                             MODEL_HELPER_PINS[filename])
    return result


def resolve_mounts(config):
    """Post-gate only: two exact Kaggle layouts, never recursive discovery."""
    roots = {}
    for role, pin in PINS.items():
        owner, slug, _ = pin["reference"].split("/")
        explicit = config["explicit_roots"][role]
        candidates = ([Path(explicit)] if explicit else
                      [Path(config["input_root"]) / "datasets" / owner / slug,
                       Path(config["input_root"]) / slug])
        found = [path for path in candidates if path.is_dir()]
        if len(found) != 1:
            raise BootstrapError("exactly one pinned mount required for " + role)
        roots[role] = str(_safe(found[0], directory=True))
    work = _safe(config["work_root"], directory=True)
    for root in map(Path, roots.values()):
        if work == root or work in root.parents or root in work.parents:
            raise BootstrapError("bootstrap outputs must be separate from every input")
    return roots


def _member(root, name):
    if (type(name) is not str or not name or "\\" in name or ":" in name
            or PurePosixPath(name).is_absolute()
            or any(part in {"", ".", ".."} for part in name.split("/"))):
        raise BootstrapError("unsafe bound material member")
    return _safe(Path(root).joinpath(*name.split("/")))


def _adapter(root):
    """Verify preserved adapter bytes without loading PEFT or reading task data."""
    root = Path(root)
    if _sha(_safe(root / "adapter-manifest.json")) != PINS["adapter"]["manifest_sha256"]:
        raise BootstrapError("adapter Dataset manifest differs")
    folder = _safe(root / "adapter", directory=True)
    binding_path = _safe(folder / "adapter-binding.json")
    if _sha(binding_path) != ADAPTER_BINDING_SHA256:
        raise BootstrapError("adapter binding differs")
    binding = _read_json(binding_path)
    files = binding.get("files")
    if (binding.get("model_id") != MODEL_ID
            or binding.get("material_manifest_sha256") != PINS["model"]["manifest_sha256"]
            or type(files) is not dict
            or not {"adapter_model.safetensors", "adapter_config.json"} <= set(files)):
        raise BootstrapError("adapter model/file binding incomplete")
    for name, expected in files.items():
        if type(expected) is not str or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            raise BootstrapError("invalid adapter file hash")
        if _sha(_member(folder, name)) != expected:
            raise BootstrapError("adapter bound file differs")
    actual = set()
    for path in folder.rglob("*"):
        _safe(path, directory=path.is_dir())
        if path.is_file():
            actual.add(path.relative_to(folder).as_posix())
    if actual != set(files) | {"adapter-binding.json"}:
        raise BootstrapError("adapter subtree closed inventory differs")
    config = _read_json(folder / "adapter_config.json")
    if config.get("base_model_name_or_path") != MODEL_ID.split("@")[0] or config.get("revision") != MODEL_ID.split("@")[1]:
        raise BootstrapError("adapter config base identity differs")
    return {"status": "verified-unused", "manifest_sha256": PINS["adapter"]["manifest_sha256"],
            "binding_sha256": ADAPTER_BINDING_SHA256, "bound_file_count": len(files),
            "scope": "pinned outer manifest and complete adapter binding subtree", "loaded": False}


def _material_child(plan):
    config = _validate_plan(plan)
    helpers = _helpers(models=True)
    roots = resolve_mounts(config)
    for role, root in roots.items():
        if _sha(_safe(Path(root) / PINS[role]["manifest"])) != PINS[role]["manifest_sha256"]:
            raise BootstrapError("Dataset manifest pin differs: " + role)
    # Whole runtime integrity is opaque: never invoke its training/query parsers.
    runtime = helpers["arc_next_offline_bundle.py"].verify_runtime(
        roots["runtime"], PINS["runtime"]["manifest_sha256"])
    source_lock = _safe(Path(roots["runtime"]) / "runtime/research/arc-next-line/model-source-lock.json")
    if _sha(source_lock) != SOURCE_LOCK_SHA256:
        raise BootstrapError("source environment lock differs")
    model = helpers["arc_next_models.py"].validate_material(
        roots["model"], "granite-4.2-8b", Path(roots["model"]) / "irisx-model-material.json")
    wheels = helpers["arc_next_offline_environment.py"].validate_wheelhouse(
        source_lock, roots["wheels"], check_runtime=False)
    adapter = _adapter(roots["adapter"])
    interpreter_dir = Path(config["work_root"]) / "cpython312"
    interpreter = helpers["arc_next_offline_interpreter.py"].prepare_interpreter(
        roots["interpreter"], PINS["interpreter"]["manifest_sha256"], interpreter_dir)
    receipts = {
        "runtime": {"status": "opaque-closed-inventory-verified",
                    "manifest_sha256": PINS["runtime"]["manifest_sha256"],
                    "file_count": len(runtime["files"]),
                    "total_bytes": sum(row["bytes"] for row in runtime["files"].values()),
                    "semantic_task_parsing": False},
        "model": {"status": "material-verified-not-loaded", "manifest_sha256": model["material_manifest_sha256"]},
        "wheels": {key: wheels[key] for key in ("status", "wheel_count", "wheel_lock_sha256", "source_lock_sha256")},
        "interpreter": {key: interpreter[key] for key in ("manifest_sha256", "archive_sha256", "executable_sha256", "verified_member_count")},
        "adapter": adapter,
    }
    return {"roots": roots, "interpreter": interpreter, "asset_receipts": receipts}


def _install_child(plan, material):
    config = _validate_plan(plan)
    helpers = _helpers()
    roots = material["roots"]
    # Revalidate both material bindings and the prepared interpreter after the
    # process boundary, including cached reuse. No existence-only admission.
    checked = helpers["arc_next_offline_interpreter.py"].validate_interpreter(
        roots["interpreter"], PINS["interpreter"]["manifest_sha256"],
        Path(config["work_root"]) / "cpython312")
    if Path(sys.executable).resolve() != Path(checked["python_executable"]).resolve():
        raise BootstrapError("installer must run under exact prepared CPython")
    environment = Path(config["work_root"]) / "environment-cp312-cu128"
    source_lock = _safe(Path(roots["runtime"]) / "runtime/research/arc-next-line/model-source-lock.json")
    if _sha(source_lock) != SOURCE_LOCK_SHA256:
        raise BootstrapError("source lock changed before install")
    reused = environment.exists()
    if not reused:
        helpers["arc_next_offline_environment.py"].install_offline(
            source_lock, roots["wheels"], environment, enabled=True)
    installed = helpers["arc_next_offline_runtime.py"]._runtime_environment({
        "environment_dir": str(environment), "runtime_root": roots["runtime"],
        "wheels_root": roots["wheels"], "pins": PINS})
    lock = _safe(installed["environment_lock"])
    return {"python_command": installed["python_command"],
            "environment_lock_path": str(lock), "actual_environment_lock_sha256": _sha(lock),
            "reused_environment": reused, "installed_offline": True}


def _group_members(pgid):
    """Linux session/group inventory; zombie processes are no longer executing."""
    members = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "stat").read_text()
            fields = raw[raw.rfind(")") + 2:].split()
            if int(fields[2]) == pgid or int(fields[3]) == pgid:
                members.append({"pid": int(entry.name), "birth": fields[19], "state": fields[0]})
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return members


def _process_identity(pid):
    """Bind a Linux PID to its kernel start tick, so PID reuse is not liveness."""
    if type(pid) is not int or pid <= 0:
        raise BootstrapError("positive process identity required")
    raw = (Path("/proc") / str(pid) / "stat").read_text()
    fields = raw[raw.rfind(")") + 2:].split()
    return {"pid": pid, "birth": fields[19], "state": fields[0]}


def _controller_identity():
    current = _process_identity(os.getpid())
    return {"pid": current["pid"], "birth": current["birth"]}


def _same_process(identity):
    try:
        current = _process_identity(identity["pid"])
        return current["birth"] == identity["birth"] and current["state"] != "Z"
    except (FileNotFoundError, ProcessLookupError):
        return False


def _assert_leader_birth(group, birth):
    try:
        current = _process_identity(group)
    except (FileNotFoundError, ProcessLookupError):
        return  # Leader exited; its surviving session members retain the group.
    if current["birth"] != birth:
        raise BootstrapError("bootstrap leader PID was reused; group signal refused")


def _kill_watchdog_group(group, birth):
    # The watcher deliberately survives TERM long enough to escalate. It has
    # independently confirmed that this is its own bootstrap session/group.
    if os.getpgrp() != group or os.getsid(0) != group:
        raise BootstrapError("watchdog session identity changed; group signal refused")
    _assert_leader_birth(group, birth)
    try:
        os.killpg(group, signal.SIGTERM)
        time.sleep(0.5)
    finally:
        _assert_leader_birth(group, birth)
        os.killpg(group, signal.SIGKILL)
    os._exit(124)


def _watchdog(request_path, request_sha, worker_pid, worker_birth):
    """Independent stdlib-only watchdog; never imports installers or model code."""
    request = _bound_request(request_path, request_sha)
    worker = {"pid": worker_pid, "birth": worker_birth}
    if (not sys.platform.startswith("linux") or not hasattr(os, "killpg")
            or os.getpgrp() != worker_pid or os.getsid(0) != worker_pid):
        raise BootstrapError("watchdog must share the exact owned bootstrap session")
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    _assert_leader_birth(worker_pid, worker_birth)
    print("IRISX_BOOTSTRAP_WATCHDOG_READY", flush=True)
    while True:
        try:
            alive = (_same_process(request["controller"]) and _same_process(worker)
                     and time.monotonic() < request["deadline_monotonic"])
        except BaseException:
            # An unreadable /proc identity is unknown, never permission to keep
            # installing after the parent can no longer be proved alive.
            alive = False
        if not alive:
            _kill_watchdog_group(worker_pid, worker_birth)
        time.sleep(0.05)


def _start_watchdog(request_path, request_sha, request):
    if not sys.platform.startswith("linux") or not hasattr(os, "killpg"):
        raise BootstrapError("independent Linux watchdog required")
    worker = _process_identity(os.getpid())
    if os.getpgrp() != worker["pid"] or os.getsid(0) != worker["pid"]:
        raise BootstrapError("bootstrap worker must own a fresh Linux session")
    command = [sys.executable, "-I", "-B", "-S", str(Path(__file__).absolute()),
               "--watchdog", str(request_path), request_sha,
               str(worker["pid"]), worker["birth"]]
    watcher = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               close_fds=True)
    ready = False
    end = min(request["deadline_monotonic"], time.monotonic() + 5.0)
    try:
        while time.monotonic() < end and watcher.poll() is None:
            readable, _, _ = select.select([watcher.stdout], [], [], 0.05)
            if readable:
                ready = watcher.stdout.readline(128) == b"IRISX_BOOTSTRAP_WATCHDOG_READY\n"
                break
        if not ready:
            raise BootstrapError("independent bootstrap watchdog did not acknowledge readiness")
    except BaseException:
        watcher.kill()
        watcher.wait(timeout=2)
        raise
    finally:
        watcher.stdout.close()
    # Do not terminate the watcher at normal return: it remains alive until
    # worker exit or controller group cleanup, closing the parent-death gap.
    return {"mode": "independent-parent-birth-and-monotonic-deadline",
            "pid": watcher.pid, "controller": request["controller"],
            "deadline_monotonic": request["deadline_monotonic"],
            "owned_group_id": worker["pid"], "leader_birth": worker["birth"]}


def _stop_group(process, leader_birth):
    for sig, wait_seconds in ((signal.SIGTERM, 1.0), (signal.SIGKILL, 2.0)):
        if process.poll() is None or any(row["state"] != "Z" for row in _group_members(process.pid)):
            _assert_leader_birth(process.pid, leader_birth)
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
        end = time.monotonic() + wait_seconds
        while time.monotonic() < end:
            process.poll()
            if not any(row["state"] != "Z" for row in _group_members(process.pid)):
                break
            time.sleep(0.02)
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        raise BootstrapError("bootstrap child could not be reaped")
    live = [row for row in _group_members(process.pid) if row["state"] != "Z"]
    if live:
        raise BootstrapError("bootstrap process group stop is unconfirmed")
    return {"owned_group_stopped": True, "leader_reaped": True,
            "live_group_members": 0, "pid": process.pid,
            "process_group_id": process.pid, "session_id": process.pid,
            "leader_birth": leader_birth,
            "scope": "owned Linux session/process group; not VM shutdown"}


def _supervise(command, log_path, deadline):
    if not sys.platform.startswith("linux") or not hasattr(os, "killpg"):
        raise BootstrapError("Linux process-group supervision required")
    if time.monotonic() >= deadline:
        raise BootstrapError("bootstrap deadline exhausted before dispatch")
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith(("PYTHON", "PIP_")):
            environment.pop(key)
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1",
                       PIP_NO_INDEX="1", PYTHONDONTWRITEBYTECODE="1", WANDB_MODE="offline")
    process = None
    leader_birth = None
    timed_out = False
    failure = None
    proof = {"dispatched": False, "owned_group_stopped": True, "leader_reaped": False,
             "live_group_members": 0, "scope": "no child dispatched"}
    try:
        with _safe(log_path, exists=False).open("xb") as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, env=environment,
                                       start_new_session=True, close_fds=True)
            leader_birth = _process_identity(process.pid)["birth"]
            while process.poll() is None:
                if time.monotonic() >= deadline or os.fstat(log.fileno()).st_size > MAX_JSON_BYTES:
                    timed_out = True
                    break
                time.sleep(0.02)
    except BaseException as exc:
        failure = exc
    finally:
        if process is not None:
            try:
                if leader_birth is None:
                    process.kill()
                    process.wait(timeout=2)
                    raise BootstrapError("bootstrap group birth was not recorded")
                proof = {"dispatched": True, **_stop_group(process, leader_birth)}
            except BaseException as exc:
                error = BootstrapError("bootstrap process stop is unconfirmed")
                error.child_stop_proof = {"dispatched": True, "owned_group_stopped": False,
                                          "leader_reaped": process.poll() is not None,
                                          "scope": "owned Linux session/process group"}
                error.owned_descendants_stopped = False
                raise error from exc
    if failure is not None or timed_out or process.returncode != 0:
        error = BootstrapError("bootstrap child timed out or failed; retained request/log; no automatic retry")
        error.child_stop_proof = proof
        raise error from failure
    return proof


def _dispatch(phase, plan, work, deadline, *, material=None):
    request = {"format": FORMAT, "phase": phase, "plan": plan, "material": material,
               "module_sha256": _sha(Path(__file__)),
               "controller": _controller_identity(), "deadline_monotonic": deadline}
    stem = phase + "-" + uuid.uuid4().hex
    request_path, result_path = work / (stem + ".request.json"), work / (stem + ".result.json")
    request["result_path"] = str(result_path)
    request_sha = _write_new(request_path, request)
    script = str(Path(__file__).absolute())
    arguments = [script, "--child", str(request_path), request_sha]
    if phase == "material":
        command = [sys.executable, "-I", "-B", "-S", *arguments]
    else:
        launcher = _helpers()["arc_next_offline_environment.py"]._LAUNCHER
        command = [material["interpreter"]["python_executable"], "-I", "-B", "-S", "-c", launcher, *arguments]
    proof = _supervise(command, work / (stem + ".log"), deadline)
    try:
        response = _read_json(result_path)
        if (type(response) is not dict or set(response) != {"request_sha256", "phase", "result", "watchdog"}
                or response["request_sha256"] != request_sha or response["phase"] != phase):
            raise BootstrapError("bootstrap response binding differs")
        watchdog = response["watchdog"]
        if (type(watchdog) is not dict
                or watchdog.get("mode") != "independent-parent-birth-and-monotonic-deadline"
                or watchdog.get("controller") != request["controller"]
                or watchdog.get("deadline_monotonic") != deadline
                or watchdog.get("owned_group_id") != proof.get("process_group_id")
                or watchdog.get("leader_birth") != proof.get("leader_birth")
                or type(watchdog.get("pid")) is not int or watchdog["pid"] <= 0):
            raise BootstrapError("bootstrap watchdog response binding differs")
        proof = {**proof, "watchdog": watchdog}
        _write_new(work / (stem + ".stop.json"), proof)
    except BaseException as exc:
        error = BootstrapError("bootstrap completed child has missing/invalid receipt")
        error.child_stop_proof = proof
        raise error from exc
    return response["result"], proof


def prepare_model_environment(plan, *, enable_model=False, gate_receipt=None, deadline_seconds=1800):
    """Prepare only after a production controller's explicit FULL gate.

    The caller must reserve bootstrap time before this call. No test executor,
    model backend, budget reset or install bypass is exposed by this API.
    """
    if type(enable_model) is not bool:
        raise BootstrapError("exact Boolean model switch required")
    if not enable_model:
        return {"status": "disabled", "files_written": 0, "install_calls": 0}
    if (type(gate_receipt) is not dict or gate_receipt.get("passed") is not True
            or gate_receipt.get("profile") != "FULL"
            or gate_receipt.get("gate") != "research_testability_only"):
        raise BootstrapError("verified FULL base testability gate required before bootstrap")
    config = _validate_plan(plan)
    if type(deadline_seconds) not in (int, float) or not math.isfinite(deadline_seconds) or not 0 < deadline_seconds <= 14400:
        raise BootstrapError("bounded finite bootstrap deadline required")
    if not sys.platform.startswith("linux") or not hasattr(os, "killpg"):
        raise BootstrapError("offline bootstrap requires Linux; no platform fallback")
    started = time.monotonic()
    deadline = started + deadline_seconds
    stops = {phase: {"dispatched": False, "owned_group_stopped": True,
                     "leader_reaped": False, "live_group_members": 0,
                     "scope": "no child dispatched"} for phase in ("material", "install")}
    phase = "material"
    try:
        work = _safe(config["work_root"], exists=False)
        work.mkdir(parents=True, exist_ok=True)
        _safe(work, directory=True)
        material, stops["material"] = _dispatch("material", plan, work, deadline)
        phase = "install"
        installed, stops["install"] = _dispatch("install", plan, work, deadline, material=material)
        roots = material["roots"]
        result = {"status": "prepared", **installed,
                  "source_root": str(Path(__file__).resolve().parents[2]),
                  "model_path": roots["model"],
                  "manifest_path": str(Path(roots["model"]) / "irisx-model-material.json"),
                  "runtime_manifest_path": str(Path(roots["runtime"]) / "bundle-manifest.json"),
                  "environment_plan_sha256": plan["plan_sha256"],
                  "asset_receipts": material["asset_receipts"],
                  "bootstrap_wall_seconds": time.monotonic() - started,
                  "child_stop_proof": stops,
                  "gpu_calls": 0, "training_calls": 0}
    except BaseException as exc:
        error = BootstrapError("offline bootstrap failed during " + phase + "; retained evidence; no automatic retry")
        if getattr(exc, "child_stop_proof", None):
            stops[phase] = exc.child_stop_proof
        error.child_stop_proof = stops
        error.owned_descendants_stopped = all(
            proof.get("owned_group_stopped") is True
            and proof.get("live_group_members") == 0
            and (proof.get("dispatched") is False or proof.get("leader_reaped") is True)
            for proof in stops.values())
        error.bootstrap_wall_seconds = time.monotonic() - started
        raise error from exc
    return result


def _bound_request(request_path, request_sha):
    if _sha(_safe(request_path)) != request_sha:
        raise BootstrapError("bootstrap request bytes changed")
    request = _read_json(request_path)
    if (type(request) is not dict or set(request) != {"format", "phase", "plan", "material",
            "module_sha256", "result_path", "controller", "deadline_monotonic"}
            or request["format"] != FORMAT):
        raise BootstrapError("invalid bootstrap child request")
    if request["module_sha256"] != _sha(Path(__file__)):
        raise BootstrapError("bootstrap child source changed")
    controller = request["controller"]
    if (type(controller) is not dict or set(controller) != {"pid", "birth"}
            or type(controller["pid"]) is not int or controller["pid"] <= 0
            or type(controller["birth"]) is not str or not controller["birth"].isdigit()
            or type(request["deadline_monotonic"]) not in (int, float)
            or not math.isfinite(request["deadline_monotonic"])):
        raise BootstrapError("bound controller identity and monotonic deadline required")
    return request


def _child(request_path, request_sha):
    request = _bound_request(request_path, request_sha)
    config = _validate_plan(request["plan"])
    result_path = _safe(request["result_path"], exists=False)
    if result_path.parent != _safe(config["work_root"], directory=True):
        raise BootstrapError("child response escaped bootstrap work root")
    watchdog = _start_watchdog(request_path, request_sha, request)
    if request["phase"] == "material" and request["material"] is None:
        result = _material_child(request["plan"])
    elif request["phase"] == "install" and type(request["material"]) is dict:
        result = _install_child(request["plan"], request["material"])
    else:
        raise BootstrapError("invalid bootstrap phase")
    _write_new(result_path, {"request_sha256": request_sha, "phase": request["phase"],
                             "result": result, "watchdog": watchdog})


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--child":
        _child(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 6 and sys.argv[1] == "--watchdog":
        _watchdog(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    else:
        raise SystemExit("Internal bootstrap child requires exact request and hash")
