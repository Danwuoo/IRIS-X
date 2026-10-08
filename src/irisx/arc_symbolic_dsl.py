"""Finite, typed object/geometry search. No answer, source-solver or IO access.

One macro is extract -> select -> transform -> render (four AST nodes).
Programs are immutable data, never Python code. Every parameter domain is fixed
before search. Semantic dedup includes every demo AND every ordered test input.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass
import math
import time
from typing import Callable

from .canonical import canonical_bytes, digest_value
from .errors import ValidationError

SOLVER_ID = "irisx-object-geometry-dsl-v1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def grid(value: object) -> list[list[int]]:
    require(isinstance(value, list) and 1 <= len(value) <= 30,
            "grid rows must be 1..30")
    require(all(isinstance(row, list) and 1 <= len(row) <= 30 for row in value),
            "grid columns must be 1..30")
    require(all(len(row) == len(value[0]) for row in value), "rectangular grid required")
    require(all(type(cell) is int and 0 <= cell <= 9 for row in value for cell in row),
            "integer colors 0..9 required")
    return [row[:] for row in value]


def validate_task(task: object) -> dict:
    require(isinstance(task, dict) and set(task) == {"train", "test"},
            "task must contain only train/test")
    require(isinstance(task["train"], list) and 1 <= len(task["train"]) <= 32 and
            isinstance(task["test"], list) and 1 <= len(task["test"]) <= 32,
            "1..32 demonstrations and tests required")
    train, tests = [], []
    for pair in task["train"]:
        require(isinstance(pair, dict) and set(pair) == {"input", "output"},
                "demonstration must contain only input/output")
        train.append({"input": grid(pair["input"]), "output": grid(pair["output"])})
    for pair in task["test"]:
        require(isinstance(pair, dict) and set(pair) == {"input"},
                "test output/truth/extra fields forbidden")
        tests.append({"input": grid(pair["input"])})
    return {"train": train, "test": tests}


@dataclass(frozen=True)
class Limits:
    wall_seconds: float = 10.0
    max_states: int = 50_000
    max_depth: int = 3
    max_ast_nodes: int = 12
    max_candidates: int = 64
    cache_bytes: int = 256 * 1024 * 1024
    address_space_bytes: int = 1024 * 1024 * 1024
    loo: bool = False

    def validate(self) -> None:
        require(type(self.wall_seconds) in (int, float) and math.isfinite(self.wall_seconds)
                and 0 < self.wall_seconds <= 10, "wall cap must be >0 and <=10 seconds")
        for field, high in (("max_states", 50_000), ("max_depth", 3),
                            ("max_ast_nodes", 12), ("max_candidates", 64),
                            ("cache_bytes", 256 * 1024 * 1024),
                            ("address_space_bytes", 1024 * 1024 * 1024)):
            value = getattr(self, field)
            require(type(value) is int and 1 <= value <= high, "invalid " + field)
        require(self.max_depth * 4 <= self.max_ast_nodes, "macro expansion exceeds AST cap")
        require(type(self.loo) is bool, "loo must be boolean")


@dataclass(frozen=True)
class Macro:
    extract: str
    select: str
    transform: str
    render: str

    def value(self) -> dict:
        return asdict(self)


EXTRACTORS = ("grid", "foreground", "components4", "components8")
SELECTORS = ("all", "largest", "smallest") + tuple("color:" + str(c) for c in range(10))
TRANSFORMS = ("identity", "rot90", "rot180", "rot270", "flip_lr", "flip_ud", "transpose",
              "fill_bbox", "scale:2", "scale:3") + tuple("recolor:" + str(c) for c in range(10))
RENDERERS = ("canvas", "crop")


def grammar() -> tuple[Macro, ...]:
    """Fixed domain, 1,120 macros; no demo-output-derived parameter inventory."""
    return tuple(Macro(extract, select, transform, render)
                 for extract in EXTRACTORS
                 for select in (SELECTORS if extract.startswith("components") else ("all",))
                 for transform in TRANSFORMS for render in RENDERERS)


GRAMMAR = grammar()
GRAMMAR_SET = frozenset(GRAMMAR)
GRAMMAR_SPEC = {"format": "irisx/arc-object-grammar-v1",
                "macro_ast_nodes": 4, "selector_nesting": 1,
                "background": "most-frequent-color; ties choose smallest color",
                "selectors_ties": "largest/smallest choose first row-major object",
                "connectivity": "same-color foreground; 4 or 8 neighbors",
                "render_collisions": "different-color overlap rejected; equal-color overlap allowed",
                "canvas_bounds": "reject out-of-bounds; never clip",
                "state_representative": "first-enumerated minimum-depth joint semantics; canonical ranking uses retained programs",
                "macros": [macro.value() for macro in GRAMMAR]}


@dataclass(frozen=True)
class Object:
    row: int
    column: int
    height: int
    width: int
    # Local coordinates, including background pixels only for whole-grid objects.
    pixels: tuple[tuple[int, int, int], ...]


def _object(points: list[tuple[int, int, int]]) -> Object:
    top, left = min(p[0] for p in points), min(p[1] for p in points)
    bottom, right = max(p[0] for p in points), max(p[1] for p in points)
    return Object(top, left, bottom - top + 1, right - left + 1,
                  tuple(sorted((r - top, c - left, color) for r, c, color in points)))


def extract_objects(rows: list[list[int]], kind: str) -> tuple[int, tuple[Object, ...]]:
    require(kind in EXTRACTORS, "unknown extractor")
    counts = Counter(color for row in rows for color in row)
    background = min(counts, key=lambda c: (-counts[c], c))
    points = [(r, c, color) for r, row in enumerate(rows) for c, color in enumerate(row)
              if kind == "grid" or color != background]
    if kind in {"grid", "foreground"}:
        return background, (_object(points),) if points else ()
    remaining = {(r, c): color for r, c, color in points}
    objects = []
    neighbors = ((-1, 0), (0, -1), (0, 1), (1, 0))
    if kind == "components8":
        neighbors += ((-1, -1), (-1, 1), (1, -1), (1, 1))
    while remaining:
        start = min(remaining)
        color = remaining.pop(start)
        stack, component = [start], []
        while stack:
            row, column = stack.pop()
            component.append((row, column, color))
            for dr, dc in neighbors:
                point = row + dr, column + dc
                if remaining.get(point) == color:
                    remaining.pop(point)
                    stack.append(point)
        objects.append(_object(component))
    return background, tuple(objects)


def _select(objects: tuple[Object, ...], selector: str) -> tuple[Object, ...]:
    require(selector in SELECTORS, "unknown selector")
    if not objects or selector == "all":
        return objects
    if selector == "largest":
        return (min(objects, key=lambda o: (-len(o.pixels), o.row, o.column)),)
    if selector == "smallest":
        return (min(objects, key=lambda o: (len(o.pixels), o.row, o.column)),)
    color = int(selector.split(":")[1])
    return tuple(o for o in objects if all(p[2] == color for p in o.pixels))


def _transform(obj: Object, transform: str, background: int) -> Object:
    require(transform in TRANSFORMS, "unknown transform")
    h, w, pixels = obj.height, obj.width, obj.pixels
    if transform == "rot90":
        pixels, h, w = tuple((w - 1 - c, r, color) for r, c, color in pixels), w, h
    elif transform == "rot180":
        pixels = tuple((h - 1 - r, w - 1 - c, color) for r, c, color in pixels)
    elif transform == "rot270":
        pixels, h, w = tuple((c, h - 1 - r, color) for r, c, color in pixels), w, h
    elif transform == "flip_lr":
        pixels = tuple((r, w - 1 - c, color) for r, c, color in pixels)
    elif transform == "flip_ud":
        pixels = tuple((h - 1 - r, c, color) for r, c, color in pixels)
    elif transform == "transpose":
        pixels, h, w = tuple((c, r, color) for r, c, color in pixels), w, h
    elif transform == "fill_bbox":
        colors = {color for _, _, color in pixels if color != background}
        require(len(colors) == 1, "bbox fill requires one foreground color")
        color = next(iter(colors))
        pixels = tuple((r, c, color) for r in range(h) for c in range(w))
    elif transform.startswith("recolor:"):
        color = int(transform.split(":")[1])
        pixels = tuple((r, c, color if old != background else old) for r, c, old in pixels)
    elif transform.startswith("scale:"):
        scale = int(transform.split(":")[1])
        require(h * scale <= 30 and w * scale <= 30, "scaled object exceeds dimensions")
        pixels = tuple((r * scale + dr, c * scale + dc, color)
                       for r, c, color in pixels for dr in range(scale) for dc in range(scale))
        h, w = h * scale, w * scale
    return Object(obj.row, obj.column, h, w, tuple(sorted(pixels)))


def apply_macro(rows: list[list[int]], macro: Macro) -> list[list[int]]:
    """Closed typed evaluator; invalid empty crop, collision or bounds fail."""
    rows = grid(rows)
    require(type(macro) is Macro and all(type(v) is str for v in
            (macro.extract, macro.select, macro.transform, macro.render))
            and macro in GRAMMAR_SET, "macro outside frozen grammar")
    background, objects = extract_objects(rows, macro.extract)
    return _apply_extracted(rows, macro, background, objects)


def _apply_extracted(rows: list[list[int]], macro: Macro, background: int,
                     objects: tuple[Object, ...]) -> list[list[int]]:
    """Reviewed internal path: immutable extractor results may be reused."""
    objects = tuple(_transform(o, macro.transform, background) for o in _select(objects, macro.select))
    require(macro.render in RENDERERS, "unknown renderer")
    if macro.render == "crop":
        require(bool(objects), "empty crop")
        top, left = min(o.row for o in objects), min(o.column for o in objects)
        h = max(o.row + o.height for o in objects) - top
        w = max(o.column + o.width for o in objects) - left
    else:
        top, left, h, w = 0, 0, len(rows), len(rows[0])
    require(1 <= h <= 30 and 1 <= w <= 30, "rendered dimensions exceed bounds")
    output, occupied = [[background] * w for _ in range(h)], {}
    for obj in objects:
        for r, c, color in obj.pixels:
            point = obj.row + r - top, obj.column + c - left
            require(0 <= point[0] < h and 0 <= point[1] < w, "canvas out of bounds")
            require(point not in occupied or occupied[point] == color, "render collision")
            occupied[point] = color
            output[point[0]][point[1]] = color
    return output


def execute_program(rows: list[list[int]], program: list[dict]) -> list[list[int]]:
    require(isinstance(program, list) and 1 <= len(program) <= 3, "bounded macro program required")
    output = grid(rows)
    for node in program:
        require(isinstance(node, dict) and set(node) == {"extract", "select", "transform", "render"},
                "macro schema differs")
        output = apply_macro(output, Macro(**node))
    return output


class Budget:
    def __init__(self, limits: Limits, now: Callable[[], float]) -> None:
        self.limits, self.now = limits, now
        self.started = now()
        self.deadline = self.started + limits.wall_seconds
        self.states = 0
        self.retained_bytes = 0
        self.peak_cache_bytes = 0

    def note_cache(self, local_bytes: int) -> None:
        self.peak_cache_bytes = max(self.peak_cache_bytes, self.retained_bytes + local_bytes)

    def reserve(self) -> str | None:
        if self.now() >= self.deadline:
            return "wall_limit"
        if self.states >= self.limits.max_states:
            return "state_limit"
        self.states += 1
        return None


def semantic_signature(values: list[list[list[int]]]) -> bytes:
    """Full ordered semantics, never demonstrations alone or task IDs."""
    return canonical_bytes(values)


def _search(task: dict, budget: Budget) -> dict:
    limits = budget.limits
    cache_allowance = limits.cache_bytes - budget.retained_bytes
    inputs = [pair["input"] for pair in task["train"]] + [pair["input"] for pair in task["test"]]
    expected = [pair["output"] for pair in task["train"]]
    signature = semantic_signature(inputs)
    queue = deque([(inputs, [])])
    seen = {signature}
    cache_size = len(signature)
    candidates: dict[bytes, dict] = {}
    candidate_costs: dict[bytes, int] = {}
    candidate_bytes = 0
    faults = 0
    stop = "exhausted"
    if cache_size > cache_allowance:
        return {"candidates": [], "stop_reason": "cache_limit", "cache_bytes": 0,
                "unique_states": 0, "invalid_expansions": 0}
    budget.note_cache(cache_size)
    while queue:
        values, program = queue.popleft()
        if len(program) >= limits.max_depth:
            continue
        # Extraction depends only on the current immutable semantic state.
        # Reusing it does not merge states or alter expansion accounting.
        extracted = [{kind: extract_objects(rows, kind) for kind in EXTRACTORS} for rows in values]
        for macro in GRAMMAR:
            stop_now = budget.reserve()
            if stop_now:
                stop = stop_now
                queue.clear()
                break
            try:
                transformed = [_apply_extracted(rows, macro, *prepared[macro.extract])
                               for rows, prepared in zip(values, extracted)]
            except ValidationError:
                faults += 1
                continue
            next_program = program + [macro.value()]
            signature = semantic_signature(transformed)
            # Check fit before dedup: identity input semantics can still be a
            # valid one-step program; the root itself is not an emitted program.
            if transformed[:len(expected)] == expected:
                outputs = transformed[len(expected):]
                output_signature = semantic_signature(outputs)
                candidate = {"program": next_program, "outputs": outputs,
                             "ast_nodes": 4 * len(next_program)}
                previous = candidates.get(output_signature)
                key = lambda c: (c["ast_nodes"], canonical_bytes(c["program"]))
                if previous is None or key(candidate) < key(previous):
                    candidate_cost = len(output_signature) + len(canonical_bytes(candidate))
                    previous_cost = candidate_costs.get(output_signature, 0)
                    if cache_size + candidate_bytes + candidate_cost - previous_cost > cache_allowance:
                        stop = "cache_limit"
                        queue.clear()
                        break
                    candidates[output_signature] = candidate
                    candidate_costs[output_signature] = candidate_cost
                    candidate_bytes += candidate_cost - previous_cost
                    if len(candidates) > limits.max_candidates:
                        worst = max(candidates, key=lambda sig: key(candidates[sig]))
                        del candidates[worst]
                        candidate_bytes -= candidate_costs.pop(worst)
                    budget.note_cache(cache_size + candidate_bytes)
            if signature in seen:
                continue
            # Conservative explicit serialized cache accounting includes
            # retained semantics and program bytes for every unique state.
            cost = len(signature) + len(canonical_bytes(next_program))
            if cache_size + candidate_bytes + cost > cache_allowance:
                stop = "cache_limit"
                queue.clear()
                break
            seen.add(signature)
            cache_size += cost
            budget.note_cache(cache_size + candidate_bytes)
            if len(next_program) < limits.max_depth:
                queue.append((transformed, next_program))
    results = sorted(candidates.values(), key=lambda c: (c["ast_nodes"], canonical_bytes(c["program"])))
    # Wall cutoff is a fixed empty result, not an arbitrary scheduling-dependent
    # partial pool. State/cache caps retain a reproducible deterministic prefix.
    if stop == "wall_limit":
        results = []
    return {"candidates": results, "stop_reason": stop, "cache_bytes": cache_size + candidate_bytes,
            "unique_states": len(seen), "invalid_expansions": faults}


def search(task: object, limits: Limits = Limits(), *, now: Callable[[], float] = time.monotonic) -> dict:
    """Cooperative reference search; use isolated runner for the hard wall cap.

    All LOO folds exclude the held-out demo before a fresh search. Main and
    folds share one task budget. Unsupported/fewer than three demos/incomplete
    folds report null support. Fit on visible demos is never test correctness.
    """
    limits.validate()
    task = validate_task(task)
    budget = Budget(limits, now)
    cpu_start = time.process_time()
    result = _search(task, budget)
    loo = None
    if limits.loo and len(task["train"]) >= 3 and result["stop_reason"] == "exhausted":
        # Main states/seen set are released when _search returns, but the main
        # candidate list is still live while each fold runs. Reserve its entire
        # serialized size against every fold's available cache budget.
        budget.retained_bytes = len(canonical_bytes(result["candidates"]))
        folds = []
        for index, held in enumerate(task["train"]):
            fold = {"train": [p for i, p in enumerate(task["train"]) if i != index],
                    "test": [{"input": held["input"]}] + task["test"]}
            measured = _search(fold, budget)
            if measured["stop_reason"] != "exhausted":
                del measured
                break
            ranked = measured["candidates"]
            folds.append(bool(ranked and ranked[0]["outputs"][0] == held["output"]))
            # Do not keep the prior fold's candidates during the next RHS call.
            del ranked, measured
        if len(folds) == len(task["train"]):
            loo = {"kind": "leave-one-demonstration-out-top-one", "folds": len(folds),
                   "supported": sum(folds), "shared_task_budget": True}
    wall = max(0.0, now() - budget.started)
    if wall >= limits.wall_seconds:
        result.update(candidates=[], stop_reason="wall_limit")
        loo = None
    result["cache_bytes"] = budget.peak_cache_bytes
    return {"format": "irisx/arc-dsl-search-v1", "solver_id": SOLVER_ID,
            "task_digest": digest_value(task), "config_digest": digest_value(asdict(limits)),
            "grammar_digest": digest_value(GRAMMAR_SPEC), "limits": asdict(limits),
            **result, "states": budget.states, "loo_support": loo,
            "wall_seconds": wall, "cpu_seconds": time.process_time() - cpu_start,
            "native_verification": None, "correctness_scored": False}
