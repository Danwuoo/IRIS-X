"""Trusted, finite typed-plan compiler. Generated source is never host-executed.

The interface accepts one to three operations. The N12 search inventory is an
explicitly smaller finite language: every atomic parameterization and selected
two-operation compositions, as documented by grammar_manifest().
"""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import math

IR_VERSION = "irisx/typed-ir-v1"
GRAMMAR_VERSION = "irisx/finite-grammar-v1"
MAX_PLAN_BYTES = 4096
MAX_SOURCE_BYTES = 32768
MAX_AST_NODES = 2048
MAX_STEPS = 3
PARAMETERS = {
    "identity": {}, "flip_horizontal": {}, "flip_vertical": {},
    "rotate": {"turns": (1, 2, 3)}, "transpose": {},
    "recolor": {"source": tuple(range(10)), "target": tuple(range(10))},
    "crop_nonbackground": {"background": tuple(range(10))},
    "scale": {"factor": (2, 3)},
    "tile": {"rows": (1, 2, 3), "columns": (1, 2, 3)},
    "largest_component_crop": {"background": tuple(range(10)), "connectivity": (4, 8)},
}


class PlanError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_plan(plan):
    """Return a fresh canonical plan or reject all unsupported structure/types."""
    if type(plan) is not dict or set(plan) != {"steps"}:
        raise PlanError("plan must contain exactly steps")
    if type(plan["steps"]) is not list or not 1 <= len(plan["steps"]) <= MAX_STEPS:
        raise PlanError("steps must be a list of one to three operations")
    steps = []
    for step in plan["steps"]:
        if type(step) is not dict or type(step.get("op")) is not str:
            raise PlanError("operation must be an object with a string op")
        op = step["op"]
        if op not in PARAMETERS or set(step) != {"op", *PARAMETERS[op]}:
            raise PlanError("unknown operation or incorrect parameter keys")
        row = {"op": op}
        for key, choices in PARAMETERS[op].items():
            if type(step[key]) is not int or step[key] not in choices:
                raise PlanError("invalid integer parameter: " + key)
            row[key] = step[key]
        if op == "recolor" and row["source"] == row["target"]:
            raise PlanError("recolor must change the color")
        if op == "tile" and row["rows"] == row["columns"] == 1:
            raise PlanError("tile must repeat at least one axis")
        steps.append(row)
    return {"steps": steps}


def parse_plan(text):
    if type(text) is not str:
        raise PlanError("plan must be raw JSON text")
    try:
        if len(text.encode("utf-8", "strict")) > MAX_PLAN_BYTES:
            raise PlanError("plan byte limit")
        def pairs(items):
            out = {}
            for key, value in items:
                if key in out:
                    raise PlanError("duplicate JSON key")
                out[key] = value
            return out
        def no_float(_):
            raise PlanError("floating-point and nonfinite values are forbidden")
        value = json.loads(text, object_pairs_hook=pairs,
                           parse_float=no_float, parse_constant=no_float)
        return validate_plan(value)
    except (UnicodeError, RecursionError, ValueError, TypeError) as exc:
        if isinstance(exc, PlanError):
            raise
        raise PlanError("invalid bounded JSON plan") from exc


