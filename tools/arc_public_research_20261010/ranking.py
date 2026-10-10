"""Frozen demos-only, support-preserving ordering for the fixed 5,965-plan pool.

This module has no file, process, compiler, verifier, model or query capability.
It computes shape/color-set abstractions, never pixels or object partitions.
The coordinator must bind these source bytes and seal all orderings before any
physical checks or evaluator outcome reads. This is CPU research, not a claim
about competition GPU inference. Cache and DEV8 experiment phases are absent.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

POLICY_VERSION = "irisx/public-demos-shape-palette-v1"
ABSTRACTION_VERSION = "dimensions-palette-upper-v1"
PRNG_VERSION = "sha256-counter-u256-rejection-v1"
INVENTORY_COUNT = 5965
INVENTORY_SHA256 = "f205b801bbb177cacd560582ddf994ad27c0f934cacd999b7983709d1c0a071e"
SORTED_INVENTORY_SHA256 = "4fae5a401a979f4c1b0d853223b5a587ba75d4e846ff39386ba151121abe0c81"
FAMILIES = ("legacy_geometry", "legacy_recolor", "legacy_other", "object_unary",
            "crop_d4", "anchored", "panel_boolean", "panel_copy")
GEOMETRY = frozenset(("identity", "rotate", "transpose", "flip_horizontal", "flip_vertical"))
ALL_DIMENSIONS = frozenset((h, w) for h in range(1, 31) for w in range(1, 31))
ALL_COLORS = frozenset(range(10))


class RankingError(ValueError):
    """The ranker was given data outside its sealed input contract."""


def canonical(value):
    """The ASCII-safe canonical plans and UTF-8 demos have one encoding."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise RankingError("bounded JSON data required") from exc


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def policy_config():
    """Return a fresh configuration; callers cannot mutate policy constants."""
    return {
        "version": POLICY_VERSION, "abstraction": ABSTRACTION_VERSION,
        "prng": PRNG_VERSION, "grid_axis_range": [1, 30], "colors": list(range(10)),
        "weight": {"base": 1, "dimension_coefficient": 4, "palette_coefficient": 2,
                   "exact_credit": 2, "compatibility_credit": 1},
        "mixture": {"uniform_numerator": 1, "denominator": 4,
                    "weighted_family_numerator": 3},
        "families": list(FAMILIES), "candidate_iteration": "ascending candidate_id",
        "family_iteration": "declared eight-family order, omit empty",
        "demo_order": "ordered, retained in demos digest; no sorting or task ID",
        "random_root": "SHA256(domain NUL canonical({demos_sha256,seed,method}))",
        "random_block": "SHA256(domain NUL root32 counter16big), counter starts at 0",
        "integer_choice": "u256 < 2**256 - (2**256 % bound), then u256 % bound",
        "draw_consumption": "uniform: index; weighted: branch, [family], index",
        "palette_credit": "exact equal=2; nonexact upper containment=1; exact mismatch=0",
        "unknown": "all legal dimensions/colors, compatibility-only, never prune",
        "intermediate_invalid": "drop invalid abstract paths; bottom is absorbing",
        "inventory_count": INVENTORY_COUNT, "inventory_sha256": INVENTORY_SHA256,
        "sorted_inventory_sha256": SORTED_INVENTORY_SHA256,
    }


def _grid_features(grid):
    if (type(grid) is not list or not 1 <= len(grid) <= 30
            or any(type(row) is not list for row in grid)
            or not 1 <= len(grid[0]) <= 30
            or any(len(row) != len(grid[0]) for row in grid)
            or any(type(c) is not int or not 0 <= c <= 9 for row in grid for c in row)):
        raise RankingError("grid must be rectangular 1..30 with integer colors 0..9")
    return {"dimensions": [len(grid), len(grid[0])],
            "palette": sorted({c for row in grid for c in row})}


