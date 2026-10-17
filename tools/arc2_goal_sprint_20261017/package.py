"""Prepare distinct private source Dataset and exact-byte offline notebooks.

This command is local-only: it never uploads, saves, runs, commits, or pushes.
Source is a strict Python/material allowlist, never a copy of a private notebook,
evaluator data, hidden files, credentials, outputs, or historical archives.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
from email.parser import BytesParser
import inspect
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import time
import zipfile

from . import launch, materials
from .bootstrap import REFERENCES
from .launch import require, regular, sha, write_new

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = ROOT / ".irisx/continuation-20261017/evidence/current-notebook/kernel-metadata.json"


def wheel_lock(wheelhouse):
    files = {}
    for path in sorted(Path(wheelhouse).glob("*.whl")):
        regular(path)
        with zipfile.ZipFile(path) as archive:
            candidates = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
            require(len(candidates) == 1, "one wheel distribution identity required")
            metadata = BytesParser().parsebytes(archive.read(candidates[0]))
        name = metadata["Name"].lower().replace("_", "-")
        version = metadata["Version"]
        require(name in {"pydantic", "pydantic-core", "annotated-types", "typing-inspection"}, "unexpected extra distribution")
        files[path.name] = {"name": name, "version": version, "sha256": sha(path), "bytes": path.stat().st_size,
                            "source": f"https://pypi.org/project/{name}/{version}/"}
    require({r["name"] for r in files.values()} == {"pydantic", "pydantic-core", "annotated-types", "typing-inspection"},
            "all four pinned AF3 dependency wheels required")
    return {"format": "irisx/goal-extra-wheel-lock-v1", "platform": "CPython312 Linux x86_64",
            "source_index": "https://pypi.org/simple", "files": files}


ENTRY_MODULES = (
    "tools.arc2_goal_sprint_20261017.launch", "tools.arc2_goal_sprint_20261017.bootstrap",
    "tools.arc2_goal_sprint_20261017.package", "tools.arc2_goal_sprint_20261017.run",
    "tools.arc2_goal_sprint_20261017.model", "tools.arc2_goal_sprint_20261017.data",
    "tools.arc2_goal_sprint_20261017.af3", "tools.arc_offline_evaluation",
    "tools.arc_learning_agent_20261011.process_guard",
    # runpy launches this solver dynamically; irisx is used inside the original scorer.
    "irisx.artifacts", "irisx.arc_agi2",
    "tools.arc2_agent_factory3_bridge_20261014.provenance",
)


def source_paths(root, entry_modules=ENTRY_MODULES):
    """Static local-import closure, including function-local/relative imports.

    Only local tools/src/irisx modules are considered; external imports come
    from the pinned wheelhouse. Dynamic runtime roots are explicit above. No
    test/release fixture, notebook, or arbitrary historical tree is glob-copied.
    """
    root = Path(root)
    queue = list(entry_modules)
    visited = set()
    paths = set()

    def resolve(module):
        if module == "irisx" or module.startswith("irisx."):
            base = root / "src" / module.replace(".", "/")
        elif module in {"tools", "src"} or module.startswith(("tools.", "src.irisx")):
            base = root / module.replace(".", "/")
        else:
            return None
        file = base.with_suffix(".py")
        package = base / "__init__.py"
        return file if file.is_file() else package if package.is_file() else None

    while queue:
        module = queue.pop()
        if module in visited:
            continue
        visited.add(module)
        path = resolve(module)
        if path is None:
            require(module not in entry_modules, "required runtime entry module missing: " + module)
            continue
        relative = path.relative_to(root)
        require(not any(part in {"tests", "fixtures", "release", "validation-tests", "__pycache__"}
                        or part.startswith("test_") or part.startswith(".") for part in relative.parts),
                "runtime import reaches excluded fixture/release source: " + module)
        regular(path)
        paths.add(path)
        parts = module.split(".")
        for end in range(1, len(parts)):
            parent = ".".join(parts[:end])
            if resolve(parent) is not None:
                queue.append(parent)
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            if isinstance(node, ast.Import):
                queue.extend(alias.name for alias in node.names if resolve(alias.name) is not None)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    prefix = package.split(".")
                    require(node.level <= len(prefix), "relative import escapes local package")
                    base = ".".join(prefix[:len(prefix) - node.level + 1])
                    target = base + ("." + node.module if node.module else "")
                else:
                    target = node.module or ""
                if resolve(target) is not None:
                    queue.append(target)
                queue.extend(target + "." + alias.name for alias in node.names
                             if resolve(target + "." + alias.name) is not None)
    af3 = root / "tools/arc2_agent_factory3_bridge_20261014"
    for relative in ("vendor/LICENSE", "vendor/NOTICE", "source-manifest.json"):
        if (af3 / relative).is_file():
            paths.add(regular(af3 / relative))
    # Explicit license/notice files for unchanged NVARC helper sources.
    for name in ("NOTICE-native.txt", "LICENSE-Apache-2.0.txt"):
        path = root / "research/stage4-e10/native-notices" / name
        if path.is_file():
            paths.add(regular(path))
    return sorted(paths)


def build_source(root, destination, extra_wheelhouse, run_id, *, adapter_resume_root=None,
                 adapter_resume_manifest_sha256=None, curriculum_root=None, curriculum_manifest_sha256=None,
                 curriculum_producer_hashes=None, training_root=None, training_manifest_path=None, public_path=None):
    destination = Path(destination)
    from tools.arc2_agent_factory3_bridge_20261014.provenance import verify_vendor
    verify_vendor()
    destination.mkdir(parents=True, exist_ok=False)
    packaged_paths = source_paths(root)
    for path in packaged_paths:
        relative = path.relative_to(root)
        regular(path)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    # Exact published material identities; no local training/evaluator data.
    qwen_materials = destination / "materials/qwen14b"
    qwen_materials.mkdir(parents=True)
    origin = Path(root) / "research/qwen14b-materials"
    contract_path = regular(origin / "material-contract.json")
    require(sha(contract_path) == materials.MODEL_CONTRACT_SHA256, "production Qwen contract differs")
    contract = json.loads(contract_path.read_bytes())
    overlay_rows = {name: {"bytes": row["size_bytes"], "sha256": row["sha256"]}
                    for name, row in contract["overlay_files"].items()}
    materials.exact_inventory(origin / "hf-overlay", overlay_rows, total_limit=32 * 1024**2)
    shutil.copyfile(contract_path, qwen_materials / "material-contract.json")
    (qwen_materials / "hf-overlay").mkdir()
    for name in overlay_rows:
        shutil.copyfile(regular(origin / "hf-overlay" / name), qwen_materials / "hf-overlay" / name)
    materials.package_materials(destination, adapter_resume_root=adapter_resume_root,
        adapter_resume_manifest_sha256=adapter_resume_manifest_sha256, curriculum_root=curriculum_root,
        curriculum_manifest_sha256=curriculum_manifest_sha256, curriculum_producer_hashes=curriculum_producer_hashes,
        training_root=training_root, training_manifest_path=training_manifest_path, public_path=public_path)
    lock = wheel_lock(extra_wheelhouse)
    extra = destination / "extra-wheels"
    extra.mkdir()
    for name in lock["files"]:
        shutil.copyfile(regular(Path(extra_wheelhouse) / name), extra / name)
    write_new(extra / "extra-wheel-lock.json", lock)
    # Runtime package roots work even when the repository uses namespace packages.
    for name in ("tools/__init__.py", "tools/arc2_goal_sprint_20261017/__init__.py", "src/__init__.py"):
        path = destination / name
        if not path.exists():
            path.write_text('"""IRIS-X packaged source namespace."""\n')
    files = {}
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            regular(path)
            files[path.relative_to(destination).as_posix()] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    require(files["tools/arc_offline_evaluation.py"]["sha256"] == launch.SCORER_SHA256, "original scorer bytes differ")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    require(re.fullmatch(r"[a-f0-9]{40}", revision), "actual source Git commit required")
    changed = subprocess.run(["git", "status", "--porcelain", "--", *[str(p.relative_to(root)) for p in packaged_paths],
                              "research/qwen14b-materials"], cwd=root, check=True, capture_output=True, text=True).stdout
    manifest = {"format": "irisx/goal-source-manifest-v1", "run_id": run_id,
                "baseline_commit": "6aefcc3af8a0a99196cf974bb2aaf30b83343137", "files": files,
                "source_git_commit": revision, "source_git_worktree_clean_for_packaged_files": not bool(changed.strip()),
                "contains_evaluator_data": False, "measurement": "public-development", "official_submission": False}
    return write_new(destination / "source-manifest.json", manifest)


def notebook(cells, run_id):
    return {"nbformat": 4, "nbformat_minor": 5, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}, "irisx_goal_run_id": run_id},
        "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                   "id": f"cell-{i}", "source": source} for i, source in enumerate(cells)]}


def notebook_source(request):
    # This small loader is the only embedded execution code. It verifies every
    # source byte against a notebook-pinned manifest before executing bootstrap.
    return '''import hashlib, json, pathlib, shutil, stat, subprocess, sys, time, zipfile
REQUEST = ''' + repr(request) + '''
def require(condition, message):
    if not condition: raise ValueError(message)
def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''): h.update(block)
    return h.hexdigest()
require(time.time() < REQUEST['session_deadline_epoch'] - 300, 'Original platform deadline expired')
owner, slug, version = REQUEST['source_dataset'].split('/')
mounts = [pathlib.Path('/kaggle/input') / slug, pathlib.Path('/kaggle/input/datasets') / owner / slug]
mounts = [p for p in mounts if p.is_dir()]
require(len(mounts) == 1, 'Exactly one source Dataset mount required')
mount = mounts[0]
manifest_path = mount / 'source-manifest.json'
require(not manifest_path.is_symlink() and digest(manifest_path) == REQUEST['source_manifest_sha256'], 'Source manifest pin differs')
manifest = json.loads(manifest_path.read_bytes())
actual = set()
for p in mount.rglob('*'):
    require(not p.is_symlink() and (p.is_file() or p.is_dir()), 'Source mount symlink/special file forbidden')
    if p.is_file(): actual.add(p.relative_to(mount).as_posix())
transport = manifest.get('transport')
expected = ({transport['filename']} if transport else set(manifest['files'])) | {'source-manifest.json'}
require(expected <= actual <= expected | {'dataset-metadata.json'}, 'Unexpected source mount inventory')
source = pathlib.Path(REQUEST['working_root'] + '-source')
source.mkdir(parents=True, exist_ok=False)
archive = None
if transport:
    require(transport['filename'] == 'source-payload.zip.bin', 'Exact source transport name required')
    require(transport['sha256'] == REQUEST['source_payload_sha256'], 'Notebook-pinned source transport differs')
    payload = mount / transport['filename']
    require(payload.stat().st_size == transport['bytes'] and digest(payload) == transport['sha256'], 'Source transport differs')
    archive = zipfile.ZipFile(payload)
    members = archive.infolist()
    require(len(members) == len(manifest['files']) and {m.filename for m in members} == set(manifest['files']), 'Exact archive members required')
    require(all((not m.is_dir() and stat.S_ISREG(m.external_attr >> 16) and (m.file_size == manifest['files'][m.filename]['bytes']) for m in members)), 'Regular bounded archive files required')
for name, row in manifest['files'].items():
    rel = pathlib.PurePosixPath(name)
    require(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe source path')
    dst = source / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if archive:
        with archive.open(name) as src, dst.open('xb') as out: shutil.copyfileobj(src, out)
    else:
        src = mount / name
        require(not any((p.is_symlink() for p in (src, *src.parents))), 'Symlink source forbidden')
        require(src.is_file() and src.stat().st_size == row['bytes'], 'Source file differs: ' + name)
        shutil.copyfile(src, dst)
    require(digest(dst) == row['sha256'], 'Source copy differs')
if archive: archive.close()
shutil.copyfile(manifest_path, source / 'source-manifest.json')
request_path = source / 'runtime-request.json'
with request_path.open('x') as f: json.dump(REQUEST, f, sort_keys=True)
subprocess.run([sys.executable, '-I', '-B', str(source / 'tools/arc2_goal_sprint_20261017/bootstrap.py'), '--request', str(request_path)], check=True)
'''


def source_transport(review, destination):
    """Flat .bin transport avoids Kaggle's per-directory ZIP prefix flattening."""
    review, destination = Path(review), Path(destination)
    manifest = json.loads(regular(review / "source-manifest.json").read_bytes())
    destination.mkdir(parents=True, exist_ok=False)
    payload = destination / "source-payload.zip.bin"
    with zipfile.ZipFile(payload, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, row in sorted(manifest["files"].items()):
            source = regular(review / name)
            require(sha(source) == row["sha256"] and source.stat().st_size == row["bytes"], "source changed before transport")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    manifest["transport"] = {"filename": payload.name, "bytes": payload.stat().st_size, "sha256": sha(payload),
                             "format": "zip-regular-files-exact-inventory"}
    return write_new(destination / "source-manifest.json", manifest)


def preflight_source(run_id):
    # No source Dataset dependency. No answer, tensor, quota, credential, or
    # competition read. The actual evaluator mount is tested with open/no read.
    helper = "\n".join(inspect.getsource(x) for x in (launch.require, launch.IsolationUnavailable,
        launch._Ruleset, launch._PathRule, launch.landlock_abi, launch.apply_landlock, launch.assert_denied))
    child = "import ctypes, errno, os, pathlib, platform, sys, json\nfrom pathlib import Path\n" + helper + '''
probe = sys.argv[1]
reads = [p for p in ('/usr','/lib','/lib64','/bin','/opt','/etc','/proc/self') if Path(p).exists()]
try:
    abi = apply_landlock(reads, ['/dev'])
    denied = assert_denied([probe])
    print(json.dumps({'landlock_abi': abi, 'actual_evaluator_open_denied': True, 'denied_probe': denied}))
except Exception as e:
    print(json.dumps({'landlock_available': False, 'error_type': type(e).__name__, 'error': str(e)}))
    sys.exit(2)
'''
    return '''import ctypes, importlib, importlib.metadata, json, os, pathlib, platform, shutil, subprocess, sys, time
def require(condition, message):
    if not condition: raise ValueError(message)
result = {'format': 'irisx/goal-platform-preflight-v1', 'run_id': ''' + repr(run_id) + ''', 'epoch': time.time(), 'python': sys.version, 'kernel': platform.release(), 'uid': os.getuid(), 'model_loaded': False, 'evaluator_answer_bytes_read': False, 'quota_queried': False}
result['dependencies'] = {}
for name in ('torch', 'transformers', 'peft', 'pydantic'):
    try:
        importlib.import_module(name)
        result['dependencies'][name] = {'version': importlib.metadata.version(name), 'imported': True}
    except Exception as e:
        result['dependencies'][name] = {'imported': False, 'error_type': type(e).__name__, 'error': str(e)[:300]}
base = pathlib.Path('/kaggle/input')
slug = 'iris-x-public120-data-20261010'
public = [p for p in (base / slug, base / 'datasets/danielwuu' / slug) if p.is_dir()]
result['public_mounts'] = [str(p) for p in public]
if len(public) == 1:
    probe = public[0] / 'evaluator/manifest.json'
    require(probe.is_file(), 'Actual evaluator manifest must exist')
    checked = subprocess.run([sys.executable, '-I', '-B', '-S', '-c', ''' + repr(child) + ''', str(probe)], capture_output=True, text=True, timeout=30, close_fds=True, stdin=subprocess.DEVNULL)
    result['landlock'] = {'returncode': checked.returncode, 'stdout': checked.stdout[-4000:], 'stderr': checked.stderr[-2000:]}
unshare = shutil.which('unshare')
if unshare:
    checked = subprocess.run([unshare, '--mount', '--propagation', 'private', '/bin/true'], capture_output=True, text=True, timeout=10, close_fds=True, stdin=subprocess.DEVNULL)
    result['private_mount_namespace'] = {'returncode': checked.returncode, 'stderr': checked.stderr[-1000:]}
else:
    result['private_mount_namespace'] = {'available': False, 'reason': 'unshare executable absent'}
output = pathlib.Path('/kaggle/working') / (result['run_id'] + '-preflight.json')
with output.open('x') as f: json.dump(result, f, indent=2, sort_keys=True)
print(json.dumps(result, indent=2, sort_keys=True))
'''


def metadata(original, filename, *, source_dataset=None, solver_dataset=None, enable_gpu=False):
    result = deepcopy(original)
    require(result.get("id_no") == 138123872 and result.get("id") == "danielwuu/iris-x-learning-agent-20261011",
            "same existing private notebook identity required")
    require(result.get("is_private") is True and result.get("machine_shape") == "NvidiaRtxPro6000", "existing private resource required")
    result.update(code_file=filename, is_private=True, enable_gpu=enable_gpu, enable_tpu=False, enable_internet=False)
    if not enable_gpu:
        # Kaggle machine_shape can override enable_gpu: omit it for CPU-only admission.
        result.pop("machine_shape", None)
        result["keywords"] = [key for key in result.get("keywords", []) if key != "gpu"]
    if source_dataset:
        selected = dict(REFERENCES)
        if solver_dataset:
            require(solver_dataset != REFERENCES["public"], "solver-only Dataset must be distinct from evaluator-bearing PUBLIC")
            selected["public"] = solver_dataset
        result["dataset_sources"] = [selected[role] for role in ("wheels", "interpreter", "training", "public")] + [source_dataset]
    result["model_sources"] = [REFERENCES["model"]]
    return result


def build(output, run_id, source_dataset, started_epoch, extra_wheelhouse, original_metadata=DEFAULT_METADATA, solver_dataset=None,
          *, solver_parameters=None, adapter_resume_root=None, adapter_resume_manifest_sha256=None,
          curriculum_root=None, curriculum_manifest_sha256=None, curriculum_producer_hashes=None,
          training_root=None, training_manifest_path=None, public_path=None):
    solver_parameters = materials.validate_solver_parameters(solver_parameters)
    output = Path(output).absolute()
    require(not output.exists(), "fresh local package identity required")
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]{3,95}", run_id), "fresh portable run identity required")
    require(re.fullmatch(r"danielwuu/[a-z0-9][a-z0-9-]+/1", source_dataset), "distinct private source Dataset numeric version1 required")
    require("iris-x-learning-agent-code-20261011" not in source_dataset, "historical source Dataset must not be reused")
    require(type(started_epoch) in {int, float} and math.isfinite(started_epoch) and 0 < started_epoch <= time.time(), "actual pre-dispatch epoch required")
    require(solver_dataset and solver_dataset != REFERENCES["public"], "solver-only Dataset required after unsupported platform isolation preflight")
    output.mkdir(parents=True)
    source = output / "source-dataset"
    review = output / "source-review"
    build_source(ROOT, review, extra_wheelhouse, run_id, adapter_resume_root=adapter_resume_root,
        adapter_resume_manifest_sha256=adapter_resume_manifest_sha256, curriculum_root=curriculum_root,
        curriculum_manifest_sha256=curriculum_manifest_sha256, curriculum_producer_hashes=curriculum_producer_hashes,
        training_root=training_root, training_manifest_path=training_manifest_path, public_path=public_path)
    fingerprint = source_transport(review, source)
    payload_sha256 = sha(source / "source-payload.zip.bin")
    owner, slug, _ = source_dataset.split("/")
    write_new(source / "dataset-metadata.json", {"id": f"{owner}/{slug}", "title": slug,
        "licenses": [{"name": "other"}], "description": "Private IRIS-X source-only successor. No evaluator data or official submission."})
    request = {"run_id": run_id, "source_dataset": source_dataset, "source_manifest_sha256": fingerprint,
               "source_payload_sha256": payload_sha256,
               "input_root": "/kaggle/input", "working_root": "/kaggle/working/" + run_id,
               "started_epoch": started_epoch, "session_deadline_epoch": started_epoch + 43200,
               "runtime_root": "/kaggle/temp/" + run_id,
               "evaluation_mode": "external-cpu" if solver_dataset else "landlock-local"}
    if solver_parameters:
        request["solver_parameters"] = solver_parameters
    if (review / materials.INDEX).is_file():
        request["continuation_materials_sha256"] = sha(review / materials.INDEX)
    if solver_dataset:
        require(re.fullmatch(r"danielwuu/[a-z0-9][a-z0-9-]+/1", solver_dataset), "distinct pinned solver-only Dataset version1 required")
        request["solver_dataset"] = solver_dataset
    original = json.loads(regular(original_metadata).read_bytes())
    prepare_request = {**request, "prepare_only": True, "run_id": run_id + "-prepare",
        "working_root": request["working_root"] + "-prepare", "runtime_root": request["runtime_root"] + "-prepare"}
    for kind, code, active, attach_source in (
            ("active-notebook", notebook_source(request), True, True),
            ("prepare-notebook", notebook_source(prepare_request), False, True),
            ("preflight-notebook", preflight_source(run_id), False, False)):
        directory = output / kind
        directory.mkdir()
        filename = "iris-x-goal-sprint-20261017.ipynb"
        write_new(directory / filename, notebook([code], run_id))
        write_new(directory / "kernel-metadata.json", metadata(original, filename,
                  source_dataset=source_dataset if attach_source else None,
                  solver_dataset=solver_dataset if attach_source else None, enable_gpu=active))
    receipt = {"run_id": run_id, "source_dataset": source_dataset, "source_manifest_sha256": fingerprint,
               "source_payload_sha256": payload_sha256, "source_review_directory": str(review),
               "source_upload_directory": str(source), "source_upload_dir_mode": "skip",
               "source_files": len(json.loads((source / "source-manifest.json").read_bytes())["files"]),
               "source_bytes": sum(p.stat().st_size for p in source.rglob("*") if p.is_file()),
               "started_epoch": started_epoch, "session_deadline_epoch": started_epoch + 43200,
               "published": False, "run_dispatched": False, "is_private_required": True,
               "evaluation_mode": request["evaluation_mode"], "solver_dataset": solver_dataset}
    write_new(output / "package-receipt.json", receipt)
    return receipt


