"""Exact code18 -> run006 proposal/final assembly; entirely local and offline.

The original complete code18 candidate and mandatory v33/v31 validators are
never replaced by source reconstruction or a current status observation.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import os
from pathlib import Path
import stat
import sys
import types

HERE = Path(__file__).absolute().parent
PREPARE_SHA = '3419fa0ab09d3e834f97d57990bb63ee96b4794a6c905d0d315e91f26ff6fb87'
LINEAGE_HELPER_SHA = 'f3cc35d60fd5f5aaa173feeb824120ff6ed18fea6a8aaba0f3368a973215e2b8'
_prep_path = HERE / 'prepare.py'
if any(x.is_symlink() for x in (_prep_path, *_prep_path.parents)):
    raise ValueError('unsafe reviewed preparation dependency')
_prep_info = _prep_path.lstat()
if not stat.S_ISREG(_prep_info.st_mode) or _prep_info.st_nlink != 1 or _prep_info.st_size > 1024**2:
    raise ValueError('bounded reviewed preparation dependency required')
_prep_fd = os.open(_prep_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
with os.fdopen(_prep_fd, 'rb') as _stream:
    _prep_opened = os.fstat(_stream.fileno())
    if (_prep_info.st_dev, _prep_info.st_ino, _prep_info.st_size, _prep_info.st_nlink) != (_prep_opened.st_dev, _prep_opened.st_ino, _prep_opened.st_size, _prep_opened.st_nlink):
        raise ValueError('reviewed preparation dependency changed')
    _prep_raw = _stream.read(1024**2 + 1)
if hashlib.sha256(_prep_raw).hexdigest() != PREPARE_SHA:
    raise ValueError('reviewed preparation dependency hash differs')
p = types.ModuleType('run006_pinned_source_preparation')
p.__file__, p.__package__ = str(_prep_path), ''
sys.modules[p.__name__] = p
exec(compile(_prep_raw, str(_prep_path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(p))

SOURCE_PROPOSAL_INVENTORY = 'ec05cdc4bbbf4e27ec409be90ee3fabdc3b108d3c38e2ae9e015f52d01e889a1'
SOURCE_SHA = 'bb997806108e8bc8b0cd392eb6e47d19127a29e16d446d1cf45e271b804f9b8a'
ARCHIVE_SHA = 'f136fe0ccad312c0a796475de73d115f0e5f4b9273be1e3a07761e2da0b507d7'
ENVIRONMENT_SHA = 'e1290d696b24992fbcce9a6f49d6486b90acb2689943a1c79a574e2713f78394'
OBSERVATION_SHA = '315a4784b4e57678c9483f849db4f4c869df0b4814ee54958347ebff1ffb699c'
V35_SAVED = '778c014ccea8b0f376d06afeeeceb318e50b3bce926ef13a6da068c9b3d5d917'
HANDOFF_SHA = 'd4b27f68dcca5eef308e1be576c49b044aec667bab9bf96887263255d4dfdfd1'
STOP_ATTESTATION_SHA = 'f7054775c0a29b3d0632332312ac0977f0b27c05cb542fe5dd9c3ce69d312071'
OWNER_REQUEST = {'owner_id': 'danielwuu', 'request_id': 'Sentinel_a518b4772d9c81919b0443db4d3cb05f',
                 'instruction': '直接修復並重跑，持續追蹤，還是之前那套模式'}
RUN = '/kaggle/working/irisx-qwen14b-rlvr-20261013-run006'
SOURCE = '/kaggle/working/irisx-qwen14b-rlvr-20261013-source006'
ENVIRONMENT = '/tmp/irisx-qwen14b-rlvr-20261013-environment006'
FORMAT = 'irisx/qwen14b-rlvr-run006-publication-contract-v1'
PROPOSAL_FORMAT = 'irisx/code19-run006-material-proposal-v1'
BINDING_KEYS = ('source_sha256', 'source_archive_sha256', 'environment_sha256', 'phase_policy_sha256',
                'dataset_file_sha256', 'deployment_inventory', 'source_proposal_inventory_sha256',
                'collector_sha256', 'current_predecessor_observation_sha256', 'owner_session_stop_attestation_sha256',
                'v35_original_dispatch_chain_sha256', 'v35_state_inventory_sha256', 'v35_launch_lineage_verifier_sha256')
need, read, obj, encoded, sha = p.need, p.read, p.obj, p.encoded, p.sha


def pinned(path, digest, cap=p.CAP):
    need(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'exact SHA256 required')
    raw = read(path, cap)
    need(sha(raw) == digest, 'pinned input differs: ' + Path(path).name)
    return raw


def descriptor(raw, name):
    return {'path': p.relative(name), **p.desc(raw)}


def closed_files(root, inventory, *, extra=()):
    """No unknown files, links or special objects; bounded bodies only."""
    root = p.ordinary(root)
    need(type(inventory) is dict and 0 < len(inventory) <= 12000, 'closed nonempty inventory required')
    for name, row in inventory.items():
        p.relative(name)
        need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int
             and 0 <= row['bytes'] <= p.CAP, 'inventory descriptor schema')
    actual = set()
    for path in root.rglob('*'):
        p.ordinary(path)
        info = path.lstat()
        need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'closed root contains special or hardlinked entry')
        if stat.S_ISREG(info.st_mode):
            actual.add(p.relative(path.relative_to(root).as_posix()))
    need(actual == set(inventory) | set(extra), 'closed inventory path set differs')
    need(sum(row['bytes'] for row in inventory.values()) <= 512 * 1024**2, 'closed inventory total cap')
    result = {}
    for name, row in inventory.items():
        raw = pinned(root / name, row['sha256'])
        need(len(raw) == row['bytes'], 'inventory byte size differs')
        result[name] = raw
    return result


def authenticated_base(snapshot, root):
    p.verify_code18_candidate(snapshot, root)
    inventory = obj(pinned(Path(root) / 'ASSEMBLY-INVENTORY.json', p.CODE18_ASSEMBLY_SHA))
    return closed_files(root, inventory, extra=('ASSEMBLY-INVENTORY.json',))


def source_inputs(root, base, assembler):
    inventory = obj(pinned(Path(root) / 'PROPOSAL-INVENTORY.json', SOURCE_PROPOSAL_INVENTORY))
    files = closed_files(root, inventory, extra=('PROPOSAL-INVENTORY.json',))
    proposal = obj(files['SOURCE-PROPOSAL.json'])
    need(proposal['assembler_source_sha256'] == PREPARE_SHA and proposal['production_admitted'] is False
         and proposal['run_authorized'] is False and proposal['successor_epoch'] is None, 'reviewed inert source proposal required')
    need(proposal['source_sha256'] == SOURCE_SHA and proposal['source_archive_sha256'] == ARCHIVE_SHA
         and proposal['environment_sha256'] == ENVIRONMENT_SHA and proposal['namespaces'] ==
         {'run': RUN, 'source': SOURCE, 'environment': ENVIRONMENT}, 'exact installer-inclusive run006 source required')
    source = {n.removeprefix('producer-source/'): raw for n, raw in files.items() if n.startswith('producer-source/')}
    old = {n.removeprefix('producer-source/'): raw for n, raw in base.items() if n.startswith('producer-source/')}
    need(len(source) == len(old) == 259 and set(source) == set(old), 'complete original/new runtime259')
    need({n for n in source if source[n] != old[n]} == {p.INSTALLER_TARGET, 'owned_runtime/release.py'}, 'only installer and release runtime delta allowed')
    need(sum(source[n] == old[n] for n in source if n.startswith('baseline/')) == 199, 'baseline199 exact preservation')
    need(sha(p.canonical(sorted((n, sha(b)) for n, b in source.items()))) == SOURCE_SHA, 'exact logical source closure')
    need(assembler.zip_blobs(source, stored=True) == files['source.zip'] and sha(files['source.zip']) == ARCHIVE_SHA, 'exact canonical source ZIP')
    need(sha(files['release/REVIEWED-ENVIRONMENT.json']) == ENVIRONMENT_SHA, 'environment pin')
    deployment = {name: files['deployment/' + name] for name in assembler.DEPLOYMENT_NAMES}
    need({n: p.desc(b) for n, b in deployment.items()} == proposal['deployment'], 'deployment inventory differs')
    return files, source, deployment, proposal


def observation_inputs(root, digest):
    need(digest == OBSERVATION_SHA, 'exact independently observed current-v35 packet required')
    raw = pinned(Path(root) / 'OBSERVATION.json', digest)
    doc = obj(raw)
    need(doc['format'] == 'irisx/run006-current-predecessor-observation-v1' and doc['status'] == 'CANCEL_ACKNOWLEDGED_DIAGNOSTICS_UNAVAILABLE'
         and doc['code_version'] == 18 and doc['notebook_version'] == 35 and doc['saved_source_sha256'] == V35_SAVED,
         'exact code18/v35 cancelled observation identity')
    need(doc['original_epoch'] == p.OLD_EPOCH and doc['original_deadline'] == p.OLD_DEADLINE, 'preserved consumed run005 clock')
    for key in ('runtime_closure_verified', 'manual_editor_session_mapping_verified', 'manual_failure_root_cause_verified',
                'physical_costs_known', 'scientific_result_verified'):
        need(doc.get(key) is False, 'observation cannot become runtime evidence')
    files = closed_files(root, doc['closed_files'], extra=('OBSERVATION.json',))
    need(len(files) == 30 and sha(files['saved_source.ipynb']) == V35_SAVED
         and sha(files['handoff.json']) == HANDOFF_SHA, 'closed original observation bodies')
    for row in doc['evidence'].values():
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'observation evidence descriptor')
        need(row['path'] in files and p.desc(files[row['path']]) == {k: row[k] for k in ('bytes', 'sha256')}, 'observation evidence link')
    files['OBSERVATION.json'] = raw
    return {'current-predecessor-v35/' + n: b for n, b in files.items()}


def stop_attestation(path, digest):
    need(digest == STOP_ATTESTATION_SHA, 'exact owner attestation packet required')
    raw = pinned(path, digest, 64 * 1024)
    doc = obj(raw)
    # Exact owner message, separately sealed by the parent/publisher. This is
    # overlap-avoidance evidence only; never a process/model closure capability.
    need(doc.get('format') == 'irisx/run006-owner-session-stop-attestation-v1', 'owner stop attestation format')
    need(doc.get('owner_attested_manual_editor_stopped') is True and doc.get('answer_message_id') == 'Sentinel_e2ee774828cc81918882d93d3ca1e20d', 'specific owner stop attestation required')
    need(doc.get('provider_session_mapping_verified') is False and doc.get('runtime_or_model_closure_verified') is False
         and doc.get('costs_or_billing_verified') is False, 'owner attestation is not runtime closure or cost proof')
    return raw


def solver_inputs(base, solver_path, new_solver_path, review_path, review_sha):
    old_raw = pinned(solver_path, p.SOLVER_SHA)
    material = obj(base['consumer-release/material_review.json'])
    need(material['dataset_file_sha256'] == p.SOLVER_SHA, 'original code18 material dataset binding')
    projected = p.project_solver(old_raw, {'run': RUN}, material)
    new_raw = read(new_solver_path)
    need(new_raw == projected, 'new solver must be exact two-path projection')
    review_raw = pinned(review_path, review_sha)
    proof = obj(review_raw)
    need(proof.get('format') == 'irisx/run006-solver-namespace-review-v1' and proof.get('status') == 'PASS'
         and proof.get('path_substitutions') == 2 and type(proof.get('path_substitutions')) is int
         and proof.get('reverse_byte_equality') is True and proof.get('escrow_bodies_read') is False, 'independent target-free solver review')
    for key, value in (('old_solver', old_raw), ('new_solver', new_raw)):
        row = proof[key]
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'} and type(row['path']) is str,
             'solver proof descriptor schema')
        need({k: row[k] for k in ('bytes', 'sha256')} == p.desc(value), 'solver proof byte binding')
    need(proof.get('prior_dataset_file_sha256') == p.SOLVER_SHA and proof.get('dataset_file_sha256') == sha(new_raw)
         and proof.get('dataset_escrow_sha256') == material['dataset_escrow_sha256']
         and proof.get('source_proposal_inventory_sha256') == SOURCE_PROPOSAL_INVENTORY, 'solver review source/material pins')
    return sha(new_raw), review_raw


def final_reviews(proposal_doc, *, proposal_path, proposal_sha, runtime_review_path, runtime_review_sha,
                  material_review_path, material_review_sha, old_material):
    expected = encoded(proposal_doc)
    need(pinned(proposal_path, proposal_sha) == expected, 'final inputs differ from exact independently reviewed proposal')
    runtime_raw = pinned(runtime_review_path, runtime_review_sha)
    material_raw = pinned(material_review_path, material_review_sha)
    runtime, material = obj(runtime_raw), obj(material_raw)
    need(runtime.get('format') == 'irisx/run006-runtime-review-v1' and runtime.get('status') == 'PASS'
         and runtime.get('proposal_sha256') == proposal_sha, 'independent runtime review required')
    need(material.get('format') == 'owned-rl-reviewed-material-v1' and material.get('status') == 'APPROVED'
         and material.get('proposal_sha256') == proposal_sha and material.get('runtime_review_sha256') == runtime_review_sha,
         'independent material review required')
    for key in BINDING_KEYS:
        need(runtime.get(key) == proposal_doc[key] and material.get(key) == proposal_doc[key], 'reviewed input binding differs: ' + key)
    for key in ('dataset_content_sha256', 'dataset_escrow_sha256'):
        need(material.get(key) == old_material.get(key), 'original dataset semantic/escrow commitment changed')
    need(runtime.get('baseline_unchanged_members') == 199 and material.get('baseline_unchanged_members') == 199
         and runtime.get('production_GPU_validation_passed') is False and material.get('production_GPU_validation_passed') is False,
         'honest baseline199 and no GPU-validation claim required')
    return runtime_raw, material_raw


def write_output(root, files):
    root = p.ordinary(root)
    need(not root.exists(), 'fresh assembly output required')
    root.mkdir(parents=True, mode=0o700)
    for name, raw in sorted(files.items()):
        path = p.ordinary(root / p.relative(name))
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        need(read(path) == raw, 'assembly output roundtrip differs')


def assemble(*, repository_root, base_root, source_proposal_root, observation_root, observation_sha,
             stop_attestation_path, stop_attestation_sha, solver_path, new_solver_path, solver_review_path,
             solver_review_sha, collector_path, collector_sha, output_root, mode,
             proposal_path=None, proposal_sha=None, runtime_review_path=None, runtime_review_sha=None,
             material_review_path=None, material_review_sha=None,
             v35_state_root=None, v35_state_inventory_path=None, v35_state_inventory_sha=None):
    need(mode in ('proposal', 'final'), 'proposal or final mode required')
    if mode == 'final':
        need(all((proposal_path, proposal_sha, runtime_review_path, runtime_review_sha, material_review_path, material_review_sha)),
             'independent exact proposal/runtime/material approvals required')
        need(all((v35_state_root, v35_state_inventory_path, v35_state_inventory_sha)), 'original v35 state and independently pinned inventory required for final assembly')
    state_inputs = (v35_state_root, v35_state_inventory_path, v35_state_inventory_sha)
    need(not any(state_inputs) or all(state_inputs), 'all original-v35 state inputs required together')
    repo, output = p.ordinary(repository_root), p.ordinary(output_root)
    need(output.is_relative_to(repo / '.irisx') and output != repo / '.irisx' and not output.exists(), 'fresh ignored assembly output required')
    for root in (base_root, source_proposal_root, observation_root, *([v35_state_root] if v35_state_root else [])):
        old = p.ordinary(root)
        need(not output.is_relative_to(old) and not old.is_relative_to(output), 'assembly input/output overlap')
    pinned(HERE / 'prepare.py', PREPARE_SHA)
    snapshot = p.Snapshot(repo)
    base = authenticated_base(snapshot, p.ordinary(base_root))
    assembler = p.load_module(snapshot.tool('prepare_successor_release.py'), 'exact_frozen_run005_assembly_helpers', repo / p.TOOL_REL / 'prepare_successor_release.py')
    source_files, source, deployment, source_proposal = source_inputs(source_proposal_root, base, assembler)
    observation = observation_inputs(observation_root, observation_sha)
    stopped = stop_attestation(stop_attestation_path, stop_attestation_sha)
    lineage_path = HERE / 'v35_lineage.py'
    lineage_raw = pinned(lineage_path, LINEAGE_HELPER_SHA)
    lineage_helper = p.load_module(lineage_raw, 'run006_reviewed_original_v35_lineage', lineage_path)
    lineage_files = lineage_helper.build(base_root, v35_state_root, v35_state_inventory_path, v35_state_inventory_sha) if all(state_inputs) else None
    lineage_sha = sha(lineage_files['LAUNCH-LINEAGE.json']) if lineage_files is not None else None
    dataset_sha, solver_review = solver_inputs(base, solver_path, new_solver_path, solver_review_path, solver_review_sha)
    collector = pinned(collector_path, collector_sha, 1024 * 1024)
    compile(collector, 'separately-reviewed-run006-collector.py', 'exec')
    prior, old_release = obj(base['publication-manifest.json']), obj(base['notebook-release.json'])
    old_material = obj(base['consumer-release/material_review.json'])
    environment = source_files['release/REVIEWED-ENVIRONMENT.json']
    source_zip = source_files['source.zip']
    deployment_inventory = {n: p.desc(b) for n, b in sorted(deployment.items())}
    wrappers = source_files['review-only/verify_parent_wrappers.py']
    proposal_doc = {'format': PROPOSAL_FORMAT, 'status': 'INDEPENDENT_REVIEW_REQUIRED',
        'assembler_source_sha256': sha(read(HERE / 'assemble_run006.py')),
        'base_assembly_inventory_sha256': p.CODE18_ASSEMBLY_SHA, 'base_publication_manifest_sha256': p.CODE18_MANIFEST_SHA,
        'source_proposal_inventory_sha256': SOURCE_PROPOSAL_INVENTORY, 'source_sha256': SOURCE_SHA,
        'source_archive_sha256': ARCHIVE_SHA, 'environment_sha256': ENVIRONMENT_SHA,
        'normalized_source_contract_sha256': source_proposal['normalized_source_contract_sha256'],
        'phase_policy_sha256': old_release['phase_policy_sha256'], 'dataset_file_sha256': dataset_sha,
        'dataset_namespace_review_sha256': solver_review_sha, 'deployment_inventory': deployment_inventory,
        'collector_sha256': collector_sha, 'current_predecessor_observation_sha256': observation_sha,
        'owner_session_stop_attestation_sha256': stop_attestation_sha,
        'v35_original_dispatch_chain_sha256': lineage_sha,
        'v35_original_dispatch_chain_verified': lineage_files is not None,
        'v35_state_inventory_sha256': v35_state_inventory_sha,
        'v35_launch_lineage_verifier_sha256': LINEAGE_HELPER_SHA,
        'installer_overlay': source_proposal['installer_overlay'],
        'changed_source_files': [p.INSTALLER_TARGET, 'owned_runtime/release.py'],
        'unchanged_source_members': 257, 'baseline_unchanged_members': 199,
        'original_baseline200_exact': False, 'production_GPU_validation_passed': False,
        'original_scorer_full167_denominator_preserved': True, 'historical_predecessor_readiness': prior['predecessor_readiness'],
        'owner_request': OWNER_REQUEST, 'namespace': {'code': 19, 'inactive': 36, 'active': 37, 'run': RUN, 'source': SOURCE, 'environment': ENVIRONMENT},
        'allocation_is_proposed_until_fresh_publisher_bracket': True, 'consumed_run005_epoch': p.OLD_EPOCH,
        'consumed_run005_deadline': p.OLD_DEADLINE, 'successor_epoch': None, 'provider_calls': 0, 'model_or_GPU_calls': 0}
    approved = mode == 'final'
    if approved:
        runtime_raw, material_raw = final_reviews(proposal_doc, proposal_path=proposal_path, proposal_sha=proposal_sha,
            runtime_review_path=runtime_review_path, runtime_review_sha=runtime_review_sha,
            material_review_path=material_review_path, material_review_sha=material_review_sha, old_material=old_material)
    else:
        runtime_raw = encoded({'format': 'irisx/run006-runtime-review-v1', 'status': 'REVIEW_REQUIRED',
            'proposal_sha256': sha(encoded(proposal_doc)), **{k: proposal_doc[k] for k in BINDING_KEYS},
            'baseline_unchanged_members': 199, 'production_GPU_validation_passed': False})
        material_raw = encoded({'format': 'owned-rl-reviewed-material-v1', 'status': 'REVIEW_REQUIRED',
            'proposal_sha256': sha(encoded(proposal_doc)), 'runtime_review_sha256': sha(runtime_raw),
            **{k: proposal_doc[k] for k in BINDING_KEYS}, 'baseline_unchanged_members': 199,
            'production_GPU_validation_passed': False,
            **{k: old_material.get(k) for k in ('dataset_content_sha256', 'dataset_escrow_sha256')}})
    auxiliary = {'NOTICE.txt': base['code-payload/NOTICE.txt'], 'release/MATERIAL-REVIEW.json': material_raw,
        'release/RUNTIME-REVIEW.json': runtime_raw, 'release/REVIEWED-ENVIRONMENT.json': environment,
        **{'deployment/' + n: b for n, b in deployment.items()}}
    payload_manifest = {'format': 'irisx/rlvr-code-material-v1', 'reference': assembler.DREF + '/19',
        'source': {'archive': {'name': 'source.zip', **p.desc(source_zip)}, 'source_sha256': SOURCE_SHA,
                   'files': {n: p.desc(b) for n, b in sorted(source.items())}},
        'auxiliary_files': {n: p.desc(b) for n, b in sorted(auxiliary.items())}}
    payload = {**auxiliary, 'manifest.json': encoded(payload_manifest), 'source.zip': source_zip}
    release = copy.deepcopy(old_release)
    release.update(production_admitted=approved, code_reference=assembler.DREF + '/19',
        code_manifest_sha256=sha(payload['manifest.json']), source_sha256=SOURCE_SHA, source_archive_sha256=ARCHIVE_SHA,
        material_review_sha256=sha(material_raw), environment_sha256=ENVIRONMENT_SHA, deployment=deployment_inventory,
        original_owner_request=copy.deepcopy(OWNER_REQUEST))
    release['dataset_references'][0] = assembler.DREF + '/19'
    release['storage']['environment_root'] = ENVIRONMENT
    release['storage']['observed_assembled_source_copy_bytes'] = sum(map(len, source.values())) + len(source_zip) + sum(map(len, auxiliary.values()))
    need(release['storage']['observed_assembled_source_copy_bytes'] + 16 * 1024**2 + 64 * 1024**2 < 128 * 1024**2, 'source/proof/log reservation exceeded')
    result = {'code-payload/' + n: b for n, b in payload.items()}
    result.update({'producer-source/' + n: b for n, b in source.items()})
    # Preserve the authentic historical chain at exactly its original paths.
    for name, raw in base.items():
        if name == 'PREDECESSOR-EVIDENCE.json' or name.startswith(('predecessor-v33/', 'historical-v31/')):
            result[name] = raw
    need(result['PREDECESSOR-EVIDENCE.json'] == base['PREDECESSOR-EVIDENCE.json'], 'original historical proof preserved')
    result.update(observation)
    result['OWNER-SESSION-STOP-ATTESTATION.json'] = stopped
    result['assembly/verify_v35_lineage.py'] = lineage_raw
    if lineage_files is not None:
        result.update({'current-predecessor-v35-launch/' + n: b for n, b in lineage_files.items()})
    result['SOURCE-INVENTORY.json'] = encoded({'format': 'irisx/run006-source-inventory-v1',
        'source_sha256': SOURCE_SHA, 'source_archive_sha256': ARCHIVE_SHA, 'files': {n: sha(b) for n, b in sorted(source.items())},
        'source_members': 259, 'unchanged_baseline_members': 199, 'original_baseline200_exact': False})
    result['SOURCE-FREEZE.json'] = encoded({'format': 'irisx/rlvr-source-freeze-v1', 'source_sha256': SOURCE_SHA,
        'source_archive_sha256': ARCHIVE_SHA, 'source_members': 259, 'files': payload_manifest['source']['files'],
        'original_baseline200_exact': False, 'unchanged_baseline_members': 199,
        'producer_inventory_artifact_sha256': sha(result['SOURCE-INVENTORY.json']),
        'self_consistency_pins': {'NORMALIZED_SOURCE_CONTRACT_SHA256': proposal_doc['normalized_source_contract_sha256'],
            'FINAL_V25_POLICY_SHA256': release['phase_policy_sha256'], 'REVIEWED_ENVIRONMENT_SHA256': ENVIRONMENT_SHA},
        'independent_approval_is_external': True})
    result['notebook-release.json'] = encoded(release)
    for name in ('finalize.py', 'accept_downloaded_mount.py'):
        result['assembly/' + name] = base['assembly/' + name]
    result['assembly/verify_parent_wrappers.py'] = wrappers
    for key, raw in {'material_review': material_raw, 'environment': environment,
                     'phase_policy': source['design/MEASURED-POLICY.json'],
                     'owner_protocol': base['consumer-release/owner_protocol.json']}.items():
        result['consumer-release/' + key + '.json'] = raw
    independent = {'format': 'owned-rl-independent-release-v1', 'source_sha256': SOURCE_SHA,
        **{key + '_sha256': sha(result['consumer-release/' + key + '.json']) for key in ('material_review', 'environment', 'phase_policy', 'owner_protocol')}}
    independent_raw = encoded(independent)
    result['consumer-release/release.json'] = independent_raw
    result.update({'terminal-consumer/' + n: b for n, b in assembler.consumer_bytes(base, independent_raw, SOURCE_SHA, ARCHIVE_SHA, collector_sha if approved else None).items()})
    builder = p.load_module(deployment['notebook_builder.py'], 'run006_exact_notebook_builder', output / 'code-payload/deployment/notebook_builder.py')
    entries = []
    for old_row in prior['notebooks']:
        row = copy.deepcopy(old_row)
        active = row['role'] == 'rlvr004'
        raw = encoded(builder.build(release, deployment['source_loader.py'].decode(), kind='active-template' if active else 'inactive'))
        result[row['path']] = raw
        row.update(bytes=len(raw), sha256=sha(raw), expected_predecessor_version=36 if active else 35,
            expected_version=37 if active else 36, predecessor_source_sha256=None if active else V35_SAVED,
            run_authorized=approved and active, dataset_sources=release['dataset_references'], output_root=RUN, source_parent=SOURCE)
        entries.append(row)
    upload = [descriptor(raw, name) for name, raw in sorted(payload.items())]
    material_rows = [row for row in upload if row['path'] != 'source.zip']
    dataset = copy.deepcopy(prior['datasets'][0])
    dataset.update(expected_predecessor_version=18, expected_version=19,
        root_manifest={'path': 'manifest.json', 'sha256': sha(payload['manifest.json'])}, upload_inventory=upload,
        upload_inventory_sha256=sha(p.canonical(upload) + b'\n'),
        version_notes='Run006 bounded installer logging and owned preparation diagnostics; code18/v35 and original v31/v33 preserved. Original material/model/hardware/science/full167 scorer/process/12h gates retained.',
        expected_readback_layouts={'original-upload': upload,
            'extracted-root': sorted(material_rows + [descriptor(b, n) for n, b in source.items()], key=lambda r: r['path']),
            'extracted-source-directory': sorted(material_rows + [descriptor(b, 'source/' + n) for n, b in source.items()], key=lambda r: r['path'])})
    result['code-upload.zip'] = assembler.zip_blobs(payload)
    dataset['transport_archive'] = descriptor(result['code-upload.zip'], 'code-upload.zip')
    publication = copy.deepcopy(prior)
    publication.update(format=FORMAT, owner_published_stable_commit=p.SNAPSHOT,
        source_freeze_sha256=sha(result['SOURCE-FREEZE.json']), runtime_source_sha256=SOURCE_SHA, source_identity_sha256=SOURCE_SHA,
        datasets=[dataset], notebooks=entries, source_review_only=not approved, run_authorized=approved,
        release_runtime_finalized=approved, runtime_source_approval=descriptor(runtime_raw, 'code-payload/release/RUNTIME-REVIEW.json'),
        parent_wrapper_verifier=descriptor(wrappers, 'assembly/verify_parent_wrappers.py'),
        no_model_mount_acceptance_helper=descriptor(result['assembly/accept_downloaded_mount.py'], 'assembly/accept_downloaded_mount.py'),
        current_predecessor_observation=descriptor(result['current-predecessor-v35/OBSERVATION.json'], 'current-predecessor-v35/OBSERVATION.json'),
        owner_session_stop_attestation=descriptor(stopped, 'OWNER-SESSION-STOP-ATTESTATION.json'),
        v35_original_dispatch_chain=None if lineage_files is None else descriptor(lineage_files['LAUNCH-LINEAGE.json'], 'current-predecessor-v35-launch/LAUNCH-LINEAGE.json'),
        v35_original_dispatch_chain_verified=lineage_files is not None,
        v35_launch_lineage_verifier=descriptor(lineage_raw, 'assembly/verify_v35_lineage.py'))
    need(publication['predecessor_readiness'] == prior['predecessor_readiness'], 'historical v33 admission descriptor changed')
    publication['jit']['entry'] = descriptor(result['assembly/finalize.py'], 'assembly/finalize.py')
    publication['jit']['dependencies'] = [descriptor(result['notebook-release.json'], 'notebook-release.json')] + [descriptor(deployment[n], 'code-payload/deployment/' + n) for n in ('notebook_builder.py', 'source_loader.py')]
    publication['consumer_contract'].update(source_sha256=SOURCE_SHA, dataset_sha256=dataset_sha,
        source_archive=descriptor(source_zip, 'code-payload/source.zip'),
        review_input_paths={'environment': SOURCE + '/release/REVIEWED-ENVIRONMENT.json', 'phase_policy': SOURCE + '/runtime/design/MEASURED-POLICY.json'},
        **{key: descriptor(result['consumer-release/' + key + '.json'], 'consumer-release/' + key + '.json') for key in ('release', 'material_review', 'environment', 'phase_policy', 'owner_protocol')})
    prefix = Path(RUN).name
    publication['terminal_contract'].update(evidence_path=prefix + '.evidence.zip', terminal_path=prefix + '.evidence.zip.terminal.json',
        checkpoint_path=prefix + '/checkpoints.zip', launcher_path=prefix + '-launcher', storage=release['storage'])
    result['publication-manifest.json'] = encoded(publication)
    result['SUCCESSOR-PROPOSAL.json'] = encoded(proposal_doc)
    result['review/SOLVER-NAMESPACE-REVIEW.json'] = solver_review
    result['review/INSTALLER-REVIEW.json'] = source_files['review-only/INSTALLER-REVIEW.json']
    result['ASSEMBLY-INVENTORY.json'] = encoded({n: p.desc(b) for n, b in sorted(result.items())})
    write_output(output, result)
    return {'status': 'INDEPENDENTLY_REVIEWED_LOCAL_CANDIDATE' if approved else 'INERT_FULL_ASSEMBLY_PROPOSAL',
        'output_root': str(output), 'proposal': descriptor(result['SUCCESSOR-PROPOSAL.json'], 'SUCCESSOR-PROPOSAL.json'),
        'publication_manifest': descriptor(result['publication-manifest.json'], 'publication-manifest.json'),
        'assembly_inventory_sha256': sha(result['ASSEMBLY-INVENTORY.json']), 'source_sha256': SOURCE_SHA,
        'source_archive_sha256': ARCHIVE_SHA, 'environment_sha256': ENVIRONMENT_SHA,
        'runtime_members': 259, 'unchanged_runtime_members': 257, 'unchanged_baseline_members': 199,
        'original_v31_v33_evidence_preserved': True, 'v35_runtime_closure_verified': False,
        'v35_original_dispatch_chain_verified': lineage_files is not None,
        'successor_epoch': None, 'provider_calls': 0, 'model_or_GPU_calls': 0, 'operational_success': False,
        'separate_final_operator_wire_monitor_review_and_fresh_provider_bracket_required': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('proposal', 'final'), required=True)
    for name in ('repository-root', 'base-root', 'source-proposal-root', 'observation-root', 'observation-sha',
                 'stop-attestation-path', 'stop-attestation-sha', 'solver-path', 'new-solver-path',
                 'solver-review-path', 'solver-review-sha', 'collector-path', 'collector-sha', 'output-root'):
        parser.add_argument('--' + name, required=True)
    for name in ('proposal-path', 'proposal-sha', 'runtime-review-path', 'runtime-review-sha', 'material-review-path', 'material-review-sha',
                 'v35-state-root', 'v35-state-inventory-path', 'v35-state-inventory-sha'):
        parser.add_argument('--' + name)
    print(encoded(assemble(**vars(parser.parse_args()))).decode(), end='')


if __name__ == '__main__':
    main()
