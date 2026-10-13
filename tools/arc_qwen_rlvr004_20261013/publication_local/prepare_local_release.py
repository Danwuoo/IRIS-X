"""Restore the exact code17 operational candidate from authorized local inputs.

The output must be fresh and inside the repository's ignored .irisx directory.
The original runtime_assembly.py is authenticated and executed without importing
producer/model code. The private predecessor archive is only streamed for its
exact size/hash and copied; its ZIP members and evaluator bodies are never read.

This restores historical release bytes, not publication authority or run success.
Local operator adaptations need new exact material/transport/monitor reviews.
If provider versions differ, bind a separate successor manifest, all notebook
code pins, SDK numeric versions, receipts, collector paths and consumer callsite
pins together. Every new attempt needs its own identity, state and JIT epoch;
never patch an already submitted active notebook or reset a consumed run clock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys


DEPLOYMENT = Path("tools/arc_qwen_rlvr004_20261013")
PREDECESSOR_NAME = "predecessor/irisx-qwen14b-rlvr-20261012-run003.evidence.zip"
PREDECESSOR_BYTES = 20130674
PREDECESSOR_SHA256 = "4f24e0e44455d0862d72803c1a852294e26d52ca0335a1fe2393406e235b4b65"
SOURCE_ARCHIVE_SHA256 = "778ac5474a176358e0789cd3b82db5d91278864724507dc56d6c33bf6cdefb9e"
SOURCE_SHA256 = "22a736bd06f10a5708a0b0c69ac3b89128394e3775c0780d19d1b999b8cc1ba1"
PINS = {
    "runtime_assembly.py": "acc71ddcc26e962b8339bda0b0d93e65ce7cc02a226a0f511a06de2a1fd9a1f9",
    "runtime-path-map.json": "0b77706cd31729f4e88f4937ca5f2749c1b8711e2890fee0ca863bbaf779fd38",
    "ASSEMBLY-INVENTORY.json": "17b644b2d10dd134f00208d60529a59720fa8233fef46632f1e529a99784fa65",
    "publication-manifest.json": "4dbd7daa4d7817970f702aaff32f9783d529c8b136e92536c788826e24d3cac1",
    "OPERATIONAL-ARTIFACT-OMISSIONS.json": "6cb2a0ceac2318e3875ad990d4af7b1fcbdec6c8f0dc7fd301645a942d98387b",
}
FILE_CAP = 64 * 1024**2
TREE_BYTES_CAP = 128 * 1024**2
TREE_FILES_CAP = 2000


class PreparationError(ValueError):
    """An input has not met the exact historical restoration contract."""


def need(value: bool, message: str) -> None:
    if not value:
        raise PreparationError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def relative_name(name: str) -> str:
    need(type(name) is str and bool(name), "relative file name required")
    path = PurePosixPath(name)
    need(not path.is_absolute() and "\\" not in name and ":" not in name
         and str(path) == name and all(part not in ("", ".", "..") for part in path.parts),
         "unsafe relative file name")
    return name


def ordinary_path(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        need(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, "st_file_attributes", 0) & 0x400,
             "linked or reparse path forbidden")
    return path


def identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    # Windows path-stat and handle-fstat expose different legacy ctime meanings
    # on Python 3.14. Both expose the same explicit birth time; POSIX retains
    # its inode change time. Content is independently hash-bound in all cases.
    stamp = getattr(info, "st_birthtime_ns", info.st_ctime_ns) if os.name == "nt" else info.st_ctime_ns
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, stamp)


def file_descriptor(path: Path, cap: int = FILE_CAP) -> dict:
    path = ordinary_path(path)
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 <= info.st_size <= cap,
         "bounded single-link regular file required")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        need(identity(os.fstat(stream.fileno())) == identity(info), "file changed before read")
        for block in iter(lambda: stream.read(1024**2), b""):
            size += len(block)
            need(size <= cap, "file exceeded byte cap")
            digest.update(block)
        need(identity(os.fstat(stream.fileno())) == identity(info), "file changed during read")
    need(identity(path.stat()) == identity(info) and size == info.st_size, "file changed after read")
    return {"bytes": size, "sha256": digest.hexdigest()}


def checked_bytes(path: Path, expected: dict | None = None) -> bytes:
    descriptor = file_descriptor(path)
    if expected is not None:
        need(descriptor == expected, "exact file descriptor mismatch: " + path.name)
    raw = ordinary_path(path).read_bytes()
    need(len(raw) == descriptor["bytes"] and sha(raw) == descriptor["sha256"],
         "file changed before materialization")
    return raw


def pinned_bytes(path: Path, pin: str) -> bytes:
    raw = checked_bytes(path)
    need(sha(raw) == pin, "historical input pin mismatch: " + path.name)
    return raw


def strict_json(raw: bytes) -> dict:
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda value: (_ for _ in ()).throw(
                           PreparationError("nonfinite JSON number")))
    need(type(value) is dict, "JSON object required")
    return value


def tree_files(root: Path) -> set[str]:
    root = ordinary_path(root)
    need(root.is_dir(), "ordinary input directory required")
    names = set()
    total = 0
    pending = [root]
    while pending:
        current = pending.pop()
        for child in current.iterdir():
            child = ordinary_path(child)
            info = child.lstat()
            if stat.S_ISDIR(info.st_mode):
                pending.append(child)
            else:
                need(stat.S_ISREG(info.st_mode), "special tree entry forbidden")
                name = relative_name(child.relative_to(root).as_posix())
                names.add(name)
                total += info.st_size
                need(len(names) <= TREE_FILES_CAP and total <= TREE_BYTES_CAP,
                     "bounded release tree required")
    return names


def verify_predecessor(path: Path) -> dict:
    expected = {"bytes": PREDECESSOR_BYTES, "sha256": PREDECESSOR_SHA256}
    need(file_descriptor(path, PREDECESSOR_BYTES) == expected,
         "exact original predecessor archive required")
    return expected


def copy_predecessor(source: Path, destination: Path, expected: dict) -> None:
    """Copy a hash-bound body without ZIP parsing or evaluator access."""
    source = ordinary_path(source)
    destination = ordinary_path(destination)
    need(not destination.exists(), "fresh predecessor destination required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    ordinary_path(destination.parent)
    before = source.stat()
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        need(identity(os.fstat(incoming.fileno())) == identity(before), "archive changed before copy")
        for block in iter(lambda: incoming.read(1024**2), b""):
            size += len(block)
            need(size <= PREDECESSOR_BYTES, "archive exceeded exact bound")
            digest.update(block)
            outgoing.write(block)
        outgoing.flush()
        os.fsync(outgoing.fileno())
        need(identity(os.fstat(incoming.fileno())) == identity(before), "archive changed during copy")
    need(identity(source.stat()) == identity(before)
         and {"bytes": size, "sha256": digest.hexdigest()} == expected,
         "archive copy descriptor mismatch")


def prepare_local_release(*, repository_root: Path, delivery_root: Path,
                          predecessor_evidence: Path, output_root: Path) -> dict:
    repo = ordinary_path(repository_root)
    delivery = ordinary_path(delivery_root)
    evidence = ordinary_path(predecessor_evidence)
    output = ordinary_path(output_root)
    scope = repo / ".irisx"
    need(repo.is_dir() and output.is_relative_to(scope) and output != scope,
         "fresh output must remain inside repository .irisx")
    need(not output.exists(), "fresh output required")
    need(not output.is_relative_to(delivery) and not delivery.is_relative_to(output)
         and not evidence.is_relative_to(output), "input/output overlap forbidden")
    need(delivery.is_dir(), "delivery release directory required")

    omission = strict_json(pinned_bytes(delivery.parent / "OPERATIONAL-ARTIFACT-OMISSIONS.json",
                                       PINS["OPERATIONAL-ARTIFACT-OMISSIONS.json"]))
    expected_evidence = {"bytes": PREDECESSOR_BYTES, "sha256": PREDECESSOR_SHA256}
    omitted = omission.get("omitted_operational_artifacts", {})
    need(omission.get("format") == "irisx/owner-source-operational-evidence-omission-v1"
         and omission.get("source_complete") is True
         and omission.get("operational_evidence_complete") is False
         and set(omitted) == {"release/" + PREDECESSOR_NAME}, "one exact operational omission required")
    record = omitted["release/" + PREDECESSOR_NAME]
    need(record.get("body_included") is False
         and {key: record.get(key) for key in expected_evidence} == expected_evidence,
         "omitted archive identity mismatch")
    # Verify this prerequisite before creating any output or running assembly.
    verify_predecessor(evidence)

    inventory_raw = pinned_bytes(delivery / "ASSEMBLY-INVENTORY.json", PINS["ASSEMBLY-INVENTORY.json"])
    inventory = strict_json(inventory_raw)
    for name, descriptor in inventory.items():
        relative_name(name)
        need(type(descriptor) is dict and set(descriptor) == {"bytes", "sha256"}
             and type(descriptor["bytes"]) is int and 0 <= descriptor["bytes"] <= FILE_CAP,
             "closed assembly descriptor required")
    need(inventory.get(PREDECESSOR_NAME) == expected_evidence, "inventory predecessor binding mismatch")
    generated = {name for name in inventory if name.startswith("producer-source/")}
    delivered = set(inventory) - generated - {PREDECESSOR_NAME}
    need(tree_files(delivery) == delivered | {"ASSEMBLY-INVENTORY.json"},
         "closed source-only delivery file set required")
    blobs = {name: checked_bytes(delivery / name, inventory[name]) for name in sorted(delivered)}
    need(sha(blobs["publication-manifest.json"]) == PINS["publication-manifest.json"],
         "original publication manifest required")

    source_base = repo / DEPLOYMENT
    script = source_base / "runtime_assembly.py"
    pinned_bytes(script, PINS["runtime_assembly.py"])
    mapping = strict_json(pinned_bytes(source_base / "runtime-path-map.json", PINS["runtime-path-map.json"]))
    freeze = strict_json(blobs["SOURCE-FREEZE.json"])
    need(mapping.get("format") == "irisx/rlvr-logical-runtime-path-map-v1"
         and mapping.get("source_member_count") == 259
         and mapping.get("source_archive_sha256") == SOURCE_ARCHIVE_SHA256
         and mapping.get("source_sha256") == SOURCE_SHA256
         and mapping.get("publication_manifest_sha256") == PINS["publication-manifest.json"],
         "exact code17 mapping required")
    members = mapping["files"]
    need(len(members) == 259 and generated == {"producer-source/" + name for name in members},
         "complete source member binding required")
    for name, record in members.items():
        relative_name(name)
        relative_name(record["repository_path"])
        descriptor = {key: record[key] for key in ("bytes", "sha256")}
        need(inventory["producer-source/" + name] == descriptor == freeze["files"][name],
             "source mapping/freeze/inventory mismatch")
        checked_bytes(repo / record["repository_path"], descriptor)
    need(sha(blobs["code-payload/source.zip"]) == SOURCE_ARCHIVE_SHA256
         and freeze.get("source_sha256") == SOURCE_SHA256, "original source archive required")

    output.parent.mkdir(parents=True, exist_ok=True)
    ordinary_path(output.parent)
    # The child compiles the very bytes it reauthenticates, so a source change
    # between the parent's check and Python startup cannot become executable.
    bootstrap = """from pathlib import Path
