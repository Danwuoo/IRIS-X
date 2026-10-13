"""Bind the unchanged code17 terminal consumer to the reviewed local collector.

Only CONSUMER-OPERATOR.json's collector digest and reviewed_entry.py's literal
operator pin change. This does not import producer/provider/model code, inspect
private operational evidence, create publication authority, or grant admission.
The result remains outside the producer and original assembled release trees.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile


REPO = Path(__file__).resolve().parents[3]
OLD_ENTRY_SHA256 = "f064fe5ef3d0788f67bae88992ff60f7b37f0c88d8e71337f7695fdfeba50862"
OLD_OPERATOR_SHA256 = "913ba758dd6e7b527a24ad214918e4204d832e4dd423e5e5cf1fde1691a8e6f8"
HELPER_INVENTORY_SHA256 = "d88b66c3b45435c2b328c2cc36c9c605c889ba76e48a36c22729db0ec2fda710"
SOURCE_INVENTORY_SHA256 = "07182a30230da14fa7cce0628ccd2e39a6146719151490acf5e1abaf76e61860"
SOURCE_SHA256 = "22a736bd06f10a5708a0b0c69ac3b89128394e3775c0780d19d1b999b8cc1ba1"
SOURCE_ARCHIVE_SHA256 = "778ac5474a176358e0789cd3b82db5d91278864724507dc56d6c33bf6cdefb9e"
RELEASE_SHA256 = "b3c1f2927a885e1ef3268f22b8c35847ec76734cb297c4d3a3fa399c2267df31"
POLICY_SHA256 = "3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda"
FILE_CAP = 64 * 1024**2


class BindingError(ValueError):
    pass


def need(value, message):
    if not value:
        raise BindingError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def ordinary(path):
    path = Path(os.path.abspath(path))
    for parent in (path, *path.parents):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        need(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, "st_file_attributes", 0) & 0x400, "linked/reparse path forbidden")
    return path


def relative(name):
    need(type(name) is str and name, "relative member name required")
    path = PurePosixPath(name)
    need(not path.is_absolute() and str(path) == name and "\\" not in name and ":" not in name
         and all(part not in ("", ".", "..") for part in path.parts), "unsafe relative member name")
    return name


def identity(info):
    stamp = getattr(info, "st_birthtime_ns", info.st_ctime_ns) if os.name == "nt" else info.st_ctime_ns
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, stamp)


def read(path, cap=FILE_CAP):
    path = ordinary(path)
    before = path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
         "bounded single-link regular file required")
    with path.open("rb") as stream:
        need(identity(os.fstat(stream.fileno())) == identity(before), "input changed before read")
        raw = stream.read(cap + 1)
        need(len(raw) <= cap and identity(os.fstat(stream.fileno())) == identity(before),
             "input changed during read or exceeded cap")
    need(identity(path.stat()) == identity(before) and len(raw) == before.st_size,
         "input changed after read")
    return raw


def pinned(path, digest):
    raw = read(path)
    need(sha(raw) == digest, "exact input pin differs: " + Path(path).name)
    return raw


def document(raw):
    def pairs(rows):
        result = {}
        for name, value in rows:
            need(name not in result, "duplicate JSON key")
            result[name] = value
        return result
    result = json.loads(raw, object_pairs_hook=pairs,
                        parse_constant=lambda value: (_ for _ in ()).throw(BindingError("nonfinite JSON")))
    need(type(result) is dict, "JSON object required")
    return result


def consumer_files(old):
    inventory_raw = pinned(old / "CONSUMER-INVENTORY.json", HELPER_INVENTORY_SHA256)
    inventory = document(inventory_raw)
    need(set(inventory) == {"format", "files"}
         and inventory["format"] == "owned-rl-batched-consumer-helpers-v1", "helper inventory schema")
    helpers = inventory["files"]
    need(type(helpers) is dict and len(helpers) == 21, "exact original 21 helpers required")
    expected = set(helpers) | {"CONSUMER-INVENTORY.json", "CONSUMER-OPERATOR.json", "reviewed_entry.py"}
    actual = set()
    pending = [old]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            path = ordinary(path)
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            else:
                need(stat.S_ISREG(info.st_mode), "consumer special entry forbidden")
                actual.add(relative(path.relative_to(old).as_posix()))
                need(len(actual) <= 24, "closed original consumer file count")
    need(actual == expected, "exact original 24-file consumer required")
    files = {name: read(old / relative(name)) for name in sorted(expected)}
    need(all(sha(files[name]) == digest for name, digest in helpers.items()), "original helper bytes differ")
    need(sha(files["reviewed_entry.py"]) == OLD_ENTRY_SHA256
         and sha(files["CONSUMER-OPERATOR.json"]) == OLD_OPERATOR_SHA256, "exact code17 outside-in pins required")
    return files, helpers


def source_binding(release_root, source_inventory, source_archive):
    release_raw = pinned(release_root / "release.json", RELEASE_SHA256)
    release = document(release_raw)
    need(release.get("format") == "owned-rl-independent-release-v1"
         and release.get("source_sha256") == SOURCE_SHA256, "original code17 independent release required")
    for name in ("material_review", "environment", "phase_policy", "owner_protocol"):
        pinned(release_root / (name + ".json"), release[name + "_sha256"])
    need(release["phase_policy_sha256"] == POLICY_SHA256, "original measured policy required")
    frozen = document(pinned(source_inventory, SOURCE_INVENTORY_SHA256))
    members = frozen["files"]
    need(type(members) is dict and len(members) == frozen.get("members") == 259
         and frozen.get("source_sha256") == SOURCE_SHA256, "complete original source inventory required")
    need(sha(json.dumps(sorted(members.items()), sort_keys=True, separators=(",", ":"),
                        allow_nan=False).encode()) == SOURCE_SHA256, "source closure digest differs")
    archive_raw = pinned(source_archive, SOURCE_ARCHIVE_SHA256)
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        entries = archive.infolist()
        need(len(entries) == len(set(entry.filename for entry in entries)) == 259
             and {entry.filename for entry in entries} == set(members), "exact original source ZIP member closure required")
        need(sum(entry.file_size for entry in entries) <= FILE_CAP, "expanded source ZIP cap")
        for entry in entries:
            relative(entry.filename)
            need(not entry.is_dir() and entry.file_size <= FILE_CAP and not entry.flag_bits & 1
                 and entry.external_attr >> 16 == (stat.S_IFREG | 0o644), "ordinary source ZIP member required")
            need(sha(archive.read(entry)) == members[entry.filename], "source ZIP member bytes differ")
    return release_raw


def successor_files(files, collector_digest):
    need(type(collector_digest) is str and re.fullmatch("[0-9a-f]{64}", collector_digest),
         "actual collector SHA256 required")
    operator = document(files["CONSUMER-OPERATOR.json"])
    expected = {"format": "owned-rl-batched-consumer-operator-v1", "source_sha256": SOURCE_SHA256,
                "source_archive_sha256": SOURCE_ARCHIVE_SHA256, "policy_sha256": POLICY_SHA256,
                "release_sha256": RELEASE_SHA256, "helper_inventory_sha256": HELPER_INVENTORY_SHA256}
    need(set(operator) == set(expected) | {"collector_entry_sha256"}
         and all(operator[key] == value for key, value in expected.items()), "original operator content binding")
    operator["collector_entry_sha256"] = collector_digest
    operator_raw = encoded(operator)
    needle = ("REVIEWED_OPERATOR_PINS_SHA256 = '" + OLD_OPERATOR_SHA256 + "'").encode()
    replacement = ("REVIEWED_OPERATOR_PINS_SHA256 = '" + sha(operator_raw) + "'").encode()
    entry_raw, count = re.subn(rb"(?m)^" + re.escape(needle) + rb"$", replacement, files["reviewed_entry.py"])
    need(count == 1, "one exact code17 entry operator literal required")
    need(entry_raw.replace(replacement, needle, 1) == files["reviewed_entry.py"], "entry changed beyond operator literal")
    updated = dict(files)
    updated["CONSUMER-OPERATOR.json"] = operator_raw
    updated["reviewed_entry.py"] = entry_raw
    return updated


def bind_consumer(*, old_root, release_root, source_inventory, source_archive, collector, output_root):
    old, release, inventory, archive, collector, output = map(
        ordinary, (old_root, release_root, source_inventory, source_archive, collector, output_root))
    need(output.is_relative_to(REPO / ".irisx") and output != REPO / ".irisx", "external owner .irisx output required")
    need(not output.exists(), "fresh successor consumer output required")
    need(not output.is_relative_to(inventory.parent)
         and all(not output.is_relative_to(path) and not path.is_relative_to(output)
                 for path in (old, release, archive, collector)), "consumer must remain outside original producer/release inputs")
    files, helpers = consumer_files(old)
    release_raw = source_binding(release, inventory, archive)
    collector_raw = read(collector, 16 * 1024**2)
    collector_digest = sha(collector_raw)
    updated = successor_files(files, collector_digest)
    changed = {name for name in files if updated[name] != files[name]}
    need(changed <= {"CONSUMER-OPERATOR.json", "reviewed_entry.py"}, "consumer change scope exceeded")
    output.mkdir(parents=True)
    ordinary(output)
    for name, raw in updated.items():
        destination = ordinary(output / name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        ordinary(destination.parent)
        with destination.open("xb") as stream:
            stream.write(raw)
        need(read(destination) == raw, "successor consumer byte roundtrip differs")
    need(read(collector, 16 * 1024**2) == collector_raw, "collector changed during consumer binding")
    return {"format": "irisx/local-code17-consumer-pin-rebind-v1", "status": "LOCAL_CONSUMER_PINS_BOUND",
            "consumer_root": str(output), "source_sha256": SOURCE_SHA256,
            "source_archive_sha256": SOURCE_ARCHIVE_SHA256, "release_sha256": sha(release_raw),
            "collector_sha256": collector_digest, "prior_entry_sha256": OLD_ENTRY_SHA256,
            "prior_operator_sha256": OLD_OPERATOR_SHA256, "helper_inventory_sha256": HELPER_INVENTORY_SHA256,
            "all_21_helpers_and_inventory_unchanged": all(updated[name] == files[name] for name in helpers)
                                                       and updated["CONSUMER-INVENTORY.json"] == files["CONSUMER-INVENTORY.json"],
            "entry_only_operator_literal_changed": True, "operator_only_collector_digest_changed": True,
            "changed_files": sorted(changed), "files": {name: sha(raw) for name, raw in sorted(updated.items())},
            "provider_calls": 0, "model_or_GPU_calls": 0, "evaluator_body_reads": 0,
            "production_admission": False, "independent_final_monitor_review_required": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("old-root", "release-root", "source-inventory", "source-archive", "collector", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = bind_consumer(old_root=args.old_root, release_root=args.release_root,
                           source_inventory=args.source_inventory, source_archive=args.source_archive,
                           collector=args.collector, output_root=args.output_root)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
