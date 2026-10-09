"""Synthetic tiny-wheel CPU tests; these do not verify the real CUDA closure."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import platform
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from tools import arc_next_offline_environment as offline


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def tiny_wheel(directory, name, version, requires=(), *, tag="py3-none-any", extra_members=None):
    distribution = name.replace("-", "_")
    stem = distribution + "-" + version
    filename = stem + "-" + tag + ".whl"
    metadata = "Metadata-Version: 2.1\nName: " + name + "\nVersion: " + version + "\n"
    metadata += "".join("Requires-Dist: " + requirement + "\n" for requirement in requires)
    members = {
        distribution + "/__init__.py": "__version__ = " + repr(version) + "\n",
        stem + ".dist-info/METADATA": metadata,
        stem + ".dist-info/WHEEL": "Wheel-Version: 1.0\nGenerator: irisx-cpu-test\nRoot-Is-Purelib: true\nTag: " + tag + "\n",
    }
    members.update(extra_members or {})
    record = io.StringIO()
    rows = csv.writer(record, lineterminator="\n")
    for path, content in members.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content.encode()).digest()).decode().rstrip("=")
        rows.writerow([path, "sha256=" + digest, len(content.encode())])
    rows.writerow([stem + ".dist-info/RECORD", "", ""])
    members[stem + ".dist-info/RECORD"] = record.getvalue()
    target = directory / filename
    with zipfile.ZipFile(target, "w") as archive:
        for path, content in members.items():
            archive.writestr(path, content)
    return target


class Wheelhouse:
    """Fixture anchors fake wheels explicitly; no official hashes are impersonated."""
    def __init__(self, root):
        self.root = root / "wheelhouse"
        self.root.mkdir()
        self.wheels = self.root / "wheels"
        self.wheels.mkdir()
        self.source = root / "synthetic-source-lock.json"
        self.packages = {}
        for name, version in offline.CORE_VERSIONS.items():
            path = tiny_wheel(self.wheels, name, version,
                              requires=("tiny-leaf>=1",) if name == "transformers" else (),
                              tag="cp312-cp312-manylinux_2_28_x86_64" if name == "torch" else "py3-none-any")
            self.packages[name] = {"version": version, "wheels": [{"filename": path.name, "sha256": sha(path)}]}
        tiny_wheel(self.wheels, "tiny-leaf", "1.0")
        write_json(self.source, {"test_fixture": True, "proposed_training_environments": {
            "common_hf_bf16_lora": {"packages": self.packages}}})
        self.refresh()

    def refresh(self):
        inventory = {}
        lines = []
        versions = {}
        for path in sorted(self.wheels.glob("*.whl")):
            # Read metadata directly so tests can intentionally construct invalid inputs.
            with zipfile.ZipFile(path) as archive:
                member = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
                msg = offline.email.message_from_bytes(archive.read(member))
            name, version = offline._name(msg["Name"]), msg["Version"]
            inventory[path.name] = {"name": name, "version": version, "sha256": sha(path), "bytes": path.stat().st_size}
            lines.append(name + "==" + version + " --hash=sha256:" + sha(path))
            versions[name] = version
        (self.root / "requirements.lock").write_text("\n".join(lines) + "\n")
        write_json(self.root / "wheel-lock.json", {
            "format": "irisx/arc-next-offline-wheel-lock-v1", "source_lock_sha256": sha(self.source),
            "python": "3.12.1", "platform": "synthetic Linux x86_64 fixture",
            "files": inventory, "versions": versions,
            "requirements_sha256": sha(self.root / "requirements.lock"),
            "all_transitive_wheels_materialized": True, "gpu_runtime_verified": False,
        })

    def update_requirement_hash(self):
        path = self.root / "wheel-lock.json"
        value = json.loads(path.read_text())
        value["requirements_sha256"] = sha(self.root / "requirements.lock")
        write_json(path, value)


class OfflineEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.fixture = Wheelhouse(self.base)

    def validate(self, **kwargs):
        return offline.validate_wheelhouse(self.fixture.source, self.fixture.root, **kwargs)

    def test_import_and_disabled_switch_are_inert(self):
        with mock.patch.object(offline.subprocess, "run", side_effect=AssertionError("subprocess forbidden")):
            self.assertEqual(offline.install_offline("absent", "absent", "absent")["status"], "disabled")
            self.assertEqual(offline.migrate_offline_guard("absent", "absent", "absent")["status"], "disabled")
        for enabled in ("False", 0, 1):
            with self.assertRaises(offline.OfflineEnvironmentError):
                offline.migrate_offline_guard("absent", "absent", "absent", enabled=enabled)
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "exact expected"):
            offline.migrate_offline_guard("absent", "absent", "absent", enabled=True)
        with self.assertRaises(offline.OfflineEnvironmentError):
            offline.install_offline("absent", "absent", "absent", enabled="False")
        with self.assertRaises(offline.OfflineEnvironmentError):
            self.validate(check_runtime="False")

    def test_static_check_never_claims_real_closure(self):
        with mock.patch.object(offline.subprocess, "run", side_effect=AssertionError("subprocess forbidden")):
            result = self.validate(check_runtime=False)
        self.assertFalse(result["complete_transitive_lock_verified"])
        self.assertFalse(result["gpu_runtime_verified"])
        self.assertEqual(result["wheel_count"], 9)

    def test_wrong_host_rejected_before_resolution(self):
        # Each invalid-host case starts from the same complete synthetic target,
        # rather than inheriting unrelated Python/OS facts from the CI runner.
        with mock.patch.object(offline.platform, "python_implementation", return_value="CPython"), \
             mock.patch.object(offline.sys, "version_info", (3, 12)), \
             mock.patch.object(offline.platform, "system", return_value="Linux"), \
             mock.patch.object(offline.platform, "machine", return_value="x86_64"), \
             mock.patch.object(offline.platform, "libc_ver", return_value=("glibc", "2.28")):
            self.assertEqual(offline._runtime()["glibc"], "2.28")
            with mock.patch.object(offline.subprocess, "run", side_effect=AssertionError("Resolution must not start")):
                with self.subTest(host="wrong architecture"), \
                     mock.patch.object(offline.platform, "machine", return_value="aarch64"):
                    with self.assertRaises(offline.RuntimeCompatibilityError) as caught:
                        self.validate()
                    self.assert_runtime_rejection(caught.exception, "machine")
                with self.subTest(host="old glibc"), \
                     mock.patch.object(offline.platform, "libc_ver", return_value=("glibc", "2.27")):
                    with self.assertRaises(offline.RuntimeCompatibilityError) as caught:
                        self.validate()
                    self.assert_runtime_rejection(caught.exception, "glibc_minimum")
                with self.subTest(host="wrong Python"), \
                     mock.patch.object(offline.sys, "version_info", (3, 11)):
                    with self.assertRaises(offline.RuntimeCompatibilityError) as caught:
                        self.validate()
                    self.assert_runtime_rejection(caught.exception, "python_major_minor")

    def assert_runtime_rejection(self, error, mismatch):
        diagnostic = error.diagnostic
        self.assertFalse(diagnostic["compatible"])
        self.assertEqual(diagnostic["mismatches"], [mismatch])
        self.assertIn("no installation or training started", str(error))
        for key in ("network_calls", "install_calls", "gpu_calls"):
            self.assertEqual(diagnostic[key], 0)

    def test_unpinned_and_embedded_pip_options_rejected(self):
        for line in ["tiny-leaf>=1", "--index-url https://example.invalid", "-r elsewhere.txt",
                     "tiny-leaf @ https://example.invalid/a.whl", "tiny-leaf==1.0 --hash=sha256:" + "0" * 64]:
            with self.subTest(line=line):
                self.fixture.refresh()
                (self.fixture.root / "requirements.lock").write_text(line + "\n")
                self.fixture.update_requirement_hash()
                with self.assertRaises(offline.OfflineEnvironmentError):
                    self.validate(check_runtime=False)

    def test_modified_or_missing_wheel_and_requirement_rejected(self):
        wheel = next(self.fixture.wheels.glob("tiny_leaf*.whl"))
        original = wheel.read_bytes()
        wheel.write_bytes(original + b"modified")
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "bytes/hash"):
            self.validate(check_runtime=False)
        wheel.write_bytes(original)
        wheel.unlink()
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Missing local path"):
            self.validate(check_runtime=False)

    def test_core_removed_from_self_consistent_manifest_is_rejected(self):
        next(self.fixture.wheels.glob("torch-*.whl")).unlink()
        self.fixture.refresh()
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Missing pinned core"):
            self.validate(check_runtime=False)

    def test_self_consistent_core_change_still_fails_source_anchor(self):
        wheel = next(self.fixture.wheels.glob("torch-*.whl"))
        with zipfile.ZipFile(wheel, "a") as archive:
            archive.writestr("extra.py", "# changed")
        self.fixture.refresh()
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "source-pinned"):
            self.validate(check_runtime=False)

    def test_extra_nonwheel_or_unlocked_wheel_rejected(self):
        for name in ("sdist.tar.gz", "stray.txt"):
            path = self.fixture.wheels / name
            path.write_text("unexpected")
            with self.assertRaisesRegex(offline.OfflineEnvironmentError, "exactly the locked wheels"):
                self.validate(check_runtime=False)
            path.unlink()
        tiny_wheel(self.fixture.wheels, "unlocked", "1.0")
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "exactly the locked wheels"):
            self.validate(check_runtime=False)

    def test_symlinks_and_manifest_traversal_rejected(self):
        wheel = next(self.fixture.wheels.glob("tiny_leaf*.whl"))
        saved = self.base / wheel.name
        wheel.replace(saved)
        wheel.symlink_to(saved)
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Symlink"):
            self.validate(check_runtime=False)
        wheel.unlink()
        saved.replace(wheel)
        lock = self.fixture.root / "wheel-lock.json"
        value = json.loads(lock.read_text())
        value["files"]["../escape.whl"] = value["files"].pop(wheel.name)
        write_json(lock, value)
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "basenames"):
            self.validate(check_runtime=False)

    def test_archive_traversal_and_direct_url_dependency_rejected(self):
        leaf = next(self.fixture.wheels.glob("tiny_leaf*.whl"))
        leaf.unlink()
        tiny_wheel(self.fixture.wheels, "tiny-leaf", "1.0", extra_members={"../../escape.py": "unsafe"})
        self.fixture.refresh()
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Unsafe.*archive"):
            self.validate(check_runtime=False)
        leaf.unlink()
        tiny_wheel(self.fixture.wheels, "tiny-leaf", "1.0", requires=["bad @ https://example.invalid/bad.whl"])
        self.fixture.refresh()
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Direct URL"):
            self.validate(check_runtime=False)

    def test_wrong_python_glibc_and_arch_wheels_rejected(self):
        for tag in ["cp311-cp311-manylinux_2_28_x86_64", "cp312-cp312-manylinux_2_31_x86_64",
                    "cp312-cp312-manylinux_2_28_aarch64", "cp312-cp312-win_amd64"]:
            with self.subTest(tag=tag), self.assertRaisesRegex(offline.OfflineEnvironmentError, "incompatible"):
                offline._portable_filename("example-1.0-" + tag + ".whl")
        self.assertEqual(offline._portable_filename("example-1.0-cp39-abi3-manylinux2014_x86_64.whl"),
                         ("example", "1.0"))

    def test_nested_vendored_metadata_does_not_replace_outer_identity(self):
        leaf=next(self.fixture.wheels.glob("tiny_leaf*.whl"));leaf.unlink()
        nested={"tiny_leaf/_vendor/vendor-2.0.dist-info/METADATA":"Metadata-Version: 2.1\nName: vendor\nVersion: 2.0\n"}
        leaf=tiny_wheel(self.fixture.wheels,"tiny-leaf","1.0",extra_members=nested)
        self.fixture.refresh()
        self.assertEqual(offline._wheel_identity(leaf),("tiny-leaf","1.0"))
        from tools.arc_next_environment import wheel_identity
        self.assertEqual(wheel_identity(leaf),("tiny-leaf","1.0"))
        self.assertEqual(self.validate(check_runtime=False)["versions"]["tiny-leaf"],"1.0")

    def test_second_root_metadata_is_rejected_even_with_nested_metadata_allowed(self):
        leaf=next(self.fixture.wheels.glob("tiny_leaf*.whl"));leaf.unlink()
        leaf=tiny_wheel(self.fixture.wheels,"tiny-leaf","1.0",extra_members={"other-2.0.dist-info/METADATA":"Name: other\nVersion: 2.0\n"})
        from tools.arc_next_environment import wheel_identity
        for parser in (offline._wheel_identity,wheel_identity):
            with self.assertRaisesRegex(ValueError,"root-level"):parser(leaf)

    def test_root_dist_info_directory_must_match_filename_and_metadata(self):
        leaf=next(self.fixture.wheels.glob("tiny_leaf*.whl"))
        with zipfile.ZipFile(leaf) as source:
            members={name.replace('tiny_leaf-1.0.dist-info/','forged-1.0.dist-info/'):source.read(name) for name in source.namelist()}
        with zipfile.ZipFile(leaf,'w') as target:
            for name,body in members.items():target.writestr(name,body)
        from tools.arc_next_environment import wheel_identity
        for parser in (offline._wheel_identity,wheel_identity):
            with self.assertRaisesRegex(ValueError,"dist-info directory"):parser(leaf)

    def test_optional_backend_wheel_rejected(self):
        tiny_wheel(self.fixture.wheels, "torchao", "0.10.0")
        self.fixture.refresh()
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Optional backend"):
            self.validate(check_runtime=False)

    def test_duplicate_json_key_rejected(self):
        path = self.fixture.root / "wheel-lock.json"
        path.write_text('{"format":"a","format":"b"}')
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Duplicate JSON"):
            self.validate(check_runtime=False)


@unittest.skipUnless(sys.version_info[:2] == (3, 12) and platform.system() == "Linux" and
                     platform.machine() == "x86_64", "Selected CPU runtime required")
class OfflineSubprocessTests(OfflineEnvironmentTests):
    def test_real_pip_resolution_uses_complete_fake_closure_offline(self):
        with mock.patch.object(socket, "socket", side_effect=AssertionError("parent sockets forbidden")):
            result = self.validate()
        self.assertTrue(result["complete_transitive_lock_verified"])
        self.assertFalse(result["gpu_runtime_verified"])

    def test_missing_transitive_wheel_fails_real_pip_without_network(self):
        next(self.fixture.wheels.glob("tiny_leaf*.whl")).unlink()
        self.fixture.refresh()
        self.assertFalse(self.validate(check_runtime=False)["complete_transitive_lock_verified"])
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Offline subprocess failed"):
            self.validate()
        self.assertFalse((self.base / "env").exists())

    def test_install_destination_cannot_mutate_wheelhouse(self):
        destination = self.fixture.root / "accidental-env"
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "outside the immutable wheelhouse"):
            offline.install_offline(self.fixture.source, self.fixture.root, destination, enabled=True)
        self.assertFalse(destination.exists())

    def test_missing_wheel_install_fails_before_creating_environment(self):
        next(self.fixture.wheels.glob("tiny_leaf*.whl")).unlink()
        self.fixture.refresh()
        destination = self.base / "must-stay-absent"
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Offline subprocess failed"):
            offline.install_offline(self.fixture.source, self.fixture.root, destination, enabled=True)
        self.assertFalse(destination.exists())

    def test_child_process_guard_blocks_dns_and_ip_sockets(self):
        for expression in ["socket.getaddrinfo('example.invalid', 443)",
                           "socket.getnameinfo(('127.0.0.1', 443), 0)", "socket.socket()"]:
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(offline.OfflineEnvironmentError, "IRISX offline guard"):
                    offline._run(sys.executable, "import socket\n" + expression)
        # The execution sandbox may deny AF_UNIX creation itself; prove our
        # policy permits local IPC without claiming an OS permission grant.
        result = offline._run(sys.executable, "import socket\n_irisx_audit('socket.__new__', (None, socket.AF_UNIX)); print('ipc-policy-ok')")
        self.assertIn("ipc-policy-ok", result.stdout)

    def test_real_install_isolated_locked_and_spawn_guarded(self):
        destination = self.base / "env"
        prepared_hash = sha(self.fixture.root / "wheel-lock.json")
        fake_host = self.base / "host-packages"
        fake_host.mkdir()
        (fake_host / "torchao.py").write_text("raise RuntimeError('host torchao must not import')")
        (fake_host / "sitecustomize.py").write_text("import os; os.environ['IRISX_FAKE_HOST_CUSTOMIZATION'] = '1'\n")
        with mock.patch.dict(offline.os.environ, {"PYTHONPATH": str(fake_host),
                             "PIP_INDEX_URL": "https://example.invalid", "PIP_FIND_LINKS": "https://example.invalid"}):
            result = offline.install_offline(self.fixture.source, self.fixture.root, destination, enabled=True)
        self.assertEqual(result["status"], "installed-offline")
        self.assertEqual(result["python_command"][1:-1], ["-I", "-B", "-S"])
        self.assertEqual(sha(self.fixture.root / "wheel-lock.json"), prepared_hash)
        self.assertEqual(result["prepared_wheel_lock_sha256"], prepared_hash)
        self.assertEqual(result, json.loads((destination / "installation-receipt.json").read_text()))
        evidence = Path(result["environment_lock"]).parent
        self.assertTrue((evidence / "wheels").is_symlink())
        runtime_lock = json.loads((evidence / "wheel-lock.json").read_text())
        self.assertEqual(runtime_lock["python"], platform.python_version())
        self.assertEqual(runtime_lock["prepared_python"], "3.12.1")
        self.assertEqual(runtime_lock["prepared_wheel_lock_sha256"], prepared_hash)
        script = self.base / "check_runtime.py"
        (self.base / "mounted_runtime_fixture.py").write_text("VALUE = 'verified'\n")
        script.write_text('''
import mounted_runtime_fixture
import importlib.util
import os
import multiprocessing
import socket
import subprocess
import sys

def child(queue):
    assert getattr(socket, "_irisx_offline_guard", False), "Missing guard; probes forbidden"
    try:
        socket.socket()
    except RuntimeError:
        queue.put("spawn-blocked")
    else:
        queue.put("UNSAFE")

if __name__ == "__main__":
    assert sys.prefix != sys.base_prefix
    assert sys.dont_write_bytecode
    assert "PYTHONPATH" not in os.environ and "PYTHONHOME" not in os.environ
    assert "PIP_INDEX_URL" not in os.environ and os.environ["PIP_NO_INDEX"] == "1"
    assert "IRISX_FAKE_HOST_CUSTOMIZATION" not in os.environ
    assert mounted_runtime_fixture.VALUE == "verified"
    assert importlib.util.find_spec("torchao") is None
    assert getattr(socket, "_irisx_offline_guard", False)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(target=child, args=(queue,))
    process.start()
    assert queue.get(timeout=30) == "spawn-blocked"
    process.join(30)
    assert process.exitcode == 0
    result = subprocess.run([sys.executable, "-c", "import socket; assert getattr(socket, '_irisx_offline_guard', False), 'Missing guard; probes forbidden'; socket.getaddrinfo('example.invalid',443)"], capture_output=True, text=True)
    assert result.returncode != 0 and "IRISX offline guard" in result.stderr
    print("isolated-spawn-guard-verified")
''')
        hostile_env = dict(offline.os.environ, PYTHONPATH=str(fake_host), PYTHONHOME=str(fake_host),
                           PIP_INDEX_URL="https://example.invalid")
        run = subprocess.run([*result["python_command"], str(script)], env=hostile_env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("isolated-spawn-guard-verified", run.stdout)
        self.assertFalse((self.base / "__pycache__").exists(), "Mounted writable source must stay byte-for-byte unchanged")
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "fresh isolated"):
            offline.install_offline(self.fixture.source, self.fixture.root, destination, enabled=True)

        # Schema/readback compatibility with the existing validator, with the
        # synthetic anchors and installed metadata substituted explicitly.
        from tools import arc_next_models
        anchors = {name: {entry["filename"]: entry["sha256"] for entry in package["wheels"]}
                   for name, package in self.fixture.packages.items()}
        with mock.patch.object(arc_next_models, "APPROVED_CORE_WHEELS", anchors), \
             mock.patch.object(arc_next_models.importlib.metadata, "version", side_effect=result["versions"].__getitem__), \
             mock.patch.object(arc_next_models.importlib.util, "find_spec", return_value=None):
            validated = arc_next_models.validate_environment(result["environment_lock"], "granite-4.2-8b")
        self.assertTrue(validated["complete_transitive_lock_verified"])


@unittest.skipUnless(sys.version_info[:2] == (3, 12) and platform.system() == "Linux" and
                     platform.machine() == "x86_64", "Selected CPU runtime required")
class EarlyGuardStartupTests(unittest.TestCase):
    """One independent tiny no-dependency wheel; no real backend material needed."""
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name)
        cls.root = cls.base / "tiny-venv"
        offline.venv.EnvBuilder(with_pip=False, symlinks=False).create(cls.root)
        cls.python = cls.root / "bin/python"
        cls.site = cls.root / "lib/python3.12/site-packages"
        cls.guard = cls.site / "sitecustomize.py"
        cls.hook = cls.root / offline.NETWORK_GUARD_HOOK_RELATIVE
        cls.guard.write_text(offline.NETWORK_GUARD)
        cls.hook.write_text(offline._network_guard_hook(cls.root))
        cls.launcher = cls.root / "offline-run.py"
        cls.launcher.write_text(offline._LAUNCHER)
        offline._run(cls.python, offline._BOOTSTRAP_PIP)
        wheel_root = cls.base / "tiny-wheelhouse"
        (wheel_root / "wheels").mkdir(parents=True)
        wheel = tiny_wheel(wheel_root / "wheels", "irisx-guard-fixture", "1.0")
        (wheel_root / "requirements.lock").write_text("irisx-guard-fixture==1.0 --hash=sha256:" + sha(wheel) + "\n")
        offline._run(cls.python, offline._PIP_MAIN, offline._pip_args(wheel_root))

    def run_code(self, code, flags=(), env=None):
        return subprocess.run([str(self.python), *flags, "-c", code],
                              env=env or offline._offline_env(), text=True, capture_output=True, timeout=60)

    def test_plain_child_and_spawn_have_actual_audit_denial(self):
        offline._verify_guard_startup(self.python)
        result = self.run_code("import irisx_guard_fixture; assert irisx_guard_fixture.__version__ == '1.0'\n" + offline._GUARD_PROBE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_guard_runs_before_shadowing_stdlib_sitecustomize(self):
        shadow = self.base / "shadow-stdlib"
        shadow.mkdir(exist_ok=True)
        (shadow / "sitecustomize.py").write_text(
            "import socket\nassert getattr(socket, '_irisx_offline_guard', False)\nSTDLIB_SHADOW = True\n")
        (shadow / "_irisx_exact_path_guard.py").write_text("raise AssertionError('Generic guard import is forbidden')\n")
        # Insert an earlier stdlib-like entry before site.main(), matching Ubuntu's
        # actual ordering without changing host stdlib or OS configuration.
        code = ("import sys, site\nsys.path.insert(0, " + repr(str(shadow)) + ")\nsite.main()\n"
                "import sitecustomize\nassert sitecustomize.STDLIB_SHADOW\n" + offline._GUARD_PROBE)
        result = self.run_code(code, flags=("-S",))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # Also prove a normal site-enabled launch with an earlier PYTHONPATH file
        # cannot replace the exact-path guard body or its persistent namespace.
        env = dict(offline._offline_env(), PYTHONPATH=str(shadow))
        result = self.run_code("import sitecustomize; assert sitecustomize.STDLIB_SHADOW\n" + offline._GUARD_PROBE, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_launcher_spawn_then_plain_descendant_are_guarded(self):
        script = self.base / "nested_probe.py"
        probe = offline._GUARD_PROBE
        script.write_text("""
