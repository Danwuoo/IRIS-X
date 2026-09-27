"""Explicit cached-material, installed-wheel, real tiny-model and namespace QA."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from irisx.arc_nvarc_candidates import QwenCandidateBackend
from irisx.arc_nvarc_qwen35_adapter import full_prefix_log_probs
from irisx.arc_nvarc_representation import compact_loaded_model, GridTokenizer
from irisx.arc_nvarc_sdg import WSLNamespaceProgramExecutor
from tools.stage_nvarc_combined_candidate import stage, preflight, RUN
from tests.test_nvarc_combined_repair import INPUT_CODE, OUTPUT_CODE, MIX

ROOT = Path(__file__).resolve().parents[1]


class CombinedCandidateStrictTests(unittest.TestCase):
    def test_real_tiny_qwen_search_diagnostics_equal_unmasked_forward(self):
        import torch
        from tests.test_arc_nvarc_ml import NvarcMLTests
        torch.set_num_threads(2)
        torch.manual_seed(19)
        model = NvarcMLTests()._tiny_qwen().eval()
        compact_loaded_model(model, {"symbols": [{"source_token_ids": [index]} for index in range(16)]})
        backend = QwenCandidateBackend(model, dfs_max_expansions=2)
        backend.representation = "source-qwen"
        query = GridTokenizer(source_chat_newlines=True).encode_query({"train": [
            {"input": [[1]], "output": [[2]]}], "test": [{"input": [[3]]}]}, 0)
        expected = full_prefix_log_probs(model, query)
        backend.generate(query, beams=2, max_new_tokens=64)
        observation = backend.last_generation_observation
        self.assertEqual(expected, observation["diagnostics"]["root"]["log_probs"])
        self.assertEqual([15, 14, 12, 10], observation["query_role_tail"])
        self.assertLessEqual(backend.forward_calls, 2)
        self.assertEqual(backend.forward_calls, observation["expansions"])

    def test_authored_python_semantic_fixture_and_numpy_dependency_gate(self):
        sandbox = WSLNamespaceProgramExecutor()
        # This retained Linux namespace has no NumPy. Keep that failure visible,
        # then check a separately authored Python semantic control in isolation;
        # never replace the real teacher program's imports with a fake module.
        with self.assertRaisesRegex(Exception, "sandbox failed"):
            sandbox.execute_entry(INPUT_CODE, "generate_puzzle_input", seed=11)
        python_input = """import random
def generate_puzzle_input(seed):
 rng = random.Random(seed)
 return [[rng.randrange(10) for _ in range(3)] for _ in range(3)]
"""
        python_output = """def generate_puzzle_output(input_grid):
 flat = [color for row in input_grid for color in row]
 values = [flat[index] for index in [7,8,6,5,4,3,2,0,1]]
 if len(values) != 9: raise ValueError('nine cells required')
 return [values[start:start+3] for start in range(0,9,3)]
"""
        varied = []
        for seed in (11, 22, 33):
            input_grid = sandbox.execute_entry(python_input, "generate_puzzle_input", seed=seed)
            output = sandbox.execute_entry(python_output, "generate_puzzle_output", input_grid=input_grid)
            flat = [color for row in input_grid for color in row]
            reference = [flat[index] for index in MIX["output_from_input"]]
            self.assertEqual(reference, [color for row in output for color in row])
            self.assertEqual([3, 3], [len(input_grid), len(input_grid[0])])
            varied.append(input_grid)
        self.assertNotEqual(varied[0], varied[1])
        # An invalid teacher permutation cannot turn seven values into nine:
        broken = python_output.replace("[7,8,6,5,4,3,2,0,1]", "[0,1,2,3,4,5,6]")
        with self.assertRaisesRegex(Exception, "sandbox failed"):
            sandbox.execute_entry(broken, "generate_puzzle_output", input_grid=varied[0])

    def test_cached_package_determinism_actual_wheel_guards_and_rehashed_tampering(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx", prefix="candidate-strict-") as temp:
            root = Path(temp)
            first, second = root/"first", root/"second"
            summary = stage(first)
            self.assertEqual(summary, stage(second))
            report = preflight(first)
            self.assertTrue(report["execution_guard_rejected"])
            self.assertEqual(12, report["generated_hardware_fixture_probe"]["cases_passed"])
            probe = root / "installed.py"
            probe.write_text('''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from irisx.arc_nvarc_combined import require_live_authorization
from irisx.arc_nvarc_combined_worker import main
from irisx.arc_nvarc_teacher_spec import parse_spec
plan=json.loads(Path(sys.argv[2]).read_bytes())
for altered in (plan,{**plan,'approved':True,'owner_decision':'Decision 0036'}):
 try: require_live_authorization(altered)
 except Exception: pass
 else: raise AssertionError('inert candidate activated')
sys.argv=['worker','--plan',sys.argv[2],'--branch','m3','--paths','ABSENT','--hardware','ABSENT','--output','ABSENT']
try: main()
except Exception as e: assert 'Decision 0036' in str(e)
else: raise AssertionError('worker guard did not stop before missing paths')
assert parse_spec('mix','{"shape":[3,3],"output_from_input":[7,8,6,5,4,3,2,0,1]}')['shape']==[3,3]
print('installed candidate guards rejected; zero workload calls')
''', encoding="utf-8")
            wheel = next((first/"wheel").glob("*.whl"))
            result = subprocess.run([sys.executable, "-I", str(probe), str(wheel), str(first/"plan.json")],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("zero workload calls", result.stdout)
            # A matching summary hash does not authorize an altered reviewed template.
            path = first/"kernel/kaggle-notebook.ipynb"
            notebook = json.loads(path.read_bytes())
            notebook["cells"][0]["source"].append("\nprint('unreviewed')\n")
            path.write_text(json.dumps(notebook))
            from irisx.arc_nvarc_combined import sha, atomic
            summary["inventory"]["kernel/kaggle-notebook.ipynb"] = sha(path)
            atomic(first/"stage-summary.json", summary)
            with self.assertRaisesRegex(Exception, "executable template"):
                preflight(first)


if __name__ == "__main__":
    unittest.main()
