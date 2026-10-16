"""Source-only training numeric diagnostic assembly; no provider or model I/O.

Drafts never manufacture independent approvals. Final mode consumes exact fresh
reviewer receipts. The unchanged pure finalizer is called only by the separately
reviewed publisher after numeric mount and inactive-notebook readbacks.
"""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import sys
import types

HERE = Path(__file__).absolute().parent
TOOL = HERE.parent
PREPARE_SHA = '302c61282ce6abc19254cf22d2f16104f0cbd523af28b8431a52a70a683510c2'
PROPOSAL_INVENTORY_SHA = 'fc32f98bef4188761fd51275bb05dd26c6fbd237afb8b8403b492f61442055cd'
ORIGINAL_SOURCE_SHA = 'c61025e67354272099e40941cadcd77202964846d9a4c42c51a1817f77bb661b'
ORIGINAL_ARCHIVE_SHA = '4d8b414bd35ca79a2eaaec7042880966879ed13bdeaf96762eaee7932ee1de4c'
SOURCE_SHA = '38698fd0861b2940bd303b59899011da0fb53d2daa4da846de80521bfc2c828b'
ARCHIVE_SHA = 'ffaea7e6dd0fd3df1b6bc0566b27278f47f318b2d680d96e358a1cc5b8584dff'
GUARDED_PARENT_SHA = '48e9b757429ffd3273b79909356fe61780fbd005d967817ba04c9caf4f8e7592'
ORIGINAL_PARENT_SHA = 'c95e9caf5e4f8230d90661bc8b68159fe29a63b52c1d6cff4f22dab05023a42e'
# Consumed v41 deployment bytes remain the input; only these two callers change.
PREPARATION_ORIGINAL = {
    'launch_notebook.py': '254f5d154bf58bc3ed962321f77a18460fa5d51c654a8e263076099fe3b96e1f',
    'prepare_entry.py': 'c85bbd12460480ca26798860ae358dd8f3fc5e3e2556090d0589828e44ef2648',
}
PREPARATION_REPAIRS = {
    'launch_notebook.py': '466c7a7a5549298172e2d2def0ad90a7f146458010c09b446b9d777cf5df3aee',
    'prepare_entry.py': '3b1c429224510bc4a65878d82959ce088f6f88767f88200eefb72392ff2e3e47',
}
# Legacy publication wire schema; run_purpose fixes this successor's narrower scope.
FORMAT = 'irisx/qwen14b-rlvr-run008-publication-contract-v1'
PROPOSAL_FORMAT = 'irisx/numeric-diagnostic-admission-proposal-v1'


def dependency(path, digest, name):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('linked assembly dependency')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 1024**2:
        raise ValueError('bounded regular assembly dependency required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        raw = stream.read(1024**2 + 1)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('assembly dependency bytes differ')
    module = types.ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(module))
    return module


s = dependency(TOOL / 'run008_successor/prepare.py', PREPARE_SHA, 'run008_frozen_successor')
p = s.p
need, read, obj, sha, encoded, canonical, desc = s.need, s.read, s.obj, s.sha, s.encoded, s.canonical, s.desc
DREF = s.DREF
RUN = '/kaggle/working/irisx-qwen14b-numeric-diagnostic-20261016-run002'
SOURCE = '/kaggle/working/irisx-qwen14b-numeric-diagnostic-20261016-source002'
ENV = '/tmp/irisx-qwen14b-numeric-diagnostic-20261016-environment002'
RUN_PURPOSE = 'training-only-numeric-diagnostic-v1'
BASE_WRAPPER_SHA = 'c3aa3b40cfba89a969dd171e758e3d9c4875686b259cfcabf80dec1da486d6bb'
BASE_TRANSPORT_SHA = '7a5a766baa4ab2654037deeab9d39e98bbd2be7b5c7eb9c341d861f86eb6cda0'
BASE_ACTIVE_WIRE_SHA = '2ab7be25726d38863379a7b63d682f86abd33d52b91116c73734cc9e647da301'
# Fixed numeric successor authenticates all behavior. Only its exact common
# dependency pin may change as the same-checkout operator is rebound.
PUBLISHED_TRANSPORT_SHA = '51d22232569515738a4e8e8215dfbcf2d17a26559c5b4fac96057ef43a6b593d'
PUBLISHED_ACTIVE_WIRE_SHA = '7fe742b5a7da15e13d1b348fad8c2f9af8cda4a5dd8206dfc2e6755534da551d'
PUBLISHED_COMMON_SHA = '88faa050b8cd7564e2d46552091773df4025b0589bd37771f79ea8648f2c053a'
BASE_PARENT_ENTRY_SHA = '91f9e9996ee67d699660f9473ca27138c9b357e3e5eb5ca66d48413022a164a3'
RUNTIME_TARGETS = frozenset(('rl_session/runtime.py', 'rl_session/numeric_shadow.py',
    'experiment_flow/flow.py', 'experiment_flow/metering.py', 'owned_runtime/worker.py',
    'owned_runtime/runner.py', 'owned_runtime/ledger.py'))
BINDING_KEYS = ('source_sha256', 'source_archive_sha256', 'environment_sha256', 'normalized_source_contract_sha256',
    'phase_policy_sha256', 'scorer_pins_sha256', 'dataset_file_sha256', 'dataset_escrow_sha256',
    'deployment_inventory', 'collector_sha256', 'consumer_helper_inventory_sha256',
    'current_predecessor_observation_sha256', 'owner_direction_sha256', 'versions',
    'loader_overlay_manifest_sha256', 'loader_overlay_review_sha256', 'assembler_source_sha256',
    'source_proposal_inventory_sha256', 'historical_candidate_inventory_sha256',
    'run_purpose', 'numeric_overlay_inventory', 'parent_wrapper_verifier_sha256', 'source_members',
    'publication_helper_inventory')


