"""Offline exact RLVR release assembler. Never calls provider, Git, Library or model."""
from pathlib import Path
import argparse,ast,copy,hashlib,importlib.util,io,json,re,shutil,stat,sys,zipfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
BASE=ROOT.parent
sys.path.insert(0,str(ROOT/'deployment'))
import source_loader as loader
import notebook_builder as notebooks

PREVIOUS=BASE/'portfolio63-checkpoint-repair-20261012'
OLD_SOURCE='ac73ca9b9f5549f6a4c5d2a876205d3dfebdbf9bba195c6a5d51f710d1eda404'
PREDECESSOR_DESCRIPTOR_SHA='ea0675c7d56126e141ab021c9f533d21f5b44ca526089e90db6c1144cc8ed940'
POLICY_SHA='3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda'
ENVIRONMENT_SHA='39d56dd0b5167ba43d9958ace70a8c2b031f29d421d051cfb75cbcff985f4c71'
SCORER_SHA='58216d4cf1ced5740b7f66b7be845d38ce327f5fb84048876aa54d3ca29f9f72'
DATASET_SHA='324140600ec7e833bb78e054b00a226a4f6d6732ca5fe1fb2ec6b001c987ef12'
OWNER_REQUEST={'owner_id':'danielwuu','request_id':'Sentinel_8879bbcf6048819182b1d5cd03126215','instruction':'我接下來是真的要離開了，要讓 astra ultra 不管怎樣就是要繼續迭代開發'}
assert OWNER_REQUEST['instruction']=='我接下來是真的要離開了，要讓 astra ultra 不管怎樣就是要繼續迭代開發'
DEPLOYMENT_NAMES={'source_loader.py','notebook_builder.py','launch_notebook.py','prepare_entry.py','parent_entry.py'}
SOURCE_ALLOWANCE=128*1024**2
SAVED_UPPER=18*1024**3+16*1024**2+SOURCE_ALLOWANCE
need=loader.need
sha=loader.digest
enc=loader.encoded


def raw(path,cap=64*1024**2):return loader.read_regular(Path(path).absolute(),cap)
def row(path,name=None):
    path=Path(path);data=raw(path)
    return {'path':name or path.name,'bytes':len(data),'sha256':sha(data)}
def write(path,data):
    path=Path(path);need(not path.exists() and not path.is_symlink(),'fresh assembly file required: '+str(path));path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(data if type(data) is bytes else enc(data))
    path.chmod(0o644)
def copy_file(path,target):write(target,raw(path))
def zip_blobs(files,*,stored=False):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED,compresslevel=None if stored else 9,allowZip64=True) as archive:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(loader.safe_name(name),(2026,10,12,0,0,0));info.create_system=3;info.external_attr=(stat.S_IFREG|0o644)<<16
            info.compress_type=zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED;archive.writestr(info,data)
    return stream.getvalue()