def build_notebook_only(destination, run_id, source_dataset, source_manifest_sha256, solver_dataset, started_epoch,
                        *, source_payload_sha256=None, prepare_only=False, original_metadata=DEFAULT_METADATA,
                        solver_parameters=None, continuation_materials_sha256=None):
    """Use already-published immutable source with a NEW actual dispatch epoch.

    Optional material roots never come from this request. The pinned source
    index alone supplies them; material changes require a new source identity.
    """
    solver_parameters = materials.validate_solver_parameters(solver_parameters)
    require(continuation_materials_sha256 is None or materials.valid_sha(continuation_materials_sha256),
            "verified continuation material index SHA required")
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]{3,95}", run_id), "portable fresh run identity required")
    require(re.fullmatch(r"[a-f0-9]{64}", source_manifest_sha256 or ""), "verified immutable source manifest pin required")
    require(re.fullmatch(r"[a-f0-9]{64}", source_payload_sha256 or ""), "verified immutable source payload pin required")
    require(type(started_epoch) in {int, float} and math.isfinite(started_epoch) and 0 < started_epoch <= time.time(), "actual pre-dispatch epoch required")
    require(re.fullmatch(r"danielwuu/[a-z0-9][a-z0-9-]+/1", source_dataset or ""), "pinned private source Dataset version1 required")
    require(type(prepare_only) is bool, "Boolean preparation-only flag required")
    require(solver_dataset and solver_dataset != REFERENCES["public"], "verified solver-only Dataset required after platform isolation preflight")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    request = {"run_id": run_id, "source_dataset": source_dataset, "source_manifest_sha256": source_manifest_sha256,
               "source_payload_sha256": source_payload_sha256,
               "solver_dataset": solver_dataset, "evaluation_mode": "external-cpu", "prepare_only": prepare_only,
               "input_root": "/kaggle/input", "working_root": "/kaggle/working/" + run_id,
               "runtime_root": "/kaggle/temp/" + run_id, "started_epoch": started_epoch,
               "session_deadline_epoch": started_epoch + 43200}
    if solver_parameters:
        request["solver_parameters"] = solver_parameters
    if continuation_materials_sha256 is not None:
        request["continuation_materials_sha256"] = continuation_materials_sha256
    filename = "iris-x-goal-sprint-20261017.ipynb"
    write_new(destination / filename, notebook([notebook_source(request)], run_id))
    write_new(destination / "kernel-metadata.json", metadata(json.loads(regular(original_metadata).read_bytes()), filename,
        source_dataset=source_dataset, solver_dataset=solver_dataset, enable_gpu=not prepare_only))
    write_new(destination / "dispatch-request.json", request)
    return {"notebook_directory": str(destination), "source_manifest_sha256": source_manifest_sha256,
            "source_payload_sha256": source_payload_sha256,
            "prepare_only": prepare_only, "enable_gpu": not prepare_only, "started_epoch": started_epoch,
            "source_rebuilt": False, "published": False}


