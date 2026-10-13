"""Validate the existing native official-auth boundary without invoking Kaggle.

This intentionally exposes a read-command PLAN, not an executable publisher.
No credential body, token, environment secret, provider or resource is read.
"""
from __future__ import annotations
import os
from pathlib import Path
import stat
import hashlib

WRAPPER_SHA256 = '46134808e2705d45d70bdc9aadd26a1e1863628d3d045a32a507efa56616b4bc'
REFERENCE = 'danielwuu/iris-x-learning-agent-20261011'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def inspect_wrapper(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and path.name == 'kaggle.sh',
         'explicit canonical path to the existing native wrapper required')
    for entry in (path, *path.parents):
        info = entry.lstat()
        need(not stat.S_ISLNK(info.st_mode), 'linked native wrapper path')
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 65536,
         'native wrapper must be a bounded ordinary file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(65537)
        after = os.fstat(stream.fileno())
    key = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)
    need(key(info) == key(opened) == key(after) == key(path.lstat()), 'native wrapper changed')
    need(hashlib.sha256(raw).hexdigest() == WRAPPER_SHA256, 'native wrapper bytes differ')
    return {'format': 'irisx/run008-native-official-auth-boundary-v1',
        'wrapper_sha256': WRAPPER_SHA256, 'expected_account': 'danielwuu',
        'configuration': 'existing wrapper-owned isolated official OAuth store',
        'credential_body_reads': 0, 'credential_copies': 0, 'provider_calls': 0,
        'authentication_or_exact_resource_access_verified': False,
        'publication_adapter_status': 'BLOCKED_UNVALIDATED_EXACT_RESOURCE_ACCESS'}


def status_read_plan(wrapper_path):
    """Exact previously denied target, to use only after legitimate access repair.

    Constructing this plan neither retries that denial nor authorizes execution.
    There is no fallback route, owner substitution, generic CLI or quota method.
    """
    boundary = inspect_wrapper(wrapper_path)
    return {'argv': [str(Path(wrapper_path)), 'kernels', 'status', REFERENCE],
        'environment': {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'},
        'timeout_seconds': 120, 'automatic_retry': False,
        'currently_blocked': True, 'boundary': boundary}


def publication_command(*_args, **_kwargs):
    raise ValueError('native publication requires fresh exact-resource evidence and independently reviewed run008 transport/wire; no executable adapter is admitted')
