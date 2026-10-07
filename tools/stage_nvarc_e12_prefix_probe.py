"""Build an inert E12 prefix probe from exact immutable v9 material bytes.

Offline only. No provider query, publication, quota assertion, model import or
GPU work. The default notebook branch performs no setup or filesystem writes.
"""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from tools import nvarc_e12_admission as owner
from tools import stage_nvarc_e11_owner_editor as historical
from tools.nvarc_native_multitask import canonical, digest, require, write
from tools.nvarc_native_submission import reject_truth
from tools.arc_kaggle_submission import parse_json
from tools.stage_nvarc_e10_screen import sha

RUN_ID = owner.RUN_ID
NOTEBOOK = historical.NOTEBOOK
SCOPE = historical.SCOPE
WORKER_PATH = 'tools/nvarc_e12_entry.py'
FROZEN_PLAN = 'frozen-v9-plan.json'
FROZEN_PLAN_SHA256 = '4267c77e4a68f16415832b80b5219fa9f0261664a97d83d7602d7a2ea7d31183'
FROZEN_SOURCE_COMMIT = 'c946719b0714b8dbf0ab13a03c76efc144e05d60'
NEW_FILES = ('tools/stage_nvarc_e12_prefix_probe.py', 'tools/nvarc_e12_admission.py',
    'tools/nvarc_e12_entry.py', 'tools/nvarc_e12_prefix_contract.py',
    'tools/nvarc_e12_training.py', 'tools/nvarc_e12_runtime.py',
    'tools/nvarc_e12_answer_evidence.py', 'tools/nvarc_e12_cleanup.py',
    'tools/nvarc_e12_archive.py', 'tools/nvarc_e12_delivery_envelope.py',
    'tools/nvarc_e12_output_lifecycle.py')
FILES = tuple(sorted(set(historical.FILES) | set(NEW_FILES)))
FALSE_FIELDS = historical.core.FALSE_FIELDS


def runtime_api():
    from tools import nvarc_e12_runtime
    return nvarc_e12_runtime


def verify_worker_result(*args, **kwargs):
    return runtime_api().verify_worker_result(*args, **kwargs)


def seal_outputs(*args, **kwargs):
    return runtime_api().seal_outputs(*args, **kwargs)


def record_worker_launch(*args, **kwargs):
    return runtime_api().record_worker_launch(*args, **kwargs)


def validate_admission(plan, *, required=False, root=None):
    owner.scope(plan)
    require(canonical(plan.get('owner_editor_admission')) == canonical(owner.admission(plan)),
        'exact optional owner E12 admission contract required')
    if required:
        require(root is not None, 'E12 confirmation root required')
        owner.verify_confirmation(root, plan)
    runtime_api().profile_for_plan(plan)


def exact_sources(commit):
    require(type(commit) is str and re.fullmatch('[0-9a-f]{40}', commit),
        'full committed E12 source required')
    result = {}
    for name in FILES:
        path = ROOT / name
        require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
            'regular E12 implementation source required')
        body = subprocess.run(['git', 'show', commit + ':' + name], cwd=ROOT,
            capture_output=True, check=True).stdout
        require(body == path.read_bytes(), 'exact committed E12 source differs: ' + name)
        tree = ast.parse(body, filename=name); result[name] = body
        if name in NEW_FILES:
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = ([a.name.split('.')[0] for a in node.names] if isinstance(node, ast.Import)
                        else [(node.module or '').split('.')[0]])
                    require(not set(names) & {'torch', 'numpy', 'tokenizers', 'unsloth', 'transformers', 'peft'},
                        'native imports must remain behind E12 owner confirmation')
    return result


def _verify_frozen_plan(parent):
    require(hashlib.sha256(canonical(parent)).hexdigest() == FROZEN_PLAN_SHA256 and
        parent['source_commit'] == FROZEN_SOURCE_COMMIT and
        set(parent['source_files_sha256']) == set(historical.FILES),
        'exact immutable v9 owner-Editor parent required')


