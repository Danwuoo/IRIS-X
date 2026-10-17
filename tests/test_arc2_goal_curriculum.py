"""Offline lineage, verifier, byte seal, and bounded RE-ARC curriculum tests."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tests.platform_requirements import requires_linux

from tools.arc2_goal_sprint_20261017 import curriculum as c
from tools.arc2_goal_sprint_20261017.data import canonical, digest


TRAIN = "007bbfb7"
TRAIN2 = "00d62c1b"
DEV = "017c7c7b"
PUBLIC = "ffffffff"


def fixture_admission():
    training, dev = {TRAIN: {}, TRAIN2: {}}, {DEV: {}}
    public = {PUBLIC: {"train": [{"input": [[0, 1], [2, 3]], "output": [[3, 2], [1, 0]]}],
                       "test": [{"input": [[9, 8], [7, 6]]}]}}
    receipt = {"training_manifest_sha256": "a" * 64, "training_tasks": len(training), "dev_tasks": len(dev),
               "train_ids_digest": digest(sorted(training)), "dev_ids_digest": digest(sorted(dev)),
               "public_digest": digest(public), "training_test_fields_used": False}
    return (training, dev, public, receipt)


def fake_pair(width):
    return {"input": [[0] * (width - 1) + [1]], "output": [[2] * width]}


def fake_inspect(_root):
    functions = {file: {p: {"sha256": ("1" if file == "generators.py" else "2") * 64}
                             for p in (TRAIN, TRAIN2, DEV, PUBLIC, "aaaaaaaa")}
                 for file in ("generators.py", "verifiers.py")}
    return {"LICENSE": c.REARC_LICENSE_TEXT}, functions, set(functions["generators.py"])


def fake_worker(_root, parent, index, config):
    start = 3 + (5 if parent == TRAIN2 else 0) + 4 * index
    pairs = [fake_pair(start + i) for i in range(config.examples_per_bundle)]
    return {"pairs": pairs, "generator_sha256": "1" * 64, "verifier_sha256": "2" * 64,
            "events": [{"attempt": i, "seed": c._attempt_seed(config.seed, parent, index, i),
                        "status": "verified", "pair_sha256": hashlib.sha256(canonical(pair)).hexdigest()}
                       for i, pair in enumerate(pairs)]}


class CurriculumTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.admission = c.Admission.from_load_data(*fixture_admission(), fixture=True)

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, name="corpus", parents=None, config=None, worker=fake_worker):
        path = self.root / name
        with patch.object(c, "inspect_source", side_effect=fake_inspect), patch.object(c, "_run_worker", side_effect=worker):
            receipt = c.prepare_curriculum("not-imported", path, admission=self.admission,
                                           parent_ids=parents or [TRAIN], config=config)
        return path, receipt

    def load(self, path, receipt, **kwargs):
        return c.load_curriculum(path, admission=self.admission,
            expected_manifest_sha256=receipt["manifest_sha256"], allow_fixture=True, **kwargs)

    def mutate(self, path, receipt, change):
        manifest = json.loads((path / "manifest.json").read_text())
        change(manifest)
        raw = canonical(manifest) + b"\n"
        (path / "manifest.json").write_bytes(raw)
        return {**receipt, "manifest_sha256": hashlib.sha256(raw).hexdigest()}

    def test_production_rejects_arbitrary_ids_even_with_self_consistent_receipt(self):
        with self.assertRaisesRegex(ValueError, "pinned historical"):
            c.Admission.from_load_data(*fixture_admission())

    def test_receipt_checks_actual_split(self):
        t, d, p, r = fixture_admission()
        r["train_ids_digest"] = digest([DEV])
        with self.assertRaisesRegex(ValueError, "actual admitted"):
            c.Admission.from_load_data(t, d, p, r, fixture=True)

    def test_receipt_checks_test_fields_unused(self):
        t, d, p, r = fixture_admission()
        r["training_test_fields_used"] = True
        with self.assertRaisesRegex(ValueError, "actual admitted"):
            c.Admission.from_load_data(t, d, p, r, fixture=True)

    def test_query_answers_rejected_before_public_digest(self):
        t, d, p, r = fixture_admission()
        p[PUBLIC]["test"][0]["output"] = [[1]]
        with patch.object(c, "digest", side_effect=AssertionError("must not hash answers")):
            with self.assertRaisesRegex(ValueError, "query answers forbidden"):
                c.Admission.from_load_data(t, d, p, r, fixture=True)

    def test_split_overlap_fails(self):
        t, d, p, r = fixture_admission()
        d[TRAIN] = {}
        with self.assertRaisesRegex(ValueError, "disjoint"):
            c.Admission.from_load_data(t, d, p, r, fixture=True)

    def test_dev_public_and_unknown_parents_rejected_before_generator(self):
        for parent in (DEV, PUBLIC, "aaaaaaaa"):
            with self.subTest(parent=parent), patch.object(c, "inspect_source", side_effect=fake_inspect), patch.object(c, "_run_worker") as worker:
                with self.assertRaisesRegex(ValueError, "not an admitted"):
                    c.prepare_curriculum("unused", self.root / parent, admission=self.admission, parent_ids=[parent])
                worker.assert_not_called()

    def test_canonical_deterministic_roundtrip_parent_grouped(self):
        a, ar = self.prepare("a", parents=[TRAIN2, TRAIN])
        b, br = self.prepare("b", parents=[TRAIN, TRAIN2])
        self.assertEqual(ar, br)
        self.assertEqual({p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()},
                         {p.relative_to(b).as_posix(): p.read_bytes() for p in b.rglob("*") if p.is_file()})
        grouped, loaded = self.load(a, ar)
        self.assertEqual(loaded, ar)
        self.assertEqual(set(grouped), {TRAIN, TRAIN2})
        self.assertEqual(loaded["examples"], 8)
        self.assertEqual(grouped[TRAIN][0]["split"], "train")
        self.assertNotIn("test", grouped[TRAIN][0])

    def test_fixture_corpus_cannot_be_loaded_by_production_default(self):
        path, receipt = self.prepare()
        with self.assertRaisesRegex(ValueError, "fixture corpus"):
            c.load_curriculum(path, admission=self.admission, expected_manifest_sha256=receipt["manifest_sha256"])

    def test_stale_direct_admission_set_binding_rejected(self):
        bad = replace(self.admission, training_ids=frozenset({TRAIN, DEV}))
        with self.assertRaisesRegex(ValueError, "admission sets|binding differs"):
            bad.validate()
        bad = replace(self.admission, training_ids=frozenset({TRAIN}))
        with self.assertRaisesRegex(ValueError, "binding differs"):
            c.prepare_curriculum("never-read", self.root / "bad", admission=bad)

    def test_pinned_mit_license_is_retained_and_verified(self):
        path, receipt = self.prepare()
        self.assertEqual((path / "LICENSE").read_text(), c.REARC_LICENSE_TEXT)
        (path / "LICENSE").write_text("changed license")
        with self.assertRaisesRegex(ValueError, "bytes/hash"):
            self.load(path, receipt)

    def test_consumer_encoding_changes_do_not_rewrite_sealed_producer(self):
        path, receipt = self.prepare()
        manifest = json.loads((path / "manifest.json").read_text())
        original = manifest["source"]["implementation_sha256"]
        changed = {name: "9" * 64 for name in original}
        with patch.object(c, "_implementation_hashes", return_value=changed):
            self.load(path, receipt)
            self.load(path, receipt, expected_producer_hashes=original)
            with self.assertRaisesRegex(ValueError, "producer implementation expectation"):
                self.load(path, receipt, expected_producer_hashes=changed)
        self.assertEqual(json.loads((path / "manifest.json").read_text())["source"]["implementation_sha256"], original)

    def test_external_manifest_seal_required(self):
        path, receipt = self.prepare()
        with self.assertRaisesRegex(ValueError, "external corpus"):
            self.load(path, {**receipt, "manifest_sha256": "0" * 64})

    def test_bundle_bytes_tampering_rejected(self):
        path, receipt = self.prepare()
        bundle = next((path / "bundles").glob("*.json"))
        bundle.write_bytes(bundle.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "bytes/hash"):
            self.load(path, receipt)

    def test_manifest_lineage_rewrite_rejected_even_with_new_seal(self):
        path, receipt = self.prepare()
        receipt = self.mutate(path, receipt, lambda m: m["admission"]["train_parent_ids"].append(DEV))
        with self.assertRaisesRegex(ValueError, "current admission"):
            self.load(path, receipt)

    def test_bundle_index_dev_parent_rejected_even_with_new_seal(self):
        path, receipt = self.prepare()
        receipt = self.mutate(path, receipt, lambda m: m["bundles"][0].update(parent_id=DEV))
        with self.assertRaisesRegex(ValueError, "not an admitted"):
            self.load(path, receipt)

    def test_unsafe_path_rejected(self):
        path, receipt = self.prepare()
        receipt = self.mutate(path, receipt, lambda m: m["bundles"][0].update(path="../escape"))
        with self.assertRaisesRegex(ValueError, "identity/path"):
            self.load(path, receipt)

    def test_symlink_rejected(self):
        path, receipt = self.prepare()
        bundle = next((path / "bundles").glob("*.json"))
        actual = self.root / "actual.json"
        bundle.rename(actual)
        try:
            bundle.symlink_to(actual)
        except OSError:
            if os.name == "nt":
                self.skipTest("Windows symlink creation privilege unavailable")
            raise
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.load(path, receipt)

    def test_unexpected_member_rejected(self):
        path, receipt = self.prepare()
        (path / "evaluator.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "unexpected corpus"):
            self.load(path, receipt)

    def test_output_cannot_overwrite(self):
        path, receipt = self.prepare()
        before = (path / "manifest.json").read_bytes()
        with patch.object(c, "inspect_source", side_effect=fake_inspect):
            with self.assertRaisesRegex(ValueError, "already exists"):
                c.prepare_curriculum("unused", path, admission=self.admission, parent_ids=[TRAIN])
        self.assertEqual((path / "manifest.json").read_bytes(), before)

    def test_pair_and_task_public_d4_color_variants_rejected(self):
        public_pair = fixture_admission()[2][PUBLIC]["train"][0]
        transformed = {k: [[9 - x for x in row] for row in v[::-1]] for k, v in public_pair.items()}
        with self.assertRaisesRegex(ValueError, "PUBLIC demonstration pair"):
            self.admission.check_pairs([transformed, fake_pair(3), fake_pair(4)])
        only_task = replace(self.admission, public_pair_variants=frozenset())
        with self.assertRaisesRegex(ValueError, "PUBLIC demonstration task"):
            only_task.check_pairs([transformed])

    def test_public_pair_rejection_discards_entire_bundle(self):
        def worker(root, parent, index, config):
            result = fake_worker(root, parent, index, config)
            result["pairs"][0] = fixture_admission()[2][PUBLIC]["train"][0]
            return result
        with self.assertRaisesRegex(ValueError, "no complete clean"):
            self.prepare(worker=worker)
        self.assertFalse((self.root / "corpus").exists())
        self.assertFalse(list(self.root.glob(".curriculum-*")))

    def test_incomplete_bundle_never_admitted(self):
        def worker(root, parent, index, config):
            result = fake_worker(root, parent, index, config)
            result["pairs"].pop()
            return result
        with self.assertRaisesRegex(ValueError, "no complete clean"):
            self.prepare(worker=worker)

    def test_missing_verifier_provenance_rejected(self):
        def worker(root, parent, index, config):
            result = fake_worker(root, parent, index, config)
            result["verifier_sha256"] = "0" * 64
            return result
        with self.assertRaisesRegex(ValueError, "worker function provenance"):
            self.prepare(worker=worker)

    def test_source_tampering_rejected_before_execution(self):
        source = self.root / "source"
        source.mkdir()
        (source / "LICENSE").write_text("not pinned")
        with self.assertRaisesRegex(ValueError, "source digest differs"):
            c.inspect_source(source)

    def test_grid_and_configuration_bounds(self):
        for grid in ([[True]], [[-1]], [[10]], [[]], [[1], [2, 3]], [[0] * 31], [[0]] * 31):
            with self.subTest(grid=grid):
                with self.assertRaises(ValueError):
                    c._pair({"input": grid, "output": [[1]]})
        for change in ({"examples_per_bundle": 2}, {"examples_per_bundle": 7}, {"seed": True},
                       {"max_attempts_per_bundle": 10000}, {"attempt_timeout_seconds": float("inf")},
                       {"difficulty_lower": -0.1}, {"difficulty_upper": float("nan")}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                c.GenerationConfig(**change).validate()

    def test_subprocess_timeout_and_error_are_bounded_rejections(self):
        with patch.object(c.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 0.1)):
            result = c._run_worker("unused", TRAIN, 0, c.GenerationConfig())
        self.assertEqual(result["events"], [{"status": "bundle_timeout"}])
        with patch.object(c.subprocess, "run", return_value=subprocess.CompletedProcess([], 7, b"", b"error")):
            result = c._run_worker("unused", TRAIN, 0, c.GenerationConfig())
        self.assertEqual(result["events"], [{"status": "worker_error", "returncode": 7}])

    @requires_linux("RE-ARC bounded generation requires POSIX SIGALRM/setitimer in a fresh worker")
    def test_real_worker_calls_verifier_and_never_accepts_mismatch(self):
        namespace = {}
        generator = lambda _a, _b: {"input": ((0, 1),), "output": ((2, 2),)}
        calls = []
        def verifier(grid):
            calls.append(grid)
            return ((3, 3),)
        config = c.GenerationConfig(examples_per_bundle=3, max_attempts_per_bundle=3)
        with patch.object(c, "inspect_source", side_effect=fake_inspect), patch.object(c, "_compile_source", return_value=(generator, verifier, namespace)), patch.dict(os.environ, {"PYTHONHASHSEED": "0"}):
            result = c._generate_worker("unused", TRAIN, 0, config)
        self.assertEqual(len(calls), 3)
        self.assertEqual(result["pairs"], [])
        self.assertEqual({e["status"] for e in result["events"]}, {"verifier_mismatch"})

    @requires_linux("RE-ARC bounded generation requires POSIX SIGALRM/setitimer in a fresh worker")
    def test_real_worker_attempt_timeout_is_not_a_verified_pair(self):
        def generator(_a, _b):
            while True:
                pass
        config = c.GenerationConfig(examples_per_bundle=3, max_attempts_per_bundle=3, attempt_timeout_seconds=0.01)
        with patch.object(c, "inspect_source", side_effect=fake_inspect), patch.object(c, "_compile_source", return_value=(generator, lambda x: x, {})), patch.dict(os.environ, {"PYTHONHASHSEED": "0"}):
            result = c._generate_worker("unused", TRAIN, 0, config)
        self.assertEqual(result["pairs"], [])
        self.assertEqual({e["status"] for e in result["events"]}, {"attempt_timeout"})

    def test_worker_seed_is_stable_and_different_across_lineages(self):
        seeds = {c._attempt_seed(42, p, i, a) for p in (TRAIN, TRAIN2) for i in range(3) for a in range(10)}
        self.assertEqual(len(seeds), 60)
        self.assertEqual(c._attempt_seed(42, TRAIN, 0, 0), c._attempt_seed(42, TRAIN, 0, 0))

    def test_admitted_ledger_cannot_claim_verification_for_changed_pair(self):
        path, receipt = self.prepare()
        manifest = json.loads((path / "manifest.json").read_text())
        ledger_path = path / "provenance.jsonl"
        ledger = [json.loads(x) for x in ledger_path.read_text().splitlines()]
        ledger[0]["attempts"][0]["pair_sha256"] = "0" * 64
        body = b"".join(canonical(row) + b"\n" for row in ledger)
        ledger_path.write_bytes(body)
        receipt = self.mutate(path, receipt, lambda m: m["ledger"].update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
        with self.assertRaisesRegex(ValueError, "pair hash/seed"):
            self.load(path, receipt)

    @unittest.skipUnless(os.environ.get("IRISX_REARC_SOURCE"), "optional pinned official source is not downloaded by tests")
    @requires_linux("RE-ARC bounded generation requires POSIX SIGALRM/setitimer in a fresh worker")
    def test_official_source_real_verifier_and_deterministic_subprocess(self):
        root = os.environ["IRISX_REARC_SOURCE"]
        _, _, parents = c.inspect_source(root)
        self.assertEqual(len(parents), 400)
        config = c.GenerationConfig(examples_per_bundle=3)
        before = random.getstate()
        first = c._run_worker(root, TRAIN, 0, config)
        second = c._run_worker(root, TRAIN, 0, config)
        self.assertEqual(first, second)
        self.assertEqual(random.getstate(), before)
        self.assertEqual(len(first["pairs"]), 3)
        self.assertEqual(sum(e["status"] == "verified" for e in first["events"]), 3)


if __name__ == "__main__":
    unittest.main()
