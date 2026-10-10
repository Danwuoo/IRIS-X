"""Additive object plans compiled to the unchanged, pinned bounded VM.

Only fixed templates become source. Source is data for the isolated VM, never
host-executed here. The finite baseline is deliberately smaller than the legal
one-to-three-step proposal language; it is not an ARC completeness claim.
"""
from __future__ import annotations

import ast
import hashlib
import itertools
import json

from .assets import load_legacy

IR_VERSION = "irisx/object-typed-ir-v2"
MAX_PLAN_BYTES = 4096
MAX_SOURCE_BYTES = 32768
MAX_AST_NODES = 2048
MAX_STEPS = 3
PARTITIONS = ("same_color_cc4", "same_color_cc8", "foreground_cc4",
              "foreground_cc8", "per_color")
RELATIONS = ("above", "below", "left", "right", "inside_bbox")
SELECTORS = ("all", "minarea", "maxarea", "containscolor")
ACTIONS = ("keep_mask", "erase_mask", "crop_bbox", "crop_mask", "paint_mask")
BASE_BACKGROUNDS = (0, "most_frequent")
OBJECT_OPS = ("object_select_render", "anchored_recolor")
PANEL_OPS = ("equal_panels_boolean", "equal_panels_copy")
NEW_OPS = OBJECT_OPS + PANEL_OPS


class PlanError(ValueError):
    pass


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _bounded_shape(value, depth=0):
    if depth > 6:
        raise PlanError("plan nesting limit")
    if type(value) is dict:
        if len(value) > 8 or any(type(k) is not str or len(k) > 32 for k in value):
            raise PlanError("bounded string parameter keys required")
        for child in value.values():
            _bounded_shape(child, depth + 1)
    elif type(value) is list:
        if len(value) > MAX_STEPS:
            raise PlanError("plan list limit")
        for child in value:
            _bounded_shape(child, depth + 1)
    elif type(value) is str:
        if len(value) > 64:
            raise PlanError("plan string limit")
    elif type(value) is not int or not 0 <= value <= 15:
        raise PlanError("only bounded integers, strings, objects and steps allowed")


def _color(value):
    if type(value) is not int or not 0 <= value <= 9:
        raise PlanError("color must be an integer in 0..9")
    return value


def _selector(value, *, anchor=False):
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise PlanError("selector must have a string kind")
    kind = value["kind"]
    allowed = ("minarea", "maxarea") if anchor else SELECTORS
    keys = {"kind", "color"} if kind == "containscolor" else {"kind"}
    if kind not in allowed or set(value) != keys:
        raise PlanError("selector kind or keys invalid")
    return {"kind": kind, **({"color": _color(value["color"])} if "color" in keys else {})}


def _action(value):
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise PlanError("action must have a string kind")
    kind = value["kind"]
    keys = {"kind", "color"} if kind == "paint_mask" else {"kind"}
    if kind not in ACTIONS or set(value) != keys:
        raise PlanError("action kind or keys invalid")
    return {"kind": kind, **({"color": _color(value["color"])} if "color" in keys else {})}


