"""Local reconstruction of deterministic, non-admitting successor preparation. No provider I/O.

This tool authenticates its frozen inputs against the owner's exact Git snapshot,
reconstructs code18, then projects only a fresh namespace and reviewed diagnostic
overlays. It cannot finalize, publish, dispatch, renew an epoch, or approve itself.
Authentic predecessor evidence remains mandatory for a separate final assembler.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import types

HERE = Path(__file__).absolute().parent
TOOL_REL = 'tools/arc_qwen_rlvr004_20261013'
SNAPSHOT = 'e951604b829497e81bc6e18b32662ff050bd54db'
TREE = 'f9b10d12b912f3a92238375451c0ad56d4cb7efb'
RUNTIME_COMMIT = 'dbf21033b41aff9327cf4f91159df0133529f176'
SOURCE_SHA = '4050616ed0ed34d19501be416650a09ae5cc9c86c875b349a056baec9308f3e3'
ARCHIVE_SHA = '22fc93ae1dfbc4d4a7c90cf9907668af5d697dece28cb9211dea82c776d7dc9e'
ENVIRONMENT_SHA = '0f7133bdb22d8cba124537622ab09a98e9450e1649df1b07d4e6661d48e33e28'
CODE18_ASSEMBLY_SHA = 'de68ffa281990b844e41ea41d11357b2214a973048cd8e14ae64cab39159a5a0'
CODE18_MANIFEST_SHA = '76b2e004770e1f41e9c2352fa9817bc185ea5fded75d9fd8ce29d50453e7b7ca'
SOLVER_SHA = '4c13f788cabe2213002593991cffcc15ffdcd6c04167967cbb9d2532536b5f47'
OLD_RUN = '/kaggle/working/irisx-qwen14b-rlvr-20261012-run005'
OLD_SOURCE = '/kaggle/working/irisx-qwen14b-rlvr-20261012-source005'
OLD_ENVIRONMENT = '/tmp/irisx-qwen14b-rlvr-20261012-environment005'
OLD_EPOCH = 1791871874
OLD_DEADLINE = 1791915074
INSTALLER_TARGET = 'baseline/tools/arc_qwen_transfer_deployment_20261012/bootstrap.py'
INSTALLER_ORIGINAL_SHA = '4ddac4166b154e1506fb029373b14297f7b0bfc7c87f37d9e83bcb9f554909f8'
OVERLAYS = {
    'launch_notebook.py': '6c85b8e1b3b3cc9b655816566d8338acb57dd0b9423a4e1fe7dd3a11cd8f2376',
    'prepare_entry.py': '2e66d6952aac1315cb3ce79e879782497dba2f9a2465b3ce672278dd7696e584',
    'rl_collect.py': 'a18d06489754eef08490fb3eb070161fd13d3ffeea47af612d9ac5250213abab',
}
CAP = 128 * 1024**2


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def relative(name):
    need(type(name) is str and name and '\\' not in name and ':' not in name
         and all(ord(c) >= 32 and ord(c) != 127 for c in name), 'unsafe relative name')
    path = PurePosixPath(name)
    need(bool(path.parts) and not path.is_absolute() and str(path) == name
         and all(p not in ('', '.', '..') for p in path.parts), 'unsafe relative name')
    return name


def ordinary(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400, 'linked or reparse path')
    return path


def read(path, cap=CAP):
    path = ordinary(path)
    # lstat/open/fstat checks ensure a static symlink, FIFO or hardlink fails before
    # its body is read. This local builder is not a hostile same-UID sandbox.
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap, 'bounded regular input')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        need((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), 'input replaced')
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
    need(signature(before) == signature(after) == signature(path.lstat()) and len(raw) == before.st_size, 'input changed')
    return raw


def obj(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def finite_float(token):
        value = float(token)
        need(math.isfinite(value), 'nonfinite JSON')
        return value
    value = json.loads(raw, object_pairs_hook=pairs, parse_float=finite_float,
                       parse_constant=lambda _: need(False, 'nonfinite JSON'))
    need(type(value) is dict, 'JSON object required')
    return value


def desc(raw):
    return {'bytes': len(raw), 'sha256': sha(raw)}


def load_module(raw, name, path):
    result = types.ModuleType(name)
    result.__file__ = str(path)
    result.__package__ = ''
    sys.modules[name] = result
    exec(compile(raw, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize), vars(result))
    return result


class Snapshot:
    """Read only byte-authenticated source paths from the exact frozen tree."""
    def __init__(self, repository_root):
        self.root = ordinary(repository_root)
        need(self.root.is_dir(), 'repository root missing')
        def git(*args):
            proc = subprocess.run(['git', '-C', str(self.root), *args], check=True,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            return proc.stdout
        commit = git('cat-file', '-p', SNAPSHOT)
        need(commit.startswith(('tree ' + TREE + '\n').encode()), 'exact snapshot tree required')
        entries = git('ls-tree', '-rz', '--full-tree', SNAPSHOT)
        self.paths = {}
        for row in entries.rstrip(b'\0').split(b'\0'):
            meta, path = row.split(b'\t', 1)
            mode, kind, blob = meta.decode().split()
            need(kind == 'blob' and mode in ('100644', '100755'), 'frozen regular source tree required')
            self.paths[relative(path.decode())] = blob
        need(len(self.paths) == 2558, 'complete frozen snapshot tree required')
        self.inputs = {}

    def read(self, name):
        name = relative(name)
        need(name in self.paths, 'input not in frozen snapshot: ' + name)
        raw = read(self.root / name)
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        need(blob == self.paths[name], 'frozen input changed: ' + name)
        self.inputs[name] = desc(raw)
        return raw

    def tool(self, name):
        return self.read(TOOL_REL + '/' + relative(name))


def identity(raw):
    document = obj(raw)
    need(set(document) == {'format', 'status', 'run_id', 'versions'}, 'identity schema')
    need(document['format'] == 'irisx/preparation-successor-proposed-identity-v1'
         and document['status'] == 'PROPOSED_NOT_PROVIDER_RESERVED', 'proposal identity only')
    run_id = document['run_id']
    need(type(run_id) is str and re.fullmatch(r'irisx-qwen14b-rlvr-20261013-run00[6-9]', run_id), 'fresh successor namespace required')
    versions = document['versions']
    need(type(versions) is dict and set(versions) == {'code_predecessor', 'code', 'notebook_predecessor', 'inactive', 'active'}, 'version schema')
    need(all(type(v) is int for v in versions.values()), 'integer versions required')
    # A newer predecessor is a different source/evidence task, never silently
    # reinterpreted by this code18-specific assembler.
    need(versions['code_predecessor'] >= 18 and versions['notebook_predecessor'] >= 35
         and versions['code'] == versions['code_predecessor'] + 1
         and versions['inactive'] == versions['notebook_predecessor'] + 1
         and versions['active'] == versions['inactive'] + 1, 'fresh consecutive live successor allocation required')
    return document


def namespaces(document):
    run_id = document['run_id']
    return {'run': '/kaggle/working/' + run_id,
            'source': '/kaggle/working/' + run_id.replace('-run', '-source'),
            'environment': '/tmp/' + run_id.replace('-run', '-environment')}


def exact_replace(raw, before, after, count=1):
    before, after = before.encode(), after.encode()
    need(before != after and raw.count(before) == count, 'exact namespace occurrence: ' + before.decode())
    result = raw.replace(before, after)
    need(result.replace(after, before) == raw, 'namespace reverse byte equality')
    return result


def frozen_runtime(snapshot, assembler):
    mapping = obj(snapshot.tool('driver_path_repair/runtime-path-map-run005.json'))
    need(mapping['source_sha256'] == SOURCE_SHA and mapping['source_archive_sha256'] == ARCHIVE_SHA, 'code18 map binding')
    files = {}
    for name, row in mapping['files'].items():
        relative(name)
        raw = snapshot.read(row['repository_path'])
        need(desc(raw) == {k: row[k] for k in ('bytes', 'sha256')}, 'mapped member binding')
        files[name] = raw
    need(len(files) == 259 and sum(n.startswith('baseline/') for n in files) == 200, 'source member closure')
    need(sha(canonical(sorted((n, sha(b)) for n, b in files.items()))) == SOURCE_SHA, 'code18 logical source')
    need(sha(assembler.zip_blobs(files, stored=True)) == ARCHIVE_SHA, 'exact code18 source archive')
    return files


def installer_overlay(old, *, overlay_path=None, overlay_sha=None, review_path=None, review_sha=None):
    """Optional exact-target local review input, never a production capability."""
    provided = (overlay_path, overlay_sha, review_path, review_sha)
    if not any(provided):
        return None
    need(all(provided), 'installer overlay and independently hash-bound review required')
    need(all(type(value) is str and re.fullmatch('[0-9a-f]{64}', value)
             for value in (overlay_sha, review_sha)), 'installer overlay review digests')
    raw, review_raw = read(overlay_path), read(review_path, 1024 * 1024)
    need(sha(raw) == overlay_sha and sha(review_raw) == review_sha, 'installer overlay or review hash mismatch')
    review = obj(review_raw)
    need(review.get('format') == 'irisx/bounded-installer-log-review-v1' and review.get('status') == 'PASS'
         and review.get('scope') == 'LOCAL_SOURCE_REVIEW_ONLY', 'independent local installer review required')
    need(review.get('target') == INSTALLER_TARGET and review.get('original_bootstrap_sha256') == INSTALLER_ORIGINAL_SHA
         and review.get('overlay_sha256') == overlay_sha, 'installer exact target/review binding')
    need(sha(old[INSTALLER_TARGET]) == INSTALLER_ORIGINAL_SHA and raw != old[INSTALLER_TARGET], 'installer original or nonempty delta')
    compile(raw, INSTALLER_TARGET, 'exec')
    return {'raw': raw, 'review_raw': review_raw, 'review_sha256': review_sha, 'overlay_sha256': overlay_sha,
            'original_sha256': INSTALLER_ORIGINAL_SHA, 'target': INSTALLER_TARGET}


def project_runtime(old, environment, space, assembler, installer=None):
    need(sha(environment) == ENVIRONMENT_SHA, 'exact code18 environment')
    original = obj(environment)
    updated = copy.deepcopy(original)
    for key in ('contract_path', 'environment_lock_path', 'tokenizer_path'):
        value = updated['model_config'][key]
        need(value.startswith(OLD_SOURCE + '/runtime/'), 'old environment source path')
        updated['model_config'][key] = space['source'] + value[len(OLD_SOURCE):]
    projected = encoded(updated)
    reverse = obj(projected)
    for key in ('contract_path', 'environment_lock_path', 'tokenizer_path'):
        reverse['model_config'][key] = OLD_SOURCE + reverse['model_config'][key][len(space['source']):]
    need(encoded(reverse) == environment, 'environment changed beyond three source paths')
    files = dict(old)
    if installer is not None:
        files[INSTALLER_TARGET] = installer['raw']
    release, count = re.subn(rb"(?m)^REVIEWED_ENVIRONMENT_SHA256 = '[0-9a-f]{64}'$",
                           ("REVIEWED_ENVIRONMENT_SHA256 = '" + sha(projected) + "'").encode(), old['owned_runtime/release.py'])
    need(count == 1, 'one environment pin')
    normalized, count = re.subn(rb"(?m)^NORMALIZED_SOURCE_CONTRACT_SHA256 = '[0-9a-f]{64}'$",
                              b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None', release)
    need(count == 1, 'one normalized pin')
    files['owned_runtime/release.py'] = normalized
    normalized_sha = sha(canonical(sorted((n, sha(b)) for n, b in files.items())))
    files['owned_runtime/release.py'] = normalized.replace(b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None',
        ("NORMALIZED_SOURCE_CONTRACT_SHA256 = '" + normalized_sha + "'").encode(), 1)
    expected = {'owned_runtime/release.py'} | ({INSTALLER_TARGET} if installer is not None else set())
    need({n for n in files if files[n] != old[n]} == expected, 'runtime delta exceeds reviewed exact targets')
    compile(files['owned_runtime/release.py'], 'owned_runtime/release.py', 'exec')
    archive = assembler.zip_blobs(files, stored=True)
    return files, archive, projected, normalized_sha


def project_deployment(snapshot, assembler, overlay_root, space, document):
    declared = obj(snapshot.tool('release/notebook-release.json'))['deployment']
    base = {}
    for name in assembler.DEPLOYMENT_NAMES:
        raw = snapshot.tool('support/deployment/' + name)
        need(desc(raw) == declared[name], 'code17 deployment binding')
        base['code-payload/deployment/' + name] = raw
    base['assembly/verify_parent_wrappers.py'] = snapshot.tool('support/assembly/verify_parent_wrappers.py')
    predecessor, wrappers = assembler.derive_deployment(base)
    frozen = {n: desc(b) for n, b in predecessor.items()}
    overlays = {}
    for name, expected in OVERLAYS.items():
        raw = read(overlay_root / name)
        need(sha(raw) == expected, 'independently reviewed diagnostic overlay changed: ' + name)
        overlays[name] = raw
    deployment = dict(predecessor)
    deployment.update({n: overlays[n] for n in ('launch_notebook.py', 'prepare_entry.py')})
    deployment['source_loader.py'] = exact_replace(deployment['source_loader.py'], assembler.DREF + '/18', assembler.DREF + '/' + str(document['versions']['code']))
    for old, new in ((OLD_RUN, space['run']), (OLD_SOURCE, space['source'])):
        deployment['notebook_builder.py'] = exact_replace(deployment['notebook_builder.py'], old, new)
    deployment['launch_notebook.py'] = exact_replace(deployment['launch_notebook.py'], OLD_ENVIRONMENT, space['environment'])
    deployment['launch_notebook.py'] = exact_replace(deployment['launch_notebook.py'], 'exact run005/source005 paths required', 'exact fresh successor run/source paths required')
    for old, new in ((OLD_RUN, space['run']), (OLD_ENVIRONMENT, space['environment'])):
        deployment['prepare_entry.py'] = exact_replace(deployment['prepare_entry.py'], old, new)
    for old, new in ((OLD_RUN, space['run']), (OLD_SOURCE, space['source']), (OLD_ENVIRONMENT, space['environment'])):
        wrappers = exact_replace(wrappers, old, new)
    for name, raw in {**deployment, 'verify_parent_wrappers.py': wrappers}.items():
        compile(raw, name, 'exec')
        need(all(old.encode() not in raw for old in (OLD_RUN, OLD_SOURCE, OLD_ENVIRONMENT)), 'consumed absolute namespace leaked')
    return deployment, wrappers, overlays['rl_collect.py'], frozen


def project_solver(raw, space, old_material):
    """Project only an already-authenticated target-free descriptor, never ZIPs."""
    need(sha(raw) == SOLVER_SHA, 'authentic code18 target-free solver descriptor required')
    original = obj(raw)
    need(original.get('public_answers_read') is False and original.get('original_test_fields_retained') is False
         and original.get('cpu_fixture_only') is False, 'target-free authentic scope')
    need(original['denominators'] == {'dev': 16, 'holdout': 32, 'ttt_dev': 8, 'ttt_holdout': 8}, 'full training denominators')
    expected = copy.deepcopy(original)
    projected = raw
    for scope in ('dev', 'holdout'):
        before = original['escrow'][scope]['path']
        need(before.startswith(OLD_RUN + '/'), 'code18 escrow-reference path')
        need(original['escrow'][scope]['sha256'] == old_material['dataset_escrow_sha256'][scope], 'unchanged escrow hash')
        after = space['run'] + before[len(OLD_RUN):]
        expected['escrow'][scope]['path'] = after
        before_bytes, after_bytes = json.dumps(before, ensure_ascii=False).encode(), json.dumps(after, ensure_ascii=False).encode()
        need(projected.count(before_bytes) == 1, 'one escrow reference occurrence')
        projected = projected.replace(before_bytes, after_bytes, 1)
    need(obj(projected) == expected, 'solver semantic change beyond two paths')
    return projected


def requirements(snapshot):
    historical = obj(snapshot.tool('release/PREDECESSOR-EVIDENCE.json'))
    # These exact old files are a mandatory gate; documentation hashes are not
    # substitutes for their bodies. No archive member is read by this tool.
    rows = [{'group': 'historical_v31', 'role': role, 'required': True, **row}
            for role, row in sorted(historical['evidence'].items())]
    rows += [
        {'group': 'code17_assembly', 'path': 'ASSEMBLY-INVENTORY.json', 'sha256': '17b644b2d10dd134f00208d60529a59720fa8233fef46632f1e529a99784fa65', 'required': True, 'qualification': 'All 324 exact inventoried bodies and closed file set required.'},
        {'group': 'code18_assembly', 'path': 'ASSEMBLY-INVENTORY.json', 'sha256': CODE18_ASSEMBLY_SHA, 'required': True, 'qualification': 'Complete exact candidate including historical v31 and v33 proofs required.'},
        {'group': 'code18_assembly', 'path': 'publication-manifest.json', 'sha256': CODE18_MANIFEST_SHA, 'required': True},
        {'group': 'v33_evidence', 'path': 'RETRIEVAL-RECEIPT.json', 'sha256': '8f7446f1182bdeacba86e982793222203b948ab4dac6831b712a786fa3c29042', 'required': True, 'qualification': 'Every listed exact numeric33 selected output is required, not just the receipt.'},
        {'group': 'v33_evidence', 'path': 'TERMINAL-DIAGNOSTIC.json', 'sha256': '7e6161727accff39afaba37e75f1527db7a638098cbcb4f58d88e95fb7b0e8bc', 'required': True},
        {'group': 'v33_evidence', 'path': 'TERMINAL-CHECKPOINT.json', 'required': True},
        {'group': 'v33_evidence', 'path': 'downloads/irisx-qwen14b-rlvr-20261012-run004.evidence.zip', 'bytes': 15908385, 'sha256': '06825c68f991fd8e9b4f1a3cf76cf5e06fae18607918bf0840991f1a9a6591cd', 'required': True},
        {'group': 'target_free_solver', 'path': 'code18-solver-descriptor.json', 'sha256': SOLVER_SHA, 'required': True},
    ]
    for name in ('dataset-code-v17-receipt.json', 'notebook-rlvr004-receipt.json', 'notebook-rlvr004-journal.json',
                 'finalization.json', 'notebook-rlvr004-wire.json', 'notebook-rlvr004-saved.ipynb'):
        rows.append({'group': 'v33_state', 'path': name, 'required': True})
    for name in ('dataset-code-v18-receipt.json', 'notebook-rlvr004-receipt.json', 'notebook-rlvr004-journal.json',
                 'notebook-rlvr004.claim.json', 'finalization.json', 'notebook-rlvr004-wire.json', 'notebook-rlvr004-saved.ipynb'):
        row = {'group': 'v35_state', 'path': name, 'required': True}
        if name == 'notebook-rlvr004-saved.ipynb':
            row.update(bytes=21096, sha256='778c014ccea8b0f376d06afeeeceb318e50b3bce926ef13a6da068c9b3d5d917')
        rows.append(row)
    return {'format': 'irisx/preparation-successor-required-inputs-v1', 'production_admitted': False,
            'inputs': rows,
            'required_field_semantics': 'Each body is mandatory when its input group is used; this is not an AND over transfer layouts or alternative assembly routes.',
            'group_roles': {
                'code18_assembly': 'Preferred closed predecessor. Embeds original historical_v31, v33_state and v33_evidence bodies.',
                'code17_assembly': 'Alternative reconstruction input only. Not additionally required when intact code18 passes the unchanged validator.',
                'historical_v31': 'Mandatory original bodies, normally embedded in code18 or code17; no duplicate transfer required.',
                'v33_state': 'Mandatory original bodies, normally embedded in code18; separate root used only for alternative reconstruction.',
                'v33_evidence': 'Mandatory original bodies, normally embedded in code18; separate root used only for alternative reconstruction.',
                'v35_state': 'Consumed direct predecessor state; separate from historical evidence and never reconstructed from current metadata alone.',
                'target_free_solver': 'Authentic descriptor for separate two-path projection review; escrow answer bodies are not read.'},
            'satisfaction_routes': [
                'Preferred: intact authenticated code18 assembly embeds the mandatory original v31 and v33 evidence; no duplicate transfer is needed.',
                'Alternative reconstruction: intact code17 assembly plus original v33 state/evidence and independently reviewed run005 solver/material inputs.',
                'Rows describe required bytes in the applicable route, not a demand to supply duplicate evidence under every root.'],
            'other_mandatory_gates': [
                'Fresh source/status/settings provider bracket by sole publisher immediately before writes.',
                'Exact source-bound v35 terminal and manual-attempt diagnostics; unavailable remains unavailable.',
                'Authentic target-free two-path projection, separately independently reviewed.',
                'Separate hash-bound runtime, material, source, transport, collector and final-wire reviews.',
                'New final assembler and new operator contract retaining genuine historical predecessor validators.',
                'One fresh distinct dispatch identity and immutable predispatch epoch; no replay/reset of run005.',
                'Unchanged material/model/hardware, full167 scorer, scientific, process and 43200-second gates.'],
            'source_only_can_satisfy_production_admission': False}


def audit_inputs(snapshot, roots=None):
    """Inventory supplied local bodies without constructing or replacing proof.

    roots maps requirement group names to directories. No credentials, archive
    members, model or provider are accessed. Presence is never chain admission.
    """
    required = requirements(snapshot)
    roots = {} if roots is None else roots
    groups = {row['group'] for row in required['inputs']}
    need(type(roots) is dict and set(roots) <= groups, 'known input groups only')
    for group, path in roots.items():
        need(type(path) is str and Path(path).is_absolute(), 'absolute local input root required')
        ordinary(path)
    rows = []
    for row in required['inputs']:
        status = 'ROOT_NOT_SUPPLIED'
        actual = None
        if row['group'] in roots:
            path = Path(roots[row['group']]) / relative(row['path'])
            try:
                actual = desc(read(path))
            except FileNotFoundError:
                status = 'MISSING'
            except (OSError, ValueError):
                status = 'UNSAFE_OR_UNREADABLE'
            else:
                pins = {key: row[key] for key in ('bytes', 'sha256') if key in row}
                status = ('PRESENT_CHAIN_VERIFICATION_REQUIRED' if not pins else
                          'EXACT_BYTES_PRESENT' if all(actual[k] == v for k, v in pins.items()) else 'PIN_MISMATCH')
        rows.append({**row, 'local_status': status, 'observed': actual})
    return {'format': 'irisx/preparation-successor-local-input-audit-v1',
            'status': 'NON_ADMITTING_AVAILABILITY_ONLY', 'inputs': rows,
            'production_admitted': False, 'predecessor_chain_verified': False,
            'all_assembly_members_checked': False, 'provider_calls': 0,
            'qualification': 'Exact small descriptors cannot substitute for original referenced bodies or unchanged full admission validators.'}


def verify_code18_candidate(snapshot, root):
    """Strict offline check of an authentic old package, never a reconstruction.

    It invokes the byte-frozen run005 validator, including its v33 chain and all
    historical v31 evidence. Missing evidence fails; no preview or waiver exists.
    """
    root = ordinary(root)
    inventory_raw = read(root / 'ASSEMBLY-INVENTORY.json')
    need(sha(inventory_raw) == CODE18_ASSEMBLY_SHA, 'exact code18 assembly inventory required')
    inventory = obj(inventory_raw)
    actual = set()
    for path in root.rglob('*'):
        ordinary(path)
        info = path.lstat()
        need(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
             'closed code18 candidate contains special or hardlinked entry')
        if stat.S_ISREG(info.st_mode):
            actual.add(relative(path.relative_to(root).as_posix()))
    need(actual == set(inventory) | {'ASSEMBLY-INVENTORY.json'}, 'closed code18 assembly required')
    for name, row in inventory.items():
        need(desc(read(root / relative(name))) == row, 'code18 exact member: ' + name)
    need(sha(read(root / 'publication-manifest.json')) == CODE18_MANIFEST_SHA, 'exact code18 manifest required')
    for name in ('config.py', 'operator_common.py', 'rl_transport.py'):
        snapshot.tool('publication_run005/' + name)
    path = snapshot.root / TOOL_REL / 'publication_run005/rl_transport.py'
    transport = load_module(snapshot.tool('publication_run005/rl_transport.py'), 'preserved_run005_predecessor_validator', path)
    transport.contract(root / 'publication-manifest.json')
    return {'status': 'AUTHENTIC_CODE18_PREDECESSOR_GATE_PASSED', 'assembly_inventory_sha256': CODE18_ASSEMBLY_SHA,
            'publication_manifest_sha256': CODE18_MANIFEST_SHA, 'production_success': False,
            'successor_admitted': False, 'provider_calls': 0}


def prepare(*, repository_root, identity_path, output_root, solver_path=None,
            installer_overlay_path=None, installer_overlay_sha=None, installer_review_path=None, installer_review_sha=None):
    repository = ordinary(repository_root)
    output = ordinary(output_root)
    need(output.is_relative_to(repository / '.irisx') and output != repository / '.irisx', 'ignored local output required')
    need(not output.exists(), 'fresh output directory required')
    identity_raw = read(identity_path, 64 * 1024)
    document = identity(identity_raw)
    space = namespaces(document)
    snapshot = Snapshot(repository)
    assembler_path = repository / TOOL_REL / 'prepare_successor_release.py'
    assembler = load_module(snapshot.tool('prepare_successor_release.py'), 'frozen_run005_source_primitives', assembler_path)
    old = frozen_runtime(snapshot, assembler)
    installer = installer_overlay(old, overlay_path=installer_overlay_path, overlay_sha=installer_overlay_sha,
                                  review_path=installer_review_path, review_sha=installer_review_sha)
    files, archive, environment, normalized_sha = project_runtime(old, snapshot.tool('driver_path_repair/environment-run005.json'), space, assembler, installer)
    deployment, wrappers, collector_reference, prior_deployment = project_deployment(snapshot, assembler,
        repository / TOOL_REL / 'preparation_diagnostics_repair', space, document)
    source_sha = sha(canonical(sorted((n, sha(b)) for n, b in files.items())))
    required = requirements(snapshot)
    material = obj(snapshot.tool('release/consumer-release/material_review.json'))
    solver = project_solver(read(solver_path), space, material) if solver_path is not None else None
    release = obj(snapshot.tool('release/notebook-release.json'))
    # Deliberately incomplete review-only release. There is no source manifest,
    # material approval, production admission or finalizer in the output.
    release.update(production_admitted=False, code_reference=assembler.DREF + '/' + str(document['versions']['code']), code_manifest_sha256=None,
        source_sha256=source_sha, source_archive_sha256=sha(archive), environment_sha256=sha(environment),
        material_review_sha256=None, deployment={n: desc(b) for n, b in deployment.items()})
    release['dataset_references'][0] = assembler.DREF + '/' + str(document['versions']['code'])
    release['storage']['environment_root'] = space['environment']
    release['storage']['observed_assembled_source_copy_bytes'] = None
    # Everything else in the old release (seven noncode mounts, original model,
    # scientific policy, hardware and storage maxima) remains byte-value equal.
    builder = load_module(deployment['notebook_builder.py'], 'inert_successor_notebook_builder', output / 'deployment/notebook_builder.py')
    preview = encoded(builder.build(release, deployment['source_loader.py'].decode(), kind='inactive'))
    result = {
        'format': 'irisx/preparation-successor-source-proposal-v1', 'status': 'INERT_SOURCE_PROPOSAL_ONLY',
        'assembler_source_sha256': sha(read(HERE / 'local_prepare.py')),
        'local_reconstruction': True, 'recovered_original_prepare_sha256': '3419fa0ab09d3e834f97d57990bb63ee96b4794a6c905d0d315e91f26ff6fb87',
        'identity': document, 'namespaces': space, 'identity_input_sha256': sha(identity_raw),
        'snapshot_commit': SNAPSHOT, 'snapshot_tree': TREE, 'runtime_parent_commit': RUNTIME_COMMIT,
        'predecessor_source_sha256': SOURCE_SHA, 'predecessor_source_archive_sha256': ARCHIVE_SHA,
        'source_sha256': source_sha, 'source_archive_sha256': sha(archive), 'environment_sha256': sha(environment),
        'normalized_source_contract_sha256': normalized_sha, 'source_members': 259,
        'changed_runtime_members': sorted(n for n in files if files[n] != old[n]),
        'unchanged_runtime_members': sum(files[n] == old[n] for n in files),
        'unchanged_baseline_members': sum(files[n] == old[n] for n in files if n.startswith('baseline/')),
        'original_baseline200_exact': installer is None, 'environment_path_substitutions': 3,
        'installer_overlay': None if installer is None else {k: v for k, v in installer.items() if k not in ('raw', 'review_raw')},
        'reviewed_diagnostic_overlay_pins': OVERLAYS, 'predecessor_deployment': prior_deployment,
        'deployment': {n: desc(b) for n, b in sorted(deployment.items())},
        'target_free_solver': None if solver is None else desc(solver),
        'target_free_solver_independent_review_required': True,
        'retained_collector_is_unmodified_run005_reference_not_successor_operator': True,
        'consumed_session': {'epoch': OLD_EPOCH, 'deadline': OLD_DEADLINE, 'preserved_never_reused': True},
        'successor_epoch': None, 'manual_failure_root_cause': 'UNVERIFIED',
        'original_installer_log_writer_is_still_unbounded': installer is None,
        'installer_runtime_validation_passed': False,
        'production_admitted': False, 'run_authorized': False, 'provider_versions_reserved': False,
        'publication_manifest_included': False, 'active_notebook_included': False,
        'provider_calls': 0, 'model_or_GPU_calls': 0, 'public_score': None,
        'original_scorer_full167_preserved': True, 'independent_approval_is_external': True,
        'required_inputs_sha256': sha(encoded(required)),
    }
    blobs = {'source.zip': archive, 'release/REVIEWED-ENVIRONMENT.json': environment,
             'SOURCE-FREEZE.json': encoded({'format': 'irisx/preparation-successor-source-freeze-v1',
                 'source_sha256': source_sha, 'source_archive_sha256': sha(archive),
                 'files': {n: desc(b) for n, b in sorted(files.items())}, 'production_admitted': False}),
             'PROPOSED-IDENTITY.json': encoded(document), 'SOURCE-PROPOSAL.json': encoded(result),
             'REQUIRED-INPUTS.json': encoded(required), 'FROZEN-INPUTS.json': encoded(snapshot.inputs),
             'LOCAL-INPUT-AVAILABILITY.json': encoded(audit_inputs(snapshot)),
             'review-only-release.json': encoded(release), 'inactive-review-preview.ipynb': preview,
             'review-only/verify_parent_wrappers.py': wrappers,
             'review-only/consumed-run005-collector-reference.py': collector_reference,
             **{'deployment/' + n: b for n, b in deployment.items()},
             **{'producer-source/' + n: b for n, b in files.items()}}
    if solver is not None:
        blobs['review-only/solver-descriptor.json'] = solver
        blobs['review-only/SOLVER-PROJECTION.json'] = encoded({'status': 'INDEPENDENT_REVIEW_REQUIRED',
            'old_sha256': SOLVER_SHA, 'new_sha256': sha(solver), 'path_substitutions': 2,
            'escrow_bodies_read': False, 'production_admitted': False})
    if installer is not None:
        blobs['review-only/INSTALLER-REVIEW.json'] = installer['review_raw']
    blobs['PROPOSAL-INVENTORY.json'] = encoded({n: desc(b) for n, b in sorted(blobs.items())})
    output.mkdir(parents=True, mode=0o700)
    for name, raw in sorted(blobs.items()):
        target = ordinary(output / relative(name))
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        need(read(target) == raw, 'output roundtrip differs')
    return {**result, 'output_root': str(output), 'proposal_inventory_sha256': sha(blobs['PROPOSAL-INVENTORY.json'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command', required=True)
    build = subparsers.add_parser('prepare')
    for name in ('repository-root', 'identity-path', 'output-root'):
        build.add_argument('--' + name, required=True)
    build.add_argument('--solver-path')
    for name in ('installer-overlay-path', 'installer-overlay-sha', 'installer-review-path', 'installer-review-sha'):
        build.add_argument('--' + name)
    verify = subparsers.add_parser('verify-code18-predecessor')
    verify.add_argument('--repository-root', required=True)
    verify.add_argument('--candidate-root', required=True)
    audit = subparsers.add_parser('audit-inputs')
    audit.add_argument('--repository-root', required=True)
    audit.add_argument('--root-map')
    args = vars(parser.parse_args())
    command = args.pop('command')
    if command == 'prepare':
        result = prepare(**args)
    elif command == 'verify-code18-predecessor':
        result = verify_code18_candidate(Snapshot(args['repository_root']), args['candidate_root'])
    else:
        result = audit_inputs(Snapshot(args['repository_root']), obj(read(args['root_map'])) if args['root_map'] else None)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
