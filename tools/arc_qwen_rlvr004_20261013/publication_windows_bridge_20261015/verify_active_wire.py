"""Independent finite portable run008 actual-wire check. No provider, model or epoch allocation.

The reviewer freezes static pins only after source and actual numeric/inactive
readbacks have passed. This entry emits a receipt only for the real subsequently
prepared JIT bytes. It never creates a claim, edits a candidate or sends a RUN.
"""
# Frozen baseline: cc14bd1, review_run008/verify_active_wire.py.
# Original SHA-256: 955f6adec5f9608d96754e18ecc9958d1b9edd0998e226621dba18f14af75e00.
# This successor binds an independently reviewed exact version allocation;
# frozen publication_run008 and review_run008 bytes remain unchanged.
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
import types

FORMAT = 'irisx/run008-windows-bridge-active-review-static-pins-v1'
CONFIG_FORMAT = 'irisx/run008-windows-bridge-operator-config-v1'
SOURCE = '38698fd0861b2940bd303b59899011da0fb53d2daa4da846de80521bfc2c828b'
ARCHIVE = 'ffaea7e6dd0fd3df1b6bc0566b27278f47f318b2d680d96e358a1cc5b8584dff'
REF = 'danielwuu/iris-x-learning-agent-20261011'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
VERSION_FIELDS = {'code_predecessor', 'code', 'inactive_predecessor', 'inactive', 'active'}
NON_CODE_PINS = [
    'danielwuu/iris-x-public120-data-20261010/1',
    'danielwuu/iris-x-learning-training-20261011/1',
    'danielwuu/iris-arc-next-runtime/8',
    'danielwuu/iris-arc-granite42-8b-offline/2',
    'danielwuu/iris-arc-next-cu128-cp312-wheels/1',
    'danielwuu/iris-arc-next-cpython312-offline/2',
    'danielwuu/iris-arc-granite42-run003-adapter-20261009/1',
]
RUN = '/kaggle/working/irisx-qwen14b-rlvr-20261013-run008'
SOURCE_ROOT = '/kaggle/working/irisx-qwen14b-rlvr-20261013-source008'
DOCS = {'active-finalized.ipynb', 'original-request.json', 'operator.json', 'parent-private-scorer.json'}


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def path(value):
    result = Path(value)
    need(result.is_absolute() and '..' not in result.parts and str(result) == str(value), 'canonical absolute path required')
    need(not any(p.is_symlink() for p in (result, *result.parents)), 'linked review path')
    return result


