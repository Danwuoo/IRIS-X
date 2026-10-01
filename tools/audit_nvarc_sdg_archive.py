"""Profile all published SDG metadata with every raw member digest rechecked.

Only teacher and parent metadata columns are decoded. No generated Python is
compiled/executed, no response is sent to a model, and no pairs are accepted.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic
from irisx.arc_nvarc_datasets import sha_file
from irisx.canonical import canonical_bytes
from irisx.errors import ValidationError


def audit():
    import pyarrow.parquet as pq
    material = ROOT / '.irisx/nvarc-original/materials/sdg-artifacts-20261002-resume-001'
    output = ROOT / '.irisx/nvarc-original/manifests/sdg-full-profile-20261002-001'
    acquisition = json.loads((material / 'acquisition.json').read_bytes())
    inventory = json.loads((material / 'archive-inventory.json').read_bytes())
    if (output.exists() or acquisition['state'] != 'verified-published-raw-artifacts' or
            acquisition['dataset'] != 'sorokin/nvarc-artifacts-puzzles/1' or not acquisition['crc_verified'] or
            sha_file(material / 'archive-inventory.json') != acquisition['inventory_sha256'] or
            inventory['member_count'] != 192 or acquisition['file_count'] != 192 or
            inventory['archive_sha256'] != acquisition['archive_sha256'] or
            inventory['uncompressed_bytes'] != 47514077184):
        raise ValidationError('complete verified original SDG archive required before profiling')
    expected = {item['path']: item for item in inventory['members']}
    archive_path = material / 'nvarc-artifacts-puzzles.zip'
    if archive_path.is_symlink() or archive_path.stat().st_size != acquisition['archive_bytes']:
        raise ValidationError('original SDG archive path/length differs')
    catalog_path = ROOT / '.irisx/nvarc-original/materials/corpus-20261001-001/catalog.json'
    catalog = json.loads(catalog_path.read_bytes())
    categories = {'arc-evaluation-ancestor': set(catalog['evaluation_ids']),
                  'protected-parent-or-visible-family': set(catalog['excluded_parent_ids']),
                  **{key + '-ancestor': set(values) for key, values in catalog['protected_categories'].items()}}
    known = set(catalog['training_ids']) | set(catalog['evaluation_ids'])
    cache, parent_counts = {}, defaultdict(Counter)
    profiles, exposures, totals = defaultdict(Counter), defaultdict(Counter), Counter()
    output.mkdir(parents=True)
    started = time.monotonic()
    ledger = {'owner_decision': 'Decision 0053', 'material': material.name,
              'acquisition_sha256': sha_file(material / 'acquisition.json'),
              'archive_inventory_sha256': acquisition['inventory_sha256'],
              'members_reserved': 0, 'members_completed': 0, 'maximum_wall_seconds': 1800,
              'maximum_member_bytes': 1024**3, 'teacher_calls': 0, 'program_executions': 0,
              'model_calls': 0, 'state': 'metadata-profile'}
    atomic(output / 'ledger.json', ledger)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            if {item.filename: item.file_size for item in archive.infolist() if not item.is_dir()} != {
                    name: item['bytes'] for name, item in expected.items()}:
                raise ValidationError('closed original SDG member inventory differs')
            for name, member in sorted(expected.items()):
                if time.monotonic() - started > 1800 or member['bytes'] > 1024**3:
                    raise ValidationError('SDG metadata profile resource ceiling reached')
                match = re.fullmatch(r'(summaries|mixtures|inputs|outputs)/data-[0-9]{5}\.parquet', name)
                if match is None:
                    raise ValidationError('original SDG metadata member path differs')
                stage = match[1]
                ledger['members_reserved'] += 1
                atomic(output / 'ledger.json', ledger)
                raw = archive.read(name)
                if len(raw) != member['bytes'] or hashlib.sha256(raw).hexdigest() != member['sha256']:
                    raise ValidationError('SDG complete raw member digest differs: ' + name)
                parquet = pq.ParquetFile(io.BytesIO(raw))
                parents_columns = ['puzzle_name'] if stage == 'summaries' else ['puzzle_name1', 'puzzle_name2']
                columns = ['model_name', 'reasoning_level', *parents_columns]
                if not set(columns) <= set(parquet.schema_arrow.names):
                    raise ValidationError('SDG original metadata columns differ')
                rows = 0
                for batch in parquet.iter_batches(batch_size=4096, columns=columns):
                    if time.monotonic() - started > 1800:
                        raise ValidationError('SDG metadata profile wall ceiling reached')
                    for item in batch.to_pylist():
                        model, reasoning = item['model_name'], item['reasoning_level']
                        if not isinstance(model, str) or not model or reasoning is not None and not isinstance(reasoning, str):
                            raise ValidationError('SDG original teacher metadata contract differs')
                        source_parents = [item[key] for key in parents_columns]
                        if any(not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{8}', value) is None for value in source_parents):
                            raise ValidationError('SDG original parent metadata contract differs')
                        parents = tuple(sorted(set(source_parents)))
                        if parents not in cache:
                            values = set(parents)
                            tags = [key for key, ids in categories.items() if values & ids]
                            if not values <= known:
                                tags.append('unresolved-original-artifact-ancestor')
                            if not tags:
                                tags.append('public-training-only')
                            cache[parents] = tags
                        profiles[stage][model, reasoning] += 1
                        exposures[stage].update(cache[parents])
                        parent_counts[parents][stage] += 1
                        rows += 1
                if rows != parquet.metadata.num_rows:
                    raise ValidationError('SDG complete metadata row coverage differs')
                totals[stage] += rows
                with (output / 'members.jsonl').open('ab') as stream:
                    stream.write(canonical_bytes({**member, 'stage': stage, 'parquet_rows': rows,
                        'row_groups': parquet.metadata.num_row_groups, 'decoded_columns': columns}, newline=True))
                del parquet, raw
                ledger['members_completed'] += 1
                atomic(output / 'ledger.json', ledger)
        with (output / 'parent-lineage.jsonl').open('wb') as stream:
            for parents, counts in sorted(parent_counts.items()):
                stream.write(canonical_bytes({'parent_ids': list(parents), 'exposure_tags': cache[parents],
                    'records_by_stage': dict(counts), 'filtered': False}, newline=True))
        report = {'format': 'irisx/nvarc-complete-sdg-metadata-profile-v1', 'dataset': acquisition['dataset'],
            'archive_sha256': acquisition['archive_sha256'], 'archive_container_digest_rechecked': False,
            'all_192_raw_member_digests_rechecked': True, 'catalog_sha256': sha_file(catalog_path),
            'rows_by_stage': dict(totals), 'teacher_profiles': {stage: [
                {'model_name': model, 'reasoning_level': reasoning, 'rows': count}
                for (model, reasoning), count in sorted(counts.items(), key=lambda item: repr(item[0]))]
                for stage, counts in profiles.items()},
            'exposure_rows_by_stage': {stage: dict(counts) for stage, counts in exposures.items()},
            'unique_parent_sets': len(parent_counts), 'parent_lineage_sha256': sha_file(output / 'parent-lineage.jsonl'),
            'member_metadata_sha256': sha_file(output / 'members.jsonl'),
            'teacher_calls': 0, 'program_executions': 0, 'model_calls': 0, 'pairs_accepted': 0,
            'program_semantics_verified': False, 'training_filtered': False, 'correctness_scored': False,
            'maximum_paid_usd': 0, 'wall_seconds': time.monotonic() - started}
        atomic(output / 'profile.json', report)
        ledger.update(state='verified-complete-metadata-profile', elapsed_seconds=time.monotonic() - started)
        atomic(output / 'ledger.json', ledger)
        print(json.dumps(report), flush=True)
    except BaseException as error:
        ledger.update(state='incomplete-retained', error_type=type(error).__name__, elapsed_seconds=time.monotonic() - started)
        atomic(output / 'ledger.json', ledger)
        raise


if __name__ == '__main__':
    audit()
