"""Fast wheel controls; tools/distribution_check.py performs actual venv install."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def load_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


distribution = load_file("distribution_check_tests", ROOT / "tools/distribution_check.py")


class DistributionTests(unittest.TestCase):
    def test_installed_probe_uses_fresh_seed_reference_and_isolates_python_pollution(self):
        with tempfile.TemporaryDirectory(prefix="irisx-wheel-startup-") as temporary:
            root = Path(temporary)
            owned = root / "owned"
            foreign = root / "foreign"
            owned.mkdir()
            foreign.mkdir()
            sentinel = root / "foreign-imported"
            (owned / "irisx.py").write_text("VALUE = 'approved constant'\n", encoding="utf-8")
            malicious = "from pathlib import Path\nPath(" + repr(str(sentinel)) + ").write_text('foreign')\nraise RuntimeError('foreign import')\n"
            for name in ("irisx.py", "sitecustomize.py"):
                (foreign / name).write_text(malicious, encoding="utf-8")
            inherited = dict(os.environ, PYTHONPATH=str(foreign), PYTHONHOME=str(root / "absent-python-home"),
                             PYTHONUSERBASE=str(foreign), PYTHONHASHSEED="random", PYTHONSAFEPATH="0")
            environment = distribution.controlled_python_environment(inherited)
            self.assertEqual({key for key in environment if key.upper().startswith("PYTHON")},
                             {"PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE"})
            for optimize in (0, 1):
                with self.subTest(optimize=optimize):
                    # The expected hash is computed by this same interpreter in
                    # another fresh process, not a cross-version numeric constant.
                    reference = subprocess.run(
                        [sys.executable, "-B", *(["-O"] if optimize else []), "-c", distribution.HASH_REFERENCE],
                        cwd=root, env=environment, capture_output=True, text=True, check=True)
                    expected = json.loads(reference.stdout)
                    probes = []
                    for _ in range(2):
                        script = "import sys; sys.path.insert(0," + repr(str(owned)) + "); " + distribution.INSTALLED_PROBE
                        result = subprocess.run(distribution.controlled_python_command(sys.executable, "-c", script, optimize=optimize),
                                                cwd=foreign, env=environment, capture_output=True, text=True, check=True)
                        probe = json.loads(result.stdout)
                        self.assertEqual(distribution.validate_child_startup(probe["startup"], optimize=optimize), [])
                        self.assertEqual(probe["seed_hashes"], expected)
                        self.assertEqual(Path(probe["origin"]), owned / "irisx.py")
                        probes.append(probe["seed_hashes"])
                    self.assertEqual(probes[0], probes[1])
                    native_environment = dict(environment, PYTHONSAFEPATH="1", PYTHONNOUSERSITE="1")
                    support = subprocess.run([sys.executable, "-B", "-c", script], cwd=foreign,
                                             env=native_environment, capture_output=True, text=True, check=True)
                    native_probe = json.loads(support.stdout)
                    self.assertEqual(distribution.validate_child_startup(native_probe["startup"], optimize=0), [])
                    self.assertEqual(native_probe["seed_hashes"], expected)
            self.assertFalse(sentinel.exists())

    def stage(self, target: Path):
        distribution.stage_sources(ROOT, target)
        return load_file("isolated_irisx_backend", target / "tools/irisx_build_backend.py")

    def test_two_clean_roots_reproduce_and_record_every_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            reports = []
            for name in ("one", "two"):
                root = Path(temporary) / name
                backend = self.stage(root)
                package = root / "src/irisx/distribution_nested/inner"
                package.mkdir(parents=True)
                package.parent.joinpath("__init__.py").write_text("", encoding="utf-8")
                package.joinpath("__init__.py").write_text("", encoding="utf-8")
                package.joinpath("sample.py").write_bytes(b"VALUE = 'staging-only'\n")
                wheel = root / "wheels" / backend.build_wheel(str(root / "wheels"))
                reports.append(distribution.verify_wheel(wheel))
                with zipfile.ZipFile(wheel) as archive:
                    self.assertIn("irisx/distribution_nested/inner/sample.py", archive.namelist())
                    self.assertEqual(archive.read("irisx/distribution_nested/inner/sample.py"), b"VALUE = 'staging-only'\n")
            self.assertEqual(reports[0], reports[1])

    def test_product_wheel_excludes_tests_caches_and_unlisted_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stage"
            backend = self.stage(root)
            for relative in ("tests/__init__.py", "tests/private.py", "__pycache__/cached.py", "test_secret.py", "credentials.json", "evaluator-inputs.json", "private-data/answer.json"):
                target = root / "src/irisx" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("excluded", encoding="utf-8")
            wheel = root / "wheels" / backend.build_wheel(str(root / "wheels"))
            distribution.verify_wheel(wheel)
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
                self.assertFalse(any("distribution_nested" in name for name in names))
                license_name = "irisx/licenses/NeMo-RL-LICENSE.txt"
                self.assertEqual(archive.read(license_name), (ROOT / "src" / license_name).read_bytes())

    def test_missing_required_module_or_license_fails(self):
        for relative in ("cli.py", "__init__.py", "licenses/NeMo-RL-LICENSE.txt"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "stage"
                backend = self.stage(root)
                (root / "src/irisx" / relative).unlink()
                with self.assertRaisesRegex(ValueError, "missing or unsafe"):
                    backend.build_wheel(str(root / "wheels"))

    def test_wheel_path_traversal_and_case_collisions_fail(self):
        backend = load_file("current_irisx_backend", ROOT / "tools/irisx_build_backend.py")
        for name in ("../escape.py", "/absolute.py", "irisx/../escape.py", "irisx//empty.py", "C:/drive.py", "irisx\\escape.py"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(ValueError, "unsafe wheel member"):
                    backend._write_wheel(temporary, {name: b"bad"})
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "case collision"):
                backend._write_wheel(temporary, {"irisx/A.py": b"a", "irisx/a.py": b"b"})

    def test_record_cannot_be_injected(self):
        backend = load_file("current_irisx_backend", ROOT / "tools/irisx_build_backend.py")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "RECORD is reserved"):
                backend._write_wheel(temporary, {f"{backend.DIST_INFO}/RECORD": b"forged"})

    def test_linked_source_fails_without_following_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stage"
            backend = self.stage(root)
            outside = Path(temporary) / "external.py"
            outside.write_text("not a product source", encoding="utf-8")
            link = root / "src/irisx/linked.py"
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"platform cannot create symlinks: {error}")
            with self.assertRaisesRegex(ValueError, "linked build path"):
                backend.build_wheel(str(root / "wheels"))

    def test_record_rejects_tampered_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "stage"
            backend = self.stage(root)
            wheel = root / "wheels" / backend.build_wheel(str(root / "wheels"))
            with zipfile.ZipFile(wheel) as original:
                members = {name: original.read(name) for name in original.namelist()}
            members["irisx/__init__.py"] += b"\n# changed\n"
            with zipfile.ZipFile(wheel, "w") as changed:
                for name, data in members.items():
                    changed.writestr(name, data)
            with self.assertRaisesRegex(ValueError, "RECORD integrity mismatch"):
                distribution.verify_wheel(wheel)

    def test_existing_output_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            sentinel = target / "sentinel"
            sentinel.write_bytes(b"preserve")
            with self.assertRaisesRegex(ValueError, "output already exists"):
                distribution.check(target)
            self.assertEqual(sentinel.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()
