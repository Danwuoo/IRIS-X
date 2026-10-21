"""Fixed 136 geometries plus one constant family; no evaluator or model imports."""

from collections import Counter
from dataclasses import dataclass, field
import time

from tools.public_sft141_diagnostic.contract import transform
from tools.public_sft141_submission.contract import canonical, digest, validate_grid

from . import METHOD_VERSION

BASES = (("identity", None), *(("crop", b) for b in range(10)),
         ("downsample", 2), ("downsample", 3), ("upscale", 2),
         ("upscale", 3), ("tile", 2), ("tile", 3))
TEMPLATES = tuple({"family": "geometry", "base": base, "parameter": parameter,
                   "view": view} for base, parameter in BASES for view in range(8))
TEMPLATES += ({"family": "constant"},)
RANKING = ["loo_exact_desc", "loo_defined_desc", "complexity_asc", "canonical_spec_asc"]


class Deadline(Exception):
    """The original run budget has been consumed; never reset it per task."""


class Inapplicable(Exception):
    """A fixed template cannot apply, with a compact stable reason."""


@dataclass
class Work:
    deadline: float = float("inf")
    counters: Counter = field(default_factory=Counter)

    def check(self):
        if time.monotonic() >= self.deadline:
            raise Deadline("original whole-run deadline")

    def cells(self, name, count):
        self.check()
        self.counters[name] += count


def key(value):
    return canonical(value).decode("ascii").rstrip("\n")


def geometry(grid, template, work):
    """One base followed by the unchanged public codec's D4 transform."""
    work.cells("geometry_input_cells", len(grid) * len(grid[0]))
    base, parameter = template["base"], template["parameter"]
    h, w = len(grid), len(grid[0])
    if base == "identity":
        result = grid
    elif base == "crop":
        cells = [(r, c) for r in range(h) for c in range(w) if grid[r][c] != parameter]
        if not cells:
            raise Inapplicable("empty_crop")
        rs, cs = zip(*cells)
        result = [row[min(cs):max(cs) + 1] for row in grid[min(rs):max(rs) + 1]]
    elif base == "downsample":
        f = parameter
        if h % f or w % f:
            raise Inapplicable("indivisible_downsample")
        result = []
        for r in range(0, h, f):
            row = []
            for c in range(0, w, f):
                color = grid[r][c]
                if any(grid[y][x] != color for y in range(r, r + f) for x in range(c, c + f)):
                    raise Inapplicable("nonuniform_downsample")
                row.append(color)
            result.append(row)
    elif base in ("upscale", "tile"):
        f = parameter
        if h * f > 30 or w * f > 30:
            raise Inapplicable("illegal_output_shape")
        if base == "upscale":
            result = [[color for color in row for _ in range(f)] for row in grid for _ in range(f)]
        else:
            result = [row * f for _ in range(f) for row in grid]
    else:
        raise ValueError("unknown frozen geometry")
    work.cells("geometry_output_cells", len(result) * len(result[0]))
    return transform(result, template["view"])


def predict(program, grid, work):
    if program["family"] == "constant":
        result = validate_grid(program["grid"])
        work.cells("constant_output_cells", len(result) * len(result[0]))
        return result
    result = geometry(grid, program, work)
    work.cells("palette_prediction_cells", len(result) * len(result[0]))
    if program["palette_mode"] == "identity":
        # An explicit parameter-free primitive, not completion of a learned map.
        return result
    mapping = dict(program["observed_mapping"])
    if any(color not in mapping for row in result for color in row):
        raise Inapplicable("unseen_color")
    return [[mapping[color] for color in row] for row in result]


def fit(template, train, work):
    """Fit from precisely these demonstrations, with no external/query labels."""
    work.check()
    if not train:
        raise ValueError("fit requires visible supports")
    if template["family"] == "constant":
        result = train[0]["output"]
        for pair in train:
            work.cells("constant_fit_cells", len(pair["output"]) * len(pair["output"][0]))
            if pair["output"] != result:
                raise Inapplicable("nonconstant_supports")
        program = {"family": "constant", "grid": validate_grid(result)}
    else:
        mapping = {}
        for pair in train:
            generated = geometry(pair["input"], template, work)
            target = pair["output"]
            if len(generated) != len(target) or len(generated[0]) != len(target[0]):
                raise Inapplicable("support_shape_mismatch")
            for row, gold_row in zip(generated, target):
                work.cells("palette_fit_cells", len(row))
                for source, target_color in zip(row, gold_row):
                    if source in mapping and mapping[source] != target_color:
                        raise Inapplicable("inconsistent_palette")
                    mapping[source] = target_color
        program = dict(template, palette_mode=("identity" if all(a == b for a, b in mapping.items())
                                               else "learned"),
                       observed_mapping=[[a, b] for a, b in sorted(mapping.items())])
    # Explicit replay is deliberately not replaced with confidence in fitting.
    for pair in train:
        if predict(program, pair["input"], work) != pair["output"]:
            raise Inapplicable("support_replay_failed")
        work.counters["support_replays_exact"] += 1
    return program


