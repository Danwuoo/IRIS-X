"""Build one self-contained, deterministic and default-inert research notebook."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import zlib

ROOT = Path(__file__).resolve().parent
PACKAGE = "arc_consolidated_20261010"
PREFIX = "tools/" + PACKAGE + "/"
NOTEBOOK_NAME = "IRIS-X-Consolidated-Offline-20261010.ipynb"
BACKEND_PINS = {
    "arc_next_models.py": "d8c3bda2ef5c557fa93756805c91ea26c5c0773d8f124914791eef13b2f0740b",
    "arc_next_index_repair.py": "05d2855e6029d873f0e74938e73d11ed7a21b72e0a630619b4415d3ebf3ac030",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    if (type(name) is not str or not name or "\\" in name or ":" in name
            or PurePosixPath(name).is_absolute()
            or any(part in {"", ".", ".."} for part in name.split("/"))
            or not name.startswith("tools/") or not name.endswith((".py", ".json"))):
        raise ValueError("unsafe embedded source path")
    return name


def _regular(path):
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
           for p in (path, *path.parents)):
        raise ValueError("symlink/junction build input")
    if not path.is_file():
        raise ValueError("missing regular build input: " + str(path))
    return path.read_bytes()


def collect_sources(package_root=ROOT, *, require_runner=True):
    """Match assets.source_identity's package inventory, plus pinned G4 helpers."""
    root = Path(package_root)
    paths = sorted(root.glob("*.py")) + sorted((root / "legacy").glob("*.py"))
    paths += sorted((root / "data").glob("*.json"))
    files = {PREFIX + path.relative_to(root).as_posix(): _regular(path).decode("utf-8")
             for path in paths if path.name != "build_notebook.py"}
    for name, expected in BACKEND_PINS.items():
        raw = _regular(root.parent / name)
        if sha(raw) != expected:
            raise ValueError("optional G4 helper source pin differs: " + name)
        files["tools/" + name] = raw.decode("utf-8")
    files["tools/__init__.py"] = _regular(root.parent / "__init__.py").decode("utf-8")
    if require_runner and PREFIX + "runner.py" not in files:
        raise ValueError("runner.py must exist before final notebook build")
    return files


