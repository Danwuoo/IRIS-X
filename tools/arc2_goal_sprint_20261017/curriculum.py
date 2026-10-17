"""Offline, verifier-backed RE-ARC bundles with fixed parent-level admission.

This module neither downloads source nor reads PUBLIC query answers. Production
admission is bound to the existing load_data receipt and its pinned 800/200
partition. The explicit fixture mode is never accepted by production consumers.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile

from src.irisx.arc_nvarc_data import known_variant_group
from tools.arc2_goal_sprint_20261017.data import canonical, digest, load_data, valid_grid

FORMAT = "irisx-clean-rearc-curriculum-v1"
SOURCE_URL = "https://github.com/michaelhodel/re-arc"
SOURCE_COMMIT = "e5b7f1d06362a76f9d3b8c25154ff1fafca897ce"
SOURCE_FILES = {
    "LICENSE": "60ea7c0edc4c765357257e31ad7c5f7d3ba7007329703d1fcfc3abbcbbd36efd",
    "generators.py": "1f598cb13c9c7b223181ab35485ca77d9079b600ee3baef1bce750db71248726",
    "verifiers.py": "e11c1ceed68ddb87fa544e3504f06d677c59698669a680e8124717f7703d80a1",
    "dsl.py": "c60faf5730a966fc1689c08bc96794cd97fd0311b8036e0f9b0c80e2d12f0f11",
    "utils.py": "48e11e45f804a37fcb0e62005c879ece7d5f0e1593d3fd53f5f978d31666540a",
}
PINNED_ADMISSION = {
    "training_manifest_sha256": "a4b9da04d8690c57a3d0855553989fa055c5b9283ffc1784fe99413c8d1cb9d5",
    "train_ids_digest": "sha256:e22c735e09d7bca513eebe1406617ee4697f316373aaac3b56041057ef0a29e1",
    "dev_ids_digest": "sha256:2543b56aebbfc7f8cec9447b5f30b06be9038529704e08c44ffdcb42762ae277",
    "public_digest": "sha256:93d3e1b76403937ce5424ae507a37d62a94c0d0e74c8fa01314c0e5572061d98",
}
PINNED_PROTECTED_IDS_DIGEST = "sha256:de177061609276f360f78795a498f7105922bd672581eb629d64ddbe19cf020f"
ID_RE = re.compile(r"[0-9a-f]{8}\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
REARC_LICENSE_TEXT = """MIT License

Copyright (c) 2024 Michael Hodel

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _ids(values):
    result = frozenset(values)
    if not result or any(not isinstance(x, str) or not ID_RE.fullmatch(x) for x in result):
        raise ValueError("nonempty eight-hex-digit parent IDs required")
    return result


def _pair(raw):
    if not isinstance(raw, dict) or set(raw) != {"input", "output"}:
        raise ValueError("exact input/output example required")
    pair = {k: [list(row) for row in raw[k]] for k in ("input", "output")}
    if not all(valid_grid(v) for v in pair.values()):
        raise ValueError("invalid generated grid: require integer colors 0..9 and 1..30 dimensions")
    return pair


def _variant(pairs):
    return known_variant_group({"train": pairs, "test": []})