def _verify_frozen(parent, frozen_payload):
    _verify_frozen_plan(parent)
    require(set(frozen_payload) == set(parent['payload_sha256']) and
        all(hashlib.sha256(body).hexdigest() == parent['payload_sha256'][name]
            for name, body in frozen_payload.items()), 'all original v9 runtime bytes must be retained exactly')


def construct(commit, parent, frozen_payload, sources):
    require(type(commit) is str and re.fullmatch('[0-9a-f]{40}', commit),
        'full committed E12 source identity required')
    _verify_frozen(parent, frozen_payload)
    require(set(sources) == set(FILES) and all(type(body) is bytes for body in sources.values()),
        'closed E12 implementation inventory required')
    require(all(sources[name] == frozen_payload[name] for name in historical.FILES),
        'historical source lineage must remain byte-identical')
    runtime = runtime_api()
    plan = copy.deepcopy(parent)
    plan.pop('e11_process_policy', None)
    plan.update(format=runtime.FORMAT, run_id=RUN_ID, screen_id=RUN_ID, source_commit=commit,
        generation_budget_profile=runtime.PROFILE, resource_budget_profile=runtime.BUDGET_PROFILE,
        **runtime.TIMING, **runtime.CAPS,
        maximum_training_forwards=768, maximum_training_backwards=768, optimizer_steps=768,
        per_worker_training_steps=192,
        maximum_training_input_tokens=2 * parent['maximum_training_input_tokens'],
        maximum_training_supervised_tokens=2 * parent['maximum_training_supervised_tokens'],
        training_token_cap_policy='conservative two-full-epoch bound; actual 64-row sampler prefix plus full128 recorded independently',
        e12_process_policy=dict(runtime.PROCESS_POLICY), cleanup_reserve_seconds=310,
        retained_model_layout=dict(runtime.MODEL_LAYOUT),
        arm_contracts={arm: runtime.arm_contract(arm) for arm in runtime.ARMS},
        arm_order=runtime.counterbalanced_order(parent['test_counts']),
        per_arm_caps=dict(runtime.PER_ARM_CAPS),
        verification_schedule='interleaved', verification_schedules=['interleaved'],
        expected_notebook_version=10, expected_previous_version=9,
        expected_previous_script_version_id=None,
        test_executions=12,
        training_reuse='independent baseline reset before each arm; immutable128-row dataset and native full-horizon128 sampler; stop after64 or128 updates',
        scientific_factor='task-local optimizer update prefix only:64 versus128; both p02=.2 INTERLEAVED',
        rng_policy='restore common baseline Python, NumPy, torch CPU and CUDA streams before each independent training arm; retain and compare actual sampler order',
        qualification_policy='resource/output evidence only; exact independent baseline resets, same full128 sampler prefix, full-horizon native scheduler and per-arm inference state preservation; separate six-test denominators; no quality or cost-reduction claim',
        output_policy='atomic prefix comparison envelope with separate per-arm exposed answers/audits and native training/reset receipts; explicit null missing slots; no official submission JSON',
        source_replay_policy='independent native64-prefix and128-control; formatter/verifier/ranker CPU replay is not native logit numerical replay',
        paired_resource_proposal=runtime.budget_report(),
        resource_admission=None, owner_editor_only=True, kernel_execution_type='INERT',
        owner_editor_admission=None, local_fixture=False,
        **{key: False for key in FALSE_FIELDS})
    plan['lineage']['historical_v9'] = dict(run_id=parent['run_id'], source_commit=FROZEN_SOURCE_COMMIT,
        plan_sha256=FROZEN_PLAN_SHA256, notebook_version=9, retained_plan=FROZEN_PLAN,
        authority_inherited=False)
    plan['lineage']['repair'] = 'new prefix experiment; no historical source, material, solver or dependency mutation'
    raw = dict(frozen_payload)
    raw.update(sources)
    raw[FROZEN_PLAN] = canonical(parent)
    plan['source_files_sha256'] = {name: hashlib.sha256(body).hexdigest()
        for name, body in sorted(sources.items())}
    plan['payload_sha256'] = {name: hashlib.sha256(body).hexdigest()
        for name, body in sorted(raw.items())}
    plan['owner_editor_admission'] = owner.admission(plan)
    validate_admission(plan); reject_truth(plan)
    raw['plan.json'] = raw['screen.json'] = canonical(plan)
    return plan, raw


