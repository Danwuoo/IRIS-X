"""Deterministic boundaries for the distinct compact ABC owner-Editor save."""

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from irisx.arc_nvarc_abc import TASKS, grammar_sequences, public_grammar
from irisx.arc_nvarc_analysis_zip_abc import verify_abc_zip, write_abc_zip
from irisx.arc_nvarc_combined import read
from irisx.canonical import digest_value
from irisx.errors import ValidationError
from tools.stage_nvarc_abc import PLAN, RUN, make_plan, metadata, preflight, save_fields
from tools.analyze_nvarc_abc import inspect
from tools.preflight_nvarc_combined import guard_prefix

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-001-submission"


class ABCBoundaryTests(unittest.TestCase):
    def test_fixed_material_representation_and_budgets(self):
        plan = read(PLAN)
        self.assertEqual(make_plan(), plan)
        self.assertEqual(("A", "B", "C"), tuple(x["id"] for x in plan["arms"]))
        self.assertEqual([0, 0, 1], [x["ttt_steps_per_task"] for x in plan["arms"]])
        self.assertEqual(18, plan["limits"]["maximum_total_generation_calls"])
        self.assertEqual(36, plan["limits"]["maximum_total_returned_sequences"])
        self.assertEqual(3, plan["limits"]["maximum_total_ttt_steps"])
        self.assertEqual(set(), set(TASKS) & set(plan["sft_train_parent_ids"]))
        self.assertEqual("QUICK_SAVE", save_fields(PACKAGE, retained_review=True)["kernel_execution_type"])
        self.assertEqual([], metadata(plan)["competition_sources"])

    def test_public_shape_and_palette_fail_closed_without_truth(self):
        visible = read(PACKAGE / "visible.json")
        shape = public_grammar({"train": visible["00576224"]["train"],
                                "test": visible["00576224"]["test"]})
        self.assertEqual([6, 6], shape["shape"])
        self.assertTrue(shape["palette_rule"])
        different = public_grammar({"train": visible["0d3d703e"]["train"],
                                    "test": visible["0d3d703e"]["test"]})
        self.assertFalse(different["palette_rule"])
        self.assertEqual(list(range(10)), different["legal_colors"])
        damaged = copy.deepcopy(visible["00576224"])
        damaged["train"][1]["output"].pop()
        self.assertEqual("unsupported-shape", public_grammar(damaged)["status"])

    def test_grammar_budget_and_model_ranked_output(self):
        g = {"status": "supported", "shape": [2, 2], "palette_rule": True,
             "legal_colors": [1, 2]}
        calls = []
        def logits(prefix):
            calls.append(tuple(prefix))
            values = [-10.0] * 16
            values[1], values[2], values[10], values[15] = -0.1, -0.2, -0.3, -0.4
            return values
        result = grammar_sequences([14, 12, 10], logits, g, maximum_tokens=64,
                                   maximum_expansions=12)
        self.assertEqual(12, result["expansions"])
        self.assertEqual(2, len(result["sequences"]))
        self.assertNotEqual(result["sequences"][0]["tokens"], result["sequences"][1]["tokens"])
        self.assertTrue(all(row["tokens"][-1] == 15 for row in result["sequences"]))
        with self.assertRaises(ValidationError):
            grammar_sequences([1], logits, g, maximum_tokens=5, maximum_expansions=12)
        with self.assertRaises(ValidationError):
            grammar_sequences([1], logits, g, maximum_tokens=64, maximum_expansions=11)

    def test_partial_zip_and_digest_tampering_rejected(self):
        plan_digest = digest_value(read(PLAN))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            work = root / RUN
            work.mkdir()
            (work / "aggregate-terminal.json").write_text('{"outcome":"failed"}', encoding="utf-8")
            (work / "worker").mkdir()
            (work / "worker" / "call-ledger.json").write_text('{"records":[]}', encoding="utf-8")
            (work / "wheel").mkdir()
            (work / "wheel" / "ignore.whl").write_text("weights or code", encoding="utf-8")
            target = root / "結果.zip"
            write_abc_zip(work, target, RUN, plan_digest)
            manifest = verify_abc_zip(target, run_id=RUN, plan_digest=plan_digest)
            self.assertEqual({"aggregate-terminal.json", "worker/call-ledger.json"}, set(manifest["files"]))
            report = inspect(target)
            self.assertEqual("unknown-no-isolated-truth", report["scoring"])
            self.assertTrue(all(row["pass_at_1"] is None for rows in report["arms"].values()
                                for row in rows))
            tampered = root / "tampered.zip"
            with zipfile.ZipFile(target) as original, zipfile.ZipFile(tampered, "w") as changed:
                for name in original.namelist():
                    data = original.read(name)
                    changed.writestr(name, b"changed" if name == "worker/call-ledger.json" else data)
            with self.assertRaisesRegex(RuntimeError, "digest differs"):
                verify_abc_zip(tampered, run_id=RUN, plan_digest=plan_digest)

    def test_exact_package_preflight_and_save_guard(self):
        report = preflight(PACKAGE, retained_review=True)
        self.assertTrue(report["retained_wheel_verified"])
        fields = save_fields(PACKAGE, retained_review=True)
        self.assertTrue(fields["is_private"])
        self.assertFalse(fields["enable_internet"])
        with tempfile.TemporaryDirectory() as temp:
            bad = Path(temp) / "bad.ipynb"
            bad.write_text(fields["text"], encoding="utf-8")
            self.assertIn('"execution_count": null', bad.read_text(encoding="utf-8"))

    def test_notebook_guard_accepts_exact_plan_and_rejects_rehashed_bytes_before_setup(self):
        source = "".join(read(PACKAGE / "kernel/kaggle-notebook.ipynb")["cells"][1]["source"])
        with tempfile.TemporaryDirectory() as temp:
            local = source.replace('work = Path("/kaggle/working") / RUN',
                                   'work = Path(' + repr(temp) + ') / RUN')
            prefix = guard_prefix(local)
            path = Path(temp) / "probe.py"
            path.write_text(prefix, encoding="utf-8")
            result = subprocess.run([sys.executable, "-I", str(path)],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("offline approved guard accepted", result.stderr)
            self.assertTrue((Path(temp) / "結果.zip").is_file())
        with tempfile.TemporaryDirectory() as temp:
            changed = source.replace('work = Path("/kaggle/working") / RUN',
                                     'work = Path(' + repr(temp) + ') / RUN').replace(
                                         'PLAN_DIGEST = ' + repr(digest_value(read(PLAN))),
                                         'PLAN_DIGEST = ' + repr("sha256:" + "0" * 64))
            path = Path(temp) / "probe.py"
            path.write_text(guard_prefix(changed), encoding="utf-8")
            result = subprocess.run([sys.executable, "-I", str(path)],
                                    capture_output=True, text=True, timeout=20)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("ABC draft is inert", result.stderr)


if __name__ == "__main__":
    unittest.main()
