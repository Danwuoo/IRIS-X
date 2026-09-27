"""Offline historical/replacement guards; no setup, CUDA or model execution."""

import hashlib
import unittest

from irisx.arc_nvarc_combined import (APPROVED_DIGEST, REPAIR_DIGEST, REPAIR_RUN, DRAFT_DIGEST, DRAFT_SHA256,
                                    activate_plan, read, require_live_authorization, validate_plan)
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError
from tools.preflight_nvarc_combined import guard_prefix, probe_guard
from tools.stage_nvarc_combined import DRAFT, render


class CombinedActivationTests(unittest.TestCase):
    def test_exact_envelope_retains_all_child_scientific_fields_and_origin(self):
        draft = read(DRAFT)
        plan = activate_plan(draft)
        self.assertEqual(DRAFT_DIGEST, digest_value(draft))
        self.assertEqual(DRAFT_SHA256, hashlib.sha256(DRAFT.read_bytes()).hexdigest())
        self.assertEqual(APPROVED_DIGEST, digest_value(plan))
        self.assertEqual(draft["branches"], plan["branches"])
        with self.assertRaisesRegex(ValidationError, "Decision 0036"):
            require_live_authorization(plan)  # Historical 001 authorization is consumed.
        replacement = activate_plan(draft, run_id=REPAIR_RUN)
        self.assertEqual(REPAIR_DIGEST, digest_value(replacement))
        require_live_authorization(replacement)
        for branch in draft["branches"]:
            self.assertEqual({k: v for k, v in draft["branches"][branch].items() if k not in {"run_id", "kernel_id"}},
                             {k: v for k, v in replacement["branches"][branch].items() if k not in {"run_id", "kernel_id"}})
        validate_plan(plan, approved=True)
        with self.assertRaisesRegex(ValidationError, "inert"):
            require_live_authorization(draft)
        with self.assertRaises(ValidationError):
            validate_plan(plan)

    def test_edited_flags_old_decisions_limits_and_unknown_fields_cannot_activate(self):
        draft = read(DRAFT)
        draft["approved"] = True
        with self.assertRaises(ValidationError):
            require_live_authorization(draft)
        for key, value in (("owner_decision", "Decision 0034"), ("approved", 1),
                           ("original_draft_digest", "sha256:" + "0" * 64),
                           ("maximum_notebook_wall_seconds", 1801), ("unexpected", True)):
            plan = activate_plan(read(DRAFT), run_id=REPAIR_RUN)
            plan[key] = value
            with self.assertRaises(ValidationError):
                require_live_authorization(plan)
        plan = activate_plan(read(DRAFT), run_id=REPAIR_RUN)
        plan["branches"]["m3"]["maximum_teacher_calls"] = 5
        with self.assertRaises(ValidationError):
            require_live_authorization(plan)

    def test_approved_notebook_guard_accepts_exact_plan_and_rejects_rehashed_mutations(self):
        plan = activate_plan(read(DRAFT), run_id=REPAIR_RUN)
        def source(value):
            return render({"plan": canonical_bytes(value)}, {"plan": "plan.json"}, approved=True, run_id=REPAIR_RUN)
        probe_guard(source(plan), REPAIR_DIGEST, accepted=True, run_id=REPAIR_RUN)
        for value in (read(DRAFT), activate_plan(read(DRAFT)), {**plan, "owner_decision": "Decision 0034"},
                      {**plan, "approved": 1}, {**plan, "maximum_notebook_wall_seconds": 1801}):
            probe_guard(source(value), digest_value(value), run_id=REPAIR_RUN)

    def test_offline_prefix_cannot_reach_live_setup_even_with_exact_approval(self):
        plan = activate_plan(read(DRAFT), run_id=REPAIR_RUN)
        source = render({"plan": canonical_bytes(plan)}, {"plan": "plan.json"}, approved=True, run_id=REPAIR_RUN)
        prefix = guard_prefix(source)
        self.assertNotIn("os.environ.update", prefix)
        self.assertNotIn("pip", prefix)
        self.assertNotIn("import torch", prefix)
        self.assertNotIn("supervise(", prefix)
        self.assertNotIn("subprocess.run", prefix)


if __name__ == "__main__":
    unittest.main()
