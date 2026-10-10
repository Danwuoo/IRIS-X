"""Independent control-oracle checks; never host-execute generated source."""
from __future__ import annotations

import ast
from collections import Counter
from copy import deepcopy
import hashlib
import inspect
import json
import unittest

from tools.arc_consolidated_20261010 import controls
from tools.arc_consolidated_20261010.controls import (
    FAMILIES, detector_controls, reference_plan, synthetic_controls,
)
from tools.arc_consolidated_20261010.verifier import capability


def unary(*, partition="same_color_cc4", background=0, selector="all", action="keep_mask", color=2, paint=9):
    return {"op":"object_select_render", "partition":partition, "background":background,
            "selector":{"kind":selector, **({"color":color} if selector == "containscolor" else {})},
            "action":{"kind":action, **({"color":paint} if action == "paint_mask" else {})}}


def anchor(relation, *, partition="same_color_cc4", background=0, kind="maxarea", focus="all"):
    return {"op":"anchored_recolor", "partition":partition, "background":background,
            "anchor_selector":{"kind":kind}, "focus_selector":{"kind":focus}, "relation":relation}


def apply(step, grid):
    return reference_plan({"steps":[step]}, grid)


class ControlSetTests(unittest.TestCase):
    def test_exact_counts_and_schema(self):
        entries = synthetic_controls()
        self.assertEqual(len(entries), 128)
        self.assertEqual(len({e["control_id"] for e in entries}), 128)
        self.assertEqual(Counter(e["polarity"] for e in entries), {"positive":64, "negative":64})
        self.assertEqual(Counter(e["family"] for e in entries), {family:16 for family in FAMILIES})
        self.assertEqual(Counter((e["family"],e["polarity"]) for e in entries),
                         {(f,p):8 for f in FAMILIES for p in ("positive","negative")})
        for entry in entries:
            self.assertEqual(set(entry), {"control_id","family","polarity","task","plan","expected_status","provenance"})
            self.assertEqual(set(entry["task"]), {"task_id","demos"})
            self.assertEqual(entry["control_id"].replace("_negative","_positive"), entry["task"]["task_id"])
            self.assertLessEqual(len(entry["control_id"]), 64)
            self.assertEqual(len(entry["task"]["demos"]), 2)
            self.assertNotEqual(entry["task"]["demos"][0]["input"], entry["task"]["demos"][1]["input"])
            for demo in entry["task"]["demos"]:
                self.assertEqual(set(demo), {"input","output"})
                for grid in demo.values():
                    self.assertTrue(1 <= len(grid) <= 30)
                    self.assertTrue(1 <= len(grid[0]) <= 30)
                    self.assertTrue(all(len(row) == len(grid[0]) for row in grid))
                    self.assertTrue(all(type(c) is int and 0 <= c <= 9 for row in grid for c in row))
        def keys(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    yield k
                    yield from keys(v)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)
        self.assertFalse(set(keys(entries)) & {"test","query","gold","solutions"})

    def test_negative_programs_change_semantics_with_original_targets(self):
        entries = synthetic_controls()
        for positive, negative in zip(entries[::2], entries[1::2]):
            self.assertEqual(positive["expected_status"], "fit")
            self.assertEqual(negative["expected_status"], "mismatch")
            self.assertNotEqual(positive["plan"], negative["plan"])
            self.assertEqual(positive["task"], negative["task"])
            self.assertIsNot(positive["task"], negative["task"])
            provenance = negative["provenance"]
            self.assertEqual(provenance["kind"], "legal_wrong_program")
            self.assertEqual(provenance["positive_control_id"], positive["control_id"])
            mismatches = []
            for index,demo in enumerate(positive["task"]["demos"]):
                self.assertEqual(reference_plan(positive["plan"],demo["input"]),demo["output"])
                if reference_plan(negative["plan"],demo["input"]) != demo["output"]:
                    mismatches.append(index)
            self.assertTrue(mismatches)
            self.assertEqual(provenance["mismatching_demo_indices"],mismatches)
            replay = deepcopy(positive["plan"])
            self.assertTrue(provenance["edits"])
            for edit in provenance["edits"]:
                target = replay
                for key in edit["path"][:-1]:
                    target = target[key]
                key = edit["path"][-1]
                self.assertEqual(target[key],edit["before"])
                if edit["after"] is None:
                    del target[key]
                else:
                    target[key] = deepcopy(edit["after"])
            self.assertEqual(replay,negative["plan"])

    def test_all_original_positive_tasks_remain_byte_identical(self):
        tasks = [e["task"] for e in synthetic_controls()[::2]]
        payload = json.dumps(tasks,sort_keys=True,separators=(",",":"))
        self.assertEqual(hashlib.sha256(payload.encode()).hexdigest(),
                         "d4f0168553db088409bfe5f4f2ec08f6bd39a194f4554ef5deb83856f0335d50")
        changed = synthetic_controls()[::2][8*6+5]
        self.assertEqual(changed["plan"]["steps"][0]["relation"],"right")
        self.assertEqual(changed["provenance"]["schema_revision"]["before_relation"],"same_normalized_mask")

    def test_target_mutants_are_separate_detector_controls(self):
        positives = synthetic_controls()[::2]
        detectors = detector_controls()
        self.assertEqual(len(detectors),64)
        self.assertFalse({e["control_id"] for e in detectors} & {e["control_id"] for e in synthetic_controls()})
        for positive, detector in zip(positives,detectors):
            self.assertEqual(detector["polarity"],"detector")
            self.assertEqual(detector["provenance"]["kind"],"target_mutant_detector_only")
            self.assertEqual(detector["plan"],positive["plan"])
            self.assertEqual(detector["expected_status"],"mismatch")
            for pos, neg in zip(positive["task"]["demos"], detector["task"]["demos"]):
                self.assertEqual(pos["input"], neg["input"])
                expected = reference_plan(positive["plan"], pos["input"])
                self.assertEqual(pos["output"], expected)
                self.assertNotEqual(neg["output"], expected)
                changed = [(r,c) for r,row in enumerate(pos["output"]) for c,value in enumerate(row)
                           if value != neg["output"][r][c]]
                self.assertEqual(changed, [(0,0)])
                self.assertEqual(neg["output"][0][0], (expected[0][0]+1)%10)

    def test_deterministic_fresh_results(self):
        first, second = synthetic_controls(), synthetic_controls()
        self.assertEqual(json.dumps(first,sort_keys=True), json.dumps(second,sort_keys=True))
        first[0]["task"]["demos"][0]["input"][0][0] = 9
        first[0]["plan"]["steps"][0]["selector"]["kind"] = "all"
        self.assertEqual(second, synthetic_controls())

    def test_oracle_has_no_production_dependency_or_dynamic_execution(self):
        tree = ast.parse(inspect.getsource(controls))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = ([n.name for n in node.names] if isinstance(node,ast.Import)
                         else [node.module or ""])
                self.assertFalse(any("arc_object_ir" in n or "arc_bounded" in n or "verifier" in n for n in names))
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                self.assertNotIn(node.func.id, {"exec","eval","compile"})

    def test_all_plans_pass_compiler_admission_without_execution(self):
        from tools.arc_consolidated_20261010.arc_object_ir import compile_plan, validate_plan
        for entry in synthetic_controls() + detector_controls():
            with self.subTest(control=entry["control_id"]):
                self.assertEqual(validate_plan(entry["plan"]), entry["plan"])
                source = compile_plan(entry["plan"])
                self.assertTrue(isinstance(source,str))
                self.assertLessEqual(len(source.encode()),32768)
                self.assertLessEqual(sum(1 for _ in ast.walk(ast.parse(source))),2048)


