"""Closed source-only release bundle; no task payloads, credentials or weights."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import stat
import zipfile

from tools.arc_learning_agent_20261011.budget import canonical, atomic_json
from tools.arc_public_research_20261010.public_evaluator import SCORER_PINS
from tools.arc_public_research_20261010.source_pack import collect_sources as previous_sources

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = 'tools/arc_learning_agent_20261011'
CODE_REFERENCE = 'danielwuu/iris-x-learning-agent-code-20261011/1'
BASE_COMMIT = 'aec565393fa154ccb9857cb18bc3d6c79b1e7ce8'


def _regular(path):
    if any(p.is_symlink() for p in (path, *path.parents)) or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('regular source required')
    raw = path.read_bytes()
    if len(raw) > 4 * 1024**2: raise ValueError('source file cap')
    return raw


def _module_file(module, root):
    if module.startswith('tools'):
        base = root / module.replace('.', '/')
    elif module == 'irisx' or module.startswith('irisx.'):
        base = root / 'src' / module.replace('.', '/')
    else: return None
    for path in (base.with_suffix('.py'), base / '__init__.py'):
        if path.is_file(): return path.relative_to(root).as_posix()
    return None


def collect_sources(root=ROOT):
    root = Path(root)
    files = dict(previous_sources(root))
    required = {'tools/arc_next_training.py', 'tools/arc_next_materials.py',
                'src/irisx/arc_nvarc_data.py', 'tools/arc_program_v2.py',
                'research/arc-next-line/training-source-inventory.json'}
    required.update(p.relative_to(root).as_posix() for p in (root / 'tools/arc_next_suite_20261009/src').glob('*.py'))
    required.update(p.relative_to(root).as_posix() for p in (root / PACKAGE).glob('*.py')
                    if p.name != 'build_notebook.py')
    for name in required:
        if not (root / name).is_file():
            if name == 'tools/arc_program_v2.py': continue  # Actual VM dependency resolved by program_tools imports.
            raise ValueError('missing source closure: ' + name)
        files[name] = _regular(root / name)
    pending = list(files); visited = set()
    while pending:
        name = pending.pop()
        if name in visited or not name.endswith('.py'): continue
        visited.add(name)
        tree = ast.parse(files[name], filename=name)
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import): modules = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level:
                    current = name.removesuffix('.py').replace('/', '.')
                    if current.startswith('src.'): current = current[4:]
                    base = current.split('.')[:-node.level]
                    modules = ['.'.join(base + node.module.split('.'))]
                else: modules = [node.module]
            for module in modules:
                target = _module_file(module, root)
                if target and target not in files:
                    files[target] = _regular(root / target); pending.append(target)
                # Package initialization participates in normal Python imports.
                parts = module.split('.')
                for i in range(1, len(parts)):
                    package = _module_file('.'.join(parts[:i]), root)
                    if package and package.endswith('/__init__.py') and package not in files:
                        files[package] = _regular(root / package); pending.append(package)
    if len(files) > 512 or sum(map(len, files.values())) > 24 * 1024**2:
        raise ValueError('closed source size cap')
    if any(hashlib.sha256(files[name]).hexdigest() != expected for name, expected in SCORER_PINS.items()):
        raise ValueError('historical scorer changed')
    return dict(sorted(files.items()))


def build_code(output, root=ROOT):
    output = Path(output)
    if output.exists(): raise ValueError('fresh source output required')
    files = collect_sources(root); output.mkdir(parents=True)
    archive = output / 'source.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name, raw in files.items():
            info = zipfile.ZipInfo(name, (2026, 10, 11, 0, 0, 0))
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED; out.writestr(info, raw)
    manifest = {'format': 'irisx/learning-source-v1', 'base_commit': BASE_COMMIT, 'reference': CODE_REFERENCE,
                'source_identity': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
                'files': {name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                          for name, raw in files.items()},
                'archive': {'name': 'source.zip', 'bytes': archive.stat().st_size,
                            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()},
                'contains_weights': False, 'contains_public_answers': False,
                'publication_authorized': False, 'gpu_runtime_verified': False}
    atomic_json(output / 'manifest.json', manifest, exclusive=True)
    return manifest
