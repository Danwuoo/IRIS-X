"""Capture the fixed accepted code23/v45 predecessor before numeric assembly.

This reviewed read-only caller uses the existing operator API and its native
guards. It does not admit the numeric publication contract or allocate a run.
Its private review binds exact local inputs, this caller, and a fresh output.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

COLLECTOR_SHA256 = 'df7f54f9f09709a423f68b01c40b3b8b79aae16e8c98639ecf03e76b864ede54'
MANIFEST_SHA256 = '15f340149a8eff74e6c1d56f3cd34b8836d349dfa6818ef14bd142dcb600161a'
MANIFEST_BYTES = 135137
SAVED_SOURCE_SHA256 = '5f884856484087033f6569335f5c65f752c4868c823276efaffed3c3e96eaeff'
SAVED_SOURCE_BYTES = 22913
VERSIONS = {'code_predecessor': 22, 'code': 23, 'inactive_predecessor': 43,
            'inactive': 44, 'active': 45}
PURPOSE = 'fixed-code23-v45-predecessor-capture-v1'
OPERATOR = Path(__file__).absolute().parents[2] / 'publication_windows_bridge_20261015'
CAP = 4 * 1024**2


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate_json_key')
            result[key] = value
        return result
    def invalid(unused):
        raise ValueError('nonfinite_json')
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    need(type(result) is dict, 'json_object_required')
    return result


def ordinary(path):
    need(type(path) in (str, type(Path())) or isinstance(path, Path), 'path_type')
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts,
         'absolute_ordinary_path_required')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'linked_path')
    return path


def read_pinned(path, digest, size=None):
    path = ordinary(path)
    before = path.lstat()
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= CAP,
         'bounded_single_link_file')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        need(identity(os.fstat(stream.fileno())) == identity(before), 'source_identity_changed')
        raw = stream.read(CAP + 1)
        need(identity(os.fstat(stream.fileno())) == identity(before)
             == identity(path.lstat()), 'source_identity_changed')
    need(len(raw) == before.st_size and sha(raw) == digest
         and (size is None or type(size) is int and len(raw) == size), 'source_hash_changed')
    return raw


def descriptor_input(row):
    need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'input_descriptor')
    need(type(row['bytes']) is int and 0 < row['bytes'] <= CAP, 'input_bytes')
    return read_pinned(row['path'], row['sha256'], row['bytes'])


def load_collector():
    path = OPERATOR / 'rl_collect.py'
    raw = read_pinned(path, COLLECTOR_SHA256)
    module = types.ModuleType('reviewed_fixed_v45_capture_collector')
    module.__file__, module.__package__ = str(path), ''
    exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


def prepare(review_path, review_sha):
    review_path = ordinary(review_path)
    review_raw = read_pinned(review_path, review_sha)
    review = strict(review_raw)
    need(review.get('status') == 'PASS' and review.get('synthetic_test_only') is False
         and review.get('provider_execution_admitted') is True
         and review.get('allowed_actions') == ['reconcile-read-only'], 'readonly_review_required')
    observer = review.get('observer')
    need(type(observer) is dict and set(observer) == {
        'purpose', 'script', 'output_root', 'manifest', 'material', 'local_config'}, 'observer_review_schema')
    need(observer['purpose'] == PURPOSE, 'fixed_capture_purpose')
    need(ordinary(observer['script']['path']) == Path(__file__).absolute(), 'reviewed_caller_path')
    descriptor_input(observer['script'])
    documents = {name: descriptor_input(observer[name]) for name in ('manifest', 'material', 'local_config')}
    need(len(documents['manifest']) == MANIFEST_BYTES and sha(documents['manifest']) == MANIFEST_SHA256,
         'fixed_accepted_v45_manifest')
    manifest, material = strict(documents['manifest']), strict(documents['material'])
    need(material.get('status') == 'APPROVED'
         and material.get('scope', {}).get('publication_manifest', {}).get('sha256') == MANIFEST_SHA256,
         'accepted_material_manifest_binding')
    approved = {(row['role'], row['sha256']) for row in material['approved_notebooks']}
    need(all((row['role'], row['sha256']) in approved for row in manifest['notebooks']),
         'accepted_approved_notebooks')
    output = ordinary(observer['output_root'])
    need(not output.exists(), 'fresh_output_required')
    args = types.SimpleNamespace(action='reconcile-read-only', review=str(review_path), review_sha=review_sha)
    for name in ('manifest', 'material', 'local_config'):
        setattr(args, name, observer[name]['path'])
        setattr(args, name + '_sha', observer[name]['sha256'])
    # The unchanged bootstrap authenticates collector -> transport -> common.
    # configure_local is the public API binding, not numeric load_contract.
    collector = load_collector()
    transport = collector.bootstrap(args)
    transport.configure_local(args)
    need(dict(transport.CONFIG.versions) == VERSIONS
         and all(type(value) is int for value in transport.CONFIG.versions.values()), 'fixed_accepted_versions')
    transport.review_gate(args.review, args.review_sha, args.manifest_sha, args.material_sha,
                         [transport.SCRIPT, transport.SCRIPT.with_name('operator_common.py')])
    transport.execution_gate(args, monitor=False)
    common = transport._common
    common.bind_action_review(args.review, args.review_sha)
    common.publication_guard()
    scratch = common.configured().scratch_root
    need(output.is_relative_to(scratch) and output != scratch, 'output_in_reviewed_scratch')
    for retained in (common.STATE, common.configured().candidate_root):
        need(not output.is_relative_to(retained) and not retained.is_relative_to(output),
             'output_overlaps_retained_inputs')
    need(read_pinned(review_path, review_sha) == review_raw, 'review_changed')
    for name, raw in documents.items():
        need(descriptor_input(observer[name]) == raw, 'input_changed')
    descriptor_input(observer['script'])
    return transport, common, manifest, output


def capture(transport, common, manifest, output):
    """Five synchronous reads; only clean native closure permits OBSERVATION."""
    output = ordinary(output)
    need(not output.exists(), 'fresh_output_required')
    output.mkdir(mode=0o700)
    def put(name, value):
        raw = value if type(value) is bytes else encoded(value)
        need(0 < len(raw) <= CAP, 'bounded_raw_observation')
        common.write_new(output / name, raw)
        return sha(raw)
    with common.lock('reconcile-read-only'):
        common.publisher_lock_owner()
        common.no_gpu_stop()
        provider = None
        try:
            provider = common.Provider()
            dataset = provider.dataset()
            before = provider.kernel()
            status = provider.status()
            after = provider.kernel()
            dataset_after = provider.dataset()
            for value in (dataset, dataset_after):
                need(type(value.id) is int and type(value.current_version_number) is int,
                     'dataset_integer_identity')
            need(dataset.id == dataset_after.id == 12504696
                 and dataset.ref == dataset_after.ref == transport.DREF
                 and dataset.owner_ref == dataset_after.owner_ref == 'danielwuu'
                 and dataset.is_private is True and dataset_after.is_private is True
                 and dataset.current_version_number == dataset_after.current_version_number == 23,
                 'fixed_code23_dataset_bracket')
            for metadata in (before.metadata, after.metadata):
                need(type(metadata.id) is int and type(metadata.current_version_number) is int
                     and metadata.is_private is True and metadata.enable_gpu is True
                     and metadata.enable_tpu is False and metadata.enable_internet is False,
                     'fixed_notebook_identity_types')
            need(before.metadata.current_version_number == after.metadata.current_version_number == 45,
                 'fixed_v45_notebook_bracket')
            raw = before.blob.source.encode('utf-8')
            need(raw == after.blob.source.encode('utf-8') and len(raw) == SAVED_SOURCE_BYTES
                 and sha(raw) == SAVED_SOURCE_SHA256, 'fixed_v45_source_bracket')
            for metadata in (before.metadata, after.metadata):
                transport.settings(metadata, transport.row(manifest, 'rlvr004'))
            need(before.metadata.to_dict() == after.metadata.to_dict(), 'full_metadata_bracket_changed')
            classification, message = common.classify(None, status.failure_message)
            need(classification != 'ACCESS_BLOCKED', 'provider_access_blocked')
            if classification == 'GPU_UNAVAILABLE_STOP' and not common.STOP.exists():
                common.write_new(common.STOP, {'classification': classification, 'message': message,
                                               'observed_epoch': time.time()})
            need(classification != 'GPU_UNAVAILABLE_STOP' and status.status.name == 'COMPLETE',
                 'fixed_v45_terminal_complete_required')
            hashes = {'dataset_metadata_sha256': put('dataset.json', dataset.to_dict()),
                'metadata_before_sha256': put('metadata-before.json', before.metadata.to_dict()),
                'status_sha256': put('status.json', status.to_dict()),
                'metadata_after_sha256': put('metadata-after.json', after.metadata.to_dict()),
                'saved_source_sha256': put('saved_source.ipynb', raw),
                'dataset_after_sha256': put('dataset-after.json', dataset_after.to_dict())}
        finally:
            if provider is not None:
                provider.close()
        common.publisher_lock_owner()
        need(provider is not None and provider.bridge.closed is True
             and provider.bridge.closure_verified is True, 'native_clean_close_required')
        observation = {'format': 'irisx/run008-live-predecessor-observation-v1',
            'code_version': 23, 'notebook_version': 45, 'provider_status': 'COMPLETE',
            'observed_epoch': time.time(), 'gpu_unavailable_stop': False, **hashes,
            **{key: False for key in ('runtime_closure_verified', 'manual_editor_session_mapping_verified',
                'manual_failure_root_cause_verified', 'physical_costs_known', 'scientific_result_verified')},
            'native_process_closure_verified': True,
            'scope': 'Five actual official read-only calls; preserved decoded DTO payloads, not HTTP wire bytes or GPU/scientific proof.'}
        digest = put('OBSERVATION.json', observation)
    return {'status': 'ACTUAL_READ_ONLY_PREDECESSOR_OBSERVED', 'observation': {
        'path': str(output / 'OBSERVATION.json'), 'bytes': len(encoded(observation)), 'sha256': digest},
        'code_version': 23, 'notebook_version': 45, 'provider_status': 'COMPLETE',
        'provider_read_calls': 5, 'provider_mutations': 0, 'native_process_closure_verified': True,
        'numeric_publication_contract_admitted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--review', required=True)
    parser.add_argument('--review-sha', required=True)
    args = parser.parse_args()
    result = capture(*prepare(args.review, args.review_sha))
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