class ObjectOracleTests(unittest.TestCase):
    def test_mask_bbox_and_union_not_object_by_object_crop(self):
        grid = [[2,2,2,0,2], [2,3,2,0,0], [2,2,2,0,0]]
        base = {"partition":"per_color", "selector":"containscolor", "color":2}
        self.assertEqual(apply(unary(**base,action="crop_bbox"),grid), grid)
        self.assertEqual(apply(unary(**base,action="crop_mask"),grid),
                         [[2,2,2,0,2],[2,0,2,0,0],[2,2,2,0,0]])

    def test_four_vs_eight_connectivity_and_preserved_original_colors(self):
        grid = [[1,0,0], [0,2,0], [0,0,2]]
        self.assertEqual(apply(unary(partition="foreground_cc8",selector="maxarea"),grid),grid)
        self.assertEqual(apply(unary(partition="same_color_cc8",selector="maxarea"),grid),
                         [[0,0,0],[0,2,0],[0,0,2]])
        self.assertEqual(apply(unary(partition="foreground_cc4",selector="minarea"),grid),grid)
        self.assertEqual(apply(unary(partition="same_color_cc4",selector="maxarea"),grid),grid)

    def test_discrete_color_group_differs_from_components(self):
        grid = [[1,0,1], [0,2,0], [0,2,0]]
        self.assertEqual(apply(unary(partition="per_color",selector="maxarea"),grid),grid)
        self.assertEqual(apply(unary(partition="same_color_cc4",selector="maxarea"),grid),
                         [[0,0,0],[0,2,0],[0,2,0]])
        mixed = [[1,2,0],[0,2,0]]
        self.assertEqual(apply(unary(partition="foreground_cc4",selector="containscolor",color=1),mixed),mixed)

    def test_ties_keep_all_and_empty_action_semantics(self):
        grid = [[1,0,2],[0,0,0]]
        for selector in ("minarea","maxarea"):
            self.assertEqual(apply(unary(selector=selector),grid),grid)
        for action in ("crop_bbox","crop_mask","erase_mask","paint_mask"):
            self.assertEqual(apply(unary(selector="containscolor",color=9,action=action),grid),grid)
        self.assertEqual(apply(unary(selector="containscolor",color=9,action="keep_mask"),grid),
                         [[0,0,0],[0,0,0]])

    def test_nonzero_background_and_mode_tie_lowest(self):
        grid = [[7,7,7],[7,1,2]]
        expected = [[7,7,7],[7,1,7]]
        for background in (7,"most_frequent"):
            self.assertEqual(apply(unary(background=background,selector="containscolor",color=1),grid),expected)
        self.assertEqual(apply(unary(background="most_frequent",action="erase_mask"),[[4,2],[2,4]]),
                         [[2,2],[2,2]])

    def test_mode_is_resolved_again_for_each_step(self):
        plan = {"steps":[unary(background="most_frequent",action="paint_mask",paint=7),
                          unary(background="most_frequent",action="erase_mask")]}
        self.assertEqual(reference_plan(plan,[[0,0,1],[0,2,2]]), [[0,0,0],[0,0,0]])

    def test_reference_preserves_input_and_rejects_intermediate_oversize(self):
        grid = [[1,0],[0,2]]
        saved = deepcopy(grid)
        output = apply(unary(action="paint_mask"),grid)
        output[0][0] = 8
        self.assertEqual(grid,saved)
        with self.assertRaises(ValueError):
            reference_plan({"steps":[{"op":"scale","factor":2}, {"op":"crop_nonbackground","background":0}]},
                           [[1]*16 for _ in range(16)])
        edge = [[0]*30 for _ in range(30)]
        edge[0][29],edge[29][0] = 1,2
        self.assertEqual(apply(unary(),edge),edge)
        for malformed in ([[True]], [[1.0]], [[-1]], [[10]], [], [[]], [[1],[1,2]]):
            with self.subTest(grid=malformed), self.assertRaises(ValueError):
                apply({"op":"identity"},malformed)