def validate_plan(plan):
    """Strict schema; no task identifiers, query labels or free source fields."""
    _bounded_shape(plan)
    if type(plan) is not dict or set(plan) != {"steps"}:
        raise PlanError("plan must contain exactly steps")
    if type(plan["steps"]) is not list or not 1 <= len(plan["steps"]) <= MAX_STEPS:
        raise PlanError("steps must contain one to three operations")
    result = []
    for step in plan["steps"]:
        if type(step) is not dict or type(step.get("op")) is not str:
            raise PlanError("operation must have a string op")
        op = step["op"]
        if op not in NEW_OPS:
            try:
                result.extend(load_legacy("arc_typed_ir").validate_plan({"steps": [step]})["steps"])
            except ValueError as exc:
                raise PlanError(str(exc)) from exc
            continue
        if op in PANEL_OPS:
            keys = {"op", "axis", "gap"}
            keys |= {"truth_table", "foreground", "background"} if op == "equal_panels_boolean" else {"direction"}
            if (set(step) != keys or type(step["axis"]) is not str or step["axis"] not in ("rows", "cols")
                    or type(step["gap"]) is not int or step["gap"] not in (0, 1)):
                raise PlanError("panel keys, axis or gap invalid")
            row = {"op": op, "axis": step["axis"], "gap": step["gap"]}
            if op == "equal_panels_copy":
                if type(step["direction"]) is not str or step["direction"] not in ("first_to_second", "second_to_first"):
                    raise PlanError("panel copy direction invalid")
                row["direction"] = step["direction"]
            else:
                if type(step["truth_table"]) is not int or not 0 <= step["truth_table"] <= 15:
                    raise PlanError("truth table must be integer0..15")
                bg = step["background"]
                if not (type(bg) is str and bg == "most_frequent"):
                    bg = _color(bg)
                row.update(truth_table=step["truth_table"], foreground=_color(step["foreground"]), background=bg)
            result.append(row)
            continue
        keys = {"op", "partition", "background"}
        keys |= ({"selector", "action"} if op == "object_select_render" else
                 {"focus_selector", "anchor_selector", "relation"})
        if set(step) != keys or type(step["partition"]) is not str or step["partition"] not in PARTITIONS:
            raise PlanError("object operation parameter keys or partition invalid")
        background = step["background"]
        if not (type(background) is str and background == "most_frequent"):
            background = _color(background)
        row = {"op": op, "partition": step["partition"], "background": background}
        if op == "object_select_render":
            row.update(selector=_selector(step["selector"]), action=_action(step["action"]))
        else:
            if type(step["relation"]) is not str or step["relation"] not in RELATIONS:
                raise PlanError("unknown anchor relation")
            row.update(focus_selector=_selector(step["focus_selector"]),
                       anchor_selector=_selector(step["anchor_selector"], anchor=True),
                       relation=step["relation"])
        result.append(row)
    clean = {"steps": result}
    try:
        if len(canonical_json(clean).encode("utf-8", "strict")) > MAX_PLAN_BYTES:
            raise PlanError("plan byte limit")
    except UnicodeError as exc:
        raise PlanError("invalid Unicode plan") from exc
    return clean


def parse_plan(text):
    if type(text) is not str:
        raise PlanError("raw JSON text required")
    try:
        if len(text.encode("utf-8", "strict")) > MAX_PLAN_BYTES:
            raise PlanError("plan byte limit")
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise PlanError("duplicate JSON key")
                result[key] = value
            return result
        def no_float(value):
            raise PlanError("floating point and nonfinite values forbidden")
        return validate_plan(json.loads(text, object_pairs_hook=pairs,
                                        parse_float=no_float, parse_constant=no_float))
    except (UnicodeError, RecursionError, ValueError, TypeError) as exc:
        if isinstance(exc, PlanError):
            raise
        raise PlanError("invalid bounded JSON plan") from exc


BACKGROUND_SOURCE = '''def obackground(g):
    counts = [0 for c in range(10)]
    for row in g:
        for c in row:
            counts[c] = counts[c] + 1
    best = 0
    for c in range(1, 10):
        if counts[c] > counts[best]:
            best = c
    return best
'''

PARTITION_SOURCE = '''def opartition(g, b, p):
    if p < 2:
        return components(g, b, 4 if p == 0 else 8)
    if p < 4:
        mask = [[0 if c == b else 1 for c in row] for row in g]
        objects = components(mask, 0, 4 if p == 2 else 8)
        return [[[v[0], v[1], g[v[0]][v[1]]] for v in obj] for obj in objects]
    objects = []
    for color in range(10):
        if color != b:
            obj = [[r, c, color] for r in range(len(g)) for c in range(len(g[0])) if g[r][c] == color]
            if obj:
                objects.append(obj)
    return objects
'''

