"""Audit every published TRM training identifier without staging evaluation labels.

The tiny prefix is training-only. Complete input/label arrays remain in the
verified ZIP: this command neither expands 39 GB nor sends data to a solver.
"""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from irisx.arc_nvarc_original_corpus import parent_metadata
from irisx.arc_nvarc_upstream import SOURCE
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def audit():
    import numpy as np
    import torch
    from tools.nvarc_source import verify as verify_source
    folder = ROOT / '.irisx/nvarc-original/materials/trm-published-train-20261002-002'
    output = ROOT / '.irisx/nvarc-original/manifests/trm-published-train-audit-20261002-001'
    if output.exists():
        raise ValidationError('new TRM training lineage audit required')
    acquisition = json.loads((folder / 'acquisition.json').read_bytes())
    inventory = json.loads((folder / 'archive-inventory.json').read_bytes())
    headers = json.loads((folder / 'array-header-observation.json').read_bytes())
    archive_path = folder / 'arc-prize-trm-training-data.zip'
    if (acquisition['dataset'] != 'cpmpml/arc-prize-trm-training-data/1' or acquisition['role'] != 'train' or
            acquisition['state'] != 'verified-published-trm-arrays' or not acquisition['crc_verified'] or
            sha_file(folder / 'archive-inventory.json') != acquisition['inventory_sha256'] or
            sha_file(folder / 'array-header-observation.json') != acquisition['header_observation_sha256'] or
            sha_file(archive_path) != acquisition['archive_sha256']):
        raise ValidationError('verified original TRM training archive required')
    source_proof = verify_source(SOURCE, json.loads((ROOT / 'trials/arc-agi-2-qwen35-nvarc/source-manifest.json').read_bytes()))
    members = {item['path']: item for item in inventory['members']}
    catalog_path = ROOT / '.irisx/nvarc-original/materials/corpus-20261001-001/catalog.json'
    catalog = json.loads(catalog_path.read_bytes())
    meta = headers['datasets']['train/dataset.json']
    if (meta['seq_len'] != 900 or meta['vocab_size'] != 12 or meta['num_puzzle_identifiers'] != 1041208 or
            meta['total_groups'] != 4073 or meta['total_puzzles'] != 1041207):
        raise ValidationError('published TRM source/checkpoint dimensions differ')
    with zipfile.ZipFile(archive_path) as archive:
        def retained_member(name):
            raw = archive.read(name)
            if len(raw) != members[name]['bytes'] or hashlib.sha256(raw).hexdigest() != members[name]['sha256']:
                raise ValidationError('TRM audited member differs: ' + name)
            return raw
        identifiers = json.loads(retained_member('identifiers.json'))
        arrays = {name: np.load(io.BytesIO(retained_member('train/all__' + name + '.npy')), allow_pickle=False)
                  for name in ('puzzle_identifiers', 'puzzle_indices', 'group_indices')}
        puzzle_ids, puzzle_indices, group_indices = (arrays[name] for name in ('puzzle_identifiers', 'puzzle_indices', 'group_indices'))
        examples = headers['arrays']['train/all__inputs.npy']['shape'][0]
        if (len(identifiers) != 1041208 or identifiers[0] != '<blank>' or len(set(identifiers)) != len(identifiers) or
                not np.array_equal(puzzle_ids, np.arange(1, len(identifiers), dtype=np.int32)) or
                puzzle_indices.shape != (1041208,) or puzzle_indices[0] != 0 or puzzle_indices[-1] != examples or
                np.any(np.diff(puzzle_indices) <= 0) or group_indices.shape != (4074,) or group_indices[0] != 0 or
                group_indices[-1] != len(puzzle_ids) or np.any(np.diff(group_indices) <= 0)):
            raise ValidationError('TRM closed training identifier/index axes differ')
        records, source_counts, exposure_counts, view_counts = [], Counter(), Counter(), Counter()
        concept = set(catalog['concept_ids'])
        for group, (start, end) in enumerate(zip(group_indices[:-1], group_indices[1:])):
            start, end = int(start), int(end)
            base = identifiers[start + 1]
            if base in concept:
                source = 'concept'
                parents, tags = parent_metadata(source, base, catalog, {})
            elif re.fullmatch(r'[0-9a-f]{8}_[0-9a-f]{8}', base):
                source = 'published-sdg'
                parents, tags = parent_metadata('nvarc_training', base, catalog,
                    {('nvarc_training', base): {'parent_ids': sorted(set(base.split('_'))), 'status': 'published-trm-lineage'}})
            elif base in catalog['evaluation_ids']:
                source = 'arc-evaluation'
                parents, tags = parent_metadata('arc2_evaluation6', base, catalog, {})
            else:
                source = 'arc-training'
                parents, tags = parent_metadata('arc2_training', base, catalog, {})
            if not 1 <= end - start <= 257:
                raise ValidationError('TRM original augmentation group bound differs')
            for name in identifiers[start + 2:end + 1]:
                match = re.fullmatch(re.escape(base) + r'\|\|\|t([0-7])\|\|\|([0-9]{10})', name)
                if match is None or sorted(match[2]) != list('0123456789'):
                    raise ValidationError('TRM original D4/color identifier differs')
            record = {'group': group, 'base': base, 'source': source, 'parent_ids': parents, 'exposure_tags': tags,
                      'identifier_range': [start + 1, end + 1], 'puzzle_range': [start, end],
                      'example_range': [int(puzzle_indices[start]), int(puzzle_indices[end])],
                      'views': end - start, 'filtered': False}
            records.append(record)
            source_counts[source] += 1
            exposure_counts.update(tags)
            view_counts[end - start] += 1
        prefix = {}
        for field in ('inputs', 'labels'):
            with archive.open('train/all__' + field + '.npy') as stream:
                version = np.lib.format.read_magic(stream)
                shape, fortran, dtype = np.lib.format.read_array_header_1_0(stream) if version == (1, 0) else np.lib.format.read_array_header_2_0(stream)
                if shape != (examples, 900) or fortran or dtype != np.dtype('uint8'):
                    raise ValidationError('TRM training prefix numeric header differs')
                prefix[field] = np.frombuffer(stream.read(8 * 900), dtype=np.uint8).copy().reshape(8, 900)
                if np.any(prefix[field] > 11):
                    raise ValidationError('TRM training prefix vocabulary differs')
    prefix['puzzle_identifiers'] = puzzle_ids[np.searchsorted(puzzle_indices, np.arange(8), side='right') - 1].copy()
    loader_path = SOURCE / 'NVARC/external/TinyRecursiveModels/puzzle_dataset.py'
    tree = ast.parse(loader_path.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'PuzzleDataset')
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '_collate_batch')
    namespace = {'np': np, 'torch': torch, 'IGNORE_LABEL_ID': -100}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(loader_path), 'exec'), namespace)
    collated = namespace['_collate_batch'](SimpleNamespace(metadata=SimpleNamespace(**meta), local_batch_size=8), prefix)
    if (not torch.equal(collated['inputs'], torch.from_numpy(prefix['inputs'].astype(np.int32))) or
            not torch.equal(collated['labels'], torch.from_numpy(np.where(prefix['labels'] == 0, -100, prefix['labels'].astype(np.int32)))) or
            not torch.equal(collated['puzzle_identifiers'], torch.from_numpy(prefix['puzzle_identifiers'].astype(np.int32)))):
        raise ValidationError('actual source TRM collation differs from independent mask/identifier oracle')
    output.mkdir(parents=True)
    with (output / 'group-lineage.jsonl').open('wb') as stream:
        for record in records:
            stream.write(canonical_bytes(record, newline=True))
    np.savez(output / 'training-prefix.npz', **prefix)
    report = {'format': 'irisx/nvarc-published-trm-training-audit-v1', 'owner_decision': 'Decision 0053',
        'dataset': acquisition['dataset'], 'archive_sha256': acquisition['archive_sha256'],
        'catalog_sha256': sha_file(catalog_path), 'source_verification_digest': digest_value(source_proof),
        'metadata': meta, 'identifiers_verified': len(identifiers), 'examples_indexed': examples,
        'groups_by_source': dict(source_counts), 'groups_by_exposure': dict(exposure_counts),
        'groups_by_view_count': {str(key): value for key, value in sorted(view_counts.items())},
        'group_lineage_sha256': sha_file(output / 'group-lineage.jsonl'),
        'source_collator_sha256': sha_file(loader_path), 'source_collator_prefix_rows': 8,
        'prefix_input_tokens': int(collated['inputs'].numel()),
        'prefix_supervised_tokens': int((collated['labels'] != -100).sum()),
        'training_prefix_sha256': sha_file(output / 'training-prefix.npz'),
        'contains_training_labels': True, 'solver_staging_authorized': False,
        'evaluation_members_read': [], 'training_filtered': False, 'full_arrays_extracted': False,
        'teacher_calls': 0, 'model_calls': 0, 'correctness_scored': False, 'maximum_paid_usd': 0}
    atomic(output / 'audit.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    audit()