def source_inputs(archive_path,inventory_path):
    source_raw=raw(archive_path);frozen=json.loads(raw(inventory_path));declared=frozen['files']
    need(type(declared) is dict and all(type(v) is str for v in declared.values()),'complete immutable producer inventory required')
    with zipfile.ZipFile(io.BytesIO(source_raw)) as archive:
        need(set(archive.namelist())==set(declared) and len(archive.namelist())==len(declared),'exact immutable source archive inventory')
        files={name:archive.read(name) for name in sorted(declared)}
    need(all(sha(b)==declared[n] for n,b in files.items()),'frozen source member hash differs')
    need(loader.zip_source(files)==source_raw,'portable canonical stored source ZIP required')
    digest=sha(json.dumps(sorted(declared.items()),sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    need(frozen['source_sha256']==digest,'producer inventory digest differs')
    need(sha(files['design/MEASURED-POLICY.json'])==POLICY_SHA,'final v3 measured policy required')
    # Every inherited baseline member must equal already delivered code13 bytes.
    prior=PREVIOUS/'release-candidate-001/code-payload/source.zip'
    with zipfile.ZipFile(prior) as archive:
        need(len(archive.namelist())==200,'exact complete baseline200 required')
        need({n for n in files if n.startswith('baseline/')}=={'baseline/'+n for n in archive.namelist()},'original200 closure differs')
        for name in archive.namelist():need(files['baseline/'+name]==archive.read(name),'unchanged original baseline member: '+name)
    for name,data in files.items():
        if name.endswith('.py'):ast.parse(data,filename=name)
    return files,source_raw,digest,frozen


def production_pins(files,environment):
    path='owned_runtime/release.py';code=files[path]
    assignments={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(code).body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'NORMALIZED_SOURCE_CONTRACT_SHA256','FINAL_V25_POLICY_SHA256','REVIEWED_ENVIRONMENT_SHA256'}}
    need(assignments['FINAL_V25_POLICY_SHA256']==POLICY_SHA and assignments['REVIEWED_ENVIRONMENT_SHA256']==sha(environment)==ENVIRONMENT_SHA,'distinct final source release policy/environment pins required')
    normal,count=re.subn(rb"(?m)^NORMALIZED_SOURCE_CONTRACT_SHA256 = (?:None|'[0-9a-f]{64}')$",b'NORMALIZED_SOURCE_CONTRACT_SHA256 = None',code)
    need(count==1,'exact normalized source pin assignment')
    bound={n:sha(b) for n,b in files.items()};bound[path]=sha(normal)
    expected=sha(json.dumps(sorted(bound.items()),sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    need(assignments['NORMALIZED_SOURCE_CONTRACT_SHA256']==expected,'normalized source self-consistency differs')
    return assignments


def predecessor(out):
    descriptor=ROOT/'publication/PREDECESSOR-DESCRIPTORS.json'
    original=raw(descriptor)
    need(PREDECESSOR_DESCRIPTOR_SHA is not None and sha(original)==PREDECESSOR_DESCRIPTOR_SHA,'sealed exact v31 predecessor descriptors')
    proof=json.loads(original);evidence={}
    for key,ref in proof['evidence'].items():
        data=raw(ref['path']);need(len(data)==ref['bytes'] and sha(data)==ref['sha256'],'exact immutable v31 predecessor artifact: '+key)
        dest='predecessor/'+Path(ref['path']).name;write(out/dest,data);evidence[key]=row(out/dest,dest)
    proof['evidence']=evidence
    proof['original_descriptor_sha256']=sha(original)
    write(out/'PREDECESSOR-EVIDENCE.json',proof)
    write(out/'PREDECESSOR-DESCRIPTORS.json',original)
    return {**row(out/'PREDECESSOR-EVIDENCE.json'),'notebook_version':31,'notebook_source_sha256':OLD_SOURCE,'provider_status':'ERROR'}


def consumer_documents(material_raw,environment_raw,policy_raw,source_sha):
    owner_protocol={'format':'owned-rl-reviewed-owner-protocol-v1','scope':'production-rl-abc','role':'rl-abc',
        'owner_identity_namespace':'verified existing Kaggle account owner; not a ChatGPT authentication subject',
        'original_owner_request':OWNER_REQUEST,'related_provenance_request_id':'Sentinel_66fb71fe5a14819198775e39f56c2393',
        'release_role':'rlvr004','clock_offsets':{'inner':42000,'outer':42180,'provider':42300,'absolute':43200},
        'publisher_authority':'separate authenticated approval required; no descriptor or source flag grants it',
        'existing_resource_only':True,'public_goal_numerator':151,'public_goal_denominator':167,'no_new_auth_grants_resources_quota':True}
    consumer_docs={'material_review':material_raw,'environment':environment_raw,'phase_policy':policy_raw,'owner_protocol':enc(owner_protocol)}
    independent_release={'format':'owned-rl-independent-release-v1','source_sha256':source_sha,**{name+'_sha256':sha(data) for name,data in consumer_docs.items()}}
    return consumer_docs,independent_release

def build(*,archive,inventory,environment,material_review,runtime_review,consumer_root,out,publishable):
    out=Path(out).absolute();need(not out.exists(),'fresh release output root required')
    files,source_raw,source_sha,source_inventory=source_inputs(archive,inventory)
    environment_raw=raw(environment);need(sha(environment_raw)==ENVIRONMENT_SHA,'exact independently reviewed environment candidate')
    material_raw=raw(material_review);material=json.loads(material_raw);runtime_raw=raw(runtime_review)
    need(material['runtime_review_sha256']==sha(runtime_raw),'material review must bind exact runtime review artifact')
    need(material['format']=='owned-rl-reviewed-material-v1' and material['source_sha256']==source_sha and material['source_archive_sha256']==sha(source_raw),'independent final material source binding differs')
    need(material['environment_sha256']==ENVIRONMENT_SHA and material['phase_policy_sha256']==POLICY_SHA and material['dataset_file_sha256']==DATASET_SHA,'reviewed environment/policy/dataset binding differs')
    pins=production_pins(files,environment_raw) if publishable else None
    auxiliary={'NOTICE.txt':raw(PREVIOUS/'release-candidate-001/code-payload/NOTICE.txt'),
        'release/MATERIAL-REVIEW.json':material_raw,'release/REVIEWED-ENVIRONMENT.json':environment_raw,
        'release/RUNTIME-REVIEW.json':runtime_raw}
    for name in sorted(DEPLOYMENT_NAMES):auxiliary['deployment/'+name]=raw(ROOT/'deployment'/name)
    actual_deployment={name:{'bytes':len(auxiliary['deployment/'+name]),'sha256':sha(auxiliary['deployment/'+name])} for name in sorted(DEPLOYMENT_NAMES)}
    need(material['deployment_inventory']==actual_deployment,'material review must bind exact external deployment bytes')
    manifest={'format':loader.FORMAT,'reference':'danielwuu/iris-x-learning-agent-code-20261011/17',
        'source':{'archive':{'name':'source.zip','bytes':len(source_raw),'sha256':sha(source_raw)},'source_sha256':source_sha,
            'files':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in files.items()}},
        'auxiliary_files':{n:{'bytes':len(b),'sha256':sha(b)} for n,b in auxiliary.items()}}
    manifest_raw=enc(manifest)
    payload={**auxiliary,'manifest.json':manifest_raw,'source.zip':source_raw}
    out.mkdir()
    for name,data in payload.items():write(out/'code-payload'/name,data)
    for name,data in files.items():write(out/'producer-source'/name,data)
    oldpins=json.loads(raw(PREVIOUS/'release-candidate-001/pins.json'));oldpublication=json.loads(raw(PREVIOUS/'release-candidate-001/publication-manifest.json'))
    dataset_refs=copy.deepcopy(oldpublication['notebooks'][0]['dataset_sources']);dataset_refs[0]='danielwuu/iris-x-learning-agent-code-20261011/17'
    source_bytes=sum(map(len,files.values()));aux_bytes=sum(map(len,auxiliary.values()))
    # Exactly these materialized source copies and two hard-capped log pairs.
    source_copy_bytes=source_bytes+len(source_raw)+aux_bytes
    need(source_copy_bytes+16*1024**2+64*1024**2<SOURCE_ALLOWANCE,'source+logs+bounded proof reservation exceeds reviewed allowance')
    release={'format':'irisx/rlvr-notebook-release-v1','release_role':'rlvr004','production_admitted':bool(publishable),
        'admission_scope':'independently reviewed immutable materials; run still requires separate authenticated publisher approval',
        'code_reference':manifest['reference'],'code_manifest_sha256':sha(manifest_raw),'source_sha256':source_sha,
        'source_archive_sha256':sha(source_raw),'material_review_sha256':sha(material_raw),'environment_sha256':sha(environment_raw),
        'phase_policy_sha256':POLICY_SHA,'scorer_pins_sha256':SCORER_SHA,'deployment':actual_deployment,
        'material_pins':{'data':oldpins['data'],'training':oldpins['training']},'dataset_references':dataset_refs,
        'original_owner_request':OWNER_REQUEST,'data_mount_layout':'datasets-owner-slug',
        'storage':{'evidence_expanded_bytes':5*1024**3,'evidence_archive_bytes':5*1024**3+16*1024**2,'checkpoint_archive_bytes':4*1024**3,
            'saved_auxiliary_allowance_bytes':SOURCE_ALLOWANCE,'observed_assembled_source_copy_bytes':source_copy_bytes,
            'both_parent_log_pairs_cap_bytes':16*1024**2,'parent_metadata_and_proof_reservation_bytes':64*1024**2,
            'saved_working_upper_bytes':SAVED_UPPER,'provider_saved_output_limit_bytes':20000000000,'saved_limit_headroom_bytes':20000000000-SAVED_UPPER,
            'co_resident_peak_plus_reserve_bytes':SAVED_UPPER+4*1024**3,
            'environment_root':'/tmp/irisx-qwen14b-rlvr-20261012-environment004','environment_saved':False}}
    write(out/'notebook-release.json',release)
    source_freeze={'format':'irisx/rlvr-source-freeze-v1','source_sha256':source_sha,'source_archive_sha256':sha(source_raw),
        'source_members':len(files),'files':manifest['source']['files'],'original_baseline200_exact':True,
        'producer_inventory_artifact_sha256':sha(raw(inventory)),'self_consistency_pins':pins,'independent_approval_is_external':True}
    write(out/'SOURCE-FREEZE.json',source_freeze)
    write(out/'SOURCE-INVENTORY.json',raw(inventory))
    for name in ('finalize.py','accept_downloaded_mount.py','verify_parent_wrappers.py'):copy_file(HERE/name,out/'assembly'/name)
    consumer_docs,independent_release=consumer_documents(material_raw,environment_raw,files['design/MEASURED-POLICY.json'],source_sha)
    for name,data in consumer_docs.items():write(out/'consumer-release'/(name+'.json'),data)
    write(out/'consumer-release/release.json',independent_release)
    # No consumer Python is put inside producer inventory or Kaggle model code Dataset.
    consumer=Path(consumer_root);consumer_inventory=consumer/'CONSUMER-INVENTORY.json'
    need(consumer_inventory.is_file(),'frozen external consumer inventory required')
    for path in sorted(consumer.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.pyc','.pyo'):continue
        if path.suffix in ('.py','.json','.md') and 'tests' not in path.parts:copy_file(path,out/'terminal-consumer'/path.relative_to(consumer))
    entries=[]
    for kind in ('inactive','active-template'):
        name='iris-x-qwen14b-rlvr-'+kind+'.ipynb';data=enc(notebooks.build(release,auxiliary['deployment/source_loader.py'].decode(),kind=kind));write(out/name,data)
        active=kind=='active-template';old=copy.deepcopy(oldpublication['notebooks'][1 if active else 0])
        old.update(role='rlvr004' if active else 'inactive',template_role=kind,path=name,bytes=len(data),sha256=sha(data),
            expected_predecessor_version=32 if active else 31,expected_version=33 if active else 32,
            predecessor_source_sha256=None if active else OLD_SOURCE,manual_start=False,enable_model=False,
            run_authorized=bool(publishable and active),dataset_sources=dataset_refs,output_root=notebooks.OUTPUT,source_parent=notebooks.SOURCE,
            epoch_policy='one explicit pure acyclic JIT finalization; all four documents share original epoch; no fallback/reset',source_dispatch_ready=False)
        old.pop('dispatch_epoch_patch',None);entries.append(old)
    upload=[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in sorted(payload.items())]
    material_rows=[r for r in upload if r['path']!='source.zip']
    dataset=copy.deepcopy(oldpublication['datasets'][0]);dataset.update(expected_predecessor_version=16,expected_version=17,
        root_manifest={'path':'manifest.json','sha256':sha(manifest_raw)},upload_inventory=upload,
        upload_inventory_sha256=sha((json.dumps(upload,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()),
        expected_readback_layouts={'original-upload':upload,'extracted-root':sorted(material_rows+[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in files.items()],key=lambda r:r['path']),
        'extracted-source-directory':sorted(material_rows+[{'path':'source/'+n,'bytes':len(b),'sha256':sha(b)} for n,b in files.items()],key=lambda r:r['path'])})
    write(out/'code-upload.zip',zip_blobs(payload));dataset['transport_archive']=row(out/'code-upload.zip')
    consumer_contract={'format':'irisx/rlvr-independent-consumer-contract-v1','source_sha256':source_sha,'dataset_sha256':DATASET_SHA,
        'source_archive':row(out/'code-payload/source.zip','code-payload/source.zip'),'source_root':'producer-source',
        'review_input_paths':{'environment':'/kaggle/working/irisx-qwen14b-rlvr-20261012-source004/release/REVIEWED-ENVIRONMENT.json','phase_policy':'/kaggle/working/irisx-qwen14b-rlvr-20261012-source004/runtime/design/MEASURED-POLICY.json'},
        **{name:row(out/'consumer-release'/(name+'.json'),'consumer-release/'+name+'.json') for name in ('release','material_review','environment','phase_policy','owner_protocol')}}
    publication={'format':'irisx/qwen14b-rlvr-startup-repair-publication-contract-v1','source_freeze_sha256':sha(enc(source_freeze)),
        'runtime_source_sha256':source_sha,'source_identity_sha256':source_sha,'datasets':[dataset],'notebooks':entries,
        'predecessor_readiness':predecessor(out),'upload_authorities':oldpublication['upload_authorities'],
        'owner_published_stable_commit':oldpublication['owner_published_stable_commit'],'owner_published_stable_tree':oldpublication['owner_published_stable_tree'],
        'candidate_git_published':False,'git_gate_required':False,'run_authorized':bool(publishable),'provider_publication_completed':False,
        'gpu_runtime_verified':False,'source_review_only':not publishable,'release_runtime_finalized':bool(publishable),
        'local_assembly_performs_provider_calls':False,'requires_separate_operator_review':True,'dispatch_ready':False,
        'runtime_source_approval':row(out/'code-payload/release/RUNTIME-REVIEW.json','code-payload/release/RUNTIME-REVIEW.json'),
        'parent_wrapper_verifier':row(out/'assembly/verify_parent_wrappers.py','assembly/verify_parent_wrappers.py'),
        'no_model_mount_acceptance_helper':row(out/'assembly/accept_downloaded_mount.py','assembly/accept_downloaded_mount.py'),
        'jit':{'format':'irisx/rlvr-pure-finalizer-contract-v1','entry':row(out/'assembly/finalize.py','assembly/finalize.py'),
            'dependencies':[row(out/'notebook-release.json','notebook-release.json')]+[row(out/'code-payload/deployment'/name,'code-payload/deployment/'+name) for name in ('notebook_builder.py','source_loader.py')],
            'output_documents':['active-finalized.ipynb','original-request.json','operator.json','parent-private-scorer.json'],'maximum_dispatch_age_seconds':60},
        'consumer_contract':consumer_contract,'terminal_contract':{'archive_caps':{'evidence_expanded_bytes':5*1024**3,'evidence_archive_bytes':5*1024**3+16*1024**2,
            'checkpoint_archive_bytes':4*1024**3,'members':12000,'json_bytes':2*1024**3,'journal_bytes':3276800000,'free_disk_reserve_bytes':4*1024**3},
            'inventory_scope':'selected_outputs_only','checkpoint_default_mode':'header-only','zip64':True,
            'evidence_path':Path(notebooks.OUTPUT).name+'.evidence.zip','terminal_path':Path(notebooks.OUTPUT).name+'.evidence.zip.terminal.json',
            'checkpoint_path':Path(notebooks.OUTPUT).name+'/checkpoints.zip','launcher_path':Path(notebooks.OUTPUT).name+'-launcher','storage':release['storage']}}
    write(out/'publication-manifest.json',publication)
    write(out/'ASSEMBLY-INVENTORY.json',{p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':sha(raw(p))} for p in sorted(out.rglob('*')) if p.is_file()})
    return {'status':'LOCAL_PUBLISHABLE_MATERIAL_PREPARED' if publishable else 'SOURCE_ONLY_PREVIEW','source_sha256':source_sha,
        'publication_manifest':row(out/'publication-manifest.json'),'output':str(out),'provider_Git_Library_GPU_calls':0}


def main():
    p=argparse.ArgumentParser()
    for name in ('archive','inventory','environment','material-review','runtime-review','consumer-root','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--publishable',action='store_true');a=p.parse_args()
    print(json.dumps(build(**vars(a)),sort_keys=True))

if __name__=='__main__':main()