def descriptor(raw, name):
    return {'path': p.relative(name), **desc(raw)}


def pinned(path, digest):
    return s.pinned(path, digest)


def output_path(repository, output):
    root, out = p.ordinary(repository), p.ordinary(output)
    scratch = root / '.irisx/numeric-diagnostic-20261016'
    need(out.is_relative_to(scratch) and out != scratch and not out.exists(), 'fresh ignored admission output required')
    return out


def observation_inputs(root, digest):
    root = p.ordinary(root)
    raw = pinned(root / 'OBSERVATION.json', digest)
    observation = obj(raw)
    need(observation.get('format') == 'irisx/run008-native-current-predecessor-observation-v1', 'fresh native observation format')
    for name, floor in (('code_version', 20), ('notebook_version', 39)):
        need(type(observation.get(name)) is int and observation[name] >= floor, 'actual numeric predecessor ' + name)
    need(observation.get('provider_status') in ('ERROR', 'COMPLETE', 'CANCEL_ACKNOWLEDGED')
         and observation.get('gpu_unavailable_stop') is False, 'terminal actual predecessor without GPU stop')
    for name in ('runtime_closure_verified', 'manual_editor_session_mapping_verified', 'manual_failure_root_cause_verified',
                 'physical_costs_known', 'scientific_result_verified'):
        need(observation.get(name) is False, 'observation is not runtime proof: ' + name)
    need(type(observation.get('observed_epoch')) in (int, float) and p.math.isfinite(observation['observed_epoch'])
         and observation['observed_epoch'] > 0, 'finite observation time')
    rows = observation['closed_files']
    # Reuse the frozen closed-directory checker through a locally measured inventory.
    need(type(rows) is dict and 0 < len(rows) <= 100, 'bounded observation inventory')
    actual = set()
    for path in root.rglob('*'):
        p.ordinary(path)
        info = path.lstat()
        need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'ordinary observation entry')
        if stat.S_ISREG(info.st_mode): actual.add(p.relative(path.relative_to(root).as_posix()))
    need(actual == set(rows) | {'OBSERVATION.json'}, 'closed observation paths')
    files = {}
    for name, row in rows.items():
        p.relative(name)
        need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int
             and 0 <= row['bytes'] <= 4 * 1024**2, 'bounded observation descriptor')
        files[name] = pinned(root / name, row['sha256'])
        need(desc(files[name]) == row, 'observation descriptor bytes')
    roles = {'saved_source', 'notebook_before', 'notebook_after', 'notebook_status', 'dataset_before', 'dataset_after'}
    evidence = observation['evidence']
    need(type(evidence) is dict and roles <= set(evidence), 'complete raw observation roles')
    need(len({r['path'] for r in evidence.values()}) == len(evidence), 'unique evidence roles')
    for row in evidence.values():
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'} and
             rows.get(row['path']) == {k: row[k] for k in ('bytes', 'sha256')}, 'exact observation evidence link')
    role = lambda name: files[evidence[name]['path']]
    need(sha(role('saved_source')) == observation['saved_source_sha256'], 'saved source hash')
    for name in ('dataset_before', 'dataset_after'):
        meta = obj(role(name))
        need(meta.get('id') == 12504696 and meta.get('ref') == DREF and meta.get('isPrivate') is True
             and meta.get('ownerRef') == 'danielwuu' and meta.get('currentVersionNumber') == observation['code_version'],
             'exact private dataset identity')
    for name in ('notebook_before', 'notebook_after'):
        meta = obj(role(name))
        need(meta.get('id') == 138123872 and meta.get('ref') == 'danielwuu/iris-x-learning-agent-20261011'
             and meta.get('currentVersionNumber') == observation['notebook_version'] and meta.get('isPrivate') is True,
             'exact private notebook identity')
        need(meta.get('kernelType') == 'notebook' and meta.get('language') == 'python'
             and meta.get('enableGpu') is True and meta.get('enableTpu') is False
             and meta.get('enableInternet') is False and meta.get('machineShape') == 'NvidiaRtxPro6000', 'offline existing hardware')
    need(obj(role('notebook_status')).get('status') == observation['provider_status'], 'raw terminal status')
    files['OBSERVATION.json'] = raw
    return observation, {'current-predecessor/' + n: b for n, b in files.items()}


def owner_inputs(path, digest):
    raw = pinned(path, digest)
    owner = obj(raw)
    need(owner.get('format') == 'irisx/numeric-diagnostic-owner-direction-v1'
         and owner.get('owner_id') == 'danielwuu', 'fresh diagnostic owner direction')
    need(owner.get('run_purpose') == RUN_PURPOSE and owner.get('training_only') is True,
         'fixed training-only diagnostic authorization')
    for key in ('one_accepted_run_per_distinct_reviewed_candidate', 'continuous_monitoring_authorized',
                'result_retrieval_authorized'):
        need(owner.get(key) is True, 'diagnostic continuation scope: ' + key)
    for key in ('rl_optimizer_commit_authorized', 'later_B_C_dev_holdout_PUBLIC_authorized',
                'gpu_quota_query_authorized', 'new_resource_or_paid_provisioning_authorized',
                'official_competition_submission_authorized', 'legal_agreement_acceptance_authorized',
                'credential_or_permission_changes_authorized_by_this_file', 'runtime_or_scientific_success_claim'):
        need(owner.get(key) is False, 'bounded diagnostic scope: ' + key)
    need(owner.get('session_limit_seconds') == 43200 and owner.get('original_public_task_count') == 120
         and owner.get('original_public_query_denominator') == 167, 'original clock and reference scorer bounds')
    need(type(owner.get('instruction')) is str and 40 < len(owner['instruction']) <= 10000
         and type(owner.get('request_id')) is str and 1 <= len(owner['request_id']) <= 256,
         'fresh sanitized owner identity')
    return owner, raw


