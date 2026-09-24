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


def verify(source: Path, manifest: dict) -> dict:
    main = source / "NVARC"
    expected = manifest["git"]
    if run("git", "rev-parse", "HEAD", cwd=main) != expected["NVARC"]["commit"]:
        raise ValueError("NVARC commit differs")
    for name, info in expected.items():
        repo = main if name == "NVARC" else main / info["path"]
        if run("git", "rev-parse", "HEAD", cwd=repo) != info["commit"]:
            raise ValueError(f"{name} commit differs")
        if info.get("notice"):
            notice = repo / info["notice"]["path"]
            if sha256(notice) != info["notice"]["sha256"]:
                raise ValueError(f"{name} license/notice differs")
    dirty = run("git", "submodule", "status", "--recursive", cwd=main).splitlines()
    if len(dirty) != len(expected) - 1 or any(line.startswith(("-", "+", "U")) for line in dirty):
        raise ValueError("recursive submodules incomplete or changed")
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
    """The sole intentional network path; exact identities are checked below."""
    main = source / "NVARC"
    source.mkdir(parents=True, exist_ok=True)
    if not main.exists():
        subprocess.run(["git", "clone", "--filter=blob:none", manifest["git"]["NVARC"]["url"],
                        str(main)], check=True)
    subprocess.run(["git", "remote", "set-url", "origin", manifest["git"]["NVARC"]["url"]],
                   cwd=main, check=True)
    subprocess.run(["git", "fetch", "origin", manifest["git"]["NVARC"]["commit"]], cwd=main, check=True)
    subprocess.run(["git", "checkout", "--detach", manifest["git"]["NVARC"]["commit"]], cwd=main, check=True)
    subprocess.run(["git", "submodule", "update", "--init", "--recursive", "--filter=blob:none"],
                   cwd=main, check=True)
    # Kaggle's versioned pull currently returns HTTP 403 even for public old
    # versions. Pull the frozen current version only after checking its number,
    # then enforce the exact source hash. A later version fails closed.
    from kaggle.api import kaggle_api_extended as kaggle

    api = kaggle.KaggleApi()
    api.authenticate()
    with api.build_kaggle_client() as client:
        for name, info in manifest["notebooks"].items():
            owner, slug = info["ref"].split("/")
            request = kaggle.ApiGetKernelRequest()
            request.user_name, request.kernel_slug = owner, slug
            response = client.kernels.kernels_api_client.get_kernel(request)
            observed = response.metadata.current_version_number
            if observed != info["version_number"]:
                raise ValueError(f"{name} current version {observed} differs from pinned {info['version_number']}")
            destination = source / info["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            pending = destination.with_suffix(destination.suffix + ".pending")
            try:
                pending.write_text(response.blob.source, encoding="utf-8")
                if sha256(pending) != info["sha256"]:
                    raise ValueError(f"{name} pulled bytes differ from pinned notebook")
                os.replace(pending, destination)
            finally:
                pending.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "materialize"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.command == "materialize":
        materialize(args.source, manifest)
    print(json.dumps(verify(args.source, manifest), indent=2))


if __name__ == "__main__":
    main()
