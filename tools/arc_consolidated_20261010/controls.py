"""Independent synthetic demonstrations for the consolidated demos-only gate.

This ordinary trusted Python reference does not import the production compiler,
bounded VM, or their helpers. It is a control oracle, never a generated-program
execution path. Its flood fill is deliberately independent of the VM primitive.
The 64 positive episodes cover eight fixed families; the 64 negatives retain
their original tasks and targets but substitute legal wrong programs. Separate
target-mutant detector controls are not part of the required gate controls.
These controls are examples, not exhaustive parameter coverage or ARC scores.
"""
from __future__ import annotations

from collections import Counter, deque
from copy import deepcopy

CONTROL_VERSION = "irisx/consolidated-independent-controls-v2"
FAMILIES = (
    "mask_bbox", "connectivity", "multicolor_groups", "render", "tie_empty",
    "nonzero_mode", "anchor_relations", "composition_panels",
)


def _grid(grid):
    if type(grid) is not list or not 1 <= len(grid) <= 30:
        raise ValueError("reference grid height must be 1..30")
    if type(grid[0]) is not list or not 1 <= len(grid[0]) <= 30:
        raise ValueError("reference grid width must be 1..30")
    width = len(grid[0])
    if any(type(row) is not list or len(row) != width or
           any(type(c) is not int or not 0 <= c <= 9 for c in row) for row in grid):
        raise ValueError("reference requires a rectangular integer color grid")
    return deepcopy(grid)


def _background(grid, value):
    if value == "most_frequent":
        counts = Counter(c for row in grid for c in row)
        return min(counts, key=lambda c: (-counts[c], c))
    if type(value) is not int or not 0 <= value <= 9:
        raise ValueError("invalid reference background")
    return value


def _objects(grid, partition, background):
    pixels = {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row)
              if value != background}
    if partition == "per_color":
        groups = {}
        for r, c in sorted(pixels):
            groups.setdefault(grid[r][c], set()).add((r, c))
        return [frozenset(p) for p in groups.values()]
    if partition not in ("same_color_cc4", "same_color_cc8", "foreground_cc4", "foreground_cc8"):
        raise ValueError("unknown reference partition")
    mono = partition.startswith("same_color")
    diagonal = partition.endswith("8")
    moves = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
             if (dr or dc) and (diagonal or abs(dr) + abs(dc) == 1)]
    groups = []
    while pixels:
        root = min(pixels)
        color = grid[root[0]][root[1]]
        pixels.remove(root)
        queue, component = deque([root]), {root}
        while queue:
            r, c = queue.popleft()
            for dr, dc in moves:
                point = (r + dr, c + dc)
                if point in pixels and (not mono or grid[point[0]][point[1]] == color):
                    pixels.remove(point)
                    component.add(point)
                    queue.append(point)
        groups.append(frozenset(component))
    return groups


def _select(objects, selector, grid):
    kind = selector["kind"]
    if kind == "all":
        return list(objects)
    if kind == "containscolor":
        color = selector["color"]
        return [obj for obj in objects if any(grid[r][c] == color for r, c in obj)]
    if kind not in ("minarea", "maxarea"):
        raise ValueError("unknown reference selector")
    if not objects:
        return []
    extreme = (min if kind == "minarea" else max)(map(len, objects))
    return [obj for obj in objects if len(obj) == extreme]


def _bbox(points):
    return (min(r for r, _ in points), min(c for _, c in points),
            max(r for r, _ in points) + 1, max(c for _, c in points) + 1)


def _render(grid, selected, background, action):
    pixels = set().union(*selected) if selected else set()
    kind = action["kind"]
    if kind == "keep_mask":
        return [[value if (r, c) in pixels else background
                 for c, value in enumerate(row)] for r, row in enumerate(grid)]
    if kind in ("erase_mask", "paint_mask"):
        color = background if kind == "erase_mask" else action["color"]
        return [[color if (r, c) in pixels else value
                 for c, value in enumerate(row)] for r, row in enumerate(grid)]
    if kind not in ("crop_bbox", "crop_mask"):
        raise ValueError("unknown reference render action")
    if not pixels:
        return deepcopy(grid)
    r0, c0, r1, c1 = _bbox(pixels)
    return [[grid[r][c] if kind == "crop_bbox" or (r, c) in pixels else background
             for c in range(c0, c1)] for r in range(r0, r1)]


