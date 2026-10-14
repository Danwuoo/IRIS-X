"""Bounded local JSON and explicit report links. No ambient or provider access."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat

MAX_JSON_BYTES = 16 * 1024 * 1024


class InputError(ValueError):
    """A fixed diagnostic code, with no private input content attached."""


def require(condition, code):
    if not condition:
        raise InputError(code)


# Save capability identities so test instrumentation of individual calls does not
# itself change platform support. The advertised capability sets are rechecked.
_READ_DIR_OPS = (os.open, os.stat)
_WRITE_DIR_OPS = (os.mkdir, os.rmdir, os.unlink, os.link)
_NOFOLLOW_STAT = os.stat
_NOFOLLOW_LINK = os.link
MAX_PATH_PARTS = 128
MAX_PATH_BYTES = 4096
_STAGE_ATTEMPTS = 16


def _platform(*, write=False):
    require(
        os.name == "posix"
        and all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"))
        and all(op in os.supports_dir_fd for op in _READ_DIR_OPS)
        and _NOFOLLOW_STAT in os.supports_follow_symlinks
        and (not write or (all(op in os.supports_dir_fd for op in _WRITE_DIR_OPS)
                           and _NOFOLLOW_LINK in os.supports_follow_symlinks)),
        "unsupported_safe_io_platform",
    )


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _directory_identity(info):
    # Directory timestamps and link counts legitimately change during output.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)


def _content_identity(info):
    # Publishing/removing a hard link changes ctime and nlink, not file content.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns)


def _close_all(descriptors):
    error = None
    while descriptors:
        try:
            os.close(descriptors.pop())
        except BaseException as exc:
            # Do not retry an uncertain close: the descriptor might be reused.
            # Continue closing the other owned descriptors even on interruption.
            if error is None:
                error = exc
    if error is not None:
        raise error


class _Parent:
    """Pin every ancestor; never resolve a file through a checked path string."""

    def __init__(self, path, *, write=False):
        _platform(write=write)
        path = Path(path).absolute()
        require(".." not in path.parts, "path_traversal")
        require(path.anchor == "/" and 1 < len(path.parts) <= MAX_PATH_PARTS
                and len(os.fsencode(path)) <= MAX_PATH_BYTES, "invalid_path")
        self.name = path.name
        self.descriptors = []
        self.links = []
        self.flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            self.descriptors.append(os.open(path.anchor, self.flags))
            for part in path.parts[1:-1]:
                parent = self.descriptors[-1]
                before = os.stat(part, dir_fd=parent, follow_symlinks=False)
                require(not stat.S_ISLNK(before.st_mode), "symlink_path")
                require(stat.S_ISDIR(before.st_mode), "path_directory")
                child = os.open(part, self.flags, dir_fd=parent)
                self.descriptors.append(child)
                require(_directory_identity(before) == _directory_identity(os.fstat(child)), "path_changed")
                self.links.append((parent, part, child, _directory_identity(before)))
            self.fd = self.descriptors[-1]
            self.verify()
        except BaseException as exc:
            self.close()
            if isinstance(exc, FileNotFoundError):
                raise InputError("output_parent_missing" if write else "input_parent_missing") from None
            raise

    def verify(self):
        for parent, name, child, expected in self.links:
            try:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                opened = os.fstat(child)
            except OSError:
                raise InputError("path_changed") from None
            require(_directory_identity(current) == _directory_identity(opened) == expected
                    and opened.st_nlink > 0, "path_changed")

    def stat(self, name):
        return os.stat(name, dir_fd=self.fd, follow_symlinks=False)

    def close(self):
        _close_all(self.descriptors)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _bounded_read(descriptor):
    chunks = []
    remaining = MAX_JSON_BYTES + 1
    while remaining:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_json(path, expected_sha256):
    """Read stable, bounded bytes; expected hashes do not attest provenance.

    Every path component is opened without following links. Namespace and file
    identity checks reject observed changes, including ancestor renames. Handles
    contain races to already-open directories; no check can exclude changes
    after its final observation or hostile same-UID mutation of an opened file.
    """
    require(type(expected_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha256), "expected_sha256")
    with _Parent(path) as parent:
        before = parent.stat(parent.name)
        require(not stat.S_ISLNK(before.st_mode), "symlink_path")
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "regular_single_link_input")
        require(0 < before.st_size <= MAX_JSON_BYTES, "input_size")
        descriptors = []
        try:
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(parent.name, flags, dir_fd=parent.fd)
            descriptors.append(descriptor)
            require(_identity(before) == _identity(os.fstat(descriptor)), "input_replaced")
            parent.verify()
            raw = _bounded_read(descriptor)
            require(_identity(before) == _identity(os.fstat(descriptor)), "input_changed")
            require(_identity(before) == _identity(parent.stat(parent.name)), "input_changed")
            parent.verify()
        finally:
            _close_all(descriptors)
    require(len(raw) == before.st_size and hashlib.sha256(raw).hexdigest() == expected_sha256, "input_hash")

    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def number(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite_json")
        return result

    def constant(_value):
        raise InputError("nonfinite_json")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_float=number, parse_constant=constant)
    except InputError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise InputError("invalid_json") from None
    require(type(value) is dict, "json_object_required")
    return value, {"bytes": len(raw), "sha256": expected_sha256}


def _link(value, descriptor, code):
    # The recorded path is deliberately ignored: only explicitly supplied files
    # may be opened, even if a collector descriptor points somewhere else.
    require(type(value) is dict, code)
    require(type(value.get("bytes")) is int and value["bytes"] == descriptor["bytes"]
            and value.get("sha256") == descriptor["sha256"], code)


def report_links(report, report_descriptor, *, checkpoint=None, checkpoint_descriptor=None,
                 retrieval=None, retrieval_descriptor=None):
    """Check local collector serialization links, without recreating admission."""
    result = {
        "report": report_descriptor,
        "checkpoint": checkpoint_descriptor,
        "retrieval": retrieval_descriptor,
        "local_descriptor_links_consistent": None,
        "external_collection_authenticated": False,
        "recorded_numeric_output_version": None,
    }
    require((checkpoint is None) == (checkpoint_descriptor is None), "checkpoint_arguments")
    require((retrieval is None) == (retrieval_descriptor is None), "retrieval_arguments")
    require(retrieval is None or checkpoint is not None, "retrieval_requires_checkpoint")
    if checkpoint is None:
        return result
    require(checkpoint.get("status") == "TERMINAL_EVIDENCE_VERIFIED", "checkpoint_status")
    _link(checkpoint.get("validation"), report_descriptor, "checkpoint_validation_link")
    require(checkpoint.get("provider_status") == report.get("provider_status"), "checkpoint_provider_status")
    for key in ("operational_success", "comparison_complete", "compute_matched", "comparison_eligible",
                "public_benchmark_evidence_eligible", "goal_met", "public_goal_met"):
        require(type(checkpoint.get(key)) is bool and checkpoint[key] is report.get(key), "checkpoint_axes")
    require(checkpoint.get("automatic_retry") is False, "checkpoint_retry")
    if retrieval is not None:
        _link(checkpoint.get("retrieval"), retrieval_descriptor, "checkpoint_retrieval_link")
        require(retrieval.get("format") == "irisx/rlvr-selected-retrieval-v1", "retrieval_format")
        version = retrieval.get("numeric_output_version")
        require(type(version) is int and version > 0, "retrieval_version")
        before, after = retrieval.get("before"), retrieval.get("after")
        require(type(before) is dict and type(after) is dict, "retrieval_bracket")
        require(before.get("status") == after.get("status") == report.get("provider_status"), "retrieval_bracket")
        require(retrieval.get("inventory_scope") == "selected_outputs_only"
                and retrieval.get("whole_provider_inventory_verified") is False, "retrieval_scope")
        result["recorded_numeric_output_version"] = version
    result["local_descriptor_links_consistent"] = True
    return result


def _output_bytes(value):
    chunks = []
    size = 1  # final newline
    try:
        encoder = json.JSONEncoder(indent=2, sort_keys=True, allow_nan=False)
        for piece in encoder.iterencode(value):
            raw = piece.encode("utf-8")
            size += len(raw)
            require(size <= MAX_JSON_BYTES, "output_size")
            chunks.append(raw)
    except InputError:
        raise
    except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError):
        raise InputError("invalid_output_json") from None
    return b"".join(chunks) + b"\n"


class _Stage:
    """Private staging prevents other users from replacing the link source.

    The caller owns the parent handle throughout cleanup. A hostile process with
    the same UID can still mutate private entries; detected replacement fails
    closed and foreign entries are not deliberately removed.
    """

    payload = "payload.json"

    def __init__(self, parent):
        self.parent = parent
        self.name = None
        self.identity = None
        self.fd = -1
        self.file = -1
        try:
            for _ in range(_STAGE_ATTEMPTS):
                name = ".arc2-report-" + secrets.token_hex(16)
                try:
                    os.mkdir(name, 0o700, dir_fd=parent.fd)
                except FileExistsError:
                    continue
                self.name = name
                break
            require(self.name is not None, "output_temporary_collision")
            info = parent.stat(self.name)
            self.identity = _directory_identity(info)
            require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700
                    and info.st_uid == os.geteuid(), "output_temporary_permissions")
            self.fd = os.open(self.name, parent.flags, dir_fd=parent.fd)
            self.verify()
            flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
            self.file = os.open(self.payload, flags, 0o600, dir_fd=self.fd)
            info = os.fstat(self.file)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    and stat.S_IMODE(info.st_mode) & 0o077 == 0, "output_temporary_permissions")
        except BaseException:
            self.close()
            raise

    def verify(self):
        require(self.identity == _directory_identity(self.parent.stat(self.name))
                == _directory_identity(os.fstat(self.fd)), "output_temporary_changed")

    def stat(self):
        return os.stat(self.payload, dir_fd=self.fd, follow_symlinks=False)

    def close(self):
        error = None
        try:
            if self.file >= 0:
                try:
                    current = self.stat()
                except FileNotFoundError:
                    pass
                else:
                    owned = os.fstat(self.file)
                    require((current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino),
                            "output_temporary_changed")
                    os.unlink(self.payload, dir_fd=self.fd)
        except BaseException as exc:
            error = exc
        descriptors = [fd for fd in (self.fd, self.file) if fd >= 0]
        self.fd = self.file = -1
        try:
            _close_all(descriptors)
        except BaseException as exc:
            if error is None:
                error = exc
        try:
            if self.name is not None and self.identity is not None:
                try:
                    current = self.parent.stat(self.name)
                except FileNotFoundError:
                    pass
                else:
                    require(_directory_identity(current) == self.identity, "output_temporary_changed")
                    os.rmdir(self.name, dir_fd=self.parent.fd)
        except BaseException as exc:
            if error is None:
                error = exc
        self.name = None
        if error is not None:
            raise error


def _verify_output(parent, descriptor, ready, raw, links):
    opened = os.fstat(descriptor)
    current = parent.stat(parent.name)
    require(opened.st_nlink == links and _identity(opened) == _identity(current)
            and _content_identity(opened) == _content_identity(ready), "output_changed")
    os.lseek(descriptor, 0, os.SEEK_SET)
    require(_bounded_read(descriptor) == raw, "output_changed")
    require(_identity(opened) == _identity(os.fstat(descriptor))
            == _identity(parent.stat(parent.name)), "output_changed")
    parent.verify()


def write_new_json(path, value):
    """Exclusively publish complete JSON through pinned POSIX directories.

    All writes and cleanup use held directory descriptors. Other users cannot
    replace the source inside private staging, and an existing destination is
    never overwritten. Detected namespace/content changes return no descriptor.
    A failure after the exclusive link can leave a complete output; rollback is
    intentionally avoided because stat-then-unlink could delete a competitor.
    This is not a durability guarantee against power loss, nor protection from
    hostile same-UID writes or namespace changes after the last observation.
    """
    raw = _output_bytes(value)
    with _Parent(path, write=True) as parent:
        try:
            parent.stat(parent.name)
        except FileNotFoundError:
            pass
        else:
            raise InputError("output_exists")
        stage = _Stage(parent)
        retained = []
        try:
            try:
                position = 0
                view = memoryview(raw)
                while position < len(raw):
                    count = os.write(stage.file, view[position:])
                    require(0 < count <= len(raw) - position, "output_write")
                    position += count
                os.fsync(stage.file)
                ready = os.fstat(stage.file)
                require(ready.st_size == len(raw) and ready.st_nlink == 1
                        and _identity(ready) == _identity(stage.stat()), "output_temporary_changed")
                parent.verify()
                stage.verify()
                try:
                    os.link(stage.payload, parent.name, src_dir_fd=stage.fd,
                            dst_dir_fd=parent.fd, follow_symlinks=False)
                except FileExistsError:
                    raise InputError("output_exists") from None
                _verify_output(parent, stage.file, ready, raw, 2)
                # Keep the exact inode alive while removing its staging link.
                retained.append(os.dup(stage.file))
            finally:
                stage.close()
            _verify_output(parent, retained[0], ready, raw, 1)
        finally:
            _close_all(retained)
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
