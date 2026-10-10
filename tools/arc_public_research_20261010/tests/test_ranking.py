"""Synthetic, demos-only ranking acceptance; zero verifier/VM dispatches.

All grids below are constructed in this file. No ARC tasks, query inputs,
answers, coverage, witnesses, or historical outcomes are loaded. Full-inventory
checks compile trusted templates only; compilation is not plan execution.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.arc_public_research_20261010 import ranking as r
from tools.arc_consolidated_20261010.arc_object_ir import base_inventory, compile_plan, smoke_inventory
from tools.arc_consolidated_20261010.stages import freeze_base_inventory


def task(tid="synthetic-only"):
    return {"task_id": tid, "demos": [{"input": [[0, 2, 2], [3, 0, 2]],
                                      "output": [[0, 3], [2, 0], [2, 2]]}]}


def plan(*steps):
    return {"steps": list(steps)}


def effect(*steps, dims=(2, 3), colors=(0, 2, 3)):
    return r.abstract_plan(plan(*steps), {"dimensions": list(dims), "palette": list(colors)})


def render(action="crop_mask", background=0, **extra):
    return {"op": "object_select_render", "partition": "same_color_cc4",
            "background": background, "selector": {"kind": "minarea"},
            "action": {"kind": action, **extra}}


def anchor(background=0):
    return {"op": "anchored_recolor", "partition": "foreground_cc4", "background": background,
            "focus_selector": {"kind": "all"}, "anchor_selector": {"kind": "maxarea"}, "relation": "right"}


def panel(axis="cols", gap=0, table=6, bg=0, fg=9):
    return {"op": "equal_panels_boolean", "axis": axis, "gap": gap,
            "truth_table": table, "background": bg, "foreground": fg}


class AbstractionTests(unittest.TestCase):
    def test_identity_and_geometry_exact(self):
        for op in ("identity", "flip_horizontal", "flip_vertical"):
            state = effect({"op": op})
            self.assertEqual(state.dimensions, {(2, 3)})
            self.assertEqual(state.palette_upper, {0, 2, 3})
            self.assertTrue(state.palette_exact)
        for op in ({"op": "transpose"}, {"op": "rotate", "turns": 1}, {"op": "rotate", "turns": 3}):
            self.assertEqual(effect(op).dimensions, {(3, 2)})
        self.assertEqual(effect({"op": "rotate", "turns": 2}).dimensions, {(2, 3)})

    def test_scale_tile_recolor_composition(self):
        state = effect({"op": "scale", "factor": 2}, {"op": "tile", "rows": 1, "columns": 3},
                       {"op": "transpose"})
        self.assertEqual(state.dimensions, {(18, 4)})
        self.assertTrue(state.palette_exact)
        state = effect({"op": "recolor", "source": 2, "target": 7})
        self.assertEqual(state.palette_upper, {0, 3, 7})
        self.assertTrue(state.palette_exact)
        self.assertEqual(effect({"op": "recolor", "source": 8, "target": 7}).palette_upper, {0, 2, 3})

    def test_palette_exact_mismatch_is_not_containment_credit(self):
        state = effect({"op": "identity"})
        self.assertEqual(r.compatibility(state, {"dimensions": [2, 3], "palette": [0, 2, 3]}),
                         {"dimension_credit": 2, "palette_credit": 2})
        self.assertEqual(r.compatibility(state, {"dimensions": [2, 3], "palette": [0]}),
                         {"dimension_credit": 2, "palette_credit": 0})

    def test_crops_include_all_rectangles_and_empty_copy(self):
        for step in ({"op": "crop_nonbackground", "background": 0},
                     {"op": "largest_component_crop", "background": 0, "connectivity": 8},
                     render("crop_bbox"), render("crop_mask")):
            state = effect(step)
            self.assertEqual(state.dimensions, {(h, w) for h in (1, 2) for w in (1, 2, 3)})
            self.assertIn((2, 3), state.dimensions)
            self.assertFalse(state.palette_exact)
            self.assertEqual(r.compatibility(state, {"dimensions": [1, 2], "palette": [2]}),
                             {"dimension_credit": 1, "palette_credit": 1})

    def test_crop_then_geometry_is_in_source_order(self):
        state = effect(render(), {"op": "transpose"}, {"op": "rotate", "turns": 2})
        self.assertEqual(state.dimensions, {(h, w) for h in (1, 2, 3) for w in (1, 2)})
        self.assertNotIn((2, 3), state.dimensions)

    def test_oversize_intermediates_are_absorbing(self):
        for later in (render(), {"op": "crop_nonbackground", "background": 0}, {"op": "unsupported"}):
            state = effect({"op": "scale", "factor": 2}, later, dims=(1, 16))
            self.assertFalse(state.dimensions)
            self.assertFalse(state.palette_upper)
            self.assertFalse(state.palette_exact)
            self.assertEqual(r.compatibility(state, {"dimensions": [1, 1], "palette": [0]}),
                             {"dimension_credit": 0, "palette_credit": 0})

    def test_ambiguous_crop_scale_drops_only_invalid_paths(self):
        state = effect(render(), {"op": "scale", "factor": 2}, dims=(2, 30))
        self.assertEqual(state.dimensions, {(h, w) for h in (2, 4) for w in range(2, 31, 2)})
        self.assertNotIn((2, 32), state.dimensions)

    def test_masks_add_only_permitted_palette_colors(self):
        for action in ("keep_mask", "erase_mask", "crop_mask"):
            state = effect(render(action, background=8))
            self.assertEqual(state.palette_upper, {0, 2, 3, 8})
            self.assertFalse(state.palette_exact)
        self.assertEqual(effect(render("crop_bbox", background=8)).palette_upper, {0, 2, 3})
        self.assertEqual(effect(render("paint_mask", background=8, color=9)).palette_upper, {0, 2, 3, 9})

    def test_unknown_frequency_nonzero_and_ties_remain_conservative(self):
        for step in (render("erase_mask", "most_frequent"), anchor("most_frequent")):
            state = effect(step, colors=(2, 4))
            self.assertEqual(state.palette_upper, {2, 4})
            self.assertFalse(state.palette_exact)
        state = effect(panel(bg="most_frequent", table=0), dims=(1, 4), colors=(2, 4))
        self.assertEqual(state.palette_upper, {2, 4})
        self.assertFalse(state.palette_exact)

    def test_tied_empty_anchor_and_matching_selectors_copy_path_included(self):
        # No object selector/anchor solver runs: all such branches stay included.
        for colors in ((0,), (1, 2), (0, 1, 2)):
            step = anchor()
            step["focus_selector"] = {"kind": "maxarea"}
            state = effect(step, colors=colors)
            self.assertEqual(state.dimensions, {(2, 3)})
            self.assertEqual(state.palette_upper, set(colors))
        self.assertTrue(effect(anchor(), colors=(0,)).palette_exact)

    def test_all_background_empty_crop_and_keep_singleton(self):
        for action in ("crop_bbox", "crop_mask", "keep_mask", "erase_mask"):
            state = effect(render(action), colors=(0,))
            self.assertIn((2, 3), state.dimensions)
            self.assertEqual(state.palette_upper, {0})
            self.assertTrue(state.palette_exact)

    def test_valid_invalid_panels_and_gap(self):
        cases = [((2, 4), "cols", 0, (2, 2)), ((5, 3), "rows", 1, (2, 3)),
                 ((2, 3), "cols", 0, (2, 3)), ((2, 1), "cols", 1, (2, 1)),
                 ((1, 3), "rows", 0, (1, 3))]
        for dims, axis, gap, expected in cases:
            state = effect(panel(axis, gap), dims=dims)
            self.assertEqual(state.dimensions, {expected})
            if expected == dims:
                self.assertEqual(state.palette_upper, {0, 2, 3})
                self.assertTrue(state.palette_exact)
            else:
                self.assertEqual(state.palette_upper, {0, 9})
                self.assertFalse(state.palette_exact)

    def test_panel_constant_tables_are_exact_only_on_valid_branch(self):
        for table, colors in ((0, {8}), (15, {9})):
            state = effect(panel(table=table, bg=8), dims=(2, 4))
            self.assertEqual(state.palette_upper, colors)
            self.assertTrue(state.palette_exact)
        state = effect(panel(table=6, bg=9), dims=(2, 4))
        self.assertEqual(state.palette_upper, {9})
        self.assertTrue(state.palette_exact)
        state = effect(panel(table=15), dims=(2, 3))
        self.assertEqual(state.palette_upper, {0, 2, 3})

    def test_panel_after_ambiguous_crop_keeps_both_split_branches(self):
        state = effect(render("crop_bbox"), panel(table=15), dims=(1, 4), colors=(2,))
        self.assertEqual(state.dimensions, {(1, 1), (1, 2), (1, 3)})
        self.assertEqual(state.palette_upper, {2, 9})
        self.assertFalse(state.palette_exact)

    def test_panel_copy_preserves_shape_but_not_exact_palette(self):
        step = {"op": "equal_panels_copy", "axis": "cols", "gap": 0, "direction": "first_to_second"}
        state = effect(step, dims=(1, 4), colors=(1, 2))
        self.assertEqual(state.dimensions, {(1, 4)})
        self.assertEqual(state.palette_upper, {1, 2})
        self.assertFalse(state.palette_exact)
        self.assertTrue(effect(step, dims=(1, 3)).palette_exact)

    def test_unknown_and_malformed_are_top_not_impossible(self):
        for step in ({"op": "future_operator"}, {"op": "scale", "factor": True},
                     {"op": "identity", "surprise": 1}, {"op": "object_select_render"},
                     {"op": "rotate", "turns": 42}, {"op": "equal_panels_boolean"}):
            state = effect(step)
            self.assertEqual(state.dimensions, r.ALL_DIMENSIONS)
            self.assertEqual(state.palette_upper, r.ALL_COLORS)
            self.assertTrue(state.unknown)
            self.assertFalse(state.palette_exact)
            self.assertEqual(r.compatibility(state, {"dimensions": [30, 30], "palette": [7, 9]}),
                             {"dimension_credit": 1, "palette_credit": 1})
        state = effect({"op": "future_operator"}, panel(table=15))
        self.assertFalse(state.palette_exact)
        self.assertTrue(state.unknown)

    def test_weights_positive_even_all_feature_contradictions(self):
        features = [{"input": {"dimensions": [16, 16], "palette": [1]},
                     "output": {"dimensions": [1, 1], "palette": [9]}}]
        self.assertEqual(r.candidate_features(plan({"op": "scale", "factor": 2}), features)["weight"], 1)
        features[0]["output"] = features[0]["input"]
        self.assertEqual(r.candidate_features(plan({"op": "identity"}), features)["weight"], 13)
        self.assertEqual(r.candidate_features(plan({"op": "identity"}), features * 2)["weight"], 25)

    def test_color_permutation_preserves_compatible_credits(self):
        mapping = {i: 9 - i for i in range(10)}
        inp = {"dimensions": [2, 3], "palette": [0, 2, 3]}
        out = {"dimensions": [2, 3], "palette": [0, 3, 7]}
        before = r.compatibility(r.abstract_plan(plan({"op": "recolor", "source": 2, "target": 7}), inp), out)
        after = r.compatibility(r.abstract_plan(plan({"op": "recolor", "source": mapping[2], "target": mapping[7]}),
            {**inp, "palette": [mapping[x] for x in inp["palette"]]}),
            {**out, "palette": [mapping[x] for x in out["palette"]]})
        self.assertEqual(before, after)


class SamplingTests(unittest.TestCase):
    def rows(self):
        return [{"candidate_id": "abcde"[i], "family": r.FAMILIES[i % 3], "weight": i + 1} for i in range(5)]

    def test_frozen_sha256_blocks(self):
        stream = r.CounterStream("0" * 64, 0, "uniform")
        self.assertEqual([stream.block().hex() for _ in range(3)], [
            "5ca661609737f295eb0f861243d2f54da3c6e7b98a8fbc51736a4f285c70568b",
            "bdf5a891681dcfa8f91654c6f56184090300fa4280e08374d4c73460d9fe56da",
            "6f470527bb74d519994b10d073dd03b5d9a97f93aae607bd5b8fbeb8772f581a"])
        # Independent specification computation (no CounterStream helper calls).
        domain = b"irisx/public-ranker/sha256-counter-u256-rejection-v1"
        payload = b'{"demos_sha256":"' + b"0" * 64 + b'","method":"uniform","seed":0}'
        root = hashlib.sha256(domain + b"\0" + payload).digest()
        self.assertEqual(hashlib.sha256(domain + b"\0" + root + b"\0" * 16).hexdigest(),
                         "5ca661609737f295eb0f861243d2f54da3c6e7b98a8fbc51736a4f285c70568b")

    def test_frozen_integer_choices_and_rejection(self):
        stream = r.CounterStream("0" * 64, 0, "uniform")
        self.assertEqual([stream.randbelow(k) for k in [1, 2, 3, 7, 10, 5965, 2**255 + 1]],
                         [0, 0, 1, 2, 6, 5750, 26401103920335490792299556141342970611029032491476358805959553063222456443381])
        stream = r.CounterStream("0" * 64, 0, "uniform")
        with patch.object(stream, "block", side_effect=[b"\xff" * 32, (17).to_bytes(32, "big")]) as block:
            self.assertEqual(stream.randbelow(10), 7)
            self.assertEqual(block.call_count, 2)
        for bound in (0, -1, True, 2**256 + 1):
            with self.assertRaises(r.RankingError):
                stream.randbelow(bound)

    def test_frozen_order_vectors(self):
        for method, expected, count in (("uniform", ["a", "d", "c", "b", "e"], 5),
                ("shape_palette_v1", ["e", "d", "b", "a", "c"], 15)):
            stream = r.CounterStream("0" * 64, 0, method)
            self.assertEqual(r.draw_order(self.rows(), stream, method), expected)
            self.assertEqual(stream.counter, count)
            self.assertEqual(r.draw_order(self.rows()[::-1], r.CounterStream("0" * 64, 0, method), method), expected)

    def test_fenwick_matches_independent_integer_list_sampler(self):
        for seed in range(12):
            for method in ("uniform", "shape_palette_v1"):
                pending = self.rows()
                stream = r.CounterStream("0" * 64, seed, method)
                expected = []
                while pending:
                    if method == "uniform" or stream.randbelow(4) == 0:
                        row = pending[stream.randbelow(len(pending))]
                    else:
                        families = [f for f in r.FAMILIES if any(x["family"] == f for x in pending)]
                        family = families[stream.randbelow(len(families))]
                        group = [x for x in pending if x["family"] == family]
                        ticket = stream.randbelow(sum(x["weight"] for x in group))
                        for row in group:
                            if ticket < row["weight"]:
                                break
                            ticket -= row["weight"]
                    pending.remove(row)
                    expected.append(row["candidate_id"])
                self.assertEqual(r.draw_order(self.rows(), r.CounterStream("0" * 64, seed, method), method), expected)

    def test_every_candidate_has_uniform_branch_support(self):
        class Scripted:
            def __init__(self, target):
                self.calls, self.target = 0, target
            def randbelow(self, bound):
                self.calls += 1
                return self.target if self.calls == 2 else 0
        rows = self.rows()
        rows[0]["weight"] = 10**9
        for i, row in enumerate(rows):
            ordering = r.draw_order(rows, Scripted(i), "shape_palette_v1")
            self.assertEqual(ordering[0], row["candidate_id"])
            self.assertEqual(set(ordering), set("abcde"))

    def test_sparse_imbalanced_families_and_duplicate_behavior_retained(self):
        rows = [{"candidate_id": str(i).zfill(3), "family": r.FAMILIES[0], "weight": 1} for i in range(100)]
        rows[-1]["family"], rows[-1]["weight"] = r.FAMILIES[-1], 10**6
        ordering = r.draw_order(rows, r.CounterStream("0" * 64, 7, "shape_palette_v1"), "shape_palette_v1")
        self.assertEqual(len(ordering), 100)
        self.assertEqual(len(set(ordering[:64])), 64)
        self.assertEqual(set(ordering), {row["candidate_id"] for row in rows})
        for bad in ([], rows + rows[:1], [{**rows[0], "weight": 0}], [{**rows[0], "family": "other"}]):
            with self.assertRaises(r.RankingError):
                r.draw_order(bad, r.CounterStream("0" * 64, 0, "uniform"), "uniform")


class FixedInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Source-template compilation only: zero VM, verifier, or model calls.
        cls.pool = freeze_base_inventory(base_inventory(), compile_plan)["candidates"]
        cls.sealed = {method: r.rank_candidates(task(), cls.pool, method=method)
                      for method in ("uniform", "shape_palette_v1")}

    def test_exact_inventory_and_eight_existing_families(self):
        self.assertEqual(len(self.pool), 5965)
        self.assertEqual(r.digest([x["plan"] for x in self.pool]), r.INVENTORY_SHA256)
        counts = {family: 0 for family in r.FAMILIES}
        for p in smoke_inventory():
            counts[r.candidate_family(p)] += 1
        self.assertEqual(list(counts.values()), [18, 17, 17, 17, 17, 17, 17, 8])
        record = self.sealed["shape_palette_v1"]
        self.assertEqual(sum(x["count"] for x in record["family_mass"]), 5965)
        self.assertEqual(sum(x["weight"] for x in record["family_mass"]),
                         sum(x["weight"] for x in record["candidate_features"]))

    def test_frozen_full_inventory_order_vectors(self):
        vectors = {
            "uniform": ("afeba35878bc9c9a27c296f9329c3aacaff491894563a93cb0c38b24b2193382",
                        "555a2161acc92fd4550b174e271c26f36b7f3f4857d0d342c3dea718a170f971", 5965),
            "shape_palette_v1": ("43bf8814d7b8cf72628f0778fbb0545735d4810878d73f15311aaf161d6948fe",
                                 "c8bb150c5d12e386a4f8db2703065334104983cfd4aaa9dab2561cc034270ceb", 16378),
        }
        for method, (ordering, window, blocks) in vectors.items():
            record = self.sealed[method]
            self.assertEqual(r.digest(record["full_order"]), ordering)
            self.assertEqual(r.digest(record["selected_candidate_ids"]), window)
            self.assertEqual(record["random_blocks_consumed"], blocks)
        self.assertEqual(self.sealed["uniform"]["config_sha256"],
                         "a2ec2f0feb88f9fc74fa44e741dd864f7bb2401c979cffef7784400198d893d6")

    def test_both_arms_full_support_and_64_distinct_slots(self):
        for record in self.sealed.values():
            self.assertEqual(len(record["full_order"]), 5965)
            self.assertEqual(len(set(record["full_order"])), 5965)
            self.assertEqual(record["selected_candidate_ids"], record["full_order"][:64])
            self.assertEqual(len(set(record["selected_candidate_ids"])), 64)
            self.assertEqual(record["excluded_candidate_ids"], [])
            self.assertEqual(record["physical_checks"], 0)
            self.assertTrue(all(x["weight"] >= 1 for x in record["candidate_features"]))
            self.assertEqual(record["ordering_sha256"], r.digest({k: v for k, v in record.items()
                if k not in ("ordering_sha256", "task_id")}))
        self.assertEqual(self.sealed["uniform"]["candidate_features"], self.sealed["shape_palette_v1"]["candidate_features"])
        self.assertNotEqual(self.sealed["uniform"]["full_order"], self.sealed["shape_palette_v1"]["full_order"])

    def test_identifier_key_and_candidate_iteration_invariance(self):
        renamed = {"demos": copy.deepcopy(task()["demos"]), "task_id": "a-completely-unrelated-id"}
        renamed["demos"][0] = dict(reversed(list(renamed["demos"][0].items())))
        for method in self.sealed:
            result = r.rank_candidates(renamed, self.pool[::-1], method=method)
            expected = {**self.sealed[method], "task_id": renamed["task_id"]}
            self.assertEqual(result, expected)

    def test_rich_task_demo_and_candidate_fields_rejected(self):
        for key in ("test", "query", "gold", "coverage", "witness", "status", "score", "feedback", "model_proposals"):
            bad = task()
            bad[key] = []
            with self.assertRaises(r.RankingError):
                r.rank_candidates(bad, self.pool)
            bad = task()
            bad["demos"][0][key] = []
            with self.assertRaises(r.RankingError):
                r.rank_candidates(bad, self.pool)
            badpool = [{**self.pool[0], key: []}, *self.pool[1:]]
            with self.assertRaises(r.RankingError):
                r.rank_candidates(task(), badpool)

    def test_no_file_process_compiler_or_verifier_capability(self):
        source = Path(r.__file__).read_text()
        imported = {n.module for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom)}
        imported |= {a.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Import) for a in n.names}
        self.assertEqual(imported, {"__future__", "dataclasses", "hashlib", "json"})
        with patch("builtins.open", side_effect=AssertionError("forbidden ranker I/O")):
            self.assertEqual(r.rank_candidates(task(), self.pool)["full_order"], self.sealed["uniform"]["full_order"])

    def test_ordered_demo_policy_seed_and_weights(self):
        two = task()
        two["demos"].append({"input": [[4]], "output": [[4]]})
        forward = r.rank_candidates(two, self.pool)
        two["demos"].reverse()
        backward = r.rank_candidates(two, self.pool)
        self.assertNotEqual(forward["demos_sha256"], backward["demos_sha256"])
        self.assertNotEqual(forward["full_order"], backward["full_order"])
        self.assertEqual([x["weight"] for x in forward["candidate_features"]],
                         [x["weight"] for x in backward["candidate_features"]])
        seeded = r.rank_candidates(task(), self.pool, seed=1)
        self.assertNotEqual(seeded["full_order"], self.sealed["uniform"]["full_order"])
        self.assertEqual(seeded["candidate_features"], self.sealed["uniform"]["candidate_features"])

    def test_data_and_config_source_fingerprints(self):
        record = self.sealed["uniform"]
        self.assertEqual(record["demos_sha256"], r.digest(task()["demos"]))
        self.assertEqual(record["features_sha256"], r.digest(record["demo_features"]))
        self.assertEqual(record["config_sha256"], r.digest(r.policy_config()))
        changed_source = [{**self.pool[0], "source_sha256": "0" * 64}, *self.pool[1:]]
        other = r.rank_candidates(task(), changed_source)
        self.assertNotEqual(other["source_sha256"], record["source_sha256"])
        self.assertNotEqual(other["ordering_sha256"], record["ordering_sha256"])
        self.assertEqual(other["full_order"], record["full_order"])
        config = r.policy_config()
        config["weight"]["base"] = 0
        self.assertEqual(r.policy_config()["weight"]["base"], 1)

    def test_inventory_bindings_fail_closed(self):
        for candidate in ({**self.pool[0], "candidate_id": "0" * 64},
                          {**self.pool[0], "origin": "proposal"},
                          {**self.pool[0], "source_sha256": "invalid"}, self.pool[1]):
            with self.assertRaises(r.RankingError):
                r.rank_candidates(task(), [candidate, *self.pool[1:]])
        changed = copy.deepcopy(self.pool[0])
        changed["plan"] = plan({"op": "future_op"})
        changed["candidate_id"] = r.digest(changed["plan"])
        with self.assertRaises(r.RankingError):
            r.rank_candidates(task(), [changed, *self.pool[1:]])
        with self.assertRaises(r.RankingError):
            r.rank_candidates(task(), self.pool[:-1])

    def test_invalid_grid_and_option_boundaries(self):
        for grid in ([[]], [], [[True]], [[1.0]], [[10]], [[-1]], [[1], [1, 2]], [[0] * 31]):
            bad = task()
            bad["demos"][0]["input"] = grid
            with self.assertRaises(r.RankingError):
                r.rank_candidates(bad, self.pool)
        for options in ({"seed": True}, {"seed": -1}, {"seed": 2**64}, {"budget": 0},
                        {"budget": 5966}, {"budget": True}, {"method": "hard_pruned"}):
            with self.assertRaises(r.RankingError):
                r.rank_candidates(task(), self.pool, **options)
        with self.assertRaises(r.RankingError):
            r.rank_candidates({"task_id": "x", "demos": []}, self.pool)
        for tid in ("", "x" * 129, "\ud800", 5, None):
            with self.assertRaises(r.RankingError):
                r.rank_candidates(task(tid), self.pool)


if __name__ == "__main__":
    unittest.main()
