"""Independent synthetic witnesses for the bounded ARC object DSL.

The expected grids below are literals or elementary constructions fixed before
calling the solver. No candidate, evaluator dataset, model, or network supplies
gold. Tiny grammar subsets are used only to isolate search invariants; each
member is an existing production macro.
"""

from __future__ import annotations

from copy import deepcopy
import unittest
from unittest import mock

from irisx import arc_symbolic_dsl as dsl
from irisx.errors import ValidationError


def macro(extract: str = "grid", select: str = "all",
          transform: str = "identity", render: str = "crop") -> dsl.Macro:
    return dsl.Macro(extract, select, transform, render)


def small_limits(depth: int = 1, **overrides: object) -> dsl.Limits:
    values = {"max_depth": depth, "max_ast_nodes": 4 * depth,
              "max_states": 50_000, "wall_seconds": 10.0}
    values.update(overrides)
    return dsl.Limits(**values)


def search(task: dict, depth: int = 1, **overrides: object) -> dict:
    # A deterministic clock isolates finite-state semantics from host load.
    # Actual hard deadline/process evidence belongs to isolated-runner tests.
    return dsl.search(task, small_limits(depth, **overrides), now=lambda: 0.0)


class IndependentObjectGeometryTests(unittest.TestCase):
    def test_asymmetric_rectangular_d4_outputs_are_literal(self) -> None:
        rows = [[1, 2, 3], [4, 5, 6]]
        expected = {
            "identity": [[1, 2, 3], [4, 5, 6]],
            # Positive quarter turns follow the array/mathematical CCW convention.
            "rot90": [[3, 6], [2, 5], [1, 4]],
            "rot180": [[6, 5, 4], [3, 2, 1]],
            "rot270": [[4, 1], [5, 2], [6, 3]],
            "flip_lr": [[3, 2, 1], [6, 5, 4]],
            "flip_ud": [[4, 5, 6], [1, 2, 3]],
            "transpose": [[1, 4], [2, 5], [3, 6]],
        }
        for transform, gold in expected.items():
            with self.subTest(transform=transform):
                self.assertEqual(dsl.apply_macro(rows, macro(transform=transform)), gold)

    def test_object_rotation_is_local_and_preserves_canvas_anchor(self) -> None:
        rows = [[8, 8, 8, 8, 8, 8, 8],
                [8, 8, 4, 4, 4, 8, 8],
                [8, 8, 4, 8, 8, 8, 8],
                [8, 8, 8, 8, 8, 8, 8],
                [8, 8, 8, 8, 8, 8, 8]]
        expected = [[8, 8, 8, 8, 8, 8, 8],
                    [8, 8, 4, 8, 8, 8, 8],
                    [8, 8, 4, 8, 8, 8, 8],
                    [8, 8, 4, 4, 8, 8, 8],
                    [8, 8, 8, 8, 8, 8, 8]]
        self.assertEqual(dsl.apply_macro(rows, macro("foreground", transform="rot90",
                                                   render="canvas")), expected)
        self.assertEqual(dsl.apply_macro(rows, macro("foreground", transform="rot90")),
                         [[4, 8], [4, 8], [4, 4]])

    def test_scale_replicates_pixels_including_whole_grid_background(self) -> None:
        self.assertEqual(dsl.apply_macro([[2, 0], [0, 2]], macro(transform="scale:2")),
                         [[2, 2, 0, 0], [2, 2, 0, 0],
                          [0, 0, 2, 2], [0, 0, 2, 2]])
        self.assertEqual(dsl.apply_macro([[4, 0]], macro(transform="scale:3")),
                         [[4, 4, 4, 0, 0, 0],
                          [4, 4, 4, 0, 0, 0],
                          [4, 4, 4, 0, 0, 0]])

    def test_largest_uses_pixel_count_instead_of_bounding_rectangle_area(self) -> None:
        rows = [[0] * 10 for _ in range(6)]
        for r, c in ((1, 1), (2, 1), (3, 1), (3, 2), (3, 3)):
            rows[r][c] = 2  # Five pixels, 3x3 bounding rectangle.
        for r in (1, 2):
            for c in (6, 7, 8):
                rows[r][c] = 3  # Six pixels, 2x3 bounding rectangle.
        self.assertEqual(dsl.apply_macro(rows, macro("components4", "largest")),
                         [[3, 3, 3], [3, 3, 3]])
        self.assertEqual(dsl.apply_macro(rows, macro("components4", "smallest")),
                         [[2, 0, 0], [2, 0, 0], [2, 2, 2]])

    def test_size_ties_select_first_row_major_component(self) -> None:
        rows = [[0, 0, 0, 0, 0, 0],
                [0, 7, 7, 0, 0, 0],
                [0, 0, 0, 0, 2, 2],
                [0, 0, 0, 0, 0, 0]]
        for selector in ("largest", "smallest"):
            with self.subTest(selector=selector):
                self.assertEqual(dsl.apply_macro(rows, macro("components4", selector)),
                                 [[7, 7]])

    def test_adjacent_different_colors_are_distinct_components(self) -> None:
        rows = [[0, 0, 0, 0, 0], [0, 2, 3, 0, 0], [0, 0, 0, 0, 0]]
        for kind in ("components4", "components8"):
            with self.subTest(kind=kind):
                background, objects = dsl.extract_objects(rows, kind)
                self.assertEqual(background, 0)
                self.assertEqual([(o.row, o.column, o.height, o.width, o.pixels)
                                  for o in objects],
                                 [(1, 1, 1, 1, ((0, 0, 2),)),
                                  (1, 2, 1, 1, ((0, 0, 3),))])
                self.assertEqual(dsl.apply_macro(rows, macro(kind, "largest")), [[2]])

    def test_diagonal_connectivity_changes_object_selection_and_crop(self) -> None:
        rows = [[0, 0, 0, 0, 0],
                [0, 2, 0, 0, 0],
                [0, 0, 2, 0, 0],
                [0, 0, 0, 2, 0],
                [0, 0, 0, 0, 0]]
        self.assertEqual(len(dsl.extract_objects(rows, "components4")[1]), 3)
        self.assertEqual(len(dsl.extract_objects(rows, "components8")[1]), 1)
        self.assertEqual(dsl.apply_macro(rows, macro("components4", "smallest")), [[2]])
        self.assertEqual(dsl.apply_macro(rows, macro("components8", "smallest")),
                         [[2, 0, 0], [0, 2, 0], [0, 0, 2]])

    def test_color_crop_renders_selected_union_without_neighboring_color(self) -> None:
        rows = [[0, 0, 0, 0, 0, 0],
                [0, 2, 3, 0, 0, 0],
                [0, 0, 0, 0, 2, 0],
                [0, 0, 0, 0, 0, 0]]
        self.assertEqual(dsl.apply_macro(rows, macro("components4", "color:2")),
                         [[2, 0, 0, 0], [0, 0, 0, 2]])
        self.assertEqual(dsl.apply_macro(rows, macro("components4", "color:2",
                                                   render="canvas")),
                         [[0, 0, 0, 0, 0, 0],
                          [0, 2, 0, 0, 0, 0],
                          [0, 0, 0, 0, 2, 0],
                          [0, 0, 0, 0, 0, 0]])

    def test_background_tie_is_color_order_instead_of_first_pixel(self) -> None:
        rows = [[6, 2], [2, 6]]
        background, objects = dsl.extract_objects(rows, "foreground")
        self.assertEqual(background, 2)
        self.assertEqual(objects[0].pixels, ((0, 0, 6), (1, 1, 6)))

    def test_nonzero_background_survives_recolor_and_bbox_fill(self) -> None:
        rows = [[8, 8, 8, 8, 8],
                [8, 2, 8, 2, 8],
                [8, 2, 2, 8, 8],
                [8, 8, 8, 8, 8]]
        self.assertEqual(dsl.apply_macro(rows, macro("foreground", transform="recolor:0")),
                         [[0, 8, 0], [0, 0, 8]])
        self.assertEqual(dsl.apply_macro(rows, macro("foreground", transform="fill_bbox")),
                         [[2, 2, 2], [2, 2, 2]])
        self.assertEqual(dsl.apply_macro(rows, macro(transform="recolor:4")),
                         [[8, 8, 8, 8, 8],
                          [8, 4, 8, 4, 8],
                          [8, 4, 4, 8, 8],
                          [8, 8, 8, 8, 8]])

    def test_monochromatic_fill_rejects_multicolor_foreground(self) -> None:
        rows = [[0, 0, 0], [0, 1, 2], [0, 0, 0]]
        with self.assertRaisesRegex(ValidationError, "one foreground color"):
            dsl.apply_macro(rows, macro("foreground", transform="fill_bbox"))
        self.assertEqual(dsl.apply_macro(rows, macro("components4", transform="fill_bbox")),
                         [[1, 2]])

    def test_empty_selected_canvas_is_background_but_empty_crop_is_invalid(self) -> None:
        rows = [[0, 0, 0], [0, 2, 0], [0, 0, 0]]
        self.assertEqual(dsl.apply_macro(rows, macro("components4", "color:9",
                                                   render="canvas")),
                         [[0, 0, 0], [0, 0, 0], [0, 0, 0]])
        with self.assertRaisesRegex(ValidationError, "empty crop"):
            dsl.apply_macro(rows, macro("components4", "color:9"))
        with self.assertRaisesRegex(ValidationError, "empty crop"):
            dsl.apply_macro([[5, 5], [5, 5]], macro("foreground"))

    def test_transformed_canvas_out_of_bounds_rejects_instead_of_clipping(self) -> None:
        rows = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 2, 2, 2]]
        with self.assertRaisesRegex(ValidationError, "out of bounds"):
            dsl.apply_macro(rows, macro("foreground", transform="rot90", render="canvas"))
        self.assertEqual(dsl.apply_macro(rows, macro("foreground", transform="rot90")),
                         [[2], [2], [2]])
        with self.assertRaisesRegex(ValidationError, "out of bounds"):
            dsl.apply_macro([[1, 2, 3], [4, 5, 6]],
                            macro(transform="transpose", render="canvas"))

    def test_different_color_collision_rejects_and_same_color_collision_merges(self) -> None:
        conflicting = [[0, 0, 0, 0], [0, 2, 3, 0],
                       [0, 0, 0, 0], [0, 0, 0, 0]]
        with self.assertRaisesRegex(ValidationError, "collision"):
            dsl.apply_macro(conflicting, macro("components4", transform="scale:2",
                                                render="canvas"))
        equal_color = [[0] * 7, [0, 2, 0, 2, 0, 0, 0], [0] * 7,
                       [0] * 7, [0] * 7]
        self.assertEqual(dsl.apply_macro(equal_color, macro("components4", transform="scale:3",
                                                           render="canvas")),
                         [[0, 0, 0, 0, 0, 0, 0],
                          [0, 2, 2, 2, 2, 2, 0],
                          [0, 2, 2, 2, 2, 2, 0],
                          [0, 2, 2, 2, 2, 2, 0],
                          [0, 0, 0, 0, 0, 0, 0]])

    def test_crop_extent_limit_applies_to_union_of_individually_valid_objects(self) -> None:
        rows = [[2] + [0] * 28 + [3]]
        with self.assertRaisesRegex(ValidationError, "rendered dimensions"):
            dsl.apply_macro(rows, macro("components4", transform="scale:2"))
        with self.assertRaisesRegex(ValidationError, "scaled object"):
            dsl.apply_macro([[2] * 16], macro(transform="scale:2"))

    def test_composed_object_operations_have_independent_literal_target(self) -> None:
        rows = [[0, 0, 0, 0, 0, 0],
                [0, 2, 0, 0, 7, 0],
                [0, 2, 2, 0, 0, 0],
                [0, 0, 0, 0, 0, 0]]
        program = [macro("components4", "largest").value(),
                   macro(transform="flip_lr").value(),
                   macro(transform="scale:2").value()]
        self.assertEqual(dsl.execute_program(rows, program),
                         [[0, 0, 2, 2], [0, 0, 2, 2],
                          [2, 2, 2, 2], [2, 2, 2, 2]])

    def test_evaluation_does_not_mutate_caller_grid_or_program(self) -> None:
        rows = [[0, 0, 0], [0, 3, 3], [0, 3, 0]]
        program = [macro("foreground", transform="flip_ud").value()]
        original = deepcopy((rows, program))
        dsl.execute_program(rows, program)
        self.assertEqual((rows, program), original)

    def test_background_is_recomputed_after_crop_instead_of_inherited(self) -> None:
        rows = [[0, 0, 0, 0], [0, 2, 2, 0], [0, 2, 0, 0], [0, 0, 0, 0]]
        program = [macro("components4", "largest").value(),
                   macro(transform="recolor:4").value()]
        # The crop is [[2, 2], [2, 0]]. Its modal color is now 2, so the
        # second macro preserves 2 and recolors the former background hole.
        self.assertEqual(dsl.execute_program(rows, program), [[2, 2], [2, 4]])


