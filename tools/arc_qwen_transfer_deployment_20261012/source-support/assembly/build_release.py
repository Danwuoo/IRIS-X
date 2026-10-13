"""Deterministic, offline true-ARC release assembly. No provider API or model execution."""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import zipfile
from build_notebook import build as notebook_build, PACKAGE

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK = ROOT/'worktree'
BASE = ROOT.parent/'portfolio63-source-recovery-20261012/exact-delivered'
BASE_MANIFEST_SHA = '74acbe1674603d6a4c7a5078f3f2afa3965afffdf1f01278b1d9220ca0aa2c7a'
BASE_ARCHIVE_SHA = '1a2688871eab0221924db7c74d6042e122b3047f37ab6db28daf1c9e9fc364d7'
CODE_REFERENCE = 'danielwuu/iris-x-learning-agent-code-20261011/11'
MODEL_REFERENCE = 'qwen-lm/qwen-3/transformers/14b/1'
BASE_COMMIT = '08d6e1c7a7feae044fdd50e6d421b4a7340ea56a'
BASE_TREE = 'c5fe7208190e2fca349296ba92ff5ecc01ad101e'
TOKENIZER = 'materials/qwen14b/hf-overlay/tokenizer.json'
PANEL_SHA = '8138168e1c8206977efaab20243ac66e04fe5d0cf5d375252b7cca68feefa17a'
EXCLUSIONS = 'panel-freeze/public120-exclusions.json'
ADDENDUM_SHA = 'ec8354dda582077a67a4df48fbd46dbca0edd1b85fd3461626e040eda5596804'
EXCLUSIONS_SHA = 'ef1d0f2812f42b221a24b6938ed1ee2b64b6165a3d071a5d2d55bb951976be9e'
RUNTIME_PREFIX = 'tools/arc_qwen_transfer_20261012/'
READINESS = ROOT.parent/'portfolio63-user-20261012/provider-source-recovery/fresh-auth-readiness/READINESS.json'
READINESS_SHA = 'a6cb4b05814afec48626fa0193291b5ccfaa8e19174082c845e37559e8d4f0a1'
PREDECESSOR_SOURCE = '8414171502ae5753fe78991314d0bb1be948788d9be8a0b8ffbb0dc28ae63c15'


def need(value, message):
    if not value: raise ValueError(message)


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()


def encoded(value):
    return (json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()


def sha(raw): return hashlib.sha256(raw).hexdigest()


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f: f.write(encoded(value))


def regular(path):
    path=Path(path)
    need(not any(p.is_symlink() for p in (path,*path.parents)),'source symlink forbidden')
    before=path.stat();need(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'single-link regular source required')
    raw=path.read_bytes();after=path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
         (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) and len(raw)==after.st_size,
         'source changed during read')
    return raw


def safe_name(name):
    need(type(name) is str and name and not name.startswith('/') and '\\' not in name and ':' not in name and
         not any(ord(c)<32 for c in name) and not any(p in ('','.','..') for p in name.split('/')),'unsafe relative path')
    return name


def file_row(path,name=None):
    raw=regular(path);return {'path':name or Path(path).name,'bytes':len(raw),'sha256':sha(raw)}


def zip_files(path,files):
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,raw in sorted(files.items()):
            entry=zipfile.ZipInfo(safe_name(name),(2026,10,12,0,0,0));entry.create_system=3
            entry.external_attr=(stat.S_IFREG|0o644)<<16;entry.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(entry,raw)


def tree_files(root):
    files={}
    for directory,dirs,names in os.walk(root,followlinks=False):
        for name in dirs: need(not (Path(directory)/name).is_symlink(),'source directory symlink forbidden')
        dirs[:]=sorted(n for n in dirs if n!='__pycache__')
        for name in sorted(names):
            p=Path(directory)/name
            if p.suffix in ('.pyc','.pyo'): continue
            logical=safe_name(p.relative_to(root).as_posix())
            need('.git' not in p.parts,'Git metadata excluded')
            files[logical]=regular(p)
    return files


