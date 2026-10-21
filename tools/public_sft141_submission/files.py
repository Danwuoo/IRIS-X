"""Bounded strict JSON reads and atomic, exclusive local artifact publication."""

from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import stat
import uuid

MAX_BYTES = 128 * 1024 * 1024
_DIRFD = (os.open in os.supports_dir_fd and os.mkdir in os.supports_dir_fd
          and os.link in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"))


def safe_path(value):
    raw = os.fspath(value)
    path = Path(raw)
    if not raw or "\x00" in raw or ".." in path.parts:
        raise ValueError("empty, NUL or parent-traversal paths are forbidden")
    return Path(os.path.abspath(path))


def _not_link(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("symlinks and reparse points are forbidden")
    return info


@contextmanager
def parent_directory(path):
    """On POSIX, traverse all ancestors through pinned no-follow directory FDs."""
    path = safe_path(path)
    if _DIRFD:
        fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in path.parent.parts[1:]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            yield path, fd
        finally:
            os.close(fd)
    else:
        # Windows has no stdlib openat/O_NOFOLLOW equivalent. Reject every
        # existing link/reparse component; do not claim an adversarial sandbox.
        for item in reversed((path.parent, *path.parent.parents)):
            if not stat.S_ISDIR(_not_link(item).st_mode):
                raise ValueError("parent is not a directory")
        yield path, None


def read_bytes(path):
    with parent_directory(path) as (path, parent):
        if parent is None:
            _not_link(path)
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        else:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
                raise ValueError("source must be a regular file no larger than 128 MiB")
            raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
            if len(raw) > MAX_BYTES or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError("source changed during bounded read")
            return raw


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def decode_json(raw):
    def invalid_constant(_):
        raise ValueError("nonfinite JSON numbers are forbidden")
    def finite_float(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("overflowed/nonfinite JSON numbers are forbidden")
        return value
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                      parse_constant=invalid_constant, parse_float=finite_float)


def load_json(path):
    raw = read_bytes(path)
    return decode_json(raw), raw


def _atomic_file(directory, dir_fd, name, raw):
    temp = "." + name + "." + uuid.uuid4().hex
    kwargs = {"dir_fd": dir_fd} if dir_fd is not None else {}
    src = temp if dir_fd is not None else directory / temp
    dst = name if dir_fd is not None else directory / name
    fd = os.open(src, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600, **kwargs)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        link_kwargs = {"src_dir_fd": dir_fd, "dst_dir_fd": dir_fd, "follow_symlinks": False} if dir_fd is not None else {}
        # Hard-link publication is atomic and fails if any destination exists.
        # No overwrite/rename fallback on filesystems without hard-link support.
        os.link(src, dst, **link_kwargs)
    finally:
        os.unlink(src, **kwargs)


def publish_bundle(output_dir, submission, closure):
    """Validate first; create one new directory, then publish each file atomically.

    Closure is published first, submission last. There is no cross-file atomic
    transaction: interrupted work must not be used unless verify succeeds.
    Existing output directories, including empty ones, are never accepted.
    """
    with parent_directory(output_dir) as (directory, parent):
        if parent is None:
            directory.mkdir(mode=0o700, exist_ok=False)
            fd = None
        else:
            os.mkdir(directory.name, 0o700, dir_fd=parent)
            fd = os.open(directory.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            _atomic_file(directory, fd, "closure.json", closure)
            _atomic_file(directory, fd, "submission.json", submission)
            if fd is not None:
                os.fsync(fd)
        finally:
            if fd is not None:
                os.close(fd)