SELECT_SOURCE = '''def oselect(objects, mode, color):
    if not objects or mode == 0:
        return objects
    if mode == 3:
        return [obj for obj in objects if color in [v[2] for v in obj]]
    size = min([len(obj) for obj in objects]) if mode == 1 else max([len(obj) for obj in objects])
    return [obj for obj in objects if len(obj) == size]
'''

RENDER_SOURCE = '''def orender(g, objects, b, action, color):
    h = len(g)
    w = len(g[0])
    out = new_grid(h, w, b) if action == 0 or action == 3 else copy_grid(g)
    r0 = h
    c0 = w
    r1 = -1
    c1 = -1
    for obj in objects:
        for v in obj:
            r = v[0]
            c = v[1]
            out[r][c] = b if action == 1 else color if action == 4 else g[r][c]
            r0 = min([r0, r])
            c0 = min([c0, c])
            r1 = max([r1, r])
            c1 = max([c1, c])
    if action == 2 or action == 3:
        if r1 < 0:
            return copy_grid(g)
        return crop(out, r0, c0, r1 + 1, c1 + 1)
    return out
'''

BBOX_SOURCE = '''def obox(obj):
    return [min([v[0] for v in obj]), min([v[1] for v in obj]), max([v[0] for v in obj]), max([v[1] for v in obj])]
'''

ANCHOR_SOURCE = '''def oanchor(g, objects, b, focus, color, anchor, relation):
    anchors = oselect(objects, anchor, 0)
    if len(anchors) != 1:
        return copy_grid(g)
    a = anchors[0]
    ab = obox(a)
    counts = [0 for c in range(10)]
    for v in a:
        counts[v[2]] = counts[v[2]] + 1
    paint = 0
    for c in range(1, 10):
        if counts[c] > counts[paint]:
            paint = c
    chosen = []
    for obj in oselect(objects, focus, color):
        if obj != a:
            box = obox(obj)
            keep = False
            if relation == 0:
                keep = box[2] < ab[0]
            if relation == 1:
                keep = box[0] > ab[2]
            if relation == 2:
                keep = box[3] < ab[1]
            if relation == 3:
                keep = box[1] > ab[3]
            if relation == 4:
                keep = box[0] >= ab[0] and box[1] >= ab[1] and box[2] <= ab[2] and box[3] <= ab[3]
            if keep:
                chosen.append(obj)
    return orender(g, chosen, b, 4, paint)
'''

PANEL_SOURCE = '''def opanels(g, axis, gap, mode, table, color, b):
    h = len(g)
    w = len(g[0])
    length = h if axis == 0 else w
    size = (length - gap) // 2
    if size < 1 or size * 2 + gap != length:
        return copy_grid(g)
    ph = size if axis == 0 else h
    pw = w if axis == 0 else size
    out = new_grid(ph, pw, b) if mode == 0 else copy_grid(g)
    for r in range(ph):
        for c in range(pw):
            rr = r + size + gap if axis == 0 else r
            cc = c + size + gap if axis == 1 else c
            if mode == 1:
                out[rr][cc] = g[r][c]
            elif mode == 2:
                out[r][c] = g[rr][cc]
            else:
                index = (2 if g[r][c] != b else 0) + (1 if g[rr][cc] != b else 0)
                divisor = 1 if index == 0 else 2 if index == 1 else 4 if index == 2 else 8
                out[r][c] = color if (table // divisor) % 2 == 1 else b
    return out
'''


