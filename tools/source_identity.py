"""Bind test execution to isolated source bytes, independently of working HEAD.

Commit manifests hash Git path/mode/blob metadata only. Snapshot verification
also hashes the actually executed regular-file bytes before and after each child.
Development snapshots remain useful but never attest a commit.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess


class SourceIdentityError(ValueError):
    pass


def _git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *arguments], cwd=root, capture_output=True)
    if check and result.returncode:
        raise SourceIdentityError(f"Git source operation failed: {arguments[0]}")
    return result


def _safe(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or PurePosixPath(value).is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise SourceIdentityError(f"unsafe source path: {value}")
    path = root
    for part in value.split("/"):
        path /= part
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise SourceIdentityError(f"linked source path: {value}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise SourceIdentityError(f"escaping source path: {value}")
    return path


def validate_manifest(entries: list[dict]) -> None:
    names = set()
    components = {}
    for entry in entries:
        if set(entry) != {"path", "mode", "blob"} or entry["mode"] not in {"100644", "100755"}:
            raise SourceIdentityError("source manifest requires regular blobs; links/submodules denied")
        name = entry["path"]
        if not isinstance(name, str) or not name or "\\" in name or ":" in name or PurePosixPath(name).is_absolute() or any(p in ("", ".", "..") for p in name.split("/")):
            raise SourceIdentityError("unsafe source manifest path")
        if entry["path"].startswith((".git/", ".irisx/")) or entry["path"] in {".git", ".irisx"}:
            raise SourceIdentityError("source manifest cannot include Git/output directories")
        if entry["path"].casefold() in names:
            raise SourceIdentityError("source manifest path/case collision")
        names.add(entry["path"].casefold())
        parts = name.split("/")
        for count in range(1, len(parts) + 1):
            prefix = "/".join(parts[:count])
            previous = components.setdefault(prefix.casefold(), prefix)
            if previous != prefix:
                raise SourceIdentityError("source manifest parent path/case collision")
        if len(entry["blob"]) != 40 or any(c not in "0123456789abcdef" for c in entry["blob"]):
            raise SourceIdentityError("invalid source blob identity")


def manifest_digest(entries: list[dict]) -> str:
    validate_manifest(entries)
    data = json.dumps(sorted(entries, key=lambda e: e["path"]), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def git_manifest(root: Path, commit: str) -> list[dict]:
    rows = _git(root, "ls-tree", "-r", "-z", "--full-tree", commit).stdout.split(b"\0")
    entries = []
    for row in rows:
        if not row:
            continue
        metadata, path = row.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        if kind != "blob":
            raise SourceIdentityError("non-blob source entry denied")
        entries.append({"path": path.decode("utf-8"), "mode": mode, "blob": blob})
    validate_manifest(entries)
    return sorted(entries, key=lambda e: e["path"])


def _paths(root: Path) -> list[str]:
    if (root / ".git").exists():
        result = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
        return sorted(set(name for name in result.stdout.decode("utf-8").split("\0") if name and not name.startswith(".irisx/")))
    result = []
    for directory, children, files in os.walk(root, followlinks=False):
        children[:] = sorted(c for c in children if c not in {".git", ".irisx", "__pycache__", ".venv", "venv"})
        for child in children:
            _safe(root, (Path(directory) / child).relative_to(root).as_posix())
        result.extend((Path(directory) / name).relative_to(root).as_posix() for name in files if not name.endswith((".pyc", ".pyo")))
    return sorted(result)


def _blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def actual_manifest(root: Path, modes: dict[str, str] | None = None) -> list[dict]:
    result = []
    for name in _paths(root):
        path = _safe(root, name)
        if not path.is_file():
            # A tracked deletion is material dirty input, not a hidden fallback.
            continue
        mode = (modes or {}).get(name, "100755" if os.name != "nt" and path.stat().st_mode & 0o111 else "100644")
        if os.name != "nt":
            mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        result.append({"path": name, "mode": mode, "blob": _blob(path.read_bytes())})
    validate_manifest(result)
    return result


def inspect_source(root: Path) -> dict:
    """Capture current source/input changes, including staged and untracked files."""
    root = Path(root).resolve()
    head, status, tree = None, None, None
    if (root / ".git").exists():
        revision = _git(root, "rev-parse", "--verify", "HEAD", check=False)
        if revision.returncode == 0:
            head = revision.stdout.decode().strip()
            tree = _git(root, "rev-parse", f"{head}^{{tree}}").stdout.decode().strip()
        state = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", check=False)
        if state.returncode == 0:
            status = state.stdout.decode("utf-8")
    entries = actual_manifest(root)
    payload = {"head_commit": head, "tree": tree, "git_status": status, "manifest": entries}
    return {**payload, "fingerprint": hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def _runner_matches(root: Path, commit: str, runner_path: Path) -> bool:
    try:
        for name, current in (("suite_runner.py", runner_path), ("source_identity.py", Path(__file__).resolve())):
            expected = _git(root, "show", f"{commit}:tools/{name}").stdout
            observed = current.read_bytes()
            # Python source newline normalization is the only accepted checkout
            # transformation. Do not invoke arbitrary Git clean/smudge filters.
            if expected != observed and expected != observed.replace(b"\r\n", b"\n"):
                return False
        return True
    except (OSError, SourceIdentityError):
        return False


def _clone_metadata(root: Path, destination: Path, commit: str) -> None:
    cloned = subprocess.run(["git", "clone", "--shared", "--no-checkout", "--", str(root), str(destination)], capture_output=True)
    if cloned.returncode:
        raise SourceIdentityError("local isolated Git clone failed")
    _git(destination, "config", "--local", "core.autocrlf", "false")
    _git(destination, "update-ref", "--no-deref", "HEAD", commit)
    _git(destination, "read-tree", commit)


def _write_committed_files(root: Path, destination: Path, entries: list[dict]) -> None:
    # cat-file reads raw immutable blobs. It executes no checkout filter,
    # smudge, hook or remote operation and therefore cannot fetch large assets.
    process = subprocess.Popen(["git", "cat-file", "--batch"], cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for entry in entries:
            process.stdin.write((entry["blob"] + "\n").encode("ascii"))
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii").strip().split()
            if len(header) != 3 or header[:2] != [entry["blob"], "blob"]:
                raise SourceIdentityError("unexpected committed blob response")
            size = int(header[2])
            data = process.stdout.read(size)
            if len(data) != size or process.stdout.read(1) != b"\n" or _blob(data) != entry["blob"]:
                raise SourceIdentityError("committed blob bytes differ")
            target = _safe(destination, entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if os.name != "nt":
                target.chmod(0o755 if entry["mode"] == "100755" else 0o644)
        process.stdin.close()
        process.wait(timeout=30)
        if process.returncode:
            raise SourceIdentityError("committed blob reader failed")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()


@dataclass
class SourceSnapshot:
    root: Path
    binding: dict
    manifest: list[dict]
    caller_root: Path
    caller_before: dict

    def changes(self) -> list[str]:
        errors = []
        try:
            modes = {e["path"]: e["mode"] for e in self.manifest}
            if actual_manifest(self.root, modes) != self.manifest:
                errors.append("executed source snapshot changed")
            if inspect_source(self.caller_root)["fingerprint"] != self.caller_before["fingerprint"]:
                errors.append("caller source/input state changed during execution")
        except (OSError, SourceIdentityError) as error:
            errors.append(str(error))
        return errors


def create_snapshot(root: Path, destination: Path, *, require_committed: bool = False, runner_path: Path | None = None) -> SourceSnapshot:
    """Run clean committed bytes, or clearly label an isolated development copy.

    The local clone shares only immutable Git objects, never working-tree files.
    No remote fetch, provider, model or original training operation occurs.
    """
    root, destination = Path(root).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise SourceIdentityError("snapshot destination must be new")
    before = inspect_source(root)
    runner_path = runner_path or Path(__file__).with_name("suite_runner.py")
    commit = before["head_commit"]
    eligible = commit is not None and before["git_status"] == "" and _runner_matches(root, commit, runner_path)
    if require_committed and not eligible:
        raise SourceIdentityError("commit evidence requires a clean Git checkout with the committed runner/source-identity helper")
    if eligible:
        entries = git_manifest(root, commit)
        _clone_metadata(root, destination, commit)
        _write_committed_files(root, destination, entries)
        actual = actual_manifest(destination, {e["path"]: e["mode"] for e in entries})
        if actual != entries:
            raise SourceIdentityError("isolated checkout differs from exact committed blob bytes")
    else:
        if commit is not None:
            _clone_metadata(root, destination, commit)
        else:
            destination.mkdir(parents=True)
        for entry in before["manifest"]:
            source = _safe(root, entry["path"])
            target = _safe(destination, entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if os.name != "nt":
                target.chmod(0o755 if entry["mode"] == "100755" else 0o644)
        # Synthetic no-Git test roots need the controlled harness itself. These
        # injected tool bytes are explicit development evidence, never a commit.
        for name in ("suite_runner.py", "source_identity.py", "workstream_management.py"):
            target = destination / "tools" / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(__file__).with_name(name), target)
        entries = actual_manifest(destination)
    if inspect_source(root)["fingerprint"] != before["fingerprint"]:
        raise SourceIdentityError("caller source changed while snapshot was prepared")
    identities = {e["path"]: e["blob"] for e in entries}
    binding = {"attestable": eligible, "evidence_kind": "commit" if eligible else "development",
               "target_commit": commit if eligible else None, "head_commit": commit,
               "inventory_blob": identities.get("tests/inventory.json"), "runner_blob": identities.get("tools/suite_runner.py"),
               "source_identity": {"format": "irisx.source-identity.v1", "commit": commit if eligible else None,
                                   "tree": before["tree"] if eligible else None, "manifest_sha256": manifest_digest(entries)}}
    return SourceSnapshot(destination, binding, entries, root, before)


def verify_binding(root: Path, binding: dict) -> list[str]:
    """Recheck a child's claimed committed identity before importing its test."""
    if binding.get("evidence_kind") != "commit":
        return []
    try:
        commit = binding["target_commit"]
        entries = git_manifest(root, commit)
        identity = binding["source_identity"]
        observed_tree = _git(root, "rev-parse", f"{commit}^{{tree}}").stdout.decode().strip()
        head = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
        if (binding.get("attestable") is not True or head != commit or identity.get("commit") != commit
                or identity.get("tree") != observed_tree or identity.get("manifest_sha256") != manifest_digest(entries)
                or actual_manifest(root, {e["path"]: e["mode"] for e in entries}) != entries):
            return ["child committed source identity does not match executed snapshot"]
        blobs = {e["path"]: e["blob"] for e in entries}
        if binding.get("inventory_blob") != blobs.get("tests/inventory.json") or binding.get("runner_blob") != blobs.get("tools/suite_runner.py"):
            return ["child inventory/runner binding differs"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        return [str(error)]
    return []