class AnchorOracleTests(unittest.TestCase):
    def test_all_four_nonoverlap_directions_include_touching_bbox_edges(self):
        # Foreground pixels touch along a boundary but have distinct colors.
        grid = [[0,1,0],[3,8,4],[0,8,0],[0,2,0]]
        positions = {"above":(0,1), "below":(3,1), "left":(1,0), "right":(1,2)}
        for relation,(r,c) in positions.items():
            expected = deepcopy(grid)
            expected[r][c] = 8
            self.assertEqual(apply(anchor(relation),grid),expected)

    def test_inside_bbox_includes_boundary_without_recoloring_anchor(self):
        grid = [[8,8,8],[8,2,0],[8,8,8]]
        expected = [[8,8,8],[8,8,0],[8,8,8]]
        self.assertEqual(apply(anchor("inside_bbox"),grid),expected)

    def test_unique_anchor_required(self):
        for grid in ([[1,0,2]], [[0,0,0]], [[1,0,2],[1,0,2]]):
            for kind in ("minarea","maxarea"):
                self.assertEqual(apply(anchor("left",kind=kind),grid),grid)

    def test_removed_same_mask_relation_is_not_a_legal_control_plan(self):
        from tools.arc_consolidated_20261010.arc_object_ir import PlanError, validate_plan
        with self.assertRaises(PlanError):
            validate_plan({"steps":[anchor("same_normalized_mask")]})
        self.assertTrue(all(step.get("relation") != "same_normalized_mask"
                            for entry in synthetic_controls() for step in entry["plan"]["steps"]))

    def test_dominant_anchor_color_tie_lowest_and_simultaneous_selection(self):
        grid = [[0,6,2,0,0],[0,0,0,0,0],[0,1,0,3,0]]
        expected = [[0,6,2,0,0],[0,0,0,0,0],[0,2,0,2,0]]
        self.assertEqual(apply(anchor("below",partition="foreground_cc4"),grid),expected)

    def test_focus_extremum_is_computed_before_excluding_anchor(self):
        grid = [[1,1,0,2,0],[0,0,0,0,0],[8,8,8,8,0]]
        self.assertEqual(apply(anchor("above",focus="maxarea"),grid),grid)
        self.assertEqual(apply(anchor("below",kind="minarea",focus="minarea"),grid),grid)
        self.assertEqual(apply(anchor("above",focus="minarea"),grid),
                         [[1,1,0,8,0],[0,0,0,0,0],[8,8,8,8,0]])