def collect():
    raw=regular(BASE/'support/code-payload/manifest.json');need(sha(raw)==BASE_MANIFEST_SHA,'exact175 baseline manifest required')
    baseline=json.loads(raw)['source_identity'];need(len(baseline)==175,'exact175 baseline required')
    need(sha(regular(BASE/'support/code-payload/source.zip'))==BASE_ARCHIVE_SHA,'exact175 baseline archive required')
    files=tree_files(WORK)
    for test_name in ('tests/test_backend_profile.py','tests/test_public_evaluation.py','tests/test_transfer_runtime.py'):
        files.pop(test_name, None)  # Local authored acceptance tests are not runtime payload.
    need(set(baseline)<=set(files),'baseline members removed')
    need(all(sha(files[n])==h for n,h in baseline.items()),'baseline bytes changed')
    for n in set(files)-set(baseline):
        need(n.startswith(RUNTIME_PREFIX) and (n.endswith('.py') or n in (RUNTIME_PREFIX+'standalone-provenance.json',RUNTIME_PREFIX+'README.md')),
             'unapproved runtime source path: '+n)
    deployed=tree_files(ROOT/'deployment/runtime')
    need(set(deployed)=={'__init__.py','source_loader.py','preloader.py','bootstrap.py'},'closed deployment source set')
    for n,raw in deployed.items(): files[PACKAGE+'/'+n]=raw
    raw=regular(ROOT/EXCLUSIONS);need(sha(raw)==EXCLUSIONS_SHA,'fixed PUBLIC120 exclusion manifest changed')
    files[EXCLUSIONS]=raw
    for n,raw in files.items():
        need(len(raw)<=(12*1024**2 if n==TOKENIZER else 2*1024**2),'member cap: '+n)
        if n.endswith('.py'): ast.parse(raw,filename=n)
    need(len(files)<=512 and sum(map(len,files.values()))<=16*1024**2,'closed source cap')
    return dict(sorted(files.items())),baseline


def approval_check(path,files):
    raw=regular(path);approval=json.loads(raw)
    need(approval.get('approved') is True,'explicit source audit approval required')
    expected={n:sha(b) for n,b in files.items() if n.startswith(RUNTIME_PREFIX)}
    need(approval.get('runtime_source_identity')==expected,'audit approval differs from exact runtime bytes')
    return {'path':Path(path).name,'bytes':len(raw),'sha256':sha(raw)},raw