class IndependentSearchWitnessTests(unittest.TestCase):
    def test_single_step_search_fits_two_demos_and_retains_literal_heldout_rotation(self) -> None:
        task = {"train": [
            {"input": [[1, 2, 3], [4, 5, 6]],
             "output": [[3, 6], [2, 5], [1, 4]]},
            {"input": [[0, 7], [8, 0], [9, 0]],
             "output": [[7, 0, 0], [0, 8, 9]]},
        ], "test": [{"input": [[2, 0, 3, 4], [5, 6, 0, 7]]}]}
        result = search(task)
        target = [[4, 7], [3, 0], [0, 6], [2, 5]]
        self.assertEqual(result["stop_reason"], "exhausted")
        self.assertTrue(any(candidate["outputs"] == [target]
                            for candidate in result["candidates"]))
        for candidate in result["candidates"]:
            for pair in task["train"]:
                self.assertEqual(dsl.execute_program(pair["input"], candidate["program"]),
                                 pair["output"])
        self.assertFalse(result["correctness_scored"])
        self.assertIsNone(result["native_verification"])

    def test_crop_largest_generalizes_to_unseen_position_color_and_distractor(self) -> None:
        task = {"train": [
            {"input": [[0, 0, 0, 0], [0, 2, 2, 0], [0, 2, 0, 7], [0, 0, 0, 0]],
             "output": [[2, 2], [2, 0]]},
            {"input": [[0, 6, 0, 0, 0], [0, 0, 0, 4, 4],
                       [0, 0, 0, 4, 0], [0, 0, 0, 0, 0]],
             "output": [[4, 4], [4, 0]]},
        ], "test": [{"input": [[0, 0, 0, 0, 0, 0],
                               [0, 8, 8, 0, 0, 0],
                               [0, 8, 0, 0, 9, 0],
                               [0, 8, 8, 0, 0, 0],
                               [0, 0, 0, 0, 0, 0]]}]}
        result = search(task)
        target = [[8, 8], [8, 0], [8, 8]]
        self.assertTrue(any(candidate["outputs"] == [target]
                            for candidate in result["candidates"]))

    def test_contradictory_same_input_demo_outputs_cannot_emit_partial_fit(self) -> None:
        task = {"train": [{"input": [[0, 1]], "output": [[0, 1]]},
                          {"input": [[0, 1]], "output": [[1, 0]]}],
                "test": [{"input": [[0, 2]]}]}
        result = search(task)
        self.assertEqual(result["stop_reason"], "exhausted")
        self.assertEqual(result["candidates"], [])

    def test_alternative_demo_fitting_programs_disagree_on_asymmetric_test(self) -> None:
        task = {"train": [{"input": [[0, 3, 0], [3, 3, 3]],
                           "output": [[0, 3, 0], [3, 3, 3]]}],
                "test": [{"input": [[0, 2, 0], [0, 2, 2]]}]}
        identity = macro(render="canvas")
        reflection = macro(transform="flip_lr", render="canvas")
        with mock.patch.object(dsl, "GRAMMAR", (identity, reflection)):
            result = search(task)
        self.assertEqual([candidate["outputs"] for candidate in result["candidates"]],
                         [[[[0, 2, 0], [2, 2, 0]]],
                          [[[0, 2, 0], [0, 2, 2]]]])
        self.assertFalse(result["correctness_scored"])
        self.assertIsNone(result["loo_support"])

    def test_two_step_dedup_must_keep_test_distinction_even_when_demos_match_root(self) -> None:
        # Reflection leaves the demonstration unchanged. On tests it changes
        # which tied-size colored component occurs first. Crop/selection does
        # not commute with reflection, so considering it directly cannot rescue
        # a demo-only semantic-state cache.
        task = {"train": [{"input": [[0, 0, 0, 0, 0],
                                      [0, 1, 0, 1, 0],
                                      [0, 0, 0, 0, 0]], "output": [[1]]}],
                "test": [{"input": [[0, 0, 0, 0, 0],
                                     [0, 2, 0, 3, 0], [0, 0, 0, 0, 0]]},
                         {"input": [[0, 0, 0, 0, 0],
                                    [0, 4, 0, 5, 0], [0, 0, 0, 0, 0]]}]}
        reflection = macro(transform="flip_lr", render="canvas")
        selection = macro("components4", "smallest")
        with mock.patch.object(dsl, "GRAMMAR", (reflection, selection)):
            result = search(task, depth=2)
        self.assertEqual(result["stop_reason"], "exhausted")
        self.assertEqual([candidate["outputs"] for candidate in result["candidates"]],
                         [[[[2]], [[4]]], [[[3]], [[5]]]])
        self.assertEqual(result["candidates"][1]["program"],
                         [reflection.value(), selection.value()])

    def test_signature_is_ordered_and_includes_every_test(self) -> None:
        self.assertNotEqual(dsl.semantic_signature([[[1]], [[2]], [[3]]]),
                            dsl.semantic_signature([[[1]], [[2]], [[4]]]))
        self.assertNotEqual(dsl.semantic_signature([[[1]], [[2]], [[3]]]),
                            dsl.semantic_signature([[[1]], [[3]], [[2]]]))
        self.assertNotEqual(dsl.semantic_signature([[[1]], [[2]]]),
                            dsl.semantic_signature([[[1]], [[2]], [[2]]]))

    def test_perfect_leave_one_demo_out_support_is_still_ambiguous_on_test(self) -> None:
        task = {"train": [{"input": [[0, color, 0]], "output": [[0, color, 0]]}
                          for color in (2, 3, 4)],
                "test": [{"input": [[0, 5, 5]]}]}
        identity = macro(render="canvas")
        reflection = macro(transform="flip_lr", render="canvas")
        with mock.patch.object(dsl, "GRAMMAR", (identity, reflection)):
            result = search(task, loo=True)
        self.assertEqual(result["loo_support"],
                         {"kind": "leave-one-demonstration-out-top-one", "folds": 3,
                          "supported": 3, "shared_task_budget": True})
        self.assertEqual([candidate["outputs"] for candidate in result["candidates"]],
                         [[[[5, 5, 0]]], [[[0, 5, 5]]]])
        self.assertFalse(result["correctness_scored"])
        self.assertIsNone(result["native_verification"])

    def test_leave_one_demo_out_builds_fresh_folds_without_held_demo(self) -> None:
        task = {"train": [{"input": [[0, color, 0]], "output": [[0, color, 0]]}
                          for color in (2, 3, 4)],
                "test": [{"input": [[0, 5, 5]]}]}
        original_search = dsl._search
        calls = []

        def observe(fold: dict, budget: dsl.Budget) -> dict:
            calls.append(deepcopy(fold))
            return original_search(fold, budget)

        with mock.patch.object(dsl, "GRAMMAR", (macro(render="canvas"),)), \
                mock.patch.object(dsl, "_search", side_effect=observe):
            result = search(task, loo=True)
        self.assertEqual(result["loo_support"]["folds"], 3)
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0], task)
        for index, fold in enumerate(calls[1:]):
            held = task["train"][index]
            self.assertEqual(fold["train"], [pair for i, pair in enumerate(task["train"])
                                            if i != index])
            self.assertEqual(fold["test"], [{"input": held["input"]}] + task["test"])
            self.assertNotIn(held, fold["train"])

    def test_incomplete_leave_one_demo_out_does_not_report_partial_support(self) -> None:
        task = {"train": [{"input": [[0, color, 0]], "output": [[0, color, 0]]}
                          for color in (2, 3, 4)],
                "test": [{"input": [[0, 5, 5]]}]}
        with mock.patch.object(dsl, "GRAMMAR", (macro(render="canvas"),)):
            result = search(task, loo=True, max_states=2)
        self.assertEqual(result["stop_reason"], "exhausted")
        self.assertEqual(result["states"], 2)
        self.assertIsNone(result["loo_support"])

    def test_candidate_outputs_preserve_order_of_multiple_test_inputs(self) -> None:
        task = {"train": [{"input": [[0, 2, 3]], "output": [[3, 2, 0]]}],
                "test": [{"input": [[0, 4, 5, 0]]}, {"input": [[7, 0, 0, 8]]}]}
        reflection = macro(transform="flip_lr", render="canvas")
        with mock.patch.object(dsl, "GRAMMAR", (reflection,)):
            result = search(task)
        self.assertEqual(result["candidates"][0]["outputs"],
                         [[[0, 5, 4, 0]], [[8, 0, 0, 7]]])

    def test_search_does_not_mutate_tasks_or_add_test_answer_fields(self) -> None:
        task = {"train": [{"input": [[0, 2]], "output": [[2, 0]]}],
                "test": [{"input": [[0, 3]]}]}
        original = deepcopy(task)
        search(task)
        self.assertEqual(task, original)
        self.assertEqual(set(task["test"][0]), {"input"})