import hashlib, sys
path = Path(sys.argv[1])
with path.open('rb') as stream:
    raw = stream.read(1024**2 + 1)
if len(raw) > 1024**2 or hashlib.sha256(raw).hexdigest() != sys.argv[2]:
    raise ValueError('runtime assembly executable pin mismatch')
with path.with_name('runtime-path-map.json').open('rb') as stream:
    mapping_raw = stream.read(1024**2 + 1)
if len(mapping_raw) > 1024**2 or hashlib.sha256(mapping_raw).hexdigest() != sys.argv[3]:
    raise ValueError('runtime assembly mapping pin mismatch')
sys.argv = [str(path), *sys.argv[4:]]
exec(compile(raw, str(path), 'exec', dont_inherit=True), {'__name__': '__main__', '__file__': str(path)})
"""
    process = subprocess.run(
        [sys.executable, "-I", "-B", "-c", bootstrap, str(script), PINS["runtime_assembly.py"],
         PINS["runtime-path-map.json"], "--repository-root", str(repo),
         "--output-root", str(output)],
        cwd=str(repo), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=120, check=False,
    )
    need(process.returncode == 0, "authenticated runtime reconstruction failed")
    reconstruction = strict_json(process.stdout)
    need(reconstruction.get("status") == "EXACT_SOURCE_RECONSTRUCTION_PASS"
         and reconstruction.get("members") == 259
         and reconstruction.get("source_archive_sha256") == SOURCE_ARCHIVE_SHA256
         and reconstruction.get("model_or_provider_calls") == 0,
         "runtime reconstruction receipt mismatch")
    rebuilt = checked_bytes(output / "source.zip", inventory["code-payload/source.zip"])
    need(rebuilt == blobs["code-payload/source.zip"], "rebuilt source archive byte mismatch")
    for name in generated:
        checked_bytes(output / name, inventory[name])
    for name, raw in blobs.items():
        target = ordinary_path(output / name)
        target.parent.mkdir(parents=True, exist_ok=True)
        ordinary_path(target.parent)
        if name == "code-payload/source.zip":
            (output / "source.zip").rename(target)
        else:
            with target.open("xb") as stream:
                stream.write(raw)
    copy_predecessor(evidence, output / PREDECESSOR_NAME, expected_evidence)
    with (output / "ASSEMBLY-INVENTORY.json").open("xb") as stream:
        stream.write(inventory_raw)
    need(tree_files(output) == set(inventory) | {"ASSEMBLY-INVENTORY.json"},
         "closed restored operational file set required")
    for name, descriptor in inventory.items():
        need(file_descriptor(output / name) == descriptor, "restored member descriptor mismatch: " + name)
    return {
        "format": "irisx/local-code17-operational-restoration-v1",
        "status": "EXACT_OPERATIONAL_CANDIDATE_RESTORED",
        "output_root": str(output), "files": len(inventory) + 1,
        "assembly_inventory_sha256": sha(inventory_raw),
        "publication_manifest_sha256": PINS["publication-manifest.json"],
        "runtime_source_sha256": SOURCE_SHA256, "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
        "source_members": 259, "predecessor_archive": expected_evidence,
        "historical_partial_predecessor_metadata_unchanged": True,
        "original_inventory_all_bytes_verified": True,
        "predecessor_archive_members_read": 0, "evaluator_body_reads": 0,
        "provider_calls": 0, "model_or_GPU_calls": 0, "Git_mutations": 0,
        "publication_or_runtime_admission": False, "operational_success": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repository-root", "delivery-root", "predecessor-evidence", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = prepare_local_release(repository_root=args.repository_root, delivery_root=args.delivery_root,
                                   predecessor_evidence=args.predecessor_evidence, output_root=args.output_root)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