def review_inputs(proposal, *, proposal_path, proposal_sha, solver_review_path, solver_review_sha,
                  runtime_review_path, runtime_review_sha, material_review_path, material_review_sha, original_solver, new_solver):
    need(pinned(proposal_path, proposal_sha) == encoded(proposal), 'final assembly differs from independently reviewed proposal')
    solver_raw = pinned(solver_review_path, solver_review_sha)
    solver = obj(solver_raw)
    need(solver.get('format') == 'irisx/numeric-diagnostic-solver-namespace-review-v1' and solver.get('status') == 'PASS'
         and type(solver.get('path_substitutions')) is int and solver['path_substitutions'] == 2
         and solver.get('reverse_byte_equality') is True and solver.get('escrow_bodies_read') is False,
         'independent exact two-path solver review')
    need(solver.get('original_solver') == desc(original_solver) and solver.get('projected_solver') == desc(new_solver)
         and solver.get('dataset_escrow_sha256') == proposal['dataset_escrow_sha256']
         and solver.get('source_proposal_inventory_sha256') == PROPOSAL_INVENTORY_SHA, 'solver review exact inputs')
    runtime_raw, material_raw = pinned(runtime_review_path, runtime_review_sha), pinned(material_review_path, material_review_sha)
    runtime, material = obj(runtime_raw), obj(material_raw)
    need(runtime.get('format') == 'irisx/numeric-diagnostic-runtime-review-v1' and runtime.get('status') == 'PASS'
         and runtime.get('proposal_sha256') == proposal_sha, 'independent runtime review')
    need(material.get('format') == 'owned-rl-reviewed-material-v1' and material.get('status') == 'APPROVED'
         and material.get('proposal_sha256') == proposal_sha and material.get('runtime_review_sha256') == runtime_review_sha,
         'independent material review')
    for document in (runtime, material):
        for key in BINDING_KEYS:
            need(document.get(key) == proposal[key], 'review exact binding: ' + key)
        need(document.get('dataset_namespace_review_sha256') == solver_review_sha
             and document.get('baseline_unchanged_members') == 199
             and document.get('production_GPU_validation_passed') is False, 'review honest CPU-only scope')
    need(material.get('dataset_content_sha256') is None, 'retain original absent semantic commitment without reading evaluator')
    return solver_raw, runtime_raw, material_raw


def repaired_preparation(deployment):
    """Apply only the fixed two-caller deployment successor.

    The original closed source proposal is still authenticated before this call.
    Normal proposal/deployment inventory and independent runtime/material review
    bind these bytes. This helper cannot approve or publish them.
    """
    result = dict(deployment)
    old_run = '/kaggle/working/irisx-qwen14b-rlvr-20261012-run005'
    old_env = '/tmp/irisx-qwen14b-rlvr-20261012-environment005'
    for name, digest in PREPARATION_REPAIRS.items():
        need(name in deployment and sha(deployment[name]) == PREPARATION_ORIGINAL[name],
             'exact consumed v41 preparation caller required: ' + name)
        raw = pinned(TOOL / 'preparation_environment_repair' / name, digest)
        raw = s.replace(raw, old_env, s.ENV)
        if name == 'prepare_entry.py':
            raw = s.replace(raw, old_run, s.RUN)
        else:
            raw = s.replace(raw, 'exact run005/source005 paths required',
                            'exact fresh successor run/source paths required')
        compile(raw, name, 'exec', dont_inherit=True, optimize=sys.flags.optimize)
        need(raw != deployment[name], 'preparation repair must change its caller')
        result[name] = raw
    need(set(result) == set(deployment) and
         {name for name in result if result[name] != deployment[name]} == set(PREPARATION_REPAIRS),
         'only two preparation deployment callers may change')
    return result