def demo_features(task):
    """Reject rich task/demo schemas BEFORE extracting only shape and palette."""
    if type(task) is not dict or set(task) != {"task_id", "demos"}:
        raise RankingError("task must contain exactly task_id and demos")
    tid, demos = task["task_id"], task["demos"]
    try:
        valid_id = type(tid) is str and bool(tid) and len(tid.encode("utf-8")) <= 128
    except UnicodeError:
        valid_id = False
    if not valid_id:
        raise RankingError("task_id must be a nonempty bounded receipt identifier")
    if type(demos) is not list or not 1 <= len(demos) <= 10:
        raise RankingError("task requires one to ten ordered demonstrations")
    features = []
    for pair in demos:
        if type(pair) is not dict or set(pair) != {"input", "output"}:
            raise RankingError("demo must contain exactly input and output")
        features.append({key: _grid_features(pair[key]) for key in ("input", "output")})
    return features


@dataclass(frozen=True)
class AbstractEffect:
    dimensions: frozenset
    palette_upper: frozenset
    palette_exact: bool
    unknown: bool = False

    def as_dict(self):
        return {"dimensions": [list(d) for d in sorted(self.dimensions)],
                "palette_upper": sorted(self.palette_upper),
                "palette_exact": self.palette_exact, "unknown": self.unknown,
                "impossible": not bool(self.dimensions)}


def _effect(dimensions, palette, exact=False, unknown=False):
    dims = frozenset((h, w) for h, w in dimensions if 1 <= h <= 30 and 1 <= w <= 30)
    colors = frozenset(palette) if dims else frozenset()
    # A nonempty legal grid with a singleton upper bound has that exact palette.
    return AbstractEffect(dims, colors, bool(dims and not unknown and
                                             (exact or len(colors) == 1)), unknown)


def _top(state):
    return _effect(ALL_DIMENSIONS, ALL_COLORS, unknown=True) if state.dimensions else state


def _crop_dimensions(dimensions):
    # Only shape arithmetic. Includes every nonempty crop and empty-copy path.
    return frozenset((r, c) for h, w in dimensions
                     for r in range(1, h + 1) for c in range(1, w + 1))


def _backgrounds(step, state):
    bg = step.get("background")
    if type(bg) is int and 0 <= bg <= 9:
        return frozenset((bg,))
    if bg == "most_frequent":
        # Counts, partitions and tie selection are intentionally not evaluated.
        return state.palette_upper
    return None


def _valid_keys(step, keys):
    return set(step) == {"op", *keys}


def _integer_in(value, choices):
    return type(value) is int and value in choices


def abstract_step(state, step):
    """Conservative operation-schema transfer, with absorbing impossible paths."""
    if not state.dimensions:
        return state
    if type(step) is not dict or type(step.get("op")) is not str:
        return _top(state)
    op = step["op"]
    dims, colors, exact = state.dimensions, state.palette_upper, state.palette_exact
    if op in GEOMETRY:
        keys = ("turns",) if op == "rotate" else ()
        if not _valid_keys(step, keys) or (op == "rotate" and
                not _integer_in(step["turns"], (1, 2, 3))):
            return _top(state)
        if op == "transpose" or (op == "rotate" and step["turns"] % 2):
            dims = frozenset((w, h) for h, w in dims)
    elif op in ("scale", "tile"):
        keys = ("factor",) if op == "scale" else ("rows", "columns")
        if not _valid_keys(step, keys):
            return _top(state)
        if op == "scale":
            if not _integer_in(step["factor"], (2, 3)):
                return _top(state)
            rh = cw = step["factor"]
        else:
            if any(not _integer_in(step[k], (1, 2, 3)) for k in keys):
                return _top(state)
            rh, cw = step["rows"], step["columns"]
        dims = frozenset((h * rh, w * cw) for h, w in dims
                         if h * rh <= 30 and w * cw <= 30)
    elif op == "recolor":
        if (not _valid_keys(step, ("source", "target")) or
                any(not _integer_in(step[k], range(10)) for k in ("source", "target"))):
            return _top(state)
        colors = frozenset(step["target"] if c == step["source"] else c for c in colors)
    elif op in ("crop_nonbackground", "largest_component_crop"):
        keys = ("background", "connectivity") if op == "largest_component_crop" else ("background",)
        if (not _valid_keys(step, keys) or
                not _integer_in(step["background"], range(10)) or
                (op == "largest_component_crop" and
                 not _integer_in(step["connectivity"], (4, 8)))):
            return _top(state)
        dims, exact = _crop_dimensions(dims), False
    elif op == "object_select_render":
        if not _object_schema(step, anchored=False):
            return _top(state)
        background, action = _backgrounds(step, state), step["action"]["kind"]
        if action in ("crop_bbox", "crop_mask"):
            dims = _crop_dimensions(dims)
        if action in ("keep_mask", "erase_mask", "crop_mask"):
            colors = colors | background
        elif action == "paint_mask":
            colors = colors | {step["action"]["color"]}
        exact = False
    elif op == "anchored_recolor":
        if not _object_schema(step, anchored=True):
            return _top(state)
        # Empty/tied anchors can copy; recoloring can only use existing colors.
        exact = False
    elif op in ("equal_panels_boolean", "equal_panels_copy"):
        if not _panel_schema(step):
            return _top(state)
        valid, invalid = set(), set()
        for h, w in dims:
            length = h if step["axis"] == "rows" else w
            size = (length - step["gap"]) // 2
            if size < 1 or size * 2 + step["gap"] != length:
                invalid.add((h, w))
            else:
                valid.add((size, w) if step["axis"] == "rows" else (h, size))
        if op == "equal_panels_copy":
            # Overwriting a panel may remove a color present only in that panel.
            exact = exact if not valid else False
        else:
            branches = []
            if invalid:
                branches.append((colors, exact))
            if valid:
                bg, fg, table = _backgrounds(step, state), step["foreground"], step["truth_table"]
                palette = frozenset((fg,)) if table == 15 else bg if table == 0 else bg | {fg}
                branches.append((palette, len(palette) == 1))
            dims = frozenset(valid | invalid)
            colors = frozenset().union(*(p for p, _ in branches))
            exact = all(e and p == colors for p, e in branches)
    else:
        return _top(state)
    return _effect(dims, colors, exact, state.unknown)