def complexity(program):
    if program["family"] == "constant":
        return 1 + len(program["grid"]) * len(program["grid"][0])
    spatial = int(program["base"] != "identity") + int(program["view"] != 0)
    palette = (1 + sum(a != b for a, b in program["observed_mapping"])
               if program["palette_mode"] == "learned" else 0)
    return spatial + palette


def loo(template, train, work):
    if len(train) == 1:
        return {"available": False, "exact_count": 0, "defined_count": 0, "folds": []}
    folds = []
    for index, held in enumerate(train):
        work.check()
        work.counters["loo_refits_attempted"] += 1
        fold = {"held_index": index, "defined": False, "exact": False}
        try:
            program = fit(template, train[:index] + train[index + 1:], work)
            fold["refit_program_sha256"] = digest(canonical(program))
            predicted = predict(program, held["input"], work)
            fold.update(defined=True, exact=predicted == held["output"],
                        prediction_sha256=digest(canonical(predicted)))
            if not fold["exact"]:
                fold["failure"] = "held_output_mismatch"
        except Inapplicable as exc:
            fold["failure"] = str(exc)
        folds.append(fold)
    return {"available": True, "exact_count": sum(f["exact"] for f in folds),
            "defined_count": sum(f["defined"] for f in folds), "folds": folds}


def rank_key(record):
    return (-record["loo"]["exact_count"], -record["loo"]["defined_count"],
            record["complexity"], record["canonical_program"])


def solve_task(task_id, task, work=None):
    """Exhaust the frozen family before issuing predictions. Partial means missing."""
    work = work or Work()
    started = time.monotonic()
    before = work.counters.copy()
    programs, attempts, seen = [], [], set()
    queries = [{"test_index": i, "candidates": [], "status": "not_completed"}
               for i in range(len(task["test"]))]
    complete = False
    stage = "fit_and_verify"
    try:
        for index, template in enumerate(TEMPLATES):
            work.check()
            attempt = {"template_index": index, "template": template, "status": "interrupted"}
            attempts.append(attempt)
            work.counters["templates_attempted"] += 1
            try:
                program = fit(template, task["train"], work)
            except Inapplicable as exc:
                attempt.update(status="rejected", failure=str(exc))
                work.counters["templates_rejected"] += 1
                continue
            canonical_program = key(program)
            if canonical_program in seen:
                attempt["status"] = "duplicate_program"
                work.counters["program_duplicates"] += 1
                continue
            # A record is usable only once every required LOO fold completes.
            reliability = loo(template, task["train"], work)
            record = {"program_id": digest(canonical(program)), "spec": program,
                      "canonical_program": canonical_program, "complexity": complexity(program),
                      "full_support_exact_count": len(task["train"]), "loo": reliability}
            seen.add(canonical_program)
            programs.append(record)
            attempt.update(status="verified", program_id=record["program_id"])
            work.counters["programs_verified"] += 1
        programs.sort(key=rank_key)
        stage = "query_prediction"
        for query, source in zip(queries, task["test"]):
            candidates, candidate_keys, failures = [], set(), Counter()
            considered = 0
            for record in programs:
                work.check()
                considered += 1
                work.counters["query_programs_attempted"] += 1
                try:
                    predicted = validate_grid(predict(record["spec"], source["input"], work))
                except Inapplicable as exc:
                    failures[str(exc)] += 1
                    work.counters["query_program_failures"] += 1
                    continue
                ckey = key(predicted)
                if ckey in candidate_keys:
                    failures["duplicate_grid"] += 1
                    work.counters["candidate_grid_duplicates"] += 1
                    continue
                candidate_keys.add(ckey)
                candidates.append({"grid": predicted, "program_id": record["program_id"],
                                   "task_rank": considered - 1})
                if len(candidates) == 2:
                    break
            query.update(candidates=candidates, status="predicted" if candidates else "missing",
                         programs_considered=considered, failures=dict(sorted(failures.items())))
        complete = True
    except Deadline:
        # A partial task does not expose a prefix-ranked answer as full search.
        for query in queries:
            query.update(candidates=[], status="not_completed")
    return {"schema": "iris-public-cpu-task-v1", "method": METHOD_VERSION,
            "task_id": task_id, "status": "complete" if complete else "partial",
            "stopped_stage": None if complete else stage, "train_count": len(task["train"]),
            "template_inventory_count": len(TEMPLATES), "attempts": attempts,
            "failure_counts": dict(sorted(Counter(a.get("failure") for a in attempts
                                                   if a["status"] == "rejected").items())),
            "programs": programs, "queries": queries, "ranking": RANKING,
            "counts": dict(sorted((work.counters - before).items())),
            "wall_seconds": time.monotonic() - started}