def verify_runtime(root, *, require_approved=False):
    root = Path(root)
    require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)),
        'regular E12 runtime root required')
    plan = parse_json((root / 'plan.json').read_bytes())
    require((root / 'plan.json').read_bytes() == (root / 'screen.json').read_bytes() == canonical(plan),
        'identical canonical E12 plan/screen required')
    validate_admission(plan, required=require_approved, root=root)
    require(set(plan['source_files_sha256']) == set(FILES) and set(FILES) <= set(plan['payload_sha256']),
        'closed E12 source and payload inventory required')
    for name, expected in plan['payload_sha256'].items():
        path = root / name
        require(path.resolve().is_relative_to(root.resolve()) and path.is_file() and
            not any(p.is_symlink() for p in (path, *path.parents)) and sha(path) == expected,
            'immutable E12 payload differs: ' + name)
    parent = parse_json((root / FROZEN_PLAN).read_bytes())
    _verify_frozen_plan(parent)
    frozen = {name: (root / name).read_bytes() for name in parent['payload_sha256']}
    sources = {name: (ROOT / name).read_bytes() for name in FILES}
    expected, raw = construct(plan['source_commit'], parent, frozen, sources)
    require(plan == expected and all((root / name).read_bytes() == body for name, body in raw.items()),
        'exact E12 source/material/plan reconstruction differs')
    return plan


def branch(body, message):
    return ('if type(globals().get(' + repr(owner.CONFIG_NAME) + ')) is not bool or globals().get(' +
        repr(owner.CONFIG_NAME) + ') is not True:\n    print(' + repr(message) + ')\nelse:\n' +
        ''.join('    ' + line if line.strip() else line for line in body.splitlines(keepends=True)))


def configuration_cell():
    return ('# Set True only to authorize this exact E12 run001 once in a fresh Editor session.\n'
        '# True declares acceptance of the original sorokin V2 / Qwen / Torch / Unsloth / FlashAttention native stack and offline setup,\n'
        '# that you personally checked at least 4 free GPU-hours, no conflicting reservation, and pay-to-scale OFF,\n'
        '# and that you will stop the Editor session after downloading.\n'
        '# The 60-minute (3600-second) watchdog is INTERNAL, not a provider-enforced session limit.\n'
        + owner.CONFIG_NAME + ' = False\n'
        + 'if ' + owner.CONFIG_NAME + ' is not True:\n    print(' + repr(owner.NO_RUN) + ')\n')


def embedded_body(notebook):
    tree = ast.parse(''.join(notebook['cells'][2]['source']))
    require(len(tree.body) == 1 and isinstance(tree.body[0], ast.If),
        'one explicit E12 owner execution branch required')
    expected = ast.parse(branch('pass\n', owner.NO_RUN)).body[0]
    require(ast.dump(tree.body[0].test) == ast.dump(expected.test) and
        ast.dump(ast.Module(body=tree.body[0].body, type_ignores=[])) ==
        ast.dump(ast.Module(body=expected.body, type_ignores=[])),
        'default E12 config must print without imports or setup')
    return ast.unparse(ast.Module(body=tree.body[0].orelse, type_ignores=[])) + '\n'


def verify_embedded_payload(notebook, raw):
    require(len(notebook['cells']) == 4 and
        ''.join(notebook['cells'][1]['source']) == configuration_cell(),
        'exact disclosure/config/execution/download with literal False required')
    body = embedded_body(notebook)
    historical.core.ancestor.ancestor.verify_embedded_payload(
        {'cells': [{}, {'source': body.splitlines(keepends=True)}]}, raw)


def _replace_once(body, old, new):
    require(body.count(old) == 1, 'one exact historical notebook hook required: ' + old[:90])
    return body.replace(old, new, 1)


