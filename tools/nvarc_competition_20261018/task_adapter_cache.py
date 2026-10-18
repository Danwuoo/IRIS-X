"""Session-owned, bounded disk snapshots for optional future task backfill.

This is not wired into the frozen notebook and does not restore a live model.
The caller supplies the complete task/index/input/config binding, calls
``model.restore_state`` itself, and checks the resulting exact adapter digest.

Roots must not exist. There is no reopening, eviction, pickle, caller-supplied
snapshot path, or crash-recovery claim. A static ownership manifest plus the
live instance's authoritative registry and per-snapshot manifests establish
ownership; disk metadata is never used to reconstruct trusted expectations.
Each put has independent ownership, including duplicate bindings/states.

``max_bytes`` bounds logical regular-file bytes, including all manifests and
in-flight files, not filesystem block allocation or host RAM. Disk admission
also reserves ``min_free_bytes`` plus conservative block/directory overhead.
Concurrent filesystem consumers can still exhaust space; failed writes clean
up only this instance's newly created, inode-verified files. Serialization uses
additional temporary host RAM, not any GPU/RAM-fraction or MIG assumption.
One instance serializes its operations; its directory must remain dedicated.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import threading
import uuid


SCHEMA = "nvarc-task-adapter-cache-v1"
_MANIFEST = "owner.json"
_STATE = "state.safetensors"
_METADATA = "snapshot.json"
_SPACE_ERRORS = {errno.ENOSPC, errno.EDQUOT}


def filesystem_supported():
    """The hardened implementation is supported on Linux descriptor APIs only."""
    return (sys.platform.startswith("linux")
            and all(type(getattr(os, flag, None)) is int
                    for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"))
            and all(hasattr(os, name) for name in ("getuid", "fstatvfs"))
            and all(function in os.supports_dir_fd for function in
                    (os.open, os.mkdir, os.stat, os.unlink, os.rmdir, os.rename))
            and os.listdir in os.supports_fd)


_DIRECTORY_FLAGS = (os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                    if filesystem_supported() else None)


class CacheIntegrityError(ValueError):
    """A binding, receipt, ownership marker, or snapshot failed verification."""


@dataclass(frozen=True)
class SnapshotReceipt:
    cache_id: str
    snapshot_id: str
    binding_sha256: str
    adapter_sha256: str
    state_sha256: str
    metadata_sha256: str
    state_bytes: int
    metadata_bytes: int
    size_bytes: int


@dataclass
class _Entry:
    receipt: SnapshotReceipt
    binding: bytes
    metadata: bytes
    inventory: dict
    directory: tuple
    files: dict


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    def check(item, depth=0):
        if depth > 64:
            raise ValueError("plain JSON binding is too deeply nested")
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) is list:
            for child in item:
                check(child, depth + 1)
            return
        if type(item) is dict and all(type(key) is str for key in item):
            for child in item.values():
                check(child, depth + 1)
            return
        raise ValueError("finite plain JSON binding required")
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _binding_bytes(binding):
    if type(binding) is not dict or not binding:
        raise ValueError("nonempty task/input/config binding dictionary required")
    return _canonical(binding)


def _identity(info):
    return info.st_dev, info.st_ino, info.st_uid


def _safe_directory(path):
    """Walk every component using no-follow directory descriptors, not resolve."""
    fd = os.open(path.anchor, _DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:]:
            following = os.open(component, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = following
        return fd
    except BaseException:
        os.close(fd)
        raise


def _file_info(directory_fd, name, expected=None, size=None):
    info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != os.getuid()
            or (expected is not None and _identity(info) != expected)
            or (size is not None and info.st_size != size)):
        raise CacheIntegrityError("cache file ownership/type/size differs")
    return info


def _read_file(directory_fd, name, identity, size):
    _file_info(directory_fd, name, identity, size)
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                 dir_fd=directory_fd)
    try:
        before = os.fstat(fd)
        if (_identity(before) != identity or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1 or before.st_size != size):
            raise CacheIntegrityError("opened cache file differs")
        chunks, remaining = [], size + 1
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after = os.fstat(fd)
        if (len(data) != size or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ctime_ns != after.st_ctime_ns):
            raise CacheIntegrityError("cache file changed while reading")
        return data
    finally:
        os.close(fd)


def _write_file(directory_fd, name, data, owned_files):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=directory_fd)
    try:
        owned_files[name] = _identity(os.fstat(fd))
        view = memoryview(data)
        while view:
            written = os.write(fd, view[:1024 * 1024])
            if written <= 0:
                raise OSError(errno.EIO, "short snapshot write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _create_directory(parent_fd, name):
    os.mkdir(name, 0o700, dir_fd=parent_fd)
    info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise CacheIntegrityError("new cache directory was replaced")
    identity = _identity(info)
    try:
        fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except BaseException:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if stat.S_ISDIR(current.st_mode) and _identity(current) == identity:
            # rmdir is intentionally nonrecursive and can only remove an empty
            # directory we just created, even when opening that directory fails.
            os.rmdir(name, dir_fd=parent_fd)
        raise
    try:
        if _identity(os.fstat(fd)) != identity:
            raise CacheIntegrityError("opened cache directory was replaced")
    except BaseException:
        os.close(fd)
        raise
    return fd, identity


def _space_available(directory_fd, reserve, sizes):
    info = os.fstatvfs(directory_fd)
    block = max(info.f_frsize, info.f_bsize, 1)
    # Per-file allocation rounding, a new snapshot directory, and conservative
    # directory-growth allowance. This is admission, not a filesystem quota.
    allocation = sum(((size + block - 1) // block) * block for size in sizes)
    allocation += 4 * block
    return info.f_bavail * info.f_frsize >= reserve + allocation


def _snapshot(state):
    import torch
    if type(state) is not dict or not state:
        raise ValueError("nonempty named trainable adapter state required")
    result = {}
    for name, tensor in sorted(state.items(), key=lambda pair: str(pair[0])):
        if (type(name) is not str or not name or "\x00" in name
                or name == "__metadata__" or not isinstance(tensor, torch.Tensor)
                or tensor.device.type != "cpu" or tensor.layout != torch.strided
                or tensor.dtype not in (torch.float16, torch.bfloat16, torch.float32, torch.float64)
                or tensor.ndim == 0):
            raise ValueError("named, finite, non-scalar CPU floating adapter tensors required")
        # Own a detached contiguous copy so a caller cannot mutate cached bytes
        # after put. The frozen model.state_digest does not support scalars.
        result[name] = tensor.detach().clone(memory_format=torch.contiguous_format)
        if not bool(torch.isfinite(result[name]).all()):
            raise ValueError("finite CPU floating adapter tensors required")
    return result


def _inventory(state):
    from .model import tensor_inventory
    result = tensor_inventory(state)
    for name, tensor in state.items():
        result[name]["nbytes"] = tensor.numel() * tensor.element_size()
    return result


class TaskAdapterCache:
    """A fresh dedicated root, one session, independent receipts, no eviction.

    ``put`` returns None on cache-capacity or disk-space admission failure.
    Invalid data and integrity failures raise ValueError; other I/O failures
    propagate. Construction needs room for the small ownership manifest.
    ``release`` is deliberately not idempotent: stale/foreign receipts fail.
    Only the caller can establish that the supplied tensors are its complete
    trainable inventory; load verifies exactly the inventory accepted by put.
    """

    def __init__(self, root, *, max_bytes, min_free_bytes):
        if not filesystem_supported():
            raise NotImplementedError("task adapter cache requires Linux no-follow descriptor APIs")
        if (type(max_bytes) is not int or max_bytes <= 0
                or type(min_free_bytes) is not int or min_free_bytes < 0):
            raise ValueError("positive max_bytes and nonnegative min_free_bytes required")
        path = Path(root)
        if ".." in path.parts:
            raise ValueError("cache root traversal is forbidden")
        self.root = path.absolute()
        if self.root == self.root.parent:
            raise ValueError("fresh dedicated cache directory required")
        self._max_bytes, self._min_free_bytes = max_bytes, min_free_bytes
        self.cache_id = uuid.uuid4().hex
        self._manifest = _canonical({"schema": SCHEMA, "cache_id": self.cache_id,
            "max_bytes": max_bytes, "min_free_bytes": min_free_bytes,
            "ownership": "session-local-registry; no reopening"})
        if len(self._manifest) > max_bytes:
            raise ValueError("max_bytes cannot hold the ownership manifest")
        self._entries = {}
        self._used = len(self._manifest)
        self._lock = threading.RLock()
        parent_fd = _safe_directory(self.root.parent)
        root_fd = None
        owned = {}
        try:
            if not _space_available(parent_fd, min_free_bytes, [len(self._manifest)]):
                raise OSError(errno.ENOSPC, "ownership manifest would consume disk reserve")
            root_fd, self._root_identity = _create_directory(parent_fd, self.root.name)
            _write_file(root_fd, _MANIFEST, self._manifest, owned)
            self._manifest_identity = owned[_MANIFEST]
            os.fsync(root_fd)
            os.fsync(parent_fd)
        except BaseException:
            if root_fd is not None:
                self._remove_directory(parent_fd, self.root.name, root_fd,
                                       self._root_identity, owned)
            raise
        finally:
            if root_fd is not None:
                os.close(root_fd)
            os.close(parent_fd)

    @staticmethod
    def _remove_directory(parent_fd, name, directory_fd, identity, files):
        """Never recursive: delete only exact recorded regular-file inodes."""
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (not stat.S_ISDIR(info.st_mode) or _identity(info) != identity
                or _identity(os.fstat(directory_fd)) != identity
                or set(os.listdir(directory_fd)) != set(files)):
            raise CacheIntegrityError("refusing cleanup of an unowned/replaced directory")
        for filename, file_identity in files.items():
            _file_info(directory_fd, filename, file_identity)
        for filename in files:
            os.unlink(filename, dir_fd=directory_fd)
        os.rmdir(name, dir_fd=parent_fd)

    def _open_root(self):
        fd = _safe_directory(self.root)
        try:
            if _identity(os.fstat(fd)) != self._root_identity:
                raise CacheIntegrityError("cache root was replaced")
            if set(os.listdir(fd)) != {_MANIFEST, *self._entries}:
                raise CacheIntegrityError("cache root contains missing/unowned entries")
            manifest = _read_file(fd, _MANIFEST, self._manifest_identity, len(self._manifest))
            if manifest != self._manifest:
                raise CacheIntegrityError("cache ownership manifest differs")
            for name, entry in self._entries.items():
                child_fd = self._open_snapshot(fd, name, entry)
                os.close(child_fd)
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def _open_snapshot(root_fd, name, entry):
        fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=root_fd)
        try:
            if (_identity(os.fstat(fd)) != entry.directory
                    or set(os.listdir(fd)) != {_STATE, _METADATA}):
                raise CacheIntegrityError("snapshot directory differs")
            _file_info(fd, _STATE, entry.files[_STATE], entry.receipt.state_bytes)
            _file_info(fd, _METADATA, entry.files[_METADATA], entry.receipt.metadata_bytes)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _entry(self, binding, receipt):
        if (type(receipt) is not SnapshotReceipt or receipt.cache_id != self.cache_id
                or type(receipt.snapshot_id) is not str
                or not re.fullmatch(r"snapshot-[0-9a-f]{32}", receipt.snapshot_id)):
            raise CacheIntegrityError("foreign or malformed snapshot receipt")
        entry = self._entries.get(receipt.snapshot_id)
        if entry is None or receipt != entry.receipt:
            raise CacheIntegrityError("unknown, modified, or released snapshot receipt")
        if _binding_bytes(binding) != entry.binding:
            raise CacheIntegrityError("task/input/config binding differs")
        return entry

    @property
    def max_bytes(self):
        return self._max_bytes

    @property
    def min_free_bytes(self):
        return self._min_free_bytes

    @property
    def used_bytes(self):
        """Verified logical file-byte usage, including the ownership manifest."""
        with self._lock:
            fd = self._open_root()
            os.close(fd)
            return self._used

    def put(self, binding, state):
        """Save an independent exact snapshot, or decline admission with None."""
        binding_bytes = _binding_bytes(binding)
        with self._lock:
            root_fd = self._open_root()
            temporary_fd = None
            temporary_name = None
            temporary_identity = None
            files = {}
            try:
                from safetensors.torch import save
                from .model import state_digest
                snapshot = _snapshot(state)
                inventory = _inventory(snapshot)
                adapter_sha256 = state_digest(snapshot)
                data = save(snapshot)
                snapshot_id = "snapshot-" + uuid.uuid4().hex
                metadata = _canonical({"schema": SCHEMA, "cache_id": self.cache_id,
                    "snapshot_id": snapshot_id, "binding": json.loads(binding_bytes),
                    "binding_sha256": _sha(binding_bytes), "adapter_sha256": adapter_sha256,
                    "state_sha256": _sha(data), "state_bytes": len(data),
                    "tensor_inventory": inventory})
                size = len(data) + len(metadata)
                if (self._used + size > self.max_bytes or not _space_available(
                        root_fd, self.min_free_bytes, [len(data), len(metadata)])):
                    return None
                receipt = SnapshotReceipt(self.cache_id, snapshot_id, _sha(binding_bytes),
                    adapter_sha256, _sha(data), _sha(metadata), len(data), len(metadata), size)
                temporary_name = ".pending-" + uuid.uuid4().hex
                temporary_fd, temporary_identity = _create_directory(root_fd, temporary_name)
                _write_file(temporary_fd, _STATE, data, files)
                _write_file(temporary_fd, _METADATA, metadata, files)
                os.fsync(temporary_fd)
                # Recheck the reserve after physical allocation, before commit.
                free = os.fstatvfs(root_fd)
                if free.f_bavail * free.f_frsize < self.min_free_bytes:
                    return None
                if snapshot_id in os.listdir(root_fd):
                    raise CacheIntegrityError("snapshot destination already exists")
                os.rename(temporary_name, snapshot_id, src_dir_fd=root_fd, dst_dir_fd=root_fd)
                temporary_name = snapshot_id
                os.fsync(root_fd)
                self._entries[snapshot_id] = _Entry(replace(receipt), binding_bytes, metadata,
                    inventory, temporary_identity, dict(files))
                self._used += size
                temporary_name = None
                return receipt
            except OSError as error:
                if error.errno in _SPACE_ERRORS:
                    return None
                raise
            finally:
                try:
                    if temporary_name is not None and temporary_fd is not None:
                        self._remove_directory(root_fd, temporary_name, temporary_fd,
                                               temporary_identity, files)
                finally:
                    if temporary_fd is not None:
                        os.close(temporary_fd)
                    os.close(root_fd)

    def load(self, binding, receipt):
        """Return independent CPU tensors after all recorded checks pass."""
        with self._lock:
            entry = self._entry(binding, receipt)
            root_fd = self._open_root()
            snapshot_fd = None
            try:
                snapshot_fd = self._open_snapshot(root_fd, receipt.snapshot_id, entry)
                metadata = _read_file(snapshot_fd, _METADATA,
                    entry.files[_METADATA], receipt.metadata_bytes)
                if metadata != entry.metadata or _sha(metadata) != receipt.metadata_sha256:
                    raise CacheIntegrityError("snapshot metadata/inventory differs")
                data = _read_file(snapshot_fd, _STATE, entry.files[_STATE], receipt.state_bytes)
                if _sha(data) != receipt.state_sha256:
                    raise CacheIntegrityError("snapshot byte digest differs")
                from safetensors import SafetensorError
                from safetensors.torch import load
                from .model import state_digest
                try:
                    state = _snapshot(load(data))
                except (ValueError, RuntimeError, SafetensorError) as error:
                    raise CacheIntegrityError("invalid safetensors snapshot") from error
                if _inventory(state) != entry.inventory:
                    raise CacheIntegrityError("snapshot tensor inventory differs")
                if state_digest(state) != receipt.adapter_sha256:
                    raise CacheIntegrityError("snapshot adapter digest differs")
                return state
            finally:
                if snapshot_fd is not None:
                    os.close(snapshot_fd)
                os.close(root_fd)

    def release(self, binding, receipt):
        """Delete only this session's exact recorded snapshot; never a path."""
        with self._lock:
            entry = self._entry(binding, receipt)
            root_fd = self._open_root()
            snapshot_fd = None
            try:
                snapshot_fd = self._open_snapshot(root_fd, receipt.snapshot_id, entry)
                self._remove_directory(root_fd, receipt.snapshot_id, snapshot_fd,
                                       entry.directory, entry.files)
                del self._entries[receipt.snapshot_id]
                self._used -= receipt.size_bytes
                os.fsync(root_fd)
            finally:
                if snapshot_fd is not None:
                    os.close(snapshot_fd)
                os.close(root_fd)