def compile_plan(plan):
    """Compile validated data through fixed templates into bounded AST syntax.

    Horizontal flip reverses columns; vertical flip reverses rows. Rotation is
    clockwise. Crops preserve all original pixels inside the selected rectangle.
    Empty foreground crops copy the input. Largest-component ties use the first
    row-major same-color component (the interpreter primitive's stable order).
    Scale/tile have a checked runtime domain: resulting axes must be <=30.
    """
    plan = validate_plan(plan)
    lines = ["def transform(grid):", "    g = copy_grid(grid)"]
    def add(text):
        lines.extend("    " + line for line in text.splitlines())
    for step in plan["steps"]:
        op = step["op"]
        if op == "identity":
            add("g = copy_grid(g)")
        elif op == "flip_horizontal":
            add("g = [row[::-1] for row in g]")
        elif op == "flip_vertical":
            add("g = g[::-1]")
        elif op == "transpose":
            add("g = transpose(g)")
        elif op == "rotate":
            for _ in range(step["turns"]):
                add("g = [row[::-1] for row in transpose(g)]")
        elif op == "recolor":
            add("g = [[%d if cell == %d else cell for cell in row] for row in g]" %
                (step["target"], step["source"]))
        elif op == "crop_nonbackground":
            add("h = len(g)\nw = len(g[0])\nr0 = h\nc0 = w\nr1 = -1\nc1 = -1\n"
                "for r in range(h):\n    for c in range(w):\n        if g[r][c] != %d:\n"
                "            r0 = min([r0, r])\n            c0 = min([c0, c])\n"
                "            r1 = max([r1, r])\n            c1 = max([c1, c])\n"
                "if r1 >= 0:\n    g = crop(g, r0, c0, r1 + 1, c1 + 1)" % step["background"])
        elif op in ("scale", "tile"):
            rh, cw = ((step["factor"], step["factor"]) if op == "scale" else
                      (step["rows"], step["columns"]))
            rr, cc = (("r // %d" % rh, "c // %d" % cw) if op == "scale" else
                      ("r % h", "c % w"))
            add("h = len(g)\nw = len(g[0])\nout = new_grid(h * %d, w * %d, 0)\n"
                "for r in range(h * %d):\n    for c in range(w * %d):\n"
                "        out[r][c] = g[%s][%s]\ng = out" % (rh, cw, rh, cw, rr, cc))
        elif op == "largest_component_crop":
            add("objects = components(g, %d, %d)\nif objects:\n"
                "    best = objects[0]\n    for obj in objects:\n"
                "        if len(obj) > len(best):\n            best = obj\n"
                "    r0 = min([pixel[0] for pixel in best])\n"
                "    c0 = min([pixel[1] for pixel in best])\n"
                "    r1 = max([pixel[0] for pixel in best])\n"
                "    c1 = max([pixel[1] for pixel in best])\n"
                "    g = crop(g, r0, c0, r1 + 1, c1 + 1)" %
                (step["background"], step["connectivity"]))
    lines.append("    return g")
    source = "\n".join(lines) + "\n"
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise PlanError("compiled source byte limit")
    if sum(1 for _ in ast.walk(ast.parse(source))) > MAX_AST_NODES:
        raise PlanError("compiled AST node limit")
    return source


def production_ids(plan):
    plan = validate_plan(plan)
    result = ["length:" + str(len(plan["steps"]))]
    for step in plan["steps"]:
        result.append("op:" + step["op"])
        result.extend("param:%s:%s:%d" % (step["op"], key, step[key])
                      for key in PARAMETERS[step["op"]])
    return result


def _atoms():
    import itertools
    groups = []
    for op, parameters in PARAMETERS.items():
        group = []
        for values in itertools.product(*parameters.values()):
            step = {"op": op, **dict(zip(parameters, values))}
            try:
                validate_plan({"steps": [step]})
            except PlanError:
                continue
            group.append(step)
        groups.append(group)
    # Round-robin parameterizations: the fixed breadth-first order exposes all
    # operation kinds early, rather than spending its first 90 slots on recolor.
    return [group[index] for index in range(max(map(len, groups)))
            for group in groups if index < len(group)]


def grammar_candidates():
    """Finite stable inventory; no data, model, task or query-label inputs.

    Includes every single operation. Compositions are every ordered pair of
    parameter-free geometry/rotation atoms; geometry and every recoloring in
    either order; and background-0 crops followed by geometry or scaling.
    Equivalent behaviors are retained as distinct syntactic candidates.
    """
    atoms = _atoms()
    geometry = [s for s in atoms if s["op"] in
                ("flip_horizontal", "flip_vertical", "rotate", "transpose")]
    recolors = [s for s in atoms if s["op"] == "recolor"]
    crops = [s for s in atoms if s["op"] == "crop_nonbackground" and s["background"] == 0]
    crops += [s for s in atoms if s["op"] == "largest_component_crop" and s["background"] == 0]
    scales = [s for s in atoms if s["op"] == "scale"]
    sequences = [[s] for s in atoms]
    sequences += [[a, b] for a in geometry for b in geometry]
    sequences += [[a, b] for a in geometry for b in recolors]
    sequences += [[b, a] for a in geometry for b in recolors]
    sequences += [[a, b] for a in crops for b in geometry + scales]
    result, seen = [], set()
    for steps in sequences:
        plan = validate_plan({"steps": steps})
        sha = digest(plan)
        if sha in seen:
            continue
        seen.add(sha)
        result.append({"id": "ir-" + sha, "ordinal": len(result), "plan": plan,
                       "production_ids": production_ids(plan), "program": compile_plan(plan)})
    return result