def delivery_download_body(plan, raw):
    """Read only; execute only separately hash-bound, staged checker source."""
    name = 'tools/nvarc_e12_delivery_envelope.py'
    checker = raw[name]
    header = ("import hashlib,os,stat,types\nfrom pathlib import Path\n"
        'DOWNLOAD_RUN_ID=' + repr(RUN_ID) + '\n'
        'DOWNLOAD_PLAN_SHA256=' + repr(hashlib.sha256(canonical(plan)).hexdigest()) + '\n'
        'DOWNLOAD_CHECKER_SHA256=' + repr(hashlib.sha256(checker).hexdigest()) + '\n'
        'DOWNLOAD_CHECKER_BYTES=' + repr(len(checker)) + '\n'
        "DOWNLOAD_PATH=Path('/kaggle/working')/(DOWNLOAD_RUN_ID+'-delivery.zip')\n")
    return header + '''if not DOWNLOAD_PATH.is_file():
    print('No finalized delivery bundle is available yet. No run, rebuild or recovery has been started by this cell.')
else:
    _checker_path=DOWNLOAD_PATH.parent/DOWNLOAD_RUN_ID/'tools/nvarc_e12_delivery_envelope.py'
    if any(p.is_symlink() for p in (_checker_path,*_checker_path.parents)):
        raise RuntimeError('regular exact staged download checker required')
    if not getattr(os,'O_NOFOLLOW',0): raise RuntimeError('no-follow checker open required')
    with os.fdopen(os.open(_checker_path,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW),'rb') as _stream:
        _before=os.fstat(_stream.fileno())
        if not stat.S_ISREG(_before.st_mode) or _before.st_nlink!=1 or _before.st_size!=DOWNLOAD_CHECKER_BYTES:
            raise RuntimeError('exact bounded staged download checker required')
        _checker_body=_stream.read(DOWNLOAD_CHECKER_BYTES+1)
        if len(_checker_body)!=DOWNLOAD_CHECKER_BYTES or hashlib.sha256(_checker_body).hexdigest()!=DOWNLOAD_CHECKER_SHA256:
            raise RuntimeError('staged download checker bytes differ')
    # Execute the exact embedded-source digest, never code from the returned ZIP.
    _checker=types.ModuleType('irisx_e12_verified_download')
    exec(compile(_checker_body,str(_checker_path),'exec'),_checker.__dict__)
    _checker.verify_envelope(DOWNLOAD_PATH.parent,run_id=DOWNLOAD_RUN_ID,plan_sha256=DOWNLOAD_PLAN_SHA256)
    print('Exact-run delivery bundle verified. It includes the unchanged runtime ZIP and separate post-write evidence; this does not establish model quality or promotion.')
    from IPython.display import FileLink,display
    display(FileLink(str(DOWNLOAD_PATH)))
    print('After downloading, STOP THE EDITOR SESSION. The internal watchdog is not a provider session timeout.')
'''