def _related(focus, anchor, relation):
    fr0, fc0, fr1, fc1 = _bbox(focus)
    ar0, ac0, ar1, ac1 = _bbox(anchor)
    if relation == "above":
        return fr1 <= ar0
    if relation == "below":
        return fr0 >= ar1
    if relation == "left":
        return fc1 <= ac0
    if relation == "right":
        return fc0 >= ac1
    if relation == "inside_bbox":
        return ar0 <= fr0 and ac0 <= fc0 and fr1 <= ar1 and fc1 <= ac1
    raise ValueError("unknown reference anchor relation")


def _panels(grid, axis, gap):
    if axis not in ("rows", "cols") or type(gap) is not int or gap not in (0, 1):
        raise ValueError("invalid reference split")
    length = len(grid) if axis == "rows" else len(grid[0])
    available = length - gap
    if available < 2 or available % 2:
        return None
    width = available // 2
    if axis == "rows":
        return deepcopy(grid[:width]), deepcopy(grid[width+gap:]), width
    return ([row[:width] for row in grid], [row[width+gap:] for row in grid], width)


def reference_plan(plan, grid):
    """Apply trusted fixture data independently, checking each intermediate grid.

    This is not a security validator for untrusted plans. All generated/model
    source belongs in the resource-guarded production verifier, never here.
    """
    if type(plan) is not dict or set(plan) != {"steps"} or type(plan["steps"]) is not list or not 1 <= len(plan["steps"]) <= 3:
        raise ValueError("reference plan needs one to three steps")
    current = _grid(grid)
    for step in plan["steps"]:
        op = step["op"]
        if op in ("object_select_render", "anchored_recolor"):
            background = _background(current, step["background"])
            objects = _objects(current, step["partition"], background)
            if op == "object_select_render":
                selected = _select(objects, step["selector"], current)
                current = _render(current, selected, background, step["action"])
            else:
                anchors = _select(objects, step["anchor_selector"], current)
                if len(anchors) == 1:
                    anchor = anchors[0]
                    # Both selectors see the original complete partition.
                    # Exclusion does not introduce an implicit next-largest
                    # or next-smallest selector when anchor is the extreme.
                    focus = [obj for obj in _select(objects, step["focus_selector"], current)
                             if obj != anchor]
                    selected = [obj for obj in focus if _related(obj, anchor, step["relation"])]
                    counts = Counter(current[r][c] for r, c in anchor)
                    color = min(counts, key=lambda c: (-counts[c], c))
                    current = _render(current, selected, background,
                                      {"kind": "paint_mask", "color": color})
        elif op in ("equal_panels_boolean", "equal_panels_copy"):
            split = _panels(current, step["axis"], step["gap"])
            if split is not None:
                first, second, width = split
                if op == "equal_panels_boolean":
                    background = _background(current, step["background"])
                    current = [[step["foreground"] if
                                (step["truth_table"] >> (2 * int(a != background) + int(b != background))) & 1
                                else background for a, b in zip(ar, br)]
                               for ar, br in zip(first, second)]
                else:
                    source = first if step["direction"] == "first_to_second" else second
                    start = width + step["gap"] if step["direction"] == "first_to_second" else 0
                    out = deepcopy(current)
                    for r, row in enumerate(source):
                        for c, color in enumerate(row):
                            rr, cc = (start+r, c) if step["axis"] == "rows" else (r, start+c)
                            out[rr][cc] = color
                    current = out
        elif op == "identity":
            current = deepcopy(current)
        elif op == "transpose":
            current = [list(row) for row in zip(*current)]
        elif op == "rotate":
            for _ in range(step["turns"]):
                current = [list(row) for row in zip(*current[::-1])]
        elif op == "flip_horizontal":
            current = [row[::-1] for row in current]
        elif op == "flip_vertical":
            current = current[::-1]
        elif op == "recolor":
            current = [[step["target"] if c == step["source"] else c for c in row] for row in current]
        elif op == "crop_nonbackground":
            selected = {(r, c) for r, row in enumerate(current) for c, value in enumerate(row)
                        if value != step["background"]}
            current = _render(current, [selected] if selected else [], step["background"], {"kind": "crop_bbox"})
        elif op == "largest_component_crop":
            objects = _objects(current, "same_color_cc"+str(step["connectivity"]), step["background"])
            selected = [max(objects, key=len)] if objects else []
            current = _render(current, selected, step["background"], {"kind": "crop_bbox"})
        elif op == "scale":
            factor = step["factor"]
            current = [[value for value in row for _ in range(factor)] for row in current for _ in range(factor)]
        elif op == "tile":
            current = [row * step["columns"] for _ in range(step["rows"]) for row in current]
        else:
            raise ValueError("unsupported trusted reference operation")
        current = _grid(current)
    return current