@dataclass(frozen=True)
class Admission:
    """Construct with from_load_data, never by resplitting generated descendants."""

    training_ids: frozenset
    dev_ids: frozenset
    public_ids: frozenset
    public_variants: frozenset
    public_pair_variants: frozenset
    binding: dict
    fixture: bool = False

    @classmethod
    def from_load_data(cls, training, dev, public, receipt, *, fixture=False):
        train_ids, dev_ids, public_ids = _ids(training), _ids(dev), _ids(public)
        if train_ids & (dev_ids | public_ids) or dev_ids & public_ids:
            raise ValueError("training/dev/PUBLIC parents must be disjoint")
        # Reject before hashing: query answers must not even enter our provenance.
        for task in public.values():
            if (not isinstance(task, dict) or set(task) != {"train", "test"}
                    or not task["train"] or not task["test"]
                    or any(not isinstance(t, dict) or set(t) != {"input"} for t in task["test"])):
                raise ValueError("solver-only PUBLIC challenges required; query answers forbidden")
            for pair in task["train"]:
                _pair(pair)
            if not all(valid_grid(t["input"]) for t in task["test"]):
                raise ValueError("invalid PUBLIC query")
        expected = {"training_tasks": len(train_ids), "dev_tasks": len(dev_ids),
                    "train_ids_digest": digest(sorted(train_ids)), "dev_ids_digest": digest(sorted(dev_ids)),
                    "public_digest": digest(public), "training_test_fields_used": False}
        if any(receipt.get(k) != v for k, v in expected.items()):
            raise ValueError("load_data receipt does not match actual admitted inputs")
        if not fixture:
            if any(receipt.get(k) != v for k, v in PINNED_ADMISSION.items()):
                raise ValueError("production requires the pinned historical 800/200 load_data admission")
            if (len(train_ids), len(dev_ids), len(public_ids), sum(len(t["test"]) for t in public.values())) != (800, 200, 120, 167):
                raise ValueError("complete 800/200 parents and PUBLIC120/167 required")
        variants = frozenset(_variant(t["train"]) for t in public.values())
        pair_variants = frozenset(_variant([p]) for t in public.values() for p in t["train"])
        binding = {**expected, "training_manifest_sha256": receipt.get("training_manifest_sha256"),
                   "protected_ids_digest": digest(sorted(public_ids)),
                   "receipt_digest": digest(receipt),
                   "public_variants_digest": digest(sorted(variants)),
                   "public_pair_variants_digest": digest(sorted(pair_variants))}
        result = cls(train_ids, dev_ids, public_ids, variants, pair_variants, binding, fixture)
        result.validate()
        return result

    def validate(self):
        train, dev, public = _ids(self.training_ids), _ids(self.dev_ids), _ids(self.public_ids)
        if train & (dev | public) or dev & public or type(self.fixture) is not bool:
            raise ValueError("invalid current admission sets/mode")
        expected = {"training_tasks": len(train), "dev_tasks": len(dev),
                    "train_ids_digest": digest(sorted(train)), "dev_ids_digest": digest(sorted(dev)),
                    "protected_ids_digest": digest(sorted(public)),
                    "public_variants_digest": digest(sorted(self.public_variants)),
                    "public_pair_variants_digest": digest(sorted(self.public_pair_variants)),
                    "training_test_fields_used": False}
        if any(self.binding.get(k) != v for k, v in expected.items()):
            raise ValueError("current Admission ID-set/variant binding differs")
        if not self.fixture and (any(self.binding.get(k) != v for k, v in PINNED_ADMISSION.items())
                                 or self.binding["protected_ids_digest"] != PINNED_PROTECTED_IDS_DIGEST
                                 or (len(train), len(dev), len(public)) != (800, 200, 120)):
            raise ValueError("current admission does not match pinned production split")

    def admit_parent(self, parent):
        if parent in self.dev_ids or parent in self.public_ids or parent not in self.training_ids:
            raise ValueError(f"parent {parent!r} is not an admitted training parent")

    def check_pairs(self, pairs):
        if any(_variant([p]) in self.public_pair_variants for p in pairs):
            raise ValueError("known PUBLIC demonstration pair variant")
        if _variant(pairs) in self.public_variants:
            raise ValueError("known PUBLIC demonstration task variant")


def load_admission(training_root, manifest_path, public_path):
    """Production entry point: actually verify source bytes through load_data."""
    loaded = load_data(training_root, manifest_path, public_path,
                       expected_manifest_sha256=PINNED_ADMISSION["training_manifest_sha256"])
    return Admission.from_load_data(*loaded)