def render(plan, raw):
    validate_admission(plan)
    require(raw.get('plan.json') == raw.get('screen.json') == canonical(plan),
        'exact E12 plan/screen bytes required')
    require(plan['payload_sha256'] == {name: hashlib.sha256(body).hexdigest()
        for name, body in raw.items() if name not in ('plan.json', 'screen.json')},
        'exact E12 embedded payload inventory required')
    from tools.stage_nvarc_e10_ttt_probe import render as training_render
    # Its old download cell has an E10/E11 identity allowlist. Use the scaffold
    # with a temporary alias, then replace that cell with E12's bound envelope
    # checker. The actual PACKED runtime always contains the real E12 plan.
    template_plan = dict(plan, screen_id=historical.RUN_ID)
    notebook = training_render(template_plan, raw)
    body = ''.join(notebook['cells'][1]['source'])
    hook = "screen=json.loads(zlib.decompress(base64.b64decode(PACKED['screen.json'])))\n"
    pin = hashlib.sha256(canonical(plan)).hexdigest()
    guard = ("if hashlib.sha256(zlib.decompress(base64.b64decode(PACKED['screen.json']))).hexdigest()!=" + repr(pin) + ":\n"
        "    raise RuntimeError('exact E12 plan bytes differ before setup')\n"
        "if HASHES!=dict(screen['payload_sha256'],**{'plan.json':" + repr(pin) + ",'screen.json':" + repr(pin) + "}) or set(PACKED)!=set(HASHES):\n"
        "    raise RuntimeError('exact E12 packed inventory differs before setup')\n")
    body = _replace_once(body, hook, hook + guard)
    old = ("owner_editor=(screen.get('approved_for_owner_editor') is True and screen.get('owner_editor_only') is True\n"
        "    and screen.get('agent_execution_authorized') is False and screen.get('kernel_execution_type')=='QUICK_SAVE')\n"
        "if (screen['approved_for_runtime'] is not True and not owner_editor) or screen['local_fixture'] is not False:\n"
        "    raise RuntimeError('inert E10 package: current free resource/materials admission required')\n")
    body = _replace_once(body, old,
        "if screen['kernel_execution_type']!='INERT' or screen['local_fixture'] is not False:\n"
        "    raise RuntimeError('exact inert E12 package required')\n")
    hook = 'paths=[Path(path) for path in sys.path'
    body = _replace_once(body, hook,
        "sys.path.insert(0,str(work))\nfrom tools.nvarc_e12_admission import write_confirmation\n"
        "write_confirmation(work,screen," + owner.CONFIG_NAME + ",START)\n" + hook)
    body = _replace_once(body, "str(work/'tools/nvarc_e10_ttt_probe.py'),'--bootstrap','--root'",
        "str(work/'tools/nvarc_e12_entry.py'),'--bootstrap','--root'")
    body = _replace_once(body, 'from tools.nvarc_e10_ttt_probe import finalize',
        'from tools.nvarc_e12_runtime import finalize')
    body = _replace_once(body, 'from tools.nvarc_process_supervisor import supervise',
        'from tools.nvarc_e12_cleanup import supervise')
    body = _replace_once(body, "or not diagnostics.get('final_archive_created'):",
        "or not diagnostics.get('final_archive_created') or not diagnostics.get('finalization_qualified') or diagnostics.get('delivery_bundle_created') is not True:")
    body = _replace_once(body,
        "HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',PYTHONIOENCODING='utf-8')",
        "HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',PYTHONIOENCODING='utf-8',\n"
        "    OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TOKENIZERS_PARALLELISM='false',UNSLOTH_DISABLE_STATISTICS='1',WANDB_DISABLED='true')")
    body = _replace_once(body, 'E10 screen incomplete or failed; retain exact terminal and evidence',
        'E12 calibration incomplete or failed; retain exact terminal and evidence')
    require("capture_path=work/'coordinator-output.log'" in body,
        'bounded historical coordinator stdout capture required')
    start_hook = 'paths=[Path(path) for path in sys.path'
    end_hook = "code=observation['returncode']\n"
    require(body.count(start_hook) == body.count(end_hook) == 1,
        'one exact E12 discovery/dispatch region required')
    start, end = body.index(start_hook), body.index(end_hook)
    bootstrap = body[start:end]
    bootstrap = _replace_once(bootstrap, 'from tools.nvarc_e12_cleanup import supervise\n', '')
    bootstrap = _replace_once(bootstrap, 'observation=supervise(command,',
        '_launch_dispatched=True\nobservation=supervise(command,')
    # A known setup failure can retain diagnostics after the complete immutable
    # runtime was unpacked. Once supervision is dispatched, its own observation
    # owns process state; never relabel an unexpected supervisor error as no-launch.
    bootstrap = ('from tools.nvarc_e12_cleanup import supervise,prelaunch_failure\n'
        '_launch_dispatched=False\ntry:\n' + ''.join(
            '    ' + line if line.strip() else line for line in bootstrap.splitlines(keepends=True)) +
        'except BaseException as _prelaunch_error:\n'
        '    if _launch_dispatched: raise\n'
        "    observation=prelaunch_failure(work/'coordinator-output.log',started=START,error=_prelaunch_error)\n")
    body = body[:start] + bootstrap + body[end:]
    body = _replace_once(body, "destination=work.parent/(screen['screen_id']+'.zip')",
        "destination=work.parent/(screen['screen_id']+'-delivery.zip')")
    body = _replace_once(body, 'if destination.is_file(): display(FileLink(str(destination)))',
        "if diagnostics.get('delivery_bundle_created') is True and diagnostics.get('delivery_bundle_path')==str(destination) and destination.is_file():\n"
        "    display(FileLink(str(destination)))")
    download = delivery_download_body(plan, raw)
    code = lambda text: dict(cell_type='code', metadata={}, execution_count=None,
        outputs=[], source=text.splitlines(keepends=True))
    notebook['cells'] = [dict(cell_type='markdown', metadata={}, source=[
        'E12 64/128 training-prefix calibration; saved without running.\n',
        'The visible confirmation defaults to False. Review the exact scope, set True yourself, then Run All once in a fresh Editor session.\n',
        'Private, Internet off, exactly four NVIDIA L4 GPUs, USD 0. Same sorokin dependency notebook V2, Qwen modification and pinned Qwen3 4B SFT139 model, including Torch, Unsloth and mjun0812 FlashAttention with the existing offline setup. Selected bytes are pinned; this is not a new full-stack certification.\n',
        'Independent baseline resets compare 64 versus 128 native updates. Both use the immutable 128-row dataset, full 128-update native scheduler horizon and 13-update warmup; 768 updates total. Each GPU retains one NativeEngine.\n',
        'Both arms use p02=.2 and INTERLEAVED verification: six tests per arm, 12 test executions total. Each test retains 120 generation seconds and 150 total seconds.\n',
        'The fixed 60-minute/3600-second limit is an INTERNAL watchdog, not a provider-enforced Editor timeout. The four-GPU reservation costs up to 4 free GPU-hours; there is no 45-minute fallback and no completion promise.\n',
        'Before confirming, personally check at least 4 free GPU-hours, no conflicting reservation, and pay-to-scale OFF. These are your declarations, not independent provider quota or paid-settings attestations.\n',
        'After downloading, STOP THE EDITOR SESSION. Do not rerun or reuse this identity. No teacher, evaluator truth, official scoring, submission or promotion is enabled.\n']),
        code(configuration_cell()), code(branch(body, owner.NO_RUN)),
        code(branch(download, 'No run was confirmed. This read-only cell will not set up or start anything.'))]
    for cell in notebook['cells'][1:]:
        compile(''.join(cell['source']), 'e12-owner-editor-cell', 'exec')
    verify_embedded_payload(notebook, raw)
    return notebook