def _object(partition="same_color_cc4", background=0, selector="all", action="keep_mask", *, color=2, paint=9):
    select = {"kind": selector, **({"color": color} if selector == "containscolor" else {})}
    render = {"kind": action, **({"color": paint} if action == "paint_mask" else {})}
    return {"op": "object_select_render", "partition": partition, "background": background,
            "selector": select, "action": render}


def _anchor(relation, *, partition="same_color_cc4", background=0, anchor="maxarea", focus="all", color=2):
    return {"op": "anchored_recolor", "partition": partition, "background": background,
            "anchor_selector": {"kind": anchor}, "relation": relation,
            "focus_selector": {"kind": focus, **({"color": color} if focus == "containscolor" else {})}}


def _case_specs():
    # Each row is an engineering hypothesis with an explicit plan and synthetic
    # input. A mirrored second input is independently evaluated, never a target
    # transformation of production output. No exposed task IDs are consulted.
    ring = [[0,0,0,0,0,0,0], [0,2,2,2,0,3,0], [0,2,4,2,0,3,0],
            [0,2,2,2,0,0,0], [0,0,0,0,0,0,0]]
    diagonal = [[1,0,0,2], [0,1,2,0], [0,3,1,0], [3,0,0,1]]
    mixed = [[0,0,0,0,0,0], [0,1,2,0,3,0], [0,2,1,0,0,0],
             [0,0,0,3,0,0], [0,1,0,0,0,0]]
    ties = [[0,1,0,2,0], [0,0,0,0,0], [0,3,0,4,0]]
    blank = [[0,0,0], [0,0,0]]
    nonzero = [[7,7,7,7,7], [7,1,1,7,2], [7,1,7,7,2], [7,7,7,7,7]]
    directions = [[0]*7 for _ in range(7)]
    for r, c, color in ((1,3,1), (5,3,2), (3,0,3), (3,6,4),
                        (3,2,8), (3,3,8), (3,4,8)):
        directions[r][c] = color
    anchor_mixed = [[0,0,0,0,0], [0,6,2,0,0], [0,0,0,0,0], [0,1,0,0,0]]
    panels = [[0,1,0,2], [1,0,2,0]]
    gap_panels = [[0,1,9,0,2], [1,0,9,2,0]]
    cases = {family: [] for family in FAMILIES}
    add = lambda family, steps, grid: cases[family].append(({"steps": steps}, deepcopy(grid)))
    for selector in ("containscolor", "maxarea"):
        for action in ("crop_bbox", "crop_mask"):
            add("mask_bbox", [_object(selector=selector, action=action)], ring)
    for action in ("crop_bbox", "crop_mask"):
        add("mask_bbox", [_object(selector="all", action=action)], ring)
        add("mask_bbox", [_object(partition="per_color", selector="containscolor", color=3, action=action)], mixed)
    for partition in ("same_color_cc4", "same_color_cc8", "foreground_cc4", "foreground_cc8"):
        for selector in ("minarea", "maxarea"):
            add("connectivity", [_object(partition=partition, selector=selector)], diagonal)
    for partition in ("same_color_cc4", "foreground_cc4", "foreground_cc8", "per_color"):
        for action in ("keep_mask", "crop_mask"):
            add("multicolor_groups", [_object(partition=partition, selector="containscolor", color=1, action=action)], mixed)
    for action in ("keep_mask", "erase_mask", "paint_mask", "crop_bbox"):
        for selector in ("all", "containscolor"):
            add("render", [_object(selector=selector, action=action)], ring)
    for selector in ("minarea", "maxarea"):
        add("tie_empty", [_object(selector=selector, action="paint_mask")], ties)
    for action in ("keep_mask", "erase_mask", "paint_mask", "crop_bbox", "crop_mask"):
        add("tie_empty", [_object(action=action)], blank)
    add("tie_empty", [_anchor("above")], ties)
    for background in (7, "most_frequent"):
        for action in ("keep_mask", "erase_mask", "crop_bbox"):
            add("nonzero_mode", [_object(background=background, selector="maxarea", action=action)], nonzero)
    add("nonzero_mode", [_object(background="most_frequent", action="keep_mask", selector="containscolor", color=4)], [[4,2], [2,4]])
    add("nonzero_mode", [_object(background="most_frequent", selector="maxarea", action="paint_mask", paint=7),
                         _object(background="most_frequent", action="crop_mask")], nonzero)
    for relation in ("above", "below", "left", "right"):
        add("anchor_relations", [_anchor(relation)], directions)
    add("anchor_relations", [_anchor("inside_bbox")], ring)
    # IR v2 removes the dead same-mask relation. This tied-anchor right plan
    # remains an explicit no-op on exactly the same retained inputs/targets.
    add("anchor_relations", [_anchor("right")], ties)
    add("anchor_relations", [_anchor("below", partition="foreground_cc4")], anchor_mixed)
    add("anchor_relations", [_anchor("above", anchor="minarea")], ring)
    add("composition_panels", [_object(selector="maxarea", action="crop_bbox"), {"op":"transpose"}], ring)
    add("composition_panels", [_object(selector="maxarea", action="crop_mask"), {"op":"transpose"}, {"op":"rotate", "turns":2}], ring)
    for table in (6, 8):
        add("composition_panels", [{"op":"equal_panels_boolean", "axis":"cols", "gap":0,
                                     "truth_table":table, "foreground":3, "background":0}], panels)
    add("composition_panels", [{"op":"equal_panels_boolean", "axis":"rows", "gap":1,
                                 "truth_table":14, "foreground":4, "background":"most_frequent"}],
        [[0,1],[1,0],[9,9],[0,2],[2,0]])
    for direction in ("first_to_second", "second_to_first"):
        add("composition_panels", [{"op":"equal_panels_copy", "axis":"cols", "gap":1, "direction":direction}], gap_panels)
    add("composition_panels", [{"op":"equal_panels_copy", "axis":"rows", "gap":0, "direction":"first_to_second"}], panels)
    if any(len(group) != 8 for group in cases.values()):
        raise AssertionError("control families must each have exactly eight episodes")
    return cases


