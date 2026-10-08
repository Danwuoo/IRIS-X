"""Separate E11 QUICK_SAVE package; only explicit owner config can enable work."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tools import stage_nvarc_e11_paired_floor as core
from tools import nvarc_e11_owner_editor as owner
from tools.nvarc_e11_paired_floor import (profile_for_plan,OWNER_BUDGET_45,verify_worker_result,
    seal_outputs,record_worker_launch,budget_report)
from tools.nvarc_native_multitask import canonical,digest,require,write
from tools.arc_kaggle_submission import parse_json
from tools.nvarc_native_submission import reject_truth
from tools.stage_nvarc_e10_screen import CONFIG_FIELDS,material_files,sha
from tools.nvarc_dependency_readproof import PROOF_FILE,read_contract

RUN_ID=owner.RUN_ID
NOTEBOOK=core.NOTEBOOK
SCOPE=core.SCOPE
WORKER_PATH='tools/nvarc_e11_owner_editor_entry.py'
NEW_FILES=('tools/nvarc_e11_owner_editor.py','tools/nvarc_e11_owner_editor_entry.py','tools/stage_nvarc_e11_owner_editor.py')
FILES=tuple(sorted(set(core.FILES)|set(NEW_FILES)))
OWNER_TRUE_FIELDS={'approved_for_owner_editor','publication_authorized'}


def validate_admission(plan,*,required=False,root=None):
    profile_for_plan(plan)
    require(plan.get('run_id')==RUN_ID and plan.get('resource_budget_profile')==OWNER_BUDGET_45 and
        plan.get('kernel_execution_type')=='QUICK_SAVE' and plan.get('owner_editor_only') is True and
        plan.get('local_fixture') is False and plan.get('resource_admission') is None and
        canonical(plan.get('owner_editor_admission'))==canonical(owner.admission(plan)) and
        all(plan.get(key) is (key in OWNER_TRUE_FIELDS) for key in core.FALSE_FIELDS),
        'exact publication-only owner-Editor admission with agent execution disabled required')
    if required:
        require(root is not None,'owner confirmation root required')
        owner.verify_confirmation(root,plan)


def exact_sources(commit):
    require(re.fullmatch('[0-9a-f]{40}',commit or ''),'full committed owner-Editor source required')
    result={}
    for name in FILES:
        path=ROOT/name;require(not path.is_symlink(),'regular source required')
        body=subprocess.run(['git','show',commit+':'+name],cwd=ROOT,capture_output=True,check=True).stdout
        require(body==path.read_bytes(),'exact committed owner-Editor source differs: '+name)
        tree=ast.parse(body,filename=name);result[name]=body
        if name in NEW_FILES:
            for node in tree.body:
                if isinstance(node,(ast.Import,ast.ImportFrom)):
                    names=[a.name.split('.')[0] for a in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]]
                    require(not set(names)&{'torch','numpy','tokenizers','unsloth','transformers','peft'},
                        'native dependencies must remain behind owner confirmation')
    core.ancestor.ancestor.native_symbol_guard({name:result[name] for name in core.ancestor.ancestor.FILES})
    return result


def construct(commit,external,config,contract,challenges,materials,proof,preprocessing_environment,sources):
    require(set(sources)==set(FILES),'closed owner-Editor implementation inventory required')
    plan,raw=core.construct(commit,external,config,contract,challenges,materials,proof,
        preprocessing_environment,{name:sources[name] for name in core.FILES},budget_profile=OWNER_BUDGET_45)
    for name in ('plan.json','screen.json'):raw.pop(name,None)
    raw.update(sources)
    plan.update(kernel_execution_type='QUICK_SAVE',owner_editor_only=True,
        **{key:key in OWNER_TRUE_FIELDS for key in core.FALSE_FIELDS})
    plan['owner_editor_admission']=owner.admission(plan)
    plan['source_files_sha256']={name:hashlib.sha256(body).hexdigest() for name,body in sorted(sources.items())}
    plan['payload_sha256']={name:hashlib.sha256(body).hexdigest() for name,body in sorted(raw.items())}
    validate_admission(plan);reject_truth(plan)
    raw['plan.json']=raw['screen.json']=canonical(plan)
    return plan,raw


def verify_runtime(root,*,require_approved=False):
    root=Path(root);require(not root.is_symlink(),'regular owner-Editor runtime root required')
    plan=parse_json((root/'plan.json').read_bytes())
    require(plan==parse_json((root/'screen.json').read_bytes()),'identical owner plan/screen required')
    validate_admission(plan,required=require_approved,root=root)
    require(set(plan['source_files_sha256'])==set(FILES) and set(FILES)<=set(plan['payload_sha256']),
        'closed owner-Editor source and payload inventory required')
    for name,expected in plan['payload_sha256'].items():
        path=root/name
        require(path.resolve().is_relative_to(root.resolve()) and not any(p.is_symlink() for p in (path,*path.parents)) and
            sha(path)==expected,'immutable owner-Editor payload differs: '+name)
    contract=parse_json((root/'material-contract.json').read_bytes())
    external={name:(root/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json']=(root/'verified-tokenizer.json').read_bytes()
    sources={name:(ROOT/name).read_bytes() for name in FILES}
    expected,raw=construct(plan['source_commit'],external,{k:plan[k] for k in (*CONFIG_FIELDS,'native_source_learning_rates')},
        contract,parse_json((root/'challenges.json').read_bytes()),
        {key:parse_json((root/'materials'/f'{key}.json').read_bytes()) for key in core.ancestor.ancestor.TASKS},
        read_contract(root/PROOF_FILE),plan['preprocessing_environment'],sources)
    require(plan==expected and all((root/name).read_bytes()==body for name,body in raw.items()),
        'exact owner-Editor source/material/plan reconstruction differs')
    return plan


def branch(body,message):
    return ("if type(globals().get("+repr(owner.CONFIG_NAME)+")) is not bool or globals().get("+
        repr(owner.CONFIG_NAME)+") is not True:\n    print("+repr(message)+")\nelse:\n"+
        ''.join('    '+line if line.strip() else line for line in body.splitlines(keepends=True)))


def embedded_body(notebook):
    tree=ast.parse(''.join(notebook['cells'][2]['source']))
    require(len(tree.body)==1 and isinstance(tree.body[0],ast.If),'one explicit owner execution branch required')
    expected=ast.parse(branch('pass\n',owner.NO_RUN)).body[0]
    require(ast.dump(tree.body[0].test)==ast.dump(expected.test) and
        ast.dump(ast.Module(body=tree.body[0].body,type_ignores=[]))==
        ast.dump(ast.Module(body=expected.body,type_ignores=[])), 'default owner config must print without imports or setup')
    return ast.unparse(ast.Module(body=tree.body[0].orelse,type_ignores=[]))+'\n'


def verify_embedded_payload(notebook,raw):
    require(len(notebook['cells'])==4,'exact disclosure/config/execution/download cell layout required')
    config=''.join(notebook['cells'][1]['source'])
    require(config==configuration_cell(),'visible exact-run config must default to literal False')
    body=embedded_body(notebook)
    core.ancestor.ancestor.verify_embedded_payload({'cells':[{}, {'source':body.splitlines(keepends=True)}]},raw)
    for node in ast.parse(body).body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='PACKED':
            keys=[key.value for key in node.value.keys]
            require(len(keys)==len(set(keys)),'duplicate owner embedded payload key')


def configuration_cell():
    return ('# Set True only to authorize this exact run003 once in a fresh Editor session.\n'
        '# True declares that you accept the original sorokin V2 / Qwen / Torch / Unsloth / FlashAttention native stack and offline setup,\n'
        '# personally checked at least 3 free GPU-hours with pay-to-scale OFF, and will stop the Editor session after downloading.\n'
        '# The 45-minute watchdog is internal code, not a provider-enforced Editor session limit.\n'
        +owner.CONFIG_NAME+' = False\n'
        +'if '+owner.CONFIG_NAME+' is not True:\n    print('+repr(owner.NO_RUN)+')\n')


def render(plan,raw):
    validate_admission(plan)
    require(raw.get('plan.json')==raw.get('screen.json')==canonical(plan),'exact owner plan/screen bytes required')
    from tools.stage_nvarc_e10_ttt_probe import render as training_render
    notebook=training_render(plan,raw)
    markdown=[
        'Owner-Editor only: E11 run003. This QUICK_SAVE does not start the experiment.\n',
        'The visible confirmation below defaults to False. Review the scope, set it to True yourself, then Run All once in a fresh session.\n',
        'Run settings: private, Internet off, exactly 4 NVIDIA L4 GPUs, USD 0.\n',
        'Execution uses the same sorokin dependency notebook V2, sorokin Qwen modification and pinned Qwen3 4B SFT139 model, including Torch, Unsloth and the mjun0812 FlashAttention build with the existing offline setup. Selected bytes are pinned; this is not a new full-stack certification.\n',
        'Compare cumulative DFS floor p=.2 against p=.1, both INTERLEAVED. The same four tasks share 512 training updates once, followed by 12 test executions (six per arm). Each test keeps 120 generation seconds and 150 total seconds.\n',
        'The 45-minute limit is an INTERNAL watchdog, not a provider-enforced Editor session timeout. It can fail on slow cleanup/finalization; no completion or model-quality claim is promised.\n',
        'Before confirming, personally check at least 3 free GPU-hours, no conflicting reservation, and pay-to-scale OFF. Those are your declarations; this notebook does not independently attest provider quota or paid settings.\n',
        'After the run, use the read-only download cell and STOP THE EDITOR SESSION to avoid continued resource use. Do not rerun or reuse this exact run identity for another attempt.\n',
        'Saving this notebook is publication consent only. Agent execution remains disabled. No teacher, evaluator truth, official scoring or competition submission is enabled.\n']
    body=''.join(notebook['cells'][1]['source'])
    hook="screen=json.loads(zlib.decompress(base64.b64decode(PACKED['screen.json'])))\n"
    require(body.count(hook)==1,'one exact owner plan hook required')
    pin=hashlib.sha256(canonical(plan)).hexdigest()
    guard=("if hashlib.sha256(zlib.decompress(base64.b64decode(PACKED['screen.json']))).hexdigest()!="+repr(pin)+":\n"
        "    raise RuntimeError('exact owner plan bytes differ before setup')\n"
        "if HASHES!=dict(screen['payload_sha256'],**{'plan.json':"+repr(pin)+",'screen.json':"+repr(pin)+"}) or set(PACKED)!=set(HASHES):\n"
        "    raise RuntimeError('exact owner packed runtime inventory differs before setup')\n")
    body=body.replace(hook,hook+guard,1)
    hook="paths=[Path(path) for path in sys.path"
    require(body.count(hook)==1,'one owner confirmation insertion point required')
    body=body.replace(hook,"sys.path.insert(0,str(work))\nfrom tools.nvarc_e11_owner_editor import write_confirmation\n"+
        "write_confirmation(work,screen,"+owner.CONFIG_NAME+",START)\n"+hook,1)
    old="str(work/'tools/nvarc_e10_ttt_probe.py'),'--bootstrap','--root'"
    require(body.count(old)==1,'one owner coordinator hook required')
    body=body.replace(old,"str(work/'tools/nvarc_e11_owner_editor_entry.py'),'--bootstrap','--root'",1)
    for old,new in (('from tools.nvarc_e10_ttt_probe import finalize','from tools.nvarc_e11_paired_floor import finalize'),
            ('from tools.nvarc_process_supervisor import supervise','from tools.nvarc_e11_cleanup import supervise'),
            ("or not diagnostics.get('final_archive_created'):","or not diagnostics.get('final_archive_created') or not diagnostics.get('finalization_qualified'):")):
        require(body.count(old)==1,'one exact owner execution hook required');body=body.replace(old,new,1)
    execution=branch(body,owner.NO_RUN)
    download=''.join(notebook['cells'][-1]['source'])
    hook='_download_path=_download_checked_archive()\n'
    require(download.count(hook)==1,'one read-only owner download hook required')
    prefix,tail=download.split(hook,1)
    download=prefix+"if not DOWNLOAD_PATH.is_file():\n    print('No finalized archive is available yet. No run or recovery has been started by this cell.')\nelse:\n"+''.join(
        '    '+line if line.strip() else line for line in (hook+tail+"print('After downloading, stop the Editor session. The internal watchdog is not a provider session timeout.')\n").splitlines(keepends=True))
    download=branch(download,'No run was confirmed. This read-only cell will not set up or start anything.')
    code=lambda value:dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=value.splitlines(keepends=True))
    notebook['cells']=[dict(cell_type='markdown',metadata={},source=markdown),code(configuration_cell()),code(execution),code(download)]
    for cell in notebook['cells'][1:]:compile(''.join(cell['source']),'owner-editor-cell','exec')
    verify_embedded_payload(notebook,raw)
    return notebook


def metadata(plan):return core.metadata(plan)


def handoff(plan):
    validate_admission(plan)
    return dict(format='irisx/e11-owner-editor-handoff-v1',run_id=RUN_ID,notebook_ref=NOTEBOOK,
        notebook_numeric_id=137327571,expected_notebook_version=9,expected_previous_version=8,
        expected_previous_script_version_id=356039440,kernel_execution_type='QUICK_SAVE',
        publication_authorized=True,publication_authorization_ref=owner.PUBLICATION_REF,
        agent_execution_authorized=False,runtime_authorized=False,owner_config_required=True,
        config_name=owner.CONFIG_NAME,default_config_value=False,execution_chat_ref=None,
        owner_declarations_are_independent_attestations=False,provider_editor_timeout_attested=False,
        internal_watchdog_seconds=2700,planned_charged_gpu_seconds_ceiling=10800,
        monitor_after_submission=False,official_submission_authorized=False,paid_usd_ceiling=0)


def package_manifest(plan,raw):
    files={'runtime/'+name:body for name,body in raw.items()}
    files.update({'kernel/notebook.ipynb':canonical(render(plan,raw)),
        'kernel/kernel-metadata.json':canonical(metadata(plan)),'cli-handoff.json':canonical(handoff(plan))})
    return dict(format='irisx/e11-owner-editor-package-v1',plan_digest=digest(plan),
        files_sha256={name:hashlib.sha256(body).hexdigest() for name,body in sorted(files.items())})


def stage(package,plan,raw):
    package=Path(package);require(not package.exists(),'new immutable owner-Editor package required')
    (package/'kernel').mkdir(parents=True)
    for name,body in raw.items():
        path=package/'runtime'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    write(package/'kernel/notebook.ipynb',render(plan,raw));write(package/'kernel/kernel-metadata.json',metadata(plan))
    write(package/'cli-handoff.json',handoff(plan));write(package/'package-manifest.json',package_manifest(plan,raw))
    return preflight(package)


def preflight(package,*,expected_manifest_sha256=None):
    package=Path(package);manifest=parse_json((package/'package-manifest.json').read_bytes())
    require(not any(p.is_symlink() for p in (package,*package.rglob('*'))) and
        manifest['files_sha256']=={p.relative_to(package).as_posix():sha(p) for p in package.rglob('*')
            if p.is_file() and p!=package/'package-manifest.json'},'closed immutable owner-Editor package required')
    if expected_manifest_sha256 is not None:require(sha(package/'package-manifest.json')==expected_manifest_sha256,'independent manifest pin differs')
    plan=verify_runtime(package/'runtime');sources=exact_sources(plan['source_commit'])
    require(plan['source_files_sha256']=={name:hashlib.sha256(body).hexdigest() for name,body in sources.items()},'committed owner sources differ')
    raw={name:(package/'runtime'/name).read_bytes() for name in (*plan['payload_sha256'],'plan.json','screen.json')}
    require(manifest==package_manifest(plan,raw) and
        parse_json((package/'kernel/notebook.ipynb').read_bytes())==render(plan,raw) and
        parse_json((package/'kernel/kernel-metadata.json').read_bytes())==metadata(plan) and
        parse_json((package/'cli-handoff.json').read_bytes())==handoff(plan),'exact owner notebook/metadata/handoff differs')
    require(not (package/'runtime'/owner.CONFIRMATION_FILE).exists(),'published package cannot fabricate owner runtime confirmation')
    return dict(run_id=RUN_ID,plan_digest=digest(plan),package_manifest_sha256=sha(package/'package-manifest.json'),
        offline_package_verified=True,publication_mode='QUICK_SAVE',publication_authorized=True,
        agent_execution_authorized=False,runtime_authorized=False,owner_config_required=True,
        new_model_calls=0,new_provider_calls=0,gpu_probe_run=False)


def build_from_frozen(package,frozen_runtime,commit,inference_plan):
    root=Path(frozen_runtime)
    require(sha(root/'plan.json')==core.ancestor.ancestor.PARENT_PLAN_SHA256 and
        sha(inference_plan)==core.ancestor.ancestor.INFERENCE_PLAN_SHA256,'exact original training/inference parents required')
    parent=parse_json((root/'plan.json').read_bytes());contract=parse_json((root/'material-contract.json').read_bytes())
    external={name:(root/name).read_bytes() for name in material_files(contract)}
    external['verified-tokenizer.json']=(root/'verified-tokenizer.json').read_bytes()
    plan,raw=construct(commit,external,{k:parent[k] for k in (*CONFIG_FIELDS,'native_source_learning_rates')},contract,
        parse_json((root/'challenges.json').read_bytes()),
        {key:parse_json((root/'materials'/f'{key}.json').read_bytes()) for key in core.ancestor.ancestor.TASKS},
        read_contract(root/PROOF_FILE),parent['preprocessing_environment'],exact_sources(commit))
    return stage(package,plan,raw)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('stage','preflight'))
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--frozen-runtime',type=Path)
    parser.add_argument('--source-commit');parser.add_argument('--inference-plan',type=Path);parser.add_argument('--expected-manifest-sha256')
    args=parser.parse_args()
    result=preflight(args.package,expected_manifest_sha256=args.expected_manifest_sha256) if args.action=='preflight' else \
        build_from_frozen(args.package,args.frozen_runtime,args.source_commit,args.inference_plan)
    print(json.dumps(result))


if __name__=='__main__':main()