def compile_plan(plan):
    """All extrema include every tie; ambiguous/empty anchors are explicit no-ops.

    Objects exclude the chosen background. Foreground components preserve
    their original colors; per-color groups may be disconnected. Crops use the
    union of selected pixels. An empty crop copies input; empty keep masks are
    all background. Anchor relations use strict disjoint bounding boxes for
    directions and inclusive full containment for inside. Focus is selected over the full original partition before
    removing the anchor; a matching unique focus/anchor extremum is a no-op.
    Anchor itself is never painted. No object is moved.
    """
    plan = validate_plan(plan)
    legacy = load_legacy("arc_typed_ir")
    new_steps = [s for s in plan["steps"] if s["op"] in NEW_OPS]
    if not new_steps:
        return legacy.compile_plan(plan)
    helpers = (PARTITION_SOURCE + SELECT_SOURCE + RENDER_SOURCE) if any(s["op"] in OBJECT_OPS for s in new_steps) else ""
    if any(s.get("background") == "most_frequent" for s in new_steps):
        helpers += BACKGROUND_SOURCE
    if any(s["op"] == "anchored_recolor" for s in new_steps):
        helpers += BBOX_SOURCE + ANCHOR_SOURCE
    if any(s["op"] in PANEL_OPS for s in new_steps):
        helpers += PANEL_SOURCE
    lines = ["def transform(grid):", "    g = copy_grid(grid)"]
    for step in plan["steps"]:
        op = step["op"]
        if op not in NEW_OPS:
            lines.extend(legacy.compile_plan({"steps": [step]}).splitlines()[2:-1])
            continue
        if op in PANEL_OPS:
            if op == "equal_panels_copy":
                mode = 1 if step["direction"] == "first_to_second" else 2
                bg, table, color = "0", 0, 0
            else:
                mode, table, color = 0, step["truth_table"], step["foreground"]
                bg = "obackground(g)" if step["background"] == "most_frequent" else str(step["background"])
            lines.append("    g = opanels(g, %d, %d, %d, %d, %d, %s)" %
                         (0 if step["axis"] == "rows" else 1, step["gap"], mode, table, color, bg))
            continue
        bg = "obackground(g)" if step["background"] == "most_frequent" else str(step["background"])
        lines.extend(["    b = " + bg, "    objects = opartition(g, b, %d)" % PARTITIONS.index(step["partition"])])
        if op == "object_select_render":
            selector, action = step["selector"], step["action"]
            lines.append("    chosen = oselect(objects, %d, %d)" % (SELECTORS.index(selector["kind"]), selector.get("color", 0)))
            lines.append("    g = orender(g, chosen, b, %d, %d)" % (ACTIONS.index(action["kind"]), action.get("color", 0)))
        else:
            selector = step["focus_selector"]
            lines.append("    g = oanchor(g, objects, b, %d, %d, %d, %d)" %
                         (SELECTORS.index(selector["kind"]), selector.get("color", 0),
                          SELECTORS.index(step["anchor_selector"]["kind"]), RELATIONS.index(step["relation"])))
    source = helpers + "\n" + "\n".join(lines) + "\n    return g\n"
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise PlanError("compiled source byte limit")
    if sum(1 for _ in ast.walk(ast.parse(source))) > MAX_AST_NODES:
        raise PlanError("compiled AST node limit")
    return source


def production_ids(plan):
    plan = validate_plan(plan)
    result = ["length:" + str(len(plan["steps"]))]
    for step in plan["steps"]:
        if step["op"] not in NEW_OPS:
            result.extend(load_legacy("arc_typed_ir").production_ids({"steps": [step]})[1:])
            continue
        result.append("op:" + step["op"])
        for key in sorted(set(step) - {"op"}):
            result.append("param:" + step["op"] + ":" + key + ":" + canonical_json(step[key]))
    return result


def object_atoms():
    """3120 one-step plans; explicit call only, independent of all tasks."""
    selectors = [{"kind": k} for k in SELECTORS[:3]]
    selectors += [{"kind": "containscolor", "color": c} for c in range(10)]
    actions = [{"kind": k} for k in ACTIONS[:4]]
    actions += [{"kind": "paint_mask", "color": c} for c in range(10)]
    result = []
    for p, b, selector, action in itertools.product(PARTITIONS, BASE_BACKGROUNDS, selectors, actions):
        result.append(validate_plan({"steps": [{"op": "object_select_render", "partition": p,
                       "background": b, "selector": selector, "action": action}]}))
    for p, b, selector, anchor, relation in itertools.product(PARTITIONS, BASE_BACKGROUNDS, selectors,
                                                            ("minarea", "maxarea"), RELATIONS):
        result.append(validate_plan({"steps": [{"op": "anchored_recolor", "partition": p,
                       "background": b, "focus_selector": selector,
                       "anchor_selector": {"kind": anchor}, "relation": relation}]}))
    return result


