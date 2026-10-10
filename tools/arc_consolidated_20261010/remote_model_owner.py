"""One prepared-interpreter model process with bounded, sequential local IPC.

The caller is the sole ledger writer and reserves before dispatch. The protocol
has no execution/source-upload action. Only hash-verified repository modules are
imported in the child; generated model text remains response data.
"""
from __future__ import annotations

from dataclasses import asdict, fields, replace
import hashlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import queue
import signal
import struct
import subprocess
import sys
import threading
import time
import uuid

PROTOCOL = "irisx/remote-model-owner-v1"
MAX_FRAME_BYTES = 4 * 1024 * 1024
MAX_LOG_BYTES = 1024 * 1024
BOOTSTRAP_KEYS = frozenset({"python_command", "source_root", "model_path", "manifest_path",
    "environment_lock_path", "actual_environment_lock_sha256", "admission_path", "admission_sha256"})
ENTRY = "tools/arc_consolidated_20261010/remote_model_owner.py"


class RemoteOwnerError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise RemoteOwnerError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _hash(value):
    _require(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value),
             "exact SHA-256 required")
    return value


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(RemoteOwnerError("nonfinite JSON")))
    _canonical(value)
    return value


def _safe(path):
    path = Path(path)
    _require(path.is_absolute(), "absolute path required")
    for item in (path, *path.parents):
        _require(not item.is_symlink() and not (hasattr(item, "is_junction") and item.is_junction()),
                 "symlink/junction not admitted")
    return path


def _read_bound(path, expected, limit=MAX_FRAME_BYTES):
    path = _safe(path)
    _require(path.is_file() and path.stat().st_size <= limit, "missing or oversized bound file")
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == _hash(expected), "bound file changed: " + path.name)
    return raw


