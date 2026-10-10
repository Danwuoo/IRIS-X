"""Verify a mounted ARC next-line wheelhouse and build an isolated offline venv.

Importing this module is inert and stdlib-only. No download path exists. The
selected application ABI is CPython 3.12 / Linux x86_64 / glibc >= 2.28 with
Torch 2.8.0+cu128. Actual GPU/driver compatibility is deliberately unclaimed.

The Python socket guard is defense in depth, not an OS sandbox: native code
and non-Python executables still require the notebook's InternetOFF boundary.
The mounted input stays untouched. Only generated runtime evidence links back
to its verified wheels; this avoids copying several gigabytes into working disk.
"""
from __future__ import annotations

import email
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import sysconfig
import tempfile
from typing import Any
import venv
import zipfile


CORE_VERSIONS = {
    "torch": "2.8.0+cu128", "transformers": "5.8.1", "peft": "0.21.0",
    "accelerate": "1.10.1", "tokenizers": "0.22.2", "huggingface-hub": "1.32.0",
    "safetensors": "0.8.0", "jinja2": "3.1.6",
}
OPTIONAL_MODULES = ("torchao", "bitsandbytes", "flash_attn", "fla", "causal_conv1d",
                    "vllm", "unsloth", "nemo")
FORBIDDEN_DISTRIBUTIONS = {"torchao", "bitsandbytes", "flash-attn", "fla",
                           "flash-linear-attention", "causal-conv1d", "vllm",
                           "unsloth", "nemo-toolkit"}
TARGET = {"implementation": "CPython", "python_major_minor": "3.12",
          "system": "Linux", "machine": "x86_64", "glibc_minimum": "2.28",
          "torch": "2.8.0+cu128"}
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
_VERSION = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9.+!_]*\Z")
_REQUIREMENT = re.compile(
    r"([a-z0-9][a-z0-9-]*)==([a-zA-Z0-9][a-zA-Z0-9.+!_]*)"
    r" --hash=sha256:([0-9a-f]{64})\Z")