GUIDE = """# IRIS-X consolidated offline ARC research

This repaired notebook is a demos-only representation and agent-testability study. Defaults are **MANUAL_START=False**, **ENABLE_MODEL=False**, **PROFILE='SMOKE'**, and **RESUME=False**. Running all cells with these defaults performs no source writes, Dataset scan, installation, tokenizer/model load, torch import, training, or GPU work.

The eight fixed exposed engineering tasks contain only task_id and demos/input/output, with no test, query, gold or solutions fields and no query evaluator. The scientific/model path never semantically reads queries, gold or solutions. An isolated integrity child streams all runtime bytes, including evaluator members, solely for hashes and returns aggregate proof. Evaluator paths, per-file gold hashes and evaluator content never go to the model. Demo-fit measures expressibility on exposed demonstrations; it is not generalization or N14 promotion. Historical N5-N14 scientific code and the N14 gate remain unchanged.

## Operation

1. Use an existing Linux environment with resource limits. Windows fails closed for real verifier work; schema/reference/mock tests do not replace Linux acceptance. Select a new OUTPUT_ROOT for each profile/run. Before any source or output write, a scan-free lexical guard separates source/cache, output and derived environment from every declared immutable input, rejecting equality, ancestor/descendant overlap, traversal and write-path links. Source extraction verifies the embedded closed inventory and hashes, refuses changed files, symlinks/junctions and conflicting imported tools packages, and records its wall time.
2. Set MANUAL_START=True for CPU SMOKE first. SMOKE checks 128 frozen candidates x 8 demo sets plus 64 positive and 64 legal wrong-program controls: **1,152 checks**, with a **300-second CPU phase**. It never opens the model gate. FULL checks **5,965 x 8 + 128 = 47,848 checks**, within **1,800 seconds**. At most **four** isolated verifier workers run; each check shares **200,000 gas** across demos, **2 CPU seconds**, **3 wall seconds**, and **256 MiB**. Timeouts retain partial/inconclusive results and unvisited candidates, never a no-witness claim.
3. Optional model work requires PROFILE='FULL', ENABLE_MODEL=True, and a completed base-inventory gate: all controls meet expectations, the physical ledger is complete, and at least two engineering tasks have a base demo-fit. Only then does automatic offline bootstrap inspect the five pinned Dataset roles (runtime/8, Granite/2, wheels/1, CPython312/2, adapter/1) under MODEL_CONFIG['input_root']. Optional explicit_roots overrides only Dataset roots. There are no manual model/environment path or hash fields. Bootstrap verifies actual mounted bytes, prepares the pinned CP312 environment offline, then creates one persistent model-owner process. A matching fixture cannot attest a real mount. Before this gate there is no model asset scan, import, installation, or load.
4. Model studies use eight tasks and one seed block, with at most **80 physical calls**: 16 shared roots, 32 true/redacted feedback calls, and 32 frozen-parent memory-off/on calls. Shared physical cost is charged once, with separate arm attribution; memory pairs change only memory content. Calls allow at most **6,144 prompt + 2,048 output = 8,192 context tokens**, with a cooperative **120-second call limit**. This implementation is not GPU-accepted and performs no training.
5. At most two legal root proposals per task enter the common pool after full compiler validation: pool cap **5,967**. Duplicate, out-of-domain and overflow outcomes have receipts. Three ranking arms use the same pool/hash, three seeded tie orders, eight tasks and 64 expansions: **4,608 fresh search checks**, without new model calls. With up to 80 response-verifier checks, FULL reserves at most **52,536 physical verifier checks** and **10,507,200,000 gas**. Keep all eight tasks in reports, including infeasible or unfinished tasks. Cached ordering diagnostics are separate from fresh search.
6. Resume only the same output root and source/task/model/prompt/sampling/budget/config bindings with RESUME=True. After installing repaired source, start a fresh kernel/runtime and choose a new OUTPUT_ROOT with RESUME=False; preserve the failed run root unchanged. A changed source identity cannot resume or migrate its ledger. Reservations are fsynced before dispatch. Missing responses remain unknown, consume their full reservation, and are never automatically resent; retained responses may receive newly charged CPU verification. Each session gets a fresh deadline while durable consumed wall persists. Stage snapshots isolate failures; global sealing requires owned-child stop evidence. Preserve the report, journal, receipts and archive even for no-go or partial outcomes.

SESSION_SECONDS=None uses a 600-second SMOKE or 7,200-second FULL session allowance, separate from the 300/1,800-second CPU phase. The entire workflow has a **14,400-second wall ceiling**, including source setup, offline installation, model loading, generation, verification, export and sealing. Deadlines are admission/cooperative limits; cleanup can overrun. **Program return and archive completion do not stop VM billing.** Stop the owner-managed VM separately.

The required 64 semantic negative controls use legal wrong programs with the original positive demo targets unchanged. Separate target-mutant detector controls are outside the required 128 controls. IR v2 excludes the dead same_normalized_mask relation. Anchor and focus selectors see the full original partition before the anchor is removed from focus.

This repair is checked with CPU contract/summary tests only; exact pinned Granite tokenizer, weights and GPU execution remain unverified. Git push and a private inactive notebook save are authorized separately; this repair performs no agent GPU or paid execution. The terminal prints a bounded summary (at most 8 KiB of summary JSON), while detailed results stay in the on-disk stage, journal, response and archive files. Start the repaired source in a fresh kernel/runtime with OUTPUT_ROOT='irisx-consolidated-20261010-repair001' and RESUME=False; choose another fresh root if that repair root already exists. See VALIDATION.md for version-specific evidence and remaining acceptance.
"""


CONFIG = '''# All manual activation remains subject to the runner's immutable gates.
MANUAL_START = False
ENABLE_MODEL = False
PROFILE = 'SMOKE'
RESUME = False
OUTPUT_ROOT = 'irisx-consolidated-20261010-repair001'
SOURCE_PARENT = '.irisx-consolidated-source'
SESSION_SECONDS = None  # SMOKE 600 / FULL 7200; persistent total wall stays bounded.
MODEL_CONFIG = {'input_root': '/kaggle/input', 'explicit_roots': {}}
'''


