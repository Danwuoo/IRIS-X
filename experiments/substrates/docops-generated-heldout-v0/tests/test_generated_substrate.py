from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


SUBSTRATE = Path(__file__).resolve().parents[1]
SCRIPTS = SUBSTRATE / "scripts"
sys.path.insert(0, str(SCRIPTS))
import generator  # noqa: E402


PROTOCOL = json.loads(
    (SUBSTRATE / "inputs" / "qualification-protocol.json").read_text(encoding="utf-8")
)
GENERATOR_SHA = hashlib.sha256(Path(generator.__file__).read_bytes()).hexdigest()


def instance(family_id: str, seed: int) -> dict:
    return generator.generate_instance(
        family_id,
        seed,
        PROTOCOL["candidate_freeze_sha"],
        GENERATOR_SHA,
        PROTOCOL["generator_config"],
    )


class GeneratedSubstrateTests(unittest.TestCase):
    def test_all_four_families_have_public_sufficient_independent_oracles(self) -> None:
        self.assertEqual(set(PROTOCOL["families"]), set(generator.FAMILIES))
        for family_id, seeds in PROTOCOL["families"].items():
            generated = instance(family_id, seeds[0])
            visible = generator.candidate_visible_bundle(generated)
            self.assertEqual(
                generator.solve_from_public(family_id, visible["public_input"]),
                generated["hidden_oracle"],
            )
            self.assertEqual(
                generator.oracle_from_hidden_state(
                    family_id, generated["hidden_generation_state"]
                ),
                generated["hidden_oracle"],
            )

    def test_same_seed_reproducible_and_different_seeds_vary(self) -> None:
        for family_id, seeds in PROTOCOL["families"].items():
            first = instance(family_id, seeds[0])
            repeated = instance(family_id, seeds[0])
            different = instance(family_id, seeds[1])
            self.assertEqual(first, repeated)
            self.assertNotEqual(
                first["manifest"]["public_input_hash"],
                different["manifest"]["public_input_hash"],
            )

    def test_candidate_visible_bundle_excludes_oracle_state_seed_and_freeze_sha(self) -> None:
        for family_id, seeds in PROTOCOL["families"].items():
            generated = instance(family_id, seeds[0])
            visible = generator.candidate_visible_bundle(generated)
            audit = generator.leakage_audit(visible, generated)
            self.assertTrue(audit["passed"], audit)
            self.assertNotIn("hidden_oracle", visible)
            self.assertNotIn("hidden_generation_state", visible)
            self.assertNotIn("generation_seed", visible)
            self.assertNotIn("candidate_freeze_sha", visible)

    def test_leakage_audit_rejects_injected_answer_and_hidden_oracle_keys(self) -> None:
        generated = instance(generator.FAMILIES[0], 4101)
        visible = generator.candidate_visible_bundle(generated)
        visible["public_input"]["expected_answer"] = generated["hidden_oracle"]
        visible["hidden_oracle"] = generated["hidden_oracle"]
        audit = generator.leakage_audit(visible, generated)
        self.assertFalse(audit["passed"])
        self.assertTrue(any("expected_answer" in finding for finding in audit["findings"]))
        self.assertTrue(any("hidden_oracle" in finding for finding in audit["findings"]))

    def test_invalid_generator_requests_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            instance("unknown-family", 1)
        with self.assertRaises(ValueError):
            generator.generate_instance(
                generator.FAMILIES[0],
                "not-an-int",  # type: ignore[arg-type]
                PROTOCOL["candidate_freeze_sha"],
                GENERATOR_SHA,
                PROTOCOL["generator_config"],
            )
        with self.assertRaises(ValueError):
            generator.generate_instance(
                generator.FAMILIES[0],
                1,
                PROTOCOL["candidate_freeze_sha"],
                GENERATOR_SHA,
                {"count": 0},
            )


if __name__ == "__main__":
    unittest.main()