def build_solver_projection(solver_root, destination, reference):
    """Stage only the exact pinned solver projection; never open evaluator bytes."""
    require(re.fullmatch(r"danielwuu/[a-z0-9][a-z0-9-]+/1", reference or ""), "fresh private solver Dataset version1 required")
    require(reference != REFERENCES["public"], "original evaluator-bearing Dataset identity must be preserved")
    manifest = launch.verify_inventory(solver_root, launch.SOLVER_MANIFEST_SHA256)
    require(set(manifest["files"]) == {"LICENSE", "NOTICE", "public-challenges.json"}, "exact solver-only file roles required")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    target = destination / "solver"
    target.mkdir()
    for name in (*manifest["files"], "manifest.json"):
        shutil.copyfile(regular(Path(solver_root) / name), target / name)
    launch.verify_inventory(target, launch.SOLVER_MANIFEST_SHA256)
    owner, slug, _ = reference.split("/")
    write_new(destination / "dataset-metadata.json", {"id": f"{owner}/{slug}", "title": slug,
        "licenses": [{"name": "other"}], "description": "Private exact pinned ARC public solver projection. Demonstrations and test inputs only; no evaluator or test answers."})
    return {"reference": reference, "solver_manifest_sha256": launch.SOLVER_MANIFEST_SHA256,
            "evaluator_data_included": False, "files": sorted(p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()),
            "published": False, "is_private_required": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-dataset")
    parser.add_argument("--solver-dataset")
    parser.add_argument("--solver-only-from")
    parser.add_argument("--notebook-only", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--source-manifest-sha256")
    parser.add_argument("--source-payload-sha256")
    parser.add_argument("--started-epoch", type=float)
    parser.add_argument("--extra-wheelhouse")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA))
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--solver-parameters", help="JSON file with only allowlisted numerical/algorithm tuning")
    parser.add_argument("--continuation-materials-sha256", help="existing source index pin, notebook-only")
    parser.add_argument("--adapter-resume-root")
    parser.add_argument("--adapter-resume-manifest-sha256")
    parser.add_argument("--curriculum-root")
    parser.add_argument("--curriculum-manifest-sha256")
    parser.add_argument("--curriculum-producer-hashes", help="explicit external JSON producer SHA map")
    parser.add_argument("--training-root")
    parser.add_argument("--training-manifest-path")
    parser.add_argument("--public-path", help="solver-only PUBLIC challenges for actual load_data admission")
    args = parser.parse_args()
    solver_parameters = None if args.solver_parameters is None else json.loads(regular(args.solver_parameters).read_bytes())
    material_inputs = dict(adapter_resume_root=args.adapter_resume_root,
        adapter_resume_manifest_sha256=args.adapter_resume_manifest_sha256, curriculum_root=args.curriculum_root,
        curriculum_manifest_sha256=args.curriculum_manifest_sha256,
        curriculum_producer_hashes=None if args.curriculum_producer_hashes is None else json.loads(regular(args.curriculum_producer_hashes).read_bytes()),
        training_root=args.training_root, training_manifest_path=args.training_manifest_path, public_path=args.public_path)
    if args.notebook_only or args.solver_only_from or args.preflight_only:
        require(not any(v is not None for v in material_inputs.values()), "new materials require a new source build")
    if not args.notebook_only:
        require(args.continuation_materials_sha256 is None, "existing continuation index pin is notebook-only")
    if args.solver_only_from or args.preflight_only:
        require(solver_parameters is None, "solver tuning requires a source or notebook build")
    if args.notebook_only:
        print(json.dumps(build_notebook_only(args.output, args.run_id, args.source_dataset, args.source_manifest_sha256,
            args.solver_dataset, args.started_epoch, source_payload_sha256=args.source_payload_sha256,
            prepare_only=args.prepare_only, original_metadata=args.metadata, solver_parameters=solver_parameters,
            continuation_materials_sha256=args.continuation_materials_sha256), sort_keys=True))
        return
    if args.solver_only_from:
        print(json.dumps(build_solver_projection(args.solver_only_from, args.output, args.solver_dataset), sort_keys=True))
        return
    if args.preflight_only:
        destination = Path(args.output)
        destination.mkdir(parents=True, exist_ok=False)
        filename = "iris-x-goal-preflight-20261017.ipynb"
        write_new(destination / filename, notebook([preflight_source(args.run_id)], args.run_id))
        write_new(destination / "kernel-metadata.json", metadata(json.loads(regular(args.metadata).read_bytes()), filename))
        print(json.dumps({"preflight_directory": str(destination), "enable_gpu": False, "enable_internet": False}))
        return
    require(args.source_dataset and args.started_epoch and args.extra_wheelhouse, "source dataset, epoch and extra wheels required")
    print(json.dumps(build(args.output, args.run_id, args.source_dataset, args.started_epoch, args.extra_wheelhouse, args.metadata, solver_dataset=args.solver_dataset,
        solver_parameters=solver_parameters, **material_inputs), sort_keys=True))


if __name__ == "__main__":
    main()
