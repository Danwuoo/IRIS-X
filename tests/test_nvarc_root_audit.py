import math
import unittest

from irisx.arc_nvarc_root_audit import audit_root
from irisx.arc_nvarc_candidates import bounded_dfs_search, candidate_score_limit
from irisx.arc_nvarc_representation import END
from irisx.errors import ValidationError


class RootAuditTests(unittest.TestCase):
    def test_default_frozen_bound_and_candidate_only_parameter_fail_closed(self):
        self.assertEqual(-math.log(.2), candidate_score_limit({}))
        self.assertEqual(-math.log(.1), candidate_score_limit({"cumulative_probability_threshold": .1}))
        for invalid in (True, 0, 1, -1, float("nan"), float("inf"), "0.02"):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                candidate_score_limit({"cumulative_probability_threshold": invalid})

    def test_more_tokens_expansions_cannot_unlock_diffuse_root_and_lower_threshold_is_not_answer(self):
        values = [math.log(0.099)] * 10 + [math.log(0.01 / 6)] * 6
        results = []
        for cap in (64, 512):
            result = bounded_dfs_search([14], lambda _: values, max_new_tokens=cap,
                max_score=-math.log(0.2), max_expansions=cap, max_sequences=2)
            self.assertEqual((1, []), (result["expansions"], result["sequences"]))
            results.append(result)
        audit = audit_root(results[0])
        self.assertEqual([0, 0, 10], [len(r["root_survivors"]) for r in audit["thresholds"]])
        # At a lower cumulative threshold the root opens, but second-token
        # uncertainty still exhausts ALL branches; no answer follows from it.
        lower = bounded_dfs_search([14], lambda _: values, max_new_tokens=64,
            max_score=-math.log(0.02), max_expansions=128, max_sequences=2)
        self.assertEqual((11, []), (lower["expansions"], lower["sequences"]))
        with self.assertRaisesRegex(ValidationError, "retained_root_log_probs_invalid"):
            audit_root({"diagnostics": {"root": {"log_probs": [0.] * 16, "allowed_token_ids": list(range(10))}}})

    def test_score_sums_include_eos_no_mask_renormalization_or_token_mean(self):
        def values(prefix):
            probabilities = [0.1 / 15] * 16
            probabilities[4 if len(prefix) == 1 else END] = 0.9
            return [math.log(p) for p in probabilities]
        result = bounded_dfs_search([14], values, max_new_tokens=2,
            max_score=-math.log(0.8), max_expansions=4, max_sequences=2)
        self.assertEqual([4, END], result["sequences"][0]["tokens"])
        self.assertAlmostEqual(-math.log(0.9 * 0.9), result["sequences"][0]["beam_nll"])
        stricter = bounded_dfs_search([14], values, max_new_tokens=2,
            max_score=-math.log(0.85), max_expansions=4, max_sequences=2)
        self.assertEqual([], stricter["sequences"])


if __name__ == "__main__":
    unittest.main()