def metadata(plan):
    return historical.metadata(plan)


def handoff(plan):
    validate_admission(plan)
    return dict(format='irisx/e12-inert-owner-handoff-v1', run_id=RUN_ID,
        notebook_ref=NOTEBOOK, notebook_numeric_id=137327571,
        expected_notebook_version=10, expected_previous_version=9,
        expected_previous_script_version_id=None, kernel_execution_type='INERT',
        publication_authorized=False, publication_authorization_ref=None,
        agent_execution_authorized=False, runtime_authorized=False,
        owner_config_required=True, config_name=owner.CONFIG_NAME, default_config_value=False,
        execution_chat_ref=None, resource_admission=None,
        owner_declarations_are_independent_attestations=False,
        provider_editor_timeout_attested=False, internal_watchdog_seconds=3600,
        planned_charged_gpu_seconds_ceiling=14400, minimum_free_gpu_hours=4,
        training_updates=768, test_executions=12, execute_commands=False,
        monitor_after_submission=False, official_submission_authorized=False, paid_usd_ceiling=0)


def package_manifest(plan, raw):
    files = {'runtime/' + name: body for name, body in raw.items()}
    files.update({'kernel/notebook.ipynb': canonical(render(plan, raw)),
        'kernel/kernel-metadata.json': canonical(metadata(plan)),
        'cli-handoff.json': canonical(handoff(plan))})
    return dict(format='irisx/e12-inert-owner-package-v1', plan_digest=digest(plan),
        files_sha256={name: hashlib.sha256(body).hexdigest() for name, body in sorted(files.items())})