def _positive_controls():
    controls = []
    for family, cases in _case_specs().items():
        for index, (plan, grid) in enumerate(cases):
            # Horizontal reflection preserves dimensions, valid colors, and
            # empty inputs while varying directional/contextual arrangements.
            inputs = [grid, [row[::-1] for row in grid]]
            if inputs[1] == grid:
                background = _background(grid, plan["steps"][0].get("background", 0))
                inputs[1].append([background] * len(grid[0]))
            demos = [{"input": deepcopy(value), "output": reference_plan(plan, value)} for value in inputs]
            identifier = f"control_{family}_{index:02d}_positive"
            controls.append({"control_id": identifier, "family": family, "polarity": "positive",
                             "task": {"task_id": identifier, "demos": demos},
                             "plan": deepcopy(plan), "expected_status": "fit",
                             "provenance": {"kind": "independent_reference", "version": CONTROL_VERSION}})
            if family == "anchor_relations" and index == 5:
                controls[-1]["provenance"]["schema_revision"] = {
                    "before_relation":"same_normalized_mask", "after_relation":"right",
                    "reason":"IR v2 removes dead same-mask relation; tied anchor preserves original task and targets"}
    return controls


def _wrong_program_mutations(plan, family):
    """Finite deterministic legal edits, independent of task IDs and compiler.

    Family-relevant edits come first. A mutation is selected only when the
    independent reference proves a mismatch on an unchanged positive demo.
    Equivalent edits are skipped, not counted as negative controls. Nothing
    in this helper generates expected targets or changes a task's contents.
    """
    for index, step in enumerate(plan["steps"]):
        op = step["op"]
        edits = []
        if op in ("object_select_render", "anchored_recolor"):
            partitions = ("same_color_cc4", "same_color_cc8", "foreground_cc4", "foreground_cc8", "per_color")
            if family == "connectivity":
                opposite = {"same_color_cc4":"same_color_cc8", "same_color_cc8":"same_color_cc4",
                            "foreground_cc4":"foreground_cc8", "foreground_cc8":"foreground_cc4"}
                first = opposite.get(step["partition"], "same_color_cc4")
                partitions = (first,) + tuple(p for p in partitions if p != first)
            partition_edits = [("partition", p) for p in partitions if p != step["partition"]]
            background_edits = [("background", b) for b in (0,"most_frequent",1,7,9) if b != step["background"]]
            if op == "object_select_render":
                action = step["action"]["kind"]
                actions = ("crop_mask","crop_bbox","erase_mask","keep_mask","paint_mask")
                if action == "crop_mask":
                    actions = ("crop_bbox",) + tuple(a for a in actions if a != "crop_bbox")
                action_edits = [("action", {"kind":a, **({"color":9} if a == "paint_mask" else {})})
                                for a in actions if a != action]
                if action == "paint_mask":
                    action_edits.insert(0, ("action", {"kind":"paint_mask", "color":(step["action"]["color"]+1)%10}))
                selector_edits = [("selector", {"kind":s}) for s in ("all","minarea","maxarea")
                                  if {"kind":s} != step["selector"]]
                selector_edits += [("selector", {"kind":"containscolor", "color":c}) for c in (1,2,9)
                                   if {"kind":"containscolor","color":c} != step["selector"]]
                if family in ("connectivity","multicolor_groups"):
                    edits = partition_edits + selector_edits + action_edits + background_edits
                elif family == "nonzero_mode":
                    edits = background_edits + action_edits + selector_edits + partition_edits
                else:
                    edits = action_edits + selector_edits + partition_edits + background_edits
            else:
                edits = [("relation",r) for r in ("above","below","left","right","inside_bbox") if r != step["relation"]]
                edits += [("anchor_selector", {"kind": "minarea" if step["anchor_selector"]["kind"] == "maxarea" else "maxarea"})]
                edits += partition_edits + background_edits
        elif op == "equal_panels_boolean":
            # Flip exactly one Boolean output row; the reference establishes
            # that the changed bit is exercised by a retained demonstration.
            edits = [("truth_table",step["truth_table"] ^ bit) for bit in (1,2,4,8)]
            edits += [("foreground",(step["foreground"]+1)%10), ("gap",1-step["gap"]),
                      ("axis","cols" if step["axis"] == "rows" else "rows")]
        elif op == "equal_panels_copy":
            edits = [("direction", "second_to_first" if step["direction"] == "first_to_second" else "first_to_second"),
                     ("gap",1-step["gap"]), ("axis","cols" if step["axis"] == "rows" else "rows")]
        elif op == "rotate":
            edits = [("turns",turns) for turns in (1,2,3) if turns != step["turns"]]
        for field, replacement in edits:
            mutated = deepcopy(plan)
            mutated["steps"][index][field] = deepcopy(replacement)
            yield mutated, [{"path":["steps",index,field], "before":deepcopy(step[field]), "after":deepcopy(replacement)}]
        if op == "object_select_render":
            # Empty objects can make every single-field edit equivalent. This
            # legal two-field error treats empty background as an object, then
            # paints that mask, exposing incorrect empty/background semantics.
            for background in (1,7,9,0):
                mutated = deepcopy(plan)
                mutated["steps"][index]["background"] = background
                mutated["steps"][index]["action"] = {"kind":"paint_mask", "color":(background+1)%10}
                changes = [{"path":["steps",index,key], "before":deepcopy(step[key]),
                            "after":deepcopy(mutated["steps"][index][key])}
                           for key in ("background","action") if step[key] != mutated["steps"][index][key]]
                yield mutated, changes
        elif op == "anchored_recolor":
            # A tied-anchor no-op can make all single-field mistakes silent.
            # A wrong background and wrong containment relation together give
            # a legal semantic negative without inventing an anchor tie rule.
            for background in (1,7,9,0):
                mutated = deepcopy(plan)
                mutated["steps"][index]["background"] = background
                mutated["steps"][index]["relation"] = "inside_bbox"
                changes = [{"path":["steps",index,key], "before":deepcopy(step[key]),
                            "after":deepcopy(mutated["steps"][index][key])}
                           for key in ("background","relation") if step[key] != mutated["steps"][index][key]]
                yield mutated, changes
    # A deleted composition step is a legal semantic mutation; preserve at
    # least one step. This matters when a geometry operation is symmetric on
    # one demo but is required on the other.
    if len(plan["steps"]) > 1:
        for index in range(len(plan["steps"])-1, -1, -1):
            mutated = deepcopy(plan)
            before = mutated["steps"].pop(index)
            yield mutated, [{"path":["steps",index], "before":before, "after":None}]


