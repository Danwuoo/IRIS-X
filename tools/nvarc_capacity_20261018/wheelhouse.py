"""Full pinned wheel Dataset admission, without copying or rehashing its wheels.

The source capsule authenticates the retained public inventories below. The
unchanged offline.verified_wheels must authenticate the wheel bodies first;
this module authenticates every other Dataset file and the complete namespace.
No provider upload metadata or unlisted root file is admitted.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from tools.arc2_goal_sprint_20261017 import bootstrap as offline
from tools.arc2_goal_sprint_20261017.launch import regular, require, sha

INVENTORY_ROOT = 'research/arc-next-line/offline-wheels-dataset-v1'
SOURCE_FILES = tuple(INVENTORY_ROOT + '/' + name for name in (
    'files.json', 'supplemental-readback.json', 'license-inventory.json',
    'requirements.lock', 'wheel-lock.json'))
SIDECARS = {'NOTICE.txt', 'license-inventory.json', 'model-source-lock.json',
            'validation-summary.json', 'wheel-provenance.json'}


def source_paths(source):
    """Explicit small public metadata closure, not an arbitrary research glob."""
    return [regular(Path(source) / name) for name in SOURCE_FILES]


def _json(path):
    path = regular(path)
    require(path.stat().st_size <= 1024**2, 'bounded wheelhouse inventory required')
    return json.loads(path.read_bytes())


def pinned_inventory(source):
    """Reconcile existing independent names/sizes, sidecar pins and license pins."""
    base = Path(source) / INVENTORY_ROOT
    lock = regular(base / 'wheel-lock.json')
    require(sha(lock) == offline.WHEEL_MANIFEST_SHA256, 'original wheel manifest pin differs')
    wheels = _json(lock)['files']
    readback = _json(base / 'supplemental-readback.json')
    require(readback['reference'] == offline.REFERENCES['wheels']
            and set(readback['files']) == SIDECARS, 'exact pinned wheel sidecars required')
    expected = {name: dict(row) for name, row in readback['files'].items()}
    license_path = regular(base / 'license-inventory.json')
    require(license_path.stat().st_size == expected['license-inventory.json']['bytes']
            and sha(license_path) == expected['license-inventory.json']['sha256'],
            'retained license inventory pin differs')
    for name in ('requirements.lock', 'wheel-lock.json'):
        path = regular(base / name)
        expected[name] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    for name, row in wheels.items():
        require(Path(name).name == name and name.endswith('.whl'), 'wheel filename required')
        expected['wheels/' + name] = {'bytes': row['bytes'], 'sha256': row['sha256']}
    licenses = _json(license_path)
    for row in licenses:
        name = row['dataset_path']
        require(name.startswith('licenses/') and name not in expected, 'unique license inventory path required')
        expected[name] = {'bytes': row['bytes'], 'sha256': row['sha256']}
    for name, row in expected.items():
        path = Path(name)
        require(not path.is_absolute() and path.as_posix() == name and '..' not in path.parts
                and '\\' not in name and type(row['bytes']) is int and row['bytes'] > 0
                and isinstance(row['sha256'], str) and re.fullmatch('[a-f0-9]{64}', row['sha256']),
                'safe exact wheelhouse file pin required')
    listed = _json(base / 'files.json')
    sizes = {row['name']: row['totalBytes'] for row in listed}
    require(len(sizes) == len(listed) and sizes == {name: row['bytes'] for name, row in expected.items()},
            'retained full wheelhouse inventory differs')
    return expected


def admit_verified_wheelhouse(root, source, verified_paths):
    """Call only after verified_wheels; reject extra/missing/tampered sidecars."""
    root = Path(root)
    expected = pinned_inventory(source)
    require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)),
            'regular wheelhouse directory required')
    wheel_names = {name for name in expected if name.startswith('wheels/')}
    require({'wheels/' + p.name for p in verified_paths if p.parent == root / 'wheels'} == wheel_names,
            'verified wheel paths differ from full pinned inventory')
    offline.exact_files(root, expected)
    for name in sorted(set(expected) - wheel_names):
        path = regular(root / name); row = expected[name]
        require(path.stat().st_size == row['bytes'] and sha(path) == row['sha256'],
                'wheelhouse sidecar bytes differ: ' + name)
    return {'format': 'irisx/pinned-wheelhouse-admission-v1', 'reference': offline.REFERENCES['wheels'],
            'files': len(expected), 'verified_wheel_files': len(wheel_names),
            'verified_non_wheel_files': len(expected) - len(wheel_names),
            'license_files': sum(name.startswith('licenses/') for name in expected),
            'unlisted_files_permitted': False, 'source_inventory_sha256': sha(Path(source) / SOURCE_FILES[0])}
