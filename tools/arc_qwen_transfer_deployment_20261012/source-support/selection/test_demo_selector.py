import copy
import math
import unittest

from demo_selector import select_answers, digest


def fixture():
    task = {"task_id": "unseen-parent", "demonstrations": [
        {"demo_id": "a", "input": [[1]], "output": [[2]]},
        {"demo_id": "b", "input": [[2]], "output": [[3]]}], "query_input": [[3]]}
    policy = {"format": "irisx/demo-only-grid-portfolio-v1",
              "candidate_order": ["base", "sft", "ttt"],
              "transform_order": ["identity", "transpose"], "maximum_answers": 2}
    candidates = []
    for cid in policy["candidate_order"]:
        candidates.append({"candidate_id": cid, "task_id": task["task_id"],
            "checkpoint_sha256": digest(cid), "adaptation_scope": "task-demonstrations" if cid == "ttt" else "none",
            "folds": [{"heldout_demo_id": did, "conditioning_demo_ids": [other],
                       "adaptation_demo_ids": [other] if cid == "ttt" else [],
                       "prediction": prediction, "nll_sum": 1.0, "token_count": 2,
                       "receipt_sha256": digest([cid, did])}
                      for did, other, prediction in [("a", "b", [[2]]), ("b", "a", [[3]])]],
            "query_predictions": [{"transform_id": transform, "grid": [[4]],
                                   "inverse_applied": True, "receipt_sha256": digest([cid, transform])}
                                  for transform in policy["transform_order"]]})
    policy["fold_conditioning_demo_ids"] = {"a": ["b"], "b": ["a"]}
    policy["candidate_specs"] = {cid: {"role": role, "checkpoint_sha256": digest(cid),
        "adaptation_scope": "task-demonstrations" if role == "task_ttt" else "none"}
        for cid, role in [("base", "frozen_base"), ("sft", "global_sft"), ("ttt", "task_ttt")]}
    return task, policy, candidates