import multiprocessing, subprocess, sys
PROBE = """ + repr(probe) + """
def child():
    exec(PROBE)
    result = subprocess.run([sys.executable, '-c', PROBE], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
if __name__ == '__main__':
    exec(PROBE)
    context = multiprocessing.get_context('spawn')
    process = context.Process(target=child)
    process.start(); process.join(30)
    assert process.exitcode == 0
""")
        result = subprocess.run([str(self.python), "-I", "-S", str(self.launcher), str(script)],
                                env=offline._offline_env(), text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_hook_fails_closed_if_guard_missing_or_changed_even_optimized(self):
        body = self.guard.read_bytes()
        try:
            for changed in (None, body + b"\n# tampered\n"):
                if changed is None:
                    self.guard.unlink()
                else:
                    self.guard.write_bytes(changed)
                for flags in ((), ("-O",), ("-OO",)):
                    result = self.run_code("raise AssertionError('User code must not run')", flags=flags)
                    self.assertEqual(result.returncode, 78, result.stdout + result.stderr)
        finally:
            self.guard.write_bytes(body)


@unittest.skipUnless(sys.version_info[:2] == (3, 12) and platform.system() == "Linux" and
                     platform.machine() == "x86_64", "Selected CPU runtime required")
class LegacyGuardMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.base = Path(cls.temporary.name)
        cls.fixture = Wheelhouse(cls.base)
        cls.root = cls.base / "legacy-env"
        receipt = offline.install_offline(cls.fixture.source, cls.fixture.root, cls.root, enabled=True)
        # Historical bytes are independent of the current installer/constants.
        # Exact literals extracted from main 077bb468's trusted pre-hook v3 code.
        frozen = Path(__file__).parent / "fixtures/arc_next_legacy_v3"
        cls.legacy_guard = (frozen / "sitecustomize.py.txt").read_bytes()
        cls.legacy_launcher = (frozen / "offline-run.py.txt").read_bytes()
        if hashlib.sha256(cls.legacy_guard).hexdigest() != "7669d1387b8429bff42428e14c0210960a465c7b7b634b661b1fb62c4cc44f82":
            raise AssertionError("Frozen v3 guard fixture changed")
        if hashlib.sha256(cls.legacy_launcher).hexdigest() != "12dca3a583c059a95db714e53f0d60952bc8e5b35d734cd21182e8487a83931c":
            raise AssertionError("Frozen v3 launcher fixture changed")
        cls.guard = cls.root / "lib/python3.12/site-packages/sitecustomize.py"
        cls.launcher = cls.root / "offline-run.py"
        cls.guard.write_bytes(cls.legacy_guard)
        cls.launcher.write_bytes(cls.legacy_launcher)
        receipt["network_guard_sha256"] = sha(cls.guard)
        receipt["python_launcher_sha256"] = sha(cls.launcher)
        receipt["python_command"] = [receipt["python_executable"], "-I", "-S", str(cls.launcher)]
        for field in ("network_guard_startup", "network_guard_startup_hook_path", "network_guard_startup_hook_sha256"):
            receipt.pop(field)
        # Dynamic paths/interpreter/wheel evidence comes from a tiny installation;
        # guard, launcher and command flags are the fixed historical identities.
        cls.legacy_receipt = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
        cls.legacy_lock = (json.dumps(receipt, sort_keys=True) + "\n").encode()
        cls.receipt_path = cls.root / "installation-receipt.json"
        cls.lock_path = cls.root / "evidence/environment-lock.json"
        cls.hook = cls.root / offline.NETWORK_GUARD_HOOK_RELATIVE

    def setUp(self):
        self.receipt_path.write_bytes(self.legacy_receipt)
        self.lock_path.write_bytes(self.legacy_lock)
        self.hook.unlink(missing_ok=True)

    def migrate(self, **kwargs):
        return offline.migrate_offline_guard(self.fixture.source, self.fixture.root, self.root, enabled=True,
                                            expected_legacy_receipt_sha256=sha(self.receipt_path), **kwargs)

    def assert_unchanged(self):
        self.assertFalse(self.hook.exists())
        self.assertEqual(self.receipt_path.read_bytes(), self.legacy_receipt)
        self.assertEqual(self.lock_path.read_bytes(), self.legacy_lock)

    def test_migration_preserves_legacy_bytes_and_changes_only_hook_and_receipts(self):
        before = {str(p.relative_to(self.root)): sha(p) for p in self.root.rglob("*") if p.is_file() and not p.is_symlink()}
        real_run = offline._run
        calls = []
        def checked_run(python, code, args=None, **kwargs):
            calls.append((code, args))
            self.assertNotEqual(code, offline._BOOTSTRAP_PIP)
            self.assertFalse(args and args[0] == "install", "Migration must not reinstall")
            return real_run(python, code, args, **kwargs)
        with mock.patch.object(offline, "_run", side_effect=checked_run), \
             mock.patch.object(offline.venv.EnvBuilder, "create", side_effect=AssertionError("No new venv")):
            result = self.migrate()
        self.assertTrue(calls)
        after = {str(p.relative_to(self.root)): sha(p) for p in self.root.rglob("*") if p.is_file() and not p.is_symlink()}
        changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
        self.assertEqual(changed, {offline.NETWORK_GUARD_HOOK_RELATIVE, "installation-receipt.json", "evidence/environment-lock.json"})
        self.assertEqual(self.hook.read_text(), offline._network_guard_hook(self.root, legacy_v3=True))
        self.assertEqual(result["network_guard_startup_hook_sha256"], sha(self.hook))
        saved = result["network_guard_migration"]
        self.assertEqual(saved["legacy_installation_receipt_utf8"].encode(), self.legacy_receipt)
        self.assertEqual(saved["legacy_environment_lock_utf8"].encode(), self.legacy_lock)
        self.assertEqual(saved["legacy_installation_receipt_sha256"], hashlib.sha256(self.legacy_receipt).hexdigest())
        self.assertEqual(saved["legacy_environment_lock_sha256"], hashlib.sha256(self.legacy_lock).hexdigest())
        self.assertEqual(self.receipt_path.read_bytes(), self.lock_path.read_bytes())
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "pre-hook"):
            self.migrate()

    def test_frozen_legacy_fixture_differs_from_new_install_identity(self):
        self.assertEqual(self.guard.read_bytes(), self.legacy_guard)
        self.assertEqual(self.launcher.read_bytes(), self.legacy_launcher)
        self.assertNotEqual(self.legacy_guard, offline.NETWORK_GUARD.encode())
        self.assertNotEqual(self.legacy_launcher, offline._LAUNCHER.encode())
        self.assertEqual(json.loads(self.legacy_receipt)["python_command"][1:-1], ["-I", "-S"])

    def test_changed_guard_or_launcher_identity_refused_even_with_rehashed_receipts(self):
        for path, body, field in ((self.guard, self.legacy_guard, "network_guard_sha256"),
                                  (self.launcher, self.legacy_launcher, "python_launcher_sha256")):
            with self.subTest(field=field):
                try:
                    path.write_bytes(body + b"\n# changed\n")
                    receipt = json.loads(self.legacy_receipt)
                    receipt[field] = sha(path)
                    write_json(self.receipt_path, receipt)
                    write_json(self.lock_path, receipt)
                    before = (self.receipt_path.read_bytes(), self.lock_path.read_bytes())
                    with self.assertRaisesRegex(offline.OfflineEnvironmentError, "trusted v3 bytes"):
                        self.migrate()
                    self.assertFalse(self.hook.exists())
                    self.assertEqual((self.receipt_path.read_bytes(), self.lock_path.read_bytes()), before)
                finally:
                    path.write_bytes(body)

    def test_new_command_flags_refused_as_legacy_even_with_rehashed_receipts(self):
        receipt = json.loads(self.legacy_receipt)
        receipt["python_command"].insert(2, "-B")
        write_json(self.receipt_path, receipt)
        write_json(self.lock_path, receipt)
        before = (self.receipt_path.read_bytes(), self.lock_path.read_bytes())
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "trusted v3 installation layout"):
            self.migrate()
        self.assertFalse(self.hook.exists())
        self.assertEqual((self.receipt_path.read_bytes(), self.lock_path.read_bytes()), before)

    def test_wrong_digest_and_receipt_pair_refused_without_mutation(self):
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "expected digest"):
            offline.migrate_offline_guard(self.fixture.source, self.fixture.root, self.root, enabled=True,
                                         expected_legacy_receipt_sha256="0" * 64)
        self.assert_unchanged()
        self.lock_path.write_text("{}")
        try:
            with self.assertRaisesRegex(offline.OfflineEnvironmentError, "receipt pair"):
                self.migrate()
            self.assertFalse(self.hook.exists())
            self.assertEqual(self.receipt_path.read_bytes(), self.legacy_receipt)
        finally:
            self.lock_path.write_bytes(self.legacy_lock)

    def test_changed_legacy_evidence_is_rejected_before_any_write(self):
        for relative in ("offline-run.py", "lib/python3.12/site-packages/sitecustomize.py",
                         "bin/python", "evidence/requirements.lock", "evidence/wheel-lock.json",
                         "evidence/pip-install-report.json", "pyvenv.cfg"):
            path = self.root / relative
            body = path.read_bytes()
            with self.subTest(relative=relative):
                try:
                    path.write_bytes(body + b"\nchanged\n")
                    with self.assertRaises((ValueError, json.JSONDecodeError)):
                        self.migrate()
                    self.assert_unchanged()
                finally:
                    path.write_bytes(body)

    def test_changed_installed_version_is_rejected_before_any_write(self):
        path = next((self.root / "lib/python3.12/site-packages").glob("tiny_leaf-*.dist-info/METADATA"))
        body = path.read_bytes()
        try:
            path.write_bytes(body.replace(b"Version: 1.0", b"Version: 9.0"))
            with self.assertRaisesRegex(offline.OfflineEnvironmentError, "Installed versions"):
                self.migrate()
            self.assert_unchanged()
        finally:
            path.write_bytes(body)

    def test_interrupted_receipt_pair_is_not_admitted_or_automatically_retried(self):
        atomic = offline._atomic_bytes
        def interrupt(path, body):
            if path == self.receipt_path:
                raise OSError("synthetic interrupted receipt commit")
            return atomic(path, body)
        with mock.patch.object(offline, "_atomic_bytes", side_effect=interrupt):
            with self.assertRaisesRegex(OSError, "interrupted"):
                self.migrate()
        self.assertTrue(self.hook.exists())
        self.assertEqual(self.receipt_path.read_bytes(), self.legacy_receipt)
        self.assertNotEqual(self.lock_path.read_bytes(), self.legacy_lock)
        with self.assertRaisesRegex(offline.OfflineEnvironmentError, "receipt pair"):
            self.migrate()


if __name__ == "__main__":
    unittest.main()
