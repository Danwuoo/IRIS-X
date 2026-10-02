"""Freeze all original source texts for native preprocessing inspection.

Reuse the already verified mask digests; do not repeat mask AST replay, model
work, evaluation or teacher-program execution.
"""
from __future__ import annotations
import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.arc_nvarc_combined import atomic, sha
from irisx.arc_nvarc_data import visible_task
from irisx.arc_nvarc_upstream import qwen_cell, source_bundle
from irisx.canonical import canonical_bytes, digest_value
from irisx.errors import ValidationError


def require(value, message):
    if not value: raise ValidationError(message)


def materialize(output):
    require(not output.exists(), 'new immutable complete source-view material required')
    import numpy as np
    from tokenizers import Tokenizer
    started = time.monotonic()
    package = ROOT / '.irisx/nvarc-original/runs/nvarc-original-qwen3-long-ttt-002/package-l4'
    summary = json.loads((package / 'stage-summary.json').read_bytes())
    require({p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file() and
        p.name != 'stage-summary.json'} == summary['inventory'], 'frozen source proposal package differs')
    plan = json.loads((package / 'plan.json').read_bytes())
    require(digest_value(plan) == summary['plan_digest'] and plan['source_view_count'] == 128,
        'complete frozen source proposal required')
    visible = json.loads((package / 'visible.json').read_bytes())
    require(len(visible) == 1 and all('output' not in row for task in visible.values() for row in task['test']) and
        digest_value([visible_task(key, value) for key, value in visible.items()]) == plan['visible_digest'],
        'truth-free fixed public source parent required')
    mask_path = ROOT / '.irisx/nvarc-original/manifests/original-ttt-loss-20261002-001/result.json'
    require(sha(mask_path) == 'bb6039067f5d008b465e5ff4e519ceb706211555ed8e318a1c84a577ba0ff484',
        'exact independently retained complete source-mask replay required')
    masks = json.loads(mask_path.read_bytes())
    require(masks['every_original_input_and_label_equal'] is True and masks['view_count'] == 128 and
        masks['source_rows_digest'] == plan['source_rows_digest'] and masks['parent_ids'] == plan['public_task_selection']['parent_ids'] and
        masks['exposure_tags'] == plan['public_task_selection']['exposure_tags'], 'source-mask lineage differs')
    model = ROOT / '.irisx/nvarc-original/materials/qwen3-published-sft139-20261002-001'
    proof = json.loads((model / 'independent-verification.json').read_bytes())
    tokenizer_path = model / 'model/tokenizer.json'
    require(proof['material_digest'] == plan['model_material_digest'] and
        sha(tokenizer_path) == proof['inventory']['tokenizer.json']['sha256'], 'exact original tokenizer required')
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    class OriginalTokenizer:
        def encode(self, text): return tokenizer.encode(text).ids
    bundle = package / 'source-bundle'
    with source_bundle(bundle, plan['source_bundle_digest']):
        loader = qwen_cell('arc_loader.py')
        formatter = loader.QwenFormatter(OriginalTokenizer())
        dataset = loader.ArcDataset(queries=visible, keys=list(visible))
        state = np.random.get_state()
        try: dataset = dataset.augment(n=16, shfl_keys=True, seed=1)
        finally: np.random.set_state(state)
        dataset = dataset.cut_to_len(formatter=formatter, name='text', max_len=8192)
        texts = dataset.as_list(formatter)
    require(len(texts) == 128, 'complete source view count differs')
    for index, (row, expected) in enumerate(zip(texts, masks['rows'])):
        ids = tokenizer.encode(row['text']).ids
        require(expected['row'] == index and hashlib.sha256(row['text'].encode()).hexdigest() == expected['original_text_sha256'] and
            digest_value(ids) == expected['input_ids_digest'] and len(ids) == expected['input_tokens'],
            'materialized original text/token prefix differs at ' + str(index))
    binding = json.loads((bundle / 'source-manifest.json').read_bytes())['notebooks']['qwen']
    notebook = bundle / binding['path']
    require(sha(notebook) == binding['sha256'], 'exact original solver notebook required')
    solver = next(''.join(c['source']).split('\n', 1)[1] for c in json.loads(notebook.read_bytes())['cells']
        if ''.join(c.get('source', [])).startswith('%%writefile arc_solver.py'))
    class_hashes = {n.name: hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
        for n in ast.parse(solver).body if isinstance(n, ast.ClassDef) and n.name in
        ('UnslothFixedTrainer', 'QwenDataCollatorForCompletionOnlyLM')}
    output.mkdir(parents=True)
    text_bytes = canonical_bytes(texts, newline=True)
    (output / 'texts.json.gz').write_bytes(gzip.compress(text_bytes, mtime=0))
    (output / 'solver.py').write_bytes(solver.encode())
    atomic(output / 'expected-rows.json', masks['rows'])
    result = {'format': 'irisx/nvarc-original-inspection-views-v1', 'outcome': 'complete-source-material',
        'source_proposal_plan_digest': summary['plan_digest'], 'source_bundle_digest': plan['source_bundle_digest'],
        'source_rows_digest': plan['source_rows_digest'], 'source_mask_proof_sha256': sha(mask_path),
        'model_material_digest': plan['model_material_digest'], 'original_notebook_sha256': binding['sha256'],
        'original_class_ast_sha256': class_hashes, 'solver_cell_sha256': sha(output / 'solver.py'),
        'parent_ids': masks['parent_ids'], 'exposure_tags': masks['exposure_tags'],
        'view_count': 128, 'input_tokens': masks['input_tokens'], 'supervised_tokens': masks['supervised_tokens'],
        'maximum_sequence_length': masks['maximum_sequence_length'], 'uncompressed_text_bytes': len(text_bytes),
        'texts_digest': digest_value(texts), 'every_text_token_digest_equal': True,
        'model_forwards': 0, 'optimizer_steps': 0, 'generations': 0, 'teacher_calls': 0, 'external_calls': 0,
        'mask_ast_replays': 0, 'correctness_scored': False, 'paid_usd': 0,
        'inventory': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in output.iterdir() if p.is_file()},
        'wall_seconds': time.monotonic() - started}
    atomic(output / 'result.json', result)
    return {'outcome': result['outcome'], 'proof_sha256': sha(output / 'result.json'),
        'wall_seconds': result['wall_seconds'], 'compressed_bytes': (output / 'texts.json.gz').stat().st_size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(materialize(parser.parse_args().output)))