def old_pins():
    nb=json.loads(regular(BASE/'iris-x-qwen14b-portfolio-manual.ipynb'))
    tree=ast.parse(''.join(nb['cells'][2]['source']))
    values=[n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PINS' for t in n.targets)]
    need(len(values)==1 and isinstance(values[0],ast.Call) and len(values[0].args)==1,'exact historical notebook pins')
    pins=json.loads(ast.literal_eval(values[0].args[0]));need(pins['code']['reference'].endswith('/10'),'code10 predecessor required')
    return pins


def build(destination,*,runtime_approval=None):
    output=Path(destination).absolute()
    need(not output.exists() and not any(p.is_symlink() for p in (output,*output.parents)),'fresh unlinked output required')
    for source in (WORK.absolute(),BASE.absolute(),(ROOT/'deployment').absolute(),HERE.absolute()):
        need(not (output==source or output in source.parents or source in output.parents),'output overlaps source')
    files,baseline=collect();reviewed=runtime_approval is not None
    approval,approval_raw=approval_check(runtime_approval,files) if reviewed else (None,None)
    readiness_raw=regular(READINESS);need(sha(readiness_raw)==READINESS_SHA,'verified readiness receipt differs')
    readiness=json.loads(readiness_raw)
    need(readiness['dataset_version']==10 and readiness['notebook_version']==19 and readiness['provider_latest_status']=='COMPLETE' and
         readiness['source_sha256']==PREDECESSOR_SOURCE,'exact predecessor state required')
    prior=json.loads(regular(BASE/'support/release-builder-inputs/previous/publication-manifest.json'))
    refs=[CODE_REFERENCE]+prior['notebooks'][0]['dataset_sources'][1:]
    need(len(refs)==8 and len(set(refs))==8,'exact eight Dataset references')
    panel_raw=regular(ROOT/'panel-freeze/frozen-panel-plan.json')
    panel_receipt_raw=regular(ROOT/'panel-freeze/PANEL-FREEZE-RECEIPT.json')
    panel_receipt=json.loads(panel_receipt_raw)
    need(sha(panel_raw)==PANEL_SHA==panel_receipt['panel']['sha256'] and panel_receipt['exclusion_manifest']['sha256']==EXCLUSIONS_SHA, 'frozen panel receipt mismatch')
    addendum_raw=regular(ROOT/'backend-receipts/material-addendum.json')
    addendum=json.loads(addendum_raw)
    addendum_digest=sha(json.dumps(addendum,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode())
    need(addendum_digest==ADDENDUM_SHA,'exact reviewed model addendum required')
    output.mkdir(parents=True);payload=output/'code-payload';payload.mkdir()
    (output/'frozen-panel-plan.json').write_bytes(panel_raw)
    (output/'PANEL-FREEZE-RECEIPT.json').write_bytes(panel_receipt_raw)
    (output/'MATERIAL-ADDENDUM.json').write_bytes(addendum_raw)
    (output/'accept-downloaded-mount.py').write_bytes(regular(HERE/'accept_downloaded_mount.py'))
    zip_files(payload/'source.zip',files)
    identity={n:sha(b) for n,b in files.items()};inventory={n:{'bytes':len(b),'sha256':identity[n]} for n,b in files.items()}
    archive=file_row(payload/'source.zip');archive['name']=archive.pop('path')
    manifest={'format':'irisx/learning-source-v1','reference':CODE_REFERENCE,'base_commit':BASE_COMMIT,
              'source_provenance':'exact-local-byte-freeze; unpublished candidate; stable owner Git base only',
              'source_identity':identity,'files':inventory,'archive':archive,
              'contains_weights':False,'contains_public_answers':False,'contains_raw_development_tasks':False,
              'gpu_runtime_verified':False,'public_scoring_enabled':True,
              'public_scoring_policy':'conditional-after-closed-owner-and-seal',
              'specific_large_member_allowance':TOKENIZER}
    write(payload/'manifest.json',manifest)
    (payload/'NOTICE.txt').write_bytes(regular(BASE/'support/code-payload/NOTICE.txt'))
    pins=old_pins();pins['code']={'reference':CODE_REFERENCE,'manifest_sha256':sha(regular(payload/'manifest.json')),'archive_sha256':archive['sha256']}
    pins['release']={'runtime_reviewed':reviewed,'runtime_review_sha256':approval['sha256'] if approval else None,
                     'source_identity_sha256':sha(canonical(identity)),'predispatch_epoch_required':True}
    write(output/'pins.json',pins)
    notebooks={}
    for role,active in (('inactive',False),('active-template',True)):
        name='iris-x-qwen14b-transfer-'+role+'.ipynb'
        notebook=notebook_build(pins,files,active=active);write(output/name,notebook)
        config=''.join(notebook['cells'][1]['source'])
        need(config.count('PREDISPATCH_EPOCH = None')==1,'one exact JIT epoch placeholder')
        for cell in notebook['cells']:
            if cell['cell_type']=='code':
                need(cell['execution_count'] is None and cell['outputs']==[],'output-free notebook')
                compile(''.join(cell['source']),'<actual-notebook>','exec')
        notebooks[role]=file_row(output/name)
    upload=[file_row(p) for p in sorted(payload.iterdir())]
    metadata=[r for r in upload if r['path']!='source.zip'];extracted=[{'path':n,**r} for n,r in inventory.items()]
    layouts={'original-upload':upload,'extracted-root':sorted(metadata+extracted,key=lambda r:r['path']),
             'extracted-source-directory':sorted(metadata+[dict(r,path='source/'+r['path']) for r in extracted],key=lambda r:r['path'])}
    write(output/'provider-layout-contracts.json',layouts)
    zip_files(output/'code-dataset-upload.zip',{p.name:regular(p) for p in sorted(payload.iterdir())})
    inner={n:h for n,h in identity.items() if Path(n).suffix in ('.py','.json','.jinja')}
    write(output/'expected-inner-source-identity.json',inner)
    tree=ast.parse(files[PACKAGE+'/preloader.py'])
    drivers=[n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='driver' for t in n.targets)]
    need(len(drivers)==1 and isinstance(drivers[0],ast.BinOp) and isinstance(drivers[0].right,ast.Constant),'exact launcher driver required')
    expected=output/'expected-launcher';expected.mkdir()
    (expected/'bootstrap.py').write_bytes(files[PACKAGE+'/source_loader.py']+drivers[0].right.value.encode())
    (expected/'owned_process_guard.py').write_bytes(files['tools/arc_learning_agent_20261011/process_guard.py'])
    if approval_raw is not None: (output/'RUNTIME-SOURCE-APPROVAL.json').write_bytes(approval_raw)
    freeze={'format':'irisx/qwen14b-transfer-source-freeze-v1','source_identity':identity,'files':inventory,
            'source_identity_sha256':sha(canonical(identity)),'runtime_member_count':len(files),'total_expanded_bytes':sum(map(len,files.values())),
            'baseline_member_count':175,'baseline_manifest_sha256':BASE_MANIFEST_SHA,'baseline_archive_sha256':BASE_ARCHIVE_SHA,
            'baseline_changed':{},'baseline_added':{n:h for n,h in identity.items() if n not in baseline},
            'build_script_sha256':sha(regular(__file__)),'notebook_builder_sha256':sha(regular(HERE/'build_notebook.py')),
            'no_model_mount_acceptance_helper':file_row(output/'accept-downloaded-mount.py'),
            'source_zip_sha256':archive['sha256'],'code_manifest_sha256':pins['code']['manifest_sha256'],
            'pins_sha256':sha(regular(output/'pins.json')),'notebooks':notebooks,'runtime_source_approval':approval,
            'source_review_only':not reviewed,'dispatchable':False,
            'limits':{'program_seconds':43200,'global_seconds':43200,'provider_runtime_seconds':42300,'execution_cutoff_seconds':42000,'outer_cutoff_seconds':42180,
                      'source_expanded_bytes':16*1024**2,'tokenizer_member_bytes':12*1024**2,'other_member_bytes':2*1024**2},
            'claim':'Local unpublished candidate. Active template is non-dispatchable until exact epoch patch and separate operator review.'}
    write(output/'SOURCE-FREEZE.json',freeze)
    dataset=copy.deepcopy(prior['datasets'][0]);dataset.update(expected_predecessor_version=10,expected_version=11,
        version_status='PROSPECTIVE_UNUPLOADED',delete_old_versions=False,payload_root='code-payload',root_manifest={'path':'manifest.json','sha256':pins['code']['manifest_sha256']},
        upload_inventory=upload,upload_inventory_sha256=sha(canonical(upload)),expected_readback_layouts=layouts,
        transport_archive=file_row(output/'code-dataset-upload.zip'),version_notes='True-ARC transfer successor source candidate; no raw tasks, gold answers or weights.')
    need(dataset['id']==12504696 and dataset['is_private'] is True,'same private code Dataset')
    notebook_contract=[]
    for role,active in (('inactive',False),('active-template',True)):
        notebook_contract.append({'role':'transfer001' if active else role,'template_role':role,**notebooks[role],'existing_notebook_reference':prior['notebooks'][0]['reference'],
            'existing_notebook_id':138123872,'expected_predecessor_version':20 if active else 19,'expected_version':21 if active else 20,
            'predecessor_source_sha256':None if active else PREDECESSOR_SOURCE,'save_mode':'RUN' if active else 'QUICK_SAVE',
            'title':'IRIS-X Learning Agent 20261011','language':'python','kernel_type':'notebook',
            'save_version_value':1 if active else 3,'session_timeout_seconds':42300 if active else None,'timeout_seconds':42300 if active else None,
            'run_authorized':bool(active and reviewed),
            'manual_start':active,'enable_model':active,'enable_gpu':active,'enable_tpu':False,'enable_internet':False,'is_private':True,
            'machine_shape':'NvidiaRtxPro6000' if active else None,'dataset_sources':refs,'model_sources':[MODEL_REFERENCE],
            'competition_sources':copy.deepcopy(prior['notebooks'][0]['competition_sources']),
            'docker_image':prior['notebooks'][0]['docker_image'],'program_session_seconds':43200,'global_seconds':43200,
            'provider_runtime_seconds':42300,'execution_cutoff_seconds':42000,'outer_cutoff_seconds':42180,'predispatch_epoch':None,'epoch_policy':'replace sole None assignment just before dispatch; no fallback or clock reset',
            'output_root':'/kaggle/working/irisx-qwen14b-transfer-20261012-run001',
            'source_parent':'/kaggle/working/irisx-qwen14b-transfer-20261012-source001',
            'dispatch_epoch_patch':{'assignment':'PREDISPATCH_EPOCH','maximum_patch_age_seconds':60,'cell_index':1,'required_original_value':None,'maximum_changed_assignments':1},
            'source_dispatch_ready':False,'requires_exact_operator_review':True})
    publication={'format':'irisx/qwen14b-transfer-publication-contract-v1','source_freeze_sha256':sha(regular(output/'SOURCE-FREEZE.json')),
        'source_identity_sha256':freeze['source_identity_sha256'],'datasets':[dataset],'notebooks':notebook_contract,
        'predecessor_readiness':{'sha256':READINESS_SHA,'notebook_version':19,'notebook_source_sha256':PREDECESSOR_SOURCE,'provider_status':'COMPLETE'},
        'public_exclusions':{'path':EXCLUSIONS,'sha256':EXCLUSIONS_SHA},
        'frozen_panel_plan':file_row(output/'frozen-panel-plan.json'),
        'model_material_addendum':{**file_row(output/'MATERIAL-ADDENDUM.json'),'canonical_identity_sha256':ADDENDUM_SHA},
        'no_model_mount_acceptance_helper':file_row(output/'accept-downloaded-mount.py'),
        'terminal_contract':{'active_role':'transfer001','statuses':['TRANSFER_COMPLETE','TRANSFER_PARTIAL','TRANSFER_NOT_ADMITTED','TRANSFER_FAILED'],
            'success_statuses':['TRANSFER_COMPLETE'],'partial_statuses':['TRANSFER_PARTIAL','TRANSFER_NOT_ADMITTED'],'failure_statuses':['TRANSFER_FAILED'],
            'file_byte_caps':{'terminal-receipt.json':1024**2,'launcher/result.json':1024**2,'ordinary_evidence_member':16*1024**2,'large_diagnostic_member':64*1024**2,'checkpoint_member':32*1024**2},
            'archive_caps':{'evidence_expanded_bytes':256*1024**2,'evidence_members':12000,'checkpoint_expanded_bytes':2*1024**3,'checkpoint_archive_bytes':2*1024**3+2*1024**2,'checkpoint_members':1025},
            'large_diagnostic_paths':['full-diagnostics.json','experiment/full-report.json','training-receipts-at-exit.json'],
            'terminal_receipt':'terminal-receipt.json','evidence_archive':'evidence.zip','checkpoint_archive':'checkpoints.zip',
            'inner_request_source_identity':{'path':'expected-inner-source-identity.json','file_sha256':sha(regular(output/'expected-inner-source-identity.json')),
                'identity_sha256':sha(canonical(inner)),'mapping':inner},
            'outer_executable_files':{n:file_row(expected/n,'expected-launcher/'+n) for n in ('bootstrap.py','owned_process_guard.py')},
            'public_scoring':'conditional full120/167 after closed model ownership and sealed predictions; evaluator gold excluded from model child',
            'operational_closure_does_not_prove_learning':True,'public_goal':{'metric':'micro pass@2','denominator':167,'minimum_correct':151}},
        'owner_published_stable_commit':BASE_COMMIT,'owner_published_stable_tree':BASE_TREE,'candidate_git_published':False,
        'git_gate_required':False,'run_authorized':reviewed,'provider_publication_completed':False,'gpu_runtime_verified':False,'source_review_only':not reviewed,
        'release_runtime_finalized':reviewed,'runtime_source_approval':approval,
        'local_assembly_performs_provider_calls':False,'requires_separate_operator_review':True,'dispatch_ready':False}
    write(output/'publication-manifest.json',publication)
    write(output/'ASSEMBLY-INVENTORY.json',{p.relative_to(output).as_posix():file_row(p,p.relative_to(output).as_posix())
        for p in sorted(output.rglob('*')) if p.is_file()})
    need(collect()[0]==files,'runtime changed during assembly; discard mixed candidate')
    return {'output':str(output),'status':'LOCAL_UNPUBLISHED_CANDIDATE' if reviewed else 'SOURCE_ONLY_NONDISPATCHABLE_PREVIEW',
            'source_members':len(files),'expanded_bytes':freeze['total_expanded_bytes'],'source_zip_sha256':archive['sha256'],
            'source_freeze_sha256':sha(regular(output/'SOURCE-FREEZE.json')),'publication_manifest_sha256':sha(regular(output/'publication-manifest.json'))}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    parser.add_argument('--runtime-approval',type=Path);args=parser.parse_args()
    print(json.dumps(build(args.output,runtime_approval=args.runtime_approval),indent=2))