BOOTSTRAP = '''# Embedded bytes are trusted repository code, never model-generated source.
if type(MANUAL_START) is not bool or type(ENABLE_MODEL) is not bool or type(RESUME) is not bool:
    raise ValueError('Manual switches must be exact booleans')
if not MANUAL_START:
    print('INACTIVE: no source writes, install, model scan, torch import, training or GPU work.')
else:
    import base64 as _base64
    import hashlib as _hashlib
    import importlib as _importlib
    import json as _json
    import os as _os
    from pathlib import Path as _Path, PurePosixPath as _PurePosixPath
    import sys as _sys
    import time as _time
    import zlib as _zlib

    _install_start = _time.monotonic()
    if PROFILE not in {'SMOKE', 'FULL'}:
        raise ValueError('Only frozen SMOKE/FULL profiles are available')
    if type(MODEL_CONFIG) is not dict or set(MODEL_CONFIG) != {'input_root', 'explicit_roots'}:
        raise ValueError('Model configuration requires only input_root and explicit_roots')
    _roles = {'runtime', 'model', 'wheels', 'interpreter', 'adapter'}
    if (type(MODEL_CONFIG['explicit_roots']) is not dict
            or set(MODEL_CONFIG['explicit_roots']) - _roles):
        raise ValueError('explicit_roots may override only the five pinned Dataset roles')
    def _mount_path(value):
        # Pure string validation: do not stat, scan, import or open a Dataset here.
        if (type(value) is not str or not value.startswith('/') or len(value) > 4096
                or '\\\\' in value or ':' in value or any(ord(c) < 32 for c in value)
                or '..' in value.split('/')):
            raise ValueError('Dataset roots must be bounded absolute Linux paths')
    _mount_path(MODEL_CONFIG['input_root'])
    for _root in MODEL_CONFIG['explicit_roots'].values():
        if _root is not None:
            _mount_path(_root)
    if type(OUTPUT_ROOT) is not str or not OUTPUT_ROOT or type(SOURCE_PARENT) is not str or not SOURCE_PARENT:
        raise ValueError('Explicit nonempty output and source directory strings required')
    if SESSION_SECONDS is not None and (type(SESSION_SECONDS) not in (int, float)
            or not (65 < SESSION_SECONDS <= 14400)):
        raise ValueError('Session allowance must be finite, exceed 65 seconds and stay within total wall 14400; ledger also checks remaining wall')

    def _canonical(value):
        return _json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                           allow_nan=False).encode('utf-8')

    def _hash(raw):
        return _hashlib.sha256(raw).hexdigest()

    def _safe_path(name):
        if (type(name) is not str or not name or '\\\\' in name or ':' in name
                or _PurePosixPath(name).is_absolute()
                or any(part in {'', '.', '..'} for part in name.split('/'))
                or not name.startswith('tools/') or not name.endswith(('.py', '.json'))):
            raise ValueError('Unsafe embedded source path')

    def _no_links(path):
        for part in (path, *path.parents):
            if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
                raise ValueError('Source/output symlink or junction forbidden')

    def _pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate embedded JSON key')
            result[key] = value
        return result

    _packed = _base64.b64decode(PACKED_SOURCE_BASE64, validate=True)
    if _hash(_packed) != PACKED_SOURCE_SHA256:
        raise ValueError('Embedded compressed source hash differs')
    if type(UNPACKED_SOURCE_BYTES) is not int or not 0 < UNPACKED_SOURCE_BYTES <= 4_000_000:
        raise ValueError('Embedded source size outside fixed bounds')
    _decoder = _zlib.decompressobj()
    _raw = _decoder.decompress(_packed, UNPACKED_SOURCE_BYTES + 1)
    if (len(_raw) != UNPACKED_SOURCE_BYTES or not _decoder.eof
            or _decoder.unused_data or _decoder.unconsumed_tail):
        raise ValueError('Embedded source stream or decompression bound differs')
    _files = _json.loads(_raw, object_pairs_hook=_pairs)
    if type(_files) is not dict or set(_files) != set(FILE_HASHES):
        raise ValueError('Embedded closed inventory differs')
    for _name, _value in _files.items():
        _safe_path(_name)
        if type(_value) is not str or _hash(_value.encode('utf-8')) != FILE_HASHES[_name]:
            raise ValueError('Embedded source file hash differs: ' + _name)
    if _hash(_canonical(FILE_HASHES)) != BUNDLE_SOURCE_SHA256:
        raise ValueError('Embedded source identity differs')
    _package_hashes = {name[len(PACKAGE_PREFIX):]: value for name, value in FILE_HASHES.items()
                       if name.startswith(PACKAGE_PREFIX)}
    if _hash(_canonical(_package_hashes)) != PACKAGE_SOURCE_SHA256:
        raise ValueError('Package source identity differs')

    # Run only the already hash-verified stdlib guard before extracting source.
    # It does not import the package or inspect any declared Dataset path.
    _guard = {'__name__': '__irisx_prewrite_path_guard__'}
    exec(compile(_files[PACKAGE_PREFIX + 'path_guard.py'], '<trusted-path-guard>', 'exec'), _guard)
    _parent = _guard['normalized_path'](SOURCE_PARENT)
    _source = _parent / BUNDLE_SOURCE_SHA256
    _output = _guard['normalized_path'](OUTPUT_ROOT)
    _guard['guard_paths'](MODEL_CONFIG, {
        'source cache parent': _parent, 'source': _source, 'output': _output,
        'environment': _guard['environment_path'](_output)})
    if _output == _source or _source in _output.parents or _output in _source.parents:
        raise ValueError('Output and source trees must be separate')
    # A notebook rerun may reuse only the same verified source origin. Refuse
    # unrelated tools packages before source creation or namespace mutation.
    for _module_name, _module in list(_sys.modules.items()):
        if _module_name == 'tools' or _module_name.startswith('tools.'):
            _origin = getattr(_module, '__file__', None)
            if type(_origin) is not str:
                raise ValueError('Conflicting loaded tools namespace')
            _origin_path = _Path(_origin).absolute()
            try:
                _relative = _origin_path.relative_to(_source).as_posix()
            except ValueError:
                raise ValueError('Conflicting imported tools path; use a fresh kernel') from None
            if _relative not in FILE_HASHES:
                raise ValueError('Unbound imported tools module')
    _expected_dirs = {str(_PurePosixPath(name).parent) for name in _files}
    _expected_dirs |= {str(parent) for name in _files for parent in _PurePosixPath(name).parents
                       if str(parent) != '.'}
    if _source.exists():
        if not _source.is_dir():
            raise ValueError('Source identity path is not a directory')
        for _existing in _source.rglob('*'):
            _no_links(_existing)
            _relative = _existing.relative_to(_source).as_posix()
            if _existing.is_dir():
                if _relative not in _expected_dirs:
                    raise ValueError('Extra directory in closed source tree')
            elif (not _existing.is_file() or _relative not in FILE_HASHES
                    or _hash(_existing.read_bytes()) != FILE_HASHES[_relative]):
                raise ValueError('Existing source differs; no overwrite permitted')
    # Exclusive file creation preserves partial installs and refuses conflicts.
    for _name, _value in sorted(_files.items()):
        _target = _source.joinpath(*_name.split('/'))
        _no_links(_target)
        _target.parent.mkdir(parents=True, exist_ok=True)
        _no_links(_target)
        if _target.exists():
            if not _target.is_file() or _hash(_target.read_bytes()) != FILE_HASHES[_name]:
                raise ValueError('Existing source differs; no overwrite permitted')
        else:
            with _target.open('xb') as _stream:
                _stream.write(_value.encode('utf-8'))
                _stream.flush()
                _os.fsync(_stream.fileno())
    _install_seconds = _time.monotonic() - _install_start
    print('SOURCE-VERIFIED ' + PACKAGE_SOURCE_SHA256)
    print('SOURCE-INSTALL-WALL-SECONDS ' + str(_install_seconds))
    _old_bytecode_setting = _sys.dont_write_bytecode
    _old_path = list(_sys.path)
    _sys.dont_write_bytecode = True
    _sys.path.insert(0, str(_source))
    try:
        _importlib.invalidate_caches()
        _runner = _importlib.import_module('tools.arc_consolidated_20261010.runner')
        RESULT = _runner.run(OUTPUT_ROOT, manual_start=True, enable_model=ENABLE_MODEL,
                             profile=PROFILE, model_config=dict(MODEL_CONFIG),
                             resume=RESUME, session_seconds=SESSION_SECONDS,
                             bootstrap_seconds=_install_seconds)
        _terminal = _importlib.import_module('tools.arc_consolidated_20261010.terminal_summary')
        print(_terminal.render(RESULT))
        print('完整結果保留於上列 output_root/report_path/archive_path；顯示文字可能截短。程序返回不代表 VM 已停止計費。')
    finally:
        _sys.path[:] = _old_path
        _sys.dont_write_bytecode = _old_bytecode_setting
'''


