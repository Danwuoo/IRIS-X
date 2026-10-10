"""Demos-only verification in a fresh, OS-limited Linux process.

Candidate source is AST data for the pinned interpreter.  It is never imported,
compiled to host bytecode, or executed as Python.  Trusted interpreter bytes are
loaded only after checking both legacy asset pins.  There is no Windows fallback.

``gas`` is observed interpreter work, or None after an unknown worker outcome.
``gas_charged`` charges the entire reservation for an unknown dispatched check.
``known`` describes the check outcome, not whether every demo was evaluated.
"""
from __future__ import annotations

import hashlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


PROTOCOL = "irisx/demos-verifier-v1"
ASSET_PINS = {
    "arc_bounded_v2.py": "9f210e97ddea7f98358ce8d3551310fe1411d57db27c21d7d80f705ce5d41ab7",
    "arc_typed_ir.py": "8802c4d8e36f2a43acac1abec5a7c2a5b913461cf9f51f7bc7a3eb274ef72ff9",
}
ASSET_DIRECTORY = Path(__file__).resolve().parent / "legacy"
MAX_SOURCE_BYTES = 32768
MAX_REQUEST_BYTES = 131072
MAX_RESPONSE_BYTES = 32768
MAX_STEPS = 200000
MAX_WALL_SECONDS = 3.0
MEMORY_BYTES = 256 * 1024 * 1024
CPU_SECONDS = 2
MAX_DEMOS = 10
MAX_FEEDBACK_SAMPLES = 8
FORBIDDEN_KEYS = frozenset({"test", "query", "gold", "solutions"})
_STATUS = {"fit", "mismatch", "out_of_domain", "admission_rejected", "unavailable", "unknown"}
_DEMO_STATUS = {"match", "mismatch", "out_of_domain", "not_evaluated"}


class AdmissionError(ValueError):
    """The request is outside the strict demos-only input contract."""


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def known_limits():
    """Return fixed ceilings; these cannot be raised through the public API."""
    return {"memory_bytes": MEMORY_BYTES, "cpu_seconds": CPU_SECONDS,
            "file_bytes": MAX_RESPONSE_BYTES, "parent_wall_seconds": MAX_WALL_SECONDS,
            "source_bytes": MAX_SOURCE_BYTES, "request_bytes": MAX_REQUEST_BYTES,
            "response_bytes": MAX_RESPONSE_BYTES, "gas": MAX_STEPS,
            "demos": MAX_DEMOS, "mismatch_samples": MAX_FEEDBACK_SAMPLES}


def capability():
    """Inspect enforcement capability without loading any interpreter or model."""
    if sys.platform != "linux":
        return {"available": False, "reason": "Linux resource limits required; no fallback",
                "platform": sys.platform, "limits": known_limits()}
    try:
        import resource
        required = ("RLIMIT_AS", "RLIMIT_CPU", "RLIMIT_FSIZE", "setrlimit", "getrusage")
        if any(not hasattr(resource, name) for name in required):
            raise ImportError("required resource controls absent")
    except ImportError:
        return {"available": False, "reason": "required resource controls unavailable",
                "platform": sys.platform, "limits": known_limits()}
    return {"available": True, "reason": "Linux resource controls available; enforced in child",
            "platform": sys.platform, "limits": known_limits()}


def _reject_forbidden(value):
    stack = [(value, 0, frozenset())]
    count = 0
    while stack:
        item, depth, ancestors = stack.pop()
        count += 1
        if count > 24000 or depth > 8:
            raise AdmissionError("task structure limit")
        if type(item) in (dict, list):
            if len(item) > 30:
                raise AdmissionError("task container size limit")
            if id(item) in ancestors:
                raise AdmissionError("task cycles forbidden")
            ancestors = ancestors | {id(item)}
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise AdmissionError("task keys must be strings")
            if any(key.casefold() in FORBIDDEN_KEYS for key in item):
                raise AdmissionError("test/query/gold/solutions keys forbidden")
            stack.extend((child, depth + 1, ancestors) for child in item.values())
        elif type(item) is list:
            stack.extend((child, depth + 1, ancestors) for child in item)


