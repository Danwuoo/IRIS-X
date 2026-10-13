"""Pure original-v35 launch provenance replay. Never runtime/closure authority.

The caller independently pins this helper and the supplement manifest. No
provider, credential, model, scorer, clock sampling or ZIP member access occurs.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import types

FORMAT = 'irisx/run006-original-v35-launch-lineage-v1'
ASSEMBLY_SHA = 'de68ffa281990b844e41ea41d11357b2214a973048cd8e14ae64cab39159a5a0'
MANIFEST_SHA = '76b2e004770e1f41e9c2352fa9817bc185ea5fded75d9fd8ce29d50453e7b7ca'
SAVED_SHA = '778c014ccea8b0f376d06afeeeceb318e50b3bce926ef13a6da068c9b3d5d917'
EPOCH, DEADLINE = 1791871874, 1791915074
CAP = 32 * 1024**2
STATE_NAMES = ('dataset-code-v18-receipt.json', 'dataset-code-v18-journal.json', 'dataset-code-v18.claim.json',
    'notebook-rlvr004-receipt.json', 'notebook-rlvr004-journal.json', 'notebook-rlvr004.claim.json',
    'notebook-rlvr004-wire.json', 'notebook-rlvr004-saved.ipynb', 'finalization.json',
    'active-finalized.ipynb', 'original-request.json', 'operator.json', 'parent-private-scorer.json')
BASE_NAMES = ('publication-manifest.json', 'notebook-release.json', 'assembly/finalize.py',
              'code-payload/deployment/notebook_builder.py', 'code-payload/deployment/source_loader.py')
FALSE_FLAGS = ('runtime_or_model_closure_verified', 'physical_costs_known', 'manual_failure_root_cause_verified', 'scientific_result_verified')


def need(ok, message):
    if not ok:
        raise ValueError('v35 lineage: ' + message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n').encode()


def desc(raw):
    return {'bytes': len(raw), 'sha256': sha(raw)}


def relative(name):
    need(type(name) is str and name and all(ord(c) >= 32 and ord(c) != 127 for c in name) and '\\' not in name and ':' not in name, 'relative path')
    path = PurePosixPath(name)
    need(path.parts and str(path) == name and not path.is_absolute() and all(x not in ('.', '..') for x in path.parts), 'relative path')
    return name


def read(path, cap=CAP):
    path = Path(os.path.abspath(path))
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'no linked input')
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap, 'bounded ordinary input')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        need((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), 'replaced input')
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    key = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns, x.st_nlink)
    need(key(before) == key(after) == key(path.lstat()) and len(raw) == before.st_size, 'changed input')
    return raw


def obj(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def number(token):
        value = float(token)
        need(math.isfinite(value), 'finite JSON')
        return value
    result = json.loads(raw, object_pairs_hook=pairs, parse_float=number,
                        parse_constant=lambda _: need(False, 'finite JSON'))
    need(type(result) is dict, 'JSON object')
    return result


def normalized(raw):
    document = obj(raw)
    for cell in document['cells']:
        if isinstance(cell.get('source'), list):
            cell['source'] = ''.join(cell['source'])
    return document


def clock():
    return {'dispatch_epoch': EPOCH, 'predispatch_epoch': EPOCH, 'deadline_epoch': DEADLINE,
            'global_deadline_epoch': DEADLINE, 'execution_deadline_epoch': EPOCH + 42000,
            'outer_deadline_epoch': EPOCH + 42180, 'provider_timeout_seconds': 42300}


def check_rows(rows):
    need(type(rows) is dict and 0 < len(rows) <= 12000, 'closed inventory required')
    for name, row in rows.items():
        relative(name)
        need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int
             and 0 <= row['bytes'] <= CAP and type(row['sha256']) is str and len(row['sha256']) == 64
             and all(c in '0123456789abcdef' for c in row['sha256']), 'descriptor')


def _check(raw, replay_root, state_inventory_sha):
    """Verify original selected bytes; frozen finalizer replay is pure."""
    inventory_raw = raw['ORIGINAL-STATE-INVENTORY.json']
    need(sha(inventory_raw) == state_inventory_sha, 'independently pinned original owner state inventory')
    state_inventory = obj(inventory_raw)
    check_rows(state_inventory)
    for name in STATE_NAMES:
        need(state_inventory.get(name) == desc(raw['state/' + name]), 'original selected state body: ' + name)
    frozen_inventory_raw = raw['frozen-code18/ASSEMBLY-INVENTORY.json']
    need(sha(frozen_inventory_raw) == ASSEMBLY_SHA, 'original code18 inventory')
    frozen_inventory = obj(frozen_inventory_raw)
    for name in BASE_NAMES:
        need(frozen_inventory.get(name) == desc(raw['frozen-code18/' + name]), 'original replay input: ' + name)
    need(sha(raw['frozen-code18/publication-manifest.json']) == MANIFEST_SHA, 'original code18 manifest')
    manifest = obj(raw['frozen-code18/publication-manifest.json'])
    active = next(row for row in manifest['notebooks'] if row['role'] == 'rlvr004')
    s = {name: raw['state/' + name] for name in STATE_NAMES}
    code, code_journal, code_claim = (obj(s[n]) for n in STATE_NAMES[:3])
    launch, journal, claim = (obj(s[n]) for n in STATE_NAMES[3:6])
    wire, final = obj(s['notebook-rlvr004-wire.json']), obj(s['finalization.json'])
    need(code['dataset_id'] == 12504696 and code['version'] == 18 and code['is_private'] is True
         and code['exact_byte_roundtrip'] is True and code['manifest_sha256'] == code['publication_manifest_sha256'] == MANIFEST_SHA,
         'original code18 exact receipt')
    need(code['journal_sha256'] == sha(s['dataset-code-v18-journal.json']) and code['claim_sha256'] == code_journal['claim_sha256'] == sha(s['dataset-code-v18.claim.json']), 'code receipt/journal/claim chain')
    need(code_journal['manifest_sha256'] == code_claim['manifest_sha256'] == MANIFEST_SHA
         and code_journal['expected_version'] == code_claim['expected_version'] == 18
         and code_journal['expected_predecessor_version'] == code_claim['expected_predecessor_version'] == 17,
         'original code write identity')
    need(all(code_journal[k] == 1 and type(code_journal[k]) is int and code_claim[k] == 0 and type(code_claim[k]) is int
             for k in ('init_calls', 'put_calls', 'version_calls')), 'original single dataset write')
    need(code_journal['payload_sha256'] == code_claim['payload_sha256'] == manifest['datasets'][0]['transport_archive']['sha256'], 'original upload payload')
    layouts = manifest['datasets'][0]['expected_readback_layouts']
    need(code['layout'] in layouts, 'original known readback layout')
    actual = {r['path']: {k: r[k] for k in ('bytes', 'sha256')} for r in layouts[code['layout']]}
    need(code['inventory_sha256'] == sha(canonical(actual)) and code['files'] == len(actual)
         and code['bytes'] == sum(row['bytes'] for row in actual.values()) and code['before'] == code['after'], 'original code inventory/metadata bracket')
    for record in (launch, journal, claim):
        need(record['manifest_sha256'] == MANIFEST_SHA and record['kernel_id'] == 138123872
             and record['reference'] == 'danielwuu/iris-x-learning-agent-20261011' and record['role'] == 'rlvr004', 'original notebook owner identity')
    need(launch['version'] == journal['expected_version'] == journal['response_version'] == claim['expected_version'] == 35
         and journal['save_calls'] == 1 and type(journal['save_calls']) is int and journal['save_accepted'] is True
         and claim['save_calls'] == 0 and type(claim['save_calls']) is int, 'original single notebook dispatch')
    need(launch['launch_journal_sha256'] == sha(s['notebook-rlvr004-journal.json'])
         and journal['claim_sha256'] == sha(s['notebook-rlvr004.claim.json'])
         and launch['finalization_sha256'] == journal['finalization_sha256'] == sha(s['finalization.json'])
         and journal['wire_sha256'] == sha(s['notebook-rlvr004-wire.json']), 'original notebook receipt/JIT/wire/claim chain')
    need(journal['code_receipt_sha256'] == sha(s['dataset-code-v18-receipt.json']), 'launch uses exact original code receipt')
    need(final['manifest_sha256'] == MANIFEST_SHA and final['template_sha256'] == active['sha256']
         and final['finalizer_sha256'] == manifest['jit']['entry']['sha256'], 'original JIT template/finalizer')
    expected_clock = clock()
    need(all(final.get(k) == v and type(final.get(k)) is int for k, v in expected_clock.items()), 'original unreset finalization clock')
    need(all(journal.get(k) == v and type(journal.get(k)) is int for k, v in expected_clock.items() if k != 'dispatch_epoch'), 'original journal clock')
    dispatched = journal['dispatch_epoch']
    need(type(dispatched) in (int, float) and math.isfinite(dispatched) and 0 <= dispatched - EPOCH <= 60, 'original dispatch age')
    helper_raw = raw['frozen-code18/assembly/finalize.py']
    helper = types.ModuleType('pure_original_code18_finalizer_replay')
    helper.__file__, helper.__package__ = str(Path(replay_root) / 'assembly/finalize.py'), ''
    exec(compile(helper_raw, helper.__file__, 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(helper))
    documents = helper.finalize(Path(replay_root), EPOCH)
    need(set(documents) == {'active-finalized.ipynb', 'original-request.json', 'operator.json', 'parent-private-scorer.json'}
         and set(final['documents']) == set(documents), 'original closed four JIT documents')
    for name, body in documents.items():
        need(s[name] == body and {k: final['documents'][name][k] for k in ('bytes', 'sha256')} == desc(body), 'original exact JIT reconstruction: ' + name)
        need(PurePosixPath(final['documents'][name]['path']).name == name, 'original JIT role/path association')
    submitted, saved = s['active-finalized.ipynb'], s['notebook-rlvr004-saved.ipynb']
    need(sha(saved) == SAVED_SHA and len(saved) == 21096 and launch['normalized_source_exact'] is True
         and {k: launch['saved_source'][k] for k in ('bytes', 'sha256')} == desc(saved), 'original saved v35 binding')
    need(sha(submitted) == final['finalized_sha256'] == journal['source_sha256'] == launch['submitted_source_sha256']
         and normalized(submitted) == normalized(saved), 'only documented source-list normalization')
    expected_wire = {'id': 138123872, 'slug': 'danielwuu/iris-x-learning-agent-20261011', 'new_title': active['title'],
        'text': submitted.decode(), 'language': 'python', 'kernel_type': 'notebook', 'dataset_data_sources': active['dataset_sources'],
        'model_data_sources': active['model_sources'], 'competition_data_sources': active['competition_sources'],
        'kernel_data_sources': [], 'is_private': True, 'enable_gpu': True, 'enable_tpu': False, 'enable_internet': False,
        'docker_image': active['docker_image'], 'kernel_execution_type': active['save_version_value'],
        'session_timeout_seconds': active['session_timeout_seconds'], 'machine_shape': active['machine_shape']}
    need(wire == expected_wire, 'exact original dataset/model/hardware/offline wire')
    return {'v35_original_dispatch_chain_verified': True, 'original_epoch': EPOCH, 'original_deadline': DEADLINE,
            'saved_source_sha256': SAVED_SHA, 'submitted_source_sha256': sha(submitted),
            **{k: False for k in FALSE_FLAGS}, 'provider_calls': 0, 'model_or_GPU_calls': 0}


def build(base_root, state_root, state_inventory_path, state_inventory_sha):
    """Return a sealed supplement only after authentic original input checking."""
    base_root, state_root = Path(base_root), Path(state_root)
    inventory_raw = read(state_inventory_path)
    need(sha(inventory_raw) == state_inventory_sha, 'original state inventory hash before parsing')
    rows = obj(inventory_raw)
    check_rows(rows)
    need(set(STATE_NAMES) <= set(rows), 'all13 original selected state files required')
    raw = {'ORIGINAL-STATE-INVENTORY.json': inventory_raw,
           'frozen-code18/ASSEMBLY-INVENTORY.json': read(base_root / 'ASSEMBLY-INVENTORY.json')}
    raw.update({'frozen-code18/' + name: read(base_root / name) for name in BASE_NAMES})
    for name in STATE_NAMES:
        body = read(state_root / name)
        need(rows[name] == desc(body), 'authentic state body before parsing: ' + name)
        raw['state/' + name] = body
    checked = _check(raw, base_root, state_inventory_sha)
    proof = {'format': FORMAT, 'status': 'ORIGINAL_DISPATCH_LINEAGE_VERIFIED_NO_RUNTIME_CLOSURE',
        'state_inventory_sha256': state_inventory_sha, 'code18_assembly_inventory_sha256': ASSEMBLY_SHA,
        'code18_publication_manifest_sha256': MANIFEST_SHA,
        'notebook_version': 35, 'code_version': 18, 'closed_files': {n: desc(b) for n, b in sorted(raw.items())}, **checked}
    raw['LAUNCH-LINEAGE.json'] = encoded(proof)
    return raw


def verify(bundle_root, expected_manifest_sha256):
    root = Path(bundle_root)
    manifest_raw = read(root / 'LAUNCH-LINEAGE.json')
    need(sha(manifest_raw) == expected_manifest_sha256, 'independently pinned launch supplement')
    proof = obj(manifest_raw)
    need(proof['format'] == FORMAT and proof['status'] == 'ORIGINAL_DISPATCH_LINEAGE_VERIFIED_NO_RUNTIME_CLOSURE'
         and proof['notebook_version'] == 35 and proof['code_version'] == 18
         and proof['code18_assembly_inventory_sha256'] == ASSEMBLY_SHA and proof['code18_publication_manifest_sha256'] == MANIFEST_SHA, 'supplement exact identity')
    rows = proof['closed_files']
    check_rows(rows)
    expected_names = {'ORIGINAL-STATE-INVENTORY.json', 'frozen-code18/ASSEMBLY-INVENTORY.json'} | {'frozen-code18/' + n for n in BASE_NAMES} | {'state/' + n for n in STATE_NAMES}
    need(set(rows) == expected_names, 'closed original supplement roles')
    actual = set()
    for path in root.rglob('*'):
        need(not path.is_symlink(), 'supplement symlink')
        info = path.lstat()
        need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'supplement special entry')
        if stat.S_ISREG(info.st_mode):
            actual.add(path.relative_to(root).as_posix())
    need(actual == expected_names | {'LAUNCH-LINEAGE.json'}, 'unknown or missing supplement body')
    raw = {name: read(root / relative(name)) for name in rows}
    need(all(desc(raw[n]) == row for n, row in rows.items()), 'supplement body integrity')
    checked = _check(raw, root / 'frozen-code18', proof['state_inventory_sha256'])
    need(all(proof.get(k) == v and type(proof.get(k)) is type(v) for k, v in checked.items()), 'supplement cannot promote closure or alter original identity')
    return proof