def repaired_runtime(source, environment):
    """Exact one-policy successor plus its derived normalized self-consistency pin."""
    need(len(source) == 259 and sha(canonical(sorted((n, sha(b)) for n, b in source.items())))
         == ORIGINAL_SOURCE_SHA, 'exact consumed v41 runtime required')
    target = 'owned_runtime/parent_scoring.py'
    need(sha(source[target]) == ORIGINAL_PARENT_SHA, 'exact consumed parent policy required')
    body = pinned(TOOL / 'preparation_environment_repair/parent_scoring.py', GUARDED_PARENT_SHA)
    compile(body, target, 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    changed, normalized = s.runtime_bytes(source, {target: body}, environment)
    archive_builder = s.dependency(TOOL / 'prepare_successor_release.py', s.ASSEMBLER_SHA,
                                   'guarded_runtime_archive_primitives')
    archive = archive_builder.zip_blobs(changed, stored=True)
    need(sha(canonical(sorted((n, sha(b)) for n, b in changed.items()))) == SOURCE_SHA
         and sha(archive) == ARCHIVE_SHA, 'exact reviewed guard successor identities')
    return changed, archive, normalized


def projected_environment(raw):
    document = obj(raw)
    for key in ('contract_path', 'environment_lock_path', 'tokenizer_path'):
        need(document['model_config'][key].startswith(s.SOURCE + '/runtime/'),
             'original reviewed environment path')
    need(raw.count(s.SOURCE.encode()) == 3, 'exact three source paths in environment')
    result = raw.replace(s.SOURCE.encode(), SOURCE.encode())
    need(result.replace(SOURCE.encode(), s.SOURCE.encode()) == raw, 'environment projection only')
    return result


def diagnostic_solver(raw, material):
    intermediate = s.solver_projection(raw, material)
    need(intermediate.count(s.RUN.encode()) == 2, 'exact two solver reference paths')
    result = intermediate.replace(s.RUN.encode(), RUN.encode())
    need(result.replace(RUN.encode(), s.OLD_RUN.encode()) == raw, 'only two original solver paths')
    return result


def runtime_overlay():
    root = HERE / 'runtime'
    bodies = {}
    for name in sorted(RUNTIME_TARGETS):
        raw = read(root / name)
        compile(raw, name, 'exec', dont_inherit=True, optimize=sys.flags.optimize)
        bodies[name] = raw
    return bodies


def diagnostic_runtime(source, original_environment, environment, overlay):
    """Overlay before any new proposal/review binding; never patch an approval."""
    guarded, _, _ = repaired_runtime(source, original_environment)
    need(set(overlay) == RUNTIME_TARGETS, 'exact seven diagnostic overlay targets')
    need('rl_session/numeric_shadow.py' not in guarded, 'diagnostic module must be a new member')
    for name, raw in overlay.items():
        need(type(raw) is bytes and raw and (name not in guarded or guarded[name] != raw),
             'changed diagnostic source body required: ' + name)
        compile(raw, name, 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    changed = {**guarded, **overlay}
    release, count = re.subn(rb"(?m)^REVIEWED_ENVIRONMENT_SHA256 = '[0-9a-f]{64}'$",
        ("REVIEWED_ENVIRONMENT_SHA256 = '" + sha(environment) + "'").encode(), guarded['owned_runtime/release.py'])
    need(count == 1, 'one derived environment pin')
    normalized, count = re.subn(rb"(?m)^NORMALIZED_SOURCE_CONTRACT_SHA256 = '[0-9a-f]{64}'$",
        b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None', release)
    need(count == 1, 'one derived normalized source pin')
    changed['owned_runtime/release.py'] = normalized
    normalized_sha = sha(canonical(sorted((n, sha(b)) for n, b in changed.items())))
    changed['owned_runtime/release.py'] = normalized.replace(b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None',
        ("NORMALIZED_SOURCE_CONTRACT_SHA256 = '" + normalized_sha + "'").encode(), 1)
    need(set(changed) == set(source) | {'rl_session/numeric_shadow.py'} and len(changed) == 260,
         'exact source members after diagnostic overlay')
    need({n for n in source if source[n] != changed[n]} ==
         (RUNTIME_TARGETS - {'rl_session/numeric_shadow.py'}) | {'owned_runtime/parent_scoring.py', 'owned_runtime/release.py'},
         'diagnostic delta exceeds exact targets')
    need(all(changed[n] == source[n] for n in source if n.startswith('baseline/')),
         'all consumed baseline bytes retained')
    builder = s.dependency(TOOL / 'prepare_successor_release.py', s.ASSEMBLER_SHA, 'numeric_archive_primitives')
    return changed, builder.zip_blobs(changed, stored=True), normalized_sha


def diagnostic_deployment(original):
    result = repaired_preparation(original)
    need(sha(result['parent_entry.py']) == BASE_PARENT_ENTRY_SHA, 'frozen installed parent entry required')
    result['parent_entry.py'] = read(HERE / 'deployment/parent_entry.py')
    replacements = {'notebook_builder.py': ((s.RUN, RUN), (s.SOURCE, SOURCE)),
        'launch_notebook.py': ((s.ENV, ENV),), 'prepare_entry.py': ((s.RUN, RUN), (s.ENV, ENV))}
    for name, pairs in replacements.items():
        for before, after in pairs:
            result[name] = s.replace(result[name], before, after)
    for name, raw in result.items():
        compile(raw, name, 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    need(set(result) == set(original), 'unchanged deployment member set')
    return result


def diagnostic_wrapper():
    # Authentication proves which existing proof checker this successor extends.
    pinned(TOOL / 'wrapper_observation_repair/verify_parent_wrappers.py', BASE_WRAPPER_SHA)
    raw = read(HERE / 'assembly/verify_parent_wrappers.py')
    compile(raw, 'verify_parent_wrappers.py', 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    return raw


def publication_helpers(source_sha, archive_sha):
    """Bind the fixed transport/wire successor; stale runtime pins stop assembly."""
    operator = TOOL / 'publication_windows_bridge_20261015'
    result = {name: read(HERE / 'publication' / name) for name in ('rl_transport.py', 'verify_active_wire.py')}
    # Do not demand historical run008 bytes at the current operator path. The
    # reviewed diagnostic body itself is the fixed behavioral baseline; only
    # one common dependency literal is normalized for that identity check.
    normalized, count = re.subn(rb"(?m)^COMMON_SOURCE_SHA256 = '[0-9a-f]{64}'$",
        ("COMMON_SOURCE_SHA256 = '" + PUBLISHED_COMMON_SHA + "'").encode(), result['rl_transport.py'])
    need(count == 1 and sha(normalized) == PUBLISHED_TRANSPORT_SHA,
         'reviewed numeric transport behavior changed')
    need(sha(result['verify_active_wire.py']) == PUBLISHED_ACTIVE_WIRE_SHA,
         'reviewed numeric active wire changed')
    expected = {'rl_transport.py': {'RUN_PATH': RUN, 'SOURCE_PATH': SOURCE, 'ENVIRONMENT_PATH': ENV,
                                  'RUN_PURPOSE': RUN_PURPOSE, 'FORMAT': FORMAT,
                                  'COMMON_SOURCE_SHA256': sha(read(operator / 'operator_common.py'))},
        'verify_active_wire.py': {'SOURCE': source_sha, 'ARCHIVE': archive_sha,
                                 'RUN': RUN, 'SOURCE_ROOT': SOURCE, 'RUN_PURPOSE': RUN_PURPOSE}}
    for name, raw in result.items():
        tree = ast.parse(raw, filename=name)
        for key, value in expected[name].items():
            assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == key for t in n.targets)]
            need(len(assignments) == 1 and ast.literal_eval(assignments[0].value) == value,
                 'fixed publication helper pin differs: ' + name + ':' + key)
        need(read(operator / name) == raw, 'integrated operator helper differs: ' + name)
        compile(raw, name, 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    return result


def assemble(*, repository_root, source_proposal_root, base_root, observation_root, observation_sha,
             owner_direction_path, owner_direction_sha, collector_path, collector_sha, output_root, mode='proposal',
             proposal_path=None, proposal_sha=None, solver_review_path=None, solver_review_sha=None,
             runtime_review_path=None, runtime_review_sha=None, material_review_path=None, material_review_sha=None):
    need(mode in ('proposal', 'final'), 'explicit proposal or final mode')
    output = output_path(repository_root, output_root)
    for original in (source_proposal_root, base_root, observation_root, owner_direction_path, collector_path):
        original = p.ordinary(original)
        need(not output.is_relative_to(original) and not original.is_relative_to(output), 'input/output overlap')
    original = s.closed(source_proposal_root, 'ASSEMBLY-INVENTORY.json', PROPOSAL_INVENTORY_SHA)
    base = s.closed(base_root, 'ASSEMBLY-INVENTORY.json', s.BASE_INVENTORY)
    inherited = obj(original['ASSEMBLY-PROPOSAL.json'])
    need(inherited['source_sha256'] == ORIGINAL_SOURCE_SHA and inherited['source_archive_sha256'] == ORIGINAL_ARCHIVE_SHA
         and inherited['proposed_code_version'] is None and inherited['publication_admitted'] is False,
         'exact independently reviewed inert source')
    observation, observed_files = observation_inputs(observation_root, observation_sha)
    owner, owner_raw = owner_inputs(owner_direction_path, owner_direction_sha)
    collector = pinned(collector_path, collector_sha)
    need(collector == read(HERE / 'publication/rl_collect.py'), 'exact diagnostic collector successor required')
    compile(collector, str(collector_path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
    versions = {'code_predecessor': observation['code_version'], 'code': observation['code_version'] + 1,
        'notebook_predecessor': observation['notebook_version'], 'inactive': observation['notebook_version'] + 1,
        'active': observation['notebook_version'] + 2}
    reference = DREF + '/' + str(versions['code'])
    deployment = {n.removeprefix('code-payload/deployment/'): b for n, b in original.items() if n.startswith('code-payload/deployment/')}
    deployment['source_loader.py'] = s.replace(deployment['source_loader.py'], s.UNBOUND_REFERENCE, reference)
    deployment = diagnostic_deployment(deployment)
    source = {n.removeprefix('producer-source/'): b for n, b in original.items() if n.startswith('producer-source/')}
    need(len(source) == 259 and sha(canonical(sorted((n, sha(b)) for n, b in source.items()))) == ORIGINAL_SOURCE_SHA,
         'exact consumed runtime259')
    need(sha(original['code-payload/source.zip']) == ORIGINAL_ARCHIVE_SHA, 'exact consumed source archive')
    original_source = dict(source)
    environment = projected_environment(original['consumer-release/environment.json'])
    overlay = runtime_overlay()
    source, archive, normalized_sha = diagnostic_runtime(source, original['consumer-release/environment.json'], environment, overlay)
    source_sha = sha(canonical(sorted((n, sha(b)) for n, b in source.items())))
    archive_sha = sha(archive)
    wrapper = diagnostic_wrapper()
    publication_sources = publication_helpers(source_sha, archive_sha)
    old_material = obj(base['consumer-release/material_review.json'])
    old_solver = s.pinned(Path(base_root).parent / 'source-rebuild/review-only/solver-descriptor.json', old_material['dataset_file_sha256'])
    need(s.solver_projection(old_solver, old_material) == original['review-only/solver-descriptor.json'],
         'authentic consumed two-path solver projection')
    solver = diagnostic_solver(old_solver, old_material)
    prior, release = obj(base['publication-manifest.json']), obj(original['notebook-release.json'])
    proposal = {'format': PROPOSAL_FORMAT, 'status': 'INDEPENDENT_REVIEW_REQUIRED',
        'source_sha256': source_sha, 'source_archive_sha256': archive_sha,
        **{key: inherited[key] for key in ('phase_policy_sha256',
            'scorer_pins_sha256', 'loader_overlay_manifest_sha256', 'loader_overlay_review_sha256')},
        'environment_sha256': sha(environment), 'normalized_source_contract_sha256': normalized_sha,
        'run_purpose': RUN_PURPOSE, 'numeric_overlay_inventory': {n: desc(b) for n, b in sorted(overlay.items())},
        'parent_wrapper_verifier_sha256': sha(wrapper),
        'publication_helper_inventory': {n: desc(b) for n, b in sorted(publication_sources.items())},
        'dataset_file_sha256': sha(solver), 'dataset_escrow_sha256': old_material['dataset_escrow_sha256'],
        'deployment_inventory': {n: desc(b) for n, b in sorted(deployment.items())},
        'collector_sha256': collector_sha, 'consumer_helper_inventory_sha256': sha(original['terminal-consumer/CONSUMER-INVENTORY.json']),
        'current_predecessor_observation_sha256': observation_sha, 'owner_direction_sha256': owner_direction_sha,
        'versions': versions, 'assembler_source_sha256': sha(read(HERE / 'assemble.py')),
        'source_proposal_inventory_sha256': PROPOSAL_INVENTORY_SHA, 'historical_candidate_inventory_sha256': s.BASE_INVENTORY,
        'namespaces': {'run': RUN, 'source': SOURCE, 'environment': ENV}, 'runtime_delta': {name: {**row, 'new': desc(source[name])}
            for name, row in inherited['runtime_delta'].items()},
        'diagnostic_successor_delta': {name: {'old': desc(original_source[name]) if name in original_source else None, 'new': desc(source[name])}
            for name in source if name not in original_source or source[name] != original_source[name]},
        'source_members': len(source), 'unchanged_consumed_source_members': sum(source[n] == original_source[n] for n in original_source),
        'original_planned_attempts': 256, 'requested_attempts': 64, 'unrequested_original_panel_attempts': 192,
        'training_only': True, 'rl_optimizer_commit_authorized': False, 'later_B_C_dev_holdout_PUBLIC_authorized': False,
        'baseline_unchanged_members': 199, 'consumer_helper_members': 21,
        'dataset_content_sha256': old_material['dataset_content_sha256'], 'production_GPU_validation_passed': False,
        'evaluator_bodies_semantically_parsed': False, 'provider_calls': 0, 'model_or_GPU_calls': 0,
        'successor_epoch': None, 'session_seconds': 43200, 'maximum_dispatch_age_seconds': 60,
        'provider_versions_reserved': False, 'final_operator_review_required': True,
        'numeric_mount_and_inactive_readback_before_active_dispatch': True,
        'historical_run007_clock': {'epoch': 1791908053, 'deadline': 1791951253}}
    approved = mode == 'final'
    if approved:
        solver_raw, runtime_raw, material_raw = review_inputs(proposal, proposal_path=proposal_path, proposal_sha=proposal_sha,
            solver_review_path=solver_review_path, solver_review_sha=solver_review_sha,
            runtime_review_path=runtime_review_path, runtime_review_sha=runtime_review_sha,
            material_review_path=material_review_path, material_review_sha=material_review_sha,
            original_solver=old_solver, new_solver=solver)
    else:
        pending = {'format': 'irisx/numeric-diagnostic-review-requirements-v1', 'status': 'REVIEW_REQUIRED',
            'proposal_sha256': sha(encoded(proposal)), **{k: proposal[k] for k in BINDING_KEYS},
            'production_GPU_validation_passed': False, 'baseline_unchanged_members': 199}
        runtime_raw = encoded({**pending, 'review_kind': 'runtime'})
        material_raw = encoded({**pending, 'review_kind': 'material', 'dataset_content_sha256': None})
        solver_raw = encoded({'format': 'irisx/numeric-diagnostic-solver-projection-v1',
            'status': 'INDEPENDENT_REVIEW_REQUIRED', 'original_sha256': sha(old_solver),
            'projected_sha256': sha(solver), 'path_substitutions': 2, 'reverse_byte_equality': True,
            'escrow_bodies_read': False, 'production_admitted': False})
    auxiliary = {'NOTICE.txt': original['code-payload/NOTICE.txt'], 'release/RUNTIME-REVIEW.json': runtime_raw,
        'release/MATERIAL-REVIEW.json': material_raw, 'release/REVIEWED-ENVIRONMENT.json': environment,
        **{'deployment/' + n: b for n, b in deployment.items()}}
    manifest = {'format': 'irisx/rlvr-code-material-v1', 'reference': reference,
        'source': {'archive': {'name': 'source.zip', **desc(archive)}, 'source_sha256': source_sha,
                   'files': {n: desc(b) for n, b in sorted(source.items())}},
        'auxiliary_files': {n: desc(b) for n, b in sorted(auxiliary.items())}}
    payload = {**auxiliary, 'manifest.json': encoded(manifest), 'source.zip': archive}
    release.update(production_admitted=approved, code_reference=reference, code_manifest_sha256=sha(payload['manifest.json']),
        source_sha256=source_sha, source_archive_sha256=archive_sha,
        material_review_sha256=sha(material_raw), deployment=proposal['deployment_inventory'],
        original_owner_request={key: owner[key] for key in ('owner_id', 'request_id', 'instruction')},
        admission_scope='TRAINING_ONLY_NUMERIC_DIAGNOSTIC; numeric mount, inactive readback and separate publisher/wire review required' if approved else 'INERT_NUMERIC_DIAGNOSTIC_ADMISSION_PROPOSAL')
    release['dataset_references'][0] = reference
    release['run_purpose'] = RUN_PURPOSE
    release['environment_sha256'] = sha(environment)
    release['storage']['environment_root'] = ENV
    need(release['dataset_references'][1:] == obj(original['notebook-release.json'])['dataset_references'][1:],
         'all seven original non-code dataset pins retained')
    release['storage']['observed_assembled_source_copy_bytes'] = sum(map(len, source.values())) + len(payload['source.zip']) + sum(map(len, auxiliary.values()))
    need(release['storage']['observed_assembled_source_copy_bytes'] + 80 * 1024**2 < 128 * 1024**2, 'source/proof/log reservation exceeded')
    files = {'code-payload/' + n: b for n, b in payload.items()}
    files.update({'producer-source/' + n: b for n, b in source.items()})
    # All original evidence is retained byte-for-byte, never relabelled as run008.
    for name, raw in base.items():
        if name == 'PREDECESSOR-EVIDENCE.json' or name.startswith(('predecessor-v33/', 'historical-v31/', 'current-predecessor-v35-launch/', 'current-predecessor-v37-launch/')):
            files[name] = raw
    for name in ('verify_v35_lineage.py', 'verify_run006_lineage.py'):
        files['assembly/' + name] = base['assembly/' + name]
    for name in ('finalize.py', 'accept_downloaded_mount.py'):
        files['assembly/' + name] = original['assembly/' + name]
    files['assembly/verify_parent_wrappers.py'] = wrapper
    files.update({'review-only/publication/' + n: b for n, b in publication_sources.items()})
    files['review-only/publication/rl_collect.py'] = collector
    files.update(observed_files)
    files['OWNER-DIRECTION.json'] = owner_raw
    files['notebook-release.json'] = encoded(release)
    for key in ('phase_policy', 'owner_protocol'):
        files['consumer-release/' + key + '.json'] = original['consumer-release/' + key + '.json']
    files['consumer-release/environment.json'] = environment
    files['consumer-release/material_review.json'] = material_raw
    independent = encoded({'format': 'owned-rl-independent-release-v1', 'source_sha256': source_sha,
        **{k + '_sha256': sha(files['consumer-release/' + k + '.json']) for k in ('material_review', 'environment', 'phase_policy', 'owner_protocol')}})
    files['consumer-release/release.json'] = independent
    consumers = {n.removeprefix('terminal-consumer/'): b for n, b in original.items() if n.startswith('terminal-consumer/')}
    operator = obj(consumers['CONSUMER-OPERATOR.json'])
    operator.update(source_sha256=source_sha, source_archive_sha256=archive_sha,
                    release_sha256=sha(independent), collector_entry_sha256=collector_sha if approved else None)
    consumers['CONSUMER-OPERATOR.json'] = encoded(operator)
    if approved:
        consumers['reviewed_entry.py'] = s.replace(consumers['reviewed_entry.py'], 'REVIEWED_OPERATOR_PINS_SHA256 = None',
            'REVIEWED_OPERATOR_PINS_SHA256 = ' + repr(sha(consumers['CONSUMER-OPERATOR.json'])))
    files.update({'terminal-consumer/' + n: b for n, b in consumers.items()})
    assembler = s.dependency(TOOL / 'prepare_successor_release.py', s.ASSEMBLER_SHA, 'run008_archive_primitives')
    files['code-upload.zip'] = assembler.zip_blobs(payload)
    files['SOURCE-INVENTORY.json'] = encoded({'format': 'irisx/numeric-diagnostic-source-inventory-v1', 'source_sha256': source_sha,
        'source_archive_sha256': archive_sha, 'files': {n: sha(b) for n, b in sorted(source.items())}, 'source_members': len(source),
        'unchanged_baseline_members': 199, 'original_baseline200_exact': False})
    files['SOURCE-FREEZE.json'] = encoded({'format': 'irisx/rlvr-source-freeze-v1', 'source_sha256': source_sha,
        'source_archive_sha256': archive_sha, 'source_members': len(source), 'files': manifest['source']['files'],
        'original_baseline200_exact': False, 'unchanged_baseline_members': 199,
        'producer_inventory_artifact_sha256': sha(files['SOURCE-INVENTORY.json']),
        'self_consistency_pins': {'NORMALIZED_SOURCE_CONTRACT_SHA256': proposal['normalized_source_contract_sha256'],
            'FINAL_V25_POLICY_SHA256': proposal['phase_policy_sha256'], 'REVIEWED_ENVIRONMENT_SHA256': proposal['environment_sha256']},
        'independent_approval_is_external': True})
    builder = p.load_module(deployment['notebook_builder.py'], 'run008_numeric_builder', output / 'code-payload/deployment/notebook_builder.py')
    notebooks = []
    for old_row in prior['notebooks']:
        row = copy.deepcopy(old_row)
        active = row['role'] == 'rlvr004'
        name = 'numeric-diagnostic-active-template.ipynb' if active else 'numeric-diagnostic-inactive.ipynb'
        raw = encoded(builder.build(release, deployment['source_loader.py'].decode(), kind='active-template' if active else 'inactive'))
        files[name] = raw
        row.update(path=name, bytes=len(raw), sha256=sha(raw), expected_predecessor_version=versions['inactive'] if active else versions['notebook_predecessor'],
            expected_version=versions['active'] if active else versions['inactive'], run_authorized=approved and active,
            predecessor_source_sha256=None if active else observation['saved_source_sha256'], dataset_sources=release['dataset_references'],
            output_root=RUN, source_parent=SOURCE)
        notebooks.append(row)
    upload = [descriptor(raw, name) for name, raw in sorted(payload.items())]
    material_rows = [row for row in upload if row['path'] != 'source.zip']
    dataset = copy.deepcopy(prior['datasets'][0])
    dataset.update(expected_predecessor_version=versions['code_predecessor'], expected_version=versions['code'],
        root_manifest={'path': 'manifest.json', 'sha256': sha(payload['manifest.json'])}, upload_inventory=upload,
        upload_inventory_sha256=sha(canonical(upload) + b'\n'), transport_archive=descriptor(files['code-upload.zip'], 'code-upload.zip'),
        version_notes='Training-only numeric diagnostic: SFT256 A and original first64 batch; no RL commit or later B/C/dev/holdout/PUBLIC. Exact cuDNN/material/process/numeric/12h gates retained; no scientific success claim.',
        expected_readback_layouts={'original-upload': upload,
            'extracted-root': sorted(material_rows + [descriptor(b, n) for n, b in source.items()], key=lambda r: r['path']),
            'extracted-source-directory': sorted(material_rows + [descriptor(b, 'source/' + n) for n, b in source.items()], key=lambda r: r['path'])})
    publication = copy.deepcopy(prior)
    publication.update(format=FORMAT, run_purpose=RUN_PURPOSE, datasets=[dataset], notebooks=notebooks,
        source_review_only=not approved, run_authorized=approved, release_runtime_finalized=approved,
        source_freeze_sha256=sha(files['SOURCE-FREEZE.json']), runtime_source_sha256=source_sha, source_identity_sha256=source_sha,
        runtime_source_approval=descriptor(runtime_raw, 'code-payload/release/RUNTIME-REVIEW.json'),
        current_predecessor_observation=descriptor(observed_files['current-predecessor/OBSERVATION.json'], 'current-predecessor/OBSERVATION.json'),
        owner_session_stop_attestation=descriptor(owner_raw, 'OWNER-DIRECTION.json'),
        parent_wrapper_verifier=descriptor(files['assembly/verify_parent_wrappers.py'], 'assembly/verify_parent_wrappers.py'),
        no_model_mount_acceptance_helper=descriptor(files['assembly/accept_downloaded_mount.py'], 'assembly/accept_downloaded_mount.py'),
        local_reconstruction={'status': 'NATIVE_NUMERIC_DIAGNOSTIC_REVIEWED' if approved else 'NATIVE_NUMERIC_DIAGNOSTIC_REVIEW_REQUIRED',
            'assembler_source_sha256': proposal['assembler_source_sha256'], 'versions': versions,
            'stop_after_submit_readback': False, 'provider_monitoring_authorized': True, 'exact_output_retrieval_authorized': True,
            'additional_gpu_runs_authorized': False},
        admission_proposal_sha256=sha(encoded(proposal)), dispatch_ready=False, provider_publication_completed=False)
    publication['jit']['entry'] = descriptor(files['assembly/finalize.py'], 'assembly/finalize.py')
    publication['jit']['dependencies'] = [descriptor(files[name], name) for name in ('notebook-release.json',
        'code-payload/deployment/notebook_builder.py', 'code-payload/deployment/source_loader.py')]
    publication['consumer_contract'].update(source_sha256=source_sha, dataset_sha256=sha(solver),
        source_archive=descriptor(payload['source.zip'], 'code-payload/source.zip'),
        review_input_paths={'environment': SOURCE + '/release/REVIEWED-ENVIRONMENT.json', 'phase_policy': SOURCE + '/runtime/design/MEASURED-POLICY.json'},
        **{key: descriptor(files['consumer-release/' + key + '.json'], 'consumer-release/' + key + '.json') for key in
           ('release', 'material_review', 'environment', 'phase_policy', 'owner_protocol')})
    prefix = Path(RUN).name
    publication['terminal_contract'].update(evidence_path=prefix + '.evidence.zip', terminal_path=prefix + '.evidence.zip.terminal.json',
        checkpoint_path=prefix + '/checkpoints.zip', launcher_path=prefix + '-launcher', storage=release['storage'])
    files['publication-manifest.json'] = encoded(publication)
    files['ADMISSION-PROPOSAL.json'] = encoded(proposal)
    files['review-only/solver-descriptor.json'] = solver
    files['review/SOLVER-NAMESPACE-REVIEW.json'] = solver_raw
    files['ASSEMBLY-INVENTORY.json'] = encoded({n: desc(b) for n, b in sorted(files.items())})
    s.write_output(output, files)
    return {'status': 'INDEPENDENTLY_REVIEWED_LOCAL_CANDIDATE' if approved else 'INERT_FULL_ASSEMBLY_PROPOSAL',
        'output_root': str(output), 'proposal_sha256': sha(files['ADMISSION-PROPOSAL.json']),
        'publication_manifest_sha256': sha(files['publication-manifest.json']), 'assembly_inventory_sha256': sha(files['ASSEMBLY-INVENTORY.json']),
        'versions': versions, 'source_sha256': source_sha, 'source_archive_sha256': archive_sha,
        'successor_epoch': None, 'provider_calls': 0, 'model_or_GPU_calls': 0, 'scientific_result': None,
        'numeric_mount_inactive_readback_and_final_operator_review_required': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('proposal', 'final'), required=True)
    for name in ('repository-root', 'source-proposal-root', 'base-root', 'observation-root', 'observation-sha',
                 'owner-direction-path', 'owner-direction-sha', 'collector-path', 'collector-sha', 'output-root'):
        parser.add_argument('--' + name, required=True)
    for name in ('proposal-path', 'proposal-sha', 'solver-review-path', 'solver-review-sha',
                 'runtime-review-path', 'runtime-review-sha', 'material-review-path', 'material-review-sha'):
        parser.add_argument('--' + name)
    print(encoded(assemble(**vars(parser.parse_args()))).decode(), end='')


if __name__ == '__main__':
    main()