def _identity(pid):
    if os.name != "posix":
        return None
    try:
        raw = (Path("/proc") / str(pid) / "stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return None
    rest = raw[raw.rfind(")") + 2:].split()
    return {"pid": pid, "state": rest[0], "ppid": int(rest[1]), "group": int(rest[2]),
            "session": int(rest[3]), "birth": int(rest[19])}


def _same_process(observed, expected):
    return (type(observed) is dict and type(expected) is dict and
            all(type(value.get(key)) is int for value in (observed, expected) for key in ("pid", "birth")) and
            observed["pid"] == expected["pid"] and observed["birth"] == expected["birth"])


def _verify_source(root, identity):
    root = _safe(root)
    _require(type(identity) is dict and ENTRY in identity and len(identity) <= 512,
             "closed executable source identity required")
    verified = {}
    for name, expected in identity.items():
        _require(type(name) is str and name.startswith("tools/") and "\\" not in name and
                 ":" not in name and not PurePosixPath(name).is_absolute() and
                 all(p not in ("", ".", "..") for p in name.split("/")) and
                 name.endswith((".py", ".json")), "unsafe source member")
        verified[name] = _read_bound(root / name, expected)
    return verified


def _admission(bootstrap, plan_hash, source_identity, *, synthetic=False):
    _require(type(bootstrap) is dict and set(bootstrap) == BOOTSTRAP_KEYS, "exact bootstrap fields required")
    _hash(plan_hash)
    _hash(bootstrap["actual_environment_lock_sha256"])
    command = bootstrap["python_command"]
    _require(type(command) is list and all(type(v) is str and v for v in command), "fixed command required")
    _require(len(command) == (4 if synthetic else 5) and command[1:4] == ["-I", "-B", "-S"],
             "prepared interpreter command differs")
    for key in ("source_root", "model_path", "manifest_path", "environment_lock_path", "admission_path"):
        _safe(bootstrap[key])
    _safe(command[0])
    if not synthetic:
        _require(os.name == "posix" and Path("/proc/self/stat").is_file(),
                 "production process ownership requires Linux /proc")
        _safe(command[4])
    receipt = _json(_read_bound(bootstrap["admission_path"], bootstrap["admission_sha256"]))
    expected = {k: v for k, v in bootstrap.items() if k not in ("admission_path", "admission_sha256")}
    _require(type(receipt) is dict and set(receipt) == {"format", "environment_plan_sha256",
             "source_identity_sha256", "prepared", "asset_receipts_sha256"}, "runtime admission schema differs")
    _hash(receipt["asset_receipts_sha256"])
    _require(receipt["format"] == "irisx/consolidated-runtime-admission-v2" and
             receipt["environment_plan_sha256"] == plan_hash and
             receipt["source_identity_sha256"] == _digest(source_identity) and
             receipt["prepared"] == expected, "immutable runtime admission does not bind this owner")
    lock = _json(_read_bound(bootstrap["environment_lock_path"], bootstrap["actual_environment_lock_sha256"]))
    if not synthetic:
        _require(lock.get("python_command") == command and lock.get("environment_lock") == bootstrap["environment_lock_path"],
                 "actual installed environment command differs")
        for path_key, hash_key in (("python_executable", "python_executable_sha256"),
                                   ("python_launcher_path", "python_launcher_sha256"),
                                   ("network_guard_path", "network_guard_sha256"),
                                   ("network_guard_startup_hook_path", "network_guard_startup_hook_sha256")):
            _read_bound(lock[path_key], lock[hash_key], 128 * 1024 * 1024)
        _require(lock["python_executable"] == command[0] and lock["python_launcher_path"] == command[4],
                 "command is not the installed guarded interpreter")
    return _verify_source(bootstrap["source_root"], source_identity)


def _mp():
    from tools.arc_consolidated_20261010 import model_provider
    return model_provider


def _request(data):
    mp = _mp()
    _require(type(data) is dict and set(data) == {f.name for f in fields(mp.ModelRequest)}, "request schema differs")
    _require(type(data["spec"]) is dict and set(data["spec"]) == {f.name for f in fields(mp.CallSpec)}, "call schema differs")
    _require(type(data["sampling"]) is dict and set(data["sampling"]) == {f.name for f in fields(mp.Sampling)}, "sampling schema differs")
    spec = dict(data["spec"])
    _require(type(spec["attribution_arms"]) is list and all(type(a) is str for a in spec["attribution_arms"]),
             "attribution arms must be a JSON array")
    spec["attribution_arms"] = tuple(spec["attribution_arms"])
    for key in ("call_id", "task_id", "stage", "arm", "root_id"):
        _require(type(spec[key]) is str and 0 < len(spec[key]) <= 240, "invalid call field")
    mp._integer(spec["seed"], 0, 2**31 - 1)
    _require(spec["stage"] in ("root", "feedback", "memory"), "unknown stage")
    for key in ("plan_sha256", "task_sha256", "model_sha256", "environment_sha256"):
        _hash(data[key])
    _require(type(data["messages_json"]) is str and len(data["messages_json"].encode()) <= 256 * 1024,
             "bounded prompt required")
    messages = _json(data["messages_json"])
    _require(type(messages) is list and len(messages) == 2 and
             all(type(m) is dict and set(m) == {"role", "content"} and type(m["content"]) is str for m in messages) and
             [m["role"] for m in messages] == ["system", "user"] and messages[0]["content"] == mp.SYSTEM_PROMPT,
             "typed prompt schema differs")
    payload = _json(messages[1]["content"])
    mp.reject_forbidden_keys(payload)
    _require(type(payload) is dict and set(payload) == {"format", "task", "grammar", "action", "parent", "history", "feedback", "memory"},
             "typed prompt payload differs")
    task = mp.validate_demos_task(payload["task"])
    _require(mp.digest(task) == data["task_sha256"] and task["task_id"] == spec["task_id"], "task binding differs")
    return mp.ModelRequest(**{**data, "spec": mp.CallSpec(**spec), "sampling": mp.Sampling(**data["sampling"])})


def _prepared(data):
    mp = _mp()
    _require(type(data) is dict and set(data) == {"request", "input_token_ids"}, "prepared schema differs")
    request = _request(data["request"])
    ids = data["input_token_ids"]
    _require(type(ids) is list and 0 < len(ids) <= request.sampling.max_prompt_tokens and
             all(type(t) is int and 0 <= t < 100352 for t in ids), "invalid admitted tokens")
    return mp.PreparedCall(request, tuple(ids))


def _write_frame(stream, value):
    raw = _canonical(value)
    _require(0 < len(raw) <= MAX_FRAME_BYTES, "IPC frame exceeds limit")
    framed = memoryview(struct.pack("!I", len(raw)) + raw)
    while framed:
        written = stream.write(framed)
        if type(written) is not int or written <= 0:
            raise OSError("model IPC write did not make progress")
        framed = framed[written:]
    stream.flush()


def _read_exact(stream, count):
    chunks = bytearray()
    while len(chunks) < count:
        block = stream.read(count - len(chunks))
        if not block:
            raise EOFError("model IPC closed before a complete frame")
        chunks.extend(block)
    return bytes(chunks)


def _read_frame(stream):
    length = struct.unpack("!I", _read_exact(stream, 4))[0]
    _require(0 < length <= MAX_FRAME_BYTES, "invalid IPC frame length")
    return _json(_read_exact(stream, length))


class RemoteModelOwner:
    """Production proxy; construction is inert until explicitly initialized.

    Every receipt distinguishes the planned environment identity from the
    independently admitted actual environment-lock bytes. No public test backend
    or command override is available beyond the immutable bootstrap admission.
    """

    def __init__(self, prepared_bootstrap, *, environment_plan_sha256, source_identity,
                 deadline_monotonic, enabled=False):
        self._configure(prepared_bootstrap, environment_plan_sha256, source_identity,
                        deadline_monotonic, enabled, synthetic=False, faults={})

    @classmethod
    def _synthetic_for_tests(cls, prepared_bootstrap, *, environment_plan_sha256,
                             source_identity, deadline_monotonic, faults=None):
        owner = cls.__new__(cls)
        owner._configure(prepared_bootstrap, environment_plan_sha256, source_identity,
                         deadline_monotonic, True, synthetic=True, faults=faults or {})
        return owner

    def _configure(self, bootstrap, plan_hash, source_identity, deadline, enabled, *, synthetic, faults):
        _require(type(enabled) is bool, "explicit Boolean enable required")
        _require(type(deadline) in (int, float) and math.isfinite(deadline) and deadline > time.monotonic(),
                 "fresh current-session owner deadline required")
        _hash(plan_hash)
        self.enabled, self.deadline = enabled, float(deadline)
        self._initialization_deadline = min(self.deadline, time.monotonic() + 1200)
        self.bootstrap = _json(_canonical(bootstrap))
        self.source_identity = _json(_canonical(source_identity))
        self.environment_sha256 = plan_hash
        self.actual_environment_lock_sha256 = bootstrap["actual_environment_lock_sha256"]
        self.model_sha256 = _mp().MODEL_MANIFEST_SHA256
        self.synthetic, self.faults = synthetic, _json(_canonical(faults))
        self.execution_mode = "synthetic-test" if synthetic else "g4"
        self._process = None
        self._owned = {}
        self._started = self._closed = self._broken = False
        self._tokenizer_ready = self._model_ready = False
        self._tokenizer_attempted = self._load_attempted = False
        self._nonce, self._sequence = uuid.uuid4().hex, 0
        self._responses = queue.Queue(maxsize=1)
        self._io_stopping = threading.Event()
        self._io_threads = []
        self._rpc_lock = threading.Lock()
        self._prepared, self._attempted = {}, set()
        self._excluded = set()
        self._stop_evidence = None
        self.load_seconds = self.model_seconds = self.tokenization_seconds = 0.0
        self.tokenizer_load_seconds = self.owner_start_seconds = 0.0
        self.load_count = self.tokenizer_load_count = 0
        self._log_bytes = 0
        self._request_path = None

    def set_initialization_deadline(self, deadline_monotonic):
        """Narrow the phase to the caller's already reserved durable allowance."""
        _require(not self._tokenizer_attempted and not self._started,
                 "initialization deadline must precede initialization")
        _require(type(deadline_monotonic) in (int, float) and math.isfinite(deadline_monotonic) and
                 time.monotonic() < deadline_monotonic <= self.deadline,
                 "invalid initialization deadline")
        self._initialization_deadline = min(self._initialization_deadline, deadline_monotonic)

    def _phase_deadline(self):
        return self.deadline if self._model_ready else min(self.deadline, self._initialization_deadline)

    def _live(self):
        if self._process is None:
            return []
        if os.name != "posix":
            return [] if self._process.poll() is not None else [{"pid": self._process.pid, "birth": None}]
        observed = {}
        for path in Path("/proc").iterdir():
            if path.name.isdecimal():
                identity = _identity(int(path.name))
                if identity:
                    observed[identity["pid"]] = identity
        for item in observed.values():
            if item["session"] == self._process.pid:
                self._owned[(item["pid"], item["birth"])] = item
        changed = True
        while changed:
            changed = False
            parents = {pid for pid, birth in self._owned if pid in observed and observed[pid]["birth"] == birth}
            for item in observed.values():
                key = item["pid"], item["birth"]
                if item["ppid"] in parents and key not in self._owned:
                    self._owned[key] = item
                    changed = True
        return [v for v in observed.values() if (v["pid"], v["birth"]) in self._owned and v["state"] not in ("Z", "X")]

    def _stop(self, *, forced):
        process = self._process
        if process is None:
            return {"process_stopped": True, "owned_descendants": [], "forced": forced}
        live = self._live()
        for sig, grace in ((signal.SIGTERM, 1.0), (getattr(signal, "SIGKILL", signal.SIGTERM), 2.0)):
            if not live:
                break
            for item in live:
                if os.name == "posix":
                    current = _identity(item["pid"])
                    if current is None or current["birth"] != item["birth"]:
                        continue
                    try:
                        os.kill(item["pid"], sig)
                    except ProcessLookupError:
                        pass
                elif self.synthetic:
                    process.kill()
            until = time.monotonic() + grace
            while time.monotonic() < until:
                process.poll()
                live = self._live()
                if not live:
                    break
                time.sleep(0.03)
        _require(not live, "owned model descendants remain live; global seal prohibited")
        process.wait(timeout=1)
        self._io_stopping.set()
        for thread in self._io_threads:
            thread.join(timeout=2)
        _require(not any(thread.is_alive() for thread in self._io_threads),
                 "owned IPC threads remain active; global seal prohibited")
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()
        self._stop_evidence = {"process_stopped": True, "worker_pid": process.pid,
                              "returncode": process.returncode, "owned_descendants": [],
                              "observed_process_identities": list(self._owned.values()), "forced": forced,
                              "owned_io_threads_stopped": True,
                              "scope": "linux-owned-process-tree" if os.name == "posix" else "synthetic-child-only"}
        return self._stop_evidence

    def _start(self):
        _require(self.enabled and not self._closed and not self._broken, "remote owner disabled or stopped")
        if self._started:
            return
        self._started = True
        began = time.monotonic()
        try:
            _admission(self.bootstrap, self.environment_sha256, self.source_identity, synthetic=self.synthetic)
            parent = _identity(os.getpid())
            directory = _safe(Path(self.bootstrap["admission_path"]).parent) / ("model-owner-" + self._nonce)
            directory.mkdir()
            request = {"protocol": PROTOCOL, "bootstrap": self.bootstrap,
                       "environment_plan_sha256": self.environment_sha256,
                       "source_identity": self.source_identity, "nonce": self._nonce,
                       "evidence_mode": "synthetic-test-only" if self.synthetic else "production",
                       "parent_identity": parent, "parent_pid": os.getpid(),
                       "deadline_monotonic": self.deadline,
                       "remaining_seconds": max(0, self.deadline - time.monotonic()), "faults": self.faults}
            _require(request["remaining_seconds"] > 0, "owner session deadline expired before process start")
            self._request_path = directory / "request.json"
            with self._request_path.open("xb") as stream:
                stream.write(_canonical(request)); stream.flush(); os.fsync(stream.fileno())
            if os.name == "posix":
                fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            command = [*self.bootstrap["python_command"], str(Path(self.bootstrap["source_root"]) / ENTRY),
                       "--owner-worker", str(self._request_path), _digest(request)]
            env = dict(os.environ)
            for key in list(env):
                if key.startswith(("PYTHON", "PIP_")):
                    env.pop(key)
            env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1",
                       PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED="0", WANDB_MODE="offline")
            self._process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, cwd=self.bootstrap["source_root"], env=env, bufsize=0,
                start_new_session=os.name == "posix")
            self._live()

            def receive():
                try:
                    while not self._io_stopping.is_set():
                        value = _read_frame(self._process.stdout)
                        try:
                            self._responses.put_nowait((True, value))
                        except queue.Full:
                            self._io_stopping.set()
                            return
                except BaseException as exc:
                    try:
                        self._responses.put_nowait((False, exc))
                    except queue.Full:
                        pass

            def log():
                with (directory / "worker.log").open("xb") as stream:
                    try:
                        while True:
                            data = self._process.stderr.read(8192)
                            if not data:
                                break
                            allowed = min(len(data), MAX_LOG_BYTES - self._log_bytes)
                            if allowed > 0:
                                stream.write(data[:allowed]); stream.flush()
                                self._log_bytes += allowed
                    except (OSError, ValueError):
                        pass
                    stream.flush(); os.fsync(stream.fileno())

            for target in (receive, log):
                thread = threading.Thread(target=target, daemon=True)
                self._io_threads.append(thread)
                thread.start()
        except BaseException:
            self._broken = True
            if self._process is not None:
                self._stop(forced=True)
            raise
        finally:
            self.owner_start_seconds += time.monotonic() - began

    def _rpc(self, action, payload, deadline):
        _require(self._rpc_lock.acquire(blocking=False), "concurrent IPC operation prohibited")
        try:
            self._start()
            deadline = min(deadline, self.deadline)
            _require(deadline > time.monotonic(), "owner deadline exhausted")
            self._sequence += 1
            request = {"protocol": PROTOCOL, "nonce": self._nonce, "sequence": self._sequence,
                       "action": action, "payload": payload}
            envelope = {**request, "request_sha256": _digest(request)}
            result = []

            def send():
                try:
                    _write_frame(self._process.stdin, envelope)
                    result.append(None)
                except BaseException as exc:
                    result.append(exc)

            writer = threading.Thread(target=send, daemon=True)
            self._io_threads.append(writer)
            writer.start()
            while writer.is_alive():
                self._live()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("model IPC send deadline")
                writer.join(min(0.05, remaining))
            if result and result[0] is not None:
                raise result[0]
            while True:
                self._live()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("model IPC response deadline")
                try:
                    ok, response = self._responses.get(timeout=min(0.05, remaining))
                    break
                except queue.Empty:
                    continue
            if not ok:
                raise response
            _require(type(response) is dict and set(response) == {"protocol", "nonce", "sequence", "request_sha256", "ok", "payload"},
                     "IPC response schema differs")
            _require(response["protocol"] == PROTOCOL and response["nonce"] == self._nonce and
                     type(response["sequence"]) is int and response["sequence"] == self._sequence and
                     response["request_sha256"] == envelope["request_sha256"] and
                     type(response["ok"]) is bool, "IPC response identity differs")
            if not response["ok"]:
                error = response["payload"]
                if error.get("type") == "TokenAdmissionError":
                    raise _mp().TokenAdmissionError(error["observed"], error["limit"])
                raise _mp().ModelContractError("remote " + str(error.get("type", "error")) + ": " + str(error.get("message", ""))[:600])
            return response["payload"]
        except (EOFError, OSError, TimeoutError, RemoteOwnerError):
            self._broken = True
            self._stop(forced=True)
            raise
        finally:
            self._rpc_lock.release()

    def initialize_tokenizer(self):
        if self._tokenizer_ready:
            return {"tokenizer_initialized": True, "model_loaded": self._model_ready,
                    "execution_mode": self.execution_mode}
        _require(not self._tokenizer_attempted, "no automatic tokenizer initialization retry")
        self._tokenizer_attempted = True
        self.tokenizer_load_count += 1
        began = time.monotonic()
        try:
            result = self._rpc("TOKENIZER_INIT", {}, self._initialization_deadline)
            _require(result.get("tokenizer_initialized") is True and result.get("model_loaded") is False,
                     "tokenizer-only initialization acknowledgement differs")
            self._tokenizer_ready = True
            return result
        finally:
            self.tokenizer_load_seconds += time.monotonic() - began

    def ensure_model_loaded(self):
        self.initialize_tokenizer()
        if self._model_ready:
            return {"model_loaded": True, "load_count": self.load_count, "load_seconds": self.load_seconds}
        _require(not self._load_attempted, "no automatic model-load retry")
        self._load_attempted = True
        self.load_count += 1
        began = time.monotonic()
        try:
            result = self._rpc("LOAD_MODEL", {}, self._initialization_deadline)
            _require(result.get("model_loaded") is True, "model load not acknowledged")
            self._model_ready = True
            return result
        finally:
            self.load_seconds += time.monotonic() - began

    def _check_request(self, request):
        decoded = _request(_json(_canonical(asdict(request))))
        _require(decoded == request and request.environment_sha256 == self.environment_sha256 and
                 request.model_sha256 == self.model_sha256, "external request plan/model binding differs")

    def prepare(self, request, *, register=True):
        _require(type(register) is bool, "register must be Boolean")
        self._check_request(request)
        self.initialize_tokenizer()
        began = time.monotonic()
        try:
            data = self._rpc("PREPARE", {"request": asdict(request), "register": register}, self._phase_deadline())
            item = _prepared(data)
            _require(item.request == request, "worker changed the external request")
            if register:
                self._prepared[request.spec.call_id] = item.sha256
            return item
        finally:
            self.tokenization_seconds += time.monotonic() - began

    def prepare_group(self, requests):
        _require(type(requests) is list and 0 < len(requests) <= 16, "bounded request group required")
        for request in requests:
            self._check_request(request)
        self.initialize_tokenizer()
        began = time.monotonic()
        try:
            result = self._rpc("PREPARE_GROUP", {"requests": [asdict(r) for r in requests]}, self._phase_deadline())
            _require(type(result) is dict and set(result) == {"prepared", "receipt"}, "group result differs")
            prepared = tuple(_prepared(value) for value in result["prepared"])
            _require([p.request for p in prepared] in ([], requests), "partial or reordered admitted group")
            receipt = result["receipt"]
            _require(type(receipt.get("denominator")) is int and type(receipt.get("admitted")) is int and
                     receipt.get("denominator") == len(requests) and receipt.get("admitted") == len(prepared),
                     "group admission denominator differs")
            for item in prepared:
                self._prepared[item.request.spec.call_id] = item.sha256
            if not prepared:
                self._excluded.update(request.spec.call_id for request in requests)
            return prepared, receipt
        finally:
            self.tokenization_seconds += time.monotonic() - began

    def dispatch(self, prepared, *, deadline_monotonic):
        mp = _mp()
        self._check_request(prepared.request)
        _require(self._model_ready and not self._closed and not self._broken,
                 "explicit separately accounted model load required before dispatch")
        _require(type(deadline_monotonic) in (int, float) and math.isfinite(deadline_monotonic) and
                 0 < deadline_monotonic - time.monotonic() <= mp.MAX_MODEL_SECONDS,
                 "invalid model deadline")
        ident = prepared.request.spec.call_id
        _require(self._prepared.get(ident) == prepared.sha256 and ident not in self._attempted and
                 ident not in self._excluded and len(self._attempted) < mp.MAX_CALLS,
                 "unprepared, changed or previously attempted call")
        self._attempted.add(ident)
        # Windows CPython 3.12 monotonic() can have coarse tick resolution.
        # Keep deadlines on that clock but measure even very short failed IPC
        # dispatches with the high-resolution performance counter.
        began = time.perf_counter()
        try:
            result = self._rpc("GENERATE", {"call_id": ident, "prepared_sha256": prepared.sha256,
                "remaining_seconds": min(mp.MAX_MODEL_SECONDS, deadline_monotonic - time.monotonic())}, deadline_monotonic)
            actual = replace(prepared, request=replace(prepared.request, environment_sha256=self.actual_environment_lock_sha256))
            expected = {"request_sha256": actual.sha256, "cache_sha256": actual.cache_sha256,
                        "external_request_sha256": prepared.sha256, "external_cache_sha256": prepared.cache_sha256,
                        "model_sha256": self.model_sha256, "environment_sha256": self.actual_environment_lock_sha256,
                        "environment_plan_sha256": self.environment_sha256,
                        "actual_environment_lock_sha256": self.actual_environment_lock_sha256}
            _require(type(result) is dict and all(result.get(k) == v for k, v in expected.items()), "worker model/environment/cache binding differs")
            mp._integer(result.get("prompt_tokens"), prepared.prompt_tokens, prepared.prompt_tokens)
            count = mp._integer(result.get("output_tokens"), 0, prepared.request.sampling.max_output_tokens)
            _require(type(result.get("output_token_ids")) is list and len(result["output_token_ids"]) == count and
                     all(type(t) is int and 0 <= t < 100352 for t in result["output_token_ids"]), "worker token usage differs")
            _require(type(result.get("text")) is str and len(result["text"].encode()) <= 131072 and
                     result.get("call_id") == ident and
                     result.get("attribution_arms") == list(prepared.request.spec.attribution_arms) and
                     type(result.get("late")) is bool and type(result.get("truncated")) is bool and
                     result["truncated"] == (result.get("finish_reason") in ("length", "wall")) and
                     result.get("finish_reason") in ("stop", "length", "wall") and
                     type(result.get("model_seconds")) in (int, float) and math.isfinite(result["model_seconds"]) and result["model_seconds"] >= 0,
                     "invalid worker response")
            return {**result, "actual_request_sha256": actual.sha256, "actual_cache_sha256": actual.cache_sha256,
                    "request_sha256": prepared.sha256, "cache_sha256": prepared.cache_sha256,
                    "environment_sha256": self.environment_sha256, "environment_binding_kind": "environment-plan",
                    "worker_model_seconds": result["model_seconds"], "model_seconds": time.perf_counter() - began}
        finally:
            # Includes failed RPC dispatches. Callers conservatively charge these
            # deltas even when no bounded response could be validated.
            self.model_seconds += time.perf_counter() - began

    def accounting(self):
        return {"physical_calls_attempted": len(self._attempted), "load_count": self.load_count,
                "load_seconds": self.load_seconds, "model_seconds": self.model_seconds,
                "tokenization_seconds": self.tokenization_seconds, "tokenizer_load_count": self.tokenizer_load_count,
                "tokenizer_load_seconds": self.tokenizer_load_seconds, "owner_start_seconds": self.owner_start_seconds,
                "install_seconds": 0.0, "installation_performed": False, "execution_mode": self.execution_mode,
                "environment_plan_sha256": self.environment_sha256,
                "actual_environment_lock_sha256": self.actual_environment_lock_sha256,
                "model_owner_stopped": self._closed, "vm_billing_stopped": False}

    def close(self):
        acknowledgement = None
        if self._closed:
            return self._close_receipt
        if self._process is not None and not self._broken and self._process.poll() is None:
            try:
                acknowledgement = self._rpc("CLOSE", {}, min(self.deadline, time.monotonic() + 30))
                _require(acknowledgement.get("model_owner_stopped") is True, "child release was not acknowledged")
                until = min(self.deadline, time.monotonic() + 5)
                while time.monotonic() < until and self._process.poll() is None:
                    self._live(); time.sleep(0.03)
            except BaseException:
                self._broken = True
        stopped = self._stop(forced=self._broken or bool(self._live()))
        self._closed = True
        self._close_receipt = {"model_owner_stopped": True, "model_released": True,
            "owned_descendants_stopped": True, "owned_descendants": [], "process_evidence": stopped,
            "child_acknowledgement": acknowledgement, "execution_mode": self.execution_mode,
            "environment_plan_sha256": self.environment_sha256,
            "actual_environment_lock_sha256": self.actual_environment_lock_sha256,
            "vm_billing_stopped": False}
        return self._close_receipt