def stage(package, plan, raw):
    package = Path(package)
    require(not package.exists(), 'new immutable E12 package required')
    (package / 'kernel').mkdir(parents=True)
    for name, body in raw.items():
        path = package / 'runtime' / name
        require(path.resolve().is_relative_to((package / 'runtime').resolve()), 'confined E12 payload required')
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
    write(package / 'kernel/notebook.ipynb', render(plan, raw))
    write(package / 'kernel/kernel-metadata.json', metadata(plan))
    write(package / 'cli-handoff.json', handoff(plan))
    write(package / 'package-manifest.json', package_manifest(plan, raw))
    return preflight(package)


def preflight(package, *, expected_manifest_sha256=None):
    package = Path(package); manifest = parse_json((package / 'package-manifest.json').read_bytes())
    require(not any(p.is_symlink() for p in (package, *package.parents, *package.rglob('*'))) and
        manifest['files_sha256'] == {p.relative_to(package).as_posix(): sha(p)
            for p in package.rglob('*') if p.is_file() and p != package / 'package-manifest.json'},
        'closed immutable E12 package required')
    if expected_manifest_sha256 is not None:
        require(sha(package / 'package-manifest.json') == expected_manifest_sha256, 'independent E12 manifest pin differs')
    plan = verify_runtime(package / 'runtime'); sources = exact_sources(plan['source_commit'])
    require(plan['source_files_sha256'] == {name: hashlib.sha256(body).hexdigest()
        for name, body in sources.items()}, 'committed E12 sources differ')
    raw = {name: (package / 'runtime' / name).read_bytes()
        for name in (*plan['payload_sha256'], 'plan.json', 'screen.json')}
    require(manifest == package_manifest(plan, raw) and
        parse_json((package / 'kernel/notebook.ipynb').read_bytes()) == render(plan, raw) and
        parse_json((package / 'kernel/kernel-metadata.json').read_bytes()) == metadata(plan) and
        parse_json((package / 'cli-handoff.json').read_bytes()) == handoff(plan),
        'exact E12 notebook/metadata/handoff differs')
    require(not (package / 'runtime' / owner.CONFIRMATION_FILE).exists(),
        'staged E12 package cannot fabricate owner runtime confirmation')
    return dict(run_id=RUN_ID, plan_digest=digest(plan),
        package_manifest_sha256=sha(package / 'package-manifest.json'),
        offline_package_verified=True, publication_mode='INERT', publication_authorized=False,
        agent_execution_authorized=False, runtime_authorized=False, owner_config_required=True,
        new_model_calls=0, new_provider_calls=0, gpu_probe_run=False)


def build_from_frozen(package, frozen_runtime, commit):
    root = Path(frozen_runtime)
    require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents, *root.rglob('*'))),
        'regular immutable frozen v9 runtime required')
    parent = parse_json((root / 'plan.json').read_bytes())
    require((root / 'plan.json').read_bytes() == (root / 'screen.json').read_bytes() == canonical(parent),
        'canonical exact frozen v9 plan/screen required')
    _verify_frozen_plan(parent)
    payload = {name: (root / name).read_bytes() for name in parent['payload_sha256']}
    plan, raw = construct(commit, parent, payload, exact_sources(commit))
    return stage(package, plan, raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('stage', 'preflight'))
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--frozen-runtime', type=Path)
    parser.add_argument('--source-commit')
    parser.add_argument('--expected-manifest-sha256')
    args = parser.parse_args()
    if args.action == 'stage':
        require(args.frozen_runtime is not None and args.source_commit is not None,
            'frozen v9 runtime and full committed E12 source required')
        result = build_from_frozen(args.package, args.frozen_runtime, args.source_commit)
    else:
        result = preflight(args.package, expected_manifest_sha256=args.expected_manifest_sha256)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
