"""CPU reference ARC proposal/check/repair harness, independent of model backend.

Generated Python syntax is interpreted as data, never compiled or executed by
Python. This is an intentionally small language, not a Python security sandbox.
All language objects are bounded ints, bools, None, lists and tuples; there is no
attribute access, import, host object, file, network or dynamic-code capability.
The caller must put blocking model calls behind its own enforced worker deadline.
No evaluator answers or model training are imported by this module.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Callable


class ProgramError(ValueError):
    pass


class BudgetError(ProgramError):
    pass


@dataclass(frozen=True)
class Limits:
    max_calls: int = 4
    max_generated_tokens: int = 8192
    max_prompt_tokens: int = 32768
    max_context_tokens: int = 8192
    max_new_tokens_per_call: int = 2048
    max_wall_seconds: float = 300.0
    max_program_steps: int = 200000
    max_total_program_steps: int = 800000
    max_ast_nodes: int = 2048
    max_source_bytes: int = 32768
    max_container_items: int = 16384
    max_value_depth: int = 16
    max_call_depth: int = 12
    max_functions: int = 8
    max_locals: int = 128
    max_integer: int = 1000000

    def validate(self):
        for key, value in asdict(self).items():
            if key == "max_wall_seconds":
                if type(value) not in (int, float) or not 0 < value <= 86400:
                    raise ValueError("invalid wall limit")
            elif type(value) is not int or value <= 0:
                raise ValueError("positive integer limit required: " + key)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def validate_grid(value):
    if (type(value) is not list or not 1 <= len(value) <= 30
            or any(type(row) is not list for row in value)
            or not 1 <= len(value[0]) <= 30
            or any(len(row) != len(value[0]) for row in value)
            or any(type(cell) is not int or not 0 <= cell <= 9
                   for row in value for cell in row)):
        raise ProgramError("expected rectangular 1..30 grid with integer colors 0..9")
    return value


def validate_task(task):
    if type(task) is not dict or set(task) != {"train", "test"}:
        raise ValueError("task must contain exactly train and test")
    if not isinstance(task["train"], list) or not 1 <= len(task["train"]) <= 10:
        raise ValueError("expected 1..10 demonstrations")
    if not isinstance(task["test"], list) or not 1 <= len(task["test"]) <= 10:
        raise ValueError("expected 1..10 test inputs")
    for pair in task["train"]:
        if type(pair) is not dict or set(pair) != {"input", "output"}:
            raise ValueError("invalid demonstration")
        validate_grid(pair["input"])
        validate_grid(pair["output"])
    for pair in task["test"]:
        if type(pair) is not dict or set(pair) != {"input"}:
            raise ValueError("test truth and metadata are forbidden")
        validate_grid(pair["input"])
    return copy.deepcopy(task)


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class _Interpreter:
    """Small bounded evaluator; builtins are manually dispatched by name."""

    def __init__(self, source, limits):
        self.limits = limits
        self.steps = 0
        self.depth = 0
        if type(source) is not str:
            raise ProgramError("source must be text")
        try:
            source_bytes = source.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ProgramError("source is not valid UTF-8") from exc
        if len(source_bytes) > limits.max_source_bytes:
            raise ProgramError("source size limit")
        try:
            tree = ast.parse(source)
        except (SyntaxError, RecursionError, MemoryError) as exc:
            raise ProgramError("invalid source syntax") from exc
        nodes = list(ast.walk(tree))
        if len(nodes) > limits.max_ast_nodes:
            raise ProgramError("AST size limit")
        allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
                   ast.Assign, ast.AugAssign, ast.Expr, ast.If, ast.For, ast.Break,
                   ast.Continue, ast.Pass, ast.Name, ast.Constant, ast.List, ast.Tuple,
                   ast.Subscript, ast.Slice, ast.BinOp, ast.UnaryOp, ast.BoolOp,
                   ast.Compare, ast.IfExp, ast.Call, ast.ListComp, ast.comprehension,
                   ast.Load, ast.Store, ast.Add, ast.Sub, ast.Mult, ast.FloorDiv,
                   ast.Mod, ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq,
                   ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)
        if any(not isinstance(node, allowed) for node in nodes):
            raise ProgramError("unsupported syntax")
        if any(isinstance(n, ast.Name) and n.id.startswith("_") for n in nodes):
            raise ProgramError("private identifiers forbidden")
        self.functions = {}
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                raise ProgramError("top level must contain function definitions only")
            a = node.args
            if (node.decorator_list or node.returns or a.posonlyargs or a.vararg
                    or a.kwarg or a.kwonlyargs or a.defaults or a.kw_defaults
                    or any(arg.annotation for arg in a.args)
                    or node.name.startswith("_") or node.name in self.functions
                    or len(a.args) > limits.max_locals
                    or any(arg.arg.startswith("_") for arg in a.args)
                    or len({arg.arg for arg in a.args}) != len(a.args)):
                raise ProgramError("unsupported function definition")
            self.functions[node.name] = node
        if not 1 <= len(self.functions) <= limits.max_functions or "transform" not in self.functions:
            raise ProgramError("define transform(grid), with bounded helper functions")
        if len(self.functions["transform"].args.args) != 1:
            raise ProgramError("transform must have one argument")

    def tick(self, n=1):
        if self.steps + n > self.limits.max_program_steps:
            self.steps = self.limits.max_program_steps
            raise BudgetError("program step limit")
        self.steps += n

    def bounded(self, value):
        count = 0
        def walk(item, depth, ancestors):
            nonlocal count
            self.tick()
            count += 1
            if count > self.limits.max_container_items or depth > self.limits.max_value_depth:
                raise BudgetError("value size or depth limit")
            if type(item) is int:
                if abs(item) > self.limits.max_integer:
                    raise BudgetError("integer magnitude limit")
            elif item is None or type(item) is bool:
                return
            elif type(item) in (list, tuple):
                if id(item) in ancestors:
                    raise ProgramError("cyclic containers forbidden")
                for child in item:
                    walk(child, depth + 1, ancestors | {id(item)})
            else:
                raise ProgramError("unsupported value type")
        walk(value, 0, set())
        return value

    def seq(self, value):
        if type(value) not in (list, tuple):
            raise ProgramError("expected list or tuple")
        return value

    def integer(self, value):
        if type(value) is not int:
            raise ProgramError("expected integer")
        return value

    def bind(self, target, value, env):
        self.tick()
        self.bounded(value)
        if isinstance(target, ast.Name):
            if target.id not in env and len(env) >= self.limits.max_locals:
                raise BudgetError("local variable limit")
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            self.seq(value)
            if len(target.elts) != len(value):
                raise ProgramError("unpack length mismatch")
            for t, v in zip(target.elts, value):
                self.bind(t, v, env)
        elif isinstance(target, ast.Subscript):
            seq = self.expression(target.value, env)
            if type(seq) is not list or isinstance(target.slice, ast.Slice):
                raise ProgramError("only list integer-index assignment allowed")
            index = self.integer(self.expression(target.slice, env))
            seq[index] = value
            self.bounded(seq)
        else:
            raise ProgramError("invalid assignment target")

    def block(self, statements, env):
        for node in statements:
            self.tick()
            if isinstance(node, ast.Return):
                raise _Return(None if node.value is None else self.expression(node.value, env))
            if isinstance(node, ast.Assign):
                value = self.expression(node.value, env)
                for target in node.targets:
                    self.bind(target, value, env)
            elif isinstance(node, ast.AugAssign):
                value = self.binary(node.op, self.expression(node.target, env),
                                    self.expression(node.value, env))
                self.bind(node.target, value, env)
            elif isinstance(node, ast.Expr):
                self.expression(node.value, env)
            elif isinstance(node, ast.If):
                self.block(node.body if self.expression(node.test, env) else node.orelse, env)
            elif isinstance(node, ast.For):
                values = tuple(self.seq(self.expression(node.iter, env)))
                broke = False
                for value in values:
                    self.tick()
                    self.bind(node.target, value, env)
                    try:
                        self.block(node.body, env)
                    except _Continue:
                        continue
                    except _Break:
                        broke = True
                        break
                if not broke:
                    self.block(node.orelse, env)
            elif isinstance(node, ast.Break):
                raise _Break()
            elif isinstance(node, ast.Continue):
                raise _Continue()
            elif isinstance(node, ast.Pass):
                pass
            else:
                raise ProgramError("unsupported statement")

    def binary(self, operator, left, right):
        self.tick()
        if isinstance(operator, ast.Add) and type(left) is type(right) and type(left) in (list, tuple):
            if len(left) + len(right) > self.limits.max_container_items:
                raise BudgetError("sequence allocation limit")
            return self.bounded(left + right)
        if isinstance(operator, ast.Mult) and (type(left) in (list, tuple) or type(right) in (list, tuple)):
            seq, n = (left, right) if type(left) in (list, tuple) else (right, left)
            self.integer(n)
            if len(seq) * max(0, n) > self.limits.max_container_items:
                raise BudgetError("sequence allocation limit")
            return self.bounded(seq * n)
        self.integer(left)
        self.integer(right)
        if isinstance(operator, ast.Add): result = left + right
        elif isinstance(operator, ast.Sub): result = left - right
        elif isinstance(operator, ast.Mult): result = left * right
        elif isinstance(operator, ast.FloorDiv): result = left // right
        elif isinstance(operator, ast.Mod): result = left % right
        else: raise ProgramError("unsupported binary operator")
        return self.bounded(result)

    def expression(self, node, env):
        self.tick()
        if isinstance(node, ast.Constant):
            return self.bounded(node.value)
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise ProgramError("unknown variable: " + node.id)
            return env[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            values = [self.expression(n, env) for n in node.elts]
            return self.bounded(values if isinstance(node, ast.List) else tuple(values))
        if isinstance(node, ast.Subscript):
            values = self.seq(self.expression(node.value, env))
            if isinstance(node.slice, ast.Slice):
                parts = [None if p is None else self.integer(self.expression(p, env))
                         for p in (node.slice.lower, node.slice.upper, node.slice.step)]
                return self.bounded(values[slice(*parts)])
            return values[self.integer(self.expression(node.slice, env))]
        if isinstance(node, ast.BinOp):
            return self.binary(node.op, self.expression(node.left, env), self.expression(node.right, env))
        if isinstance(node, ast.UnaryOp):
            value = self.expression(node.operand, env)
            if isinstance(node.op, ast.Not): return not value
            self.integer(value)
            return self.bounded(-value if isinstance(node.op, ast.USub) else value)
        if isinstance(node, ast.BoolOp):
            for child in node.values:
                value = self.expression(child, env)
                if isinstance(node.op, ast.And) and not value: return value
                if isinstance(node.op, ast.Or) and value: return value
            return value
        if isinstance(node, ast.Compare):
            left = self.expression(node.left, env)
            for op, child in zip(node.ops, node.comparators):
                right = self.expression(child, env)
                self.bounded(left)
                self.bounded(right)
                if isinstance(op, ast.Eq): ok = left == right
                elif isinstance(op, ast.NotEq): ok = left != right
                elif isinstance(op, ast.Lt): ok = left < right
                elif isinstance(op, ast.LtE): ok = left <= right
                elif isinstance(op, ast.Gt): ok = left > right
                elif isinstance(op, ast.GtE): ok = left >= right
                elif isinstance(op, ast.In): ok = left in self.seq(right)
                elif isinstance(op, ast.NotIn): ok = left not in self.seq(right)
                else: raise ProgramError("unsupported comparison")
                if not ok: return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return self.expression(node.body if self.expression(node.test, env) else node.orelse, env)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.keywords:
                raise ProgramError("only named calls with positional arguments allowed")
            return self.call(node.func.id, [self.expression(a, env) for a in node.args])
        if isinstance(node, ast.ListComp):
            result = []
            local = dict(env)
            def visit(index):
                self.tick()
                if index == len(node.generators):
                    if len(result) >= self.limits.max_container_items:
                        raise BudgetError("comprehension allocation limit")
                    result.append(self.expression(node.elt, local))
                    return
                gen = node.generators[index]
                if gen.is_async:
                    raise ProgramError("async forbidden")
                for value in tuple(self.seq(self.expression(gen.iter, local))):
                    self.bind(gen.target, value, local)
                    if all(self.expression(cond, local) for cond in gen.ifs):
                        visit(index + 1)
            visit(0)
            return self.bounded(result)
        raise ProgramError("unsupported expression")

    def call(self, name, args):
        self.tick()
        for value in args:
            self.bounded(value)
        if name in self.functions:
            if self.depth >= self.limits.max_call_depth:
                raise BudgetError("call depth limit")
            fn = self.functions[name]
            if len(args) != len(fn.args.args):
                raise ProgramError("argument count mismatch")
            self.depth += 1
            try:
                self.block(fn.body, {a.arg: v for a, v in zip(fn.args.args, args)})
            except _Return as ret:
                return self.bounded(ret.value)
            finally:
                self.depth -= 1
            return None
        if name == "len" and len(args) == 1:
            return len(self.seq(args[0]))
        if name == "range" and 1 <= len(args) <= 3:
            for value in args: self.integer(value)
            seq = range(*args)
            if len(seq) > self.limits.max_container_items:
                raise BudgetError("range allocation limit")
            return self.bounded(list(seq))
        if name == "enumerate" and len(args) == 1:
            return self.bounded(list(enumerate(self.seq(args[0]))))
        if name == "zip" and 1 <= len(args) <= 8:
            return self.bounded(list(zip(*(self.seq(v) for v in args))))
        if name in {"min", "max", "sum", "sorted", "reversed", "unique"} and len(args) == 1:
            values = self.seq(args[0])
            for value in values: self.integer(value)
            self.tick(len(values) * max(1, len(values).bit_length()))
            if name == "min": value = min(values)
            elif name == "max": value = max(values)
            elif name == "sum": value = sum(values)
            elif name == "sorted": value = sorted(values)
            elif name == "reversed": value = list(reversed(values))
            else: value = sorted(set(values))
            return self.bounded(value)
        if name == "abs" and len(args) == 1:
            return abs(self.integer(args[0]))
        if name == "append" and len(args) == 2 and type(args[0]) is list:
            if len(args[0]) >= self.limits.max_container_items:
                raise BudgetError("append allocation limit")
            args[0].append(args[1])
            self.bounded(args[0])
            return None
        if name == "copy_grid" and len(args) == 1:
            validate_grid(args[0])
            return self.bounded([list(row) for row in args[0]])
        if name == "new_grid" and len(args) == 3:
            h, w, color = (self.integer(v) for v in args)
            if not 1 <= h <= 30 or not 1 <= w <= 30 or not 0 <= color <= 9:
                raise ProgramError("new_grid bounds")
            return self.bounded([[color for _ in range(w)] for _ in range(h)])
        if name == "transpose" and len(args) == 1:
            validate_grid(args[0])
            return self.bounded([list(row) for row in zip(*args[0])])
        if name == "crop" and len(args) == 5:
            grid, r0, c0, r1, c1 = args
            validate_grid(grid)
            for v in args[1:]: self.integer(v)
            if not 0 <= r0 < r1 <= len(grid) or not 0 <= c0 < c1 <= len(grid[0]):
                raise ProgramError("crop bounds")
            return self.bounded([row[c0:c1] for row in grid[r0:r1]])
        if name == "components" and len(args) == 3:
            grid, background, connectivity = args
            validate_grid(grid)
            self.integer(background)
            self.integer(connectivity)
            if not 0 <= background <= 9 or connectivity not in (4, 8):
                raise ProgramError("components requires background color and connectivity 4 or 8")
            # Same-color components; return objects of [row, column, color] pixels.
            seen, result = set(), []
            for r in range(len(grid)):
                for c in range(len(grid[0])):
                    self.tick()
                    if (r, c) in seen or grid[r][c] == background:
                        continue
                    pending, component = [(r, c)], []
                    seen.add((r, c))
                    while pending:
                        rr, cc = pending.pop()
                        component.append([rr, cc, grid[rr][cc]])
                        for dr, dc in ((-1, 0), (0, -1), (0, 1), (1, 0),
                                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
                            self.tick()
                            if connectivity == 4 and dr and dc:
                                continue
                            nr, nc = rr + dr, cc + dc
                            if (0 <= nr < len(grid) and 0 <= nc < len(grid[0])
                                    and (nr, nc) not in seen and grid[nr][nc] == grid[r][c]):
                                seen.add((nr, nc))
                                pending.append((nr, nc))
                    result.append(sorted(component))
            return self.bounded(result)
        raise ProgramError("unknown or incorrectly called primitive: " + name)


def execute_program(source, grid, limits=Limits()):
    """Return output and consumed interpreter steps; never mutate caller input."""
    limits.validate()
    validate_grid(grid)
    machine = _Interpreter(source, limits)
    try:
        result = machine.call("transform", [copy.deepcopy(grid)])
        return {"output": copy.deepcopy(validate_grid(result)), "steps": machine.steps}
    except (ProgramError, IndexError, ZeroDivisionError, TypeError, ValueError,
            RecursionError, _Break, _Continue) as exc:
        if isinstance(exc, ProgramError):
            exc.steps = machine.steps
            raise
        error = ProgramError("program runtime error: " + type(exc).__name__)
        error.steps = machine.steps
        raise error from exc


PROGRAM_INSTRUCTIONS = (
    "Return one JSON object with kind=program and source defining transform(grid). "
    "Use only integer/bool/None, lists/tuples, indexing/slices, arithmetic + - * // %, "
    "comparisons, if, for, list comprehensions, break/continue, return, and named helper "
    "functions. No imports, attributes, strings, dicts, while, exceptions or host APIs. "
    "Primitives: len(xs), range(stop) or range(start,stop,step), enumerate(xs), zip(xs,ys), "
    "min/max/sum/sorted/reversed/unique(integer_list), abs(n), append(xs,x), copy_grid(g), "
    "new_grid(height,width,color), transpose(g), crop(g,r0,c0,r1,c1) with exclusive end. "
    "components(g,background,connectivity) gives same-color objects as lists of [row,col,color] "
    "pixels, with connectivity 4 or 8. Choose background from evidence rather than assuming 0. "
    "Use generic loops and conditionals to build new transformations. Return a rectangular "
    "1..30 integer grid with colors 0..9. Fit every demonstration with the same function."
)


def _feedback(source, task, limits, remaining_steps):
    rows, outputs, steps = [], [], 0
    error = None
    for index, pair in enumerate(task["train"]):
        available = min(limits.max_program_steps - steps, remaining_steps - steps)
        if available <= 0:
            error = "program work exhausted"
            break
        local = Limits(**{**asdict(limits), "max_program_steps": available})
        try:
            run = execute_program(source, pair["input"], local)
            steps += run["steps"]
            prediction = run["output"]
            target = pair["output"]
            same_shape = (len(prediction), len(prediction[0])) == (len(target), len(target[0]))
            mismatch = ([] if not same_shape else
                        [[r, c, prediction[r][c], target[r][c]]
                         for r in range(len(target)) for c in range(len(target[0]))
                         if prediction[r][c] != target[r][c]])
            rows.append({"demo_index": index, "exact": prediction == target,
                         "shape_match": same_shape, "predicted_shape": [len(prediction), len(prediction[0])],
                         "target_shape": [len(target), len(target[0])],
                         "mismatch_count": len(mismatch) if same_shape else None,
                         "first_mismatches": mismatch[:12]})
        except ProgramError as exc:
            steps += getattr(exc, "steps", 0)
            error = str(exc)
            break
    demo_exact = len(rows) == len(task["train"]) and all(row["exact"] for row in rows)
    if demo_exact:
        for pair in task["test"]:
            available = min(limits.max_program_steps - steps, remaining_steps - steps)
            if available <= 0:
                error = "program work exhausted"
                break
            local = Limits(**{**asdict(limits), "max_program_steps": available})
            try:
                run = execute_program(source, pair["input"], local)
                steps += run["steps"]
                outputs.append(run["output"])
            except ProgramError as exc:
                steps += getattr(exc, "steps", 0)
                error = str(exc)
                break
    return {"demonstrations": rows, "all_demonstrations_exact": demo_exact,
            "error": error, "program_steps": steps,
            "outputs": outputs if len(outputs) == len(task["test"]) and error is None else None}


def solve_task(task, arm, model: Callable, count_prompt_tokens: Callable,
               limits=Limits(), seed=0, expected_model_id=None):
    """Run one fixed-weight A/B/C arm with explicit measured model-call accounting.

    model(request) -> {text,prompt_tokens,generated_tokens,model_id,finish_reason}.
    count_prompt_tokens(messages) must use the exact deployed chat template.
    A blocking callback requires an outer enforced deadline; this function only
    enforces admission and detects deadline overrun after a callback returns.
    """
    limits.validate()
    task = validate_task(task)
    if arm not in {"grid", "program", "repair"}:
        raise ValueError("unknown arm")
    start = time.monotonic()
    calls, candidates, feedbacks = [], [], []
    totals = {"prompt_tokens": 0, "generated_tokens": 0, "program_steps": 0}
    instruction = ("Return one JSON object with kind=grid and outputs containing one "
                   "rectangular integer grid per ordered test input. Infer a rule from all demonstrations."
                   if arm == "grid" else PROGRAM_INSTRUCTIONS)
    initial = [{"role": "system", "content": instruction},
               {"role": "user", "content": json.dumps(task, separators=(",", ":"))}]
    messages = copy.deepcopy(initial)
    terminal, usage_known = "call_limit", True
    active_model_id = expected_model_id
    for index in range(limits.max_calls):
        if time.monotonic() - start >= limits.max_wall_seconds:
            terminal = "wall_deadline"
            break
        if arm != "grid" and totals["program_steps"] >= limits.max_total_program_steps:
            terminal = "program_work_budget"
            break
        prompt = count_prompt_tokens(copy.deepcopy(messages))
        if type(prompt) is not int or prompt <= 0:
            raise ValueError("exact positive prompt token count required")
        if time.monotonic() - start >= limits.max_wall_seconds:
            terminal = "wall_deadline"
            break
        output_allowance = min(limits.max_new_tokens_per_call,
                               limits.max_generated_tokens - totals["generated_tokens"],
                               limits.max_context_tokens - prompt)
        if output_allowance <= 0 or totals["prompt_tokens"] + prompt > limits.max_prompt_tokens:
            terminal = "token_budget"
            break
        request = {"messages": copy.deepcopy(messages), "max_new_tokens": output_allowance,
                   "seed": seed + index, "call_id": index,
                   "deadline_monotonic": start + limits.max_wall_seconds}
        event = {"call_id": index, "prompt_digest": _digest(messages),
                 "reserved_prompt_tokens": prompt, "max_new_tokens": output_allowance,
                 "status": "attempted", "prompt_tokens": None, "generated_tokens": None,
                 "model_id": None, "finish_reason": None}
        before = time.monotonic()
        if before - start >= limits.max_wall_seconds:
            terminal = "wall_deadline"
            break
        calls.append(event)
        try:
            response = model(request)
        except Exception as exc:
            event.update(status="callback_error", elapsed_seconds=time.monotonic() - before,
                         error_type=type(exc).__name__)
            usage_known, terminal = False, "unknown_usage_callback_failure"
            break
        event["elapsed_seconds"] = time.monotonic() - before
        required = {"text", "prompt_tokens", "generated_tokens", "model_id", "finish_reason"}
        if (type(response) is not dict or not required.issubset(response)
                or type(response["text"]) is not str
                or type(response["prompt_tokens"]) is not int or response["prompt_tokens"] < 0
                or type(response["generated_tokens"]) is not int or response["generated_tokens"] < 0
                or type(response["model_id"]) is not str or not response["model_id"]
                or type(response["finish_reason"]) is not str):
            event["status"], terminal, usage_known = "invalid_usage", "unknown_usage_invalid_response", False
            break
        for field in required - {"text"}: event[field] = response[field]
        totals["prompt_tokens"] += response["prompt_tokens"]
        totals["generated_tokens"] += response["generated_tokens"]
        event["response_digest"] = _digest(response["text"])
        event["response_text"] = response["text"]
        if active_model_id is None: active_model_id = response["model_id"]
        if (response["prompt_tokens"] != prompt or response["generated_tokens"] > output_allowance
                or response["model_id"] != active_model_id):
            event["status"], terminal = "contract_violation", "model_contract_violation"
            break
        if time.monotonic() - start >= limits.max_wall_seconds:
            event["status"], terminal = "late_response", "wall_deadline"
            break
        event["status"] = "completed"
        candidate, feedback = None, None
        try:
            if len(response["text"].encode()) > limits.max_source_bytes * 2:
                raise ProgramError("response size limit")
            payload = json.loads(response["text"])
            if arm == "grid":
                if type(payload) is not dict or set(payload) != {"kind", "outputs"} or payload["kind"] != "grid":
                    raise ProgramError("invalid grid response schema")
                outputs = payload["outputs"]
                if type(outputs) is not list or len(outputs) != len(task["test"]):
                    raise ProgramError("one output per test required")
                for grid in outputs: validate_grid(grid)
                candidate = {"kind": "direct-grid", "outputs": outputs,
                             "demo_evidence": "not_applicable", "source": None}
            else:
                if type(payload) is not dict or set(payload) != {"kind", "source"} or payload["kind"] != "program":
                    raise ProgramError("invalid program response schema")
                feedback = _feedback(payload["source"], task, limits,
                                     limits.max_total_program_steps - totals["program_steps"])
                totals["program_steps"] += feedback["program_steps"]
                if feedback["outputs"] is not None:
                    candidate = {"kind": "interpreted-program", "outputs": feedback["outputs"],
                                 "demo_evidence": "all-demonstrations-exact-fit",
                                 "source": payload["source"]}
        except (ValueError, UnicodeError, RecursionError) as exc:
            feedback = {"error": str(exc), "all_demonstrations_exact": False,
                        "program_steps": 0, "outputs": None, "demonstrations": []}
        if feedback is not None:
            feedbacks.append({"call_id": index, **feedback})
        if time.monotonic() - start >= limits.max_wall_seconds:
            event["candidate_rejected"] = "verification_deadline"
            terminal = "wall_deadline"
            break
        if candidate is not None:
            candidate.update(call_id=index, digest=_digest(candidate["outputs"]),
                             lodo_status="not_run")
            candidate["admitted_at_seconds"] = time.monotonic() - start
            candidate["usage_at_admission"] = dict(totals)
            candidates.append(candidate)
        if arm == "repair" and feedback is not None and feedback["outputs"] is None:
            # Oversize model text is not copied unbounded into future contexts.
            prior = response["text"][:limits.max_source_bytes]
            messages = initial + [{"role": "assistant", "content": prior},
                                  {"role": "user", "content": "Repair using only this demonstration feedback: " +
                                   json.dumps(feedback, separators=(",", ":"))}]
        else:
            messages = copy.deepcopy(initial)
    unique = {}
    for candidate in candidates:
        key = candidate["digest"]
        if key not in unique: unique[key] = {**candidate, "votes": 0}
        unique[key]["votes"] += 1
    ranked = sorted(unique.values(), key=lambda c: (-c["votes"], c["call_id"], c["digest"]))
    selected = []
    for test_index in range(len(task["test"])):
        distinct = []
        for candidate in ranked:
            grid = candidate["outputs"][test_index]
            if grid not in distinct: distinct.append(grid)
        selected.append({"test_index": test_index, "attempts": distinct[:2]})
    return {"format": "irisx/arc-next-agent-v1", "arm": arm, "task_digest": _digest(task),
            "limits": asdict(limits), "model_id": active_model_id, "seed": seed,
            "calls": calls, "usage": totals, "usage_known": usage_known,
            "terminal_reason": terminal, "elapsed_seconds": time.monotonic() - start,
            "candidates": candidates, "ranked_candidates": ranked, "feedback": feedbacks,
            "selected": selected, "correctness_scored": False, "lodo_status": "not_run",
            "selection_policy": "whole-task-vector-vote_then-first-call_then-digest; distinct-per-test",
            "program_work_unit": "bounded-interpreter-gas; not hardware instruction count",
            "hard_model_deadline_enforced": False}
