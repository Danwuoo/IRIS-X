"""Prepare and independently review-gate the code18/run005 local successor.

The original code17 candidate is a mandatory exact, closed input. Proposal mode
creates inert review materials only. Final mode requires separately supplied,
hash-bound runtime and material approvals of that exact proposal. No provider,
authentication, model or evaluator ZIP-member calls occur in this assembler.
"""
from __future__ import annotations
import argparse, copy, hashlib, io, json, os, re, stat, sys, types, zipfile
from pathlib import Path, PurePosixPath

BASE_MANIFEST = '4dbd7daa4d7817970f702aaff32f9783d529c8b136e92536c788826e24d3cac1'
BASE_ASSEMBLY = '17b644b2d10dd134f00208d60529a59720fa8233fef46632f1e529a99784fa65'
BASE_SOURCE = '22a736bd06f10a5708a0b0c69ac3b89128394e3775c0780d19d1b999b8cc1ba1'
BASE_ARCHIVE = '778ac5474a176358e0789cd3b82db5d91278864724507dc56d6c33bf6cdefb9e'
BASE_ENVIRONMENT = '39d56dd0b5167ba43d9958ace70a8c2b031f29d421d051cfb75cbcff985f4c71'
HELPER_INVENTORY = 'd88b66c3b45435c2b328c2cc36c9c605c889ba76e48a36c22729db0ec2fda710'
V33_SAVED = 'e7747c8013a9149cf7331954fd583fd8770adb416b2881074c9875f94c3f7761'
V33_SUBMITTED = 'a3bdc6b13870a0dcc6862a08b2ebbef6f07419e9147c1c989fb6a4403abba037'
V33_ARCHIVE = '06825c68f991fd8e9b4f1a3cf76cf5e06fae18607918bf0840991f1a9a6591cd'
V33_DIAGNOSTIC = '7e6161727accff39afaba37e75f1527db7a638098cbcb4f58d88e95fb7b0e8bc'
V33_RETRIEVAL = '8f7446f1182bdeacba86e982793222203b948ab4dac6831b712a786fa3c29042'
DREF = 'danielwuu/iris-x-learning-agent-code-20261011'
RUN = '/kaggle/working/irisx-qwen14b-rlvr-20261012-run005'
SOURCE = '/kaggle/working/irisx-qwen14b-rlvr-20261012-source005'
ENVIRONMENT = '/tmp/irisx-qwen14b-rlvr-20261012-environment005'
DEPLOYMENT_NAMES = ('source_loader.py','notebook_builder.py','launch_notebook.py','prepare_entry.py','parent_entry.py')
CAP = 128 * 1024**2

def need(ok, message):
    if not ok: raise ValueError(message)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def encoded(value): return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def relative(name):
    need(type(name)is str and name and '\\' not in name and ':' not in name, 'unsafe relative name')
    path=PurePosixPath(name)
    need(not path.is_absolute() and str(path)==name and all(x not in ('','.','..') for x in path.parts),'unsafe relative name')
    return name
def ordinary(path):
    path=Path(os.path.abspath(path))
    for p in (path,*path.parents):
        try:info=p.lstat()
        except FileNotFoundError:continue
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,'linked/reparse path')
    return path
def read(path,cap=CAP):
    path=ordinary(path);before=path.stat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=cap,'bounded regular input')
    raw=path.read_bytes();after=path.stat()
    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and len(raw)==before.st_size,'input changed')
    return raw
def pinned(path,digest):
    raw=read(path);need(sha(raw)==digest,'exact input hash: '+Path(path).name);return raw
def desc(raw,path): return {'path':relative(path),'bytes':len(raw),'sha256':sha(raw)}
def obj(raw):
    def pairs(rows):
        result={}
        for k,v in rows:need(k not in result,'duplicate JSON key');result[k]=v
        return result
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite JSON'))
    need(type(value)is dict,'JSON object required');return value
def zip_blobs(files,stored=False):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(relative(name),(2026,10,12,0,0,0));info.create_system=3;info.external_attr=(stat.S_IFREG|0o644)<<16
            info.compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
            archive.writestr(info,raw,compress_type=info.compress_type,compresslevel=None if stored else 9)
    return stream.getvalue()
def module(raw,name,path):
    result=types.ModuleType(name);result.__file__=str(path);result.__package__='';sys.modules[name]=result
    exec(compile(raw,str(path),'exec',dont_inherit=True,optimize=sys.flags.optimize),vars(result));return result

