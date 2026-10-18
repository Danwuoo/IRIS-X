"""Offline, Torch-free source admission and adversarial panel-binding tests."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.irisx.arc_nvarc_data import known_variant_group
from tools.arc2_goal_sprint_20261017.data import canonical, digest
from tools.nvarc_efficient_fusion_20261018 import panels


def task(index):
    # Same independent1000 source construction as test_nvarc_matched_workflow,
    # without importing that module's optional Torch/transformers dependencies.
    return {"train": [{"input": [[0, 1, 2, 3] + [(index >> i) & 1 for i in range(12)] + [4, 4]], "output": [[2]]},
                      {"input": [[5, 6]], "output": [[7]]}]}


def corpus(root):
    training = {f"t{i:04}": task(i) for i in range(800)}
    development = {f"d{i:04}": task(1000 + i) for i in range(200)}
    public = {f"p{i:04}": {**task(2000 + i), "test": [{"input": [[9]]}] * (2 if i < 47 else 1)}
              for i in range(120)}
    source = root / "training"
    source.mkdir()
    manifest = {"files": {}, "protected_ids": list(public),
                "upstream": {"fixed_splits": {"train": list(training), "dev": list(development)}}}
    for parent, value in {**training, **development}.items():
        # An invalid target is intentional: training-file test fields must not
        # be interpreted, validated as training, or included in any panel.
        raw = canonical({**value, "test": [{"input": [[8]], "output": "FORBIDDEN-UNUSED"}]})
        (source / (parent + ".json")).write_bytes(raw)
        manifest["files"]["data/training/" + parent + ".json"] = {
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    path = root / "manifest.json"
    path.write_bytes(canonical(manifest))
    pin = hashlib.sha256(path.read_bytes()).hexdigest()
    split = {"training_manifest_sha256": pin, "training_tasks": 800, "dev_tasks": 200,
             "train_ids_digest": digest(sorted(training)), "dev_ids_digest": digest(sorted(development)),
             "public_digest": digest(public), "training_test_fields_used": False, "excluded_task_ids": []}
    kwargs = {"training_root": source, "training_manifest_path": path,
              "expected_training_manifest_sha256": pin}
    return training, development, public, split, kwargs


def reseal(prepared):
    admission, protocol, binding = (prepared[k] for k in ("admission", "protocol", "source_binding"))
    for key, field in (("source_sha256", "source"), ("split_sha256", "split"),
                       ("family_lineage_sha256", "family_lineage")):
        admission[key] = protocol[key] = panels.sha(binding[field])
    protocol["admission_sha256"] = panels.sha(admission)
    prepared["pins"] = {"admission_sha256": panels.sha(admission), "protocol_sha256": panels.sha(protocol),
                        "source_binding_sha256": panels.sha(binding)}


def rewrite_source(args, replacements):
    """Make a distinct synthetic source/pin, not a mutation of production data."""
    training, development, public, split, kwargs = args
    path = kwargs["training_manifest_path"]
    manifest = json.loads(path.read_bytes())
    for parent, value in replacements.items():
        (training if parent in training else development)[parent] = copy.deepcopy(value)
        raw = canonical({**value, "test": "UNUSED-NOT-TRAINING"})
        (kwargs["training_root"] / (parent + ".json")).write_bytes(raw)
        manifest["files"]["data/training/" + parent + ".json"] = {
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    path.write_bytes(canonical(manifest))
    pin = hashlib.sha256(path.read_bytes()).hexdigest()
    kwargs["expected_training_manifest_sha256"] = split["training_manifest_sha256"] = pin


class EfficientFusionPanelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.args = corpus(Path(cls.temp.name))
        cls.prepared = panels.prepare_panels(*cls.args[:4], **cls.args[4])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_fixed64_96_counts_exclusions_and_exposure_qualification(self):
        prepared, protocol = self.prepared, self.prepared["protocol"]
        self.assertEqual(len(prepared["training"]), 64)
        self.assertEqual(len(prepared["development"]), 96)
        self.assertEqual([len(protocol[k]) for k in
                          ("excluded_previous_panel", "excluded_stability_panel", "excluded_matched_panel")], [24, 32, 16])
        self.assertEqual(protocol["available_development_variant_groups"], 128)
        self.assertEqual(protocol["exposed_development_parents"], 72)
        self.assertEqual(protocol["exposed_development_variant_groups"], 72)
        self.assertEqual(protocol["probability_policy"], "fp32-backbone-math-v1")
        selected = set(protocol["development_parent_ids"])
        for key in ("excluded_previous_panel", "excluded_stability_panel", "excluded_matched_panel"):
            self.assertFalse(selected & set(protocol[key]))
        self.assertFalse(set(protocol["development_variant_groups"].values())
                         & set(protocol["excluded_development_variant_groups"]))
        self.assertFalse(protocol["initial_weight_cleanliness_claimed"])
        self.assertFalse(protocol["performance_or_difficulty_selection_used"])
        self.assertFalse(prepared["source_binding"]["family_lineage"]["semantic_family_independence_claimed"])
        self.assertEqual(len(prepared["source_binding"]["source"]["files"]), 1000)
        self.assertTrue(all(set(t) == {"train"} for t in prepared["training"].values()))
        self.assertNotIn("FORBIDDEN-UNUSED", json.dumps(prepared))
        self.assertIs(panels.validate_prepared(prepared), prepared)

    def test_historical_selectors_match_frozen_ordering(self):
        development = self.args[1]
        groups = self.prepared["source_binding"]["family_lineage"]["groups"]["dev"]
        order = lambda salt: sorted(development, key=lambda p: hashlib.sha256((salt + p).encode()).hexdigest())
        previous = order("nvarc-dev-v1:")[:24]
        unavailable = {groups[p] for p in previous}
        chosen = []
        for parent in order("compact-paired-ttt-stability-v1:"):
            if groups[parent] not in unavailable:
                chosen.append(parent)
                unavailable.add(groups[parent])
            if len(chosen) == 32:
                break
        matched = []
        for parent in order("compact-matched-controls-v1:dev:"):
            if groups[parent] not in unavailable:
                matched.append(parent)
                unavailable.add(groups[parent])
            if len(matched) == 16:
                break
        self.assertEqual(previous, self.prepared["protocol"]["excluded_previous_panel"])
        self.assertEqual(chosen, self.prepared["protocol"]["excluded_stability_panel"])
        self.assertEqual(matched, self.prepared["protocol"]["excluded_matched_panel"])

    def test_mapping_order_does_not_change_frozen_payload(self):
        args = [dict(reversed(list(value.items()))) if index < 3 else value
                for index, value in enumerate(self.args[:4])]
        self.assertEqual(panels.prepare_panels(*args, **self.args[4]), self.prepared)

    def test_smaller_panels_are_explicit_synthetic_fixture_only(self):
        prepared = panels.prepare_panels(*self.args[:4], **self.args[4], train_count=2, dev_count=3)
        self.assertEqual((len(prepared["training"]), len(prepared["development"])), (2, 3))
        panels.validate_prepared(prepared)
        for train_count, dev_count in ((0, 96), (65, 96), (64, 97), (True, 96), (64, False)):
            with self.subTest(counts=(train_count, dev_count)), self.assertRaises(ValueError):
                panels.prepare_panels(*self.args[:4], **self.args[4], train_count=train_count, dev_count=dev_count)
        with self.assertRaisesRegex(ValueError, "official source requires"):
            panels.prepare_panels(*self.args[:4], training_root=self.args[4]["training_root"],
                                  training_manifest_path=self.args[4]["training_manifest_path"], train_count=2, dev_count=3)

    def test_wrong_source_pin_and_mapping_fail_closed(self):
        kwargs = {**self.args[4], "expected_training_manifest_sha256": "0" * 64}
        with self.assertRaisesRegex(ValueError, "independently pinned"):
            panels.prepare_panels(*self.args[:4], **kwargs)
        training = copy.deepcopy(self.args[0])
        training[next(iter(training))]["train"][0]["output"] = [[9]]
        with self.assertRaisesRegex(ValueError, "mapping differs"):
            panels.prepare_panels(training, *self.args[1:4], **self.args[4])

    def test_source_byte_corruption_and_inventory_addition_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            args = corpus(Path(temp))
            source = args[4]["training_root"]
            path = source / (next(iter(args[0])) + ".json")
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "source training bytes differ"):
                panels.prepare_panels(*args[:4], **args[4])
            (source / "extra.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "inventory"):
                panels.prepare_panels(*args[:4], **args[4])

    def test_public_answers_and_training_test_projection_fail(self):
        training, development, public, split = copy.deepcopy(self.args[:4])
        public[next(iter(public))]["test"][0]["output"] = [[1]]
        split["public_digest"] = digest(public)
        with self.assertRaisesRegex(ValueError, "answer-free"):
            panels.prepare_panels(training, development, public, split, **self.args[4])
        training[next(iter(training))]["test"] = [{"input": [[1]], "output": [[2]]}]
        with self.assertRaisesRegex(ValueError, "train-only"):
            panels.prepare_panels(training, self.args[1], self.args[2], self.args[3], **self.args[4])

    def test_parent_and_content_public_overlap_fail(self):
        public = copy.deepcopy(self.args[2])
        public[next(iter(public))]["train"] = copy.deepcopy(next(iter(self.args[0].values()))["train"])
        split = {**self.args[3], "public_digest": digest(public)}
        with self.assertRaisesRegex(ValueError, "known-variant overlap"):
            panels.prepare_panels(self.args[0], self.args[1], public, split, **self.args[4])
        public[next(iter(self.args[0]))] = public.pop(next(iter(public)))
        with self.assertRaisesRegex(ValueError, "parent overlap"):
            panels.prepare_panels(self.args[0], self.args[1], public, split, **self.args[4])

    def test_pins_and_resealed_dev_target_contamination_fail(self):
        altered = copy.deepcopy(self.prepared)
        altered["protocol"]["development_parent_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "pinned panel"):
            panels.validate_prepared(altered)
        altered = copy.deepcopy(self.prepared)
        parent = next(iter(altered["development"]))
        altered["development"][parent]["train"][0]["output"] = [[9]]
        altered["protocol"]["development_task_sha256"][parent] = panels.sha(altered["development"][parent])
        altered["protocol"]["development_target_digest"][parent] = digest([[9]])
        reseal(altered)
        with self.assertRaisesRegex(ValueError, "trusted source demonstrations"):
            panels.validate_prepared(altered)

    def test_resealed_protected_training_and_historical_dev_substitutions_fail(self):
        altered = copy.deepcopy(self.prepared)
        train_parent = next(iter(altered["training"]))
        dev_parent = next(iter(altered["development"]))
        altered["training"][train_parent] = copy.deepcopy(altered["development"][dev_parent])
        row = altered["admission"]["parents"][0]
        row["task_sha256"] = panels.sha(altered["training"][train_parent])
        row["variant_group"] = known_variant_group({**altered["training"][train_parent], "test": []})
        row["family_id"] = "known-variant:" + row["variant_group"]
        altered["admission"]["excluded"] = {"parent_ids": [], "variant_groups": [], "family_ids": []}
        reseal(altered)
        with self.assertRaisesRegex(ValueError, "trusted source demonstrations"):
            panels.validate_prepared(altered)
        altered = copy.deepcopy(self.prepared)
        historical = altered["protocol"]["excluded_previous_panel"][0]
        altered["development"][historical] = copy.deepcopy(self.args[1][historical])
        del altered["development"][dev_parent]
        index = altered["protocol"]["development_parent_ids"].index(dev_parent)
        altered["protocol"]["development_parent_ids"][index] = historical
        reseal(altered)
        with self.assertRaisesRegex(ValueError, "source-derived fixed development"):
            panels.validate_prepared(altered)

    def test_resealed_variant_and_exclusion_changes_fail(self):
        for key, change in (("development_variant_groups", lambda value: value.update({next(iter(value)): "f" * 64})),
                            ("excluded_matched_panel", lambda value: value.reverse())):
            altered = copy.deepcopy(self.prepared)
            change(altered["protocol"][key])
            reseal(altered)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "fixed panel protocol"):
                panels.validate_prepared(altered)
        altered = copy.deepcopy(self.prepared)
        altered["source_binding"]["family_lineage"]["groups"]["train"][next(iter(self.args[0]))] = \
            next(iter(altered["source_binding"]["family_lineage"]["groups"]["public"].values()))
        altered["source_binding"]["split"]["known_variant_partition_sha256"] = panels.sha(
            altered["source_binding"]["family_lineage"]["groups"])
        reseal(altered)
        with self.assertRaisesRegex(ValueError, "known-variant overlap"):
            panels.validate_prepared(altered)

    def test_availability_is_recomputed_for_duplicate_variants(self):
        protocol = self.prepared["protocol"]
        exposed = set(protocol["excluded_previous_panel"] + protocol["excluded_stability_panel"]
                      + protocol["excluded_matched_panel"])
        eligible = sorted(set(self.args[1]) - exposed)
        with tempfile.TemporaryDirectory() as temp:
            args = corpus(Path(temp))
            rewrite_source(args, {eligible[1]: args[1][eligible[0]]})
            prepared = panels.prepare_panels(*args[:4], **args[4])
            self.assertEqual(prepared["protocol"]["available_development_parents"], 128)
            self.assertEqual(prepared["protocol"]["available_development_variant_groups"], 127)
            self.assertEqual(len(set(prepared["protocol"]["development_variant_groups"].values())), 96)
            panels.validate_prepared(prepared)
            rewrite_source(args, {p: args[1][eligible[0]] for p in eligible[1:35]})
            with self.assertRaisesRegex(ValueError, "insufficient independent"):
                panels.prepare_panels(*args[:4], **args[4])

    def test_repeated_held_inputs_are_not_eligible(self):
        protocol = self.prepared["protocol"]
        exposed = set(protocol["excluded_previous_panel"] + protocol["excluded_stability_panel"]
                      + protocol["excluded_matched_panel"])
        parent = sorted(set(self.args[1]) - exposed)[0]
        with tempfile.TemporaryDirectory() as temp:
            args = corpus(Path(temp))
            value = copy.deepcopy(args[1][parent])
            value["train"][1]["input"] = value["train"][0]["input"]
            rewrite_source(args, {parent: value})
            prepared = panels.prepare_panels(*args[:4], **args[4])
            self.assertEqual(prepared["protocol"]["available_development_variant_groups"], 127)
            self.assertNotIn(parent, prepared["development"])

    def test_pure_validation_does_not_read_files_and_torch_import_is_forbidden(self):
        from unittest.mock import patch
        with patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected source reread")):
            panels.validate_prepared(self.prepared)
        code = """
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'torch', 'transformers', 'peft', 'numpy'}:
        raise AssertionError('heavy dependency imported: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from tools.nvarc_efficient_fusion_20261018 import panels
assert 'torch' not in sys.modules
assert panels.PROTOCOL == 'compact-efficient-fusion-v1'
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                                check=False, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