def make_notebook(files):
    """Pure notebook assembly; injected test sources must be labelled mocks."""
    if type(files) is not dict or not files:
        raise ValueError("nonempty trusted source inventory required")
    for name, value in files.items():
        safe_name(name)
        if type(value) is not str:
            raise ValueError("embedded source must be UTF-8 text")
    files = dict(sorted(files.items()))
    hashes = {name: sha(value.encode("utf-8")) for name, value in files.items()}
    package_hashes = {name[len(PREFIX):]: value for name, value in hashes.items() if name.startswith(PREFIX)}
    raw = canonical(files)
    packed = zlib.compress(raw, 9)
    payload = {
        "PACKAGE_PREFIX": PREFIX,
        "FILE_HASHES": hashes,
        "BUNDLE_SOURCE_SHA256": sha(canonical(hashes)),
        "PACKAGE_SOURCE_SHA256": sha(canonical(package_hashes)),
        "PACKED_SOURCE_SHA256": sha(packed),
        "UNPACKED_SOURCE_BYTES": len(raw),
        "PACKED_SOURCE_BASE64": base64.b64encode(packed).decode("ascii"),
    }
    data = "# Exact trusted repository bytes; decompression occurs only after MANUAL_START.\n"
    data += "\n".join(key + " = " + repr(value) for key, value in payload.items()) + "\n"

    def cell(kind, source, name):
        result = {"cell_type": kind, "id": "consolidated-" + name,
                  "metadata": {}, "source": source.splitlines(keepends=True)}
        if kind == "code":
            result.update(execution_count=None, outputs=[])
        return result

    return {"nbformat": 4, "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python"},
                "irisx_suite": "arc-consolidated-20261010",
                "irisx_manual_start": False, "irisx_enable_model": False, "irisx_default_profile": "SMOKE",
                "irisx_gpu_executed": False, "irisx_training_executed": False,
                "irisx_source_identity_sha256": payload["PACKAGE_SOURCE_SHA256"],
                "irisx_bundle_sha256": payload["BUNDLE_SOURCE_SHA256"],
                "irisx_source_files": hashes, "irisx_optional_backend_pins": BACKEND_PINS,
                "irisx_publication_performed": False,
            },
            "cells": [cell("markdown", GUIDE, "guide"), cell("code", CONFIG, "config"),
                      cell("code", data, "payload"), cell("code", BOOTSTRAP, "run")]}


def build_notebook(destination=None):
    notebook = make_notebook(collect_sources())
    path = Path(destination) if destination is not None else ROOT / "notebooks" / NOTEBOOK_NAME
    if any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
           for p in (path, *path.parents)):
        raise ValueError("symlink/junction notebook destination")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return {"notebook": str(path), "sha256": sha(raw), "bytes": len(raw),
            "source_identity_sha256": notebook["metadata"]["irisx_source_identity_sha256"],
            "default_inert": True, "gpu_executed": False}


if __name__ == "__main__":
    print(json.dumps(build_notebook(), ensure_ascii=False, indent=2))
