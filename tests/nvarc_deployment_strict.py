"""Installed wheel and real tokenizer tests; missing ML/source never skips."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from tools import irisx_build_backend
from irisx.arc_nvarc_source_bundle import build_bundle, verify_bundle, NOTEBOOK
from irisx.arc_nvarc_sdg import BoundedLocalHFTeacher
from irisx.arc_nvarc_teacher_profile import LIMITS, TOTAL_TOKENS
from irisx.errors import ValidationError

ROOT = Path(__file__).resolve().parents[1]
TRIAL = ROOT / "trials/arc-agi-2-qwen35-nvarc"
LOCAL = ROOT / ".irisx/arc-agi-2/qwen35-nvarc"


def prepare_probe(root: Path) -> None:
    wheel = irisx_build_backend.build_wheel(str(root / "wheel"))
    with zipfile.ZipFile(root / "wheel" / wheel) as archive:
        archive.extractall(root / "site")
    build_bundle(LOCAL / "source", TRIAL / "source-manifest.json", root / "source-bundle")
    shutil.copyfile(ROOT / "tests/nvarc_installed_wheel_probe.py", root / "probe.py")
    shutil.copyfile(TRIAL / "configs/source-integration-sft-4b-001.json", root / "config.json")


class DeploymentTests(unittest.TestCase):
    def test_installed_wheel_real_tiny_source_flow_and_bundle_tampering(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".irisx", prefix="nvarc-installed-") as temp:
            root = Path(temp)
            prepare_probe(root)
            env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                   "HF_DATASETS_OFFLINE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
            env.pop("PYTHONPATH", None)
            check = subprocess.run([sys.executable, "-I", str(root / "probe.py")], cwd=root,
                                   env=env, capture_output=True, text=True, timeout=180)
            self.assertEqual(0, check.returncode, check.stdout + check.stderr)
            observed = json.loads((root / "probe-result.json").read_bytes())
            self.assertEqual((1, 1, 4), (observed["tiny_sft_steps"], observed["ttt_steps"], observed["generation_calls"]))
            path = root / "source-bundle" / NOTEBOOK
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.assertRaises(ValidationError):
                verify_bundle(root / "source-bundle", observed["source_bundle_digest"])
            path.write_bytes(original)
            (root / "source-bundle/unexpected.json").write_text("{}")
            with self.assertRaises(ValidationError):
                verify_bundle(root / "source-bundle", observed["source_bundle_digest"])

    def test_direct_mode_eos_and_stage_budget_with_actual_tokenizer(self):
        import torch
        from transformers import Qwen3_5Tokenizer

        tokenizer = Qwen3_5Tokenizer(vocab={"<|endoftext|>": 0, "a": 1}, merges=[],
            chat_template="{% if enable_thinking is sameas false %}a{% else %}aaa{% endif %}")
        case = self

        class Model:
            device = torch.device("cpu")

            def generate(self, tokens, **kwargs):
                case.assertEqual(1, tokens.shape[-1])
                case.assertEqual(512, kwargs["max_new_tokens"])
                return torch.cat((tokens, torch.tensor([[1, 0]])), dim=1)

        provider = BoundedLocalHFTeacher(Model(), tokenizer, model_material_digest="sha256:" + "0" * 64,
            maximum_input_tokens=8192, maximum_output_tokens=3072, maximum_total_tokens=TOTAL_TOKENS,
            stage_limits=LIMITS, enable_thinking=False, require_complete=True)
        item = {"train_demos": [{"input": [[1]], "output": [[2]]}] * 2}
        response = provider.complete("summary", item,
            "{INPUT_IMAGE1}{OUTPUT_IMAGE1}{INPUT_IMAGE2}{OUTPUT_IMAGE2}{USER_COMMENTS}")
        provider.validate_response("summary", response)
        self.assertEqual("a", response["content"])
        self.assertEqual("eos", response["finish_reason"])
        self.assertEqual(4608, provider.reserved_tokens)
