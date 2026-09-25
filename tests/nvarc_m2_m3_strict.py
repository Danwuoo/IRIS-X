"""Actual pinned-source ML and namespace checks; no dependency skips."""

from __future__ import annotations

import copy
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import torch

from irisx.arc_nvarc_m2 import freeze_arc_sft_data, load_frozen_arc_sft_data
from irisx.arc_nvarc_fsdp import run as run_fsdp_probe
from irisx.arc_nvarc_representation import verify_model_material
from irisx.arc_nvarc_sdg import (WSLNamespaceProgramExecutor, render_source_teacher_prompt,
                                 replay_pinned_ten_stage_sdg, replay_teacher_program_ledgers,
                                 run_teacher_pipeline, SavedTeacher)
from irisx.canonical import canonical_bytes
from irisx.arc_nvarc_training import load_compact_model, train_torch_sft
from irisx.errors import ValidationError
from tools.nvarc_m2_m3 import (DEFAULT_CONFIG, SOURCE, checked_source, tiny_joint,
                                tiny_sft, tiny_solve)
from tools.preflight_nvarc_m2_m3 import preflight as preflight_stage
from tools.stage_nvarc_m3_teacher import stage as stage_teacher
from irisx.arc_nvarc_m3_trm import run_tiny_trm


class M2M3StrictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        checked_source()
        cls.config = json.loads(DEFAULT_CONFIG.read_bytes())

    def test_real_arc_qwen_resume_trm_and_joint_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data, sft, qwen, trm, joint = (root / name for name in
                                           ("arc-data", "sft", "qwen", "trm", "joint"))
            frozen = freeze_arc_sft_data(self.config, SOURCE, data)
            self.assertEqual((128, 0), (frozen["train_episodes"], frozen["dev_augmentation_count"]))
            self.assertFalse(frozen["dev_truth_retained"])
            self.assertNotIn('"output"', json.dumps(json.loads((data / "dev-visible.json").read_bytes())
                                                   ["00576224"]["test"]))
            tampered = copy.deepcopy(self.config)
            tampered["train"][0]["sha256"] = "0" * 64
            with self.assertRaises(ValidationError):
                freeze_arc_sft_data(tampered, SOURCE, root / "tampered")
            chain = tiny_sft(self.config, data, sft)
            self.assertEqual(2, chain["completion"]["steps"])
            self.assertEqual(chain["interruption"]["identity_digest"],
                             chain["completion"]["identity_digest"])
            # Uninterrupted same-model training must reproduce model and
            # optimizer state after the interrupted/reloaded path.
            continuous_model = load_compact_model(sft / "base", dtype="float32")
            sequences = load_frozen_arc_sft_data(self.config, data)
            training = {**self.config["sft"], "max_steps": 2,
                        "maximum_training_tokens": self.config["tiny_cpu_validation_tokens"]}
            continuous = train_torch_sft(continuous_model, sequences, root / "continuous",
                                         training, model_identity_digest=chain["base_material_digest"])
            resumed = torch.load(sft / "training/training-state.pt", weights_only=False)
            whole = torch.load(root / "continuous/training-state.pt", weights_only=False)
            self.assertEqual((resumed["cursor"], resumed["tokens_seen"], resumed["step"]),
                             (whole["cursor"], whole["tokens_seen"], whole["step"]))
            self.assertEqual(continuous["identity_digest"], chain["training_identity_digest"])
            for key in resumed["model"]:
                self.assertTrue(torch.equal(resumed["model"][key], whole["model"][key]), key)
            for key in resumed["optimizer"]["state"]:
                for state_key, value in resumed["optimizer"]["state"][key].items():
                    other = whole["optimizer"]["state"][key][state_key]
                    self.assertTrue(torch.equal(value, other) if torch.is_tensor(value)
                                    else value == other)
            solved = tiny_solve(self.config, data, sft, qwen)
            self.assertEqual(chain["sft_export_material_digest"], solved["sft_export_material_digest"])
            trm_chain = run_tiny_trm(self.config, SOURCE / "NVARC/external/TinyRecursiveModels",
                                     SOURCE, data, trm)
            self.assertEqual((1, 1, True), (trm_chain["train_steps"], trm_chain["ttt_steps"],
                                              trm_chain["reload_equal"]))
            joint_result = tiny_joint(self.config, data, sft, qwen, trm, joint)
            self.assertEqual(1, joint_result["trm_candidates"])
            self.assertEqual(8, joint_result["qwen_verifier_explicit_forwards"])
            self.assertEqual(1, joint_result["joint"]["branch_counts"]["trm"])
            self.assertFalse(joint_result["contains_evaluator_truth"])
            mounted = root / "flat-dataset-mount"
            shutil.copytree(sft / "export", mounted)
            (mounted / "dataset-metadata.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                verify_model_material(mounted, chain["sft_export_material_digest"])
            verify_model_material(mounted, chain["sft_export_material_digest"],
                                  allowed_extra_files={"dataset-metadata.json"})

    def test_real_namespace_limits_and_ten_stage_saved_replay(self):
        sandbox = WSLNamespaceProgramExecutor()
        self.assertEqual([[1, 2]], sandbox.execute("def transform(grid): return grid", [[1, 2]]))
        filesystem = ('def transform(grid):\n import os\n'
                      ' return [[1 if not os.path.exists("/mnt/c/Users") else 0]]')
        readonly = ('def transform(grid):\n'
                    ' try:\n  open("/usr/bin/nvarc-write-probe", "w").write("x")\n'
                    '  return [[0]]\n except OSError:return [[1]]')
        network = ('def transform(grid):\n import socket\n'
                   ' s=socket.socket();s.settimeout(1)\n'
                   ' try:s.connect(("1.1.1.1",80));return [[0]]\n'
                   ' except OSError:return [[1]]')
        memory = ('def transform(grid):\n'
                  ' try: x=bytearray(1000000000);return [[0]]\n'
                  ' except MemoryError:return [[1]]')
        processes = ('def transform(grid):\n import os,time\n n=0\n'
                     ' for i in range(24):\n'
                     '  try:\n   p=os.fork()\n'
                     '   if p==0:time.sleep(5);os._exit(0)\n   n+=1\n'
                     '  except OSError:break\n'
                     ' return [[1 if n<24 else 0]]')
        for program in (filesystem, readonly, network, memory, processes):
            self.assertEqual([[1]], sandbox.execute(program, [[1]]))
        with self.assertRaises(ValidationError):
            sandbox.execute('def transform(grid):\n import time;time.sleep(10);return grid', [[1]])
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(__file__).parent / "fixtures/nvarc_sdg_saved_replay.json"
            replay = replay_pinned_ten_stage_sdg(fixture, SOURCE, Path(temp) / "replay", sandbox)
            self.assertEqual((10, 10, 5, 0),
                             (replay["stage_count"], replay["generated_program_invocations"],
                              replay["pair_count"], replay["teacher_calls"]))
            self.assertTrue(replay["source_pair_filter_passed"])
            saved = json.loads(fixture.read_bytes())
            seed = Path(temp) / "teacher-seed.json"
            seed.write_bytes(canonical_bytes({"format": "irisx/nvarc-m3-teacher-seed-v1",
                                              "record": {"record_id": saved["record_id"]}},
                                             newline=True))
            ledgers = Path(temp) / "teacher-ledgers"
            run_teacher_pipeline([{"record_id": saved["record_id"]}],
                                 {stage: stage for stage in
                                  ("summary", "mix", "input-logic", "output-logic")},
                                 SavedTeacher(saved["responses"]), ledgers,
                                 seed=24, maximum_calls=0)
            teacher_replay = replay_teacher_program_ledgers(
                ledgers, seed, Path(temp) / "teacher-replay", sandbox)
            self.assertEqual((10, 5, True),
                             (teacher_replay["generated_program_invocations"],
                              teacher_replay["pair_count"],
                              teacher_replay["source_pair_filter_passed"]))

    def test_teacher_prompt_render_and_external_draft_guards(self):
        prompts = SOURCE / "NVARC/SDG/prompts"
        item = {"train_demos": [{"input": [[1]], "output": [[2]]},
                                {"input": [[3]], "output": [[4]]}],
                "source_comments": "Public training examples only",
                "second_description": "Second public training parent",
                "stage_responses": {"summary": "first summary", "mix": "mixed summary",
                                    "input-logic": "def generate_puzzle_input(seed): return [[seed % 10]]"}}
        for stage, filename, expected in (
                ("summary", "summary_v1.md", "Public training examples only"),
                ("mix", "mix_v1.md", "Second public training parent"),
                ("input-logic", "generate_puzzle_input.md", "mixed summary"),
                ("output-logic", "generate_puzzle_output.md", "def generate_puzzle_input")):
            rendered = render_source_teacher_prompt(stage, item,
                                                     (prompts / filename).read_text(encoding="utf-8"))
            self.assertIn(expected, rendered)
        with self.assertRaises(ValidationError):
            render_source_teacher_prompt("summary", {"train_demos": []},
                                         (prompts / "summary_v1.md").read_text(encoding="utf-8"))
        root = Path(__file__).resolve().parents[1]
        for template, plan_name, marker in (
                ("nvarc_m2_fsdp_notebook.py.tmpl", "m2-fsdp-feasibility-draft.json",
                 "exact owner-approved feasibility plan required"),
                ("nvarc_m3_teacher_notebook.py.tmpl", "m3-teacher-draft.json",
                 "exact owner-approved teacher plan required")):
            payload = (root / "trials/arc-agi-2-qwen35-nvarc/configs" / plan_name).read_bytes()
            encoded = base64.b64encode(payload).decode()
            source = (root / "tools" / template).read_text(encoding="utf-8")
            source = source.replace("__PAYLOADS__", repr({"plan": encoded})).replace(
                "__HASHES__", repr({"plan": hashlib.sha256(payload).hexdigest()}))
            result = subprocess.run([sys.executable, "-c", source], capture_output=True,
                                    text=True, timeout=10)
            self.assertNotEqual(0, result.returncode)
            self.assertIn(marker, result.stderr)
        with self.assertRaises(ValidationError):
            run_fsdp_probe(root / "trials/arc-agi-2-qwen35-nvarc/configs/m2-fsdp-feasibility-draft.json",
                           root / "nonexistent-model", root / "nonexistent-sequences",
                           root / "nonexistent-output")

    def test_approved_teacher_package_preflight_is_read_only_and_bound(self):
        root = Path(__file__).resolve().parents[1]
        draft = (root / "trials/arc-agi-2-qwen35-nvarc/configs/m3-teacher-draft.json").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            authorization = base / "authorization.json"
            authorization.write_bytes(canonical_bytes({
                "approved": True,
                "draft_plan_sha256": hashlib.sha256(draft).hexdigest(),
                "run_id": "nvarc-m3-teacher-small-001",
                "kernel_id": "danielwuu/nvarc-m3-teacher-small-001",
                "owner_decision": "Decision 0028; exact two-probe approval",
            }, newline=True))
            package = base / "package"
            stage_teacher(package, authorization)
            report = preflight_stage(package, approved=True)
            self.assertTrue(report["approved"])
            self.assertEqual(0, report["external_calls"])
            self.assertFalse(report["draft_guard_verified"])
            with self.assertRaises(ValidationError):
                preflight_stage(package)
            metadata = package / "kernel/kernel-metadata.json"
            value = json.loads(metadata.read_bytes())
            value["enable_internet"] = True
            metadata.write_bytes(canonical_bytes(value, newline=True))
            with self.assertRaises(ValidationError):
                preflight_stage(package, approved=True)


if __name__ == "__main__":
    unittest.main()
