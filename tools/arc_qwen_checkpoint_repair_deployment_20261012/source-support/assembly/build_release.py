"""Deterministic, offline checkpoint-repair release assembly. No provider API or model execution."""
from __future__ import annotations
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import zipfile
from build_notebook import build as notebook_build, PACKAGE

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK = ROOT/'final-source-freeze-002'
PREVIOUS = ROOT.parent/'portfolio63-transfer-repair-20261012'
PRIOR_RELEASE = PREVIOUS/'release-candidate-002'
AUTHOR_FREEZE = ROOT/'assembly/AUTHOR-SOURCE-FREEZE-002.json'
AUTHOR_FREEZE_SHA = '04df597883ef454fe2b71a26289fe2ec703c1b407cfca2224ccfedc0cce79fa2'
PREDECESSOR_DESCRIPTORS = ROOT/'publication/PREDECESSOR-DESCRIPTORS.json'
PREDECESSOR_DESCRIPTORS_SHA = 'ef9e66cc2473306c6a54e2dc930dfdd9a9096433b7fb8810287501a6067d5b6b'
PREDECESSOR_DESCRIPTORS_BYTES = 4424
SHARED_CHECKPOINT = 'tools/arc_qwen_portfolio_20261012/checkpoints.py'
ALLOWED_CHANGED = {SHARED_CHECKPOINT, 'tools/arc_qwen_transfer_20261012/backend.py', 'tools/arc_qwen_transfer_20261012/experiment.py', 'tools/arc_qwen_transfer_20261012/public_evaluation.py'}
ALLOWED_ADDED = {'tools/arc_qwen_transfer_20261012/checkpoint_policy.py'}
GENUINE_TINY_INNER_IDENTITY_SHA = 'e02c3485ac271fa738d0bc8728ad4e7f07be3f43e698d5387c6bfbea1a07e245'
AUTHOR_INNER_IDENTITY_SHA = 'd485de95b68e0147e0d122143d25e983b7c60800259fdf8e44315b4537818b86'
PRIOR_SOURCE_ZIP_SHA = '6fe28472f84860b58895eed066169560e4d5fa62b6114594f7794a2924e2206c'
PRIOR_FULL_IDENTITY_SHA = 'be965cd065e6cce06f8fc77b9facd99264565a1b1e374bfee889c421f53a22ea'
TERMINAL_AUDIT_SHA = 'b12cc4416b7c366a6cfbc0f4d16de511377251145f456fd8065542b1b9ed681e'
BASE = ROOT.parent/'portfolio63-source-recovery-20261012/exact-delivered'
BASE_MANIFEST_SHA = '74acbe1674603d6a4c7a5078f3f2afa3965afffdf1f01278b1d9220ca0aa2c7a'
BASE_ARCHIVE_SHA = '1a2688871eab0221924db7c74d6042e122b3047f37ab6db28daf1c9e9fc364d7'
CODE_REFERENCE = 'danielwuu/iris-x-learning-agent-code-20261011/13'
MODEL_REFERENCE = 'qwen-lm/qwen-3/transformers/14b/1'
BASE_COMMIT = '08d6e1c7a7feae044fdd50e6d421b4a7340ea56a'
BASE_TREE = 'c5fe7208190e2fca349296ba92ff5ecc01ad101e'
TOKENIZER = 'materials/qwen14b/hf-overlay/tokenizer.json'
PANEL_SHA = '8138168e1c8206977efaab20243ac66e04fe5d0cf5d375252b7cca68feefa17a'
EXCLUSIONS = 'panel-freeze/public120-exclusions.json'
ADDENDUM_SHA = 'ec8354dda582077a67a4df48fbd46dbca0edd1b85fd3461626e040eda5596804'
EXCLUSIONS_SHA = 'ef1d0f2812f42b221a24b6938ed1ee2b64b6165a3d071a5d2d55bb951976be9e'
RUNTIME_PREFIX = 'tools/arc_qwen_transfer_20261012/'
PREDECESSOR_SOURCE = 'a7451ae7a341c36483737987d2edfaabd0e2e5cb8890234ec6b56f8565b26f03'


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
    author_raw=regular(AUTHOR_FREEZE)
    need(sha(author_raw)==AUTHOR_FREEZE_SHA,'exact author receipt bytes required')
    frozen=json.loads(author_raw)
    inner={n:sha(b) for n,b in files.items() if Path(n).suffix in ('.py','.json','.jinja')}
    need(inner==frozen['source_identity'] and sha(canonical(inner))==frozen['source_identity_sha256']==AUTHOR_INNER_IDENTITY_SHA,
         'exact author executable source freeze required')
    prior_manifest=json.loads(regular(PRIOR_RELEASE/'code-payload/manifest.json'))
    old=prior_manifest['source_identity']
    need(len(old)==199 and sha(canonical(old))==PRIOR_FULL_IDENTITY_SHA,'exact previous199 source closure required')
    need(sha(regular(PRIOR_RELEASE/'code-payload/source.zip'))==PRIOR_SOURCE_ZIP_SHA,'exact previous source archive required')
    need(set(baseline)<=set(files),'baseline source members removed')
    changed={n for n in old if n in files and sha(files[n])!=old[n]}
    added=set(files)-set(old)
    need(not set(old)-set(files),'previous source members removed')
    need(changed==ALLOWED_CHANGED and added==ALLOWED_ADDED,'delta outside explicit checkpoint repair allowlist')
    need(all(sha(files[n])==h for n,h in baseline.items() if n not in ALLOWED_CHANGED),'unreviewed baseline bytes changed')
    changed_rows=[r for r in frozen['changed_files'] if r['before_sha256'] is not None]
    added_rows=[r for r in frozen['changed_files'] if r['before_sha256'] is None]
    need(changed=={r['path'] for r in changed_rows} and added=={r['path'] for r in added_rows},'unaudited successor source change')
    for row in changed_rows:
        need(old[row['path']]==row['before_sha256'] and sha(files[row['path']])==row['after_sha256'],'author changed-source receipt differs')
    for row in added_rows:
        need(sha(files[row['path']])==row['after_sha256'],'author added-source receipt differs')
    deployed=tree_files(ROOT/'deployment/runtime')
    need(set(deployed)=={'__init__.py','source_loader.py','preloader.py','bootstrap.py'},'closed deployment source set')
    need(all(files[PACKAGE+'/'+n]==raw for n,raw in deployed.items()),'deployment differs from CPU source freeze')
    need(sha(files[EXCLUSIONS])==EXCLUSIONS_SHA,'fixed PUBLIC120 exclusion manifest changed')
    runner=ast.parse(files[RUNTIME_PREFIX+'runner.py'])
    caps=[n.value for n in runner.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MAX_TOTAL_BYTES' for t in n.targets)]
    need(len(caps)==1 and ast.dump(caps[0])==ast.dump(ast.parse('512*1024**2',mode='eval').body),'final512MiB runtime evidence cap required')
    for n,raw in files.items():
        need(len(raw)<=(12*1024**2 if n==TOKENIZER else 2*1024**2),'member cap: '+n)
        if n.endswith('.py'): ast.parse(raw,filename=n)
    need(len(files)<=512 and sum(map(len,files.values()))<=16*1024**2,'closed source cap')
    return dict(sorted(files.items())),baseline


def approval_check(path,files):
    raw=regular(path);approval=json.loads(raw)
    need(approval.get('format')=='irisx/independent-transfer-checkpoint-runtime-review-v1' and approval.get('approved') is True and approval.get('known_blockers')==[], 'explicit source audit approval required')
    expected={n:sha(b) for n,b in files.items() if n.startswith(RUNTIME_PREFIX) or n==SHARED_CHECKPOINT}
    need(approval.get('runtime_source_identity')==expected,'audit approval differs from exact runtime bytes')
    inner={n:sha(b) for n,b in files.items() if Path(n).suffix in ('.py','.json','.jinja')}
    need(approval.get('source_identity_sha256')==sha(canonical(inner)),'approval full source identity differs')
    return {'path':'RUNTIME-SOURCE-APPROVAL.json','bytes':len(raw),'sha256':sha(raw)},raw


def old_pins():
    pins=json.loads(regular(PRIOR_RELEASE/'pins.json'))
    need(pins['code']['reference'].endswith('/12'),'code12 predecessor required')
    return pins



def predecessor_evidence():
    raw=regular(PREDECESSOR_DESCRIPTORS)
    need(len(raw)==PREDECESSOR_DESCRIPTORS_BYTES and sha(raw)==PREDECESSOR_DESCRIPTORS_SHA,'exact predecessor descriptors required')
    value=json.loads(raw)
    need(value['closed_verified'] is True and value['predecessor_version']==23 and value['code_dataset_version']==12 and
         value['provider_status']=='COMPLETE' and value['runtime_status']=='TRANSFER_PARTIAL' and
         value['public_status']=='PUBLIC_NOT_RUN' and value['saved_source_sha256']==PREDECESSOR_SOURCE,
         'exact v23 complete provider / partial runtime predecessor required')
    need(value['checkpoint_archive_bytes_verified'] is False and value['whole_provider_inventory_verified'] is False and
         value['checkpoint_metadata_only']['body_consumed_bytes']==0 and
         value['checkpoint_provider_presence']=='HTTP200_CONTENT_LENGTH_VERIFIED','predecessor qualified retrieval scope differs')
    rows={**value['artifacts'],'handoff':value['handoff']};blobs={}
    for key,row in rows.items():
        data=regular(row['path'])
        need(len(data)==row['bytes'] and sha(data)==row['sha256'],'predecessor descriptor changed: '+key)
        blobs[key]=(Path(row['path']).name,data)
    audit=json.loads(blobs['terminal_audit'][1]);validation=json.loads(blobs['validation'][1]);checkpoint=json.loads(blobs['checkpoint'][1])
    need(sha(blobs['terminal_audit'][1])==TERMINAL_AUDIT_SHA and audit['status']=='PASS' and audit['valid'] is True and
         audit['version']==23 and audit['provider_status']=='COMPLETE' and audit['runtime_status']=='TRANSFER_PARTIAL',
         'predecessor independent terminal audit differs')
    need(checkpoint['status']=='TERMINAL_EVIDENCE_VERIFIED' and validation['valid'] is True and
         validation['version']==23 and validation['kernel_id']==138123872 and validation['clock']['within_deadline'] is True and
         validation['saved_source_sha256']==PREDECESSOR_SOURCE and validation['status']=='TRANSFER_PARTIAL',
         'predecessor validated terminal/source/clock differs')
    need(sha(blobs['saved_source'][1])==PREDECESSOR_SOURCE,'exact predecessor saved source required')
    for key in ('validation','retrieval'):
        need(checkpoint[key]['sha256']==sha(blobs[key][1]) and audit[key]['sha256']==sha(blobs[key][1]),'predecessor terminal reconciliation differs')
    need(validation['retrieval_receipt_sha256']==sha(blobs['retrieval'][1]),'predecessor retrieval identity differs')
    return value,raw,blobs


def emit_predecessor(output,evidence):
    value,descriptor_raw,blobs=evidence
    folder=output/'predecessor';folder.mkdir();rows={}
    for key,(name,raw) in blobs.items():
        path=folder/name;path.write_bytes(raw);rows[key]=file_row(path,'predecessor/'+name)
    (output/'PREDECESSOR-DESCRIPTORS.json').write_bytes(descriptor_raw)
    record={'format':'irisx/transfer003-predecessor-evidence-v1','numeric_notebook_version':23,
           'code_dataset_version':12,'notebook_id':138123872,'code_dataset_id':12504696,
           'provider_status':'COMPLETE','runtime_status':'TRANSFER_PARTIAL','public_status':'PUBLIC_NOT_RUN',
           'saved_source_sha256':PREDECESSOR_SOURCE,'within_absolute_deadline':True,
           'whole_provider_inventory_verified':False,'checkpoint_provider_presence':value['checkpoint_provider_presence'],
           'checkpoint_archive_bytes_verified':False,'checkpoint_metadata_only':value['checkpoint_metadata_only'],
           'public_score':None,'goal_met':False,'operational_success':False,'science_complete':False,'evidence':rows,
           'sealed_predecessor_descriptors':file_row(output/'PREDECESSOR-DESCRIPTORS.json'),
           'qualification':'Selected numeric23 retrieval and sealed archive integrity verified; separate checkpoint header-only presence. No checkpoint body, whole provider inventory, VM teardown or billable GPU-duration claim.'}
    write(output/'PREDECESSOR-EVIDENCE.json',record)
    return file_row(output/'PREDECESSOR-EVIDENCE.json')


def emit_generation_policy(output,files):
    member=RUNTIME_PREFIX+'call_policy.py';source=files[member];tree=ast.parse(source)
    constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and
               len(n.targets)==1 and isinstance(n.targets[0],ast.Name)}
    expected={'GENERATION_HARD_SECONDS':180.0,'GENERATION_SOFT_SECONDS':175.0,'OTHER_HARD_SECONDS':120.0,'OTHER_SOFT_SECONDS':115.0}
    need(constants==expected,'exact source-bound generation/likelihood budgets required')
    policy_node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='policy')
    value=next(n.value for n in policy_node.body if isinstance(n,ast.Return))
    need(isinstance(value,ast.Dict),'literal generation policy required')
    policy={ast.literal_eval(k):constants[v.id] if isinstance(v,ast.Name) else ast.literal_eval(v) for k,v in zip(value.keys,value.values)}
    # Runtime protocol.digest uses sorted ASCII JSON plus one trailing newline.
    runtime_digest=sha(json.dumps(policy,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()+b'\n')
    record={'format':'irisx/transfer002-source-bound-generation-policy-v1','source_member':member,
            'source_sha256':sha(source),'runtime_policy':policy,'runtime_policy_sha256':runtime_digest,
            'generation_hard_seconds':180,'generation_work_seconds':175,'likelihood_hard_seconds':120,'likelihood_work_seconds':115,
            'calibration_and_training':'unchanged historical120s hard cap and branch-bound work deadline; no new115s soft limit',
            'execution_cutoff_seconds':42000,'outer_cutoff_seconds':42180,'provider_runtime_seconds':42300,'global_seconds':43200,
            'timing_refresh_source_member':RUNTIME_PREFIX+'timing_refresh.py',
            'timing_refresh_source_sha256':sha(files[RUNTIME_PREFIX+'timing_refresh.py']),
            'scientific_model_material_panels_scoring_unchanged':True,'forecast_is_guarantee':False}
    need(encoded(record)==regular(PRIOR_RELEASE/'GENERATION-CALL-POLICY.json'),'unchanged generation policy descriptor required')
    write(output/'GENERATION-CALL-POLICY.json',record)
    return {**file_row(output/'GENERATION-CALL-POLICY.json'),'runtime_policy_sha256':runtime_digest,
            'source_member':member,'source_sha256':sha(source)}



def emit_checkpoint_policy(output,files):
    # Invoke only the exact frozen, pure schedule contract. Model/network imports
    # are forbidden, and -I/-B avoid environment imports and source mutation.
    code = r"""import builtins,json,sys
original=builtins.__import__
def guarded(name,*a,**k):
    if name.split('.')[0] in ('torch','transformers','peft','kaggle','requests','httpx','socket') or name in ('urllib.request','urllib.error'):
        raise AssertionError('model/network import forbidden in checkpoint policy assembly')
    return original(name,*a,**k)
builtins.__import__=guarded
sys.path.insert(0,sys.argv[1])
from tools.arc_qwen_transfer_20261012.checkpoint_policy import contract,GLOBAL,TTT,FIXTURE
print(json.dumps({'global':contract(GLOBAL,'global_grid'),'ttt':contract(TTT,'representative_ttt'),
                  'fixture':contract(FIXTURE,'global_grid')},sort_keys=True,separators=(',',':')))
"""
    result=subprocess.run([sys.executable,'-I','-B','-c',code,str(WORK.absolute())],
                          capture_output=True,check=True,timeout=30,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','CUDA_VISIBLE_DEVICES':''})
    need(len(result.stdout)<=16384 and not result.stderr,'bounded clean checkpoint policy source result required')
    contracts=json.loads(result.stdout)
    expected={'global':('transfer-global-64-256-v1',[0,64,256],False,'global_grid','global'),
              'ttt':('transfer-ttt-0-8-16-v1',[0,8,16],False,'representative_ttt','task'),
              'fixture':('transfer-fixture-1-2-v1',[0,1,2],True,'global_grid','global')}
    members=[RUNTIME_PREFIX+'checkpoint_policy.py',RUNTIME_PREFIX+'protocol.py',SHARED_CHECKPOINT]
    identities={name:sha(files[name]) for name in members}
    for key,(schedule,updates,fixture,branch,scope) in expected.items():
        value=contracts[key]
        need(value['format']=='irisx/transfer-checkpoint-schedule-v1' and value['schedule_id']==schedule and
             value['allowed_updates']==updates and value['fixture_only'] is fixture and value['branch_id']==branch and value['scope']==scope,
             'source checkpoint policy differs from reviewed closed schedules')
        need(value['source_sha256']=={Path(n).name:identities[n] for n in members[:2]},'checkpoint policy is not source-bound')
    need(set(contracts)==set(expected),'closed checkpoint contract set required')
    record={'format':'irisx/transfer003-source-bound-checkpoint-policy-v1','contracts':contracts,'source_sha256':identities}
    write(output/'CHECKPOINT-POLICY.json',record)
    return file_row(output/'CHECKPOINT-POLICY.json')

def verify_descriptors(output):
    """Resolve release descriptors in their documented root, payload, or archive context."""
    output=Path(output);count=0
    def row(value,base=output):
        nonlocal count
        name=safe_name(value['path']);raw=regular(base/name)
        expected=value.get('sha256',value.get('file_sha256'))
        need(expected==sha(raw),'relative descriptor hash differs: '+name)
        if 'bytes' in value:need(type(value['bytes']) is int and value['bytes']==len(raw),'relative descriptor size differs: '+name)
        count+=1
    def walk(value):
        if isinstance(value,dict):
            if 'path' in value and ('sha256' in value or 'file_sha256' in value):row(value)
            for key,item in value.items():walk(item)
        elif isinstance(value,list):
            for item in value:walk(item)
    publication=json.loads(regular(output/'publication-manifest.json'))
    for key,value in publication.items():
        if key!='datasets':walk(value)
    payload=output/'code-payload'
    code=json.loads(regular(payload/'manifest.json'))
    with zipfile.ZipFile(payload/'source.zip') as archive:
        need(sorted(archive.namelist())==sorted(code['files']),'archive member closure differs')
        expanded={name:archive.read(name) for name in archive.namelist()}
    for name,descriptor in code['files'].items():
        need(len(expanded[name])==descriptor['bytes'] and sha(expanded[name])==descriptor['sha256']==code['source_identity'][name],
             'source archive inventory differs: '+name)
        count+=1
    archive=code['archive'];row({'path':archive['name'],'bytes':archive['bytes'],'sha256':archive['sha256']},payload)
    layouts=json.loads(regular(output/'provider-layout-contracts.json'))
    for dataset in publication['datasets']:
        base=output/safe_name(dataset['payload_root']);row(dataset['root_manifest'],base)
        for descriptor in dataset['upload_inventory']:row(descriptor,base)
        row(dataset['transport_archive'])
        need(dataset['expected_readback_layouts']==layouts,'provider readback layouts differ')
    for kind,rows in layouts.items():
        for descriptor in rows:
            name=safe_name(descriptor['path'])
            source_name=name.removeprefix('source/') if kind=='extracted-source-directory' else name
            raw=regular(payload/name) if kind=='original-upload' or name in ('manifest.json','NOTICE.txt') else expanded[source_name]
            need(len(raw)==descriptor['bytes'] and sha(raw)==descriptor['sha256'],'virtual provider-layout descriptor differs: '+name)
            count+=1
    for name in ('SOURCE-FREEZE.json','PANEL-FREEZE-RECEIPT.json','PREDECESSOR-EVIDENCE.json'):
        walk(json.loads(regular(output/name)))
    if (output/'ASSEMBLY-INVENTORY.json').exists():
        inventory=json.loads(regular(output/'ASSEMBLY-INVENTORY.json'))
        actual={p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file() and p.name!='ASSEMBLY-INVENTORY.json'}
        need(set(inventory)==actual,'final assembly inventory is not closed')
        need(all(name==descriptor['path'] for name,descriptor in inventory.items()),'assembly inventory path key differs')
        walk(inventory)
    need(publication['source_freeze_sha256']==sha(regular(output/'SOURCE-FREEZE.json')),'source freeze descriptor differs')
    return {'format':'irisx/transfer-release-descriptor-verification-v1','status':'PASS','verified_descriptors':count,
            'relative_root_payload_and_archive_contexts_verified':True,'model_calls':0,'provider_calls':0,
            'source_archive_members':len(expanded),'runtime_approval_emitted_name_matches':publication['runtime_source_approval'] is None or publication['runtime_source_approval']['path']=='RUNTIME-SOURCE-APPROVAL.json'}


def build(destination,*,runtime_approval=None):
    output=Path(destination).absolute()
    need(not output.exists() and not any(p.is_symlink() for p in (output,*output.parents)),'fresh unlinked output required')
    for source in (WORK.absolute(),BASE.absolute(),(ROOT/'deployment').absolute(),(ROOT/'worktree').absolute(),PREVIOUS.absolute(),HERE.absolute()):
        need(not (output==source or output in source.parents or source in output.parents),'output overlaps source')
    files,baseline=collect();reviewed=runtime_approval is not None
    approval,approval_raw=approval_check(runtime_approval,files) if reviewed else (None,None)
    predecessor=predecessor_evidence()
    prior=json.loads(regular(PRIOR_RELEASE/'publication-manifest.json'))
    refs=[CODE_REFERENCE]+prior['notebooks'][0]['dataset_sources'][1:]
    need(len(refs)==8 and len(set(refs))==8,'exact eight Dataset references')
    panel_raw=regular(PRIOR_RELEASE/'frozen-panel-plan.json')
    panel_receipt_raw=regular(PRIOR_RELEASE/'PANEL-FREEZE-RECEIPT.json')
    panel_receipt=json.loads(panel_receipt_raw)
    need(sha(panel_raw)==PANEL_SHA==panel_receipt['panel']['sha256'] and panel_receipt['exclusion_manifest']['sha256']==EXCLUSIONS_SHA, 'frozen panel receipt mismatch')
    addendum_raw=regular(PRIOR_RELEASE/'MATERIAL-ADDENDUM.json')
    addendum=json.loads(addendum_raw)
    addendum_digest=sha(json.dumps(addendum,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode())
    need(addendum_digest==ADDENDUM_SHA,'exact reviewed model addendum required')
    output.mkdir(parents=True);payload=output/'code-payload';payload.mkdir()
    (output/'frozen-panel-plan.json').write_bytes(panel_raw)
    (output/'panel-freeze').mkdir()
    (output/'panel-freeze/frozen-panel-plan.json').write_bytes(panel_raw)
    (output/EXCLUSIONS).write_bytes(files[EXCLUSIONS])
    predecessor=emit_predecessor(output,predecessor)
    generation_policy=emit_generation_policy(output,files)
    checkpoint_policy=emit_checkpoint_policy(output,files)
    (output/'FINAL-RUNTIME-FREEZE.json').write_bytes(regular(AUTHOR_FREEZE))
    (output/'ARCHIVE-CAPACITY-RECEIPT.json').write_bytes(regular(PRIOR_RELEASE/'ARCHIVE-CAPACITY-RECEIPT.json'))
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
    freeze={'format':'irisx/qwen14b-transfer-checkpoint-repair-source-freeze-v1','source_identity':identity,'files':inventory,
            'source_identity_sha256':sha(canonical(identity)),'runtime_member_count':len(files),'total_expanded_bytes':sum(map(len,files.values())),
            'baseline_member_count':175,'baseline_manifest_sha256':BASE_MANIFEST_SHA,'baseline_archive_sha256':BASE_ARCHIVE_SHA,
            'prior_source_zip_sha256':PRIOR_SOURCE_ZIP_SHA,'frozen_inner_source_identity_sha256':AUTHOR_INNER_IDENTITY_SHA,
            'genuine_tiny_inner_source_identity_sha256':GENUINE_TINY_INNER_IDENTITY_SHA,
            'genuine_tiny_scope':'Historical generation-repair tiny main is unchanged provenance only. Checkpoint repair is qualified by a separate native production-schedule test; no additional full main or pretrained model test claimed.',
            'generation_call_policy':generation_policy,'checkpoint_policy':checkpoint_policy,'predecessor_evidence':predecessor,
            'author_runtime_freeze':file_row(output/'FINAL-RUNTIME-FREEZE.json'),
            'capacity_export_validation':file_row(output/'ARCHIVE-CAPACITY-RECEIPT.json'),
            'baseline_changed':{n:{'before_sha256':baseline[n],'after_sha256':identity[n]} for n in baseline if baseline[n]!=identity[n]},
            'prior_changed':{n:{'before_sha256':json.loads(regular(PRIOR_RELEASE/'code-payload/manifest.json'))['source_identity'][n],'after_sha256':identity[n]} for n in sorted(ALLOWED_CHANGED)},
            'prior_added':{n:identity[n] for n in sorted(ALLOWED_ADDED)},'baseline_added':{n:h for n,h in identity.items() if n not in baseline},
            'build_script_sha256':sha(regular(__file__)),'notebook_builder_sha256':sha(regular(HERE/'build_notebook.py')),
            'no_model_mount_acceptance_helper':file_row(output/'accept-downloaded-mount.py'),
            'source_zip_sha256':archive['sha256'],'code_manifest_sha256':pins['code']['manifest_sha256'],
            'pins_sha256':sha(regular(output/'pins.json')),'notebooks':notebooks,'runtime_source_approval':approval,
            'source_review_only':not reviewed,'dispatchable':False,
            'limits':{'program_seconds':43200,'global_seconds':43200,'provider_runtime_seconds':42300,'execution_cutoff_seconds':42000,'outer_cutoff_seconds':42180,
                      'source_expanded_bytes':16*1024**2,'tokenizer_member_bytes':12*1024**2,'other_member_bytes':2*1024**2},
            'claim':'Local unpublished candidate. Active template is non-dispatchable until exact epoch patch and separate operator review.'}
    write(output/'SOURCE-FREEZE.json',freeze)
    dataset=copy.deepcopy(prior['datasets'][0]);dataset.update(expected_predecessor_version=12,expected_version=13,
        version_status='PROSPECTIVE_UNUPLOADED',delete_old_versions=False,payload_root='code-payload',root_manifest={'path':'manifest.json','sha256':pins['code']['manifest_sha256']},
        upload_inventory=upload,upload_inventory_sha256=sha(canonical(upload)),expected_readback_layouts=layouts,
        transport_archive=file_row(output/'code-dataset-upload.zip'),version_notes='Transfer003 bounded checkpoint repair: source-bound global0/64/256 and TTT0/8/16; legacy portfolio cap, generation policy, clocks, science and materials unchanged.')
    need(dataset['id']==12504696 and dataset['is_private'] is True,'same private code Dataset')
    notebook_contract=[]
    for role,active in (('inactive',False),('active-template',True)):
        notebook_contract.append({'role':'transfer003' if active else role,'template_role':role,**notebooks[role],'existing_notebook_reference':prior['notebooks'][0]['existing_notebook_reference'],
            'existing_notebook_id':138123872,'expected_predecessor_version':24 if active else 23,'expected_version':25 if active else 24,
            'predecessor_source_sha256':None if active else PREDECESSOR_SOURCE,'save_mode':'RUN' if active else 'QUICK_SAVE',
            'title':'IRIS-X Learning Agent 20261011','language':'python','kernel_type':'notebook',
            'save_version_value':1 if active else 3,'session_timeout_seconds':42300 if active else None,'timeout_seconds':42300 if active else None,
            'run_authorized':bool(active and reviewed),
            'manual_start':active,'enable_model':active,'enable_gpu':active,'enable_tpu':False,'enable_internet':False,'is_private':True,
            'machine_shape':'NvidiaRtxPro6000' if active else None,'dataset_sources':refs,'model_sources':[MODEL_REFERENCE],
            'competition_sources':copy.deepcopy(prior['notebooks'][0]['competition_sources']),
            'docker_image':prior['notebooks'][0]['docker_image'],'program_session_seconds':43200,'global_seconds':43200,
            'provider_runtime_seconds':42300,'execution_cutoff_seconds':42000,'outer_cutoff_seconds':42180,'predispatch_epoch':None,'epoch_policy':'replace sole None assignment just before dispatch; no fallback or clock reset',
            'output_root':'/kaggle/working/irisx-qwen14b-transfer-20261012-run003',
            'source_parent':'/kaggle/working/irisx-qwen14b-transfer-20261012-source003',
            'dispatch_epoch_patch':{'assignment':'PREDISPATCH_EPOCH','maximum_patch_age_seconds':60,'cell_index':1,'required_original_value':None,'maximum_changed_assignments':1},
            'source_dispatch_ready':False,'requires_exact_operator_review':True})
    publication={'format':'irisx/qwen14b-transfer-checkpoint-repair-publication-contract-v1','source_freeze_sha256':sha(regular(output/'SOURCE-FREEZE.json')),
        'source_identity_sha256':freeze['source_identity_sha256'],'datasets':[dataset],'notebooks':notebook_contract,
        'predecessor_readiness':{**predecessor,'notebook_version':23,'notebook_source_sha256':PREDECESSOR_SOURCE,'provider_status':'COMPLETE','runtime_status':'TRANSFER_PARTIAL'},
        'generation_call_policy':generation_policy,'checkpoint_policy':checkpoint_policy,
        'upload_authorities':['https://storage.googleapis.com:443','https://www.googleapis.com:443'],
        'public_exclusions':{'path':EXCLUSIONS,'sha256':EXCLUSIONS_SHA},
        'frozen_panel_plan':file_row(output/'frozen-panel-plan.json'),
        'model_material_addendum':{**file_row(output/'MATERIAL-ADDENDUM.json'),'canonical_identity_sha256':ADDENDUM_SHA},
        'no_model_mount_acceptance_helper':file_row(output/'accept-downloaded-mount.py'),
        'terminal_contract':{'active_role':'transfer003','statuses':['TRANSFER_COMPLETE','TRANSFER_PARTIAL','TRANSFER_NOT_ADMITTED','TRANSFER_FAILED'],
            'success_statuses':['TRANSFER_COMPLETE'],'partial_statuses':['TRANSFER_PARTIAL','TRANSFER_NOT_ADMITTED'],'failure_statuses':['TRANSFER_FAILED'],
            'file_byte_caps':{'terminal-receipt.json':1024**2,'launcher/result.json':1024**2,'ordinary_evidence_member':16*1024**2,'large_diagnostic_member':64*1024**2,'checkpoint_member':32*1024**2},
            'archive_caps':{'evidence_expanded_bytes':512*1024**2,'evidence_archive_bytes':544*1024**2,'evidence_members':12000,'checkpoint_expanded_bytes':2*1024**3,'checkpoint_archive_bytes':2*1024**3+2*1024**2,'checkpoint_members':1025},
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
    write(output/'DESCRIPTOR-VERIFICATION.json',verify_descriptors(output))
    write(output/'ASSEMBLY-INVENTORY.json',{p.relative_to(output).as_posix():file_row(p,p.relative_to(output).as_posix())
        for p in sorted(output.rglob('*')) if p.is_file()})
    verify_descriptors(output)
    need(collect()[0]==files,'runtime changed during assembly; discard mixed candidate')
    return {'output':str(output),'status':'LOCAL_UNPUBLISHED_CANDIDATE' if reviewed else 'SOURCE_ONLY_NONDISPATCHABLE_PREVIEW',
            'source_members':len(files),'expanded_bytes':freeze['total_expanded_bytes'],'source_zip_sha256':archive['sha256'],
            'source_freeze_sha256':sha(regular(output/'SOURCE-FREEZE.json')),'publication_manifest_sha256':sha(regular(output/'publication-manifest.json'))}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    parser.add_argument('--runtime-approval',type=Path);args=parser.parse_args()
    print(json.dumps(build(args.output,runtime_approval=args.runtime_approval),indent=2))