@dataclass(frozen=True)
class GenerationConfig:
    seed: int = 20261017
    bundles_per_parent: int = 1
    examples_per_bundle: int = 4
    max_attempts_per_bundle: int = 40
    attempt_timeout_seconds: float = 2.0
    bundle_timeout_seconds: float = 30.0
    difficulty_lower: float = 0.0
    difficulty_upper: float = 1.0

    def validate(self):
        for name, low, high in (("seed", 0, 2**63 - 1), ("bundles_per_parent", 1, 16),
                                ("examples_per_bundle", 3, 6), ("max_attempts_per_bundle", 3, 256)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"invalid bounded {name}")
        if self.max_attempts_per_bundle < self.examples_per_bundle:
            raise ValueError("attempt budget below bundle size")
        for name, low, high in (("attempt_timeout_seconds", 0.01, 30.0),
                                ("bundle_timeout_seconds", 0.1, 300.0)):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"invalid bounded {name}")
        if self.attempt_timeout_seconds > self.bundle_timeout_seconds:
            raise ValueError("attempt timeout exceeds bundle timeout")
        if (type(self.difficulty_lower) not in (int, float) or type(self.difficulty_upper) not in (int, float)
                or not 0 <= self.difficulty_lower <= self.difficulty_upper <= 1):
            raise ValueError("difficulty bounds must lie in [0,1]")


def inspect_source(source_root):
    """Read/hash only. Neither import upstream nor accept moving branch identities."""
    root = Path(source_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("regular local source directory required")
    bodies = {}
    for name, expected in SOURCE_FILES.items():
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"regular pinned source required: {name}")
        body = path.read_bytes()
        if _sha(body) != expected:
            raise ValueError(f"pinned RE-ARC source digest differs: {name}")
        bodies[name] = body.decode("utf-8")
    functions = {}
    for file, prefix in (("generators.py", "generate_"), ("verifiers.py", "verify_")):
        source = bodies[file]
        lines = source.splitlines(keepends=True)
        functions[file] = {}
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith(prefix):
                # Upstream definitions are ASCII and start in column zero. Slice
                # pre-split lines once, rather than rescan the 600 KiB file 400 times.
                segment = "".join(lines[node.lineno - 1:node.end_lineno - 1]) + lines[node.end_lineno - 1][:node.end_col_offset]
                functions[file][node.name[len(prefix):]] = {"node": node, "sha256": _sha(segment.encode("utf-8"))}
    parents = set(functions["generators.py"]) & set(functions["verifiers.py"])
    if len(parents) != 400:
        raise ValueError("complete pinned generator/verifier inventory required")
    return bodies, functions, parents


def _implementation_hashes():
    root = Path(__file__).resolve().parents[2]
    return {name: _sha((root / name).read_bytes()) for name in (
        "tools/arc2_goal_sprint_20261017/curriculum.py", "tools/arc2_goal_sprint_20261017/data.py",
        "src/irisx/arc_nvarc_data.py", "src/irisx/canonical.py", "src/irisx/errors.py")}


def _upstream_record():
    return {"repository": SOURCE_URL, "commit": SOURCE_COMMIT, "license": "MIT",
            "files_sha256": dict(SOURCE_FILES),
            "execution": "exact selected generator/verifier AST, exact DSL and unifint; no plotting/main imports"}


def _source_record():
    return {"implementation_sha256": _implementation_hashes(), **_upstream_record()}


def _compile_source(bodies, functions, parent):
    # Only these hash-verified upstream definitions execute. In particular, never
    # call upstream main/demo/fix_bugs, which can read original tasks/test answers.
    namespace = {"__builtins__": __builtins__, "__name__": "irisx_pinned_rearc"}
    dsl = ast.parse(bodies["dsl.py"])
    exec(compile(dsl, "re-arc/dsl.py", "exec"), namespace)
    utils = ast.parse(bodies["utils.py"])
    selected = [n for n in utils.body if
                (isinstance(n, ast.ImportFrom) and n.module == "random")
                or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "rng" for t in n.targets))
                or (isinstance(n, ast.FunctionDef) and n.name == "unifint")]
    exec(compile(ast.Module(body=selected, type_ignores=[]), "re-arc/utils.py", "exec"), namespace)
    for file in ("generators.py", "verifiers.py"):
        node = functions[file][parent]["node"]
        exec(compile(ast.Module(body=[node], type_ignores=[]), "re-arc/" + file, "exec"), namespace)
    return namespace["generate_" + parent], namespace["verify_" + parent], namespace