def _grid(value):
    if (type(value) is not list or not 1 <= len(value) <= 30
            or any(type(row) is not list for row in value)
            or not 1 <= len(value[0]) <= 30
            or any(len(row) != len(value[0]) for row in value)
            or any(type(cell) is not int or not 0 <= cell <= 9 for row in value for cell in row)):
        raise AdmissionError("grid must be rectangular 1..30 with integer colors 0..9")
    return [row[:] for row in value]


def validate_task(task):
    """Copy exactly task_id and input/output demos; reject hidden extra fields."""
    _reject_forbidden(task)
    if type(task) is not dict or set(task) != {"task_id", "demos"}:
        raise AdmissionError("task must contain exactly task_id and demos")
    ident = task["task_id"]
    try:
        if type(ident) is not str or not 1 <= len(ident.encode("utf-8", "strict")) <= 128:
            raise AdmissionError("task_id must be nonempty UTF-8 text, at most 128 bytes")
    except UnicodeError as exc:
        raise AdmissionError("task_id must be valid UTF-8") from exc
    if type(task["demos"]) is not list or not 1 <= len(task["demos"]) <= MAX_DEMOS:
        raise AdmissionError("expected 1..10 demonstrations")
    demos = []
    for pair in task["demos"]:
        if type(pair) is not dict or set(pair) != {"input", "output"}:
            raise AdmissionError("demo must contain exactly input and output")
        demos.append({"input": _grid(pair["input"]), "output": _grid(pair["output"])})
    return {"task_id": ident, "demos": demos}


def _check_assets():
    values = {}
    for filename, expected in ASSET_PINS.items():
        path = ASSET_DIRECTORY / filename
        with path.open("rb") as source_file:
            data = source_file.read(128 * 1024 + 1)
        if len(data) > 128 * 1024 or hashlib.sha256(data).hexdigest() != expected:
            raise AdmissionError("legacy asset hash mismatch: " + filename)
        values[filename] = data
    return values


class _PinnedLoader(importlib.abc.SourceLoader):
    """Serve already verified trusted bytes, never a second filesystem read."""
    def __init__(self, path, data):
        self.path, self.data = str(path), data

    def get_filename(self, fullname):
        return self.path

    def get_data(self, path):
        if path != self.path:
            raise OSError("unpinned import path")
        return self.data


def _load_interpreter(assets):
    name = "_irisx_consolidated_pinned_bounded_v2"
    loader = _PinnedLoader(ASSET_DIRECTORY / "arc_bounded_v2.py", assets["arc_bounded_v2.py"])
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclass resolves the trusted module by name.
    try:
        loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _strict_json(data):
    def pairs(values):
        out = {}
        for key, value in values:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out

    def constant(value):
        raise ValueError("nonfinite JSON number")

    return json.loads(data.decode("utf-8", "strict"), object_pairs_hook=pairs,
                      parse_constant=constant)


def _bindings(request):
    return {"request_sha256": _digest(request), "task_sha256": _digest(request["task"]),
            "source_sha256": hashlib.sha256(request["source"].encode("utf-8")).hexdigest(),
            "asset_sha256": dict(ASSET_PINS)}


def _result(status, reason, request=None):
    return {"schema": PROTOCOL, "status": status, "known": status not in {"unknown", "unavailable"},
            "all_demos_fit": status == "fit", "demos": [], "gas": 0,
            "worker_wall_seconds": None, "worker_cpu_seconds": None, "reason": reason[:160],
            "limits": known_limits(), **(_bindings(request) if request is not None else
                {"request_sha256": None, "task_sha256": None, "source_sha256": None,
                 "asset_sha256": dict(ASSET_PINS)})}


def _empty_demo(index, pair):
    return {"index": index, "status": "not_evaluated", "match": None,
            "input_shape": [len(pair["input"]), len(pair["input"][0])],
            "expected_shape": [len(pair["output"]), len(pair["output"][0])],
            "actual_shape": None, "mismatch_count": None, "mismatch_samples": [],
            "gas": 0, "wall_seconds": 0.0, "reason": "not evaluated"}


def _feedback(actual, expected):
    count, samples = 0, []
    for row in range(max(len(actual), len(expected))):
        aa = actual[row] if row < len(actual) else []
        ee = expected[row] if row < len(expected) else []
        for column in range(max(len(aa), len(ee))):
            a = aa[column] if column < len(aa) else None
            e = ee[column] if column < len(ee) else None
            if a != e:
                count += 1
                if len(samples) < MAX_FEEDBACK_SAMPLES:
                    samples.append({"row": row, "column": column, "expected": e, "actual": a})
    return count, samples


