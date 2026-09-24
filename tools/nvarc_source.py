"""Explicit network materialization and offline verification of pinned NVARC code.

The source tree is ignored local material. This command never runs a notebook,
loads model weights, or opens ARC answer files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / ".irisx/arc-agi-2/qwen35-nvarc/source"
MANIFEST = ROOT / "trials/arc-agi-2-qwen35-nvarc/source-manifest.json"


def run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True, encoding="utf-8").strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_digest(manifest: dict) -> str:
    encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def repositories(source: Path, manifest: dict):
    main = source / "NVARC"
    for name, info in manifest["git"].items():
        yield name, main if name == "NVARC" else main / info["path"], info


def require_clean_repo(name: str, repo: Path) -> None:
    """Reject changed source and executable additions in each repository.

    Only bytecode from the three source modules the adapter compiles directly
    from checked source is allowed. Those cache files cannot replace the code
    used by the integration. All other untracked and ignored files fail closed.
    """
    top = Path(run("git", "rev-parse", "--show-toplevel", cwd=repo)).resolve()
    if top != repo.resolve():
        raise ValueError(f"{name} is not an independent Git checkout")
    # Git status trusts assume-unchanged and skip-worktree bits. Reject those
    # flags instead of allowing a changed tracked file to hide behind them.
    for line in run("git", "ls-files", "-v", cwd=repo).splitlines():
        if line and (line[0].islower() or line[0] == "S"):
            raise ValueError(f"{name} tracked file bypass flag: {line}")
    status = run("git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
                 "status", "--porcelain=v1", "--untracked-files=all",
                 "--ignored=matching", "--ignore-submodules=all", cwd=repo)
    permitted = {
        "NVARC": (r"SDG/scripts/__pycache__/build_datasets\.cpython-\d+\.pyc",),
        "TinyRecursiveModels": (
            r"dataset/__pycache__/build_arc_dataset\.cpython-\d+\.pyc",
            r"dataset/__pycache__/common\.cpython-\d+\.pyc"),
    }
    for line in status.splitlines():
        if line[:2] in ("??", "!!") and any(
                re.fullmatch(pattern, line[3:]) for pattern in permitted.get(name, ())):
            continue
        raise ValueError(f"{name} index/worktree is dirty: {line}")


def verify_git(source: Path, manifest: dict) -> None:
    main = source / "NVARC"
    expected = manifest["git"]
    for name, repo, info in repositories(source, manifest):
        if run("git", "rev-parse", "HEAD", cwd=repo) != info["commit"]:
            raise ValueError(f"{name} commit differs")
        require_clean_repo(name, repo)
        if info.get("notice"):
            notice = repo / info["notice"]["path"]
            if sha256(notice) != info["notice"]["sha256"]:
                raise ValueError(f"{name} license/notice differs")
    dirty = run("git", "submodule", "status", "--recursive", cwd=main).splitlines()
    if len(dirty) != len(expected) - 1 or any(line.startswith(("-", "+", "U")) for line in dirty):
        raise ValueError(f"recursive submodules incomplete or changed: {dirty}")


def verify(source: Path, manifest: dict) -> dict:
    main = source / "NVARC"
    expected = manifest["git"]
    verify_git(source, manifest)
    for name, info in manifest["notebooks"].items():
        file = source / info["path"]
        if sha256(file) != info["sha256"]:
            raise ValueError(f"{name} notebook bytes differ")
        notebook = json.loads(file.read_text(encoding="utf-8"))
        if not notebook.get("cells"):
            raise ValueError(f"{name} notebook has no cells")
    for name, info in manifest["code_files"].items():
        if sha256(main / name) != info["sha256"]:
            raise ValueError(f"{name} source bytes differ")
    return {"source_ready": True, "git_repositories": len(expected),
            "notebooks": len(manifest["notebooks"]), "code_files": len(manifest["code_files"]),
            "data_ready": False, "model_ready": False}


def materialize(source: Path, manifest: dict) -> None:
    """Reuse verified cache, otherwise acquire pinned bytes and fail closed."""
    try:
        verify(source, manifest)
        return
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError):
        pass
    main = source / "NVARC"
    source.mkdir(parents=True, exist_ok=True)
    try:
        verify_git(source, manifest)
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError):
        if main.exists():
            for name, repo, _ in repositories(source, manifest):
                if repo.exists():
                    require_clean_repo(name, repo)
        if not main.exists():
            subprocess.run(["git", "clone", "--filter=blob:none", manifest["git"]["NVARC"]["url"],
                            str(main)], check=True)
        subprocess.run(["git", "remote", "set-url", "origin", manifest["git"]["NVARC"]["url"]],
                       cwd=main, check=True)
        subprocess.run(["git", "fetch", "origin", manifest["git"]["NVARC"]["commit"]], cwd=main, check=True)
        subprocess.run(["git", "checkout", "--detach", manifest["git"]["NVARC"]["commit"]], cwd=main, check=True)
        subprocess.run(["git", "submodule", "update", "--init", "--recursive", "--filter=blob:none"],
                       cwd=main, check=True)
    for name, info in manifest["notebooks"].items():
        destination = source / info["path"]
        if destination.exists():
            if sha256(destination) != info["sha256"]:
                raise ValueError(f"{name} cached notebook bytes differ")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        pending = destination.with_suffix(destination.suffix + ".pending")
        pending.unlink(missing_ok=True)
        try:
            observed, content = fetch_current_notebook(info)
            if observed != info["version_number"]:
                raise ValueError(f"{name} current version {observed} differs from pinned {info['version_number']}")
            pending.write_bytes(content)
            if sha256(pending) != info["sha256"]:
                raise ValueError(f"{name} pulled bytes differ from pinned notebook")
            os.replace(pending, destination)
        finally:
            pending.unlink(missing_ok=True)


def fetch_current_notebook(info: dict) -> tuple[int, bytes]:
    """Network fallback only when the exact cached notebook is absent.

    Kaggle's historical versioned pull returned HTTP 403 for the pinned TRM
    version, so the verified local bundle is the stable offline rebuild path.
    """
    from kaggle.api import kaggle_api_extended as kaggle

    api = kaggle.KaggleApi()
    api.authenticate()
    with api.build_kaggle_client() as client:
        owner, slug = info["ref"].split("/")
        request = kaggle.ApiGetKernelRequest()
        request.user_name, request.kernel_slug = owner, slug
        response = client.kernels.kernels_api_client.get_kernel(request)
        return response.metadata.current_version_number, response.blob.source.encode("utf-8")


def export_bundle(source: Path, manifest: dict, bundle: Path) -> None:
    """Export a relocatable local source tree after full verification.

    A Git bundle cannot be made from Kaggle's partial-blob Git clones: prior
    history may contain objects absent locally. Copying the checked checkout,
    including its Git object stores, preserves the exact pinned HEAD offline.
    """
    source = source.resolve()
    bundle = bundle.resolve()
    verify(source, manifest)
    if bundle.is_relative_to(source):
        raise ValueError("source bundle cannot be inside its source tree")
    if bundle.exists():
        raise ValueError("source bundle destination must be new")
    bundle.mkdir(parents=True)
    shutil.copytree(source / "NVARC", bundle / "NVARC", symlinks=True)
    record = {"format": "irisx/nvarc-local-source-bundle-v2",
              "source_manifest_sha256": manifest_digest(manifest),
              "files": {}, "notebooks": {}}
    for index, (name, info) in enumerate(manifest["notebooks"].items()):
        filename = f"notebooks/notebook-{index:03d}.ipynb"
        destination = bundle / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / info["path"], destination)
        record["notebooks"][name] = filename
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink():
            raise ValueError("source bundle cannot contain symbolic links")
        if path.is_file():
            record["files"][path.relative_to(bundle).as_posix()] = {
                "sha256": sha256(path), "bytes": path.stat().st_size}
    (bundle / "source-bundle.json").write_text(
        json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def import_bundle(source: Path, manifest: dict, bundle: Path) -> None:
    """Rebuild a new source cache from verified local members; no network."""
    source = source.resolve()
    bundle = bundle.resolve()
    if source.exists() and (not source.is_dir() or any(source.iterdir())):
        raise ValueError("bundle import needs an empty source destination")
    record = json.loads((bundle / "source-bundle.json").read_text(encoding="utf-8"))
    if (record.get("format") != "irisx/nvarc-local-source-bundle-v2" or
            record.get("source_manifest_sha256") != manifest_digest(manifest) or
            set(record.get("notebooks", {})) != set(manifest["notebooks"])):
        raise ValueError("source bundle manifest identity differs")
    for index, (name, info) in enumerate(manifest["notebooks"].items()):
        filename = f"notebooks/notebook-{index:03d}.ipynb"
        if record["notebooks"][name] != filename or record["files"].get(filename, {}).get("sha256") != info["sha256"]:
            raise ValueError(f"source bundle notebook identity differs: {name}")
    expected_files = set(record["files"])
    if (not expected_files or any(not (name.startswith("NVARC/") or
            name.startswith("notebooks/")) or ".." in Path(name).parts or
            "\\" in name for name in expected_files)):
        raise ValueError("source bundle member path is unsafe")
    actual_files = set()
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise ValueError("source bundle contains symbolic links")
        if path.is_file():
            actual_files.add(path.relative_to(bundle).as_posix())
    if actual_files != expected_files | {"source-bundle.json"}:
        raise ValueError("source bundle has missing or unexpected members")
    for name, info in record["files"].items():
        path = bundle / name
        if path.stat().st_size != info.get("bytes") or sha256(path) != info.get("sha256"):
            raise ValueError(f"source bundle member differs: {name}")
    source.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundle / "NVARC", source / "NVARC")
    for index, (_, info) in enumerate(manifest["notebooks"].items()):
        destination = source / info["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle / f"notebooks/notebook-{index:03d}.ipynb", destination)
    verify(source, manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "materialize", "export-bundle"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--bundle", type=Path,
                        help="local verified bundle; import on materialize, output on export-bundle")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.command == "export-bundle":
        if args.bundle is None:
            parser.error("export-bundle requires --bundle")
        export_bundle(args.source, manifest, args.bundle)
        print(json.dumps({"bundle": str(args.bundle), "source_manifest_sha256":
                          manifest_digest(manifest)}, indent=2))
        return
    if args.command == "materialize":
        if args.bundle is None:
            materialize(args.source, manifest)
        else:
            import_bundle(args.source, manifest, args.bundle)
    elif args.bundle is not None:
        parser.error("verify does not take --bundle")
    print(json.dumps(verify(args.source, manifest), indent=2))


if __name__ == "__main__":
    main()