class _AttemptTimeout(BaseException):
    pass


def _alarm(_signum, _frame):
    raise _AttemptTimeout()


def _attempt_seed(seed, parent, bundle_index, attempt):
    return int(_sha(canonical([seed, parent, bundle_index, attempt]))[:16], 16)


def _generate_worker(source_root, parent, bundle_index, config):
    config.validate()
    if os.environ.get("PYTHONHASHSEED") != "0" or not hasattr(signal, "setitimer"):
        raise ValueError("worker requires fresh PYTHONHASHSEED=0 and POSIX interval timers")
    bodies, functions, parents = inspect_source(source_root)
    if parent not in parents:
        raise ValueError("no pinned generator/verifier for parent")
    generator, verifier, namespace = _compile_source(bodies, functions, parent)
    signal.signal(signal.SIGALRM, _alarm)
    pairs, events, seen_inputs = [], [], set()
    for attempt in range(config.max_attempts_per_bundle):
        seed = _attempt_seed(config.seed, parent, bundle_index, attempt)
        random.seed(seed)
        namespace["rng"] = []
        event = {"attempt": attempt, "seed": seed}
        try:
            signal.setitimer(signal.ITIMER_REAL, config.attempt_timeout_seconds)
            pair = _pair(generator(config.difficulty_lower, config.difficulty_upper))
            event["pair_sha256"] = _sha(canonical(pair))
            result = [list(row) for row in verifier(tuple(tuple(row) for row in pair["input"]))]
            if not valid_grid(result) or result != pair["output"]:
                event["status"] = "verifier_mismatch"
            elif pair["input"] == pair["output"]:
                event["status"] = "degenerate_identity"
            elif digest(pair["input"]) in seen_inputs:
                event["status"] = "duplicate_input"
            else:
                event["status"] = "verified"
                seen_inputs.add(digest(pair["input"]))
                pairs.append(pair)
        except _AttemptTimeout:
            event["status"] = "attempt_timeout"
        except Exception as exc:
            event["status"] = "generator_or_verifier_error"
            event["error_type"] = type(exc).__name__
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
        events.append(event)
        if len(pairs) == config.examples_per_bundle:
            break
    return {"pairs": pairs, "events": events,
            "generator_sha256": functions["generators.py"][parent]["sha256"],
            "verifier_sha256": functions["verifiers.py"][parent]["sha256"]}


def _run_worker(source_root, parent, bundle_index, config):
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    # A fresh process fixes hashing and isolates random state. This is a bounded
    # trusted-source worker, not a claimed OS/security or evaluator sandbox.
    command = [sys.executable, "-m", "tools.arc2_goal_sprint_20261017.curriculum", "_worker",
               str(Path(source_root).resolve()), parent, str(bundle_index), canonical(asdict(config)).decode()]
    try:
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=config.bundle_timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        return {"pairs": [], "events": [{"status": "bundle_timeout"}]}
    if result.returncode != 0:
        return {"pairs": [], "events": [{"status": "worker_error", "returncode": result.returncode}]}
    if len(result.stdout) > 256 * 1024:
        raise ValueError("oversize generator worker result")
    return json.loads(result.stdout)


def _write_json(path, value):
    body = canonical(value) + b"\n"
    path.write_bytes(body)
    return {"bytes": len(body), "sha256": _sha(body)}


def _admission_record(admission):
    return {"binding": admission.binding, "train_parent_ids": sorted(admission.training_ids),
            "dev_parent_ids": sorted(admission.dev_ids), "protected_public_ids": sorted(admission.public_ids),
            "descendant_split": "inherit_admitted_training_parent_only"}


