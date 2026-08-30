"""Targeted H-I1a safety, mutation, prevention, and oracle checks."""

from __future__ import annotations

import importlib.util
import inspect
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = ROOT / "experiments" / "exp-2026-08-30-preexecution-write-interception" / "scripts" / "run_experiment.py"
DEFINITION_PATH = ROOT / "experiments" / "exp-2026-08-30-preexecution-write-interception" / "inputs" / "experiment-definition.json"


def load_runner():
    spec = importlib.util.spec_from_file_location("h_i1a_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load H-I1a runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InterceptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()
        cls.definition = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
        cls.template, cls.actions, cls.policy, cls.expectations, _ = cls.runner.validate_definition(
            cls.definition
        )
        cls.by_id = {action["action_id"]: action for action in cls.actions}

    def copied_workspace(self, temporary: str, name: str = "workspace") -> tuple[Path, Path]:
        sandbox = Path(temporary) / "sandbox"
        sandbox.mkdir()
        workspace = sandbox / name
        shutil.copytree(self.template, workspace)
        return sandbox, workspace

    def test_fresh_copies_are_byte_identical_to_frozen_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary) / "sandbox"
            sandbox.mkdir()
            first = sandbox / "first"
            second = sandbox / "second"
            shutil.copytree(self.template, first)
            shutil.copytree(self.template, second)
            first_snapshot = self.runner.workspace_snapshot(first)
            second_snapshot = self.runner.workspace_snapshot(second)
            self.assertEqual(first_snapshot, second_snapshot)
            self.assertEqual(first_snapshot, self.definition["workspace_template_snapshot"])

    def test_sandbox_boundary_rejects_outside_absolute_and_network_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sandbox, workspace = self.copied_workspace(temporary)
            outside_workspace = Path(temporary) / "outside-workspace"
            shutil.copytree(self.template, outside_workspace)
            action = self.by_id["overwrite-protected"]
            with self.assertRaises(self.runner.DefinitionError):
                self.runner.validate_action_paths(outside_workspace, sandbox, action)
            for target in ("../escape.txt", str(Path(temporary).resolve() / "absolute.txt"), r"\\server\share\file.txt"):
                escaped = {**action, "target": target}
                with self.assertRaises(self.runner.DefinitionError, msg=target):
                    self.runner.validate_action_paths(workspace, sandbox, escaped)

    def test_identical_action_identity_is_used_in_both_arms(self) -> None:
        action = self.by_id["overwrite-protected"]
        expected_hash = self.definition["action_definition_sha256"][action["action_id"]]
        self.assertEqual(expected_hash, self.runner.sha256_bytes(self.runner.canonical_json_bytes(action)))
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary) / "sandbox"
            sandbox.mkdir()
            hashes = []
            for arm in self.runner.ARMS:
                workspace = sandbox / arm
                shutil.copytree(self.template, workspace)
                self.runner.execute_episode(workspace, sandbox, action, arm, self.policy)
                hashes.append(self.runner.sha256_bytes(self.runner.canonical_json_bytes(action)))
            self.assertEqual(hashes, [expected_hash, expected_hash])

    def test_post_hoc_arm_actually_mutates_every_prohibited_action(self) -> None:
        prohibited = self.expectations["prohibited_action_ids"]
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary) / "sandbox"
            sandbox.mkdir()
            for action_id in prohibited:
                workspace = sandbox / action_id
                shutil.copytree(self.template, workspace)
                episode = self.runner.execute_episode(
                    workspace,
                    sandbox,
                    self.by_id[action_id],
                    "post-hoc-check-v0",
                    self.policy,
                )
                self.assertTrue(episode["mutation_primitive_executed"], action_id)
                self.assertTrue(episode["post_state_oracle"]["prohibited_mutation_observed"], action_id)
                self.assertFalse(episode["post_state_oracle"]["protected_state_unchanged"], action_id)
                self.assertEqual(episode["policy_evaluation"]["timing"], "after_execution")

    def test_pre_execution_arm_blocks_before_primitive_and_preserves_state(self) -> None:
        prohibited = self.expectations["prohibited_action_ids"]
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary) / "sandbox"
            sandbox.mkdir()
            with patch.object(self.runner, "execute_action", side_effect=AssertionError("primitive executed")):
                for action_id in prohibited:
                    workspace = sandbox / action_id
                    shutil.copytree(self.template, workspace)
                    episode = self.runner.execute_episode(
                        workspace,
                        sandbox,
                        self.by_id[action_id],
                        "pre-execution-intercept-v0",
                        self.policy,
                    )
                    self.assertFalse(episode["mutation_primitive_executed"], action_id)
                    self.assertEqual(episode["input_snapshot_before"], episode["input_snapshot_after"])
                    self.assertTrue(episode["post_state_oracle"]["prohibited_mutation_prevented"], action_id)

    def test_permitted_controls_are_not_blocked(self) -> None:
        permitted = self.expectations["permitted_action_ids"]
        with tempfile.TemporaryDirectory() as temporary:
            sandbox = Path(temporary) / "sandbox"
            sandbox.mkdir()
            for action_id in permitted:
                workspace = sandbox / action_id
                shutil.copytree(self.template, workspace)
                episode = self.runner.execute_episode(
                    workspace,
                    sandbox,
                    self.by_id[action_id],
                    "pre-execution-intercept-v0",
                    self.policy,
                )
                self.assertEqual(episode["policy_evaluation"]["decision"], "permit", action_id)
                self.assertTrue(episode["mutation_primitive_executed"], action_id)
                self.assertTrue(episode["post_state_oracle"]["protected_state_unchanged"], action_id)

    def test_post_state_oracle_interface_excludes_interceptor_decision(self) -> None:
        parameters = tuple(inspect.signature(self.runner.post_state_oracle).parameters)
        self.assertEqual(parameters, ("before", "after", "action", "policy"))
        with tempfile.TemporaryDirectory() as temporary:
            sandbox, workspace = self.copied_workspace(temporary)
            action = self.by_id["overwrite-protected"]
            before = self.runner.workspace_snapshot(workspace)
            paths = self.runner.validate_action_paths(workspace, sandbox, action)
            self.runner.execute_action(action, paths)
            after = self.runner.workspace_snapshot(workspace)
            oracle = self.runner.post_state_oracle(before, after, action, self.policy)
            self.assertTrue(oracle["prohibited_mutation_observed"])


if __name__ == "__main__":
    unittest.main()
