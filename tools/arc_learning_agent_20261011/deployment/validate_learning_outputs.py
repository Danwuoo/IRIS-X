"""Offline, fail-closed operational validation of one exact learning-agent run.

No provider calls, writes, extraction, code execution, model loading, pickle loading,
local /proc checks, or correctness analysis. The caller supplies trusted publication
and launch records plus bounded numeric-version downloads. Historical process
receipts establish recorded closure, not the current state of a remote VM or billing.
CLI success means production operational completion only; synthetic test validation
is API-only and explicitly never produces production success.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

MIB = 1024 ** 2
ARCHIVE_CAP = 512 * MIB
ADAPTER_CAP = 512 * MIB
ADAPTER_TOTAL_CAP = 1024 * MIB
DOWNLOAD_CAP = 2048 * MIB
JSON_CAP = 64 * MIB
MEMBER_CAP = 128 * MIB
MAX_FILES = 20000
POLICIES = ('global_grid', 'task_ttt', 'full_agent')
STAGE_CAPS = {'data_admission': 900, 'bootstrap_and_load': 1800, 'calibrate': 900, 'global_sft': 10800, 'train_only_program_rollouts': 2700, 'verified_trajectory_sft': 2700, 'dev_and_freeze': 3600, 'public_solve': 16200}
CAPS = {'generation_calls': 1600, 'scoring_forwards': 12000, 'input_tokens': 50_000_000,
        'output_tokens': 3_200_000, 'training_steps': 8192, 'cpu_checks': 12000, 'gas': 2_400_000_000}
SCORER_PINS = {
    'tools/arc_offline_evaluation.py': '3df3fd40c0a4db82dc6ad5c568102e45ad10efad8529412eae0623bd9f4ba016',
    'tools/arc_kaggle_submission.py': 'cdd570c99614d5eb326f9f07d86b36f80e4f5e53ec197370b5a0e03f262366bf',
    'src/irisx/arc_agi2.py': '0af942df40b76f208546a88864e84ddf521168bdb8f1fa4ce24232c36f3034a1',
    'tools/nvarc_native_multitask.py': '274cc5391ee45ee098cba4f002e31425d5bed88993c2b9319b0320c17a08fbdb',
    'tools/nvarc_native_solve_runtime.py': '56380d7c5fbb9219acfc846af275d6a334ed9460b6b6448e6feacf78be77b1c1',
    'src/irisx/__init__.py': '3ca8d59be8dae69d75bd92b279cdab54a5c411162d78544578f924264905702e',
    'src/irisx/artifacts.py': '28a7a48cbabd0f8556a1f976aebeaec3cc0824a380ab8bb4c12ba5cdfc762c95',
    'src/irisx/canonical.py': 'd2bacf5548440c865a64cb7cdfbbefcb995ec47e4e53ddfa4457964a83740a6a',
    'src/irisx/contracts.py': 'afb58a3fefe0c5482616d4cd219779c5bc9dacb30be44ea153ab85496b9af6b1',
    'src/irisx/errors.py': '45c10f3c10c958cb3cca97a26a3a0f79925ed5818ce591327d9ef1a851a6ffa4',
    'src/irisx/engine.py': 'bd08a6d9740d7696c6663410a450323c0c00cc5320bce184339ea4a98717d283',
    'src/irisx/bindings.py': 'cc0bb9698ab8803c3c951cd88d7c233661dd2a38c6f1066f7d86ac8be98f7601',
    'tools/__init__.py': 'f5ed985f7ed9e31ea3be113e86b11a7b44313f467c2e468a034ff789c7b85c76',
    'src/irisx/admission.py': '0520aa0b966ea7b2bd7f88330f6c3e0e407e428cf144458a1fda89317c38bb63',
}


class ValidationError(ValueError):
    """A fixed operational error code; never interpolate untrusted metric content."""


def need(condition, code):
    if not condition:
        raise ValidationError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                       allow_nan=False) + '\n').encode()


def digest(value):
    return sha(canonical(value))


def hash_ok(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def number(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def safe_name(name):
    need(type(name) is str and 0 < len(name) < 4096 and '\\' not in name and ':' not in name
         and not any(ord(c) < 32 for c in name), 'unsafe_relative_path')
    need(not name.startswith('/') and all(x not in ('', '.', '..') for x in name.split('/')),
         'unsafe_relative_path')
    return name


def suffix_path(path, suffix):
    need(type(path) is str and '\\' not in path and '..' not in path.split('/')
         and (path == suffix or path.endswith('/' + suffix)), 'remote_path_binding')


def _open_regular(path, cap):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink_forbidden')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise ValidationError('regular_file_unavailable') from exc
    stream = os.fdopen(fd, 'rb')
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_size > cap:
        stream.close()
        raise ValidationError('regular_file_or_size_cap')
    return stream, info.st_size


def regular_bytes(path, cap=JSON_CAP):
    stream, size = _open_regular(path, cap)
    with stream:
        raw = stream.read(cap + 1)
    need(len(raw) == size and len(raw) <= cap, 'file_changed_or_size_cap')
    return raw


def regular_hash(path, cap):
    stream, expected_size = _open_regular(path, cap)
    count = 0
    h = hashlib.sha256()
    with stream:
        while True:
            block = stream.read(MIB)
            if not block:
                break
            count += len(block)
            need(count <= cap, 'file_size_cap')
            h.update(block)
    need(count == expected_size, 'file_changed')
    return {'bytes': count, 'sha256': h.hexdigest()}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate_json_key')
        result[key] = value
    return result


def parse(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValidationError('nonfinite_json')))
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError('invalid_json') from exc


def document(value):
    if type(value) is dict:
        return copy.deepcopy(value), digest(value)
    raw = regular_bytes(value)
    result = parse(raw)
    need(type(result) is dict, 'document_object_required')
    return result, sha(raw)


def score_labels(raw):
    """Project top-level operational labels; skip scientific subtrees undecoded.

    Excluded values are only lexically scanned to locate their boundary. They are
    never materialized, evaluated, compared, summarized, or returned.
    """
    allowed = {'format', 'status', 'measurement', 'competition_gpu_equivalent', 'tasks', 'tests',
               'prediction_origin', 'training_used', 'training_steps', 'prediction_seal_sha256',
               'scorer_sha256', 'generation_may_resume'}
    try:
        text = raw.decode('utf-8')
        decoder = json.JSONDecoder()
        n, i, out, keys = len(text), 0, {}, set()
        def whitespace(p):
            while p < n and text[p].isspace(): p += 1
            return p
        i = whitespace(i)
        need(i < n and text[i] == '{', 'score_label_object')
        i += 1
        while True:
            i = whitespace(i)
            need(i < n, 'score_label_truncated')
            if text[i] == '}':
                i = whitespace(i + 1)
                need(i == n, 'score_label_trailing')
                return out
            key, i = decoder.raw_decode(text, i)
            need(type(key) is str and key not in keys, 'score_label_duplicate')
            keys.add(key)
            i = whitespace(i)
            need(i < n and text[i] == ':', 'score_label_separator')
            start = i = whitespace(i + 1)
            stack, quoted, escaped = [], False, False
            while i < n:
                ch = text[i]
                if quoted:
                    if escaped: escaped = False
                    elif ch == '\\': escaped = True
                    elif ch == '"': quoted = False
                elif ch == '"': quoted = True
                elif ch in '[{': stack.append(ch)
                elif ch in ']}':
                    if not stack: break
                    need((stack.pop(), ch) in (('[', ']'), ('{', '}')), 'score_label_structure')
                elif ch == ',' and not stack: break
                i += 1
            need(not stack and not quoted and i > start, 'score_label_structure')
            if key in allowed:
                out[key] = parse(text[start:i])
            need(i < n and text[i] in ',}', 'score_label_delimiter')
            if text[i] == ',':
                i = whitespace(i + 1)
                need(i < n and text[i] != '}', 'score_label_trailing_comma')
    except (UnicodeError, ValueError, IndexError) as exc:
        if isinstance(exc, ValidationError): raise
        raise ValidationError('invalid_score_labels') from exc


def normalize_notebook(value):
    value = copy.deepcopy(value)
    for cell in value['cells']:
        if isinstance(cell['source'], list): cell['source'] = ''.join(cell['source'])
    return value


def notebook_constants(notebook):
    values = {}
    driver_suffix = None
    for cell in notebook['cells']:
        if cell.get('cell_type') != 'code': continue
        tree = ast.parse(cell['source'])
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try: values[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, TypeError): pass
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'driver' for t in node.targets):
                if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.Add) and isinstance(node.value.left, ast.Name) and node.value.left.id == 'loader_source':
                    driver_suffix = ast.literal_eval(node.value.right)
    return values, driver_suffix


def verify_launch(manifest, manifest_sha, finalization, journal, launch, finalized_path,
                  template_path=None, saved_path=None):
    specs = [n for n in manifest['notebooks'] if n['role'] == 'run001']
    need(len(specs) == 1, 'active_notebook_contract')
    spec = specs[0]
    raw = regular_bytes(finalized_path)
    template_raw = regular_bytes(template_path or spec['path'])
    need(sha(raw) == finalization['finalized_sha256'] == launch['submitted_source_sha256'] == journal['source_sha256'], 'submitted_source_hash')
    need(sha(template_raw) == spec['sha256'] == finalization['template_sha256'], 'template_hash')
    normalized = normalize_notebook(parse(raw))
    template = normalize_notebook(parse(template_raw))
    epoch = finalization['predispatch_epoch']
    need(number(epoch) and finalization['deadline_epoch'] == epoch + 43200, 'launch_deadline')
    patch = spec['dispatch_epoch_patch']
    need(patch['required'] is True and patch['assignment'] == 'PREDISPATCH_EPOCH', 'mandatory_epoch_patch')
    index = patch['cell_index']
    code = normalized['cells'][index]['source']
    pattern = r'(?m)^PREDISPATCH_EPOCH\s*=\s*([^\n]+)$'
    found = re.findall(pattern, code)
    need(len(found) == 1, 'epoch_assignment')
    need(ast.literal_eval(found[0]) == epoch and type(ast.literal_eval(found[0])) in (int, float), 'epoch_assignment')
    reset = copy.deepcopy(normalized)
    reset['cells'][index]['source'] = re.sub(pattern, 'PREDISPATCH_EPOCH = None', code)
    need(reset == template, 'non_epoch_source_change')
    saved_raw = regular_bytes(saved_path or launch['saved_source']['path'])
    need(sha(saved_raw) == launch['saved_source']['sha256'] and len(saved_raw) == launch['saved_source']['bytes'], 'saved_source_hash')
    need(normalize_notebook(parse(saved_raw)) == normalized and launch['normalized_source_exact'] is True, 'saved_source_normalized_binding')
    need(journal['manifest_sha256'] == launch['manifest_sha256'] == manifest_sha, 'launch_manifest_binding')
    need(journal['reference'] == launch['reference'] == spec['reference'], 'launch_reference')
    need(integer(spec['expected_version'], 1) and type(launch['version']) is int and launch['version'] == spec['expected_version'] == journal['expected_version'], 'launch_numeric_version')
    need(integer(launch['kernel_id'], 1) and launch['kernel_id'] == journal['kernel_id'], 'launch_owner_kernel')
    need(journal['save_calls'] == 1 and type(journal['save_calls']) is int, 'single_launch_required')
    need(number(journal['dispatch_epoch']) and 0 <= journal['dispatch_epoch'] - epoch <= patch['maximum_patch_age_seconds'], 'stale_dispatch_epoch')
    constants, driver_suffix = notebook_constants(normalized)
    need(constants.get('PREDISPATCH_EPOCH') == epoch and constants.get('MANUAL_START') is True and constants.get('ENABLE_MODEL') is True, 'active_production_flags')
    need(constants.get('OUTPUT_ROOT') == spec['output_root'] and constants.get('SESSION_SECONDS') == 43200 and constants.get('PROFILE') == 'LEARNING_AGENT12H', 'active_production_config')
    need(isinstance(driver_suffix, str), 'bootstrap_driver_suffix_missing')
    launcher = manifest['notebook_launcher']
    need(constants['LOADER_SHA256'] == launcher['loader_sha256'] and constants['GUARD_SHA256'] == launcher['guard_sha256'] and sha((constants['LOADER_SOURCE'] + driver_suffix).encode()) == launcher['driver_sha256'] and launcher['deadline_seconds'] == 43200, 'manifest_launcher_source_pins')
    return spec, constants, driver_suffix


class Downloads:
    def __init__(self, root, receipt, launch, spec, manifest_sha):
        self.root = Path(root).absolute()
        need(self.root.is_dir() and not any(p.is_symlink() for p in (self.root, *self.root.parents)), 'download_root')
        self.files, self.listed = {}, {}
        version = spec['expected_version']
        need(type(receipt['numeric_output_version']) is int and receipt['numeric_output_version'] == version, 'retrieval_numeric_version')
        need(receipt['manifest_sha256'] == manifest_sha and receipt['reference'] == launch['reference'] and receipt['kernel_id'] == launch['kernel_id'], 'retrieval_binding')
        for side in ('before', 'after'):
            snap = receipt[side]
            need(snap['reference'] == launch['reference'] and snap['kernel_id'] == launch['kernel_id'] and type(snap['version']) is int and snap['version'] == version, 'provider_version_drift')
            need(snap['status'] == 'COMPLETE', 'provider_not_complete')
            need(snap['source_sha256'] == launch['saved_source']['sha256'], 'provider_source_drift')
        need(type(receipt['files']) is list and 0 < len(receipt['files']) <= MAX_FILES, 'retrieval_file_count')
        total, local_names = 0, set()
        for row in receipt['files']:
            name, local = safe_name(row['provider_path']), safe_name(row['local_path'])
            need(name not in self.files and local not in local_names, 'duplicate_download')
            need(type(row['version']) is int and row['version'] == version, 'download_version')
            need(integer(row['bytes']) and hash_ok(row['sha256']), 'download_descriptor')
            cap = ARCHIVE_CAP if name.endswith('.zip') else ADAPTER_CAP if '/trained-global-adapter/' in name else JSON_CAP
            descriptor = regular_hash(self.root / local, cap)
            need(descriptor == {k: row[k] for k in ('bytes', 'sha256')}, 'download_bytes_hash')
            total += descriptor['bytes']; need(total <= DOWNLOAD_CAP, 'download_total_cap')
            self.files[name] = (self.root / local, descriptor)
            local_names.add(local)
        need(type(receipt['provider_files']) is list and len(receipt['provider_files']) <= MAX_FILES, 'provider_listing_count')
        for row in receipt['provider_files']:
            name = safe_name(row['path'])
            need(name not in self.listed and integer(row['bytes']), 'provider_listing_descriptor')
            self.listed[name] = row['bytes']
        for name, (_, descriptor) in self.files.items():
            need(self.listed.get(name) == descriptor['bytes'], 'download_listing_mismatch')

    def raw(self, name, cap=JSON_CAP):
        need(name in self.files, 'required_download_missing')
        return regular_bytes(self.files[name][0], cap)

    def json(self, name):
        return parse(self.raw(name))


class Evidence:
    def __init__(self, downloads, output_root, synthetic):
        self.d, self.prefix = downloads, output_root + '/'
        self.closure = downloads.json(self.prefix + 'post-seal-closure.json')
        c = self.closure
        need(c.get('format') == 'irisx/learning-export-closure-v1' and c.get('generation_may_resume') is False, 'post_seal_closure')
        need(re.fullmatch(r'learning-[0-9a-f]{32}', c.get('run_id', '')) is not None, 'run_id')
        self.run_id = c['run_id']
        archive_relative = 'archives/evidence-' + self.run_id + '.zip'
        # Synthetic fixture relocation is explicit and never accepted in production.
        suffix_path(c['archive']['path'], archive_relative if synthetic else output_root + '/' + archive_relative)
        self.archive_name = self.prefix + archive_relative
        need(self.archive_name in downloads.files, 'closed_archive_missing')
        archive_path, descriptor = downloads.files[self.archive_name]
        need(descriptor == {k: c['archive'][k] for k in ('bytes', 'sha256')}, 'closed_archive_hash')
        self.archive_sha = descriptor['sha256']
        self.inventory_raw = downloads.raw(self.prefix + 'archives/evidence-inventory.json')
        self.inventory = parse(self.inventory_raw)
        inv = self.inventory
        need(inv.get('format') == 'irisx/learning-evidence-inventory-v1' and inv.get('run_id') == self.run_id, 'inventory_run')
        need(digest(inv) == c['inventory_sha256'] and inv.get('separate_artifacts') == c.get('separate_artifacts'), 'inventory_closure_binding')
        need(inv.get('evaluator_answer_payloads_included') is False and inv.get('installed_environment_included') is False, 'inventory_scope')
        self.stream, _ = _open_regular(archive_path, ARCHIVE_CAP)
        try:
            self.zip = zipfile.ZipFile(self.stream)
            infos = self.zip.infolist()
            need(0 < len(infos) <= MAX_FILES, 'archive_member_count')
            names, expanded = set(), 0
            for info in infos:
                name = safe_name(info.filename)
                need(name not in names and not info.is_dir(), 'archive_duplicate_or_directory')
                mode = info.external_attr >> 16
                need(not mode or stat.S_IFMT(mode) in (0, stat.S_IFREG), 'archive_nonregular_member')
                need(not (info.flag_bits & 1) and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'archive_encoding')
                need(integer(info.file_size) and info.file_size <= MEMBER_CAP, 'archive_member_cap')
                expanded += info.file_size; need(expanded <= ARCHIVE_CAP, 'archive_expansion_cap')
                names.add(name)
            need(type(inv.get('files')) is dict and names == set(inv['files']) | {'evidence-inventory.json'}, 'archive_inventory_set')
            need(parse(self.raw('evidence-inventory.json')) == inv and self.raw('evidence-inventory.json') == canonical(inv), 'archive_inventory_bytes')
            for name, row in inv['files'].items():
                safe_name(name)
                need(type(row) is dict and set(row) == {'bytes', 'sha256'} and integer(row['bytes']) and hash_ok(row['sha256']), 'archive_descriptor')
                need(self.hash_member(name) == row, 'archive_member_hash')
            self.member_count = len(names)
            self.expanded_bytes = expanded
        except BaseException:
            self.stream.close()
            raise

    def raw(self, name):
        info = self.zip.getinfo(name)
        need(info.file_size <= MEMBER_CAP, 'archive_member_cap')
        try:
            with self.zip.open(info) as stream:
                raw = stream.read(MEMBER_CAP + 1)
            need(len(raw) == info.file_size, 'archive_actual_size')
            return raw
        except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
            raise ValidationError('archive_crc_or_corruption') from exc

    def hash_member(self, name):
        info = self.zip.getinfo(name)
        h, count = hashlib.sha256(), 0
        try:
            with self.zip.open(info) as stream:
                while True:
                    block = stream.read(MIB)
                    if not block: break
                    count += len(block); need(count <= MEMBER_CAP, 'archive_actual_size')
                    h.update(block)
        except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
            raise ValidationError('archive_crc_or_corruption') from exc
        need(count == info.file_size, 'archive_actual_size')
        return {'bytes': count, 'sha256': h.hexdigest()}

    def json(self, name):
        need(name in self.inventory['files'], 'evidence_missing')
        return parse(self.raw(name))

    def close(self):
        self.zip.close(); self.stream.close()


def identity(value):
    need(type(value) is dict and set(value) == {'pid', 'birth', 'session', 'state'}, 'process_identity_schema')
    need(integer(value['pid'], 1) and integer(value['birth']) and integer(value['session'], 1) and type(value['state']) is str and len(value['state']) == 1, 'process_identity')
    return value['pid'], value['birth'], value['session']


def historical_proof(proof, fmt='irisx/owned-process-closure-v1'):
    """Validate persisted remote proof only. Deliberately never consult local PIDs."""
    need(proof.get('format') == fmt and proof.get('scope') == 'dedicated-subreaper-tree' and proof.get('closed') is True and proof.get('ownership_complete') is True, 'historical_closure_incomplete')
    need(proof.get('remaining') == [] and proof.get('errors') == [] and proof.get('forced') is False, 'historical_closure_forced_or_remaining')
    need(type(proof.get('returncode')) is int and proof['returncode'] == 0 and type(proof.get('worker_returncode')) is int and proof['worker_returncode'] == 0, 'historical_worker_failed')
    root = identity(proof['root_identity'])
    owned = [identity(v) for v in proof['owned_identities']]
    need(owned and len(owned) == len(set(owned)) and root in owned, 'historical_root_binding')
    reaped = [identity(v) for v in proof['reaped_identities']]
    need(len(reaped) == len(set(reaped)) and set(reaped) <= set(owned), 'historical_reaped_binding')
    return root


def proof_bundle(read_json, prefix, expected_proof):
    proof = read_json(prefix + 'closure.json')
    need(proof == expected_proof, 'persisted_tree_proof_binding')
    root = historical_proof(proof)
    launch = read_json(prefix + 'launch.json')
    worker = read_json(prefix + 'worker-launch.json')
    supervisor = read_json(prefix + 'supervisor-result.json')
    need(launch['format'] == 'irisx/owned-process-launch-v1' and launch['scope'] == 'dedicated-subreaper-tree' and identity(launch['supervisor_identity']) == root, 'process_launch_binding')
    need(worker['format'] == 'irisx/owned-worker-launch-v1' and worker['parent_death_signal'] == 9 and identity(worker['supervisor_identity']) == root, 'worker_launch_binding')
    child = identity(worker['worker_identity'])
    need(child in [identity(x) for x in proof['owned_identities']], 'worker_owned_binding')
    need(historical_proof(supervisor, 'irisx/owned-supervisor-result-v1') == child and identity(supervisor['supervisor_identity']) == root, 'supervisor_result_binding')
    return launch, worker


def verify_ledger(raw, expected):
    need(raw.endswith(b'\n') and len(raw) <= MEMBER_CAP, 'ledger_truncated_or_cap')
    lines = raw.splitlines()
    need(0 < len(lines) <= 100000, 'ledger_event_count')
    used, pending, seen, completed = dict.fromkeys(CAPS, 0), {}, set(), {}
    previous, caps = '0' * 64, None
    for i, line in enumerate(lines):
        row = parse(line)
        need(type(row) is dict and row.get('index') == i and type(row.get('index')) is int and row.get('previous') == previous, 'ledger_chain_index')
        body = {k: v for k, v in row.items() if k != 'sha256'}
        need(row.get('sha256') == digest(body), 'ledger_chain_hash')
        previous = row['sha256']
        event = row.get('event')
        if i == 0:
            need(event == 'opened' and set(row) == {'event', 'index', 'previous', 'sha256', 'caps'}, 'ledger_open')
            caps = row['caps']
            need(type(caps) is dict and set(caps) == set(CAPS) and all(integer(v) and v <= CAPS[k] for k, v in caps.items()), 'ledger_caps')
            continue
        need(event in ('reserved', 'complete', 'failed', 'excluded'), 'ledger_unknown_work')
        need(set(row) == {'event', 'index', 'previous', 'sha256', 'event_id', 'amounts'}, 'ledger_event_schema')
        event_id, amounts = row['event_id'], row['amounts']
        need(type(event_id) is str and event_id and type(amounts) is dict and amounts and set(amounts) <= set(CAPS) and all(integer(v) for v in amounts.values()), 'ledger_amounts')
        if event == 'reserved':
            need(not pending and event_id not in seen, 'ledger_duplicate_or_pending')
            seen.add(event_id); pending[event_id] = amounts
            for key, value in amounts.items():
                used[key] += value; need(used[key] <= caps[key], 'ledger_cap_exceeded')
        else:
            need(event_id in pending and set(amounts) == set(pending[event_id]), 'ledger_unreserved_work')
            reserved = pending.pop(event_id)
            for key, value in amounts.items():
                need(value <= reserved[key], 'ledger_reservation_exceeded')
                used[key] -= reserved[key] - value
            completed[event_id] = {'event': event, 'amounts': amounts}
    need(not pending, 'ledger_pending_work')
    observed = {'caps': caps, 'charged': used, 'pending': {}, 'events': len(lines), 'last_sha256': previous}
    need(expected == observed, 'ledger_summary_binding')
    need(used['training_steps'] > 0 and used['generation_calls'] > 0, 'no_physical_training_or_generation')
    return observed, completed


def verify_training(result, completed, synthetic):
    stage = result['stages'].get('global_sft')
    need(type(stage) is dict and integer(stage.get('steps'), 1) and stage.get('steps') == stage.get('optimizer_steps') and stage.get('optimizer_state_consistent') is True and stage.get('usage_known') is True, 'global_sft_actual_optimizer_required')
    need(stage.get('status') in ('complete', 'deadline', 'token_budget', 'no_context_eligible_records') and integer(stage.get('attempted_microbatches'), stage['steps']), 'global_sft_failed_or_unknown')
    updates = stage.get('updates')
    need(type(updates) is list and len(updates) == stage['steps'], 'global_sft_update_count')
    prior = stage.get('adapter_before_sha256')
    need(hash_ok(prior), 'global_sft_adapter_before')
    last_adam = None
    for update in updates:
        need(update.get('finite_gradients') is True and integer(update.get('changed_adapter_tensors'), 1) and integer(update.get('adam_step'), 1), 'global_sft_finite_changed_update')
        need(number(update.get('gradient_norm')) and number(update.get('elapsed_seconds'), 1e-12), 'global_sft_update_finiteness')
        need(type(update.get('loss')) in (int, float) and math.isfinite(update['loss']), 'global_sft_update_finiteness')
        need(update.get('adapter_before_sha256') == prior and hash_ok(update.get('adapter_after_sha256')) and update['adapter_after_sha256'] != prior, 'global_sft_update_chain')
        need(last_adam is None or update['adam_step'] == last_adam + 1, 'global_sft_adam_sequence')
        prior, last_adam = update['adapter_after_sha256'], update['adam_step']
    need(prior == stage.get('adapter_after_sha256') and prior != stage['adapter_before_sha256'], 'global_sft_adapter_after')
    event = completed.get(stage.get('physical_event_id'))
    need(event and event['event'] == 'complete' and event['amounts'].get('training_steps') == stage['attempted_microbatches'] and event['amounts'].get('input_tokens') == stage['input_tokens'], 'global_sft_physical_binding')
    need(result['training_steps'] >= stage['steps'] and result['charged_training_microbatches'] == result['physical_usage']['charged']['training_steps'], 'training_counter_binding')
    model = result['stages']['model_load']['identity']
    if synthetic:
        need(result['prediction_origin'] == 'synthetic_cpu' and result['production_model'] is False and model.get('execution_mode') == 'tiny_cpu' and stage.get('tiny_cpu') is True, 'synthetic_labels_required')
    else:
        need(result.get('prediction_origin') == 'trained_model_research' and result.get('production_model') is True, 'production_model_required')
        need(model.get('model_key') == 'granite-4.2-8b' and model.get('repository') == 'ibm-granite/granite-4.2-8b' and model.get('revision') == 'f8de16cdcdbc6c779ca517604e050d82cc119e44' and model.get('native_embedding_rows') == 100352 and model.get('full_native_vocabulary') is True and model.get('full_loaded_source_tensor_coverage') is True and model.get('loaded_parameter_count') == 8791592960 and model.get('source_parameter_count') == 8791592960 and stage.get('tiny_cpu') is False and stage.get('full_native_vocabulary') == 100352, 'production_native_model_required')
        hardware = result['stages']['model_load']['hardware']
        need(hardware.get('gpu_count') == 1 and hardware.get('bf16_supported') is True and hardware.get('compute_capability') == [12, 0] and hardware.get('cpu_count') == 48 and number(hardware.get('gpu_total_memory_bytes'), 90_000_000_000) and number(hardware.get('host_memory_bytes'), 170 * 1024**3), 'production_hardware_receipt')
        gpu_name = hardware.get('gpu_name', '').upper()
        need('RTX PRO 6000' in gpu_name and 'BLACKWELL' in gpu_name, 'production_hardware_name')
        need(tuple(int(x) for x in hardware['torch_cuda'].split('.')[:2]) >= (12, 8) and tuple(int(x) for x in hardware['driver_version'].split('.')) >= (580, 95, 5), 'production_hardware_versions')
    return stage['steps']


def verify_adapter(evidence, result, synthetic):
    separate = evidence.inventory['separate_artifacts']
    need(type(separate) is dict and 0 < len(separate) <= MAX_FILES, 'separate_artifact_inventory')
    adapter, checkpoint, downloaded_checkpoints, total = {}, {}, 0, 0
    for name, row in separate.items():
        safe_name(name)
        need(set(row) == {'bytes', 'sha256'} and integer(row['bytes']) and hash_ok(row['sha256']), 'separate_descriptor')
        provider = evidence.prefix + name
        need(evidence.d.listed.get(provider) == row['bytes'], 'separate_artifact_provider_presence')
        if name.startswith('worker/trained-global-adapter/'):
            need(provider in evidence.d.files and evidence.d.files[provider][1] == row, 'adapter_bytes_not_verified')
            total += row['bytes']; need(row['bytes'] <= ADAPTER_CAP and total <= ADAPTER_TOTAL_CAP, 'adapter_download_cap')
            adapter[name.removeprefix('worker/trained-global-adapter/')] = row
        elif name.startswith('worker/checkpoints/'):
            checkpoint[name] = row
            if provider in evidence.d.files:
                need(evidence.d.files[provider][1] == row, 'checkpoint_download_hash')
                downloaded_checkpoints += 1
        else:
            raise ValidationError('unexpected_separate_artifact')
    need({'adapter-binding.json', 'adapter_config.json', 'adapter_model.safetensors'} <= set(adapter) and checkpoint, 'adapter_or_checkpoints_missing')
    binding = evidence.d.json(evidence.prefix + 'worker/trained-global-adapter/adapter-binding.json')
    exported = {k: v for k, v in result['stages']['global_export'].items() if k != 'path'}
    need(binding == exported and binding.get('format') == 'irisx/learning-agent-adapter-v1' and binding.get('same_process_state_saved') is True and binding.get('saved_state_exact') is True, 'adapter_export_binding')
    need(set(binding['files']) == set(adapter) - {'adapter-binding.json'} and all(adapter[n]['sha256'] == h for n, h in binding['files'].items()), 'adapter_all_file_hashes')
    need(hash_ok(binding.get('adapter_sha256')) and hash_ok(binding.get('saved_adapter_sha256')), 'adapter_state_hashes')
    native = binding['model_identity']['native_identity']
    need(native == result['stages']['model_load']['identity'], 'adapter_native_identity')
    if not synthetic:
        need(binding['model_identity'].get('tiny_cpu') is False and binding['model_identity']['model_config']['vocab_size'] == 100352 and 'tiny-byte-tokenizer.json' not in adapter, 'synthetic_adapter_forbidden')
    selected = result['stages']['global_selection']['selected']
    selected_stage = {'global_sft': 'global_sft', 'trajectory_sft': 'trajectory_sft'}.get(selected)
    need(selected_stage is not None and binding['adapter_sha256'] == result['stages'][selected_stage]['adapter_after_sha256'], 'selected_adapter_binding')
    reports = result['stages']['global_sft'].get('checkpoints')
    need(type(reports) is list and reports, 'global_checkpoint_receipt_missing')
    latest = reports[-1]
    need(latest.get('format') == 'irisx/learning-lora-checkpoint-v1' and latest.get('atomic') is True and latest.get('includes_optimizer_rng_cursor') is True, 'global_checkpoint_receipt')
    directory = PurePosixPath(latest['path']).name
    safe_name(directory)
    state_name = 'worker/checkpoints/global-sft/' + directory + '/state.pt'
    need(checkpoint.get(state_name) == {'bytes': latest['state_bytes'], 'sha256': latest['state_sha256']}, 'global_checkpoint_state_binding')
    retained = [r for r in latest['retention'] if r['status'] == 'retained']
    need(0 < len(retained) <= 2, 'checkpoint_retention_count')
    for row in retained:
        safe_name(row['directory'])
        base = 'worker/checkpoints/global-sft/' + row['directory']
        need(checkpoint.get(base + '/state.pt', {}).get('sha256') == row['state_sha256'] and checkpoint.get(base + '/manifest.json', {}).get('sha256') == row['manifest_sha256'], 'checkpoint_retention_binding')
    # Checkpoint tensor content is never unpickled. Absence of a download is a
    # distinct provider-presence + archive-hash-manifest level, not byte proof.
    return {'adapter_files_hashed': len(adapter), 'adapter_bytes_hashed': total,
            'checkpoint_files_listed': len(checkpoint), 'checkpoint_files_hashed': downloaded_checkpoints,
            'checkpoint_verification': 'all_downloaded_bytes_hashed' if downloaded_checkpoints == len(checkpoint) else 'provider_presence_and_sealed_hash_manifest'}


def verify_predictions(e, result, source, source_sha, synthetic):
    summary = e.json('summary.json')
    need(summary.get('status') == 'COMPLETE' and summary.get('solver_status') == 'complete' and summary.get('score_status') == 'SCORED', 'runtime_terminal_incomplete')
    need(summary.get('run_id') == e.run_id and summary.get('model_stopped') is True and summary.get('training_steps') == result['training_steps'] and summary['physical_usage'] == result['physical_usage'], 'summary_binding')
    seal_raw = e.raw('predictions/prediction-seal.json')
    seal_sha = sha(seal_raw); seal = parse(seal_raw)
    need(summary['prediction_seal']['sha256'] == seal_sha and seal['format'] == 'irisx/learning-prediction-seal-v1' and seal['generation_may_resume'] is False, 'prediction_seal')
    need(seal['source_identity'] == source and len(source) == 97 and digest(source) == source_sha, 'exact_97_source_identity')
    need(all(source.get(k) == v for k, v in SCORER_PINS.items()), 'historical_scorer_pins')
    need(seal['tasks'] == 120 and seal['tests'] == 167 and seal['policies'] == list(POLICIES), 'prediction_denominator')
    need(seal['bindings'] == {'prediction_origin': result['prediction_origin'], 'run_id': e.run_id}, 'prediction_origin_binding')
    expected_files = {p + '.json' for p in POLICIES} | {'owner-closure.json', 'solver-result.json'}
    need(set(seal['files']) == expected_files, 'prediction_seal_file_set')
    for name, row in seal['files'].items():
        need(e.inventory['files'].get('predictions/' + name) == row, 'prediction_member_binding')
    need(e.raw('predictions/solver-result.json') == e.raw('worker/result.json') and e.raw('predictions/owner-closure.json') == e.raw('owner-closure.json'), 'sealed_result_closure_copies')
    need(result['solver_manifest_sha256'] == seal['solver_manifest_sha256'], 'solver_manifest_binding')
    pools = {}
    for policy in POLICIES:
        pool = e.json('predictions/' + policy + '.json')
        need(pool['run_id'] == e.run_id and pool['method'] == 'learning-agent/' + policy, 'pool_run_policy')
        records = pool['records']; need(type(records) is list and len(records) == 120, 'pool_task_denominator')
        task_ids = [r['task_id'] for r in records]
        need(len(set(task_ids)) == 120 and all(re.fullmatch('[0-9a-f]{8}', t) for t in task_ids), 'pool_task_identity')
        need(sum(len(r['tests']) for r in records) == 167, 'pool_test_denominator')
        for row in records:
            need(type(row['task_digest']) is str and row['task_digest'].startswith('sha256:') and hash_ok(row['task_digest'][7:]) and row['tests'], 'pool_task_digest')
            need([t['test_index'] for t in row['tests']] == list(range(len(row['tests']))), 'pool_test_indexes')
            for test in row['tests']:
                need(type(test['input_digest']) is str and test['input_digest'].startswith('sha256:') and hash_ok(test['input_digest'][7:]) and type(test['ranked_grids']) is list and len(test['ranked_grids']) <= 2, 'prediction_shape')
                # Deliberately do not inspect grid values or evaluate correctness.
        pools[policy] = {r['task_id']: (r['task_digest'], [(t['test_index'], t['input_digest']) for t in r['tests']]) for r in records}
    need(all(v == pools[POLICIES[0]] for v in pools.values()), 'pool_shared_denominator')
    results = result['results']
    need(type(results) is dict and set(results) <= set(pools[POLICIES[0]]), 'attempted_task_identity')
    need(synthetic or set(results) == set(pools[POLICIES[0]]), 'all_120_task_attempts_required')
    need(results, 'no_task_attempts')
    for task_id, task in results.items():
        need(task['task_id'] == task_id and task.get('status') in ('complete', 'budget_stopped', 'error'), 'task_attempt_terminal')
        need(task['physical_usage'].get('unknown_usage_events') == 0, 'task_unknown_work')
        need(e.json('worker/tasks/' + task_id + '/result.json') == task, 'task_result_binding')
        need(set(task['policies']) == set(POLICIES) and all(len(task['policies'][p]) == len(pools[p][task_id][1]) for p in POLICIES), 'task_test_attempt_denominator')
    process = e.json('evaluation/process-receipt.json')
    need(process.get('returncode') == 0 and type(process['returncode']) is int and process.get('owned_process_stopped') is True and process.get('prediction_seal_sha256') == seal_sha, 'scorer_process_closure')
    for name in ('evaluation/public-summary.json', 'evaluation/evaluator-detail.json'):
        labels = score_labels(e.raw(name))
        need(labels.get('status') == 'SCORED' and labels.get('format') == 'irisx/learning-public-evaluation-v1' and labels.get('tasks') == 120 and labels.get('tests') == 167, 'scorer_status_labels')
        need(labels.get('prediction_origin') == result['prediction_origin'] and labels.get('prediction_seal_sha256') == seal_sha and labels.get('scorer_sha256') == SCORER_PINS['tools/arc_offline_evaluation.py'] and labels.get('generation_may_resume') is False and labels.get('training_used') is True and labels.get('training_steps') == result['training_steps'], 'scorer_labels_binding')
    return summary, seal, seal_sha, len(results)


def verify_inner_owner(e, result, source_sha):
    closure = e.json('owner-closure.json'); start = e.json('owner-start.json')
    request_raw = e.raw('worker/request.json'); request = parse(request_raw)
    need(closure['format'] == 'irisx/learning-owner-closure-v1' and closure.get('graceful') is True and closure.get('returncode') == 0 and closure.get('session_members') == [], 'owner_not_graceful')
    root = historical_proof(closure['process_tree_proof'])
    need(identity(closure['worker_identity']) == identity(start['worker_identity']) == root and root[0] == root[2], 'owner_root_binding')
    need(identity(closure['parent_identity']) == identity(start['parent_identity']), 'coordinator_historical_binding')
    need(closure['source_identity_sha256'] == source_sha and closure['result_sha256'] == sha(e.raw('worker/result.json')) and closure['request_sha256'] == start['request_sha256'] == result['request_sha256'] == sha(request_raw), 'owner_hash_binding')
    need(request['run_id'] == e.run_id and digest(request['source_identity']) == source_sha and request['solver_manifest_sha256'] == result['solver_manifest_sha256'], 'owner_request_binding')
    launch, _ = proof_bundle(e.json, 'worker/process-guard/', closure['process_tree_proof'])
    need(identity(launch['coordinator_identity']) == identity(closure['parent_identity']) and launch['worker_argv'][-1] == sha(request_raw), 'owner_launch_request_binding')
    return request, closure


def verify_outer(d, spec, constants, suffix, finalization, e, summary, inner_closure):
    prefix = spec['output_root'] + '-launcher/'
    request_raw = d.raw(prefix + 'request.json'); request = parse(request_raw)
    closure_raw = d.raw(prefix + 'launcher-closure.json'); closure = parse(closure_raw)
    epoch, deadline = finalization['predispatch_epoch'], finalization['deadline_epoch']
    need(closure.get('format') == 'irisx/learning-notebook-closure-v1' and closure.get('started_epoch') == epoch and closure.get('hard_deadline_epoch') == deadline, 'outer_deadline_binding')
    need(closure.get('forced') is False and closure.get('reason') is None and closure.get('within_absolute_deadline') is True and number(closure.get('completed_epoch')) and epoch <= closure['completed_epoch'] <= deadline, 'outer_deadline_or_forced')
    historical_proof(closure['process_tree_proof'])
    launch, worker = proof_bundle(d.json, prefix + 'owned-tree/', closure['process_tree_proof'])
    need(identity(inner_closure['parent_identity']) == identity(worker['worker_identity']), 'outer_inner_owner_binding')
    need(launch['worker_argv'][-1] == sha(request_raw), 'outer_request_launch_hash')
    expected_config = {k.lower(): constants[k] for k in ('MANUAL_START', 'ENABLE_MODEL', 'PROFILE', 'OUTPUT_ROOT', 'SOURCE_PARENT', 'INPUT_ROOT', 'CODE_ROOT', 'DATA_ROOT', 'TRAINING_ROOT', 'MODEL_CONFIG', 'SEED')}
    expected_config.update(session_seconds=constants['SESSION_SECONDS'], predispatch_epoch=epoch)
    need(request['config'] == expected_config and request['pins'] == constants['LEARNING_PINS'], 'outer_request_source_config')
    need(request['started_epoch'] == epoch and request['hard_deadline_epoch'] == deadline, 'outer_request_deadline')
    need(sha(constants['LOADER_SOURCE'].encode()) == constants['LOADER_SHA256'] == request['loader_sha256'], 'outer_loader_hash')
    need(d.raw(prefix + 'owned_process_guard.py') == constants['GUARD_SOURCE'].encode() and sha(constants['GUARD_SOURCE'].encode()) == constants['GUARD_SHA256'] == request['guard_sha256'], 'outer_guard_hash')
    bootstrap = d.raw(prefix + 'bootstrap.py')
    need(bootstrap == (constants['LOADER_SOURCE'] + suffix).encode() and sha(bootstrap) == request['driver_sha256'], 'outer_driver_hash')
    suffix_path(request['launcher_root'], spec['output_root'] + '-launcher')
    returned = d.json(prefix + 'result.json')
    need({k: v for k, v in returned.items() if k != 'export'} == summary and returned.get('export') == e.closure, 'outer_post_export_result')
    clock = e.json('session-clock.json')
    need(clock == summary['clock'] and clock['format'] == 'irisx/learning-clock-v1' and clock['session_id'] == e.run_id and clock['origin'] == 'pre-dispatch' and clock['started_epoch'] == epoch and clock['deadline_epoch'] == deadline and clock['maximum_seconds'] == 43200, 'session_absolute_clock')
    return sha(closure_raw)


def verify_public_pins(seal, constants):
    pins = constants['LEARNING_PINS']['data']['role_manifests']
    need(seal['solver_manifest_sha256'] == pins['solver'] and seal['evaluator_manifest_sha256'] == pins['evaluator'], 'approved_public_data_pins')


def validate_outputs(download_root, *, manifest, finalization, launch_journal, launch_receipt,
                     retrieval_receipt, finalized_notebook, template_notebook=None,
                     saved_notebook=None, launch_binding=None, allow_synthetic=False):
    """Return compact counters/IDs/hashes. Raise ValidationError on any missing proof.

    Manifest must be its exact reviewed file, not an edited reconstruction. Other
    metadata may be paths or mappings (mappings are hashed using canonical JSON).
    All local/provider paths are explicit. allow_synthetic is solely for tests;
    its result always has operational_success=False, status=SYNTHETIC_VALIDATED.
    """
    need(type(allow_synthetic) is bool, 'synthetic_flag_boolean')
    m, manifest_sha = document(manifest)
    f, _ = document(finalization); j, _ = document(launch_journal)
    l, _ = document(launch_receipt); r, retrieval_sha = document(retrieval_receipt)
    try:
        need(m['format'] == 'irisx/learning-publication-contract-v1', 'publication_manifest_format')
        spec, constants, suffix = verify_launch(m, manifest_sha, f, j, l, finalized_notebook, template_notebook, saved_notebook)
        if r.get('launch_binding_sha256') is not None:
            need(launch_binding is not None, 'launch_binding_missing')
            binding, binding_sha = document(launch_binding)
            need(binding_sha == r['launch_binding_sha256'], 'launch_binding_hash')
            for key, expected in {'predispatch_epoch': f['predispatch_epoch'], 'deadline_epoch': f['deadline_epoch'], 'submitted_source_sha256': l['submitted_source_sha256'], 'saved_source_sha256': l['saved_source']['sha256']}.items():
                need(binding.get(key) == expected, 'launch_binding_fields')
        d = Downloads(download_root, r, l, spec, manifest_sha)
        e = Evidence(d, spec['output_root'], allow_synthetic)
        try:
            result = e.json('worker/result.json')
            need(result['format'] == 'irisx/learning-owner-result-v1' and result['run_id'] == e.run_id and result['status'] == 'complete' and result['model_stopped'] is True and result['pending_work'] == {}, 'solver_terminal_incomplete')
            source, source_sha = m['source_identity'], m['source_identity_sha256']
            need(result['source_identity_sha256'] == source_sha, 'result_source_binding')
            ledger, completed = verify_ledger(e.raw('worker/physical-work.jsonl'), result['physical_usage'])
            global_steps = verify_training(result, completed, allow_synthetic)
            summary, seal, seal_sha, attempted = verify_predictions(e, result, source, source_sha, allow_synthetic)
            if not allow_synthetic:
                verify_public_pins(seal, constants)
            inner_request, owner = verify_inner_owner(e, result, source_sha)
            admission = e.json('admission.json')
            need(admission['run_id'] == e.run_id and admission['source_identity'] == source and admission['enable_model'] is True and admission['solver_manifest_sha256'] == seal['solver_manifest_sha256'] and admission['evaluator_manifest_sha256'] == seal['evaluator_manifest_sha256'], 'admission_binding')
            need(inner_request['source_identity'] == source and inner_request['clock'] == summary['clock'] and admission['clock'] == summary['clock'], 'request_clock_source_binding')
            if allow_synthetic:
                need(inner_request['config'].get('tiny_cpu') is True and inner_request['config'].get('validation_mode') is True, 'synthetic_test_mode_required')
                need(attempted == inner_request['config'].get('fixture_tasks', 2), 'synthetic_attempt_count')
            else:
                need(inner_request['config'].get('tiny_cpu', False) is False and inner_request['config'].get('validation_mode', False) is False and inner_request['config'].get('session_seconds') == 43200 and inner_request['config'].get('predispatch_clock') is True, 'production_request_config')
            artifact_counts = verify_adapter(e, result, allow_synthetic)
            outer_sha = verify_outer(d, spec, constants, suffix, f, e, summary, owner)
            need([s.get('stage') for s in result['stage_clock']] == list(STAGE_CAPS), 'stage_clock_sequence')
            for stage in result['stage_clock']:
                need(stage.get('maximum_seconds') == STAGE_CAPS[stage['stage']] and stage.get('status') == 'complete' and stage.get('within_cap') is True and number(stage.get('started_epoch')) and number(stage.get('elapsed_seconds')) and stage['elapsed_seconds'] <= stage['maximum_seconds'] and f['predispatch_epoch'] <= stage['started_epoch'] <= stage['started_epoch'] + stage['elapsed_seconds'] <= f['deadline_epoch'], 'stage_deadline_or_incomplete')
            return {'format': 'irisx/learning-operational-validation-v1',
                    'status': 'SYNTHETIC_VALIDATED' if allow_synthetic else 'COMPLETE',
                    'operational_success': not allow_synthetic, 'synthetic_test_only': allow_synthetic,
                    'reference': l['reference'], 'kernel_id': l['kernel_id'], 'version': l['version'],
                    'run_id': e.run_id, 'manifest_sha256': manifest_sha,
                    'submitted_source_sha256': l['submitted_source_sha256'],
                    'saved_source_sha256': l['saved_source']['sha256'],
                    'retrieval_receipt_sha256': retrieval_sha, 'source_identity_sha256': source_sha,
                    'archive_sha256': e.archive_sha, 'archive_members_hashed': e.member_count,
                    'archive_expanded_bytes': e.expanded_bytes, 'prediction_seal_sha256': seal_sha,
                    'launcher_closure_sha256': outer_sha, 'task_attempts': attempted,
                    'prediction_tasks': 120, 'prediction_tests': 167, 'global_sft_optimizer_steps': global_steps,
                    'training_optimizer_steps': result['training_steps'],
                    'physical_ledger_events': ledger['events'], 'physical_ledger_sha256': ledger['last_sha256'],
                    'physical_counts': ledger['charged'], **artifact_counts,
                    'historical_process_closure_verified': True, 'absolute_deadline_verified': True,
                    'provider_vm_or_billing_state_verified': False, 'scientific_metrics_read': False}
        finally:
            e.close()
    except (KeyError, TypeError, IndexError, SyntaxError, zipfile.BadZipFile, OSError) as exc:
        raise ValidationError('missing_or_invalid_operational_evidence') from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-root', required=True)
    for name in ('manifest', 'finalization', 'launch-journal', 'launch-receipt', 'retrieval-receipt', 'finalized-notebook'):
        parser.add_argument('--' + name, required=True)
    for name in ('template-notebook', 'saved-notebook', 'launch-binding'):
        parser.add_argument('--' + name)
    args = vars(parser.parse_args(argv)); root = args.pop('download_root')
    try:
        receipt = validate_outputs(root, **args)
    except ValidationError as exc:
        print(json.dumps({'status': 'REJECTED', 'operational_success': False, 'error_code': str(exc), 'scientific_metrics_read': False}, sort_keys=True))
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