def prepare_curriculum(source_root, output_root, *, admission, parent_ids=None, config=None):
    """Write a new immutable compact bundle directory; return its external seal.

    The parent sampler should choose a training parent first, then choose that
    parent's original demonstrations or one generated bundle. Never resplit or
    uniformly sample the union of parents and synthetic descendants.
    """
    admission.validate()
    config = config or GenerationConfig()
    config.validate()
    bodies, functions, available = inspect_source(source_root)
    source_binding = _source_record()
    parents = sorted(admission.training_ids & available if parent_ids is None else set(parent_ids))
    if not parents or len(parents) * config.bundles_per_parent > 5000:
        raise ValueError("nonempty bounded requested parent inventory required")
    for parent in parents:
        admission.admit_parent(parent)
        if parent not in available:
            raise ValueError(f"no pinned generator and verifier for {parent}")
    root = Path(output_root)
    if root.exists() or root.is_symlink():
        raise ValueError("output directory already exists; immutable identities cannot be overwritten")
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".curriculum-", dir=root.parent))
    bundles, ledger, seen = [], [], set()
    try:
        (stage / "bundles").mkdir()
        for parent in parents:
            for index in range(config.bundles_per_parent):
                if _source_record() != source_binding:
                    raise ValueError("preparation implementation changed during generation")
                result = _run_worker(source_root, parent, index, config)
                event = {"parent_id": parent, "bundle_index": index, "attempts": result["events"]}
                pairs = [_pair(p) for p in result["pairs"]]
                if len(pairs) != config.examples_per_bundle:
                    event["status"] = "insufficient_verified_examples"
                    ledger.append(event)
                    continue
                try:
                    admission.check_pairs(pairs)
                except ValueError:
                    event["status"] = "public_variant_rejected"
                    ledger.append(event)
                    continue
                variant = _variant(pairs)
                if variant in seen:
                    event["status"] = "duplicate_bundle_rejected"
                    ledger.append(event)
                    continue
                seen.add(variant)
                provenance = {"source_commit": SOURCE_COMMIT, "generator": "generate_" + parent,
                              "verifier": "verify_" + parent,
                              "generator_sha256": functions["generators.py"][parent]["sha256"],
                              "verifier_sha256": functions["verifiers.py"][parent]["sha256"],
                              "seed": config.seed, "bundle_index": index,
                              "example_seeds": [e["seed"] for e in result["events"] if e["status"] == "verified"]}
                if (result.get("generator_sha256") != provenance["generator_sha256"]
                        or result.get("verifier_sha256") != provenance["verifier_sha256"]):
                    raise ValueError("worker function provenance differs")
                task_id = f"rearc.{parent}.{index:03d}.{_sha(canonical(pairs))[:16]}"
                bundle = {"task_id": task_id, "parent_id": parent, "split": "train", "train": pairs,
                          "provenance": provenance}
                path = "bundles/" + task_id + ".json"
                row = {"path": path, "task_id": task_id, "parent_id": parent, "examples": len(pairs),
                       **_write_json(stage / path, bundle)}
                bundles.append(row)
                event.update(status="admitted", task_id=task_id, bundle_sha256=row["sha256"])
                ledger.append(event)
        if not bundles:
            raise ValueError("no complete clean verified bundles generated")
        ledger_body = b"".join(canonical(row) + b"\n" for row in ledger)
        (stage / "provenance.jsonl").write_bytes(ledger_body)
        license_body = bodies["LICENSE"].encode("utf-8")
        if _sha(license_body) != SOURCE_FILES["LICENSE"]:
            raise ValueError("pinned MIT license differs")
        (stage / "LICENSE").write_bytes(license_body)
        if _source_record() != source_binding:
            raise ValueError("preparation implementation changed during generation")
        manifest = {"format": FORMAT, "mode": "synthetic_fixture" if admission.fixture else "production",
                    "source": source_binding, "admission": _admission_record(admission),
                    "config": asdict(config), "python_version": list(sys.version_info[:3]), "python_hash_seed": 0,
                    "requested_parent_ids": parents, "bundles": bundles,
                    "ledger": {"path": "provenance.jsonl", "sha256": _sha(ledger_body), "bytes": len(ledger_body)},
                    "license": {"path": "LICENSE", "sha256": _sha(license_body), "bytes": len(license_body)},
                    "counts": {"bundles": len(bundles), "examples": sum(b["examples"] for b in bundles),
                               "parents": len({b["parent_id"] for b in bundles}),
                               "statuses": dict(sorted(Counter(e["status"] for e in ledger).items()))},
                    "deduplication": "known D4/color-renaming/demo-shuffle PUBLIC demonstration tasks and pairs",
                    "limitations": "Not a proof of semantic independence or generator correctness; no PUBLIC query answers read."}
        seal = _write_json(stage / "manifest.json", manifest)
        total_bytes = seal["bytes"] + len(ledger_body) + len(license_body) + sum(b["bytes"] for b in bundles)
        if total_bytes > MAX_ARTIFACT_BYTES:
            raise ValueError("bounded compact corpus byte limit exceeded")
        # Read the finished product through the same consumer checks before publishing it locally.
        load_curriculum(stage, admission=admission, expected_manifest_sha256=seal["sha256"],
                        allow_fixture=admission.fixture)
        os.rename(stage, root)
        return {"manifest_sha256": seal["sha256"], "artifact_bytes": total_bytes, **manifest["counts"]}
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _read_bound(root, name, row, *, limit=MAX_ARTIFACT_BYTES):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != name:
        raise ValueError("unsafe corpus member path")
    current = root
    for component in path.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError("corpus symlink forbidden")
    if not current.is_file() or current.stat().st_size > limit:
        raise ValueError("missing or oversized corpus member")
    body = current.read_bytes()
    if len(body) != row["bytes"] or _sha(body) != row["sha256"]:
        raise ValueError("corpus member bytes/hash differ")
    return body


