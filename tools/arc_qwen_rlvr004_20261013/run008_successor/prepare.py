"""Deterministic, non-publishing run008 assembly from the verified run007 bytes.

No provider, credential, clock, model, scorer or evaluator-body API is called.
The output is an inert proposal; new review and live allocation are mandatory.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import types

HERE = Path(__file__).absolute().parent
TOOL = HERE.parent
PREPARE_SHA = '1456ee33a3ff89b81a543cd5a7a6ebbe1154f261c10912ba8e03184c39acd840'
ASSEMBLER_SHA = 'ec7907c8432660d23f0874c41835e410ca046dea6034cb81c64f74b72fec3a04'
BASE_INVENTORY = 'de519816720ceb3bf07e0bf015c888b7e4bd9fdb344c2dbe355281230920ee88'
SOURCE_INVENTORY = 'fbe2a8aed267c8e189c7a5dae17a6dd7e4625383f5403ad14c382ddb3ab44714'
BASE_SOURCE = '89d19e7e9859d756f320d28fe55f908aee3c7b568f31ea10ecc82cb1be13b14b'
BASE_ARCHIVE = 'd224867c19eedf5605dc04079edacfcffa37a3171a15600d855007032145e77a'
REPORT_SHA = '3645c2321618476401242f3f2684c82c08f15978f894fae88b76574a7ab0cf04'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
UNBOUND_REFERENCE = DREF + '/UNBOUND-RUN008'
OLD_RUN = '/kaggle/working/irisx-qwen14b-rlvr-20261013-run007'
OLD_SOURCE = '/kaggle/working/irisx-qwen14b-rlvr-20261013-source007'
OLD_ENV = '/tmp/irisx-qwen14b-rlvr-20261013-environment007'
RUN, SOURCE, ENV = (value.replace('007', '008') for value in (OLD_RUN, OLD_SOURCE, OLD_ENV))
ALLOWED_TARGETS = frozenset('owned_runtime/' + name + '.py' for name in
                            ('environment_v2', 'parent_scoring', 'runner', 'worker'))


def dependency(path, digest, name):
    for entry in (path, *path.parents):
        if entry.is_symlink():
            raise ValueError('linked preparation dependency')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1024**2:
        raise ValueError('bounded regular preparation dependency required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        raw = stream.read(1024**2 + 1)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('preparation dependency bytes differ')
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


p = dependency(TOOL / 'preparation_successor/local_prepare_run007.py', PREPARE_SHA, 'run008_frozen_primitives')
need, read, obj, sha, encoded, canonical, desc = p.need, p.read, p.obj, p.sha, p.encoded, p.canonical, p.desc


def pinned(path, digest):
    need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'exact SHA256 required')
    raw = read(path)
    need(sha(raw) == digest, 'pinned input differs: ' + Path(path).name)
    return raw


def closed(root, inventory_name, digest):
    root = p.ordinary(root)
    inventory = obj(pinned(root / inventory_name, digest))
    need(0 < len(inventory) <= 12000, 'bounded closed inventory')
    actual = set()
    for path in root.rglob('*'):
        p.ordinary(path)
        info = path.lstat()
        need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
             'closed input contains special or hardlinked entry')
        if stat.S_ISREG(info.st_mode):
            actual.add(p.relative(path.relative_to(root).as_posix()))
    need(actual == set(inventory) | {inventory_name}, 'closed input path set differs')
    need(sum(row['bytes'] for row in inventory.values()) <= 512 * 1024**2, 'closed input total cap')
    result = {}
    for name, row in inventory.items():
        p.relative(name)
        need(type(row) is dict and set(row) == {'bytes', 'sha256'}
             and type(row['bytes']) is int and 0 <= row['bytes'] <= p.CAP, 'inventory descriptor')
        result[name] = pinned(root / name, row['sha256'])
        need(desc(result[name]) == row, 'inventory size differs')
    return result


def authenticate(repository, candidate, source_proposal, report):
    """Authenticate complete historical bodies without interpreting evaluator ZIPs."""
    reconstruction = obj(pinned(report, REPORT_SHA))
    need(reconstruction['status'] == 'PASS'
         and reconstruction['candidate_comparison']['all_files_byte_identical'] is True
         and reconstruction['source_comparison']['all_files_byte_identical'] is True, 'verified rebuild report')
    base = closed(candidate, 'ASSEMBLY-INVENTORY.json', BASE_INVENTORY)
    prior_source = closed(source_proposal, 'PROPOSAL-INVENTORY.json', SOURCE_INVENTORY)
    source = {n.removeprefix('producer-source/'): b for n, b in base.items() if n.startswith('producer-source/')}
    need(len(source) == 259 and source == {n.removeprefix('producer-source/'): b for n, b in prior_source.items()
                                         if n.startswith('producer-source/')}, '259 original source bodies')
    assembler = dependency(TOOL / 'prepare_successor_release.py', ASSEMBLER_SHA, 'run008_frozen_archive_primitives')
    need(sha(canonical(sorted((n, sha(b)) for n, b in source.items()))) == BASE_SOURCE, 'historical source identity')
    need(assembler.zip_blobs(source, stored=True) == base['code-payload/source.zip']
         and sha(base['code-payload/source.zip']) == BASE_ARCHIVE, 'historical source archive identity')
    frozen = p.frozen_runtime(p.Snapshot(repository), assembler)
    baseline = [n for n in frozen if n.startswith('baseline/')]
    need(len(baseline) == 200 and sum(source[n] == frozen[n] for n in baseline) == 199,
         'frozen baseline199 preservation')
    return base, source, assembler, prior_source


def overlay_inputs(source, manifest_path=None, manifest_sha=None, review_path=None, review_sha=None):
    need(bool(manifest_path) == bool(manifest_sha), 'overlay path/hash required together')
    need(bool(review_path) == bool(review_sha), 'review path/hash required together')
    need(not review_path or manifest_path, 'review requires overlays')
    if not manifest_path:
        return {}, None, None
    raw = pinned(manifest_path, manifest_sha)
    document = obj(raw)
    need(set(document) == {'format', 'base_source_sha256', 'files'}
         and document['format'] == 'irisx/run008-loader-overlay-set-v1'
         and document['base_source_sha256'] == BASE_SOURCE, 'new overlay manifest schema')
    rows = document['files']
    need(type(rows) is dict and 0 < len(rows) <= 4 and set(rows) <= ALLOWED_TARGETS, 'narrow loader target set')
    overlay = {}
    for target, row in rows.items():
        need(type(row) is dict and set(row) == {'path', 'original_sha256', 'bytes', 'sha256'}, 'overlay descriptor')
        p.relative(row['path'])
        body = pinned(Path(manifest_path).parent / row['path'], row['sha256'])
        need(type(row['bytes']) is int and len(body) == row['bytes'] and len(body) <= 1024**2
             and sha(source[target]) == row['original_sha256'] and body != source[target], 'exact changed overlay binding')
        compile(body, target, 'exec', dont_inherit=True, optimize=sys.flags.optimize)
        overlay[target] = body
    review = None
    if review_path:
        review = obj(pinned(review_path, review_sha))
        need(review.get('format') == 'irisx/run008-loader-overlay-review-v1'
             and review.get('status') == 'PASS' and review.get('scope') == 'LOCAL_SOURCE_REVIEW_ONLY'
             and review.get('overlay_manifest_sha256') == manifest_sha
             and review.get('base_source_sha256') == BASE_SOURCE
             and review.get('overlay_sha256') == {n: sha(b) for n, b in overlay.items()}
             and review.get('production_GPU_validation_passed') is False,
             'fresh independent exact overlay review required')
    return overlay, document, review


def replace(raw, before, after, count=1):
    return p.exact_replace(raw, before, after, count)


def environment_bytes(raw):
    document = obj(raw)
    changed = copy.deepcopy(document)
    for key in ('contract_path', 'environment_lock_path', 'tokenizer_path'):
        value = document['model_config'][key]
        need(value.startswith(OLD_SOURCE + '/runtime/'), 'original environment source path')
        changed['model_config'][key] = SOURCE + value[len(OLD_SOURCE):]
    result = encoded(changed)
    need(result.replace(SOURCE.encode(), OLD_SOURCE.encode()) == raw, 'environment only three source paths')
    return result


def solver_projection(raw, material):
    need(sha(raw) == material['dataset_file_sha256'], 'authentic historical target-free solver bytes')
    document = obj(raw)
    need(document.get('public_answers_read') is False and document.get('original_test_fields_retained') is False
         and document.get('cpu_fixture_only') is False, 'authentic target-free solver scope')
    need(document['denominators'] == {'dev': 16, 'holdout': 32, 'ttt_dev': 8, 'ttt_holdout': 8}, 'full training denominators')
    expected = copy.deepcopy(document)
    projected = raw
    for scope in ('dev', 'holdout'):
        before = document['escrow'][scope]['path']
        need(before.startswith(OLD_RUN + '/') and document['escrow'][scope]['sha256'] == material['dataset_escrow_sha256'][scope],
             'exact original escrow reference')
        after = RUN + before[len(OLD_RUN):]
        # Quoted JSON strings are the exact only two allowed byte changes.
        old_bytes = p.json.dumps(before, ensure_ascii=False).encode()
        new_bytes = p.json.dumps(after, ensure_ascii=False).encode()
        need(projected.count(old_bytes) == 1, 'one escrow reference occurrence')
        projected = projected.replace(old_bytes, new_bytes, 1)
        expected['escrow'][scope]['path'] = after
    need(obj(projected) == expected and projected.replace(RUN.encode(), OLD_RUN.encode()) == raw,
         'solver changes beyond two paths')
    return projected


def runtime_bytes(old, overlay, environment):
    source = {**old, **overlay}
    release, count = re.subn(rb"(?m)^REVIEWED_ENVIRONMENT_SHA256 = '[0-9a-f]{64}'$",
        ("REVIEWED_ENVIRONMENT_SHA256 = '" + sha(environment) + "'").encode(), old['owned_runtime/release.py'])
    need(count == 1, 'one release environment pin')
    normalized, count = re.subn(rb"(?m)^NORMALIZED_SOURCE_CONTRACT_SHA256 = '[0-9a-f]{64}'$",
        b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None', release)
    need(count == 1, 'one normalized source pin')
    source['owned_runtime/release.py'] = normalized
    normalized_sha = sha(canonical(sorted((n, sha(b)) for n, b in source.items())))
    source['owned_runtime/release.py'] = normalized.replace(b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None',
        ("NORMALIZED_SOURCE_CONTRACT_SHA256 = '" + normalized_sha + "'").encode(), 1)
    need({n for n in source if source[n] != old[n]} == set(overlay) | {'owned_runtime/release.py'}, 'runtime delta exceeds exact targets')
    need(all(source[n] == old[n] for n in source if n.startswith('baseline/')), 'all run007 baseline bytes retained')
    return source, normalized_sha


def deployment_bytes(base, reference):
    result = {n.removeprefix('code-payload/deployment/'): b for n, b in base.items()
              if n.startswith('code-payload/deployment/')}
    replacements = {
        'source_loader.py': [(DREF + '/20', reference)],
        'notebook_builder.py': [(OLD_RUN, RUN), (OLD_SOURCE, SOURCE)],
        'launch_notebook.py': [(OLD_ENV, ENV)],
        'prepare_entry.py': [(OLD_RUN, RUN), (OLD_ENV, ENV)],
    }
    for name, pairs in replacements.items():
        for before, after in pairs:
            result[name] = replace(result[name], before, after)
    need(len(result) == 5, 'five source-owned deployment helpers')
    for name, raw in result.items():
        compile(raw, name, 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    return result


def consumer_bytes(base, independent, source_sha, archive_sha):
    result = {n.removeprefix('terminal-consumer/'): b for n, b in base.items() if n.startswith('terminal-consumer/')}
    inventory = obj(result['CONSUMER-INVENTORY.json'])
    need(len(inventory['files']) == 21 and set(result) == set(inventory['files']) |
         {'CONSUMER-INVENTORY.json', 'CONSUMER-OPERATOR.json', 'reviewed_entry.py'}, 'closed consumer24')
    need(all(sha(result[n]) == h for n, h in inventory['files'].items()), 'unchanged consumer21 source bytes')
    operator = obj(result['CONSUMER-OPERATOR.json'])
    operator.update(source_sha256=source_sha, source_archive_sha256=archive_sha,
                    release_sha256=sha(independent), collector_entry_sha256=None)
    result['CONSUMER-OPERATOR.json'] = encoded(operator)
    result['reviewed_entry.py'], count = re.subn(rb"(?m)^REVIEWED_OPERATOR_PINS_SHA256 = '[0-9a-f]{64}'$",
        b'REVIEWED_OPERATOR_PINS_SHA256 = None', result['reviewed_entry.py'])
    need(count == 1, 'pending consumer entry remains unadmitted')
    return result


def write_output(root, files):
    root = p.ordinary(root)
    need(not root.exists(), 'fresh output required')
    root.mkdir(parents=True, mode=0o700)
    try:
        for name, raw in sorted(files.items()):
            path = root / p.relative(name)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
                stream.write(raw)
            need(read(path) == raw, 'output roundtrip differs')
    except BaseException:
        # Only the brand-new private output tree owned by this invocation.
        shutil.rmtree(root)
        raise


def prepare(*, repository_root, candidate_root, source_proposal_root, rebuild_report, output_root,
            overlay_manifest=None, overlay_manifest_sha=None, overlay_review=None, overlay_review_sha=None,
            proposed_code_version=None):
    repository, output = p.ordinary(repository_root), p.ordinary(output_root)
    scratch = repository / '.irisx/run008-packaging'
    need(output.is_relative_to(scratch) and output != scratch and not output.exists(), 'fresh ignored run008 output required')
    for root in (candidate_root, source_proposal_root, Path(rebuild_report).parent,
                 *([Path(overlay_manifest).parent] if overlay_manifest else [])):
        original = p.ordinary(root)
        need(not output.is_relative_to(original) and not original.is_relative_to(output), 'input/output overlap')
    # A caller may rebuild a numerical draft after a fresh live readback. This
    # remains an explicitly unreserved proposal, never evidence of provider state.
    need(proposed_code_version is None or type(proposed_code_version) is int and proposed_code_version > 20,
         'optional proposed code version must be a new integer; never current-state evidence')
    reference = UNBOUND_REFERENCE if proposed_code_version is None else DREF + '/' + str(proposed_code_version)
    base, old, assembler, prior_source = authenticate(repository, candidate_root, source_proposal_root, rebuild_report)
    overlay, overlay_doc, review_doc = overlay_inputs(old, overlay_manifest, overlay_manifest_sha, overlay_review, overlay_review_sha)
    environment = environment_bytes(base['consumer-release/environment.json'])
    source, normalized_sha = runtime_bytes(old, overlay, environment)
    source_sha = sha(canonical(sorted((n, sha(b)) for n, b in source.items())))
    archive = assembler.zip_blobs(source, stored=True)
    deployment = deployment_bytes(base, reference)
    old_release = obj(base['notebook-release.json'])
    old_material = obj(base['consumer-release/material_review.json'])
    solver = solver_projection(prior_source['review-only/solver-descriptor.json'], old_material)
    binding = {'dataset_file_sha256': sha(solver), 'source_sha256': source_sha, 'source_archive_sha256': sha(archive),
        'environment_sha256': sha(environment), 'normalized_source_contract_sha256': normalized_sha,
        'phase_policy_sha256': old_release['phase_policy_sha256'], 'scorer_pins_sha256': old_release['scorer_pins_sha256'],
        'deployment': {n: desc(b) for n, b in sorted(deployment.items())},
        'loader_overlay_manifest_sha256': overlay_manifest_sha, 'loader_overlay_review_sha256': overlay_review_sha}
    pending = {'format': 'irisx/run008-review-requirements-v1', 'status': 'REVIEW_REQUIRED',
               'production_admitted': False, 'baseline_unchanged_members': 199,
               'production_GPU_validation_passed': False, **binding}
    runtime_review = encoded({**pending, 'review_kind': 'runtime'})
    material_review = encoded({**pending, 'review_kind': 'material', 'dataset_namespace_review_sha256': None,
        'dataset_file_sha256': sha(solver), 'unchanged_historical_dataset_escrow_sha256': old_material['dataset_escrow_sha256']})
    auxiliary = {'NOTICE.txt': base['code-payload/NOTICE.txt'], 'release/MATERIAL-REVIEW.json': material_review,
        'release/RUNTIME-REVIEW.json': runtime_review, 'release/REVIEWED-ENVIRONMENT.json': environment,
        **{'deployment/' + n: b for n, b in deployment.items()}}
    manifest = {'format': 'irisx/rlvr-code-material-v1', 'reference': reference,
        'source': {'archive': {'name': 'source.zip', **desc(archive)}, 'source_sha256': source_sha,
                   'files': {n: desc(b) for n, b in sorted(source.items())}},
        'auxiliary_files': {n: desc(b) for n, b in sorted(auxiliary.items())}}
    payload = {**auxiliary, 'source.zip': archive, 'manifest.json': encoded(manifest)}
    release = copy.deepcopy(old_release)
    release.update(production_admitted=False, code_reference=reference,
        code_manifest_sha256=sha(payload['manifest.json']), source_sha256=source_sha,
        source_archive_sha256=sha(archive), environment_sha256=sha(environment),
        material_review_sha256=sha(material_review), deployment=binding['deployment'], original_owner_request=None)
    release['admission_scope'] = 'INERT_RUN008_PROPOSAL; fresh runtime/material/owner/publisher approvals required'
    release['dataset_references'][0] = reference
    release['storage']['environment_root'] = ENV
    release['storage']['observed_assembled_source_copy_bytes'] = sum(map(len, source.values())) + len(archive) + sum(map(len, auxiliary.values()))
    need(release['storage']['observed_assembled_source_copy_bytes'] + 80 * 1024**2 < 128 * 1024**2, 'source/proof/log reservation exceeded')
    consumer_release = {key: base['consumer-release/' + key + '.json'] for key in ('phase_policy', 'owner_protocol')}
    consumer_release.update(material_review=material_review, environment=environment)
    independent = encoded({'format': 'owned-rl-independent-release-v1', 'source_sha256': source_sha,
        **{key + '_sha256': sha(raw) for key, raw in consumer_release.items()}})
    consumers = consumer_bytes(base, independent, source_sha, sha(archive))
    files = {'code-payload/' + n: b for n, b in payload.items()}
    files.update({'producer-source/' + n: b for n, b in source.items()})
    files.update({'terminal-consumer/' + n: b for n, b in consumers.items()})
    files.update({'consumer-release/' + n + '.json': b for n, b in consumer_release.items()})
    files['consumer-release/release.json'] = independent
    files['notebook-release.json'] = encoded(release)
    files['review-only/solver-descriptor.json'] = solver
    files['review-only/SOLVER-PROJECTION.json'] = encoded({'format': 'irisx/run008-solver-projection-v1',
        'status': 'INDEPENDENT_REVIEW_REQUIRED', 'original_sha256': old_material['dataset_file_sha256'],
        'projected_sha256': sha(solver), 'path_substitutions': 2, 'reverse_byte_equality': True,
        'escrow_bodies_read': False, 'production_admitted': False})
    files['code-upload-PROPOSAL.zip'] = assembler.zip_blobs(payload)
    # Existing pure finalizer rejects this proposal because production_admitted=False.
    for name in ('finalize.py', 'accept_downloaded_mount.py'):
        files['assembly/' + name] = base['assembly/' + name]
    wrappers = base['assembly/verify_parent_wrappers.py']
    for before, after in ((OLD_RUN, RUN), (OLD_SOURCE, SOURCE), (OLD_ENV, ENV)):
        wrappers = replace(wrappers, before, after)
    files['assembly/verify_parent_wrappers.py'] = wrappers
    builder = p.load_module(deployment['notebook_builder.py'], 'run008_inert_builder', output / 'code-payload/deployment/notebook_builder.py')
    for kind in ('inactive', 'active-template'):
        files['run008-' + kind + '.ipynb'] = encoded(builder.build(release, deployment['source_loader.py'].decode(), kind=kind))
    delta = {n: {'old': desc(old[n]), 'new': desc(source[n]), 'reason': 'derived environment/source pins' if n == 'owned_runtime/release.py' else 'loader overlay'}
             for n in source if old[n] != source[n]}
    blockers = ['fresh exact-resource access and official terminal source/settings/version bracket',
        'independent final runtime/material/source/consumer/transport/wire review',
        'independent review of the authentic target-free solver two-path run008 projection',
        'new owner request binding; native official-auth publisher integration and review',
        'numeric Dataset download/mount acceptance; inactive notebook source/settings readback',
        'fresh run008-only claim/journal and immutable predispatch epoch; never reused run007 state']
    if not overlay: blockers.insert(0, 'loader overlays not yet supplied')
    elif not review_doc: blockers.insert(0, 'fresh independent exact loader-overlay review')
    proposal = {'format': 'irisx/run008-local-assembly-proposal-v1', 'status': 'OFFLINE_PROPOSAL_NOT_PUBLISHABLE',
        'builder_sha256': sha(read(HERE / 'prepare.py')), 'historical_candidate_inventory_sha256': BASE_INVENTORY,
        'historical_source_proposal_inventory_sha256': SOURCE_INVENTORY, 'historical_rebuild_report_sha256': REPORT_SHA,
        'historical_predecessor': {'code_version': 20, 'notebook_version': 39, 'epoch': 1791908053,
                                 'deadline': 1791951253, 'current_live_identity_verified': False},
        'proposed_code_version': proposed_code_version, 'provider_versions_reserved': False,
        'source_members': 259, 'unchanged_run007_source_members': len(source) - len(delta),
        'unchanged_run007_baseline_members': 200, 'unchanged_frozen_code18_baseline_members': 199,
        'unchanged_consumer_helper_members': 21, 'runtime_delta': delta, 'namespaces': {'run': RUN, 'source': SOURCE, 'environment': ENV},
        'non_code_dataset_pins': release['dataset_references'][1:], 'material_pins': release['material_pins'],
        'new_review_required': True, 'old_approvals_rebound': False, 'original_owner_request_reused': False,
        'publication_admitted': False, 'run_authorized_by_artifact': False, 'successor_epoch': None,
        'session_seconds': 43200, 'maximum_dispatch_age_seconds': 60,
        'latest_owner_scope_includes_monitoring_and_retrieval': True,
        'provider_calls': 0, 'model_or_GPU_calls': 0, 'scientific_result': None,
        'evaluator_bodies_semantically_parsed': False, 'whole_candidate_upload_allowed': False,
        'future_only_upload_root': 'code-payload', 'blocking_gates': blockers, **binding}
    files['ASSEMBLY-PROPOSAL.json'] = encoded(proposal)
    files['DELTA-INVENTORY.json'] = encoded({'runtime': delta,
        'deployment': {n: {'old': desc(base['code-payload/deployment/' + n]), 'new': desc(b)}
                       for n, b in deployment.items() if b != base['code-payload/deployment/' + n]},
        'unchanged_consumer_helpers': obj(consumers['CONSUMER-INVENTORY.json'])['files']})
    files['ASSEMBLY-INVENTORY.json'] = encoded({n: desc(b) for n, b in sorted(files.items())})
    write_output(output, files)
    return {**proposal, 'output_root': str(output), 'assembly_inventory_sha256': sha(files['ASSEMBLY-INVENTORY.json'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root', 'candidate-root', 'source-proposal-root', 'rebuild-report', 'output-root'):
        parser.add_argument('--' + name, required=True)
    for name in ('overlay-manifest', 'overlay-manifest-sha', 'overlay-review', 'overlay-review-sha'):
        parser.add_argument('--' + name)
    parser.add_argument('--proposed-code-version', type=int)
    print(encoded(prepare(**vars(parser.parse_args()))).decode(), end='')


if __name__ == '__main__':
    main()