def _crop_d4():
    # Six nonidentity D4 elements have one legacy step. Anti-diagonal is
    # transpose followed by a half-turn; with the object crop this is 3 steps.
    geometries = [[{"op": "flip_horizontal"}], [{"op": "flip_vertical"}],
                  [{"op": "rotate", "turns": 1}], [{"op": "rotate", "turns": 2}],
                  [{"op": "rotate", "turns": 3}], [{"op": "transpose"}],
                  [{"op": "transpose"}, {"op": "rotate", "turns": 2}]]
    return [validate_plan({"steps": [{"op": "object_select_render", "partition": p,
             "background": b, "selector": {"kind": selector}, "action": {"kind": action}}, *geometry]})
            for p, b, action, selector, geometry in itertools.product(PARTITIONS, BASE_BACKGROUNDS,
             ("crop_bbox", "crop_mask"), ("minarea", "maxarea"), geometries)]


def _panel_atoms():
    boolean = [{"steps": [{"op": "equal_panels_boolean", "axis": axis, "gap": gap,
                "truth_table": table, "foreground": color, "background": background}]}
               for axis, gap, table, color, background in itertools.product(("rows", "cols"),
                (0, 1), range(16), range(10), BASE_BACKGROUNDS)]
    copies = [{"steps": [{"op": "equal_panels_copy", "axis": axis, "gap": gap, "direction": direction}]}
              for axis, gap, direction in itertools.product(("rows", "cols"), (0, 1),
                ("first_to_second", "second_to_first"))]
    return boolean + copies


def base_inventory():
    """Exactly 5965 fresh canonical plans, never generated at import time.

    1277 legacy; 1820 object unary; 280 crop/D4; 1300 anchored; 1280 panel
    Boolean; 8 panel copies. Object/copy/Boolean grid dimensions never grow.
    No arbitrary composition cross-product. All literal backgrounds and legal
    <=3-step proposals are accepted independently of inventory membership.
    """
    atoms = object_atoms()
    return ([validate_plan(c["plan"]) for c in load_legacy("arc_typed_ir").grammar_candidates()]
            + atoms[:1820] + _crop_d4() + atoms[1820:] + _panel_atoms())


