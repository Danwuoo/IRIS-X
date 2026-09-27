"""Actual tiny M2 integration and saved M3 rejection; no provider calls."""

import copy
import json
from pathlib import Path
import tempfile
import subprocess
from unittest.mock import patch
import unittest

from irisx.arc_nvarc_editor004 import run_m2, run_m3, verify_branch
from irisx.arc_nvarc_source_continuation import EXPORT, TRAINING
from irisx.arc_nvarc_combined import read, atomic
from irisx.arc_nvarc_representation import compact_loaded_model
from irisx.arc_nvarc_sdg import BoundedLocalHFTeacher
from tests.test_nvarc_editor004 import PLAN, ROOT
from tools.stage_nvarc_combined import M2


class Editor004StrictTests(unittest.TestCase):
    def test_actual_posix_launcher_with_pinned_numpy_and_no_host_files_or_network(self):
        from irisx.arc_nvarc_semantics import prepare_numpy
        from irisx.arc_nvarc_combined import sha
        wheel = ROOT / ".irisx/arc-agi-2/trial-001/runtime/linux-cp312/numpy-2.2.6-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
        launcher = ROOT / "tools/nvarc_sdg_semantic_namespace_004.sh"
        linux = lambda p:"/mnt/c"+p.resolve().as_posix()[2:]
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx",prefix="editor004-posix-") as temp:
            deps = Path(temp) / "numpy"
            prepare_numpy(wheel,deps)
            probe = Path(temp) / "probe.py"
            probe.write_text('''import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from irisx.arc_nvarc_semantics import SemanticProgramExecutor
executor=SemanticProgramExecutor(Path(sys.argv[2]),launcher=Path(sys.argv[3]),launcher_sha256=sys.argv[4])
assert executor.command()[0]=="sh"
code="import numpy as np\\ndef generate_puzzle_input(seed): return np.random.default_rng(seed).integers(0,10,size=(3,3))"
assert executor.probe(code,"generate_puzzle_input",seed=11)["shape"]==[3,3]
filesystem="import os,numpy as np\\ndef generate_puzzle_input(seed): return np.array([[int(not os.path.exists('/mnt/c/Users'))]])"
assert executor.probe(filesystem,"generate_puzzle_input",seed=0)["value"]==[[1]]
network="import socket,numpy as np\\ndef generate_puzzle_input(seed):\\n s=socket.socket();s.settimeout(1)\\n try: s.connect(('1.1.1.1',80))\\n except OSError: return np.array([[1]])\\n return np.array([[0]])"
assert executor.probe(network,"generate_puzzle_input",seed=0)["value"]==[[1]]
print("actual POSIX branch, NumPy, filesystem and network controls passed")
''',encoding="utf-8")
            subprocess.run(["wsl","-d","Ubuntu-24.04","--","true"],check=True,capture_output=True,timeout=60)
            completed = subprocess.run(["wsl","-d","Ubuntu-24.04","--","python3","-I",linux(probe),
                linux(ROOT / "src"),linux(deps),linux(launcher),sha(launcher)],capture_output=True,text=True,timeout=55)
            self.assertEqual(0,completed.returncode,completed.stderr)

    def test_real_tiny_worker_one_adaptation_twelve_calls_and_ledger_verification(self):
        import torch
        from tests.test_arc_nvarc_ml import NvarcMLTests
        torch.set_num_threads(2);torch.manual_seed(19)
        model = NvarcMLTests()._tiny_qwen().eval()
        compact_loaded_model(model,{"symbols":[{"source_token_ids":[i]} for i in range(16)]})
        original_to = model.to
        model.to = lambda target: original_to("cpu" if target == "cuda:0" else target)
        plan = read(PLAN)
        paths = {key:str(M2 / name) for key,name in (("source_config","source-config.json"),
            ("visible","visible.json"),("training_evidence","training-evidence.json"))}
        paths.update(m2_model="fixture",bundle=str(ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-editor-003/source-bundle"))
        material = {"kind":"sft-inference-export","base_material_digest":read(Path(paths["source_config"]))["profiles"]["4b"]["material_digest"],
                    "training_identity_digest":TRAINING}
        with tempfile.TemporaryDirectory() as temp, patch("irisx.arc_nvarc_training.load_compact_model",return_value=model),patch(
                "irisx.arc_nvarc_representation.verify_model_material",return_value=material):
            ready = []
            run_m2(plan,paths,Path(temp),lambda:ready.append(True))
            counts = verify_branch(plan,"m2",Path(temp))
            self.assertEqual(12,counts["generation_calls"])
            self.assertEqual(1,counts["ttt_steps"])
            self.assertEqual([True],ready)

    def test_saved_wrong_summary_is_complete_negative_with_one_call_and_raw_reply(self):
        import transformers
        from tests.test_nvarc_semantics import retained
        class SavedBoundTeacher(BoundedLocalHFTeacher):
            def complete(self,stage,item,prompt):
                self.reserved_tokens += sum(self.stage_limits[stage].values())
                return {"text":retained()["responses"]["summary"]["text"],"finish_reason":"eos",
                    "input_tokens":10,"output_tokens":10,"output_token_ids":[1]*10,
                    "enable_thinking":False,"model_material_digest":self.model_material_digest}
        class Model:
            def eval(self):return self
        package = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-editor-004-final"
        plan = read(PLAN)
        paths = {k:str(package / n) for k,n in (("seed","seed.json"),("prompts","prompts.json"),("model_manifest","model-manifest.json"))}
        paths["m3_model"] = "fixture"
        with tempfile.TemporaryDirectory() as temp,patch("irisx.arc_nvarc_4b_pilot.verify_model_material"),patch.object(
            transformers.AutoTokenizer,"from_pretrained",return_value=None),patch.object(
            transformers.AutoModelForMultimodalLM,"from_pretrained",return_value=Model()),patch(
            "irisx.arc_nvarc_sdg.BoundedLocalHFTeacher",SavedBoundTeacher):
            run_m3(plan,paths,Path(temp),lambda:None)
            counts = verify_branch(plan,"m3",Path(temp))
            self.assertEqual((1,0,0),(counts["teacher_calls"],counts["accepted_stages"],counts["accepted_pairs"]))
            result = read(Path(temp) / "work/result.json")
            self.assertIn("summary",result["response_digests"])
            self.assertEqual("teacher-stage-rejected",result["semantic_disposition"])


if __name__ == "__main__":unittest.main()