def load_curriculum(root, *, admission, expected_manifest_sha256, expected_producer_hashes=None,
                    allow_fixture=False):
    """Verify sealed bytes and current lineage, returning {parent: [train-tasks]}.

    Requires the external manifest hash recorded when preparing/packaging. This
    never trusts a manifest to approve its own parent IDs or its own byte seal.
    Producer hashes remain sealed historical provenance, not an equality gate
    against unrelated current consumer code. Packages may additionally bind the
    exact expected_producer_hashes map; current admission/dedup always rerun.
    """
    admission.validate()
    root = Path(root)
    manifest_path = root / "manifest.json"
    if (root.is_symlink() or manifest_path.is_symlink() or not manifest_path.is_file()
            or manifest_path.stat().st_size > 8 * 1024 * 1024):
        raise ValueError("regular bounded corpus manifest required")
    raw = manifest_path.read_bytes()
    if not SHA_RE.fullmatch(expected_manifest_sha256) or _sha(raw) != expected_manifest_sha256:
        raise ValueError("external corpus manifest seal differs")
    manifest = json.loads(raw)
    if raw != canonical(manifest) + b"\n" or manifest.get("format") != FORMAT:
        raise ValueError("canonical curriculum manifest required")
    expected_mode = "synthetic_fixture" if admission.fixture else "production"
    if manifest.get("mode") != expected_mode or (admission.fixture and not allow_fixture):
        raise ValueError("fixture corpus/admission forbidden in production")
    if not admission.fixture and any(admission.binding.get(k) != v for k, v in PINNED_ADMISSION.items()):
        raise ValueError("current admission does not match pinned production split")
    source = dict(manifest.get("source", {}))
    producer_hashes = source.pop("implementation_sha256", None)
    if (not isinstance(producer_hashes, dict) or not producer_hashes
            or any(not isinstance(k, str) or not isinstance(v, str) or not SHA_RE.fullmatch(v)
                   for k, v in producer_hashes.items())):
        raise ValueError("sealed producer implementation inventory required")
    if expected_producer_hashes is not None and producer_hashes != expected_producer_hashes:
        raise ValueError("explicit producer implementation expectation differs")
    if manifest.get("admission") != _admission_record(admission) or source != _upstream_record():
        raise ValueError("current admission or pinned generator source differs")
    config = GenerationConfig(**manifest["config"])
    config.validate()
    requested = manifest["requested_parent_ids"]
    if not requested or requested != sorted(set(requested)):
        raise ValueError("unique ordered requested parents required")
    for parent in requested:
        admission.admit_parent(parent)
    rows = manifest["bundles"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 5000:
        raise ValueError("bounded nonempty bundle inventory required")
    by_parent, seen_paths, seen_tasks, seen_variants = {}, set(), set(), set()
    license_row = manifest["license"]
    if license_row["path"] != "LICENSE" or license_row["sha256"] != SOURCE_FILES["LICENSE"]:
        raise ValueError("pinned MIT license inventory required")
    license_body = _read_bound(root, "LICENSE", license_row, limit=4096)
    total_bytes = len(raw) + len(license_body)
    for row in rows:
        parent, task_id, name = row["parent_id"], row["task_id"], row["path"]
        admission.admit_parent(parent)
        if parent not in requested or name in seen_paths or task_id in seen_tasks:
            raise ValueError("duplicate or unrequested bundle identity")
        if name != "bundles/" + task_id + ".json" or not re.fullmatch(r"rearc\.[0-9a-f]{8}\.[0-9]{3}\.[0-9a-f]{16}", task_id):
            raise ValueError("invalid bundle identity/path")
        body = _read_bound(root, name, row, limit=128 * 1024)
        total_bytes += len(body)
        bundle = json.loads(body)
        if body != canonical(bundle) + b"\n" or set(bundle) != {"task_id", "parent_id", "split", "train", "provenance"}:
            raise ValueError("canonical strict task bundle required")
        if bundle["parent_id"] != parent or bundle["task_id"] != task_id or bundle["split"] != "train":
            raise ValueError("bundle parent identity differs")
        pairs = [_pair(p) for p in bundle["train"]]
        if len(pairs) != config.examples_per_bundle or len(pairs) != row["examples"]:
            raise ValueError("complete 3..6 example bundle required")
        if (len({digest(p["input"]) for p in pairs}) != len(pairs)
                or any(p["input"] == p["output"] for p in pairs)):
            raise ValueError("duplicate input or degenerate generated example")
        admission.check_pairs(pairs)
        variant = _variant(pairs)
        if variant in seen_variants:
            raise ValueError("duplicate invariant bundle")
        provenance = bundle["provenance"]
        index = provenance["bundle_index"]
        if (type(index) is not int or not 0 <= index < config.bundles_per_parent
                or provenance["source_commit"] != SOURCE_COMMIT or provenance["seed"] != config.seed
                or provenance["generator"] != "generate_" + parent or provenance["verifier"] != "verify_" + parent
                or not SHA_RE.fullmatch(provenance["generator_sha256"])
                or not SHA_RE.fullmatch(provenance["verifier_sha256"])
                or len(provenance["example_seeds"]) != len(pairs)
                or task_id != f"rearc.{parent}.{index:03d}.{_sha(canonical(pairs))[:16]}"):
            raise ValueError("invalid bundle generator/seed provenance")
        seen_paths.add(name)
        seen_tasks.add(task_id)
        seen_variants.add(variant)
        by_parent.setdefault(parent, []).append(bundle)
    ledger_row = manifest["ledger"]
    if ledger_row["path"] != "provenance.jsonl":
        raise ValueError("fixed provenance ledger path required")
    ledger_body = _read_bound(root, "provenance.jsonl", ledger_row, limit=32 * 1024 * 1024)
    total_bytes += len(ledger_body)
    ledger = [json.loads(line) for line in ledger_body.splitlines()]
    if ledger_body != b"".join(canonical(row) + b"\n" for row in ledger):
        raise ValueError("canonical provenance ledger required")
    expected_slots = {(p, i) for p in requested for i in range(config.bundles_per_parent)}
    if len(ledger) != len(expected_slots) or {(e["parent_id"], e["bundle_index"]) for e in ledger} != expected_slots:
        raise ValueError("complete attempted parent/bundle ledger required")
    admitted = {e["task_id"]: e for e in ledger if e["status"] == "admitted"}
    if set(admitted) != seen_tasks:
        raise ValueError("admitted ledger and bundle inventory differ")
    row_by_task = {r["task_id"]: r for r in rows}
    for parent, tasks in by_parent.items():
        for bundle in tasks:
            event = admitted[bundle["task_id"]]
            successes = [a for a in event["attempts"] if a["status"] == "verified"]
            if (event["parent_id"] != parent or event["bundle_index"] != bundle["provenance"]["bundle_index"]
                    or event["bundle_sha256"] != row_by_task[bundle["task_id"]]["sha256"]
                    or len(successes) != len(bundle["train"])
                    or [e["seed"] for e in successes] != bundle["provenance"]["example_seeds"]):
                raise ValueError("verified example ledger differs")
            for event_pair, pair in zip(successes, bundle["train"]):
                if (event_pair["pair_sha256"] != _sha(canonical(pair))
                        or event_pair["seed"] != _attempt_seed(config.seed, parent,
                            bundle["provenance"]["bundle_index"], event_pair["attempt"])):
                    raise ValueError("verified pair hash/seed differs")
    counts = {"bundles": len(rows), "examples": sum(r["examples"] for r in rows), "parents": len(by_parent),
              "statuses": dict(sorted(Counter(e["status"] for e in ledger).items()))}
    if counts != manifest["counts"] or total_bytes > MAX_ARTIFACT_BYTES:
        raise ValueError("corpus totals differ or exceed compact bound")
    actual_files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()}
    if actual_files != seen_paths | {"manifest.json", "provenance.jsonl", "LICENSE"}:
        raise ValueError("unexpected corpus members")
    return by_parent, {"manifest_sha256": expected_manifest_sha256, "artifact_bytes": total_bytes, **counts}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "_worker":
        _, root, parent, index, raw = argv
        print(canonical(_generate_worker(root, parent, int(index), GenerationConfig(**json.loads(raw)))).decode())
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate"))
    parser.add_argument("--training-root", required=True)
    parser.add_argument("--training-manifest", required=True)
    parser.add_argument("--public-challenges", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-root")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--producer-hashes", help="optional JSON file containing package-pinned producer hash map")
    parser.add_argument("--parents", nargs="+")
    parser.add_argument("--seed", type=int, default=20261017)
    parser.add_argument("--bundles-per-parent", type=int, default=1)
    parser.add_argument("--examples-per-bundle", type=int, default=4)
    args = parser.parse_args(argv)
    admission = load_admission(args.training_root, args.training_manifest, args.public_challenges)
    if args.command == "prepare":
        if not args.source_root:
            parser.error("prepare requires --source-root (already materialized pinned source)")
        result = prepare_curriculum(args.source_root, args.output, admission=admission,
                                    parent_ids=args.parents, config=GenerationConfig(seed=args.seed,
                                    bundles_per_parent=args.bundles_per_parent, examples_per_bundle=args.examples_per_bundle))
    else:
        if not args.manifest_sha256:
            parser.error("validate requires the external --manifest-sha256")
        expected_producer = None if args.producer_hashes is None else json.loads(Path(args.producer_hashes).read_bytes())
        _, result = load_curriculum(args.output, admission=admission, expected_manifest_sha256=args.manifest_sha256,
                                    expected_producer_hashes=expected_producer)
    print(canonical(result).decode())


if __name__ == "__main__":
    main()
