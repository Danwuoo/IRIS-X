"""Offline owner-Editor authorization and no-run request regression checks."""

import copy
from pathlib import Path
import tempfile
import unittest

from irisx.arc_nvarc_combined import read, require_live_authorization, EDITOR_DIGEST
from irisx.errors import ValidationError
from tools.stage_nvarc_combined_editor import PLAN, RUN, validate, render, save_fields
from tools.stage_nvarc_combined_candidate import PLAN as CANDIDATE_PLAN
from tools.stage_nvarc_combined import metadata
from tools.preflight_nvarc_combined import probe_guard
from irisx.arc_nvarc_combined import atomic
from irisx.canonical import digest_value

ROOT = Path(__file__).resolve().parents[1]


class EditorAuthorizationTests(unittest.TestCase):
    def test_exact_editor_guard_preserves_candidate_and_rejects_changed_budget(self):
        plan = read(PLAN)
        validate(plan)
        self.assertEqual(read(CANDIDATE_PLAN)["branches"], plan["branches"])
        require_live_authorization(plan)
        changed = copy.deepcopy(plan)
        changed["branches"]["m3"]["maximum_teacher_calls"] += 1
        with self.assertRaises(ValidationError):
            require_live_authorization(changed)
        source = render({"plan": PLAN.read_bytes()}, {"plan": "plan.json"})
        probe_guard(source, EDITOR_DIGEST, accepted=True, run_id=RUN)
        source = render({"plan": CANDIDATE_PLAN.read_bytes()}, {"plan": "plan.json"})
        probe_guard(source, digest_value(read(CANDIDATE_PLAN)), run_id=RUN)

    def test_save_projection_requires_quick_save_and_unexecuted_private_notebook(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx") as temp:
            package = Path(temp)
            atomic(package / "plan.json", read(PLAN))
            atomic(package / "kernel/kernel-metadata.json", metadata(read(PLAN)))
            notebook = {"cells": [{"cell_type": "code", "source": ["print('fixture')\n"],
                                  "outputs": [], "execution_count": None}]}
            atomic(package / "kernel/kaggle-notebook.ipynb", notebook)
            fields = save_fields(package)
            self.assertEqual("QUICK_SAVE", fields["kernel_execution_type"])
            self.assertFalse(fields["enable_internet"])
            self.assertTrue(fields["is_private"])
            self.assertEqual("NvidiaL4", fields["machine_shape"])
            notebook["cells"][0]["execution_count"] = 1
            atomic(package / "kernel/kaggle-notebook.ipynb", notebook)
            with self.assertRaisesRegex(ValidationError, "was executed"):
                save_fields(package)


if __name__ == "__main__":
    unittest.main()