def _evaluate(request, vm):
    started = time.monotonic()
    result = _result("mismatch", "demo mismatch", request)
    result["demos"] = [_empty_demo(i, pair) for i, pair in enumerate(request["task"]["demos"])]
    try:
        vm._Interpreter(request["source"], vm.Limits(max_program_steps=request["max_steps"]))
    except vm.ProgramError as exc:
        result.update(status="admission_rejected", reason=str(exc)[:160])
        result["worker_wall_seconds"] = time.monotonic() - started
        return result
    total = 0
    for demo, pair in zip(result["demos"], request["task"]["demos"]):
        remaining = request["max_steps"] - total
        if remaining == 0:
            demo["reason"] = "shared candidate gas exhausted"
            continue
        tick = time.monotonic()
        try:
            outcome = vm.execute_program(request["source"], pair["input"],
                                         vm.Limits(max_program_steps=remaining))
            actual = outcome["output"]
            demo["gas"] = outcome["steps"]
            demo["actual_shape"] = [len(actual), len(actual[0])]
            count, samples = _feedback(actual, pair["output"])
            demo.update(match=count == 0, mismatch_count=count, mismatch_samples=samples,
                        status="match" if count == 0 else "mismatch",
                        reason="demo fit" if count == 0 else "demo mismatch")
        except vm.ProgramError as exc:
            demo.update(status="out_of_domain", gas=getattr(exc, "steps", 0), reason=str(exc)[:160])
        demo["wall_seconds"] = time.monotonic() - tick
        total += demo["gas"]
    fit = all(row["status"] == "match" for row in result["demos"])
    domain = any(row["status"] in {"out_of_domain", "not_evaluated"} for row in result["demos"])
    result.update(status="fit" if fit else "out_of_domain" if domain else "mismatch",
                  all_demos_fit=fit, gas=total,
                  reason="all demos fit" if fit else "candidate outside bounded domain" if domain else "demo mismatch",
                  worker_wall_seconds=time.monotonic() - started)
    return result


def _worker():
    """Private child entry point. Resource controls precede request/model code."""
    if not capability()["available"]:
        return 3
    import resource
    try:
        for kind, amount in ((resource.RLIMIT_AS, MEMORY_BYTES),
                             (resource.RLIMIT_CPU, CPU_SECONDS),
                             (resource.RLIMIT_FSIZE, MAX_RESPONSE_BYTES)):
            resource.setrlimit(kind, (amount, amount))
        if hasattr(resource, "RLIMIT_CORE"):
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (OSError, ValueError):
        return 3
    request = None
    try:
        data = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(data) > MAX_REQUEST_BYTES:
            return 4
        request = _strict_json(data)
        if type(request) is not dict or set(request) != {"protocol", "source", "task", "max_steps"}:
            return 4
        if request["protocol"] != PROTOCOL:
            return 4
        _validate_request(request["source"], request["task"], MAX_WALL_SECONDS, request["max_steps"])
        vm = _load_interpreter(_check_assets())
        result = _evaluate(request, vm)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        result["worker_cpu_seconds"] = usage.ru_utime + usage.ru_stime
        output = _canonical(result)
        if len(output) > MAX_RESPONSE_BYTES:
            return 5
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError, MemoryError):
        # Missing/corrupt assets and protocol failures cannot fabricate evidence.
        return 4