def _selector_schema(value, anchor=False):
    if type(value) is not dict:
        return False
    kind = value.get("kind")
    if kind == "containscolor" and not anchor:
        return set(value) == {"kind", "color"} and _integer_in(value["color"], range(10))
    return set(value) == {"kind"} and kind in (("minarea", "maxarea") if anchor
                                              else ("all", "minarea", "maxarea"))


def _object_schema(step, anchored):
    keys = {"partition", "background"} | ({"focus_selector", "anchor_selector", "relation"}
                                          if anchored else {"selector", "action"})
    if (not _valid_keys(step, keys) or step["partition"] not in
            ("same_color_cc4", "same_color_cc8", "foreground_cc4", "foreground_cc8", "per_color")
            or not (_integer_in(step["background"], range(10)) or step["background"] == "most_frequent")):
        return False
    if anchored:
        return (_selector_schema(step["focus_selector"]) and
                _selector_schema(step["anchor_selector"], True) and
                step["relation"] in ("above", "below", "left", "right", "inside_bbox"))
    action = step["action"]
    if not _selector_schema(step["selector"]) or type(action) is not dict:
        return False
    if action.get("kind") == "paint_mask":
        return set(action) == {"kind", "color"} and _integer_in(action["color"], range(10))
    return set(action) == {"kind"} and action["kind"] in ("keep_mask", "erase_mask", "crop_bbox", "crop_mask")


def _panel_schema(step):
    boolean = step["op"] == "equal_panels_boolean"
    keys = {"axis", "gap"} | ({"truth_table", "foreground", "background"} if boolean else {"direction"})
    if (not _valid_keys(step, keys) or step["axis"] not in ("rows", "cols")
            or not _integer_in(step["gap"], (0, 1))):
        return False
    if not boolean:
        return step["direction"] in ("first_to_second", "second_to_first")
    return (_integer_in(step["truth_table"], range(16)) and
            _integer_in(step["foreground"], range(10)) and
            (_integer_in(step["background"], range(10)) or step["background"] == "most_frequent"))


def abstract_plan(plan, input_features):
    """Pure public helper for synthetic abstraction tests, never a grid solver."""
    state = _effect((tuple(input_features["dimensions"]),), input_features["palette"], True)
    if (type(plan) is not dict or set(plan) != {"steps"} or
            type(plan["steps"]) is not list or not 1 <= len(plan["steps"]) <= 3):
        return _top(state)
    for step in plan["steps"]:
        state = abstract_step(state, step)
    return state


