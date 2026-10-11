"""Build a closed, training-only source material from exact public upstream blobs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from tools.arc_learning_agent_20261011.budget import atomic_json
from tools.arc_learning_agent_20261011.data import load_official_training

REFERENCE = 'danielwuu/iris-x-learning-training-20261011/1'
ROOT = Path(__file__).resolve().parents[2]


def build_training_assets(source_dir, license_path, output_root, *, protected_ids):
    source_dir, license_path, output = map(Path, (source_dir, license_path, output_root))
    if output.exists(): raise ValueError('fresh training material identity required')
    tasks, receipt = load_official_training(source_dir,
        ROOT / 'research/arc-next-line/training-source-inventory.json', protected_ids=protected_ids)
    from tools.arc_public_research_20261010.public_data import LICENSE_SHA256
    raw_license = license_path.read_bytes()
    if hashlib.sha256(raw_license).hexdigest() != LICENSE_SHA256:
        raise ValueError('same pinned upstream Apache2 license required')
    output.mkdir(parents=True)
    for task_id in sorted(tasks):
        target = output / 'data/training' / (task_id + '.json'); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source_dir / (task_id + '.json')).read_bytes())
    (output / 'LICENSE').write_bytes(raw_license)
    (output / 'NOTICE').write_text('ARC-AGI-2 official training source at f3283f727488ad98fe575ea6a5ac981e4a188e49. Apache-2.0; original notices retained. Original training-file test fields are preserved for byte identity but excluded by the training loader. No public evaluation files are included.\n')
    (output / 'training-source-inventory.json').write_bytes(
        (ROOT / 'research/arc-next-line/training-source-inventory.json').read_bytes())
    files = {p.relative_to(output).as_posix(): {'bytes': p.stat().st_size,
             'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(output.rglob('*')) if p.is_file()}
    manifest = {'format': 'irisx/learning-training-material-v1', 'reference': REFERENCE,
                'files': files, 'upstream': receipt, 'tasks': len(tasks),
                'license': 'Apache-2.0', 'public_evaluation_files': 0,
                'published': False, 'protected_ids': sorted(protected_ids)}
    atomic_json(output / 'manifest.json', manifest, exclusive=True)
    return {'reference': REFERENCE, 'manifest_sha256': hashlib.sha256((output / 'manifest.json').read_bytes()).hexdigest(),
            'files': len(files), 'tasks': len(tasks), 'publication_status': 'local-prepared-only'}
