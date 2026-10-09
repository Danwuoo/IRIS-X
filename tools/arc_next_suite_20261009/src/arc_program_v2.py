"""Next-phase CPU program verifier for a separately pinned bounded-v2 interpreter. Candidate Python syntax is interpreted as AST data.

This wrapper imports only a separately hash-pinned trusted bounded-v2 module. Model source is
never passed to Python execution, a shell, an import mechanism, or host APIs.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib.machinery
import importlib.util
import json
import math
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

AGENT_SHA256 = "9f210e97ddea7f98358ce8d3551310fe1411d57db27c21d7d80f705ce5d41ab7"
MAX_SOURCE_BYTES = 32768
MAX_INPUT_BYTES = 262144
MAX_OUTPUT_BYTES = 65536
MAX_PROGRAM_STEPS = 200000
MAX_WALL_SECONDS = 3.0
MAX_CPU_SECONDS = 2
MAX_MEMORY_BYTES = 256 * 1024 * 1024
MAX_AST_NODES = 2048
PRIMITIVE_ARITIES = {
    "list": (1, 1), "len": (1, 1), "range": (1, 3), "enumerate": (1, 1), "zip": (1, 8),
    "min": (1, 1), "max": (1, 1), "sum": (1, 1), "sorted": (1, 1),
    "reversed": (1, 1), "unique": (1, 1), "abs": (1, 1),
    "append": (2, 2), "copy_grid": (1, 1), "new_grid": (3, 3),
    "transpose": (1, 1), "crop": (5, 5), "components": (3, 3),
}
SYNTHETIC_EXAMPLES = (
    "def transform(grid):\n    return copy_grid(grid)\n",
    "def transform(grid):\n    out = copy_grid(grid)\n    for r in range(len(out)):\n        for c in range(len(out[r])):\n            if out[r][c] == 1:\n                out[r][c] = 2\n    return out\n",
)


def program_contract():
    return (
        "Return only raw source beginning with def and defining transform(grid). "
        "Helpers may precede transform. No Markdown fences, JSON envelope or prose. "
        "This is a bounded Python-like language: integer/bool/None, lists/tuples, "
        "indexing/slices, + - * // %, comparisons, boolean operators, if, for, "
        "list comprehensions, lexical break/continue, return, simple assignment "
        "and named helpers. Use explicit assignments; += and every augmented "
        "assignment are forbidden. No import, general attribute access, strings, dictionaries, "
        "exceptions, nested definitions, async or host APIs. While is supported under the same gas limit. "
        "Only list.append(x), list.pop() or list.pop(index), list.extend(xs) are admitted methods. "
        "Generator comprehensions are eagerly evaluated as bounded lists. is/is not compare language object identity. "
        "Primitives: list(xs), len(xs), range(stop) or range(start,stop[,step]), enumerate(xs), "
        "zip(xs,...), min/max/sum/sorted/reversed/unique(integer_list), abs(n), "
        "append(xs,x), copy_grid(g), new_grid(h,w,color), transpose(g), "
        "crop(g,r0,c0,r1,c1) with exclusive end, "
        "components(g,background,connectivity) with connectivity 4 or 8; "
        "components returns same-color objects containing [row,column,color] pixels. "
        "Calls resolve declared helper/primitive names; for loops snapshot their "
        "iterables. Return a rectangular 1..30 grid with integer colors 0..9. "
        "Fit every visible demonstration with the same program. "
        "Limits: source 32768 UTF-8 bytes; 2048 AST nodes; 200000 shared demo/query "
        "steps; 16384 recursive value items; value depth 16; call depth 12; "
        "8 functions; 128 locals; integer magnitude at most 1000000. "
        "Synthetic contract example 1 (identity):\n" + SYNTHETIC_EXAMPLES[0] +
        "Synthetic contract example 2 (replace color 1 with 2):\n" + SYNTHETIC_EXAMPLES[1]
    )


def _result():
    return {
        "format_admitted": False,
        "python_parse_admitted": False,
        "ast_admitted": False,
        "demo_execution_success": False,
        "all_demonstrations_exact": False,
        "query_execution_success": False,
        "candidate": None,
        "program_steps": 0,
        "verification_seconds": 0.0,
        "feedback": {"error": None, "demonstrations": [], "all_demonstrations_exact": False},
        "error_category": None,
    }


def _fail(result, category, error=None, *, demo_feedback=True):
    result["error_category"] = category
    result["candidate"] = None
    if demo_feedback:
        result["feedback"]["error"] = str(error or category)[:512]
    return result


def _format_ok(source):
    if type(source) is not str or len(source) > MAX_SOURCE_BYTES:
        return False
    try:
        return len(source.encode("utf-8", "strict")) <= MAX_SOURCE_BYTES and bool(
            re.match(r"\Adef\b", source.strip()))
    except UnicodeError:
        return False


def _strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value
    def constant(_):
        raise ValueError("nonfinite JSON value")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def _load_agent(path):
    # The deployment path is trusted input, never model-selected. Only the
    # exact bytes verified here are compiled by the trusted module importer.
    with open(path, "rb") as handle:
        source = handle.read(100001)
    if len(source) > 100000 or hashlib.sha256(source).hexdigest() != AGENT_SHA256:
        raise ValueError("bounded-v2 source hash mismatch")
    class VerifiedSourceLoader(importlib.machinery.SourceFileLoader):
        def get_code(self, fullname):
            if fullname != "nextphase_pinned_bounded_v2":
                raise ImportError("unexpected trusted module name")
            # Bypass cached pyc and any second file read (TOCTOU). This is
            # hash-pinned application code, never generated candidate source.
            return self.source_to_code(source, os.fspath(path))
    loader = VerifiedSourceLoader("nextphase_pinned_bounded_v2", os.fspath(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None or spec.loader is None:
        raise ValueError("runtime8 import unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # Trusted hash-pinned module, never candidate source.
    return module


def _guard(source, tree, agent, limits):
    # Apply bounded-v2 syntax/signature/name/AST checks, then full-tree admission below.
    machine = agent._Interpreter(source, limits)
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise agent.ProgramError("AST size limit")
    parents = {id(child): parent for parent in nodes for child in ast.iter_child_nodes(parent)}
    for node in nodes:
        if isinstance(node, ast.Attribute):
            parent = parents.get(id(node))
            if not isinstance(parent, ast.Call) or parent.func is not node or node.attr not in ("append", "pop", "extend"):
                raise agent.ProgramError("unsupported attribute " + node.attr + " at line " + str(node.lineno) + "; only list append/pop/extend calls are allowed")
        if isinstance(node, ast.AugAssign):
            raise agent.ProgramError("augmented assignments are forbidden; use explicit assignment")
        if isinstance(node, ast.Constant):
            if type(node.value) not in (int, bool, type(None)):
                raise agent.ProgramError("only integer/bool/None literals are allowed")
            if type(node.value) is int and abs(node.value) > limits.max_integer:
                raise agent.ProgramError("integer magnitude limit")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.keywords or node.func.attr not in ("append", "pop", "extend"):
                    raise agent.ProgramError("only positional append/pop/extend list methods allowed")
                low, high = (0, 1) if node.func.attr == "pop" else (1, 1)
                if not low <= len(node.args) <= high:
                    raise agent.ProgramError("list method arity at line " + str(node.lineno))
                continue
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise agent.ProgramError("only named positional calls are allowed at line " + str(node.lineno))
            name = node.func.id
            if name in machine.functions:
                low = high = len(machine.functions[name].args.args)
            elif name in PRIMITIVE_ARITIES:
                low, high = PRIMITIVE_ARITIES[name]
            else:
                raise agent.ProgramError("unknown named call " + name[:80] + " at line " + str(node.lineno) + "; use only declared helpers or documented primitives")
            if not low <= len(node.args) <= high:
                raise agent.ProgramError("call argument count mismatch for " + name[:80] + " at line " + str(node.lineno) + "; expected " + str(low) + ".." + str(high))
        if isinstance(node, ast.comprehension) and node.is_async:
            raise agent.ProgramError("async comprehensions are forbidden")
    # Explicit traversal avoids relying on ast.parse's missing compile-time
    # control-flow checks. Loop else is outside that loop's break/continue scope.
    for function in tree.body:
        stack = [(node, 0) for node in function.body]
        while stack:
            node, loop_depth = stack.pop()
            if isinstance(node, ast.FunctionDef):
                raise agent.ProgramError("nested function definitions are forbidden")
            if isinstance(node, (ast.Break, ast.Continue)) and not loop_depth:
                raise agent.ProgramError("break/continue require a lexical loop in this function")
            if isinstance(node, (ast.For, ast.While)):
                stack.extend((child, loop_depth + 1) for child in node.body)
                stack.extend((child, loop_depth) for child in node.orelse)
                expressions = (node.target, node.iter) if isinstance(node, ast.For) else (node.test,)
                stack.extend((child, loop_depth) for child in expressions)
            else:
                stack.extend((child, loop_depth) for child in ast.iter_child_nodes(node))


def _demo_row(index, prediction, target):
    same_shape = (len(prediction), len(prediction[0])) == (len(target), len(target[0]))
    mismatch = [] if not same_shape else [
        [r, c, prediction[r][c], target[r][c]]
        for r in range(len(target)) for c in range(len(target[0]))
        if prediction[r][c] != target[r][c]
    ]
    return {
        "demo_index": index, "exact": prediction == target,
        "shape_match": same_shape,
        "predicted_shape": [len(prediction), len(prediction[0])],
        "target_shape": [len(target), len(target[0])],
        "mismatch_count": len(mismatch) if same_shape else None,
        "first_mismatches": mismatch[:12],
    }


def _verify_in_worker(source, task, agent_path, emit):
    result = _result()
    if not _format_ok(source):
        return _fail(result, "format", "raw bounded source must begin with def")
    result["format_admitted"] = True
    try:
        agent = _load_agent(agent_path)
    except Exception:
        return _fail(result, "source_binding", "pinned bounded-v2 unavailable")
    try:
        task = agent.validate_task(task)
        if len(task["test"]) != 1:
            raise ValueError("exactly one ordered query required")
    except (ValueError, TypeError, RecursionError):
        return _fail(result, "task_schema", "invalid solver-visible task")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return _fail(result, "python_parse", "syntax error at line " + str(exc.lineno) + ", column " + str(exc.offset) + ": " + str(exc.msg)[:180])
    except (ValueError, RecursionError, MemoryError):
        return _fail(result, "python_parse", "invalid or resource-exhausted Python syntax")
    result["python_parse_admitted"] = True
    limits = agent.Limits(max_program_steps=MAX_PROGRAM_STEPS)
    try:
        _guard(source, tree, agent, limits)
    except (agent.ProgramError, RecursionError, MemoryError) as exc:
        return _fail(result, "allowed_ast", str(exc))
    result["ast_admitted"] = True
    rows = result["feedback"]["demonstrations"]
    for index, pair in enumerate(task["train"]):
        remaining = MAX_PROGRAM_STEPS - result["program_steps"]
        if remaining <= 0:
            return _fail(result, "demo_budget", "program step allowance exhausted")
        try:
            run = agent.execute_program(source, pair["input"], dataclasses.replace(limits, max_program_steps=remaining))
            result["program_steps"] += run["steps"]
            rows.append(_demo_row(index, run["output"], pair["output"]))
        except agent.ProgramError as exc:
            result["program_steps"] += getattr(exc, "steps", 0)
            return _fail(result, "demo_runtime", str(exc))
    result["demo_execution_success"] = True
    exact = all(row["exact"] for row in rows)
    result["all_demonstrations_exact"] = exact
    result["feedback"]["all_demonstrations_exact"] = exact
    if not exact:
        return _fail(result, "demo_mismatch", "visible demonstrations do not all match")
    # This record survives a hard query-phase failure; no query diagnostic or
    # prediction is ever copied into demonstration repair feedback.
    emit("query_pending", result)
    remaining = MAX_PROGRAM_STEPS - result["program_steps"]
    if remaining <= 0:
        return _fail(result, "query_budget", demo_feedback=False)
    try:
        run = agent.execute_program(source, task["test"][0]["input"], dataclasses.replace(limits, max_program_steps=remaining))
        result["program_steps"] += run["steps"]
        result["query_execution_success"] = True
        result["candidate"] = run["output"]
        return result
    except agent.ProgramError as exc:
        result["program_steps"] += getattr(exc, "steps", 0)
        return _fail(result, "query_runtime", demo_feedback=False)


def _emit(stage, result):
    data = json.dumps({"stage": stage, "result": result}, separators=(",", ":"), allow_nan=False)
    if len(data.encode("utf-8")) > MAX_OUTPUT_BYTES // 2:
        raise ValueError("worker record size limit")
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


def _worker_main(agent_path):
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("worker input size limit")
    payload = _strict_json(raw)
    if type(payload) is not dict or set(payload) != {"source", "task"}:
        raise ValueError("worker input schema")
    result = _verify_in_worker(payload["source"], payload["task"], agent_path, _emit)
    _emit("final", result)


def _valid_demo_row(row, index):
    expected = {"demo_index", "exact", "shape_match", "predicted_shape", "target_shape", "mismatch_count", "first_mismatches"}
    if type(row) is not dict or set(row) != expected or type(row["demo_index"]) is not int or row["demo_index"] != index:
        return False
    if type(row["exact"]) is not bool or type(row["shape_match"]) is not bool:
        return False
    for key in ("predicted_shape", "target_shape"):
        shape = row[key]
        if type(shape) is not list or len(shape) != 2 or any(type(v) is not int or not 1 <= v <= 30 for v in shape):
            return False
    if row["shape_match"] != (row["predicted_shape"] == row["target_shape"]):
        return False
    count, mismatches = row["mismatch_count"], row["first_mismatches"]
    if type(mismatches) is not list or len(mismatches) > 12:
        return False
    if row["shape_match"]:
        h, w = row["target_shape"]
        if type(count) is not int or not 0 <= count <= h * w or len(mismatches) != min(count, 12):
            return False
        if row["exact"] != (count == 0):
            return False
        previous = (-1, -1)
        for cell in mismatches:
            if type(cell) is not list or len(cell) != 4 or any(type(v) is not int for v in cell):
                return False
            r, c, predicted, target = cell
            if not (0 <= r < h and 0 <= c < w and 0 <= predicted <= 9 and 0 <= target <= 9 and predicted != target):
                return False
            if (r, c) <= previous:
                return False
            previous = (r, c)
    elif count is not None or mismatches or row["exact"]:
        return False
    return True


def _valid_result(value):
    if type(value) is not dict or set(value) != set(_result()):
        return False
    phases = ("format_admitted", "python_parse_admitted", "ast_admitted", "demo_execution_success", "all_demonstrations_exact", "query_execution_success")
    if any(type(value[key]) is not bool for key in phases):
        return False
    if any(value[phases[i + 1]] and not value[phases[i]] for i in range(len(phases) - 1)):
        return False
    if type(value["program_steps"]) is not int or not 0 <= value["program_steps"] <= MAX_PROGRAM_STEPS:
        return False
    seconds = value["verification_seconds"]
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        return False
    category = value["error_category"]
    if category is not None and (type(category) is not str or not 1 <= len(category) <= 64 or not re.fullmatch(r"[a-z_]+", category)):
        return False
    feedback = value["feedback"]
    if type(feedback) is not dict or set(feedback) != {"error", "demonstrations", "all_demonstrations_exact"}:
        return False
    if feedback["error"] is not None and (type(feedback["error"]) is not str or len(feedback["error"]) > 512):
        return False
    if type(feedback["all_demonstrations_exact"]) is not bool or feedback["all_demonstrations_exact"] != value["all_demonstrations_exact"]:
        return False
    rows = feedback["demonstrations"]
    if type(rows) is not list or len(rows) > 10 or any(not _valid_demo_row(row, i) for i, row in enumerate(rows)):
        return False
    if rows and not value["ast_admitted"]:
        return False
    if value["demo_execution_success"] and (not rows or value["all_demonstrations_exact"] != all(row["exact"] for row in rows)):
        return False
    if value["all_demonstrations_exact"] and feedback["error"] is not None:
        return False
    candidate = value["candidate"]
    if candidate is not None:
        if type(candidate) is not list or not 1 <= len(candidate) <= 30 or any(type(row) is not list for row in candidate):
            return False
        if not 1 <= len(candidate[0]) <= 30 or any(len(row) != len(candidate[0]) for row in candidate):
            return False
        if any(type(cell) is not int or not 0 <= cell <= 9 for row in candidate for cell in row):
            return False
        if not value["query_execution_success"] or category is not None:
            return False
    elif value["query_execution_success"]:
        return False
    return True


def _result_binds_task(result, task):
    """Validate returned demo evidence against the exact submitted visible task."""
    rows = result["feedback"]["demonstrations"]
    if not result["ast_admitted"]:
        return not rows
    if type(task) is not dict or set(task) != {"train", "test"}:
        return False
    train, test = task["train"], task["test"]
    if type(train) is not list or not 1 <= len(train) <= 10 or type(test) is not list or len(test) != 1:
        return False
    if len(rows) > len(train) or (result["demo_execution_success"] and len(rows) != len(train)):
        return False
    def grid_ok(grid):
        return (type(grid) is list and 1 <= len(grid) <= 30
                and all(type(row) is list for row in grid)
                and 1 <= len(grid[0]) <= 30
                and all(len(row) == len(grid[0]) for row in grid)
                and all(type(cell) is int and 0 <= cell <= 9 for row in grid for cell in row))
    for pair in train:
        if type(pair) is not dict or set(pair) != {"input", "output"} or not grid_ok(pair["input"]) or not grid_ok(pair["output"]):
            return False
    if type(test[0]) is not dict or set(test[0]) != {"input"} or not grid_ok(test[0]["input"]):
        return False
    for row, pair in zip(rows, train):
        target = pair["output"]
        if row["target_shape"] != [len(target), len(target[0])]:
            return False
        if any(cell[3] != target[cell[0]][cell[1]] for cell in row["first_mismatches"]):
            return False
    return True


def _decode_records(raw):
    # Preserve a validated demo-fit record even if the query worker's later
    # output is truncated, oversized, malformed, or inconsistent.
    lines = raw.splitlines()
    if not lines:
        raise ValueError("worker record count")
    record = _strict_json(lines[0])
    if type(record) is not dict or set(record) != {"stage", "result"} or not _valid_result(record["result"]):
        raise ValueError("worker record schema")
    first = record["result"]
    if record["stage"] == "final":
        if len(raw) > MAX_OUTPUT_BYTES or len(lines) != 1 or first["all_demonstrations_exact"] or (first["error_category"] is None and not first["query_execution_success"]):
            raise ValueError("invalid final worker result")
        return None, first
    if record["stage"] != "query_pending" or not first["all_demonstrations_exact"] or first["candidate"] is not None or first["error_category"] is not None:
        raise ValueError("invalid query progress record")
    if len(raw) > MAX_OUTPUT_BYTES or len(lines) != 2:
        return first, None
    try:
        record = _strict_json(lines[1])
        if type(record) is not dict or set(record) != {"stage", "result"} or record["stage"] != "final" or not _valid_result(record["result"]):
            return first, None
        final = record["result"]
        if final["error_category"] is None and not final["query_execution_success"]:
            return first, None
        stable = ("format_admitted", "python_parse_admitted", "ast_admitted", "demo_execution_success", "all_demonstrations_exact", "feedback")
        if any(final[key] != first[key] for key in stable) or final["program_steps"] < first["program_steps"]:
            return first, None
        return first, final
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        return first, None


def verify_program(source, task, agent_path, *, timeout_seconds=3):
    """Verify one candidate using visible examples and exactly one query.

    Hard failures conservatively spend the candidate's full 200,000 gas budget.
    timeout_seconds may tighten, but never enlarge, the frozen three-second cap.
    """
    started = time.monotonic()
    result = _result()
    def finish(value):
        value["verification_seconds"] = time.monotonic() - started
        return value
    if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= MAX_WALL_SECONDS:
        raise ValueError("timeout must be positive and at most three seconds")
    if not _format_ok(source):
        return finish(_fail(result, "format", "raw bounded source must begin with def"))
    result["format_admitted"] = True
    try:
        payload = json.dumps({"source": source, "task": task}, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return finish(_fail(result, "task_schema", "invalid solver-visible task"))
    if len(payload) > MAX_INPUT_BYTES:
        return finish(_fail(result, "input_size", "solver input exceeds IPC limit"))
    command = [sys.executable, "-I", "-B", "-S", str(pathlib.Path(__file__).resolve()), "--worker", os.fspath(agent_path)]
    failure = None
    raw = b""
    # File-backed stdout/stderr avoid unbounded parent pipe accumulation. Worker
    # RLIMIT_FSIZE additionally bounds each output file before any JSON parsing.
    try:
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=output, stderr=errors, close_fds=True)
            try:
                try:
                    remaining = max(0.0, started + timeout_seconds - time.monotonic())
                    process.communicate(payload, timeout=remaining)
                except subprocess.TimeoutExpired:
                    failure = "worker_timeout"
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    process.communicate()
                if failure is None and process.returncode != 0:
                    failure = "worker_signal" if process.returncode < 0 else "worker_failure"
            finally:
                # Also covers KeyboardInterrupt/SystemExit and unexpected IPC
                # errors: no child may outlive this verification operation.
                try:
                    if process.poll() is None:
                        try:
                            process.kill()
                        except ProcessLookupError:
                            pass
                finally:
                    try:
                        process.wait()
                    finally:
                        if process.stdin is not None:
                            process.stdin.close()
            output.seek(0)
            raw = output.read(MAX_OUTPUT_BYTES + 1)
    except (OSError, subprocess.SubprocessError):
        failure = "worker_start_failure"
    try:
        progress, final = _decode_records(raw)
        submitted_task = _strict_json(payload)["task"]
        if progress is not None and not _result_binds_task(progress, submitted_task):
            progress = final = None
            failure = failure or "worker_output"
        if final is not None and not _result_binds_task(final, submitted_task):
            final = None
            failure = failure or "worker_output"
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError):
        progress = final = None
        failure = failure or "worker_output"
    if failure is None and final is not None:
        return finish(final)
    if failure is None:
        failure = "worker_output"
    if progress is not None:
        result = progress
        result["error_category"] = "query_" + failure
        result["query_execution_success"] = False
        result["candidate"] = None
    else:
        # An unknown phase is not mislabeled as a visible-demo error. This
        # absence of feedback is not evidence that demonstrations mismatched.
        result["error_category"] = failure
        result["feedback"]["error"] = None
    result["program_steps"] = MAX_PROGRAM_STEPS
    return finish(result)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--worker":
        raise SystemExit("internal CPU worker only")
    _worker_main(sys.argv[2])