def compatibility(effect, output_features):
    dimension = tuple(output_features["dimensions"])
    palette = frozenset(output_features["palette"])
    d = (2 if len(effect.dimensions) == 1 and not effect.unknown else 1) if dimension in effect.dimensions else 0
    p = 0
    if effect.dimensions:
        if effect.palette_exact and not effect.unknown:
            p = 2 if palette == effect.palette_upper else 0
        elif palette <= effect.palette_upper:
            p = 1
    return {"dimension_credit": d, "palette_credit": p}


def candidate_family(plan):
    """Exactly the existing smoke_inventory partition, including multi-step order."""
    steps, op = plan["steps"], plan["steps"][0]["op"]
    if op == "object_select_render":
        return FAMILIES[3 if len(steps) == 1 else 4]
    if op in ("anchored_recolor", "equal_panels_boolean", "equal_panels_copy"):
        return FAMILIES[("anchored_recolor", "equal_panels_boolean", "equal_panels_copy").index(op) + 5]
    return FAMILIES[0 if all(s["op"] in GEOMETRY for s in steps)
                    else 1 if any(s["op"] == "recolor" for s in steps) else 2]


def candidate_features(plan, features):
    credits = [compatibility(abstract_plan(plan, pair["input"]), pair["output"]) for pair in features]
    return {"family": candidate_family(plan), "credits": credits,
            "weight": 1 + 4 * sum(c["dimension_credit"] for c in credits)
                        + 2 * sum(c["palette_credit"] for c in credits)}


class CounterStream:
    """Versioned, whole-SHA256-block counter stream; unbiased integer draws."""
    DOMAIN = b"irisx/public-ranker/sha256-counter-u256-rejection-v1"

    def __init__(self, demos_sha256, seed, method):
        self.root = hashlib.sha256(self.DOMAIN + b"\0" + canonical(
            {"demos_sha256": demos_sha256, "seed": seed, "method": method})).digest()
        self.counter = 0

    def block(self):
        if self.counter >= 1 << 128:
            raise RankingError("counter stream exhausted")
        value = hashlib.sha256(self.DOMAIN + b"\0" + self.root + self.counter.to_bytes(16, "big")).digest()
        self.counter += 1
        return value

    def randbelow(self, bound):
        if type(bound) is not int or not 1 <= bound <= 1 << 256:
            raise RankingError("integer bound outside u256 range")
        limit = (1 << 256) - ((1 << 256) % bound)
        while True:
            value = int.from_bytes(self.block(), "big")
            if value < limit:
                return value % bound


class _MassTree:
    """Integer Fenwick tree: deterministic O(log n) draw and removal."""
    def __init__(self, values):
        self.tree = [0] + list(values)
        self.total = sum(values)
        for i in range(1, len(self.tree)):
            j = i + (i & -i)
            if j < len(self.tree):
                self.tree[j] += self.tree[i]

    def remove(self, index, mass):
        self.total -= mass
        i = index + 1
        while i < len(self.tree):
            self.tree[i] -= mass
            i += i & -i

    def find(self, ticket):
        if not 0 <= ticket < self.total:
            raise RankingError("ticket outside remaining mass")
        index = 0
        step = 1 << ((len(self.tree) - 1).bit_length() - 1)
        while step:
            nxt = index + step
            if nxt < len(self.tree) and self.tree[nxt] <= ticket:
                index = nxt
                ticket -= self.tree[nxt]
            step >>= 1
        return index


def draw_order(rows, stream, method):
    """Draw all rows without replacement. Internal small-pool test surface.

    rows: unique candidate_id/family/positive integer weight records. Candidate
    IDs establish iteration only, never a semantic feature or weight.
    """
    if method not in ("uniform", "shape_palette_v1"):
        raise RankingError("unknown ranking method")
    ordered = sorted(rows, key=lambda row: row["candidate_id"])
    if (not ordered or len({r["candidate_id"] for r in ordered}) != len(ordered)
            or any(r["family"] not in FAMILIES or type(r["weight"]) is not int or r["weight"] < 1 for r in ordered)):
        raise RankingError("nonempty unique candidates with positive weights required")
    uniform = _MassTree([1] * len(ordered))
    members = [[i for i, row in enumerate(ordered) if row["family"] == family] for family in FAMILIES]
    trees = [_MassTree([ordered[i]["weight"] for i in group]) for group in members]
    positions = {idx: (family, pos) for family, group in enumerate(members) for pos, idx in enumerate(group)}
    result = []
    while uniform.total:
        if method == "uniform" or stream.randbelow(4) == 0:
            idx = uniform.find(stream.randbelow(uniform.total))
        else:
            active = [i for i, tree in enumerate(trees) if tree.total]
            family = active[stream.randbelow(len(active))]
            idx = members[family][trees[family].find(stream.randbelow(trees[family].total))]
        family, pos = positions[idx]
        uniform.remove(idx, 1)
        trees[family].remove(pos, ordered[idx]["weight"])
        result.append(ordered[idx]["candidate_id"])
    return result