def _validate_request(source, task, timeout, max_steps):
    if type(source) is not str:
        raise AdmissionError("source must be text")
    try:
        if not 1 <= len(source) <= MAX_SOURCE_BYTES or len(source.encode("utf-8", "strict")) > MAX_SOURCE_BYTES:
            raise AdmissionError("source byte limit")
    except UnicodeError as exc:
        raise AdmissionError("source must be valid UTF-8") from exc
    if type(timeout) not in (int, float) or not 0 < timeout <= MAX_WALL_SECONDS:
        raise AdmissionError("parent wall limit must be positive and at most 3 seconds")
    if type(max_steps) is not int or not 1 <= max_steps <= MAX_STEPS:
        raise AdmissionError("candidate gas limit must be 1..200000")
    return {"protocol": PROTOCOL, "source": source, "task": validate_task(task), "max_steps": max_steps}


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _validate_receipt(result, request):
    """Reject malformed, unbound, inflated, or self-contradictory child output."""
    if type(result) is not dict or set(result) != set(_result("unknown", "", request)):
        raise ValueError("worker receipt schema")
    if (result["schema"] != PROTOCOL or type(result["status"]) is not str
            or result["status"] not in _STATUS - {"unknown", "unavailable"}):
        raise ValueError("worker status")
    if any(result[key] != value for key, value in _bindings(request).items()):
        raise ValueError("worker receipt binding")
    if result["limits"] != known_limits() or type(result["limits"]) is not dict:
        raise ValueError("worker limits")
    if type(result["known"]) is not bool or result["known"] is not True:
        raise ValueError("worker known flag")
    if type(result["all_demos_fit"]) is not bool:
        raise ValueError("worker fit flag")
    if type(result["gas"]) is not int or not 0 <= result["gas"] <= request["max_steps"]:
        raise ValueError("worker gas")
    if any(not _number(result[key]) for key in ("worker_wall_seconds", "worker_cpu_seconds")):
        raise ValueError("worker timing")
    if type(result["reason"]) is not str or len(result["reason"]) > 160:
        raise ValueError("worker reason")
    demos = result["demos"]
    if type(demos) is not list or len(demos) != len(request["task"]["demos"]):
        raise ValueError("worker demo count")
    for index, (row, pair) in enumerate(zip(demos, request["task"]["demos"])):
        template = _empty_demo(index, pair)
        if type(row) is not dict or set(row) != set(template):
            raise ValueError("worker demo schema")
        if (type(row["index"]) is not int or row["index"] != index
                or type(row["status"]) is not str or row["status"] not in _DEMO_STATUS):
            raise ValueError("worker demo identity")
        if row["input_shape"] != template["input_shape"] or row["expected_shape"] != template["expected_shape"]:
            raise ValueError("worker demo shapes")
        for key in ("input_shape", "expected_shape", "actual_shape"):
            shape = row[key]
            if shape is not None and (type(shape) is not list or len(shape) != 2 or
                                     any(type(n) is not int or not 1 <= n <= 30 for n in shape)):
                raise ValueError("worker shape value")
        if type(row["gas"]) is not int or not 0 <= row["gas"] <= request["max_steps"] or not _number(row["wall_seconds"]):
            raise ValueError("worker demo accounting")
        if type(row["reason"]) is not str or len(row["reason"]) > 160:
            raise ValueError("worker demo reason")
        samples = row["mismatch_samples"]
        if type(samples) is not list or len(samples) > MAX_FEEDBACK_SAMPLES:
            raise ValueError("worker samples")
        for sample in samples:
            if type(sample) is not dict or set(sample) != {"row", "column", "expected", "actual"}:
                raise ValueError("worker mismatch sample schema")
            if any(type(sample[k]) is not int or not 0 <= sample[k] < 30 for k in ("row", "column")):
                raise ValueError("worker mismatch coordinate")
            if any(sample[k] is not None and (type(sample[k]) is not int or not 0 <= sample[k] <= 9)
                   for k in ("expected", "actual")) or sample["expected"] == sample["actual"]:
                raise ValueError("worker mismatch values")
        if row["status"] in {"match", "mismatch"}:
            count = row["mismatch_count"]
            if type(row["match"]) is not bool or row["match"] != (row["status"] == "match"):
                raise ValueError("worker demo fit")
            if type(count) is not int or not 0 <= count <= 900 or len(samples) != min(count, MAX_FEEDBACK_SAMPLES):
                raise ValueError("worker mismatch count")
            if row["actual_shape"] is None or (count == 0) != row["match"]:
                raise ValueError("worker mismatch agreement")
            if row["match"] and row["actual_shape"] != row["expected_shape"]:
                raise ValueError("worker fit shape")
        elif any(row[key] is not None for key in ("match", "actual_shape", "mismatch_count")) or samples:
            raise ValueError("worker unevaluated feedback")
        if row["status"] == "not_evaluated" and row["gas"] != 0:
            raise ValueError("worker unevaluated gas")
    if sum(row["gas"] for row in demos) != result["gas"]:
        raise ValueError("worker gas total")
    fit = all(row["status"] == "match" for row in demos)
    domain = any(row["status"] in {"out_of_domain", "not_evaluated"} for row in demos)
    status = "fit" if fit else "out_of_domain" if domain else "mismatch"
    if result["status"] == "admission_rejected":
        if any(row["status"] != "not_evaluated" for row in demos) or result["gas"]:
            raise ValueError("worker admission accounting")
    elif result["status"] != status:
        raise ValueError("worker aggregate status")
    if result["all_demos_fit"] != fit:
        raise ValueError("worker aggregate fit")
    return result