class PanelOracleTests(unittest.TestCase):
    def test_all_sixteen_tables_all_ten_backgrounds_and_both_axes(self):
        for background in range(10):
            other = (background+1)%10
            paint = (background+2)%10
            # Positions enumerate bit pairs 00,01,10,11 in truth-table order.
            first = [[background,background,other,other]]
            second = [[background,other,background,other]]
            for table in range(16):
                expected = [[paint if bit == "1" else background for bit in f"{table:04b}"[::-1]]]
                for axis in ("rows","cols"):
                    for gap in (0,1):
                        grid = (first + ([[other]*4] if gap else []) + second if axis == "rows"
                                else [first[0] + ([other] if gap else []) + second[0]])
                        step = {"op":"equal_panels_boolean", "axis":axis, "gap":gap,
                                "truth_table":table,"foreground":paint,"background":background}
                        with self.subTest(background=background,table=table,axis=axis,gap=gap):
                            self.assertEqual(apply(step,grid),expected)

    def test_invalid_split_is_copy_and_valid_shape_boundaries(self):
        for axis in ("rows","cols"):
            for gap in (0,1):
                for length in (1,2,3,4,29,30):
                    grid = [[1]*2 for _ in range(length)] if axis == "rows" else [[1]*length for _ in range(2)]
                    step = {"op":"equal_panels_boolean","axis":axis,"gap":gap,
                            "truth_table":0,"foreground":3,"background":0}
                    output = apply(step,grid)
                    available = length-gap
                    if available < 2 or available%2:
                        self.assertEqual(output,grid)
                        self.assertIsNot(output,grid)
                    else:
                        height,width = (available//2,2) if axis == "rows" else (2,available//2)
                        self.assertEqual(output,[[0]*width for _ in range(height)])

    def test_copy_both_axes_directions_and_separator_retention(self):
        for axis in ("rows","cols"):
            for gap in (0,1):
                for direction in ("first_to_second","second_to_first"):
                    a,b = [[1,2],[3,4]], [[5,6],[7,8]]
                    grid = (a + ([[9,9]] if gap else []) + b if axis == "rows" else
                            [ar + ([9] if gap else []) + br for ar,br in zip(a,b)])
                    chosen = a if direction == "first_to_second" else b
                    expected = (chosen + ([[9,9]] if gap else []) + chosen if axis == "rows" else
                                [row + ([9] if gap else []) + row for row in chosen])
                    original = deepcopy(grid)
                    step = {"op":"equal_panels_copy","axis":axis,"gap":gap,"direction":direction}
                    self.assertEqual(apply(step,grid),expected)
                    self.assertEqual(grid,original)

    def test_mode_uses_entire_grid_including_separator(self):
        step = {"op":"equal_panels_boolean","axis":"rows","gap":1,
                "truth_table":8,"foreground":4,"background":"most_frequent"}
        self.assertEqual(apply(step,[[0,1],[9,9],[9,0]]),[[9,4]])


@unittest.skipUnless(capability()["available"], "Linux resource limits required; no unguarded VM fallback")
class IsolatedControlAcceptanceTests(unittest.TestCase):
    def test_all_controls_in_fresh_resource_guarded_vm_processes(self):
        from tools.arc_consolidated_20261010.arc_object_ir import compile_plan
        from tools.arc_consolidated_20261010.verifier import verify
        for entry in synthetic_controls():
            with self.subTest(control=entry["control_id"]):
                receipt = verify(compile_plan(entry["plan"]), entry["task"])
                self.assertEqual(receipt["status"], entry["expected_status"], receipt)


if __name__ == "__main__":
    unittest.main()