def verify_base(root):
    root=ordinary(root);inventory=obj(pinned(root/'ASSEMBLY-INVENTORY.json',BASE_ASSEMBLY))
    paths=set()
    for p in root.rglob('*'):
        ordinary(p)
        if p.is_file():paths.add(p.relative_to(root).as_posix())
    need(paths==set(inventory)|{'ASSEMBLY-INVENTORY.json'} and len(paths)==325,'exact closed code17 candidate required')
    files={}
    for name,row in inventory.items():
        relative(name);raw=read(root/name);need({'bytes':len(raw),'sha256':sha(raw)}==row,'code17 member differs: '+name);files[name]=raw
    need(sha(files['publication-manifest.json'])==BASE_MANIFEST and sha(files['code-payload/source.zip'])==BASE_ARCHIVE,'base source/manifest binding')
    with zipfile.ZipFile(io.BytesIO(files['code-payload/source.zip'])) as z:
        names=z.namelist();need(len(names)==len(set(names))==259,'complete original source ZIP')
        source={relative(n):z.read(n) for n in names}
    need(all(files['producer-source/'+n]==b for n,b in source.items()),'original source materialization differs')
    need(sha(canonical(sorted((n,sha(b)) for n,b in source.items())))==BASE_SOURCE,'original raw source closure')
    need(sum(n.startswith('baseline/') for n in source)==200,'complete inherited baseline200')
    return files,source

def derive_environment(raw):
    need(sha(raw)==BASE_ENVIRONMENT,'original reviewed environment required')
    document=obj(raw);model=document['model_config'];old='/kaggle/working/irisx-qwen14b-rlvr-20261012-source004'
    for key in ('contract_path','environment_lock_path','tokenizer_path'):
        need(model[key].startswith(old+'/runtime/'),'exact source004 material path required')
        model[key]=SOURCE+model[key][len(old):]
    updated=encoded(document);reverse=obj(updated)
    for key in ('contract_path','environment_lock_path','tokenizer_path'):reverse['model_config'][key]=old+reverse['model_config'][key][len(SOURCE):]
    need(encoded(reverse)==raw,'environment changed beyond exactly three namespace paths')
    return updated