def grammar_manifest():
    candidates = grammar_candidates()
    return {"format": GRAMMAR_VERSION, "interface_max_steps": MAX_STEPS,
            "search_max_steps": 2, "candidate_count": len(candidates),
            "single_step_count": sum(len(c["plan"]["steps"]) == 1 for c in candidates),
            "two_step_count": sum(len(c["plan"]["steps"]) == 2 for c in candidates),
            "candidate_inventory_sha256": digest(candidates),
            "production_vocabulary": sorted({p for c in candidates for p in c["production_ids"]}),
            "coverage_scope": "Authored witnesses only; no claim of complete ARC coverage",
            "runtime_domain": "1..30 rectangular color grids; intermediate scale/tile axes <=30; shared interpreter gas applies"}


def order_candidates(proposals=(), *, mode="uniform", alpha=1.0):
    """Return an ordered inventory with normalized prior_weight (no execution).

    Smoothed feature-prior ranking starts with uniform candidate mass and
    multiplies production likelihood ratios against the zero-observation
    prior, then normalizes over this exact inventory. This is not a full PCFG.
    With no observed productions it returns the exact uniform order/weights.
    Hard pruning uses zero pseudocount and requires every
    production to have appeared; it may return no candidates. Uniform assigns
    equal candidate mass. Fixed inventory ordinal breaks all score ties.
    """
    if mode not in ("uniform", "smoothed", "hard_pruned"):
        raise ValueError("unknown prior mode")
    if type(alpha) not in (int, float) or not math.isfinite(alpha) or not 1e-6 <= alpha <= 1000:
        raise ValueError("alpha must be finite and between 1e-6 and 1000")
    if type(proposals) not in (list, tuple) or len(proposals) > 4:
        raise ValueError("at most four shared proposal plans are allowed")
    candidates = grammar_candidates()
    vocabulary = {p for c in candidates for p in c["production_ids"]}
    counts = collections.Counter()
    for proposal in proposals:
        plan = parse_plan(proposal) if type(proposal) is str else validate_plan(proposal)
        counts.update(p for p in production_ids(plan) if p in vocabulary)
    if mode == "uniform" or (mode == "smoothed" and not counts):
        return [{**c, "prior_weight": 1.0 / len(candidates)} for c in candidates]
    smoothing = float(alpha) if mode == "smoothed" else 0.0
    denominator = sum(counts.values()) + smoothing * len(vocabulary)
    scored = []
    for candidate in candidates:
        masses = [counts[p] + smoothing for p in candidate["production_ids"]]
        if not denominator or any(v == 0 for v in masses):
            continue
        # p0(production)=1/|vocabulary|. Ratio correction removes the
        # unobserved length/parameter-count bias of multiplying raw priors.
        if mode == "smoothed":
            score = sum(math.log(v * len(vocabulary) / denominator) for v in masses)
        else:
            score = sum(math.log(v / denominator) for v in masses)
        scored.append((score, candidate))
    if not scored:
        return []
    maximum = max(s for s, _ in scored)
    normalizer = sum(math.exp(s - maximum) for s, _ in scored)
    scored.sort(key=lambda x: (-x[0], x[1]["ordinal"]))
    return [{**c, "prior_weight": math.exp(s - maximum) / normalizer} for s, c in scored]


def plan_contract():
    return ("Return only a JSON object with exactly steps, a list of one to three operations. "
            "Each operation has exactly op and the listed integer parameters. No booleans, "
            "floats, extra keys, duplicate keys, Markdown or prose. "
            "Allowed operations/parameters: " + canonical_json(PARAMETERS) +
            ". recolor source and target must differ; tile rows and columns cannot both be 1. "
            "rotate turns are clockwise quarter turns. Horizontal flips reverse columns; "
            "vertical flips reverse rows. Empty foreground crops return a copy. Largest "
            "same-color component ties select first row-major component. scale/tile outputs "
            "must have axes <=30. Example: {\"steps\":[{\"op\":\"rotate\",\"turns\":1},"
            "{\"op\":\"recolor\",\"source\":1,\"target\":2}]}")
