"""Offline owner-save guard, bounded reservations and error ZIP behavior."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from irisx.arc_nvarc_editor004 import require_editor_authorization, observe_call, partial_counts
from irisx.arc_nvarc_analysis_zip import write_analysis_zip
from irisx.arc_nvarc_combined import require_live_authorization
from irisx.errors import ValidationError

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "trials/arc-agi-2-qwen35-nvarc/configs/m2-m3-combined-editor-004.json"


class Editor004Tests(unittest.TestCase):
    def test_only_exact_new_owner_envelope_and_old_gates_reject(self):
        plan = json.loads(PLAN.read_bytes())
        require_editor_authorization(plan)
        with self.assertRaises(ValidationError):
            require_live_authorization(plan)
        mutations = [("approved",False),("owner_decision","Decision 0037"),("run_id","nvarc-m2-m3-combined-003")]
        for key,value in mutations:
            draft = copy.deepcopy(plan); draft[key] = value
            with self.subTest(key=key),self.assertRaises(ValidationError):
                require_editor_authorization(draft)
        draft = copy.deepcopy(plan);draft["branches"]["m2"]["maximum_source_generation_calls"] = 13
        with self.assertRaises(ValidationError):
            require_editor_authorization(draft)

    def test_reservations_arm_indices_pending_counts_and_single_ttt(self):
        plan = json.loads(PLAN.read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            observe = observe_call(plan,output)
            observe({"kind":"ttt","status":"reserved","steps":1,"task_id":"00576224"})
            observe({"kind":"ttt","status":"complete","task_id":"00576224","observation":{"steps":1}})
            event = {"kind":"generation","status":"reserved","index":1,"task_id":"00576224","arm_id":"control-p020"}
            observe(event)
            counts = partial_counts(plan,"m2",output)
            self.assertEqual(1,counts["reserved_counters"]["generation"])
            self.assertEqual(0,counts["actual_counters"]["completed_generation"])
            with self.assertRaises(ValidationError):observe(event)
            with self.assertRaises(ValidationError):observe({**event,"index":5})
            observe({**event,"status":"complete","generation_observation":{"query_digest":"x"}})
            observe({**event,"arm_id":"candidate-p010"})
            self.assertEqual(2,partial_counts(plan,"m2",output)["reserved_counters"]["generation"])

    def test_partial_failure_zip_has_raw_digests_and_excludes_model_and_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp);work = root / "work";work.mkdir()
            (work / "aggregate-terminal.json").write_text('{"outcome":"failed"}')
            (work / "workers/m3/work").mkdir(parents=True)
            raw = work / "workers/m3/work/result.json";raw.write_text('{"raw_reply":"retained"}')
            (work / "sandbox-dependencies").mkdir()
            (work / "sandbox-dependencies/inventory.json").write_text('{}')
            (work / "workers/m2").mkdir()
            (work / "workers/m2/model.safetensors").write_bytes(b'not evidence')
            result = write_analysis_zip(work,root / "結果.zip","fixture","sha256:fixture")
            with zipfile.ZipFile(result["path"]) as archive:
                self.assertEqual({"aggregate-terminal.json","workers/m3/work/result.json","analysis-manifest.json"},set(archive.namelist()))
                manifest = json.loads(archive.read("analysis-manifest.json"))
                self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(),manifest["files"]["workers/m3/work/result.json"]["sha256"])
                self.assertFalse(manifest["contains_evaluator_truth"])
            with self.assertRaisesRegex(RuntimeError,"already exists"):
                write_analysis_zip(work,root / "結果.zip","fixture","x")


if __name__ == "__main__":
    unittest.main()