def derive_source(old,parent_raw,environment_raw):
    files=dict(old);need(parent_raw!=old['owned_runtime/parent_scoring.py'],'nonempty independently reviewed parent repair required')
    compile(parent_raw,'owned_runtime/parent_scoring.py','exec');files['owned_runtime/parent_scoring.py']=parent_raw
    release=old['owned_runtime/release.py']
    release,count=re.subn(rb"(?m)^REVIEWED_ENVIRONMENT_SHA256 = '[0-9a-f]{64}'$",("REVIEWED_ENVIRONMENT_SHA256 = '"+sha(environment_raw)+"'").encode(),release)
    need(count==1,'one environment source pin')
    normal,count=re.subn(rb"(?m)^NORMALIZED_SOURCE_CONTRACT_SHA256 = '[0-9a-f]{64}'$",b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None',release)
    need(count==1,'one normalized source pin')
    normalized=dict(files);normalized['owned_runtime/release.py']=normal
    normal_sha=sha(canonical(sorted((n,sha(b)) for n,b in normalized.items())))
    files['owned_runtime/release.py']=normal.replace(b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None',("NORMALIZED_SOURCE_CONTRACT_SHA256 = '"+normal_sha+"'").encode(),1)
    changed={n for n in files if files[n]!=old[n]}
    need(changed=={'owned_runtime/parent_scoring.py','owned_runtime/release.py'},'source repair delta exceeded two members')
    need(all(files[n]==old[n] for n in files if n.startswith('baseline/')),'baseline200 changed')
    hashes={n:sha(b) for n,b in sorted(files.items())};source_sha=sha(canonical(sorted(hashes.items())))
    archive=zip_blobs(files,stored=True)
    inventory={'format':'owned-rl-production-driver-location-successor-source-inventory-v1','members':259,'files':hashes,
        'source_sha256':source_sha,'normalized_source_contract_sha256':normal_sha,'environment_sha256':sha(environment_raw),
        'predecessor_source_sha256':BASE_SOURCE,'predecessor_archive_sha256':BASE_ARCHIVE,
        'unchanged_baseline_members':200,'unchanged_source_members':257,'production_dispatch_authorized':False}
    return files,archive,encoded(inventory),normal_sha,source_sha

def rebuild_source(*,repository_root,parent_overlay,parent_overlay_sha,output_root):
    """Rebuild exact runtime bytes from Git source/map plus the small repair.

    This stage requires no operational candidate, predecessor evidence, reviews,
    credentials or provider observations. The generated release pin file and map
    are compact artifacts the owner may separately retain in Git after review.
    """
    repo,overlay,output=map(ordinary,(repository_root,parent_overlay,output_root))
    need(not output.exists(),'fresh source output required')
    need(output.is_relative_to(repo/'.irisx') and output!=repo/'.irisx','ignored source output required')
    need(overlay.is_relative_to(repo) and not overlay.is_relative_to(repo/'.irisx'),'tracked repair overlay required')
    tool=repo/'tools/arc_qwen_rlvr004_20261013'
    mapping=obj(pinned(tool/'runtime-path-map.json','0b77706cd31729f4e88f4937ca5f2749c1b8711e2890fee0ca863bbaf779fd38'))
    old={}
    for name,row in mapping['files'].items():
        relative(name);relative(row['repository_path']);raw=read(repo/row['repository_path'])
        need({'bytes':len(raw),'sha256':sha(raw)}=={k:row[k] for k in ('bytes','sha256')},'Git predecessor source member differs');old[name]=raw
    need(len(old)==259 and sha(zip_blobs(old,stored=True))==BASE_ARCHIVE,'exact Git source reconstruction')
    environment=derive_environment(read(tool/'release/consumer-release/environment.json'))
    source,archive,inventory,normalized,source_sha=derive_source(old,pinned(overlay,parent_overlay_sha),environment)
    freeze={'format':'irisx/rlvr-source-freeze-v1','source_sha256':source_sha,'source_archive_sha256':sha(archive),'source_members':259,
        'files':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in sorted(source.items())},'original_baseline200_exact':True,
        'producer_inventory_artifact_sha256':sha(inventory),'self_consistency_pins':{'NORMALIZED_SOURCE_CONTRACT_SHA256':normalized,
            'FINAL_V25_POLICY_SHA256':'3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda','REVIEWED_ENVIRONMENT_SHA256':sha(environment)},'independent_approval_is_external':True}
    updated=copy.deepcopy(mapping);updated.update(source_sha256=source_sha,source_archive_sha256=sha(archive),publication_manifest_sha256=None,
        source_mapping_not_runtime_admission=True,source_only_rebuild_requires_operational_evidence=False)
    for name,raw in source.items():updated['files'][name].update(bytes=len(raw),sha256=sha(raw))
    updated['files']['owned_runtime/parent_scoring.py']['repository_path']=overlay.relative_to(repo).as_posix()
    updated['files']['owned_runtime/release.py']['repository_path']='tools/arc_qwen_rlvr004_20261013/driver_path_repair/release_run005.py'
    blobs={'source.zip':archive,'SOURCE-INVENTORY.json':inventory,'SOURCE-FREEZE.json':encoded(freeze),'environment-run005.json':environment,
        'runtime-path-map-run005.json':encoded(updated),'release_run005.py':source['owned_runtime/release.py'],
        **{'producer-source/'+n:b for n,b in source.items()}}
    output.mkdir(parents=True)
    for name,raw in blobs.items():
        destination=ordinary(output/relative(name));destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as stream:stream.write(raw)
        destination.chmod(0o644)
    return {'status':'EXACT_GIT_SOURCE_SUCCESSOR_REBUILT','source_sha256':source_sha,'source_archive_sha256':sha(archive),
        'environment_sha256':sha(environment),'output_root':str(output),'source_members':259,'provider_calls':0,'model_or_GPU_calls':0,
        'operational_evidence_required':False,'independent_approval_is_external':True}

def derive_deployment(base):
    result={n:base['code-payload/deployment/'+n] for n in DEPLOYMENT_NAMES}
    for name,substitutions in {'source_loader.py':[(DREF+'/17',DREF+'/18')],
        'notebook_builder.py':[('irisx-qwen14b-rlvr-20261012-run004','irisx-qwen14b-rlvr-20261012-run005'),('irisx-qwen14b-rlvr-20261012-source004','irisx-qwen14b-rlvr-20261012-source005')],
        'launch_notebook.py':[('irisx-qwen14b-rlvr-20261012-environment004','irisx-qwen14b-rlvr-20261012-environment005'),('exact run004/source004 paths required','exact run005/source005 paths required')]}.items():
        for before,after in substitutions:
            need(result[name].count(before.encode())==1,'one exact deployment namespace occurrence: '+name)
            result[name]=result[name].replace(before.encode(),after.encode(),1)
        compile(result[name],name,'exec')
    wrappers=base['assembly/verify_parent_wrappers.py']
    for stem in ('environment','run','source'):
        before=('irisx-qwen14b-rlvr-20261012-'+stem+'004').encode();after=('irisx-qwen14b-rlvr-20261012-'+stem+'005').encode()
        need(wrappers.count(before)==1,'one wrapper namespace occurrence');wrappers=wrappers.replace(before,after,1)
    return result,wrappers

def dataset_namespace(base,review_path,review_sha):
    """Verify two target-free escrow-reference path changes; never open escrows."""
    need(review_path and review_sha,'independent solver namespace proof required')
    proof=obj(pinned(review_path,review_sha));old_material=obj(base['consumer-release/material_review.json'])
    need(proof.get('format')=='irisx/run005-solver-namespace-review-v1' and proof.get('status')=='PASS'
         and proof.get('path_substitutions')==2 and proof.get('reverse_byte_equality') is True,'reviewed two-path solver projection required')
    old_ref,new_ref=proof['old_solver'],proof['new_solver']
    old_raw=pinned(old_ref['path'],old_ref['sha256']);new_raw=pinned(new_ref['path'],new_ref['sha256'])
    need(len(old_raw)==old_ref['bytes'] and len(new_raw)==new_ref['bytes'] and old_ref['sha256']==old_material['dataset_file_sha256'],
         'original reviewed target-free solver bytes required')
    old=obj(old_raw);new=obj(new_raw)
    need(old.get('public_answers_read') is False and old.get('original_test_fields_retained') is False and old.get('cpu_fixture_only') is False,
         'authentic target-free solver scope required')
    need(old['denominators']=={'dev':16,'holdout':32,'ttt_dev':8,'ttt_holdout':8},'full original training evaluation denominators')
    projected=old_raw;expected=copy.deepcopy(old);old_prefix='/kaggle/working/irisx-qwen14b-rlvr-20261012-run004/'
    for scope in ('dev','holdout'):
        old_path=old['escrow'][scope]['path'];need(old_path.startswith(old_prefix),'original run004 solver escrow-reference path')
        new_path=RUN+'/'+old_path[len(old_prefix):];expected['escrow'][scope]['path']=new_path
        before=json.dumps(old_path,ensure_ascii=False).encode();after=json.dumps(new_path,ensure_ascii=False).encode()
        need(projected.count(before)==1,'one original escrow-reference string');projected=projected.replace(before,after,1)
        need(old['escrow'][scope]['sha256']==old_material['dataset_escrow_sha256'][scope],'escrow byte commitment changed')
    need(projected==new_raw and new==expected,'solver changed beyond two exact paths')
    need(proof.get('dataset_file_sha256')==new_ref['sha256'] and proof.get('prior_dataset_file_sha256')==old_ref['sha256']
         and proof.get('dataset_escrow_sha256')==old_material['dataset_escrow_sha256'],'solver namespace proof pins')
    return new_ref['sha256']

def predecessor(base,state,evidence):
    result={};selected={};receipt=obj(pinned(evidence/'RETRIEVAL-RECEIPT.json',V33_RETRIEVAL))
    need(receipt['numeric_output_version']==33 and receipt['reference']=='danielwuu/iris-x-learning-agent-20261011','v33 retrieval identity')
    for snap in (receipt['before'],receipt['after']):need(snap['version']==33 and snap['status']=='ERROR' and snap['source_sha256']==V33_SAVED and snap['gpu_stop'] is False,'v33 source/status bracket')
    for row in receipt['files']:
        name=relative(row['provider_path']);raw=read(evidence/'downloads'/name)
        need({'bytes':len(raw),'sha256':sha(raw)}=={k:row[k] for k in ('bytes','sha256')} and row['numeric_version']==33 and row['http_status']==200,'selected v33 output')
        target='predecessor-v33/selected/'+name;result[target]=raw;selected[name]=desc(raw,target)
    metadata={'code_receipt':state/'dataset-code-v17-receipt.json','launch_receipt':state/'notebook-rlvr004-receipt.json',
        'launch_journal':state/'notebook-rlvr004-journal.json','finalization':state/'finalization.json',
        'launch_wire':state/'notebook-rlvr004-wire.json','saved_source':state/'notebook-rlvr004-saved.ipynb',
        'retrieval_receipt':evidence/'RETRIEVAL-RECEIPT.json','terminal_diagnostic':evidence/'TERMINAL-DIAGNOSTIC.json',
        'terminal_checkpoint':evidence/'TERMINAL-CHECKPOINT.json'}
    refs={}
    for role,path in metadata.items():
        raw=read(path);target='predecessor-v33/metadata/'+role+path.suffix;result[target]=raw;refs[role]=desc(raw,target)
    prefix='irisx-qwen14b-rlvr-20261012-run004'
    for role,name in {'evidence_archive':prefix+'.evidence.zip','terminal_receipt':prefix+'.evidence.zip.terminal.json',
        'runtime_outer_closure':prefix+'/outer-closure.json','owned_result':prefix+'/owned-result.json'}.items():refs[role]=selected[name]
    need(refs['saved_source']['sha256']==V33_SAVED and refs['evidence_archive']['sha256']==V33_ARCHIVE and refs['evidence_archive']['bytes']==15908385 and refs['terminal_diagnostic']['sha256']==V33_DIAGNOSTIC,'exact failed v33 artifacts')
    launch=obj(result[refs['launch_receipt']['path']]);code=obj(result[refs['code_receipt']['path']]);diagnostic=obj(result[refs['terminal_diagnostic']['path']])
    need(launch['version']==33 and launch['submitted_source_sha256']==V33_SUBMITTED and launch['normalized_source_exact'] is True and code['version']==17 and code['exact_byte_roundtrip'] is True,'v33 launch/code identity')
    need(diagnostic['status']=='UNSEALED_SESSION_DIAGNOSTICS' and diagnostic['provider_status']=='ERROR' and diagnostic['diagnostic_transport_integrity_verified'] is True and diagnostic['external_stage_process_closure_verified'] is True and diagnostic['runtime_safe_closure'] is False and diagnostic['runtime_model_closure_verified'] is False and diagnostic['physical_costs_known'] is False and diagnostic['physical_journal_present_in_archive'] is False and diagnostic['public_score'] is None and diagnostic['actual_gpu_stop'] is False,'v33 diagnostic qualification')
    historical='historical-v31/PREDECESSOR-EVIDENCE.json';result[historical]=base['PREDECESSOR-EVIDENCE.json']
    result['historical-v31/PREDECESSOR-DESCRIPTORS.json']=base['PREDECESSOR-DESCRIPTORS.json']
    for name,raw in base.items():
        if name.startswith('predecessor/'):result['historical-v31/'+name]=raw
    proof={'format':'irisx/rlvr005-predecessor-evidence-v1','notebook_id':138123872,'numeric_notebook_version':33,
        'code_dataset_id':12504696,'code_dataset_version':17,'provider_status':'ERROR','saved_source_sha256':V33_SAVED,
        'submitted_source_sha256':V33_SUBMITTED,'evidence':refs,'selected_outputs':selected,'historical_v31':desc(result[historical],historical)}
    result['PREDECESSOR-EVIDENCE.json']=encoded(proof)
    return result

def consumer_bytes(base,release_raw,source_sha,source_archive_sha,collector_sha):
    helpers=obj(base['terminal-consumer/CONSUMER-INVENTORY.json'])['files'];need(len(helpers)==21 and sha(base['terminal-consumer/CONSUMER-INVENTORY.json'])==HELPER_INVENTORY,'original21 helpers')
    result={name.removeprefix('terminal-consumer/'):raw for name,raw in base.items() if name.startswith('terminal-consumer/')}
    need(set(result)==set(helpers)|{'CONSUMER-INVENTORY.json','CONSUMER-OPERATOR.json','reviewed_entry.py'},'closed24 consumer')
    need(all(sha(result[n])==h for n,h in helpers.items()),'consumer helper change')
    operator={'format':'owned-rl-batched-consumer-operator-v1','source_sha256':source_sha,'source_archive_sha256':source_archive_sha,
        'policy_sha256':'3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda','release_sha256':sha(release_raw),
        'collector_entry_sha256':collector_sha,'helper_inventory_sha256':HELPER_INVENTORY}
    result['CONSUMER-OPERATOR.json']=encoded(operator)
    replacement=('REVIEWED_OPERATOR_PINS_SHA256 = '+repr(sha(result['CONSUMER-OPERATOR.json']) if collector_sha else None)).encode()
    result['reviewed_entry.py'],count=re.subn(rb"(?m)^REVIEWED_OPERATOR_PINS_SHA256 = '[0-9a-f]{64}'$",replacement,result['reviewed_entry.py'])
    need(count==1,'one consumer entry literal');return result

def assemble(*,base_root,state_root,evidence_root,parent_overlay,parent_overlay_sha,output_root,mode,
             runtime_review=None,runtime_review_sha=None,material_review=None,material_review_sha=None,
             proposal=None,proposal_sha=None,collector=None,collector_sha=None,dataset_path_review=None,dataset_path_review_sha=None):
    need(mode in ('proposal','final'),'assembly mode')
    if mode=='final':need(all((runtime_review,runtime_review_sha,material_review,material_review_sha,proposal,proposal_sha,collector,collector_sha)),
                          'independent reviews/proposal/collector required')
    base_root,state_root,evidence_root,parent_overlay,output_root=map(ordinary,(base_root,state_root,evidence_root,parent_overlay,output_root))
    need(not output_root.exists(),'fresh successor output required')
    need(output_root.is_relative_to(base_root.parent) and output_root!=base_root.parent and not output_root.is_relative_to(base_root),'ignored sibling successor output required')
    base,old=verify_base(base_root);parent_raw=pinned(parent_overlay,parent_overlay_sha)
    dataset_sha=dataset_namespace(base,dataset_path_review,dataset_path_review_sha)
    environment=derive_environment(base['consumer-release/environment.json']);source,source_zip,source_inventory,normal_sha,source_sha=derive_source(old,parent_raw,environment)
    deployment,wrappers=derive_deployment(base);prior=obj(base['publication-manifest.json']);old_release=obj(base['notebook-release.json'])
    deployment_inventory={n:{'bytes':len(b),'sha256':sha(b)} for n,b in sorted(deployment.items())}
    proposal_doc={'format':'irisx/code18-run005-material-proposal-v1','status':'INDEPENDENT_REVIEW_REQUIRED','base_publication_manifest_sha256':BASE_MANIFEST,
        'base_source_sha256':BASE_SOURCE,'source_sha256':source_sha,'source_archive_sha256':sha(source_zip),'source_inventory_sha256':sha(source_inventory),
        'normalized_source_contract_sha256':normal_sha,'environment_sha256':sha(environment),'phase_policy_sha256':old_release['phase_policy_sha256'],
        'dataset_file_sha256':dataset_sha,'dataset_namespace_review_sha256':dataset_path_review_sha,'parent_overlay_sha256':parent_overlay_sha,'deployment_inventory':deployment_inventory,
        'changed_source_files':['owned_runtime/parent_scoring.py','owned_runtime/release.py'],'unchanged_source_members':257,'unchanged_baseline_members':200,
        'namespace':{'code':18,'inactive':34,'active':35,'run':RUN,'source':SOURCE,'environment':ENVIRONMENT,'release_role':'rlvr004'},
        'no_provider_or_model_calls':True,'GPU_validation_passed':False,'original_scorer_full167_denominator_preserved':True}
    approved=mode=='final'
    if approved:
        need(all((runtime_review,runtime_review_sha,material_review,material_review_sha,proposal,proposal_sha,collector,collector_sha)),'independent reviews/proposal/collector required')
        submitted=pinned(proposal,proposal_sha);need(submitted==encoded(proposal_doc),'final source differs from independently reviewed proposal')
        runtime_raw=pinned(runtime_review,runtime_review_sha);runtime=obj(runtime_raw);material_raw=pinned(material_review,material_review_sha);material=obj(material_raw)
        need(runtime['status']=='PASS' and runtime['proposal_sha256']==proposal_sha and runtime['source_sha256']==source_sha and runtime['source_archive_sha256']==sha(source_zip),'runtime independent review binding')
        need(material['status']=='APPROVED' and material['format']=='owned-rl-reviewed-material-v1' and material['proposal_sha256']==proposal_sha
            and material['runtime_review_sha256']==runtime_review_sha,'material independent review binding')
        for key in ('source_sha256','source_archive_sha256','environment_sha256','phase_policy_sha256','dataset_file_sha256','deployment_inventory'):need(material[key]==proposal_doc[key],'reviewed material field differs: '+key)
        old_material=obj(base['consumer-release/material_review.json'])
        for key in ('dataset_escrow_sha256','dataset_content_sha256'):need(material.get(key)==old_material.get(key),'original dataset/escrow binding changed')
        pinned(collector,collector_sha)
    else:
        runtime_raw=encoded({**proposal_doc,'status':'REVIEW_REQUIRED','proposal_sha256':sha(encoded(proposal_doc))})
        old_material=obj(base['consumer-release/material_review.json'])
        material_raw=encoded({'format':'owned-rl-reviewed-material-v1','status':'REVIEW_REQUIRED','proposal_sha256':sha(encoded(proposal_doc)),
            **{k:proposal_doc[k] for k in ('source_sha256','source_archive_sha256','environment_sha256','phase_policy_sha256','dataset_file_sha256','deployment_inventory')},
            'dataset_escrow_sha256':old_material.get('dataset_escrow_sha256'),'dataset_content_sha256':old_material.get('dataset_content_sha256'),'runtime_review_sha256':sha(runtime_raw)})
        collector_sha=None
    auxiliary={'NOTICE.txt':base['code-payload/NOTICE.txt'],'release/MATERIAL-REVIEW.json':material_raw,'release/REVIEWED-ENVIRONMENT.json':environment,'release/RUNTIME-REVIEW.json':runtime_raw,
        **{'deployment/'+n:b for n,b in deployment.items()}}
    payload_manifest={'format':'irisx/rlvr-code-material-v1','reference':DREF+'/18','source':{'archive':{'name':'source.zip','bytes':len(source_zip),'sha256':sha(source_zip)},
        'source_sha256':source_sha,'files':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in sorted(source.items())}},'auxiliary_files':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in sorted(auxiliary.items())}}
    payload={**auxiliary,'manifest.json':encoded(payload_manifest),'source.zip':source_zip}
    release=copy.deepcopy(old_release);release.update(production_admitted=approved,code_reference=DREF+'/18',code_manifest_sha256=sha(payload['manifest.json']),source_sha256=source_sha,
        source_archive_sha256=sha(source_zip),material_review_sha256=sha(material_raw),environment_sha256=sha(environment),deployment=deployment_inventory)
    release['dataset_references'][0]=DREF+'/18';release['storage']['environment_root']=ENVIRONMENT
    release['storage']['observed_assembled_source_copy_bytes']=sum(map(len,source.values()))+len(source_zip)+sum(map(len,auxiliary.values()))
    need(release['storage']['observed_assembled_source_copy_bytes']+16*1024**2+64*1024**2<128*1024**2,'source/proof/log reservation exceeded')
    output={'code-payload/'+n:b for n,b in payload.items()};output.update({'producer-source/'+n:b for n,b in source.items()})
    output['SOURCE-INVENTORY.json']=source_inventory;output['SOURCE-FREEZE.json']=encoded({'format':'irisx/rlvr-source-freeze-v1','source_sha256':source_sha,'source_archive_sha256':sha(source_zip),
        'source_members':259,'files':payload_manifest['source']['files'],'original_baseline200_exact':True,'producer_inventory_artifact_sha256':sha(source_inventory),
        'self_consistency_pins':{'NORMALIZED_SOURCE_CONTRACT_SHA256':normal_sha,'FINAL_V25_POLICY_SHA256':release['phase_policy_sha256'],'REVIEWED_ENVIRONMENT_SHA256':sha(environment)},'independent_approval_is_external':True})
    output['notebook-release.json']=encoded(release);output['assembly/finalize.py']=base['assembly/finalize.py'];output['assembly/accept_downloaded_mount.py']=base['assembly/accept_downloaded_mount.py'];output['assembly/verify_parent_wrappers.py']=wrappers
    for key,raw in {'material_review':material_raw,'environment':environment,'phase_policy':source['design/MEASURED-POLICY.json'],'owner_protocol':base['consumer-release/owner_protocol.json']}.items():output['consumer-release/'+key+'.json']=raw
    independent={'format':'owned-rl-independent-release-v1','source_sha256':source_sha,**{key+'_sha256':sha(output['consumer-release/'+key+'.json']) for key in ('material_review','environment','phase_policy','owner_protocol')}}
    independent_raw=encoded(independent);output['consumer-release/release.json']=independent_raw
    output.update({'terminal-consumer/'+n:b for n,b in consumer_bytes(base,independent_raw,source_sha,sha(source_zip),collector_sha).items()})
    builder=module(deployment['notebook_builder.py'],'run005_exact_notebook_builder',output_root/'code-payload/deployment/notebook_builder.py')
    entries=[]
    for old_n in prior['notebooks']:
        n=copy.deepcopy(old_n);active=n['role']=='rlvr004';raw=encoded(builder.build(release,deployment['source_loader.py'].decode(),kind='active-template' if active else 'inactive'))
        output[n['path']]=raw;n.update(bytes=len(raw),sha256=sha(raw),expected_predecessor_version=34 if active else 33,expected_version=35 if active else 34,
            predecessor_source_sha256=None if active else V33_SAVED,run_authorized=bool(approved and active),dataset_sources=release['dataset_references'],output_root=RUN,source_parent=SOURCE)
        entries.append(n)
    upload=[desc(b,n) for n,b in sorted(payload.items())];material_rows=[r for r in upload if r['path']!='source.zip']
    dataset=copy.deepcopy(prior['datasets'][0]);dataset.update(expected_predecessor_version=17,expected_version=18,root_manifest={'path':'manifest.json','sha256':sha(payload['manifest.json'])},
        upload_inventory=upload,upload_inventory_sha256=sha(canonical(upload)+b'\n'),version_notes='Run005 source-owned driver-location and bounded preflight diagnostic repair; code17/v33 preserved, original RL/scorer/model/data/resource/12h limits unchanged.',
        expected_readback_layouts={'original-upload':upload,'extracted-root':sorted(material_rows+[desc(b,n) for n,b in source.items()],key=lambda r:r['path']),
            'extracted-source-directory':sorted(material_rows+[desc(b,'source/'+n) for n,b in source.items()],key=lambda r:r['path'])})
    output['code-upload.zip']=zip_blobs(payload);dataset['transport_archive']=desc(output['code-upload.zip'],'code-upload.zip')
    output.update(predecessor(base,state_root,evidence_root));publication=copy.deepcopy(prior)
    publication.update(format='irisx/qwen14b-rlvr-run005-publication-contract-v1',source_freeze_sha256=sha(output['SOURCE-FREEZE.json']),runtime_source_sha256=source_sha,source_identity_sha256=source_sha,datasets=[dataset],notebooks=entries,
        predecessor_readiness={**desc(output['PREDECESSOR-EVIDENCE.json'],'PREDECESSOR-EVIDENCE.json'),'notebook_version':33,'notebook_source_sha256':V33_SAVED,'provider_status':'ERROR'},
        source_review_only=not approved,run_authorized=approved,release_runtime_finalized=approved,runtime_source_approval=desc(runtime_raw,'code-payload/release/RUNTIME-REVIEW.json'),
        parent_wrapper_verifier=desc(wrappers,'assembly/verify_parent_wrappers.py'),no_model_mount_acceptance_helper=desc(output['assembly/accept_downloaded_mount.py'],'assembly/accept_downloaded_mount.py'))
    publication['jit']['entry']=desc(output['assembly/finalize.py'],'assembly/finalize.py')
    publication['jit']['dependencies']=[desc(output['notebook-release.json'],'notebook-release.json')]+[desc(deployment[n],'code-payload/deployment/'+n) for n in ('notebook_builder.py','source_loader.py')]
    publication['consumer_contract'].update(source_sha256=source_sha,dataset_sha256=dataset_sha,source_archive=desc(source_zip,'code-payload/source.zip'),review_input_paths={'environment':SOURCE+'/release/REVIEWED-ENVIRONMENT.json','phase_policy':SOURCE+'/runtime/design/MEASURED-POLICY.json'},
        **{key:desc(output['consumer-release/'+key+'.json'],'consumer-release/'+key+'.json') for key in ('release','material_review','environment','phase_policy','owner_protocol')})
    prefix=Path(RUN).name;publication['terminal_contract'].update(evidence_path=prefix+'.evidence.zip',terminal_path=prefix+'.evidence.zip.terminal.json',checkpoint_path=prefix+'/checkpoints.zip',launcher_path=prefix+'-launcher',storage=release['storage'])
    output['publication-manifest.json']=encoded(publication);output['SUCCESSOR-PROPOSAL.json']=encoded(proposal_doc)
    output['ASSEMBLY-INVENTORY.json']=encoded({n:{'bytes':len(b),'sha256':sha(b)} for n,b in sorted(output.items())})
    output_root.mkdir(parents=True)
    for name,raw in sorted(output.items()):
        target=ordinary(output_root/relative(name));target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(raw)
        target.chmod(0o644)
        need(read(target)==raw,'assembled member roundtrip')
    return {'status':'INDEPENDENTLY_REVIEWED_SUCCESSOR_ASSEMBLED' if approved else 'INERT_SUCCESSOR_PROPOSAL_PREPARED','output_root':str(output_root),
        'proposal':desc(output['SUCCESSOR-PROPOSAL.json'],'SUCCESSOR-PROPOSAL.json'),'publication_manifest':desc(output['publication-manifest.json'],'publication-manifest.json'),
        'source_sha256':source_sha,'source_archive_sha256':sha(source_zip),'environment_sha256':sha(environment),'source_members':259,
        'baseline200_unchanged':True,'remaining257_source_members_unchanged':True,'family_role':'rlvr004','provider_calls':0,'model_or_GPU_calls':0,
        'original_v31_and_v33_preserved':True,'operational_success':False,'independent_publication_review_still_required':True}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('source','proposal','final'),required=True)
    for name in ('parent-overlay','parent-overlay-sha','output-root'):parser.add_argument('--'+name,required=True)
    for name in ('base-root','state-root','evidence-root','repository-root'):parser.add_argument('--'+name)
    for name in ('runtime-review','runtime-review-sha','material-review','material-review-sha','proposal','proposal-sha','collector','collector-sha','dataset-path-review','dataset-path-review-sha'):parser.add_argument('--'+name)
    args=vars(parser.parse_args())
    if args['mode']=='source':
        need(args['repository_root'],'Git source repository required')
        result=rebuild_source(**{k:args[k] for k in ('repository_root','parent_overlay','parent_overlay_sha','output_root')})
    else:
        args.pop('repository_root');need(all(args[k] for k in ('base_root','state_root','evidence_root')),'operational predecessor roots required')
        result=assemble(**args)
    print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