def smoke_inventory():
    """Fixed 128 plans distributed across eight declared syntax families.

    Select evenly spaced ordinals inside each family, then round-robin. This
    covers the Boolean table range instead of selecting a trivial table prefix.
    Family quotas are frozen at18,17,17,17,17,17,17,8 (sum128).
    """
    groups = [[] for _ in range(8)]
    geometry = {"identity", "rotate", "transpose", "flip_horizontal", "flip_vertical"}
    for plan in base_inventory():
        steps = plan["steps"]
        op = steps[0]["op"]
        if op == "object_select_render":
            index = 3 if len(steps) == 1 else 4
        elif op == "anchored_recolor":
            index = 5
        elif op == "equal_panels_boolean":
            index = 6
        elif op == "equal_panels_copy":
            index = 7
        else:
            index = 0 if all(s["op"] in geometry for s in steps) else 1 if any(s["op"] == "recolor" for s in steps) else 2
        groups[index].append(plan)
    selected = [[group[i * (len(group) - 1) // (quota - 1)] for i in range(quota)]
                for group, quota in zip(groups, (18, 17, 17, 17, 17, 17, 17, 8))]
    result = []
    for offset in range(max(map(len, selected))):
        for group in selected:
            if offset < len(group):
                result.append(group[offset])
    return result


def inventory_manifest():
    plans = base_inventory()
    return {"format": IR_VERSION, "candidate_count": len(plans), "legacy_count": 1277,
            "object_select_render_count": 5 * 2 * 13 * 14,
            "crop_d4_count": 5 * 2 * 2 * 2 * 7,
            "anchored_recolor_count": 5 * 2 * 13 * 2 * 5,
            "equal_panels_boolean_count": 2 * 2 * 16 * 10 * 2,
            "equal_panels_copy_count": 2 * 2 * 2,
            "object_backgrounds": list(BASE_BACKGROUNDS), "proposal_max_steps": MAX_STEPS,
            "inventory_sha256": digest(plans),
            "partition_name_mapping": dict(zip(("mono4", "mono8", "foreground4", "foreground8", "color_groups"), PARTITIONS)),
            "crop_d4_scope": "minarea/maxarea, crop_bbox/crop_mask, all 5 partitions, 2 backgrounds, 7 nonidentity D4; anti-diagonal is transpose then rotate2",
            "predecessor": {"format": "irisx/object-typed-ir-v1", "candidate_count": 6225,
                "inventory_sha256": "a8f0479d5d613f9475d27987c1ea6232cf291211e52a6d6337284ab12a8da501",
                "removed_relation": "same_normalized_mask", "removed_candidates": 260,
                "reason": "a distinct equal occupancy mask has equal area and cannot match a unique min/max anchor"},
            "anchor_focus_order": "apply focus selector to full partition, then exclude anchor; matching min/min or max/max unique extrema are no-ops, not next-extremum selection",
            "smoke_families": ["legacy_geometry", "legacy_recolor", "legacy_other", "object_unary", "crop_d4", "anchored", "panel_boolean", "panel_copy"],
            "smoke_family_quotas": [18, 17, 17, 17, 17, 17, 17, 8],
            "smoke_rule": "evenly spaced family ordinals, then round-robin; 128 unique fixed plans",
            "primary_pool_ceiling": 5967,
            "scope": "5965 exact v2 candidates; removed relation is rejected by the proposal schema too; no padding or completeness claim"}


def plan_contract():
    return (load_legacy("arc_typed_ir").plan_contract() +
            " Also accepted: object_select_render with exactly partition, background, selector, action;"
            " anchored_recolor with exactly partition, background, focus_selector, anchor_selector, relation."
            " partition=" + canonical_json(PARTITIONS) + "; background=integer0..9 or most_frequent"
            " (most frequent ties choose lowest color). Selector={kind:all|minarea|maxarea} or"
            " {kind:containscolor,color:integer0..9}; min/max include ALL ties. Action={kind:keep_mask|"
            "erase_mask|crop_bbox|crop_mask} or {kind:paint_mask,color:integer0..9}. Anchor selector must"
            " be minarea or maxarea; empty or tied anchors copy input. Relation=" + canonical_json(RELATIONS) +
            ". Direction relations require disjoint bboxes; inside_bbox is full inclusive bbox containment."
            " Anchor itself is excluded."
            " Focus selector applies to full partition before anchor removal; matching min/min or"
            " max/max unique extrema therefore copy unchanged, never choose the next extremum."
            " Selected focus pixels become anchor dominant color (ties lowest). Empty crops copy input;"
            " empty keep produces background. All object steps preserve/crop dimensions. Shared pinned"
            " VM gas, 30x30 grids, 32768 source bytes and 2048 AST nodes remain enforced."
            " equal_panels_boolean takes exactly axis:rows|cols,gap:0|1,truth_table:integer0..15,"
            "foreground:integer0..9,background:integer0..9|most_frequent. Equal panels exclude central gap;"
            " output is one panel-sized grid, lookup bit index=2*first_occupied+second_occupied (occupied!=background),"
            " output foreground when table bit is1 else background. equal_panels_copy takes exactly"
            " axis,gap,direction:first_to_second|second_to_first; preserves full shape, separator and other panel."
            " Invalid/empty/unequal panel splits copy the input.")


def unit_witnesses():
    """Supplementary unit-only witnesses; release uses controls.py independent128."""
    def render(partition="same_color_cc4", background=0, selector=None, action=None):
        return {"steps": [{"op": "object_select_render", "partition": partition,
                           "background": background, "selector": selector or {"kind": "all"},
                           "action": action or {"kind": "keep_mask"}}]}
    def anchor(relation, partition="same_color_cc4", anchor_kind="maxarea"):
        return {"steps": [{"op": "anchored_recolor", "partition": partition, "background": 0,
                           "focus_selector": {"kind": "all"}, "anchor_selector": {"kind": anchor_kind},
                           "relation": relation}]}
    rows = [
        ("all_min_ties", [[1,0,2,0,3,3]], [[1,0,2,0,0,0]],
         render(selector={"kind":"minarea"}), "fit"),
        ("all_max_ties", [[1,1,0,2,2,0,3]], [[1,1,0,2,2,0,0]],
         render(selector={"kind":"maxarea"}), "fit"),
        ("foreground_colors", [[1,2,0,3]], [[1,2]],
         render("foreground_cc4", selector={"kind":"maxarea"}, action={"kind":"crop_mask"}), "fit"),
        ("diagonal_cc8", [[1,0],[0,1]], [[1,0],[0,1]], render("same_color_cc8"), "fit"),
        ("diagonal_foreground8", [[1,0],[0,2]], [[0,0],[0,0]],
         render("foreground_cc8", action={"kind":"erase_mask"}), "fit"),
        ("per_color_discrete", [[1,0,1,0,2]], [[1,0,1,0,0]],
         render("per_color", selector={"kind":"maxarea"}), "fit"),
        ("background_tie_low", [[1,2]], [[1,7]],
         render(background="most_frequent", action={"kind":"paint_mask","color":7}), "fit"),
        ("contains_color", [[1,2,0,3]], [[0,0,0,3]],
         render("foreground_cc4", selector={"kind":"containscolor","color":2}, action={"kind":"erase_mask"}), "fit"),
        ("crop_bbox_keeps_unselected", [[1,0,2,0,1]], [[1,0,2,0,1]],
         render("per_color", selector={"kind":"containscolor","color":1}, action={"kind":"crop_bbox"}), "fit"),
        ("empty_crop_noop", [[0,0]], [[0,0]], render(action={"kind":"crop_mask"}), "fit"),
        ("anchor_dominant_tie", [[1,2,0,0,0,3]], [[1,2,0,0,0,1]],
         anchor("right", "foreground_cc4"), "fit"),
        ("ambiguous_anchor_noop", [[1,0,2]], [[1,0,2]], anchor("right"), "fit"),
        ("empty_anchor_noop", [[0]], [[0]], anchor("above"), "fit"),
        ("anchor_below", [[1,1],[0,0],[2,0]], [[1,1],[0,0],[1,0]], anchor("below"), "fit"),
        ("anchor_above", [[2,0],[0,0],[1,1]], [[1,0],[0,0],[1,1]], anchor("above"), "fit"),
        ("anchor_left", [[2,0,1,1]], [[1,0,1,1]], anchor("left"), "fit"),
        ("anchor_inside", [[1,1,1],[1,2,1],[1,1,1]], [[1,1,1],[1,1,1],[1,1,1]], anchor("inside_bbox"), "fit"),
        ("expected_mismatch", [[1,0,2]], [[2,0,1]], render(), "mismatch"),
        ("intermediate_oversize", [[1]*16], [[1]*16],
         {"steps":[{"op":"scale","factor":2},{"op":"crop_nonbackground","background":0}]}, "out_of_domain"),
    ]
    return [{"control_id": name, "task": {"task_id": "synthetic-"+name,
             "demos": [{"input": inp, "output": out}]}, "plan": plan,
             "expected_status": status, "category": "positive" if status == "fit" else "negative"}
            for name, inp, out, plan, status in rows]