class _PinnedLoader(importlib.abc.Loader):
    def __init__(self, raw, path):
        self.raw, self.path = raw, path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        # Only already hash-verified repository source reaches this loader.
        exec(compile(self.raw, str(self.path), "exec"), module.__dict__)


class _PinnedFinder(importlib.abc.MetaPathFinder):
    def __init__(self, root, verified):
        self.root, self.verified = Path(root), verified

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "tools" and not fullname.startswith("tools."):
            return None
        relative = fullname.replace(".", "/")
        for name, package in ((relative + "/__init__.py", True), (relative + ".py", False)):
            if name in self.verified:
                return importlib.util.spec_from_file_location(fullname, self.root / name,
                    loader=_PinnedLoader(self.verified[name], self.root / name),
                    submodule_search_locations=[str(self.root / relative)] if package else None)
        if any(name.startswith(relative + "/") for name in self.verified):
            spec = importlib.util.spec_from_loader(fullname, loader=None, is_package=True)
            spec.submodule_search_locations = []
            return spec
        raise ModuleNotFoundError("module outside verified source inventory: " + fullname)


class _SyntheticBackend:
    """Fixed private process-test backend; no arbitrary injectable code."""
    def __init__(self, faults):
        allowed = {"delay_generate_seconds", "delay_load_seconds", "crash_generate", "bad_counter", "fail_load", "grandchild"}
        _require(type(faults) is dict and set(faults) <= allowed, "unknown synthetic fault")
        self.faults, self.loaded, self.grandchild = faults, False, None

    def encode(self, messages):
        return list(_canonical(messages))

    def ensure_model_loaded(self):
        delay = self.faults.get("delay_load_seconds", 0)
        _require(type(delay) in (int, float) and math.isfinite(delay) and 0 <= delay <= 10, "invalid synthetic delay")
        time.sleep(delay)
        if self.faults.get("fail_load"):
            raise RuntimeError("synthetic partial load failure")
        self.loaded = True

    def generate(self, prepared, *, deadline_monotonic):
        if self.faults.get("grandchild") and self.grandchild is None:
            self.grandchild = subprocess.Popen([sys.executable, "-I", "-B", "-S", __file__, "--synthetic-sleeper"])
        delay = self.faults.get("delay_generate_seconds", 0)
        _require(type(delay) in (int, float) and math.isfinite(delay) and 0 <= delay <= 10, "invalid synthetic delay")
        time.sleep(delay)
        if self.faults.get("crash_generate"):
            os._exit(79)
        result = {"request_sha256": prepared.sha256, "model_sha256": prepared.request.model_sha256,
            "environment_sha256": prepared.request.environment_sha256, "text": '{"steps":[{"op":"identity"}]}',
            "prompt_tokens": prepared.prompt_tokens, "output_tokens": 1, "output_token_ids": [42], "finish_reason": "stop"}
        if self.faults.get("bad_counter"):
            result["output_tokens"] = True
        return result

    def close(self):
        # Deliberately do not reap a fault-injected grandchild: the outer owner
        # must establish process-tree stop instead of trusting this assertion.
        return {"model_released": True, "descendants_stopped": True, "owned_descendants": []}


