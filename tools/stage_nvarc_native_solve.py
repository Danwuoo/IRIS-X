"""Offline staging of a new native trained-solve experiment; no provider calls."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from irisx.canonical import canonical_bytes, digest_value
from irisx.arc_nvarc_combined import atomic, sha
from tools import stage_nvarc_native_editor_008 as old
from tools import nvarc_native_solve_render as render
from tools.nvarc_native_solve_runtime import SOURCE_HASHES, validate_visible, require

CONTROL_SHA = '6cf868e127919747b1ccc46d60bc8e4905ce2eb2c25e11fc9e7fae1ddcfd452c'
BASE_COMMIT = 'd3df02a3e05c0516331c1af89edc6b463f2a24a3'
OWNER_RUN_INSTRUCTION = 'Sentinel_f4849b57d6c8819189eb074710948940'
OLD_PACKAGE = ROOT / '.irisx/nvarc-original/runs/nvarc-original-qwen3-native-ttt-008/package-l4'
LONG_PACKAGE = ROOT / '.irisx/nvarc-original/runs/nvarc-original-qwen3-long-ttt-002/package-l4'
OLD_PLAN_DIGEST = 'sha256:6e7b20de68182151e3f92511bc9202d6b7e813e690f39ee8ca3bfac2e240f897'
RUNTIME = ROOT / 'tools/nvarc_native_solve_runtime.py'


def frozen_inputs():
    checked = old.preflight(OLD_PACKAGE)
    require(checked['plan_digest'] == OLD_PLAN_DIGEST, 'exact frozen008 prerequisite required')
    previous = json.loads((OLD_PACKAGE / 'plan.json').read_bytes())
    raw = old.raw_payloads(previous)
    summary = json.loads((LONG_PACKAGE / 'stage-summary.json').read_bytes())
    for name in ('visible.json', 'plan.json'):
        require(sha(LONG_PACKAGE / name) == summary['inventory'][name], 'frozen source visible/plan bytes differ')
    source_plan = json.loads((LONG_PACKAGE / 'plan.json').read_bytes())
    require(digest_value(source_plan) == summary['plan_digest'], 'frozen long-source plan digest differs')
    visible_body = (LONG_PACKAGE / 'visible.json').read_bytes()
    visible = json.loads(visible_body); task_id = validate_visible(visible)
    require(digest_value([{'task_id': task_id, **visible[task_id]}]) == source_plan['visible_digest'] and
            source_plan['source_rows_digest'] == previous['source_rows_digest'] and
            source_plan['public_task_selection']['parent_ids'] == previous['parent_ids'] and
            source_plan['public_task_selection']['exposure_tags'] == previous['exposure_tags'],
            'same exposed visible task/training lineage required')
    notebook = LONG_PACKAGE / 'source-bundle/kaggle-qwen/arc2-qwen3-unsloth-flash-lora-batch4-queue.ipynb'
    require(sha(notebook) == '506b85db66f9949022e87935ccb06a73fd78cb690883bd600bfb5c7d36c2b3af',
            'exact original code notebook required')
    cells = json.loads(notebook.read_bytes())['cells']
    bodies = {'solver.py': raw['solver']}
    for name in ('arc_loader.py', 'arc_decoder.py'):
        marker = '%%writefile ' + name + '\n'
        found = []
        for cell in cells:
            text = cell.get('source', '')
            text = ''.join(text) if isinstance(text, list) else text
            if text.startswith(marker):
                found.append(text[len(marker):].encode('utf-8'))
        require(len(found) == 1, 'one exact original source cell required')
        bodies[name] = found[0]
    require({name: hashlib.sha256(body).hexdigest() for name, body in bodies.items()} == SOURCE_HASHES,
            'code-only source cell identities differ')
    return previous, raw, visible_body, bodies


def admission_for(path, run_id):
    if path is None:
        return None, None
    value = json.loads(path.read_bytes())
    fields = {'format', 'run_id', 'control_sha256', 'source_commit', 'maximum_paid_usd',
              'prior_sessions_reconciled', 'quota_reservation_id', 'reserved_quota_hours',
              'quota_observed_at', 'local_resource_admission', 'ui_operator', 'private', 'internet',
              'owner_editor_sessions_closed', 'owner_clearance_ref', 'l4_quota_multiplier'}
    require(set(value) == fields and value['format'] == 'irisx/controller-gpu-admission-v1' and
        value['run_id'] == run_id and value['control_sha256'] == CONTROL_SHA and
        value['source_commit'] == BASE_COMMIT and type(value['maximum_paid_usd']) is int and
        value['maximum_paid_usd'] == 0 and value['prior_sessions_reconciled'] is True and
        value['owner_editor_sessions_closed'] is True and isinstance(value['owner_clearance_ref'], str) and
        value['owner_clearance_ref'] and type(value['l4_quota_multiplier']) in (int, float) and
        value['l4_quota_multiplier'] == 2 and
        value['local_resource_admission'] is True and value['ui_operator'] == 'user' and
        value['private'] is True and value['internet'] is False and
        isinstance(value['quota_reservation_id'], str) and value['quota_reservation_id'] and
        type(value['reserved_quota_hours']) in (int, float) and
        math.isfinite(value['reserved_quota_hours']) and value['reserved_quota_hours'] >= 2.5 and
        isinstance(value['quota_observed_at'], str),
        'explicit reconciled controller resource admission required')
    require(datetime.fromisoformat(value['quota_observed_at'].replace('Z', '+00:00')).utcoffset() is not None,
            'quota observation must include a timezone')
    return value, sha(path)


def construct(run_id, admission_path=None):
    require(re.fullmatch(r'nvarc-original-qwen3-native-solve-\d{3}', run_id) is not None,
            'new native-solve identity required')
    previous, raw, visible, bodies = frozen_inputs()
    admission, admission_sha = admission_for(admission_path, run_id)
    plan = dict(previous)
    for key in ('owner_editor_only', 'kernel_execution_type', 'approved_proposal_plan_digest'):
        plan.pop(key, None)
    plan.update(format=render.FORMAT, run_id=run_id, kernel_id='danielwuu/' + run_id,
        approved=admission is not None, owner_decision='dots-control-kit-v1.2.0',
        control_version='1.2.0', control_sha256=CONTROL_SHA, source_commit=BASE_COMMIT,
        controller_admission_sha256=admission_sha, controller_admission=admission,
        baseline_native008_plan_digest=OLD_PLAN_DIGEST,
        baseline_native008_archive_sha256='2a8acbc25e5f4b673e3982c550914728ddf8db350191cc4b9cf823db8014dfec',
        visible_sha256=hashlib.sha256(visible).hexdigest(), visible_digest=digest_value(json.loads(visible)),
        original_solve_source_sha256=SOURCE_HASHES, maximum_training_forwards=128,
        maximum_outer_forwards=4359, maximum_optimizer_steps=128, maximum_generations=4,
        inference_forward_limits={'control': 7, 'generation': 4096, 'verification': 128},
        maximum_inference_input_tokens=5*1024**2, maximum_control_input_tokens=168,
        maximum_candidate_sequences=64, maximum_inference_seconds=900, diagnostic_task_seconds=1200,
        task_clock_policy='hard1200s from first training call; preprocessing excluded; not historical native clock parity',
        maximum_notebook_wall_seconds=3600, maximum_child_wall_seconds=3000,
        packaging_reserve_seconds=120, maximum_result_uncompressed_bytes=16*1024**2,
        minimum_free_working_bytes=4*1024**3, required_quota_reservation_hours=2.5,
        pythonhashseed=0, maximum_teacher_calls=0, maximum_paid_usd=0,
        owner_editor_only=True, kernel_execution_type='QUICK_SAVE',
        owner_execution_instruction_ref=OWNER_RUN_INSTRUCTION,
        agent_execution_authorized=False, save_helper_status_calls=0,
        initial_execution_route='private_QUICK_SAVE_only; owner starts Run_All and returns archive',
        editor_fallback='none; no automatic execution or queued fallback for this owner-run envelope',
        correctness_scored=False, full_numerical_parity_claim=False,
        scope='one exposed source-development task: pre-training native interface/cache controls,128-step epoch,source generation/ranking,exception-safe reset')
    raw.update(plan=canonical_bytes(plan, newline=True), worker=render.worker(raw['worker'].decode()),
        loader=bodies['arc_loader.py'], decoder=bodies['arc_decoder.py'],
        solve_runtime=RUNTIME.read_bytes(), visible=visible)
    source = old.proposal.predecessor.render(plan, raw)
    source = render.parent(source)
    disk_anchor = "phase='original-source-inventory'"
    require(source.count(disk_anchor) == 1, 'native parent disk admission anchor differs')
    source = source.replace(disk_anchor, "import shutil\n    if shutil.disk_usage(work).free < plan['minimum_free_working_bytes']:\n"
        "        raise RuntimeError('native solve working-space reserve unavailable')\n    " + disk_anchor)
    compile(source, 'native-trained-solve-parent', 'exec')
    download = download_cell(plan)
    notebook = {'nbformat': 4, 'nbformat_minor': 5,
        'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
        'cells': [{'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [],
                   'source': cell.splitlines(keepends=True)} for cell in (source, download)]}
    return plan, raw, notebook, old.proposal.predecessor.metadata(plan)


def download_cell(plan):
    # This cell has no dependency on model execution or variables from Run All.
    source = old.proposal.predecessor.ARCHIVE.read_text(encoding='utf-8')
    source += '''

def validate_closed_download(path, run_id, plan_digest):
    with zipfile.ZipFile(path) as stream:
        names=stream.namelist()
        if len(names)!=len(set(names)) or sum(row.file_size for row in stream.infolist())>16*1024**2:
            raise RuntimeError('closed bounded result archive required')
        manifest=json.loads(stream.read('manifest.json'))
        members=manifest['members']
        if manifest['run_id']!=run_id or manifest['plan_digest']!=plan_digest or len(members)!=len({r['path'] for r in members}) or set(names)!={r['path'] for r in members}|{'manifest.json'}:
            raise RuntimeError('exact result identity and closed members required')
        for row in members:
            body=stream.read(row['path'])
            if len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']:
                raise RuntimeError('result member integrity differs')
'''
    path = "Path('/kaggle/working/結果.zip')"
    args = path + ',' + repr(plan['run_id']) + ',' + repr(digest_value(plan))
    source += 'validate_closed_download(' + args + ')\nshow_editor_archive(' + args + ')\n'
    source += "print('下載結果.zip後，請停止本次GPU session。若前一格失敗，請保留結果，不要重新Run All。')\n"
    compile(source, 'native-owner-independent-download', 'exec')
    return source


def stage(package, run_id, admission_path=None):
    require(not package.exists(), 'new immutable native-solve package required')
    plan, raw, notebook, metadata = construct(run_id, admission_path)
    (package / 'kernel').mkdir(parents=True)
    atomic(package / 'plan.json', plan)
    atomic(package / 'kernel/notebook.ipynb', notebook)
    atomic(package / 'kernel/kernel-metadata.json', metadata)
    if admission_path is not None:
        (package / 'controller-admission.json').write_bytes(admission_path.read_bytes())
    atomic(package / 'stage-summary.json', {'run_id': run_id, 'plan_digest': digest_value(plan),
        'payload_sha256': {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()},
        'inventory': {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file()}})
    return preflight(package)


def preflight(package):
    saved = json.loads((package / 'plan.json').read_bytes())
    path = package / 'controller-admission.json'
    plan, raw, notebook, metadata = construct(saved['run_id'], path if path.is_file() else None)
    summary = json.loads((package / 'stage-summary.json').read_bytes())
    require(saved == plan and summary['plan_digest'] == digest_value(plan) and
        summary['run_id'] == plan['run_id'] and
        summary['inventory'] == {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*')
                                if p.is_file() and p.relative_to(package).as_posix() != 'stage-summary.json'} and
        not any(p.is_symlink() for p in package.rglob('*')) and
        json.loads((package / 'kernel/notebook.ipynb').read_bytes()) == notebook and
        json.loads((package / 'kernel/kernel-metadata.json').read_bytes()) == metadata and
        summary['payload_sha256'] == {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()},
        'closed native-solve plan/program/material bytes differ')
    return {'run_id': plan['run_id'], 'plan_digest': digest_value(plan),
        'offline_package_verified': True, 'approved_for_runtime': plan['approved'],
        'provider_calls': 0, 'model_calls': 0, 'maximum_generations': 4,
        'maximum_optimizer_steps': 128, 'maximum_notebook_wall_seconds': 3600,
        'required_quota_reservation_hours': 2.5, 'manual_ui_only': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('stage', 'preflight'))
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--run-id')
    parser.add_argument('--admission', type=Path)
    args = parser.parse_args()
    print(json.dumps(stage(args.package, args.run_id, args.admission) if args.action == 'stage'
                     else preflight(args.package)))