def synthetic_controls():
    """Return 64 independent-reference positives and 64 wrong-program negatives.

    A negative shares its positive's exact task, including task_id, inputs and
    expected outputs. Its distinct control_id identifies the different plan
    check. Every negative records its legal edits and the demo indices where
    the independent reference finds a mismatch. Admission of every plan and
    Linux-only resource-guarded VM acceptance are tested separately.
    """
    result = []
    for positive in _positive_controls():
        result.append(positive)
        for plan, changes in _wrong_program_mutations(positive["plan"], positive["family"]):
            mismatches = [index for index,demo in enumerate(positive["task"]["demos"])
                          if reference_plan(plan,demo["input"]) != demo["output"]]
            if not mismatches:
                continue
            result.append({"control_id": positive["control_id"].replace("_positive","_negative"),
                           "family":positive["family"], "polarity":"negative",
                           "task":deepcopy(positive["task"]), "plan":plan, "expected_status":"mismatch",
                           "provenance":{"kind":"legal_wrong_program", "version":CONTROL_VERSION,
                                         "positive_control_id":positive["control_id"], "edits":changes,
                                         "mismatching_demo_indices":mismatches}})
            break
        else:
            raise AssertionError("no independent semantic negative for " + positive["control_id"])
    return result


def detector_controls():
    """Return the 64 historical target-mutant checks, outside required controls.

    These detect a scorer that ignores the expected target. They are explicitly
    not semantic-program negatives and are never returned by synthetic_controls.
    """
    result = []
    for positive in _positive_controls():
        task = deepcopy(positive["task"])
        identifier = positive["control_id"].replace("control_","detector_").replace("_positive","_target")
        task["task_id"] = identifier
        edits = []
        for index,demo in enumerate(task["demos"]):
            before = demo["output"][0][0]
            demo["output"][0][0] = (before+1)%10
            edits.append({"path":["demos",index,"output",0,0], "before":before, "after":demo["output"][0][0]})
        result.append({"control_id":identifier, "family":positive["family"], "polarity":"detector",
                       "task":task, "plan":deepcopy(positive["plan"]), "expected_status":"mismatch",
                       "provenance":{"kind":"target_mutant_detector_only", "version":CONTROL_VERSION,
                                     "positive_control_id":positive["control_id"], "edits":edits}})
    return result