def _worker(request_path, request_hash):
    # Separate the protocol handles from stdin/stdout used by third-party code.
    incoming = os.fdopen(os.dup(0), "rb", buffering=0)
    outgoing = os.fdopen(os.dup(1), "wb", buffering=0)
    with open(os.devnull, "rb") as empty:
        os.dup2(empty.fileno(), 0)
    os.dup2(2, 1)
    sys.stdin, sys.stdout = open(os.devnull), sys.stderr
    config = _json(_read_bound(request_path, request_hash))
    _require(config["protocol"] == PROTOCOL and config["evidence_mode"] in ("production", "synthetic-test-only"), "worker identity differs")
    synthetic = config["evidence_mode"] == "synthetic-test-only"
    if os.name == "posix":
        _require(os.getsid(0) == os.getpid(), "worker must own a new Linux session")
        import ctypes
        _require(ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) == 0,
                 "parent-death stop could not be established")
        _require(os.getppid() == config["parent_pid"] and _same_process(_identity(os.getppid()), config["parent_identity"]),
                 "parent identity changed before worker admission")
    else:
        _require(synthetic and os.getppid() == config["parent_pid"], "non-Linux production forbidden")
    remaining = config["remaining_seconds"]
    _require(type(remaining) in (int, float) and math.isfinite(remaining) and 0 < remaining <= 14400,
             "invalid worker session allowance")
    deadline = config["deadline_monotonic"]
    _require(type(deadline) in (int, float) and math.isfinite(deadline), "invalid worker deadline")
    deadline = min(deadline, time.monotonic() + remaining)
    _require(deadline > time.monotonic(), "worker deadline expired before admission")
    watchdog_stop = threading.Event()

    def watchdog():
        if not watchdog_stop.wait(max(0, deadline - time.monotonic())):
            if os.name == "posix" and os.getsid(0) == os.getpid():
                os.killpg(os.getpid(), signal.SIGKILL)
            os._exit(78)

    threading.Thread(target=watchdog, daemon=True).start()
    marker = {"worker_pid": os.getpid(), "worker_identity": _identity(os.getpid()),
              "parent_pid": config["parent_pid"], "nonce": config["nonce"],
              "environment_plan_sha256": config["environment_plan_sha256"],
              "actual_environment_lock_sha256": config["bootstrap"]["actual_environment_lock_sha256"],
              "source_identity_sha256": _digest(config["source_identity"]),
              "admission_sha256": config["bootstrap"]["admission_sha256"],
              "evidence_mode": config["evidence_mode"]}
    with (Path(request_path).parent / "worker-start.json").open("xb") as stream:
        stream.write(_canonical(marker)); stream.flush(); os.fsync(stream.fileno())
    if os.name == "posix":
        fd = os.open(Path(request_path).parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    verified = _admission(config["bootstrap"], config["environment_plan_sha256"], config["source_identity"], synthetic=synthetic)
    _require(not any(name == "tools" or name.startswith("tools.") for name in sys.modules), "preloaded tools modules forbidden")
    sys.meta_path.insert(0, _PinnedFinder(config["bootstrap"]["source_root"], verified))
    if not synthetic:
        import socket
        _require(getattr(socket, "_irisx_offline_guard", False), "prepared interpreter network guard missing")
        lock = _json(_read_bound(config["bootstrap"]["environment_lock_path"], config["bootstrap"]["actual_environment_lock_sha256"]))
        _require(hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest() == lock["python_executable_sha256"],
                 "worker interpreter is not the admitted executable")
    mp = _mp()
    bootstrap, actual_hash, plan_hash = config["bootstrap"], config["bootstrap"]["actual_environment_lock_sha256"], config["environment_plan_sha256"]
    factory = (lambda: _SyntheticBackend(config["faults"])) if synthetic else (lambda: mp.G4Backend(
        enabled=True, model_path=bootstrap["model_path"], manifest_path=bootstrap["manifest_path"],
        environment_lock_path=bootstrap["environment_lock_path"], environment_sha256=actual_hash))
    owner = mp.SingleModelOwner(factory, enabled=True, environment_sha256=actual_hash,
                                execution_mode="synthetic-test" if synthetic else "g4")
    registered, sequence = {}, 0

    def translate(raw):
        external = _request(raw)
        _require(external.environment_sha256 == plan_hash, "external environment-plan binding differs")
        return external, replace(external, environment_sha256=actual_hash)

    def outward(external, item, register):
        outer = replace(item, request=external)
        if register:
            registered[outer.sha256] = (outer, item)
        return asdict(outer)

    try:
        while time.monotonic() < deadline:
            envelope = _read_frame(incoming)
            _require(type(envelope) is dict and set(envelope) == {"protocol", "nonce", "sequence", "action", "payload", "request_sha256"}, "invalid IPC request fields")
            binding = {k: v for k, v in envelope.items() if k != "request_sha256"}
            sequence += 1
            _require(envelope["protocol"] == PROTOCOL and envelope["nonce"] == config["nonce"] and
                     type(envelope["sequence"]) is int and envelope["sequence"] == sequence and
                     envelope["request_sha256"] == _digest(binding), "IPC request identity changed")
            action, payload, done = envelope["action"], envelope["payload"], False
            try:
                if action == "TOKENIZER_INIT":
                    _require(payload == {}, "initialization takes no payload")
                    result = owner.initialize_tokenizer()
                elif action == "LOAD_MODEL":
                    _require(payload == {}, "model load takes no payload")
                    result = owner.ensure_model_loaded()
                elif action == "PREPARE":
                    _require(set(payload) == {"request", "register"} and type(payload["register"]) is bool, "prepare schema differs")
                    external, actual = translate(payload["request"])
                    result = outward(external, owner.prepare(actual, register=payload["register"]), payload["register"])
                elif action == "PREPARE_GROUP":
                    _require(set(payload) == {"requests"} and type(payload["requests"]) is list and 0 < len(payload["requests"]) <= 16, "group schema differs")
                    pairs = [translate(value) for value in payload["requests"]]
                    items, receipt = owner.prepare_group([actual for _, actual in pairs])
                    prepared = [outward(external, item, True) for (external, _), item in zip(pairs, items)]
                    if items:
                        for row, value in zip(receipt["requests"], prepared):
                            outer = _prepared(_json(_canonical(value)))
                            row["actual_request_sha256"] = row["request_sha256"]
                            row["request_sha256"] = outer.sha256
                    result = {"prepared": prepared, "receipt": receipt}
                elif action == "GENERATE":
                    _require(set(payload) == {"call_id", "prepared_sha256", "remaining_seconds"}, "generation schema differs")
                    _require(payload["prepared_sha256"] in registered, "unregistered native token handle")
                    external, actual = registered[payload["prepared_sha256"]]
                    _require(external.request.spec.call_id == payload["call_id"] and owner._model_ready, "wrong call or model not explicitly loaded")
                    remaining = payload["remaining_seconds"]
                    _require(type(remaining) in (int, float) and math.isfinite(remaining) and 0 < remaining <= mp.MAX_MODEL_SECONDS, "invalid generation allowance")
                    dispatch_started = time.perf_counter()
                    result = owner.dispatch(actual, deadline_monotonic=min(deadline, time.monotonic() + remaining))
                    result["backend_model_seconds"] = result["model_seconds"]
                    result["model_seconds"] = time.perf_counter() - dispatch_started
                    result.update(external_request_sha256=external.sha256, external_cache_sha256=external.cache_sha256,
                                  environment_plan_sha256=plan_hash, actual_environment_lock_sha256=actual_hash)
                elif action == "CLOSE":
                    _require(payload == {}, "close takes no payload")
                    result, done = owner.close(), True
                else:
                    raise RemoteOwnerError("unknown IPC action")
                ok = True
            except Exception as exc:
                result, ok = {"type": type(exc).__name__, "message": str(exc)[:600]}, False
                if isinstance(exc, mp.TokenAdmissionError):
                    result.update(observed=exc.observed, limit=exc.limit)
            _write_frame(outgoing, {"protocol": PROTOCOL, "nonce": config["nonce"], "sequence": sequence,
                                   "request_sha256": envelope["request_sha256"], "ok": ok, "payload": result})
            if done:
                return
    finally:
        try:
            owner.close()
        finally:
            watchdog_stop.set()
            incoming.close(); outgoing.close()


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--owner-worker":
        _worker(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 2 and sys.argv[1] == "--synthetic-sleeper":
        time.sleep(30)
    else:
        raise SystemExit("Only the bound owner-worker entry point is supported")
