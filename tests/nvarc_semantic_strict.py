"""Actual isolated NumPy generated-program checks. Missing materials FAIL."""

import json
from pathlib import Path
import tempfile
import subprocess
import unittest

from irisx.arc_nvarc_semantics import (prepare_numpy, SemanticProgramExecutor,
                                     accept_semantic_record, accept_program_pairs)
from irisx.errors import ValidationError
from tests.test_nvarc_semantics import retained, item, SUMMARY, MIX, INPUT, OUTPUT, response

ROOT = Path(__file__).resolve().parents[1]
WHEEL = ROOT / ".irisx/arc-agi-2/trial-001/runtime/linux-cp312/numpy-2.2.6-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"


class SemanticStrictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=ROOT / ".irisx", prefix="semantic-strict-")
        cls.deps = Path(cls.temp.name) / "numpy"
        cls.manifest = prepare_numpy(WHEEL, cls.deps)
        cls.sandbox = SemanticProgramExecutor(cls.deps)
        # WSL boot is setup, separate from each generated program's hard bound.
        subprocess.run(["wsl", "-d", cls.sandbox.distribution, "--", "true"],
                       check=True, capture_output=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_numpy_contract_positive_has_lineage_and_independent_color_challenges(self):
        replies = {stage: response(text) for stage, text in {
            "summary": json.dumps(SUMMARY), "mix": json.dumps(MIX), "input-logic": INPUT, "output-logic": OUTPUT}.items()}
        accepted = accept_semantic_record(item(), replies, self.sandbox)
        self.assertEqual("accepted-bounded-contract", accepted["status"])
        self.assertEqual((5, 12, 44), (len(accepted["pairs"]), accepted["output_challenges"], accepted["program_invocations"]))
        self.assertTrue(accepted["source_filter_passed"])
        self.assertFalse(accepted["teacher_yield_claim"])
        self.assertEqual(set(replies), set(accepted["raw_response_digests"]))

    def test_retained_programs_reject_in_isolation_without_repairing_them(self):
        raw = retained()["responses"]
        observations = [self.sandbox.probe(raw["input-logic"]["content"], "generate_puzzle_input", seed=seed) for seed in range(5)]
        self.assertTrue(any(o.get("kind") == "dict" for o in observations))
        self.assertTrue(all(o.get("kind") == "dict" or o.get("error") == "ValueError" for o in observations))
        output = self.sandbox.probe(raw["output-logic"]["content"], "generate_puzzle_output", input_grid=[[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.assertEqual("IndexError", output["error"])

    def test_program_contract_mutations_reject_type_shape_colors_variation_and_index_answers(self):
        input_variants = {
            "input_type_mismatch": INPUT.replace("size=(3,3))", "size=(3,3)).astype(float)"),
            "input_shape_mismatch": INPUT.replace("size=(3,3)", "size=(2,3)"),
            "input_color_or_grid_invalid": INPUT.replace("integers(0,10", "integers(10,20"),
            "input_seed_variation_missing": "import numpy as np\ndef generate_puzzle_input(seed): return np.zeros((3,3),dtype=int)",
            "input_correlated_cell_traces": "import numpy as np\ndef generate_puzzle_input(seed): return np.full((3,3),np.random.default_rng(seed).integers(0,10),dtype=int)",
        }
        for reason, code in input_variants.items():
            with self.subTest(reason=reason), self.assertRaisesRegex(ValidationError, reason):
                accept_program_pairs(code, OUTPUT, MIX, self.sandbox)
        wrong_output = "import numpy as np\ndef generate_puzzle_output(input_grid): return np.arange(9).reshape(3,3)"
        with self.assertRaisesRegex(ValidationError, "output_permutation_mismatch"):
            accept_program_pairs(INPUT, wrong_output, MIX, self.sandbox)
        # General rectangular contract, independent of the two retained parents.
        control_input = INPUT.replace("size=(3,3)", "size=(2,3)")
        control_output = "import numpy as np\ndef generate_puzzle_output(input_grid): return np.asarray(input_grid)[::-1,::-1].copy()"
        accepted = accept_program_pairs(control_input, control_output,
            {"shape": [2, 3], "output_from_input": [5,4,3,2,1,0]}, self.sandbox)
        self.assertEqual(5, len(accepted["pairs"]))

    def test_namespace_canaries_and_resource_bounds_still_hold_with_numpy_mount(self):
        probes = [
            'import os\ndef generate_puzzle_input(seed):\n assert not os.path.exists("/mnt/c/Users")\n return np.array([[1]])',
            'import os,errno\ndef generate_puzzle_input(seed):\n os.mkdir("/tmp/inner")\n try: os.chroot("/tmp/inner")\n except OSError as e: return np.array([[int(e.errno==errno.EPERM)]])\n return np.array([[0]])',
            'def generate_puzzle_input(seed):\n try: open("/opt/numpy/numpy/WRITE-CANARY", "w")\n except OSError: return np.array([[1]])\n return np.array([[0]])',
            'import socket\ndef generate_puzzle_input(seed):\n s=socket.socket();s.settimeout(1)\n try: s.connect(("1.1.1.1",80))\n except OSError: return np.array([[1]])\n return np.array([[0]])',
            'def generate_puzzle_input(seed):\n try: x=bytearray(1000000000)\n except MemoryError: return np.array([[1]])\n return np.array([[0]])',
            'import os,time\ndef generate_puzzle_input(seed):\n n=0\n for i in range(24):\n  try:\n   p=os.fork()\n   if p==0: time.sleep(5);os._exit(0)\n   n+=1\n  except OSError: break\n return np.array([[int(n<24)]])',
        ]
        for code in probes:
            with self.subTest(code=code[:30]):
                self.assertEqual([[1]], self.sandbox.probe("import numpy as np\n" + code, "generate_puzzle_input", seed=0)["value"])
        with self.assertRaisesRegex(ValidationError, "sandbox failed"):
            self.sandbox.probe("import time\ndef generate_puzzle_input(seed): time.sleep(10)", "generate_puzzle_input", seed=0)

    def test_changed_dependency_inventory_fails_closed(self):
        path = self.deps / "UNBOUND"
        path.write_text("not part of cached wheel")
        try:
            with self.assertRaisesRegex(ValidationError, "sandbox_dependency_inventory_differs"):
                SemanticProgramExecutor(self.deps)
        finally:
            path.unlink()
        manifest = self.deps / "inventory.json"
        original = manifest.read_bytes()
        changed = json.loads(original)
        changed["wheel_sha256"] = "0" * 64
        manifest.write_text(json.dumps(changed))
        try:
            with self.assertRaisesRegex(ValidationError, "sandbox_dependency_inventory_differs"):
                SemanticProgramExecutor(self.deps)
        finally:
            manifest.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
