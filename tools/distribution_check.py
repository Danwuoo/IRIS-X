"""Offline, non-editable wheel acceptance in isolated staging roots and a venv.

Only Git-tracked product/build inputs and the public P2 admission snapshot are
copied. Generated wheels, environments and raw command logs stay in --output.
This is developer self-validation, not independent acceptance or ARC validation.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

# Safe-path children do not add the script directory automatically. Only this
# source tool directory is admitted for the shared startup and snapshot helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from .suite_runner import controlled_python_command, controlled_python_environment, validate_child_startup
except ImportError:
    from suite_runner import controlled_python_command, controlled_python_environment, validate_child_startup


ROOT = Path(__file__).resolve().parents[1]
BUILD_INPUTS = ("src/irisx", "pyproject.toml", "tools/irisx_build_backend.py", "README.md")
ADMISSION_INPUTS = (
    "AGENTS.md", "PRODUCT_THESIS.md", "trials/p2-admission/admission.json",
    "docs/decisions/0001-adopt-product-oriented-domain-ai-specialization.md",
    "docs/decisions/0002-adopt-p1-contract-and-serialization-foundation.md",
    "docs/decisions/0003-record-p2-admission-block.md",
)
HASH_REFERENCE = "import json; print(json.dumps([hash('IRIS-X seed sentinel'), hash('synthetic engineering')]))"
INSTALLED_PROBE = (
    "import irisx,json,os,site,pathlib,sys; "
    "print(json.dumps({'origin':irisx.__file__,'prefix':sys.prefix,'site_paths':site.getsitepackages(),"
    "'editable_pth':[str(p) for s in site.getsitepackages() for p in pathlib.Path(s).glob('*editable*.pth')],"
    "'startup':{'flags':{name:getattr(sys.flags,name) for name in "
    "('optimize','safe_path','no_user_site','dont_write_bytecode','ignore_environment','isolated','hash_randomization')},"
    "'python_environment':{name:os.environ.get(name) for name in ('PYTHONHASHSEED','PYTHONDONTWRITEBYTECODE')}},"
    "'seed_hashes':[hash('IRIS-X seed sentinel'),hash('synthetic engineering')]}))"
)


def tracked_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", *BUILD_INPUTS], cwd=root,
        check=True, stdout=subprocess.PIPE,
    )
    return sorted(item for item in result.stdout.decode("utf-8").split("\0") if item)


def copy_declared(root: Path, destination: Path, names: list[str] | tuple[str, ...]) -> None:
    for name in names:
        parts = PurePosixPath(name).parts
        if not parts or any(part in ("", ".", "..") for part in name.split("/")) or "\\" in name or ":" in name:
            raise ValueError(f"unsafe source path: {name}")
        source = root.joinpath(*parts)
        for parent in (source, *source.parents):
            if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
                raise ValueError(f"linked source input: {name}")
            if parent == root:
                break
        if not source.is_file() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"missing or unsafe declared input: {name}")
        target = destination.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def stage_sources(root: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError(f"staging root already exists: {destination}")
    destination.mkdir(parents=True)
    names = tracked_paths(root)
    for required in ("src/irisx/__init__.py", "src/irisx/cli.py", "pyproject.toml", "tools/irisx_build_backend.py"):
        if required not in names:
            raise ValueError(f"required tracked input missing: {required}")
    copy_declared(root, destination, names)


def verify_wheel(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) != len({name.casefold() for name in names}):
            raise ValueError("duplicate or case-colliding wheel member")
        for name in names:
            if name.startswith("/") or "\\" in name or ":" in name or any(part in ("", ".", "..") for part in name.split("/")):
                raise ValueError(f"unsafe wheel member: {name}")
            if archive.getinfo(name).is_dir():
                raise ValueError(f"unexpected directory member: {name}")
        records = [name for name in names if name.endswith(".dist-info/RECORD")]
        if len(records) != 1:
            raise ValueError("wheel must have exactly one RECORD")
        record = records[0]
        rows = list(csv.reader(io.StringIO(archive.read(record).decode("utf-8"), newline="")))
        if any(len(row) != 3 for row in rows) or len(rows) != len(names) or {row[0] for row in rows} != set(names):
            raise ValueError("RECORD does not exactly cover wheel members")
        if len({row[0] for row in rows}) != len(rows):
            raise ValueError("duplicate RECORD entry")
        for name, digest, size in rows:
            if name == record:
                if digest or size:
                    raise ValueError("RECORD must have an empty self digest and size")
                continue
            data = archive.read(name)
            expected = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
            if digest != expected or size != str(len(data)):
                raise ValueError(f"RECORD integrity mismatch: {name}")
        forbidden = ("tests", "__pycache__", ".irisx", ".git", "credentials", "evaluator-inputs")
        if any(any(part in forbidden or part.startswith("test_") for part in name.split("/")) or name.endswith((".pyc", ".pth")) for name in names):
            raise ValueError("product wheel contains excluded or editable payload")
        package_resources = [name for name in names if name.startswith("irisx/") and not name.endswith(".py")]
        if package_resources != ["irisx/licenses/NeMo-RL-LICENSE.txt"]:
            raise ValueError(f"unexpected product resources: {package_resources}")
        if not any(name.endswith(".dist-info/licenses/NeMo-RL-LICENSE.txt") for name in names):
            raise ValueError("distribution license notice missing")
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "members": len(names), "record_verified": True}


def venv_python(path: Path) -> Path:
    return path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def check(output: Path, root: Path = ROOT) -> dict:
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    if output.is_symlink() or not output.resolve().is_relative_to(root.resolve() / ".irisx"):
        raise ValueError("output must be a new ignored .irisx directory in this checkout")
    output.mkdir(parents=True)
    report = {"schema": "irisx/distribution-self-check-v1", "status": "failed", "python": sys.version,
              "platform": platform.platform(), "commands": [], "scope": "synthetic engineering only", "independent_review": "pending"}
    report.update(target_commit=None, attestable=False, evidence_kind="development")
    report["head_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    environment = controlled_python_environment()
    environment.update({"PIP_NO_INDEX": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"})
    report["python_environment"] = {name: environment[name] for name in
                                    ("PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE")}

    def run(command: list[str], cwd: Path, expected: int = 0, *, native_console: bool = False) -> str:
        number = len(report["commands"]) + 1
        command_environment = environment
        if native_console:
            # A console executable cannot accept Python's interpreter flags.
            # Admit only these two fixed controls on the already scrubbed base.
            command_environment = dict(environment, PYTHONSAFEPATH="1", PYTHONNOUSERSITE="1")
        result = subprocess.run(command, cwd=cwd, env=command_environment, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / f"command-{number:02}.log").write_text(result.stdout, encoding="utf-8")
        receipt = {"argv": command, "cwd": str(cwd), "exit_code": result.returncode, "expected_exit_code": expected, "log": f"command-{number:02}.log"}
        if native_console:
            receipt["python_environment"] = {name: command_environment[name] for name in
                                              ("PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE", "PYTHONSAFEPATH", "PYTHONNOUSERSITE")}
        report["commands"].append(receipt)
        if result.returncode != expected:
            raise RuntimeError(f"command {number} returned {result.returncode}; expected {expected}; see command log")
        return result.stdout

    try:
        # Formal evidence uses the same committed raw-Git source as suite reports;
        # neither staged/dirty inputs nor caller edits can supply wheel bytes.
        try:
            from .source_identity import create_snapshot
        except ImportError:
            from source_identity import create_snapshot
        source_snapshot = create_snapshot(root, output / "source", require_committed=True)
        root = source_snapshot.root
        report.update(source_snapshot.binding)
        stages = [output / "stage-a", output / "stage-b"]
        for stage in stages:
            stage_sources(root, stage)
        builder = output / "builder-venv"
        run(controlled_python_command(sys.executable, "-m", "venv", str(builder)), output)
        builder_python = str(venv_python(builder))
        wheels = []
        for stage in stages:
            wheel_dir = stage / "wheelhouse"
            run(controlled_python_command(builder_python, "-m", "pip", "wheel", "--no-index", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheel_dir), str(stage)), stage)
            matches = list(wheel_dir.glob("*.whl"))
            if len(matches) != 1:
                raise ValueError("expected exactly one wheel per staging root")
            wheels.append(matches[0])
        wheel_reports = [verify_wheel(path) for path in wheels]
        if wheel_reports[0]["sha256"] != wheel_reports[1]["sha256"]:
            raise ValueError("clean staging builds are not byte reproducible")
        report["wheels"] = wheel_reports
        consumer = output / "consumer-venv"
        run(controlled_python_command(sys.executable, "-m", "venv", str(consumer)), output)
        python = str(venv_python(consumer))
        with tempfile.TemporaryDirectory(prefix="irisx-external-wheel-") as temporary:
            external = Path(temporary).resolve()
            if external.is_relative_to(root.resolve()):
                raise ValueError("external smoke cwd unexpectedly inside source checkout")
            run(controlled_python_command(python, "-m", "pip", "install", "--no-index", "--no-deps", str(wheels[0])), external)
            reference = json.loads(run(controlled_python_command(python, "-c", HASH_REFERENCE), external))
            origin = json.loads(run(controlled_python_command(python, "-c", INSTALLED_PROBE), external))
            if validate_child_startup(origin.get("startup")) or origin.get("seed_hashes") != reference:
                raise ValueError("installed interpreter startup or same-interpreter seed reference mismatch")
            if not Path(origin["origin"]).resolve().is_relative_to(consumer.resolve()) or origin["editable_pth"]:
                raise ValueError("package origin is not the non-editable consumer venv")
            report["installation"] = {**origin, "external_cwd": str(external), "pythonpath_removed": True, "non_editable": True}
            commands = [
                ["--help"], ["fixture", "prepare", "--output", str(external / "fixture")],
                ["spec", "validate", str(external / "fixture/specification.json")],
                ["trial", "validate", str(external / "fixture/trial.json")],
                ["trial", "run", "--trial", str(external / "fixture/trial.json"), "--output", str(external / "run")],
                ["package", "build", "--run", str(external / "run"), "--output", str(external / "package")],
                ["package", "verify", str(external / "package")],
            ]
            for args in commands:
                run(controlled_python_command(python, "-m", "irisx", *args), external)
            if (root / "src/irisx/domains/arc_agi_2/cli.py").is_file():
                run(controlled_python_command(python, "-m", "irisx", "arc-agi-2", "--help"), external)
                run(controlled_python_command(python, "-m", "irisx", "arc-agi-2", "source", "validate", str(external / "missing-arc-source")), external, expected=2)
                report["arc_parser_facade"] = "passed (help and missing-path error only)"
            if (root / "src/irisx/domains/line_b/flow.py").is_file():
                run(controlled_python_command(python, "-m", "irisx.domains.line_b.flow", "--output", str(external / "line-b")), external)
                result = json.loads((external / "line-b/handoff.json").read_text(encoding="utf-8"))
                if result.get("scope") != "synthetic engineering-only non-deployable" or result.get("package_created") is not True:
                    raise ValueError("installed line-b did not complete the synthetic package loop")
                report["line_b_synthetic_flow"] = "passed"
            cli = consumer / ("Scripts/irisx.exe" if os.name == "nt" else "bin/irisx")
            # Execute the installed script itself under the controlled consumer
            # interpreter. The Windows distlib .exe contains a Python zip entry.
            run(controlled_python_command(python, str(cli), "--help"), external)
            native_probe = json.loads(run([python, "-B", "-c", INSTALLED_PROBE], external, native_console=True))
            if validate_child_startup(native_probe.get("startup"), optimize=0) or native_probe.get("seed_hashes") != reference:
                raise ValueError("native-console environment support probe does not enforce startup controls")
            run([str(cli), "--help"], external, native_console=True)
            report["native_console"] = {
                "environment_support_probe": native_probe["startup"],
                "seed_reference_matched": True,
                "native_cli_flags_readback": "not introspected; separate same-interpreter support probe only",
            }
            copy_declared(root, external / "public-admission", ADMISSION_INPUTS)
            run(controlled_python_command(python, "-m", "irisx", "admission", "validate", str(external / "public-admission/trials/p2-admission/admission.json")), external)
            run(controlled_python_command(python, "-m", "irisx", "package", "verify", str(external / "missing")), external, expected=2)
            report["synthetic_reference_flow"] = "passed"
        source_changes = source_snapshot.changes()
        if source_changes:
            report.update(target_commit=None, attestable=False, evidence_kind="development", source_changes=source_changes)
            raise ValueError("source changed during formal validation")
        report["status"] = "passed"
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = check(args.output.resolve())
    except (OSError, ValueError) as error:
        report = {"schema": "irisx/distribution-self-check-v1", "status": "failed", "error": str(error)}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