class SelectorTests(unittest.TestCase):
    def test_positive_tie_prefers_registered_base(self):
        receipt = select_answers(*fixture())
        self.assertEqual(receipt["answers"][0]["candidate_id"], "base")
        self.assertEqual(len(receipt["answers"]), 1)
        self.assertFalse(receipt["query_targets_accessed"])

    def test_adapted_wins_on_demo_evidence_not_order(self):
        t, p, c = fixture()
        c[0]["folds"][0]["prediction"] = [[0]]
        c[1]["folds"][0]["prediction"] = [[0]]
        self.assertEqual(select_answers(t, p, c)["answers"][0]["candidate_id"], "ttt")

    def test_top_two_distinct_without_gold(self):
        t, p, c = fixture()
        c[1]["query_predictions"][0]["grid"] = [[5]]
        c[2]["query_predictions"][0]["grid"] = [[6]]
        self.assertEqual([r["grid"] for r in select_answers(t, p, c)["answers"]], [[[4]], [[5]]])

    def test_votes_and_registered_transform_tie(self):
        t, p, c = fixture()
        p["transform_order"].append("rot180")
        for candidate in c:
            candidate["query_predictions"].append({"transform_id": "rot180", "grid": [[5]], "inverse_applied": True, "receipt_sha256": "a" * 64})
            candidate["query_predictions"][1]["grid"] = [[5]]
        self.assertEqual(select_answers(t, p, c)["answers"][0]["grid"], [[5]])

    def test_abstention(self):
        t, p, c = fixture()
        for candidate in c:
            for prediction in candidate["query_predictions"]:
                prediction["grid"] = None
        self.assertTrue(select_answers(t, p, c)["abstention"])

    def test_inputs_immutable(self):
        args = fixture()
        before = copy.deepcopy(args)
        select_answers(*args)
        self.assertEqual(args, before)

    def test_query_gold_and_scoring_fields_forbidden(self):
        for key in ("query_output", "target", "correct", "public_score"):
            t, p, c = fixture()
            t[key] = [[4]]
            with self.assertRaises(ValueError):
                select_answers(t, p, c)

    def test_candidate_score_injection_forbidden(self):
        t, p, c = fixture()
        c[0]["test_correct"] = True
        with self.assertRaises(ValueError):
            select_answers(t, p, c)

    def test_heldout_demo_never_in_context(self):
        t, p, c = fixture()
        c[0]["folds"][0]["conditioning_demo_ids"] = ["a", "b"]
        with self.assertRaises(ValueError):
            select_answers(t, p, c)

    def test_heldout_demo_never_in_adaptation(self):
        t, p, c = fixture()
        c[2]["folds"][0]["adaptation_demo_ids"] = ["a", "b"]
        with self.assertRaises(ValueError):
            select_answers(t, p, c)

    def test_base_cannot_claim_task_updates(self):
        t, p, c = fixture()
        c[0]["folds"][0]["adaptation_demo_ids"] = ["b"]
        with self.assertRaises(ValueError):
            select_answers(t, p, c)

    def test_missing_or_duplicate_fold(self):
        for duplicate in (False, True):
            t, p, c = fixture()
            c[0]["folds"] = [c[0]["folds"][0]] * (2 if duplicate else 1)
            with self.assertRaises(ValueError):
                select_answers(t, p, c)

    def test_missing_candidate_is_not_favorable_selection(self):
        t, p, c = fixture()
        with self.assertRaises(ValueError):
            select_answers(t, p, c[1:])

    def test_missing_duplicate_unknown_transform(self):
        for mutation in ("missing", "duplicate", "unknown", "inverse"):
            t, p, c = fixture()
            rows = c[0]["query_predictions"]
            if mutation == "missing": rows.pop()
            elif mutation == "duplicate": rows[1]["transform_id"] = "identity"
            elif mutation == "unknown": rows[1]["transform_id"] = "extra"
            else: rows[1]["inverse_applied"] = False
            with self.assertRaises(ValueError): select_answers(t, p, c)

    def test_nonfinite_negative_nll_and_invalid_tokens(self):
        for value in (math.nan, math.inf, -1, True):
            t, p, c = fixture()
            c[0]["folds"][0]["nll_sum"] = value
            with self.assertRaises(ValueError): select_answers(t, p, c)
        for value in (0, -1, True, 1.5):
            t, p, c = fixture()
            c[0]["folds"][0]["token_count"] = value
            with self.assertRaises(ValueError): select_answers(t, p, c)

    def test_invalid_grid_types(self):
        for value in ([[True]], [[-1]], [[10]], [[1], [2, 3]], [], [[1.0]], [[math.nan]]):
            t, p, c = fixture()
            c[0]["query_predictions"][0]["grid"] = value
            with self.assertRaises(ValueError): select_answers(t, p, c)

    def test_registered_partial_context_and_full_ttt_lineage(self):
        t, p, c = fixture()
        t["demonstrations"].append({"demo_id": "c", "input": [[4]], "output": [[5]]})
        p["fold_conditioning_demo_ids"]["c"] = ["a"]
        for candidate in c:
            for row in candidate["folds"]:
                if candidate["adaptation_scope"] == "task-demonstrations":
                    row["adaptation_demo_ids"].append("c")
            candidate["folds"].append({"heldout_demo_id": "c", "conditioning_demo_ids": ["a"],
                "adaptation_demo_ids": ["a", "b"] if candidate["adaptation_scope"] == "task-demonstrations" else [],
                "prediction": [[5]], "nll_sum": 1.0, "token_count": 2, "receipt_sha256": "a" * 64})
        self.assertEqual(select_answers(t, p, c)["rankings"][0]["demo_denominator"], 3)
        c[0]["folds"][0]["conditioning_demo_ids"] = ["b", "c"]
        with self.assertRaises(ValueError): select_answers(t, p, c)

    def test_registered_context_cannot_be_empty_or_leaked(self):
        for ids in ([], ["a"], ["other"], ["b", "b"]):
            t, p, c = fixture()
            p["fold_conditioning_demo_ids"]["a"] = ids
            with self.assertRaises(ValueError): select_answers(t, p, c)

    def test_role_or_checkpoint_swap(self):
        for field, value in [("adaptation_scope", "task-demonstrations"), ("checkpoint_sha256", "f" * 64)]:
            t, p, c = fixture()
            c[0][field] = value
            with self.assertRaises(ValueError): select_answers(t, p, c)
        t, p, c = fixture()
        p["candidate_specs"]["base"]["role"] = "task_ttt"
        p["candidate_specs"]["base"]["adaptation_scope"] = "task-demonstrations"
        with self.assertRaises(ValueError): select_answers(t, p, c)

    def test_selection_hash(self):
        receipt = select_answers(*fixture())
        claimed = receipt.pop("selection_sha256")
        self.assertEqual(claimed, digest(receipt))


if __name__ == "__main__":
    unittest.main()