class OfflineEnvironmentError(ValueError):
    """An unverified or incompatible wheelhouse must not be installed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OfflineEnvironmentError(message)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _no_symlinks(path: str | Path, *, directory: bool = False) -> Path:
    path = Path(path)
    _require(".." not in path.parts, "Path traversal is forbidden")
    path = path.absolute()
    for member in (path, *path.parents):
        _require(not member.is_symlink(), "Symlink input is forbidden: " + str(member))
    _require(path.is_dir() if directory else path.is_file(), "Missing local path: " + str(path))
    return path


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def _json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_bytes(), object_pairs_hook=_unique_object)
    _require(isinstance(result, dict), "JSON object required: " + str(path))
    return result


def _write(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def inspect_runtime() -> dict[str, Any]:
    """Observe the host without third-party imports, installs or GPU calls.

    This is diagnostic evidence, never permission to consume a different ABI.
    Record every predicate separately so a notebook mismatch is actionable even
    when its workflow stops before it can write a successful stage receipt.
    """
    libc, version = platform.libc_ver()
    if libc != "glibc":
        try:
            value = os.confstr("CS_GNU_LIBC_VERSION") or ""
            libc, version = value.split(" ", 1)
        except (AttributeError, ValueError, OSError):
            pass
    observed = {
        "implementation": platform.python_implementation(),
        "python": platform.python_version(),
        "python_major_minor": ".".join(map(str, sys.version_info[:2])),
        "python_executable": sys.executable,
        "python_full_version": sys.version,
        "python_soabi": sysconfig.get_config_var("SOABI"),
        "system": platform.system(), "machine": platform.machine(),
        "libc": libc, "glibc": version,
    }
    checks = {key: observed[key] == TARGET[key] for key in (
        "implementation", "python_major_minor", "system", "machine")}
    checks["glibc_minimum"] = (
        libc == "glibc" and re.fullmatch(r"\d+\.\d+(?:\.\d+)*", version) is not None
        and tuple(map(int, version.split("."))) >= (2, 28))
    return {"format": "irisx/arc-next-host-runtime-observation-v1",
            "expected": {key: TARGET[key] for key in checks},
            "observed": observed, "checks": checks,
            "mismatches": [key for key, passed in checks.items() if not passed],
            "compatible": all(checks.values()),
            "network_calls": 0, "install_calls": 0, "gpu_calls": 0}


class RuntimeCompatibilityError(OfflineEnvironmentError):
    """The observed interpreter cannot consume the exact mounted wheel ABI."""
    def __init__(self, diagnostic: dict[str, Any]):
        self.diagnostic = diagnostic
        observed = diagnostic["observed"]
        differences = []
        for key in diagnostic["mismatches"]:
            actual = (observed["libc"] + " " + observed["glibc"]
                      if key == "glibc_minimum" else observed[key])
            differences.append(key + ": observed " + repr(actual) +
                               ", required " + repr(diagnostic["expected"][key]))
        super().__init__(
            "Offline wheel ABI mismatch (" + "; ".join(differences) + "). "
            "Interpreter: " + observed["python_executable"] + ". "
            "The locked wheels require CPython 3.12, Linux x86_64, glibc >= 2.28; "
            "no installation or training started. Select a verified compatible "
            "interpreter or prepare a separately verified matching wheelhouse; "
            "do not bypass this gate or install cp312 wheels into another Python ABI.")


def _runtime() -> dict[str, str]:
    diagnostic = inspect_runtime()
    if not diagnostic["compatible"]:
        raise RuntimeCompatibilityError(diagnostic)
    observed = diagnostic["observed"]
    return {"python": observed["python"], "glibc": observed["glibc"],
            "platform": platform.platform(), "implementation": observed["implementation"]}


def _portable_filename(filename: str) -> tuple[str, str]:
    """Conservative target tag gate; pip also checks its complete actual tag set."""
    _require(filename.endswith(".whl") and "/" not in filename and "\\" not in filename
             and Path(filename).name == filename, "Only safe wheel basenames are permitted")
    fields = filename[:-4].split("-")
    _require(len(fields) in (5, 6), "Invalid wheel filename: " + filename)
    distribution, version = _name(fields[0]), fields[1]
    _require(_NAME.fullmatch(distribution) is not None and _VERSION.fullmatch(version) is not None,
             "Invalid wheel identity: " + filename)
    if len(fields) == 6:
        _require(re.fullmatch(r"[0-9][a-zA-Z0-9_]*", fields[2]) is not None,
                 "Invalid wheel build tag")
    python_tags, abi_tags, platforms = [value.split(".") for value in fields[-3:]]
    portable = {"any", "manylinux1_x86_64", "manylinux2010_x86_64", "manylinux2014_x86_64"}
    portable.update(f"manylinux_2_{minor}_x86_64" for minor in range(5, 29))
    accepted = False
    for py in python_tags:
        for abi in abi_tags:
            for target in platforms:
                if target not in portable:
                    continue
                if py == "cp312" and abi in {"cp312", "abi3", "none"}:
                    accepted |= target != "any" or abi == "none"
                elif py in {f"cp3{minor}" for minor in range(2, 12)} and abi == "abi3":
                    accepted |= target != "any"
                elif py in {"py3", *(f"py3{minor}" for minor in range(13))} and abi == "none":
                    accepted = True
    _require(accepted, "Wheel is incompatible with portable CPython 3.12/glibc 2.28 x86_64: " + filename)
    return distribution, version


def _wheel_identity(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        seen = set()
        metadata = []
        for item in members:
            parts = PurePosixPath(item.filename)
            _require(item.filename not in seen and not parts.is_absolute() and
                     ".." not in parts.parts and "\\" not in item.filename and
                     not stat.S_ISLNK(item.external_attr >> 16),
                     "Unsafe or duplicate wheel archive member: " + item.filename)
            seen.add(item.filename)
            # Vendored packages may carry nested dist-info metadata; only the
            # outer wheel's single root dist-info directory owns its identity.
            if len(parts.parts) == 2 and parts.parts[0].endswith(".dist-info") and parts.parts[1] == "METADATA":
                metadata.append(item)
        _require(len(metadata) == 1 and metadata[0].file_size < 4 * 1024 * 1024,
                 "Exactly one root-level bounded wheel METADATA is required")
        msg = email.message_from_bytes(archive.read(metadata[0]))
        _require(len(msg.get_all("Name", [])) == 1 and len(msg.get_all("Version", [])) == 1,
                 "Exactly one wheel name/version is required")
        name, version = _name(msg["Name"]), msg["Version"]
        _require(_NAME.fullmatch(name) is not None and _VERSION.fullmatch(version) is not None,
                 "Unsafe wheel metadata identity")
        directory = PurePosixPath(metadata[0].filename).parts[0][:-len(".dist-info")]
        parts = directory.rsplit("-", 1)
        _require(len(parts) == 2 and _name(parts[0]) == name and parts[1] == version,
                 "Root dist-info directory differs from wheel metadata identity")
        for requirement in msg.get_all("Requires-Dist", []):
            _require("@" not in requirement and "://" not in requirement,
                     "Direct URL/path wheel dependencies are forbidden")
        _require(_portable_filename(path.name) == (name, version),
                 "Wheel filename/metadata identity differs: " + path.name)
        return name, version


# Loaded by exact-path early .pth for ordinary/spawn children; sitecustomize
# remains a fallback. Also inline before site.main in launcher/pip. AF_UNIX remains available
# for local multiprocessing IPC. Native networking is outside Python's audit API.
NETWORK_GUARD = r'''
import sys as _guard_sys
# Set before any other import: the portable stdlib is hash-closed too.
_guard_sys.dont_write_bytecode = True
import os as _guard_os
import socket as _guard_socket
# -I only protects this interpreter. Plain sys.executable subprocesses inherit
# os.environ, so remove host PYTHONPATH/PYTHONHOME/sitecustomize and pip overrides.
for _guard_key in list(_guard_os.environ):
    if _guard_key.startswith(("PYTHON", "PIP_")):
        _guard_os.environ.pop(_guard_key)
_guard_os.environ.update({"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONNOUSERSITE": "1", "PIP_CONFIG_FILE": _guard_os.devnull,
    "PIP_NO_INDEX": "1", "PIP_NO_CACHE_DIR": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"})
if not getattr(_guard_socket, "_irisx_offline_guard", False):
    def _irisx_deny(*args, **kwargs):
        raise RuntimeError("IRISX offline guard: network sockets and DNS are disabled")
    def _irisx_audit(event, args):
        if event == "socket.__new__" and args[1] in (_guard_socket.AF_INET, _guard_socket.AF_INET6):
            _irisx_deny()
        if event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo"):
            _irisx_deny()
        if event in ("socket.connect", "socket.sendto", "socket.bind"):
            if args[0].family in (_guard_socket.AF_INET, _guard_socket.AF_INET6):
                _irisx_deny()
    _guard_sys.addaudithook(_irisx_audit)
    _guard_socket.getaddrinfo = _irisx_deny
    _guard_socket.gethostbyname = _irisx_deny
    _guard_socket.gethostbyname_ex = _irisx_deny
    _guard_socket.gethostbyaddr = _irisx_deny
    _guard_socket.getnameinfo = _irisx_deny
    _guard_socket.create_connection = _irisx_deny
    _guard_socket._irisx_offline_guard = True
_guard_os.environ["HF_HUB_OFFLINE"] = "1"
_guard_os.environ["TRANSFORMERS_OFFLINE"] = "1"
_guard_os.environ["HF_DATASETS_OFFLINE"] = "1"
_guard_os.environ["WANDB_MODE"] = "offline"
'''

# .pth files run before generic sitecustomize resolution. In particular Ubuntu's
# stdlib sitecustomize must not shadow the task-owned guard for ordinary children.
NETWORK_GUARD_HOOK_RELATIVE = "lib/python3.12/site-packages/000_irisx_offline_guard.pth"

# Frozen pre-hook v3 identities from main 077bb4680706b95f196621dab4360ffe03504354.
# Migration must not redefine historical installation bytes when new installs
# change their guard ordering or interpreter flags.
_LEGACY_V3_GUARD_SHA256 = "7669d1387b8429bff42428e14c0210960a465c7b7b634b661b1fb62c4cc44f82"
_LEGACY_V3_LAUNCHER_SHA256 = "12dca3a583c059a95db714e53f0d60952bc8e5b35d734cd21182e8487a83931c"
_LEGACY_V3_PYTHON_FLAGS = ("-I", "-S")


def _network_guard_hook(environment_dir: str | Path, *, legacy_v3: bool = False) -> str:
    """Render an exact-path, digest-bound bootstrap with durable function globals.

    site.addpackage executes .pth statements inside a function: bare exec there
    would split locals from globals and break the audit callback after startup.
    A private shared namespace remains owned by the installed audit callback.
    Bootstrap failures terminate the interpreter because site otherwise prints
    .pth errors and continues without the guard.
    """
    path = str(Path(environment_dir).absolute() / "lib/python3.12/site-packages/sitecustomize.py")
    digest = (_LEGACY_V3_GUARD_SHA256 if legacy_v3 else
              hashlib.sha256(NETWORK_GUARD.encode()).hexdigest())
    bootstrap = (
        "import os, hashlib\n"
        "try:\n"
        f"    path = {path!r}\n"
        "    with open(path, 'rb') as stream: body = stream.read()\n"
        f"    if hashlib.sha256(body).hexdigest() != {digest!r}: raise ValueError('Guard digest changed')\n"
        "    namespace = {'__name__': '_irisx_exact_path_guard', '__file__': path}\n"
        "    exec(compile(body, path, 'exec'), namespace, namespace)\n"
        "except BaseException:\n"
        "    os._exit(78)\n"
    )
    return "import builtins; builtins.exec(" + repr(bootstrap) + ", {})\n"


def _guard_hook_fields(destination: Path) -> dict[str, str]:
    hook = destination / NETWORK_GUARD_HOOK_RELATIVE
    return {"network_guard_startup": "exact-path-pth-v1",
            "network_guard_startup_hook_path": str(hook),
            "network_guard_startup_hook_sha256": _sha(hook)}


# Every network-denial probe first checks activation; an unguarded negative test
# must never issue even a DNS lookup or an Internet-family socket request.
_GUARD_PROBE = r'''
import _socket, socket
if not getattr(socket, "_irisx_offline_guard", False):
    raise AssertionError("Missing early network guard; probes forbidden")
for family in (socket.AF_INET, socket.AF_INET6):
    try:
        _socket.socket(family, socket.SOCK_STREAM)
    except RuntimeError as exc:
        assert "IRISX offline guard" in str(exc)
    else:
        raise AssertionError("Internet-family socket was not denied")
try:
    _socket.getaddrinfo("example.invalid", 443)
except RuntimeError as exc:
    assert "IRISX offline guard" in str(exc)
else:
    raise AssertionError("DNS was not denied by the audit hook")
# AF_UNIX is expressly allowed by our hook; host sandbox policy may still deny it.
socket.getaddrinfo.__globals__["_irisx_audit"]("socket.__new__", (None, socket.AF_UNIX))
'''


def _verify_guard_startup(python: Path) -> None:
    """Probe ordinary startup and a spawned descendant without inline guards."""
    code = _GUARD_PROBE + "\n" + (
        "import builtins, multiprocessing\n"
        "if __name__ == '__main__':\n"
        "    context = multiprocessing.get_context('spawn')\n"
        f"    process = context.Process(target=builtins.exec, args=({_GUARD_PROBE!r},))\n"
        "    process.start()\n"
        "    process.join(30)\n"
        "    if process.is_alive():\n"
        "        process.terminate(); process.join(); raise AssertionError('Spawn guard probe timed out')\n"
        "    assert process.exitcode == 0, 'Spawn guard probe failed'\n"
        "    print('plain-and-spawn-guard-verified')\n"
    )
    try:
        completed = subprocess.run([str(python), "-B", "-c", code], env=_offline_env(),
                                   capture_output=True, text=True, check=True, timeout=60)
        _require("plain-and-spawn-guard-verified" in completed.stdout, "Missing startup guard proof")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise OfflineEnvironmentError("Early startup guard check failed: " +
                                      str(getattr(exc, "stderr", ""))[-6000:]) from exc


_PIP_MAIN = r'''
import sys
from pip._internal.cli.main import main
raise SystemExit(main(sys.argv[1:]))
'''

_BOOTSTRAP_PIP = r'''
# CPython's bundled installer is the sole seed, never host site-packages.
# Replace ensurepip's nested subprocess so the network guard cannot be lost.
import ensurepip
import hashlib
from pathlib import Path
import sys

def guarded_seed(args, additional_paths=None):
    paths = [Path(value) for value in (additional_paths or [])]
    assert paths and all(path.suffix == ".whl" for path in paths)
    sys.path[:0] = [str(path) for path in paths]
    lock = paths[0].parent / "seed-requirements.lock"
    lock.write_text("".join(path.name.split("-")[0] + "==" + path.name.split("-")[1]
        + " --hash=sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() + "\n"
        for path in paths))
    from pip._internal.cli.main import main
    return main(["install", "--isolated", "--no-index", "--no-cache-dir",
        "--disable-pip-version-check", "--only-binary=:all:", "--require-hashes",
        "--find-links", str(paths[0].parent), "-r", str(lock)])

ensurepip._run_pip = guarded_seed
ensurepip.bootstrap(default_pip=True)
'''

_LAUNCHER = NETWORK_GUARD + r'''
import site
site.main()
import runpy
import sys
from pathlib import Path
# CPython spawn/resource-tracker copy the parent's -S flag. Drop that flag for
# those children so the persistent venv sitecustomize guard is actually loaded.
# All other isolation flags survive. Nested children start with site enabled.
import multiprocessing.util as _mp_util
_original_interpreter_flags = _mp_util._args_from_interpreter_flags
def _guarded_interpreter_flags():
    return [flag for flag in _original_interpreter_flags() if flag != "-S"]
_mp_util._args_from_interpreter_flags = _guarded_interpreter_flags
if len(sys.argv) < 2:
    raise SystemExit("Usage: offline-run.py SCRIPT [ARGS...] or -m MODULE [ARGS...]")
args = sys.argv[1:]
if args[0] == "-m":
    if len(args) < 2:
        raise SystemExit("Module name required")
    sys.argv = args[1:]
    runpy.run_module(args[1], run_name="__main__", alter_sys=True)
else:
    script = Path(args[0]).resolve(strict=True)
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), *args[1:]]
    runpy.run_path(str(script), run_name="__main__")
'''


def _offline_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("PIP_", "PYTHON")):
            env.pop(key)
    env.update({"PIP_CONFIG_FILE": os.devnull, "PIP_NO_INDEX": "1",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_CACHE_DIR": "1",
                "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1", "WANDB_MODE": "offline",
                "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def _run(python: str | Path, code: str, args: list[str] | None = None,
         *, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    command = [str(python), "-I", "-B", "-S", "-c", NETWORK_GUARD +
               "\nimport site\nsite.main()\n" + code, *(args or [])]
    try:
        return subprocess.run(command, env=_offline_env(), capture_output=True,
                              text=True, check=True, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stderr = getattr(exc, "stderr", "") or ""
        stdout = getattr(exc, "stdout", "") or ""
        raise OfflineEnvironmentError("Offline subprocess failed: " +
                                      str(stdout)[-6000:] + str(stderr)[-6000:]) from exc


def _pip_args(root: Path, *, report: Path | None = None, dry_run: bool = False) -> list[str]:
    args = ["install", "--isolated", "--no-index", "--no-cache-dir",
            "--disable-pip-version-check", "--only-binary=:all:", "--require-hashes",
            "--ignore-installed", "--find-links", str(root / "wheels"),
            "-r", str(root / "requirements.lock")]
    if dry_run:
        args.append("--dry-run")
    if report is not None:
        args.extend(["--report", str(report)])
    return args


def _verify_report(path: Path, root: Path, inventory: dict[str, Any]) -> None:
    from urllib.parse import unquote, urlparse
    report = _json(path)
    observed = {}
    by_name = {entry["name"]: (filename, entry) for filename, entry in inventory.items()}
    for install in report.get("install", []):
        name = _name(install["metadata"]["name"])
        _require(name in by_name and name not in observed, "Unexpected pip resolution result")
        filename, expected = by_name[name]
        download = install["download_info"]
        url = urlparse(download["url"])
        _require(url.scheme == "file" and not url.netloc and not url.query and not url.fragment
                 and Path(unquote(url.path)) == root / "wheels" / filename,
                 "Pip must consume only exact mounted wheel files")
        _require(download.get("archive_info", {}).get("hashes", {}).get("sha256") == expected["sha256"],
                 "Pip consumed a different wheel digest")
        _require(install["metadata"]["version"] == expected["version"], "Pip version drift")
        observed[name] = expected["version"]
    _require(set(observed) == set(by_name), "Pip resolution did not verify every locked wheel")


def validate_wheelhouse(source_lock_path: str | Path, wheelhouse_root: str | Path,
                        check_runtime: bool = True) -> dict[str, Any]:
    """Verify bytes and pins; by default prove closure with offline pip dry-run.

    check_runtime=False performs static material/selected-target checks only and
    never claims dependency closure or installation readiness. It is suitable for
    CPU packaging inspection on a machine with a different interpreter.
    """
    _require(type(check_runtime) is bool, "Boolean check_runtime required")
    runtime = _runtime() if check_runtime else None
    source = _no_symlinks(source_lock_path)
    root = _no_symlinks(wheelhouse_root, directory=True)
    wheels = _no_symlinks(root / "wheels", directory=True)
    lock_path = _no_symlinks(root / "wheel-lock.json")
    requirements_path = _no_symlinks(root / "requirements.lock")
    lock = _json(lock_path)
    source_lock = _json(source)
    packages = source_lock.get("proposed_training_environments", {}).get("common_hf_bf16_lora", {}).get("packages", {})
    _require(isinstance(packages, dict) and set(packages) == set(CORE_VERSIONS),
             "Source lock must include exactly the reviewed core packages")
    _require(all(packages[name].get("version") == version for name, version in CORE_VERSIONS.items()),
             "Source lock core backend tuple differs from selected target")
    _require(lock.get("format") == "irisx/arc-next-offline-wheel-lock-v1" and
             lock.get("source_lock_sha256") == _sha(source), "Wheel lock/source lock binding mismatch")
    _require(lock.get("all_transitive_wheels_materialized") is True,
             "Prepared wheelhouse must declare materialized transitive wheels")
    _require(isinstance(lock.get("python"), str) and re.fullmatch(r"3\.12\.\d+", lock["python"]) is not None,
             "Wheelhouse must be prepared for CPython 3.12")
    _require(lock.get("requirements_sha256") == _sha(requirements_path), "Requirements lock hash mismatch")
    inventory = lock.get("files")
    _require(isinstance(inventory, dict) and bool(inventory), "Nonempty wheel inventory required")
    versions = {}
    for filename, entry in inventory.items():
        _portable_filename(filename)
        _require(isinstance(entry, dict) and _HASH.fullmatch(str(entry.get("sha256", ""))) is not None
                 and type(entry.get("bytes")) is int and entry["bytes"] > 0, "Invalid wheel lock entry")
        path = _no_symlinks(wheels / filename)
        _require(path.stat().st_size == entry["bytes"] and _sha(path) == entry["sha256"],
                 "Wheel bytes/hash mismatch: " + filename)
        name, version = _wheel_identity(path)
        _require(entry.get("name") == name and entry.get("version") == version and name not in versions,
                 "Wheel identity mismatch or duplicate distribution: " + filename)
        _require(name not in FORBIDDEN_DISTRIBUTIONS, "Optional backend must be absent: " + name)
        if name in packages:
            expected = packages[name]
            _require(version == expected["version"] and any(
                wheel.get("filename") == filename and wheel.get("sha256") == entry["sha256"]
                for wheel in expected.get("wheels", [])), "Core wheel is not source-pinned: " + name)
        versions[name] = version
    _require(set(CORE_VERSIONS) <= set(versions), "Missing pinned core wheel")
    _require(lock.get("versions") == versions, "Wheel inventory/version lock mismatch")
    actual_members = list(wheels.iterdir())
    _require(all(path.is_file() and not path.is_symlink() and path.suffix == ".whl" for path in actual_members)
             and {path.name for path in actual_members} == set(inventory),
             "Wheel directory must contain exactly the locked wheels, with no extra files or links")
    requirements = {}
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = _REQUIREMENT.fullmatch(line)
        _require(match is not None, "Only exact pinned, SHA-256-only requirements are permitted")
        name, version, sha256 = match.groups()
        _require(name not in requirements, "Duplicate requirement: " + name)
        requirements[name] = (version, sha256)
    _require(requirements == {entry["name"]: (entry["version"], entry["sha256"])
                              for entry in inventory.values()}, "Requirements/inventory mismatch")
    if check_runtime:
        with tempfile.TemporaryDirectory(prefix="irisx-offline-resolve-") as temporary:
            report = Path(temporary) / "resolution.json"
            _run(sys.executable, _PIP_MAIN, _pip_args(root, report=report, dry_run=True))
            _verify_report(report, root, inventory)
    return {"status": "verified" if check_runtime else "static-verified-runtime-unchecked",
            "target": dict(TARGET), "runtime": runtime, "versions": versions,
            "wheel_count": len(inventory), "wheelhouse_root": str(root),
            "source_lock_sha256": _sha(source), "wheel_lock_sha256": _sha(lock_path),
            "requirements_sha256": _sha(requirements_path),
            "complete_transitive_lock_verified": check_runtime,
            "pip_offline_resolution_verified": check_runtime,
            "network_guard": "python-socket-audit-with-no-index; not an OS sandbox",
            "gpu_runtime_verified": False}


def install_offline(source_lock_path: str | Path, wheelhouse_root: str | Path,
                    environment_dir: str | Path, enabled: bool = False) -> dict[str, Any]:
    """Create a fresh isolated venv and neighboring evidence, disabled by default.

    The return value is an environment-lock object with paths/launch command.
    Save/use its environment_lock path inside the returned child interpreter;
    the notebook's existing kernel and host packages are never modified.
    """
    _require(type(enabled) is bool, "Boolean owner switch required")
    if not enabled:
        return {"status": "disabled", "network_calls": 0, "install_calls": 0, "gpu_calls": 0}
    destination = Path(environment_dir).absolute()
    _require(".." not in destination.parts and not destination.exists() and not destination.is_symlink(),
             "A fresh isolated environment destination is required")
    for parent in destination.parents:
        _require(not parent.is_symlink(), "Environment parent may not be a symlink")
    checked = validate_wheelhouse(source_lock_path, wheelhouse_root)
    root = Path(checked["wheelhouse_root"])
    _require(root not in destination.parents, "Environment must be outside the immutable wheelhouse")
    venv.EnvBuilder(with_pip=False, system_site_packages=False, symlinks=False).create(destination)
    python = destination / "bin" / "python"
    evidence = destination / "evidence"
    evidence.mkdir()
    try:
        _run(python, _BOOTSTRAP_PIP)
        site_directory = destination / "lib" / "python3.12" / "site-packages"
        _require(site_directory.is_dir(), "Isolated venv site-packages was not created")
        guard_path = site_directory / "sitecustomize.py"
        guard_path.write_text(NETWORK_GUARD, encoding="utf-8")
        (destination / NETWORK_GUARD_HOOK_RELATIVE).write_text(_network_guard_hook(destination), encoding="utf-8")
        launcher = destination / "offline-run.py"
        launcher.write_text(_LAUNCHER, encoding="utf-8")
        report = evidence / "pip-install-report.json"
        _run(python, _PIP_MAIN, _pip_args(root, report=report))
        _verify_report(report, root, _json(root / "wheel-lock.json")["files"])
        _run(python, _PIP_MAIN, ["check", "--isolated", "--disable-pip-version-check"])
        inspected = _run(python, '''
import importlib.metadata
import importlib.util
import json
import platform
import socket
import sys
wanted = json.loads(sys.argv[1])
optional = json.loads(sys.argv[2])
assert sys.prefix != sys.base_prefix, "A venv is required"
assert all(importlib.util.find_spec(name) is None for name in optional), "Optional backend leaked into venv"
assert getattr(socket, "_irisx_offline_guard", False), "Missing network guard"
print(json.dumps({"versions": {name: importlib.metadata.version(name) for name in wanted},
    "python": platform.python_version(), "prefix": sys.prefix}))
''', [json.dumps(checked["versions"]), json.dumps(OPTIONAL_MODULES)])
        actual = json.loads(inspected.stdout)
        _require(actual["versions"] == checked["versions"] and actual["prefix"] == str(destination),
                 "Installed distribution versions or interpreter differ from verified lock")
        _verify_guard_startup(python)
        # Rehash the source after consumption; do not bless changed mounted bytes.
        after = validate_wheelhouse(source_lock_path, root, check_runtime=False)
        _require(all(after[key] == checked[key] for key in (
            "source_lock_sha256", "wheel_lock_sha256", "requirements_sha256", "versions")),
            "Wheelhouse changed during installation")
        prepared = _json(root / "wheel-lock.json")
        runtime_wheels = dict(prepared, python=actual["python"], platform=platform.platform(),
                              prepared_wheel_lock_sha256=checked["wheel_lock_sha256"],
                              prepared_python=prepared["python"])
        (evidence / "requirements.lock").write_bytes((root / "requirements.lock").read_bytes())
        _write(evidence / "wheel-lock.json", runtime_wheels)
        (evidence / "wheels").symlink_to(root / "wheels", target_is_directory=True)
        result = {
            "format": "irisx/arc-next-environment-lock-v1", "status": "installed-offline",
            "versions": actual["versions"], "python": actual["python"],
            "wheel_lock_sha256": _sha(evidence / "wheel-lock.json"),
            "prepared_wheel_lock_sha256": checked["wheel_lock_sha256"],
            "source_lock_sha256": checked["source_lock_sha256"],
            "complete_transitive_lock": True, "pip_offline_resolution_verified": True,
            "pip_check_passed": True, "isolated_venv": True, "target": dict(TARGET),
            "environment_lock": str(evidence / "environment-lock.json"),
            "wheel_lock": str(evidence / "wheel-lock.json"),
            "python_executable": str(python),
            "python_executable_sha256": _sha(python),
            "python_launcher_path": str(launcher),
            "python_launcher_sha256": _sha(launcher),
            "venv_config_sha256": _sha(destination / "pyvenv.cfg"),
            "python_command": [str(python), "-I", "-B", "-S", str(launcher)],
            "network_guard_path": str(guard_path),
            "network_guard_sha256": _sha(guard_path),
            "network_guard": "Python socket/DNS audit only; external InternetOFF boundary still required",
            "optional_backend_modules_absent": list(OPTIONAL_MODULES),
            "source": "verified mounted wheels; CPython ensurepip supplies only installer seed",
            "gpu_runtime_verified": False, "gpu_calls": 0,
        }
        result.update(_guard_hook_fields(destination))
        _write(evidence / "environment-lock.json", result)
        _write(destination / "installation-receipt.json", result)
        return result
    except Exception as exc:
        # A failed environment is retained for diagnosis and cannot be reused.
        _write(evidence / "installation-failed.json", {
            "status": "failed-installation-not-admitted", "error_type": type(exc).__name__,
            "gpu_runtime_verified": False,
        })
        raise


def _atomic_bytes(path: Path, body: bytes) -> None:
    """Replace a single task-owned file atomically; callers validate the pair."""
    descriptor, temporary = tempfile.mkstemp(prefix=".irisx-guard-", dir=path.parent)
    staging = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    finally:
        if staging.exists():
            staging.unlink()


def migrate_offline_guard(source_lock_path: str | Path, wheelhouse_root: str | Path,
                          environment_dir: str | Path, enabled: bool = False, *,
                          expected_legacy_receipt_sha256: str | None = None) -> dict[str, Any]:
    """Repair exactly one verified pre-hook v3 installation, disabled by default.

    No download, pip install, venv creation or OS-setting mutation occurs. The
    caller must bind the exact existing installation-receipt.json bytes. All
    legacy evidence and installed versions are validated before the first write.
    Original receipt bytes are retained verbatim inside both replacement receipts.
    Only the hook and two receipts change; each is replaced atomically. A process
    interruption between receipts leaves a mismatched, non-admitted pair and is
    deliberately not an automatic retry/recovery authorization.
    """
    _require(type(enabled) is bool, "Boolean owner switch required")
    if not enabled:
        return {"status": "disabled", "network_calls": 0, "install_calls": 0, "gpu_calls": 0}
    _require(_HASH.fullmatch(str(expected_legacy_receipt_sha256 or "")) is not None,
             "An exact expected legacy receipt SHA256 is required")
    runtime = _runtime()
    destination = _no_symlinks(environment_dir, directory=True)
    source = _no_symlinks(source_lock_path)
    root = _no_symlinks(wheelhouse_root, directory=True)
    _require(destination != root and root not in destination.parents and destination not in root.parents
             and destination not in source.parents,
             "Environment must be separate from immutable wheelhouse and source")
    paths = {key: _no_symlinks(destination / relative) for key, relative in {
        "receipt": "installation-receipt.json", "environment_lock": "evidence/environment-lock.json",
        "python": "bin/python", "launcher": "offline-run.py", "config": "pyvenv.cfg",
        "guard": "lib/python3.12/site-packages/sitecustomize.py",
        "wheel_lock": "evidence/wheel-lock.json", "requirements": "evidence/requirements.lock",
        "report": "evidence/pip-install-report.json",
    }.items()}
    snapshots = {key: path.read_bytes() for key, path in paths.items()}
    _require(hashlib.sha256(snapshots["receipt"]).hexdigest() == expected_legacy_receipt_sha256,
             "Legacy installation receipt differs from the exact expected digest")
    legacy = _json(paths["receipt"])
    _require(_json(paths["environment_lock"]) == legacy, "Legacy receipt pair differs")
    hook = destination / NETWORK_GUARD_HOOK_RELATIVE
    _require(not hook.exists() and not hook.is_symlink(), "Migration requires an exact pre-hook environment")
    _require(not (destination / "evidence/installation-failed.json").exists(),
             "Failed installations cannot be migrated")
    _require(hashlib.sha256(snapshots["guard"]).hexdigest() == _LEGACY_V3_GUARD_SHA256 and
             hashlib.sha256(snapshots["launcher"]).hexdigest() == _LEGACY_V3_LAUNCHER_SHA256,
             "Legacy guard or launcher differs from trusted v3 bytes")
    _require(_sha(paths["python"]) == _sha(Path(sys.executable).resolve()),
             "Legacy interpreter differs from this CPython executable")
    cfg = dict(line.split(" = ", 1) for line in snapshots["config"].decode().splitlines() if " = " in line)
    _require(cfg.get("include-system-site-packages") == "false", "Legacy venv must isolate host packages")
    checked = validate_wheelhouse(source, root, check_runtime=False)
    prepared = _json(root / "wheel-lock.json")
    wheels = _json(paths["wheel_lock"])
    expected_wheels = dict(prepared, python=runtime["python"], platform=runtime["platform"],
                           prepared_wheel_lock_sha256=checked["wheel_lock_sha256"],
                           prepared_python=prepared["python"])
    _require(wheels == expected_wheels, "Legacy runtime wheel evidence differs from prepared closure")
    _require(snapshots["requirements"] == (root / "requirements.lock").read_bytes(),
             "Legacy requirements evidence differs")
    link = destination / "evidence/wheels"
    _require(link.is_symlink() and link.resolve(strict=True) == (root / "wheels").resolve(strict=True),
             "Legacy wheels link differs from the exact mounted directory")
    _verify_report(paths["report"], root, prepared["files"])
    # Strict reconstruction rejects a changed layout, legacy claim, launcher,
    # source binding, or already migrated receipt instead of generalizing repair.
    expected = {
        "format": "irisx/arc-next-environment-lock-v1", "status": "installed-offline",
        "versions": checked["versions"], "python": runtime["python"],
        "wheel_lock_sha256": _sha(paths["wheel_lock"]),
        "prepared_wheel_lock_sha256": checked["wheel_lock_sha256"],
        "source_lock_sha256": checked["source_lock_sha256"],
        "complete_transitive_lock": True, "pip_offline_resolution_verified": True,
        "pip_check_passed": True, "isolated_venv": True, "target": dict(TARGET),
        "environment_lock": str(paths["environment_lock"]), "wheel_lock": str(paths["wheel_lock"]),
        "python_executable": str(paths["python"]), "python_executable_sha256": _sha(paths["python"]),
        "python_launcher_path": str(paths["launcher"]), "python_launcher_sha256": _sha(paths["launcher"]),
        "venv_config_sha256": _sha(paths["config"]),
        "python_command": [str(paths["python"]), *_LEGACY_V3_PYTHON_FLAGS, str(paths["launcher"])],
        "network_guard_path": str(paths["guard"]), "network_guard_sha256": _sha(paths["guard"]),
        "network_guard": "Python socket/DNS audit only; external InternetOFF boundary still required",
        "optional_backend_modules_absent": list(OPTIONAL_MODULES),
        "source": "verified mounted wheels; CPython ensurepip supplies only installer seed",
        "gpu_runtime_verified": False, "gpu_calls": 0,
    }
    _require(legacy == expected, "Legacy receipt differs from the exact trusted v3 installation layout")
    inspected = _run(paths["python"], r'''
import importlib.metadata, importlib.util, json, pathlib, sys
wanted = json.loads(sys.argv[1])
optional = json.loads(sys.argv[2])
site_root = pathlib.Path(sys.prefix) / "lib/python3.12/site-packages"
observed = {}
for distribution in importlib.metadata.distributions(path=[str(site_root)]):
    name = distribution.metadata["Name"].lower().replace("_", "-").replace(".", "-")
    assert name not in observed, "Duplicate installed distribution"
    observed[name] = distribution.version
assert set(observed) <= set(wanted) | {"pip"}, "Unexpected installed distribution"
assert all(importlib.util.find_spec(name) is None for name in optional), "Optional backend leaked"
print(json.dumps({"versions": {name: observed.get(name) for name in wanted}, "prefix": sys.prefix}))
''', [json.dumps(checked["versions"]), json.dumps(OPTIONAL_MODULES)])
    actual = json.loads(inspected.stdout)
    _require(actual == {"versions": checked["versions"], "prefix": str(destination)},
             "Installed versions or prefix differ from legacy lock")
    _run(paths["python"], _PIP_MAIN, ["check", "--isolated", "--disable-pip-version-check"])
    _require(all(path.read_bytes() == snapshots[key] for key, path in paths.items()),
             "Legacy evidence changed during migration validation")
    _require(_sha(source) == checked["source_lock_sha256"] and
             _sha(root / "wheel-lock.json") == checked["wheel_lock_sha256"] and
             _sha(root / "requirements.lock") == checked["requirements_sha256"],
             "Mounted locks changed during migration validation")
    hook_body = _network_guard_hook(destination, legacy_v3=True).encode()
    result = dict(legacy,
        network_guard_startup="exact-path-pth-v1",
        network_guard_startup_hook_path=str(hook),
        network_guard_startup_hook_sha256=hashlib.sha256(hook_body).hexdigest(),
        network_guard_migration={
            "format": "irisx/offline-guard-migration-v1",
            "legacy_installation_receipt_sha256": expected_legacy_receipt_sha256,
            "legacy_environment_lock_sha256": hashlib.sha256(snapshots["environment_lock"]).hexdigest(),
            "legacy_installation_receipt_utf8": snapshots["receipt"].decode("utf-8"),
            "legacy_environment_lock_utf8": snapshots["environment_lock"].decode("utf-8"),
            "network_calls": 0, "install_calls": 0, "gpu_calls": 0,
        })
    receipt_body = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    _atomic_bytes(hook, hook_body)
    # Do not bless the upgrade until ordinary and spawned starts enforce denial.
    # If verification fails, the legacy receipts remain intact and non-admitted.
    _verify_guard_startup(paths["python"])
    _atomic_bytes(paths["environment_lock"], receipt_body)
    _atomic_bytes(paths["receipt"], receipt_body)
    _require(_json(paths["receipt"]) == result == _json(paths["environment_lock"]),
             "Migrated receipt readback differs")
    return result