class IndependentBoundaryTests(unittest.TestCase):
    def test_all_unknown_macro_fields_and_unbounded_programs_fail_closed(self) -> None:
        good = macro().value()
        bad_programs = [[], [good] * 4, (good,), [{**good, "code": "print('unsafe')"}],
                        [{k: v for k, v in good.items() if k != "select"}],
                        [{**good, "extract": "eval"}],
                        [{**good, "select": "lambda:all"}],
                        [{**good, "transform": "scale:4"}],
                        [{**good, "render": "clip"}],
                        ["identity"], [lambda rows: rows]]
        for program in bad_programs:
            with self.subTest(program=repr(program)):
                with self.assertRaises(ValidationError):
                    dsl.execute_program([[0, 1]], program)

    def test_whole_grid_and_foreground_extractors_cannot_gain_component_selectors(self) -> None:
        for kind in ("grid", "foreground"):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(ValidationError, "outside frozen grammar"):
                    dsl.apply_macro([[0, 2], [0, 0]], macro(kind, "largest"))

    def test_grids_reject_boolean_float_ragged_empty_and_oversize_values(self) -> None:
        invalid = [[], [[]], [[True]], [[1.0]], [[-1]], [[10]],
                   [[1], [1, 2]], [[0] * 31], [[0]] * 31, ((0,),)]
        for rows in invalid:
            with self.subTest(rows=repr(rows)):
                with self.assertRaises(ValidationError):
                    dsl.grid(rows)

    def test_task_rejects_test_truth_extra_metadata_and_missing_demo_output(self) -> None:
        original = {"train": [{"input": [[0, 2]], "output": [[2, 0]]}],
                    "test": [{"input": [[0, 3]]}]}
        mutations = []
        for field in ("output", "answer", "truth_digest", "task_id", "expected_shape"):
            task = deepcopy(original)
            task["test"][0][field] = [[9]]
            mutations.append(task)
        task = deepcopy(original)
        task["answers"] = [[[9]]]
        mutations.append(task)
        task = deepcopy(original)
        del task["train"][0]["output"]
        mutations.append(task)
        for task in mutations:
            with self.subTest(task=task):
                with self.assertRaises(ValidationError):
                    search(task)

    def test_limits_reject_bool_nonfinite_and_inconsistent_ast_budgets(self) -> None:
        bad = [dsl.Limits(wall_seconds=True), dsl.Limits(wall_seconds=float("nan")),
               dsl.Limits(wall_seconds=float("inf")), dsl.Limits(wall_seconds=10.1),
               dsl.Limits(max_states=True), dsl.Limits(max_depth=4),
               dsl.Limits(max_ast_nodes=11), dsl.Limits(max_candidates=65),
               dsl.Limits(cache_bytes=0), dsl.Limits(loo=1)]
        for limits in bad:
            with self.subTest(limits=limits):
                with self.assertRaises(ValidationError):
                    limits.validate()

    def test_state_and_cache_caps_return_reproducible_unscored_prefixes(self) -> None:
        task = {"train": [{"input": [[0, 2]], "output": [[0, 2]]}],
                "test": [{"input": [[0, 3]]}]}
        limited = search(task, max_states=1)
        repeated = search(task, max_states=1)
        self.assertEqual(limited["stop_reason"], "state_limit")
        self.assertEqual(limited["states"], 1)
        self.assertEqual(limited["candidates"], repeated["candidates"])
        self.assertFalse(limited["correctness_scored"])
        cached = search(task, cache_bytes=1)
        self.assertEqual(cached["stop_reason"], "cache_limit")
        self.assertEqual(cached["candidates"], [])
        self.assertEqual(cached["states"], 0)
        self.assertLessEqual(cached["cache_bytes"], 1)

    def test_wall_cutoff_discards_already_discovered_candidate_pool(self) -> None:
        task = {"train": [{"input": [[0, 2]], "output": [[0, 2]]}],
                "test": [{"input": [[0, 3]]}]}
        times = iter((0.0, 0.0, 10.0))
        with mock.patch.object(dsl, "GRAMMAR", (macro(render="canvas"),)):
            result = dsl.search(task, small_limits(), now=lambda: next(times))
        self.assertEqual(result["states"], 1)
        self.assertEqual(result["stop_reason"], "wall_limit")
        self.assertEqual(result["candidates"], [])
        self.assertIsNone(result["loo_support"])


if __name__ == "__main__":
    unittest.main()
