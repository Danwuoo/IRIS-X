"""Build/verify a fresh exact Stage 4 full-input candidate, entirely offline.

No competition API, credential access, publication or journal reuse. An inert
package is preparation, not a selected scientific candidate or GPU evidence.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zlib

# A packaged verifier must never add __pycache__ members to its own immutable
# build-source inventory, even when the caller omits Python's -B flag.
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_multitask import canonical, digest, require, write
from tools.nvarc_native_submission import reject_truth
from tools.nvarc_official_render import bridge
from tools.nvarc_notebook_controls import provider_cap_fields
from tools.stage_nvarc_e10_screen import (EXTERNAL_FILES, CONFIG_FIELDS, read_materials,
    validate_baseline, rendered_worker, material_files, native_notice_closure)

FORMAT = 'irisx/stage4-full-input-candidate-v1'
LOCAL_FILES = (
    'tools/arc_kaggle_submission.py', 'tools/nvarc_native_solve_runtime.py', 'tools/nvarc_native_multitask.py',
    'tools/nvarc_native_submission.py', 'tools/nvarc_native_export.py', 'tools/nvarc_output_lifecycle.py',
    'tools/nvarc_allocation_transport.py', 'tools/nvarc_public_eval.py', 'tools/nvarc_public_eval_parent.py',
    'tools/nvarc_official_adapter.py', 'tools/nvarc_official_parent.py', 'tools/nvarc_stage4_parent.py',
    'tools/stage_nvarc_stage4_candidate.py', 'tools/stage_nvarc_e10_screen.py',
    'tools/nvarc_original_native_ttt_worker.py', 'tools/nvarc_native_multitask_render.py',
    'tools/nvarc_official_render.py', 'tools/nvarc_native_ttt_budget.py', 'tools/nvarc_native_ttt_schedule.py',
    'tools/nvarc_calibration_gate.py', 'tools/nvarc_process_supervisor.py', 'tools/nvarc_source_verification.py',
    'tools/nvarc_resource_observer.py', 'tools/nvarc_guarded_cpu.py', 'tools/nvarc_resource_attachment.py',
    'tools/nvarc_notebook_controls.py')
PRODUCER_PATHS = {'worker': 'inspection.py', 'helper': 'inspection_helpers.py',
    'budget': 'nvarc_native_ttt_budget.py', 'schedule': 'nvarc_native_ttt_schedule.py',
    'solve_runtime': 'tools/nvarc_native_solve_runtime.py', 'multitask': 'tools/nvarc_native_multitask.py',
    'bridge': 'tools/nvarc_native_submission.py', 'exporter': 'tools/arc_kaggle_submission.py'}
POLICY = {'verification_schedule': 'interleaved', 'maximum_notebook_wall_seconds': 42600,
    'initial_preparation_seconds': 900, 'packaging_reserve_seconds': 1800,
    'scheduler_reserve_seconds': 300, 'maximum_export_process_seconds': 1200,
    'minimum_free_working_bytes': 20*1024**3}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_snapshot(root, source_commit):
    require(re.fullmatch('[0-9a-f]{40}', source_commit or ''), 'full source commit required')
    result = {}
    for name in LOCAL_FILES:
        committed = subprocess.run(['git', 'show', source_commit+':'+name], cwd=root, capture_output=True, check=True).stdout
        path = Path(root)/name
        require(not path.is_symlink() and path.read_bytes() == committed,
                'exact committed Stage4 source required: '+name)
        result[name] = committed
    return result


def render_from_snapshot(sources):
    # Rendering is pure source transformation; no historical notebook executes.
    with tempfile.TemporaryDirectory(prefix='stage4-render-') as directory:
        root = Path(directory)
        path = root/'tools/nvarc_original_native_ttt_worker.py'; path.parent.mkdir()
        path.write_bytes(sources['tools/nvarc_original_native_ttt_worker.py'])
        return rendered_worker(source_root=root)


def validate_policy(policy):
    require(set(policy) == set(POLICY) and policy['verification_schedule'] in ('interleaved', 'deferred') and
        all(type(policy[key]) is int and policy[key] > 0 for key in set(POLICY)-{'verification_schedule'}) and
        policy['initial_preparation_seconds']+policy['packaging_reserve_seconds']+policy['scheduler_reserve_seconds'] <
        policy['maximum_notebook_wall_seconds'] and
        policy['maximum_export_process_seconds'] <= policy['packaging_reserve_seconds'],
        'finite full-input preparation/scheduler/finalization policy required')


def validate_controller_admission(admission, run_id):
    # External receipts are byte-bound, not authenticated or inferred here.
    require(isinstance(admission, dict) and set(admission) == {'decision', 'run_id', 'execution_plan_digest',
        'current_free_resource_check_sha256', 'material_rules_check_sha256', 'paid_usd', 'private'} and
        admission['decision'] == '0061' and admission['run_id'] == run_id and type(admission['paid_usd']) is int and admission['paid_usd'] == 0 and
        admission['private'] is True and re.fullmatch('sha256:[0-9a-f]{64}', admission['execution_plan_digest']) and
        all(re.fullmatch('[0-9a-f]{64}', admission[key]) for key in
            ('current_free_resource_check_sha256', 'material_rules_check_sha256')),
        'independently reviewed finite private free execution admission required')


def construct(run_id, source_commit, external, config, contract, sources, *, policy=None, admission=None):
    require(re.fullmatch('stage4-full-input-[a-z0-9-]+', run_id or '') and
        re.fullmatch('[0-9a-f]{40}', source_commit or ''), 'new Stage4 identity/full commit required')
    require(set(sources) == set(LOCAL_FILES), 'closed Stage4 source snapshot required')
    policy = dict(POLICY if policy is None else policy); validate_policy(policy)
    validate_baseline(config, external, contract)
    reject_truth(config); reject_truth(contract)
    notice_closure = native_notice_closure(contract, external)
    if admission is not None:
        require(notice_closure, 'native source license/notice closure required before candidate admission')
        validate_controller_admission(admission, run_id)
    for name, body in sources.items(): ast.parse(body, filename=name)
    payload = dict(sources); payload.update(external)
    payload['tools/nvarc_native_submission.py'] = bridge(payload['tools/nvarc_native_submission.py'])
    payload['inspection.py'] = render_from_snapshot(sources)
    for name in ('nvarc_native_ttt_budget.py', 'nvarc_native_ttt_schedule.py'):
        payload[name] = sources['tools/'+name]
    payload['tools/__init__.py'] = b''
    payload['material-contract.json'] = canonical(contract)
    payload['source-config.json'] = canonical(config)
    producer_files = {key: hashlib.sha256(payload[name]).hexdigest() for key, name in PRODUCER_PATHS.items()}
    candidate = dict(config)
    candidate.update(format=FORMAT, run_id=run_id, kernel_id='danielwuu/'+run_id,
        source_commit=source_commit, owner_decision='Decision 0061', official_score_scope=False,
        official_submission_authorized=False, maximum_formal_submissions=0,
        approved=admission is not None, controller_admission=admission, maximum_paid_usd=0, maximum_teacher_calls=0,
        pythonhashseed=0, parallel_workers=4, selected_gpu_indices=[0, 1, 2, 3],
        scientific_selection_status='pending independent real GPU comparison and final freeze',
        promotion=False, actual_gpu_timing_measured=False, correctness_scored=False,
        runtime_input_policy='all actual mounted task/test inputs; never preview IDs or evaluator answers',
        source_config_digest=digest(config), material_contract_digest=digest(contract),
        native_notebook_notice_closure=notice_closure,
        producer_files=producer_files, producer_sha256=digest(producer_files),
        source_files_sha256={name: hashlib.sha256(body).hexdigest() for name, body in sorted(sources.items())},
        payload_sha256={name: hashlib.sha256(body).hexdigest() for name, body in sorted(payload.items())},
        export_verification_process='fresh-cpu-startup-hashseed-0',
        export_helper_sha256=hashlib.sha256(payload['tools/nvarc_native_export.py']).hexdigest(),
        output_lifecycle_sha256=hashlib.sha256(payload['tools/nvarc_output_lifecycle.py']).hexdigest(),
        exposure='historically exposed public development; checkpoint training exposure unresolved',
        **policy)
    payload['candidate-plan.json'] = canonical(candidate)
    return candidate, payload


def render(candidate, payload):
    source = 'import base64,hashlib,json,os,signal,subprocess,sys,time,zlib\nfrom pathlib import Path\nSTART=time.monotonic()\n'
    source += 'PACKED='+repr({key: base64.b64encode(zlib.compress(body, 9)).decode() for key, body in sorted(payload.items())})+'\n'
    source += 'HASHES='+repr({key: hashlib.sha256(body).hexdigest() for key, body in sorted(payload.items())})+'\n'
    source += '''candidate=json.loads(zlib.decompress(base64.b64decode(PACKED['candidate-plan.json'])))
if candidate['approved'] is not True or candidate['official_submission_authorized'] is not False:
    raise RuntimeError('inert Stage4 candidate: reviewed private free rehearsal admission required')
work=Path('/kaggle/working')/candidate['run_id'];work.mkdir(exist_ok=False)
for name,packed in PACKED.items():
    decoder=zlib.decompressobj();body=decoder.decompress(base64.b64decode(packed,validate=True),8*1024**2)
    if not decoder.eof or decoder.unused_data or hashlib.sha256(body).hexdigest()!=HASHES[name]:
        raise RuntimeError('bounded exact Stage4 payload differs: '+name)
    path=work/name
    if not path.resolve().is_relative_to(work.resolve()): raise RuntimeError('confined Stage4 payload required')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
paths=[Path(p) for p in sys.path if Path(p).is_absolute() and Path(p).is_relative_to('/kaggle/usr/lib/notebooks')]
matches=[p for p in dict.fromkeys(paths) if (p/'qwen3.patch').is_file()]
if len(paths)>32 or len(matches)!=1: raise RuntimeError('one exact original offline dependency notebook mount required')
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0',PYTHONPATH=str(work),
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',PYTHONIOENCODING='utf-8')
command=[sys.executable,str(work/'tools/nvarc_stage4_parent.py'),'--root',str(work),'--dependency',str(matches[0]),
    '--started',str(START),'--owner-pid',str(os.getpid())]
sys.path.insert(0,str(work))
from tools.nvarc_process_supervisor import supervise
result=supervise(command,env=env,cwd=work,started=START,
    total_seconds=candidate['maximum_notebook_wall_seconds'],cleanup_seconds=60)
if result['returncode']!=0 or result['timed_out'] or not result['confirmed_stopped']:
    raise RuntimeError('Stage4 private rehearsal failed; retain output and independent terminal gates')
'''
    compile(source, 'stage4-candidate-notebook', 'exec')
    return {'nbformat': 4, 'nbformat_minor': 5,
        'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
        'cells': [{'cell_type': 'markdown', 'metadata': {}, 'source': ['Private full-input Stage4 rehearsal.\n',
            'Scientific selection, actual GPU resource evidence and official scoring remain pending.\n',
            'This candidate has no finalized ZIP producer. Retrieve its existing E01 output and native evidence through the Files tab; archive creation or recovery is not provided.\n']},
            {'cell_type': 'code', 'execution_count': None, 'metadata': {}, 'outputs': [], 'source': source.splitlines(keepends=True)}]}


def metadata(candidate):
    return {'id': candidate['kernel_id'], 'title': candidate['run_id'], 'code_file': 'notebook.ipynb',
        'language': 'python', 'kernel_type': 'notebook', 'is_private': True, 'enable_gpu': True,
        'enable_internet': False, 'machine_shape': 'NvidiaL4', 'docker_image': candidate['docker_image'],
        'docker_image_pinning_type': 'original', 'dataset_sources': [],
        'kernel_sources': ['sorokin/pip-install-unsloth-flash-patch'],
        'competition_sources': ['arc-prize-2026-arc-agi-2'], 'model_sources': candidate['model_sources']}


def decoded_notebook(notebook):
    cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
    require(len(cells) == 1 and cells[0]['execution_count'] is None and cells[0]['outputs'] == [],
            'one unexecuted exact notebook cell required')
    values = {}
    for node in ast.parse(''.join(cells[0]['source'])).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ('PACKED', 'HASHES'):
            name = node.targets[0].id
            require(name not in values, 'duplicate notebook payload assignment')
            values[name] = ast.literal_eval(node.value)
    require(set(values) == {'PACKED', 'HASHES'} and set(values['PACKED']) == set(values['HASHES']), 'closed notebook envelope required')
    result = {}
    for name, packed in values['PACKED'].items():
        decoder = zlib.decompressobj(); body = decoder.decompress(base64.b64decode(packed, validate=True), 8*1024**2)
        require(decoder.eof and not decoder.unused_data and hashlib.sha256(body).hexdigest() == values['HASHES'][name],
                'exact bounded notebook payload mismatch')
        result[name] = body
    return result


def verify_runtime_tree(root, *, require_approved=False):
    root = Path(root)
    require(not (root/'candidate-plan.json').is_symlink(), 'regular exact candidate plan required')
    candidate = parse_json((root/'candidate-plan.json').read_bytes())
    require(candidate['format'] == FORMAT and candidate['official_submission_authorized'] is False and
        candidate['maximum_formal_submissions'] == 0 and candidate['promotion'] is False and
        type(candidate['approved']) is bool and (not require_approved or candidate['approved']),
        'distinct private-only candidate required')
    if candidate['approved']: validate_controller_admission(candidate['controller_admission'], candidate['run_id'])
    else: require(candidate['controller_admission'] is None, 'inert candidate cannot carry execution admission')
    require(not root.is_symlink(), 'regular candidate root required')
    for name, expected in candidate['payload_sha256'].items():
        path = root/name
        require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) and sha(path) == expected,
                'exact Stage4 runtime payload differs: '+name)
    if candidate['approved']:
        contract = parse_json((root/'material-contract.json').read_bytes())
        external = {name: (root/name).read_bytes() for name in material_files(contract)}
        require(candidate['native_notebook_notice_closure'] is True and native_notice_closure(contract, external),
                'admitted candidate requires exact native source notice closure')
    return candidate


def cli_handoff(candidate):
    """Commands are inert data. Actual provider/official execution belongs outside."""
    return {'format': 'irisx/stage4-offline-cli-handoff-v1', 'run_id': candidate['run_id'],
        'candidate_digest': digest(candidate), 'journal_policy': 'new coordinator execution ledger identity only',
        **provider_cap_fields(candidate),
        'status_argv': ['kaggle', 'kernels', 'status', candidate['kernel_id']],
        'output_argv_template': ['kaggle', 'kernels', 'output', candidate['kernel_id'], '-p', 'RETAINED-OUTPUT'],
        'official_submission_argv_template': ['kaggle', 'competitions', 'submit', 'arc-prize-2026-arc-agi-2',
            '-k', candidate['kernel_id'], '--version', 'EXACT-REVIEWED-VERSION', '-f', 'submission.json',
            '-m', 'Stage4 selected exact candidate '+candidate['run_id']],
        'official_submission_authorized': False, 'execute_commands': False,
        'required_before_official': ['scientific selection and single confirmation freeze',
            'current rules/licenses/exposure review', 'full-input private GPU completion/resource/exit evidence',
            'exact accepted kernel/version receipt and complete verified retrieval',
            'E01 strict committed generation/projection and independent four-gate review', 'new owner official submission decision']}


def stage(package, candidate, payload, sources):
    package = Path(package); require(not package.exists(), 'new immutable Stage4 package path required')
    package.mkdir(parents=True)
    for prefix, values in (('runtime', payload), ('build-source', sources)):
        for name, body in values.items():
            path = package/prefix/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
    (package/'kernel').mkdir()
    write(package/'kernel/notebook.ipynb', render(candidate, payload))
    write(package/'kernel/kernel-metadata.json', metadata(candidate))
    write(package/'cli-handoff.json', cli_handoff(candidate))
    write(package/'package-manifest.json', {'format': 'irisx/stage4-package-manifest-v1', 'run_id': candidate['run_id'],
        'candidate_digest': digest(candidate), 'files_sha256': {p.relative_to(package).as_posix(): sha(p)
            for p in sorted(package.rglob('*')) if p.is_file()}})
    return preflight(package)


def preflight(package, *, expected_manifest_sha256=None):
    package = Path(package)
    require(expected_manifest_sha256 is None or re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256), 'external manifest SHA256 required')
    if expected_manifest_sha256: require(sha(package/'package-manifest.json') == expected_manifest_sha256, 'externally retained package differs')
    require(not package.is_symlink() and not any(p.is_symlink() for p in package.rglob('*')), 'closed regular Stage4 package required')
    manifest = parse_json((package/'package-manifest.json').read_bytes())
    require(set(manifest) == {'format', 'run_id', 'candidate_digest', 'files_sha256'} and
        manifest['format'] == 'irisx/stage4-package-manifest-v1' and manifest['files_sha256'] ==
        {p.relative_to(package).as_posix(): sha(p) for p in package.rglob('*') if p.is_file() and p != package/'package-manifest.json'},
        'closed immutable package inventory differs')
    candidate = verify_runtime_tree(package/'runtime')
    sources = {name: (package/'build-source'/name).read_bytes() for name in LOCAL_FILES}
    config = parse_json((package/'runtime/source-config.json').read_bytes())
    contract = parse_json((package/'runtime/material-contract.json').read_bytes())
    external = {name: (package/'runtime'/name).read_bytes() for name in material_files(contract)+('verified-tokenizer.json',)}
    expected, payload = construct(candidate['run_id'], candidate['source_commit'], external, config, contract, sources,
        policy={key: candidate[key] for key in POLICY}, admission=candidate['controller_admission'])
    closed_names = {'runtime/'+name for name in payload} | {'build-source/'+name for name in LOCAL_FILES} | {
        'kernel/notebook.ipynb', 'kernel/kernel-metadata.json', 'cli-handoff.json'}
    require(set(manifest['files_sha256']) == closed_names, 'exact closed Stage4 package membership differs')
    notebook = parse_json((package/'kernel/notebook.ipynb').read_bytes())
    require(expected == candidate and manifest['candidate_digest'] == digest(candidate) and manifest['run_id'] == candidate['run_id'] and
        {name: (package/'runtime'/name).read_bytes() for name in payload} == payload and
        notebook == render(candidate, payload) and decoded_notebook(notebook) == payload and
        parse_json((package/'kernel/kernel-metadata.json').read_bytes()) == metadata(candidate) and
        parse_json((package/'cli-handoff.json').read_bytes()) == cli_handoff(candidate), 'exact deterministic candidate reconstruction differs')
    return {'run_id': candidate['run_id'], 'candidate_digest': digest(candidate),
        'package_manifest_sha256': sha(package/'package-manifest.json'), 'offline_package_verified': True,
        'approved_for_private_runtime': candidate['approved'], 'scientific_selection_status': candidate['scientific_selection_status'],
        'official_submission_authorized': False, 'official_scoring_ready': False, 'actual_gpu_timing_measured': False,
        'promotion': False, 'external_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('action', choices=('stage', 'preflight'))
    parser.add_argument('--package', type=Path, required=True); parser.add_argument('--run-id'); parser.add_argument('--source-commit')
    for name in ('materials', 'material-contract', 'template', 'tokenizer', 'policy', 'admission'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--expected-manifest-sha256'); args = parser.parse_args()
    if args.action == 'preflight': result = preflight(args.package, expected_manifest_sha256=args.expected_manifest_sha256)
    else:
        external, config, contract = read_materials(args.materials, args.material_contract, args.template, args.tokenizer)
        candidate, payload = construct(args.run_id, args.source_commit, external, config, contract,
            source_snapshot(ROOT, args.source_commit), policy=load_json_optional(args.policy), admission=load_json_optional(args.admission))
        result = stage(args.package, candidate, payload, source_snapshot(ROOT, args.source_commit))
    print(canonical(result).decode())


def load_json_optional(path): return None if path is None else parse_json(path.read_bytes())


if __name__ == '__main__': main()