def read(value, expected=None, cap=4 * 1024**2):
    p = path(value)
    before = p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 <= before.st_size <= cap, 'bounded ordinary review file')
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    identity = lambda x: (x.st_dev, x.st_ino, x.st_mode, x.st_nlink, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
    need(identity(before) == identity(opened) == identity(after) == identity(p.lstat()), 'review file changed during read')
    need(len(raw) <= cap and (expected is None or sha(raw) == expected), 'review file hash or size differs')
    return raw


def obj(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'duplicate review JSON key')
            result[k] = v
        return result
    def number(value):
        result = float(value)
        need(math.isfinite(result), 'nonfinite review JSON')
        return result
    value = json.loads(raw, object_pairs_hook=pairs, parse_float=number,
                       parse_constant=lambda _: need(False, 'nonfinite review JSON'))
    need(type(value) is dict, 'review object required')
    return value


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def config(notebook):
    found = {}
    for cell in obj(notebook)['cells']:
        if cell.get('cell_type') != 'code':
            continue
        source = cell['source']
        need(type(source) in (str, list), 'notebook source type')
        for node in ast.parse(''.join(source)).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    value = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                name = node.targets[0].id
                need(name not in found, 'duplicate notebook configuration')
                found[name] = value
    return found


def versions(value):
    """An exact reviewed allocation, never a free numeric-version override."""
    need(type(value) is dict and set(value) == VERSION_FIELDS, 'exact reviewed version schema')
    need(all(type(number) is int and number > 0 for number in value.values()), 'strict positive integer versions')
    need(value['code'] == value['code_predecessor'] + 1
         and value['inactive'] == value['inactive_predecessor'] + 1
         and value['active'] == value['inactive'] + 1, 'exact reviewed successor versions')
    return value


def exact_int(value, expected):
    return type(value) is int and value == expected


def manifest_versions(manifest, allocation):
    datasets = manifest['datasets']
    need(type(datasets) is list and len(datasets) == 1, 'one exact code dataset role')
    dataset = datasets[0]
    need(exact_int(dataset['id'], 12504696) and dataset['reference'] == DREF
         and dataset['is_private'] is True, 'exact code dataset identity')
    need(exact_int(dataset['expected_predecessor_version'], allocation['code_predecessor'])
         and exact_int(dataset['expected_version'], allocation['code']), 'reviewed manifest code versions')
    notebooks = manifest['notebooks']
    need(type(notebooks) is list and len(notebooks) == 2, 'two exact notebook roles')
    rows = {row['role']: row for row in notebooks}
    need(set(rows) == {'inactive', 'rlvr004'}, 'exact distinct notebook roles')
    for role, predecessor, successor in (('inactive', 'inactive_predecessor', 'inactive'),
                                         ('rlvr004', 'inactive', 'active')):
        row = rows[role]
        need(exact_int(row['existing_notebook_id'], 138123872)
             and row['existing_notebook_reference'] == REF, 'exact notebook identity')
        need(exact_int(row['expected_predecessor_version'], allocation[predecessor])
             and exact_int(row['expected_version'], allocation[successor]), 'reviewed manifest notebook versions')
        need(row['dataset_sources'] == [DREF + '/' + str(allocation['code']), *NON_CODE_PINS],
             'exact reviewed numeric dataset pins')
    return rows


def verify(pins_path, pins_sha):
    pins = obj(read(pins_path, pins_sha))
    need(pins.get('format') == FORMAT and pins.get('status') == 'SOURCE_AND_PRELAUNCH_READBACKS_REVIEWED'
         and pins.get('synthetic_test_only') is False, 'actual independently reviewed static pins required')
    need(sha(read(str(Path(__file__).absolute()))) == pins['verifier_sha256'], 'independent verifier bytes changed')
    allocation = versions(pins['versions'])
    root, state = path(pins['candidate_root']), path(pins['state_root'])
    manifest_raw = read(str(root / 'publication-manifest.json'), pins['publication_manifest_sha256'])
    manifest = obj(manifest_raw)
    need(manifest['format'] == 'irisx/qwen14b-rlvr-run008-publication-contract-v1'
         and manifest['run_authorized'] is True and manifest['runtime_source_sha256'] == SOURCE,
         'reviewed run008 publication manifest')
    need(manifest['consumer_contract']['source_archive']['sha256'] == ARCHIVE, 'original reviewed archive identity')
    rows = manifest_versions(manifest, allocation)
    for name, descriptor in pins['prelaunch_files'].items():
        need(type(name) is str and type(descriptor) is dict and set(descriptor) == {'path', 'sha256', 'bytes'}, 'prelaunch descriptor')
        raw = read(descriptor['path'], descriptor['sha256'], cap=16 * 1024**2)
        need(len(raw) == descriptor['bytes'], 'prelaunch descriptor size')
    cfg = obj(read(pins['prelaunch_files']['local_config']['path'], pins['local_config_sha256']))
    need(cfg.get('format') == CONFIG_FORMAT, 'reviewed portable local config format')
    need(versions(cfg['versions']) == allocation, 'independently reviewed local version allocation')
    need(cfg['candidate_root'] == str(root) and cfg['state_root'] == str(state)
         and cfg['publication_manifest_sha256'] == pins['publication_manifest_sha256'], 'exact local state binding')
    code = obj(read(str(state / ('dataset-code-v' + str(allocation['code']) + '-receipt.json')), pins['code_receipt_sha256']))
    inactive = obj(read(str(state / 'notebook-inactive-receipt.json'), pins['inactive_receipt_sha256']))
    need(exact_int(code['dataset_id'], 12504696) and exact_int(code['version'], allocation['code'])
         and code['is_private'] is True and code['exact_byte_roundtrip'] is True, 'actual numeric code readback')
    need(exact_int(inactive['kernel_id'], 138123872) and exact_int(inactive['version'], allocation['inactive'])
         and inactive['reference'] == REF and inactive['role'] == 'inactive'
         and inactive['status'] == 'COMPLETE' and inactive['normalized_source_exact'] is True,
         'actual inactive readback')
    need(code['manifest_sha256'] == inactive['manifest_sha256'] == pins['publication_manifest_sha256'], 'prelaunch manifest chain')
    for snapshot in (code['before'], code['after']):
        need(exact_int(snapshot['id'], 12504696) and snapshot['ref'] == DREF
             and exact_int(snapshot['version'], allocation['code']) and snapshot['private'] is True,
             'actual code readback bracket identity')
    code_stem = 'dataset-code-v' + str(allocation['code'])
    code_journal = obj(read(str(state / (code_stem + '-journal.json')), code['journal_sha256']))
    code_claim_raw = read(str(state / (code_stem + '.claim.json')), code['claim_sha256'])
    code_claim = obj(code_claim_raw)
    need(code_journal['claim_sha256'] == sha(code_claim_raw), 'actual code claim chain')
    for document in (code_claim, code_journal):
        need(exact_int(document['expected_predecessor_version'], allocation['code_predecessor'])
             and exact_int(document['expected_version'], allocation['code'])
             and document['manifest_sha256'] == pins['publication_manifest_sha256'],
             'actual code claim and journal allocation')
    # Official notebook metadata returns owner/slug identities, not numeric pins.
    # Numeric versions remain exact in the reviewed manifest and outgoing wire.
    returned_sources = inactive['dataset_sources_returned']
    need(type(returned_sources) is list and all(type(value) is str for value in returned_sources),
         'actual inactive dataset identity list')
    need(exact_int(inactive['predecessor']['version'], allocation['inactive_predecessor'])
         and exact_int(inactive['snapshot']['version'], allocation['inactive'])
         and inactive['snapshot']['status'] == 'COMPLETE'
         and sorted(returned_sources) == sorted('/'.join(value.split('/')[:2])
                                               for value in rows['inactive']['dataset_sources']),
         'actual inactive predecessor snapshot and pins')
    final_raw = read(str(state / 'finalization.json'))
    final = obj(final_raw)
    epoch = final['predispatch_epoch']
    need(type(epoch) is int and epoch > 0 and 0 <= time.time() - epoch <= 60, 'fresh immutable predispatch epoch')
    clocks = {'dispatch_epoch': epoch, 'predispatch_epoch': epoch, 'deadline_epoch': epoch + 43200,
              'global_deadline_epoch': epoch + 43200, 'execution_deadline_epoch': epoch + 42000,
              'outer_deadline_epoch': epoch + 42180, 'provider_timeout_seconds': 42300}
    need(all(type(final.get(k)) is int and final[k] == v for k, v in clocks.items()), 'unchanged absolute original clock')
    need(final['format'] == 'irisx/rlvr-finalization-v1' and final['manifest_sha256'] == pins['publication_manifest_sha256']
         and set(final['documents']) == DOCS, 'closed actual JIT document set')
    jit = manifest['jit']
    need(jit['maximum_dispatch_age_seconds'] == 60 and set(jit['output_documents']) == DOCS, 'reviewed finite JIT contract')
    for descriptor in [jit['entry'], *jit['dependencies']]:
        rel = Path(descriptor['path'])
        need(not rel.is_absolute() and '..' not in rel.parts, 'relative pinned finalizer dependency')
        raw = read(str(root / rel), descriptor['sha256'])
        need(len(raw) == descriptor['bytes'], 'finalizer dependency size')
    entry = root / jit['entry']['path']
    module = types.ModuleType('independent_exact_finalizer')
    module.__file__, module.__package__ = str(entry), ''
    exec(compile(read(str(entry), jit['entry']['sha256']), str(entry), 'exec', dont_inherit=True), vars(module))
    expected = module.finalize(root, epoch)
    need(set(expected) == DOCS, 'independent reconstructed JIT set')
    actual = {}
    for name in sorted(DOCS):
        descriptor = final['documents'][name]
        need(descriptor['path'] == str(state / name), 'exact original JIT path')
        raw = read(str(state / name), descriptor['sha256'])
        need(len(raw) == descriptor['bytes'] and raw == expected[name], 'actual JIT differs from reviewed reconstruction')
        actual[name] = raw
    n = rows['rlvr004']
    need(exact_int(n['expected_predecessor_version'], allocation['inactive'])
         and exact_int(n['expected_version'], allocation['active']) and n['run_authorized'] is True,
         'one exact numeric active successor')
    need(final['template_sha256'] == n['sha256'] and final['finalized_sha256'] == sha(actual['active-finalized.ipynb'])
         and final['finalizer_sha256'] == jit['entry']['sha256'], 'JIT finalizer/template/source chain')
    expected_config = {'MANUAL_START': True, 'ENABLE_MODEL': True, 'PREDISPATCH_EPOCH': epoch, 'NOTEBOOK_KIND': 'active-finalized',
        'SESSION_SECONDS': 43200, 'PROBE_SECONDS': 43200, 'EXECUTION_CUTOFF_SECONDS': 42000,
        'OUTER_CUTOFF_SECONDS': 42180, 'PROVIDER_RUNTIME_SECONDS': 42300, 'OUTPUT_ROOT': RUN,
        'SOURCE_PARENT': SOURCE_ROOT, 'PROFILE': 'QWEN14B_RLVR12H'}
    notebook_config = config(actual['active-finalized.ipynb'])
    need(all(type(notebook_config.get(k)) is type(v) and notebook_config[k] == v for k, v in expected_config.items()),
         'active notebook exact configuration')
    expected_wire = {'id': 138123872, 'slug': REF, 'new_title': 'IRIS-X Learning Agent 20261011',
        'text': actual['active-finalized.ipynb'].decode(), 'language': 'python', 'kernel_type': 'notebook',
        'dataset_data_sources': n['dataset_sources'], 'model_data_sources': ['qwen-lm/qwen-3/transformers/14b/1'],
        'competition_data_sources': ['arc-prize-2026-arc-agi-3'], 'kernel_data_sources': [], 'is_private': True,
        'enable_gpu': True, 'enable_tpu': False, 'enable_internet': False, 'docker_image': n['docker_image'],
        'kernel_execution_type': 1, 'session_timeout_seconds': 42300, 'machine_shape': 'NvidiaRtxPro6000'}
    wire_raw = read(str(state / 'notebook-rlvr004-wire.json'))
    need(obj(wire_raw) == expected_wire
         and wire_raw == (json.dumps(expected_wire, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode(),
         'actual exact active wire settings and serialized bytes')
    journal_raw = read(str(state / 'notebook-rlvr004-journal.json'))
    journal = obj(journal_raw)
    claim_raw = read(str(state / 'notebook-rlvr004.claim.json'), journal['claim_sha256'])
    claim = obj(claim_raw)
    need(journal['stage'] == 'wire_prepared' and type(journal['save_calls']) is int and journal['save_calls'] == 0
         and claim['stage'] == 'claimed' and exact_int(claim['save_calls'], 0), 'unsent one-attempt claim')
    for document in (claim, journal):
        need(exact_int(document['expected_version'], allocation['active'])
             and exact_int(document['kernel_id'], 138123872) and document['reference'] == REF
             and document['role'] == 'rlvr004'
             and document['manifest_sha256'] == pins['publication_manifest_sha256'], 'original claim target')
        need(exact_int(document['predecessor']['version'], allocation['inactive'])
             and document['predecessor']['status'] == 'COMPLETE', 'original claim exact inactive predecessor')
        need(document['material_approval_sha256'] == pins['material_approval_sha256']
             and document['transport_review_sha256'] == pins['transport_review_sha256']
             and document['monitor_review_sha256'] == pins['monitor_review_sha256']
             and document['mount_receipt_sha256'] == pins['mount_receipt_sha256']
             and document['persisted_audit_sha256'] == pins['persisted_audit_sha256']
             and document['code_receipt_sha256'] == pins['code_receipt_sha256']
             and document['inactive_receipt_sha256'] == pins['inactive_receipt_sha256'], 'claim exact prelaunch receipts')
        need(document['stop_after_submit_readback'] is False and document['provider_monitoring_authorized'] is True,
             'current monitoring scope')
    need(all(type(journal.get(k)) is int and journal[k] == v for k, v in clocks.items()), 'prepared original clock cannot reset')
    need(journal['source_sha256'] == sha(actual['active-finalized.ipynb']) and journal['wire_sha256'] == sha(wire_raw)
         and journal['finalization_sha256'] == sha(final_raw), 'prepared exact byte chain')
    need(0 <= time.time() - epoch <= 60, 'dispatch epoch expired during review')
    return {'format': 'irisx/run008-active-wire-review-v1', 'status': 'PASS', 'synthetic_test_only': False,
        **{key: pins[key] for key in ('publication_manifest_sha256', 'material_approval_sha256', 'transport_review_sha256', 'local_config_sha256')},
        'wire_sha256': sha(wire_raw), 'finalization_sha256': sha(final_raw), 'finalized_source_sha256': sha(actual['active-finalized.ipynb']),
        'prepared_journal_sha256': sha(journal_raw), 'predispatch_epoch': epoch, 'numeric_notebook_version': allocation['active'],
        'versions': dict(allocation),
        'static_review_pins_sha256': pins_sha, 'verifier_sha256': pins['verifier_sha256'],
        'exact_four_document_reconstruction': True, 'provider_calls': 0, 'model_or_GPU_calls': 0,
        'production_GPU_validation_passed': False, 'scientific_result': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pins', 'pins-sha', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = verify(args.pins, args.pins_sha)
    destination = path(args.output)
    raw = encoded(result)
    with os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    need(read(str(destination)) == raw, 'receipt write roundtrip')
    print(json.dumps({'status': 'ACTUAL_ACTIVE_WIRE_VERIFIED', 'sha256': sha(raw),
                      'predispatch_epoch': result['predispatch_epoch'], 'numeric_notebook_version': result['numeric_notebook_version']}))


if __name__ == '__main__':
    main()