def _terminate(process):
    # The pinned language cannot spawn processes, but reap the whole new session
    # on timeout rather than leaving a future trusted-worker descendant behind.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        process.kill()
    process.wait()


def verify(source, task, *, timeout=MAX_WALL_SECONDS, max_steps=MAX_STEPS):
    """Verify one candidate against demos only, returning bounded evidence.

    Each call has a fresh worker and one shared gas budget across its demos.
    No candidate runs in this process; missing Linux controls return unavailable.
    The caller must persist its reservation before invoking this function.
    """
    started = time.monotonic()
    request, dispatched = None, False
    descendants_stopped = True
    reserved = 0
    try:
        request = _validate_request(source, task, timeout, max_steps)
        payload = _canonical(request)
        if len(payload) > MAX_REQUEST_BYTES:
            raise AdmissionError("request byte limit")
    except (AdmissionError, ValueError, UnicodeError, RecursionError) as exc:
        result = _result("admission_rejected", str(exc), request)
    else:
        cap = capability()
        if not cap["available"]:
            result = _result("unavailable", cap["reason"], request)
        else:
            try:
                _check_assets()
            except (OSError, AdmissionError) as exc:
                result = _result("admission_rejected", str(exc), request)
            else:
                result = _result("unknown", "worker did not return a verified receipt", request)
                try:
                    with tempfile.TemporaryDirectory(prefix="irisx-demo-verify-") as directory:
                        root = Path(directory)
                        (root / "request.json").write_bytes(payload)
                        with (root / "request.json").open("rb") as input_file, \
                                (root / "response.json").open("wb") as output_file, \
                                (root / "stderr.txt").open("wb") as error_file:
                            remaining = timeout - (time.monotonic() - started)
                            if remaining <= 0:
                                result = _result("unavailable", "parent admission deadline exhausted", request)
                            else:
                                process = subprocess.Popen(
                                    [sys.executable, "-I", str(Path(__file__).resolve()), "--worker"],
                                    stdin=input_file, stdout=output_file, stderr=error_file,
                                    cwd=directory, start_new_session=True, close_fds=True)
                                dispatched, reserved, descendants_stopped = True, max_steps, False
                                try:
                                    process.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
                                except subprocess.TimeoutExpired:
                                    _terminate(process)
                                    descendants_stopped = True
                                    result["reason"] = "parent wall deadline; worker killed and reaped"
                                except BaseException:
                                    _terminate(process)
                                    raise
                                else:
                                    descendants_stopped = True
                                    if process.returncode == 0:
                                        with (root / "response.json").open("rb") as response_file:
                                            data = response_file.read(MAX_RESPONSE_BYTES + 1)
                                        if len(data) > MAX_RESPONSE_BYTES:
                                            raise ValueError("worker response byte limit")
                                        result = _validate_receipt(_strict_json(data), request)
                                    else:
                                        result["reason"] = "worker exited without receipt: " + str(process.returncode)
                except (OSError, ValueError, UnicodeError, RecursionError) as exc:
                    result = _result("unknown" if dispatched else "unavailable",
                                     "worker transport: " + str(exc), request)
    if dispatched and result["status"] == "unknown":
        result["gas"] = None
    result.update(dispatched=dispatched, gas_reserved=reserved,
                  owned_descendants_stopped=descendants_stopped,
                  gas_charged=reserved if dispatched and not result["known"] else result["gas"],
                  wall_reserved_seconds=float(timeout) if dispatched else 0.0,
                  wall_seconds=time.monotonic() - started)
    return result


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("This module only exposes a private --worker entry point.")
    raise SystemExit(_worker())