def _bound_candidates(candidates):
    if type(candidates) is not list or len(candidates) != INVENTORY_COUNT:
        raise RankingError("exact 5965-candidate frozen base inventory required")
    expected_keys = {"candidate_id", "plan", "origin", "source_sha256"}
    for row in candidates:
        if (type(row) is not dict or set(row) != expected_keys or row["origin"] != "base"
                or row["candidate_id"] != digest(row["plan"])):
            raise RankingError("candidate must be canonical base plan plus source hash only")
        source = row["source_sha256"]
        if type(source) is not str or len(source) != 64 or any(c not in "0123456789abcdef" for c in source):
            raise RankingError("candidate compiled-source SHA256 required")
    rows = sorted(candidates, key=lambda row: row["candidate_id"])
    if len({row["candidate_id"] for row in rows}) != INVENTORY_COUNT:
        raise RankingError("duplicate candidate ID")
    if digest([row["plan"] for row in rows]) != SORTED_INVENTORY_SHA256:
        raise RankingError("candidate plans differ from the fixed base inventory")
    return rows


def rank_candidates(task, candidates, seed=0, method="uniform", budget=64):
    """Seal the full support and top window using demonstrations only.

    The source fingerprint binds the *provided* compiled-source hashes. The
    coordinator authenticates them against compiler bytes and also records
    this module's actual source-file hash; this pure function opens no files.
    Inventory input order does not matter. Ordered demo order does matter to
    randomization and its digest, but does not change summed semantic weights.
    """
    features = demo_features(task)
    if type(seed) is not int or not 0 <= seed < 1 << 64:
        raise RankingError("seed must be a uint64 integer")
    if method not in ("uniform", "shape_palette_v1"):
        raise RankingError("unknown ranking method")
    if type(budget) is not int or not 1 <= budget <= INVENTORY_COUNT:
        raise RankingError("budget must be a positive integer within the inventory")
    candidates = _bound_candidates(candidates)
    demos_sha = digest(task["demos"])
    rows = [{"candidate_id": row["candidate_id"], **candidate_features(row["plan"], features)}
            for row in candidates]
    stream = CounterStream(demos_sha, seed, method)
    ordering = draw_order(rows, stream, method)
    config = policy_config()
    source_binding = [{"candidate_id": row["candidate_id"], "source_sha256": row["source_sha256"]}
                      for row in candidates]
    record = {
        "format": POLICY_VERSION, "task_id": task["task_id"], "method": method,
        "seed": seed, "budget": budget, "demos_sha256": demos_sha,
        "demo_features": features, "features_sha256": digest(features),
        "config": config, "config_sha256": digest(config),
        "inventory_count": len(candidates), "inventory_sha256": INVENTORY_SHA256,
        "sorted_inventory_sha256": SORTED_INVENTORY_SHA256,
        "source_sha256": digest(source_binding),
        "source_binding_kind": "candidate_id/compiled_source_sha256 sorted by candidate_id",
        "candidate_features": rows, "candidate_features_sha256": digest(rows),
        "family_mass": [{"family": family,
                         "count": sum(row["family"] == family for row in rows),
                         "weight": sum(row["weight"] for row in rows if row["family"] == family)}
                        for family in FAMILIES],
        "full_order": ordering, "selected_candidate_ids": ordering[:budget],
        "excluded_candidate_ids": [], "random_blocks_consumed": stream.counter,
        "physical_checks": 0,
    }
    # Task ID is outside the semantic seal too: a rename cannot alter it.
    record["ordering_sha256"] = digest({k: v for k, v in record.items() if k != "task_id"})
    return record
